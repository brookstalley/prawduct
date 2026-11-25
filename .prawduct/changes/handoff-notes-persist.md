---
schema: 1
type: fix
scope: handoff-notes-persist
date: 2026-11-25
title: "Handoff notes survive a session that wrote none (#1238)"
closes: [brookstalley/prawduct#1238]
---
Forward notes lasted one session boundary. The boundary copied `.prawduct/.handoff-notes.md` into
the handoff and deleted the file, and the next boundary rebuilt the handoff from scratch. So a
session that ended without writing notes (a crash, an exhausted context) erased the notes it was
handed, and they existed nowhere.

The generated handoff now fences the notes. When the session that is ending left no notes, or an
empty file, the generator carries the previous handoff's fenced notes forward under
`## Notes For The Next Session (inherited)`, says how many boundaries they have crossed unchanged,
and tells the reader to check them against the plan and git. Notes end only when a session writes
its own, including "nothing beyond the plan". The inherited text is never written back to
`.handoff-notes.md`, so the Stop hook's missing-note advisory and the clear-verdict check still ask
only about the current session. Inherited notes take the place of the "no forward note" section, so
the briefing points at the handoff as context rather than as a bare machine record.

A handoff written before this release has no fences, so its notes are not carried; the first
boundary after upgrading behaves as before.

## Consumer note
Notes in `.prawduct/.handoff-notes.md` now stay in the handoff, marked inherited, until a session writes its own, so a session that ends without writing them no longer loses them. To end notes deliberately, write "nothing beyond the plan".
