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
  becomes an `@AGENTS.md` import plus Claude-only lines. Claude Code reads `AGENTS.md` natively
  only as a fallback when no `CLAUDE.md` exists, so the import is what makes it load in every
  Claude session. That change is its own backlog item and ships independently of the adapter.
- **D-4 "Officially supported" means R-1 to R-13 met on a pinned host version range, with R-8
  shown live.** Anything short of that is labelled *experimental*. The adapter has one named
  maintainer, and it is demoted to experimental when it falls a set number of host releases
  behind without an update (the number is set at design).

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
| 1 | SessionStart banner + digest (matcher `startup\|resume\|clear\|compact\|fork`) | `hooks/hooks.json`, `hooks/banner.py`, `hooks/digest.py` | Version banner; governance digest injected as context | fallback (`/prawduct:methodology`) | **Supported primitive from documentation; not observed on pinned `0.156.1`.** `SessionStart` supports `startup`, `resume`, `clear`, and `compact`, and plain text or JSON additional context reaches the model. The absent `fork` source is dispositioned in rows 2 and 39. | Host adapter maps the four native sources and treats reviewer/subagent creation separately; retain `/prawduct:methodology` equivalent as a doctor-visible fallback. |
| 2 | SessionStart split: `startup\|clear` runs `clear --session-start`; `resume\|compact\|fork` runs `--brief-only` | `hooks/hooks.json`; `cmd_clear` in `bin/prawduct-hook` | Session boundary vs continuation: resets markers, `.session-base-tree`, waivers, regenerates the handoff | gate | **Partial/fallback.** Native source values distinguish new/clear from resume/compact; subagent fork is not a SessionStart source. | After core's host-neutral tolerant JSON parse, the adapter reads the host `source` key and normalizes a `session_boundary` enum; core invokes `clear --session-start` or `--brief-only`. An unsupported source fails closed rather than guessing. |
| 3 | Session source comes from the matcher; the `source` payload field is never read | `hooks/hooks.json` | Boundary classification is done by registration | gate (adapter must map the host's source to the flag) | **Partial/fallback.** Codex supplies `source` and applies the matcher to it, but documents no `fork` source. | After host-neutral parsing, the adapter alone reads host payload keys and emits a normalized event; core consumes that event. Unknown/missing gate-relevant sources fail closed. |
| 4 | Stop hook, every turn | `hooks/hooks.json`; `cmd_stop`; `hooks/gates.json` | All session-end gates (reflection, Critic, PR, trivial, learnings, clear-verdict) | gate | **Supported primitive.** Codex exposes synchronous `Stop`; F1 observed a bounded repeated sequence. | Register one host Stop entry that calls the host-neutral stop evaluator through the adapter. |
| 5 | Stop blocks by exit 2 with the reason on stderr, which the host feeds back to the model | `cmd_stop` | The blocking channel for every gate | gate | **Supported with evidence limit.** Official contract supports it; F1 directly observed continuations and captured hook intent/host streams, but inner exit/stderr attribution is derived. | Adapter owns Codex output/exit translation while core returns a host-neutral block decision and reason. |
| 6 | No `stop_hook_active` re-entry guard; blocking again on every Stop relies on Claude's exit-2 re-prompt loop | `cmd_stop` | Gate persistence across retries | gate (depends on the host's re-fire semantics) | **Supported for the bounded matrix.** Three unchanged-gate continuations, independent gate opening, and fourth completion were observed. Codex also supplies `stop_hook_active`. | Core stays stateless; adapter forwards every Stop to core and does not suppress retries merely because `stop_hook_active` is true. |
| 7 | Stop advisories at exit 0 as stdout JSON `{systemMessage, additionalContext}` | `bin/prawduct-hook` (advisory emit) | Deferral notes, non-blocking advisories | fallback | **Partial/fallback.** `systemMessage` is supported, but the Codex Stop contract does not establish Claude's exact top-level `additionalContext` advisory shape. | Core emits `Advisory{text, audience}`; Codex initially renders it as `systemMessage`, and any model-steering context requires an explicitly documented Codex shape. |
| 8 | Stop payload `last_assistant_message` | `lib/gates.py` | The clear-verdict gate; the RUNNING + DO NOT CLEAR deferral | gate (clear-verdict); deferral degrades to block | **Not verified for the gate.** The field is documented as string or null, but F1 did not exercise clear-verdict parsing or preserve its text. | Normalize null/absent distinctly and keep the existing block path until a contract fixture plus authorized live test proves text/size/newline behavior. |
| 9 | Stop payload `background_tasks[]` | `lib/gates.py` | Defers blockers while a background task is in flight | fallback (absent means block as normal) | **Partial/fallback.** The field is absent from the documented Codex Stop payload, but upstream already defines absence as “block as normal.” | Optional host capability; absence follows the existing named backstop and blocks normally rather than deferring. |
| 10 | Stdin payload parsing tolerates empty or garbage input as `{}` | `bin/prawduct-hook` payload reader | Stop and SubagentStop input | gate (fails closed) | **Supported existing core behavior.** Upstream locates the tolerance in `bin/prawduct-hook`'s payload reader; Codex supplies JSON in the normal path, but no host primitive is needed for the fallback. | Core keeps the host-neutral tolerant byte-to-JSON parse and maps empty/garbage input to `{}`; the adapter then reads only host-specific keys and normalizes them; core gates consume the normalized event and fail closed. |
| 11 | SubagentStop, matcher `(^\|:)critic-reviewer$`; payload `agent_type`, `cwd` | `hooks/hooks.json`; `cmd_subagent_stop` | Consolidates each Critic partial as its reviewer finishes | fallback (Stop consolidates idempotently) | **Partial/fallback.** Codex exposes `SubagentStop` and matcher by `agent_type`, but F1 did not exercise the rendezvous; the current event-table reading does not independently settle `cwd`, while a summarised O1 fetch reported it. Stop consolidation remains the idempotent backstop. | After core's tolerant parse, the adapter reads confirmed host keys and normalizes subagent identity; core consumes the event and retains its Stop consolidation path. Doctor reports unavailable or untrusted hooks. |
| 12 | SessionStart plain stdout goes into model context | `cmd_clear`; `hooks/banner.py` | Briefing, handoff, advisories, the new-gate relay | fallback | **Supported from documentation; not observed on pinned `0.156.1`.** Plain stdout becomes extra developer context. | Host renderer may use plain text for the brief; canonical content remains generated from shared core state. |
| 13 | SessionStart JSON `hookSpecificOutput{additionalContext, reloadSkills}` and its size limit | `hooks/digest.py` | Governance digest; skill-cache refresh in the framework repo | fallback | **Partial/fallback.** O1 documents `hookSpecificOutput.additionalContext` and the handler's `additionalContextLimit`; neither O1 nor E5 documents a Codex `reloadSkills` output. | Normalize `additional_context`; bound injected context by the documented handler limit. Treat skill refresh as a separate Codex capability checked by doctor and never silently claim it. |
| 14 | `statusMessage` on each hook | `hooks/hooks.json` | Spinner text | UX | **Supported UX from documentation; not observed on pinned `0.156.1`.** | Keep status text in host registration metadata, outside core gate decisions. |
| 15 | Retired hook subcommands kept inert because the host pins hooks.json lazily | `bin/prawduct-hook` | Old registrations must exit 0 silently | UX (compat) | **Supported existing core compatibility behavior.** Keeping inert commands needs no Codex primitive; whether Codex has Claude's lazy-pinned-registration hazard is not established. | Preserve core no-op compatibility commands while any shipped registration can still reference them; adapter registers only current events and makes no cross-host lazy-pinning claim. |
| 16 | `${CLAUDE_PLUGIN_ROOT}` in hook commands and code | `hooks/hooks.json`; `bin/prawduct-hook`; `hooks/*.py` | Finds `lib/`, the manifest version, the gate registry | gate (code falls back to its own path) | **Supported from documentation; not observed on pinned `0.156.1`.** Plugin hooks receive `PLUGIN_ROOT`; compatibility variables `CLAUDE_PLUGIN_ROOT` and `CLAUDE_PLUGIN_DATA` are also set. | Canonical host contract uses a neutral plugin-root input; Codex adapter prefers `PLUGIN_ROOT`, Claude adapter supplies its native root. |
| 17 | `CLAUDE_PROJECT_DIR` | `bin/prawduct-hook`; `hooks/*.py`; `lib/gitstate.py` | Project root; worktree redirect in the Stop path | gate (falls back to cwd or worktree toplevel) | **Partial/fallback.** Hook payload supplies `cwd`; Git can resolve the toplevel. No Codex analogue to `CLAUDE_PROJECT_DIR` is established, and O5's managed-worktree details are desktop-app documentation rather than a stable CLI contract. | Central `resolve_project_root(host,cwd,git)` returns root plus structural Git worktree identity; if either is unproven, the dependent gate refuses rather than trusting a host path convention. |
| 18 | `CLAUDE_CONFIG_DIR` and `~/.claude*` roots | `hooks/banner.py`; `lib/plugin_activation.py`; `lib/stranded_work.py` | Install detection; transcript roots for liveness | UX / fallback | **Partial/fallback.** Codex uses `~/.codex`; hooks provide `transcript_path`, whose format is explicitly unstable. Plugin activation is configured through Codex plugin/config surfaces. | Host capability object supplies config root, plugin activation, and optional transcript liveness path; never parse transcript contents. |
| 19 | `${CLAUDE_SKILL_DIR}` in skill prose | critic, pr, methodology, janitor, runbook, report-bug skills; `lib/buildplan_refs.py` | Loading the Critic and PR protocols and the methodology guides next to their skill | gate in effect | **Partial/fallback; Claude form unsupported.** No equivalent variable is established, but Codex skills package colocated references and scripts. | Propose portable relative resource references or a generated host launcher that resolves the active skill directory. Until packaging proof exists, affected gates remain unavailable/fail closed. Any edit to canonical Claude-facing skill prose must preserve R-3 and R-4 and requires upstream review. |
| 20 | Transcript directory mtimes (content never read) | `lib/stranded_work.py` | Worktree liveness in the briefing and `worktrees` | fallback (reflog, session markers, file mtimes) | **Partial/fallback.** A transcript path may exist, but its format and availability are not stable contracts. | Treat transcript mtime as an optional host signal behind the existing reflog/session-marker/file-mtime backstops. |
| 21 | Reviewer agents' `tools:` allowlists (`Bash(pattern)`, `Write`) | `agents/critic-reviewer.md`, `agents/pr-reviewer.md` | Reviewer isolation. On Claude the tool *set* is enforced; `Bash` patterns and `Write` paths are a contract the reviewer keeps, backed by consolidation validating each partial | gate (R-8) | **Not verified for R-8; direct Claude `tools:` form unsupported.** O4 documents no per-agent exact tool allowlist and says subagents inherit the parent sandbox. F1's attempted constrained subject exposed forbidden surfaces and omitted all five approved tools, so no tested topology reached the refusal test. | A separately launched, manifest-checked constrained session and an exact advertised-tool/denial bar are proposals, not requirements. Neither in-session nor separate-session topology is proven necessary or sufficient. Brooks must rule on the R-8 bar and topology; until a live pass, the Critic gate fails closed and support is not claimed. |
| 22 | `model: inherit`; `omitClaudeMd: true` on the PR reviewer | `agents/*.md` | Same-model review; PR reviewer isolated from instructions and memory | fallback (isolation weakens) | **Partial/fallback.** Custom agents can select a model/sandbox/MCP/skills and otherwise inherit settings; no exact `omitClaudeMd` equivalent is established. | Define explicit reviewer profile inputs: model policy, context seed, instruction sources, sandbox, and tool manifest. Refuse unsupported omission/isolation claims. |
| 23 | Subagent dispatch through the Agent tool, three reviewers concurrently | `skills/critic/coordinator.md`; `skills/pr/SKILL.md` | Independent multi-role Critic; the PR reviewer | gate (single-pass roster is the fallback) | **Partial/fallback.** Codex supports concurrent subagents, but F1 did not prove the constrained Critic tool surface. | Host dispatcher may run the roster concurrently only after an ephemeral/runtime capability check kept outside `.prawduct/` state/evidence files. The upstream-named single-pass roster is the backstop; an external-session route is a separate proposal for Brooks. Any durable `.prawduct/` field would be a Brooks-owned R-5/R-9 format proposal. |
| 24 | Skill frontmatter `context: fork` | critic, backlog, advisory skills | Critic runs outside the builder's context; backlog out of main context | gate (critic), UX (others) | **Partial/fallback; Claude form unsupported.** Codex has subagents but no established automatic mapping from this field. | Propose a small skill-manifest translator: Critic becomes explicit fresh-context dispatch; UX-only forks may run inline when declared safe. Upstream names no fallback for this row, so isolation-sensitive dispatch blocks until the translation is proven. |
| 25 | Skill frontmatter `allowed-tools` with `Bash(...)` grants and deny patterns; `$ARGUMENTS`; `argument-hint`; `disable-model-invocation` | `skills/*/SKILL.md` | What each skill may run; argument passing | fallback / UX | **Partial/fallback; direct format unsupported.** Codex skills use `SKILL.md`; tool policy belongs in agent/config/MCP policy, not presumed Claude frontmatter. | Separate portable skill instructions from host dispatch/policy metadata; translate arguments explicitly and fail closed on an unrepresentable safety restriction. |
| 26 | `.claude/rules/learnings/core.md` loaded every session by the harness | `lib/learnings_files.py`; `lib/init_product.py` | Durable rules in context; the core budget gate assumes that load cost | gate | **Partial/fallback.** Codex loads `AGENTS.md` once per run through hierarchical discovery, not `.claude/rules/learnings/core.md`; no documented include syntax is established. | Loading bounded core learnings inline from `AGENTS.md` is a new proposal, not part of D-3. Brooks must rule on its R-3 effect, duplicate-load risk for Claude, and interaction with the core budget gate. Until inclusion and budget behavior are proven, Codex does not claim autoload and the dependent gate fails closed. |
| 27 | Area learnings loaded when a file matching `paths:` is read | `lib/learnings_files.py`; `agents/pr-reviewer.md` | `learnings-files --for-diff` mirrors what the harness loaded; Critic cross-check | gate (a host without on-read loading needs an explicit read) | **Partial/fallback.** Codex instruction scope follows directories from project root to cwd, not arbitrary file-read matchers. | Keep `learnings-files --for-diff` as the explicit portable loader and require the Critic to read its result; optional directory-scoped AGENTS files are optimization, not the gate. |
| 28 | Learnings gates (unmigrated, over-budget, budget-unreasoned, rule length) | `hooks/gates.json`; `cmd_stop` | Keep the corpus shaped for harness autoload | gate | **Supported core behavior after explicit loading.** The gate logic is host-neutral; automatic context-cost assumptions are not. | Core evaluates the same corpus. Adapter/doctor exposes loading and truncation only as ephemeral runtime output outside `.prawduct/`; any durable evidence field is a separate Brooks-owned R-5/R-9 format proposal. No persistent state schema is added here. |
| 29 | Governance anchor in `CLAUDE.md` (moving to `AGENTS.md`, see D-3) | `lib/migrate_plugin.py`; `lib/anchor_repair.py`; `lib/init_product.py`; `lib/onboarding_probes.py` | Plugin-absent notice; points the agent at the methodology | fallback | **Supported and already decided.** Codex natively reads `AGENTS.md`. | Canonical anchor moves to `AGENTS.md`; `CLAUDE.md` imports it and retains Claude-only lines as Brooks ruled. The anchor move is its own upstream backlog item and ships independently of the adapter. |
| 30 | Judgeability treats root `CLAUDE.md`, `skills/`, `agents/`, `methodology/`, `templates/` as protected and `.claude/settings.json` as metadata | `lib/buildplan_refs.py`; `lib/gitstate.py`; `lib/coverage_algebra.py` | What reopens the Critic gate; the doc-only fast path | gate (`AGENTS.md` would be misclassified today) | **Unsupported without core change.** Current classification omits `AGENTS.md` and Codex/plugin metadata. | The protected/judgeability set remains core-owned contract data. Brooks must decide whether D-3's independent `AGENTS.md` anchor move also owns its protected-path entry. Adapters may separately propose additive Codex-only entries (`.codex/`, portable plugin manifests, generated assets) through upstream-reviewed rules and may never remove a core entry. Gate evaluation remains in core. |
| 31 | `.claude/settings.json` install reference (`extraKnownMarketplaces`, `enabledPlugins`) | `lib/migrate_plugin.py`; `lib/init_product.py`; install-reference probes | Onboard, migrate, doctor, the drift advisory | fallback | **Partial/fallback.** Codex supports plugin manifests, marketplaces, and `.codex/config.toml`, not `.claude/settings.json`. | Host install-reference provider returns activation/provenance state at runtime from existing host/project configuration; migration and doctor consume it without a new persistent state schema. |
| 32 | Per-repo disable via `.claude/settings.local.json` `enabledPlugins` | `lib/repo_toggle.py`; `skills/repo-disable` | Opt out per repo | UX | **Not verified for pinned `0.156.1`.** Current official packaging docs describe repo `.codex/config.toml` enable/disable, but F1 did not establish the exact stable key/precedence on the pinned runtime. | Design a Codex repo-toggle provider only after static pinned-version confirmation and one authorized reload test; it must edit only the owned key and round-trip other config unchanged. |
| 33 | Reads `~/.claude/plugins/installed_plugins.json` and names `known_marketplaces.json` | `lib/plugin_activation.py`; install-reference probes | `check-plugin-active` during onboarding | fallback (answers `unknown` on doubt) | **Partial/fallback.** Codex exposes plugin marketplace/config state but not Claude's registry files. | Replace file-name probes with a host activation provider that returns active/inactive/unknown plus provenance. |
| 34 | Managed install vs `--plugin-dir` checkout detection | `hooks/banner.py` | Provenance in the banner | UX | **Partial/fallback.** Plugin root and marketplace source can distinguish installed bundles from source checkouts, but no Prawduct live test exists. | Host provenance provider classifies source, installed cache, repo marketplace, and unknown; banner consumes only the normalized value. |
| 35 | Version from `.claude-plugin/plugin.json` vs `.prawduct/.prawduct-version` | `bin/prawduct-hook`; `hooks/banner.py` | Gate attribution; new-gate announcements | fallback | **Supported design primitive from documentation; not observed on pinned `0.156.1`.** Portable `plugin.json` or Codex compatibility manifest carries a version; project state keeps `.prawduct-version`. | Neutral manifest reader accepts the selected adapter manifest; core comparison and new-gate logic remain unchanged. |
| 36 | Plugin `bin/` on the Bash PATH (bare `prawduct-hook`) | every skill, agent and methodology file that runs it | Every skill-driven gate write (critic-begin, consolidate, evidence, PR review) | gate | **Partial/fallback; bare PATH behavior not verified.** Plugin packaging documents no automatic `bin/` PATH contract. | Skills invoke a plugin-root-resolved launcher or a declared plugin command; doctor proves executability before gates are reported active. |
| 37 | Harness worktree naming (`.claude/worktrees/agent-*`, `wf_*`) | `lib/gitstate.py`; `bin/prawduct-hook` | Refuse `.prawduct/` writes that would strand in a disposable worktree | fallback (without it, writes strand silently) | **Partial/fallback.** O5 describes desktop-app managed worktrees, not a stable CLI `$CODEX_HOME/worktrees` path, name, or detached-HEAD contract. | Detect Git worktree identity and ownership structurally (`git rev-parse`/worktree metadata), with optional host hints; never key safety to a directory-name regex alone. |
| 38 | `/prawduct:*` command names in gate and briefing text | `bin/`, `lib/`, `hooks/`, skills | Remedy text in blocking messages | UX | **Partial/fallback; Claude syntax unsupported.** | Render remedies from host command metadata: Codex skill/instruction invocation versus Claude slash command; core uses semantic action IDs. |
| 39 | Session model: `/clear` is a boundary; resume, compact and fork continue; the SAFE TO CLEAR / DO NOT CLEAR block | `methodology/`; `hooks/session-digest.md`; `cmd_clear`; clear-verdict gate | Boundary resets; the clear-verdict gate parses those labels from `last_assistant_message` | gate | **Partial/fallback.** Codex exposes startup/resume/clear/compact SessionStart sources and Stop's last assistant message; fork is a subagent lifecycle, not a documented root SessionStart source. | Normalize root-session transitions separately from reviewer/subagent creation; keep SAFE TO CLEAR parsing host-neutral and fail closed on unknown transitions. |

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

The adapter author fills the Codex and Proposed seam columns above, starting with the **gate**
rows, and posts the feasibility evidence on #928. R-8 comes first: whether a reviewer-specific
policy can take shell access away from the Critic on Codex, or whether the Critic has to run as a
separate constrained session. Then design: the concrete seam, and the Codex feasibility spike
(the issue's Phase 1) scoped to one skill, the session briefing and one Stop gate, with a live
probe for each host-behaviour assumption.
