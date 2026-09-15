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

### While a Critic review is LIVE, read the reviewed files and edit only the free surfaces (`.prawduct/`, the plan, the change-log) — `critic-begin` snapshots a tree, so editing a reviewed file leaves reviewers grading code that is gone and the suite covering the pre-edit tree. Tell: `test-status` still exits 0, blind to an edit after the run it graded

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

**The tell is the part worth keeping.** `prawduct-hook test-status` exited 0 throughout. It is
session-scoped: it answers "did a suite pass in this session over these paths", not "does the
evidence describe the bytes on disk now", so it is structurally blind to an edit made after the run
it graded. The one probe that looks like it would catch this cannot. `building.md` now carries the
boundary explicitly, which is the fix the rule exists to make unnecessary.
