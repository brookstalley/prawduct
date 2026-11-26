# Issue #1247: review cadence for long plans (design research)

`status: accepted · stage: design · area: critic · added: 2026-11-25 · source: read-only design
research dispatched from the 2026-11-25 backlog batch · issue:
https://github.com/brookstalley/prawduct/issues/1247`

**Accepted 2026-11-25.** The owner accepted all six decisions below as recommended ("yes to all of your
recommendations", `.prawduct/owner-rulings.md`). The numbers re-derive with
`python3 -I documentation/issues/1247-measure/measure.py <ledger.jsonl> <repo_dir> [since]`
(`verify_attrib.py` beside it checks the later-review attribution). Line citations are against develop at a74b98c5. Counts come from a read-only
scan of this clone's governance ledger (`.prawduct/.governance-ledger.jsonl` in the main checkout,
`review.critic` events from 2026-09-18, the first day after the stage-keyed norm, to 2026-11-25), and
each is labelled with that source.

## The short answer

#1247 asks for something that already exists, with a hard-coded bound. The short-plan deferral (#292)
is boundary-only cadence with an opt-out. Inference answers `deferred` and the Stop gate warns instead
of blocking, but only for plans of at most `SHORT_PLAN_MAX_CHUNKS = 3` chunks
(`critic_mode.py:1280`, checked at `:1458`) that touch no risk surface. The ask is a key that lifts the
bound, plus a change to what a `Critic mode:` declaration means. The premise does not hold on this
clone: here `chunk` rounds find more BLOCKING findings per minute than any other mode (§4).

## 1. What inference and the Stop gate expect, by chunk position

**The Stop gate is per turn, not per chunk.** It applies when the session changed judgeable files
under a bound plan (`prawduct-hook:3932-3934`). It blocks unless composed coverage spans the session's
base tree to the working tree with no open blocker (`session_review_verdict`, `:4118-4124`). It does
not read mode labels or chunk counts. On an `uncovered` verdict it relaxes in two cases only:
- **Extension deferral** (#167, `:4198`, `critic_mode.extension_deferral_owed`, `:1991`). A fix to
  chunks that a review already certified rides the next review the plan owes.
- **Short-plan deferral** (`:4193`, `critic_mode.short_plan_deferral`, `:1354`). On a non-final chunk
  it warns (`:4210`). On the last chunk it blocks and names the boundary step (`:4222-4238`).

**Inference, by position** (`infer_mode`, `critic_mode.py:223`):

| Position | Plan > 3 chunks, or a risk surface touched | Short plan |
|---|---|---|
| any chunk that declares `Critic mode:` (current = first open chunk) | that mode (`:295`) | that mode, and the whole plan loses the deferral (`:1471`) |
| non-final chunk, code in flight | `chunk` (rule 4, `:441`) | `deferred` (`:381-383`) |
| non-final chunk, clean tree | `chunk` over the unreviewed interval (`_mid_plan_answer`, `:901`) | `deferred` |
| last chunk, code in flight | `final` (rule 3, `:1226`), or `deferred` until commit if `Type: cumulative-final` | `deferred`: commit, then `cumulative` (`LAST_CHUNK_BOUNDARY_STEP`, `:2224`) |
| last chunk, clean tree | `cumulative` (rule 2, or `_clean_tree_redirect`, `:521`) | `cumulative` |
| fix after a review | `verify-resolutions` (rules 1/1b), or `deferred` by extension | same |

**Suite evidence is not required on every dispatch.** Only `verify-resolutions` refuses stale evidence
(exit 7, `critic_consolidate.py:4080-4096`). At `cumulative` a stale suite is a WARNING, and at `final`
it is an observation (`critic/SKILL.md:60`). Evidence is current when it is tree-valid, or when it was
recorded in this session (`gates.py:503`, `:626`). `building.md:93,105` asks for the suite once, at the
boundary. So "each dispatch needs a fresh whole-suite record" is true only of a verify pass across a
session boundary after a code change, and it is correct there.

## 2. Already answered or free

- **Round budget (owner ruling 2026-11-23).** A chunk's first review and the scope's first `cumulative`
  are not charged (`critic_consolidate.py:4921`, `_cadence_round_ids`). This answers the exhaustion
  half of the pain (`chunk-plan-order` needed `--force` for its boundary review). It saves no round and
  no minute.
- **Short plans** (`planning.md:144`, `review-cycle.md:14`) already get the cadence #1247 asks for.
- **Fixes ride later reviews** through extension deferral, and a `chunk` review starts at the covered
  frontier, so committing before reviewing costs nothing extra.
- **Ask 3, mostly shipped.** The tree-valid clause reuses a record across any delta of paths that cannot
  change a test outcome (`coverage_algebra.affects_test_outcome`, `:208`). That covers docs, metadata,
  and #1239's declared static content (`static_content_prefixes`). It also reuses a run recorded in
  another worktree through the store (`_store_run_vouching`). What remains is "code that no test
  reaches", which is test-impact analysis. That belongs to #1096 (a composable run ledger with narrow
  runs) and #1088 (covered lines). Content-equivalence gating was built, rated unsound and reverted (#367,
  `review-proportionality-assessment-2026-09-17.md` §4).

## 3. Norm, default, or prose?

Per-chunk review is **not a ratified norm.** The NFR (`nonfunctional-requirements.md:117`, ratified
2026-09-17) keys rigor to stage. It says the boundary is "never skipped or inferred away". It does not
require any inner-stage review to exist. Its last sentence governs which mode to pick when one runs.
The per-chunk row is prose (`review-cycle.md:14`) enforced by the Stop gate's coverage check.

The 3-chunk bound is an owner trade-off. It came from the review-stages plan as an owner-vetoable
`[ASSUMPTION]` (`archive/build-plan-review-stages.md:98`) on the owner's 2026-09-17 trade ("saving a
lot of wall clock for at most a minor drop in quality"). #292 says "the USER owns this tradeoff
(Principle 23)" and makes the guardrail test load-bearing: a 4-chunk plan still owes per-chunk review
(`tests/test_short_plan_deferral.py:155`).

So a cadence key is a **default change that needs an owner ruling, not a norm amendment**, with one
exception. Combined with #1232's `per_release`, an eligible plan could reach the integration branch with
no review at all. The NFR amendment accepted on 2026-11-23 (decision 2 of the #1222/#1223 design) is
scoped to "short-plan-eligible" work. Widening that set widens the amendment (§5).

**Decided against before.** "A skip-gate needs the MOST adversarial coverage" (#292, #291; the trivial
fast-path was retired). The review-stages plan named #716 as the miss story: its round-4 defect had been
present since chunk 1. Its advisory said Chunk 04 "is the one chunk that removes a review rather than a
severity". No unmerged branch holds a cadence key. On 2026-11-25, `git log --all --grep='1247\|cadence\|per_release'`
matched only the merged `fix/round-budget-cadence`.

## 4. Measured here

Source: the ledger above, 573 `review.critic` events. The plan's chunk count is the number of distinct
`## Chunk N` headings in `build-plan-<scope>.md`, live or archived. Three scopes with no plan (180
rounds) are excluded from the plan split.

| Mode | Rounds | Median min | Total h | Rounds with a BLOCKING | BLOCKING findings per hour |
|---|---|---|---|---|---|
| chunk | 57 | 5.0 | 5.9 | 25 (44%) | 5.8 |
| final | 23 | 7.0 | 3.2 | 9 (39%) | 3.1 |
| cumulative | 180 | 9.0 | 29.1 | 43 (24%) | 2.2 |
| verify-resolutions | 313 | 4.0 | 23.6 | 23 (7%) | 1.0 |

The 5.0-minute chunk median is 2.5× the NFR's "per-chunk ≤ 120s median" target
(`nonfunctional-requirements.md:145`). That target is the unit-cost lever. Cadence is the run-count
lever.

**Plans of more than 3 chunks** (19 scopes):
- `chunk` rounds: 25, 173 min.
- Verify passes following a `chunk` round: 12, 48 min.
- Chunk cadence total: 221 of the 801 review minutes on those scopes (28%), against 524 min (65%) for
  `cumulative` and its verify tails.
- Over 68 days that is the ceiling on what boundary-only would save here: about 3.7 h, or about 25 min
  for each of the 9 scopes that ran any `chunk` round.
- 10 of the 19 scopes recorded no `chunk` round. The ledger does not say why.

**`chunk-plan-order`** (7 chunks) looks like the issue's shape:
- 6 `chunk` rounds took 57 min, against one `cumulative` of 15 min.
- The `chunk` rounds found all 3 of the plan's BLOCKING findings: a `plan retract --all` that does not
  converge, an untested `--json` branch, and a second, weaker plugin-build reader.
- The `cumulative` found none, but it read a tree the `chunk` rounds had already fixed.

**Would the boundary have caught the `chunk` BLOCKINGs? Not derivable.** There were 34 `chunk`
BLOCKINGs. By goal: Broken 19, Missing 13, Unintended 2. None was a record. At the inner stage, records
are observations, which buy no round. For 26 of the 34, a later `cumulative` in the same scope reviewed
the finding's files. That condition is necessary, not sufficient. Two had no later `cumulative`. The
store cannot say what a reviewer would have seen in a tree that was then fixed. Two ways to derive it:
- A replay: re-dispatch `cumulative` on a reconstructed pre-fix branch for a sample of these findings.
- A prospective trial: run the reporter's repo under boundary-only cadence for several long plans, and
  record which boundary findings trace to an early chunk and their fix size.

The issue's own figures are from a consumer repo and cannot be re-derived from here.

**One more fact:** this repo's `risk_surfaces` (`project-state.yaml:707-713`) cover `plugin/skills/`,
`plugin/bin/*hook*` and `plugin/lib/gates*`. Most framework plans touch one, so here a key that keeps
the risk-surface condition would rarely apply.

## 5. Seams with #1232 (#1223 wave 2)

1. **`_short_plan_shape` / `short_plan_deferral` (`critic_mode.py:1354-1523`).** #1232's derived
   eligibility includes "short-plan-eligible". If #1247 widens the bound through this predicate,
   `per_release` eligibility widens silently, and a 10-chunk plan could reach develop with no review
   before the release batch. Fix: give eligibility its own named shape bound (the current 3), separate
   from the cadence-dependent deferral answer.
2. **`infer_mode`'s last-chunk branches** (`:381-398`, the rule-3 `cumulative-final` arm, `:424`
   `_clean_tree_redirect`, `LAST_CHUNK_BOUNDARY_STEP`). #1232 answers `chunk` here under `per_release`.
   #1247 changes the non-final positions (`:381`, `_mid_plan_answer` `:901`). Both edit the same
   function. One owner should land first, and the other should rebase onto it.
3. **`review_owed_after` (`:1574`).** `OWED_BOUNDARY` for short plans means "the cumulative is owed".
   Under `per_release` it is owed at release. Under a wider cadence it applies to more plans. Both
   change who reads `_short_plan_shape` here.
4. **The Stop gate's Critic branch (`prawduct-hook:4191-4238`).** #1247 changes when it warns. #1232
   changes what the last-chunk block names.
5. **Message constants and prose.** Both changes edit `short_plan_next_step`,
   `SHORT_PLAN_OWN_PR_NOTE` and `_deferral_rationale`.
   - The bound is stated in `review-cycle.md:14`, `planning.md:144` and `critic/SKILL.md:37`.
     `tests/test_short_plan_deferral.py:451` pins the first two to `SHORT_PLAN_MAX_CHUNKS`.
   - `building.md:114,236` and `templates/build-plan.md` point at that rule instead of restating it.
     `test_v5_methodology.py:3745` and `test_v5_templates.py:293` pin that they do not restate it.
6. **Key namespace** in `project-state-keys.md`, beside `review_round_budget`.

**How the keys compose.** There are two orthogonal axes: whether inner-stage reviews run at each chunk,
and where the boundary review runs. Use two keys in one naming pattern, `<stage>_review:
per_<unit>`:
- `chunk_review: per_chunk | per_plan`, default `per_chunk`;
- `boundary_review: per_pr | per_release`, default `per_pr`.

One combined enum would be a 2×2 matrix with one dangerous cell, `per_plan` plus `per_release`. That
cell stays bounded by seam 1's fixed eligibility.

## 6. Proposed shape (if the owner wants the key)

- **`chunk_review: per_plan`** turns off the chunk-count condition in `_short_plan_shape` and nothing
  else. The risk-surface, base-branch and readability conditions stay. Inference keeps answering
  `deferred`, and the Stop gate keeps warning on non-final chunks. The last chunk still owes the
  boundary `cumulative`. Default `per_chunk` changes nothing.
- **Keystone opt-in.** Under `per_plan`, a `Critic mode:` declaration makes only its own chunk owe a
  review. Today any declaration cancels the deferral for the whole plan. This is harder than it looks:
  under deferral, earlier chunks stay open until the boundary review names them, so the "current chunk"
  (first open, `:295`) is chunk 01 for the whole plan. The chunk in flight has to be the first chunk
  that is open and not built, which needs `plan_status.built_chunks`. That walk is bounded to short
  plans for cost (`:1425`, spy-pinned at `test_short_plan_deferral.py:796`).
- **Guardrail.** #292's 4-chunk test becomes "a 4-chunk plan under `per_chunk`". Add tests that a
  risk-surface plan under `per_plan` still owes per-chunk review, and that `per_release` eligibility
  ignores `chunk_review`.

## Decisions for the owner

1. **Should cadence be configurable at all?** *Recommend:* yes, as a per-repo key, `chunk_review:
   per_chunk | per_plan`. Eligibility stays derived, with no per-plan field, consistent with decision 3
   of the #1222/#1223 design.
2. **Default for plans over 3 chunks?** *Recommend:* keep `per_chunk`. On this clone, `chunk` rounds
   have the highest BLOCKING yield per minute (5.8/h against the cumulative's 2.2/h), and the
   catch-anyway rate is not derivable. Revisit with the reporter's repo under a `per_plan` trial and a
   later-catch tally, as #1232 does for its consumer evidence.
3. **Does `per_plan` keep the risk-surface condition?** *Recommend:* yes. It is #292's guardrail and
   #1232's eligibility. Dropping it would make `per_plan` mean "never review mid-plan".
4. **What does `Critic mode:` mean under `per_plan`?** *Recommend:* keystone, so the declaring chunk
   alone owes its review, built on the not-yet-built reading of the chunk in flight. Under `per_chunk`,
   short plans keep today's whole-plan opt-out, so no existing plan changes meaning.
5. **Is `per_release` eligibility fixed at 3 chunks, independent of `chunk_review`?** *Recommend:* yes.
   Otherwise #1247 silently widens the NFR amendment accepted on 2026-11-23.
6. **Ask 3, reusing suite records.** *Recommend:* no new mechanism under #1247. The shipped tree-valid
   clause, #1239's static content and the store already reuse records wherever no test-affecting path
   changed. Test-impact reuse goes to #1096/#1088, and #367's ruling stands.

| Item | Proposed stage | Effort | Impact |
|---|---|---|---|
| #1247 (asks 1, 2) | design: rule 1-5, land after #1232's `critic_mode` edits | M (key, keystone reading, built walk, prose sweep) | S here (≤ ~3.7 h over 68 days); unmeasured on the reporter's repo |
| #1247 ask 3 | close into #1096/#1088 | — | — |

Triage: keep #1247 open as its own item. It is not a duplicate of #1223/#1232, which change where the
boundary runs, not whether inner reviews run. Link it to #1232 as sequenced after it because of the
shared `critic_mode` functions, and label it `area:critic, kind:feature, stage:design, effort:M,
impact:S`.
