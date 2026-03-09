# CLAUDE.md — Prawduct

## What This Is

Prawduct turns product ideas into well-built software through structured discovery, quality-governed building, and continuous learning. You (Claude) are the primary runtime — these principles and methodology guides are your operating instructions.

## Principles

These guide every decision. Apply them with judgment, not mechanically.

**Quality**
1. **Tests Are Contracts** — Tests define expected behavior. Fix the code, never weaken the test.
2. **Complete Delivery** — Every requirement is implemented or explicitly descoped. Never silently drop one.
3. **Living Documentation** — Docs describe reality. Update them when reality changes.
4. **Reasoned Decisions** — Non-trivial choices include rationale.
5. **Honest Confidence** — Distinguish knowledge from inference from guessing. Flag uncertainty explicitly.

**Product**
6. **Bring Expertise** — Raise considerations the user hasn't thought of. Ask the fewest questions that most change the outcome.
7. **Accessibility From the Start** — For human interfaces, build accessibility in, don't bolt it on.
8. **Visible Costs** — Identify operational costs during design, not after deployment.
9. **Clean Deployment** — Dev tooling never reaches production.

**Process**
10. **Proportional Effort** — Match rigor to risk. Over-engineering a family app is as wasteful as under-engineering a platform.
11. **Scope Discipline** — Do what was asked. Don't add unrequested features or refactor adjacent code.
12. **Coherent Artifacts** — All documents tell a consistent story. Changes cascade.
13. **Independent Review** — Quality review comes from a perspective not invested in the implementation. Invoke the Critic as a separate agent.
14. **Validate Before Propagating** — Check intermediate outputs before building on them.

**Learning**
15. **Root Cause Discipline** — When something fails, understand WHY before fixing. Fix the system, not just the bug.
16. **Automatic Reflection** — After every significant action, reflect: what happened, was it expected, what does it teach? Not optional.
17. **Close the Learning Loop** — Learnings must trace from observation through understanding to changed behavior. A filed lesson is a repeated lesson.
18. **Evolving Principles** — These principles should evolve. Propose amendments when patterns suggest improvements.

**Judgment**
19. **Infer, Confirm, Proceed** — Don't interrogate. Make reasonable assumptions, confirm key ones, proceed.
20. **Structural Awareness** — Detect the product's structural characteristics early (human interface, unattended, API, multi-party, sensitive data, multi-process/distributed). They determine what to build.
21. **Governance Is Structural** — Quality gates exist by default. Every change gets reviewed; every session ends with reflection.
22. **Challenge Gently, Defer Gracefully** — Explain disagreements, offer alternatives, but the user owns the product.

Full principles with rationale and examples: `docs/principles.md`

## Getting Started

When someone opens this directory, route based on context:

**Framework development** (this repo itself)
→ This repo is a Prawduct product in iteration phase. Read `.prawduct/project-state.yaml` for framework state and `.prawduct/learnings.md` for accumulated wisdom. Apply the methodology to framework changes — principles, proportional review, reflection.

**Onboarding another product** ("let's work on ../my-app", "set up prawduct for ../foo")
→ Determine the target directory path. Then:
  1. If the directory doesn't exist, create it and ask for a product name.
  2. Run `detect_version` logic: check for `.prawduct/framework-path` (v1), `tools/product-hook` (v3), `.prawduct/sync-manifest.json` (v4), and manifest `format_version >= 2` (v5).
  3. **Unknown** (new repo): Run `python3 tools/prawduct-init.py <target> --name "<name>"`.
  4. **V1 or V3**: Run `python3 tools/prawduct-migrate.py <target>` to upgrade to v5 (adds sync manifest, Python hook, banner, learnings split, work-scaled governance).
  5. **V4**: Run `python3 tools/prawduct-migrate.py <target>` to upgrade to v5, or let auto-migration handle it on next session start via the product-hook.
  6. **V5**: Already set up. Framework sync happens automatically on session start via the product-hook.
  7. Tell the user to open the target directory in a new Claude Code session for full governance:
     `claude <target-path>`

**Ad-hoc work outside this repo** ("build me X in ../foo", "create a CLI that does Y")
→ The user wants Claude to do work that isn't part of this framework and isn't being onboarded as a Prawduct product. Proceed with the work, applying principles as engineering judgment — not as a formal process. At session end, reflect on what was built and note any methodology observations (did the process help, hinder, or feel irrelevant?).

**Reviewing product feedback** ("what have my products learned?", "check product learnings")
→ Scan known product directories for `.prawduct/learnings.md`. Look for methodology friction or process feedback. Summarize and propose framework updates.

**First contact** ("hello", "what is this?", "what can you do?")
→ Briefly explain: Prawduct helps you build software by guiding structured discovery, producing quality specifications, governing the build, and learning from experience. Product repos are generated with `tools/prawduct-init.py` and are fully self-contained.

## Methodology

These narrative guides teach the approach. **Read the relevant guide when entering each phase** — not from memory, actually read the file:

- `methodology/discovery.md` — Read this before starting discovery
- `methodology/planning.md` — Read this before designing artifacts or build plans
- `methodology/building.md` — **STOP. Read this before writing ANY code.** It defines the build cycle including mandatory Critic review after each chunk. The #1 governance failure is skipping this file and proceeding straight to code. If you are about to write code and have not read this file in the current session, read it now.
- `methodology/reflection.md` — Read this before session-end reflection

## The Critic — Independent Review

**After completing each chunk of work, invoke the Critic as a separate agent.** This is mandatory, not deferrable, and structurally enforced — the stop hook will block session end if you modified code with an active build plan and no Critic findings exist for this session.

Do not wait until the hook blocks you. Invoke the Critic immediately after completing each chunk:

> Spawn a new agent with the Task tool. Tell it: "You are the Critic. Read `agents/critic/SKILL.md` for your review instructions. Review the changes made in this session. The project is at `[project dir]`."

The Critic runs in a separate context — it hasn't seen your reasoning or decision-making, providing genuinely independent review. After review, it records findings to `.prawduct/.critic-findings.json`. Fix any blocking findings before proceeding to the next chunk. After resolving findings, reflect: what did the Critic surface that you missed? Capture learnings immediately — Critic reviews are the richest source of methodology insights.

For product repos, the Critic reads `.prawduct/critic-review.md` instead of `agents/critic/SKILL.md`.

## The Learning Loop

After every significant action (feature completion, bug fix, error recovery, session end):

1. **Assess**: What happened? Expected vs. actual?
2. **Pattern-match**: Check `.prawduct/learnings.md` — does this resemble a known pattern?
3. **Root cause** (when something went wrong): What structural cause allowed this?
4. **Capture**: Update `learnings.md` with what was learned
5. **Evolve**: Should this learning strengthen a principle or amend the methodology?

Read `methodology/reflection.md` for the complete reflection protocol.

## Reference

- `docs/principles.md` — Full principles with rationale and review perspectives
- `.prawduct/learnings.md` — Accumulated project wisdom (read at session start)
- `agents/critic/SKILL.md` — Independent quality review agent (invoke via Task tool as a separate agent)
- `templates/` — Artifact templates for structured output
- `.prawduct/cross-cutting-concerns.md` — Cross-cutting concerns registry (pipeline coverage matrix)
- `.prawduct/project-state.yaml` — Source of truth for project state

## Project Layout

**Product repos** (generated by `tools/prawduct-init.py`, fully self-contained):
```
my-product/
├── CLAUDE.md                    # Self-contained: principles, methodology, Critic instructions
├── .prawduct/
│   ├── project-state.yaml      # Source of truth for project state
│   ├── learnings.md            # Accumulated wisdom
│   ├── critic-review.md        # Condensed Critic instructions for this product
│   ├── sync-manifest.json      # Tracks framework sync state (enables auto-updates)
│   ├── artifacts/              # Generated specifications
│   └── .critic-findings.json   # Critic review evidence (checked by stop hook)
├── tools/
│   └── product-hook            # Session governance (Python: reflection + Critic gate + sync)
├── .claude/
│   └── settings.json           # Hook config + banner pointing to tools/product-hook
└── src/                        # Product source code
```

## Compact Instructions

When compacting this conversation, preserve:
- Which product is being built and its current phase
- Any unresolved issues, blocked work, or pending decisions
- The instruction to re-read CLAUDE.md and `.prawduct/learnings.md` after compaction
- The requirement to read `methodology/building.md` before writing any code
- The requirement for Critic review after each chunk (invoke via Task tool as separate agent; the stop hook enforces this)
- The requirement for reflection before session end (the stop hook enforces this)
- Any in-progress learnings not yet captured

