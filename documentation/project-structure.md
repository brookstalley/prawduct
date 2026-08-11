# Framework Repository Structure

Prawduct *is* a Claude Code plugin (and its own git-backed marketplace). The file-sync engine the
v1 distribution shipped was retired in M4 — governance now lives entirely under `plugin/`. **Every
framework path is under `plugin/`**, which is the single fact to carry away: the marketplace's
`source` is `./plugin`, so that subtree is what a consumer actually installs, and the repo root
holds only the things a consumer never receives.

```
prawduct/
├── CLAUDE.md                          # Framework operating instructions (principles + methodology pointers)
├── README.md                          # Human-facing project overview
├── .claude-plugin/
│   └── marketplace.json               # single-plugin marketplace entry; source: ./plugin
│
│   # ── plugin/ — the distribution. This subtree IS what installs. ──
├── plugin/
│   ├── .claude-plugin/plugin.json     # name: prawduct, version (mirrors plugin/VERSION)
│   ├── VERSION                        # semver (mirrored by plugin.json and pyproject.toml)
│   ├── CHANGELOG.md                   # consumer-facing release notes
│   ├── hooks/hooks.json               # SessionStart (banner + briefing + digest), Stop (Critic + reflection gates), SubagentStop
│   ├── bin/prawduct-hook              # the runtime: every gate, probe and state writer (Python, one file)
│   ├── lib/                           # the bodies the hook reaches lazily (init_product, migrate_plugin, core,
│   │                                  #   change_log, plan_index, plan_archive, critic_consolidate, release_readiness, …)
│   ├── skills/                        # framework skills → /prawduct:* (critic, pr, backlog, doctor, janitor,
│   │   │                              #   learnings, methodology, migrate, onboard, report-bug, runbook, advisory, …)
│   │   ├── critic/                    # bundled Critic protocol (context:fork — SKILL.md, review-protocol.md,
│   │   │                              #   review-cycle.md, goals-1-3.md, framework-checks.md)
│   │   └── pr/                        # bundled PR-reviewer protocol
│   ├── agents/critic-reviewer.md      # the coordinator's subagent definition (its own restricted tools)
│   ├── methodology/                   # Narrative guides (read via ${CLAUDE_PLUGIN_ROOT})
│   │   ├── discovery.md               # How to explore a problem space
│   │   ├── planning.md                # How to design artifacts and decompose into chunks
│   │   ├── building.md                # The build cycle, including the Critic review cycle
│   │   ├── reflection.md              # The learning loop
│   │   └── session-digest.md          # SessionStart additionalContext digest
│   ├── docs/                          # principles.md (the 24), norms.md, waivers.md,
│   │                                  #   doctor-vs-janitor.md, governance-telemetry.md, runbook-authoring.md, examples/
│   └── templates/                     # Place-once + planning artifact templates for product repos
│       ├── project-state.yaml         # Product state template (health_check, build_state)
│       ├── boundary-patterns.md       # Contract surfaces between components
│       ├── build-plan.md, product-brief.md, ...  # Artifact templates
│       ├── human-interface/           # has_human_interface templates
│       └── unattended-operation/      # runs_unattended templates
│
│   # ── repo root — development only; none of it installs ──
├── pyproject.toml                        # pytest configuration + project version (the third mirrored version file)
├── tools/                                # one-off measurement scripts, not shipped and not the retired v1 sync engine
├── documentation/                        # framework design docs (this file lives here, NOT in plugin/docs/)
├── incoming-bugs/                        # upstream bug reports products file about prawduct itself
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
├── .prawduct/                         # Framework's own prawduct state — it governs itself
│   ├── project-state.yaml             # Source of truth for framework iteration
│   ├── learnings.md                   # Accumulated wisdom (surfaced via /prawduct:learnings)
│   ├── learnings-detail.md            # Full learning context and history
│   ├── change-log.md                  # what shipped, per scope, with its release= tag
│   ├── cross-cutting-concerns.md      # Concern-to-pipeline coverage registry
│   ├── artifacts/                     # this repo's own specs and plans (+ archive/)
│   ├── runbooks/                      # operational procedures (release cut, pruned promotion)
│   └── archive/working-notes/         # Design notes from the v1-v3 era (Feb 2026)
└── .claude/
    └── settings.json                  # {} — this repo is governed by its own plugin (plugin/hooks/hooks.json)
```

> **Two paths people get wrong, because their names collide.** `documentation/` (repo root) holds
> framework *design* docs — including this file — and does not ship. `plugin/docs/` holds the
> reference material the *methodology cites by path* (`principles.md`, `norms.md`, `waivers.md`) and
> does ship. A pointer to `docs/principles.md` is wrong on both counts; it is
> `plugin/docs/principles.md`.

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
│   │   ├── project-preferences.md     # developer preferences (language, testing, style)
│   │   └── archive/                   # plans past their end of life (`prawduct-hook archive-plan`) — committed
│   │                                  #   history, pruned at directory level by every scan on a hot path
│   ├── .pr-reviews/                   # PR review evidence (gitignored)
│   ├── .test-evidence.json            # test evidence for the Critic (gitignored)
│   ├── .critic-findings.json          # derived view of the latest Critic review fact (gitignored; gates compose over the evidence store under .git/, not this file)
│   └── .governance-ledger.jsonl       # append-only governance-event history (gitignored; written only by `prawduct-hook ledger-append`)
├── .claude/
│   └── settings.json                  # the committed install reference (marketplace + enabled plugin)
└── src/                               # product source code (+ the product's own skills, MCP servers, configs)
```

Governance — `/prawduct:*` skills, the SessionStart + Stop hooks, methodology, and the Critic/PR protocols — comes from the **plugin**, not the repo. (A v1 file-sync repo carries committed framework files until it runs `/prawduct:migrate`.)
