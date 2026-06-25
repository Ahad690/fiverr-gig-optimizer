# fiverr-gig-optimizer

A Claude Code skill that turns your list of services into an optimized,
research-backed Fiverr gig catalog — titles, tags, 3-tier pricing,
descriptions, thumbnail specs, a phase-based launch plan, and a cross-sell map.
**Every market number it reports — competition, demand, competitor prices —
comes from a deterministic Python script operating on real data. It never
guesses.**

## Why this isn't a fluff tool

Most "Fiverr optimizer" prompts tell the model to *mentally estimate* how many
competitors a keyword has and what to charge. That output is hallucinated and
changes every run. Here, the LLM never produces a market figure. Competition,
demand, and pricing are computed by auditable scripts (`score_keyword.py`,
`query_dataset.py`, `analyze_pricing.py`) from data you can see. If the data
isn't there, the skill asks you or says it doesn't have it.

Offer-design choices (delivery days, revisions, what's in each package) *are*
authored by the model — those are your decisions, not market measurements.

## Install

```
/plugin marketplace add Ahad690/fiverr-gig-optimizer
/plugin install fiverr-gig-optimizer@fiverr-tools
```

For reproducible installs, pin to a release tag or commit SHA. Validate locally
with `claude plugin validate .`.

## The three data paths

1. **Sample data (default, free).** Ships with `benchmarks.sample.json` and a
   deterministic keyword lookup (`query_dataset.py`). **The sample data is
   partial and dated** — every result is labeled with its dataset date and a
   match confidence (HIGH / MEDIUM / LOW). On a weak match the skill asks you
   for a count instead of inventing one.
2. **Manual counts.** Open Fiverr, search your keyword, paste the
   "X services available" count. The skill scores exactly that number.
3. **Live scrape (opt-in, your key).** Provide an Apify-compatible token and
   actor id; `scrape.py` pulls fresh gigs for your categories, then
   `build_benchmarks.py` builds the pricing pools and lookup index.

### Getting and passing a scraper key

The skill never ships a key. Supply your own via `--api-key` or the
`APIFY_TOKEN` environment variable, and set `scraper.actor_id` in
`scoring-config.json` (or pass `--actor-id`). Scraping costs are yours.

## Scoring (auditable, tunable)

All constants live in `references/scoring-config.json`.

- **Competition score (0–100, higher = less competition).** Piecewise-linear
  over `log10(gig_count)`, anchored `(1→100), (200→70), (2000→40), (20000→0)`.
  Example: `gig_count=24 → 82` (LOW). `gig_count=0 → UNTESTED` (not a top score).
- **Demand score.** Median review count of the top competitors, normalized to a
  ceiling. `null` when no competitor data is available — never guessed.
- **Opportunity.** `0.6·competition + 0.4·demand` (competition-only, flagged,
  when demand is unavailable).
- **Pricing.** Per-tier percentiles of real competitor prices: Basic = p25,
  Standard = median, Premium = p75 (new sellers shift lower to win first
  reviews). Tiers with too few samples are flagged low-confidence.

Edit the anchors, weights, thresholds, and FX table to retune — nothing is
hidden in the model.

## Contributing data

Contribution is **opt-in** and anonymized. `contribute.py` strips all
seller-identifying fields to the keep-list, deduplicates, and opens a pull
request to the community Hugging Face dataset; you're credited in
`CONTRIBUTORS.md`. Preview exactly what would be shared with
`contribute.py --input <file> --dry-run`. See [`DATA_POLICY.md`](DATA_POLICY.md)
for the full keep/strip list.

## No ML, no auto-scraping, no guessed numbers

- No machine learning, training, or ranking prediction — scoring is rule-based.
- No scraping by default; live scraping is opt-in and uses your own key.
- No model-estimated competition counts or prices, anywhere.

## License

- **Code:** MIT — [`LICENSE`](LICENSE).
- **Data + docs:** CC-BY-4.0 — [`LICENSE-DATA`](LICENSE-DATA).
- Community dataset (CC-BY-4.0): set in `scoring-config.json → dataset_repo`
  (`https://huggingface.co/datasets/Ahad690/fiverr-gigs`).

## Troubleshooting

- **No Chrome/Edge:** `build_pdfs.py` warns and exits 0; the HTML catalog still
  renders. PDFs are optional.
- **Scrape returns nothing / "blocked":** the primary engine relies on TLS
  impersonation. It works from a residential IP; from a datacenter/VPN IP set
  `PROXY_URL` to a residential proxy, or configure the Apify fallback (with a key).
- **HTTP 429 on scrape:** you're rate-limited — wait and retry, or lower
  `--limit` (the engine already throttles ~2s/request; raise `RATE_LIMIT_DELAY`).
- **Low-confidence pricing:** a tier had fewer than `min_samples` prices; the
  number is shown but flagged. Add data (manual or scrape) to firm it up.
- **Low match confidence / no match:** the sample dataset doesn't cover your
  keyword well; paste the Fiverr count (Path B) so the skill can score it.

## Development

```
python -m unittest discover -s tests -p "test_*.py" -v
```

Project layout, scoring spec, and build order live in
`fiverr-gig-optimizer-PRD-v1.1.md`.
