# Framework Repository Structure

The framework repo layout:

```
prawduct/
├── CLAUDE.md                          # Primary instruction surface: 22 principles + methodology pointers
├── README.md                          # Human-facing project overview
├── methodology/                       # Narrative guides (essays, not checklists)
│   ├── discovery.md                   # How to explore a problem space
│   ├── planning.md                    # How to design artifacts and decompose into chunks
│   ├── building.md                    # How to build with quality, including Critic review cycle
│   └── reflection.md                  # The learning loop
├── agents/                            # Independent review agents
│   ├── README.md                      # Agent architecture overview
│   ├── critic/                        # Independent review agent (invoked via /critic skill)
│   │   ├── SKILL.md                   # Full Critic instructions
│   │   ├── framework-checks.md        # Framework-specific checks (7-10)
│   │   └── review-cycle.md            # Review lifecycle and output format
│   └── pr-reviewer/                   # Release readiness reviewer (invoked via /pr skill)
│       └── SKILL.md                   # PR review goals and merge criteria
├── tools/
│   ├── product-hook                   # Hook script: session clear + stop (framework and products)
│   ├── prawduct-setup.py              # Thin CLI: setup, sync, validate (delegates to lib/)
│   ├── prawduct-init.py               # Backward-compat shim → prawduct-setup.py setup
│   ├── prawduct-migrate.py            # Backward-compat shim → prawduct-setup.py setup
│   ├── prawduct-sync.py              # Backward-compat shim → prawduct-setup.py sync
│   └── lib/                           # Core implementation modules
│       ├── __init__.py                # Re-exports for backward compat
│       ├── core.py                    # Shared helpers, MANAGED_FILES, template strategies
│       ├── init_cmd.py                # Setup/init command implementation
│       ├── migrate_cmd.py             # Migration command implementation
│       ├── sync_cmd.py                # Sync command implementation
│       └── validate_cmd.py            # Validate command implementation
├── templates/                         # Templates for product repos
│   ├── product-claude.md              # Self-contained CLAUDE.md for products (v3 core)
│   ├── critic-review.md              # Condensed Critic instructions for products (v3 core)
│   ├── product-settings.json          # .claude/settings.json template for products
│   ├── project-state.yaml             # Product state template (health_check, build_state)
│   ├── boundary-patterns.md           # Contract surfaces between components
│   ├── build-plan.md, product-brief.md, ...  # Artifact templates
│   ├── human-interface/               # has_human_interface templates
│   └── unattended-operation/          # runs_unattended templates
├── pyproject.toml                        # Minimal pytest configuration
├── tests/
│   ├── test_prawduct_init.py             # Tests for init functionality (prawduct-setup.py)
│   ├── test_prawduct_migrate.py          # Tests for migration + v5 migration (prawduct-setup.py)
│   ├── test_prawduct_sync.py             # Tests for sync functionality (prawduct-setup.py)
│   ├── test_prawduct_validate.py         # Tests for validation functionality (prawduct-setup.py)
│   ├── test_product_hook.py              # All product-hook tests (governance, briefing, canary, handoff)
│   ├── test_integration_lifecycle.py     # End-to-end lifecycle tests
│   ├── test_preferences_lifecycle.py     # Project preferences lifecycle tests
│   ├── test_v5_methodology.py           # Methodology and Critic content tests
│   ├── test_v5_templates.py             # Template structure and consistency tests
│   ├── test_product_compat.py           # Product repo compatibility tests
│   ├── test_coverage_gaps.py            # User journey and edge case coverage tests
│   ├── test_pr_reviewer.py              # PR reviewer agent tests
│   └── scenarios/                     # 4 test scenarios for framework validation
├── docs/
│   ├── principles.md                  # Full 22 principles with rationale
│   ├── project-structure.md           # This file
│   └── examples/                      # Observability strategy examples (API service, event-driven)
├── .prawduct/                         # Framework's own prawduct state
│   ├── project-state.yaml             # Source of truth for framework iteration
│   ├── learnings.md                   # Accumulated wisdom (read at session start)
│   ├── learnings-detail.md            # Full learning context and history
│   ├── cross-cutting-concerns.md      # Concern-to-pipeline coverage registry
│   └── archive/                       # Archived development history
│       └── working-notes/             # Design notes from v1-v3 era (Feb 2026)
└── .claude/
    └── settings.json                  # 2 hooks: SessionStart (clear) + Stop (reflection + Critic gate)
```

## Product repos (generated by prawduct)

```
my-product/
├── CLAUDE.md                          # Self-contained: principles, methodology, Critic instructions
├── .prawduct/
│   ├── project-state.yaml             # Product state (classification, decisions, health_check)
│   ├── learnings.md                   # Active rules, read at session start (<3K tokens)
│   ├── learnings-detail.md            # Full learning context and history
│   ├── backlog.md                     # Deferred work items (out-of-scope captures)
│   ├── build-governance.md            # Build governance reference (read before coding)
│   ├── critic-review.md               # Goal-based Critic instructions for this product
│   ├── pr-review.md                   # PR reviewer instructions for this product
│   ├── sync-manifest.json             # Tracks framework sync state (format_version 2)
│   ├── artifacts/                     # Generated specifications
│   │   ├── boundary-patterns.md       # Contract surfaces between components
│   │   └── project-preferences.md     # Developer preferences (language, testing, style)
│   ├── .subagent-briefing.md          # Generated briefing for delegated agents
│   ├── .session-handoff.md            # Auto-generated context from previous session (read at session start)
│   ├── .pr-reviews/                   # PR review evidence (gitignored)
│   ├── .test-evidence.json            # Test evidence for Critic (gitignored)
│   └── .critic-findings.json          # Critic review evidence (checked by stop hook)
├── tools/
│   └── product-hook                   # Session governance (Python: reflection + Critic gate + sync + v4→v5 auto-migration)
├── tests/
│   └── conftest.py                    # Auto-grouping for parallel test execution (pytest-xdist)
├── .claude/
│   ├── skills/
│   │   ├── pr/SKILL.md                # /pr — PR lifecycle management
│   │   ├── critic/SKILL.md            # /critic — Independent Critic review (tool-restricted)
│   │   ├── janitor/SKILL.md           # /janitor — Periodic codebase maintenance
│   │   ├── learnings/SKILL.md         # /learnings — Context-efficient knowledge lookup
│   │   └── prawduct-doctor/SKILL.md   # /prawduct-doctor — Health check and repair
│   └── settings.json                  # Hook config + banner pointing to tools/product-hook
└── src/                               # Product source code
```
