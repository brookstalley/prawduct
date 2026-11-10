# Issue #1094 — critic: rate test failures in a join step, not in reviewers: Design

`status: draft · stage: design · area: critic · added: 2026-10-28 · issue:
https://github.com/brookstalley/prawduct/issues/1094`

Related: #678 (the guidance half: say tests and review may run concurrently). This item is the
mechanism change #678 scopes out. No requirements doc exists; the acceptance criteria are the
issue's Proposal and its two open questions, restated as D1–D5 below.

## Research (verified 2026-10-28 against the tree, not recalled)

- **The open question is answered: a `test-evidence record` write during a live review does not
  void the review's tree.**
  - `.prawduct/.test-evidence.json` is gitignored (`.gitignore:23`; also `.critic-active`, line 3).
  - `evidence.capture_tree` builds its tree from a temp index with `git add -A`, so ignored files
    never enter it. The record file moving cannot change the tree `critic-begin` snapshotted.
  - The `test-run` line that `record` appends goes to the evidence store, a kind the coverage
    verdict never reads (`OBSERVATIONAL_KINDS`, `plugin/lib/evidence.py`).
  - What can move the tree is the suite's own writes. `record` already handles that: it captures
    `pre_run_tree`, and keeps it as `evidence_tree` only when `_test_evidence_tree_valid` says the
    tree held still by `affects_test_outcome` path (`prawduct-hook` ~5027).
  - Caveat to test, not assume: a suite that writes a *tracked* judgeable file mid-review moves
    the tree. `record` then omits `evidence_tree`, and the join treats the evidence as
    unvouched (D3). That is the correct fail-closed behaviour.
- **Reviewers do not run tests today.** `review-protocol.md` §1 says "Do not run tests", and the
  skill's `allowed-tools` denies `pytest`. What reviewers do is read `.test-evidence.json`, run
  `prawduct-hook test-status` (exit 1 = stale or missing), and rate: stale → WARNING at
  `cumulative`; failures in evidence → BLOCKING. So the serial cost the issue names is *ordering*
  (the suite must be recorded before the review starts, or the freshness read is wrong), and the
  duplicated cost is each reviewer partial re-deriving the same verdict from the same file.
- **No code rates failures.** `critic_consolidate.py` has no reference to test evidence or
  `test-status`. The rating lives only in reviewer prose (`goals-1-3.md` step 4,
  `review-protocol.md` §1, `SKILL.md` step 5). A mechanical join therefore *adds* a rater rather
  than moving one, which is the main risk (D2).
- **Wall clock, from the issue's measurement (2026-10-27):** suite 1351.9s, pool phase 113.0s. About
  92% is local `test_commands`. Concurrency hides that cost; it does not remove it. Profiling the
  local entries is #1015's job and is the larger win. This design is sequenced after it, not
  instead of it (D5).

## Decisions

### D1 — Two lanes, joined by tree identity

Run the suite (`test-evidence record`) and the review (`critic-begin` → partials →
`critic-consolidate`) concurrently on one tree. Neither lane waits on the other until
`critic-consolidate`, the join. Reviewers stop reading `test-status` and stop rating anything about
suite results; they keep reviewing test *quality and coverage* from code (§1 bullets unchanged).

### D2 — The join rates failures, in code

`critic-consolidate` gains one step after partials are merged. It takes the manifest's tree
(recorded by `critic-begin` as the review's head tree) and the evidence record, and emits a
synthetic finding with a fixed id prefix and `source: join`:

| Evidence state | Finding |
|---|---|
| vouches for the review tree, `failed + errors == 0` | none |
| vouches for the review tree, failures present | **BLOCKING**, one finding listing failing test ids from the JUnit-derived counts |
| no record, or record has no `evidence_tree`, or tree differs by a judgeable path | **WARNING** at `cumulative`; observation at `final` and `chunk` (today's wording, now emitted once instead of per reviewer) |
| suite still running (D4) | consolidate waits or reports "suite owed" per mode (see D4) |

The tree comparison is `gates._test_evidence_tree_valid`, the comparison the freshness gate already
trusts, never raw equality (a run writes caches and reports of its own). No new freshness logic.

Why code, not a model: the rating is a pure function of two recorded facts. A join that a
reviewer could re-rate would recreate the duplication. The consolidator already owns severity
for findings it merges; this adds one deterministic source.

### D3 — Flakes are not rated by the join

The issue says reviewers rate "failures and flakes". The tree has no flake concept in the critic
path (`grep flake plugin` finds only `CHANGELOG.md`). Flake marking is #1088's scope
(`test-evidence`). The join rates what the evidence says and no more: a failure is a failure. When
#1088 lands a "flake" field, the join reads it as one more column in the table above; it is not
invented here.

### D4 — Concurrency protocol and the still-running case

`record` is a foreground command and writes the evidence file only when the run ends. So "suite
still running" is detectable only by absence: no record, or a record whose tree is stale.
Options considered:

1. **Join treats absent evidence as WARNING (chosen).** Simple, fail-open on the review, fail-closed
   on landing: the Stop gate and `/prawduct:pr` already require current evidence before work lands
   (`final` observation text), so a review that finishes before the suite does cannot let red code
   land. The builder re-runs `critic-consolidate` (idempotent over the same partials; verify
   this in the build) after the record appears, or the next boundary run supplies the verdict.
2. A `.test-run-active` marker mirroring `.critic-active`, with `critic-consolidate` waiting on it.
   Rejected for now: a new persisted file and a wait loop for a case the gate already covers.
   Revisit if the WARNING-then-rerun path shows up as friction in telemetry.

### D5 — Sequencing

1. #1015 (profile and cut the suite, target ~5 min) first. If the suite lands near the review's
   own 4–10 minute duration, concurrency saves little and the join is still worth shipping for the
   dedupe in D2, but its priority drops to M.
2. #678 guidance (say the two may run concurrently) can ship independently and first.
3. This item: join step + reviewer prose edits.

## Build outline (for the plan, not binding until requirements are confirmed)

- `critic_consolidate.py`: `_join_test_evidence(project_dir, manifest) -> list[finding]`, called
  after partial merge, before severity tally. Pure function over (manifest tree, evidence dict,
  tree-valid callable) so tests inject the tree check.
- `critic_begin` / manifest: confirm the review's head tree is already recorded; add it if not.
- Prose, one owner each: `review-protocol.md` §1, `goals-1-3.md` step 4, and `SKILL.md` step 5
  drop the reviewer-side `test-status` read and failure rating, and say the join rates them. Per
  the core learning on mechanism changes, grep for the *claim* ("Test failures in evidence →
  BLOCKING", "exit 1 = stale") across prose, tests and templates, and delete superseded sentences.
- Tests, each red-verified: (a) failures on matching tree → BLOCKING finding; (b) green on
  matching tree → none; (c) tracked judgeable file changed after the run → WARNING, not green;
  (d) no `evidence_tree` → WARNING; (e) a `record` write between `critic-begin` and consolidate
  leaves the manifest tree and review validity unchanged (the answered open question, as a test).

## Risks

- **Double-counting during rollout:** if reviewers still rate failures from stale cached skill
  text while the join also does, the same failure appears twice. Mitigation: the join dedupes on
  its fixed id prefix, and the build bumps the skill version so a stale cache is detected like the
  existing `--mode` skew guard.
- **A join finding with no reviewer to resolve it:** `verify-resolutions` must treat the join's
  finding as resolved by a green record on the new tree, not by a reviewer partial. Needs a
  decision in requirements (open question 1).

## Open questions for the owner

1. How does `verify-resolutions` close a join-sourced BLOCKING finding: by a fresh green record on
   the new tree (recommended, mechanical), or by the usual disposition path?
2. Is D4 option 1 acceptable (review may finish before the suite; landing is still gated), or do
   you want the review to refuse to consolidate until a vouching record exists?
3. Confirm D5 ordering: ship after #1015, or ship the join now regardless of suite time?
