# DCP Mechanical Enforcement — Plan

Created: 2026-02-15

## Motivation

governance-stop.sh only enforces DCP retrospective completion (`directional_change.retrospective_completed`). Intermediate DCP steps (plan-stage Critic review, per-phase reviews, session observation) rely entirely on agent compliance. When the agent skips reading stage-6-iteration.md, all intermediate governance evaporates. This was proven during the standalone product repo support implementation.

## Design

Add 4 new fields to `directional_change` in `.session-governance.json`:
- `plan_stage_review_completed` (boolean) — Set true after plan-stage Critic review (DCP step 4)
- `total_phases` (integer) — Set when writing the plan (DCP step 3). Number of implementation phases.
- `phases_reviewed_count` (integer) — Incremented after each per-phase lightweight review (DCP step 7)
- `observation_captured` (boolean) — Set true after session observation (DCP step 10)

`governance-stop.sh` checks all four alongside the existing `retrospective_completed` check when `directional_change.active` is true:
- `plan_stage_review_completed` must be true
- `phases_reviewed_count` must be > 0 ONLY when `total_phases` > 1 (single-phase DCPs skip this — DCP step 7 says "for multi-phase changes")
- `observation_captured` must be true
- `retrospective_completed` must be true (existing check)

Each blocked field produces a specific message about which DCP step is missing.

## Files Modified (4)

| File | Change |
|------|--------|
| `.claude/hooks/governance-stop.sh` | Add 3 new checks in the DCP debt section |
| `skills/orchestrator/stage-6-iteration.md` | Add instructions to set each field at the right DCP step |
| `skills/orchestrator/SKILL.md` | Update `.session-governance.json` schema to include new fields |
| `project-state.yaml` | change_log entry |

## Phases

Single phase — all 4 files are tightly coupled and the change is small.

## Removed/Renamed Terms

None — this is purely additive.

## Backward Compatibility

- Existing `.session-governance.json` files without the new fields: governance-stop.sh should treat missing fields as "not applicable" (only check when `directional_change.active` is true AND the field exists). This handles sessions that started before this change.
- Framework repo: fully compatible — these fields are only checked when a DCP is active.
