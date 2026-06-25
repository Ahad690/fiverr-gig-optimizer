#!/usr/bin/env python3
"""scrape.py — opt-in live scrape via an Apify-compatible actor. FR5.

Runs ONLY with the user's own API key. The skill never ships a key and never
scrapes by default. Maps actor results into the canonical schema (§7.1),
converts non-USD prices to USD via the static fx table, and writes
benchmarks.local.json (the ONLY writer of that file — §7.4).

Currency: usd = price * fx.rates[original_currency]  (rates = USD per unit).

CLI:
    scrape.py --query "ai chatbot" --category "Programming & Tech" \
        [--api-key KEY | env APIFY_TOKEN] [--actor-id ID] \
        [--limit 50] [--out benchmarks.local.json] [--config path.json]

Exit codes: 0 success; 2 auth error; 3 rate-limited; 4 other API error;
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


def to_usd(price, currency, fx):
    if price is None:
        return None
    rate = fx["rates"].get(currency)
    if rate is None:
        return None  # unknown currency: do not guess
    return round(price * rate, 2)


def map_item(item, category, fx):
    """Map one actor result dict into a canonical row. Unknown fields -> null."""
    cur = item.get("currency") or "USD"
    row = {
        "scraped_at": item.get("scraped_at") or time.strftime("%Y-%m-%d"),
        "category": category or item.get("category"),
        "subcategory": item.get("subcategory"),
        "title": item.get("title"),
        "seller_level": item.get("seller_level"),
        "rating": item.get("rating"),
        "review_count": item.get("review_count"),
        "basic_price": to_usd(item.get("basic_price"), cur, fx),
        "standard_price": to_usd(item.get("standard_price"), cur, fx),
        "premium_price": to_usd(item.get("premium_price"), cur, fx),
        "basic_delivery_days": item.get("basic_delivery_days"),
        "standard_delivery_days": item.get("standard_delivery_days"),
        "premium_delivery_days": item.get("premium_delivery_days"),
        "tags": [t.lower() for t in (item.get("tags") or [])],
        "gig_count_in_search": item.get("gig_count_in_search"),
        "currency": "USD",
        "original_currency": cur,
    }
    return row


def run_actor(api_key, base_url, actor_id, query, limit):
    """Call the actor's run-sync-get-dataset-items endpoint. Returns a list."""
    import requests  # imported here so the scoring core needs no third-party deps

    url = f"{base_url}/acts/{actor_id}/run-sync-get-dataset-items"
    try:
        resp = requests.post(
            url,
            params={"token": api_key},
            json={"query": query, "maxItems": limit},
            timeout=120,
        )
    except requests.RequestException as exc:
        print(f"error: request failed: {exc}", file=sys.stderr)
        sys.exit(4)

    if resp.status_code in (401, 403):
        print("error: authentication failed — check your scraper API key "
              "(--api-key or APIFY_TOKEN).", file=sys.stderr)
        sys.exit(2)
    if resp.status_code == 429:
        print("error: rate-limited by the scraper API (HTTP 429). Wait and "
              "retry, or lower --limit.", file=sys.stderr)
        sys.exit(3)
    if not resp.ok:
        print(f"error: scraper API returned HTTP {resp.status_code}: "
              f"{resp.text[:200]}", file=sys.stderr)
        sys.exit(4)

    try:
        return resp.json()
    except ValueError:
        print("error: scraper API returned non-JSON response.", file=sys.stderr)
        sys.exit(4)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Opt-in live Fiverr scrape (user key required).")
    ap.add_argument("--query", required=True, help="Search query / keyword to scrape.")
    ap.add_argument("--category", help="Category to stamp on rows.")
    ap.add_argument("--api-key", help="Scraper API token (or set APIFY_TOKEN).")
    ap.add_argument("--actor-id", help="Override actor id (else from config).")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--config", help="Path to scoring-config.json.")
    args = ap.parse_args(argv)

    api_key = args.api_key or os.environ.get("APIFY_TOKEN")
    if not api_key:
        print("error: no API key. Pass --api-key or set APIFY_TOKEN. This skill "
              "never scrapes without your own key.", file=sys.stderr)
        return 1

    cfg = load_config(args.config)
    scraper = cfg["scraper"]
    actor_id = args.actor_id or scraper.get("actor_id")
    if not actor_id or actor_id.startswith("<"):
        print("error: no actor_id configured. Set scraper.actor_id in "
              "scoring-config.json or pass --actor-id.", file=sys.stderr)
        return 1

    items = run_actor(api_key, scraper["base_url"], actor_id, args.query, args.limit)
    rows = [map_item(it, args.category, cfg["fx"]) for it in items]
    rows = [r for r in rows if r.get("title")]  # drop empty results, never pad

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2, ensure_ascii=False)
    print(f"Wrote {len(rows)} canonical rows to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
