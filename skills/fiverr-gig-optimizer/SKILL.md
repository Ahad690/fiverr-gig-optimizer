---
name: fiverr-gig-optimizer
description: >
  Generates a research-backed Fiverr gig catalog — titles, tags, 3-tier
  pricing, descriptions, thumbnail specs, and a phase-based launch plan —
  using deterministic Python scripts for all competition and pricing numbers.
  Use when the user asks to optimize a Fiverr gig, research a Fiverr keyword,
  check gig competition, price a gig, or plan a Fiverr launch.
allowed-tools: Bash(python3 *) Read Write
argument-hint: "[service or keyword]"
metadata:
  version: "1.1"
license: MIT
---

## Overview

This skill turns a freelancer's services into an optimized Fiverr gig catalog.
**Every market number — competition counts, demand, competitor prices — comes
from a Python script operating on real input data, never from the model.**
Offer-design fields (delivery days, revisions, package contents) are the
seller's own choices and may be authored, kept realistic. Scores and prices are
computed by the scripts below; you surface their JSON output verbatim.

## When to use

Optimize a Fiverr gig; research a Fiverr keyword; check gig competition; price a
gig or its tiers; plan a Fiverr launch; build a gig catalog from a service list.

## Hard rules

1. **Never invent a market number.** Competition counts, demand scores, and
   competitor prices come only from `score_keyword.py`, `query_dataset.py`, and
   `analyze_pricing.py`. Do not invent, round, relabel, or recall from memory
   any of them.
2. **Always run the scoring scripts** to produce competition/demand/opportunity
   and pricing. Surface their JSON fields verbatim.
3. **If market data is missing, ask or say "I don't have that."** When a dataset
   lookup returns `no_match`, ask the user to paste the Fiverr count — never
   fabricate one.
4. **Offer design is allowed.** Delivery days, revisions, and included items are
   the seller's choices; keep them realistic and consistent with stated turnaround.
5. **Strip PII before any contribution** (see `contribute.py` / DATA_POLICY.md).

Run scripts as: `python3 ${CLAUDE_SKILL_DIR}/scripts/<name>.py ...`

## Workflow

**Step 1 — Gather (FR1/FR2).** Ask in ONE numbered message: name; brand
(optional); website (optional); services list; headshot path (optional);
existing gig URLs or "none"; monthly revenue goal; experience level
(New / L1 / L2 / Top Rated). If fewer than 3 services, ask for more.

**Step 1b — Optional profile import.** If the user gives their Fiverr profile
URL, run `import_profile.py --url "<url>"` to pre-fill name, seller level, and
their existing gigs *with current prices/tags* (public data only — no private
analytics). Use `existing_gigs` to optimize what they already have and
`suggested_services` as keyword seeds; still ask for the revenue goal and any
new services. Skip if no link is given — never require it.

**Step 2 — Generate keyword candidates (FR6a).** From the services, propose
single-service keywords and 2-way (sometimes 3-way) combos, following
`references/fiverr-seo-playbook.md`. These are *search candidates, not
measurements* — generating them is allowed. They get scored next.

**Step 3 — Acquire data (pick a path).**
- **Path A (default, free):** for each candidate run
  `query_dataset.py --keyword "<kw>"`. Use the returned `gig_count`,
  `top_gigs`, and `match_confidence`. On `flags:["no_match"]` → go to Path B
  for that keyword. Write `top_gigs` to a temp file to feed Step 4.
- **Path B (manual):** ask the user to paste the "X services available" count
  Fiverr shows for the keyword. Never fabricate it.
- **Path C (live scrape, opt-in):** run
  `scrape.py --query "<kw>" [--category "<cat>"] [--limit N]`. The primary
  engine (vendored Perseus reader) needs no key and returns the real search
  total as `gig_count_in_search`; on a non-residential IP set `PROXY_URL`. With
  an Apify key it can fall back to the configured actor (which cannot supply the
  search total — count then comes from a manual paste). Then run
  `build_benchmarks.py` to build the pools + index. Live scraping is the user's
  responsibility under Fiverr's ToS.

**Step 4 — Score (FR7/FR8).** For each keyword:
`score_keyword.py --keyword "<kw>" --gig-count <N> [--top-gigs top.json]`.
Surface `competition_score`, `tier`, `demand_score`, `opportunity_score`,
`flags` verbatim.

**Step 5 — Price (FR9/FR10).** Build per-tier price lists for the category
(from `pricing-pools.local.json` via `build_benchmarks.py`, or from `top_gigs`),
then `analyze_pricing.py --prices pools.json --category "<cat>" --experience <lvl>`.
Use the recommended triple; respect low-confidence flags.

**Step 6 — Assemble `gig-config.json` (FR11–FR13).** Using the computed tiers,
scores, and prices + the playbook + `references/categories.json`: write
titles/tags/descriptions (lint rules in the playbook), pick phases and
cross-sells, set per-gig thumbnail accent from the palette. The `competition`,
`scores`, and `pricing` blocks are the script outputs — do not alter them.

**Step 7 — Render (FR14/FR15).**
`build_catalog.py gig-config.json` → `fiverr-catalog.html`. Optionally
`build_pdfs.py gig-config.json` for per-gig PDFs (skips if no Chrome).
After a live scrape, offer contribution (`contribute.py`, default no).

## Output format

- Present each keyword's scores exactly as the script returned them, with a
  **provenance line**, e.g.:
  `Competition for "ai chatbot n8n": sample-data match, confidence HIGH,
  dataset generated 2025-12 · score 82 (LOW) · demand n/a · opportunity 82`.
- State where files were written (`fiverr-catalog.html`, any PDFs).
- For low-confidence pricing or low match confidence, say so plainly.

## Error handling

- No scraper key → offer Path A (sample) or Path B (manual).
- `query_dataset.py` `no_match` / LOW confidence → ask for a manual count.
- Pricing tier `confidence:"low"` → present the number but flag it; for n=0,
  recommend nothing for that tier.
- No Chrome/Edge → `build_pdfs.py` warns and exits 0; the HTML still renders.

## Examples

**(a) Full run on sample data (MEDIUM/HIGH match).** User lists "n8n automation,
AI chatbots, OpenAI integrations". You generate combos, run `query_dataset.py`
("ai chatbot n8n" → gig_count 1243, confidence HIGH), score it (82, LOW),
analyze pricing from `top_gigs`, assemble `gig-config.json`, render the catalog,
and report each number with its provenance line.

**(b) No match → ask, don't guess.** A niche combo returns
`flags:["no_match"]`. You reply: "I don't have data for that keyword in the
sample set. Open Fiverr, search it, and paste the 'X services available' count
so I can score it." You do **not** state any competition number.
