#!/usr/bin/env python3
"""contribute.py — opt-in, anonymized dataset contribution. FR17.

Strips PII to the §7.3 keep-list, deduplicates (hash on title|category), and
opens a pull request to the community Hugging Face dataset. Contribution is
opt-in and defaults to nothing destructive: use --dry-run to preview the exact
cleaned + deduped records without opening a PR.

PII guarantee: output rows are rebuilt from the KEEP list only, so no dropped
field can leak — even if the scrape added unexpected columns.

CLI:
    contribute.py --input benchmarks.local.json --dry-run
    contribute.py --input benchmarks.local.json --contributor "name" \
        [--existing existing.json] [--token HF_TOKEN] [--config path.json]
"""
import argparse
import hashlib
import json
import os
import sys

# §7.3 — the ONLY fields that may ever leave the user's machine.
KEEP = [
    "scraped_at", "category", "subcategory", "title", "seller_level",
    "rating", "review_count", "basic_price", "standard_price", "premium_price",
    "basic_delivery_days", "standard_delivery_days", "premium_delivery_days",
    "tags", "gig_count_in_search", "currency", "original_currency",
]
# §7.3 — must NEVER appear in output (asserted before any upload).
FORBIDDEN = [
    "seller_username", "seller_name", "seller_display_name", "profile_url",
    "gig_url", "seller_url", "profile_photo_url", "freelancers_link",
    "seller_country", "review_text", "reviews", "image_url", "image_urls",
    "id", "gig_id", "seller_id",
]


def default_config_path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "references", "scoring-config.json")


def load_config(path=None):
    with open(path or default_config_path(), encoding="utf-8") as fh:
        return json.load(fh)


def strip_pii(row):
    """Rebuild a row from the keep-list only. Missing keep fields -> null."""
    return {k: row.get(k, None) for k in KEEP}


def row_hash(row):
    title = (row.get("title") or "").strip().lower()
    category = (row.get("category") or "").strip().lower()
    return hashlib.sha256(f"{title}|{category}".encode("utf-8")).hexdigest()


def clean_and_dedup(rows, existing_hashes):
    seen = set(existing_hashes)
    out = []
    for row in rows:
        clean = strip_pii(row)
        if not clean.get("title"):
            continue
        h = row_hash(clean)
        if h in seen:
            continue
        seen.add(h)
        out.append(clean)
    return out


def assert_no_pii(rows):
    for row in rows:
        for key in row:
            if key not in KEEP:
                raise AssertionError(f"PII guard failed: unexpected field '{key}'")
        for bad in FORBIDDEN:
            if bad in row:
                raise AssertionError(f"PII guard failed: forbidden field '{bad}'")


def append_contributor(name):
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.abspath(os.path.join(here, "..", "..", "..", "CONTRIBUTORS.md"))
    line = f"- {name}\n"
    try:
        with open(path, encoding="utf-8") as fh:
            if line in fh.read():
                return
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError as exc:
        print(f"warning: could not update CONTRIBUTORS.md: {exc}", file=sys.stderr)


def open_hf_pr(rows, repo, token, contributor):
    """Upload cleaned rows and open a dataset PR. Requires huggingface_hub."""
    try:
        from huggingface_hub import HfApi, CommitOperationAdd
    except ImportError:
        print("error: huggingface_hub is required to open a PR "
              "(pip install huggingface_hub).", file=sys.stderr)
        sys.exit(1)

    repo_id = repo.rstrip("/").split("datasets/")[-1]
    payload = json.dumps(rows, ensure_ascii=False, indent=2).encode("utf-8")
    fname = f"contributions/{contributor.replace(' ', '_')}.json"
    api = HfApi(token=token)
    commit = api.create_commit(
        repo_id=repo_id,
        repo_type="dataset",
        operations=[CommitOperationAdd(path_in_repo=fname, path_or_fileobj=payload)],
        commit_message=f"Add anonymized contribution from {contributor}",
        create_pr=True,
    )
    return getattr(commit, "pr_url", None) or str(commit)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Opt-in anonymized dataset contribution.")
    ap.add_argument("--input", required=True, help="Scraped benchmarks.local.json.")
    ap.add_argument("--existing", help="Existing dataset JSON, for cross-file dedup.")
    ap.add_argument("--contributor", default="anonymous")
    ap.add_argument("--token", help="Hugging Face token (or set HF_TOKEN).")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print cleaned + deduped records; open no PR.")
    ap.add_argument("--config", help="Path to scoring-config.json.")
    args = ap.parse_args(argv)

    with open(args.input, encoding="utf-8") as fh:
        rows = json.load(fh)

    existing_hashes = set()
    if args.existing:
        with open(args.existing, encoding="utf-8") as fh:
            for r in json.load(fh):
                existing_hashes.add(row_hash(strip_pii(r)))

    cleaned = clean_and_dedup(rows, existing_hashes)
    assert_no_pii(cleaned)  # hard guard before anything leaves the machine

    if args.dry_run:
        print(json.dumps({
            "dry_run": True,
            "input_rows": len(rows),
            "contributable_rows": len(cleaned),
            "pii_fields_present": 0,
            "records": cleaned,
        }, indent=2, ensure_ascii=False))
        return 0

    if not cleaned:
        print("Nothing new to contribute (all rows were duplicates or empty).")
        return 0

    cfg = load_config(args.config)
    token = args.token or os.environ.get("HF_TOKEN")
    if not token:
        print("error: no Hugging Face token. Pass --token or set HF_TOKEN.",
              file=sys.stderr)
        return 1

    pr_url = open_hf_pr(cleaned, cfg["dataset_repo"], token, args.contributor)
    append_contributor(args.contributor)
    print(f"Opened dataset PR with {len(cleaned)} rows: {pr_url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
