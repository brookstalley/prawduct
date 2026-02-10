# Artifact Generator

The Artifact Generator produces the build plan artifacts for a user's product. It selects the appropriate artifact set based on product shape, generates each artifact from decisions in Project State, enforces cross-artifact consistency, and declares dependencies between artifacts. It is invoked by the Orchestrator during Stage 3 (Artifact Generation).

## When You Are Activated

The Orchestrator activates this skill when `current_stage` is "artifact-generation" and the product definition has been confirmed by the user.

When activated:

1. Read `project-state.yaml` — it must have classification, product definition, and scope decisions populated.
2. Determine which artifacts to generate based on the product's shape.
3. Generate each artifact, writing files to the `artifacts/` directory.
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

**Phase 1 scope:** Generate universal artifacts only. Shape-specific artifacts (UI, API, automation, multi-party) are added in Phase 2 as each shape is implemented.

## Step 2: Generate Each Artifact

Every artifact must follow the standard format defined in `docs/high-level-design.md` § "Artifact Format (V1)": markdown body with YAML frontmatter.

### Artifact: Product Brief

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

### Artifact: Data Model

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

### Artifact: Security Model

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

### Artifact: Test Specifications

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

### Artifact: Non-Functional Requirements

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

### Artifact: Operational Specification

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

### Artifact: Dependency Manifest

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

## Step 3: Validate Cross-Artifact Consistency

After generating all artifacts, check:

- **Entity coverage:** Every entity in the Data Model appears in the Test Specifications. Every entity referenced in the Product Brief appears in the Data Model.
- **Flow coverage:** Every core flow from the Product Brief has test scenarios in the Test Specifications.
- **Security coverage:** Every access pattern implied by the Product Brief is addressed in the Security Model.
- **Dependency coverage:** Every external service or library mentioned in any artifact appears in the Dependency Manifest.

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
- [ ] Automation/Pipeline artifacts: pipeline architecture, scheduling spec, monitoring/alerting spec, failure recovery spec, configuration spec (Phase 2)
- [ ] Multi-Party artifacts: per-party experience specs, party interaction model, migration/adoption plan (Phase 2)
- [ ] Modular artifact updates: when a decision changes, update only affected artifacts rather than regenerating all (Phase 2)
- [ ] Build ordering: produce an execution plan with dependency graph and parallelization opportunities (Phase 2)
