#!/usr/bin/env python3
"""Offline tests for scrape.py mapping — no network, no curl_cffi needed.

scrape.py imports the vendored scraper lazily, so importing the module here
exercises only the pure mapping helpers.
"""
import os
import sys
import unittest

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "skills",
                       "fiverr-gig-optimizer", "scripts")
sys.path.insert(0, os.path.abspath(SCRIPTS))

import scrape  # noqa: E402

FX = {"base": "USD", "rates": {"USD": 1.0, "EUR": 1.08}}

# Fixture mirrors the live test output: duration in HOURS, packages basic->premium.
SEARCH_ITEM = {
    "title": "I will build an ai chatbot",
    "seller_name": "code_craf",
    "seller_level": "level_two_seller",
    "price": 1.5,
    "rating": 5.0,
    "reviews_count": 865,
    "url": "https://www.fiverr.com/code_craf/ai-chatbot",
}
DETAIL = {
    "title": "I will build a custom ai chatbot",
    "seller": {"username": "code_craf", "level": "level_two_seller", "country": "US"},
    "packages": [
        {"name": "Basic", "price": 150.0, "delivery_days": 96, "revisions": -1},
        {"name": "Standard", "price": 750.0, "delivery_days": 336, "revisions": -1},
        {"name": "Premium", "price": 2500.0, "delivery_days": 504, "revisions": -1},
    ],
    "tags": ["AI Chatbot", "AI Developer", "OpenAI"],
    "rating": 5.0,
    "reviews_count": 865,
    "category": "Programming & Tech",
    "sub_category": "AI Development",
}


class TestHoursToDays(unittest.TestCase):
    def test_known_conversions(self):
        self.assertEqual(scrape.hours_to_days(96), 4)
        self.assertEqual(scrape.hours_to_days(336), 14)
        self.assertEqual(scrape.hours_to_days(504), 21)

    def test_edges(self):
        self.assertIsNone(scrape.hours_to_days(0))
        self.assertIsNone(scrape.hours_to_days(None))
        self.assertEqual(scrape.hours_to_days(12), 1)  # never round down to 0


class TestToUsd(unittest.TestCase):
    def test_usd_passthrough(self):
        self.assertEqual(scrape.to_usd(100, "USD", FX), 100.0)

    def test_eur(self):
        self.assertEqual(scrape.to_usd(100, "EUR", FX), 108.0)

    def test_unknown_currency_is_none(self):
        self.assertIsNone(scrape.to_usd(100, "JPY", FX))


class TestMapKyurish(unittest.TestCase):
    def setUp(self):
        self.row = scrape.map_kyurish(SEARCH_ITEM, DETAIL, 13954, "Programming & Tech",
                                      FX, "2026-06-25")

    def test_three_tier_prices(self):
        self.assertEqual(self.row["basic_price"], 150.0)
        self.assertEqual(self.row["standard_price"], 750.0)
        self.assertEqual(self.row["premium_price"], 2500.0)

    def test_delivery_converted_hours_to_days(self):
        self.assertEqual(self.row["basic_delivery_days"], 4)
        self.assertEqual(self.row["standard_delivery_days"], 14)
        self.assertEqual(self.row["premium_delivery_days"], 21)

    def test_gig_count_from_search_total(self):
        self.assertEqual(self.row["gig_count_in_search"], 13954)

    def test_metadata_and_normalization(self):
        self.assertEqual(self.row["category"], "Programming & Tech")
        self.assertEqual(self.row["subcategory"], "AI Development")
        self.assertEqual(self.row["review_count"], 865)
        self.assertEqual(self.row["tags"], ["ai chatbot", "ai developer", "openai"])
        self.assertEqual(self.row["currency"], "USD")
        self.assertEqual(self.row["original_currency"], "USD")

    def test_fewer_packages_leave_nulls(self):
        d = dict(DETAIL, packages=DETAIL["packages"][:1])
        row = scrape.map_kyurish(SEARCH_ITEM, d, 100, None, FX, "2026-06-25")
        self.assertEqual(row["basic_price"], 150.0)
        self.assertIsNone(row["standard_price"])
        self.assertIsNone(row["premium_price"])


if __name__ == "__main__":
    unittest.main()
