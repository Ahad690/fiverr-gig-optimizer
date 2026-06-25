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


if __name__ == "__main__":
    unittest.main()
