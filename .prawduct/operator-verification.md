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
