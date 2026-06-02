# Framework Repository Structure

Prawduct v2 *is* a Claude Code plugin (and its own git-backed marketplace). The repo
also carries the **frozen v1 file-sync engine** (under `tools/`) as a sibling service for
un-migrated external repos, removed post-2.0 once all local repos migrate. The layout:

```
prawduct/
├── CLAUDE.md                          # Framework operating instructions (principles + methodology pointers)
├── README.md                          # Human-facing project overview
├── VERSION                            # semver (mirrored by .claude-plugin/plugin.json)
│
│   # ── Plugin (v2.0 distribution — the primary surface) ──
├── .claude-plugin/
│   ├── plugin.json                    # name: prawduct, version (mirrors VERSION)
│   └── marketplace.json               # single-plugin marketplace entry (pinned ref: main) — lands in Chunk 2 (marketplace publish, pending)
├── hooks/hooks.json                   # SessionStart (banner + briefing + guidance digest), Stop (Critic + reflection gates)
├── skills/                            # framework skills → /prawduct:* (critic, pr, doctor, migrate, building, discovery, …)
│   ├── critic/                        # bundled Critic protocol (context:fork skill — review-protocol.md, review-cycle.md, framework-checks.md)
│   └── pr/                            # bundled PR-reviewer protocol (review-protocol.md)
├── bin/prawduct-hook                  # plugin runtime governance (Python; reads/writes only ${CLAUDE_PROJECT_DIR}/.prawduct/)
├── lib/                               # plugin governance + scaffolding/migration (init_product, migrate_plugin, core, views, critic_mode, advisory, …)
├── methodology/                       # Narrative guides (bundled; read via ${CLAUDE_PLUGIN_ROOT})
│   ├── discovery.md                   # How to explore a problem space
│   ├── planning.md                    # How to design artifacts and decompose into chunks
│   ├── building.md                    # How to build with quality, including the Critic review cycle
│   ├── reflection.md                  # The learning loop
│   └── session-digest.md             # SessionStart additionalContext digest
│
│   # ── Frozen v1 file-sync engine (sibling service for un-migrated repos; removed post-2.0) ──
├── tools/
│   ├── product-hook                   # legacy session hook (frozen; stands down when the plugin governs)
│   ├── prawduct-setup.py              # legacy CLI: setup, sync, validate (delegates to lib/)
│   ├── prawduct-init.py               # backward-compat shim → prawduct-setup.py setup
│   ├── prawduct-migrate.py            # backward-compat shim → prawduct-setup.py setup
│   ├── prawduct-sync.py              # backward-compat shim → prawduct-setup.py sync
│   └── lib/                           # legacy file-sync implementation modules
│       ├── core.py                    # MANAGED_FILES/SKILL_PLACEMENTS, template strategies
│       ├── init_cmd.py                # file-sync setup/init
│       ├── migrate_cmd.py             # file-sync per-feature migration
│       ├── sync_cmd.py                # file-sync sync
│       └── validate_cmd.py            # file-sync validate
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
│   └── scenarios/                     # 8 test scenarios for framework validation
├── docs/
│   ├── principles.md                  # Full 23 principles with rationale
│   ├── project-structure.md           # This file
│   └── examples/                      # Observability strategy examples (API service, event-driven)
├── .prawduct/                         # Framework's own prawduct state
│   ├── project-state.yaml             # Source of truth for framework iteration
│   ├── learnings.md                   # Accumulated wisdom (surfaced via /prawduct:learnings)
│   ├── learnings-detail.md            # Full learning context and history
│   ├── cross-cutting-concerns.md      # Concern-to-pipeline coverage registry
│   └── archive/                       # Archived development history
│       └── working-notes/             # Design notes from v1-v3 era (Feb 2026)
└── .claude/
    └── settings.json                  # {} — this repo is governed by its own plugin (hooks/hooks.json); the legacy hook wiring was removed at the Chunk-13 cutover
```

## Product repos (plugin-governed)

A v2 product repo commits only its own state plus a small install reference — no framework files. Governance comes from the plugin.

```
my-product/
├── CLAUDE.md                          # product instructions + a thin static governance anchor (PRAWDUCT:ANCHOR)
├── .prawduct/
│   ├── project-state.yaml             # product state (classification, decisions, health_check; distribution: plugin)
│   ├── learnings.md                   # active rules, surfaced via /prawduct:learnings
│   ├── learnings-detail.md            # full learning context and history
│   ├── backlog.md                     # deferred work items (out-of-scope captures)
│   ├── change-log.md                  # change log
│   ├── artifacts/                     # generated specifications
│   │   ├── boundary-patterns.md       # contract surfaces between components
│   │   └── project-preferences.md     # developer preferences (language, testing, style)
│   ├── .pr-reviews/                   # PR review evidence (gitignored)
│   ├── .test-evidence.json            # test evidence for the Critic (gitignored)
│   └── .critic-findings.json          # Critic review evidence (gitignored, checked by the Stop hook)
├── .claude/
│   └── settings.json                  # the committed install reference (marketplace + enabled plugin)
└── src/                               # product source code (+ the product's own skills, MCP servers, configs)
```

Governance — `/prawduct:*` skills, the SessionStart + Stop hooks, methodology, and the Critic/PR protocols — comes from the **plugin**, not the repo. (A v1 file-sync repo carries committed framework files until it runs `/prawduct:migrate`.)
