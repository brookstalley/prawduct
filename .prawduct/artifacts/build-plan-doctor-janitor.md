<!-- Build Plan — doctor↔janitor scope boundary (GOV-9K2T)
     Tier: 1 (Source of Truth). For HOW to build, read /prawduct:building.
-->
---
artifact: build-plan
version: 2
scope: doctor-janitor
depends_on: []
last_validated: null
---

## Requirements Confidence

**Level:** High

**Why:** The research (this session) audited all 9 doctor Health-Check items against all
10 janitor themes; the responsibility split, the two real overlaps (API versioning, gitignore),
and the deliverable shape are each statable in one sentence. The user confirmed the build shape
(canonical doc + mirrored summaries in each skill + the gitignore cross-reference).

**Open assumptions / unknowns:**
- [ASSUMPTION: the canonical doc lives at `docs/doctor-vs-janitor.md` (plugin-shipped, reachable from product repos via `${CLAUDE_SKILL_DIR}/../../docs/`, like `docs/principles.md`) | LOW impact | user can correct]
- [ASSUMPTION: add a one-line doctor+janitor entry to the methodology index (`skills/methodology/SKILL.md`) overview, which today names critic/pr/learnings/backlog but not the two maintenance/health skills | LOW impact | user can drop]

**What would raise confidence:** N/A (High).

## Status

<!-- Derived view (views_enabled: true): checkboxes regen from change-log status=shipped
     tags via regen-views. Do NOT hand-edit — add a tagged change-log entry instead. -->

- [ ] Chunk 01: doctor↔janitor boundary — canonical doc + mirrored skill summaries + gitignore cross-ref + guard test
Context: Sole chunk. Ships as one PR (Type: cumulative-final → the chunk review IS the cumulative gate). Closes GOV-9K2T.

### Chunk 01: doctor↔janitor boundary

- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria below met and full test suite passes (`pytest tests/`).
  2. `/prawduct:critic cumulative` run (the single review for this one-chunk PR) and blocking findings resolved.
  3. Statusless change-log entry added (`scope=doctor-janitor`); committed.

#### Deliverables

1. **NEW `docs/doctor-vs-janitor.md`** — the canonical reference (single source of truth):
   - The three-axis distinction: **subject** (prawduct scaffolding & recorded decisions vs. the
     product's own code/docs/tests/deps), **action model** (report-and-guide vs. survey-and-fix),
     **question type** (conformance vs. craft). Plus the softer cadence axis.
   - The **placement rule** for a new concern (doctor if governance-conformance / a required
     decision is recorded·present·correct; janitor if the product's own craft is well-built·current;
     **both** only when a concern has both facets — each skill owns its facet and cross-references).
   - The **"legitimately both"** pattern with the two worked examples: API versioning (doctor #9
     "decision recorded?" vs. janitor theme "designed to evolve well?") and gitignore (doctor #8
     "prawduct contract" vs. janitor VCS "general hygiene").
   - The **adjacencies** that are handoffs, not overlaps: Template Currency, backlog (external files
     vs. the prawduct backlog's own health).

2. **`skills/doctor/SKILL.md`** — add a short `## Scope & boundary` block near the top (after the
   intro paragraph, before Context Detection): doctor = prawduct governance/install conformance,
   report-and-guide; for the product's own codebase craft → janitor; one-line pointer to the
   canonical doc. **Also** add a gitignore cross-reference to Health-Check #8 (the prawduct *contract*
   facet; general gitignore hygiene → janitor VCS).

3. **`skills/janitor/SKILL.md`** — mirrored `## Scope & boundary` block near the top (after "The
   Janitor's Perspective"): janitor = the product's own code/docs/tests/deps craft, survey-and-fix;
   for prawduct governance/install health → doctor; pointer to the canonical doc. **Also** add a
   gitignore cross-reference to the Version Control Hygiene theme (general hygiene here; the prawduct
   gitignore *contract* → doctor #8).

4. **`skills/methodology/SKILL.md`** — add a one-line doctor+janitor entry to the overview map (the
   two maintenance/health skills are currently absent from it), pointing to the canonical doc for the
   split. Keep minimal.

5. **NEW `tests/test_doctor_janitor_boundary.py`** — structural guard locking the three-place
   coherence the "canonical + mirror" shape introduces:
   - `docs/doctor-vs-janitor.md` exists and names both skills + the placement rule.
   - Both `skills/doctor/SKILL.md` and `skills/janitor/SKILL.md` contain a `Scope & boundary` heading
     and a pointer to the canonical doc.
   - Both skills carry the gitignore cross-reference (doctor #8 ↔ janitor VCS).

#### Acceptance criteria

- A maintainer reading either skill learns, in ≤5 lines, what that skill owns and what routes to the
  other, with a pointer to the full rule.
- The canonical doc answers "which skill does a new concern belong to?" deterministically, including
  the "legitimately both" case.
- The two real overlaps (API versioning, gitignore) are each cross-referenced in both directions.
- New guard test passes; full suite stays green (no regression in the janitor Template-Currency or
  slash-command-reference guards).

#### Surfaces touched (cascade enumerated up front)

`docs/doctor-vs-janitor.md` (new) · `skills/doctor/SKILL.md` · `skills/janitor/SKILL.md` ·
`skills/methodology/SKILL.md` · `tests/test_doctor_janitor_boundary.py` (new) ·
`.prawduct/change-log.md` (statusless entry) · `.prawduct/project-state.yaml` (`active_build_plan`
repoint) · `.prawduct/backlog.md` (GOV-9K2T open→promoted→shipped via `/prawduct:backlog`).

No token-budget guardrail tests bound these surfaces (test_v5_methodology budgets cover building.md
and the Critic SKILL.md only — neither touched).

#### Out of scope

- No change to *what* doctor or janitor check (no checks added/removed/moved) — this clarifies the
  boundary, it doesn't redraw coverage. The API check stays in both, facets delineated.
- The coded auto-detect Exposed-API trigger (`CRT-4Q7K`) and standalone error-model artifact
  (`TPL-8H3M`) are separate backlog items.
