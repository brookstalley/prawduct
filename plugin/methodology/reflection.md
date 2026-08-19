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
---

`STATE` — what changed; committed or not; suite green or not.

`RUNNING` / `YOUR TURN` / `COMPLETE` — one only: a machine event produces the next turn / only you can / nothing needs to.

`SAFE TO CLEAR` / `DO NOT CLEAR` — the label is the verdict; the copy is the reason.
```

The shape is part of the signal, not decoration, and each element does a different job. The `---` rule is the only horizontal break in the turn, so it separates the block from the wall of text above it before the reader has parsed a word. Blank lines give each answer its own landing place — three answers run together as list items, or bolded inline inside a paragraph, stop being *separately* findable, and separately findable is most of what the block is for, because the reader is scanning for one of the three, not reading all three. The backticked labels are the only coloured tokens near the bottom of the turn, so the eye finds them without reading — which is why each label states its own answer instead of naming a topic. A label the reader has to read past to learn the verdict has spent its colour on nothing.

What each line owes:

1. **State** — the evidence, not the verdict: what changed, whether it is committed, whether the suite is green. No hedging. This is the "did it work?" they scrolled down to answer, and it is what makes the line below *earned* rather than merely asserted.
2. **Disposition** — exactly one of `RUNNING`, `YOUR TURN`, `COMPLETE`, chosen on a single axis: **what produces the next turn.** Not "is there a problem" — that question mixes a diagnosis into a slot that owes a verdict.

   - `RUNNING` — a machine event will: a dispatched agent, a monitor, a background command, a scheduled wake-up. They can walk away; results arrive without them. **Name the event, and bound the promise** — a dead subagent, a timed-out monitor or a stalled queue silently falsifies "results will arrive", so say what you do if it does not land ("if it is not back in ~10 min I re-check"). An unbounded `RUNNING` can strand someone on a turn that never comes.
   - `YOUR TURN` — only a human utterance will. Nothing is pending; the session is inert until they speak. The label answers *is it me?*; the **copy leads with the ask, imperative, cheapest form first**, because its three shades cost them very different amounts: *just go* ("say go — nothing else needed"), *decide* ("pick A or B"), *unblock* ("I need push access to the release remote"). Obstruction is one of those shades, not a label of its own — a reason belongs in the copy.
   - `COMPLETE` — nothing needs to. **A blank slate: you have no next action to propose.** Not "a unit of work finished" — ending a plan while knowing a PR is the obvious next step is `YOUR TURN`. Read this way the label stays rare enough to mean something.

   **Precedence:** if a human utterance is required it is `YOUR TURN` even when something is also running — they are the binding constraint — and the copy names what is in flight, because that fact leaves the label and would otherwise be lost.

   **But do not predict one.** A turn where something is running and a decision *may* be needed once it lands is `RUNNING`, never `YOUR TURN`: you cannot know the decision will be needed, since the job may return "option 1 is clearly correct". This line reports what **is**, never what might be; put the forewarning in the copy.
3. **Clear** — `SAFE TO CLEAR` or `DO NOT CLEAR`. The label is the verdict and the copy is the reason, so someone who reads the label and nothing else has already been answered. This line answers a different axis from the one above it — not whose move it is, but **what survives a clear** — which is why both are needed.

   **A findings-only turn is not safe to clear until its findings are on disk.** The verdict is defined by disk and process state, so a turn whose entire output is analysis *in the conversation* — an investigation, a comparison, a design you talked through — computes as safe while clearing destroys everything it produced. Persist to `.prawduct/.handoff-notes.md` first, then claim it. The tell that this went wrong is a `SAFE TO CLEAR` whose stated reason **cites the message itself** ("the analysis is above"): a reason that points at the thing a clear deletes is not a reason, it is the defect stated out loud.

   **Write the notes before a long wait, not after it.** If you are about to dispatch something slow, persist first — then a reader who walks away mid-run finds the session already as clearable as it can be, with only the running work blocking, which resolves itself. The worst outcome this line exists to prevent is a multi-hour task landing while they are away and the turn still saying `DO NOT CLEAR`: they return to both a cold cache and a session they cannot leave, purely because bookkeeping trailed the work. **At the conclusion of a long-running task, reaching `SAFE TO CLEAR` is part of the task**, not a report about it.

**Three ways to fail this, all equally expensive.** *Omitting it* — silence gets read as whichever answer they were hoping for, and they clear on top of live work. *Burying it* — the same lines, correct and complete, in the middle of a long summary; a signal above the fold is a signal not sent. *Padding it* — a closing paragraph of prose that has to be parsed is a closing paragraph that gets skipped. None of these is fixed by writing more.

**Outstanding means in flight, not just unstarted — and anything outstanding takes the disposition line, named: `RUNNING` when the work is only waiting on the event, `YOUR TURN` when you also owe them something, and never `COMPLETE`.** Critic reviewers dispatched but not consolidated; a `/prawduct:pr` reviewer still running; any background agent whose output you have not read; a Critic run this work owes; a governance step that was skipped or failed. The coordinator case is the one that catches people: a `final`/`cumulative` review dispatches three subagents and the fork returns immediately, so your turn ends with the review still running — that turn is `RUNNING`, never `COMPLETE`. Never signal safety to close a turn tidily.

**Choosing the label is a procedure, and its first step is not a label at all:**

1. **Is there work you can do right now with what you have? Then do it — do not end the turn.** Handing back to ask permission you do not need costs a round-trip and, if they stepped away, a context replay into a cold cache. This step yields to one hard stop: **a chunk boundary whose review has not run.** There you stop even with work in hand.
2. Is a machine event pending that will produce the next turn? → `RUNNING`, naming it and what you do if it does not land.
3. Is everything finished, with nothing outstanding on disk or in flight? → `COMPLETE`.
4. Otherwise → `YOUR TURN`.

**Four ways to get the label wrong**, each tempting for its own reason: `RUNNING` with nothing actually running — "I'll continue next turn" is `YOUR TURN`; `COMPLETE` with a dispatched review unfinished; `YOUR TURN` reached by skipping step 1, which spends their attention to buy nothing; and the ask buried mid-paragraph instead of leading the copy. See `methodology/building.md` "Session Scope Discipline".

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

Each archived block is preceded by a provenance tag line — `<!-- prawduct: version=X.Y.Z | archived=YYYY-MM-DD -->` — recording the plugin version that archived it, so the corpus can be grouped by release without reconstructing it from prose dates. `version=unknown` means the version could not be read, never that the reflection is suspect. The file is gitignored, so this line is the only history it has.
