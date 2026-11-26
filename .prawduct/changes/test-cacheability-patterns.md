---
schema: 1
type: feature
scope: test-cacheability-patterns
date: 2026-11-26
title: The test-determinism page names three more cacheability patterns, and the uncacheable-tests advisory fires and names each cause's remedy
---
The owner ruled on 2026-11-26 (`.prawduct/owner-rulings.md`, "test cacheability") that the lessons
this repo's own cache work proved (#1218, #1226) ship to consuming repos. This change does that.
It adds no mechanical detector, under the design-stance ruling of the same day.

### The patterns page
`plugin/docs/test-determinism.md` grows from eight patterns to eleven:

- P9: a test runs the product's own entry point as a subprocess.
- P10: a tool child reads ambient machine state.
- P11: production code reads the clock or randomness directly.

A new section, "Declaring a test uncacheable on purpose", covers tests whose subject is the
checkout or the network. The page also says that P9 through P11 are found by measuring, not by
reading a change, so the Critic's judged set is unchanged. `tests/test_discipline_table.py` now
derives the pattern rows from the patterns section and pins the count the prose states.

### The advisory
`plugin/lib/testament_cache_probes.py` maps each cause kind testament reports to its pattern and a
one-line remedy (`REMEDIES`), in `owner_action`. A kind not in the map gets a pointer to the page
and no guess. The `file` kind, a read outside the tree and temp, points at the page's "Declaring a
test uncacheable on purpose" section, which now says to read such a file from the tree or the
test's temporary directory when it is not the test's subject.

The advisory says to fix first the cause that frees the most tests, and the summary now leads with
it. Causes are ranked by testament's `frees` (what fixing a cause frees once the causes ranked
before it are fixed), or by `alone` from a coordinator that sends no `frees`. A cause is raised
when that count is above 0, so a cause that never blocks a test alone but frees some once others
are fixed is raised now too. The evidence format and `PROBE_VERSION` are unchanged. The advisory
never fired before this change (below), so no dismissal exists to reset.

**Before this change the advisory never fired.** The probe read a provisional envelope (`root`,
a `rows` list) that testament never shipped. testament writes `<project>.<suite>.json` with a
single `row` and no `root`, so every real snapshot read as nothing to report. The probe now reads
the shipped shape. It takes the project from `.testament.toml`'s `name`, which testament requires,
and finds this project's snapshots by the `project` each file names, not by its filename.

**A snapshot counts only when its `tree` is the tree of one of HEAD's last 500 commits.** The
envelope's `commit` is a synthetic commit in testament's own store, never one of the repo's, so it
cannot place a run on a branch. The `tree` is the worktree content the run shipped. It equals a
commit's tree only when the run was of that commit with nothing uncommitted, so a dirty-tree run,
perhaps a sibling worktree's work in progress, is skipped. Each snapshot is judged alone. One that
is skipped (narrowed only, an unknown version, unreadable, or not of this branch) is named on
stderr. The other suites' current snapshots keep reporting, but no open advisory resolves on that
sync. The probe reports "could not look" only when none of the project's snapshots is usable. Another
project's file, whatever its shape, never affects this one. One test fixture,
`tests/fixtures/testament_cacheability_snapshot.json`, is a real snapshot of this repo trimmed to
four causes, and it drives the advisory end to end with its own synthetic commit.

## Consumer note
If your repo runs its tests through testament, the uncacheable-tests advisory now actually
appears at session start. It never fired before, because it read a snapshot shape testament never
wrote. For each cause it gives the remedy pattern in prawduct's `docs/test-determinism.md`. That
page now has three more patterns (P9 to P11: run your own CLI in-process in the heavy tests, start
tool children through one isolating and dating helper, give the clock and randomness one
replaceable owner) and a section on declaring a test uncacheable on purpose.

The advisory reads only a snapshot of a clean run of a commit on your branch. After a run with
uncommitted changes, it skips that suite until the suite runs on a clean commit, and it says so at
session start. A clean run of an older commit on your branch still counts, and it reports the causes
as they were at that commit, not as they are at HEAD.
