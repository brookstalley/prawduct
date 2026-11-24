---
schema: 1
type: docs
scope: live-review-writes
date: 2026-11-24
title: the Critic guidance no longer says .prawduct/ is free to write while a review runs
closes: []
---
`skills/critic/review-cycle.md` titled its free-writes paragraph "Which writes are free while a
review is in flight", and the batch-fix directive printed at every consolidation said those paths
were "free to write at any time". Both meant free of new review. But while a review runs,
consolidation refuses any change except prawduct's session files until the builder attests it with
`--tree-changed-by-builder` (#992), because that check is how a reviewer's write is caught. The
paragraph is now "Which writes cost no new review" and says that while a review runs only session
files are free of the check. The directive says "free of new review once a review is recorded".

A learnings rule from the static-content boundary review is added to `gates.md`: list every input to
a lightening declaration's authority before the first fix.

## Consumer note
While a Critic review is running, write only `.prawduct/.session-reflected` and
`.prawduct/.handoff-notes.md`. Anything else, `.prawduct/` included, means passing
`--tree-changed-by-builder` when the review is consolidated.
