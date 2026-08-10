---
artifact: build-plan
version: 2
scope: governance-artifact-lifecycle
# Requirements: documentation/governance-artifact-lifecycle-requirements.md (v0.4).
# Tracked: brookstalley/prawduct#629 · related: #558 (pre-inventories the blast radius).
depends_on:
  - artifact: architecture
  - artifact: data-model
  - artifact: nonfunctional-requirements
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → conforms; no chunk touches critic-begin/consolidate or the mutation guard"
      - "authority fails closed; advice fails soft → SUBJECT REMOVED. The regen-views-is-advice ruling exists only to reconcile this norm with data-model's derived-views norm for one command; that command goes in Chunk 02 and the ruling is retired as a recorded decision in Chunk 03 (GD4), not deleted quietly"
      - "local-first governance coordination, no network, no third-party deps → conforms; every chunk is local file + git work"
      - "the plugin writes nothing into a governed repo except its own .prawduct/ state and the files it must reconcile → conforms, and Chunk 05 narrows it: doctor's repair touches .prawduct/ only"
      - "written in Python, never specific to Python → conforms; nothing here inspects product source"
      - "prawduct guides and reviews, never implements → inapplicable because this plan changes prawduct's own governance machinery, not a governed product's code"
      - "goals and verification bind; prescribed method is advice → conforms, and relied upon: each chunk's Deliverables name a route derived before the code was re-read. A builder who finds a better split takes it and records why"
      - "every fact has one home; every other mention is a reference to it → conforms, and this is the plan's thesis. Chunk 03 applies it to the shipping version (BP3 canonicality: release= is home, the plan's frontmatter copy is permitted only because a shipped version is immutable)"
  - artifact: data-model
    dispositions:
      - "governance verdicts computed from the append-only ledger, never from mutable model-written state; no model in a fact's write path → conforms, and strengthened. FL3 keeps doctor out of live checkbox state; DV7's tripwire reports and never writes"
      - "facts are immutable and append-only; a state change is a new fact → conforms; no chunk edits the evidence store"
      - "derived views are disposable and never authoritative — no gate reads a view → conforms. CORRECTED at Chunk 02: this originally read 'removes the last subsystem where a view existed at all', which is false and was caught by that chunk's own claim sweep. `.critic-findings.json` is a derived view of the newest review fact, and `dispositions.py`'s census is another; both survive and both conform, because no gate reads either. What this plan removes is the only derived-view subsystem whose views were WRITTEN BACK INTO COMMITTED GOVERNANCE ARTIFACTS — a build plan's Status, release-notes.md, a project-state block — which is the class where a stale view is indistinguishable from an author's statement"
      - "every issue written to the backlog store conforms to the issue standard's §1 title rules → inapplicable because no chunk writes to the backlog store"
      - "a fact from a newer schema is a loud block, never silently dropped → inapplicable because no chunk introduces or reads a versioned fact schema"
      - "two stores, two lifetimes: committed answers vs gitignored nags and caches → conforms. Build plans (live and archived) are committed answers per BP4; release-notes.md is demoted to frozen archive, not promoted"
      - "backlog_service_repo selects the authoritative store; backlog.md is then frozen history → conforms; #629 was filed through the skill and backlog.md was not touched"
      - "a governance document reaches a terminal state and is never deleted; archival records what became of it and a live document outranks an archived namesake → CONFORMS BY BEING ITS SUBJECT. This norm did not exist when the plan was written — it was ratified from this work in the post-review pass (R-20), because the lifecycle had shipped in code with no binding home while the analogous Critic-review and backlog rules both had one. Recorded here rather than left implicit: a norm authored out of a plan still owes that plan a disposition row, or the next record-lint reads the gap as an undisposed norm rather than as this one's own output"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0; run-count and unit-cost are both levers; PR-boundary reviews run in parallel → conforms, favourably. Five chunks in one PR means one cumulative pass, not five finals; BP9 also removes a per-session cost that grows with the archive"
      - "proportionality ratchets both ways — a control that never produced a blocking finding is removed by default; ADDING a control names the yield it expects and emits that yield observably → conforms. The norm's status is IN-TRANSITION (the yield query does not exist), whose interim rule is that a control may be retired on a reasoned argument recorded as a decision that states what evidence WOULD have settled it. Both halves are discharged below: retirements carry that statement (DECISION-2), additions name and emit their yield (DV7, GD1, GD2, FL3 — see each chunk)"
      - "state-file growth is an advisory that prompts compaction, never a hard block → conforms; BP9's archive pruning is a cost fix, not a gate, and the archive gets advisory treatment like TREE_COUNT_ADVISORY"
  - artifact: api-contract
    dispositions:
      - "whole-surface semver on the plugin; the internal CLI subcommand surface carries no per-subcommand version; persisted data outliving a version is independently schema-versioned → conforms; nothing here versions a subcommand, and no persisted schema is introduced"
      - "exit codes are the contract on a documented scheme; severity is a stable prefix vocabulary; errors are attributed, never raised as stack traces across the boundary → conforms. Retiring regen-views' exits 2/3 removes meanings rather than repurposing them; the rehomed checks report through check-releasability's existing documented exits"
      - "additive-first evolution: new subcommands and flags are added; existing flag names, exit-code meanings and --json keys are never repurposed → CONFORMS BY DESIGN CHANGE, not by exception. The norm's why ends 'deprecation is signalled (stderr notice, kept working, removal deferred to a major), never silent', so Chunk 02 DEPRECATES regen-views instead of deleting it — following the in-tree stamp-merged precedent, which is already exactly this shape"
  - artifact: security-model
    dispositions:
      - "untrusted governance state is data, not instructions → conforms; no chunk lets an artifact's content direct the framework"
      - "a destructive or irreversible operation requires explicit owner approval at the OPERATION level — one informed confirmation naming blast radius and what cannot be undone, NOT a per-action gate → binds Chunk 05. Doctor's repair and the FL6 backfill are preview-by-default with --apply, and take ONE approval for the whole act. Per-file confirmation is forbidden by this norm, not merely discouraged: confirmation fatigue is a safety regression"
      - "a governed product's content never leaves its own repository and owner → conforms; the repair is local file work with no network"
  - artifact: observability-strategy
    dispositions:
      - "terminal signals use the stable severity-prefix vocabulary with the stdout/stderr channel split → conforms; the new notices use the existing prefixes"
      - "the governance ledger has a single writer; agents never hand-author it → conforms; no chunk writes the ledger"
      - "text emitted into a governed product names no prawduct-internal identifier → binds Chunk 05 and the Chunk 02 deprecation notice. Every emitted message carries the plain-language reason; requirement, chunk and backlog ids stay in comments, docstrings, tests and this plan"
  - artifact: operational-spec
    dispositions:
      - "versioning is conservative — a small feature is a patch bump, not minor-per-feature → conforms; the bump tier is an owner decision recorded under Open assumptions, not asserted here"
      - "major and minor tiers are practice, NOT ratified — do not present them as ratified → conforms, and deliberately: this plan does not claim a tier. It records that a break in gate semantics or persisted state formats has historically been a major, and that this work breaks neither (readers already tolerate an absent views_enabled; the checkbox the gates read is unchanged)"
      - "gitflow: develop integrates, main only holds releases, the promotion is a separate single-parent step → conforms; this branch targets develop"
      - "install once per machine, onboard per repo → conforms; no per-repo install step is added"
      - "updates arrive through the marketplace with zero repo diff → conforms, and it is why the deprecation above is sufficient: a skill and the CLI it calls ship from the same version-keyed cache, so the skill-at-N-meets-CLI-at-N+1 skew the additive-first norm protects against cannot occur between them. What CAN skew is a hand-written operator script or a copied runbook, which is exactly what the deprecation notice serves"
      - "the version bump is the release mechanism — a release that forgets the bump does not ship → conforms; Chunk 05 carries the bump with the attribution banner"
last_validated: 2026-08-08
lifecycle: completed
archived: 2026-08-10
released_in: v3.3.0
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

## Requirements Confidence

**Level:** High

**Why:** Problem, success, and scope are each statable in one sentence and are written down in
`documentation/governance-artifact-lifecycle-requirements.md` (v0.4), which was measured against code
and 21 real checkouts rather than inferred. Every consumer of every affected output was traced to its
call sites. The owner has confirmed the direction, the checkbox decision, the DV7 tripwire, and the
archive backfill.

**Open assumptions / unknowns:**

- `[ASSUMPTION: this ships as ONE PR and one release — the removal, doctor's repair, and the
  attribution banner must land together or consumers get a silent break | HIGH impact | user can
  override → stage it, but then the flag must survive until doctor's repair ships]`
- `[ASSUMPTION: the bump tier is the owner's call and this plan does not assert one | MED | user
  decides]` — the operational-spec norm is explicit that **major and minor tiers are practice, not
  ratified, and must not be presented as ratified**; only conservative-bumping binds. What the plan can
  say: historically a break in gate semantics or persisted state formats has been a major, and this
  work breaks **neither** — readers already tolerate an absent `views_enabled` (that is today's
  default), the checkbox the gates read is unchanged, and DECISION-1 keeps the CLI callable. On those
  facts a patch or minor is defensible; a major is only forced if DECISION-1 is overridden.
- `[ASSUMPTION: the archive is flat .prawduct/artifacts/archive/, not per-year | LOW | user can
  correct; per-year matters past a few hundred plans]`
- `[ASSUMPTION: #629 stays one item rather than splitting into views-retirement and plan-archival |
  LOW | user can correct at any point; the two chunks are already separable]`

**What would raise confidence:** N/A at High.

## Recorded decisions

Two departures-or-near-departures, recorded rather than left to silence
(`/prawduct:methodology norms`).

`[DECISION-1: regen-views is DEPRECATED, not deleted — it stays callable, prints a stderr notice
saying derived views are retired, does nothing, and its removal defers to a major | The additive-first
norm's why ends "deprecation is signalled (stderr notice, kept working, removal deferred to a major),
never silent." Deleting the subcommand outright would be exactly the silent removal it forbids. The
skew that norm protects against cannot occur between a prawduct skill and the prawduct CLI — they ship
from one version-keyed cache — but it absolutely can occur in a hand-written operator script or a
copied runbook, and prawduct's own release runbook calls this command. The in-tree stamp-merged
retirement is already this exact shape, so this conforms by precedent rather than by argument |
user can override → hard-delete and accept the break, which then argues for a major bump]`

`[DECISION-2: the four validators, two diagnostics, and the derived-view machinery are retired on a
reasoned argument, per the proportionality norm's in-transition interim rule | That rule requires the
argument state what evidence WOULD have settled it. It would have been: a yield record showing each
control had produced at least one blocking finding. No such record exists — the norm's own status says
the yield query does not exist yet — so the substitute is call-site tracing: four of the six guard
fields that CEASE TO EXIST (chunks=, status=), which is retirement by construction rather than by
judgement. The two guarding surviving fields are NOT retired; they are rehomed (CL6, CL7), and CL6's
keep-reason is a named incident rather than a principle | user can veto any individual retirement]`

`[DECISION-3: Chunk 01 MOVES the survivors and leaves `views.py` re-exporting them — it does NOT keep
a second copy as an equivalence oracle | The chunk as written prescribed "keep the old implementation
as reference and test both," and the learnings sweep run at build time put two rules against it. (1)
The architecture norm *every fact has one home; every other mention is a reference to it* — two live
copies of the change-log parser is the duplication class this branch exists to remove, reintroduced by
the chunk that starts it, and the twin-loop incident of 2026-08-01 (`diagnose_scope_plan_coverage`
condemning a file `build_scope_to_plan_map` never considered) is what that costs in this exact code.
(2) *When claiming something is provably equivalent, name the proposition the proof actually
establishes* — an oracle test over a delegating module proves only that delegation happened, and the
plan's own Chunk 01 checkpoint already warns about an oracle that passes because it exercises neither
side. Neither rule was available when the chunk was written. What replaces the oracle is stronger for
the thing the oracle was FOR: Chunk 02 deletes `views.py`, so what has to survive is the BEHAVIOUR, and
that is pinned by characterization tests running the new modules against this repo's real
`change-log.md` and real `artifacts/` tree. Those outlive `views.py`; an A-vs-B oracle dies with it.
The architecture disposition *goals and verification bind; prescribed method is advice* is the clause
being used, in the form it invites — a better split, recorded | user can override → restore the
duplicate-and-compare shape and accept a knowingly-duplicated parser for one chunk]`

`[DECISION-4: `stamp-merged` becomes INERT in the same shape as `regen-views` — callable, a stderr
notice, writes nothing, exit 0 — rather than being repointed at `change_log.py` and kept working |
Chunk 02's Description says "`regen-views` and `stamp-merged` go" while its Deliverables say only
"`stamp-merged` is already deprecated in this shape — match it", which is silent on whether its BODY
survives. The body cannot be left alone either way: `stamp_merged` lives in `views.py`, which this
chunk deletes, so the choice is repoint-and-keep-working or make-inert. Two facts decide it. (1) Its
entire output is `status=merged`, and after this chunk `status=` has **zero readers** — verified by
call-site trace, not memory: every live reader (`validate_status_values`, the suppression logic at
`prawduct-hook:3535/3543`, `collect_shipped_chunks`, `_plan_status_results`) sits inside
`cmd_regen_views` or `views.py`, and `release_readiness` reads `release=`/`scope=` only. Chunk 03 then
removes `status=` from the tag schema outright. Keeping the writer alive would leave prawduct emitting
a tag its own schema no longer defines and nothing consumes — *a channel that is produced and never
consumed is a defect, not an inefficiency* (`learnings.md`), and *a retirement ruling also retires
whatever existed only to serve the retired thing*. (2) Inertness is the LESS invasive option for the
norm that governs here: `api-contract.md`'s deprecation-is-signalled norm demands the subcommand stay
callable and signalled with removal deferred to a major, and an inert stub satisfies all three. No
flow runs `stamp-merged` (its own docstring says so), so no caller observes the behaviour change
except as the notice | user can override → move `stamp_merged` into `change_log.py` and keep it
writing, which then obliges Chunk 03 to keep `status=` in the schema for a writer with no reader]`

`[DECISION-5: BP7's "a reference into an archived plan resolves" means by SCOPE or NAME, not by
PATH — live citations were repointed; citations inside RECORDS were deliberately left | Archiving
moves a file, so any hard-coded `artifacts/build-plan-<scope>.md` dangles at the moment the plan
finishes. Two classes came out of the sweep and they take opposite treatment. **Live surfaces**
(`nonfunctional-requirements.md`, two open-issue design docs, `work-model-delta.md`,
`backlog-service-prd.md`, `roi-batch/LAUNCH.md`) were repointed at their `archive/` paths, because a
reader following them today should land on the file. **Records** (`change-log.md`, `backlog.md`,
`learnings-detail.md`, `operator-verification.md`, the release plans) were not: they state where a
file was when the entry was written, and editing them to satisfy a resolver falsifies the record —
the same rule that exempts them from the path-reference check. What makes this a decision rather
than a gap is that the durable fix is neither: plans resolve **by scope**, which is how
`check-releasability` finds them and how the archive stays searchable, so `review-protocol.md`'s
drift rule now says to cite a plan by scope and warns that a durable artifact citing a path is
citing something that moves | user can override → sweep the record files too, accepting that their
paths then describe a tree that did not exist when they were written]`

**Retroactivity: `migrate`, declared** — not `contain`. Every norm carries this field, and a fleet
default cannot leave it implicit. Existing sites are swept: `views_enabled` keys and `scope_rollups`
blocks across onboarded repos, and accumulated live build plans into the archive (FL6). The norm's
`migrate` form also requires a tracking item whose **first acceptance criterion is the completion of
the enumeration** — that item is **#629**, and its acceptance must be updated to say so before
Chunk 05 starts.

## Status

- [x] Chunk 01: Rehome the survivors — two named modules, nothing deleted yet
- [x] Chunk 02: One reading — retire the flag, the command, and the dual progress path
- [x] Chunk 03: Trim the tag schema, the doc restatements, and the two norm decisions
- [x] Chunk 04: Archival — completion frontmatter, five deletion sites, two terminal states
- [x] Chunk 05: Doctor repair, the archive backfill, and the guards that keep it converged
Context: Plan written 2026-08-08 on `feature/governance-artifact-lifecycle` (off `develop`),
requirements v0.4 committed at `b681fab`. Ships as one PR — Chunk 05's cumulative review is the
`/prawduct:pr create` gate. Suite state is read from the evidence store, not recorded here.

**Chunk 01 shipped.** `views.py` became a re-export of `change_log.py` (tags) and `plan_index.py`
(plans) per DECISION-3. Its three review rounds are closed with nothing outstanding.

**Chunk 02 shipped and its review is closed.** `rev-20260808T170438Z-d90bf42a` (`cumulative`, 3
reviewers) returned 2 blocking / 7 warning / 12 note — actually 3 blocking; all three were fixed at
`8121f97` along with seven other findings, and twelve were accepted as recorded facts.
`rev-20260808T172837Z-3a4c7133` (`verify-resolutions`) returned **0/0/0**, and
`check-cumulative-critic` reports composed coverage spanning the branch with no unresolved blocking.

**One of those blockers was a framework defect this chunk provoked rather than contained**, fixed in
place per the fix-in-place norm: the chunk-ref check asserts existence for every backticked
deliverable ref and had no notion of a deliverable declared as a REMOVAL, so a retirement chunk
reported `missing-ref:` *because it succeeded* — at BLOCKING severity. Every future retirement chunk
would have hit it, and the tempting workaround (reword the plan until the parser stops seeing the
path) makes the plan describe its own deletion less clearly. `_BUILD_PLAN_GONE_QUALIFIER_RE` is the
mirror of `new`: explicit and adjacent rather than a heuristic, and with no expiry, because a
removal's delivery IS the absence.

**Chunk 02 shipped.** `views.py` is deleted; chunk progress has ONE reading — the Status
checkboxes, ticked by hand. `_git_aware_progress`, `degraded_progress_notice`,
`DEGRADED_PROGRESS_TOKEN` and `ChunkProgress.git_derived` are gone; `_resolve_chunk_progress_from`
is now a pure function of the plan text (it no longer takes `project_dir`, which is the collapse
made structural). `regen-views` and `stamp-merged` are deprecated-and-inert per DECISION-1/4.
DV7's tripwire — `unticked_committed_chunk_notice` — replaces the degraded-reading notice at both
of its call sites.

**Verification Strategy item 1 is DISCHARGED, and by A/B rather than by reading the diff.** A
control worktree at the pre-chunk HEAD ran the same four fixtures through a real `clear` → edit →
`stop` boundary. Results identical in every cell, including on a `views_enabled: true` repo:
reflection and critic-review gates both fire on an unticked chunk with session changes, and both
fall silent only when every box is ticked. **The worry this retired: there is no gate narrowing.**
The Stop gate always read the checkboxes directly (`_count_build_plan_chunks`), never the git
reading, so success criterion 6 holds by construction and is now measured rather than asserted.
One consequence is worth naming because it is newly load-bearing: ticking the last box now
disarms the gate, so the plan's own "Done when" ordering (Critic passes, THEN mark `[x]`) is the
thing keeping the final chunk reviewed. DV7's tripwire covers the opposite error.

**The two acceptance sweeps, as commands rather than a tally.** The versions below are the
CORRECTED ones. The first pass was recorded with two structural gaps the Critic caught, and the
correction is the more useful record: it omitted **the deleted module's own name** (`views.py`,
`lib.views`) from the identifier list, and it rooted only at `plugin/`. Both gaps produced real
residue — a standalone spike script whose `from lib import views` no suite run can go red on, a
shipped plugin docstring in `backlog/legacy.py` describing itself as the analogue of the deleted
module, and `documentation/project-structure.md` naming a deleted test file. **The lesson is that a
retirement's identifier sweep must include the retired thing's OWN name**, which is the one term the
author is least likely to list because it is the thing being removed rather than a symptom of it.

```
# (1) identifiers — including the module's own name, over every source root
grep -rnE 'views_enabled|regen.views|scope_rollups|stamp.merged|lib[./]views|views\.py|test_views' \
  plugin/ tests/ documentation/ --include='*.py' --include='*.yaml' \
  --include='prawduct-hook' --include='*.md'
# (2) the claim, in a vocabulary sharing no word with (1)
grep -rniE 'derived view|regenerat|flips at release|do not hand-edit|hand-flip' \
  plugin/ tests/ documentation/ --include='*.py' --include='*.yaml' \
  --include='prawduct-hook' --include='*.md'
```

Neither returns anything that ASSERTS the retired model outside Chunk 03's declared surfaces —
though the identifier sweep does not come back literally EMPTY over `tests/`, and the distinction is
worth keeping honest: four test files still write `views_enabled: true` as inert fixture filler
(carried to Chunk 03 above). Nothing reads it, so it asserts nothing; it does make the claim harder
to check than a clean grep would. The recorded commands also do not root at `.prawduct/`, where
everything is either frozen record or Chunk 03's declared work — true, but not falsifiable by the
command as written. What
they do return, and why each is correct: the two deprecated commands and their notices (DECISION-1/4);
past-tense retirement statements (required by GD3 — a reader looking for the flag must find the
retirement, not silence); `.critic-findings.json` and the disposition census, which are derived views
that legitimately survive; `plugin/CHANGELOG.md` and the requirements docs, which are **records** of
what was true when written and are falsified by editing; and `tests/test_plugin_migrate.py`, which
models a pre-2.0 file-sync repo where both the module and the flag really existed.

The residue inside `plugin/skills`, `plugin/methodology`, `plugin/templates` and
`documentation/release-process.md` is Chunk 03's declared work. **Two files were owned by nobody and
are fixed here rather than left**: `documentation/project-structure.md` (named a deleted module and a
deleted test file in its tree map) and `plugin/lib/backlog/legacy.py` (a shipped docstring calling
itself the analogue of the deleted module).

**Known interim cost, stated rather than discovered at PR time:** until Chunk 03 lands,
`documentation/release-process.md` tells an operator to run `regen-views` and read exit codes 2 and 3
that no longer exist. That document is a release runbook, so the window matters — it is closed by
Chunk 03, which is why this plan ships as one PR.

**Deliberately NOT done here, so it reads as a decision rather than an omission:** this repo's own
`.prawduct/project-state.yaml` keeps its now-inert `views_enabled:` and `scope_rollups:` keys.
Chunk 05's doctor repair removes them, and the plan names this repo as that repair's verification
subject — hand-editing them now would delete the subject.

**Chunk 03 shipped and its review is closed.** `chunks=` and `status=` are out of the tag schema and
out of every document that taught it; `check-releasability` reads `scope=` and `release=` and nothing
else. Both norm decisions are recorded rather than doc-synced: GD4 retires the
`regen-views-is-advice` ruling on both norms it touched and promotes its category-level sentence onto
`architecture.md`, so a future view writer needs no new ruling; BP7 narrows the ephemeral-ref firewall
onto ids that *mutate*, which is why the sibling count rule turned out to be the same rule. The
checkbox default landed in both digests. All three Chunk 02 carry-ins are discharged — R-16 in the
build-plan template where an author meets it, R-9's four fixtures, and R-22 decided (HOIST, executing
in Chunk 04).

`rev-20260808T182148Z-46964b12` (`cumulative`, 3 reviewers) returned 1 blocking / 4 warning / 15
note; the blocker and seven others were fixed at `b2c86d48`, all 20 findings are dispositioned, and
`rev-20260808T184452Z-a04d85ab` (`verify-resolutions`) returned **0/0/0**.

**The blocker is the lesson of this chunk, and it was a class of miss no sweep would have caught.**
`docs/principles.md` — the parent statement CLAUDE.md cites and every `final` review reads — still
taught the deletion premise and `chunks=` while three of its own children had just been narrowed. It
was in no chunk's enumeration. **The pattern: when you re-derive a rule, find the statement it is
derived FROM**, because the enumeration you inherited lists the places the rule is *applied*, not the
place it is *stated*. Two of the three reviewers found it independently.

Two enumeration misses in one chunk, both found by running rather than reading: `methodology/planning.md`
(inside a directory Chunk 02 recorded as "independently confirmed complete") and `docs/principles.md`
above. **The interim cost Chunk 02 flagged is discharged** — `documentation/release-process.md` no
longer instructs an operator to run a retired command and read exit codes that do not exist.

**Chunk 04 shipped.** `plan_archive.py` + `prawduct-hook archive-plan` give a plan an end of life
that is not deletion: completion frontmatter, both terminal states, a move into an `archive/` beside
the plan, checkboxes untouched. All three carried-in code items landed (the tripwire's narrowing and
DV7's wiring in one commit, R-22's hoist, R-14's symmetric walks). Suite state is read from the
evidence store, not copied here — the copy drifts and nothing reads it.

**BP6's list was three open sites and turned out to be four.** `plugin/methodology/planning.md`
taught the deletion premise and was in nobody's enumeration — found by running the sweep rather than
reading the list, which is now the second consecutive chunk where that is how the missing site was
found. A *second* sweep, over the statements this change FALSIFIES rather than the ones that instruct
it, then found three more: `briefing.py`'s helper docstrings still called it "the delete nudge", and
`templates/build-plan.md` still stated the tripwire's precondition as `Chunk <n>` matched anywhere.
**Two sweeps, different vocabularies, different answers** — the falsification pass is the one that
keeps being skipped, and it is where the docstring that now lies lives.

**Two departures from this chunk's written deliverables, both recorded rather than silent.**
(1) `_CHUNK_COMMIT_RE` ships THREE anchored forms, not the two the plan gave verbatim: over this
repo's last 800 commit subjects the two-arm version silences `drift-burndown` and `critic-burndown`
entirely, whose chunks are only ever named `close Chunk NN`. The plan's narrowing was verified
against this branch alone — the sample was the defect. The third arm is pinned positively for all
three forms, negatively for three real prose mentions, and by a strictly-narrowing property (0
subjects match that the old pattern missed). Accepted as R-4 on the review record.
(2) The frontmatter key for the shipping release is **`released_in`, not `release`** —
`release-plan-v3.2.7.md` already carries `release:` meaning *the release this plan governs*, and
release plans are exactly what gets archived, since `check-releasability` searches the archive by
design. The short name would have made re-stamping silently strip it. Found by asking "what already
uses this name?" against the real artifacts directory; every test written at the time passed.

`rev-20260808T192216Z-35d1afc0` (`chunk`) returned 1 blocking / 1 warning / 2 note, and
`rev-20260808T193445Z-6f2c8912` (`verify-resolutions`) returned **0/0/0** with R-1 and R-2 both
settled from the tree rather than from the fix commit. The blocker was
a record defect I caused by editing during the review (evidence and fact anchored to a pre-rename
tree), remedied by re-running the suite and re-covering with `verify-resolutions`. R-2 and R-3 are
fixed: the merge flow is now pinned **positively** on both paths (an assert-absent sweep passes when
the instruction is simply dropped — the never-armed failure this branch closed for DV7, one file
over), and the frontmatter round trip is lossless in both directions (`absorbed "here"` used to read
back as `absorbed "here`; Chunk 05's backfill is its first reader).

Next: Chunk 05. Doctor repair, the FL6 backfill, the convergence guards, FL4's attribution, and the
`cumulative` that gates the PR. **`check-change-log-entry` is RED and Chunk 05 owes the entry** —
no entry exists for this branch at all. Check the token budgets BEFORE writing: `building.md` has 2
tokens of headroom and the full digest ~15 characters (#630).

## Scaffolding

Existing repo; no new scaffold, no new dependencies, no build-config change. `uv run pytest -q` runs
the suite as today. The one structural addition is two new `plugin/lib/` modules in Chunk 01, which
need no scaffolding beyond their files and tests.

### Verification Strategy

Tests carry most of this, but three things tests cannot see, each assigned to a chunk:

1. **The gates still fire.** After Chunk 02 the Stop hook's Critic and reflection gates depend on the
   hand-ticked checkbox alone. Verify by exercising a real session boundary — not by reading the code
   that was just changed. This is the `gates.py:808` failure mode, and it failed silently last time.
2. **A real repo converges.** After Chunk 05, run doctor's repair against an actual consumer checkout
   from each cohort — one key-absent, one inert-`true`, one live-`true` (the requirements doc names
   which repos are which) — on a scratch copy, and confirm idempotence by running it twice.

   **DISCHARGED 2026-08-10, and by parsing the result rather than reading the output.** Scratch
   copies of `discodon` (key-absent), `cordyceps` (`true`, never regenerated) and `hallucinote`
   (`true`, with a real `release-notes.md`) each converged, and each reported *nothing to change* on
   an immediate second `--apply` — idempotence measured at the boundary the operator actually
   crosses, not asserted from the code. The third cohort is the only one that exercises the
   release-notes freeze, which is why it had to be a repo that really ran the old command.

   The assertion that makes this evidence rather than a line count: both changed state files were
   parsed before and after, and in each **exactly two top-level keys were removed (`views_enabled`,
   `scope_rollups`), none was added, and no surviving key's value changed.** A shorter file proves
   nothing about which lines went. `hallucinote` also exercised the backfill on a layout no fixture
   in this repo has — plans nested as `plans/<id>/build-plan.md`, four of them sharing that filename
   — and that is what surfaced the preview naming them indistinguishably (fixed by routing both
   commands' output through `plan_index.display_path`). A single operation-level approval over a
   list whose items cannot be told apart is not informed consent, which is the norm this plan cites
   for the approval shape in the first place.
3. **An archived plan still reads right.** After Chunk 04, open an archived plan cold and confirm the
   frontmatter answers "is this current?" before any body text can mislead, and that `grep` hits from
   it carry `archive/` in the path.

## Project Structure

```
plugin/lib/
├── change_log.py     # new (Chunk 01): tag reading + the merged validator
├── plan_index.py     # new (Chunk 01): scope→plan resolution, archive-aware
├── views.py          # deleted (Chunk 02)
├── buildplan_refs.py # dual reading collapses (Chunk 02)
├── release_readiness.py  # gains the rehomed checks (Chunk 01)
└── doctor/…          # gains the repair + backfill (Chunk 05)
```

### Module Boundaries

`change_log.py` knows tags and nothing about plans. `plan_index.py` knows plans and nothing about
tags. Nothing named `views` survives — the current module does both jobs under a name describing
neither, which is part of why the dual-reading defect reached three consumers before anyone
generalised it. `release_readiness.py` is the only caller of the tag validator, because it owns the
only gate that reads tags.

## Build Chunks

### Chunk 01: Rehome the survivors — two named modules, nothing deleted yet

- **Description:** The thin slice that proves the split before anything is removed. **Move** what must
  outlive `views.py` into two clearly-named modules, repoint callers, and fold the two earned checks
  into the gate that needs them — with `views.py` still present and still working, now as a
  **re-export** of the moved names rather than a second copy (DECISION-3, taken at build time on two
  learnings rules that were not available when this chunk was written). After this chunk the tree has
  one implementation reached by two import paths, and the behaviour Chunk 02 must not change is pinned
  by characterization tests over this repo's real data — which survive `views.py`, where an
  A-vs-B oracle would not.
- **Depends on:** none
- **Artifacts consumed:** requirements v0.4 — "What survives the deletion", CL6, CL7
- **Deliverables:**
  - new `plugin/lib/change_log.py` — `parse_change_log`, `ChangeLogEntry`, `parse_tag_line`, plus one
    merged `validate_change_log_tags` over the two surviving keys (value format, duplicate key,
    duplicate tag line), replacing four separate validators.
  - new `plugin/lib/plan_index.py` — `build_scope_to_plan_map`, `iter_scoped_plan_candidates`, the
    frontmatter/artifact-kind parsers, and the archive-skip guard. **Prune the archive directory at
    walk level** — the archive directory under .prawduct/artifacts/, created in Chunk 04 — rather than
    rglob-then-filter (BP9): three hot paths ask this, so the cost is paid at every session START via
    the briefing, at every session END via the Stop hook, and at review dispatch. Pruning a directory
    that does not exist yet is a no-op, so this lands safely before Chunk 04 creates it.
  - `plugin/lib/release_readiness.py` — calls `validate_change_log_tags`, and gains the rehomed
    "unreleased scope with no build-plan file" diagnostic, searching live **and** archived plans (CL7,
    BP8). Note `_find_release_plan` globs non-recursively today; BP8's live-then-archive rule lands here.
    **Also rehomed: the duplicate-scope half of `diagnose_scope_plan_coverage`** — CL6 lists that
    function whole among the six checks dying with `regen-views`, and its duplicate half guards
    frontmatter `scope:`, a field that SURVIVES. Enumerating the doomed module's callees is what this
    branch asks of every deletion, so leaving it would be the thesis's own failure inside the chunk
    written to prevent it. Reported, never fatal, like CL7. Recorded here so Chunk 02's sweep reads it
    as a survivor rather than as an orphan.
  - `plugin/lib/buildplan_refs.py::_scope_plan_map` repointed at `plan_index`.
  - Both new modules follow this repo's **return-value error convention** — `lib/` functions return
    dicts carrying `status`/`reason`; exceptions escape only at boundaries. New raising code inside
    governance internals is a preferences violation, so the extraction must not "simplify" the existing
    functions into raisers on the way across.
- **Tests:** unit — the merged validator against each malformed shape the four separate ones caught,
  including the `release=unreleased` case by name; `plan_index` archive pruning (an archived namesake
  must not shadow its live sibling, and must not be parsed). **Characterization** (replacing the
  equivalence oracle, per DECISION-3) — `change_log.parse_change_log` over this repo's real
  `change-log.md` and `plan_index.build_scope_to_plan_map` over its real artifacts directory, asserting
  the properties Chunk 02 must not change: every scope the log declares resolves to the plan file that
  declares it, the tagged-entry count and the release-pending scope set are what the tree says, and no
  archived path appears. These pin behaviour against data, so they still discriminate after `views.py`
  is gone. Integration — `check-releasability` exits non-zero on a malformed `release=` and names it.
  Perf — `plan_index` must not drag a heavy submodule (the NFR hot-path budget: three governance paths
  import it, two of them per session), asserted the way `test_lib_lazy_imports.py` already asserts it,
  with `lib.views` as the positive control that proves the probe can fail.
- **Acceptance criteria:** `check-releasability` refuses a `release=unreleased` entry with a named
  reason (this is the acceptance criterion, not a side effect — it is the guard that hid a branch from
  v3.2.8); the characterization tests pass and are shown to discriminate (each fails on a deliberately
  perturbed input, not merely passes); review dispatch, session start and session end all still
  resolve the branch's plan.
- **Critic mode:** final
  <!-- Override: inference picks `chunk` mid-plan. This chunk lands the architectural keystone —
       two module boundaries every later chunk builds on, plus the rehoming that decides whether the
       deletion in Chunk 02 is safe. Coherence matters before, not after. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: One reading — retire the flag, the command, and the dual progress path

- **Description:** Delete the machinery now that its survivors have homes. `views_enabled` goes from
  code, template, and every conditional; `regen-views` and `stamp-merged` go; the git-derived
  precedence composition and its degraded-reading notice go, leaving the hand-ticked checkbox as the
  single reading. Add DV7's reporting-only staleness tripwire, which is the one thing the git reading
  was genuinely good for.
- **Depends on:** Chunk 01
- **Artifacts consumed:** requirements v0.4 — DV1–DV5, DV7; #558's blast-radius inventory
- **Deliverables:**
  - `plugin/lib/views.py` deleted; `plugin/lib/core.py` loses `views_enabled` from the opt-in scan
    surface.
  - `plugin/bin/prawduct-hook` — `regen-views` is **deprecated, not removed** (DECISION-1): it stays
    callable, prints a `WARNING:` stderr notice in **plain language naming no internal identifier**
    (the observability norm), writes nothing, and exits 0. `stamp-merged` is already deprecated in this
    shape — match it rather than inventing a second convention. Removal of both defers to a major.
    **`stamp-merged` becomes inert in that same shape** (DECISION-4), because `views.stamp_merged`
    dies with the module and its only output — `status=` — has no reader left after this chunk.
  - **The registries and prose that name what changed here, in THIS commit** — *removing a mechanism
    requires removing its name too*, and *the registry documenting an enumerated set is owed its row in
    the same commit that changes the set*. Three that a `views_enabled` grep alone does not reach:
    `.prawduct/artifacts/api-contract.md`'s Surface Inventory (its Deprecated row lists
    `regen-views --check` and `stamp-merged`; both entries change meaning), and two docstrings that
    become false the moment `views.py` is gone —
    `plugin/lib/release_readiness.py::release_pending_scopes` (contrasts itself against
    `views.collect_release_pending_scopes` and explains itself in terms of what `regen-views` needs) and
    `plugin/lib/buildplan_refs.py::_normalize_chunk_id` (says it is "**not** `views.normalize_chunk_id`,
    which is the canonical one" — after the deletion it IS the only one).
    **Not here: `.prawduct/cross-cutting-concerns.md`'s derived-views row.** It is already Chunk 03's,
    and splitting one row's rewrite across two chunks is the incoherence this branch exists to remove.
    Chunk 03 owes it the `test_public_function_coverage` treatment — the surviving backstop and the
    restore trigger recorded, not the row deleted.
  - `plugin/lib/buildplan_refs.py` — `_git_aware_progress`, `_committed_chunk_ids`'s progress role,
    `degraded_progress_notice` and `DEGRADED_PROGRESS_TOKEN` removed; `resolve_chunk_progress` becomes
    the checkbox reading; `_completed_chunk_ids`' two-reading branch collapses to one.
    `_commits_ahead_of_base` **stays** — `critic_mode` uses it independently.
  - DV7's tripwire: `_committed_chunk_ids` is **repurposed, not deleted** — it feeds a
    reporting-only comparison of the ticked set against the chunk ids the session's commits mention.
    **Expected yield, per the proportionality norm:** it catches a finished-but-unticked chunk before
    the session boundary. It **emits that yield observably** — every firing names the chunk and the
    commit, so the control can be retired on evidence later rather than defended on principle.
  - `plugin/templates/project-state.yaml` loses `views_enabled` and `scope_rollups`;
    `plugin/lib/briefing.py`, `critic_mode.py`, `gates.py`, `advisory_store.py`,
    `operator_verification.py` lose their `views_enabled` branches and caveats.
  - `.prawduct/release-notes.md` renamed to frozen archive with a header saying so (DV5).
  - **Three dependents of Chunk 01's re-export shim that this chunk breaks.** Each is a correct
    Chunk 01 decision with an obligation landing here, and none would name its cause in the failure:
    (1) `tests/test_lib_lazy_imports.py::test_the_probe_can_fail` uses `lib.views` as its **positive
    control**, and `HEAVY_SUBMODULES` lists it — the control needs a new subject, and without one
    every empty-set assertion in that file goes vacuous rather than red; (2)
    `tests/spikes/change_log_roundtrip.py` does `from lib import views` and is a **standalone,
    non-collected script**, so the suite will not catch it (the shim's `noqa` names it); (3)
    `plugin/lib/views.py::_plan_label` is deleted, the inlined path helper going with the module;
    and (4) `tests/preferences/test_build_plan_decoding.py::test_the_pin_has_something_to_check` asserts
    `set(PLAN_MODULES) <= modules`, so deleting `views.py` turns the pin red until `PLAN_MODULES`
    drops it. Repair by repointing, never by weakening the probe.
- **Tests:** `tests/test_views.py` is retired here. Its ~30 tests targeting `parse_change_log` are
  **the contract** — rewritten against `change_log.py` in Chunk 01, so they move rather than die with
  the file, and the same applies to every other survivor it hosts. Rewrite the
  `views_enabled`-parameterised cases in `test_build_plan_resolution.py`,
  `test_critic_mode_inference.py`, `test_handoff_parser_correctness.py` (its "Defect 4 — at EVERY
  consumer" section becomes a single-reading assertion), `test_briefing_functions.py`,
  `test_plugin_runtime.py`, `test_plugin_migrate.py`. New: the tripwire reports and never writes.
- **Acceptance criteria:** one reading of chunk progress exists; the Stop hook's Critic and reflection
  gates still engage on a plan with an unticked chunk **and still engage after the final chunk is
  committed but before its review** — verify against a real session boundary, per Verification Strategy
  item 1; `regen-views` still exits 0 with its notice.
  **Completeness is a falsifying command returning nothing, never a count of sites fixed** — a count is
  true of any prefix of the real set. And the identifier sweep is only half: grepping `views_enabled`
  finds the sites that *name* it and misses the prose that *asserts the old model in other words*. So
  two sweeps, in vocabularies sharing no word: (1) the identifiers — `views_enabled`, `regen-views`,
  `scope_rollups`, `stamp-merged`; (2) the claim — "derived view", "regenerate", "flips at release",
  "canonical source is the change-log tag", "do not hand-edit", "hand-flip". Both must come back empty
  of live assertions before this chunk closes. Record the commands, not the tally.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: Trim the tag schema, the doc restatements, and the two norm decisions

- **Description:** The prose half, and the two norm lifecycle events. `chunks=` and `status=` leave the
  tag schema; every document that teaches the derived-views model is corrected; the
  `regen-views-is-advice` ruling is retired with its precedence annotations removed from both norms it
  touched, and the ephemeral-ref firewall is narrowed. Both are recorded decisions, not doc-sync.
- **Depends on:** Chunk 02
- **Artifacts consumed:** requirements v0.4 — CL1, CL2, CL5, GD3, GD4, BP7
- **Deliverables — the surfaces, enumerated so the chunk's true size is visible.** Plugin docs
  shipping to consumers: `plugin/skills/critic/review-protocol.md`, `plugin/skills/critic/SKILL.md`,
  `plugin/skills/critic/review-cycle.md`, `plugin/skills/pr/SKILL.md`,
  `plugin/skills/pr/review-protocol.md`, `plugin/methodology/building.md`,
  `plugin/templates/build-plan.md`, `plugin/templates/change-log.md`, and
  **`plugin/methodology/session-digest.md`** — a new framework-wide default must land in the digest,
  because place-once preferences and the thin CLAUDE.md anchor do **not** reach migrated repos, and
  "the checkbox is yours to tick" is exactly such a default. Repo records:
  `documentation/release-process.md` (step 3's knowingly-broken sweep and step 4 both go),
  `.prawduct/cross-cutting-concerns.md` (the derived-views row and its READ-side rule — **and the
  Requirements-clarity row, which gains a runtime leg**: `check-releasability` now reports a
  release-pending scope with no build-plan file, a Principle 6 detector the row's discovery /
  artifact / `building.md` / UserPromptSubmit legs do not cover),
  `.prawduct/runbooks/cut-and-publish-a-plugin-release.md` (Phase 1 steps 2 and 10).
  Norm decisions: `.prawduct/artifacts/architecture.md` and `.prawduct/artifacts/data-model.md` lose
  the `regen-views-is-advice` precedence annotations; `.prawduct/learnings.md` +
  `learnings-detail.md` retire the ruling and the eight format-rule entries, and **invert the
  never-hand-check-the-boxes rule** (it becomes the opposite instruction, and its `learnings-detail.md`
  body — which now also records the false `Resume:` signal the derived boxes produce — is rewritten
  with it, not left asserting the retired mechanism). Its shape was already fixed at `4dcd883`, so the
  400-char budget is no longer the inverting author's problem; **do not re-locate it by line number**,
  the numbers moved in that commit. Its neighbour — *a change-log entry's BODY must cover every chunk
  its `chunks=` tag claims* — is a **second** entry this chunk owes a rewrite: `chunks=` leaves the tag
  schema here, but the lesson under it (release notes derive from the entry body, so an omitted
  deliverable ships invisibly) survives the tag and must be re-expressed without it rather than retired
  along with the eight format rules. Several of these carry token-budget guardrail tests — expect the
  trim, do not discover it at close.
- **Tests:** the structural//assert-absent scans that pin retired vocabulary; the guardrail tests on
  the trimmed surfaces; `test_record_lint.py`'s citation checks against the retired learnings ids.
  - **Carried in from Chunk 02's review (R-16), the half that did not land.** The tripwire's
    precondition — it fires only on a `Chunk <n>` commit subject, so a repo without that habit gets
    permanent silence indistinguishable from "every box is correct" — is recorded in
    `unticked_committed_chunk_notice`'s docstring but NOWHERE A READER OF THE NOTICE SEES IT. The
    finding named two remedies and Chunk 02 delivered neither: an author-facing statement in
    `plugin/templates/build-plan.md` or `plugin/methodology/building.md` (both this chunk's files),
    or the emitted notice stating its own basis. Take one. A control whose blind spot is documented
    only where its authors read is a control that looks healthy to everyone else.
  - **Carried in from Chunk 02's review (R-9's tail), while this chunk is already sweeping.** Four
    test files still write `views_enabled: true` as inert fixture filler —
    `tests/test_release_verification.py`, `tests/test_plugin_runtime.py` (two sites) and
    `tests/test_classify_diff_risk.py`. Nothing reads it and no assertion depends on it, so this
    is cosmetic; it matters only because it is why an identifier sweep over `tests/` does not come
    back empty, which makes the completeness claim harder to check than it should be. (Leave
    `tests/test_plugin_migrate.py` alone — it models a pre-2.0 file-sync repo where the flag really
    existed.)
  - **R-22 — DECIDED: hoist, executed in Chunk 04.** The narrowing of `duplicate_scope_errors`'
    trigger was a side effect of Chunk 01's rehoming rather than a choice, and the arm taken is to
    restore its old reach. The reasoning and the test to write are recorded on Chunk 04's
    Deliverables, where the edit lands — this chunk is `Type: doc-only` and the fix is code, the
    same call made for the tripwire narrowing.
- **Acceptance criteria:** no shipped document teaches `chunks=`, `status=`, or a derived Status block;
  the release process describes adding `release=` and nothing else; both norm retirements are recorded
  as decisions naming what changed and why, and a reader of either norm finds the retirement rather
  than silence.
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 04: Archival — completion frontmatter, five deletion sites, two terminal states

- **Description:** Give build plans an end-of-life that is not deletion. A completed or superseded plan
  gains completion frontmatter and moves to the archive; every surface that deletes a plan or teaches
  that plans are deleted is changed; archived plans stay findable by name.
- **Depends on:** Chunk 03
- **Artifacts consumed:** requirements v0.4 — BP1–BP3, BP5, BP6, BP8, BP10
- **Deliverables:**
  - The archival operation itself — add completion frontmatter, move plans into
    new `.prawduct/artifacts/archive/`, and leave checkbox state untouched (FL6: it is not a
    precondition and is not corrected, because nothing reads an archived plan's boxes).
  - Completion frontmatter carrying: terminal state (**completed** or **superseded/abandoned** — BP10's
    two states), date, the release that carried it where the product versions, an explicit
    no-longer-maintained statement, and for the superseded case what replaced it or why it stopped.
  - **The deletion surfaces** (BP6), because fixing one leaves the behaviour in force in the rest.
    **THREE remain — the list is two shorter than when it was written**, and the two that went were
    removed by Chunk 03's BP7 re-derivation rather than by this chunk: `plugin/methodology/building.md`
    (the "deleted when work ships" premise) and `plugin/skills/critic/review-protocol.md` (the WARNING
    resting on it) are already done — `grep -rniE 'deleted when (the )?work ships|plan is deleted'
    plugin/` comes back empty. Do not go looking for them. Still open, and all three genuinely
    instruct deletion rather than merely assuming it: `plugin/skills/pr/SKILL.md` (merge flow archives
    instead of deleting; the gitflow-vs-trunk branch still decides *when*, not *whether*),
    `plugin/skills/janitor/SKILL.md` (its delete-the-plan cleanup step), `plugin/lib/briefing.py`
    (**two** nudges telling the operator to delete the plan every session).
    **A live interim contradiction until this lands:** `docs/principles.md` now says a completed plan
    is archived while those three still say delete. Nothing reaches a consumer inconsistent because
    the branch ships as one PR — but that is the reason it must, not a reason to relax.
  - **Cosmetic, free on any commit this chunk makes:** `plugin/lib/change_log.py`'s docstring says
    "21 repos'" — a count in a durable docstring, which is the exact shape Chunk 03 re-derived
    Principle 13 to prohibit. It is illustrative, not load-bearing (the argument survives at 22), so
    it was NOT fixed in Chunk 03: `change_log.py` is judgeable, and a two-word docstring edit after a
    clean `verify-resolutions` buys a whole review round for nothing. Make it relational here, where
    the file is being opened anyway.
  - `plugin/templates/build-plan.md` gains the completion-frontmatter shape.
  - **A false positive DV7's tripwire produced on this repo, minutes after it shipped.**
    `_CHUNK_COMMIT_RE` is `Chunk\s+(\d+)`, which matches a chunk id anywhere in a commit subject —
    including a commit that merely *mentions* a later chunk. Chunk 02's own closing commit ("…carry
    R-16's undelivered half and R-9's tail to Chunk 03") made the notice report Chunk 03 as
    finished-but-unticked. Not caught by review; caught by running the thing.
    **This lands here rather than in Chunk 03 only because that chunk is `Type: doc-only`** — the
    fix is code, and retyping a chunk to carry a rider is how a review mode gets chosen for the
    wrong diff. A narrowing verified against this branch's real subjects, which keeps both
    conventions in use and drops the prose mention:
    `re.compile(r"\(Chunk\s+(\d+)\)|:\s*Chunk\s+(\d+)\b")` — parenthesised (`land it (Chunk 04)`)
    or immediately after the conventional-commit colon (`feat(scope): Chunk 02 — …`). Take the
    `_committed_chunk_ids` group-handling with it (two groups now), and pin all four subject forms.
    **Why it is worth doing rather than accepting:** a brand-new control whose first firing is
    wrong teaches its first readers to ignore it, which is the habituation the proportionality norm
    exists to prevent — and this control's whole defence is that it emits its yield observably.
  - **DV7 is wired where no governed session reaches it** (Chunk 03's cumulative review, W-3;
    carried here because it is code and the tripwire's regex fix is already in this chunk — one
    commit, no extra round). Its only call sites are `cmd_verify_chunk_refs` and `cmd_handoff`;
    the Stop hook and `critic-begin` grade through `record_lint` → `buildplan_refs`, and `/clear`
    writes the handoff via `briefing.generate_session_handoff`, so an ordinary session never
    sees the notice. **This is worse than an unfired control**: DV7's stated defence is that it
    emits its yield observably, so a later "zero recorded yield" would read as *no defect
    occurred* when the truth is *never armed* — the retirement-on-evidence argument would be
    made from a control that was never in the path. Wire it into the session-boundary surface
    (`/clear`'s handoff generation is the natural one — it already reads the plan), and pin the
    call site, not just the function. Fix this in the SAME commit as the regex narrowing above:
    arming a control whose first firing is a known false positive is the one ordering that makes
    things worse.
  - **R-22, decided in Chunk 03 and landing here because the decision is HOIST and the edit is code.**
    `duplicate_scope_errors` currently sits inside `_plan_coverage_warnings`, which
    `check_releasability` reaches only after `if not pending: return 0` — so on a repo with nothing
    release-pending it never runs, where its old caller ran it every invocation. **Hoist it above that
    early return.** The reasoning, recorded because "either is fine" was the offer and this is the arm
    taken: the function takes only `artifacts_dir` and asks a question about repo structure, so gating
    it on `pending` is a coupling nobody chose — it was a side effect of the rehoming. Its message
    ("one plan is malformed") is actionable at any time, and the defect it names is exactly the kind
    that is cheap to fix on a quiet day and expensive to discover mid-release, when scope→plan
    resolution has just become load-bearing. Noise risk is near zero: two plans genuinely declaring
    one scope is rare and always wrong. Keep the missing-plan half where it is — that one is *about*
    the pending set and correctly scoped to it. Test the no-pending repo with a duplicate scope, which
    is the case that is silent today.
  - **Carried in from Chunk 02's review (R-14), because this chunk creates the directory that makes
    it real.** `plan_index._markdown_files` prunes ANY directory component named `archive` at every
    depth, but `iter_scoped_plan_candidates(include_archived=True)` re-walks only the archive
    directly beneath the artifacts root. On a repo nesting plans as `plans/<id>/build-plan.md` with a sibling
    `plans/<id>/archive/`, an archived plan is therefore pruned from the live pass AND absent from
    the archived pass — invisible to every reader, which BP8's live-then-archive rule assumes cannot
    happen. Today it costs only a spurious "no build-plan file" advisory because no archive exists;
    once this chunk creates them, it is a correctness bug. Make the two walks symmetric, and test the
    nested case specifically — the flat fixture passes under both shapes.
- **Tests:** unit — frontmatter round-trips for both terminal states; a named artifact resolves after
  archival and a live file wins over an archived namesake (BP8); an archived plan is not treated as a
  live assertion by any scanner (BP5). Integration — the merge flow archives rather than deletes on
  both the trunk and gitflow paths. Assert-absent: no shipped surface instructs deleting a plan.
- **Acceptance criteria:** a completed plan ends up in the archive with frontmatter that answers "is
  this current?" on open; a superseded half-finished plan archives too, with unticked boxes intact; no
  surface anywhere tells anyone to delete a plan.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 05: Doctor repair, the archive backfill, and the guards that keep it converged

- **Description:** Land the fleet. Doctor performs the mechanical repair and the one-time backfill;
  two guards stop the divergence recurring; the release attributes the change. Nothing here asks the
  owner to hand-edit a repo.
- **Depends on:** Chunk 04
- **Artifacts consumed:** requirements v0.4 — FL1–FL7, GD1, GD2, GD3
- **Deliverables:**
  - Doctor's mechanical repair (FL2), idempotent and a no-op on repos already converged: remove the
    `views_enabled:` key, remove `scope_rollups:` and its comments, freeze `release-notes.md`, strip
    `<!-- views_enabled: … -->` comments from build plans.
    **Preview-by-default with `--apply`, and ONE operation-level approval** naming the blast radius and
    what cannot be undone — the security-model norm forbids a per-action gate here, in those terms:
    per-file confirmation is not merely noisy, it is a safety regression through confirmation fatigue.
    Every emitted line carries a plain-language reason and **no prawduct-internal identifier**.
  - The FL6 backfill: archive existing shipped plans, here and in consumer repos. Shipped is decided
    mechanically — a plan whose `scope=` carries a `release=` tag in the change log — which is a
    fitting last use of the tag data before it goes inert. Where a product has no release tags, doctor
    **proposes** the set and the operator confirms; proposing a move is not writing governance state,
    so FL3 does not reach it. **This repo is a subject, not an exception** — its own accumulated plans
    are backfilled by the same code path, which is also the verification that the path works.
  - FL3's report-only notice for live plans whose Status was derived and is stale on an in-flight
    chunk. **Expected yield:** it names the plans a human must look at once, per repo, during the
    transition. **Emitted observably:** it prints the plan and the chunk, so it can be retired when it
    stops firing.
  - **GD1** — a test asserting every opt-in flag's template value equals its code default. **Expected
    yield:** it fails on the next flag whose template and code disagree, which is the actual root cause
    of the split this plan exists to fix (three disagreeing declarations, nothing comparing them).
    **Emitted observably:** the failure names the flag and both values.
  - **GD2** — a doctor check that fails if `views_enabled` reappears. **Expected yield:** a repo
    reintroducing the flag by copying an old state file. Prints the repo and the key.
  - **GD3** — the retirement is recorded where someone looking for `views_enabled` or `regen-views`
    finds it, not silence. The failure mode being designed against is the `cmd_regen_views` docstring,
    which described the file-sync auto-enable for three minor versions after that engine was deleted.
  - **FL4** — a version-delta banner headline naming the retired flag and command, plus the
    `plugin/CHANGELOG.md` entry that becomes the GitHub Release notes.
  - **One test this chunk's backfill is expected to break**, named so it is repaired rather than
    weakened: `tests/test_plan_index.py::TestAgainstTheRealArtifactsDirectory` asserts a floor on how
    many scopes the LIVE map resolves. The backfill archives shipped plans, so the floor moves. It was
    deliberately set low (>= 2) rather than tightened, and the sibling assertion pins this branch's own
    in-flight plan, which carries no `release=` and so is not backfilled — but a red here is archival
    working, not a `plan_index` regression.
- **Tests:** unit — repair idempotence (twice is a no-op) and per-cohort behaviour across all three
  cohorts; the backfill's shipped-set derivation; GD1 across every opt-in flag; GD2's detection.
  Integration — a scratch copy of one real repo per cohort converges, per Verification Strategy item 2.
- **Acceptance criteria:** all three cohorts converge with no hand-editing; running the repair twice
  changes nothing the second time; GD1 fails if a template default is edited away from its code
  default; the banner names the change on the release that carries it.
- **Type:** cumulative-final
  <!-- Last chunk of a plan shipping as one PR: its review IS the one
       `/prawduct:critic cumulative` over merge-base...HEAD. Commit first, run once, no separate
       `final`. That review is also the `/prawduct:pr create` gate. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status; change-log entry added carrying `scope=governance-artifact-lifecycle`

## Early Feedback Milestone

**Milestone chunk:** 02
**What the user can do:** open a build plan mid-branch and see checkboxes that mean what they say —
tick one when a chunk finishes and have it stay ticked. That is the whole user-visible point, and it
arrives as soon as the derivation is gone.

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk after its Critic review passes. Ships as **one PR** — the
removal, doctor's repair, and the attribution banner must land in the same release or consumers get a
silent break (see the HIGH open assumption). Chunk 05's cumulative review is the `/prawduct:pr create`
gate.

- **After Chunk 01** (architecture validation): confirm the two module boundaries hold and that the
  characterization tests actually discriminate — perturb each input and watch the test fail. Under
  DECISION-3 there is no second implementation to be vacuously equal to, which removes the ledger
  spike's trap but not the obligation: a characterization test asserting a property the data cannot
  violate is the same empty pass by another route.
- **After Chunk 02** (midpoint, highest risk): verify the Stop hook's gates against a real session
  boundary, not by reading the diff. This is where `gates.py:808`'s incident happened, and it failed
  silently.
- **Before Chunk 05 completes** (release readiness): confirm no consumer repo needs a manual step, and
  that #558 is closed or repointed rather than left describing a flag that no longer exists.
