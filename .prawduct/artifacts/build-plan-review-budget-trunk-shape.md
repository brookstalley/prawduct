---
artifact: build-plan
version: 2
scope: review-budget-trunk-shape
branch: fix/review-budget-trunk-shape
backlog: brookstalley/prawduct#776
depends_on:
  - artifact: api-contract
governed_by:
  - artifact: api-contract
    dispositions:
      - "whole-surface semantic versioning; persisted data independently schema-versioned → inapplicable because this plan adds no subcommand and changes no persisted schema: the discriminator it needs (`actor.worktree`) is ALREADY written on 100% of the store's 966 review facts, earliest 2026-07-13, measured 2026-09-20. Had that field not existed the norm WOULD have applied, and the plan would be a schema-lock-in decision instead"
      - "exit codes are the contract; stable severity prefixes; errors attributed → conforms: exit 4's meaning is untouched ('the loop has run out while the gate may still be unsatisfied'). Only the derivability of its count changes"
      - "additive-first evolution; existing exit-code meanings never repurposed; deprecation signalled → conforms, with a recorded consequence: see [DECISION] below. No flag, `--json` key or exit code is repurposed; an exit code that was UNREACHABLE on one repo shape becomes reachable there"
partition: serial — one chunk
last_validated: 2026-09-20
---

## Requirements Confidence

**Level:** High

**Why:** The defect, its mechanism and its fix are each statable in one sentence, and all three were
verified against HEAD rather than taken from the item — `_round_budget_verdict`'s own docstring names
trunk-based merge-base zeroing as the reason the budget keys on SCOPE, then bounds the count by
`coverage.count_branch_rounds`, which admits a round only on `merge_base..HEAD` lineage. The owner
chose "make it fire on trunk" over "retract the claim" on 2026-09-20.

**Open assumptions / unknowns:**

`[ASSUMPTION: a trunk-shaped empty span and a fresh-branch-with-no-commits empty span should be
treated the SAME — both fall back to scope+worktree | MED impact | user can override]` They are
indistinguishable from the span alone (both have `merge_base == HEAD`). Treating them alike means a
brand-new branch resuming an existing scope inherits that scope's rounds from this worktree, which
is arguably correct because the budget's declared unit IS the scope — but it is a behaviour change
on branch-based repos too, not only trunk ones, and that is worth the reader's attention.

**What would raise confidence:** N/A for the fix. The assumption above is a scope call, not an
unknown — it is recorded so it can be vetoed, not researched.

## What I would do differently — the advisory obligation

**The approved fix, as I described it to the owner, was unsound as literally stated.** I said "count
by scope alone when the branch span is empty". `api-contract.md`'s exit-4 row records the lineage
intersection *with its reason* — the evidence store is clone-wide — and `count_branch_rounds`'s
docstring says the same: *"how many reviews exist" is not "how many this branch bought"*. Scope alone
would sweep in a sibling worktree's rounds on the same scope and overcount, and that docstring is
explicit that overcounting "says something false in the direction that discredits the whole message."
So the fix bounds by **scope + `actor.worktree`**, not scope alone. The owner approved a direction;
this is that direction implemented against a constraint the description had omitted.

**What I am deliberately NOT doing.** The deeper question is whether lineage was ever the right bound
or was always a proxy for worktree+scope — if the latter, the fallback should be the *primary* path
and the lineage intersection should go. I am not answering that here: it would change behaviour on
every branch-based repo (the common case) to fix one that is currently broken, and it deserves its own
item with its own measurement. This plan makes the control work where it does not work at all, and
leaves the working path alone.

**The cheaper alternative I rejected, and why.** #776 offered "retract the claim on three surfaces"
for less work. The owner chose the fix, and I agree: the review round budget is the loop's *only*
declared stopping rule, and a trunk-based consumer today has none — silently, which
`_round_budget_verdict`'s own docstring calls "the worst way for a control to be absent."

`[DECISION: ship the newly-reachable exit 4 with a consumer note rather than a deprecation cycle |
the additive-first norm's Why is protecting CALLERS across versions, and a trunk-based consumer's
caller has never been able to see a 4 from this path — but 4 is already documented, already emitted
on branch-based repos, and `--force` is its escape hatch, so no caller binds to its absence. Making
an inert control operative is the fix, not a side effect | user can veto/override]`

## Status

- [ ] Chunk 01: The round budget fires on the trunk shape, bounded by worktree
Context: Plan written 2026-09-20 on `fix/review-budget-trunk-shape` (branched from `develop` @
`225da107`, immediately after the v3.6.0 release). Nothing built yet. Next: Chunk 01.

## Build Chunks

### Chunk 01: The round budget fires on the trunk shape, bounded by worktree

- **Description:** `_round_budget_verdict` (`plugin/lib/critic_consolidate.py`) intersects this
  scope's review facts with the rounds `coverage.count_branch_rounds` attributes to this branch. That
  function admits a round only when its commit lies strictly after the merge-base on HEAD's lineage,
  so on a trunk-based repo — where every push makes `merge_base == HEAD` — the attributed set is
  empty, `spent` is 0, and exit 4 can never fire. Add a fallback: when the branch span is empty,
  bound the scope's facts by `actor.worktree` equal to this worktree instead of by lineage. The
  store is clone-wide, so the bound cannot simply be dropped.
- **Depends on:** nothing
- **Artifacts consumed:** `.prawduct/artifacts/api-contract.md` § Operations (the `critic-begin` 4
  row) and § Direction (all three norms, dispositioned in the frontmatter above).
- **Deliverables:**
  - `plugin/lib/critic_consolidate.py` — the trunk-shape fallback in `_round_budget_verdict`, with
    the reason for the worktree bound stated inline (not "because the span is empty" but "because the
    store is clone-wide and lineage is the only thing that was separating worktrees").
  - `plugin/lib/coverage.py` — only if `count_branch_rounds` must distinguish "empty span" from
    "unavailable" for the caller to branch correctly. Read it before editing: it already returns
    `{"status": "counted"|"unavailable"}` and a counted-but-empty result may already be
    distinguishable, in which case this file is untouched. **Do not edit it to add a signal it
    already carries.**
  - `.prawduct/artifacts/api-contract.md` — the exit-4 row's sentence *"Rounds are counted per
    build-plan scope (intersected with this branch's lineage, since the store is clone-wide)"*
    becomes true-as-written again by naming the fallback. This is **description tracking code**, not
    a norm amendment: the sentence sits in the operations description, and none of the three Direction
    norms is edited.
  - `plugin/templates/project-state.yaml` § REVIEW ROUND BUDGET — its comment currently says a
    branch-counted rule "could never fire" on trunk, offered as the reason the unit is the scope.
    After this chunk that reason is still right and the mechanism finally matches it; state what the
    fallback is so a consumer reading the template is not told a story about a control that used to
    be absent.
  - `.prawduct/change-log.md` — one entry, `scope=review-budget-trunk-shape`, untagged (it ships in
    the next release). **Do NOT touch the v3.5.0 change-log entry** that carries the same claim: it
    is released history, and rewriting it would restate what was true at that release as though the
    fallback had shipped then.
  - **Rider, and it is not scope creep:** #859's one-line fix — have `plan-backfill --apply` name the
    staging remedy in its output (`plugin/lib/plan_archive.py`). It rides this commit because this
    commit is judgeable and owes a review anyway, so the rider buys no round; deferring it to a round
    of its own would. It bit the v3.5.0 and v3.6.0 cuts identically.
- **Tests:** three, and the third is the one that makes the first two mean anything.
  1. **Trunk shape fires.** `merge_base == HEAD`, N full rounds recorded for one scope in this
     worktree, budget N → `critic-begin` exits 4. Red-verify by reverting the fallback.
  2. **A sibling worktree's rounds do not count.** Same scope, same empty span, rounds split between
     two `actor.worktree` values → only this worktree's are spent. This is the assertion that pins
     the design constraint rather than the behaviour: scope-alone passes test 1 and fails this one,
     which is exactly the forbidden implementation the frontmatter's disposition rules out.
  3. **Branch-based repos are unaffected.** A non-empty `merge_base..HEAD` span still counts by
     lineage, and a round from another worktree that IS on this branch's lineage still counts — so
     the fallback is proven not to have replaced the primary path.
- **Acceptance criteria:** all three tests green and each red-verified against the mutation it names;
  `test-status` exit 0 on a tree-vouched run; the two prose surfaces describe the shipped mechanism;
  no Direction norm edited.
- **Type:** cumulative-final
- **Critic mode:** inferred — do NOT declare one. One chunk, and nothing this branch touches is in
  `risk_surfaces:` (`plugin/lib/critic_consolidate.py`, `coverage.py` and `plan_archive.py` are none
  of `gates*`, `*hook*` or `skills/`), so the roster stays the standard one and the plan owes a single
  boundary `cumulative`. **This session switched branches after SessionStart, so pass the mode
  explicitly at dispatch rather than trusting `infer-critic-mode`'s stale marker.**
- **Done when:**
  1. Three tests green, each red-verified by the mutation its bullet names
  2. Committed, then `/prawduct:critic cumulative` run and every blocking finding resolved
  3. Chunk marked `[x]` — after the review, because the last tick disarms the Stop gate
  4. #776 → `shipped` and #859 → `shipped` through `/prawduct:backlog`

## Verification Strategy

Beyond the tests: build a throwaway trunk-shaped repo (one branch, `base_branch` equal to it, rounds
recorded past the budget) and run `critic-begin` in it, confirming a 4 and the census it renders. The
unit tests assert the count; only an end-to-end run confirms the refusal path the count feeds still
works when the count finally becomes non-zero — the gap between "my new input is correct" and "the
gate answers differently" is the one `core.md` names as the expensive one.
