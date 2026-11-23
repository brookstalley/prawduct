---
schema: 1
type: fix
scope: recorder-temp-session-file
date: 2026-11-23
title: prawduct's temp files are session files
closes: [brookstalley/prawduct#1202]
---
Prawduct writes a file atomically: through a temp sibling, then a rename into place. For an instant the
temp file exists untracked. A review's tree capture landing in that instant read it as a changed tree
and refused the review. A write that died before the rename left the temp file for the next
`git add -A`. #1202 reported this for `test-evidence record`. It held for every such writer: the shared
`core.atomic_write_text` (the findings cache, the session handoff, the advisory store, the review
marker and more), the backlog snapshot and migration checkpoint, plan status imports, learnings
compaction and the Stop hook's activity cache.

Every one of them now names its temp file with one suffix, `core.TEMP_SUFFIX` (`.prawduct.tmp`), through
`core.temp_sibling` or a `mkstemp` suffix. The session-file contract ignores `.prawduct/**/*.prawduct.tmp`,
and consolidation's tree check reads that glob the way gitignore does. So a temp file under `.prawduct/`
is never a changed tree or a commit candidate. The entry is anchored under `.prawduct/` rather than at
any depth, so a product whose `.gitignore` holds a wholesale `.prawduct/` rule already satisfies it and
is not asked for a line. The one writer outside `.prawduct/` is learnings compaction. It is an attended
operation whose leftover git shows, and it is left outside on purpose. The two modules that cannot
import `lib`, the hook and `lib/host.py`, spell the suffix. `tests/test_temp_suffix.py` fails on any
temp-name literal under `plugin/` that ends in a bare `.tmp`. The entry's boundary disposition is to
survive: the next write overwrites a leftover, and unlinking one at a boundary could race another
session's writer between its write and its rename.

## Consumer note
The managed `.gitignore` section gains `.prawduct/**/*.prawduct.tmp`. A product that lists session files
one by one sees the gitignore-contract-drift advisory count one more missing entry until the owner says
go to reconcile it. A product with a wholesale `.prawduct/` rule sees nothing. A leftover temp file from
an older version keeps its old `.tmp` name, which stays visible to git; it is safe to delete.
