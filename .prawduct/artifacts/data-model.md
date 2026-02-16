---
artifact: data-model
version: 1
depends_on:
  - artifact: product-brief
depended_on_by:
  - artifact: test-specifications
  - artifact: security-model
  - artifact: api-contract
  - artifact: dependency-manifest
last_validated: 2026-02-16
---

# Data Model

<!-- sourced: docs/high-level-design.md § C5 Project State, Artifact Format, 2026-02-16 -->
<!-- sourced: .prawduct/framework-observations/schema.yaml, 2026-02-16 -->

## Entities

### ProjectState

The master state file for any project managed by Prawduct. All skills read from and write to this shared state — it is the primary coordination mechanism.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| classification | object | required | Domain, structural characteristics, domain characteristics, risk profile |
| classification.domain | string | required | Product domain (e.g., developer-tool, social, marketplace) |
| classification.structural | object | required | 5 boolean/object fields for structural characteristics |
| product_definition | object | required | Vision, goals, users, core flows, scope, platform, nonfunctional, regulatory |
| technical_decisions | object | required | Architecture, technology, data model, integration, operational decisions |
| design_decisions | object | required | IA, interaction patterns, accessibility approach, visual direction |
| artifact_manifest | object | required | Categorized registry of all tracked files with dependency chains |
| dependency_graph | list | required | Decision-to-artifact impact mapping |
| open_questions | list | required | Unresolved questions with blocking status, priority, waiting_on |
| user_expertise | object | required | Multi-dimensional expertise profile inferred from conversation signals |
| current_stage | string | required, enum | One of: intake, discovery, definition, artifact-generation, build-planning, building, iteration |
| change_log | list | required, append-only | Entries with what, why, blast_radius, classification, date, optional retrospective |
| build_plan | object | required | Strategy, remaining_work, chunks, current_chunk, governance_checkpoints |
| build_state | object | required | Source root, test tracking, spec compliance, reviews |
| iteration_state | object | required | Feedback cycles |
| observation_backlog | object | optional | Triaged observations pending action, with last_triage date |
| deprecated_terms | list | optional | Vocabulary removed in directional changes, with patterns for scanning |

### Artifact

A generated document with structured metadata. The framework's primary output — each artifact is a markdown file with YAML frontmatter enabling mechanical dependency tracking.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| artifact | string | required, unique per project | Artifact identifier (e.g., product-brief, data-model) |
| version | integer | required, >= 1 | Incremented on substantive changes |
| depends_on | list | required | Artifacts this one reads from (with optional section) |
| depended_on_by | list | required | Artifacts that read from this one |
| last_validated | date or null | required | When last confirmed to match implementation |
| body | markdown | required | Human- and LLM-readable content |

### Observation

A structured record of framework behavior captured automatically as a side-effect of normal operation.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| observation_id | string | required, unique | Format: {session_type}-{date}-{sequence} |
| timestamp | datetime | required, auto-set | ISO-8601 creation time |
| session_type | enum | required | One of: product_use, evaluation, framework_dev |
| session_context | string | optional | Scenario name, product name, or session description |
| observations | list | required, min 1 | Array of individual observation entries |
| observations[].type | enum | required | One of: coverage, proportionality, process_friction, missing_guidance, rubric_issue, skill_quality, critic_gap, integration_friction |
| observations[].description | string | required | Generalized (not product-specific) description |
| observations[].evidence | string | required | Specific evidence supporting the observation |
| observations[].severity | enum | required | One of: blocking, warning, note |
| observations[].status | enum | required | One of: noted, triaged, requires_pattern, acted_on, archived |
| observations[].skills_affected | list | optional | Skill files this observation pertains to |
| observations[].proposed_action | string | optional | Concrete action to address the observation |

### Skill

An LLM instruction set (SKILL.md file) that defines behavior for a specific framework capability.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| name | string | required | Skill identifier (e.g., orchestrator, domain-analyzer) |
| file_path | string | required | Path to SKILL.md (may have sub-files) |
| version | integer | required | Version tracked in artifact_manifest |
| purpose | string | in file | One-paragraph purpose statement at file top |
| instructions | markdown | in file | Structured procedural instructions |

### EvaluationResult

A recorded evaluation run with structured scoring against scenario rubrics.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| scenario | string | required | Scenario name from tests/scenarios/ |
| date | date | required | Evaluation date |
| evaluator | enum | required | claude-simulation, claude-interactive, or human |
| framework_version | string | required | Git SHA at evaluation time |
| result | object | required | pass/partial/fail/deferred/unable counts by component |
| skills_updated | list | required | Skills modified as a result of this evaluation |

### GovernanceState

Session-scoped tracking of governance debt and edit activity, maintained by mechanical hooks.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| product_dir | string | required | Absolute path to project root |
| product_output_dir | string | required | Absolute path to .prawduct/ |
| current_stage | string | required | Current stage from project-state.yaml |
| session_started | datetime | required | Session start timestamp |
| framework_edits | object | required | Files edited and total edit count |
| governance_state | object | required | Chunk review debt, FRP tracking, checkpoint tracking |
| directional_change | object | required | DCP tracking: active, plan, retrospective, phase reviews |

## Relationships

- A **Project** has one **ProjectState** (one-to-one)
- A **ProjectState** references many **Artifacts** via `artifact_manifest` (one-to-many)
- An **Artifact** depends on other **Artifacts** (many-to-many, via `depends_on`/`depended_on_by`)
- A **Project** has many **Observations** in `framework-observations/` (one-to-many)
- A **Project** has many **EvaluationResults** in `eval-history/` (one-to-many)
- A **Session** has one **GovernanceState** in `.session-governance.json` (one-to-one, session-scoped)
- **Skills** produce and consume **Artifacts** — the Orchestrator manages skill transitions

## State Machines

### Observation Lifecycle

```
noted → triaged → requires_pattern → acted_on → archived
noted → triaged → acted_on → archived
noted → acted_on → archived  (direct action on first observation)
```

- `noted`: Initial capture, unprocessed
- `triaged`: Reviewed, priority assigned, added to observation_backlog if deferred
- `requires_pattern`: Waiting for additional occurrences to cross tier threshold (meta: 2+, build: 3+, product: 4+)
- `acted_on`: Observation addressed — skill updated or backlog item created
- `archived`: Terminal. Moved to `framework-observations/archive/`

### Stage Progression

```
intake → discovery → definition → artifact-generation → build-planning → building → iteration
                                                                                    ↺ (iteration loops)
```

- Transitions are fuzzy, not rigid gates — discovery and definition interleave
- Each transition records a Framework Reflection Protocol entry in `change_log`
- Stage Transition Protocol verifies prerequisites before advancing

### Chunk Status (during Stage 5: Build)

```
pending → in-progress → complete → review → approved
                      → blocked (dependency not met)
```

- `pending`: Not yet started
- `in-progress`: Builder actively working
- `complete`: Code written, tests passing
- `review`: Critic governance in progress
- `approved`: Critic review passed, chunk done
- `blocked`: Cannot start until dependency chunks complete

### Change Classification (Stage 6: Iteration)

```
User request → classify → cosmetic | functional | directional
```

- `cosmetic`: Flows to build, minimal artifact updates
- `functional`: Updates relevant artifacts, Critic re-validates
- `directional`: 3-tier DCP (mechanical/enhancement/structural), may trigger reclassification

## Constraints

- Every artifact's `depended_on_by` list must be the inverse of all other artifacts' `depends_on` lists (denormalized cache — validated during consistency checks)
- Observation `status` may only advance forward through the lifecycle (no backward transitions except manual override)
- `current_stage` transitions must follow the defined stage progression order
- `change_log` is append-only — entries may not be modified or deleted (compaction creates summary entries)
- Every `change_log` entry for a directional change must include a `retrospective` field
- Observation files in `framework-observations/` must follow the schema in `framework-observations/schema.yaml`
- Test count (`build_state.test_tracking.test_count`) must not decrease (HR1: No Test Corruption)
