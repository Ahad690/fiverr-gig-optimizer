#!/usr/bin/env python3
"""validate.py — generalized, config-driven validation + gating gates.

Reusable across projects. Pure stdlib (json, hashlib, statistics) — no pip
installs, so it runs anywhere and stays trivially auditable.

Three things live here:
  1. Per-row schema/PII/range validation        -> validate_row / partition
  2. The merge/no-op/abort gate (corrupt ratio)  -> decide
  3. Optional anti-abuse heuristics              -> abuse_scan

Everything is driven by a SCHEMA / ABUSE config dict so you adapt it to your
domain by editing config, not code. See the example configs at the bottom.
"""
import hashlib
import statistics


# --------------------------------------------------------------------------
# 1. Per-row validation
# --------------------------------------------------------------------------

def validate_row(row, schema):
    """Return (ok, reason). Enforces shape, ranges, list types, and no-PII."""
    if not isinstance(row, dict):
        return False, "not an object"
    for bad in schema.get("forbidden", []):
        if bad in row:
            return False, f"forbidden/PII field present: {bad}"
    for field in schema.get("required_str", []):
        v = row.get(field)
        if not (isinstance(v, str) and v.strip()):
            return False, f"missing {field}"
    for field, bounds in schema.get("numeric", {}).items():
        v = row.get(field)
        if v is None:
            continue
        if not isinstance(v, (int, float)):
            return False, f"{field} not number-or-null"
        if "min" in bounds and v < bounds["min"]:
            return False, f"{field} below min {bounds['min']}"
        if "max" in bounds and v > bounds["max"]:
            return False, f"{field} above max {bounds['max']}"
    for field in schema.get("list_fields", []):
        v = row.get(field)
        if v is not None and not isinstance(v, list):
            return False, f"{field} not a list"
    return True, "ok"


def strip_to_keep(row, keep):
    """Rebuild a row from the keep-list only (drops any stray/PII field)."""
    return {k: row.get(k, None) for k in keep}


def partition(rows, schema):
    """Split rows into (valid_and_canonicalized, invalid_reasons)."""
    keep = schema.get("keep", [])
    valid, invalid = [], []
    for row in rows:
        ok, reason = validate_row(row, schema)
        if ok:
            valid.append(strip_to_keep(row, keep) if keep else row)
        else:
            invalid.append(reason)
    return valid, invalid


def row_hash(row, key_fields):
    """Stable hash over selected fields, for dedup."""
    parts = [str(row.get(f, "")).strip().lower() for f in key_fields]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def dedup_count(rows, key_fields):
    seen, n = set(), 0
    for r in rows:
        h = row_hash(r, key_fields)
        if h not in seen:
            seen.add(h)
            n += 1
    return n


# --------------------------------------------------------------------------
# 2. The merge gate
# --------------------------------------------------------------------------

def decide(seen, invalid_count, new_after_dedup, min_new, max_corrupt_ratio, file_errors):
    """Verdict for a batch. Returns {action: merge|noop|abort, status, reason}."""
    if file_errors:
        return {"action": "abort", "status": "corrupt",
                "reason": f"{file_errors} file(s) failed to parse"}
    if seen == 0:
        return {"action": "noop", "status": "empty", "reason": "no rows found"}
    ratio = invalid_count / seen
    if ratio > max_corrupt_ratio:
        return {"action": "abort", "status": "corrupt",
                "reason": f"corrupt fraction {ratio:.0%} > {max_corrupt_ratio:.0%} "
                          f"({invalid_count}/{seen})"}
    if new_after_dedup < min_new:
        return {"action": "noop", "status": "insufficient",
                "reason": f"only {new_after_dedup} new row(s); need >= {min_new}"}
    return {"action": "merge", "status": "ok",
            "reason": f"{new_after_dedup} clean new row(s)"}


# --------------------------------------------------------------------------
# 3. Optional anti-abuse heuristics (well-formed-but-suspicious data)
# --------------------------------------------------------------------------

def abuse_scan(rows, reference_rows, abuse):
    """Return a list of reasons ([] = clean). Each check runs only if configured.

    Schema validation already covers types/PII/ranges; these catch suspicious
    patterns: duplicate flooding, broken value ordering, and group outliers vs
    a reference distribution.
    """
    reasons = []
    if not rows:
        return reasons

    # Duplicate flooding (low unique ratio).
    key = abuse.get("dedup_key")
    if key and len(rows) >= abuse.get("dedup_min_rows", 5):
        uniq = dedup_count(rows, key)
        if uniq / len(rows) < abuse.get("min_unique_ratio", 0.5):
            reasons.append(f"only {uniq}/{len(rows)} unique rows (flooding)")

    # Ascending-ordering violations across a set of fields (e.g. price tiers).
    order = abuse.get("ordering")
    if order:
        viol = 0
        for r in rows:
            seq = [r.get(f) for f in order if isinstance(r.get(f), (int, float))]
            if len(seq) >= 2 and any(a > b for a, b in zip(seq, seq[1:])):
                viol += 1
        if viol / len(rows) > abuse.get("ordering_violation_max_ratio", 0.3):
            reasons.append(f"{viol}/{len(rows)} rows violate ascending {order}")

    # Group-median outlier vs reference distribution.
    out = abuse.get("outlier")
    if out and reference_rows:
        field, group = out["field"], out["group_by"]
        factor, min_rows = out.get("factor", 10), out.get("min_rows", 3)
        ref = _group_medians(reference_rows, group, field)
        cur = _group_values(rows, group, field)
        for g, vals in cur.items():
            if g in ref and ref[g] > 0 and len(vals) >= min_rows:
                r = statistics.median(vals) / ref[g]
                if r > factor or r < 1 / factor:
                    reasons.append(f"group '{g}' {field} median is {r:.1f}x reference (outlier)")
    return reasons


def _group_values(rows, group, field):
    out = {}
    for r in rows:
        g, v = r.get(group), r.get(field)
        if g is not None and isinstance(v, (int, float)):
            out.setdefault(g, []).append(v)
    return out


def _group_medians(rows, group, field):
    return {g: statistics.median(v) for g, v in _group_values(rows, group, field).items() if v}


# --------------------------------------------------------------------------
# Example config (adapt to your domain)
# --------------------------------------------------------------------------

EXAMPLE_SCHEMA = {
    "keep": ["id", "title", "category", "price", "rating", "tags"],
    "required_str": ["title", "category"],
    "numeric": {"price": {"min": 0, "max": 100000}, "rating": {"min": 0, "max": 5}},
    "list_fields": ["tags"],
    "forbidden": ["email", "username", "profile_url", "phone", "ip"],
}
EXAMPLE_ABUSE = {
    "dedup_key": ["title", "category"],
    "min_unique_ratio": 0.5,
    "ordering": [],                       # e.g. ["basic", "standard", "premium"]
    "outlier": {"field": "price", "group_by": "category", "factor": 10, "min_rows": 3},
}


if __name__ == "__main__":  # tiny smoke test
    good = {"title": "t", "category": "c", "price": 10, "rating": 4.5, "tags": ["x"]}
    assert validate_row(good, EXAMPLE_SCHEMA)[0]
    assert not validate_row(dict(good, email="a@b.c"), EXAMPLE_SCHEMA)[0]
    assert not validate_row(dict(good, rating=9), EXAMPLE_SCHEMA)[0]
    v, inv = partition([good, {"title": "", "category": "c"}], EXAMPLE_SCHEMA)
    assert len(v) == 1 and len(inv) == 1
    assert decide(10, 0, 8, 1, 0.0, 0)["action"] == "merge"
    assert decide(10, 1, 9, 1, 0.0, 0)["action"] == "abort"   # any invalid at ratio 0
    print("validate.py self-test OK")
