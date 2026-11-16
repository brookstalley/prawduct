---
schema: 1
type: fix
scope: verify-coverage-stub-remedy
date: 2026-11-15
title: verify-coverage now tells you to wait for, or rerun, a record attempt instead of asking for coverage fields
closes: [brookstalley/prawduct#1181]
---
While a worktree's first `test-evidence record` is running, or after it was interrupted, the saved
record is a stub that carries no run. `prawduct-hook verify-coverage` still refused it (exit 1) but
with the wrong advice: "evidence lacks F4a schema". It now reads the record's own fields and, for a
void that carries no run's coverage, prints the same remedy `test-status` and the other gates print:
wait for a run in progress, run the suite again after an interrupted one. A void over an earlier run
that did carry coverage fields is judged on them, as before.

## Consumer note
`prawduct-hook verify-coverage` on a repo with `coverage_required: true` still exits 1 while a
record attempt is in progress or after it was interrupted; the message now tells you to wait
(`prawduct-hook test-status --wait`) or to run the suite and record it, instead of asking for F4a
coverage fields.
