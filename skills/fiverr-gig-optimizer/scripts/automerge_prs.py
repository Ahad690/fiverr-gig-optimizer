#!/usr/bin/env python3
"""automerge_prs.py — auto-merge clean contribution PRs to the HF dataset.

Lists open pull requests on the community dataset and merges only the ones that
are safe under deterministic checks; anything else is commented and left open
for a human.

A PR is auto-merged ONLY when ALL hold:
  1. It removes no files and modifies no existing file (purely additive).
  2. Every added file is `contributions/*.json`.
  3. Total added rows <= --max-rows (anti-flood).
  4. Every row passes schema + range + PII validation, and the corrupt fraction
     is <= --max-corrupt-ratio.
Otherwise the bot comments the reason and leaves the PR open (human review).

IMPORTANT: schema validation proves rows are well-formed and PII-free, NOT that
the numbers are authentic. Auto-merge trades human review for scale; the dataset
is versioned, so any bad merge is revertible. Tune the gates to your risk
tolerance, or run with --dry-run in CI and merge manually.

CLI:
    automerge_prs.py [--repo <hf-url-or-id>] [--dry-run] [--max-rows 2000] \
        [--max-corrupt-ratio 0.0] [--token TOKEN] [--config path.json]

Needs a write token (--token, HF_TOKEN, or a cached `hf auth login`).
Exit: 0 always unless a usage/setup error (1).
"""
import argparse
import json
import os
import statistics
import sys

import contribute       # row_hash, strip_pii
import refresh_dataset as rd  # validate_row, partition_rows

TIER_PRICE = ("basic_price", "standard_price", "premium_price")


def default_config_path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "references", "scoring-config.json")


def load_config(path=None):
    with open(path or default_config_path(), encoding="utf-8") as fh:
        return json.load(fh)


def repo_id_from(repo):
    return repo.rstrip("/").split("datasets/")[-1]


# --------------------------------------------------------------------------
# Pure decision logic (unit-testable).
# --------------------------------------------------------------------------

def additive_only(added, removed, modified):
    """Safe shape: only new contributions/*.json files, nothing else touched."""
    if removed:
        return False, f"removes {len(removed)} file(s)"
    if modified:
        return False, f"modifies {len(modified)} existing file(s)"
    if not added:
        return False, "no added files"
    bad = [f for f in added
           if not (f.startswith("contributions/") and f.endswith(".json"))]
    if bad:
        return False, f"adds non-contribution file(s): {bad[:3]}"
    return True, "additive contributions only"


def reference_medians(rows):
    """{category -> median basic_price} from a reference dataset (e.g. local sample)."""
    by_cat = {}
    for r in rows:
        cat, price = r.get("category"), r.get("basic_price")
        if cat and isinstance(price, (int, float)):
            by_cat.setdefault(cat, []).append(price)
    return {c: statistics.median(v) for c, v in by_cat.items() if v}


def abuse_scan(rows, reference_rows, acfg):
    """Stateless anti-abuse heuristics. Returns a list of reasons ([] = clean).

    Schema validation already covers PII / types / negatives / ranges. These
    catch *suspicious-but-well-formed* submissions and route them to a human:
      - absurd absolute values (price/review/gig-count ceilings)
      - too many price-ordering violations (basic<=standard<=premium)
      - duplicate flooding (low unique ratio)
      - per-category median price that is a wild outlier vs the reference data
    """
    reasons = []
    if not rows:
        return reasons

    max_price = acfg.get("max_price", 50000)
    max_reviews = acfg.get("max_review_count", 1_000_000)
    max_gig = acfg.get("max_gig_count", 5_000_000)

    # Absolute ceilings.
    for r in rows:
        for k in TIER_PRICE:
            v = r.get(k)
            if isinstance(v, (int, float)) and v > max_price:
                reasons.append(f"price {k}={v} exceeds ceiling {max_price}")
                break
        rc, gc = r.get("review_count"), r.get("gig_count_in_search")
        if isinstance(rc, (int, float)) and rc > max_reviews:
            reasons.append(f"review_count {rc} exceeds ceiling {max_reviews}")
        if isinstance(gc, (int, float)) and gc > max_gig:
            reasons.append(f"gig_count_in_search {gc} exceeds ceiling {max_gig}")

    # Price-ordering violations (basic <= standard <= premium where present).
    viol = 0
    for r in rows:
        b, s, p = (r.get("basic_price"), r.get("standard_price"), r.get("premium_price"))
        seq = [x for x in (b, s, p) if isinstance(x, (int, float))]
        if len(seq) >= 2 and any(a > c for a, c in zip(seq, seq[1:])):
            viol += 1
    if rows and viol / len(rows) > acfg.get("ordering_violation_max_ratio", 0.3):
        reasons.append(f"{viol}/{len(rows)} rows violate basic<=standard<=premium")

    # Duplicate flooding.
    if len(rows) >= 5:
        uniq = len({contribute.row_hash(contribute.strip_pii(r)) for r in rows})
        ratio = uniq / len(rows)
        if ratio < acfg.get("min_unique_ratio", 0.5):
            reasons.append(f"only {uniq}/{len(rows)} unique rows (duplicate flooding)")

    # Per-category price-median outlier vs reference distribution.
    ref = reference_medians(reference_rows or [])
    factor = acfg.get("outlier_factor", 10)
    min_rows = acfg.get("outlier_min_rows", 3)
    pr_by_cat = {}
    for r in rows:
        if isinstance(r.get("basic_price"), (int, float)) and r.get("category"):
            pr_by_cat.setdefault(r["category"], []).append(r["basic_price"])
    for cat, prices in pr_by_cat.items():
        if cat in ref and ref[cat] > 0 and len(prices) >= min_rows:
            med = statistics.median(prices)
            r = med / ref[cat]
            if r > factor or r < 1 / factor:
                reasons.append(f"category '{cat}' median ${med:.0f} is {r:.1f}x the "
                               f"reference ${ref[cat]:.0f} (outlier)")
    return reasons


def pr_verdict(added, removed, modified, rows, invalid_count, valid_new,
               file_errors, max_rows, max_corrupt_ratio, abuse_reasons=None):
    """Return {action: merge|hold, status, reason}."""
    ok, why = additive_only(added, removed, modified)
    if not ok:
        return {"action": "hold", "status": "unsafe_shape", "reason": why}
    if max_rows and rows > max_rows:
        return {"action": "hold", "status": "too_large",
                "reason": f"{rows} rows > max {max_rows}"}
    gate = rd.decide(rows, invalid_count, valid_new, min_new=1,
                     max_corrupt_ratio=max_corrupt_ratio, file_errors=file_errors)
    if gate["action"] != "merge":
        # corrupt / empty / insufficient all -> hold for a human
        return {"action": "hold", "status": gate["status"], "reason": gate["reason"]}
    if abuse_reasons:
        return {"action": "hold", "status": "suspicious",
                "reason": "; ".join(abuse_reasons)}
    return {"action": "merge", "status": "ok",
            "reason": f"{valid_new} clean new row(s); validated"}


# --------------------------------------------------------------------------
# HF interaction.
# --------------------------------------------------------------------------

def _siblings_map(api, repo_id, revision):
    info = api.repo_info(repo_id=repo_id, repo_type="dataset",
                         revision=revision, files_metadata=True)
    return {s.rfilename: getattr(s, "blob_id", None) for s in info.siblings}


def diff_files(api, repo_id, pr_num):
    """Return (added, removed, modified) filename lists for the PR."""
    main = _siblings_map(api, repo_id, "main")
    pr = _siblings_map(api, repo_id, f"refs/pr/{pr_num}")
    added = [f for f in pr if f not in main]
    removed = [f for f in main if f not in pr]
    modified = [f for f in pr if f in main
                and main[f] is not None and pr[f] is not None and main[f] != pr[f]]
    return added, removed, modified


def load_pr_rows(api, repo_id, pr_num, files):
    from huggingface_hub import hf_hub_download
    rows, errs = [], 0
    for fname in files:
        try:
            local = hf_hub_download(repo_id=repo_id, filename=fname,
                                    repo_type="dataset", revision=f"refs/pr/{pr_num}")
            with open(local, encoding="utf-8") as fh:
                payload = json.load(fh)
        except Exception as exc:  # noqa: BLE001
            print(f"warning: PR #{pr_num} file '{fname}' unreadable: {exc}", file=sys.stderr)
            errs += 1
            continue
        if isinstance(payload, list):
            rows.extend(payload)
        elif isinstance(payload, dict) and isinstance(payload.get("rows"), list):
            rows.extend(payload["rows"])
        elif isinstance(payload, dict):
            rows.append(payload)
    return rows, errs


def dedup_count(valid_rows):
    seen, n = set(), 0
    for r in valid_rows:
        h = contribute.row_hash(r)
        if h not in seen:
            seen.add(h)
            n += 1
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description="Auto-merge clean contribution PRs to the HF dataset.")
    ap.add_argument("--repo", help="HF dataset URL or id (default: config dataset_repo).")
    ap.add_argument("--dry-run", action="store_true", help="Decide only; merge nothing.")
    ap.add_argument("--max-rows", type=int, default=None,
                    help="Hold PRs larger than this (default: config automerge.max_rows_per_pr).")
    ap.add_argument("--max-corrupt-ratio", type=float, default=0.0,
                    help="Allowed invalid fraction (default 0: any invalid row -> hold).")
    ap.add_argument("--token", help="HF write token (or HF_TOKEN, or cached login).")
    ap.add_argument("--config")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    repo = args.repo or cfg.get("dataset_repo", "")
    if not repo or "<" in repo:
        print("error: no dataset_repo configured (set it or pass --repo).", file=sys.stderr)
        return 1
    repo_id = repo_id_from(repo)
    token = args.token or os.environ.get("HF_TOKEN")  # None -> cached login

    try:
        from huggingface_hub import HfApi
    except ImportError:
        print("error: huggingface_hub required (pip install -r requirements.txt).", file=sys.stderr)
        return 1
    api = HfApi(token=token)

    acfg = cfg.get("automerge", {})
    max_rows = args.max_rows if args.max_rows is not None else acfg.get("max_rows_per_pr", 2000)
    # Reference distribution for outlier detection: the local sample dataset.
    try:
        with open(rd.default_dataset_path(), encoding="utf-8") as fh:
            reference_rows = json.load(fh)
    except OSError:
        reference_rows = []

    try:
        prs = list(api.get_repo_discussions(repo_id=repo_id, repo_type="dataset",
                                             discussion_type="pull_request",
                                             discussion_status="open"))
    except Exception as exc:  # noqa: BLE001
        print(f"error: could not list PRs for '{repo_id}': {exc}", file=sys.stderr)
        return 1

    actions = []
    for pr in prs:
        num = pr.num
        added, removed, modified = diff_files(api, repo_id, num)
        rows, errs = load_pr_rows(api, repo_id, num, added)
        valid, invalid = rd.partition_rows(rows)
        valid_new = dedup_count(valid)
        abuse = abuse_scan(valid, reference_rows, acfg)
        verdict = pr_verdict(added, removed, modified, len(rows), len(invalid),
                             valid_new, errs, max_rows, args.max_corrupt_ratio,
                             abuse_reasons=abuse)
        entry = {"pr": num, "title": pr.title, "added_files": added,
                 "rows": len(rows), "valid": len(valid), "invalid": len(invalid),
                 **verdict}

        if not args.dry_run:
            try:
                if verdict["action"] == "merge":
                    api.merge_pull_request(repo_id, num, repo_type="dataset",
                                           comment=f"Auto-merged by bot: {verdict['reason']}.")
                    entry["merged"] = True
                else:
                    api.comment_discussion(
                        repo_id, num, repo_type="dataset",
                        comment=f"Auto-merge bot held this PR ({verdict['status']}): "
                                f"{verdict['reason']}. Needs a human review.")
                    entry["merged"] = False
            except Exception as exc:  # noqa: BLE001
                entry["error"] = str(exc)
        actions.append(entry)

    report = {
        "repo": repo_id,
        "open_prs": len(prs),
        "merged": sum(1 for a in actions if a.get("action") == "merge" and a.get("merged")),
        "held": sum(1 for a in actions if a.get("action") == "hold"),
        "dry_run": args.dry_run,
        "actions": actions,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
