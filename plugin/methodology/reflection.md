# Reflection: The Learning Loop

Reflection is how Prawduct gets smarter — not through accumulated rules or hooks, but through genuine understanding of what happened and why, captured in a form that influences future behavior. Without reflection, the system repeats mistakes; with it, the system evolves. The unit of value is a behaviour that changed, never a rule that was stored.

## When to Reflect

**Reflect at work boundaries — not at session end.** The primary reflection moment is when a unit of work concludes, while context is fresh. Writing reflections when the user says "ready to /clear" creates friction and hurts quality.

**Primary triggers** (reflect *now*, not later):
- **Right after Critic passes on a chunk** — the highest-signal moment; capture what independent review surfaced before moving on.
- **After fixing a bug** — especially: why did it exist? Root cause belongs in writing while the chain of whys is clear.
- **After recovering from an error or unexpected state** — failure modes are the richest source of learning.
- **After a non-trivial judgment call** — the rationale decays fast.
- **After a PR merge** — the close of a larger unit of work.

**Write reflections as they happen** to `.prawduct/.session-reflected`, appending across work cycles — one entry per chunk / bug / recovery. By the time the user says `/clear`, reflection is already done. **Session-end becomes synthesis, not from-scratch:** scan what you wrote and add a short synthesis only if a *cross-cutting* pattern emerged ("I kept hitting the same class of bug today"). If none is visible, the accumulated entries ARE the session reflection.

Depth scales with significance: a routine bug fix warrants a sentence; a structural failure warrants deep analysis. Noting "this went smoothly" is useful too — and "this went smoothly despite X" more so.

**The stop hook enforces the habit, not the cadence.** The prescribed cadence is work-boundary reflection; the hook checks only a session-end floor — when this session changed judgeable code, `.session-reflected` names what you expected vs. what actually happened and a root cause (or "no defect"). It trusts your judgment about what to reflect on and how deeply. If you've been reflecting at work boundaries, the gate is already satisfied. (Per-work-cycle governance is the methodology's responsibility, not the hook's — see `methodology/building.md` "Sessions and Work Cycles".)

## The Reflection Process

### Step 1: Assess
What happened? Was the outcome expected? If not, what's the gap between expected and actual?

### Step 2: Pattern-Match
Check the learnings rules (`.claude/rules/learnings/`, already in your context). Does this resemble a known pattern? If a learning exists but wasn't followed, that's important — it isn't prominent enough, needs refinement, or was the wrong lesson. If no relevant learning exists, this may be a new pattern worth capturing.

### Step 3: Root Cause (when something went wrong)
Don't fix the symptom — ask "what about the system allowed this?" and chain the whys:

- The test was wrong → Why was the wrong test written? → The spec was ambiguous → Why wasn't the ambiguity caught? → Spec review didn't apply the Skeptic perspective → Why not? → ...

Fixing a shallow cause patches one instance; fixing a deep cause prevents a class of problems.

**The stopping rule, stated so it survives being applied in a hurry.** Stop at the *shallowest* cause that satisfies all three: (1) you can change it **here**, in this repo, with the access you have; (2) changing it would have prevented **this** instance; (3) changing it would prevent instances that **do not look like this one**. Two of three is not a stop. Fail (3) and you have the symptom's parent rather than the class — keep chaining. Fail (1) and you have a cause you can only report: record it as a learning or a backlog item, and take the deepest cause you *can* change as the fix.

Three whys is typical, and the chain is short by default because most chains are. What signals it stopped **early** is a terminal that restates the failure instead of explaining it — "the model made a mistake", "we were in a hurry", "nobody reviewed it". None of those is something you can change, so none of them is a stop.

### Step 4: Capture — route what you learned to the one place it fires

What a reflection produces is one of four things, and each has exactly one home. Deciding which is the step; writing it is the easy part.

- **An episode** — what happened, expected vs. actual, the root cause or "no defect" — goes to **`.prawduct/.session-reflected`**, in that shape (it is the shape the gate grades). It is removed at the next session boundary (a fresh start or `/clear` — not a resume/compact/fork, which continue this session), and the machine-generated handoff is the only thing carrying it forward: nothing archives it. Most cycles produce an episode and nothing else.
- **A rule about this product** — a fact the model cannot know or derive: an API quirk, an invariant, an environment constraint, the consequence of a ratified decision — goes to **`.claude/rules/learnings/`**: `core.md` if it is cross-cutting, or the area file whose `paths:` frontmatter covers the files it governs, so the harness loads it only when those files are read. Write it as a heading that carries the rule, its brief why, and **the instance that earned it, inline** — the file that fires is the only one read at the moment a rule has to fire, so an instance relocated anywhere else is an instance lost. Never a narrative; the episode already holds that.
- **Framework friction** — a rule naming the Critic, a gate, a hook, a build plan or the backlog, or any lesson about prawduct rather than about this product — goes **upstream through `/prawduct:report-bug`** at the moment you write it, and is never stored as a product rule. A bug report against prawduct filed where no framework session will read it is a bug report nobody receives.
- **Portable engineering discipline** — a lesson that would be true in any repo, on any stack, about building software with an agent ("green is evidence only about what could have made it red") — is **not written as a product rule**. Say in the episode *why* it is portable and stop: the framework curates those into the surfaces where rules measurably fire (`docs/discipline.md` records where each lives), so a product that rewrites one has paid for a rule it already inherited.

**The corpus has a budget, and the budget is the curation mechanism.** Each rules file carries a byte ceiling (16KB by default; `learnings_budgets:` in `project-state.yaml` raises it per file, with a reason). A file over its ceiling *and grown this session* blocks at session end, and the payment is made by the author with the episode in hand: **merge or delete a genuine duplicate in the same commit, or raise the budget with its reason — never trim a rule to fit.** The descent obligation that governs reading the rules lives in `core.md`'s own header, two sentences long; it is not restated here.

Good rules have: **context** (one sentence), **what happened**, **why** (root cause), **lesson** (what to do differently), and the **related principle**. Bad rules are too abstract ("be more careful with tests"), too specific ("in file X line 42 change Y"), or write-only (filed where nobody reads them).

### Step 5: Evolve
Should this learning change anything upstream? **Strengthen a principle** that's consistently violated because it's too abstract; **amend the methodology** when a guide misses a recurring case; **improve an existing learning** that proved insufficient; **propose a new principle** for a pattern fundamental enough to recur across projects. This step closes the learning loop — without it, learnings accumulate but the system doesn't evolve.

### Step 6: Persistence and Boundary Check

Before ending a work cycle, verify:

**Persistence**: Any plans, chunk definitions, or significant decisions created this cycle but not yet in an artifact? Persist them now — anything not in a file is lost.

**Deferred work**: Any items identified as out-of-scope? Add them via `/prawduct:backlog add` (it stamps `source:` — `builder`, `critic`, or `reflection`), one item with enough context to be actionable later.

**Earn the backlog entry — don't let it inflate.** The backlog is for work with a *real, near-term consumer*:
- **File it** when the item has a user-facing payoff or concrete pending need (a bug a product hits, a feature someone awaits, a refactor blocking work).
- **Do NOT file** pure internal-ceremony items — stricter-review proposals, doc-prose tightening, speculative checks with no current consumer. Capture these as a reflection or a learning instead. A NOTE correctly judged out-of-scope *because there's no consumer yet* belongs in a spec/proposal appendix, not the pickable `## Open` section.
- **Cross-product lessons** belong to *that product's* backlog or a methodology-research note, not this repo's pickable backlog.

Rationale: auto-filed NOTEs turn one-time observations into perpetual every-session lines — how a backlog drifts from a working set into a self-portrait of the tooling reviewing itself.

**Work cycle boundary**: Is the work complete and the next task independent? Then prepare the close — (1) reap any ad-hoc delegate this cycle dispatched: collect its branch and its report, and name the integration debt it hands you — here, and never as a mid-flow interrupt (`methodology/delegation.md` argues why), (2) persist pending requirements/decisions/plans — that integration debt included, (3) update the build plan Status section — mark chunks, update Context, (4) write the forward notes — the line "nothing beyond the plan" if that is the truth, but not *no file*, which tells the next session you left none, (5) state explicitly that governance is complete.

**Then close the turn with the standing block** — its shape, its trigger, the clear verdict and what a live review or an unreaped delegate does to it are `methodology/session-hygiene.md`, the one home for how a turn ends; the session digest injects the shape into every session, so it reaches you whether or not you open that guide.

### Step 7: Methodology Check

Did the methodology help or hinder? One sentence suffices for smooth sessions. When governance felt disproportionate, a scenario wasn't covered, or you worked around the process — say so specifically. This is the most valuable feedback the system receives.

## Framework Reflection

At natural milestones (finishing discovery, planning, a build or subsystem), reflect more broadly:

- **Proportionality**: Was the effort appropriate for this product's risk?
- **Coverage**: Did discovery, planning, and building address the right things?
- **Applicability**: Did any artifacts or processes feel forced for this product type?
- **Missing guidance**: Did you improvise anywhere? That signals a methodology gap.
- **Concern completeness**: Any cross-cutting concerns not surfaced anywhere in the pipeline? Check `.prawduct/cross-cutting-concerns.md`, and think about what's missing from the registry itself.
- **Learning completeness**: Were observations captured for everything significant?

This produces change-log entries and may trigger methodology updates. **Product feedback review**: periodically scan product repos' `.claude/rules/learnings/` for methodology feedback that should have gone upstream — the reverse channel; products discover gaps the framework can't see from inside.

## Post-Fix Reflection

When fixing a bug or recovering from an error, apply root-cause discipline before implementing:

1. **Classify**: product bug or framework/methodology issue? Framework issues get deeper analysis.
2. **Root cause**: chain the whys to something structural — don't stop at "the code was wrong." A reported cause is a hypothesis until you reproduce it against live data; the report's own evidence often carries the disproof.
3. **Fix scope**: fix the root cause, not the symptom. If it's in the methodology, update the methodology.
4. **Meta-check**: could the same root cause manifest elsewhere? Fix those too.
5. **Capture**: route it as Step 4 says — failures are the richest source.

## Learning Lifecycle

The lifecycle is the only growth path, and its end state is a deletion.

**Provisional**: a single incident; may be wrong or over-specific. Format: "When X, do Y because Z", with the instance inline.

**Confirmed**: validated across 2+ incidents or by the user. It stays in `.claude/rules/learnings/` — the rules that change behaviour — and its second instance joins the first.

**Incorporated**: a confirmed rule violated again despite capture is promoted to structure — a test, a hook check, a Critic goal, or a methodology sentence — **and then deleted from the rules file.** Incorporated is the product; the rules file is the waiting room, and a small waiting room is the point. Git is the history: a retirement is a deletion whose commit message is the forwarding address. This is how learnings become governance.

**Consolidation is the same act under the budget.** Two rules that say one thing are merged into the stronger one, instances unioned, in the commit that would otherwise have grown the file. Nothing consolidates for you, and nothing archives what you remove.
