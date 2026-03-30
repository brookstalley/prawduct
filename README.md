# Prawduct

Prawduct is a product development framework for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) that adds structured planning, independent quality reviews, and continuous per-project learning to AI-assisted software development.

## The Problem

Going from "I need an app that does X" straight to code skips the hard questions: Who are the users? What are the edge cases and failure modes? What does "done" look like? What needs to be tested, and how?

Claude Code is fantastic at writing code, but without discipline it makes assumptions about product intent, produces code that drifts from requirements, skips edge cases, weakens tests to make them pass, and accumulates technical debt — all without telling you.

## How Prawduct Works

You describe what you want to build, either a net-new product or enhancements to an existing one. Prawduct scales governance to match the work:

**Discovery** — Asks about your users, workflows, edge cases, security, and scope. Scales question depth to risk: a family scratchpad gets 5-8 questions; a financial platform gets 15-25. Discovery is continuous — new features need their own discovery.

**Planning** — Produces structured specifications in dependency order: product brief, data model, security model, test specifications, non-functional requirements, and a chunked build plan.

**Building** — Implements the product in governed chunks. Governance depth scales with work size (trivial → large) and type (bugfix → feature → refactor). Each chunk follows a cycle: read spec, write tests alongside implementation, verify, then submit for independent Critic review. The Critic runs as a separate agent with no access to the builder's reasoning — it sees only the code and specs, catching things the builder's own context blinds it to.

**Reflection and Learning** — After each significant action, captures what happened, whether it was expected, and what it teaches. Learnings follow a lifecycle (provisional → confirmed → incorporated) and accumulate across sessions. Learnings are checked when planning new work, closing the loop.

## Why Prawduct Works

### Structural enforcement, not just instructions

Telling an LLM to "always do X" works until context gets large, and those instructions degrade with compaction.

Prawduct enforces governance at four levels:

- **Session briefing** — On session start, a staleness scan checks artifacts against code reality and delivers a structured briefing with project context, warnings, and relevant learnings
- **Critic review** — A session hook blocks completion if code was modified against a build plan but no independent review happened. The Critic skill has structural tool restrictions preventing test/build execution
- **Session reflection** — A session hook blocks completion if no reflection was captured (skipped for doc-only changes)
- **Compliance canary** — At session end, informational checks flag common governance failures (code without tests, dependencies without rationale, broad exception handling)

Everything else is governed by 22 principles and four methodology guides that stay in context via CLAUDE.md.

### Independent Critic review

The Critic runs as a Claude Code skill with `context: fork` (separate context) and `allowed-tools` that prevent running tests, builds, or executables. It has no access to the builder's reasoning or justifications — only the code, tests, and specifications. This structural separation catches blind spots that in-context review misses. The builder records test evidence (`.prawduct/.test-evidence.json`) during verification; the Critic reads it instead of re-running the suite.

### The Janitor

All projects suffer drift over time. Each individual review can be executed perfectly, but accumulation over time means cruft appears, old code is not updated to new architectural patterns, tests go stale, documentation goes stale, Git accumulates dead branches, etc. The janitor skill is focused on periodic repo maintenance to catch these kinds of issues that are next to impossible for humans or LLMs to be perfect at during day-to-day work.

### Self-contained product repos

Generated product repos carry everything they need: own CLAUDE.md, own hooks, own Critic instructions, own learning history. There is no runtime dependency on the Prawduct framework. Products work identically whether the framework repo exists or not.

This means:
- Products are portable and shareable
- The framework is a generator, not a runtime dependency
- Each product can evolve independently
- Framework updates propagate via automatic, edit-preserving sync (requires having the framework cloned to a sibling dir)

### Proportional rigor

The framework detects structural characteristics (human interface, API, background automation, multi-party, sensitive data, distributed) and scales everything accordingly — discovery depth, artifact detail, test coverage, review intensity. A quick utility doesn't get exhaustive governance; a platform doesn't get hobby-grade review.

### Closed learning loop

Learnings are captured during development, and read at session start to inform decisions. A two-tier system keeps active rules concise (<3K tokens in `learnings.md`) with full context in `learnings-detail.md`. Learnings follow a lifecycle: provisional (single observation) → confirmed (recurring pattern) → incorporated (absorbed into principles or methodology). A dedicated /learnings skill lets Claude Code request relevant learnings for planned work rather than loading lots of tokens that aren't relevant to the task at hand.

## Getting Started

### Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- Python 3
- git

Clone the framework repo first:

```bash
git clone https://github.com/brookstalley/prawduct
```

### Start a new product from scratch

```bash
python3 prawduct/tools/prawduct-setup.py setup ~/my-product --name "My Product"
cd ~/my-product
claude
```

Then describe what you want to build.

### Add Prawduct to an existing repo

```bash
python3 prawduct/tools/prawduct-setup.py setup ~/existing-repo --name "My Existing Project"
cd ~/existing-repo
claude
```

Prawduct detects existing code and infers project conventions (language, test framework, code style) before making any changes. The `setup` subcommand auto-detects repo state and routes to init, migration, or sync as needed.

### Update product repos after framework changes

Product repos sync automatically at session start via the product-hook. To sync manually:

```bash
python3 prawduct/tools/prawduct-setup.py sync ~/my-product
```

If a template changed but the product file has local edits, sync skips it with a message. Use `--force` to accept the new template version (overwrites local edits):

```bash
python3 prawduct/tools/prawduct-setup.py sync ~/my-product --force
```

### Health check a product repo

```bash
python3 prawduct/tools/prawduct-setup.py validate ~/my-product
```

Or from within a product repo, use `/prawduct-doctor` to check health and offer repair.

### Develop the framework itself

```bash
cd prawduct
claude
```

## Q&A

Q: **Doesn't this use a lot of tokens?**

A: Yes, yes it does. However, it uses fewer tokens than having to go back and revise applications over and over again. Developing clear scope, writing good requirements docs, and ensuring test coverage and architectural consistency takes a lot of thought and effort, for human or machine. The only thing more expensive is *not* doing that stuff.

Q: **What languages can Prawduct develop in**

A: Really anything Claude Code can. Prawduct has no language-specific instructions or code, and relies on Claude's smarts to plan appropriately for the target language. You'll get better results with the languages Claude is better at, of course.

Q: **How much control do I have over product and tech choices?**

A: As much or as little as you want. Prawduct is designed to interview you during the onboarding process and to make inferences about the areas where you're opinionated versus not. But you can always express a preference (for a language, a color scheme, a logging provider) and Prawduct will honor it. Project prefernences are stored in `.prawduct/artifacts/project-preferencs.md` and you can edit them directly if you like.

## Testing Prawduct

Unit tests cover all hooks and setup tooling (750 tests):

```bash
cd prawduct
python3 -m pytest tests/
```

Scenario tests in `tests/scenarios/` are manual evaluations — each describes a sample product, a user persona, scripted inputs, and a rubric. Run them by opening the Prawduct repo in Claude Code and following the scenario's evaluation procedure:

```bash
cd prawduct
claude
> let's run through tests/scenarios/home-environmental-monitor.md
```

These scenario tests *should* spawn a second Claude Code that does the work without seeing the full scenario file, ensuring fair testing.

This may take a while, anywhere from 3 - 15 minutes depending on scenario.

## Generated Product Repo Structure

```
my-product/
├── CLAUDE.md                    # 22 principles + methodology (synced from framework)
├── .prawduct/
│   ├── project-state.yaml      # Product definition, work tracking, build plan
│   ├── learnings.md            # Active rules, read by /learnings skill (<3K tokens)
│   ├── learnings-detail.md     # Full learning context and history
│   ├── backlog.md              # Deferred work items (out-of-scope captures)
│   ├── build-governance.md     # Build governance reference (read before coding)
│   ├── critic-review.md        # Goal-based Critic instructions for this product
│   ├── pr-review.md            # PR reviewer instructions for this product
│   ├── sync-manifest.json      # Tracks framework sync state
│   ├── artifacts/              # Specifications generated during planning
│   │   ├── boundary-patterns.md  # Contract surfaces between components
│   │   └── project-preferences.md # Developer preferences (language, testing, style)
│   ├── .subagent-briefing.md   # Generated briefing for delegated agents
│   ├── .pr-reviews/            # PR review evidence (checked by stop hook)
│   └── .critic-findings.json   # Critic review evidence (checked by stop hook)
├── tools/
│   └── product-hook            # Session governance (Python, zero dependencies)
├── .claude/
│   ├── skills/
│   │   ├── pr/SKILL.md              # /pr — PR lifecycle management
│   │   ├── critic/SKILL.md          # /critic — Independent Critic review (tool-restricted)
│   │   ├── janitor/SKILL.md         # /janitor — Periodic codebase maintenance
│   │   ├── learnings/SKILL.md       # /learnings — Context-efficient knowledge lookup
│   │   └── prawduct-doctor/SKILL.md  # /prawduct-doctor — Health check and repair
│   └── settings.json           # Hook configuration
└── src/                        # Your product code
```

## Framework Layout

```
prawduct/
├── CLAUDE.md                   # 22 principles + methodology pointers
├── methodology/                # Narrative guides: discovery, planning, building, reflection
├── agents/critic/              # Independent per-chunk review agent
├── agents/pr-reviewer/         # Independent PR release-readiness reviewer
├── tools/                      # prawduct-setup.py (unified setup/sync/validate), product-hook
├── templates/                  # Artifact templates for generated products
├── tests/                      # Framework tests (pytest) and evaluation scenarios
├── docs/                       # Full principles with rationale, project structure
└── .prawduct/                  # Framework's own state, learnings, artifacts
```

## Architecture

Three layers:

1. **22 Principles** — Always in context via CLAUDE.md. Grouped into Quality, Product, Process, Learning, and Judgment. They govern how work gets done but don't enforce process interruptions.

2. **Methodology guides** — Narrative essays read when entering each activity (discovery, planning, building, reflection). They teach the approach rather than prescribing rigid steps. Governance depth scales with work size and type.

3. **Structural enforcement** — Python hooks that enforce what principles alone can't guarantee: session briefing with staleness detection on start, independent Critic review and reflection gates on stop, compliance canary checks for common governance failures. Zero external dependencies.

See [`docs/principles.md`](docs/principles.md) for the full principles with rationale and review perspectives.

## Recent Changes

### 1.3.0 (2026-03-30)
- refactor: Extracted `tools/lib/` modules (core, init, migrate, sync, validate) from monolithic setup script
- feature: Framework version tracking — sync records `framework_version` in manifest; session start warns if `../prawduct` is stale relative to last sync
- feature: Reflection gate is now advisory (not blocking) when no build plan is active — exploratory/Q&A sessions no longer require mandatory reflection
- feature: Comprehensive test coverage for all user onboarding journeys (750 tests)
- fix: V4_GITIGNORE_ENTRIES now matches GITIGNORE_ENTRIES (adds `.session-handoff.md`, `.test-evidence.json`, `.pr-reviews/`)
- fix: Critic changelog scope — only checks entries from current changeset, not historical entries
- fix: Gitignore hygiene — sync removes managed files from .gitignore if incorrectly added
- fix: Deprecation warnings when migrating v1/v3/partial repos

### Pre-1.3.0
- Critic is a Claude Code skill with structural tool restrictions (`allowed-tools` prevents test/build execution; `context: fork` preserves independence)
- Test evidence mechanism — builder records results; Critic reads evidence instead of re-running suites
- Critic Goal 7 "The Design Is Sound" — encapsulation, coupling, simplification, deduplication
- Security checks in Critic Goal 1 — injection, hardcoded secrets, input validation (BLOCKING)
- Critic coordinator pattern — medium/large reviews spawn parallel subagents
- PR reviewer agent and `/pr` skill — independent release-readiness review
- Work-scaled governance — depth scales with work size and type instead of rigid phases
- Session handoff, compliance canary, `--force` flag for sync, doc-only reflection skip

## License

MIT — see [LICENSE](LICENSE).
