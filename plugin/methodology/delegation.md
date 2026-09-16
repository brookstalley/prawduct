# Delegating Work: When To, What a Delegate Verifies, and What It Costs

**Prawduct states the goal, one default, and the considerations. You choose the mechanism.** You can see this machine, this project's test regime and this moment's load; a framework distributed to every governed repo cannot. Nothing here names *your* runner, *your* markers, or a tier of prawduct's invention — where a decision needs one, naming it is yours. (Prawduct's own commands are in bounds: the record it owns is inside the line.)

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
- **The unattributable green.** *Tell:* you accepted a pass count without knowing what was collected, from a box running several agents. A test worker that dies under contention is typically not re-queued and does not fail the run — measured in one governed repo, three whole-suite runs of the same tree each reported a *different* total, none of them more than about half of what the suite collects, and all three exited 0. A green you cannot attribute to a known set of tests is not evidence — so record it as one: `test-evidence record --degraded "<what did not report>"`, which the gates read as stale rather than as a pass. Prawduct cannot detect this; the record carries what you saw.
- **The Done taken on faith.** *Tell:* you accepted a delegate's completion report on a removal or a sweep without re-deriving it — the grep for the symbol it removed, the recount of the inventory it swept. These fail in the direction of looking finished, so the report reads identically either way.
- **Boundaryless fan-out.** *Tell:* you cannot say which files each delegate owns without reopening their briefs.
- **The delegate that governs.** *Tell:* a delegate ran the Critic, updated project state, or ticked a Status box.
- **The brief that costs more than the work.** *Tell:* the context you assembled exceeds what the chunk changes.
- **Serial by default.** *Tell:* a plan with independent chunks and no partition decision recorded either way. Serial is very often right; *unexamined* is what this names.

## What a brief must say

A list of what has to be said, in your own words — not a template, and not something to generate. A brief that could be copy-pasted from the last one has stopped carrying information.

- **The work** — the chunk spec and the artifacts it references, or the task stated in full.
- **The ownership boundary** — what this delegate owns, and what it must not touch.
- **A verification ceiling** — the narrowest run that covers its own change, never the run you will do at integration. A cost bound, not a rigor discount. **Read `project-preferences.md`'s `Delegate verification` row first, where the project has one** — a ceiling you invent beside a ceiling the owner already ratified is the retyping this whole feature exists to end.
- **What to return**, and in what form.
- **Who integrates** — you. Say so, so the delegate doesn't try.

If you cannot state the ownership boundary without re-reading the other delegates' briefs, the partition isn't ready and the fan-out will cost more than it saves.

## Work no plan anticipated

The partition above is drawn at plan time. The other trigger is an interrupt — a tangent the user raises mid-chunk, or work you are about to propose backlogging.

**A delegated tangent is never *done*.** You own integration, so what comes back is a branch plus an integration debt: a combined run, live verification, the Critic, a merge. Isolation stops delegates fighting *during* the run and does nothing about the merge, so that branch also ages against the line you are actively moving. And the reason you delegated — this context is full, or nearly — guarantees the agent that incurred the debt is not the one who will pay it. So coordination has to be **a role recorded on disk, not an agent held in memory**: a debt that lives only in your context evaporates at the next `/clear`, leaving an unmerged branch and a worktree nobody remembers creating.

**The decision is three-way, made once, out loud: do it now, delegate it, or backlog it.** Delegation is offered first — and that default is a *policy* setting rather than a technical one. `project-preferences.md`'s `Delegation` row overrides it in the project's own words, and `off` means the proposal is never made. The question that sorts the three: *would you integrate this today if it came back green?* If not, the honest artifact is a backlog item.

**Disclose before dispatching** (Principle 9, Visible Costs): what the delegate will do, what it will *not* do, that its result carries an integration debt and who is expected to pay it, and **how many ad-hoc branches already await integration**. A fifth outstanding branch is a different proposal from a first one, and the user should hear which one this is — unmerged branches are inventory, and this trigger is the one best at accumulating it.

**Requirements first — four paths, and no fifth.** An ad-hoc delegate never builds against unclear requirements: you state them in the brief, or you reference an artifact that already states them, or the delegate drafts them as its first deliverable, or it stops and demands them. Path three has an edge worth naming — a delegate drafting requirements is doing discovery, and requirements drafted in a worktree and never ratified are `/prawduct:methodology building`'s *silently invent a requirement* failure in a new costume, with the branch's existence standing in for approval. Drafted requirements come back marked **proposed**, and ratifying them is part of the debt.

**What it hands back is a branch and a report** naming what it verified, what it assumed, and what it left for integration. Everything above binds unchanged, the verification ceiling and the no-governance rule included.

**Write the brief into the delegate's worktree**, at `.prawduct/.delegate-brief.md`, rather than only into the prompt. The artifact that had to exist anyway becomes the dispatch record — what was delegated, what it owns, who integrates — and an abandoned worktree stops being invisible. No registry, no schema, no lease; nothing new to keep in sync.

**So you create the worktree, write the brief into it, and then dispatch, pointing the agent at that directory.** `git worktree add` it yourself: the harness's own `isolation: "worktree"` shape hands the agent a tree you cannot name until it is already running, so there is no moment at which the dispatcher could write the record — and a brief written *by* the delegate is missing in precisely the case it exists for, one that dies early. This is the coordinator's write, not the delegate's; the no-governance rule binding the delegate is untouched, and everything else about dispatch is `/prawduct:methodology building` § Delegating Work to Subagents.

**Do not dispatch what this session cannot reap.** Expected runtime against the useful context you have left is a real comparison, and "no" means backlog. The unreapable delegate is the worst outcome on offer: compute spent, no result read, a worktree orphaned. Reap at a work-cycle boundary, never as a mid-flow interrupt — the mechanism that exists to protect focus must not become the thing that breaks it. What an unreaped delegate does to the clear verdict is `/prawduct:methodology session-hygiene`.

**Reaping ends with the worktree, not with the merge.** Take the branch and the report, then remove the worktree — or at least its brief. The brief is what a session start reads to notice an orphan, so one left behind in a checkout reused for ordinary work raises an advisory about work nobody delegated, and it does so under a fresh id each time the branch changes, which no dismissal settles.

### Anti-patterns, ad-hoc

- **The delegate you cannot reap.** *Tell:* you estimated its runtime as longer than the context you had left, and dispatched anyway.
- **The brief that scoped the tangent.** *Tell:* scoping cost more context than doing the work would have, or more than the one-line backlog entry it replaced.
- **The un-ratified requirement.** *Tell:* a branch carries a requirements doc nobody approved and code that already implements it.
- **The debt that lives in your head.** *Tell:* you can name which branch needs integrating and no file can.
- **The tangent that was a decision.** *Tell:* the delegate was dispatched to decide something rather than to build something already decided.
- **Delegation as a way to say yes.** *Tell:* you dispatched because declining felt unhelpful, not because the work was ready to hand over.
