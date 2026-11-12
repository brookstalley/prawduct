---
schema: 1
type: feature
scope: review-round-cost
date: 2026-11-11
title: an unreadable reviewer partial costs one reviewer, and an inherited red baseline is waived without a round
closes: [brookstalley/prawduct#961, brookstalley/prawduct#900]
---
Two causes made a whole Critic round buy nothing, and both are gone.

**One unreadable partial (#961).** `critic_consolidate.check_partial` is now the single verdict on
one reviewer partial. Its body, `_load_partial`, parses the file and then checks the schema, the
keyed location, the role, the dispatching review's id and the reviewed commit. `consolidate`'s
read loop and the new read-only verb `prawduct-hook validate-partial <path>` both use it, so they
cannot disagree. The reviewer agent and the Critic skill grant the verb. A reviewer validates its
own partial before it returns and fixes it until the verb exits 0.

Consolidation stays fail-closed: a review never persists with a role missing. When it refuses, its
message now says which role failed, which other partials passed and are kept on disk, which are
still unwritten, and the cheap remedy. That remedy is to re-dispatch only the failing reviewer,
with the same manifest and prompt, and not to run `critic-begin` or `critic-discard`, which would
archive the sound partials. An inline single-pass fork is told to rewrite its own partial and
re-run consolidation. The remedy's wording lives in the refusal alone, and each surface that meets
a refusal defers to it: the Critic skill tells the fork to follow its own consolidate's remedy,
`building.md` tells the main session to follow the printed remedy rather than start a fresh
review, and the Stop hook's backstop blocker says the same and that `/prawduct:critic` is refused
while the complete roster is on disk. The coordinator, which stops before consolidation and never
meets a refusal, carries no remedy.

**An inherited red baseline (#900).** The owner ruled auto-waive on 2026-10-21. A test-run fact
now carries the failing test ids, with the same cap as the per-worktree record. A reviewer lists
the ids a test-failure finding rates in an optional `failed_tests` field; both review protocols
(`goals-1-3.md` and `review-protocol.md`, Goal 1) and the dispatched reviewer's partial schema say
so, so the waiver can fire at `final` and `cumulative` too. `evidence.newest_suite_run` finds the
newest suite run on a tree, matching the tree, not the head, and skipping narrowed runs, and
`evidence.inherited_failures` reads the base tree's failing ids from it. After the review fact is
appended, consolidate resolves the merge-base with `coverage.resolve_merge_base_tree`, the prelude
every gate uses, and writes a `waived` resolution fact, with `origin: inherited-baseline` and
`base_run`, for each BLOCKING finding whose every named id that run also failed.

The base must be genuinely before the reviewed work. There is no waiver when the base fell
through to the moving `HEAD~1` fallback, when the merge-base is not an ancestor of the review
interval's own base commit (work committed straight onto the base branch), or when the base tree
is the reviewed tree. The reviewed tree's own newest suite run must list every failure (the 100-id
cap fails closed on this side too), and each failure it has that the base did not must be named by
a BLOCKING finding that stays unwaived, so a reviewer naming only the inherited subset of a mixed
red suite waives nothing. Any id missing from the base run, no run on either tree, or a newer
green run on the base means no waiver either, and the finding blocks as before. A finding that
named tests and was not waived gets one stderr line saying why.

The finding stays BLOCKING on the record. Both the PR gate and the Stop gate read the waiver as
resolving it. The findings cache reads the waivers from the store rather than taking them from
consolidation, so a clone that ingests the review renders them the same way: the summary and the
NEXT-ACTION line stop counting them as open, and each waived entry is marked `waived:
inherited-baseline`. The census and `review-stats` report them as their own outcome
(`waived-inherited` / `waived_inherited`), apart from a reviewer's judged waiver and outside the
acted-on rate. `data-model.md`, `review-cycle.md`, `building.md` and the module docstrings state
the resolution rule with this second origin.

`tests/test_critic_consolidate.py` carries both halves. For #961: a three-role roster with one
malformed partial leaves the other two byte-identical, the verb and consolidate agree on the same
file, and a rewrite of only the bad partial consolidates. For #900: the waiver, every no-waiver
case in the item's acceptance, the three bases that are not before the work, the capped and the
mixed red suite on the reviewed tree, a failed waiver append and a newer-schema run fact (both
fail closed), the ingest render, the `review-stats` outcome, the idempotent re-run, and a base
run recorded from a real detached worktree of the merge-base. `tests/test_test_run_facts.py` pins
the run fact's `failed_tests`, and `tests/test_critic_reviewer_agent.py` pins `failed_tests` on
every reviewer surface that rates a test failure or defines the partial schema.
Reviewer payload budgets rose by declaration in `tests/test_reviewer_payload_budget.py`, each
raise with its reason, and methodology prose budgets rose in `tests/test_v5_methodology.py`.

## Consumer note
- **A failing reviewer partial no longer costs the whole round.** When `critic-consolidate`
  refuses one, its message names the role and gives the remedy: re-dispatch that one reviewer.
  Follow it; do not start a new review, which is refused while the other partials are on disk.
- **Reviewers check their own partial.** They now run `prawduct-hook validate-partial` before
  returning, so a malformed partial is usually caught before consolidation.
- **Getting an inherited failure waived without a round.** If your branch's base already fails a
  test, record the suite once in a clean checkout of the merge-base, for example
  `git worktree add --detach <dir> $(git merge-base HEAD <base>)` and then
  `prawduct-hook test-evidence record` there. The evidence store is shared by the clone, so the
  branch's next review, in any mode, waives a BLOCKING finding for that same failure itself, as
  long as your own tree's recorded run fails nothing new that no other finding names. The finding
  still shows on the record, marked waived and citing the base run. When a waiver does not fire,
  consolidation prints one line saying why. A repo whose base resolves to the `HEAD~1` fallback
  gets no waiver; set `base_branch:` in `.prawduct/project-state.yaml`.
