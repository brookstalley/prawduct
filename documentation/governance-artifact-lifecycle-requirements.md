# Governance Artifact Lifecycle — Requirements

`status: draft v0.4 — 2026-08-08 · source: owner-initiated simplification review (this session) · stage: requirements · tracked: brookstalley/prawduct#629 · related: #558 · supersedes: .prawduct/artifacts/change-log-ledger-design.md (GO'd 2026-07-31, never scheduled — see "Out of scope")`

> **Tracking.** Filed as **#629** (`governance: shipped build plans and derived views have no
> end-of-life`, `stage: research`). **#558** (`views: views_enabled is a vestigial flag gating two
> checkbox meanings`) is `related`, not duplicate — it deliberately scoped *out* "whether derived views
> are the right model, only whether the flag still earns its branch," which is exactly this doc's
> question, so #558 is the item that left this unowned. #558 also pre-inventories the retirement blast
> radius (4 `is_views_enabled` read sites, ~10 doc surfaces carrying the conditional caveat) — reconcile
> against it rather than re-deriving. Adjacent and deliberately not merged: #252, #539, #587, #334.

> **v0.2 (same session, owner-requested simplification pass).** Added CL6/CL7 (six validators have
> `regen-views` as their *only* caller — two guard surviving fields and must be rehomed, consolidated
> into one), BP8/BP9 (two defects v0.1 would have introduced: archived release plans becoming
> unfindable, and an unbounded archive walked twice per session), a canonicality rule on BP3, a "What
> survives the deletion" subsection correcting the naïve "views.py minus the parser" reading, and an
> explicit observability ledger. Net effect: **fewer moving parts than v0.1** — six checks become one
> — while three observables v0.1 would have silently dropped are now required.
>
> **v0.3 (same session).** Owner confirmed the checkbox decision and the DV7 tripwire. DV3 now records
> *why* git cannot carry chunk progress (the `gates.py:808` incident) rather than asserting the choice.
> **BP6 broadened from one deletion site to five** — the janitor and the session-briefing nudge both
> delete plans, and the methodology plus a Critic check both *teach* the premise; naming only the PR
> flow would have left the behaviour in force. **BP10 added**: abandoned/superseded plans archive too,
> or they accumulate in live `artifacts/` forever reading as active.
>
> **v0.4 (same session, owner direction).** Backfilling existing shipped plans into the archive is now
> **required** for this repo and for consumers (**FL6**), not deferred to "from now on" — and
> **checkbox state is explicitly not a precondition and is not corrected on the way in**, because
> nothing reads an archived plan's boxes. That removes the only step v0.3 could not automate, so the
> backfill is fully mechanical; FL3's "report, never write" narrows to plans that stay live. **FL7**
> records that archival is normal operations, so the live directory never re-accumulates.

Evidence below was measured this session against the framework tree at `ede8801` and against all
21 local checkouts under `~/source` carrying `.prawduct/project-state.yaml`. **Re-derive rather than
cite** — every count here is a measurement of a growing corpus, and this repo has three recorded
instances of an unreproducible number propagating through governance records
(`change-log-ledger-design.md` §11.2).

## Problem

The framework assigned the **wrong lifecycle to two classes of governance document**, then built
machinery to cope with the consequences. One root cause, two mirror-image symptoms.

**Symptom A — documents that should be hand-written were made derived.** `views_enabled: true` makes
build-plan `## Status` checkboxes, `.prawduct/release-notes.md`, and `scope_rollups:` derived views of
`change-log.md` tag lines. Consequences, all observed:

1. **A tool exists whose job is to overwrite what people write.** `learnings.md` carries a rule
   specifically to suppress the correct instinct (L:175 — *"Never hand-check a build plan's `## Status`
   boxes… Hand-setting them survives until `regen-views` silently reverts them"*). It exists because it
   kept recurring.
2. **A second reading of chunk progress had to be built to route around the first.** Because the boxes
   only flip at release, they are wrong mid-branch, so `buildplan_refs._git_aware_progress` derives
   progress from git instead. The same defect then reached **three consumers independently** — CRT-7B4M
   (mode inference), BLD-7K3Q (`verify-chunk-refs`), SCN-4H9T (session handoff) — each fixed locally
   before anyone generalised it (`tests/test_handoff_parser_correctness.py`, section *"Defect 4 —
   `views_enabled`, at EVERY consumer"*). `cross-cutting-concerns.md` then grew a **READ-side** rule
   telling all future readers not to trust the boxes.
3. **The release step is knowingly broken and deliberately unfixed.** `release-process.md` step 3's
   selection rule is wrong three ways at once — positional, scope-narrowed, and it tags withheld work as
   shipped under a pruned release. That is REL-7D4X, REL-8P6M(e), and PR-reviewer finding W-1: *the same
   defect in the same sweep, found three separate times.*
4. **A norm collision exists only because this command exists.** The `regen-views-is-advice` ruling
   (2026-08-01) reconciles `architecture.md`'s *authority fails closed* against `data-model.md`'s
   *derived views are never authoritative*, with precedence recorded on both norms.
5. **14 of 220 learnings encode nothing but this format's rules** — `chunks=` zero-padding, `scope:`
   must be a slug not a version, statusless-on-feature-branch, flip statusless at release, `scope: null`
   inherits another scope's flips, and so on.
6. **Nothing the views produce is read to reach a decision.** `scope_rollups:` has zero consumers
   repo-wide outside the module that writes it. The checkboxes are explicitly untrusted (above).
   `release-notes.md` is not what ships — GitHub Releases are cut from hand-written
   `plugin/CHANGELOG.md`. Cost: ~4,800 lines (`views.py` + `test_views.py`), four validators whose only
   job is catching malformed hand-written tags, and ~250 lines of dual-reading machinery in
   `buildplan_refs.py`.

**Symptom B — documents that should be durable were made ephemeral.** `/prawduct:pr`'s merge flow
**deletes** a completed build plan (step 7 / create-flow step 1d). Consequences, all observed and
already recorded in the backlog:

1. **Requirements get stranded and must be rescued before deletion.**
   `backlog-service-requirements.md` exists partly to absorb *"the upstream bug-reporting requirements
   formerly stranded in the shipped `build-plan-upstream-bug-reporting.md` (an ephemeral build plan)."*
2. **References into plans dangle by design, and an authoring discipline exists to cope.** The
   **ephemeral-ref firewall** (`cross-cutting-concerns.md:44`, born 2026-07-14) is a Critic WARNING plus
   a documented rule, whose stated rationale is *"a build id dangles when the plan is deleted."*
3. **The registry documenting that firewall was itself violating it** — a `cross-cutting-concerns.md`
   row rode its meaning on `build-plan-session-boundary-events.md` Chunk 02, a few rows below the row
   forbidding exactly that.
4. **Hazards die with their carrier.** LRN-9K2P (open, `stage: ready`) would orphan ~28 learnings
   pointers; the hazard *"lived only in the collapse map and the learnings-firing build plan, both
   deletable working artifacts, neither of which whoever picks up LRN-9K2P has any reason to open."* A
   note had to be hand-copied onto the item so the constraint would survive.
5. **Shipped source carried refs that deletion would void** — nine dangling build-plan chunk refs had
   to be stripped from `lib/backlog/` before a PR *"because they resolve to nothing once
   `/prawduct:pr` deletes the build plan."*
6. **Findings with no durable home get filed against the framework instead** — *"filed from the Chunk 01
   Critic review, whose only other home would be a build plan deleted at release."*

**Why it diverged across the fleet.** Three declarations of the `views_enabled` default disagree, and
nothing compares them: `is_views_enabled` returns False on a missing key (*"opt-in by design"*); the
template ships `views_enabled: true` under a header reading *"enabled by default"*; and
`cmd_regen_views`' docstring says *"sync auto-enables for existing repos"* — naming the file-sync
engine **deleted at M4 (v2.0.3)**, which used to reconcile the other two. It has been gone for three
minor versions and the docstring still describes it as live. `views_enabled` is the **only** flag whose
template value contradicts the code default; `coverage_required` and
`operator_verification_required` both ship `false`, matching. `/prawduct:doctor` does not look at the
flag at all, so divergence was undetectable by construction.

The result is not a decision split. **Not one repo has `views_enabled: false`** — every "off" repo is
key-absent. 9 repos have `true`; 12 have the key absent. Of the 9, only **4 ever ran `regen-views`**
(the ones with a `release-notes.md`). So 17 of 21 repos have never produced these views, for months,
and nothing broke — an unplanned control group that already ran the experiment.

## Success

- Exactly **one** reading of "which chunk is done" exists, and no tool rewrites it.
- **No command exists whose purpose is to overwrite hand-authored governance state.**
- A completed build plan is readable a year later, and a reference into it resolves.
- All onboarded repos reach the same state **without the owner hand-editing any of them**, and a check
  keeps them there.
- None of the 14 format-rule learnings remains necessary.
- An agent that ticks a checkbox when it finishes a chunk is **right**, not fighting the framework.

## Actors

- **Project agents** — Claude sessions building against a plan: tick boxes, write change-log entries,
  archive plans at completion.
- **Owner** — decides releases; must not have to hand-migrate 9 repos.
- **Gates** — `check-releasability`, `check-change-log-entry`, the Stop-hook Critic/reflection gates.
- **Future readers** — any session reading an archived plan, or a durable record referencing one.

## Requirements

MUST unless marked SHOULD.

### DV — Derived views retired

- **DV1** The `views_enabled` flag is removed from code, template, and documentation. No repo-level
  switch selects between derived and hand-maintained governance state — the two-path choice is the
  defect, not the configuration of it.
- **DV2** `regen-views` and the deprecated `stamp-merged` are removed. Standing constraint: **no
  command may exist whose purpose is to overwrite hand-authored governance state.**
- **DV3** Build-plan `## Status` checkboxes are hand-maintained and authoritative. Exactly one reading
  of chunk progress exists; the git-derived *precedence composition* (`_git_aware_progress`) and its
  `degraded-chunk-reading` notice are removed.
  **Why the checkbox and not git — recorded because it has already been decided the hard way once.**
  Four decisions read box state: the Stop hook's blocking Critic + reflection gates, review-mode
  inference, the session briefing's `Resume: Chunk NN` line, and chunk-ref expiry (#224a). Git
  **cannot** carry it: `gates.py:808` records that routing this through the git signal made the
  blocking reflection and Critic gates **switch themselves off** the moment the final chunk was
  committed, across the entire complete-but-unmerged window — because *a chunk's last commit lands
  before its Critic pass and its reflection.* The checkbox marks the end of **governance**; a commit
  marks the end of **coding**, and they differ by exactly the two events the gates exist to enforce.
  Fleet evidence that hand-ticking works: in the two heavily-used repos where checkboxes have been
  authoritative all along, agents keep them ~91% ticked with no tool involved (discodon 269/26 across
  102 plans; discodon-brooks2 132/10 across 68 — re-derive, do not cite). Archival (BP2/BP3) raises
  their value further: an archived plan is read outside its git context, where a ticked Status block
  answers "what shipped" on open and a git-derived reading cannot.
- **DV7** A **reporting-only** staleness tripwire compares the ticked set against the chunk ids the
  session's commits mention and surfaces a disagreement. It is **never authoritative and never
  auto-fixes** — same posture as FL3. Rationale: with one signal, *forgetting to tick* becomes the only
  failure mode, and this is the one thing the git reading is genuinely good for. `_committed_chunk_ids`
  is therefore **repurposed, not deleted** — from deriving progress to checking it. *Stated as a cost:
  this is a new surface, and it makes the deletion smaller than "remove the dual reading" implies.*
- **DV4** `scope_rollups:` is removed from `project-state.yaml` and from the template.
- **DV5** `release-notes.md` is no longer generated. Existing files are **preserved as frozen archives,
  not deleted** (see FL2).
- **DV6** The consumer-facing changelog remains `plugin/CHANGELOG.md` — hand-written, one headline per
  release, the source of GitHub Release notes and the version-delta banner. *Descriptive of today;
  recorded so it is not re-derived or re-automated.*

### CL — Change log

- **CL1** `.prawduct/change-log.md` is prose. Its only machine-read fields are `scope=` and `release=`.
- **CL2** `chunks=` and `status=` are removed from the tag schema and from every document that teaches
  it. Existing tags in committed change logs are **left in place and read by nothing** — rewriting 21
  repos' history is churn with no consumer.
- **CL3** `check-releasability` continues to derive release-pending scopes from `scope=` plus the
  absence of `release=`. *Unchanged; recorded because it is the only surviving gate over change-log
  content and the sole reason any tag survives.*
- **CL4** `check-change-log-entry` continues to gate on a branch adding an entry heading. It reads diff
  shape, never tags, and is unaffected.
- **CL5** (SHOULD) At release, the only change-log edit is adding `release=vX.Y.Z` to the entries that
  shipped. The three-tag sweep and its selection rule are removed.
- **CL6** Change-log tag validation is **one** validator over the two surviving keys — value format,
  duplicate key, duplicate tag line — invoked by `check-releasability`, the gate that depends on them.
  *This is a consolidation that must not become a deletion.* Six checks exist today
  (`validate_status_values`, `validate_release_values`, `validate_tag_line_multiplicity`,
  `validate_tag_conflicts`, `validate_chunk_roster`, `diagnose_scope_plan_coverage`) and **`regen-views`
  is the only caller of all six**, so removing it silently removes them all. Four die correctly with
  the fields they guard. `validate_release_values` guards a **surviving gated** field and has a
  recorded incident: `release=unreleased` on six entries removed their whole scope from the
  release-pending set and **hid an entire branch from the v3.2.8 release**. Losing that guard while
  keeping the field it protects would be a net regression, not a simplification.
- **CL7** The "unreleased scope with no build-plan file" diagnostic survives, rehomed to
  `check-releasability` and searching live **and** archived plans. `check-releasability` globs only the
  *release plan* today, so it does not cover this. Its meaning also improves: post-change, a scope
  shipping with no plan is **work with no documented parent** (Principle 6), not merely a view that
  cannot regenerate.

### What survives the deletion

Recorded because the naïve reading — "`views.py` minus the parser" — is wrong, and the plan must not
be written against it. Three groups survive:

1. **Change-log tag reading** — `parse_change_log`, `ChangeLogEntry`, `parse_tag_line`, plus CL6's
   merged validator. Consumer: `check-releasability`.
2. **Scope→plan resolution** — `build_scope_to_plan_map`, `iter_scoped_plan_candidates`, and the
   frontmatter/artifact-kind parsers they use. `buildplan_refs._scope_plan_map` delegates to these, and
   **three hot governance paths ask it: review dispatch, every session END (the Stop hook), and every
   session START (the briefing).** This group is also the archive-aware scanner BP5 and BP8 depend on.
3. `_commits_ahead_of_base` in `buildplan_refs` — `critic_mode` uses it for review-mode inference,
   independent of any view.

The survivors belong in **two clearly-named modules** — change-log tags, and a plan index — not one.
Today both live in a module named `views` that does neither, which is part of why the dual-reading
defect reached three consumers before anyone generalised it.

### BP — Build-plan lifecycle

- **BP1** A completed build plan is **never deleted**. This retires the "build plans are ephemeral"
  premise wherever it is stated or relied upon.
- **BP2** Completion is recorded **in the plan's own frontmatter**, and the plan is **moved to
  `.prawduct/artifacts/archive/`**. Both, not either: the frontmatter makes the document
  self-describing when read directly; the move keeps the live artifacts directory unambiguous.
- **BP3** The completion frontmatter states, at minimum: completed status, the completion date, the
  release or version that carried the work when the product versions, and **that the document is no
  longer maintained and describes what was built rather than what will be**.
  **Canonicality, because BP3 and CL1 both record the shipping version:** the change-log `release=` tag
  is canonical — it is what `check-releasability` reads. The frontmatter's copy is a **permitted stable
  copy**, and the distinction is the rule BP7 preserves: a shipped version number is immutable, so a
  copy of it cannot dangle, whereas a count or a chunk id can. Two copies of an immutable fact is
  self-containment; two copies of a mutable one is the drift the firewall exists to prevent.
- **BP4** Active and archived build plans are **committed to git**. *Largely already true —
  `gate-soundness` ch.3 made plans tracked, and `core.RETIRED_GITIGNORE_ENTRIES` actively strips
  `.prawduct/artifacts/build-plan.md` from a product's `.gitignore` and tells the owner to `git add`.
  What this requirement adds: the archive directory must never be gitignored, and the retirement must
  stay recorded so the v1.3.x gitignore behaviour is not reintroduced.*
- **BP5** Every reader that scans `artifacts/` treats `archive/` as **history, not live assertion**,
  uniformly. *Partly built: `record_lint._ARCHIVE_MARKERS` and the shadowing guard in `views.py`. When
  `views.py` goes, its copy of the rule must not go with it.*
- **BP6** **Every** surface that deletes a plan, or teaches that plans are deleted, is changed — not
  just the PR flow. The deletion premise lives in **five** places, and a requirement naming one would
  leave the behaviour in force:
  1. `plugin/skills/pr/SKILL.md:70` — the merge flow deletes the plan file. Archives instead. Clearing
     `active_build_plan` is unchanged, and the gitflow-vs-trunk branch (PR-7Q3M) still decides *when*,
     not *whether*.
  2. `plugin/skills/janitor/SKILL.md:161` — *"Stale build plans … Clean up: delete plan file."* Becomes
     an archival step.
  3. `plugin/lib/briefing.py:253,272` — the session briefing **actively nudges** *"if work is done,
     delete the plan."* The framework tells the operator to do this every session; the nudge becomes
     "archive the plan."
  4. `plugin/methodology/building.md:85` — teaches that a chunk/plan reference dangles because plans
     *"are deleted when work ships."* The premise is retired (see BP7).
  5. `plugin/skills/critic/review-protocol.md:88` — the Critic WARNING resting on the same premise.
     Re-derived per BP7, as a norm decision.
- **BP10** **Two terminal states archive, not one:** *completed* (every chunk shipped) and
  *superseded/abandoned* (work stopped, descoped, or absorbed elsewhere). The frontmatter distinguishes
  them, and for the second it names what superseded the plan or why it stopped. *Without this,
  "archive when complete" leaves partially-done dead plans in live `artifacts/` forever, reading as
  active — which is the confusion this requirement set exists to remove.* It is already the common
  case, not a corner: ten of this repo's build plans carry unticked boxes, and they are **not** all in
  flight — `build-plan-v3.2.0-golive.md` sits at 6 ticked / 5 unticked with v3.2.0 seven releases
  behind us. Such a plan can never satisfy "all boxes ticked" and so would never archive. These plans
  also cost real time: the scope→plan scan walks them at session start **and** end (BP9).
- **BP7** (SHOULD) A reference into an archived plan resolves. The **ephemeral-ref firewall's rationale
  is re-derived, not silently inherited**: what remains prohibited is riding durable meaning on an
  identifier that *changes* (a count, a chunk number that renumbers), not on a document that persists.
  Narrowing or retiring it is a norm decision (GD4), not a doc edit.
- **BP8** **Archival never changes whether a document can be found by name.** A reader resolving a
  *named* artifact searches live, then archive; a live file wins over an archived namesake. *This
  closes a breakage this requirement set would otherwise introduce:* `release_readiness._find_release_plan`
  globs `.prawduct/artifacts/release-plan-<version>*.md` **non-recursively**, so archiving release plans
  would make `check-releasability` fail closed with `no-release-plan` on any earlier version. The
  live-wins half already exists as a per-file guard in `views.py:766`; BP8 is its general form, and it
  must outlive the module that currently carries it.
- **BP9** The archive is **pruned at directory level** by any scan on a hot path, not walked and
  filtered per file. *This closes a cost this requirement set would otherwise introduce:* keeping plans
  forever means `artifacts/` grows without bound, and the scope→plan scan runs at **session start and
  session end**. Today's implementation `rglob`s everything and discards `archive/` entries afterwards,
  so every archived plan would be parsed twice per session to be thrown away. Growth in the archive
  must cost one skipped directory, not N frontmatter parses.

### FL — Fleet convergence

- **FL1** After the release that carries this, every onboarded repo reaches the target state **without
  the owner hand-editing any repo.**
- **FL2** `/prawduct:doctor` performs the **mechanical** repair, idempotently, a no-op on repos already
  in the target state: remove the `views_enabled:` key, remove the `scope_rollups:` block and its
  comments, freeze `release-notes.md` as an archive, strip `<!-- views_enabled: … -->` comments from
  build plans.
- **FL3** Doctor **reports and never auto-fixes** the checkbox reconciliation **on plans that stay
  live**. A derived Status block is stale on an in-flight chunk, only a session with the work in context
  can say which chunk is done, and the Stop hook's gates read that state — **a model must not write it**
  (`data-model.md`: no model in a fact's write path). *Narrowed by FL6: this applies to live plans only,
  because an archived plan's boxes are not read by anything.*
- **FL4** The behaviour change is **attributed** on the release that carries it — a version-delta
  banner headline naming the retired flag and command. Per the existing rule, a plugin update may change
  behaviour immediately provided the change is announced and traceable to the version.
- **FL5** Already-deleted plans are **not** resurrected from git history. *(Reduced from v0.3, which also
  said archival applies only from this release forward — FL6 replaces that half.)*
- **FL6** **Existing shipped plans are backfilled into the archive**, for this repo and for consumers —
  not left for "from now on." Accumulated live plans reading as active is the confusion this whole set
  exists to remove, and prawduct alone carries 114 artifacts.
  **Checkbox state is never corrected on the way in.** An archived plan may be left with unticked
  boxes; nothing reads them once it is out of the live directory, so "make it look complete first"
  would be ceremony with no consumer.
  **AMENDED 2026-08-11 (v3.3.1, #634) — it IS a precondition of the mechanical sweep, and remains
  none of an explicit `archive-plan`.** This paragraph read "explicitly NOT a precondition for
  archiving" without qualification, which selection by change-log `release=` made unsafe: that tag
  answers *did the scope ship*, never *did the plan finish*, and the two come apart whenever a scope
  ships partially — a consumer repo archived a plan as `completed` with two chunks unbuilt and still
  live. The claim that removing the precondition "removes the judgment" was the load-bearing error:
  it removed only *whose* judgment, leaving the tool to decide, wrongly, every release. The sweep now
  declines such a plan and names the chunk. Judgment is still out of the write path — the predicate
  is a deterministic count, and declining hands the call to a human rather than taking it. The
  binding statement is the ruling in `data-model.md` § Direction; this requirement records it.
  What remains to decide is only **which plans are shipped**, and one mechanical test is available
  today: a plan whose `scope=` carries a `release=` tag in the change log shipped. That reuses the field
  CL3 keeps, needs no judgment, and is a fitting last use of the tag data before it goes inert. Where a
  product has no release tags, doctor **proposes** the set and the operator confirms — proposing a move
  is not writing governance state, so FL3's prohibition does not reach it.
- **FL7** Archiving is **normal operations, not a migration event.** FL6's backfill is one-time; BP6's
  five surfaces make archival the routine end-of-life step thereafter, so the live directory does not
  re-accumulate and no second backfill is ever needed.

### GD — Guard against recurrence

- **GD1** A test asserts that **every opt-in flag's template value equals its code default.** This is
  the actual root cause — three declarations with nothing comparing them — and without it the same drift
  recurs on the next flag.
- **GD2** A doctor check fails if `views_enabled` reappears in a repo's `project-state.yaml`.
- **GD3** Retired flag and command names are recorded where an agent looking for them finds the
  **retirement**, not silence. A stale docstring describing a deleted mechanism (`cmd_regen_views` on
  file-sync auto-enable) is the failure mode being designed against.
- **GD4** Retiring the `regen-views-is-advice` ruling is a **norm lifecycle event**, recorded as a
  decision with its precedence annotations removed from both `architecture.md` and `data-model.md`.
  Norms bind; deleting one silently because its subject went away is not a doc-sync
  (`/prawduct:methodology norms`).

## Observability: what improves, and what must be carried across

Simplification here removes machinery, not visibility. Stated explicitly because "delete the views" is
the kind of change that loses an observable by accident.

**Improves.** *"Which chunks shipped in release X"* moves from a `chunks=` tag — a machine field
detached from the work, whose zero-padding rules cost a learning apiece — to the **archived plan's own
ticked Status block plus its completion frontmatter**: co-located with the narrative that explains the
work, durable, and self-describing when opened directly. *"What did this branch change and why"* is
unaffected: it was always the change-log prose, which this set does not touch.

**Must be carried across, not dropped** (each has a requirement): the malformed-`release=` guard whose
absence hid a branch from a release (CL6) · the unreleased-scope-with-no-plan diagnostic, which becomes
a Principle 6 signal (CL7) · findability of a named artifact after archival (BP8) · the live-wins-over-
archived precedence (BP5, BP8).

**Deliberately not preserved.** `validate_status_values` and `validate_chunk_roster` guard fields that
cease to exist. `validate_tag_line_multiplicity` guards a case with zero instances in the corpus
(`change-log-ledger-design.md` §11.5); its coverage folds into CL6's single validator rather than
surviving as its own check.

## Out of scope

- **The change-log ledger design** (`.prawduct/artifacts/change-log-ledger-design.md` — typed facts in
  `.prawduct/changes/` plus release records). **Explicitly superseded, and this is recorded so nobody
  schedules it later from reading only its §11.7 GO.** Its engineering is sound and its diagnosis is
  right, but it answers *"how do we store these views' inputs properly"* when the prior question is
  whether the views earn storage at all. The design flags this itself as a MED-impact open assumption
  — *"whether [the 224 Status checkboxes] earn their machinery is a separate question."* Resolved
  against the evidence above, that assumption deletes the plan rather than scheduling it, and avoids a
  five-chunk migration, a major version bump, and a second concurrent fleet rollout.
- **Backlog → GitHub Issues migration.** Untouched; shares no code and no files. This also resolves the
  ledger design's §11.6 scheduling gate ("which fleet migration is proven end-to-end first") by
  removing one of the two contenders.
- **Rewriting historical change-log entries, tags, or `plugin/CHANGELOG.md` format.**
- **Whether `.prawduct/change-log.md` should exist at all.** It is prose with two gating tags after this
  work; further consolidation with `plugin/CHANGELOG.md` is a separate question.

## Open assumptions

- ~~`[ASSUMPTION: build-plan ## Status checkboxes are KEPT and hand-ticked …]`~~ — **RESOLVED, owner
  confirmed.** Kept and hand-ticked, plus DV7's reporting-only tripwire. The evidence that settled it is
  recorded in DV3 rather than here, because it is a reason the design rests on, not an open question.
- `[ASSUMPTION: the archive is a flat .prawduct/artifacts/archive/, not per-year subdirectories | LOW |
  user can correct — per-year matters past a few hundred plans]`
- `[ASSUMPTION: release-notes.md is frozen as release-notes-archive.md rather than deleted | LOW |
  user can correct → delete it; it is generated and unread, and git holds it]`
- `[ASSUMPTION: this ships as a minor bump — removing a flag whose views nothing reads is a default
  change, not a breaking API change for products | MED | user can override → major bump]`
- `[ASSUMPTION: archived plans stay under .prawduct/artifacts/ rather than moving to documentation/ |
  LOW | user can correct]`

## Governing norms — reconciliation

Per `methodology/planning.md`, a departure from a norm is never silent.

| Norm | Disposition |
|---|---|
| `data-model.md`: derived views are disposable and never authoritative; **no gate reads a view** | **Conforms, and strengthens it** — this removes the last subsystem where a view existed at all. FL3 is the same norm applied to the migration's own write path. |
| `data-model.md`: no model in a fact's write path | **Conforms** — checkboxes become hand-authored *state*, not a derived view of a fact, so there is no fact whose write path a model enters. FL3 keeps doctor out of it. |
| `architecture.md`: authority fails closed, advice fails soft | **Subject removed.** The `regen-views-is-advice` ruling exists to reconcile this with the derived-views norm for one command. That command goes; the ruling is retired as a recorded decision (GD4), not deleted quietly. |
| `nonfunctional-requirements.md`: state-file growth is advisory, never a hard block | **Conforms** — the archive directory gets advisory treatment, matching `TREE_COUNT_ADVISORY`. |
| `project-preferences.md`: merge-commit strategy, no attribution trailers | **Unaffected.** |
| Ephemeral-ref firewall (`cross-cutting-concerns.md:44`) | **Narrowed by BP7, as a recorded norm decision.** Its stated rationale ("a build id dangles when the plan is deleted") is largely removed by BP1; what survives is the count/renumbering half. Not a doc-sync. |

## Requirements confidence: **High**

The problem is measured against code and 21 real repos rather than inferred; every consumer of every
affected output was traced to its call sites; both symptoms have independent recorded evidence trails
predating this session. The residual uncertainty is the single MED assumption above (keep or drop the
checkboxes), which is a decision rather than an unknown.
