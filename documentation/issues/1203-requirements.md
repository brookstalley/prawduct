# Issue #1203: the chunk-subject walk reads base merges that plan spans exclude (Requirements)

`status: draft · stage: requirements · area: plan-status · added: 2026-11-28 · source: #1199
build · issue: https://github.com/brookstalley/prawduct/issues/1203`

Related: #1199 (spans credit the merged-in side of a non-base merge), #1082 (span certification,
and the owner ruling of 2026-10-27 that took path credit away from spans), #1141 (a chunk certified
by another chunk's review: route C is this walk's subject half). The norm being defended is
`plugin/methodology/planning.md` "Chunk state", which says a span credits "a first-parent commit
(or one merged in from a non-base branch) whose subject carries the plan's scope and the chunk".

## Problem

Two readers in `plugin/lib/plan_status.py` each decide which commits in an interval are the plan
branch's own work. They give different answers. (The issue names `critic_consolidate.py` for the
walk, but the walk has since moved into `plan_status.py`. `critic_consolidate.py:3687` now only
calls it, through `chunk_proposal`.)

| Reader | Where | Commits it reads | A merge of the base |
|---|---|---|---|
| Span (`_Spans.carried`) | `plan_status.py:665` | `git log --first-parent base..head`. Then, for each merge among those, the merged-in side's own first-parent commits (`_Spans._side`), but only when that side's tip is not on the plan base's first-parent history (`first_parent_answer`) | Adds nothing |
| Walk (`_walk_branch`) | `plan_status.py:1902` | `git log base..head`: every parent, through every merge | Adds every base commit that `base` cannot reach |

`base` is not the same in every call to the walk:

- **No `since`** (`built_report`, and the lane proposal at `critic_mode.py:2660`). `base` is the
  plan's resolved base ref (`origin/<b>` preferred). A base merge usually brings in commits that
  ref can already reach, so `base..head` drops them and the two readers seldom disagree. The
  exceptions are a base ref that lags the commit that was merged, such as a local `develop` that
  is ahead of `origin/develop`, and a base the resolver cannot find.
- **`since` given** (`critic_consolidate.py:3687`, the `final` and `cumulative` proposal). `base`
  is the review interval's `base_commit`, which can be older than a base merge inside the
  interval. A `final` dispatched after "chunk review at X, merge develop, more work" has
  `since = X`. Every develop commit between X and the merge is then in the walk. The span for the
  same interval drops all of them.

**Consequence.** If one of those base commits has a subject carrying this plan's scope and an open
chunk id, the proposal names that chunk and the fact certifies it by name
(`planning.md`: a fact naming a chunk is certification, alongside the span). The interval's span
would not have credited it. So a chunk reads `done` from work this branch never did. That breaks
#1141 G1 ("a review certifies a chunk only when it read that chunk's work"), and the rendered
reason does not say why. Such a subject turns up when a plan ships in parts
(`planning.md` "A plan may ship in parts"), when a sibling plan reuses a scope, or when a hotfix
uses the plan's scope.

The disagreement can only go one way. The walk's subject set is a superset of the span's for the
same interval: every commit the span reads is reachable along all parents. So the walk only ever
proposes too much, and too much is the direction that certifies unbuilt work.

## The decision the issue asks for

The issue frames the choice as **exclude base merges from the walk** or **include them in the
span**.

**Recommendation: the walk excludes them.** Both readers ask one owner which commits in an
interval are the branch's own work, and that owner applies the span's rule.

- Including base merges in spans reverses #1199's and #1082's stated rule ("a base merge adds
  nothing"). It also reverses the `planning.md` sentence quoted above. That is a governance change
  with no owner ruling behind it, so this item cannot make it (core.md: a governance change cannot
  supply its own authority).
- A base merge's commits are the base's work, which was reviewed and certified on its own branch.
  Crediting them to this plan is exactly the false certification this item exists to prevent.
- Excluding them can only make the walk name fewer chunks. Naming fewer leaves a chunk open and
  keeps every gate armed, which is the fail direction `chunk_proposal` already documents.

The rest of this document assumes the recommendation. Q1 asks the owner to confirm it.

## Goals

- G1. One function answers "which commits in `base..head` are this branch's own". The span and the
  walk both read it, so the two cannot disagree on any interval.
- G2. For the same plan and interval, the walk's subject answers (`scoped_named`, `named`,
  `all_named`, `scoped_commits`) never include a commit that the span excludes.
- G3. Every walk caller keeps its current fail direction. When git cannot say whether a side is the
  base's, the commit is not credited, and the caller's existing "could not say" note is printed.
- G4. The fixture in the issue's acceptance criterion fails on current develop before the fix and
  passes after it (core.md: a check never seen to return non-zero proves nothing).

## Non-goals

- Changing what a span credits. #1199's rule stands as written.
- The walk's Deliverables-path half (`changed`). Q2 covers it; nothing here changes it unless the
  owner rules.
- Re-certifying history. A fact already written keeps the chunks it names, and `plan retract` is
  the remedy for a wrong one (`planning.md`).
- Changing commit-subject conventions or the scope rule (`_subject_chunks`, `_CHUNK_COMMIT_RE`).
- Squash-merged parts. `planning.md` already says a squash reopens a part's chunks.

## Requirements

**R1. One owner.** A single function in `plan_status.py` takes an interval (`base`, `head`) and the
plan's resolved base. It returns the interval's own commits: the first-parent commits plus the own
merged-in sides, expanded transitively as `_Spans._with_merged` does today. `_Spans` keeps its
memoization and dirty-tree chain (`_verbatim_chain`) and gets its committed list from this
function. No second copy of the side test (`merge-base --is-ancestor` plus `first_parent_answer`)
remains (hook-surface.md: export the answer, not the walker).

**R2. The walk reads the owner.** `_walk_branch` takes its commits from R1's function, never from a
bare `git log base..head`. This applies with and without `since`. Every subject-derived field
(`named`, `scoped_named`, `all_named`, `scoped_commits`) is computed from that list.

**R3. Two bases, both stated.** The walk has two bases. The *interval base* is where its range
starts: `since` or the resolved plan base, as today. The *plan base* is what a side is tested
against: always `_resolve_base`, even when `since` is given. The walk passes both to R1. Today the
walk has only the first, and R1 needs the second.

**R4. Unknown means not credited.** R1 cannot tell whether a merged-in side is the base's when the
plan base resolves to no ref, a parent is not an object id, or a git call fails. In those cases
the side contributes no commits, as `_Spans._side` does today. A git failure on the first-parent
log itself is returned as a cause string, which keeps the existing `isinstance(walk, str)`
handling in `chunk_proposal`, `built_report` and their callers.

**R5. Bounded cost.** An interval with no merge on its first parents costs one `git log`, the same
as the walk today. Each merge adds at most what `_Spans` already spends per merged-in tip: one
`merge-base --is-ancestor`, one bounded first-parent `rev-list`, and one side log. `built_report`
runs on the session-start briefing, so a plan branch with no merges must cost no more git calls
than it does now.

**R6. Notes that tell the truth.** `chunk_proposal`'s note for a chunk named only by an unscoped
subject stays. A chunk that only a base-merge commit names is not proposed and gets no new note,
because that commit was never this plan's work. Q3 asks whether the owner wants that exclusion
said out loud.

**R7. Prose agrees.** The walk's docstring, `chunk_proposal`'s `final`/`cumulative` paragraph, and
`_log_commits`' list of its readers must describe the shared rule. Today they read as if the walk
covers the whole of `since..branch`. `planning.md` "Chunk state" already states the span rule. If
`/prawduct:methodology` or the critic skill restates the proposal's range, those restatements are
updated in the same change (core.md: a mechanism change is done when every artifact describing it
agrees).

## Acceptance criteria

- [ ] **AC1 (the issue's).** A fixture branch merges develop, and the develop side carries a commit
  `feat(<plan scope>): … (Chunk N)` for an open chunk N. `_Spans.carried` for an interval spanning
  the merge returns a chunk set, and `chunk_proposal(..., "final", since=<interval base>)`
  returns the same set from its subject half. Neither includes N. The test fails on develop at
  `748cfc41`.
- [ ] **AC2 (#1199 still holds).** The same fixture, but the merged-in side is a delegate branch
  merged with `--no-ff` whose tip is not on develop's first parents. Both readers include the
  delegate's `(Chunk N)`.
- [ ] **AC3 (no `since`).** `built_report` on a branch whose base merge brought in a scoped commit
  the resolved base ref cannot reach (the ref lags the merged commit) does not tag that chunk
  built from the subject.
- [ ] **AC4 (unknown).** With the plan base unresolvable and a merge in the interval, the walk
  credits nothing from the merged-in side. `chunk_proposal` and `built_report` print their
  existing cause and note text, and the tests assert that text (hook-surface.md: pin every
  rendered branch).
- [ ] **AC5 (one owner, mechanically).** A test or lint asserts that `_walk_branch` and `_Spans`
  get their committed commit list from R1's function. Today `plan_status.py` calls `_log_commits(`
  in three places: `_Reachability._merged_verbatim` (line 523), `_Spans._log`'s memo (line 723) and
  the walk's bare `base..head` (line 1936). After the change, the walk's call must be gone, and any
  new call must sit inside R1's function. The check fails on anything else.
- [ ] **AC6 (cost).** A test counts `run_git` calls for `built_report` on a branch with no merges
  and requires the same count as today.

## Open questions for the owner

- **Q1. Confirm the direction.** Should the walk exclude base merges (recommended, above), or
  should spans include them (this reverses #1199 and the `planning.md` sentence)?
- **Q2. The path half.** Should `_BranchWalk.changed` also come from the own-commit list? Today a
  base merge's touched paths in `since..head` can tag a chunk `built` by its Deliverables (in
  `built_report` only, which certifies nothing and only arms the short-plan gate). Restricting it
  is consistent with R1. It could also hide a chunk that really was built on the base side of a
  plan shipped in parts. Recommended: restrict it, in the same change, because one owner means one
  answer.
- **Q3. Say the exclusion?** Should `chunk_proposal` add a note when an open chunk is named only by
  a base-merge subject ("named by a commit the base merged in, not this branch's work")? It is
  cheap and helps diagnose #1141-style reports. The cost is one more advisory line in a dispatch
  that already prints several. Recommended: no note for now. Revisit if a report shows the case
  arising.

```prawduct
v: 1
```
