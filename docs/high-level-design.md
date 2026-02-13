# High-Level Design

## System Overview

The system consists of eight components organized into three layers: a **Conversation Layer** (user-facing), a **Production Layer** (artifact generation and build management), and a **Quality Layer** (governance, trajectory, and learning).

```
┌─────────────────────────────────────────────────────┐
│                 CONVERSATION LAYER                   │
│                                                      │
│   ┌──────────────┐       ┌───────────────────┐      │
│   │  Orchestrator │◄─────►│ Domain Analyzer   │      │
│   │     (C1)      │       │      (C2)         │      │
│   └──────┬───────┘       └───────────────────┘      │
│          │                                           │
├──────────┼───────────────────────────────────────────┤
│          │        PRODUCTION LAYER                   │
│          ▼                                           │
│   ┌──────────────┐       ┌───────────────────┐      │
│   │   Artifact    │◄─────►│  Project State    │      │
│   │  Generator    │       │      (C5)         │      │
│   │    (C3)       │       └────────┬──────────┘      │
│   └──────────────┘                │                  │
│                                   │                  │
├───────────────────────────────────┼──────────────────┤
│           QUALITY LAYER           │                  │
│                                   ▼                  │
│   ┌──────────────┐       ┌───────────────────┐      │
│   │  Trajectory   │◄─────►│ Build Governance  │      │
│   │   Monitor     │       │  (The Critic)     │      │
│   │    (C7)       │       │      (C6)         │      │
│   └──────────────┘       └───────────────────┘      │
│                                                      │
│   ┌──────────────┐       ┌───────────────────┐      │
│   │   Review      │       │  Learning System  │      │
│   │   Lenses      │       │      (C8)         │      │
│   │    (C4)       │       └───────────────────┘      │
│   └──────────────┘                                   │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### V1 Scope

Not all components are equally essential for a working v1:

- **V1 Phase 1 (vertical slice):** C1 (Orchestrator Stages 0-3), C2 (Domain Analyzer), C3 (Artifact Generator Phases A-C), C4 (Review Lenses), C5 (Project State), C6 framework governance mode, C8a (Observation Capture)
- **V1 Phase 2 (build loop):** C1 (Orchestrator Stages 4-6), C3 (Artifact Generator Phase D — build planning), C3b (Builder — code generation from build plans), C6 product governance mode (spec compliance, test integrity, scope violation), build-phase observation types
- **V1 Phase 2 (widen):** C6 remaining sub-components (architectural consistency, documentation controller, operational readiness), additional product shapes, mechanical tools (governance enforcement hooks now built — see C6 section; remaining sub-check tools still deferred)
- **V1.5:** C7 (Trajectory Monitor) — architecturally accommodate but implement after v1 validates
- **V2:** C8 full (Learning System with pattern detection, validation, incorporation) — requires data from many projects; premature before user base exists

The Trajectory Monitor's triggers (R4.2) can be handled by simple heuristics in v1, upgraded to a dedicated component later. See `docs/requirements.md` § "Phase 1 vs Phase 2" for the full deferral rationale.

---

## Product Concern Taxonomy

Products are classified by their active **concerns** — independent dimensions that drive discovery questions, artifact selection, and governance focus. A product may have any combination of concerns. This replaces a fixed shape taxonomy (UI Application, API, Automation, Multi-Party, Hybrid) with composable dimensions that handle products the framework has never seen.

### Concerns

| Concern | What it triggers | Example signals |
|---------|-----------------|-----------------|
| **`human_interface`** | UX questions, screen/interaction specs, accessibility | "app," "screen," "button," "terminal," "voice," "dashboard" |
| **`unattended_operation`** | Scheduling, monitoring, failure recovery specs; silent-failure review mandate | "automatically," "every day," "cron," "background," "pipeline" |
| **`api_surface`** | API contracts, integration guide, versioning, SLAs | "API," "endpoint," "webhook," "consumers," "SDK" |
| **`multi_party`** | Per-party specs, interaction model, trust boundaries | "buyers and sellers," "admin panel," distinct user types interacting |
| **`constrained_environment`** | Resource budget questions, host system constraints | "embedded," "firmware," "plugin," "extension," "browser extension," "offline" |
| **`external_integrations`** | Resilience questions, rate limiting, cost awareness | External services, APIs, data sources mentioned |
| **`sensitive_data`** | Security depth, regulatory discovery, data classification | "health data," "payments," "children," "PII," "financial" |

### How Concerns Differ from Shapes

Shapes were mutually exclusive categories — a product was either a "UI Application" or an "Automation," and hybrids required special handling. Concerns are independent dimensions that combine freely:

- A **family score tracker** has `human_interface` (screen, mobile) — that's it.
- A **background data pipeline** has `unattended_operation` + `external_integrations`.
- A **monitoring dashboard** has `human_interface` (screen) + `unattended_operation` + `external_integrations`.
- An **earbud firmware** has `constrained_environment` (embedded) + `human_interface` (minimal: LEDs, buttons).
- A **two-sided marketplace** has `human_interface` (screen) + `multi_party` + `api_surface` + `sensitive_data` (payments).

No product needs a special "hybrid" designation — it simply has the concerns it has.

### Common Concern Bundles

For communication with users, familiar patterns still have natural names. The Orchestrator uses these in conversation — "this sounds like a background automation" — but they are not stored fields. They are just shorthand:

- "UI Application" ≈ `human_interface` (screen) as the primary concern
- "Automation / Pipeline" ≈ `unattended_operation` + `external_integrations`
- "API / Service" ≈ `api_surface` as the primary concern
- "Multi-Party Platform" ≈ `multi_party` + `human_interface` + often `sensitive_data`

### Concern Detection

The Domain Analyzer (C2) detects concerns during intake based on signals in the user's description. Multiple concerns may be detected simultaneously. When no clear signals exist for any concern, the Domain Analyzer asks a clarifying question.

### Concern Evolution

The 7 concerns are the starting set. The self-improvement loop applies: `missing_guidance` observations pointing to an unrecognized dimension (2+ occurrences) are candidates for a new concern. Existing concerns are refined through `coverage` and `applicability` observations. The Structural Critique Protocol reviews the concern set periodically.

---

## Process Stages

### Stage 0: Intake & Triage
**Owner:** Orchestrator (C1) + Domain Analyzer (C2)

1. User provides raw input
2. Domain Analyzer classifies domain and detects concerns
3. Orchestrator begins expertise calibration from initial input signals
4. System confirms classification with user: "This sounds like a location-based social app for mobile. Is that right?"

### Stage 0.5: Validation
**Owner:** Orchestrator (C1) + Domain Analyzer (C2) + Review Lenses (C4)

Product Lens and Skeptic Lens evaluate before deep discovery begins:
- Does this warrant building? Are there existing solutions?
- Is this one product or multiple?
- Is this feasible for LLM-assisted development?
- Are there obvious regulatory or legal constraints?

If concerns arise, surface them to user. Possible outcomes: proceed, refine scope, pivot, or recommend not building.

### Stage 1: Discovery
**Owner:** Orchestrator (C1) + Domain Analyzer (C2)

Dynamic questioning based on classification. Discovery depth calibrated to product risk and user patience.

Domain Analyzer provides:
- Archetype-specific critical questions (prioritized by impact)
- Concern-specific technical questions
- Risk and complexity profile
- Considerations the user hasn't raised

Orchestrator manages:
- Question pacing and prioritization
- Expertise calibration (ongoing)
- Inference and confirmation (not interrogation)
- Pushback on questionable decisions
- Recognition of when discovery is "good enough"

Output: Populated Project State (C5) with decisions, open questions, and rationale.

### Stage 2: Product Definition
**Owner:** Orchestrator (C1) + Review Lenses (C4)

Crystallize discovery into firm decisions:
- Users and personas
- Platform and reach
- Core flows (or core pipeline stages, or core API operations)
- V1 scope vs. later
- Non-functional requirements (performance, cost, uptime, accessibility)
- Regulatory constraints

Product, Design, Architecture, and Skeptic lenses evaluate the product definition before proceeding. (Testing Lens does not apply — no test specifications exist yet.)

Output: Finalized product decisions in Project State. Ready for artifact generation.

### Stage 3: Artifact Generation
**Owner:** Artifact Generator (C3) + Review Lenses (C4)

Generate the concern-appropriate artifact set. Each artifact:
- Is reviewed by all relevant lenses before finalization
- States its dependencies on other artifacts explicitly
- Is version-tracked in Project State (C5)

Output: Complete, reviewed artifact set.

### Stage 4: Build Planning
**Owner:** Artifact Generator (C3) + Project State (C5)

Produce execution plan:
- Build order with dependency graph
- Parallelization opportunities
- Early-feedback milestones (get something in front of the user as soon as possible)
- Governance checkpoints (when does the Critic run full reviews?)

Output: Ordered build plan ready for coding agent.

### Stage 5: Build + Governance Loop
**Owner:** Build Governance (C6) + Trajectory Monitor (C7)

Repeating cycle during development:
1. Coding agent builds a defined chunk
2. Critic evaluates (spec compliance, test integrity, architectural consistency, documentation)
3. Issues categorized: blocking / warning / note
4. Agent addresses blocking issues
5. Critic verifies fixes (watching for fix-by-fudging)
6. Trajectory Monitor checks for holistic concerns at defined triggers
7. Proceed to next chunk or trigger refactoring review

### Stage 6: Iteration
**Owner:** Orchestrator (C1) + Project State (C5)

User sees built artifact, reacts, requests changes. Orchestrator classifies:
- **Cosmetic:** flows directly to build, minimal artifact updates
- **Functional:** updates relevant artifacts, Critic re-validates affected areas
- **Directional:** may trigger reclassification (R5.4), re-enters discovery for new scope, propagates through all artifacts

---

## Components (Detailed)

### C1: Orchestrator

**Purpose:** Manages the overall process — from first user input through build completion and iteration. The conductor of all other components.

**Key responsibilities:**
- Stage management and transitions (fuzzy, not rigid gates)
- Conversation flow: when to ask, infer, push back, or move on
- User expertise model: multi-dimensional, inferred from behavior, continuously updated
- Pacing calibration: match discovery depth to product risk and user patience
- Escalation decisions: what requires user input vs. autonomous handling
- Change classification: cosmetic vs. functional vs. directional

**Interactions:**
- Calls C2 for classification and discovery questions
- Calls C3 for artifact generation
- Reads/writes C5 for all project decisions
- Invokes C4 at stage transitions and on generated artifacts
- Receives signals from C6 and C7 during build phase
- Escalates to user only per principles (genuine product decisions, unresolvable disagreements, vision-affecting changes)

**Design considerations:**
- Must handle scattered, contradictory, or uncertain users gracefully
- Must know when "good enough" discovery has occurred — this threshold varies by concern set and risk level
- Stage transitions are fuzzy: discovery and definition interleave, building and iteration overlap
- Must handle "just build it" users by accelerating with explicit assumptions, not by skipping governance

### C2: Domain Analyzer

**Purpose:** Classifies the product and activates relevant lines of inquiry. The system's product knowledge encoded as principles, not encyclopedia entries.

**Key responsibilities:**
- Product classification: domain (social, marketplace, B2B, utility, etc.) and concerns (human_interface, unattended_operation, api_surface, multi_party, constrained_environment, external_integrations, sensitive_data)
- Risk and complexity profiling per archetype
- Discovery question generation, prioritized by impact
- Proactive expertise: considerations the user is unlikely to raise, given their expertise profile
- Prior art awareness: surface existing solutions in the space (using web search when needed)
- Regulatory flag detection: identify when domain or features trigger regulatory requirements

**Knowledge structure:**
Principles tagged to archetypes and concerns. Examples:
- [network effects] "Products with network effects must address the cold-start problem."
- [user content] "Any product where users generate content must have a moderation strategy."
- [location] "Location-based products must address privacy, battery impact, and precision."
- [non-technical users] "Products targeting non-technical users must heavily weight onboarding, error recovery, and accessibility."
- [unattended] "Products that run unattended must have monitoring, alerting, and failure recovery as core features, not afterthoughts."
- [financial] "Products handling money must address idempotency, reconciliation, and audit trails."
- [multi-party] "Products with multiple user types must discover each party's needs independently and model their interactions explicitly."
- [API] "APIs must address versioning, backward compatibility, and consumer onboarding (docs + sandbox)."

Principles also fire on feature detection: adding messaging to any product triggers moderation concerns regardless of archetype.

**Evolves via:** Learning System (C8) adds new discovery questions and risk patterns based on observed project outcomes.

### C3: Artifact Generator

**Purpose:** Produces the build plan artifacts. Selects the appropriate artifact set based on product concerns and generates each artifact from the decisions in Project State.

**Key responsibilities:**
- Artifact set selection based on product concerns (see Product Concern Taxonomy)
- Generation of each artifact with cross-references and dependency declarations
- Consistency enforcement across artifacts (data model matches API contracts matches screen specs)
- Build ordering with dependency graph and early-feedback milestones
- Artifact updates when decisions change (modular, not regenerate-everything)

**Artifact dependency model:**

```
Product Brief (universal)
    │
    ├──► Information Architecture        API Contracts              Pipeline Architecture
    │    (human_interface: screen)        (api_surface)              (unattended_operation)
    │         │                                  │                          │
    │         ▼                                  ▼                          ▼
    │    Screen Specs                    Integration Guide          Scheduling Spec
    │    (human_interface: screen)        (api_surface)              (unattended_operation)
    │         │                                  │                          │
    ├──► Data Model (universal) ◄────────────────┤                          │
    │         │                                  │                          │
    ▼         ▼                                  ▼                          ▼
Security Model (universal)              SLA Definition             Monitoring Spec
    │                                    (api_surface)              (unattended_operation)
    ▼
Non-Functional Requirements (universal)
    │
    ▼
Test Specifications (universal)
    │
    ▼
Operational Specification (universal)
    │
    ▼
Dependency Manifest (universal)
```

**Each artifact declares:**
- What it depends on (and which version)
- What depends on it
- When it was last validated against implementation (once build begins)

### C4: Review Lenses

**Purpose:** Multi-perspective validation applied to system output at every stage. Five lenses defined in principles.md (Product, Design, Architecture, Skeptic, Testing).

**When they fire:**
- **Stage 0.5 (Validation):** Product and Skeptic evaluate whether to build at all
- **Stage 1 (Discovery):** Product and Skeptic check whether the right questions are being asked
- **Stage 2 (Product Definition):** Product, Design, Architecture, and Skeptic lenses review crystallized decisions
- **Stage 3 (Artifact Generation):** All five lenses review artifacts before finalization (Testing Lens activates in Phase C when test specifications exist)
- **Stage 5 (Build + Governance):** Architecture and Skeptic validate implementation
- **Stage 6 (Iteration):** Product evaluates change requests; Architecture evaluates blast radius

**Output structure per lens evaluation:**
- Findings: specific observations, not vague impressions
- Severity: blocking (must address before proceeding), warning (must address before delivery), note (consider)
- Recommended action: what to do about each finding

**Design considerations:**
- Different lenses have different authority. The Architecture lens can block on boundary violations. The Skeptic flags but doesn't block (unless the risk is severe).
- Lenses should not all fire with equal depth on every evaluation. Routine artifact generation gets a lighter touch than a major scope change.
- Lens perspectives should rotate emphasis: sometimes lead with security, sometimes with cost, sometimes with accessibility. Prevents blind spots from developing.

### C5: Project State

**Purpose:** The single source of truth for the project — all decisions, their rationale, dependencies, open questions, and change history.

**Structure:**

```
Project State
├── Classification
│   ├── Domain(s)
│   ├── Concerns (independent dimensions)
│   └── Risk profile
├── Product Definition
│   ├── Vision & goals (resolved/open)
│   ├── Users & personas — per party if multi-party (resolved/open)
│   ├── Core flows / operations / pipeline stages (resolved/open)
│   ├── Scope decisions (v1 / accommodate / later / never)
│   ├── Platform & reach
│   ├── Non-functional requirements
│   ├── Regulatory constraints
│   └── Cost estimates
├── Technical Decisions
│   ├── Architecture choices + rationale
│   ├── Technology choices + rationale
│   ├── Data model decisions
│   ├── Integration decisions
│   └── Operational decisions (deployment, monitoring, recovery)
├── Design Decisions
│   ├── IA decisions
│   ├── Interaction patterns
│   ├── Accessibility approach
│   └── Visual direction
├── Artifact Manifest
│   ├── (artifact → version, dependencies, last validated)
│   └── Documentation tier assignments
├── Dependency Graph
│   └── (decision → affected decisions, affected artifacts)
├── Open Questions
│   └── (question, blocking what, waiting on whom, priority)
├── User Expertise Profile
│   └── (dimension → inferred level, evidence)
└── Change Log
    └── (what changed, why, blast radius, classification, date)
```

**Design considerations:**
- Must support partial resolution. The system works productively with incomplete state throughout discovery.
- Must be queryable: Critic asks "what did we decide about auth?" Orchestrator asks "what's unresolved?"
- Must support rollback: if a directional change fails, the previous state is recoverable.

### C6: Build Governance (The Critic)

**Purpose:** Automated quality enforcement during development. The embodiment of the Hard Rules from principles.md.

**Sub-components:**

**Spec Compliance Auditor**
- After each work unit, diffs implementation against specification
- Produces explicit checklist: specified → implemented → discrepancy
- Discrepancies must be resolved: fix implementation or formally amend spec with rationale

**Test Integrity Checker**
- Monitors for corruption patterns: deletion, commenting, assertion weakening, trivial assertions, testing mocks instead of behavior
- Mechanical checks: test count trend, assertion count per test, coverage metrics
- Flags all test modifications with explanation requirement
- Enforces tests-alongside-implementation

**Architectural Consistency Checker**
- Validates implementation against architecture artifact
- Checks: module boundary respect, dependency direction, data flow, separation of concerns
- Flags violations with specific evidence

**Documentation Controller**
- Enforces Tier 1/2/3 system
- Prevents ad hoc document creation in canonical doc space
- Validates Source of Truth documents against implementation
- Sweeps ephemeral documents for expiration
- Maintains artifact manifest in Project State

**Operational Readiness Checker** (for automations, APIs, and services)
- Verifies monitoring is implemented, not just specified
- Verifies failure recovery paths are tested
- Verifies alerting thresholds are configured
- Verifies deployment procedure is documented and reproducible

**Review cycle:**
1. Agent completes a defined work unit
2. All relevant Critic sub-components evaluate
3. Issues categorized: blocking / warning / note
4. Agent addresses blocking issues
5. Critic verifies fixes — specifically watching for:
   - "Fixing" by weakening the check instead of fixing the code
   - "Fixing" by changing the spec to match the (wrong) implementation
   - "Fixing" by adding a workaround rather than addressing root cause
6. Proceed to next chunk or re-enter step 4

**Mechanical enforcement:** Beyond the LLM-driven review cycle, governance is enforced mechanically via Claude Code hooks that operate independent of LLM judgment. Framework governance uses commit gate hooks (`critic-gate.sh`, `framework-edit-tracker.sh`, `orchestrator-gate.sh`) that block commits without Critic evidence and track edits with escalating reminders. Product governance uses session tracking hooks (`product-governance-tracker.sh`, `product-governance-stop.sh`, `product-governance-prompt.sh`) that maintain `.product-session.json` state to track governance debt — advisory for soft items (observation capture reminders), blocking for critical items (unreviewed chunks, overdue governance checkpoints).

### C7: Trajectory Monitor

**Purpose:** Manages the project's trajectory — detecting drift, triggering holistic reviews, resisting entropy. [v1.5 — simple heuristics in v1, dedicated component later]

**Holistic review triggers:**
- Change touches >N files/modules
- Agent works around existing structure
- 3+ consecutive changes to same area
- Regular cadence at feature milestones
- User-initiated scope change classified as directional

**Holistic review process:**
"If we designed this from scratch today, knowing what we know, would we design it the same way?" Applied at every level: data model, architecture, test suite structure, UX flow, documentation organization.

**Entropy metrics tracked:**
- Code complexity trends
- Test suite health trends (coverage, assertion quality, flakiness)
- Documentation freshness
- Architectural boundary violation frequency
- Ratio of workarounds to clean implementations

### C8: Learning System

**Purpose:** Makes the system smarter over time by observing patterns across projects. [v2 — requires project volume]

**Sub-components:**

**C8a: Project Observer** — Passive signal collection. Governance interventions, user direction changes, discovery gaps, refactoring triggers.

**C8b: Pattern Extractor** — Periodic cross-project analysis. Applies review lenses to its own findings. Requires statistical significance, not anecdotes.

**C8c: Validation Pipeline** — Four gates: consistency with principles (hard rules are axioms), appropriate specificity, reversibility, adversarial testing against historical projects.

**C8d: Incorporation Engine** — Routes validated learnings to the right component with provenance. New questions → C2. New failure modes → C6. New patterns → C3. Refined thresholds → C7.

**C8e: Retirement Monitor** — Reviews incorporated learnings against current evidence. System knowledge can shrink.

---

## Skill Interaction Model

Components in the Conversation, Production, and Quality layers are implemented as LLM instruction sets (SKILL.md files) operating within a single LLM context. They are not separate services or agents. Understanding how they interact is essential to implementation.

### Execution Model

The LLM operates under one skill's instructions at a time. The Orchestrator (C1) is the default active skill and manages transitions to other skills as needed.

**Interaction patterns:**

- **Skill switching:** The Orchestrator loads another skill's instructions when entering that skill's domain (e.g., loads Domain Analyzer instructions during classification). The Orchestrator's framing context persists.
- **Shared state via files:** Project State (C5) is a YAML file in the project directory. All skills read from and write to this shared state. This is the primary coordination mechanism.
- **Artifact I/O:** Generated artifacts are markdown files with YAML frontmatter. Skills produce and consume these files.
- **Tool invocation:** Mechanical tools include both shell scripts invoked by the LLM during governance phases and Claude Code hooks that fire automatically on tool use events, providing enforcement independent of LLM judgment. Script output feeds back into the LLM's evaluation; hook output is injected as advisory messages or blocks operations directly.

### Persistence Model (V1)

Project state persists as files in the user's project directory:

- `project-state.yaml` — Master state file (C5)
- `doc-manifest.yaml` — Documentation tier tracking
- `artifacts/` — Generated artifacts (markdown with YAML frontmatter)
- `working-notes/` — Ephemeral Tier 3 documents

This is intentionally simple: files are human-readable, version-controllable, and require no infrastructure. The LLM reads these files at session start and writes them as decisions are made. This is a reversible choice — if file-based persistence proves insufficient, migration to a structured store is straightforward because the schema is already defined in C5.

### Artifact Format (V1)

Each artifact is a markdown file with structured YAML frontmatter:

```yaml
---
artifact: product-brief
version: 1
depends_on:
  - artifact: project-state
    section: product-definition
depended_on_by:
  - artifact: data-model
  - artifact: information-architecture
last_validated: null  # populated during build phase
---

# Product Brief

[Human-readable content here]
```

The body is readable by both humans and LLMs. The frontmatter enables mechanical dependency tracking and change propagation. This format is a starting hypothesis — if it proves insufficient during the vertical slice, it changes.

---

## Validation Strategy for Skills

Skills (LLM instruction sets) produce non-deterministic outputs. This doesn't excuse them from testability — it requires a different kind of testing. Per "Define Testability for Judgment-Dependent Outputs" (principles.md), evaluation rubrics with specific, observable criteria must be defined before building.

### Scenario-Based Evaluation

Each skill is tested against a defined set of product scenarios. For each scenario, the evaluation rubric specifies:

- **Input:** A product description with known characteristics.
- **Test conversation:** For conversational scenarios, scripted user responses for each topic the system is likely to ask about. Without defined responses, two evaluations of the same skill will diverge because the evaluator gave different answers, making regression detection unreliable. The scripted responses also encode a test persona (expertise level, communication style, cooperativeness) that the system's behavior should adapt to.
- **Must-do:** Things the skill must do (e.g., "must classify as automation/pipeline," "must ask about failure recovery," "must surface monitoring as a concern").
- **Must-not-do:** Things the skill must avoid (e.g., "must not ask about screen layouts for a pipeline," "must not recommend not building without stated reason").
- **Quality criteria:** Specific, observable markers of good output (e.g., "questions are prioritized by impact, not presented as a flat list," "pushback includes rationale, not just disagreement").
- **State validation:** Expected state of `project-state.yaml` after the process completes. Since Project State is the coordination mechanism between all skills, its correctness after each stage is a critical test of inter-skill compatibility.

### Minimum Test Scenarios

Five scenarios that cover the product concern taxonomy:

1. **Consumer mobile app** (primary concerns: `human_interface`) — tests screen-related discovery, accessibility, onboarding, platform considerations.
2. **Background data pipeline** (primary concerns: `unattended_operation`, `external_integrations`) — tests operational concerns, monitoring, failure recovery, cost awareness. Tests that the system does *not* ask about screens or navigation.
3. **B2B integration API** (primary concerns: `api_surface`, `sensitive_data`) — tests contract design, versioning, consumer needs, SLAs. Tests expertise calibration for a technical user.
4. **Simple family utility** (primary concerns: `human_interface`, low risk) — tests pacing sensitivity, scope restraint. The system should *not* interrogate this the same way it interrogates a B2B platform.
5. **Two-sided marketplace** (primary concerns: `multi_party`, `human_interface`, `api_surface`, `sensitive_data`) — tests multi-party discovery, per-party needs, cross-party interactions, trust boundaries.

### Evaluation Isolation

Evaluations must not write files into the prawduct framework repository. Each evaluation run:

1. Creates a temporary project directory outside the prawduct tree (e.g., `/tmp/eval-<scenario-name>/`).
2. Copies `templates/project-state.yaml` into that directory.
3. Runs the full scenario with all file output directed to the temporary directory.
4. Evaluates the resulting files (`project-state.yaml`, `artifacts/`) and the conversation transcript against the rubric.
5. Records results before cleaning up.

All skills reference `project-state.yaml`, `artifacts/`, and `working-notes/` as paths relative to the user's project directory. The Orchestrator is responsible for establishing this directory at the start of any session and ensuring it is not the prawduct repo itself.

### Regression Detection

When a skill is modified, all scenarios are re-evaluated. A regression is:

- A must-do item that previously passed now failing.
- A must-not-do item that previously passed now triggering.
- Quality criteria that previously held now absent.

This is judgment-based evaluation, not mechanical. But it has structure, and structure enables regression detection even for non-deterministic outputs. Over time, as patterns stabilize, some evaluations may become partially mechanizable (e.g., checking that specific keywords or topics appear in output).

### Evaluation Lifecycle

The complete evaluation process — from setup through execution, result recording, learning extraction, and regression detection — is documented in `docs/evaluation-methodology.md`. Key aspects:

- **Simulation vs. Interactive**: Simulation (LLM plays test persona) is fast and covers mechanical criteria but cannot evaluate conversation quality. Interactive evaluation (human plays test persona) provides full transcript analysis but requires significantly more time.
- **Learning Extraction**: A systematic process for transforming evaluation observations into framework improvements, with provenance tracking and "Learn Slowly" principles to avoid over-fitting to single instances.
- **Meta-Learning**: After each evaluation, critique the evaluation process itself — rubric quality, scenario design, method choice, process friction. Each eval should make the next eval better.
- **Recording Format**: Standardized YAML frontmatter enables machine-parseable regression detection across framework changes.

For detailed procedures, decision matrices, and recording templates, see `docs/evaluation-methodology.md`.

---

## Bootstrapping: Vertical Slice Approach

Per "Prove the Path Before Widening It" (principles.md), the system itself is built as a narrow vertical slice first, then widened. This replaces the component-by-component build order with a path-first approach.

### Phase 1: One Path Through the System

Pick one product scenario (the family utility — a simple UI application with low risk) and build just enough of each component to handle it end-to-end:

1. **C5 (Project State):** Define the schema first — everything else reads/writes this. Validate that the structure captures what discovery and artifact generation need.
2. **C2 (Domain Analyzer):** Classify "UI Application" + "Utility" domain. Generate discovery questions for this combination only.
3. **C1 (Orchestrator):** Manage a discovery conversation for this one scenario. Handle stage transitions 0 → 0.5 → 1 → 2.
4. **C3 (Artifact Generator):** Generate the universal artifact set (product brief, data model, security model, test specs, NFRs, operational spec, dependency manifest). Skip concern-specific artifacts initially.
5. **C4 (Review Lenses):** Apply all five lenses to the generated artifacts (Testing Lens in Phase C). Evaluate whether findings are specific and actionable.

**Evaluate against the family utility test scenario rubric.** The vertical slice succeeds when:
- The conversation flow produces a populated Project State from a vague input.
- The artifacts are internally consistent and cross-referenced.
- The Review Lenses produce specific, actionable findings (not vague impressions).
- A human reading the output would consider it a plausible starting point for building.

**What this proves:** That the skill interaction model works, that the artifact format is adequate, that Project State captures enough, and that the end-to-end flow produces something useful.

**What this defers:** Other product concerns, concern-specific artifacts, the Critic (C6), pacing sensitivity, prior art search, expertise calibration beyond basic, and mechanical tools.

### Phase 2: Widen Based on Phase 1 Findings

Phase 1 validated the architecture. Phase 2 widening has delivered:

- `unattended_operation` concern with full-depth discovery, 5 templates, domain overlays, and test scenario rubric (background-data-pipeline).
- Critic (C6) with framework governance (7 checks) and product governance (spec compliance, test integrity, scope violation).
- Mechanical governance hooks: commit gate, edit tracker, orchestrator gate, product governance tracker/stop/prompt.
- Builder with chunk execution, scaffolding, proportionality, and artifact insufficiency flagging.
- Stages 4-6 (Build Planning, Build + Governance, Iteration) across Orchestrator, Builder, and Critic.
- Terminal arcade game test scenario (entertainment domain, creative product handling).

Remaining Phase 2 widening (tracked in `project-state.yaml` → `remaining_work`, phase: v1-widen):

- Deepen api_surface and multi_party concerns (discovery, templates, test scenarios).
- Create human_interface templates (6 templates).
- Orchestrator sophistication: pushback, prior art, pacing, reclassification.
- Critic sub-components: architectural consistency, documentation controller, operational readiness.
- Critic-Review Lenses integration; Review Lenses variable-depth and rotating emphasis.
- Builder multi-concern chunk patterns; Domain Analyzer additional overlays.
- Mechanical sub-check tools (5 scripts).

### Phase 3: Full V1

All v1 requirements implemented, all six test scenarios passing evaluation rubrics, the system used to govern its own development. The "compiler compiles itself" test: take Prawduct's own product idea through the full framework and evaluate whether the resulting build plan would produce this system.

---

## Documentation Architecture

All projects (including this one) follow a three-tier system:

**Tier 1: Source of Truth**
- Canonical reference for each topic — exactly one document per topic
- Must reflect current reality at all times
- Protected: cannot be created or deleted without governance approval
- Examples in this project: vision.md, requirements.md, principles.md, high-level-design.md

**Tier 2: Generated**
- Derived from implementation or Tier 1 docs
- Automated generation preferred
- Always current by definition
- Examples: API docs from code, type docs from schemas, dependency graphs from analysis

**Tier 3: Ephemeral**
- Working notes, decision explorations, spike findings
- Stored in a designated working area, separate from Tier 1/2
- Explicit expiration (default: 2 weeks)
- Periodically swept: incorporate into Tier 1, or delete
- Examples: research notes, experiment results, draft proposals

**Document Manifest:** Every project maintains a manifest listing all Tier 1 documents, their purpose, and their last-validated date. The manifest itself is Tier 1.

---

## Cross-Cutting Concerns

### User Expertise Adaptation
Spans C1, C2, C3, C4. The system maintains a multi-dimensional expertise profile inferred from conversation. Dimensions include: product thinking, technical depth, design sensibility, domain knowledge, operational awareness. The profile updates continuously and drives vocabulary, explanation depth, and involvement calibration.

### Change Propagation
Decision changes flow: Project State (C5) identifies affected decisions and artifacts → Artifact Generator (C3) updates affected artifacts → Build Governance (C6) re-validates affected implementation → Trajectory Monitor (C7) assesses whether change patterns suggest deeper issues.

### Feedback Integration
User reacts to build → Orchestrator (C1) classifies feedback → if directional, Domain Analyzer (C2) re-evaluates → if reclassification, discovery reopens for changed concerns → Project State (C5) updates → change propagation follows.

### Cost Tracking
Surfaces during discovery (C2 flags cost-relevant design choices), quantified during artifact generation (C3 includes cost estimates in operational spec), monitored during build (C6 checks for cost-relevant deviations), validated during trajectory review (C7 catches cost drift).

---

## Open Design Questions

These are acknowledged gaps that require further work. Per our own principles, we're documenting them rather than pretending they don't exist.

### Resolved

1. **~~Artifact format specification.~~** V1 format defined: markdown files with YAML frontmatter for dependency tracking and metadata. See "Artifact Format (V1)" section above. Per-artifact schema definitions and examples will be validated during the vertical slice — the format is a hypothesis, not a commitment.
2. **~~Agent communication protocol.~~** V1 answer: the LLM *is* both the framework and the coding agent. Skills switch context within a single LLM session. Artifacts are files in the project directory. The "handoff" is the LLM reading its own generated build plan. See "Skill Interaction Model" section above. This will need revisiting for agent agnosticism (R7.3, v1.5).
3. **~~Persistence and session management.~~** V1 answer: file-based persistence in the project directory. See "Persistence Model (V1)" section above. Session resumption = LLM reads project-state.yaml and artifacts at conversation start.
7. **~~Bootstrapping.~~** Replaced component-by-component build order with vertical slice approach. See "Bootstrapping: Vertical Slice Approach" section above.

### Open

4. **Multi-user collaboration.** Current design assumes single user. Team scenarios need coordination design. [v1.5 or later — no user projects to learn from yet.]
5. **Product concerns we haven't tested.** Games, content platforms, developer tools, IoT-adjacent, data-intensive products. The concern taxonomy may need new dimensions. [Will surface during Phase 2 widening via `missing_guidance` observations. The concern model is designed to evolve — see Product Concern Taxonomy § Concern Evolution.]
6. **Minimum viable Critic.** What's the smallest useful Critic for v1? Likely: spec compliance + test integrity + doc controller. Architectural consistency and operational readness can follow. [Deferred to Phase 2 of bootstrapping.]
8. **Observation capture during product sessions requires framework repo write access.** The Orchestrator instructs writing observation files to `{prawduct-repo}/framework-observations/`, but during product sessions the LLM may be working in a different directory without access to the framework repo. V1 mitigation: fallback to writing observations in the user's project `working-notes/` for manual transfer. Proper fix: a mechanism (MCP server, post-session hook, or shared observation store) that doesn't require direct filesystem access to the framework repo. [Will surface during real product usage.]
