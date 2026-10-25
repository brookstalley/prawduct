---
schema: 1
type: feature
scope: review-stats-dispositions
date: 2026-10-25
title: review-stats reports what the builder did with each finding, not only what the reviewer labelled
---
`review-stats` groups reviews by role × model × mode, scope and stage, but its only yield figure
was `actionable_rate`: the share of reviews a reviewer labelled blocking or warning. A finding
that was fixed and one that was accepted and left looked the same. Every stat block now carries
a `dispositions` block (#941). It joins each ledger review to the evidence store by its
`fact_id` and reads each blocking or warning finding's outcome by the rule `stats` and
`render-dispositions` use (`stats.finding_outcome`). The acted-on arithmetic moved into one
helper, `stats.acted_on`, which both reports call.

The block says how many reviews joined and how many didn't. `review.pr` events carry no
`fact_id`, so they never join. When the store is missing, unreadable or outside git, the block
says so with a reason and gives no rate, and every severity figure is unchanged. The window
selects reviews, and their outcomes are read as the store stands at run time (`as_of`).

## Consumer note
- `prawduct-hook review-stats --json` is `schema_version` 9. It adds a top-level
  `dispositions` header and a `dispositions` block on every stat block (`joined_reviews`,
  `unjoined_reviews`, `by_outcome`, `answered`, `acted_on_rate`). No key was removed, and
  `actionable_rate` keeps its meaning.
- The human line leads its yield figures with `acted on N% of M answered blocking/warning
  findings, U undispositioned (J of R reviews joined)`, and the old `actionable` figure now
  reads `severity-actionable`.
