#!/usr/bin/env python3
"""Offline tests for build_catalog.py — catalog renders, and each gig carries
both the canvas thumbnail and the copy-ready AI image prompt alternative."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
SCRIPT = os.path.join(ROOT, "skills", "fiverr-gig-optimizer", "scripts", "build_catalog.py")

CONFIG = {
    "seller": {"name": "Test Seller"},
    "provenance": "test data",
    "gigs": [{
        "id": 1, "phase": 1, "title": "I will build an AI chatbot with n8n",
        "cat": "Programming & Tech", "tags": ["ai", "chatbot", "n8n"],
        "desc": "A test description.",
        "competition": {"tier": "LOW", "count": 24},
        "scores": {"opportunity": 82, "flags": []},
        "pricing": {"basic": {"name": "Basic", "price": 50, "del": "3d", "rev": 1, "items": ["x"]}},
        "img": {"headline": "AI Chatbot", "sub": "n8n + OpenAI", "badge": "FAST DELIVERY",
                "tools": ["n8n", "OpenAI"], "accent": "#06b6d4"},
        "xsell": "pairs with gig #2",
    }],
}


class TestBuildCatalog(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.cfg = os.path.join(self.dir, "gig-config.json")
        self.out = os.path.join(self.dir, "catalog.html")
        with open(self.cfg, "w", encoding="utf-8") as fh:
            json.dump(CONFIG, fh)
        r = subprocess.run([sys.executable, SCRIPT, self.cfg, "--out", self.out],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(self.out, encoding="utf-8") as fh:
            self.html = fh.read()

    def test_canvas_thumbnail_still_present(self):
        self.assertIn("canvas", self.html)
        self.assertIn("Download PNG", self.html)

    def test_ai_prompt_ui_present(self):
        self.assertIn("Copy AI image prompt", self.html)
        self.assertIn("aiPrompt(", self.html)
        self.assertIn("ChatGPT / DALL·E / Midjourney", self.html)

    def test_fallback_prompt_composed_from_gig_img_block(self):
        # No ai_prompt in CONFIG -> the deterministic fallback composer is used;
        # it must reference the img fields and thumbnail spec…
        for needle in ("1280x769", "img.headline", "img.badge", "img.tools",
                       "img.accent", "spelled exactly as written"):
            self.assertIn(needle, self.html)
        # …and the gig's real data must be in the embedded CONFIG for it to use.
        self.assertIn("FAST DELIVERY", self.html)
        self.assertIn("n8n + OpenAI", self.html)

    def test_model_authored_ai_prompt_takes_priority(self):
        cfg = json.loads(json.dumps(CONFIG))
        cfg["gigs"][0]["img"]["ai_prompt"] = (
            "An isometric 3D scene of a friendly robot assembling chat bubbles "
            'on a conveyor belt, headline "AI CHATBOT" spelled exactly as written, '
            "1280x769 landscape, teal #06b6d4 accent, no watermarks."
        )
        cfg_path = os.path.join(self.dir, "gig-config2.json")
        out = os.path.join(self.dir, "catalog2.html")
        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh)
        r = subprocess.run([sys.executable, SCRIPT, cfg_path, "--out", out],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(out, encoding="utf-8") as fh:
            html = fh.read()
        # The authored prompt is embedded, and the renderer prefers it.
        self.assertIn("isometric 3D scene of a friendly robot", html)
        self.assertIn("gig.img.ai_prompt", html)


if __name__ == "__main__":
    unittest.main()
