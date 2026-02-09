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

Components, in recommended implementation order:

1. **C2: Domain Analyzer** (`skills/domain-analyzer/SKILL.md`) — The most novel piece. Start here. Test against diverse product ideas.
2. **C1: Orchestrator** (`skills/orchestrator/SKILL.md`) — Conversation flow, stage management, calibration. Depends on C2.
3. **C3: Artifact Generator** (`skills/artifact-generator/SKILL.md`) — Templates and generation logic. Start with universal artifacts, add shape-specific ones.
4. **C5: Project State** (`templates/project-state.yaml`) — Schema design. Define what gets tracked and how.
5. **C4: Review Lenses** (`skills/review-lenses/SKILL.md`) — May merge into critic skill. Build and evaluate.
6. **Mechanical tools** (`tools/`) — Test integrity, doc validation, boundary checking. Satisfying because they're deterministic.
7. **C6: Critic** (`skills/critic/SKILL.md`) — Combines LLM judgment with mechanical tool invocations.

C7 (Trajectory Monitor) and C8 (Learning System) are post-v1. Accommodate them architecturally but don't build them yet.

## Testing Strategy for This Project

Since this project is a framework of skills and tools (not a traditional application), testing looks different:

- **Skills:** Test by running them against diverse product scenarios. Minimum test scenarios: a consumer mobile app, a background automation, a B2B API, a simple family utility, and a multi-party platform. Evaluate whether the skill asks the right questions, produces good artifacts, and catches problems.
- **Mechanical tools:** Standard unit/integration tests. Feed them known-good and known-bad project states and verify correct detection.
- **End-to-end:** Take a product idea from raw input through to build plan using the full framework. Evaluate the build plan's quality. This is the compiler-compiles-itself test.

## Conventions

- **File naming:** lowercase-with-hyphens for all files and directories.
- **Skill format:** Every SKILL.md starts with a one-paragraph purpose statement, then structured instructions.
- **Templates:** Include comments/guidance explaining what goes in each section. Templates are instructional, not just structural.
- **Commit messages:** Describe what changed and why. "Updated orchestrator skill" is not acceptable. "Added pacing sensitivity to orchestrator: system now adapts discovery depth to user patience level (R1.8)" is.
- **Working notes:** Any file in `working-notes/` must include a creation date. Notes older than 2 weeks are stale — incorporate into Tier 1 or delete.
