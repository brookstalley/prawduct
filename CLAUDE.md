# CLAUDE.md — Prawduct

## What This Project Is

Prawduct is a framework that turns vague product ideas into well-built software. It does this by guiding structured discovery, producing agent-executable build plans, and enforcing quality throughout development. You (Claude) are its primary runtime — you read these skills and follow their instructions to help users build products.

## When Someone Opens This Directory

Route based on what the user says:

**They describe a product idea** ("I want to build an app that...", "let's make a tool for...", "I have an idea for..."):
→ They want to USE Prawduct. Read `skills/orchestrator/SKILL.md` and follow its instructions. The Orchestrator handles everything from here — classification, discovery, product definition, artifact generation, and review. **Important:** The Orchestrator will set up a separate project directory for their files. Never write project output into this framework directory.

**They reference framework internals or want to work on this project** ("fix the domain analyzer", "update the rubric", "work on Phase 2", "what should I work on next?", "run the eval", "I want to contribute"):
→ They want to BUILD Prawduct itself. Follow the framework development instructions below. Use the V1 Build Order and current project state to orient.

**Their intent is unclear** ("let's go!", "hello", "what can you do?"):
→ Explain what Prawduct does and ask what they'd like to build. Something like:

> "Prawduct helps turn a product idea into a clear, detailed build plan. Tell me what you want to build — even a rough idea is fine — and I'll guide you through some questions about who it's for and what matters most. Then I'll produce a set of artifacts (product brief, data model, security model, test specs, and more) that a developer or coding agent can use to start building. What would you like to build?"

If they then describe a product, route to the Orchestrator. If they want to work on the framework, follow the framework development instructions.

## Project Structure

```
prawduct/
├── CLAUDE.md                          # You are here
├── skills/                            # LLM instruction sets (your behavior)
│   ├── orchestrator/SKILL.md          # Conversation flow, stage management, user calibration
│   ├── domain-analyzer/SKILL.md       # Product classification, discovery questions, principles
│   ├── artifact-generator/SKILL.md    # How to produce each artifact type, format specs
│   ├── critic/SKILL.md                # Framework self-governance + product build governance
│   └── review-lenses/SKILL.md         # Four evaluation perspectives (product, design, arch, skeptic)
├── tools/                             # Deterministic scripts (mechanical enforcement)
│   ├── critic-reminder.sh             # Warn if Critic not run before framework commits
│   ├── observation-analysis.sh        # Parse observations, detect patterns, produce summary
│   ├── test-integrity-checker.sh      # [planned Phase 2] Monitor test count, assertion trends
│   ├── doc-architecture-validator.sh  # [planned Phase 2] Enforce tier system, manifest compliance
│   ├── boundary-checker.sh            # [planned Phase 2] Verify architectural boundary respect
│   └── spec-compliance-diff.sh        # [planned Phase 2] Diff specifications against implementation
├── scripts/                           # Eval/validation helper scripts
│   ├── validate-eval-output.sh        # Mechanical validation for evaluation output
│   ├── validate-schema.py             # Validate project-state.yaml against template
│   └── check-artifacts.py             # Check artifact files for frontmatter and structure
├── templates/                         # Starting templates for user project artifacts
│   ├── project-state.yaml             # Master project state (decisions, deps, open questions)
│   ├── eval-result-template.md        # Template for recording evaluation results
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
├── tests/                             # Evaluation rubrics for skill validation
│   └── scenarios/                     # Per-scenario test definitions (Tier 1)
│       ├── family-utility.md          # Phase 1 vertical slice scenario
│       ├── background-data-pipeline.md # Built early (Phase 2 scenario, used for observation testing)
│       ├── consumer-mobile-app.md     # [planned Phase 2]
│       ├── b2b-integration-api.md     # [planned Phase 2]
│       └── two-sided-marketplace.md   # [planned Phase 2]
├── eval-history/                      # Evaluation results (Tier 1, append-only)
│   └── {scenario}-{date}.md           # Per-run results with YAML frontmatter
├── framework-observations/            # Automatic observation capture (Tier 1, append-only)
│   ├── README.md                      # Observation system documentation
│   ├── schema.yaml                    # Observation entry schema
│   └── {date}-{description}.yaml      # Per-session observations
├── docs/                              # This project's own Tier 1 documentation
│   ├── vision.md
│   ├── requirements.md
│   ├── principles.md
│   ├── high-level-design.md
│   ├── evaluation-methodology.md
│   ├── self-improvement-architecture.md # C8 learning system design and philosophy
│   └── doc-manifest.yaml              # Tier 1 doc registry for the framework itself
└── working-notes/                     # Tier 3 ephemeral docs (auto-expire after 2 weeks)
    └── .gitkeep
```

## Framework Development

The rest of this file is for building Prawduct itself — the skills, templates, tools, and docs that make up the framework. If you're here to USE Prawduct to build a product, you don't need any of this; the Orchestrator skill handles it (see "When Someone Opens This Directory" above).

### Getting started on framework development:
1. Read `docs/principles.md` — these are your hard rules. Never violate them.
2. Read `docs/requirements.md` — focus on [v1] tagged items.
3. Read `docs/high-level-design.md` — understand the components and their interactions.
4. Check the V1 Build Order (below) to understand the current phase and what's already been built. Compare it against the actual files in `skills/`, `templates/`, and `tests/scenarios/` to see the current state.
5. To run an evaluation, see `tests/scenarios/` — each scenario has an Evaluation Procedure section with setup, run, and evaluation steps.
6. Apply the framework to itself. Every decision needs rationale. Every artifact needs tests. Documentation follows the tier system.

### After modifying skills, templates, or principles:
Before committing changes to the framework, read `skills/critic/SKILL.md` and apply **Framework Governance mode** to your changes. This catches specificity leaks, broken read-write chains, disproportionate additions, and cross-skill inconsistencies. The Critic is the framework's self-governance mechanism — it enforces the same quality standards the framework applies to user products.

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
6. **C6: Critic — framework governance mode** (`skills/critic/SKILL.md`) — Apply to framework changes before committing. Product governance mode is Phase 2.
7. **C8a: Observation Capture** (`framework-observations/`) — Automatic observation capture at stage transitions and during evaluation. This is minimal C8 (Observer only); pattern detection and incorporation are Phase 2/3.

**Evaluate against the family utility test scenario rubric** (see `docs/high-level-design.md` § "Validation Strategy for Skills"). Phase 1 succeeds when the end-to-end flow produces useful, consistent output from a vague input and automatically captures observations for future pattern detection.

### Phase 2: Widen

- Extend the Critic (C6) with product governance mode (spec compliance, test integrity). Framework governance mode is already in Phase 1.
- Add product shapes one at a time (automation → API → multi-party), evaluating each against its test scenario rubric.
- Add shape-specific artifacts and templates as each shape is added.
- Build mechanical tools (`tools/`).
- Add Orchestrator sophistication (pacing, expertise calibration, pushback).

### Phase 3: Full V1

All v1 requirements, all five test scenarios passing, framework governing its own development.

**C8a (Observation Capture)** is built in Phase 1 to start accumulating data. Full C7 (Trajectory Monitor) and C8 (Learning System with pattern detection, validation, incorporation) are v1.5/v2.

## Testing Strategy for This Project

Since this project is a framework of skills and tools (not a traditional application), testing looks different. See `docs/high-level-design.md` § "Validation Strategy for Skills" for the full approach.

- **Skills:** Test against five defined product scenarios with evaluation rubrics specifying must-do, must-not-do, and quality criteria. "Good" is not a test — specific, observable criteria are. The five scenarios: consumer mobile app, background automation, B2B API, family utility, two-sided marketplace.
- **Mechanical tools:** Standard unit/integration tests. Feed them known-good and known-bad project states and verify correct detection.
- **End-to-end:** Take a product idea from raw input through to build plan using the full framework. Evaluate the build plan against its scenario rubric. The compiler-compiles-itself test: run Prawduct through Prawduct.

### Recording Evaluation Results

Every evaluation run **must** produce a results file in `eval-history/` before the evaluation directory is cleaned up. This is not optional — unrecorded evaluations are wasted work.

**Template:** Use `templates/eval-result-template.md` as the canonical format — it defines the required YAML frontmatter, per-component rubric tables, and the full result file structure. Copy it, fill it in, and save to `eval-history/{scenario-name}-{YYYY-MM-DD}.md`.

**For complete evaluation procedures** (setup, execution, analysis, learning extraction, regression detection), see `docs/evaluation-methodology.md`.

**Observation extraction:** After recording eval results, framework findings are extracted and written to `framework-observations/` as structured observations. This feeds the pattern detection system. See `docs/evaluation-methodology.md` § "Recording Results" step 6 for the extraction procedure.

## Conventions

- **File naming:** lowercase-with-hyphens for all files and directories.
- **Skill format:** Every SKILL.md starts with a one-paragraph purpose statement, then structured instructions.
- **Templates:** Include comments/guidance explaining what goes in each section. Templates are instructional, not just structural.
- **Commit messages:** Describe what changed and why. "Updated orchestrator skill" is not acceptable. "Added pacing sensitivity to orchestrator: system now adapts discovery depth to user patience level (R1.8)" is.
- **Working notes:** Any file in `working-notes/` must include a creation date. Notes older than 2 weeks are stale — incorporate into Tier 1 or delete.
