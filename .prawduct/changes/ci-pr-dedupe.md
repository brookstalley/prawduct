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

A new `plan` job (`python tools/ci-suite.py plan`, nothing installed, no pool key) now asks, for a
pull request whose head is in this repository, two things: is the merge commit's tree the tree of
the head the event names, and does GitHub's API list a `push` run of this workflow for that head
that is queued, running, or finished green or red. When both hold, the `pool`, `pytest` and
`collector` jobs of the pull request's run are skipped and the push run of the same commit is the
verdict. Everything else still runs in full: a base that moved and was not merged in, a checkout of
some other head than the event names, any case where git cannot answer, and any case where no push
run is found (a commit pushed with a workflow's own token starts none, a run can be cancelled, and
a push run not yet registered when the PR run asks lands here too, which costs one run and no
verdict). The `plan` job's token is the workflow's own with `actions: read` added at job level, in
the one step that asks; the pool key is not involved.

A fork's pull request is not skipped by this file as it stands: the `plan` job is not created for it
and the stage refuses a fork too. A pull request's workflow file is the merge commit's, so a fork
that edits this file decides its own run, and the diff shows it.

The stage always exits 0, and the job is `continue-on-error`, so a failure of the `plan` job itself
(a checkout, a runner, its time limit) does not fail the run: the jobs below it run unless it says
`true`, so it can only ever save a run. Nothing requires these checks (no branch protection or
ruleset exists), and a skipped job reports as skipped.

The workflow's "Weighed and kept" comment is rewritten to say what the pull request's run now does.
`tests/preferences/test_ci_workflow_conventions.py` pins the fork clause, the event-supplied head,
the plan job's permissions and token, and which jobs wait on the plan; `tests/test_ci_suite.py`
drives the stage against real merge commits, one whose tree equals the head's and one whose base
moved, and the push-run lookup against an injected API.

## Consumer note
none: this repository's own CI workflow; no governed repo reads it
