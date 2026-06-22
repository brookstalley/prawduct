---
artifact: build-plan
version: 2
scope: test-evidence
depends_on: []
last_validated: null
---

<!-- Bundle: TST-4K2P (spine) + TST-7M3K + TST-2H9P — the test-evidence `record`
     cluster. Picked together (one PR) for review economy, not a shared
     abstraction: a code survey (2026-06-22) established the three legs are
     independent fixes that happen to share the `bin/prawduct-hook test-evidence
     record` surface. See "Survey findings that reshaped this plan" below. -->

## Requirements Confidence

**Level:** High

**Why:** A full code survey (the writer, the freshness gate, every consumer, and
the guarding tests) verified each leg against the real implementation before this
plan was written; the spine's original premise was found inaccurate and the user
chose the corrected direction (retire the misleading field; keep the gate
timestamp-based). The remaining choices are well-scoped and listed below as
vetoable assumptions.

**Open assumptions / unknowns:**
- [ASSUMPTION: TST-4K2P removes `git_sha` from the record entirely rather than replacing it with an "honest" descriptor field | LOW impact | user can override — the field is dead-read by all runtime consumers, and `timestamp` already provides temporal ordering, so a replacement breadcrumb earns no consumer]
- [ASSUMPTION: TST-7M3K adds a `--from-junit <path>` ingest mode (reporter's option 1) rather than making `record` the canonical runner that replaces the builder's run (option 2) | MED impact | user can override — option 1 is surgical and composes with the existing flow; option 2 restructures the build cycle's Verify step]
- [ASSUMPTION: TST-2H9P scope is "loud-fail + document the existing `tests_dirs:` knob," not a new layout auto-detection engine | MED impact | user can override — the knob already exists and is wired into the overlay; the genuine residual is that zero test-discovery fails *silently* into an empty evidence half]
- [ASSUMPTION: passing `--from-junit` together with `test_command:`/trailing `-- pytest args` is rejected as a conflicting combination | LOW impact | user can override]

**What would raise confidence:** N/A.

## Survey findings that reshaped this plan

The code survey (kept in conversation; key receipts below) corrected the backlog's
stated premises. Builders of each chunk should read this before starting:

1. **`git_sha` is dead-read.** It is written by `test-evidence record`
   (`bin/prawduct-hook`, the record-dict assembly) but **no runtime code reads it**
   and it is **not** in the evidence schema. Its only other appearances are a
   docstring, and the one-line record summary printed to the agent.
2. **The freshness gate is timestamp-based, not SHA-based.** `tests_are_current`
   in `lib/gates.py` decides fresh-vs-stale by `evidence_ts >= session_start`. Its
   docstring states content-fingerprinting "was removed pre-v1.4 after chronic
   false positives." The observed false-positive "stale" WARNING comes from the
   **PR-reviewer agent eyeballing the `git_sha` field**, not from `test-status`.
   → Therefore TST-4K2P is *retire the misleading field + retarget the review
   protocols at `test-status`*, NOT *re-introduce content-hashing* (that would
   reverse a deliberate decision).
3. **TST-7M3K is confirmed real.** `record` runs the suite itself via
   `subprocess.run` and cannot ingest an existing report.
4. **TST-2H9P is mostly already shipped.** The `tests_dirs:` knob exists and is
   threaded `record` → `bin/test-reference-verify --tests-dir`. The residual gap:
   when discovery finds zero tests (monorepo without the knob set), the empty
   `changes_referenced`/`tests_executed` halves are written **silently**, producing
   a false missing-coverage downstream.

## Status

- [ ] Chunk 01: Retire the misleading `git_sha` — freshness is `test-status`, period
- [ ] Chunk 02: `--from-junit` ingest — end the double-execution of the suite
- [ ] Chunk 03: Loud-fail on empty test discovery + document the `tests_dirs:` knob
Context: ALL THREE CHUNKS COMPLETE. Ch01 (50c8ecb): `git_sha` retired; PR/Critic
protocols retargeted at `test-status`; obsolete "record AFTER commit" learning
replaced. Ch02 (eeb4122): `record --from-junit <report>` ingests an existing JUnit
run instead of re-running the suite (ends the double-execution). Ch03: verifier
fails LOUD when zero tests are discovered while judgeable Python files changed
(naming the `tests_dirs:` knob) instead of silently writing empty halves, and
`record` now forwards the verifier's stderr; the `tests_dirs:` knob was already
documented (hook docstring + Verify line), so no further building.md edit was
needed (it's at its token ceiling) — the warning message is the actionable doc.
1368 tests pass (3 new). Cumulative Critic = the `/prawduct:pr create` gate; backlog
TST-4K2P/7M3K/2H9P stay `promoted` until the PR ships them (user drives `/pr`).

## Scaffolding

N/A — this modifies existing framework machinery in an established repo. Test
runner, coverage tooling, and project structure already exist (`tests/`,
pytest-xdist, `python3 bin/prawduct-hook`). No new dependencies.

### Verification Strategy

Beyond the unit suite: exercise the **repo-local** hook directly
(`python3 bin/prawduct-hook test-evidence record …` and `… test-status`) — per the
learning that the bare `prawduct-hook` on PATH is the released plugin cache and
shows stale behavior. For Chunk 02, verify a single suite run (not two) by
observing process behavior / timing. Confirm `test-status` still reports `current`
on a freshly-recorded clean tree after each chunk.

## Build Chunks

### Chunk 01: Retire the misleading `git_sha` — freshness is `test-status`, period

- **Description:** Remove the dead-read, actively-misleading `git_sha` identity
  from the test-evidence record, and retarget the review protocols so freshness is
  determined *only* by `prawduct-hook test-status` — never inferred from a commit
  field. This is the keystone: it establishes the "freshness = test-status"
  contract that the rest of the bundle and its consumers rest on. This is a
  *project-wide concept* threaded across surfaces; they are enumerated below so the
  chunk's true size is visible up front (planning.md "Enumerate the surfaces").
- **Depends on:** none
- **Artifacts consumed:** this plan ("Survey findings"); `methodology/building.md`
  (Verify section, for the freshness-ordering note)
- **Deliverables (enumerated surfaces):**
  - `bin/prawduct-hook` — remove `git_sha` from the record-dict assembly in the
    `test-evidence record` handler; drop the `git rev-parse HEAD` call that feeds
    it; reword the record-summary log line that prints `@ {git_sha}`; update the
    handler docstring that explains the `git_sha = HEAD` rationale.
  - `tests/test_plugin_runtime.py` — the `git_sha`-assertion in
    `test_passing_suite_writes_schema_valid_evidence` encodes the behavior being
    removed; renegotiate the contract in the open (per the learning): assert
    `git_sha` is **absent** from the written record, with a comment citing the
    removal rationale. Keep every other assertion in that test.
  - `skills/pr/review-protocol.md` — the Merge-Hygiene test-evidence bullet: state
    that freshness is `prawduct-hook test-status` (exit 0/1) **only**; do not infer
    staleness from any commit/SHA field in the evidence.
  - `skills/critic/review-protocol.md` — Goal 1 ("Nothing Is Broken") test-status
    line: same clarification.
  - `skills/critic/SKILL.md` — align any `.test-evidence.json` reading guidance
    that references a commit/SHA field.
  - `.prawduct/learnings.md` — the "Record test-evidence AFTER committing" rule was
    a workaround for the `git_sha` lag; it is now obsolete (timing no longer affects
    a removed field). Update/retire it transparently, pointing at this change.
- **Tests:** Update `test_passing_suite_writes_schema_valid_evidence` (absence
  assertion). Confirm `TestValidateEvidenceSchema` cases still pass (git_sha was
  never required, so schema is unaffected). Confirm `test_record_makes_test_status_current`
  still passes (freshness path untouched).
- **Acceptance criteria:** `python3 -m pytest -q` green; `git_sha` appears nowhere
  in `bin/`, `lib/`, `hooks/`, `skills/`, `methodology/` except (optionally) a
  historical note; a fresh `python3 bin/prawduct-hook test-evidence record` writes a
  record with no `git_sha` and `… test-status` reports `current`.
- **Type:** code
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run (infers `chunk`) and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status (tagged change-log entry, `scope=test-evidence`)

### Chunk 02: `--from-junit` ingest — end the double-execution of the suite

- **Description:** Add a `--from-junit <path>` flag to `test-evidence record` that
  ingests a JUnit XML the builder already produced instead of re-running the suite.
  Default (no flag) keeps today's run-the-suite behavior, so existing callers are
  unaffected. Update the build cycle's Verify guidance to the single-run flow.
- **Depends on:** Chunk 01
- **Artifacts consumed:** this plan ("Survey findings"); `methodology/building.md`
  (Verify section)
- **Deliverables:**
  - `bin/prawduct-hook` — in the `test-evidence record` handler: add
    `--from-junit <path>`; when present, short-circuit before the runner branch,
    read+parse the provided JUnit XML (reusing the existing multi-`<testsuite>`
    count-aggregation path), and error cleanly on a missing or malformed file.
    Reject `--from-junit` combined with `test_command:` or trailing `-- pytest args`
    (conflicting sources) with a clear usage error, mirroring how extras are
    rejected today when `test_command:` is set.
  - `methodology/building.md` — Verify section: document the single-run flow
    (builder runs the suite once with `--junit-xml=<f>`, then
    `test-evidence record --from-junit <f>`), replacing wording that implies
    `record` itself re-runs.
- **Tests:** Add `--from-junit` coverage in `tests/test_plugin_runtime.py`:
  happy path (passing-suite XML → record written, **no** subprocess run — assert via
  a patched/observed runner), missing file → clean non-zero error, malformed XML →
  clean error, failing-suite XML → record reflects failures and the command exits
  non-zero. Existing run-based tests (`test_declared_test_command_is_run`,
  `test_multi_suite_junit_report_is_aggregated`, etc.) stay green on the default path.
- **Acceptance criteria:** `python3 -m pytest -q` green; with `--from-junit`, no
  pytest subprocess is spawned (observed); a malformed/missing file fails loudly,
  not silently.
- **Type:** code
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run (infers `chunk`) and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status (tagged change-log entry, `scope=test-evidence`)

### Chunk 03: Loud-fail on empty test discovery + document the `tests_dirs:` knob

- **Description:** Close the TST-2H9P residual: when the F4a overlay discovers zero
  test files under the resolved tests dirs, emit a clear WARNING that names the
  `tests_dirs:` knob instead of silently writing empty
  `changes_referenced`/`tests_executed` halves (which read downstream as false
  missing-coverage). Document the existing `tests_dirs:` knob where test config is
  described. Last chunk → its review is the one cumulative pass and the PR gate.
- **Depends on:** Chunk 01, Chunk 02
- **Artifacts consumed:** this plan ("Survey findings")
- **Deliverables:**
  - `bin/test-reference-verify` — when test discovery yields zero files under the
    resolved `--tests-dir` set, emit a loud WARNING to stderr naming the
    `tests_dirs:` knob (do not silently proceed to empty halves). No behavior change
    when discovery finds tests.
  - `bin/prawduct-hook` — surface that warning through the `record` overlay
    invocation so the operator sees it at record time.
  - `methodology/building.md` — document the `tests_dirs:` knob (whitespace-separated
    test roots; needed for engine-subdir / monorepo layouts) in the Verify section
    alongside `test_command:`.
- **Tests:** Add a zero-discovery test in `tests/test_reference_verifier.py` (or the
  runtime suite) asserting the warning fires and is visible. Existing
  `test_default_remains_single_tests_dir` and `test_tests_dirs_forwarded_to_coverage_overlay`
  stay green.
- **Acceptance criteria:** `python3 -m pytest -q` green; a `record` run whose
  tests dir contains no tests prints a knob-naming WARNING (not a silent empty half).
- **Type:** cumulative-final
  <!-- Last chunk of a single-PR plan: its own review IS the one
       `/critic cumulative` against merge-base...HEAD (the PR gate). Commit the
       chunk first, then run cumulative once — no separate `final`. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed and chunk marked `[x]` in Status (tagged change-log entry, `scope=test-evidence`)
  3. Backlog hygiene: update TST-4K2P, TST-7M3K, TST-2H9P via `/prawduct:backlog`
     (TST-4K2P → shipped with a note that the fix was "retire git_sha," not
     content-hashing; the others → shipped)
  4. `/prawduct:critic cumulative` run against `merge-base...HEAD` and blocking
     findings resolved — this is the structural gate for `/prawduct:pr create`.

## Early Feedback Milestone

**Milestone chunk:** Chunk 01
**What the user can do:** After Chunk 01, the misleading `git_sha` is gone and a
fresh `record` → `test-status` cycle no longer produces an eyeballable stale signal
— the core user-facing pain (false-positive "stale" WARNINGs) is resolved at the
first chunk. Chunks 02–03 remove the double-cost and the monorepo silent-failure.

## Governance Checkpoints

**Commit & PR cadence:** Commit per chunk after `/prawduct:critic` (chunk mode)
passes on Chunks 01–02; on Chunk 03 commit first, then run the one
`/prawduct:critic cumulative` (its review AND the `/prawduct:pr create` gate). One
PR for the whole bundle (review economy — P0).

- After Chunk 01: per-chunk Critic (keystone — confirms the "freshness = test-status"
  contract is coherent across the writer and both review protocols before later
  chunks build on it).
- After Chunk 03: cumulative Critic over the full branch — the release-readiness pass.
