---
artifact: build-plan
version: 2
scope: critic-dispatch-clock
branch: feat/critic-dispatch-clock
partition: serial — one mechanism and the records that describe it; Chunk 02 edits a norm whose statement Chunk 01 falsifies, so they cannot be reviewed apart
depends_on:
  - artifact: build-plan-pr-review-payload
governed_by:
  - artifact: data-model
    dispositions:
      - "governance verdicts computed from the append-only fact ledger, never from model-written state → conforms, and this plan EXTENDS it: the whole point is moving one number out of the reviewing model's write path and into code's. No model chooses the value; the caller chooses only when to mark"
      - "absence means NOT MEASURED, never zero → conforms unchanged; the Critic marker's every degraded path returns no `dispatched_at` key, exactly as the PR marker's does, and both populations stay separately reported"
      - "staleness is a TREE question, not a clock one → conforms unchanged; the Critic marker records the HEAD it was written at and consumption requires that same HEAD"
      - "only `review.pr` appends consume the marker → **DEPARTURE, see the [DECISION] below.** The norm's WHY is preserved by construction; its STATEMENT is written over a singular marker and this plan makes the marker set plural"
      - "facts are immutable and append-only → inapplicable; no fact kind is added, edited or read, and the ledger is not the evidence store"
      - "derived views are disposable and never authoritative → conforms; nothing persists a derived verdict, and no gate reads a duration"
      - "two stores, two lifetimes → conforms; the new marker is per-clone, gitignored, and registered in all three enumerations that track that boundary"
      - "a fact written by a newer schema is a loud block → inapplicable; `dispatched_at` is an OPTIONAL envelope key already in schema 1 and this plan adds no key"
      - "a governance document reaches a terminal state, never deleted → inapplicable; no document is retired"
      - "every backlog write conforms to the title rules → inapplicable; no backlog item is written by a chunk"
      - "`backlog_service_repo` selects the authoritative store → inapplicable"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → conforms; the mark is written by `critic-begin`, which is code running BEFORE any reviewer is spawned, and no reviewer touches it"
      - "authority fails closed; advice fails soft → conforms; a duration is advice end to end. Every failure path (unwritable marker, unreadable marker, git silent, tree mismatch) degrades to a self-reported estimate and NAMES the degradation, never to a wrong number and never to a block"
      - "races are avoided by construction wherever a design choice can avoid them → **this is the norm that chooses the design.** A shared marker with a widened consumer set would be a race; two slots cannot collide, so the Critic gets its own rather than the PR marker getting a second consumer"
      - "local-first: no network, no daemon, no third-party runtime dependency → conforms; one more small JSON file and one more `git rev-parse`"
      - "the plugin writes nothing into a governed repo except its own `.prawduct/` state → conforms; the marker is `.prawduct/` state and `.gitignore` is a reconciled file"
      - "prawduct is Python but never Python-specific → conforms; a timestamp and a SHA"
      - "prawduct guides and reviews; it never implements → conforms; no product code"
      - "goals and verification bind; prescribed method is advice → engaged: this plan's Chunk 01 deliverables name call sites, and a builder who finds a better seam records why rather than silently relocating"
      - "every fact has one home → **load-bearing here.** `measured_interval_seconds` already IS the one home for the interval predicate, and its own docstring says three readers diverged when it was not. Chunk 01 adds a consumer and adds NO second predicate"
      - "atomic writes everywhere → ruling needed, and Chunk 01 answers it: `review_dispatch.begin` uses a plain `write_text`, not `core.atomic_write_text`. That is pre-existing on the PR path; the Critic path inherits it rather than diverging, and whether BOTH should move is recorded as an out-of-scope observation rather than fixed in a plan that is not about it"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 — cost = unit-cost × run-count, and BOTH are levers (amended 2026-07-29) → **conforms, and this plan is that norm's instrument rather than either lever.** The amendment made unit-cost a declared variable; a variable nobody can measure is not a lever. Every current reading of it is a reviewer's estimate"
      - "the two independent reviews at the PR boundary run in parallel, never sequentially → conforms and is PROTECTED: preserving that concurrency is precisely why the marker is split rather than shared. Stated as its own line because it is the clause this plan's central design decision turns on, though it lives inside the wall-clock norm's statement"
      - "proportionality ratchets both ways; a control that never produces a blocking finding is removed by default, and adding a control names the yield it expects AND emits it observably → ENGAGED, and it cuts in this plan's favour on both halves. Nothing here is a control — no gate, no refusal, no exit code — so the removal clause does not bite; and the norm's SECOND half is the whole point, since a control whose yield nobody can measure is exactly what the review subsystem has been arguing about. The yield is emitted observably by construction: `review-stats` already reports `duration_measured` and `duration_self_reported` separately, so this plan's own effect is readable from the instrument it ships"
      - "state-file growth past its size threshold is an advisory warning, never a hard block → conforms; the new marker is a two-key JSON object with a per-session lifetime (registered in the session-reset delete list), so it does not grow, and nothing here adds a threshold or a block"
      - "review rigor is stage-keyed; the inner stage blocks only on the inner BLOCKING set and the boundary stage runs everything → inapplicable, because no chunk changes a severity, a stage, a review's scope or what any stage blocks on. Named rather than skipped because it is the norm the sibling item #830 would depart from, and this plan deliberately ships the instrument without taking that decision"
  - artifact: observability-strategy
    dispositions:
      - "stable severity-prefix vocabulary with the channel split → conforms; the one new emission is a fail-soft `NOTE:`-class line on stderr, matching `pr-review-dispatch`'s existing degraded-write message"
      - "the governance ledger has a single writer → conforms; `ledger-append` stays the only writer and this plan changes what it FINDS, never who writes"
      - "no prawduct-internal identifier in text emitted into a governed product → conforms; the reason strings name trees and clocks"
  - artifact: api-contract
    dispositions:
      - "additive-first evolution; existing flag names and exit-code meanings never repurposed → conforms; **no new subcommand and no new flag.** `critic-begin` marks internally, so the CLI surface, the exit-code table and every skill grant are untouched"
      - "exit codes are the contract → conforms; `critic-begin` returns exactly what it returns today. A marker that cannot be written is never fatal to the dispatch it precedes"
      - "whole-surface semantic versioning; persisted data independently schema-versioned → conforms; the ledger's `schema_version` stays 1 because `dispatched_at` is an existing optional envelope key"
last_validated: 2026-09-19
---

## Requirements Confidence

**Level:** High

**Why:** The problem is measured, not inferred, and the mechanism already exists and is proven on a
sibling path. Re-derive the measurement with the command in Chunk 01's acceptance criteria rather
than trusting these figures: at plan time the ledger held 1,026 review events of which **2** carried
a measured duration, both `review.pr`; 80% of `duration_seconds` values were multiples of 30s and
23% were exactly `300`, across 63 distinct values. `plugin/lib/telemetry.py`'s own provenance
docstring already states the defect and names this fix — *"making it measurable means timing the
`critic-begin`→`critic-consolidate` interval in code instead of trusting the partial"* — so the
design is the repo's own recorded answer, not a new one. Every module this touches was read before
planning: `review_dispatch.py` whole, `ledger.py`'s `_append_event`, `critic_consolidate.begin_review`'s
dispatch path, and the three registries enumerating the existing marker.

**Open assumptions / unknowns:**

- `[ASSUMPTION: the dispatch→append interval is the wall clock worth measuring for the Critic, including consolidation and any coordinator fan-out — the same span the PR path already measures | MED impact | user can correct]` The alternative is measuring only the reviewers' own spans, which would need N marks for a coordinator roster and would exclude the consolidation the builder also waits through.
- `[ASSUMPTION: no owner appetite for backfilling the 1,024 self-reported rows | LOW impact | user can override]` They stay self-reported and stay counted in their own population, so the two eras are distinguishable by the presence of the key. Backfill is not possible anyway — the clock was never read.
- `[ASSUMPTION: a Critic review's HEAD does not move between critic-begin and ledger-append on the ordinary path | MED impact | verified by the acceptance criteria's live run]` If it does, the tree check refuses the mark and the row degrades to self-reported, which is the correct direction. `critic-begin` already snapshots a tree and an edit under review voids the review, so a moving HEAD is already a defect this does not create.

**What would raise confidence:** Nothing pending. The live run in Chunk 01's acceptance criteria is
the confirmation, and it is cheap because this branch's own review produces the row.

## Status

- [x] Chunk 01: A second stopwatch — the Critic's dispatch mark, and every enumeration that tracks one
- [ ] Chunk 02: The norm the plural marker falsifies, and the prose written over the singular one

**Short plan (2 chunks), so no per-chunk review is inferred** — the boundary `cumulative` on
Chunk 02 is every chunk's review (`review-cycle.md`, "When Review Is Required"). One round, by
construction. This is deliberate and is stated here because the plan is *about* review cost: a plan
that spent four rounds proving reviews cost too much would be its own counterexample.

## The norm departure, recorded

`[DECISION: the dispatch marker becomes one slot PER CONSUMING EVENT KIND, so a `review.critic`
append consumes a Critic marker and never the PR reviewer's | `data-model.md` § Direction's norm
reads "Only `review.pr` appends consume the marker", and its stated why is that a `review.critic`
append clearing a shared marker would silently delete a live PR review's measurement on exactly the
timing where the two overlap. That why is preserved by CONSTRUCTION here and not merely by care:
with one slot per kind there is no shared cell to clear, so the failure the norm forbids is
unreachable rather than avoided. What the norm's statement cannot survive is the shape change — it
is written over a singular "the marker", and after this there are two. The narrow reading (widen
`CONSUMING_EVENT_KINDS` to include `review.critic`) is the reading the module's own comment warns
against in as many words — "A kind added here without that argument re-opens the race" — and this
plan does not take it | user can veto/override]`

**This decision is recorded HERE, in the plan, and the `data-model.md` amendment is Chunk 02's
deliverable — deliberately not the same act.** A governance change cannot supply its own authority,
and a norm amended in the same commit as the code it blesses is indistinguishable from laundering
however sound the substance. The owner's confirmation of this decision is what Chunk 02 cites; if it
does not come, Chunk 01's code is what changes, not the norm.

## Scaffolding

Existing repo — no initialization. Suite: `uv run pytest -q` (the bare `python3` is a different
interpreter on this box); record evidence via `uv run python plugin/bin/prawduct-hook test-evidence
record`. No dependencies added.

### Verification Strategy

Beyond unit tests, this plan has an unusually cheap live check and must not substitute a fixture for
it: **this branch's own boundary review produces the first measured `review.critic` row.** Chunk 02's
acceptance runs `review-stats` afterwards and reads the `measured`/`self-reported` split for the
critic rows. A fixture can only show the plumbing carries a value it was handed; the live run is what
shows `critic-begin` and `ledger-append` agree about a tree across a real multi-minute review with a
real reviewer in between.

**Every degraded path gets a test, and each is red-verified by breaking the subject** — an absent
mark, an unreadable mark, a mark from another tree, git silent on either side. These are the paths
that decide whether absence stays honest, and the module's own docstring says a field whose absence
is ambiguous renders the exact inverse of the signal it was added for.

**A positive control is required before any "this is now measured" claim.** The instrument being
built is a measurement instrument; a test suite that passes against a clock that never ticks is the
failure this plan exists to end. At least one test asserts a NON-`None` measured interval reaches
`review-stats`'s `measured` population, and at least one asserts the *same* fixture reports
`self-reported` when the mark is withheld — the treatment and its control, in one pair.

## Build Chunks

### Chunk 01: A second stopwatch — the Critic's dispatch mark, and every enumeration that tracks one

- **Description:** `review_dispatch` supplies one marker at a fixed basename and one consuming kind.
  Make the slot a function of the event kind: `review.pr` keeps `.pr-review-dispatch.json` at its
  current path (no migration, no consumer change), and `review.critic` gets its own sibling. The
  module's degraded-path semantics — absence is not-measured, staleness is a tree question, a named
  reason for every outcome — are inherited wholesale rather than re-derived, and
  `measured_interval_seconds` stays the single home for the interval predicate with no second copy.
  `begin_review` writes the Critic mark on the path where it actually dispatches — **after** the
  free-interval and budget refusals have had their chance, because a refused round spawns no reviewer
  and marking one would attest an interval nobody spent. A marker that cannot be written is never
  fatal to the dispatch it precedes.
  **Enumerations are part of this chunk, not follow-up bookkeeping:** three places list the existing
  marker by path — `plugin/lib/core.py`, and two in `plugin/bin/prawduct-hook` (one of which is a
  session-reset delete list, so a marker missing from it survives a reset and can attest a stale
  interval) — plus `.gitignore`. A member added to an enumerated set owes its registry a row in the
  same commit.
- **Depends on:** none
- **Artifacts consumed:** `data-model.md` § the three dispatch-marker norms; `.prawduct/artifacts/build-plan-pr-review-payload.md` (the sibling path this mirrors)
- **Deliverables:** `plugin/lib/review_dispatch.py` (per-kind marker path; `begin`/`consume` take the
  kind; `CONSUMING_EVENT_KINDS` and the module docstring restated over a plural marker set — the
  concurrency argument is *kept and strengthened*, never deleted), `plugin/lib/critic_consolidate.py`
  (`begin_review` marks on the dispatching path), `plugin/bin/prawduct-hook` (the two enumerations;
  `cmd_pr_review_dispatch` passes its kind explicitly), `plugin/lib/core.py` (the enumeration),
  `.gitignore`. `plugin/lib/ledger.py` needs no logic change — it already asks `consume` — but its
  envelope docstring says `dispatched_at` is "written only when a `review.pr` append finds a dispatch
  marker", which this makes false, and that sentence is the one a maintainer reads to decide whether
  a key is envelope or payload.
- **Tests:** the positive control (a marked Critic dispatch yields a non-`None` measured interval that
  reaches `review-stats`'s `measured` population) paired with its withheld-mark control on the same
  fixture; the four degraded paths, each red-verified; **the concurrency case the norm is about — a
  live PR mark survives a `review.critic` append, and a live Critic mark survives a `review.pr`
  append**, which is the assertion that makes the [DECISION] checkable rather than argued; a Critic
  mark from a different tree is refused and the row lands self-reported; a refused `critic-begin`
  (free-interval) writes no mark. Port the existing `review_dispatch` cases across the new parameter
  rather than writing fresh ones — the precedent's tests enumerate the branches its design creates.
- **Acceptance criteria:** `review-stats` distinguishes measured from self-reported for `critic/*`
  rows exactly as it already does for `pr/*`; the PR path's behaviour is byte-identical to today
  (its marker path, its consumption, its degraded reasons); no new subcommand, no new flag, no
  changed exit code; the four enumerations and `.gitignore` all carry the new marker; suite green.
  Re-derive the plan's measurement figures with `python3 plugin/bin/prawduct-hook review-stats` and
  a scan of `.prawduct/.governance-ledger.jsonl` rather than quoting this document's numbers.
- **Type:** code
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Change-log entry added (`scope=critic-dispatch-clock`, no `release=`)
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: The norm the plural marker falsifies, and the prose written over the singular one

- **Description:** Chunk 01 makes one ratified norm's statement false while preserving its why. Amend
  it — **on the owner's confirmation of the `[DECISION]` above, cited to where that confirmation
  landed, which is not this artifact** — so the norm binds the plural shape: each consuming kind owns
  its own slot, and the race the norm exists to prevent is unreachable rather than avoided. Then sweep
  the prose written over the singular marker. This is a sweep with a grep, not a memory: search the
  *shape* (the marker's path, `CONSUMING_EVENT_KINDS`, `dispatched_at`) and separately the *claim*
  ("only the PR reviewer", "self-reported"), because a survivor phrased in neither vocabulary is the
  one a single-vocabulary grep leaves standing.
  **The `telemetry.py` provenance docstring is the sharpest case and is named rather than left to the
  sweep:** it currently tells the reader the figure is a median of self-reported estimates and that
  making it measurable "means timing the `critic-begin`→`critic-consolidate` interval in code" — a
  sentence that describes this plan in the future tense and goes false the moment Chunk 01 lands.
- **Depends on:** Chunk 01 (the amendment describes shipped behaviour; writing it first would be the
  amend-to-match-own-code tell with the code not even written yet)
- **Artifacts consumed:** `data-model.md`, `docs/norms.md` (the amendment's required shape)
- **Deliverables:** `.prawduct/artifacts/data-model.md` (the norm amended, with its date, its owner
  attribution and the pointer to where the confirmation landed — never a silent rewrite),
  `plugin/lib/telemetry.py` (the provenance docstring), and whatever the two-vocabulary grep returns.
  `api-contract.md`'s ops list needs a re-read but likely no edit: `critic-begin`'s signature and
  exit codes are unchanged, and a command that also writes a marker is not a surface change.
- **Tests:** the norm-lifecycle guards already covering `data-model.md` § Direction, plus a pin that
  the amended norm still carries the concurrency why — an amendment that keeps the conclusion and
  drops the reason is how the next shape change loses the argument. Any prose guard whose pinned
  sentence moved is renegotiated in the open, never weakened to pass.
- **Acceptance criteria:** no surface still asserts a singular marker or a PR-only consumer; the
  amendment names what changed, why, and whose call it was; the live check runs — `review-stats`
  after this branch's own boundary review shows `critic/*` rows under `measured`, which is the
  treatment, against the 1,024 historical rows as the control; suite green.
- **Type:** doc-only
  <!-- The norm edit is the deliverable; Chunk 01 shipped the behaviour it describes. -->
- **Critic mode:** cumulative
  <!-- Last chunk of a short plan: this one review covers both chunks and is the branch's only round. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Change-log entry added
  3. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  4. Chunk marked `[x]` in Status

## Early Feedback Milestone

**Milestone chunk:** 01
**What the user can do:** run `/prawduct:critic` on anything, then `prawduct-hook review-stats`, and
read a Critic round's duration that no model estimated.

## Governance Checkpoints

**Commit & PR cadence:** feature branch `feat/critic-dispatch-clock` off `develop`; one commit per
chunk. Chunk 02's cumulative makes the branch PR-ready.

- After Chunk 02 (cumulative): confirm the concurrency argument survived the amendment in force and
  not merely in wording, that no degraded path can render a measured-looking wrong number, and that
  the positive control genuinely discriminates — a measurement instrument whose tests pass against a
  dead clock is this plan's own failure mode.

## Out of Scope

- **Backfilling the 1,024 self-reported rows.** Impossible — the clock was never read. They stay in
  their own population, which is what makes the before/after readable at all.
- **Retiring or reinterpreting `duration_seconds`.** The self-reported estimate keeps being written
  and keeps being the fallback on every degraded path. Deciding whether a measured row should stop
  carrying an estimate is a question for after there is data, not before.
- **`core.atomic_write_text` for the marker write.** Pre-existing on the PR path; the Critic path
  inherits it rather than diverging, and moving both is its own small item (recorded here so the
  observation is not lost — it is the kind of thing a reviewer finds and a plan should have named).
- **Anything about what to DO with the measurement** — #167, #830, and whether the 2026-07-30
  per-mode payload cut met its ≤3 min target. This plan builds the instrument; it takes no position
  on the decisions the instrument informs, and deliberately ships before them.
- **A `--json` or report-shape change to `review-stats`.** It already reports the two populations
  separately; this plan changes what falls into which, not how either is rendered.
