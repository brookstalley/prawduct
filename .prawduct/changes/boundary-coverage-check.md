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
with its reason. A merge counts as `pr-covered` only when a boundary review read the branch from its
base and nothing but fix verification followed it. A reused scope is read through its newest add. Facts
a newer plugin wrote make the answer unevaluable (exit 3) rather than partial.

`check-releasability` prints the op's count line on every run with pending work, plus a `NOTE:` per
scope not covered, and its exit is unchanged. The PR skill's release-promotion guard runs the op and
relays it before handing back to the release process. `documentation/release-process.md` and the
release runbook say how to read the lines.

This is wave 1 of #1223 (owner ruling 2026-11-23, decision 5). It counts what a per-release boundary
review would have to cover before any review changes.

## Consumer note
Nothing changes in how you review or release. `check-releasability` prints a `boundary coverage:` line
and a `NOTE:` for each pending merge no boundary review covered, and its exit code does not move. When
`/prawduct:pr` stops at a release branch, it now runs `prawduct-hook check-boundary-coverage` and relays
what it found before handing back to your release process.
