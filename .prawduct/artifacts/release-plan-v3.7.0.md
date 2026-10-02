# Release Plan — v3.7.0, Whole-Develop Promotion

**Status:** IN PROGRESS, 2026-10-02. Phase 0 classified every pending scope and Phase 1 prep is
on `develop`. Re-derive rather than reading this line as a measurement:
`prawduct-hook check-releasability --release v3.7.0`, `git log --oneline origin/main -1`.

**Version:** v3.7.0, a **minor**, and the owner named the number ("let's get 3.7.0 PR'd and
released to main", 2026-10-02). The minor was already decided before this cut.
`release-plan-v3.6.1.md` held `learnings-one-line` out of v3.6.1 because it registers gates
`since: 3.7.0` and "ships as the minor that follows". `develop` has carried `3.7.0-dev.N` since.
`plugin/hooks/gates.json` now has three rows stamped `since: 3.7.0`
(`learnings-rule-too-long`, `learnings-rule-body`, `clear-verdict`), so the banner announces
three gates newly on by default. That, plus a corpus freeze on any repo whose learnings are over
the new limits, is a minor under the release-history precedent, not a patch.

## Release classification

Every release-pending scope ships. `check-releasability --release v3.7.0` enumerates them.
Phase 1 step 2's per-candidate test ran over all 35 untagged entries: none of their headings
appears in the v3.6.1 tree's change-log or archive. A control confirmed the comparison can find
a match: two headings tagged `release=v3.6.1` are both present in that tree. The two entries
dated on the cut day (2026-09-24) were checked by name. `release-v3.6.1` is the post-cut reopen
commit. `learnings-one-line` was deliberately held out of v3.6.1, and its code test agrees:
`git show v3.6.1:plugin/hooks/gates.json` has no `since: 3.7.0` row, and `develop` has three.

No open issue is a release blocker. The tracker has no blocker label, and a search of open
issues for release-blocking terms found only ordinary backlog work.

| Scope | Disposition | Blocker |
|---|---|---|
| clear-verdict-coherence | ships | |
| dead-why-reaffirmed | ships | |
| dev-track-bump-3.6.2-dev.1 | ships | |
| dev-track-bump-3.6.2-dev.2 | ships | |
| dev-track-bump-3.6.2-dev.3 | ships | |
| dev-track-bump-3.6.2-dev.4 | ships | |
| dev-track-bump-3.6.2-dev.5 | ships | |
| dev-track-bump-3.6.2-dev.6 | ships | |
| dev-track-bump-3.6.2-dev.7 | ships | |
| dev-track-bump-3.7.0-dev.1 | ships | |
| dev-track-bump-3.7.0-dev.2 | ships | |
| dev-track-bump-3.7.0-dev.3 | ships | |
| dev-track-bump-3.7.0-dev.4 | ships | |
| drop-risk-surface-ask | ships | |
| four-part-release-versions | ships | |
| learnings-one-line | ships | |
| onboard-ux | ships | |
| opus-55-w1-always-on | ships | |
| opus-55-w2-hook-gate-text | ships | |
| opus-55-w3-review-machinery | ships | |
| opus-55-w3b-review-cycle-split | ships | |
| opus-55-w4-methodology-templates | ships | |
| opus-55-w5-operational-skills | ships | |
| opus-55-w6-reference-docs | ships | |
| record-lint-945-939 | ships | |
| release-v3.6.1 | ships | |
| review-friction | ships | |
| short-plan-tick | ships | |
| sibling-hook-perf | ships | |
| stranded-work | ships | |
| suite-at-boundary-note-window | ships | |
| test-evidence-pre-run-tree | ships | |
| test-evidence-root-testcases | ships | |
| update-body-lint | ships | |

**Nothing is withheld, so `K = 0`** and this is a standard whole-develop promotion. `K` is taken
from the gate's own output.

## Digest coverage

The gate's scope-name match finds 21 of the 34 scopes in the open `plugin/CHANGELOG.md` section.
Walking the other 13 by hand:

- Twelve record the release mechanics themselves, and no consumer note is owed for them: the
  eleven `dev-track-bump-*` scopes and `release-v3.6.1`.
- `suite-at-boundary-note-window` is test-only. Its own entry says "nothing changes for
  consumers".

## Plans

Twelve live plans declare a shipping scope: `learnings-one-line`, the seven `opus-55-w*`
plans (`w1`–`w6` plus `w3b`), `review-friction`, `short-plan-tick`, `sibling-hook-perf`
and `stranded-work`. To find them, grep `.prawduct/artifacts/*.md` for a `scope:` line naming a
scope from the table. Every chunk box on all twelve is ticked. `active_build_plan` was already
`null` on `develop`, so there was no pointer to clear before the sweep. The other 22 scopes are
plan-less work.

`plan-backfill` could not evaluate `waiver-pragma-plan.md`, a 2.0-line plan whose `scope:` sat in
an HTML comment rather than frontmatter, so no sweep had ever reached it. Its boxes were all
ticked and its work is old, so it was archived at this cut with `archive-plan --state completed
--release v2.0.4`. The release comes from a tree-content test, not ancestry: `lib/waivers.py`, its
first deliverable, is absent from the v2.0.0–v2.0.3 trees and present from v2.0.4.
