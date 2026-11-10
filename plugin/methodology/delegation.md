# Delegating Work to Subagents

**Default: if splitting the work across subagents would finish it sooner and the pieces won't collide, split it.** Stay serial when pieces share files or need each other's output, when a piece is smaller than the brief it would need, or when this project's preferences say so.

You are the coordinator, and how you arrange the work is your call. Five things hold however you arrange it:

- **Tell the user.** Before the first dispatch of a work cycle, say what you are fanning out, to how many agents, on which models, and who integrates. The first time in a session, add that `project-preferences.md` → `Delegation` is where they change whether and how this happens.
- **Delegates run on Opus- or Sonnet-class models, and you choose.** The stronger where a piece needs design judgment or is a review; the lighter where it is well specified. Set reasoning effort the same way. Never lighter than Sonnet-class.
- **Delegates do not run heavy tests.** A delegate proves its own change with the narrowest run that could fail because of it. What is heavy here (the full suite, integration and end-to-end runs, anything slow, paid, or contending for the machine) runs once, on the merged result. `Delegate verification` in preferences says what counts; absent that, the declared suite does.
- **One integration branch.** Delegate branches merge there and the heavy run happens there. Hold it yourself, or hand it to a dedicated integrator subagent when merging and long runs would otherwise eat your context or stall dispatch. An integrator is the one delegate that runs heavy tests. Review, project state and the decision that the work is done stay with you either way.
- **Nothing outlives the cycle unrecorded.** An unmerged delegate branch is written where the next session will read it, and a merged one is reaped.

A brief says the work, the files this delegate owns, what proves it, what to return, and who integrates.

---

Everything below is reference: what makes the five hold in practice, and the ways delegation has gone wrong.

## Model and effort are yours to set

**Always name the model at dispatch.** A dispatch that names none inherits yours, and on a session running a tier stronger than Opus-class that is the most expensive choice available, made by accident. A fan-out multiplies it: N delegates on the top tier is N times the mistake. Opus-class or Sonnet-class is the default for build, research and integration delegates alike; putting one on your own stronger tier is a deliberate exception you can justify in a sentence and name in the disclosure — never the default, and never the result of leaving the field out. Name the class rather than pinning one model alias, falling back down the chain to whatever the host offers that is still Sonnet-class or stronger.

**Set reasoning effort the same way.** The host gives a subagent an effort of its own only when instructions explicitly ask for one, so this guide is that ask: choose an effort per piece, as you choose the model.

"A piece that is a review" means review-shaped delegated work. Dispatch of the Critic and the PR reviewer is governed by their own skills, not by this guide.

## When serial is right

**Parallel is not automatically faster, and the wall clock to compare is the bounded one.** Three delegates each running the run the integration branch will do is more load and more wall clock than one run there. The partition is usually drawn with a build plan, before any brief exists, but the bound is a property of the *chunk*: ask what would prove each chunk on its own. **A chunk you cannot answer that for is not scoped tightly enough to hand to anyone**, which is worth more than the estimate you were trying to make. A plan-time partition is a default, not a commitment; re-check it at dispatch against what the machine is actually doing.

Conflict between pieces is paid at merge, after every delegate has finished being confident, so "won't collide" means disjoint files *and* no seam both would write: a shared table, a router, a budget test. Give each seam one owner.

Serial is a decision like any other. Record it either way in the plan's `partition:` field. Where `project-preferences.md` and this guide differ, the preferences win, and `Delegation: off` means delegation is never proposed.

## Who does what

**A delegate verifies what proves its own change, and nothing beyond it.** It builds; it does not govern. A harness scratch worktree is unbound, and the governance commands (`critic-begin`, dispositions, advisories, plan and state writes) refuse there, naming you as the one who runs them.

**An integrator** holds the integration branch, merges delegate branches as they land, resolves conflicts, runs the heavy tests, and reports the merged head and the result. You review on that head, update project state, and decide the work is done; the Critic, reflection and the done decision never move to it. It is the one delegate that leaves its scratch branch: have it switch its isolated worktree onto the integration branch (`git switch <branch>`, which needs your own checkout off that branch). A heavy run from a scratch branch is recorded as a narrowed fact in the shared store, not as that branch's test evidence, so the gates on the integration branch would still read stale and the run would be paid for twice.

**Considerations, not rules** — the answers differ by project, machine and moment:

- **What is this machine already doing?** Verification, not editing, is the wall clock, and the clamps protecting a box from one run are per-process: they do not compose across N delegates.
- **What in this project's regime is expensive** — in time, money, credentials, or dependence on something nobody here controls — **and does this piece need any of it?** A failure in a test that depends on an uncontrolled third party says nothing about the delegate's change.

## What a brief must say

What has to be said, in your own words — not a template. A brief that could be copy-pasted from the last one has stopped carrying information.

- **The work** — the chunk spec and the artifacts it references, or the task stated in full.
- **The ownership boundary** — what it owns, what it must not touch, and any budget its files sit under (a size ceiling, a byte cap) that it would otherwise meet only as a red test.
- **A verification ceiling** — the narrowest run that covers its own change. **Read `project-preferences.md`'s `Delegate verification` row first**: a ceiling invented beside one the owner ratified is the retyping that row exists to end.
- **What to return**, and in what form — for a removal or a sweep, the output of the command that shows it complete.
- **Who integrates** — you or your integrator, by name, so the delegate neither merges nor governs.

If you cannot state the ownership boundary without re-reading the other briefs, the partition isn't ready.

## Dispatch and reaping

**Dispatch with `isolation: "worktree"`.** It is the only shape that moves a delegate: a worktree you create and point it at does not hold, because Bash `cd` does not persist between calls and a skill forks in the session's own directory, so its git commands land in your checkout. The tree is `.claude/worktrees/agent-<id>` on branch `worktree-agent-<id>`, and it reads HEAD, so commit what it must see or put it in the prompt and say the prompt outranks any file. That branch is cut from the repo's default branch, not yours: on gitflow the prompt's first instruction is `git reset --hard <your branch>`, or the delegate builds against a release. A build delegate does not switch branches: a named branch in a worktree binds through its plan like any checkout, which is what the integrator's switch is for. The rest of dispatch is `/prawduct:methodology building` § Delegating Work to Subagents.

**Write the brief into the delegate's worktree**, at `.prawduct/.delegate-brief.md`, as soon as the launch returns its id. It is the dispatch record — what was delegated, what it owns, who integrates — and what makes an abandoned worktree visible. No registry, no schema, no lease. A brief written *by* the delegate is missing in exactly the case it exists for, one that dies early.

**Do not dispatch what this session cannot reap.** Expected runtime against the useful context you have left is a real comparison, and "no" means backlog. Reap at a work-cycle boundary, never as a mid-flow interrupt.

**Reaping ends with the worktree, not with the merge.** Take the branch and the report, merge it, then `prawduct-hook git-tidy --reap <worktree>` removes the worktree and its branch; a brief left in a reused checkout raises an advisory about work nobody delegated. What an unreaped delegate does to the clear verdict is `/prawduct:methodology session-hygiene`.

## Anti-patterns

Each carries a **tell** — the thing you can catch yourself doing.

- **The silent fan-out.** *Tell:* the user learned how many agents ran, or on what, from their results.
- **The inherited model.** *Tell:* a dispatch with no model named, from a session on a tier stronger than Opus-class.
- **The delegate that verifies the whole product.** *Tell:* the brief names a command the integration branch will run.
- **N baselines.** *Tell:* the brief says "make sure tests pass before you start." A delegate inherits your baseline.
- **The unattributable green.** *Tell:* you accepted a pass count without knowing what was collected, from a box running several agents. A worker that dies under contention is typically not re-queued and does not fail the run, so one tree can report different totals, all exiting 0. Record it as what it is: `test-evidence record --degraded "<what did not report>"`, which the gates read as stale rather than as a pass.
- **The Done taken on faith.** *Tell:* you accepted a completion report on a removal or a sweep that carried no evidence — no grep for the removed symbol, no recount against the source. These fail in the direction of looking finished.
- **Boundaryless fan-out.** *Tell:* you cannot say which files each delegate owns without reopening their briefs.
- **The delegate that governs.** *Tell:* a brief tells a delegate to run the Critic or update project state — including an integrator's.
- **Serial by default.** *Tell:* a plan with independent chunks and no partition decision recorded either way. Serial is very often right; *unexamined* is what this names.

## Work no plan anticipated

The other trigger is an interrupt — a tangent the user raises mid-chunk, or work you are about to propose backlogging.

**A delegated tangent is never *done*.** What comes back is a branch plus an integration debt: a merge, the heavy run, live verification, the Critic. Isolation stops delegates fighting *during* the run and does nothing about the merge, and the branch ages against the line you are moving. The reason you delegated — this context is full, or nearly — means the agent that incurred the debt may not be the one who pays it, so the debt is **a record on disk, not an agent held in memory**: the brief in the worktree.

**The decision is three-way, made once, out loud: do it now, delegate it, or backlog it.** `project-preferences.md`'s `Delegation` row sets the policy, and `off` means delegation is never proposed. The sorting question: *would this be integrated today if it came back green?* If not, backlog it; if it takes a handful of tool calls, do it now; delegate it when it runs beside your work and touches nothing yours does. When you disclose it, say **how many ad-hoc branches already await integration** — a fifth is a different proposal from a first.

**Requirements first — four paths, and no fifth.** You state them in the brief, or you reference an artifact that already states them, or the delegate drafts them as its first deliverable, or it stops and demands them. A delegate drafting requirements is doing discovery: drafted requirements come back marked **proposed**, and ratifying them is part of the debt, or the branch's existence stands in for approval.

**What it hands back is a branch and a report** naming what it verified, what it assumed, and what it left for integration.

### Anti-patterns, ad-hoc

- **The delegate you cannot reap.** *Tell:* you estimated its runtime as longer than the context you had left, and dispatched anyway.
- **The brief that scoped the tangent.** *Tell:* scoping cost more context than doing the work would have, or more than the one-line backlog entry it replaced.
- **The un-ratified requirement.** *Tell:* a branch carries a requirements doc nobody approved and code that already implements it.
- **The debt that lives in your head.** *Tell:* you can name which branch needs integrating and no file can.
- **The tangent that was a decision.** *Tell:* the delegate was dispatched to decide something rather than to build something already decided.
- **Delegation as a way to say yes.** *Tell:* you dispatched because declining felt unhelpful, not because the work was ready to hand over.
