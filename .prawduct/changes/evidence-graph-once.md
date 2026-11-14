---
schema: 1
type: refactor
scope: evidence-graph-once
date: 2026-11-12
title: the excused-gap search and the coverage search walk one evidence graph
closes: [brookstalley/prawduct#1157]
---
The Stop gate's excused-gap arm (`coverage_algebra.excused_gap_verdict`) is relax-only because every
review and free edge it composes is one `coverage_verdict` would use. That held only while `_reach`
and `_find_path` each rebuilt the same evidence graph by hand: the node set, the review adjacency and
the free-edge relation. No test compared the copies, so a change to one would have let the arm compose
across edges coverage no longer grants, failing open in the gate that ends a session.

Both searches now build one `_EvidenceGraph` (nodes, review steps indexed in both directions, free
steps from per-tree keys or the pairwise reference probe). Verdicts are unchanged.
`TestOneEvidenceGraph` checks 300 seeded cases in both free-edge forms. `_reach`'s closure must be
exactly what `_find_path` reaches, and every non-gap step of an excused path must be a valid review
edge or a genuinely free interval. Both tests were seen red against mutants of the old `_reach` and of
the shared builder.

Also: `gates._cached_diff_fn`'s docstring no longer claims that every caller pairs it with
`_tree_key_fn`. The uncovered-cause explanation passes it alone because that explanation only lists
the files of named intervals. And `hook-surface.md` gains the rule that a message from a hook that
exits 0 must use the host's delivery channel, not plain stderr.

## Consumer note
none: internal refactor of the coverage algebra; no gate verdict, message or command changes
