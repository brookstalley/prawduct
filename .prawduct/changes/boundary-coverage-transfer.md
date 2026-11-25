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

The transfer decision now has one home, `gates.base_advance_transfer`. The PR gate, the Stop gate
and the release op all call it, each asking the suite about the tree it vouches for. When the
transfer grants, the op asks the owner-ruled boundary question of the span the coverage came from.
That is a boundary review, then only `verify-resolutions` passes. A merge that passes reads as a new
classification, `pr-transferred`, which counts as covered and is named in the count line. A transfer
of inner-stage-only coverage still reads `inner-only`. When the diff matched and no suite run met
the tip, the `uncovered` reason now says that, so the remedy reads as a suite run, not a review.

## Consumer note
`check-boundary-coverage` and the `boundary coverage:` line in `check-releasability` can now name
`pr-transferred`: a merge whose branch synced its base after review and that the PR gate passed by
its base-advance transfer. It counts as covered. `--json` `counts` has a new `pr-transferred` key.
