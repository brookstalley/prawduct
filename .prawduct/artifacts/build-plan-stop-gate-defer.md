<!-- Build Plan — defer session-end gates while harness-tracked background work is in flight (STH-3W7F). -->
---
artifact: build-plan
version: 2
scope: stop-gate-defer
depends_on: []
last_validated: null
---

## Requirements Confidence

**Level:** High

**Why:** The problem, fix, and scope are each statable in one sentence, and the
load-bearing fact has been verified against ground truth rather than recalled.
**Problem:** a coordinating agent that launches a background `Workflow`/`Task` and
yields trips the Stop-hook Critic/reflection gate every turn (files changed, no
Critic yet) — but the diff isn't final and the session *can't* end (the harness
re-wakes it), so each block is pure noise; one reported session absorbed ~15
block-loops over a ~12-min lane (STH-3W7F). **Fix:** the Stop hook reads the
`background_tasks` array Claude Code now puts on its stdin (v2.1.145+; verified —
installed client is 2.1.191) and, when harness-tracked work is in flight, defers
the session-end blockers to the next Stop instead of blocking. **Scope:** the
deferral never *skips* a gate — the gate is stateless and re-arms the instant
`background_tasks` empties, so the Critic/reflection still fire when the work
lands. This is the auto-detect fix (STH-3W7F option a), now viable because the
harness exposes the signal — superseding the half-designed self-declared
`.gates-deferred` marker (option b), which the 2026-06-04 investigation reached
for *only because* the hook could not then see live jobs.

**Why this is "fix the classification," not "demote blocking→warning":** the
in-flight block is a genuine false positive — there is nothing to Critic yet and
the session cannot end. The gate is taught that *files-changed + tracked work in
flight* is a distinct state from *work-done + Critic-skipped*; it does not fire
the blocker in that state, and still blocks normally the moment the work lands.
Nothing is demoted to an ignorable warning (honors the standing
`warnings-are-effectively-blocking` feedback).

**Open assumptions / unknowns:**
- `[ASSUMPTION: any non-empty background_tasks defers (no filtering by task type) | LOW impact | user can veto]` — over-deferral is cheap: the deferral re-arms every turn, and a session with a live background task is "paused waiting" anyway, so blocking it buys nothing. A type filter (defer only on diff-producing types) is a later refinement if a real perpetual-task false-defer is observed.
- `[ASSUMPTION: field ABSENT (older client / registry unreachable / no stdin) must behave exactly as today — block | HIGH impact | user can correct]` — the safe default on an unknown signal is the current gate behavior, never silent suppression. Only a clearly-present non-empty list defers.
- `[ASSUMPTION: untrackable external waits (a CI run, a remote queue, a manual gh poll) are OUT of scope | MED impact | user can veto to widen]` — those leave background_tasks empty, so the gate still blocks. The TTL-waiver escape hatch for them (STH-3W7F option d) is deferred as a separate, lower-priority item; building it now reintroduces the drift surface the report itself rates inferior.

**What would raise confidence:** N/A (High).

## Status

- [ ] Chunk 01: Defer session-end gates while harness-tracked background work is in flight

## Build Chunks

### Chunk 01: Defer session-end gates while harness-tracked background work is in flight

- **Description:** Teach the Stop hook to read its stdin payload and detect
  in-flight harness-tracked background work via the `background_tasks` array
  (Claude Code v2.1.145+). When such work is in flight AND the session-end gates
  would otherwise block, defer the block (return 0 with a concise stderr note
  naming the in-flight tasks) instead of returning exit 2. The deferral is
  stateless — recomputed from the live array on every Stop fire — so it re-arms
  automatically: the very next Stop after `background_tasks` empties enforces the
  Critic/reflection gate normally. A degradation ladder keeps the gate sound:
  field **absent** (old client / registry unreachable / no stdin / malformed) →
  do **not** defer (block exactly as today); field present & **empty** (idle) →
  do **not** defer (block as today); field present & **non-empty** → defer. The
  permissive direction (suppressing the block) is taken only on a clearly-present
  non-empty list; every uncertain case falls to the blocking default.
- **Deliverables:**
  - `lib/gates.py`:
    - new pure helper `background_tasks_in_flight(stop_input) -> tuple[bool, list[str]]`
      — implements the degradation ladder above and returns `(in_flight, labels)`
      where each label summarizes a task (`<type>:<name|id>`) for the deferral
      note. Fail-closed to `(False, [])` on any non-dict / non-list / malformed
      shape (uncertainty → do not defer → gate still blocks).
  - `bin/prawduct-hook`:
    - new `_read_stop_stdin() -> dict` — parses the Stop-hook JSON from stdin,
      fail-soft: interactive TTY, empty stdin, or malformed JSON → `{}` (so the
      gate degrades to its no-signal behavior). Never raises. Mirrors the existing
      stdin read in `cmd_user_prompt_submit`.
    - `cmd_stop` gains an optional `stop_input: dict | None = None` parameter
      (default `None` → `{}`, keeping direct callers/tests working). Early, it
      computes `defer_active, in_flight = _gates().background_tasks_in_flight(stop_input)`.
      The PR-gate network probe (`gh pr list`) is guarded with `and not defer_active`
      so a deferred Stop skips the network call. After blockers are collected, if
      `defer_active and blockers`, print a `GATES DEFERRED` note (lists in-flight
      tasks + that the gate will fire on the next Stop, not skipped) and `return 0`;
      otherwise the existing `return 2`/`return 0` logic stands unchanged.
    - the `stop` dispatch (`main`) passes the parsed stdin:
      `return cmd_stop(project_dir, _read_stop_stdin())`.
  - `methodology/building.md`: update the **In-flight background work** paragraph
    (currently says detection is "pending") to describe the shipped auto-detect
    behavior and that the agent need do nothing.
  - `tests/test_plugin_runtime.py`: extend `run_plugin_hook` with a `stdin: str = ""`
    parameter passed as `input=stdin` to `subprocess.run` (existing callers get
    `""` → empty stdin → block-as-today, no behavior change), and add deferral
    end-to-end cases.
  - new `tests/test_stop_gate_defer.py` (or extend an existing gate test module):
    unit tests for `background_tasks_in_flight` covering the full ladder.
- **Tests:**
  - Unit (`background_tasks_in_flight`): absent key → `(False, [])`; empty list →
    `(False, [])`; non-empty (workflow/subagent) → `(True, [labels])`; malformed
    (non-dict input, non-list value, list of non-dicts) → `(False, [])`.
  - End-to-end (`run_plugin_hook stop` with mock git + active plan + code diff +
    no findings):
    1. `background_tasks` non-empty → **exit 0**, stderr contains the deferral
       note (NOT a CRITIC block).
    2. `background_tasks` empty → **exit 2**, CRITIC block (blocks as today).
    3. stdin absent/empty → **exit 2**, CRITIC block (no regression).
    4. malformed stdin → **exit 2** (fail-soft to block).
    5. **Re-arm:** a deferred call (non-empty → exit 0) followed by an idle call
       (empty → exit 2) on the same fixture proves the gate re-arms (not a
       one-shot waiver, not a persisted skip).
  - Full suite green.
- **Acceptance criteria:** With an active build plan, a code diff, and no Critic
  findings: a Stop whose stdin carries a non-empty `background_tasks` returns 0
  with a deferral note; the same fixture with an empty array (or no stdin, or
  malformed stdin) returns 2 with the CRITIC block; and a deferred-then-idle
  sequence blocks on the idle call (re-arm). No existing stop-gate test changes
  behavior. Suite green.
- **Critic mode:** final
- **Type:** code
- **Done when:** 1. Acceptance + tests pass · 2. `/prawduct:critic final` blocking resolved · 3. committed + `[x]` (change-log entry + regen-views, views_enabled) · 4. `/prawduct:critic cumulative` (the `/prawduct:pr` gate) when PR'd.
