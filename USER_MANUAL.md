# User Manual — fiverr-gig-optimizer

A step-by-step guide to using the skill, from install to a finished gig catalog.
For the project overview and the scoring rationale, see [`README.md`](README.md).
For exactly what data is handled, see [`DATA_POLICY.md`](DATA_POLICY.md).

---

## 1. What this skill does (in one minute)

You describe your services. The skill researches each keyword against **real
data**, scores how crowded and how in-demand it is, benchmarks competitor
**prices**, and hands you a ready-to-publish catalog: titles, tags, 3-tier
pricing, descriptions, thumbnail specs, a launch plan, and a cross-sell map —
as an HTML page with copy buttons and downloadable thumbnails.

**The rule that makes it different:** every market number (competition, demand,
price) is computed by a Python script from data you can see. The model never
guesses one. If the data isn't there, it asks you or says so.

---

## 2. Requirements

- **Claude Code** (the skill runs there).
- **Python 3.8+** on your PATH (the scripts run via `python3`).
- *Optional:* **Google Chrome or Microsoft Edge** — only if you want per-gig
  PDFs. Without it, you still get the HTML catalog.
- *Optional:* **live-scrape deps** (`curl-cffi`, `beautifulsoup4`) — only for
  Path C. The default scrape engine needs **no API key** (best from a
  residential IP; otherwise set `PROXY_URL`).
- *Optional:* an **Apify key** — only for the Path C *fallback* engine.
- *Optional:* a **Hugging Face token** — only if you contribute data back.

Install the optional Python packages only if you'll scrape or contribute:

```
pip install -r requirements.txt
```

The scoring core needs none of them.

---

## 3. Install

```
/plugin marketplace add Ahad690/fiverr-gig-optimizer
/plugin install fiverr-gig-optimizer@fiverr-tools
```

To pin a version, add a release tag or commit SHA. Verify the package locally any time with:

```
claude plugin validate .
```

---

## 4. Your first run (the free path)

1. In Claude Code, just describe what you do, e.g.:

   > help me optimize my Fiverr gigs for n8n automation and AI chatbots

   (Or run it explicitly: `/fiverr-gig-optimizer`.)

2. The skill asks **one** set of questions. Answer in a single message:
   - your name, brand (optional), website (optional)
   - your **services** (give at least 3 — it needs them to find combo niches)
   - a headshot path (optional)
   - existing gig URLs, or "none"
   - your monthly revenue goal
   - your experience level: **New / L1 / L2 / Top Rated**

3. It proposes **keyword candidates** — single services plus 2-way combos
   (e.g. "ai chatbot + n8n"). These are just search ideas; they get scored next.

4. For each candidate it looks up the bundled **sample dataset** and reports a
   line like:

   > Competition for "ai chatbot n8n": sample-data match, confidence HIGH,
   > dataset generated 2025-12 · score 82 (LOW) · demand n/a · opportunity 82

   - **Confidence** tells you how well the sample data matched your keyword.
   - If a keyword gets **no match**, the skill will **ask you to paste the
     count** Fiverr shows (see §5, Path B). It will not invent one.

5. It benchmarks pricing, assembles the catalog, and writes
   **`fiverr-catalog.html`**. Open it in a browser: each gig has a thumbnail,
   copy buttons for title/description/tags, a PNG download, and the launch plan.

That's the whole loop — no key, no setup.

---

## 5. The three data paths

You'll be steered to one of these per keyword. You can mix them.

### Path A — Sample data (default, free)
Uses the bundled `benchmarks.sample.json`. **It is partial and dated** — every
result is labeled with the dataset date and a match confidence. Best for a quick
first pass. Weak matches fall through to Path B.

### Path B — Manual counts (free, most accurate for *your* keyword)
1. Open Fiverr and search your exact keyword.
2. Read the **"X services available"** number near the results.
3. Paste that number when the skill asks.

The skill scores precisely that count. This is the most reliable free option
because the number is live and specific to your keyword.

### Path C — Live scrape (opt-in)
Pulls fresh gigs so pricing, demand, **and the real competition count** are
current. It has two engines.

**Default engine (no key, recommended).** Reads Fiverr's own page data directly
and uniquely recovers the real **"X services available" total**, writing it as
`gig_count_in_search` — the one number the sample and Apify paths can't give you.

```
python3 scripts/scrape.py --query "ai chatbot" --category "Programming & Tech" --limit 30
python3 scripts/build_benchmarks.py --input benchmarks.local.json
```

- Works from a **residential IP** (a normal home connection) with no proxy.
  On a datacenter/VPN IP, set a residential proxy first:
  `export PROXY_URL=...` (Windows: `setx PROXY_URL "..."`, new shell after).
- `--pages N` scans more search pages; `--limit N` caps how many gig pages it
  opens for pricing detail.

**Fallback engine (Apify, optional).** If the default engine is blocked and you
have Apify residential proxies, set a key and force it. Note: no Apify actor
returns the search total, so `gig_count_in_search` stays empty on this path —
use a manual count for that number.

```
export APIFY_TOKEN=your_token_here          # Windows: setx APIFY_TOKEN "..."
python3 scripts/scrape.py --query "ai chatbot" --engine apify --limit 30
```

`scrape.py` writes `benchmarks.local.json` (USD-normalized canonical rows).
`build_benchmarks.py` turns it into `pricing-pools.local.json` and
`dataset-index.local.json`. All `*.local.json` files stay on your machine
(they're git-ignored). Scraping is **your responsibility** under Fiverr's ToS —
see [`DATA_POLICY.md`](DATA_POLICY.md).

---

## 5b. Import your existing Fiverr profile (optional)

If you already sell on Fiverr, paste your profile link and the skill pre-fills
Step 1 — name, seller level, and your existing gigs **with their current
prices** — instead of making you type it all out:

```
python3 scripts/import_profile.py --url https://www.fiverr.com/<username>
```

What you get back: your display name, member-since, each existing gig's
three-tier packages (price + delivery), tags, and a list of `suggested_services`
(keyword seeds drawn from your own gig tags). The skill then benchmarks **your**
prices against the live market and can rewrite the gigs you already have.

- **Public data only.** It never logs in and cannot see private analytics
  (impressions, clicks, conversion, earnings) — you'll still be asked for your
  revenue goal.
- Same engine as Path C: works from a residential IP; set `PROXY_URL` otherwise.
- Strictly opt-in — used only when you provide the link.

---

## 6. Reading the output

Each gig in the catalog carries:

| Thing | What it means |
|---|---|
| **Competition score** (0–100) | Higher = *less* crowded = better. 82 is a low-competition keyword. |
| **Tier** | `LOW` / `MEDIUM` / `HIGH`, or `UNTESTED` when a search returns 0 gigs. |
| **Demand score** (0–100) | Proven buyer demand from competitor review volume. `n/a` when there's no competitor data — never guessed. |
| **Opportunity** | A blend of competition and demand (or competition-only, flagged, when demand is missing). |
| **Pricing** | Basic/Standard/Premium recommended from real competitor prices. New sellers get lower entry prices to win first reviews. |
| **Provenance line** | Where each number came from (sample / manual / live) and, for sample data, the match confidence. |
| **Flags** | e.g. `demand_unavailable`, `low_confidence` — read these; they tell you how much to trust a number. |

A **low-confidence** pricing flag means too few competitor samples were found;
the number is shown but treat it as a hint, not gospel — add data via Path B/C.

---

## 7. Running the scripts directly (optional)

You don't need to — the skill orchestrates them — but they're plain CLIs:

```
# Score one keyword (gig_count from your own count or a lookup)
python3 scripts/score_keyword.py --keyword "ai chatbot n8n" --gig-count 24

# Look a keyword up in the sample dataset
python3 scripts/query_dataset.py --keyword "ai chatbot n8n"

# Import your own public Fiverr profile + each gig's current prices
python3 scripts/import_profile.py --url https://www.fiverr.com/<username>

# Pull the community dataset into your local sample (validated + gated)
python3 scripts/refresh_dataset.py --dry-run

# Price a category from a per-tier price file.
# --category is a top-level key in pricing-pools.local.json, formatted
# "Category > Subcategory" exactly as it appears in your data (open the file
# to see the available keys).
python3 scripts/analyze_pricing.py --prices pricing-pools.local.json \
    --category "Programming & Tech > AI Development" --experience New

# Render a catalog you already have
python3 scripts/build_catalog.py gig-config.json --out fiverr-catalog.html

# Optional per-gig PDFs (skips cleanly if no Chrome/Edge)
python3 scripts/build_pdfs.py gig-config.json --out-dir pdfs
```

Every script prints JSON or a status line; add `--help` to any of them.

---

## 8. Tuning the scoring

All knobs live in `skills/fiverr-gig-optimizer/references/scoring-config.json`
and nothing is hidden in the model. Common edits:

- **`competition.anchors`** — reshape the competition curve.
- **`tiers.low_max` / `medium_max`** — where LOW/MEDIUM/HIGH boundaries sit.
- **`opportunity.w_competition` / `w_demand`** — rebalance the blend.
- **`opportunity.combo_bonus`** — set to `10` to reward niche combos (default 0).
- **`pricing.min_samples`** — how many competitor prices a tier needs before
  it's "high confidence" (default 8).
- **`pricing.new_seller` / `default`** — the percentiles each strategy uses.
- **`fx.rates`** — static currency table (`usd = price * rate`); update
  `rates_as_of` when you change it.

Re-run after editing — output changes deterministically.

---

## 9. Contributing data back (opt-in)

After a live scrape you can share your **anonymized** rows to grow the community
dataset.

**Contribution is OFF by default. Nothing ever leaves your machine unless you
deliberately run the command in Step 2.** There is no background upload and no
auto-share setting — the "toggle" is simply whether you run `contribute.py`
*without* `--dry-run`. Two independent on-switches must both be flipped: dropping
`--dry-run` **and** having `HF_TOKEN` set (without the token it stops and shares
nothing).

**Step 1 — preview (safe; shares nothing):**

```
python3 scripts/contribute.py --input benchmarks.local.json --dry-run
```

This prints the exact cleaned, de-duplicated rows that *would* be shared and
opens no PR. Inspect it.

**Step 2 — turn it on (actually share):**

```
export HF_TOKEN=your_hf_token               # Windows: setx HF_TOKEN "..."
python3 scripts/contribute.py --input benchmarks.local.json --contributor "Your Name"
```

This opens a pull request to the community Hugging Face dataset.

A PII guard strips every seller-identifying field (username, profile/gig URLs,
country, review text, IDs, images) before anything leaves your machine and
aborts if any slips through. You're credited in `CONTRIBUTORS.md`. Full
keep/strip list: [`DATA_POLICY.md`](DATA_POLICY.md).

---

## 9b. Refreshing from the community dataset (the read side)

Contribution sends data *up* to the shared Hugging Face dataset. This pulls it
*back down* so your local sample (Path A) keeps improving as the dataset grows:

```
python3 scripts/refresh_dataset.py --dry-run   # preview: shows what would merge
python3 scripts/refresh_dataset.py             # validate + merge clean new rows
```

It is deliberately cautious — it only uses data that is:

- **Uncorrupted** — every row is schema-checked (required fields, sane numbers,
  no PII). If a file won't parse, or too many rows are malformed
  (`--max-corrupt-ratio`, default 25%), it **refuses and leaves your file
  untouched**.
- **Sufficient** — if there aren't at least `--min-new` clean, genuinely new
  rows (after de-duplication), it does nothing.

Scoring still reads your local file afterwards, so results stay deterministic.
(The dataset is empty until contributions arrive, so today this is a clean
no-op.)

---

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| **Skill asks for a count instead of giving one** | The sample data didn't match that keyword (low/no confidence). Paste the Fiverr "X services available" count (Path B). This is by design — it won't guess. |
| **Pricing says "low confidence"** | Too few competitor prices for that tier. Add data via a manual count or a live scrape. |
| **No PDFs generated** | Chrome/Edge wasn't found. The HTML catalog is unaffected; PDFs are optional. |
| **Scrape returns nothing / "blocked" (default engine)** | The default engine needs a residential IP. From a datacenter/VPN IP, `export PROXY_URL=<residential proxy>` and retry, or use a manual count. |
| **`HTTP 429` during scrape** | You're rate-limited. Wait, then retry with a smaller `--limit` (or raise `RATE_LIMIT_DELAY`). |
| **`authentication failed` during scrape** | Only the **Apify fallback** (`--engine apify`) needs a key. Check `--api-key` or `APIFY_TOKEN`. The default engine needs no key. |
| **`no actor_id configured`** | Apify fallback only: set `scraper.actor_id` in `scoring-config.json` or pass `--actor-id`. |
| **`huggingface_hub is required`** | `pip install -r requirements.txt` before contributing. |
| **Profile import returns 0 gigs** | Usually a transient block (the script warns you). Retry; if you're not on a residential IP, set `PROXY_URL` first. |
| **Catalog opens but a thumbnail looks blank** | Make sure the gig's `img` block has `headline`/`accent`; re-run the skill if you hand-edited `gig-config.json`. |

---

## 11. FAQ

**Does it post gigs to Fiverr for me?** No. It produces copy-paste-ready content
and never touches your account.

**Will the numbers change between runs?** Not for the same input — scoring is
deterministic. They change only when your data changes.

**Can I trust the sample data prices?** Treat them as a dated starting point.
For decisions, prefer a manual count (Path B) or a fresh scrape (Path C); the
provenance line and confidence labels tell you which you're looking at.

**Is scraping legal?** That's on you to determine in your jurisdiction. The skill
never scrapes by default and ships no key. See [`DATA_POLICY.md`](DATA_POLICY.md).
