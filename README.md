# Prawduct

Prawduct is a product development framework for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) that adds structured planning, independent quality reviews, and continuous per-project learning to AI-assisted software development.

## Table of Contents

- [Quick Start](#quick-start)
- [The Problem](#the-problem)
- [How Prawduct Works](#how-prawduct-works)
- [Why Prawduct Works](#why-prawduct-works)
- [Working with Prawduct](#working-with-prawduct)
- [Q&A](#qa)
- [Testing Prawduct](#testing-prawduct)
- [Product Repo Structure](#product-repo-structure)
- [Framework Layout](#framework-layout)
- [Architecture](#architecture)
- [Recent Changes](#recent-changes)

## The Problem

Going from "I need an app that does X" straight to code skips the hard questions: Who are the users? What are the edge cases and failure modes? What does "done" look like? What needs to be tested, and how?

Claude Code is fantastic at writing code, but without discipline it makes assumptions about product intent, produces code that drifts from requirements, skips edge cases, weakens tests to make them pass, and accumulates technical debt — all without telling you.

## Quick Start

### Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- Python 3 (the plugin's governance hooks are Python, zero external dependencies)
- git

Prawduct v2 is distributed as a **Claude Code plugin**. A product repo commits only a
small install *reference* — never framework files. (See [MIGRATION](documentation/MIGRATION.md)
to move an existing v1 file-sync repo onto the plugin.)

### Install the plugin

Prawduct is published as a Claude Code plugin from its own marketplace (this repo, pinned to
`main`). Add the marketplace and install the plugin:

```bash
claude plugin marketplace add brookstalley/prawduct
claude plugin install prawduct@prawduct
```

The `/prawduct:*` skills and governance are then available in your sessions. To onboard a repo
so it self-governs for everyone who clones it, run `/prawduct:doctor` (below) — it commits a
small install reference (marketplace + enabled plugin); no framework files land in your tree.

> **Developing the framework itself?** Load your working copy instead of the released plugin
> with `claude --plugin-dir /path/to/prawduct --add-dir /path/to/prawduct` — the `--add-dir`
> (same path) lets methodology-reading skills (`/prawduct:building`, `/prawduct:critic`,
> `/prawduct:planning`) load their bundled guides from the out-of-tree plugin. See
> [Develop the framework itself](#develop-the-framework-itself).

### Start a new product

```bash
mkdir ~/my-product && cd ~/my-product && git init
claude
> /prawduct:doctor .
```

`/prawduct:doctor` (Onboard) scaffolds the product-owned state — `.prawduct/`, a thin
governance anchor in `CLAUDE.md`, and the committed install reference — with **zero**
framework files in your tree. Then describe what you want to build:

```
> I want to build a meal planning app for families with dietary restrictions
```

### Add Prawduct to an existing repo

```bash
cd ~/existing-repo
claude
> /prawduct:doctor .
```

For a brand-new `.prawduct/`, doctor scaffolds it; for a repo that still carries v1
file-sync framework files, it routes you to `/prawduct:migrate` (one reversible commit).

Prawduct will ask the obvious questions and also the non-obvious questions before getting started. It analyzes existing code (if any) to infer project conventions (language, test framework, code style) and records them for future reference.

## How Prawduct Works

You describe what you want to build, either a net-new product or enhancements to an existing one. Prawduct scales governance to match the work:

**Discovery** — Asks about your users, workflows, edge cases, security, and scope. Scales question depth to risk: a family scratchpad gets 5-8 questions; a financial platform gets 15-25. Discovery is continuous — new features need their own discovery.

**Planning** — Produces structured specifications in dependency order: product brief, data model, security model, test specifications, non-functional requirements, and a chunked build plan.

**Building** — Implements the product in governed chunks. Governance depth scales with work size (trivial → large) and type (bugfix → feature → refactor). Each chunk follows a cycle: read spec, write tests alongside implementation, verify, then submit for independent Critic review. The Critic runs as a separate agent with no access to the builder's reasoning — it sees only the code and specs, catching things the builder's own context blinds it to.

**Reflection and Learning** — After each significant action, captures what happened, whether it was expected, and what it teaches. Learnings follow a lifecycle (provisional → confirmed → incorporated) and accumulate across sessions. Learnings inform future plans, reducing repetition of the same mistakes.

## Why Prawduct Works

### Structural enforcement, not just instructions

Telling an LLM to "always do X" works until context gets large, the LLM decides that work is too minor to merit discipline, or context gets compacted.

Prawduct enforces governance at four levels:

- **Session briefing** — On session start, a staleness scan checks artifacts against code reality and delivers a structured briefing with project context, warnings, and relevant learnings. The session briefing surfaces things like current stage in multi-step work, PR's waiting to be merged, and recently completed work.
- **Critic review** — A session hook blocks completion if code was modified against a build plan but no independent review happened. The Critic skill has structural tool restrictions preventing test/build execution.
- **Session reflection** — A session hook blocks completion if no reflection was captured (skipped for doc-only changes)
- **Compliance canary** — At session end, informational checks flag common governance failures (code without tests, dependencies without rationale, broad exception handling)

Everything else is governed by 23 principles and four methodology guides that stay in context via CLAUDE.md.

### Independent Critic review

The Critic runs as a Claude Code skill with `context: fork` (separate context) and `allowed-tools` that prevent running tests, builds, or executables. It has no access to the builder's reasoning or justifications — only the code, tests, and specifications. This structural separation catches blind spots that in-context review misses. The builder records test evidence (`.prawduct/.test-evidence.json`) during verification; the Critic reads it instead of re-running the suite.

### The Janitor

All projects suffer drift over time. Each individual review can be executed perfectly, but accumulation over time means cruft appears, old code is not updated to new architectural patterns, tests go stale, documentation goes stale, Git accumulates dead branches, etc. The janitor skill is focused on periodic repo maintenance to catch these kinds of issues that are next to impossible for humans or LLMs to be perfect at during day-to-day work.

### Zero committed framework files

A product repo commits only its own state plus a small install *reference* — no framework code. Governance comes from the plugin, which lives out-of-tree in the Claude Code plugin cache. The product's own `.prawduct/` state (learnings, backlog, decisions, artifacts) stays in the repo and is fully portable.

This means:
- Product repos stay clean — framework updates never show up in your diffs (the v1 stash/pop/merge papercut is eliminated)
- The framework version is a clear signal, shown in the session banner — not buried in synced files
- Each product keeps its own learning history and evolves independently
- Updates arrive via the marketplace with **zero repo diff**

(Existing v1 repos that committed framework files keep working and migrate when ready — see [MIGRATION](documentation/MIGRATION.md).)

### Proportional rigor

The framework detects structural characteristics (human interface, API, background automation, multi-party, sensitive data, distributed) and scales everything accordingly — discovery depth, artifact detail, test coverage, review intensity. A quick utility doesn't get exhaustive governance; a platform doesn't get hobby-grade review.

### Closed learning loop

Learnings are captured during development and surfaced on demand via the `/prawduct:learnings` skill, which reads the knowledge files in a forked context and returns only what's relevant to the task at hand. A two-tier system separates concise standing rules (`learnings.md`) from full root cause / debugging detail (`learnings-detail.md`). Learnings follow a lifecycle: provisional (single observation) → confirmed (recurring pattern) → incorporated (absorbed into principles or methodology).

## Working with Prawduct

### Update product repos

Updates arrive through the plugin marketplace: with `autoUpdate`, Claude Code re-resolves the latest release at session start — **zero changes to your repo**. The session banner shows the active version and, on a bump, what changed and which governance gates are newly active. There is no sync step and no framework files to reconcile.

(v1 file-sync repos not yet migrated keep running on their last-synced framework copy until you move them onto the plugin with `/prawduct:migrate` — see [MIGRATION](documentation/MIGRATION.md).)

### Health-check a product repo

From within a product repo:

```
> /prawduct:doctor
```

It validates the committed install reference, confirms the repo is on the plugin, flags any stale file-sync residue, and checks core `.prawduct/` state — with the fix for each issue.

### Develop the framework itself

```bash
cd prawduct
claude --plugin-dir .
```

This repo is governed by its own plugin — it dogfoods itself. See [docs/release-process.md](docs/release-process.md) for the gitflow release model and the release checklist.

## Q&A

Q: **Doesn't this use a lot of tokens?**

A: Yes, yes it does. However, it uses fewer tokens than having to go back and revise applications over and over again. Developing clear scope, writing good requirements docs, and ensuring test coverage and architectural consistency takes a lot of thought and effort, for human or machine. The only thing more expensive is *not* doing that stuff.

Q: **What languages can Prawduct develop in?**

A: Really anything Claude Code can. Prawduct has no language-specific instructions or code, and relies on Claude's smarts to plan appropriately for the target language. You'll get better results with the languages Claude is better at, of course.

Q: **How much control do I have over product and tech choices?**

A: As much or as little as you want. Prawduct is designed to interview you during the onboarding process and to make inferences about the areas where you're opinionated versus not. But you can always express a preference (for a language, a color scheme, a logging provider) and Prawduct will honor it. Project preferences are stored in `.prawduct/artifacts/project-preferences.md` and you can edit them directly if you like.

Q: **How do I remove Prawduct from a project?**

A: Easily done: 1) Delete `.prawduct/`, 2) remove the prawduct install reference (`extraKnownMarketplaces.prawduct` + the `enabledPlugins` entry) from `.claude/settings.json`, 3) remove the `PRAWDUCT:ANCHOR` block from CLAUDE.md. (A v1 file-sync repo that hasn't migrated also has committed framework files to delete — or just `git revert` the migration commit to go back.)

## Testing Prawduct

Unit tests cover the plugin runtime, scaffolding, migration, hooks, and governance (714 tests):

```bash
cd prawduct
python3 -m pytest tests/
```

Scenario tests in `tests/scenarios/` are end-to-end evaluations — each describes a product, a user persona with scripted responses, and a detailed rubric. Together they cover every structural characteristic, a range of risk levels, diverse tech stacks, and user expertise from novice to deep expert.

| Scenario | Persona | Structural characteristics | Stack | Risk | Tests |
|----------|---------|--------------------------|-------|------|-------|
| **Quick To-Do App** | Mobile user (implied) | `has_human_interface` (mobile) | Mobile | Low | Proportionality — light-touch process for trivial products; happy path |
| **Score Night** | Non-technical family user | `has_human_interface` (mobile) | Mobile | Low | Pacing for non-technical users; scope restraint |
| **DoseCheck** | Marketing manager, 38 | `handles_sensitive_data` (health), `has_human_interface` (iOS) | iOS / Swift | High | High-risk + low-scale tension; privacy without over-engineering |
| **Digest Bot** | Indie dev, mid-level backend | `runs_unattended` (scheduled) | Python | Low-Med | Headless pipeline detection; no UI questioning; external integrations |
| **Terminal Invaders** | Senior engineer, 8 yrs | `has_human_interface` (terminal) | Language-agnostic | Low-Med | Unusual UI substrate; real-time game loop; cross-platform terminal |
| **Chromavert** | Senior Rust engineer, 6 yrs | `exposes_programmatic_interface` (REST) | Rust | Medium | API-only product; mathematical correctness; N×N conversion matrix |
| **QuickCheck** | 8th-grade science teacher, 15 yrs | `has_multiple_party_types`, `has_human_interface` (web) | Web | Medium | Multi-party workflows; trust boundaries; COPPA; non-technical vocab |
| **ThermoGraph** | Retired EE, 35 yrs experience | `multi_process_distributed`, `runs_unattended`, `has_human_interface`, `exposes_programmatic_interface` | Go | Low-Med | 4 overlapping characteristics; process topology; inverse vocabulary calibration (expert systems, novice web) |

Run a scenario by opening this repo in Claude Code:

```bash
cd prawduct
claude
> let's run through tests/scenarios/home-environmental-monitor.md
```

The coordinating Claude spawns a second session that does the work without seeing the full scenario file, relays scripted answers, then scores against the rubric. Takes 3–15 minutes depending on scenario.

## Product Repo Structure

A v2 product repo commits only its own state plus the install reference — no framework files. Governance (skills, hooks, methodology, Critic/PR protocols) comes from the plugin.

```
my-product/
├── CLAUDE.md                    # your product instructions + a thin static governance anchor (PRAWDUCT:ANCHOR)
├── .prawduct/
│   ├── project-state.yaml       # product definition, work tracking, build plan
│   ├── learnings.md             # active rules (read by /prawduct:learnings)
│   ├── learnings-detail.md      # full learning context and history
│   ├── backlog.md               # deferred work items (out-of-scope captures)
│   ├── change-log.md            # change log
│   ├── artifacts/               # specifications generated during planning
│   │   ├── project-preferences.md  # developer preferences (language, testing, style)
│   │   └── boundary-patterns.md    # contract surfaces between components
│   ├── .pr-reviews/             # PR review evidence (gitignored; checked by the Stop hook)
│   └── .critic-findings.json    # Critic review evidence (gitignored; checked by the Stop hook)
├── .claude/
│   └── settings.json            # the committed install reference (marketplace + enabled plugin)
└── src/, tests/, …              # your product code, your own skills, MCP servers, configs
```

No `tools/product-hook`, no `tools/lib/`, no committed `.claude/skills/*`, no `sync-manifest.json` — those live in the plugin, out of your tree.

## Framework Layout

Prawduct *is* the plugin (and its own git-backed marketplace):

```
prawduct/
├── .claude-plugin/
│   ├── plugin.json             # name: prawduct, version (mirrors VERSION)
│   └── marketplace.json        # single-plugin marketplace entry (plugin source "./", consumers pin ref: main)
├── hooks/hooks.json            # SessionStart (banner + briefing + guidance digest), Stop (Critic + reflection gates)
├── skills/                     # framework skills → /prawduct:* (critic, pr, doctor, migrate, building, …)
├── bin/prawduct-hook           # runtime governance (Python; reads/writes only ${CLAUDE_PROJECT_DIR}/.prawduct/)
├── lib/                        # governance + scaffolding/migration modules (init_product, migrate_plugin, …)
├── methodology/ docs/ templates/  # bundled; read by skills/hooks via ${CLAUDE_PLUGIN_ROOT}
├── tests/                      # framework tests (pytest) and evaluation scenarios
├── VERSION
└── .prawduct/                  # the framework's own state — it dogfoods its own plugin
```

## Architecture

Three layers:

1. **23 Principles** — Always in context via CLAUDE.md. Grouped into Quality, Product, Process, Learning, and Judgment. They govern how work gets done but don't enforce process interruptions.

2. **Methodology guides** — Narrative essays read when entering each activity (discovery, planning, building, reflection). They teach the approach rather than prescribing rigid steps. Governance depth scales with work size and type.

3. **Structural enforcement** — Python hooks that enforce what principles alone can't guarantee: session briefing with staleness detection on start, independent Critic review and reflection gates on stop, compliance canary checks for common governance failures. Zero external dependencies.

See [`docs/principles.md`](docs/principles.md) for the full principles with rationale and review perspectives.

## Recent Changes

Full history is in [CHANGELOG.md](CHANGELOG.md). Highlights:

### 2.0 — Plugin distribution
- Prawduct ships as a **Claude Code plugin** — product repos commit zero framework files, just a small install reference; updates arrive with zero repo diff
- `/prawduct:*` namespaced skills; governance via the plugin's SessionStart (banner + briefing + guidance digest) and Stop (Critic + reflection gates) hooks
- **Version-delta banner** (shows what changed + newly-active gates on update); marketplace `autoUpdate` for always-latest
- **`/prawduct:migrate`** — one-command, reversible v1 file-sync → plugin cutover (see [MIGRATION](documentation/MIGRATION.md))
- Plugin-native new-product scaffolding via `/prawduct:doctor`
- Gitflow release model (see [docs/release-process.md](docs/release-process.md))
- Backward compatible: existing v1 file-sync repos migrate onto the plugin via `/prawduct:migrate` (one reversible, revertable commit)

## License

MIT — see [LICENSE](LICENSE).
