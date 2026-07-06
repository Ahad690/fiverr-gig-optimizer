# Good First Issues — seed list

18 small, well-scoped tasks that make good first PRs. Each has clear acceptance
criteria so a newcomer can finish in one sitting. This is the **fork-funnel**: label
them `good first issue`, and beginners farming their GitHub contributions will fork,
fix, PR, and star.

To create them all as real GitHub issues, run `bash scripts/seed_issues.sh` (below),
or copy each block into a new issue by hand.

| # | Title | Area | Acceptance |
|---|-------|------|-----------|
| 1 | Add a Graphic Design category preset | presets | `benchmarks.sample.json` gains a graphic-design segment; a test asserts it loads |
| 2 | Add a Video & Animation category preset | presets | new segment + test |
| 3 | Add a Writing & Translation category preset | presets | new segment + test |
| 4 | Add `--json` output flag to `build_catalog.py` | feature | emits the catalog as JSON; test checks schema |
| 5 | Add a `--csv` competitor export to `analyze_pricing.py` | feature | writes rows to CSV; test on a fixture |
| 6 | Translate `FIVERR_PASTE_SHEET.md` template to Spanish | i18n | `FIVERR_PASTE_SHEET.es.md` mirrors structure |
| 7 | Translate the paste sheet to Portuguese | i18n | `.pt-BR.md` variant |
| 8 | Add dark-mode CSS to the catalog HTML | ui | `prefers-color-scheme: dark` styles; screenshot in PR |
| 9 | Add a "copy title" button to each gig card | ui | button copies the title; no framework, vanilla JS |
| 10 | Validate tag count ≤ 5 in `build_catalog.py` | validation | warns/flags gigs with >5 tags; test |
| 11 | Validate title ≤ 80 chars | validation | flag over-length titles; test |
| 12 | Add a `--seller-name` CLI override | feature | overrides `seller.name` from config; test |
| 13 | Document each script's JSON I/O in `docs/` | docs | one markdown page per script |
| 14 | Add example `gig-config.json` for a designer | examples | realistic sample under `examples/` |
| 15 | Add a `make test` / `just test` shortcut | dx | one-command test run; README note |
| 16 | Improve the empty-state when a keyword has no data | ux | catalog renders an honest "no data" card; test |
| 17 | Add `pre-commit` config running `pytest` | dx | `.pre-commit-config.yaml` + docs |
| 18 | Add alt-text lint for README images | a11y | script flags `<img>` missing `alt`; CI-friendly |

## `scripts/seed_issues.sh`

```bash
#!/usr/bin/env bash
# Creates the labels + issues above. Requires: gh auth login already done.
set -e
REPO="Ahad690/fiverr-gig-optimizer"
gh label create "good first issue" --repo "$REPO" --color 7057ff --force 2>/dev/null || true
gh label create "hacktoberfest"    --repo "$REPO" --color ff6b35 --force 2>/dev/null || true

create() { gh issue create --repo "$REPO" --label "good first issue" --title "$1" --body "$2"; }

create "Add a Graphic Design category preset" "Add a graphic-design segment to \`benchmarks.sample.json\` and a test asserting it loads. See CONTRIBUTING.md. Honesty rule: no invented numbers — presets carry provenance."
create "Add \`--json\` output flag to build_catalog.py" "Emit the catalog as JSON alongside HTML. Add a test checking the schema. Keep pytest green."
# ... (repeat for issues 2-18; see table above)
echo "Done. Review the created issues before sharing."
```

> **Note:** creating 18 public issues is outward-facing and hard to undo. Review the
> list, then run the script (or ask the maintainer to). Start with 5–8 if unsure.
