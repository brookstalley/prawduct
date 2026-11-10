---
schema: 1
type: feature
scope: audit-guidance
date: 2026-11-10
title: The close is one line, delegation is the default, and requirements guidance covers four measured misses
---
Three changes to what every governed session is told, each ruled on by the owner on 2026-11-10
after an audit of the governed products (#1131, #1133, #1135).

**The close.** A turn that ends a chunk or leaves work outstanding closes with one line:
disposition, clear verdict, a short reason. The three-paragraph block and its `STATE` paragraph are
gone. A turn that needs the user restates every ask in full just above that line, numbered, with a
recommendation; "see above" is never an ask. `standing_block` reads the one-line form and still
reads the old one, so a session on an older digest is not misread. The `clear-reason` Stop check
records its firing as a `stop-observed:clear-reason` fact and no longer blocks; `stats` reports it
under *observed only*. It leaves the gate registry, as `clear-verdict` did.

**Delegation.** `delegation.md` opens with the default (split the work when that finishes sooner
and the pieces will not collide) and five things that hold however the coordinator arranges it:
tell the user; delegates run on Opus- or Sonnet-class models the coordinator names, with effort it
sets; delegates run no heavy tests; one integration branch, held by the coordinator or a dedicated
integrator; nothing outlives the cycle unrecorded. A dispatch always names its model, because an
unnamed one inherits the coordinator's. The closed list of reasons to ask for approval is gone,
and the `Delegation approval` preference is retired; `Delegation` and `Delegate verification`
remain. The refusal a build delegate gets from a governance command now names the coordinator.
That refusal already existed for harness scratch worktrees. A delegate sharing the coordinator's
worktree is still not detected.

**Requirements.** Four additions, each in the guide that owns it. Output judged by looking at it
is shown as a real specimen first (`discovery.md`). An owner's ruling is written, dated, to
`.prawduct/owner-rulings.md` before the reply (`building.md`, with a template). A rule the agent
originated is labelled as its own and offered with "don't have this" first (`discovery.md`). A
third fix on one surface stops for a definition (`building.md`).

The guidance was tried on three fresh agents before landing. Given a plan with two independent
chunks on a top-tier session, the agent disclosed the fan-out, named a Sonnet-class and an
Opus-class delegate with efforts, kept the declared suite off both, and pointed at the
`Delegation` preference. Given a request for a weekly report, it proposed a sample from real data
before the schedule. Given an owner statement mid-build, it wrote the owner's words to the rulings
record before replying, and dropped a limit it had been about to add as its own idea. That third
trial also logged a logo tweak as a ruling, so the section now says a ruling is what later work
must honour.

## Consumer note
Sessions close with one line instead of three paragraphs, and a turn that needs you ends with its
questions restated above that line. A close that cites the message itself as its record is no
longer sent back by the Stop hook; it is counted under "observed only" in `prawduct-hook stats`.
Agents delegate by default when it shortens the work, tell you how many agents and which models,
and keep the full test suite off delegates; `Delegation: off` in `project-preferences.md` turns
this off, and a `Delegation approval` row, if you have one, is no longer read. Agents now write
your rulings to `.prawduct/owner-rulings.md`; commit that file.
