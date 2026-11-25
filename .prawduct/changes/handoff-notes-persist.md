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

The generated handoff now fences the notes. When the session that is ending delivered no notes (no
file, an empty one, or one that cannot be read), the generator carries the previous handoff's fenced
notes forward under `## Notes For The Next Session (inherited)`, says what the ending session left
and how many boundaries the notes have crossed unchanged, and tells the reader to check them
against the plan and git. Notes end only when a session writes its own, including "nothing beyond
the plan", and the digest says a write replaces them, so the writer carries forward what still
applies. Fence-shaped lines inside embedded notes are made inert, and only the notes section that
opens the handoff is read, so notes that quote a fence, or a reflection that does, cannot cut notes
short or invent them. The inherited text is never written back to `.handoff-notes.md`, so the Stop
hook's missing-note advisory and the clear-verdict check still ask only about the current session.
The "no forward note" section still appears beside inherited notes, and the briefing's pointer
names both.

A handoff written before this release has no fences, so its notes are not carried; the next
handoff says so under `## Earlier Notes Not Carried`.

## Consumer note
Notes in `.prawduct/.handoff-notes.md` now stay in the handoff, marked inherited, until a session writes its own, so a session that ends without writing them no longer loses them. To end notes deliberately, write "nothing beyond the plan".
