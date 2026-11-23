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
`chunk` review and the scope's first boundary review (`final` or `cumulative`), and the budget
counts what is left. A chunk's second review, a second boundary review, and a `chunk` review
naming no chunk are still counted, so a review loop meets the same ceiling it did. The refusal
message and its `guard-refusal` record now give the cadence count, which `evidence list` renders as
`cadence=N`. A record with no `cadence` field predates this change, and its `spent` included cadence
rounds.

## Consumer note
A build plan's planned reviews no longer spend the review round budget. That means each chunk's
first `chunk` review and the plan's first `final` or `cumulative` review. A plan with more chunks
than `review_round_budget` now reaches its boundary review without `--force`. Repeated reviews of
the same work are counted as before.
