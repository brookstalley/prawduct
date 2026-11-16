---
schema: 1
type: fix
scope: test-evidence-no-stale-green
date: 2026-11-15
title: A record attempt that fails no longer leaves the old green vouching, and an old report no longer vouches for a newer tree
closes: [brookstalley/prawduct#679, brookstalley/prawduct#848, brookstalley/prawduct#1178]
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

**`test-status` tells a run in progress from one that died, and can wait for it (#1178).** The void
also carries `in_progress`: the recorder's pid, host, machine, start time and command. While that
process is alive, `test-status` prints `running:` with the elapsed time and, when the last record
has a duration, that duration as an estimate (never a percentage). Once the recorder is gone and
nothing landed, it prints `stale (interrupted):`. A pid is checked against the process's start time
(`ps -o etime`), so a reused pid does not read as the recorder, and an unreaped zombie reads as
gone. A refusal also reads as interrupted, since its recorder has exited. A worktree's first run
shows too: with no usable record to void, the attempt writes a stub with zero counts that every
reader refuses, so a refused first attempt reads as interrupted, where it used to leave no record.

Every state that cannot be checked has an end. "Machine" is the boot (and, on Linux, the pid
namespace), not the hostname, which macOS changes with the network. A recorder on another machine,
or a live pid `ps` could not confirm, reads as running only until it is three times the last run's
duration old (at least 30 minutes), then as interrupted. Its refusal names that time and says that
if no run is going there, the suite can be run now.

Every remedy comes from one owner. `gates.suite_remedy` reads the record's state (running,
interrupted, failing, degraded, not current) and gives the remedy for it. The `verify-resolutions`
refusal (exit 7), `check-releasability`'s `unproven-suite:` line and both gates' coverage-transfer
note print it, instead of each adding its own "run the suite", which told a run in progress to
start a second one. The exit-7 guard's recorded `reason` is that same state, so `running` and
`interrupted` join its slugs. `ps` runs once per verdict rather than once per reader.
`test-status --wait [--timeout N]` (default 300s,
at most 3600s) blocks until the record lands or the recorder dies, then prints the verdict. A
timeout with the run still going exits 75, sysexits' "try again later": 1 would send the reader
to run the suite again, and 3 means the subject could not be read. No hook calls it.
`test-status` now takes arguments, so it left the no-argument set, and `/prawduct:pr`'s grant
became `test-status*`. `lib/record_progress.py` owns the liveness check and the estimate, and
`lib/gates.py` owns the wording.

**An ingested report stamps a tree only when the run behind it started after every edit to a file
the suite reads (#848, R-4).** `--from-junit` stamped the current tree onto the ingested run and
appended a `test-run` fact for it, so a report written before the last edit became tree-valid
evidence for code it never ran against. `evidence.report_predates_tree` now checks every file the
suite can depend on and withholds the stamp when one is newer than the run's start. The start, not
the report's modification time, which is when the run ended: an edit made mid-run predates the
report. The start is the earlier of the report's time less its recorded duration and a
`<testsuite timestamp>` with a UTC offset (pytest writes one). A report giving neither withholds the
stamp. That covers deletions too, dated by the
directory the file left, including files removed by a commit or checkout after the run started. A
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
advice, the critic skill's exit-7 row and `review-cycle.md`'s matching sentence, `building.md`'s
baseline step, the guard-refusal slugs in `artifacts/data-model.md`, and the `degraded` field's
comment in `lib/gates.py`.

## Consumer note
While `test-evidence record` is running, `test-status` prints **running** with the elapsed time and
an estimate from the last run, a worktree's first run included. Wait for it with
`prawduct-hook test-status --wait`, which exits 75 if its timeout passes first, rather than starting
a second run. If a `test-evidence record` refuses or is interrupted, `test-status` now reads
**stale (interrupted)** and names the attempt. It no longer shows the previous green, and a refused
first attempt no longer reads as no evidence. A run on another machine reads as interrupted once it
is three times the last run's duration old (at least 30 minutes). Run the suite through the
recorder, or ingest a whole-suite report, to get back to current. Ingesting a report of a run that
started before your latest edit still records it, but only as current for this session: a later
session or another worktree will run the suite again rather than trust it for a tree it never ran
against.
