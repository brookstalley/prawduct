---
schema: 1
type: feature
scope: boundary-coverage-check
date: 2026-11-23
title: check-boundary-coverage names the release-pending merges no boundary review covered
closes: []
---
A new advisory op, `prawduct-hook check-boundary-coverage`, answers one question for each release-pending
scope: was the merge that brought it in covered by a boundary review? Either at its PR (a boundary review
over the branch, followed only by fix verification), or by a batch review spanning the merge. Each scope
reads `no-judgeable`, `pr-covered`, `batch-covered`, `inner-only`, `uncovered`, `direct` or `unknown`,
with its reason. `check-releasability` prints the count and a note per merge that isn't covered, and its
exit is unchanged. This is wave 1 of #1223 (owner ruling 2026-11-23, decision 5). It counts what a
per-release boundary review would have to cover before any review changes.

## Consumer note
Nothing changes in how you review or release. `check-releasability` prints new `NOTE:` lines for merges
no boundary review covered; they are advice, and its exit code does not move.
