---
artifact: build-plan
version: 2
scope: failing-test-ids
branch: fix/792-failing-test-ids
depends_on:
  - artifact: boundary-patterns
governed_by:
  - artifact: api-contract
    dispositions:
      - "whole-surface semantic versioning; persisted data independently schema-versioned → conforms: `failed_tests` is an optional key on `.test-evidence.json`, which carries no schema version; readers that predate it never look it up"
      - "exit codes are the contract → conforms: `test-evidence record` and `test-status` keep every exit code; only the printed reason gains the names"
      - "additive-first evolution → conforms: one new optional record key; no flag, exit code or existing key changes meaning"
  - artifact: data-model
    dispositions:
      - "governance verdicts come from the append-only fact ledger, never mutable model-written state → inapplicable, because `.test-evidence.json` is not on the fact ledger and the new key feeds no verdict (a record with `failed > 0` is refused before the names are read)"
      - "facts are immutable and append-only → inapplicable, because no fact is written"
      - "two stores, two lifetimes → conforms: the names live in the per-worktree gitignored record beside the counts they explain"
      - "derived views are disposable and never authoritative → inapplicable, because no view is added or read"
      - "a governance document reaches a terminal state, never deleted → conforms: this plan is archived at the release, not deleted"
      - "every issue written to the backlog conforms to the §1 title rules → inapplicable, because no issue is written (#792's close at merge changes status only)"
      - "a fact written by a newer schema is a loud block → inapplicable, because no fact is written"
      - "backlog_service_repo selects the authoritative backlog → conforms: #792 closes through /prawduct:backlog on the Issues backend"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 → conforms: the change removes a whole-suite re-run whose only purpose was learning which tests failed"
      - "proportionality ratchets both ways → inapplicable, because no control is added or removed"
      - "review rigor is stage-keyed → inapplicable, because no chunk changes a severity or a stage"
      - "state-file growth is advisory, never a block → conforms: the list is capped, so a mass failure cannot grow the record without bound"
partition: serial — one chunk over two modules
last_validated: 2026-09-23
lifecycle: completed
archived: 2026-09-24
released_in: v3.6.1
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

# Build plan — keep the failing test names, not just the count (#792)

## Requirements Confidence

**Level:** High

**Problem:** `test-evidence record` writes `failed: 2` and nothing else about the failures.
`test-status` then exits 1 with no names, and the junit report the run produced is deleted. On
2026-09-11 finding two failures cost a second full-suite run (about 10 minutes under load).

**Success:** after a run with failures, `test-status`, the `record` output line and the PR review
payload all name the failing tests, so nobody re-runs the suite to learn which ones broke.

**Out of scope:** keeping the junit report on disk (the names are what was missing; the report is
a temp file on purpose); failure messages or tracebacks; per-tree history (#653, next plan).

`[DECISION: store names only, capped at 100, as `classname::name` (or `name` when a case has no
classname) | the record feeds gates and must stay small, and 100 names is far past the point where
a run is "broadly broken" rather than "these few broke"; `classname::name` is built from junit's
own attributes (with fallbacks for reporters that omit one), and building a pytest node id would
make the framework Python-specific
| vetoable]`

`[DECISION: absence of `failed_tests` means "no per-test ids were available" (a pass,
`--from-counts`, a summary-only suite), never "nothing failed" — `failed` stays the count of
record | boundary-patterns.md: "a new field has to name its absent-case semantics"; a reader that
took absence as a pass would contradict the counts | vetoable]`

`[DECISION: the names reach readers through `_load_test_evidence`'s reason string | it is the one
prologue both evidence readers share, and `test-status`, the PR-gate transfer and the PR review
payload all print that reason, so one edit reaches all three | vetoable]`

## Chunk 1: record and print the failing test ids

**Delivers:**
- `cmd_test_evidence` collects the id of every leaf `<testcase>` carrying `<failure>` or `<error>`,
  in report order, across all roots, and writes up to 100 as `failed_tests` when there is at least
  one.
- `--no-rerun` carries the prior record's `failed_tests` forward, like `degraded`: a restamp
  reuses the counts, so it has to reuse the names that explain them (boundary-patterns.md sweep
  rule).
- The `recorded:` line names up to 10 failing ids and says how many more the record holds.
- `_load_test_evidence`'s failing-record reason names up to 10 ids and how many more exist.
- `failed_tests` deliberately kept OUT of the evidence schema: it is only printed, and validating its
  type would let a malformed value turn a passing record stale (review R-1 of the chunk's cumulative).
- `boundary-patterns.md`'s `.test-evidence.json` entry names the key and its absence meaning.

**Done when:**
- Tests cover: a run with failures and errors records both, in order; a passing run writes no key;
  `--from-counts` writes no key; a summary-only suite with failures writes no key; the cap holds at
  100 with `failed` still the true count; restamp carries the names; `test-status` prints names and
  "N more"; the `recorded:` line prints names.
- Each new test is seen red against the pre-fix code.
- Targeted tests green; one `/prawduct:critic`.

## Status

- [x] Chunk 1: record and print the failing test ids
