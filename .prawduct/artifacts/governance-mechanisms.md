---
artifact: governance-mechanisms
version: 1
depends_on:
  - artifact: pipeline-architecture
  - artifact: configuration-spec
depended_on_by: []
last_validated: 2026-02-17
---

# Governance Mechanisms

<!-- sourced: .prawduct/hooks/*.sh (6 hooks), tools/record-critic-findings.sh, tools/capture-observation.sh, 2026-02-17 -->

This artifact documents how governance is mechanically enforced — the hooks, state files, and enforcement chains that ensure quality and learning processes actually fire. For *what* is monitored and *why*, see `monitoring-alerting-spec.md` and `docs/self-improvement-architecture.md`. For state file schemas, see `configuration-spec.md`.

## Hook Lifecycle

Six hooks in `.prawduct/hooks/` enforce governance at different points in the Claude Code tool lifecycle. Each hook derives `FRAMEWORK_ROOT` from its own script location, making hooks resilient to `framework-path` staleness.

### Event Ordering

```
UserPromptSubmit  →  PreToolUse (per tool call)  →  PostToolUse (per tool call)  →  Stop
governance-prompt     governance-gate                governance-tracker              governance-stop
                      critic-gate (Bash only)
```

On compaction: `compact-governance-reinject` fires as a SessionStart hook.

### Hook Summary

| Hook | Event | Behavior | Can Block? |
|------|-------|----------|------------|
| `governance-prompt.sh` | UserPromptSubmit | If `.orchestrator-activated` marker missing, injects activation instruction into context | No (advisory) |
| `governance-gate.sh` | PreToolUse (Read, Edit, Write) | Blocks skill/template reads without activation; blocks all governed edits without activation; blocks edits without PFR diagnosis; blocks product edits with chunk review debt | **Yes** (exit 2) |
| `governance-tracker.sh` | PostToolUse (Edit, Write) | Silent bookkeeping: tracks framework/product edits, sets PFR state, triggers DCP classification at 3+ files, maintains `.critic-pending` | No (exit 0 always) |
| `critic-gate.sh` | PreToolUse (Bash) | Only activates for `git commit` commands. Blocks if PFR observation file missing; delegates to `critic-reminder.sh` for Critic evidence check. On success: cleans up all session state files | **Yes** (exit 2) |
| `governance-stop.sh` | Stop | Blocks session completion when critical debt exists (see Enforcement Chains below) | **Yes** (exit 2) |
| `compact-governance-reinject.sh` | SessionStart (compact) | After context compaction, re-injects skill file locations and governance debt summary | No (advisory) |

### File Classification

Both `governance-gate.sh` and `governance-tracker.sh` classify files into three categories:

- **Framework files:** Match patterns (`skills/`, `tools/`, `docs/`, `CLAUDE.md`, `README.md`, `.prawduct/hooks/`, `.prawduct/artifacts/`, etc.) AND repo root equals framework root
- **Product files:** Inside the `product_dir` recorded in `.session-governance.json`
- **Ungoverned files:** Everything else (e.g., `~/.claude/plans/`, temp files). Allowed without activation.

A subset of framework files are **governance-sensitive** (`skills/`, `tools/`, `scripts/`, `.prawduct/hooks/`). These define framework behavior and trigger the PFR enforcement chain.

## State Files

All session state lives in `.prawduct/` within `$CLAUDE_PROJECT_DIR`. See `configuration-spec.md` for the complete schema.

| File | Created by | Read by | Lifecycle |
|------|-----------|---------|-----------|
| `.orchestrator-activated` | Orchestrator step 3 | governance-gate, governance-prompt | Cleared on commit (critic-gate) or `/clear` |
| `.session-governance.json` | Orchestrator step 4 | All hooks | Cleared on commit (critic-gate) or `/clear` |
| `.critic-pending` | governance-tracker (on framework edit) | critic-gate | Cleared on commit (critic-gate) |
| `.critic-findings.json` | `record-critic-findings.sh` | governance-stop, critic-gate | Cleared on commit (critic-gate) |

### `.session-governance.json` Key Fields

The governance-tracker builds this file incrementally. Key fields and who sets them:

| Field | Set by | Read by | Purpose |
|-------|--------|---------|---------|
| `framework_edits.files[]` | governance-tracker | governance-stop | List of edited framework files for Critic coverage check |
| `governance_state.chunks_completed_without_review` | governance-tracker (on project-state.yaml edit) | governance-gate, governance-stop | Blocks product edits until review |
| `directional_change.needs_classification` | governance-tracker (at 3+ files) | governance-stop | Blocks until DCP tier is set |
| `directional_change.active`, `.tier`, etc. | Agent (per DCP instructions) | governance-stop | Blocks on incomplete DCP steps |
| `pfr_state.required` | governance-tracker (on gov-sensitive edit) | governance-gate, governance-stop | Triggers PFR enforcement chain |
| `pfr_state.diagnosis_written` | Agent (writes diagnosis) | governance-gate | Unblocks edits after diagnosis |
| `pfr_state.observation_file` | Agent (after capture-observation.sh) | governance-stop, critic-gate | Unblocks commit after observation |

## Enforcement Chains

### 1. Orchestrator Activation (HR9)

**Purpose:** All framework access routes through the Orchestrator.

```
Session start
  → governance-prompt.sh injects "activate now" message
  → governance-gate.sh blocks all skill reads + governed edits
  → Agent reads orchestrator/SKILL.md (whitelisted) and follows activation
  → Writes .orchestrator-activated marker with timestamp + "praw-active" token
  → governance-gate.sh validates marker (present, valid token, < 12 hours old)
  → Reads and edits unblocked
```

### 2. Post-Fix Reflection (PFR)

**Purpose:** Every non-cosmetic change to governance-sensitive files requires root cause analysis before the fix and an observation after.

```
Agent attempts to edit skills/, tools/, scripts/, or .prawduct/hooks/
  → governance-gate.sh: no pfr_state yet → BLOCKS edit
  → Agent writes pfr_state.diagnosis (symptom, five_whys, root_cause, category, meta_fix_plan)
  → Agent sets pfr_state.diagnosis_written: true
  → governance-gate.sh: diagnosis_written → allows edit
  → governance-tracker.sh: adds file to governance_sensitive_files, sets pfr_state.required: true
  → Agent makes changes, runs Critic, then captures observation
  → Agent sets pfr_state.observation_file to observation path
  → governance-stop.sh: checks observation_file is set → allows stop
  → critic-gate.sh: checks observation file exists on disk → allows commit
```

**Cosmetic escape:** Set `pfr_state.cosmetic_justification` and `pfr_state.required: false`.

**RCA universality:** Root cause analysis is required for *all* observations, not just PFR-triggered ones. The observation schema mandates `root_cause_analysis` with `five_whys` as required fields, and `capture-observation.sh` requires `--rca-symptom`, `--rca-root-cause`, and `--rca-category` for every invocation.

### 3. Directional Change Protocol (DCP)

**Purpose:** Multi-file changes get governance proportionate to impact.

```
Agent edits 3+ distinct framework files
  → governance-tracker.sh: sets directional_change.needs_classification: true
  → governance-stop.sh: blocks until classified
  → Agent reads stage-6-iteration.md, classifies as mechanical/enhancement/structural
  → Agent sets directional_change.active: true, .tier, .total_phases, etc.
  → governance-stop.sh: checks per-tier requirements:
      - plan_stage_review_completed (enhancement/structural)
      - phases_reviewed_count vs total_phases (when > 1 phase)
      - observation_captured
      - retrospective_completed
      - artifacts_verified (enhancement/structural)
  → All checks pass → allows stop
```

### 4. Critic Evidence Gate

**Purpose:** Framework commits require structured Critic review evidence.

```
Agent runs `git commit`
  → critic-gate.sh activates (only for git commit commands)
  → Checks PFR observation gate (if pfr_state.required, observation file must exist)
  → Delegates to tools/critic-reminder.sh:
      - Checks staged files for framework patterns
      - If framework files staged: looks for .critic-findings.json
      - Validates findings cover edited files, have 4+ checks, are fresh (< 2 hours)
  → All checks pass → cleans up session state → allows commit
  → Any check fails → BLOCKS with instructions to run Critic
```

### 5. Compaction Enforcement

**Purpose:** project-state.yaml doesn't grow unbounded.

```
Agent attempts to stop/complete session
  → governance-stop.sh: runs compact-project-state.sh --check
  → If exit code 1 (compaction needed) → BLOCKS with instruction to run compaction
  → If exit code 0 (clean) or error → allows
```

Session Resumption also runs compaction automatically when `session-health-check.sh` reports `STATE_WARNINGS > 0`.

### 6. Chunk Review Gate (Product Builds)

**Purpose:** Product build chunks get Critic review before more work proceeds.

```
Builder completes a chunk, marks status as "review" in project-state.yaml
  → governance-tracker.sh: detects completed chunks without reviews
  → Sets governance_state.chunks_completed_without_review > 0
  → governance-gate.sh: blocks product file edits until review debt is 0
  → Agent reads Critic skill, reviews chunk, records findings
  → Updates project-state.yaml with review entry
  → governance-tracker.sh: recalculates → chunks_completed_without_review: 0
  → Edits unblocked
```

## Recovery

When enforcement blocks unexpectedly, the hook error message names the skill file to read. Hooks survive context compaction. See `failure-recovery-spec.md` for per-failure recovery procedures.

**Key recovery principle:** `.session-governance.json` is session-scoped throwaway. Corruption has no lasting impact — previous state is always recoverable from `project-state.yaml` and git history.
