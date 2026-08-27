---
artifact: build-plan
version: 2
scope: branch-claim-multiplicity
branch: fix/branch-claim-multiplicity
depends_on:
  - artifact: tactical-efficiency-analysis-2026-08-13
  - artifact: build-plan-tactical-efficiency
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → inapplicable, because no chunk touches a reviewer write path or the `clear` refusal"
      - "authority fails closed; advice fails soft → [DECISION: Chunk 01 STOPS treating multiple branch claims as an authority failure. Fail-closed protects against *governing by a plan nobody chose*; it was pointed at a proposition that is simply false — a branch can legitimately carry several plans (owner, 2026-08-13; discodon carries three on one branch). The posture is preserved where it belongs: resolution still never picks silently, it reports what claimed the branch and what it chose | engages the norm's why: a wrong plan governing must not look like a right one — met by loud attribution rather than by refusal | user can veto and keep the refusal]"
      - "local-first: no network, no daemon, no third-party runtime dependency → conforms (file reads and one git probe; Chunk 04 adds a doc and a version string)"
      - "the plugin writes nothing into a governed repo except its own .prawduct/ state → conforms; Chunk 04's dogfooding recipe is per-machine `.claude/settings.local.json`, written by the operator, never by the plugin"
      - "prawduct is Python but never Python-specific → conforms; frontmatter, git and prose only"
      - "prawduct guides and reviews; it never implements → conforms; no product code is written by any chunk"
      - "goals and verification bind; prescribed method is advice → engaged and exercised: Chunk 03's prescribed method (fix the probe's prose) was falsified by its own verification step and the chunk was rescoped to a test, with the reason recorded inline rather than silently dropped"
      - "every fact has one home → conforms: which plan governs stays computed at resolution, nothing new is stored, and the contested-claim sentence is rendered by one function (`core.describe_branch_claim`) rather than restated per surface"
  - artifact: data-model
    dispositions:
      - "verdicts computed from the append-only fact ledger, never from mutable model-written state → inapplicable, because no chunk touches the Critic data plane"
      - "facts are immutable and append-only → inapplicable, same reason: no fact kind is added, edited or read here"
      - "derived views are disposable and never authoritative → conforms; `BranchClaim` is a return value computed per call, never persisted, so no gate can read a stale one"
      - "a governance document reaches a terminal state, never deleted; live outranks archived → engaged by Chunk 02, which moves the retention signal off the `active_build_plan` scalar for a branch-declaring plan. Archiving is unchanged and still happens at the release."
      - "every issue written to the backlog store conforms to the issue standard's §1 title rules → inapplicable, because no chunk writes a backlog item (the `plan_index` refactor R-11 names is filed by hand through `/prawduct:backlog`, which enforces it)"
      - "a newer-schema fact surfaces as a loud block → inapplicable, because no chunk reads the evidence store"
      - "two stores, two lifetimes → inapplicable, because no chunk writes to either store"
      - "`backlog_service_repo` selects the authoritative backlog store → conforms; nothing here reads or writes `.prawduct/backlog.md`"
last_validated: 2026-08-13
---

## Requirements Confidence

**Level:** High

**Why:** Three of the four items are defects found by reviewing shipped code against live consumer
data, not inferred: discodon's `.prawduct/artifacts/` carries five build plans that already declare
`branch:`, three of them naming one branch, all written before the field had meaning. The fourth
(release notes + dogfooding) is a stated owner requirement. The mechanism was read before planning
(`core.resolve_build_plan_path`, `plan_index.branch_claiming_plans`, `briefing.staleness_scan`,
`gitattributes_probes`, the marketplace install shape in a consumer's `.claude/settings.json`).

**Open assumptions / unknowns:**

- [ASSUMPTION: the plugin version is the marketplace cache key, so dogfooding off `develop` needs a
  prerelease bump rather than only a ref change | MED impact | verified at first install attempt;
  if wrong, the recipe loses one step]
- ~~[ASSUMPTION: Chunk 01 keeps `AmbiguousPlanBranchError` and its Stop-hook exit-2 handling alive
  for the residual unresolvable case rather than deleting them]~~ — **RESOLVED THE OTHER WAY during
  the build.** The precedence leaves no unresolvable case, so the class, the hook's `main()`
  classifier and the `cmd_stop` probe had no route that could raise them. Kept, they would have been
  handling for a condition no code can produce — the residue Principle 25 names — so all three were
  deleted and their tests redirected. Recorded rather than quietly satisfied: an assumption that
  resolves against itself is the one worth seeing.

**What would raise confidence:** Nothing pending.

## Status

- [x] Chunk 01: Several plans may claim one branch — resolve and attribute, never refuse
- [x] Chunk 02: A branch-declaring plan retires by archiving alone — no pointer left to ignore
- [x] Chunk 03: Pin what union-merge does with a twice-landed entry
- [ ] Chunk 04: Release notes and a develop-track dogfooding path for sibling repos

**Chunk 04 stays UNTICKED, and this paragraph carries why** — not VRF-017 alone. The 2026-08-13
amendment's decision is honoured rather than overridden: the box opens only when a sibling repo has
actually run a session on the track. The queue entry exists (`operator-verification.md`), but this repo runs
`operator_verification_required: false`, so `check-operator-verification` returns "not required"
and no gate will ever raise it: a deferral queue whose enforcing gate is off is a write-only
queue. The obligation is therefore stated here, where the briefing and the release checklist
read it. **What is done:** the release notes (in the OPEN `## v3.4.1-dev.2` section) and the
dogfooding recipe, both in `-dev.N` terms. **What is not:** nobody has run a session on the
develop track, because the recipe installs from `ref: develop` and could not be exercised until
this merged. Whoever runs VRF-017 ticks the box, folded into the next PR that touches the repo rather
than a bookkeeping commit on `develop`; a release cut before then should say in its notes that the
track is undogfooded — and if this repo wants the queue to bind, that is the
`operator_verification_required` flag, which is an owner decision and was not flipped here.

Chunk 01 landed 2026-08-13 (`9e66c88e` + `9f933285`; review `rev-20260814T033741Z-ba15c001`, 0
blocking / 10 warnings / 13 notes, all ten warnings fixed in one batch and six notes accepted as
facts). **Three reviewers independently found the same defect**, and it was in the one sentence that
replaces the deleted refusal: the `order` reason asserted "no single plan has chunks left" in a state
where several do — the shipped headline case. Derived from the state now, with each rendered reason
pinned; none of the three wordings had been asserted anywhere before.

Two findings reached past the files the chunk was about: three skill files still spelled
one-claimant resolution (the `/prawduct:pr` one feeds `archive-plan`, so a discretionary pick could
retire a live sibling plan), and the contested-claim line failed silent inside a broad `except` —
the only surface that says a branch is contested, with the fail-closed backstop deliberately gone.
An existing guardrail test caught the fix's own gap: the PR skill was told to run a command it was
not granted.

R-11's better shape — moving the Status-roster predicate down into `plan_index` so `core`'s
dependencies stay downward — was **not taken here** and is filed rather than smuggled in: it is a
refactor of the parser's home, not a line. The laziness that holds the graph acyclic is documented as
a constraint at both ends meanwhile.

Context: Authored 2026-08-13 after a review of the tactical-efficiency pass against its own analysis
and build plan. Chunks 01–03 fix defects that review found; Chunk 04 is the release work the pass
still owes. Parent evidence: `tactical-efficiency-analysis-2026-08-13.md` §F6–F7 and
`build-plan-tactical-efficiency.md` Chunks 06–07. Branch: `fix/branch-claim-multiplicity` off
`develop`. This plan declares its own `branch:`, so it is the second live opt-in and Chunk 01's
first real test.

## Scaffolding

Existing repo — no initialization. Suite: `python3 -m pytest tests/ -q`; record evidence via
`prawduct-hook test-evidence record`. Several governance prose files carry token-budget guardrail
tests — when a protocol edit trips one, simplify or deduplicate within the file first, raise the
ceiling second, and never relocate text between files to dodge a budget.

### Verification Strategy

Beyond unit tests: Chunk 01 is verified against a fixture repo carrying two claiming plans AND
against a read-only replay of discodon's real frontmatter (its five claims, three colliding) — the
population that found the defect is the population the fix must satisfy. Chunk 02 by resolving on
this branch and on `develop` before/after. Chunk 04's recipe is verified by actually pointing one
sibling repo at the develop track and opening a session there.

## Build Chunks

### Chunk 01: Several plans may claim one branch — resolve and attribute, never refuse

- **Description:** `_branch_claimed_plan` treats two live plans declaring one `branch:` as an
  authority failure and refuses, which fails the arrangement it was built to serve: a branch can
  carry several plans (a `release/2-0` with a telemetry plan and a documentation plan; discodon
  carries three on one branch today). Replace the refusal with a stated precedence over the
  claimants: (1) plans with unfinished chunks (`buildplan_refs._has_unfinished_chunk` — the plan
  being *worked* is the one governance is about); (2) the `active_build_plan` scalar when it names
  one of the claimants, which promotes the pointer from legacy to the tie-breaker *within* a branch;
  (3) a stated deterministic order over what remains. **Attribution is what replaces the refusal**
  — whenever more than one plan claimed the branch, the choice and the rejected claimants are named
  where the reader is (session briefing; gate output that reports a resolved plan). Chunk 06's
  concern was that governing by the wrong plan looks exactly like governing correctly; being told
  which plan was chosen and what else claimed the branch is what makes it stop looking that way.
  **Precedence step 1 must not flip resolution at the closing PR:** ticking the last chunk box
  empties the unfinished set, so an empty result falls through to the full claimant set rather than
  to the pointer — a sole claimant keeps governing after its last tick.
- **Depends on:** none
- **Artifacts consumed:** `build-plan-tactical-efficiency.md` Chunk 06
- **Deliverables:** `plugin/lib/core.py` (`_branch_claimed_plan` precedence + an attribution the
  callers can render), `plugin/lib/briefing.py` (report the multi-claim case rather than the
  refusal), `plugin/methodology/planning.md` and `plugin/templates/build-plan.md` (the one-plan-per-
  branch claim is wrong in both — state that several plans may claim a branch and how the winner is
  chosen). Decide and record whether `AmbiguousPlanBranchError` and its Stop-hook exit-2 handling
  retain a caller; if nothing can raise, delete them rather than leaving blessed dead code
  (Principle 25).
- **Tests:** two claimants, one unfinished → unfinished wins; two unfinished, pointer names one →
  pointer wins; two unfinished, pointer names neither → deterministic and attributed, never raising;
  sole claimant with all chunks complete still resolves (the closing-PR case); discodon's real
  five-claim shape resolves without raising on each of its branch names; no claimant → pointer, then
  default, unchanged.
- **Acceptance criteria:** a fixture repo with three plans claiming the checked-out branch resolves
  one, names it and the other two, and every gate runs; no input produces a refusal that stops a
  session; suite green.
- **Critic mode:** final
  <!-- Keystone: this changes what every governance surface resolves. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Change-log entry added (`scope=branch-claim-multiplicity`, no `release=`)
  3. `/prawduct:critic` run and blocking findings resolved
  4. Committed and chunk marked `[x]` in Status

### Chunk 02: A branch-declaring plan retires by archiving alone — no pointer left to ignore

- **Description:** `planning.md` and `/prawduct:pr` both promise that a merged branch-declaring plan
  "reads live-but-inactive with no advisory to ignore." It does not: the merge-flow RETAIN bullet
  says to keep `active_build_plan` pointing at it, so resolution falls through to the scalar and the
  archive-the-plan advisory fires exactly as before — observed on this repo's own `develop` for the
  tactical-efficiency plan, the feature's first case. Resolve the tension in the RETAIN bullet: a
  plan that declares `branch:` has its pointer **cleared** at the closing merge (the plan stays live
  and findable; the release still archives it via `plan-backfill`), while a scalar-only plan keeps
  today's retention. Clear this repo's own pointer accordingly.
- **Depends on:** Chunk 01 (same resolution story; sequencing avoids doc churn)
- **Artifacts consumed:** `build-plan-tactical-efficiency.md` Chunk 06, `tactical-efficiency-analysis-2026-08-13.md` §F7
- **Deliverables:** `plugin/skills/pr/SKILL.md` (Step 1d + the Merge Flow "Confirm the bookkeeping merged WITH the PR" RETAIN bullets),
  `plugin/methodology/planning.md` plan-lifecycle paragraph, `.prawduct/project-state.yaml`
  (clear the pointer — the tactical plan declares its branch)
- **Tests:** the prose guards these files carry, updated only where the pinned sentence changed
- **Acceptance criteria:** on `develop` with the pointer cleared, resolution reports no active plan
  and the archive advisory is silent; on this branch, this plan still resolves by `branch:`; suite green
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Change-log entry added
  3. `/prawduct:critic` run and blocking findings resolved
  4. Committed and chunk marked `[x]` in Status

### Chunk 03: Pin what union-merge does with a twice-landed entry

- **Description:** **The prose defect this chunk was written to fix does not exist — the check
  disproved it, and the chunk is rescoped rather than dropped.** The concern was that union keeps
  *duplicate whole entries* when the same entry lands on both sides, a shape the probe's stated
  caveat does not mention. Constructed rather than asserted, in a throwaway repo carrying the
  attribute: an identical entry on both sides merges to **one** copy (the union driver unions
  conflicting hunks; identical hunks are not conflicting), and a *reworded* copy of one entry keeps
  both body lines **under a single header** — which is precisely the two-sided-edit-to-one-line case
  the caveat already states. The shipped caveat is complete.
  What is missing is not prose but a pin: the caveat is a claim about git's behavior and rests on a
  measurement nobody recorded. Add the two shapes to the probe's existing fixture test — that is
  this chunk's own severity rule applied to itself ("delete the claim, make it relational, or pin it
  with a test"), and it is the third of the three.
- **Depends on:** none
- **Artifacts consumed:** `tactical-efficiency-analysis-2026-08-13.md` §F6
- **Deliverables:** amended during the build, and the amendment is the chunk's actual finding.
  Planned: `tests/test_gitattributes_probes.py` only. **Shipped: also `plugin/lib/change_log.py`**
  (`ChangeLogEntry.unconsumed_tag_lines`, `_is_standalone_tag_line`, a
  `validate_change_log_tags` warning) and the probe's docstring — because writing the pin
  **falsified the caveat it was meant to pin**. Union concatenates whole *hunks*, so the second
  version of a two-sided tag-line edit lands past the entry's prose, where the head-of-body tag
  block has already stopped: it was metadata to nobody and no validator saw it, under a caveat
  asserting the release gate caught it. A pin cannot be written against a false claim, so the
  requirement grew a parent here rather than the code shipping without one — the shape is
  *the advice this framework prints into a user's repository must be true*, which is the same
  requirement Chunk 07 of the parent pass acted on when it tested union-merge before recommending it.
- **Tests:** the identical-entry shape (merges to one copy), the reworded-entry shape (both body
  lines, one header, and the stray now counted), both conditions of the detector with the corpus
  case that forces each, and the real 306-entry change log as its own fixture — alongside the
  existing no-attribute conflict control
- **Acceptance criteria:** the probe's stated caveat is pinned by a constructed merge rather than by
  a claim, and says only what the merge actually does; the detector fires on no real entry; suite green
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Change-log entry added
  3. `/prawduct:critic` run and blocking findings resolved
  4. Committed and chunk marked `[x]` in Status

### Chunk 04: Release notes and a develop-track dogfooding path for sibling repos

- **Description:** The tactical-efficiency pass has shipped to nobody: the plugin version is still
  3.3.4 and there are no release notes for it. Two deliverables. (1) **Release notes** for the pass
  — consumer-facing, covering the two surfaces a consumer will actually meet: the new ambient
  change-log union-merge advisory (what it is, that it is advice, how to make it stop) and the
  `branch:` opt-in (what it buys, that nothing migrates, and — post-Chunk 01 — that several plans may
  claim one branch). (2) **A dogfooding path that does not touch `main`:** sibling repos install
  from a `github` marketplace source pinned to `ref: main`; a second marketplace (`prawduct-dev`,
  same repo, `ref: develop`) declared in a sibling's **`.claude/settings.local.json`** — per-machine,
  uncommitted — puts that one repo on the develop track with nothing pushed to `main` and no other
  consumer affected. Verify the version-as-cache-key assumption at first install; if it holds,
  `develop` carries a prerelease version (e.g. `3.4.0-rc.1`) so the cache actually refreshes.
  Document the recipe where a maintainer will find it, and state how to get back off the track.
- **Depends on:** Chunks 01–03 (the notes describe their shipped state)
- **Artifacts consumed:** `documentation/release-process.md`,
  `.prawduct/runbooks/cut-and-publish-a-plugin-release.md`
- **Deliverables:** amended during the build. Planned: an entry in `.prawduct/release-notes.md`.
  **Not written, deliberately** — that file is a FROZEN ARCHIVE of a derived view retired at
  v3.2.7, and it says so in its own header; adding an entry would revive the thing that was
  retired. The consumer-facing surface is `plugin/CHANGELOG.md` (a `## vX.Y.Z` section) plus
  `README.md` § Recent Changes on a minor bump, published as a GitHub Release from that section.
  Shipped: those two, the dogfooding recipe and its lifecycle in `documentation/release-process.md`,
  the prerelease bump in all three version files, and — not planned — prerelease support in
  `banner.version_tuple` and the two version checks that rejected it.
- **Tests:** the prerelease ordering and its banner consequence, which were not planned either:
  the bump is a version *string*, but three checks read that string and all three refused it
- **Acceptance criteria:** one sibling repo is actually running the develop track and its session
  briefing reports the new version; `main` is untouched; the way back off the track is written down.
  <!-- Amended 2026-08-13 during the build: the live half CANNOT be met from this branch. The
       marketplace source is `{source: github, ref: develop}`, so a sibling repo fetches develop from
       GitHub — this work has to be merged and pushed there before any install can see it. Stated
       rather than quietly satisfied by installing from a local path, which would verify a different
       recipe than the one documented. The doc half (CHANGELOG, README, version bump, the recipe and
       the way back off it) is complete; the chunk stays UNTICKED until a sibling repo has actually
       run a session on the track. -->
- **DESCOPED 2026-08-27 — the prerelease half was superseded on `develop`, owner decision at the
  base sync.** While this branch sat unmerged (251 commits of drift), `develop` shipped its own
  develop track with a deliberately NARROWER rule: `-dev` / `-dev.N` is the only permitted
  prerelease form, asserted by `test_version_tuple_refuses_an_unpermitted_prerelease`, which
  requires `3.4.0-rc.1` to NOT parse so that the banner and the manifest guard keep answering the
  same question about what a legal version is. This chunk's general-semver parser and its
  `3.4.0-rc.1` bump are the thing that test refuses. Adopting them would have meant deleting a test
  written on purpose, so the base sync resolved every version-carrying file — `plugin/VERSION`,
  `plugin.json`, `pyproject.toml`, `banner.version_tuple`, and both version test files — in
  `develop`'s favour, and this chunk's In-build discovery below is superseded rather than shipped.
  What survived and is DONE: the release notes (the `branch:` opt-in and the union-merge advisory,
  written into the OPEN `## v3.4.1-dev.2` section, not the shipped `## v3.4.0`, because this work
  is still release-pending) and the dogfooding recipe, both restated in `-dev.N` terms — the recipe
  had been instructing maintainers to set a version the merged code now rejects, and the runbook's
  changelog note had been asserting the open section is written under the final number when
  `develop`'s step 10 opens it under the prerelease heading and renames it at the cut.
  **A release-candidate stage now does not exist in any form**; wanting one is a fresh item designed
  against the `-dev` rule rather than against it, not a resurrection of this chunk.

- **In-build discovery — the repo's own tooling rejected the prerelease.** The version-as-cache-key
  assumption held, and its consequence did not: `plugin.json`'s semver check demanded exactly three
  numeric parts, the changelog check demanded a section named for the exact running version, and
  `banner.version_tuple` parsed any suffix as "older than everything" — so a dogfooding repo would
  have got no banner at all and the next real release would have replayed every headline in the
  file. All three now understand a prerelease: it sorts below its own release (semver), and a
  prerelease is satisfied by the changelog section of the release it is a prerelease OF, so an rc
  bump does not owe a changelog edit for a version nobody will ship.
- **Type:** cumulative-final
  <!-- Last chunk: its review IS the one `/prawduct:critic cumulative` over the branch. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Change-log entry added
  3. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  4. Chunk marked `[x]` in Status

## Early Feedback Milestone

**Milestone chunk:** 01
**What the user can do:** check out a branch carrying two plans and watch governance resolve one,
name it, and name the other — instead of refusing to end the session.

## Governance Checkpoints

**Commit & PR cadence:** feature branch `fix/branch-claim-multiplicity` off `develop`; commit per
chunk after its Critic review passes. Chunk 04's cumulative makes the branch PR-ready.

- After Chunk 01 (`final` review): confirm the precedence is stated once, that attribution reaches
  every surface that resolves a plan, and that no path can still refuse a session to death.
- After Chunk 04 (cumulative): full-bundle review, then the live sibling-repo install is the
  acceptance evidence — not a claim that the recipe would work.
