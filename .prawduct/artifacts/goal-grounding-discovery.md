---
artifact: discovery
scope: goal-grounding
depends_on:
  - artifact: requirements-alignment-discovery   # the 10-09 design this revises; its Goals, Audience and Constraints still hold
  - artifact: nonfunctional-requirements         # Direction: review wall-clock P0; new controls emit their yield
---

# Discovery: Grounding Goals Before Investment

This revises `requirements-alignment-discovery.md` (settled 2026-10-09). That design shipped
in full (#970–#974). A week later testament was built under it and failed at the product level.
Everything below is a delta: what the earlier design left out, and why it missed.

## Goals

The owner's own words, 2026-10-20:

- **The aim is to state what ambiguity costs, highest cost first, not to remove all of it.**
- **Every decision that commits investment (time, resources, money, or architecture that later
  work builds on) is checked for well-grounded goals. If they are not grounded, work stops and
  says so.** "Users will appreciate that."
- **Pushback is short and strong**: "this is a huge fork in the road, worth taking the time to
  define clearly now", not an explanatory paragraph.
- **Requirements drift is normal, and prawduct should call it out.** It is a gradient, so
  calibration is the hard part, and also why it is valuable.
- **What an ambiguity is about decides whether it matters.** A hedge about goals, customers or
  their needs matters. "AWS or Azure? Not sure yet" does not.

The owner's earlier frame, from the same session: "Why am I always the one to ask 'what are we
really trying to achieve' and 'how does this implementation meet our product goals'? The agent
using prawduct should be prodding me when I have blind spots."

## Why the 10-09 design missed testament

Testament (`~/source/testrouter`) was onboarded on 2026-10-16. Every plan it wrote opens with
`## Goals` and a response from the alignment pass, and every plan was reviewed against those goals.
Each mechanism worked as built:

1. **The pass judges whether the *request* is clear, not whether the goals behind it are
   grounded.** "Add pacepace as a contributor with write access" is a perfectly clear request.
   Doing it contradicted the brief's "built for one owner", and nothing checked the request
   against the premise.
2. **"Proceed, citing it" trusts whatever it cites.** All three security plans proceed by citing
   a requirements doc. Citation chains end at a recorded premise that no one goes back to
   ground.
3. **Provenance records two states, said and inferred, but not a third: said, but hedged.** In
   discovery the owner answered: "I expect this might be used by others… not sure… scope that out
   for now… at most trusted external users (I would give them root)." That was recorded as an
   owner statement and became `has_multiple_party_types: null`, "one trust level", plus a `never`
   item. The Critic's rule that an inferred goal is a WARNING never fired, because the goal was
   recorded as said.
4. **Nothing compares what is now true with what the brief says.** Drift arrives as remarks
   and acts spread over sessions:
   - "it will eventually be public" (10-17), treated as a packaging question;
   - the agent minting a join token for a second person (10-17);
   - an outside user filing issues against their own repo (10-19).

   The alignment pass reads one request at a time. The discovery.md rule "a multi-user flip
   re-opens auth, data isolation, and audit" depends on the agent recalling it mid-chunk, and it
   never fired.
5. **Ambiguity is handled flat.** Nothing ranks an open question by what rests on it, so the one
   that would shape auth, the network, secrets and containment got the same treatment as a
   packaging choice.

**Cost to testament:** the owner raised every product-level requirement:
- API keys (mid-chunk, 10-17);
- "no worse off" fallback;
- stored results;
- public addresses;
- the full trust and shared-use audit (10-20).

The 10-20 rework took about 31 commits, three versions of the requirements in one day, and 24
audit findings, reversed two norms, and still has a wave pending. The owner ended up writing the
actor matrix themselves: "This has been tricky to specify."

**The pattern generalizes.** Transcripts and records were sampled 2026-10-20; extracts are kept
outside git. Discodon, hallucinote and samsung/Arrt each moved toward more parties or public exposure:

| Product | What changed | What the record still says |
|---|---|---|
| discodon | public listeners, a co-developer, a public tunnel the agent opened | Discord personas |
| hallucinote | made public, marketplace release | "single-user, local-only, private project" |
| samsung/Arrt | a public service for up to 1,000 Apple TVs; the October pivot matched the text of two armed reopen triggers | "LAN-only, one household", triggers never marked fired |

In all three, the product-goal questions came from the owner. The agent's reframes stayed at the
solution layer.

**The one success shows the conditions it needs.** Arrt, 2026-07-19: adding MCP flipped
`exposes_programmatic_interface`. The agent ran the re-derivation and the assumption audit
exactly as discovery.md asks. It worked because:
- the trigger was concrete ("any consumer not deployed from this repo");
- a field visibly changed;
- the agent was inside that very decision.

Without the third condition, the same mechanism failed in October. Drift detection cannot depend
on recall mid-build.

## Proposed design (for owner confirmation)

### A. Grounding check at investment decisions

**When it runs:** at a decision that commits investment:
- a plan;
- a design artifact;
- an architectural choice that later work will build on;
- spending;
- an outward commitment (an invite, a publish, a public endpoint).

Mechanical work stays exempt, as in the earlier design.

**What it asks:** which product goals does this rest on (who it is for, what job it does, what
success means, who else touches it and whose machines it runs on), and is each one *grounded*?
A goal is grounded when it is stated by the owner without a hedge **and** is still true given
what has happened since.

**Response:**
- **Grounded:** proceed, under the existing alignment pass.
- **Ungrounded, with a lot resting on it:** stop and flag, in a sentence or two. "This is a huge
  fork in the road, worth defining clearly now: auth, network exposure and where secrets live all
  turn on it." The owner can answer, or choose best judgment, which the earlier design already
  treats as legitimate.
- **Ungrounded, with little resting on it:** record the default taken and what would reopen it,
  and keep going.

**What an ambiguity costs** is how much investment rests on it, times how hard that is to reverse
once built. Only the top items reach the owner, in one batch, highest cost first.

**What it is about is the filter, not wording.** Hedges about the product (customers, needs,
goals, parties, whose machine) qualify. Hedges about the solution (vendor, stack, library) get a
recorded default, unless one stands in for a goal ("a customer requires Azure"). This is
judgment, never word-matching: a lexical trigger fires on AWS-versus-Azure and teaches the owner
to ignore it.

### B. A hedged answer stays open

When the owner hedges about the product, the record keeps the hedge:
- as an open question;
- with a concrete revisit trigger, worded the way the Arrt trigger that fired was;
- with the cheap hedges taken now. For testament, that was an owner field on every key from day
  one.

It never becomes `null` or a `never` item. A third provenance state, *said, hedged*, sits beside
said and inferred. The boundary review treats a plan resting on a hedged goal the way it treats
one resting on an inferred goal.

### C. Drift is announced, by tier

| Tier | When | What the owner sees |
|---|---|---|
| Record | one weak signal, little resting on it | nothing in the turn; noted so later signals add up |
| Heads-up | signals building on one product axis, or one moderate signal | one line: "This moves us toward multi-user. The brief still says one owner." |
| Fork | an act contradicts the brief, signals add up past the bar, or a lot rests on the axis | "This is really changing: one owner → three people's repos. Worth redefining the goals before the next plan." |

Signals, strongest first:

1. **Acts that contradict the record's own text.** Making a repo public, a tunnel or public URL,
   an invite or token for another person, a new commit author, a marketplace listing, each set
   against "single-user", "LAN-only", "private" or a `never` item. Every product sampled would
   have tripped this. It is concrete enough to check mechanically.
2. **Armed revisit triggers matched against new plan and design text**, at plan approval. Arrt's
   triggers literally described the October event.
3. **Hedges about the product in conversation**, judged under A's filter.

Drift is not a defect. The fork tier's output is a question ("do we update the goals?"), and
answering it updates the brief and classification so that the flip is on the record.

### D. The agent asks the goal questions

At discovery, and at every fork, the agent opens by restating what the product is trying to
achieve and how this work serves it, before the owner has to ask. The 10-09 design already tells
the agent to lead with its own reading. What changes is that the reading is about the product,
not just the request.

## Constraints carried forward

These come from `requirements-alignment-discovery.md`. All of them still hold:
- The session digest is full.
- Review wall-clock is P0, and every new control emits its yield.
- Mechanical work gets no slower.
- The owner is often away.
- Natural language is preferred over schema.

Two follow from them here:
- A stop costs the owner an interruption, so the fork tier has to be rare to keep its force (the
  owner's measure: rounds and stops caused or saved).
- Signal 3 and A's filter stay as judgment. Only signals 1 and 2 are candidates for a mechanism.

## Relation to #986

#986 ("make a late requirement cheap to absorb") rules out expanding discovery up front, because
about four in five late requirements could not have been known in advance. Testament's could have
been: they were said in conversation, or done by the agent, and went unexamined. This design adds
no discovery rounds. It makes the agent name a requirement as it surfaces, and #986 makes it
cheap to absorb once named. The two compose.

## Acceptance (draft)

- **Testament replay.** A fresh agent with the change replays testament's discovery (noun-account transcript
  `63e84817`, local) and its 10-17 sessions. It must:
  - flag "might be used by others… scope that out for now" as a fork at discovery;
  - raise the fork tier when it mints the second person's join token;
  - not flag a solution hedge planted as a negative control ("AWS or Azure, not sure yet").
- **Arrt replay.** The October public-service plan fires the two armed triggers.
- **Yield.** The 2026-10-08 audit scripts the parent doc names (kept outside git) count
  owner-raised product-level questions and owner corrections per product, measured before and
  after the change.

## Open questions for the owner

1. **Who runs the grounding check at a plan: the building agent, or an independent reviewer?**
   - For an independent reviewer: every case above is the building agent caught up in momentum,
     and the Critic's value comes from its independence.
   - Against: the earlier design treats a new review round per plan as a cost to justify.
   - A middle path: fold it into the existing pass at plan approval and the boundary review, and
     go independent only if the replay shows self-checks miss.
2. **Signal 1's vehicle:** a per-turn check (immediate, but always running), or a scan at plan
   approval (cheaper, but it lags). The testament invite happened mid-session, between plans.
3. **Backfill:** run the drift check on the products already governed (testament, discodon,
   hallucinote, Arrt), whose records are all stale on parties or exposure.
