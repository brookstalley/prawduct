# Issue #928 — Portable host adapters (Codex first, Gemini later): Requirements

`status: draft · stage: requirements (D-1 to D-12 ruled, 2026-09-30 to 2026-10-13) · area: governance/plugin-runtime · added: 2026-09-30 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/928`

This document turns the proposal in #928 into requirements, grounded in the tree. The owner's
rulings on its open questions are recorded in the three Decisions sections below (D-1 to
D-12). Design (the actual host contract, file layout) is the next stage and is deliberately
not here.

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
  `{"systemMessage"}` on Stop at exit 0 (user-only, #822), and
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
  between `critic-begin` and consolidation outside prawduct's own session files (D-11). A host that cannot
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
  that the tree did not change outside prawduct's session files during the review (scope: D-11). That check is #992 and
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

## Decisions (owner, 2026-10-13): answers to PR #944

- **D-11 R-8(c) is scoped to what #992 checks (row 21).** R-8(c) said "outside the reviewer's own
  files". #992 exempts every path in `core.GITIGNORE_ENTRIES`, and gitignored paths never enter
  the tree it captures. The wording now matches the code. Narrowing the code to the reviewer's
  marker and partial would refuse a review whenever the builder writes its own session files
  during it (handoff notes, test evidence, the ledger), which `review-cycle.md` asks it to do. That
  would charge the builder on every review cycle to close a small gap. Known residual: a reviewer
  could write to the ledger or another reviewer's partial without being caught. That gap is the
  same on Claude, so it is not a Codex parity gap, and partial validation at consolidation is
  still the backstop.
- **D-12 The plugin-cache report stays in rows 18 and 33.** It reads config roots (row 18) and
  installed-plugin state (row 33), and it is doctor hygiene. Like those rows, it is outside the
  supported contract (D-10). It needs no row of its own.

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

Evidence labels for the Codex 0.156.1 mapping:

- **F1:** [Bounded non-interactive Stop and R-8 probe record](https://github.com/brookstalley/prawduct/issues/928#issuecomment-6115715618), Codex CLI `0.156.1`; a project-hook Stop fixture passed its bounded matrix, while reviewer tool refusal was not reached.
- **O1:** [Official Codex Hooks documentation](https://learn.chatgpt.com/docs/hooks), current unversioned documentation consulted for the `0.156.1` mapping.
- **O4:** [Official Codex Subagents documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents), current unversioned documentation consulted for the `0.156.1` mapping.
- **O5:** [Official Codex Worktrees documentation](https://learn.chatgpt.com/docs/environments/git-worktrees), current unversioned desktop-app documentation consulted for the `0.156.1` mapping; it is not a stable CLI worktree-path contract.
- **E5:** [Independent 39-row inventory analysis and reconciliation](https://github.com/brookstalley/prawduct/issues/928#issuecomment-6115715618), Codex CLI `0.156.1`; analysis rather than an additional live test.

Per D-10, the supported host contract includes normalized event payloads, root resolution, and skill packaging (rows 19, 24, 25, and 36). Install, provenance, repo-toggle, and remedy-text rows (18, 31–34, and 38) remain UX proposals outside that contract for now. The read-only plugin-cache surface (`lib/plugin_caches.py`) belongs in rows 18 and 33 (D-12).

| # | Surface | Where | Governance uses it for | Class | Codex | Proposed seam |
|---|---|---|---|---|---|---|
| 1 | SessionStart banner + digest (matcher `startup\|resume\|clear\|compact\|fork`) | `hooks/hooks.json`, `hooks/banner.py`, `hooks/digest.py` | Version banner; governance digest injected as context | fallback (`/prawduct:methodology`) | **Supported primitive from documentation; not observed on pinned `0.156.1`.** `SessionStart` supports `startup`, `resume`, `clear`, and `compact`, and plain text or JSON additional context reaches the model. The absent `fork` source is dispositioned in rows 2 and 39. | Host adapter maps the four native sources and treats reviewer/subagent creation separately; retain `/prawduct:methodology` equivalent as a doctor-visible fallback. |
| 2 | SessionStart split: `startup\|clear` runs `clear --session-start`; `resume\|compact\|fork` runs `--brief-only` | `hooks/hooks.json`; `cmd_clear` in `bin/prawduct-hook` | Session boundary vs continuation: resets markers, `.session-base-tree`, waivers, regenerates the handoff | gate | **Partial/fallback.** Codex documents `startup`, `resume`, `clear`, and `compact` SessionStart sources. The [Codex CLI docs](https://learn.chatgpt.com/docs/developer-commands) describe root-chat fork commands, but O1 documents no `fork` SessionStart source; a subagent start is a different lifecycle event. The boundary behavior of a root fork is unverified on pinned `0.156.1`. | After core's host-neutral tolerant JSON parse, the adapter reads the host `source` key and normalizes a `session_boundary` enum; core invokes `clear --session-start` or `--brief-only`. An unsupported source fails closed rather than guessing. |
| 3 | Session source comes from the matcher; the `source` payload field is never read | `hooks/hooks.json` | Boundary classification is done by registration | gate (adapter must map the host's source to the flag) | **Partial/fallback.** Codex supplies `source` and applies the matcher to it, but documents no `fork` source. | After host-neutral parsing, the adapter alone reads host payload keys and emits a normalized event; core consumes that event. Unknown/missing gate-relevant sources fail closed. |
| 4 | Stop hook, every turn | `hooks/hooks.json`; `cmd_stop`; `hooks/gates.json` | All session-end gates (reflection, Critic, PR, trivial, learnings, clear-verdict, clear-reason) | gate | **Supported primitive.** Codex exposes synchronous `Stop`; F1 observed a bounded repeated sequence. | Register one host Stop entry that calls the host-neutral stop evaluator through the adapter. |
| 5 | Stop blocks by exit 2 with the reason on stderr, which the host feeds back to the model | `cmd_stop` | The blocking channel for every gate | gate | **Supported with evidence limit.** Official contract supports it; F1 directly observed continuations and captured hook intent/host streams, but inner exit/stderr attribution is derived. | Adapter owns Codex output/exit translation while core returns a host-neutral block decision and reason. |
| 6 | No `stop_hook_active` re-entry guard; blocking again on every Stop relies on Claude's exit-2 re-prompt loop | `cmd_stop` | Gate persistence across retries | gate (depends on the host's re-fire semantics) | **Supported for the bounded matrix.** Three unchanged-gate continuations, independent gate opening, and fourth completion were observed. Codex also supplies `stop_hook_active`. | Core stays stateless; adapter forwards every Stop to core and does not suppress retries merely because `stop_hook_active` is true. |
| 7 | Stop advisories at exit 0 as stdout JSON `{systemMessage}` (user-only); at exit 2 on stderr beside the blockers (#822). A `_LogOnlyAdvisory` (the Critic gate's deferral notes) stays in the stderr log at exit 0 and reaches the transcript only beside a block | `bin/prawduct-hook` (`_deliver_stop_advisories`) | Non-blocking advisories; deferral notes only at exit 2 | fallback | **Partial/fallback.** `systemMessage` is supported; Claude's Stop has no non-continuing model channel either, so neither host needs one. | Core emits `Advisory{text, audience}`; Codex initially renders it as `systemMessage`, and any model-steering context requires an explicitly documented Codex shape. |
| 8 | Stop payload `last_assistant_message` | `lib/gates.py` | The clear-verdict and clear-reason gates; the RUNNING + DO NOT CLEAR deferral | gate (clear-verdict, clear-reason); deferral degrades to block | **Not verified for the gates.** O1 documents `last_assistant_message` as string or null, but F1 exercised neither clear-verdict nor clear-reason parsing or preserved text behavior. | Normalize null and absent distinctly; keep the existing block path until fixtures and an authorized live test prove text, size, newline, and both clear-verdict/clear-reason parsing behaviors. |
| 9 | Stop payload `background_tasks[]` | `lib/gates.py` | Defers blockers while a background task is in flight | fallback (absent means block as normal) | **Partial/fallback.** The field is absent from the documented Codex Stop payload, but upstream already defines absence as “block as normal.” | Optional host capability; absence follows the existing named backstop and blocks normally rather than deferring. |
| 10 | Stdin payload parsing tolerates empty or garbage input as `{}` | `bin/prawduct-hook` payload reader | Stop and SubagentStop input | gate (fails closed) | **Supported existing core behavior.** Upstream locates the tolerance in `bin/prawduct-hook`'s payload reader; Codex supplies JSON in the normal path, but no host primitive is needed for the fallback. | Core keeps the host-neutral tolerant byte-to-JSON parse and maps empty/garbage input to `{}`; the adapter then reads only host-specific keys and normalizes them; core gates consume the normalized event and fail closed. |
| 11 | SubagentStop, matcher `(^\|:)critic-reviewer$`; payload `agent_type`, `cwd` | `hooks/hooks.json`; `cmd_subagent_stop` | Consolidates each Critic partial as its reviewer finishes | fallback (Stop consolidates idempotently) | **Partial/fallback.** O1 documents `SubagentStop`, a matcher on `agent_type`, and common hook input `cwd`; it does not establish that `cwd` identifies a distinct subagent worktree. F1 did not exercise reviewer rendezvous. Stop consolidation remains the idempotent backstop. | After core's tolerant parse, the adapter reads the documented common `cwd` and event-specific `agent_type`/`agent_id`, resolves project identity structurally, and emits a normalized subagent event. A fixture and authorized live test must establish any separate subagent-worktree meaning before it is used for a gate. Core retains idempotent Stop consolidation; doctor reports unavailable or untrusted hooks. |
| 12 | SessionStart plain stdout goes into model context | `cmd_clear`; `hooks/banner.py` | Briefing, handoff, advisories, the new-gate relay | fallback | **Supported from documentation; not observed on pinned `0.156.1`.** Plain stdout becomes extra developer context. | Host renderer may use plain text for the brief; canonical content remains generated from shared core state. |
| 13 | SessionStart JSON `hookSpecificOutput{additionalContext, reloadSkills}` and its size limit | `hooks/digest.py` | Governance digest; skill-cache refresh in the framework repo | fallback | **Partial/fallback.** O1 documents `hookSpecificOutput.additionalContext` and the handler's `additionalContextLimit`; neither O1 nor E5 documents a Codex `reloadSkills` output. | Normalize `additional_context` and budget the SessionStart digest plus core learnings against the configured Codex handler's approximate `additionalContextLimit`, with margin for other context. If oversized, put a one-line notice first in the emitted context, keep a standing briefing advisory until resolved, and report it in doctor. Test that notice delivery/order on pinned Codex; do not treat the handler threshold as a global hard context cap. Check learnings growth against the same budget. Treat `reloadSkills` as unverified and do not silently claim it. |
| 14 | `statusMessage` on each hook | `hooks/hooks.json` | Spinner text | UX | **Supported UX from documentation; not observed on pinned `0.156.1`.** | Keep status text in host registration metadata, outside core gate decisions. |
| 15 | Retired hook subcommands kept inert because the host pins hooks.json lazily | `bin/prawduct-hook` | Old registrations must exit 0 silently | UX (compat) | **Supported existing core compatibility behavior.** Keeping inert commands needs no Codex primitive; whether Codex has Claude's lazy-pinned-registration hazard is not established. | Preserve core no-op compatibility commands while any shipped registration can still reference them; adapter registers only current events and makes no cross-host lazy-pinning claim. |
| 16 | `${CLAUDE_PLUGIN_ROOT}` in hook commands and code | `hooks/hooks.json`; `bin/prawduct-hook`; `hooks/*.py` | Finds `lib/`, the manifest version, the gate registry | gate (code falls back to its own path) | **Supported from documentation; not observed on pinned `0.156.1`.** Plugin hooks receive `PLUGIN_ROOT`; compatibility variables `CLAUDE_PLUGIN_ROOT` and `CLAUDE_PLUGIN_DATA` are also set. | Canonical host contract uses a neutral plugin-root input; Codex adapter prefers `PLUGIN_ROOT`, Claude adapter supplies its native root. |
| 17 | `CLAUDE_PROJECT_DIR` | `bin/prawduct-hook`; `hooks/*.py`; `lib/gitstate.py` | Project root; worktree redirect in the Stop path | gate (falls back to cwd or worktree toplevel) | **Partial/fallback.** Hook payload supplies `cwd`; Git can resolve the toplevel. No Codex analogue to `CLAUDE_PROJECT_DIR` is established, and O5's managed-worktree details are desktop-app documentation rather than a stable CLI contract. | Central `resolve_project_root(host,cwd,git)` returns root plus structural Git worktree identity; if either is unproven, the dependent gate refuses rather than trusting a host path convention. |
| 18 | `CLAUDE_CONFIG_DIR` and `~/.claude*` roots | `hooks/banner.py`; `lib/plugin_activation.py`; `lib/stranded_work.py`; `lib/plugin_caches.py` | Install detection; transcript roots for liveness; read-only unused-plugin-cache report | UX / fallback | **Partial/fallback.** Codex uses `~/.codex`; hooks provide `transcript_path`, whose format is explicitly unstable. Plugin activation is configured through Codex plugin/config surfaces. | Host capability object supplies config root, plugin activation, and optional transcript liveness path; never parse transcript contents. |
| 19 | `${CLAUDE_SKILL_DIR}` in skill prose | critic, pr, methodology, janitor, runbook, report-bug skills; `lib/buildplan_refs.py` | Loading the Critic and PR protocols and the methodology guides next to their skill | gate in effect | **Partial/fallback; Claude form unsupported.** No equivalent variable is established, but Codex skills package colocated references and scripts. | Propose portable relative resource references or a generated host launcher that resolves the active skill directory. Until packaging proof exists, affected gates remain unavailable/fail closed. Any edit to canonical Claude-facing skill prose must preserve R-3 and R-4 and requires upstream review. |
| 20 | Transcript directory mtimes (content never read) | `lib/stranded_work.py` | Worktree liveness in the briefing and `worktrees` | fallback (reflog, session markers, file mtimes) | **Partial/fallback.** A transcript path may exist, but its format and availability are not stable contracts. | Treat transcript mtime as an optional host signal behind the existing reflog/session-marker/file-mtime backstops. |
| 21 | Reviewer agents' `tools:` allowlists (`Bash(pattern)`, `Write`) | `agents/critic-reviewer.md`, `agents/pr-reviewer.md` | Reviewer isolation. On Claude the tool *set* is enforced; `Bash` patterns and `Write` paths are a contract the reviewer keeps, backed by consolidation validating each partial and refusing a review during which the working tree changed outside prawduct's session files (#992) | gate (R-8) | **Not verified for R-8; direct Claude `tools:` form unsupported.** O4 documents no per-agent exact tool allowlist and says subagents inherit the parent sandbox. F1's attempted constrained subject self-reported forbidden surfaces and omitted all five approved tools, so no tested topology reached the refusal test. | Under D-5, require a live Codex host refusal of a tool outside the reviewer’s declared set and fresh reviewer context; either in-session or separate-session dispatch may qualify. Core #992 compares the dispatch and consolidation trees, but its current implementation exempts all Prawduct session entries and gitignored paths, not solely the reviewer’s own files; D-11 rules that this is the scope R-8(c) requires. Older manifests without `dispatch_tree` return `unrecorded` and still consolidate, so the new check is not enforced for them. Only the main session may pass `critic-consolidate --tree-changed-by-builder <reason>`, which records paths and the builder’s attestation for independent PR review, not proof of authorship. Hooks and Stop cannot pass the flag. F1 reached no undeclared-tool refusal; R-8 remains unverified and the Critic gate closed. Exact shell-pattern scoping is not required. |
| 22 | `model: inherit`; `omitClaudeMd: true` on the PR reviewer | `agents/*.md` | Same-model review; PR reviewer isolated from instructions and memory | fallback (isolation weakens) | **Partial/fallback.** Custom agents can select a model/sandbox/MCP/skills and otherwise inherit settings; no exact `omitClaudeMd` equivalent is established. | Define explicit reviewer profile inputs: model policy, context seed, instruction sources, sandbox, and tool manifest. Refuse unsupported omission/isolation claims. |
| 23 | Subagent dispatch through the Agent tool, three reviewers concurrently | `skills/critic/coordinator.md`; `skills/pr/SKILL.md` | Independent multi-role Critic; the PR reviewer | gate (single-pass roster is the fallback) | **Partial/fallback.** Codex supports concurrent subagents, but F1 did not prove the constrained Critic tool surface. | Host dispatch may run the roster concurrently only after the R-8 tool-set refusal, fresh-context and #992 tree-change requirements are proved for its actual topology. D-5 permits either in-session or separate-session dispatch; neither is presumed necessary or sufficient. The upstream single-pass roster remains the named backstop. Any durable `.prawduct/` field is a Brooks-owned R-5/R-9 format proposal. |
| 24 | Skill frontmatter `context: fork` | critic, backlog, advisory skills | Critic runs outside the builder's context; backlog out of main context | gate (critic), UX (others) | **Partial/fallback; Claude form unsupported.** Codex has subagents but no established automatic mapping from this field. | Propose a small skill-manifest translator: Critic becomes explicit fresh-context dispatch; UX-only forks may run inline when declared safe. Upstream names no fallback for this row, so isolation-sensitive dispatch blocks until the translation is proven. |
| 25 | Skill frontmatter `allowed-tools` with `Bash(...)` grants and deny patterns; `$ARGUMENTS`; `argument-hint`; `disable-model-invocation` | `skills/*/SKILL.md` | What each skill may run; argument passing | fallback / UX | **Partial/fallback; direct format unsupported.** Codex skills use `SKILL.md`; tool policy belongs in agent/config/MCP policy, not presumed Claude frontmatter. | Separate portable skill instructions from host dispatch/policy metadata; translate arguments explicitly and fail closed on an unrepresentable safety restriction. |
| 26 | `.claude/rules/learnings/core.md` loaded every session by the harness | `lib/learnings_files.py`; `lib/init_product.py` | Durable rules in context; the core budget gate assumes that load cost | gate | **Partial/fallback.** Codex loads `AGENTS.md` once per run through hierarchical discovery, not `.claude/rules/learnings/core.md`; no documented include syntax is established. | Under D-7, the Codex adapter injects `core.md` with the SessionStart digest and accounts for both under the host context limit. Claude retains its harness load of `.claude/rules/learnings/`; both hosts use the explicit `learnings-files --for-diff` read for area learnings. Do not import or inline core learnings in `AGENTS.md`. |
| 27 | Area learnings loaded when a file matching `paths:` is read | `lib/learnings_files.py`; `agents/pr-reviewer.md` | `learnings-files --for-diff` mirrors what the harness loaded; Critic cross-check | gate (a host without on-read loading needs an explicit read) | **Partial/fallback.** Codex instruction scope follows directories from project root to cwd, not arbitrary file-read matchers. | Under D-7, use `learnings-files --for-diff` as the explicit area-learnings read on both hosts and require the Critic to read its result. No directory-scoped `AGENTS.md` optimization is proposed; Brooks did not rule on that variant by name. |
| 28 | Learnings gates (unmigrated, over-budget, budget-unreasoned, rule length, rule body) | `hooks/gates.json`; `cmd_stop` | Keep the corpus shaped for harness autoload | gate | **Supported core behavior after explicit loading.** The gate logic is host-neutral; automatic context-cost assumptions are not. | Core evaluates the same corpus. Adapter/doctor exposes loading and truncation only as ephemeral runtime output outside `.prawduct/`; any durable evidence field is a separate Brooks-owned R-5/R-9 format proposal. No persistent state schema is added here. |
| 29 | Governance anchor in `CLAUDE.md` (moving to `AGENTS.md`, see D-3) | `lib/migrate_plugin.py`; `lib/anchor_repair.py`; `lib/init_product.py`; `lib/onboarding_probes.py` | Plugin-absent notice; points the agent at the methodology | fallback | **Documented host primitive; core migration done in #942 (2026-10-14).** Codex documents `AGENTS.md` discovery. All anchor content is in root `AGENTS.md`; a `CLAUDE.md` prawduct creates is exactly `@AGENTS.md`, and in an existing product `CLAUDE.md` the import replaces the shipped anchor while the product's own text stays (owner, 2026-10-14). `prawduct-hook reanchor` moves already-onboarded repos. | All canonical anchor content stays in root `AGENTS.md`, core-owned. The Codex adapter consumes it through host loading. |
| 30 | Judgeability treats root `CLAUDE.md`, `skills/`, `agents/`, `methodology/`, `templates/` as protected and `.claude/settings.json` as metadata | `lib/buildplan_refs.py`; `lib/gitstate.py`; `lib/coverage_algebra.py` | What reopens the Critic gate; the doc-only fast path | gate (`AGENTS.md` would be misclassified today) | **Core change done in #942 (2026-10-14) for `AGENTS.md`.** Root `AGENTS.md` is protected (`agents-md-edited`) exactly as root `CLAUDE.md` is; Codex/plugin metadata paths are not classified yet. | D-6 keeps the protected/judgeability set core-owned. Adapters may propose additive Codex-only paths upstream but never remove a core entry; core retains gate evaluation. |
| 31 | `.claude/settings.json` install reference (`extraKnownMarketplaces`, `enabledPlugins`) | `lib/migrate_plugin.py`; `lib/init_product.py`; install-reference probes | Onboard, migrate, doctor, the drift advisory | fallback | **Partial/fallback.** Codex supports plugin manifests, marketplaces, and `.codex/config.toml`, not `.claude/settings.json`. | Host install-reference provider returns activation/provenance state at runtime from existing host/project configuration; migration and doctor consume it without a new persistent state schema. |
| 32 | Per-repo disable via `.claude/settings.local.json` `enabledPlugins` | `lib/repo_toggle.py`; `skills/repo-disable` | Opt out per repo | UX | **Not verified for pinned `0.156.1`.** Current official packaging docs describe repo `.codex/config.toml` enable/disable, but F1 did not establish the exact stable key/precedence on the pinned runtime. | Design a Codex repo-toggle provider only after static pinned-version confirmation and one authorized reload test; it must edit only the owned key and round-trip other config unchanged. |
| 33 | Reads Claude `installed_plugins.json`, names `known_marketplaces.json`, and scans cached Prawduct versions under each config root | `lib/plugin_activation.py`; install-reference probes; `lib/plugin_caches.py` | `check-plugin-active` during onboarding; doctor cache-hygiene recommendation | fallback (answers `unknown` on doubt) | **Partial/fallback.** Codex exposes plugin marketplace/config state but not Claude's registry files. | Replace file-name probes with a host activation provider that returns active/inactive/unknown plus provenance. |
| 34 | Managed install vs `--plugin-dir` checkout detection | `hooks/banner.py` | Provenance in the banner | UX | **Partial/fallback.** Plugin root and marketplace source can distinguish installed bundles from source checkouts, but no Prawduct live test exists. | Host provenance provider classifies source, installed cache, repo marketplace, and unknown; banner consumes only the normalized value. |
| 35 | Version from `.claude-plugin/plugin.json` vs `.prawduct/.prawduct-version` | `bin/prawduct-hook`; `hooks/banner.py` | Gate attribution; new-gate announcements | fallback | **Supported design primitive from documentation; not observed on pinned `0.156.1`.** Portable `plugin.json` or Codex compatibility manifest carries a version; project state keeps `.prawduct-version`. | Neutral manifest reader accepts the selected adapter manifest; core comparison and new-gate logic remain unchanged. |
| 36 | Plugin `bin/` on the Bash PATH (bare `prawduct-hook`) | every skill, agent and methodology file that runs it | Every skill-driven gate write (critic-begin, consolidate, evidence, PR review) | gate | **Partial/fallback; bare PATH behavior not verified.** Plugin packaging documents no automatic `bin/` PATH contract. | Skills invoke a plugin-root-resolved launcher or a declared plugin command; doctor proves executability before gates are reported active. |
| 37 | Harness worktree naming (`.claude/worktrees/agent-*`, `wf_*`) | `lib/gitstate.py`; `bin/prawduct-hook` | Refuse `.prawduct/` writes that would strand in a disposable worktree | fallback (without it, writes strand silently) | **Partial/fallback.** O5 describes desktop-app managed worktrees, not a stable CLI `$CODEX_HOME/worktrees` path, name, or detached-HEAD contract. | Detect Git worktree identity and ownership structurally (`git rev-parse`/worktree metadata), with optional host hints; never key safety to a directory-name regex alone. |
| 38 | `/prawduct:*` command names in gate and briefing text | `bin/`, `lib/`, `hooks/`, skills | Remedy text in blocking messages | UX | **Partial/fallback; Claude syntax unsupported.** | Render remedies from host command metadata: Codex skill/instruction invocation versus Claude slash command; core uses semantic action IDs. |
| 39 | Session model: `/clear` is a boundary; resume, compact and fork continue; the SAFE TO CLEAR / DO NOT CLEAR block | `methodology/`; `methodology/session-digest.md`; `cmd_clear`; clear-verdict and clear-reason gates | Boundary resets; the clear-verdict and clear-reason gates parse labels and reasons from `last_assistant_message` | gate | **Partial/fallback.** O1 documents `startup`, `resume`, `clear`, and `compact` SessionStart sources and Stop's `last_assistant_message`. The [Codex CLI docs](https://learn.chatgpt.com/docs/developer-commands) describe root-chat fork commands, but O1 names no `fork` SessionStart source. Fork transition classification and clear-verdict/clear-reason parsing remain unverified on pinned `0.156.1`. | Normalize root-session transitions independently of subagent creation. Clear resets; resume and compact continue; root-chat fork requires a proven launcher/host continuity receipt or fails closed because no `fork` SessionStart source is documented. Keep SAFE TO CLEAR and clear-reason parsing in core and enable both only after row 8’s text/size/newline test. |

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

The inventory is merged (PR #944), its evidence is on #928, and it is ruled on (D-5 to D-12).
R-8(a) is satisfied: the refusal receipt was posted on #928 on 2026-10-22
([comment](https://github.com/brookstalley/prawduct/issues/928#issuecomment-6331682061)), which
is the bar the owner set on 2026-10-21. R-8(b), R-8(c) and full R-8 parity stay open.

Next, in order:

1. **The host seam (#1037).** Every host payload read, `CLAUDE_*` root read and structured hook
   response write moves into `plugin/lib/host.py`, chosen by `PRAWDUCT_HOST`, behind a golden
   test of the SessionStart, Stop and SubagentStop output (R-2, R-3). Plain text the hooks print
   in place (the briefing, the Stop's notes ahead of its block) stays where it is for #1038 to
   move.
2. **The Codex Phase 1 spike (#1038).** Built on the seam, in `adapters/codex/`, labelled
   experimental: one skill (`methodology`), the briefing, one Stop gate (`reflection`) and doctor
   detection, with a live probe for each host-behaviour assumption. Target: the 3.8 release.

**What the Codex source says about a deny-everything PreToolUse hook** (read from the source at
tag `rust-v0.156.1`, commit `b412ff32`, on 2026-10-15; none of it was run). It shapes the R-8(a)
probe and does not satisfy it.

- **One hook's allow cannot override another hook's deny.** The outcome blocks if any handler
  blocked ([`pre_tool_use.rs:115`](https://github.com/openai/codex/blob/rust-v0.156.1/codex-rs/hooks/src/events/pre_tool_use.rs#L115)),
  and a block discards every handler's input rewrite (line 129). `permissionDecision: "allow"`
  with no `updatedInput` is reported as unsupported and decides nothing.
- **Only synchronous hooks can block** ([`engine/mod.rs:154`](https://github.com/openai/codex/blob/rust-v0.156.1/codex-rs/hooks/src/engine/mod.rs#L154)).
- **The hook fails open.** A deny hook that errors, exits with a code other than 0 or 2, exits 2
  with empty stderr, or prints invalid JSON is recorded as failed and the tool runs
  ([`pre_tool_use.rs:205-293`](https://github.com/openai/codex/blob/rust-v0.156.1/codex-rs/hooks/src/events/pre_tool_use.rs#L205-L293)).
  The reviewer's hook must catch its own errors and still deny.
- **Not every tool reaches the hook.** Every function tool does by default
  ([`registry.rs:130`](https://github.com/openai/codex/blob/rust-v0.156.1/codex-rs/core/src/tools/registry.rs#L130)),
  and so do `apply_patch` (matched as `Write`/`Edit` too), shell (`exec_command`, named `Bash`)
  and MCP tools. `write_stdin` and the code-mode `wait` skip it on purpose: they continue a call
  that already passed. Hosted web search is a hosted tool spec, switched off only by config
  ([`hosted_spec.rs:19`](https://github.com/openai/codex/blob/rust-v0.156.1/codex-rs/core/src/tools/hosted_spec.rs#L19)).
  No PreToolUse path for it was found. So a reviewer session has to disable it in config. That
  is parity: on Claude, a tool missing from `tools:` is absent too, not refused.
