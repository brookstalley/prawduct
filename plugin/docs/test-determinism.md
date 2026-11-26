# Test Determinism and Dependency Scope

A test's result depends only on what it exercises, and is the same on any machine, any run.

A test that breaks this costs one of two things. Either its result cannot be trusted to repeat
(determinism), or no runner can reuse a prior result, because the test depends on far more than it
exercises, so an edit to any file re-runs it (reuse and closure breadth). The tests still pass,
which is why none of this shows up until something measures it. The same eleven patterns recur
across products. Stack-agnostic phrasing comes first; pytest names are examples.

## The patterns

| # | Pattern | What it costs | Remedy |
|---|---|---|---|
| P1 | A root test-config file (pytest: the top-level `conftest.py`) imports the app or its core modules at module level | Every test then depends on the whole app: reuse and closure breadth | Import inside the fixtures that need it |
| P2 | An always-on fixture (pytest: `autouse=True`) imports everything, or a package `__init__` eagerly re-exports all its submodules | Every test depends on every module: reuse and closure breadth | Import inside the fixtures that need it; build registries lazily or copy-on-write |
| P3 | A test double or shared helper reads the real clock or real randomness (a fake's constructor calling `datetime.now`, `os.urandom`, `UUID()`) | One fake makes every test that builds it unrepeatable: determinism | Inject or freeze the clock and randomness; no ambient reads in fakes |
| P4 | The clock or randomness is read at import or parametrize time (module-level `now()`, a default argument, a decorator argument) | Every test in the process inherits the value: determinism, process-wide | Inject or freeze it; no ambient reads at import |
| P5 | Build output or setup products live inside the tree (a compiled artifact, a bundle, a generated token, an untracked file the tests read) | A result depends on whether and when that file was produced: determinism and reuse | Build and cache outside the checkout |
| P6 | Tool state that changes test outcomes lives inside the tree (for example a property-testing tool's example database in the checkout) | A result depends on what earlier runs left behind: determinism | Keep that state outside the checkout |
| P7 | Whole-repo scans run at collection time (convention or enforcement tests that read every file while the suite is being assembled) | Their reads count against every test in the process, not only the scanner | Whole-tree reads belong in the test body |
| P8 | Shared code paths write into the checkout during tests | A result depends on, and changes, the tree it ran in | Write under the test's temporary directory |
| P9 | A test runs the product's own command-line entry point as a subprocess where it could call it in-process | A child process is opaque to the runner, so no prior result can be reused: reuse | Run the entry point in-process in the heavy tests (arguments, output, exit status and the state the call mutates swapped in and restored); keep a few subprocess tests that prove the real entry point |
| P10 | A test starts a tool child (git, a package manager) that reads ambient machine state: global or system config, the time now, the user's environment | The child's result differs by machine and by moment, and the runner cannot replay what it read: determinism and reuse | One helper that every such child goes through: it isolates the child (no global or system config), dates it from the suite's clock, the one P11's owner returns, and sheds only the variables that point it somewhere else (git: those naming another repository, not every `GIT_*`, which would shed the isolation too) |
| P11 | Production code reads the clock or randomness directly (P3 and P4 cover test doubles and import time) | Every test that reaches that path makes the read, so none of them can be cached: reuse, and determinism wherever the value is compared | One owner per source, which the product calls and the suite replaces. IDs are the common case: one minted with a random draw where it is needed blocks every test that mints one; derive it from the owner |

P1, P2 and P7 concern the import graph and scope. P3 through P6, P8, P10 and P11 concern
hermeticity, which "tests are independent" implies and does not spell out. P9 concerns what the
runner can see. Measuring any of them is a job for the project's runner (testament is one such
tool); this page defines the patterns and does not depend on any one. P9 through P11 are found by
measuring, not by reading a change: the runner's list of what blocks caching names them (where
the runner is testament, prawduct's `uncacheable-tests` advisory relays that list with each cause's
pattern). Fix first the cause whose fix frees the most tests.

## Declaring a test uncacheable on purpose

Some tests exist to read what these patterns keep out: this checkout's own history, tracked files
or release tags, or the network. Moving them into a temporary directory removes their subject. Such
a test says so in the runner's configuration instead, by its id or by the shared reader it calls,
with the reason; the runner then stops reporting it as a cause (testament, for one, takes an
`[[uncacheable]]` entry with a `why` in `.testament.toml`). Declare only a read that is the test's
subject: a test that merely starts a tool in the checkout while aiming it at a temporary repository
is a fixture to fix (P10), not a read to decline.

## What the review detects, and what a reviewer judges

A mechanical detector reads each changed test-tree file and package `__init__`, and every conftest
(deleting one can make another the root), for the shapes a static read can see. Its results arrive in the review the way the record-lint results do: a
reviewer never raises, restates or re-derives them.

| Pattern | Check id | At the merge boundary | At the inner stage |
|---|---|---|---|
| P1 | `test-scope-conftest` | blocking | observation |
| P2 | `test-scope-autouse`, `test-scope-init` | blocking | observation |
| P3 (in a fake, helper or conftest) | `test-clock-fake` | warning | observation |
| P4 | `test-clock-import` | warning | observation |

- Only sites a change introduces count. A product's existing P1 never blocks an unrelated change,
  and a renamed file introduces nothing. `prawduct-hook determinism-scan` lists the sites that
  already exist, which `/prawduct:janitor`'s Test Fitness theme reads.
- What the detector reads today is Python. A *root* conftest is a `conftest.py` with none in any
  directory above it. *First-party* code is a package or module at a project root (the repo root, or any
  directory holding a `pyproject.toml`, `setup.py` or `setup.cfg`) or under its `src/`, outside a
  test directory; a tree put on the import path some other way is not seen. An import
  under `if TYPE_CHECKING:` is exempt. Under P2 an autouse fixture counts when it is in a `conftest.py`
  and imports any first-party module, and a package `__init__` counts when it imports every one of
  its submodules and has at least three. P3 counts in conftests, fakes and helpers, whether the
  clock is called or handed on (`default_factory=datetime.now`), but not in a test module's own
  tests. Interval clocks (`time.monotonic`, `time.perf_counter`) are not ambient reads.
- Any changed code file under a test tree that is not Python is reported unchecked, never silently
  passed.
- The reviewer judges what the detector did not report: a P3 or P4 read it missed (one made calls
  deep, or in a language without rules), and P5 through P8. Each is a warning at the boundary and an observation inside; process- or conftest-wide
  outranks a single test.

## Waiving a site

A site that stays on purpose carries `prawduct:allow prawduct/test-scope -- reason` on its line, or
on a comment line directly above it. A waiver trailing the previous statement does not reach it. The reason says why the site stays; the reviewer still reads it, and a waiver
with no reason waives nothing.
