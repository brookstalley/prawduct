# Running tests

How agents run this repo's tests. `AGENTS.md` points here rather than carrying it, because
everything in `AGENTS.md` is injected into every session and this is read only when running tests.

Run tests with `testament run`, not `pytest` directly. It sends this worktree (uncommitted
and untracked files included; ignored files such as `.env` never leave the machine) to
testament's runners and streams the results back. If no coordinator answers, it runs the same
tests here under this machine's test-slot cap and says so.

If `testament` isn't installed: `uv tool install
git+ssh://git@github.com/brookstalley/testament@main` (or `git+https://…`), then
`testament guide machine`. Until it is, run `pytest` as before.

    testament run --json -- tests/unit/test_foo.py -k bar   # any pytest selection
    testament run --json                                     # the project's default suite

Read the JSON on stdout:

- `exit_code`: 0 all passed; 1 tests failed (a real red: fix it); 5 nothing collected;
  2 anything else, which is **not** a test result. Read `error.code`; when `error.retryable` is
  true, run again.
- `report.items[]`: one per test, with `outcome` (`passed`, `failed`, `error`, `skipped`),
  `message` (pytest's failure text for a failed or errored test) and `runner`.
- `report.missing`: tests that were requested but never reported. A non-empty list is exit 2
  (`population_mismatch`), never a pass.
- `fallback`: present when the tests ran on this machine instead of the runners. Flags
  that need one local pytest process (`-x`, `--maxfail`, `-n`, `--lf`) always run here;
  `fallback.reason` names the flag. Flags that need a terminal (`--pdb`, `-s`, `--co`) are
  refused under `--json`.
- `setup`: present when testament isn't fully set up for this repo or machine. The tests
  still ran; tell the person, and point them to the `guide` command it names.

`testament status` shows the runners and what's queued.

## Recording evidence

`prawduct-hook test-evidence record` records the boundary run, and it runs on the pool. The
first `test_commands` entry in `.prawduct/project-state.yaml` is
`testament run --junit-xml {junit_xml}`, and the recorder ingests the JUnit report it writes.
If no coordinator answers, testament runs the same tests on this machine and the recorder takes
that run the same way. The other two entries run on this machine: the collector's node suite,
and the tests the pool selects out because runners have no git history or backlog cache
(`requires_history`, `requires_local_cache`). Together the three entries are the whole suite.

A run that reaches no result leaves no report, and the recorder refuses to record it. So does a
command that exits non-zero while its report shows no failing test, which is what a pool run
reporting `population_mismatch` looks like.
