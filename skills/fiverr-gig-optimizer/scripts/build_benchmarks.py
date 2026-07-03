#!/usr/bin/env python3
"""build_benchmarks.py — derive working files from canonical rows. §7.4.

Reads benchmarks.local.json (or a user CSV in the canonical column layout) and
writes TWO outputs:
  - pricing-pools.local.json : per category -> per tier -> [prices] (for analyze_pricing.py)
  - dataset-index.local.json : keyword/tag -> {gig_count, row_ids}  (for query_dataset.py)

This script does no scoring and invents no data.

CLI:
    build_benchmarks.py --input benchmarks.local.json \
        [--pools pricing-pools.local.json] [--index dataset-index.local.json]
    build_benchmarks.py --csv rows.csv ...
"""
import argparse
import csv
import json
import os
import sys

TIER_PRICE = {"basic": "basic_price", "standard": "standard_price", "premium": "premium_price"}


def load_rows(input_path=None, csv_path=None):
    if csv_path:
        with open(csv_path, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        for r in rows:
            for k in ("basic_price", "standard_price", "premium_price",
                      "gig_count_in_search", "review_count"):
                if k in r and r[k] not in (None, ""):
                    try:
                        r[k] = float(r[k])
                        if r[k].is_integer():
                            r[k] = int(r[k])
                    except (ValueError, AttributeError):
                        r[k] = None
                else:
                    r[k] = None
            if isinstance(r.get("tags"), str):
                r["tags"] = [t.strip().lower() for t in r["tags"].replace(";", ",").split(",") if t.strip()]
        return rows
    with open(input_path, encoding="utf-8") as fh:
        return json.load(fh)


def category_key(row):
    cat = row.get("category") or "Uncategorized"
    sub = row.get("subcategory")
    return f"{cat} > {sub}" if sub else cat


def build_pools(rows):
    pools = {}
    for row in rows:
        key = category_key(row)
        bucket = pools.setdefault(key, {"basic": [], "standard": [], "premium": []})
        for tier, field in TIER_PRICE.items():
            v = row.get(field)
            if isinstance(v, (int, float)):
                bucket[tier].append(v)
    return pools


def build_index(rows):
    """keyword/tag -> {gig_count (mode-ish), row_ids}."""
    index = {}
    for i, row in enumerate(rows):
        terms = set(t.lower() for t in (row.get("tags") or []))
        sub = row.get("subcategory")
        if sub:
            terms.add(sub.lower())
        gc = row.get("gig_count_in_search")
        for term in terms:
            entry = index.setdefault(term, {"gig_counts": [], "row_ids": []})
            entry["row_ids"].append(i)
            if isinstance(gc, (int, float)):
                entry["gig_counts"].append(gc)
    # Collapse gig_counts to a single representative value (most common).
    out = {}
    for term, entry in index.items():
        counts = entry["gig_counts"]
        gig_count = max(set(counts), key=counts.count) if counts else None
        out[term] = {"gig_count": gig_count, "row_ids": entry["row_ids"]}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build pricing pools + dataset index from canonical rows.")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--input", help="Path to benchmarks.local.json (canonical rows).")
    src.add_argument("--csv", help="Path to a CSV in the canonical column layout.")
    ap.add_argument("--pools", default="pricing-pools.local.json")
    ap.add_argument("--index", default="dataset-index.local.json")
    args = ap.parse_args(argv)

    rows = load_rows(args.input, args.csv)
    pools = build_pools(rows)
    index = build_index(rows)

    # Pools/index are DERIVED artifacts (rebuildable from --input any time), so
    # replacing them is fine — but write atomically so a crash can't corrupt them.
    import local_data
    local_data.write_json_atomic(args.pools, pools)
    local_data.write_json_atomic(args.index, index)

    print(f"Wrote {args.pools} ({len(pools)} categories) and "
          f"{args.index} ({len(index)} terms) from {len(rows)} rows.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
