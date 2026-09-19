---
paths:
  - "plugin/skills/critic/**"
  - "plugin/agents/**"
---

# Learnings — reviews

Rules that fire while running or acting on a Critic review. **Reading a rule is not applying it.** Name the rule and say what it changes about the decision in front of you, or say that it does not apply.

<!-- Migrated from `.prawduct/learnings.md` in the v2 cutover merge (2026-09-15): these
     rules reached `develop` after the branch migrated its corpus, so they had no home in
     `core.md` and `core.md` had no headroom. Scoped here rather than appended there. -->

### When a control narrows what a REVIEWER sees, say which of the two roles it narrows — **subject** (a thing that can be wrong) or **oracle** (the authority the code is judged against) — because a file plays both parts and dropping the oracle looks exactly like the narrowing working. A measurement of what findings were *about* (36% cite only records) was applied to what the reviewer *reads*; every spec here is non-judgeable — the build plan, every artifact, `project-preferences.md` — and `goals-1-3.md` sends the reviewer to exactly those for Goal 2 coverage and norm departures, both BLOCKING. Tell: the chunk's success metric and its failure mode move the same direction, so no planned verification can separate them — the guard must assert the oracle was DELIVERED, never that the finding count fell

### Check WHICH interval the Critic mode takes — they differ and both fail silently. `chunk` is HEAD-tree → working tree, so committing first reviews an EMPTY interval; `cumulative` is a COMMIT RANGE, so NOT committing first reviews everything except your work. Only the Signals interval line says which. Tell: you took the mode from the plan without asking what tree it reads

### Withholding a fix to protect a review round is only correct if `cost-of-commit` PRICES it `costs-a-round` — run it on the fix's paths BEFORE deciding, because docs, artifacts and `.prawduct/` state price `free` and the round you are protecting was never owed. Tell: you are reasoning about which paths move coverage instead of asking the tool

**What happened.** After a clean `verify-resolutions` closed the cumulative gate on
`feat/upstream-filing-adapter`, three doc fixes from the round's demoted observations were left
uncommitted on the reasoning that committing them would reopen the gate and cost another ~5 min
round. The independent PR reviewer ran `prawduct-hook cost-of-commit` on those exact paths and got
`free`. The round being protected was never owed, and the same command prices the genuinely
expensive case correctly — two `.py` paths in the same batch returned `costs-a-round`.

**Why the reasoning felt sound and was not.** The rule being applied came from the *previous*
session on the same branch, which had committed four non-blocking fixes and only then run
`cost-of-commit` — the one ordering that makes the answer useless. It recorded the correct lesson
("separate-commit a non-blocking fix only when the branch needs coverage NOW") and the next session
read it as a standing reason to WITHHOLD rather than as an instruction to ASK. A rule about a tool
degraded into a heuristic that replaces the tool. **Both failures are the same failure**: deciding
what a commit costs by reasoning about the coverage algebra, in a repo that ships a command which
answers it in under a second, in both directions.

**The second-order damage is the part worth remembering.** Believing the fixes were expensive routed
three carried obligations into `.prawduct/.handoff-notes.md` — gitignored, consumed by the next
`/clear` — and the committed build plan already cited that file as a co-record of a Wave B
obligation. A durable artifact naming a path that exists on no other clone gives an obligation one
real home while reading as though it has two. So the pricing error did not just cost accuracy; it
degraded where the work was recorded.

**Why an independent reviewer caught it.** Two Critic rounds and the builder all missed it, and the
PR reviewer found it not by reading harder but by running a tool the builder had reasoned past. A
fresh context had no reason to inherit the premise — which is the specific value of review
independence, distinct from a second opinion on the same evidence.

**Generalizes:** any heuristic derived from a tool's output, carried forward as a rule, drifts into
a replacement for the tool. When a learnings rule names a command, the rule is to RUN it.

### While a Critic review is LIVE, read the reviewed files and edit only the free surfaces (`.prawduct/`, the plan, the change-log) — `critic-begin` snapshots a tree, so editing a reviewed file leaves reviewers grading code that is gone and the suite covering the pre-edit tree. Tell: `test-status` still exits 0 — it now NAMES the changed paths (#767), so the blindness is gone and the permission is not

Earned on the operator-verification drain fix (2026-09-12). `building.md` said "Don't poll;
deep-scrub your own changes while it runs, which often pre-resolves findings", and that was read as
licence to keep editing the files under review. The scrub was genuinely productive — it caught a
duplicated test class and a message that offered a remedy the code would refuse — but it also
rewrote `operator_verification.py` and its test file after `critic-begin` had snapshotted the tree
and after the suite had gone green.

The result was the review's own BLOCKING finding, and two reviewers reached it independently: one
read the lib twice minutes apart and got different blobs, the other noticed its findings were
against a state that no longer existed. `.test-evidence.json` recorded the PRE-edit tree, so the
reviewed code had no green suite behind it and the green suite described code nobody reviewed.

**The tell is the part worth keeping, and #767 changed half of it (2026-09-19).** `prawduct-hook
test-status` exited 0 throughout, and still does — that half is unchanged, and it is the half that
matters, because exit 0 is what a reader treats as permission. What is no longer true is the
blindness: the tree clause is asked on every call, so the printed line reads `current (session-fresh,
not tree-vouched)` and names the changed paths. The gate now TELLS you and still lets you through,
which is a deliberate choice — a refusal here would tax every consumer for a rare edge case (owner
ruling, 2026-09-19) — so the rule stands and its remedy is unchanged: read the label, because
nothing will stop you. `building.md` carries the boundary explicitly.

### A CLASS fixed at a SUBSET is worse than one left alone — the partial repair removes the symptom that would have made the next reader look, and can leave prose that now argues FOR the defect. Fix every member or accept the finding; never the three you can see. Tell: your fix came from the report's ROW COUNT rather than from re-running its own falsifying query

**Measured 2026-09-19 on `review-cost-decision`, and it cost two of that branch's five review
rounds (~10 min of a ~45 min total).** A mechanical `stage`→`route` rename over-applied into prose
that was *about* the stage concept. The first repair fixed three of seven sites — the three the
review had listed. The result was a heading reading *"Not `stage`, which was the first cut and was
wrong"* sitting directly above a clause blaming route-keying, on top of a route-keyed dict. The
next reviewer's words: the inverted-repair risk was **better supported after the fix than before
it**, because a maintainer chasing the contradiction re-keys back to stage and reinstates the very
defect the round before had fixed.

**Why the subset is selected, every time.** A review reports the members it happened to see, and
reading a report for *what to change* rather than for *what it says is in scope* stops at the rows.
The same branch produced the same shape twice more: a guard bound to the blank-line block instead
of the bullet, so a neighbouring `**BLOCKING**` satisfied the check for a whole list and two true
reversions survived green; and a release-note sweep where the report named two stale carriers and
its own suggested grep found three.

**The discipline is mechanical, and it is the report's own query, not its summary.** A summary
DEDUPES — one row per `(artifact, id)` — so its row count is a lower bound on the sites needing the
change, and the hidden ones are exactly those nobody re-checks. Re-run the falsifying search, fix
every hit, then re-run it and require zero. Where the sweep is a rename, the query must be about the
CONCEPT rather than the token, because the sites that survive are the ones that say the old word
correctly.

**And the accept is a real option with no shame in it.** Both partial repairs here would have been
strictly better left alone: the prose was merely stale, and stale prose does not argue for a
defect. What made them expensive was choosing FIX and then delivering a prefix of it. Relates to
[[A fix lands at the instance a review named; the defect lives in the class]] — that rule is about
the class being wider than the instance; this one is about what happens when you *know* the class
and ship part of it anyway.

### Before recommending that something be BUILT, check whether it was already built and REMOVED — a removal comment is a decision with measurement behind it, and re-proposing it spends that measurement twice. Absence invites a proposal; a decision demands new evidence to reopen it. Tell: you are proposing a control and have not opened the module that would host it

**The case.** An audit of 141 PR-review records led with "lint pinned figures and citations at the
source." Both halves were already answered in the tree. `record_lint`'s `suite-total-claim` had
covered pinned suite totals since it shipped. The citation half — `dangling-ref` — had been built,
**measured at 3 findings and 0 true positives**, deleted under `nonfunctional-requirements.md`
§ Direction (*a control that fires and catches nothing is removed by default*), and annotated with
the exact bar for re-adding it: evidence that the class costs review rounds. The audit did not clear
that bar; of its two citation-drift findings, one sat in a file every check excludes by design and
the other was a wrong symbol name that path resolution would not catch.

**The evidence was in hand before the recommendation was made.** One reviewed finding cited
`record_lint.py` by name. It was read as an *example of citation drift* rather than as proof that a
record-lint subsystem existed — the file was named in the input and never opened.

**The cheap check** is opening the module that would host the thing you are about to recommend. The
removal comment exists *specifically* to stop a helpful future reader restoring the check.

**Re-homed 2026-09-19** from the pre-migration `learnings.md`/`learnings-detail.md` pair, where it
stranded on an unmerged branch for nine days. Filed in `reviews.md` because its trigger is
recommending a control while auditing — but it generalizes to planning, and the 2026-09-19
convergence pass is the confirming instance in the other direction: `documentation/issues/167-design.md`
was a complete design three separate searches had missed, and the mechanical seeder
(`prawduct-hook jurisdiction`) is what surfaced it, not a more careful read.
