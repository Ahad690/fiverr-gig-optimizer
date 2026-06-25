#!/usr/bin/env python3
"""analyze_pricing.py — deterministic per-tier pricing benchmarks. §8.6.

Computes p10/p25/median/p75/p90 WITHIN each tier's own price distribution and
recommends a Basic/Standard/Premium triple. Never invents a benchmark: when a
tier has no samples it recommends nothing numeric for that tier.

Confidence rule (PRD v1.1 §8.6, with the v1.1 ambiguity resolved):
  - n == 0                 -> confidence "low", no numeric recommendation.
  - 1 <= n < min_samples   -> compute the percentile but flag confidence "low".
  - n >= min_samples       -> confidence "ok".

CLI:
    analyze_pricing.py --prices path.json [--category "Cat > Sub"] \
        --experience New [--config path.json]

--prices points to either:
  * a per-tier object: {"basic":[..], "standard":[..], "premium":[..]}, or
  * a pricing-pools file keyed by category (use --category to select one).
"""
import argparse
import json
import os
import statistics
import sys

TIERS = ("basic", "standard", "premium")


def default_config_path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "references", "scoring-config.json")


def load_config(path=None):
    with open(path or default_config_path(), encoding="utf-8") as fh:
        return json.load(fh)


def percentile(values, p):
    """Percentile via statistics.quantiles (inclusive), p in [0, 100]. §8.6."""
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    if p <= 0:
        return s[0]
    if p >= 100:
        return s[-1]
    q = statistics.quantiles(s, n=100, method="inclusive")  # 99 cut points
    return q[p - 1]


def spread(values):
    """The full p10/p25/median/p75/p90 spread for one tier."""
    return {
        "p10": percentile(values, 10),
        "p25": percentile(values, 25),
        "median": percentile(values, 50),
        "p75": percentile(values, 75),
        "p90": percentile(values, 90),
    }


def analyze(prices_by_tier, experience, cfg):
    pcfg = cfg["pricing"]
    min_samples = pcfg["min_samples"]
    strat = pcfg["new_seller"] if experience == "New" else pcfg["default"]
    rec_p = {
        "basic": strat["basic_p"],
        "standard": strat["standard_p"],
        "premium": strat["premium_p"],
    }

    tiers_out = {}
    recommended = {}
    flags = []

    for tier in TIERS:
        values = [
            v for v in prices_by_tier.get(tier, [])
            if isinstance(v, (int, float))
        ]
        n = len(values)

        if n == 0:
            tiers_out[tier] = {
                "n": 0,
                "confidence": "low",
                "reason": "insufficient samples (n=0)",
            }
            recommended[tier] = None
            flags.append(f"{tier}_no_samples")
            continue

        confidence = "ok" if n >= min_samples else "low"
        tier_block = {"n": n, "confidence": confidence}
        tier_block.update(spread(values))
        if confidence == "low":
            tier_block["reason"] = f"insufficient samples (n={n})"
            flags.append(f"{tier}_low_confidence")
        tiers_out[tier] = tier_block

        recommended[tier] = round(percentile(values, rec_p[tier]))

    return {
        "experience": experience,
        "strategy": "new_seller" if experience == "New" else "default",
        "tiers": tiers_out,
        "recommended": recommended,
        "flags": flags,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Deterministic Fiverr pricing benchmarks.")
    ap.add_argument("--prices", required=True,
                    help="Path to a per-tier price object or a pricing-pools file.")
    ap.add_argument("--category", help="Category key to select from a pricing-pools file.")
    ap.add_argument("--experience", default="L1",
                    help="Seller experience: New / L1 / L2 / Top Rated.")
    ap.add_argument("--config", help="Path to scoring-config.json.")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    with open(args.prices, encoding="utf-8") as fh:
        data = json.load(fh)

    if args.category:
        if args.category not in data:
            print(json.dumps({"error": f"category not found: {args.category}"}))
            return 1
        prices_by_tier = data[args.category]
    else:
        prices_by_tier = data

    result = analyze(prices_by_tier, args.experience, cfg)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
