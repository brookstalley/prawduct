# AGENTS.md — Prawduct

## What This Is

Prawduct turns product ideas into well-built software through structured discovery, quality-governed building, and continuous learning. You (Claude) are the primary runtime — these principles and methodology guides are your operating instructions. Why prawduct exists and how it must evolve: `documentation/purpose.md`.

## Principles

The principles guide every decision. Apply them with judgment, not mechanically. The
always-injected session digest carries the roster, grouped; the full text with rationale and the
review perspectives is `plugin/docs/principles.md` (`/prawduct:methodology principles`), which is
where the count and the groups are defined rather than restated.

## Getting Started

When someone opens this directory, route on what they want:

| They want | Do this |
|---|---|
| **Framework development** (this repo) | It is a Prawduct product in active development. Read `.prawduct/project-state.yaml`; apply the methodology to framework changes like any other work. |
| **Onboard another product** — *"set up prawduct for ../foo"* | `/prawduct:onboard <target-path>` (it routes a pre-2.0 file-sync repo to `/prawduct:migrate`). Then tell the user to open the target in a new session — `claude <target-path>` — because governance loads at session start. `/prawduct:doctor` for an already-onboarded repo. |
| **Ad-hoc work outside this repo** — *"build me X in ../foo"* | Not framework work and not being onboarded. Do the work, applying the principles as engineering judgment rather than as process. Reflect at the end on whether the methodology helped, hindered, or was irrelevant — that observation is the only thing this repo gets out of it. |
| **Review product feedback** — *"what have my products learned?"* | Scan known product directories for `.claude/rules/learnings/`, looking for methodology friction; summarize it and propose framework updates. Also triage upstream bug reports about prawduct itself: they arrive as issues, the `untriaged-upstream-reports` advisory counts them, and staging one clears it (`/prawduct:backlog`; intake set and steps: `/prawduct:report-bug`). |
| **First contact** — *"what is this?"* | Prawduct helps you build software by guiding structured discovery, producing quality specifications, governing the build, and learning from experience. It installs as a Claude Code plugin; product repos commit a small install reference and no framework files. |

## Before Building: The Alignment Pass

When the user says "build X," "implement Y," or "let's add Z", run the alignment pass the session
digest describes before a plan exists: proceed, proceed citing a backlog item or spec, ask in one
batch, or hold up — and say which. Full text: `plugin/methodology/building.md` "Before You Build".

## Methodology

The narrative guides live in `plugin/methodology/`: `discovery.md`, `planning.md`, `building.md`,
`reflection.md`, `delegation.md`, `session-hygiene.md` — the reader carries each one's when-to-read.
**Read the one for the work you are entering — the file itself, not from memory.**

## The Critic — Independent Review

Each chunk's "Done when" says when to run `/prawduct:critic`: after acceptance criteria pass,
before marking it complete, or once at a short plan's boundary.

Two things bind you and are not restated by the skill you invoke. **Fix every blocking finding
before the next chunk** — `/prawduct:critic verify-resolutions` records the resolution facts that
unblock them. Then **reflect immediately**: what did the Critic surface that you missed? Critic
reviews are the richest source of methodology insights, and the insight decays fast.

Everything else is read with the plugin, not from here: `plugin/skills/critic/SKILL.md` for the
mechanics (the no-execution contract, the `critic-begin` → partials → `critic-consolidate` data
plane over the shared evidence store, and what a live review's marker does and does not
block), `review-cycle.md` for modes and the evidence model, `review-protocol.md` for goals and
severity, and `plugin/methodology/building.md` for the builder-side steps the skill does not
address to you.

## PR Review — Release Readiness

**Anything PR-shaped — "PR this", "create a PR", "push this up" — goes through `/prawduct:pr`**,
which handles the whole lifecycle (branch hygiene, review, create, update, merge) and dispatches an
independent reviewer for a fresh-eyes release-readiness assessment. Protocol:
`plugin/skills/pr/review-protocol.md`.

## The Learning Loop

Reflect at **work boundaries**, not at session end. When a chunk concludes (Critic passes), a bug
is fixed, an error is recovered from, or a judgment call is made — reflect *now*, while context is
fresh, into `.prawduct/.session-reflected`. The stop hook enforces only a session-end floor (the
assess and root-cause lines below), not this cadence.

Each time: **assess** (expected vs. actual), **pattern-match** against the learnings rules,
find the **root cause** when something went wrong, **capture** a narrative entry — adding a durable
rule to `.claude/rules/learnings/` only if this cycle earned one — and ask whether it should **evolve** a
principle or the methodology. Session-end then becomes a synthesis scan, not a from-scratch write.
Full protocol: `plugin/methodology/reflection.md`.

## Reference

- `plugin/docs/principles.md` — Full principles with rationale and review perspectives
- `.claude/rules/learnings/` — Accumulated project wisdom, harness-loaded (`core.md` always; areas on a matching read)
- `plugin/templates/` — Artifact templates for structured output
- `.prawduct/cross-cutting-concerns.md` — Cross-cutting concerns registry (pipeline coverage matrix)
- `.prawduct/project-state.yaml` — Source of truth for project state

## Project Layout

`documentation/project-structure.md` — both trees, annotated: this framework repo, and what a
plugin-governed product repo commits (its own state plus a small install reference; no framework
files). Governance — `/prawduct:*` skills, the SessionStart + Stop hooks, methodology, and the
Critic/PR protocols — comes from the **plugin**, not the repo.

## Running tests

Run tests with `testament run`, not `pytest` directly. It sends this worktree (uncommitted
and untracked files included; ignored files such as `.env` never leave the machine) to
testament's runners and streams the results back. If no coordinator answers, it runs the same
tests here under this machine's test-slot cap and says so.

If `testament` isn't installed: `uv tool install
git+ssh://git@github.com/brookstalley/testament@main` (or `git+https://…`), then
`testament guide machine`. Until it is, run `pytest` as before.

    testament run --json -- tests/unit/test_foo.py -k bar   # any pytest selection
    testament run --json                                     # the project's default suite

Read the JSON on stdout:

- `exit_code`: 0 all passed; 1 tests failed (a real red: fix it); 5 nothing collected;
  2 anything else, which is **not** a test result. Read `error.code`; when `error.retryable` is
  true, run again.
- `report.items[]`: one per test, with `outcome` (`passed`, `failed`, `error`, `skipped`),
  `message` (pytest's failure text for a failed or errored test) and `runner`.
- `report.missing`: tests that were requested but never reported. A non-empty list is exit 2
  (`population_mismatch`), never a pass.
- `fallback`: present when the tests ran on this machine instead of the runners. Flags
  that need one local pytest process (`-x`, `--maxfail`, `-n`, `--lf`) always run here;
  `fallback.reason` names the flag. Flags that need a terminal (`--pdb`, `-s`, `--co`) are
  refused under `--json`.
- `setup`: present when testament isn't fully set up for this repo or machine. The tests
  still ran; tell the person, and point them to the `guide` command it names.

`testament status` shows the runners and what's queued.

**Evidence still comes from the recorder.** A pool run can't yet be recorded as prawduct test
evidence: the recorder ingests JUnit (`test-evidence record --from-junit`), and `testament run`
writes only JSON until brookstalley/testament#52. Until then, record the boundary run with
`prawduct-hook test-evidence record`.

## Compact Instructions

When compacting, preserve: which product is being built and its current work (size, type,
description); unresolved issues, blocked work and pending decisions; and learnings not yet
captured. Governance is re-injected on compact by the session digest, so summarize what you
learned from methodology files and cite their paths rather than inlining them.

