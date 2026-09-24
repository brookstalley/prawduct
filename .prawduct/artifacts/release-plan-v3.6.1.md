# Release Plan — v3.6.1, Whole-Develop Promotion

**Status:** IN PROGRESS, 2026-09-24. Phase 0 and Phase 1 run on `develop` at `80575c12`, which is
the merge of #899. That merge is what made `develop` green: before it, one suite failure was
committed straight to `develop` (`a0e90e80`, the #672 design doc). Re-derive this state rather
than reading it here: `git log --oneline origin/main -1`, `prawduct-hook check-released v3.6.1`.

**Version:** v3.6.1, a **patch**, and the owner named the number ("release 3.6.1", 2026-09-24).
It matches both the ratified conservative-versioning norm (`operational-spec.md` `## Direction`)
and the `3.6.1-dev.N` track `develop` has carried since the v3.6.0 cut. The bundle has more than
a small patch's weight: 26 scopes, and one of them, `suite-at-boundary`, changes a default. But
nothing in it is a subsystem going live, a persisted-format one-way door, or a gate newly on by
default in the sense v3.6.0 recorded. The default that moves makes things cheaper, not stricter:
a chunk's Verify step now runs the inner-loop row, and the declared suite runs at the boundary.
`plugin/hooks/gates.json` has no row stamped `since: 3.6.1`, so the banner announces no new
gate. **`learnings-one-line` is deliberately not in this release.** It is unmerged on
`feature/learnings-one-line`, it registers two gates `since: 3.7.0`, and it ships as the minor
that follows.

## Release classification

Twenty-six release-pending scopes, **all shipping**. `check-releasability --release v3.6.1`
enumerates them. Phase 1 step 2's per-candidate test ran over every untagged entry: none of the
27 entries' headings appears in the v3.6.0 tree's change-log or archive. For the one scope whose
entries are dated before the v3.6.0 cut (`coverage-honesty`, entries from 2026-08-20), a code
test confirmed it: `git grep plans_missing_scope v3.6.0 -- plugin` finds nothing, and it is
present on `develop`. That scope merged as #879 after the cut.

| Scope | Disposition | Blocker |
|---|---|---|
| 863-payload-backlog-scan | ships | |
| 866-cost-of-commit-covered | ships | |
| coverage-honesty | ships | |
| dev-track-bump-20260922 | ships | |
| dev-track-bump-3.6.1-dev.3 | ships | |
| dev-track-bump-3.6.1-dev.4 | ships | |
| dev-track-bump-3.6.1-dev.5 | ships | |
| dev-track-bump-3.6.1-dev.6 | ships | |
| failing-test-ids | ships | |
| far-behind-branch-guidance | ships | |
| learnings-migrate-local | ships | |
| measured-round-price | ships | |
| per-tree-test-evidence | ships | |
| pin-status-tick-meaning | ships | |
| pr-review-clock | ships | |
| pr-reviewer-path-scoped-rules | ships | |
| release-v3.6.0 | ships | |
| review-budget-trunk-shape | ships | |
| review-interval-extension | ships | |
| review-loop-economy | ships | |
| review-scrub-seams | ships | |
| reviewer-prompt-file-list | ships | |
| scope-note-plan-less-silence | ships | |
| standing-block-closing-section | ships | |
| suite-at-boundary | ships | |
| unresolved-scope-diagnosis | ships | |

**Nothing is withheld, so `K = 0`** and this is a standard whole-develop promotion. `K` is taken
from the gate's own output.

## Digest coverage

The gate's scope-name match finds 18 of the 26 scopes in the `## v3.6.1-dev.6` section. Walking
the other eight by hand:

- Five record the release mechanics themselves, and no consumer note is owed for them: the four
  `dev-track-bump-*` scopes, and `dev-track-bump-20260922`.
- `review-loop-economy` is a maintainer instrument under `tools/`. It does not ship in the
  plugin subtree, so no note is owed.
- `scope-note-plan-less-silence` is described in other words under `unresolved-scope-diagnosis`
  ("A branch that touched no plan gets no note").
- `pr-reviewer-path-scoped-rules` had no note. One is added at this cut, because it corrects a
  claim the plugin made to consumers about what the PR reviewer can see.

## Plans

Eight live plans declare a shipping scope: `per-tree-test-evidence`, `suite-at-boundary`,
`pr-review-clock`, `coverage-honesty`, `unresolved-scope-diagnosis`, `failing-test-ids`,
`review-interval-extension` and `review-budget-trunk-shape`. To find them, grep
`.prawduct/artifacts/*.md` for a `scope:` line naming a scope from the table. Every chunk box on
seven of them is ticked, and `plan-backfill` archives those seven.

`build-plan-coverage-honesty.md` is the exception. It closes on Chunks 01–02 on purpose. Chunk 03
was split out to #672, and Chunk 04 was superseded by #734. Each chunk's heading records its own
reason. The two unticked boxes are therefore not unfinished work, and they stay unticked, because
ticking them would claim builds that did not happen. `plan-backfill` refuses the plan on Status
completeness, and the runbook's remedy for that refusal is an explicit
`archive-plan --state completed --release v3.6.1`. `active_build_plan` was already `null` on
`develop`, so there was no pointer to clear before the sweep. The other 18 scopes are plan-less
work.
