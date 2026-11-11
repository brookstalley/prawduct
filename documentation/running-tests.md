# Running tests

How agents run this repo's tests. `AGENTS.md` points here rather than carrying it, because
everything in `AGENTS.md` is injected into every session and this is read only when running tests.

Run tests with `testament run`, not `pytest` directly. It sends this worktree (uncommitted
and untracked files included; ignored files such as `.env` never leave the machine) to
testament's runners and streams the results back. If no coordinator answers, it runs the same
tests here under this machine's test-slot cap and says so.

If `testament` isn't installed: `uv tool install
git+ssh://git@github.com/brookstalley/testament@main` (or `git+https://…`), then
`testament guide machine`. No pool is needed: with no coordinator, `testament run` runs the
tests on this machine. Until it is installed, run `pytest` as before, and record evidence the
way "Recording evidence" below describes for a machine without testament.

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

Recording needs `testament` and node installed: any command that cannot start fails the whole
record. On a machine without testament, run the two suites yourself and ingest both reports in
one call:

    uv run --extra dev python -m pytest tests/ --junit-xml=/tmp/py.xml -q
    node --test --test-reporter=junit --test-reporter-destination=/tmp/node.xml collector/test/*.test.mjs
    prawduct-hook test-evidence record --from-junit /tmp/py.xml --from-junit /tmp/node.xml

A plain `pytest tests/` run already includes the marked tests, so these two reports are the whole
suite.

## In CI

`.github/workflows/tests.yml` runs the pytest suite through `tools/ci-suite.py`, whose docstring
is the reference for what follows. It has two stages, which are two jobs:

- **`pool`** holds the pool's key. It downloads the pool's own CLI build from the pool's console,
  runs `testament run --no-fallback`, and tells the next job whether the pool ran the suite. It
  installs nothing from a package index and runs no test, which is why it may hold the key.
- **`pytest`** runs after it, whatever its result, and is given no secret. When the pool ran the
  suite it runs the tests `.testament.toml` selects out; otherwise it runs `python -m pytest`,
  the whole suite. A pull request from a fork is always the second case: it gets no key.

Each job's summary on GitHub says what it ran.

Three repository settings feed it (*Settings → Secrets and variables → Actions*):

- `TESTAMENT_KEY`, a secret: a client key made for this CI in the pool's console (People, **+ New
  client key**). Revoke it there when CI should stop using the pool.
- `TESTAMENT_COORDINATOR`, a variable: the pool's wire address, the one `testament run` submits to.
- `TESTAMENT_CONSOLE`, a variable: the address the console is opened at, `https://…`. The CLI
  build is downloaded from it.

Reading a red or yellow run:

- **A warning on `pool`, "the pool could not be used"**: the pool or its console did not answer,
  was busy, lost the run twice, or took longer than the ten minutes the runner gives it. `pool`
  passes, `pytest` ran the whole suite, and its result is the verdict. Nothing to fix in the
  repository.
- **`pool` failed with "this workflow cannot use the pool"**: the pool refused the key, a variable
  is missing, or the build could not be installed. `pytest` still ran the whole suite, so its
  result says whether the tree is sound, and `pool` stays red until the setting is fixed. A
  replaced key is the usual cause: make a new one and set the secret again.
- **`pool` failed with failing tests**: the pool ran the suite and tests failed there. `pytest`
  still ran the tests the pool leaves out.
- **Failing tests** are named in the summary whichever machine ran them.
