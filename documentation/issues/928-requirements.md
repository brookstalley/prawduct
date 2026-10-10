# Issue #928 — Portable host adapters (Codex first, Gemini later): Requirements

`status: draft · stage: requirements (D-1, D-2, D-4 ruled 2026-09-30) · area: governance/plugin-runtime · added: 2026-09-30 · source: scheduled
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
  (SubagentStop, `cmd_subagent_stop`), `last_assistant_message` / `background_tasks` (Stop,
  `lib/gates.py`) — and emits Claude response shapes. It reads no `session_id`,
  `transcript_path`, `stop_hook_active` or `hook_event_name`; those names appear only in
  docstrings. The response shapes are:
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
- **R-8 (must).** Critic independence on the target host is at parity with what Claude Code
  actually delivers, shown live and not asserted (owner ruling 2026-10-10, D-5). Three parts:
  (a) the host *refuses* any tool outside the reviewer's declared set (no edit tool), watched in
  a live test; (b) the reviewer starts from fresh context, without the builder's reasoning;
  (c) the reviewer's shell scope and write paths, which are a contract on Claude and not a fence,
  are backed by a host-neutral core check that fails the review when the working tree changed
  outside the reviewer's own files between `critic-begin` and consolidation. A host that cannot
  meet (a) and (b) runs its Critic as a separate constrained session, or the adapter is not
  "supported" (see D-4).
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

## Decisions (owner, 2026-09-30)

- **D-1 Same repo.** The adapter lives in this repo under a dedicated directory and ships on one
  release train with the core. A companion package would bring back the version-pinning problem
  the plugin already pays for, at the exact point (the hook protocol) most likely to move.
- **D-2 The boundary is the hook protocol plus path resolution.** Payload in, response out, and
  how the plugin and project roots are found. The `prawduct-hook` subcommands stay internal and
  free to change. Design picks the concrete seam.
- **D-3 Replaced by an inventory.** Instead of the owner guessing which Claude-specific pieces
  stay out of the core, § Host-surface inventory below lists every host-shaped surface the
  engine touches. The adapter author marks each one for Codex (supported, fallback, or
  unsupported) and proposes the seams. The owner rules on that proposal at design.
  One item is already decided: the governance anchor moves to `AGENTS.md`, and `CLAUDE.md`
  becomes the one line `@AGENTS.md` (narrowed from "plus Claude-only lines" on 2026-10-10, D-8).
  Claude Code reads `AGENTS.md` natively only when no `CLAUDE.md`, `.claude/CLAUDE.md` or
  `CLAUDE.local.md` exists in the working directory or above it, so the import is what makes it
  load in every Claude session. That change is #942 and ships independently of the adapter.
- **D-4 "Officially supported" means R-1 to R-13 met on a pinned host version range, with R-8
  shown live.** Anything short of that is labelled *experimental*. The adapter has one named
  maintainer, and it is demoted to experimental when it falls a set number of host releases
  behind without an update (the number is set at design).

## Decisions (owner, 2026-10-10): rulings on the inventory

Rulings on the decisions the adapter author's inventory proposal (PR #944) asked for. Row numbers
refer to § Host-surface inventory.

- **D-5 R-8 is a parity bar (rows 21, 23).** As written on 2026-09-30, R-8 asked the host to refuse
  arbitrary shell and product writes. Claude Code refuses neither: the reviewer's `Bash(...)`
  patterns and `Write` paths are a contract (`agents/critic-reviewer.md` says so), and
  consolidation validated only the partial. Codex was being held to a bar the Claude adapter
  fails. R-8 now requires host-enforced tool *set*, fresh context, and a host-neutral core check
  that the tree did not change outside the reviewer's files during the review. That check is #992 and
  benefits Claude independently of the adapter.
  - *Owner ruling 2026-10-10, on building #992.* A tree diff cannot say who changed a path, and
    `review-cycle.md` asks the builder to prep while a review runs. So a changed tree refuses
    consolidation without destroying the review, and the main session may consolidate with
    `critic-consolidate --tree-changed-by-builder "<reason>"`. That writes the paths and the reason
    into the review fact, and the PR payload's `review_tree_changes` section shows them to the
    independent PR reviewer. The hook and the session-end backstop never pass the flag. The
    check (c) still holds: no change goes unrecorded. Chosen over a strict fail (which loses valid
    reviews to builder prep) and over a warning-only record.
- **D-6 Protected paths stay core-owned (row 30).** `AGENTS.md` joins the protected-prose set as
  part of #942 (already in its acceptance criteria). Adapters may propose additive entries
  upstream and never remove one.
- **D-7 Core learnings reach Codex through SessionStart injection (rows 26, 27).** Claude keeps
  loading `.claude/rules/learnings/` through the harness, unchanged. The Codex adapter injects
  `core.md` as SessionStart context alongside the digest. Area learnings load on both hosts through
  the explicit `learnings-files --for-diff` read. Rejected: importing `core.md` from `AGENTS.md`
  (Codex documents no include syntax, and Claude would load it twice through rules), and inlining
  the rules into `AGENTS.md` (learnings would become protected prose, reopening the Critic gate on
  every new rule, and the learnings writer would edit a section of a user-owned file).
- **D-8 `CLAUDE.md` is the one line `@AGENTS.md` (row 29).** Deleting `CLAUDE.md` outright would
  fail open: a consumer's `CLAUDE.local.md`, or a `CLAUDE.md` in a parent directory, stops Claude
  reading `AGENTS.md` with no warning. The import costs nothing; Claude documents that it never
  loads `AGENTS.md` twice.
- **D-9 Context over the SessionStart limit is loud at session start (row 13).** The adapter
  measures the injected context when it builds it. Over the host's limit, it puts a one-line notice
  first in that context, raises a standing advisory that shows in every briefing until resolved,
  and doctor reports it too. Doctor alone runs too rarely. Design also checks the learnings budget
  gate against the host limit so learnings growth cannot cause the overflow.
- **D-10 D-2 scope.** In the supported contract: normalizing each host payload into one event shape,
  and root resolution. Skill packaging (rows 19, 24, 25, 36) is in, because gates depend on it,
  and canonical skill prose stays single-source (R-3, R-4). Out of the supported contract for now:
  install, provenance, repo-toggle and remedy-text rows (18, 31 to 34, 38), which are UX.

## Host-surface inventory

Every place the engine depends on Claude Code specifically, taken from `develop` at `2caeca96`
by searching the plugin (hook registrations, payload keys read, response shapes, `CLAUDE_*`
variables, skill and agent frontmatter, instruction files, plugin install paths). Paths are
under `plugin/`. Re-derive before relying on a row; the code moves.

**Class** is what the item means for governance on Claude today:
**gate** = a gate or the Critic's independence depends on it;
**fallback** = governance survives without it through a named backstop;
**UX** = presentation or convenience only.

The last two columns are for the adapter author: what Codex does for this item, and the seam
proposed for it.

| # | Surface | Where | Governance uses it for | Class | Codex | Proposed seam |
|---|---|---|---|---|---|---|
| 1 | SessionStart banner + digest (matcher `startup\|resume\|clear\|compact\|fork`) | `hooks/hooks.json`, `hooks/banner.py`, `hooks/digest.py` | Version banner; governance digest injected as context | fallback (`/prawduct:methodology`) | | |
| 2 | SessionStart split: `startup\|clear` runs `clear --session-start`; `resume\|compact\|fork` runs `--brief-only` | `hooks/hooks.json`; `cmd_clear` in `bin/prawduct-hook` | Session boundary vs continuation: resets markers, `.session-base-tree`, waivers, regenerates the handoff | gate | | |
| 3 | Session source comes from the matcher; the `source` payload field is never read | `hooks/hooks.json` | Boundary classification is done by registration | gate (adapter must map the host's source to the flag) | | |
| 4 | Stop hook, every turn | `hooks/hooks.json`; `cmd_stop`; `hooks/gates.json` | All session-end gates (reflection, Critic, PR, trivial, learnings, clear-verdict) | gate | | |
| 5 | Stop blocks by exit 2 with the reason on stderr, which the host feeds back to the model | `cmd_stop` | The blocking channel for every gate | gate | | |
| 6 | No `stop_hook_active` re-entry guard; blocking again on every Stop relies on Claude's exit-2 re-prompt loop | `cmd_stop` | Gate persistence across retries | gate (depends on the host's re-fire semantics) | | |
| 7 | Stop advisories at exit 0 as stdout JSON `{systemMessage, additionalContext}` | `bin/prawduct-hook` (advisory emit) | Deferral notes, non-blocking advisories | fallback | | |
| 8 | Stop payload `last_assistant_message` | `lib/gates.py` | The clear-verdict gate; the RUNNING + DO NOT CLEAR deferral | gate (clear-verdict); deferral degrades to block | | |
| 9 | Stop payload `background_tasks[]` | `lib/gates.py` | Defers blockers while a background task is in flight | fallback (absent means block as normal) | | |
| 10 | Stdin payload parsing tolerates empty or garbage input as `{}` | `bin/prawduct-hook` payload reader | Stop and SubagentStop input | gate (fails closed) | | |
| 11 | SubagentStop, matcher `(^\|:)critic-reviewer$`; payload `agent_type`, `cwd` | `hooks/hooks.json`; `cmd_subagent_stop` | Consolidates each Critic partial as its reviewer finishes | fallback (Stop consolidates idempotently) | | |
| 12 | SessionStart plain stdout goes into model context | `cmd_clear`; `hooks/banner.py` | Briefing, handoff, advisories, the new-gate relay | fallback | | |
| 13 | SessionStart JSON `hookSpecificOutput{additionalContext, reloadSkills}` and its size limit | `hooks/digest.py` | Governance digest; skill-cache refresh in the framework repo | fallback | | |
| 14 | `statusMessage` on each hook | `hooks/hooks.json` | Spinner text | UX | | |
| 15 | Retired hook subcommands kept inert because the host pins hooks.json lazily | `bin/prawduct-hook` | Old registrations must exit 0 silently | UX (compat) | | |
| 16 | `${CLAUDE_PLUGIN_ROOT}` in hook commands and code | `hooks/hooks.json`; `bin/prawduct-hook`; `hooks/*.py` | Finds `lib/`, the manifest version, the gate registry | gate (code falls back to its own path) | | |
| 17 | `CLAUDE_PROJECT_DIR` | `bin/prawduct-hook`; `hooks/*.py`; `lib/gitstate.py` | Project root; worktree redirect in the Stop path | gate (falls back to cwd or worktree toplevel) | | |
| 18 | `CLAUDE_CONFIG_DIR` and `~/.claude*` roots | `hooks/banner.py`; `lib/plugin_activation.py`; `lib/stranded_work.py` | Install detection; transcript roots for liveness | UX / fallback | | |
| 19 | `${CLAUDE_SKILL_DIR}` in skill prose | critic, pr, methodology, janitor, runbook, report-bug skills; `lib/buildplan_refs.py` | Loading the Critic and PR protocols and the methodology guides next to their skill | gate in effect | | |
| 20 | Transcript directory mtimes (content never read) | `lib/stranded_work.py` | Worktree liveness in the briefing and `worktrees` | fallback (reflog, session markers, file mtimes) | | |
| 21 | Reviewer agents' `tools:` allowlists (`Bash(pattern)`, `Write`) | `agents/critic-reviewer.md`, `agents/pr-reviewer.md` | Reviewer isolation. On Claude the tool *set* is enforced; `Bash` patterns and `Write` paths are a contract the reviewer keeps, backed by consolidation validating each partial and refusing a review during which the working tree changed outside prawduct's session files (#992) | gate (R-8) | | |
| 22 | `model: inherit`; `omitClaudeMd: true` on the PR reviewer | `agents/*.md` | Same-model review; PR reviewer isolated from instructions and memory | fallback (isolation weakens) | | |
| 23 | Subagent dispatch through the Agent tool, three reviewers concurrently | `skills/critic/coordinator.md`; `skills/pr/SKILL.md` | Independent multi-role Critic; the PR reviewer | gate (single-pass roster is the fallback) | | |
| 24 | Skill frontmatter `context: fork` | critic, backlog, advisory skills | Critic runs outside the builder's context; backlog out of main context | gate (critic), UX (others) | | |
| 25 | Skill frontmatter `allowed-tools` with `Bash(...)` grants and deny patterns; `$ARGUMENTS`; `argument-hint`; `disable-model-invocation` | `skills/*/SKILL.md` | What each skill may run; argument passing | fallback / UX | | |
| 26 | `.claude/rules/learnings/core.md` loaded every session by the harness | `lib/learnings_files.py`; `lib/init_product.py` | Durable rules in context; the core budget gate assumes that load cost | gate | | |
| 27 | Area learnings loaded when a file matching `paths:` is read | `lib/learnings_files.py`; `agents/pr-reviewer.md` | `learnings-files --for-diff` mirrors what the harness loaded; Critic cross-check | gate (a host without on-read loading needs an explicit read) | | |
| 28 | Learnings gates (unmigrated, over-budget, budget-unreasoned, rule length) | `hooks/gates.json`; `cmd_stop` | Keep the corpus shaped for harness autoload | gate | | |
| 29 | Governance anchor in `CLAUDE.md` (moving to `AGENTS.md`, see D-3) | `lib/migrate_plugin.py`; `lib/anchor_repair.py`; `lib/init_product.py`; `lib/onboarding_probes.py` | Plugin-absent notice; points the agent at the methodology | fallback | | |
| 30 | Judgeability treats root `CLAUDE.md`, `skills/`, `agents/`, `methodology/`, `templates/` as protected and `.claude/settings.json` as metadata | `lib/buildplan_refs.py`; `lib/gitstate.py`; `lib/coverage_algebra.py` | What reopens the Critic gate; the doc-only fast path | gate (`AGENTS.md` would be misclassified today) | | |
| 31 | `.claude/settings.json` install reference (`extraKnownMarketplaces`, `enabledPlugins`) | `lib/migrate_plugin.py`; `lib/init_product.py`; install-reference probes | Onboard, migrate, doctor, the drift advisory | fallback | | |
| 32 | Per-repo disable via `.claude/settings.local.json` `enabledPlugins` | `lib/repo_toggle.py`; `skills/repo-disable` | Opt out per repo | UX | | |
| 33 | Reads `~/.claude/plugins/installed_plugins.json` and names `known_marketplaces.json` | `lib/plugin_activation.py`; install-reference probes | `check-plugin-active` during onboarding | fallback (answers `unknown` on doubt) | | |
| 34 | Managed install vs `--plugin-dir` checkout detection | `hooks/banner.py` | Provenance in the banner | UX | | |
| 35 | Version from `.claude-plugin/plugin.json` vs `.prawduct/.prawduct-version` | `bin/prawduct-hook`; `hooks/banner.py` | Gate attribution; new-gate announcements | fallback | | |
| 36 | Plugin `bin/` on the Bash PATH (bare `prawduct-hook`) | every skill, agent and methodology file that runs it | Every skill-driven gate write (critic-begin, consolidate, evidence, PR review) | gate | | |
| 37 | Harness worktree naming (`.claude/worktrees/agent-*`, `wf_*`) | `lib/gitstate.py`; `bin/prawduct-hook` | Refuse `.prawduct/` writes that would strand in a disposable worktree | fallback (without it, writes strand silently) | | |
| 38 | `/prawduct:*` command names in gate and briefing text | `bin/`, `lib/`, `hooks/`, skills | Remedy text in blocking messages | UX | | |
| 39 | Session model: `/clear` is a boundary; resume, compact and fork continue; the SAFE TO CLEAR / DO NOT CLEAR block | `methodology/`; `hooks/session-digest.md`; `cmd_clear`; clear-verdict gate | Boundary resets; the clear-verdict gate parses those labels from `last_assistant_message` | gate | | |

Not host-specific but external: the Stop PR check shells out to `gh`; hooks.json sets no
`timeout`, so the host default applies; telemetry assumes Anthropic model ids.

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

The inventory is filled (PR #944) and ruled on (D-5 to D-10). Next, the adapter author posts the
evidence the inventory cites (F1, O1, O4, O5, E5) on #928. Then the R-8 probe against the parity
bar: does Codex refuse a tool outside the reviewer's declared set, in-session or as a separate
constrained session? Then design: the concrete seam, and the Codex feasibility spike (the issue's
Phase 1) scoped to one skill, the session briefing and one Stop gate, with a live probe for each
host-behaviour assumption.
