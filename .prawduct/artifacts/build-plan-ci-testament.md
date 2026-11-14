---
artifact: build-plan
version: 2
scope: ci-testament
branch: feature/ci-testament
base: develop
working-branches: []
partition: "serial, one builder - the runner and the workflow that calls it are one seam, and the conventions test reads both"
governed_by:
  - artifact: architecture
    dispositions:
      - "every fact has one home → conforms; the tests the job runs beside a pool run are derived from the manifest's own selection rather than restated, the suite's flags stay in pyproject.toml, and the pool image's Python becomes a checked copy of the floor as the matrix already is"
      - "authority fails closed; advice fails soft → conforms; a pool that refuses the job's key fails the job, and only a pool that cannot be reached falls back to the job"
      - "local-first → inapplicable because the norm is about governance coordination, and this is the repo's own CI"
      - "an independent reviewer never mutates the session it reviews → inapplicable because no review path changes"
      - "the plugin writes nothing into a governed repo except its own state → inapplicable because nothing under plugin/ changes"
      - "written in Python, never specific to Python → inapplicable because no gate or canary changes"
      - "guides and reviews, never implements → inapplicable because this is the framework repo's own tooling, not a governed product's"
      - "goals and verification bind, method is advice → conforms"
  - artifact: security-model
    dispositions:
      - "untrusted governance state is data, not instructions → inapplicable because no governance state is read"
      - "a destructive or irreversible operation requires owner approval at the operation level → conforms; the secret and the two variables are set at the owner's instruction of 2026-11-11 and each is removable, and nothing is published"
      - "a governed product's content leaves its repository only through a pinned, owner-approved surface → inapplicable because the norm governs the plugin acting in a product; here the repo's own public tree goes to the pool its developers already send it to"
  - artifact: project-preferences
    dispositions:
      - "CI workflows restate no fact that lives in pyproject.toml → conforms; tests.yml gains no pytest flag and no dependency name"
      - "Parallelization (the worker count is a developer-ergonomics setting CI inherits) → conforms; the statement stands for a suite run on the job, and a pool run takes its parallelism from the pool"
depends_on:
  - .github/workflows/tests.yml
  - .testament.toml
  - tests/preferences/test_ci_workflow_conventions.py
  - documentation/running-tests.md
  - .prawduct/owner-rulings.md
last_validated: 2026-11-11
---

## Goals

**Response taken:** Proceed, citing it. The owner said on 2026-11-11 "let's get ci using
testament", supplying a client key ("github secret") and the coordinator's address ("variable I
think, not secret"); the previous session's handoff quotes the owner on the same question: "We
should be. I can get a key if needed". Both are in `.prawduct/owner-rulings.md`.

**Product:** A push or a pull request gets its verdict from the same pool, image and selection a
developer's `testament run` uses, so CI and the developer's machine stop being two different ways
of running the suite, and CI's runs appear in the pool's history beside everyone else's.

**Architecture:**
- One runner, new `tools/ci-suite.py`, decides where the suite runs and is the only thing the
  workflow's test jobs call. Its decisions are unit-tested; a workflow's inline shell cannot be.
- It has two stages, run as two jobs. `pool` holds the key and runs no test; `tests` runs pytest
  and is given no secret. The first hands the second one word: whether the pool ran the suite.
- The `pool` job installs the pool's own published CLI build, downloaded from the pool's console
  with the job's key. Testament's source is private and this repo is public, so the job cannot
  install it from source, and a build taken from the pool can never be the wrong version for
  that pool.
- A pool run covers what `.testament.toml` selects. The `tests` job runs what the manifest
  selects out, derived from the manifest's own marker expression, so the two halves are the
  whole suite by construction.
- What each job does, by the workflow's situation:

  | The workflow | `pool` job | `tests` job runs |
  |---|---|---|
  | has no key (a fork's pull request, Dependabot) | passes, says so | the whole suite |
  | has a key and the pool answers | the pool's result | what the manifest selects out |
  | has a key and the pool cannot be reached, is busy, loses the run twice, or does not finish in time | passes, with a warning | the whole suite |
  | has a key and the pool refuses it, or the settings are incomplete | fails, naming why | the whole suite, for the verdict on the tree |

**Constraints:**
- The key is held by a job that installs nothing from a package index and runs no test. A step,
  or a child's stripped environment, is not a boundary: a process can read its parent's.
- `pull_request_target` is never a trigger: it would hand a fork's code the key, and the key runs
  code on the owner's machines.
- `tests.yml` keeps its triggers, its matrix, its history depth and its rule against pytest flags.
- The pool's addresses are repository variables, not text in a tracked file. The run's summary
  names no runner.

**Tradeoffs accepted:**
- *Inferred:* a pool that cannot be reached must not turn CI red, because the verdict is about the
  tree and the pool is the owner's own machines. Testament's own repository chose the opposite
  (`--no-fallback`, no run on the job) to save Actions minutes, which a public repository does not
  pay for. Worth revisiting if fallbacks become frequent enough that the pool's history stops
  describing CI.
- *Inferred:* a pool that refuses the key fails the `pool` job even when the suite passes in the
  `tests` job. Nothing else tells the owner that CI has stopped using the pool, and a warning on
  a green run is not read.
- *Inferred:* a third setting, the console's address, is needed beside the two the owner supplied,
  because the CLI build is served by the console and not by the wire address.
- Push and pull-request runs of one branch both go to the pool. The workflow's reason for running
  both (they test different trees) stands; what it now spends is pool slots rather than free
  Actions minutes. Put to the owner at the boundary rather than changed here.
- The `tests` job waits for the `pool` job, because what it runs depends on the answer. Running
  the selected-out tests in a third, concurrent job would save under a minute a run and would run
  them twice on every pull request from a fork.

**Decisions made mid-build:**
- `docker/testament.Dockerfile` is pinned by the conventions test and not edited. Its comment
  ("Python 3.14 is the CI matrix's current leg") is still true, and the file is an image input:
  an edit to a comment would rebuild the pool's image for nothing. Settled by "every fact has one
  home": the pin is the reference, the comment needs no second statement of it.
- The runner became two stages in two jobs after the boundary review. The first version held the
  key in one step and stripped it from pytest's environment; the review pointed out that a child
  reads its parent's environment from `/proc`, so every test and every dev dependency on a keyed
  job could read the key. Settled by the constraint the plan already stated (the key never
  reaches a test), which the first version claimed and did not meet.
- Chunk 03 keys on `verdict` and fails closed on a missing one rather than deriving it from the
  exit code. The CLI the job runs is always the pool's own build, so it always carries `verdict`,
  and a copy of testament's outage list here would be a second home for a fact testament owns.
  Settled by the CLI's own instruction ("key scripts on verdict") and "every fact has one home".
- Chunk 03's selection check is an allowlist (one `-m`, plus output-only flags), not a list of
  narrowing flags to refuse: a flag it has never seen fails closed, by name. Settled by the
  plan's constraint that the two runs are the whole suite by construction.
- A `failed` verdict whose reason is neither a failed test nor an empty selection (for example
  `population_mismatch`) is a refusal, not retried: testament marks it a failure, and it can come
  from the project's own hung test. The pool job is red and the test job runs the whole suite.
  Settled by "an ending this runner cannot read fails closed".
- A failed run that the pool then cut short stays the pool's run: the test job runs only what
  the manifest selects out, so the tests the cut left unrun run nowhere this time. CI is red
  either way and the summary names them. Running the whole suite on the job as well would cost a
  full run on every such red to learn about tests behind a failure already being fixed. Settled
  by the product goal (the tree gets a verdict); revisit if cut-short runs become common.
- Both pool attempts share one ten-minute allowance, and the `pool` job's limit is set from it
  (15 minutes); the `pytest` job keeps the 20 minutes it had, a limit earlier runs of the whole
  suite on GitHub's runner fit inside (about five minutes each). The review noted the first
  version's single 30-minute limit was unmeasured against two full waits plus a suite run.
- A busy console (HTTP 408 or 429) is an outage, not a refusal: read as a refusal it would turn
  CI red and send the reader to replace a key that is fine.
- The rule that the key is held by a job that runs no test and reaches no fork's code is a norm
  this work originated. It is a row in `project-preferences.md`, marked as the agent's, for the
  owner to confirm or strike.

**Level:** High for the runner's decisions, which were each observed against the live pool on
2026-11-11 before the plan was written (the CI key runs a file on the pool from an empty home
directory; the console serves the build to that key and refuses a request without one; an
unreachable coordinator under `--no-fallback` is exit 2 with `retryable: true`; no key is
`machine_not_set_up`). Medium for the job itself until it has run on a GitHub runner: whether the
client needs anything the runner image lacks is unobserved. The first push of the branch settles
it.

## Verification Strategy

The runner's decision table is tested with its outside calls (the download and install, the pool
run, pytest) replaced, and the entry point is driven once per stage with nothing replaced but
those calls' bodies. The tests are shown able to fail by a mutation sweep over the runner, the
workflow and the pool image, with a control in each group that must survive. The workflow's
properties are tested on the parsed workflow, as the conventions test already does. The product
check is the branch's own CI run: its `pool` job's summary must say the suite ran on the pool,
and its `pytest` job must run only the selected-out tests. The no-key row is the `tests` stage
run with no word, which is `python -m pytest`, the command CI ran before this work.

## Build Chunks

### Chunk 01: The runner decides where the suite runs

- **Description:** new `tools/ci-suite.py`, in two stages. `pool` reads the job's settings,
  fetches and installs the pool's CLI build, runs the suite on the pool and answers whether it
  did; `tests` runs the selected-out tests or the whole suite on that answer, per the table in
  Goals. Each writes a job summary that says what it ran and what failed.
- **Depends on:** none
- **Deliverables:** new `tools/ci-suite.py`; new `tests/test_ci_suite.py`.
- **Tests:** One per row of the table and per boundary inside a row: no key passes `pool`,
  attempts no download and leaves the whole suite to `tests`; a pool verdict of pass or fail is
  the `pool` job's, and `tests` runs the selected-out tests either way; a retryable end is tried
  once more within one allowance and then leaves the suite to `tests`; a refusal fails `pool`
  and still leaves the suite to `tests`; incomplete settings fail and name the setting; a
  download whose bytes do not match the pool's checksum, or whose name is not a wheel's, is not
  installed; the `pool` stage never runs a test; `tests` runs the whole suite on any word but the
  pool's; the selected-out expression against this repo's manifest is the complement of the
  manifest's.
- **Acceptance criteria:** every row of the table is a passing test; the runner uses the standard
  library only; `tests` run locally with no settings runs the suite on this machine.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

### Chunk 02: The workflow calls the runner, and every description of CI agrees

**Type:** cumulative-final

- **Description:** `tests.yml` gains the `pool` job, which calls the runner's `pool` stage with
  the key, the two addresses and the branch name, and its `pytest` job calls the `tests` stage
  with the pool job's answer; the conventions test pins what must hold of the workflow now that
  it carries a secret; `.testament.toml`, `pyproject.toml`, `documentation/running-tests.md` and
  `documentation/project-structure.md` say what CI does; the owner's words, the norm's row, the
  change record and the repository's secret and variables are in place.
- **Depends on:** Chunk 01
- **Deliverables:** `.github/workflows/tests.yml`;
  `tests/preferences/test_ci_workflow_conventions.py`; the four descriptions above;
  `.prawduct/artifacts/project-preferences.md`; `.prawduct/owner-rulings.md`; new `.prawduct/changes/ci-testament.md`; the Actions secret
  `TESTAMENT_KEY` and variables `TESTAMENT_COORDINATOR` and `TESTAMENT_CONSOLE`.
- **Tests:** no workflow triggers on `pull_request_target`; the key is named only by the `pool`
  job's own step; that job has exactly its three steps; the `pytest` job is given one word and
  no secret and runs whatever the `pool` job's result; no step runs pytest but through the
  runner; the token is read-only; the addresses are variables; the pool image's Python is the
  declared floor.
- **Acceptance criteria:** the branch's CI run reports the suite ran on the pool and passes; no
  tracked file names the pool's hosts; no sentence in the tree still says CI runs `python -m
  pytest` on the runner as its only path.
- **Done when:**
  1. Acceptance criteria met, the declared suite recorded once on the finished branch
  2. Committed, then `/prawduct:critic cumulative`

### Chunk 03: The runner keys on testament's verdict, and refuses a selection it cannot complement

**Type:** cumulative-final

- **Description:** The revival's boundary review (2026-11-14) paired a native review, which found
  that the runner reads testament's exit codes as they stood on 2026-11-11. testament has since
  frozen its exit codes and added `verdict` / `verdict_reason` to the envelope (`testament run
  --help`: "key scripts on verdict"). Exit 75 is an outage, and exit 2 can carry a test that
  failed before the pool cut the run short ("never retry it away"). The runner read exit 75 as a
  refused key, so every outage turned CI red and pointed at the key, and it retried any retryable
  exit 2, which could retry away a real failure. Now the pool stage decides by `verdict`:
  `passed` is a pass; `failed` with tests failed or nothing collected is the tree's result; any
  other `failed` is a refusal; `unavailable` is retried once within the allowance, then falls
  back; a missing or unknown verdict is a refusal (fail closed). `selected_out` refuses a manifest
  it cannot complement exactly: a second `-m`, a joined `-m` form, `-k`/`--deselect`/`--ignore`,
  a path after `pytest`, or a `default_selection` other than the suite's `testpaths`. The pool run
  is started from the repo root, a console that drops mid-download is an outage, the matrix
  comment says what a new leg now runs, and a test holds the pool job's time limit above the
  allowance.
- **Depends on:** Chunk 02
- **Deliverables:** `tools/ci-suite.py`; `tests/test_ci_suite.py` (its envelope fixtures follow
  testament's frozen contract, renegotiated in the open); `tests/preferences/test_ci_workflow_conventions.py`;
  `.github/workflows/tests.yml` (comment only); `documentation/running-tests.md`.
- **Tests:** one per verdict path, including exit 2 with a failed test (never retried, the job
  fails, the failures are named) and exit 75 (retried once, then a warning and a fallback); each
  selection the runner cannot complement is refused; an `IncompleteRead` is an outage; the
  conventions test compares the pool job's `timeout-minutes` with the allowance.
- **Acceptance criteria:** no envelope a frozen-contract testament can emit is misread. The
  branch's own CI run reports, in the `pool` job's log, that the suite ran on the pool.
- **Ruled by the owner 2026-11-14 (`owner-rulings.md`):** CI does not pass `--fresh --no-cache`
  (testament's advice for a required merge check: a throwaway container and no cached passes),
  which would cost a full, uncached run on the pool for every push and PR. Revisit if a cached
  pass ever hides a real failure.
- **Done when:**
  1. Acceptance criteria met, the declared suite recorded once on the finished branch
  2. Committed, then `/prawduct:critic cumulative`
