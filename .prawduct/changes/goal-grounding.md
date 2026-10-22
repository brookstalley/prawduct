---
schema: 1
type: feature
scope: goal-grounding
date: 2026-10-21
title: the alignment pass judges whether the goals under the work are grounded
closes: [brookstalley/prawduct#1029]
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
- Drift is announced by tier (`methodology/discovery.md`): record (noted, silent), heads-up (one
  line; also when only the record lags a change the owner made out loud) and fork (drift nobody
  chose). Irreversibility raises the tier, publishing is a hard stop, and touching someone
  else's ownership is the strongest signal. Before presenting a plan, the agent reads it against
  the brief's revisit triggers and scope words.
- The session digest tells the agent to name drift from the brief when it sees it, pointing to
  the tiers. A replay of four governed products' real moments (chunk 04) drove it, and drove
  wording fixes: a recorded hedge with a lot resting on it is still raised; publishing is a hard
  stop at the act; ownership covers repo, code and data, and a fork comes before the act.
- Owner ruling, 2026-10-21: the owner can defer a high-stakes product question; the agent names
  its cost first. The hedge paragraph says so. One replay case (record lag aimed at the wrong
  line) stays short, filed as #1030.
- `tools/measure-alignment-yield.py` reports `goal_questions`: owner turns asking what the
  product or the work is trying to achieve, the control's yield (it should fall). A lead, read
  by hand. Baseline: `tools/measure-alignment-yield.py --until 2026-10-22`.

## Consumer note
Plans now say in their Goals response line whether any goal they rest on is ungrounded, and a
product goal you answer with a hedge ("maybe others later") is kept as an open question with a
revisit trigger instead of being settled for you. Expect an occasional one-sentence flag before a
plan when much rests on an audience or ownership question nobody has answered, naming what it
costs to leave open (you can still defer it), and a one-line
note when work moves the product away from what its brief says (more users, public exposure).
