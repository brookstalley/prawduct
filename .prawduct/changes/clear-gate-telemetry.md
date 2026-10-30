---
schema: 1
type: fix
scope: clear-gate-telemetry
date: 2026-10-29
title: Clear gates count only real catches, and YOUR TURN may hold a live clear
---

The 3.8.0-dev field survey (2026-10-29) found two problems with the clear gates. #1044 relies on
these gates' data to decide whether to keep, narrow or retire them.

**The catch count was inflated.** `stats` counted a `clear-reason` firing as a catch whenever no
handoff notes were on disk. Ten of the eleven 3.8 firings came from one repo, and the transcripts
show question or diagnosis turns ("why is X down") in sessions that changed nothing. That
observation can't tell a read-once answer from a lost decision, so the data leaned towards keeping
the gate.

Clear-gate firings now record `session_changed`: did the session author a non-metadata change,
committed or not (`gates.session_work_span`)? A `clear-reason` firing now counts as a catch only
when notes were absent and the session changed something. A read-only session's firing is
unclassified, and so is any firing recorded before the key existed, because neither can say what a
clear would lose. The gate's behaviour is unchanged.

**`clear-verdict` refused a hold that was true.** Of the ten 3.8 firings with observations, seven
were `YOUR TURN` + `DO NOT CLEAR` while harness background work or a live Critic review was
running. Each cost a round trip that only relabelled the turn as `RUNNING`. The owner ruled to
narrow the gate now rather than wait for #1044's quarter of data.

The Stop hook now lets that pair stand when it observes the work. Only an observed True passes. A
`COMPLETE` + `DO NOT CLEAR`, a `YOUR TURN` with nothing observed (the server-or-recorder case behind
#932), and work the hook can't see (an unread delegate's finished output) still block. The digest
and `session-hygiene.md` state the amended rule: only work a clear would kill earns
`DO NOT CLEAR`, `COMPLETE` never carries it, and `YOUR TURN` carries it only beside that work, named
in the copy.

## Consumer note
- `YOUR TURN` + `DO NOT CLEAR` is no longer refused while a background task or a live Critic review
  is running. Name the work in the copy. With nothing running, the pair is still refused.
- `prawduct-hook stats` may report fewer `clear-reason` catches than before. Firings from sessions
  that changed nothing, and firings recorded before this release, are now unclassified.
