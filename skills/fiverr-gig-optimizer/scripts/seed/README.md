# Seed: building `benchmarks.sample.json`

The bundled sample dataset is compiled by merging public Kaggle Fiverr gig
datasets into the canonical schema (PRD §7.1) with `merge_kaggle.py`.

**The sample data is partial and dated.** Every output that uses it labels its
`scraped_at`/coverage and a match confidence. It is never presented as live.

## Sources

Add the datasets you merged here, with their date and license. Examples of the
kind of public datasets used (verify each dataset's own license before
redistributing rows):

| Source (Kaggle slug)              | Approx. date | Coverage                | License (verify) |
|-----------------------------------|--------------|-------------------------|------------------|
| `<owner>/fiverr-data-gigs`        | 2024-xx      | mixed categories        | check on Kaggle  |
| `<owner>/fiverr-gigs`             | 2024-xx      | data-science gigs       | check on Kaggle  |

Set each row's `scraped_at` to its source dataset's collection date.

## Regenerate

1. Download the raw CSVs.
2. Write a field-mapping JSON per CSV (canonical field -> source column), e.g.:

   ```json
   {
     "_defaults": { "category": "Programming & Tech", "scraped_at": "2024-06-01", "currency": "USD" },
     "title": "gig_title",
     "subcategory": "sub_category",
     "rating": "seller_rating",
     "review_count": "num_reviews",
     "basic_price": "price_basic",
     "standard_price": "price_standard",
     "premium_price": "price_premium",
     "tags": "search_tags",
     "gig_count_in_search": "results_count"
   }
   ```

3. Run:

   ```bash
   python3 merge_kaggle.py \
     --input raw/gigs1.csv --map maps/gigs1.json \
     --input raw/gigs2.csv --map maps/gigs2.json \
     --out ../../references/benchmarks.sample.json
   ```

4. Validate the output against the canonical schema (every row has the §7.1
   keys; numerics are number-or-null). The committed
   `references/benchmarks.sample.json` is a small, hand-verified set you can
   replace with a fuller merge.

## Notes

- Prices are normalized to USD using the static `fx` table in
  `scoring-config.json` (`usd = price * rates[original_currency]`). If a source
  reports a non-USD currency, set `original_currency` and convert before commit.
- Missing numeric fields stay `null` — never zero-filled or guessed.
