# AGENTS.md — running fiverr-gig-optimizer from any agentic CLI

This is a **Claude Code skill**, but it is CLI-agnostic: the intelligence lives in
`skills/fiverr-gig-optimizer/SKILL.md` plus deterministic Python scripts, so any
agentic coding CLI (Claude Code, Codex, OpenCode, Cursor, Gemini CLI, Copilot CLI,
Qwen, Kimi, Grok) can drive it. This file is the entry point those tools read.

## The one rule you may never break

**The model never emits a market number.** Competition counts, demand signals, and
competitor pricing come **only** from the scripts below, run on real data. If the
data isn't there, you **ask the user or say you don't have it** — you never estimate,
average-in-your-head, or fill a gap with a plausible figure. Offer design (delivery
days, revisions, package contents) *is* yours to author; market measurements are not.

Every score you surface must keep its provenance line. This is the whole point of the
project — a fabricated number defeats it.

## How to run it

1. Read `skills/fiverr-gig-optimizer/SKILL.md` — it is the full operating procedure.
2. Interview the user for their services (or read a CV/portfolio they provide).
3. Produce numbers only via the deterministic scripts:

```bash
python skills/fiverr-gig-optimizer/scripts/score_keyword.py   # competition + opportunity
python skills/fiverr-gig-optimizer/scripts/query_dataset.py    # demand from sample/live data
python skills/fiverr-gig-optimizer/scripts/analyze_pricing.py  # 3-tier pricing from competitor percentiles
python skills/fiverr-gig-optimizer/scripts/build_catalog.py gig-config.json --out fiverr-catalog.html
```

4. Render `fiverr-catalog.html` — the deliverable — with a provenance line under every score.

## Contract enforcement

`tests/` (82 tests) encodes the honesty rules. If you change scoring, pricing, or
rendering, `pytest -q` must stay green. A change that lets the model author a market
number is a bug, not a feature.
