---
artifact: build-plan
version: 2
scope: dispositions-travel
branch: fix/dispositions-travel
base: develop
working-branches: []
last_validated: 2026-11-23
partition: "delegated — 01, 02 and 03 in parallel, worktree-isolated, on Opus (01, 02) and Sonnet (03); the coordinator integrates on fix/dispositions-travel. Ownership is by file: 01 owns plugin/lib/dispositions.py and tests/test_dispositions.py and data-model.md's disposition-body paragraph; 02 owns evidence.py, evidence_notes.py, ledger.py, critic_consolidate.py's _refuse_over_budget, security-model.md and the transport tests; 03 owns the other descriptions. Seams: record's result key `note` and auto_accept's `unsent` (01 writes, 02 reads) are fixed in this plan; data-model.md is two sections in two chunks and the coordinator merges it"
governed_by:
  - artifact: data-model
    dispositions:
      - "verdicts computed from facts, no model in the write path → conforms; the D4 winner is a pure function of the facts held"
      - "facts immutable and append-only → conforms; a new answer is a new fact, and a legacy id collision (D6) is reported, never rewritten"
      - "derived views never authoritative → conforms; the census reads the index, which reads facts"
      - "a governance document reaches a terminal state → inapplicable because no document other than this plan is archived"
      - "backlog issues conform to the title rules → inapplicable because no backlog write path changes"
      - "a newer-schema fact is surfaced, never dropped → conforms; an old plugin skips the kind and keeps the lines through the merge (D9 R13, pinned by T8)"
      - "two stores, two lifetimes → conforms; a disposition still has one home, the store, and the note is a copy (#606)"
      - "backlog_service_repo selects the authoritative store → inapplicable because no backlog read changes"
      - "D1 (chunk state from facts) → inapplicable because no chunk-state reader changes"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → inapplicable because no reviewer-side write path changes"
      - "authority fails closed; advice fails soft → conforms; a failed attach never fails the record (D1), and no gate reads a disposition (D9)"
      - "local-first → conforms; attach is two local git calls, and only `evidence sync` pushes"
      - "the plugin writes only its own state → conforms"
      - "written in Python, never specific to Python → conforms"
      - "guides and reviews, never implements → conforms"
      - "goals and verification bind, method is advice → conforms; departures are recorded under Decisions made mid-build"
  - artifact: security-model
    dispositions:
      - "untrusted governance state is data → conforms; an ingested disposition reaches the census, the briefing and the prior-dispositions block, and no gate (D9, pinned by T7)"
      - "destructive operation needs operation-level approval → inapplicable because nothing is deleted or rewritten"
      - "product content leaves only through pinned, approved surfaces → conforms; `evidence sync` pushes only to the product's own push remote, which the norm does not govern as cross-owner, and the outbound entry names the four newly published fields (design § Security model)"
---

## Goals

**Response taken:** Proceed, citing it — `documentation/issues/1207-design.md` (D1–D10, T1–T13) and
the owner rulings of 2026-11-22 in `.prawduct/owner-rulings.md` (dispositions travel, all three
actions; backfill in-flight branches through `reconcile`; budget-sweep ACCEPTs travel; no sweep of
merged branches).

**Product:** an ACCEPT, FILE or `--fixed` answered in one clone reads the same in every clone that
has synced the branch, and every clone picks the same winner when a finding has several answers.

**Constraints:** no gate may read a disposition (D9). A failed note write never fails a record.
The outbound security entry is amended in the same chunk that starts sending (G5).

**Decisions made mid-build:**
- The design's Chunking put D1 (the writer attaches) in its Chunk 2. This plan moves D1's edits to
  `dispositions.py` (`record`'s attach and `note`, `auto_accept`'s `unsent`, `disposition_cmd`'s
  NOTE) into Chunk 01, so one delegate owns that file. Chunk 02 reads the two keys. The work and its
  tests are unchanged; only the chunk that carries them moved.
- Chunks are reviewed once, by Chunk 03's `cumulative`, because the three are built in parallel and
  integrated before any review could see one alone.

**Level:** High — design reviewed and ruled; nothing fast-moving.

## Build Chunks

### Chunk 01: Convergence in one clone, and the writer attaches

- **Description:** D4 (`answer_key`), D5 (tagged ids, `seq = max + 1`), the index, history,
  `prior_dispositions` and no-op check reading one winner; D1 (`record` attaches to its review's
  anchor and returns `note`, `auto_accept` returns `unsent`, `disposition_cmd` prints a NOTE on a
  failed attach and exits 0).
- **Depends on:** none
- **Artifacts consumed:** `documentation/issues/1207-design.md` D1, D4, D5, Test plan
- **Deliverables:** convergence and attach in `plugin/lib/dispositions.py`; the module docstring's
  store-order and race sentences rewritten; `data-model.md`'s disposition-body text ("last-recorded
  wins … sequenced id") rewritten to D4/D5; tests T3, T4 and T5 at store level, T9, T12, and the
  `TestRedisposition` updates in `tests/test_dispositions.py`
- **Acceptance criteria:** each new test seen red before its fix; `tests/test_dispositions.py` green
- **Done when:** 1. criteria met 2. committed 3. covered by Chunk 03's `cumulative`

### Chunk 02: Transport

- **Description:** D2, D3, D6 and the security-model sentences, and the cross-clone tests.
- **Depends on:** none to build; its cross-clone tests pass only once Chunk 01 is merged
- **Artifacts consumed:** `documentation/issues/1207-design.md` D2, D3, D6, D7, D9, Security model, Test plan
- **Deliverables:** `TRANSPORTED_KINDS` and its comment; `unattached`'s disposition branch;
  ingest's legacy-collision count; the `evidence_notes` and `ledger.py` docstrings and the pinned
  ledger test; `_refuse_over_budget` surfacing `unsent`; `security-model.md`'s outbound and inbound
  sentences; tests T1, T2, T4 and T5 across two clones, T6, T7, T8, T10, T11, T13
- **Acceptance criteria:** each new test seen red before its fix; after integration, the transport
  and ledger test files green
- **Done when:** 1. criteria met 2. committed 3. covered by Chunk 03's `cumulative`

### Chunk 03: Every description agrees (R14)

- **Description:** the descriptions of the old rule, and the falsifying search for it in other words.
- **Depends on:** Chunks 01 and 02 merged, for the final search
- **Artifacts consumed:** `documentation/issues/1207-design.md` Chunking item 3
- **Deliverables:** `governance-telemetry.md`, `review-cycle.md` and `data-model.md` "Reach beyond
  the clone" say dispositions travel; the design doc's stale note about the unrecorded ruling is
  removed; the falsifying search's output over `plugin/`, `tests/`, `documentation/` and
  `.prawduct/artifacts/`
- **Type:** cumulative-final
- **Done when:** 1. integrated and the suite green 2. committed, then `/prawduct:critic cumulative`
  run and blocking findings resolved

## Governance Checkpoints

After integration: the declared suite once on `fix/dispositions-travel`, then the one `cumulative`.
After merge and before the first sync from this repo: the operator scan in the design's Security
model section (list what `reconcile` would attach, grep it for other products' names).
