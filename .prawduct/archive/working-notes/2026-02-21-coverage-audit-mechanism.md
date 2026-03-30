# Design Proposal: Coverage Audit Mechanism

**Status**: Proposal (not yet implemented)
**Tier**: 3 (Working Note — design exploration)
**Created**: 2026-02-21
**Expires**: 2026-03-07

---

## Problem Statement

The framework's self-improvement loop is reactive: it observes friction during use and learns from it. This catches behavioral issues (proportionality drift, process friction, coherence gaps) because they produce repeated observations that cross detection thresholds.

**Omission gaps are invisible to this loop.** If the framework doesn't address a cross-cutting concern (e.g., design systems, observability), there's no artifact for it, no Critic check, no observation, and nothing enters the improvement pipeline. The concern simply doesn't exist from the framework's perspective.

### Evidence

Two significant gaps — design systems and observability — persisted through:
- 13+ product evaluation scenarios
- 6+ framework development sessions
- 2 external audits
- Multiple Structural Critique Protocol invocations

Neither was detected because neither produced an observation. They were identified only when a human with domain expertise reviewed the framework's coverage against industry standards.

### Root Cause

The framework has three self-improvement mechanisms:

| Mechanism | What it catches | Why it missed this |
|-----------|----------------|-------------------|
| Observation system (C8a) | Friction during use — things that go wrong | Omission gaps don't produce friction; the concern simply never arises |
| Critic (C6) | Quality issues in what exists — coherence, compliance, scope | Checks what's there, not what's absent |
| Structural Critique Protocol | Architectural misalignment with principles | Fires infrequently; scope is structural characteristics, not cross-cutting concerns |

**The gap**: The framework audits **coherence** (are things we address internally consistent?) but not **coverage** (are we addressing everything we should?).

### Meta-Meta Analysis: What Else Is Missing?

The same mechanism that missed design systems and observability likely missed other cross-cutting concerns. An exhaustive audit (performed 2026-02-21) identified these additional gaps, ranked by how often they matter:

| Concern | Impact | Current State |
|---------|--------|---------------|
| **Error handling strategy** | Nearly universal | Only covered for unattended pipelines; no consistent taxonomy or UX guidance |
| **Performance verification** | High for anything with users | NFRs set targets but nothing verifies them under load |
| **Analytics / product metrics** | High for consumer products | Completely absent — products ship with no usage insight |
| **Schema/data migration** | Critical for stateful evolving apps | Not covered |
| **Dependency security** | Universal | Manifest exists with "risk" field, no CVE/license scanning |
| **Cost monitoring** | Important for cloud-deployed | Estimation at design time only, no runtime tracking |

These should be tracked in the proposed registry (below) and addressed proportionate to their impact.

---

## Proposed Solution

### A. Cross-Cutting Concerns Registry

A new Tier 1 artifact: `.prawduct/artifacts/cross-cutting-concerns-registry.md`

Maps each cross-cutting concern the framework addresses to its full pipeline coverage:

```
| Concern | Discovery | Artifact | Builder | Critic | Review Lens | Status |
|---------|-----------|----------|---------|--------|-------------|--------|
| Security | Dim 4 + handles_sensitive_data | security-model.md | Spec compliance | Check 1 | Arch (proportionality), Skeptic (abuse) | Complete |
| Accessibility | HR7 + has_human_interface | accessibility-spec.md | HR7 enforcement | Check 1 | Design (mandatory finding) | Complete |
| Observability | Dim 7 (partial) | None (gap) | None | None | Skeptic (partial) | Gap — see proposal |
| Design System | Dim 10 (partial) | design-direction.md (partial) | None | None | Design (partial) | Gap — see proposal |
| Error Handling | Dim 5 (pipelines only) | failure-recovery-spec (unattended only) | None | None | None | Gap |
| Performance | Dim 6 + NFRs | nonfunctional-requirements.md | None (no verification) | None | Skeptic (partial) | Partial |
| Cost Awareness | HR8 + Dim 6 | nonfunctional-requirements.md (estimates) | None (no monitoring) | None | Skeptic (cost surprises) | Partial |
| Data Privacy | Dim 4 + handles_sensitive_data | security-model.md (section) | Spec compliance | Check 1 | Skeptic | Mostly complete |
| Dependency Mgmt | Dim 8 | dependency-manifest.yaml | Spec compliance | Check 1 | Arch, Skeptic | Mostly complete (no security scanning) |
| Deployment | Dim 7 | operational-spec.md | Spec compliance | Check 1 | Arch | Complete for v1 |
| Testing Strategy | All dims | test-specifications.md | Builder step 4 | Check 2 | Testing Lens | Complete |
```

**Three functions of the registry:**
1. **Gap detection**: Empty cells are pipeline gaps — a concern that's discovered but not specified, or specified but not checked.
2. **Completeness audit**: The concern list itself is reviewed against industry standards.
3. **New concern onboarding**: When adding a concern, the registry shows exactly what pipeline steps need implementation.

### B. Coverage Audit Protocol

Integrated into two existing mechanisms:

**1. Session health check** (`tools/session-health-check.sh`):
- Read the registry
- Count concerns with gaps (any empty pipeline cell)
- Report: `COVERAGE_GAPS: N concerns with incomplete pipeline coverage`
- List each gap with its missing cells

**2. Structural Critique Protocol** (expanded trigger):
- After the existing structural characteristics review, add: "Does the concerns registry include all cross-cutting concerns relevant to products in [current domain]?"
- This catches concerns missing from the registry entirely (not just pipeline gaps within known concerns)

### C. Critic Framework Check

Expand the Critic's framework-specific checks to include pipeline coverage:

**When a new artifact template is created:**
- Does the template have corresponding discovery questions?
- Does the Critic have a check that validates against this artifact?
- Does at least one Review Lens evaluate this artifact's domain?

**When a new discovery dimension or amplification rule is added:**
- Does it lead to an artifact that captures the discovered information?
- Does the Builder have guidance on implementing it?

This is a **coherence check applied to the pipeline itself**, not to artifact content. It asks: "is the framework's own plumbing complete?"

---

## Integration Points

| File | Change | Scope |
|------|--------|-------|
| `.prawduct/artifacts/cross-cutting-concerns-registry.md` | **New** — Tier 1 artifact with pipeline mapping | New file |
| `tools/session-health-check.sh` | Add registry gap check | Small addition |
| `docs/self-improvement-architecture.md` | Add Failure Mode 11: Omission Gaps Invisible to Reactive Learning | Section addition |
| `agents/critic/framework-checks.md` | Add pipeline coverage check | Small addition |
| `skills/orchestrator/protocols/governance.md` | Expand SCP to include coverage audit | Small addition |
| `docs/high-level-design.md` | Mention registry in Cross-Cutting Concerns section | Small addition |

**Estimated scope**: Enhancement-tier DCP. 1 new file, 5 modified files. No template changes, no discovery changes, no builder changes.

---

## Implementation Sequence

1. Create the registry with current state (accurately reflecting what exists today and what's missing)
2. Add health check integration
3. Add Critic pipeline coverage check
4. Expand SCP
5. Document in self-improvement-architecture.md
6. Run Critic review on all changes

**Dependency**: This mechanism should be implemented first, before the design system and observability proposals. It provides the tracking structure that makes those implementations measurable and ensures future gaps are caught.

---

## Open Questions

1. **Registry granularity**: Should the registry track concerns at the level shown above (Security, Accessibility, Observability) or finer-grained (Authentication, Authorization, Data Privacy, Encryption)? The coarser level seems right — too fine and it becomes an enumeration that violates Generality Over Enumeration. Each row should represent a cross-cutting concern that needs its own pipeline, not a sub-aspect of an existing concern.

2. **Automation potential**: Could the health check mechanically verify pipeline coverage (e.g., grep for template references in Critic checks)? Partially — it can verify file existence but not semantic coverage. The registry's value is in human-maintained semantic mapping.

3. **Scope boundary**: What distinguishes a "cross-cutting concern" that needs a registry row from a "feature" that's handled by existing mechanisms? Proposed heuristic: a concern is cross-cutting if it applies to multiple product types and requires discovery → artifact → build → review pipeline coverage. A feature is product-specific and handled by the existing artifact system.
