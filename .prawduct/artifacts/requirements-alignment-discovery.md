---
artifact: discovery
scope: requirements-alignment
depends_on:
  - artifact: nonfunctional-requirements   # Direction: review wall-clock P0; new controls emit their yield
---

# Discovery: Aligning Agent and Owner on Goals

## Goals

**Product.** An owner hands work to an agent, including long autonomous runs while they are away,
and comes back to what they meant. Every clarification the work needs is asked together, up front,
before a plan is written. The owner welcomes questions; what they cannot afford is a six-hour build
that stops every fifteen minutes. Questions will still arise during implementation, and prawduct's
job then is to make sure the agent has enough context to answer them well itself.

Owners using prawduct want great, scalable, long-lived products, so an agent deciding on its own
favours the **most durable** choice, not the most reversible one:

1. **Do it right.**
2. **Do it in line with the product's other choices** at the product, architecture, and technology
   levels, including the backlog. Backlog items are the richest record of where the product is
   going.
3. **Stop and ask only when the stakes really are high**: the choice is irreversible, spends real
   money, takes on large tech debt, or costs work out of proportion to its benefit.

**Before building is the one place for an explicit clarify, ask, or acknowledge.** Ceremony is
still to be avoided there.

**Architecture.** Three properties have to hold for that:

1. *Goals outlive the session.* Every session starts cold. Today an agent mid-build reconstructs
   intent from plans and briefs that an earlier agent wrote, which is how an inference becomes an
   "owner ruling" a week later. What the owner wants, and why, has to be written down where the
   building agent reads it.
2. *The owner's words stay distinguishable from the agent's inferences*, wherever goals are
   recorded. This is natural language ("you said…", "I'm assuming…"), not a schema.
3. *Goals reach every decision point*: when the plan is written, when the agent decides something
   mid-build, and when the work is reviewed. Today the Critic reviews against the plan, so a plan
   that faithfully implements a misread goal passes.

**Implementation.** Deliberately open until the design below is confirmed. The five backlog items
filed from the audit (#970–#974) are fixes for symptoms; they get re-cut against this design rather
than built as filed.

## Audience

Owners in general, but expert ones, at roughly this owner's depth in product management,
requirements, and engineering. They write terse, high-context requests and want autonomy, not
tutoring. The agent's job is to surface its own reading and the forks in it, not to teach.
**Near-term and North Star coincide here**; a novice-owner mode is not a goal.

## Constraints

- **The session digest is full** (about 9,500 characters of a 10,000 wall). Anything every
  repo must see is paid for by rewriting what is there, not by adding.
- **Review wall-clock is a P0 norm**, and **every new control must emit observable yield**
  (`nonfunctional-requirements.md` § Direction). A new review round per plan is a cost to justify,
  not a default.
- **Mechanical work must not get slower.** A bug with a repro, "continue", or a PR operation gets
  no new step.
- **The owner is often away while work runs.** Nothing may depend on them answering mid-build.
- **Natural language over schema.** Agents reason well over a sentence like "home use for now,
  thousands of anonymous users eventually" and badly over fields filled because a slot existed.
  Structure goes only where a mechanism must read it.

## Why: the evidence

Measured 2026-10-08 over Claude Code transcripts since 2025-09 (960 owner requests across 17
projects; data and extraction scripts outside git at `.prawduct/.req-audit-2026-10-08/`).

The rework the audit found sorts by the level where alignment broke, and it is almost never the
level prawduct reviews:

| Level | Example |
|---|---|
| Product | postarr: who uses it and where was never asked, so a public feed for up to 1,000 Apple TVs came up only when the owner raised it |
| Architecture | prawduct's core.md: the goal (an index) was lost when the work became "a 16KB byte cap" |
| Constraints | puzzles: an example in a reference image became the rule "round ends". samsung: the agent invented a spending cap and wrote it into the brief |
| Implementation | rarely. This is what the Critic is built to catch |

Other measurements: agents asked before building on 24 of 138 substantive governed requests. Of
286 questions asked, 158 were about process or design choices, and about a quarter of the
requirements questions came up mid-build. In 22 sampled underspecified requests, 9 led to rework,
each traced to an inference the owner never saw.

Framework causes (source checked 2026-10-09):
- Discovery's feature-level "three questions" are product-level only, answered after the agent has
  decided what it is building.
- The asking bar leans against the owner ("Infer aggressively"; ask only when "consequential and
  genuinely unverifiable"; Principle 20's cost-of-asking sentence).
- The "Before Building" check exists only in this repo's CLAUDE.md, never in a product repo.
- `[ASSUMPTION … | user can override]` has no answered state.
- `scope.accommodate`, the North Star tier, is written at discovery and read by nothing.

## Proposed Design (for owner confirmation)

**An alignment pass before building.** Before substantial work, the agent judges two things: how
clear the goals already are, from the request, the brief, and the backlog, and how much work and
risk lie ahead. It then takes one of four responses and **always says which one, in a line**,
because the acknowledgement is how the owner catches a misreading before it is built:

| Situation | Response |
|---|---|
| Clear by nature, however large: a mechanical bug fix where the bug and its repro define success | **Proceed.** Restate the target in a sentence and go. |
| A backlog item or spec already answers the goal and requirement questions | **Proceed, citing it.** Restate the goals from the item, name anything it leaves open and the inference made there, and go. |
| Mostly clear, but a high-level goal or a key architecture choice is missing | **Ask, in one batch.** Lead with the agent's own reading, so the owner corrects rather than authors. |
| A lot of work, and the goals or requirements are not understood | **Hold up.** "This is a lot of work and I don't understand the goals yet. Shall we discuss, or do you want me to use best judgment?" |

- **The written form scales with the response.** A sentence for Proceed. For Ask or Hold up, a
  short statement of the goals at the product and architecture levels, the constraints, and the
  tradeoffs the agent would accept, saying plainly what the owner said and what the agent is
  inferring. A page of goals is quicker to correct than a plan, and a plan quicker than code.
- **Best judgment is a legitimate answer to Hold up.** When the owner chooses it, the agent
  proceeds with its inferences written down, and the boundary review puts them in front of the
  owner.
- **The goals persist as the plan's opening**, so a cold session mid-build reads them before the
  chunks. The product's near-term and North Star live once in the brief, in prose, and every
  pass cites them.
- **Mid-build, the agent decides rather than asks.** It applies the durable-choice order in Goals
  above and records the decision in one line, naming the goal or prior choice that settled it.
  It stops only for the high-stakes cases listed there. A decision the goals didn't settle
  counts as a miss by the alignment pass, and gets flagged for the boundary.
- **The boundary review judges against the goals**, not only the plan. It lists the agent's
  mid-build decisions for the owner, and it treats a goal that was inferred and never put to the
  owner as a finding.
- **Yield is the owner's own two measures**, taken from transcripts: questions that interrupted a
  build, and owner corrections after one. The audit script measures both today, which satisfies
  the norm requiring every new control to emit observable yield, without adding a new ledger kind.

**What becomes of the filed items:**
- **#972** (plan template) becomes the plan's goals opening.
- **#970** (provenance) is absorbed into the pass's said-versus-inferred language. It no longer
  needs a tag schema.
- **#971** (intake in every repo) becomes a rewrite of the digest's rigor paragraph that points at
  the pass.
- **#973** (North Star) becomes near-term and North Star in prose, in the brief, cited by every
  pass.
- **#974** (brief coherence) stays, because the brief is the product-level goals statement and
  must not contradict itself.
- **New: the Critic reviews against goals.**

## Settled 2026-10-09

The owner approved this design with the two corrections above: choose the most durable option,
not the most reversible, and use the four responses for latitude before building. Two of the
agent's proposals were not contested:

- The pass is triggered by any substantial request, not only by work that has a plan. The four
  responses keep it cheap where the work is clear.
- A mid-build decision that went against the owner's intent is a miss by the alignment pass, and
  it feeds reflection. It is the main signal for improving the pass.
