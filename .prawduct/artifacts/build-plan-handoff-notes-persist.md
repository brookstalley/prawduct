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
      - "advice fails soft, but never silently → conforms: carrying notes forward cannot block a boundary; an unreadable or unfenced handoff carries nothing, and the handoff says when notes are inherited and how far"
      - "every fact has one home → conforms: the notes' text lives in the handoff, and the next boundary reads it from there; no second store or copy-back to `.handoff-notes.md`"
      - "observable beats stored → conforms: the carried count is read from the previous handoff's own fence, not from a separate record"
partition: serial — one chunk
---

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
  wrote. Inherited notes do suppress the handoff's "no forward note" section, whose heading would
  otherwise make the briefing call the handoff a bare machine record.
- Unbounded lifetime, with the count shown so the reader can judge drift, rather than an expiry
  that would recreate the loss on a schedule.
- A pre-fence handoff carries nothing: guessing where agent-written markdown ends could hand the next
  session text the notes never held. Costs one boundary at upgrade.

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
