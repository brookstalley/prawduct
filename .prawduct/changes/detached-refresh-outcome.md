---
schema: 1
type: fix
scope: detached-refresh-outcome
date: 2026-11-18
title: a failing background counts refresh leaves a record, and the briefing says stuck instead of warming
closes: [brookstalley/prawduct#755]
---
The session-start counts refresh runs detached with its stderr discarded. When it failed, it wrote
nothing, so a refresh that had failed for a week looked exactly like one just started. The briefing
printed `counts warming` at every session start. `refresh-counts` now records each attempt in the
counts snapshot: `last_attempt_at` and `last_error`. A failure records them whether it came back as
an error or was raised, and a success clears the error. The last good counts are never overwritten.
This mirrors the cache sync's attempt record (#625).

The briefing reads that record. With no counts and a recorded failure, it says `counts stuck` and
gives the error and the command to run. With counts and a failing refresh, it adds `refresh failing`
to the pending line. That includes a zero-pending snapshot, which used to print nothing. A test lists
every detached warm (`transport.spawn_detached` caller) against the test proving it records a
failure, so adding a new one without an outcome record fails the suite.

## Consumer note
none: the new snapshot fields are additive, and a snapshot written before them reads as it did
