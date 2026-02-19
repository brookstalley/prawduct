# Quickstart Guide

Get from zero to your first Prawduct-guided product in 5 minutes.

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed
- Python 3.8+ with `pip3`
- git

## 1. Install (one command)

```bash
~/.prawduct/framework/tools/prawduct-quick my-project
```

This clones the framework (if needed), installs dependencies, and sets up your project directory. If you already have a project directory, point it there instead:

```bash
~/.prawduct/framework/tools/prawduct-quick /path/to/existing-project
```

**Manual setup** (if you prefer):

```bash
git clone https://github.com/brookstalley/prawduct ~/.prawduct/framework
pip3 install -r ~/.prawduct/framework/requirements.txt
python3 ~/.prawduct/framework/tools/prawduct-init.py --fix my-project
```

## 2. Open in Claude Code

```bash
cd my-project
claude
```

## 3. Describe your idea

Just tell it what you want to build. Even a rough idea works:

> "I want to build a simple app that tracks my family's board game scores"

The framework starts a conversation. It asks about your users, edge cases, and scope — calibrated to your idea's complexity. A simple utility gets a few questions. A complex platform gets more.

## 4. Watch it work

The framework guides you through:

1. **Discovery** — asks the questions you didn't know to ask
2. **Definition** — crystallizes scope, personas, and technical decisions
3. **Artifact generation** — produces structured specs (product brief, data model, test specs, etc.)
4. **Build planning** — breaks the work into governed chunks
5. **Building** — implements each chunk with quality review
6. **Iteration** — you try it, give feedback, it improves

At each step, it adapts to you. If you bring product expertise, it focuses on faithful execution. If you bring technical skill, it fills in the product discipline.

## 5. What just happened

Behind the scenes, Prawduct:

- **Classified your product** by its structural characteristics (human interface, API, automation, etc.)
- **Asked discovery questions** dynamically generated from your product's domain
- **Produced structured artifacts** that the AI coding agent uses as a build spec
- **Reviewed artifacts** through five evaluation perspectives (product, design, architecture, skeptic, testing)
- **Built in governed chunks** with a Critic reviewing each piece against the specs
- **Tracked quality** — test counts, spec compliance, scope discipline

The quality governance is automatic. You don't need to remember to run reviews or check tests — the framework handles it.

## What's next

- **Iterate:** After the first build, just tell it what you want to change
- **Learn more:** See the [README](../README.md) for full documentation
- **Contribute:** The framework observes its own performance and improves over time

## Troubleshooting

**"prawduct-quick: command not found"** — Run it with the full path: `~/.prawduct/framework/tools/prawduct-quick`

**"PyYAML not installed"** — Run: `pip3 install pyyaml`

**"Hook blocked my edit"** — The governance system requires the Orchestrator to be loaded first. Start a new conversation and say hello.

**"I want to start over"** — Delete the `.prawduct/` directory in your project and re-run `prawduct-init.py --fix .`
