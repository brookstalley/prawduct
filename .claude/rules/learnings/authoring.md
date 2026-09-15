---
paths:
  - "plugin/methodology/**"
  - "plugin/docs/**"
  - "plugin/skills/**"
  - ".prawduct/artifacts/**"
---

# Learnings — authoring

Rules that fire while writing durable prose: methodology, docs, specs, records. **Reading a rule is not applying it.** Name the rule and say what it changes about the decision in front of you, or say that it does not apply.

<!-- Migrated from `.prawduct/learnings.md` in the v2 cutover merge (2026-09-15): these
     rules reached `develop` after the branch migrated its corpus, so they had no home in
     `core.md` and `core.md` had no headroom. Scoped here rather than appended there. -->

### A chunk boundary defers a DELETION, never a CORRECTION — when your chunk falsifies a sentence whose surface the plan assigned to a later chunk, fix the falsehood NOW and leave only the removal. A claim's home and its truth-condition are different things: a plan listing a file under Chunk 02 said where the prose lives, not when it stopped being true

### When you change a MECHANISM, cascade-search the CLAIM, not just the code — edited tokens find every site that RUNS the old procedure, never the prose that DESCRIBES it. Enumerate the claims FIRST, **plural**: a change usually falsifies more than one, and cascading the one your plan named leaves the rest standing. Tell: you can state the claim you searched for in the singular

**The case that produced it.** Fixing the tag/publish order caught both runbooks and the process
doc via the command strings `git tag` / `gh release create`. The Critic then found a stale "on
every tag push" in `architecture.md`, a superseded command in a historical release plan, and one
doc asserting flatly what another hedged — none of them reachable from any string that had been
edited, because a sentence describing what the system does shares no token with the code that does
it.

**The amendment, 2026-09-07 — enumerate the claims first, and expect more than one.** Rewriting
`/prawduct:report-bug` onto the upstream filing adapter falsified two claims, not one: *it writes a
drop-box file* and *it otherwise captures the bug locally*. The build plan named the first, so the
first is what got cascaded; the second kept its carriers — `prawduct-hook`'s `cmd_bug_inbox`
docstring, which still published the exit-code contract of a caller that no longer existed and
instructed the very local capture the new design forbids, and `architecture.md`'s Persistence
Boundaries row, which still named the retired write path as the live one.

What makes this worth recording rather than filing under carelessness: the same session had, one
chunk earlier, written a reflection *about this rule* after a claim turned out to have four
carriers. Knowing the rule and having just been burned by it were both insufficient, because the
rule as written starts one step too late. The failure is not in the searching. It is that the set
being searched for was assembled from the plan's sentence about the change rather than from the
change itself — and a plan names the claim that motivated the work, not every claim the work
happens to falsify.

The cheap discipline: before cascading anything, write down what is no longer true, as a list. If
the list has one item, ask what else the change made false. The enumeration takes a minute; a
carrier that survives it reads as current until someone trips on it.

### A reflection written at speed is a HYPOTHESIS, and re-reading your own note later feels like evidence — re-derive a diagnosis from provenance before building on it, because the mechanism freshest in context is the one you will blame. A session reflection named the doc-only fast path as the cause of a red integration branch; the actual cause was two commits pushed directly to it with CI failing unread, found only by asking the API which PR carried them. The fix built on the wrong reading would have been inert. Tell: your causal claim names the file you happened to be reading when the symptom appeared

### A ruling recorded only where the deciding team reads it is NOT recorded — put it in the artifact the ASKERS receive, because finding the rule, seeing it filed as a bug twice, and finding no statement that the answer is settled reads as "known bug, still open". Tell: the ruling is in your governance state and the change-log, and the shipped copy got only the rule

Same cycle. Two downstream products filed the same defect a day apart, each proposing that the
parser be widened to accept the shape that tripped them. The widening was declined and the reasoning
written up carefully — in this repo's own `operator-verification.md` queue header and in the
change-log. The plan asserted it was in the shipped template too. It was not: the template got the
shape call-out and stopped short of saying the widening had been considered and refused.

The consequence is specific rather than tidy-mindedness. The audience that produced both reports
reads only the template. It would have found a rule, an acknowledgement that the rule gets filed as
a bug repeatedly, and no statement that the question is settled — and the cheapest reading of that
is "known bug, still open", whose natural actions are a third report or a local parser patch. A
decision's home is wherever the people who keep asking the question will meet it.
