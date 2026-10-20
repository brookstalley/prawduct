---
schema: 1
type: chore
scope: testament-evidence
date: 2026-10-19
title: boundary test evidence is recorded from the Testament pool
---
- #1020, closing #1016's last acceptance item. brookstalley/testament#52 gave `testament run` a
  JUnit report, so the first `test_commands` entry is now `testament run --junit-xml {junit_xml}`
  and `prawduct-hook test-evidence record` ingests the pool's run. The pytest half took about a
  minute on the pool, against about 7.5 minutes locally (measured 2026-10-19).
- The pool selects out tests it cannot run, so on its own it would have recorded a subset as the
  suite. A third entry runs exactly those here: `requires_history` (one test), and a new sibling
  marker, `requires_local_cache`, on `TestSilentAgainstThisRepo`, whose full assertion needs this
  clone's backlog cache and which skipped on every runner. Counts reconcile with the local run:
  9,145 passed and 17 skipped either way. `.testament.toml` deselects both markers.
- Checked live, not inferred:
  - Pool unavailable: a runner restart mid-run made testament fall back to this machine, and the
    recorder took that run.
  - No result: testament exits 2 and deletes the report, and the recorder refuses with exit 2 and
    writes no evidence.
  - Partial report: the recorder's existing per-command rule covers it. A non-zero exit with no
    failing test in the report is refused, and testament's `population_mismatch` is exactly that.
- `documentation/running-tests.md`'s "Evidence still comes from the recorder" section, stale since
  testament#52, is rewritten as "Recording evidence".
- Recording now needs `testament` installed (any command that cannot start fails the record).
  `running-tests.md` and the README say so, and name the by-hand route for a machine without it:
  run pytest and the node suite, then pass both reports to one `record --from-junit` call.

## Consumer note
none: prawduct's own test recording; nothing changes for repos using the plugin
