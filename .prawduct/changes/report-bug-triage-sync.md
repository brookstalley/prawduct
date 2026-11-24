---
schema: 1
type: fix
scope: report-bug-triage-sync
date: 2026-11-24
title: upstream-report triage refreshes the backlog cache first, and the intake advisory routes to it
closes: []
---
The receiving-side triage steps in `/prawduct:report-bug` listed waiting reports with
`backlog cache-query unstaged`, which reads only the local cache. A report filed after the last
sync was missing from the list, and the empty result looked like an empty intake. The steps now
run `backlog sync` first. If the sync fails, or the listing carries `sync_error` or exits 6, the
steps say the list is a floor ("at least N") and never report the intake as empty.

The `untriaged-upstream-reports` advisory recommended `/prawduct:backlog`, which has no route for
upstream triage, so an agent following it never reached those steps. All four shapes of the
advisory (a count, a stalled count, a stalled zero, an unreadable cache) now recommend
`/prawduct:report-bug`.

## Consumer note
none: the advisory fires and the triage steps run only in prawduct's own repo, the pinned upstream target.
