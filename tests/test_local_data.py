#!/usr/bin/env python3
"""Tests for the no-data-destroyed persistence layer (local_data.py) and
scrape.py's accumulate-by-default persist_rows(). Offline; no network."""
import json
import os
import sys
import tempfile
import unittest

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "skills",
                       "fiverr-gig-optimizer", "scripts")
sys.path.insert(0, SCRIPTS)

import local_data  # noqa: E402
import scrape  # noqa: E402


def _row(title, price=100):
    return {"title": title, "category": "Programming & Tech",
            "subcategory": "AI Development", "basic_price": price}


class TestLocalData(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "benchmarks.local.json")

    def test_atomic_write_and_load(self):
        local_data.write_json_atomic(self.path, [_row("a")])
        self.assertEqual(len(local_data.load_json_list(self.path)), 1)
        self.assertFalse(os.path.exists(self.path + ".tmp"))

    def test_corrupt_file_preserved_not_destroyed(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write("{definitely not json")
        rows = local_data.load_json_list(self.path)
        self.assertEqual(rows, [])
        backups = [f for f in os.listdir(self.dir) if ".corrupt-" in f]
        self.assertEqual(len(backups), 1)
        with open(os.path.join(self.dir, backups[0]), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "{definitely not json")  # bytes intact

    def test_backup_existing_keeps_bytes(self):
        local_data.write_json_atomic(self.path, [_row("a")])
        backup = local_data.backup_existing(self.path)
        self.assertTrue(backup and os.path.exists(backup))
        self.assertFalse(os.path.exists(self.path))
        with open(backup, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)[0]["title"], "a")

    def test_backup_missing_file_is_none(self):
        self.assertIsNone(local_data.backup_existing(self.path))


class TestPersistRows(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "benchmarks.local.json")

    def test_default_accumulates_never_overwrites(self):
        scrape.persist_rows(self.path, [_row("a")])
        final, note = scrape.persist_rows(self.path, [_row("b")])
        self.assertEqual([r["title"] for r in final], ["a", "b"])  # a survived
        self.assertIn("accumulate", note)

    def test_accumulate_dedups(self):
        scrape.persist_rows(self.path, [_row("a")])
        final, _ = scrape.persist_rows(self.path, [_row("a", price=999)])
        self.assertEqual(len(final), 1)  # duplicate key skipped, original kept
        self.assertEqual(final[0]["basic_price"], 100)

    def test_overwrite_backs_up_previous_file(self):
        scrape.persist_rows(self.path, [_row("a")])
        final, note = scrape.persist_rows(self.path, [_row("b")], overwrite=True)
        self.assertEqual([r["title"] for r in final], ["b"])
        backups = [f for f in os.listdir(self.dir) if ".bak-" in f]
        self.assertEqual(len(backups), 1)  # 'a' still exists in the backup
        with open(os.path.join(self.dir, backups[0]), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)[0]["title"], "a")

    def test_corrupt_existing_preserved_then_accumulates(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write("[broken")
        final, _ = scrape.persist_rows(self.path, [_row("a")])
        self.assertEqual(len(final), 1)
        self.assertTrue(any(".corrupt-" in f for f in os.listdir(self.dir)))


if __name__ == "__main__":
    unittest.main()
