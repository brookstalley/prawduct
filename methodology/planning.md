# Planning: Designing the Solution

Planning bridges discovery and building. You've understood the problem; now design the solution in enough detail to build it well, but not so much detail that the planning itself becomes the project.

## Artifact Generation

Artifacts are specification files that guide building. They ensure you think through the design before writing code — catching issues at the spec level is cheaper than catching them in implementation. Each artifact is a file written to `.prawduct/artifacts/` (see "Where Artifacts Live" below).

**Universal artifacts** (every product, scaled to risk):
- **Product Brief** — Vision, personas, flows, scope, success criteria. The foundation everything else references.
- **Data Model** — Entities, relationships, constraints, state machines. The structural backbone.
- **Security Model** — Authentication, authorization, data privacy, abuse prevention.
- **Test Specifications** — Concrete test scenarios at unit, integration, and e2e levels, with risk-proportionate depth.
- **Non-Functional Requirements** — Performance targets, scalability, uptime expectations, cost constraints.
- **Operational Specification** — Deployment, monitoring, alerting, failure recovery.
- **Dependency Manifest** — Every external library with justification and alternatives considered.

**Structurally-triggered artifacts** (based on characteristics detected in discovery):
- *Human interface*: Interaction design, information architecture, accessibility specification, onboarding flow
- *Runs unattended*: Pipeline architecture, scheduling, monitoring and alerting, failure recovery, configuration management
- *Programmatic interface*: API contract (operations, request/response formats, error codes, authentication, rate limits)
- *Multiple party types*: Per-party experience specifications, trust boundary analysis, data isolation rules
- *Sensitive data*: Deepens existing artifacts (data lifecycle, security model, audit trails) rather than creating new ones
- *Multi-process or distributed*: System architecture — process topology, communication channels (patterns, endpoints, protocols), concurrency model, persistence boundaries (what's durable vs. ephemeral, what lives where)

### Artifact Dependencies

Artifacts depend on each other. The Product Brief is the foundation — everything references it. The Data Model and NFRs depend on the brief. Security, testing, and operational specs depend on the data model. Generate them in dependency order and validate at boundaries.

**Phase A**: Product Brief (everything depends on this)
**Phase B**: Data Model + Non-Functional Requirements
**Phase C**: Everything else (security, testing, operations, structural artifacts)
**Phase D**: Build Plan (depends on all artifacts)

Between phases, review what you've produced. Apply the review perspectives (Product, Design, Architecture, Skeptic, Testing) to catch issues before they propagate downstream. The cost of fixing a spec error scales with how many downstream artifacts have already incorporated it.

### Where Artifacts Live

Write all generated artifacts to `.prawduct/artifacts/`. This is the canonical location — the Critic reads from it and the build cycle references it. The stop hook triggers the Critic review gate when it detects a build plan (either `artifacts/build-plan.md` or a `build_plan` section with chunks in `project-state.yaml`).

Name files by artifact type: `product-brief.md`, `data-model.md`, `build-plan.md`, etc. For onboarded projects that already have specifications elsewhere, those can stay — but Prawduct-generated artifacts go in `.prawduct/artifacts/`. The build plan can live in `project-state.yaml` alongside status tracking if that's more natural, but keeping chunk specifications in a separate `build-plan.md` artifact makes the Critic's spec-compliance check cleaner.

### Proportionality

Artifact depth scales to risk. A low-risk personal utility might have a 1-page product brief and a minimal data model. A high-risk financial platform needs deep specs with edge case coverage. The same artifacts exist at different depths — the framework doesn't skip artifacts for low-risk products, it scales them.

If an artifact is genuinely not applicable (e.g., API contract for a product with no programmatic interface), note that briefly and move on. Don't generate content just to fill a template.

## Build Planning

The build plan decomposes artifacts into buildable chunks — coherent units of work with clear deliverables and acceptance criteria.

**Good chunks are:**
- **Vertically sliced** — each chunk delivers working, testable functionality from data model through UI (if applicable)
- **Dependency-ordered** — later chunks build on earlier ones; the first chunk validates the architecture
- **Independently testable** — each chunk can be verified without waiting for later chunks
- **Small enough to review** — a chunk should be reviewable in one Critic pass

**The first chunk is special.** It should be a thin vertical slice through the entire architecture — proving that the layers connect, the data flows, and the build approach works. Don't build one layer completely before touching the next. Validate the path before widening it.

**Verification strategy.** The build plan should include how the builder will confirm each chunk's output works beyond tests — exercising the product as its users or consumers would experience it. What this looks like depends on structural characteristics and available tools. Don't over-specify — describe the approach, not a checklist. For many products, the simplest effective method is best. Complex products (e.g., those with human interfaces or multi-party interactions) may need dedicated tooling planned into the scaffold.

**Governance checkpoints** are points during the build where you pause to review the whole — not just the current chunk but the trajectory. Place them at natural boundaries: after the first chunk (architecture validation), at the midpoint, and before completion. The number scales with risk (1-2 for low-risk, 3-5 for high-risk).

## Common Traps

**Over-specification**: Writing specs so detailed they're harder to maintain than the code. Specs should be precise enough to build from but not so rigid they can't adapt to implementation discoveries.

**Under-specification**: Leaving ambiguities that the builder will have to resolve with guesses. Every ambiguity is a risk of building the wrong thing. Be specific about behavior, flexible about implementation.

**Monolithic chunks**: Chunks so large they can't be reviewed meaningfully. If a chunk touches every layer and takes days, it's too big. Split it.

**Dependency ignorance**: Planning chunks that can't be built in order because they depend on things that don't exist yet. Map dependencies explicitly.

**Line-number scoping**: Identifying change sites by line number rather than by structural pattern. "Change lines 42, 87, and 134" is brittle — those lines shift as the file evolves. "All methods that swallow exceptions and return failure replies" is robust — it identifies the pattern, so you find all instances even if new ones were added since the plan was written. Scope changes by the pattern they share, not by their current addresses.

**Template worship**: Generating every section of every template regardless of relevance. If a section doesn't apply, say so briefly. Don't fill space with "not applicable" paragraphs.
