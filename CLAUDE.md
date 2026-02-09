# CLAUDE.md — Prawduct

## What This Project Is

Prawduct is a framework that turns vague product ideas into well-built software. It does this by guiding structured discovery, producing agent-executable build plans, and enforcing quality throughout development. You (Claude) are both the builder of this framework and its primary runtime.

Read `docs/vision.md` for the full picture. Read `docs/principles.md` before making any decisions — it contains the hard rules.

## Project Structure

```
prawduct/
├── CLAUDE.md                          # You are here
├── skills/                            # LLM instruction sets (your behavior)
│   ├── orchestrator/SKILL.md          # Conversation flow, stage management, user calibration
│   ├── domain-analyzer/SKILL.md       # Product classification, discovery questions, principles
│   ├── artifact-generator/SKILL.md    # How to produce each artifact type, format specs
│   ├── critic/SKILL.md                # Governance rules, review cycle, fix verification
│   └── review-lenses/SKILL.md         # Four evaluation perspectives (product, design, arch, skeptic)
├── tools/                             # Deterministic scripts (mechanical enforcement)
│   ├── test-integrity-checker.sh      # Monitor test count, assertion trends, corruption patterns
│   ├── doc-architecture-validator.sh  # Enforce tier system, manifest compliance, orphan detection
│   ├── boundary-checker.sh            # Verify architectural boundary respect
│   └── spec-compliance-diff.sh        # Diff specifications against implementation
├── templates/                         # Starting templates for user project artifacts
│   ├── project-state.yaml             # Master project state (decisions, deps, open questions)
│   ├── doc-manifest.yaml              # Documentation tier tracking
│   ├── product-brief.md               # Template: users, personas, problem, success criteria
│   ├── data-model.md                  # Template: entities, relationships, constraints
│   ├── security-model.md              # Template: auth, authorization, privacy, abuse prevention
│   ├── test-specifications.md         # Template: scenarios at all levels
│   ├── nonfunctional-requirements.md  # Template: performance, cost, uptime, scalability
│   ├── operational-spec.md            # Template: deployment, monitoring, alerting, recovery
│   ├── dependency-manifest.yaml       # Template: external deps with justification
│   ├── ui/                            # UI application shape
│   │   ├── information-architecture.md
│   │   ├── screen-spec.md             # Per-screen template (all states)
│   │   ├── design-direction.md
│   │   ├── accessibility-spec.md
│   │   ├── localization-requirements.md
│   │   └── onboarding-spec.md
│   ├── api/                           # API/service shape
│   │   ├── api-contract.md            # Per-endpoint template
│   │   ├── integration-guide.md
│   │   ├── versioning-strategy.md
│   │   └── sla-definition.md
│   ├── automation/                    # Automation/pipeline shape
│   │   ├── pipeline-architecture.md
│   │   ├── scheduling-spec.md
│   │   ├── monitoring-alerting-spec.md
│   │   ├── failure-recovery-spec.md
│   │   └── configuration-spec.md
│   └── multi-party/                   # Multi-party platform shape
│       ├── party-experience-spec.md   # Per-party template
│       ├── party-interaction-model.md
│       └── migration-adoption-plan.md
├── docs/                              # This project's own Tier 1 documentation
│   ├── vision.md
│   ├── requirements.md
│   ├── principles.md
│   └── high-level-design.md
└── working-notes/                     # Tier 3 ephemeral docs (auto-expire after 2 weeks)
    └── .gitkeep
```

## How to Work on This Project

### If you're building Prawduct itself:
1. Read `docs/principles.md` — these are your hard rules. Never violate them.
2. Read `docs/requirements.md` — focus on [v1] tagged items.
3. Read `docs/high-level-design.md` — understand the components and their interactions.
4. Apply the framework to itself. Every decision needs rationale. Every artifact needs tests. Documentation follows the tier system.

### If you're using Prawduct to build a user's product:
1. Read the orchestrator skill: `skills/orchestrator/SKILL.md`
2. It will tell you what other skills to invoke and when.
3. The general flow is: classify → validate → discover → define → generate artifacts → build → govern → iterate.
4. User project files go in a separate project directory, not in the prawduct tree.

## Key Principles (read `docs/principles.md` for the full set)

These are the ones most likely to be violated under pressure:

- **HR1: No Test Corruption.** Never weaken, delete, or comment out tests to make them pass. Fix the code or formally change the spec.
- **HR2: No Silent Requirement Dropping.** If you can't implement something, flag it. Don't skip it.
- **HR3: No Documentation Fiction.** Docs describe reality, not intent.
- **HR5: No Confidence Without Basis.** If you're unsure, say so explicitly.
- **HR6: No Ad Hoc Documentation.** Every doc has a tier, an owner, and a location. No orphans.

## V1 Build Order

Build as a vertical slice, not component-by-component. See `docs/high-level-design.md` § "Bootstrapping: Vertical Slice Approach" for the full rationale.

### Phase 1: Prove the Path (one scenario end-to-end)

Use the **family utility** test scenario (simple UI app, low risk). Build just enough of each component to handle this one case through the full pipeline:

1. **C5: Project State** (`templates/project-state.yaml`) — Define the schema first. Everything else reads/writes this.
2. **C2: Domain Analyzer** (`skills/domain-analyzer/SKILL.md`) — Classify "UI Application" + "Utility." Generate discovery questions for this combination only.
3. **C1: Orchestrator** (`skills/orchestrator/SKILL.md`) — Manage stages 0 → 0.5 → 1 → 2 for this one scenario.
4. **C3: Artifact Generator** (`skills/artifact-generator/SKILL.md`) — Generate universal artifacts only (product brief, data model, security model, test specs, NFRs, operational spec, dependency manifest).
5. **C4: Review Lenses** (`skills/review-lenses/SKILL.md`) — Apply all four lenses to the generated artifacts.

**Evaluate against the family utility test scenario rubric** (see `docs/high-level-design.md` § "Validation Strategy for Skills"). Phase 1 succeeds when the end-to-end flow produces useful, consistent output from a vague input.

### Phase 2: Widen

- Add product shapes one at a time (automation → API → multi-party), evaluating each against its test scenario rubric.
- Add shape-specific artifacts and templates as each shape is added.
- Build mechanical tools (`tools/`).
- Build the Critic (C6) — start with spec compliance + test integrity.
- Add Orchestrator sophistication (pacing, expertise calibration, pushback).

### Phase 3: Full V1

All v1 requirements, all five test scenarios passing, framework governing its own development.

C7 (Trajectory Monitor) and C8 (Learning System) are post-v1. Accommodate them architecturally but don't build them yet.

## Testing Strategy for This Project

Since this project is a framework of skills and tools (not a traditional application), testing looks different. See `docs/high-level-design.md` § "Validation Strategy for Skills" for the full approach.

- **Skills:** Test against five defined product scenarios with evaluation rubrics specifying must-do, must-not-do, and quality criteria. "Good" is not a test — specific, observable criteria are. The five scenarios: consumer mobile app, background automation, B2B API, family utility, two-sided marketplace.
- **Mechanical tools:** Standard unit/integration tests. Feed them known-good and known-bad project states and verify correct detection.
- **End-to-end:** Take a product idea from raw input through to build plan using the full framework. Evaluate the build plan against its scenario rubric. The compiler-compiles-itself test: run Prawduct through Prawduct.

## Conventions

- **File naming:** lowercase-with-hyphens for all files and directories.
- **Skill format:** Every SKILL.md starts with a one-paragraph purpose statement, then structured instructions.
- **Templates:** Include comments/guidance explaining what goes in each section. Templates are instructional, not just structural.
- **Commit messages:** Describe what changed and why. "Updated orchestrator skill" is not acceptable. "Added pacing sensitivity to orchestrator: system now adapts discovery depth to user patience level (R1.8)" is.
- **Working notes:** Any file in `working-notes/` must include a creation date. Notes older than 2 weeks are stale — incorporate into Tier 1 or delete.
