---
schema: 1
type: refactor
scope: retire-three-principles
date: 2026-11-18
title: The principles are grouped by how they fire, and three of them now live inside their neighbours
closes: [brookstalley/prawduct#686]
---
`docs/principles.md` used to present its principles as one flat list under six headings. They are
now grouped into three kinds by how they fire:

- **craft** bars that apply to every task;
- **governance and stance**, which covers how the process and the agent operate;
- **coverage** rules for the requirement classes discovery must not miss.

The session digest's roster follows the same grouping.

Three principles were retired into the principles that absorbed them. Owner decision, 2026-08-19.
The case for each was re-measured before the change: in the last tagged learnings corpus, #19 and
#20 had no citations, and #12 had four.

- **Scope Discipline (#12)** became the "all of it, none more" half of Complete Delivery (#2).
- **Evolving Principles (#19)** became the amendment clause in the document's preamble.
- **Infer, Confirm, Proceed (#20)** joined Bring Expertise (#7), which made the same point from the
  other end.

Principle numbers are permanent addresses, so nothing was renumbered. Each retired number keeps
its slot under § Retired Numbers, with a pointer to the principle that absorbed it, and a test
fails if any number is reused.

Governance Is Structural (#22) also gains a "Gates are backstops" paragraph. The goal is to pass
every gate the first time, because a block costs an extra turn plus replayed context.

## Consumer note
Citations of `(#12)`, `(#19)` or `(#20)` in your learnings or specs still resolve: the slots point
at the principles that absorbed them. The always-injected digest is about 11 tokens smaller.
