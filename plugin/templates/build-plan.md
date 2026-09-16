<!-- Build Plan Template — Tier 1 (Source of Truth)

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
# branch: the branch this plan governs. UNCOMMENT IT with your real branch name —
# it is left commented rather than filled in like the fields around it because a
# placeholder branch is one no repo has, and the session briefing correctly
# reports a plan claiming a branch that does not exist.
#
# Declaring it makes every governance surface resolve THIS plan while that branch
# is checked out, ahead of the `active_build_plan` scalar — so two concurrent
# branches stop fighting over one line, and archiving the plan (or deleting the
# merged branch) ends the claim with nothing to un-point. Leave it out and the
# scalar keeps working exactly as before.
#
# Several plans MAY declare one branch — a release branch carrying two workstreams
# is ordinary, not an error. Governance picks one by a stated precedence and the
# session briefing says which it chose, why, and what else claimed the branch.
# The precedence itself lives in ONE place: methodology/planning.md, "Which plan
# is active is branch state".
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
# END OF LIFE — written by `prawduct-hook archive-plan`, not by hand. A plan is
# never deleted: when its work is done, or has stopped, been descoped, or been
# absorbed elsewhere, it is stamped with these keys and moved into `archive/`.
# The command writes them; they are shown here so a reader of an archived plan
# knows what they mean.
#   lifecycle: completed | superseded   <- which of the two terminal states
#   archived: YYYY-MM-DD                <- when it reached one
#   released_in: vX.Y.Z                 <- the release that carried it, where the
#                                          product versions. NOT `release:` — a
#                                          release plan uses that for the release
#                                          it GOVERNS, which is a different fact.
#                                          The change-log `release=` tag stays
#                                          canonical; this is a permitted copy
#                                          because a shipped version is immutable
#                                          and cannot drift.
#   superseded_by: <what replaced it, or why it stopped>   <- superseded only
#   unbuilt_at_archive: <what this plan's own Status said was still unbuilt>
#                                       <- ABSENCE MEANS CLEAN, not unknown. It
#                                          appears only when the Status roster
#                                          shows unticked chunks, or when there
#                                          is no readable roster at all — an
#                                          unparseable plan is not evidence of
#                                          completion. Written by the explicit
#                                          `archive-plan` route only; the
#                                          automatic sweep refuses incomplete
#                                          plans, so it never produces one.
#   maintained: false
# Status checkboxes are NOT touched on the way in. An archived plan may carry
# unticked boxes — that records how the work ended, and nothing reads them once
# the plan is out of the live directory. `unbuilt_at_archive:` exists because
# nothing reads them: the fact has to be said in the frontmatter to be said at all.
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

<!-- The cross-session handoff, and the ONLY reading of chunk progress. The boxes are
     yours to tick: mark `[x]` by hand when a chunk's "Done when" steps are all
     satisfied — nothing derives them, so an unticked box is read everywhere as work
     still open. Keep Context current. Context runs from `Context:` to the end of this
     section, so it may be several paragraphs — the handoff carries it whole. Keep it
     LAST: a chunk checkbox after it closes the block, and anything below that is
     dropped from the handoff.

     Ticking is load-bearing in both directions. Ticking the LAST box disarms the Stop
     hook's Critic gate, which is why "Done when" puts the review before the tick. (Not
     the reflection gate — that one asks whether this session changed judgeable code, so
     no box disarms it.) The opposite error — a chunk built, committed, left unticked — is caught
     by an advisory, and ITS PRECONDITION IS YOUR COMMIT CONVENTION: it fires only on a
     NUMERIC chunk id in one of three anchored positions —

         feat(scope): land it (Chunk 02)          <- parenthesised
         docs(scope): Chunk 02 — the prose half   <- right after the colon
         docs(scope): close Chunk 02 — the census <- the closing idiom

     A chunk id anywhere else in the subject is read as a MENTION, not as work — so
     "carried into Chunk 03" reports nothing, which is the point: an advisory whose
     first firing is wrong is an advisory people learn to ignore. A repo that doesn't
     name chunks in commit subjects, or numbers them `Chunk A`, gets permanent silence
     from it — and silence there is indistinguishable from every box being right.
     Number the chunks and name them in one of the three forms, or accept that the
     boxes have no backstop. -->

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
