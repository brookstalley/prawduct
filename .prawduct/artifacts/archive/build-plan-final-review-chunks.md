---
artifact: build-plan
version: 2
scope: final-review-chunks
branch: fix/1072-final-review-chunks
base: develop
working-branches: []
last_validated: 2026-10-26
depends_on:
  - brookstalley/prawduct#1072
  - .prawduct/artifacts/release-plan-v3.8.0.md
governed_by:
  - .prawduct/artifacts/architecture.md
  - .prawduct/artifacts/api-contract.md
  - .prawduct/artifacts/data-model.md
  - .prawduct/artifacts/nonfunctional-requirements.md
partition: serial — two small chunks sharing `plugin/lib/plan_status.py`, and 02's retraction reads the proposal 01 changes
lifecycle: completed
archived: 2026-10-30
released_in: v3.8.0
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

# Build Plan — Final review chunks: reach, not mode (#1072)

## Goals

**Response taken:** Proceed, citing #1072. The issue has a repro, acceptance criteria and a
scope-out, and it is a v3.8.0 release requirement (owner, 2026-10-26; `release-plan-v3.8.0.md` row
`final-review-chunks | ships`).

**Problem:** `plan_status.propose_chunks` proposes every open chunk for a `final` or `cumulative`
review, and `critic-begin` certifies the proposal when `--chunks` is omitted.
`methodology/planning.md` recommends overriding an early keystone chunk forward to `final`, so
following that advice marks every later chunk done before it is built. A wrong certification cannot
be taken back. Chunk state (#1051) ships in v3.8.0, so every governed product would get wrong
`plan status` answers and a Stop gate that stops asking for reviews.

**Success:**
- A review's **mode sets its depth, not its reach.** A mid-plan `final` names only the chunks its
  interval built. So does a mid-plan `cumulative`, the boundary for a short plan that opens its own
  PR early.
- An end-of-plan boundary review still names every built chunk, so a short plan still finishes on
  its one review.
- `prawduct-hook plan retract` reopens a chunk that a fact wrongly certified. It records a reason,
  and the retraction travels to other clones.

**Out of scope (the issue's scope-out):** the `built` hot-path rule. `chunk_states` stays free of
git walks (NF1). `built_report`'s matching rule is unchanged; its subject half is shared with the
proposal through one `git log` reader, and its path half is not used for certification.

**Inferences (flagged for the boundary review):**
- *What whole-plan modes propose.* The open chunks the interval's diff touches through their
  Deliverables, plus the open chunks a commit subject on the plan's branch names. Not
  `built_report`'s path rule (Chunk 01 review): a later chunk's Deliverable that an earlier commit
  touched, such as the fragment `plan new` stubs, reads as built there before anyone builds it. A
  table tag can afford that error; a certification cannot. The diff alone would drop a chunk whose
  Deliverables name no path. `short_plan_next_step` tells the builder
  to name such a chunk in a commit subject precisely so that it reads as built, so the boundary review
  has to name it. `chunk` mode is unchanged: it uses the diff only, because it reviews a dirty tree
  and `extension_deferral_owed` calls it on the Stop path, where a git walk is not allowed.
- *When the branch walk cannot answer,* the proposal falls back to the diff alone. Naming too few
  chunks fails closed: an open chunk keeps every gate armed. Naming too many is the defect this plan
  fixes.
- *A retraction targets one (fact, chunk) pair,* not the chunk as a whole (**owner-confirmed
  2026-10-26:** retractions need no sign-off), so a later honest review
  of the same chunk still certifies it. It needs no owner authority, because it can only reopen a
  chunk. That arms gates and never disarms them, so the governed party still cannot certify itself
  (`data-model.md`'s ledger norm, Why).
- *How retractions are stored.* They are a new fact kind, `chunk-retracted`. They are transported
  like `chunk-imported`: a retraction that other clones never see leaves those clones certifying the
  chunk. They are observational: the coverage verdict never reads them, because a retraction changes
  chunk state, not tree coverage.
- *A ticked `## Status` box certifies its chunk in memory (MG1) after any withdrawal,* so the
  remedy is to untick the box. The command refuses any retraction of that chunk with that remedy,
  whether a fact certifies it or not.

**Noticed, not fixed here:** the issue's second symptom. A Chunk 01 `chunk` review proposed Chunk 07
because `plan new` stubs the change fragment, which is one of Chunk 07's Deliverables, into Chunk
01's diff. That is a Deliverables-overlap false positive in `chunk` mode, independent of reach, and
it is filed as its own backlog item.

**Decisions made mid-build:**
- Boundary review: whole-plan proposals read commit subjects only in the review's own commit range
  (`since` = the interval's base). A verify pass drops chunks retracted from facts on its chain, and
  a ticked box refuses any retraction of its chunk. Settled by the cumulative's R-1/R-2/R-5: three
  routes by which a retracted chunk came back as done. The class is "a proposal or a certification
  copied from somewhere that never asked about retractions".
- Chunk 01: whole-plan modes add only subject-named chunks to the diff's answer, not `built_report`'s
  touched-path rule. Settled by the Chunk 01 review's blocking finding, which reproduced the #1072
  repro on the consumer-digest plan's own history. #1075 tracks the same overlap on `built_report`
  and `chunk` mode.
- Chunk 01: `planning.md` needed no edit. Its short-plan and keystone lines do not state the
  proposal rule, and both are true under the fix (the keystone override is now safe). The
  clause I first added was reverted: the reader has nothing to reason past.
- Chunk 01's review was dispatched with `--chunks 01`. `plan_status.py` is a Deliverable of both
  chunks, so the `chunk`-mode proposal named 01 and 02. That is the overlap #1075 records, not reach.
- `plan retract` is guarded like `plan import-status --apply`: refused in a scratch worktree, and not
  under the binary-skew guard, which today covers no `plan` op.

## Norm reconciliation (`governed_by`)

- `architecture.md` "Authority fails closed; advice fails soft" — **conforms**. When reach cannot be
  read, the proposal names fewer chunks, and a retraction can only reopen one.
- `architecture.md` "Every fact has one home" — **conforms**. The reach rule lives in
  `propose_chunks`; the skill, planning.md and the docstrings point to it rather than restate it.
- `architecture.md`, the other norms (reviewer never mutates, local-first, writes only `.prawduct/`,
  language-agnostic, guides-not-implements, goals bind) — **inapplicable**, because this plan adds no
  reviewer write path, network call, repo write outside the evidence store, language dispatch or
  product code.
- `api-contract.md` "Exit codes are the contract" — **conforms**. `plan retract` uses
  `import-status`'s scheme: 0 ok, 1 `refused: <code>`, 2 usage.
- `api-contract.md` "Additive-first evolution" — **conforms**. It adds a subcommand and a fact kind,
  and the `chunks_proposed` key keeps its meaning (the code-derived proposal). Semantic versioning is
  **inapplicable**: the release sets the version.
- `data-model.md` "verdicts from the append-only ledger, no model in a fact's write path" —
  **conforms**. Code writes the retraction from the caller's arguments, as `disposition` facts are
  written, and it can only un-certify.
- `data-model.md` "Facts are immutable and append-only" — **conforms**. This norm is why retraction
  is a new fact and never an edit to the review fact.
- `data-model.md` "newer-schema fact surfaced loudly" — **conforms**. The new kind is not a schema
  bump. An older reader keeps the unknown kind in its digest, and in that older reader the retracted
  chunk stays done: the `chunk-imported` precedent (`evidence.py` comment). The other norms
  (derived views, terminal state, backlog titles, two stores, backlog store) are **inapplicable**.
- `nonfunctional-requirements.md` "Review wall-clock is P0" — **conforms**. The subject walk
  runs once per `final`/`cumulative` dispatch, not on Stop. The other norms (proportionality,
  growth advisory, stage-keyed rigor) are **inapplicable**.

## Build Chunks

### Chunk 01: Reach, not mode — what final and cumulative propose

- **Description:** Whole-plan modes propose the open chunks the review's interval built, not every
  open chunk.
- **Depends on:** none
- **Deliverables:**
  - `plugin/lib/plan_status.py`: in `propose_chunks`, whole-plan modes propose the open chunks the
    diff touches or a commit subject in the review's range names (see Decisions; not `built_report`'s
    path rule). The "every open chunk" rule is retired, along with
    its docstring and the module docstring's line.
  - `plugin/lib/critic_consolidate.py`: the `_proposed_chunks` and `begin_review` docstrings.
  - `plugin/lib/critic_mode.py`: the docstrings that claim a cumulative names every open chunk.
  - `plugin/skills/critic/SKILL.md`: step 4's proposal sentence.
  - `plugin/methodology/planning.md`: the short-plan and keystone-override lines.
- **Tests:** `tests/test_plan_status.py`:
  - the #1072 repro: a mid-plan `final` after Chunk 02 proposes `02` only, with 03 and 04 unbuilt.
    It is red against the pre-fix code.
  - a `cumulative` names a chunk built only by a commit subject that names it.
  - an unbuilt later chunk is not proposed.
  - when the branch walk is unavailable, the proposal is the diff's alone.
- **Acceptance criteria:**
  - a mid-plan `final` review proposes only the touched chunks (#1072 acceptance 1);
  - a short plan's end-of-plan `cumulative` still names every built chunk.
- **Done when:**
  1. Tests pass.
  2. No surface describing the proposal still claims "every open chunk". The sweep greps the concept,
     not one token: "every open chunk", "names every chunk", "closes them all".
  3. `/prawduct:critic` run and blocking findings resolved — the plan touches risk surfaces
     (`plugin/skills/`, `plugin/bin/*hook*`), so it is not a short plan and this chunk gets its own
     review, certifying `01` alone (`--chunks 01`; see Decisions).
  4. Committed.

### Chunk 02: A recorded retraction

- **Description:** `plan retract` writes a `chunk-retracted` fact, and `chunk_states` stops counting
  that fact for that chunk.
- **Depends on:** Chunk 01
- **Deliverables:**
  - `plugin/lib/plan_status.py`: `RETRACTED_KIND`; `chunk_states` skips a retracted (fact, chunk)
    pair and gives the reason in the chunk's row.
  - `plugin/lib/evidence.py`: `KNOWN_KINDS`, `OBSERVATIONAL_KINDS`, `TRANSPORTED_KINDS` and their
    comments.
  - `plugin/lib/evidence_notes.py`: the docstrings naming the HEAD-anchored kind. Its `missing`
    branch already treats every non-review, non-resolution transported kind alike.
  - The artifacts naming the transported or known kinds: `data-model.md` (kind list, transport,
    a body bullet), `api-contract.md` (the `plan retract` entry, transport), `architecture.md`,
    `security-model.md`.
  - `plugin/bin/prawduct-hook`: `plan retract <chunk> --reason <text> [--fact <id>] [--plan <path>]
    [--json]` (`--fact` omitted: the fact certifying the chunk now), plus its guards and `_PLAN_HELP`.
  - `plugin/methodology/planning.md` "Chunk state": how a wrong certification is undone.
  - `.prawduct/changes/final-review-chunks.md`.
- **Tests:**
  - `tests/test_plan_status.py`: a retracted pair reopens; the fact's other chunks stay done; a later
    review re-certifies; another scope's retraction is ignored.
  - `tests/test_plan_retract.py`: each refusal; an idempotent re-run; the note is attached.
  - the kind-registry tests.
- **Acceptance criteria:** a recorded retraction exists (#1072 acceptance 2), and `plan status`
  shows the chunk open with the retraction's reason.
- **Type:** cumulative-final
- **Done when:**
  1. Tests pass, and the declared suite is recorded green.
  2. Committed, then `/prawduct:critic cumulative` is run and blocking findings are resolved. That
     review is dispatched through the fixed proposal, and its fact must certify 02, so
     `plan status` finishes.
