---
artifact: operational-spec
version: 1
depends_on:
  - artifact: nonfunctional-requirements
  - artifact: security-model
depended_on_by:
  - artifact: dependency-manifest
last_validated: 2026-02-16
---

# Operational Specification

<!-- MINIMAL: No infrastructure — framework runs in user's LLM session. -->
<!-- sourced: docs/high-level-design.md § Persistence Model, 2026-02-16 -->

## Applicability

Prawduct has no deployment, no servers, no databases, no infrastructure. It is a collection of text files (skills, templates, tools) consumed by the LLM at runtime. "Operations" means version control and state recovery.

## Deployment

Framework is distributed as a git repository. Users clone or reference it. Updates are git pulls. There is no build step, no compilation, no package management.

## Versioning

- **Git-based:** All framework files are version-controlled. Git SHA provides exact version identification.
- **Framework version tracking:** `prawduct-init.py` writes the current framework version to `.prawduct/framework-version` in product repos. Session health check detects version changes.
- **Schema versioning:** `project-state.yaml` includes a `schema_version` field. Migration tiers handle version transitions (v0→v2 heavy, v0.5→v2 moderate, v1→v2 lightweight).

## State Recovery

- **After compaction:** Hooks survive context compaction. The SessionStart hook (`compact-governance-reinject.sh`) re-injects governance instructions. Skill files are re-read from disk when referenced.
- **After session restart:** `project-state.yaml` persists all project state. Session Resumption reads it and rebuilds context. `.session-governance.json` is recreated from project state if missing.
- **Framework-path staleness:** If the framework directory moves, `.prawduct/framework-path` becomes stale. Governance hooks are resilient — they derive `FRAMEWORK_ROOT` from their own script location, so they continue to function. The `framework-path` file primarily affects product-repo bootstrap and divergence detection. Corrected by re-running `prawduct-init.sh`.
