#!/usr/bin/env python3
"""merge_kaggle.py — build benchmarks.sample.json from raw Kaggle CSVs.

Merges one or more public Kaggle Fiverr gig CSVs into the canonical schema
(PRD §7.1) and writes references/benchmarks.sample.json. Column names differ
across datasets, so the mapping is configurable per input via --map.

This script does NOT invent data: rows missing a required field keep `null`
for that field; rows missing BOTH a title and a category are skipped.

Usage:
    merge_kaggle.py --input gigs1.csv --map maps/gigs1.json \
                    --input gigs2.csv --map maps/gigs2.json \
                    --out ../../references/benchmarks.sample.json

A --map file maps canonical field -> source column name, plus:
    {"_defaults": {"category": "...", "scraped_at": "2024-01-01",
                   "currency": "USD"},
     "title": "gig_title", "basic_price": "price_basic", ...}

Uses the stdlib csv module (no pandas required).
"""
import argparse
import csv
import json
import sys

CANONICAL_FIELDS = [
    "scraped_at", "category", "subcategory", "title", "seller_level",
    "seller_country", "rating", "review_count",
    "basic_price", "standard_price", "premium_price",
    "basic_delivery_days", "standard_delivery_days", "premium_delivery_days",
    "tags", "gig_count_in_search", "currency", "original_currency",
]
NUMERIC_FIELDS = {
    "rating", "review_count", "basic_price", "standard_price", "premium_price",
    "basic_delivery_days", "standard_delivery_days", "premium_delivery_days",
    "gig_count_in_search",
}


def to_number(value):
    if value is None:
        return None
    s = str(value).strip().replace("$", "").replace(",", "")
    if s == "" or s.lower() in ("nan", "none", "null"):
        return None
    try:
        f = float(s)
        return int(f) if f.is_integer() else f
    except ValueError:
        return None


def to_tags(value):
    if not value:
        return []
    if isinstance(value, list):
        items = value
    else:
        items = str(value).replace(";", ",").split(",")
    return [t.strip().lower() for t in items if t and t.strip()]


def map_row(raw, mapping):
    defaults = mapping.get("_defaults", {})
    out = {}
    for field in CANONICAL_FIELDS:
        if field in defaults and (field not in mapping):
            value = defaults[field]
        else:
            col = mapping.get(field)
            value = raw.get(col) if col else defaults.get(field)
        if field == "tags":
            out[field] = to_tags(value)
        elif field in NUMERIC_FIELDS:
            out[field] = to_number(value)
        else:
            out[field] = (str(value).strip() if value not in (None, "") else None)
    # original_currency falls back to currency when absent.
    if out.get("original_currency") is None:
        out["original_currency"] = out.get("currency")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Merge Kaggle Fiverr CSVs into the canonical schema.")
    ap.add_argument("--input", action="append", default=[], required=True,
                    help="Raw CSV path (repeatable).")
    ap.add_argument("--map", action="append", default=[], required=True,
                    help="Field-mapping JSON for the matching --input (repeatable).")
    ap.add_argument("--out", required=True, help="Output benchmarks.sample.json path.")
    args = ap.parse_args(argv)

    if len(args.input) != len(args.map):
        print("error: each --input needs a matching --map", file=sys.stderr)
        return 1

    merged = []
    for csv_path, map_path in zip(args.input, args.map):
        with open(map_path, encoding="utf-8") as fh:
            mapping = json.load(fh)
        with open(csv_path, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            for raw in reader:
                row = map_row(raw, mapping)
                if not row.get("title") and not row.get("category"):
                    continue
                merged.append(row)

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, indent=2, ensure_ascii=False)
    print(f"Wrote {len(merged)} rows to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
