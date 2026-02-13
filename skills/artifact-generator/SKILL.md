# Artifact Generator

The Artifact Generator produces the build plan artifacts for a user's product. It selects the appropriate artifact set based on structural characteristics and domain analysis, generates each artifact from decisions in Project State, enforces cross-artifact consistency, and declares dependencies between artifacts. It is invoked by the Orchestrator during Stage 3 (Artifact Generation).

## When You Are Activated

The Orchestrator activates this skill when `current_stage` is "artifact-generation" and the product definition has been confirmed by the user.

When activated:

1. Read `project-state.yaml` in the user's project directory — it must have classification, product definition, and scope decisions populated.
2. Determine which artifacts to generate based on the product's active structural characteristics and domain characteristics.
3. Generate artifacts in phased dependency order, writing files to the `artifacts/` directory within the user's project directory. Create this directory if it doesn't exist. All artifact file paths in this skill are relative to the project directory.
4. Update `project-state.yaml` → `artifact_manifest` with each generated artifact.

## Step 1: Select Artifact Set

Read `classification.structural` and `classification.domain_characteristics` from project-state.yaml. Generate the universal artifact set plus any structurally-triggered artifacts, then assess whether domain characteristics call for additional artifacts not covered by the standard set.

**Universal artifacts (all products):**

| Artifact | File | Purpose |
|----------|------|---------|
| Product Brief | `artifacts/product-brief.md` | Users, personas, problem, success criteria |
| Data Model | `artifacts/data-model.md` | Entities, relationships, constraints, state machines |
| Security Model | `artifacts/security-model.md` | Auth, authorization, data privacy, abuse prevention |
| Test Specifications | `artifacts/test-specifications.md` | Concrete test scenarios at all levels |
| Non-Functional Requirements | `artifacts/nonfunctional-requirements.md` | Performance, scalability, uptime, cost |
| Operational Specification | `artifacts/operational-spec.md` | Deployment, monitoring, alerting, recovery, backup |
| Dependency Manifest | `artifacts/dependency-manifest.yaml` | External deps with justification |

**When `structural.runs_unattended` is active:**

| Artifact | File | Purpose |
|----------|------|---------|
| Pipeline Architecture | `artifacts/pipeline-architecture.md` | Data sources, processing stages, outputs, data flow |
| Scheduling Spec | `artifacts/scheduling-spec.md` | Triggers, frequency, timezone, retry windows |
| Monitoring & Alerting | `artifacts/monitoring-alerting-spec.md` | Health metrics, failure detection, alerting rules |
| Failure Recovery | `artifacts/failure-recovery-spec.md` | Per-stage failure handling, retry logic, partial success |
| Configuration | `artifacts/configuration-spec.md` | Configurable parameters, mechanism, validation, secrets |

**Notes for `runs_unattended` artifacts:**
- "Core Flows" in the Product Brief become pipeline stages. Frame them as processing stages (fetch, filter, format, deliver), not user actions.
- The Data Model captures processed entities (e.g., Article, FilterCriteria, Source), not UI entities.
- NFRs emphasize runtime constraints (execution window, cost per run) and operational requirements over user-facing performance.

**When `structural.has_human_interface` (modality: screen) is active:**

| Artifact | File | Purpose |
|----------|------|---------|
| Information Architecture | `artifacts/information-architecture.md` | Screen inventory, navigation structure, user flows, information hierarchy |
| Screen Specifications | `artifacts/screen-specs.md` | Per-screen layout, data display, user actions, states (all screens in one file) |
| Design Direction | `artifacts/design-direction.md` | Visual identity, color, typography, spacing, component patterns |
| Accessibility Spec | `artifacts/accessibility-spec.md` | Compliance level, keyboard nav, screen reader, contrast, focus management |
| Localization Requirements | `artifacts/localization-requirements.md` | Target locales, string externalization, RTL support, formatting |
| Onboarding Spec | `artifacts/onboarding-spec.md` | First-run experience, empty states, permission requests, progressive disclosure |

**Notes for `has_human_interface` artifacts:**
- "Core Flows" in the Product Brief become screen sequences. Frame them as user journeys through screens (view → act → navigate), not abstract processes.
- The Data Model captures user-facing entities (e.g., Player, Game, Score) that appear on screens. Every data element in the Screen Spec must trace to a Data Model entity.
- NFRs emphasize user-facing performance (load time, interaction responsiveness, animation smoothness) and platform-specific constraints.

**When `structural.exposes_programmatic_interface` is active:**

API-specific artifacts (API contracts, integration guide, versioning strategy, SLA definition) are generated when implemented. Use templates from `templates/api-surface/`.

**When `structural.has_multiple_party_types` is active:**

Multi-party artifacts (per-party experience specs, party interaction model, migration/adoption plan) are generated when implemented. Use templates from `templates/multi-party/`.

### Analysis-Driven Artifact Determination

After selecting structurally-triggered artifacts, review `classification.domain_characteristics` for additional artifact needs not covered by templates. Domain characteristics may surface needs that don't fit existing structural categories but still warrant dedicated artifacts or deepened sections within standard artifacts.

**Examples:**
- A product with domain characteristic "constrained hardware environment" may need a resource budget artifact or a deepened NFR section covering memory ceilings, CPU duty cycles, and power budgets — even though `constrained_environment` is not a structural characteristic.
- A product with domain characteristic "external service integration" may need deepened failure recovery and dependency sections — even when `runs_unattended` isn't active (e.g., an interactive app that calls external APIs).

**Process:** For each domain characteristic, assess whether the universal + structurally-triggered artifacts adequately cover its implications. If not, either (a) add specific sections to existing artifacts addressing the gap, or (b) in rare cases, generate an additional artifact with justification. Prefer deepening existing artifacts over creating new ones.

### Applicability Assessment

Before generating each artifact, briefly assess whether it is **substantively applicable** to this product. Some products have degenerate cases where an artifact's domain simply doesn't exist — for example, a static site has no authentication, no server-side data model, and no operational complexity.

**When an artifact is substantively applicable:** Generate it normally, at proportionate depth.

**When an artifact's domain is minimal or absent:** Generate a **minimal artifact** — the standard frontmatter, a brief statement of why the domain is minimal for this product, and any residual concerns worth documenting (e.g., "no auth needed, but email is exposed to scrapers"). A minimal artifact should be under half a page. This is not the same as skipping the artifact — the brief assessment itself has value, and the frontmatter maintains the dependency chain. But don't pad content to fill a template when there's genuinely nothing to say.

**When to use minimal vs. full:** The test is simple: if you find yourself writing sentences that say "not applicable," "none," or "this product doesn't have [X]" for most sections of the artifact, it should be minimal. If any section has substantive content, generate the full artifact.

**Truly minimal products:** When a product has no persistence, no authentication, no networking, and is single-user local, the Orchestrator may approve generating only Product Brief, Test Specifications, and Dependency Manifest. The remaining universal artifacts (Data Model, Security Model, NFRs, Operational Spec) would each be minimal artifacts documenting absence — generating and reviewing them adds governance overhead without proportionate value. If any of these dimensions is present (even lightly), generate the full set with applicability assessment as above.

**The Product Brief and Test Specifications are never minimal.** Every product has users, flows, and testable behavior. If you think the Product Brief is inapplicable, the product definition is incomplete — go back to discovery.

## Step 2: Generate Artifacts in Phases

Artifacts are generated in dependency order across three phases. Each phase includes an incremental consistency check against all previously generated artifacts. The Orchestrator applies review lenses between phases to catch errors before they propagate into downstream artifacts (see Orchestrator Stage 3).

Every artifact must follow the standard format defined in `docs/high-level-design.md` § "Artifact Format (V1)": markdown body with YAML frontmatter.

### Phase A: Foundation

Generate the Product Brief first. Every other artifact depends on it — errors here propagate into everything downstream. The Orchestrator applies review lenses after this phase and persists findings to `project-state.yaml` → `review_findings.entries` before proceeding.

#### Artifact: Product Brief

**Reads from:** `project-state.yaml` → `product_definition`, `classification`

**Frontmatter:**
```yaml
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
last_validated: null
---
```

**Content must include:**
- **Vision:** One clear sentence (from `product_definition.vision`).
- **Users & Personas:** Who uses this, their needs, constraints, technical level. Drawn from `product_definition.users.personas`.
- **Core Flows:** What users do, in priority order. Drawn from `product_definition.core_flows`.
- **Success Criteria:** How we know this worked. Drawn from `product_definition.goals`.
- **Scope:** What's in v1, what's deferred, what's out. Drawn from `product_definition.scope`.
- **Platform:** Where it runs. Drawn from `product_definition.platform`.

**Proportionality:** For a low-risk utility, this should be 1-2 pages. For a complex platform, it may be longer. Don't pad.

**Incremental check after Phase A:**
- Vision, personas, flows, scope, and platform are all present and internally consistent.
- Every persona has at least one core flow. Every core flow serves at least one persona.

### Phase B: Structure

Generate the Data Model and Non-Functional Requirements. Both depend primarily on the Product Brief. The Orchestrator applies review lenses after this phase and persists findings to `review_findings.entries` before proceeding.

#### Artifact: Data Model

**Reads from:** Product Brief (entities implied by flows), `project-state.yaml` → `technical_decisions.data_model`

**Frontmatter:**
```yaml
---
artifact: data-model
version: 1
depends_on:
  - artifact: product-brief
depended_on_by:
  - artifact: test-specifications
  - artifact: security-model
last_validated: null
---
```

**Content must include:**
- **Entities:** Each entity with its fields, types, and constraints. Derived from the core flows and user personas in the Product Brief.
- **Relationships:** How entities relate (one-to-many, many-to-many, etc.).
- **State machines:** If any entity has lifecycle states (e.g., a game session: setup → in-progress → completed), document the valid transitions.
- **Constraints:** Validation rules, uniqueness requirements, required fields.
- **Experience-critical parameters:** If an entity has fields whose values directly shape the user experience (visual layout proportions, timing intervals, difficulty curves, animation speeds), those values should be specified as concrete fields with constraints and defaults — not left as implementation details. The test: could two different Builders implement this data model and produce noticeably different user experiences? If so, the divergence points need explicit specification.

**Key instruction:** The entities must be traceable back to the Product Brief. If the Product Brief mentions "scores," there must be a Score entity (or equivalent). If there's no entity for something the user talked about, something is missing.

#### Artifact: Non-Functional Requirements

**Reads from:** `project-state.yaml` → `product_definition.nonfunctional`, `classification.risk_profile`

**Frontmatter:**
```yaml
---
artifact: nonfunctional-requirements
version: 1
depends_on:
  - artifact: product-brief
depended_on_by:
  - artifact: operational-spec
  - artifact: dependency-manifest
last_validated: null
---
```

**Content must include:**
- **Performance targets:** Response times, throughput. Proportionate — "pages load in under 2 seconds" is fine for a family app. Don't specify p99 latencies.
- **Scalability:** Expected user and data growth. Be honest — a family app serving 4-10 users doesn't need horizontal scaling.
- **Availability:** Uptime target. "Best-effort" or "should work when family wants to play" is fine for low-risk.
- **Cost constraints:** Budget for hosting, services. Surface this even if the answer is "as cheap as possible."

**Proportionality rule:** NFRs for a family utility should fit on half a page. If you're writing about load balancers and CDNs, recalibrate.

**Incremental check after Phase B:**
- Entity coverage: every entity implied by Product Brief core flows appears in the Data Model. Every persona's data needs are represented.
- NFR targets are consistent with the product's risk profile and platform.

### Phase C: Integration

Generate the remaining artifacts. Each depends on one or more artifacts from earlier phases. The Orchestrator applies all five review lenses to the complete artifact set after this phase (the Testing Lens activates here, evaluating test specification comprehensiveness) and persists all findings to `review_findings.entries`.

#### Artifact: Security Model

**Reads from:** Product Brief (who accesses what), Data Model (what needs protecting), `project-state.yaml` → `classification.risk_profile`

**Frontmatter:**
```yaml
---
artifact: security-model
version: 1
depends_on:
  - artifact: product-brief
  - artifact: data-model
depended_on_by:
  - artifact: test-specifications
  - artifact: operational-spec
last_validated: null
---
```

**Content must include:**
- **Authentication:** How users identify themselves. Proportionate to risk — a family app might just use device-level identification or a simple name picker, not OAuth.
- **Authorization:** Who can access what. What data is shared, what's private.
- **Data Privacy:** What data is collected, how it's stored, who can see it.
- **Abuse Prevention:** What could go wrong if someone acts maliciously? Proportionate to risk — a family app has minimal abuse vectors.

**Proportionality rule:** The security model must match the product's risk profile. A low-risk family utility should NOT have the same security model as a B2B financial platform. If you're writing about OAuth flows and role-based access control for a family score tracker, you've over-engineered it.

#### Artifact: Test Specifications

**Reads from:** Product Brief (flows to test), Data Model (entities to validate), Security Model (access rules to verify)

**Frontmatter:**
```yaml
---
artifact: test-specifications
version: 1
depends_on:
  - artifact: product-brief
  - artifact: data-model
  - artifact: security-model
depended_on_by:
  - artifact: operational-spec
last_validated: null
---
```

**Content must include:**
- **Test scenarios organized by flow:** For each core flow from the Product Brief, specify concrete test cases.
- **Happy path tests:** The normal, expected flow works.
- **Error cases:** What happens when things go wrong (invalid input, missing data, network failure).
- **Edge cases:** Boundary conditions, empty states, maximum values.
- **State coverage:** For entities with lifecycles, test each valid transition AND at least one invalid transition.

**Key instruction:** Test scenarios must be **specific and concrete**, not generic.

- **Bad:** "Test that scoring works."
- **Good:** "Test recording a score of 47 for Player 'Alice' in a game of Catan with 3 players. Verify the score appears in the game session, the player's history updates, and the leaderboard recalculates."

Each test must specify: the setup (preconditions), the action (what the user or system does), and the expected result (what should happen).

#### Artifact: Operational Specification

**Reads from:** NFRs, Security Model, `project-state.yaml` → `technical_decisions.operational`

**Frontmatter:**
```yaml
---
artifact: operational-spec
version: 1
depends_on:
  - artifact: nonfunctional-requirements
  - artifact: security-model
depended_on_by:
  - artifact: dependency-manifest
last_validated: null
---
```

**Content must include:**
- **Deployment:** How and where. For a simple app: single deployment target, simple process.
- **Backup & recovery:** How data is backed up. Even a family app should have basic backup.
- **Monitoring:** What to watch. Proportionate — "is the app responding?" is sufficient for low-risk.
- **Failure recovery:** What happens if it goes down. For low-risk: "restart it."

#### Artifact: Dependency Manifest

**Reads from:** All other artifacts (what external services, libraries, or APIs are needed)

**Frontmatter:**
```yaml
---
artifact: dependency-manifest
version: 1
depends_on:
  - artifact: product-brief
  - artifact: data-model
  - artifact: operational-spec
depended_on_by: []
last_validated: null
---
```

**Format:** YAML, not markdown.

**Each dependency entry:**
```yaml
dependencies:
  - name: "[library or service name]"
    type: library | service | api | infrastructure
    justification: "Why this is needed and why this specific choice"
    alternatives_considered: ["alt1", "alt2"]
    version: "pinned or range"
    cost: "free | estimated monthly cost"
    risk: "What happens if this dependency disappears or breaks"
```

**Key instruction:** Every dependency must have a justification. "It's popular" is not a justification. "It provides [specific capability] that we need for [specific feature], and the alternatives [X, Y] were rejected because [reasons]" is.

### Phase C: Unattended Operation Artifacts

When `structural.runs_unattended` is active, generate these structurally-triggered artifacts alongside the universal Phase C artifacts. Use the corresponding templates from `templates/unattended-operation/`.

#### Artifact: Pipeline Architecture

**Reads from:** Product Brief (pipeline stages from core flows), Data Model (entities flowing through the pipeline), `project-state.yaml` → `technical_decisions`

**Frontmatter:**
```yaml
---
artifact: pipeline-architecture
version: 1
depends_on:
  - artifact: product-brief
depended_on_by:
  - artifact: scheduling-spec
  - artifact: monitoring-alerting-spec
  - artifact: failure-recovery-spec
  - artifact: test-specifications
last_validated: null
---
```

**Content must include:**
- **Data sources:** Every external source with access method, auth, format, rate limits, and reliability expectations.
- **Processing stages:** Each stage in data flow order — input, processing logic, output, dependencies, and failure behavior.
- **Outputs:** Every destination with format, delivery method, and success criteria.
- **Data flow diagram:** Text-based visualization of the complete pipeline.
- **Data retention:** What's stored between runs, retention period, cleanup.
- **Pipeline boundaries:** What this pipeline does NOT do.

**Proportionality:** For a simple side-project pipeline, this may be 1-2 pages. For a complex ETL system, it may be longer. The level of detail for each stage should match its complexity and failure risk.

#### Artifact: Scheduling Spec

**Reads from:** Pipeline Architecture (what runs), NFRs (timing constraints), `project-state.yaml` → `product_definition.nonfunctional`

**Frontmatter:**
```yaml
---
artifact: scheduling-spec
version: 1
depends_on:
  - artifact: pipeline-architecture
  - artifact: nonfunctional-requirements
depended_on_by:
  - artifact: monitoring-alerting-spec
  - artifact: configuration-spec
last_validated: null
---
```

**Content must include:**
- **Trigger type:** Scheduled (cron), event-driven, or hybrid — with rationale.
- **Schedule:** Frequency, time, timezone, cron expression.
- **Execution window:** Expected duration, timeout, behavior on timeout.
- **Concurrency:** What happens if runs overlap.
- **Retry policy:** When and how failed runs are retried.
- **Manual trigger:** How to run the pipeline outside its schedule.

#### Artifact: Monitoring & Alerting Spec

**Reads from:** Pipeline Architecture (what to monitor), Scheduling Spec (when it should run), NFRs (availability targets)

**Frontmatter:**
```yaml
---
artifact: monitoring-alerting-spec
version: 1
depends_on:
  - artifact: pipeline-architecture
  - artifact: scheduling-spec
  - artifact: nonfunctional-requirements
depended_on_by:
  - artifact: test-specifications
  - artifact: operational-spec
last_validated: null
---
```

**Content must include:**
- **Health metrics:** What indicates the pipeline is healthy (run completion, duration, items processed, error count, source availability).
- **Failure detection:** How each failure type is detected — total failure, partial failure, silent failure, degraded performance.
- **Alerting rules:** For each alertable condition: trigger, severity, notification channel, expected response.
- **Logging:** What's logged, where, at what level, retention.
- **Distinguishing "no data" from "failure."** This is critical and must be explicitly addressed. A pipeline that finds nothing new looks identical to a pipeline that failed to fetch — unless the monitoring is designed to tell them apart.

**Key instruction:** Monitoring findings must be specific and actionable: "alert when no articles posted for 2 consecutive days" not "implement monitoring." Generic monitoring specs are worse than none — they create false confidence.

#### Artifact: Failure Recovery Spec

**Reads from:** Pipeline Architecture (stages that can fail), Monitoring & Alerting Spec (how failures are detected)

**Frontmatter:**
```yaml
---
artifact: failure-recovery-spec
version: 1
depends_on:
  - artifact: pipeline-architecture
  - artifact: monitoring-alerting-spec
depended_on_by:
  - artifact: test-specifications
  - artifact: configuration-spec
last_validated: null
---
```

**Content must include:**
- **Per-stage failure handling:** For every processing stage — failure modes, behavior on failure, impact on downstream stages, recovery action.
- **Partial success behavior:** What happens when some sources succeed and others fail. Is partial output delivered? At what threshold is it too degraded?
- **Retry logic:** Which failures are retryable, retry count, delay strategy, exhaustion behavior.
- **Dead letter / failed item handling:** Proportionate to product risk — log and skip for side projects, dead letter queues for critical systems.
- **Data integrity on failure:** Idempotency, duplicate output risk, state cleanup.
- **Recovery procedures:** How to diagnose and manually recover.

**Key instruction:** Every stage in the Pipeline Architecture must have a corresponding failure handling entry here. If a stage can fail (and all stages can), its failure behavior must be specified.

#### Artifact: Configuration Spec

**Reads from:** Pipeline Architecture (what's configurable), Failure Recovery Spec (configuration validation), `project-state.yaml` → `product_definition`

**Frontmatter:**
```yaml
---
artifact: configuration-spec
version: 1
depends_on:
  - artifact: pipeline-architecture
  - artifact: failure-recovery-spec
depended_on_by:
  - artifact: test-specifications
  - artifact: dependency-manifest
last_validated: null
---
```

**Content must include:**
- **Configuration items:** Each configurable parameter with purpose, type, default, constraints, and examples.
- **Configuration mechanism:** How config is stored and loaded (file, env vars, combination). Proportionate to product complexity.
- **Configuration validation:** Startup validation, required vs. optional fields, behavior with invalid config.
- **Configuration changes:** How changes are applied (restart, hot-reload, between runs).
- **Secrets management:** How API keys and tokens are stored and rotated. Proportionate — env vars are fine for side projects.

### Phase C: Human Interface Artifacts

When `structural.has_human_interface` (modality: screen) is active, generate these structurally-triggered artifacts alongside the universal Phase C artifacts. Use the corresponding templates from `templates/human-interface/`.

#### Artifact: Information Architecture

**Reads from:** Product Brief (screens implied by core flows, personas, platform), `project-state.yaml` → `product_definition`

**Frontmatter:**
```yaml
---
artifact: information-architecture
version: 1
depends_on:
  - artifact: product-brief
depended_on_by:
  - artifact: screen-spec
  - artifact: localization-requirements
  - artifact: onboarding-spec
  - artifact: accessibility-spec
last_validated: null
---
```

**Content must include:**
- **Screen inventory:** Every distinct screen with purpose, primary persona(s), entry points, and priority.
- **Navigation structure:** Primary pattern (tab bar, drawer, stack), hierarchy, persistent vs. contextual elements, back/escape behavior.
- **User flows:** For each core flow, the screen sequence from start to completion — starting screen, actions, transitions, ending state.
- **Information hierarchy:** Per-screen priority ranking of content, actions, and status indicators.
- **Screen states:** For each screen, the empty, loading, populated, and error states.
- **Boundaries:** What the interface does NOT include.

**Key instruction:** Every core flow from the Product Brief must map to a screen sequence. If a flow can't be traced through specific screens, the screen inventory is incomplete.

**Proportionality:** For a low-risk utility, 1-2 pages. For a complex multi-screen app, proportionally more. If you're documenting 20 screens for a family score tracker, recalibrate.

#### Artifact: Screen Specifications

**Reads from:** Information Architecture (screen inventory, flows), Data Model (entities displayed), `project-state.yaml` → `product_definition`

**Frontmatter:**
```yaml
---
artifact: screen-spec
version: 1
depends_on:
  - artifact: information-architecture
  - artifact: data-model
depended_on_by:
  - artifact: onboarding-spec
  - artifact: accessibility-spec
  - artifact: test-specifications
last_validated: null
---
```

**Content must include (per screen):**
- **Purpose:** One sentence — why this screen exists.
- **Layout:** Spatial arrangement of content and controls. For cross-platform products, describe shared layout intent first, then per-platform differences.
- **Data displayed:** Each data element with source entity/field from the Data Model, display format, and update behavior.
- **User actions:** Each action with trigger, result, and validation behavior.
- **States:** Empty, loading, populated, error, and any screen-specific states.
- **Navigation:** Entry points, exit points, back behavior.

**Key instruction:** Every data element must trace to a Data Model entity. Every action must trace to a core flow step. If a data element or action can't be traced, the upstream artifacts are incomplete.

**Proportionality:** For a low-risk utility, half a page per screen. Don't pad with implementation details the Builder doesn't need.

#### Artifact: Design Direction

**Reads from:** Product Brief (product identity, platform, personas), `project-state.yaml` → `design_decisions`

**Frontmatter:**
```yaml
---
artifact: design-direction
version: 1
depends_on:
  - artifact: product-brief
depended_on_by:
  - artifact: onboarding-spec
  - artifact: accessibility-spec
last_validated: null
---
```

**Content must include:**
- **Visual identity:** Style reference, mood, constraints.
- **Color:** Concrete hex values for primary, secondary, background, text, and semantic colors (error/warning/success).
- **Typography:** Font families, sizes (heading/body/caption), weights.
- **Spacing & layout:** Base spacing unit, margins, content width, touch target minimums.
- **Component patterns:** Reusable elements (buttons, inputs, cards, navigation, feedback). For cross-platform products, shared design tokens first, then per-platform patterns.
- **Motion & transitions:** Screen transitions, feedback animations, duration guidelines, reduced motion behavior.
- **Platform conventions:** Which conventions to follow, intentional deviations with rationale.

**Key instruction:** Concrete enough that the Builder doesn't make aesthetic choices. Specific colors, fonts, spacing — not "clean and modern." If two Builders reading this spec would produce visually different products, it's underspecified.

**Proportionality:** For a low-risk utility, half a page. For a consumer product with brand requirements, proportionally more.

#### Artifact: Accessibility Spec

**Reads from:** Screen Specifications (elements needing accessibility), Design Direction (color/contrast, motion), NFRs (platform requirements)

**Frontmatter:**
```yaml
---
artifact: accessibility-spec
version: 1
depends_on:
  - artifact: screen-spec
  - artifact: design-direction
  - artifact: nonfunctional-requirements
depended_on_by:
  - artifact: test-specifications
last_validated: null
---
```

**Content must include:**
- **Target compliance level:** WCAG level, platform guidelines, or game accessibility guidelines.
- **Keyboard navigation:** Tab order, shortcuts, focus indicators, trap prevention.
- **Screen reader support:** Semantic structure, labels, alt text, dynamic announcements.
- **Color & contrast:** Minimum ratios, non-color state indicators, colorblind safety.
- **Focus management:** Initial focus, modal focus, dynamic content focus, restoration.
- **Touch targets:** Minimum sizes per platform, spacing, gesture alternatives.
- **Reduced motion:** What changes, how to detect preference.
- **Platform-specific guidance:** Platform accessibility features to support.

**Key instruction:** Requirements must be testable. "Accessible" is not a requirement. "4.5:1 contrast ratio for body text" is. Every requirement in this spec should be verifiable during build.

**Proportionality:** For a low-risk utility, a third of a page covering compliance target and key requirements. Don't write a full WCAG audit plan for a family app.

#### Artifact: Localization Requirements

**Reads from:** Information Architecture (screens with text), Product Brief (target audience, locale)

**Frontmatter:**
```yaml
---
artifact: localization-requirements
version: 1
depends_on:
  - artifact: information-architecture
  - artifact: product-brief
depended_on_by:
  - artifact: test-specifications
last_validated: null
---
```

**Content must include:**
- **Target locales:** Primary locale and any additional locales. Whether localization is planned for later (affects string externalization now).
- **String externalization:** Whether strings are externalized, file format, key naming convention, interpolation format.
- **RTL support:** Whether required, and if so, layout and text considerations.
- **Date/time/number formatting:** Locale-aware or fixed, specific format decisions.
- **Locale-specific adjustments:** Text expansion accommodation, cultural considerations.
- **Pluralization:** Strategy for handling plural forms.

**Key instruction:** "English only" is valid but must be explicit. The Builder must know whether to externalize strings even for a single-locale product — if localization is planned later, externalize now.

**Proportionality:** For a low-risk personal utility with a single locale, a quarter page. State "English only, no localization planned, strings inline" and move on.

#### Artifact: Onboarding Spec

**Reads from:** Information Architecture (screen inventory, flows), Screen Specifications (states, layout), Design Direction (visual patterns)

**Frontmatter:**
```yaml
---
artifact: onboarding-spec
version: 1
depends_on:
  - artifact: information-architecture
  - artifact: screen-spec
  - artifact: design-direction
depended_on_by:
  - artifact: test-specifications
last_validated: null
---
```

**Content must include:**
- **First-run experience:** What happens on first launch — setup steps, initial screen, path to core value. For cross-platform products, describe per-platform first-run paths (e.g., iOS: App Store → launch → permissions; Web: landing page → sign up → email verify).
- **Progressive disclosure:** What's visible immediately vs. discovered later, how advanced features are surfaced.
- **Empty states:** Per-screen empty state message (specific text), call to action, visual treatment.
- **Permission requests:** Each permission with when requested, user-facing explanation, denied behavior, re-prompt policy.
- **Tutorial approach:** Method (tooltips, walkthrough, none), which features, skippability, repeat access.
- **Return-user experience:** State restoration, change indicators, re-engagement (if applicable).

**Key instruction:** Onboarding is a core flow, not an afterthought. Every permission request must specify what happens when denied. The first-run experience should reach core value as fast as possible.

**Proportionality:** For a low-risk utility, half a page. "No tutorial needed, clear empty states, no permissions required" may be the entire spec.

### Phase D: Build Planning

Phase D translates abstract technical decisions into concrete build instructions. This is the key bridge between "what to build" (artifacts from Phases A-C) and "how to build it" (executable instructions for the Builder).

Phase D is invoked by the Orchestrator during Stage 4 (Build Planning), after Phase C artifacts have been reviewed and confirmed.

#### Artifact: Build Plan

**Reads from:** `project-state.yaml` → `technical_decisions`, `classification.risk_profile`; `artifacts/dependency-manifest.yaml`; `artifacts/operational-spec.md`; `artifacts/product-brief.md`; `artifacts/data-model.md`; `artifacts/test-specifications.md`; `artifacts/nonfunctional-requirements.md`

**Frontmatter:**
```yaml
---
artifact: build-plan
version: 1
depends_on:
  - artifact: product-brief
  - artifact: data-model
  - artifact: test-specifications
  - artifact: nonfunctional-requirements
  - artifact: dependency-manifest
  - artifact: operational-spec
depended_on_by: []
last_validated: null
---
```

**What to produce:**

1. **Concrete scaffolding instructions.** Read `technical_decisions` from project-state.yaml and `dependency-manifest.yaml`. Produce exact commands to initialize the project, install dependencies, and configure build tools. "React + Vite" in technical decisions becomes `npm create vite@latest project-name -- --template react` plus `npm install` with every package from the dependency manifest. The Builder executes these commands — it must not need to figure out which packages to install.

2. **Concrete project structure.** Derive directory layout and module boundaries from the data model and product shape. For a UI app: component directories aligned to core flows, a data layer aligned to data model entities, test files alongside source. Name the directories explicitly.

3. **Feature-first build chunks.** For products with `has_human_interface`, each chunk delivers one user-visible flow end-to-end (data + logic + UI + tests). For products with `exposes_programmatic_interface`, each chunk delivers one endpoint group. For products with `runs_unattended`, each chunk delivers one processing stage end-to-end (input + processing + output + tests for that stage).

   **Chunk ordering (general):**
   - Chunk 01 is always the scaffold: project init, dependencies, build config, test runner, verification.
   - Next: core data entities and storage layer — the foundation other features build on.
   - Then: feature chunks ordered by user value (highest first). The first feature chunk should be the earliest point the user can interact with the product.
   - Last: polish, edge cases, and cross-cutting concerns.

   **Chunk ordering (when `runs_unattended` is active):**
   - Chunk 01: scaffold (project init, dependencies, config loading, test runner).
   - Chunk 02: data entities and any persistence layer (article model, source model, etc.).
   - Chunk 03: first pipeline stage — typically the data fetch stage, since everything downstream depends on it.
   - Subsequent chunks: additional pipeline stages in data flow order (parse → filter → format → deliver).
   - Output delivery chunk: connects the pipeline to its destination (Slack, email, file, etc.).
   - Final chunks: integration (end-to-end pipeline run), monitoring/alerting implementation, configuration management.
   - The early feedback milestone for an unattended system is when the first end-to-end run produces visible output (even if filtering or formatting is basic).

   **Chunk ordering (when `has_human_interface` is active):**
   - Chunk 01: scaffold (project init, dependencies, build config, test runner, dev server).
   - Chunk 02: data entities + UI shell with navigation skeleton (app chrome, empty screens wired together).
   - Chunk 03: first user-visible flow end-to-end (data + logic + UI + tests) — this is the early feedback milestone.
   - Subsequent chunks: remaining core flows in priority order. Each chunk delivers one flow end-to-end (screen + data + tests).
   - Late chunks: design polish (applying design direction tokens), accessibility implementation (from accessibility spec), onboarding implementation (from onboarding spec).
   - The early feedback milestone for a screen-based product is when the user can complete one core flow visually in the running app.

4. **Acceptance criteria per chunk.** Map each chunk's acceptance criteria to specific test scenarios from `artifacts/test-specifications.md`. The criteria must be concrete and verifiable: "npm test passes," "recording a score for 3 players renders in the game view," not "scoring works."

5. **Early feedback milestone.** Identify which chunk first lets the user interact with a working product. For most products, this should be chunk 3 or earlier. Mark this explicitly — the Orchestrator uses it for user communication.

6. **Governance checkpoints.** Mark where the Critic runs a full cross-chunk review (not just per-chunk). At minimum: after the early feedback milestone and after all chunks complete.

**Proportionality:** For a low-risk utility, expect 5-7 chunks. A complex platform may have 10-15. If a family score tracker has 12 chunks, the plan is over-engineered. If it has 2, the chunks are too large for meaningful governance.

**NFR technique traceability:** For every NFR that constrains *how* something is built (not just performance targets), the build plan must include a concrete implementation instruction in the relevant chunk. NFR targets ("30 FPS", "under 2 second startup") become chunk acceptance criteria. NFR techniques ("dirty-rect rendering", "connection pooling", "batch processing") become chunk implementation instructions with enough detail that the Builder doesn't need to choose an approach. If the NFR says "only redraw changed portions," the chunk must say "track changed positions and redraw only those; do not clear the full screen each frame." The test: if the Builder follows the chunk instructions literally, will the NFR technique be implemented?

**Platform-specific scaffolding constraints:** Some platforms impose structural constraints that affect testability, packaging, or distribution. The build plan must account for these in the scaffolding and packaging instructions — the Builder should not need to discover them mid-build. Examples of what to check: Does the target platform's build system allow test targets to import executable targets? (If not, the scaffold must split into library + executable.) Does the target platform require a specific packaging format (app bundle, APK, installer) for features like system integration, launch-at-login, or background execution? If so, include packaging as an explicit scaffolding step or dedicated chunk.

**The key test:** Could the Builder execute this plan without making any technology decisions? Every technology, library, directory name, and build command should be specified. If the Builder would need to choose between alternatives, the build plan is underspecified.

**Update project-state.yaml:** After generating the build plan, populate `build_plan.strategy`, `build_plan.chunks` (with status "pending" for all), and `build_plan.governance_checkpoints`.

## Step 3: Validate Cross-Artifact Consistency (Phase C)

After generating all Phase C artifacts, run the full cross-artifact consistency check. (Phase A and Phase B incremental checks are defined within their respective phases above.)

- **Entity coverage:** Every entity in the Data Model appears in the Test Specifications. Every entity referenced in the Product Brief appears in the Data Model.
- **Flow coverage:** Every core flow from the Product Brief has test scenarios in the Test Specifications.
- **Security coverage:** Every access pattern implied by the Product Brief is addressed in the Security Model.
- **Dependency coverage:** Every external service or library mentioned in any artifact appears in the Dependency Manifest.

**Additional consistency checks when `structural.runs_unattended` is active:**

- **Stage coverage:** Every processing stage in the Pipeline Architecture has a corresponding failure handling entry in the Failure Recovery Spec and at least one test scenario in the Test Specifications.
- **Monitoring coverage:** Every health metric in the Monitoring & Alerting Spec corresponds to an observable aspect of the pipeline (stage completion, output delivery, source availability).
- **Configuration coverage:** Every aspect of the pipeline that the user said would change (source list, filter criteria, schedule) appears as a configuration item in the Configuration Spec.
- **Failure-to-test traceability:** Every failure mode in the Failure Recovery Spec has a corresponding test scenario in the Test Specifications. This is a direct input to the Testing Lens's evaluation.

**Additional consistency checks when `structural.has_human_interface` is active:**

- **Screen coverage:** Every screen in the Information Architecture has a corresponding section in the Screen Specifications. Every core flow from the Product Brief maps to a screen sequence in the Information Architecture.
- **Data display traceability:** Every data element shown in Screen Specifications traces to a Data Model entity. If a screen displays data that doesn't exist in the Data Model, the Data Model is incomplete.
- **Accessibility coverage:** Every interactive element type in the Screen Specifications (buttons, inputs, navigation) has corresponding accessibility requirements in the Accessibility Spec. Color values in the Design Direction meet the contrast ratios specified in the Accessibility Spec.
- **State coverage:** Every screen state defined in the Information Architecture (empty, loading, populated, error) has a corresponding specification in Screen Specifications with specific content/behavior.
- **Onboarding-to-screen traceability:** Every screen referenced in the Onboarding Spec (first-run, empty states, permission request contexts) exists in the Information Architecture and has a corresponding Screen Specification.

If any inconsistency is found, fix it before presenting artifacts to the user.

## Step 4: Update Artifact Manifest

Write each generated artifact to `project-state.yaml` → `artifact_manifest.artifacts`:

```yaml
artifacts:
  - name: product-brief
    file_path: artifacts/product-brief.md
    version: 1
    depends_on: [project-state]
    depended_on_by: [data-model, security-model, test-specifications]
    last_validated: null
    tier: 1
  # ... (one entry per artifact)
```

## Extending This Skill

Remaining artifact template work is tracked in `project-state.yaml` → `build_plan.remaining_work`.

When adding structurally-triggered artifacts:
1. Create a templates directory under `templates/` named for the structural characteristic (e.g., `templates/api-surface/`).
2. Add one template per artifact, following the YAML frontmatter format defined in `docs/high-level-design.md` § "Artifact Format (V1)".
3. Add the structural characteristic's artifact list to this skill's Phase C section, following the pattern of the `runs_unattended` artifacts block.
4. Update the artifact dependency model if the new artifacts have cross-characteristic dependencies.
5. Register the template directory in `docs/doc-manifest.yaml`.
