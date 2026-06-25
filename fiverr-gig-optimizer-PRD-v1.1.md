# PRD — Fiverr Gig Optimizer (Claude Code Skill)

**Version:** 1.1 (supersedes 1.0)
**Status:** Ready to build
**Type:** Open-source Claude Code Skill + community dataset
**Target runtime:** Claude Code (Skills standard, agentskills.io). Portable to other agents that support the standard.

---

## Changelog (v1.0 → v1.1)

This revision resolves a gap analysis. Each item below is now authoritative; where it conflicts with anything later in the doc, this changelog and the updated section win.

**Hard contradictions fixed**
- **C1 — Scoring curve recalibrated and example/test corrected.** The v1.0 log formula scored gig_count=24 at ~65 but the example/test claimed 88, and the curve mis-mapped tiers (LOW boundary scored ~42). The formula is the source of truth; it has been **replaced** with a piecewise-linear-on-log10 curve (§8.2) anchored so tiers read intuitively. gig_count=24 now scores **82**; §8.7 and §15 updated to match. `gig_count=0` is a flagged special case, not a top score.
- **C2 — `benchmarks.local.json` single writer.** `scrape.py` is the only writer of `benchmarks.local.json` (raw canonical rows). `build_benchmarks.py` consumes it and writes **different** outputs: `pricing-pools.local.json` and `dataset-index.local.json` (§7.4, §11).
- **C3 — Dual license files.** Repo ships `LICENSE` (MIT, code) **and** `LICENSE-DATA` (CC-BY-4.0, data + docs). §11, §16.

**Missing specs added**
- **M1 — Keyword/combo generation defined** as an explicit LLM step (§6.2a / FR6a). Candidates are not measurements, so LLM generation is permitted.
- **M2 — Path A lookup defined.** New `query_dataset.py` derives `gig_count` + `top_gigs` from the dataset by keyword match, with a `match_confidence`; low/no match → skill asks the user, never fabricates (§6.2 FR3, §8A).
- **M3 — `analyze_pricing.py` per-tier semantics specified:** percentiles are computed **within each tier's own distribution**, with a defined percentile method (§8.6).
- **M4 — Schemas added** for `scoring-config.json` (§8.8) and `categories.json` (§7.5).
- **M5 — Field provenance defined** (§7.6): which gig fields come from scripts vs the LLM. The determinism rule is scoped to **market measurements**, not the seller's own offer design.
- **M6 — USD FX source defined:** a static `fx` table in `scoring-config.json` with an as-of date (§7.1, §8.8). "No live FX" (§18) stands.
- **M7 — `contribute.py` dependency declared:** `huggingface_hub` (§13).
- **M8 — `--dry-run` documented** for `contribute.py` (FR17, §14 Phase 6, §8C).

**Underspecified items resolved**
- **R1 — KPIs / success metrics added** (§5a) as explicit, if soft, targets.
- **R2 — Phase 0 and Phase 2 acceptance checks added** (§15).
- **R3 — Edge cases defined:** gig_count=0 and 1≤n<min_samples (§8.2, §8.6).
- **R4 — `seller_level` ↔ experience mapping defined** (§7.7); user-stated experience drives the new-seller pricing flag.
- **R5 — Tier thresholds have one home:** `scoring-config.json`. `keyword-tiers.json` is **removed** (§11).

---

## 0. How to use this document with Claude Code

This PRD is written to be **one-shot implementable**. To build:

1. Create an empty directory and `git init`.
2. Save this file as `PRD.md` in the root.
3. In Claude Code, run:
   > Read `PRD.md` in full, including the Changelog. Build the entire project following Section 14 (Build Order) top to bottom. Create every file in Section 11 (Repo Structure). Do not skip the scripts. After each phase, run that phase's acceptance check from Section 15 before continuing. Use only the deterministic scoring in Section 8 — never invent competition, demand, or competitor-price numbers anywhere in the skill's instructions or output. When market data is missing, ask the user or state that it isn't available.

**North-star rule:** every figure the skill reports about **market conditions** — competition counts, demand, competitor prices — must come from a Python script operating on real input data. The LLM layer never estimates these. (Offer-design fields like delivery days and package contents are the seller's own choices and may be LLM-generated; see §7.6.) If market data is missing, the skill asks the user for it or says it doesn't have it.

---

## 1. Overview

### 1.1 What we are building
A Claude Code Skill named `fiverr-gig-optimizer` that turns a freelancer's list of services into an optimized, research-backed Fiverr gig catalog: titles, tags, 3-tier pricing, descriptions, thumbnail specs, a phase-based launch plan, and a cross-sell map. All quantitative **market** recommendations come from deterministic Python scripts — not model guesses.

### 1.2 Why it exists
- **Fluff skills.** Existing "Fiverr optimizer" repos tell the model to "mentally estimate" competition and prices. That output is hallucinated and unstable. This project replaces guesses with computed values.
- **No good free data.** No comprehensive, current, all-category Fiverr dataset is freely available. Public Kaggle datasets are stale and niche. This project ships a sample dataset, lets users optionally pull fresh data with their own scraper key, and grows a shared community dataset via opt-in contributions.

### 1.3 Distribution model
- Open-source on GitHub. **Code: MIT (`LICENSE`). Data + docs: CC-BY-4.0 (`LICENSE-DATA`).**
- Installable as a Claude Code **plugin** via `marketplace.json`.
- Companion **community dataset** on the Hugging Face Datasets Hub, grown via opt-in pull requests.

---

## 2. Goals and Non-Goals

### 2.1 Goals
- G1. Produce a complete, copy-paste-ready Fiverr gig catalog from a user's services.
- G2. Base every market figure (competition/demand/pricing) on real data via deterministic scripts.
- G3. Work out-of-the-box for free using a bundled sample dataset (zero API key required) — **including a defined keyword→data lookup (§8A).**
- G4. Optionally fetch fresh, category-specific data using the user's own scraper API key.
- G5. Optionally let users contribute anonymized data back to a shared public dataset.
- G6. Ship as a clean, properly packaged, installable open-source Claude Code plugin.

### 2.2 Non-Goals (explicit)
- N1. **No machine learning.** No training, model files, embeddings, or ranking prediction. Scoring is rule-based and auditable.
- N2. **No scraping by default.** Live scraping is opt-in, runs only with the user's own key, and is the user's responsibility.
- N3. **No guessed market numbers.** No fallback to model-estimated competition counts or prices.
- N4. Not a Fiverr account automation tool (no posting, refreshing, or messaging bots).
- N5. Not a paid product; no payment layer in v1.

---

## 3. Design Principles / Constraints

- **P1 — Determinism over generation, for market data.** Sorting, parsing, scoring, statistics, validation, dedup, and all **market measurements** live in Python scripts. The model never produces competition/demand/competitor-price numbers. (Offer-design fields are exempt; §7.6.)
- **P2 — Progressive disclosure.** `SKILL.md` stays lean (target < 400 lines). Detail lives in `references/` and loads only when needed. Scripts are executed, not read into context.
- **P3 — Honest about data.** With no key and no user-supplied counts, the skill uses the sample dataset via `query_dataset.py` and clearly labels coverage, age, and **match confidence**. It never presents an approximate or stale number as live.
- **P4 — Privacy by default.** Contributions strip all seller-identifying fields (§7.3).
- **P5 — Portability.** Prefer standard Skills frontmatter fields; keep Claude-Code-specific fields optional.
- **P6 — No heavy deps unless justified.** Stdlib first. `requests` for HTTP; `huggingface_hub` for contribution; `pandas` only where it meaningfully simplifies CSV work. HTML/PDF output reuses headless Chrome.

---

## 4. Target Users

- **U1 — New Fiverr seller** with skills but no gigs. Free path (sample data).
- **U2 — Existing seller** optimizing/expanding. May provide Analytics export and/or a scraper key.
- **U3 — Agency / power user** scraping multiple categories, willing to contribute data back.
- **U4 — Contributor / developer** improving the skill or dataset.

---

## 5. User Stories

- US1. As U1, I describe my services and get 3–4 launch gigs with titles, tags, pricing, and thumbnail specs.
- US2. As any user, competition labels reflect the real number of gigs for a keyword.
- US3. As any user, pricing tiers are benchmarked against real competitor prices.
- US4. As U2, I paste the "X services available" count and the skill scores it — no guessing.
- US5. As U2/U3, I provide my own scraper key and the skill pulls fresh data for my categories.
- US6. As U3, I opt in to contribute anonymized data; I'm credited.
- US7. As any user, I get a single HTML catalog with copy buttons and downloadable thumbnails, plus optional per-gig PDFs.
- US8. As U4, `DATA_POLICY.md` tells me exactly what is collected and stripped.

## 5a. Success Metrics / KPIs (soft targets for a personal + OSS tool)

- K1 — **Provenance coverage: 100%.** Every market number in any output carries a source label (sample / manual / live) and, for sample data, a match confidence. Verified by the §15 global grep + output inspection.
- K2 — **Determinism: 0 guessed market numbers.** No prose/template in the skill describes producing competition or price figures without data (enforced in §15).
- K3 — **Output lint pass ≥ 90%.** Of generated gigs, ≥90% satisfy: title starts "I will", ≤80 chars, exactly 5 tags, description ≤1200 chars. A `lint_gig_config.py` check (optional) or manual spot-check confirms.
- K4 — **Dataset growth (aspirational):** community dataset reaches a documented row/category milestone over time via contributions (tracked in the HF repo, not enforced by the build).

---

## 6. Functional Requirements

### 6.1 Information gathering (SKILL.md, Step 1)
- FR1. Ask, in one numbered message: name; brand (optional); website (optional); services list; headshot path (optional); existing gig URLs or "none"; monthly revenue goal; experience level (New / L1 / L2 / Top Rated).
- FR2. If fewer than 3 services are given, prompt for more (needed for combo-niche analysis).

### 6.2a Keyword & combo candidate generation (LLM step) — **NEW**
- FR6a. From the services list, the model proposes a candidate set of (a) single-service keywords and (b) 2-way combos (e.g. "n8n + AI chatbot"), following naming guidance in `fiverr-seo-playbook.md`. These are **search candidates, not measurements**, so LLM generation is allowed. The candidate list is then scored using real data (§6.2/§6.3). Combos with 3+ services are allowed when the playbook deems them coherent.

### 6.2 Data acquisition (one of three paths)
- FR3. **Path A — Sample data (default, free).** For each candidate keyword, run `query_dataset.py` against `references/benchmarks.sample.json` (and `dataset-index.local.json` if present) to obtain `gig_count`, `top_gigs`, and `match_confidence` (§8A). On low/no match, the skill asks the user to paste a count (Path B) — it never fabricates one. State coverage, the dataset's `generated_at`, and match confidence in output.
- FR4. **Path B — Manual counts.** For each keyword, ask the user to paste the count Fiverr shows ("X services available"). Never fabricate this number.
- FR5. **Path C — Live scrape (opt-in).** With the user's scraper key + actor ID, `scrape.py` pulls gigs for the target categories into `benchmarks.local.json` (raw canonical rows). `build_benchmarks.py` then derives `pricing-pools.local.json` and `dataset-index.local.json` from it.
- FR6. The chosen path and freshness are surfaced in output (e.g. "Competition for 'x': sample-data match, confidence MEDIUM, dataset generated 2025-12; pricing: live scrape 2026-06-25").

### 6.3 Competition + opportunity scoring (deterministic)
- FR7. `score_keyword.py` computes competition/demand/opportunity scores and a tier label per keyword using only supplied data and `scoring-config.json` (§8).
- FR8. The skill surfaces the script's JSON fields verbatim. No relabeling or invented numbers.

### 6.4 Pricing analysis (deterministic)
- FR9. `analyze_pricing.py` takes competitor prices for a category and returns p10/p25/median/p75/p90 **per tier** and a recommended Basic/Standard/Premium triple (§8.6).
- FR10. If a tier has fewer than `min_samples` (default 8) prices, the script returns `confidence: "low"` for that tier and recommends nothing numeric for it.

### 6.5 Gig catalog generation
- FR11. The skill assembles `gig-config.json` (§7.2) from: computed competition tiers/scores, computed pricing, SEO rules (`fiverr-seo-playbook.md`), and the taxonomy (`categories.json`).
- FR12. Title rules: starts with "I will", ≤80 chars, primary keyword front-loaded. Exactly 5 tags. Description ≤1200 chars, primary keyword in first paragraph. Unique thumbnail accent per gig from the palette.
- FR13. Phase rollout: Phase 1 = 3–4 lowest-competition combos; Phase 2 = 2–3 premium upsells; Phase 3 = 1–2 expansions. Each gig lists 2–3 cross-sell targets.

### 6.6 Output rendering
- FR14. `build_catalog.py` reads `gig-config.json` and writes a self-contained `fiverr-catalog.html` (canvas thumbnails 1280×769, copy buttons, per-gig PNG download, cross-sell map, action plan). **No scoring inside.**
- FR15. `build_pdfs.py` optionally renders one A4 PDF per gig via headless Chrome; skipped gracefully if no Chrome/Edge (warn, don't fail).

### 6.7 Contribution (opt-in)
- FR16. After a live scrape, ask whether to contribute the anonymized data. Default no; never pressure.
- FR17. `contribute.py` strips PII (§7.3), deduplicates against the dataset, and opens a Hugging Face PR; the user is added to `CONTRIBUTORS.md`. Supports `--dry-run` (prints cleaned + deduped records, opens no PR).

### 6.8 Invocation
- FR18. Model-invocable (auto-triggers on Fiverr phrasing) and runnable as `/fiverr-gig-optimizer`.

---

## 7. Data Schemas

### 7.1 Canonical gig record
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
  "currency": "USD",
  "original_currency": "USD"
}
```
Prices are normalized to USD at ingest using the static `fx` table in `scoring-config.json` (§8.8); `original_currency` records the pre-conversion currency. Missing numerics are `null`, never zero-filled or guessed. `gig_count_in_search` is the "X services available" total for the search that produced the row.

### 7.2 `gig-config.json` (input to renderers)
```json
{
  "seller": { "name": "", "brand": "", "website": "", "photo": "" },
  "data_provenance": {
    "pricing_source": "sample_dataset|manual|live_scrape",
    "pricing_generated_at": "2026-06-25",
    "competition_source": "sample_dataset|manual|live_scrape",
    "match_confidence": "HIGH|MEDIUM|LOW|null"
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
      "competition": { "count": 24, "tier": "LOW", "source": "manual", "match_confidence": null },
      "scores": { "competition": 82, "demand": null, "opportunity": 82, "flags": ["demand_unavailable"] },
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
The renderer treats `competition`, `scores`, and `pricing` as authoritative precomputed inputs and performs **no** scoring.

### 7.3 PII stripping (contribution)
**Keep:** `scraped_at, category, subcategory, title, seller_level, rating, review_count, basic_price, standard_price, premium_price, basic_delivery_days, standard_delivery_days, premium_delivery_days, tags, gig_count_in_search, currency, original_currency`.
**Drop before contributing (hard requirement):** seller username, seller display name, profile URL, gig URL, profile photo URL, seller country, any free-text review content, any image URLs, any ID fields.

### 7.4 Local working files (provenance — resolves C2)
- `benchmarks.local.json` — **written only by `scrape.py`.** Raw canonical gig rows (§7.1) from a live scrape.
- `pricing-pools.local.json` — **written by `build_benchmarks.py`.** Per-category, per-tier price lists consumed by `analyze_pricing.py`. Shape: `{ "<category/subcategory>": { "basic": [..], "standard": [..], "premium": [..] } }`.
- `dataset-index.local.json` — **written by `build_benchmarks.py`.** A keyword/tag → `{gig_count, row_ids}` index that `query_dataset.py` can use for faster/fresher Path-A lookups. Optional; `query_dataset.py` falls back to scanning `benchmarks.sample.json` if absent.
All three match `*.local.json` in `.gitignore` and are never committed.

### 7.5 `categories.json` schema (resolves M4)
Nested object: category → subcategory → list of leaf subcategories.
```json
{
  "Programming & Tech": {
    "AI Development": ["AI Chatbots", "AI Agents", "AI Applications"],
    "Website Development": ["Business Websites", "E-Commerce Development", "Landing Pages"]
  },
  "Digital Marketing": {
    "Search": ["SEO", "Local SEO"],
    "Social": ["Social Media Marketing", "Paid Social"]
  }
}
```
v1 may ship top categories + key subcategories and expand later. Used for FR11 categorization and to validate the `cat` field.

### 7.6 Field provenance (resolves M5)
The determinism rule (P1) applies to **market measurements only**. Provenance per `gig-config.json` field:

| Field group | Source | Why |
|---|---|---|
| `competition.count`, `.tier`, `scores.*` | **Script** (`score_keyword.py` / `query_dataset.py`) | Market measurement |
| `pricing.*.price` | **Script** (`analyze_pricing.py`) | Market measurement (competitor prices) |
| `pricing.*.del` (delivery), `.rev` (revisions), `.items` | **LLM**, from the user's stated capabilities + playbook conventions | Seller's own offer design, not a market measurement |
| `title`, `desc`, `tags` | **LLM**, following playbook + `categories.json` | Copy, constrained by lint rules (FR12) |
| `img.*` (headline, sub, badge, tools, accent, pdfWhat) | **LLM**, palette from playbook | Presentation |
| `data_provenance.*` | **Script/orchestration** | Truthful labeling |

Delivery days and revisions are numbers but are **choices, not observations**, so LLM generation does not violate P1. The skill must still keep them realistic and consistent with the user's stated turnaround.

### 7.7 `seller_level` ↔ experience mapping (resolves R4)
```
New        <-> new_seller
L1         <-> level_one_seller
L2         <-> level_two_seller
Top Rated  <-> top_rated_seller
```
The **user's stated experience** drives the new-seller pricing flag (§8.6), not scraped seller levels. Scraped `seller_level` is used only as demand/quality context.

---

## 8. Scoring Specification (deterministic — the core)

All constants live in `references/scoring-config.json` (schema §8.8) so they are transparent and tunable. Defaults below.

### 8A. Path-A dataset lookup — `query_dataset.py` (resolves M2/G3)
**Purpose:** derive a `gig_count` and `top_gigs` for a keyword from the sample/local dataset so the free path can feed `score_keyword.py`.

**CLI:** `query_dataset.py --keyword "ai chatbot n8n" [--dataset references/benchmarks.sample.json] [--index dataset-index.local.json] [--top-n 10]`

**Matching logic (deterministic):**
1. Normalize keyword and each row's `tags`, `title`, `subcategory` to lowercase token sets.
2. For each row, compute a match score = max(Jaccard(keyword_tokens, tag_tokens), subcategory-contains-keyword ? 1.0 : 0, title-token-overlap ratio).
3. A row "matches" if match score ≥ `lookup.match_threshold` (default 0.5).
4. `gig_count` = the `gig_count_in_search` of the best-matching search cluster (mode of matched rows' `gig_count_in_search`; if they disagree, take the median). `top_gigs` = matched rows sorted by `review_count` desc, truncated to `top_n`.
5. `match_confidence`: HIGH if best match score ≥ 0.8 and ≥ `lookup.min_rows` (default 5) rows matched; MEDIUM if ≥ threshold; LOW if below threshold or fewer than `min_rows`.

**Output:**
```json
{ "keyword":"ai chatbot n8n", "gig_count": 1243, "match_confidence":"MEDIUM",
  "matched_rows": 7, "top_gigs":[ /* canonical rows */ ], "source":"sample_dataset" }
```
If `match_confidence == "LOW"` or no rows match → return `gig_count: null` with `flags:["no_match"]`; the skill then asks the user for a manual count (Path B). **No fabrication.**

### 8.1 Inputs to `score_keyword.py`
- `gig_count` — integer total gigs for the keyword (from `query_dataset.py`, manual paste, or scrape). Required for competition scoring.
- Optional `top_gigs` — competitor records for demand. Absent → `demand_score = null` (not guessed); opportunity falls back to competition-only with a flag.

### 8.2 Competition score (0–100, higher = less competition = better) — **recalibrated (resolves C1, R3)**
Piecewise-linear interpolation over `log10(gig_count)`, anchored to the tier structure. Anchors `(gig_count → score)`: `(1 → 100), (200 → 70), (2000 → 40), (20000 → 0)`, clamped to [0, 100].

```python
import math
def competition_score(gig_count, anchors):  # anchors = [[1,100],[200,70],[2000,40],[20000,0]]
    if gig_count == 0:
        return None  # special case: no results -> see flags below, not a top score
    x = math.log10(max(gig_count, 1))
    pts = [(math.log10(c), s) for c, s in anchors]
    if x <= pts[0][0]:  return round(pts[0][1])
    if x >= pts[-1][0]: return round(pts[-1][1])
    for (x0, s0), (x1, s1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            t = (x - x0) / (x1 - x0)
            return round(s0 + t * (s1 - s0))
```
Worked values: `gig_count=24 → 82`; `200 → 70`; `2000 → 40`; `10000 → 12`. (24: log10≈1.380, t=1.380/2.301=0.600, 100−0.600×30=82.)

**Edge case `gig_count == 0`:** `competition_score = null`, add flag `"no_results"`, and set `tier = "UNTESTED"`. Opportunity for an untested niche is `null` with flag `"untested_niche"` (no demand evidence either way) — not a perfect score.

Tier from `gig_count` (thresholds in `scoring-config.json`):
```
UNTESTED: gig_count == 0
LOW:      0 < gig_count < 200
MEDIUM:   200 <= gig_count < 2000
HIGH:     gig_count >= 2000
```

### 8.3 Demand score (0–100, higher = more proven buyer demand)
Proxy = median `review_count` of the top N (default 10) competitor gigs.
```
DEMAND_CEILING = 500
demand_score = round(clamp((median_top_reviews / DEMAND_CEILING) * 100, 0, 100))
```
If `top_gigs` unavailable → `demand_score = null`.

### 8.4 Opportunity score (0–100)
```
if tier == "UNTESTED":            opportunity = null; flag "untested_niche"
elif demand_score is not null:    opportunity = round(0.6*competition_score + 0.4*demand_score)
else:                             opportunity = competition_score; flag "demand_unavailable"
```
Weights live in config; rationale documented in README so users can audit/adjust.

### 8.5 Combo-niche bonus (optional, default OFF)
If a keyword is a 2+ word combo with `gig_count` below the LOW threshold, add `combo_bonus` (default 0; opt-in +10) to `opportunity`, capped at 100. Off by default to keep scores literal.

### 8.6 Pricing recommendation (resolves M3, R3)
**Per-tier semantics:** percentiles are computed **within each tier's own price distribution** — p25 of the *basic* prices, median of the *standard* prices, p75 of the *premium* prices — not from a merged pool.

**Percentile method (defined):**
```python
def percentile(values, p):  # p in [0,100]
    s = sorted(values)
    if len(s) == 1: return s[0]
    # statistics.quantiles inclusive, n=100, then index by p (1..99); clamp ends
    import statistics
    if p <= 0:   return s[0]
    if p >= 100: return s[-1]
    q = statistics.quantiles(s, n=100, method="inclusive")  # 99 cut points
    return q[p-1]
```
Recommendation:
```
default:
  basic    = percentile(basic_prices, 25)
  standard = percentile(standard_prices, 50)
  premium  = percentile(premium_prices, 75)

new-seller strategy (user experience == "New"):
  basic    = percentile(basic_prices, 10)
  standard = percentile(standard_prices, 25)
  premium  = percentile(premium_prices, 50)
```
**Confidence:** computed per tier. If a tier has `n < min_samples` (default 8) → that tier returns `{"confidence":"low","reason":"insufficient samples (n=<k>)"}` and recommends nothing numeric for it. If `1 <= n < min_samples`, still report the raw percentile **but flag low confidence**; if `n == 0`, recommend nothing for that tier.

### 8.7 Output contract — `score_keyword.py` (corrected example, resolves C1)
```json
{
  "keyword": "ai chatbot n8n",
  "gig_count": 24,
  "competition_score": 82,
  "tier": "LOW",
  "demand_score": null,
  "opportunity_score": 82,
  "flags": ["demand_unavailable"]
}
```
The skill surfaces these fields verbatim.

### 8.8 `scoring-config.json` schema (resolves M4, M6, R5)
```json
{
  "competition": {
    "anchors": [[1, 100], [200, 70], [2000, 40], [20000, 0]]
  },
  "tiers": { "low_max": 200, "medium_max": 2000 },
  "demand": { "ceiling": 500, "top_n": 10 },
  "opportunity": { "w_competition": 0.6, "w_demand": 0.4, "combo_bonus": 0 },
  "pricing": {
    "min_samples": 8,
    "default":    { "basic_p": 25, "standard_p": 50, "premium_p": 75 },
    "new_seller": { "basic_p": 10, "standard_p": 25, "premium_p": 50 }
  },
  "lookup": { "match_threshold": 0.5, "min_rows": 5, "top_n": 10 },
  "scraper": { "base_url": "https://api.apify.com/v2", "actor_id": "<actor-id-here>" },
  "dataset_repo": "https://huggingface.co/datasets/<owner>/fiverr-gigs",
  "fx": {
    "base": "USD",
    "rates_as_of": "2026-06-01",
    "rates": { "USD": 1.0, "EUR": 1.08, "GBP": 1.27, "INR": 0.012, "PKR": 0.0036 }
  }
}
```
Tier thresholds live **only** here (no separate `keyword-tiers.json`). FX is a **static** table with an explicit `rates_as_of`; `scrape.py` converts non-USD prices to USD on ingest by dividing/multiplying via this table. (§18 "no live FX" stands.)

---

## 9. Data Sources and Policy

- **Seed (`benchmarks.sample.json`).** Built by merging the maintainer's public Kaggle Fiverr datasets into the canonical schema (§7.1), with `scraped_at`/`generated_at` set to each source's date. `scripts/seed/merge_kaggle.py` + `seed/README.md` document the merge and dates. Coverage is partial and dated — labeled as such everywhere it's used.
- **Live (`scrape.py`).** Uses an Apify-compatible scraping API with the **user's own key** and a configurable `actor_id`. Costs are the user's. The skill never ships a key and never scrapes without one.
- **Community dataset (Hugging Face).** Public, CC-BY-4.0, grown via opt-in PRs from `contribute.py`. Repo path set in `scoring-config.json → dataset_repo`.
- **`DATA_POLICY.md`** must state: only public Fiverr listing data is handled; exact keep/strip fields (§7.3); contribution is opt-in and CC-BY-4.0; live scraping is the user's responsibility under Fiverr's ToS; no private account data is stored.

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
  version: "1.1"
license: MIT
---
```
Constraints: `name` ≤64 chars, lowercase/numbers/hyphens only; `description` ≤1024 chars; no XML tags; no reserved words ("anthropic", "claude").

### 10.2 Body structure (in order)
1. `## Overview` — one paragraph; restate the determinism-for-market-data rule.
2. `## When to use` — trigger phrases.
3. `## Hard rules` — never invent competition/demand/competitor-price numbers; always run the scoring scripts; on missing market data, ask or say "I don't have that"; offer-design fields (delivery, revisions, items) may be authored but kept realistic; strip PII before any contribution.
4. `## Workflow` — Steps 1–7 mapping to FR1–FR17, each naming the exact script via `python3 ${CLAUDE_SKILL_DIR}/scripts/<name>.py ...` and the reference file to read. **Include the keyword-generation step (FR6a) and the Path-A `query_dataset.py` step (FR3).**
5. `## Output format` — present scores verbatim from JSON; always include a provenance line; where files are written.
6. `## Error handling` — no key → offer manual/sample paths; low match confidence → ask for a manual count; insufficient pricing samples → low-confidence flag; no Chrome → skip PDFs with a warning.
7. `## Examples` — (a) a full run on sample data with a MEDIUM-confidence match; (b) a run where `query_dataset.py` returns `no_match` and the skill **asks** for a count instead of guessing.

Keep the body < 400 lines. Push the full SEO ruleset and color palette into `references/fiverr-seo-playbook.md`.

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
│       │   ├── score_keyword.py        # §8.2–8.5, output §8.7
│       │   ├── query_dataset.py        # §8A  (Path A lookup) — NEW
│       │   ├── analyze_pricing.py      # §8.6
│       │   ├── scrape.py               # FR5; writes benchmarks.local.json only
│       │   ├── build_benchmarks.py     # writes pricing-pools.local.json + dataset-index.local.json
│       │   ├── contribute.py           # FR17 (+ --dry-run); PII strip + dedup + HF PR
│       │   ├── build_catalog.py        # FR14 (HTML; no scoring)
│       │   ├── build_pdfs.py           # FR15 (headless Chrome; optional)
│       │   └── seed/
│       │       ├── merge_kaggle.py
│       │       └── README.md
│       ├── references/
│       │   ├── benchmarks.sample.json  # bundled seed (canonical schema)
│       │   ├── scoring-config.json     # §8.8 — sole home for thresholds + fx + config
│       │   ├── categories.json         # §7.5
│       │   └── fiverr-seo-playbook.md  # title/tag/desc rules + 8-color palette
│       └── assets/
│           └── pdf-template.html
├── tests/
│   ├── test_score_keyword.py
│   ├── test_query_dataset.py           # NEW
│   └── test_analyze_pricing.py
├── examples/
│   └── sample-gig-config.json
├── DATA_POLICY.md
├── CONTRIBUTORS.md
├── LICENSE                              # MIT (code)
├── LICENSE-DATA                         # CC-BY-4.0 (data + docs) — NEW
├── requirements.txt
├── .gitignore                           # *.local.json, .env, __pycache__
└── README.md
```
(`keyword-tiers.json` removed — thresholds live in `scoring-config.json`.)

---

## 12. Plugin Packaging

### 12.1 `plugin.json`
```json
{
  "name": "fiverr-gig-optimizer",
  "version": "1.1.0",
  "description": "Research-backed Fiverr gig optimizer. Deterministic competition + pricing scoring, no ML, no guessed market numbers.",
  "author": { "name": "<maintainer>" },
  "license": "MIT",
  "keywords": ["fiverr", "freelance", "gig", "pricing", "seo", "claude-code", "skill"]
}
```

### 12.2 `.claude-plugin/marketplace.json`
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
Rules: kebab-case names; `name` must NOT be a reserved Anthropic marketplace name (`claude-code-plugins`, `anthropic-plugins`, `agent-skills`). Show pinning by tag/SHA in docs. Validate with `claude plugin validate .`.

### 12.3 Install instructions (README)
```
/plugin marketplace add <github-username>/fiverr-gig-optimizer
/plugin install fiverr-gig-optimizer@fiverr-tools
```

---

## 13. Dependencies (resolves M7)

- **Python 3.8+.** Stdlib: `json, csv, statistics, math, hashlib, argparse, urllib, os, sys, datetime`.
- **Third-party:** `requests>=2.31` (HTTP for scrape); `huggingface_hub>=0.23` (contribution PRs); `pandas>=2.0` **only** inside `seed/merge_kaggle.py` / `build_benchmarks.py` if it simplifies CSV merging (else stdlib `csv`).
- **Optional runtime:** Google Chrome or Microsoft Edge for `build_pdfs.py` (auto-detect; skip if absent).
- **Scraper:** Apify-compatible token via `--api-key` or `APIFY_TOKEN`; `actor_id` from `scoring-config.json`.
- **Contribution:** Hugging Face token (contributors only).
- Create `requirements.txt` listing exactly: `requests>=2.31`, `huggingface_hub>=0.23`, and `pandas>=2.0` if used.

---

## 14. Build Order (top to bottom)

**Phase 0 — Scaffold.** Repo tree (§11); `LICENSE` (MIT); `LICENSE-DATA` (CC-BY-4.0); `.gitignore`; empty `CONTRIBUTORS.md`; `requirements.txt`.

**Phase 1 — Scoring core.**
1. `references/scoring-config.json` (§8.8).
2. `score_keyword.py` (§8.2–8.5; output §8.7). CLI: `--keyword "x" --gig-count N [--top-gigs path.json]`.
3. `analyze_pricing.py` (§8.6). CLI: `--prices path.json --experience New`.
4. `query_dataset.py` (§8A). CLI: `--keyword "x" [--dataset ...] [--index ...] [--top-n 10]`.
5. Tests: `test_score_keyword.py`, `test_query_dataset.py`, `test_analyze_pricing.py` — assert exact outputs (e.g. gig_count=24 → competition_score=82, tier=LOW).

**Phase 2 — Reference data.**
6. `categories.json` (§7.5).
7. `fiverr-seo-playbook.md` (rules + 8-color palette).
8. `seed/merge_kaggle.py` + `seed/README.md`; produce `benchmarks.sample.json` (a few real, schema-valid rows acceptable for first build; document regeneration).

**Phase 3 — Skill definition.**
9. `SKILL.md` (§10) wiring Steps 1–7 to scripts/references, including FR6a and the Path-A step.
10. `examples/sample-gig-config.json` (§7.2).

**Phase 4 — Data acquisition (opt-in).**
11. `scrape.py` — call the configured actor with the user's key; map results to canonical schema (§7.1), convert currencies via `fx`; write `benchmarks.local.json`. Handle 429/auth with clear messages.
12. `build_benchmarks.py` — from `benchmarks.local.json` (or a user CSV) write `pricing-pools.local.json` + `dataset-index.local.json`.

**Phase 5 — Output rendering.**
13. `build_catalog.py` — `gig-config.json` → `fiverr-catalog.html` (no scoring).
14. `build_pdfs.py` — optional per-gig A4 PDFs via headless Chrome; skip gracefully.

**Phase 6 — Contribution.**
15. `contribute.py` — PII strip (§7.3), dedup (hash on `title|category`), HF PR; append contributor to `CONTRIBUTORS.md`; support `--dry-run`.
16. `DATA_POLICY.md` (§9).

**Phase 7 — Packaging + docs.**
17. `.claude-plugin/plugin.json` + `marketplace.json` (§12); run `claude plugin validate .`.
18. `README.md` (§16).

---

## 15. Acceptance Criteria (per phase)

- **Phase 0 — NEW.** Repo tree matches §11; `claude` loads in the directory with no error; both `LICENSE` and `LICENSE-DATA` exist; `requirements.txt` present.
- **Phase 1.** `score_keyword.py --keyword "ai chatbot n8n" --gig-count 24` → `competition_score: 82, tier: "LOW", demand_score: null, opportunity_score: 82`. `--gig-count 0` → `competition_score: null, tier: "UNTESTED", opportunity_score: null, flags:["no_results","untested_niche"]`. `analyze_pricing.py` on a 12-price tier returns p25/median/p75; on a 5-price tier returns `confidence:"low"` for that tier. `query_dataset.py` on a keyword present in the sample returns a `gig_count` + `match_confidence`; on a nonsense keyword returns `gig_count:null, flags:["no_match"]`. All three test files pass.
- **Phase 2 — NEW checks added.** `benchmarks.sample.json` validates against the canonical schema (every row has the required keys; numerics are number-or-null); `categories.json` parses as the §7.5 shape; `scoring-config.json` parses and contains all keys in §8.8.
- **Phase 3.** Installed locally, "help me optimize my Fiverr gigs for n8n automation" auto-triggers the skill; `/fiverr-gig-optimizer` also works. With no key, the skill runs `query_dataset.py`; on `no_match` it **asks for a count** and states no competition number it wasn't given. `claude --debug` shows no YAML error; `/doctor` shows the description not truncated/dropped.
- **Phase 4.** With a valid key, `scrape.py` writes ≥1 valid canonical row (USD-normalized, `original_currency` set); with an invalid key it prints a clear auth error and exits non-zero (no crash, no fabricated data). `build_benchmarks.py` produces both `pricing-pools.local.json` and `dataset-index.local.json`.
- **Phase 5.** `build_catalog.py` on `examples/sample-gig-config.json` produces one HTML file that opens with working copy buttons and ≥1 rendered thumbnail. `build_pdfs.py` with no browser warns and exits 0.
- **Phase 6.** `contribute.py --dry-run` on a scraped file outputs cleaned, deduped records with **zero** PII fields (assert none of the §7.3 drop-keys appear).
- **Phase 7.** `claude plugin validate .` passes; README install commands are correct and copy-pasteable.

**Global acceptance.** Grep the final `SKILL.md` and all prose templates for market-guessing language ("estimate", "mentally", "approximately", "I think the competition") — there must be none describing how to produce **market** numbers without data. (Offer-design language about delivery/revisions is fine.)

---

## 16. README Requirements

Include: one-paragraph pitch; the determinism principle scoped to market data (why this isn't a fluff tool); install commands (§12.3); the three data paths (sample/manual/live) with the honest note that sample data is partial, dated, and surfaced with a match confidence; how to get and pass a scraper key; how to contribute and what gets stripped (link `DATA_POLICY.md`); the scoring formula (anchors, weights) and how to tune `scoring-config.json`; a "no ML, no auto-scraping, no guessed market numbers" statement; **license split — code MIT (`LICENSE`), data + docs CC-BY-4.0 (`LICENSE-DATA`)**; link to the Hugging Face dataset; troubleshooting (no Chrome, 429s, low-confidence pricing, low match confidence).

---

## 17. Compliance Notes (in docs, not just code)

- Fiverr has no public data API; its `robots.txt` disallows search paths; it uses anti-bot protection. The skill does **not** scrape by default and never ships credentials.
- Live scraping runs only with the user's own key and is the user's responsibility under Fiverr's ToS and applicable law. State this in README and `DATA_POLICY.md`.
- Only public listing metadata is handled or shared; all seller-identifying fields are stripped before contribution (§7.3).
- This is not legal advice; the project takes no position on the legality of scraping in any jurisdiction and asks users to verify their own compliance.

---

## 18. Out of Scope / Future (v2+)

- Ranking prediction or any ML model (excluded in v1).
- Auto-publishing gigs, messaging, or account automation.
- A hosted web UI or paid marketplace listing.
- **Live FX.** v1 uses the static `fx` table (§8.8) with a documented `rates_as_of`; live currency conversion is out of scope.
- Auto-refreshing the bundled sample data on a schedule (v1 is manual via `seed/`).

---

## 19. Appendix — Key Facts the Implementer Should Honor

- Skills load via progressive disclosure: only `name` + `description` (~100 tokens) preload; the body loads on trigger; `scripts/`, `references/`, `assets/` load only when pointed to. Keep `SKILL.md` lean.
- Reference scripts as `${CLAUDE_SKILL_DIR}/scripts/<name>.py` so paths resolve wherever installed.
- Pre-approve tools with `allowed-tools: Bash(python3 *) Read Write`.
- Every script emits JSON to stdout; the skill surfaces market fields verbatim.
- Authoritative references: `code.claude.com/docs/en/skills`, `platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices`, `agentskills.io/specification`, and the `anthropics/skills` + `anthropics/claude-code` (plugin-dev / skill-development) repos.
- Treat version-specific limits (token/line caps, frontmatter fields) as current-but-mutable; prefer documented standard fields for portability.
