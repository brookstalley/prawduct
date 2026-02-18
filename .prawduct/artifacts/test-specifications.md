---
artifact: test-specifications
version: 2
depends_on:
  - artifact: product-brief
  - artifact: data-model
  - artifact: security-model
depended_on_by: []
last_validated: 2026-02-18
---

# Test Specifications

<!-- sourced: docs/evaluation-methodology.md, 2026-02-16 -->

## Test Strategy

Prawduct is a framework of LLM instruction sets with mechanical tools (shell scripts, Python scripts). Testing operates at three levels:

- **Unit tests** verify individual mechanical tools with known inputs and expected outputs. Each tool script (`capture-observation.sh`, `record-critic-findings.sh`, `compact-project-state.py`, `session-health-check.sh`, etc.) has deterministic behavior that can be validated with known-good and known-bad project states. Mock: filesystem state. Don't mock: the script logic itself.
- **Integration tests** verify tool interactions with framework state files. Tools read and write `project-state.yaml`, `.session-governance.json`, and observation files — integration tests verify these interactions produce correct state transitions. Mock: nothing (use real files in a temp directory). Verify: state file content after tool execution.
- **E2E tests** are full scenario evaluations: take a product idea from raw input through the complete framework pipeline (classify → discover → define → generate → plan → build) and evaluate the output against rubrics with specific, observable criteria. These prove the framework delivers value end-to-end.

Coverage measurement: `scripts/validate-schema.sh` validates structural correctness of outputs. Evaluation rubrics (in `tests/scenarios/`) define must-do, must-not-do, and quality criteria per scenario.

Mocking principles: For unit tests of tools, create temporary project state files with known content. For integration tests, use real files in isolated temp directories. For E2E evaluations, use scripted conversations against clean framework state. Never mock the skill instructions themselves — they're the thing being tested.

Test isolation: Each test scenario starts from clean framework state in an isolated project directory. No shared mutable state between scenarios. Observation files created during tests don't persist to the main framework-observations directory.

## Flow: Discovery to Build Plan

### Happy Path

**Test: Family utility end-to-end (tests/scenarios/family-utility.md)**
- Level: e2e
- Setup: Clean framework state, isolated project directory
- Action: Provide "family score tracker" as input, respond to discovery questions per scripted test conversation
- Expected: Classification as has_human_interface (screen, mobile). Discovery asks about users, scoring, game sessions. Product definition includes personas, core flows, scope. Artifacts generated with correct frontmatter and cross-references. Review Lenses produce specific findings.

**Test: Background data pipeline end-to-end (tests/scenarios/background-data-pipeline.md)**
- Level: e2e
- Setup: Clean framework state, isolated project directory
- Action: Provide "daily tech news digest" as input
- Expected: Classification as runs_unattended (scheduled). Discovery asks about data sources, filtering, delivery. Pipeline architecture, scheduling, monitoring artifacts generated.

**Test: Terminal arcade game end-to-end (tests/scenarios/terminal-arcade-game.md)**
- Level: e2e
- Setup: Clean framework state, isolated project directory
- Action: Provide "terminal-based arcade game" as input
- Expected: Classification as has_human_interface (terminal). Discovery adapts to game/entertainment domain. Creative product handling without over-engineering governance.

### Error Cases

**Test: Vague input handling**
- Level: e2e
- Setup: Clean framework state
- Action: Provide extremely vague input ("I want to build something")
- Expected: System asks clarifying questions without classifying prematurely. Does not skip discovery.

**Test: Contradictory user input**
- Level: e2e
- Setup: Mid-discovery, user provides input contradicting earlier statements
- Expected: System flags contradiction, asks for clarification, does not silently adopt either version.

### Edge Cases

**Test: Ultra-minimal product**
- Level: e2e
- Setup: Clean framework state
- Action: Provide a product idea simpler than the lowest-risk scenario
- Expected: Framework applies proportionate governance — abbreviated discovery, minimal artifacts, no over-engineering.

## Flow: Build with Governance

### Happy Path

**Test: Chunk execution with Critic review**
- Level: e2e
- Setup: Completed build plan with defined chunks
- Action: Builder executes first chunk
- Expected: Code written, tests pass, Critic reviews against specs, findings categorized by severity.

### Error Cases

**Test: Test corruption attempt (HR1)**
- Level: e2e
- Setup: Failing test during chunk execution
- Action: Attempt to weaken or delete test to make it pass
- Expected: Critic blocks the change. Test count does not decrease. Assertion count does not decrease.

**Test: Silent requirement dropping (HR2)**
- Level: e2e
- Setup: Build plan chunk with difficult requirement
- Action: Builder skips requirement without flagging
- Expected: Critic's spec compliance check catches the omission. Requirement is flagged, not silently dropped.

## Flow: Framework Self-Improvement

### Happy Path

**Test: Observation capture at stage transition**
- Level: e2e
- Setup: Active product session transitioning between stages
- Action: Stage transition occurs
- Expected: change_log entry created (blocking). If substantive findings exist, observation file created with schema-compliant YAML.

**Test: Pattern detection surfaces actionable pattern**
- Level: integration
- Setup: 3+ observations of same type affecting same skill in framework-observations/
- Action: Session health check runs during session resumption
- Expected: Pattern detected, concrete recommendation generated, presented to user for act-or-defer decision.

### Error Cases

**Test: Observation capture not invoked (Failure Mode 1)**
- Level: e2e
- Setup: Framework session runs without observation capture
- Action: Evaluation methodology Step 7 verification
- Expected: Blocking failure — evaluation is incomplete without observation capture verification.

## State Transition Tests

### Observation Lifecycle: noted → triaged

- Level: integration
- Setup: Observation with status: noted, age > 2 days
- Action: Triage during session health check
- Expected: Status updated to triaged, added to observation_backlog with priority

### Observation Lifecycle: acted_on → archived

- Level: unit
- Setup: Observation with status: acted_on, all entries resolved
- Action: update-observation-status.sh --archive
- Expected: File moved to framework-observations/archive/

### Observation Lifecycle: invalid transition noted → archived

- Level: unit
- Setup: Observation with status: noted
- Action: Attempt to archive without triaging
- Expected: Transition rejected — observations must progress through lifecycle

### Stage Transition: discovery → definition

- Level: e2e
- Setup: Project in discovery stage with sufficient decisions
- Action: Stage Transition Protocol verification
- Expected: Prerequisites met (classification complete, key decisions documented), FRP entry recorded in change_log, current_stage updated

### Change Classification: directional change

- Level: e2e
- Setup: User requests change affecting 3+ files
- Action: Orchestrator classifies change
- Expected: Classified as structural DCP. Plan created, plan-stage Critic review, per-phase reviews, retrospective required.

## Security Concern Tests

### Hook bypass resilience

- Level: unit
- Setup: Governance hooks active
- Action: Attempt to edit governed file without Orchestrator activation
- Expected: governance-gate.sh blocks the edit with HR9 message

### Governance marker spoofing

- Level: unit
- Setup: No Orchestrator activation
- Action: Manually create .orchestrator-activated file
- Expected: Marker created but governance-gate.sh additionally validates marker recency (< 12 hours). The real governance (Critic review, skill instructions) is unaffected by marker state.
