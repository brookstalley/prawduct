# Prawduct

Prawduct turns product ideas into quality software — whether you're a developer who needs product discipline or a product thinker who needs faithful execution.

LLM code generation is great. But going from "I need an app that does X" straight to code skips the hard questions: Who are the users? What are the edge cases, failure modes, and what does "done" look like? What needs to be tested, and how? Prawduct fills those gaps. It's the senior product thinker, the software architect, and the quality guardian — guiding the process from idea through working, tested code, and then to iteration and improvement.

## Getting Started

### Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (Anthropic's AI-powered development CLI)
- git

### Building a new product

1. Clone this repo: `git clone https://github.com/brookstalley/prawduct`
2. Generate a product repo: `python3 prawduct/tools/prawduct-init.py ~/my-product --name "My Product"`
3. Open the generated directory in Claude Code
4. Tell it about your idea

The generated repo is fully self-contained — own CLAUDE.md, own hooks, own Critic instructions. No runtime dependency on the framework. Claude starts a conversation: asks about your product idea, users, edge cases, and scope. Based on your answers it produces structured specifications, then builds the product in governed chunks with independent quality review.

### Developing the framework itself

1. Clone this repo
2. Open the directory in Claude Code
3. Say hello

## What It Does

You describe what you want to build. The framework takes it from there:

- **Asks the questions you didn't know to ask** — about your users, their workflows, edge cases, failure modes, product scope, and security
- **Produces structured specifications** covering design, data, security, testing, operations, and dependencies
- **Builds the product in governed chunks** — every piece reviewed by an independent Critic agent, every test verified
- **Catches the things that usually go wrong** — requirements that silently vanish, tests that get hacked to pass, architecture that erodes over time
- **Learns from experience** — accumulated learnings improve future sessions

## What It Produces

A product build generates:

- **Product brief** — users, personas, flows, scope, success criteria
- **Data model** — entities, relationships, constraints
- **Security model** — auth, authorization, privacy, abuse prevention
- **Test specifications** — scenarios at all levels
- **Non-functional requirements** — performance, cost, uptime, scalability
- **Build plan** — chunked, dependency-ordered, with acceptance criteria

The framework adapts to each product's structural characteristics — discovery depth, risk profiling, and build plan structure all adjust based on what's active (human interface, API, background automation, multi-party, sensitive data).

## Architecture

Prawduct is built on three layers:

1. **22 Principles** — always in context via CLAUDE.md, governing how work gets done
2. **Methodology guides** — narrative essays for discovery, planning, building, and reflection
3. **Structural gates** — hooks that enforce the 2-3 behaviors Claude can't self-regulate (independent Critic review, session reflection)

Product repos are fully self-contained — own CLAUDE.md, own hooks, own Critic instructions. No runtime dependency on the framework repo.

See `docs/principles.md` for the full principles with rationale.

## Project Layout

```
prawduct/
├── CLAUDE.md               # 22 principles + methodology pointers
├── methodology/            # Narrative guides (discovery, planning, building, reflection)
├── agents/critic/          # Independent review agent
├── tools/                  # reflection-hook, product-hook, prawduct-init.py
├── templates/              # Artifact templates for products
├── tests/scenarios/        # Evaluation rubrics
├── docs/                   # principles, high-level design, project structure
└── .prawduct/              # Framework's own state, learnings, artifacts
```
