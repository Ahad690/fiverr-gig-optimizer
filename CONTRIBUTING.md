# Contributing to fiverr-gig-optimizer

Thanks for helping build gig research that refuses to guess. **First-timers welcome** —
this repo is deliberately friendly to your first open-source PR.

## Your first PR in 10 minutes

```bash
git clone https://github.com/Ahad690/fiverr-gig-optimizer && cd fiverr-gig-optimizer
python -m venv .venv && . .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt pytest
pytest -q                                        # 82 tests — should be green
```

Pick a [`good first issue`](https://github.com/Ahad690/fiverr-gig-optimizer/labels/good%20first%20issue),
comment to claim it, open a PR. That's it.

## The one rule (non-negotiable)

**The model never invents a market number.** Competition, demand, and pricing come
only from the deterministic scripts, on real data. If you add a feature, it must not
let the LLM author a market figure — provenance on every number, or it doesn't merge.
See `AGENTS.md` for the full contract.

## What makes a good PR here

- **Small and scoped.** One issue, one PR.
- **A test.** New behavior gets a test in `tests/`. Keep `pytest -q` green.
- **Honest.** Category presets, output formats, docs, and new deterministic data
  sources are all welcome. "Make the AI estimate X" is not.

## Good areas to contribute

- New **category presets** (Graphic Design, Video, Writing gigs — not just Programming).
- New **output formats** for the catalog (JSON, CSV, Notion export).
- **Localization** of the paste sheet and catalog UI.
- More **deterministic data adapters** (new dataset sources with provenance).
- Docs, examples, and test coverage.

By contributing you agree your work is MIT-licensed like the rest of the repo.
