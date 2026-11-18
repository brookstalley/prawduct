---
schema: 1
type: fix
scope: branch-review-set
date: 2026-11-18
title: An earlier review round's open findings are no longer hidden behind the newest review
closes: [brookstalley/prawduct#334]
---
Three surfaces read the newest review in place of the branch's reviews. A finding left open on an
earlier round was invisible to the census, named by no `verify-resolutions` roll-call, and routed by
the gate to a whole spanning `cumulative`. They now all compose over one set,
`coverage.branch_review_ids`. It holds the review facts anchored on `merge_base..HEAD`, or this
worktree's review facts when that span holds no commits. The round budget already counted over that
set and now takes it from the same owner. It narrows the set to its scope, and its `review_ids`
are unchanged.

**Render.** `render-dispositions` with no flags renders every review in the branch's set. When the
set is unavailable or empty, it renders the newest review and prints one stderr line saying so.
`--review` and `--scope` are unchanged. The census summary adds `open_blocking` and
`undispositioned_warning`, and the report schema moves to 3. Both changes are additive.

**Write.** `carried_blocking` returns the unresolved blockers of every review in the branch's set,
plus the anchor review's as before. The verify dispatch's roll-call, the consolidation `NOT DONE`
line and the derived findings cache all carry them. A verify dispatch counts them as actionable, so
it is no longer refused as "nothing to verify" when the only open blocker is an earlier round's.
The verify pass's interval anchor is unchanged.

**Gate.** `check-cumulative-critic` no longer says "no verify-resolutions pass will name again" for
a blocker inside the branch's set. It says to run verify-resolutions, whose roll-call names it. A
blocker on a review outside the set still routes to a spanning `cumulative`.

**Read.** The session handoff's `## Critic Findings` section adds one line under the newest
review's record. That line comes from facts over the branch's set and gives the open blocking count,
the undispositioned warning count and the number of rounds. When the store is unreadable or the set
cannot be derived, the line says so and does not report the branch clean.

## Consumer note
A bare `render-dispositions` now lists every review on the branch, not just the newest one, so a
change-log entry or PR body pasted from it can grow. Pass `--review <id>` to get the old
single-review table. A `--json` consumer sees `schema_version: 3`, which has two new summary keys and
no removed ones.
