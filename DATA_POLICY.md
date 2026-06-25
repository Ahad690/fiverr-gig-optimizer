# Data Policy

This skill handles **only public Fiverr listing metadata**. It stores no private
user account data, and it never scrapes by default.

## What is handled

When you use the live scrape (opt-in, your own key) or contribute data, only
**public listing metadata** is processed. The canonical record (PRD §7.1) is:

`scraped_at, category, subcategory, title, seller_level, seller_country,
rating, review_count, basic_price, standard_price, premium_price,
basic_delivery_days, standard_delivery_days, premium_delivery_days, tags,
gig_count_in_search, currency, original_currency`.

`seller_country` is a coarse market signal (a country code) kept for regional
pricing analysis. It is *not* tied to a username, profile, or any other
identifier — those are always stripped (below) — so a row cannot be traced back
to a specific seller.

## What is kept vs stripped on contribution

Contribution is **opt-in** and defaults to nothing. When you contribute,
`contribute.py` rebuilds every row from the keep-list above and **drops** all
seller-identifying fields before anything leaves your machine:

**Dropped (hard requirement):** seller username, seller display name, profile
URL, gig URL, seller profile URL, profile photo URL, any free-text review
content, any image URLs, any ID fields.

A PII guard (`assert_no_pii`) runs before any upload and aborts if a non-keep
field is present. Use `contribute.py --dry-run` to inspect the exact cleaned,
deduplicated records first.

## License

Contributed data and all documentation are released under **CC-BY-4.0**
(`LICENSE-DATA`). Code is **MIT** (`LICENSE`). By contributing you agree to
release your anonymized rows under CC-BY-4.0. Contributors are credited in
`CONTRIBUTORS.md`.

## Live scraping is your responsibility

- Fiverr has no public data API; its `robots.txt` disallows search paths and it
  uses anti-bot protection. This skill therefore does **not** scrape by default
  and never ships credentials.
- The live scrape runs **only with your own scraper key** and is **your
  responsibility** under Fiverr's Terms of Service and applicable law in your
  jurisdiction.
- This is **not legal advice.** The project takes no position on the legality of
  scraping anywhere and asks you to verify your own compliance before scraping.

## No account data

The skill never asks for, stores, or transmits your Fiverr login, password, or
any private account information.
