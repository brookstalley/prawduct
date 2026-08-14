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

- [ ] Chunk 01: Several plans may claim one branch — resolve and attribute, never refuse
- [ ] Chunk 02: A branch-declaring plan retires by archiving alone — no pointer left to ignore
- [ ] Chunk 03: Pin what union-merge does with a twice-landed entry
- [ ] Chunk 04: Release notes and a develop-track dogfooding path for sibling repos

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
- **Deliverables:** `plugin/skills/pr/SKILL.md` (Step 1d + merge-flow step 7 RETAIN bullets),
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
- **Deliverables:** `tests/test_gitattributes_probes.py` only — no prose change; the docstring
  already says what git does
- **Tests:** the identical-entry shape (merges to one copy) and the reworded-entry shape (both body
  lines, one header), alongside the existing no-attribute conflict control
- **Acceptance criteria:** the probe's stated caveat is pinned by a constructed merge rather than by
  a claim; suite green
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
- **Artifacts consumed:** `.prawduct/release-notes.md`, `documentation/release-process.md`
- **Deliverables:** `.prawduct/release-notes.md` entry; the dogfooding recipe in
  `documentation/` (release process or a sibling doc); a prerelease version bump on `develop` if the
  cache-key assumption holds
- **Tests:** none beyond the suite — this is documentation plus a version string; the recipe's
  verification is the live install below
- **Acceptance criteria:** one sibling repo is actually running the develop track and its session
  briefing reports the new version; `main` is untouched; the way back off the track is written down
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
