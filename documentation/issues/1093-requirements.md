# Issue #1093 — session-continuity: turn-close shape keeps decisions in a longer body: Requirements

`status: draft · stage: requirements · area: session-continuity · kind: spike · added: 2026-11-06 · source: user (3.8.0-dev health survey, 2026-10-27) · issue: https://github.com/brookstalley/prawduct/issues/1093`

Related: `plugin/methodology/session-hygiene.md` (the standing turn-close block: `STATE` / disposition / clear verdict), `plugin/lib/standing_block.py` (the block's parser and verdict reader).

## Problem

In the 3.8.0-dev survey (window about two days, a signal to watch, not a measurement) turn length drifted up: p90 +9%, turns over 2500 characters 13% -> 18%. Buried questions stayed under 1% and flat, so nothing is broken yet.

Suspected cause: the block forbids padding and its `YOUR TURN` copy "leads with the ask", while the decisions themselves (numbered options, trade-offs) stay in the body above. The ask the user must act on then lives inside the longest part of the turn, and the closing line can only point "above".

This is a hypothesis. The spike's first job is to test it; only a supported hypothesis licenses a methodology change.

## Goals

- G1. Know whether long turns are disproportionately turns that carry decisions (the correlation the suspected cause predicts).
- G2. If so, know whether letting the closing block restate the decisions, bounded, shortens the body without reintroducing padding.
- G3. Leave the buried-question rate (<1%) no worse.

## Non-goals

- Changing the three-line block's labels or the Stop hook's verdict reading (`standing_block.py`), unless G2 is supported and a follow-up is filed.
- Capping total turn length. Long turns that carry no decision are not the target.
- Grading the content of a decision's reasoning.

## Requirements

**Measurement (answers G1)**

- R1. Classify each turn in a fixed window as `decision-bearing` (the closing disposition is `YOUR TURN`, or the body holds a numbered or lettered choice) or `not`, by a rule stated before looking at lengths.
- R2. Report, per class: n, median and p90 characters, share over 2500. The survey's 13% / 18% figures are reproduced with the same script first, so the baseline is the survey's, not a new one.
- R3. The window is at least 7 days and spans at least two sessions' worth of different work types; the survey's two days is the stated weakness. Absent enough turns, the result is "inconclusive", not a verdict.
- R4. Falsifier: if decision-bearing turns are not longer than others (or the share over 2500 moved in the other class), the hypothesis is rejected and the item closes with that finding.

**Experiment (answers G2; runs only if R4 does not reject)**

- R5. Variant: for a `YOUR TURN` close, the disposition copy may restate each pending decision in at most one line each, with a bound of three decisions, and the body may then drop its own restatement of them. Everything else in the block is unchanged.
- R6. Compare variant turns to control turns on: body length, closing-block length, buried-question rate, and a padding check (closing block lines that restate STATE or repeat the body without a decision).
- R7. Success: body length down with no rise in buried questions and no rise in padding. A shorter body bought by a longer closing block with the same total length is a null result.
- R8. Every measure reads a queryable fact (character counts, label positions, a question mark's position relative to the closing rule). None grades prose quality.

**Output**

- R9. The spike ends with one recorded outcome: reject (close), adopt (a ready issue editing `session-hygiene.md` and the parser's tolerance for the longer copy, with its own tests), or inconclusive (state the window needed).
- R10. Measurement code, if any, reuses the survey's turn-extraction path rather than adding a second reader of transcripts (a new reader needs a named consumer in the same change).

## Open questions

- Q1. Where did the survey read turns from? The script is not in the repo; R2 depends on finding or re-deriving it. Owner to point to it.
- Q2. Is a numbered choice in the body a reliable decision marker, or do prose asks ("should I...?") dominate? R1's rule should be checked on a hand-labelled sample of about 30 turns.
- Q3. Does the longer 3.8.0-dev turn also reflect more complex work (bigger builds) rather than shape? The window should control for work size, e.g. by comparing within the same chunk type.
- Q4. Is a bound of one line per decision, three decisions, right? Tune on the sample from Q2, not by feel.

## Done when

R1-R4 produce a recorded verdict on the hypothesis. If supported, R5-R9 produce an adopt / reject / inconclusive outcome on the issue.
