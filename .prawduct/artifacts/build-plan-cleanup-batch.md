---
artifact: build-plan
version: 2
# Distinct scope. Six small, independent backlog items batched into one PR and
# BUILT IN PARALLEL via worktree-isolated workflow subagents (one chunk each),
# then integrated + cumulative-Critic'd + reflected in the launching session.
# Selected for fully disjoint file ownership so the parallel diffs apply cleanly.
scope: cleanup-batch
depends_on: []
last_validated: null
---

## Requirements Confidence

**Level:** High

**Why:** Six well-scoped backlog items, each with a clear fix-shape stated in the backlog and
re-verified during triage. Each chunk owns a disjoint file-set (see Project Structure), so they
are independently buildable and reviewable. Three are refactor/optimization/test-add (code); three
are prose-only protocol/methodology edits (doc-only).

**Open assumptions / unknowns:**
- BLD-7P3K is scoped **test-only** for this batch (the backlog's open "test vs. runtime check"
  question resolves toward test-only — proportional, and keeps it disjoint from SYN-9C4T's hook edits).
- The doc chunks (CRT-4W8M, MET-7H2D) may push their target files past the `test_v5_methodology.py`
  token-budget assertions. Budget reconciliation (`tests/test_v5_methodology.py`) is owned by the
  INTEGRATOR, not the chunk agents — so the six parallel diffs never collide on that shared test file.

**What would raise confidence:** N/A.

## Status

<!-- Derived view. Mark a chunk shipped by adding a change-log entry tagged
     scope=cleanup-batch / status=shipped, then run regen-views.
     Do NOT hand-edit the checkboxes. (Stays [ ] while release-pending=merged.) -->

- [x] Chunk 01: SYN-9C4T — extract `read_bool_yaml_key` into `lib/core.py`, call from both sites
- [x] Chunk 02: TST-5W1J — cache test-file reads in `bin/test-reference-verify` (drop O(N·T))
- [x] Chunk 03: BLD-7P3K — guard test: active build plan's Status chunk IDs parse as `### Chunk <id>:`
- [x] Chunk 04: CRT-4W8M — Critic check: exact-match assertions for "no behavior change" refactors
- [x] Chunk 05: PRR-4M9T — trim PR-reviewer goals to remove Critic overlap
- [x] Chunk 06: MET-7H2D — testing guidance: multi-hop edge-case tests
Context: Plan authored 2026-06-04. Built via a parallel workflow (6 worktree-isolated subagents,
one chunk each, disjoint file ownership); integrated, full-suite-verified, and cumulative-Critic'd
in the launching session. Governance: per-chunk targeted tests by each agent → full suite at
integration → cumulative Critic gates the PR (wait_for_user). Becomes the 4th release-pending plan.

## Scaffolding

N/A — existing repo. Test runner: `python3 -m pytest` (config: `-n auto --dist loadfile --timeout 30`).
Single-module self-checks run with `-n0` to avoid xdist contention (see TST-4P8H).

## Project Structure

Disjoint file ownership per chunk (this is what makes the parallel build safe):

- **Chunk 01 (SYN-9C4T):** `lib/core.py` (+new public helper), `lib/views.py`, `bin/prawduct-hook`, `tests/test_views.py`
- **Chunk 02 (TST-5W1J):** `bin/test-reference-verify`, `tests/test_reference_verifier.py`
- **Chunk 03 (BLD-7P3K):** `tests/test_build_plan_resolution.py` (reads `lib/core.py`, edits nothing else)
- **Chunk 04 (CRT-4W8M):** `skills/critic/review-protocol.md`
- **Chunk 05 (PRR-4M9T):** `skills/pr/review-protocol.md`, `tests/test_pr_reviewer.py`
- **Chunk 06 (MET-7H2D):** `methodology/building.md`
- **Integrator-owned (NOT a chunk):** `tests/test_v5_methodology.py` (budget assertions for building.md
  & review-protocol.md + any presence assertions for new doc content), the build plan, `project-state.yaml`.

## Build Chunks

### Chunk 01: SYN-9C4T — extract shared `read_bool_yaml_key`
**Type:** code
**Acceptance criteria:**
- Add a public `read_bool_yaml_key(path, key) -> bool` to `lib/core.py` (alongside the existing
  no-PyYAML yaml helpers ~line 108) performing the column-0 boolean scan against a YAML file.
- `is_views_enabled` (in `lib/views.py`) and `_read_bool_yaml_key` (in `bin/prawduct-hook`, which
  also serves `coverage_required`) both delegate to the new helper. Behavior is byte-for-byte preserved.
  (File and symbol kept as separate backtick tokens — `path::symbol` trips the chunk-ref parser; see BLD-8F2Q.)
- Tests in `tests/test_views.py` cover the extracted helper (true/false/missing-key/missing-file/
  malformed-line) and confirm both call sites still resolve correctly.
**Done when:** the `tests/test_views.py` suite green (that file was retired with derived views;
the helper's tests now live in `tests/test_core_yaml_keys.py`); behavior unchanged; integrated.

### Chunk 02: TST-5W1J — cache test-file contents in `bin/test-reference-verify`
**Type:** code
**Acceptance criteria:**
- `discover_tests` (or equivalent) reads each test file's contents ONCE into a dict; `_has_reference`
  runs substring matching against the cached text instead of re-opening every test file per changed file.
- Eliminates the O(N·T) re-reads; output/behavior of the verifier is unchanged (a refactor for speed).
- Existing tests in `tests/test_reference_verifier.py` still pass; add a test asserting the cache is
  built once / reads are not repeated per changed file (e.g. via a read counter or by asserting result
  parity across multi-changed-file inputs).
**Done when:** `python3 -m pytest tests/test_reference_verifier.py -n0` green; behavior unchanged; integrated.

### Chunk 03: BLD-7P3K — guard test for build-plan chunk-heading parse
**Type:** code
**Acceptance criteria:**
- New test in `tests/test_build_plan_resolution.py`: resolve the active build plan via
  `lib.core.resolve_build_plan_path`, parse its `## Status` section chunk IDs, and assert each maps to a
  parseable `### Chunk <id>:` heading (colon form, three-hash) in the plan body — so a depth/format drift
  (e.g. `#### Chunk NN:` under a `### Lane` grouping, which silently defeated the `### Chunk ` parsers and
  fail-closed chunk-type to `code`) fails LOUDLY.
- Scope: **test-only** (the runtime-check-for-any-product variant is deferred; note it in the test docstring).
- The test must PASS against the current active plan (this `build-plan-cleanup-batch.md`, which uses the
  correct `### Chunk NN:` form — dogfoods the guard).
**Done when:** `python3 -m pytest tests/test_build_plan_resolution.py -n0` green; integrated.

### Chunk 04: CRT-4W8M — Critic check: exact-match assertions for "no behavior change" refactors
**Type:** doc-only
**Acceptance criteria:**
- Add a check to `skills/critic/review-protocol.md` (under the Refactor work-type / Goal 1 area): when a
  chunk's explicit bar is "no behavior change," verify output assertions are exact-match (not substring/
  contains); if not → WARNING. Phrasing tight; match the file's existing check style.
- Keep `skills/critic/review-protocol.md` under its **3120-token** budget if possible by tightening the
  added prose. If it cannot fit, REPORT the new token count (do NOT edit `tests/test_v5_methodology.py` —
  the integrator owns the budget assertion + any presence assertion for this check).
**Done when:** `python3 -m pytest tests/test_v5_methodology.py -n0` reported (pass or budget-fail noted); integrated.

### Chunk 05: PRR-4M9T — trim PR-reviewer goals to remove Critic overlap
**Type:** doc-only
**Acceptance criteria:**
- In `skills/pr/review-protocol.md`, trim the PR-reviewer goals that overlap the Critic (the backlog
  names goals 1, 2, 4, 5, 6) down to release-specific concerns (narrative, scope, merge hygiene,
  simplification), now that the layering is explicit (Critic-chunk = local; Critic-final = synthesis;
  PR reviewer = release readiness). Preserve release-readiness coverage; this is a trim, not a gut.
- Update assertions in `tests/test_pr_reviewer.py` that pin the removed goals to reflect the new intended
  protocol structure (a deliberate contract change — document why in the change; never weaken a test that
  guards something still meant to hold).
**Done when:** `python3 -m pytest tests/test_pr_reviewer.py -n0` green; integrated.

### Chunk 06: MET-7H2D — testing guidance: multi-hop edge-case tests
**Type:** doc-only
**Acceptance criteria:**
- Add a bullet to `methodology/building.md` §Test Discipline: when tested behavior depends on a
  SUBSEQUENT invocation (next cycle, next call, next prune — accumulator/coordinator/cursor/retry),
  exercise at least one additional step beyond the immediate post-state. Tight, single bullet.
- `methodology/building.md` budget is **4560 tokens** and the file sits near that ceiling. Make the
  addition fit by keeping it tight; if it cannot fit, REPORT the new token count (do NOT edit
  `tests/test_v5_methodology.py` — the integrator owns the budget bump + rationale).
**Done when:** `python3 -m pytest tests/test_v5_methodology.py -n0` reported (pass or budget-fail noted); integrated.

## Governance Checkpoints

- **Per-chunk:** each parallel agent runs its own TARGETED test module (`-n0`) and self-verifies before returning.
- **Integration:** the launching session applies the six diffs, runs the FULL suite, and reconciles any
  `tests/test_v5_methodology.py` budget assertions for the doc chunks.
- **Cumulative Critic** over `origin/develop...HEAD` gates the PR (Principle 14 — Independent Review at the bundle level).

## Release note (becomes the 4th release-pending plan)

At merge this is the 4th release-pending plan (after roi-batch, roi-batch-2, evidence-deferral). The
`develop→main` release must run `regen-views` once per scope (the `active_build_plan` pointer resolves a
single plan — REL-4T8N is the fix for that friction). The `active_build_plan` comment in
`project-state.yaml` enumerates the release-pending set.
