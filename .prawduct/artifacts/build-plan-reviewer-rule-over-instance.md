---
artifact: build-plan
version: 1
scope: reviewer-rule-over-instance
governed_by:
  - artifact: nonfunctional-requirements.md   # § Direction — review cost is unit-cost × run-count
    dispositions:
      - "Review wall-clock is a P0 constraint: this plan is the run-count lever, and pays for its
         own unit-cost in place — review-cycle.md's ceiling holds at 9600 rather than rising."
last_validated: 2026-08-11
---

# Build plan — Reviewers file the rule, not the Nth instance

**Scope:** `reviewer-rule-over-instance`
**Size:** small · **Type:** debt paydown
**Critic mode:** final
**Requirements confidence:** High — the parent norm is ratified and the evidence is measured.

## Context

An audit of 141 PR-review evidence records across 7 repos (2026-08-10) hand-classified all 43
post-scope-down warnings. 8 of 43 (19%) were stale-figure or citation drift — a count or a citation
pinned in prose that went stale. The rule against writing them already exists in three places:

- `plugin/methodology/building.md:87` — "a count nothing reads is not worth writing … make it
  relational … or cite the command that regenerates it."
- `.prawduct/learnings.md:358` (2026-07-31) — "the fix is not counting more carefully but moving the
  count out of prose entirely."
- `.prawduct/learnings.md:400` (2026-08-02) — "prefer a relational statement over a literal count."

The reviewers filed per-instance findings on 2026-08-03 and 2026-08-06 anyway, and the 08-06 one
**cites the learning while filing the instance**. Each such finding buys a review round.

## Requirements

**R1 — A reviewer that recognises a finding as a repeat of a rule already in `learnings.md` reports
the unmechanized rule once, not the instance.**

Parent: `nonfunctional-requirements.md` § Direction — *"Review wall-clock is a P0 constraint:
cost = unit-cost × run-count, and both factors are levers — run-count via gate and chunk
structure."* A recurring finding class that is re-filed per instance is run-count the structure
never removes. This requirement is an implementation of that ratified norm, not a new one.

**R2 — The instruction must not become a licence to drop findings.** Naming the rule is a
*substitution* for the instance, not a suppression of it: the reviewer still reports, at the same
severity, but reports the rule's unmechanized state once rather than each occurrence.

## Out of scope (declared, not dropped)

- **Restoring a `dangling-ref` / citation lint.** `plugin/lib/record_lint.py:59-75` records that this
  check was built, measured (3 findings, 0 true positives) and removed under
  `nonfunctional-requirements.md` § Direction ("a control that fires and catches nothing is removed
  by default"), and that re-adding it needs *evidence that the class costs review rounds*. **This
  audit does not supply that evidence**: of the two citation-drift warnings, one (W19) is in
  `backlog-archive.md`, which every check excludes by design, and the other (W25) is a wrong *symbol
  name*, which a path-resolution check would not catch. The bar stands unmet; the check stays out.
- **Widening `suite-total-claim` to two-digit counts.** The regex comment
  (`record_lint.py:81-97`) excludes them deliberately, reasoning that a two-digit figure is nearly
  always a scoped or delta count and a tripwire that fires on "a total of 25 backlog items" gets
  ignored. One true positive (a stale "(27 tests)") does not outweigh a documented false-positive
  argument.
- **A `test-count-lag` check** (`project-state.yaml` `test_tracking.test_count` vs recorded
  evidence). New scope, so **filed as #633** rather than left here — a plan gets archived, and a
  deferral recorded only in an archived plan is a drop with extra steps (`learnings.md:360`). Filing
  it turned up more than the deferral did: prawduct **removed** `test_count` as computed-not-tracked
  (`lib/briefing.py:172`), so the field is residue in 11 sibling repos, and in all 4 that also hold
  `.test-evidence.json` it disagrees with recorded `passed + skipped`. The item therefore carries
  **both directions** — build the check, or delete the field under the same "a control that fires and
  catches nothing is removed by default" norm this plan invoked to keep `dangling-ref` out. It is
  `stage: research` because the disagreements are not uniformly errors (one repo documents a
  deselection offset; another's *evidence* is the stale side), so a naive equality check would be
  wrong in both directions.

## Chunks

- **Chunk 01 — the instruction, in both cross-check owners.** Add R1/R2 to the Critic's Learnings
  Cross-Check (`plugin/skills/critic/review-cycle.md`, the `final`/`cumulative` owner) and to the PR
  reviewer's Learnings Cross-Check (`plugin/skills/pr/review-protocol.md`), which currently says a
  reintroduced pattern is "a WARNING at minimum" and gives no route to the rule.

  *Done when:* both protocols carry the instruction; the two files agree on who reports what; the
  change-log entry is written; `/prawduct:critic` passes with no unresolved blocking findings.

## Appendix — reproducing the audit

The 19% figure and the classification behind it are the evidence for R1, so the method has to
outlive the scratch scripts that produced it. Corpus: every
`/Users/brookstalley/source/*/.prawduct/.pr-reviews/*.json` (141 records, 7 repos — discodon,
hallucinote, prawduct, discodon-evals, discodon-offline, discodon-brooks2, trenchant). Each record
carries `timestamp`, `branch`, `findings[]` with `severity`/`goal`/`file`/`summary`, and (since
2026-06-10) `duration_seconds`.

Three cuts, in order:

1. **Era split at 2026-06-10** — PR #88 (`Review proportionality: telemetry, risk escalation, scoped
   PR review`) rescoped the goal set. Findings whose `goal` names bugs or tests drop to zero after
   it, so pre-#88 records answer a different question and are excluded.
2. **Severity filter** — `warning` + `blocking` only (43 post-#88). Notes were read but not
   classified; they are 75% of volume and carry the same shape.
3. **Hand classification**, not regex. A keyword pass put 42% of warnings in a "mechanizable" bucket;
   reading them dropped it to ~12%, because the biggest apparent group — stale test evidence — turned
   out to include three cases where `prawduct-hook test-status` exited **0** and the reviewer caught a
   *coverage* gap the hook cannot see. **Any re-run that classifies by keyword will reproduce the
   wrong number.**

Counts as classified: 25 substantive · 8 stale-figure/citation drift · 3 borderline · 4
cosmetic · 2 redundant-with-Critic · 1 no-action. The drift bucket over the total 43 is the 19%.

**A caveat that bounds all of it:** finding *correctness* was never independently verified.
`prawduct-hook render-dispositions` shows PR findings are effectively never dispositioned, so the
false-positive rate is unmeasured, and the corroboration is indirect — ~78 commits across the
siblings whose subjects cite a PR-review finding as their reason to exist.

## Status

- [ ] Chunk 01 — the instruction, in both cross-check owners

**Context:** Next is Chunk 01. Nothing built yet.
