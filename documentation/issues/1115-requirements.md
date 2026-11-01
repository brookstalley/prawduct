# Issue #1115 — telemetry: roll up review stats across clones: Requirements

`status: draft · stage: requirements · area: governance/telemetry · added: 2026-11-01 · source: user · issue: https://github.com/brookstalley/prawduct/issues/1115`

Related: #1058 (ingested reviews counted twice by `stats` and `contribute`), #1061 (evidence-transport polish), #1050/#1052 (review facts travel as git notes), #263 and #941 (the disposition join into `review-stats`), #1063 (opt-out switch for the transport).

## Problem

Dispositions (`accept` / `file` / `fixed` answers to findings) are recorded as `disposition` facts in the clone-shared evidence store (`plugin/lib/dispositions.py`). `disposition` is in `KNOWN_KINDS` but not in `TRANSPORTED_KINDS` (`plugin/lib/evidence.py`), so only `review`, `resolution`, `chunk-imported` and `chunk-retracted` ride `refs/notes/prawduct`.

The cost: every number that joins findings to their outcomes — `review-stats` outcome rates, `stats` benefit figures, round tallies, the disposition census — is computed from one clone's store. A second clone sees the branch's reviews and resolutions (ingested) but none of its dispositions, so the same finding reads `undispositioned` there. Found in the 2026-10-28 two-clone transport tests: a fresh clone ingested 2 reviews and 3 resolutions and none of the dispositions.

Nothing is wrong at a gate today (a disposition can never weaken a gate; no gate reads them). The loss is in measurement. The owner's direction (2026-10-28): roll stats up across clones, and maybe store them somewhere, in the future.

## Goals

- G1. A stats report run in any clone that holds a branch's reviews reports the same finding outcomes for that branch as the clone that decided them.
- G2. No review, finding or disposition is counted more than once because it was seen by more than one clone or arrived by more than one route (live write, notes ingest, contribute bundle).
- G3. No gate behaviour changes. Whatever carries dispositions stays observational: it is left out of `coverage_fingerprint` like the other observational kinds, and the safety property in `dispositions.py` (a disposition never weakens a gate) still holds and is still pinned by test.
- G4. The privacy contract of `contribute` is unchanged: a report carries no identifier, text or fine-grained time.

## Non-goals

- A hosted collector or dashboard. "Store them somewhere" is a later decision; this item defines what a cross-clone figure *means*, not where it is kept.
- Aggregating across products. Rollup is across clones of one product.
- Changing disposition vocabulary (`action`) or the census rendering.
- Fixing #1058 itself. It is a prerequisite (see R5), not part of this item.

## Requirements

- R1. **Choose the rollup route.** Candidates:
  - **A. Transport dispositions as notes.** Add `disposition` to `TRANSPORTED_KINDS`; `evidence sync` carries them with the review they answer. Every existing report (`review-stats`, `stats`, census) then becomes cross-clone for free, and the fix is one kind plus the anchoring rule. Cost: a disposition is a builder's reasoning ("accepted because…"), possibly free text, and the notes ref is readable by anyone who can fetch the remote, which is the trust question #1063 raises. It also grows the notes payload (see the size probes in `evidence_size_probes.py`).
  - **B. Aggregate at a collector via `contribute`.** Dispositions stay local; weekly anonymous bundles carry outcome *counts*. Keeps free text off the remote. But a bundle is anonymous by design (no install id), so the collector cannot tell two clones of one product from two products, and it cannot rejoin a finding to its outcome. It yields population rates, not "this branch's outcomes in my clone".
  - **C. Transport only a derived outcome, not the fact.** A transported kind carries `{review_id, fid, outcome}` with no reason text. Gives G1 without the free-text exposure. Adds a kind and a derivation step that must agree with `stats.finding_outcome`.
  Recommendation to confirm: **C** for in-product rollup (G1), leaving **B** as the route for cross-product population figures, which it already is. A is simplest but exposes reasons on the remote.
- R2. Whichever kind travels, it anchors to the commit of the review it answers (`evidence.review_anchor`), so it rides the same note as that review and is fetched with it. A disposition whose review is not in the receiving clone is held, not dropped, and applies when the review arrives (the order of arrival is not the order of decision).
- R3. A transported outcome and a locally recorded disposition for the same `(review_id, fid)` resolve by the same rule `dispositions.finding_state` uses today (newest answer wins, per-finding sequence in the id). Ingest must not reorder or overwrite a clone's own answer with an older foreign one.
- R4. The new kind is added to `OBSERVATIONAL_KINDS` if (and only if) `coverage_verdict` cannot see it. This is checked, not assumed: a test feeds a store whose only difference is the new facts and asserts the coverage verdict and fingerprint are unchanged.
- R5. **Double-count safety first.** Before any rollup figure is published, every reader that sums over the store (`stats`, `review-stats`, `contribute`) counts an ingested review once, by fact id. This is #1058's acceptance; R5 makes it a precondition of this item and a regression test here (same fact present via two routes counts once).
- R6. Reports label their basis: the header says whether figures cover "this clone only" or "this clone plus ingested", with the count of ingested reviews, so a reader can tell a rolled-up rate from a local one. A report over a store with no ingested facts is byte-for-byte unchanged.
- R7. `contribute` windows are unaffected by ingestion: a week's report counts a review in the window of its own timestamp, whichever clone wrote it, and a bundle already sent is never re-sent because a later sync brought in more facts for an old week. (Settle window and dedupe record are the existing mechanism; this requirement pins that they are not bypassed.)
- R8. Tests per behaviour, each red-verified against the current code: (a) two-clone round trip yields equal outcome tallies; (b) disposition arrives before its review; (c) local newer answer survives an older foreign one; (d) the same review via notes and via local write counts once; (e) coverage verdict and fingerprint unchanged by the new facts; (f) a sent contribute week is not re-offered after a sync.

## Acceptance

- Clone A reviews a branch and dispositions a finding; clone B runs `evidence sync` and `review-stats`: B reports the finding with A's outcome, and the totals match A's.
- Re-running sync, or ingesting the same notes twice, changes no figure.
- `prawduct-hook stats` and `review-stats` in a single-clone product print what they printed before.
- No coverage verdict, fingerprint or gate result differs with and without the transported facts.

## Open questions for the owner

- Q1. Confirm C over A (outcome only, no reason text) for what travels. If reasons must travel, A needs the #1063 opt-out first.
- Q2. Is "ingested but undecided" (review present, no disposition anywhere) a distinct state in reports, or does it keep reading `undispositioned`?
- Q3. Does "store them somewhere" mean a collector is wanted soon? If so, the in-product rollup (this item) and the `contribute` path should share one outcome derivation so the two never disagree.
- Q4. Sizing: C is likely M (one kind, anchor rule, ingest merge, labelled header). If R1 lands on A it drops to S, and if a collector joins it is L.

## Next step

On confirmation of Q1–Q3, write the design: the shape of the transported outcome fact, where `evidence_notes` ingest applies the hold-until-review rule, and how `stats`/`review-stats` take the basis label without changing single-clone output.
