# CLAUDE.md — Prawduct

## What This Project Is

Prawduct is a framework that turns vague product ideas into well-built software. It does this by guiding structured discovery, producing agent-executable build plans, and enforcing quality throughout development. You (Claude) are its primary runtime — you read these skills and follow their instructions to help users build products.

## When Someone Opens This Directory

**ALWAYS read `skills/orchestrator/SKILL.md` FIRST, before taking any action.** This is not optional. The Orchestrator is your process — it handles session resumption, change classification, governance routing, and the Critic gate. Everything goes through it. A user providing a detailed implementation plan, specific instructions, or saying "just do X" does not bypass the Orchestrator — their input becomes input to the Orchestrator's process, which determines the appropriate governance level. This is HR9 (No Governance Bypass). A mechanical hook enforces this.

After loading the Orchestrator, it will route based on context:

**New product idea** ("I want to build an app that...", "let's make a tool for...", "I have an idea for..."):
→ The Orchestrator sets up a separate project directory. It will not write new product output into an existing project's directory.

**First contact** ("hello", "what is this?", "what can you do?", or any message where the user appears unfamiliar with Prawduct):
→ The Orchestrator provides a brief orientation (see its New User Orientation section), then waits for the user to indicate what they'd like to do.

**Everything else** (framework dev, returning user, "fix the domain analyzer", "what should I work on next?"):
→ The Orchestrator reads `project-state.yaml` at the repo root, performs Session Resumption, and enters Stage 6 iteration for framework development.

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
│   └── review-lenses/SKILL.md         # Five evaluation perspectives (product, design, arch, skeptic, testing)
├── tools/                             # Deterministic scripts (mechanical enforcement)
│   ├── capture-observation.sh         # Create schema-compliant observation files from CLI args
│   ├── record-critic-findings.sh      # Record structured Critic findings for commit gate
│   ├── session-health-check.sh        # Session orientation: patterns, backlog, stale items, infrastructure health
│   ├── update-observation-status.sh   # Observation lifecycle transitions and archiving
│   ├── critic-reminder.sh             # Verify Critic evidence before framework commits
│   ├── observation-analysis.sh        # Parse observations, detect patterns, produce summary
│   ├── test-integrity-checker.sh      # [planned Phase 2] Monitor test count, assertion trends
│   ├── doc-architecture-validator.sh  # [planned Phase 2] Enforce tier system, manifest compliance
│   ├── boundary-checker.sh            # [planned Phase 2] Verify architectural boundary respect
│   ├── spec-compliance-diff.sh        # [planned Phase 2] Diff specifications against implementation
│   └── docs-freshness-checker.sh      # [planned Phase 2] Diff CLAUDE.md tree against disk, check last_validated dates
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
│   ├── human-interface/               # [planned] human_interface concern (screen type)
│   │   ├── information-architecture.md
│   │   ├── screen-spec.md             # Per-screen template (all states)
│   │   ├── design-direction.md
│   │   ├── accessibility-spec.md
│   │   ├── localization-requirements.md
│   │   └── onboarding-spec.md
│   ├── api-surface/                   # [planned] api_surface concern
│   │   ├── api-contract.md            # Per-endpoint template
│   │   ├── integration-guide.md
│   │   ├── versioning-strategy.md
│   │   └── sla-definition.md
│   ├── unattended-operation/          # unattended_operation concern
│   │   ├── pipeline-architecture.md
│   │   ├── scheduling-spec.md
│   │   ├── monitoring-alerting-spec.md
│   │   ├── failure-recovery-spec.md
│   │   └── configuration-spec.md
│   └── multi-party/                   # [planned] multi_party concern
│       ├── party-experience-spec.md   # Per-party template
│       ├── party-interaction-model.md
│       └── migration-adoption-plan.md
├── tests/                             # Evaluation rubrics for skill validation
│   └── scenarios/                     # Per-scenario test definitions (Tier 1)
│       ├── family-utility.md          # Phase 1 vertical slice scenario
│       ├── background-data-pipeline.md # Phase 2 scenario, used for observation testing
│       ├── terminal-arcade-game.md    # Game design scenario, tests creative product handling
│       ├── consumer-mobile-app.md     # [planned Phase 2]
│       ├── b2b-integration-api.md     # [planned Phase 2]
│       └── two-sided-marketplace.md   # [planned Phase 2]
├── eval-history/                      # Evaluation results (Tier 1, append-only)
│   └── {scenario}-{date}.md           # Per-run results with YAML frontmatter
├── framework-observations/            # Automatic observation capture (Tier 1, lifecycle-managed)
│   ├── README.md                      # Observation system documentation
│   ├── schema.yaml                    # Observation entry schema
│   ├── archive/                       # Resolved observations (all statuses terminal)
│   └── {date}-{description}.yaml      # Per-session observations
├── .claude/                           # Claude Code integration (hooks, settings)
│   ├── hooks/
│   │   ├── critic-gate.sh             # PreToolUse hook: blocks commit without structured Critic evidence
│   │   ├── framework-edit-tracker.sh  # PostToolUse hook: tracks edits in .session-edits.json, escalating reminders
│   │   ├── orchestrator-gate.sh       # PreToolUse hook: blocks framework file edits without Orchestrator activation
│   │   ├── product-governance-tracker.sh  # PostToolUse hook: tracks product build governance debt, injects reminders
│   │   ├── product-governance-stop.sh     # Stop hook: blocks completion when critical product governance debt exists
│   │   └── product-governance-prompt.sh   # UserPromptSubmit hook: injects governance status at start of turn
│   ├── settings.json                  # Project-level Claude Code settings
│   └── settings.local.json            # Local overrides (not committed)
├── docs/                              # This project's own Tier 1 documentation
│   ├── vision.md
│   ├── requirements.md
│   ├── principles.md
│   ├── high-level-design.md
│   ├── evaluation-methodology.md
│   ├── self-improvement-architecture.md # C8 learning system design and philosophy
│   ├── skill-authoring-guide.md       # Structural + health standards for LLM skill instructions
│   └── doc-manifest.yaml              # Tier 1 doc registry for the framework itself
└── working-notes/                     # Tier 3 ephemeral docs (auto-expire after 2 weeks)
    └── .gitkeep
```

## Framework Development

Framework development is managed by the Orchestrator. The framework's own `project-state.yaml` at the repo root tracks its state — the framework is a product in Stage 6 (iteration). The Orchestrator handles session resumption, change classification, review, observation capture, and the Critic gate.

The Framework Status section below provides build context. The Key Principles, Testing Strategy, and Conventions sections provide constraints the Orchestrator needs when making framework changes.

### After modifying skills, templates, or principles:
**Critic governance is enforced mechanically.** A Claude Code hook blocks `git commit` when framework files are staged without Critic evidence, and edit hooks remind you as you modify framework files. But don't wait for the gate — run the Critic as a **separate, final step** in any multi-file framework change, not as a sub-step of another work item. The Critic should run after all modifications are complete and before reporting results to the user.

**For directional or multi-file changes (3+ framework files):** Follow the Directional Change Protocol in `skills/orchestrator/SKILL.md`. This requires a written plan, plan-stage Critic review before implementation, per-phase lightweight reviews, and a final full Critic review. The protocol ensures governance is proportionate to change impact — not just a rubber stamp at the end.

To run the Critic: read `skills/critic/SKILL.md` and apply **Framework Governance mode** (all 7 checks) to your changes. This catches specificity leaks, broken read-write chains, disproportionate additions, cross-skill inconsistencies, cumulative skill health drift, and learning system impact. After review, run `tools/record-critic-findings.sh` to record structured findings — the commit gate verifies this file exists with all 7 checks and coverage of all staged files. Include "Framework Governance Review" in the commit message.

## Key Principles (read `docs/principles.md` for the full set)

These are the ones most likely to be violated under pressure:

- **HR1: No Test Corruption.** Never weaken, delete, or comment out tests to make them pass. Fix the code or formally change the spec.
- **HR2: No Silent Requirement Dropping.** If you can't implement something, flag it. Don't skip it.
- **HR3: No Documentation Fiction.** Docs describe reality, not intent.
- **HR5: No Confidence Without Basis.** If you're unsure, say so explicitly.
- **HR6: No Ad Hoc Documentation.** Every doc has a tier, an owner, and a location. No orphans.
- **HR9: No Governance Bypass.** The Orchestrator's governance process is not optional. Detailed plans, direct instructions, or "just do X" requests are input to the process, not replacements for it.

## Framework Status

The framework follows a vertical-slice build approach (see `docs/high-level-design.md` § "Bootstrapping: Vertical Slice Approach"). Core infrastructure is built; deepening remaining product concerns is in progress.

**Built and operational:**
- Full stage pipeline: Stages 0-6 (Intake through Iteration)
- All core skills: Orchestrator, Domain Analyzer, Artifact Generator (Phases A-D), Builder, Critic (framework + product governance), Review Lenses (all five)
- Concern-based classification: human_interface and unattended_operation concerns fully supported with templates; all 7 concerns detectable
- Observation capture system with triage and session resumption integration
- Pattern surfacing: `session-health-check.sh` parses observations, applies tiered thresholds, and surfaces actionable patterns with proposed actions during session resumption; Orchestrator presents patterns to user for act-or-defer decisions
- Mechanical self-improvement tools: `capture-observation.sh` (schema-compliant observation creation), `record-critic-findings.sh` (structured Critic evidence), `session-health-check.sh` (session orientation with actionable pattern surfacing and infrastructure health monitoring), `update-observation-status.sh` (observation lifecycle transitions and archiving)
- Hardened commit gate: verifies structured Critic findings (`.critic-findings.json`) with all 7 checks and staged file coverage, escalating edit tracker with per-file tracking
- Mechanical product build governance: three-layer hook system (PostToolUse tracker, Stop blocker, UserPromptSubmit context) enforces Critic review, FRP, and observation capture during product builds via `.product-session.json` state tracking
- Self-hosted development through the Orchestrator's own Stage 6 process
- Three test scenarios with evaluation rubrics: family-utility, background-data-pipeline, terminal-arcade-game

**Remaining work** (tracked in `project-state.yaml` → `build_plan.remaining_work`):
- **v1-widen (15 items):** Deepen api_surface and multi_party concerns with templates and scenarios; create human_interface templates; Orchestrator sophistication (pushback, prior art, pacing, reclassification); Critic sub-components and Review Lenses integration; Builder multi-concern patterns; mechanical sub-check tools; consumer-mobile-app scenario
- **v1-validation (3 items):** Full V1 validation (all scenarios end-to-end); Builder parallel execution and incremental builds
- **v1.5 (5 items):** C7 Trajectory Monitor; regulatory discovery; cost awareness; accessibility enforcement; agent agnosticism

**C8 (Learning System):** Observation Capture (C8a) is active with mechanical tooling and lifecycle management (status transitions, archiving). Pattern Detection (C8b) is partially built — mechanical detection with tiered thresholds surfaces actionable patterns during session resumption; infrastructure health monitoring detects accumulation, staleness, and archive backlog. Incorporation (C8c-e) is partially built — human-approved incorporation via session resumption act-or-defer decisions, with approved changes following normal Critic governance. Full automated incorporation remains v2 scope.

## Testing Strategy for This Project

Since this project is a framework of skills and tools (not a traditional application), testing looks different. See `docs/high-level-design.md` § "Validation Strategy for Skills" for the full approach.

- **Skills:** Test against product scenarios with evaluation rubrics specifying must-do, must-not-do, and quality criteria. "Good" is not a test — specific, observable criteria are. Three scenarios implemented: family utility, background data pipeline, terminal arcade game. Three planned: consumer mobile app, B2B integration API, two-sided marketplace.
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
- **Documentation freshness:** When creating a new file in the framework (skill, template, doc, tool, test scenario), update CLAUDE.md's project structure tree in the same session. When changing a component's capabilities, verify its description in CLAUDE.md still matches. When a milestone completes (phase finished, major feature shipped), check whether CLAUDE.md contains planning artifacts that should be converted to status descriptions — roadmaps become stale silently because the content stays true long enough that nobody questions it. The FRP's Documentation Freshness dimension catches both inaccuracy and obsolescence, but prevention is cheaper than detection.
