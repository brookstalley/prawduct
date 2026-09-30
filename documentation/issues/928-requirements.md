# Issue #928 — Portable host adapters (Codex first, Gemini later): Requirements

`status: draft · stage: requirements · area: governance/plugin-runtime · added: 2026-09-30 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/928`

This document turns the proposal in #928 into requirements the owner can accept, amend or
reject. It does **not** decide the open questions in the issue (§ Decisions needed); it
narrows them with grounding from the tree and recommends an answer to each. Design (the
actual host contract, file layout) is the next stage and is deliberately not here.

## Problem

Prawduct's governance runs only under Claude Code. Someone who uses Codex (and later Gemini
CLI) cannot get the Critic, the Stop gates or the session briefing, so those users either go
ungoverned or fork the plugin — and a fork drifts. The proposer (Jason-Vaughan, a collaborator)
offers to build and **maintain** a Codex adapter, and to follow with Gemini, provided the
project agrees the host boundary first.

The observable problem to solve: *a repository governed by Prawduct can be worked in a second
harness with the same gates and the same `.prawduct/` evidence, without a second copy of the
governance logic.*

## Grounding facts

Measured on `develop`, 2026-09-30. Re-derive with the commands shown; do not copy the numbers.

- **The engine is mostly host-neutral.** `plugin/lib/` is 63 Python modules;
  `grep -rlE "CLAUDE_PLUGIN_ROOT|CLAUDE_PROJECT_DIR" plugin --include=*.py plugin/bin` finds the
  Claude-specific environment reads in a handful of files, concentrated in `bin/prawduct-hook`
  (root/project resolution near its top, plus worktree handling in `cmd_stop`) and `hooks/*.py`.
  `CLAUDE_PLUGIN_DATA` and `CLAUDE_ENV_FILE` are not used anywhere, so there is no host-managed
  persistent-data dependency to translate — all mutable state is already in the repo's `.prawduct/`.
- **The host-shaped surface is the hook payload/response protocol, not the logic.**
  `bin/prawduct-hook` (one ~9k-line dispatcher) reads Claude payload fields — `agent_type`
  (SubagentStop, `cmd_subagent_stop`), `last_assistant_message` / `transcript_path` /
  `background_tasks` (Stop, `lib/gates.py`) — and emits Claude response shapes:
  `{"systemMessage", "additionalContext"}` on Stop, and
  `{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext"}}` from
  `hooks/digest.py`. Exit-code semantics (exit 2 = block) are part of the contract too.
- **Registration is Claude-format.** `plugin/hooks/hooks.json` wires SessionStart (matchers
  `startup|resume|clear|compact|fork`), Stop, and SubagentStop (matcher
  `(^|:)critic-reviewer$`) via `${CLAUDE_PLUGIN_ROOT}`. Whether Codex/Gemini honour each matcher
  and event is a **live fact I have not verified** (the issue cites docs; those were not
  fetched in this session).
- **Skills and agents are Claude-format and carry safety-relevant frontmatter.**
  14 lines across `plugin/skills/*/SKILL.md` use `context: fork`, `allowed-tools` or
  `subagent_type`; `critic/SKILL.md` grants an explicit `Bash(...)` allowlist plus `Agent`.
  `agents/critic-reviewer.md` and `pr-reviewer.md` bound the reviewer by a `tools:` list that
  omits unrestricted Bash. Per `.claude/rules/learnings/core.md`, the tool *set* is the enforced
  boundary and `Bash(pattern)` granularity is *declared, not verified* — so Critic independence
  (invariant 3 in the issue) is only as strong as the target host's tool-restriction semantics.
- **Independence has a second mechanism: the no-execution contract plus deterministic
  consolidation.** Reviewers write partials; `critic-begin` → partials → `critic-consolidate`
  validates them into the shared evidence store (`plugin/skills/critic/SKILL.md`). This part is
  host-neutral and is what makes "reviewers judge, code consolidates" portable.
- **Prior art in the repo:** no `documentation/` or `.prawduct/artifacts/` document addresses
  multi-host support (grep for Codex/Gemini/"host-neutral" finds only unrelated hits). No
  unmerged proposal branch on `origin` concerns it (branches: `feat/*`, `docs/*`, `fix/*`
  listed by `git ls-remote --heads origin`). The claim "no prior art" is scoped to those searches.

## Requirements

Must / should are relative to the **Codex adapter reaching "supported"**; Gemini gets its own
requirements after the contract is proven (R-14).

### Core boundary

- **R-1 (must).** A written, versioned *host contract* enumerates every point where the core
  depends on the host: plugin-root resolution, project-root resolution, session identity, hook
  input fields consumed, hook output shapes and exit codes produced, reviewer dispatch, and
  tool-restriction semantics. It is derived from the code (the reads/emits listed in Grounding
  facts), not written from the proposal.
- **R-2 (must).** Host-specific reads and emits live behind that contract in one place. After the
  change, `grep` for host env-var names and hook-payload keys outside the adapter layer returns
  nothing. (Falsifying command to be defined in design; the Grounding-facts grep is the
  baseline and the current answer is "many sites in `prawduct-hook`".)
- **R-3 (must).** Claude Code behaviour is unchanged: the existing suite passes, and the Claude
  adapter is the contract's reference implementation, not a rewrite. A byte-level golden test of
  the hook outputs for SessionStart/Stop/SubagentStop before vs. after the refactor is the
  no-regression evidence.
- **R-4 (must).** One source of truth: skills, methodology, templates and agent prompts are
  generated or referenced from the canonical `plugin/` assets, never hand-copied into an adapter
  tree. A test fails if an adapter contains a canonical file that differs from its source.

### State and evidence

- **R-5 (must).** No new state schema. A repo alternately driven by Claude Code and Codex reads
  and writes the same `.prawduct/` files; a cross-host round-trip test (write evidence under one
  adapter, gate under the other) is required.
- **R-6 (must).** Session identity, worktree resolution and stop-gate scoping behave identically
  when the host does not export `CLAUDE_PROJECT_DIR`. Today the Stop path treats a worktree
  toplevel that differs from that variable as a signal (`cmd_stop`); the contract must say what
  the equivalent signal is per host, or state that the gate degrades and how loudly.

### Governance semantics

- **R-7 (must).** Fail closed on capability gaps. If a host cannot deliver an event the core
  relies on (SubagentStop, Stop with block semantics, SessionStart context injection), the
  adapter's doctor reports it and the gate does **not** silently become advisory. Where a
  documented backstop exists (idempotent consolidation at Stop), the contract names it.
- **R-8 (must).** Critic independence is demonstrated, not asserted: on the target host, a test
  shows the reviewer cannot write product files and cannot run arbitrary shell, using the
  host's *actual refusal* (per the learnings rule: never write "structurally enforced" without
  having watched the harness refuse it). If a host cannot meet this, that host's Critic runs as
  a separate constrained session or the adapter is not "supported" (see D-4).
- **R-9 (must).** Consolidation stays deterministic and host-agnostic: reviewer output enters via
  the existing `critic-consolidate` path with the same validation.
- **R-10 (should).** `doctor` gains an adapter-aware check: plugin active, hooks trusted and
  firing, host version inside the compatibility manifest, project state readable. It reports
  *not-verified* rather than *ok* for anything it cannot observe.

### Compatibility and release

- **R-11 (must).** A compatibility manifest records supported (Prawduct version × host version)
  pairs; an unsupported pair fails explicitly at session start.
- **R-12 (must).** Shared cross-host contract tests run against every adapter; CI runs the
  Claude adapter always and other adapters when their host CLI is available. A test that is
  skipped because a host is absent must say so in its output, not pass (a skip is not a pass).
- **R-13 (must).** Packaging tests prove the adapter bundle contains required assets and no
  internal development files (`.prawduct/`, `documentation/`, tests).
- **R-14 (should).** Gemini is a separate later requirements pass, gated on Codex meeting R-1–R-13
  and on a Gemini feasibility finding about reviewer independence (one session vs. a launched
  second session).

## Acceptance (Codex "supported")

The issue's 18-item checklist is accepted as the functional bar, with two amendments: (a) each
item is verified by a named test or a recorded live run — "hooks can be reviewed and trusted" and
"resume/compaction do not lose state" are live-host facts and go to the operator-verification
queue with the gate **on** (learnings: a deferral queue with a disabled gate is write-only);
(b) add R-3 (Claude golden test) and R-5 (cross-host round trip), which the checklist implies
but does not name.

## Out of scope

TangleClaw-specific behaviour; a Codex-specific evidence schema; rewriting the engine in another
language; an MCP server (unless a feasibility finding shows it is required); shipping Gemini in
the same change as Codex; weakening Critic independence to fit a host; any change to how Claude
Code users install or invoke Prawduct.

## Decisions needed (owner) — recommendations

The issue's seven questions collapse to four real forks; the rest follow.

- **D-1 Same repo vs. companion packages.** *Recommend: same repo, adapter under a dedicated
  directory, one release train.* The learnings on two-copies-of-one-idea, and the fact that the
  hook protocol is the volatile part, argue against version-skew between core and adapter; a
  companion package reintroduces the pinning problem the plugin already pays for.
- **D-2 Where the boundary sits.** *Recommend: the hook protocol (payload in, response out) plus
  path resolution — not the CLI subcommands.* The subcommand surface is internal (the plugin's
  own tooling has retired subcommands under an inert-retention rule); making it a public host
  contract freezes more than a host needs. Design must pick the concrete seam.
- **D-3 Claude-specific things that stay outside the portable core.** Candidate list for the
  owner to confirm: `context: fork` skill semantics; `Bash(pattern)` frontmatter grants; the
  plugin cache/pin model and `/prawduct:migrate` file-sync history; `CLAUDE.md` as the anchor
  (Codex would use `AGENTS.md`).
- **D-4 "Officially supported" bar.** *Recommend:* all R-1–R-13 met on the pinned host version
  range, with R-8 demonstrated live. Anything short is labelled *experimental*. Because the
  proposer commits to maintenance, name a single owner and a rule for what happens if that
  maintainer goes quiet (adapter demoted to experimental after N unreleased host versions).

## Risks

- **Independence erosion.** The largest risk is a host whose tool restrictions are weaker than
  Claude's. Mitigation is R-8 and D-4, not trust in the host's documentation.
- **Refactor blast radius.** Moving host reads out of a ~9k-line dispatcher touches the Stop gate.
  R-3's golden test and a delta review of the refactor commit are the controls.
- **Maintenance concentration.** The offer is one person's. See D-4.
- **Unverified host behaviour.** Codex/Gemini event names, matchers and blocking semantics come
  from the issue's links and were not verified here. The design stage's first task is a
  feasibility spike that records what each host *actually does* for each contract point.

## Next step

Owner answers D-1…D-4 on the issue. Then design stage: the concrete seam, the Codex feasibility
spike (issue's Phase 1) scoped to one skill, the session briefing, and one Stop gate, with a
live probe for each host-behaviour assumption.
