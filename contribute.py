#!/usr/bin/env python3
"""One-command, opt-in contribution to the community gig dataset.

    python contribute.py            # preview + (after a one-time token setup) open a PR
    python contribute.py --dry-run  # preview only; upload nothing

Thin wrapper over the skill's contribute script that:
  * auto-locates your scraped ``benchmarks.local.json`` (run a scrape first),
  * guides a one-time Hugging Face token setup, then never asks again, and
  * remembers your contributor name (in ``.contributor``) so you never retype it.

Nothing is ever uploaded without your token and an explicit run — no background
sync. Pass ``--input PATH`` to override the data file, ``--contributor NAME`` to
set/replace the remembered name.
"""
from __future__ import annotations

import os
import pathlib
import sys

_ROOT = pathlib.Path(__file__).parent
_SCRIPTS = _ROOT / "skills" / "fiverr-gig-optimizer" / "scripts"
_NAME_FILE = _ROOT / ".contributor"
sys.path.insert(0, str(_SCRIPTS))

from contribute import main  # noqa: E402  (skill script on the path above)


def _augment(argv: list[str]) -> list[str] | None:
    argv = list(argv)
    # Default --input to the scraped benchmarks in the repo root.
    if "--input" not in argv:
        default_input = _ROOT / "benchmarks.local.json"
        if not default_input.exists():
            print(f"No {default_input.name} found. Run a scrape first (it writes "
                  "benchmarks.local.json), or pass --input PATH.")
            return None
        argv += ["--input", str(default_input)]
    # Remember / reuse the contributor name.
    if "--contributor" in argv:
        try:
            _NAME_FILE.write_text(argv[argv.index("--contributor") + 1], encoding="utf-8")
        except (IndexError, OSError):
            pass
    elif _NAME_FILE.exists():
        name = _NAME_FILE.read_text(encoding="utf-8").strip()
        if name:
            argv += ["--contributor", name]
    elif sys.stdin.isatty() and "--dry-run" not in argv:
        name = input("Contributor name to credit on the PR (e.g. your HF username): ").strip()
        if name:
            try:
                _NAME_FILE.write_text(name, encoding="utf-8")
            except OSError:
                pass
            argv += ["--contributor", name]
    return argv


if __name__ == "__main__":
    _args = _augment(sys.argv[1:])
    raise SystemExit(1 if _args is None else main(_args))
