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

**When `structural.has_human_interface` (modality: screen) is active:**

Read templates from `templates/human-interface/`. Generate: Information Architecture, Screen Specifications, Design Direction, Accessibility Spec, Localization Requirements, Onboarding Spec.

Notes for `has_human_interface`: "Core Flows" become screen sequences. Data Model captures user-facing entities. NFRs emphasize user-facing performance.

**When templates exist for a structural characteristic:** Read and follow the templates. They define structure, required sections, and generation guidance. Generate content from project-state.yaml following the template.

**When templates don't exist for a structural characteristic** (e.g., `exposes_programmatic_interface`, `has_multiple_party_types`): Dynamically generate appropriate artifacts using the product's domain characteristics and your domain knowledge. The skill's structural routing pattern still applies — but instead of reading from pre-built templates, generate artifacts that match the characteristic's needs. Either path produces valid artifacts.

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

2. **Concrete project structure.** Directory layout and module boundaries derived from the data model and product shape.

3. **Feature-first build chunks.** Each chunk delivers one user-visible flow end-to-end (data + logic + UI + tests). Chunk ordering depends on structural characteristics:
   - Chunk 01 is always scaffold: project init, dependencies, build config, test runner.
   - When `has_human_interface`: UI shell with navigation → first user flow → remaining flows → polish.
   - When `runs_unattended`: data entities → first pipeline stage → stages in flow order → output delivery → monitoring.
   - Otherwise: core data entities → feature chunks by user value → polish.

4. **Acceptance criteria per chunk.** Map to specific test scenarios from `artifacts/test-specifications.md`.

5. **Early feedback milestone.** Which chunk first lets the user interact with a working product.

6. **Governance checkpoints.** At minimum: after early feedback milestone and after all chunks complete.

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
- Screen coverage: every IA screen has a Screen Spec section. Every core flow maps to a screen sequence.
- Data display traceability: every screen data element traces to a Data Model entity.
- Accessibility coverage: every interactive element type has accessibility requirements.
- State coverage: every screen state (empty, loading, populated, error) has a specification.
- Onboarding-to-screen traceability: every onboarding-referenced screen exists.

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

To add a new structural characteristic's artifacts:
1. Create a templates directory under `templates/` named for the characteristic (e.g., `templates/api-surface/`).
2. Add one template per artifact with YAML frontmatter, section structure, and generation guidance in HTML comments.
3. The skill's existing structural routing will pick up templates automatically — no skill modifications needed for template-based characteristics.
4. For characteristics without templates, the dynamic generation fallback handles artifact creation.
5. Register the template directory in `docs/doc-manifest.yaml`.
