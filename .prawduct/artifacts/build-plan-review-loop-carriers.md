---
artifact: build-plan
version: 2
scope: review-loop-carriers
depends_on: []
last_validated: 2026-08-04
---

## Requirements Confidence

**Level:** High

**Why:** The problem was measured, not inferred — two evidence stores and one full
consumer transcript, all on the released v3.2.3. The parent requirement (#167,
CRT-3W6P) already states the design constraint this plan honors, and the owner chose
the scope directly (layers 1+2; both sides on numbers) after seeing the measurement.

**Open assumptions / unknowns:** none that change the build.

**What would raise confidence:** N/A — the next real signal is post-release telemetry
(`prawduct-hook review-stats`), not more design.

## The problem, measured

The framework's loop-termination rule **shipped correctly in v3.2.3** and does not
reach the actor who needs it.

`methodology/building.md` "Resolve findings" and `skills/critic/review-cycle.md`
§ "The review loop terminates" both say the right thing: zero blocking ends the review,
WARNING/NOTE gate nothing, batch every fix into ONE commit, accept is the default. In
the consumer session that ran ten Critic rounds on one branch, the builder read
**neither file** (zero occurrences of either path in the transcript) and never invoked
`/prawduct:methodology`. It never entered the build cycle at all, because the branch
had no build plan — `record_lint` recorded exactly that: *"no build plan under
artifacts/ declares [this scope]"*.

Every carrier of the rule is a **pull** carrier:

| Carrier | Read by | Reached the builder |
|---|---|---|
| `methodology/building.md` § Resolve findings | a builder entering a build plan | no — no plan existed |
| `skills/critic/review-cycle.md` § The review loop terminates | nobody in the builder role | no |
| `_BATCH_FIX_DIRECTIVE` (`critic_consolidate.py`) | whoever runs `critic-consolidate` | **no — 7 reviewer-fork contexts, 0 builder contexts** |

The directive's own docstring already records why (the comment above
`RESOLUTION_IS_A_CLAIM_DIRECTIVE`):
*"Nor does it carry to the builder: the Critic skill is `context: fork`, and the fork's
report-back instruction enumerates findings and a summary, not the consolidator's
stdout."* On the single-pass path the reviewing fork runs consolidate itself, so the
one runtime carrier prints into the reviewer's context and dies there.

Meanwhile both **push** carriers that do reach the builder at the decision point say
*review again*: `check-cumulative-critic`'s `uncovered:` stderr (`gates.check_cumulative_critic`)
names two remedies, both full reviews; and findings arrive carrying `recommendation` text
with no statement of what gates.

**Scale, from the evidence stores since the v3.2.3 tag (2026-08-02):**

| | discodon | prawduct |
|---|---|---|
| review facts | 92 | 96 |
| findings | 806 | 618 |
| blocking | 30 (3.7%) | — |
| zero-blocking `verify-resolutions` rounds | 60 of 92 | 45 of 96 |
| longest consecutive chain | 9 | 4 |

Five of the ten-round session's nine `verify-resolutions` invocations open with
*"close coverage to committed HEAD"* — reviews run to satisfy a gate, not to get review
value. That is the signature this plan targets.

**The second half is supply.** A round that runs still has to find nothing new to fix,
or it manufactures the next one. `verify-resolutions` today runs Goals 1-3 over the fix
delta and rates what it notices at any severity, so round N+1 reliably hands the builder
new WARNING/NOTE work — and the review's own change-log and record prose is the surface
it walks. The narrowest recurring instance is the contestable count: roughly one finding
in eleven across that window is count-shaped, and `goals-1-3.md`'s chunk-`Type:`
paragraph actively directs doc-only Goal 1 at *"prose and numeric counts"*.

## Requirements

| Req | Source | This plan |
|---|---|---|
| R1 — the exit condition reaches the builder without depending on a file the builder may never open | #167 ("nothing detects an agent running round N+1 against an already-passing gate") | Chunk 01 |
| R2 — the gate that reports the gap distinguishes fix churn from new work, and names the disposition escape | #167 ("the discriminator is what moved the tree between rounds") | Chunk 01 |
| R3 — a re-review cannot manufacture non-blocking work | #167 open question 3 ("whether verify-resolutions should review the delta at all") | Chunk 02 |
| R4 — inert contestable counts stop generating correction rounds, on both the writing and the reviewing side | the numbers item filed 2026-08-04 | Chunk 03 |

**Out of scope, deliberately:** #167's `critic-begin` *refusal*. Refusing a round leaves
coverage open with no path to close it — the PR gate then blocks with no remedy, which
is a worse failure than the loop. The refusal needs a paired coverage-closing route
designed first; this plan makes the loop terminate without needing it.

## Status

- [x] Chunk 01: The exit condition and the fix-churn diagnosis reach the builder
- [ ] Chunk 02: `verify-resolutions` adjudicates; it does not re-review
- [ ] Chunk 03: Contestable counts, on both sides

Context: Plan authored 2026-08-04 on `fix/review-loop-carriers`, cut from `develop` at
`dbb42f3`, after reading the ten-round consumer transcript and both evidence stores.
Parent requirement #167 (CRT-3W6P) stays open — its structural-refusal half is
explicitly out of scope here.

Chunk 01 is built and green (suite passes; the fix-churn NOTE and `next_action` both
verified against a scratch repo, not only unit tests). One design change during the
build, worth carrying: the gate line is **code-owned** (`next_action_line`) and the
protocols only order it relayed, rather than each quoting both variants. That was
forced by the two protocol files sitting at their token ceilings — and it is the better
shape anyway, since the builder now meets the same sentence whether they read the fork's
report or `next_action`. Neither ceiling was raised; both additions were funded by
trims the files' own budget comments had designated. Next: Chunk 02.

## Verification Strategy

Every chunk is verified by running the changed command against a real repo state, not
only by unit test: `prawduct-hook critic-consolidate` on a fixture review to read the
emitted `next_action`, and `prawduct-hook check-cumulative-critic` on a branch whose only
delta is a fix commit, to read the fix-churn NOTE. Prose changes to a fork-read protocol
are pinned by test, because nothing else can observe them.

## Build Chunks

### Chunk 01: The exit condition and the fix-churn diagnosis reach the builder

- **Description:** Make the two push carriers the builder actually meets carry the rule.
  The findings cache is read by the builder by contract, so what gates goes *in* it,
  computed in code. The `uncovered:` gate message is the exact decision point, so it
  learns to say when the gap is the builder's own non-blocking fixes.
- **Depends on:** none
- **Deliverables:**
  - `plugin/lib/critic_consolidate.py` — `fact_to_cache_record` gains `next_action`,
    derived from the fact's own severity counts. Blocking present: fix them, batch into
    ONE commit, ONE `verify-resolutions`. Zero blocking: the review is over, and the
    line names `prawduct-hook disposition <fact_id> <fid> --accept "<reason>"` with its
    own review id already substituted.
  - `plugin/lib/coverage.py` — new `diagnose_fix_churn`: the newest review fact on
    HEAD's lineage, with zero unresolved blocking, whose judgeable delta to HEAD is
    confined to files that review's own findings named.
  - `plugin/lib/gates.py` — the `uncovered:` branch prints the fix-churn NOTE before the
    generic remedy, in the slot the stale-remote-base NOTE already established.
  - `plugin/skills/critic/goals-1-3.md` and `plugin/skills/critic/review-protocol.md` —
    the report-back contract gains a required closing line stating the gate verdict, so
    the fork's returned summary carries it even when the builder reads no file.
- **Tests:** unit — `next_action` for each severity shape; `diagnose_fix_churn` returns
  None for a genuine outside change (the #167 counter-example: a merge widening the delta
  past the named files) and a diagnosis for a pure fix commit; a fact with unresolved
  blocking never diagnoses as churn. Prose pins for both protocol files.
- **Acceptance criteria:** a builder that reads only `.critic-findings.json` learns the
  review is over and how to accept; a builder that runs only the gate learns its gap is
  self-inflicted and how to close it without another full review.
- **Type:** code
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: `verify-resolutions` adjudicates; it does not re-review

- **Description:** Round N+1 exists to answer one question — were the named findings
  resolved? Today it also walks the fix delta at full severity and hands back new
  WARNING/NOTE work, which is round N+2's supply. Narrow it: new findings in
  `verify-resolutions` are **BLOCKING only**; anything else the reviewer notices is
  reported as an advisory observation in prose, where it informs without becoming work.
- **Depends on:** Chunk 01
- **Deliverables:**
  - `plugin/skills/critic/goals-1-3.md` — a mode-conditional section: what
    `verify-resolutions` rates and what it demotes to observation. The classes that
    matter in a fix delta are already BLOCKING-rated (weakened tests, dropped
    requirements, untested changed behavior, security, fix-by-fudging) and stay so.
  - `plugin/lib/critic_consolidate.py` — a dispatch-time directive beside
    `RESOLUTION_IS_A_CLAIM_DIRECTIVE`, printed by `critic-begin` for this mode, stating
    the narrowing where the reviewer meets it.
  - `plugin/skills/critic/review-cycle.md` — the per-mode table and the termination
    section record the narrowed contract.
- **Tests:** prose pins that the mode-conditional rule exists and that the BLOCKING
  classes are named; a directive test in the shape of `TestResolutionIsAClaimDirective`.
- **Acceptance criteria:** a `verify-resolutions` pass over a clean fix delta records
  zero findings and the gate passes — there is no round N+2 to generate.
- **Type:** code
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: Contestable counts, on both sides

- **Description:** Stop the exchange at its source and cap it at its sink. A count that
  nothing reads is not worth a commit, and a reviewer who corrects one should say so in
  the finding rather than leave the builder to infer it.
- **Depends on:** Chunk 02
- **Deliverables:**
  - `plugin/methodology/building.md` — the builder-side norm, beside the existing
    self-contained-comments rule: don't write a contestable count where the number is
    inert; omit it, qualify it, or cite the query that regenerates it. Load-bearing
    numbers stay exact.
  - `plugin/skills/critic/goals-1-3.md` — drop `numeric counts` from the doc-only Goal 1
    line; add the severity cap: a finding whose only subject is a count in inert prose is
    a NOTE and must carry the inert qualifier (true figure, that nothing reads it, and
    that no edit is wanted).
  - `plugin/skills/critic/review-protocol.md` — the same cap in the severity contract.
- **Tests:** prose pins on all three files, including that `numeric counts` no longer
  appears as a doc-only Goal 1 target.
- **Acceptance criteria:** the doc-only protocol no longer directs reviewers to hunt
  counts; a reviewer correcting an inert count produces a NOTE that tells the builder not
  to change it.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then ONE `/prawduct:critic cumulative` — it is this chunk's review and
     the PR gate's evidence
  3. Chunk marked `[x]` in Status
