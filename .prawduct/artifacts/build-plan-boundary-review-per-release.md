---
artifact: build-plan
version: 2
scope: boundary-review-per-release
branch: feature/boundary-review-per-release
base: develop
working-branches: []
last_validated: 2026-11-25
depends_on:
  - artifact: nonfunctional-requirements
  - artifact: architecture
  - artifact: api-contract
  - artifact: data-model
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is a P0 constraint (cost = unit-cost × run-count) → conforms: the lane cuts run-count (one boundary review per release batch instead of per PR, and no verify round for a blocker-free fix tail) in an opted-in repo; the yield claim is #1223's and #1222's ledger figures, re-measured by Chunk 02's op in the consumer repo before Chunks 03-06 proceed"
      - "proportionality ratchets both ways (a new control names its yield) → conforms: the new control is the blocking release check under per_release; its yield is the count of release-pending merges it holds back, printed by check-releasability on every run (the wave-1 count line), so it can be judged"
      - "state-file growth is advisory → inapplicable because nothing here writes state; the anchor and every classification derive from git and the existing evidence store"
      - "review rigor is stage-keyed; the boundary runs everything and is never skipped or inferred away → amendment confirmed by the owner 2026-11-25 (decision 1 below, owner-rulings.md); Chunk 01 records it beneath the clause, which keeps its ratified words"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → conforms: the release batch review is an ordinary Critic dispatch with a new interval; no reviewer gains a write"
      - "authority fails closed; advice fails soft → conforms: per_pr keeps the op advisory; under per_release every degradation (no anchor, unreadable store, octopus, squash, unknown) reads not-covered and the gate refuses; an unreadable `boundary_review:` reads per_pr, the stricter policy"
      - "local-first: process-spawn, atomic files, the git object database → conforms: the anchor is a git query; no network, no daemon"
      - "the plugin writes nothing into a governed repo but its own state → conforms: the op stays read-only apart from the tree-key memo check-cumulative-critic already writes"
      - "never specific to Python → conforms: judgeability is coverage_algebra.is_judgeable_path; the anchor reads a release file and version tags, neither language-specific"
      - "prawduct guides and reviews; it never implements → inapplicable because this is framework code"
      - "goals and verification bind; prescribed method is advice → conforms: chunk routes are forecasts; the acceptance criteria bind"
      - "every fact has one home → conforms: the policy has one reader (review_lane.boundary_review_policy), lane eligibility one predicate (critic_mode.lane_eligibility, composing short_plan_deferral), the tail deferral one predicate in gates.py read by the PR gate and the Stop gate, the release classification stays boundary_coverage's, and the relax-only batch rule lives with the other composition rules in coverage_algebra"
  - artifact: api-contract
    dispositions:
      - "whole-surface semver; no per-subcommand version → conforms: a minor (a new key, a new flag, a gate a consumer can opt into)"
      - "exit codes are the contract; stable severity prefixes; errors attributed → conforms: check-boundary-coverage keeps exit 0 answered / 3 unevaluable; the blocking reading is a new `--gate` flag (exit 1 = not covered under per_release); check-releasability's refusal gains a named reason code"
      - "additive-first evolution → conforms: no exit meaning is repurposed (hence `--gate` rather than changing the bare op's exit); --json gains keys (`source`, `anchor`) and classes, never renames one"
  - artifact: data-model
    dispositions:
      - "verdicts from the append-only fact ledger, no model in a fact's write path → conforms: the batch review's fact is consolidated like any review; its interval is code-derived"
      - "facts are immutable and append-only → conforms: no fact is edited; a batch review's blockers clear through resolution facts"
      - "derived views are never authoritative → conforms: no gate reads .critic-findings.json"
      - "a governance document is archived, never deleted → inapplicable because no document is retired"
      - "backlog title rules → inapplicable because nothing writes the backlog"
      - "a newer-schema fact blocks loudly → conforms: the op's schema-ahead refusal stands and, under per_release, refuses the release"
      - "two stores, two lifetimes → conforms: the policy is a committed answer (project-state); the anchor is derived, never cached as a committed field"
      - "backlog_service_repo selects the store → inapplicable because nothing reads the backlog"
partition: "01 ∥ 02 (01: lib/core.py key constant, new lib/review_lane.py, templates/project-state.yaml, docs/project-state-keys.md, the NFR; 02: lib/boundary_coverage.py and its tests; 02 starts only after #1250 is on develop) → 03 ∥ 04 (03: lib/coverage_algebra.py new pure rule, lib/boundary_coverage.py batch rule, lib/critic_consolidate.py begin_review release interval, prawduct-hook cmd_critic_begin; 04: lib/critic_mode.py, the Stop-gate critic block in prawduct-hook, skills/critic/SKILL.md + review-cycle.md) → 05 (lib/gates.py tail deferral, the same Stop-gate block after 04, skills/pr/SKILL.md Step 2) → 06 serial last (lib/release_readiness.py, prawduct-hook cmd_check_boundary_coverage, skills/pr/SKILL.md release guard, documentation/release-process.md, the release runbook, api-contract). The integrator owns every merge into plugin/bin/prawduct-hook and the whole-tree guard tests (prose budgets, op-set and grant tests, the key-reference test). Sequence against #1247: Chunk 04 never builds concurrently with #1247's inference change"
---

## Goals

**Response taken:** Proceed citing a spec, with six owner decisions batched below. The spec is
`documentation/issues/1222-1223-design.md`, accepted 2026-11-23 ("Yes to all",
`.prawduct/owner-rulings.md`), decisions 1-4; decision 5 shipped as wave 1 (#1233,
`check-boundary-coverage`), decision 6 as `free-interval-warnings`. The "covered" definition this
plan gates on was accepted on 2026-11-24 ("Yes agreed"): a boundary prefix plus a verify-only tail,
the composition over all facts also `covered`, with wave 1's three inferences
(`archive/build-plan-boundary-coverage-check.md` Goals). Issue: #1232.

### Owner decisions (all six confirmed as recommended, 2026-11-25: "yes to all of your recommendations", `.prawduct/owner-rulings.md`)

1. **Confirm the NFR amendment text, as written.** It is recorded beneath the stage-keyed clause in
   `nonfunctional-requirements.md`; the clause keeps its ratified words. *Recommend:* confirm.
   Proposed text:

   > Amended (proposed, #1232): a repo that declares `boundary_review: per_release` runs the
   > boundary review for **eligible** work once per release batch rather than once per PR.
   > Eligible is derived, never declared: the branch's plan is short (at most three chunks, none
   > declaring `Critic mode:` or `Type: cumulative-final`), nothing it changed is a risk surface,
   > and it changes at most N judgeable files (decision 4). That work's PR is covered by its inner
   > review, and its boundary review is **moved, not skipped**: the release check refuses the
   > release until a boundary-stage review has read every merge since the last release, at its PR
   > or in a release batch review. In the same repo, a fix tail after a blocker-free review may
   > merge before a review reads it, as a deferral to that same release check, never as coverage.
   > BLOCKING findings clear only through `verify-resolutions`, at either point. The default is
   > `per_pr`, where this clause binds unchanged.

2. **The release anchor (#1232 requirement 1).** *Recommend option A+B:* the anchor is whichever of
   these sits nearest the base's tip on its first-parent line: (A) the newest first-parent commit
   that adds a release file under `.prawduct/releases/` (prawduct's cut writes one; here that is
   `436f44d3 release: prep v3.10.0`), or (B) the oldest first-parent commit containing the newest
   version tag reachable from the base (classic gitflow back-merges and trunk repos). With neither,
   there is no anchor: advice says so; a per_release gate refuses. **Amended 2026-11-26 (owner ruling):** B is the oldest first-parent commit of the base
   containing the merge-base of the base and the newest version tag, so a release tagged on a merge
   commit the base never sees (the consumer repo tags `v2.22.0` on `main`) anchors on the develop
   commit it released; where the tag is reachable the answer is unchanged. Options weighed, from how
   v3.10.0 was actually cut here:
   - **A, the release file.** Observable, already committed, written by the cut in both the
     whole-develop and the pruned path (Phase 1 lands on `develop` either way). Misses a repo that
     does not cut through `cut-change-log`; the consumer repo below has no release files.
   - **B, a reachable tag.** Works wherever the tag reaches the base. Here it never does:
     promotions are single-parent commits on `main`, so `v3.10.0` is not an ancestor of `develop`.
   - **C, tree identity** (the first-parent commit whose tree equals the newest tag's tree). True
     here today (`436f44d3` and the tag commit `e9c06c07` share tree `d5ee1aef…`), but a pruned
     promotion's tree exists on no `develop` commit, so it fails exactly where the gap is.
   - **D, a recorded fact** (the cut appends a fact or a project-state field naming the commit).
     Stored state that can be forgotten or lost per clone; A already is the recorded fact, in git.
   - **E, commit-subject conventions** (`release: prep`, `release: reopen develop`, or the
     `release-vX.Y.Z` reopen fragment). Prose matching, and specific to this repo's runbook.

   The walk then classifies every judgeable first-parent commit after the anchor, **unioned** with
   wave 1's pending-fragment join, so a scope withheld by a pruned release (merged before the
   anchor, still pending) stays classified.

3. **Release bookkeeping commits on the base.** The reopen commit (`c9b58e4e`, version files plus
   a fragment) follows the anchor and reads `direct`, so under per_release every release would
   need a batch review just for it. *Recommend:* a single-parent commit whose judgeable changes
   are all paths the repo **declares** in `release_version_files:` reads `release-bookkeeping`,
   counted covered. Undeclared (the fallback layout guess) does not qualify.

4. **The judgeable-file bound for eligibility.** *Recommend:* 10, a constant beside
   `SHORT_PLAN_MAX_CHUNKS`, not a key. The design's measured fix deltas had a median of 4 and a
   p90 of 11 judgeable files; #1223 describes the lane's work as "a few hundred lines". Revisit
   from Chunk 02's counts in the consumer repo.

5. **Scope of the fix-tail deferral (decision 1).** The ruling does not tie it to eligibility.
   *Recommend:* it applies to any PR in a per_release repo, lane or not, when the tail meets
   `diagnose_fix_churn`'s conditions **and** touches no risk surface. A tail on a risk surface
   still buys its verify round.

6. **Run the pay test before Chunks 03-06.** *Run and ruled 2026-11-26: go on Chunks 03-06* (counts and
   method in `.prawduct/owner-rulings.md`; read from the consumer repo's ledger and git, the op not run there). #1232 says the consumer repo's counts decide whether
   the lane pays. Wave 1's op cannot answer it there (it classifies pending fragments only, and that
   repo has two). *Recommend:* build Chunks 01-02, run Chunk 02's op in that repo (command under
   Verification Strategy), and take go/no-go on 03-06 from its per-merge counts.

### Inferred design calls (made on the owner's behalf; the boundary review should check each)

- *Inferred:* `boundary_review:` is read from `project-state.yaml` **at the merge-base with the
  integration branch** (the `coverage.integration_base` / `_state_in` pattern
  `static_content_prefixes` uses), so a branch cannot opt itself into the lane: a governance change
  cannot supply its own authority. The release check reads it at the base tip. A value it cannot
  read, or any value but `per_release`, is `per_pr`.
- *Inferred:* eligibility reuses `short_plan_deferral`'s shape conditions (`_short_plan_shape`: chunk
  count, no `Critic mode:`, not on the base, no risk surface by `risk.paths_touch_risk_surface`;
  decision M14), adds the
  judgeable-file bound over merge-base…working tree, and treats `Type: cumulative-final` as an
  opt-out, because that declaration names a boundary review.
- *Inferred:* the lane's review at the last chunk is `chunk` over the whole branch: commit the last
  chunk, then inference answers `chunk`, whose interval on a clean tree starts at the covered
  frontier or the merge-base (`critic_consolidate.working_tree_interval_base`). It must name every
  open built chunk (`--chunks`), as the boundary cumulative does today, or `critic-begin` exit 8
  refuses it. An explicit `/prawduct:critic cumulative` still buys the per-PR boundary.
- *Inferred:* the release batch review is `cumulative` mode (boundary stage) dispatched on the
  base branch with a new `critic-begin --span release` interval: release anchor tree → HEAD tree,
  subject = the judgeable files of every not-covered entry, context = the rest of the span
  (`files_context`, the bounded-cumulative mechanism). Its fact is never a `review_edges` edge
  (its subject is partial), so it cannot turn any PR gate verdict toward covered. Its blocking
  findings gate the release check, and any span that ends at the tree it reviewed, which is the
  base there and the verify pass that fixes them. They do not gate a feature branch that merely
  forked from that tree (decision M1 below).
- *Inferred:* the relax-only batch rule (design §3): a not-covered merge `M` reads `batch-covered`
  when a boundary-stage review `B` brackets it on the first-parent line, `M`'s judgeable files that
  still differ from the anchor are within `B.files_reviewed`, and composition over all facts at
  `B`'s nodes has no unresolved blocker. A fix to `B`'s own findings committed on the base is
  covered when `verify-resolutions` and free edges alone compose `B.head_tree` → the fix commit's
  tree: the accepted "boundary prefix plus verify-only tail" shape, applied to the batch.
- *Inferred:* the blocking reading is a new flag, `check-boundary-coverage --gate` (exit 1 when any
  entry is not covered and the policy is per_release; 3 unevaluable), because the bare op's exit 0
  is a published meaning (api-contract: additive-first). Under per_release an unevaluable answer
  refuses the release.
- *Inferred:* a deferred fix tail reads as a new class, `tail-deferred`, not covered, so the
  release reader can tell "the PR gate deferred this" from "nothing reviewed this".

**Product:** #1223 asks for a small-feature lane in a repo that releases several times a day:
one inner review per feature, and the boundary review once per release batch. #1222 asks that a
fix for a non-blocking finding not buy its own round. The design found them one mechanism: #1222's
"next review that runs anyway" exists only if #1223's release-batch review exists. This repo
stays `per_pr` (decision 4): it releases about every ten days and `../prawduct-live` runs develop,
so a batch here would be large and unreviewed boundary code would govern live sessions.

**Architecture:** One question per owner. The policy has one reader; eligibility one predicate;
the tail deferral one predicate shared by the PR gate and the Stop gate; the release answer stays
`boundary_coverage`'s. Every relaxation is opt-in, read from the integration branch, and owed to a
check that blocks: decision 1 says the deferral ships only together with the release check, so
this plan ships as one PR and no part merges alone.

**Constraints:** No new persisted format: the anchor derives from git; the batch review's fact uses
the existing manifest fields (`span` gains the value `release`, read by the reviewer's span note).
The default (`per_pr`) changes no verdict, exit or inference anywhere: every chunk proves that with
a control test on a repo without the key.

**Tradeoffs accepted:**
- A squash merge reads `direct`, so under per_release it is owed to the release batch review
  unless its PR review spans exactly the trees it landed (decision M6). Revisit if a squashing
  consumer opts in; `/prawduct:doctor` could warn.
- The deferral is file-level evidence (`diagnose_fix_churn`'s stated bound): it cannot tell a fix
  from new work written into a named file. It is a deferral, so a reviewer still reads the tail at
  the release; that is what makes the file-level bound acceptable here when it was refused as a grant.
- Anchor B picks up any version-shaped tag reachable from the base. A stale ancient tag only widens
  the walk (the safe direction), but under a gate a wide walk can hold a release for old work.
  Nearest-wins keeps A ahead of B here.

**Decisions made mid-build:** *(appended while building)* Each one is inferred on the owner's
behalf and is the owner's to veto. The Chunk 06 boundary cumulative (rev-20261126T024337Z-72d8857e,
W9) found M2 to M6 recorded only in docstrings.

- **M1, release-span blockers (2026-11-26; reverses Chunk 03's inference).** A release batch
  review's BLOCKING finding gates the release check and any span ending at the tree it reviewed.
  It does not gate a feature branch forked from that tree. *Why:* under Chunk 03's reading, every
  branch cut from the base tip read `blocked` for code it never touched (native review finding),
  and the verify pass that clears the blocker composes to that same tree, so narrowing the reading
  hides nothing from it. Lives in `coverage_algebra._counts_at`.
- **M2, the round budget never charges a release batch review** (`critic_consolidate._cadence_round_ids`).
  *Why:* it is the release's own step, not a round on any scope. Charging it would leave `--force`
  as the only route to a held per_release release. It widens the owner's 2026-11-23 ruling
  (item 2). **Confirmed by the owner 2026-11-26** (`owner-rulings.md`); the `review_round_budget` key
  doc says so.
- **M3, the release policy falls back to the checkout's declaration.** The checkout's `per_release`
  stands when the integration tip cannot be read, or when the read fails. A failed read then
  refuses as unevaluable rather than passing. *Why:* for a release check `per_release` is the
  stricter reading. The architecture disposition's "unreadable reads per_pr" is the PR side's rule.
- **M4, the release span can start before the anchor,** at the first parent of the oldest owed entry
  when one sits at or before the anchor (a scope that a pruned release withheld). *Why:* a review
  starting at the anchor could never bracket that entry, so the release would be held forever.
- **M5, the batch rule credits every `unknown` merge that names a parent,** octopus merges,
  unrelated-history merges and undiffable merges included. *Why:* what the merge brought onto the
  base is what the release review rates. Without this, the gate's remedy never terminates (W1).
- **M6, a squash merge reads `batch-covered`** when its PR review spans exactly the trees it landed.
  *Why:* that review read everything the squash brought. This supersedes the original tradeoff,
  which said every squash would need a release batch review.
- **M7, a branch may opt OUT of per_release at its tip, never in.** A merged branch is judged
  per_release only if both its merge-base and its tip declare it
  (`review_lane.boundary_review_policy_of_merge`). *Why:* a governance change cannot supply its own
  authority, but tightening needs none.
- **M8, the release op accepts a recorded transfer grant from either gate,** the PR gate or the
  Stop gate, but only for exactly the merged span. *Why:* when both gates granted the same span,
  the Stop gate's record is the only one.
- **M9, a failed policy read refuses the release as unevaluable**, even when every entry reads
  covered. *Why:* an answer reached under a guessed policy is not an answer.
- **M10, prerelease tags (`-rc.N`, `-dev.N`) are never a release anchor**; only a release file the
  cut wrote anchors one. *Why:* the work between the last release and an rc tag would go unwalked.
- **M11, a plain `/prawduct:critic cumulative` on the integration base at its tip is the release
  batch review** (`critic-begin` derives `--span release`) where the policy in force is
  `per_release`; under `per_pr` it stays the plain cumulative (round-4 review, native finding 1:
  deriving it there turned a no-op into a refusal or a review no gate reads). *Why:* that is the
  one state where a plain cumulative reviews nothing; no model has to choose the flag.
- **M12, retired 2026-11-26 (owner ruling "what was over-built", item 3).** It cleared a merged
  branch's unresolved blocker on the base. Its premise, a merge made over a blocker past the PR
  gate, is the owner's deliberate call under good faith, so the release no longer re-checks it: a
  release batch review settles its own findings only. The version-shape checks on declared version
  files retired with it.
- **M13, the lane's reading is memoised for one inference only**, and a crash in the lane predicate
  is noted even under `per_pr`. *Why:* inference writes nothing to the tree; the crash happens
  while the policy is being read, before anything knows which policy applies.
- **M14, lane eligibility calls `_short_plan_shape`, not `short_plan_deferral(...).defers`.** *Why:*
  `defers` also answers "not finished", and a plan the lane's review just finished must stay in the
  lane, or the first fix after that review would bring back the cumulative the lane moved. A later
  widening of `short_plan_deferral` (#1247 seam 2) is not inherited by the lane; change both.
- **M15, `reverted`** (owner ruling 2026-11-26, R-4): an owed entry whose every judgeable file is,
  at the base tip, back to its content at the release span's start is covered. Where the span starts
  before the anchor, an entry reverting a change shipped between that start and the anchor also reads
  `reverted` (the batch rule's condition 2 shares this). Veto-able.
- **M16, the batch fix tail asks only boundary reviews at or after the span start.** A verify-only
  tail from an older review no longer credits a later commit; it reads `direct` and the release
  batch review reads it, the safe direction. Veto-able.

**Level:** Medium. The mechanism is clear and every piece has a precedent in the code (the short-plan
deferral, the bounded cumulative, the fix-churn diagnosis, `excused_gap_verdict`). Two things would
raise it: the consumer repo's per-merge counts (decision 6), and confirming at Chunk 04's start that
a `chunk` review can name all open built chunks the way the boundary cumulative does
(`plan_status.chunk_proposal`).

### Seams with concurrent work

- **#1250 (in flight):** `check-boundary-coverage` will honour the PR gate's base-advance transfer
  through a predicate shared with `gates.py`, reported as a distinct covered-via-transfer class.
  Chunk 02 starts from develop after #1250 merges and treats that class as covered (it is in
  `boundary_coverage.COVERED`); the anchor walk classifies post-anchor merges through the same
  `classify_commit`, so the transfer arm applies to them with no second implementation. Chunk 05's
  tail deferral is attempted only after the transfer fails, the order `_branch_coverage` already has.
- **#1247 (design in flight; a review-cadence key for per-chunk vs boundary-only review in long
  plans):** it touches the same code. Name these seams before either builds:
  1. *Key namespace:* `boundary_review:` says where the boundary runs; #1247's key says whether inner
     per-chunk reviews run. Keep two keys with non-overlapping names, documented next to each other
     in `project-state-keys.md`; whichever lands second adds the cross-reference.
  2. *`critic_mode.short_plan_deferral` / `_short_plan_shape` / `SHORT_PLAN_MAX_CHUNKS`:* if #1247
     widens deferral to long plans, the lane must still pin "at most three chunks" itself. Otherwise
     boundary-only cadence plus per_release would route a large plan's boundary to the release.
  3. *`LAST_CHUNK_BOUNDARY_STEP`, `short_plan_next_step`, `_mid_plan_answer`, the rule-2 and rule-4
     clean-tree redirect, `boundary_cumulative_still_owed`:* both change the last-chunk answer.
  4. *The Stop gate's critic block in `prawduct-hook`* (the deferral/last-chunk branch): both
     change its prose.
  Sequencing: Chunk 04 never runs concurrently with #1247's build. Whichever lands second rebases
  and re-reads every site above.

## Scaffolding

Not applicable: framework code in an existing runtime. Tests run with `testament run`
(`documentation/running-tests.md`); evidence with `prawduct-hook test-evidence record`. The scope's
change fragment is written with the plan (`prawduct-hook plan new` writes both) at Chunk 01.

### Verification Strategy

Each chunk runs its narrow selection plus the whole-tree guards (the prose budgets and NFR greps in
`tests/test_v5_methodology.py` and `tests/test_plugin_methodology_digest.py`; the key-reference test;
`tests/test_skill_command_grants.py` and the op-set tests; `tests/preferences/`; the path-reference
checks). The declared suite runs once, at Chunk 06's boundary.

Beyond tests, the op is read as an operator reads it:
- On this repo (per_pr) after Chunk 02: `prawduct-hook check-boundary-coverage` names the anchor
  (`436f44d3`, release file), classifies `c9b58e4e` per decision 3, and `check-releasability`'s exit
  equals develop's.
- In the consumer repo, the pay test (decision 6): `prawduct-hook check-boundary-coverage --json`
  from its integration checkout. It is not run from here: it writes the clone's tree-key memo
  (`gates._tree_key_fn` → `tree_key_memo.put`), so the owner or coordinator runs it. Before Chunk 02
  lands, `git describe --tags --abbrev=0 develop` there (read-only) says whether anchor B will find
  one; that repo has no release files, so A will not.
- After Chunk 03: a scratch clone of this repo with `boundary_review: per_release` committed on its
  develop, one lane branch merged, then a release batch review run, and the op reads it covered.

## Build Chunks

### Chunk 01: The `boundary_review` key, read from the integration branch

- **Description:** One reader for the policy, and the norm it rests on.
  - new `plugin/lib/review_lane.py`: `boundary_review_policy(project_dir) -> Policy(value, source, note)`,
    reading `boundary_review:` from `.prawduct/project-state.yaml` at the merge-base with the integration
    branch (`coverage.integration_base`), and `boundary_review_policy_at(project_dir, rev)` for the
    release check, which reads at the base tip. `per_pr` unless the value is exactly `per_release`;
    the note says why when a working-tree value is not yet in force.
  - `plugin/lib/core.py`: the key constant, and its row wherever the opt-in key set is enumerated
    (grep `STATIC_CONTENT_PREFIXES_KEY` for the pattern).
  - `plugin/templates/project-state.yaml`: a one-line hint. `plugin/docs/project-state-keys.md`: the
    entry (values, read-from-base rule, what per_release changes, that the release check blocks).
  - `.prawduct/artifacts/nonfunctional-requirements.md`: the amendment, under the clause, as
    confirmed (decision 1). The statement keeps its words.
  - This repo's `.prawduct/project-state.yaml` sets nothing (per_pr by default).
- **Depends on:** none
- **Artifacts consumed:** `documentation/issues/1222-1223-design.md` decisions 2 and 4; decision 1 above
- **Deliverables:** the policy reader and its tests; the key's documentation; the NFR amendment; the
  change fragment.
- **Tests:** unit over fixture repos: the key read at the merge-base; a branch adding `per_release`
  reads `per_pr` with the note; a typo reads `per_pr`; absent reads `per_pr`; the base-tip reader.
  The key-reference test sees the new key.
- **Acceptance criteria:** a branch cannot opt itself in (red under a mutant reading the working
  tree); every unreadable or unknown value reads per_pr; the doc, template and constant agree.
- **Done when:**
  0. The owner has confirmed decision 1's text, recorded in `.prawduct/owner-rulings.md` before
     this chunk commits
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed (`feat(boundary-review-per-release): … (Chunk 01)`)

### Chunk 02: A release anchor, and every judgeable commit since it

- **Description:** #1232 requirement 1, in `plugin/lib/boundary_coverage.py` (on top of #1250).
  - `release_anchor(project_dir, base) -> Anchor(commit, tree, source, reason) | None`, per
    decision 2: candidate A (newest first-parent commit adding a file under `.prawduct/releases/`,
    `consumer_digest.RELEASES_DIR_REL`), candidate B (oldest first-parent commit containing the
    newest version tag reachable from the base, version-shaped by `release_readiness.normalize_version`),
    the nearer to the tip wins.
  - The report classifies every first-parent commit after the anchor that changes a judgeable file,
    unioned with wave 1's pending-fragment join, de-duplicated by commit. Entries gain `source`
    (`fragment`, `walk` or both); a walked commit with no fragment has an empty scope and its subject.
  - Decision 3's `release-bookkeeping` class (covered), from the declared `release_version_files:`.
  - No anchor: the walk is skipped and the report says so. The fragment-only classification is
    still given (advisory, as today).
  - `count_line` names the anchor and the denominator ("N of M judgeable commits since <anchor>").
- **Depends on:** #1250 merged to develop
- **Artifacts consumed:** decision 2 and 3 above; `.prawduct/runbooks/cut-and-publish-a-plugin-release.md` Phases 1 and 3
- **Deliverables:** the anchor, the walk, the new class, their tests; `--json` additions.
- **Tests:** real-git fixtures for: a whole-develop cut (anchor A); a pruned cut whose withheld scope
  sits before the anchor and is still classified through its fragment; a back-merged tag (anchor B);
  both present, the nearer wins; neither (no anchor, the report says so); a judgeable direct commit
  after the anchor with no fragment (classified `direct`, which wave 1 could not see); a reopen
  commit touching only declared version files (`release-bookkeeping`) and one touching another file
  too (`direct`). One `requires_local_cache` test reads this repo's history and asserts anchor
  `436f44d3`.
- **Acceptance criteria:** wave 1's invisible case (a judgeable commit with no fragment) is
  classified; every new class is red under a mutant of its predicate; per_pr output on this repo
  keeps check-releasability's exit unchanged.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed (`feat(boundary-review-per-release): … (Chunk 02)`)
  4. The pay test (decision 6) has been run in the consumer repo and its counts relayed to the
     owner. Chunks 03-06 wait on the go/no-go.

### Chunk 03: The release batch review, and the relax-only rule that credits it

- **Description:**
  - `plugin/lib/coverage_algebra.py`: a pure rule beside `excused_gap_verdict`, for example
    `batch_review_covers(facts, review, merge_files, …)`, that answers covered / blocked / not for
    one entry against one boundary-stage review. Relax-only: it never adds an edge, never changes
    `coverage_verdict`, and blockers settle over all facts at the review's nodes.
  - `plugin/lib/boundary_coverage.py`: the batch rule and the batch fix tail (Goals, inferred calls),
    generalising wave 1's `_batch_review` (whose whole-edge check is the special case where the
    subject is every file), and the `tail-deferred` class Chunk 05 needs, read as not covered.
  - `plugin/lib/critic_consolidate.py` `begin_review`, and `critic-begin --span release` in
    `prawduct-hook`: on the base branch with a clean tree, the interval is anchor tree → HEAD tree,
    the subject the not-covered entries' judgeable files that still differ from the anchor, the rest
    `files_context`; `span: release` with a `span_reason` naming the anchor. Refused, naming why, with
    no anchor, off the base branch, on a dirty tree, or with nothing not covered (exit 3, no review
    needed).
- **Depends on:** Chunk 02
- **Artifacts consumed:** design §3 (the relax-only rule); `plugin/skills/critic/review-cycle.md` bounded cumulative and `files_context`
- **Deliverables:** the pure rule, the classification wiring, the dispatch interval, their tests.
- **Tests:** unit over the pure rule (a file outside the subject refuses; an unresolved blocker
  refuses; a resolution fact clears it; a review not bracketing refuses); fixture repo through the
  CLI: two lane merges, a batch review, both `batch-covered`; a batch blocker fixed on the base
  through `verify-resolutions` reads covered once resolved; a pr-covered merge's file outside the
  subject stays pr-covered and does not stop the batch crediting others. The batch fact is not an
  edge: `check-cumulative-critic` on a branch spanning it is unchanged (control).
- **Acceptance criteria:** the rule is relax-only (property: adding a batch fact never turns any
  `coverage_verdict` from not-covered to covered); every refusal of `--span release` is reachable
  and named.
- **Critic mode:** final
  <!-- Override: this rule is the authority a per_release release gate trusts. Its coherence is
       worth a full inner review before Chunk 06 makes it block. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed (`feat(boundary-review-per-release): … (Chunk 03)`)

### Chunk 04: Inference answers `chunk` at an eligible last chunk

- **Description:** In `plugin/lib/critic_mode.py`:
  - `lane_eligibility(project_dir, prawduct_dir, plan, progress) -> LaneEligibility(eligible, reason)`:
    policy per_release (Chunk 01's reader), the short plan's shape (`_short_plan_shape`, M14), at most
    `LANE_MAX_JUDGEABLE_FILES` (decision 4) judgeable files merge-base…working tree, and no
    `Type: cumulative-final`. Fails closed: anything unreadable is not eligible.
  - At an eligible last chunk on a clean tree, rule 2 and the rule-4 redirect answer `chunk` with a
    `per-release lane:` rationale naming the chunks it must certify; with code in flight, rule 2b's
    deferral names the lane's step.
  - One statement for the step, beside `LAST_CHUNK_BOUNDARY_STEP` (for example
    `LAST_CHUNK_RELEASE_STEP`), composed by `short_plan_next_step` when the deferral carries the
    lane, so inference, the rationale and the Stop gate cannot disagree.
  - Enumerate by query before editing: every reader of `LAST_CHUNK_BOUNDARY_STEP`,
    `short_plan_next_step`, `boundary_cumulative_still_owed`, `OWED_BOUNDARY`,
    `boundary_review_on_chain` and `_clean_tree_redirect`, and every prose sentence saying a short
    plan's last review is the `cumulative` (`plugin/skills/critic/SKILL.md`, `plugin/skills/critic/review-cycle.md`'s "When Review
    Is Required" row, `plugin/methodology/planning.md` "Critic Mode Per Chunk", `plugin/skills/pr/SKILL.md` lines naming
    the per-feature cumulative). Each gets a per_release clause or is left true as written.
  - The Stop gate's critic block in `prawduct-hook`: its literals ("the boundary review is the PR
    gate's evidence", "deferred to this boundary review") take the lane's wording when the deferral
    carries it.
- **Depends on:** Chunk 01
- **Artifacts consumed:** decisions 3 and 4 of the design; the NFR amendment (Chunk 01)
- **Deliverables:** the predicate, the inference answers, the one step statement, the Stop-gate
  prose, the methodology and skill sentences; their tests.
- **Tests:** inference on fixture repos: an eligible last chunk answers `chunk` (clean tree) and
  `deferred` naming the lane step (dirty); each eligibility condition flips it back to `cumulative`
  (per_pr, a risk surface, 4 chunks, a `Critic mode:`, `Type: cumulative-final`, 11 judgeable files);
  an explicit `/prawduct:critic cumulative` still answers cumulative; the lane's `chunk` dispatch
  names every open built chunk and is not refused with exit 8; the PR gate passes on the lane's
  coverage. The existing short-plan, Stop-gate and inference suites pass unchanged on per_pr repos.
- **Acceptance criteria:** with the key absent, inference answers exactly what develop does (a
  control over the existing fixtures); with per_release and an eligible plan, no `cumulative` is
  inferred anywhere on the branch.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed (`feat(boundary-review-per-release): … (Chunk 04)`)

### Chunk 05: A blocker-free fix tail is deferred to the release

- **Description:** Decision 1, scoped by decision 5.
  - `plugin/lib/gates.py`: one predicate, `fix_tail_deferral(...)`, true when the policy is
    per_release, `coverage.diagnose_fix_churn` returns `churn` (an anchor review on this branch after
    the merge-base, base → anchor composing blocker-free, every judgeable tail file named by that
    review's findings), and no tail path is a risk surface. `_branch_coverage` tries it after the
    base-advance transfer fails and returns a new status `deferred`; `check-cumulative-critic`
    exits 0 and prints a `NOTE:` naming the review, the tail's files and the release check that now
    owes them a read.
  - The Stop gate's critic block honours the same predicate (after Chunk 04's edits there).
  - `plugin/skills/pr/SKILL.md` Step 2: the deferred pass, in one sentence, and that it exists only in a
    per_release repo.
  - `branch_coverage_verdict`'s callers that switch on `status` are found by query and handle the
    new value (a status a reader does not know must not read as covered).
- **Depends on:** Chunk 01, Chunk 04 (the Stop-gate block)
- **Artifacts consumed:** design §1 and §4; the "What must not break" list there
- **Deliverables:** the predicate, the new status and its renders, the Stop-gate wiring, the skill
  sentence; their tests.
- **Tests:** per_release fixture: a cumulative with warnings, a fix in a named file, PR gate exit 0
  with the NOTE; controls that each refuse: per_pr; a blocker open; a tail file the review did not
  name; a tail on a risk surface; an anchor review predating the merge-base. The design's must-not-break
  list stays green: `test_free_interval_with_unresolved_findings_dispatches`,
  `test_dispositions.py::test_blocking_is_refused_outright`, `tests/test_cumulative_gate.py`,
  `tests/preferences/test_free_interval_prose.py`, the NFR retirement grep in
  `tests/test_v5_methodology.py`, the `boundary_frontier` bounded-span tests.
- **Acceptance criteria:** a BLOCKING finding never defers (red under a mutant that drops the
  blocker condition); every reader of the coverage status handles `deferred`; per_pr is unchanged.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed (`feat(boundary-review-per-release): … (Chunk 05)`)

### Chunk 06: The release check blocks a per_release release

- **Description:**
  - `prawduct-hook check-boundary-coverage --gate`: exit 1 when the base-tip policy is per_release
    and any entry is not covered, 3 when unevaluable (including no anchor), 0 otherwise. Under
    per_pr, `--gate` exits 0 with the advice unchanged. The bare op's exits do not change.
  - `plugin/lib/release_readiness.py` `check_releasability`: under per_release a not-covered or
    unevaluable answer is a refusal with a named reason code (for example `boundary-uncovered:`),
    printed with the remedy (`/prawduct:critic` with `critic-begin --span release` on the base). The
    per_pr lines stay advice, exit unchanged.
  - `plugin/skills/pr/SKILL.md` release-promotion guard: under per_release it runs `--gate` and stops on
    exit 1 or 3, naming the batch review; per_pr text unchanged.
  - `documentation/release-process.md` and `.prawduct/runbooks/cut-and-publish-a-plugin-release.md`
    Phase 0: the per_release step, stated as not applying to this repo.
  - `.prawduct/artifacts/api-contract.md`: the flag, its exits, the refusal code.
  - The false-positive audit owed when advice turns blocking: list every class a correct release
    could still meet (squash `direct`, octopus `unknown`, an untracked fragment, a missing anchor,
    #1250's transfer), and state for each whether it blocks and the route out. The audit goes in the
    key's documentation, where a repo deciding to opt in reads it.
- **Depends on:** Chunks 02, 03, 04, 05
- **Artifacts consumed:** design decision 5; wave 1's Chunk 02 surfaces
- **Deliverables:** the flag, the refusal, the skill, docs, runbook, contract updates, the audit;
  their tests.
- **Tests:** check-releasability on a per_release fixture with one lane merge: refuses with the code;
  after a batch review, passes; per_pr control: the same history exits as develop does. `--gate` exit
  table pinned. The op-set and grant tests cover the new flag (a prefix-matching grant already exists;
  test by rule over the dispatcher's op set). The release guard's prose names a flag the op has.
- **Acceptance criteria:** this repo's `check-releasability` exit equals develop's; a per_release
  fixture cannot pass the release check over an unreviewed merge, a deferred tail or a missing
  anchor; every artifact that describes the op agrees (grep the claim, not the tokens).
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and the declared suite passes (recorded once, here)
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved

## Early Feedback Milestone

**Milestone chunk:** 02
**What the user can do:** run `prawduct-hook check-boundary-coverage` on this repo and in the
consumer repo and read every judgeable commit since the last release, anchored, with the lane's
pay test answered by real counts.

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk after its review; one PR for the whole plan (decision 1
binds the deferral to the release check, so no part merges alone). The plan touches
`plugin/bin/prawduct-hook`, `plugin/lib/` and `plugin/skills/`, declared risk surfaces, so it is not a
short plan: each chunk gets its inner review, Chunk 03 a `final`, and Chunk 06's cumulative is the PR
gate. This repo is per_pr, so its own PR runs the boundary review as usual.

- Before Chunk 01 commits: decision 1 confirmed and recorded.
- After Chunk 02: the pay test (decision 6). Go or no-go on 03-06.
- Before Chunk 04 starts: #1247's state checked; the seams above re-read against develop.
- At Chunk 06 (cumulative): the whole bundle against these Goals, including each inferred call.
