---
schema: 1
type: docs
scope: goal-grounding-discovery
date: 2026-10-20
title: Discovery for grounding goals before investment, revising the 10-09 alignment design after testament
---
`.prawduct/artifacts/goal-grounding-discovery.md` revises `requirements-alignment-discovery.md`.
It explains why the shipped alignment pass, plan goals and goal-judged boundary review missed
testament's product-level requirements (trust and shared use), shows the same pattern in three
more governed products, and proposes four changes:
- a grounding check at investment decisions, which states what an ambiguity costs, highest first;
- hedged owner answers kept as open questions with revisit triggers;
- drift announced in tiers (record, heads-up, fork);
- the agent asking the goal questions itself.

The owner then settled the open questions: the building agent runs the check, signal 1 runs at
plan approval, and the checks stay ambient rather than named steps. A first read-only drift check
on testament, discodon, hallucinote and Arrt found fork-tier drift in all four and calibrated the
tiers: record lag is a heads-up, irreversible and publishing acts raise the tier (publishing is a
hard stop), and the audience axis is checked first.

Design only. No behaviour changes.

## Consumer note
none: design-only discovery artifact; no shipped behaviour changes
