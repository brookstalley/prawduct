---
schema: 1
type: chore
scope: testament-cache-areas
date: 2026-11-23
title: "Test suite: cacheable git children and testament areas (#1215, #1216)"
closes: [brookstalley/prawduct#1215, brookstalley/prawduct#1216]
---
Git children that inherit the test process's environment now run with isolated config, a fixed
date and a test identity (`GIT_TEST_ENV` in `tests/conftest.py`, applied at import), and helpers
that build their own environment start from it, so testament can cache those tests. On the runs
measured 2026-11-23, the uncacheable share fell from 49.3% to about 35% of the suite.

Tests whose commits are compared with a real-clock session stamp opt out with
`@pytest.mark.real_git_clock`, which also marks them `uncacheable`. A fixed git date made their
session span empty, so five of them passed without running the path they test. This is a stopgap
until #1218 gives git and production code one test clock. `.testament.toml` declares 13 areas, so
a run reports, times and selects tests by subsystem (`testament areas check --strict` passes).

## Consumer note
None. This changes only this repository's tests and test configuration; nothing ships in the plugin.
