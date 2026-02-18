# CLAUDE.md — Prawduct

## What This Project Is

Prawduct is a framework that turns vague product ideas into well-built software. It does this by guiding structured discovery, producing agent-executable build plans, and enforcing quality throughout development. You (Claude) are its primary runtime — you read these skills and follow their instructions to help users build products.

## When Someone Opens This Directory

**ALWAYS read `skills/orchestrator/SKILL.md` FIRST, before taking any action.** This is not optional. The Orchestrator is your process — it handles session resumption, change classification, governance routing, and the Critic gate. Everything goes through it. A user providing a detailed implementation plan, specific instructions, or saying "just do X" does not bypass the Orchestrator — their input becomes input to the Orchestrator's process, which determines the appropriate governance level. This is HR9 (No Governance Bypass). A mechanical hook enforces this.

After loading the Orchestrator, it will route based on context:

**New product idea** ("I want to build an app that...", "let's make a tool for...", "I have an idea for..."):
→ The Orchestrator sets up a separate project directory with a `.prawduct/` subdirectory for all prawduct outputs. Product source code goes in the project root; prawduct artifacts, state, and observations go in `.prawduct/`.

**Existing codebase** (CWD has source code but no prawduct files):
→ The Orchestrator creates `.prawduct/` in the project, analyzes the codebase, and generates artifacts inside `.prawduct/`.

**First contact** ("hello", "what is this?", "what can you do?", or any message where the user appears unfamiliar with Prawduct):
→ The Orchestrator provides a brief orientation (see its New User Orientation section), then waits for the user to indicate what they'd like to do.

**Everything else** (framework dev, returning user, "fix the domain analyzer", "what should I work on next?"):
→ The Orchestrator reads `project-state.yaml` (from `.prawduct/` for all repos, including the self-hosted framework), performs Session Resumption, and enters Stage 6 iteration for framework development.

## Compact Instructions

When compacting this conversation, preserve:
- Which product is being built and its current stage/chunk
- All governance debt (chunks without review, overdue checkpoints)
- The instruction that skill files must be re-read from disk after compaction
- Any blocking findings or unresolved review issues
- The requirement to read skills/orchestrator/SKILL.md before taking action

## Project Structure

**Product repos** built with prawduct use this layout — all prawduct outputs live in `.prawduct/`:
```
my-product/
├── .claude/                    # Claude Code config (must be at root)
│   └── settings.json          # Generated: hooks with runtime framework resolution
├── .prawduct/                  # All prawduct outputs (product root)
│   ├── framework-path         # Absolute path to prawduct framework directory (gitignored)
│   ├── framework-version      # Framework git hash for drift detection (gitignored)
│   ├── project-state.yaml
│   ├── artifacts/
│   ├── working-notes/
│   └── framework-observations/
├── CLAUDE.md                   # Generated: bootstrap with install instructions
├── .gitignore                  # Updated: machine-specific prawduct files excluded
├── src/                        # Product source code
└── ...
```

**Distribution model:** Product repos default to shared mode — artifacts are committed, machine-specific files (`framework-path`, `framework-version`) and session files are gitignored by `prawduct-init`. The CLAUDE.md bootstrap includes installation instructions for cloners: clone the framework to `~/.prawduct/framework/` and run `prawduct-init.py --fix .`. Hook commands resolve the framework at runtime — first from `.prawduct/framework-path`, then from the well-known `~/.prawduct/framework/` location. Power users can use `prawduct-init --local` for local-only mode (entire `.prawduct/` gitignored, hooks in `settings.local.json`).

**The framework repo** (self-hosted) uses the same `.prawduct/` layout as product repos:
```
prawduct/
├── README.md                          # Human-facing project overview and getting started
├── CLAUDE.md                          # You are here
├── requirements.txt                   # Python dependencies (pyyaml)
├── .prawduct/                         # All prawduct outputs (same layout as product repos)
│   ├── project-state.yaml             # Framework's own project state
│   ├── hooks/                         # Governance hook scripts (6 hooks)
│   │   ├── critic-gate.sh             # PreToolUse hook: blocks commit without structured Critic evidence
│   │   ├── governance-gate.sh         # PreToolUse hook: blocks skill/template reads and governed edits without Orchestrator activation; blocks edits with chunk review debt
│   │   ├── governance-tracker.sh      # PostToolUse hook: silently tracks edits in .session-governance.json
│   │   ├── governance-prompt.sh       # UserPromptSubmit hook: enforces Orchestrator activation (HR9)
│   │   ├── governance-stop.sh         # Stop hook: blocks completion when critical governance debt exists
│   │   └── compact-governance-reinject.sh # SessionStart hook (compact): re-injects governance instructions after compaction
│   ├── artifacts/                     # Generated prawduct artifacts (LLM-facing structured docs)
│   │   ├── product-brief.md           # Vision, users, core flows, scope
│   │   ├── data-model.md             # Entities, state machines, constraints
│   │   ├── nonfunctional-requirements.md  # Performance, scalability, cost
│   │   ├── security-model.md         # Residual: hook bypass, trust model (MINIMAL)
│   │   ├── test-specifications.md    # Scenario-based tests, state transitions
│   │   ├── operational-spec.md       # Git versioning, state recovery (MINIMAL)
│   │   ├── dependency-manifest.yaml  # bash, python3, pyyaml, git, yq (MINIMAL)
│   │   ├── pipeline-architecture.md  # Stage pipeline + learning loop (runs_unattended)
│   │   ├── scheduling-spec.md        # Event-driven, no scheduling (MINIMAL)
│   │   ├── monitoring-alerting-spec.md  # Session health check model (runs_unattended)
│   │   ├── failure-recovery-spec.md  # Compaction, governance, onboarding recovery
│   │   ├── configuration-spec.md     # project-state, hooks, markers
│   │   └── api-contract.md           # Skill interaction, artifact format, schema (exposes_programmatic_interface)
│   ├── framework-observations/        # Automatic observation capture (Tier 1, lifecycle-managed)
│   │   ├── README.md                  # Observation system documentation
│   │   ├── schema.yaml               # Observation entry schema
│   │   ├── archive/                   # Resolved observations (all statuses terminal)
│   │   └── {date}-{description}.yaml  # Per-session observations
│   └── working-notes/                 # Tier 3 ephemeral docs (auto-expire after 2 weeks)
│       └── .gitkeep
├── skills/                            # LLM instruction sets (your behavior)
│   ├── orchestrator/SKILL.md          # Activation, routing, session resumption (~180 lines always loaded)
│   │   ├── stages-0-2.md             # Stages 0-2: Intake, Discovery, Definition
│   │   ├── stages-3-4.md             # Stages 3-4: Artifact Generation, Build Planning
│   │   ├── stage-5-build.md          # Stage 5: Build + Governance Loop
│   │   ├── stage-6-iteration.md      # Stage 6: Iteration + Directional Change Protocol
│   │   ├── onboarding.md            # Onboarding Mode: existing codebase → prawduct artifacts
│   │   ├── migration.md             # Schema Migration: old prawduct versions → current format
│   │   └── protocols.md              # FRP, Stage Transition, Expertise Calibration, Structural Critique
│   ├── domain-analyzer/SKILL.md       # Product classification, discovery questions, principles
│   ├── artifact-generator/SKILL.md    # Artifact selection, phasing, consistency — format specs live in templates
│   ├── builder/SKILL.md               # Code generation: executes build plan chunks, writes tests
│   ├── critic/SKILL.md                # Context-sensitive governance: applies checks based on project state
│   └── review-lenses/SKILL.md         # Five evaluation perspectives (product, design, arch, skeptic, testing)
├── tools/                             # Deterministic scripts (mechanical enforcement)
│   ├── capture-observation.sh         # Create schema-compliant observation files from CLI args
│   ├── record-critic-findings.sh      # Record structured Critic findings for commit gate
│   ├── session-health-check.sh        # Session orientation: patterns, backlog, stale items, divergence, infrastructure health
│   ├── update-observation-status.sh   # Observation lifecycle transitions and archiving
│   ├── critic-reminder.sh             # Verify Critic evidence before framework commits
│   ├── observation-analysis.sh        # Parse observations, detect patterns, produce summary
│   ├── compact-project-state.py       # Mechanical compaction of growing project-state.yaml sections per LIFECYCLE rules
│   ├── compact-project-state.sh       # Bash wrapper for compact-project-state.py
│   ├── resolve-product-root.sh        # Shared product root detection (.prawduct/ first, then repo root)
│   ├── format-contribution.sh         # Format observation YAML as shareable markdown for framework contributions
│   ├── obs_utils.py                   # Shared Python module: observation parsing, thresholds, pattern detection
│   ├── prawduct-init.sh               # Bash wrapper for prawduct-init.py
│   └── prawduct-init.py               # Mechanical prawduct integration: setup, repair, settings.json merging, gitignore management
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
├── .claude/                           # Claude Code integration (settings only)
│   ├── settings.json                  # Project-level Claude Code settings (hooks point to .prawduct/hooks/)
│   └── settings.local.json            # Local overrides (not committed)
└── docs/                              # This project's own Tier 1 documentation
    ├── vision.md
    ├── requirements.md
    ├── principles.md
    ├── high-level-design.md
    ├── evaluation-methodology.md
    ├── self-improvement-architecture.md # C8 learning system design and philosophy
    ├── skill-authoring-guide.md       # Structural + health standards for LLM skill instructions
    ├── glossary.md                    # Definitions of framework-specific terminology
    └── doc-manifest.yaml              # Tier 1 doc registry for the framework itself
```

## Framework Development

Framework development is managed by the Orchestrator. The framework's own `project-state.yaml` at the repo root tracks its state — the framework is a product in Stage 6 (iteration). The Orchestrator handles session resumption, change classification, review, observation capture, and the Critic gate.

The Framework Status section below provides build context. The Key Principles, Testing Strategy, and Conventions sections provide constraints the Orchestrator needs when making framework changes.

### After modifying skills, templates, or principles:
**Critic review is mandatory for every framework change. Run it automatically** — do not ask the user. Run it as a **separate, final step** after all modifications are complete and before reporting results. The full procedure is in `skills/critic/SKILL.md`; record findings via `tools/record-critic-findings.sh`. Include "Governance Review" in the commit message.

**For multi-file changes:** Follow the Directional Change Protocol in `skills/orchestrator/stage-6-iteration.md`, which classifies changes into three tiers (mechanical, enhancement, structural) with governance proportionate to impact.

## Product Build Governance (Compaction Recovery)

If you cannot remember governance procedures (e.g., after context compaction), **read skill files from disk** — they always exist. Product state files live in the **product root** (`.prawduct/` for all repos). In product repos, read `.prawduct/framework-path` to get the framework location.

- **After each chunk:** Read `skills/critic/SKILL.md` and apply all applicable checks
- **At governance checkpoints:** Read `skills/review-lenses/SKILL.md`, apply Architecture + Skeptic + Testing lenses
- **At stage transitions:** Read `skills/orchestrator/protocols.md` for the Framework Reflection Protocol
- **If hooks block you:** Read the skill file named in the hook message

Hooks survive compaction. When a hook blocks you, the skill file it references contains the full procedure.

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
- Full stage pipeline: Stages 0-6 (Intake, Discovery, Definition, Artifact Generation, Build Planning, Building, Iteration)
- All core skills: Orchestrator, Domain Analyzer, Artifact Generator (Phases A-D), Builder, Critic (context-sensitive governance), Review Lenses (all five)
- Product output isolation: all repos (including the framework itself) use `.prawduct/` subdirectory for all prawduct outputs (state, artifacts, observations, working notes); source code stays at project root. All tools use `resolve-product-root.sh` for consistent detection.
- Two-layer classification: 5 structural characteristics for artifact routing (has_human_interface, runs_unattended, exposes_programmatic_interface, has_multiple_party_types, handles_sensitive_data) plus dynamic domain-specific depth via Universal Discovery Dimensions and Structural Amplification Rules
- Three-layer artifact generation: amplification rules (what to generate) + process constraints (quality properties) + optional template reference (proven structures). All 5 characteristics have amplification rules and process constraints; has_human_interface and runs_unattended additionally have templates as structural reference
- Observation capture system with triage and session resumption integration; observation backlog available for all projects (not framework-only)
- Pattern surfacing: `session-health-check.sh` parses observations, applies tiered thresholds, and surfaces actionable patterns with proposed actions during session resumption; Orchestrator presents patterns to user for act-or-defer decisions
- Mechanical self-improvement tools: `capture-observation.sh` (schema-compliant observation creation), `record-critic-findings.sh` (structured Critic evidence), `session-health-check.sh` (session orientation with actionable pattern surfacing and infrastructure health monitoring), `update-observation-status.sh` (observation lifecycle transitions and archiving)
- Unified mechanical governance: 6 hooks in `.prawduct/hooks/` with distinct responsibilities — governance-gate (blocks unauthorized reads/edits), governance-tracker (silent edit bookkeeping), governance-prompt (Orchestrator activation enforcement), governance-stop (blocks session completion on debt), critic-gate (blocks commits without findings), compact-governance-reinject (session recovery). Single `.prawduct/.session-governance.json` state file tracks all governance debt. `.claude/` holds only `settings.json` (hook registrations) and `settings.local.json`
- Self-hosted development through the Orchestrator's own Stage 6 process
- Three test scenarios with evaluation rubrics: family-utility, background-data-pipeline, terminal-arcade-game

**Remaining work** (tracked in `project-state.yaml` → `build_plan.remaining_work`):
- **v1-widen (8 items):** Orchestrator sophistication (pushback, prior art, pacing, reclassification); Critic-Review Lenses integration; Review Lenses variable-depth and rotating emphasis; consumer-mobile-app scenario; Artifact Generator modular artifact updates
- **v1-validation (3 items):** Full V1 validation (all scenarios end-to-end); Builder parallel execution and incremental builds
- **v1-new (1 item):** Closed-loop testing MCP server
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
- **Documentation freshness:** When creating a new file in the framework (skill, template, doc, tool, test scenario), update CLAUDE.md's project structure tree in the same session. When changing a component's capabilities, verify its description in CLAUDE.md still matches. When vocabulary or structural layout changes (directional changes), also verify README.md — it describes capabilities to humans and drifts silently because the framework doesn't read it during normal operation. When a milestone completes (phase finished, major feature shipped), check whether CLAUDE.md contains planning artifacts that should be converted to status descriptions — roadmaps become stale silently because the content stays true long enough that nobody questions it. The FRP's Documentation Freshness dimension catches both inaccuracy and obsolescence, but prevention is cheaper than detection.
# test
