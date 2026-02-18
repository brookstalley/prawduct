# Artifact Generator

The Artifact Generator produces the build plan artifacts for a user's product. It selects the appropriate artifact set based on structural characteristics and domain analysis, generates each artifact from decisions in Project State, enforces cross-artifact consistency, and declares dependencies between artifacts. It is invoked by the Orchestrator during Stage 3 (Artifact Generation).

## When You Are Activated

The Orchestrator activates this skill when `current_stage` is "artifact-generation" and the product definition has been confirmed by the user.

When activated:

1. Read `project-state.yaml` in the user's project directory — it must have classification, product definition, and scope decisions populated.
2. Determine which artifacts to generate based on the product's active structural characteristics and domain characteristics.
3. Generate artifacts in phased dependency order, writing files to the `artifacts/` directory within the product root. Create this directory if it doesn't exist. All artifact file paths in this skill are relative to the product root (`.prawduct/` for all repos).
4. Update `project-state.yaml` → `artifact_manifest` with each generated artifact.

## Step 1: Select Artifact Set

Read `classification.structural` and `classification.domain_characteristics` from project-state.yaml. Generate the universal artifact set plus any structurally-triggered artifacts, then assess whether domain characteristics call for additional artifacts.

**Universal artifacts (all products):**

| Artifact | Template | Purpose |
|----------|----------|---------|
| Product Brief | `templates/product-brief.md` | Users, personas, problem, success criteria |
| Data Model | `templates/data-model.md` | Entities, relationships, constraints, state machines |
| Security Model | `templates/security-model.md` | Auth, authorization, data privacy, abuse prevention |
| Test Specifications | `templates/test-specifications.md` | Concrete test scenarios at all levels |
| Non-Functional Requirements | `templates/nonfunctional-requirements.md` | Performance, scalability, uptime, cost |
| Operational Specification | `templates/operational-spec.md` | Deployment, monitoring, alerting, recovery |
| Dependency Manifest | `templates/dependency-manifest.yaml` | External deps with justification |

**When `structural.runs_unattended` is active:**

Read templates from `templates/unattended-operation/`. Generate: Pipeline Architecture, Scheduling Spec, Monitoring & Alerting, Failure Recovery, Configuration.

Notes for `runs_unattended`: "Core Flows" become pipeline stages. Data Model captures processed entities. NFRs emphasize runtime constraints and operational requirements.

**When `structural.has_human_interface` is active:**

Consult the `has_human_interface` amplification rules (in the "Structural Amplification Rules for Artifact Generation" section below) to determine what artifacts to generate based on modality. For screen-modality products, read templates from `templates/human-interface/` as structural reference. For other modalities, generate appropriate artifacts guided by the amplification rules and constrained by the process constraints.

Notes for `has_human_interface`: "Core Flows" become user journeys through the interface (modality-dependent). Data Model captures user-facing entities. NFRs emphasize user-perceived performance.

**For all structural characteristics:** Consult the Structural Amplification Rules for Artifact Generation section below. When templates exist for the characteristic and modality, use them as structural reference. When templates don't exist, dynamically generate appropriate artifacts guided by the amplification rules and constrained by the process constraints. Either path produces valid artifacts — templates are an optimization for proven structures, not a requirement.

## Structural Amplification Rules for Artifact Generation

Each structural characteristic has three layers that guide artifact generation:

1. **Amplification rules** — what additional artifact concerns to generate and how universal artifacts deepen.
2. **Process constraints** — quality properties that must hold regardless of modality. The Critic and Review Lenses verify these.
3. **Template reference** — when templates exist for this characteristic and modality, use them as structural reference; otherwise generate appropriate artifacts guided by the amplification rules and constrained by the process constraints.

### `has_human_interface`

**Amplification rules:** Generate interface structure artifact, interaction specifications, design direction, accessibility specification, onboarding specification. Specific artifacts depend on modality — screen-based products get IA and screen specs; terminal products get interaction model and display specs; minimal interfaces (firmware, LED panels) get input/output mapping and feedback specifications. The LLM determines appropriate artifacts for the modality using its own domain knowledge.

Universal artifact deepening: Product Brief frames "Core Flows" as user journeys through the interface. Data Model captures user-facing entities with experience-critical parameters as concrete fields. NFRs emphasize user-perceived performance (responsiveness, frame rates, animation timing). Security Model addresses interface-specific concerns (session management, input validation, client-side data exposure).

**Process constraints:**
- Structure before details: interface structure (information architecture, interaction model, input/output mapping) must be complete before implementation specs.
- All states specified: every user-facing element must specify its states (empty, loading, populated, error — or modality-appropriate equivalents such as idle/active/fault for firmware, or prompt/processing/result for CLIs).
- Accessibility alongside design, not after (HR7).
- Every interaction traces to a core flow; every data element traces to Data Model.
- Experience-critical parameters concretely specified: frame rates, response times, animation timing, physical feedback characteristics — whatever is perceptible to the user and would diverge if left to implementation.

**Verification amplification:** When the user opted into agent verification during discovery, include verification infrastructure in artifact generation. For web modality: MCP server with browser automation is the preferred approach (rich, typed tool access to the running product). For terminal modality: process I/O via Bash is usually sufficient. For desktop: platform-appropriate automation. Verification infrastructure is development-only (HR10). See `docs/high-level-design.md` § Agent Verification Architecture.

**Template reference:** `templates/human-interface/` provides proven structure for screen-modality products. For other modalities, amplification rules + process constraints guide generation.

### `runs_unattended`

**Amplification rules:** Generate pipeline architecture, scheduling specification, monitoring & alerting, failure recovery, configuration specification. "Core Flows" become pipeline stages. Data Model captures processed entities. NFRs emphasize runtime constraints and operational requirements.

Universal artifact deepening: Product Brief frames success criteria for headless operation ("digest delivered by 7 AM" not "works well"). Security Model addresses credential management for external services. Test Specs include silent-failure detection and partial-success scenarios. Test Strategy addresses test levels: unit tests for processing logic and business rules, integration tests for service interactions with external dependency mocking, E2E tests for full pipeline execution from trigger to output.

**Process constraints:**
- Silent failure is default mode — monitoring must distinguish "no results" from "didn't run."
- Every pipeline stage has failure handling and corresponding tests.
- Every external dependency has resilience handling (retry, circuit break, fallback).
- Idempotency: if the system runs twice, it must not produce duplicate output.
- Configuration is validated at startup, not at first use.

**Verification amplification:** For unattended systems, Bash-based verification is usually sufficient — run the pipeline and inspect outputs/logs. MCP servers are warranted only when pipeline state is complex or requires real-time observation. Verification scenarios: pipeline executes end-to-end, outputs are correct, idempotency holds, failure modes are observable.

**Template reference:** `templates/unattended-operation/` provides proven structure.

### `exposes_programmatic_interface`

**Amplification rules:** Generate API contract artifact (operations, request/response shapes, error codes, auth, rate limits), versioning strategy section (in operational spec or standalone).

Universal artifact deepening: Data Model gets API-facing schemas and request/response types. Security Model gets consumer authentication, rate limiting, API key management. Test Specs get contract testing and backward compatibility tests; Test Strategy includes contract tests as a distinct level verifying API shape and behavior stability across versions. NFRs get latency SLAs, throughput targets, availability guarantees. Operational Spec gets consumer impact analysis and deprecation procedures.

**Process constraints:**
- Every API operation traces to a core flow (operations serve use cases, not implementation convenience).
- Every error code has a documented meaning and at least one test scenario.
- Backward compatibility strategy is explicit before any versioning decisions.
- Consumer experience is first-class: error messages are helpful, not just status codes.
- Rate limiting and authentication are specified per-consumer-type, not globally.

**Verification amplification:** For APIs, Bash with curl/httpie plus contract tests provides adequate verification. MCP servers are warranted when the API has complex state requiring inspection between calls (connection pools, caches, session state).

**Template reference:** None currently. Dynamic generation guided by amplification rules + process constraints.

### `has_multiple_party_types`

**Amplification rules:** Generate per-party experience specification (each party's flows, needs, constraints), party interaction model (how parties affect each other, trust boundaries, data visibility).

Universal artifact deepening: Product Brief gets per-party personas and flows. Data Model gets party-scoped entities and cross-party trust boundaries. Security Model gets per-party access controls and cross-party data isolation. Test Specs get per-party flow tests and cross-party interaction tests.

**Process constraints:**
- Each party's needs discovered independently (don't conflate distinct user types).
- Trust boundaries explicit: one party's data never leaks to another unless designed.
- Cross-party interactions modeled bidirectionally (what A does affects B, and vice versa).
- Every party has at least one complete flow from entry to core value.
- Power asymmetries acknowledged (marketplace seller vs. buyer, teacher vs. student).

**Template reference:** None currently. Dynamic generation guided by amplification rules + process constraints.

### `handles_sensitive_data`

**Amplification rules:** No additional standalone artifacts — deepens existing ones. Security Model gets data classification, lifecycle (collection → storage → access → deletion), breach scenarios, audit requirements. Data Model gets retention policies and access audit fields. Test Specs get access control verification and data lifecycle tests. Operational Spec gets audit logging, breach response procedures, data destruction verification.

**Process constraints:**
- Every sensitive entity has full lifecycle defined (how collected, stored, accessed, deleted).
- Data minimization: justify what's collected; don't collect "just in case."
- Access patterns have audit trails.
- Retention policies have enforcement mechanisms (not just documentation).
- Breach scenario is specified (what happens, who's notified, what's the recovery path).

**Template reference:** None needed — deepening existing artifacts.

---

### Analysis-Driven Artifact Determination

After selecting structurally-triggered artifacts, review `classification.domain_characteristics` for additional artifact needs not covered by templates. Domain characteristics may surface needs that don't fit existing structural categories but still warrant dedicated artifacts or deepened sections within standard artifacts.

**Process:** For each domain characteristic, assess whether the universal + structurally-triggered artifacts adequately cover its implications. If not, either (a) add specific sections to existing artifacts addressing the gap, or (b) in rare cases, generate an additional artifact with justification. Prefer deepening existing artifacts over creating new ones.

### Applicability Assessment

Before generating each artifact, assess whether it is **substantively applicable** to this product.

**When substantively applicable:** Generate it normally, at proportionate depth.

**When minimal or absent:** Generate a **minimal artifact** — standard frontmatter, a brief statement of why the domain is minimal, and any residual concerns. Under half a page. This is not skipping — the assessment has value and the frontmatter maintains the dependency chain.

**When to use minimal vs. full:** If you find yourself writing "not applicable" or "none" for most sections, it should be minimal.

**Truly minimal products:** When a product has no persistence, no auth, no networking, and is single-user local, the Orchestrator may approve generating only Product Brief, Test Specifications, and Dependency Manifest.

**The Product Brief and Test Specifications are never minimal.** Every product has users, flows, and testable behavior.

## Step 2: Generate Artifacts in Phases

Artifacts are generated in dependency order across phases. Each phase includes an incremental consistency check. The Orchestrator applies review lenses between phases.

Every artifact must follow the standard format defined in `docs/high-level-design.md` § "Artifact Format (V1)": markdown body with YAML frontmatter.

**For each artifact:** Read the corresponding template from `templates/`. The template defines the structure, required sections, frontmatter format, and generation guidance (in HTML comments). Generate content from project-state.yaml following the template's guidance.

### Phase A: Foundation

Generate the Product Brief first. Every other artifact depends on it. The Orchestrator applies review lenses after this phase.

Read `templates/product-brief.md`. Generate from `project-state.yaml` → `product_definition`, `classification`.

**Incremental check after Phase A:**
- Vision, personas, flows, scope, and platform are all present and internally consistent.
- Every persona has at least one core flow. Every core flow serves at least one persona.

### Phase B: Structure

Generate the Data Model and Non-Functional Requirements. Both depend primarily on the Product Brief. The Orchestrator applies review lenses after this phase.

Read `templates/data-model.md` and `templates/nonfunctional-requirements.md`.

**Incremental check after Phase B:**
- Entity coverage: every entity implied by Product Brief core flows appears in the Data Model.
- NFR targets are consistent with the product's risk profile and platform.

### Phase C: Integration

Generate the remaining artifacts: Security Model, Test Specifications, Operational Spec, Dependency Manifest, and any structurally-triggered artifacts. The Orchestrator applies all five review lenses after this phase.

Read the corresponding template for each artifact. For structurally-triggered artifacts, read from the characteristic's template directory.

**Risk-proportionate phasing:**

| Risk Level | Phases | Notes |
|------------|--------|-------|
| Low | 2 checkpoints: Product Brief + review, then all remaining + full review | Foundation review is never skipped |
| Medium | 3 phases as described above (A → B → C) | Standard flow |
| High | 3 phases with deeper review at each boundary | Consider additional domain-specific lenses |

### Phase D: Build Planning

Phase D translates abstract technical decisions into concrete build instructions. Invoked by the Orchestrator during Stage 4 (Build Planning).

Read `templates/build-plan.md`. Generate from `project-state.yaml` → `technical_decisions`, `classification.risk_profile`, plus all generated artifacts.

**What to produce:**

1. **Concrete scaffolding instructions.** Exact commands to initialize the project, install dependencies, and configure build tools. Use the product name from the Product Brief.

2. **Concrete project structure.** Directory layout and module boundaries derived from the data model and structural characteristics. Test infrastructure must match the test strategy: test directory structure accommodating all test levels specified in the strategy, per-level runner configuration, mock library setup when the strategy calls for mocking external services, and coverage tool configuration (always — coverage measurement is baseline regardless of risk level).

3. **Feature-first build chunks.** Each chunk delivers one user-visible flow end-to-end (data + logic + interface + tests). Chunk ordering depends on structural characteristics:
   - Chunk 01 is always scaffold: project init, dependencies, build config, test runner.
   - When `has_human_interface`: interface shell → first user flow end-to-end → remaining flows → polish. For screen-modality: navigation shell with routing. For terminal: display framework with input handling. For minimal: I/O initialization with feedback loop.
   - When `runs_unattended`: data entities → first pipeline stage → stages in flow order → output delivery → monitoring.
   - When `exposes_programmatic_interface`: API scaffold → core data layer → first API operation end-to-end → remaining operations → consumer documentation/SDK.
   - When `has_multiple_party_types`: shared data layer → first party's core flow → second party's core flow → cross-party interactions → trust boundary enforcement.
   - When `handles_sensitive_data`: this doesn't change chunk order — it deepens chunks by adding audit logging, access control verification, and lifecycle management to the chunks where sensitive entities are implemented.
   - When multiple characteristics are active, the ordering combines: start with whichever characteristic dominates the architecture (usually the primary structural characteristic), then interleave the others. The scaffold chunk accommodates all active characteristics.
   - Otherwise: core data entities → feature chunks by user value → polish.

4. **Acceptance criteria per chunk.** Map to specific test scenarios from `artifacts/test-specifications.md`.

5. **Early feedback milestone.** Which chunk first lets the user interact with a working product.

6. **Governance checkpoints.** At minimum: after early feedback milestone and after all chunks complete.

7. **Verification infrastructure** (when user opted in during discovery). Include verification tooling in the scaffold chunk specification: what tools to install, how to configure them, and how they integrate with the dev workflow. Specify the verification strategy appropriate to the product's structural characteristics (see `docs/high-level-design.md` § Agent Verification Architecture). Verification infrastructure is development-only — include removal/disabling instructions for deployment (HR10: No Dev Tooling in Production).

**NFR technique traceability:** For every NFR that constrains *how* something is built, the build plan must include a concrete implementation instruction in the relevant chunk.

**Platform-specific scaffolding constraints:** Account for platform build system requirements (test target imports, packaging format, system integration).

**The key test:** Could the Builder execute this plan without making any technology decisions?

**Update project-state.yaml:** Populate `build_plan.strategy`, `build_plan.chunks`, and `build_plan.governance_checkpoints`.

## Step 3: Validate Cross-Artifact Consistency (Phase C)

After generating all Phase C artifacts, run the full cross-artifact consistency check:

- **Entity coverage:** Every entity in the Data Model appears in the Test Specifications. Every entity referenced in the Product Brief appears in the Data Model.
- **Flow coverage:** Every core flow from the Product Brief has test scenarios.
- **Security coverage:** Every access pattern implied by the Product Brief is addressed in the Security Model.
- **Dependency coverage:** Every external service or library mentioned in any artifact appears in the Dependency Manifest.

**When `structural.runs_unattended` is active:**
- Stage coverage: every pipeline stage has failure handling and tests.
- Monitoring coverage: every health metric corresponds to an observable pipeline aspect.
- Configuration coverage: every changeable aspect appears in the Configuration Spec.
- Failure-to-test traceability: every failure mode has a test scenario.

**When `structural.has_human_interface` is active:**
- Interface structure coverage: every section of the interface structure (IA screens, interaction model elements, I/O mappings) has a corresponding specification. Every core flow maps to an interface sequence.
- Data display traceability: every interface data element traces to a Data Model entity.
- Accessibility coverage: every interactive element type has accessibility requirements.
- State coverage: every user-facing element has all relevant states specified (empty, loading, populated, error — or modality-appropriate equivalents).
- Onboarding-to-interface traceability: every onboarding-referenced element exists.

**When `structural.exposes_programmatic_interface` is active:**
- Operation coverage: every API operation traces to a core flow.
- Error coverage: every error code has a documented meaning and at least one test scenario.
- Versioning: backward compatibility strategy is documented.
- Consumer documentation: every operation has consumer-facing documentation.

**When `structural.has_multiple_party_types` is active:**
- Party flow coverage: every party has at least one complete flow from entry to core value.
- Trust boundary coverage: every cross-party interaction has trust boundary analysis.
- Data isolation: party-scoped data access is documented and tested.

**When `structural.handles_sensitive_data` is active:**
- Lifecycle coverage: every sensitive entity has collection, storage, access, and deletion defined.
- Audit coverage: every access pattern has an audit trail specified.
- Retention enforcement: every retention policy has an enforcement mechanism.

**Universal (all products):**
- **Test infrastructure alignment:** Every test level in the test strategy (unit, integration, E2E) has corresponding infrastructure in the build plan scaffold: directory structure, runner configuration, and any required libraries (mock framework, coverage tool). A test strategy that specifies three levels but a scaffold that only configures one runner is an inconsistency.

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

### Adding a new structural characteristic

The three-layer architecture (amplification rules + process constraints + template reference) guides all artifact generation. Adding a new characteristic means:

1. **Define amplification rules** in the "Structural Amplification Rules for Artifact Generation" section: what additional artifacts to generate and how universal artifacts deepen.
2. **Define process constraints** that must hold regardless of modality or domain. These are quality properties the Critic and Review Lenses verify.
3. **Optionally create templates** as reference material for well-tested modalities. Templates are an optimization for proven structures, not a requirement. A characteristic without templates uses amplification rules + process constraints to guide dynamic generation.
4. **Add consistency checks** to Step 3 for the new characteristic.
5. **Add chunk ordering** to Phase D for the new characteristic.
6. Register any template directory in `docs/doc-manifest.yaml`.

### Modifying existing characteristics

- Strengthen amplification rules when observations show the LLM missing important artifact concerns.
- Strengthen process constraints when observations show quality gaps the Critic should catch.
- Add templates when a modality has been validated across multiple products and the templates would prevent common mistakes.
- Templates should never be the only path — if templates were deleted, the amplification rules + process constraints should still produce adequate artifacts.

### When artifacts change

When a decision changes mid-build, update only affected artifacts rather than regenerating all. Consult the artifact dependency chain (frontmatter `depends_on` and `depended_on_by`) to identify the blast radius.
