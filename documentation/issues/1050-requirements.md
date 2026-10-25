# Issue #1050 — work units: one identity binds plan, branch, fragment and backlog item; chunk status stops being hand-ticked: Requirements

`status: draft · stage: design · area: governance · added: 2026-10-25 · amended: 2026-10-24 (owner
rulings D1–D6, BR5/BR6 amended, ST8/EV1–EV2/DG1–DG2 added) · source: owner session · issue:
https://github.com/brookstalley/prawduct/issues/1050 · design: 1050-design.md`

Related: #1007 (two readers of "which plan is this review of"; shape (b) fixed by #1049, shape (a)
open), #843 (a finished branch that never got a PR), #834 (derive the change record at merge),
#712 (the GV3 sweep for merged work whose item is still open), #672 (coverage composes by tree,
gates key on identity). Precedents, closed: #208, #283, #344, #541, #448, #312, #479 (plan
misattribution and the single pointer), #558, #587, #252, #229, #386, #516, #188, #327, #380,
#454, #470, #378, #911, #999 (two meanings of a checkbox, and chunk inference graded wrong).
Unmerged prior art: `docs/one-home-per-fact` (`documentation/one-home-per-fact-requirements.md`
R6) and `docs/consumer-overhead-program` (pain pattern 5, "misattributed gates and advisories").

This document states the problem and what must be true. It does not choose a design; design is
the next stage.

## Problem

One piece of work in a prawduct repo has no single identity. It shows up as a build plan, a git
branch, a change fragment, one or more backlog items, review facts, ledger events and commits.
Each of those names the work its own way, and governance has to work out which of them belong
together every time it asks a question. It works that out by several routes that can disagree.
When they disagree, gates arm against the wrong plan, reviews grade the wrong chunk and telemetry
counts work under the wrong scope. All of these failures look like correct operation.

Separately, whether a chunk is done is a line of markdown the agent edits by hand (`- [x]`), and
every gate believes it. The tick has to happen at one particular moment (after the chunk's
review, except on short plans, where it is at commit, and never for the last chunk until after the
PR's cumulative review), because ticking the last box switches the Critic gate off. Agents and
the owner find that rule confusing. Getting it wrong either disarms a gate early or leaves a
finished plan reading as live.

The owner's framing, 2026-10-25: branch↔plan resolution "has been a problem for a long time"; the
checkboxes "have been a source of constant confusion and difficulty"; and the change-log refactor
(fragments keyed by scope, #1012) makes this the moment to rethink how these artifacts and
concepts intersect.

### What happened this session (2026-10-25)

- A Critic review of `fix/plan-archive-scope-name` was written to the governance ledger as
  `scope=review-stats-dispositions`: the scope of a finished plan on a different, merged branch.
  `critic_consolidate` had correctly resolved no scope. Then `ledger._scope_from_plan` fell back
  through `core.resolve_build_plan_path` to the leftover `artifacts/build-plan.md`. The event was
  corrected by hand, because the append-only ledger has no correction mechanism.
- PR #1049 fixed the root cause for one shape: a plan declaring `branch:` no longer governs other
  branches through the pointer or conventional-path fallback. Making that change required
  touching 14 resolver callers and rewriting ten prose documents that described the old rule.
- A finished plan retained for its release made the session briefing say "archive the plan" on
  every unclaimed branch. Following the PR skill's step on gitflow means ignoring that advice.

## Grounding facts

Checked against `develop` after #1049 (3.7.3-dev.4), 2026-10-25.

**How a plan becomes "the plan for this work": four routes, two resolvers.**
- The routes: a frontmatter `branch:` claim (`core.resolve_branch_claim`); the
  `active_build_plan` pointer (`core.pointer_plan_path`); the conventional
  `artifacts/build-plan.md` (`core.DEFAULT_BUILD_PLAN_REL`); and matching the branch name, or
  its last segment, against a declared `scope:` (`buildplan_refs.infer_scope_from_branch`, whose
  docstring says "A name is the only signal").
- Two resolvers compose those routes differently. `core.resolve_build_plan_path` uses the claim,
  then the pointer, then the default, and has 13 callers outside core. `buildplan_refs.
  resolve_branch_plan` uses the claimed scope, then the branch-name scope match, then the
  pointer, and has 10 callers, including the Stop gate, mode inference, `critic-begin`,
  `verify-records`, the PR payload and `cost-of-commit`. They disagree when a branch name matches
  a scope whose plan is not the claiming or pointed plan.
- The unticked-chunk notice, `verify-chunk-refs`, the briefing's staleness and `Resume:` lines,
  the handoff and the ledger's scope fallback use the first resolver. The gates use the second.
- Explicit overrides add three more inputs: `--scope`/`--chunk` on `critic-begin` and
  `verify-records`, the manifest's `scope`/`chunk`, and `PRAWDUCT_VERIFY_CHUNK_ID`.
- The precedence is restated in prose in `methodology/planning.md:54-56` (its declared single
  home), `skills/backlog/SKILL.md:131`, `skills/backlog/adapter-mode.md:284` and
  `skills/pr/SKILL.md:90`.

**"Scope" (the work's name) is stored or derived in eight places.** Plan frontmatter `scope:`;
the plan filename stem (the ledger fallback); the branch name (inference); the conventional-commit
scope (`_COMMIT_SCOPE_RE`); the fragment `scope:` plus its filename stem; the legacy change-log
`scope=`; the manifest, review-fact and ledger `scope` (each with its own fallback); and backlog
`closed-by`, which is free-form. In `lib/backlog/`, "scope" is a homonym meaning `owner/repo`.
The fragment's scope must equal the plan's `scope:` (FRG2, `data-model.md:341`), but nothing checks
that at write time. Only the release-time advisory (CL7) notices a mismatch.

**"Is chunk N done?" has six readings.**
- The Status box in the working tree (`resolve_chunk_progress`).
- The Status box at HEAD (`committed_chunk_progress`).
- Commit subjects naming the chunk (`_committed_chunk_ids`, reporting only, DV7).
- The legacy `project-state.yaml` `build_plan.chunks[].status`, which is ORed into the Stop
  hook's `has_build_plan`.
- The archive stamp `unbuilt_at_archive`.
- Two private checkbox scans that bypass the shared parser (`pr_payload._section_build_plan`
  scans the whole file, and `buildplan_refs:1281` re-checks prefixes).

"Is the plan finished?" behaves four ways on a plan with no Status items: unfinished
(`has_unfinished_chunk`), not complete (`build_plan_is_complete`), refused
(`incompleteness_reason`), and no governed work (`_has_active_build_plan_file`).

**The tick is read at about 30 consumer sites** (inventory, 2026-10-25), and they make these decisions: the Stop hook's Critic gate (`cmd_stop`: "the last tick
disarms"), the short-plan and extension deferrals, review-mode inference (`critic_mode`, 12
sites), the current-chunk choice for record lint and `verify-chunk-refs`, owed-review advice at
consolidation, `cost-of-commit` pricing, briefing staleness and `Resume:`, `plan-backfill`'s
archive refusal (#634) and the archive stamp. No Python code writes a tick. 13 prose files in `plugin/` discuss ticking Status (grep for
`tick`/`[x]` together with `Status`), and the instructing ones include the session digest, the
build-plan template, the PR skill, `planning.md`, `building.md` and the PR review protocol.

**Measured on this repo:**
- One live plan. 162 archived plans: 78 declare `branch:` and 84 do not; 161 declare `scope:`.
  11 archived plans carry unticked boxes.
- Since 2026-06-01, 177 of 2,666 commits on `develop` changed only a build plan, and 35 commit
  messages mention ticking or Status boxes. Not all of the 177 are tick commits.

**Backlog↔work links.**
- `working-branch` (`owner/repo@branch`) marks an item as being worked and excludes it from
  `pick`. Nothing compares it with the current branch or a plan.
- `closed-by` is free-form, and no code joins it to a plan or fragment.
- The fragment's `closes:` is the single home for which items a change closes (#1012), and
  `closed-by` is its back-reference.
- Build-plan-aware ranking in `pick` is prose only; `lib/backlog/` reads no plan.

## Decisions already made that bind this work

These are ratified and implemented. Where a requirement below departs from one, the departure is
named, and making it is a recorded norm amendment for the owner (`docs/norms.md`), not a doc edit.

- **DV3 (`governance-artifact-lifecycle-requirements.md:145-160`; binding home `data-model.md`
  § Direction, lines 65 and 72; `cross-cutting-concerns.md:47`).** Status checkboxes are
  hand-maintained and authoritative, the single reading of chunk progress. The recorded why is
  that git-derived progress was rejected: "a chunk's last commit lands before its Critic pass and
  its reflection. The checkbox marks the end of **governance**; a commit marks the end of
  **coding**." Deriving from git switched the gates off early (the `gates.py:808` incident).
  DV2: no command may exist to overwrite hand-authored governance state. DV7: git is a reporting
  tripwire only.
- **No model in a fact's write path; derived views never feed a gate** (`data-model.md`
  § Direction).
- **Plans are never deleted.** There are two terminal states, the archive is history, and a live
  plan wins over an archived namesake (BP1-BP10).
- **`branch:` is the one non-inferential binding.** A plan declaring it governs that branch only
  (#1049). Several plans per branch is ordinary; there is one plan per scope (`planning.md:54-66`).
- **A fragment's scope is the plan's scope, two branches never share a scope, and the fragment's
  `closes:` is the single home of what a change closes** (FRG1, FRG2; `1012-requirements.md:72`).
- **Backlog status is never inferred from plans, change logs or commits** (D4, then GV10).
  Holding an item is `working-branch`; `closed-by` names a branch, PR or release, never a bare
  chunk id.
- **Every fact has one home, and a fact is the whole predicate** (`architecture.md` § Direction,
  in transition; its stopgap expires 2026-12-01).
- **Proportionality.** No new hard gates for backlog hygiene (GV12). Fixes are minimal and
  external (`work-model.md` §2).

**The conflict this document has to surface.** The owner's ask, to stop hand-ticking chunk status,
reverses DV3. DV3's reason is sound, and it is about *git*: git cannot see the end of governance.
It does not rule out deriving status from the *governance events themselves*. Those events (a
Critic review consolidated with zero unresolved blocking findings for that chunk, and the
reflection) are already recorded by code in the evidence store, and no model writes them. Whether
those events are reliable enough to replace the tick depends on attribution, which is the first
half of this problem. So the requirements below put identity and binding first and status second,
and the DV3 amendment is decision D1.

## Definitions

- **Work unit.** One coherent piece of work that ships under one change record: what a plan
  plans, a branch carries, a fragment records and a backlog item asks for. *Inferred:* the unit
  is today's plan `scope:`, which is why fragments are already keyed by it.
- **Identity.** The one name a work unit is known by. Every artifact belonging to the unit carries
  it or references it.
- **Binding.** The recorded relation between a work unit and the branch or branches carrying it.
- **Chunk done.** A chunk's governance is complete: it is built, committed and reviewed with no
  unresolved blocking finding (or, on a short plan, committed with its review deferred to a
  recorded later review), and its reflection is captured. Never "merged" or "released"
  (`planning.md:58`).
- **Governing plan.** The plan whose chunks the gates, mode inference and reviews act on for the
  checked-out work.

## Requirements

### Identity

- **WU1** Every work unit has exactly one identity, declared once, at the moment the unit comes
  into existence. Every other artifact of the unit carries that identity or references it, and
  none restates it under a different spelling.
- **WU2** The identity is machine-validated wherever it is written. A plan, fragment, review fact,
  ledger event or backlog back-reference that names a unit that does not exist, or names the
  same unit two different ways, is caught at write time, not at release (today's CL7 gap).
- **WU3** Governance never infers a work unit's identity from a name that merely resembles it,
  such as a branch name or a filename stem. Inference from names is retired or demoted to a
  suggestion a human confirms (D3).
- **WU4** The identity is stable for the unit's whole life. Renumbering chunks, renaming a branch,
  moving a plan into the archive or cutting a release never changes it (BP7).

### Binding (plan ↔ branch)

- **BR1** "Which work unit, and which plan, is this checkout working on?" has one answer, computed
  by one owner. Every consumer gets the answer, not the walker: the Stop gate, mode inference,
  review dispatch, record lint, the ledger, the briefing, the PR payload, `cost-of-commit` and the
  backlog skill. The second resolver and its prose restatements go away.
- **BR2** The binding is recorded when the work starts, without the agent having to remember to
  write it. *Inferred:* recorded when the plan is created on, or the branch is created for, the
  unit.
- **BR3** The answer has three outcomes, each reported distinctly: the checkout is bound to unit X;
  the checkout is bound to no unit (chores, small fixes, integration branches); or the binding is
  broken (it names a branch that does not exist, or several units claim incompatibly). An unbound
  checkout is a normal state, never an error, and it never borrows another unit's plan.
- **BR4** Every review, ledger event and gate decision records the unit it was about, taken from
  BR1's answer, or records "none". No consumer substitutes a fallback of its own. (This is the
  defect class #1049 closed for one route.)
- **BR5** *(amended 2026-10-24, owner)* At most one live plan **claims** the checked-out branch.
  Any number of plans may be *present* on it — a merged child's plan rides along inert until its
  release — and presence binds nothing. Two live claimants is a broken binding (BR3), reported,
  never resolved by precedence. A unit has one integration branch and may declare working
  branches that merge into it (D4); it never spans two integration branches. *Superseded:* the
  precedence list at `planning.md:56` and "several plans per branch is ordinary".
- **BR6** *(amended 2026-10-24, owner)* Detached HEADs, linked worktrees, delegate worktrees and a
  checkout outside git resolve predictably and say which case they are in. A harness scratch
  worktree (`gitstate.is_ephemeral_worktree`) is **unbound by construction**: it resolves no unit,
  owes no review and writes no review fact; its work is attributed when the coordinator merges
  and reviews it. A *named* branch worked in a worktree binds through its unit's declaration
  (`branch:` or `working-branches:`), the same as any checkout. This is #648's
  durable/disposable line made the binding rule.

### Chunk status

- **ST1** Whether a chunk is done (the definition above) is answered from a recorded fact that is
  written by code at the governance event itself. A hand-edited line is not that fact (D1). No
  model sits in the write path of the fact any gate reads.
- **ST2** The Stop hook's Critic and reflection gates stay armed until governance of the last
  chunk is complete. They are never switched off by a commit or by an edit the agent makes before
  its review. That is DV3's requirement, preserved.
- **ST3** Short plans and deferred reviews keep working. A chunk committed with its review
  deferred is a distinct, recorded state. The later review that covers it completes it, without a
  second hand edit.
- **ST4** Dropping, deferring or descoping a chunk is an explicit, recorded decision with a reason,
  made by a human or agent on purpose. It is never inferred from the absence of a tick (BP10's
  superseded state, at chunk granularity).
- **ST5** A reader can still see a plan's progress where they look today, in the plan and in the
  briefing, without editing anything. Any rendered progress is a view, and no gate reads a view
  (`data-model.md` § Direction).
- **ST6** "Is the plan finished?" and "which chunk is current?" each have one answer and one
  owner. A plan with no chunks answers the same way everywhere (today it answers four ways).
- **ST7** The legacy `project-state.yaml` `build_plan.chunks[].status` reading stops being a
  second input to the gates, or is migrated.
- **ST8** *(added 2026-10-24)* A review fact names the **set** of chunks it certifies, declared
  at dispatch and confirmed by the coordinator; the framework proposes the set from the reviewed
  diff and the chunks' deliverables. Parallel delegation lands several chunks per review, and a
  singular chunk chosen by "first unticked" misnames what was reviewed.

### Evidence

- **EV1** *(added 2026-10-24)* Review and resolution facts are keyed by the trees they cover, as
  today, so a consumer that squash- or rebase-merges loses no verdict a branch-time gate reached.
  Squash and rebase are not forbidden; where history is rewritten, only history-derived lifecycle
  degrades, and it falls back to the PR record.
- **EV2** *(added 2026-10-24)* The facts a gate reads travel with the branch: a second clone or
  machine reconstructs the same verdict from the same facts (the data-model norm's stated why,
  which today holds only across worktrees of one clone because the store is `.git`-local).
  Transport is a git-native ref pushed with the branch, never a network service (NF1,
  `architecture.md` local-first).

### Delegation

- **DG1** *(added 2026-10-24)* The delegation protocol's division — delegates build and prove
  their own change under a ceiling; the coordinator integrates, reviews and governs — is
  unchanged and becomes structural through BR6: no refusal list is needed for a checkout that
  is bound to nothing.
- **DG2** *(added 2026-10-24)* A delegate's narrowed test run is recorded as evidence the
  coordinator can see, attributed to the tree it ran on and marked as narrowed. The ephemeral
  guard's rationale (a `.prawduct/` write strands at merge) does not reach the shared store, so
  refusing the fact half of `test-evidence record` discards evidence for no reason.

### Lifecycle

- **LC1** A work unit's lifecycle (in progress, merged and awaiting release, released, superseded)
  is derived from facts git and the change record already hold wherever they can be observed
  (branch existence, merge into the base, release tag, fragment present or cut). It is stored only
  where it cannot be observed. *Inferred:* "observable beats stored" (`hook-surface.md` learning).
- **LC2** A merged-but-unreleased unit on gitflow is visibly live and inactive. It governs nothing,
  is advised about nowhere, and is archived by the release mechanically, with no step for the
  agent to remember at merge (generalises #1049).
- **LC3** Plans are still never deleted, and the archive still ends a unit's live presence
  (BP1-BP10). Archival of a unit whose chunks are not all done still requires a recorded
  superseded decision (the #634 ruling).

### Backlog links

- **BL1** From a work unit you can find the backlog items it serves, and from an item its work
  units, by following references, never by inferring status (D4/GV10 hold).
- **BL2** The fragment's `closes:` stays the single home of what a unit closes. `closed-by` is a
  back-reference that names the unit's identity in a validated form, not free text.
- **BL3** `working-branch` and the unit's binding cannot silently disagree. An item marked as
  worked on branch B while B is bound to a unit that does not serve it is reported (advisory,
  GV12).

### Migration and compatibility

- **MG1** Every onboarded consumer repo keeps working through the transition: existing plans,
  pointer-only plans, plans with ticked boxes and archived plans. Nothing is reinterpreted
  silently. A repo is either migrated by one reviewable command (`/prawduct:doctor` or
  `/prawduct:migrate`) or keeps the old behaviour until it is.
- **MG2** Existing ticked boxes are imported as recorded completion, marked as imported rather than
  evidenced, so history is not rewritten and no gate loses its answer at cutover.
- **MG3** Retiring the pointer, the conventional-path default or branch-name inference is a
  deprecation with a stated window, a briefing notice in affected repos and a migration path. It
  is never a same-release removal (D2, D3).

### Non-functional

- **NF1** The answers to BR1, ST1 and ST6 are cheap enough for the hot paths (session start, every
  Stop, review dispatch): no network, and no cost that grows with the archive (BP9).
- **NF2** Authority fails closed and advice fails soft (`architecture.md` § Direction). An
  unreadable binding blocks nothing that only advises, and never lets a gate pass on a guess.
- **NF3** The new model is simpler for the agent to operate than the old one. The tick-timing
  rules, the "don't tick the last box yet" exception, the pointer bookkeeping and the
  precedence restatements leave the session digest, the template and the skills, net of what
  the model adds. Measured by prose and token budget, not asserted.
- **NF4** Every requirement above is pinned by a test that fails on the shipped misattribution
  shapes: the #1049 ledger event, #1007 shape (a), #208's mode inference on an unrelated plan,
  and #541's third reader.

## Acceptance

1. On a repo with a finished, retained plan and an unrelated branch, no gate, review, ledger
   event, briefing line or backlog ranking refers to the finished plan. The same holds for a
   plan that declares no branch (#1007 shape (a)).
2. One function answers "which unit and which plan is this checkout". Grepping for the retired
   resolvers and the prose precedence copies returns only that owner and its documentation.
3. An agent completes a multi-chunk plan, including a short-plan deferral and the PR's cumulative
   review, without editing a Status line. The Critic gate stays armed until the final review is
   consolidated and disarms only then.
4. Dropping a chunk without a recorded decision leaves the plan unfinished and says why.
   Recording the decision finishes it.
5. A fragment, review fact or `closed-by` naming a nonexistent or misspelled unit is refused or
   reported where it is written.
6. A consumer repo with pointer-only plans and ticked boxes keeps passing its gates unmigrated,
   and passes identically after the migration command.
7. The session digest and the build-plan template are shorter than today, and the tick-timing
   instructions are gone from them.
8. A coordinator merges two delegate branches carrying chunks 01 and 03, runs one review naming
   both, and both read as done while 02 stays open — without a hand edit.
9. A scratch delegate worktree on a bound branch's fork resolves no unit and arms no gate; a named
   working branch declared by the plan resolves the unit with role `working`.

## Decisions (ruled 2026-10-24, owner, design session)

Recorded here and in `1050-design.md` § Rulings so the DV3 amendment is not its own only witness.
The design doc carries each ruling's reasoning; this list is the record.

- **D1 — yes.** DV3 is amended: chunk status derives from the review and resolution facts written
  at the governance event, never from git and never from a hand edit. DV3's why ("a commit marks
  the end of coding, not governance") is preserved; only the carrier changes. The Stop gate's
  verdict was already evidence-derived, so the change reaches arming and chunk selection only.
- **D2 — retire both**, read-only through a deprecation window (MG3) for repos with no plan
  declaring a binding.
- **D3 — retire**; a suggestion at minting only.
- **D4 — yes, bounded**: one integration branch per unit, plus declared working branches that
  merge into it. A follow-up fix is a new unit.
- **D5 — the plan mints the identity** (its `scope:`); the branch binds it; everything else
  references it. Issue numbers are `closes:` references.
- **D6 — no.** Reflection stays a session-end gate.
- **Squash/rebase are not forbidden** (EV1). Merge-only enforcement is a `doctor` offer.

## Research for design — findings (2026-10-24)

- **Attribution today.** 1,247 review facts in this repo's store: `scope_chosen_by` =
  `branch-name` 618, `not-resolved` 234 (scope null), `explicit-args` 46, absent (pre-field)
  349. About 19% of attributed-era reviews could not say what they reviewed, and the ledger then
  borrowed a scope for them. Re-derive: iterate `kind == "review"` facts in
  `<git-common-dir>/prawduct/evidence.jsonl` and count `body.scope_chosen_by`.
- **The store is clone-local.** `evidence.store_path` is `<git-common-dir>/prawduct/evidence.jsonl`;
  the ledger is gitignored per worktree. Neither is pushed. This is EV2's origin.
- **Consumer repos running pointer-only plans** (live plan, no `branch:`, `active_build_plan`
  set): faidh, metallm, discodon (kairo worktree). hallucinote has a live plan with neither
  `scope:` nor `branch:`. Sizes MG1–MG3 at three repos plus one unbound plan.
- **Stacked-PR binding.** GitHub binds PR↔branch natively, retargets a PR whose base branch is
  merged and deleted, and fires closing keywords only on the default branch (already in the PR
  skill). Merge-commit history carries a stack without rewriting; the base of a branch is the one
  relation git does not persist, so the plan records `base:`.

## Scope-out

- Changing what a chunk *is*, how plans are chunked, or Critic modes beyond what ST2-ST3 require.
- Backlog status inference from plans or commits (D4/GV10 stand).
- The git hygiene of merged branches and worktrees (#1041) and stranded-branch detection (#843),
  beyond consuming LC1's answer.
- Rewriting archived plans. They are history, and MG2 imports their state rather than editing it.
- The change-fragment format itself (#1012), except for WU2's validation of its scope.
