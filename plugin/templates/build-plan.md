<!-- Build Plan Template

     A FILLED EXAMPLE: a small household grocery-list web app ("Pantry"). Replace the
     content; keep the field labels exactly as written (`**Title Case:**`). The plan
     defines WHAT to build — for HOW, read `/prawduct:methodology building` first. A plan is
     specific enough when the builder never has to make a technology decision.
-->
---
artifact: build-plan
version: 2
# scope: change-log scope tag. The release gate pairs this plan with the change-log
# entries carrying the same `scope=`. Use your in-flight chunks' tag; null is fine
# for single-version products.
scope: pantry-v1
# branch: the branch this plan governs — uncomment with your real branch (a
# placeholder names a branch no repo has). While it is checked out, governance
# resolves this plan ahead of active_build_plan; several plans may declare one
# branch (precedence: methodology/planning.md "Which plan is active is branch state").
# branch: feature/pantry-v1
depends_on:
  - artifact: product-brief
  - artifact: data-model
  - artifact: test-specifications
  - artifact: dependency-manifest
  - artifact: operational-spec
governed_by:
  # Governing artifacts whose `## Direction` norms bind this plan. Seed with
  # `prawduct-hook jurisdiction`; omit when the product has declared no norms.
  # Each entry records one disposition line PER NORM in that artifact (`/prawduct:methodology norms`):
  # conforms | ruling needed | exception | amendment proposed | inapplicable because X.
  - artifact: data-model
    dispositions:
      - "all timestamps UTC ISO-8601 → conforms"
      - "money as integer minor units → inapplicable because this plan touches no money fields"
# partition: who builds each chunk, recorded either way — one line, and
# "serial, because X" is an answer. Drawn when the chunk boundaries are drawn
# (methodology/planning.md "Partition: Serial or Delegated"), because that is
# the last moment the whole partition is visible before any brief exists. What
# the field catches is not serial work but UNEXAMINED work: independent chunks
# and no line here is the `serial by default` anti-pattern.
partition: serial — each chunk builds on the last, and 03 extends 02's routes
last_validated: 2026-07-03
# End of life — written by prawduct-hook archive-plan, never by hand; a plan is
# archived, not deleted:
#   lifecycle: completed | superseded · archived: YYYY-MM-DD · released_in: vX.Y.Z
#     (not release:, which a release plan uses for the release it governs)
#   superseded_by: <what replaced it, or why it stopped>   (superseded only)
#   unbuilt_at_archive: <unticked chunks>   (absent means clean)
#   maintained: false
---

## Goals

<!-- The alignment pass's written form (methodology/planning.md "Goals"): a cold session
     reads this before any chunk, mid-build decisions are made against it, and the
     boundary review judges the work by it. Mark each inference in plain words. -->

**Response taken:** Ask, in one batch — the owner answered 2026-07-02.

**Product:** A shared grocery list that replaces the paper list on the fridge. The brief's near-term is one household; its North Star is a few households sharing recipes.

**Architecture:** Runs on a home server, and data stays local. Keep multi-household possible: a household id on every row, nothing else household-specific. *Inferred:* no auth beyond a shared device.

**Constraints:** No paid services (owner).

**Tradeoffs accepted:** Barcode lookup calls OpenFoodFacts directly, with no cache — revisit if lookups feel slow. It may never matter, so no backlog item.

**Level:** High — problem, success, and scope confirmed with the owner; no fast-moving dependencies.

## Status

<!-- The cross-session handoff, and the ONLY reading of chunk progress. The boxes are
     yours to tick: mark `[x]` by hand when a chunk's "Done when" steps are all
     satisfied — built, reviewed, committed (a short plan's earlier chunks at commit:
     methodology/planning.md); never merged or released — nothing derives them, so an unticked box is read everywhere as work
     still open. Keep Context current. Context runs from `Context:` to the end of this
     section, so it may be several paragraphs — the handoff carries it whole. Keep it
     LAST: a chunk checkbox after it closes the block, and anything below that is
     dropped from the handoff.

     Ticking the LAST box disarms the Stop hook's Critic gate, so review before you
     tick it. A built-but-unticked chunk is caught by an advisory only if commit
     subjects name a numeric chunk id as (Chunk 02), right after the colon, or
     "close Chunk 02"; other positions read as a mention. -->

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

<!-- Chunks usually work best as vertical slices in dependency order; one Critic pass per
     chunk is the firm limit (methodology/planning.md). Here Chunk 01 is a thin slice
     through every layer. `Deliverables:` states what the chunk
     delivers. Backtick a path only when that file existing is itself the requirement —
     every backticked path in the current chunk's section is existence-checked, BLOCKING
     when missing; prefix a path the chunk CREATES with "new".

     Optional fields are declared only when they apply — missing is always the safe
     default. Field reference:
       `Critic mode:` / `Type:` — methodology/planning.md "Critic Mode Per Chunk" /
         "Choosing a Chunk Type"; the mode table is in skills/critic/review-cycle.md,
         the Type table in skills/critic/cross-checks.md.
         Mode missing or unrecognized → inferred; no rule firing → `chunk`, the inner-stage review.
         Each chunk's "Done when" runs `/prawduct:critic`; a SHORT plan owes fewer runs
         than one per chunk, and which and when is stated by review-cycle.md's
         "When Review Is Required" row — not restated here.
       `Foreign API:` / `Exposed API:` / `Visual change:` — methodology/planning.md.
       `Trivial because:` — required iff `Type: trivial`. -->

### Chunk 01: Walking skeleton — list page backed by SQLite

- **Description:** Prove the path: one page renders grocery items from SQLite. Layers connect end-to-end before any feature widens.
- **Depends on:** none
- **Artifacts consumed:** `data-model.md` (Item entity), `test-specifications.md` §1
- **Deliverables:** the list page renders seeded items from SQLite end to end (routes and a store module in the app package, one Jinja page)
- **Tests:** unit — `store.py` CRUD; integration — GET / renders seeded items (httpx)
- **Acceptance criteria:** the chunk's own tests pass; browser shows the seeded list at /
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: Add and check off items, grouped by store section

- **Description:** The daily flow: add an item with a store section, check it off, checked items archive. Lands the item state machine the app depends on.
- **Depends on:** Chunk 01
- **Artifacts consumed:** `product-brief.md` core flow 1, `test-specifications.md` §2
- **Deliverables:** add and check-off routes, the open → checked → archived transitions in the store, and the add form grouped by section
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
- **Deliverables:** barcode lookup against OpenFoodFacts with an offline manual fallback (new `pantry/lookup.py` client, a lookup route and UI field)
- **Tests:** unit — response parsing against the captured real shape; integration — lookup route with the client faked (fake built after verify-api, never before)
- **Acceptance criteria:** a known barcode prefills the name; API down → the form still works manually
- **Type:** cumulative-final
  <!-- Last chunk: its review IS the one `/prawduct:critic cumulative` — commit
       first, run it once, no separate `final`. On a short plan that one run is every
       earlier chunk's review too (review-cycle.md's "When Review Is Required" row);
       not on THIS plan, because Chunk 02 declares a `Critic mode:`. -->
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

**Commit & PR cadence:** commit per chunk after its Critic review passes (per-chunk commit is what scopes `chunk`-mode reviews). A short plan ticks and reviews differently — see methodology/planning.md "Critic Mode Per Chunk"; this plan is not one, because Chunk 02 declares a `Critic mode:`. The last chunk commits first, and its `cumulative` review makes the branch PR-ready — `/prawduct:pr create` is gated on it and runs when the user asks for a PR.

- After chunk 01: confirm the architecture (routes → store → SQLite) before widening.
- After chunk 03 (cumulative): full-bundle review; verify the offline fallback has real coverage.
