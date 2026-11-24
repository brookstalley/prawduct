---
artifact: build-plan
version: 2
scope: test-determinism
branch: feature/test-determinism
base: develop
working-branches: []
last_validated: 2026-11-24
partition: "01 and 02 concurrent — 01 (the detector and its review channel: plugin/lib, critic_consolidate, waivers.md, tests) built by the coordinator; 02 (prose: docs, methodology, templates, Critic goal prose, janitor theme, discipline table, their budget tests) delegated to one Sonnet delegate in an isolated worktree, writing against the check ids and severities this plan fixes. The files are disjoint; the seam is the check-id vocabulary, which this plan owns and neither chunk changes. 03 serial after 01, because it reuses 01's detector. The coordinator integrates"
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → inapplicable because the detector runs in critic-begin (code) and reviewers only read its results"
      - "authority fails closed; advice fails soft → conforms; a Python test file the detector cannot parse is an `unchecked` entry the boundary rates, never a pass; the doctor and janitor uses are advice and degrade to a note"
      - "local-first → conforms; the detector reads the git object database and the tree, with no network"
      - "the plugin writes only its own state → conforms; the detector and the doctor check read the product's files and write nothing into them"
      - "written in Python, never specific to Python → conforms; checks dispatch per file by language, Python rules are populated first, and a changed test file in a language with no rules is reported `unchecked`, never silently passed"
      - "guides and reviews, never implements → conforms; it is a review instrument, and no product tool checks a diff for these shapes statically (testament measures them after a run, which #1244 consumes rather than re-derives)"
      - "goals and verification bind, method is advice → conforms; Deliverables below are a forecast, and a better route is taken and recorded under Decisions made mid-build"
      - "every fact has one home → conforms; the P1–P8 definitions live in plugin/docs/test-determinism.md, each check's severity in the one severity table consolidation reads, and the real-clock/randomness API list in the detector module; every other surface cites them"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 → conforms; the detector adds no reviewer and no round, and in critic-begin it parses only the changed files under a test tree plus package __init__ files, with the AST"
      - "proportionality ratchets both ways → conforms; expected yield: a BLOCKING on any change that adds a first-party import to a root conftest or an importing autouse fixture, rare per PR but present in every product the 2026-11-24 audit measured; emitted observably because each result enters the review fact under its own check id, which the ledger can count"
      - "state-file growth is advisory only → inapplicable because no state file grows"
      - "review rigor is stage-keyed → conforms; P1/P2 are blocking at the boundary and observations inside, and P1/P2 are not added to the inner BLOCKING set"
  - artifact: data-model
    dispositions:
      - "verdicts from the append-only fact ledger, no model in the write path → conforms; the detector is deterministic code whose results consolidation writes into the review fact"
      - "facts immutable and append-only → conforms; nothing edits a fact"
      - "derived views never authoritative → conforms; no gate reads the doctor listing"
      - "governance documents archived, never deleted → inapplicable because no document's lifecycle changes"
      - "backlog titles conform on every write path → inapplicable because no backlog write path changes"
      - "newer-schema facts block loudly → conforms; any new manifest or fact key is additive, read by readers that tolerate unknown keys"
      - "two stores, two lifetimes → inapplicable because nothing new is stored"
      - "backlog_service_repo selects the authoritative store → inapplicable because the backlog is untouched"
  - artifact: api-contract
    dispositions:
      - "whole-surface semver; evidence store independently schema-versioned → conforms; additive keys only, so no schema bump"
      - "exit codes are the contract → conforms; the doctor check uses doctor's existing exit scheme"
      - "additive-first evolution → conforms; new check ids and keys are added, none repurposed"
  - artifact: observability-strategy
    dispositions:
      - "stable severity-prefix vocabulary → conforms; the doctor lines use the existing prefixes"
      - "the ledger has a single writer → conforms; results reach it only through consolidation"
      - "text emitted into a governed product names no prawduct-internal identifier → conforms; a finding and a doctor line state the shape and its remedy in plain words and cite the shipped doc and the waiver, never the P-numbers, this plan, #1243 or a chunk"
---

## Goals

**Response taken:** Ask, in one batch. The owner answered on 2026-11-24 ("Agreed to all
recommendations", after "Agreed on all counts" in the testament session), recorded at the top of
`.prawduct/owner-rulings.md`. Backlog item #1243 (stage design); its measured leg is #1244, blocked by
#1096.

**Product:** governed products stop writing tests whose results can't be trusted to repeat, or that a
runner can't reuse. The testament pool for 2026-11-17 to 11-24 measured 36–49% of each big product's
results as uncacheable, and many tests' dependency closures as the whole package (#1243, with
per-product evidence). prawduct writes and reviews those tests, so the regime learns the eight
patterns. Its review blocks the two costliest ones when a change introduces them.

**Architecture:** one detector, three consumers. A static, per-language detector finds the
mechanisable shapes. It runs base-vs-head inside the review, and whole-tree for doctor/onboard and the
janitor. Reviewers judge the shapes that can't be detected statically (P3 deep reads, P5, P7, P8). Must
stay possible: #1244's measured channel. When a runner reports determinism causes, those causes join
the same check ids rather than adding a parallel vocabulary.

**Constraints (owner, 2026-11-24):**
- A newly introduced P1 or P2 is BLOCKING at the merge-boundary review. At the inner stage it is an
  observation, because it is not in the inner BLOCKING set.
- That verdict comes from the detector, not a reviewer's reading.
- It is waivable with `prawduct:allow prawduct/test-scope -- reason`, and the Critic still checks the
  reason.
- The pattern catalogue has one home, `plugin/docs/test-determinism.md`. `building.md` carries one
  pointer sentence, because it is at its token ceiling (pay in place, `authoring.md`). The discipline
  table registers a row.
- P6 is phrased by consequence: tool state that changes outcomes, such as the hypothesis example
  database. `.pytest_cache` is not named.
- Only *introduced* sites count at review. A product's existing P1 never blocks an unrelated PR.

**Detection rules (Inferred — mine, not the owner's; the boundary review may disagree):**
- **P1** (`test-scope-conftest`). A root conftest gains a module-level import of a first-party,
  non-test module.
  - A *root* conftest is a `conftest.py` with no `conftest.py` in any ancestor directory below the
    repo root.
  - *First-party* means a top-level package or module found at the repo root or under `src/`, outside
    any directory named `tests`/`test`.
  - An import under `if TYPE_CHECKING:` is exempt. One inside a module-level `try:` counts.
- **P2a** (`test-scope-autouse`). A fixture declared `autouse=True` imports a first-party module in its
  body, and either the fixture or that import is new.
- **P2b** (`test-scope-init`). A first-party package `__init__.py` imports, at module level, every one
  of its sibling submodules (and there are at least three), and before the change it did not.
  "Imports everything" is read as all of them, so an ordinary public-API re-export of a few names
  doesn't trip it.
- **P3** (`test-clock-fake`). In a conftest, or a non-`test_*` module under a test tree (fakes,
  helpers), new code calls a real clock or randomness API (the list lives in the detector). Rated
  WARNING at the boundary.
- **P4** (`test-clock-import`). In any test-tree file, a new real clock or randomness call runs at
  import time: at module level, in a decorator argument such as `parametrize`, or as a default
  argument. Rated WARNING at the boundary.
- One waiver id, `prawduct/test-scope`, covers every check this detector emits. P3 and P4 are
  WARNINGs, which a recorded accept also discharges. The waiver is for a site that stays on purpose.

**Tradeoffs accepted:**
- Python/pytest rules only in this plan. Other languages report `unchecked` and are left to the
  reviewer's reading. Revisit when a non-Python product's measured closures show the same breadth
  (Swift in arrt-player is the likely first).
- No session-start advisory. The whole-tree check runs in doctor and onboard only, because a
  per-session probe is a cost every consumer pays (memory: don't default to adding tax).
- No backlog item for either: each may never matter.

**Decisions made mid-build:** *(append one line each, naming the goal or prior choice that settled
it)*

**Level:** Medium. The goals and severities are owner-ruled. The detection rules above are my
inference, and the route into review isn't verified yet: record-lint delivers deterministic checks
into a review at stage-keyed severity, but its subject is governance records, not test code. The
cheapest step that raises the level is Chunk 01's step 0: read `critic-begin`'s `record_lint` wiring and
`critic_consolidate`'s delivery of it, then choose between a sibling module rated in the same severity
table and an extension of `record_lint`. Record the choice here.

## Verification Strategy

Beyond the unit tests, each chunk is exercised as a reviewer meets it:
- Chunk 01: run `critic-begin`/`critic-consolidate` on a scratch product repo whose branch adds a
  module-level app import to its root conftest, and read the consolidated finding. Then repeat with
  the waiver, and with an untouched pre-existing P1.
- Chunk 02: a fresh agent reads `building.md` § Test Discipline and is asked to write a fake with a
  timestamp, to see whether the pointer changes what it writes (`tests.md`: model the reader).
- Chunk 03: run `/prawduct:doctor` against a real governed checkout known to carry P1, read-only, and
  check that it names the site.

## Build Chunks

### Chunk 01: The detector and its review channel

- **Description:** a static detector for the P1, P2a, P2b, P3 and P4 shapes above, dispatched per file
  by language. Python rules are populated; any other language's changed test file is reported
  `unchecked`. `critic-begin` runs it base-vs-head over the review's subject. Consolidation records each
  result at the severity the one table assigns for the review's stage:
  - P1 and P2 are blocking at the boundary and observations at the inner stage.
  - P3 and P4 are warnings at the boundary and observations at the inner stage.
  - `unchecked` follows record-lint's rule: one step below the check's severity.

  A line carrying `prawduct:allow prawduct/test-scope -- reason`, or the line above it, suppresses the
  result through the waivers recognizer (`line_waives`). The waiver gets its row in the
  `plugin/docs/waivers.md` registry.
- **Depends on:** none
- **Deliverables:** the detector module in `plugin/lib/` (new); its delivery into the review manifest
  and consolidation; the severity entries; the `test-scope` row in `plugin/docs/waivers.md`; tests.
- **Tests:**
  - Unit tests for each rule, on fixtures from the population each rule is worst at: a test-only
    import in a root conftest (must not fire), `TYPE_CHECKING` (must not fire), a nested non-root
    conftest (must not fire for P1), a two-name re-export `__init__` (must not fire for P2b), a test
    function reading the clock (must not fire for P3), and a fake reading `datetime.now` (must fire).
  - Base-vs-head: a pre-existing P1 left untouched yields nothing.
  - At the layer the ruling is about: a fixture repo run through `critic-begin` and
    `critic-consolidate` yields a BLOCKING finding at `cumulative` and an observation at `chunk`
    (`tests.md`: pin at the layer it was reported at).
  - The waiver suppresses the result, and a waiver with no reason doesn't.
  - Each test is seen red against the mutation it pins.
- **Acceptance criteria:**
  - A boundary review of a diff that adds a module-level app import to a root conftest produces a
    BLOCKING finding naming the file, line and the waiver remedy.
  - A diff adding a fake that reads the real clock produces a WARNING.
  - The same diffs at the inner stage produce observations only.
  - A non-Python changed test file produces an `unchecked` entry, not silence.
- **Done when:**
  0. Step 0: read the `record_lint` wiring in `critic-begin` and its delivery in `critic_consolidate`,
     choose the sibling-or-extension route, and record it under Decisions made mid-build.
  1. Acceptance criteria met and the narrowest covering tests pass (the full suite is recorded once,
     before the boundary review).
  2. `/prawduct:critic` run and blocking findings resolved.
  3. Committed as `feat(test-determinism): … (Chunk 01)`.

### Chunk 02: The rule, where agents read it

- **Description:** the principle and the P1–P8 catalogue in one owner doc, with every other surface
  pointing to it.
- **Depends on:** none (written against this plan's check ids and severities; Chunk 01 doesn't change
  them)
- **Type:** doc-only
- **Deliverables:**
  - **`plugin/docs/test-determinism.md` (new):**
    - The principle: a test's result depends only on what it exercises, and is the same on any
      machine and any run.
    - Each of P1–P8 with its consequence and its one-line remedy.
    - Which patterns the review detects, and under which check id.
    - The waiver.
    - The pointer to #1244's measured channel, as a forward reference rather than a claim.
  - **`plugin/methodology/building.md` § Test Discipline:** one sentence and a pointer. Paid in place
    under the token ceiling: cut a class another file owns, not the least-defended clause.
  - **`plugin/templates/test-specifications.md`:** a short "Determinism and dependency scope" section
    that cites the doc.
  - **Critic goal prose** (wherever test quality is judged, `goals-1-3.md` / `review-protocol.md`):
    - The reviewer judges P3 deep reads, P5, P7 and P8 in changed tests, conftests, fixtures and fakes.
      Each is a WARNING at the boundary and an observation inside.
    - Severity is ranked by blast radius: process- or conftest-wide outranks a single test.
    - The detector's results are not restated (record-lint's rule).
  - **`plugin/skills/janitor/themes.md` Test Fitness:** a bullet for determinism and closure breadth
    that reads the detector's whole-tree output when Chunk 03 lands, and the runner's cause list when
    one exists.
  - **`plugin/docs/discipline.md`:** a row with an anchor phrase that `tests/test_discipline_table.py`
    checks.
- **Tests:** the existing budget and discipline-table tests stay green without raising a ceiling. A
  guard test pins the building.md pointer to the doc's real heading, with anchors derived by reading
  the file.
- **Acceptance criteria:**
  - building.md and the template state the principle and point to the P1–P8 remedies.
  - The janitor theme names the sweep.
  - The Critic prose names the judged patterns and defers to the detector for the rest.
  - The fresh-agent read in Verification Strategy changes what the agent writes.
- **Done when:**
  1. Acceptance criteria met and the methodology/budget tests pass.
  2. `/prawduct:critic` run and blocking findings resolved.
  3. Committed as `docs(test-determinism): … (Chunk 02)`.

### Chunk 03: Doctor and onboard flag the existing shapes

- **Description:**
  - `/prawduct:doctor`, and onboard's report, run Chunk 01's detector over the whole tree (current
    state, not base-vs-head) and list existing P1–P4 sites, largest blast radius first.
  - They also flag two cheap P6 shapes: hypothesis in use with its example database left in the
    checkout, and a pytest cache directory not redirected out of the tree where a caching runner is
    configured.
  - These are advice: each is a note with its remedy, never a gate.
- **Depends on:** Chunk 01
- **Type:** cumulative-final
- **Deliverables:** a whole-tree entry point on the detector; the doctor check; onboard's report line;
  tests.
- **Tests:**
  - A fixture repo carrying P1 and P3 is listed. A clean fixture lists nothing, with a control showing
    the clean fixture was scanned (corpus size in the output).
  - The doctor check is tested on its effect: follow the remedy on a fixture and the site drops out
    (`tests.md`: test a recommendation's effect).
- **Acceptance criteria:**
  - Doctor on a fixture with P1 names the conftest and line.
  - A clean repo reports zero sites over a non-empty scanned set.
  - Nothing is written into the product.
- **Done when:**
  1. Acceptance criteria met; full suite recorded with `testament run`.
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved.

## Governance Checkpoints

- After Chunk 01: confirm the detector's route into review before Chunk 03 builds a second consumer on
  it, and reconcile Chunk 02's prose with what Chunk 01 actually rates.
- Chunk 03's cumulative is the PR boundary. The boundary review judges the Inferred detection rules
  against the owner's goals.
