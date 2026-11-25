---
artifact: build-plan
version: 2
scope: handoff-notes-persist
branch: fix/handoff-notes-persist
base: develop
working-branches: []
last_validated: 2026-11-25
depends_on:
  - artifact: architecture
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → inapplicable because this changes the boundary's handoff generator, which no reviewer runs"
      - "authority fails closed; advice fails soft → conforms: the handoff is advice; carrying notes cannot block a boundary, and notes it cannot delimit are named in the next handoff rather than dropped silently"
      - "local-first: process-spawn, atomic files, the git object database → conforms: reads and writes only `.prawduct/` files, through the existing atomic handoff write"
      - "the plugin writes nothing into a governed repo but its own state → conforms: the only file written is `.prawduct/.session-handoff.md`, already the generator's"
      - "never specific to Python → inapplicable because the handoff is markdown about a session, with no reading of the product's code"
      - "prawduct guides and reviews; it never implements → inapplicable because this is framework code"
      - "goals and verification bind; prescribed method is advice → conforms: the chunk's routes are forecasts; the report's repro and the acceptance criteria bind"
      - "every fact has one home → conforms: the notes' text lives in the handoff, and the next boundary reads it there; no second store and no copy-back to `.handoff-notes.md`, and the carried count is read from the previous handoff's own fence"
partition: serial — one chunk
lifecycle: completed
archived: 2026-11-25
released_in: v3.10.0
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

## Goals

**Response taken:** Proceed, citing #1238. The owner ruled on 2026-11-25 that it ships in the next
release (`.prawduct/owner-rulings.md`). The report defines success: notes written by session A reach
session C when session B ends without writing any.

**Product:** Forward notes survive only one session boundary, so a session that crashes or runs out
of context before writing notes erases the notes it was handed.

**Architecture:** The generated handoff fences the notes. When the ending session left no notes (or
an empty file), `render_session_handoff` carries the previous handoff's fenced notes forward under an
inherited heading, with a count of boundaries crossed. Nothing is restored to `.handoff-notes.md`.

**Decisions made (inferred, mine, open for the owner at the boundary review):** the two questions
the triage comment left open, answered as it leaned.
- *What ends an inherited note:* only a session-written, non-empty notes file, the documented
  "nothing beyond the plan" stub included. An empty file does not, since it is what truncation leaves,
  not a statement.
- *Freshness surfaces:* inherited notes are never written back to the notes file, so the Stop hook's
  missing-note advisory and the clear-verdict check (`notes_present`) still see only what this session
  wrote. The handoff's "no forward note" section still fires beside inherited notes (reversed at the
  boundary review: suppressing it hid the signal for good once any notes existed), and the briefing's
  pointer names both instead of calling the handoff a bare machine record.
- Unbounded lifetime, with the count shown so the reader can judge drift, rather than an expiry
  that would recreate the loss on a schedule.
- A pre-fence handoff carries nothing: guessing where agent-written markdown ends could hand the next
  session text the notes never held. Costs one boundary at upgrade, and the next handoff says so.

**Decisions made mid-build:**
- Boundary review (rev-20261125T223801Z-2275f4a8): the reader trusted that it owned the only fence
  lines and gave one empty answer for every "nothing carried" cause, so notes that quoted a fence
  (the natural case: copying the inherited block to keep it), text quoted later in the handoff, an
  undecodable handoff or an unreadable notes file each lost notes silently. Now the renderer defangs
  fence lines in the notes it embeds, the reader reads only the opening notes section and decodes
  lossily, an unreadable notes file inherits too, a drop it cannot avoid is named, the first sentence
  follows what the ending session left, and the "no forward note" section is no longer suppressed by
  inherited notes (the pointer names both instead). The digest and `session-hygiene.md` say that a
  write replaces inherited notes, so the writer carries forward what still applies.

## Build Chunks

### Chunk 01: Notes persist until a session replaces them

- **Description:** The handoff fences its notes, and a boundary whose session wrote none carries the
  previous handoff's notes forward, marked inherited.
- **Depends on:** none
- **Deliverables:** `plugin/lib/briefing.py` (fences, `_read_inherited_notes`, the inherited
  section, the no-forward-note suppression); `tests/test_handoff_channel.py`;
  `plugin/methodology/session-hygiene.md` (the lifetime rule) and its reading in
  `tests/test_v5_methodology.py`; `.prawduct/artifacts/architecture.md` (the handoff pair's contract)
- **Tests:** through the real `clear` hook — A writes, B writes nothing, C sees A's notes; the count
  grows per boundary; a written note (the stub) replaces them; an empty file does not. Unit — the
  no-forward-note section yields to inherited notes, with a control; notes carrying their own `##`
  headings are carried whole; unfenced, hand-authored and ambiguous handoffs carry nothing.
- **Acceptance criteria:** the report's repro passes; nothing restores the notes file
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
