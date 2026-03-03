# Cross-Cutting Concerns Registry

Maps concerns to pipeline coverage. Use this as a starting point for completeness checks — but think about what's missing, not just what's listed.

**Pipeline dimensions:**
- **Discovery** — Is this concern surfaced during discovery?
- **Artifact** — Does at least one artifact template specify it?
- **Builder** — Does the build methodology guide implementation?
- **Critic** — Does the Critic have a check that validates it?

## Coverage Matrix

| Concern | Discovery | Artifact | Builder | Critic | Notes |
|---------|-----------|----------|---------|--------|-------|
| Security | Structural: `handles_sensitive_data` | Security model artifact | building.md | Check 1 (Spec Compliance) | Full coverage |
| Accessibility | discovery.md: Surface Accessibility Needs | project-state.yaml: `accessibility_approach` | building.md (Principle 7 ref) | Check 1 (Spec Compliance) | Added in meta-reflection |
| Testing | Inferred from risk level | Test specifications artifact | building.md: Test Discipline | Check 2 (Test Integrity) | Full coverage |
| Cost awareness | discovery.md: Surface Operational Costs | project-state.yaml: `cost_estimates`, `cost_constraints` | — | — | Discovery + artifact only; no build/critic enforcement. Proportionate for now. |
| Observability | discovery.md: Surface Observability Needs | Observability strategy artifact; project-state.yaml: `observability_approach` | building.md: observability implementation guidance | Check 6 (Learning/Observability) | Full coverage |
| Performance | Structural: `runs_unattended`, scale signals | NFR artifact | building.md (implicit) | Check 4 (Proportionality) | Indirect coverage via NFR |
| Error handling | discovery.md: Surface Error Handling Approach | project-state.yaml: `error_handling_approach` | building.md: Test Discipline (error cases) | Check 6 (Learning/Observability) | Discovery surfaces approach scaled to risk; test discipline validates coverage |
| Data privacy | Structural: `handles_sensitive_data` | Security model artifact | building.md | Check 1 (Spec Compliance) | Covered via security pipeline |
| Deployment | Structural awareness | Build plan artifact | building.md (Principle 9) | Check 3 (Scope Discipline) | Indirect coverage |
| Dependency management | — | Build plan: dependency manifest | building.md | Check 3 (Scope: unlisted deps) | No discovery trigger; starts at planning |

## Known Gaps

- **Cost awareness** lacks builder guidance and Critic enforcement. Currently proportionate — most products don't need cost gates during build. Revisit if cost overruns become a pattern.
- **Error handling** now has discovery coverage and a `project-state.yaml` field (`error_handling_approach`). Design depth scales to risk — standard patterns for low-risk, full error architecture for high-risk. Build enforcement comes from test discipline (error case coverage) and Critic Check 6.
- **Dependency management** has no discovery trigger. Dependencies are a planning concern, not a discovery concern. This is by design.

## Maintenance

Update this registry when:
- A new concern is added to any pipeline stage
- An existing concern's coverage changes
- The Critic reviews framework changes that touch cross-cutting concerns (Check 10)

This registry is human-maintained. Don't automate validation — the value is in the thinking, not the checking.
