---
schema: 1
type: fix
scope: closes-cache-miss
date: 2026-11-18
title: a closes id the local backlog cache lacks reads unchecked, and a rebuild no longer strands another repo's cache
closes: [brookstalley/prawduct#1195]
---
`check-pr-hygiene` reported `closes-unresolved` for any id missing from the local backlog cache,
so an open issue the cache had lost read like a bad id. It now reports `closes-unresolved` only for a
spelling no backlog could resolve. A well-formed id the cache lacks, whether an issue id or a `PFX`
alias, reads `unchecked`. That line names `prawduct-hook backlog sync --rebuild --repo <scope>` and
`backlog get`. An id on another repo also reads `unchecked`, naming `backlog get` for that id, since
the single-repo cache never holds it. The check stays offline.

How the cache went partial: the store is shared by the whole clone and holds one repo. A rebuild
deleted every item but rewrote only its own scope's watermark. Another scope's watermark survived
over items that were gone, and that scope's next incremental sync fetched only issues changed since.
Everything older stayed missing. Local clones whose `backlog_service_repo` had moved showed this:
cursor rows for the old scopes, with zero items behind them. A rebuild now drops every other scope's
watermark in the same transaction. An incremental sync that finds a second watermark, left by an
earlier plugin, rebuilds once and says why.

## Consumer note
A clone whose backlog cache holds watermarks for more than one repo rebuilds its cache on the next
sync, once. No action needed.
