---
artifact: reference
# scope intentionally empty: this is a point-in-time inventory, not a plan;
# no derived-view scope ownership.
scope:
status: reference — snapshot of the v2.3.3 governance kernel
created: 2026-07-12
depends_on: []
---

# Governance Kernel Inventory — v2.3.3 (2026-07-12)

Requirements-preservation snapshot for the kernel redesign
(`kernel-redesign-discovery.md`). Every gate, state file, and invariant the
redesign must consciously keep, change, or delete — so nothing is dropped
silently (Principle 2). Compiled by a read-only inventory agent over
`bin/prawduct-hook` (3,089 lines, flat `if/elif` dispatch), `lib/` (12,451
lines), `hooks/`, `skills/`; spot-checked by the main session.

## 1. Hook subcommands (34) — what each protects

Classes: **HARD** = can block (exit ≠ 0 stops a flow), **ADV** = advisory
(informational, fail-open), **BOOK** = bookkeeping/state-writer.

| Subcommand | Protects (the WHY) | Caller | Class |
|---|---|---|---|
| `clear --session-start` | Sessions start from clean, correctly-scoped state; refuses to run while `.critic-active` present (a reviewer must never mutate the session it reviews) | SessionStart hook | HARD (the critic guard) + BOOK |
| `critic-begin` / `critic-end` | Review-in-progress marker lifecycle; wipes stale partials at begin | `/prawduct:critic` | BOOK |
| `critic-consolidate` | Deterministic merge of reviewer partials → findings + ledger anchor; no model in the write path | SubagentStop, Stop backstop, manual | BOOK (fail-closed) |
| `subagent-stop` | Event-driven consolidate as each reviewer finishes | SubagentStop hook (matcher `critic-reviewer`) | ADV (never blocks the agent) |
| `build-index` | Warm work-model index for the undocumented-requirement tripwire | SessionStart | BOOK |
| `user-prompt-submit` | Tripwire #1: a new requirement entering undocumented | UserPromptSubmit hook | ADV |
| `stop` | The session-end gate battery (see §4) | Stop hook | HARD |
| `test-status` / `validate-evidence` | Evidence freshness vs. schema validity (deliberately split) | critic/pr skills | ADV |
| `test-evidence record` | The evidence writer — gates judge output the plugin produced (TST-6V2N) | build cycle | BOOK |
| `check-cumulative-critic` | A fresh review vouches for the exact code the PR ships at HEAD | `/prawduct:pr create` | HARD |
| `verify-chunk-refs` | Plan references resolve on disk (Critic Goal 2) | critic | HARD |
| `verify-coverage` | Changed files were actually exercised, when `coverage_required` | critic | HARD (opt-in) |
| `ledger-append` | Agents never hand-author the ledger | critic/pr skills | BOOK (append-only) |
| `review-stats` | Visible Costs — review overhead observable | manual/janitor | ADV |
| `classify-diff-risk` | Review rigor matches blast radius | critic/pr | ADV (fail-open → standard) |
| `check-operator-verification` / `accept-…` / `verify-…` | Human-verification obligations can't ship silently; overrides capture rationale | `/prawduct:pr` | HARD (opt-in) + BOOK |
| `check-pr-doc-only` | Doc-only PR carveout signal | pr | ADV |
| `check-change-log-entry` | Shipped change is recorded (REL-6C3W) | pr | HARD |
| `regen-views [--check]` | Derived views never silently partial-flip (VWS-6R4T) | manual / release pre-flight | HARD on `--check` |
| `stamp-merged` | **DEPRECATED** — announces its own deprecation | none | vestigial |
| `infer-critic-mode` | Skill picks mode without arbitrary-code Bash | critic | ADV |
| `compute-verify-resolutions-scope` | Critic verify scope == the scope the stop gate enforces (no drift) | critic | ADV (feeds a gate) |
| `resolve-base` | One source of truth for the gitflow diff base | critic/pr | BOOK (fail-closed → full review) |
| `advisory <subcmd>` | Advisory lifecycle without arbitrary code | `/prawduct:advisory` | ADV |
| `migrate-plugin` / `init-product` / `update-gitignore` | Onboarding/migration mutate repos reviewably | onboard/migrate/doctor | BOOK |
| `audit-learnings` | Learnings lifecycle hygiene | doctor | BOOK |
| `repo-disable` | Per-repo off-switch | repo-disable skill | BOOK |
| `bug-inbox` | Upstream bug channel resolution (exit 1 = unreachable → local fallback) | report-bug | ADV |

Thin-wrapper note: the gate bodies live in `lib/gates.py` / `lib/coverage.py`
(STH-9V4K ch.6); `bin/prawduct-hook` top level stays lib-free and lazy-imports.

## 2. State files — writer/reader/keying

Gitignore contract: `lib/core.py:75-95`, mirrored at `bin/prawduct-hook:353-375`
(pinned by `TestSessionGitignoreMirror`); `_untrack_session_files` defensively
untracks at every SessionStart.

**Session-scoped, gitignored, single-slot** (reset by `clear`): `.session-start`
(freshness epoch for every gate), `.session-reflected` (reflection gate input;
archived → `reflections.md`), `.session-git-baseline`, `.session-handoff.md`,
`.subagent-briefing.md` (written by code, read only by agents), `.gates-waived`
(agent-written waivers, auto-cleared).

**Critic state, gitignored**: `.critic-active` (marker, 30-min TTL),
`.critic-findings.json` (**single-slot**, keyed by reviewed commit, freshness =
mtime vs `.session-start`), `.critic-partials/` (per-role partials + the
**model-written** `manifest.json` — the roster-defect site),
`.governance-ledger.jsonl` (**append-only**; PR-gate fallback + telemetry),
`.pr-reviews/<branch>.json` (one slot per branch).

**Other per-clone, gitignored**: `.test-evidence.json` (timestamp-keyed only —
`git_sha` deliberately removed, TST-4K2P), `.work-model-index.json`,
`.advisories.json`, `.prawduct-version`, `.bug-inbox`, `reflections.md`
(append-only, per-clone).

**Committed, product-owned**: `project-state.yaml` (config knobs: `base_branch`,
`coverage_required`, `views_enabled`, `operator_verification_required`,
`test_command`, `tests_dirs`, `active_build_plan`), `backlog.md`,
`learnings.md` + `learnings-detail.md`, `change-log.md` (canonical store for
derived views), `artifacts/*.md` (build plans deliberately tracked),
`operator-verification.md`, `release-notes.md`.

**Vestigial**: `.sync-pending` (no reader or writer anywhere — file-sync era),
`.critic-test-findings.json` (gitignore entry only), `stamp-merged`.

## 3. Gate semantics — the question each answers

- `tests_are_current` — can I trust the saved test result without re-running?
  (this-session + zero failures; content hashing removed pre-v1.4 — do not
  reintroduce)
- `background_tasks_in_flight` — is the diff still being produced? DEFER, don't
  block (STH-3W7F)
- `critic_findings_satisfy_session_gate` — does the findings file vouch for
  *this session's* changes? (single source shared with the briefing — STH-4F7C
  ended a drift bug)
- `_is_trivial_fileset_eligible` — does a `Type: trivial` declaration stay
  inside catastrophic-blast-radius bounds? (size explicitly NOT a bound)
- `check_cumulative_critic` — does a fresh review vouch for the exact code this
  PR ships at HEAD? (cumulative OR chain OR this-session ledger fallback)
- `verify_coverage` — was every changed file the evidence *can judge*
  exercised? (only blocks on judgeable files)
- `_record_covers_head` — does the reviewed commit still cover HEAD, or only
  docs changed since? (CRT-7M2D)

**Known duplicate/divergent sites** (redesign targets): the doc-only question
answered three ways (`cmd_stop`, `coverage._pr_diff_is_doc_only`,
`_record_covers_head`); metadata-exemption boundary drawn differently by
`_record_covers_head` vs `_compute_verify_resolutions_scope` (CRT-5D8Q
deadlock); freshness tie-rules deliberately divergent (`>` vs `>=`).

## 4. Hook wiring

- **SessionStart** (`startup|resume|clear|compact`): banner → digest →
  `clear --session-start` (not on compact) → `build-index`.
- **UserPromptSubmit**: tripwire nudge.
- **Stop**: gate battery, in order — background-work deferral → compliance
  canary → Gate 1 reflection (blocking only with active plan) → Gate 2 Critic
  (+ trivial enforcement, abandoned-Critic self-heal-or-block, verify-scope
  staleness) → Gate 2.5 advisory synthesis → Gate 3 PR-review evidence.
  Waivers: `reflection`/`critic`/`pr`.
- **SubagentStop** (`critic-reviewer`): consolidate.
- `hooks/gates.json` is gate *attribution* (banner announcements + blocker
  prefixes), not wiring.

## 5. Skills (14) and the no-arbitrary-code pattern

fork + restricted: `advisory`, `backlog`, `critic` (git read-only +
enumerated hook subcommands; pytest denied), `learnings`. Non-fork:
`doctor`, `janitor`, `methodology`, `migrate`, `onboard`, `ping`, `pr`,
`repo-disable`, `report-bug`. Plus `agents/critic-reviewer.md` (restricted
reviewer agent type; SubagentStop matcher target).

**Load-bearing pattern**: skills call `prawduct-hook <subcmd>` precisely so
`allowed-tools` can scope to `Bash(prawduct-hook <subcmd>*)` instead of
`Bash(python3 -c *)` — arbitrary-code-free skills are structurally
enforceable. Any redesign of the CLI must preserve a stable, allowlistable
command surface.

## 6. Deliberate decisions — do not casually reverse

- All mutable state under the **session worktree's** `.prawduct/`; no state
  shared between unrelated repos (same-repo guard in
  `gitstate.resolve_project_dir`). ← the redesign changes the *keying*, not
  the isolation-between-products invariant.
- Fail-open vs fail-closed is per-command and deliberate: session-start/prompt
  paths never block; gates fail closed; state mutators exit 1 on broken lib.
- Removed, do-not-reintroduce: content/tree-hash test freshness (chronic false
  positives), `git_sha` evidence pinning (TST-4K2P), `_pr_diff_is_trivial`
  fast-path, `stamp-merged` flow, file-sync distribution.
