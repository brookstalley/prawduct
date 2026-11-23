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

The owner ruling of 2026-11-23 answers it. `_cadence_round_ids` takes out the scope's first
boundary review, its first `cumulative` (the boundary stage), and each chunk's first review in any
other mode (a plan may declare `Critic mode: final` for a chunk). The budget counts what is left. A
chunk's second review, a second `cumulative`, and a review naming no chunk are still counted, so a
review loop meets the same ceiling it did. At the ceiling, a dispatch that is itself a cadence step
still runs. The check runs after the chunk proposal is drawn, so a chunk's first review is
recognised whether its chunk came from `--chunks` or from the proposal. The refusal
message and its `guard-refusal` record now give the cadence count, which `evidence list` renders as
`cadence=N`. A record with no `cadence` field predates this change, and its `spent` included cadence
rounds.

## Consumer note
A build plan's planned reviews no longer spend the review round budget. That means each chunk's
first review, in any mode, and the plan's first `cumulative`. A plan with more chunks than
`review_round_budget` now reaches its boundary review without `--force`, and a planned review still
runs after loops have used up the budget. Repeated reviews of the same work, including a second
`cumulative`, are counted as before.
