---
paths:
  - "plugin/methodology/**"
  - "plugin/docs/**"
  - "plugin/skills/**"
  - ".prawduct/**"
  - ".claude/rules/learnings/**"
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

### A "keep both sides" conflict resolution silently drops whatever the BASE grew in a region the branch also touched — after a large base advance, diff the merged tree against the incoming commit for CONTENT, not just for conflicts, because the loss appears nowhere in the diff you reviewed. Eight active learnings lost their narrative blocks in a 216-commit merge: present at both parents, absent at HEAD, every rule still ending `— [learnings-detail.md]`, and the merge message recorded a different, verified deletion, so the collateral set read as accounted for. `check-learnings-pairing` is one-directional and saw nothing; a Critic Records Pass found it two chunks later, one merge short of propagating to develop. Tell: you resolved conflict hunks by keeping both sides and never compared the result against the side you were merging IN

Found 2026-09-09 by the Records Pass of `review-loop-termination` Chunk 04's cumulative review, two
chunks after the merge that caused it.

`feat/review-loop-termination` advanced its base over 216 develop commits, eighteen conflict hunks,
resolved by keeping both sides. The suite was green and the merge message recorded a deletion of four
historical `learnings-detail.md` entries, verified present in the archive — an honest, checked
record of an intended change.

Eight *other* narrative blocks went with them. Each existed at the interval base AND at the merged
develop commit; none existed at HEAD; all eight rules were still active in `learnings.md` and still
ended `— [learnings-detail.md]`, so each had become a citation to a file that no longer held it. None
had been moved to `learnings-history.md`.

Why nothing caught it: the accounted-for deletion made the region look reviewed, `check-learnings-
pairing` verifies index→detail in one direction only, and a merge diff shows conflicts rather than
content the other side grew. The next merge would have propagated the loss to develop.

The check that would have caught it is cheap and mechanical — after a large base advance, list the
`##` headings of a long-lived append-only record at both parents and at the merged tree, and account
for every heading present at either parent and absent at the result.

### After the last commit, re-check that the remote ref IS HEAD before creating or merging a PR — because every downstream signal agrees with a stale ref instead of contradicting it: the coverage gate reads LOCAL HEAD and re-runs green, CI grades the PUSHED tip and passes, the PR merges cleanly, and the description cites a commit the merge never took. Pushing early is legitimate (it is exactly the independent prep the reviewer-wait invites); what is missing is the re-check after the commit that follows it. Tell: you pushed at one point in the flow and committed at a later one. The only thing that catches it is `git branch -d` refusing the delete, which fires AFTER the merge

PR #803 merged one commit short of its branch, and nothing in a fully-governed flow noticed.

The sequence was ordinary. The branch was pushed with `-u` during the independent reviewer's run —
legitimate prep, and exactly what the skill's wait-time guidance asks for. The reviewer then
returned a WARNING; it was fixed, committed, and the commit was never pushed, because the push had
already happened and Step 5 reads as though push-and-create are one act.

What makes this worth a rule is how quiet it is. Every check that could have caught it is computed
from a ref that agrees with itself:

- `check-cumulative-critic` re-ran and reported `satisfied` — it reads LOCAL HEAD, which had the
  commit.
- CI passed — it grades the PUSHED tip, which did not, and had nothing to disagree with.
- `gh pr merge --merge` succeeded, because the PR was internally consistent.
- The PR description said the warning "is fixed in 662a86fe", naming a commit outside its own merge.

The single signal was `git branch -d` refusing to delete the local branch afterwards, on the
grounds that its tip was not an ancestor of the base. That is a real safety net and it worked — but
it fires AFTER the merge, when the remedy is no longer `git push` but a second PR against a
protected integration branch.

The framework gap this exposed (fixed in the same cycle): `pr/SKILL.md` Step 5 bundled "push with
`-u`" and "`gh pr create`" into one sentence, so it read as atomic, while Step 3 actively encouraged
the prep that splits them. Step 5 now requires `git rev-parse HEAD` to equal `git rev-parse @{u}`
after the push, and the Merge Flow carries the same check against `headRefOid` — the merge being the
irreversible act.

The general form is worth more than the instance: **a check is only a check if it can disagree with
the thing it grades.** Three green signals here were all downstream of the same stale ref. When
something can be stale, verify it against a source that does not share its staleness.
