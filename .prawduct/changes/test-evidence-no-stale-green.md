---
schema: 1
type: fix
scope: test-evidence-no-stale-green
date: 2026-11-15
title: A record attempt that fails no longer leaves the old green vouching, and an old report no longer vouches for a newer tree
closes: [brookstalley/prawduct#679, brookstalley/prawduct#848]
---
Two fixes to `prawduct-hook test-evidence record`. In both, test evidence claimed more than the
run behind it could show.

**A refused or interrupted record now voids the standing record (#679).** `record` rewrote
`.prawduct/.test-evidence.json` only when a record landed. Every refusal (exit 2) returned
earlier, and a run killed mid-suite never reached the write, so an earlier green went on vouching
for a tree whose latest run had failed or never finished. `test-status`, the Stop gate,
`/prawduct:pr` and `/prawduct:critic` all read green. Now, once the arguments have been checked
and before a suite runs or a report is read, `record` marks the standing record void. A record
that lands replaces it. Anything else leaves it void: a refusal, a crash, or Ctrl-C on a hung
suite.

The void keeps the earlier counts, drops the tree, and takes the current time. It carries
`degraded`, the field every reader already refuses through `gates.run_refusal`, so no reader had
to change. `void` names the attempt for the recorder itself. Because the void is the newest word,
a green `test-run` fact for the same tree from another worktree cannot answer over it.
`--no-rerun` refuses to restamp a void record. Usage errors refuse before the void and leave a
good record untouched. `--from-counts` and `--no-rerun` run nothing and do not void.

**An ingested report stamps a tree only when it is newer than every file the suite reads (#848,
R-4).** `--from-junit` stamped the current tree onto the ingested run and appended a `test-run`
fact for it, so a report written before the last edit became tree-valid evidence for code it never
ran against. `evidence.report_predates_tree` now checks every file the suite can depend on and
withholds the stamp when one is newer than the report. That covers deletions too, dated by the
directory the file left, including files removed by a commit or checkout after the report. A
withheld record stays current this session only, and a `warning:` names the file. Directories are
consulted only for deletions, because the producer's scope record is written into `.prawduct/`
after the report. A bound over every directory would have withheld the stamp on every ingest of
the conventional report path. A test drives the real producer to pin this.

**The fallback's refusal names a way forward that works from the fallback (#848, R-2).** On the
undeclared pytest fallback, the scope record comes from the repo's own producer, so "run the
recorder" was the command that had just refused. There, the remedy now names the narrowing
arguments to drop, or says to fix the producer or declare `test_command`. The ingest site keeps
its remedy.

**The declared run path's non-read of the scope record is now explained, not changed (#848,
R-1/R-6).** It is correct: the declaration defines the suite, and the exit-status check refuses a
command that exits nonzero while its report shows no failing test. The cleanup comment and
`docs/test-report-contract.md` now say so.

Docs updated: `docs/test-report-contract.md` (refusal semantics, both remedy sites, the tree
bound and its blind spots), `documentation/running-tests.md`, the `/prawduct:pr` skill's ingest
advice, and the `degraded` field's comment in `lib/gates.py`.

## Consumer note
If a `test-evidence record` refuses or is interrupted, `test-status` now reads **stale** and names
the attempt. It no longer shows the previous green. Run the suite through the recorder, or ingest a
whole-suite report, to get back to current. Ingesting a report that is older than your latest edit
still records it, but only as current for this session: a later session or another worktree will
run the suite again rather than trust it for a tree it never ran against.
