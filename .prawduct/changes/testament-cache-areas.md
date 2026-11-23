---
schema: 1
type: chore
scope: testament-cache-areas
date: 2026-11-23
title: "Test suite: cacheable git children and testament areas (#1215, #1216)"
closes: [brookstalley/prawduct#1215, brookstalley/prawduct#1216]
---
Every git child the test suite spawns now runs with isolated config, fixed dates and a test
identity (`GIT_TEST_ENV` in `tests/conftest.py`), so testament can cache those tests. The
uncacheable share of the suite fell from 49.3% to 33.9% on the measured run. `.testament.toml`
declares 13 areas, so a run reports, times and selects tests by subsystem.

## Consumer note
None. This changes only this repository's tests and test configuration; nothing ships in the plugin.
