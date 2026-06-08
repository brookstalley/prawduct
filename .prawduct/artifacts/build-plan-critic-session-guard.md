---
artifact: build-plan
version: 2
# Namespaces this plan's chunk numbering so a shipped `chunks=1…` entry from
# another scope (e.g. work-model v2.0.13) can't flip our Chunk 1 (the cross-scope
# collision the template warns about). Matches the change-log entry's `scope=`.
scope: critic-session-guard
depends_on: []
last_validated: null
---

## Requirements Confidence

**Level:** High

**Why:** The problem is observed and root-caused (CRT-3X9D), success is statable in
one sentence, and scope is bounded to one runtime concern with a known fix shape the
user explicitly chose (Path A, crash-resilient, waiver-style override).

**Open assumptions / unknowns:**
- `[ASSUMPTION: 30-minute marker TTL is the right freshness window | LOW impact | user can correct]` — Critic reviews target 4–10 min (final/cumulative); 30 min protects a slow review while a crashed marker frees within the window. Tunable in one constant.
- `[ASSUMPTION: a stale/corrupt marker should fail toward availability (sweep + proceed), not toward protection (block) | MED impact | user already endorsed "resilient to crashes, doesn't have to be perfect"]` — a corrupt marker offers no protection but never bricks `clear`; the override exists regardless.
- `[ASSUMPTION: routing the SessionStart hook to `clear --session-start` is safe | LOW impact | user can correct]` — old-lib/new-hook and new-lib/old-hook both degrade gracefully (the flag is ignored by old `cmd_clear`; bare `clear` with no marker behaves as today).

**What would raise confidence:** N/A (High).

## Problem / Success / Scope

- **Problem:** The Critic is documented as structurally unable to run executables, but a
  coordinator subagent (spawned via the `Agent` tool, which does **not** inherit the
  Critic skill's restricted `allowed-tools`) ran `pytest` and `prawduct-hook clear` during
  the STH-9V4K ch.7 review. `clear` is destructive: it archived/deleted `.session-reflected`,
  rewrote `.session-start` (making fresh test evidence read "stale"), and recaptured the git
  baseline — an independent reviewer clobbered the very session it was reviewing.
- **Success:** A bare `prawduct-hook clear` issued while a Critic review is plausibly in
  progress **refuses** (non-zero, no mutation) and prints an actionable override. The
  legitimate SessionStart reset always proceeds. The block is crash-resilient — a crashed or
  hung Critic does not permanently brick `clear` (TTL auto-expiry + session-start sweep +
  explicit override).
- **Out of scope:** Path B (a dedicated restricted reviewer-agent type for the coordinator
  subagents — deferred as defense-in-depth). Guarding `stop` (verified read-only — no session
  mutation). Stopping the Critic from running `pytest` per se (the harm chain ran through
  `clear`; protecting `clear` neutralizes the stale-evidence symptom). The builder's own
  `prawduct-hook clear` smoke-test habit (pre-existing, separate concern).

## Status

- [x] Chunk 1: Critic-active session guard (`.critic-active` marker + `clear` guard + `critic-begin`/`critic-end`)

**Context:** Branch `fix/critic-session-guard-CRT-3X9D` off `develop`. Single-chunk plan.
Baseline green (947 passed) before work. `active_build_plan` repointed here from the
release-pending hook-decomposition plan (its release obligation stays tracked in backlog
STH-9V4K + its unflipped checkboxes). No PR unless the user asks.

---

### Chunk 1: Critic-active session guard

- **Type:** code
- **Critic mode:** final
  <!-- Override: single-chunk plan that touches framework instruction files
       (skills/critic/SKILL.md, CLAUDE.md) — needs Goals 4-7 + Framework-Specific
       Checks 7-10 (coherence between the docs' "cannot mutate" claim and the new
       enforcement), which `chunk` mode skips. -->

- **Design — the resilient marker (waiver model):**
  - The Critic writes a new `.prawduct/.critic-active` (JSON: `started_at` UTC, `pid`, `tool`) at
    the start of its run via a new `prawduct-hook critic-begin`, and removes it at the end via
    `prawduct-hook critic-end`. Both are added to the Critic skill's `allowed-tools`.
  - Session-mutating `clear` consults the marker. "Active" = marker present AND age ≤ TTL
    (`CRITIC_ACTIVE_TTL_SECONDS = 1800`). Age = `now − started_at` if parseable, else file
    mtime; if neither is readable → treated as **stale** (fail toward availability).
  - **Three independent ways a stale marker self-corrects** (resilience, per user):
    1. **TTL auto-expiry** — a crashed/hung Critic's marker stops counting as active after 30 min.
    2. **Session-start sweep** — the next real session start (`clear --session-start`) deletes any marker.
    3. **Explicit override** — the refusal message tells the agent/user exactly how to correct it
       (`rm .prawduct/.critic-active`, or `prawduct-hook clear --force`).
  - The SessionStart hook is rerouted to `clear --session-start` (always proceeds + sweeps).
    A bare `clear` (what the reviewer subagent ran) is the guarded path.
  - Guard placement: at the **top** of `cmd_clear`, before any mutation. On a lib import
    failure the guard **fails open** (proceeds) — session start must never be blocked by an
    incomplete install (consistent with cmd_clear's existing degrade-on-broad-catch pattern;
    and a broken lib means the Critic can't run either, so there's no review to protect).

- **Deliverables (surfaces enumerated — ~8):**
  1. new `lib/critic_marker.py` — `write_marker`, `clear_marker`, `review_active(prawduct_dir) -> (bool, age|None)`, `CRITIC_ACTIVE_TTL_SECONDS`. Pure stdlib (json/datetime/pathlib).
  2. `bin/prawduct-hook` — `_critic_marker()` lazy accessor (mirrors `_briefing()`); `cmd_clear(project_dir, argv)` parses `--session-start`/`--force` + the guard; new `cmd_critic_begin`/`cmd_critic_end`; dispatch entries; `_USAGE` updated; `.critic-active` added to `_SESSION_GITIGNORED_PATHS`.
  3. `lib/core.py` — `.critic-active` added to `GITIGNORE_ENTRIES` (keeps the `TestSessionGitignoreMirror` parity green).
  4. `.gitignore` (repo) — add `.critic-active`.
  5. `hooks/hooks.json` — SessionStart `clear` → `clear --session-start`.
  6. `skills/critic/SKILL.md` — `allowed-tools` += `Bash(prawduct-hook critic-begin)`, `Bash(prawduct-hook critic-end)`; add a `critic-begin` step (after mode resolve) and a `critic-end` step (after writing findings); update the Structural-Constraints prose + the header comment to describe the real backstop.
  7. `CLAUDE.md` — coherent one-clause update to the Critic paragraph: the session-mutating path is now independently guarded so a reviewer can't clobber the session even if a tool restriction leaks (CRT-3X9D).
  8. tests — see Done-when.

- **Done when:**
  1. **Tests** (new `tests/test_critic_session_guard.py` + updates to `tests/test_plugin_runtime.py`):
     - bare `clear` + **fresh** marker → exit ≠ 0; `.session-reflected` preserved (NOT archived/deleted), `.session-start` unchanged, marker NOT removed; stderr names the override (`rm`, `--force`, CRT-3X9D).
     - `clear --session-start` + marker → exit 0; marker swept; `.session-start`/baseline written; briefing rendered (regression of existing clear behavior).
     - `clear --force` + fresh marker → exit 0; proceeds.
     - bare `clear` + **stale** marker (started_at older than TTL) → exit 0; marker swept; normal reset.
     - bare `clear` + **no** marker → exit 0 (unchanged behavior — regression guard).
     - `critic-begin` writes a parseable marker with a timestamp; `critic-end` removes it; `critic-end` is idempotent (no-op + exit 0 when absent).
     - updated `test_hooks_json_wires_briefing_and_gate` + `test_clear_matcher_excludes_compact` accept `clear --session-start`.
     - `run_plugin_hook` extended to pass extra argv.
  2. Full suite green; `.prawduct/.test-evidence.json` written.
  3. `/prawduct:critic final` run; blocking findings resolved.
  4. CRT-3X9D reconciled in `.prawduct/backlog.md`; tagged change-log entry added.
  5. Reflection appended to `.session-reflected`.
  6. Committed; chunk marked `[x]` in Status.
