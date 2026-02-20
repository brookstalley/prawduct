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

**Recovery:** Orchestrator recreates if missing. SessionStart hook clears corrupted files. Hooks read defensively — missing fields treated as not-applicable. See `governance-mechanisms.md` § "State Files" for who creates/reads each field.

**Impact:** Governance tracking resets but project-state.yaml preserves actual state. PFR state also resets (`required` defaults to false when missing), but governance-tracker.sh re-sets it on the next governance-sensitive edit.

### Interrupted Onboarding

**Failure mode:** Onboarding of an existing codebase is interrupted mid-process.

**Recovery:**
1. `.onboarding-state.json` persists progress across sessions
2. `prawduct-init.py` detects `onboarding_in_progress` flag and routes to resume
3. Orchestrator loads onboarding.md and skips completed phases using cached state

**Impact:** Onboarding resumes from last completed phase. Partial artifacts may need regeneration for the interrupted phase.

### Observation Accumulation

**Failure mode:** Observations accumulate without triage, exceeding manageable volume.

**Recovery:** `session-health-check.sh` detects accumulation and staleness (see `monitoring-alerting-spec.md` for thresholds). Orchestrator surfaces during Session Resumption. `update-observation-status.sh` provides mechanical lifecycle transitions and archiving.

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
1. Governance hooks are resilient — they derive `FRAMEWORK_ROOT` from their own script location (`$(cd "$(dirname "$0")/../.." && pwd)`), so they continue to find skills and tools regardless of `.prawduct/framework-path` content.
2. The `framework-path` file is still used by non-hook code (e.g., `compact-governance-reinject.sh` for product repo detection). User re-runs `prawduct-init.sh` from the new framework location to update it.
3. `.claude/settings.json` hook paths use runtime resolution and are set by `prawduct-init.py`, so they also remain correct as long as hooks are physically in the framework.

**Impact:** Hooks continue to function. `framework-path` staleness primarily affects product-repo bootstrap (CLAUDE.md instructions) and session-health-check divergence detection. Corrected by re-running `prawduct-init.sh`.

### External Repository Edit (Unregistered Repo)

**Failure mode:** Agent attempts to edit files in a git repository that hasn't been onboarded to Prawduct. Gate blocks the edit.

**Recovery:**
1. The block message provides two options: (a) onboard the repo by telling the Orchestrator to work on it (triggers `prawduct-init` automatically), or (b) restart Claude Code without Prawduct hooks if governance isn't wanted for that repo.
2. No data loss — the edit was blocked before it could execute.

**Impact:** Intentional blocking, not a failure. The block message is self-contained recovery guidance. This gate prevents governance escapes where an agent develops in a sibling repository without any quality enforcement.

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
