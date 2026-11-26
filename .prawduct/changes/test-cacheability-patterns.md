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
one-line remedy (`REMEDIES`), in `owner_action`. It also says to fix the cause that frees the most
tests first. A kind not in the map gets a pointer to the page and no guess. The evidence and
`PROBE_VERSION` are unchanged, so the advisory's id is unchanged and a dismissal still holds.

**Before this change the advisory never fired.** The probe read a provisional envelope (`root`,
a `rows` list) that testament never shipped. testament writes `<project>.<suite>.json` with a
single `row` and no `root`, so every real snapshot read as nothing to report. The probe now reads
the shipped shape. It takes the project from `.testament.toml`'s `name`, decides an envelope is
this branch's by its `commit` being an ancestor of HEAD, and treats a file without a `row` as
unreadable rather than as empty. The provisional reader is gone. One test fixture,
`tests/fixtures/testament_cacheability_snapshot.json`, is a real snapshot of this repo trimmed to
four causes, and it drives the advisory end to end.

## Consumer note
If your repo runs its tests through testament, the uncacheable-tests advisory now actually
appears at session start. It never fired before, because it read a snapshot shape testament never
wrote. For each cause it gives the remedy pattern in prawduct's `docs/test-determinism.md`. That
page now has three more patterns (P9 to P11: run your own CLI in-process in the heavy tests, start
tool children through one isolating and dating helper, give the clock and randomness one
replaceable owner) and a section on declaring a test uncacheable on purpose.
