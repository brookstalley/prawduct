---
artifact: build-plan
version: 2
scope: purpose-and-cession
depends_on: []
governed_by:
  # Seeded via `prawduct-hook jurisdiction` 2026-08-13; curated to the one artifact
  # whose Direction norms actually reach a prose-only cycle.
  - artifact: architecture
    dispositions:
      - "every fact has one home → conforms — purpose.md becomes the single home for the framework's purpose; the six artifact-frontmatter 'vision lives in README.md + CLAUDE.md' comments and CLAUDE.md's opening line become references to it, and purpose.md restates no fact another file owns (principles stay in principles.md)"
      - "guides, never implements → conforms — prose-only cycle, no product code or tooling"
      - "goals and verification bind; prescribed method is advice → conforms — this plan's Deliverables read as advisory per the norm"
      - "an independent reviewer never mutates the session it reviews → inapplicable because this cycle changes no reviewer or mutation site"
      - "authority fails closed; advice fails soft → inapplicable because this cycle produces no gate or verdict code"
      - "local-first governance coordination → inapplicable because this cycle adds no network, daemon, or dependency"
      - "the plugin writes nothing into a governed repo except its own state and reconciled seams → inapplicable because no plugin writer changes; the CLAUDE.md edited here is prawduct-the-product's own file"
      - "prawduct is written in Python and must never be specific to Python → inapplicable because this cycle ships prose and test-contract updates only"
last_validated: 2026-08-13
lifecycle: completed
archived: 2026-08-20
released_in: v3.4.0
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

## Requirements Confidence

**Level:** High

**Why:** The problem (prawduct has no recorded purpose; the graceful-cession posture exists only in one conversation), success criteria (purpose.md on disk carrying the owner's ratified framing; principles #25/#26 landed with their cascade coherent), and scope (documents and their pinning contracts only — no mechanism, no gates, no ledger yet) were each confirmed directly with the owner on 2026-08-12. Source material is the ratified program plan, now durably recorded in `.prawduct/artifacts/program-purpose-and-cession.md` (it was carried in the gitignored `.prawduct/.handoff-notes.md` while this plan was authored) — no fast-moving external facts.

**Open assumptions / unknowns:**
- [ASSUMPTION: `purpose.md` lives in `documentation/` (framework-internal), not `plugin/docs/` (shipped to products) — it is prawduct's own north star, not consumer guidance | MED impact | user can override]
- [ASSUMPTION: principle names are "Third Rework Is a Deletion Signal" (#25) and "Graceful Cession" (#26) | LOW impact | user can rename at review]
- [ASSUMPTION: CLAUDE.md roster additions are paid by trims inside CLAUDE.md so it holds its ~150-line target | LOW impact]

**What would raise confidence:** N/A

## Status

- [x] Chunk 01: documentation/purpose.md — the framework's own north star
- [x] Chunk 02: Principles 25 and 26 with their cascade
Context: Plan authored 2026-08-13 from the ratified program, now recorded in `.prawduct/artifacts/program-purpose-and-cession.md` (owner approved 2026-08-12). This is Cycle 1 of a four-cycle program; Cycle 2 is backlog #181 (GOV-6D4Q), the deletion-only pass — this plan deliberately precedes it so the pass's "why" is on disk first. BOTH CHUNKS COMPLETE 2026-08-13: suite green, evidence recorded. Review history: cumulative rev-20260813T042938Z-81decaea (1 blocking — the ride-along early plan archive, reverted; 4 warnings; 1 note → #302/MET-9W2P shipped, Principle 25 IS that item) then verify-resolutions rev-20260813T044600Z-78bedb91 (all resolved, 0/0/0). Branch `docs/purpose-and-cession` is PR-ready; owner runs `/prawduct:pr` next session, then Cycle 2 (#181).

## Verification Strategy

Prose deliverables: verification is coherence, not execution. Each chunk closes by (a) re-reading the changed docs end-to-end against the ratified framing (`.prawduct/artifacts/program-purpose-and-cession.md`), (b) running the full test suite (the roster and budget pins are the executable contract), and (c) Critic review per chunk. No product to launch.

## Build Chunks

### Chunk 01: documentation/purpose.md — the framework's own north star

- **Description:** Create the purpose document prawduct has never had (verified 2026-08-12: nothing vision/purpose-shaped ever existed in git history). Spine is the owner's framing, user-needs not model-timelines: prawduct builds on today's models and runtimes to close the gap between what they provide and what consumers need to deliver successful software products; models are commodities, consumers differentiate above the mass-market baseline, and prawduct supplies that layer permanently — ceding what the baseline absorbs and moving its value higher. Body carries: why the gap never closes (requirements arrive late — human nature, not tooling immaturity); the three-hedge taxonomy (runtime judgment / joint myopia / statelessness) with their distinct depreciation schedules; the durable core (mandate + record + audit); fractional shifting ownership with the false-precision caveat (continuous evolution, not step functions); deletion with the same care as addition; and the directional-by-construction telemetry rule (schemas physically incapable of carrying proprietary information). ~One page.
- **Depends on:** none
- **Artifacts consumed:** `.prawduct/artifacts/program-purpose-and-cession.md` (ratified program + owner refinements)
- **Deliverables:** new `documentation/purpose.md`; the six artifact-frontmatter comments currently reading "vision lives in README.md + CLAUDE.md" (`architecture.md`, `data-model.md`, `api-contract.md`, `observability-strategy.md`, `nonfunctional-requirements.md`, `security-model.md` under `.prawduct/artifacts/`) repointed to `documentation/purpose.md` — one-home cascade, the relocated parent's old pointers must not survive
- **Tests:** none new — no contract surface changes in this chunk
- **Acceptance criteria:** doc exists, ≤ ~120 lines, carries every element listed in the description, contradicts nothing in `CLAUDE.md` or `plugin/docs/principles.md`; full suite still green
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met, suite green
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: Principles 25 and 26 with their cascade

- **Description:** Amend `plugin/docs/principles.md` (per Principle 19) with **#25 Third Rework Is a Deletion Signal** (proposed by the 2026-07-02 efficiency review, never adopted; now supported by four recorded cases) and **#26 Graceful Cession** (every mechanism carries the assumption that justifies it; a runtime or harness change that breaks the assumption forces a re-price — cede downward or move up an abstraction level). Enumerated cascade surfaces (planning.md "Enumerate the surfaces"): `plugin/docs/principles.md` (new `### 25.` / `### 26.` sections in the established format); `tests/test_v5_methodology.py::TestPrinciplesDoc` (PRINCIPLES roster + the exactly-24 count → 26 — a contract updated *with* its requirement, not weakened); `CLAUDE.md` (two roster lines under Learning/Judgment + one pointer line to `documentation/purpose.md`, paid by in-file trims to hold ~150 lines); `plugin/methodology/session-digest.md` and `-slim.md` (verify only — expected outcome is no edit, since the full digest is at 10,138 chars against a 10,000-char spill limit and must not grow; if the digest turns out to enumerate principles, the fix is a pointer, not an enumeration).
- **Depends on:** Chunk 01
- **Artifacts consumed:** `documentation/purpose.md` (the principles must be derivable from it), `plugin/docs/principles.md` §24 (format to match)
- **Deliverables:** amended `plugin/docs/principles.md`, updated `tests/test_v5_methodology.py` roster, amended `CLAUDE.md` (roster + pointer, net ≤ 150 lines)
- **Tests:** updated roster/count contract in `TestPrinciplesDoc`; full suite green including every budget pin
- **Acceptance criteria:** `### 25.` and `### 26.` present in principles.md matching house format; roster test asserts 1..26; CLAUDE.md ≤ 150 lines with both roster lines and the purpose.md pointer; digests unchanged or pointer-only; suite green
  - *Reconciled at build (goals-bind norm — better route, recorded):* the full digest already enumerates the roster by group, so "unchanged or pointer-only" would have left it FALSE against principles.md — the one incoherence this plan exists to avoid. The Evolution roster line was added instead, paid in-file (net −2 chars); the slim digest carries no roster and is untouched, exactly as the AC anticipated.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met, suite green
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status

## Early Feedback Milestone

**Milestone chunk:** 01
**What the user can do:** read `documentation/purpose.md` and veto the framing before the principles derive from it.

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk after its review passes. Chunk 02's cumulative review makes the branch PR-ready; `/prawduct:pr` runs when the owner asks. Merge as a true merge commit (repo default).

- After Chunk 01: owner-readable purpose.md exists — the framing is vetoable before Chunk 02 derives principles from it.
- After Chunk 02 (cumulative): full-bundle coherence — purpose.md, principles, CLAUDE.md, and handoff notes tell one story.
