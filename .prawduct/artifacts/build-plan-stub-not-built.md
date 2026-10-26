---
artifact: build-plan
version: 2
scope: stub-not-built
branch: fix/1075-stub-not-built
base: develop
working-branches: []
last_validated: 2026-10-26
depends_on:
  - brookstalley/prawduct#1075
governed_by:
  - .prawduct/artifacts/architecture.md
  - .prawduct/artifacts/api-contract.md
  - .prawduct/artifacts/data-model.md
  - .prawduct/artifacts/nonfunctional-requirements.md
partition: serial — Chunk 02 is the change record for Chunk 01's fix, and its dispatch is the fix's live check
---

# Build Plan — A plan's fragment stub is not a built chunk (#1075)

## Goals

**Response taken:** Proceed, citing #1075. The issue has a repro, acceptance criteria and a
scope-out. The owner folded two items from #1072's boundary review into it (issue comment, R-4
and R-11), because they live in the same walker.

**Problem:** `plan new` writes the change fragment `.prawduct/changes/<scope>.md` as an empty stub in
the plan's first commit. A plan's change-record chunk lists that fragment under Deliverables, so
`plan_status._touches` counts the plan commit as building that chunk. `plan status` then tags the
last chunk `built` right after `plan new`, and a Chunk 01 `chunk` review's interval contains the
stub, so it proposes and certifies the last chunk.

**Success (#1075's acceptance):**
- Right after `plan new` and its commit, `plan status` shows no chunk as `built`.
- A Chunk 01 `chunk` review does not propose the change-record chunk because of the stub alone.
- A later commit that really writes the fragment still marks that chunk `built`.
- (R-11) When the subject walk cannot answer, the whole-plan proposal's dispatch says so in its
  notes, instead of silently naming fewer chunks.
- (R-4) The proposal never counts another plan's `Chunk N` subject.

**Out of scope:** #1072's reach rule. Deliverables overlap between two real chunks: a chunk that
genuinely writes another chunk's Deliverable early still reads as touching it.

**Inferences (flagged for the boundary review):**
- *What "a stub" is.* A fragment whose narrative and consumer note are both empty: exactly what
  `plan_mint.new` writes, and what the fragment validator refuses to release. The test is on
  content at the tree being judged, not on which commit added it. The issue offered two options;
  the content test serves both readers from one owner without a per-commit walk, which `chunk`
  mode must not do, because `extension_deferral_owed` asks it on the Stop path. A title alone
  does not make a fragment written, because `plan new --title` fills it at mint time.
- *Which tree.* `built_report` reads the fragment at the walked branch head (committed work).
  The dispatch proposal reads it at the review's `head_tree`, the tree whose diff it was given.
  The Stop-path caller reads the working tree, which is where its diff ends.
- *A fragment that cannot be read at that tree* (deleted, or git fails) counts as unwritten. On
  the certifying path that names fewer chunks, which fails closed. A fragment that does not parse
  counts as written, because `plan new` never writes one.
- *R-4, decided:* when the plan declares `scope:`, the proposal counts only subjects carrying that
  scope. The render tag keeps today's fallback (every subject counts when none carries the scope),
  because a wrong tag costs a misread table, while a wrong proposal certifies unbuilt work. When
  the fallback would have named a chunk the proposal did not, the dispatch notes it, so a builder
  whose subjects drifted from the scope sees why.
- *R-11's channel.* The proposal's notes ride `begin_review`'s existing `notes`, which the CLI
  prints at dispatch. The proposal list keeps its type for its callers.

**Decisions made mid-build:**
- Chunk 01: `built_chunks` was documented as "render-only; no gate reads it", but
  `critic_mode.short_plan_deferral`'s `read_built` arms a short plan's last-chunk block from it.
  So the stub also made a two-chunk short plan's Stop gate demand the boundary review during
  Chunk 01. The claim now says a gate may read it only to arm, and every "render-only" copy was
  corrected. Settled by "do it right": the fix removes a false arm, and a written fragment still
  arms.
- Chunk 01: at dispatch, the subject walk always receives the interval's base commit, so `base:`
  is never consulted there. R-11's note fires when `git log` itself fails. Its dispatch test
  injects that failure, and `plan_status`'s own test covers the unresolvable-`base:` cause.
- Chunk 01: `head_tree` is guarded by `gitstate.is_object_id` inside the public function, as
  `since` is. A malformed value reads every fragment as unreadable (naming fewer), never a git
  argv.

## Norm reconciliation (`governed_by`)

- `architecture.md` "Authority fails closed; advice fails soft" — **conforms**. Every unreadable
  case names fewer chunks on the certifying path, and the notes are advice.
- `architecture.md` "Every fact has one home" — **conforms**. "Is this fragment still a stub" lives
  once in `change_fragments`, and both readers ask it through one `plan_status` helper.
- `architecture.md`, the other norms (reviewer never mutates, local-first, writes only `.prawduct/`,
  language-agnostic, guides-not-implements, goals bind) — **inapplicable**: no reviewer write path,
  network call, repo write, language dispatch or product code.
- `api-contract.md` "Exit codes are the contract" and "Additive-first evolution" — **conforms**: no
  exit code changes, and `chunks_proposed` keeps its meaning.
- `data-model.md` — **inapplicable**: no fact kind or schema changes.
- `nonfunctional-requirements.md` "Review wall-clock is P0" — **conforms**: at most one `git show`
  per changed fragment path, and the walk is still one `git log`.

## Build Chunks

### Chunk 01: A stub is not work; the proposal says why it named fewer

- **Description:** Both readers of "which chunks have work" leave out an unwritten fragment stub.
  The certifying proposal counts only scoped subjects, and says when its walk could not answer.
- **Depends on:** none
- **Deliverables:**
  - `plugin/lib/change_fragments.py`: `Fragment.unwritten` and `is_unwritten_stub(text)`.
  - `plugin/lib/plan_status.py`: one helper that drops unwritten fragment paths from a changed set,
    used by `built_report` and `propose_chunks`; the walk keeps the scoped and fallback subject
    sets apart; a proposal report carrying notes; docstrings.
  - `plugin/lib/critic_consolidate.py`: `_proposed_chunks` passes `head_tree` and returns the
    proposal's notes, which `begin_review` appends.
- **Tests:** `tests/test_plan_status.py`, `tests/test_change_fragments.py`, and the
  `critic-begin` proposal tests:
  - #1075's repro: `plan new`'s stub committed → `plan status` shows nothing built, and a `chunk`
    proposal over the stub's diff is empty (red against the pre-fix code);
  - a commit writing the fragment's narrative → the change-record chunk is built and proposed;
  - another plan's unscoped `Chunk N` subject is not proposed when this plan's scoped subjects
    exist or not, and the render tag keeps its fallback;
  - an unresolvable `base:` → the whole-plan proposal's notes name the cause.
- **Acceptance criteria:** #1075's three acceptance boxes, plus R-4 and R-11 above.
- **Critic mode:** chunk
  <!-- Opts this short plan back into per-chunk review: Chunk 01's dispatch is the fix's
       live check (it must not propose 02 off this plan's own stub). -->
- **Done when:**
  1. Tests pass.
  2. No surface describing the built rule or the proposal contradicts it (sweep: "touches",
     "Deliverables path", "every subject counts").
  3. `/prawduct:critic` run and blocking findings resolved. The plan touches `plugin/lib/` only,
     but Chunk 02 must see the fix live, so this chunk gets its own review: its proposal must name
     `01` alone, not `02` (acceptance 2, on this plan's own stub).
  4. Committed.

### Chunk 02: Change record

- **Description:** The fragment for this unit.
- **Depends on:** Chunk 01
- **Deliverables:**
  - `.prawduct/changes/stub-not-built.md`
- **Tests:** none: prose. `plan status` before this chunk shows it unbuilt; after its commit, built.
- **Acceptance criteria:** the fragment validates; the boundary review names 01 and 02.
- **Type:** cumulative-final
- **Done when:**
  1. Declared suite recorded green.
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved.
