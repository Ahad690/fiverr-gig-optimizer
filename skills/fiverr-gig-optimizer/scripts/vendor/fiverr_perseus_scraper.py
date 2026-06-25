"""Fiverr Perseus reader — VENDORED, MIT.

Source: KyuRish/fiverr-mcp-server  (src/fiverr_mcp_server/utils/scraper.py)
        https://github.com/KyuRish/fiverr-mcp-server  @ v0.1.1 (2026-02-23)
Copyright (c) 2026 KyuRish. Licensed under the MIT License — see ./LICENSE.

This file is vendored ~verbatim and is the only component that talks to Fiverr.
It parses Fiverr's `perseus-initial-props` SSR blob via curl_cffi TLS
impersonation and uniquely exposes `total_results` (= rawListingData.num_found),
which we use as `gig_count_in_search`. Kept faithful for easy upstream diffing;
all schema mapping and the hours->days delivery fix live in ../scrape.py, not
here. Requires: curl-cffi, beautifulsoup4 (see requirements.txt).
"""
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse

from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

logger = logging.getLogger(__name__)

# Fiverr category slugs for the list_categories tool
FIVERR_CATEGORIES = {
    "graphics-design": "Graphics & Design",
    "programming-tech": "Programming & Tech",
    "digital-marketing": "Digital Marketing",
    "video-animation": "Video & Animation",
    "writing-translation": "Writing & Translation",
    "music-audio": "Music & Audio",
    "business": "Business",
    "consulting": "Consulting",
    "ai-services": "AI Services",
    "personal-growth": "Personal Growth & Hobbies",
}


class FiverrScraper:
    BASE_URL = "https://www.fiverr.com"
    SEARCH_URL = f"{BASE_URL}/search/gigs"

    ACHIEVEMENT_MAP = {
        1: "level_one_seller",
        2: "level_two_seller",
        3: "top_rated_seller",
    }

    _FIVERR_HOST_RE = re.compile(r"^(www\.)?fiverr\.com$", re.IGNORECASE)
    _USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]+$")

    def __init__(self):
        self.session = cffi_requests.Session(impersonate="chrome")
        self._last_request_time = 0.0
        self._lock = threading.Lock()
        try:
            self._min_delay = max(1.0, float(os.getenv("RATE_LIMIT_DELAY", "2")))
        except (ValueError, TypeError):
            self._min_delay = 2.0
        proxy_url = os.getenv("PROXY_URL", "")
        if proxy_url:
            self.session.proxies = {
                "http": proxy_url,
                "https": proxy_url,
            }

    def _throttle(self):
        with self._lock:
            elapsed = time.time() - self._last_request_time
            if elapsed < self._min_delay:
                time.sleep(self._min_delay - elapsed)
            self._last_request_time = time.time()

    def _validate_fiverr_url(self, url: str) -> str:
        """Ensure URL points to fiverr.com over HTTP(S). Raises ValueError otherwise."""
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"URL scheme must be http or https, got: {parsed.scheme}")
        if not self._FIVERR_HOST_RE.match(parsed.hostname or ""):
            raise ValueError(f"URL must point to fiverr.com, got: {parsed.hostname}")
        return url

    def _normalize_url(self, path: str) -> str:
        """Convert a path or full URL to a validated Fiverr URL."""
        if "://" in path:
            return self._validate_fiverr_url(path)
        return f"{self.BASE_URL}/{path.lstrip('/')}"

    @staticmethod
    def _validate_username(username: str) -> str:
        """Validate username is alphanumeric + underscores only."""
        if not FiverrScraper._USERNAME_RE.match(username):
            raise ValueError(f"Invalid Fiverr username: {username}")
        return username

    def _fetch_page(self, url: str, retries: int = 3) -> BeautifulSoup:
        browsers = ["chrome", "safari", "chrome110"]
        for attempt in range(retries):
            self._throttle()
            browser = browsers[attempt % len(browsers)]
            try:
                response = self.session.get(
                    url, impersonate=browser, timeout=30,
                )
            except (ConnectionError, TimeoutError, OSError) as e:
                logger.warning("Request failed (attempt %d/%d): %s", attempt + 1, retries, e)
                if attempt < retries - 1:
                    time.sleep(3 * (attempt + 1))
                    continue
                raise
            if response.status_code == 200:
                return BeautifulSoup(response.text, "html.parser")
            if response.status_code == 403 and attempt < retries - 1:
                logger.warning("Got 403, retrying with %s (attempt %d/%d)", browser, attempt + 1, retries)
                time.sleep(3 * (attempt + 1))
                continue
            response.raise_for_status()
        raise RuntimeError(f"Failed to fetch {url} after {retries} retries")

    def _extract_perseus_props(self, soup: BeautifulSoup) -> dict:
        script = soup.find("script", id="perseus-initial-props")
        if not script or not script.contents:
            logger.warning("No perseus-initial-props found on page")
            return {}
        try:
            raw = script.contents[0]
            text = raw if isinstance(raw, str) else raw.text
            return json.loads(text)
        except (json.JSONDecodeError, AttributeError, IndexError) as e:
            logger.warning("Failed to parse perseus props: %s", e)
            return {}

    # --- Search ---

    def search_gigs(
        self,
        query: str,
        category: str = "",
        min_price: int | None = None,
        max_price: int | None = None,
        seller_level: str = "",
        sort_by: str = "relevance",
        page: int = 1,
    ) -> dict:
        params: dict = {"query": query}
        if page > 1:
            params["page"] = str(page)
        if category:
            params["category"] = category
        if min_price is not None or max_price is not None:
            low = min_price if min_price is not None else ""
            high = max_price if max_price is not None else ""
            params["price_buckets"] = f"{low}-{high}"
        if seller_level:
            params["seller_level"] = seller_level
        if sort_by and sort_by != "relevance":
            params["sort_by"] = sort_by

        url = f"{self.SEARCH_URL}?{urlencode(params)}"
        soup = self._fetch_page(url)
        props = self._extract_perseus_props(soup)

        if not props:
            return {
                "gigs": [], "query": query, "page": page,
                "total_results": 0, "has_more": False,
                "error": "Could not extract search data - Fiverr may have blocked this request",
            }

        gigs = []
        items = props.get("items", [])
        for item in items:
            gigs.append(self._parse_search_item(item))

        # Pagination info from raw listing data
        raw = props.get("rawListingData", {})
        total_results = raw.get("num_found", 0) or 0
        has_more = raw.get("has_more", False)

        return {
            "gigs": gigs,
            "query": query,
            "page": page,
            "total_results": total_results,
            "has_more": has_more,
        }

    def _parse_search_item(self, item: dict) -> dict:
        gig_url = item.get("gig_url", "")
        if gig_url and not gig_url.startswith("http"):
            gig_url = f"{self.BASE_URL}{gig_url}"

        # Convert cents to dollars
        price_cents = item.get("price_i", 0) or 0

        return {
            "title": item.get("title", ""),
            "seller_name": item.get("seller_name", ""),
            "seller_level": item.get("seller_level", ""),
            "price": round(price_cents / 100, 2),
            "rating": float(item.get("buying_review_rating", 0) or 0),
            "reviews_count": int(item.get("buying_review_rating_count", 0) or 0),
            "url": gig_url,
        }

    # --- Gig Details ---

    def get_gig_details(self, url: str) -> dict:
        url = self._normalize_url(url)
        soup = self._fetch_page(url)
        props = self._extract_perseus_props(soup)

        if not props:
            return {"url": url, "error": "Could not extract page data - Fiverr may have blocked this request"}

        # Overview has gig + seller summary
        overview = props.get("overview", {})
        gig_overview = overview.get("gig", {})

        if not gig_overview.get("title"):
            return {"url": url, "error": "Gig not found or has been removed"}
        seller_overview = overview.get("seller", {})
        categories = overview.get("categories", {})

        # Seller card has detailed seller info
        seller_card = props.get("sellerCard", {})

        # Description
        desc_data = props.get("description", {})
        description = desc_data.get("content", "")

        # Packages - convert cents to dollars
        packages_data = props.get("packages", {})
        package_list = packages_data.get("packageList", [])
        packages = []
        for pkg in package_list:
            revisions_data = pkg.get("revisions", {})
            raw_revisions = revisions_data.get("value", 0) if isinstance(revisions_data, dict) else 0
            revisions = raw_revisions if raw_revisions >= 0 else -1  # -1 = unlimited

            features = []
            for feat in pkg.get("features", []):
                if isinstance(feat, dict) and feat.get("included"):
                    label = feat.get("label", "")
                    value = feat.get("value", "")
                    feat_type = feat.get("type", "")
                    if feat_type == "BOOLEAN":
                        features.append(label)
                    elif feat_type == "NUMERIC" and value:
                        features.append(f"{label}: {value}")
                    else:
                        features.append(label)

            price_cents = pkg.get("price", 0)

            packages.append({
                "name": pkg.get("title", "Package"),
                "price": round(price_cents / 100, 2),
                "description": pkg.get("description", ""),
                "delivery_days": pkg.get("duration", 0),
                "revisions": revisions,
                "features": features,
            })

        # Tags
        tags_data = props.get("tags", {})
        tags = [
            t.get("name", "") for t in tags_data.get("tagsGigList", [])
            if isinstance(t, dict)
        ]

        # Metadata from description
        metadata = {}
        for attr in desc_data.get("metadataAttributes", []):
            if isinstance(attr, dict):
                name = attr.get("name", "")
                values = attr.get("values", [])
                if name and values:
                    metadata[name] = [
                        v.get("name", str(v)) if isinstance(v, dict) else str(v)
                        for v in values
                    ]

        # Category info
        cat = categories.get("category", {})
        sub_cat = categories.get("subCategory", {})

        # Seller level from achievement number
        achievement = seller_overview.get("achievement", 0)
        seller_level = self.ACHIEVEMENT_MAP.get(achievement, "")

        return {
            "url": url,
            "title": gig_overview.get("title", ""),
            "description": description,
            "seller": {
                "username": seller_overview.get("username", ""),
                "display_name": seller_overview.get("displayName", "")
                                or seller_card.get("displayName", ""),
                "level": seller_level,
                "country": seller_card.get("countryCode", ""),
            },
            "packages": packages,
            "tags": tags,
            "metadata": metadata,
            "rating": float(gig_overview.get("rating", 0) or 0),
            "reviews_count": int(gig_overview.get("ratingsCount", 0) or 0),
            "category": cat.get("name", ""),
            "sub_category": sub_cat.get("name", ""),
            "orders_in_queue": gig_overview.get("ordersInQueue", 0),
        }

    # --- Seller Profile ---

    def get_seller_profile(self, username: str) -> dict:
        self._validate_username(username)
        url = f"{self.BASE_URL}/{username}"
        soup = self._fetch_page(url)
        props = self._extract_perseus_props(soup)

        if not props:
            return {"username": username, "url": url,
                    "error": "Could not extract profile data - seller may not exist or Fiverr blocked the request"}

        seller = props.get("seller", {})
        user = seller.get("user", {})
        profile = user.get("profile", {})
        address = user.get("address", {})

        # Languages
        languages = []
        for lang in user.get("languages", []):
            if isinstance(lang, dict):
                languages.append({
                    "language": lang.get("code", ""),
                    "level": lang.get("level", ""),
                })

        # Member since (unix timestamp)
        joined_at = user.get("joinedAt", 0)
        member_since = ""
        if joined_at:
            try:
                member_since = datetime.fromtimestamp(joined_at, tz=timezone.utc).strftime("%b %Y")
            except (ValueError, OSError):
                pass

        # Gigs data
        gigs_data = props.get("gigsData", [])
        gigs = []
        for gig in gigs_data:
            if isinstance(gig, dict):
                # LOCAL FIX (fiverr-gig-optimizer): current Fiverr profile
                # gigsData uses "gig_url", not "url"; without this every profile
                # gig comes back with an empty URL. See vendor/NOTICE.md.
                gig_url = gig.get("gig_url") or gig.get("url") or ""
                if gig_url and not gig_url.startswith("http"):
                    gig_url = f"{self.BASE_URL}{gig_url}"
                gigs.append({
                    "title": gig.get("title", ""),
                    "url": gig_url,
                    "rating": float(gig.get("rating", 0) or 0),
                })

        # Certifications
        certifications = [
            {
                "name": c.get("certificationName", ""),
                "from": c.get("receivedFrom", ""),
                "year": c.get("year", 0),
            }
            for c in seller.get("certifications", []) if isinstance(c, dict)
        ]

        # Hourly rate - convert cents to dollars
        hourly_rate = seller.get("hourlyRate", {})
        hourly_cents = hourly_rate.get("priceInCents", 0) if isinstance(hourly_rate, dict) else 0

        return {
            "username": user.get("name", username),
            "url": url,
            "display_name": profile.get("displayName", ""),
            "bio": seller.get("oneLinerTitle", ""),
            "location": address.get("countryName", ""),
            "member_since": member_since,
            "response_time": "Highly responsive" if seller.get("isHighlyResponsive") else "",
            "description": seller.get("description", ""),
            "languages": languages,
            "gigs": gigs,
            "certifications": certifications,
            "hourly_rate": round(hourly_cents / 100, 2) if hourly_cents else 0,
            "approved_gigs_count": seller.get("approvedGigsCount", 0),
            "is_verified": user.get("isVerified", False),
        }

    # --- Reviews ---

    def get_gig_reviews(self, url: str) -> dict:
        url = self._normalize_url(url)
        soup = self._fetch_page(url)
        props = self._extract_perseus_props(soup)

        if not props:
            return {
                "reviews": [], "url": url,
                "error": "Could not extract review data - Fiverr may have blocked this request",
            }

        # Check if the gig actually exists on this page
        overview = props.get("overview", {})
        gig_overview = overview.get("gig", {})
        if not gig_overview.get("title"):
            return {
                "reviews": [], "url": url,
                "error": "Gig not found or has been removed",
            }

        return {
            "reviews": self._parse_reviews_from_props(props),
            "url": url,
        }

    def _parse_reviews_from_props(self, props: dict) -> list:
        # Current structure: props["reviews"] is a dict with "reviews" list inside
        reviews_section = props.get("reviews", {})
        if isinstance(reviews_section, dict):
            reviews_list = reviews_section.get("reviews", [])
            if reviews_list:
                return self._format_reviews(reviews_list)

        # Legacy structure: props["reviewsData"]["buying_reviews"]["reviews"]
        reviews_data = props.get("reviewsData", {})
        if isinstance(reviews_data, dict):
            buying = reviews_data.get("buying_reviews", {})
            if isinstance(buying, dict):
                reviews_list = buying.get("reviews", [])
                if reviews_list:
                    return self._format_reviews(reviews_list)

        return []

    def _format_reviews(self, reviews: list) -> list:
        result = []
        for review in reviews:
            if not isinstance(review, dict):
                continue

            # Current fields: username, reviewer_country, value, created_at, comment
            # Legacy fields: reviewer.name, reviewer.country, rating, date, text
            buyer_name = review.get("username", "")
            country = review.get("reviewer_country") or review.get("reviewer_country_code") or ""

            if not buyer_name:
                reviewer = review.get("reviewer") or review.get("buyer") or {}
                if isinstance(reviewer, dict):
                    buyer_name = reviewer.get("name") or reviewer.get("username") or ""
                    country = country or reviewer.get("country") or ""

            result.append({
                "buyer_name": buyer_name,
                "country": country,
                "rating": review.get("value") or review.get("rating") or 0,
                "date": review.get("created_at") or review.get("date") or review.get("createdAt") or "",
                "text": review.get("comment") or review.get("text") or review.get("body") or "",
            })
        return result