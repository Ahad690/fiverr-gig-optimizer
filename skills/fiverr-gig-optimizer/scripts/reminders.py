#!/usr/bin/env python3
"""reminders.py — small shared CLI niceties.

The contribution reminder prints a colorful one-liner (to STDERR, so it never
corrupts machine-readable JSON on stdout) after a run, nudging users to grow the
free community dataset. On by default; toggle with `ui.contribution_reminder`
in references/scoring-config.json. Color is used only on an interactive
terminal, so logs/CI/pipes stay clean.
"""
import json
import os
import sys


def _load_config():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "..", "references", "scoring-config.json")
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def contribution_reminder(cfg=None):
    """Print the contribution nudge unless disabled in config."""
    cfg = cfg if cfg is not None else _load_config()
    ui = cfg.get("ui", {}) if isinstance(cfg, dict) else {}
    if not ui.get("contribution_reminder", True):
        return
    repo = cfg.get("dataset_repo", "the community dataset") if isinstance(cfg, dict) else ""

    msg = ("Love this? Help the free dataset grow - share anonymized data: "
           "scrape.py --contribute")
    hint = "disable: ui.contribution_reminder=false"

    if sys.stderr.isatty():
        line = (f"\033[1;35m✨\033[0m \033[1;36m{msg}\033[0m  "
                f"\033[2m| {repo} | {hint}\033[0m")
    else:
        line = f"* {msg}  | {repo} | {hint}"
    print(line, file=sys.stderr)
