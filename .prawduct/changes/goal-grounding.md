---
schema: 1
type: feature
scope: goal-grounding
date: 2026-10-21
title: the alignment pass judges whether the goals under the work are grounded
---
- #1029, building the settled design in `.prawduct/artifacts/goal-grounding-discovery.md`.
- At any decision that commits investment (a plan, a design artifact, an architectural choice,
  spending, an outward commitment), the agent names the product goals the work rests on and
  whether each is grounded: stated by the owner without a hedge, and still true. An ungrounded
  goal with a lot resting on it gets a one-sentence stop; one with little resting on it gets a
  recorded default. What a hedge is about decides whether it counts: product hedges do,
  solution hedges (vendor, stack) get a default. Audience is checked first. The check lives in
  `methodology/discovery.md`; building.md, planning.md and the digest point to it.
- A hedged owner answer stays open in the brief as `Hedged:`, with a revisit trigger and the
  cheap hedges taken now. It is never recorded as `null` or a `never` item. The boundary review
  rates a goal still hedged like one still inferred (WARNING).

## Consumer note
Plans now say in their Goals response line whether any goal they rest on is ungrounded, and a
product goal you answer with a hedge ("maybe others later") is kept as an open question with a
revisit trigger instead of being settled for you. Expect an occasional one-sentence stop before a
plan when much rests on an audience or ownership question nobody has answered.
