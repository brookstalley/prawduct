# Prawduct

Prawduct turns product ideas into quality software — whether you're a developer who needs product discipline or a product thinker who needs faithful execution.

LLM code generation is great. But going from "I need an app that does X" straight to code skips the hard questions: Who are the users? What are the edge cases, failure modes, and what does "done" look like? What needs to be tested, and how? Prawduct fills those gaps. It's the senior product thinker, the software architect, and the quality guardian — guiding the process from idea through working, tested code, and then to iteration and improvement.

Prawduct supports everything from multi-user web applications to headless utility scripts. It adapts to you: if you bring deep product thinking, it focuses on faithful execution; if you bring technical skill, it fills in the product discipline. Extensive internal reflection extracts learnings that improve the framework over time — Prawduct itself is built and maintained using its own framework.

## Quick Start

**New to Prawduct?** See the [5-minute quickstart guide](docs/quickstart.md) or run:

```bash
~/.prawduct/framework/tools/prawduct-quick my-project
```

## Getting Started

### Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (Anthropic's AI-powered development CLI)
- Python 3.8+
- git
- PyYAML: `pip3 install pyyaml`

### Building a new product

1. Clone this repo to the well-known location: `git clone https://github.com/brookstalley/prawduct ~/.prawduct/framework`
2. Install dependencies: `pip3 install -r ~/.prawduct/framework/requirements.txt`
3. Open your project directory in Claude Code
4. Run: `python3 ~/.prawduct/framework/tools/prawduct-init.py --fix .`
5. Verify the setup: `python3 ~/.prawduct/framework/tools/prawduct-init.py --check .` (all checks should show "ok")
6. Say hello

The framework starts a conversation. It asks about your product idea, your users, edge cases, and scope. Based on your answers it produces structured specifications, then builds the product in governed chunks. A simple utility gets a lightweight process; a complex platform gets more depth. The whole thing adapts to you.

**Local-only mode:** If you don't want prawduct files committed to your repo (e.g., for personal projects or experiments), use `--local` during init:

```
python3 ~/.prawduct/framework/tools/prawduct-init.py --fix --local .
```

This stores prawduct hooks in `.claude/settings.local.json` (gitignored by Claude Code) instead of `settings.json`.

### Developing the framework itself

1. Clone this repo
2. `pip3 install -r requirements.txt`
3. Open the directory in Claude Code
4. Say hello

### Cloning a project that already uses Prawduct

If you clone a repo that was built with Prawduct, the CLAUDE.md bootstrap will guide framework installation. Install the framework to `~/.prawduct/framework/`, run `pip3 install -r ~/.prawduct/framework/requirements.txt`, and run `prawduct-init.py --fix .` to connect it.

## What It Does

You describe what you want to build. The framework takes it from there:

- **Asks the questions you didn't know to ask** — about your users, their workflows, edge cases, failure modes, product scope, and security
- **Produces structured specifications** covering design, data, security, testing, operations, and dependencies — the artifacts that make code generation successful
- **Builds the product in governed chunks** — every piece reviewed against specs, every test verified, every dependency justified
- **Catches the things that usually go wrong** — requirements that silently vanish, tests that get hacked to pass, architecture that erodes over time, documentation that contradicts itself
- **Observes its own operation and improves** — Prawduct runs internal critiques frequently, observing where the framework is not working as well as it should. These observations are stored, and can be used when applying Prawduct to itself.

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

The framework adapts to each product's structural characteristics — discovery depth, risk profiling, and build plan structure all adjust based on what's active (human interface, API, background automation, multi-party, sensitive data). Some characteristics have dedicated artifact templates that add depth; others work through the universal artifact set with dynamic domain-specific questions.

## What It Is Not

- **Not a replacement for domain expertise.** If you're building a medical app, you still need medical knowledge. The framework ensures the product and engineering thinking is sound.
- **Not a form to fill out.** The discovery process is a conversation that adapts to you.

## Terminology

Prawduct has its own vocabulary -- stages, structural characteristics, review lenses, hard rules, and more. See [`docs/glossary.md`](docs/glossary.md) for definitions.

## Contributing

The framework governs its own development using the same process it applies to user products. All framework changes go through a 9-check governance review (the Critic), and the framework captures structured observations about its own performance during use.

See `docs/principles.md` for the hard rules that are never compromised.

## Project Layout

```
prawduct/
├── skills/                  # LLM instruction sets (seven skills)
├── templates/               # Starting templates for product artifacts
├── tools/                   # Mechanical enforcement scripts
├── scripts/                 # Validation helper scripts
├── tests/scenarios/         # Evaluation rubrics for skill validation
├── docs/                    # Framework documentation
├── .prawduct/               # Framework's own prawduct outputs
│   ├── framework-observations/  # Captured learnings (structured, lifecycle-managed)
│   └── working-notes/           # Ephemeral notes (2-week expiration)
├── eval-history/            # Evaluation results (append-only)
└── .claude/                 # Claude Code config and governance hooks
```

See `CLAUDE.md` for the full project structure with per-file descriptions.
