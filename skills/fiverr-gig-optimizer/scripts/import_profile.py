#!/usr/bin/env python3
"""import_profile.py — optional: pre-fill from the user's own Fiverr profile.

Given a Fiverr profile URL (or username), fetches the seller's PUBLIC profile
and each existing gig's current packages (prices, delivery, tags) so the skill
can pre-fill Step 1 and optimize gigs the seller already has. Uses the same
vendored Perseus engine as scrape.py.

PUBLIC DATA ONLY. This never logs in and cannot access private analytics
(impressions, clicks, conversion, earnings, order queue). Opt-in; the skill
runs it only when the user provides their profile link. Works from a
residential IP (set PROXY_URL otherwise). The user's own ToS responsibility.

CLI:
    import_profile.py --url https://www.fiverr.com/<username> \
        [--limit 20] [--out profile-import.json] [--config path.json]

Output: a single JSON object on stdout (and --out if given).
"""
import argparse
import collections
import json
import os
import sys
import time
from urllib.parse import urlparse

# Reuse the pure mapping helpers (no heavy imports at module load).
import scrape


def default_config_path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "references", "scoring-config.json")


def load_config(path=None):
    with open(path or default_config_path(), encoding="utf-8") as fh:
        return json.load(fh)


def extract_username(url_or_name):
    """Accept a bare username or any fiverr.com/<username>[/...] URL."""
    s = (url_or_name or "").strip()
    if "://" not in s and "/" not in s:
        return s
    if "://" not in s:
        s = "https://" + s
    parts = [p for p in urlparse(s).path.split("/") if p]
    if not parts:
        raise ValueError(f"could not find a username in: {url_or_name}")
    return parts[0]


def map_existing_gig(detail, fx):
    """A lightweight 'current gig' record (the seller's OWN gig, with prices).

    Not a competitor row: no gig_count_in_search (this isn't a market search).
    """
    detail = detail or {}
    tiers = scrape._packages_to_tiers(detail.get("packages", []), fx, duration_in_hours=True)
    return {
        "title": detail.get("title"),
        "url": detail.get("url"),
        "category": detail.get("category"),
        "subcategory": detail.get("sub_category"),
        "seller_level": (detail.get("seller") or {}).get("level"),
        "seller_country": (detail.get("seller") or {}).get("country"),
        "rating": detail.get("rating"),
        "review_count": detail.get("reviews_count"),
        "tags": [t.lower() for t in (detail.get("tags") or []) if t],
        "pricing": {
            "basic": {"price": tiers["basic_price"], "delivery_days": tiers["basic_delivery_days"]},
            "standard": {"price": tiers["standard_price"], "delivery_days": tiers["standard_delivery_days"]},
            "premium": {"price": tiers["premium_price"], "delivery_days": tiers["premium_delivery_days"]},
        },
    }


def suggested_services(existing_gigs, top_n=8):
    """Seed keywords from the seller's own tags (most frequent first)."""
    counter = collections.Counter()
    for g in existing_gigs:
        counter.update(g.get("tags") or [])
    return [tag for tag, _ in counter.most_common(top_n)]


def import_profile(url_or_name, cfg, limit=20, today=None):
    today = today or time.strftime("%Y-%m-%d")
    fx = cfg["fx"]
    username = extract_username(url_or_name)

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
    try:
        from fiverr_perseus_scraper import FiverrScraper
    except ImportError as exc:
        print(f"error: needs curl-cffi + beautifulsoup4 "
              f"(pip install -r requirements.txt): {exc}", file=sys.stderr)
        sys.exit(1)

    sc = FiverrScraper()
    profile = sc.get_seller_profile(username)
    if profile.get("error"):
        print(f"error: could not load profile '{username}': {profile['error']}",
              file=sys.stderr)
        sys.exit(5)

    existing = []
    for gig in (profile.get("gigs") or [])[:limit]:
        gig_url = gig.get("url")
        if not gig_url:
            continue
        detail = sc.get_gig_details(gig_url)
        if detail.get("error"):
            print(f"warning: skipped gig (blocked): {gig_url}", file=sys.stderr)
            continue
        detail.setdefault("url", gig_url)
        existing.append(map_existing_gig(detail, fx))

    approved = profile.get("approved_gigs_count") or 0
    if not existing and approved:
        print(f"warning: profile loaded but no gigs could be imported "
              f"(approved_gigs_count={approved}). Likely a transient block — "
              f"retry, or set PROXY_URL if you are not on a residential IP.",
              file=sys.stderr)

    # seller_level: prefer the profile's gigsData value (reliable), fall back to
    # the per-gig detail level; None -> the skill asks the user.
    levels = [g.get("seller_level") for g in (profile.get("gigs") or []) if g.get("seller_level")]
    levels += [g["seller_level"] for g in existing if g.get("seller_level")]
    seller_level = collections.Counter(levels).most_common(1)[0][0] if levels else None

    return {
        "source": "fiverr_profile",
        "scraped_at": today,
        "public_data_only": True,
        "username": username,
        "name": profile.get("display_name") or username,
        "location": profile.get("location"),
        "member_since": profile.get("member_since"),
        "verified": profile.get("is_verified"),
        "approved_gigs_count": profile.get("approved_gigs_count"),
        "seller_level": seller_level,
        "existing_gigs": existing,
        "suggested_services": suggested_services(existing),
        "note": "Public profile + gigs only. No private analytics "
                "(impressions/clicks/earnings) — ask the user for goals.",
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Import a user's own public Fiverr profile + gig prices.")
    ap.add_argument("--url", required=True, help="Fiverr profile URL or username.")
    ap.add_argument("--limit", type=int, default=20, help="Max gigs to fetch details for.")
    ap.add_argument("--out", help="Optional path to also write the JSON.")
    ap.add_argument("--config", help="Path to scoring-config.json.")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    result = import_profile(args.url, cfg, limit=args.limit)
    text = json.dumps(result, indent=2, ensure_ascii=False)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
    import reminders
    reminders.contribution_reminder(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
