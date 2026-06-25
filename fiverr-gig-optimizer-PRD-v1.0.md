# PRD — Fiverr Gig Optimizer (Claude Code Skill)

**Version:** 1.0
**Status:** Ready to build
**Type:** Open-source Claude Code Skill + community dataset
**Target runtime:** Claude Code (Skills standard, agentskills.io). Portable to other agents that support the standard.

---

## 0. How to use this document with Claude Code

This PRD is written to be **one-shot implementable**. To build:

1. Create an empty directory and `git init`.
2. Save this file as `PRD.md` in the root.
3. In Claude Code, run:
   > Read `PRD.md` in full. Build the entire project following Section 14 (Build Order) top to bottom. Create every file in Section 11 (Repo Structure). Do not skip the scripts. After each phase, run the acceptance check for that phase from Section 15 before moving on. Use only the deterministic scoring defined in Section 8 — never invent competition numbers or prices anywhere in the skill's instructions or output.

**North-star rule for the implementer:** every number the skill reports about competition, demand, or pricing must come from a Python script operating on real input data. The LLM layer (SKILL.md instructions) must never estimate, guess, or "mentally search" for any figure. If data is missing, the skill asks the user for it or says it doesn't have it.

---

## 1. Overview

### 1.1 What we are building
A Claude Code Skill named `fiverr-gig-optimizer` that helps a freelancer turn their list of services into an optimized, research-backed Fiverr gig catalog: titles, tags, 3-tier pricing, descriptions, thumbnail specs, a phase-based launch plan, and a cross-sell map. All quantitative recommendations are derived from real data via deterministic Python scripts — not from model guesses.

### 1.2 Why it exists
Two gaps:
- **Fluff skills.** Existing "Fiverr optimizer" repos instruct the model to "mentally estimate" competition and prices. That output is hallucinated and changes every run. This project replaces guesses with computed values.
- **No good free data.** There is no comprehensive, current, all-category Fiverr dataset available for free. Public Kaggle datasets are stale (12+ months) and niche (mostly data-science gigs). This project ships a sample dataset, lets users optionally pull fresh data with their own scraper key, and builds a shared community dataset through opt-in contributions.

### 1.3 Distribution model
- Open-source on GitHub under MIT (code) / CC-BY-4.0 (data and docs).
- Installable as a Claude Code **plugin** via a `marketplace.json` so users run `/plugin marketplace add <user>/<repo>` then `/plugin install fiverr-gig-optimizer@<marketplace>`.
- A companion **community dataset** hosted on the Hugging Face Datasets Hub, grown via opt-in pull requests from users.

---

## 2. Goals and Non-Goals

### 2.1 Goals
- G1. Produce a complete, copy-paste-ready Fiverr gig catalog from a user's services.
- G2. Base every competition/demand/pricing figure on real data through deterministic scripts.
- G3. Work out-of-the-box for free using a bundled sample dataset (zero API key required).
- G4. Optionally fetch fresh, category-specific data using the user's own scraper API key.
- G5. Optionally let users contribute anonymized data back to a shared public dataset.
- G6. Ship as a clean, properly packaged, installable open-source Claude Code plugin.

### 2.2 Non-Goals (explicit)
- N1. **No machine learning.** No training, no model files, no embeddings, no ranking prediction. Scoring is rule-based and auditable.
- N2. **No scraping by default.** The skill does not scrape Fiverr automatically. Live scraping is opt-in, runs only with the user's own API key, and is the user's responsibility.
- N3. **No guessed numbers.** No fallback to model-estimated competition counts or prices anywhere.
- N4. Not a Fiverr account automation tool (no posting, no auto-refresh, no messaging bots).
- N5. Not a paid product; no payment layer in v1.

---

## 3. Design Principles / Constraints

- **P1 — Determinism over generation.** Sorting, parsing, scoring, statistics, validation, and dedup live in Python scripts. Code is repeatable; the model is not. (This is the single most important constraint.)
- **P2 — Progressive disclosure.** `SKILL.md` stays lean (target < 400 lines). Detailed rules go in `references/` and load only when needed. Scripts are executed, not read into context.
- **P3 — Honest about data.** If the user has no data and provides no key, the skill uses the sample dataset and clearly labels its age/coverage. It never pretends a number is live.
- **P4 — Privacy by default.** Contributions strip all seller-identifying fields. Only listing metadata (titles, prices, tiers, ratings counts, tags, category) is shared.
- **P5 — Portability.** Use only standard Skills frontmatter fields where possible so the skill works across agents supporting the open standard. Keep Claude-Code-specific fields optional.
- **P6 — No heavy deps unless justified.** Python stdlib first (`json`, `csv`, `statistics`, `math`, `hashlib`, `argparse`, `urllib`). Add `requests` for HTTP, `pandas` only if it meaningfully simplifies the benchmark build. The HTML/PDF output reuses headless Chrome (already a common machine dep) rather than a PDF library.

---

## 4. Target Users

- **U1 — New Fiverr seller** with skills but no gigs, unsure what to offer or how to price. Uses sample data, free path.
- **U2 — Existing seller** optimizing or expanding. May provide their Analytics export and/or a scraper key for fresh data in their niche.
- **U3 — Agency / power user** scraping multiple categories, willing to contribute data back.
- **U4 — Contributor / developer** improving the skill or the dataset.

---

## 5. User Stories

- US1. As U1, I describe my services and get 3–4 launch gigs with titles, tags, pricing, and thumbnail specs, so I can publish today.
- US2. As any user, I want competition labels that reflect the real number of gigs for a keyword, so I target low-competition niches instead of crowded ones.
- US3. As any user, I want pricing tiers benchmarked against real competitor prices, so I don't underprice or overprice.
- US4. As U2, I paste the "X services available" count Fiverr shows and the skill scores it — no guessing.
- US5. As U2/U3, I provide my own scraper API key and the skill pulls fresh data for my exact categories.
- US6. As U3, I opt in to contribute my anonymized scraped data so the shared dataset improves; I'm credited.
- US7. As any user, I get a single HTML catalog with copy buttons and downloadable thumbnails, plus optional per-gig PDFs.
- US8. As U4, I can read `DATA_POLICY.md` and understand exactly what is collected and stripped.

---

## 6. Functional Requirements

### 6.1 Information gathering (SKILL.md, Step 1)
- FR1. Ask, in one numbered message: name; brand (optional); website (optional); services list; headshot path (optional); existing gig URLs or "none"; monthly revenue goal; experience level (New / L1 / L2 / Top Rated).
- FR2. If fewer than 3 services are given, prompt for more (needed for combo-niche analysis).

### 6.2 Data acquisition (one of three paths, user chooses)
- FR3. **Path A — Sample data (default, free).** Use bundled `references/benchmarks.sample.json`. Clearly state coverage and the `generated_at` date.
- FR4. **Path B — Manual counts.** For each service/combo keyword, ask the user to paste the gig count Fiverr shows ("X services available"). Never fabricate this number.
- FR5. **Path C — Live scrape (opt-in).** If the user provides an Apify (or compatible) API key and actor ID, run `scrape.py` to pull gigs for their target categories into `benchmarks.local.json`.
- FR6. The chosen path and data freshness are surfaced in the final output ("Pricing based on: sample data, generated 2026-XX; competition for 'X' based on: user-supplied count / live scrape").

### 6.3 Competition + opportunity scoring (deterministic)
- FR7. `score_keyword.py` computes a competition score, demand score, opportunity score, and tier label for each keyword/combo using only supplied data and the thresholds/weights in `references/scoring-config.json`. See Section 8 for the exact formula.
- FR8. The skill reports only the script's output. No rounding, relabeling, or invented numbers in prose.

### 6.4 Pricing analysis (deterministic)
- FR9. `analyze_pricing.py` takes competitor prices (from the chosen data path) for a category and returns p10/p25/median/p75/p90 per tier and a recommended Basic/Standard/Premium triple using the strategy in `references/scoring-config.json`.
- FR10. If a category has insufficient samples (configurable `min_samples`, default 8), the script says so and the skill tells the user pricing is low-confidence — it does not invent a benchmark.

### 6.5 Gig catalog generation
- FR11. The skill assembles a `gig-config.json` (schema in Section 7.2) using: computed competition tiers, computed pricing, SEO rules from `references/fiverr-seo-playbook.md`, and the Fiverr taxonomy in `references/categories.json`.
- FR12. Title rules enforced: starts with "I will", ≤ 80 chars, primary keyword front-loaded. Exactly 5 tags. Description ≤ 1200 chars with the primary keyword in the first paragraph. Each gig gets a unique thumbnail accent color from the playbook palette.
- FR13. Phase-based rollout: Phase 1 = 3–4 lowest-competition combo niches; Phase 2 = 2–3 premium upsells (after 5+ reviews); Phase 3 = 1–2 expansions. Each gig lists 2–3 cross-sell targets.

### 6.6 Output rendering
- FR14. `build-catalog.py` reads `gig-config.json` and writes a single self-contained `fiverr-catalog.html`: canvas thumbnails (1280×769), copy-to-clipboard buttons for title/desc/tags, per-gig PNG download, cross-sell map, action plan. (This step may reuse/adapt an existing open script; it is the only "presentation" component and contains no scoring logic.)
- FR15. `build-pdfs.py` optionally renders one A4 PDF per gig via headless Chrome. Skipped gracefully if no Chrome/Edge is found (warn, don't fail).

### 6.7 Contribution (opt-in)
- FR16. After a live scrape, ask whether to contribute the anonymized data to the community dataset. Default to no; never pressure.
- FR17. `contribute.py` strips PII (Section 7.3), deduplicates against the existing dataset, and opens a pull request to the Hugging Face dataset repo. The user is added to `CONTRIBUTORS.md`.

### 6.8 Invocation
- FR18. The skill is model-invocable (auto-triggers on Fiverr-related phrasing in its description) and also runnable directly as `/fiverr-gig-optimizer`.

---

## 7. Data Schemas

### 7.1 Canonical gig record (used by scraper, sample data, and dataset)
```json
{
  "scraped_at": "2026-06-25",
  "category": "Programming & Tech",
  "subcategory": "AI Development > AI Chatbots",
  "title": "I will build a custom AI chatbot for your website",
  "seller_level": "level_two_seller",
  "rating": 4.9,
  "review_count": 847,
  "basic_price": 75,
  "standard_price": 199,
  "premium_price": 450,
  "basic_delivery_days": 3,
  "standard_delivery_days": 7,
  "premium_delivery_days": 14,
  "tags": ["chatbot", "ai", "openai", "langchain", "automation"],
  "gig_count_in_search": 1243,
  "currency": "USD"
}
```
Notes: prices normalized to USD. `gig_count_in_search` is the "X services available" total for the search that produced this row (same value across rows from one search). Missing numeric fields are `null`, never zero-filled or guessed.

### 7.2 `gig-config.json` (input to the renderers)
```json
{
  "seller": { "name": "", "brand": "", "website": "", "photo": "" },
  "data_provenance": {
    "pricing_source": "sample_dataset|manual|live_scrape",
    "pricing_generated_at": "2026-06-25",
    "competition_source": "manual|live_scrape|sample_dataset"
  },
  "strategy": {
    "monthlyTarget": "$10,000",
    "primaryCategory": "Programming & Tech",
    "phase1Count": 4, "phase2Count": 3, "phase3Count": 2
  },
  "gigs": [
    {
      "id": 1,
      "phase": 1,
      "title": "I will ... (<=80 chars)",
      "cat": "Programming & Tech > AI Chatbots",
      "tags": ["t1","t2","t3","t4","t5"],
      "desc": "<=1200 chars",
      "competition": { "count": 24, "tier": "LOW", "source": "manual" },
      "scores": { "competition": 88, "demand": 41, "opportunity": 69 },
      "xsell": "CROSS-SELLS TO: Gig #2, Gig #3",
      "pricing": {
        "basic":    { "name":"Starter","title":"","price":97,"del":"3 days","rev":"2","items":[] },
        "standard": { "name":"Business","title":"","price":247,"del":"6 days","rev":"3","items":[] },
        "premium":  { "name":"Enterprise","title":"","price":497,"del":"10 days","rev":"5","items":[] }
      },
      "img": {
        "bg1":"#030a0a","bg2":"#061818","accent":"#06b6d4",
        "headline":"AI CHATBOT","sub":"Custom GPT for your site",
        "badge":"LOW COMPETITION","tools":["OpenAI","LangChain","n8n"],
        "pdfWhat":"One-line summary for PDF"
      }
    }
  ]
}
```
The renderer must treat `competition`, `scores`, and `pricing` as authoritative inputs (already computed). The renderer performs **no** scoring.

### 7.3 PII stripping (contribution)
**Keep:** `scraped_at, category, subcategory, title, seller_level, rating, review_count, basic_price, standard_price, premium_price, basic_delivery_days, standard_delivery_days, premium_delivery_days, tags, gig_count_in_search, currency`.
**Drop before contributing (hard requirement):** seller username, seller display name, profile URL, gig URL, profile photo URL, seller country, any free-text review content, any image URLs, any ID fields.

---

## 8. Scoring Specification (deterministic — the core of the project)

All constants live in `references/scoring-config.json` so they are transparent and tunable. Defaults below.

### 8.1 Inputs available
- `gig_count` — integer total gigs for the keyword (manual paste or scrape). Required for competition scoring.
- Optional `top_gigs` — list of competitor records (for demand + pricing). When absent, demand score is reported as `null` (not guessed) and opportunity falls back to competition-only with a flag.

### 8.2 Competition score (0–100, higher = less competition = better)
```
MAX_GIGS = 10000   # ceiling for normalization
competition_score = round( clamp(100 - (log10(max(gig_count,1)) / log10(MAX_GIGS)) * 100, 0, 100) )
```
Tier from `gig_count` via thresholds:
```
LOW:    gig_count < 200
MEDIUM: 200 <= gig_count < 2000
HIGH:   gig_count >= 2000
```

### 8.3 Demand score (0–100, higher = more proven buyer demand)
Proxy = median `review_count` of the top N (default 10) competitor gigs.
```
DEMAND_CEILING = 500
demand_score = round( clamp((median_top_reviews / DEMAND_CEILING) * 100, 0, 100) )
```
If `top_gigs` is unavailable → `demand_score = null`.

### 8.4 Opportunity score (0–100)
```
if demand_score is not null:
    opportunity = round(0.6 * competition_score + 0.4 * demand_score)
else:
    opportunity = competition_score   # flagged: "competition-only, no demand signal"
```
Rationale documented in README so users can audit and adjust weights.

### 8.5 Combo-niche bonus (optional, default off)
If a keyword is a 2+ word combo whose `gig_count` is below the LOW threshold, add `COMBO_BONUS` (default 0; opt-in to +10) to `opportunity`, capped at 100. Off by default to keep scores literal.

### 8.6 Pricing recommendation
Given competitor prices per tier:
```
percentiles: p10, p25, median, p75, p90  (statistics.quantiles)
recommended:
  basic    = p25   (entry, gets the click)
  standard = median
  premium  = p75
new-seller strategy flag (experience == "New"):
  basic    = p10   (undercut to win first reviews)
  standard = p25
  premium  = median
```
If samples < `min_samples` (default 8) → return `{"confidence":"low","reason":"insufficient samples (n=<k>)"}` and recommend nothing numeric.

### 8.7 Output contract (every script emits JSON to stdout)
`score_keyword.py` output:
```json
{
  "keyword": "ai chatbot n8n",
  "gig_count": 24,
  "competition_score": 88,
  "tier": "LOW",
  "demand_score": null,
  "opportunity_score": 88,
  "flags": ["demand_unavailable"]
}
```
The SKILL.md instructs the model to surface these fields verbatim.

---

## 9. Data Sources and Policy

- **Seed (`benchmarks.sample.json`).** Compiled by merging the public Kaggle Fiverr datasets the maintainer has (e.g. `asarli/...`, `muhammadadiltalay/fiverr-data-gigs`, `ourfuture/fiverr-gigs`) into the canonical schema, with `scraped_at` set to each dataset's date. Document the merge in `scripts/seed/README.md`. Coverage is partial and dated — labeled as such everywhere it's used.
- **Live (`scrape.py`).** Uses a third-party scraping API (Apify-compatible) with the **user's own key** and a configurable actor ID. Costs are the user's (roughly a few cents per 100 gigs depending on provider). The skill never ships a key and never scrapes without one.
- **Community dataset (Hugging Face).** Public, CC-BY-4.0, grown via opt-in PRs from `contribute.py`. Repo: `huggingface.co/datasets/<owner>/fiverr-gigs` (placeholder; maintainer sets the real path in `scoring-config.json` → `dataset_repo`).
- **`DATA_POLICY.md`** must state: only public Fiverr listing data is handled; exactly which fields are kept vs stripped (Section 7.3); that contribution is opt-in and CC-BY-4.0; that live scraping is the user's responsibility and subject to Fiverr's ToS; that the project stores no private user account data.

---

## 10. SKILL.md Specification

### 10.1 Frontmatter (exact)
```yaml
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
  version: "1.0"
license: MIT
---
```
Constraints to respect: `name` ≤ 64 chars, lowercase/numbers/hyphens only; `description` ≤ 1024 chars; no XML tags; no reserved words ("anthropic", "claude").

### 10.2 Body structure (sections, in order)
1. `## Overview` — one paragraph; restate the determinism rule.
2. `## When to use` — trigger phrases.
3. `## Hard rules` — never invent competition counts or prices; always run the scoring scripts; if data is missing, ask or say "I don't have that"; strip PII before any contribution.
4. `## Workflow` — Steps 1–7 mapping to FR1–FR17, each step naming the exact script to run via `python3 ${CLAUDE_SKILL_DIR}/scripts/<name>.py ...` and the reference file to read.
5. `## Output format` — how to present scores (verbatim from JSON) and where files are written.
6. `## Error handling` — missing key → offer manual/sample paths; insufficient samples → low-confidence flag; no Chrome → skip PDFs with a warning.
7. `## Examples` — (a) a full run on sample data; (b) a "missing gig count" run where the skill asks instead of guessing.

Keep total body < 400 lines. Push the full SEO ruleset and color palette into `references/fiverr-seo-playbook.md`, loaded only when generating gigs.

---

## 11. Repo Structure (create all of these)

```
fiverr-gig-optimizer/
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
├── skills/
│   └── fiverr-gig-optimizer/
│       ├── SKILL.md
│       ├── scripts/
│       │   ├── score_keyword.py        # FR7 / Section 8.2–8.5
│       │   ├── analyze_pricing.py      # FR9 / Section 8.6
│       │   ├── scrape.py               # FR5 (Apify-compatible, user key)
│       │   ├── build_benchmarks.py     # builds benchmarks.local.json from scrape/CSV
│       │   ├── contribute.py           # FR17 (PII strip + dedup + HF PR)
│       │   ├── build_catalog.py        # FR14 (HTML; no scoring)
│       │   ├── build_pdfs.py           # FR15 (headless Chrome; optional)
│       │   └── seed/
│       │       ├── merge_kaggle.py     # builds benchmarks.sample.json from raw CSVs
│       │       └── README.md           # documents the merge + source dates
│       ├── references/
│       │   ├── benchmarks.sample.json  # bundled seed data (canonical schema)
│       │   ├── scoring-config.json     # all thresholds/weights (Section 8)
│       │   ├── categories.json         # Fiverr taxonomy
│       │   ├── keyword-tiers.json      # tier thresholds (or inline in scoring-config)
│       │   └── fiverr-seo-playbook.md  # title/tag/desc rules + color palette
│       └── assets/
│           └── pdf-template.html       # optional editorial PDF template
├── tests/
│   ├── test_score_keyword.py
│   └── test_analyze_pricing.py
├── examples/
│   └── sample-gig-config.json
├── DATA_POLICY.md
├── CONTRIBUTORS.md
├── LICENSE                              # MIT
├── .gitignore                           # ignore *.local.json, .env, __pycache__
└── README.md
```

---

## 12. Plugin Packaging

### 12.1 `plugin.json`
```json
{
  "name": "fiverr-gig-optimizer",
  "version": "1.0.0",
  "description": "Research-backed Fiverr gig optimizer. Deterministic competition + pricing scoring, no ML, no guessing.",
  "author": { "name": "<maintainer>" },
  "license": "MIT",
  "keywords": ["fiverr", "freelance", "gig", "pricing", "seo", "claude-code", "skill"]
}
```

### 12.2 `marketplace.json` (repo root, inside `.claude-plugin/`)
```json
{
  "name": "fiverr-tools",
  "owner": "<github-username>",
  "plugins": [
    {
      "name": "fiverr-gig-optimizer",
      "source": "./",
      "description": "Research-backed Fiverr gig optimizer (Claude Code skill)."
    }
  ]
}
```
Rules: all names kebab-case; `name` must NOT be a reserved Anthropic marketplace name (e.g. `claude-code-plugins`, `anthropic-plugins`, `agent-skills`). For reproducible installs in docs, show pinning by tag/SHA. Validate with `claude plugin validate .`.

### 12.3 Install instructions (for README)
```
/plugin marketplace add <github-username>/fiverr-gig-optimizer
/plugin install fiverr-gig-optimizer@fiverr-tools
```

---

## 13. Dependencies

- **Python:** 3.8+. Stdlib: `json, csv, statistics, math, hashlib, argparse, urllib, os, sys, datetime`. Third-party: `requests` (HTTP for scrape/contribute). `pandas` only inside `seed/merge_kaggle.py` and `build_benchmarks.py` if it simplifies CSV merging (otherwise stdlib `csv`).
- **Optional runtime:** Google Chrome or Microsoft Edge for `build_pdfs.py` (auto-detect; skip gracefully if absent).
- **Scraper:** an Apify-compatible account + API token, supplied by the user via `--api-key` or `APIFY_TOKEN` env var. Actor ID configurable in `scoring-config.json` → `scraper.actor_id`.
- **Contribution:** a Hugging Face account + token for opening dataset PRs (only needed by contributors).
- Pin nothing the model must guess; list exact versions in `requirements.txt` (create it: `requests>=2.31` and, if used, `pandas>=2.0`).

---

## 14. Build Order (follow top to bottom)

**Phase 0 — Scaffold.** Create the repo tree (Section 11), `LICENSE` (MIT), `.gitignore`, empty `CONTRIBUTORS.md`, `requirements.txt`.

**Phase 1 — Scoring core (the heart).**
1. `references/scoring-config.json` with all constants from Section 8.
2. `score_keyword.py` (Section 8.2–8.5, output contract 8.7). CLI: `score_keyword.py --keyword "x" --gig-count 24 [--top-gigs path.json]`.
3. `analyze_pricing.py` (Section 8.6). CLI: `analyze_pricing.py --prices path.json --experience New`.
4. `tests/test_score_keyword.py`, `tests/test_analyze_pricing.py` — assert exact outputs for known inputs (e.g. gig_count=24 → competition_score=88, tier=LOW).

**Phase 2 — Reference data.**
5. `references/categories.json` (Fiverr taxonomy; can start with top categories + key subcategories, expandable).
6. `references/fiverr-seo-playbook.md` (title/tag/desc rules + the 8-color thumbnail palette).
7. `scripts/seed/merge_kaggle.py` + `seed/README.md`; produce `references/benchmarks.sample.json` from the maintainer's Kaggle CSVs (placeholder file with a few real rows is acceptable for first build; document how to regenerate).

**Phase 3 — Skill definition.**
8. `SKILL.md` (Section 10) wiring Steps 1–7 to the scripts and references. Enforce the hard rules.
9. `examples/sample-gig-config.json` matching Section 7.2.

**Phase 4 — Data acquisition (opt-in).**
10. `scrape.py` — call the configured Apify actor with the user's key, map results into the canonical schema (Section 7.1), write `benchmarks.local.json`. Handle 429/auth errors with clear messages.
11. `build_benchmarks.py` — turn a scrape result or a user CSV into per-category price lists consumed by `analyze_pricing.py`.

**Phase 5 — Output rendering.**
12. `build_catalog.py` — read `gig-config.json`, emit `fiverr-catalog.html` (canvas thumbnails, copy buttons, PNG download, cross-sell map, action plan). No scoring inside.
13. `build_pdfs.py` — optional per-gig A4 PDFs via headless Chrome; skip gracefully if no browser.

**Phase 6 — Contribution.**
14. `contribute.py` — PII strip (7.3), dedup (hash on `title|category`), open a Hugging Face dataset PR; append contributor to `CONTRIBUTORS.md`.
15. `DATA_POLICY.md` (Section 9).

**Phase 7 — Packaging + docs.**
16. `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` (Section 12); run `claude plugin validate .`.
17. `README.md` (Section 16).

---

## 15. Acceptance Criteria (run per phase)

- **Phase 1.** `python3 score_keyword.py --keyword "ai chatbot n8n" --gig-count 24` returns `competition_score: 88, tier: "LOW", demand_score: null, opportunity_score: 88`. `analyze_pricing.py` on a 12-row price file returns p25/median/p75 and a recommended triple; on a 5-row file returns `confidence: "low"`. Both test files pass.
- **Phase 3.** Installed locally, asking "help me optimize my Fiverr gigs for n8n automation" auto-triggers the skill; `/fiverr-gig-optimizer` also works. The skill **asks for the gig count** when none is provided and **does not** state any competition number it wasn't given. Verify with `claude --debug` (no YAML errors) and `/doctor` (description not truncated/dropped).
- **Phase 4.** With a valid scraper key, `scrape.py` writes ≥ 1 valid canonical-schema record; with an invalid key it prints a clear auth error and exits non-zero (no crash, no fabricated data).
- **Phase 5.** `build_catalog.py` on `examples/sample-gig-config.json` produces a single HTML file that opens in a browser with working copy buttons and at least one rendered thumbnail. `build_pdfs.py` with no browser prints a warning and exits 0.
- **Phase 6.** `contribute.py --dry-run` on a scraped file outputs a cleaned, deduped record set with **zero** PII fields present (assert none of the dropped keys from 7.3 appear).
- **Phase 7.** `claude plugin validate .` passes. README install commands are correct and copy-pasteable.

**Global acceptance:** Grep the final `SKILL.md` and all prose templates for guessing language ("estimate", "mentally", "approximately", "I think the competition") — there must be none describing how to produce numbers without data.

---

## 16. README Requirements

Must include: one-paragraph pitch; the determinism principle (why this isn't a fluff tool); install commands (Section 12.3); the three data paths (sample / manual / live) with the honest note that the sample data is partial and dated; how to get and pass a scraper key; how to contribute and what gets stripped (link `DATA_POLICY.md`); the scoring formula and how to tune `scoring-config.json` (so users can audit it); a "no ML, no auto-scraping, no guessed numbers" statement; license note (MIT code, CC-BY-4.0 data/docs); link to the Hugging Face dataset; a short troubleshooting section (no Chrome, 429s, low-confidence pricing).

---

## 17. Compliance Notes (bake into docs, not just code)

- Fiverr has no public data API; its `robots.txt` disallows search paths; it uses anti-bot protection. The skill therefore does **not** scrape by default and never ships credentials.
- Live scraping runs only with the user's own key and is the user's responsibility under Fiverr's Terms of Service and applicable law. State this in README and `DATA_POLICY.md`.
- Only public listing metadata is ever handled or shared; all seller-identifying fields are stripped before contribution (Section 7.3).
- This is not legal advice; the project takes no position on the legality of scraping in any jurisdiction and asks users to verify their own compliance.

---

## 18. Out of Scope / Future (v2+)

- Ranking prediction or any ML model (explicitly excluded in v1).
- Auto-publishing gigs, messaging, or account automation.
- A hosted web UI or paid marketplace listing.
- Multi-currency live FX (v1 normalizes to USD at ingest).
- Auto-refreshing the bundled sample data on a schedule (v1 is manual via `seed/`).

---

## 19. Appendix — Key Facts the Implementer Should Honor

- Skills load via progressive disclosure: only `name` + `description` (~100 tokens) preload; the body loads on trigger; `scripts/`, `references/`, `assets/` load only when the instructions point to them. Keep `SKILL.md` lean.
- Reference script paths with `${CLAUDE_SKILL_DIR}/scripts/<name>.py` so they resolve wherever the skill is installed.
- Pre-approve tools with `allowed-tools: Bash(python3 *) Read Write` to avoid permission prompts mid-run.
- Authoritative references for the standard and packaging: `code.claude.com/docs/en/skills`, `platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices`, `agentskills.io/specification`, and the `anthropics/skills` + `anthropics/claude-code` (plugin-dev / skill-development) repos.
- Treat all version-specific limits (token/line caps, frontmatter fields) as current-but-mutable; prefer the documented standard fields for portability.
