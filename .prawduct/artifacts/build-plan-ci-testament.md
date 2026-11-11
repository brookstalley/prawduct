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
  workflow's test step calls. Its decisions are unit-tested; a workflow's inline shell cannot be.
- The job installs the pool's own published CLI build, downloaded from the pool's console with the
  job's key. Testament's source is private and this repo is public, so the job cannot install it
  from source, and a build taken from the pool can never be the wrong version for that pool.
- A pool run covers what `.testament.toml` selects. The job itself runs what the manifest selects
  out, derived from the manifest's own marker expression, so the two halves are the whole suite by
  construction.
- Where the suite runs, by the job's situation:

  | The job | Suite runs | Job result |
  |---|---|---|
  | has no key (a fork's pull request, Dependabot) | on the job | the suite's |
  | has a key and the pool answers | on the pool, plus the selected-out tests on the job | theirs |
  | has a key and the pool cannot be reached, or loses the run twice, or does not finish in time | on the job, with a warning | the suite's |
  | has a key and the pool refuses it, or the job's settings are incomplete | on the job, for the verdict on the tree | failed, naming why |

**Constraints:**
- The key reaches one step only, never the dependency install, and never a test process.
- `pull_request_target` is never a trigger: it would hand a fork's code the key, and the key runs
  code on the owner's machines.
- `tests.yml` keeps its triggers, its matrix, its history depth and its rule against pytest flags.
- Nothing that names the pool's hosts is written to a tracked file: the addresses are repository
  variables. The run's summary names no runner.

**Tradeoffs accepted:**
- *Inferred:* a pool that cannot be reached must not turn CI red, because the verdict is about the
  tree and the pool is the owner's own machines. Testament's own repository chose the opposite
  (`--no-fallback`, no run on the job) to save Actions minutes, which a public repository does not
  pay for. Worth revisiting if fallbacks become frequent enough that the pool's history stops
  describing CI.
- *Inferred:* a pool that refuses the key fails the job even when the suite passes on it. Nothing
  else tells the owner that CI has stopped using the pool, and a warning on a green run is not
  read.
- *Inferred:* a third setting, the console's address, is needed beside the two the owner supplied,
  because the CLI build is served by the console and not by the wire address.
- Push and pull-request runs of one branch both go to the pool. The workflow's reason for running
  both (they test different trees) stands; what it now spends is pool slots rather than free
  Actions minutes. Put to the owner at the boundary rather than changed here.
- The selected-out tests run after the pool's, not beside them. Running them concurrently would
  save about a minute a run and would have the job writing into the worktree while the client
  ships it.

**Decisions made mid-build:**
- `docker/testament.Dockerfile` is pinned by the conventions test and not edited. Its comment
  ("Python 3.14 is the CI matrix's current leg") is still true, and the file is an image input:
  an edit to a comment would rebuild the pool's image for nothing. Settled by "every fact has one
  home": the pin is the reference, the comment needs no second statement of it.
- The job's time limit goes from 20 to 30 minutes, so the worst path through the runner (a pool
  run lost late and tried again, then the suite on the job) ends with a verdict. Not settled by
  the goals; the cheaper of the two ways to be wrong.
- The rule that the key reaches one step and no fork's code is a norm this work originated. It
  is a row in `project-preferences.md`, marked as the agent's, for the owner to confirm or strike.

**Level:** High for the runner's decisions, which were each observed against the live pool on
2026-11-11 before the plan was written (the CI key runs a file on the pool from an empty home
directory; the console serves the build to that key and refuses a request without one; an
unreachable coordinator under `--no-fallback` is exit 2 with `retryable: true`; no key is
`machine_not_set_up`). Medium for the job itself until it has run on a GitHub runner: whether the
client needs anything the runner image lacks is unobserved. The first push of the branch settles
it.

## Verification Strategy

The runner's decision table is tested with its three outside calls (the download, the pool run,
pytest on the job) replaced, each row red first. The workflow's properties are tested on the
parsed workflow, as the conventions test already does. The product check is the branch's own CI
run: its summary must say the suite ran on the pool, and its pull-request-shaped twin is checked
when a pull request exists. The no-key row is checked on the runner by a run with the key withheld
(`workflow_dispatch` is not added for it; the check is a local run of the runner with an empty
environment against the real suite's collection).

## Build Chunks

### Chunk 01: The runner decides where the suite runs

- **Description:** new `tools/ci-suite.py`: reads the job's settings, fetches and installs the
  pool's CLI build, runs the suite on the pool and the selected-out tests on the job, or the whole
  suite on the job, per the table in Goals; writes a job summary that names where the suite ran
  and what failed.
- **Depends on:** none
- **Deliverables:** new `tools/ci-suite.py`; new `tests/test_ci_suite.py`.
- **Tests:** Red first, one per row of the table and per boundary inside a row: no key runs the
  whole suite on the job and attempts no download; a pool verdict of pass or fail is the job's,
  and the selected-out tests run either way; a retryable end is tried once more and then runs on
  the job; a refusal runs on the job and still fails; incomplete settings fail and name the
  setting; a download whose bytes do not match the pool's checksum, or whose name is not a wheel's,
  is not installed; no test process's environment holds the key; the selected-out expression
  against this repo's manifest is the complement of the manifest's.
- **Acceptance criteria:** every row of the table is a passing test; the runner uses the standard
  library only; run locally with no settings it runs the suite on this machine.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

### Chunk 02: The workflow calls the runner, and every description of CI agrees

**Type:** cumulative-final

- **Description:** `tests.yml`'s test step calls the runner with the key, the two addresses and
  the branch name; the conventions test pins what must hold of the workflow now that it carries a
  secret; `.testament.toml`, `pyproject.toml`, `documentation/running-tests.md` and
  `documentation/project-structure.md` say what CI does; the owner's words, the norm's row, the
  change record and the repository's secret and variables are in place.
- **Depends on:** Chunk 01
- **Deliverables:** `.github/workflows/tests.yml`;
  `tests/preferences/test_ci_workflow_conventions.py`; the four descriptions above;
  `.prawduct/artifacts/project-preferences.md`; `.prawduct/owner-rulings.md`; new `.prawduct/changes/ci-testament.md`; the Actions secret
  `TESTAMENT_KEY` and variables `TESTAMENT_COORDINATOR` and `TESTAMENT_CONSOLE`.
- **Tests:** Red first: no workflow triggers on `pull_request_target`; the key is named in exactly
  one step's environment and in no job's or workflow's; the test step runs the runner and no
  other step runs pytest; the token is read-only; the addresses are variables; the pool image's
  Python is the declared floor.
- **Acceptance criteria:** the branch's CI run reports the suite ran on the pool and passes; no
  tracked file names the pool's hosts; no sentence in the tree still says CI runs `python -m
  pytest` on the runner as its only path.
- **Done when:**
  1. Acceptance criteria met, the declared suite recorded once on the finished branch
  2. Committed, then `/prawduct:critic cumulative`
