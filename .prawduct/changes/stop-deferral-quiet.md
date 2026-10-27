---
schema: 1
type: fix
scope: stop-deferral-quiet
date: 2026-10-27
title: Stop's deferred-review notice no longer appears in the transcript every turn
---
Between chunks of a multi-chunk plan, the Stop hook's Critic gate defers a review to the boundary
and says so: "no review covers this session's changes yet, and none is owed now… Commit and carry
on." On a turn nothing blocked, that notice went into the transcript as a `systemMessage`, every
turn the deferral held. Only the user reads that channel, and the notice gives them nothing to do.
The model never sees exit-0 output at all. Both deferral notices, the review-interval extension and
the short-plan non-final chunk, now go to the hook's stderr log at exit 0. When another gate blocks
the turn, they still appear in the block text beside the blockers, where the model reads them.

## Consumer note
- The `WARNING (deferred-boundary-review)` notice no longer appears in your transcript on
  turns that end normally. Nothing about when reviews are owed has changed: the boundary review
  is still required, and its gate blocks as before.
