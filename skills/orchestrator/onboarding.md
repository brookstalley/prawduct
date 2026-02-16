# Onboarding Mode — Existing Project Analysis

Onboarding Mode reverse-engineers an existing codebase into prawduct artifacts so the user can iterate on their product with full framework governance. This mode is entered when the Orchestrator detects project signals (source code, package manifests) in the current directory but no `project-state.yaml` or `.prawduct/` directory.

## When This File Is Read

The Orchestrator routes here from SKILL.md Step 1c when `prawduct-init.sh` reports `next_action: "onboarding"` and the user has an existing codebase (not a new product idea). The Orchestrator has already confirmed this is an existing codebase needing onboarding, and `prawduct-init.sh` has created the `.prawduct/` directory and bootstrap files.

---

## Phase 1: Codebase Analysis

Analyze the existing codebase systematically. Read selectively — entry points, key configs, README, a sample of each major directory — not every file. For large codebases (100+ files), focus on structure and representative samples.

### 1a. Tech Stack Detection

Read package manifests (`package.json`, `Cargo.toml`, `go.mod`, `requirements.txt`, `pyproject.toml`, `Gemfile`, `build.gradle`, `pom.xml`, `*.xcodeproj`, `Package.swift`, `pubspec.yaml`, etc.) to identify:

- Primary language(s)
- Framework(s) (React, Express, Django, SwiftUI, Flutter, etc.)
- Key dependencies and their purposes
- Build tooling (webpack, vite, cargo, gradle, xcodebuild, etc.)
- Test framework(s) (Jest, pytest, XCTest, etc.)

### 1b. Architecture Inference

Scan directory structure, entry points, and imports to identify:

- Project structure pattern (monorepo, MVC, component-based, feature-based, etc.)
- Data layer (database type, ORM, data files, Core Data, etc.)
- API surface (REST endpoints, GraphQL schema, CLI commands)
- Auth approach (if any)
- Key architectural patterns (dependency injection, state management, etc.)

### 1c. Product Understanding

Read documentation and source to understand what the product does:

- README.md, docs/, documentation directories
- Package description fields
- Route definitions / page components / view controllers → infer core flows
- User-facing strings → infer features and personas
- Error messages → infer edge cases handled

### 1d. Structural Characteristics

Infer from codebase signals:

| Characteristic | Signals |
|---------------|---------|
| `has_human_interface` | React/Vue/Svelte/SwiftUI components, HTML templates, CSS files, storyboards, XIBs, screen-related routes. Infer modality (screen/terminal/voice) and platform (mobile/web/desktop/cross-platform) from framework. |
| `runs_unattended` | Cron configs, worker processes, queue consumers, scheduled tasks, background job definitions |
| `exposes_programmatic_interface` | API route files, OpenAPI specs, GraphQL schemas, SDK exports, protobuf definitions |
| `has_multiple_party_types` | Multiple auth roles, admin vs user routes, distinct user models, role-based access |
| `handles_sensitive_data` | Auth/password handling, encryption libraries, PII fields in models, compliance configs, health/financial data models |

### 1e. Test Coverage Analysis

Scan test files to understand:

- Test count and framework
- What's tested (unit, integration, e2e, UI tests, snapshot tests)
- Coverage gaps (directories with no corresponding test files)
- Test naming patterns and quality signals

### 1f. Risk Assessment

Infer from:

- Structural characteristics (more characteristics → higher complexity)
- Deployment configs (production vs development signals)
- Data handling (PII, financial, health data)
- User count signals (analytics configs, scaling configs)
- Regulatory signals (compliance configs, data residency)

### 1g. Documentation Mapping

**When:** `prawduct-init.sh` reported `existing_docs` with content (especially `architecture`, `api_specs`, or large `readme`).

Use the classified doc inventory from `prawduct-init.sh` output to prioritize reading:

1. **Architecture and design docs** (`existing_docs.architecture`) — highest value. Read fully. These provide the clearest picture of intended system structure, which may differ from what the code shows today.
2. **API specifications** (`existing_docs.api_specs`) — read fully. OpenAPI/GraphQL/protobuf files are precise and map directly to the `exposes_programmatic_interface` characteristic.
3. **README** (`existing_docs.readme`) — read fully. Primary source for product purpose, setup, and intended audience.
4. **docs/ directory** (`existing_docs.docs_dir`) — read selectively. Skip contribution guides, setup docs, and meeting notes. Prioritize anything describing features, architecture, or user flows.
5. **Existing CLAUDE.md** — if `existing_docs.claude_md_content_bytes > 0`, read it for project-specific instructions, conventions, and context that should be preserved (not overwritten by the prawduct bootstrap).

**Record per doc:**
- Which prawduct artifact it maps to (e.g., architecture doc → product brief + data model)
- What product knowledge it provides (e.g., "describes the auth flow and user roles")
- Apparent freshness (recent git modifications vs stale)

**Principle:** Existing docs are more authoritative than code inference for "what does this product do" and "why was it built this way." Code is more authoritative for "what does it actually do right now." When they conflict, note the discrepancy — code wins for current state, docs win for intent.

---

## Phase 2: User Confirmation

Present the analysis as a readable summary. This is a **genuine blocking question** — wait for the user to confirm or correct before generating artifacts.

**Format:**

> "I've analyzed your codebase. Here's what I see:
>
> **[product name]** — a **[framework/language]** app that **[inferred purpose]**.
>
> **Structural characteristics:** [list detected characteristics with key properties]
> **Tech stack:** [languages, frameworks, key dependencies]
> **Tests:** [count] test files covering [areas]
> **Architecture:** [inferred pattern]
> **Risk level:** [low/medium/high with brief rationale]
>
> **Things I'm less sure about:** [uncertainties — e.g., 'I see auth but not sure if there are distinct user types', 'the docs mention an API but I didn't find route definitions']
>
> Does this match your understanding? Anything I'm missing or getting wrong?"

**Key principles:**

- Mark all inferred content explicitly (HR3: No Documentation Fiction)
- State uncertainties clearly (HR5: No Confidence Without Basis)
- Don't fabricate product understanding from sparse signals — say what you don't know
- This is the user's opportunity to correct misunderstandings before they propagate into artifacts

**After user confirms** (or provides corrections), proceed to Phase 3. If the user corrects significant aspects, update your analysis before generating artifacts.

---

## Phase 3: Artifact Generation

Bootstrap infrastructure (`.prawduct/`, `framework-path`, `CLAUDE.md`, `.claude/settings.json`) has been created by `prawduct-init.sh` during Orchestrator activation. Generate prawduct artifacts from the confirmed analysis.

### 3a. Project State

Create `.prawduct/project-state.yaml` from the framework template (`templates/project-state.yaml`). Populate:

- `schema_version: 2`
- `classification` — domain, structural characteristics, domain_characteristics, risk_profile (all from Phase 1 analysis, confirmed in Phase 2)
- `product_definition` — vision (synthesized from README/docs), personas (inferred from user types), core_flows (from routes/views/handlers), scope (current features in v1, empty later/never)
- `product_identity` — name from package manifest or README
- `platform` — from tech stack detection
- `nonfunctional` — inferred from existing configs (performance budgets, uptime requirements, etc.)
- `technical_decisions` — actual decisions already made in the codebase (language, framework, data layer, deployment), each with rationale "Existing codebase uses [X]" and alternatives_considered: ["Inherited — project already built with this choice"]
- `design_decisions` — from existing UI patterns, accessibility configs, etc.
- `user_expertise` — infer from code quality, documentation quality, test coverage
- `current_stage: iteration` — the product is already built
- `change_log` — single entry: "Onboarded existing [product] codebase into prawduct"

### 3b. Artifacts

Generate **complete standalone artifacts** in `.prawduct/artifacts/`. Each artifact must stand alone — incorporate content from existing docs rather than referencing them.

**Source tagging:** When artifact content is derived from an existing doc, tag the section:
```markdown
<!-- sourced: docs/architecture.md, 2026-02-16 -->
```
This enables divergence detection during Session Resumption (compare git timestamps of source doc vs artifact). No active sync is required — divergence is detected mechanically.

**When existing docs conflict with code:** Note the discrepancy in the artifact. Code wins for describing current state; docs win for describing intent. Example:
```markdown
> **Note:** `docs/architecture.md` describes a microservices architecture, but the codebase
> is currently a monolith. This may indicate planned migration or stale documentation.
```

For each artifact, mark inferred sections: "Inferred from codebase analysis — verify with product owner."

**Always generate (universal artifacts):**

1. **Product Brief** — synthesized from README + code analysis. Core flows from routes/handlers. Success criteria inferred from test assertions.
2. **Data Model** — extracted from database schemas, ORM models, type definitions, API response types. Include entity relationships.
3. **Test Specifications** — derived from existing tests (what's tested) plus gap analysis (what's not). Reference actual test files.
4. **Security Model** — inferred from auth patterns, middleware, sensitive data handling. Mark any gaps found.
5. **Non-functional Requirements** — from configs, performance budgets, existing SLAs if documented.
6. **Operational Spec** — from deployment configs, CI/CD, monitoring setup.
7. **Dependency Manifest** — populated directly from package manifests with actual dependencies and their purposes.

**Generate only for detected characteristics:**

- `has_human_interface` → Information Architecture (from routes/navigation), Screen Specs (from view components), Design Direction (from styles/theme), Accessibility Spec (from accessibility configs), Onboarding Spec (from onboarding flows if present)
- `runs_unattended` → Pipeline Architecture, Scheduling Spec, Monitoring/Alerting Spec, Failure Recovery Spec, Configuration Spec
- Other characteristics → generate applicable artifacts per the Artifact Generator's amplification rules

### 3c. Build Plan (Retroactive)

Create `.prawduct/artifacts/build-plan.md` with chunks that map to existing modules/features. Mark all chunks as "complete" since the code exists. This provides a structural map of what was built and how it fits together.

### 3d. Artifact Manifest

Populate `artifact_manifest.artifacts` in project-state.yaml with all generated artifact entries including file paths, dependency declarations, and version 1.

---

## Phase 4: Enter Iteration

1. Set `current_stage` to `iteration` in project-state.yaml
2. Present a summary to the user:

> "I've onboarded **[product]** into prawduct. Here's what was generated:
>
> - `project-state.yaml` — classification, product definition, technical decisions
> - [N] artifacts in `.prawduct/artifacts/` — [list artifact names]
>
> Anything marked 'Inferred' should be verified — I derived it from code analysis, not product requirements.
>
> You're now in iteration mode. Tell me what you want to change or build next, and the framework will govern the changes."

3. The user can now iterate on their product with full prawduct governance (Critic reviews, artifact updates, test tracking).

---

## Onboarding State Tracking

Onboarding can be interrupted (context compaction, session end, user pause). Track progress in `.prawduct/.onboarding-state.json`:

```json
{
  "started": "2026-02-16T10:00:00Z",
  "current_phase": 2,
  "phase_1_complete": true,
  "phase_2_complete": false,
  "analysis_cache": {
    "tech_stack": { "languages": ["typescript"], "frameworks": ["react", "express"] },
    "structural_characteristics": { "has_human_interface": true, "runs_unattended": false },
    "doc_mapping": [
      { "doc": "docs/architecture.md", "maps_to": "product-brief", "freshness": "recent" }
    ]
  }
}
```

**Write** this file at each phase transition (after Phase 1 completes, after Phase 2 completes, etc.).

**Read on re-entry:** When the Orchestrator routes here and `prawduct-init.sh` reports `onboarding_in_progress` is not null, skip completed phases:
- If `phase_1_complete` is true, skip Phase 1 and use `analysis_cache` for Phase 2
- If `phase_2_complete` is true, skip Phase 2 and proceed to Phase 3

**Delete** the file when Phase 4 completes (onboarding finished).

---

## Edge Cases

**Monorepo:** Treat the CWD as the project. If the user says "I want to onboard the `api/` package specifically," respect that and scope analysis to the subdirectory.

**Sparse codebase:** If analysis can't determine product purpose, structural characteristics, or tech stack with reasonable confidence, say so explicitly and ask the user to describe their product. Fall back to a hybrid approach: use what you can detect and ask about what you can't.

**Large codebase (500+ files):** Don't read every file. Sample strategy:
- All config/manifest files
- README and docs/
- Entry points (main files, index files, app files)
- 2-3 representative files from each major directory
- All test configuration files
- Schema/model definitions

**Projects with existing docs:** If the project has thorough documentation (README, architecture docs, API docs), lean heavily on those for product understanding rather than code analysis. Existing docs are more reliable than code inference for "what does this product do."
