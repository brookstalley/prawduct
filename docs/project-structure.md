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
│   ├── artifacts/                     # 14 product specs (see doc-manifest.yaml); derived from docs/ + discovery
│   ├── framework-observations/        # Automatic observation capture (Tier 1, lifecycle-managed)
│   │   ├── README.md                  # Observation system documentation
│   │   ├── schema.yaml               # Observation entry schema
│   │   ├── archive/                   # Resolved observations (all statuses terminal)
│   │   └── {date}-{description}.yaml  # Per-session observations
│   └── working-notes/                 # Tier 3 ephemeral docs (auto-expire after 2 weeks)
│       └── .gitkeep
├── skills/                            # LLM instruction sets loaded into main context
│   ├── orchestrator/SKILL.md          # Activation, routing, session resumption (~180 lines always loaded)
│   │   ├── stages-0-2.md             # Stages 0-2: Intake, Discovery, Definition
│   │   ├── stages-3-4.md             # Stages 3-4: Artifact Generation, Build Planning
│   │   ├── stage-5-build.md          # Stage 5: Build + Governance Loop
│   │   ├── stage-6-iteration.md      # Stage 6: Iteration + Directional Change Protocol
│   │   ├── onboarding.md            # Onboarding Mode: existing codebase → prawduct artifacts
│   │   ├── migration.md             # Schema Migration: old prawduct versions → current format
│   │   ├── observation-contribution.md  # Product repo observation submission flow
│   │   └── protocols/
│   │       ├── agent-invocation.md    # Critic, Lenses, Obs Triage, Artifact Generator agent protocols
│   │       ├── governance.md          # FRP, PFR, Stage Transition, Expertise Calibration, Structural Critique
│   │       └── stage-prerequisites.md # Per-stage prerequisite checklists
│   ├── domain-analyzer/SKILL.md       # Product classification, discovery questions, principles
│   └── builder/SKILL.md               # Code generation: executes build plan chunks, writes tests
├── agents/                            # LLM instruction sets spawned as subprocesses via Task tool
│   ├── critic/
│   │   ├── SKILL.md                  # Context-sensitive governance: invoked as subagent, reads checks from project state
│   │   ├── framework-checks.md       # Checks 7-9 (Generality, Instruction Clarity, Cumulative Health) — framework only
│   │   └── review-cycle.md           # Product build chunk review lifecycle, output format, recording
│   ├── review-lenses/SKILL.md         # Five evaluation perspectives: invoked as subagent for prospective artifact review
│   ├── pattern-extractor/SKILL.md     # Observation pattern analysis: invoked as subagent for systemic trend detection
│   ├── artifact-generator/SKILL.md    # Artifact selection, phasing, consistency: invoked per-phase as subagent
│   └── observation-triage/SKILL.md    # Observation priority/archive triage: invoked as subagent during session resumption
├── tools/                             # Deterministic scripts (mechanical enforcement, 20 files + governance/)
│   ├── governance-hook                # Single entry point for all Claude Code hooks (bash, delegates to Python)
│   ├── governance/                    # Python module: all hook logic (12 submodules)
│   │   ├── {context,classify,state}.py  # Foundation: path resolution, file classification, session state
│   │   ├── {gate,tracker,stop,commit}.py  # Decision logic: PreToolUse, PostToolUse, Stop, Commit gates
│   │   ├── {prompt,reinject}.py       # Advisory hooks: activation check, post-compaction reinject
│   │   ├── trace.py                   # Local-only trace emission, persistence, rotation
│   │   └── __main__.py                # CLI: python3 -m governance <gate|track|stop|commit|prompt|compact-reinject>
│   ├── prawduct-init.{sh,py}         # Project setup, repair, settings.json merging, gitignore management
│   ├── prawduct-statusline.py         # Claude Code statusline: session state, governance todos, context bar, git
│   ├── session-health-check.sh        # Session orientation: patterns, backlog, divergence, trace analysis
│   ├── extract-patterns.sh            # Pattern Extractor wrapper: threshold check, report recording
│   ├── dcp-update.sh                  # DCP state management: classify, track phases, mark completion
│   ├── record-lens-findings.sh        # Review Lenses evidence: structured findings for Orchestrator
│   ├── measure-context-overhead.sh    # Token-approximate context budget measurement
│   ├── prawduct-quick                 # One-command project setup for new users
│   ├── analyze-session-traces.sh      # Trace analysis: gate block rates, PFR/DCP trigger rates
│   ├── compact-project-state.{sh,py}  # Mechanical compaction of growing project-state.yaml sections
│   ├── contribute-observations.sh     # Check/format/submit product observations to framework repo
│   └── ...                            # Observation lifecycle, Critic evidence, product root detection
├── scripts/                           # Eval/validation helpers (validate-eval-output, validate-schema, check-artifacts)
├── templates/                         # Starting templates for user project artifacts
│   ├── project-state.yaml, build-plan.md, + 9 artifact templates  # Core templates
│   ├── human-interface/               # has_human_interface templates (6 files)
│   └── unattended-operation/          # runs_unattended templates (5 files)
├── tests/                             # Evaluation rubrics for skill validation
│   └── scenarios/                     # 4 scenarios: family-utility, background-data-pipeline, terminal-arcade-game, quick-todo-app
├── eval-history/                      # Evaluation results (Tier 1, append-only)
│   └── {scenario}-{date}.md           # Per-run results with YAML frontmatter
├── .claude/                           # Claude Code integration (settings only)
│   ├── settings.json                  # Project-level Claude Code settings (hooks call tools/governance-hook)
│   └── settings.local.json            # Local overrides (not committed)
└── docs/                              # Design documents (WHY — upstream, Tier 1; see high-level-design.md § Documentation Architecture)
    ├── quickstart.md                   # 5-minute getting started guide
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
