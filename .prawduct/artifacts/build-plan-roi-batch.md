---
artifact: build-plan
version: 2
# Explicit scope (NOT null) — sidesteps the very inference trap Chunk 02 fixes
# (BLD-4Q9X). Tag change-log entries `scope=roi-batch` when shipping each chunk
# so `regen-views` flips the checkboxes below correctly.
scope: roi-batch
depends_on: []
last_validated: null
---

## Requirements Confidence

**Level:** High

**Why:** Nine pre-triaged backlog items, each with a written fix-shape and a named file set;
two are reproducible correctness bugs, the rest are tests/docs. Scope is closed.

**Open assumptions / unknowns:** None material. The only soft spot is TST-2R7H's target
test file (the builder locates the existing stop-gate test and mirrors it, or creates a new
`tests/test_critic_gate_fallthrough.py`).

**What would raise confidence:** N/A.

## Status

<!-- Derived view. Mark a chunk shipped by adding a change-log entry tagged
     scope=roi-batch / status=shipped, then run `prawduct-hook regen-views`.
     Do NOT hand-edit the checkboxes. Chunks are INDEPENDENT (no depends-on) and
     are built by two parallel background workflows (see Build Chunks → Build model). -->

- [x] Chunk 01: CRT-3M8Q — /critic honors the build plan's per-chunk Critic mode override
- [x] Chunk 02: BLD-4Q9X — `scope: null` suppresses change-log scope inference
- [x] Chunk 03: TST-2R7H — regression coverage for non-handoff Type → gate fall-through
- [x] Chunk 04: MIG-8C3V — migrate's CLAUDE.md transform no longer leaves a leading double blank line
- [x] Chunk 05: docs-coherence batch (MET-4K8Z, MET-1T5W, MET-8N2C, MET-2D9K, DOC-2W9P)
Context: Plan authored 2026-06-03 pre-/clear. Built by two parallel workflows
(`.prawduct/roi-batch/wf-code.js` = chunks 01–04, `.prawduct/roi-batch/wf-docs.js` = chunk 05).
The workflows do the BUILD half only (fix + regression test + scoped test run, no commit, no
Critic). The launching session does the governance half: full suite → single `/critic cumulative`
→ commits → `/prawduct:pr` → archive the 9 backlog items + change-log → clear `active_build_plan`.

## Scaffolding

N/A — existing repo, no scaffold. Test runner: `python3 -m pytest`.

## Project Structure

N/A — edits land in existing trees (`lib/`, `bin/`, `skills/critic/`, `methodology/`,
`documentation/`, `tests/`).

## Build Chunks

<!-- Build model: the chunks are independent. Two background workflows build them in
     parallel against a single feature branch (`fix/roi-batch`); their file sets are
     disjoint by construction so the shared working tree never sees a same-file race.
     The per-chunk "Done when" Critic step is satisfied ONCE, cumulatively, by the
     launching session after both workflows finish — see Governance Checkpoints. -->

### Chunk 01: CRT-3M8Q — honor the per-chunk Critic mode override

- **Description:** Make critic-mode inference read the active build plan's CURRENT chunk
  `**Critic mode:**` field as a successive override, so a plan-mandated `final` no longer
  silently runs as inferred `chunk`. Prefer this fix-shape over chasing Skill-tool
  `$ARGUMENTS` threading — it is testable and matches the methodology's stated
  "successive override" intent.
- **Depends on:** none
- **Deliverables:** `lib/critic_mode.py`, `bin/prawduct-hook`, `skills/critic/SKILL.md`,
  `skills/critic/review-cycle.md`, `tests/test_critic_mode_inference.py`
- **Tests:** a plan whose active chunk declares `Critic mode: final` makes inference return
  `final` with `mode_chosen_by` reflecting the plan override.
- **Acceptance criteria:** `python3 -m pytest tests/test_critic_mode_inference.py -q` green;
  skill prose documents the now-honored override.
- **Type:** code
- **Done when:** acceptance + scoped tests pass (build half); cumulative Critic in the
  launching session (governance half).

### Chunk 02: BLD-4Q9X — `scope: null` suppresses change-log inference

- **Description:** In `lib/views.py`, distinguish "key absent" from "key present with
  null/empty" in `_parse_build_plan_frontmatter_scope`; have `_detect_active_scope` skip
  change-log inference when the key was explicitly null, so an author's `scope: null` opt-out
  is honored instead of inheriting a prior `scope=` tag.
- **Depends on:** none
- **Deliverables:** `lib/views.py`, `tests/test_views.py`
- **Tests:** `scope: null` + a change-log with a prior `scope=` entry → inference suppressed
  (no inherited scope); key-absent still infers (contrast case).
- **Acceptance criteria:** the `tests/test_views.py` suite green (that file was retired with
  derived views).
- **Type:** code
- **Done when:** acceptance + scoped tests pass; cumulative Critic in the launching session.

### Chunk 03: TST-2R7H — gate fall-through regression coverage

- **Description:** Pin that ONLY `designer-handoff` skips the stop-hook Critic gate; the Types
  `code` / `doc-only` / `cleanup` / `cumulative-final` all fall through to the default gate.
  Read the gate logic in `bin/prawduct-hook` (read-only) and mirror the existing
  designer-handoff skip test.
- **Depends on:** none
- **Deliverables:** new `tests/test_critic_gate_fallthrough.py` (or an added
  `TestNonHandoffTypesFallThroughToGate` class in the existing stop-gate test file — builder's
  call; must NOT reuse `tests/test_critic_mode_inference.py` or `tests/test_views.py`)
- **Tests:** parametrized over the four non-handoff Types, asserting the gate is NOT skipped.
- **Acceptance criteria:** the new test runs green in isolation.
- **Type:** code
- **Done when:** acceptance + scoped tests pass; cumulative Critic in the launching session.

### Chunk 04: MIG-8C3V — migrate double-blank-line fix

- **Description:** In `lib/migrate_plugin.py`, stop `apply_claude_anchor`/`_drop_generator_comments`
  from leaving two consecutive blank lines at the top of the migrated CLAUDE.md (collapse 3+
  newlines to 2, or drop the blank line left adjacent to removed generator comments). Cosmetic,
  no semantic change.
- **Depends on:** none
- **Deliverables:** `lib/migrate_plugin.py`, `tests/test_plugin_migrate.py`
- **Tests:** migrated CLAUDE.md has no leading double blank line.
- **Acceptance criteria:** `python3 -m pytest tests/test_plugin_migrate.py -q` green.
- **Type:** code
- **Done when:** acceptance + scoped tests pass; cumulative Critic in the launching session.

### Chunk 05: docs-coherence batch

- **Description:** Five prose/accuracy fixes. (a) MET-1T5W — add a "Forward-references"
  paragraph to `methodology/planning.md` documenting the `new` `path` build-plan convention.
  (b) MET-8N2C — `methodology/planning.md` ~L118: "the first item in its Done-when" →
  "prepended as step 0 in its Done-when (so existing step numbering is preserved…)". (c)
  MET-2D9K — add a `methodology/planning.md` section paralleling the build-plan `Visual change:`
  field. (d) MET-4K8Z — promote the "8-surface cascade → anticipate token-budget pressure in
  chunk plans" pattern into methodology prose (it recurred again this session). (e) DOC-2W9P —
  repoint retired file-sync paths in `documentation/post-sync-advisory-spec.md` and
  `documentation/governance-tax-followups.md` to plugin-native (`lib/advisory_store.py`,
  `hooks/hooks.json`, `bin/prawduct-hook`).
- **Depends on:** none
- **Deliverables:** `methodology/planning.md`, `methodology/building.md`,
  `documentation/post-sync-advisory-spec.md`, `documentation/governance-tax-followups.md`
- **Tests:** none (prose). The methodology files carry token-budget guardrail tests — run them
  after editing; TRIM to fit if a budget would bust (never weaken the budget test).
- **Acceptance criteria:** methodology token-budget guardrail tests green; paths in the design
  docs resolve to real plugin files.
- **Type:** doc-only
- **Done when:** guardrail tests green; cumulative Critic in the launching session.

## Early Feedback Milestone

N/A — internal framework maintenance, no interactive surface.

## Governance Checkpoints

**Commit & PR cadence:** Two parallel workflows build all five chunks (build half only — no
commits, no Critic). The launching session then: (1) runs the FULL `python3 -m pytest` suite;
(2) runs a SINGLE `/critic cumulative` over `merge-base...HEAD` — proportional, since the chunks
are small and independent; (3) resolves blocking findings; (4) commits per concern on
`fix/roi-batch`; (5) `/prawduct:pr`; (6) archives the 9 backlog items, adds change-log entries
tagged `scope=roi-batch`, and clears `active_build_plan`.

- After all chunks: `/critic cumulative` (the `/pr create` gate).
