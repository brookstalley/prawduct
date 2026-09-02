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

Prawduct is a **Claude Code plugin**: install it **once at the user level**, then **onboard each
repo** you want governed — the same command for a new or existing repo. A project commits only a
tiny install *reference*, never framework files.

### 1. Install the plugin (once, for your machine)

```bash
claude plugin marketplace add brookstalley/prawduct
claude plugin install prawduct@prawduct
```

`/prawduct:*` is now available in every Claude Code session.

### 2. Onboard a repo — new or existing, same command

```bash
cd ~/my-repo          # new repo? `mkdir ~/my-repo && cd "$_" && git init` first
claude
> /prawduct:onboard .
```

This scaffolds `.prawduct/`, a thin `CLAUDE.md` anchor, and the committed install reference — zero
framework files in your tree. Then describe what you want:

```
> build a meal-planning app for families with dietary restrictions
> add OAuth login to the existing API
```

Anyone who clones the repo gets the same governance (the plugin auto-installs on first trusted
open). Already onboarded? `/prawduct:doctor` health-checks the repo. Moving a pre-2.0 file-sync
repo? `/prawduct:onboard` routes it to [`/prawduct:migrate`](documentation/MIGRATION.md).

### Turn Prawduct off in a specific repo

Because the plugin installs for your whole machine, its commands and hooks load in every repo you
open. To switch it off in one repo — `/prawduct:*` commands, hooks, and banner — run
**`/prawduct:repo-disable`**. It writes a per-repo `enabledPlugins` override (`committed` for the
whole team, or `local` just for you), preserving your other settings; it takes effect after
`/reload-plugins` or a restart. There's intentionally no re-enable command — once disabled, the
plugin's own commands no longer load — so re-enable by editing the settings file's
`enabledPlugins` back to `"prawduct@prawduct": true` (or via Claude Code's native `/plugin` menu).

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

Everything else is governed by a set of principles, always in context via the session digest, and methodology guides read on demand.

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

Learnings are captured during development as ordinary `.claude/rules/learnings/` files, so the harness loads them and nothing has to look them up: `core.md` is in context from launch, and each `<area>.md` declares `paths:` globs that bring it in when Claude reads a file they match. Rules are concise standing statements — the narrative behind one lives in the session reflection, not in the rule. Learnings follow a lifecycle: provisional (single observation) → confirmed (recurring pattern) → incorporated (absorbed into principles or methodology).

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
claude --plugin-dir ./plugin --add-dir .
```

This repo is governed by its own plugin — it dogfoods itself. **`--plugin-dir` takes `./plugin`, not `.`** — the plugin root moved into `plugin/` in v3.1.1 so that the repo's own state stops being distributed, and the repo root is no longer a plugin root. `--add-dir .` (the repo) lets methodology-reading skills (`/prawduct:methodology building`, `/prawduct:critic`, `/prawduct:methodology planning`) load their bundled guides from the out-of-tree plugin; a real marketplace install grants that automatically. See [documentation/release-process.md](documentation/release-process.md) for the gitflow release model and the release checklist.

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

Unit tests cover the plugin runtime, scaffolding, migration, hooks, and governance (1,716 tests):

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
├── .claude/rules/learnings/
│   ├── core.md                  # cross-cutting rules — loaded by the harness in every session
│   └── <area>.md                # area rules with `paths:` — loaded when a matching file is read
├── .prawduct/
│   ├── project-state.yaml       # product definition, work tracking, build plan
│   ├── backlog.md               # deferred work items (out-of-scope captures)
│   ├── change-log.md            # change log
│   ├── artifacts/               # specifications generated during planning
│   │   ├── project-preferences.md  # developer preferences (language, testing, style)
│   │   └── boundary-patterns.md    # contract surfaces between components
│   ├── .pr-reviews/             # PR review evidence (gitignored; checked by the Stop hook)
│   └── .critic-findings.json    # derived view of the latest review fact (gitignored; gates read the evidence store, not this)
├── .claude/
│   └── settings.json            # the committed install reference (marketplace + enabled plugin)
└── src/, tests/, …              # your product code, your own skills, MCP servers, configs
```

No `tools/product-hook`, no `tools/lib/`, no committed `.claude/skills/*`, no `sync-manifest.json` — those live in the plugin, out of your tree.

## Framework Layout

This repo hosts the plugin and its own git-backed marketplace. **Only `plugin/` is distributed** —
everything beside it is prawduct's own development state and never reaches a consumer's plugin cache
(v3.1.1; the source was previously `"./"`, i.e. the whole repo, ~6.7 MB of it).

```
prawduct/
├── .claude-plugin/marketplace.json   # marketplace entry (plugin source "./plugin"; consumers pin ref: main)
│
├── plugin/                     # ⇦ THE DISTRIBUTED PLUGIN — this directory, and nothing else, is what installs
│   ├── .claude-plugin/plugin.json    # name: prawduct, version (mirrors VERSION)
│   ├── hooks/hooks.json        # SessionStart (banner + briefing + digest), Stop (Critic + reflection gates)
│   ├── skills/                 # framework skills → /prawduct:* (onboard, doctor, critic, pr, runbook, …)
│   ├── bin/prawduct-hook       # runtime governance (Python; writes the governed repo's own state + the files architecture.md § Direction names)
│   ├── lib/                    # governance + scaffolding/migration modules (init_product, migrate_plugin, …)
│   ├── methodology/ templates/ agents/   # read by skills/hooks via ${CLAUDE_PLUGIN_ROOT}
│   ├── docs/                   # only the guides skills route to (principles, norms, waivers, runbook-authoring, …)
│   ├── VERSION                 # read at runtime by lib/core.py and lib/evidence.py
│   └── CHANGELOG.md            # the version-delta banner reads this one
│
├── tests/                      # NOT distributed. framework tests (pytest) + evaluation scenarios
├── documentation/              # NOT distributed. prawduct's own requirements, specs, and release process
├── .prawduct/                  # NOT distributed. the framework's own state — it dogfoods its own plugin
├── CLAUDE.md                   # NOT distributed. prawduct's own operating instructions
└── README.md  LICENSE  pyproject.toml
```

Real files, not symlinks — deliberately. A symlink farm was tried first (much smaller diff) and is
broken on any checkout without symlink support: with `core.symlinks=false`, the Git-for-Windows
default, every entry becomes a few-byte text stub and the plugin installs inert.

`tests/test_plugin_packaging.py` pins that boundary in both directions: a required component going
missing breaks governance for every consumer at once, and a leak puts another product's
documentation in their cache. Neither failure is visible locally, because `--plugin-dir` resolves
against the repo root.

## Architecture

Three layers:

1. **Principles** — Always in context via the session digest, which carries the roster grouped. They govern how work gets done but don't enforce process interruptions.

2. **Methodology guides** — Narrative essays read when entering each activity (discovery, planning, building, reflection). They teach the approach rather than prescribing rigid steps. Governance depth scales with work size and type.

3. **Structural enforcement** — Python hooks that enforce what principles alone can't guarantee: session briefing with staleness detection on start, independent Critic review and reflection gates on stop, compliance canary checks for common governance failures. Zero external dependencies.

See [`docs/principles.md`](plugin/docs/principles.md) for the full principles with rationale and review perspectives.

## Recent Changes

Full release notes are in [CHANGELOG.md](plugin/CHANGELOG.md). Two major releases define the current architecture, and the **3.1–3.4** line is what has been built on top of them:

### 3.1–3.4 — Governance that reports its own state
- **Less waiting on the gates, fewer rounds in review** — the *check* for whether a review is needed stops timing out (20 s → 0.35 s), because the coverage verdict is memoized instead of rescanning every tree the evidence store mentions; syncing your base no longer buys a re-review, because coverage **transfers** when the branch's judgeable files are byte-identical across the two spans. The review itself costs what it always did
- **A finding says whether it found an instance or a class** — and an unbounded class closes only by a *construction*, not by fixing the sites it happened to name; a turn-closing block whose second line answers *whose move is it* (`RUNNING` / `YOUR TURN` / `COMPLETE`) rather than naming a topic; and one session digest for every repo, framework or product
- **Norms bind, descriptions track** — `## Direction` statements in governing artifacts carry normative authority, with an owner-ratification flow and time-domain health sweeps; enforcement is scoped to adoption, so a repo with no ratified norms gets NOTEs and is never blocked
- **Review depth is a risk question, not a file count** — the Critic's three-reviewer coordinator fires on a declared **risk surface** or 12+ judgeable files; `risk_surfaces:` in `project-state.yaml` is how you say where your risk actually lives. Fast `chunk`/`verify-resolutions` reviews got ~83% cheaper, and coordinator reviews now genuinely run in parallel rather than riding an ambient default
- **The review loop has an exit condition** — `.critic-findings.json` carries a code-computed `next_action` that says, in the file the builder opens by contract, *zero blocking: the review is over*. Findings are **dispositioned** — fixed, accepted with a reason, or filed — rather than filed by default
- **Learnings fire where the mistake gets made** — rules that used to wait in a file to be read now print at the command that runs at the moment they apply, in any language rather than only Python; and every agent turn closes with a fixed three-line block — state, whose move it is, clear-verdict
- **The GitHub-Issues backlog service, now live** — opt-in behind a single `backlog_service_repo` key; unset means the markdown backend, byte-for-byte. Prawduct migrated its own backlog through it: 371 items, 0 stranded, 0 collisions. The governance surfaces that went dark at the cutover — the Critic's reconciliation walk and hygiene checks, the PR reviewer's R-1/R-2, the janitor's Backlog Health block — read it again through a **local cache** that syncs incrementally and queries offline, and can now answer which backlog items touch the files a branch actually changed
- **Build-plan checkboxes mean what they say** — `views_enabled` and the derived-view machinery are retired, so a plan's `## Status` block is the plan's own content and nothing overwrites a tick. Finished plans get an `archive/` with a recorded end of life (*completed* or *superseded*) instead of accumulating in the live directory, and two preview-first `/prawduct:doctor` repairs converge an existing repo in one confirmation
- **A build plan can declare the branch it governs** (`branch:` in frontmatter), so two concurrent branches stop conflicting on one line of `project-state.yaml`. Several plans may claim one branch — the briefing says which one governs and why. Entirely opt-in: a plan without it resolves exactly as before
- **Release integrity** — a Phase 0 `check-releasability` gate that fails closed unless every release-pending scope is classified, `check-released` to verify a published release from the *consumer's* side, `release_version_files:` so a product declares which files carry its version, and CI on every push across a 3.10-and-3.14 matrix (CI verifies a release; it never publishes one)
- **The plugin installs from a curated root** — 109 files, 1.7 MB, holding only what you actually run; a `"source": "./"` had been shipping prawduct's own backlog, learnings, and build plans into every consumer's plugin cache
- **Session boundaries stopped destroying session evidence** — `--resume`, `--fork-session`, and compaction now run *orientation*, not a boundary reset, and `.prawduct/.handoff-notes.md` is a forward channel the machine never overwrites
- **Also** — `/prawduct:runbook` (authoring guide, template, and skill), Principle 24 (Retrieval Over Generation), a structural-coverage advisory chain that can see what was *never created*, `test_commands:` for polyglot suites, and merge commits as the standing default everywhere

### 3.0 — Review evidence as a composable fact store
- Review results are **append-only facts** in a store shared by every worktree of a clone — not single-slot, per-worktree files judged by modification time and a mode label
- The Critic, PR, and Stop gates **answer by composing those facts over a range of git trees**, which removes three long-standing frictions: a chunk-reviewed branch no longer demands a redundant full re-review, a good review no longer goes "stale" at a session boundary, and parallel worktrees can see each other's review state
- The review lifecycle is **code-written end to end** — the model contributes only its judgment, so no hand-written protocol file can silently lose a review
- **Zero-touch upgrade** despite the major version: the store initializes lazily, so no consuming repo needs a migration commit or carries any repo diff
- New **`.gitignore` contract-drift advisory** — a session-start nudge when a repo's `.gitignore` drifts from the framework's session-file contract, self-resolving once reconciled

### 2.0 — Plugin distribution
- Prawduct ships as a **Claude Code plugin** — product repos commit zero framework files, just a small install reference; updates arrive with zero repo diff
- `/prawduct:*` namespaced skills; governance via the plugin's SessionStart (banner + briefing + guidance digest) and Stop (Critic + reflection gates) hooks
- **Version-delta banner** (shows what changed + newly-active gates on update); marketplace `autoUpdate` for always-latest
- **`/prawduct:migrate`** — one-command, reversible v1 file-sync → plugin cutover (see [MIGRATION](documentation/MIGRATION.md))
- Plugin-native onboarding/scaffolding via `/prawduct:onboard` (health-check/repair stays `/prawduct:doctor`)
- Gitflow release model (see [docs/release-process.md](documentation/release-process.md))

Between 2.0 and 3.0, the **2.1–2.3** line hardened the framework without changing its shape: reviews became proportional, observable (a governance ledger + `review-stats`), and resilient (a persistence redesign so a coordinator review can't be silently lost); the backlog grew lifecycle stages and multi-agent claims; API design joined the cross-cutting concerns; and dozens of gate-soundness and session hot-path fixes landed. See the [CHANGELOG](plugin/CHANGELOG.md) for the full stream.

## License

MIT — see [LICENSE](LICENSE).
