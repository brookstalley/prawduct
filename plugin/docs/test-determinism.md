# Test Determinism and Dependency Scope

A test's result depends only on what it exercises, and is the same on any machine, any run.

A test that breaks this costs one of two things. Either its result cannot be trusted to repeat
(determinism), or no runner can reuse a prior result, because the test depends on far more than it
exercises, so an edit to any file re-runs it (reuse and closure breadth). The tests still pass,
which is why none of this shows up until something measures it. The same eight patterns recur
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

P1, P2 and P7 concern the import graph and scope. P3 through P6 and P8 concern hermeticity, which
"tests are independent" implies and does not spell out. Measuring either is a job for the project's
runner (testament is one such tool); this page defines the patterns and does not depend on any one.

## What the review detects, and what a reviewer judges

A mechanical detector reads each changed test-tree file and package `__init__` for the shapes a
static read can see. Its results arrive in the review the way the record-lint results do: a
reviewer never raises, restates or re-derives them.

| Pattern | Check id | At the merge boundary | At the inner stage |
|---|---|---|---|
| P1 | `test-scope-conftest` | blocking | observation |
| P2 | `test-scope-autouse`, `test-scope-init` | blocking | observation |
| P3 (in a fake, helper or conftest) | `test-clock-fake` | warning | observation |
| P4 | `test-clock-import` | warning | observation |

- Only sites a change introduces count. A product's existing P1 never blocks an unrelated change,
  and a renamed file introduces nothing. `/prawduct:doctor` lists the sites that already exist.
- What the detector reads today is Python. A *root* conftest is a `conftest.py` with none in any
  directory above it. *First-party* code is a package or module at the repo root or under `src/`,
  outside a test directory; a tree put on the import path some other way is not seen. An import
  under `if TYPE_CHECKING:` is exempt. A package `__init__` counts under P2 when it imports every one
  of its submodules and has at least three. P3 counts in conftests, fakes and helpers, not in a test
  module's own tests.
- A changed test file in a language with no rules is reported unchecked, never silently passed.
- The reviewer judges what a static read cannot: a P3 read made several calls deep, and P5, P7 and
  P8. Each is a warning at the boundary and an observation inside; process- or conftest-wide
  outranks a single test.

## Waiving a site

A site that stays on purpose carries `prawduct:allow prawduct/test-scope -- reason` on its line or
the line above it. The reason says why the site stays; the reviewer still reads it, and a waiver
with no reason waives nothing.

## Measured evidence

When a runner reports each test's determinism causes, a later change lets the review compare that
list with the base's, so a cause site the diff introduced, including one a read missed, is a
finding under the same check ids above.
