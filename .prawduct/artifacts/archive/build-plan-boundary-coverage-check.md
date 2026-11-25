---
artifact: build-plan
version: 2
scope: boundary-coverage-check
branch: feature/boundary-coverage-check
base: develop
working-branches: []
last_validated: 2026-11-23
depends_on:
  - artifact: nonfunctional-requirements
  - artifact: architecture
  - artifact: api-contract
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is a P0 constraint → conforms: the op runs no review and adds no round; it measures where the per-PR boundary review is spent, which wave 2 needs before it changes the review"
      - "proportionality ratchets both ways (a new control names its yield) → conforms: yield is the count of release-pending merges with no boundary coverage, read by the release operator in check-releasability and by the wave-2 decision; advisory, so it cannot buy a round"
      - "state-file growth is advisory → inapplicable because the op writes no state"
      - "review rigor is stage-keyed; the boundary is never skipped or inferred away → conforms: this plan changes no stage, mode or gate; the amendment is wave 2's (owner ruling 2026-11-23, decision 2)"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → inapplicable because the op is not a reviewer"
      - "authority fails closed; advice fails soft → conforms: the op is advice; an unevaluable merge reads `unknown`, never `covered`, and the check-releasability line never changes its exit"
      - "local-first: process-spawn, atomic files, the git object database → conforms: git and the local evidence store only"
      - "the plugin writes nothing into a governed repo but its own state → conforms: read-only"
      - "never specific to Python → conforms: judgeability is coverage_algebra.is_judgeable_path, language-agnostic"
      - "prawduct guides and reviews; it never implements → inapplicable because this is framework code"
      - "goals and verification bind; prescribed method is advice → conforms: chunk routes below are forecasts"
      - "every fact has one home → conforms: coverage composes through coverage_algebra, stage through critic_consolidate.STAGE_*, the pending set through release_readiness.pending_scopes; the op owns only its classification"
  - artifact: api-contract
    dispositions:
      - "whole-surface semver; CLI subcommands carry no per-subcommand version → conforms: a new subcommand, patch-level"
      - "exit codes are the contract; stable severity prefixes; errors attributed → conforms: exit 0 answered (any classification), 3 could not evaluate; NOTE:/WARNING: prefixes only"
      - "additive-first evolution → conforms: a new op and a new check-releasability line; no existing flag, exit or --json key changes"
partition: serial — 02 reads 01's classification and its --json, and both chunks edit plugin/bin/prawduct-hook's dispatcher
lifecycle: completed
archived: 2026-11-25
released_in: v3.10.0
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

## Goals

**Response taken:** Proceed citing a spec. The spec is `documentation/issues/1222-1223-design.md`, accepted 2026-11-23 ("Yes to all", `.prawduct/owner-rulings.md`). Its decision 5 is this plan: one `check-boundary-coverage` op, called by `check-releasability` and the PR skill's release guard, shipped advisory first to count uncovered merges. The owner said "and the 1223" on 2026-11-23.

**Product:** #1223 asks for a small-feature lane: an inner review per feature, and the boundary review once per release batch. That is safe only if something at the release can say which merged work no boundary review read. This plan builds that instrument, advisory, so its counts exist before wave 2 changes any review. #1223 names a consumer repo that releases several times a day. In this repo, which stays `per_pr` (decision 4), the counts should be near zero.

**Architecture:** One question gets one owner. For each release-pending scope, was the merge that brought it in covered by a boundary review, at its PR or by a batch review spanning it? Wave 2 makes that answer blocking for a `per_release` repo (decision 1: the deferral ships only together with the release check), so its classification must be strict now. Advice may be wrong in the safe direction (`uncovered`/`unknown`), never in the other (`covered`).

**Constraints:** Read-only. Uses the existing evidence store, the coverage algebra and the pending-scope set; no new persisted format. Ships advisory: no exit code changes anywhere, check-releasability included.

**Tradeoffs accepted:**
- A squash-merged PR has no second parent to read a branch tip from, and git cannot tell it from work committed on the base, so it reads `direct` with a reason naming both. This repo merges with merge commits; revisit if a consumer squashes.
- Only commits that ADD a pending fragment are classified. A judgeable commit on the base that adds none (a direct fix, or a PR merged outside `/prawduct:pr` with no change record) is invisible, so the count can read "N of N covered" over unreviewed work. Finding every first-parent commit since the last release needs a release anchor on `develop`, which pruned single-parent promotions don't give. Wave 2 must build that anchor before this answer gates anything (recorded on #1232). Advice can carry the limit; a gate cannot.
- The PR skill's release guard gets prose naming the op, not a new gate. It is advice and the skill already stops there; wave 2 decides whether that stop becomes a check.

**Inferred at build time; the owner accepted all three as written on 2026-11-24 (`.prawduct/owner-rulings.md`):**
- *Inferred:* the release unit is the pending fragment set, not the commits since the last tag. Releases here are single-parent tree-set promotions, so `main`'s tags are not ancestors of `develop`, and "did this ship" is about tree content (release learnings). Each pending fragment is joined to the first-parent commit on the integration branch that added `.prawduct/changes/<scope>.md`. That commit is the merge to classify, or a direct commit, which has no PR boundary.
- *Inferred, and a correction to the design doc §3:* boundary coverage is NOT "coverage composed from boundary-stage facts only". Almost every PR here ends with a cumulative followed by an inner-stage `verify-resolutions` over the fix commits. A boundary-only composition calls 7 of this repo's 14 pending per-PR merges uncovered (prototype, 2026-11-23). A `verifies` link can't mark the tail either, because older verify facts don't carry one (#1221's reads `None`). The rule: a span `S → H` is boundary-covered when `coverage_verdict` over all facts is `covered`, and some boundary-stage review `B` gives both halves:
  - boundary-stage edges alone compose `S → B.head_tree`;
  - `verify-resolutions` and free edges alone compose `B.head_tree → H`.

  A tail of new chunk reviews after a boundary review therefore does not pass: only fix verification may follow the boundary. On this repo the prototype classifies all 14 pending per-PR merges `pr-covered`. Candidate `B`s are bounded to reviews whose head tree is a tree of the branch's own commits, because looping over every boundary review in the store cost 15s for 15 scopes.
- *Inferred:* a merge is `batch-covered` when some blocker-free boundary-stage review's base and head trees bracket it on the integration branch's first-parent line (base at or before the merge's first parent, head at or after the merge). The design's "relax-only rule" calls this; it adds nothing that coverage_verdict would refuse, because the merge's own span is not composed through it.

**Decisions made mid-build:**
- Chunk 01: a squash merge reads `direct`, not `unknown`. A squash commit has one parent, like work committed on the base, and the classification can't tell them apart; both are "no PR boundary on record". Settled by the Goals' strictness rule: the reading says not-covered either way.
- Chunk 01: `pr-covered` also requires the composition over ALL facts to be covered, not only the restricted halves. An inner review's open blocker at the tip blocks the PR gate, so it must block this reading too. The surviving mutant of the sweep found this, and it is pinned.
- Chunk 01 review round 1: the pending fragment joins to its NEWEST adding commit (a release deletes shipped fragments, so a reused scope is pending through its latest add). Refused fragments are named in the report, not dropped. Facts a newer plugin wrote make the report unevaluable, since one could be a review with an open blocker. The #1231 real-store test is `requires_local_cache`, because the evidence store is per clone and never committed.
- Boundary review (rev-20261124T044504Z-ac4ab539) fixes, each red-verified:
  - the advice has a fault boundary in check-releasability, and malformed boundary facts are skipped;
  - a batch review must span the merge on its own;
  - a merge commit's own judgeable edits block `pr-covered`;
  - a dirty-tree cumulative can split the span;
  - short commit names are resolved, and octopus merges read `unknown`;
  - `-m` on the fragment lookup is for git before 2.31 (a survivor on modern git, by design);
  - not-covered lines are marked by the code's covered set, which the docs point at;
  - `uncovered` names `evidence sync`.

  The native review's rename claim did not hold: a path-limited log never pairs the moved fragment with its source, so `--no-renames` changed nothing, and a test pins the moved-fragment case instead.
- Chunk 02: check-releasability prints no refused-fragment line. It runs below that gate's own refusal return, so a refused fragment never reaches the advice, and a line for it would be unreachable.
- Chunk 02: the count line has one owner, `boundary_coverage.count_line`, read by the op's report and by check-releasability, rather than being sliced out of the rendered report by position.
- Chunk 01: exit 0 whenever the op answered and 3 when it could not evaluate (no base, an unreadable change record or store), per the api-contract exit scheme. The op is in `_EPHEMERAL_SAFE_COMMANDS` because it writes no repo state; the shared tree-key cache it updates is the same write `check-cumulative-critic` makes.

**Level:** High for the per-PR reading: a prototype over this repo's 15 pending scopes reproduced the known history (14 per-PR merges covered, and the v3.9.0 release-bookkeeping commit `direct`). Medium for `batch-covered`, which no history here exercises; only its fixture proves it, until wave 2 runs a batch review.

**Wave 2 (not this plan):** the `boundary_review: per_pr | per_release` key, derived eligibility, inference answering `chunk` at a lane-eligible last chunk, the blocker-free tail deferral, the NFR amendment, a release batch review, and this op turning blocking under `per_release`. It is filed as a backlog item when this plan lands, `blocked_by` this scope, with the counts this op produces as its entry evidence.

## Scaffolding

Not applicable: framework code in an existing runtime. Tests run with `testament run` (`documentation/running-tests.md`), evidence with `prawduct-hook test-evidence record`.

### Verification Strategy

Run the op against this repo after each chunk and read the human output as an operator would at a release. The reading must be right for merges whose history is known: this session's #1231, and a doc-only merge. Then run `check-releasability` and confirm the new lines read correctly next to its existing output, with the exit unchanged.

## Build Chunks

### Chunk 01: `check-boundary-coverage` classifies each release-pending merge

- **Description:** A new `lib/boundary_coverage.py` and a `check-boundary-coverage [--json]` op. For each scope in `release_readiness.pending_scopes`, find the first-parent commit on the integration base (`resolve-base`) that added its fragment, then classify it:
  - `no-judgeable`: the merge's span changes no judgeable file;
  - `pr-covered`: boundary coverage, as defined in Goals, composes from `tree(merge-base(M^1, M^2))` to `tree(M^2)` with zero unresolved blocking;
  - `batch-covered`: a blocker-free boundary review brackets M on first-parent;
  - `inner-only`: coverage composes only with inner-stage edges;
  - `uncovered`: nothing composes;
  - `direct`: the fragment landed in a non-merge commit that changes a judgeable file (judgeability is asked first, for direct commits too, so release bookkeeping on `.prawduct/` reads `no-judgeable`);
  - `unknown`: no adding commit (not merged yet, or the fragment is untracked), or git or the store unreadable.

  Each classification carries its reason. Human output is one line per scope plus a count line naming the denominator. `--json` is the same data, keyed for wave 2.
- **Depends on:** none
- **Artifacts consumed:** `documentation/issues/1222-1223-design.md` §3–§4; the Goals inferences above
- **Deliverables:** the op, its lib owner and its tests.
  - A real-git fixture repo drives each classification, including:
    - a cumulative followed by a verify (`pr-covered`);
    - chunk reviews only (`inner-only`);
    - a squash (`direct`, its reason naming the squash);
    - a review with an unresolved blocker (never `pr-covered`);
    - a batch review bracketing an uncovered merge (`batch-covered`).
  - One test reads this repo's real history and store and asserts the classification of a merge whose coverage is known. It is not a fixture; tests rule: a predicate over real artifacts reads one.
- **Tests:** unit over the fact-restriction and bracket predicates; integration over the fixture repo through the CLI (the layer the op is used at); the real-repo test; exit-code contract (0 answered, 3 unevaluable store or base).
- **Acceptance criteria:** every classification is reachable from the CLI on a fixture and red under a mutant of its predicate. The restricted fact set is pinned so that a chunk-only path never reads `pr-covered`. On this repo the op names #1231's merge `pr-covered`.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed (`feat(boundary-coverage-check): … (Chunk 01)`)

### Chunk 02: release surfaces read it, advisory

- **Description:**
  - `check-releasability` prints the op's count line and one `NOTE:` per merge that is not covered or not judged (`inner-only`, `uncovered`, `direct`, `unknown`), next to its other advisories. Its exit is unchanged; a test pins that.
  - The PR skill's release-promotion guard names the op as the thing to read before handing back to the release process.
  - `documentation/release-process.md` gets the step.
  - The op's entry goes wherever this repo's CLI surface is listed: grep the dispatcher's op set, `allowed-tools` grants and the docs that enumerate ops.
- **Depends on:** Chunk 01
- **Artifacts consumed:** `plugin/skills/pr/SKILL.md` release-promotion guard; `documentation/release-process.md`
- **Deliverables:** the check-releasability lines and their test, the skill and doc prose, the op's registration everywhere the op set is enumerated, and the change fragment.
- **Tests:**
  - check-releasability on a fixture with one uncovered merge prints the NOTE and exits as before; the control has none.
  - The release guard's prose names an op the dispatcher has.
  - The existing op-set and grant tests are extended, not bypassed.
- **Acceptance criteria:**
  - `check-releasability` on this repo prints the new lines and its exit equals develop's.
  - Every enumerated op list includes the op.
  - The wave-2 backlog item is filed with this op's first counts from this repo.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved

## Early Feedback Milestone

**Milestone chunk:** 01
**What the user can do:** run `prawduct-hook check-boundary-coverage` on this repo and read which pending merges a boundary review covered.

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk after its review. The branch changes `plugin/bin/prawduct-hook` and `plugin/skills/`, both declared risk surfaces, so this is not a short plan: Chunk 01 gets an inner review and Chunk 02's cumulative is the PR gate.

- After Chunk 01: check the classification against this repo's real merges before anything reads it.
- At Chunk 02 (cumulative): the full bundle, including whether the Goals inferences hold.
