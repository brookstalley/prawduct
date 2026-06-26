<!-- Build Plan — kill the test-evidence double-run at its source (retired
     "record after commit" habit) + give non-JUnit (embedded/bespoke) toolchains
     a first-class on-ramp. Originating bug: COV-3R9K (upstream report from
     scriob). One PR for the whole bundle (review economy — P0). -->
---
artifact: build-plan
version: 2
scope: test-evidence-single-run
depends_on: []
last_validated: null
---

## Requirements Confidence

**Level:** High

**Why:** The root cause was verified by a multi-agent investigation, not recalled:
a consumer map of every `.test-evidence.json` / `changes_referenced` reader, an
empirical `git diff` trace in throwaway repos, the TST-4K2P / TST-7M3K history,
and three adversarial verifiers. The reported double-run is **not** gate-forced —
freshness is session-scoped (`lib/gates.py:tests_are_current`: `timestamp >=
.session-start` AND `failed==0`, with **no** `git_sha` / HEAD / tree-hash since
TST-4K2P), and `changes_referenced` is produced by `git diff --name-only <base>`
(base→**working tree**, content-based), commit-invariant on a real base branch.
The double-run is driven by a **retired** "record AFTER the final commit / SHA
must equal HEAD" habit (declared obsolete at `learnings.md:270-272`). The user
chose the scope below.

**Open assumptions / unknowns:**
- [ASSUMPTION: `--from-counts` takes `passed=N failed=M skipped=K [duration=S]`
  key=value tokens; `passed`+`failed` required, `skipped`/`duration` default 0 |
  LOW impact | user can override the surface]
- [ASSUMPTION: `--no-rerun` reuses the existing `.test-evidence.json` counts and
  re-overlays the F4a half against the current tree (no suite run) — an
  unverifiable operator assertion, identical in trust posture to `--from-junit` |
  LOW impact | user can override]
- [ASSUMPTION: the HEAD~1 advisory is stderr-only and fires in the **recording
  flow** (the recorder + the standalone verifier), NOT in the shared
  `_resolve_base_branch` resolver — to avoid noise on the doc-only / change-log /
  stop gates that also resolve a base but for which HEAD~1 is not an actionable
  problem | LOW impact | user can override the placement]
- [ASSUMPTION: the **Python-only coverage floor** (`bin/test-reference-verify`
  symbol-grep) is OUT of scope here — filed as a separate backlog item per the
  user's "add `--from-counts`, backlog the floor" choice]

**Constraints a build MUST honor (deliberate prior decisions — do not reverse):**
- NO content-/tree-hash freshness, and NO `git_sha`/HEAD/commit-position field.
  Both were removed pre-v1.4 (chronic false positives) and TST-4K2P explicitly
  rejected re-adding them. Freshness stays **session-scoped** (timestamp).
- Preserve `--from-junit` single-run economy and the conflicting-source guards
  (an ingest mode rejects `test_command:` / trailing pytest args / a second
  source).
- Preserve the CRT-7M2D doc-only allowance and the TST-2H9P loud-fail.

## Survey findings that shaped this plan

1. **No consumer requires post-commit evidence.** Every reader (freshness gate,
   schema validator, `verify-coverage`, Critic/PR protocols) keys off the
   session-scoped `test-status` exit code or the content-based changed-file set —
   none read a commit/SHA field (the record carries none). The real covers-HEAD
   gate operates on the **Critic-findings** record (`commit_reviewed`), not on
   test-evidence; the stale habit most plausibly bled over from there.
2. **`--from-junit` already ends the build-then-record double-run** (TST-7M3K) —
   the residual is methodology/discoverability + the non-JUnit gap.
3. **Two real coverage-half shifts survive (adversarial):** on a *fixed* base, a
   **rename** (`{old,new}`→`{new}`, harmless shrink) and a **force-added
   gitignored path** (`{}`→`{path}`, can block `verify_coverage` when
   `coverage_required:true`, default off). These bite the F4a `changes_referenced`
   half, not the run/freshness half — `--no-rerun` is the sanctioned cheap
   refresh.
4. **HEAD~1 fallback base genuinely shifts** even on a literal no-op commit (it is
   a moving ref) — only on repos with no `origin/main`/`main`/`base_branch:`.
   Advisory, not a behavior change.

## Status

- [ ] Chunk 01: `--from-counts` — generic non-JUnit result on-ramp
- [ ] Chunk 02: `--no-rerun` restamp + HEAD~1 fallback-base advisory
- [ ] Chunk 03: mechanism-neutral methodology + backlog hygiene (cumulative-final)
Context: Plan created (feature/test-evidence-single-run, off develop). Building
Chunk 01 first. Backlog COV-3R9K is the originating item (reframe + file the
coverage-floor residual in Chunk 03).

## Scaffolding

N/A — modifies existing framework machinery (`bin/prawduct-hook`,
`bin/test-reference-verify`, `lib/coverage.py`, `methodology/building.md`) in an
established repo. Test runner (pytest-xdist), tests dir, and structure already
exist. No new dependencies.

### Verification Strategy

Beyond the unit suite: exercise the **repo-local** hook directly
(`python3 bin/prawduct-hook test-evidence record --from-counts …`, `… --no-rerun`)
— the bare `prawduct-hook` on PATH is the released plugin cache and shows stale
behavior. Confirm `test-status` still reports `current` after each ingest mode.

## Build Chunks

### Chunk 01: `--from-counts` — generic non-JUnit result on-ramp

- **Description:** Add `test-evidence record --from-counts passed=N failed=M
  skipped=K [duration=S]` so any toolchain (embedded HIL, custom harness, a runner
  that can't emit JUnit XML) records evidence **without** faking a JUnit report.
  This is the agnosticism keystone: the minimum viable test result is pass/fail/
  skip counts, and forcing that through JUnit XML *is* the coupling. Default
  behavior (run the suite) and `--from-junit` are unchanged.
- **Depends on:** none
- **Artifacts consumed:** this plan; `bin/prawduct-hook:cmd_test_evidence`
- **Deliverables:**
  - `bin/prawduct-hook` — in `cmd_test_evidence`: parse `--from-counts` and its
    `key=value` tokens (new module-level `_parse_evidence_counts` helper). When
    present, set `passed/failed/skipped/duration` directly, `proc=None`,
    `command` = a self-documenting `--from-counts …` string; skip the XML path.
    Reject combining `--from-counts` with `--from-junit` (two sources), with
    extra pytest args, or with a declared `test_command:` — mirroring the existing
    `--from-junit` guards. Unknown/duplicate keys, non-integer counts, negative
    values, and missing `passed`/`failed` → clean exit 2 with a usage message.
    Update the handler docstring + the `record` usage line + the top-level
    usage string (`bin/prawduct-hook` ~line 2402).
  - The F4a overlay still runs (best-effort); a non-Python repo yields empty
    `changes_referenced` honestly — no regression.
- **Tests** (`tests/test_plugin_runtime.py`, new `class TestFromCountsIngest`,
  mirroring `TestFromJunitIngest`): happy path (counts recorded, **no** subprocess
  — the repo's own test would fail if run; assert schema-valid + `test-status`
  current); `failed>0` → exit 1; missing `passed`/`failed` → usage error; unknown
  key → usage error; non-integer / negative value → usage error; rejects
  `--from-junit` combo; rejects extra args; rejects `test_command:` combo.
- **Acceptance criteria:** `python3 -m pytest -q` green; a non-JUnit `record
  --from-counts passed=5 failed=0 skipped=1` writes schema-valid evidence with no
  pytest subprocess and `test-status` reports `current`.
- **Type:** code
- **Done when:** 1) AC met + tests pass; 2) `/prawduct:critic` (infers `chunk`)
  blocking findings resolved; 3) committed.

### Chunk 02: `--no-rerun` restamp + HEAD~1 fallback-base advisory

- **Description:** Two conveniences. (a) `--no-rerun` (alias `--restamp`): reuse
  the existing `.test-evidence.json` counts, re-stamp the timestamp, and re-run
  the F4a overlay against the **current** tree — the sanctioned cheap refresh
  after a rename/force-add `changes_referenced` shift, with no suite run. (b) A
  stderr advisory when the diff base resolves to the moving `HEAD~1` fallback,
  naming the `base_branch:` knob — closing the one path where a no-op commit
  genuinely shifts the changed-file set.
- **Depends on:** Chunk 01 (shares `cmd_test_evidence` arg parsing)
- **Artifacts consumed:** this plan; `bin/prawduct-hook`,
  `bin/test-reference-verify`
- **Deliverables:**
  - `bin/prawduct-hook:cmd_test_evidence` — add `--no-rerun`/`--restamp`: require
    an existing evidence file (clean error if absent or malformed/missing count
    fields), reuse `passed/failed/skipped/duration_seconds/command`, `proc=None`,
    re-stamp `timestamp`, then the normal atomic write + F4a overlay. Reject
    combining with `--from-junit` / `--from-counts` / extra args / `test_command:`.
    Docstring + usage updates.
  - `bin/prawduct-hook:cmd_test_evidence` — after resolving the overlay base, if
    it is `HEAD~1`, print a one-line stderr advisory naming `base_branch:`.
  - `bin/test-reference-verify:main` — when the base **auto-resolves** to `HEAD~1`
    (no explicit `--base`), print the same advisory. (Not placed in the shared
    `_resolve_base_branch`/`_resolve_base` to avoid noise on unrelated gates.)
- **Tests:**
  - `tests/test_plugin_runtime.py` (`class TestNoRerunRestamp`): `--no-rerun`
    reuses prior counts + refreshes timestamp without a subprocess (the repo's own
    test would fail if run); missing evidence → clean error; malformed evidence →
    clean error; rejects combination with `--from-junit`/`--from-counts`/extra
    args. Alias `--restamp` works.
  - `tests/test_reference_verifier.py` (`class TestHeadTilde1Advisory`, modeled on
    `TestEmptyDiscoveryWarns`): a repo with only `main` absent → standalone
    verifier auto-resolving `HEAD~1` warns naming `base_branch:`; an explicit
    `--base` or a resolvable `main`/`origin/main` → no warning.
- **Acceptance criteria:** `python3 -m pytest -q` green; `--no-rerun` refreshes a
  record with no subprocess; a HEAD~1-fallback record/verify prints the advisory.
- **Type:** code
- **Done when:** 1) AC met + tests pass; 2) `/prawduct:critic` (infers `chunk`)
  blocking findings resolved; 3) committed.

### Chunk 03: mechanism-neutral methodology + backlog hygiene

- **Description:** Make single-record-at-Verify the explicit, mechanism-neutral
  default and **kill the retired "re-record after commit" habit** — the actual
  high-leverage fix that propagates to every consumer via the plugin. Then
  reconcile the backlog.
- **Depends on:** Chunk 01, Chunk 02
- **Artifacts consumed:** this plan
- **Deliverables:**
  - `methodology/building.md` — rewrite the Verify *Code:* bullet: record **once,
    at Verify, not after committing**; a commit (even a no-op) does not stale
    session-scoped evidence (so `test-status` stays green); name the on-ramps
    mechanism-neutrally — `--from-junit` (any JUnit emitter), `--from-counts` (any
    toolchain, no JUnit — embedded/bespoke), `--no-rerun` (restamp). **Constraint:
    `test_v5_methodology.py:185` caps building.md at <4950 tokens and it currently
    sits at ~4949** — trim the bullet to net-neutral, or bump the cap by the
    minimum needed WITH a rationale comment (sanctioned precedent: the cap was
    bumped 4850→4950 before). Detailed flag syntax stays in the hook help, not
    here.
  - `.prawduct/backlog.md` — mark the obsolete "Stopgap … record test-evidence as
    the LAST step, after committing" wording (in the TST-4K2P content-hash item)
    as **SUPERSEDED** (it survives only as a quoted-obsolete reference). Do **not**
    touch `learnings.md:270-272` — it is already the live correction.
  - Backlog hygiene via `/prawduct:backlog`: reframe **COV-3R9K** (run-half =
    closed by docs + `--from-counts`/`--no-rerun`; cite the corrected diagnosis),
    and **add** a new item for the Python-only coverage floor (bring-your-own
    verifier is the current escape; a language-agnostic/pluggable floor is the
    residual).
  - `.prawduct/change-log.md` — one tagged entry (`scope=test-evidence-single-run`,
    `chunks=01,02,03`, `status=merged` until the PR ships) so the PR's
    change-log gate passes; then `prawduct-hook regen-views`.
- **Tests:** `python3 -m pytest -q` green (the methodology token-cap test must
  pass — confirm building.md fits or the cap was bumped with rationale).
- **Acceptance criteria:** building.md prescribes record-once + names all three
  on-ramps + states a commit does not stale evidence; the stale backlog stopgap is
  marked superseded; COV-3R9K reframed; coverage-floor item filed; suite green.
- **Type:** cumulative-final
  <!-- Last chunk of a single-PR plan: its review IS the one `/critic cumulative`
       against merge-base...HEAD (the `/prawduct:pr create` gate). Commit first,
       then run cumulative once — no separate `final`. -->
- **Done when:** 1) AC met + tests pass; 2) committed + change-log entry +
  `regen-views`; 3) backlog reconciled; 4) `/prawduct:critic cumulative` against
  `merge-base...HEAD`, blocking findings resolved (the PR gate).

## Early Feedback Milestone

**Milestone chunk:** Chunk 01
**What the user can do:** after Chunk 01 a non-JUnit / embedded toolchain can
record evidence with `--from-counts` — the agnosticism gap the user flagged is
closed at the first chunk. Chunk 02 adds the restamp/advisory conveniences;
Chunk 03 kills the double-run habit at its documentation source.

## Governance Checkpoints

**Commit & PR cadence:** per-chunk `/prawduct:critic` (chunk) on Chunks 01–02; on
Chunk 03 commit first, then the one `/prawduct:critic cumulative` (its review AND
the `/prawduct:pr create` gate). One PR for the whole bundle (review economy — P0).
