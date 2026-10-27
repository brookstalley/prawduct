---
artifact: build-plan
version: 2
scope: chunk-proposal-silence
branch: fix/1081-chunk-proposal
base: develop
working-branches: []
last_validated: 2026-10-26
depends_on:
  - brookstalley/prawduct#1081
governed_by:
  - .prawduct/artifacts/architecture.md
  - .prawduct/artifacts/api-contract.md
  - .prawduct/artifacts/nonfunctional-requirements.md
partition: serial — Chunk 02 is the change record for Chunk 01's fix
---

## Goals

**Response taken:** Proceed, citing #1081. The issue has a reproduction, the expected behaviour,
and a root cause that triage checked against the code. The owner said "fix bug report"
(2026-10-26).

**Problem:** At a plan's boundary `cumulative` review, `critic-begin` proposed no chunks although
every chunk's work was on the branch. So the default certified nothing, nobody was told, and three
plans in one repo were archived with `unbuilt_at_archive` on shipped work. There were three
causes:
- the subject walk's pattern is case-sensitive and does not accept `<scope> chunk 01: …`;
- a bare Deliverables name (`` `page.js` ``) can never match a repo-relative diff path, while the
  record lint skips bare names, so the two disagree about what a Deliverable reference is;
- the proposal's notes print to `critic-begin`'s stderr inside the forked critic, which never
  reaches the main agent.

**Success (#1081's Expected):**
- When a whole-plan review certifies no chunk while the plan has open ones, the relayed
  `NEXT-ACTION:` line says so, names the open chunks and the `--chunks` remedy.
- The proposer and the record lint agree that a bare name is a Deliverable path only when that
  file exists at the repo root. At a whole-plan review, an unproposed chunk whose Deliverables are
  all such other bare names gets a dispatch note telling the author to write repo-relative paths.
- Subjects naming a chunk match case-insensitively, and `chunk NN:` (a chunk id followed by a
  colon) is a carrying form. A subject that begins with the plan's scope as a plain prefix
  (`<scope> chunk 01: …`) carries that scope.

**Out of scope:** #1082, whether a review's commit span should certify chunks it does not name.
That needs a design decision from the owner.

**Inferences (flagged for the boundary review):**
- *Bare names do not match by basename.* Making them match would let an unrelated `core.py`
  certify a chunk, and a wrong certification is never reviewed again. Naming fewer and saying so
  fails closed, as `architecture.md` "Authority fails closed; advice fails soft" asks. 202 of
  1278 Deliverables tokens in this repo's own plans are bare, many of them symbols, so the lint
  must not start blocking on them either.
- *The NEXT-ACTION carrier.* `critic-consolidate` works out, after appending the fact, whether a
  whole-plan review certified nothing while its plan has open chunks. If so, it adds a clause to
  the line the fork must relay verbatim, and to the `.critic-findings.json` copy of that line.
  That avoids depending on the fork relaying stderr, and no persisted schema changes.
- *`chunk NN:`* counts anywhere in a subject. Prose like "carried to Chunk 04" has no colon after
  the id, so it still does not count.

**Decisions made mid-build:**
- Chunk 01: the clause is computed at the close rather than recorded in the manifest at
  dispatch. Both carriers then come from one computation, as `rides_next_review` already does.
  Settled by "match the product's other choices".
- Chunk 01: the bare-name note fires only when EVERY Deliverables token of an unproposed chunk is
  bare and absent at the root. 202 of 1278 tokens in this repo's plans are bare, many of them
  symbols, so firing on any bare token would be noise. Only the all-bare chunk is invisible to
  the diff.
- Chunk 01, *not settled by the goals*: the boundary suite failed in
  `test_retired_claims::TestThisRepoIsClean` on its 30s timeout at load average ~45.
  `retired_claims._INLINE_RETIRES_RE` was quadratic on long lines (3.2s of the scan). It is
  replaced by the linear `_has_inline_retires`, checked equal on every tracked line that carries
  `Retires:`; the scan's declaration read drops from 3.24s to 0.03s. Fixed here under the
  no-pre-existing-exception rule, because it fails this branch's suite.
- Chunk 01: `feat(unit): Chunk 02 work moved` already counted under the `: Chunk N` form. That
  is unchanged; only prose without a colon after the id stays uncounted.

**Level:** High. The code paths are read and the reporter's repro is concrete.

## Governing norms

- `architecture.md` "Authority fails closed; advice fails soft": **conforms**. No chunk is
  certified from a weaker signal, and every new line is advice.
- `api-contract.md` "Exit codes are the contract" and "Additive-first evolution": **conforms**. No
  exit code changes, and `chunks_proposed` keeps its meaning.
- `nonfunctional-requirements.md` "Review wall-clock is P0": **conforms**. No new git call; the
  open chunks are already computed for the proposal.
- The other norms (reviewer never mutates, local-first, writes only `.prawduct/`,
  language-agnostic): **inapplicable**. There is no reviewer write path, network call or product
  code here.

## Build Chunks

### Chunk 01: The proposal says when it names nothing, and reads more subject forms

- **Description:** The subject walk reads more carrying forms. A bare Deliverables name is a path
  only when it exists at the repo root, and the dispatch says so when that leaves a chunk out. A
  whole-plan review that certifies no open chunk says so in `NEXT-ACTION:`.
- **Depends on:** none
- **Deliverables:**
  - `plugin/lib/plan_status.py`: `_CHUNK_COMMIT_RE` matches case-insensitively and accepts
    `chunk NN:`; scope carried by a plain prefix (`_carries_scope`); a dispatch note for an
    unproposed chunk whose Deliverables are all bare names absent at the repo root
    (`_bare_only`). `deliverable_paths` already matches a bare name only as a root-level file.
  - `plugin/lib/critic_consolidate.py`: `_uncertified_open_chunks` and `uncertified_clause`;
    `next_action_line` and `fact_to_cache_record` carry the clause.
- **Tests:** `tests/test_plan_status.py` and the critic-begin/consolidate tests:
  - #1081's repro: bare Deliverables names plus `<scope> chunk 01: …` subjects → a cumulative
    proposal names the chunk (red before the fix);
  - prose "carried to Chunk 04" still names nothing;
  - a whole-plan review certifying nothing while chunks are open → `NEXT-ACTION:` names them and
    `--chunks`; a `chunk`-mode review and a review with nothing open do not add the clause;
  - a bare name existing at the repo root still matches.
- **Acceptance criteria:** #1081's three Expected items, as written under Success.
- **Done when:**
  1. Tests pass.
  2. No surface describing the carrying forms or Deliverable paths contradicts them (sweep:
     "anchored forms", "path-shaped", "Bare filenames").
  3. Committed.

### Chunk 02: Change record

- **Description:** The change fragment and its consumer note.
- **Depends on:** Chunk 01
- **Deliverables:** `.prawduct/changes/chunk-proposal-silence.md`
- **Type:** cumulative-final
- **Done when:**
  1. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved.
