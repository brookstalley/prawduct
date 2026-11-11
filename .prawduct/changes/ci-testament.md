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

`tools/ci-suite.py` is what the workflow's test step calls. A job that holds the pool's key
downloads the pool's published CLI build from the pool's console with that key (testament's
source is private, so a public repository's job cannot install it from source), checks it against
the digest the pool names, installs it into an environment of its own, and runs `testament run
--no-fallback`. The job then runs the tests `.testament.toml` selects out, by negating the
manifest's own marker expression, so the two runs are the whole suite and the markers are named
in one file.

A job without the key runs the whole suite on the job; a pull request from a fork is that case.
A pool that cannot be reached, loses the run twice, or does not finish within the runner's wait
also runs the suite on the job, with a warning, and the job takes the suite's result. A pool that
refuses the key, a missing setting, or a build that will not install runs the suite on the job
and fails the job whatever the suite says: only a red job tells the owner that CI has stopped
using the pool. An end the runner does not recognise is treated as a refusal.

No test process and no installer is given the key or the pool's addresses. The run's summary
names failing tests and never a runner.

### The workflow, its pins and its descriptions (Chunk 02)

`tests.yml` hands the key, the two addresses and the branch name to the test step alone. The
conventions test now holds that no workflow triggers on `pull_request_target`, that the secret
is named only in that step's environment, that the job's token is read-only, that the addresses
are repository variables, and that the pool image's Python is the declared floor, which on the
pool path is what exercises it. The norm is a new row in `project-preferences.md`, marked as
originated by the agent.

`.testament.toml`, `pyproject.toml`, `documentation/running-tests.md` (a new "In CI" section,
with how to read a warning and an error) and `documentation/project-structure.md` describe CI as
it now runs. The repository gained the Actions secret `TESTAMENT_KEY` and the variables
`TESTAMENT_COORDINATOR` and `TESTAMENT_CONSOLE`.

## Consumer note
None. This changes how this repository tests itself; nothing under `plugin/` changed.
