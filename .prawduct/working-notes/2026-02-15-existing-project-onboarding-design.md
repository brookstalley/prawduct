# Existing Project Onboarding Design

Created: 2026-02-15
Phase: 4 (Design only — no implementation in this phase)
Status: Draft

## Problem

Prawduct currently only handles two entry points:
1. **New product** — user describes an idea, framework guides from scratch through Stages 0-6
2. **Returning prawduct project** — project-state.yaml exists, Session Resumption continues from where we left off

Missing entry points:
- **Existing codebase without prawduct** — a real project with source code, dependencies, maybe tests, but no prawduct artifacts. User wants to bring it into the framework for iteration.
- **Old prawduct project** — project-state.yaml exists but from an older version of prawduct with different schemas, artifacts, or approaches.

## Solution: Onboarding Mode

A new Orchestrator mode that reverse-engineers an existing codebase into prawduct artifacts, then enters Stage 6 (Iteration) since the product is already built.

## Detection

The Orchestrator's project directory setup (Step 1) already has the right hooks. Currently:

```
Condition 3: No project-state.yaml + CWD contains project signals → Use CWD
```

This currently falls through to Stage 0 (Intake), which is wrong for an existing codebase. The new behavior:

```
Condition 3: No project-state.yaml + CWD contains project signals → Enter Onboarding Mode
```

For old prawduct detection, a new condition:

```
Condition 1b (modified): YES + project-state.yaml exists → Check schema version.
  - Current version → Session Resumption (existing flow)
  - Old/unrecognized version → Enter Migration Mode
```

## Onboarding Mode: Fresh Codebase

### Phase 1: Codebase Analysis

The Orchestrator analyzes the existing codebase systematically:

**1a. Tech stack detection**
Read package.json / Cargo.toml / go.mod / requirements.txt / etc. to identify:
- Primary language(s)
- Framework(s) (React, Express, Django, etc.)
- Key dependencies
- Build tooling
- Test framework(s)

**1b. Architecture inference**
Scan directory structure, entry points, and imports to identify:
- Project structure pattern (monorepo, MVC, component-based, etc.)
- Data layer (database type, ORM, data files)
- API surface (REST endpoints, GraphQL schema, CLI commands)
- Auth approach (if any)

**1c. Product understanding**
Read documentation and source to understand what the product does:
- README.md, docs/, wiki links
- Package description fields
- Route definitions / page components → infer core flows
- User-facing strings → infer personas and features
- Error messages → infer edge cases handled

**1d. Structural characteristics**
Infer from codebase signals:

| Characteristic | Signals |
|---------------|---------|
| has_human_interface | React/Vue/Svelte components, HTML templates, CSS files, screen-related routes |
| runs_unattended | Cron configs, worker processes, queue consumers, scheduled tasks |
| exposes_programmatic_interface | API route files, OpenAPI specs, GraphQL schemas, SDK exports |
| has_multiple_party_types | Multiple auth roles, admin vs user routes, distinct user models |
| handles_sensitive_data | Auth/password handling, encryption libs, PII fields, compliance configs |

**1e. Test coverage analysis**
Scan test files to understand:
- Test count and framework
- What's tested (unit, integration, e2e)
- Coverage gaps (directories with no test files)

**1f. Risk assessment**
Infer from characteristics, user count signals (analytics configs, deployment configs), data sensitivity, and operational complexity.

### Phase 2: User Confirmation

Present the analysis as a readable summary:

> "I've analyzed your codebase. Here's what I see: **[product name from package.json]** — a **[framework]** app that **[inferred purpose]**. It has **[characteristics]**. Tech stack: **[languages/frameworks]**. I found **[N]** test files covering **[areas]**. The architecture looks like **[pattern]**.
>
> A few things I'm less sure about: **[uncertainties — e.g., 'I see auth but not sure if there are distinct user types']**.
>
> Does this match your understanding? Anything I'm missing or getting wrong?"

This is a **genuine blocking question** — the agent's analysis may be incomplete or wrong. Wait for user confirmation before generating artifacts.

### Phase 3: Artifact Generation

Generate prawduct artifacts from the analysis:

1. **project-state.yaml** — populated with classification, product definition (inferred), technical decisions (from actual codebase), and current_stage set to "iteration"

2. **Product Brief** — synthesized from README, package description, and code analysis. Mark inferred sections explicitly: "Inferred from codebase analysis — verify with product owner."

3. **Data Model** — extracted from database schemas, ORM models, TypeScript interfaces, or API response types

4. **Test Specifications** — derived from existing tests, noting gaps where no tests exist

5. **Security Model** — inferred from auth patterns, middleware, and sensitive data handling

6. **Dependency Manifest** — populated from package.json/Cargo.toml/etc. with actual dependencies and their purposes

7. **Structural-characteristic artifacts** — only for characteristics that are present (e.g., Screen Specs for has_human_interface products, derived from existing components/routes)

8. **Build Plan** — retroactive: chunks map to existing modules/features, all marked "complete"

### Phase 4: Enter Iteration

Set current_stage to "iteration" and orient the user:

> "I've onboarded **[product]** into prawduct. The artifacts are in `artifacts/` — they reflect what I found in the codebase. Anything marked 'inferred' should be verified. You're in iteration mode — tell me what you want to change or build next."

## Migration Mode: Old Prawduct Projects

### Version Detection

Add a `schema_version` field to the project-state.yaml template. Current version: `2`.

During Session Resumption, before loading state:

1. Read `project-state.yaml`
2. Check for `schema_version` field
3. If missing or old:
   - Detect version from structural signals (field names, section presence)
   - Enter Migration Mode

### Version Signal Detection

Since we didn't version old schemas, detect by structural signals:

| Version | Signals |
|---------|---------|
| Pre-concern (v0) | Has `product_shape` or `shape` field instead of `structural` |
| Concern-based (v0.5) | Has `concerns` with items like `human_interface`, `unattended_operation` |
| Characteristic-based (v1) | Has `structural` with `has_human_interface`, etc. but no `schema_version` |
| Current (v2) | Has `schema_version: 2` |

### Migration Process

1. **Read old project-state.yaml** completely
2. **Map old fields to current schema:**
   - `product_shape: "UI Application"` → `structural.has_human_interface: { modality: screen }`
   - `concerns.human_interface` → `structural.has_human_interface`
   - `concerns.api_surface` → `structural.exposes_programmatic_interface`
   - Old `artifact_manifest` entries → map to current artifact names
   - Old `build_plan` format → map to current chunk format
3. **Preserve user content:** All product-specific content (vision, personas, flows, decisions) carries forward. Only the structural framing changes.
4. **Present migration summary:**

   > "I found a prawduct project from an older version. Here's what's changing:
   > - Classification updated from [old format] to structural characteristics
   > - [N] artifacts mapped to current naming
   > - Build state preserved ([N] chunks complete)
   > Your product content is unchanged — just the framework structure around it."

5. **Write migrated project-state.yaml** with `schema_version: 2`
6. **Enter Session Resumption** with the migrated state

### Old Artifact Detection

Also scan for old artifact formats:
- Artifacts in non-standard locations (root instead of `artifacts/`)
- Old naming conventions (if any changed)
- Missing frontmatter (older versions may not have required it)

Generate missing artifacts where possible from existing content.

## Framework Changes Required

### Orchestrator (`skills/orchestrator/SKILL.md`)

1. **Step 1 condition 3:** Change from "Use CWD" + Stage 0 to "Enter Onboarding Mode"
2. **New section: Onboarding Mode** with the Phase 1-4 process above
3. **Session Resumption:** Add version check before loading state

### Project State Template (`templates/project-state.yaml`)

1. Add `schema_version: 2` field at the top

### Critic (`skills/critic/SKILL.md`)

1. When reviewing onboarded projects: verify artifacts actually match codebase (not fabricated from inference)
2. Inferred content should be marked as such (HR3: No Documentation Fiction)

### Test Scenarios

1. New scenario: "Onboard an existing Express+React project" — tests the full onboarding flow
2. Existing scenarios: verify they still work (regression)

## Open Questions

1. **Monorepo handling:** If the CWD is a monorepo with multiple packages, does each package become a separate prawduct project? Or is the monorepo the project?

2. **Partial prawduct projects:** What if someone started prawduct, generated some artifacts, but didn't finish? Not old-version, just incomplete. The current Session Resumption handles this (resumes from current_stage), but what if the artifacts are inconsistent with the code?

3. **Codebase analysis depth:** How deep should the agent go? Reading every source file is impractical for large codebases. Need heuristics: read entry points, key config files, README, a sample of components, but not every file.

4. **Artifact accuracy:** Inferred artifacts will have gaps and errors. Should the framework run Review Lenses on inferred artifacts before presenting to the user? (Probably yes — catches obvious issues.)

## Implementation Sequence

1. Add `schema_version` to project-state.yaml template (smallest, lowest risk)
2. Add version detection to Session Resumption
3. Implement migration for known old schemas
4. Implement Onboarding Mode (largest piece)
5. Add test scenario for onboarding
6. Critic updates for inferred artifact handling
