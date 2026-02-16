---
artifact: failure-recovery-spec
version: 1
depends_on:
  - artifact: pipeline-architecture
  - artifact: monitoring-alerting-spec
depended_on_by:
  - artifact: configuration-spec
last_validated: 2026-02-16
---

# Failure Recovery Specification

<!-- sourced: docs/self-improvement-architecture.md § Failure Modes and Safeguards, 2026-02-16 -->

## Per-Stage Failure Handling

### Context Compaction

**Failure mode:** LLM context window fills up, conversation is compressed, governance instructions may be lost.

**Recovery:**
1. SessionStart hook (`compact-governance-reinject.sh`) fires on compaction
2. Hook re-injects core governance instructions (CLAUDE.md location, Orchestrator activation requirement, skill re-read instructions)
3. Hooks themselves survive compaction (they're shell scripts, not context)
4. CLAUDE.md § "Product Build Governance (Compaction Recovery)" provides explicit re-read instructions

**Impact:** Session continues with governance intact. Some conversation context may be lost but project state persists on disk.

### Governance State Corruption

**Failure mode:** `.session-governance.json` is missing, corrupted, or contains stale data.

**Recovery:**
1. If file is missing during active build: Orchestrator recreates it from project-state.yaml (Session Resumption constraint)
2. If file is corrupted: SessionStart hook clears it on next session
3. If file has stale data: Governance hooks read it defensively — missing fields treated as not-applicable

**Impact:** Governance tracking resets. Previous session's edit counts and debt tracking are lost, but project-state.yaml preserves the actual state.

### Interrupted Onboarding

**Failure mode:** Onboarding of an existing codebase is interrupted mid-process.

**Recovery:**
1. `.onboarding-state.json` persists progress across sessions
2. `prawduct-init.py` detects `onboarding_in_progress` flag and routes to resume
3. Orchestrator loads onboarding.md and skips completed phases using cached state

**Impact:** Onboarding resumes from last completed phase. Partial artifacts may need regeneration for the interrupted phase.

### Observation Accumulation

**Failure mode:** Observations accumulate without triage, exceeding manageable volume.

**Recovery:**
1. `session-health-check.sh` detects accumulation (> 30 active files)
2. Health check flags stale `noted` observations (> 2 days)
3. Orchestrator surfaces during Session Resumption with concrete triage recommendations
4. `update-observation-status.sh` provides mechanical lifecycle transitions and archiving

**Impact:** Pattern detection may be impaired by noise. Triage reduces active set to actionable items.

### Observation Capture Failure

**Failure mode:** Framework runs but no observation files are created (Failure Mode 1).

**Recovery:**
1. Evaluation methodology Step 7 verifies observation capture (blocking check)
2. Session health check reports zero observations + recent change_log entries as warning
3. Manual observation capture via `capture-observation.sh`

**Impact:** Lost observations cannot be reconstructed. Framework misses potential learnings from affected sessions.

### Framework-Path Staleness

**Failure mode:** Framework directory moves but `.prawduct/framework-path` still points to old location.

**Recovery:**
1. Hooks fail loudly — shell errors when sourcing non-existent scripts
2. User re-runs `prawduct-init.sh` from the new framework location to update paths
3. `.claude/settings.json` hook paths need manual update (absolute paths)

**Impact:** All governance hooks and skill reads fail until paths are corrected. This is intentionally loud rather than silent.

## Partial Success Behavior

Framework stages are designed to work with partial state:
- **Discovery with partial classification:** System proceeds with what it has, discovers more during conversation
- **Artifact generation with open questions:** Artifacts note unresolved items explicitly rather than guessing
- **Build with incomplete artifacts:** Builder flags spec gaps as blocking rather than inventing behavior

## Data Integrity on Failure

- **project-state.yaml:** Git-tracked. Previous state always recoverable via git history.
- **Observation files:** Append-only directory. Individual file corruption affects only that observation.
- **Artifacts:** Git-tracked. Dependency frontmatter enables impact assessment after any change.
- **.session-governance.json:** Session-scoped throwaway. Fresh file each session; corruption has no lasting impact.
