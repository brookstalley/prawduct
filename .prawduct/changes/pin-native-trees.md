---
schema: 1
type: fix
scope: pin-native-trees
date: 2026-11-14
title: a paired native run's reviewed trees are pinned, so git gc cannot prune them before verification
closes: [brookstalley/prawduct#1174]
---
A paired native run records the base and head trees its review read, and the #1130 blind sheet
tells the verifier to read the code there. A dirty working tree's tree is written through a
temporary index, so nothing references it, and `git gc` prunes an unreferenced object after
`gc.pruneExpire` (two weeks by default). The experiment runs at least four weeks, so the trees
could be gone by its stop-time verification.

`native-review record` now pins both trees under `refs/prawduct/native-trees/<review-id>/`,
including on a re-run for a review it already recorded. A pin that fails never blocks the
record; its output says the trees could not be pinned. Whether a run is pinned is read from the
refs, never stored. The refs are clone-local: prawduct's evidence sync pushes only its notes
ref. `compare.py --pin` pins the trees of runs recorded before this, and `compare.py` warns
about any review whose tree is gone or whose event names none. The research README says how to release the refs at the
stop.

## Consumer note
none: paired native runs happen only on development builds; this adds clone-local refs under
`refs/prawduct/native-trees/` there and nothing elsewhere
