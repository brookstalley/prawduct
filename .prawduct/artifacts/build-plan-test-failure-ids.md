---
artifact: build-plan
version: 2
scope: test-failure-ids
# branch: fix/test-failure-ids   <- uncomment when the branch is created
partition: serial — one chunk
program: consumer-overhead-program-2026-09.md (WS3)
related_issues:
  - "brookstalley/prawduct#792 — the record keeps a failure count, not the names"
  - "brookstalley/prawduct#680 — mostly stale (--from-junit/--no-rerun work with a declared test_command); its live residue is #792. Close #680 at merge, citing this plan"
governed_by:
  - artifact: data-model
    dispositions:
      - "a persisted format is a lock-in decision; consumer queries precede fields → ENGAGED: queries enumerated in Chunk 01 before the field is named"
  - artifact: api-contract
    dispositions:
      - "additive-first evolution → conforms; a new optional key, no existing key changes meaning; readers that don't know it ignore it"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 → ENGAGED: removes the second full-suite run spent finding failures"
last_validated: 2026-09-16
---

# Build plan — failing test ids in test evidence

## Requirements Confidence

**Level:** High

**Why:** The problem, fix and success are each one sentence in #792. The JUnit report is already
parsed in `prawduct-hook` (`test-evidence record`, the `<testsuite>` aggregation).

**Open assumptions / unknowns:**
- `[ASSUMPTION: cap the stored ids at 50, plus a truncated count | LOW impact | user can change the cap]`
- `[ASSUMPTION: a count-only source (--from-counts, --no-rerun) records no ids, and test-status says the ids are unavailable rather than printing nothing | MED impact | user can correct]`

**What would raise confidence:** N/A

## Status

- [ ] Chunk 01: Record failing test ids and print them in test-status
Context: Drawn 2026-09-16. Nothing built. Must merge before WS6 (multi-slot evidence) designs its
record shape.

## Chunk 01: Record failing test ids and print them in test-status

- **Description:** Where the JUnit report is parsed, collect `classname::name` for every `<testcase>`
  holding `<failure>` or `<error>`, across all `<testsuite>` elements. Store them in the evidence
  record as an optional list with a truncation count. `prawduct-hook test-status` prints them when
  it reports a red run.
  **Consumer queries, stated before the field:** (1) `test-status`: which tests failed? (2) the
  builder after a red run: can I re-run only those? (ids must be pytest-addressable where the runner
  is pytest); (3) WS6's multi-slot record: carried per slot unchanged; (4) the Critic's test-evidence
  check: did a named test fail? (read only, no gate).
- **Deliverables:** the ids list plus truncation count in `.test-evidence.json` (name fixed in the
  chunk, after the queries); the parse in both ingest paths (hook-run and `--from-junit`); the
  `test-status` output; the `test-evidence record` docstring updated.
- **Tests:** a JUnit fixture with 2 failures and 1 error → 3 ids recorded and printed; a
  multi-`<testsuite>` report → ids from every suite; 60 failures → 50 ids plus a truncated count
  of 10; a count-only source → no ids key, and `test-status` says ids are unavailable; a green run
  → no ids key; an old record without the key still reads (back-compat).
- **Acceptance criteria:** tests pass; an existing `.test-evidence.json` from v3.5.0 is read without
  error.
- **Done when:** acceptance passes; `/prawduct:critic`; tick; close #792 and #680.
