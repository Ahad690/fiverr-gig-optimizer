# Vendored third-party code

## fiverr_perseus_scraper.py

- **Upstream:** [KyuRish/fiverr-mcp-server](https://github.com/KyuRish/fiverr-mcp-server),
  file `src/fiverr_mcp_server/utils/scraper.py`, version v0.1.1 (2026-02-23).
- **License:** MIT — full text in [`LICENSE`](LICENSE) (Copyright (c) 2026 KyuRish).
- **Why vendored:** it is the only tool we found that exposes Fiverr's search
  total (`rawListingData.num_found`), which we map to `gig_count_in_search` —
  the field no Apify actor returns. It parses the `perseus-initial-props` SSR
  blob using `curl_cffi` browser-TLS impersonation.
- **Modifications:** none to the logic — only a provenance header was prepended.
  All schema mapping into our canonical record, and the delivery-units fix
  (Fiverr's package `duration` is in **hours**; we divide by 24 to get days),
  live in `../scrape.py`, keeping this file easy to diff against upstream.

To update: re-copy `scraper.py` from a newer upstream tag, re-add the header,
and re-run `tests/test_scrape_mapping.py`.
