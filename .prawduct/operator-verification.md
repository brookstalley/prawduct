# Operator Verification Queue

<!-- Append-only queue of human-verification items for visual / live-integration
     changes automated tests can't fully cover. Each entry is a level-2 heading:
     `## VRF-<id> — <Chunk N> — <title>`; first body line is
     `**Status:** pending | verified | accepted`. When
     `operator_verification_required: true`, `/pr create` BLOCKS on any pending
     entry (currently false here, so this is a tracked reminder, not a gate).
     Append-only history — don't delete drained entries. -->

## VRF-001 — Chunk 01 — Worktree resolution against the live harness

**Status:** pending
**Added:** 2026-06-20 (worktree-compat Chunk 01, STH-4K7N)
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

**Status:** pending
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
