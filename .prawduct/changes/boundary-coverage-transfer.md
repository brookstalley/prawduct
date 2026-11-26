---
schema: 1
type: fix
scope: boundary-coverage-transfer
date: 2026-11-25
title: "check-boundary-coverage applies the PR gate's base-advance transfer, and names it pr-transferred (#1250)"
closes: [brookstalley/prawduct#1250]
---
A branch that synced its base after its boundary review passed the PR gate by the base-advance
transfer: its judgeable diff was byte-identical across the advance, and a suite run had met its tip.
`check-boundary-coverage` did not apply that transfer. No review fact starts at the new merge-base,
so it read the same merge as `uncovered`, and `check-releasability` printed a NOTE calling reviewed
work unreviewed. #1249 at the v3.10.0 cut was the case. The records-only commit after its sync was
not part of the failure: its paths are not judgeable, so it composes as a free edge.

The op now reads the grant the PR gate recorded for the merged span first
(`gates.recorded_transfer_grant`), so the authority's decision stands without a second suite check.
With no grant it re-decides with the gate's own function, `gates.base_advance_transfer`, which the
PR gate and the Stop gate also call. Its suite question is then asked of the branch: runs recorded
at the branch's commits that met its tip under the PR gate's own tolerance, never the release
checkout's own record, which a suite run in flight voids. Either way, the op then asks the
owner-ruled boundary question of the span the coverage came from: a boundary review, then only
`verify-resolutions` passes. A merge that passes reads as a new classification, `pr-transferred`,
which counts as covered and is named in the count line. A transfer of inner-stage-only coverage
still reads `inner-only`. When the diff matched and no grant or run was found, or the transfer check
could not run, the `uncovered` reason says which. Grants and suite runs are not transported between
clones, so a release cut in another clone can still read such a merge as `uncovered`, and the
reason names that limit.

## Consumer note
`check-boundary-coverage` and the `boundary coverage:` line in `check-releasability` can now name
`pr-transferred`: a merge whose branch synced its base after review and that the PR gate passed by
its base-advance transfer. It counts as covered. `--json` `counts` has a new `pr-transferred` key.
The answer reads evidence from the clone the release runs in: a merge whose PR gate ran in another
clone can still read `uncovered`, with a reason saying so.
