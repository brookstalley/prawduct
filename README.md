# Prawduct

Prawduct is a framework for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) that adds structured product thinking, independent quality review, and continuous learning to AI-assisted software development.

## The Problem

Going from "I need an app that does X" straight to code skips the hard questions: Who are the users? What are the edge cases and failure modes? What does "done" look like? What needs to be tested, and how?

LLM code generation is powerful, but without discipline it produces code that drifts from requirements, skips edge cases, weakens tests to make them pass, and accumulates technical debt — all without telling you.

## How It Works

You describe what you want to build. Prawduct guides the process through four phases:

**Discovery** — Asks about your users, workflows, edge cases, security, and scope. Scales question depth to risk: a family utility gets 5-8 questions; a financial platform gets 15-25.

**Planning** — Produces structured specifications in dependency order: product brief, data model, security model, test specifications, non-functional requirements, and a chunked build plan. Artifacts are reviewed at phase boundaries before building starts.

**Building** — Implements the product in governed chunks. Each chunk follows a cycle: read spec, write tests first, implement, verify, then submit for independent Critic review. The Critic runs as a separate agent with no access to the builder's reasoning — it sees only the code and specs, catching things the builder's own context blinds it to.

**Reflection** — After each significant action, captures what happened, whether it was expected, and what it teaches. Learnings accumulate across sessions and directly influence future decisions.

## What Makes It Work

### Structural enforcement, not just instructions

The core insight: telling an LLM to "always do X" works until complexity or momentum takes over. Prawduct enforces the two behaviors Claude can't reliably self-regulate:

- **Critic review** — A session hook blocks completion if code was modified against a build plan but no independent review happened
- **Session reflection** — A session hook blocks completion if no reflection was captured

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

Learnings aren't just filed — they're read at session start and directly influence decisions. The framework's own development demonstrates this: the pattern "judgment alone won't interrupt momentum" (observed when Claude skipped Critic review despite being told not to) drove the architectural shift from principles-only governance to structural enforcement via hooks.

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
│   ├── project-state.yaml      # Phase, product definition, build plan, test tracking
│   ├── learnings.md            # Accumulated wisdom, read at session start
│   ├── critic-review.md        # Critic instructions for this product
│   ├── sync-manifest.json      # Tracks framework sync state
│   ├── artifacts/              # Specifications generated during planning
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

2. **Methodology guides** — Narrative essays read at phase entry points (discovery, planning, building, reflection). They teach the approach rather than prescribing rigid steps.

3. **Structural gates** — Python hooks that enforce the behaviors principles alone can't guarantee: independent review and session reflection. Zero external dependencies, validated via JSON structure checks and timestamp comparison.

See [`docs/principles.md`](docs/principles.md) for the full principles with rationale and review perspectives.
