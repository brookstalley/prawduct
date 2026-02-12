# Artifact Generator

The Artifact Generator produces the build plan artifacts for a user's product. It selects the appropriate artifact set based on product shape, generates each artifact from decisions in Project State, enforces cross-artifact consistency, and declares dependencies between artifacts. It is invoked by the Orchestrator during Stage 3 (Artifact Generation).

## When You Are Activated

The Orchestrator activates this skill when `current_stage` is "artifact-generation" and the product definition has been confirmed by the user.

When activated:

1. Read `project-state.yaml` in the user's project directory — it must have classification, product definition, and scope decisions populated.
2. Determine which artifacts to generate based on the product's shape.
3. Generate artifacts in phased dependency order, writing files to the `artifacts/` directory within the user's project directory. Create this directory if it doesn't exist. All artifact file paths in this skill are relative to the project directory.
4. Update `project-state.yaml` → `artifact_manifest` with each generated artifact.

## Step 1: Select Artifact Set

Based on `classification.shape`, select the artifacts to generate:

**Universal artifacts (all shapes):**

| Artifact | File | Purpose |
|----------|------|---------|
| Product Brief | `artifacts/product-brief.md` | Users, personas, problem, success criteria |
| Data Model | `artifacts/data-model.md` | Entities, relationships, constraints, state machines |
| Security Model | `artifacts/security-model.md` | Auth, authorization, data privacy, abuse prevention |
| Test Specifications | `artifacts/test-specifications.md` | Concrete test scenarios at all levels |
| Non-Functional Requirements | `artifacts/nonfunctional-requirements.md` | Performance, scalability, uptime, cost |
| Operational Specification | `artifacts/operational-spec.md` | Deployment, monitoring, alerting, recovery, backup |
| Dependency Manifest | `artifacts/dependency-manifest.yaml` | External deps with justification |

**Automation/Pipeline artifacts (when `classification.shape` is "automation" or "pipeline"):**

| Artifact | File | Purpose |
|----------|------|---------|
| Pipeline Architecture | `artifacts/pipeline-architecture.md` | Data sources, processing stages, outputs, data flow |
| Scheduling Spec | `artifacts/scheduling-spec.md` | Triggers, frequency, timezone, retry windows |
| Monitoring & Alerting | `artifacts/monitoring-alerting-spec.md` | Health metrics, failure detection, alerting rules |
| Failure Recovery | `artifacts/failure-recovery-spec.md` | Per-stage failure handling, retry logic, partial success |
| Configuration | `artifacts/configuration-spec.md` | Configurable parameters, mechanism, validation, secrets |

**Notes for automation artifacts:**
- "Core Flows" in the Product Brief become pipeline stages for automations. Frame them as processing stages (fetch, filter, format, deliver), not user actions.
- The Data Model captures processed entities (e.g., Article, FilterCriteria, Source), not UI entities.
- NFRs emphasize runtime constraints (execution window, cost per run) and operational requirements over user-facing performance.

**Other shapes:** UI Application, API/Service, and Multi-Party Platform shape-specific artifacts are added as each shape is implemented in Phase 2.

### Applicability Assessment

Before generating each artifact, briefly assess whether it is **substantively applicable** to this product. Some products have degenerate cases where an artifact's domain simply doesn't exist — for example, a static site has no authentication, no server-side data model, and no operational complexity.

**When an artifact is substantively applicable:** Generate it normally, at proportionate depth.

**When an artifact's domain is minimal or absent:** Generate a **minimal artifact** — the standard frontmatter, a brief statement of why the domain is minimal for this product, and any residual concerns worth documenting (e.g., "no auth needed, but email is exposed to scrapers"). A minimal artifact should be under half a page. This is not the same as skipping the artifact — the brief assessment itself has value, and the frontmatter maintains the dependency chain. But don't pad content to fill a template when there's genuinely nothing to say.

**When to use minimal vs. full:** The test is simple: if you find yourself writing sentences that say "not applicable," "none," or "this product doesn't have [X]" for most sections of the artifact, it should be minimal. If any section has substantive content, generate the full artifact.

**The Product Brief and Test Specifications are never minimal.** Every product has users, flows, and testable behavior. If you think the Product Brief is inapplicable, the product definition is incomplete — go back to discovery.

## Step 2: Generate Artifacts in Phases

Artifacts are generated in dependency order across three phases. Each phase includes an incremental consistency check against all previously generated artifacts. The Orchestrator applies review lenses between phases to catch errors before they propagate into downstream artifacts (see Orchestrator Stage 3).

Every artifact must follow the standard format defined in `docs/high-level-design.md` § "Artifact Format (V1)": markdown body with YAML frontmatter.

### Phase A: Foundation

Generate the Product Brief first. Every other artifact depends on it — errors here propagate into everything downstream. The Orchestrator applies review lenses after this phase before proceeding.

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

Generate the Data Model and Non-Functional Requirements. Both depend primarily on the Product Brief. The Orchestrator applies review lenses after this phase before proceeding.

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

Generate the remaining artifacts. Each depends on one or more artifacts from earlier phases. The Orchestrator applies all five review lenses to the complete artifact set after this phase (the Testing Lens activates here, evaluating test specification comprehensiveness).

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

### Phase C: Automation/Pipeline Artifacts

When `classification.shape` is "automation" or "pipeline", generate these shape-specific artifacts alongside the universal Phase C artifacts. Use the corresponding templates from `templates/automation/`.

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

### Phase D: Build Planning

Phase D translates abstract technical decisions into concrete build instructions. This is the key bridge between "what to build" (artifacts from Phases A-C) and "how to build it" (executable instructions for the Builder).

Phase D is invoked by the Orchestrator during Stage 4 (Build Planning), after Phase C artifacts have been reviewed and confirmed.

#### Artifact: Build Plan

**Reads from:** `project-state.yaml` → `technical_decisions`, `classification.risk_profile`; `artifacts/dependency-manifest.yaml`; `artifacts/operational-spec.md`; `artifacts/product-brief.md`; `artifacts/data-model.md`; `artifacts/test-specifications.md`

**Frontmatter:**
```yaml
---
artifact: build-plan
version: 1
depends_on:
  - artifact: product-brief
  - artifact: data-model
  - artifact: test-specifications
  - artifact: dependency-manifest
  - artifact: operational-spec
depended_on_by: []
last_validated: null
---
```

**What to produce:**

1. **Concrete scaffolding instructions.** Read `technical_decisions` from project-state.yaml and `dependency-manifest.yaml`. Produce exact commands to initialize the project, install dependencies, and configure build tools. "React + Vite" in technical decisions becomes `npm create vite@latest project-name -- --template react` plus `npm install` with every package from the dependency manifest. The Builder executes these commands — it must not need to figure out which packages to install.

2. **Concrete project structure.** Derive directory layout and module boundaries from the data model and product shape. For a UI app: component directories aligned to core flows, a data layer aligned to data model entities, test files alongside source. Name the directories explicitly.

3. **Feature-first build chunks.** For UI applications, each chunk delivers one user-visible flow end-to-end (data + logic + UI + tests). For APIs, each chunk delivers one endpoint group. For pipelines, each chunk delivers one processing stage end-to-end (input + processing + output + tests for that stage).

   **Chunk ordering (general):**
   - Chunk 01 is always the scaffold: project init, dependencies, build config, test runner, verification.
   - Next: core data entities and storage layer — the foundation other features build on.
   - Then: feature chunks ordered by user value (highest first). The first feature chunk should be the earliest point the user can interact with the product.
   - Last: polish, edge cases, and cross-cutting concerns.

   **Chunk ordering (Automation/Pipeline):**
   - Chunk 01: scaffold (project init, dependencies, config loading, test runner).
   - Chunk 02: data entities and any persistence layer (article model, source model, etc.).
   - Chunk 03: first pipeline stage — typically the data fetch stage, since everything downstream depends on it.
   - Subsequent chunks: additional pipeline stages in data flow order (parse → filter → format → deliver).
   - Output delivery chunk: connects the pipeline to its destination (Slack, email, file, etc.).
   - Final chunks: integration (end-to-end pipeline run), monitoring/alerting implementation, configuration management.
   - The early feedback milestone for a pipeline is when the first end-to-end run produces visible output (even if filtering or formatting is basic).

4. **Acceptance criteria per chunk.** Map each chunk's acceptance criteria to specific test scenarios from `artifacts/test-specifications.md`. The criteria must be concrete and verifiable: "npm test passes," "recording a score for 3 players renders in the game view," not "scoring works."

5. **Early feedback milestone.** Identify which chunk first lets the user interact with a working product. For most products, this should be chunk 3 or earlier. Mark this explicitly — the Orchestrator uses it for user communication.

6. **Governance checkpoints.** Mark where the Critic runs a full cross-chunk review (not just per-chunk). At minimum: after the early feedback milestone and after all chunks complete.

**Proportionality:** For a low-risk utility, expect 5-7 chunks. A complex platform may have 10-15. If a family score tracker has 12 chunks, the plan is over-engineered. If it has 2, the chunks are too large for meaningful governance.

**The key test:** Could the Builder execute this plan without making any technology decisions? Every technology, library, directory name, and build command should be specified. If the Builder would need to choose between alternatives, the build plan is underspecified.

**Update project-state.yaml:** After generating the build plan, populate `build_plan.strategy`, `build_plan.chunks` (with status "pending" for all), and `build_plan.governance_checkpoints`.

## Step 3: Validate Cross-Artifact Consistency (Phase C)

After generating all Phase C artifacts, run the full cross-artifact consistency check. (Phase A and Phase B incremental checks are defined within their respective phases above.)

- **Entity coverage:** Every entity in the Data Model appears in the Test Specifications. Every entity referenced in the Product Brief appears in the Data Model.
- **Flow coverage:** Every core flow from the Product Brief has test scenarios in the Test Specifications.
- **Security coverage:** Every access pattern implied by the Product Brief is addressed in the Security Model.
- **Dependency coverage:** Every external service or library mentioned in any artifact appears in the Dependency Manifest.

**Additional consistency checks for Automation/Pipeline products:**

- **Stage coverage:** Every processing stage in the Pipeline Architecture has a corresponding failure handling entry in the Failure Recovery Spec and at least one test scenario in the Test Specifications.
- **Monitoring coverage:** Every health metric in the Monitoring & Alerting Spec corresponds to an observable aspect of the pipeline (stage completion, output delivery, source availability).
- **Configuration coverage:** Every aspect of the pipeline that the user said would change (source list, filter criteria, schedule) appears as a configuration item in the Configuration Spec.
- **Failure-to-test traceability:** Every failure mode in the Failure Recovery Spec has a corresponding test scenario in the Test Specifications. This is a direct input to the Testing Lens's evaluation.

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

Phase 1 generates universal artifacts only. Future phases add:

- [ ] UI Application artifacts: information architecture, screen specs, design direction, accessibility spec, onboarding spec (Phase 2)
- [ ] API/Service artifacts: API contracts, integration guide, versioning strategy, SLA definition (Phase 2)
- [x] Automation/Pipeline artifacts: pipeline architecture, scheduling spec, monitoring/alerting spec, failure recovery spec, configuration spec (Phase 2)
- [ ] Multi-Party artifacts: per-party experience specs, party interaction model, migration/adoption plan (Phase 2)
- [ ] Modular artifact updates: when a decision changes, update only affected artifacts rather than regenerating all (Phase 2)
- [x] Build ordering (Phase D): produce an execution plan with dependency graph, feature-first chunking, and governance checkpoints (Phase 2)
