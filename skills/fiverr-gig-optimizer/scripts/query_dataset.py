#!/usr/bin/env python3
"""query_dataset.py — Path A dataset lookup. §8A.

Derives a gig_count and top_gigs for a keyword from the bundled sample dataset
(or a local scraped dataset) so the free path can feed score_keyword.py.

Matching is deterministic. When the match is weak (LOW confidence or no rows),
it returns gig_count: null with flag "no_match" so the skill asks the user for
a manual count instead of fabricating one.

CLI:
    query_dataset.py --keyword "ai chatbot n8n" \
        [--dataset references/benchmarks.sample.json] \
        [--index dataset-index.local.json] [--top-n 10] [--config path.json]
"""
import argparse
import json
import os
import re
import statistics
import sys

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def default_config_path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "references", "scoring-config.json")


def default_dataset_path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "references", "benchmarks.sample.json")


def load_config(path=None):
    with open(path or default_config_path(), encoding="utf-8") as fh:
        return json.load(fh)


def tokens(text):
    return set(_TOKEN_RE.findall((text or "").lower()))


def jaccard(a, b):
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def overlap_ratio(keyword_tokens, other_tokens):
    """Fraction of keyword tokens present in other_tokens."""
    if not keyword_tokens:
        return 0.0
    return len(keyword_tokens & other_tokens) / len(keyword_tokens)


def row_match_score(keyword_tokens, keyword_lower, row):
    tag_tokens = set()
    for t in row.get("tags") or []:
        tag_tokens |= tokens(t)
    subcategory = (row.get("subcategory") or "").lower()
    title_tokens = tokens(row.get("title"))

    by_tags = jaccard(keyword_tokens, tag_tokens)
    by_subcat = 1.0 if keyword_lower and keyword_lower in subcategory else 0.0
    by_title = overlap_ratio(keyword_tokens, title_tokens)
    return max(by_tags, by_subcat, by_title)


def query(keyword, dataset, cfg, top_n=None):
    lk = cfg["lookup"]
    threshold = lk["match_threshold"]
    min_rows = lk["min_rows"]
    top_n = top_n or lk["top_n"]

    keyword_lower = keyword.lower().strip()
    keyword_tokens = tokens(keyword)

    scored = []
    for row in dataset:
        s = row_match_score(keyword_tokens, keyword_lower, row)
        if s >= threshold:
            scored.append((s, row))

    matched_rows = len(scored)
    no_match = {
        "keyword": keyword,
        "gig_count": None,
        "match_confidence": "LOW",
        "matched_rows": matched_rows,
        "top_gigs": [],
        "source": "sample_dataset",
        "flags": ["no_match"],
    }

    if matched_rows == 0:
        return no_match

    best_score = max(s for s, _ in scored)

    # Confidence: the row-count floor wins (v1.1 ambiguity resolved). Fewer
    # than min_rows -> LOW regardless of how strong the best single match is.
    if matched_rows < min_rows:
        confidence = "LOW"
    elif best_score >= 0.8:
        confidence = "HIGH"
    elif best_score >= threshold:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    if confidence == "LOW":
        no_match["matched_rows"] = matched_rows
        return no_match

    # gig_count: mode of matched rows' gig_count_in_search; median if no
    # single mode. Ignore rows missing the field.
    counts = [
        r.get("gig_count_in_search")
        for _, r in scored
        if isinstance(r.get("gig_count_in_search"), (int, float))
    ]
    if not counts:
        no_match["matched_rows"] = matched_rows
        return no_match

    try:
        gig_count = statistics.mode(counts)
    except statistics.StatisticsError:
        gig_count = round(statistics.median(counts))

    top_gigs = [r for _, r in sorted(scored, key=lambda sr: (sr[1].get("review_count") or 0),
                                     reverse=True)][:top_n]

    return {
        "keyword": keyword,
        "gig_count": int(gig_count),
        "match_confidence": confidence,
        "matched_rows": matched_rows,
        "top_gigs": top_gigs,
        "source": "sample_dataset",
        "flags": [],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Deterministic Path-A dataset lookup.")
    ap.add_argument("--keyword", required=True)
    ap.add_argument("--dataset", help="Path to a canonical-schema dataset JSON list.")
    ap.add_argument("--index", help="Optional dataset-index.local.json (reserved).")
    ap.add_argument("--top-n", type=int, default=None)
    ap.add_argument("--config", help="Path to scoring-config.json.")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    dataset_path = args.dataset or default_dataset_path()
    with open(dataset_path, encoding="utf-8") as fh:
        dataset = json.load(fh)

    result = query(args.keyword, dataset, cfg, top_n=args.top_n)
    print(json.dumps(result, indent=2))
    import reminders
    reminders.contribution_reminder(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
