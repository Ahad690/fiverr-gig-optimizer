#!/usr/bin/env python3
"""refresh_dataset.py — pull the community HF dataset into the local sample.

Closes the contribution loop on the READ side: downloads the public Hugging Face
dataset, validates every row, and merges only clean, new rows into the local
benchmarks file. Scoring still reads a local, versioned file afterwards — so
determinism is preserved; the file just gets richer over time.

SAFETY GATES (the "only use it if sufficient and uncorrupted" rule):
  - Uncorrupted: every row is schema-validated (required keys, number-or-null
    numerics, sane ranges, no PII fields). A file that won't parse, or a corrupt
    fraction above --max-corrupt-ratio, ABORTS the merge (local file untouched).
  - Sufficient: after validation + dedup, fewer than --min-new genuinely new
    rows is a no-op (nothing merged), not an error.

Public dataset → no token needed to read.

CLI:
    refresh_dataset.py [--repo <hf-url-or-id>] [--dataset <local.json>] \
        [--dry-run] [--min-new 1] [--max-corrupt-ratio 0.25] [--config path.json]

Exit codes: 0 merged or clean no-op; 2 corrupted source (refused);
1 usage/network/IO error.
"""
import argparse
import json
import os
import sys

# Reuse the canonical keep-list, PII guard, and dedup hash from contribute.py.
import contribute

REQUIRED = contribute.KEEP                 # canonical fields (§7.1)
FORBIDDEN = contribute.FORBIDDEN           # must never appear
NUMERIC = {
    "rating", "review_count", "basic_price", "standard_price", "premium_price",
    "basic_delivery_days", "standard_delivery_days", "premium_delivery_days",
    "gig_count_in_search",
}


def default_config_path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "references", "scoring-config.json")


def load_config(path=None):
    with open(path or default_config_path(), encoding="utf-8") as fh:
        return json.load(fh)


def default_dataset_path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "references", "benchmarks.sample.json")


def repo_id_from(repo):
    return repo.rstrip("/").split("datasets/")[-1]


# --------------------------------------------------------------------------
# Pure validation/gating logic (unit-testable, no network).
# --------------------------------------------------------------------------

def validate_row(row):
    """Return (ok, reason). Enforces schema, ranges, and the no-PII rule."""
    if not isinstance(row, dict):
        return False, "not an object"
    for bad in FORBIDDEN:
        if bad in row:
            return False, f"PII field present: {bad}"
    if not (isinstance(row.get("title"), str) and row["title"].strip()):
        return False, "missing title"
    if not (isinstance(row.get("category"), str) and row["category"].strip()):
        return False, "missing category"
    for k in NUMERIC:
        v = row.get(k)
        if v is not None and not isinstance(v, (int, float)):
            return False, f"{k} not number-or-null"
        if isinstance(v, (int, float)) and v < 0:
            return False, f"{k} negative"
    r = row.get("rating")
    if isinstance(r, (int, float)) and not (0 <= r <= 5):
        return False, "rating out of range"
    tags = row.get("tags")
    if tags is not None and not isinstance(tags, list):
        return False, "tags not a list"
    return True, "ok"


def partition_rows(rows):
    """Split into (valid_canonicalized, invalid_reasons)."""
    valid, invalid = [], []
    for row in rows:
        ok, reason = validate_row(row)
        if ok:
            valid.append(contribute.strip_pii(row))  # rebuild from keep-list only
        else:
            invalid.append(reason)
    return valid, invalid


def decide(seen, invalid_count, new_after_dedup, min_new, max_corrupt_ratio,
           file_errors):
    """Gate decision. Returns {action, status, reason}."""
    if file_errors:
        return {"action": "abort", "status": "corrupt",
                "reason": f"{file_errors} dataset file(s) failed to parse"}
    if seen == 0:
        return {"action": "noop", "status": "empty",
                "reason": "no rows found in the dataset (nothing to pull yet)"}
    corrupt_ratio = invalid_count / seen
    if corrupt_ratio > max_corrupt_ratio:
        return {"action": "abort", "status": "corrupt",
                "reason": f"corrupt fraction {corrupt_ratio:.0%} exceeds "
                          f"{max_corrupt_ratio:.0%} ({invalid_count}/{seen} rows)"}
    if new_after_dedup < min_new:
        return {"action": "noop", "status": "insufficient",
                "reason": f"only {new_after_dedup} new valid row(s); "
                          f"need >= {min_new}"}
    return {"action": "merge", "status": "ok",
            "reason": f"{new_after_dedup} new valid row(s) ready to merge"}


# --------------------------------------------------------------------------
# Network (lazy import) + orchestration.
# --------------------------------------------------------------------------

def fetch_dataset_rows(repo_id):
    """Download all .json data files from the HF dataset. Returns (rows, file_errors)."""
    try:
        from huggingface_hub import HfApi, hf_hub_download
    except ImportError:
        print("error: huggingface_hub required (pip install -r requirements.txt).",
              file=sys.stderr)
        sys.exit(1)

    api = HfApi()
    try:
        files = api.list_repo_files(repo_id=repo_id, repo_type="dataset")
    except Exception as exc:  # network/auth/not-found
        print(f"error: could not list dataset '{repo_id}': {exc}", file=sys.stderr)
        sys.exit(1)

    data_files = [f for f in files if f.endswith(".json")
                  and os.path.basename(f) not in ("dataset_infos.json",)]
    rows, file_errors = [], 0
    for fname in data_files:
        try:
            local = hf_hub_download(repo_id=repo_id, filename=fname, repo_type="dataset")
            with open(local, encoding="utf-8") as fh:
                payload = json.load(fh)
        except (json.JSONDecodeError, OSError, Exception) as exc:  # noqa: BLE001
            print(f"warning: failed to read '{fname}': {exc}", file=sys.stderr)
            file_errors += 1
            continue
        if isinstance(payload, list):
            rows.extend(payload)
        elif isinstance(payload, dict) and isinstance(payload.get("rows"), list):
            rows.extend(payload["rows"])
        elif isinstance(payload, dict):
            rows.append(payload)
    return rows, file_errors


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pull + validate + merge the community HF dataset.")
    ap.add_argument("--repo", help="HF dataset URL or id (default: config dataset_repo).")
    ap.add_argument("--dataset", help="Local benchmarks file to merge into.")
    ap.add_argument("--dry-run", action="store_true", help="Report only; do not write.")
    ap.add_argument("--min-new", type=int, default=1, help="Min new valid rows to merge.")
    ap.add_argument("--max-corrupt-ratio", type=float, default=0.25,
                    help="Abort if more than this fraction of rows are invalid.")
    ap.add_argument("--config", help="Path to scoring-config.json.")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    repo = args.repo or cfg.get("dataset_repo", "")
    if not repo or "<" in repo:
        print("error: no dataset_repo configured. Set it in scoring-config.json "
              "or pass --repo.", file=sys.stderr)
        return 1
    repo_id = repo_id_from(repo)
    local_path = args.dataset or default_dataset_path()

    with open(local_path, encoding="utf-8") as fh:
        local_rows = json.load(fh)
    local_hashes = {contribute.row_hash(contribute.strip_pii(r)) for r in local_rows}

    print(f"Pulling dataset '{repo_id}' ...", file=sys.stderr)
    pulled, file_errors = fetch_dataset_rows(repo_id)
    valid, invalid = partition_rows(pulled)

    # Dedup valid rows against local + within the pulled set.
    seen = set(local_hashes)
    new_rows = []
    for r in valid:
        h = contribute.row_hash(r)
        if h in seen:
            continue
        seen.add(h)
        new_rows.append(r)

    verdict = decide(len(pulled), len(invalid), len(new_rows),
                     args.min_new, args.max_corrupt_ratio, file_errors)

    report = {
        "repo": repo_id,
        "pulled_rows": len(pulled),
        "valid_rows": len(valid),
        "invalid_rows": len(invalid),
        "new_after_dedup": len(new_rows),
        "local_rows_before": len(local_rows),
        "status": verdict["status"],
        "action": verdict["action"],
        "reason": verdict["reason"],
        "dry_run": args.dry_run,
    }

    if verdict["action"] == "abort":
        report["merged"] = 0
        print(json.dumps(report, indent=2))
        return 2  # refused: corrupted source
    if verdict["action"] in ("noop",) or args.dry_run:
        report["merged"] = 0
        if args.dry_run and verdict["action"] == "merge":
            report["would_merge"] = len(new_rows)
        print(json.dumps(report, indent=2))
        return 0

    # Merge. Purely additive (all local rows kept, clean new rows appended) and
    # written atomically so a crash mid-write can't corrupt the local file.
    combined = local_rows + new_rows
    import local_data
    local_data.write_json_atomic(local_path, combined)
    report["merged"] = len(new_rows)
    report["local_rows_after"] = len(combined)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
