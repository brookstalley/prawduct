---
schema: 1
type: fix
scope: import-status-remove-block
date: 2026-11-11
title: plan import-status --remove-block refuses a Status section that holds subsections
closes: [brookstalley/prawduct#1137]
---
`plan import-status --remove-block` deletes the plan's `## Status` section, whose extent is the
reader's: `plan_index.status_section_bounds` runs it to the next `## ` heading and deliberately
past any `###` heading, so a plan that keeps its chunk definitions under `## Status` still reads.
Reused by the writer, that extent took every one of those definitions with the checkbox list, open
chunks included, and the command reported success. #1137 reported it from a repo where three plans
lost far more than their lists.

`_status_block_span` in `plugin/bin/prawduct-hook` now refuses, as `status-block-undelimited`,
when a heading of any level sits inside the span outside a comment, naming the line. It is the
existing rule for this writer applied to a case it had missed — a writer claims nothing it cannot
delimit — and it reuses the existing refusal code, so the contract's list of refusals and the
doctor skill's account of them stand as written. Like every other block refusal it comes before
any fact is written. A `#` that opens no heading (`#12`, `#later`) is block text and does not
refuse.

`tests/test_plan_import_status.py` carries the report's own shape and an H1 variant in the
refusal table, a test that the refusal names its line and leaves the open chunk's definition in
place, and a control that a non-heading `#` still lets the removal through.

## Consumer note
`prawduct-hook plan import-status <plan> --apply --remove-block` no longer deletes chunk
definitions kept as `###` subsections under `## Status`. It now stops with
`refused: status-block-undelimited`, names the line of the first heading inside the section, and
writes nothing. To remove the block, add a `## ` heading between the checkbox list and the
subsections (for example `## Build Chunks`) and run it again, or delete the list by hand. If an
earlier run of this command already removed chunk definitions from a plan, they are in that
plan's git history.
