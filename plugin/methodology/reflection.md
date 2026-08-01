# Reflection: The Learning Loop

Reflection is how Prawduct gets smarter — not through accumulated rules or hooks, but through genuine understanding of what happened and why, captured in a form that influences future behavior. Without reflection, the system repeats mistakes; with it, the system evolves.

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

**The stop hook enforces the habit, not the cadence.** The prescribed cadence is work-boundary reflection; the hook checks only a session-end floor — `.session-reflected` exists and has content. It trusts your judgment about what to reflect on and how deeply. If you've been reflecting at work boundaries, the gate is already satisfied. (Per-work-cycle governance is the methodology's responsibility, not the hook's — see `methodology/building.md` "Sessions and Work Cycles".)

## The Reflection Process

### Step 1: Assess
What happened? Was the outcome expected? If not, what's the gap between expected and actual?

### Step 2: Pattern-Match
Check `learnings.md`. Does this resemble a known pattern? If a learning exists but wasn't followed, that's important — it isn't prominent enough, needs refinement, or was the wrong lesson. If no relevant learning exists, this may be a new pattern worth capturing.

### Step 3: Root Cause (when something went wrong)
Don't fix the symptom — ask "what about the system allowed this?" and chain the whys:

- The test was wrong → Why was the wrong test written? → The spec was ambiguous → Why wasn't the ambiguity caught? → Spec review didn't apply the Skeptic perspective → Why not? → ...

Stop when you reach something you can change. Fixing a shallow cause patches one instance; fixing a deep cause prevents a class of problems.

### Step 4: Capture
Two targets, two purposes:

- **`.prawduct/.session-reflected`** — the *narrative* of this work cycle. A short entry per reflection; archived to `reflections.md` at the next session boundary (a fresh start or `/clear` — not a resume/compact/fork, which continue this session).
- **`.prawduct/learnings.md`** — *standing rules* future sessions should follow. Add here only when the cycle produced a durable lesson; most cycles produce a reflection entry and no new learning.

Good learnings have: **context** (one sentence), **what happened**, **why** (root cause), **lesson** (what to do differently), and the **related principle**. Bad learnings are too abstract ("be more careful with tests"), too specific ("in file X line 42 change Y"), or write-only (filed where nobody reads them).

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

**Work cycle boundary**: Is the work complete and the next task independent? Then prepare the close — (1) persist pending requirements/decisions/plans, (2) update the build plan Status section — mark chunks, update Context, (3) write the forward notes — the line "nothing beyond the plan" if that is the truth, but not *no file*, which tells the next session you left none, (4) state explicitly that governance is complete.

**Then close the turn with the standing block.** The trigger — the same one every surface states — is **any turn that ends a chunk or work cycle, or that you end with work outstanding**; it is not every turn, and appending it to trivial Q&A trains the user to skip it, reproducing by volume the burying it exists to prevent.

Write for the person who walked away: a long build leaves them returning to a wall of text, and they read the bottom. Everything they need in the next five seconds goes last, after every other word, in this exact shape — **three separate paragraphs, a blank line between each, the labels backticked so the terminal renders them as coloured tokens**:

```
`STATE` — done / blocked / waiting; committed or not; suite green or not.

`NEXT` — the ONE next action, and whose it is.

`CLEAR` — Safe to `/clear`. — or — Not safe to `/clear` yet: [what has to happen first].
```

The shape is part of the signal, not decoration. Three answers run together as list items, or bolded inline inside a paragraph, stop being *separately* findable — and separately findable is most of what the block is for, because the reader is scanning for one of the three, not reading all three. Blank lines give each its own landing place; the backticked label is the only coloured token near the bottom of the turn, so the eye finds it without reading.

What each line owes:

1. **State** — done, blocked, or waiting; whether the work is committed; whether the suite is green. No hedging. This is the "did it work?" they scrolled down to answer.
2. **Next** — the ONE next action and **whose it is**. Someone back after ninety minutes needs to know immediately whether they are the blocker or you are. If it is theirs, say exactly what you need; if it is yours, say what you are doing and roughly how long.
3. **Clear** — the safety verdict, and when it is negative, what has to happen first.

**Three ways to fail this, all equally expensive.** *Omitting it* — silence gets read as whichever answer they were hoping for, and they clear on top of live work. *Burying it* — the same lines, correct and complete, in the middle of a long summary; a signal above the fold is a signal not sent. *Padding it* — a closing paragraph of prose that has to be parsed is a closing paragraph that gets skipped. None of these is fixed by writing more.

**Outstanding means in flight, not just unstarted — and anything outstanding takes the second line, named.** Critic reviewers dispatched but not consolidated; a `/prawduct:pr` reviewer still running; any background agent whose output you have not read; a Critic run this work owes; a governance step that was skipped or failed. The coordinator case is the one that catches people: a `final`/`cumulative` review dispatches three subagents and the fork returns immediately, so your turn ends with the review still running — that turn takes the second line. Never signal safety to close a turn tidily. See `methodology/building.md` "Session Scope Discipline".

**Forward notes are not a reflection.** A reflection looks back at what happened; `.prawduct/.handoff-notes.md` looks forward at what the next session needs — where you stopped, what you'd do next, what would bite them. It is one of the two session files **you** own — the other is `.prawduct/.session-reflected`, the subject of this guide, which is why the pairing is easy to confuse. The rest of what the next session receives is machine state about the past, plus whatever you curated into the build plan's Context block. The generated `.prawduct/.session-handoff.md` is the machine's: it is rewritten from your notes at every `/clear`, so writing into it directly is how context gets lost.

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

This produces change-log entries and may trigger methodology updates. **Product feedback review**: periodically scan product repos' `learnings.md` for methodology feedback — the reverse channel; products discover gaps the framework can't see from inside.

## Post-Fix Reflection

When fixing a bug or recovering from an error, apply root-cause discipline before implementing:

1. **Classify**: product bug or framework/methodology issue? Framework issues get deeper analysis.
2. **Root cause**: chain the whys to something structural — don't stop at "the code was wrong."
3. **Fix scope**: fix the root cause, not the symptom. If it's in the methodology, update the methodology.
4. **Meta-check**: could the same root cause manifest elsewhere? Fix those too.
5. **Capture**: add to learnings — failures are the richest source.

## Learning Lifecycle

**Provisional**: single incident; may be wrong or over-specific. Format: "When X, do Y because Z."

**Confirmed**: validated across 2+ incidents or by the user. Promoted to active rules in `learnings.md` — the learnings that change behavior.

**Incorporated**: encoded into methodology, templates, or hooks. Archived from active rules — the wisdom lives in the system's instructions now.

**Recurrence escalation**: a confirmed learning violated again despite capture is promoted to structural enforcement — a hook check, Critic rule, or CLAUDE.md repetition. This is how learnings become governance.

## Managing Learnings Over Time

Two files, split by purpose:

**`learnings.md`** — concise standing rules, organized by topic (not chronology): each entry a `## ` heading that states the rule and its brief why in one line ("When X, do Y because Z"), with the full narrative kept in `learnings-detail.md` under the same heading — not duplicated here. Keywords in the heading trigger pattern recognition; the headings feed the session briefing.

**`learnings-detail.md`** — full root cause / fix / rule format with `## Topic` headers, consulted when debugging in a known area. No size constraint.

The `/prawduct:learnings [topic]` skill reads both in a forked context and returns only what's relevant. The Critic and PR reviewer read the full files directly.

**Prune regularly.** A learning incorporated into methodology or structurally enforced has done its job — condense or remove it. **Consolidate** related entries into single stronger ones. **Keep `learnings.md` scannable** — most common first; stale entries archived. Learnings have freshness: yesterday's is highly relevant; a three-month-old one never reinforced may be an artifact of one situation.

Example of a concise rule:
> **Pydantic v2**: Never use `@computed_field` in models with `extra="forbid"` — it serializes but fails deserialization. Use `@property` for derived values.

The corresponding `learnings-detail.md` entry carries the full observation, error message, root-cause chain, and fix.

## Reflections Archive

Session reflections in `.prawduct/.session-reflected` are automatically archived to `.prawduct/reflections.md` at the next session boundary (a fresh start or `/clear`) — an unbounded historical record for framework improvement, NOT loaded into session context.
