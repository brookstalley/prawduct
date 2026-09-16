---
artifact: build-plan
version: 2
scope: transfer-denial-voice
# branch: fix/transfer-denial-voice   <- uncomment when the branch is created
partition: serial — Chunk 03 builds on Chunk 01's denial reason, and Chunk 02 is the design Chunk 03 needs
program: consumer-overhead-program-2026-09.md (WS5)
depends_on:
  - "fix/coverage-honesty merged to develop (program Owner decision 2) — Chunk 01 is that plan's split-out Chunk 03"
related_issues:
  - "brookstalley/prawduct#672 — Half 2 (the transfer is denied by any conflict resolution) and the diagnostic wording. Half 1 (superseded blocker) is NOT here; it goes with #768 and #334 leg 2 in a later wave"
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "a control emits its yield observably → ENGAGED: Chunk 01 gives the denial outcome a record"
      - "no miss-rate increase is accepted for round count → ENGAGED: Chunk 03 may extend the transfer only where the tolerated edit is to non-judgeable paths, which no review would rate"
  - artifact: data-model
    dispositions:
      - "guard-refusal facts observational, `guard` as grouping key, interval nested under `interval`, single sink → conforms (Chunk 01, as specced)"
  - artifact: observability-strategy
    dispositions:
      - "stable severity-prefix vocabulary, stdout/stderr split → conforms"
last_validated: 2026-09-16
---

# Build plan — the base-advance transfer explains itself, then tolerates prose conflicts

## Requirements Confidence

**Level:** Low for Chunks 02–03. High for Chunk 01.

**Why:** Chunk 01 has a written spec: `build-plan-coverage-honesty.md` Chunk 03, on the unmerged
branch `fix/coverage-honesty`. Chunk 03's rule is one of three candidate directions in #672, and
no choice has been made.

**Open assumptions / unknowns (Chunk 02 must close these):**
- Q1: which conflict edits may the transfer tolerate? Non-judgeable paths only (per
  `coverage_algebra.judgeable_files`), or also judgeable paths whose post-resolution content equals
  one of the two parents?
- Q2: what does the transfer compare after tolerating the conflict? The judgeable subset of the
  diff must be byte-identical to the reviewed diff. Is that sufficient, given the base's own trees
  are covered by facts in the shared store?
- Q3: does a tolerated transfer record a grant under the existing `record_transfer_grant`, or a
  distinct grant kind a yield query can separate?
- `[ASSUMPTION: Q1 answers "non-judgeable paths only" | HIGH impact | user can widen]` — the
  narrowest reading, and the one both field reports need (CHANGELOG / change-log / preferences /
  CONTRIBUTING conflicts).

**What would raise confidence:** Chunk 02's design doc, reviewed by the owner.

## Status

- [ ] Chunk 01: The transfer's silent denial gets a reason and a record
- [ ] Chunk 02: Design — tolerate conflict resolutions confined to non-judgeable paths
- [ ] Chunk 03: Build the tolerated transfer
Context: Drawn 2026-09-16. Blocked on `fix/coverage-honesty` reaching develop. Field cost: ~11 min
and ~1h, from two independent reports on #672.

## Chunk 01: The transfer's silent denial gets a reason and a record

- **Description:** Build the spec at `build-plan-coverage-honesty.md` Chunk 03 (as it reaches develop
  with that branch) verbatim. A denial returns a reason from `coverage.diagnose_base_advance_transfer`
  instead of `None`. `gates.transfer_remedy` says "denied: <reason>" instead of "could not run". A
  denial record is span-deduped on the grant path's key through `evidence.append_guard_refusal`.
- **Deliverables / Tests / Acceptance:** as that spec, including its positive control (a span that
  should grant still grants and records).
- **Done when:** acceptance passes; `/prawduct:critic`; tick; mark the coverage-honesty plan's Chunk 03
  as built here.

## Chunk 02: Design — tolerate conflict resolutions confined to non-judgeable paths

- **Type:** doc-only
- **Description:** Write `documentation/issues/672-half2-design.md` answering Q1–Q3 against the
  current `diagnose_base_advance_transfer`. It must include: the exact predicate; why it cannot let an
  unreviewed judgeable byte through (a counter-example search, not an assertion); the grant record
  shape; the test plan. Use the hallucinote report (3 prose files resolved, 60 files lost coverage)
  as a worked example.
- **Deliverables:** the design doc; #672 updated with Half 2 split out (the issue's own triage
  recommends the split).
- **Acceptance criteria:** the owner has answered Q1–Q3 on the issue or in the doc.
- **Done when:** doc committed; owner answer recorded; `/prawduct:critic`; tick.

## Chunk 03: Build the tolerated transfer

- **Type:** cumulative-final
- **Description:** Implement Chunk 02's design. Scope and tests come from that design. This entry is
  deliberately a placeholder until Chunk 02 is accepted; re-draw it then rather than building from
  this line.
- **Done when:** commit; one `/prawduct:critic cumulative`; tick.
