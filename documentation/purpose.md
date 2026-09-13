# Purpose

<!-- The framework's own north star — why prawduct exists and what shape its evolution
     must take. Ratified by owner decision 2026-08-12. This file is the ONE home for
     prawduct's purpose (architecture.md "every fact has one home"); CLAUDE.md's opening
     line and the artifact-frontmatter product-brief comments are references to it.
     Rules live elsewhere: plugin/docs/principles.md holds the binding principles,
     .prawduct/artifacts/architecture.md holds the ratified norms. This file explains
     why those exist and how they must change. -->

**Prawduct builds on today's models and runtimes to close the gap between what they
provide and what consumers need to deliver successful software products.**

## The bet

Models are commodities. Every team, every competitor, every hobbyist has the same ones
on the same day. Nobody differentiates by using a model; they differentiate by what
they deliver *above* the mass-market baseline. Prawduct's business is supplying that
above-baseline layer: the completeness, memory, and judgment disciplines that turn
generally-available capability into successful products.

The baseline rises constantly, and prawduct's features are, deliberately, early
deliveries of things models and harnesses will subsume some months or years later.
When subsumption arrives, prawduct cedes that ground and moves its value higher. This
makes prawduct a permanent business, not a dying one: the frontier between "what the
runtime provides" and "what a successful product needs" moves, but it does not close.
**A mechanism deleted because the runtime absorbed its job is the system working, not
the system failing.**

## Why the gap never closes

Software is an open-ended problem, and the requirements that decide success routinely
arrive late: "oh, it has to work offline," "RTL languages are our main use case," "it
has to run on a twenty-year-old PC" — months into a project. It is not possible to
elicit every important requirement before starting, and it is always more expensive to
learn one later. This is human nature, not tooling immaturity, so no runtime
improvement retires it. And mass-market capabilities generalize by construction, while
every successful product wins on specifics. Models and harnesses will always trail
real-world use cases; prawduct lives in that trailing gap.

## What prawduct hedges

Every prawduct mechanism insures against one of three failure sources, and they
depreciate on different schedules:

1. **Runtime judgment** — given full context, the model does the wrong thing.
   Shrinks with every model release. Mechanisms here are priced against the runtime
   that existed when they were written, and they are the first candidates for cession.
2. **Joint myopia** — the context was never in the room. The human didn't say it, so
   no judgment could act on it; human-plus-model is a task-focused pair that will
   happily build the wrong thing excellently. This is the checklist insight: completeness
   under task-focus is hard for *any* competent agent. It depreciates slowly — better
   runtimes elicit better — but never fully, for the reasons above.
3. **Statelessness** — sessions forget, and so do people. Decisions, learnings, and
   requirements must outlive the conversation that produced them. Depreciates on the
   harness's schedule, not the model's.

What does not depreciate is thinner than any mechanism: the **mandate** (making the
pause legitimate — licensing a task-focused pair to stop and do discovery at all), the
**record** (answers captured so they bind work done later by someone else), and the
**audit** (verifying the delivered thing is complete against the record). Intelligence
is not on that list; the runtime supplies intelligence at an ever-rising level.
Prawduct's durable role is standing, memory, and checkback.

## How responsibility shifts

Responsibility for each condition of successful delivery is *shared* — human, runtime,
and framework each hold a fraction, and the fractions drift as runtimes improve. It is
never "the human owns requirements and the model owns architecture"; it is a balance
that moves gradually, which is why prawduct must evolve **continuously, not in step
functions**. The operating rules for that evolution:

- **Every mechanism carries the assumption that justifies it.** When a model or harness
  change breaks the assumption, the mechanism is re-priced: ceded downward, or moved up
  an abstraction level. As the mechanical is subsumed, the abstract reaches higher —
  prawduct does not shrink when the runtime improves; it rises. (Principle 26.)
- **The third rework of a mechanism is a deletion signal, not a patch signal.**
  (Principle 25.)
- **Deletion gets the same care as addition** — reviewed, evidenced, recorded. A
  mechanism exits whole: its code, tests, docs, and records together.
- The planned instrument for all of this is a **responsibility ledger** (Cycle 3 of
  the cession program, `.prawduct/artifacts/program-purpose-and-cession.md`): each
  condition of successful software development, who holds it today, under what
  assumption, and what external signal would reassign it. Re-pricing is event-driven —
  a runtime change, not a calendar — and each re-pricing is conducted by a runtime
  smarter than the one that wrote the rows.
- **Until the ledger carries them, cessions ride the change-log.** A re-pricing is
  recorded as a `.prawduct/change-log.md` entry naming what was ceded, the assumption
  that expired, and what survives on which remaining rationale — a log of *changes*
  standing in for a register of *holdings*. Writing one is the regime, not a workaround
  for a missing surface. Cycle 3 landing moves the register to the ledger and leaves the
  narrative where it already is; a ceder reading this before then writes the change-log
  entry and nothing else. Worked example, and the shape to copy: the 2026-08-19 entry
  *“the work-cycle limit is re-priced, and a rationale is formally ceded”*.

## What prawduct never does

Prawduct guides and reviews; it never implements, and it never re-implements what a
product's own tooling already does (the binding form of this rule lives in
`.prawduct/artifacts/architecture.md` § Direction). And whatever prawduct learns from
the products it governs is **directional by construction**: measurement schemas must be
physically incapable of carrying proprietary information — counts against fixed
vocabularies, never free text, paths, or code — so that telemetry can scale to
consumers without ever collecting what isn't prawduct's to hold.
