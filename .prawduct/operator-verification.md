# Operator Verification Queue

<!-- Append-only queue of human-verification items for visual / live-integration
     changes automated tests can't fully cover. Each entry is a level-2 heading:
     `## VRF-<id> — <Chunk N> — <title>`; first body line is
     `**Status:** pending | verified | accepted`. When
     `operator_verification_required: true`, `/pr create` BLOCKS on any pending
     entry (currently false here, so this is a tracked reminder, not a gate).
     Append-only history — don't delete drained entries. -->

## VRF-001 — Chunk 01 — Worktree resolution against the live harness

**Status:** verified
**Added:** 2026-06-20 (worktree-compat Chunk 01, STH-4K7N)
**Verified:** 2026-07-18 — by accumulated dogfood, not a single scripted run. This session
runs in a **linked worktree** (`git rev-parse --show-toplevel` = `…/prawduct-wt-backlog-prd`,
common-dir = the primary's `…/prawduct/.git`, shared). `prawduct-hook evidence status`
resolves the shared store to `<common-dir>/prawduct/evidence.jsonl` (102 resolution +
104 review facts) — worktree-aware resolution live in the running harness. The live-harness
assumption (a hook *process* runs with the worktree as its cwd, so gate state resolves to the
worktree with no false block) is confirmed by prior in-place governed close-outs from this
worktree: STH-3R8K's session ran `/prawduct:critic final` (clean) and closed its Stop gates
here, committing 1637c4a in place; and the worktree-compat plan (STH-4K7N) itself ran
`/prawduct:critic cumulative` over `merge-base…HEAD` and `/prawduct:pr create` from a worktree.
Closes the HIGH open assumption in `artifacts/build-plan-worktree-compat.md` and the reconciled
CRT-6W2N (shipped 2026-07-18).
**Where to verify:** A real Claude Code session in a prawduct-governed repo — enter
a git worktree on a feature branch (`EnterWorktree`, or `git worktree add … <branch>`
+ a Bash `cd`), do a small code change, then run the governed close-out.

**Why a human check:** unit tests confirm `resolve_project_dir` follows a worktree
*given* a worktree cwd, but they cannot reach the live harness assumption that a
Stop/SessionStart hook *process* actually runs with the worktree as its cwd (docs
say yes; corroborated by the existing briefing worktree warning). This is the HIGH
open assumption in `artifacts/build-plan-worktree-compat.md`.

**Verify (from inside the worktree):**
- `prawduct-hook` resolves `.prawduct/` to the worktree: `.critic-findings.json`,
  `.session-reflected`, and `.test-evidence.json` written here are the ones the
  Stop gate and `check-cumulative-critic` read (no false block).
- `/prawduct:critic` runs and records findings in the worktree's `.prawduct/`.
- `/prawduct:pr create` finds the cumulative record and proceeds — no
  review-in-primary / raw-`gh` workaround needed.
- A normal (non-worktree) session is unchanged.

## VRF-002 — Chunk 04 — SubagentStop fires critic-consolidate for a dispatched critic-reviewer

**Status:** pending — narrowed 2026-07-27; fact 2 is CLOSED and was a real defect

> === 2026-07-27 — FACT 2 RESOLVED BY STATIC ANALYSIS, AND IT WAS BROKEN (CRT-2J8N) ===
>
> This entry's own last line said to "investigate the matcher string
> (`prawduct:critic-reviewer` vs `critic-reviewer`)". That investigation finally ran, and
> the matcher was wrong from birth: **for `SubagentStop`**, Claude Code evaluates a matcher
> of only letters, digits, `_`, `-`, spaces, `,` and `|` as a **literal** — a single exact
> string, or a `|`/`,`-separated **list** of exact strings — and the runtime `agent_type` of a
> plugin subagent is the **plugin-scoped** `prawduct:critic-reviewer`. The bare
> `critic-reviewer` matcher could never match, so this hook never fired — in any repo, on any
> v3.1.1 install. Fixed to `(^|:)critic-reviewer$`.
>
> **Scoped to `SubagentStop`, deliberately:** which literal class an event uses is **not
> uniform across hook events**, so this is not a global rule — the
> `startup|resume|clear|compact|fork` `SessionStart` matchers in the same `hooks.json` are
> lists of exact strings and were always correct. Source:
> https://code.claude.com/docs/en/hooks (verified 2026-07-27), corroborated during review
> against the installed Claude Code 2.1.220 matcher implementation.
>
> **The reasoning error worth keeping:** fact 2 above waves this off with "the command
> defends with an `agent_type` endswith-check and is no-op-safe regardless." That defense
> lives *downstream of the matcher* — if the matcher never fires, the defense never runs.
> A guard behind a gate that never opens is not a guard.
>
> **And it was not un-testable.** "Matcher-anchoring semantics vary by Claude Code
> version" justified deferring the whole of fact 2 to a live check. But whether a matcher
> *can* match a given `agent_type` is a pure static question, and it is now pinned by
> `tests/test_critic_reviewer_agent.py::TestSubagentStopMatcherMatchesRuntimeAgentType`,
> which encodes the documented two-path matcher rule. Only *delivery* — does the harness
> actually emit the event — still needs the live check below.
>
> **Still pending, and now higher value:** run the verification steps below against the
> fixed matcher. They are correct as far as they go, but they need TWO additions or they
> can return a false verdict in either direction:
>
> 1. **Isolate the harness.** The *installed* plugin's hooks fire in every repo you open,
>    including a scratch repo built to test a hook change, so a stale copy can fire
>    alongside the fixed one. Run with `CLAUDE_CONFIG_DIR=<empty dir>` (learnings.md — the
>    rule earned when exactly this contaminated a hook e2e run and nearly got working code
>    "debugged").
> 2. **Attribute the consolidation, do not just observe it.** Three things can consolidate:
>    this hook, the skill's own explicit `critic-consolidate`, and the session-end backstop.
>    Nothing currently RECORDS which one fired — so "findings appeared" is consistent with
>    the hook still being dead. That ambiguity is precisely why this went unnoticed for 17
>    days, and it bit again during the 2026-07-27 review, where the reviewing agent reported
>    the trigger "did consolidate without an explicit call" and had no way to know that.
>    Until a trigger is recorded on the `review.critic` event, this step must be run with the
>    skill's explicit consolidate call suppressed, or the verdict means nothing.

**Added:** 2026-07-10 (critic-persistence-redesign Chunk 04)
**Where to verify:** A real Claude Code session in this repo AFTER the plugin is
updated to a version carrying `agents/critic-reviewer.md` + the `SubagentStop` hook
(this session runs the plugin from `~/.claude/plugins/cache/.../2.3.0`, so the new
agent type and hook are NOT yet live — they can't be exercised pre-release).

**Why a human/live check:** three integration facts are unverifiable by code analysis
(the Chunk 03 Critic note) —
1. the plugin's `critic-reviewer` agent type resolves when dispatched via the Agent
   tool (`subagent_type: critic-reviewer` / plugin-scoped `prawduct:critic-reviewer`);
2. the `SubagentStop` hook matcher `critic-reviewer` actually fires for that agent's
   completion (matcher-anchoring semantics vary by Claude Code version — the command
   defends with an `agent_type` endswith-check and is no-op-safe regardless);
3. the fired hook runs `prawduct-hook subagent-stop` → `critic-consolidate` with a
   `cwd` that resolves `.prawduct/`.

**Already validated (this session, not needing the live harness):** the command BODY —
`bin/prawduct-hook subagent-stop` with a SubagentStop-shaped stdin — is pinned by
`tests/test_subagent_stop.py` (delegates to consolidate, scoped+bare agent_type,
cwd-locates-project, always exit 0 incl. on a stale consolidation, defensive gate on a
wrong agent_type). The consolidation core itself is `tests/test_critic_consolidate.py`.

**Verify (post-update, in a real medium+ session that triggers a coordinator review):**
- Run a `final`/`cumulative` `/prawduct:critic`; confirm the coordinator writes
  `.prawduct/.critic-partials/manifest.json` and dispatches three `critic-reviewer`
  subagents that each write the partial path the manifest's `rendezvous` names for their role
  (keyed by review id — an operator looking for a bare `<role>.json` will correctly find none).
- Confirm that as the reviewers finish, `.critic-findings.json` appears with a
  `review.critic` ledger anchor and the `.critic-active` marker is cleared — WITHOUT
  the main loop having run `critic-consolidate` by hand (i.e. the hook did it).
- If findings do NOT appear event-driven, the session-end backstop must still block on
  the lingering marker (the floor) — confirm that too, then investigate the matcher
  string (`prawduct:critic-reviewer` vs `critic-reviewer`) against the installed version.

## VRF-003 — Chunk 05 — Coverage chain advances layer 0 → layer 1 in the live briefing

**Status:** pending
**Added:** 2026-07-16 (structural-coverage Chunk 05)
**Where to verify:** The next real Claude Code session opened in this repo (a `clear`
hook run), reading the SessionStart briefing.

**Why a human/live check:** the layer transition is agent-verified below through the
`coverage-status` doctor report, but the operator-facing surface is the SessionStart
*briefing advisory* — whether the nudge a human actually sees has advanced from the
discovery-not-captured line to the strategy-artifact-missing line. That end-to-end
path (hook → probe roster → briefing text) is exercised only by a live session start.

**Already observed (this session, via the real CLI — not needing a fresh session):**
- BEFORE recording `classification.structural`, `prawduct-hook coverage-status`
  reported `Layer 0 · discovery: characteristics NOT RECORDED`, `Active nudge → Layer 0`.
- AFTER recording prawduct's six reconciled characteristics, the same command reports
  `Layer 0 · discovery: characteristics RECORDED`, `Layer 1 · strategy artifacts: 7
  expected artifact(s) missing`, `Active nudge → Layer 1` — the five universal plus
  `api-contract.md (exposes_programmatic_interface)` and `architecture.md
  (multi_process_distributed)`. `--json` confirms `active_layer: 1`,
  `structural_recorded: true`. No strategy-class artifact was authored (fixture stays empty).

**Verify (next session):**
- The briefing NO LONGER prints the `DISCOVERY NOT CAPTURED` block (layer 0 cleared).
- The coverage advisory now names the missing strategy-class artifacts (layer 1), and
  it is a single `info` nudge, not a double-nag with any layer-0 or layer-2 line.

## VRF-004 — Chunk 01 (backlog-service) — CLI file/get round-trip + JSON envelope

**Status:** verified (2026-07-17, throwaway repo `brookstalley/prawduct-backlog-smoke`)
**Added:** 2026-07-16 (backlog-service Chunk 01 — walking skeleton; renumbered from VRF-003
on the 2026-07-17 develop merge — the id collided with structural-coverage's VRF-003 above)
**Result:** L5 live smoke passed through `cli.run`; the hand round-trip confirmed every
eyeball item — canonical `owner/repo#N` id, `stage:ready` label, `v: 1` body block,
title/stage round-trip, `status`→`open`, valid `--json` (jq on the raw stdout), SEC-1 clean
(no token / `proxy-injected` / `x-oauth` in std{out,err}), GV6 (namespaced labels created,
GitHub-default + a fixture `keep-me` label untouched). SPIKE facts confirmed: issue numbers
`1..4` monotonic/never-reused (M6); `If-None-Match` conditional GET returns `304 Not
Modified` (ETag/304). Raw issue shape captured for the fake (CONTRACT-1): keys incl.
`number`, `node_id` (`I_kwDO…`), `state`, `labels[].name`, timestamps.
**Where to verify:** a throwaway GitHub repo with `gh` authenticated (`repo` scope). Run the
gated L5 smoke, or drive the CLI by hand:

    BACKLOG_LIVE_REPO=you/throwaway python -m pytest tests/test_backlog_smoke_live.py -q
    # or:
    prawduct-hook backlog provision --repo you/throwaway
    prawduct-hook backlog file --repo you/throwaway --title smoke --body hi --stage ready --json
    prawduct-hook backlog get <printed-id> --json

**Consuming the `--json` correctly (avoid a false "malformed output"):** pipe the command's
stdout *directly* to jq (`… --json | jq .`) or redirect to a file. Do **not** capture into a
shell variable and `echo "$out" | jq` under **zsh** — zsh's `echo` builtin interprets `\n`
escapes, re-introducing raw newlines that make valid JSON look malformed. The `--json` bytes
are correct (`json.dumps`, cli.py `_emit`); the corruption is consumer-side.

**Why a human check (absorbs the Done-when step-0 `verify-api`/CONTRACT-1 obligation):** the
L1 suite proves the logic against the in-process fake, but the fake's *behavior*
(read-your-writes on create, real label-create semantics, `node_id`/number assignment, the
exact JSON shapes) is confirmed only against live GitHub — Test Specs §2.1: behavioral
fidelity is the L4/L5 spikes' job, not the shape-diff. This live pass is where the real
response shapes get captured to seed/confirm the fake (CONTRACT-1), and where SPIKE-S1's
core-gating facts are confirmed: issue numbers are never reused (M6), ETag/304 conditional
GET works. Run 2026-07-17 — see **Result** above.

**Verify (human eyeballs) — all confirmed 2026-07-17:**
- `file` returns a canonical `owner/repo#N` id immediately; the issue exists with the
  `stage:ready` label and a `prawduct` body block (`v: 1`).
- `get <id>` round-trips title/stage; `status` decodes to `open` (no status label).
- `--json` output is pure JSON on stdout (`| jq .` never chokes); **no token or the
  `proxy-injected` literal appears anywhere** in stdout/stderr (SEC-1).
- `provision` creates the namespaced `stage:`/`status:` labels and leaves any pre-existing
  non-prawduct labels untouched (GV6).

## VRF-005 — Chunk 02 (backlog-service) — live two-axis status transition + label-remove encoding

**Status:** pending
**Added:** 2026-07-17 (backlog-service Chunk 02 — state-machine keystone)
**Where to verify:** a throwaway GitHub repo with `gh` authenticated (`repo` scope). Run the
gated L5 status smoke, or drive the CLI by hand:

    BACKLOG_LIVE_REPO=you/throwaway python -m pytest tests/test_backlog_smoke_live.py -q
    # or:
    prawduct-hook backlog status you/throwaway#<n> --to in-progress --json
    prawduct-hook backlog status you/throwaway#<n> --to shipped --json

**Why a human/live check (fake-unconfirmable):** the L1 suite proves the crash-safe write order
(`set-status`, CRASH-1) and the CAS/mass-assignment guards against the in-process fake, but three
behaviors are confirmed only against real GitHub —
1. **label-remove path encoding:** `GhTransport.remove_label` URL-encodes the label name
   (`quote(name, safe="")`), so `status:in-progress` → `status%3Ain-progress` in the DELETE path;
   real `gh api`'s handling of the encoded colon is not exercisable by the fake.
2. **reopen clears `state_reason`:** the transition `shipped → in-progress` PATCHes `state: open`
   and expects GitHub to clear `state_reason` (the decoder relies on it).
3. **`add_labels` is additive / never a zero-label window** on real GitHub during an open sub-state
   transition (`submitted → in-progress`).

**Verify (human eyeballs):**
- `status --to in-progress` on an open item: the issue gains `status:in-progress` and (if it had
  one) loses the prior open sub-state label; the decoded `status` is `in-progress`.
- `status --to shipped`: the issue is **closed** with `state_reason: completed`, **no** `status:`
  label remains, decoded `status` is `shipped`; a re-run is a clean no-op (exit 0, unchanged).
- `--json` stays pure JSON; **no token / `proxy-injected` literal** appears anywhere (SEC-1).

## VRF-006 — Chunk 06 (backlog-service) — prawduct-first migration: scrub dispositions + migrated repo + live briefing

**Status:** VERIFIED 2026-08-01 — the real migration ran. See § "Settled facts" below.
**Added:** 2026-07-17 (backlog-service Chunk 06, offline deliverables landed; live
migration/repoint/retirement deferred to an owner-run session after design sign-off)

> ### ✅ VERIFIED — 2026-08-01, v3.2.0 Chunk 06, owner-run
>
> **Settled facts (raw tool output, not narration):**
>
> ```
> import:           371 created, 0 skipped, 0 collision(s) of 371 source item(s)
>                   (152 restructured by plan)
> pacing:           ≥6548 REST points; no throttling (budgets never bound)
> unreconciled:     none — the "imported but NOT reconciled" line is ABSENT
> verify-migration: {"source_items": 371, "aliased": 371, "missing": [],
>                    "unaliasable": [], "collisions": [], "status_mismatch": [],
>                    "duplicate_alias": []}   exit 0
> post-import:      42 dispositions applied, 42 of 42 clean (24 merges, 18 drops)
> tracker after:    155 open / 149 shipped / 67 dropped = 371
> ```
>
> **The owner-eyeball checks below, answered:**
> - **Disposition list** — 42 applied, every one owner-confirmed (18 from 2026-07-18, 24 from
>   Survey 3). Nothing hard-deleted: drops are *closed*, duplicates *merged with a
>   `superseded_by` redirect written before the close*, bodies preserved.
> - **Spot-check** — `MIG-M4-REMOVE` resolves (decision 4's superseded consequence, proved live:
>   the multi-hyphen id carries a real alias rather than a content digest); `CRT-9K2P` carries the
>   plan's restructured title; the three `promoted` items resolve.
> - **Live briefing** — `post_cutover` is True and `probe_migration_required` now fires **0 times**,
>   so done-when 4 is satisfied *as a consequence* rather than as separate work.
> - **`legacy.py` NOT retired** — struck per GV7/MG3, and independently required, since
>   `lib/backlog/migrate.py` reads through `legacy.parse_backlog`.
> - **Drop-box NOT retired** — the MG5 leg stays gated by BKL-9XQ2.
>
> ### ROLLBACK (done-when #5 — MG1: rollback = close, never delete)
>
> **There is no undo. GitHub has no ordinary issue-delete and never reuses numbers**, so the 371
> issues this created are permanent. "Rollback" means **neutralise**, not remove, and it has two
> independent halves — do both or the repo is left in a worse state than either:
>
> 1. **Unset `backlog_service_repo` in `project-state.yaml`.** That alone restores the markdown as the
>    live backlog, un-retires the markdown-premise advisory probes, and silences
>    `backlog-checks-dormant`. It is a one-line revert and it is the *only* half that matters for
>    getting the repo working again.
> 2. **Close the migrated issues**, filtering on the `id:` alias namespace so the 9 pre-existing
>    native issues are untouched — they predate the migration and are not ours to close. Closing is
>    optional for correctness and required for tidiness; an abandoned open set on a public repo reads
>    as a live backlog to anyone who finds it.
> 3. **Revert the FROZEN-HISTORY banner at the head of `.prawduct/backlog.md`.** Easy to miss,
>    and it is the step that makes the other two coherent: the import never mutated that file,
>    but the cutover commit added a banner declaring it dead and pointing at the tracker. Run
>    steps 1 and 2 without this and the restored live backlog announces that it is frozen and
>    redirects readers to a tracker step 2 has just closed.
>
> **The markdown is still authoritative-as-of-migration, which is what makes this recoverable at all**
> — it was never mutated by the import, so unsetting the scalar returns the repo to a working state
> with a corpus that is stale by exactly the work done since. **What does NOT come back** is the 42
> dispositions: they were applied on the tracker only, deliberately, so a rollback restores 24 items
> the owner had merged away and 18 the owner had dropped. Re-applying them to the markdown by hand is
> the cost of rolling back, and it is the reason to be sure before doing so.
>
> ### Done-when #3's "no duplicates on a re-run" — NOT verified, and verifying it is now destructive
>
> **Stated honestly rather than claimed.** The obvious check is to re-run the import and confirm the
> alias-keyed skip path creates nothing. **That check cannot be run now without undoing this session's
> work**: `migration-scrub.md` records that the skip path *still reconciles status*, so a re-run
> re-syncs every already-migrated item to its **markdown** status — which would **reopen all 42 items
> disposed after the import**. The acceptance check is destructive once dispositions are applied.
>
> What stands in its place, and why it is strong evidence for the same property: `verify-migration`
> reported **0 `collisions` and 0 `duplicate_alias` across 371 aliased items**, and the skip authority
> is the `id:PFX` label written atomically in the create, guarded by
> `tests/test_backlog_migrate.py::TestArchiveScope::test_open_then_all_backfills_the_archive_without_duplicating`.
> That is the mechanism the sub-clause is really about. **It is not the same as having re-run it**, and
> this entry does not pretend otherwise.
>
> This sharpens the ordering defect filed as `#528`: the gate must run before disposals *and* the
> re-run acceptance check must run before them too, which means both belong in one ordering fix.
>
> **Two residuals, neither a blocker, both recorded rather than discovered later:**
>
> 1. **`promoted` has no Issues-backend equivalent.** The adapter's status enum is
>    `submitted|open|in-progress|shipped|dropped`, so the three `promoted` source items decoded to
>    **`open`**. That is the right degradation — promoted means in-flight — but it is a **vocabulary
>    loss**, and the frozen markdown is now the only place that distinction survives.
> 2. **`verify-migration` must run BEFORE post-import disposals, and the runbook's Step 4→5 ordering
>    says the opposite.** The gate compares each covered item's decoded status against the **source
>    markdown**, so folding a duplicate whose source status is `open` makes it read as
>    `status_mismatch`. Disposing first would turn the scrub's own owner-confirmed decisions into a
>    false exit 4. The gate certifies *the migration* — that nothing was stranded; the disposals are
>    tracker actions taken after it. Filed.
**Where to verify:** A real owner-driven session, after design sign-off, running the
migration-scrub runbook (`skills/backlog/migration-scrub.md`) against a chosen target
repo — first SPIKE-S2 (`tests/spikes/s2_migration.py`) on a throwaway copy, then the
real prawduct backlog.

**Why a human check:** the scrub's disposition decisions and the fidelity of the
migrated backlog are, by design, owner-confirmed (MG4/MIG-5) — no automated test can
sign off on *which* items are stale/duplicate or that the migrated bodies read
correctly. Chunk 06's acceptance is the dogfood itself.

**Verify (owner eyeballs):**
- The **scrub disposition list** — every stale/dup disposition is one the owner
  confirmed; no item was dropped silently and nothing was hard-deleted (dropped items
  are *closed*, duplicates *merged+redirected*, bodies preserved).
- A **spot-check of migrated bodies/IDs** — a handful of items read verbatim on
  GitHub Issues and every hand-minted `PFX` resolves as an `id:PFX` alias.
- The **live briefing counts** — session start reads the backlog count through the
  adapter (not `legacy.py`), with a visible age, and never hangs when GitHub is slow.
- The `incoming-bugs/` drop-box is retired only *after* the above, and only in lockstep with its
  MG5 replacement. **`legacy.py` is not retired at this cutover at all** — GV7/MG3 hold it as the
  shared markdown read path until the whole portfolio has migrated.

**Drop-box retirement — verify the lockstep replacement (BKL-0QR1, resolved 2026-07-17 → option c):**
`incoming-bugs/` is retired **only together with** its minimal same-repo replacement (PRD §8.9/MG5),
never before it. Before/at the retirement, eyeball that the replacement is live:
- `/prawduct:report-bug`, on the reachable-channel path, files an `untriaged-upstream`-labeled
  **GitHub issue** into prawduct's own (public) repo via the adapter — no `incoming-bugs/` file write.
- The `untriaged-upstream-reports` advisory counts those **labeled open issues**, not `incoming-bugs/*.md`.
- The **no-channel fallback** still degrades cleanly to local capture + the canonical-tracker pointer.
- Only *then* is `incoming-bugs/` retired (`legacy.py` is **not** — GV7/MG3, portfolio-wide only).
  The full XP1 cross-owner/foreign-identity
  plane stays **W3** — it is deliberately *not* in this slice.

## VRF-007 — Chunk 02 (backlog-skill-repoint) — /prawduct:backlog drives Issues end-to-end through the skill

**Status:** pending
**Added:** 2026-07-19 (backlog-skill-repoint Chunk 02 — read + write ops via the adapter)
**Pre-verified (adapter loop, 2026-07-19):** the adapter substrate the skill drives is confirmed live
against the private throwaway `brookstalley/prawduct-backlog-smoke` — reads (`counts`/`list`/`list
--filter`/`get`/`pick`), writes (`file`/`status`/`claim`/`link`/`update`/`status --to dropped`), the
`promoted`→`in-progress` bridge (a `status:in-progress` label was applied live), not-found (exit 3),
and stale-timestamp conflict (exit 4). One doc bug caught + fixed: the `get` envelope does not expose
`updated_at`, so the update guidance dropped the unimplementable get-then-`--if-updated-at` step.
**Remaining for the drain:** the model actually executing `adapter-mode.md` in a real sibling
*session* via `--plugin-dir` — the prose-routing confirm a headless adapter loop can't cover.
**Where to verify:** A sibling product repo pointed at this checkout via `--plugin-dir=../prawduct/plugin`,
with `backlog_service_repo: owner/repo` set in its `.prawduct/project-state.yaml` and `gh`
authenticated. This is **Phase 1** of the migration program (the owner-scoped dogfood) — it exercises
the repointed skill against real Issues without touching prawduct's own backlog.

**Why a human check:** skills are prose the model executes — there are no unit tests for skill
behavior, and `--json`-shape checks never exercise the human output. Only a real run confirms
legibility, the dual-mode routing, and that nothing silently reads the frozen markdown.

**Verify (drive the real loop through the skill, eyeball the human output):**
1. `/prawduct:backlog` (no args) → the adapter `counts` rollup + menu (not the frozen markdown file).
2. `add` → files a real GitHub issue (issue-standard title; any `lint` WARN surfaced); `list` shows it.
3. `update <id> status=promoted` → maps to **`in-progress`**; a field change (title/stage/area)
   round-trips — the edit is reflected by a following `get`/`list`; `claim` and `link` work; `pick`
   returns adapter ranked ready-work with the build-plan-overlap + stage framing intact.
   (The `--if-updated-at` guard is deliberately **not** exercised: the `get` envelope exposes no
   `updated_at`, so the skill's normal path omits it — see the Pre-verified note above.)
4. `find`/`dedup` → the **W2-deferred NOTE** (not a fabricated search); `migrate`/archive-split → the
   not-applicable NOTE.
5. **Fail-loud:** break `gh` auth (or point at an unreachable repo) → a clear NOTE, and **never** a
   silent fall-back to the frozen markdown.
6. **Markdown path unchanged:** with `backlog_service_repo` unset, the skill behaves exactly as before.

Drains when Phase 1 runs.

## VRF-008 — Chunk 01 (skills-cutover-awareness) — dormancy is stated, not silently wrong

**Status:** superseded
**Added:** 2026-07-19 (skills-cutover-awareness Chunk 01 — GV8 interim contract)
**Superseded:** 2026-08-07 by the backlog read-through cache (Chunk 06), which **restored every
reader this entry verified as dormant.** Do not drain it — its eleven steps now assert the inverse of
what ships: step 1 wants the `backlog-checks-dormant` advisory at session start (the probe is
deleted), steps 2 and 6 want the Critic's walk and the PR reviewer's R-1/R-2 to emit an "unavailable"
NOTE *instead of* running (both now run and emit per-item findings by design), step 8 wants the
janitor's Backlog Health block to be a single unavailable line with none of its checks having run
(four now run), and steps 10–11 pin the wording of NOTEs that no longer exist. An operator working
through it would report a failure against correct behaviour, or 'fix' the restored readers back to
dormancy. Superseded by **VRF-015**, which verifies the restored contract. Kept rather than deleted —
this file is append-only, and the record of what was once verified is the point.

**Why a human check:** the deliverable is a *stated absence*. Tests pin that the probe fires and that
its operator-facing strings don't contradict each other, but no test can confirm that a reviewer
reading `review-cycle.md` actually skips the walk and says so — skills are prose a model executes.
The failure this chunk exists to kill (confident findings drawn from frozen markdown) is only
observable in a real run against a cut-over repo. This is the VRF-007 lesson applied: a prose→CLI
handoff survives clean multi-reviewer review and still fails live.

**Where to verify:** the cut-over sibling product repo, pointed at this checkout via
`--plugin-dir=../prawduct/plugin`, with `backlog_service_repo` set.

**Verify:**
1. Session start → the `backlog-checks-dormant` advisory appears once, `info` priority, naming the
   dormant checks. It must read as an accepted interim state, not as an error.
2. `/prawduct:critic final` (or `cumulative`) → Backlog Reconciliation emits the single
   "unavailable" NOTE and **no** per-item findings. Confirm no finding cites an item that was
   archived at cutover — that is the exact false positive this replaces.
3. Confirm the reviewer did **not** open `.prawduct/backlog.md` for live state.
4. Dismiss the advisory → it stays dismissed on the next session, and the Critic NOTE still appears
   (dismissal silences the reminder, never the review-time statement).
5. **Pre-cutover unchanged:** in a repo with `backlog_service_repo` unset, no advisory and the
   backlog walk runs exactly as before.
6. **The PR path (Chunk 02) — R-2 specifically.** `/prawduct:pr create` in the same cut-over repo →
   the PR reviewer emits the single "unavailable" NOTE in place of R-1/R-2 and cites no `PFX-XXXX`
   from the frozen file. R-2 needs its own live check rather than riding step 2's: it is the sole
   owner of the `closes:`-vs-open consistency check (no Critic layer runs it), so a reviewer that
   silently keeps resolving `closes:` against frozen markdown looks *identical* to one that correctly
   found nothing — the failure mode is invisible in the output, which is why only a live run shows it.
7. **Pre-cutover PR path unchanged:** with `backlog_service_repo` unset, R-1/R-2 run as before —
   confirm R-2 still flags a deliberately-planted `closes:` for an item left `status: open`.

8. **The janitor (Chunk 03).** `/prawduct:janitor` in the same cut-over repo → the findings report
   contains the Backlog Health block as a single "unavailable" line — **present, not omitted**. An
   omitted section is the failure this replaces: it reads as a clean bill of health. Confirm none of
   the seven checks ran, in particular that no finding proposes `/prawduct:backlog migrate` or an
   archive split (checks 6 and 7 — advice an operator could act on to no effect post-cutover), and
   that Step 1's overlap context came from `/prawduct:backlog list` rather than the frozen file.
9. **Pre-cutover janitor unchanged:** with `backlog_service_repo` unset, all seven Backlog Health
   checks run and report as before.
10. **The emitted NOTEs name no internal id (Chunk 04).** Across steps 2, 6, and 8, confirm each
    "unavailable" NOTE ends with the plain-language resolution ("they return when the backlog
    read-through cache lands") and cites no `GV8`/`W1`-style identifier — the operator reading it has
    no register to resolve one against.
11. **The backlog skill's markdown-only rules stay quiet (Chunk 04).** `/prawduct:backlog find <q>`
    → the deferred-search NOTE, naming no internal milestone id; and no surface proposes an archive
    split. Confirm the skill never opened `.prawduct/backlog.md` for live state.

Drains when a cut-over repo runs a `final`/`cumulative` review **and** a `/prawduct:pr create` **and**
a `/prawduct:janitor` on this plugin build. Each of the three dispatches a different reader and none
substitutes for another: a Critic run never dispatches the PR reviewer (steps 6-7), and neither one
runs the janitor (steps 8-9) — draining on a subset would leave the unexercised readers reading as
verified. This is the plan's Verification Strategy stated as a drain condition rather than as prose
alongside one.

## VRF-009 — Chunk 05 — SPIKE-S2 live migration dry-run (paced archive burst + fidelity)

**Status:** verified
**Run:** 2026-07-24 (SPIKE-S2 live dry-run, `--archive-scope all`)
**Where run:** private throwaway `brookstalley/prawduct-s2-dryrun-20260724` (created for this run —
deletion pending; the session `gh` token has `repo` but not `delete_repo` scope, so the owner removes
it). Invocation:
`python tests/spikes/s2_migration.py --repo brookstalley/prawduct-s2-dryrun-20260724 --yes --archive-scope all`
(`--from .prawduct/backlog.md` default; **no** `--archive` file — the full backlog already carries the
`## Archive` section, so archived items create-then-close from the main source under scope `all`. Passing
`--archive` at the same file would double-parse; the non-PFX archive item would duplicate).

**This is the SPIKE-S2 that VRF-006 names as the prerequisite** ("first SPIKE-S2 on a throwaway copy,
then the real prawduct backlog") — now done. It does **not** run the real migration (still VRF-006).

**Settled facts (raw harness output):**
```json
{
  "aliases_minted": 294,
  "archive_burst_wall_seconds": 1086.422,
  "archive_scope": "all",
  "content_creation_wait_seconds": 0.0,
  "content_creation_waits": 0,
  "fidelity_ok": true,
  "new_pfx_minted": [],
  "node_id_stable_across_transfer": null,
  "pacer_budgets": {"per_hour_creates": 500, "per_minute_creates": 80, "per_minute_points": 900},
  "pick_latency_ms_by_candidates": {"1": 25501, "3": 25787, "5": 27778},
  "relationships_reconstructed": false,
  "rest_point_wait_seconds": 0.0,
  "rest_point_waits": 0,
  "rest_points_charged": 5360,
  "resume_created_duplicates": 0
}
```

**Confirmed live:**
- **Volume + idempotency:** live tally **148 open / 147 closed / 295 total** — exactly the parser's
  prediction (148 open + 147 archived→closed). `resume_created_duplicates: 0`; a second full import was a
  pure no-op (find-or-create skip). No over/under-creation, no duplicates.
- **Body fidelity (live MIG-1):** `fidelity_ok: true` — every hand-minted PFX item's body survived
  import→export→diff verbatim.
- **ID aliasing (live MIG-2):** `aliases_minted: 294` (all 294 PFX source items; the 295th
  pending/archived item carries no PFX), `new_pfx_minted: []` — no PFX minted on import.

**The §9 S2 pacing result — and a correction to last session's prediction:**
- `rest_point_waits: 0` **and** `content_creation_waits: 0` — **neither the 900-pts/min REST ceiling nor
  the 80-creates/min ceiling ever engaged.** `rest_points_charged: 5360` (write=5 / read=1; 295 creates +
  147 closes = 2,210 write-points, the ~3,150 balance is reads) over `archive_burst_wall_seconds: 1086`
  (~18 min) ≈ **296 pts/min average**. Peak: an archived item = read+create+close ≈ 11 pts over ~3 serial
  round-trips (~1.3s) ≈ **~500 pts/min** — still under 900.
- **`rest_points_charged` is a FLOOR, not an exact count (BKL-3H7W).** `_PacingTransport` charges per
  transport *method* call, so a paged read (`list_labels`) issues several HTTP requests and is charged
  once. The undercount falls entirely on the read side — the ~3,150 read-point balance above is the
  soft number; the 2,210 write-points (295 creates + 147 closes) are exact. Direction of the error is
  known: **real usage is higher than measured, so the headroom is smaller than these figures state.**
  The conclusion survives — even a 3× read undercount lands near ~644 pts/min against the 900 ceiling —
  but "296 pts/min" should not be quoted as the margin. Re-derive when BKL-3H7W makes the meter exact.
- **Root cause (I predicted the opposite last session).** I forecast `point_waits > 0`, reasoning that
  147 archived items sit "comfortably over" a ~75-item threshold. That was wrong — it conflated *total
  volume* with *per-minute rate*. Serial `gh` round-trip latency caps the create-then-close rate at
  ~40–45 items/min (~500 pts/min) **regardless of total count**, so the 900/min ceiling is never breached
  no matter how large the archive. **Settled constant for NFR §9 S2: under the serial importer the Pacer
  budgets (80/min, 500/hr, 900 pts/min) are a non-binding safety belt, not the active governor; wall-clock
  is latency×call-count (~442 writes + ~3,150 reads ≈ 18 min), not pacing-limited.** The point ceiling
  would bind only if writes were parallelized/batched — untrue today. Flag this fact if that changes.

**Not exercised by this run (honest gaps, not failures):**
- **Relationships (live MIG-3):** `relationships_reconstructed: false` — **expected**: the source backlog
  has no native `blocked_by`/`sub_issues`/parent metadata (only a free-text `related:` field), so there
  was nothing to reconstruct. MIG-3 stays unproven *live*; the in-process MIG-3 test remains its only
  evidence until a source with a native graph is migrated.
- **Pick latency / PROBE-LAT:** `pick_latency_ms_by_candidates` = 25.5s / 25.8s / 27.8s. **This probe
  confirms nothing. Both claims originally recorded here were false** (corrected 2026-07-24 after the
  cumulative Critic review; verified against the code, not conceded):
  - ~~"flat across 1→3→5 candidates confirms the batched-GraphQL path (not N+1)"~~ — **there is no
    GraphQL anywhere in `plugin/lib/backlog/`** (zero matches), and `query.pick` is **exactly the N+1 shape the
    claim denied**: it calls `transport.list_blocked_by(owner, repo, number)` once **per candidate issue**
    inside the loop (`query.py:180`).
  - **The probe cannot detect N+1 by construction.** `limit` is applied at
    `candidates[: max(0, limit)]` (`query.py:196`) — *after* the full per-issue fan-out has already run.
    So varying it 1→3→5 cannot change the number of transport calls, and flatness was **guaranteed**
    regardless of the underlying shape. A flat result was the only possible outcome; it is not evidence.
  - The absolute value is *also* contaminated (the picks ran immediately after a 5,360-point burst, so
    the reads almost certainly ate `RateLimitBackoff` sleeps) — but that was never the main problem.
  - **Net: NFR §4 PROBE-LAT is entirely unsettled by this run** — neither the absolute floor nor the
    call-shape. A real answer needs a probe that varies the *candidate-set size* (which drives the
    fan-out) against a quiescent repo, not `limit`.
  - **Why this is recorded rather than quietly deleted:** the failure was reading a confirmation into a
    measurement whose design could not have produced a disconfirmation. That is the same
    false-reassurance class as BKL-8V3D and the phantom target-pin — a safety/performance claim asserted
    where nothing checked it — and this instance was authored *by the same session that was hunting that
    class elsewhere.*
- **node_id across transfer (ID-4 / step 7):** `null` — not run (`--transfer-to` omitted; needs a second
  throwaway repo). Genuinely open.

**Follow-ups:**
- Owner deletes throwaway `brookstalley/prawduct-s2-dryrun-20260724` (needs `delete_repo` scope).
- Optional: node_id-transfer probe (second throwaway + `--transfer-to`) to settle ID-4.
- Optional: clean PROBE-LAT floor — `pick` against a quiescent migrated repo, no preceding burst.

## VRF-010 — Chunk 05b / F1 — the three relationship-timeline readers, live

**Status:** verified (2026-07-28, throwaway repo `brookstalley/prawduct-readers-20260728`)
**Added:** 2026-07-28 (functional-audit F1 — the readers no migration exercises)

**Why this run existed.** `BKL-3N8Q` records that `list_blocked_by` / `list_sub_issues` /
`list_timeline` are shape-verified against the in-process fake only. Three live migrations
(~209 items 2026-07-17, 295 items 2026-07-24) never touched them, and the reason is
structural rather than an oversight: **the importer maps `related:` to no native edge**, so a
migration creates zero dependencies and zero sub-issues. Only a purpose-built graph exercises
these three. Cost: 3 issues, 2 links.

**Result — all three readers work against real GitHub; the fake's shapes match.**

- **`list_blocked_by`** — `link #2 blocked-by #1`, then `pick` returned **only #1** (blocked
  item correctly excluded). Closing #1 and re-picking returned **#2** with `all 1 blocker
  closed`. Both directions of the predicate are live-correct. The real payload carries
  `number`, `state`, `repository.owner.login`, `repository.name` — exactly the keys
  `GhTransport.list_blocked_by` parses. It also carries `issue_dependencies_summary`
  (`blocked_by` / `total_blocked_by` / `blocking` / `total_blocking`), which the adapter does
  not read.
- **`list_sub_issues`** — `link #2 child #3`; the endpoint returns `{number, state, title}`,
  parsed correctly.
- **`list_timeline`** — events observed on #1: `labeled`, `blocking_added`, `closed`.

**MIG-3 is now live-proven, for the first time.** `export` calls all three through the
transport, and this repo had the native graph SPIKE-S2 and VRF-009 both lacked. The dump is
correct: `#2 → {blocked_by: [#1], sub_issues: [#3]}`, `#1` and `#3` empty. VRF-009's
"MIG-3 native-graph reconstruction is UNPROVEN, not failed — a source with real sub-issue
trees needs a separate test" is **discharged by this run.**

**Chunk 05b's `_blocker_clause` fix is live-proven on both branches** — `no blockers recorded`
for an item with no dependencies, `all 1 blocker closed` for a verified-clear one.

**NEW FINDING (not a blocker; record before it bites someone) — `pick` can return an item
closed seconds earlier.** Immediately after `status --to shipped` on #1, `pick` returned #1 as
ready work. GitHub itself was already correct (`state: closed`, `state_reason: completed`,
`closed_at` set) and a direct `issues?state=open&labels=stage:ready` query already excluded
it — so this is **the list-endpoint replication window, not a filter bug**. A re-run seconds
later was correct. `file` has a bounded settle-retry for the documented 404-after-create
window; the **close→list** path has no equivalent. Real-workflow shape: an agent closes an
item, immediately picks its next task, and is handed back the item it just finished. File
against `BKL-3N8Q`'s family or as its own item; the fix is likely the same bounded
settle-retry `file` already uses.

**Where to verify:**

    R=you/throwaway
    prawduct-hook backlog provision --repo $R
    A=$(prawduct-hook backlog file --repo $R --title A --body x --stage ready --json | jq -r .data.id)
    B=$(prawduct-hook backlog file --repo $R --title B --body x --stage ready --json | jq -r .data.id)
    prawduct-hook backlog link $B --edge blocked-by --to $A
    prawduct-hook backlog pick --repo $R --limit 5 --json   # expect A only
    prawduct-hook backlog status $A --to shipped
    sleep 5 && prawduct-hook backlog pick --repo $R --limit 5 --json   # expect B, "all 1 blocker closed"
    prawduct-hook backlog export --repo $R --to /tmp/x       # expect the native graph in item-*.json

**Follow-ups:**
- Owner deletes throwaway `brookstalley/prawduct-readers-20260728` (needs `delete_repo` scope;
  the session token carries `gist`, `read:org`, `repo` only).
- `BKL-3N8Q` is now fully dischargeable: its `pick`-path half shipped with Chunk 05b, and its
  foreign-API-verification half is this run. Flip via `/prawduct:backlog` at Chunk 09.

## VRF-011 — Chunk 05b / BKL-8K2N — the import progress heartbeat, live

**Status:** verified (2026-07-28, throwaway repo `brookstalley/prawduct-readers-20260728`)
**Added:** 2026-07-28

**Result.** A 55-record live import emitted exactly the designed signal:

    backlog: migrating: 25/55 — 25 created, 0 skipped
    backlog: migrating: 50/55 — 50 created, 0 skipped
    brookstalley/…: imported 55 created, 0 skipped, 0 collision(s) of 55 source item(s)
      pacing: ≥716 REST points; no throttling (budgets never bound)

Two beats, no beat on the final record (the summary follows immediately), all on stderr.

**Measured throughput: 55 records in 1 min 46 s ≈ 31 records/min** — below the ~40–45/min VRF-009
inferred. Two consequences worth carrying into Chunk 06:

- **A ~900-issue migration is ~29 minutes** at this rate, inside the 18–40 min estimate but nearer
  its middle than its floor.
- **At 31/min, `PROGRESS_EVERY = 25` is a beat roughly every 48 s**, and the *first* beat lands ~48 s
  in. Judged acceptable and left alone: ~36 beats across a 900-record run is reassurance without
  becoming the commentary `test_an_unthrottled_run_stays_quiet` exists to forbid. **If an operator
  reports the startup silence as uncomfortable, lower the constant — do not add a separate
  first-record special case**, which is a second code path for one line of output.

**`no throttling (budgets never bound)` reproduced VRF-009 exactly** on an independent run — the
pacing budgets are confirmed non-binding under the serial importer for a second time, which is
precisely why the heartbeat had to exist: every pacing announcement is exception-only and none of
them ever fires.

**Caveat inherited from BKL-3H7W (still open):** the `≥716 REST points` figure is a **floor**, not an
exact count — a paged list costs 1 point regardless of page count. The `≥` in the output says so.

**Follow-ups:** the throwaway now holds 58 issues; owner deletes it (needs `delete_repo` scope).

## VRF-012 — F9 — `samsung-frame-art-loader` stranded-item recovery

**Status:** verified (2026-07-28)
**Added:** 2026-07-28

**Before.** `backlog_service_repo` set (so `post_cutover` True, markdown read as frozen history) while
`.prawduct/backlog.md` still held **9 open items**, only **2** of which (`CUI-WT3K` → #2,
`TVW-4Q7M` → #3) carried an `id:PFX` alias. The other 7 existed nowhere on the service.

**Recovery run (operator, plugin build `wt-prawduct-backlog` @ v3.1.2+branch):**

    prawduct-hook backlog import --repo brookstalley/samsung-frame-art-loader \
      --from .prawduct/backlog.md
    → imported 7 created, 2 skipped, 0 collision(s) of 9 source item(s)
      pacing: ≥126 REST points; no throttling (budgets never bound)

**`2 skipped` is the load-bearing number** — it proves the alias-keyed skip recognised the two
already-migrated items rather than duplicating them. `9 created` would have meant 7 duplicates in a
store with no delete. **A recovery re-import must be read on that field, not on success/failure.**

**After — completeness check, the one that should have run at the original cutover:**

    source items in backlog.md : 9
    issues carrying an id:alias : 9
    MISSING (source with no alias on target): NONE

All nine resolve: #2, #3 unchanged; `LEG-8H2P`→#19, `SEC-K3V9`→#20, `ARC-7QN2`→#21, `REL-M5X8`→#22,
`REL-2JH6`→#23, `ARC-B4TD`→#24, `TST-9WFC`→#25, all OPEN. Repo total 24 = 17 prior + 7 new.

**No heartbeat fired, correctly** — 9 records is below `PROGRESS_EVERY` (25), which is the designed
silence for a short run. Worth stating because an operator primed to watch for it could read the
absence as a hang.

**`no throttling (budgets never bound)`** — third independent confirmation, after VRF-009 and VRF-011.

**`backlog.md` is now correctly frozen history** and should be left in place: MG3 binds the markdown
read path until the *last* project cuts over, so deleting it is not the tidy-up it looks like.

**What this does NOT close.** The recovery fixed the instance; the defect that produced it is
untouched — **cutover (step 6) still has no precondition on verification (step 5)**, and the
completeness comparison above is a hand-run script, not a command. See functional-audit F9.

## VRF-013 — Chunk 06 pre-run gate — the two transport/pagination defects, live read-only

**Status:** pending
**Added:** 2026-07-31

**Why this exists.** `.prawduct/artifacts/migration-scrub-decisions.md` carries a **pre-run gate**
added 2026-07-18 (holistic Fable review): *"the run is BLOCKED until the two transport/pagination
defects are fixed and live-verified read-only against the real repo (>30 labels, 127+ PRs)."* Both
code paths were re-read 2026-07-31 and **both look correct** — but no VRF records the live half, and
VRF-009/011 ran against a *throwaway* repo, not a repo at the scale the gate names. The gate asks for
evidence at scale; this entry is that evidence. **Read-only: no writes, no issues created, nothing
mutated.** Cost: a handful of API reads.

**Set up once.** From the prawduct checkout, with `gh` authenticated:

```sh
python3
```

```python
import sys; sys.path.insert(0, "plugin")
from lib.backlog.transport import GhTransport
t = GhTransport()
OWNER, REPO = "brookstalley", "prawduct"
```

**Fact 1 — multi-page reads reassemble correctly (the `--paginate` multi-doc JSON defect).**
`_api_paged` uses an explicit page loop rather than `gh --paginate`, because that flag emits each page
as a *separate JSON document* and a single `json.loads` over the concatenation fails the moment a
result exceeds one page. `per_page` is injectable precisely so a live check can force multi-page
behaviour against a real dataset that isn't yet huge. Run:

```python
one  = t._api_paged(f"repos/{OWNER}/{REPO}/labels", per_page=100)
many = t._api_paged(f"repos/{OWNER}/{REPO}/labels", per_page=2)
print(len(one), len(many))
print({l["name"] for l in one} == {l["name"] for l in many})
```

**PASS:** both counts equal, and the name sets are identical (`True`). `per_page=2` forces many pages
over the same data, so an equal result proves the loop reassembles rather than truncating or throwing.
**FAIL:** any exception (especially a `json` decode error), unequal counts, or `False`.

**Fact 2 — the terminator reads the RAW page, not the PR-filtered view.**
This is the sharper defect. `iter_alias_issues` scans `issues` — an endpoint where **pull requests
interleave with issues** — filters PRs out inside the loop, and must test `len(batch) < per_page`
against the **unfiltered** batch. If the length test ever saw the filtered count, a page that happened
to be mostly PRs would look short and the scan would stop early, silently under-reporting alias
coverage — which is exactly what `verify-migration` reads to decide the migration is complete.
prawduct's own repo is the right test bed because it carries **127+ PRs**. Run:

```python
from lib.backlog import core
# Starred unpack, so a later widening of the yield cannot break this snippet in
# an operator's hands (it already widened once: `id_aliases` PFXs, labels, and
# now the decoded status the completeness gate compares).
seen = {n for n, *_rest in core.iter_alias_issues(t, OWNER, REPO)}
print("issues reached:", len(seen))
raw = t.list_issues(OWNER, REPO, state="all", per_page=100, page=1)
print("page 1 raw:", len(raw), "| PRs on page 1:", sum(1 for i in raw if "pull_request" in i))
```

**PASS:** `issues reached` is in the hundreds and clearly exceeds the non-PR count of page 1 — i.e.
the scan kept going past a PR-heavy page. **FAIL:** `issues reached` lands at or just under the non-PR
count of page 1, which is the early-termination signature.

**Fact 3 — the two remaining `_api_paged` readers behave on a real object.** `list_timeline` and
`list_sub_issues` share the same loop. Pick any real issue number `N` from `seen` above:

```python
N = sorted(seen)[0]
print(len(t.list_timeline(OWNER, REPO, N)), len(t.list_sub_issues(OWNER, REPO, N)))
```

**PASS:** both return without raising (0 is a fine answer — most issues have no sub-issues).
**FAIL:** an exception, which would mean the shared loop is wrong for those paths.

**What a pass discharges.** The 2026-07-18 pre-run gate, which is one of the named blockers on Chunk
06. Record the numbers observed — not just "passed" — so a later reader can tell this ran against the
real repo at real scale rather than a fixture.

**What a pass does NOT discharge.** `BKL-7V2D` (the completeness gate cannot see "imported but never
reconciled") is a separate Chunk 06 blocker — **fixed 2026-07-31**, so no longer outstanding, but still
not something this probe speaks to: it is about what `verify-migration` *inspects*, not about whether
pagination is sound. (That fix is also why Fact 2's snippet unpacks with `*_rest`: it widened
`iter_alias_issues` to yield the decoded status.) And `BKL-3H7W` (the meter under-counts paged reads)
is untouched by this — a paged list still costs 1 point regardless of page count.

---

## VRF-014 — v3.2.3 OWNER RELEASE GATE — go/no-go evidence

**Status:** verified

**All three items discharged as of 2026-08-02** — a dated fact; `git tag -l v3.2.3` is the live test
for whether the release has since published. *(The `**Status:** verified` line above is the shape
`_STATUS_LINE_RE` in `plugin/lib/operator_verification.py` actually parses — a bare token on its own
line. The previous prose-in-the-bold form fell through to `pending`, so `check-operator-verification`
read this discharged entry as still blocking. Critic N-7; six sibling entries carry the same shape and
are left alone rather than swept in a release commit.)*

The three gate items live in
`.prawduct/artifacts/release-plan-v3.2.3.md` § OWNER RELEASE GATE. Recorded here per that section's
own instruction ("Record the result in `.prawduct/operator-verification.md` … then run Phase 2").

**Each item was discharged by a different kind of evidence, and the difference is the point.** Item 2
by a verified scope argument (the carve-out names an unbuilt capability), item 3 by an explicit second
acceptance of a named residual risk, item 1 by owner attestation with its timing confirmed against
`6f443a2`. Read each section for what it does and does not establish before treating this header as a
blanket clearance — the header is a roll-up, not the evidence.

### Item 2 — "GitHub Issues is working great" — **DISCHARGED 2026-08-02**

**Owner statement (2026-08-02):** *"so far github issues ARE working great. the only thing not
validated is handling of private repos filing issues upstream. I think that is acceptable for now."*

Per the 2026-07-28 owner ruling this item is **functional completeness, not performance**: for every
*supported* scenario, no functional requirement is broken, unproven against the real API, or silently
wrong. `BKL-2K8V` (pick latency) is an NFR and explicitly does not gate.

**The named carve-out does not compromise the criterion, because the scenario is out of scope rather
than unproven.** Verified against the tree at 2026-08-02, not inferred:

- Private-repo upstream filing is pinned to **W3** and explicitly fenced:
  `documentation/backlog-service-prd.md:187` — *"arbitrary cross-owner targets, private repos,
  foreign-identity auth-by-target-owner … stays W3; do not pull it forward."*
- **No upstream GitHub-issue path ships at all in v3.2.3**, for public or private targets. The MG5
  leg is unbuilt: `artifacts/build-plan-backlog-service.md:121` carries Chunk 06 as `- [ ]`,
  `incoming-bugs/` is still present, and `plugin/lib/upstream_probes.py:56` still counts drop-box
  files rather than labeled issues.
- Today's upstream path therefore makes **no GitHub API call**: inbox reachable → a plain file write
  to `<inbox>/<slug>.md` ("no git operations, no commit"); no inbox → `report-bug/SKILL.md` §4
  **"do not attempt any upstream write"**, capture locally and point at the tracker URL.

Repo visibility cannot change behavior in a code path that makes no API call, so "unproven against
the real API" is not triggered. **Item 2 passes on scope, not on an accepted risk.**

**What this does NOT discharge.** Items 1 and 3 below. Also *not* discharged: any claim about a
private product repo running **its own** backlog on **its own** private Issues. That is a genuinely
shipping scenario on the same `gh` path with the same inherited auth, and `backlog.md:1379` scopes it
explicitly DO-NOT-BLOCK — but nothing here measured it, and the owner's statement was about upstream
filing, so it must not be read as covering it.

**Correction recorded so it is not repeated.** The owner's stated plan was to validate private-repo
upstream filing with their own private repos *immediately after release*. That plan targets an
unbuilt capability: post-v3.2.3, a private repo filing upstream reaches the drop-box or the inert
fallback, so the exercise would measure pre-MG5 behavior and could read as a false pass. **The real
checkpoint is the release that carries MG5**, which `.prawduct/backlog.md:1379-1381` already gates:
*BLOCK Chunk 06's MG5 leg and the release that carries it; DO NOT BLOCK a consumer migrating its own
backlog to its own Issues.* Note the exposure there is broader than private repos —
`backlog.md:1365` records that even the minimal **public-repo** replacement "already sends a
consumer's bug body into a public repo," making content-minimization (`BKL-7Q4M`) live at Chunk 06
rather than deferrable to W3.

### Item 1 — exercise the candidate in sibling repos via `--plugin-dir` — **DISCHARGED 2026-08-02, by owner attestation**

**Owner statement (2026-08-02):** *"already exerised. we're good."*

**Owner answer on timing (2026-08-02), verbatim — this is the load-bearing half, so it is quoted
rather than narrated.** Asked *"Did the sibling-repo exercise happen before or after PR #566
(drift-burndown) merged to develop today?"*, the owner selected:

> **"After — it covered today's tip"**
> *(option text: "The exercise loaded a candidate that already included drift-burndown.")*

**Why that question was asked rather than assumed.** This item's scope had *grown* after VRF-014 last
recorded it: `drift-burndown` merged as PR #566 (`6f443a2`) the same day, and two of its chunks are
exactly the class item 1 exists to catch — Chunk 03 makes the *green is evidence* directive fire
outside Python (invisible to this repo's own suite, which is Python), and Chunk 04 adds doctor
**Health Check #13**, which by construction only shows up in an already-onboarded *consuming* repo. So
the exercise is attested against the release as it now stands, not an earlier candidate.

**Where this record is weaker than the item's own template asks, stated so a later reader is not
misled.** The item's text calls for *"naming which sibling repos were exercised and what was
checked,"* and this record carries an owner attestation plus a timing confirmation instead of that
enumeration. No per-surface result is recorded for the two post-#566 surfaces above; they are inside
the exercised tree by the owner's confirmation, and nothing here measured them individually. That is
the owner's call to make and it is made — recorded at this granularity deliberately rather than
upgraded by inference, because writing repo names or check results that were not stated would be the
precise defect this file exists to prevent.

### Item 3 — migration advisory fleet-wide with `BKL-8W2M` unbuilt — **DISCHARGED 2026-08-02, by explicit second acceptance**

**Owner statement (2026-08-02):** *"item 3 -- yes, accept the amplified volume. It's a minor
annoyance, we can work on BKL-8W2M in the next few days."*

This is the **second acceptance** the gate item asked for, and it is recorded as its own decision
rather than folded into `BKL-7D3V` — the two accept different things:

| | `BKL-7D3V` (prior) | This acceptance |
|---|---|---|
| Who sees the `warn` | the **agent** only | the **person**, in conversation |
| How often | once per session, to stdout | every session, relayed |
| Resolvable by the recipient | no | no |

**What is being accepted.** In every un-migrated repo with a structured backlog,
`backlog-service-migration-required` fires at `warn` and `upgrade-discovery` Chunk 01 relays it to
the person **every session**, with `BKL-8W2M` (#197) unbuilt at `stage:requirements` — so there is no
action the recipient can take to make it stop short of migrating.

**The residual risk is not the nag.** It is **desensitization of the `warn` channel**: an
unresolvable advisory arriving every session teaches the reader to skip the block, which then costs
every *other* `warn` its audience. That is the exact failure the relay's own `info`-exclusion note
was written to prevent ("a channel that nags every session is one you learn to skip"), so this
release ships a mechanism whose stated rationale its own content partly violates. The exposure is
**bounded by time, not by design** — it ends when `BKL-8W2M` ships, which the owner intends within
days of release. If `BKL-8W2M` slips well past that, this acceptance should be re-taken rather than
assumed to still hold; nothing in the code will re-raise it.

**Not re-litigated:** the lift itself is settled by owner ruling 2026-07-24, and `BKL-7D3V` scopes
re-litigating it out. Only the amplified *delivery* was open, and only that is accepted here.


## VRF-015 — Chunk 06 (backlog-cache) — the restored readers produce findings, and say so when they cannot

**Status:** pending
**Added:** 2026-08-07 (backlog-cache Chunk 06 — supersedes VRF-008)

**Why a human check:** the deliverable is a *judgement* made by three prose readers. Tests pin that
the queries answer, that an unreadable store exits 6, and that the prose routes correctly — but no
test can confirm that a reviewer reading `review-cycle.md` actually runs the walk and emits findings
a person would act on. Skills are prose a model executes, and the failure this work exists to kill
(a reader that matches nothing while reporting confidently) is only visible end to end.

**Steps:**

1. On a cut-over repo, run `/prawduct:critic final` on a branch with real changes. The Backlog
   Reconciliation section must contain **per-item findings**, not an "unavailable" NOTE.
2. Confirm at least one finding names a real open item and that its id resolves.
3. Run `/prawduct:janitor`. The **Backlog Health** block must list area groupings and any stale or
   unstaged items — not a single unavailable line.
4. Confirm the janitor's Backlog Health ran without a permission prompt for
   `prawduct-hook backlog cache-query`.
5. Move the store aside (`<git-common-dir>/prawduct/backlog-cache.sqlite3`) and re-run both. Each
   must **say the cache is unreadable and name `prawduct-hook backlog sync`** — never report clean,
   and never report an empty result set.
6. Restore the store. Confirm the session briefing carries **no** dormancy advisory.
7. Confirm the freshness line appears in human-mode output: `prawduct-hook backlog cache-query
   unstaged --repo <scope>` (no `--json`) ends with a `cache:` line naming the age.

**Verified by:** _(operator, date)_
