---
schema: 1
type: fix
scope: backlog-service
date: 2026-11-15
title: the backlog cache drops a deleted issue, `related` links are written on both items, and two silent decode losses now warn
closes: [brookstalley/prawduct#1080, brookstalley/prawduct#835]
---
Three backlog-service bugs where the answer looked right and was not.

**A deleted issue stayed open in the cache (#1080).** GitHub answers a hard-deleted issue with
410 Gone. The transport only recognised 404, so a 410 was treated as a retryable outage, and the
deleted issue stayed in the local cache as an open item, showing up in `pick`, `find` and dedup.
A 410 is now a terminal `not_found` (exit 3, not retryable, with `details.http_status: 410`), and
`get` removes that one item from the cache. A plain 404 still does not evict, because it also
means "no access". If the cache cannot be updated, `get` says so in a warning and still reports
`not_found`. `sync` is unchanged and still never sweeps for deletions: a deleted issue nobody
`get`s stays until `sync --rebuild`. The cache spec records this.

**`link --edge related` wrote one item only (#835).** `related` has no native GitHub edge, so it
is a line in each item's body block, and `link` and `unlink` only touched the first item. The edge
was visible from the source and invisible from the target. Both items are now written, each side
idempotent on its own and each mirrored into the cache. If the second write fails after the first
landed, the call never goes quiet. A retryable failure returns an error with `details.partial: true`
(`written`, `unwritten`), and running the same command again completes only the missing side. A
permanent failure on the target, typically a cross-repo item this identity cannot write, returns
ok with `target_written: false` and a warning, so links to upstream issues keep working. The first
write is never rolled back. Edges already written one-sided are not repaired by this change:
re-running `link` on each pair fills in the target.

**Two decode losses now warn (#745, partly).** An open item with no `stage:` label, and an item
whose `prawduct:` block is gone, used to decode silently into plain defaults. Both now carry a
warning on `get` and the other reads. The returned values do not change, and `file` does not warn
about what the filer just chose. The third leg, a soft facet (`area`, `impact`, ...) deleted in
the GitHub UI, is not built: telling "deleted" from "never set" needs a record of the old value,
and where that record comes from is an open question on the issue. #745 stays open.

## Consumer note
`backlog get` of a deleted issue now exits 3 (`not_found`) instead of 6, and clears it from the
local cache. `link`/`unlink --edge related` now write both items; a half-written link shows
`details.partial` in the error and is finished by repeating the command. Reads of an open item
with no stage, or one whose `prawduct:` block was removed, carry a new warning. Run `backlog
unlink`/`link` again on old one-sided `related` pairs to complete them.
