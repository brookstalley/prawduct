---
artifact: product-brief
version: 1
depends_on:
  - artifact: project-state
    section: product-definition
depended_on_by:
  - artifact: data-model
  - artifact: security-model
  - artifact: test-specifications
  - artifact: nonfunctional-requirements
  - artifact: pipeline-architecture
  - artifact: api-contract
  - artifact: dependency-manifest
last_validated: 2026-02-16
---

# Product Brief

## Vision

<!-- sourced: docs/vision.md, 2026-02-16 -->

A framework that turns vague product ideas into well-built software by guiding structured discovery, producing agent-executable build plans, and enforcing quality throughout development.

## Identity

Prawduct is an LLM instruction framework — its "interface" is a conversation mediated by the Orchestrator skill. The framework's voice is warm, clear, and proportionate: it adapts vocabulary and depth to the user's expertise level. It challenges gently, defers gracefully, and prioritizes the user's time. Output formatting follows markdown with YAML frontmatter for all structured artifacts.

## Users & Personas

<!-- sourced: .prawduct/project-state.yaml § product_definition.users, 2026-02-16 -->

### Product Builder

Someone with a product idea who wants to build it with LLM assistance. Ranges from non-technical to expert.

- **Needs:** Turn a vague idea into a concrete, buildable plan. Get product thinking they don't have (architecture, security, accessibility, operations). Build with quality governance that catches issues early.
- **Technical level:** Varies (none to advanced)
- **Constraints:** Patience varies — some want thorough discovery, some want to build immediately. Expertise varies across all dimensions.

### Framework Developer

Someone contributing to Prawduct itself — improving skills, templates, tools, or docs.

- **Needs:** Understand what to work on next (build order, phase status). Make changes governed by the framework's own quality process. Capture observations that improve the framework over time.
- **Technical level:** Advanced
- **Constraints:** Must follow the framework's own principles while changing them.

## Core Flows

<!-- sourced: .prawduct/project-state.yaml § product_definition.core_flows, 2026-02-16 -->
<!-- sourced: docs/high-level-design.md § Process Stages, 2026-02-16 -->

Since Prawduct has `runs_unattended` characteristics, core flows are framed as pipeline stages:

### Flow 1: Discovery to Build Plan (must-have)

User describes a product idea → Orchestrator classifies via Domain Analyzer → adaptive discovery questions calibrated to risk and user expertise → product definition crystallized → Review Lenses evaluate → Artifact Generator produces structurally-appropriate artifacts → build plan with dependency graph and governance checkpoints.

**Pipeline stages:** Intake → Classification → Discovery → Definition → Artifact Generation → Build Planning

### Flow 2: Build with Governance (must-have)

Builder executes build plan chunks → Critic evaluates each chunk (spec compliance, test integrity, coherence, scope discipline) → issues categorized (blocking/warning/note) → agent addresses blocking issues → Critic verifies fixes → proceed to next chunk or trigger refactoring review.

**Pipeline stages:** Chunk Execution → Critic Review → Issue Resolution → Verification → Next Chunk

### Flow 3: Framework Self-Improvement (must-have)

Framework development follows the same Orchestrator process → observations captured automatically at stage transitions → pattern detection via tiered thresholds → actionable patterns surfaced during session resumption → human-approved incorporation → Critic governance on changes.

**Pipeline stages:** Observation Capture → Pattern Detection → Pattern Surfacing → Human-Approved Incorporation → Critic Review

## Success Criteria

<!-- sourced: .prawduct/project-state.yaml § product_definition.goals, 2026-02-16 -->

1. End-to-end flow from vague input to useful build plan for any combination of structural characteristics
2. Framework governs its own development through its own process (eat your own cooking)
3. Observation capture fires automatically at every stage transition — no manual reminders needed
4. Review Lenses produce specific, actionable findings across all structural characteristics

## Scope

<!-- sourced: .prawduct/project-state.yaml § product_definition.scope, 2026-02-16 -->
<!-- sourced: docs/requirements.md § V1 Scope, 2026-02-16 -->

**v1:**
- Five structural characteristics plus dynamic domain-specific depth
- Full stage pipeline (0 through 6)
- Five review lenses with concern-appropriate application
- Critic with context-sensitive governance (10 checks, applicability based on project state)
- Builder skill for code generation from build plans
- Observation capture at every stage transition
- Three test scenarios with evaluation rubrics (family-utility, background-data-pipeline, terminal-arcade-game)
- Self-hosted framework development via Orchestrator

**Accommodate:**
- Agent agnosticism (R7.3) — artifact formats designed for any LLM agent
- Mechanical tools infrastructure

**Later:**
- C7 Trajectory Monitor as dedicated component (simple heuristics suffice in v1)
- C8 full Learning System (requires observation volume from many projects)
- Multi-user collaboration (current design assumes single user)

**Out of scope:**
- Code generation without governance (violates core thesis)
- Prescriptive technology choices (framework learns questions, not answers)

## Platform

<!-- sourced: .prawduct/project-state.yaml § product_definition.platform, 2026-02-16 -->

CLI (Claude Code) — runs within LLM sessions. No infrastructure, no services. Framework is instruction files consumed by the LLM runtime.
