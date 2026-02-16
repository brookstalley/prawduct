---
artifact: pipeline-architecture
version: 1
depends_on:
  - artifact: product-brief
depended_on_by:
  - artifact: scheduling-spec
  - artifact: monitoring-alerting-spec
  - artifact: failure-recovery-spec
  - artifact: configuration-spec
last_validated: 2026-02-16
---

# Pipeline Architecture

<!-- sourced: docs/high-level-design.md § Process Stages, 2026-02-16 -->
<!-- sourced: docs/self-improvement-architecture.md § Three-Phase Architecture, 2026-02-16 -->

Prawduct operates as two interlocking pipelines: the **stage pipeline** (user-facing product development) and the **learning loop** (framework self-improvement).

## Data Sources

### User Input (Stage Pipeline)

| Source | Type | Format | Reliability |
|--------|------|--------|-------------|
| User conversation | Event-driven (LLM session) | Natural language | Always available when session active |
| project-state.yaml | File read | YAML | Always available (file on disk) |
| Existing codebase | File system scan | Source code, configs | Available for onboarding/iteration |
| Framework skill files | File read | Markdown | Always available (framework repo) |

### Observation Data (Learning Loop)

| Source | Type | Format | Reliability |
|--------|------|--------|-------------|
| framework-observations/*.yaml | File read | YAML per schema | Always available |
| change_log entries | Embedded in project-state.yaml | YAML | Always available |
| eval-history/*.md | File read | Markdown with YAML frontmatter | Append-only |

## Processing Stages

### Stage Pipeline: Intake → Build Plan

```
[User Input] → [Intake/Classification] → [Discovery] → [Definition] → [Artifact Generation] → [Build Planning] → [Building] → [Iteration]
                      ↓                        ↓              ↓                  ↓                     ↓                ↓              ↓
               [Domain Analyzer]        [Domain Analyzer] [Review Lenses]  [Artifact Generator]  [Artifact Gen]   [Builder]    [Orchestrator]
                      ↓                        ↓              ↓                  ↓                     ↓                ↓              ↓
               [project-state.yaml]     [project-state]  [project-state]   [artifacts/]          [build-plan]    [source code]  [project-state]
```

**Stage 0 — Intake & Triage:** Domain Analyzer classifies domain and structural characteristics. Orchestrator begins expertise calibration.

**Stage 1 — Discovery:** Dynamic questioning based on classification. Discovery depth calibrated to risk and user patience. Output: populated project-state.yaml.

**Stage 2 — Definition:** Crystallize discovery into firm decisions. Review Lenses (Product, Design, Architecture, Skeptic) evaluate. Output: finalized product decisions.

**Stage 3 — Artifact Generation:** Generate structurally-appropriate artifact set in dependency order (Phase A: foundation → Phase B: structure → Phase C: integration → Phase D: build plan). Review Lenses evaluate each phase.

**Stage 4 — Build Planning:** Produce execution plan with dependency graph, parallelization opportunities, early-feedback milestones, governance checkpoints.

**Stage 5 — Building:** Repeating cycle: Builder executes chunk → Critic evaluates → issues resolved → next chunk.

**Stage 6 — Iteration:** User feedback classified (cosmetic/functional/directional). Changes propagated through artifacts. DCP for structural changes.

### Learning Loop: Capture → Detect → Incorporate

```
[Stage Transitions] → [Observation Capture] → [Pattern Detection] → [Pattern Surfacing] → [Human Decision] → [Incorporation]
[DCP Retrospectives] ↗                              ↓                        ↓                    ↓                    ↓
[Evaluations] ↗                              [obs_utils.py]        [session-health-check]   [act or defer]    [Stage 6 + Critic]
```

**C8a — Observation Capture (BUILT):** Automatic at stage transitions (change_log entry blocking). Observation files for substantive findings.

**C8b — Pattern Detection (PARTIALLY BUILT):** `session-health-check.sh` parses observations, applies tiered thresholds (meta: 2+, build: 3+, product: 4+), surfaces actionable patterns.

**C8c-e — Incorporation (PARTIALLY BUILT):** Session resumption presents patterns → user approves or defers → approved changes follow normal governance.

## Outputs

| Output | Destination | Format | Success Criteria |
|--------|-------------|--------|------------------|
| Populated project-state.yaml | .prawduct/ | YAML | All required sections populated, decisions documented |
| Generated artifacts | .prawduct/artifacts/ | Markdown + YAML frontmatter | Template-compliant, cross-referenced, internally consistent |
| Build plan | .prawduct/artifacts/build-plan.md | Markdown | Dependency-ordered chunks with governance checkpoints |
| Source code | Project root | Per technology | Passes tests, matches specs |
| Observations | .prawduct/framework-observations/ | YAML per schema | Generalized, schema-compliant |
| Evaluation results | eval-history/ | Markdown + YAML frontmatter | Complete scoring, observations extracted |

## Pipeline Boundaries

- **Does NOT generate code directly** — that is the Builder skill's job, operating under the build plan
- **Does NOT make product decisions** — it facilitates, challenges, and documents. The user owns product decisions.
- **Does NOT prescribe technology choices** — it learns questions and problems, not solutions
- **Does NOT operate across sessions** — each session reads state from disk and operates independently
