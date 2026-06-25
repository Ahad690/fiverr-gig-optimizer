#!/usr/bin/env python3
"""Tests for query_dataset.py — Path A lookup (PRD §15 Phase 1)."""
import json
import os
import sys
import unittest

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "skills",
                       "fiverr-gig-optimizer", "scripts")
sys.path.insert(0, os.path.abspath(SCRIPTS))

import query_dataset as qd  # noqa: E402

CFG = qd.load_config()
DATASET_PATH = os.path.join(SCRIPTS, "..", "references", "benchmarks.sample.json")
with open(os.path.abspath(DATASET_PATH), encoding="utf-8") as fh:
    DATASET = json.load(fh)


class TestQuery(unittest.TestCase):
    def test_known_keyword_matches(self):
        r = qd.query("ai chatbot n8n", DATASET, CFG)
        self.assertEqual(r["gig_count"], 1243)
        self.assertIn(r["match_confidence"], ("HIGH", "MEDIUM"))
        self.assertGreaterEqual(r["matched_rows"], CFG["lookup"]["min_rows"])
        self.assertTrue(r["top_gigs"])
        self.assertEqual(r["flags"], [])

    def test_top_gigs_sorted_by_reviews(self):
        r = qd.query("ai chatbot", DATASET, CFG)
        reviews = [g["review_count"] for g in r["top_gigs"]]
        self.assertEqual(reviews, sorted(reviews, reverse=True))

    def test_nonsense_keyword_no_match(self):
        r = qd.query("underwater basket weaving zxqv", DATASET, CFG)
        self.assertIsNone(r["gig_count"])
        self.assertEqual(r["match_confidence"], "LOW")
        self.assertIn("no_match", r["flags"])
        self.assertEqual(r["top_gigs"], [])


if __name__ == "__main__":
    unittest.main()
