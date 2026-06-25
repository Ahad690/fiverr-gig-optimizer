#!/usr/bin/env python3
"""score_keyword.py — deterministic competition/demand/opportunity scoring.

Implements PRD v1.1 sections 8.1-8.5 and the output contract 8.7.
All constants come from references/scoring-config.json. This script NEVER
invents a market number: gig_count must be supplied (from query_dataset.py,
a manual paste, or a live scrape).

CLI:
    score_keyword.py --keyword "ai chatbot n8n" --gig-count 24 \
        [--top-gigs path.json] [--config path.json]

Output: a single JSON object on stdout (see §8.7).
"""
import argparse
import json
import math
import os
import statistics
import sys


def default_config_path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "references", "scoring-config.json")


def load_config(path=None):
    with open(path or default_config_path(), encoding="utf-8") as fh:
        return json.load(fh)


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def competition_score(gig_count, anchors):
    """Piecewise-linear interpolation over log10(gig_count). §8.2.

    Returns None for gig_count == 0 (the UNTESTED special case), otherwise an
    integer in [0, 100] where higher means LESS competition (better).
    """
    if gig_count == 0:
        return None
    x = math.log10(max(gig_count, 1))
    pts = [(math.log10(c), s) for c, s in anchors]
    if x <= pts[0][0]:
        return round(pts[0][1])
    if x >= pts[-1][0]:
        return round(pts[-1][1])
    for (x0, s0), (x1, s1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            t = (x - x0) / (x1 - x0)
            return round(s0 + t * (s1 - s0))
    return round(pts[-1][1])  # unreachable, defensive


def tier_for(gig_count, tiers):
    if gig_count == 0:
        return "UNTESTED"
    if gig_count < tiers["low_max"]:
        return "LOW"
    if gig_count < tiers["medium_max"]:
        return "MEDIUM"
    return "HIGH"


def demand_score(top_gigs, ceiling, top_n):
    """Median review_count of the top N competitor gigs, normalized. §8.3.

    Returns None when no usable competitor data is available (never guessed).
    """
    if not top_gigs:
        return None
    reviews = [
        g["review_count"]
        for g in top_gigs[:top_n]
        if isinstance(g.get("review_count"), (int, float))
    ]
    if not reviews:
        return None
    median_reviews = statistics.median(reviews)
    return round(clamp((median_reviews / ceiling) * 100, 0, 100))


def score(keyword, gig_count, top_gigs, cfg):
    anchors = cfg["competition"]["anchors"]
    tiers = cfg["tiers"]
    dem = cfg["demand"]
    opp = cfg["opportunity"]

    comp = competition_score(gig_count, anchors)
    tier = tier_for(gig_count, tiers)
    flags = []

    if tier == "UNTESTED":
        result = {
            "keyword": keyword,
            "gig_count": gig_count,
            "competition_score": None,
            "tier": "UNTESTED",
            "demand_score": None,
            "opportunity_score": None,
            "flags": ["no_results", "untested_niche"],
        }
        return result

    dem_score = demand_score(top_gigs, dem["ceiling"], dem["top_n"])

    if dem_score is not None:
        opportunity = round(
            opp["w_competition"] * comp + opp["w_demand"] * dem_score
        )
    else:
        opportunity = comp
        flags.append("demand_unavailable")

    # Combo-niche bonus (default OFF; §8.5). Applies only to multi-word combos
    # below the LOW threshold, and never to an untested niche.
    combo_bonus = opp.get("combo_bonus", 0)
    is_combo = len(keyword.split()) >= 2
    if combo_bonus and is_combo and gig_count < tiers["low_max"]:
        opportunity = min(100, opportunity + combo_bonus)
        flags.append("combo_bonus_applied")

    return {
        "keyword": keyword,
        "gig_count": gig_count,
        "competition_score": comp,
        "tier": tier,
        "demand_score": dem_score,
        "opportunity_score": opportunity,
        "flags": flags,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Deterministic Fiverr keyword scoring.")
    ap.add_argument("--keyword", required=True)
    ap.add_argument("--gig-count", type=int, required=True,
                    help="Total gigs for the keyword. Use 0 for 'no results'.")
    ap.add_argument("--top-gigs", help="Path to JSON list of canonical gig rows.")
    ap.add_argument("--config", help="Path to scoring-config.json.")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)

    top_gigs = []
    if args.top_gigs:
        with open(args.top_gigs, encoding="utf-8") as fh:
            top_gigs = json.load(fh)

    result = score(args.keyword, args.gig_count, top_gigs, cfg)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
