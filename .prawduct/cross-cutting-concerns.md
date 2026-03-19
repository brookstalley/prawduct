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
| Security | Structural: `handles_sensitive_data` | Security model artifact | building.md | Goal 1 (Nothing Is Broken: injection, secrets, input validation) + Goal 2 (auth completeness) | Full coverage |
| Accessibility | discovery.md: Surface Accessibility Needs | project-state.yaml: `accessibility_approach` | building.md (Principle 7 ref) | Goal 2 (Nothing Is Missing) | Added in meta-reflection |
| Testing | Inferred from risk level | Test specifications artifact | building.md: Test Discipline | Goal 1 (Nothing Is Broken) | Full coverage |
| Cost awareness | discovery.md: Surface Operational Costs | project-state.yaml: `cost_estimates`, `cost_constraints` | — | — | Discovery + artifact only; no build/critic enforcement. Proportionate for now. |
| Observability | discovery.md: Surface Observability Needs | Observability strategy artifact; project-state.yaml: `observability_approach` | building.md: observability guidance | Goal 6 (System Can Be Understood) | Full coverage |
| Performance | Structural: `runs_unattended`, scale signals | NFR artifact | building.md (implicit) | Goal 5 (Decisions Were Deliberate) | Indirect coverage via NFR |
| Error handling | discovery.md: Surface Error Handling Approach | project-state.yaml: `error_handling_approach` | building.md: Exception Handling section + pragma convention | Goal 3 (broad-except pragma verification) + Goal 6 (System Can Be Understood) | v6: pragma marking for intentional broad catches; canary detects unmarked catches |
| Data privacy | Structural: `handles_sensitive_data` | Security model artifact | building.md | Goal 2 (Nothing Is Missing) | Covered via security pipeline |
| Deployment | Structural awareness | Build plan artifact | building.md (Principle 9) | Goal 3 (Nothing Is Unintended) | Indirect coverage |
| Dependency management | — | Build plan: dependency manifest | building.md | Goal 3 (Nothing Is Unintended: unlisted deps) | No discovery trigger; starts at planning |
| Infrastructure dependencies | discovery.md: Surface Infrastructure Dependencies | project-state.yaml: `infrastructure_dependencies` | building.md: Verify step + Common Traps | Goal 2 (Nothing Is Missing) + Goal 4 (Coherence) | Full coverage |
| Boundary coherence | Structural: detected at build time | boundary-patterns.md | building.md: Investigated Changes | Goal 5 (Decisions Were Deliberate) | v5: boundary investigation + compliance canary |
| Subagent governance | — | .subagent-briefing.md (generated) | building.md: Delegating Work | Goal 4 (Everything Is Coherent) | v5: briefing file + Critic reviews all output |
| PR review | N/A (framework capability) | agents/pr-reviewer/SKILL.md, templates/pr-review.md | building.md: Creating Pull Requests | N/A (PR reviewer is peer of Critic) | `/pr` skill invokes reviewer agent; stop hook blocks without evidence |

## Known Gaps

- **Cost awareness** lacks builder guidance and Critic enforcement. Currently proportionate — most products don't need cost gates during build. Revisit if cost overruns become a pattern.
- **Error handling** — resolved. Now has full pipeline coverage: discovery surfaces approach, builder has Exception Handling section with `prawduct:ok-broad-except` pragma convention, Critic verifies marked catches are at genuine system boundaries, and the compliance canary flags unmarked broad catches.
- **Dependency management** has no discovery trigger. Dependencies are a planning concern. This is by design.
- **Learnings relevance filtering** is not yet implemented in the session briefing. Currently shows the last 3 rule-formatted learnings. Future work: filter by recent git changes and file types. Tracked as a potential enhancement, not blocking.

## Maintenance

Update this registry when:
- A new concern is added to any pipeline stage
- An existing concern's coverage changes
- The Critic reviews framework changes that touch cross-cutting concerns (Pipeline Coverage check)

This registry is human-maintained. Don't automate validation — the value is in the thinking, not the checking.
