---
artifact: cross-cutting-concerns-registry
version: 1
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
| **Dependencies** | Mostly Complete | Universal dimension: Dependencies | dependency-manifest.yaml template | Builder manages dependencies per manifest | Check 1 (Spec Compliance) validates dependency declarations | Architecture Lens evaluates dependency choices |
| **Data Privacy** | Mostly Complete | Amplified by handles_sensitive_data; Universal dimension: Security covers data handling | security-model.md covers data lifecycle and access controls | Builder implements per security model | Check 1 (Spec Compliance) validates data handling | Architecture Lens evaluates data boundaries |
| **Cost** | Partial | Universal dimension: Operational Lifecycle (cost-relevant choices); NFR discovery | NFR template includes cost targets; operational-spec covers infrastructure cost | — | — | Skeptic Lens flags cost concerns |
| **Error Handling** | Partial | Amplified by runs_unattended (failure recovery); Universal dimension: Failure Modes | failure-recovery-spec.md (runs_unattended only); no universal error handling artifact | Builder implements error handling per failure-recovery-spec | Check 1 (Spec Compliance) validates against failure-recovery-spec when present | Architecture Lens evaluates resilience |
| **Performance** | Partial | Universal dimension: Performance (NFR targets) | NFR template includes performance targets | Builder implements to NFR targets | Check 1 (Spec Compliance) validates NFR compliance | Architecture Lens evaluates performance architecture |
| **Observability** | Partial | Amplified by runs_unattended (monitoring); Universal dimension: Operational Lifecycle | monitoring-alerting-spec.md (runs_unattended only); no universal observability artifact | Builder implements monitoring per spec when present | — | — |
| **Design System** | Partial | Art direction discovered for has_human_interface products | art-direction.md covers visual direction and principles | Builder follows art direction | — | Design Lens evaluates visual consistency |
| **Agent Verification** | Partial | Opt-in discovery dimension (not default); HLD architecture section | — | Builder Step 4b (verification infrastructure) | — | — |
| **Analytics / Product Metrics** | Gap | — | — | — | — | — |
| **Schema / Data Migration** | Gap | — | — | — | — | — |

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
