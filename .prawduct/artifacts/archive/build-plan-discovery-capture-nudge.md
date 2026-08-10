---
artifact: build-plan
version: 2
scope: discovery-capture-nudge
depends_on: []
last_validated: null
lifecycle: completed
archived: 2026-08-10
released_in: v2.0.10
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

## Requirements Confidence

**Level:** High

**Why:** The problem, success, and scope are each statable in one sentence and the root
cause is verified in code. **Problem:** a product onboarded via `/prawduct:onboard` and then
worked on docs-first (or as an existing codebase) accumulates rich product-definition work
while `project-state.yaml` stays template-default, and prawduct never nudges — because the
*only* "you haven't done discovery" signal (`bin/prawduct-hook` `cmd_clear`, the unfilled-
`project-preferences` CRITICAL) is gated on `has_code`, so a no-code-yet discovery/arch phase
is silent by construction (verified at `bin/prawduct-hook:1937`; the detection also has zero
direct tests). **Success:** when discovery is uncaptured but the repo shows product-definition
work (code and/or `docs/` markdown), the session briefing emits a routing nudge to
`/prawduct:discovery`, and `/prawduct:discovery` has a documented reconciliation mode for the
docs-first / brownfield entry path; a truly fresh onboarded repo (no code, no docs) stays
silent. **Out of scope:** changing the existing `has_code`-gated `project-preferences` CRITICAL
(preferences are correctly a code-time concern — kept as-is); auto-editing `project-state.yaml`
(discovery/doctor stay read-and-guide); reconciling Scriob itself (its own session owns that).

**Open assumptions / unknowns:**
- [ASSUMPTION: "product-definition work exists" = source code OR any `*.md` under `docs/` | MED impact | user can correct/override/defer] — chosen to be general (not Scriob-specific) while staying quiet on a freshly-onboarded repo (`init-product` creates neither code nor `docs/`). The conjunction with "discovery uncaptured" keeps false-positives low.
- [ASSUMPTION: the nudge is briefing-prominent but advisory in tone (routes, does not hard-block the turn) | LOW impact | user can correct/override/defer] — a docs-first user may be mid-requirements; a hard "do this NOW" CRITICAL every session would be noise. It routes; the agent uses judgment.

**What would raise confidence:** N/A (High).

## Status

- [x] Chunk 01: Detect uncaptured discovery and route to /prawduct:discovery (code + tests)
- [x] Chunk 02: Route onboarding to discovery + reconciliation methodology (doc-only)
Context: Fixes the framework gap surfaced by ../Scriob (onboarded, worked docs-first, project-state stayed empty, prawduct never adapted). **BOTH CHUNKS DONE — branch ready for PR (waiting on owner).** Chunk 01 (945b006, `chunk` Critic 0 findings): detection spine in `cmd_clear` — `_has_product_code`/`_has_product_definition_work`/`_discovery_uncaptured` helpers + the "DISCOVERY NOT CAPTURED" nudge; 17 tests; validated against a real `init-product` scaffold AND live Scriob (now reconciled → correctly silent). Chunk 02 (d3de33b): onboard→discovery routing + the "Reconciling an Existing or Docs-First Product" methodology section + discovery/doctor skill pointers + cross-cutting row. Hardening pass (fdba557, owner asked for "won't happen again" confidence): pinned the template→detector contract (TestTemplateContract — guards BLD-7P3K-class silent rot) and broadened doc roots to docs/ + documentation/. Cumulative Critic (whole branch, re-run at HEAD): 0 blocking / 0 warning / 1 note (BLD-2R9X, already filed). 832 tests green; /pr gate satisfied. Checkboxes are a derived view — flipped at release via regen-views.

## Build Chunks

### Chunk 01: Detect uncaptured discovery and route to /prawduct:discovery

- **Description:** Add a detection block to `cmd_clear` (the session-start briefing) that fires when discovery is uncaptured (`project-state.yaml` still carries both template sentinels `  domain: null` and `  vision: null`) AND the repo shows product-definition work (source code OR markdown under `docs/`). It prints a prominent routing nudge to stdout pointing at `/prawduct:discovery` and naming the reconciliation path for repos that already have docs/code. A freshly-onboarded repo (uncaptured but no code and no docs) stays silent. Extract the inline `has_code` computation (currently buried in the prefs block) into a shared helper so the new check and the existing prefs CRITICAL reuse one definition (Goal 7 — no duplication). The existing `has_code`-gated prefs CRITICAL is left behaviorally unchanged.
- **Depends on:** none
- **Deliverables:**
  - `bin/prawduct-hook` — `cmd_clear` gains the discovery-uncaptured detection + nudge; `has_code` extracted to a module-level helper (e.g. `_has_product_code`) and a new `_has_product_definition_work` helper.
  - new `tests/test_discovery_capture_nudge.py` — first direct tests for this detection family.
- **Tests:**
  - uncaptured + a markdown file under docs/requirements/ present → nudge fires, names `/prawduct:discovery`.
  - uncaptured + source code present (brownfield) → nudge fires.
  - uncaptured + no code and no docs (fresh onboard) → NO nudge.
  - captured (`domain`/`vision` filled) + docs present → NO nudge.
  - the refactored `_has_product_code` helper: detects `.py`, ignores `.prawduct/` and framework tooling (lock the refactor so the prefs path is safe).
- **Acceptance criteria:** `python3 -m pytest -q` green (813→ +new tests); the four scenarios above behave as specified; no behavior change to the existing prefs CRITICAL (a test pins it still fires on code-without-prefs and not on no-code).
- **Type:** code
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` (infers `chunk`) run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: Route onboarding to discovery + reconciliation methodology

- **Description:** Close the "onboard ≠ discovery" seam and give `/prawduct:discovery` a documented reconciliation mode, so the Chunk 01 nudge routes somewhere real. Surfaces (enumerated up front per planning.md's cascade rule):
  - `skills/onboard/SKILL.md` — the onboard flow ends by routing to `/prawduct:discovery` as the first product-session step (new repo → capture; existing docs/code → reconcile).
  - `methodology/discovery.md` — new section "Reconciling an Existing or Docs-First Product": when product-definition work already exists (requirements/arch/vision docs or an existing codebase) but `project-state.yaml` is template-default, discovery *reconciles* — read those sources, backfill classification + structural characteristics + product definition, and set `open_questions` to reference the canonical docs rather than duplicate them; keep `docs/` as the detailed source.
  - `skills/discovery/SKILL.md` — one-line pointer so the skill names both the greenfield and reconcile entry paths.
  - `skills/doctor/SKILL.md` — add a "discovery captured" health-check bullet (doctor reads-and-guides; routes to `/prawduct:discovery` when uncaptured-with-product-work).
  - `.prawduct/cross-cutting-concerns.md` — extend the "Requirements clarity" row (or add a "Discovery capture" row) to record the new pipeline coverage (Discovery: reconciliation section; Builder: briefing nudge).
- **Depends on:** Chunk 01 (the nudge text references the reconciliation behavior this chunk documents)
- **Deliverables:** the five files above.
- **Tests:** doc-only; no new pytest. A coherence check that the nudge string in `bin/prawduct-hook` and the routing target (`/prawduct:discovery`) are consistent is covered by the Critic's Goal 4 rather than a unit test (greppy assertion on prose would be a false-confidence test — see project-preferences Enforcement guardrail).
- **Acceptance criteria:** the reconciliation section reads coherently with the rest of `discovery.md`; onboard routes to discovery; the cross-cutting registry reflects reality; full suite still green.
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met and tests pass (suite still green; no test changes expected)
  2. `/prawduct:critic` run and blocking findings resolved
  3. `/prawduct:critic cumulative` run against `merge-base...HEAD` (covers Chunk 01 code + Chunk 02 docs together — the `/pr create` gate) and blocking findings resolved
  4. Committed and chunk marked `[x]` in Status

## Governance Checkpoints

**Commit & PR cadence:** Commit per chunk after its `/prawduct:critic` passes. After Chunk 02, run `/prawduct:critic cumulative` over the whole branch as the integration review and `/pr create` gate. PR creation waits for the owner (`PR creation: wait_for_user`).

- After Chunk 01: `chunk` review — detection logic + test coverage are the correctness-critical piece.
- After Chunk 02: `cumulative` review — coherence across the code nudge and the methodology it routes to is a cross-file property the per-chunk lens can't see.
