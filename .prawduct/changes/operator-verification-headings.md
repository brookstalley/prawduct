---
schema: 1
type: fix
scope: operator-verification
date: 2026-11-15
title: A queue headed "## [VRF-001] title" is now read, and an unreadable queue is reported the same way everywhere
closes:
  - brookstalley/prawduct#811
  - brookstalley/prawduct#801
---
A queue whose entries were headed `## [VRF-001] title` (the id in brackets) was read as having no
entries at all. The gate, accept and verify each reacted differently: accept refused with advice that
contradicted itself, verify called the queue "empty", and a repo with the requirement off said nothing.

**Read both heading styles.** `## VRF-012 - title` and `## [VRF-012] title` are both entries now. The
operator's heading line is kept exactly as written, so draining an entry leaves their style alone. Only
a `VRF-` id opens an entry, so a `## Notes` section stays harmless.

**One refusal for an unreadable queue.** When a queue has content but no recognised entries (for
example `### VRF-1` headings), check, accept and verify all give the same message. It quotes the first
heading it could not read, lists the accepted shapes, and tells the agent what it can do: hand the
operator that line and stop, rather than reformat their record. The two competing instructions are gone.

**A repo with the requirement off is told.** `check-operator-verification` still exits 0 when
`operator_verification_required` is off, but it now prints a one-line note to stderr if the queue is
unreadable. With the requirement on, nothing changed (exit 3).

**Internal.** `mark_verified` and `mark_accepted` now return `{"status": "ok" | "refused", "reason": ...}`
instead of raising `ValueError`, matching the rest of the library. Nothing a user runs behaves differently.

## Consumer note
If your queue uses `## [VRF-NNN] title` headings it now works with no edits. If an unreadable queue was
ever reported as "empty", you will now see the real reason.
