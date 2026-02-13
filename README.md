# Prawduct

Prawduct turns product ideas into quality software.

LLM code generation is great. But product thinking is often missing — it's easy to go from "I need an app that does X" straight to code, without thinking about about users, edge cases, failure modes, and what "done" looks like. Prawduct fills that gap. It's the senior product thinker, software architect, and quality guardian that guides the entire process from idea through working, tested code.

Prawduct is designed to support everything from multi-tier web applications to headless utility scripts. Extensive internal reflection extracts learnings that improve the framework for future usage.

## Getting Started

Requires [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

1. Clone this repo
2. Open the directory in Claude Code
3. Say hello

The framework handles orientation and routing from there.

## What It Does

You describe what you want to build. The framework takes it from there:

- **Asks the questions you didn't know to ask** — about your users, their workflows, edge cases, failure modes, product scope, and security
- **Produces structured specifications** covering design, data, security, testing, operations, and dependencies — the artifacts that make code generation successful
- **Builds the product in governed chunks** — every piece reviewed against specs, every test verified, every dependency justified
- **Catches the things that usually go wrong** — requirements that silently vanish, tests that get weakened to pass, architecture that erodes over time, documentation that contradicts itself

The discovery process is a conversation. It adapts to you — a simple data cleaning utility gets lighter treatment than a B2B API handling financial transactions. Whether you bring a rough napkin sketch or a detailed spec, the framework meets you where you are and fills in what you don't have.

## What It Produces

A product build generates:

- **Product brief** — users, personas, flows, scope, success criteria
- **Data model** — entities, relationships, constraints
- **Security model** — auth, authorization, privacy, abuse prevention
- **Test specifications** — scenarios at all levels
- **Non-functional requirements** — performance, cost, uptime, scalability
- **Operational spec** — deployment, monitoring, alerting, recovery
- **Dependency manifest** — every external dependency justified
- **Build plan** — chunked, dependency-ordered, with acceptance criteria for each piece

The framework adapts to each product's shape — discovery depth, risk profiling, and build plan structure all adjust based on what concerns are active (UI, API, background automation, multi-party, etc.). Some concerns have dedicated artifact templates that add depth; others work through the universal artifact set.

## What It Is Not

- **Not a replacement for domain expertise.** If you're building a medical app, you still need medical knowledge. The framework ensures the product and engineering thinking is sound.
- **Not a form to fill out.** The discovery process is a conversation that adapts to you.

## Contributing

The framework governs its own development using the same process it applies to user products. All framework changes go through a 7-check governance review (the Critic), and the framework captures structured observations about its own performance during use.

See `docs/principles.md` for the hard rules that are never compromised.

## Project Layout

```
prawduct/
├── skills/                  # LLM instruction sets (six skills)
├── templates/               # Starting templates for product artifacts
├── tools/                   # Mechanical enforcement scripts
├── scripts/                 # Validation helper scripts
├── tests/scenarios/         # Evaluation rubrics for skill validation
├── docs/                    # Framework documentation
├── framework-observations/  # Captured learnings (structured, lifecycle-managed)
├── eval-history/            # Evaluation results (append-only)
└── working-notes/           # Ephemeral notes (2-week expiration)
```

See `CLAUDE.md` for the full project structure with per-file descriptions.
