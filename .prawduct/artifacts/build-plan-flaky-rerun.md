---
artifact: build-plan
version: 2
scope: flaky-rerun
branch: feature/1087-flaky-rerun
base: develop
working-branches: []
last_validated: 2026-10-26
depends_on:
  - brookstalley/prawduct#1087
governed_by:
  - .prawduct/artifacts/architecture.md
  - .prawduct/artifacts/api-contract.md
  - .prawduct/artifacts/data-model.md
  - .prawduct/artifacts/nonfunctional-requirements.md
  - .prawduct/artifacts/security-model.md
partition: serial — every chunk edits `cmd_test_evidence` in `plugin/bin/prawduct-hook` and the record's `flaky` field
---

## Goals

**Response taken:** Ask, in one batch. The owner said "let's land 1087" (2026-10-26). #1087 sits
at `stage:design`. Three forks were put to the owner, who chose the recommended option on each
(2026-10-26):
- a **per-command rerun template**, not pytest-only and not a whole-command rerun;
- **`flaky_policy` defaults to `warn`**;
- **one branch, chunked**, with one cumulative review and one PR.

**Product:** In a governed repo, one load-induced failure of a timing-bound test should cost
that test's rerun, not a whole declared suite (#1087 measured an 18-minute suite, with two of six
boundary runs lost in one session). A retry must not hide a race the branch introduced. Tests stay
contracts: a test that fails on every attempt stays red, and nothing is weakened.

**Architecture:**
- The flake record is a field on the existing evidence record and the `test-run` fact. It is not
  a new store.
- Diff-judging happens at record time, against the same base and changed-file set the coverage
  verifier scores (`coverage._coverage_resolve_base` / `_coverage_changed_files`). The record is
  tree-bound, so a moved tree means a re-run, and record-time judgment cannot go stale.
- `flaky` never moves a verdict by being read. Like `failed_tests`, it stays out of
  `_EVIDENCE_SCHEMA`, and readers ignore a malformed value. Only `block` moves a verdict, and it
  does that at record time by leaving the test counted as failed.

**Constraints:**
- Additive only (api-contract Direction): one new flag, new optional `project-state.yaml` keys
  and a new optional record/fact field. No existing flag, exit code or key changes meaning.
- The record must not grow without bound: `flaky` is capped like `failed_tests`.
- A rerun must run on the same tree. The existing pre/post tree bracket in `cmd_test_evidence`
  has to enclose the reruns too, or a rerun after an edit could vouch for a tree the suite never
  met.

**Verified (foreign formats; verify-api done 2026-10-26):**
- Surefire's report XSD (3.5.6) defines `<flakyFailure>`/`<flakyError>` (the test failed, then
  passed on a rerun, so there is no `<failure>`/`<error>`) and `<rerunFailure>`/`<rerunError>`.
  Those last two accompany a final `<failure>`/`<error>`, so the test failed every time and
  already counts as failed. Each carries `message`/`type` and a `<stackTrace>` child.
- **Correction to #1087:** pytest-rerunfailures does *not* mark flakes in JUnit. It sets
  `report.outcome = "rerun"`, and pytest's `junitxml.pytest_runtest_logreport` only handles
  passed/failed/skipped, so the XML shows a plain pass. Its flakes are invisible to `--from-junit`.
  Part 2 therefore covers Surefire-convention reporters, not pytest-rerunfailures.
- `testament run` passes everything after its own flags to pytest as a selection, so a rerun
  template can hand it node ids.

**Tradeoffs accepted:**
- *No built-in rerun for declared commands.* Appending ids to a command that already names a
  selection (`pytest tests/ -m "…"`) would rerun the whole selection. So a declared command
  reruns only when it has an explicit template. The fallback pytest path, whose argv the hook
  builds itself, gets one built in. This departs from the option's wording ("pytest/testament
  get a built-in default"): that default cannot be made safe. Revisit if a runner exposes a
  selection-replacing flag.
- *"Touched" judges the test's own file, not the code it covers.* #1087 also asks whether the
  branch "touched the covered code". The only coverage signal is the Python-only symbol-grep in
  `bin/test-reference-verify`, which maps changed files to tests as a whole, not per test. A
  flake in an unchanged test file that exercises changed code is accepted and noted, not warned.
  Backlog item to file at Chunk 03: judge by covered code where `coverage_level: executed`
  evidence exists.
- *Unknown file reads as touched.* A test whose file cannot be resolved (no `file` attribute, a
  classname that maps to no file) gets `touched: null`, and the policy treats it as touched. An
  unknown case gets the strict policy, never the lenient one (hook-surface rule on fallback
  direction).

**[DECISION: the recorder reruns failed tests itself, although architecture.md says prawduct never
re-implements what product tooling does | a runner's own retry (pytest-rerunfailures) is
invisible in its JUnit, so the gate cannot see a flake and cannot judge it against the diff, which
is the race-hiding #1087 exists to prevent. The recorder's rerun is a recording policy over the
product's own declared command (it runs the product's tooling and implements no test execution),
and a runner that reports its own flakes is read instead (part 2) | owner can veto]**

**Inferences (flagged for the boundary review):**
- *Retry ceiling:* `--rerun-failed` defaults to 1 retry. `=N` allows up to 5 (beyond that, the
  suite is not flaky but broken). The retry is skipped when more than 5 tests fail, since that is
  a broken run and not a flake. Both limits are module constants.
- *Rerun ids:* the template gets `{pytest_node_ids}` (one argv token per id, resolved from the
  JUnit `file` attribute or the dotted classname to `path.py::Class::name`; ids that cannot be
  resolved are not retried and stay red) and `{junit_xml}` (required, as for `test_command`).
  Rerun results are matched to the original failures by JUnit id (`classname::name`), the same id
  `failed_tests` already uses.
- *Config shape:* `test_rerun_command:` pairs with `test_command:`. `test_rerun_commands:` is a
  block list aligned by position with `test_commands:`, where an entry `none` means no rerun for
  that command, and any length mismatch is refused. A mapping form would need the YAML reader
  extended, and the reader refuses nested mappings on purpose.
- *`first_failure`:* the failure element's `message` attribute, else the first line of its text,
  truncated to 300 characters. The full trace stays in the runner's own output.
- *`--rerun-failed`* applies to live runs only. With `--from-junit`, `--from-counts` or
  `--no-rerun` it is refused (exit 2): there is no process to rerun.

**Decisions made mid-build:** (none yet)

**Level:** Medium-High. The recorder is well understood, and the foreign formats are verified.
What would raise it: Chunk 02 run once on this repo with a forced failure that passes on rerun.

## Persisted format: the `flaky` field

Its consumers' questions, which are its requirements:
1. `test-status` and the Critic: which tests passed only on retry, and did this branch touch
   any of them? (Critic: WARNING under `warn`.)
2. The handoff and the PR body: which flakes should reach the backlog?
3. `run_refusal`: never consulted. Only `block` moves a verdict, and it does so at record time.
4. Another worktree reusing a `test-run` fact: the same flake list, so a reused green carries
   its flakes.

Shape, capped at 20 entries, sorted by id: `{"id", "first_failure", "attempts", "source":
"rerun"|"junit", "file"?, "touched": true|false|null}`. `attempts` counts the failures before the
pass.

## Governing norms

- architecture "Authority fails closed; advice fails soft": **conforms**. `block` leaves the test
  failing; an unknown file reads as touched; `warn` is advice.
- architecture "Never specific to Python": **conforms**. Rerun templates are per command, and
  the `{pytest_node_ids}` placeholder is one ecosystem's opt-in. The JUnit flake ingest serves
  any runner that reports flakes. A command with neither is not retried and says so.
- architecture "never re-implements product tooling": **[DECISION]** above.
- architecture "Goals and verification bind; method is advice": **conforms**.
- architecture "Every fact has one home": **conforms**. The changed-file set comes from
  `coverage`, and the JUnit id from `_junit_case_id`.
- architecture "writes nothing but `.prawduct/` …": **conforms**. Writes go only to the record
  and the store.
- api-contract "Additive-first evolution": **conforms**. A new flag and new optional keys; exit
  codes unchanged (0 when the record is green, 1 when red, 2 usage).
- data-model "Facts immutable, append-only": **conforms**. `flaky` rides the fact appended for
  the run.
- data-model "newer-schema fact surfaced loud": **inapplicable**. An optional body field that
  older readers ignore is not a schema bump. The Chunk 01 tests confirm the store accepts it.
- nonfunctional "Proportionality … emits its yield observably": **conforms**. Every flake is
  printed, stored, and carried to the handoff and the PR body.
- nonfunctional "Review wall-clock", "stage-keyed rigor": **conforms**. The new Critic WARNING is
  boundary-stage only; at the inner stage it is an observation.
- security-model "Untrusted governance state is data": **conforms**. `first_failure` text is
  test output and is printed as data, truncated.
- Other norms (reviewer non-mutation, network surfaces, destructive-op approval, backlog store):
  **inapplicable**. Nothing here sends, deletes or reviews.

## Build Chunks

### Chunk 01: Flake field and JUnit flake ingest

- **Description:** Read Surefire-convention flake elements in every JUnit the recorder parses,
  record them as `flaky`, and print them on the record line and in `test-status`.
- **Depends on:** none
- **Deliverables:**
  - `plugin/bin/prawduct-hook` `cmd_test_evidence`: a leaf with `flakyFailure`/`flakyError` and
    no `failure`/`error` is passed with a flake; collect `flaky` entries (`source: "junit"`,
    `attempts` = number of flaky elements); write the capped field to the record and the
    `test-run` fact; print a `flaky:` line.
  - `plugin/lib/gates.py`: one `name_flaky_tests` formatter (tolerant of malformed values),
    used by the record line and by `test_status`, which prints one line per flake after the
    verdict and never changes the exit code.
- **Tests:** `tests/test_test_evidence_flaky.py` (new):
  - flakyFailure-only leaf → passed, `flaky` entry carries message text;
  - rerunFailure + failure → failed, no `flaky` entry;
  - flakyError counts the same as flakyFailure;
  - no flake elements → no `flaky` key at all (absence, never `[]`);
  - cap at 20; malformed `flaky` in a record → `test-status` exit unchanged, no traceback;
  - `test-run` fact carries `flaky`.
- **Acceptance criteria:** tests pass. An existing record without the key reads exactly as
  before.
- **Done when:**
  1. Tests pass.
  2. Committed.

### Chunk 02: `--rerun-failed[=N]`

- **Description:** After a live run, rerun only the failed tests on the same tree through each
  command's rerun template, and record a green that carries the flakes, or a red that stays red.
- **Depends on:** Chunk 01
- **Deliverables:**
  - `plugin/bin/prawduct-hook` `cmd_test_evidence`: parse `--rerun-failed[=N]`; read
    `test_rerun_command:` / `test_rerun_commands:` (validated before any suite runs: shlex-split,
    `{junit_xml}` and `{pytest_node_ids}` required, length alignment, `none`); group failures by
    command; resolve node ids; rerun up to N times inside the tree bracket; update counts,
    `failed_tests` and `flaky` (`source: "rerun"`); treat a command whose every failure flaked
    green as exit 0 for both the exit-status check and the record's exit code. Print why any
    failure was not retried (no template, unresolvable id, over the threshold).
  - The fallback pytest path builds its own rerun argv.
- **Tests:** in `tests/test_test_evidence_flaky.py`, with a fake declared command (a script
  that writes JUnit from an attempt counter):
  - one failure that passes on rerun → exit 0, `failed: 0`, one flake;
  - one that fails every attempt → exit 1, still in `failed_tests`, no flake;
  - more than 5 failures → no rerun, and it says so;
  - a command with no template / `none` → not retried, named;
  - an unresolvable classname → not retried;
  - `test_rerun_commands` length mismatch, or a missing placeholder → exit 2 before running;
  - `--rerun-failed` with `--from-junit` → exit 2;
  - a tree edit during the rerun → no `evidence_tree`;
  - node-id resolution: `tests.test_x.TestY` + `test_z[a]` → `tests/test_x.py::TestY::test_z[a]`.
- **Acceptance criteria:** tests pass. On this repo, a forced flaky test run through a temporary
  `test_rerun_command` records green with one flake (product verification).
- **Done when:**
  1. Tests pass.
  2. Committed.

### Chunk 03: Judge flakes against the branch, `flaky_policy`

- **Description:** Classify each flake as touched or not by the branch's changed files, and apply
  `flaky_policy: accept | warn | block` (default `warn`).
- **Depends on:** Chunk 02
- **Deliverables:**
  - `plugin/bin/prawduct-hook`: `touched` on each entry from `coverage._coverage_changed_files`
    at `coverage._coverage_resolve_base`, with `null` when the file is unknown or the diff
    cannot run. Under `block`, a touched or unknown flake is not credited: it stays in `failed`
    and `failed_tests`, and the entry records `"blocked": true`.
  - `flaky_policy` reader: an unknown value is refused (exit 2), like other enum keys.
  - `plugin/lib/gates.py` `test_status`: mark touched flakes `(touched by this branch)`.
  - `plugin/skills/critic/goals-1-3.md` and `review-protocol.md`: under `warn`, a touched or
    unknown flake in the evidence → WARNING "a test this branch touched passed only on retry" at
    the boundary, an observation at the inner stage. Under `accept`, nothing.
  - `plugin/docs/project-state-keys.md`: `flaky_policy`, `test_rerun_command(s)`.
  - File the deferred covered-code backlog item.
- **Tests:** touched / untouched / unknown classification; `block` keeps a touched flake red
  and credits an untouched one; an invalid policy → exit 2; a prose pin that the Critic rule
  names `flaky_policy`.
- **Done when:**
  1. Tests pass.
  2. Committed.

### Chunk 04: Surfacing and the change record

- **Description:** Carry flakes into the session handoff and the PR payload and body, and write
  the change fragment.
- **Depends on:** Chunk 03
- **Deliverables:**
  - `plugin/lib/briefing.py` `render_session_handoff`: a flakes line from the record.
  - `plugin/lib/pr_payload.py` `_section_test_evidence`: the flake lines.
  - `plugin/skills/pr/SKILL.md`: the PR body names each flake, as a backlog candidate.
  - `plugin/docs/test-report-contract.md` and `plugin/methodology/building.md` "Verify": one
    mention each of `--rerun-failed` and flake ingest, with no restated mechanics.
  - new `.prawduct/changes/flaky-rerun.md`.
- **Type:** cumulative-final
- **Done when:**
  1. Tests pass (declared suite recorded).
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved.
