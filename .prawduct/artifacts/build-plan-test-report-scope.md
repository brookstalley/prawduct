---
artifact: build-plan
version: 2
scope: test-report-scope
branch: feature/test-report-scope
depends_on: []
governed_by:
  - artifact: architecture
    dispositions:
      - "the plugin writes nothing into a governed repo except its own `.prawduct/` state and the files it reconciles (`.gitignore`) → conforms: the two new ignore entries land in the managed `GITIGNORE_ENTRIES` section, which is the declared seam; nothing else in a consumer repo is written by the plugin, and the runner config that emits the report is the product's own file, edited by the product"
      - "prawduct is written in Python and must never be specific to Python → conforms: the report is JUnit XML (already the ingest format) and the scope record is plain JSON at a path derived by string suffix; the reader branches on no language, suffix or ecosystem. The pytest wiring is one worked example beside four other-ecosystem sketches, and it lives in this repo's own `tests/`, not in the plugin"
      - "prawduct guides and reviews; it never implements — a best practice enters as a *requirement* → conforms, and this is the load-bearing one: the two properties enter as a REQUIREMENT in `building.md` plus a contract prawduct READS. The plugin installs no runner config and no conftest anywhere. This repo implements the requirement in its own `pyproject.toml`/`tests/conftest.py` under the norm's own scope note — prawduct-the-product is a product like any other"
      - "goals and verification bind; prescribed method is advice → conforms: the contract states what must be true (a report from every run; the invocation's scope recorded beside it) and how it is checked (the sidecar the recorder reads). The per-ecosystem mapping is explicitly labelled advice"
      - "every fact has one home → conforms: the sidecar schema, the conventional path and the reader's rules are stated once in new `plugin/docs/test-report-contract.md`; `building.md` and the CLI's refusals point at it"
      - "an independent reviewer never mutates the session it reviews → inapplicable because nothing here runs inside a review or touches the review data plane; the reader is invoked by `test-evidence record`, which no reviewer calls"
      - "authority fails closed; advice fails soft → conforms, and it is the rule that shaped the error posture: every ambiguous record (unreadable, malformed, schema-ahead, mismatched) refuses because this feeds an evidence record the freshness gates read, while the producer's own write failure degrades to a stderr NOTE, because a producer that cannot write must not take the suite down with it"
      - "local-first: governance coordination is process-spawn + atomic file writes + the git object database, no network and no daemon → conforms: the record is one atomically-written local file read by one process; nothing here opens a socket or adds a dependency"
  - artifact: api-contract
    dispositions:
      - "additive-first evolution; existing flag names and exit-code meanings are never repurposed → conforms: `--from-junit` keeps its name, its arity and its exit codes. The new refusal is reachable only when a scope record exists beside the report, which no repo has today, so every existing caller's behaviour is unchanged by construction"
      - "exit codes are the contract → conforms: every new refusal exits 2, the code this command already uses for its validation refusals; no new code is introduced"
      - "persisted data that outlives a plugin version is independently schema-versioned with forward-incompatibility detection → conforms: the sidecar carries `v: 1`, and a `v` the reader does not know is a loud refusal rather than a silent skip"
      - "whole-surface semantic versioning; the internal CLI subcommand surface carries no per-subcommand version → inapplicable because no subcommand is added or removed: `test-evidence record` keeps its name, flags and exit codes"
  - artifact: data-model
    dispositions:
      - "a record written by a newer schema than the reader is a loud block, never silently dropped → conforms: an unknown `v` refuses and says so; this is the same posture as the fact store's schema-ahead block, applied to a different artifact"
      - "two stores, two lifetimes — shared committed answers vs per-clone gitignored caches → conforms: the report and its scope record are per-clone run output, gitignored through the managed section, and nothing about them is committed"
      - "governance verdicts are computed from the fact ledger, never from mutable model-written state → inapplicable because this plan writes no fact and renders no verdict; it decides whether an ingest is ACCEPTED, and a refusal writes nothing"
      - "facts are immutable and append-only; a state change is a new fact → inapplicable because the scope record is not a fact and never enters the ledger; it is run output, rewritten by the next run by design"
      - "derived views are disposable and never authoritative → conforms: the record is derived from an invocation and is disposable (deleted at the session boundary, regenerated by the next run); no gate reads it to reach a verdict — it can only REFUSE to let a record be written"
      - "a governance document reaches a terminal state and is never deleted → inapplicable because the report and its record are run output rather than governance documents, which is why deleting them at the boundary is correct here and would not be for an artifact"
      - "every backlog issue conforms to the issue standard's title rules → inapplicable because this plan writes no backlog item; #825's close is bookkeeping at merge"
      - "`backlog_service_repo` selects the authoritative backlog store → inapplicable because nothing here reads a backlog store"
  - artifact: observability-strategy
    dispositions:
      - "stable severity-prefix vocabulary, stdout for the answer and stderr for diagnostics → conforms: the refusals print `error: …` on stderr exactly as this command's existing refusals do, and the producer's degraded path uses `NOTE:`"
      - "the governance ledger has a single writer; agents never hand-author it → inapplicable because nothing here writes the ledger"
      - "text emitted into a governed product names no prawduct-internal identifier → conforms: the refusals name commands and file paths a consumer has (`test-evidence record`, `docs/test-report-contract.md`), no review ids and no internal symbols"
partition: serial — one chunk; the mechanism is derived from the contract stated in the same chunk
last_validated: 2026-09-18
---

## Requirements Confidence

**Level:** High

**Why:** The requirement came from the owner in the previous session and is recorded verbatim in
the handoff: put the machine-readable report into the runner's default arguments so it is a side
effect of *every* run, and record the invocation's scope beside it so ingesting a narrow run cannot
launder a subset as suite evidence. Both halves were re-derived here against the code —
`cmd_test_evidence`'s `--from-junit` path trusts the operator's assertion that the report is the
declared command's full output (`plugin/bin/prawduct-hook:3925-3934`), and pytest's config surface
was probed directly (below) rather than recalled.

**Open assumptions / unknowns:**

- `[ASSUMPTION: the conventional report path is `.prawduct/.test-report.xml`, fixed by prawduct rather than declared per repo in `project-state.yaml` | MED impact | user can correct]` A convention needs no new key, works in any ecosystem, and lets prose name the exact recovery command; a declared key would additionally let `test-status` point at the report, which is deferred here. A repo whose runner cannot write there simply passes its own path to `--from-junit`, as today.
- `[ASSUMPTION: a run that CAN stop early (`-x` / `--maxfail`) is recorded as `partial` even when it in fact completed | LOW impact | user can override]` The alternative is having the recorder compare the report's leaf count against a selected-count in the sidecar, which is exact but introduces a false-refusal class (parametrization, deselection, xdist aggregation) on first release. Deliberately deferred; the schema is additive.

**What would raise confidence:** N/A — both assumptions are recorded above and neither blocks.

## Verify-api: pytest's configuration surface (the chunk's **Foreign API:** pytest)

Probed on 2026-09-18 with a scratch project rather than read from documentation, because the
classifier is built on these exact attributes:

- `config.option.xmlpath` carries the `--junit-xml` value and is readable at `pytest_configure`;
  a command-line `--junit-xml` **overrides** the `addopts` one (verified: with both set, only the
  command-line path was written). That is what keeps the recorder's own temp-file run working
  unchanged after `addopts` gains the conventional path.
- `config.args` is the resolved selection (equal to `testpaths` when no path argument is given);
  `-k` lands in `config.option.keyword`, `-m` in `markexpr`, `-x` in `maxfail`, and a node id
  appears in `config.args` with a `::`.
- `hasattr(config, "workerinput")` distinguishes an xdist worker from the controller.
- `session.shouldstop` reads `False` at `pytest_sessionfinish` even for a run that stopped at
  `-x`, so it is **not** a usable truncation signal — `maxfail` being set is what the classifier
  keys on.

## Status

- [x] Chunk 01: The contract, and the mechanism derived from it

Context: built 2026-09-18 on `feature/test-report-scope` (cut from `develop` at `ded04e89`).
Three commits: the contract, the mechanism, then the review's fixes. One `cumulative` (coordinator
roster — `plugin/bin/*hook*` is a declared risk surface) returning 16 findings, then two
`verify-resolutions` rounds; 14 fixed, 3 accepted on the record, 0 outstanding. The suite is green
and recorded (7272 passed / 0 failed), tree-valid for the reviewed tree.

Three of the review's warnings were design gaps rather than records nits, and all three are the
same shape — *the warrant is narrower than the thing it licenses*: a refusal written for one of six
causes, an ingest-only guard whose warrant did not cover the interpreter-fallback run path, and a
"never committed" promise resting on ignore patterns that anchor to the repo root while the runner
resolves the report path against the invocation directory. Each was fixed by moving the CODE to
meet the words rather than softening the words.

Next: nothing within this plan. `/prawduct:pr` when the owner asks, which is also where #825's
close belongs — this repo's Issues backend defers that to the merge, and the dissolved-not-built
reasoning is in Done-when step 4 below.

Planned as two chunks (contract, then mechanism) and **merged into one before any code
was written**. The split would have bought a `chunk`-mode review of prose whose correctness is a
claim about code the same branch ships — a reviewer reading the contract without the reader it
specifies is grading intent, and would read both again in the boundary `cumulative` regardless.
What the split was protecting (a wrong schema that code then derives from) is instead the
governance checkpoint below, run before the mechanism is written. The two halves survive as the
deliverable groups A and B.

## Build Chunks

### Chunk 01: The contract, and the mechanism derived from it

- **Description:** State the language-agnostic requirement, then implement it on both sides, in
  that order — so the implementation is derived from the contract rather than described by it
  afterwards. Two properties: **(1)** the machine-readable report is emitted by *every* run,
  configured in the runner's own default-arguments file rather than typed at the call site — so no
  run is ever unrecordable; and **(2)** the invocation's *scope* is recorded beside the report by
  the runner's pre/post-run hook — so the recorder can tell a whole-suite run from a scoped subset.
  The second is what makes the first safe: once a report is always sitting at a known path, a
  `-k`-narrowed run leaves one that looks exactly like the suite's, and `--from-junit` would record
  it as the suite's evidence. That is the "laundering a scoped subset" trap #680 names, and it is a
  false green rather than a lost ten minutes.

- **Depends on:** none

- **Deliverables (group A — the contract):**
  - new `plugin/docs/test-report-contract.md` — the one home for: the conventional report path
    (`.prawduct/.test-report.xml`) and its scope record (`<report>.scope.json`), the v1 schema and
    every field's reader, the reader's rules (absent → today's posture; malformed, unknown `v`,
    wrong `report`, or `scope: partial` → refuse), and the per-ecosystem mapping table (pytest
    `addopts` + `conftest.py`; .NET `.runsettings` + an assembly fixture; Go a test target +
    `TestMain`; Jest `reporters` + `globalSetup`; CTest `CTestConfig` + a fixture test) labelled as
    advice under the goals-bind norm
  - `plugin/methodology/building.md` § Test Discipline — the two properties, ~5 lines, pointing at
    the contract doc for the schema. The file sits one token under its ceiling, so this is paid in
    place from genuine duplication or declared as a raise with its reason; never trimmed to fit
  - `tests/test_v5_methodology.py` — the ceiling reading and ratchet/raise, in the same commit as
    the prose (an unratcheted slack is a loan the next edit collects)
  - `tests/test_test_report_contract.py` (new) — the contract doc states each field the reader
    consumes, and names both refusal directions

- **Deliverables (group B — the mechanism):** the consumer is
  `test-evidence record --from-junit`, which today trusts that the report it is handed covers the
  declared suite; it now reads the scope record beside each report and refuses a narrowed or
  truncated one. The producer is this repo, as the contract's worked example. Consumer before
  producer, so nothing is produced that nothing reads.
  - new `plugin/lib/report_scope.py` — `read_scope_record(report_path)` returning a
    `ScopeVerdict(ok, reason, cause)`; pure, no I/O beyond reading one file, no language dispatch.
    **Named `report_scope`, not `test_report`** (the first draft of this line): a module matching
    `test_*.py` is a test file to every tool that walks the tree, which this repo's own
    `tests/preferences/test_test_location.py` caught on the first full suite run
  - `plugin/bin/prawduct-hook` — `cmd_test_evidence` consults it once per `--from-junit` report
    before parsing, refusing with exit 2 and a message that names the honest remedies (run the
    declared command through the recorder; ingest a report from a full run) and says that editing
    or deleting the scope record is not one; and the run path unlinks `<temp>.scope.json` beside
    the temp report it already unlinks
  - `plugin/lib/core.py` — `.prawduct/.test-report.xml` and `.prawduct/.test-report.xml.scope.json`
    join `GITIGNORE_ENTRIES`, which is how the convention reaches every governed repo
  - `.gitignore` — this repo's own copy of those two entries
  - `pyproject.toml` — the pytest `addopts` gain the conventional `--junit-xml` report path
    (`plugin/docs/test-report-contract.md` names it), with the comment stating why: the report is a
    side effect of every run, and the declared command's own flag still overrides it
  - `tests/conftest.py` — the classifier and the two hooks
  - `.prawduct/change-log.md` — one entry, `scope=test-report-scope`

- **Tests:**
  1. The reader, per rule: absent → proceed; `scope: full` → proceed; `scope: partial` → refuse,
     with `why` and `at` in the message; malformed JSON → refuse; `v: 2` → refuse naming the
     schema; `report:` naming a different file → refuse. Each red-verified by mutating the
     rule it pins, not by mutating the fixture
  2. The end-to-end refusal at the CLI layer, where the defect would be reported — a real
     `--from-junit` invocation against a report with a `partial` record beside it, asserting
     exit 2 and that **nothing was written** to `.test-evidence.json` (the prior record survives
     untouched, which is the reason for refusing rather than recording degraded)
  3. The classifier, per narrowing signal: `-k`, `-m`, a node id, a subset path, `-x`, and the
     default invocation → `full`
  4. One integration test that runs real pytest in a subprocess against a copy of this repo's
     own `tests/conftest.py`, asserting the record exists and reads `full` for a plain run and
     `partial` for a `-k` run. The copy is the real artifact, so the wiring cannot drift from a
     replica; the test is what proves the hooks are wired at all
  5. The managed-gitignore contract test picks up the two new entries

- **Acceptance criteria:**
  - A report produced by a narrowed run cannot be recorded as suite evidence, and the refusal
    names a remedy that reaches the state
  - A repo with no scope record behaves exactly as it does today, asserted rather than assumed
  - A plain `pytest` run in this repo leaves a report and a `full` scope record without anyone
    typing a flag; the recorder's own declared-command run is unaffected (its `--junit-xml`
    overrides `addopts`, verified in the probe above) and leaves no temp litter.
    **How this half was actually verified, because a bare full run costs six minutes and this
    change exists to stop spending those:** the producer was observed firing under this repo's
    REAL declared command (the configure-time record sat beside the recorder's temp report during
    the 04:40Z run, under `-n 5`), the temp record was gone afterwards (the unlink works), and the
    *classification* of that exact invocation shape — `args=["tests/"]` against
    `testpaths=["tests"]`, exit 1 — is pinned by unit cases plus a scratch project mirroring the
    config under real pytest. The one thing not observed end to end is this repo's own bare run
    printing `full`; it is decomposed rather than assumed, and the decomposition is stated here
    rather than hidden behind the word "verified".
  - The declared suite passes, recorded through `prawduct-hook test-evidence record`

- **Foreign API:** pytest — the `config.option` / `pytest_configure` / `pytest_sessionfinish`
  surface the producer is built on. Verified by probe rather than from documentation; the findings
  are § Verify-api above, and one of them (`session.shouldstop` reads `False` after an `-x` stop)
  contradicted the classifier's first design.

- **Type:** cumulative-final
  <!-- `plugin/bin/*hook*` is a declared risk surface, so the short-plan review
       deferral does not apply: the boundary review is the coordinator roster,
       and the one `cumulative` covers the whole branch. -->

- **Done when:**
  0. `verify-api` on pytest's config/hook surface — **done**, § Verify-api above
  1. Acceptance criteria met and the declared suite passes
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status
  4. `#825` reconciled: its problem is dissolved rather than its proposed mechanism built — a run
     outside the recorder no longer needs stopping because it is no longer lost — and that
     reasoning is recorded on the item, not inferred by the next reader

## Governance Checkpoints

**Before the mechanism is written.** The one place this plan can go wrong cheaply is the schema:
once a producer exists in another repo, a field's meaning is expensive to change. The check is the
one the planning guide names for a persisted format — every field has a consumer query behind it
(`scope` answers "was this narrowed", `why` answers "what narrowed it", `report` answers "is this
record about the file I was handed", `at` answers "which run wrote it", `v` answers "can this
reader read it") — and any field without one is cut before the mechanism depends on it.

**Commit & PR cadence:** the contract commits first and the mechanism second, so the diff reads in
the order it was derived; the one `cumulative` after the last commit is the chunk's review and the
PR gate's evidence.

**What I would do differently, stated before the chunk is built.** Two things.

*First, the piece I cut.* A declared `test_report_path:` in `project-state.yaml` would let
`test-status`'s `stale:` line and the recorder's refusals point at the exact report from the run
that just happened — which is the difference between guidance that fires and guidance an agent has
to remember. I cut it because it adds a key to the template, a `/prawduct:doctor` check and a
migration surface for a benefit the fixed convention already delivers most of, and because the
convention works for a repo that has never heard of the key. If the recovery loop still misses in
practice, that is the next thing to add, and the sidecar already carries enough for it.

*Second, the risk I am accepting.* The `partial` refusal is a gate in front of an *agent*, and an
agent's cheapest route past it is `rm` on the scope record — after which the trusting path returns.
Nothing structural closes that, because absence must stay permissive for every repo that has not
wired a producer. The refusal says so in words, which is the weakest form of a rule; the honest
statement is that this raises the cost of laundering from "type nothing" to "delete a file you were
just told not to delete", and does not make it impossible.
