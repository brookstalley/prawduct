---
schema: 1
type: chore
scope: ci-pr-dedupe
date: 2026-11-25
title: A pull request from a branch of this repository no longer re-runs the suite its push already ran
---
`.github/workflows/tests.yml` triggers on `push` and `pull_request`, so a branch with an open PR ran
the suite twice. The workflow's comment said the two runs test different trees (the branch tip and
the merge result). They do not when the base was merged into the branch before the PR was opened,
which is what `/prawduct:pr` does: the merge ref and the tip are one tree, and the second run only
repeated the first.

A new `plan` job (`python tools/ci-suite.py plan`, no secret, nothing installed) now asks, for a
pull request whose head is in this repository, whether the merge commit's tree is the tree of the
head the event names. When it is, the `pool`, `pytest` and `collector` jobs of the pull request's
run are skipped and the push run of the same commit is the verdict. Everything else still runs in
full: a fork's pull request (the `plan` job is not created for one, and the runner refuses a fork
too), a base that moved and was not merged in, a checkout of some other head than the event names,
and any case where git cannot answer. The `plan` job cannot fail the run, and the jobs below it run
unless it says `true`, so it can only ever save a run. Nothing requires these checks (no branch
protection or ruleset exists), and a skipped job reports as skipped.

The workflow's "Weighed and kept" comment is rewritten to say what the pull request's run now does.
`tests/preferences/test_ci_workflow_conventions.py` pins the fork clause, the event-supplied head,
and which jobs wait on the plan; `tests/test_ci_suite.py` drives the stage against real merge
commits, one whose tree equals the head's and one whose base moved.

## Consumer note
none: this repository's own CI workflow; no governed repo reads it
