---
schema: 1
type: fix
scope: chunk-credit-merged-verified
date: 2026-11-18
title: plan status credits a chunk whose review was extended by a verify pass, or whose commit came in through a delegate merge
closes: [brookstalley/prawduct#1191, brookstalley/prawduct#1199]
---
`prawduct-hook plan status` left two kinds of reviewed chunk `open`, even though
`check-cumulative-critic` covered them.

- **A verify pass extending a dirty-tree chunk review (#1191).** A `verify-resolutions` pass over
  a review of uncommitted work records no `base_commit`, because the writer copies the prior
  review's `head_commit` and a dirty-tree review has none. A span with no `base_commit` carried
  nothing, so committing the verified tree verbatim as `(Chunk N)` credited no chunk. Such a pass
  now spans from the anchor of the review it extends. The link is the one `critic_mode.review_chain`
  follows: a review's `base_tree` is the head tree of the newest review before it. The credit
  holds only while every review on that line is a coverage edge and certifies by the usual rule.
  Its blocking findings must be resolved and its anchor must be on the branch. The chunk's commit
  carries work from both intervals.
- **A delegate's chunk commit merged with `--no-ff` (#1199).** A span read the interval along
  first parents only, which drops the delegate's `(Chunk N)` commit on the merge's second parent.
  The merge commit's own subject is unscoped, so it counts for nothing either. A merge now adds the
  first-parent commits of the side it brought in, unless that side is the base's own work. The base's
  own work is a merged-in tip on the plan's base's first-parent history. A delegate's tip is never
  there, either before the plan merges or after. A merge of the base still carries nothing. When
  the base resolves to no ref, or git cannot answer, the side carries nothing.

The fact's `chunks_proposed` is unchanged: a `chunk`-mode proposal still names chunks by
Deliverables path alone. The chunk is credited by span, as `plan status` reports.

## Consumer note
`plan status` may now show as done a chunk it showed as open: one verified by a
`verify-resolutions` pass and then committed, or one built by a delegate and merged into the plan's
branch with a merge commit. No action needed.
