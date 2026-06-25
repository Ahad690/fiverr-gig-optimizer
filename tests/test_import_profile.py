#!/usr/bin/env python3
"""Offline tests for import_profile.py — no network, no curl_cffi needed."""
import os
import sys
import unittest

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "skills",
                       "fiverr-gig-optimizer", "scripts")
sys.path.insert(0, os.path.abspath(SCRIPTS))

import import_profile as ip  # noqa: E402

FX = {"base": "USD", "rates": {"USD": 1.0}}

DETAIL = {
    "title": "I will build a custom ai chatbot",
    "url": "https://www.fiverr.com/code_craf/ai-chatbot",
    "seller": {"level": "level_two_seller"},
    "packages": [
        {"name": "Basic", "price": 150.0, "delivery_days": 96},
        {"name": "Standard", "price": 750.0, "delivery_days": 336},
        {"name": "Premium", "price": 2500.0, "delivery_days": 504},
    ],
    "tags": ["AI Chatbot", "OpenAI"],
    "rating": 5.0,
    "reviews_count": 865,
    "category": "Programming & Tech",
    "sub_category": "AI Development",
}


class TestExtractUsername(unittest.TestCase):
    def test_bare_username(self):
        self.assertEqual(ip.extract_username("code_craf"), "code_craf")

    def test_profile_url(self):
        self.assertEqual(ip.extract_username("https://www.fiverr.com/code_craf"), "code_craf")

    def test_gig_url_returns_owner(self):
        self.assertEqual(
            ip.extract_username("https://www.fiverr.com/code_craf/do-ai-chatbot-stuff"),
            "code_craf")

    def test_no_scheme(self):
        self.assertEqual(ip.extract_username("fiverr.com/code_craf"), "code_craf")


class TestMapExistingGig(unittest.TestCase):
    def setUp(self):
        self.g = ip.map_existing_gig(DETAIL, FX)

    def test_prices_and_hours_to_days(self):
        self.assertEqual(self.g["pricing"]["basic"]["price"], 150.0)
        self.assertEqual(self.g["pricing"]["basic"]["delivery_days"], 4)
        self.assertEqual(self.g["pricing"]["standard"]["delivery_days"], 14)
        self.assertEqual(self.g["pricing"]["premium"]["delivery_days"], 21)

    def test_metadata(self):
        self.assertEqual(self.g["category"], "Programming & Tech")
        self.assertEqual(self.g["subcategory"], "AI Development")
        self.assertEqual(self.g["seller_level"], "level_two_seller")
        self.assertEqual(self.g["tags"], ["ai chatbot", "openai"])


class TestSuggestedServices(unittest.TestCase):
    def test_ranks_by_frequency(self):
        gigs = [
            {"tags": ["ai chatbot", "openai"]},
            {"tags": ["ai chatbot", "n8n"]},
        ]
        out = ip.suggested_services(gigs)
        self.assertEqual(out[0], "ai chatbot")  # appears twice -> first
        self.assertIn("openai", out)
        self.assertIn("n8n", out)


if __name__ == "__main__":
    unittest.main()
