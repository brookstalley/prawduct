# CLAUDE.md — Prawduct

## What This Project Is

Prawduct is a framework that turns vague product ideas into well-built software. It does this by guiding structured discovery, producing agent-executable build plans, and enforcing quality throughout development. You (Claude) are its primary runtime — you read these skills and follow their instructions to help users build products.

## When Someone Opens This Directory

Route based on what the user says:

**They describe a NEW product idea** ("I want to build an app that...", "let's make a tool for...", "I have an idea for..."):
→ They want to USE Prawduct to build something new. Read `skills/orchestrator/SKILL.md` and follow its instructions. The Orchestrator will set up a separate project directory for their files. It will not write new product output into an existing project's directory.

**Everything else** (framework dev, unclear intent, returning user, "fix the domain analyzer", "what should I work on next?", "hello", "what can you do?"):
→ Read `skills/orchestrator/SKILL.md` and follow its instructions. The Orchestrator reads `project-state.yaml` at the repo root, performs Session Resumption, and enters Stage 6 iteration for framework development. For unclear intent, the Orchestrator naturally handles orientation — it sees the framework's project state and can explain what Prawduct does and what's in progress.

## Project Structure

```
prawduct/
├── CLAUDE.md                          # You are here
├── project-state.yaml                 # Framework's own project state (self-hosted)
├── skills/                            # LLM instruction sets (your behavior)
│   ├── orchestrator/SKILL.md          # Conversation flow, stage management, user calibration
│   ├── domain-analyzer/SKILL.md       # Product classification, discovery questions, principles
│   ├── artifact-generator/SKILL.md    # How to produce each artifact type, format specs
│   ├── builder/SKILL.md               # Code generation: executes build plan chunks, writes tests
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
│   ├── build-plan.md                  # Template: concrete build instructions, chunking, scaffolding
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

Framework development is managed by the Orchestrator. The framework's own `project-state.yaml` at the repo root tracks its state — the framework is a product in Stage 6 (iteration). The Orchestrator handles session resumption, change classification, review, observation capture, and the Critic gate.

The V1 Build Order below provides build phase context. The Key Principles, Testing Strategy, and Conventions sections provide constraints the Orchestrator needs when making framework changes.

### After modifying skills, templates, or principles:
**Critic governance is enforced mechanically.** A Claude Code hook blocks `git commit` when framework files are staged without Critic evidence, and edit hooks remind you as you modify framework files. But don't wait for the gate — run the Critic as a **separate, final step** in any multi-file framework change, not as a sub-step of another work item. The Critic should run after all modifications are complete and before reporting results to the user.

To run the Critic: read `skills/critic/SKILL.md` and apply **Framework Governance mode** (all 6 checks) to your changes. This catches specificity leaks, broken read-write chains, disproportionate additions, cross-skill inconsistencies, and cumulative skill health drift. Include "Framework Governance Review" in the commit message so the gate recognizes it.

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
5. **C4: Review Lenses** (`skills/review-lenses/SKILL.md`) — Apply all five lenses to the generated artifacts (Testing Lens activates in Phase C).
6. **C6: Critic — framework governance mode** (`skills/critic/SKILL.md`) — Apply to framework changes before committing. Product governance mode is Phase 2.
7. **C8a: Observation Capture** (`framework-observations/`) — Automatic observation capture at stage transitions and during evaluation. This is minimal C8 (Observer only); pattern detection and incorporation are Phase 2/3.

**Evaluate against the family utility test scenario rubric** (see `docs/high-level-design.md` § "Validation Strategy for Skills"). Phase 1 succeeds when the end-to-end flow produces useful, consistent output from a vague input and automatically captures observations for future pattern detection.

### Phase 2: Widen

- [x] Extend the Critic (C6) with product governance mode (spec compliance, test integrity, scope violation).
- [x] Add Builder skill (C3b) for code generation from build plans.
- [x] Extend Artifact Generator with Phase D (build planning) and build-plan template.
- [x] Extend Orchestrator with Stages 4 (Build Planning), 5 (Build + Governance Loop), 6 (Iteration).
- [x] Extend observation system for build-phase observation types.
- [x] Extend family utility eval rubric for Stages 4-6.
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
