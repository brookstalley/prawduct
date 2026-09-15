---
paths:
  - "plugin/bin/**"
  - "plugin/lib/**"
---

# Learnings — hook-surface

Rules that fire while changing the hook, its ops, or a library reader. **Reading a rule is not applying it.** Name the rule and say what it changes about the decision in front of you, or say that it does not apply.

<!-- Migrated from `.prawduct/learnings.md` in the v2 cutover merge (2026-09-15): these
     rules reached `develop` after the branch migrated its corpus, so they had no home in
     `core.md` and `core.md` had no headroom. Scoped here rather than appended there. -->

### Adding an op whose NAME EXTENDS an existing one silently widens every prefix-matching grant and guard naming the shorter one — Bash grants are prefix matches, so `file-upstream` inherited `Bash(... backlog file*)` no-prompt with all three grant tests green. Ask those guards by rule over the dispatcher's own op set, never over today's names. Tell: your new op shares a prefix with a granted one

### A comment reasoning about a CONDITION binds every branch that condition reaches, not the one you were writing — when you justify how a branch handles a degraded input, walk the sibling branches before moving on, because the reasoning is about the input and stopping writing is not evidence you stopped needing it. Tell: the comment names a condition ("a failed sync still answers ok") inside one arm of an `if`

`upstream_probes.py`'s intake count read the backlog cache and split degraded from healthy on
`status != "ok"`. A store whose last sync FAILED still answers `ok` — it carries its rows plus a
`sync_error` — so *readable* and *current* are two questions and only the first was being asked.

The comment above the count knew this. It said, in as many words, that a failed sync still answers
`ok`, and reasoned it through for the counting branch: stale rows can only under-report, a report
filed since the failure is missing rather than invented, so "at least N are waiting" is the honest
reading and silence would be the lie. Correct, and it stopped there. The zero branch — `if count ==
0: return []` — sat four lines below, where the same staleness turns the reading into a false
all-clear: nothing filed before the failure, nothing counted since, and no session-start signal at
all while filed reports go unread.

What makes this worth a rule rather than a shrug is that the same chunk's change-log paragraph
asserted the opposite behaviour ("a triage nudge that vanishes when its data source breaks reads
exactly like one that found nothing to say") and the plan's `governed_by` disposition cited the
*advice fails soft is not advice fails silent* norm by name. Three carriers of the right answer, and
the code did the wrong thing in the branch nobody wrote a sentence about. The defect was not a
missing case; it was **reasoning scoped to the branch being written rather than to the condition
being reasoned about**.

The fix separated the two axes at the seam — `_intake_reading` returns `(count, sync_is_stuck)` —
so a caller that collapses them fails in the helper's own test rather than in whichever branch
happens to be exercised. Both branches now use the second axis, in opposite directions: a stale
count is stated as a floor, a stale zero gets its own candidate with its own evidence (and therefore
its own dismissal key, since evidence is what the advisory id hashes).

**The cheap check that would have caught it:** after writing a comment that names a condition, grep
the function for every other `if` the condition can reach. It costs one read of a thirty-line
function.

---

### A lint that SKIPS what it cannot statically read needs a companion asserting everything is readable — otherwise it degrades silently into approval the first time someone hoists a string into a constant or behind a helper, which is ordinary refactoring instinct and invisible in review. Write the companion in the same commit as the lint; a "today nothing does this" comment is the version that fails

### Copying a fix into a sibling procedure or reader is a NEW change needing its own analysis — two of them share a paragraph or a regex, not their invariants, so ask what a WRONG value COSTS at each site, because that decides the fix's shape next door. Tell: you fixed one file and grep found the same lines elsewhere

Two documents share a paragraph, not their invariants, so one edit can repair one and break the
other. The 2026-09-10 instance widened the rule from documents to any parallel implementation, and
supplied the missing question: **what does a WRONG value cost at each site?**

`**Critic mode:**` and `**Type:**` are the same field grammar read by two modules. The mode reader
was fixed first: search the whole chunk section, bind the first VALID token, and prose is harmless
because only one of four words can win. Transcribed to `**Type:**` that is a hole. An unknown mode
earns a NOTE; an unknown type FAILS the chunk. And three of the six types *buy* something —
`designer-handoff` makes the stop hook set `designer_handoff_skip` and the Critic skill exit before
`critic-begin`. So a Description sentence naming `**Type:** designer-handoff`, in a chunk declaring
no type at all, would have switched review off silently in every governed product. Same regex, same
widening, opposite blast radius.

The fix was a construction rather than a longer list of shapes: one predicate deciding DECLARATION
vs mention (the marker opens its line, follows a `·`, or opens a sentence), shared by both readers
and spent only on BINDING — neither reports from it, because position is a heuristic and a
heuristic must not be what fails someone's chunk. **The sentence-opening arm is a knowing
residual**: real plans separate composed fields with a period, so a sentence that BEGINS with the
marker still binds, and the bound on that is prose in `methodology/planning.md` rather than code.
Narrowing the predicate would drop the composed forms the readers exist to find. The grammar moved to one factory in
`buildplan_refs` at the same time; the two hand-copied delimiter classes had already drifted, one
binding `<br>` and one reading the same line as declaring no field.

**The tell that the analysis was skipped**: the sibling's code open in one window, and a first
draft that was its loop with the label swapped.

---

### When a change redefines a FIELD, enumerate its READERS, not the documents that describe it — a surface list reads like completeness and is blind to the consumers comparing against the field's old meaning. Tell: your plan lists "surfaces this concept touches" and the field is a published key other modules compare against

### Instructions for driving code are sourced from the CODE's surface, with the design as a constraint on it — a design says what must be GUARANTEED and is silent on the states, refusal codes, envelope fields and failure modes no guarantee turns on, which is exactly where a reader meets reality. Tell: your instructions cite design sections and you never opened the handler

**What happened.** `/prawduct:report-bug` was rewritten to drive the `file-upstream` adapter, and
the rewrite was composed from the approved design: its payload section, its consent section, its
five-check contract. The design is correct and the instructions matched it. Six of the cumulative
review's eleven warnings were still the same defect — the skill under-specified against the
adapter:

- it branched on the `always-file` consent state, and no output carried that state, so the branch
  could never be taken and a shipped preference did nothing on its only consumer;
- it explained the `self-file` refusal as "you are in prawduct's own checkout", which is one of the
  two situations that code covers — and the other one routed the reader into the exact write the
  same skill forbids two sections later;
- it summarized the approval guarantee unconditionally, on a surface whose stated purpose is to be
  honest about what is and is not mechanical, when standing consent waives the byte comparison;
- it reduced a successful send to "print the URL", when the success envelope can carry a warning
  saying the idempotency check did not run — so a degraded filing reads as a clean one and the
  operator makes the retry that creates the duplicate;
- it treated a transport failure at create as a refusal, and answered it with "file by hand" —
  the one action that converts an unknowable outcome into a duplicate in a public repo.

**Why the design could not have prevented any of them.** A design states what must be guaranteed.
It is silent, correctly, about the states a value can hold that no guarantee turns on, the error
codes that distinguish two causes under one refusal, the fields an envelope carries besides the
result, and the failure modes that are neither success nor refusal. Those are exactly the places a
reader driving the code meets reality — and every one of the six lives there.

**The discipline.** Read the handler. Enumerate every state, every returned field, every refusal
code, every way it can fail, and give the reader a line for each — then check the design to see
which of those lines it constrains. Design-first produces instructions that are true and
incomplete; code-first produces instructions that are complete and then get checked for truth.

**Related.** This is the sibling of the rule that a guardrail on an instruction surface must model
the READER: that one is about testing the instructions, this one is about sourcing them.

### Checking the STATE after a repair does not verify what the repair REPORTED — read the writing run's own output, because the idempotent re-run that follows prints the right answer and covers the wrong one. Tell: you confirmed a fix by running it twice and reading the second

**The instance (2026-08-25, `prawduct-hook reanchor`).** `repair()` built its result by copying
`check()`'s dict and setting only `applied`. A successful `--apply` therefore returned `status:
stale` and the detail prose describing an anchor that lies to plugin-less clones — the condition it
had just removed. The CLI prints status and detail and stops (its confirmation block is gated on
`not applied`), `--json` published the same false state, and doctor maps every non-`ok` status to
degraded. A repair that worked reported itself as the problem.

**How it survived a product verification that ran the exact command.** The check was: seed a stale
repo, run `--apply`, run again, confirm `ok`. The transcript literally read

    reanchor (apply): stale        <- the wrong report, looked straight at
    reanchor (dry-run): ok         <- the re-run, which is what got believed

The second line answered the question being asked ("did the repair work?") and in doing so supplied
a plausible reading for the first. Idempotency checks are especially good at this: the follow-up run
is *designed* to print the healthy state, so it will always be there to explain away whatever the
writing run said.

**The rule is about which run you read, not about testing more.** A repair has two observable
outputs — the state afterwards, and the report it made while getting there — and only the second
reaches an operator in the moment. Verifying the first is not evidence about the second.

**What closes it mechanically:** an assertion on the WRITING run's output that names the pre-fix
status as forbidden (`assert STATUS_STALE not in result.stdout`), not merely the post state as
present. Both precedents in this family (`learnings_obligation`, `norm_index_scaffold`) return their
OK status on success, so copying the precedent's TEST file — not just its shape — would also have
caught it.
