---
schema: 1
type: fix
scope: round-budget-cadence
date: 2026-11-23
title: the review round budget no longer charges a plan's own cadence
---
`review_round_budget` (6 by default) counted every full review round in a build-plan scope,
including each chunk's planned `chunk` review. A plan of seven chunks, with one clean review per
chunk, ran out the budget on Chunks 01 to 06, so `critic-begin` refused its boundary review (exit
4), the one review the methodology says is never skipped. `--force` was the only way through. The
review that shipped the budget had raised this (R-9(a)) and left it as an open owner question.
`chunk-plan-order` hit it on 2026-11-23.

The owner ruling of 2026-11-23 answers it. `_cadence_round_ids` takes out each chunk's first
review, in whatever mode it ran (a plan may declare `Critic mode: final` for a chunk), and the
scope's first boundary review (the first `final` or `cumulative` naming no chunk an earlier review
had not). The budget counts what is left. A chunk's second review, a second boundary review, and a
review naming no chunk are still counted, so a review loop meets the same ceiling it did. At the
ceiling, a dispatch that is itself a cadence step still runs: a chunk's first review named with
`--chunks`, or the first boundary review. The refusal says to pass `--chunks` for a chunk's first
review, which is the one case the check cannot see before the proposal is drawn. The refusal
message and its `guard-refusal` record now give the cadence count, which `evidence list` renders as
`cadence=N`. A record with no `cadence` field predates this change, and its `spent` included cadence
rounds.

## Consumer note
A build plan's planned reviews no longer spend the review round budget. That means each chunk's
first review, in any mode, and the plan's first boundary `final` or `cumulative`. A plan with more
chunks than `review_round_budget` now reaches its boundary review without `--force`, and a planned
review still runs after loops have used up the budget. Pass `--chunks` on a chunk's first review so
it is recognised. Repeated reviews of the same work are counted as before.
