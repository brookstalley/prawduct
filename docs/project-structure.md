# Framework Repository Structure

Tier: 3 (Reference)
Owner: CLAUDE.md

The framework repo (self-hosted) uses the same `.prawduct/` layout as product repos:

```
prawduct/
├── README.md                          # Human-facing project overview and getting started
├── CLAUDE.md                          # Agent instructions (always loaded)
├── requirements.txt                   # Python dependencies (pyyaml)
├── .prawduct/                         # Product specifications (WHAT/HOW — downstream from docs/)
│   ├── project-state.yaml             # Framework's own project state (core; pointers to split files)
│   ├── project-definition.yaml        # Split: classification, product_definition, technical/design decisions
│   ├── artifact-manifest.yaml         # Split: full artifact manifest with dependency graph
│   ├── observation-backlog-deferred.yaml # Split: deferred observation backlog items
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
├── tools/                             # Deterministic scripts (mechanical enforcement, 14 files)
│   ├── prawduct-init.{sh,py}         # Project setup, repair, settings.json merging, gitignore management
│   ├── prawduct-statusline.py         # Claude Code statusline: stage, governance alerts, context bar, git
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
    ├── project-structure.md           # This file — framework repo layout reference
    └── doc-manifest.yaml              # Tier 1 doc registry for the framework itself
```
