# v5 Build Plan

## Strategy

Six chunks, dependency-ordered. Each is independently testable and leaves the framework functional. The first chunk establishes the v5 product template — everything else builds on it.

Key architectural decisions:
- **Templates first, hooks second.** Templates define what products look like; hooks enforce it. Templates can be tested independently.
- **Methodology and Critic together.** Methodology tells the builder what to do; the Critic verifies it was done. They must be coherent.
- **Migration last.** Migration transforms v4 products into v5 shape. It can only be built after the target shape is defined.

All work on `develop` branch. Nothing reaches products until merged to `main`.

---

## Chunk 1: v5 Product Template (C1 + C2 + C4 foundation)

The v5 CLAUDE.md template is the most critical artifact — it's loaded into every session. This chunk defines what a v5 product looks like.

**Deliverables:**
- `templates/product-claude.md` — v5 template. Target: <2,800 tokens (same or less than v4). Restructured:
  - Critical rules at TOP (momentum-vulnerable behaviors)
  - Work-scaled governance model (size × type, no phases)
  - Investigated changes (boundary + decision research)
  - Concise Critic instructions
  - Compact instructions section
- `templates/project-state.yaml` — v5 fields:
  - Remove `current_phase`
  - Add `health_check` section (last_full_check, last_check_findings)
  - Add `work_in_progress` section (replaces phase tracking)
  - Preserve all existing fields
- `templates/boundary-patterns.md` — NEW template for per-project contract surface documentation
- `templates/critic-review.md` — Updated for goal-based Critic scope

**Acceptance Criteria:**
- product-claude.md is <=2,800 tokens (measure with tiktoken or word-count heuristic)
- All four consolidated requirements (C1-C4) are represented in the template
- Block markers (PRAWDUCT:BEGIN/END) present and correctly placed
- Template renders correctly when placed by init
- Backward-compatible: a v4 product reading this template functions correctly even without the new hook

**Tests:**
- Token count verification for product-claude.md
- Template structure tests (markers present, sections exist)
- project-state.yaml schema tests (new fields present, old fields preserved)

---

## Chunk 2: Session Briefing + Staleness Scan (C2 + C4 core mechanisms)

The session briefing is the primary delivery mechanism for v5 governance. This chunk implements the SessionStart hook enhancements.

**Deliverables:**
- `tools/product-hook` cmd_clear enhancements:
  - Staleness scan: check test count vs. documented count, directory structure vs. architecture artifact, dependency files vs. manifest
  - Session briefing assembly: project identity, stale artifact warnings, relevant learnings, key reminders
  - Print briefing to stdout (injected as system-reminder)
  - Subagent briefing generation: assemble `.prawduct/.subagent-briefing.md` from static rules + project-preferences + active learnings

**Acceptance Criteria:**
- Session briefing prints to stdout, <400 tokens
- Staleness scan completes in <5 seconds
- Subagent briefing file generated at `.prawduct/.subagent-briefing.md`
- Existing cmd_clear functionality preserved (sync, git baseline, size warnings, preferences check)
- Graceful degradation: missing artifacts don't crash the scan

**Tests:**
- Staleness scan with various artifact states (fresh, stale, missing)
- Session briefing format and content verification
- Subagent briefing generation and content verification
- Performance test: scan completes within timeout
- Backward compatibility: existing tests still pass

---

## Chunk 3: Compliance Canary (C2 stop hook)

The compliance canary catches governance failures before session end.

**Deliverables:**
- `tools/product-hook` cmd_stop enhancements:
  - Detect: code changed but no tests added/modified
  - Detect: new dependency added without rationale
  - Detect: broad exception handling introduced (grep for `except Exception` patterns)
  - Report canary findings to stdout (informational, not blocking — existing reflection + Critic gates remain blocking)
  - Preserve existing gate logic (reflection gate, Critic review gate)

**Acceptance Criteria:**
- Canary detects all three failure modes
- Canary findings print to stdout (model sees them)
- Existing blocking gates (reflection, Critic) unchanged and still functional
- False positive rate is low — canary uses file-change heuristics, not full AST analysis
- Canary doesn't slow down session end significantly

**Tests:**
- Each canary detection (code-no-tests, new-dep-no-rationale, broad-except)
- False positive scenarios (test file renamed but not deleted, dep added with rationale)
- Existing gate tests still pass
- Integration: canary + gates work together

---

## Chunk 4: Methodology + Critic Updates (C1 + C3 + C4)

Update the guidance documents and review agent for v5.

**Deliverables:**
- `methodology/building.md` — v5 updates:
  - Work-scaled governance (size × type determines depth)
  - Investigated changes (boundary investigation, decision research, research subagents)
  - Subagent briefing reference (read `.prawduct/.subagent-briefing.md`)
  - Updated Critic section (goal-based, not checklist)
- `methodology/discovery.md` — Continuous discovery (not phase-gated)
- `methodology/planning.md` — Continuous planning, work-type-specific planning
- `methodology/reflection.md` — Learning lifecycle (provisional → confirmed → incorporated)
- `agents/critic/SKILL.md` — Goal-based scope:
  - Critic receives signals (files changed, work type, work size) and reasons about what to check
  - Explicit checks for: unreasoned major decisions, boundary investigation gaps, subagent governance gaps
  - Preserve existing checks (spec compliance, test integrity, scope, proportionality, coherence, learning/observability)
  - Framework-specific checks preserved (generality, clarity, health, pipeline coverage)
- `agents/critic/review-cycle.md` — Updated for work-scaled review
- `.prawduct/cross-cutting-concerns.md` — Updated coverage matrix

**Acceptance Criteria:**
- Methodology files are internally consistent
- Critic instructions cover all C1-C4 verification needs
- Work-scaled governance is clearly documented with examples
- Investigated changes pattern is documented for both boundary and decision research
- Learning lifecycle is documented with promotion/archival criteria
- Token counts for methodology files within budget (~2,500 each)

**Tests:**
- Scenario tests updated to reflect v5 methodology
- Cross-reference check: all Critic checks have corresponding methodology guidance

---

## Chunk 5: Migration + Sync (v4 → v5)

Make v5 deployable to existing products.

**Deliverables:**
- `tools/prawduct-sync.py` — v5 migration logic:
  - Detect v4 manifest (version field or absence of v5 markers)
  - Split learnings: `learnings.md` → active rules + `learnings-detail.md` (reference)
  - Update project-state.yaml: retire current_phase, add health_check section
  - Add new files to sync manifest (boundary-patterns.md as place_once)
  - Bump manifest version
- `tools/prawduct-init.py` — v5 file structure:
  - Place boundary-patterns.md template
  - Generate v5 sync manifest
  - Use v5 product-claude.md template
- `tools/prawduct-migrate.py` — v4→v5 migration path:
  - Version detection for v4 (has sync-manifest, no v5 version marker)
  - Run learnings split
  - Update project-state.yaml
  - Update sync manifest

**Acceptance Criteria:**
- New v5 init creates all required files in correct structure
- v4→v5 migration preserves all user content
- Learnings split correctly separates active rules from reference
- Migration is idempotent (running twice doesn't break anything)
- Auto-pull + sync + migration chain works end-to-end
- Existing v1→v4 and v3→v4 migration paths still work

**Tests:**
- Init tests for v5 file structure
- Migration tests: v4 product → v5 product (all files correct)
- Learnings split tests (various input formats)
- Idempotency tests (migrate twice)
- Existing migration tests still pass

---

## Chunk 6: Framework CLAUDE.md + Integration Validation

Update the framework's own CLAUDE.md and validate everything works together.

**Deliverables:**
- `CLAUDE.md` — Updated for v5:
  - Getting Started routing updated for v5 product structure
  - Methodology references updated
  - v5 Critic instructions
- End-to-end validation:
  - Init a fresh v5 product, verify all files correct
  - Simulate v4→v5 migration, verify all files correct
  - Verify CLAUDE.md token count meets target
  - Run full test suite, verify all pass
- `.prawduct/project-state.yaml` — Update framework state:
  - Document v5 build in change_log
  - Update build_state

**Acceptance Criteria:**
- Framework CLAUDE.md is self-consistent
- All 245+ tests pass (no regressions)
- New tests bring total to 280+ (minimum 35 new tests across chunks)
- product-claude.md template is <=2,800 tokens
- v5 product can be initialized, built in, and reviewed by Critic
- v4 product can be migrated and continues to function

**Tests:**
- Full regression suite
- Integration: init → build → Critic review → reflection cycle
- Token count verification

---

## Dependency Order

```
Chunk 1 (templates)
  ↓
Chunk 2 (session briefing) ──→ Chunk 3 (compliance canary)
  ↓
Chunk 4 (methodology + Critic)
  ↓
Chunk 5 (migration + sync)
  ↓
Chunk 6 (framework CLAUDE.md + integration)
```

Chunks 2 and 3 can be parallelized (both modify product-hook but different commands).
Chunk 4 depends on Chunk 1 (templates define what methodology describes).
Chunk 5 depends on Chunks 1-4 (migration targets the v5 shape).
Chunk 6 depends on everything (integration validation).
