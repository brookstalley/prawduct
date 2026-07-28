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
  subagents that each write `<role>.json`.
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

**Status:** pending (deferred — the live migration itself is not yet run)
**Added:** 2026-07-17 (backlog-service Chunk 06, offline deliverables landed; live
migration/repoint/retirement deferred to an owner-run session after design sign-off)
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
- `legacy.py` and the `incoming-bugs/` drop-box are retired only *after* the above.

**Drop-box retirement — verify the lockstep replacement (BKL-0QR1, resolved 2026-07-17 → option c):**
`incoming-bugs/` is retired **only together with** its minimal same-repo replacement (PRD §8.9/MG5),
never before it. Before/at the retirement, eyeball that the replacement is live:
- `/prawduct:report-bug`, on the reachable-channel path, files an `untriaged-upstream`-labeled
  **GitHub issue** into prawduct's own (public) repo via the adapter — no `incoming-bugs/` file write.
- The `untriaged-upstream-reports` advisory counts those **labeled open issues**, not `incoming-bugs/*.md`.
- The **no-channel fallback** still degrades cleanly to local capture + the canonical-tracker pointer.
- Only *then* are `legacy.py` and `incoming-bugs/` retired. The full XP1 cross-owner/foreign-identity
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

**Status:** pending
**Added:** 2026-07-19 (skills-cutover-awareness Chunk 01 — GV8 interim contract)

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
