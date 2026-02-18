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
├── .prawduct/                         # Product specifications (WHAT/HOW — downstream from docs/)
│   ├── project-state.yaml             # Framework's own project state
│   ├── hooks/                         # Governance hook scripts (6 hooks)
│   │   ├── critic-gate.sh             # PreToolUse hook: blocks commit without structured Critic evidence
│   │   ├── governance-gate.sh         # PreToolUse hook: blocks skill/template reads and governed edits without Orchestrator activation; blocks edits with chunk review debt
│   │   ├── governance-tracker.sh      # PostToolUse hook: silently tracks edits in .session-governance.json
│   │   ├── governance-prompt.sh       # UserPromptSubmit hook: enforces Orchestrator activation (HR9)
│   │   ├── governance-stop.sh         # Stop hook: blocks completion when critical governance debt exists (incl. observation capture)
│   │   └── compact-governance-reinject.sh # SessionStart hook (compact): re-injects governance instructions after compaction
│   ├── artifacts/                     # 14 product specs (see doc-manifest.yaml); derived from docs/ + discovery
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
├── tools/                             # Deterministic scripts (mechanical enforcement, 13 files)
│   ├── prawduct-init.{sh,py}         # Project setup, repair, settings.json merging, gitignore management
│   ├── session-health-check.sh        # Session orientation: patterns, backlog, divergence, health
│   ├── compact-project-state.{sh,py}  # Mechanical compaction of growing project-state.yaml sections
│   ├── contribute-observations.sh     # Check/format/submit product observations to framework repo
│   └── ...                            # Observation lifecycle, Critic evidence, product root detection
├── scripts/                           # Eval/validation helpers (validate-eval-output, validate-schema, check-artifacts)
├── templates/                         # Starting templates for user project artifacts
│   ├── project-state.yaml, build-plan.md, + 9 artifact templates  # Core templates
│   ├── human-interface/               # has_human_interface templates (6 files)
│   └── unattended-operation/          # runs_unattended templates (5 files)
├── tests/                             # Evaluation rubrics for skill validation
│   └── scenarios/                     # 3 scenarios: family-utility, background-data-pipeline, terminal-arcade-game
├── eval-history/                      # Evaluation results (Tier 1, append-only)
│   └── {scenario}-{date}.md           # Per-run results with YAML frontmatter
├── .claude/                           # Claude Code integration (settings only)
│   ├── settings.json                  # Project-level Claude Code settings (hooks point to .prawduct/hooks/)
│   └── settings.local.json            # Local overrides (not committed)
└── docs/                              # Design documents (WHY — upstream, Tier 1; see high-level-design.md § Documentation Architecture)
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

The framework follows a vertical-slice build approach (see `docs/high-level-design.md` § "Bootstrapping: Vertical Slice Approach"). The framework is self-hosted in Stage 6 (iteration).

**Built:** Full stage pipeline (Stages 0-6), all 6 core skills, product output isolation (`.prawduct/`), two-layer classification (5 structural characteristics + dynamic domain depth), three-layer artifact generation, observation capture with pattern surfacing, unified mechanical governance (6 hooks), 3 test scenarios. C8 Learning System: capture active, pattern detection partially built, automated incorporation v2 scope. See `project-state.yaml` for detailed capability tracking.

**Remaining work** (tracked in `project-state.yaml` → `build_plan.remaining_work`):
- **v1-widen (7):** Orchestrator sophistication (prior art, pacing, reclassification); Critic-Review Lenses integration; consumer-mobile-app scenario; Artifact Generator modular updates
- **v1-validation (3):** Full V1 validation; Builder parallel execution and incremental builds
- **v1-new (2):** Agent verification loops (MCP for web UI; Bash for terminal/API)
- **v1.5 (5):** C7 Trajectory Monitor; regulatory discovery; cost awareness; accessibility enforcement; agent agnosticism

## Testing Strategy for This Project

Since this project is a framework of skills and tools (not a traditional application), testing looks different. See `docs/high-level-design.md` § "Validation Strategy for Skills" for the full approach.

- **Skills:** Test against product scenarios with evaluation rubrics specifying must-do, must-not-do, and quality criteria. "Good" is not a test — specific, observable criteria are. Three scenarios implemented: family utility, background data pipeline, terminal arcade game. Three planned: consumer mobile app, B2B integration API, two-sided marketplace.
- **Mechanical tools:** Standard unit/integration tests. Feed them known-good and known-bad project states and verify correct detection.
- **End-to-end:** Take a product idea from raw input through to build plan using the full framework. Evaluate the build plan against its scenario rubric. The compiler-compiles-itself test: run Prawduct through Prawduct.

**Recording results and procedures:** See `docs/evaluation-methodology.md` and `templates/eval-result-template.md`.

## Conventions

- **File naming:** lowercase-with-hyphens for all files and directories.
- **Skill format:** Every SKILL.md starts with a one-paragraph purpose statement, then structured instructions.
- **Templates:** Include comments/guidance explaining what goes in each section. Templates are instructional, not just structural.
- **Commit messages:** Describe what changed and why. "Updated orchestrator skill" is not acceptable. "Added pacing sensitivity to orchestrator: system now adapts discovery depth to user patience level (R1.8)" is.
- **Working notes:** Any file in `working-notes/` must include a creation date. Notes older than 2 weeks are stale — incorporate into Tier 1 or delete.
- **Documentation freshness:** When creating a new file in the framework (skill, template, doc, tool, test scenario), update CLAUDE.md's project structure tree in the same session. When changing a component's capabilities, verify its description in CLAUDE.md still matches. When vocabulary or structural layout changes (directional changes), also verify README.md — it describes capabilities to humans and drifts silently because the framework doesn't read it during normal operation. When a milestone completes (phase finished, major feature shipped), check whether CLAUDE.md contains planning artifacts that should be converted to status descriptions — roadmaps become stale silently because the content stays true long enough that nobody questions it. The FRP's Documentation Freshness dimension catches both inaccuracy and obsolescence, but prevention is cheaper than detection.
