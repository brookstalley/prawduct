---
artifact: build-plan
version: 2
scope: review-interval-extension
branch: feature/167-review-interval-extension
backlog: brookstalley/prawduct#167
depends_on:
  - artifact: review-loop-nontermination-diagnosis
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → inapplicable, because no chunk touches a reviewer write path"
      - "authority fails closed; advice fails soft → engaged, conforms: no refusal is added and none is weakened on weak evidence. The Stop gate's block becomes an advisory only while a later review is owed on the gate plan, the same evidence short-plan deferral already rests on, and the PR gate stays authoritative. The merge-base condition relaxes a verdict only where composition itself proves coverage"
      - "local-first: no network, no daemon, no third-party dependency → conforms: git and the local evidence store only"
      - "the plugin writes nothing into a governed repo except its own state → conforms: one optional field on the manifest and the review fact"
      - "Python-written, never Python-specific → conforms: trees and paths only"
      - "prawduct guides and reviews; it never implements → conforms: the change is to when review is owed, not to product code"
      - "goals and verification bind; prescribed method is advice → conforms: the design's method is a best guess and the chunks record any departure"
      - "every fact has one home → conforms: the covered frontier is one function, `gates.covered_frontier(project_dir)`, read by `critic-begin` (and, from Chunk 2, the Stop gate's deferral). The Stop gate and `cost-of-commit` ask a different question, merge-base → working-tree composition, and both now ask it through one function, `gates._merge_base_verdict`"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 → the purpose: removes verify rounds bought for non-blocking fixes while a later review is owed (63 of 150 measured)"
      - "proportionality ratchets both ways; a control names its yield and emits it → conforms: `base_extended_from` on each manifest and review fact counts the rounds this saves; the Stop advisory carries `DEFERRED_REVIEW_TOKEN`"
      - "state-file growth is advisory → inapplicable, because no state file grows beyond one optional key per fact"
      - "review rigor is stage-keyed → engaged, conforms by interpretation (recorded here, owner-visible): an extended `chunk`/`final` review is still inner stage. The norm names the inner stage as `chunk`, `final`, `verify-resolutions`; `verify-resolutions` already reviews a committed fix delta at the inner stage, and extension moves that same delta into the next inner review. The boundary stage (`cumulative`, PR review) is untouched"
  - artifact: data-model
    dispositions:
      - "verdicts computed from the append-only fact ledger → conforms: the frontier and both gate answers are computed from review facts"
      - "facts immutable and append-only → conforms: one new optional key, written once at append"
      - "derived views never authoritative → conforms: no gate reads `.critic-findings.json`"
      - "a governance document reaches a terminal state, never deleted → inapplicable, because no chunk archives or deletes a governance document"
      - "backlog issue titles follow the issue standard → inapplicable, because no chunk writes a backlog item"
      - "a newer-schema fact is a loud block → conforms: the key is additive, so `evidence.SCHEMA_VERSION` stays 1 and older readers ignore it"
      - "two stores, two lifetimes → conforms: nothing new is stored outside the evidence store"
      - "`backlog_service_repo` selects the authoritative backlog → inapplicable, because no chunk reads the backlog"
  - artifact: api-contract
    dispositions:
      - "whole-surface semantic versioning; persisted data independently schema-versioned → conforms: optional fact key, no schema bump"
      - "exit codes are the contract → conforms: no exit code changes meaning; `infer-critic-mode` gains a trigger for its existing `deferred` answer"
      - "additive-first evolution → conforms: no flag, exit code or `--json` key is repurposed; the manifest and fact gain `base_extended_from`"
partition: serial — every chunk edits `critic_consolidate.py` or the gates that read its facts
last_validated: 2026-09-22
---

# Build plan — let the next review cover a non-blocking fix (#167)

Design: `documentation/issues/167-interval-extension-design.md` (owner-approved 2026-09-22,
including its two open questions: extend over any uncovered committed work, not only fix churn;
and extend `final` as well as `chunk`).

## Requirements Confidence

**Level:** High

**Why:** the opportunity was measured on 2026-09-22 against the fleet's evidence stores (the #724
comments hold the scripts). The previous attempt's failure is recorded with numbers in the archived
`build-plan-review-convergence.md`. A boundary investigation of every consumer that could assume a
`chunk` review starts at HEAD found exactly one that breaks (the Stop gate's session-anchored
composition), and the fix for it ships in Chunk 1.

**Out of scope:** `cumulative` incrementality (the diagnosis doc's RC4); churn grants; any change to
`verify-resolutions`; BLOCKING handling; the PR gate.

`[ASSUMPTION, corrected by Chunk 1's review: the covered frontier is searched along first-parent
history from HEAD back to the merge-base. A base sync does NOT preserve the frontier: the merge-base
becomes the new base tip, and a pre-sync review composes from it only across a non-judgeable
advance. After a judgeable sync nothing is a frontier and the interval stays at HEAD until a review
spans the sync. That is today's behaviour, not a regression; the base-advance transfer that would
carry it across belongs to `gates._merge_base_verdict` | MED impact | owner can correct]`

## Chunk 1: A chunk/final review starts at the covered frontier, and the gates can see it

**Delivers:**
- `gates.covered_frontier(project_dir)`: the newest commit on HEAD's first-parent history (HEAD back
  toward the merge-base) whose tree composition reaches from the merge-base tree with zero
  unresolved blockers **through at least one review**, or `None`.
  **Departure from this plan's first draft, recorded:** the draft named `coverage` and a `facts`
  argument. The function lives in `gates` because it needs `_store_precheck`, `_cached_diff_fn` and
  `_tree_key_fn`, and it reads the store itself, like every other gates verdict. A frontier reached
  by free edges alone (nothing on the branch reviewed yet) is not a frontier, which keeps the draft's
  "no prior review: today's interval" criterion. An intermediate build extended to the merge-base in
  that case; the Chunk 1 review found it made the first inner-stage review a whole-branch review,
  and it was removed.
- `critic-begin`, `chunk`/`final`: when the frontier exists and is not HEAD's tree, the base is the
  frontier tree, and the manifest and review fact carry `base_extended_from` (the frontier tree;
  null otherwise). `commit_reviewed` stays the dispatch commit; `base_commit` is the frontier's
  commit.
- The Stop gate's session coverage and `gates.commit_coverage` also accept coverage composing from
  the merge-base tree to their target tree (additive, relax-only). The Stop gate already did this
  from a session-base marker; it now does it from the HEAD fallback too, and `commit_coverage` calls
  the same `_merge_base_verdict`.

**Done when:**
- End to end on a real repo fixture: review → commit a non-blocking fix → dirty next-chunk work →
  `critic-begin --mode chunk` spans frontier → working tree; the consolidated fact composes, so the
  Stop gate and `check-cumulative-critic` both answer covered with no verify round, where they
  answered uncovered before.
- An unresolved blocker on the path: no extension, today's behaviour.
- No prior review, or the frontier is HEAD: today's interval, `base_extended_from` null.
- The session-base scenario from the design (fix committed in an earlier session) is covered by the
  merge-base condition, with a test that is red without it.
- Existing tests pinning `base_commit == head` for chunk are renegotiated in the open.
- Targeted tests green.

## Chunk 2: Nothing tells the builder to buy the round

**Delivers:** the Stop gate prints the deferral advisory, not a blocker, when session changes are
`uncovered`, the frontier path has zero unresolved blockers, and the gate plan has an unticked
chunk. At the last chunk it still blocks. `infer-critic-mode` answers `deferred` for a clean tree
mid-plan after a non-blocking fix. The review close's NEXT-ACTION leads with carry-on when a later
review is owed. `cost-of-commit` prices such a commit as riding the next review.
`_widened_fallback_mode` stops claiming `final` cannot see committed work.

**Done when:** each changed message has a test on its rendered text (both directions: mid-plan and
last chunk); targeted tests green.

## Chunk 3: The docs say what the code now does

**Delivers:** the prose cascade listed in the design's "Prose that becomes false", reworded in place
under the reviewer-payload token ceilings; the backlog item's stage moves forward.

**Done when:** a grep for the "uncommitted diff" descriptions of `chunk`/`final` returns only true
sentences; suite green; one `cumulative` review of the branch (short plan: the boundary review is
the plan's review).

## Status

- [ ] Chunk 1: A chunk/final review starts at the covered frontier, and the gates can see it
- [ ] Chunk 2: Nothing tells the builder to buy the round
- [ ] Chunk 3: The docs say what the code now does
