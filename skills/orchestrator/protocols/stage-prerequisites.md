# Stage Transition Prerequisites

Per-stage prerequisite checklists referenced by the Stage Transition Protocol in `skills/orchestrator/protocols/governance.md`.

---

### → Stage 1 (Discovery)
- `classification.structural` has at least one non-null structural characteristic
- `classification.domain` is set
- `classification.risk_profile.overall` is set
- `classification.risk_profile.factors` has at least 2 entries with rationale

### → Stage 2 (Definition)
- `product_definition.vision` is set
- `product_definition.users.personas` has at least one persona
- `product_definition.core_flows` has at least one flow
- `product_definition.platform` is set
- `user_expertise` has at least `technical_depth` and `product_thinking` inferred

### → Stage 3 (Artifact Generation)
This is the highest-stakes transition — discovery becomes production. Check thoroughly:

- All Stage 2 prerequisites met
- `product_definition.scope.v1` has at least 3 items
- `product_definition.scope.later` has at least 1 item (scope without deferral is suspicious)
- `product_definition.goals` has at least 1 measurable success criterion
- `product_definition.nonfunctional` has at least `performance` and `uptime` set
- `technical_decisions` has at least one decision with rationale (the specific decisions needed depend on the product — check that every choice affecting implementation complexity has been made)
- When `structural.has_human_interface` is active: `design_decisions.accessibility_approach` is set
- `open_questions` has no high-priority items with `waiting_on: "user"` (unresolved user questions block artifact generation)
- `classification.domain_characteristics` is populated (at least 1 entry)

### → Stage 4 (Build Planning)
- All Stage 3 prerequisites met
- All 7 universal artifacts generated (or minimal artifacts where applicable) with correct frontmatter
- Cross-artifact consistency check passed
- All five review lenses applied (Testing Lens in Phase C), all blocking findings resolved
- Artifacts presented to user (user can interrupt with corrections)

### → Stage 5 (Building)
- Build plan artifact generated (`artifacts/build-plan.md`)
- `build_plan.strategy` is set in project-state.yaml
- `build_plan.chunks` has at least 3 entries (scaffold + data layer + at least one feature)
- Every chunk has `acceptance_criteria` mapped to test specification scenarios
- `build_plan.governance_checkpoints` has at least one checkpoint
- Build plan presented to user (user can interrupt with corrections)

### → Stage 6 (Iteration)
- All chunks in `build_plan.chunks` have status "complete"
- All tests pass
- Full Critic product governance review completed
- Product presented to user with instructions for running it
