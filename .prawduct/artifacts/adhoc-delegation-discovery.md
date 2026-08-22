# Discovery — Ad-Hoc Delegation (Tangents and Deferred Work)

**Status:** requirements drafted, owner-ruled on four shaping questions; design not yet built.
**Parent:** `delegation-and-verification-cost-discovery.md` — that feature governs *planned*
delegation (a build plan's chunks, partitioned at plan time). This one covers the other trigger:
work that arrives when no plan anticipated it.

---

## 1. The ask

Two moments, in the owner's words:

- *"When a user is mid-session and asks for something tangential, the natural thing to do is
  propose a subagent, so the current context and focus is not lost."*
- *"When the natural instinct is to propose backlogging related work, prawduct should encourage
  proposing a subagent on a worktree to address in the background."*

And two binding rules stated with the ask:

- *"These ad hoc subagents should follow the same rules we specify in delegation: do not run heavy
  tests, the coordinating agent is responsible for integration and live testing."*
- *"They have the same absolute rule that they must understand requirements before building.
  Either they draft the requirements, the coordinator passes them in, the coordinator references
  existing docs, or they stop and demand clear requirements."*

## 2. What is genuinely new here

The parent feature answers *how to split work you already scoped*. Everything in it — the
verification ceiling, the brief contract, the anti-patterns, the `Delegation` /
`Delegate verification` / `Delegation approval` preference rows — carries over unchanged. Three
things do not carry over, and they are the whole of this design.

### 2.1 The trigger is an interrupt, not a boundary

The parent's load-bearing bet was placement: *"guidance-only is what already failed at 0.34%; the
delegation question has to arrive where the coordinator is already stopping."* So it fires where
chunk boundaries are drawn and at a chunk close.

A tangent has no such boundary. It arrives as a user message in the middle of a chunk. Prawduct
registers `SessionStart`, `Stop` and `SubagentStop` hooks — nothing fires on a user message, and
adding a `UserPromptSubmit` probe would have to classify tangency from prose, which
`docs/norms.md` § Deliberate Non-Design rules out ("no prose-parsing probes — a probe that
misfires trains its reader to ignore the one real catch").

Two stopping points do exist:

- **`/prawduct:backlog add`.** When the agent is about to file the tangent, a skill runs. This is
  the exact analogue of the parent's plan-time prompt, and it covers the *second* moment in the
  ask verbatim.
- **The work-cycle boundary**, where reaping and the standing block already live.

The *first* moment — a tangent raised mid-chunk with no backlog intent — has only one carrier that
reaches it: the always-injected session digest. That is expensive real estate and is this
design's main placement risk (§8).

### 2.2 Under the owner's own rule, a delegated tangent is never *done*

If the coordinator owns integration and live testing, an ad-hoc delegate does not produce finished
work. It produces a branch plus an **integration debt** — a combined run, live verification, the
Critic, state updates, a merge. And the trigger the ask names ("the main agent's context is almost
full and should be cleared") *guarantees* the agent that incurred the debt is not the one who will
pay it.

So the role has to move: **coordination is a role recorded on disk, not an agent held in memory.**
A debt that lives only in the dispatching agent's context evaporates at `/clear`, leaving an
unmerged branch and a worktree nobody remembers creating.

### 2.3 The feature's real product is a safe `/clear`, not a spawn

`methodology/reflection.md`'s work-cycle-boundary rule — mirrored in the always-injected digest —
already says an unread background agent is `RUNNING`, never `COMPLETE`. Read literally, that rule
*forbids* the thing the ask wants: dispatch a tangent so the main context can be cleared.

The resolution is not to weaken it. It is to make the record the thing that buys the clear:

> An in-flight ad-hoc delegate is `RUNNING` and `DO NOT CLEAR`. A **reaped** delegate whose debt is
> on disk is `SAFE TO CLEAR`, and the debt's presence on disk is what makes it so.

That inverts the feature from "a new way to spawn work" into "the discipline that makes clearing
safe while work is outstanding," which is what actually resolves the hour-long-agent versus
nearly-full-context tension in the ask.

## 3. Diagnosis — the three costs a naive version would pay

Recorded because the design exists to hold them down, and because each becomes an anti-pattern
with a tell (§4.3).

**Delegating a tangent does not save context; scoping it spends context.** A backlog item is
*allowed to be underspecified* — `pick` routes an early-`stage:` item to discovery later. A
delegate is not: the brief contract requires the work, an ownership boundary, a verification
ceiling, a return form, and who integrates, and the owner's requirements rule adds a requirements
bar on top. "The brief that costs more than the work" is already a named anti-pattern. A rule that
fires on *every* tangent burns the most main context on exactly the tangents that most needed
offloading.

**Ad-hoc delegation is a WIP multiplier.** Backlog items are cheap to create *and cheap to
abandon* — many tangents die on their own, which is a feature of deferral, not a defect. A
delegate is cheap to create and expensive to abandon: the compute is spent, and what is left is a
branch that must be integrated, or explicitly killed, while decaying against a moving main line.
Unmerged branches are inventory. This runs against Scope Discipline (#12) and Proportional
Effort (#11), and the design answers it with disclosure of outstanding debt rather than a quota.

**Session-bounded dispatch means an unreapable delegate is worse than a backlog item.** The owner
ruled delegates session-bounded (§7, D3). A delegate whose expected runtime exceeds the session's
remaining useful context yields the worst outcome available: compute spent, no result read, a
worktree orphaned, and a `DO NOT CLEAR` the user must sit through or override. Backlogging that
same tangent costs one line.

## 4. The shape of the answer

### 4.1 The goal

**Work that is not the current work cycle's gets an explicit three-way decision — do it now,
delegate it, or backlog it — made once, out loud, with its cost stated.** Delegation is offered
first by default; the project sets the policy. A delegate builds only against requirements it can
name, verifies only its own change, and hands back a branch plus a report. The debt it leaves is
on disk before the session ends.

### 4.2 Considerations — questions, not rules

Inherited from the parent guide's style. The answers differ by project and by moment.

- **Would you integrate this today if it came back green?** If not, the honest artifact is a
  backlog item, and dispatching is a way of saying yes without meaning it.
- **Can you state the requirement, or point at the artifact that states it?** If neither, the
  delegate's job is to *draft* requirements, not to build (§4.4).
- **Will it still merge cleanly?** Isolation prevents delegates fighting *during* the run. It does
  nothing about the merge, and the tangent's branch ages against the line you are actively moving.
- **Can you reap it before you need the context back?** Expected delegate runtime against
  remaining useful main context is a real comparison, and the answer "no" means backlog.
- **How much already awaits integration?** A fifth outstanding branch is a different proposal from
  a first one, and the user should hear which one this is.

### 4.3 Anti-patterns, each with a tell

- **The delegate you cannot reap.** *Tell:* you estimated its runtime as longer than the context
  you have left, and dispatched anyway.
- **The brief that scoped the tangent.** *Tell:* scoping it cost more context than doing it would
  have, or more than the one-line backlog entry it replaced.
- **The un-ratified requirement.** *Tell:* a branch carries a requirements doc nobody approved and
  code that already implements it.
- **The debt that lives in your head.** *Tell:* you can name which branch needs integrating and no
  file can.
- **The tangent that was a decision.** *Tell:* the delegate was dispatched to decide something
  rather than to build something already decided.
- **Delegation as a way to say yes.** *Tell:* you dispatched because declining felt unhelpful, not
  because the work was ready to hand over.

### 4.4 The requirements bar (owner ruling, absolute)

An ad-hoc delegate never builds against unclear requirements. Four permitted paths, and no fifth:

1. The coordinator states the requirements in the brief.
2. The coordinator references an artifact that already states them.
3. The delegate drafts them **first**, as its first deliverable.
4. The delegate stops and demands them.

Path 3 has a sharp edge: a delegate drafting requirements is doing discovery, and requirements
drafted in a worktree and never ratified are `building.md`'s "silently *invent* a requirement"
failure in a new costume — with the branch's existence standing in for approval. So a delegate's
drafted requirements return **proposed**, marked as such, and ratification is part of the
integration debt.

### 4.5 The brief is the dispatch record

The brief contract already requires a brief. Writing it **into the delegate's worktree** rather
than only into the prompt makes it the record of the dispatch: what was delegated, what it owns,
what it may run, what it must not do, and who integrates. No registry, no schema, no lease — the
artifact that had to exist anyway identifies the worktree and carries the debt's terms.

Consequence: an abandoned delegate worktree is detectable from the filesystem alone, which is what
makes the orphan advisory (§4.6) possible without inventing state.

### 4.6 Where the debt lives after reaping

Every carrier already exists. Nothing new is introduced:

- **In-session, unreaped** — the standing block's `RUNNING` / `DO NOT CLEAR`.
- **Across `/clear`** — `.prawduct/.handoff-notes.md`, in prose, naming the branch and what it
  still owes.
- **When the tangent is a backlog item** — the item's own `accepted-by:` claim and
  `status: promoted`, which already mean "someone is on it" and "in flight."
- **When a worktree is left behind** — an advisory at session start, from the presence of a brief
  in an unmerged worktree. Resolved by integrating, or by abandoning it with the reason recorded.

### 4.7 Disclosure and the policy dial

The parent's asymmetry holds — **inform always, ask only on a named reason** — with the
proposal carrying what varies: what the delegate will do, what it will *not* do, that integration
is owed and by whom, and how many ad-hoc branches already await integration (Principle 9, Visible
Costs).

Aggressiveness is a **policy** decision, not a technical one (D1). The guide states the default —
delegation-first — and `project-preferences.md`'s existing `Delegation` row is where a project
changes it. `off` remains a complete answer, honoured without ceremony.

## 5. Requirements

**The decision**

- **R1** Work identified that is not the current work cycle's — a tangent the user raises, or work
  the agent would otherwise propose backlogging — gets an explicit three-way decision: do it now,
  delegate it, or backlog it.
- **R2** The stated default is delegation-first. It is a policy setting: the guide states the
  default, `project-preferences.md`'s `Delegation` row overrides it in the project's own words,
  and `off` means the proposal is never made.
- **R3** A dispatch proposal discloses, before dispatch: what the delegate will do, what it will
  not do, that its result carries an integration debt and who is expected to pay it, and how many
  ad-hoc branches already await integration.

**The requirements bar**

- **R4** An ad-hoc delegate never builds against unclear requirements. Exactly four paths are
  permitted: requirements passed in the brief, an artifact referenced, drafted by the delegate as
  its first deliverable, or the delegate stops and demands them.
- **R5** Requirements a delegate drafts return marked **proposed**. Ratification is the
  coordinator's or the owner's and is part of the integration debt — never implied by the branch
  existing.

**What a delegate does**

- **R6** The parent guide's contract binds ad-hoc delegates unchanged: a verification ceiling that
  is the narrowest run proving its own change and never the coordinator's integration run; no
  governance acts (no Critic, no state updates, no Status ticks, no backlog writes); the
  coordinator owns integration and live verification.
- **R7** An ad-hoc delegate's deliverable is a branch plus a report naming what it verified, what
  it assumed, and what it left for integration.
- **R8** The brief is written into the delegate's worktree and is the dispatch record. No
  registry, schema, lease or slot accounting is introduced.

**Reaping, clearing, debt**

- **R9** Dispatch is session-bounded: do not dispatch what this session cannot reap. Expected
  runtime against remaining useful context is part of the decision, and "cannot reap" means
  backlog instead.
- **R10** The standing block accounts for ad-hoc delegates: unreaped is `RUNNING` and
  `DO NOT CLEAR`; reaped with its debt on disk may be `SAFE TO CLEAR`. The record on disk is what
  makes the clear safe.
- **R11** Reaping happens at a work-cycle boundary, not as a mid-flow interrupt — the mechanism
  that exists to protect focus must not be the thing that breaks it.
- **R12** A delegate worktree left unintegrated is surfaced at session start as an advisory,
  resolved by integrating it or by abandoning it with the reason recorded.

**Placement**

- **R13** The doctrine lives in `plugin/methodology/delegation.md`; `building.md` carries a
  pointer only.
- **R14** `/prawduct:backlog add` raises the delegation question when the item describes work in
  this repo that is ready to build — not for idea-stage capture.
- **R15** `methodology/reflection.md`'s work-cycle-boundary rule carries the reaping step and the
  block semantics of R10.

## 6. Explicitly out of scope

- **Delegates that outlive the session** — detached processes, cloud agents, cron. D3 rules
  session-bounded; anything longer is a backlog item today.
- **Automatic tangent detection.** No `UserPromptSubmit` hook, no prose-parsing probe
  (`docs/norms.md` § Deliberate Non-Design).
- **Any new registry, schema, lease, semaphore or slot accounting** — the parent design collapsed
  for proposing exactly this.
- **Auto-merge of delegate branches**, and delegates opening PRs. A PR is a coordinator act;
  `/prawduct:pr` dispatches an independent reviewer.
- **Delegates running the Critic** or any other governance act.
- **A quota on outstanding debt.** Disclosure (R3), not a threshold — a number the framework
  invents would be wrong in every repo.

## 7. Decisions (owner rulings)

- **D1 — Delegation-first, as policy.** The default is to propose a delegate, controlled by
  `project-preferences.md`, revisable later. *"This should be a policy decision, not a technical
  decision."*
- **D2 — Branch plus report, debt recorded.** The delegate commits to its own branch, verifies
  narrowly, and returns a report; integration, live testing, Critic and state updates are a debt a
  later coordinator inherits from the record.
- **D3 — Session-bounded, and part of the block.** Dispatched delegates live inside the session
  and are accounted for by `RUNNING` / `SAFE TO CLEAR`.
- **D4 — Doctrine plus one small mechanism.** A `delegation.md` section, the block amendment, the
  backlog prompt, one advisory over carriers that already exist.
- **D5 — The requirements bar is absolute**, with the four paths of R4.

## 8. Findings and open questions

### 8.1 The digest cannot fund a new trigger line (measured)

The mid-chunk tangent has no carrier but the always-injected digest, so the digest budget decides
how much of the ask is deliverable. Measured against `tests/test_v5_methodology.py`:

| Shape | Reading | Ceiling | Headroom |
|---|---|---|---|
| framework | 3310 | 3322 | 12 |
| product | 2236 | 2245 | 9 |

And the governing rule is a ratchet: *"a ceiling left at its old value after a cut silently
re-funds the growth the cut paid for — the next addition trims or relocates, it does not bump."*
A phrase that would actually change behaviour costs several times the headroom, so **an always-on
tangent trigger has to be funded by deleting something of comparable value from the digest**, and
this feature's line would have to outrank what it displaces. On-demand guides carry a reading and
no ceiling, so the *doctrine* is free; only the always-on trigger is expensive.

**Where the digest's weight actually sits** (same estimator, measured 2026-08-21): "The hardest
rules" is 1121 of 1974 tokens, and two bullets inside it are 23% of the whole file — the standing
block (287) and forward/handoff notes (176). Those are the two bullets this feature must touch.
Roughly 50-80 tokens across them restate `reflection.md` (:97 the findings-only rule, :116 the
forward/backward pairing and the machine's file) — but two rules in the handoff bullet, "never ask
whether to prepare one" and "never blind-append", appear in the digest and nowhere else. Relocating
those would be a behavioural loss for every session that never opens the guide, dressed as a dedup
(the learning that governs this: funding a budget by deleting what another surface says is only
valid for readers who *receive* that surface). The standing block's cost is a format spec needed at
write time on every closing turn, which is the case a pointer serves worst.

Two consequences, one mandatory and one a decision:

- **Mandatory.** The digest's standing-block bullet already states that an unread background agent
  is `RUNNING`, never `COMPLETE`. R10 contradicts that as written, so the amendment must land in
  the digest regardless of budget — the alternative is an injected rule that forbids the feature.
  It should be sought as a **rewording at or near zero net cost**, not an addition.
- **A decision.** The mid-chunk tangent trigger is optional. Serving the ask at
  `/prawduct:backlog add` plus the work-cycle boundary covers the second moment in §1 fully, and
  the first only when the agent's instinct was already to file something. Three ways to buy the
  first moment: displace a digest line of comparable value; consolidate the two boundary bullets
  (worth doing on its own merits, with its own review — not as this feature's funding source); or
  **raise the ceiling deliberately**. The ratchet forbids *undeclared* growth, not declared growth
  — the test's own comment requires a departure to say why. Ruling the trigger worth N tokens is
  the same kind of policy call as D1.

### 8.2 Open questions

- **Defensive asking.** The parent design warned that an agent resolving vagueness "asks
  defensively every time." A prompt at `backlog add` risks becoming exactly that. The ready-to-
  build qualifier in R14 is the intended guard; whether it holds is a thing to watch, not a thing
  provable here.
- **Reap failure.** What a coordinator does when a delegate returns unusable work — a wrong
  approach, an assumption the owner would veto — is integration's problem, and integration is
  already the coordinator's. Worth a sentence in the guide; not obviously worth a requirement.
