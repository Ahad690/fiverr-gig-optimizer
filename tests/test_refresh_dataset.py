#!/usr/bin/env python3
"""Offline tests for refresh_dataset.py gates — no network, no huggingface_hub."""
import os
import sys
import unittest

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "skills",
                       "fiverr-gig-optimizer", "scripts")
sys.path.insert(0, os.path.abspath(SCRIPTS))

import refresh_dataset as rd  # noqa: E402

GOOD = {
    "scraped_at": "2026-06-25", "category": "Programming & Tech",
    "subcategory": "Data Scraping", "title": "I will do web scraping",
    "seller_level": "level_two_seller", "rating": 4.9, "review_count": 100,
    "basic_price": 30, "standard_price": 90, "premium_price": 250,
    "basic_delivery_days": 2, "standard_delivery_days": 5, "premium_delivery_days": 10,
    "tags": ["scraping", "python"], "gig_count_in_search": 12978,
    "currency": "USD", "original_currency": "USD",
}


class TestValidateRow(unittest.TestCase):
    def test_good(self):
        self.assertEqual(rd.validate_row(GOOD), (True, "ok"))

    def test_pii_rejected(self):
        bad = dict(GOOD, seller_username="someone")
        ok, reason = rd.validate_row(bad)
        self.assertFalse(ok)
        self.assertIn("PII", reason)

    def test_missing_title(self):
        self.assertFalse(rd.validate_row(dict(GOOD, title=""))[0])

    def test_rating_out_of_range(self):
        self.assertFalse(rd.validate_row(dict(GOOD, rating=9))[0])

    def test_negative_price(self):
        self.assertFalse(rd.validate_row(dict(GOOD, basic_price=-5))[0])

    def test_bad_numeric_type(self):
        self.assertFalse(rd.validate_row(dict(GOOD, review_count="lots"))[0])

    def test_tags_not_list(self):
        self.assertFalse(rd.validate_row(dict(GOOD, tags="scraping"))[0])


class TestPartition(unittest.TestCase):
    def test_strips_to_keep_list(self):
        valid, invalid = rd.partition_rows([dict(GOOD, seller_url="x", _junk=1)])
        # PII row is rejected entirely (seller_url is forbidden)
        self.assertEqual(len(valid), 0)
        self.assertEqual(len(invalid), 1)

    def test_canonicalizes_extra_nonpii_keys(self):
        valid, invalid = rd.partition_rows([dict(GOOD, harmless_extra="keep?")])
        self.assertEqual(len(valid), 1)
        self.assertNotIn("harmless_extra", valid[0])  # rebuilt from keep-list


class TestSellerCountryKept(unittest.TestCase):
    def test_in_keep_not_forbidden(self):
        import contribute
        self.assertIn("seller_country", contribute.KEEP)
        self.assertNotIn("seller_country", contribute.FORBIDDEN)

    def test_survives_validation_and_strip(self):
        import contribute
        row = dict(GOOD, seller_country="PK")
        ok, _ = rd.validate_row(row)
        self.assertTrue(ok)
        valid, _ = rd.partition_rows([row])
        self.assertEqual(valid[0].get("seller_country"), "PK")


class TestDecide(unittest.TestCase):
    def test_file_errors_abort(self):
        v = rd.decide(seen=10, invalid_count=0, new_after_dedup=10,
                      min_new=1, max_corrupt_ratio=0.25, file_errors=1)
        self.assertEqual(v["action"], "abort")
        self.assertEqual(v["status"], "corrupt")

    def test_empty_is_noop(self):
        v = rd.decide(0, 0, 0, 1, 0.25, 0)
        self.assertEqual(v["action"], "noop")
        self.assertEqual(v["status"], "empty")

    def test_too_corrupt_aborts(self):
        v = rd.decide(seen=10, invalid_count=5, new_after_dedup=5,
                      min_new=1, max_corrupt_ratio=0.25, file_errors=0)
        self.assertEqual(v["action"], "abort")

    def test_insufficient_is_noop(self):
        v = rd.decide(seen=10, invalid_count=0, new_after_dedup=0,
                      min_new=1, max_corrupt_ratio=0.25, file_errors=0)
        self.assertEqual(v["action"], "noop")
        self.assertEqual(v["status"], "insufficient")

    def test_merge_ok(self):
        v = rd.decide(seen=10, invalid_count=1, new_after_dedup=8,
                      min_new=1, max_corrupt_ratio=0.25, file_errors=0)
        self.assertEqual(v["action"], "merge")
        self.assertEqual(v["status"], "ok")


if __name__ == "__main__":
    unittest.main()
