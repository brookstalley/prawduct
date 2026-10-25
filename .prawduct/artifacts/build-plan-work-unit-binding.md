---
artifact: build-plan
version: 2
scope: work-unit-binding
branch: feature/1050-work-unit-binding
base: develop
working-branches: []
partition: >-
  01 and 06 serial (coordinator). 02–05 delegated after 01 commits, isolated worktrees, disjoint
  ownership — A: plugin/lib callers; B: plugin/bin/prawduct-hook callers; C: new lib modules plus
  change_fragments.py and lib/backlog; D: prose. The coordinator owns core.py, buildplan_refs.py,
  the hook's subcommand table, the advisory registry and integration.
governed_by:
  - .prawduct/artifacts/data-model.md
  - .prawduct/artifacts/architecture.md
  - .prawduct/artifacts/api-contract.md
depends_on:
  - documentation/issues/1050-requirements.md
  - documentation/issues/1050-design.md
last_validated: 2026-10-24
---

## Goals

**Response taken:** Proceed, citing #1050 (`stage: design`) and `documentation/issues/1050-design.md`
§ 1–2 and § 6–7 (Wave 1). The owner ruled D1–D6 and the three amendments on 2026-10-24 and asked for
the build to be coordinated with delegates.

**Product:** Which plan governs a checkout has one answer from one owner, with no fallback that can
look correct while being wrong. Every review, ledger event and gate decision records the unit it
was about or `none`. A scratch delegate worktree is bound to nothing. This closes the class #1049
closed for one route, and #1007 shape (a).

**Architecture:** `work_unit.resolve()` is the only walker; every consumer takes its `Binding`.
Facts written by code keep recording what code resolved (`data-model.md`: no model in a fact's
write path — the `Binding` is computed, never typed). Authority fails closed: a `broken` binding
blocks what `bound` would have blocked and advises what it would have advised (`architecture.md`).
Additive-first on the CLI: `--chunk` and the old `scope_chosen_by` values stay readable; new values
are added, none repurposed (`api-contract.md`).

**Governing-norm reconciliation:**
- data-model.md "no model in a fact's write path" — conforms.
- data-model.md "derived views never feed a gate" — conforms; `Binding` is a computed fact, not a view.
- data-model.md DV3 (hand ticks authoritative) — **untouched in this wave**; this plan keeps its
  own `## Status` block because the gate still arms on it. The amendment lands in Wave 2 with the
  code that honours it, recorded in § Direction then.
- architecture.md "every fact has one home" — conforms; the precedence rule's home becomes
  `planning.md` alone, and `Binding` is the one home of "which plan".
- architecture.md local-first — conforms; no network.
- api-contract.md additive-first — conforms, see above.

**Constraints:** the legacy window (MG3) means the pointer and default routes are *demoted*, not
deleted, in this wave: served only when no live plan in the repo declares `branch:`, and only for a
plan that itself declares none, with the `plan-unbound-legacy` advisory. Tests pin both halves.

**Tradeoffs accepted:** `core.resolve_build_plan_path` and `buildplan_refs.resolve_branch_plan`
survive one release as shims over `resolve()` so that a consumer repo's pinned plugin version and a
newer one agree on the answer during the window. Revisit: delete the shims when the window closes.

**Decisions made mid-build:**
- Chunk 05's acceptance grep was wrong as written: six `active_build_plan` mentions live in the
  Critic skill's docs (`critic/SKILL.md`, `review-cycle.md`, `cross-checks.md`, `goals-1-3.md`,
  `pr/review-protocol.md` "Dangling pointers", `doctor/SKILL.md`) and describe the scope-derivation
  mechanism Chunks 02/03 change — prose that a code change falsifies is updated with the code, so
  they move to Chunk 06's deliverables. Settled by the plan's own ownership rule.
- 05 merged before 01 and reviewed with it in one `final`: both are small, `final` covers the full
  diff anyway, and review wall clock is the owner's P0.
- `pr/SKILL.md` step 9's "ignore the archive advisory during the window" sentence is deleted, not
  moved: since #1049 a `branch:`-declaring plan is inactive on every other branch, so the advisory
  it told you to ignore no longer fires.
- Chunk 01 departures from `1050-design.md` § 2, settled by the coordinator (design updated):
  a claimant with `branch:` but no `scope:` is `bound` with `scope=None` and a `reason` naming the
  fix — it governs its branch today and MG1 forbids silent reinterpretation; `reason` may be set
  on `bound`; the scratch-worktree check precedes the detached-HEAD check (a scratch tree is
  unbound whatever its HEAD); a legacy binding has `role=None`; detached HEAD is `unbound` even
  in the legacy window (which branch's plan governs is unknowable there, and serving the pointer
  is the misattribution class). `broken` is two or more claimants, or — after the first review's
  R-1 — any live plan whose claim declaration cannot be read: authority fails closed, so an
  unreadable `branch:`/`working-branches:` never reopens the legacy route. `Binding.claimants`
  (additive, defaulted) carries the plans involved so a consumer can act on `broken` without
  parsing prose.
- BR3's "claims a branch that does not exist → broken" is not observable from `resolve()`, which
  reads only the checked-out branch; it is a repo-wide check and moves to `doctor` in Wave 2
  (#1051, noted there). Explicitly deferred, not dropped.
- Chunk 01's acceptance "fails on develop's resolvers" is met for the shapes that were defects
  (#208, #1007(a) silence, two claimants, working branch, scratch/detached in a legacy repo);
  three shapes (#1049 default-path, "declaring `branch:` never served", scratch on a bound
  branch) were already answered correctly after #1049 and the tests say so in comments rather
  than asserting a false red. Acceptance read accordingly.
- Chunk 03's open calls, settled by the coordinator: a detached HEAD arms no Critic gate at Stop
  (it is `unbound`; a detached checkout is transient — mid-rebase, a bisect — and the gate re-arms
  the moment the branch is checked out again, while the old behaviour served the pointer's plan,
  which could be the wrong one); `verify-chunk-refs` with a chunk named but no plan bound exits 1
  `cannot-verify` rather than a false 0 (a check that could not run must not read as a pass); the
  ST7 `project-state.yaml` arm still arms a scratch worktree in a repo with unfinished state
  chunks — Wave 2 deletes the arm (#1051). Chunk 03's two strict xfails (inference and the
  critic-begin manifest resolve in `plugin/lib/`) go red when Chunk 02 lands; Chunk 06 deletes
  the marks.
- Chunk 04's open calls, accepted by the coordinator: the near-miss scope check lives in the
  fragment parser (`check_fragment_text`/`read_fragment_file`/`load_pending`), so it reaches
  record lint, the PR payload, `release_readiness` and the cut alike — one owner, and no consumer
  repo has a `changes/` directory yet (checked 2026-10-24), so promoting CL7's advisory to a
  refusal costs no existing release; a bare known slug in `closed-by` is accepted and stored as
  `scope:<slug>` with a warning (tolerate the natural variant, refuse only genuine ambiguity);
  minting also refuses a scope one spelling from an existing one, `branch == base`, and an
  existing `--branch`; `bind` never re-points an existing claim (that stays a hand edit a reviewer
  sees); `base:` defaults to `project-state.yaml` `base_branch:`, else the remote default per
  `coverage._resolve_base_branch`, else `main` — git records no parent for a branch, so the plan
  records it (design § Research).
- Chunk 02's open calls, settled by the coordinator: the `critic_mode` helpers take the `Binding`
  (the hook passes it through; Chunk 03's `_gate_plan_of()` converter goes in 06a); an unbound
  checkout grades nothing in record lint and adds no `unchecked` line (a line there fires on every
  chore review), a broken one does; `learning.fired` events carry the review's scope; the flat
  `lib.resolve_build_plan_path` export is gone (no caller). Reversed: `scope_unresolved_cause`
  stays a short code — api-contract.md is additive-first, and a field that held a code must not
  start holding a sentence; the sentence goes in a new `scope_reason` (06a).
- Review cadence, settled by the coordinator: 02, 03 and 04 cannot each be reviewed green on
  their own (02 changed `critic_mode`'s signatures; 03's hook still feeds the old object — nine
  Stop-gate tests are red until 06a closes the seam), so they are reviewed together with 06a in
  one `chunk` pass once green, and the PR's `cumulative` follows. Two rounds instead of four; the
  fact will name one chunk because today's field is singular (ST8 is Wave 2).
- Chunk 05's prose states the rule in the present tense while `plan bind`, the
  `plan-unbound-legacy` advisory and the Stop hook's scratch-worktree behaviour land in 03 and 06.
  One PR; at merge every sentence is true. Chunk 06's acceptance gains one check per claim.

**Level:** High for § 2 (the resolver and its callers are enumerated in the requirements'
grounding facts); Medium for § 1's `plan new` defaults for `base:` — raise by reading how
`gitstate` finds the integration branch before Chunk 04 is briefed.

## Status

- [x] Chunk 01: `work_unit.resolve` — one owner, three answers, four red-first shapes
- [x] Chunk 02: lib callers take `Binding`
- [x] Chunk 03: hook callers take `Binding`
- [x] Chunk 04: `plan new` / `plan bind`, fragment and `closed-by` scope validation
- [x] Chunk 05: one home for the rule — prose
- [ ] Chunk 06: integration — shims, advisory, subcommand wiring, suite, cumulative review

Context: Chunk 01 is the keystone and is reviewed `final` before anything builds on it. 02–05 are
delegated in parallel; each is reviewed when it merges into this branch (the coordinator's review,
`chunk` mode, naming the chunk). 06 is the one `cumulative`. Boxes are ticked by the coordinator
after each merge's review — this is the last plan that ticks; Wave 2 removes the block.

## Build Chunks

### Chunk 01: `work_unit.resolve` — one owner, three answers, four red-first shapes

- **Description:** New module `plugin/lib/work_unit.py` with `Binding` and `resolve()` exactly as
  `1050-design.md` § 2 states, including the scratch-worktree and detached-HEAD cases and the
  legacy step 4. No caller changes yet.
- **Depends on:** none
- **Artifacts consumed:** `documentation/issues/1050-design.md` § 2; `plugin/lib/gitstate.py`
  (`is_ephemeral_worktree`, `current_branch`); `plugin/lib/plan_index.py`
  (`iter_scoped_plan_candidates`); `plugin/lib/core.py` (`resolve_branch_claim`, `pointer_plan_path`,
  `DEFAULT_BUILD_PLAN_REL`, read-only in this chunk).
- **Deliverables:** new `plugin/lib/work_unit.py`; new `tests/test_work_unit.py` covering: the
  #1049 shape (finished plan at the default path, unrelated branch → `unbound`); #1007 shape (a)
  (lone plan declaring no branch → `legacy-default` inside the window, with the advisory key in
  `Binding.reason`); #208 (unrelated plan, branch matching no claim → `unbound`); two claimants →
  `broken`; a declared working branch → `bound, role=working`; a scratch worktree forked from a
  bound branch → `unbound`; detached HEAD → `unbound`; a plan declaring `branch:` is never served
  by step 4.
- **Tests:** the module above, red first against a stub `resolve` that returns the old resolver's
  answer for each shape.
- **Acceptance criteria:** every listed shape has a test that fails on develop's resolvers and
  passes on `resolve()`; `resolve()` makes no network call and reads the archive directory never.
- **Critic mode:** final
  <!-- Keystone: four delegates build on this API. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status — then 02–05 are briefed

### Chunk 02: lib callers take `Binding`

- **Description:** Every `plugin/lib/*.py` caller of `core.resolve_build_plan_path` or
  `buildplan_refs.resolve_branch_plan` — except `core.py` and `buildplan_refs.py` themselves —
  takes `work_unit.resolve()` and reads the `Binding`. `ledger._scope_from_plan` is deleted: an
  event records the fact's scope or `null`. `critic_consolidate.build_fact_body` writes
  `scope_chosen_by` from the `Binding` (`binding | legacy-pointer | legacy-default |
  explicit-args | none`). `pr_payload`, `coverage` (`cost-of-commit`), `briefing` (`Resume:`,
  staleness, the pointer-missing warning) and `handoff` read the `Binding` and render its
  `reason` where they named a plan before.
- **Depends on:** Chunk 01
- **Artifacts consumed:** `1050-design.md` § 2 "BR4"; the caller inventory in
  `1050-requirements.md` § Grounding facts.
- **Deliverables:** the callers above migrated; `tests/test_ledger*.py`,
  `tests/test_critic_consolidate*.py`, `tests/test_pr_payload*.py`, `tests/test_briefing*.py`
  extended: a review on a branch no plan claims records `scope: null, scope_chosen_by: none`
  and a ledger event with `scope: null` (the #1049 event shape, red first).
- **Tests:** the modules above, scoped to the files touched.
- **Acceptance criteria:** `grep -n "resolve_build_plan_path\|resolve_branch_plan" plugin/lib/*.py`
  returns hits only in `core.py`, `buildplan_refs.py` and `work_unit.py`; the #1049 ledger shape
  test passes.
- **Done when:**
  1. Acceptance criteria met and tests pass (the delegate's ceiling: the test modules for the
     files it touched)
  2. Branch handed back; coordinator merges, runs `/prawduct:critic` naming this chunk, resolves
     blocking findings
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: hook callers take `Binding`

- **Description:** Every caller inside `plugin/bin/prawduct-hook` — `cmd_stop`'s `branch_plan`,
  `critic-begin`, `verify-records`, `infer-critic-mode`, `verify-chunk-refs`, the handoff writer,
  `cost-of-commit`'s entry, the briefing entry — takes `work_unit.resolve()`. `cmd_stop`'s
  `has_build_plan` still counts boxes in this wave, but on the bound plan only; the
  `_has_build_plan_in_state` OR-arm is **kept** (ST7 is Wave 2) and noted. `scope_unresolved_cause`
  is populated from `Binding.reason`.
- **Depends on:** Chunk 01
- **Artifacts consumed:** `1050-design.md` § 2; `plugin/bin/prawduct-hook` lines the inventory
  names (`cmd_stop` ~2728, the ephemeral-worktree guard ~8960 — read, not changed here).
- **Deliverables:** the hook callers migrated; `tests/test_stop_hook*.py` and
  `tests/test_infer_critic_mode*.py` extended with: a scratch worktree forked from a bound branch
  arms no Critic gate (the #648 trap, red first); mode inference on a branch no plan claims
  answers `none`, not another plan's chunk (#208, red first).
- **Tests:** the modules above, scoped to the files touched.
- **Acceptance criteria:** `grep -n "resolve_build_plan_path\|resolve_branch_plan"
  plugin/bin/prawduct-hook` returns nothing; both red-first tests pass.
- **Done when:**
  1. Acceptance criteria met and tests pass (ceiling as Chunk 02)
  2. Branch handed back; coordinator merges, reviews naming this chunk, resolves blocking findings
  3. Committed and chunk marked `[x]` in Status

### Chunk 04: `plan new` / `plan bind`, fragment and `closed-by` scope validation

- **Description:** New `plugin/lib/plan_mint.py`: `new(scope, branch, base, title, working)` and
  `bind(path, branch)` per `1050-design.md` § 1 — writes the plan from the template with
  `scope`/`branch`/`base`/`working-branches`, stubs the fragment, refuses a taken scope, a second
  claim on the branch, or the scratch branch pattern. `change_fragments.validate` gains the WU2
  scope check (matches a live-then-archived plan, or no plan exists). `lib/backlog` validates
  `closed-by` as `scope:<slug>` | PR | release tag against known scopes (BL2). Library and tests
  only; the `prawduct-hook plan` subcommand is wired in Chunk 06.
- **Depends on:** Chunk 01
- **Artifacts consumed:** `1050-design.md` § 1 and § 6; `plugin/lib/change_fragments.py`;
  `plugin/templates/build-plan.md`; `plugin/lib/backlog/` (the `closed-by` write path).
- **Deliverables:** new `plugin/lib/plan_mint.py`; `change_fragments.py` and the backlog adapter
  extended; new `tests/test_plan_mint.py`; `tests/test_change_fragments*.py` and the backlog
  adapter tests extended: a fragment whose scope a plan spells differently is refused at write
  (red first — today only CL7 notices); `closed-by: scope:nonexistent` is refused.
- **Tests:** the modules above.
- **Acceptance criteria:** `new` produces a plan and fragment that `change_fragments.validate`
  accepts and `work_unit.resolve()` binds on the named branch; the two refusals are red-first.
- **Done when:**
  1. Acceptance criteria met and tests pass (ceiling as Chunk 02)
  2. Branch handed back; coordinator merges, reviews naming this chunk, resolves blocking findings
  3. Committed and chunk marked `[x]` in Status

### Chunk 05: one home for the rule — prose

- **Description:** `methodology/planning.md` "Which plan is active" becomes the one paragraph
  `1050-design.md` § 2 "Prose" describes: a plan claims its branch, at most one claim per
  checkout, unbound is normal, a scratch worktree is unbound; the precedence list is deleted. The
  restatements in `skills/backlog/SKILL.md`, `skills/backlog/adapter-mode.md` and
  `skills/pr/SKILL.md` become one-line pointers; the PR skill's Merge Flow drops its pointer
  bookkeeping. `methodology/delegation.md` and `building.md` § Delegating: the two-kind worktree
  sentence replaces "tell it not to write `.prawduct/`"; the "delegate that governs" tell keeps
  "ran the Critic, updated project state". `docs/project-state-keys.md` marks `active_build_plan`
  deprecated with the window's condition. Nothing about ticking changes in this wave.
- **Depends on:** Chunk 01 (for the vocabulary; no code dependency)
- **Artifacts consumed:** `1050-design.md` § 2 "Prose", § 7; `1050-requirements.md` BR5/BR6.
- **Deliverables:** the files above; `tests/test_plugin_methodology_digest.py` and the token
  budget tests still green or their ceilings lowered in the same commit (a trim lowers its
  ceiling).
- **Tests:** the budget and digest tests; the citation-count tests that read methodology.
- **Acceptance criteria:** `grep -rn "active_build_plan" plugin/methodology plugin/skills` returns
  only `planning.md`'s one paragraph and the deprecation note; the delegation sentence appears in
  both methodology files and the old "don't write `.prawduct/`" instruction in neither.
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met and budget tests pass
  2. Branch handed back; coordinator merges, reviews naming this chunk, resolves blocking findings
  3. Committed and chunk marked `[x]` in Status

### Chunk 06: integration — shims, advisory, subcommand wiring, suite, cumulative review

- **Description:** `core.resolve_build_plan_path` and `buildplan_refs.resolve_branch_plan` become
  shims over `work_unit.resolve()` (one release, then deleted — recorded in Tradeoffs);
  `buildplan_refs.infer_scope_from_branch` is deleted, its logic moved into `plan_mint.new`'s
  suggestion. The `plan-unbound-legacy` advisory is registered and raised from `Binding.chosen_by
  in (legacy-pointer, legacy-default)`. `prawduct-hook plan new|bind` is wired. The full suite runs
  once. Version bump to 3.7.3-dev.5 (four files). Change fragment
  `.prawduct/changes/work-unit-binding.md` with a consumer note naming the deprecation and
  `plan bind`.
- **Depends on:** Chunks 02–05
- **Artifacts consumed:** everything above; `plugin/lib/core.py`; `plugin/lib/buildplan_refs.py`;
  the advisory registry.
- **Deliverables:** the shims, the deletion, the advisory, the subcommand, the bump, the fragment;
  the six Critic/PR/doctor skill-doc passages that still describe pointer-based scope derivation
  (`grep -rn active_build_plan plugin/skills` lists them) rewritten to the `Binding` rule or
  deleted; `tests/test_pr_reviewer.py::test_merge_flow_buildplan_cleanup_is_conditioned`
  rewritten to pin the new rule (a `branch:`-declaring plan needs nothing at merge) — it pinned the
  pointer step Chunk 05 deleted, and a prose ceiling run cannot see a repo-coupled test;
  `buildplan_refs.unticked_committed_chunk_notice` takes the bound plan instead of resolving its
  own; the hook's `_gate_plan_of()` collapsed onto one lib helper; Chunk 03's two xfail marks
  deleted; `tests/test_build_plan_resolution.py`'s "inline mirror" docstring and its two
  detached/outside-worktree pins rewritten to the new answer (`unbound`), reason in the fragment;
  `buildplan_refs.resolve_reviewed_plan`'s `gap=None` silence on single-scope repos (#1007(a))
  replaced by the `Binding`; the `closed-by` form (`scope:<slug>` | PR | release tag, bare slug
  tolerated) stated once in `skills/backlog/SKILL.md` and the six other passages that still say
  "bare scope or branch name" (`skills/backlog/adapter-mode.md`, `skills/pr/SKILL.md`,
  `skills/critic/cross-checks.md`, `templates/backlog.md`, `docs/principles.md`) pointed at it; `templates/build-plan.md`
  frontmatter comments corrected ("several plans may declare one branch", "resolves ahead of
  active_build_plan", "null is fine" for `scope:` are all false now) and `base:` /
  `working-branches:` documented there, since minted plans copy those comments verbatim;
  `tests/test_core*.py` and `tests/test_buildplan_refs*.py` adjusted so the shims' tests assert
  the new answer (never weakened: a test that pinned the old fallback is rewritten to pin the
  refusal, with the reason in the fragment).
- **Tests:** the full suite (`testament run`), recorded as the boundary run.
- **Acceptance criteria:** `1050-requirements.md` Acceptance 1, 2, 5 and 9 hold on this branch;
  `grep -rn "infer_scope_from_branch" plugin/` returns nothing; the suite is green; and every
  present-tense claim Chunk 05's prose makes is true at HEAD: `prawduct-hook plan bind` exists,
  the `plan-unbound-legacy` advisory is registered and fires on a pointer-only fixture, a scratch
  worktree's Stop hook arms no Critic gate, and `prawduct-hook plan resolve` (new, read-only)
  prints the `Binding` so a skill told to "resolve the plan the way governance does" has a command
  to run.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and the suite passes
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status

## Verification Strategy

Beyond tests: on this repo, with the finished `review-stats-dispositions` plan still live at
`artifacts/build-plan.md`, check out an unclaimed branch and confirm the briefing says *unbound*,
`infer-critic-mode` answers `none`, and a dry `critic-begin` records `scope: null`. Then
`plan new smoke-test --branch feature/smoke` and confirm the same surfaces bind. In a scratch
worktree forked from `feature/1050-work-unit-binding`, confirm the Stop hook arms no Critic gate.

## Governance Checkpoints

**Commit & PR cadence:** 01 commits after its `final` review. Each delegate hands back a branch; the
coordinator merges it into `feature/1050-work-unit-binding`, reviews the merge in `chunk` mode
naming the chunk, resolves blocking findings and commits. 06 commits first, then its `cumulative`
is the PR gate. One PR, to `develop`, via `/prawduct:pr`.

- After Chunk 01: the `Binding` API is final before any delegate is briefed — a field added later
  costs four re-briefs.
- Before briefing 02–05: re-check the partition against the machine (four isolated worktrees,
  each running only its own test modules; the coordinator runs nothing until integration).
- After Chunk 06 (cumulative): Acceptance 1, 2, 5, 9 verified live, not from the tests alone.
