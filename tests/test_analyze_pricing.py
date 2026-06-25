#!/usr/bin/env python3
"""Tests for analyze_pricing.py — per-tier percentiles + confidence (PRD §15)."""
import os
import sys
import unittest

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "skills",
                       "fiverr-gig-optimizer", "scripts")
sys.path.insert(0, os.path.abspath(SCRIPTS))

import analyze_pricing as ap  # noqa: E402

CFG = ap.load_config()


class TestPercentile(unittest.TestCase):
    def test_single_value(self):
        self.assertEqual(ap.percentile([42], 25), 42)

    def test_median(self):
        self.assertEqual(ap.percentile([10, 20, 30], 50), 20)

    def test_bounds(self):
        self.assertEqual(ap.percentile([10, 20, 30], 0), 10)
        self.assertEqual(ap.percentile([10, 20, 30], 100), 30)


class TestAnalyze(unittest.TestCase):
    def test_full_tier_returns_spread_and_recommendation(self):
        prices = {
            "basic": [20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75],  # n=12
            "standard": [50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160],
            "premium": [120, 140, 160, 180, 200, 220, 240, 260, 280, 300, 320, 340],
        }
        r = ap.analyze(prices, "L1", CFG)
        self.assertEqual(r["tiers"]["basic"]["confidence"], "ok")
        for key in ("p10", "p25", "median", "p75", "p90"):
            self.assertIn(key, r["tiers"]["basic"])
        self.assertIsInstance(r["recommended"]["basic"], int)
        self.assertIsInstance(r["recommended"]["standard"], int)
        self.assertIsInstance(r["recommended"]["premium"], int)

    def test_low_sample_tier_is_low_confidence(self):
        prices = {"basic": [20, 30, 40, 50, 60], "standard": [], "premium": []}  # n=5
        r = ap.analyze(prices, "L1", CFG)
        self.assertEqual(r["tiers"]["basic"]["confidence"], "low")
        # v1.1 resolution: 1 <= n < min_samples still yields a number, flagged low.
        self.assertIsInstance(r["recommended"]["basic"], int)

    def test_empty_tier_recommends_nothing(self):
        prices = {"basic": [], "standard": [], "premium": []}
        r = ap.analyze(prices, "L1", CFG)
        self.assertIsNone(r["recommended"]["basic"])
        self.assertEqual(r["tiers"]["basic"]["confidence"], "low")

    def test_new_seller_uses_lower_percentiles(self):
        prices = {"basic": list(range(10, 130, 10)), "standard": [], "premium": []}  # n=12
        default = ap.analyze(prices, "L1", CFG)["recommended"]["basic"]
        newbie = ap.analyze(prices, "New", CFG)["recommended"]["basic"]
        self.assertLess(newbie, default)


if __name__ == "__main__":
    unittest.main()
