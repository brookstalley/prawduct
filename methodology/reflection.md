# Reflection: The Learning Loop

Reflection is how Prawduct gets smarter. Not through accumulated rules or additional hooks — through genuine understanding of what happened and why, captured in a form that influences future behavior.

This is the most important methodology guide. Without reflection, the system repeats mistakes. With it, the system evolves.

## When to Reflect

**After every significant action.** Not every keystroke — every meaningful outcome:
- Completing a feature or chunk
- Fixing a bug (especially: why did it exist?)
- Recovering from an error or unexpected state
- Making a decision that required judgment
- After receiving Critic findings (the richest source of learnings — an independent perspective surfacing blind spots you can't see yourself)
- Ending a session where work was done

The depth of reflection scales with significance. A routine bug fix might warrant a single sentence. A structural failure that required significant recovery warrants deep analysis.

**The session-end reflection is mandatory.** Before ending any session where files were modified, reflect on what happened. The stop hook enforces this — not the specific content of the reflection, but the habit of reflecting.

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
Update the project's `.prawduct/learnings.md` with what you learned. Write it in natural language that your future self will actually internalize when reading it at session start.

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

### Step 6: Methodology Check

Did the methodology help or hinder this session? One sentence is enough for sessions where things went smoothly. When governance felt disproportionate, a common scenario wasn't covered, or you had to work around the process — say so specifically. This is the most valuable feedback the system can receive, and it's how the methodology itself evolves.

## Framework Reflection

At phase transitions (finishing discovery, completing planning, finishing a build, beginning iteration), do a broader reflection:

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

## Managing Learnings Over Time

`learnings.md` should be a living document, not an ever-growing log:

**Prune regularly.** When a learning has been incorporated into a principle or methodology update, it can be condensed or removed from learnings.md — its wisdom now lives in the system's instructions.

**Consolidate related entries.** Multiple learnings about the same pattern should merge into a single, stronger entry.

**Keep it readable.** If learnings.md grows past ~3,000 tokens, it's time to prune. The most common learnings should be first. Stale or fully-incorporated learnings should be archived or removed.

**Learnings have freshness.** A learning from yesterday is highly relevant. A learning from three months ago that hasn't been reinforced might be an artifact of a specific situation rather than a general pattern. Review old learnings with fresh eyes.

### When learnings outgrow one file

Projects with sustained building accumulate detailed technical learnings — root cause analyses, debugging stories, framework-specific gotchas. These are valuable as debugging reference but too large for ambient session context. When learnings.md grows past the ~3,000-token threshold and pruning alone isn't enough, split into two files:

**`learnings.md`** (~3,000 tokens, always loaded at session start)
- Organized by **topic area**, not chronologically
- Each entry: the rule + brief "why" (1-3 lines)
- Enough keywords in each rule to trigger pattern recognition when a related problem occurs
- Footer pointing to the detail file

**`learnings-detail.md`** (no size limit, consulted when stuck)
- Full observation / root cause / fix / rule format
- Organized by topic area with clear `## Topic` headers for searchability
- Consulted when: hitting an error in a known area, debugging something unexpected, or working in a domain with known pitfalls

The key design: `learnings.md` is the **index** (cheap to load, triggers recognition), `learnings-detail.md` is the **reference** (rich context for when you need to reason about *why* something works the way it does). The concise rules help you know *when* to consult the detail.

Example of a concise rule in `learnings.md`:
> **Pydantic v2**: Never use `@computed_field` in models with `extra="forbid"` — it serializes but fails deserialization. Use `@property` for derived values. Model validators that set fields must use `self.__dict__[]` to avoid recursion with `validate_assignment=True`.

The corresponding detail in `learnings-detail.md` would have the full observation, the actual error message, the root cause chain, and the fix — invaluable when debugging a variant of the same problem, but unnecessary as ambient context.

## The Mechanical Enforcement

The stop hook is the one piece of mechanical enforcement in the learning loop. It checks:
- Were files modified during this session?
- If yes, was reflection captured?

If no reflection was captured, the hook blocks session exit with a reminder. This enforces the habit, not the content. The system trusts your judgment about what to reflect on and how deeply — it just ensures you don't skip the habit entirely.

This is the minimum viable enforcement: one hook, one check. If this proves insufficient (reflection is consistently shallow or skipped), the enforcement can be tightened. But start light and add enforcement only when the system demonstrates it needs it.
