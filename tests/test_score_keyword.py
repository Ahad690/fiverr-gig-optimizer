#!/usr/bin/env python3
"""Tests for score_keyword.py — exact deterministic outputs (PRD §15 Phase 1)."""
import os
import sys
import unittest

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "skills",
                       "fiverr-gig-optimizer", "scripts")
sys.path.insert(0, os.path.abspath(SCRIPTS))

import score_keyword as sk  # noqa: E402

CFG = sk.load_config()


class TestCompetitionScore(unittest.TestCase):
    def test_anchor_values(self):
        anchors = CFG["competition"]["anchors"]
        self.assertEqual(sk.competition_score(200, anchors), 70)
        self.assertEqual(sk.competition_score(2000, anchors), 40)
        self.assertEqual(sk.competition_score(20000, anchors), 0)
        self.assertEqual(sk.competition_score(1, anchors), 100)

    def test_24_scores_82(self):
        anchors = CFG["competition"]["anchors"]
        self.assertEqual(sk.competition_score(24, anchors), 82)

    def test_10000_scores_12(self):
        anchors = CFG["competition"]["anchors"]
        self.assertEqual(sk.competition_score(10000, anchors), 12)

    def test_zero_is_none(self):
        anchors = CFG["competition"]["anchors"]
        self.assertIsNone(sk.competition_score(0, anchors))


class TestScore(unittest.TestCase):
    def test_low_competition_no_demand(self):
        r = sk.score("ai chatbot n8n", 24, [], CFG)
        self.assertEqual(r["competition_score"], 82)
        self.assertEqual(r["tier"], "LOW")
        self.assertIsNone(r["demand_score"])
        self.assertEqual(r["opportunity_score"], 82)
        self.assertIn("demand_unavailable", r["flags"])

    def test_untested_niche(self):
        r = sk.score("super rare combo", 0, [], CFG)
        self.assertIsNone(r["competition_score"])
        self.assertEqual(r["tier"], "UNTESTED")
        self.assertIsNone(r["opportunity_score"])
        self.assertIn("no_results", r["flags"])
        self.assertIn("untested_niche", r["flags"])

    def test_demand_blends_into_opportunity(self):
        top = [{"review_count": 500}, {"review_count": 500}, {"review_count": 500}]
        r = sk.score("ai chatbot", 24, top, CFG)
        # demand = median(500)/500*100 = 100; opp = 0.6*82 + 0.4*100 = 89.2 -> 89
        self.assertEqual(r["demand_score"], 100)
        self.assertEqual(r["opportunity_score"], 89)

    def test_tiers(self):
        self.assertEqual(sk.score("k", 199, [], CFG)["tier"], "LOW")
        self.assertEqual(sk.score("k", 200, [], CFG)["tier"], "MEDIUM")
        self.assertEqual(sk.score("k", 1999, [], CFG)["tier"], "MEDIUM")
        self.assertEqual(sk.score("k", 2000, [], CFG)["tier"], "HIGH")


if __name__ == "__main__":
    unittest.main()
