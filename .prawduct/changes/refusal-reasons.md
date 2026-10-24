---
schema: 1
type: feature
scope: refusal-reasons
date: 2026-10-24
title: a control firing records why it fired, and stats tells a catch from a slip
---
The evidence store counted control firings but not their causes. Nobody could tell whether a block by
`clear-verdict` or `clear-reason` (5 of 8 Stop blocks on plugin 3.7) caught a real problem or only a
formatting slip. That was the first step #1044 asked for. The fix is shaped for any control, blocking
or not, because the sink every control firing goes through now takes two optional, validated fields:

- `reason`: which check failed, a slug from a closed set.
- `observed`: a flat map of machine facts seen at firing time.

A value that isn't machine-shaped is dropped and named, and the firing still counts. Producers pass
declared constants and observations, never the turn's words.

Two Stop gates are the first to record them:
- `clear-verdict` records which disposition it paired with `DO NOT CLEAR`.
- `clear-reason` records the self-citation's form, never its words.

Both observe whether work was live (harness background tasks or a live Critic review) and whether
handoff notes were on disk.

`prawduct-hook stats` (report schema 2) counts Stop blocks and guard refusals by reason. For the two
clear gates it also derives a catch / slip / unclassified verdict at read time from those observations.
The rule lives in the reader, so revising it re-reads every recorded firing. Definitions:
`docs/governance-telemetry.md`. #1044 stays open for its quarter of data and the keep, narrow or
retire decision.

## Consumer note
- `prawduct-hook stats` prints a `stop reasons` line per clear gate, and `--json` is
  `schema_version` 2. It adds `stop_blocks.by_gate_reason`, `stop_blocks.verdicts` and
  `guard_refusals.by_guard_reason`. No key was removed.
