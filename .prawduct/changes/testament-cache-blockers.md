---
schema: 1
type: chore
scope: testament-cache-blockers
date: 2026-11-23
title: "Test suite: one clock for git and the plugin, in-process hook calls (#1218)"
closes: [brookstalley/prawduct#1218]
---
The suite now runs git and the plugin on one clock. `lib/clock.py` is the one owner of "now" for
the stamps the plugin writes and later compares: evidence facts, `.session-start`, ledger events,
backlog syncs and advisory transitions. `tests/conftest.py` pins that clock and git's dates to one
instant through `PRAWDUCT_TEST_ONLY_FROZEN_NOW`, so a commit made after a session starts reads as
part of that session. A test about the order of moments moves both clocks together. Which clock a
read uses is decided by what it is compared with. A real file mtime or another process's start
stays on the wall clock, and `tests/test_clock.py` lists each such read with its reason.

This supersedes the `@pytest.mark.real_git_clock` stopgap and the `GIT_TEST_ENV` dict from the
`testament-cache-areas` change. The tests that carried the marker are cacheable again and still
reach the committed-work path. Children that need a scrubbed environment build it with
`conftest.scrubbed_env`, which carries `TEST_ENV`, git's isolation and the suite's clock. A guard
test refuses a new hook child started with a hand-built environment.

The heaviest hook tests call `prawduct-hook` in-process (`tests/_hook_inproc.py`), so the only
children they start are git's, which testament can vouch for. `.testament.toml` declines the tests
that read this checkout's own git history on purpose.

## Consumer note
The scratch repository the `.gitignore` check creates used to run its git with every `GIT_*`
variable dropped. It now drops only the ones that name a repository (`GIT_DIR`, `GIT_WORK_TREE`,
`GIT_INDEX_FILE` and the like), so your identity and any git config you give in the environment
(`GIT_CONFIG_*`) apply to it, as they do to your own git.
