# Glossary

Terms used across prawduct's documentation, skills, and tools.

## Stages

The pipeline that takes a product idea to working software:

| Stage | Name | What happens |
|-------|------|--------------|
| 0 | Intake & Triage | Domain Analyzer classifies the product and profiles risk |
| 1 | Discovery | Targeted questions based on classification, calibrated to risk |
| 2 | Product Definition | Crystallizes discovery into firm decisions; Review Lenses applied |
| 3 | Artifact Generation | Produces structured specifications in phases A-C with review gates |
| 4 | Build Planning | Translates specs into chunked, executable build instructions |
| 5 | Build + Governance | Executes the build plan chunk by chunk with Critic review |
| 6 | Iteration | Handles post-build feedback; classifies changes and governs accordingly |

## Artifact Generation Phases

| Phase | Name | What it produces |
|-------|------|------------------|
| A | Foundation | Product Brief (everything else depends on it) |
| B | Structure | Data Model and Non-Functional Requirements |
| C | Integration | Security Model, Test Specs, Operational Spec, Dependency Manifest, structurally-triggered artifacts |
| D | Build Planning | The build plan with scaffolding, chunks, and acceptance criteria |

## Components

| ID | Name | Role |
|----|------|------|
| C1 | Orchestrator | Manages the overall process, routes to other skills, handles session resumption |
| C2 | Domain Analyzer | Classifies products, generates discovery questions, profiles risk |
| C3 | Artifact Generator | Produces structured specification artifacts from project state |
| C3b | Builder | Executes the build plan chunk by chunk; never decides, only executes |
| C4 | Review Lenses | Five perspectives for evaluating artifacts and decisions |
| C5 | Project State | The single source of truth YAML file for the project |
| C6 | The Critic | Enforces quality through nine context-sensitive checks |
| C7 | Trajectory Monitor | (v1.5) Detects drift and triggers holistic reviews |
| C8 | Learning System | Observes patterns across projects to improve the framework |

## Structural Characteristics

Five properties of a product's architecture that trigger different artifact needs. A product may have any combination.

- **`has_human_interface`** -- The product has user-facing surfaces (screens, terminals, voice, spatial). Triggers interface structure artifacts, design direction, accessibility spec. Set `modality` and `platform`.
- **`runs_unattended`** -- The product runs automatically without user interaction. Triggers pipeline architecture, scheduling, monitoring, failure recovery, and configuration specs. Set `trigger` type.
- **`exposes_programmatic_interface`** -- The product exposes APIs, webhooks, or SDKs. Triggers API contract artifacts and versioning strategy. Set `consumers` to internal/external/both.
- **`has_multiple_party_types`** -- Distinct user types interact within the same system (buyers/sellers, teachers/students). Triggers per-party experience specs and interaction model.
- **`handles_sensitive_data`** -- The product handles PII, health data, payments, or other regulated information. Deepens existing artifacts (especially Security Model and Data Model). Set `categories` and `regulatory`.

## Three-Layer Artifact Architecture

How the framework decides what to generate and how deep to go:

1. **Amplification Rules** -- What additional artifacts to generate and how to deepen universal artifacts when a structural characteristic is active.
2. **Process Constraints** -- Quality properties that must hold regardless of modality, verified by the Critic and Review Lenses (e.g., "every pipeline stage must have failure handling").
3. **Template Reference** -- Optional proven structures for well-tested modalities. Currently exist for `has_human_interface` (screen) and `runs_unattended`.

## Review Lenses

Five perspectives applied at stage boundaries and governance checkpoints:

- **Product Lens** -- "Does this solve a real problem? Is the scope right?"
- **Design Lens** -- "Is the experience intuitive? Are all states handled?"
- **Architecture Lens** -- "Will this work? Is it maintainable?"
- **Skeptic Lens** -- "What will go wrong? What are we not thinking about?"
- **Testing Lens** -- "Are tests comprehensive, proportionate, and traceable to risks?" (Only applies once test specifications exist, Stage 3 Phase C onward.)

## Critic Checks

Nine checks applied by the Critic (C6) after changes:

| # | Name | When it applies |
|---|------|----------------|
| 1 | Spec Compliance | Build stages (5+) |
| 2 | Test Integrity | Build stages (5+) |
| 3 | Scope Discipline | Always |
| 4 | Proportionality | Always |
| 5 | Coherence | Always |
| 6 | Learning/Observability | Always |
| 7 | Generality | Skill/template changes |
| 8 | Instruction Clarity | Skill changes |
| 9 | Cumulative Health | Substantial skill modifications |

## Hard Rules

Non-negotiable behavioral rules (see `docs/principles.md` for full definitions):

| Rule | Name | Summary |
|------|------|---------|
| HR1 | No Test Corruption | Never weaken tests to make them pass |
| HR2 | No Silent Requirement Dropping | Flag it if you can't implement it |
| HR3 | No Documentation Fiction | Docs describe reality, not intent |
| HR4 | No Unexamined Decisions | Every non-trivial decision needs rationale |
| HR5 | No Confidence Without Basis | Say "I'm unsure" when you are |
| HR6 | No Ad Hoc Documentation | Every doc has a tier, owner, and location |
| HR7 | No Accessibility Afterthought | Accessibility from the start for UI products |
| HR8 | No Uncounted Costs | Identify and estimate ongoing costs |
| HR9 | No Governance Bypass | The Orchestrator's process is not optional |

## Protocols

| Abbreviation | Full Name | When used |
|-------------|-----------|-----------|
| FRP | Framework Reflection Protocol | At every stage transition -- assess whether the framework served well |
| PFR | Post-Fix Reflection Protocol | Every non-cosmetic fix -- classify, root-cause, fix, observe |
| DCP | Directional Change Protocol | Multi-file changes in Stage 6 -- classifies as mechanical/enhancement/structural |

### DCP Tiers

- **Mechanical** -- Renames, moves, formatting across any file count. Normal Critic review only.
- **Enhancement** -- Adds or modifies capability across 3+ files. Requires plan, implementation, artifact freshness check, Critic review.
- **Structural** -- Modifies framework concepts, governance, or vocabulary. Full protocol with phased review, observation, and retrospective.

## Change Classifications

How user feedback is categorized in Stage 6:

- **Cosmetic** -- Wording, formatting, minor adjustments. No artifact updates needed.
- **Functional** -- New features, changed behavior. Requires artifact updates, then a mini build loop.
- **Directional** -- Fundamentally different product vision. May trigger reclassification and the DCP.

## Key Terms

**Artifact** -- A structured markdown file with YAML frontmatter containing a specification (product brief, data model, security model, etc.). Generated during Stage 3, consumed during Stage 5.

**Chunk** -- A discrete unit of work in the build plan delivering one user-visible flow end-to-end. Chunk 01 is always the project scaffold.

**Classification** -- The Domain Analyzer's assessment of a product: domain, structural characteristics, risk profile, and domain-specific characteristics.

**Compaction** -- Mechanical archiving of completed sections in `project-state.yaml` to prevent unbounded growth. Run via `tools/compact-project-state.sh`.

**Discovery Dimensions** -- Ten mandatory areas explored for every product: Users, Core Experience, Data, Security, Failure Modes, Performance, Operational Lifecycle, Dependencies, Regulatory, Product Identity.

**Domain Characteristics** -- Product-specific properties identified by the LLM during classification (e.g., "realtime audio processing," "casual family gaming context"). Distinct from structural characteristics.

**Expertise Calibration** -- The continuous process of inferring user expertise from conversational signals. Never asks users to self-assess. Drives vocabulary and involvement depth.

**Governance Debt** -- Incomplete governance steps tracked in `.session-governance.json` -- unreviewed chunks, skipped FRP, incomplete DCP steps. The stop hook blocks session completion when critical debt exists.

**Minimal Artifact** -- An artifact assessed as not substantively applicable. Generated with standard frontmatter and a brief explanation. Product Brief and Test Specifications are never minimal.

**Observation** -- A structured YAML file in `framework-observations/` capturing a finding about the framework's behavior. Created via `tools/capture-observation.sh`. Has lifecycle states (active, resolved, archived).

**Product Root** -- The `.prawduct/` subdirectory where all prawduct outputs live (project state, artifacts, observations, working notes).

**Project State** -- The `project-state.yaml` file in the product root. The single source of truth for all decisions, their rationale, dependencies, and change history.

**Proportionality** -- The governing principle that process depth must match product risk. A family utility and a B2B financial platform receive different treatment at every stage.

**Question Budget** -- Maximum discovery questions per risk level: Low = 5-8 (1-2 rounds), Medium = 8-15 (2-4 rounds), High = 15-25 (3-6 rounds).

**Risk Profile** -- Assessment of overall product risk across six factors: Users, Data sensitivity, Failure impact, Technical complexity, Regulatory exposure, Execution quality bar. Overall risk is the highest factor that matters for this product.

**Session Resumption** -- The process of recovering context at the start of a new session: load project state, run health check, orient the user.

**Universal Artifacts** -- The seven artifacts generated for every product: Product Brief, Data Model, Security Model, Test Specifications, Non-Functional Requirements, Operational Spec, Dependency Manifest.

## Documentation Tiers

- **Tier 1 (Source of Truth)** -- Canonical reference. One document per topic. Must reflect current reality.
- **Tier 2 (Generated)** -- Derived from implementation or Tier 1. Always current by definition.
- **Tier 3 (Ephemeral)** -- Working notes in `working-notes/`. Expire after 2 weeks.
