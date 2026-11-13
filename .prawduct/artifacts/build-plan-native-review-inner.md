---
artifact: build-plan
version: 2
scope: native-review-inner
branch: feature/native-review-inner
base: develop
working-branches: []
partition: "serial — 02 reads the record fields 01 adds (mode, stage, the range's kind), and both are small enough that a hand-off costs more than it saves"
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → conforms; an inner review's range is named by writing two unreachable commit objects (`git commit-tree`) — no ref, index or working-tree change — and the native review still runs without `--fix`, `--comment` or `--post`"
      - "authority fails closed; advice fails soft → conforms; a range that cannot be named, a sample that misses, or a native run that never lands changes no gate and costs the Critic nothing"
      - "every fact has one home → conforms; the pairing decision stays in `critic_consolidate.native_review_pairing`, the range in one new helper beside it, and the re-raise rule in `compare.py` alone"
      - "guides and reviews, never implements → conforms; measurement only"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 → conforms; nothing waits for the native run at any stage, and naming the range is two local git calls"
      - "review rigor is stage-keyed → conforms, and is why an inner run's findings are not put to the builder (DECISION under Goals): the inner stage blocks only on ships-broken, and a second unrated list beside a `verify-resolutions` pass would manufacture rounds"
      - "proportionality ratchets both ways; a control names its expected yield and emits it → conforms; the yield is the per-stage table `compare.py` prints, and the inner sample ends with #1130's stop"
  - artifact: data-model
    dispositions:
      - "facts immutable and append-only → conforms; the `native.review` event gains fields, appended once per run as before"
      - "no model in a fact's write path → conforms; mode, stage, the range's kind and whether the tree moved are all derived by code"
      - "a newer-schema fact is surfaced, never dropped → inapplicable because the record stays a per-clone ledger event, not an evidence-store fact"
  - artifact: api-contract
    dispositions:
      - "additive-first evolution → conforms; the event gains fields and the manifest block appears on more modes, with no field removed or renamed"
      - "exit codes are the contract → inapplicable because no verb or exit code changes"
depends_on:
  - plugin/lib/critic_consolidate.py
  - plugin/lib/native_review.py
  - plugin/lib/evidence.py
  - .prawduct/research/native-review-paired/compare.py
  - .prawduct/research/native-review-paired/README.md
  - plugin/docs/project-state-keys.md
  - plugin/docs/governance-telemetry.md
  - plugin/skills/critic/review-cycle.md
last_validated: 2026-11-13
---

## Goals

**Response taken:** Proceed, citing it. On 2026-11-13 the owner answered "1. yes file and build,
and let's wait on 2" (`.prawduct/owner-rulings.md`) to a proposal to measure what #1130 does not:
the severity of what each instrument misses (#1164), the inner stage where most correctness review
happens (#1166), and the native review's re-raise rate (#1165). #1166 replaces #1130's scope-out of
`chunk` and `verify-resolutions` reviews. The blind verification waits.

**Product:** #1130's question, sharpened: can the native review own bug-hunting while the Critic
keeps what it judges against plans, specs and test records? The first five paired reviews (all
boundary) say the native review finds more code bugs and the Critic more plan and record defects,
but the data cannot answer the hand-off: it has no severity split, it leaves out the Critic's
observations (so a native finding the Critic demoted counts as native-only), it never sees the
`chunk` and `verify-resolutions` reviews that are most of the Critic's correctness volume, and it
cannot see a reviewer with no memory of dispositions raising the same finding again.

**Architecture:** the Critic is unchanged. The native review stays a second instrument that rates
and blocks nothing.

**Constraints:**
- An inner review usually reads a working tree, not a commit (`head_commit` is null), and the
  native review takes a commit range. The range must still be the Critic's exact interval.
- The native review reads source from the working tree, which the builder may edit after the
  Critic consolidates. A short inner Critic pass (median measured 89s, `review-stats`) ends well
  before a native `high` run (67-99s measured, plus the wrapper).
- Cost. Over the four weeks to 2026-11-13, `prawduct` and `testrouter` ran about 500 inner Critic
  reviews (`chunk` + `verify-resolutions`, `prawduct-hook review-stats --since 2026-10-16` in each).
  Pairing all of them would roughly triple the experiment's native spend.

**Tradeoffs accepted:** each sampled inner review costs a wrapper and a native fork, about the same
as a boundary pairing (`fork_costs.py` over the host-facts session). Worth revisiting if a month's
spend surprises; the sample rate is one constant.

**Decisions made in planning:**
- Inferred: sample one in six `chunk` and `verify-resolutions` reviews, chosen by the review id so
  the choice is code's and reproducible. About eighty runs a month at the current rate, enough to
  reach #1130's sixty within its four weeks. `final` reviews are not paired: they are rare and the
  owner approved the two modes named.
- Inferred: when either end of the interval has no commit, the range is named by two unreachable
  commits — the base tree's (or the real base commit) and the head tree's, parented on the base —
  so `git diff base...head` is exactly the Critic's interval. The commit message names the review
  id and nothing else. Commits are left to `git gc`; nothing reads them after the run.
- [DECISION: an inner run's findings are not put to the builder — no `NEXT-ACTION` clause; its
  text stays readable with `native-review show` | #1130 step 4 has the builder work from the union
  so the experiment costs no missed finding, which the boundary pairing already secures for the
  same code; at the inner stage a second unrated list beside a `verify-resolutions` pass would
  manufacture rounds the stage norm forbids, and would make the next inner run measure the
  builder's reaction to the last one | owner can veto]
- Inferred: `record` notes whether the working tree still equals the reviewed tree when the native
  run lands (`tree_moved`), and `compare.py` warns on each run where it moved, rather than refusing
  the run: a moved tree is likely at the inner stage and still mostly comparable.
- Inferred, the re-raise rule (#1165): a finding in paired review K is a re-raise candidate of an
  earlier finding E when E is from an earlier paired review J in the same repo whose interval
  overlaps K's (same non-null plan scope, else their commit ranges share a commit), E names one of
  its files, and E is either a Critic finding of J with an `accept` or `file` disposition, or a
  native finding of a boundary run of J (the builder saw it). A native finding of an inner run is
  never E: the builder never saw it. Candidates go on the blind sheet as "same defect?"; the
  confirmed ones are re-raises. Both instruments are measured, so the Critic's rate is the
  baseline the native one is read against.
- Inferred: #1130's stop condition counts boundary pairs only, as it did; inner pairs are reported
  beside it.

**Level:** Medium. The synthetic range rests on git semantics (three-dot diff over unreachable
commits) that are certain, and on the native review accepting any commit range, which the boundary
pairing shows for real commits only. The cheapest step that raises it: one live paired inner review
after the dev build advances, read with `native-review show` — the native text should describe the
chunk's diff and nothing else.

## Verification Strategy

Chunk 01 by its tests and by naming a range in a scratch repo with a dirty tree: `git diff
<base>...<head>` over the two synthetic commits must equal the diff from the base tree to the
captured working tree. The live check is the Level's step above, after merge and the
`../prawduct-live` advance. Chunk 02 by known-answer tests and a run over the paired reviews
recorded so far, whose boundary table must agree with the previous run's.

## Build Chunks

### Chunk 01: A sample of inner reviews pairs a native review over the Critic's exact interval

- **Description:**
  - `native_review_pairing` pairs `chunk` and `verify-resolutions` reviews when the review id
    falls in the one-in-six sample, as well as every `cumulative`. Released builds and the opt-out
    are unchanged. An unsampled inner review says nothing new.
  - One helper names the native range: the real commits when both exist; otherwise two unreachable
    commits over the base and head trees. A failure to name one leaves the review unpaired with a
    note, never an error.
  - The sidecar and the `native.review` event carry the review's mode, its stage, whether the range
    is synthetic, and (event only) whether the working tree had moved off the head tree when the
    run was recorded. The event no longer claims every run was a boundary `cumulative`.
  - `next_action_clause` is silent for an inner run (DECISION under Goals).
  - Docs: `plugin/docs/project-state-keys.md` (what pairs), `plugin/docs/governance-telemetry.md`
    (the event's new fields), `plugin/skills/critic/review-cycle.md` (the manifest's
    `native_review` line).
- **Depends on:** none
- **Tests:** red first — a sampled `chunk` and `verify-resolutions` review gets a block, an
  unsampled one none, `final` none; released build and opt-out still none at every mode; a dirty
  tree's range diffs to exactly the captured tree; the event records the mode and stage it was
  given; an inner run's clause is empty and a boundary run's unchanged.
- **Acceptance criteria:** #1166's sample pairs with the Critic's interval; nothing changes on a
  released build or with the opt-out; the reviewer payload budget tests stay green.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed

### Chunk 02: The comparison reads severity, stage and re-raises

- **Description:**
  - `compare.py` matches each native finding against the Critic's findings first, then its
    observations, and tallies per Critic severity (blocking, warning, observation) as well as per
    goal, each split by stage (#1164).
  - The stop condition counts boundary pairs; inner pairs and wall clock are reported per stage.
  - Re-raise candidates by the rule under Goals, on the blind sheet as "same defect?" items whose
    key says which instrument re-raised and what kind of earlier finding it repeats; the report
    prints candidate counts per instrument (#1165).
  - A warning naming each run whose tree moved before it was recorded.
  - The README's monthly procedure and decision table read the new columns.
- **Depends on:** 01
- **Tests:** known-answer — a native finding matching only a Critic observation counts as shared
  under `observation`; an inner pair does not advance the stop condition; a native finding in a
  later overlapping review naming an earlier accepted finding's file is a candidate, and one whose
  earlier review does not overlap is not.
- **Done when:**
  1. Known-answer tests green, and the script run over the paired reviews recorded so far
  2. Committed

### Chunk 03: The boundary review

- **Type:** cumulative-final
- **Description:** change fragment `.prawduct/changes/native-review-inner.md`; suite green on the
  head, recorded; the boundary cumulative review.
- **Depends on:** 01, 02
- **Done when:**
  1. Suite green on the head, recorded
  2. Cumulative review with no unresolved blocking finding
