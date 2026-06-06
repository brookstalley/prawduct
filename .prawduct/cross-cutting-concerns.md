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
| Accessibility | discovery.md: Surface Accessibility Needs | project-state.yaml: `accessibility_approach` | building.md (Principle 8 ref) | Goal 2 (Nothing Is Missing) | Added in meta-reflection |
| Testing | Inferred from risk level; domain-driven strategies (PBT, contract, state-machine) surfaced in discovery | Test specifications artifact (incl. Property-Based Tests section); project-preferences: Testing strategies | building.md: Test Discipline + "Test strategies match the domain" | Goal 1 (Nothing Is Broken: PBT NOTE check) | Full coverage incl. strategy guidance |
| Cost awareness | discovery.md: Surface Operational Costs | project-state.yaml: `cost_estimates`, `cost_constraints` | — | — | Discovery + artifact only; no build/critic enforcement. Proportionate for now. |
| Observability | discovery.md: Surface Observability Needs | Observability strategy artifact; project-state.yaml: `observability_approach` | building.md: observability guidance | Goal 6 (System Can Be Understood) | Full coverage |
| Performance | Structural: `runs_unattended`, scale signals | NFR artifact | building.md (implicit) | Goal 5 (Decisions Were Deliberate) | Indirect coverage via NFR |
| Error handling | discovery.md: Surface Error Handling Approach | project-state.yaml: `error_handling_approach` | building.md: Exception Handling section + intentional-waiver pragma (`docs/waivers.md`) | Goal 3 (waiver legitimacy: reason present, real boundary) + Goal 6 (System Can Be Understood) | v6: pragma marking for intentional broad catches; canary detects unwaived catches + reason-less waivers (generalized to `prawduct:allow` in the waiver-pragma work) |
| Data privacy | Structural: `handles_sensitive_data` | Security model artifact | building.md | Goal 2 (Nothing Is Missing) | Covered via security pipeline |
| Deployment | Structural awareness | Build plan artifact | building.md (Principle 10) | Goal 3 (Nothing Is Unintended) | Indirect coverage |
| Dependency management | — | Build plan: dependency manifest | building.md | Goal 3 (Nothing Is Unintended: unlisted deps) | No discovery trigger; starts at planning |
| Infrastructure dependencies | discovery.md: Surface Infrastructure Dependencies | project-state.yaml: `infrastructure_dependencies` | building.md: Verify step + Common Traps | Goal 2 (Nothing Is Missing) + Goal 4 (Coherence) | Full coverage |
| Boundary coherence | Structural: detected at build time | boundary-patterns.md | building.md: Investigated Changes | Goal 5 (Decisions Were Deliberate) | v5: boundary investigation + compliance canary |
| Subagent governance | — | .subagent-briefing.md (generated) | building.md: Delegating Work | Goal 4 (Everything Is Coherent) | v5: briefing file + Critic reviews all output |
| PR review | N/A (framework capability) | skills/pr/review-protocol.md | building.md: Creating Pull Requests | N/A (PR reviewer is peer of Critic) | `/pr` skill invokes reviewer agent; stop hook blocks without evidence |
| Requirements clarity | discovery.md: Discovery Recurs + **Calibrate Rigor to Stakes, Knowledge, and Volatility** (self-assessment + intentional inference + research triggers) | build-plan.md: Requirements Confidence + **Open assumptions** (`[ASSUMPTION]` format); planning.md: Assumptions element | building.md: Before You Build (condensed) + **A Requirement Surfaced Mid-Build** tripwires + Decision Research (volatility trigger); CLAUDE.md + session digest: rigor-scaling runtime trigger + no-silent-invent mirror; **runtime**: UserPromptSubmit orphan-term nudge (`prawduct-hook user-prompt-submit`, `lib/work_model_index.py`) | Goal 2 (acceptance criteria as observable behavior + Requirements Confidence field present) | v1.3.15; expanded rigor-and-stance (2026-06-04) — proportional rigor (stakes × knowledge-confidence × volatility), intentional vetoable-assumption inference; anchored on Principle 6; **work-model (2026-06-06)** — undocumented-requirement catch (Principle 6 mirror: never silently *invent* a requirement) |
| Discovery capture | discovery.md: **Reconciling an Existing or Docs-First Product** (reconciliation entry path when docs/code precede discovery) | project-state.yaml: `classification` + `product_definition` (the captured outputs); onboard SKILL routes to `/prawduct:discovery` | `cmd_clear` session briefing: **DISCOVERY NOT CAPTURED** nudge when state is template-default but the repo shows product work (code or `docs/*.md`) | — (enforced by the briefing nudge + `/prawduct:doctor` Health Check #6, not a code-Critic goal) | discovery-capture-nudge (2026-06-05); closes the docs-first / brownfield onboard gap surfaced by Scriob |
| Agent stance / conduct | N/A (framework-wide agent behavior, not a per-product concern) | methodology/agent-stance.md (the 9 stances); session-digest.md (condensed always-on carrier) | building.md + all guides (stances operationalize the principles) | — (conduct, not a code artifact; some stances align with existing goals — scope-discipline ↔ Goal 7, verify-own-work ↔ Goal 1) | rigor-and-stance (2026-06-04); voice/conduct register complementing the 23 principles; digest is the carrier (a force-for-plugin output style would clobber a consumer's style — verified) |
| Foreign API verification | discovery.md: Surface Infrastructure Dependencies (Foreign APIs subcategory) | build-plan.md: `**Foreign API:** <name>` field | planning.md: Foreign API Verification section (verify-api step prepended as Done-when step 0) | Goal 2: chunks with `**Foreign API:**` need `verify-api` in Done-when → WARNING | v1.4 F8; anchored on hallucinote's Ableton-MCP rework pattern |
| Cumulative-Critic gate | — | build-plan.md: Wave structure (chunks group into bundles) | building.md: cumulative pass at wave end | Cumulative mode (lens: `merge-base...HEAD`, distinct from chunk lens) | v1.4 F2; `pr/SKILL.md` Step 2 invokes `check-cumulative-critic` before PR creation |
| Build-plan ref drift | — | build-plan.md: backticked path references resolved to real files | building.md: builder runs `verify-chunk-refs` before marking chunk done | Goal 2: non-zero `verify-chunk-refs` exit → BLOCKING | v1.4 F3; `prawduct-hook verify-chunk-refs [chunk_id]` |
| Chunk Type / proportional review | — | build-plan.md: `**Type:**` field (`code` \| `doc-only` \| `cleanup` \| `designer-handoff` \| `cumulative-final`) | planning.md: Type allowed values + scope guidance per type | Goal selection modulated by Type (e.g. doc-only skips test-coverage goals); unknown Type fails closed to `code` | v1.4 F6; orthogonal to mode axis |
| Derived views (work-log → Status / release-notes / scope-rollups) | — | change-log.md `<!-- prawduct: ... -->` tag schema (`chunks=`, `status=shipped`, `release=`, `scope=`); project-state.yaml: `views_enabled`, `scope_rollups` | building.md chunk-close step: run `regen-views` (or add tagged change-log entry) instead of hand-editing Status; sync auto-enables on v1.3.x → v1.4 upgrade | Goal 4: view ↔ tag mismatch → WARNING ("run regen-views"); flag the source change-log entry, not the derived file | v1.4 F1; `prawduct-hook regen-views`; one-shot manifest tracking via `v1_4_views_enabled` |
| Coverage evidence (symbol-coverage floor + enforcement) | — | `.test-evidence.json` F4a fields (`verifier`, `tests_executed`, `changes_referenced`, `coverage_level`); project-state.yaml: `coverage_required` | building.md Test Discipline: "Idiomatic tooling, honest coverage" paragraph names floor caveat + recommends real-coverage tools for `executed` | Goal 1: `verify-coverage` BLOCKING per missing file when opted in; wording scaled to `coverage_level` (floor `referenced` disclaims execution; `executed` does not) | v1.4 F4; `bin/test-reference-verify` ships as Python floor, setting `coverage_required: true` is the opt-in path, default off in v1.4 (workflow commitment), v1.5 drops legacy-shape compat |

## Known Gaps

- **Cost awareness** lacks builder guidance and Critic enforcement. Currently proportionate — most products don't need cost gates during build. Revisit if cost overruns become a pattern.
- **Error handling** — resolved. Now has full pipeline coverage: discovery surfaces approach, builder has the Exception Handling section using the general intentional-waiver pragma `prawduct:allow prawduct/broad-except -- reason` (spec `docs/waivers.md`; legacy `prawduct:ok-broad-except` still honored), the Critic verifies each waiver is legitimate (reason present, genuine boundary), and the compliance canary flags both unwaived broad catches and reason-less waivers.
- **Dependency management** has no discovery trigger. Dependencies are a planning concern. This is by design.
- **Learnings relevance filtering**: Session briefing now shows a topic index of section headers instead of the last 3 rules. Learnings are consumed at Critic review, PR review, planning, and building. Future work: a `/learnings [topic]` skill for targeted lookup without loading the full file. Tracked as a potential enhancement, not blocking.

## Maintenance

Update this registry when:
- A new concern is added to any pipeline stage
- An existing concern's coverage changes
- The Critic reviews framework changes that touch cross-cutting concerns (Pipeline Coverage check)

This registry is human-maintained. Don't automate validation — the value is in the thinking, not the checking.
