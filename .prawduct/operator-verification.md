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
