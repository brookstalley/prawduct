---
schema: 1
type: fix
scope: exit1-covering-mode
date: 2026-11-18
title: every verify-resolutions demotion now names the mode to re-dispatch in
closes: [brookstalley/prawduct#662]
---
`critic-begin --mode verify-resolutions` has two kinds of demotion. Exit 2 (the delta widened) already
named a covering mode. The exit-1 anchor refusals gave a reason and nothing else: no prior review on
this lineage, a prior fact with no `head_tree`, and a prior tree that cannot be diffed. The skill then
told the reader to apply the demotion property by hand, and two of those triggers (a branch switch,
rewritten history) are by construction the committed-work case. A `final` re-dispatched there reviews
only what the working tree happens to hold.

Each of those refusals now returns `kind: "anchor-unusable"`, still at exit 1, with `fallback_mode`, and
its reason names the re-dispatch. The mode comes from the recommender exit 2 already used, now called
`covering_fallback_mode` because it serves both kinds of demotion. It is asked with "committed work
moved" assumed, so `working_tree_interval_base` decides from the store's review facts and not from the
anchor that failed. A new arm handles a covered HEAD, where the last reviewed state is HEAD's own tree:
the committed work is covered, so it names `final` and no longer falls through to a whole-branch
`cumulative`. That arm applies at exit 2 as well. An unusable evidence store keeps exit 6 and names no
mode. The critic skill's exit table and `review-cycle.md`'s Demotion rows now say to re-dispatch in the
named mode.

## Consumer note
A `verify-resolutions` that cannot use its anchor now prints `Re-dispatch as `<mode>`` in its exit-1
reason. Re-dispatch in that mode. Exit codes do not change.
