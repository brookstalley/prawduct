<!-- Build Plan Template — Tier 1 (Source of Truth)

     A FILLED EXAMPLE: a small household grocery-list web app ("Pantry"). Replace the
     content; keep the field labels exactly as written (`**Title Case:**`). The plan
     defines WHAT to build — for HOW, read `/prawduct:methodology building` first. A plan is
     specific enough when the builder never has to make a technology decision.
-->
---
artifact: build-plan
version: 2
# scope: change-log scope tag (with `views_enabled`, regen-views flips Status
# checkboxes from entries matching it). Use your in-flight chunks' tag; null is fine
# for single-version products.
scope: pantry-v1
depends_on:
  - artifact: product-brief
  - artifact: data-model
  - artifact: test-specifications
  - artifact: dependency-manifest
  - artifact: operational-spec
governed_by:
  # Governing artifacts whose `## Direction` norms bind this plan. Seed with
  # `prawduct-hook jurisdiction`; omit when the product has declared no norms.
  # Each entry records one disposition line PER NORM in that artifact (`docs/norms.md`):
  # conforms | ruling needed | exception | amendment proposed | inapplicable because X.
  - artifact: data-model
    dispositions:
      - "all timestamps UTC ISO-8601 → conforms"
      - "money as integer minor units → inapplicable because this plan touches no money fields"
last_validated: 2026-07-03
---

## Requirements Confidence

<!-- Honest self-assessment (Principle 6). High: problem, success, and scope each
     statable in one sentence. Medium: assumptions inferred — list them. Low: unknowns
     named + what would resolve them. Not a gate; committing to a level forces honesty. -->

**Level:** High

**Why:** Problem, success criteria, and scope were confirmed with the user in one discovery round; no fast-moving or post-cutoff dependencies.

**Open assumptions / unknowns:** [ASSUMPTION: single household, no auth beyond a shared device | MED impact | user can override]

**What would raise confidence:** N/A

## Status

<!-- The cross-session handoff. Mark `[x]` when a chunk's "Done when" steps are all
     satisfied; keep Context current. When `views_enabled`, checkboxes regenerate from
     tagged change-log entries — update the tag, don't hand-flip. -->

- [ ] Chunk 01: Walking skeleton — list page backed by SQLite
- [ ] Chunk 02: Add and check off items, grouped by store section
- [ ] Chunk 03: Barcode lookup via OpenFoodFacts
Context: Plan approved 2026-07-03; nothing built yet. Next: Chunk 01.

## Scaffolding

### Project Initialization

`uv init pantry && cd pantry && uv add fastapi uvicorn jinja2 && uv add --dev pytest httpx`

### Dependencies

fastapi (routing), uvicorn (server), jinja2 (templates), sqlite3 (stdlib storage); dev: pytest, httpx (test client). Rationale per package in `dependency-manifest.md`.

### Build & Test Configuration

Single `tests/` directory (low-risk product); `uv run pytest -q` runs everything. Coverage measured with `--cov=pantry`, no threshold enforced.

### Scaffold Verification

`uv run uvicorn pantry.main:app` serves a placeholder page at :8000; `uv run pytest -q` passes with the smoke test.

### Verification Strategy

<!-- How the builder confirms each chunk works beyond tests, as users would experience
     it. Scale to complexity; verification infrastructure is dev-only (Principle 10). -->

Run the server and click through the core flow (add item → see it listed → check it off) after each chunk. Chunk 03 additionally probes the live OpenFoodFacts API before any client code is written.

## Project Structure

```
pantry/
├── pantry/            # app package: main.py (routes), store.py (SQLite access)
├── templates/         # Jinja2 pages
└── tests/
```

### Module Boundaries

Routes never touch SQLite directly — persistence goes through `store.py`. Templates render data passed by routes; no logic in templates.

## Build Chunks

<!-- Chunks are vertical slices, dependency-ordered, each reviewable in one Critic pass;
     Chunk 01 is a thin slice through every layer. The Critic existence-checks backticked
     paths in the current chunk's section — prefix paths the chunk CREATES with "new".

     Optional fields are declared only when they apply — missing is always the safe
     default. Field reference:
       `Critic mode:` / `Type:` — methodology/planning.md "Critic Mode Per Chunk" /
         "Choosing a Chunk Type"; behavior tables in skills/critic/review-cycle.md.
         Mode missing, unrecognized, or inference unconfident → the review runs `final`.
       `Foreign API:` / `Exposed API:` / `Visual change:` — methodology/planning.md.
       `Trivial because:` — required iff `Type: trivial`. -->

### Chunk 01: Walking skeleton — list page backed by SQLite

- **Description:** Prove the path: one page renders grocery items from SQLite. Layers connect end-to-end before any feature widens.
- **Depends on:** none
- **Artifacts consumed:** `data-model.md` (Item entity), `test-specifications.md` §1
- **Deliverables:** new `pantry/main.py`, new `pantry/store.py`, new `templates/list.html`, seeded dev database
- **Tests:** unit — `store.py` CRUD; integration — GET / renders seeded items (httpx)
- **Acceptance criteria:** `uv run pytest -q` passes; browser shows the seeded list at /
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: Add and check off items, grouped by store section

- **Description:** The daily flow: add an item with a store section, check it off, checked items archive. Lands the item state machine the app depends on.
- **Depends on:** Chunk 01
- **Artifacts consumed:** `product-brief.md` core flow 1, `test-specifications.md` §2
- **Deliverables:** POST routes in `pantry/main.py`, state transitions in `pantry/store.py` (open → checked → archived), form UI in `templates/list.html`
- **Tests:** unit — state transitions including double-check-off; integration — full add → check → archive cycle (one step beyond the immediate post-state)
- **Acceptance criteria:** user can add an item and see it under its section; checking it moves it to "done" without error
- **Critic mode:** final
  <!-- Override: inference would pick `chunk` mid-plan, but this chunk lands the
       state-machine keystone — worth the full review now. -->
- **Visual change:** yes — form layout and section grouping need a human look before merge
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: Barcode lookup via OpenFoodFacts

- **Description:** Enter a barcode → prefill the item name from OpenFoodFacts, with graceful manual fallback when the API is unreachable.
- **Depends on:** Chunk 02
- **Artifacts consumed:** `dependency-manifest.md` (OpenFoodFacts entry)
- **Deliverables:** `pantry/lookup.py` client with offline fallback, lookup route + UI field
- **Tests:** unit — response parsing against the captured real shape; integration — lookup route with the client faked (fake built after verify-api, never before)
- **Acceptance criteria:** a known barcode prefills the name; API down → the form still works manually
- **Type:** cumulative-final
  <!-- Last chunk: its review IS the one `/prawduct:critic cumulative` — commit
       first, run it once, no separate `final`. -->
- **Foreign API:** openfoodfacts-http
- **Done when:**
  0. verify-api — probe the live API for two barcodes; capture the actual response shape in `.prawduct/artifacts/api-notes-off.md`
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status

<!-- Rarely-used optional fields, shown once for syntax:
- **Type:** trivial
- **Trivial because:** project-wide rename of ListItem to Item; no behavior change
- **Exposed API:** pantry-http-api   (requires recorded versioning + error-model decisions)
-->

## Early Feedback Milestone

<!-- The first chunk where the user can interact with the product — chunk 3 at latest
     for most products. -->

**Milestone chunk:** 01
**What the user can do:** open the list page and see real items from the database.

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk after its Critic review passes (per-chunk commit is what scopes `chunk`-mode reviews). The last chunk's `cumulative` review makes the branch PR-ready — `/prawduct:pr create` is gated on it and runs when the user asks for a PR.

- After chunk 01: confirm the architecture (routes → store → SQLite) before widening.
- After chunk 03 (cumulative): full-bundle review; verify the offline fallback has real coverage.
