# Issue #1094 — critic: rate test failures in a join step, not in reviewers: Design

`status: draft · stage: design · area: critic · added: 2026-10-28 · revised: 2026-11-18 · issue:
https://github.com/brookstalley/prawduct/issues/1094`

Related: #678 (the guidance half: say tests and review may run concurrently), #1015 (profile and
cut the suite), #1096 (run ledger), #1088 (flake touch marking). No requirements doc exists; the
acceptance criteria are the issue's Proposal and its open question, restated as D1–D6 below.

**Revision note (2026-11-18).** The 2026-10-28 draft never reached `develop`; it sat on two session
branches. This revision lands it on `develop` and re-checks every research claim against the
`develop` tree at `c9c6af7a`. Four of the draft's claims no longer hold, and they change the design:

| 2026-10-28 draft said | `develop` today | Effect |
|---|---|---|
| "No code rates failures"; `critic_consolidate.py` never reads test evidence | Reviewers still rate, but now in a structured `failed_tests` field that consolidate validates and matches against the merge-base run to waive inherited failures (`_waive_inherited_failures`, `_inherited_baseline`) | The join is no longer a new rater beside prose. It replaces the reviewer as the *source* of a field code already consumes (D2) |
| A running suite is "detectable only by absence" | The recorder stamps `in_progress` on the record; `gates.SUITE_STATES` has `running` and `interrupted`; `test-status --wait` exists; reviewers are told `running:` is never a finding | The draft's rejected option 2 (a run-active marker) already shipped in another form. D4 is rewritten around it |
| Stale or missing evidence is a WARNING the reviewer raises at `cumulative` and notes at `final` | Same, but the suite is now recorded once, at the boundary run (`building.md` "Code"), so `chunk` and `final` raise nothing for stale or missing | Concurrency only matters at the boundary. D1 is scoped to `cumulative` |
| "The tree has no flake concept in the critic path" | Records carry `flaky` entries with a record-time `flaky_policy` outcome; reviewers rate a `flaky_policy: warn` line WARNING at the boundary | D3 reverses: the join rates flakes too |

## Research (verified 2026-11-18 against `develop`, not recalled)

- **The open question carried from #678 is still answered: a `test-evidence record` write during a
  live review does not void the review's tree.**
  - `.prawduct/.test-evidence.json` is gitignored (`.gitignore:29`; `.critic-active`, line 3).
  - `evidence.capture_tree` builds its tree from a temporary index, so ignored files never enter it.
  - The `test-run` fact `record` appends is an observational kind
    (`evidence.OBSERVATIONAL_KINDS`), which the coverage verdict never reads.
  - What can move the tree is the suite's own writes to tracked judgeable files. `record` keeps
    `evidence_tree` only when `gates._test_evidence_tree_valid` says the tree held still
    (`plugin/bin/prawduct-hook` ~6330). A run that moved it is unvouched, which the join treats as
    not current. Read from the code; the build pins it with a test (see Build outline, test e).
- **What reviewers do with suite results today** (`review-protocol.md` §1, `goals-1-3.md` step 4 and
  its bullet, `SKILL.md` step 5, three statements of one rule):
  - run `prawduct-hook test-status` and read `.test-evidence.json`;
  - stale or missing: WARNING at `cumulative`, an observation at `final`, nothing at `chunk`;
  - `running:`: never a finding (`--wait`, or note it);
  - failures: BLOCKING, copying the failing ids into the finding's `failed_tests`;
  - a `flaky:` line tagged `flaky_policy: warn`: WARNING at the boundary, an observation inside.
- **Every one of those ratings is a function of recorded facts.** None needs the diff. The reviewer
  is a transcription step between `.test-evidence.json` and the review fact.
- **That transcription is load-bearing and already guarded against.** `_inherited_baseline` refuses
  a waiver unless every failure the branch caused is named by an unwaived finding, because "a
  reviewer that named only the inherited subset of a mixed red suite must not have the whole suite
  waived" (its docstring). The guard exists because a model copies the ids.
- **Consolidate already holds everything the join needs.** It reads the reviewed tree's newest
  whole-suite run (`evidence.newest_suite_run(store, manifest["head_tree"])`), its failing ids and
  whether the list is complete (`evidence.run_failed_tests`, the 100-id cap), and the suite state
  (`gates.suite_remedy`).
- **One mode already orders tests before review in code.** `verify-resolutions` dispatch refuses
  with exit 7 when saved evidence exists and is not current (`_stale_test_evidence`, #724). The
  other three modes have no such gate, which is the issue's first sentence. It stays true.
- **Consolidation's shape fits a second lane.** It persists only when every roster role has
  reported, and is otherwise "a no-op naming the missing roles (still in flight)". It removes the
  partials on success, so a repeat call is a no-op. The draft's "re-run `critic-consolidate` after
  the record appears" therefore cannot add a late verdict; the wait must come before persisting.
- **Wall clock (issue comment, 2026-10-27):** suite 1351.9s, pool phase 113.0s; about 92% is local
  `test_commands`. Not re-measured for this revision. #1015 is still open at `stage:ready`.

## Decisions

### D1 — Two lanes at the boundary, joined by tree identity

At `cumulative`, the builder may start `test-evidence record` and the review (`critic-begin` →
partials → `critic-consolidate`) on the same tree, in either order or together. Neither lane reads
the other until consolidate. Inside a plan (`chunk`, `final`) nothing changes in ordering, because
no suite run is owed there.

In every mode, reviewers stop running `test-status`, stop reading `.test-evidence.json`, and stop
rating suite results. They keep reviewing test quality and coverage from the code.

`verify-resolutions` keeps its exit-7 precondition. That mode reviews a fix, and a red suite there
is cheaper to learn before dispatch than after.

### D2 — Consolidate is the source of suite findings

After partials merge and before the review fact is appended, consolidate derives the suite
findings itself and adds them to the merged set with `source: join` and a fixed fid prefix:

| Suite state for the reviewed tree | `cumulative` | `final` | `chunk` |
|---|---|---|---|
| a whole-suite run vouches, no failures, no warn-policy flake | none | none | none |
| a run vouches, failures present | BLOCKING | BLOCKING | BLOCKING |
| a run vouches, a flake with `flaky_policy: warn` | WARNING | observation | observation |
| no run vouches (missing, stale, degraded, interrupted) | WARNING | observation | none |
| `running` | wait (D4) | observation | none |

This is the reviewers' current table, cell for cell. The build must not change a rating while
moving it; a rating change is a separate item.

- **Failures:** one BLOCKING finding whose `failed_tests` is the run's own list. When the run's
  list is incomplete (the 100-id cap), the finding says so and carries what is listed;
  `_inherited_baseline` already refuses a waiver in that case.
- **The waiver path is unchanged.** `_waive_inherited_failures` runs after the review fact is
  appended and reads `failed_tests` off BLOCKING findings. It does not care who wrote them. Its
  "every new failure is named by an unwaived finding" guard becomes true by construction.
- **Splitting inherited from new:** the join writes two findings when it can tell them apart (a
  base-tree run exists): one for ids the base also failed, one for the rest. Otherwise a single
  finding mixing both could never be waived, which is worse than today, where a reviewer may split
  them. This is the one place the join does more than transcribe.
- **A reviewer partial that still carries `failed_tests`** (stale skill text during rollout) is
  dropped in favour of the join's finding, with a line on stderr. Two sources for one rating is the
  duplication this item removes.

Why code and not a model: the rating is a function of two recorded facts, and the only judgment in
it (did this branch cause the failure) is already made in code by the waiver.

### D3 — Which comparison says a run vouches

Two exist, and they differ:

- `evidence.newest_suite_run(store, tree)` matches `body.tree == tree` exactly. The inherited
  waiver uses it.
- `gates.suite_vouches_for_tree(project_dir, tree)` compares by judgeable path, so a run that wrote
  a cache or a report still vouches. The base-advance transfer uses it.

The join needs the failing ids, which only the store fact carries, so it reads the fact. Chosen:
use the exact match for the fact, and fall back to "no run vouches" when it misses. That is
fail-safe (a WARNING, never a false green) and keeps the join and the waiver on one lookup. If
real runs miss on exact identity often enough to matter, that is a defect in the shared lookup and
is fixed there for both readers, not worked around in the join. The build measures the miss rate on
this repo's own store before choosing otherwise (open question 3).

Session freshness, the other disjunct of `gates.tests_are_current`, is not consulted. The issue
asks for tree identity, and "recorded earlier this session" says nothing about the reviewed tree.

### D4 — The suite is one more party consolidate waits for

At `cumulative` only, when the suite state is `running`, consolidate does what it does for a
missing roster role: persists nothing and names what is still in flight, with
`gates.suite_remedy`'s wait clause. Nothing is written, so the next call finds the same partials.

- **Who makes the next call.** Consolidation is triggered per reviewer by `SubagentStop`, so when
  the suite outlasts the last reviewer, no trigger is left. `test-evidence record` therefore calls
  the same consolidate entry point when it finishes. With no manifest waiting it is a no-op. This
  is the consumer for the new wait state; without it the state would have none.
- **`interrupted`** is not waited on. The recorder is gone, so it rates as "no run vouches".
- **No suite started.** Consolidate cannot tell "not started yet" from "not going to run". It
  rates WARNING and persists, as a reviewer does today. The builder who meant to run both lanes
  starts the suite first or alongside; `building.md` says so in one line.
- **Not chosen: wait whenever no run vouches.** That would make the suite a hard prerequisite of a
  boundary review, which the landing gates already enforce where it matters
  (`release_readiness`'s `unproven-suite`), and would stall every product with no suite.

### D5 — Clearing a join finding

A join BLOCKING finding is an ordinary BLOCKING finding on the review fact. It clears the ordinary
way: fix, record the suite, `verify-resolutions`. That mode's exit-7 precondition already refuses
dispatch on a red or stale suite, so a verify pass that reaches a reviewer has a current green run
behind it. No new resolution origin is added. An inherited failure clears through the existing
waiver with no round, as today.

The earlier draft proposed a mechanical close on a fresh green record. Not chosen here: it would
add a third route to lifting a BLOCKING finding, and #1160's design is already reworking how verify
passes answer open blockers. Revisit after #1160 lands (open question 1).

### D6 — Sequencing

1. #678 (guidance) can ship first and alone.
2. This item's dedupe half (D2, D3, D5: the join rates, reviewers stop) has no dependency on suite
   time and is worth shipping for correctness alone: it removes a model from a deterministic path
   and a transcription the waiver has to defend against.
3. The concurrency half (D1's two lanes, D4's wait) pays off in proportion to suite time. With
   about 92% of the suite in local `test_commands`, #1015 is the larger wall-clock win and goes
   first. If the suite lands near the review's own duration, the wait state is still correct but
   rarely entered.
4. #1096 (run ledger) changes how the suite state is composed. If it lands first, the join reads
   the composed state through the same `gates` functions and needs no change of its own; if it
   lands after, it must keep `newest_suite_run`'s contract or update both readers.

## Build outline (not binding until the owner answers the questions below)

- `critic_consolidate.py`: `_join_suite_findings(mode, head_tree, store, suite_state) ->
  (findings, observations, wait)`, a pure function called after partial merge. Inputs are injected
  so tests need no git.
- Consolidate's persist condition gains the `wait` case at `cumulative`; the no-op message names
  the suite beside any missing roles.
- `test-evidence record`: on finish, call the consolidate entry point.
- Partial validation: a reviewer finding carrying `failed_tests` is dropped with a stderr line
  rather than refused, so a stale skill cache cannot fail a whole consolidation.
- Prose, one statement each: `review-protocol.md` §1, `goals-1-3.md` step 4 and bullet, `SKILL.md`
  step 5, `cross-checks.md`'s test-evidence column, `review-cycle.md`'s inherited-failure bullet,
  and `building.md`'s "Critic takes minutes" paragraph. Search for the claim ("Test failures in
  evidence", "the only freshness signal", "exit 1 = stale") across prose, tests and templates,
  and delete the superseded sentences. `SKILL.md`'s `allowed-tools` loses `test-status` if nothing
  else in the skill uses it.
- Tests, each seen to fail first:
  (a) a vouching red run yields BLOCKING with the run's ids, at every mode;
  (b) a vouching green run yields nothing;
  (c) no vouching run yields WARNING at `cumulative`, an observation at `final`, nothing at `chunk`;
  (d) `running` at `cumulative` persists nothing and leaves the partials; a later call with a
      finished run persists;
  (e) a `record` write between `critic-begin` and consolidate leaves `head_tree` unchanged;
  (f) a mixed red suite with a base run splits into an inherited finding that is waived and a new
      one that is not;
  (g) a reviewer partial carrying `failed_tests` is superseded by the join's finding, not doubled;
  (h) a `flaky_policy: warn` entry rates WARNING at `cumulative`.
- Replay: run the join over this repo's stored reviews that carry a `failed_tests` finding and
  compare its output to what the reviewer wrote. A difference is either a reviewer error the join
  fixes or a rating the table above lost; each one is read before shipping.

## Risks

- **A wait with no waker.** If `record` dies after stamping `in_progress`, the state becomes
  `interrupted` and the next consolidate call persists with a WARNING. But nothing makes that next
  call. Mitigation: the builder-facing no-op message says to re-run `critic-consolidate` once
  `test-status --wait` returns, and the Stop gate's live-review marker already keeps the session
  from ending on an unconsolidated review. Confirm the second half in the build.
- **Exact-tree misses read as "suite owed"** when the suite did run (D3). Measured before build.
- **Lost nuance.** A reviewer could say something about a failure beyond its id (for example that
  the failing test is the one the diff weakened). The join cannot. Reviewers still review test
  quality from the code, and the failing ids are in the findings file for them to read on a later
  round, but the first round's reviewers no longer see suite results at all. Open question 2.

## Open questions for the owner

1. **Clearing (D5).** Keep the ordinary route (fix, record, `verify-resolutions`), as chosen, or
   let a fresh green run on the fixed tree close a join finding with no reviewer round?
2. **Do reviewers still see suite results?** Chosen: no, in any mode. The alternative is to hand
   them the join's findings as context (read, not rated), which keeps the nuance in Risks and costs
   the wait at dispatch that this item removes.
3. **Vouching comparison (D3).** Exact tree match on the store fact, as chosen, or widen
   `newest_suite_run` to the judgeable-path comparison for both the join and the waiver?
4. **Ship the dedupe half ahead of #1015 (D6 step 2)?** Recommended yes. The draft's single
   "after #1015" ordering was written when the join looked like a new rater; it is now the removal
   of one.
