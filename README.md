# Prawduct

Prawduct is a framework for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) that adds structured product thinking, independent quality review, and continuous learning to AI-assisted software development.

## The Problem

Going from "I need an app that does X" straight to code skips the hard questions: Who are the users? What are the edge cases and failure modes? What does "done" look like? What needs to be tested, and how?

LLM code generation is powerful, but without discipline it produces code that drifts from requirements, skips edge cases, weakens tests to make them pass, and accumulates technical debt — all without telling you.

## How It Works

You describe what you want to build. Prawduct scales governance to match the work:

**Discovery** — Asks about your users, workflows, edge cases, security, and scope. Scales question depth to risk: a family utility gets 5-8 questions; a financial platform gets 15-25. Discovery is continuous — new features need their own discovery.

**Planning** — Produces structured specifications in dependency order: product brief, data model, security model, test specifications, non-functional requirements, and a chunked build plan.

**Building** — Implements the product in governed chunks. Governance depth scales with work size (trivial → large) and type (bugfix → feature → refactor). Each chunk follows a cycle: read spec, write tests first, implement, verify, then submit for independent Critic review. The Critic runs as a separate agent with no access to the builder's reasoning — it sees only the code and specs, catching things the builder's own context blinds it to.

**Reflection** — After each significant action, captures what happened, whether it was expected, and what it teaches. Learnings follow a lifecycle (provisional → confirmed → incorporated) and accumulate across sessions.

## What Makes It Work

### Structural enforcement, not just instructions

The core insight: telling an LLM to "always do X" works until complexity or momentum takes over. Prawduct enforces governance at three levels:

- **Session briefing** — On session start, a staleness scan checks artifacts against code reality and delivers a structured briefing with project context, warnings, and active learnings
- **Critic review** — A session hook blocks completion if code was modified against a build plan but no independent review happened
- **Session reflection** — A session hook blocks completion if no reflection was captured
- **Compliance canary** — At session end, informational checks flag common governance failures (code without tests, dependencies without rationale, broad exception handling)

Everything else is governed by 22 principles and four methodology guides that stay in context via CLAUDE.md.

### Independent Critic review

The Critic is invoked as a separate agent (via Claude Code's agent/subagent capability), not as self-review in the same conversation. It has no access to the builder's reasoning or justifications — only the code, tests, and specifications. This structural separation catches blind spots that in-context review misses.

### Self-contained product repos

Generated product repos carry everything they need: own CLAUDE.md, own hooks, own Critic instructions, own learning history. No runtime dependency on the framework. Products work identically whether the framework repo exists or has been deleted.

This means:
- Products are portable and shareable
- The framework is a generator, not a runtime dependency
- Each product can evolve independently
- Framework updates propagate via automatic, edit-preserving sync — never overwrites your changes

### Proportional rigor

The framework detects structural characteristics (human interface, API, background automation, multi-party, sensitive data, distributed) and scales everything accordingly — discovery depth, artifact detail, test coverage, review intensity. A weekend project doesn't get enterprise governance; a platform doesn't get hobby-grade review.

### Closed learning loop

Learnings aren't just filed — they're read at session start and directly influence decisions. A two-tier system keeps active rules concise (<3K tokens in `learnings.md`) with full context in `learnings-detail.md`. Learnings follow a lifecycle: provisional (single observation) → confirmed (recurring pattern) → incorporated (absorbed into principles or methodology).

The framework's own development demonstrates this: the pattern "judgment alone won't interrupt momentum" (observed when Claude skipped Critic review despite being told not to) drove the architectural shift from principles-only governance to structural enforcement via hooks.

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
python3 prawduct/tools/prawduct-init.py ~/my-product --name "My Product"
cd ~/my-product
claude
```

Then describe what you want to build.

### Add Prawduct to an existing repo

```bash
python3 prawduct/tools/prawduct-init.py ~/existing-repo --name "My Existing Project"
cd ~/existing-repo
claude
```

Prawduct detects existing code and infers project conventions (language, test framework, code style) before making any changes.

### Develop the framework itself

```bash
cd prawduct
claude
```

## Generated Product Repo Structure

```
my-product/
├── CLAUDE.md                    # 22 principles + methodology (synced from framework)
├── .prawduct/
│   ├── project-state.yaml      # Product definition, work tracking, build plan
│   ├── learnings.md            # Active rules, read at session start (<3K tokens)
│   ├── learnings-detail.md     # Full learning context and history
│   ├── critic-review.md        # Goal-based Critic instructions for this product
│   ├── sync-manifest.json      # Tracks framework sync state
│   ├── artifacts/              # Specifications generated during planning
│   │   ├── boundary-patterns.md  # Contract surfaces between components
│   │   └── project-preferences.md # Developer preferences (language, testing, style)
│   ├── .subagent-briefing.md   # Generated briefing for delegated agents
│   └── .critic-findings.json   # Review evidence (checked by stop hook)
├── tools/
│   └── product-hook            # Session governance (Python, zero dependencies)
├── .claude/
│   └── settings.json           # Hook configuration
└── src/                        # Your product code
```

## Framework Layout

```
prawduct/
├── CLAUDE.md                   # 22 principles + methodology pointers
├── methodology/                # Narrative guides: discovery, planning, building, reflection
├── agents/critic/              # Independent review agent instructions
├── tools/                      # prawduct-init.py, prawduct-migrate.py, prawduct-sync.py, product-hook
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
