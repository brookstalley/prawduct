---
schema: 1
type: fix
scope: scope-record-no-clock
date: 2026-10-26
title: The test-report scope record no longer reads the clock
---

testament's result cache will not reuse a result from a test process that read the live clock.
This repo's scope record was first written from `pytest_configure`, outside any test, and it
stamped `at` with `datetime.now()`. testament charges a clock read like that to every test in the
process. Over seven days it was the only thing keeping about 300k of 577k executions from being
cacheable.

- `tests/conftest.py` `write_scope_record` no longer writes `at`. It was display-only: the reader
  quotes it in a partial-run refusal when present and already copes when it is absent. The JUnit
  report's own `timestamp` says when the run happened.
- The contract keeps `at` as an optional field, so the reader still quotes it from producers that
  write it. The contract's worked pytest producer drops it, and the field row says why.
- A writer test pins that the record carries no `at`.

## Consumer note
The worked pytest producer in `docs/test-report-contract.md` no longer writes the optional `at`
field, and the contract now says why. A clock read in `pytest_configure` happens outside any test,
so a result cache that refuses to reuse clock-reading tests charges it to every test in the run. If
you copied the producer, you can drop `at` from yours too: the JUnit report's own `timestamp` says
when the run happened. Records that still carry `at` read exactly as before.
