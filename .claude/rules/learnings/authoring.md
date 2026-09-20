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

**The amendment, 2026-09-17 — the sweep that crosses FILES is blind to the carrier in the file you
are editing.** Fixing `/prawduct:pr` Step 1 to name `test-evidence record`, the enumeration ran
exactly as prescribed: grep the claim, find the carriers, check each. It reported two, and it was
right about both — `building.md` and `delegation.md` already said it correctly. A cumulative review
then found a third, `SKILL.md`'s own `## Important` checklist, a hundred and fifty lines below the
edited sentence and still naming only `test-status`.

What makes this worth a second amendment rather than a shrug is the specific false confidence.
A cross-file sweep *feels* exhaustive precisely because it crossed files: having proved you looked
beyond your own edit, the file under your cursor reads as territory you have already covered — and
you have, in the sense that you are looking right at it, which is not the sense that matters. The
same-file carrier is usually the worst kind, too, because it sits under a heading like `## Important`
or `## Summary` whose whole job is to restate the procedure a reader might not scroll to.

**The cheap discipline, extended: grep your own file first, then the siblings.** And when the
same-file carrier is a restatement, the remedy is a construction, not a third copy — point it at the
one home and say that it deliberately does not restate, or the next editor updates two of three.

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

The check that would have caught it is cheap and mechanical, and a HEADING account is not it —
that is the half this rule was read as prescribing, and it is the half that already failed. The
v3.5.1 cutover merge verified all 318 headings survived, and they did, while five bodies had been
revised in place: three lost outright, two shipped twice. **Account for CONTENT: for every unit at
either parent, find its counterpart in the result and compare the TEXT, keying on an opening short
enough to survive a rewording.** `audit_against_incoming` in `tests/test_learnings_files.py` is that
check — it separates `missing` (no counterpart at all) from `diverged` (counterpart found, text
differs), and only the second can see a revision. A divergence is not automatically a defect; the
other side may have revised it deliberately. It is always a DECISION, and the merge that makes it
silently is the one that goes wrong.

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

### A QUOTATION you lift into a durable record drifts toward the generalisation you are writing toward, and that direction is why it survives review — verify quoted evidence mechanically, exactly as you would a `file:line`, because a paraphrase that SHARPENS the source reads as good writing rather than as an error. Tell: the address resolved, so the quote felt checked

Measured 2026-09-18 by the audit of `mcp-mining/hallucinote-server-structured.md`, a 106-rule capture
in which **every cited address resolved** — 0 NOT-FOUND, every constant matching the tree.

Of 202 quoted evidence fragments, 170 matched the source exactly. **Nineteen did not, and one appeared
nowhere in the tree at all.** No path check can see this class, which is the trap: the schema puts a
`PROVENANCE:` line under every quote, so verifying the address creates the impression that the
quotation came with it.

**The direction is the finding, and it is what makes the class undetectable.** The two edits that
mattered both moved *toward* the generalisation the corpus was being written for:

- an error-model rationale was rewritten from *"its quality directly determines"* to *"its
  **structure** decides"*;
- *"Live"* — one specific host — became *"the host"*, in a corpus whose subject is the host/server
  boundary.

Both read **better** as durable material than the source does. A reviewer scanning for errors sees a
well-turned sentence, and the specific observation has been quietly laundered into a general claim the
source never made. `core.md`'s transcription rule already names the mechanism (*a paraphrase reads
exactly like a faithful copy*); this adds that the drift is not random, and that its direction is
always toward what you wanted the source to say.

**The instrument is mechanical, so build it rather than resolving to read more carefully.** Extract the
quoted runs, normalise whitespace, case and trailing punctuation, split on the record's own ellipses,
search the corpus of sources, and binary-search the longest matching prefix so a divergence *point* is
located instead of an absence merely reported. **THREE controls, not two** — a nonsense string must
return zero (the search is not matching everything), a large known-good set must return hits (it is
not dead), and **a deliberately CORRUPTED real fragment must miss.** The third is what proves the
search *discriminates* rather than merely runs, and it is not optional: measured 2026-09-18 against
a mutant that matched everything, the known-good control reported a false **120/120 green** while
only the nonsense and corruption controls went red. A control that passes more easily the more
broken the instrument is measures nothing.

**The extraction pattern is itself a claim about the record's conventions, and controls on the
SEARCH do not cover it.** Six defects were found paying this debt across four captures and every one
lived in the measuring apparatus, not the records. Two were in the recipe as first written here: it
read only the `*"…"*` form, when only one capture used that convention; and as a `grep -oE` it was
**line-based**, so every quotation that wrapped was invisible — most of one capture's. Two more were
in its replacement: a naive `"([^"]+)"` is not escape-aware and truncates on embedded JSON, and
splitting on a bare `**RULE:**` marker also catches it *discussed in the record's own header*,
shifting every rule id so citations point at the wrong rules while reading as precise. Anchor the
splitter on the same command the corpus counts itself with, and assert the two agree.

Three of those live in **extraction**, and every search-side control stayed green through all
three — reverting the escape-aware regex left the self-test fully passing. So pin extraction
directly, against an inline fixture carrying one instance of each defect the conventions can
produce. **And when you write the control that closes a class, check it discriminates the CLASS and
not just the instance**: the first attempt here emptied the primary corpus loader, which also
empties the first corpus, so the weaker check it replaced passed it. The control claimed the class,
pinned the instance, and shipped that false claim into two durable records before a reviewer caught
it — which is the sixth defect, and the only one that was about the controls rather than the code.

**A refusal is a guard.** The paths that stop a vacuous pass — an unreadable input, an empty corpus,
an unknown flag value, a selection that would examine nothing — stand between a broken run and a
clean-looking result, and they go unpinned because they read as error handling rather than as logic.
Derive the roster from the source (parse the module for its own refusal sites, compare the NAMED ids
against a registry) rather than maintaining a list. And **assert each control reached its subject**:
where every refusal shares one exit code, a control whose fixture never arrives catches an unrelated
refusal and prints PASS.

State what the instrument cannot see, in the artifact rather than in your head: a quotation *stitched*
from two non-adjacent sentences with no ellipsis marked shows up as a prefix match and has to be read.
The script narrows the set a human must read; it never empties it.
