---
schema: 1
type: feature
scope: ci-testament
date: 2026-11-11
title: CI runs the suite on testament's pool, and on the job when it cannot
---
The owner asked on 2026-11-11 for CI to use testament and supplied a client key for it. Until
now `.github/workflows/tests.yml` ran `python -m pytest` on GitHub's runner, a different machine,
interpreter build and selection from the one a developer's `testament run` uses.

### The runner decides where the suite runs (Chunk 01)

`tools/ci-suite.py` has two stages, which the workflow runs as two jobs. The `pool` stage, given
the pool's key, downloads the pool's published CLI build from the pool's console with that key
(testament's source is private, so a public repository's job cannot install it from source),
checks it against the digest the pool names, installs it into an environment of its own, runs
`testament run --no-fallback`, and answers one word: whether the pool ran the suite. The `tests`
stage reads that word. When the pool ran the suite it runs the tests `.testament.toml` selects
out, by negating the manifest's own marker expression, so the two runs are the whole suite and
the markers are named in one file. On any other word, an empty one included, it runs the whole
suite.

With no key the `pool` stage passes and says so; a pull request from a fork is that case. A pool
that cannot give a verdict twice, a console that cannot be reached or is busy, or a run that does
not finish within ten minutes over both attempts also passes, with a warning. A pool that refuses
the key, a missing setting, a build that will not install, or an ending the runner cannot read
fails the `pool` stage: only a red job tells the owner that CI has stopped using the pool. In each of those cases
the `tests` stage still runs the whole suite, so the tree gets its verdict.

The run's summary names failing tests and never a runner.

### The workflow, its pins and its descriptions (Chunk 02)

`tests.yml` gains a `pool` job, the only one given the key, and the `pytest` job now runs after
it whatever its result. The two are separate jobs because the boundary review found that a step
is not a boundary: the first version ran pytest as a child of the process that held the key,
with the key stripped from the child's environment, and a child can read its parent's
environment from `/proc`. So the job that holds the key installs nothing from a package index
and runs no test, and the job that installs the dev extra and runs the tests is given no secret.

The conventions test holds that no workflow triggers on `pull_request_target`, that only the
`pool` job's own step names the secret, that the `pool` job has exactly its three steps, that
the `pytest` job receives one word from it and runs whatever its result, that the token is
read-only, that the addresses are repository variables, and that the pool image's Python is the
declared floor, which on the pool path is what exercises it. The norm is a new row in
`project-preferences.md`, marked as originated by the agent.

`.testament.toml`, `pyproject.toml`, `documentation/running-tests.md` (a new "In CI" section,
with how to read a warning and a failure) and `documentation/project-structure.md` describe CI
as it now runs. The repository gained the Actions secret `TESTAMENT_KEY` and the variables
`TESTAMENT_COORDINATOR` and `TESTAMENT_CONSOLE`.

### The runner reads testament's verdict (Chunk 03)

The runner was written against testament's exit codes as they stood on 2026-11-11. testament has
since frozen its exit codes and added `verdict` to its envelope, and says to key scripts on it.
The boundary review that revived the branch found the runner misreading two endings: exit 75 (the
pool could not give a verdict) read as a refused key, so every outage would have turned CI red
and pointed at the key; and a retryable exit 2 was run again even when a test had already failed,
so a failure could pass on the second attempt and vanish. Now `passed` passes; `failed` from a
failed test or an empty selection is the tree's result and is never retried; `unavailable` is
retried once, then falls back with a warning; anything else, a missing or unknown verdict
included, fails closed.

The runner also refuses a manifest whose selection it cannot complement exactly: a second `-m`,
any other pytest flag that could narrow the run, a path after `pytest`, or a `default_selection`
other than the suite's `testpaths`. Before, the tests such a manifest dropped would have run in
neither job. The pool run starts from the repo root, a console that drops the connection
mid-download is an outage, and a test holds the `pool` job's time limit above what the runner may
wait.

## Consumer note
None. This changes how this repository tests itself; nothing under `plugin/` changed.
