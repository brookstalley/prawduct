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

## Compact Instructions

When compacting this conversation, preserve:
- Which product is being built and its current stage/chunk
- All governance debt (chunks without review, overdue checkpoints)
- The instruction that skill files must be re-read from disk after compaction
- Any blocking findings or unresolved review issues
- The requirement to read skills/orchestrator/SKILL.md before taking action

## Project Structure

```
prawduct/
├── README.md                          # Human-facing project overview and getting started
├── CLAUDE.md                          # You are here
├── project-state.yaml                 # Framework's own project state (self-hosted)
├── skills/                            # LLM instruction sets (your behavior)
│   ├── orchestrator/SKILL.md          # Conversation flow, stage management, user calibration
│   ├── domain-analyzer/SKILL.md       # Product classification, discovery questions, principles
│   ├── artifact-generator/SKILL.md    # Artifact selection, phasing, consistency — format specs live in templates
│   ├── builder/SKILL.md               # Code generation: executes build plan chunks, writes tests
│   ├── critic/SKILL.md                # Context-sensitive governance: applies checks based on project state
│   └── review-lenses/SKILL.md         # Five evaluation perspectives (product, design, arch, skeptic, testing)
├── tools/                             # Deterministic scripts (mechanical enforcement)
│   ├── capture-observation.sh         # Create schema-compliant observation files from CLI args
│   ├── record-critic-findings.sh      # Record structured Critic findings for commit gate
│   ├── session-health-check.sh        # Session orientation: patterns, backlog, stale items, infrastructure health
│   ├── update-observation-status.sh   # Observation lifecycle transitions and archiving
│   ├── critic-reminder.sh             # Verify Critic evidence before framework commits
│   ├── observation-analysis.sh        # Parse observations, detect patterns, produce summary
│   ├── compact-project-state.py       # Mechanical compaction of growing project-state.yaml sections per LIFECYCLE rules
│   └── compact-project-state.sh       # Bash wrapper for compact-project-state.py
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
│   ├── human-interface/               # has_human_interface structural characteristic (modality: screen)
│   │   ├── information-architecture.md
│   │   ├── screen-spec.md             # Per-screen template (all states)
│   │   ├── design-direction.md
│   │   ├── accessibility-spec.md
│   │   ├── localization-requirements.md
│   │   └── onboarding-spec.md
│   └── unattended-operation/          # runs_unattended structural characteristic
│       ├── pipeline-architecture.md
│       ├── scheduling-spec.md
│       ├── monitoring-alerting-spec.md
│       ├── failure-recovery-spec.md
│       └── configuration-spec.md
├── tests/                             # Evaluation rubrics for skill validation
│   └── scenarios/                     # Per-scenario test definitions (Tier 1)
│       ├── family-utility.md          # Phase 1 vertical slice scenario
│       ├── background-data-pipeline.md # Phase 2 scenario, used for observation testing
│       └── terminal-arcade-game.md    # Game design scenario, tests creative product handling
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
│   │   ├── governance-gate.sh         # PreToolUse hook: blocks edits without Orchestrator activation or with chunk review debt
│   │   ├── governance-tracker.sh      # PostToolUse hook: tracks all edits and governance debt in .session-governance.json
│   │   ├── governance-prompt.sh       # UserPromptSubmit hook: injects governance status at start of turn
│   │   ├── governance-stop.sh         # Stop hook: blocks completion when critical governance debt exists
│   │   └── compact-governance-reinject.sh # SessionStart hook (compact): re-injects governance instructions after compaction
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
**Framework Critic review is mandatory for every framework change. Run it automatically.** Do not ask the user whether to run it. A Claude Code hook blocks `git commit` when framework files are staged without Critic evidence, a Stop hook blocks session completion when framework edits lack Critic review, and a UserPromptSubmit hook injects governance reminders. But don't wait for the gates — run the Critic as a **separate, final step** in every framework change regardless of file count, not as a sub-step of another work item. Run the Critic automatically after all modifications are complete and before reporting results to the user.

**For directional or multi-file changes (3+ framework files):** Follow the Directional Change Protocol in `skills/orchestrator/SKILL.md`. This requires a written plan, plan-stage Critic review before implementation, per-phase lightweight reviews, and a final full Critic review. The protocol ensures governance is proportionate to change impact — not just a rubber stamp at the end.

To run the Critic: read `skills/critic/SKILL.md` and apply all applicable checks to your changes. The Critic determines which checks apply from context — always at least Scope Discipline, Proportionality, Coherence, and Learning/Observability; plus Generality, Instruction Clarity, and Cumulative Health for skill/template changes. After review, run `tools/record-critic-findings.sh` to record structured findings — the commit gate verifies this file exists with at least 6 checks and coverage of all staged files. Include "Governance Review" in the commit message.

## Product Build Governance (Compaction Recovery)

If you are building a product and cannot remember governance procedures (e.g., after context compaction), follow these steps. **Skill files are always on disk — read them.**

1. **After each chunk:** Read `skills/critic/SKILL.md` from disk and apply all applicable checks (Spec Compliance, Test Integrity, Scope Discipline, and others based on context)
2. **Record findings:** Add review entry to the product's `project-state.yaml` → `build_state.reviews`
3. **Clear debt:** Update `.claude/.session-governance.json` → `governance_state.chunks_completed_without_review` to 0
4. **At governance checkpoints:** Read `skills/review-lenses/SKILL.md` from disk, apply Architecture + Skeptic + Testing lenses
5. **At stage transitions:** Read `skills/orchestrator/SKILL.md` from disk and run the Framework Reflection Protocol
6. **If hooks block your edits:** The hook message tells you which skill file to read. Read it from disk and follow its instructions.

Hooks survive compaction but `additionalContext` does not. When a hook blocks or reminds you, it means governance procedures are needed — the skill files contain the full procedures.

## Key Principles (read `docs/principles.md` for the full set)

These are the ones most likely to be violated under pressure:

- **HR1: No Test Corruption.** Never weaken, delete, or comment out tests to make them pass. Fix the code or formally change the spec.
- **HR2: No Silent Requirement Dropping.** If you can't implement something, flag it. Don't skip it.
- **HR3: No Documentation Fiction.** Docs describe reality, not intent.
- **HR5: No Confidence Without Basis.** If you're unsure, say so explicitly.
- **HR6: No Ad Hoc Documentation.** Every doc has a tier, an owner, and a location. No orphans.
- **HR9: No Governance Bypass.** The Orchestrator's governance process is not optional. Detailed plans, direct instructions, or "just do X" requests are input to the process, not replacements for it.

## Framework Status

The framework follows a vertical-slice build approach (see `docs/high-level-design.md` § "Bootstrapping: Vertical Slice Approach"). Core infrastructure is built; structural characteristics cover artifact routing and dynamic domain depth provides domain-specific discovery.

**Built and operational:**
- Full stage pipeline: Stages 0-6 (Intake through Iteration)
- All core skills: Orchestrator, Domain Analyzer, Artifact Generator (Phases A-D), Builder, Critic (context-sensitive governance), Review Lenses (all five)
- Two-layer classification: 5 structural characteristics for artifact routing (has_human_interface, runs_unattended, exposes_programmatic_interface, has_multiple_party_types, handles_sensitive_data) plus dynamic domain-specific depth via Universal Discovery Dimensions and Structural Amplification Rules; has_human_interface and runs_unattended fully supported with templates
- Observation capture system with triage and session resumption integration; observation backlog available for all projects (not framework-only)
- Pattern surfacing: `session-health-check.sh` parses observations, applies tiered thresholds, and surfaces actionable patterns with proposed actions during session resumption; Orchestrator presents patterns to user for act-or-defer decisions
- Mechanical self-improvement tools: `capture-observation.sh` (schema-compliant observation creation), `record-critic-findings.sh` (structured Critic evidence), `session-health-check.sh` (session orientation with actionable pattern surfacing and infrastructure health monitoring), `update-observation-status.sh` (observation lifecycle transitions and archiving)
- Unified mechanical governance: 5 hooks (governance-gate, governance-tracker, governance-prompt, governance-stop, critic-gate) plus compact-governance-reinject for session recovery. Single `.session-governance.json` state file tracks both framework edits and product governance debt. Commit gate verifies structured Critic findings (`.critic-findings.json`) with at least 6 applicable checks and staged file coverage
- Self-hosted development through the Orchestrator's own Stage 6 process
- Three test scenarios with evaluation rubrics: family-utility, background-data-pipeline, terminal-arcade-game

**Remaining work** (tracked in `project-state.yaml` → `build_plan.remaining_work`):
- **v1-widen (13 items):** Create exposes_programmatic_interface and has_multiple_party_types templates; Orchestrator sophistication (pushback, prior art, pacing, reclassification); Critic sub-components and Review Lenses integration; Builder structural-characteristic chunk patterns; mechanical sub-check tools; consumer-mobile-app scenario; modular artifact updates
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
