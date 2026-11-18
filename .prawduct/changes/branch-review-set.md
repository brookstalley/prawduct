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
the gate to a whole spanning `cumulative`. The census, the handoff and the round budget now compose
over one set, `coverage.branch_review_ids`. It holds the review facts anchored on
`merge_base..HEAD`. When that span holds no commits, it holds this worktree's review facts, narrowed
as the last paragraph describes. The round budget already counted over that set and now takes it
from the same owner, passing its scope. Its `review_ids` are unchanged.

**Render.** `render-dispositions` with no flags renders every review in the branch's set. When the
set is unavailable or empty, it renders the newest review and prints one stderr line saying so.
`--review` and `--scope` are unchanged. The census summary adds `open_blocking`,
`open_blocking_basis` and `undispositioned_warning`, and the report schema moves to 3. Both changes
are additive.

**Write.** `carried_blocking` returns every blocker the gate still counts at the tree the verify
pass anchors on, an earlier round's included. The verify dispatch's roll-call, the consolidation
`NOT DONE` line and the derived findings cache all carry them. A verify dispatch counts them as
actionable, so it is no longer refused as "nothing to verify" when the only open blocker is an
earlier round's. The verify pass's interval anchor is unchanged.

**Gate.** `check-cumulative-critic` no longer says "no verify-resolutions pass will name again" for
a superseded blocker the roll-call names. It says to run verify-resolutions instead. A blocker the
roll-call would not name still routes to a spanning `cumulative`.

**Read.** The session handoff's `## Critic Findings` section adds one line under the newest
review's record. That line comes from facts over the branch's set and gives the open blocking count,
the undispositioned warning count and the number of rounds. When the store is unreadable or the set
cannot be derived, the line says so and does not report the branch clean.

**One predicate for "open", and a bounded fallback.** The roll-call, the `NOT DONE` line, the
verify dispatch's count, the gate's remedy and the census ask the gate's own question,
`coverage.open_blockers`. The handoff line does not: composing it is a coverage walk measured at
~75s on a cold verdict memo, which SessionStart would pay, so that line counts blockers with no
resolution fact, says so, and names `check-cumulative-critic` for the gate's count. It reads the coverage verdict from
the merge base through `coverage_algebra.blockers_counted`. A blocker is open only while the gate
counts it. A resolution fact clears it, and so does a clean spanning review whose composed path
never stands at the blocker's tree. Before this, a blocker with no resolution fact counted as open
even after such a review. The gate passed, but the roll-call still named the blocker, a verify
round was dispatched for nothing, consolidation wrote a false `NOT DONE`, and the handoff and the
census reported it open. The census summary's new `open_blocking_basis` says whether its count came
from the gate or, when no path composes, from resolution facts alone.

With an empty span, the worktree fallback no longer returns every review the worktree ever
recorded. That pool was over a thousand facts in a long-lived checkout, across all scopes and all
time. The fallback now keeps only the reviews linked to HEAD's tree, using the same review-link
rule, `coverage_algebra.linked_reviews`, that the verify anchor, `review_chain` and the
extended-interval walk now share. The round budget passes its scope instead and is bounded by that
scope. One consolidation also resolves the merge base and walks the lineage only once.

## Consumer note
A bare `render-dispositions` now lists every review on the branch, not just the newest one, so a
change-log entry or PR body pasted from it can grow. Pass `--review <id>` to get the old
single-review table. A `--json` consumer sees `schema_version: 3`, which has three new summary keys
and no removed ones.
