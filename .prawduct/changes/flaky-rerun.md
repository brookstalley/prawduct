---
schema: 1
type: feature
scope: flaky-rerun
date: 2026-10-26
title: One flaky test costs one test's rerun, and the retry cannot hide a race the branch made
closes: [brookstalley/prawduct#1087]
---

#1087. `test-evidence record` needed a green run of the exact tree, so when one timing-bound test
failed under load, the only ways to clear the gate were another full suite run or `--degraded`,
which the gates read as stale. On a repo with an 18-minute suite, that lost two of six boundary
runs in one session. Now a flake costs one test's rerun. The rerun is recorded rather than
hidden, and it is judged against the branch's diff, which a test runner cannot see.

### Chunk 01: flakes are recorded

- A JUnit `<testcase>` with `<flakyFailure>`/`<flakyError>` and no final `<failure>`/`<error>`
  is Surefire's mark for a test that failed and then passed on the runner's retry. It counts as a
  pass and carries a `flaky` entry: id, first failure text (bounded), the number of failed
  attempts, the source, and the test file where the report names one. `<rerunFailure>` sits beside
  a final `<failure>`, so that test failed every attempt and stays failed.
- `flaky` is capped and sorted, and omitted when nothing flaked. It is carried by the record, the
  `test-run` fact and a restamp. It is kept out of the evidence schema, as `failed_tests` is: it
  is printed and carried, and a malformed value never moves a verdict.
- The record line prints `passed only on retry:`. `test-status` prints one `flaky:` line per
  flake after its verdict, and the exit code is unchanged.
- pytest-rerunfailures writes no such marker (pytest's JUnit writer drops its `rerun` reports),
  so its retries stay invisible to `--from-junit`. Corrected from #1087, which listed it.

### Chunk 02: `record --rerun-failed[=N]`

- After a live run, the recorder retries only the failing tests, by pytest node id, up to N times
  (default 1, at most 5). The retries run inside the run's tree bracket, so an edit during a
  retry still withholds `evidence_tree`. A retry that passes turns a failure into a pass carrying
  a flake (`source: "rerun"`). A test that fails every attempt, or is skipped on retry, stays
  red.
- A declared command is retried only through its own template: `test_rerun_command:`, or
  `test_rerun_commands:` aligned by position with `test_commands:` (`none` to opt a command
  out), with `{junit_xml}` and `{pytest_node_ids}`. Appending ids to a command that already names
  a selection would rerun all of it. The fallback pytest path builds its own rerun. Templates are
  checked before any suite runs.
- Not retried, with the output saying which: more than 5 failures (a broken run), a failure
  with no test id, a command with no template, or an id naming no file in the repo. The flag is
  refused with `--from-junit`, `--from-counts` and `--no-rerun`, which run nothing.

### Chunk 03: flakes are judged against the branch

- Each flake is marked `touched` when the branch's changed files (the coverage verifier's base
  and set) include its test file. The file comes from the report, or is resolved from pytest's
  classname. `null`, meaning the file or the diff could not be read, is treated as touched by
  every policy.
- `flaky_policy: accept | warn | block` (default `warn`). `block` leaves a touched flake failed,
  so the record is red and the exit status nonzero. A restamp is not judged again. An unknown
  value is refused before any run.
- `test-status` tags each flake `[touched by this branch]`, `[branch touch unknown]` or
  `[outside this branch's diff]`. The boundary Critic warns on the first two under `warn`, and
  the rule is pinned to the printed tags.
- A flake in an unchanged test file that covers changed code is not yet treated as touched:
  #1088.

### Chunk 04: flakes reach the handoff and the PR

The session handoff gains a "Flaky Tests" section. The PR payload's `test_evidence` section
carries the `flaky:` lines, and `/prawduct:pr` lists them in the PR body under "Passed only on
retry". The project-state keys reference, the state template, `test-report-contract.md` and
`building.md` name the new flag and keys.

## Consumer note
When one test fails under load, `prawduct-hook test-evidence record --rerun-failed` retries only
the failures instead of the whole suite. A test that passes on retry is recorded as a flake, not
hidden in the green. With a declared `test_command:`, add a `test_rerun_command:` that takes
`{junit_xml}` and `{pytest_node_ids}` (`test_rerun_commands:`, one per entry, for
`test_commands:`). Flakes are judged against your branch's diff: under the default
`flaky_policy: warn`, a flake in a test the branch changed draws a Critic warning, and
`flaky_policy: block` keeps it failing. Reports that mark a runner's own retries
(`<flakyFailure>`, Maven Surefire's convention) are read the same way. `test-status`, the
session handoff and the PR body now list flakes.
