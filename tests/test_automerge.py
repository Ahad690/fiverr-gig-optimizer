#!/usr/bin/env python3
"""Offline tests for automerge_prs.py decision logic — no network."""
import os
import sys
import unittest

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "skills",
                       "fiverr-gig-optimizer", "scripts")
sys.path.insert(0, os.path.abspath(SCRIPTS))

import automerge_prs as am  # noqa: E402

CONTRIB = ["contributions/alice.json"]


class TestAdditiveOnly(unittest.TestCase):
    def test_clean(self):
        ok, _ = am.additive_only(CONTRIB, [], [])
        self.assertTrue(ok)

    def test_removed_blocks(self):
        self.assertFalse(am.additive_only(CONTRIB, ["x.json"], [])[0])

    def test_modified_blocks(self):
        self.assertFalse(am.additive_only(CONTRIB, [], ["README.md"])[0])

    def test_non_contribution_file_blocks(self):
        self.assertFalse(am.additive_only(["README.md"], [], [])[0])
        self.assertFalse(am.additive_only(["contributions/x.txt"], [], [])[0])

    def test_empty_blocks(self):
        self.assertFalse(am.additive_only([], [], [])[0])


class TestPrVerdict(unittest.TestCase):
    def test_merge(self):
        v = am.pr_verdict(CONTRIB, [], [], rows=5, invalid_count=0, valid_new=5,
                          file_errors=0, max_rows=2000, max_corrupt_ratio=0.0)
        self.assertEqual(v["action"], "merge")

    def test_unsafe_shape_holds(self):
        v = am.pr_verdict(CONTRIB, ["gone.json"], [], rows=5, invalid_count=0,
                          valid_new=5, file_errors=0, max_rows=2000, max_corrupt_ratio=0.0)
        self.assertEqual(v["action"], "hold")
        self.assertEqual(v["status"], "unsafe_shape")

    def test_too_large_holds(self):
        v = am.pr_verdict(CONTRIB, [], [], rows=5000, invalid_count=0, valid_new=5000,
                          file_errors=0, max_rows=2000, max_corrupt_ratio=0.0)
        self.assertEqual(v["status"], "too_large")

    def test_any_invalid_holds_by_default(self):
        # default max_corrupt_ratio=0.0 -> a single invalid row holds the PR
        v = am.pr_verdict(CONTRIB, [], [], rows=5, invalid_count=1, valid_new=4,
                          file_errors=0, max_rows=2000, max_corrupt_ratio=0.0)
        self.assertEqual(v["action"], "hold")

    def test_empty_holds(self):
        v = am.pr_verdict(CONTRIB, [], [], rows=0, invalid_count=0, valid_new=0,
                          file_errors=0, max_rows=2000, max_corrupt_ratio=0.0)
        self.assertEqual(v["action"], "hold")

    def test_abuse_reasons_hold_a_clean_pr(self):
        v = am.pr_verdict(CONTRIB, [], [], rows=5, invalid_count=0, valid_new=5,
                          file_errors=0, max_rows=2000, max_corrupt_ratio=0.0,
                          abuse_reasons=["category 'X' median is 50x reference"])
        self.assertEqual(v["action"], "hold")
        self.assertEqual(v["status"], "suspicious")


ACFG = {"max_price": 50000, "max_review_count": 1_000_000, "max_gig_count": 5_000_000,
        "min_unique_ratio": 0.5, "ordering_violation_max_ratio": 0.3,
        "outlier_factor": 10, "outlier_min_rows": 3}


def _row(cat="Programming & Tech", b=30, s=90, p=250, **kw):
    r = {"category": cat, "subcategory": "X", "title": "i will do x",
         "basic_price": b, "standard_price": s, "premium_price": p,
         "review_count": 100, "gig_count_in_search": 1000, "tags": ["x"]}
    r.update(kw)
    return r


class TestAbuseScan(unittest.TestCase):
    def test_clean_passes(self):
        ref = [_row(b=25), _row(b=35), _row(b=30)]
        rows = [_row(b=28), _row(b=32), _row(b=30)]
        self.assertEqual(am.abuse_scan(rows, ref, ACFG), [])

    def test_price_ceiling_flagged(self):
        rows = [_row(p=999999)]
        self.assertTrue(any("ceiling" in r for r in am.abuse_scan(rows, [], ACFG)))

    def test_ordering_violation_flagged(self):
        # all rows have basic > premium
        rows = [_row(b=500, s=200, p=50) for _ in range(4)]
        self.assertTrue(any("violate" in r for r in am.abuse_scan(rows, [], ACFG)))

    def test_duplicate_flood_flagged(self):
        rows = [_row(b=30) for _ in range(6)]  # all identical
        self.assertTrue(any("unique" in r for r in am.abuse_scan(rows, [], ACFG)))

    def test_price_outlier_vs_reference_flagged(self):
        ref = [_row(b=30), _row(b=30), _row(b=30)]          # reference median ~30
        rows = [_row(b=3000), _row(b=3000), _row(b=3000)]   # 100x outlier
        self.assertTrue(any("outlier" in r for r in am.abuse_scan(rows, ref, ACFG)))


if __name__ == "__main__":
    unittest.main()
