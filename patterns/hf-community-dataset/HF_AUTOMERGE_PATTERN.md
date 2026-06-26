# Pattern: a self-growing community dataset on Hugging Face with a safe auto-merge bot

A reusable design for open-source projects that want a **community-contributed
dataset** which improves itself over time, **without** a maintainer hand-reviewing
every contribution — and without risking the dataset getting corrupted.

It combines three things:
1. **Hugging Face as a git-versioned store** (every state revertible).
2. A **stacking-not-rewriting** data model (append-only, content-addressed).
3. A **layered guard stack** so a bot can auto-merge clean contributions and
   hold suspicious ones for a human.

Files in this folder:
- [`validate.py`](validate.py) — stdlib-only, config-driven validation + gates.
- [`automerge.py`](automerge.py) — the HF PR loop (uses `validate.py`).
- [`automerge-workflow.yml`](automerge-workflow.yml) — the GitHub Actions template.

---

## 1. The flywheel

```
contributor runs your tool
        │  (anonymized, validated locally)
        ▼
  opens a PR to the HF dataset     ──►   refs/pr/<N>  (isolated branch)
        │
        ▼
  GitHub Action (cron) runs automerge.py
        │   ├─ purely additive?  schema/PII/range ok?  not suspicious?
        │   ├─ YES → merge PR  ──►  main (new commit, new file)
        │   └─ NO  → comment + leave open for a human
        ▼
  consumers run "refresh": pull dataset → merge new rows into a local copy
        │   (dedup; local file is what scoring/training reads → deterministic)
```

The contribution goes **up** (PR → merge), and a `refresh` step pulls it back
**down** into each user's local copy. Production never reads HF live — it reads a
local, versioned snapshot — so determinism/reproducibility is preserved while the
shared corpus grows.

---

## 2. Why Hugging Face: git-versioned, so everything is revertable

An HF repo (dataset/model/space) is **literally a git repo** (git + git-LFS).
That single fact powers the whole safety story:

- **Every change is a commit with a SHA**; full history is retained. Nothing is
  ever truly overwritten — a change is a new commit on top.
- **A PR is a branch** at ref **`refs/pr/<N>`**, separate from `main` until merged.
  You can read any revision — SHA, branch, tag, or `refs/pr/N`:
  ```python
  hf_hub_download(repo_id, filename=f, repo_type="dataset", revision=f"refs/pr/{n}")
  ```
  This is how the bot inspects a PR's proposed files *without trusting them yet*.
- **Merging = a commit on `main`.**
- **Reverting = a corrective commit, not history surgery.** Because every prior
  SHA stays addressable, you undo a bad merge by adding a commit that restores
  the earlier state:
  ```python
  from huggingface_hub import HfApi, CommitOperationDelete
  HfApi(token=...).create_commit(
      repo_id="owner/dataset", repo_type="dataset",
      operations=[CommitOperationDelete(path_in_repo="contributions/bad.json")],
      commit_message="Revert bad contribution")
  ```
- **Consumers can pin a revision**, so a bad auto-merge can't poison anyone
  downstream until *you* bump the pin:
  ```python
  load_dataset("owner/dataset", revision="<good-sha-or-tag>")
  ```
  Tag known-good snapshots with `api.create_tag(repo_id, tag="v1", revision="<sha>")`.

**Safety = prevention + recovery.** The guards (§4) stop bad merges; git
versioning guarantees that anything that slips through is recoverable and that
pinned consumers were never affected.

---

## 3. Design principle: stack, don't rewrite

Apply one rule at every layer: **data accumulates as append-only, content-addressed
additions with dedup — never destructive rewrites.** Three mechanisms:

1. **One new file per contribution, content-addressed.** Write each contribution to
   `contributions/<author>-<sha256(payload)[:10]>.json` — a *new* file, never a
   shared file that gets rewritten. Consequences:
   - Two contributors (or two runs) **never collide** on a path, so merging PR #2
     can't silently clobber PR #1.
   - Re-submitting identical data hashes to the *same* filename → **idempotent**.
2. **Additive-only merge gate.** The bot refuses any PR that modifies or removes an
   existing file — only brand-new files under the contributions prefix are
   mergeable. Auto-merge therefore *structurally cannot* rewrite existing data.
3. **Dedup on read, not overwrite on write.** The `refresh` step pulls all stacked
   files and merges them into the local copy with row-level dedup — additive, never
   rewriting curated rows.

Append-only + git-versioned is the combination that makes unattended auto-merge
defensible: a merge adds an isolated file (small blast radius), and that file is
one corrective commit away from gone. A "single rewritten file" design is the
opposite — every merge mutates shared state, conflicts are constant, and one bad
write can wipe good data.

---

## 4. The guard stack (in `automerge.py` / `validate.py`)

A PR merges **only if it clears every layer**; failing any one → the bot
**comments the reason and leaves the PR open** (never a silent drop):

| # | Guard | What it stops | On fail |
|---|-------|---------------|---------|
| 0 | **Scope** — only *open pull requests* | acting on merged/closed PRs; non-idempotency | ignored |
| 1 | **Additive-only** — no removes, no modifies (blob-id compared), only `contributions/*.json` added | edits to the card, deletes/overwrites, sneaked-in files | HOLD `unsafe_shape` |
| 2 | **Size cap** (`max_rows_per_pr`) | flooding / DoS | HOLD `too_large` |
| 3 | **Schema + PII + range** per row, then **corrupt-ratio gate** | malformed rows, PII fields, out-of-range values, unparseable files | HOLD/ABORT `corrupt` (or `empty`/`insufficient`) |
| 4 | **Anti-abuse heuristics** | well-formed-but-fake: duplicate flooding, broken value ordering, group-median outliers vs a reference | HOLD `suspicious` |

Layer 3 also **rebuilds every row from a keep-list** (`strip_to_keep`), so a stray
or PII field can't ride through even if validation missed it. Default
`max_corrupt_ratio = 0.0` means **a single invalid row holds the whole PR**.

There's also a **token gate** (no write token → nothing merges) and a **`--dry-run`**
mode (decide + report, act on nothing) for safe previews and CI.

### The honest boundary — state this in your README
These gates prove a row is **well-formed, PII-free, in-range, non-duplicate, and
statistically unremarkable**. They do **not** prove the numbers are *authentic* — a
patient adversary could submit plausible, in-distribution fake data. That residual
risk is exactly why §2 (versioning/revert) matters: prevention narrows the blast
radius; versioning guarantees recovery. Don't oversell schema validation as
authenticity.

---

## 5. How the GitHub Action pushes to HF (the auth chain)

It is **not `git push`** — it's the `huggingface_hub` library making authenticated
HTTPS API calls, driven by a token stored as a GitHub secret:

```
fine-grained HF token → GitHub repo secret (HF_TOKEN) → workflow env var
                      → huggingface_hub (HfApi) → HF REST API
```

- Store the token: `gh secret set HF_TOKEN -R owner/repo` (or Settings → Secrets).
- The workflow injects it: `env: HF_TOKEN: ${{ secrets.HF_TOKEN }}`.
- The script uses it: `HfApi(token=os.environ["HF_TOKEN"])`, then `upload_file` /
  `create_commit` / `merge_pull_request`. (`HfApi()` also auto-reads `HF_TOKEN`.)
- The **cron schedule** is the "automatic" trigger; `workflow_dispatch` is the
  manual button.

Generic "push files" example (for a different use case than merging):
```python
api.upload_file(path_or_fileobj="out/data.json", path_in_repo="data.json",
                repo_id="owner/dataset", repo_type="dataset",
                commit_message="CI update")
# api.upload_folder(folder_path="out", repo_id=..., repo_type="dataset")
# api.create_commit(..., create_pr=True)   # push as a PR instead of to main
```

### Token permissions (fine-grained)
Scope to **just the target repo**, and check only:
- **Write access to contents/settings** of the repo (create commits / merge PRs).
- **Interact with discussions / Open pull requests** (open, comment, merge PRs).

Leave everything else off. **Use a fine-grained token, not an `hf auth login`
OAuth token** — OAuth tokens expire and the scheduled run will silently start
failing.

---

## 6. Gotchas (these will bite you)

- **Forked-PR runs don't get secrets.** GitHub withholds secrets from
  `pull_request` workflows triggered by forks (security). Drive the bot from
  `schedule` / `workflow_dispatch` / `push` on your own branch — not a fork PR
  event. (External contributors' *HF* PRs are unaffected; this is only about the
  *GitHub* Action having the secret.)
- **Guard for the empty secret** (`if [ -z "$HF_TOKEN" ]`) so the job no-ops
  cleanly in forks instead of erroring.
- **`permissions:` in the YAML is the GitHub token, not HF.** Your HF write
  ability comes entirely from the secret; you don't widen GitHub perms to write to
  HF.
- **The HF repo must exist** (or `api.create_repo(repo_id, repo_type=..., exist_ok=True)`).
- **Never echo the token** — reference only as `$HF_TOKEN` / `${{ secrets.HF_TOKEN }}`.
- **Reading a public dataset needs no token**; only the write side does.

---

## 7. Adapting the included code

1. **`validate.py`** — edit `EXAMPLE_SCHEMA` (keep-list, required strings, numeric
   ranges, list fields, forbidden/PII fields) and `EXAMPLE_ABUSE` (dedup key,
   ordering fields, outlier field/group/factor) for your domain. Pure stdlib; run
   `python validate.py` for its self-test.
2. **`automerge.py`** — set `CONFIG` (repo_id, repo_type, path_prefix, gates,
   schema, abuse, dedup_key, optional reference_path). `python automerge.py
   --dry-run` to preview.
3. **`automerge-workflow.yml`** — copy to `.github/workflows/`, fix the script
   path, set the `HF_TOKEN` secret.

On the **contribution (write) side** of your tool, mirror §3: strip to the
keep-list, assert no forbidden fields, and upload to
`contributions/<author>-<contenthash>.json` via `create_commit(..., create_pr=True)`.

---

*Reference implementation this was extracted from:
[Ahad690/fiverr-gig-optimizer](https://github.com/Ahad690/fiverr-gig-optimizer)
(`skills/fiverr-gig-optimizer/scripts/{contribute,refresh_dataset,automerge_prs}.py`).*
