#!/usr/bin/env python3
"""scrape.py — opt-in live scrape into the canonical schema. FR5.

Runs ONLY at the user's request (the skill never scrapes by default and ships
no key). Two engines:

  - PRIMARY: "kyurish" — the vendored Perseus reader
    (scripts/vendor/fiverr_perseus_scraper.py, MIT). It parses Fiverr's SSR
    blob with curl_cffi TLS impersonation and uniquely returns the search total
    (`num_found`), which we record as `gig_count_in_search`. Needs no account;
    on a residential IP it works without a proxy (set PROXY_URL otherwise).

  - FALLBACK: "apify" — the configured Apify actor (automation-lab/...). Useful
    when you have residential proxies and the primary is blocked. NOTE: no Apify
    actor returns the search total, so `gig_count_in_search` stays null on this
    path; get the count from a manual paste instead.

Delivery fix: Fiverr's package `duration` is in HOURS; we divide by 24 to get
delivery days. Prices normalize to USD via the static fx table
(usd = price * fx.rates[currency]).

CLI:
    scrape.py --query "ai chatbot" [--category "Programming & Tech"] \
        [--engine auto|kyurish|apify] [--pages 1] [--limit 20] \
        [--api-key KEY | env APIFY_TOKEN] [--actor-id ID] \
        [--out benchmarks.local.json] [--config path.json]

Exit codes: 0 success; 2 auth error (apify); 3 rate-limited (apify);
4 other API error; 5 blocked/empty (primary, no fallback available);
1 usage/IO error. Never writes fabricated data.
"""
import argparse
import json
import os
import sys
import time

DEFAULT_OUT = "benchmarks.local.json"


def default_config_path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "references", "scoring-config.json")


def load_config(path=None):
    with open(path or default_config_path(), encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------
# Pure mapping helpers (no third-party imports — unit-testable offline).
# --------------------------------------------------------------------------

def hours_to_days(hours):
    """Fiverr package `duration` is in hours; convert to whole days (min 1)."""
    if not hours or hours <= 0:
        return None
    return max(1, round(hours / 24))


def to_usd(price, currency, fx):
    """usd = price * fx.rates[currency]. Unknown currency -> None (never guess)."""
    if price is None:
        return None
    rate = fx["rates"].get(currency)
    if rate is None:
        return None
    return round(price * rate, 2)


def _packages_to_tiers(packages, fx, duration_in_hours=True):
    """Map an ordered package list (basic->premium) to flat tier fields.

    `packages` items must expose `price` and a delivery value under
    `delivery_days` (hours, per Fiverr) or `deliveryDays`.
    """
    order = ["basic", "standard", "premium"]
    out = {}
    for i, tier in enumerate(order):
        if i < len(packages):
            pkg = packages[i]
            raw_delivery = pkg.get("delivery_days", pkg.get("deliveryDays"))
            delivery = hours_to_days(raw_delivery) if duration_in_hours else (
                int(raw_delivery) if raw_delivery else None)
            out[f"{tier}_price"] = to_usd(pkg.get("price"), "USD", fx)
            out[f"{tier}_delivery_days"] = delivery
        else:
            out[f"{tier}_price"] = None
            out[f"{tier}_delivery_days"] = None
    return out


def accumulate(existing, new):
    """Merge new canonical rows into existing, de-duped by title|category|subcategory.

    Existing rows are kept first; genuinely new rows are appended. Used by
    --append so repeated scrapes grow a local file instead of overwriting it.
    """
    def key(r):
        return (r.get("title"), r.get("category"), r.get("subcategory"))
    seen = {key(r) for r in existing}
    merged = list(existing)
    for r in new:
        if key(r) in seen:
            continue
        seen.add(key(r))
        merged.append(r)
    return merged


def map_kyurish(search_item, detail, total_results, category_override, fx, today):
    """Build a canonical row (§7.1) from a KyuRish search item + gig detail."""
    detail = detail or {}
    seller = detail.get("seller", {}) or {}
    tiers = _packages_to_tiers(detail.get("packages", []), fx, duration_in_hours=True)
    row = {
        "scraped_at": today,
        "category": detail.get("category") or category_override,
        "subcategory": detail.get("sub_category"),
        "title": detail.get("title") or search_item.get("title"),
        "seller_level": seller.get("level") or search_item.get("seller_level") or None,
        "seller_country": seller.get("country") or None,
        "rating": detail.get("rating") if detail.get("rating") else search_item.get("rating"),
        "review_count": detail.get("reviews_count")
        if detail.get("reviews_count") is not None else search_item.get("reviews_count"),
        "basic_price": tiers["basic_price"],
        "standard_price": tiers["standard_price"],
        "premium_price": tiers["premium_price"],
        "basic_delivery_days": tiers["basic_delivery_days"],
        "standard_delivery_days": tiers["standard_delivery_days"],
        "premium_delivery_days": tiers["premium_delivery_days"],
        "tags": [t.lower() for t in (detail.get("tags") or []) if t],
        "gig_count_in_search": total_results if total_results else None,
        "currency": "USD",
        "original_currency": "USD",
    }
    return row


def map_apify(item, total_results, category_override, fx, today):
    """Best-effort mapping for the Apify fallback actor (UNVERIFIED).

    Apify actors do not return the search total, so gig_count_in_search stays
    whatever the item carries (normally null). Handles either a flat schema or
    a packages[] detail schema.
    """
    cur = item.get("currency") or "USD"
    packages = item.get("packages")
    if packages:
        tiers = _packages_to_tiers(packages, fx, duration_in_hours=False)
    else:
        tiers = {
            "basic_price": to_usd(item.get("basic_price"), cur, fx),
            "standard_price": to_usd(item.get("standard_price"), cur, fx),
            "premium_price": to_usd(item.get("premium_price"), cur, fx),
            "basic_delivery_days": item.get("basic_delivery_days"),
            "standard_delivery_days": item.get("standard_delivery_days"),
            "premium_delivery_days": item.get("premium_delivery_days"),
        }
    return {
        "scraped_at": item.get("scrapedAt") or item.get("scraped_at") or today,
        "category": category_override or item.get("category"),
        "subcategory": item.get("subCategoryId") or item.get("subcategory"),
        "title": item.get("title"),
        "seller_level": item.get("sellerLevel") or item.get("seller_level"),
        "seller_country": item.get("sellerCountry") or item.get("seller_country"),
        "rating": item.get("sellerRating") or item.get("rating"),
        "review_count": item.get("sellerReviewCount") or item.get("review_count"),
        **tiers,
        "tags": [t.lower() for t in (item.get("tags") or []) if t],
        "gig_count_in_search": item.get("gig_count_in_search") or total_results,
        "currency": "USD",
        "original_currency": cur,
    }


# --------------------------------------------------------------------------
# Engines (lazy imports so the mapping helpers stay dependency-free).
# --------------------------------------------------------------------------

def scrape_kyurish(query, category, pages, limit, fx, today):
    """Primary engine. Returns (rows, total_results). Raises on hard block."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
    try:
        from fiverr_perseus_scraper import FiverrScraper
    except ImportError as exc:
        print(f"error: primary engine needs curl-cffi + beautifulsoup4 "
              f"(pip install -r requirements.txt): {exc}", file=sys.stderr)
        sys.exit(1)

    sc = FiverrScraper()
    gigs, total_results = [], None
    for page in range(1, pages + 1):
        res = sc.search_gigs(query, category=category or "", page=page)
        if res.get("error"):
            print(f"warning: search page {page} blocked: {res['error']}", file=sys.stderr)
            continue
        total_results = res.get("total_results") or total_results
        gigs.extend(res.get("gigs", []))
        if not res.get("has_more"):
            break

    rows = []
    for item in gigs[:limit]:
        url = item.get("url")
        if not url:
            continue
        detail = sc.get_gig_details(url)
        if detail.get("error"):
            print(f"warning: detail blocked for {url}: {detail['error']}", file=sys.stderr)
            continue
        rows.append(map_kyurish(item, detail, total_results, category, fx, today))
    return rows, total_results


def scrape_apify(query, category, limit, api_key, base_url, actor_id, fx, today):
    """Fallback engine via the Apify actor. Returns rows."""
    import requests

    url = f"{base_url}/acts/{actor_id}/run-sync-get-dataset-items"
    try:
        resp = requests.post(
            url, params={"token": api_key},
            json={"searchQueries": [query], "maxItems": limit, "includeGigDetails": True},
            timeout=180,
        )
    except requests.RequestException as exc:
        print(f"error: request failed: {exc}", file=sys.stderr)
        sys.exit(4)

    if resp.status_code in (401, 403):
        print("error: authentication failed — check your Apify key.", file=sys.stderr)
        sys.exit(2)
    if resp.status_code == 429:
        print("error: rate-limited (HTTP 429). Wait and retry.", file=sys.stderr)
        sys.exit(3)
    if not resp.ok:
        print(f"error: Apify returned HTTP {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
        sys.exit(4)
    try:
        items = resp.json()
    except ValueError:
        print("error: Apify returned non-JSON.", file=sys.stderr)
        sys.exit(4)

    print("note: Apify fallback mapping is unverified and cannot supply "
          "gig_count_in_search (no actor returns the search total).", file=sys.stderr)
    return [map_apify(it, None, category, fx, today) for it in items if it.get("title")]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Opt-in live Fiverr scrape into the canonical schema.")
    ap.add_argument("--query", required=True)
    ap.add_argument("--category")
    ap.add_argument("--engine", choices=["auto", "kyurish", "apify"], default="auto")
    ap.add_argument("--pages", type=int, default=1, help="Search pages to scan (primary engine).")
    ap.add_argument("--limit", type=int, default=20, help="Max gig-detail fetches.")
    ap.add_argument("--api-key", help="Apify token (or APIFY_TOKEN). Fallback only.")
    ap.add_argument("--actor-id", help="Override Apify actor id.")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--append", action="store_true",
                    help="Accumulate into --out (de-duped) instead of overwriting it.")
    ap.add_argument("--contribute", action="store_true",
                    help="After scraping, push anonymized rows to the HF dataset (opt-in).")
    ap.add_argument("--contributor", default="anonymous", help="Credited name for --contribute.")
    ap.add_argument("--token", help="HF write token for --contribute (or HF_TOKEN, or cached login).")
    ap.add_argument("--config")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    fx = cfg["fx"]
    today = time.strftime("%Y-%m-%d")
    scraper_cfg = cfg.get("scraper", {})
    api_key = args.api_key or os.environ.get("APIFY_TOKEN")
    actor_id = args.actor_id or scraper_cfg.get("actor_id")

    rows = []
    if args.engine in ("auto", "kyurish"):
        rows, total = scrape_kyurish(args.query, args.category, args.pages, args.limit, fx, today)
        if not rows and args.engine == "auto" and api_key and actor_id and not actor_id.startswith("<"):
            print("note: primary engine returned nothing — trying Apify fallback.", file=sys.stderr)
            rows = scrape_apify(args.query, args.category, args.limit, api_key,
                                scraper_cfg["base_url"], actor_id, fx, today)
        elif not rows:
            print("error: primary engine returned no rows (blocked or empty) and no "
                  "Apify fallback configured. Try a residential IP/PROXY_URL, or use a "
                  "manual count.", file=sys.stderr)
            return 5
    else:  # explicit apify
        if not api_key:
            print("error: --engine apify needs --api-key or APIFY_TOKEN.", file=sys.stderr)
            return 1
        if not actor_id or actor_id.startswith("<"):
            print("error: no actor_id configured. Set scraper.actor_id or pass --actor-id.",
                  file=sys.stderr)
            return 1
        rows = scrape_apify(args.query, args.category, args.limit, api_key,
                            scraper_cfg["base_url"], actor_id, fx, today)

    rows = [r for r in rows if r.get("title")]
    fresh = len(rows)

    # --append: accumulate into the existing file (de-duped) instead of overwriting.
    if args.append and os.path.exists(args.out):
        try:
            with open(args.out, encoding="utf-8") as fh:
                existing = json.load(fh)
        except (json.JSONDecodeError, OSError):
            existing = []
        before = len(existing)
        rows = accumulate(existing, rows)
        print(f"append: {before} existing + {fresh} scraped -> {len(rows)} rows "
              f"(+{len(rows) - before} new).", file=sys.stderr)

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2, ensure_ascii=False)
    counts = {r["gig_count_in_search"] for r in rows if r.get("gig_count_in_search")}
    print(f"Wrote {len(rows)} canonical rows to {args.out} "
          f"(gig_count_in_search: {sorted(counts) or 'null'}).")

    # --contribute (flag) or scraper.auto_contribute (config): opt-in, token-gated,
    # and always announced — never a silent background upload.
    do_contribute = args.contribute or scraper_cfg.get("auto_contribute", False)
    if do_contribute:
        import contribute
        token = args.token or os.environ.get("HF_TOKEN")
        if not token:
            print("note: --contribute/auto_contribute is on but no HF token was found "
                  "(--token / HF_TOKEN / cached login) — skipping upload, nothing shared.",
                  file=sys.stderr)
        else:
            cleaned = contribute.clean_and_dedup(rows, set())
            contribute.assert_no_pii(cleaned)
            if not cleaned:
                print("note: nothing to contribute after cleaning.", file=sys.stderr)
            else:
                print(f"Contributing {len(cleaned)} anonymized rows to the community "
                      f"dataset as '{args.contributor}' ...", file=sys.stderr)
                pr = contribute.open_hf_pr(cleaned, cfg["dataset_repo"], token, args.contributor)
                contribute.append_contributor(args.contributor)
                print(f"Opened contribution PR: {pr}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
