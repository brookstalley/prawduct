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
re-run consolidation. The Critic skill and the coordinator carry the remedy in one sentence each.

**An inherited red baseline (#900).** The owner ruled auto-waive on 2026-10-21. A test-run fact
now carries the failing test ids, with the same cap as the per-worktree record. A reviewer lists
the ids a test-failure finding rates in an optional `failed_tests` field. A new classifier,
`evidence.inherited_failures`, finds the newest suite run on the merge-base tree; it matches the
tree, not the head, and skips narrowed runs. After the review fact is appended, consolidate takes
each BLOCKING finding whose every named id that run also failed and writes a `waived` resolution
fact for it, with `origin: inherited-baseline` and `base_run`.

The finding stays BLOCKING on the record. Both the PR gate and the Stop gate read the waiver as
resolving it, and the NEXT-ACTION line names waived findings first instead of asking for a fix.
Any id missing from the base run, no run on that tree, or a newer green run there means no
waiver, and the finding blocks as before. `data-model.md`, `review-cycle.md`, `building.md` and the
module docstrings now state the resolution rule with this second origin.

`tests/test_critic_consolidate.py` carries both halves. For #961: a three-role roster with one
malformed partial leaves the other two byte-identical, the verb and consolidate agree on the same
file, and a rewrite of only the bad partial consolidates. For #900: the waiver, every no-waiver
case in the item's acceptance, the idempotent re-run, and a base run recorded from a real detached
worktree of the merge-base. `tests/test_test_run_facts.py` pins the run fact's `failed_tests`.
Reviewer payload budgets rose by declaration in `tests/test_reviewer_payload_budget.py`, each
raise with its reason, and methodology prose budgets rose in `tests/test_v5_methodology.py`.

## Consumer note
- **A failing reviewer partial no longer costs the whole round.** When `critic-consolidate`
  refuses one, its message names the role and gives the remedy: re-dispatch that one reviewer.
  Do not start a new review.
- **Reviewers check their own partial.** They now run `prawduct-hook validate-partial` before
  returning, so a malformed partial is usually caught before consolidation.
- **Getting an inherited failure waived without a round.** If your branch's base already fails a
  test, record the suite once in a clean checkout of the merge-base, for example
  `git worktree add --detach <dir> $(git merge-base HEAD <base>)` and then
  `prawduct-hook test-evidence record` there. The evidence store is shared by the clone, so the
  branch's next review waives a BLOCKING finding for that same failure itself. The finding still
  shows on the record, marked waived and citing the base run.
