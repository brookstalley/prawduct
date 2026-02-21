---
artifact: cross-cutting-concerns-registry
version: 2
depends_on:
  - artifact: product-brief
  - artifact: test-specifications
depended_on_by: []
last_validated: 2026-02-21
---

# Cross-Cutting Concerns Registry

<!-- sourced: agents/critic/SKILL.md, agents/review-lenses/SKILL.md, skills/domain-analyzer/SKILL.md, agents/artifact-generator/SKILL.md, skills/builder/SKILL.md, 2026-02-21 -->

This registry maps cross-cutting concerns to their pipeline coverage across five dimensions. It is a **visibility tool** — empty cells are informational, not blocking. Gaps enter the normal observation > triage > action cycle.

## Pipeline Dimensions

| Dimension | What it means | Where it lives |
|-----------|--------------|----------------|
| **Discovery** | Questions/dimensions that surface this concern during Stages 0-1 | Domain Analyzer, Universal Discovery Dimensions |
| **Artifact** | Templates or generated artifacts that specify this concern | Artifact Generator, templates/ |
| **Builder** | Build instructions that implement or address this concern | Builder skill |
| **Critic** | Checks that validate this concern during review | Critic checks |
| **Review Lens** | Lens evaluations that assess this concern | Review Lenses |

## Coverage Matrix

| Concern | Status | Discovery | Artifact | Builder | Critic | Review Lens |
|---------|--------|-----------|----------|---------|--------|-------------|
| **Security** | Complete | Universal dimension: Security | security-model.md template | Builder implements per security-model artifact | Check 1 (Spec Compliance) validates against security-model | Architecture Lens evaluates security boundaries |
| **Accessibility** | Complete | Universal dimension: Users (accessibility needs); Amplified by has_human_interface | art-direction.md covers accessibility approach; NFR template includes accessibility targets | Builder implements per accessibility specs | Check 1 (Spec Compliance) validates accessibility requirements | Design Lens evaluates accessibility compliance |
| **Testing** | Complete | Universal dimension: Development Standards (testing approach); project-preferences.md captures methodology | test-specifications.md template with test strategy, levels, infrastructure | Builder Step 5 (test implementation), Step 5a (history recording) | Check 2 (Test Integrity) — dedicated check for test quality, levels, isolation | Testing Lens evaluates test strategy and coverage |
| **Deployment** | Complete | Universal dimension: Operational Lifecycle | operational-spec.md template; dependency-manifest template | Builder implements deployment per operational spec | Check 1 (Spec Compliance) validates against operational spec | Architecture Lens evaluates deployment architecture |
| **Dependencies** | Complete | Universal dimension: Dependencies and Integration Points | dependency-manifest.yaml template; security-model.md covers credential management | Builder uses only listed dependencies; raises artifact_insufficiency if unlisted needed | Check 3 (Scope Discipline) blocks unlisted dependencies; Check 4 (Proportionality) evaluates justification | Architecture Lens evaluates dependency choices; Skeptic Lens requires resilience findings for runs_unattended |
| **Data Privacy** | Complete | Amplified by handles_sensitive_data with data categories and regulatory applicability; Dimension 4 (Security) covers data lifecycle | security-model.md Data Privacy section; AG deepens for handles_sensitive_data: lifecycle, breach scenarios, audit, retention | Builder implements lifecycle management, audit logging, access controls per security-model | Check 1 (Spec Compliance) validates data handling; NFR compliance checks regulatory constraints | Architecture Lens evaluates encryption/access control; Skeptic Lens raises breach and compliance scenarios |
| **Cost** | Complete | Risk profiling includes cost of operations; Dimension 6 includes hard limits (cost); dependency discovery surfaces per-use API costs | NFR template has Cost Constraints section; dependency-manifest.yaml lists cost per dependency; operational-spec addresses deployment cost | Builder follows build plan which includes cost estimates from NFRs | Check 1 verifies operational costs identified; Check 4 (Proportionality) flags unjustified infrastructure cost | Skeptic Lens evaluates cost surprises (per-use APIs, storage growth); Architecture Lens checks deployment cost |
| **Error Handling** | Complete | Dimension 5 (Failure Modes and Recovery) explicitly surfaces error handling; amplified for runs_unattended | operational-spec.md Failure Recovery section; failure-recovery-spec.md for runs_unattended; test-specifications.md Error Cases | Builder Step 2 requires error case tests; Step 3 implements per operational-spec | Check 1 verifies error handling matches specs; Check 2 requires error case coverage | Skeptic Lens always raises failure findings; amplified for runs_unattended silent failures; Testing Lens requires failure mode coverage |
| **Performance** | Complete | Dimension 6 (Performance and Resource Constraints) with latency, throughput, resource expectations; amplified for has_human_interface | NFR template Performance section with response times and throughput targets; test-specifications.md includes performance tests | Builder implements to NFR targets; optimization only when build plan includes it | Check 1 verifies performance targets have tests; Check 4 flags optimization without justification | Architecture Lens evaluates performance concerns against NFRs; Testing Lens verifies performance test infrastructure |
| **Observability** | Complete | Dimension 7 (Operational Lifecycle) covers monitoring, log access, diagnostics; Dimension 5 asks how you would know something failed | operational-spec.md Monitoring section; monitoring-alerting-spec.md for runs_unattended with health metrics, alerting, logging | Builder implements monitoring per operational-spec and monitoring-alerting specs | Check 1 requires monitoring implemented and alerting configured; Check 6 requires observation paths for new capabilities | Skeptic Lens requires silent-failure and external-dependency-resilience findings; Architecture Lens evaluates monitoring proportionality |
| **Design System** | Complete | Dimension 10 (Product Identity) covers style, mood, visual preferences for has_human_interface | design-direction.md template with Visual Identity, Color, Typography, Spacing, Component Patterns, Motion, Platform Conventions | Builder implements design per design-direction.md specifications exactly | Check 5 (Coherence) verifies design token adherence and component reuse; Check 3 flags over-design | Design Lens evaluates consistency, interaction patterns, design identity completeness |
| **Agent Verification** | Complete | Opt-in during discovery (Stages 0-2 verification tooling question); HLD architecture section documents strategies | AG Phase D specifies verification infrastructure in scaffold chunk; per-characteristic strategies documented | Builder Step 4b (Runtime Verification) uses MCP tools (web), Bash (pipelines), or curl (APIs) | Check 1 verifies verification coverage and HR10 (dev tooling isolation) | Architecture Lens evaluates verification adequacy; Skeptic Lens evaluates observation approach |
| **Analytics / Product Metrics** | Partial | Product Brief Success Criteria implicitly expects measurable outcomes; not a dedicated discovery dimension | product-brief.md Success Criteria section; data-model could include analytics entities but not templated | Builder implements what artifacts specify; analytics only built if specified | Check 5 (Coherence) would flag metrics in Success Criteria not in Data Model | Skeptic Lens evaluates edge cases but not analytics architecture; Product Lens evaluates measurability |
| **Schema / Data Migration** | Partial | Dimension 3 (Data and Persistence) covers entity structure but not migration strategy | data-model.md specifies entities but not migration; API versioning strategy for exposes_programmatic_interface only | Builder implements per specifications; migration only built if in artifacts | Check 5 (Coherence) addresses artifact freshness but not schema versioning | Architecture Lens evaluates data model but not migration/versioning strategy |

## Status Definitions

- **Complete**: All 5 pipeline dimensions have explicit coverage for this concern.
- **Mostly Complete**: 4+ dimensions covered; remaining gaps are minor or handled indirectly.
- **Partial**: 2-3 dimensions covered; significant pipeline gaps exist.
- **Gap**: 0-1 dimensions covered; concern is effectively absent from the pipeline.

## How to Use This Registry

1. **Session health check** reads this file and reports gap counts (informational only).
2. **Critic Check 10** (Pipeline Coverage) references this registry when new artifacts or discovery dimensions are added.
3. **Structural Critique Protocol** includes a coverage audit question that checks whether the registry is complete.
4. **Gaps do NOT block anything.** They enter the normal observation > triage > action cycle via `project-state.yaml` backlog.

## Maintenance

When adding a new artifact template, discovery dimension, Critic check, or Review Lens:
- Update the relevant row(s) in the coverage matrix.
- If the change addresses a concern not yet in the registry, add a new row.
- The Critic's Pipeline Coverage check (Check 10) will flag omissions.
