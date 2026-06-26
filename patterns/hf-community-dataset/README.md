# hf-community-dataset pattern

A reusable, project-agnostic pattern for a **self-growing community dataset on
Hugging Face** with a **safe auto-merge bot** — extracted from this repo so it can
be dropped into other open-source projects.

**Start here:** [`HF_AUTOMERGE_PATTERN.md`](HF_AUTOMERGE_PATTERN.md) — the full
write-up (architecture, HF git versioning + revert, stacking-not-rewriting,
the guard stack, the GitHub Actions auth chain, token perms, and gotchas).

Code templates:
- [`validate.py`](validate.py) — stdlib-only, config-driven validation + merge gates (`python validate.py` runs a self-test).
- [`automerge.py`](automerge.py) — the Hugging Face PR loop; edit `CONFIG`, then `python automerge.py --dry-run`.
- [`automerge-workflow.yml`](automerge-workflow.yml) — GitHub Actions schedule template; needs an `HF_TOKEN` repo secret.

In one line: contributions go **up** as content-addressed PR files → a bot
**auto-merges** only purely-additive, validated, non-suspicious ones → consumers
**pull** them back into a local snapshot. Append-only on top of git versioning =
safe to automate and always revertible.

License: same as the parent repo (code MIT).
