---
artifact: discovery
scope: gate-as-dispatcher
status: requirements
date: 2026-08-06
---

# Requirements — Gate as Dispatcher

## 1. The problem, observably

Critic review rounds are dispatched by **protocol habit**; coverage is decided by **algebra**. The
two never talk. `coverage_algebra.is_judgeable_path` already classifies which paths need review
coverage, and `coverage_verdict` already grants **free edges** for intervals holding no judgeable
content — but that predicate is consulted only when *grading* coverage after the fact, never when
*deciding to spend* a review. It is a predicate used as an auditor instead of as a scheduler.

`check-cumulative-critic` can tell you a round was unnecessary. It can only tell you **after** you
have paid for it.

### The observation that started this

On `fix/backlog-import-title-boundary` (merged, PR #615), rounds 3, 4, and 5 were dispatched after
three consecutive docs commits. All three were provably unnecessary on two independent grounds:

```
round 3: 27a00fc..f76e603 — 2 files, judgeable=NONE -> FREE EDGE
round 4: f76e603..a15f7e8 — 5 files, judgeable=NONE -> FREE EDGE
round 5: a15f7e8..90f6744 — 1 file, judgeable=NONE -> FREE EDGE
```

and all three returned `{blocking: 0, warning: 0, note: 0}`. Coverage composed across all three
without any review fact. Nothing demanded them — not the stop hook, not `check-cumulative-critic`.

### Scale (re-derive; do not cite these digits)

Classifying every review fact in `.git/prawduct/evidence.jsonl` by
`coverage_algebra.is_judgeable_path` over its recorded `files_changed`:

| | free-edge reviews | judgeable reviews |
|---|---|---|
| count | 62 of 492 (12.6%) | 430 |
| blocking / review | 0.08 | 0.28 |
| found nothing at all | 23% | 16% |

~5.2 opus-hours at the 300s verify-mode median.

**Do not overstate this.** Free-edge reviews are *not* worthless — 5 blockers, 79 warnings and 69
notes across the 62. They are **mispriced and misplaced**: merge-blocking rounds producing
advisory-grade findings on prose that the same framework waves through at the PR boundary via
`check-pr-doc-only`. The argument is about where they sit in the loop, not about deleting them.

## 2. Root cause — the precise predicate

All of rounds 2–5 ran in `verify-resolutions` mode. Round 2 was **legitimate**: it verified the
resolutions of the 5 blocking findings from round 1. Rounds 3–5 followed *clean* rounds, so they had
no findings to verify **and** no judgeable content to judge. That distinction is the whole design:

> **Refuse to dispatch iff the interval holds no judgeable file AND there are no unresolved blocking
> findings this review could resolve.**

Both conjuncts are load-bearing:

- Drop the first and you refuse reviews of real code.
- Drop the second and you **deadlock the gate**: a `blocked` verdict's only remedy is a
  `verify-resolutions` pass, so refusing that pass would leave the findings unresolvable forever.

Applied retroactively, the predicate refuses rounds 3, 4, 5 and dispatches rounds 1, 2, 6, 7 — the
exact split the evidence supports.

## 3. Success criteria (verifiable)

1. A dispatch whose interval holds **no judgeable file** and which has **no unresolved blocking
   findings to resolve** does not spawn a reviewer; it returns in well under a second with a message
   naming the free files and the override.
2. A dispatch whose interval holds **≥1 judgeable file** always proceeds — including one judgeable
   file among many non-judgeable ones, and including governance-protected `.md`
   (`skills/`, `methodology/`, `templates/`, root `CLAUDE.md`), which **is** judgeable.
3. A dispatch that could resolve unresolved blocking findings always proceeds, even over an entirely
   free interval. No input wedges the gate.
4. Anything the check cannot compute (diff failure, unreadable tree, missing store) **dispatches**.
   Uncertainty never buys a skip.
5. An explicit override forces a review regardless.
6. `check-cumulative-critic`'s verdict is unchanged by this work for every input. The refusal must
   never widen what can merge.

## 4. The safety argument (why this is not a new escape hatch)

**The dispatcher may refuse only what the gate would already pass.** Same predicate, same inputs,
moved upstream of the cost. A refused review is one whose absence `check-cumulative-critic` already
tolerates via a free edge — so the refusal grants nothing that was not already granted, and no
unreviewed judgeable content can reach a merge through it.

This is the distinction from `#292 / CRT-9R4K` ("defer per-chunk reviews on short plans"), which is
**not** this item: that proposal trades early detection for wall-clock and needs a user judgement
call on blast radius. This one trades nothing — a free interval has no judgeable content to detect a
defect in. It should not be conflated with #292 or blocked on it.

Governing norm engaged — *architecture.md*, **"Authority fails closed; advice fails soft."** This
change is authority-adjacent, and it conforms: the refusal does not produce a merge verdict, it
declines to spend a reviewer, and every uncomputable input falls through to dispatching.

Governing norm engaged — *nonfunctional-requirements.md*, **"Proportionality ratchets both ways…
adding a control names its expected yield and emits it observably."** The mirror obligation for
*removing* a control's firing is the same: §1's measurement is that recorded argument, and
Chunk 2 makes the refusals observable rather than silent.

## 5. Scope

**In scope**

- The refusal predicate at dispatch, in `critic-begin` / `critic_consolidate.begin_review`.
- A distinct exit code so the skill can distinguish "no review needed" from "dispatch failed".
- The prose surfaces that actively teach the treadmill (§7).
- Observability: refusals are recorded, so the yield claim stays falsifiable.

**Out of scope, deliberately**

- **Scoping the review payload to the judgeable subset.** This was in the original three-layer
  sketch and is **withdrawn on evidence**: round 6 of the merged branch caught a change-log sentence
  asserting coverage the code did not have. A reviewer handed only the `.py` files could not have
  found it. Doc/code coherence is exactly what the full interval buys, and the payload is not where
  the measured waste is.
- **Taking prose review off the blocking path.** A policy change with real risk; layer 1 captures
  100% of the measured waste (the 62 reviews were classified by precisely this predicate), so this
  should wait for evidence it is still needed.
- **Refusing when a prior fact already covers a *judgeable* interval** (the full
  `coverage_verdict == covered` variant). Strictly broader than the free-interval rule and not
  supported by any measurement yet — how often a genuinely-judgeable interval is re-reviewed is
  unmeasured. Measure before building.
- Changing `is_judgeable_path` itself. See §6.

## 6. The door that stays closed

**Do not relax `is_judgeable_path` to buy speed.** `plugin/lib/coverage_algebra.py:72-88` records
that exact experiment — AST-keying Python so comment-only edits stay free — being **built and
reverted**, because `prawduct:allow` pragmas live in source comments, so a byte-identical AST can
suppress a compliance check. A wrongly granted free edge ships unreviewed code: the fatal failure
direction. This work needs none of it — rounds 3–5 were already free under the current strict
predicate.

## 7. Prose surfaces that teach the treadmill

These are behavioral logic, not documentation, and are governance-protected (hence judgeable):

- The Critic's `NEXT-ACTION` text — *"land every fix in ONE commit, then run ONE
  `/prawduct:critic verify-resolutions`."* For a fix commit touching no judgeable file that is
  simply wrong. It should say: **ask the gate; review only if it reports uncovered.**
- `check-cumulative-critic`'s remedy text, which prescribes running a review without first saying
  "check whether the interval is free."
- `/prawduct:pr` Step 2's sequencing paragraph, same shape.

## 8. Open assumptions

- `[ASSUMPTION: a new exit code (3) is the right skill-facing signal for "no review needed", rather
  than exit 0 with a parsed marker | MED impact | user can override]` — exit 0 currently means
  "dispatched, proceed", so reusing it would make the skill review anyway.
- `[ASSUMPTION: the override spelling is a --force flag on critic-begin, surfaced as
  /prawduct:critic --force | LOW impact | user can rename]`
- `[ASSUMPTION: refusal applies to every mode, not just verify-resolutions | MED impact]` — the
  measured waste is all verify-resolutions, but a `chunk`/`final` dispatch over an entirely
  non-judgeable working tree is waste by the same argument. Note `begin_review` already refuses an
  empty diff for every mode *except* verify-resolutions, so a mode-uniform rule matches the existing
  shape.

## 9. Discrepancy to resolve in Chunk 1 (do not build past it)

`learnings-detail.md` (CRT-7M2D, dated 2026-07-14) states that governance/instruction `.md`
including **`learnings.md` and `change-log.md`** is judgeable. The current code disagrees: both live
under `.prawduct/`, which `gitstate.METADATA_PREFIXES` classifies as never-judgeable, and an
empirical check on 2026-08-06 returned `False` for `.prawduct/change-log.md`.

This matters directly — if `change-log.md` were judgeable, rounds 3–5 would not have been free.
The empirical result governs what shipped, but the contradiction must be resolved before this work
leans on the predicate: either the learning is stale w.r.t. `METADATA_PREFIXES` and should be
corrected, or the code has drifted from an intended rule. **Read the mechanism; do not assume the
learning is stale just because it is inconvenient here.**

## 10. Requirements Confidence

**High.** Problem, success criteria, and scope are each statable in one sentence; the predicate is
derived from measurement rather than intuition and was validated retroactively against seven real
rounds. The one genuine unknown is §9, and Chunk 1 closes it before anything depends on it.
