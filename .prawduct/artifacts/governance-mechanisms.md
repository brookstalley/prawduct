---
artifact: governance-mechanisms
version: 4
depends_on:
  - artifact: pipeline-architecture
  - artifact: configuration-spec
depended_on_by: []
last_validated: 2026-02-19
---

# Governance Mechanisms

<!-- sourced: tools/governance-hook, tools/governance/ (Python module), 2026-02-19 -->

This artifact documents how governance is mechanically enforced — the hooks, state files, enforcement chains, and trace system that ensure quality and learning processes actually fire. For *what* is monitored and *why*, see `monitoring-alerting-spec.md` and `docs/self-improvement-architecture.md`. For state file schemas, see `configuration-spec.md`.

## Architecture

All governance logic lives in `tools/governance/` — a Python module with submodules for context resolution, file classification, session state management, gate decisions, edit tracking, stop validation, commit gating, prompt checks, post-compaction reinject, and trace emission. A single bash entry point (`tools/governance-hook`) resolves the framework root and delegates to the module.

```
tools/governance-hook           # Single bash entry point for all Claude Code hooks
tools/governance/
├── __init__.py        # Package init, version
├── __main__.py        # CLI: python3 -m governance <gate|track|stop|commit|prompt|compact-reinject>
├── context.py         # Path resolution (one implementation)
├── classify.py        # File classification (one implementation)
├── state.py           # Session state read/write (schema versioned)
├── trace.py           # Trace event emission + persistence + rotation
├── gate.py            # PreToolUse decisions
├── tracker.py         # PostToolUse tracking
├── stop.py            # Stop hook validation
├── commit.py          # Commit gate + session archival + cleanup
├── prompt.py          # UserPromptSubmit: activation reminder + framework version check
├── failure.py         # PostToolUseFailure: investigation reminder on unexpected errors
├── reinject.py        # SessionStart compact: post-compaction context recovery
```

### Hook Protocol

`tools/governance-hook` is the single entry point for all hooks:
1. Derives `FRAMEWORK_ROOT` from its own location (`dirname "$0"/..`)
2. Sets `PYTHONPATH` and calls `python3 -m governance <command> --root $FRAMEWORK_ROOT`
3. The module reads hook JSON from stdin (for commands that need it)
4. Exits with the module's exit code (0=allow, 2=block)

### Event Ordering

```
UserPromptSubmit  →  PreToolUse (per tool call)       →  PostToolUse (per tool call)  →  Stop
prompt               gate (Edit/Write/Read/              track                           stop
                           Task/Glob/Grep)
                     commit (Bash only)
```

On compaction: `compact-reinject` fires as a SessionStart hook.

### Hook Summary

| Subcommand | Event | Module | Can Block? |
|------------|-------|--------|------------|
| `prompt` | UserPromptSubmit | `prompt.py` | No (advisory only: activation reminder + product context validation + framework version staleness) |
| `gate` | PreToolUse (Read, Edit, Write, Task, Glob, Grep) | `gate.py` | **Yes** (exit 2) |
| `track` | PostToolUse (Edit, Write) | `tracker.py` | No (exit 0 always) |
| `failure` | PostToolUseFailure | `failure.py` | No (advisory only: investigation reminder) |
| `commit` | PreToolUse (Bash) | `commit.py` | **Yes** (exit 2) |
| `stop` | Stop | `stop.py` | **Yes** (exit 2) |
| `compact-reinject` | SessionStart (compact) | `reinject.py` | No (advisory only) |

### File Classification

`tools/governance/classify.py` classifies files into four categories (single implementation, previously duplicated across hooks):

- **Framework files:** Match patterns (`skills/`, `agents/`, `tools/`, `docs/`, `CLAUDE.md`, `README.md`, `.prawduct/artifacts/`, etc.) AND repo root equals framework root
- **Product files:** Inside the `product_dir` recorded in `.session-governance.json`
- **External repo files:** In a git repository (detected via `.git` directory walk, handling worktrees/submodules) that is neither the framework root nor an onboarded product (no `.prawduct/` directory). **Blocked** by the gate — the repo must be onboarded via `prawduct-init` first.
- **Ungoverned files:** Not in any git repo (e.g., `/tmp/`, `~/.claude/plans/`, downloaded files). Allowed without activation.

A subset of framework files are **governance-sensitive** (`skills/`, `agents/`, `tools/`, `scripts/`). These define framework behavior and trigger the PFR enforcement chain.

Git root detection results are cached by directory prefix to avoid repeated filesystem walks.

## State Files

All session state lives in `.prawduct/` within the product directory (resolved from the file's git root by `resolve_product_for_file()` in `tools/governance/context.py`). Session state uses schema versioning: reads v1 (pre-module format) and v2 (module format), always writes v2.

| File | Created by | Read by | Lifecycle |
|------|-----------|---------|-----------|
| `.orchestrator-activated` | Orchestrator step 3 | gate.py, prompt.py | Lives in product's `.prawduct/`; cleared on commit or `/clear` |
| `.session-governance.json` | Orchestrator step 4 | All modules | Cleared on commit or `/clear` |
| `.critic-pending` | tracker.py (on framework edit) | commit.py | Cleared on commit |
| `.critic-findings.json` | `record-critic-findings.sh` | stop.py, commit.py | Cleared on commit |
| `.session-trace.jsonl` | trace.py (write-through on every event) | commit.py (archival) | Cleared on commit or `/clear` |
| `traces/session-log.jsonl` | commit.py (on commit) | analyze-session-traces.sh | Persistent, append-only |
| `traces/sessions/<ts>.json` | commit.py (on commit) | analyze-session-traces.sh | Persistent, rotated to 20 |

### `.session-governance.json` Key Fields (v2 schema)

| Field | Set by | Read by | Purpose |
|-------|--------|---------|---------|
| `schema_version` | state.py | state.py | Schema versioning (2 = current) |
| `framework_edits.files[]` | tracker.py | stop.py | Edited framework files for Critic coverage |
| `governance_state.chunks_completed_without_review` | tracker.py | gate.py, stop.py | Blocks product edits until review |
| `governance_state.retroactive_review_in_progress` | Agent (via dcp-update.sh or direct) | stop.py | Suppresses chunk review debt during active review catchup |
| `directional_change.needs_classification` | tracker.py (at 3+ files) | stop.py | Blocks until DCP tier is set |
| `pfr_state.rca` | Agent (natural language) | gate.py | Unblocks governance-sensitive edits after RCA (>=50 chars) |
| `pfr_state.observation_file` | Agent (after capture-observation.sh) | stop.py, commit.py | Unblocks commit after observation |

## Enforcement Chains

### 1. Orchestrator Activation (HR9)

**Purpose:** All framework access routes through the Orchestrator.

```
Session start
  → prompt subcommand injects "activate now" message
  → gate subcommand blocks all skill reads + governed edits + research tools (Task, Glob, Grep)
  → Agent reads orchestrator/SKILL.md (whitelisted) and follows activation
  → Writes .orchestrator-activated marker to product's .prawduct/ with timestamp + "praw-active" token
  → gate subcommand validates marker (present, valid token, < 12 hours old)
  → All tools unblocked
```

### 2. Framework Version Staleness (Advisory)

**Purpose:** Detect when a product repo's framework version is outdated and advise the agent to upgrade.

```
Agent activates Orchestrator (activation marker exists)
  → prompt subcommand reads .prawduct/framework-version from session-level prawduct dir
  → Compares stored SHA against running framework's git HEAD
  → Mismatch → injects additionalContext with upgrade command (prawduct-init.py --json)
  → Agent sees advisory on next prompt submission and can offer upgrade
```

Additionally, `session-health-check.sh` produces a "Framework version mismatch" divergence signal during Session Resumption, giving the Orchestrator a second detection path.

### 3. Post-Fix Reflection (PFR)

**Purpose:** Every non-cosmetic change to governance-sensitive files requires root cause analysis before the fix and an observation after.

```
Agent attempts to edit skills/, tools/, or scripts/
  → gate.py: pfr_state.rca missing or < 50 chars → BLOCKS edit
  → Agent writes natural language RCA to pfr_state.rca (5 whys: immediate problem,
    why it happens, deeper structural cause, class of problem, prevention)
  → gate.py: rca present and >= 50 chars → allows edit
  → tracker.py: adds file to governance_sensitive_files, sets pfr_state.required: true
  → Agent makes changes, invokes Critic agent for review, then captures observation
  → Agent sets pfr_state.observation_file to observation path
  → stop.py: checks observation_file is set → allows stop
  → commit.py: checks observation file exists on disk → allows commit
```

**Gate ensures ordering** (pause before fixing) and prompts for 5-whys structure. **Critic ensures quality** (the whys are substantive, the fix targets the root cause). Each does what it's good at.

**Cosmetic escape:** Set `pfr_state.cosmetic_justification` and `pfr_state.required: false`.

**RCA universality:** Root cause analysis is required for *all* observations, not just PFR-triggered ones. The observation schema mandates `root_cause_analysis` with `five_whys` as required fields.

### 4. Directional Change Protocol (DCP)

**Purpose:** Multi-file changes get governance proportionate to impact.

```
Agent edits 3+ distinct framework files
  → tracker.py: sets directional_change.needs_classification: true
  → stop.py: blocks until classified
  → Agent reads stage-6-iteration.md, classifies as mechanical/enhancement/structural
  → Agent runs tools/dcp-update.sh classify --tier <tier> --description "..."
    (sets active, tier, plan_description, and clears needs_classification)
  → stop.py: checks per-tier requirements:
      - plan_stage_review_completed (structural only)
      - phases_reviewed_count vs total_phases (when > 1 phase)
      - observation_captured
      - retrospective_completed
      - artifacts_verified (enhancement/structural)
  → All checks pass → allows stop
```

### 5. Critic Evidence Gate

**Purpose:** Framework commits require structured Critic review evidence.

```
Agent runs `git commit`
  → commit.py activates (only for git commit commands)
  → Checks PFR observation gate (if pfr_state.required, observation file must exist)
  → Delegates to tools/critic-reminder.sh for Critic evidence check
  → All checks pass → archives session traces → cleans up session state → allows commit
  → Any check fails → BLOCKS with instructions to run Critic
```

### 6. Compaction Enforcement

**Purpose:** project-state.yaml doesn't grow unbounded.

```
Agent attempts to stop/complete session
  → stop.py: runs compact-project-state.sh --check
  → If exit code 1 (compaction needed) → BLOCKS with instruction to run compaction
  → If exit code 0 (clean) or error → allows
```

### 7. Chunk Review Gate (Product Builds)

**Purpose:** Product build chunks get Critic review before more work proceeds.

```
Builder completes a chunk, marks status as "review" in project-state.yaml
  → tracker.py: detects completed chunks without reviews
      (matches chunk_id from build_state.reviews against id from build_plan.chunks)
  → Sets governance_state.chunks_completed_without_review > 0
  → gate.py: blocks product file edits until review debt is 0
      (exempts project-state.yaml and .session-governance.json)
  → Orchestrator invokes Critic agent (separate context, reads agents/critic/SKILL.md)
  → Agent reviews chunk, runs record-critic-findings.sh
  → Orchestrator updates project-state.yaml with review entry
  → tracker.py: recalculates → chunks_completed_without_review: 0
  → Edits unblocked
```

### 8. Observation Capture Enforcement

**Purpose:** Warning/blocking Critic findings must produce observations — the learning loop can't be skipped.

```
Critic review produces findings with highest_severity >= warning
  → Agent records findings via record-critic-findings.sh
  → Agent attempts to stop/complete session
  → stop.py: reads .critic-findings.json and governance_state.observations_captured_this_session
  → If highest_severity in (warning, blocking) AND observations == 0 → BLOCKS
  → Agent captures observation(s) to framework-observations/
  → Agent increments observations_captured_this_session
  → stop.py: observations > 0 → allows stop
```

### 9. External Repository Gate

**Purpose:** Prevent governance escapes where an agent edits files in a sibling git repository without onboarding it to Prawduct.

```
Agent attempts to edit a file outside framework and onboarded products
  → classify.py: _find_git_root() walks up directories looking for .git (dir or file)
  → File is in a git repo that isn't the framework root or product_dir → is_external_repo: true
  → gate.py: _check_external_repo() fires
  → If governance active (marker exists + valid): BLOCKS with "repo not onboarded" message
  → If governance not active: BLOCKS with "activate first" message
  → Both messages steer toward two options: onboard with prawduct-init, or restart without Prawduct
  → File NOT in any git repo (temp, downloads): ungoverned, allowed
```

**Design:** The gate blocks both when governance is active and when it isn't. If Prawduct hooks are running, you're in a Prawduct context — editing unregistered repos should require conscious registration. The git-repo detection (`.git` directory/file walk) is lightweight and cached by directory prefix.

### 10. Investigation Reminder (PostToolUseFailure)

**Purpose:** When a tool fails unexpectedly, nudge the agent to investigate root cause rather than silently working around it.

```
Any tool fails (PostToolUseFailure fires)
  → failure.py: filters out routine errors (not unique, file not found, governance blocks)
  → failure.py: filters out user interrupts (is_interrupt flag)
  → Unexpected error survives filters → injects additionalContext advisory
  → Advisory prompts agent to apply root cause analysis before working around
  → Agent decides: one-off vs systemic. If systemic → captures as observation.
```

**Design rationale:** The 5-whys/PFR discipline is behavioral — under task pressure, behavioral instructions get deprioritized. This hook provides a mechanical trigger that fires exactly when the agent encounters the kind of failure that should be investigated, regardless of context (framework dev or product builds).

## Trace System

Every governance decision emits a trace event as a side effect of doing the work. Traces are local-only — they never leave the user's machine and make no network calls.

### Three-level persistence

| Level | Location | Contents | Lifecycle |
|-------|----------|----------|-----------|
| **3: In-session** | `.session-trace.jsonl` | Individual gate checks, edit tracking, stop validations (one JSON line per event, write-through) | Session-scoped, archived at commit |
| **1: Summary** | `traces/session-log.jsonl` | One line per session: file counts, gate block counts, triggers | Append-only, persistent |
| **2: Archive** | `traces/sessions/<ts>.json` | Complete session state including all trace events | Rotated to last 20 |

### Privacy model

- Traces contain governance decisions (gate results, file classifications). Never file contents, diffs, or user messages.
- Written to `.prawduct/traces/` (gitignored by `prawduct-init.py`). No network calls.
- `tools/analyze-session-traces.sh` runs locally for pattern analysis.

## Recovery

When enforcement blocks unexpectedly, the hook error message names the skill file to read. Hooks survive context compaction. See `failure-recovery-spec.md` for per-failure recovery procedures.

**Key recovery principle:** `.session-governance.json` is session-scoped throwaway. Corruption has no lasting impact — previous state is always recoverable from `project-state.yaml` and git history.
