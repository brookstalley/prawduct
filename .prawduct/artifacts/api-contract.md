---
artifact: api-contract
version: 1
depends_on:
  - artifact: product-brief
  - artifact: data-model
depended_on_by: []
last_validated: 2026-02-16
---

# API Contract

<!-- sourced: docs/high-level-design.md § Skill Interaction Model, Artifact Format, 2026-02-16 -->
<!-- sourced: docs/skill-authoring-guide.md, 2026-02-16 -->

Prawduct's `exposes_programmatic_interface` characteristic is internal — skills define contracts consumed by other skills within a single LLM context. This is not a REST API or library interface; it is a structured interaction model mediated by shared files.

## Skill Interaction Model

### Execution Model

The LLM operates under one skill's instructions at a time. The Orchestrator (C1) is the default active skill and manages transitions.

### Interaction Patterns

| Pattern | Mechanism | Example |
|---------|-----------|---------|
| Skill switching | Orchestrator loads another skill's instructions | "Read skills/domain-analyzer/SKILL.md" during classification |
| Shared state | All skills read/write project-state.yaml | Domain Analyzer writes classification; Artifact Generator reads it |
| Artifact I/O | Skills produce/consume markdown files with YAML frontmatter | Artifact Generator writes product-brief.md; Builder reads it |
| Tool invocation | Shell scripts invoked by LLM or fired by hooks | `capture-observation.sh`, governance hooks |

### Skill Contract Requirements

Per `docs/skill-authoring-guide.md`:
- Every SKILL.md starts with a one-paragraph purpose statement
- Procedural instructions use imperative voice
- Decision trees use numbered steps (S1)
- All thresholds are concrete (S2)
- Critical rules have structural emphasis (S4)
- No internal contradictions without explicit resolution (S6)

## Artifact Format Specification

Every artifact is a markdown file with YAML frontmatter:

```yaml
---
artifact: <identifier>       # Required, unique per project
version: <integer>           # Required, >= 1
depends_on:                  # Required, list of dependency references
  - artifact: <name>
    section: <optional>      # Specific section if partial dependency
depended_on_by:              # Required, inverse of other artifacts' depends_on
  - artifact: <name>
last_validated: <date|null>  # Required, null until build begins
---
```

Body is markdown — human-readable and LLM-consumable. Frontmatter enables mechanical dependency tracking and change propagation.

## Project-State Schema Contract

### Section Ownership

| Section | Primary Writer | Readers |
|---------|---------------|---------|
| classification | Domain Analyzer (C2) | All skills |
| product_definition | Orchestrator (C1) from user input | All skills |
| technical_decisions | Orchestrator (C1) from discovery | Builder, Critic |
| design_decisions | Orchestrator (C1) from discovery | Builder, Critic |
| artifact_manifest | Artifact Generator (C3) | Orchestrator, Critic, session-health-check |
| build_plan | Artifact Generator (C3, Phase D) | Builder, Orchestrator, Critic |
| build_state | Builder | Critic, Orchestrator |
| change_log | All skills (append-only) | Session Resumption, pattern detection |
| observation_backlog | Orchestrator (from triage) | Session Resumption |
| deprecated_terms | DCP Step 6 | session-health-check scanning |

### Read/Write Contracts

- **Append-only:** `change_log` entries are never modified after creation (compaction creates summary entries)
- **Version-tracked:** `artifact_manifest` entries include version numbers incremented on substantive changes
- **Partial resolution:** All sections support `null` values during discovery — the system works productively with incomplete state
- **Rollback support:** For directional changes, the previous state is recoverable via git

## Tool CLI Interfaces

### Observation Tools

| Tool | Interface | Output |
|------|-----------|--------|
| `capture-observation.sh` | `--type TYPE --description DESC --evidence EVID --severity SEV [--skill SKILL]` | Creates schema-compliant YAML file |
| `update-observation-status.sh` | `FILE --status STATUS [--archive]` | Updates observation status, optionally moves to archive/ |
| `observation-analysis.sh` | `[--patterns-only]` | Parses observations, applies tiered thresholds, reports patterns |

### Session Tools

| Tool | Interface | Output |
|------|-----------|--------|
| `session-health-check.sh` | (no args, reads project state) | Actionable patterns, backlog status, infrastructure health, divergence signals |
| `record-critic-findings.sh` | `--type TYPE --summary SUMMARY` | Records structured Critic evidence for commit gate |

### Infrastructure Tools

| Tool | Interface | Output |
|------|-----------|--------|
| `prawduct-init.sh` | `[--json] [--check] [--local] <target_dir>` | Detects/repairs integration state, returns JSON with next_action. `--check` detects without changes. `--local` skips git-tracked files (CLAUDE.md, .gitignore). |
| `resolve-product-root.sh` | (sourceable or executable) | Prints absolute path to product root (.prawduct/) |
| `compact-project-state.py` | `[--dry-run] <project-state-path>` | Compacts growing sections per lifecycle rules |

## Versioning Strategy

- **Framework versions:** Tracked by git SHA. `prawduct-init.py` writes current version to `.prawduct/framework-version`.
- **Schema versions:** `project-state.yaml` `schema_version` field. Migration tiers handle transitions.
- **Artifact versions:** Integer version in YAML frontmatter, incremented on substantive changes.
- **Backward compatibility:** Migration skill (`skills/orchestrator/migration.md`) handles old schema versions. `prawduct-init.py` detects schema version and routes accordingly.
