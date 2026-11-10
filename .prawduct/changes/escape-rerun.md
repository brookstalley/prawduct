---
schema: 1
type: chore
scope: escape-rerun
date: 2026-11-10
title: "A scorer for the governance study's escape re-run (#987)"
---
The governance ROI study scored rework only for landings up to 2026-09-10, the last date with a
full 30-day window. #987 re-runs the instrument on later landings to check whether the fast,
ungoverned repo F escapes more than governed work.

`.prawduct/research/escape-2026-10/rerun.py` scores that run without changing the instrument. It
imports `stats.mode`, `stats.CUTOFF` and `escape.WINDOW_DAYS`, and applies the study's
`edge_rates` rule to three disjoint groups: repo F, ungoverned excluding F, and governed. A
landing whose window is still open is counted as `window-open` and left out of the rate. The
script refuses a file in which any `(repo, sha)` appears twice, because a duplicate means a
`--branch` run was appended to the main run, and skipping it would hide that. `test_rerun.sh` is
its known-answer test; it failed with the guard removed before the guard went in. The study's
Re-deriving section gains the steps.

## Consumer note
none: research tooling in this repo's `.prawduct/research/`; nothing ships in the plugin.
