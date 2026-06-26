#!/usr/bin/env python3
"""reminders.py — the user-facing contribution nudge.

Rendered into the catalog HTML (the deliverable the *user* opens), not printed
to stderr — stderr is consumed by the agent running the scripts, the user never
sees it. On by default; toggle with `ui.contribution_reminder` in
references/scoring-config.json.
"""
import html
import json
import os


def _load_config(cfg=None):
    if cfg is not None:
        return cfg
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "..", "references", "scoring-config.json")
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def contribution_html(cfg=None):
    """Return an HTML banner (or '' if disabled in config)."""
    cfg = _load_config(cfg)
    ui = cfg.get("ui", {}) if isinstance(cfg, dict) else {}
    if not ui.get("contribution_reminder", True):
        return ""
    repo = cfg.get("dataset_repo", "") if isinstance(cfg, dict) else ""
    href = html.escape(repo or "https://huggingface.co/")
    return (
        '<div class="contrib">✨ Love this? Help the free Fiverr dataset grow — '
        f'<a href="{href}" target="_blank" rel="noopener">contribute your '
        'anonymized data</a> so everyone gets better benchmarks. '
        '<span class="contrib-off">(maintainers: toggle via '
        '<code>ui.contribution_reminder</code>)</span></div>'
    )
