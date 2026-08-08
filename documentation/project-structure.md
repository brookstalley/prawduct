# Framework Repository Structure

Prawduct v2 *is* a Claude Code plugin (and its own git-backed marketplace). The file-sync
engine the v1 distribution shipped (the `tools/` tree) was retired in M4 — governance now
lives entirely in the plugin (`bin/`, `lib/`, `skills/`, `methodology/`, `hooks/`). The layout:

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
├── bin/prawduct-hook                  # plugin runtime governance (Python; writes the governed repo's own state + the files architecture.md § Direction's reconciled-files norm names)
├── lib/                               # plugin governance + scaffolding/migration (init_product, migrate_plugin, core, change_log, plan_index, critic_mode, advisory, …)
├── methodology/                       # Narrative guides (bundled; read via ${CLAUDE_PLUGIN_ROOT})
│   ├── discovery.md                   # How to explore a problem space
│   ├── planning.md                    # How to design artifacts and decompose into chunks
│   ├── building.md                    # How to build with quality, including the Critic review cycle
│   ├── reflection.md                  # The learning loop
│   └── session-digest.md             # SessionStart additionalContext digest
├── templates/                         # Place-once + planning artifact templates for product repos
│   ├── project-state.yaml             # Product state template (health_check, build_state)
│   ├── boundary-patterns.md           # Contract surfaces between components
│   ├── build-plan.md, product-brief.md, ...  # Artifact templates
│   ├── human-interface/               # has_human_interface templates
│   └── unattended-operation/          # runs_unattended templates
├── pyproject.toml                        # Minimal pytest configuration
├── tests/
│   ├── test_plugin_runtime.py            # Plugin hook runtime (briefing, gates, canary, handoff)
│   ├── test_plugin_init.py               # init-product scaffolding (plugin-native)
│   ├── test_plugin_migrate.py            # /prawduct:migrate file-sync → plugin cutover
│   ├── test_plugin_manifest.py           # plugin.json / marketplace.json / hooks wiring
│   ├── test_plugin_methodology_digest.py # SessionStart digest + methodology reader skills
│   ├── test_plugin_version_banner.py     # version-delta SessionStart banner
│   ├── test_critic_mode_inference.py     # /critic mode inference
│   ├── test_critic_skill_metadata.py     # Critic skill tool restrictions (no test execution)
│   ├── test_build_plan_resolution.py     # active-build-plan resolver (lib ↔ hook parity)
│   ├── test_operator_verification.py     # operator-verification queue + gate
│   ├── test_advisory_store.py, test_advisory_cmd.py  # post-sync advisories
│   ├── test_audit_learnings.py           # learnings-lifecycle audit
│   ├── test_reference_verifier.py        # coverage floor verifier
│   ├── test_pr_reviewer.py               # PR review gate + protocol
│   ├── test_v5_methodology.py            # Methodology + Critic skill content
│   ├── test_v5_templates.py              # Surviving template + plugin-skill content
│   ├── preferences/                      # Architecture/style preference tests
│   └── scenarios/                        # Framework-validation scenarios
├── docs/
│   ├── principles.md                  # Full 24 principles with rationale
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
│   ├── .critic-findings.json          # derived view of the latest Critic review fact (gitignored; gates compose over the evidence store under .git/, not this file)
│   └── .governance-ledger.jsonl       # append-only governance-event history (gitignored; written only by `prawduct-hook ledger-append`)
├── .claude/
│   └── settings.json                  # the committed install reference (marketplace + enabled plugin)
└── src/                               # product source code (+ the product's own skills, MCP servers, configs)
```

Governance — `/prawduct:*` skills, the SessionStart + Stop hooks, methodology, and the Critic/PR protocols — comes from the **plugin**, not the repo. (A v1 file-sync repo carries committed framework files until it runs `/prawduct:migrate`.)
