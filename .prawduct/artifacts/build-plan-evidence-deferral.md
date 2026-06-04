---
artifact: build-plan
version: 2
# Distinct scope. Two items triaged from Hallucinote bug reports + confirmed
# firsthand in roi-batch-2: TST-6V2N (test-evidence writer) and STH-3W7F
# (stop-gate vs in-flight background work — DESIGN + safe floor only).
scope: evidence-deferral
depends_on: []
last_validated: null
---

## Requirements Confidence

**Level:** High

**Why:** Two bugs filed by a real product repo (`incoming-bugs/`) and reproduced firsthand this
session. Chunk 01 (TST-6V2N) has a clear, self-contained fix-shape (a new subcommand). Chunk 02
(STH-3W7F) is scoped DOWN to a design + safe docs floor because the real auto-detection fix is
fragile (investigated below).

**Open assumptions / unknowns:** Chunk 01's robust path is `pytest --junit-xml` (built-in, no
plugin) for exact counts rather than parsing the terminal summary line. Chunk 02 ships the floor,
not the auto-detector.

**What would raise confidence:** N/A.

## Status

<!-- Derived view. Mark a chunk shipped by adding a change-log entry tagged
     scope=evidence-deferral / status=shipped, then run regen-views.
     Do NOT hand-edit the checkboxes. -->

- [ ] Chunk 01: TST-6V2N — `test-evidence record` subcommand (writer for the gate's reader)
- [ ] Chunk 02: STH-3W7F — stop-gate-vs-background-work: safe docs floor + recorded design
Context: Plan authored 2026-06-04 (bug triage follow-up from `incoming-bugs/`). Built directly in
the main session (not a workflow — the two chunks share `bin/prawduct-hook` and chunk 02 is
design-informed). Governance: full suite → cumulative Critic → present for PR (wait_for_user).
THREE plans will be release-pending at merge: roi-batch, roi-batch-2, evidence-deferral.

## Scaffolding

N/A — existing repo. Test runner: `python3 -m pytest`.

## Project Structure

N/A — edits land in `bin/prawduct-hook` (new `cmd_test_evidence` + dispatch), `tests/`,
`docs/waivers.md`, `.prawduct/backlog.md` (STH-3W7F design update).

## Build Chunks

### Chunk 01: TST-6V2N — `test-evidence record` subcommand
**Type:** code
**Acceptance criteria:**
- New `prawduct-hook test-evidence record [-- <pytest args>]` subcommand (argv style mirroring
  `advisory`/`migrate-plugin`; dispatched from `main()`).
- Runs the suite via `pytest --junit-xml=<tmp> -q [extra]` and parses the JUnit XML `testsuite`
  attributes (`tests`/`failures`/`errors`/`skipped`/`time`) for EXACT counts — `passed = tests -
  failures - errors - skipped` — so counts are tied to a real run, not a hand-stamp over stale data.
- Stamps `git_sha = HEAD` (`git rev-parse HEAD`) + an ISO-8601 UTC `timestamp`, sets `command`.
- Merges the F4a half by invoking `bin/test-reference-verify --merge-into <evidence> --base <base>`
  (base from `resolve-base`) — reuse, don't duplicate, the coverage-evidence logic.
- Writes `.prawduct/.test-evidence.json` ATOMICALLY (tmp file + `os.replace`). The written record
  passes `_validate_evidence_schema` and makes `test-status` report `current` for HEAD.
- Exit code reflects the suite result (0 iff the suite passed); evidence is written either way
  (a failing run records `failed > 0`).
- Tests in `tests/test_plugin_runtime.py` (or a new `tests/test_test_evidence.py`): against a
  tiny temp repo with ONE trivial passing test → record → assert evidence has correct counts /
  git_sha == HEAD / fresh timestamp / schema-valid; a failing-test repo → `failed >= 1`, non-zero
  exit, evidence still written. Do NOT recurse into the full prawduct suite.
**Done when:** full suite green; `/prawduct:critic` (cumulative, launching session).

### Chunk 02: STH-3W7F — stop-gate-vs-background-work (design + safe floor)
**Type:** doc-only
**Acceptance criteria:**
- **Investigation (record findings):** the Stop hook (`prawduct-hook stop`) does NOT read stdin,
  so it has no `transcript_path`/`session_id`; auto-detecting a live workflow would require reading
  stdin → deriving the session dir → inspecting `subagents/workflows/*/journal.jsonl`, and even then
  `started > result` cannot distinguish a LIVE run from a CRASHED one (the journal persists after
  completion). Harness-version-dependent → NOT safe to build now.
- **Safe floor (ship) — REVISED during build:** the original plan (sanction an in-flight WAIVER
  convention) was REJECTED on investigation — waiving the Critic gate would SKIP the Critic the
  completed background work still needs, so a waiver is semantically wrong here, not just overloaded.
  The shipped floor instead clarifies in `methodology/building.md` (Gate-waivers, where `.gates-waived`
  is actually documented — NOT `docs/waivers.md`, which is the source-comment pragma) that in-flight
  background work is "wait, don't waive": SPIN is the correct behavior, the repeated block is an
  expected reminder, and the real fix is pending (`STH-3W7F`).
- **Design (record in backlog STH-3W7F):** the cleaner real fix is a self-declared `.gates-deferred`
  file (the AGENT knows it launched background work; the hook can't) that defers the gate EXACTLY
  ONCE then auto-rearms (so it can never permanently skip the Critic) — sidesteps the fragile
  auto-detection. Update STH-3W7F with this design + the detection-fragility finding.
- No runtime/behavior change in this chunk. Touches `methodology/building.md` (the floor),
  `.prawduct/backlog.md` (STH-3W7F design), and `tests/test_v5_methodology.py` (the building.md
  token-budget guardrail bumped 4450→4560 to accommodate the floor — the file sat at its prior
  ceiling, so the addition was halved first and trimming unrelated prose would violate Scope
  Discipline; rationale recorded in the test comment).
**Done when:** docs coherent; full suite green; cumulative Critic.

## Governance Checkpoints

- **Cumulative Critic** over `origin/develop...HEAD` gates the PR.
- **Full suite** run by the launching session before the Critic.

## Release note (now THREE release-pending plans)

At merge this becomes the third release-pending plan (after roi-batch, roi-batch-2). The
`develop→main` release must run `regen-views` once per scope (the pointer resolves one plan):
point it at each of roi-batch / roi-batch-2 / evidence-deferral, regen, before clearing. The
`active_build_plan` comment in `project-state.yaml` enumerates all three. (The single-pointer /
multi-pending-plan friction is itself worth a backlog item against the release tooling if it
keeps recurring.)
