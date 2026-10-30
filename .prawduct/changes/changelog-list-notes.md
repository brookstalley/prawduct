---
schema: 1
type: fix
scope: changelog-list-notes
date: 2026-10-30
title: A consumer note that opens with a list starts below its label in the paragraphs layout
---

The cut's `paragraphs` layout renders each consumer note as `**`scope`**: {note}`. Fragment notes
are usually bullet lists, so the first bullet landed on the label line as `**`scope`**: - item`.
Markdown then renders that item as plain text after the label, and only the remaining items as a
list. Four v3.7.2 entries shipped that way, and 16 of the 29 v3.8.0 notes would have.

`consumer_digest._entry_lines` now detects a note whose first line is a CommonMark list item. When
the template puts text before `{note}` on the same line, it ends that line at the label and starts
the note after a blank line. Notes that don't open a list are unchanged, and so is a template with
nothing before `{note}`. The bullet layouts are unchanged. The four published v3.7.2 entries in
`plugin/CHANGELOG.md` are repaired the same way.

## Consumer note
- With `consumer_digest: layout: paragraphs`, a consumer note that starts with a list item now
  renders as a list under its label, instead of putting the first item on the label line as text.
