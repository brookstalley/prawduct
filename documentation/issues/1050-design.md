# Issue #1050 — work units: one identity binds plan, branch, fragment and backlog item; chunk status stops being hand-ticked: Design

`status: draft · stage: design · area: governance · added: 2026-10-24 · source: owner session ·
issue: https://github.com/brookstalley/prawduct/issues/1050`

Requirements: `1050-requirements.md` (amended 2026-10-24 with the rulings below). Where this doc
and the requirements differ, the requirements bind; this doc chooses how to meet them.

Related: #1007 (shape (a) is closed by Wave 1), #1049 (the one-route fix this generalises), #1012
(fragments keyed by scope; unchanged here except for write-time validation), #648 (the
scratch-vs-named worktree line this design inherits), #634 (the archive sweep's precondition
becomes the derived "finished"), #843 and #1041 (consume the lifecycle answer; out of scope).

## Summary

One piece of work is a **work unit**, named by its **scope** slug, minted once by one command that
also binds a branch to it and stubs its change fragment. Which unit a checkout is working on has
**one resolver with three answers** (bound, unbound, broken) and **no fallbacks**: a live plan
either claims the checked-out branch or it does not. Whether a chunk is done is **a query over
code-written review facts**, not a line of markdown; the `## Status` block leaves the template and
is rendered on demand. The Stop hook's Critic gate **arms on binding and discharges on coverage**,
which it already computes from the evidence store, so "the last tick disarms the gate" ceases to be
a concept. Review facts **name the set of chunks they certify**, which is what parallel delegation
needs and the serial "first unticked box" never gave. Evidence **travels with the branch** as git
notes keyed to the reviewed commit and carrying the reviewed trees, so a second clone reconstructs
every verdict and the data-model norm's own promise ("any worktree reconstructs the same verdict")
becomes true across clones. Lifecycle is **observed from git**, stored nowhere.

Three waves, each shippable alone. Wave 1 is pure deletion plus one new owner; Wave 2 removes the
tick; Wave 3 adds transport.

## Rulings recorded (owner, 2026-10-24)

The requirements doc's open decisions, as ruled in the design session, and the three amendments the
session added. Each is a departure from, or a sharpening of, a ratified norm, and is recorded here
and in the requirements so the amendment is not its own only witness (`docs/norms.md`).

- **D1 — yes, amend DV3.** Chunk status derives from governance events (the review and resolution
  facts), never from git and never from a hand edit. DV3's stated why — "a commit marks the end of
  coding, not governance" — is preserved exactly: the fact that completes a chunk is written at the
  governance event. What changes is only that the hand tick is no longer the carrier.
  *Why the change is smaller than it looks:* the Stop gate's verdict is already evidence-derived
  (`gates.session_review_verdict` → `coverage_algebra.coverage_verdict`); the tick's roles were
  arming the gate, picking the current chunk, and feeding advisory readers. None of those is a
  verdict.
- **D2 — retire the pointer and the conventional path**, with the MG3 window. The pointer's residual
  job (tie-breaking within a branch) disappears with D-BR5 below.
- **D3 — retire branch-name → scope inference.** A suggestion at minting time only.
- **D4 — yes, bounded.** A unit has one **integration branch** (where its PR comes from) and may
  declare **working branches** that merge into it and never into the base directly. A unit never
  spans two integration branches; a follow-up fix is a new unit.
- **D5 — the plan mints the identity.** The branch binds it; the fragment and every fact reference
  it. Issue numbers are `closes:` references, never the identity.
- **D6 — no.** Reflection stays a session-end gate. "Chunk done" is built, committed and reviewed
  with no unresolved blocking finding.
- **D-BR5 (amends BR5) — at most one live plan *claims* the checked-out branch.** Any number of
  plans may be *present* (a merged child's plan rides along inert until release). "Several plans
  per branch is ordinary" is retired as a design goal; release branches are unbound.
- **D-BR6 (amends BR6) — a harness scratch worktree is unbound by construction.** It resolves no
  unit, owes no review, writes no fact. A *named* branch worked in a worktree binds through its
  unit's declaration (`branch:` or `working-branches:`). This is #648's durable/disposable line,
  made the binding rule.
- **D-ST8 (new) — a review fact names the set of chunks it certifies.** Parallel delegation lands
  several chunks per review; a singular `chunk` chosen by "first unticked" misnames what was
  reviewed.
- **Squash and rebase are not forbidden.** The design is tree-keyed and degrades gracefully where a
  consumer rewrites history (§ Evidence transport). Enforcing merge-only is a `doctor` offer, not a
  requirement.

## Design

### 1. Identity and minting

The identity is the plan's `scope:` — a slug matching the fragment filename rule
(`change_fragments`: `[a-z0-9][a-z0-9-]*`), unique across live and archived plans and fragments in
the repo. It is minted by one command and written to three places in one act:

```
prawduct-hook plan new <scope> [--branch <name>] [--base <branch>] [--title T] [--working]
```

- Writes `.prawduct/artifacts/build-plan-<scope>.md` from the template with frontmatter
  `scope`, `branch` (default: the checked-out branch; `--branch` creates it from `--base`), `base`
  (default: the checked-out branch's upstream base, else the repo's integration branch per
  `project-state.yaml`), and an empty `working-branches: []`.
- Stubs `.prawduct/changes/<scope>.md` with the same `scope`, `type` and `title`, and a
  `## Consumer note` placeholder that `change_fragments` already refuses to ship unfilled.
- Refuses when the scope is taken, when a live plan already claims the branch, or when the branch
  is the harness scratch pattern.

`prawduct-hook plan bind <path> --branch <name>` writes `branch:` into an existing plan (the
migration path for unbound live plans; `doctor` offers it). `plan new --working` adds the
checked-out branch to the bound unit's `working-branches:` instead of minting.

**WU2 at write time.** `change_fragments.validate` gains a scope check: the fragment's `scope`
matches a plan (live first, then archive) **or** no plan exists and the fragment is the unit's
only declaration (small fixes have no plan; the fragment is then the unit). A fragment naming a
scope that a plan spells differently is refused where it is written. CL7 stays as the release-time
backstop and should fire zero times once this lands (a test asserts the writer path refuses what
CL7 would catch).

### 2. The resolver — one owner, three answers

New module `plugin/lib/work_unit.py`:

```python
@dataclass(frozen=True)
class Binding:
    state: Literal["bound", "unbound", "broken"]
    scope: str | None          # bound only
    plan_path: Path | None     # bound only
    role: Literal["integration", "working"] | None   # which branch kind the checkout is
    reason: str | None         # broken / unbound explanation, one sentence, for the briefing
    chosen_by: Literal["binding", "legacy-pointer", "legacy-default", "none"]

def resolve(project_dir, *, branch=None) -> Binding
```

Algorithm, in full:

1. If HEAD is detached, the checkout is outside a work tree, or the worktree is the harness
   scratch kind (`gitstate.is_ephemeral_worktree`) → `unbound`, reason names the case (BR3, BR6).
2. Claimants = live plans (`plan_index.iter_scoped_plan_candidates`, archive pruned) whose
   `branch:` equals the current branch (role `integration`) or whose `working-branches:` contains
   it (role `working`).
3. One claimant → `bound`, `chosen_by: binding`. Zero → step 4. Two or more → `broken`, reason
   lists the claimants (this can arise only from merging two claiming branches; `plan new`
   refuses the second claim on one branch).
4. **Legacy window only** (MG3): if no live plan in the repo declares `branch:` at all, and the
   `active_build_plan` pointer or `artifacts/build-plan.md` names a live plan that itself declares
   no `branch:`, resolve it with `chosen_by: legacy-pointer|legacy-default` and raise the
   `plan-unbound-legacy` advisory naming `plan bind`. A plan declaring *some* `branch:` is never
   served by this step (#1049's rule, now the whole rule). Otherwise `unbound`.

Every consumer takes `Binding`, not the walker. The two resolvers it replaces,
`core.resolve_build_plan_path` (13 callers) and `buildplan_refs.resolve_branch_plan` (10 callers),
become thin shims over `resolve()` for one release and are then deleted; `buildplan_refs.
infer_scope_from_branch` is deleted in Wave 1 (D3) except as the suggestion inside `plan new`.
The explicit overrides (`--scope`/`--chunk` on `critic-begin` and `verify-records`, the manifest's
fields, `PRAWDUCT_VERIFY_CHUNK_ID`) remain, recorded as `explicit-args`.

**BR4.** `critic_consolidate.build_fact_body` records `scope` and `scope_chosen_by` from the
`Binding` (`binding | explicit-args | none`); `branch-name` and `not-resolved` stop being written
(readers tolerate them in history — additive-first, `api-contract.md` § Direction). The ledger's
`_scope_from_plan` fallback is deleted; a ledger event records the fact's scope or `null`. The PR
payload, `cost-of-commit`, the briefing's `Resume:` and staleness lines, `verify-chunk-refs` and
the handoff all read `Binding`.

**Prose.** `planning.md:54-56` becomes the one home of the rule, now one paragraph: a plan claims
its branch; one claim per checkout; unbound is normal. The restatements in
`skills/backlog/SKILL.md`, `skills/backlog/adapter-mode.md` and `skills/pr/SKILL.md` become
pointers. The PR skill's Merge Flow loses its pointer bookkeeping entirely.

**Legacy window (MG3).** Step 4 ships in Wave 1 and is removed no earlier than two minor releases
later, and only after a release in which the `plan-unbound-legacy` advisory has been observed to
fire on no known consumer (measured, not asserted). Known consumers running pointer-only plans on
2026-10-24: faidh, metallm, and discodon's kairo worktree.

### 3. Chunk status as a query

New module `plugin/lib/plan_status.py`, the one owner of ST6's two questions:

```python
def chunk_states(plan, facts) -> dict[str, ChunkState]
    # ChunkState = open | built | done | dropped
def is_finished(plan, facts) -> bool          # every chunk done or dropped
def current_chunks(plan, facts) -> list[str]  # open chunks, in plan order
```

- **done**: there exists a `review` fact whose body `scope` is this unit, whose `chunks` contains
  the id, whose blocking count is zero or whose every blocking finding has a `resolution` fact
  with a passing disposition (the rule `dispositions.census` already owns), and whose
  `head_commit` is reachable from the unit's integration branch or a declared working branch (in
  Wave 3, equivalently: the note is on a commit in that history). Mode labels do not matter, as
  they do not for coverage today.
- **dropped**: the plan's frontmatter `dropped:` lists the id with a reason (ST4). A declaration,
  hand-written on purpose; never inferred.
- **built**: a rendering convenience only — a commit on the branch whose subject names
  `Chunk <id>` (`_committed_chunk_ids`, DV7) or whose diff touches the chunk's Delivers paths. No
  gate reads it; the short-plan "committed, review deferred to the boundary" state is this, and
  the boundary review's `chunks` list completes it (ST3) with no second write.
- **open**: otherwise.

`is_finished` replaces the four readings (`has_unfinished_chunk`, `build_plan_is_complete`,
`incompleteness_reason`, `_has_active_build_plan_file`'s count). A plan with no chunks is
`finished` everywhere. The #634 archive-sweep precondition becomes `is_finished` — still
deterministic, still no model in the path; what the sweep declines is still one `--state
superseded` from its terminal state. `unbuilt_at_archive` is stamped from `chunk_states`.

**ST8 — the review names its chunks.** `critic-begin --chunks 01,03` (repeatable; `--chunk`
stays as a one-element alias for one release). The skill proposes the set: for `chunk` mode, the
open chunks whose Delivers paths intersect the dispatch diff; for `final`/`cumulative`, every
open chunk. The coordinator confirms or edits; the manifest carries `chunks`, the fact carries
`chunks` (and `chunk` = first element for one release, for old readers). Mode inference stops
reading boxes: `infer-critic-mode` uses `current_chunks()` and the plan's short-plan rule.

**The gate (ST2).** `cmd_stop`'s `has_build_plan` becomes `resolve().state == "bound"` and the
plan is live. The unticked-box count and the `project-state.yaml` `chunks[].status` scan are
deleted (ST7). The verdict is unchanged: coverage of the session's judgeable change. The
"all boxes ticked → nudge a final" advisory becomes "every chunk done or dropped and the latest
fact is not final/cumulative → nudge". After the boundary review, HEAD's tree is the reviewed
tree, so a finished plan passes every Stop without any disarming step.

**Rendering (ST5).** The template loses `## Status`. `prawduct-hook plan status [<path>]` prints
the chunk table (id, state, certifying fact id, date); the briefing's build-plan line and the
`/clear` handoff call it. The unticked-committed advisory becomes "built but not done" from
`chunk_states`.

**Migration (MG1, MG2).** `doctor` detects a live plan with a `## Status` block. For each ticked
box it appends one `chunk-imported` fact (new kind; `{scope, chunk, source: "status-box",
imported_at}`), code-written from the box, no judgment anywhere; `chunk_states` counts an imported
fact as `done`, tagged `imported` in the rendering. The block is then removed from the plan in the
same reviewable commit. Archived plans are history and are not touched; their boxes render as
they always did. Unmigrated repos keep passing: until a plan has no `## Status` block,
`chunk_states` reads the boxes as imported facts in memory (same code path, nothing written).

### 4. Evidence transport — git notes

`refs/notes/prawduct`. At consolidation, after the store append, `evidence.append_fact` also runs
`git notes --ref prawduct append -F <fact-json> <head_commit>` for `review` and `resolution` facts
(the kinds the coverage verdict reads; observational kinds stay store-only). The note body is the
fact envelope, one JSON object per line — the store's format, so a note *is* store lines on a
commit, and ingestion is a line-by-line `append_fact` deduplicated by fact id.

- **Cumulative across rounds.** Each consolidated round appends. Rounds normally sit on different
  commits (review on C1, fixes land as C2, verify-resolutions on C2); two rounds on one commit
  append two records to its note. The coverage algebra needs every round — a blocking finding in
  round 1 is discharged only by a resolution fact in round 2 — so "latest wins" is not an option,
  and the immutability norm already says so. `.critic-findings.json` remains the disposable view
  of the newest fact.
- **Transport.** `/prawduct:pr create|update` pushes `refs/notes/prawduct` with the branch
  (`git push origin refs/notes/prawduct`, after `git fetch origin refs/notes/prawduct` and
  `git notes merge -s union`). `onboard`/`doctor` set `remote.origin.fetch` to include the notes
  ref and `notes.rewriteRef=refs/notes/prawduct` (so local amend/rebase carry notes). Session
  start ingests notes not yet in the store — idempotent, bounded by the branch's commits since
  merge-base (NF1; the archive is not walked).
- **Tree-keyed, so squash-tolerant.** Coverage composes by `base_tree`/`head_tree` inside the
  fact, exactly as today; the commit the note hangs on is a locator. A squash or rebase-merge
  leaves the notes ref intact and only makes the reviewed commits unreachable from the base; the
  branch-time gates (Stop, `check-cumulative-critic`, the PR gate) ran before that. What degrades
  is only § 5's history-derived lifecycle, which falls back to the PR (`gh pr list --state merged
  --json headRefName,mergeCommit`). Under squash or rebase-merge a branch is single-use, as the
  digest already says.
- **Optional mirror.** `critic-consolidate --github-status` posts a `prawduct/critic` commit status
  for the fact (success when zero blocking, failure otherwise) so branch protection can require a
  Critic pass. Write-only; never read on a hot path (NF1). Off by default.

### 5. Lifecycle, observed

`plan status` reports `in-progress | merged-unreleased | released | superseded` from: the
integration branch exists and is unmerged into `base`; `git merge-base --is-ancestor <tip> <base>`
with no containing release tag; a tag contains it; the archive stamp. Nothing is stored (LC1).
The release cut archives every `merged-unreleased` plan whose fragment it ships — the existing
mechanism, now with `is_finished` as its precondition (#634). A `merged-unreleased` plan is
present on the base branch, claims a branch that is gone, and so is `unbound` everywhere: LC2
holds with no step at merge.

### 6. Backlog links

`closed-by` accepts `scope:<slug>`, a PR URL/number, or a release tag, validated by the adapter
against known scopes (live and archived plans plus fragments) — BL2. `pick` and the briefing
raise the BL3 advisory when an item's `working-branch` is bound to a unit whose fragment does not
`close` it (GV12: advisory only). No status inference anywhere (GV10).

### 7. Delegation

- `delegation.md` and `building.md` § Delegating: one sentence replaces "tell it not to write
  `.prawduct/`" — *a scratch worktree is unbound; it builds, you govern.* The "delegate that
  governs" tell drops "ticked a Status box"; chunk-close step 5 ("Update build plan Status") is
  deleted.
- The ephemeral guard admits `test-evidence record` **into the shared store only** from a scratch
  tree: the `test-run` fact is appended with `narrowed: true` and the delegate's ceiling, and the
  per-worktree JSON is not written (that half is what strands). The coordinator's `test-status`
  lists delegate runs by tree so "the unattributable green" becomes attributable. Nothing about
  what a delegate proves, or who integrates, changes.

### 8. What is deleted

Counted so NF3 is measured at the end, not asserted: `buildplan_refs.resolve_branch_plan` and
`infer_scope_from_branch`; `core.resolve_build_plan_path`'s pointer and default routes (after the
window); `ledger._scope_from_plan`; `gates._has_build_plan_in_state`; the unticked count in
`_has_active_build_plan_file`; the two private checkbox scans (`pr_payload._section_build_plan`,
`buildplan_refs:1281`); `has_unfinished_chunk`, `build_plan_is_complete`, `incompleteness_reason`
(folded into `is_finished`); the template's `## Status` block and its three "chunk marked `[x]`"
Done-when lines; the digest's tick paragraph; the tick-timing prose in `planning.md`,
`building.md`, the PR skill and protocol (13 files carry it today); the PR skill's pointer
bookkeeping; the precedence restatements in three skills. The digest and template are measured
before and after (token budget tests already pin them).

### 9. Tests that pin it (NF4)

Each shipped misattribution shape becomes a red-first test against `resolve()` and
`chunk_states()`: the #1049 ledger event (finished plan at the default path, unrelated branch →
`unbound`); #1007 shape (a) (lone plan declaring no branch → `legacy-*` with the advisory inside
the window, `unbound` outside it); #208 (mode inference on an unrelated plan → `unbound`, mode
`none`); #541 (a third reader of chunk progress → the `TestOneCurrentChunkImplementation` pin
extends to `plan_status` as the only walker); plus: two claimants → `broken`; scratch worktree on
a bound branch's fork → `unbound`; a working branch → `bound, role=working`; a review fact naming
`chunks: [01, 03]` completes both and leaves 02 `open`; a short plan's boundary review completes
every chunk; a `dropped:` chunk finishes a plan and an undeclared unbuilt one does not; a fragment
with a misspelled scope is refused at write; notes round-trip (append → fresh clone → ingest →
identical verdict); squash of a reviewed branch leaves `evidence status` able to list its facts.

## Waves

| Wave | Delivers | Closes | Plan |
|---|---|---|---|
| 1 — binding | § 1, § 2, § 6's `closed-by` validation, the Wave-1 half of § 7 (prose), legacy window, tests for the four shapes | #1007(a); half of #1050 | `build-plan-work-unit-binding.md` on `feature/1050-work-unit-binding` |
| 2 — status | § 3, the rest of § 7, § 8's tick deletions, MG2 import | the other half of #1050 | #1051, drawn when Wave 1 merges |
| 3 — transport | § 4, § 5 | the cross-clone gap this design surfaced | #1052, drawn when Wave 2 merges |

Each wave is a plan, not a program (`planning.md` "Plan Shape"). Waves 2 and 3 are filed as
#1051 and #1052, children of #1050, so the handoff cannot lose them.

## Open questions

- **Q1** Whether `.critic-findings.json` survives Wave 3 or `plan status`/`evidence list` replace
  it. Not load-bearing; decide at Wave 3.
- **Q2** The legacy window's length is stated as a measurement condition, not a date. If the
  owner prefers a date, name it in the requirements' MG3.
- **Q3** Whether a plan-less small fix (fragment-only unit) should also be able to bind a branch
  (`fragment` frontmatter `branch:`), or whether unbound-with-a-fragment is sufficient. Default:
  sufficient; the PR gate is coverage, not binding.
