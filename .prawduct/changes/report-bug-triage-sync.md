---
schema: 1
type: fix
scope: report-bug-triage-sync
date: 2026-11-24
title: report-bug triage refreshes the backlog cache before listing the intake set
closes: []
---
The receiving-side triage steps in `/prawduct:report-bug` listed waiting reports with
`backlog cache-query unstaged`, which reads only the local cache. A report filed after the last
sync was missing from the list, and the empty result looked like an empty intake. The steps now
run `backlog sync` first.

## Consumer note
none: receiving-side triage runs only in prawduct's own repo; consumer repos never run these steps.
