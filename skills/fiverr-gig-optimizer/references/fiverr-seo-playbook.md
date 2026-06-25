# Fiverr SEO Playbook

Loaded only when generating gig copy (FR11/FR12). All competition, demand, and
price numbers come from the scoring scripts — nothing in this file authorizes
guessing a market figure. This file governs **copy and presentation** only.

---

## 1. Title rules (hard constraints — enforced)

- Must start with **"I will"**.
- **≤ 80 characters** total.
- Front-load the **primary keyword** (the scored keyword/combo) as early as
  possible after "I will".
- Lowercase except proper nouns/tools (Fiverr renders titles in its own case).
- One clear deliverable per title. No pipes, no ALL CAPS, no emojis.
- Avoid superlatives Fiverr discourages ("best", "cheapest", "#1").

**Good:** `I will build a custom ai chatbot with openai for your website`
**Bad:** `I will do EVERYTHING ai related — chatbots, logos & more!!!`

## 2. Tags (hard constraint)

- **Exactly 5 tags.**
- Lowercase, 1–2 words each, no punctuation.
- Tag 1 = the primary keyword. Tags 2–5 = the strongest matching tokens from
  the scored keyword/combo and its tool stack.
- No duplicates; no tag that merely repeats the category name.

## 3. Description rules (hard constraints)

- **≤ 1200 characters.**
- **Primary keyword appears in the first paragraph.**
- Structure: hook → what you deliver → why you → packages note → soft CTA.
- Plain, scannable. Short paragraphs or a tight bullet list. No invented stats,
  no "industry-leading" filler, no fake guarantees.

## 4. Packages (offer design — LLM-authored, kept realistic)

Prices come from `analyze_pricing.py` (never invented). Delivery days, revision
counts, and the bullet list of included items are the **seller's own choices**
(§7.6) — author them from the user's stated capabilities and keep them coherent:

- Basic < Standard < Premium on price, scope, delivery time, and revisions.
- Delivery should rise with scope (e.g. 3 → 6 → 10 days), revisions likewise.
- Each tier lists 3–6 concrete, checkable deliverables.

## 5. Phase rollout (FR13)

- **Phase 1** — 3–4 gigs in the lowest-competition combo niches (highest
  opportunity_score). These get the account its first reviews.
- **Phase 2** — 2–3 premium upsells, launched after ~5+ reviews exist.
- **Phase 3** — 1–2 expansions into adjacent niches.
- Every gig lists **2–3 cross-sell targets** (other gig ids) in `xsell`.

## 6. Thumbnail palette (8 accent colors)

Assign each gig a **unique** accent from this palette (cycle by gig id so no two
adjacent gigs repeat). `bg1`/`bg2` are the dark gradient stops; `accent` is the
highlight.

| # | Name        | accent    | bg1       | bg2       |
|---|-------------|-----------|-----------|-----------|
| 1 | Cyan        | `#06b6d4` | `#030a0a` | `#061818` |
| 2 | Violet      | `#8b5cf6` | `#0a0612` | `#160a22` |
| 3 | Emerald     | `#10b981` | `#03100b` | `#062016` |
| 4 | Amber       | `#f59e0b` | `#120c03` | `#221806` |
| 5 | Rose        | `#f43f5e` | `#120308` | `#220610` |
| 6 | Blue        | `#3b82f6` | `#03080f` | `#06101f` |
| 7 | Lime        | `#84cc16` | `#0a0f03` | `#141f06` |
| 8 | Fuchsia     | `#d946ef` | `#0f0312` | `#1f0622` |

## 7. Thumbnail copy (`img` block)

- `headline` — 1–3 words, ALL CAPS, the core offer (e.g. `AI CHATBOT`).
- `sub` — one short benefit line (≤ ~32 chars).
- `badge` — the competition tier label from the score (`LOW COMPETITION`,
  `MEDIUM COMPETITION`, `HIGH COMPETITION`, or `UNTESTED NICHE`). This is a
  **computed** label — copy it verbatim from the score output.
- `tools` — 2–4 tool/tech names actually used (e.g. `OpenAI`, `LangChain`, `n8n`).
- `pdfWhat` — one-line plain-English summary for the optional PDF.
