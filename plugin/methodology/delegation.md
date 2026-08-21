# Delegating Work: When To, What a Delegate Verifies, and What It Costs

**Prawduct states the goal, one default, and the considerations. You choose the mechanism.** You can see this machine, this project's test regime and this moment's load; a framework distributed to every governed repo cannot. Nothing here names a command, a marker, a tier or a runner — where a decision needs one, naming it is yours.

The dispatch mechanics — worktree isolation, the shared git index, what an isolated agent can and cannot see — are `/prawduct:methodology building` § Delegating Work to Subagents. This guide is the judgment that comes first.

## When to delegate

**Default: delegate when the same work finishes in less wall clock and the delegates will not fight each other.** A plan whose chunks are independent is the ordinary yes. Delegate regardless of the wall clock when **the user asks** (Principle 23), when a well-scoped chunk wants a clean context, or when the main context has grown large enough that the work would be done badly in it.

**Parallel is not automatically faster, and the wall clock to compare is the bounded one.** Three delegates each running the run *you* would do at integration is more machine load and more wall clock than doing it once yourself. This decision is usually made while a build plan is being drawn, before any brief exists — but the bound is a property of the *chunk*, not of the brief, and a chunk's deliverables are already declared. So ask what would prove each chunk on its own. **A chunk you cannot answer that for is not scoped tightly enough to hand to anyone**, which is worth more than the estimate you were trying to make. Plan-time partition is a default, not a commitment: re-check it at dispatch against what the machine is actually doing.

Stay serial when any of these holds:

- **The chunks aren't independent** — one needs another's output, or two touch the same files. Conflict cost is paid at merge, by you, after both delegates have finished being confident.
- **Briefing costs more than the work.** A brief that runs to tens of thousands of tokens is not worth assembling for a small chunk, and while that is what one costs, it is the honest reason a lot of parallelizable work is done inline.
- **The project says otherwise.** `project-preferences.md` is where a project records its own delegation policy — including `off`, and including delegation already pre-approved. Read it before fanning out; where it and this guide differ, it wins.

Serial is a decision like any other. Record it either way, in the plan's `partition:` field — "serial, because these three chunks all edit the same module" is an answer; silence is not.

## What a delegate is for

**A delegate verifies what proves its own change, and nothing beyond it.** The coordinator owns integration verification and all governance: the combined run, end-to-end checks, the Critic, reflection, state updates, merges.

## Considerations

Questions, not rules. The answers differ by project, by machine, and by the moment you ask.

- **What must this delegate prove, and what is the smallest thing that proves it?**
- **Who checks the seams between delegates, and when?** Integration is nobody's job unless you make it yours.
- **What is this machine already doing?** Verification, not editing, is the wall clock. N delegates each running the coordinator's run is N times the load on one box, and the clamps that protect a box from *one* run are per-process — they do not compose across runs.
- **What in this project's regime is expensive** — in time, in money, in credentials, or in dependence on something nobody here controls — **and does this delegate need any of it?**

On that last question: a failure in a test that depends on an uncontrolled third party is not a signal about the delegate's change at all. One governed repo paid to learn it — a 403 from a video host failed a gate for a diff touching only that repo's visualization code, and the identical tree passed seven minutes later. Prawduct names the consideration; you decide what it means for your suite.

## Anti-patterns

Each carries a **tell** — the thing you can catch yourself doing. A rule with no tell reads as true afterwards instead of firing at the moment of the error.

- **The delegate that verifies the whole product.** *Tell:* the brief names a command the *coordinator* would run at integration.
- **N baselines.** *Tell:* the brief says "make sure tests pass before you start." A delegate inherits your baseline; re-establishing one N times buys nothing and costs N runs.
- **The unattributable green.** *Tell:* you accepted a pass count without knowing what was collected, from a box running several agents. A test worker that dies under contention is typically not re-queued and does not fail the run — measured in one governed repo, three whole-suite runs of the same tree each reported a *different* total, none of them more than about half of what the suite collects, and all three exited 0. A green you cannot attribute to a known set of tests is not evidence.
- **Boundaryless fan-out.** *Tell:* you cannot say which files each delegate owns without reopening their briefs.
- **The delegate that governs.** *Tell:* a delegate ran the Critic, updated project state, or ticked a Status box.
- **The brief that costs more than the work.** *Tell:* the context you assembled exceeds what the chunk changes.
- **Serial by default.** *Tell:* a plan with independent chunks and no partition decision recorded either way. Serial is very often right; *unexamined* is what this names.

## What a brief must say

A list of what has to be said, in your own words — not a template, and not something to generate. A brief that could be copy-pasted from the last one has stopped carrying information.

- **The work** — the chunk spec and the artifacts it references, or the task stated in full.
- **The ownership boundary** — what this delegate owns, and what it must not touch.
- **A verification ceiling** — the narrowest run that covers its own change, never the run you will do at integration. A cost bound, not a rigor discount.
- **What to return**, and in what form.
- **Who integrates** — you. Say so, so the delegate doesn't try.

If you cannot state the ownership boundary without re-reading the other delegates' briefs, the partition isn't ready and the fan-out will cost more than it saves.
