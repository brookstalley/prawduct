# Reflection: The Learning Loop

Reflection is how Prawduct gets smarter. Not through accumulated rules or additional hooks — through genuine understanding of what happened and why, captured in a form that influences future behavior.

This is the most important methodology guide. Without reflection, the system repeats mistakes. With it, the system evolves.

## When to Reflect

**Reflect at work boundaries — not at session end.** The primary reflection moment is when a unit of work concludes, while context is fresh. Writing reflections when the user says "ready to /clear" creates friction (the user is waiting) and hurts quality (rushed recall).

**Primary triggers** (reflect *now*, not later):
- **Right after Critic passes on a chunk** — the highest-signal moment. The Critic just gave you independent feedback; capture what it surfaced before you move on.
- **After fixing a bug** — especially: why did it exist? Root cause belongs in writing while the chain of whys is clear.
- **After recovering from an error or unexpected state** — failure modes are the richest source of learning.
- **After making a non-trivial judgment call** — the rationale decays fast.
- **After a PR merge** — the close of a larger unit of work.

**Write reflections as they happen** to `.prawduct/.session-reflected`, appending across work cycles within a session. A session's reflection file accumulates organically: one entry per chunk / bug / recovery, each dated or labeled. By the time the user says `/clear`, the reflection is already done.

**Session-end becomes synthesis, not from-scratch.** When a session ends, scan what you already wrote during the session and add a short synthesis only if a *cross-cutting* pattern emerged (e.g., "I kept hitting the same class of bug today," "the methodology felt heavy for this work type"). If no cross-session pattern is visible, the accumulated per-work-cycle entries ARE the session reflection — no further writing needed. `/clear` is fast.

The depth of reflection scales with significance. A routine bug fix might warrant a single sentence. A structural failure that required significant recovery warrants deep analysis.

**The stop hook enforces the habit, not the cadence.** The prescribed cadence is work-boundary reflection; the hook checks only a session-end floor — `.session-reflected` exists and has content. It trusts your judgment about what to reflect on and how deeply. If you've been reflecting at work boundaries throughout the session, the gate is already satisfied — no last-minute scramble. (Per-work-cycle governance is the methodology's responsibility, not the hook's — see `methodology/building.md` "Sessions and Work Cycles".)

## The Reflection Process

### Step 1: Assess
What happened? Was the outcome expected? If not, what's the gap between what you expected and what actually occurred?

Don't skip this even when things went well. "This went smoothly" is useful to note — it means the methodology worked for this case. "This went smoothly despite X" is even more useful — it identifies a risk that didn't materialize this time.

### Step 2: Pattern-Match
Check the project's `learnings.md`. Does this situation resemble any known pattern? Have you seen this failure mode before? Is there a learning that should have prevented this?

If a learning exists but wasn't followed, that's important. It means either the learning isn't prominent enough, or it needs refinement to be more recognizable, or it was the wrong lesson.

If no relevant learning exists, that's also information — this is a new pattern worth capturing.

### Step 3: Root Cause (when something went wrong)
Don't fix the symptom. Find the structural cause.

Ask: "What about the system allowed this?" Not "what broke?" but "why was it possible for this to break?"

Chain the whys:
- The test was wrong → Why was the wrong test written? → The spec was ambiguous → Why wasn't the ambiguity caught? → Spec review didn't apply the Skeptic perspective → Why not? → ...

Stop when you reach something you can change. The root cause is the deepest point in the chain where a change would prevent recurrence. Fixing a shallow cause patches one instance; fixing a deep cause prevents a class of problems.

### Step 4: Capture
Two targets, two purposes:

- **`.prawduct/.session-reflected`** — the *narrative* of what happened this work cycle. Append a short entry (a paragraph or a few bullets) each time you reflect. This is per-session and gets archived to `reflections.md` on next session start.
- **`.prawduct/learnings.md`** — *standing rules* future sessions should follow. Only add here if this work cycle produced a durable lesson. Most work cycles produce a reflection entry but no new learning; that's fine.

Write in natural language that your future self will actually internalize when reading it at session start.

Good learnings have:
- **Context**: What was the situation? (Brief — one sentence.)
- **What happened**: What went wrong or right?
- **Why**: The root cause or the reason it worked.
- **Lesson**: What to do differently (or the same) next time.
- **Related principle**: Which principle does this reinforce or extend?

Bad learnings are:
- Too abstract: "Be more careful with tests" teaches nothing.
- Too specific: "In file X line 42 change Y to Z" doesn't generalize.
- Write-only: Filed away where nobody reads them. (This is why learnings live in learnings.md, not in structured YAML archives.)

### Step 5: Evolve
Ask: should this learning change anything upstream?

- **Strengthen a principle?** If a principle is consistently being violated because it's too abstract, add concreteness to it.
- **Amend the methodology?** If a methodology guide doesn't cover a case that keeps arising, add guidance.
- **Update learnings.md?** If an existing learning was insufficient, improve it.
- **Propose a new principle?** If a pattern is fundamental enough and recurs across projects, it might deserve principle status.

This step is what closes the learning loop. Without it, learnings accumulate but the system doesn't evolve. With it, every failure makes the system genuinely better.

### Step 6: Persistence and Boundary Check

Before ending a work cycle, verify two things:

**Persistence**: Were any plans, roadmaps, chunk definitions, or significant decisions created during this work cycle but not yet written to an artifact? If so, persist them now. Conversation context does not survive across sessions — anything not in a file is lost.

**Deferred work**: Were any items identified as out-of-scope during this work cycle? Add them via `/prawduct:backlog add` (it stamps `source:` — `builder` for work you identified, `critic` for Critic NOTEs that warrant future investigation, `reflection` for ideas surfaced during reflection — rather than a hand-edit). One bullet per item with enough context to be actionable later. These items are surfaced in the next session's briefing and triaged during `/prawduct:janitor` runs.

**Earn the backlog entry — don't let it inflate.** The backlog is for work with a *real, near-term consumer*, not a graveyard for every observation. Before filing, apply this bar:
- **File it** when the item has a user-facing payoff or a concrete pending need (a bug a product hits, a feature someone is waiting on, a refactor blocking other work).
- **Do NOT file** pure internal-ceremony items — proposals to make the review stricter, doc-prose tightening, "validate against more datapoints first," or speculative checks with no current consumer. Capture these as a *reflection* (the narrative) or a *learning* (a standing rule), not as a pickable backlog item. A NOTE you correctly judged out-of-scope *because there's no consumer yet* belongs in a spec/proposal appendix, not the pickable `## Open` section.
- **Cross-product lessons** (something learned in product A while working on the framework, or vice versa) belong to *that product's* backlog or a methodology-research note — not this repo's pickable backlog.

Rationale: a NOTE auto-filed into the pickable backlog turns a one-time review observation into a perpetual every-session line. Unbounded filing is how a backlog drifts from a working set into a 50-item self-portrait of the tooling reviewing itself.

**Work cycle boundary**: Is the current work complete and the next task independent? If so, complete handoff and *affirmatively* tell the user `/clear` is safe — do not leave them guessing. Before signaling: (1) persist any pending requirements, decisions, or plans to artifacts, (2) update the build plan Status section in `.prawduct/artifacts/build-plan.md` — mark completed chunks and update the Context line — so the next session's briefing and handoff file surface the task, (3) then say explicitly that governance is complete and `/clear` is safe, noting what was persisted. Never signal safety if any governance step was skipped or failed. See `methodology/building.md` "Session Scope Discipline" for the full protocol.

### Step 7: Methodology Check

Did the methodology help or hinder this session? One sentence is enough for sessions where things went smoothly. When governance felt disproportionate, a common scenario wasn't covered, or you had to work around the process — say so specifically. This is the most valuable feedback the system can receive, and it's how the methodology itself evolves.

## Framework Reflection

At natural milestones (finishing discovery, completing planning, finishing a build or subsystem), do a broader reflection:

- **Proportionality**: Was the effort level-appropriate for this product's risk? Too much? Too little?
- **Coverage**: Did discovery surface everything important? Did planning cover the right artifacts? Did building address the right risks?
- **Applicability**: Were the artifacts and processes relevant to this product type, or did some feel forced?
- **Missing guidance**: Did you have to improvise anywhere? That's a signal the methodology might need extension.
- **Concern completeness**: Are there cross-cutting concerns this product should address that aren't surfaced anywhere in the pipeline? Check `.prawduct/cross-cutting-concerns.md` as a starting point, but think about what's missing from the registry, not just what's listed.
- **Learning completeness**: Were observations captured for everything significant that happened?

This broader reflection produces change log entries and may trigger methodology updates. It's how the system stays calibrated across different product types.

**Product feedback review**: If product repos exist, periodically scan their `learnings.md` for methodology feedback. This is the reverse channel — products discover gaps that the framework can't detect from the inside.

## Post-Fix Reflection

When fixing a bug or recovering from an error, apply root cause discipline before implementing the fix:

1. **Classify**: Is this a product bug or a framework/methodology issue? Product bugs get fixed normally. Framework issues get deeper analysis.
2. **Root cause**: Chain the whys until you reach something structural. Don't stop at "the code was wrong."
3. **Fix scope**: Fix the root cause, not just the symptom. If the root cause is in the methodology, update the methodology.
4. **Meta-check**: Are there other places where the same root cause might manifest? Fix those too.
5. **Capture**: Add to learnings. This is the most important time to capture — failures are the richest source of learning.

## Learning Lifecycle

Learnings evolve through stages:

**Provisional**: Single incident. May be wrong or over-specific. Captured after a Critic finding or unexpected outcome. Format: "When X, do Y because Z."

**Confirmed**: Validated across 2+ incidents or explicitly confirmed by user. Promoted to active rules in `learnings.md`. These are the learnings that change behavior.

**Incorporated**: Encoded into methodology, templates, or hooks. Archived from active rules — the wisdom now lives in the system's instructions, so the learning entry is redundant.

**Recurrence escalation**: When a confirmed learning is violated again despite being captured, it's promoted to structural enforcement — a hook check, Critic rule, or CLAUDE.md repetition. This is how learnings become governance.

## Managing Learnings Over Time

Learnings are split across two files by purpose:

**`learnings.md`** — concise standing rules
- Organized by **topic area**, not chronologically
- Each entry: the rule + brief "why" (1-3 lines)
- Enough keywords in each rule to trigger pattern recognition when a related problem occurs
- Section headers are extracted by the session briefing for ambient context

**`learnings-detail.md`** — full root cause / fix / rule format
- Consulted when: hitting an error in a known area, debugging something unexpected, or working in a domain with known pitfalls
- Organized by topic area with clear `## Topic` headers for searchability

The `/prawduct:learnings [topic]` skill reads both files in a forked context and returns only what's relevant to your task — keeping your main context clean. Use it before planning work in an unfamiliar area. The Critic and PR reviewer read the full files directly for comprehensive cross-checking.

**Prune regularly.** When a learning has been incorporated into a principle or methodology update, condense or remove it from `learnings.md`. When a learning has been structurally enforced (hook, gate, code pattern that prevents the mistake), it has done its job and can be pruned.

**Consolidate related entries.** Multiple learnings about the same pattern should merge into a single, stronger entry.

**Keep `learnings.md` scannable.** Most common learnings first. Stale or fully-incorporated learnings should be archived or removed. The detail file has no size constraint.

**Learnings have freshness.** A learning from yesterday is highly relevant. A learning from three months ago that hasn't been reinforced might be an artifact of a specific situation rather than a general pattern.

Example of a concise rule in `learnings.md`:
> **Pydantic v2**: Never use `@computed_field` in models with `extra="forbid"` — it serializes but fails deserialization. Use `@property` for derived values. Model validators that set fields must use `self.__dict__[]` to avoid recursion with `validate_assignment=True`.

The corresponding detail in `learnings-detail.md` would have the full observation, the actual error message, the root cause chain, and the fix — invaluable when debugging a variant of the same problem.

## Reflections Archive

Session reflections are written to `.prawduct/.session-reflected` during the session and automatically archived to `.prawduct/reflections.md` on the next session start. This archive is an unbounded historical record intended for framework improvement — it is NOT loaded into session context. It captures the full narrative of how the methodology performed across all sessions, providing the raw material for prawduct evolution.

