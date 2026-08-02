# Learnings

Accumulated wisdom from this project's development. Read this at session start — it directly informs how you work. Entries are ordered by relevance; most important patterns first.

No size constraint on this file — it's the deep reference, consulted via `/learnings` or directly when debugging in a known area. Prune entries that have been incorporated into principles, methodology, or structural enforcement.

---

## A sample you sliced for DISPLAY is not the set — if the command that formed your impression carried a `[:8]` or a `head`, re-run it unsliced before writing "all/every/entirely", because the slice is invisible in the output you read back. A RETRACTION is where this bites hardest

A Critic warning retracted a claim I had measured in an unrepresentative scratch repo. Fixing it, I
wrote the *replacement* at three sites: "26 unjudged entries, all under `.prawduct/`". The verify
round read the record I had cited — 16 under `.prawduct/`, 10 unprotected prose, held out by a
different branch of the predicate. The conclusion survived; the characterisation misled the exact
reader the passage addressed, someone weighing whether to relax the metadata carve-out and now told
it was the whole story rather than 62% of it.

The false "all" was not carelessness in the sentence. It came from a diagnostic I had run earlier
whose output I sliced — `print(... [:8])` — to keep the terminal readable. Eight `.prawduct/` paths
were visible and eighteen more were not, some of them different in kind. Nothing in the output says
"18 omitted"; the slice erases itself, so the impression it leaves is indistinguishable from having
seen the whole set.

Why this is not covered by the existing rule (`learnings.md`: *anything one command could check is a
CLAIM… a CORRECTION is itself a completeness claim*): that rule was quoted **in the same commit**
that carried the false replacement, and did not prevent it. It already records that quoting the
parent rule demonstrably does not prevent recurrence. So the useful addition is not another
exhortation to be careful but a mechanical trigger with a visible tell — the `[:8]` or `head` in
your own scrollback — and the observation that a retraction is the highest-risk moment, because the
author replacing a false claim feels most careful and is therefore least likely to re-open the
artifact being cited.

## An exception APPENDED to standing advice still leads with the advice — so before appending, ask whether the exception can cover the WHOLE set, and if it can, it must be able to REPLACE the lead sentence rather than follow it

`#536` was filed because a superseded blocker could only be cleared by a spanning review, while the
gate message prescribed `verify-resolutions`. The fix added a clause naming the spanning route — and
appended it *after* the existing "Fix them, then run `/prawduct:critic verify-resolutions`" sentence.
For the partial case that is right: some blockers are reachable by the standard route, so it should
lead and the exception should qualify it. For the total case it reproduced the filed defect exactly.
The operator whose every blocker is superseded was still told, first, to take the one route that
cannot work; the correction arrived four lines later, after they had read an instruction.

I noticed the awkwardness reading the live output and talked myself out of it — the word "instead"
seemed to carry the weight. A reviewer flagged it independently with a sharper argument: people act
on the first instruction, and the cost is a real verify round (~1-2 min plus a fix commit) that
clears nothing. That is the tell for this whole class — **when you find yourself justifying why a
reader will get to the correction, the correction is in the wrong position.**

The structural fix matters more than the wording: `blocking_remedy_lines` now owns the entire remedy
and returns one of three blocks, deciding which route *leads*. Both call sites render whatever it
returns and compose nothing themselves, so neither can reintroduce a lead sentence of its own. The
earlier shape — shared exception, locally-owned lead — looked like deduplication while leaving the
load-bearing decision duplicated at two sites.

Generalizes past messages: any place a conditional qualifier is bolted onto an unconditional
statement. The test is whether the qualifier's predicate is a *count over the same set* the statement
addresses. If it is, the all-case exists and must be handled by replacement.

## When you TRANSCRIBE a rule between two records, its identifiers are the part that silently degrades — re-verify every field, symbol and path against the code, because a paraphrase reads exactly like a faithful copy

Three independent reviewers converged on one defect: a retire rule corrected twice in the build plan
had never reached the change-log, so the durable record — the one that outlives the plan — still
stated the rejected version. The fix transcribed the corrected rule across. In doing so it wrote
"findings whose **`summary`** opens with the token" where the plan said `title`.

`summary` is not a random error. It is the adjacent, plausible word: findings *do* have summaries in
the PR reviewer's record, and the per-worktree derived cache *does* carry a per-finding `summary`.
But the shared evidence store — the only store a 30-review sweep can query — carries `title`, written
by `critic_consolidate` from the partial's `name`. A sweep run against the named field would return
zero for every review and retire a control that had been firing: the precise failure the correction
existed to prevent, reproduced one level down by the commit that prevented it.

Two things make this its own rule rather than another instance of the two-copies pattern:

1. **The direction flipped.** The four prior instances on this branch all had the primary site fixed
   and the secondary stale. This one had the *plan* correct and the *durable copy* wrong — because
   the defect entered during transcription, not during the original edit. Sweeping "did the fix reach
   the second site?" would have reported clean; the second site existed and said something false.
2. **Prose review does not catch it.** Both sentences are grammatical, both name a real field, and
   the wrong one is more familiar. Only checking the identifier against the code separates them.

The durable mitigation is to carry the *reason* with the token, not the token alone: the change-log
now says "`title`, because a partial's `name` becomes the fact's `title`, while per-finding `summary`
lives only in the per-worktree derived cache." A future transcriber paraphrasing that sentence has to
paraphrase a mechanism, which is much harder to do wrongly than a bare field name.

## A fix ships TWO artifacts that can independently be false — the change, and the evidence that it works. This branch put every defect in the second: a test that could not see the bug it pinned, then a comment asserting the rule its own assertion disproves. When you fix something, sweep the NEIGHBOURING PROSE in the same pass, or a reviewer finds it one comment at a time

Measured across one chunk. Five review passes; the last three each returned a finding, and none was
in an instruction:

- The fix was correct; the **test** pinning it passed against the defect.
- The test was fixed; a **comment fifteen lines above it** still asserted the rule the new assertion
  disproves — and it was the authority a maintainer would cite to weaken that assertion.
- Two more comments: a docstring prescribing a rule unconditionally after it became conditional, and
  a note whose two constraints had their *scopes* backwards.

The sibling of [[justify at the altitude of the decision]] one layer out. That rule is about reasons
being wrong. This one is about **evidence** being wrong — and evidence is more dangerous, because a
green test and a plausible comment both produce the felt experience of verification while providing
none. You do not re-read them, because their whole job is to be the thing you trust.

**Why prose specifically.** A comment beside a fix is written in the same minute as the fix, from
inside the frame the fix just created, and it describes the code as the author now intends it rather
than as it now is. When the fix *narrows* a rule — from "always X" to "X only on path A" — every
sentence nearby that still says "always X" becomes false silently, and no test covers a comment.

**The cheap countermeasure, and the reason it is worth doing:** when a fix changes a rule, grep the
symbol's name across the module and read every prose hit in the same pass. It costs one search. Not
doing it costs a review round *per comment*, because each fix commit moves HEAD past the verified
tree and buys another coverage pass — so a two-line comment edit is a full round.

## A mutation test is only evidence if the MUTANT IS THE DEFECT — hand-reverting to "something wrong" tests nothing. Restore the code that actually shipped the bug, gate conditions included: drop a guard the real defect sat behind and the test exercises a path the bug never reached, passing against the very code it was written to catch

Found by a `verify-resolutions` pass on work where I had *already* mutation-tested the fix and
recorded it as verified.

The defect: a completion set was computed by slicing a roster with a COUNT of done items, which is
not positional, so a non-contiguous roster named the wrong chunks. The real code guarded that slice
behind `if progress.git_derived:` and used an exact predicate otherwise. My fix removed the branch.
To mutation-test it I pasted the count-slice back — **unguarded**, applying to both paths.

That mutant is not the bug. It is a *different* bug, and it happens to be one my test could see. The
faithful revert restores the guard too, and against it both of my new tests passed: one ran on the
checkbox path, where the original code was correct, and the other's done-set was contiguous, where
the count and the prefix agree. Two tests written specifically to pin this fix, both green against
the defect.

**Why hand-reverting goes wrong in this exact direction.** You revert from memory of *the fix*, not
of *the original*, so what you reconstruct is "the fix, inverted" — and the fix is usually a
simplification, so the inversion drops the very conditions that made the original subtle. The guard
you forget is the one that made the bug hard to find in the first place.

Countermeasures, cheapest first: revert with `git show <commit>^:<path>` or `git stash` rather than
by retyping; then assert the mutant actually *fails* the test — a mutation run where nothing goes
red is a failed experiment, not a passed one. And when the fixture is the thing in doubt, make it
assert its own preconditions (`assert progress.git_derived`, `assert progress.complete == 2`) so a
silent fixture regression is loud rather than green.

Same family as [[the fix for a review finding needs the same adversarial pass as the original work]]
— the verification reflex relaxes exactly where the previous round proved it should not — and the
concrete instance of the test-evidence prompt's standing warning that a fixture which never reaches
the subject passes forever.

## RULING (regen-views-is-advice) — when two norms reach one command, its OUTPUT decides the posture: a writer whose only product is a DERIVED VIEW fails soft one view at a time, because no gate reads a view to reach a verdict. Soft is not blanket — input it cannot interpret at all still fails closed. Skip-and-report a bad view, never write it half-right

**Collision ruling, owner decision 2026-08-01**, raised by #201's fourth leg. Two `## Direction`
norms both reached `regen-views` and pointed opposite ways: `architecture.md`'s *authority fails
closed; advice fails soft*, and `data-model.md`'s *derived views are disposable and never
authoritative — no gate reads a view to reach a verdict*.

**Why the output decides.** The authority norm's why is that a verdict must not be satisfiable by
feeding it garbage. That rationale reaches a command only where a verdict exists to corrupt.
`regen-views` emits no verdict and no gate consumes its output *to reach one*, so the authority
half never attaches, and the derived-views norm decides the posture. Rule at the category level:
**the failure posture of a command follows what it produces, not how important the command feels.**

Two edges, because the unqualified form is false in both directions. *"No gate reads a view"* is too
strong — a gate trigger does read the build-plan checkbox view (`cross-cutting-concerns.md` records
this deliberately); what no gate does is read one **to reach a verdict**, which is the norm's own
wording and the load-bearing clause. And *fails soft* is not blanket: input the command cannot
interpret at all still fails closed, because a view written from it would be half-right rather than
absent, and silent half-rightness is the bug class the whole rule protects.

**What the ruling had to preserve.** VWS-6R4T made the command fail closed for a stated reason —
*"no silent partial flips — partial application is the bug class"* (the ASSUMPTION block in
`artifacts/build-plan-changelog-fail-loud.md`). That content survives; only its whole-run coupling
is dropped. The unit of atomicity moves from the **run** to the **view**: a view whose inputs are
invalid is skipped and reported, never written half-right, and views with no dependency on the bad
input are still written. `views.apply_regen` already writes each view as one whole file, so per-view
skipping cannot produce the state VWS-6R4T names. This is the distinction that let the leg be
granted without reopening the bug class: **"fail soft" means "don't block the others," never "write
one you know is wrong."**

**The dry run was the drift.** `--check` and the real run validated identically — `cmd_regen_views`
consulted the flag only *after* its validation block had already returned — so the two-step
`--check` → `regen-views` that every release plan prescribed was validate-and-stop followed by
validate-and-stop-or-write. The first step could not catch anything the second didn't. Worse,
`--check` exited 0 while writes were *pending*, so a clean check meant "the tags parse," not "the
views are correct," and it was read as the latter: one reporting repo had lost whole version
sections from `release-notes.md` and was running `scope_rollups` at roughly half its true key count
while the check reported up to date. **A dry run that validates identically to the real run is not a
safety device — it is a way for a check to report clean while the artifact it checks rots.** Hence
one mode: views always regenerate.

Recorded shapes, not values, on purpose. Earlier drafts of this entry carried exact line citations
(`prawduct-hook:3028-3043`, `views.py:1339-1345`) and exact counts; **both citations were already
wrong at the commit that shipped this entry** — the code moved in the same change, and one of the
lines cited no longer existed. A durable rule that names a line number is a rule with an expiry date
nobody sets. Name the function; let the reader grep.

**The generalizable tell.** The question arrived as "is this command authority or advice?" and
looked like an unresolvable norm conflict for as long as it was asked at the *command* level. It
dissolved on asking what the command *produces*. When two norms appear to collide, check whether
they are being applied at the same granularity before arbitrating between their whys — a collision
at the wrong altitude is usually a category error wearing a conflict's clothes.

## The fix for a review finding needs the same adversarial pass as the original work — dispatch a delta review of the fix commit, because "I am correcting a known defect" feels like lower-risk work than writing new code and the verification reflex relaxes exactly where the last round proved it shouldn't

The release-readiness bundle produced a clean measurement of this. One Critic cumulative (1 blocking / 12 warnings / 10 notes) → three verify passes, **each of which found a defect introduced by the previous round's fix** → clean. An independent PR reviewer then read the resulting tree and found W-1, a defect the bundle had itself created and *twice declared closed*. The fix for W-1 was then delta-reviewed and contained **2 BLOCKING plus 3 warnings**. Four rounds, four times the correction carried a new defect.

The critical procedural fact: warnings do not block PR creation, and the PR skill's flow permits going straight to `gh pr create` once blocking findings are clear. Had that path been taken, both BLOCKING defects would have shipped into a runbook a human executes at the next release — including an entry-condition check whose "stop" branch was unreachable and whose "proceed" branch exits non-zero while its "stop" branch exits zero.

**Why the reflex relaxes.** Writing a correction produces the felt experience of having verified something. The frame is already established by the finding, the edit is small and local, and the author is reasoning from "I now know what was wrong" — which is knowledge about the *past* state, not about the edit just made. So the same scrutiny that would attend new code is not applied, precisely in the round where the previous round demonstrated it was needed.

**Mechanics.** After committing fixes, spawn one review scoped to *exactly that commit* — `git show <sha>` — and tell it two things: the measured base rate, and to assume more defects remain regardless of how confident the diff's prose sounds. Don't give it a general brief; give it the fix's own claims to re-execute:

- run every command the fix publishes, verbatim, and compare real output (and **stream and exit code**) to what the surrounding prose promises;
- check every cited tree, commit, line number and count *at the tree named* — not at HEAD, and not at the tree the author had in mind;
- open every cross-reference, including ids the fix forward-references into other files;
- ask whether any premise was inherited from the finding rather than measured in the tree.

This is minutes, not another full cumulative. `/prawduct:critic verify-resolutions` is the Critic-side equivalent and extends coverage over the delta at delta cost.

**The three traps that recurred**, worth naming because each looks like diligence:

1. **A detection command blind to its own defect.** The replacement census grepped the *vocabulary* (`content-identical`, `tree-set`) while the residual asserted the same thing by *invoking the mechanism* (`git diff --stat origin/main origin/develop`) — so the command written to prove the class was closed could not see the one hit that prompted it. Same shape as a test that cannot fail. Grep the mechanism, not the phrasing.
2. **A claim measured at the pre-fix tree.** "Run at tree `eac2638` it returns 13 hits, all qualified" — `eac2638` was the *parent*, where two of the hits *are* the residual. The count happened to be 13 at both trees, so the number looked right. Self-refuting under the paragraph's own instruction to re-derive. Replacing a figure with a derivation does not discharge the duty to run it at the tree you cite.
3. **An inherited premise hardened into certainty.** "v3.2.0 is planned non-pruned" came from a reviewer's parenthetical and an owner decision recorded only in *untracked* handoff notes; it was escalated to "structurally unreachable, not merely unlikely." No `release-plan-v3.2.0*.md` existed and no tracked artifact stated the promotion shape. The underlying defect survived without the overclaim — a *version* is the wrong kind of trigger for a *promotion shape* — which is the tell: when a finding is real, the overclaim is load-bearing for nothing and should be dropped.

Discovered 2026-07-29, release-readiness (PR #143; Critic cumulative `rev-20260729T185143Z` → verify passes `rev-…192252Z`/`rev-…194336Z`/`rev-…195906Z` → independent PR review → delta review of `c68443d`). Relates to Validate Before Propagating (#15), Root Cause Discipline (#16), Honest Confidence (#5).

Measured base rate on one bundle: **four consecutive review rounds, each of which found a defect introduced by the previous round's fix** — three Critic verify passes plus a delta review that turned up 2 BLOCKING in a fix commit an independent PR reviewer had already cleared the tree for. Warnings don't block PR creation, so going straight to `gh pr create` after a fix commit is permitted and would have shipped both. Mechanics: after committing fixes for findings, spawn one focused review scoped to *exactly that commit* (`git show <sha>`), told the base rate and told to assume more remain — it is minutes, not another full cumulative, and `verify-resolutions` is the Critic-side equivalent. Give it the fix's own claims to re-run rather than a general brief: every published command executed, every cited tree/line/count checked at the tree named, every cross-reference opened. The specific traps that recur: a *detection* command that cannot match the defect it was written to find (grepping the vocabulary when the residual asserts the same thing by invoking the mechanism), a claim measured at the **pre-fix** tree, and an inherited premise hardened into a certainty the tree cannot support. Discovered 2026-07-29, release-readiness (PR #143; Critic `rev-…185143Z` → three verify passes → delta review of `c68443d`). Relates to Validate Before Propagating (#15), Root Cause Discipline (#16), Honest Confidence (#5), [[When you "correct" an inherited number, recount the SET and not just the count]], [[Verify a disposition against the diff before recording it]].
## Justify at the ALTITUDE OF THE DECISION, never the mechanism — a mechanism claim carries the same verification duty as the instruction it supports but escapes the check by reading as commentary. Test: must the reader reason PAST this instruction? No → mechanism is liability; yes (a norm, a recorded decision) → verify it like code. Same species as over-precise counts. Altitude, never omission

A long run of `verify-resolutions` rounds on a single **doc-only** chunk (v3.2.3, `backlog-burndown` Chunk 01, the migration-scrub runbook). The defects clustered hard in the justifications — a representative set, not a census:

1. **The remedy I clarified.** Disambiguating two senses of "duplicate" required saying which act was correct — which put my weight behind a `duplicate_alias` fold that cannot clear the list it is prescribed for (the alias scan never consults `superseded_by`; `merge` leaves the loser's `id_aliases`).
2. **The command I named.** The replacement said `backlog update --body`, which a *passing test* proves cannot perform the edit — `_body_update_preserving_block` strips the caller's block and re-appends the old one.
3. **The bypass I authorized.** `gh issue edit --body` is a whole-body replacement handed over with no read-modify-write step, so it would drop the `superseded_by` the fold had just written — silently, since the gate never reads that field.
4. **The instruction's own nouns.** `# delete ONLY the one id_aliases entry; leave every other line alone` — but `id_aliases` is one line holding a list, so "entry" and "line" name the same thing, and the ambiguity resolved toward deleting the line and silently dropping any other ids on it.
5. **The reason I supplied.** "A loser that was itself an earlier survivor carries several ids, and `merge` never moves them" — self-contradictory in one sentence, and false: *because* merge never moves aliases, an earlier survivor is precisely the item that accumulated none.

**The instruction was usually right; the sentence explaining why was what kept failing.** Item 4 is the instructive exception and worth keeping in view — the same disease in the imperative mood, two nouns for one object, resolving toward data loss.

*(This paragraph has been rewritten twice by reviews of this very entry. First it read "the instruction was right every time" — a universal contradicted by item 4. Then the opening stated a round count that went stale between rounds. Both are the species the entry indicts, committed inside it. The fix that finally held was not a more accurate number or a hedged absolute but **removing the countable claim** — "a long run", "usually", "a representative set, not a census" — because a value can go stale and a form cannot. When a claim draws the same finding twice, change its shape, not its contents.)*

**Why justification escapes the check.** Explanation is generative: it reaches for a mechanism that makes the instruction feel inevitable, which is the generate-instead-of-retrieve move Principle 24 exists to catch. But it doesn't *present* as a claim — it presents as commentary on a claim already made, so it never enters the set of things to verify. Note that #3 is the sharpest form: I cited the exact fields the preservation guard protects *as my justification for bypassing the guard*, and then didn't carry the guard's job across. The sentence functioned as permission rather than as a specification of what I now owed.

**The countermeasure is fewer claims, not better ones.** "Verify harder" cannot help with a claim that never entered the check set. The closing fix carried three clauses, each pinned to a named call site, and dropped the explanatory framing entirely. When the reviewer then surfaced a residual (`_block_for` iterates source metadata after writing `id_aliases`, so a hand-authored source bar could carry a longer list), the right move was to leave the text alone — the existing sentence already said "a longer list means someone hand-edited it," and adding a covering clause would have been the same reflex again.

**Stopping rule this produced.** Convergence shows as severity falling — blocking → warning → note — not as findings reaching zero. A dense document always yields another note. Notes-only means close.

### The generalization (owner, 2026-08-01): this is the exact-numbers problem again

The owner named the sibling: review feedback that reads *"it's 22 call sites, not 21"* — true, and useless. Moving those claims to *"more than 10"* largely ended that churn. **Same defect, different surface: a claim finer than any decision requires is pure liability. It can be wrong, and being right buys nothing.** The repo already institutionalized the numbers half (D14 "never persist derived counts"; `record_lint._SUITE_TOTAL_RE`, which lints humans for writing suite totals; the no-suite-total-claim preference row). This rule is the prose half.

**Why "don't justify unless someone will decide on it" is the wrong form of the fix.** It collides with three standing things: Principle 4 (*Reasoned Decisions*), the norms lifecycle (a norm's **why** is what decides whether a proposed exception is legitimate — `docs/norms.md`), and this file's own premise that a rule without its reason is inert. It also has a bad failure mode: read as "justify less," it is gameable into "drop traceability," and the agent that suppresses its why draws fewer findings while becoming less reviewable. The problem was never that I explained; it was the *altitude* I explained at.

**The operative test.** Will the reader have to reason **past** this instruction — handle a case it doesn't enumerate, or depart from it?

- **No** → mechanism is liability. Justify at decision altitude: *"delete a list element, not the line — taking the line can remove more than you meant."* Sound, actionable, needs no call-site check.
- **Yes** → mechanism is load-bearing and gets verified like code. This is why a norm, a `## Direction` entry, or a recorded design decision **must** carry mechanism: someone will later argue an exception, and the why is the only thing that adjudicates it.

A runbook step is almost always the first case. A norm is always the second. The four defects above were all first-case instructions carrying second-case prose.

Sharpens [[The fix for a review finding needs the same adversarial pass as the original work]], which says to re-review fixes; this says where in the fix to look. Relates to Retrieval Over Generation (#24), Honest Confidence (#5), Reasoned Decisions (#4 — the constraint this rule must not violate).

## A governance change cannot supply its own authority — when an agent amends a binding norm mid-build, land the owner's confirmation somewhere the amendment isn't, because a change that is its own only witness is indistinguishable from laundering however sound the substance

`operational-spec.md` § Direction's gitflow promotion norm bound `develop`→`main` to a *content-identical tree-set*. That mechanism blocked Chunk 02, and it was genuinely wrong: the norm's stated purpose is that a release must not **ship integration WIP**, and content-identity *forces* precisely that whenever `develop` holds unready work. prawduct had already departed from it twice (v3.1.1, v3.1.2) with nothing recorded, so the binding text described a practice that had ceased. The amendment narrowed the mechanism to a *fully classified partition* — every unreleased scope shipped or withheld behind a named blocker — landing **stricter** about what the norm actually protects.

Every element of that justification was true and well-argued. The Critic still cleared it only as *"legitimate rather than laundering"* while flagging (R-7) that the ruling's provenance existed **only inside the diff that made it** — the edit recorded itself as "Amended 2026-07-29 by owner ruling," and that claim was its own sole evidence.

That is the whole defect, and it is structural rather than a matter of degree. An inspector reading the change sees the norm's new text and, as its only support, the same commit asserting that authority was granted. **A laundered amendment produces a byte-identical artifact.** Soundness is not observable from inside the change, so a reviewer cannot distinguish the two cases and correctly declines to — the finding is not "this is suspicious," it is "this is unfalsifiable from here."

The trap is that arguing the amendment well *feels* like discharging the burden, and the quality of the argument is inversely related to noticing what's missing: the reasoning is right there in the diff, so the record seems complete. It isn't. The argument establishes that the amendment *should* be granted; it cannot establish that it *was*.

**Mechanics.** Raise it as a blocking precondition rather than editing quietly (here: Critic R-25). Carry it to the next human checkpoint — PR time — as an explicit owner question, with the consequences of a veto spelled out concretely (which chunks lose their premise, which files revert), because a question that hides its cost isn't a real choice. Record the answer in the norm's own `Status:` line, as a vetoable `[DECISION: … | user can veto or narrow]`, where a future reader meets the norm — the change-log is a log, not a place anyone consults before applying a rule. Until confirmed, the honest count is "N accepted notes and **one open question**," not N+1 accepted; here the census had to be corrected from 10-accepted to 9-accepted-plus-1-discharged.

**Residual worth knowing.** The closure's own rule is "land the attestation somewhere the amendment isn't," and the confirmation landed in the same sentence of the same line it certifies. The only witness genuinely outside the change is the PR thread — so the PR body must quote the amended norm and its `[DECISION]` verbatim for owner sign-off. Recording it in the artifact is necessary and not sufficient.

Discovered 2026-07-29, release-readiness (Critic cumulative `rev-20260729T185143Z` R-7; discharged at PR time in `1a8bcc5`). Relates to Reasoned Decisions (#4), Honest Confidence (#5), Challenge Gently/Defer Gracefully (#23), and the norm lifecycle (`/prawduct:methodology norms` — amendment vs. ruling vs. exception).

When a norm blocks the work and the norm looks wrong, raise it as a **blocking precondition** (never edit quietly), then carry it to the next *human* checkpoint — PR time — as an explicit owner question with the consequences of a veto spelled out, and record the answer in the **norm's own `Status:` line** where a future reader meets the norm, not only in the change-log. Until confirmed it is a proposal: count it as "N accepted notes and one open question," not N+1 accepted. The trap is that arguing the amendment *well* feels like discharging the burden — the better the argument, the less the missing attestation is noticed — but the argument only establishes that authority *should* be granted, never that it *was*, and a laundered amendment produces a byte-identical artifact. Discovered 2026-07-29, release-readiness (Critic `rev-20260729T185143Z` R-7, discharged at PR time in `1a8bcc5`). Relates to Reasoned Decisions (#4), Honest Confidence (#5), Challenge Gently/Defer Gracefully (#23), norm lifecycle (`/prawduct:methodology norms`). Companion to [[Verify a disposition against the diff before recording it]] — that rule covers claims a diff can settle; this one covers the claim a diff structurally cannot.
## When a release ships a PRUNED tree, a clean `git apply` is NOT evidence of a sound tree — the shipping code can depend on a symbol the WITHHELD work introduced, which a textual patch tool cannot see: v3.1.2's ship set called `sys.stderr` while `import sys` had arrived in `briefing.py` with the withheld backlog-service work, so `git apply` reported the file applied cleanly and produced a `NameError` in a shipped path (11 test failures). Run the suite against the candidate tree, and diff every shipped file's imports against its `develop` counterpart

v3.1.2 was a pruned promotion: `main`'s tree was built as `v3.1.1` + the diff `e597b21..develop`, withholding the backlog-service subsystem. `git apply --3way` reported three conflicts and applied everything else "cleanly" — including `plugin/lib/briefing.py` and `plugin/bin/prawduct-hook`.

The resulting program was broken. `prawduct-hook handoff preview` raised `NameError: name 'sys' is not defined`, taking 11 tests with it. The ship set added code calling `sys.stderr`, but `import sys` had been added to `briefing.py` by the **withheld** work, in a hunk the ship patch therefore did not carry. Neither side of the patch is wrong; the dependency simply crosses the cut, and a textual tool has no way to notice.

The general shape: **a patch tool verifies textual applicability, not semantic completeness.** Any tree assembled by patching rather than by checking out a reviewed commit needs execution-level validation, because the failure mode is a silent reference to something that no longer exists.

Two checks caught and bounded it here, and both are cheap enough to be standard for pruned releases:

1. **Run the suite against the candidate tree.** It found the defect immediately. This is also the argument for a pruned release being validated as a *tree*, not as a patch review.
2. **Diff imports per shipped file.** For each Python file the ship set touched, compare module-level imports in the candidate against the same file on `develop`; anything present there and absent here is a candidate for this class. Run across all 23 shipped Python files, it confirmed exactly one instance — which converts "we fixed the bug we found" into "we bounded the class."

The residue is worth recording where the code lives: `main` now carries one line of shipped code that exists in no reviewed commit. It self-resolves at the next release that ships the withheld work, because `main` then takes `develop`'s tree wholesale. Recorded in `artifacts/release-plan-v3.1.2-pruned.md` so the divergence is not later read as an accident.

## When determining what a PREVIOUS release actually shipped, test its CODE against that release's tree — never the change-log's prose or heading presence, which a pruned release leaves behind: v3.1.1's tree carries all ten backlog-service change-log entries whose code it deliberately withheld, so a heading-presence test called them shipped and would have mis-tagged them, silently dropping ten entries from v3.1.2's release notes. This is the runbook's own REL-7D4X rule and it is load-bearing in both directions

The release runbook's step 2 states the rule: an entry is release-pending iff it carries no `release=` tag **and** its code is absent from the previous release's tree. I reached for a cheaper proxy instead — is the entry's heading present in `git show v3.1.1:.prawduct/change-log.md`? — reasoning that the change-log gate guarantees an entry lands with its code, so prose presence implies code presence.

That inference fails across a pruned release. v3.1.1 was itself cut from `v3.1.0`'s tree, and the prune removed the backlog-service **code** while leaving its **change-log entries** in the tree. So all ten entries read as "shipped in v3.1.1" while their code had never reached a consumer. Acting on it would have left ten genuinely-unreleased entries untagged — no release-notes entry, no checkbox flip, and nothing downstream complains.

The code test inverted the answer completely: `v3.1.1` has `plugin/lib/backlog.py` (single module) where `develop` has the `plugin/lib/backlog/` package, and v3.1.1's `backlog_probes.py` has **zero** occurrences of `backlog-service-migration-required`. All ten were release-pending.

Two general points:

- **The runbook already knew.** Its REL-7D4X warning says the boundary "narrows the search, it does NOT define the set" and that a positional sweep drops entries silently. I read that warning, correctly rejected the positional shortcut it names — and then invented a *different* shortcut with the same defect. The lesson is about the class, not the instance: when a document warns that a cheap proxy for X is unsound, the warning is about proxies for X, not about the one proxy it names.
- **It is load-bearing in both directions.** A pruned release makes prose and code diverge permanently, so prose-based reasoning can both over-claim (an entry looks shipped when it is not) and under-claim. Only the code test is stable across it.

## When work is authored ON TOP OF work you may later need to withhold, the two become inseparable by file — pruning is by commit range, so everything merged in between ships or waits together: v3.1.2's ship and withhold sets overlapped in 11 files including `prawduct-hook` and `briefing.py`, so "ship only the session work" also withheld an unrelated refactor and five skills' prose. Sequence a release-gated subsystem BEHIND independently-shippable work, not before it

The backlog-service subsystem was release-gated on four open safety blockers (BKL-6J2X, BKL-5N9W, BKL-8V3D, BKL-2Q7F) — a chain that routes the whole installed fleet into a migration path able to write 100–250 real issues into a real repo while an agent believes a dry-run guarded it. It merged to `develop` in PRs #137–#139. The session-continuity work then merged **on top of it** in PR #140.

That ordering is what made v3.1.2 expensive. v3.1.1 had pruned *parallel* work — it cut from `v3.1.0`'s tree and applied a small hotfix. Here the work we wanted to ship was authored against the post-relayout codebase, so:

- the two sets overlapped in **11 files**, including `plugin/bin/prawduct-hook` and `plugin/lib/briefing.py`, making a file-level split impossible;
- the split had to be by commit range (`e597b21..HEAD`), which is coarser than by feature — so an unrelated refactor (PDT-WT9K) and prose in five skills were withheld as collateral;
- the ship set had a latent dependency on the withheld set (the `import sys` above), which only execution revealed.

**The scheduling rule:** when a subsystem is gated on blockers that are not yet closed, land it *after* the work that must ship independently, or keep it on its own long-lived branch. Merging a release-gated subsystem into the integration branch early converts every subsequent release into tree surgery. The cost is invisible at merge time and paid later, by someone reconstructing which commits belong to which feature.

## When deferring something to a live/operator check, SPLIT it into "can this be true in principle" (static — test it now) and "does the harness actually do it" (live — queue it) — bundling them defers the testable half indefinitely, and that half is where the bug usually is: CRT-2J8N deferred all of "does the SubagentStop matcher fire" as un-unit-testable because *anchoring semantics vary by version*, true of delivery but false of matchability, and the bare-name matcher could never have matched the plugin-scoped `agent_type` on any version

`operator-verification.md` VRF-002 (2026-07-10) listed three integration facts as "unverifiable by code analysis." Fact 2 was whether the `SubagentStop` matcher fires for the dispatched reviewer, justified with "matcher-anchoring semantics vary by Claude Code version."

That justification is true about **delivery** — whether the harness emits the event for this agent, on this version, is genuinely only observable live. It is false about **matchability** — whether a given matcher string *can* equal a given `agent_type` is a pure function of the matcher rule and the two strings, decidable at rest. Bundling the two put the decidable half into a queue for seventeen days, and the decidable half was the broken one: the matcher was `critic-reviewer`, the runtime value `prawduct:critic-reviewer`, and for SubagentStop an all-alphanumeric matcher is compared as a literal.

The split is the general move. Any "we'll have to check that live" should be interrogated for a static residue, because the live queue is slow, human-gated, and — as GOV-2W7Q records — sometimes not enforced at all. Whatever can be pinned now, pin now; send only true harness-behaviour questions to the queue.

Concretely here: `_matcher_matches` in `tests/test_critic_reviewer_agent.py` encodes the documented rule and evaluates the real `hooks.json` matcher against the real scoped agent type. That is the static half, and it fails loudly on the bare-name form. VRF-002 keeps only the delivery half.

## When defense-in-depth is offered as the reason a risk needn't be verified, check the defense is REACHABLE from the failure it is meant to absorb — a guard downstream of the thing that fails never runs, so it buys nothing: `cmd_subagent_stop`'s `agent_type.endswith(...)` check was cited as making matcher uncertainty tolerable, but it sits behind the matcher, and a matcher that never fires never reaches it

VRF-002's fact 2 reads: the matcher's behaviour is uncertain "— the command defends with an `agent_type` endswith-check and is no-op-safe regardless." Both halves of that defense are real. `cmd_subagent_stop` genuinely accepts bare and scoped forms, and `critic-consolidate` genuinely no-ops until the roster is complete. The reasoning is still invalid, because both live **inside the handler**, and the handler only runs if the matcher matched. The uncertainty was about whether the handler would ever be invoked; the mitigation assumed it had been.

The detectable shape is a sentence of the form *"X is uncertain, but that's fine because Y handles it"* where Y executes only on the success path of X. It is self-defeating and findable by reading, which is what makes it review-shaped rather than test-shaped — filed as CRT-6B9M for a Critic protocol clause.

Ask, for any claimed mitigation: **on the failure path I am worried about, does this code execute at all?** Here the answer was no, and no amount of correctness inside the guard could change it.

## A deferral queue whose enforcing gate is disabled is a WRITE-ONLY queue — check the gate is ON at the moment you defer work into it, because the deferral itself feels like diligence: `operator-verification.md` named the CRT-2J8N matcher as the thing to investigate 17 days before it was found, and sat `pending` the whole time behind `operator_verification_required: false`, with 6 of 8 entries in the same state

The process worked right up to the point where it had to be enforced. The Chunk 03 Critic flagged three unverifiable integration facts; a VRF entry was filed; its verification steps were correct and specific, ending with "investigate the matcher string (`prawduct:critic-reviewer` vs `critic-reviewer`) against the installed version." Every step of that is good practice. The entry then sat `pending` for seventeen days because `project-state.yaml` sets `operator_verification_required: false`, so `check-operator-verification` short-circuits to exit 0 and `/prawduct:pr create` Step 2b never blocks.

Filing into an unenforced queue is indistinguishable, from the inside, from handling the risk — that is what makes it dangerous. The act of writing the entry discharges the felt obligation.

There is a second-order lesson recorded in GOV-2W7Q. The gate's default was justified by "Prawduct has no human-facing UI surface to verify pre-merge; product repos that ship visual changes opt in." That rationale is sound for *visual* verification and irrelevant to what the queue actually accumulated: every pending entry is a **live-harness integration** check. The category drifted away from the rationale and the default was never revisited, so nobody was ever asked the real question — does prawduct require live-harness verification before a PR? **When a default is justified by a category, re-read the justification when the contents change category.**

## When a test asserts a VALUE and its comment claims that value feeds a downstream contract, assert the CONTRACT instead — the comment does the reasoning the test never performs, so it reads as coverage while providing none: `test_name_is_critic_reviewer` checked the agent's frontmatter name and commented that the name "is the SubagentStop matcher target", true of dispatch and false of the matcher, and never opened `hooks.json`

The test asserted `name == "critic-reviewer"` — true, and still true after the fix. Its comment said that name "is dispatch subagent_type AND the SubagentStop matcher target." The first conjunct is right; the second is wrong, because the matcher is compared against the plugin-scoped identifier. The test never read `hooks.json`, so it could not have caught the mismatch, yet anyone auditing coverage for "is the matcher contract tested?" would find this and stop looking.

That is the harm: it is not merely absent coverage, it is **coverage-shaped absence**. A comment asserting a downstream relationship is a claim; if it is worth writing, it is worth asserting.

The same session produced a second instance from the opposite direction — an over-match guard using `general-purpose`, `Explore`, `prawduct:pr-reviewer`, none of which contain the agent name, so they fail to match under every candidate matcher including the broken one. The guard ran and asserted nothing discriminating. Both belong to the family TST-9M2X names; the fix in each case is to choose inputs that can distinguish the correct implementation from the plausible wrong one, and — as `test_the_over_match_guard_is_not_vacuous` now does — to pin that the guard itself can fail.

## When a decision defers a SET of findings rather than fixing them, enumerate the set against the filings before calling it done — deferral converts every item into a filing obligation and nothing reconciles the two lists automatically: a "file all ten" call produced six items covering eight, and the two dropped ones were found only because an independent reviewer counted

The owner chose "file rather than fix" for a cumulative's ten warnings. Six backlog items were filed. Mapping findings to items afterwards showed R-1 and R-8 had no home: a finding from the review's *methodology* section had been substituted into the slot where the first theme belonged, and the theme was lost — despite having been discussed in prose and offered as an explicit option in the decision put to the owner.

A fix-decision is self-checking, because unfixed code fails its test. A defer-decision has no such feedback: the finding leaves the review, and only a filing that nobody verifies stands between it and oblivion. The reconciliation is trivial — enumerate the source set, map each element to a filing, name the unmapped — and it takes under a minute against ten findings.

Generalises beyond findings to any "we'll handle these later" batch: deferred requirements, descoped acceptance criteria, follow-ups promised in a PR description. **The list you deferred from is the checklist; walk it.**

## When a skill/runbook has the model do a read-then-write CLI dance (read X's field, then write with `--if-<field>`), verify the READ actually SURFACES the field the write consumes — a write flag EXISTING in the CLI is not the same as its input being OBTAINABLE from the paired read, and static prose-vs-code review checks only the former; dogfood the handoff live (or write a read-then-feed test), because that gap survives even a clean multi-reviewer review

**Pattern**: The backlog-skill-repoint runbook (`skills/backlog/adapter-mode.md`) told the skill to `get` an item's `updated_at`, then `update <id> --if-updated-at <ts>` for optimistic concurrency. The cumulative Critic's correctness reviewer verified `--if-updated-at` EXISTS in `cli.py` — true — and passed. But the `get` envelope's decoded item (`encode.decode_item`) does NOT expose `updated_at` (keys: area/status/labels/body/id/…), so the instruction was unimplementable: the skill would pass an empty/`?` timestamp and get a spurious exit-4 conflict every time. All three independent Critic reviewers (correctness / design / sustainability) missed it. The Phase-1 pre-verification dogfood — running the actual read-then-write loop against real GitHub Issues — caught it immediately (the CAS rightly rejected the mismatched timestamp with exit 4).

**Root cause**: "the flag exists" and "the data to feed the flag is obtainable through the same interface" are two separate facts. Static review naturally checks flag existence against the CLI's arg parser; it does not trace whether the paired READ op's output schema actually contains the field. The read's projection (`decode_item`) and the write's flag (`--if-updated-at`) live in different code and were never cross-checked.

**The move**: for any documented A-then-B adapter/CLI dance where B consumes a field from A, DOGFOOD the handoff (run A, feed its output to B against a real backend) or write a read-then-feed test — don't spot-check each op in isolation. Fix here: dropped the get-then-CAS step; `update` is last-write-wins (correct for the single-actor interactive skill), with `--if-updated-at` documented as an optional guard only usable when a caller already holds the timestamp from elsewhere. This is *why* Phase-1 pre-verification earned its place before the PR. Kin to [[When developing requirements to replace a working system]] and the "verify against real instances — mocks are not verification" trap: the incidental part of an interface (a paired read's schema, a menu entry, an error-path envelope field) is load-bearing.

## When reconciling a backlog item a PR *partly* shipped, read ALL that PR's build-plan chunks before declaring any leg still open — a multi-chunk PR routinely lands the docs/methodology/skill leg in a LATER chunk than the code chunk, so crediting only the code chunk falsely marks the item open and sends the next picker to rebuild shipped work (the shipped-but-not-removed drift BKL-8T3W targets); diagnostic before writing requirements: read the delivering plan's `## Build Chunks`, or `git show --stat <merge>` for the doc paths the "open" leg names

**Pattern**: CRT-6W2N ("no supported git-worktree workflow") was reframed on 2026-06-22 after its code leg shipped: the reconciliation credited STH-4K7N's `resolve_project_dir` (the code) but declared the "documentation/methodology leg" *genuinely open*, and kept the item at `stage: requirements`. Asked on 2026-07-18 to open the requirements pass, I ran retrieval first — `git log -S "Working in a git worktree" -- methodology/building.md` and read `build-plan-worktree-compat.md`. STH-4K7N's plan had TWO chunks: Chunk 01 (code) AND **Chunk 02 "Worktree workflow guidance"**, whose description is verbatim CRT-6W2N's fix-shapes 1 & 3 ("document the now-supported worktree workflow so repos stop reinventing the review-in-primary / raw-`gh` workaround"). Both chunks merged in the SAME PR (#107, commit 796719d) on 2026-06-22 — the same day as the reconciliation. The docs leg was never open; I nearly wrote requirements for shipped work. Reconciled CRT-6W2N as shipped instead.

**Root cause**: the 2026-06-22 reconciler bound the item's "shipped" claim to the PR's *scope name* (`worktree-compat`) and its headline artifact (`resolve_project_dir`), not to the PR's chunk list. A multi-chunk PR that pairs a code chunk with a docs/methodology chunk is the COMMON shape — build plans routinely end with a "guidance/docs" chunk — so "code shipped, docs still open" against a single delivering PR is a red flag, not a stable state: the docs almost certainly rode the same merge.

**The move**: when a reconciliation would split one delivering PR into "code shipped / docs (or methodology, or skill) leg still open," enumerate that PR's build-plan `## Build Chunks` (or `git show --stat <merge>` filtered to the doc/methodology paths the "open" leg names) BEFORE crediting only part of it. This is the specific mechanism behind [[When surfacing a batch of model-proposed candidates for owner confirm-or-correct]]'s sibling concern in `backlog` BKL-8T3W (shipped-but-not-removed drift) — a structural check for it should compare an open item's claimed-open leg against the chunk manifest of any PR its `related:`/`closed-by:` names, not just the PR's scope label. Relates to Retrieval Over Generation (#24 — the cheapest check, `git log -S` / reading the plan, is exactly what caught it), Root Cause Discipline (#16), Complete Delivery (#2 — this is its inverse: a leg wrongly recorded as *un*delivered), and the sibling stale-base reconciliation diagnostic ("A red version/release-hygiene test ... is often a branch-STALENESS symptom").

## When compacting or migrating a file that tooling parses, classify every span by its CONSUMER before moving it — machine-read metadata (a parsed comment, a `sentinel=` tag, a status marker) is not "narrative" and must stay where its reader looks, because a content-loss guard that only proves "prose is preserved elsewhere" is blind to metadata it silently relocates or drops

**Pattern**: Compacting prawduct's own `learnings.md` (2026-07-17, 78KB→13KB), I moved each entry's narrative to `learnings-detail.md` and reduced learnings.md to header-only rules. My migration guard asserted *every learnings.md body is preserved in detail* — and it passed. But three entries carried `<!-- prawduct-learning: … sentinel=… -->` comments that `audit_learnings_cmd.py` parses **from learnings.md** (the `sentinel=` link is how `audit-learnings --apply` retires a learning once its enforcing test passes; `confirmations=`/`created=` are lifecycle data). I treated those comments as narrative: for the 73 header-reduced entries they vanished; for a moved entry they'd have gone to the wrong file. The first Critic pass caught it as a WARNING. Restored all three on the first body line under their headings (where `parse_learning_metadata` reads them) and confirmed the real parser sees all 3 (2 sentinels).

**Root cause**: I dichotomized the file's content into "narrative vs. header" when there was a third class — machine-read operational metadata with a *required location* (the file its reader looks in). A guard that only proves prose is preserved *somewhere* validates the wrong invariant; it cannot see metadata that must stay *put*.

**The move**: before any compaction/relocation of a file that a tool reads, enumerate what each consumer parses from it and treat those spans as fixed-location, not relocatable. The stronger guard checks placement-by-consumer, not just narrative-preservation. Relates to Root Cause Discipline (#16), Validate Before Propagating (#15 — verify the guard checks the invariant that matters), and [[When a governance checkpoint verifies a required side-effect happened, put it OUTSIDE the control flow that produces the side-effect]] (a check that verifies the wrong thing).

## When surfacing a batch of model-proposed candidates for owner confirm-or-correct (norm ratification, backlog reconcile, findings triage), triage by decision-worthiness FIRST — surface the few that carry a real fork individually, bulk-confirm the obvious rest, never a flat dump — because a flat list at scale buries the real decisions and trains the owner to rubber-stamp, defeating the review it exists to be

**Pattern**: While ratifying prawduct's own norms (2026-07-17), the doctor Norm Ratification flow instructed "present all candidates in one block for the owner to confirm, correct, or strike." Reading the seven strategy artifacts + preferences yielded ~20 candidate norms. Presented flat — even tiered into core/secondary — the owner's response was immediate: "far too much of a wall of text for me to process." The owner named it a defect in the model, not just the moment.

**Root cause — the flow had no notion of *signal*.** It treated a 3-candidate product and a 20-candidate mature framework identically: every candidate got equal presentation weight. But candidates are not equal. Most are rubber-stamps (facts are append-only, a reviewer never mutates its own session, authority fails closed) — a decision plainly stands behind them and the owner will just say yes. A few carry a genuine fork only the owner can resolve. A flat list makes the two indistinguishable, so the load-bearing 2-3 decisions drown in the obvious 17. The two predictable outcomes are the two failure modes of any un-triaged confirm batch: the owner **bounces off** the wall (what happened), or **rubber-stamps everything** — and blanket approval silently defeats owner-ratification, which is the entire reason ratification is owner-driven rather than automatic. A flow that produces rubber-stamping has quietly become the auto-ratification `docs/norms.md` forbids, just laundered through a human keystroke.

**The fix — surface by exception, with a reusable taxonomy.** Step 2 now *triages* each candidate into **clear-to-ratify** (decision plainly stands behind it, statement matches the code today, why is obvious) vs. **needs-a-ruling**. Step 3 presents them asymmetrically: needs-a-ruling individually with its fork + a recommendation (these are the point of the flow); clear-to-ratify as a single bulk-confirm line; and above ~6 total candidates the flat dump is *banned*, not merely discouraged. The needs-a-ruling taxonomy is the durable part — it generalizes past ratification to any candidate-surfacing step: **aspirational** (the statement outruns the code → honest form is `in-transition` + a tracking backlog item, or a narrower scope — e.g. "verdicts derive from facts" is realized only for the Critic plane while test-run/PR-review evidence still lives in its own files); **practice-not-written** (ratifying binds a habit that was never a written rule — e.g. conservative versioning, visible only in the tag history — and binding force is itself the decision to make); **wording/scope fork** (the drafted statement is too strong or slightly false — e.g. "the plugin writes nothing into a repo" is false, it reconciles `.gitignore`/`settings`); **collision/ambiguous** (two candidate whys conflict, or the normative/descriptive call is genuinely unclear); **whyless** (the rationale can't be stated without the owner — backfill first, per the collision rule).

**The failure mode is symmetric.** The opposite of a wall is not correct either: asking one norm per message is an interrogation that the original flow explicitly banned ("never ask one per message"). Surface-by-exception threads between them — individual attention *only* for the items that earn it, bulk for the rest.

**The guard against over-correcting into silence.** Bulk-confirming the clear tier must stay an *explicit* confirm. A clear-to-ratify tier that is presented but not affirmed is **not** ratified — the owner's "confirm" (or per-item veto) is what binds; no response ratifies nothing. Otherwise "bulk-confirm" becomes exactly the auto-ratification the whole flow exists to avoid, and the fix would reintroduce the disease it cured.

**Installed**: `skills/doctor/SKILL.md` Norm Ratification steps 2–3 (the triage + surface-by-exception + the ~6 cap + the guard); mirrored in `docs/norms.md` § Adoption (which restates the flow). The sibling pattern — `skills/janitor/SKILL.md` Step-3 Reconcile, which the original doctor step explicitly borrowed ("the janitor Step-3 Reconcile pattern") — shares the identical shape and is the open follow-up, held out of this change for scope discipline — it is now the *residual* scope of [[backlog]] GOV-8R3F, the requirement this cycle was captured under (the doctor half shipped here). Relates to Governance Is Structural (#22 — a review that gets rubber-stamped is not a gate), Independent Review (#14), Bring Expertise (#7 — the fewest asks that most change the outcome), and Proportional Effort (#11 — presentation weight should scale with decision weight).

## When writing a durable artifact (code comment, docstring, long-lived spec), never anchor its meaning to an ephemeral build identifier — carry the *why* inline, because build plans are deleted after completion and every project has many "chunk 03"s

**Pattern**: The owner reported a recurring leak (2026-07-14) — ephemeral identifiers ("chunk 03", "the eval-trust build plan") making it into durable artifacts like code comments and long-lived specs, where they mean nothing once the work is done.

**Root cause — an asymmetry in lifespans, with no firewall.** Build plans and their chunk labels are the *most* ephemeral artifacts in the system: `/prawduct:pr` deletes the plan file on merge (trunk) or release (gitflow), and the janitor sweeps stale ones. Yet the framework had (a) no guidance anywhere on what a code comment should contain (no WHY-vs-WHAT rule) and (b) no check for ephemeral references in durable output. So a comment like `// per chunk 03` — meaningful while the plan exists — silently rots into a dangling pointer the moment the plan is retired, and it isn't even uniquely resolvable (the build-plan template ships Chunk 01/02/03, so every project mints its own "chunk 03").

**The load-bearing distinction is product-artifact vs build-cycle-bookkeeping, NOT durable-file vs ephemeral-file.** A blunt "chunk ids never appear in durable files" rule would be wrong — it would contradict two deliberate existing conventions: change-log `chunks=00,01` tags and backlog `closed-by: <chunk-id>`. Those are *bookkeeping whose job is to record the build work*; the chunk ref there is an audit breadcrumb that degrades gracefully (the entry is still understandable without it). The forbidden case is a *product* artifact (code, comments, docstrings, long-lived specs, `docs/`, data model) whose meaning you can't reconstruct once the plan is gone. The backlog `closed-by` rule ("use a durable handle — a branch/scope name — not an ephemeral SHA or PR number") is the same identifier discipline pointed the other way, and was the precedent cited when writing this.

**The test**: *will this reference still resolve, and mean the right thing, after the build plan is deleted?* If the artifact needs it to be understood and it points at deleted scaffolding, it fails — carry the reason inline instead.

**Installed (full package, owner-approved scope)**: a clause under Principle 13 (using #10's construction-equipment metaphor); a builder rule in `methodology/building.md`; a compact line in `methodology/session-digest.md` (the only surface that reaches already-onboarded/migrated products — a framework-wide default must land there, per the session-digest carrier rule); and a Critic Goal 4 check (`ephemeral-ref firewall` → WARNING, bookkeeping explicitly out of scope). Deliberately NOT built: a grep/hook tripwire (false-positive-prone on "chunk" as a common word; case-law-first — automate only if the rule + Critic prove insufficient) — filed as [[backlog]] GOV-3P8K.

Discovered ephemeral-ref-firewall (2026-07-14). Relates to Coherent Artifacts (#13), Clean Deployment (#10), Reasoned Decisions (#4), Living Documentation (#3), and the backlog `closed-by` durable-handle rule.

## A red version/release-hygiene test on a feature branch is often a branch-STALENESS symptom, not a doc defect — check distance from the integration branch before patching the changelog

**Pattern**: backlog-service Chunk 01 close-out (2026-07-17). Resumed a session whose prior turn had
left a BLOCKING Critic finding: "CHANGELOG.md missing the current version (2.3.3) entry" — the suite
was red because `test_changelog_has_current_version_entry` saw `VERSION`/`plugin.json` at 2.3.3 but
`CHANGELOG.md`'s top entry at v2.3.2. The finding read as a one-line doc fix.

**Root cause**: `feature/backlog-prd-owner-feedback` was cut from `develop` at v2.0.1 and never
reconciled. Measured against `develop` (@ 3.0.4, the integration branch): **45 commits behind, 14
ahead**. The 14 ahead were almost all *docs* (the PRD drill-down); the Chunk 01 code was uncommitted.
The branch's `VERSION` had reached 2.3.3 via an ancestor `release-prep(v2.3.3)` commit, but the
v2.3.3 CHANGELOG headline — and every entry through v3.0.4 — lives on `develop`, because the release
flow adds the public headline on the integration side. So the branch had the version bump without its
changelog entry: a pure staleness artifact.

**Why patching would have been wrong** (Root Cause Discipline #16): (a) the v2.3.3 headline already
exists downstream, so hand-adding it here fabricates divergent history that conflicts at merge; (b) it
leaves the branch a full major version behind — including v3.0.0's *breaking rewrite of the review
data plane* (append-only evidence fact store). The prior session's blocking Critic finding was itself
recorded under the obsolete pre-v3.0.0 single-slot model. Patching the symptom would have shipped
Chunk 01 reviewed under a governance model it will never merge under.

**Fix**: merge `develop` in. `VERSION`/`CHANGELOG.md`/`plugin.json` all reconciled by auto-merge
(→ 3.0.4, full changelog history), and the v3.0.0 fact-store data plane came with it. The merge was
near-clean — one conflict (`active_build_plan`, exactly as the serial-merge-bookkeeping rule
predicts) — because the branch's own commits were docs and the uncommitted Chunk 01 code auto-merged
against v3.0.0's `bin/prawduct-hook` gate rewrite. One merge-boundary break surfaced (`norm_probes.py`
importing the pre-move `.backlog` API — see the sweep-every-reader rule). Re-review under v3.0.0 came
back 0 blocking.

**Diagnostic before ANY changelog edit on a feature branch**: `git rev-list --count HEAD..<integration>`
and `git merge-base <integration> HEAD`. If the branch is many releases / a major version behind,
reconcile (merge the integration branch), don't patch. A Critic reviews the *tree*, not the branch
*topology*, so it can correctly report the red suite while reading the symptom — the staleness
diagnosis is the builder's to make. Relates to Root Cause Discipline (#16), Coherent Artifacts (#13),
Honest Confidence (#5), and the sibling `check-cumulative-critic` stale-base gate diagnostic below.

When a feature branch fails a release-hygiene test (e.g. `test_changelog_has_current_version_entry`: `VERSION`/`plugin.json` say vN but `CHANGELOG.md`'s top entry is vN-1), check the branch's distance from its integration branch BEFORE editing the changelog. A branch cut long ago and never reconciled can sit many releases — a whole major version — behind (here: cut at v2.0.1, **45 commits / one major behind `develop` @ 3.0.4**); its `VERSION` was bumped by an ancestor `release-prep(vN)` commit, but the matching CHANGELOG headline landed on the integration branch, not this one. Patching the changelog on the stale base FABRICATES divergent history (the entry already exists downstream) and keeps the work under an obsolete governance model (a Critic finding here was recorded under the pre-v3.0.0 single-slot data plane). Root-cause fix: merge the integration branch in — `VERSION`/`CHANGELOG`/`plugin.json` reconcile by auto-merge and the current review data plane comes with it. Diagnostic before ANY changelog edit: `git rev-list --count HEAD..<integration>` + `git merge-base <integration> HEAD` — many releases behind ⇒ reconcile, don't patch. A Critic can correctly flag the red suite yet read the symptom ("add the vN headline"); the reviewer sees the tree, not the branch topology, so this diagnosis is the builder's. Full narrative in `learnings-detail.md`. Discovered backlog-service Chunk 01 close-out (2026-07-17). Relates to Root Cause Discipline (#16), Coherent Artifacts (#13), and the sibling stale-base gate diagnostic below.
## When `check-cumulative-critic` reports `uncovered` on a branch whose code you know was reviewed, suspect a stale base before running a fresh review — the gate anchors to `origin/<base>` by design, so unpushed integration commits drag already-shipped work into the required span

**Pattern**: v3.0.3 release (2026-07-14). Wrapping a +0.0.1 release, `check-cumulative-critic`
reported `uncovered: no composed review evidence spans 136bca56..b9b4356 at HEAD` for a feature
(`tree-validated-test-evidence`) whose change-log said it had a clean final Critic + a
verify-resolutions pass. Investigation, not re-review, was the right first move.

**Root cause — a two-layer staleness.** (1) `resolve-base` returned `origin/develop`, which sat at
**v3.0.1** while local `develop` was at **v3.0.2** — three unpushed commits, including a
`release-prep(v3.0.2)` that had never been promoted to `main` (a "phantom release": version files
and `develop` moved, but the `develop→main` promotion + push never happened, across sessions).
(2) `check-cumulative-critic` composes review facts from `merge-base(base, HEAD)`'s TREE forward;
with the base stale, the required span became the whole **v3.0.2 + v3.0.3** range. The evidence
store DID contain a clean fact for every piece (`test-evidence-ingest-test-command` base_tree
`136bca56`→`9136970e`; `tree-validated-test-evidence` `998c5d31`→`cb5aa9ca`→`669e94d5`, all
blocking=0), but no single chain composed from the stale `origin/develop` tree to HEAD because the
reviewed *working* trees never exactly equalled the committed trees (docs/release-prep tails).

**The fix was reconciling the base, not re-reviewing.** `git push origin develop` (a required
release step regardless) advanced `origin/develop` to the local tree; re-running the gate then
reported `satisfied: ... 2 review fact(s) + 1 free edge(s), 0 unresolved blocking` — the chain now
began at `develop`'s actual tree (`998c5d31`, exactly the feature's review base) and the single
free edge was the docs-only tail the CRT-7M2D allowance excuses. Zero fresh review needed.

**Diagnostic order** (bank this to avoid the 4–10 min wrong remedy the stderr suggests):
1. `prawduct-hook resolve-base` — is it `origin/<b>`?
2. Is local `<b>` ahead of `origin/<b>` AND an ancestor of HEAD? (feature cut from unpushed base)
3. If yes → `git push origin <b>` and re-check the gate BEFORE `/prawduct:critic cumulative`.
4. If unsure, read the evidence store (`<git-common-dir>/prawduct/evidence.jsonl`): the review
   chain's earliest `base_tree` should equal `merge-base(resolve-base, HEAD)`'s tree; if it equals
   the LOCAL integration tree instead, the base is stale.

**Systematic follow-through**: filed COV-7K4N (a stale-base hint on the uncovered path so the gate
diagnoses this itself + an unpromoted-release-prep session-start advisory for the root cause;
deferred spike on preferring the nearer of local/remote base).

**Now tool-supported** (COV-7K4N shipped as `stale-remote-base-diagnostics`, merged 2026-07-19):
the manual diagnostic order above is automated. `check-cumulative-critic`'s `uncovered` stderr
appends the `git push origin <b>` hint when the base is `origin/<b>` sitting behind an
ancestor-of-HEAD local `<b>` (`coverage.diagnose_stale_remote_base`), and a session-start advisory
(`lib/stale_base_probes.py`, type `unpromoted-release-prep`) nudges before the gate is hit when
local `<b>` carries an unpushed `release-prep(...)`, self-resolving on push. The base-resolution
re-architecture that would eliminate the false-`uncovered` at its root stays deferred as
COV-9B4T. Frequency is low — needs gitflow
(`base_branch: develop`) AND a feature built on an unpushed local-`develop` advance; trunk repos
(base = `main`) essentially never hit it since `main` never sits locally-ahead. The gap that
warrants the fix is the *misleading remedy* when it does fire, not the frequency. Relates to Root
Cause Discipline (#16), Validate Before Propagating (#15), Honest Confidence (#5), and COV-5H3N
(the distinct wrong-default-to-`main` facet), PR-7T2K (the mirror-image feature-branch push-state
case).

## When you add an ingest/IO surface to a platform-agnostic framework, expose the minimal data primitive — not one ecosystem's file format — or you silently lock out the toolchains the agnosticism promised

**Pattern**: test-evidence-single-run (2026-06-26, v2.2.3). An upstream report (COV-3R9K, scriob)
said consumers run the suite twice per chunk. A multi-agent investigation found the double-run was
NOT gate-forced (freshness is session-scoped; `changes_referenced` is base→working-tree
content-based, commit-invariant) — it came from a retired "record after the final commit" habit.
While scoping the fix, the user asked: "prawduct is supposed to be language/platform agnostic — are
we breaking embedded/non-Python users?" Auditing the recorder showed it was JUnit-XML-coupled: the
default runner is pytest, the `test_command:` knob REQUIRES a `{junit_xml}` placeholder, and
`--from-junit` ingests JUnit. JUnit is a broad de-facto standard (pytest/vitest/ctest/nextest/
gotestsum all emit it), so `test_command:` already made the recorder runner-agnostic FOR
JUnit-emitters — but a bespoke HIL rig or custom harness that can't emit JUnit had only two off-road
options: hand-write `.test-evidence.json` (the gap TST-6V2N closed) or write a JUnit adapter.

**Fix**: `--from-counts passed=N failed=M skipped=K [duration=S]` — the minimum viable test result
is pass/fail/skip counts; forcing those through JUnit XML WAS the coupling. The on-ramp records
counts directly (no run), so any toolchain participates. The Python-only COVERAGE floor (symbol-grep
in `bin/test-reference-verify`) is a separate, larger gap, split to COV-4M2J.

**Two lessons**: (1) When you add an ingest path to an agnostic framework, ask which real toolchains
CANNOT produce its format BEFORE shipping — agnostic-for-X is not agnostic. (2) A bug report's stated
root cause is a hypothesis: the report blamed a three-dot `git diff base...HEAD` shift, but the
producers use two-arg `git diff <base>` (base→worktree, commit-invariant); verifying against source
(not recalling, not trusting the report) redirected the whole fix from the report's suggested
content-hash (a deliberately-rejected mechanism, pre-v1.4 + TST-4K2P) to documentation + the on-ramp.
Relates to Bring Expertise (#7), Honest Confidence (#5), Verify-don't-guess, Proportional Effort
(#11).

When a framework brands itself language/platform-agnostic, a core ingest surface must not be gated on one ecosystem's interchange format. test-evidence `record` accepted results ONLY as JUnit XML (default pytest, `test_command:` requiring `{junit_xml}`, `--from-junit`) — fine for the many stacks that emit JUnit, but it left embedded/HIL/bespoke toolchains with no paved on-ramp (hand-write the JSON, or fake a JUnit file). The fix is to expose the MINIMAL primitive the gate actually needs — for test results, pass/fail/skip counts (`--from-counts`) — so any toolchain participates without writing an adapter. It surfaced only because the user asked "are we breaking non-Python/embedded users?"; so when adding an ingest path, ask up front which real toolchains CAN'T produce its format. Corollary (same cycle): an upstream bug report's stated root cause is a HYPOTHESIS — the scriob report blamed a `git diff base...HEAD` membership shift the producers don't do (they diff base→worktree, commit-invariant); verify against source before designing, because the real fix was docs + this on-ramp, not the report's suggested content-hash (which a deliberate prior decision had rejected). Relates to Bring Expertise (#7), Honest Confidence (#5), Proportional Effort (#11), Verify-don't-guess, and [[backlog]] COV-4M2J (the Python-only coverage-floor residual).
## When a build plan ships in a different release than it targeted, its frontmatter `scope:` must be the scope-NAME (not a version) — `regen-views` resolves plans by it and a version there silently skips Status flipping at release

**Pattern**: v2.1.8 batch release (2026-06-22). The `hook-cli-robustness` branch was built
targeting v2.1.7, then batched into the v2.1.8 release alongside three other branches. Its
build-plan frontmatter read `scope: v2.1.7` (and five prose references said v2.1.7). The PR
reviewer flagged the version references as a single **cosmetic** Coherent-Artifacts WARNING
("authoring-time snapshot, may be waived"). Checking the convention — every sibling plan's
frontmatter `scope:` is the scope NAME (`test-evidence`, `gate-hardening`, …), matching its
change-log `scope=` tag — revealed that line 11 was not cosmetic: it is the field
`regen-views` uses (REL-4T8N) to resolve a change-log `scope=hook-cli-robustness` tag to its
build-plan file. With `scope: v2.1.7`, the release would have enumerated `scope=hook-cli-robustness`,
found no plan with that frontmatter, and left the plan's `## Status` checkboxes `[ ]` — a silent
miss, since regen-views skips (doesn't error on) an unresolved scope.

**The rule**: when a plan ships in a different release than it was authored for, audit the
frontmatter `scope:` and any version references. The `scope:` must equal the change-log `scope=`
tag (the scope name), never a version. Don't accept a reviewer's "cosmetic version string" framing
for the frontmatter line — verify it against the sibling-plan convention, because release-time
`## Status` regeneration is load-bearing on it. The prose version references ARE cosmetic; the
frontmatter `scope:` is not. Relates to Coherent Artifacts (#13), Validate Before Propagating (#15),
Independent Review (#14 — the reviewer surfaced it but mis-severitied it; the audit caught the real impact).

## When serially merging several stale feature branches into develop for one batched release, expect additive bookkeeping conflicts every time — and watch for a duplicate `active_build_plan:` key the auto-merge creates

**Pattern**: v2.1.8 batch release (2026-06-22). Four completed-but-stale feature branches
(12–21 commits behind develop) were merged into develop in sequence for one release. Observations:

- **Bookkeeping conflicts are additive and predictable.** Every single merge conflicted on
  `.prawduct/change-log.md`, `.prawduct/backlog.md`, `.prawduct/project-state.yaml`, and
  `CHANGELOG.md` — because each branch had appended a change-log entry at the file top, backlog
  items at the `## Open` head, a pointer-history comment, and (for branches carrying the
  `024bf53` v2.1.6-headline cherry-pick) a `## v2.1.7`-vs-empty CHANGELOG gap. The resolution is
  always a UNION: keep both sides' additions. For the change-log, place all release-pending
  entries above the prior `release=vX` boundary regardless of their header dates (worktree-compat
  was dated 2026-06-20 but still belongs above the 2026-06-21 v2.1.7 boundary entry) — the release
  checklist enumerates by boundary, not date.

- **The `active_build_plan:` duplicate-key trap.** worktree-compat set its pointer near the TOP of
  project-state.yaml (just under `base_branch:`) while develop carried the pointer in the canonical
  mid-file slot (set to hot-path by the previous merge). Two column-0 `active_build_plan:` keys on
  different lines do NOT textually conflict, so git auto-merged BOTH → a duplicate top-level YAML
  key. It is runtime-correct under the repo's first-wins line parser (`lib.core.read_str_yaml_key`)
  but a PyYAML reader would last-wins to the WRONG plan, silently disabling that scope's gates. The
  cumulative Critic caught it as a Goal-4 coherence WARNING. Fix: collapse to one canonical key.

- **Critic records don't survive re-sync.** Each branch's prior-session cumulative Critic findings
  were gone (single-slot `.critic-findings.json`, gitignored), and re-syncing develop changed HEAD
  anyway — so a fresh `cumulative` per branch after the sync was unavoidable (verify-resolutions
  only extends a record that already covers the merge-base..pre-fix range). A forked Critic that
  dies mid-run (connection-closed) leaves `.critic-active` set with no findings written; clear it
  with `prawduct-hook critic-end` before re-invoking.

**The rule**: batch-merging stale branches → resolve bookkeeping by union (release-boundary order
for the change-log), explicitly check for a duplicated `active_build_plan:` key, and run a fresh
cumulative Critic on each branch AFTER syncing develop in. Relates to Coherent Artifacts (#13),
Independent Review (#14), Validate Before Propagating (#15).

## When a session switches branches after SessionStart, pass the Critic mode explicitly — `infer-critic-mode` trusts the stale session-start branch marker

**Pattern**: hot-path-git-batching / STH-6Q9D (2026-06-21). The session started on
`feature/hook-cli-robustness` (a merge-ready branch the user deferred), then the
work moved to a fresh `feature/hot-path-git-batching` off develop. At chunk close I
ran `/prawduct:critic` with no args. It inferred `verify-resolutions` and chained to
the *prior* session's anchors `f208ad2`/`f92a4be` — which live on the SIBLING
hook-cli-robustness branch and are not ancestors of HEAD. The mode-inference read the
branch captured at SessionStart, not the current one.

**Why the guard missed it**: `compute-verify-resolutions-scope` demotes a chain only
when the anchor `commit_reviewed` SHA does not *resolve*. A sibling-branch SHA still
resolves in the shared object store — it's simply not an ancestor of HEAD — so the
demote-guard passed it and the review computed an `anchor..HEAD` two-way diff that
spanned the divergence point. That surfaced the sibling branch's `git_path_is_ignored`
deletion and a `BLD-4K7P` carveout removal as if THIS work removed shipped behavior;
both were absent at the develop merge-base and untouched by the real commit. The Critic
self-flagged the phantoms and recommended `cumulative` on this branch, which I then ran
(clean: 0/0/4), followed by a chain-extending `verify-resolutions` (0/0/0).

**The rule**: after any mid-session branch switch, the session-start git markers
(branch, baseline) are stale for governance inference — pass the Critic mode
explicitly and anchor on the current branch. The deeper fix is filed as CRT-8H3R: add
a `git merge-base --is-ancestor <anchor> HEAD` check to the demote-guard so a
non-ancestor anchor demotes to `cumulative`/`final` instead of computing a divergent
delta. Note this is distinct from CRT-6J4P (anchor is a valid ancestor, just from a
prior bundle — surprise, not unsoundness); CRT-8H3R is the actual soundness bug.

---

## When verifying a framework-repo `lib/`/`bin/` change by running the hook, invoke the repo-local `python3 plugin/bin/prawduct-hook` — the bare `prawduct-hook` on PATH is the installed plugin cache, not your working tree

Surfaced 2026-06-22 during TEL-4M9X (review-stats model-id normalization). After landing the `_canonical_model` fold in `lib/telemetry.py` and confirming the unit tests passed, I ran `prawduct-hook review-stats` against the real ledger to watch the opus buckets collapse — and they didn't: the output still showed `opus` / `claude-opus-4-8` / `claude-opus-4-8[1m]` as three separate buckets, exactly as before the fix. Momentary "did the change not take?" The root cause: `command -v prawduct-hook` resolved to `~/.claude/plugins/cache/prawduct/prawduct/2.1.7/bin/prawduct-hook` — the installed plugin, pinned to the released v2.1.7 and importing *that release's* `lib/telemetry.py`, which has no `_canonical_model`. Re-running `python3 plugin/bin/prawduct-hook review-stats` from the repo root (which imports the working-tree `lib/`) showed the correct collapse — the 14-review cumulative bucket, with `fable` kept distinct. The unit tests never caught a problem because `tests/test_review_stats.py` invokes the hook via `ROOT / "bin" / "prawduct-hook"` — i.e. the repo-local copy — so the suite always exercised the new code. Fix-shape: when behaviorally verifying a framework `lib/`/`bin/` change, invoke the repo-local `python3 plugin/bin/prawduct-hook <cmd>`; treat the bare on-PATH command as *released* behavior that lags your edits until the plugin is re-released and re-cached. The diagnostic contradiction to watch for — green tests but unchanged PATH-command output — is itself the signal you're hitting the cached plugin, not your working tree. Relates to Honest Confidence (#5 — don't report a fix as broken on stale evidence), Validate Before Propagating (#15), and Reasoned Decisions (#4).

---

**Sharpening (2026-07-27, SCN-5B8Q Chunk 01) — the case where you don't get to choose the binary.**
The rule above assumes you invoke the hook. When the change is to `hooks.json` itself, the *harness*
invokes it, and the user-scoped installed plugin (`prawduct@prawduct`, a different checkout at `main`)
fires its own SessionStart entries in **every** repo you open — including the scratch repo you built to
test your fix. A real `claude --resume` against fixed hooks destroyed session evidence anyway, because
the OLD matcher fired alongside the new one; the fixed code was never at fault. Two rules: (a) an
end-to-end test of a hook/matcher change must isolate the config (`CLAUDE_CONFIG_DIR=<empty dir>`) or
it is testing the installed copy, not yours; (b) **when an integration test fails against a globally
installed component, identify which copy ran before debugging your own** — trusting the first failure
here would have meant "fixing" correct code. The contaminated run is not waste: it reproduced the
defect end-to-end on shipped code, which is stronger evidence than the simulation that motivated the
plan. Relates to Root Cause Discipline (#16) and Validate Before Propagating (#15).
## When prose picks which model a reviewer/subagent runs on, express it as an ordered fallback chain resolved at dispatch — never a pinned alias

**Pattern**: reviewer-model-fallback (2026-06-12). Reviewer dispatch pinned `model: fable` (escalate) / `model: opus` (standard) as literals in three skill-prose surfaces. Fable was temporarily withdrawn; the pin would break escalate-tier review — or worse, silently run it on the *session* model, because Claude Code resolves a blocked/unavailable subagent `model:` override to the inherited/default model rather than erroring (verified via `claude-code-guide`, code.claude.com/docs — not recall).

**Fix**: ordered tier chains + a withdrawn-model resolution rule across all three surfaces (`escalate` fable→opus, `standard` opus→sonnet): "use the first the harness lists as valid; fall back on a withdrawn/unrecognized model or dispatch error; record what ran." Per-call and frontmatter `model:` take a single value (no fallback syntax), so resolution is prose-driven by the runtime dispatching agent — the only actor that can see the live valid-model set (a Python hook can't, so an automated availability probe isn't feasible; the heavier registry+drift-check option is deferred as REL-5K8M).

**Two reusable sub-lessons**: (1) a token-budget guardrail at its ceiling forces trim-vs-bump on any necessary addition — remove genuine redundancy (cross-file duplicate comments, self-restating clauses), don't bump the budget or drop a check; the guardrail correctly makes new content pay for itself. (2) Verifying harness/model behavior beats recalling it: the silent-substitution-to-session-model detail (which I would not have recalled correctly) is exactly what turned the rule from "pass fable and hope" into "pick a confirmed-valid model, then fall back explicitly."

## After a clean cumulative (0 blocking/0 warning), NOTEs are advisory — don't chase cosmetic ones; fixing them reopens the coverage gate on judgeable governance files and forces a no-value review pass

**Pattern**: upstream-bug-reporting (2026-06-20). A cumulative Critic over the bundle came back 0 blocking / 0 warning / 5 notes. Some notes were `.py` (a misleading docstring, a speculative dead-code guard), some `.md` (slim-digest framing); fixing them meant a follow-up commit. Because the follow-up touched `lib/upstream_probes.py` (non-`.md`), the prior cumulative no longer vouched for HEAD, so the PR gate (`check-cumulative-critic`) needed a fresh HEAD-covering record — a full re-review. Had the fixes been `.md`-only, the CRT-7M2D docs-only allowance would have kept the original cumulative HEAD-covering and cost nothing.

**Why the re-review is full, not light**: the cheap post-fix path (`verify-resolutions`, Goals 1-3 over the delta) *demotes to `final`* precisely when prior findings hold no BLOCKING/WARNING — there's nothing to "verify resolved," so it falls back to a full pass. So an all-NOTE cumulative gives no cheap re-review path for a `.py` touch.

**Reusable rule**: self-scrub hard BEFORE the first cumulative (the methodology's "deep-scrub while the Critic runs" only helps if there's a gap to use; a synchronous skill return leaves none — so scrub before invoking). When notes land: fix `.md` notes in place (free), and weigh each `.py` cosmetic note against one opus re-run — fixing a false docstring + dropping dead code was worth it here, but a pure tense-nit was not (left as a defensible description). Route low-value `.py` notes to a backlog item rather than re-reviewing. Ties directly to the Review-wall-clock-is-P0 priority.

**Correction (2026-07-14, ephemeral-ref-firewall).** Two claims above are wrong, proven by direct observation this session — keep the narrative for history but do not act on the struck reasoning:
- **"`.md` fixes ride free" is false for JUDGEABLE files.** The CRT-7M2D docs-only free-edge covers only *non-judgeable* files (pure docs). Governance/instruction `.md` — `docs/principles.md`, `methodology/`, `skills/*/` protocols, `learnings.md`, `change-log.md` — is judgeable, so a `.md`-only note-fix commit to those left `check-cumulative-critic` **`uncovered`**. The real axis is judgeable-vs-non-judgeable, not `.md`-vs-`.py`.
- **"verify-resolutions demotes to `final` when no blocking/warning remains" is false.** With 0 prior blocking/warning AND a real delta, verify-resolutions ran as a LIGHT single-pass (Goals 1-3, one reviewer, ~1-2 min) and closed coverage — it did NOT demote. Demotion fires only when the anchor is missing, history was rewritten, the delta widens past 2×prior+5 files, or the prior was clean *and nothing changed since* (`review-cycle.md` demotion table); the original rule omitted the "and nothing changed" clause.
So the post-fix cost is ONE light pass, not a full re-review — but that is beside the point. The load-bearing lesson is upstream of cost: **a clean cumulative (0 blocking/0 warning) is already "ready to proceed" — NOTEs are advisory.** Don't chase cosmetic ones (they only reopen the gate for a no-value pass); self-scrub before the first review, fix only high-value notes (filing a deferred item = Complete Delivery), and batch ALL durable edits so there is ONE review, not three. Owner flagged this directly during ephemeral-ref-firewall: "avoid excessive reviews when they add no value."

## Artifacts drift silently during sustained building

**Pattern**: Discodon built 40+ chunks over multiple sessions. Artifacts written during planning (test-specifications, architecture, data-model) were never updated. Test-specifications says "1056 tests" when the actual count is 1318+. Coverage matrix is missing 15+ test files. Architecture may not reflect scheduling, tool framework, or prompt architecture features.

**Root cause**: Build cycle step 8 said "Update state" (meaning project-state.yaml) but didn't mention updating artifacts. The Critic's Coherence check verified code→artifact direction (does code implement the spec?) but not artifact→code direction (does the spec still describe the code?). No structural prompt to update artifacts as the code evolved.

**Resolution**: (1) Updated build cycle step 8 to explicitly include artifact updates. (2) Added bidirectional artifact freshness check to Critic's Coherence check. (3) This is Principle 3 (Living Documentation) applied to specifications — the same principle that prevents documentation fiction also applies to specs that become planning fiction.

**Principle**: Relates to Living Documentation (#3), Coherent Artifacts (#13).

## Structural gates must match natural workflow

**Pattern**: The stop hook checked for `artifacts/build-plan.md` to trigger the Critic gate. The methodology said to put the build plan there. But the natural workflow for discodon put the build plan in `project-state.yaml` (alongside status tracking). Result: the Critic structural gate never fired for 40+ build sessions. The Critic was invoked purely through behavioral compliance (Claude following CLAUDE.md instructions).

**Root cause**: When there are two reasonable places for something and the gate only checks one, the gate becomes optional. This is especially ironic given the v2 learning that "judgment alone won't interrupt momentum" — the gate existed to catch judgment failures but was watching the wrong door.

**Resolution**: Updated the hook to check both `artifacts/build-plan.md` and `project-state.yaml` for build plan content. Updated methodology to acknowledge both locations.

**Principle**: Relates to Governance Is Structural (#22) — structural gates must match how people actually work.

## Growing files need structural nudges to prune

**Pattern**: Discodon's learnings.md grew to 42KB (430 lines, ~12,000 tokens) despite guidance saying "keep under ~3,000 tokens." Each session added detailed technical learnings. No session pruned. The guidance to prune was present but never triggered behavior change — exactly the pattern from "filed-away observations don't change behavior."

**Resolution**: Originally a clear-hook size warning at 8KB (2026-Q1). Superseded when learnings moved to the `/learnings` skill (`context: fork`, filters to ~500 tokens) — the skill makes large knowledge files cheap to consult, so the size threshold no longer earns its complexity. The surviving mechanical-check pattern is the `project-state.yaml > 40KB` warning, which serves the same role for a file that is still loaded directly. The nudge returned 2026-06-10 (MET-6W3J) at the 40KB project-state threshold — at ~80KB the per-lookup cost of the fork-skill read became the problem the threshold now guards.

**Principle**: Relates to Close the Learning Loop (#18). The general rule (size targets need mechanical checks) still holds; the specific case got obsolesced by a better load mechanism.

---

## Init leaves CLAUDE.md unmerged when onboarding existing repos (RESOLVED)

**Pattern**: `prawduct-init.py`'s `write_template` skips existing files to avoid overwriting user edits. When onboarding an existing repo that already has a CLAUDE.md, init created all other Prawduct files but left CLAUDE.md untouched — no framework block markers, no Prawduct content.

**Resolution**: Added three-way CLAUDE.md handling in `run_init()`: new file → write template; existing without markers → prepend framework template, preserving user content below END marker; existing with markers → skip (sync handles). The merge action is reported in output. Manifest hash is correctly computed from the merged result.

**Principle**: Relates to Complete Delivery (#2) and Honest Confidence (#5).

## Mock scripts break with embedded newlines in f-strings

**Pattern**: The test mock git script is built via an f-string with `textwrap.dedent`. When `git_output` contains literal newlines (e.g., `" M file.py\n"`), the newline breaks `textwrap.dedent` — the injected line has no leading whitespace, so dedent finds no common prefix and leaves the shebang indented, making the script non-functional.

**Lesson**: When building mock scripts via f-string interpolation, avoid injecting values that contain newlines into the template. Test the mock's boundaries, not just the logic it simulates. Single-line mock outputs test the same comparison logic without fighting the test harness.

**Principle**: Relates to Tests Are Contracts (#1) — tests should be robust to incidental complexity.

## Shared modules via importlib work well for hyphenated Python scripts

**Pattern**: The sync/init/migrate scripts need to share helpers (`compute_hash`, `render_template`, `merge_settings`, `create_manifest`) but have hyphenated filenames that prevent normal Python imports. Using `importlib.util.spec_from_file_location` for cross-script imports works cleanly — already used in test files, now used in production code too.

**Lesson**: When multiple scripts need shared logic, extract it to one canonical module and import via importlib rather than duplicating. This prevented three copies of `merge_settings` from drifting apart. The pattern is: one module owns the function, others import it.

**Principle**: Relates to Coherent Artifacts (#13) — one source of truth for shared logic.

## Judgment alone won't interrupt momentum

**Pattern**: The v2 experiment replaced structural Critic gates with principles saying "invoke the Critic after each chunk." In the first real product build (Hum, chunk 1), Claude didn't read `methodology/building.md`, never invoked the Critic, and self-declared the chunk complete with 15 findings that any independent review would have caught. Discovery and planning methodology guides were read correctly — building was skipped because "start coding" doesn't naturally trigger "read the process guide first."

**Lesson**: There's an asymmetry between behaviors Claude will self-regulate and behaviors it won't. Claude follows principles about *how* to do work (test quality, scope discipline, spec fidelity). It does *not* self-impose process interruptions that halt momentum (invoke a reviewer, pause to read methodology). The first category can be governed by principles. The second needs structural gates. The minimum structural enforcement is: force independent review before declaring work complete.

**Principle**: Relates to Governance Is Structural (#22) and Independent Review (#14).

## Products must be self-contained for parallel agent work

**Pattern**: The v1 system required `framework-path` pointing to a local clone, runtime hook resolution, and shared session state files (`.session-governance.json`, `.active-products/`). This made it impossible for multiple agents to work on different products simultaneously — shared mutable state created race conditions and clobbering.

**Lesson**: Product repos must carry everything they need: their own CLAUDE.md with principles, their own hooks, their own Critic instructions. No runtime dependency on a framework clone. No shared state between agents. The framework is a *generator* that produces self-contained product repos, not a *runtime* that products depend on. This is also the distribution story — if products are self-contained, they work anywhere Claude Code runs.

**Principle**: Relates to Clean Deployment (#10) and structural independence.

## Reactive systems can't detect missing things

**Pattern**: The learning pipeline (observations, Critic, reviews) validates quality of what exists but cannot identify what should exist and doesn't. Critical gaps (missing cross-cutting concerns, missing artifact categories) went undetected across 13+ evaluations and 6+ sessions until an external audit surfaced them.

**Lesson**: Correctness validation ("does this work?") and completeness auditing ("is this everything?") are fundamentally different capabilities. You need both. Periodically step back and ask "what should exist here that doesn't?" — not just "is what exists correct?"

**Principle**: Relates to Automatic Reflection (#17) — reflection must include completeness, not just correctness.

## Governance complexity breeds governance complexity

**Pattern**: Each failure spawned a separate fix. After 11 independent additions, hooks alone were 1,079 lines — exceeding the skill files they protected. Triple-redundant debt detection, uniform 11-step processes regardless of impact. Root cause: reactive additions without coverage auditing.

**Lesson**: Before adding any new enforcement mechanism, ask: "Is this failure already covered by something that exists? Am I adding defense-in-depth where defense-in-one suffices?" Impact-scaled processes (lightweight for small changes, heavy for structural ones) reduce the temptation to make everything heavyweight.

**Principle**: Relates to Proportional Effort (#11) — governance itself must be proportional.

## Independent review catches what self-review misses

**Pattern**: Moving the Critic from in-context (same LLM reviews its own work) to a separate agent improved review quality measurably. The independent agent caught 2 surviving reference errors that in-context review missed, on its very first invocation.

**Lesson**: Independence is a feature for review functions. The reviewer should NOT see the builder's conversation context — that's what creates blind spots. Invoke the Critic as a separate agent via the Task tool. This likely applies to any review function.

**Principle**: Relates to Independent Review (#14).

## Principles need runtime enforcement, not just change-time checks

**Pattern**: "Generality Over Enumeration" was checked when modifying framework files but not when evaluating incoming user guidance. Result: the framework accepted a 285-line technology-specific design that violated the principle, because the principle wasn't applied at runtime.

**Lesson**: Principles apply to decisions as they happen, not just during retrospective review. When receiving guidance or making decisions, actively check: does this violate a principle? Especially watch for: technology specificity, structural assumptions, scope creep, and instance-specific solutions where general ones exist.

**Principle**: Relates to Governance Is Structural (#22) — governance applies continuously, not at checkpoints.

## Filed-away observations don't change behavior

**Pattern**: The YAML observation system captured detailed findings with severity, RCA categories, and status tracking. But observations accumulated without systematically influencing future decisions. The learning loop was write-only — observations were filed but nothing read them before making new decisions.

**Lesson**: Learnings must live where they're read, not where they're filed. This file exists because YAML archives don't change behavior. Keep learnings here, in natural language, where they're loaded at session start and directly influence decisions. When a learning has been incorporated into a principle or methodology update, it can be condensed here.

**Principle**: Relates to Close the Learning Loop (#18).

## Phase-based implementation enables independent testing and rollback

**Pattern**: Large changes (17+ files) that follow phased plans (infrastructure → validation → consumption → documentation) succeed more reliably than monolithic changes. Each phase preserves system functionality and enables confidence to build incrementally.

**Lesson**: For significant changes, plan phases so each one is independently testable and the system remains functional at every boundary. The opposite pattern — monolithic changes with deferred integration — creates fragility and makes rollback difficult.

**Principle**: Relates to Validate Before Propagating (#15).

## Denormalized state drifts without mechanical validation

**Pattern**: Parallel artifact generation by 5 agents produced 12 inconsistencies in denormalized inverse-dependency fields. Each agent independently estimated the field without cross-agent validation.

**Lesson**: Either compute derived data on demand from the source of truth, or mechanically validate it after writes. Never trust denormalized caches maintained by independent actors. This applies to any computed or derived field in any artifact.

**Principle**: Relates to Coherent Artifacts (#13).

## Coherence cascades require checking summaries, not just primary locations

**Pattern**: When adding `prior_art` to discovery, the primary section and template were updated correctly. But two summary lines elsewhere ("What Discovery Produces" in discovery.md and the condensed discovery paragraph in product-claude.md) listed what classification contains without mentioning prior art. Similarly, only one of four test scenarios received the new rubric criterion. The Critic caught all three gaps.

**Lesson**: When adding a concept to a system, search for every place that *summarizes* or *enumerates* what the system contains. Summaries are a form of denormalized state — they drift when the source of truth changes. After making a primary change, grep for summary phrases ("produces", "contains", "includes") that might need updating. Also check *scope declarations* — section comments that say "only for X" may contradict a universally-applicable new field. And check test scenarios — if sibling concepts have rubric criteria, the new concept needs one too.

**Reinforcement (2026-02-22)**: Fell into this exact pattern again when adding `error_handling_approach` under a "UI only" section comment and omitting test scenario rubric coverage. The learning was already captured; reading it wasn't enough to prevent the miss. The scope-declaration variant (section comments) and the test-scenario variant are now explicitly called out above.

**Principle**: Relates to Coherent Artifacts (#13) and Living Documentation (#3).

## Escape hatches in classification create silent failures

**Pattern**: Gate classified files as framework/product/ungoverned with ungoverned defaulting to auto-allow. An entire product was built without governance because unregistered repos fell into the "ungoverned" escape hatch.

**Lesson**: When classifying inputs, the "unknown" category should default to "suspicious/blocked", not "allowed." Fail-closed is almost always safer than fail-open. This applies broadly: any classification with an "other" bucket that auto-allows is a potential escape hatch.

**Principle**: Relates to Governance Is Structural (#22).

---

<!-- Narratives moved from learnings.md 2026-06-10 (MET-6W3J compaction) -->

## A new build plan with `scope: null` and low chunk numbers inherits another scope's shipped checkbox flips — set `scope:` from the start

When creating a build plan, set the frontmatter `scope:` to a unique slug immediately (matching the change-log entry's `scope=` tag) — do NOT leave it `scope: null`. With `views_enabled: true`, `regen-views` derives each plan's `## Status` checkboxes from `status=shipped` change-log entries; `collect_shipped_chunks` filters by the plan's detected scope, but a `scope: null` plan falls into "legacy unfiltered" mode where EVERY shipped entry contributes its chunk IDs. So a brand-new single-chunk plan whose chunk is "Chunk 1" gets flipped to `[x]` by an unrelated shipped entry like `chunks=1,2,3 | status=shipped | scope=work-model` — a spurious "shipped" on work that's only on a feature branch. (Discovered building CRT-3X9D: my `scope: null` plan's Chunk 1 flipped from the work-model v2.0.13 entry.) The build-plan template's `scope:` comment warns about this, but the warning lives in a template comment that from-scratch plan authors don't see, so it keeps recurring. Fix-shape: every build plan declares a unique `scope:` slug up front; verify by running `regen-views` after adding the change-log entry and reading the plan back (a statusless branch entry must leave the chunk `[ ]`) — `--check` is gone, views always regenerate. Discovered CRT-3X9D (2026-06-07, branch). Relates to Coherent Artifacts (#13), [[new change-log entries on a feature branch are statusless]] (the sibling regen-views trap), and Validate Before Propagating (#15).

## New change-log entries on a feature branch are statusless — `status=in-progress` is deprecated and trips the regen-views typo-guard

When adding a `.prawduct/change-log.md` entry for work on a feature branch (before it reaches develop), leave the `status=` tag OFF entirely — do NOT use `status=in-progress`. `lib/views.py` recognizes only `{shipped, merged}` (`VALID_STATUS_VALUES`), and `warn_unrecognized_status_tags` flags any *present-but-unrecognized* `status=` as "Likely a typo" on every `regen-views` run; `in-progress` is a deprecated legacy value (`docs/release-process.md` "Change-log `status=` values" documents the current model). The documented lifecycle (updated by single-pr-bookkeeping, 2026-07-10): the entry stays **statusless** through the feature→develop merge — a statusless tagged entry IS the release-pending state, and the old post-merge `status=merged` stamp step was retired because it required a commit on the integration branch, forcing protected-branch consumers into bookkeeping-only PRs (`merged` in older logs is an accepted legacy synonym, treated as statusless). Flip to `status=shipped` + `release=vX.Y.Z` at the develop→main release (gitflow), or write `status=shipped` (+ `release=` when the product versions) in the closing PR when its base is the release surface (trunk). A statusless entry triggers no warning (the guard only fires when `status=` is *present*) and flips no checkbox (that needs `status=shipped` + `chunks=`), which is exactly correct for branch-state and release-pending work. The work-model entry (v2.0.13, the immediately prior session) used `status=in-progress` on its branch and it slipped through only because `regen-views` wasn't run during that window — REL-8K3M's cumulative Critic caught the same value as a WARNING. Fix-shape: branch entries carry only `type=`/`scope=`; statuses change only inside a PR (release-prep or a trunk closing PR), never as a post-merge commit. Discovered REL-8K3M (2026-06-06, develop). Relates to Coherent Artifacts (#13), Escape hatches create silent failures (#22), Honest Confidence (#5), and Living Documentation (#3).

## A change-log `chunks=` tag must match the build plan's chunk-heading numbering *exactly* (zero-padding included) or `regen-views` flips only the matching chunks

When tagging a multi-chunk change-log entry, the `chunks=` list must use the **same numbering format** as the plan's `## Status` headings — if the plan reads `Chunk 01 … Chunk 10`, the tag must be `chunks=01,02,…,10`, not `chunks=1,2,…,10`. `lib/views.py`'s `regenerate_status_section` matches chunk IDs as **literal strings** (`CHUNK_LINE_RE` captures `01` from `Chunk 01:`), so `chunks=1` does not match `Chunk 01` — and the failure is *partial and silent*: at v2.0.15 release-prep, `chunks=1,2,…,10` against `Chunk 01..10` headings flipped **only chunk 10** (the one token that happened to match), leaving 01–09 stuck `[ ]` with no error. The tell is `regen-views`' own output — `"1 chunk(s) flipped — shipped [10]"` when you expected 10. The work-model release (v2.0.13) dodged this by using single-digit `Chunk 1/2/3` headings to match `chunks=1,2,3` (noted inline in its prep commit), but a plan written with zero-padded headings needs zero-padded tags. Fix-shape: after `regen-views` at release, read its flipped-count and confirm it equals the chunk count; if fewer flipped, the `chunks=` numbering doesn't match the headings — align the tag to the headings (don't renumber the plan). Discovered v2.0.15 backlog-rework release (2026-06-08, release). Relates to Coherent Artifacts (#13), Validate Before Propagating (#15), and [[At release, flip statusless unreleased change-log entries]].

## When a feature's logic lives in a `context:fork` skill (no Bash), `lib/` holds the DATA, not the LOGIC — logic helpers nothing imports are dead code

A `context:fork` skill (e.g. `/prawduct:backlog`, `allowed-tools: Read, Edit, Write, Grep, Glob` — no Bash) is LLM-interpreted prose: it cannot import or call a `lib/` module. So its filtering/routing/dedup/ranking *logic* is the agent reasoning over the file it reads — there is no Python call site. The runtime (`bin/prawduct-hook` and the hooks it runs) is the only consumer of `lib/`. Consequence: when planning such a feature, `lib/` should carry the **data layer** (a parser + pure query accessors — like `lib/backlog.py` mirroring `lib/views.py`) that the *runtime* needs (briefing counts, probes), and the **logic** belongs in the skill prose. A planned `lib/` "logic helper" the skill would supposedly use (`is_implementable`, a dedup-candidate scorer, an archive-split function) is **dead code** — nothing imports it — and the Critic flags it (Goal 7) or it sits untested-by-a-real-consumer. The backlog-rework plan listed four such helpers; each was correctly descoped, but the descope must be **recorded** (Principle 2) — the Critic flagged the first one left silent (ch.03). Fix-shape: when a plan assigns logic to a fork-skill feature, put data in `lib/` (+ tests) and logic in the SKILL.md; if a plan line says "add `lib/` helper X for the skill," ask "does any *Python* path call X?" — if no, it's skill prose, descope the helper and record it. Discovered backlog-rework v0.3 (2026-06-08, branch). Relates to The Design Is Sound (#7 — no dead code), Complete Delivery (#2 — record descopes), Scope Discipline (#12), and [[fine-grained tool restriction needs a fork-skill, not a named subagent]].

## At release, flip *statusless* unreleased change-log entries to `status=shipped` too — not just `status=merged`

`docs/release-process.md` step 3 says to flip entries "from `status=merged` to `status=shipped`," but in practice most unreleased entries reach release-prep **statusless**, not `status=merged`. The documented two-state lifecycle (add `status=merged` at the feature→develop merge — see [[new change-log entries on a feature branch are statusless]]) is manual, and the `/prawduct:pr` merge flow does NOT apply it, so a branch entry stays statusless from branch through develop into release-prep. A release author who follows step 3 literally flips only the `status=merged` entries and **silently drops every statusless one** — and because `regen-views` acts only on entries with `status ∈ {shipped, merged}`, a dropped statusless entry's build-plan `## Status` checkboxes never flip, and it never appears in `release-notes.md` or `scope_rollups`. The omission is invisible (no warning — a statusless entry trips no typo-guard), so the release ships looking complete while quietly missing scopes. At v2.0.14 (batched: hook-decomp ch.1–7 + critic-session-guard) **8 of 10** unreleased entries were statusless; only the two bugfixes carried `status=merged`. Fix-shape: at release-prep, enumerate ALL change-log entries above the prior `release=vX` boundary and flip each (statusless OR `status=merged`) to `status=shipped` + `release=vX.Y.Z`; then run `regen-views` (exit 0, not 3 — a 3 means some scope's `## Status` was suppressed) and confirm every shipped scope's plan flipped to `[x]` and appears in `scope_rollups`. Deeper fix is filed ([[backlog]] REL-2N8K): either make the feature→develop merge reliably set `status=merged`, or reword release-process.md step 3 to say "statusless or `status=merged`." Discovered v2.0.14 release (2026-06-08, release). Relates to Complete Delivery (#2), Living Documentation (#3), [[new change-log entries on a feature branch are statusless]], and Validate Before Propagating (#15).

## "I'm just codifying their guidance" is not an exemption from the research trigger — and volatility is a separate axis from knowledge-confidence

When you're about to design or place something and tell yourself "I'm only writing down what the user already specified, so no research needed," check whether the *design or placement* (not the content) lives in a fast-moving domain — that's a separate, easily-missed trigger. In rigor-and-stance (2026-06-04) I judged "no web research — internal codification of owner guidance," but the work was *designing agent methodology and choosing a Claude Code placement*, both in a space that ships changes weekly, well past my training cutoff. The owner caught it; two research passes then materially improved the design AND corrected the requirements model we were building. Root cause: I conflated owner-specified *content* (the stances — genuinely no research) with the *design/placement* (volatile — needed it). The durable distinction, now encoded in `methodology/discovery.md` "Calibrate Rigor": rigor has TWO independent research axes — **knowledge-confidence** ("do I know enough to design this well?" → reason/decompose) and **volatility/recency** ("does correctness depend on timely / post-cutoff / fast-moving data?" → web research). My miss was a pure volatility miss *with* high knowledge-confidence — direct proof the axes are distinct, which is why the model splits them. Fix-shape: before declaring "no research needed," run the self-check "does this depend on the current state of the world, or a field moving faster than my training cycle?" against the DESIGN and its INPUTS, not just the stated requirements — "I'm just codifying" is the phrase that suppresses exactly this check. Discovered rigor-and-stance (2026-06-04, develop). Relates to Honest Confidence (#5), Bring Expertise (#7), Validate Before Propagating (#15).

## The "canonical" mechanism for a capability can be disqualified by a plugin's composability + always-on constraints — verify the constraint before adopting the recommendation

When research or docs name a "first-class / canonical" mechanism for a capability, verify it against the consumer's *structural* constraints before adopting it — a governance plugin needs its behavior always-on AND non-clobbering of a consumer's own config, and that can disqualify the otherwise-correct canonical choice. In rigor-and-stance (2026-06-04) the research recommended Claude Code **Output Styles** as the first-class home for agent personality/stance (true in general — system-prompt-level, prompt-cached, discoverable via `/config`). A verification pass confirmed `force-for-plugin: true` HARD-OVERRIDES (clobbers) a consumer's own selected output style and does not compose — disqualifying for a plugin whose governance must be unconditional AND must not trample a consumer's setup. The always-on SessionStart digest is both unconditional and composable (additive context, orthogonal to the user's chosen style), so the stance stayed there — the original instinct, now correct for a *verified* reason instead of inertia. Sibling of "verify the platform's copy/packaging boundary before duplicating": a generic best-practice loses to a verified structural constraint; confirm the constraint (single active slot? clobbers? composes?) before taking the rec. Platform fact for future Claude Code work: an output style's `force-for-plugin` overrides the user's `outputStyle` (one active style at a time, no merge). Discovered rigor-and-stance (2026-06-04, develop). Relates to Validate Before Propagating (#15), Reasoned Decisions (#4), Visible Costs (#9).

## When fanning out a batch build to parallel worktree-isolated workflow agents, partition by disjoint file ownership (integrator owns shared files) and force-clean leftover worktrees before the integration suite

A workflow that builds N backlog items in parallel via `isolation: worktree` subagents integrates cleanly IFF the work is partitioned so each agent OWNS a disjoint file-set and any file that MULTIPLE chunks would touch is reserved for the integrator. In cleanup-batch (6 chunks, 2026-06-04) the one shared file was `tests/test_v5_methodology.py` (token-budget assertions for both `methodology/building.md` and the critic `review-protocol.md`); keeping it OFF the two doc agents — they only *reported* budget overruns in their structured result, the integrator did the bump — meant all six `git diff --cached` patches applied to the main tree with zero conflicts (`git apply --check` clean on all 6). Two operational gotchas: (1) worktree-isolated agents' worktrees do NOT auto-remove when they have changes, and this repo's structural tests (`test_test_location`, `test_plugin_methodology_digest`) scan the whole tree — so leftover `.claude/worktrees/wf_*/` copies fail the suite with "not one canonical copy" / "test files outside tests/". `git worktree unlock && remove -f && prune` them BEFORE the integration full-suite run (filed a backlog item to make those tests ignore `.claude/worktrees/`). (2) Governance stays in the main session: agents BUILD and self-verify only their targeted test module (`-n0`); the integrator runs the FULL suite, reconciles shared-file budgets, records test-evidence, and runs the cumulative Critic. The Critic's only findings were integration-bookkeeping (stale evidence, a chunk-ref-parser false positive), never code — confirming the agents-build / main-session-governs split holds at fan-out. Discovered cleanup-batch (2026-06-04, develop). Relates to Independent Review (#14), Scope Discipline (#12), and Proportional Effort (#11).

## When a fresh-eyes review's advice about a CONVENTION conflicts with a durable learning + the process doc, the documented convention wins — re-verify before acting

When a forked Critic / PR reviewer makes a claim about *how this project does bookkeeping* (release timing, status semantics, "X is consistent with the flow"), treat it as a reading of the CURRENT tree, not as institutional authority — the reviewer has not read `learnings.md` or `docs/release-process.md` and only sees the artifacts in front of it. In the roi-batch session the cumulative Critic noted "no change-log entry yet is consistent with this project's release flow (added at release time)" — empirically true of the recent *plan-IS-the-release* cases (every prior entry was `status=shipped`, added in the `chore(release)` commit), so it over-generalized. I over-weighted it (plus the runbook's own `status=shipped` error) and first DEFERRED the change-log entirely + CLEARED `active_build_plan` — the opposite of the documented convention. The source of truth (`docs/release-process.md` + `learnings.md` "KEEP the build plan" + the build plan's own `scope=` comment) prescribes Model A for a batched sub-release merged ahead of its `develop→main` release: add a `status=merged` change-log entry (tagged `scope=`, `chunks=`), KEEP `active_build_plan` until the release, then the release flips `merged→shipped` + runs `regen-views` + clears the pointer. Fix-shape: when a review's convention-claim or a pre-`/clear` runbook's bookkeeping step diverges from a durable learning, RE-READ the learning + process doc and follow them; a reviewer's tree-level observation does not override documented institutional memory. Discovered roi-batch (2026-06-03, develop). Relates to Validate Before Propagating (#15), Independent Review (#14), and Close the Learning Loop (#18).

## A reviewer's NOTE/severity is a prior, not a verdict — re-scope any "harmless" change that touches a governance-gate input

When an independent review rates a change low-severity ("harmless dead allowlist entries"), treat the label as a starting prior, not a conclusion — especially when the change touches an *input to a governance gate*. The develop→main v2.0.3 release review NOTE-rated removing `.claude/skills/` and `tools/product-hook` from `_METADATA_PREFIXES` (the allowlist `_is_metadata_path` consults to decide whether a changed file trips the Critic/reflection gates). Tracing the call sites showed it was not purely dead: `tools/product-hook` removal is inert in a plugin repo (the file never exists), but removing `.claude/skills/` is a real behavior change — a product's *own* skill under `.claude/skills/` had been classified as excused framework metadata and silently skipped the gates, so the removal closes a governance hole. A behavior change to a gate input is a contract change and gets a test (`TestMetadataPathClassification` pins both the classifier and the end-to-end inference flip from rule-4 to "no build plan medium+"). Fix-shape: for any edit to a gate's input set (allowlists, prefix tables, fileset bounds), enumerate the predicate's consumers (`grep` its call sites), decide whether behavior actually changes, and add/adjust a test when it does — don't let a low-severity label substitute for tracing the blast radius. Discovered v2.0.3 develop→main promotion (folding `[JAN-4F7M]`). Relates to Tests Are Contracts (#1), Root Cause Discipline (#16), Independent Review (#14), and Honest Confidence (#5).

## A new framework-wide DEFAULT must land in the session digest — place-once preferences and the thin anchor don't reach migrated repos

When changing a framework-level *default behavior* that every product (any vintage) should pick up, the carrier must be `methodology/session-digest.md` — the only surface injected into every product session unconditionally (`hooks/digest.py`, all SessionStart matchers). The intuitive homes don't propagate to existing repos: `templates/project-preferences.md` is **place-once** (created once at init, never regenerated when the template changes — see "Framework ownership follows the write strategy"), and a migrated repo's `CLAUDE.md` is only the thin static anchor (`migrate_plugin.STATIC_ANCHOR`, deliberately minimal/version-free), so neither carries a default added after the repo was set up. Concretely (v2.0.0, "default to no commit attribution trailers"): the rule went in the digest (reaches all vintages) + the project-preferences template (documents the opt-in for *new* products) — and was deliberately NOT added to the every-session `product-claude.md` PRAWDUCT block, which is token-budget-bound (`test_token_budget`, 3050) and was already at ceiling; duplicating it there would have bought nothing the digest doesn't already deliver, at a permanent per-session token cost. Fix-shape: for a new default, ask "which surface does an *already-onboarded* repo actually re-read?" → the digest, not its frozen place-once files. Relates to Coherent Artifacts (#13), Visible Costs (#9), and Proportional Effort (#11).

## Single-repo plugin+marketplace: the marketplace entry's plugin `source` must be `"./"`, not `{source:github,ref}`

When a plugin and its `.claude-plugin/marketplace.json` live in the SAME repo (prawduct's topology), the marketplace entry's plugin `source` must be the relative `"./"`, NOT a `{ "source": "github", "repo": …, "ref": … }` object. The github-source form makes Claude Code **re-clone the repo over SSH** (`git@github.com:…`) to fetch the plugin — which fails with "Permission denied (publickey)" on any machine without SSH keys (most HTTPS/`gh`-auth users), **even for a public repo**. The `"./"` form reuses the marketplace's own HTTPS checkout (one clone, no SSH) and inherits the marketplace's pinned `ref`. Don't confuse the two source surfaces: the *consumer's* `extraKnownMarketplaces` source IS `{source:github,repo,ref:main}` (that's the marketplace clone — HTTPS, fine); the *plugin* source inside `marketplace.json` is `"./"`. Empirically proven in the v2.0.0 Chunk-2 spike (throwaway public repo) and confirmed on prawduct's real marketplace install (`claude plugin install prawduct@prawduct` → v2.0.0, no SSH). Related operational gotchas from the same release: `claude plugin marketplace remove <name>` **cascades** — it disables dependent plugins and wipes their `enabledPlugins`/`extraKnownMarketplaces` from settings (don't use it as "cleanup" if you want the plugin to stay enabled); and `git merge -F -` does **not** read stdin like `git commit` (use `-m` or a real file). Full spike results in `docs/release-process.md`. Relates to Validate Before Propagating (#15) and Visible Costs (#9).

## Release-bound work merged feature→develop under gitflow: KEEP the build plan — it's a live release artifact, not spent

When you merge a feature branch whose work ships at a *later* `develop→main` release (gitflow batched-release, not the old develop-merge=release model), do NOT delete the build plan at merge time. The PR skill's merge-flow **step 7** ("delete `artifacts/build-plan.md` after merge; git preserves history") assumes the older model where the develop-merge *is* the release. Under gitflow the build plan stays a *live release artifact* in the window between the develop-merge and the develop→main release: release-checklist **step 4** runs `regen-views` *on the build plan* to flip its `## Status` checkboxes `[ ]`→`[x]` from the change-log's `status=shipped` entries (`docs/release-process.md`). Delete it at merge and the release step has nothing to regenerate — and the `active_build_plan` pointer in `project-state.yaml` must likewise survive until the release. Retention loses nothing: the release-pending state is already fully captured in the change-log's `status=merged` entry plus its "Deferred" note, and git preserves the plan regardless. So the deletion is both premature and lossy. Fix-shape: the skill's step 7 should be *conditioned on whether the merge is itself the release* (develop-merge that ships now → delete; develop-merge ahead of a batched develop→main release → retain). Discovered v2.0.0 PR #49 merge to develop (release deferred to develop→main per `docs/release-process.md`). Relates to Coherent Artifacts (#13), Living Documentation (#3), and Proportional Effort (#11).

## A `--plugin-dir` read-block is a dev-flag artifact, not a self-containment bug — pair it with `--add-dir`

When testing a Claude Code plugin's self-containment via `--plugin-dir <path-outside-the-project>`, a skill reading its OWN bundled file (`${CLAUDE_SKILL_DIR}/../../methodology/X.md`) is blocked by the session's working-dir read sandbox — which looks exactly like a self-containment defect ("the skill can't read its methodology"). It isn't: the path resolves correctly into the plugin, but the plugin tree sits outside the project dir, so tool reads there are sandboxed. Pass `--add-dir <plugin-path>` alongside `--plugin-dir` and the read succeeds; a real *marketplace* install grants plugin-tree reads automatically (the plugin is discovered from a config root already in scope), so `--add-dir` is a dev-flag-only need. Do NOT "fix" the skill's paths in response to a `--plugin-dir`-only failure. Verified v2.0.0 Chunk 12 (claude-code-guide + empirical A/B: `/prawduct:building` returned the plugin's H1 from a hallucinote-2 cwd with no `methodology/`, but only once `--add-dir` was added). Relates to Honest Confidence (#5) and Validate Before Propagating (#15).

## Test subprocesses: HOME=tmp_path leaks Python's pyc cache into the test repo

When a test invokes a Python subprocess via `subprocess.run(env={"HOME": str(project_dir), ...}, cwd=str(project_dir))`, Python's xcode-shipped interpreter writes `.pyc` cache files to `$HOME/Library/Caches/com.apple.python/...`. If `$HOME == cwd == git repo root`, `git ls-files --others --exclude-standard` then returns ~50 untracked cache files, inflating diff counts and triggering scope-widening / status-pollution failures in helpers that use it. Fix: set `HOME` to a directory OUTSIDE the test's git repo (e.g., `project_dir.parent / f"{project_dir.name}-home"`). Discovered v1.5.1 Chunk 03 (TestComputeVerifyResolutionsScopeSubcommand). Relates to Structural Awareness (#21).

## "Structurally enforced" requires verifying the harness actually enforces it

When claiming a constraint is "structurally enforced" by a config/sandbox/permission system, verify the enforcement before claiming it in change-logs or memory rules. The v1.5.1 Chunk 02 `!Bash(pytest*)` deny patterns added to skill `allowed-tools` were claimed structural but the Critic ran pytest unimpeded one chunk later — the harness allows `Bash(python3:*)` at project level which overrides skill-level `!`-deny. The prose claim "structurally enforced" survived only until the next chunk's Critic. Negative-path probe (write a test that asserts the constraint blocks the forbidden invocation) before claiming. Discovered v1.5.1 Chunk 04 Critic. Relates to Honest Confidence (#5) and Validate Before Propagating (#15). (v1.8.0 Chunk E added `test_no_allow_pattern_permits_pytest` — the probe this rule asked for — backing the pure-allow-list claim for the Critic.)

## Tool-restricted reviewer agents must be context:fork SKILLS, not named plugin subagents

When an agent needs a fine-grained tool restriction (the Critic: read-only git verbs, no pytest, no tree mutation), implement it as a `context: fork` skill with a pure-allow `allowed-tools` list — NOT as a named plugin subagent (`agents/<name>.md`). A named plugin subagent's `tools`/`disallowedTools` frontmatter is bare-tool-names-only (no `Bash(git diff:*)` granularity), so listing `Bash` grants unrestricted Bash; and a skill's `allowed-tools` does NOT bind a named subagent it delegates to. Only the fork-skill layer can express AND enforce the fine-grained allow-list. Verified v2.0.0 Chunk 4 (claude-code-guide + `--plugin-dir` probes); this is why the recorded "Option A — proper plugin subagents" decision was reversed mid-build once the unverified granularity assumption resolved. Relates to Reasoned Decisions (#4) and the safety constraint CRT-2M5P. Caveat: whether the fork-skill cap is enforced interactively (vs. headless, where a probe showed it is NOT) is still open — backlog CRT-9V4T.

## When a deliberate change turns a passing test red, renegotiate the contract in the open

When you intentionally change a documented behavior and an existing test fails because it encoded the OLD behavior, do NOT silently relax or delete the assertion. Rename the test to the new contract, re-document why in the docstring, invert the assertion, and record the rationale (commit/change-log). "Fix the code, not the test" (Principle 1) assumes the test encodes CORRECT behavior — when the test encodes the very thing you're deliberately removing (an every-session nag, or a safety hole asserted as "legitimate"), the test is a contract to renegotiate transparently, not a bright line to respect blindly. Keep any still-valid invariant explicit (changing template-drift to fire-once, also assert the user's place-once file is still never overwritten). Recurred ~20× across v1.8.0 chunks B/C/E. Relates to Tests Are Contracts (#1) and Reasoned Decisions (#4).

## A behavior change isn't done until every artifact that DESCRIBES it is updated

When you change behavior that a synced/templated/documented artifact describes — a briefing format, what files ship to product repos, a CLI's output — grep for every place that describes it, not just the code that implements it. The v1.8.0 cumulative Critic caught two misses in one bundle: the product CLAUDE.md template still described the pre-diet briefing, and the product-layout diagrams still omitted the now-shipped `tools/lib/`. Same blind spot both times: changed the behavior, missed the descriptions. The independent cumulative review is the fresh-eyes pass that catches doc-vs-behavior drift the builder is blind to. Relates to Living Documentation (#3) and Independent Review (#14).

## A decision reversed mid-chunk leaves stale rationale in prose you just wrote

When you reverse a design decision partway through a chunk, the code follows the new decision (it's what you're actively editing) but comments and docstrings you authored *under the old decision* keep asserting it — and they feel trustworthy precisely because you wrote them minutes ago. Before handing to the Critic, re-grep your OWN new comments/docstrings for the abandoned rationale. v2.0.0 Chunk 7: the banner docstring claimed the version marker was gitignored "via `GITIGNORE_ENTRIES` in `lib/core.py`" — written while leaning toward adding it there; the decision then flipped to gitignore-in-this-repo-only + defer-to-Chunk-9, the code followed, the docstring lied until the Critic flagged it. Distinct from "update every artifact that describes a behavior change" (#3): the trigger here is a *reversal within one work cycle*, and the stale prose is your own fresh code-adjacent text. Relates to Living Documentation (#3) and Reasoned Decisions (#4).

## Editing a runtime that governs the current session: check your own signals first

When you modify a runtime that ALSO governs the session you're editing in (a self-hosted framework — prawduct's hooks govern prawduct's own development), verify the change doesn't alter the CURRENT session's governance before trusting it. v2.0.0 Chunk 8 added "legacy hook stands down when it detects the plugin" to `tools/product-hook` — which is THIS repo's own active SessionStart/Stop hook. A wrong detection signal (or a stray `enabledPlugins` / `distribution: plugin` already in this repo) would have silently disabled the very Stop gate enforcing the session, with no test failure to warn you. The check is one command: run the new detection against the repo root and confirm it returns the expected value (here: plugin-active = False) before relying on the edit. "Am I standing on the branch I'm sawing?" Distinct from test coverage — this is about the live session, not the test matrix. Every remaining v2.0 migration chunk (9–13) edits this same self-hosted runtime, so the check recurs. Relates to Structural Awareness (#21) and Validate Before Propagating (#15).

## Cumulative-Critic finds first-use regressions chunk-Critic can't

When wrapping a multi-chunk bundle, expect the cumulative-Critic pass to surface ≥1 finding the chunk passes missed — mechanisms introduced in chunk N often misbehave only against prose in chunk M. Plan a remediation slot before `/pr create` rather than treating the cumulative pass as a formality. Because the lens differs: chunk-Critic diffs the chunk's own commit; cumulative-Critic diffs `merge-base...HEAD` and catches helper-vs-prose interactions invisible at chunk scope. Wave 1's `_looks_like_file_path` (Chunk 02) false-positived on slash-commands in Chunk 01's prose — only the cumulative pass saw both at once. Relates to Independent Review (#14).

## Auto-enable belongs with visibility, not with enforcement

When deciding whether a new opt-in feature should silently auto-enable on sync, ask whether flipping it ON would cause the next PR to **block** unexpectedly. Visibility surfaces (derived views, additional briefing fields, schema fields the writer fills in) auto-enable safely — at worst the user sees new output. Enforcement surfaces (Critic BLOCKING checks, gates that refuse `/pr create`, hooks that exit non-zero) must be explicitly invoked via `migrate --enable-<feature>` so the workflow commitment is visible before it bites. Chunk 07's F1 derived-views auto-enabled silently on sync ("users should get views for free"). Chunk 10's F4 coverage *deliberately* broke the pattern — a silently-flipped `coverage_required: true` would BLOCK the user's next PR for reasons they didn't agree to. Same shape (one-shot manifest flag, additive YAML edit) but opposite invocation policy. **Nuance (v2.0.0 §5a — owner override):** this rule is *superseded* when the owner explicitly models governance **as CI** — a plugin update MAY ship a gate that blocks immediately, with no opt-in / adopt step, *provided the block is attributed*: the version-delta banner announces the new gate on the bump that introduces it, and the blocking message names the version + gate so a surprise block is always traceable to the update ("no different than shipping a CI change that blocks someone's push"). Visibility is preserved as **attribution, not opt-in**; the deciding question becomes whether a block is *explainable*, not whether it was *pre-adopted*. Relates to Visible Costs (#9) and Governance Is Structural (#22).

## Removing a mechanism requires removing its name too

When deprecating or removing a mechanism, grep for the mechanism's **name** in active prose and update terminology in the same change — not in a follow-up cleanup. Because lingering names mislead readers into looking for code that doesn't exist; the resulting confusion is worse than not removing the mechanism at all. The "fingerprint" tree-hash freshness mechanism was removed pre-v1.4, but the word survived in 5 active sites (shebang docs, docstrings, lockstep build-governance prose) until Chunk 10 caught them — a year of reader-confusion gap. Fix-shape: each PR that removes a mechanism includes a `grep -rn` pass for its name(s) across `tools/`, `templates/`, `methodology/`, `agents/` and updates each hit to either describe what replaced it or annotate it as historical. **Caveat (v2.0.0 Chunk 13): you can only remove the name from a path once the mechanism has actually LEFT that path.** A mechanism kept deliberately alive for un-migrated consumers — a frozen "live service," not dead code — correctly keeps its name on the paths it still occupies. Before deleting a "deprecated" mechanism, verify nothing reaches back to it at runtime (here: file-sync's `tools/`+`templates/` are `MANAGED_FILES` and an un-migrated product's `try_sync()` calls back to this framework's `prawduct-setup.py` every session — a live service). Sweep the name from the *active* path now; gate the still-live path's sweep behind the mechanism's actual removal (Chunk 13 swept the plugin/active path + dropped `agents/`; the `templates/`+`tools/` sweep is deferred to milestone M4, when the engine is finally deleted). Relates to Living Documentation (#3), Close the Learning Loop (#18), and Unnecessary Backwards Compatibility (a live consumer is the opposite case — removal there is a breaking change to be sequenced behind migration).

## Build-plan fields use `**Title Case:**`, not snake_case

When adding a new build-plan field, format the label as `**Title Case:**` (bold, words-with-spaces, colon) — matching `**Type:**`, `**Critic mode:**`, `**Requirements Confidence:**`, `**Acceptance criteria:**`, `**Done when:**`. Snake_case (`foreign_api:`, `coverage_required:`) is the YAML-key namespace in `project-state.yaml`, a different surface. The methodology's prose form must be string-identical to the template's label except for the `**...**` bolding — so the Critic's substring-match finds real plans. Wave 1's F8 conflated the two namespaces (`foreign_api:` in prose, `**Foreign API:**` in template) and the Critic-check substring never matched a real plan. Relates to Coherent Artifacts (#13).

## Build-plan chunk parsers accept `### Chunk N:` AND `## Chunk N (ID) — Name` (BLD-5J8N) — but `regen-views`/`chunks=` still key on the colon Status form

**Superseded 2026-07-18 (BLD-5J8N / PDT-C6R4).** The `verify-chunk-refs` chunk-id/section parsers were historically hardwired to the colon form: they isolated the id via `rest.split(":",1)[0]`, so an em-dash separator (`### Chunk N — Name`) or the research-plan form (`## Chunk N (ID) — Name`) made the *whole string* the "id", matched no heading, and — worse — surfaced as a generic exit-1 "chunk not found" indistinguishable from a real missing deliverable, so reviewers learned to hand-wave the exit (false-negative habituation) and a real dropped-deliverable BLOCKING could hide behind it. Now the shared `lib/buildplan_refs.py` primitives (`_chunk_section_lines`, `_chunk_id_from_item_text`, `_current_chunk_id_from_status`) match both H2/H3 headings with a `:`, `—`, `–`, `-`, or `(` after the id via `_CHUNK_HEADING_RE`/`_CHUNK_ITEM_RE` — the id MUST be followed by a separator/paren/EOL, so a notes sub-heading like `### Chunk 2 build-session decisions` (no separator) is NOT mistaken for a chunk boundary. This fixes `verify-chunk-refs` (Goal-2) AND `infer-critic-mode`'s chunk-type/current-chunk lookup (they share these primitives — the GOV-8N4V facet), and `cmd_verify_chunk_refs` now emits a distinct `cannot-verify:` (gate could not run) message vs `missing-ref:` (a named deliverable is absent), so the two are never conflated. Leading-zero tolerance is preserved (`1` matches `### Chunk 01:`). Guard tests: `tests/test_buildplan_walkers.py::TestH2ChunkHeadingForm`/`::TestChunkIdFromItemText`.

**Still true — the residual colon dependency.** `regen-views`'s `CHUNK_LINE_RE` (in `lib/views.py`) is a SEPARATE parser for the `## Status` checkbox LINES and was NOT broadened here, and the `chunks=`-tag→Status-line match is *literal* (no leading-zero tolerance — `Chunk 1` ≠ `Chunk 01`). So a plan whose Status LINES use the em-dash/colon-less form can pass the gates yet fail to flip its checkboxes at merge. Tracked as follow-up VWS-2F9K — until it lands, keep `## Status` checkbox lines in the `- [ ] Chunk NN: Name` colon form even when the Build-Chunks headings use the H2 research form. Sibling of "Build-plan fields use `**Title Case:**`" — build-plan text is a contract with the parsers. Original silent-failure discovered v2.0.0 Chunk 1 Critic; broadened 2026-07-18. Relates to Coherent Artifacts (#13), Escape hatches create silent failures (#22), and Honest Confidence (#5).

## Submodule and same-name function in __init__ shadow each other

When a `lib/__init__.py` does `from .foo import foo` (re-exporting a function whose name matches its submodule), attribute access `lib.foo` returns the function while `sys.modules['lib.foo']` still holds the module — `import lib.foo as alias` resolves to one or the other depending on context, and `monkeypatch.setattr(alias, "name", ...)` raises `AttributeError` when it lands on the function. Because Python's `from package.submodule import name` registers both in the parent's namespace; the later import wins for attribute lookup. Fix-shape: use the `_cmd.py` (or other) suffix that every other lib module already uses (`migrate_cmd.py`, `sync_cmd.py`, `init_cmd.py`, `validate_cmd.py`, `views_cmd.py`) — the convention isn't aesthetic, it prevents this collision. Caught in Chunk 13 when test monkeypatches failed; renamed `audit_learnings.py` → `audit_learnings_cmd.py` before commit. Relates to Coherent Artifacts (#13) and Reasoned Decisions (#4).

## Detection of structural characteristics should not rely on mechanistic surface markers

When classifying whether a project has a structural characteristic (uses LLM inference, has human interface, runs unattended, sensitive data, multi-process), use *what the project's correctness depends on* — not surface markers like import statements, hostnames, or filename patterns. Because surface markers miss cases where the same structural feature manifests differently. Prawduct's own Open 1 empirical-detection survey initially classified itself as "not LLM-using" because the framework's executable code has zero LLM SDK imports, zero LLM-API hostnames, and zero message/role/tool-use shapes — but the framework's primary deliverable IS prompts (skill markdown files loaded by an external Claude Code runtime), so its correctness fundamentally depends on LLM behavior. The mechanistic test missed Category B (runtime-instruction) projects entirely until the user surfaced the gap. Fix-shape: every structural-characteristic detector answers "what determines correctness here?" first, then lists surface signals as *evidence* for that structural question — not as the question itself. The distinguishing feature for the LLM case turned out to be "prompts-as-code (Python builds API request bodies) vs prompts-as-content (markdown loaded by an external runtime)" — both correctness-depends-on-LLM, neither captured by SDK enumeration. Discovered 2026-05-28 during prompt-management v0.1 → v0.2. Relates to Structural Awareness (#21), Honest Confidence (#5), and Bring Expertise (#7).

## Shared "answer" state and personal "nag" state belong in separate stores

When designing state about ongoing concerns (advisories, follow-ups, todos), separate two semantically distinct kinds of state: the *answer to the question* (committed, team-shared — e.g., `project-state.yaml`'s `uses_llm_inference: true`) and *have I personally dealt with this nag?* (gitignored, per-clone — e.g., `.advisories.json`'s dismissed list). Because conflating them gets both directions wrong: either everyone's dismissals leak across clones (personal task state shouldn't propagate to teammates) or no resolution propagates (when a teammate's commit answers the structural question, the answer should auto-clear the nag for everyone on next pull, not require each developer to dismiss separately). The post-sync advisory infrastructure (`documentation/post-sync-advisory-spec.md` v0.2) made this explicit: probes declare both a *trigger condition* (reads code state — "should I ask?") and a *resolution condition* (reads `project-state.yaml` — "has the team answered?"); active state lives in the gitignored nag log, settled facts live in the committed answer store. Discovered 2026-05-28 via Q2 in the advisory spec when the naive single-store design would have produced wrong cross-clone behavior. Generalizes beyond advisories — any feature that tracks "did the team agree on X?" + "have I personally followed up?" benefits from this separation. Relates to Coherent Artifacts (#13) and Structural Awareness (#21).

## Framework ownership follows the write strategy, not just registry membership

When defining "the framework owns this file" sets — for auto-commit, hash-based change detection, or "is this user WIP or framework drift" partitioning — the discriminator is *whether the framework overwrites the file on every run*, not "is the file in any registry the framework knows about." Template / block-template / always-update / merge-settings strategies overwrite each sync; place-once strategies create once and never re-touch. The two have opposite ownership semantics after first creation, even though both lists live side-by-side in `core.py`. Because Chunk 11's first-pass `_framework_known_paths` included `PLACE_ONCE_TEMPLATES` and `PLACE_ONCE_COPY` (`.prawduct/change-log.md`, `.prawduct/backlog.md`, `tests/conftest.py`), a user chunk-close append to change-log.md would have been swept into the auto-commit's `chore(sync):` marker — re-creating the exact co-mingling F5a aims to prevent. Fix-shape: when building "framework-managed" sets, derive them from the *strategies that overwrite* (the manifest's `files` dict, sourced from `MANAGED_FILES`), not from "every path the framework has ever placed." Place-once is genuinely place-once — trust the contract. Relates to Reasoned Decisions (#4) and Coherent Artifacts (#13).

## A leftover marker is not an in-progress signal — and a test using the canonical marker leaves the real-world branch untested

When detecting external-tool state from filesystem markers (a `.git/` ref, a lockfile, a PID file), check whether the tool *removes* each marker when the condition ends — a leftover artifact is not an in-progress signal. `_git_op_in_progress` treated `.git/REBASE_HEAD` as a live rebase, but git does **not** clean up `REBASE_HEAD` when a rebase ends (it lingers until the next rebase overwrites it), unlike `MERGE_HEAD`/`CHERRY_PICK_HEAD`/`REVERT_HEAD` which git *does* remove — so the stale ref produced a phantom "rebase in progress" on every downstream session and could block auto-sync. Prefer the tool's own authoritative test: the `rebase-merge`/`rebase-apply` directory check (what `git status` uses) was already present and correct; the ref check was a redundant false-positive source. Two compounding lessons: (1) the existing regression test simulated a rebase with the `rebase-merge` *directory* — it passed via the correct branch and never exercised the buggy `REBASE_HEAD` *file* branch, so the bug only ever fired in the real world; when a detector has multiple input paths, test each one with the messy inputs real systems produce (leftover refs), not just the clean canonical marker. (2) The misdetection was cached into `.prawduct/.sync-pending` and replayed verbatim every session, turning a one-time false positive into sticky noise — a derived/cached blocker that never re-evaluates makes any transient false-positive permanent. Discovered 2026-06-01 from a Hallucinote bug report. Relates to Tests Are Contracts (#1), Root Cause Discipline (#16), and Honest Confidence (#5).

## A near-verbatim file PORT carries the source's prose — adapt the docs, not just the logic

When you create a new file by copying an existing one and surgically adapting it (the design-blessed "duplicate during coexistence" pattern — e.g. `tools/product-hook` → plugin `bin/prawduct-hook` in v2.0.0 Chunk 5), the copy inherits every docstring, comment, and user-facing message from the source — and those describe the SOURCE's world, not the new one. After adapting the logic, do an explicit doc-sweep: grep the copy for terms that were true only of the source (here: "trigger sync", "needs tools/lib", "run a framework sync", `python3 tools/product-hook` tool forms) and repoint them to the new context. The Chunk 5 Critic's one WARNING was exactly this — the logic was correct and tests passed, but the inherited prose lied (it claimed the plugin syncs and that lib might be absent, when the plugin never syncs and always bundles lib). EXCEPTION: leave verbatim any string that is a cross-file CONTRACT (the `final|fallback-no-tools-lib` token the critic skill prose matches on) — renaming it silently breaks the consumer. Fix-shape: treat a copy-port as logic-adapt PASS + doc-sweep PASS, two passes, before declaring done. Discovered v2.0.0 Chunk 5. Relates to Living Documentation (#3), Coherent Artifacts (#13), and The System Can Be Understood (#6, accurate diagnostics).

## Verify the platform's copy/packaging boundary before duplicating a shared bundled file — a prior "duplicate into each consumer" choice may be an unverified-constraint workaround

Before deciding whether to DUPLICATE a shared file into each consumer dir vs. REFERENCE one canonical copy, verify the platform's file-resolution/packaging boundary — and don't cargo-cult an earlier duplication decision made when that boundary was unverified. In v2.0.0 Chunk 4 the Critic/PR protocols were COPIED into each skill's own dir (`skills/critic/review-protocol.md`) and referenced via `${CLAUDE_SKILL_DIR}/…` — the safe move *then*, because Claude Code's plugin-install copy semantics were unverified. Chunk 6 needed the same call for `methodology/`. Rather than inherit the duplication, I verified (claude-code-guide → plugins-reference "path traversal limitations"): a marketplace install copies the WHOLE plugin tree — the boundary is the PLUGIN ROOT, and only traversal *outside* it fails. So `methodology/` stays ONE canonical source at plugin root, read by hooks via `${CLAUDE_PLUGIN_ROOT}/…` and by skills via in-plugin `${CLAUDE_SKILL_DIR}/../../methodology/…` (a traversal that stays inside the root) — no copies, no parity test, no drift surface. Note the two valid in-plugin read paths: `${CLAUDE_PLUGIN_ROOT}` substitutes in HOOK commands and bash-injection/subprocess env but NOT in skill PROSE; skill prose gets `${CLAUDE_SKILL_DIR}`, so a skill reaches a plugin-root file via `${CLAUDE_SKILL_DIR}/../../`. Fix-shape: when a duplicate-vs-reference decision recurs, re-verify the constraint that motivated the earlier choice — single source of truth beats a parity-tested copy whenever the platform actually guarantees the canonical file ships. Discovered v2.0.0 Chunk 6. Relates to Validate Before Propagating (#15), Reasoned Decisions (#4), and the DRY/no-unnecessary-duplication design goal (Critic Goal 7).

## Dogfooding the generator on its own output masks output-relative bugs the real consumer would hit

When a generator/framework repo runs its OWN output (here: the framework governed by its own plugin via `--plugin-dir .`), paths relative to the generator's tree resolve fine — because the generator's checkout HAS them — so the dogfood passes while the same artifact breaks in a real consumer that lacks those paths. v2.0.0 Chunk 11: the plugin's critic skill read `docs/principles.md` repo-relative and hardcoded "This is the Prawduct framework itself, not a product repo"; both are correct in the framework checkout and wrong/broken in any product repo, and a `--plugin-dir .` run here would never expose either. Therefore "self-contained / no external files needed" must be proven by (a) a STATIC audit of the artifact for tree-relative reads, and (b) a run against a tree that genuinely lacks the generator's source (a real consumer, or a stripped copy) — never by the generator dogfooding itself. Discovered v2.0.0 Chunk 11 (the real-consumer proof is Chunk 12 — hallucinote). Relates to Validate Before Propagating (#15) and Honest Confidence (#5).

## Relocating a source file: sweep every READER of the old path, not just the data-key references

When you move a source file (`git mv A → B`) and repoint the engine that reads it, the migration is not done until **every reader of the old path** is swept — including test content-assertions that `read_text()` the old path and fixtures that write/read it, not only the structural/manifest references that name the path as a data key. v2.0.0 Chunk 14 relocated 6 file-sync skill sources `.claude/skills/<n>/SKILL.md → templates/skill-<n>.md`; validating the hardcoded template-*value* assertions and existence checks all passed, but **5 failures + 8 errors** surfaced on the first full-suite run from tests that read the framework skill *content* by path (and a fake-framework fixture that *wrote* the old source path). Grep the old path for `read_text` / `open` / fixture writes, not just for the path string used as a dict key. The content was byte-identical at the new home, so every repoint was a one-line path swap — but they had to be found. Relates to Validate Before Propagating (#15) and Living Documentation (#3).

When moving a source file, sweep EVERY reader of the old path — grep it for `read_text` / `open` / fixture writes, not just the path string used as a data key; content-assertions and fixtures that touch the old path surface only on the full-suite run. **The sweep re-triggers at every MERGE, not just at move time:** merging an integration branch into a feature branch that renamed/packaged a module can import NEW readers of the old path that didn't exist when the move was done (here: `lib/norm_probes.py` arrived from develop importing the pre-move `from .backlog import …` API after Chunk 01 moved the parser to `.backlog.legacy`; the full-suite collection error caught it). After such a merge, grep the merged-in tree for the old import/path before trusting green.

**Readers are not only code — and the non-code readers are the ones the suite cannot see (recurrence 3, 2026-07-21, escalated).** The `plugin/` relocation merge left `bin/prawduct-hook` in five skills' *instruction prose* and, worse, in their `allowed-tools:` **permission grants** — so the documented command could not run and the grant did not cover the one that would. A green full suite proved nothing, because no test executes a skill's front-matter. Same merge, same class, third occurrence. The sweep surfaces, in the order they fail silently: `allowed-tools:` grants → skill/methodology prose → durable planning artifacts (`.prawduct/artifacts/**` — release plans and build plans a future session reads as current instruction, which is DOC-2R7M) → docstrings (lowest stakes; often correct to leave). The packaging boundary test verifies file *location* and is blind to path *references*; closing that asymmetry is the structural enforcement this recurrence earns (BLD-6P8T). Relates to Validate Before Propagating (#15) and Living Documentation (#3).
## A review's "inert / harmless" verdict on a latent bug is conditional on the current call graph

When review judges a latent defect "inert" or "harmless" *because nothing currently exercises the broken path*, treat that as "inert **for now**", not "safe to leave forever" — the next feature that touches the dormant path makes it live. v2.0.0 Chunk 14: the relocation Critic correctly flagged the plugin `lib/core.py`'s byte-parity `FRAMEWORK_DIR = parent.parent.parent` mis-resolving one level too high (it sits at `lib/`, not `tools/lib/`) as inert — and it WAS, until the very next chunk's scaffolder became the first plugin code to render `templates/` at runtime via `core.TEMPLATES_DIR`, which crashed (`…/source/templates/...` not found). So: when you write code that touches a path a prior review called inert, re-check the verdict's premise before relying on it. Fix here: resolve `templates/`/`VERSION` from the plugin root (`__file__.parent.parent`), the established `bin/`/`hooks/` pattern — not via `core`'s parity-locked constant. Relates to Honest Confidence (#5) and Root Cause Discipline (#16).

## Excising a subsystem silently kills the incidental work it happened to host — re-home the orphaned call, and test the positive

When you remove a mechanism, audit not just what *calls* it (the name-sweep above) but what *it* called that was not actually part of its purpose — incidental work co-located inside the removed code path dies with it, and no test catches it because the tests assert the subsystem is GONE, not that its side effects survived. v2.0.0 Chunk 5 excised file-sync `sync` from the plugin runtime; the post-sync advisory **probe** step lived inside the sync tail (`tools/lib/sync_cmd.py` → `run_sync_advisories`) but was purely local — it reads the consumer's own `.prawduct/` (backlog.md, project-state.yaml), no network/checkout — i.e. not sync at all, just co-located. Excising sync silently took it: `cmd_clear` hardcoded `sync_advisories = []`, so the probe roster never ran in ANY plugin repo, `.advisories.json` never refreshed, and the `legacy-backlog-format` nudge → `/prawduct:backlog migrate` could never fire (surfaced ~4 months later, as a user's confusion that the plugin cutover didn't migrate their backlog). The port thoroughly verified the NEGATIVE ("no sync": `test_sync_cluster_excised`, `test_clear_does_not_sync_even_with_manifest`) but never asserted the POSITIVE that sync's non-sync side effects were re-homed. Fix-shape: when removing subsystem X, list everything X *did* and split it into "X's actual job" vs "work X merely hosted"; re-home the latter to a surviving call site (here: `cmd_clear` now calls `run_sync_advisories` directly, before the briefing reads the store) and add a regression test asserting the re-homed behavior STILL happens. Directly relevant to the pending Chunk-13 file-sync removal ([MIG-M4-REMOVE]), which excises more of the same engine. Discovered 2026-06-03 (advisory-probe fix). Relates to Root Cause Discipline (#16), Validate Before Propagating (#15), and Complete Delivery (#2 — a capability dropped without a decision is a silently-dropped requirement).

## A "renders-but-doesn't-resolve" leak is a SURFACE, not a line — sweep the whole renderer and assert the bad form is ABSENT

When user-facing output names something that won't resolve in the current context — a bare `/backlog` skill in a plugin repo that namespaces it `/prawduct:backlog`, a stale command form, a renamed token — fix every command-bearing line in the SAME renderer in one pass, not just the one you noticed, and add a test that asserts the WRONG form is ABSENT, not merely that the right form is present. A presence-only assertion (`assert "/prawduct:backlog" in out`) passes happily while a sibling line still emits the bare `/backlog`. In the ADV-3K7Q fix the Critic caught the same leak class in two successive rounds — first the advisory dismiss hint left bare after the migrate action was fixed, then `/backlog to triage` left bare after both advisory lines were fixed — because each patch targeted the flagged line, not `assemble_session_briefing` as a surface. Root cause upstream: v2.0.0 Chunk 13's namespace divergence was driven module-by-module (it diverged `operator_verification`) instead of by enumerating every command-bearing OUTPUT, so `backlog_probes` and three briefing status lines were silently missed and only surfaced when v2.0.2 re-enabled the advisory. Fix-shape: when you touch one occurrence of a context-dependent leak, immediately `grep` the enclosing renderer (and its frozen twin) for the whole leak class, fix all live-context occurrences together, leave the frozen-context twin (the file-sync `tools/` copy) untouched, and pin it with assert-present + assert-absent. Extends the copy-port doc-sweep rule (a copied renderer inherits the source's command vocabulary) and the deprecation name-sweep rule. Discovered 2026-06-03 (ADV-3K7Q). Relates to Coherent Artifacts (#13), Validate Before Propagating (#15), and Complete Delivery (#2).

## An "assert the bad form is ABSENT" sweep is only as good as the pattern that defines the bad form — enumerate the whole FORM-FAMILY, not one spelling

The renderer-surface rule above says grep "the whole leak class." The trap: a frozen-vs-namespaced vocabulary has MULTIPLE spellings of the SAME leak, and a grep that encodes one spelling silently passes over the siblings. Completing ADV-3K7Q's gate-message sweep, I grepped `/(critic|pr|backlog|learnings|...)\b` and cleared every BARE slash-command form from `bin/prawduct-hook` — but that pattern can't match the **hyphenated frozen skill name** `/prawduct-advisory` (the v1 file-sync skill; the plugin form is `/prawduct:advisory`), so a `cmd_advisory` docstring kept emitting it. The Critic caught it — the exact leak class I thought I'd swept, in a spelling my pattern didn't cover. Widening to `/prawduct-[a-z]+` then surfaced a THIRD spelling, the legacy CLI tool `prawduct-setup` (correctly left as a factual historical reference, not a command-resolution leak). Fix-shape: before declaring a namespace/rename sweep done, list every SPELLING the frozen vocabulary uses for the thing — bare `/cmd`, hyphenated `/prawduct-cmd`, legacy CLI `prawduct-setup` — and run one grep per spelling (or a union pattern), because each spelling is a distinct regex the others won't match; then bake the full spelling-set into the absent-assertion's `FORBIDDEN` list, not just the spelling you happened to fix. Discovered 2026-06-03 (gate-message sweep). Extends the renderer-surface rule above; relates to Validate Before Propagating (#15) and Complete Delivery (#2).

## An untested governance bound rots silently across a migration — sweep the guards (with tests), not just the prose

The name-sweep rule above ("Removing a mechanism requires removing its name too") covers prose; its sharper corollary is about *guards*. When a migration removes or relocates a mechanism, the code that **enforces a bound by naming the old shape** rots silently if no test pins it. Two instances surfaced together in the 2.0-rock-solid pass (2026-06-03), both rooted in M4's `agents/`→`skills/` plugin cutover: (1) the trivial/doc-only file-set gate (`_classify_trivial_change`) still bounded `agents/` (deleted) and was **missing `skills/`** — so a `Type: trivial` chunk could edit `skills/critic/SKILL.md` (the Critic's own protocol) without tripping the catastrophic-blast-radius guard; the literal survived precisely because the bound had **zero test coverage**. (2) M4 deleted `tests/test_coverage_gaps.py`, which carried the only `_SESSION_GITIGNORED_PATHS`↔`GITIGNORE_ENTRIES` parity test, while leaving comments that still cited it as live — so the two mirrored lists could drift undetected. Fix-shape: when a migration removes/relocates a mechanism, enumerate the **guards** that referenced the old shape (path bounds, allowlists, parity tests, prefix tables) and (a) repoint them to the new shape, (b) add the regression test if it was missing, or (c) **restore** a deleted guard rather than deleting its now-dangling references — deleting a reference to a guard that *should* exist hides the gap instead of closing it. A guard with no test is the thing most likely to carry a stale literal through a cutover. Discovered 2026-06-03 (waiver-pragma / 2.0-rock-solid pass; gate fixed test-first, 12 new tests; parity test restored). Relates to Tests Are Contracts (#1), Root Cause Discipline (#16), and "Removing a mechanism requires removing its name too" (the prose sibling of this rule).

## In a leaf-first decomposition, dependency-scan a chunk's COMMAND bodies against later-chunk symbols before moving — and never move a parity-pinned mirror just because a deliverable lists it

A leaf-first module extraction (move module N only after the modules it depends on) is safe for *leaf helpers* but has two traps when a chunk also moves *command bodies* or *named functions* — both surfaced in STH-9V4K ch.5 (`lib/coverage.py`), and the build plan was wrong on both. (1) **A command body can reach UP the DAG even when its helpers move down it.** The plan assigned `cmd_verify_coverage` + `cmd_check_cumulative_critic` to the `coverage` chunk, but an AST scan of their bodies (run BEFORE editing) showed they call `_validate_evidence_schema` / `validate_critic_findings` / `_CRITIC_MODE_CUMULATIVE` — all symbols assigned to the LATER `gates` chunk. With the DAG `coverage ← gates`, moving them into coverage would be a `coverage → gates → bin` back-import. Fix: defer those two commands to the `gates` chunk (where `gates → coverage` is legal); their shared helpers still move down. (2) **A function carrying an explicit mirror/parity contract stays put regardless of the deliverable.** The plan listed `_read_bool_yaml_key` to move + "repoint test_views.py", but its def was annotated `# intentional inline mirror (import-light hot path); pinned by TestBoolKeyCallSiteParity` and a test class pins it to `lib.core.read_bool_yaml_key` — the same class as `_read_str_yaml_key`, which the plan's Out-of-scope keeps in the hook. The plan's Out-of-scope merely forgot this sibling mirror. Moving it would break the parity test and regress the import-light invariant. Fix-shape, now part of the move ritual for every remaining chunk (6, 7): before moving a chunk's symbols, (a) AST-scan each moved *body* for references to symbols slated for any LATER chunk — if found, defer that body to the chunk that owns those symbols; and (b) grep each moved def's surrounding comment + the test suite for `mirror` / `*Parity*` / `import-light` — if pinned, it stays in the hook even if the deliverable lists it. Both checks are cheap and both caught a real plan defect here. Discovered 2026-06-07 (STH-9V4K ch.5). Relates to Validate Before Propagating (#15), Requirements Precede Code (#6 — the plan is the parent; correct it, don't silently follow or silently deviate), and Reasoned Decisions (#4).

## A format's schema legend lives in `templates/` (scaffold-only) — adding an optional field reaches already-onboarded repos only via a migrate/triage *refresh* step, not the template

When you add an optional field to a structured-file format (here the backlog: `stage:`/`refs:`/`accepted-by:` in v2.0.15), there are **two** propagation surfaces that drift independently, and it's easy to wire only the first: (1) the **per-item** backfill — the triage/`migrate` step that writes the new field onto existing items; and (2) the file's **schema legend** — the `<!-- … -->` header comment that documents what each field means. The legend is authored **once at scaffold time** from `templates/backlog.md` and is never re-applied to an already-onboarded repo, so a product that adopts the new field ends up with backfilled items behind a legend that never documents them — a reader hits `stage: ready` on an item with no key explaining it. `../scriob` hit exactly this (2026-06-08): their grooming pass backfilled `stage:` but the legend still didn't mention `accepted-by`, and they had to hand-patch it. Root cause is the same shape as [[a new build plan with scope null inherits another scope's shipped checkbox flips]]'s tail ("the warning lives in a template comment that from-scratch authors don't see, so it keeps recurring") — **anything that lives only in `templates/` is scaffold-only and does not reach onboarded repos**; the universal carriers are `migrate`/triage (for backlog.md) and `methodology/session-digest.md` (for default-behavior changes). Fix-shape: when adding an optional format field, wire BOTH surfaces — the per-item backfill AND a legend-refresh step in `migrate` that reconciles the header to the canonical field set (additive/non-destructive: fill missing canonical-field docs, never remove a repo's local extension like a `kind:` facet). Self-check when shipping a format addition: "a repo onboarded *before* this field existed runs `migrate` — does its legend end up documenting the field?" If no, the legend-refresh step is missing. Fixed in `skills/backlog/SKILL.md` migrate step 4c + `documentation/backlog-system-requirements.md` §8.4. Discovered via scriob (2026-06-08, develop). Relates to Living Documentation (#3), Coherent Artifacts (#13), Complete Delivery (#2), and [[a new build plan with scope null inherits another scope's shipped checkbox flips]].

## A structural bound that ENFORCES a declaration is not a DETECTOR of the declared property — reusing it at a new boundary silently drops its justification

When you reuse a structural predicate at a second boundary, re-derive *why it's valid there* — don't assume the justification travels with the code. A bound can be a **necessary** condition that *enforces* an explicit declaration ("you declared this chunk `Type: trivial`; therefore its files must stay within these paths") without being a **sufficient** condition that *detects* the declared property ("these files are within the paths, therefore the work is trivial"). The `Type: trivial` fileset bounds (`_classify_trivial_change` / `_TRIVIAL_PROTECTED_PATHS`) were designed as the *enforcement* of a per-chunk declaration — the stop hook checks them **only when `chunk_type == "trivial"`**. The PR-boundary `check-pr-trivial` / `_pr_diff_is_trivial` reused the *same bounds* with no link to any declaration, so it became a *detector*: a multi-chunk **feature** that only modified existing files cleared the fileset and was reported `trivial`, skipping BOTH the cumulative-Critic gate and the independent PR reviewer (the two core review gates). The skill text even admitted the sufficient condition was elsewhere — *"trivial is a semantic claim, validated per-chunk by Critic Goal 3"* — but nothing checked that claim at the bundle boundary, so a necessary condition silently stood in for a sufficient one. Compounding it: the fast-path shipped with **zero** test coverage at the PR boundary — a **skip-gate (a gate whose job is to waive other gates) needs the *most* adversarial coverage, not the least**, because its failure mode is invisible (work sails through). Discovered 2026-06-08 (incoming-bug from scriob); user chose to retire the PR-boundary fast-path entirely rather than gate it on the declaration (the doc-only fast-path — all-`.md` = no code — stays, because *that* predicate is genuinely sufficient at its boundary). Fix-shape: when a predicate moves to a new boundary, write down the sufficient condition for the *decision being made there* (here: "skip review") and confirm the predicate actually establishes it — if it only establishes a necessary precondition, either gate on the real (declared/semantic) signal or don't make the decision automatically; and give every skip-gate a regression test that asserts a non-eligible case still BLOCKS. Relates to Reasoned Decisions (#4), Validate Before Propagating (#15), Governance Is Structural (#22), Tests Are Contracts (#1), and [[an untested governance bound rots silently across a migration]].

## A rebuild scoped to a subsystem's "remaining / deferred" parts silently omits an already-shipped part that was deleted in between — re-port against the spec roster, not the open-work list

When you rebuild a subsystem in a new home, enumerate what it is *supposed* to contain from the **specification**, not from the **open-work backlog** — because a backlog framed as "the *remaining* N" silently assumes the already-shipped part still exists, and if a migration deleted that part in between, the rebuild reproduces only the remainder and the primary member vanishes with no error. The post-sync advisory backlog roster is spec'd (`backlog-system-requirements.md` §8.2) as **four** probes; `legacy-backlog-format` (the `/prawduct:backlog migrate` nudge — trigger: `backlog.md` has >5 items, none carrying a `[PFX-XXXX]` id; resolution: `backlog_format_version: 2`) was the **single production probe** shipped in v1.7.0, and `[BKL-2F7K]` tracked only "ship the three *remaining* §8.2 probes." M4 (v2.0.3) then deleted the file-sync `tools/lib/backlog_probes.py` **with the engine** — taking the primary probe. The v0.3 backlog rework built a new plugin-native `lib/backlog_probes.py` scoped to `[BKL-2F7K]` (the three deferred probes) and assumed the primary one already existed — so `register()` registered three and never re-ported `legacy-backlog-format`. The roster ran (the grooming probe fired in real briefings, which is exactly why the absence *looked* fine — the channel was alive, just missing one member), but the migrate nudge could never fire. This is the **second chapter** of [[excising a subsystem silently kills the incidental work it happened to host]]: chapter one re-homed the advisory *infrastructure* (so the roster runs); this chapter is the *member* that the infra was always about, still missing because the rebuild's scope inherited a "ship the rest" framing that predated the deletion. Surfaced 2026-06-08 as a user's report that updating the plugin didn't nudge their backlog to migrate. Fix-shape: when rebuilding/porting a subsystem, list its members from the spec/requirements roster and diff that against what the new module actually registers (here: a `register()` that names every spec'd probe; an end-to-end test that drives the *registered* roster, not just each probe in isolation, so an unregistered member fails a test); and when a deletion lands between a feature's spec and its build, re-confirm the baseline the feature's scope assumes still exists. Relates to Complete Delivery (#2 — a member dropped without a decision is a silently-dropped requirement), Root Cause Discipline (#16), Validate Before Propagating (#15), and [[removing a mechanism requires removing its name too]] (its inverse: this is *rebuilding* requires rebuilding the whole roster).

## A persisted schema's requirements are its consumers' future queries — lock-in is reversal cost, not LOC, so "small format" never exempts it from decision research

The decision-research trigger list already names **lock-in** as a research trigger, but lock-in gets mis-sized when judged by implementation effort: a 10-line JSONL writer with the wrong shape is HIGH lock-in (every line written in the old shape is a migration liability), while a 500-line refactor behind a stable interface may be none. The 2026-06-10 review-proportionality plan hit this exactly: the governance ledger was first designed mechanism-first ("append review records to a file") and marked **High confidence** — but the cheapest discovery question for any data product, *"what questions must this data answer over time?"*, was never asked. The user's unprompted analytics requirements (model efficiency per ROLE, findings density per code path, wall-clock per phase per feature, cross-project aggregation) restructured the schema from review-shaped to an event-envelope shape — a structural choice that retrofitting after lines exist would cost a migration. A second trap rode along: user **endorsement of an analysis/diagnosis is not a requirements confirmation for the artifacts that implement it** — "this is fantastic, build all five" confirmed the cost diagnosis, not the data product's spec. Fix-shape (and the methodology tripwire shipped with review-proportionality ch.01): a chunk introducing any persisted format/schema/ledger must enumerate, in the plan, the questions the data must answer — elicited from its future consumers (usually the user), not inferred from the mechanism — before designing fields; and judge every lock-in trigger by reversal cost, never by LOC. Cheap accommodations that make this survivable when a question is missed anyway: per-line `schema_version`, envelope/payload split, consumers skip unknown kinds/fields, a structural single-writer (validate at append) instead of prose-instructed serialization. Caught at plan stage by the user, before any code — which is the plan-review layer working, but the elicitation should have happened at authoring. Relates to Requirements Precede Code (#6), Reasoned Decisions (#4), Bring Expertise (#7 — the builder should have asked), and Honest Confidence (#5 — "High" meant mechanism-confidence, not requirements-confidence).

## Verify a review artifact's cited gaps against HEAD first — its file-state claims aged the moment it was written, some were never true. A `file:line` you did not resolve yourself is a claim, not a citation: its precision reads as evidence of having been read. Anchor on symbols and headings, not digits — one that visibly breaks gets fixed; one still arithmetically valid under a rewrite never does

**Instance (2026-07-28, v3.2.0 Chunk 05c / BKL-72AS) — the inherited-`file:line` facet, where the
claim was never true rather than stale.** Resuming from a prior session's analysis, two of its
load-bearing details were wrong, and the *shape* of the error is the lesson.

(1) It enumerated three copies of the id-shape regex and named `migrate.py:585` as the third. 585
is a **consumer** of `is_pfx`; the real third copy was `_ID_MARKER_RE` at `migrate.py:67`. Shipping
the widening without it would have been worse than not shipping it — the parser would mint the alias
while the title kept its `[MIG-M4-REMOVE]` marker, so every affected item imports with a malformed
title. The enumeration had been done by reasoning about *which modules matter* instead of grepping
the character-class fragment; one `grep -rn "A-Za-z0-9" --include="*.py" --include="*.md"` found all
four in seconds. **Enumerate a shared shape by its bytes, never by recalling its consumers.**

(2) It explained the blocked escape hatch as "`core.py:933` filters `id_aliases()` through
`is_pfx`." I filed that into a backlog item and a build plan **before** resolving it. The path was
wrong (`plugin/lib/core.py` is 386 lines; the real site is `plugin/lib/backlog/core.py:933`) and so
was the mechanism — that filter governs alias *read-back*. The actual reason is stronger:
`verify_migration` derives `unaliasable` at `migrate.py:1163` from the **source parse alone** and
never reads the target, so no issue-side action clears it for any id of any shape. Verifying it also
turned up a second, larger defect: the runbook's step-6 remedy told operators to hand-add an
`id:PFX` label — which can never clear the exit-4 — and had been contradicting the code's own remedy
string (`migrate.py:1212-1219`) all along.

**Why it survived:** a `file:line` reads as evidence that someone opened the file. Precision is not
provenance. The claim was doing real decision work — it was the argument for why widening beat the
alternatives — so an unverified premise was carrying the decision. This is the inverse of the known
"delegated verification inherits your frame" trap: here I inherited *someone else's* frame, and its
specificity is what made it credible. Both resolve to the same discipline — the premise is the thing
you must check yourself, whichever direction it arrived from. Self-review before the Critic caught
the same wrong mechanism a third time, already written into a durable source comment in `ids.py`.

Relates to [[Correcting a false claim is authoring a new claim — verify the replacement and the
artifacts it cites, because the fixing mood generates claims faster than the checking reflex fires]],
Validate Before Propagating (#15), and Retrieval Over Generation (#24).

Full context (2026-07-02, gate-noise / GOV-7T2M, Wave 1 Plan A of the efficiency-review fix
program): The parent artifact `framework-efficiency-review-2026-07-02.md` carried two claims
that were wrong by build time. (1) "residual gap: review protocols still let reviewers eyeball
staleness" — but PR #104 (2026-06-22, TST-4K2P cluster) had added "that exit code is the *only*
freshness signal" to both `skills/critic/review-protocol.md:41` and `skills/pr/review-protocol.md:56`
ten days before the review was written; the audit agents missed it. Found via
`git log -S 'freshness signal'` on the cited files before planning. Descoping it avoided adding
a duplicate line to a protocol sitting at its 3350-token ceiling. (2) The literal instruction
"drop refactor/rename/redesign/rework/remove/replace from REQUIREMENT_VERBS" ignored the set's
second role: `find_orphan_terms` exempts these verbs from being reported as orphans, and a
3-line probe showed rename/redesign/rework are NOT absorbed by the `_in_floor` frequency floor —
a bare drop would make "rename the FooBar module" report *rename* itself as the orphan (a brand-new
false-positive class in a fix whose whole purpose was killing false positives). The fix became a
two-set split (REQUIREMENT_VERBS for requirement-shape, MAINTENANCE_VERBS added to the orphan
exemption union). Why it matters going forward: ~13 more backlog items point at this same parent
artifact (waves 1-3); every one of them should re-verify its cited file:line evidence and
empirically probe the predicate it changes before planning. The artifact remains the requirement's
*evidence and rationale*; it is not a statement of current file state nor a validated design.

## When a plan sets a quantitative reduction/size floor over a corpus you cannot shrink by dropping content, derive the floor from a per-file compressibility sample — not a global intuition

Context: the prose-diet feature (MET-3Q8V) targeted the ~37k est-token governance cycle-load
set. The build plan's Success clause set a floor of ≥45% reduction, targeting 50%, alongside a
hard no-drop constraint (no rule, gate semantics, or checkable bar may be lost — Complete
Delivery outranks the number). The 45–50% figure came from a global intuition that priced
*triplication* — the mode×type matrix and stance prose repeated across three surfaces — as the
bulk of the mass.

What actually happened across three chunks: structural single-sourcing + editorial compression +
folding five instruction surfaces landed the corpus at 36,991 → 25,789 est tokens, **−30.3%**,
measured with the test suite's `words × 1.3` estimator. The cumulative Critic flagged this as
BLOCKING against the ≥45% floor. Root-cause, chaining the whys: (1) single-sourcing the
triplicated matrices recovered only ~3–4k est tokens, not the assumed bulk — the repetition was a
small fraction of total mass; (2) the corpus's true composition is rule-dense — single-statement
rules, irreducible behavior tables, and deliberate weaker-model anchors that the no-drop
constraint forbids compressing further; (3) ~2.6k est tokens of in-set two-reviewer chain
machinery had already been carved out to a separate backlog item (review Overbuilt #4) by the plan
itself; (4) the same review program had earlier certified `review-protocol.md` already lean —
evidence the 50% prior had ignored.

Resolution: the owner chose to amend the Success floor to the honest achieved −30.3% rather than
direct a further compression pass (whose realistic yield was ~3–5 more points, approaching rule
loss). This confirmed the provisional lesson recorded at chunk close: a reduction floor set above
honest reach, over a corpus with a no-drop constraint, is not a stretch goal — it is a latent
Complete-Delivery violation that detonates at close-out, when the only ways to "hit the number"
are to drop a load-bearing rule or to miss your own acceptance criterion. The number is a
*measurement of rule density*, not a measure of remaining waste.

The cheap prevention: before writing a quantitative reduction floor under a no-drop constraint,
take a per-file compressibility sample — pick 2–3 representative files, estimate honest achievable
compression on each (what's redundant vs. what's irreducible rule text), and derive the corpus
floor from that bottom-up estimate. Record the floor as a vetoable assumption with its derivation,
not as an aspiration handed down from a global "should be halvable" feel. Relates to Complete
Delivery (#2 — the number must never outrank preservation), Reasoned Decisions (#4 — a floor needs
a derivation), Honest Confidence (#5 — distinguish a measured estimate from an intuition), and
Proportional Effort (#11 — a sampling step is cheap insurance against a close-out trade-off).

## When a governance checkpoint verifies a required side-effect happened, put it OUTSIDE the control flow that produces the side-effect — a check inside the fallible flow can't catch that flow's own skip

**Context (critic-persistence-redesign, 2026-07-09/10).** Claude Code v2.1.198 flipped Agent
subagents to background-by-default. The Critic's final/cumulative coordinator was a `context: fork`
skill that dispatched 3 reviewers and *resumed inline* to persist (write findings → ledger anchor →
critic-end). Under background-by-default the fork returns before the resume, so the writeback never
ran: reviews were silently lost, surfacing only later as a check-cumulative-critic deadlock (CRT-9K7T).

**The trap.** A prior hardening (gate-friction-batch Chunk 03) added a HEAD-coverage assertion
INSIDE critic-end. But the failure mode is "critic-end never reached" — so the assertion, living
inside the flow that fails, could never fire on that flow's own failure. Verifying persistence at
the skippable step is worthless when the step is skipped.

**The fix (Option A).** Decouple model judgment from deterministic persistence:
1. The floor is OUTSIDE the flow — a lingering `.critic-active` marker caught at session end
   (a state critic-end would have cleared). This is Chunk 01, built first, on purpose.
2. Persistence is a pure function of durable on-disk state — reviewers write partials; a
   deterministic, idempotent, fail-closed `critic-consolidate` merges them (NO model in the write
   path), so no fork/background/resume behavior can bypass it.
3. Event-driven fast path (SubagentStop → consolidate) for latency, but the session-end backstop
   is the enforcing floor — a two-tier design that degrades gracefully if the fast path misfires.

**Process notes worth keeping.**
- Verified the post-cutoff harness facts (background-by-default date, SubagentStop existence,
  plugin `agents/` auto-discovery, agent-type/matcher semantics) via `claude-code-guide` + empirical
  reasoning, NOT recall — the whole fix hinged on facts recall would have gotten wrong.
- Honest limitation (Principle 5): the harness firing the SubagentStop hook and resolving the
  plugin `critic-reviewer` agent type can't be exercised until the plugin ships this branch (the
  session runs the plugin from cache, not the working tree). Captured as operator-verification
  VRF-002; the command bodies + consolidation core are exhaustively unit-tested meanwhile. When the
  thing under test is the installed governance machinery itself, "self-validating" needs the fix to
  be *live* first — flag the gap, don't fake the validation.
- Token-budget friction: adding a subsystem's prose to a lean instruction file (review-protocol.md,
  3350-token ceiling) meant RELOCATING record detail to review-cycle.md, not expanding — the
  prose-diet lever, and the budget test earned its keep by forcing it.

## When developing requirements to replace a working system, sweep every consumer's actual usage before finalizing — reported pain is a hypothesis, and the loudest complaint is often not the deepest failure

Full narrative (2026-07-13, backlog-service requirements discovery). The owner asked for
requirements to move the backlog out of git, framing the pain as slow LLM-mediated CRUD, merge
conflicts, and git-coupled edits. All three were real and independently corroborated (BKL-7M4Q
crash corruption; discodon's 454 backlog.md commits with 47 merges / 38 conflict-mentioning
commits; the incoming-bugs drop-box). But a read-only sweep of all 16 local checkouts of the 8
backlog-bearing projects (scriob, scriob2, discodon + 5 copies, hallucinote ×2, cordyceps,
trenchant, puzzles, metallm, prawduct) produced a different ranking:

1. Stale item state / trust collapse — hallucinote hit two `stage: ready` items 60–80% done in
   one session; a scriob scrub found four completed items sitting in Open; an upstream report
   counted three ready items 60–100% shipped; discodon's EVL-D8K2 described a destructive live
   code path as "permanently dead" (dangerously inverted); discodon ran a 48-agent
   assessor+adversarial-verifier workflow over 39 items because item text could no longer be
   trusted. Consumers now re-verify premises in code before building — universally.
2. Stale views across checkouts — the wt-discodon-backlog worktree showed 66 closed items as
   Open and was missing 65 newer ones; discodon-brooks2 held SOL-K3PN found nowhere else.
   Cross-copy divergence was ~98% staleness, ~2% genuine fork.
3. Only then: merge conflicts, unsafe mutation, git coupling — the originally-reported pains.

Consequence: the requirements doc gained a Truth & freshness group (TF1 single live view, TF2
first-class verification stamps, TF3 mass grooming as supported workload) that no tracker
provides out of the box and that the original sketch never implied. Also observed and folded in:
per-project soft vocabularies (scriob's `kind:` on 158 items, `owner:`, `reverted-by:`, stage
values `discovery`/`built`), zero-ceremony tier (metallm: 5 items, no metadata), high-cardinality
ad-hoc ID prefixes (27–58/project), and bulk-read grooming workloads that must be served from a
local cache, not a rate-limited API.

Method notes that made it work: requirements were drafted from the problem BEFORE reading the
vendor research (two parallel web-research agents ran meanwhile), so GitHub/Linear capabilities
informed a separate adopt/build/buy section rather than anchoring the requirements themselves;
and the sweep was one read-only background agent — cheap insurance against designing to the
complaint instead of the disease.

---

## Re-attempting a mechanism rejected for a false-positive class: make it ADDITIVE and relax-only, and separate the framing from the primitive

Context: the deferred kernel-v3 §4 item ("test evidence on the store") had three live frictions —
restart false-stale, doc/metadata-edit re-run, chronic per-session re-run — all rooted in
`tests_are_current` keying freshness on `timestamp >= .session-start` (WHEN the run happened)
rather than WHAT tree it ran against. The obvious fix ("stamp a tree hash, compare it") was the
*exact* direction rejected twice before: the content-hash fingerprint (HEAD SHA + sha256 of dirty
files, v1.3.4→v1.3.8) and `git_sha` (v2.1.8, TST-4K2P) — both rejected for chronic false-STALES,
a standing and explicit rejection (COV-3R9K, kernel-v3 R10, `coverage_algebra.py:66`).

What made the third attempt land where two failed:
- **Additive, relax-only shape.** Not "replace the timestamp with a tree check" but "current iff
  session-fresh OR tree-valid." A disjunction that only moves evidence stale→fresh cannot, by
  construction, produce a false stale — the failure mode of both predecessors. The immunity is a
  property of the shape, not of implementation care.
- **Path-classification, not content-hashing.** The clause diffs two git tree objects
  (`capture_tree` / `tree_diff`) and filters with `is_judgeable_path` — it never hashes file
  bytes, so it honors the standing "paths classify, contents don't" rule. Metadata churn (the
  record's own `.prawduct/.test-evidence.json` write, doc edits) filters out; the verbatim-commit
  case survives because the *judgeable-scoped* tree is preserved even though the raw tree SHA
  shifts when `record` writes the evidence file — the stronger, real invariant.
- **`evidence_tree` is a gate-consumed object, not an eyeball field.** `git_sha` failed partly
  because review agents *read* it and inferred staleness from a lagging SHA. `evidence_tree` is
  only ever consumed by the gate's tree-diff — no human/agent reads it as a position signal.

Build-time refinements the design predicted imperfectly: dropped the proposed `head_tree` field
(no consumer — the clause needs only `tree_diff(evidence_tree, current_tree)`), and excluded
`--from-counts` from capture (hand-typed counts carry no machine tie to the working tree; this
also preserved the standing `test_restamp_flips_stale_record_to_current` contract). Validation
matrix: 11 cases (5 relax-only current, 5 judgeable-change stale, 1 `--from-counts`-stays-stale)
plus 2 monkeypatch fail-toward-stale unit tests; full suite 1727 passed. The env-drift tradeoff
(the incidental per-session re-run that catches dep/flake drift with no file footprint) was
explicitly accepted by the owner as an expensive, undesigned safety net.

A mechanism carrying scar tissue can be viable on a second attempt if you change its FRAMING, not just its implementation — and the check before re-proposing is *what exactly was rejected: the direction or the primitive?* Test-evidence tree-anchoring had been rejected twice (content-hash "fingerprint" v1.3.8, `git_sha` v2.1.8), both as *expiry signals that make evidence go stale*, and both failed as false-STALES (HEAD-SHA baked in; churny metadata hashed between Verify and Critic). The winning reframe was a **disjunction that only ever moves the verdict in the safe direction**: `current iff session-fresh OR judgeable-tree-matches`. Because it can only turn stale→current, never current→stale, it is *structurally* incapable of the false-stale class that killed both predecessors — a property you get from the SHAPE, not from getting details right (which the two prior patches each wrongly believed they had). Separately, distinguish FRAMING from PRIMITIVE: what stayed banned was content-*hashing* (`coverage_algebra`: "paths classify, contents don't"); classifying *paths* via a git tree-diff + `is_judgeable_path` is a different, already-trusted primitive that sits entirely outside the rejection. So: when a diagnosis proposes something with a standing rejection, separate the rejected *direction* (expiry/replace) from the rejected *primitive* (content-hash) — an additive, relax-only, path-classifying clause may be untouched by either. Gate it on a validation matrix that proves the safe-direction-only property BEFORE the schema lands: reasoning the §9 matrix pre-build caught that capturing a tree for `--from-counts` would have flipped a standing restamp contract (stale→current) — the gate doing exactly its job for a lineage where "we believed we'd solved it" had failed twice. Detail in [[learnings-detail]]. Relates to Root Cause Discipline (#16 — fix the failure class, not the instance), Reasoned Decisions (#4), Honest Confidence (#5), Validate Before Propagating (#15), and [[Test-evidence freshness is test-status (session timestamp) ONLY]].
## When validating a CLI's JSON output, feed the tool the raw bytes (direct pipe or file) — never `echo "$captured" | jq` under zsh, whose `echo` interprets `\n` and turns valid JSON into a false "malformed output" finding

**Pattern**: During the VRF-004 live smoke (backlog-service Chunk 01, 2026-07-17), driving the CLI
by hand, I captured `file --json` into a shell variable and ran `echo "$FILE_OUT" | jq`. jq failed
with "Invalid string: control characters from U+0000 through U+001F must be escaped," the body field
showing raw newlines around the appended ` ```prawduct / v: 1 ``` ` block. My first read was a real
serializer defect — the `--json` envelope emitting unescaped newlines — exactly the class VRF-004's
"`| jq .` never chokes" clause exists to catch. It looked like the highest-value possible outcome of
the live pass: a real bug the offline L1 suite couldn't see.

**Why it was a false positive**: before reporting it, I re-ran capturing stdout to a file and parsed
with `python3 … json.loads` — result **OK**, body repr `'…\n\n```prawduct\nv: 1\n```\n'` with the
newlines properly escaped, and only ONE raw `0x0a` in the whole file (the trailing `print` newline).
The serializer (`cli.py::_emit` → `json.dumps(result)`) was correct all along. The corruption was
introduced by **zsh's `echo` builtin**, which interprets backslash escapes by default (unlike POSIX
sh / bash without `-e`): echoing the JSON string re-expanded every `\n` into a literal newline, and
jq then correctly rejected the mangled bytes. The `get <id>` "empty ID" error that followed was a
cascade — `ID=$(echo "$OUT" | jq -r .id)` returned empty because that jq had failed.

**The fix / the discipline**: (1) Consume JSON from the raw bytes — pipe the command *directly*
(`… --json | jq .`) or redirect to a file and validate that; for a definitive check use a real
parser on the real bytes (`python3 -c 'import json; json.load(open(p))'`), which no shell can
corrupt. (2) Do NOT "harden" the producer: the CLI's bytes were valid, standard JSON, and defending
correct output against a specific shell's `echo` both distorts right behavior and can't actually fix
a consumer that re-interprets escapes (root-cause discipline — the shell was the fault, not the
code). (3) Verify before reporting: this nearly became a BLOCKING finding against a correct
serializer; a strict-parser cross-check on the raw file is the cheap veto. Filed as durable rule +
a VRF-004 "consuming the `--json` correctly" note so the next operator doesn't trip the same trap.
Relates to Honest Confidence (#5), Root Cause Discipline (#16), Validate Before Propagating (#15).

Verifying a `--json` CLI, the natural move — capture stdout into a shell var, then `echo "$out" | jq .` — is a trap in **zsh** (this repo's shell): zsh's `echo` builtin interprets backslash escapes by default, so it re-expands the JSON's escaped `\n` into raw newlines, and jq then correctly rejects the corrupted bytes ("control characters from U+0000 through U+001F must be escaped"). The CLI output was never wrong — `json.dumps` escaped the newlines properly; the corruption is 100% consumer-side. This nearly became a false BLOCKING finding against a correct serializer during VRF-004 (backlog-service Chunk 01 live smoke). Two safe consumption patterns: pipe the command *directly* (`prawduct-hook … --json | jq .`) or redirect to a file and validate that (`… --json >/tmp/x.json; jq -e . /tmp/x.json`); to prove validity beyond doubt use `python3 -c 'import json,sys; json.load(open(sys.argv[1]))'` — a real parser on the real bytes, immune to the shell. Corollary for the producer side: do NOT "harden" correct JSON against a shell's `echo` — it distorts right behavior and can't fix a consumer that re-interprets escapes. Same epistemics as the "read the run's own summary, don't trust the pipe" test-evidence rule above: the shell between you and the tool can lie about the tool's output. Discovered VRF-004 zsh-echo false positive (2026-07-17). Relates to Honest Confidence (#5 — nearly reported a guess as a defect), Root Cause Discipline (#16 — the shell, not the code, was the fault), Validate Before Propagating (#15), and [[Never chain a test-evidence `record` after a suite run in the same command]].
## When a session finds uncommitted work in a worktree it did NOT launch in, treat it as another session's territory and leave it alone — a session works only in its own worktree, because sibling WIP belongs to a possibly-live session and adopting it collides with that work and writes into the clone-shared governance state

Discovered 2026-07-17: a session launched in the main checkout read the SessionStart briefing's *enumerated* list of sibling worktrees, saw uncommitted feature work in one, judged it adoptable, entered it, and began verifying/reviewing — while that worktree had its own live session doing the same work. Root cause was briefing NOISE, not a locking gap: listing siblings' branches/paths reads as a menu of adoptable work. Fix removed the enumeration so the briefing orients to THIS worktree only ([[backlog]] WT-8Q3N); the durable agent-side rule stands regardless — check a worktree's `.prawduct/.session-start` liveness before touching one you did not launch in, and default to leaving it alone. Relates to Scope Discipline (#12 — do what was asked, where it was asked), Root Cause Discipline (#16 — the fix was upstream noise, not a downstream lock), Structural Awareness (#21).

## When a fail-closed validator guards a model-written field, tolerate the natural encoding variant — reserve the hard fail for genuine ambiguity, because incidental strictness at a model-output seam is a latent fail-close

A field a model fills has more than one natural encoding of the same meaning: `[]` and an omitted key both say "no files"; `null` and absence both say "unset." When the validator accepts one and hard-fails the other — and the failure aborts a larger operation (a whole consolidation, a whole gate) — you've made a semantically-null distinction load-bearing, and the escalation cost is wildly out of proportion to the "defect." Fail-closed is right for genuine ambiguity (a missing judgment field, a severity typo, a commit mismatch, staleness — where persisting would be *wrong*); it's wrong for a syntactic variant that normalizes to the same thing downstream. The tell that strictness is incidental rather than chosen: no test codifies the rejection — it fell out of reusing a stricter helper (`_nonempty_str_list` where `_str_list` was meant). Fix by tolerating the encoding and letting normalization collapse it (`[]` → absent), not by teaching the model to emit the one blessed form. Discovered critic-empty-files-tolerance (2026-07-10, discodon report): `critic-consolidate` fail-closed on a reviewer partial's `"files": []`, the exact silently-lost-review class the module exists to prevent. Relates to Root Cause Discipline (#16), Honest Confidence (#5), and [[When a governance checkpoint verifies a required side-effect happened, put it OUTSIDE the control flow that produces the side-effect]] (same module, same failure class).

## When designing any flow step that records status or bookkeeping, make it ride IN the PR that does the work — a step that can only run post-merge on the integration branch is structurally broken for protected-branch consumers

When a flow needs a status flip, an archive, a derived-view regen, or an artifact retirement, design it to land on the feature branch so it merges atomically with the work — because protected integration branches take commits only by PR, and any post-merge bookkeeping step forces those consumers into a second, bookkeeping-only PR (observed live: the stamp-merged chore commit, reported by a product repo within a month of shipping). Atomicity is also the correctness argument: a claim written on the branch only becomes visible where it's true (the merge), and an abandoned PR abandons its bookkeeping, so state can't drift. Where the truth genuinely isn't knowable pre-merge (gitflow's released-vs-pending), derive it from location (a statusless tagged entry ON the integration branch IS release-pending) rather than stamping it. Test for the pattern: "does any step of this flow instruct a commit while sitting on the integration branch?" — a guardrail test now pins this for `/prawduct:pr`. Discovered single-pr-bookkeeping (2026-07-10, user report + discodon live data point). Relates to Governance Is Structural (#22), Coherent Artifacts (#13), Proportional Effort (#11), and [[new change-log entries on a feature branch are statusless]] (the lifecycle this rule produced).

## When you disable a mechanism at its wiring point but keep its implementation, reconcile the retained code's self-descriptions in the same change — or its prose reads as false

Removing a feature's *active wiring* (the skill prose / config that invokes it) while retaining its implementation leaves every docstring, comment, artifact, learning, and backlog item that *described the live behavior* stale — the code is correct but its prose now lies. The Critic reliably catches this as "concept ripple into non-diff files" (v3.0.1 reviewer-model-tiering removal: 3 independent reviewers each flagged the same class — `lib/risk.py` docstring, `lib/telemetry.py` comment, the A/B artifact, a learning, a backlog item). When a restore is planned, add a dated **PAUSED** note rather than deleting — preserves the rationale for the restore and keeps the reader un-misled. Relates to Living Documentation (#3), Coherent Artifacts (#13); the removed mechanism itself is the [[when-prose-picks-which-model-a-reviewer-subagent-runs-on]] dispatch rule (now dormant).

## Pre-dispatch bootstrap code must fail open on a `lib/` ImportError

`get_project_dir()` and any other helper that runs in `main()` BEFORE command dispatch must not hard-depend on the lazily-imported plugin `lib/`: wrap the lib call and fall back to the env/cwd behavior on `ImportError`. Adding a `lib` call there once broke the `regen-views` "could not import" contract — the eager import crashed with a traceback before the command's own graceful handler could fire. The hook's lib-free top level + lazy per-command imports are the architecture; bootstrap code that pre-empts a command's import-error handling defeats it. Relates to Honest Confidence (#5) and the broad-except/fail-open conventions.

## Session-end signals must come AFTER handoff

When signaling session completion ("Ready for next session", "Session is complete"), do the handoff FIRST — commit, update build plan Status, write reflection, capture backlog. Because users interpret completion signals as "handoff is done" and act on them immediately.

## Test-evidence freshness is `test-status` (session timestamp) ONLY — `git_sha` was retired as misleading (TST-4K2P)

The freshness gate (`prawduct-hook test-status`) decides current-vs-stale by `timestamp >= .session-start`, never by a commit field. The record no longer carries a `git_sha`: TST-4K2P removed it because it was **dead-read** by every runtime consumer yet review agents *eyeballed* it and flagged a false "stale / ran against a tree without the fix" whenever a record-before-commit run made the stamp lag HEAD. Consequences: (1) record timing no longer matters for freshness — the old "record AFTER commit, on a clean tree" stopgap is **obsolete**; record whenever in the cycle. (2) When reviewing, judge freshness ONLY by the `test-status` exit code — never infer staleness from a commit/SHA field (there is none). (3) Content-*hash* freshness stays dead (removed pre-v1.4 for chronic false positives), but an **additive tree-VALIDITY clause** now supplements the timestamp (`_test_evidence_tree_valid`, 2026-07-14): current iff session-fresh **OR** the judgeable-scoped working tree matches the recorded run's `evidence_tree`. That `evidence_tree` is a gate-CONSUMED tree object the freshness gate *diffs* — NOT a commit/position field to eyeball like the retired `git_sha`, so it doesn't reopen the lag-behind-HEAD staleness. It classifies paths (git tree-diff + `is_judgeable_path`), never file contents, and only ever relaxes stale→current, so it cannot reintroduce the false-STALE that killed the fingerprint. See [[re-attempting a mechanism rejected for a false-positive class make it additive and relax-only]]. Relates to Honest Confidence (#5 — don't let a misleading field read as a real gap), Validate Before Propagating (#15), and [[when verifying a framework-repo change by running the hook use the repo-local bin/prawduct-hook]].

## A cross-cutting concern can be UNCOVERED even when discovery names it once — audit the coverage matrix for "named-but-dropped", not just "absent"

A concern discovery mentions in passing but no downstream stage operationalizes (no artifact template, no builder guidance, no Critic check, no matrix row) is *uncovered*, not covered — a failure distinct from "absent," and one the coverage matrix itself misses because it lists concerns without auditing whether each is carried *through* all four columns. When checking pipeline coverage, walk each named concern across Discovery → Artifact → Builder → Critic and treat a name-without-operationalization as a gap; the cost is real (../scriob ran ~697/700 commits with its API unversioned on an unchallenged one-word "versioning deferred" note, then paid a coordinated breaking-change retrofit). The framework had no opinion to pressure-test the deferral with, because the concern was named but never built. Relates to [[reactive systems can't detect missing things]] (the Critic reviews diffs, so a never-built concern is invisible to it), Complete Delivery (#2), Governance Is Structural (#22), and Validate Before Propagating (#15).

## Before "fixing" an apparent forgotten-manual-update, check whether the artifact is a GENERATED / DERIVED view — the real fix is upstream

When something looks like a stale or forgotten manual edit (an unflipped checkbox, an out-of-date count, a summary that lags), first ask whether that artifact is *derived* from a canonical source rather than hand-maintained — a correct-looking manual edit to a generated view is churn the generator silently overwrites, and the diagnosis ("someone forgot to update it") is wrong. In this repo `views_enabled: true` makes a build-plan `## Status` block a derived view of `change-log.md` `status=shipped|merged` tags: checkboxes flip at merge/release via `regen-views`, so `[ ]` on a feature branch is the CORRECT derived state, not a gap — I hand-flipped Chunks 01/02 to `[x]`, wrote a reflection calling it a "coherence gap," and `regen-views` overwrote it back to unshipped. The methodology already says "don't hand-edit Status when views_enabled" — the trap was acting on the *symptom* before checking the *generation model*. Verify what writes an artifact before you write it; fix the source (the tags), then regenerate. Relates to Validate Before Propagating (#15), Living Documentation (#3 — docs describe reality, but derived docs describe it *through* their source), Root Cause Discipline (#16), and [[denormalized state drifts without mechanical validation]].

## Never chain a test-evidence `record` after a suite run in the same command, and never read a piped suite's exit code — read the run's own summary first, because a false-green record pollutes the gate exactly like a false-red

When recording test evidence from a suite you just ran, the counts must come from the run's OWN final summary, read AFTER completion, and the record command must be a SEPARATE step gated on that reading — never `pytest … | tail` (the pipeline exit is tail's, so a red suite reports exit 0; use `set -o pipefail` or check the summary line) and never `…; prawduct-hook test-evidence record --from-counts <assumed>` chained unconditionally. Because the failure mode is a polluted gate wearing a green badge: this repo recorded 1700/0/0 while the suite said "4 failed" (caught only by re-reading the output file), the mirror image of TST-6F2R's false-red from discodon — the ingest on-ramp (`--from-counts`) trusts the caller, so the caller's discipline IS the integrity boundary. Relates to Honest Confidence (#5), Validate Before Propagating (#15), and [[backlog]] TST-6F2R.

## A proactive nudge narrowed to pass a "zero-fire against this repo" acceptance criterion suppresses the exact signal on the reference repo — check the repo is genuinely OUT of the target state before muting

When a newly-built advisory/nudge whose whole job is discoverability ("surface X so the user never has to know to ask") collides with a "zero advisories against this repo" acceptance criterion, do NOT resolve the tension by narrowing the trigger until it goes silent — first confirm the repo is genuinely OUT of the nudge's target state. If it is IN that state, the fire is signal, not noise, and muting it blinds the reference implementation to the very need the nudge exists to surface — the worst possible place to be blind, because the reference repo is what every adopter copies and what you observe most directly. The norm-lifecycle build narrowed `norm-registry-unratified` to require strategy-class artifacts (Chunk 3, Critic R-1) to hit its zero-fire acceptance, but prawduct's own norms live in preferences + learnings with no strategy artifacts, so the reference repo's registry sits unratified AND un-nudged — invisible until the owner happened to ask "did this ever surface?". The narrowing also over-corrected on its own stated noise fear ("would false-fire on every pre-norm product"): every pre-norm product genuinely SHOULD adopt, so that fire is signal, and the one-shot + shared-answer + clears-on-ratify-or-record-none mechanism was already built to make a broad adoption nudge tolerable — the noise was handled, so narrowing traded away real signal for nothing. Rule: when a proactive nudge and a zero-fire criterion conflict, satisfy the criterion by proving the repo is out of the target state (ratify, or record the none-outcome) — never by shrinking the trigger; a "zero advisories" bar is only honest when the silence is compliance, not a narrowed probe. Filed as [[backlog]] GOV-EXI2. Relates to Honest Confidence (#5 — silence-by-narrowing reads as compliance but isn't), Bring Expertise (#7 — the nudge exists to raise what the user didn't know to ask), Governance Is Structural (#22 — the probe is the structural surface that makes the need discoverable), [[A test asserting the framework repo's OWN state instead of the propagated contract gives false coverage]] (same dogfooding blind-spot family — the reference repo's own state masks the real gap), and [[When generalizing or detecting "across all cases", the COMMON / AVAILABLE instance silently narrows the requirement to itself]].

## For a coverage / forcing-function opt-out, make the resolution a first-class recorded artifact (even a one-line stub), not a suppression flag

When a forcing function (a coverage nudge, a required-artifact check, any "you must have X" gate) needs an opt-out for products where X genuinely doesn't apply, resist a suppression scalar / exclusion list — make the resolution the artifact EXISTING, where a deliberate `(not relevant — <reason>)` stub is valid content. A suppression flag is inert (nobody reads it), invisible (buried in state), and rubber-stampable (decline-all defeats the purpose); a first-class artifact — even a one-line stub — is self-documenting, lives where a reader looks for the decision, participates in the rest of the pipeline (the Critic can read it, a norm can attach to it, risk calibration can challenge it), and makes the opt-out a conscious recorded act rather than a silent toggle. Split the labor to keep the check simple: the forcing function owns EXISTENCE (a decision was recorded); the Critic / risk calibration own decision QUALITY (is "(not relevant)" honest for THIS product — e.g. a high-risk repo stubbing out its security model, or a repo that recorded `exposes_programmatic_interface` stubbing out its api-contract, is a contradiction they catch). This also keeps proportionality honest for tiny products: a 30-second stub is cheaper and more legible than maintaining an exclusion list, and a gentle recurring nudge stays un-annoying precisely because resolution is that cheap — so "surface repeatedly" beats "one-shot dismiss + suppression state." Emerged when the owner rejected a `coverage_declined_*` project-state scalar for the structural-coverage probe in favor of `(not relevant)` stub artifacts. Relates to Living Documentation (#3 — the decision documents itself where reality is described), Proportional Effort (#11), Governance Is Structural (#22), Honest Confidence (#5 — a recorded decline is visible and correctable; a silent flag is neither), and [[reactive systems can't detect missing things]] (the forcing function exists because absence is invisible — its resolution must not itself be invisible).

## A repo-coupled (non-hermetic) test turns every "non-judgeable" doc/state change into a silent test-breaker — the doc-only and test-status classifiers assume non-code files can't change test outcomes

Both PR fast-paths that skip the suite key off a path-based judgeability classifier: `check-pr-doc-only` skips review + suite when every changed file is `.md`/non-code, and `test-status` reports `current` when only "non-judgeable" paths (`.md`, `.prawduct/**` state) changed since the recorded run. That assumption — non-code files can't change test outcomes — is FALSE for any test that reads committed state or docs. prawduct's own `tests/test_norm_probes.py::TestSilentAgainstThisRepo` is a deliberately non-hermetic tripwire reading the live `project-state.yaml`; the norm-registry ratification (#125, a doc-only + `project-state.yaml` PR) cleared `norm-registry-unratified` but tripped `norm-health-sweep-overdue`, breaking it — and BOTH gates waved #125 through (doc-only skipped the suite; test-status called the tree `current`), so the red landed on develop unseen and surfaced only on the next unrelated branch's suite run. When you add a repo-coupled test that reads committed state, you take on a hidden coupling: either make it robust to the state transitions that WILL happen (here, ratification seeds the sweep baseline so the tripwire expects post-ratification silence), or ensure the judgeability classifiers treat its inputs as judgeable — never leave a non-hermetic test whose inputs the gates believe are inert. Filed [[backlog]] COV-4H7N (recorded as a hard constraint on COV-2P7F, which wants the opposite — `.prawduct/**` exempted from gates; a blanket exemption is unsound while non-hermetic tests exist). Relates to Tests Are Contracts (#1), Validate Before Propagating (#15), Governance Is Structural (#22), Honest Confidence (#5 — a skipped suite reads as "nothing to check" but wasn't), and [[A test asserting the framework repo's OWN state instead of the propagated contract gives false coverage]] (sibling non-hermetic-test hazard).

## When committing a consequential decision under momentum, do the cheapest check that could change it FIRST (read the mechanism before tuning it, search current practice before working around a behavior, re-read the artifact you're relying on before contradicting it) — because generation has a short head and a long tail: the plausible unchecked answer costs nothing now and detonates downstream, while retrieval is minutes, full stop

**Source:** upstream learning candidate from discodon
(`prawduct-learning-retrieval-over-generation.md`, frontmatter-dated 2026-07-18 UTC),
incorporated 2026-07-17 local time as Principle 24
(Retrieval Over Generation) plus the cheap-check gate in `methodology/building.md` Decision
Research, the cost-asymmetry framing in `methodology/discovery.md` Calibrate Rigor, a stance
bullet in both session digests, and the "Tuning a mechanism you haven't read" Common Trap.

**The incident that taught it:** a research-agent inner loop kept timing out / returning empty
results. A multi-day, ~$15 eval campaign tuned model, round count, and prompts — parameters of
a loop nobody had read. A 10-minute code read (the loop reserved no round for conclusion) and
one web search (forced-synthesis-on-budget-exhaustion is a documented anti-pattern) would have
collapsed the entire effort. The failure was not a knowledge gap — the ground truth was
available and cheap; the miss was not checking when a check was cheap and decisive.

**Detectors (any one firing = stop and do the cheap check):** confidence word with no citation;
tuning an unread mechanism; an artifact in hand contradicting the choice, unreconciled;
working around a behavior unchecked against known anti-patterns; ≥10× cost asymmetry ignored;
novel design vocabulary with zero citations; revising the same decision 2-3× with no new fact;
recalling fast-moving facts instead of looking them up. The prawduct "terms not found in any
governing artifact" nudge is one of these detectors mechanized — treat it as a confabulation
alarm, not noise.

## When a docstring makes an absolute robustness claim (never raises / always returns / idempotent), make it literally true and test the claimed-safe path — an absolute claim beside a call that *can* violate it is a coherence gap reviewers reliably flag

**Pattern**: COV-7K4N build (2026-07-14). `diagnose_stale_remote_base`'s docstring said "Never
raises; any git failure returns None," but its local-branch guard called `_git_ref_exists` — a bare
`subprocess.run(..., timeout=30)` that can raise `TimeoutExpired`/`OSError`.

**Why it mattered despite near-zero exposure.** Real-world reachability was effectively nil (the
same helper runs earlier in the same invocation via `_resolve_base_branch`), yet the builder's
self-scrub AND every reviewer who touched it independently converged on the gap — three-way
agreement on a "practically-nil but real" contract violation.

**The move**: when review converges like that, the right response is not "reviewers agree it's fine
as a NOTE" but to make the claim TRUE. Route the guard through the never-raising helper
(`evidence.run_git`, which converts subprocess failures to a nonzero rc) and add a test that
exercises the claimed-safe degradation branch (a non-git dir → `None`, no exception). Cost was one
`verify-resolutions` delta pass.

Absolute claims are cheap to write and expensive to leave slightly false: they read as guarantees
callers lean on — here both the gate's already-failing path and the broad-except-wrapped probe.
Relates to Honest Confidence (#5), Tests Are Contracts (#1), and the `evidence.run_git` no-raise
contract.

## Merge instructions written BEFORE the merge — a subagent's advice, or a note you wrote yourself — are verified against the merge's actual hunk shape, never applied literally: whoever reasons from the BRANCH cannot see a convention the DESTINATION adopted after the branch was cut

Two instances, one session. (a) A merge agent advised taking the branch's `learnings.md` body
verbatim — but develop had since compacted that rule to heading-only with the narrative moved to
`learnings-detail.md`, so following the advice would have silently reversed the compaction. (b) A
reserved-split-id note *I wrote myself* said "take the branch's version and drop this note" — correct
when written, but the branch had since moved `## Archive` upward, so applying it literally would have
archived 10 open backlog items. The common cause is temporal, not competence: any instruction
authored against the branch is blind to what the destination adopted afterward, and a self-authored
note carries no warning label. Discipline: at merge time, read the actual hunk boundaries the conflict
presents before honoring any pre-written resolution, including your own. Sharpens [[When a fresh-eyes
review's advice about a CONVENTION conflicts with a durable learning + the process doc, the documented
convention wins]] — there the convention was documented and findable; here it exists only in the
destination's tree. Discovered fix/cov-7k4n-stale-base-advisory merge (2026-07-19). Relates to
[[A subagent's reported COUNT or LIST is a lead, not ground truth]] and [[Verify a review artifact's cited gaps against HEAD first]].

## When a feature's value rests on an invariant ("presence of X proves Y"), audit the DEGRADATION paths first — that is where the invariant actually lives: a helper that swallows failure into "" or False makes absence ambiguous and can render the signal's exact inverse, so pick each fallback's direction from what the invariant needs, not from what is locally safe

The feature's whole claim was "the presence of this segment proves a checkout install." Two
Critic rounds inverted that claim twice, both in degradation paths, never in the carefully-designed
happy path. First: `checkout_provenance` returned `""` silently when git failed, making absence
ambiguous — a real checkout with a broken git read looked identical to a managed install, so absence
was read as "managed install won." Second: `is_managed_install` failed open to `False`, so on an
unresolvable path a genuine managed install renders a **spurious** checkout segment — the exact false
claim the feature exists to prevent. Rule: when a feature's value is an invariant of the form
"X present ⇒ Y", enumerate every path that can produce or suppress X under failure and check whether
the invariant survives each; a locally reasonable default (`""`, `False`, "assume not") is the wrong
default when it makes the signal ambiguous or inverted. Kin to [[When the success path threads
advisory/audit data through a result envelope, add it to EVERY error-return path too]] (both: the
interesting behavior is on the path you didn't design), and to [[When a docstring makes an absolute
robustness claim (never raises / always returns / idempotent), make it literally true and test the
claimed-safe path]]. Discovered BRF-7Q4M banner load provenance (2026-07-19). Relates to Honest
Confidence (#5), Root Cause Discipline (#16), Independent Review (#14) — self-review reliably
re-walks the happy path.

## When a durable plan asserts VCS state ("the code lives on branch X, not develop", "resuming means landing Y", an ahead/behind count), re-derive it from git before acting on or copying it — plan prose about branches and merges is a snapshot that expires the instant the next merge lands, so run `gh pr view` / `git merge-base --is-ancestor` / compare tree hashes first; a since-merged "land this branch" step is a no-op a plain merge performs silently, and the check costs under a minute

Authoring `build-plan-v3.2.0-golive.md` (2026-07-24), I trusted the release plan's
"⚠️ First: the code lives on `feature/backlog-service-relayout`, not `develop`" section — a section
written 2026-07-21 and *self-consciously* written to be durable ("the document someone opens six weeks
from now"). It was falsified within two days: **PR #137 merged relayout → develop on 2026-07-23.** On
that stale premise I wrote a "Chunk 01: land the relayout branch → develop" step plus a whole
Prerequisites block. Had we run `/prawduct:pr` on it, it would have merged **nothing**: relayout was an
*ancestor* of develop (`git merge-base --is-ancestor` → yes), and develop's `plugin/lib/backlog` tree
was **byte-identical** (`e25f555`) to relayout's — the code was already there. Three sub-minute checks
each catch it before a line of plan prose is written: `gh pr view 137` (state MERGED), `git merge-base
--is-ancestor <branch> origin/develop` (yes ⇒ a merge is a no-op), and comparing
`git rev-parse origin/develop:<path>` to the branch's (identical ⇒ code already landed). The tell is a
plan step of the shape "merge/land branch X" or "the code is on X, not Y" — a claim about VCS state,
which is exactly the class that expires on the next merge. Distinct from
[[A red version/release-hygiene test on a feature branch is often a branch-STALENESS symptom, not a doc
defect — check distance from the integration branch before patching the changelog]]: that one is *your
current branch* being stale versus integration; this one is *a plan's prose about branch state* being
stale, and it bites when you copy that prose forward into a new artifact. Kin to the coverage-claim
falsification family ([[Before writing any sentence of the shape "X now covers/catches/handles Y" or
"there is no Y", run the one query that would falsify it]]) — same reflex, applied to VCS-state claims —
and to Validate Before Propagating (#15) and Living Documentation (#3, the release plan's own section
should have been annotated the moment #137 landed).
## Before implementing against a mechanism, grep the BACKLOG for that mechanism's name — and when claiming something is "provably equivalent," name the proposition the proof actually establishes, because equivalence under one model is not equivalence under the one that governs behaviour

A coverage-gate relaxation was designed, argued across five soundness properties, tested, proven on real git blobs, and shipped — and the Critic returned **10 blocking findings** and refuted the premise. Two separable failures, both durable. **(1) The objection was already filed.** `COV-3M8Q`, opened by the owner eight days earlier, *was* this proposal and stated the disqualifying property outright: "a bug in the equivalence check ships unreviewed code. That is the unsafe direction." The mechanism was searched (`is_judgeable_path`, `_free_edge_files`, the do-not-reintroduce note); the *backlog* was not. Prior art on a change lives in the tracker, not in the code, and the person requesting the change is often the person who already wrote down why it fails. **(2) The proof was of the wrong proposition.** "An identical AST is a proof, not a heuristic" is true and irrelevant: AST equality proves *the parser sees the same program*, not *the system behaves the same*, and behaviour here includes everything that reads source **as text** — `waivers.py`'s `prawduct:allow` pragma is a comment that `compliance.py` acts on, so an AST-identical edit can suppress a compliance check, and tests asserting over `.py` prose are a second such channel. Before asserting equivalence, write the sentence "this proves X" and check X is the property you need. Corollary that generalizes past this case: **when a cost hurts, prefer the fix that removes the cost over the fix that removes the check** — the boring already-planned option (make the review cheap) sat beside the clever one (make the review skippable) with zero soundness risk, and only the clever one could ship unreviewed code. Also: of five soundness claims, three failed, every one because the claim being *made* was verified rather than the case that would *break* it. Discovered 2026-07-29 (built, reviewed, reverted to a byte-identical `gates.py` the same session). Relates to Retrieval Over Generation (#24), Root Cause Discipline (#16), Honest Confidence (#5), [[The fix for a review finding needs the same adversarial pass as the original work]].

## Under a single-parent promotion model, "did this ship?" is a question about TREE CONTENT and never about ancestry — `git tag --contains` cannot return a positive answer for any scope, so it fails as a confident false negative, and the content test needs a control that fails plus a functional-surface target

A `develop`→`main` promotion is a **single-parent** commit, so no `develop` commit is ever an ancestor of a release tag. `git tag --contains <commit>` therefore reports "no release contains this" for *everything* — read naively it "confirms" that nothing in the repo has ever shipped. Use `git show <tag>:<path>` or `git grep <needle> <tag>`: tree content, not ancestry. Two further traps, both hit in one sitting. **(1) A presence test needs a control that fails.** A needle taken from a merge diff can be re-flowed pre-existing prose rather than scope-introduced text; it "proved" a scope shipped in a release tagged three days *before* the scope merged. Always assert the needle is **absent at the tag immediately before the work merged** — a needle that is present everywhere is measuring nothing, exactly like a test that cannot fail. **(2) Test the surface whose absence would matter.** Repo state (`.prawduct/artifacts/`, plans, backlog) travels with the tree wholesale, so a pruned release routinely ships a scope's *build plan* while withholding its *code*. Validated needles that land in `.prawduct/` are true and irrelevant; retargeting to `plugin/skills/`, `plugin/lib/` reversed the verdict on a scope from shipped to never-shipped. Corollary for release archaeology when no tag exists for the era (prawduct's earliest is `v1.8.1`, so the v1.x releases are untestable): fall back to **chunk membership** — a per-chunk change-log entry inherits the release of the unique rollup entry whose `chunks=` enumeration contains it — and say plainly that this is a structural read of the ledger, *not* the code test. Discovered 2026-07-29, release-readiness (discharging Phase 0's own precondition: its six "historical" scopes were three, and the other three had never shipped). Relates to Honest Confidence (#5), Validate Before Propagating (#15), Retrieval Over Generation (#24), [[Pinning the CONSTANT a threshold uses is not testing the threshold]].

## When you "correct" an inherited number, recount the SET and not just the count — re-measuring inside the frame you inherited reproduces the frame's error while feeling exactly like verification

W-1 was filed as "8 statusless change-log entries across four scopes." I recounted **those four scopes**, got 9, recorded the correction in five documents and asserted it in a commit message as "counted at `c49be89` and at HEAD." At HEAD it was 16 across five scopes — the branch had added 7 entries under a scope the finding never named. The finding was *about scope-narrowed counting*, and the count written to prove it was scope-narrowed the same way. The trap is specific: correcting a figure produces the felt experience of verification, so the frame the figure sits in — which scopes, which range, which tree — is never re-examined, and an inherited frame is exactly as untrustworthy as an inherited number ([[an inherited diagnosis is a hypothesis, not a finding]]). Two mechanics: recompute the **denominator** first (all scopes, all entries) and only then the numerator; and where the number will be read later, **write the derivation command into the document instead of the figure**, with the tree it was measured on beside it — a number in prose decays silently on the next merge, a command does not. **Companion, from the fix to this very finding: run the command you publish as proof.** Replacing the decaying figure with a derivation command was the right shape, and the command printed 54 entries across 12 scopes against the 23-across-six stated two lines below it — under a sentence instructing the reader to trust the command over the paragraph. The boundary-restricted version written next keyed on a bare `release=`, a string the document's own prose contains, so it placed the boundary inside a paragraph and returned 1. A command in a runbook is a *claim that it reproduces the stated result*; publishing one unexecuted is the same act as writing an unverified count, one level of indirection out. Discovered 2026-07-29, release-readiness Chunk 03 (Critic cumulative `rev-20260729T185143Z` then verify `rev-20260729T192252Z`, warning both rounds). Relates to Honest Confidence (#5), Validate Before Propagating (#15), [[Verify a disposition against the diff before recording it]].

## Correcting a false claim is authoring a new claim — verify the replacement and the artifacts it cites, because the fixing mood generates claims faster than the checking reflex fires

Fixing a false safety claim across ten sites, the same changeset introduced two fresh ones: an `all`-scope bullet promising the archive "stays reachable from `find`/`list`" (post-cutover `find` is W2-deferred for *every* item — established by the PR merged an hour earlier, precisely because it was adjacent), and "re-run with `--archive-scope all` to backfill, no duplicates" (true about duplicates, silent that the skip path reconciles status, so a backfill reopens anything closed on the service since cutover). Then the *correction* of one of those overclaims swung into a different wrong claim — asserting a backlog note "records the same gap" when it concluded the opposite — taking three commits to land accurate. **Two rules.** (1) A replacement sentence gets the same falsification query the original needed; being in the middle of a correction is the *highest*-risk moment for this class, not a safe one. (2) When successive edits to one passage alternate direction (overclaim → overcorrect → …), stop editing and go read the sources — the oscillation is the tell that you are reasoning from the passage instead of from what it describes, and a reviewer calling a further pass "churn, not improvement" is usually right. Discovered 2026-07-20 on `fix/archive-scope-preservation-claim` (cumulative + 5 verify-resolutions rounds, 15→0). Relates to [[Before writing any sentence of the shape "X now covers/catches/handles Y" or "there is no Y", run the one query that would falsify it]] and Validate Before Propagating (#15).

**Second recurrence, 2026-08-02, `fix/drift-burndown` Chunk 02 — and it fired inside a sweep whose
entire subject was false claims, with this rule already written.** Auditing 32 coverage-matrix rows,
31 cells got a query and an answer. The Dependency-management cell got a conclusion: "`building.md`
names a new dependency only as a size heuristic", written from the impression left by a grep I had
run for something else — a grep whose output *contained* the line that falsifies it
(`building.md:150` names external dependency as one of five triggers making a decision major). The
Critic caught it as a warning: *the sweep reproduced its own target defect*. **What the rule was
missing is the trigger.** "The fixing mood" is a state you cannot notice from inside; "I am writing
a replacement sentence" is an event. The operative form: when the correction is drafted, run the
query against **the replacement**, not against the claim being replaced — you have just read the
source, so the correction feels checked, and reading is what produced the error. The syntactic tell,
usable mid-sweep: *this cell got a conclusion where every other one got a query.* Corollary observed
in the same chunk: the four corrections written after this fired were each grep-verified against the
mechanism first, and all four passed the verify round.

## A falsifying grep queries a PHRASING; only a reader queries a concept — the same stale state written in words your query does not contain is invisible, so the sites that survive a sweep are exactly the ones that paraphrase

`fix/drift-burndown` Chunk 02 (#179), 2026-08-02. VRF-010 had verified three foreign-API readers
live, and the closure had to be propagated to every record still encoding the pre-verification state.
The falsifying query was the claim's own vocabulary — `fake-verified`, `shape-verified`, `fake only`
— and it found the two golive-plan sites the item named plus the `project-state.yaml` claim. The
Critic then found a **third** golive site the query could not reach: Chunk 05b's `Covers:` line,
reading *"its foreign-API verification half **stays open**"*. Same state, same file, same release —
zero shared vocabulary with the query.

This is the limit of the standing *query the CONCEPT, not the phrasing* rule, and the limit is
structural rather than a lapse: **a grep can only ever match a phrasing.** "Query the concept" is
achievable only by (a) naming the *state* being asserted and then searching two or three vocabularies
that share no word with each other — here, the claim's own words, the *consequence* words
(`stays open`, `still open`, `unverified`), and the *entity* words (the item id, the reader names) —
or (b) handing the concept to a reader, which is what independent review is and why it caught this.

The cheap discipline: after a sweep, ask *what would this record say if it never used my search
terms?* If you cannot answer, the sweep covered a phrasing and reported it as coverage. Relates to
[[A completeness claim asserts the falsifying COMMAND now returns nothing]] and Independent Review (#14).

## Before writing any sentence of the shape "X now covers/catches/handles Y" or "there is no Y", run the one query that would falsify it — a coverage claim is the highest-frequency error class here and is almost always checkable in under a minute, so treat the SENTENCE as the trigger, not your confidence in it

The claim-shape is the tripwire, not the topic: "this test now catches the class", "every reader is repointed", "there is nothing local to run this against", "the inventory is exhaustive". Six instances across 2026-07-19/20 — twice stating a repo/state didn't exist that did (one loop over sibling `project-state.yaml` files falsified it), twice describing a regex/test as covering a class it demonstrably could not (`[^.]` excluding the dots in `.prawduct/backlog.md`; an `op == "x"` derivation blind to `op in ("a","b")`), once repeating a docstring's rationale that the requirements had already corrected two days earlier, and once writing "fixing one and not the other would be the patch-the-flagged-line failure" while leaving the sibling copy in the same file. Being careful demonstrably does not work at this frequency; the check does. Fix-shape: (a) for a set/coverage claim, re-derive the set with the precise query right before writing it; (b) for an absence claim ("no X exists"), run the enumeration rather than reasoning from what you happened to see; (c) for a rationale read off a comment or docstring, verify the requirement it cites still says that — the nearest source is not the authoritative one; (d) for "I am avoiding anti-pattern P", actually run P's detector, because naming P is not running it.

**Instance 8 (2026-07-20) sharpens this into something mechanically detectable — the check can be *performed* and still be worthless.** Correcting a false claim across the repo, I ran the grep, counted the hits, and told the user "seven surfaces." The pipeline ended in `| head -20`, so real hits had been truncated away; a wider re-run found more and I said "nine." The enumerated truth was **ten claim sites across seven files** — so the first number was wrong, and so was the correction, which is the part worth keeping: *this entry originally asserted "It was nine," and a Critic pass caught the durable learning about miscounting carrying a wrong count.* A number read off a truncated search is not a count — it is a check-shaped artifact that reads as diligence in the transcript, and is therefore *more* convincing than an unchecked guess would have been. The tell is now syntactic rather than introspective: **if the pipeline that establishes completeness contains `head`, `tail`, `-m`, or any other cap, its output must not be stated as a total.** Re-run it uncapped, with the pattern widened to the claim's actual shape, before writing the number. Corollary from the same session, pointing the other way: before mass-correcting a sentence, check the *siblings* that share its wording — four "recoverable via the MG2 export backup" claims about `restructure` were **true** (the block carries `original_title`/`original_body`, so the post-import export does hold them) while the identically-worded `--archive-scope` ones were false, so a sweep-and-replace would have converted four correct statements into wrong ones. Relates to Honest Confidence (#5), Validate Before Propagating (#15), Retrieval Over Generation (#24), and [[Verify a review artifact's cited gaps against HEAD first]].

**Sharpening (2026-07-20, `fix/archive-scope-preservation-claim`, across a run of verify-resolutions
rounds — count deliberately omitted; corollary (c) says why):
the error lives in the QUANTIFIER, and that makes it detectable before writing.** Across one branch
the same shape recurred with the narrow fact correctly verified every time and the written claim
scoped wider than the check: "there is **no** follow-up commit on **any** of them" (true for two of
three files — the third had one), "the other ten, **every** one of them migration work" (one was
not — `stale-remote-base-diagnostics`; the sentence survives verbatim in the hotfix plan and is
now *true*, because the set it quantifies over was re-derived, which is the point: quantified
sentences go stale when the set moves under them, not when the words change), "six `--repo`
placeholders in six **steps**" (six commands across four steps), "**also**
catches a second minting site" (only one copied in the same literal shape; an f-string passes).
Each was written inside the correction of the previous one. So the operative rule is not "check
harder" — it is **verify at the quantifier**: when a sentence contains *no / every / all / only /
none / also*, the check must enumerate the quantified set, and a per-file claim needs a per-file
loop, not a combined query that returns one answer. Three corollaries. (a) A number derived
positionally is not derived from the field: counting change-log entries *above* a release boundary
structurally cannot see an unreleased entry below it, and one was there — REL-2N8K reproducing
inside the plan citing REL-2N8K. (b) **An untouched sentence inside an edited paragraph reads as
freshly vouched-for.** Editing a paragraph re-publishes all of it; re-verify the sentences you did
not change, because a reviewer — and a later reader — cannot tell which ones you actually looked at.
(c) **Some quantified sets contain the sentence that counts them, and those counts cannot be
written truthfully.** This entry first opened "five verify-resolutions rounds," then "twelve —
eleven reachable, one orphaned," and a re-enumeration minutes later returned thirteen reachable
plus the orphan, because the review answering the sentence had itself consolidated in between and a
widened predicate swept in a round the first query's `head_commit` filter had missed. Neither
number was carelessly derived; both were stale on arrival. The tell is self-reference: **when the
act of writing the claim changes the set the claim quantifies over, no enumeration converges** —
say "a run of" and describe the shape, or pin the set to a closed predicate ("the rounds preceding
this one") that writing cannot move. Counting harder is the wrong response; the set is the problem.

## When you add a fallback lookup INSIDE a per-item loop, amortize it AND make it a no-op on the common path — a naive fallback that fires on every miss is O(N²) at scale, and the fresh case is all-misses

A spec that says "make X a fallback authority in `_find_by_key`" reads as "scan on every label-miss" — but the importer calls it once per record, and on a FRESH import every record misses the label (nothing exists yet), so a per-miss full-issue scan is O(N²), invisible in the unit suite and only biting at ~200-item migration scale (the same full-scan cost BKL-2K8V already flagged). The fix (BKL-4W7H `_AliasIndex`): build the fallback index ONCE, lazily on the first miss, and cache it for the run — a clean import/resume where every label is intact never scans at all; a drifted re-import pays exactly one scan. Pin the zero-cost property with a test that asserts NO unfiltered `list_issues` on a clean re-run — a silent perf regression here won't show in the unit suite. Corollary (same cycle): when a fix must satisfy two named gaps (here read-resolution AND import-idempotency), look for the ONE mechanism that closes both — restoring the `id:PFX` label on the fallback hit self-heals the skip-authority AND makes the alias resolve again, because the label was both keys. Relates to Proportional Effort (#11), Tests Are Contracts (#1), and [[backlog]] BKL-2K8V (the ~12s full-scan pick floor).

## When a test injects a fixed clock, EVERY actor in the scenario must share that clock domain — one real-clock participant (a CLI front, an un-injected default) turns fixed-timestamp + TTL into a scheduled deterministic failure at stamp+TTL wall time

A claim-conflict test stamped the holder's claim via `core.claim(now=NOW)` (fixed 2026-07-17T12:00Z) but drove the challenger through `cli.run`, which reads the real clock. The 24h claim TTL made the test green until 2026-07-18T12:00Z and deterministically red after — the challenger's "conflict" became a LEGAL TTL-reap of an expired claim. The product was correct; the test mixed clock domains, and the failure surfaced as an apparent regression in an unrelated PR-prep run. Rule: pick ONE domain per scenario — inject `now` into every participant, or drive every participant through the real clock (here: both claims via the CLI). Sweep test: grep each test file mixing `now=<fixed>` with a front that defaults to wall time. Discovered PR-prep after the develop merge (2026-07-18); the sibling query/governance suites were single-domain and clean. Relates to Tests Are Contracts (#1 — the fix preserved the contract, changed only the clock plumbing), Root Cause Discipline (#16 — "passed yesterday, fails today, no code change" points at time, not the merge), and [[When validating a CLI's JSON output, feed the tool the raw bytes (direct pipe or file) — never `echo "$captured" | jq` under zsh, whose `echo` interprets `\n` and turns valid JSON into a false "malformed output" finding]] (both: the harness between test and product lied, not the product).

## A review finding is about a CLAIM, not a file — resolve it by grepping the claim's wording, and never truncate the recommendation you are acting on

Four consecutive review rounds on one chunk found the previous round's fix incomplete in the same
direction: the named instance fixed, the class missed. A guard, then a docstring one module over while
the docstring *inside the function being changed* still stated the reversed rule, then a renamed
heading that orphaned six cross-references, then two more surfaces still promising a behavior three of
five sources no longer perform. The mechanical cause of the last one is exact and embarrassing: I
printed the findings with `recommendation[:400]`, and that finding's closing instruction — "check
these two other sites while you are there" — sat past the cut, so I acted on a truncated instruction
and then reported the finding closed. This is the `head`-in-a-completeness-pipeline rule
([[Instance 8]]) applied to review findings rather than to greps: **a finding read through a
truncation must not be reported as resolved.** Two rules: (1) read each finding's recommendation in
FULL before acting, and re-read it before claiming closure — the tail is where reviewers put the
"while you're in there" sites; (2) resolve by **grepping the claim's distinctive wording across the
repo** (prose, docstrings, skill instructions, operator-facing message strings, plans, change-log),
not by editing the files the finding lists. When that sweep was finally run correctly it found
**sites the reviewers' own enumerations had not included** — so the mechanical sweep is strictly
stronger than following the finding's file list, and it is the move that scales when the same claim
was copied. (It took three attempts to run it correctly; the failures are (a) and (b) below.) Corollary for the change-log specifically: an entry authored inside an unreleased bundle
is not append-only history — if a later commit in the same bundle reverses its claim, fix the sentence
(with a note that it was corrected), because with `views_enabled` it derives release-notes and the
contradiction ships. Relates to Living Documentation (#3) and Validate Before Propagating (#15).

**Round five sharpened it twice more, and both are mechanical.** (a) **Grep the REVERSED SENTENCE's
own wording, not the wording of the sites you already found.** I swept `"swept at next session start"`
— the phrasing of the two sites the previous finding named — when the load-bearing claim was
`"both paths want"`. Right method, wrong claim: the claim to sweep is the *proposition that changed*,
which you can name from the decision you reversed, not from the files you last edited.
(b) **Claim sweeps are case-insensitive, always.** The hit I missed was in a test module's docstring
and read "which **BOTH** paths want" — capitalized for emphasis, so a case-sensitive `grep` skipped
it, and emphasis-capitalization is exactly the variation a durable-prose sweep will meet. Use `grep
-rni`, and sweep several *formulations* of the claim, not one string. Measured on the pre-fix tree:
`git grep "both paths want"` → **2** hits; `git grep -i` → **3**. The one letter of difference was
the whole miss. *(This entry first cited the case-sensitive command as returning three — quoting a
count that its own next sentence explains is impossible. A later review caught it. Correcting a false
claim is authoring a new one, and a learning that states its evidence wrongly teaches a future session
to discount the rule when the command disagrees.)* The two sites that survived to
round five were the worst two in the bundle: a test module docstring that hands a maintainer written
license to revert the test back to the defect, and a build plan's Verification Strategy step that
would have had an operator confirm the regression as a success.

## Verifying an inventory against the code cannot catch a wrong CATEGORY — the check confirms the frame it was built from

Splitting `cmd_clear` into boundary vs. orientation, I sorted its 17 statements by *does it destroy
session evidence*, enumerated them, verified the inventory against the source (the plan explicitly told
me to), and it passed. Two reviewers then independently found the axis was wrong: a **third** category
exists — statements that destroy nothing yet **interpret session state as belonging to a session that
has finished**. Two qualified (the critic-active marker sweep; the previous-session gate check), both
looked read-only, and a destruction-based sort files them under orientation *and then the verification
agrees*, because it re-asks the frame's own question. Worse, the refutation was already in my own
artifact: the `fork` decision said "a fork's parent is often still running" three paragraphs above a
sweep decision asserting "a marker outliving a session cannot correspond to a live reviewer." Rule:
when a change is driven by a **classification**, the verification pass must ask a *different* question
than the one that produced the classes — for session-lifecycle code, "what does this statement believe
about the session it is running in?" rather than "what does it write?" And when two decisions in one
artifact rest on opposite premises about the same entity, that is a contradiction to find by reading
your own decisions against each other, not something to wait for a reviewer to catch. Relates to
Validate Before Propagating (#15), Root Cause Discipline (#16), and [[Before writing any sentence of
the shape "X now covers/catches/handles Y" or "there is no Y", run the one query that would falsify
it]].

## A mechanism that collapses a distinction forces every downstream rule to hold for the WEAKEST member of the collapsed set

`--brief-only` marks "continuation," so `resume`, `compact` and `fork` reach the hook
indistinguishably. Fine for the boundary/continuation split it was built for — but the premise
licensing the critic-marker sweep ("an in-flight review dies with its process") is true for `resume`,
false for `compact` (fires in-process) and often false for `fork` (parent still running). One flag
covering all three means the safe semantics are the weakest member's, so the sweep had to become
boundary-only. Rule: when introducing a flag/enum that merges cases, enumerate the merged set and check
each downstream rule against **every** member, not the motivating one; if a rule holds for only some,
either split the mechanism or take the weakest member's answer — and record which you chose and why.
Relates to Reasoned Decisions (#4).

## When a finding is "harmless by coincidence," check what makes it harmless before deferring it

The cross-plan chunk-id conflation (`_committed_chunk_ids` matching `Chunk NN` in any commit subject,
no scope filter) was pre-existing, outside the chunk's surface, and provably harmless on the branch —
an easy defer. But it was harmless only because `active_build_plan` pointed at the *wrong* plan, and
correcting that pointer (my own bookkeeping error, a separate finding) would have armed it: the active
plan's two-chunk Status would have read COMPLETE with a chunk unbuilt. The "cosmetic" fix was
load-bearing. Rule: before deferring a latent defect, name the specific condition keeping it dormant
and check whether anything in the current changeset removes that condition. Corollary on the fix
itself: a filter that could **erase** a signal rather than narrow it needs a no-match fallback — scope
tags are a convention, so filtering strictly would have wiped a sibling plan's entire git signal
(its commits say `session-continuity`, its frontmatter `session-handoff-continuity`) and traded
cross-contamination for a different wrong answer. Apply the filter only when it matches something, so
it is always narrowing, never erasing. Relates to Scope Discipline (#12) and Complete Delivery (#2).

## When verifying an assumption, build the instrument WIDER than the proposition — the confirm/deny answer is rarely where the value is

SCN-5B8Q's plan named one load-bearing assumption (`--resume` restores the transcript) and said verify
before building. A codeword planted in a headless session and read back from the resumed one answered
it: yes. But the probe also logged the whole `SessionStart` payload — strictly more than the question
needed — and *that* surfaced `fork`, a **fifth** source the plan was written without, which restores
the transcript AND allocates a new session id (so its parent session is often still live, making it the
one source where a boundary reset destroys a **running** session's evidence). Under the plan's proposed
matchers `fork` matched neither entry and would have silently received nothing. The assumption was
true; the plan was still wrong, and no amount of testing the *proposition* would have shown it. Rule:
when a check is cheap, record the mechanism's full output rather than the single field that answers
your question — unknown unknowns live in the columns you didn't ask for. Corollary for the guard that
results: pin the **partition/class property** over the enumerated set, not a spot-check on the one
member that motivated the work — a spot-check on `compact` is exactly what let `fork` go unnoticed.
Relates to Retrieval Over Generation (#24) and Honest Confidence (#5).

## Single-repo plugin+marketplace: the marketplace entry's plugin `source` must be a RELATIVE PATH, not `{source:github,ref}` — and that path is a curated subdirectory, not the repo root

A `{source:github,…}` object makes Claude Code re-clone over SSH to fetch the plugin, which fails with "Permission denied (publickey)" on any machine without SSH keys, even for a public repo. A relative path reuses the marketplace's own HTTPS checkout. **Corrected 2026-07-21:** this entry previously read `must be "./"` with no body, so the heading was the whole rule — and a reader applying it would revert the v3.1.1 packaging fix. `"./"` distributes the entire repository, putting prawduct's own backlog, learnings and internal docs into every consumer's plugin cache (GOV-4H7T). The path is `"./plugin"`, a curated root holding only what consumers run. Both halves matter and neither implies the other: relative-not-github is about the clone transport, subdirectory-not-root is about the distributed surface. Pinned by `tests/test_plugin_packaging.py`.

## When a later chunk extends an earlier chunk's module with a derived/richer version of a constant that module already defines by hand, grep for the name first — you otherwise create a SHADOWED DUPLICATE that silently works until the two drift, and the fix is to make the richer structure the source of truth the older constant derives from

Chunked builds keep extending earlier chunks' modules, and the trap is adding a parallel definition of something already there while focused on the new feature. Building the backlog-service status *encoder* (Chunk 02) I added `_STATUS_ENCODING` (a map: status → (state, state_reason, label)) plus `STATUS_VALUES = tuple(_STATUS_ENCODING)` — not noticing Chunk 01 had already defined a hand-written `STATUS_VALUES` literal at the top of the same module. Two module-level definitions of the same name: the later one wins, and because the values were identical it *worked*, so no test failed — a dead literal + a silent drift hazard (add a status to one, not the other, and they disagree). Both Critic reviewers (correctness + design) flagged it independently. The clean resolution is NOT "delete the duplicate" but "pick the SoT and derive": promote the richer structure (`_STATUS_ENCODING`) to the single definition and derive every vocabulary constant from it (`STATUS_VALUES = tuple(...)`, `STATUS_OPEN_LABELS = tuple(s for s,(…,label) in …items() if label)`), so drift is now *impossible*, not merely absent. Discipline: before defining a module-level constant/enum/table in a module you're extending, `grep` the module for the name and for the concept; if the concept already has a hand-maintained form and you're adding a structured one, make the structured one authoritative. This is [[When developing requirements to replace a working system, sweep every consumer's actual usage before finalizing]] pointed inward — sweep every *definition*, not just every reader — and a Reasoned-Decisions/SoT instance (identical duplicated state is denormalization that drifts without mechanical validation). Discovered backlog-service Chunk 02 (2026-07-17, both Critic reviewers). Relates to Reasoned Decisions (#4), Coherent Artifacts (#13), Validate Before Propagating (#15), and [[Before "fixing" an apparent forgotten-manual-update, check whether the artifact is a GENERATED / DERIVED view]] (same derive-don't-duplicate spine).

## Idempotent-re-run crash-safety is only sound when SOME actor is guaranteed to re-run the same transition — when recovery depends on the crashed party specifically (the one who won't return), make the write ATOMIC, not merely re-run-convergent

Two compound-write ops in the same subsystem can both be "crash-safe via idempotent re-run" and yet one be broken, because the property hides an assumption: *who* re-runs. The backlog-service `set-status` (Chunk 02) is genuinely crash-safe — its add-before-remove label reconciliation converges on *any* subsequent writer's re-run (the next status change by anyone self-heals a torn state). I pattern-matched that onto `claim` (Chunk 03): take the assignee first, stamp `claimed_at` second, "a re-run by the same actor converges." But claim's recovery depended on the **crashed actor** returning — and the exact failure the feature exists for (M11: a *died* fleet agent's claim must free so `pick` can't starve) is precisely when that actor never returns. Worse, my own fail-open ("assignee set + no `claimed_at` stamp → treat as a live claim, never reap") made the torn intermediate state *permanently* stuck: assigned-but-unstampable, invisible to `pick` until a manual `unclaim`. The Critic caught it; every one of my own tests passed because the two-write torn state is invisible without fault-injection at the seam. Fix: collapse the take into ONE atomic `update_issue` PATCH (assignees + body together — GitHub's issue PATCH accepts both), so no torn state can exist; drop the now-redundant `set_assignees` seam; add a fault-injected crash test (inject at the take → item stays free → re-run converges). Test for the pattern: for any compound write claiming crash-safety-by-re-run, ask "if the process that crashed never comes back, does another actor's ordinary operation still converge this?" — if recovery is actor-specific, atomicity (one request, or a redirect-before-close ordering that reads valid at every cut) is required, not idempotent re-run. Discovered backlog-service Chunk 03 (2026-07-17, Critic warning). Relates to Root Cause Discipline (#16), Honest Confidence (#5 — green tests don't prove a seam's crash path), Independent Review (#14 — a "does it work?" self-review can't see the torn state), and [[When a later chunk extends an earlier chunk's module with a derived/richer version of a constant that module already defines by hand, grep for the name first]] (both are "the earlier chunk's pattern doesn't transfer unexamined to the later one").

## A human-mode output formatter that dispatches on "which key is present" silently shadows a new result type sharing a key with an earlier branch — order the checks most-specific-first, and TEST the human path because `--json`-only tests never exercise the formatter

The backlog-service CLI's `_print_human_ok` is an `if/elif` chain keyed on the presence of a distinctive field (`"candidates"`→pick, `"items"`→list, `"by_status"`→counts, …). Chunk 05's `export` result carries `{repo, dir, count, items}` — and its `items` is a list of id *strings*, but the earlier `elif "items" in data` branch (the `list` result) assumed a list of item *dicts* and called `.get("id")` on each → `AttributeError` the moment `export` ran in human mode. Every test passed because they all asserted on `--json` output, which bypasses the formatter entirely. Two coupled lessons: (1) a dispatch keyed on key-presence is order-sensitive and additively fragile — a new result type must be matched on its *own* unique key placed before any earlier branch whose key it happens to share (same failure family as the shadowed-duplicate constant, but for output shapes); (2) `--json`-only tests are not coverage of the human path — driving the actual front at Verify (Principle 15) caught it where the whole L1 suite could not. Fix: reorder the migration branches ahead of the generic `items`/`candidates` ones, plus a human-mode regression test that runs each new op without `--json`. Discovered backlog-service Chunk 05 (2026-07-17, at Verify). Relates to [[When a later chunk extends an earlier chunk's module with a derived/richer version of a constant that module already defines by hand, grep for the name first]] and Honest Confidence (#5 — green tests over the wrong surface aren't verification).

## An "unverified / validated-when-run" honesty caveat covers only genuinely-unknowable facts (live behaviour, external state) — NEVER facts checkable now (a key path, a signature, a flag); verify the knowable, disclaim only the unknowable

A dev-only spike script (can't run offline) carried a "these assertions are validated when run live" caveat — but one check read the export's native graph from top-level `dependencies`/`sub_issues` keys when `_export_record` nests them under `relationships`, an always-falsy false-negative the Critic caught. The caveat is legitimate for the live-GitHub timing/behaviour the script probes; it is *not* a license to skip reading a source file whose shape is knowable now. When you write a confidence disclaimer, scope it to the genuinely-uncertain and still verify everything statically checkable. Discovered backlog-service Chunk 06 offline deliverables (2026-07-17, Critic chunk-mode). Sharpens Honest Confidence (#5) and Validate Before Propagating (#15).

## A `/prawduct:*` skill fork writes `.prawduct/` state to the LAUNCH dir, not a worktree the session ENTERED mid-session — launch/`/clear` inside the worktree, or relocate the fork's output and restore the polluted checkout

When you enter a git worktree mid-session (harness `EnterWorktree`), main-loop `prawduct-hook` calls resolve to the worktree (Bash cwd = worktree; STH-4K7N's cwd-based `resolve_project_dir`), but a skill invoked as a FORK does NOT — its `CLAUDE_PROJECT_DIR`/cwd stays pinned to the launch dir, so `/prawduct:backlog add` (and any state-mutating skill) silently writes into the PRIMARY checkout and reports success. If that checkout is another active worktree's WIP, this cross-pollutes a different branch's diff/Critic/PR. Confirmed 2026-07-16 (VWS-2W6H landed in feature/norm-lifecycle, not the backlog-service worktree — had to relocate it and `git checkout` the primary's backlog.md) and independently in discodon (SCH-2QW9/ENT-T8QN: an item filed into a worktree's backlog, reverted + hand-merged so "main solely owns the backlog"). So: prefer to LAUNCH (or `/clear`) the session INSIDE the worktree so every fork inherits the worktree project dir; if you must file from a mid-entered worktree, verify WHERE the fork wrote and relocate + restore. Deeper cause — `.prawduct/backlog.md` is a per-working-copy flat file, so worktrees diverge by construction (a motivation for a server-side backlog store). Full detail + fix-shape in [[backlog]] STH-7W9K. Relates to Structural Awareness (#21), Root Cause Discipline (#16), and [[backlog]] CRT-6W2N / STH-4K7N.

## When salvaging work from a branch you are about to delete, diff the ID SETS of its state files — a commit-by-commit triage silently drops novel items that ride inside otherwise-obsolete commits

Retiring a stale worktree branch, the natural triage is per commit: read each one, judge it superseded or novel, salvage the novel. That method has a blind spot — a commit's *overall* disposition says nothing about every hunk inside it, and `.prawduct/` state files accumulate independent items that ride along with unrelated code. Confirmed 2026-07-19: commit-by-commit triage of the removed `backlog-service-plan` branch concluded exactly one backlog item needed salvaging; the Critic then caught that the learnings rule I had just ported ended with a dangling `[[backlog]] STH-7W9K` pointer, and STH-7W9K turned out to be committed *inside* a 100%-obsolete backlog-service walking-skeleton commit. Extracting every `[XXX-NNNN]` id from both copies and running `comm -23` found three more (STH-7W9K, VWS-2W6H, BLD-6T4R) in seconds. So: for any structured state file with stable ids (backlog, operator-verification, change-log scopes), compare the SETS mechanically and let the diff — not your reading of the commit log — decide what is missing; then re-verify each candidate against current code before filing, since a stranded item's body may describe behavior that has since drifted (VWS-2W6H's loud error had partly become a silent wrong-pick). Generalizes [[When a later chunk extends an earlier chunk's module with a derived/richer version of a constant that module already defines by hand, grep for the name first]] from definitions to *records*, and relates to Complete Delivery (#2 — never silently drop a requirement, including one someone else wrote), Validate Before Propagating (#15), and [[A `/prawduct:*` skill fork writes `.prawduct/` state to the LAUNCH dir]] (the pollution that stranded these items in the first place).

## Before filing a finding against a mechanism, read that mechanism's own documented degradations — a design that enumerates its deliberate weaknesses has usually already considered yours

Filed SCN-5B8Q claiming a resume re-anchors the session base and so "blinds the Critic gate to everything before the resume." `gates.session_review_verdict`'s docstring already covered it: a commit made without review leaves a gap no dispatchable review can span from the session base, so composed coverage of merge-base → working tree is used instead — chosen deliberately because demanding an unsatisfiable base "would only train waivers." `check_cumulative_critic` independently requires merge-base → HEAD before any PR. The real residue was much smaller (the session gate silently *narrows*, and that narrowing alone is undocumented). The tell was structural, not subtle: I asserted a severity about a function I had not read, in the same session I wrote down that a checkable claim in a durable artifact is a claim. **Corollary that generalizes further:** the verification subagent I delegated to did not catch it — it *amplified* it ("worse than reported"), because it verified the facts I handed it and inherited the frame I handed it with them. Delegated verification checks your evidence, not your premise, so the premise is exactly what you must check yourself. Discovered 2026-07-27 (owner challenge during session-boundary-events planning). Relates to [[Anything in a durable artifact that one command could check is a CLAIM]], [[A subagent's reported COUNT or LIST is a lead, not ground truth — verify before a blanket edit]], and Retrieval Over Generation (#24).

## A channel that is produced and never consumed is a DEFECT, not an inefficiency — name the consumer in the same change that adds the producer, or don't produce

Four live instances in this repo, which is what makes it a class rather than an anecdote: `.session-handoff.md` was written by the machine and then overwritten by the machine (the original continuity bug); `.handoff-notes.md` is written by the model and goes unconsumed wherever the installed plugin predates the feature; `ChunkProgress.git_derived` is computed on every resolve and read by no production caller; and the session briefing is not rendered at all on `compact`, the one source where context genuinely was just lost. Each looked like waste and each was actually a *silent wrong answer* — the reader either gets stale content presented as current, or gets nothing where something was promised. The owner's form of the rule is the sharpest: *if the output were worthless we should cut the feature, not write one and then not read it.* So: adding a producer without a named consumer is the same defect as dropping a requirement, and it hides better — the producing code is present, tested, and green. When you cannot name the consumer, the honest moves are to delete the producer or to record the gap with an item that makes "tracked" true. Discovered session-handoff-continuity, chunks 01-03 (2026-07-27). Relates to [[Anything in a durable artifact that one command could check is a CLAIM]] and Complete Delivery (#2).

## Anything in a durable artifact that one command could check is a CLAIM — an identifier, a count, a `file:line`, or a facet value, not just a rationale — so run its falsifying query first. The rationale you REACHED FOR to defend a decision already made is the one to verify, and a CORRECTION is itself a completeness claim: quoting the parent rule demonstrably does not prevent this

The sibling of [[A rationale you reached for to defend a decision you'd already made is the one to verify BEFORE writing it into a durable spec — the reach itself is the tell]], generalized past rationales after four instances in two chunks. Writing `SCN-6H2W` into `project-preferences.md` for an item not yet filed (the real id came back `MET-8K4R`); filing it with `kind: design`, a value invented on the spot with zero other users in a 4,700-line backlog; filing `stage: design` when the item's own body said the work was "discovery-shaped", which routes to planning instead of discovery; and asserting a token budget of 4590 in two artifacts after a later edit moved it to 4595. Each is the same act as the recruited rationale — producing a plausible token in the shape the sentence needed — but on surfaces that do not *feel* like assertions. An identifier feels like a label, a facet like a form field, a count like bookkeeping; all four are checkable in one command and all four were wrong. So: before a durable artifact ships, grep it for every id, count, filename and enumerated value you wrote from memory, and re-derive each. Three of the four here were caught only because a subagent reported its own result back, which is luck, not method. Discovered session-handoff-continuity Chunk 03 (2026-07-27). Relates to [[Before writing any sentence of the shape "X now covers/catches/handles Y" or "there is no Y", run the one query that would falsify it — a coverage claim is the highest-frequency error class here and is almost always checkable in under a minute, so treat the SENTENCE as the trigger, not your confidence in it]] — same trigger-on-the-sentence discipline, extended to sentences that contain no verb at all — and [[A subagent's reported COUNT or LIST is a lead, not ground truth — verify before a blanket edit]], whose inverse held here: the subagent's report was what caught me. Honest Confidence (#5).

## A status surface that reports the ABSENCE of expected output must say whether absence is the normal in-flight state — a bare zero invites the reader to invent a death story and take recovery action against healthy work

Confirmed 2026-07-20 ("critic reviewers died with fork", cross-repo): background critic reviewers
run 5-15 min after the dispatching fork returns; a parent session consolidating at ~2.5 min got
`0/3 partials present`, inferred "the fork ended and took them with it" (transcript-verified false
— all three were alive and completed), and re-dispatched a duplicate roster, doubling review cost.
Same binary had run the identical shape clean the day before — the trap is probabilistic model
inference over ambiguous silence, so the fix belongs at the decision point: the message now renders
dispatch age plus a wait/abandon verdict (8b6eef6, CRT-3F7M fix (b)). Generalizes to any
empty-state report an agent acts on (empty queue, no results yet, 0 workers reporting): pair the
count with the timing fact that discriminates in-flight from dead, and name the sanctioned recovery
path so the reader doesn't improvise one. Relates to Honest Confidence (#5), and note the failure
phrase itself ("died with fork") began as one model's hallucinated diagnosis and propagated as
observed fact — including into CRT-3F7M's title.

## When auditing guidance material, have a fresh agent USE it before you recommend changing it — analytic review predicts defects that do not survive contact with practice, and the trial is what tells you which findings are real

Auditing the runbook guide/skill/template (2026-07-20), I argued from the text that the template should be inverted — minimal default, optional sections in a library — because a form-shaped template pulls authors into filling it in and "deletion is the weaker operation." Two subagents then authored real runbooks from the *unmodified* material and both deleted correctly and for the right reasons (blast radius, duration, authorization, maintenance, prerequisites, phases, irreversible block — each against its include-test), with one reporting the guide "stopped me from writing a bloated runbook, which is what I would otherwise have produced." The recommendation was refuted by the artifact it was about. The trials also produced findings no amount of reading would have: that ~150 of 1,277 lines carried all the binding instruction, that the worked example outperformed everything after it, and that a documented procedure contradicted itself in a way only a deriving reader would hit. So: for any material whose purpose is to *make an agent produce something*, the audit is a usage trial, and reading is only how you form hypotheses to test. Run the trial before writing recommendations, not after — otherwise the write-up is sunk cost arguing against the evidence. Corollary, learned the same session: an audit's deliverable is ranked findings, not a work program; ~7 verified small defects became a 5-chunk plan with 12 new rules before the owner cut it back to the defects. Relates to Proportional Effort (#11 — which the methodology states for artifacts and rigor but not for the size of a response to a finding), Retrieval Over Generation (#24), and Honest Confidence (#5).

## In an append-heavy file, a union merge is safe only when neither side RELOCATED an entry — a moved item reads as "absent here, present there," which is exactly the shape a union is built to merge

Integrating `develop` into a 40-commits-stale feature branch produced four conflicts, all append-collisions in `.prawduct/` markdown, zero in code. Three were straight unions. The fourth was not: `develop` had marked BLD-7K3Q `status: shipped` and **moved it into the archive section**, while the feature branch still carried it `open` at its original position. Git presents that as "our side has content, their side is empty" — indistinguishable from an ordinary one-sided append — so a mechanical union would have resurrected finished work as a live duplicate item, in the file that decides what gets worked on next. The check that caught it costs one command: for each item the union would keep, ask whether the *other* side has that id anywhere else in the file, not just at the conflict anchor. So: before unioning a conflict in a newest-first ledger (backlog, change-log, learnings), diff the **id sets** of both whole files, not the hunks — an id present on both sides at different offsets is a relocation, and relocation is the one case union gets wrong. Corollary: a resolution that drops a side also drops any evidence that accumulated only there (here, a recurrence note whose residual was still live), so read what you are discarding rather than only what you are keeping — merge resolution is a place evidence evaporates with no diff to show for it. Discovered 2026-07-28 (v3.2.0 develop-integration). Relates to Coherent Artifacts (#13), Validate Before Propagating (#15).

## "Advice fails soft" is not "advice fails silent" — a degraded advisory path must still name its consequence, or it manufactures the false success it was meant to prevent

Same chunk, second instance of the same class. `architecture.md`'s ratified norm reads "advice fails soft… a probe that errors is swallowed with attribution, not raised" — and its own words are *degrades to a note*. I read the norm as license to swallow, and left handoff generation as the one failure path in `cmd_clear` that printed nothing, while every sibling (session-start write, each session-file unlink) named what the user loses. Consequence: an agent that wrote a forward note, watched `/clear` exit 0, and reported "safe to `/clear`" was wrong, and nothing told anyone — which is precisely the silent-success defect the chunk existed to repair, reproduced inside the repair. So: when a norm says a path may not *block*, that constrains the exit code, not the diagnostic. Ask separately "who is harmed by this failure, and how would they learn?" — if the answer is "nobody tells them," the soft failure is incomplete regardless of the norm. Discovered session-handoff-continuity Chunk 01 (2026-07-26, Critic warning). Relates to Honest Confidence (#5) and Living Documentation (#3).

## A fix lands at the instance a review named; the defect lives in the class — so before closing a finding, name the class and route it through one owner, because every local fix looks complete from inside itself

Three instances in one bundle, which is why this is a rule and not an anecdote. (1) CRT-7B4M shipped the git-derived "which chunk is current" for `infer-critic-mode` alone; the identical defect then surfaced at `verify-chunk-refs` (BLD-7K3Q) and at the session handoff (SCN-4H9T) — three consumers, one root cause, fixed once locally and twice more later. (2) The Chunk 01 Critic's central catch produced the rule "make the state representable," and it was applied to `_read_handoff_notes` — while its sibling `_read_unmarked_handoff`, *three lines below*, kept returning a string whose emptiness meant absent / machine-generated / **unreadable**, and the Chunk 02 Critic found it as BLOCKING. The learning had been written the day before, from that very function's neighbour. (3) Chunk 02's own sweep moved three git helpers into one module and pinned them out of the old one — while the *composition* they served ("try git, else checkboxes") stayed written in two places, so a third progress signal would have diverged the consumers again with the pin still green. So: a finding names a location; ask what class it belongs to and sweep the class. Prefer sweeping **by construction** — one owner every consumer must go through — over sweeping by enumeration, because enumeration is a list that the next consumer is not on. Corollary with teeth: a consolidation pin that asserts where a SYMBOL lives does not assert where a DECISION is made; pin the decision. Second corollary, learned the hard way over three consecutive review rounds on one class (a build-plan read decoding with the operator's locale, so two readers of the same file disagree about whether it parses): each sweep reached exactly as far as the unit being edited — the function, then the module — because **a boundary you are inside is invisible**, which is what makes this recur rather than what makes it careless. So when a class comes back a THIRD time, stop sweeping and make it enforceable: a pin is checked by something with no field of view. The tell that you are still sweeping by attention is a commit subject claiming the class is handled. Discovered session-handoff-continuity Chunk 02 (2026-07-27, Critic blocking + warning ×3 rounds). Relates to [[When a guarantee names a specific event, gate on THAT event]], Root Cause Discipline (#16) and Close the Learning Loop (#18).

## A CLI on `$PATH` is a different checkout from the worktree you are editing — an interactive command's exit code is not verification evidence for a change to that command

The Chunk 02 Critic coordinator traced a lead that did not reproduce: it ran `prawduct-hook verify-chunk-refs` and got the pre-fix answer, because bare `prawduct-hook` resolved to the *installed plugin* (`~/source/prawduct`, on `main`) while the fix lived in the feature worktree. It corrected itself in the review, and the hazard generalizes past that one command: in any repo whose own tool is installed globally — a plugin, a CLI, an editable package — the shell reaches for the installed copy while you are reading the edited one, and the two agree just often enough to be trusted. The tell is a live check that disagrees with a passing test suite, and the instinct to believe the CLI. So: invoke the artifact under test by explicit path (`python3 plugin/bin/tool`, `./bin/tool`) whenever the change IS the tool, and say which copy ran when citing the output as evidence. This also bites the dogfooding case in the other direction — this repo's own `/clear` hook ran the installed `main` build all session, so Chunk 01's shipped forward-channel code was not the code that processed the notes file. Discovered session-handoff-continuity Chunk 02 (2026-07-27, Critic note). Relates to Honest Confidence (#5) and Validate Before Propagating (#15).

## When you relocate importable code behind a conftest sys.path shim, standalone/non-collected scripts do NOT get the shim — grep for `__main__` scripts that self-insert the old root and fix each, because conftest only fires under pytest

Confirmed 2026-07-24 (SPIKE-S2 harness, v3.2.0 Chunk 05). The v3.1.1 relocation moved `lib/` under
`plugin/` (GOV-4H7T) and updated `tests/conftest.py` to insert `plugin/` — which silently rescues every
pytest-*collected* test whose own `parent.parent` self-insert now points at the wrong root (the insert
became "harmless redundant"). But `tests/spikes/s2_migration.py` runs *outside* pytest (dev-only,
operator-run), where conftest never fires, so its stale self-insert was load-bearing and left the script
dead on `import` (`ModuleNotFoundError: No module named 'lib'`) for a full minor version — undetected
because no CI test imports it. Lesson: a conftest path shim makes collected tests lie about whether their
own path setup is correct; when you move importable code, the collected suite passing proves nothing about
standalone scripts. Grep for `if __name__ == "__main__"` files (and `bin/` entrypoints) that compute a
root and `sys.path.insert` it, and fix each to the new layout. Relates to "no pre-existing exception" (a
found breakage is yours to fix or flag) and Honest Confidence (#5 — green collected tests are not coverage
of uncollected code).

## Before predicting a per-minute rate ceiling will engage, check whether serial round-trip latency already caps throughput below it — a rate ceiling is bounded by requests/min = 60 / round-trip-seconds, so it never binds on TOTAL volume no matter how large; it binds only when you issue requests concurrently/batched faster than one round-trip drains

Confirmed 2026-07-24 (SPIKE-S2 live dry-run, v3.2.0 Chunk 05 → VRF-009). I forecast the `--archive-scope
all` burst (147 archived items, create-then-close) would breach the Pacer's 900-pts/min ceiling
(`rest_point_waits > 0`) because 147 sits "comfortably over" a ~75-item threshold I invented. The live run
reported `rest_point_waits: 0` and `content_creation_waits: 0` — *neither* ceiling engaged. The error was
conflating **total volume** with **per-minute rate**: the serial `gh` importer does ~1.3s per archived
item (~11 pts: read+create+close), so peak ≈ ~500 pts/min — under 900 regardless of total count. 5,360 pts
over ~18 min = ~296 pts/min average. There is no total-count threshold for a rate ceiling under serial
I/O; the ceiling would bind only under parallelized writes. So the settled NFR §9 S2 fact is the opposite
of the forecast: the Pacer budgets are a non-binding safety belt for the serial importer, and wall-clock
is latency×call-count, not pacing-limited. General rule for any "will we hit the rate limit?" question:
compute the achievable request rate from the round-trip time first (it's the ceiling on the ceiling); a
plausible volume-based argument is not a rate argument. Relates to Honest Confidence (#5), Root Cause
Discipline (#16), and Retrieval Over Generation (#24 — the spike is the cheapest check that changes the
recorded constant).

## When a release has two documents tracking its state, one is already wrong — designate a single live tracker and demote the other to a decision record; and author each build chunk from the TREE, never from the upstream plan, because a plan derived from a plan describes intent the code may have overtaken

Confirmed 2026-07-24 (v3.2.0 pre-ship audit). One root cause, two symptoms, both found in one sitting.
**Symptom A — plan-vs-plan.** `release-plan-backlog-service-golive.md` and `build-plan-v3.2.0-golive.md`
both tracked v3.2.0 state. By day four, 11 of the release plan's 21 ship-list rows were stale, four of
its five `blocker` rows were built, and the two documents *directly contradicted each other on the
critical path*: the release plan said the long pole was a discovery spike that had been settled the day
before, while the build plan said the long pole was the migration. Nobody was misled only because the
build plan happened to be the one being read — that is luck, not a control. **Symptom B —
plan-vs-tree.** Two chunks (05's MG4 scrub workflow, 07's briefing repoint) were authored from the
release plan rather than from the code, and BOTH were already fully built when finally read against the
tree; each was minutes away from being re-authored. **The shared cause is derivation from a document
instead of from reality.** Two rules follow. (1) Exactly one artifact holds live release state; every
other release-adjacent doc is explicitly demoted to a decision record, keeps only what nothing else
records (owner decisions, ratified rationale, sequencing rules), and says so at the top — re-ticking a
stale tracker just restarts the drift clock. (2) A build chunk's step 0 is a scoping read against the
tree; "the plan says this is unbuilt" is a hypothesis, not a finding. Note the asymmetry that makes this
cheap to act on: reading the tree first costs minutes and the failure it prevents is building something
twice, or worse, "fixing" working code to match a stale description. Relates to Living Documentation
(#3), Validate Before Propagating (#15 — a plan is an intermediate output), Coherent Artifacts (#13),
and Retrieval Over Generation (#24).

## When a guard test pins a safety claim, assert the PROPERTY, not one spelling of it — a test that matches a literal (an exact flag token, an exact grant string, a substring anywhere in a file) passes for every rewording of the same defect, so write the check to answer the question the property asks and verify it red against a DIFFERENT phrasing than the one that prompted it

Confirmed 2026-07-24 (v3.2.0 cumulative Critic — three instances surfaced in a single review, two of
them in guards written days earlier specifically to prevent the class). **(a)** BKL-8V3D's guard scanned
for the flag tokens `--apply`/`--dry-run` in backlog instruction surfaces. The very branch that shipped it
introduced a *mechanism* claim — "the primary guard is the adapter's target-pin", a thing that exists
nowhere in the code — and the guard could not see it, because it was hunting flags. **(b)** BKL-5N9W's
grant test asserted the absence of exact strings like `Bash(prawduct-hook backlog import *)`; a
**broader** wildcard, `Bash(prawduct-hook *)`, re-granted every withheld high-consequence op with all
three tests green. Widening is the most natural way that rail ever gets dismantled, and the test was
blind to precisely that. **(c)** My first fix for (a) used a "backing token must appear in the adapter
source" check — which passed, because the token appeared in a *docstring*, reproducing one level up the
whole-file-substring flaw I was fixing. The shared shape: **the property is semantic ("does any granted
pattern permit this command?", "is this named mechanism implemented?") and the test asked a lexical
question instead.** Two rules. (1) Write the check as the property's own question — expand grant patterns
and test whether they *match*; resolve claimed mechanisms against an explicit allowlist of what exists
(an allowlist fails safe; a source-scan heuristic fails open, and unknown-is-unbacked forces a deliberate
review when something real ships). (2) **Verify red against a different phrasing than the one that
prompted the guard** — re-running the original defect only proves the test remembers its origin story. A
line-wide negation filter I wrote also swallowed the exact claim it targeted, because the offending line
contained an unrelated "not"; only injecting a *variant* exposed it. Relates to Tests Are Contracts (#1),
Honest Confidence (#5), and the false-reassuring-claim-in-an-instruction-surface class BKL-8V3D named.

## When the deliverable is INSTRUCTIONS, at least one guardrail must model the READER — tests that measure the artifact (size, budget, "the right words are present") all pass while the instruction has no effect, because none of them read the file in the order an agent reads it

Confirmed 2026-07-30 (record-mechanization Chunk 03). A per-mode payload split gave `chunk` and
`verify-resolutions` reviewers a self-contained `goals-1-3.md` and routed them there at step 2 of the
Critic skill — an 83% token cut, six guardrails, every one mutation-proved. It did **nothing**.
`SKILL.md`'s header is the first instruction in the skill body and it said to read
`review-protocol.md` "(read this first)", twenty-six lines above the routing, without naming
`goals-1-3.md` at all. Agents obeyed the header, loaded the full 10,519-token predecessor payload, and
only then reached the instruction telling them not to. The reviewer that caught it did so by *doing*
it and reporting its own token spend as the evidence.

Every guardrail stayed green because every guardrail measured **file sizes**. "The bytes are correct"
and "the behavior is correct" are different claims for an instruction file, and size-shaped tests only
ever prove the first. The reader-shaped questions are: what is read *first*, what is read
*unconditionally*, and does an earlier directive outrank a later one? Write at least one test that
asks those — assert reading ORDER and unconditional citations, not just presence and budget.

Two riders, both paid for in the same work cycle. **(a)** The first cut of those reader-shaped tests
had the same disease one level up: the fast-path check excused any *line* containing "final", and the
single-pass roster bullet permanently contains "small `final`/`cumulative`" — so the one line that had
carried half the defect was excluded unconditionally, and "mutation-proved" was true of one leak and
false of the other. Judge the **citation in its own clause**, never the line it sits on. **(b)** A
reviewer running on a cached pre-fix skill body cannot measure the fix: the acceptance evidence for an
instruction change has to come from a **fresh session**, and a same-session reading proves nothing.

Instance of the "assert the PROPERTY, not one spelling of it" rule above — the header test I first
wrote pinned the literal string "read this first", which any rewording would have walked past.
Relates to Tests Are Contracts (#1) and Honest Confidence (#5).

## A review ending is not a filing event — dispose every non-blocking finding as FIX or ACCEPT, and treat FILE as the narrow case clearing THREE bars: it names its trigger, the work is **large** (a chunk's worth, not an hour's), and it cannot be absorbed into the current work. **Deep context on a small problem is a FIX signal, not a filing signal.**

Scope of the three bars: "cannot be absorbed" means own design, own review, or genuinely orthogonal. Owner-requested 2026-07-29; the binding statement is `skills/critic/review-cycle.md`'s FILE bullet, and this entry must not drift from it.

Because "file the rest" is a disposal route and thorough reviewers produce many findings. An ACCEPT is Principle 2's *explicit descope*: recorded as a fact (`prawduct-hook disposition … --accept "<reason>"`) and rendered into the change-log entry for that work with `render-dispositions`, where the next reader of the change meets it — not a backlog id nobody will action, and not a count hand-written into prose, which drifts. Measured on this repo when the rule was still "file the rest": open items **50 → 180 in 26 days**, 67 of them Critic-sourced, **53 of those never touched since filing**, 58% of all Critic items ever filed still open, and 42 of 67 sitting at `effort: S` — the band where filing costs more reader-attention over its lifetime than the fix costs. The compounding tell is the sharpest signal: **`verify-chunk-refs` alone accumulated SIX open items**, each a facet found by a *later* review of the same still-unfixed gate — filing made every pass re-discover the mechanism instead of closing it, so the backlog grew while the defect stayed. A double-digit filing count is not thoroughness, it is undisposed review. Framework-specific corollary: a framework that does this to itself does it once per build plan to every repo that adopts it. Relates to Principle 2 and [[When a scope narrowing is recorded, it is a CASCADE, not an annotation]]

## Widening a predicate takes TWO searches: grepping the pattern finds its DUPLICATE COPIES, never the CALLERS that branch on the predicate it backs. So grep the *shape* for copies, then the *predicate's name* for branches; a survey that ran only the first is incomplete however clean it looked. Generalizes to any shared predicate — a validator, a feature flag, a type guard

Chunk 05c widened an id-shape regex; `grep -rn "A-Za-z0-9"` correctly found all four copies (and caught a third the inherited plan had missed), so the survey felt complete and stopped. It was blind by construction to `core.resolve_ref`, which gates an alias round-trip on `is_pfx` — the Critic found it. `grep -rn "is_pfx"` takes seconds and was never run. The consequence was cost plus a widened ambiguity class, not a break, but nothing about the method would have caught a break either. . Relates to [[A completeness claim states the COMMAND that would falsify it and asserts that command now returns nothing]] (same enumeration-wearing-a-query's-clothes failure, one level up: a correct query against the wrong axis) and Root Cause Discipline (#16)

## A spike that discards its code leaves its numbers unfalsifiable — commit the derivation as a runnable script and cite the command, never the digits, because a count transcribed into prose goes stale silently as the corpus grows; the fix is not counting more carefully but moving the count out of prose entirely

Confirmed 2026-07-31 (record-mechanization Chunk 05, the change-log ledger spike). `change-log-ledger-design.md`
§1 opened with a hand-authored tag census that matched **no** query over its own named tree, and the wrong
sizing had already propagated into the migration plan's conversion and archive sets. A design artifact whose
entire thesis is *mechanize hand-authored records* was itself carrying one — the disease found in the
prescription.

**The correction then repeated the offence twice**, which is the part worth keeping. Replacing the census by
hand produced a claim about tag-key ordering *inferred from a count rather than measured*, and totals stated
at a tree the shipping commit no longer described. Counting more carefully is not the fix; a number in prose
has no owner and no tripwire, so it rots at the next merge whoever wrote it.

The structural fix was to stop having a number: `tests/spikes/change_log_roundtrip.py` ships as the oracle,
takes any ref, self-checks its own partition arithmetic, and the artifact cites the command. Two review
findings retired at the mechanism instead of by footnote. The owner's intervention — *"are we getting caught
up in numbers again?"* — is what reframed a correction into a structural fix, and is the tell to watch for:
hand-correcting a count is the moment to ask why the count is in prose at all.

Relates to [[A completeness claim states the COMMAND that would falsify it and asserts that command now returns nothing]]
(same move — cite the falsifying command, not the tally), Living Documentation (#3), and Root Cause
Discipline (#16).

## Routing a filing to the handoff is NOT filing it — file the item the moment you decide it should exist, because a handoff note is read by a session that arrives with its own plan and treats an inherited instruction as context rather than work, and an unwritten handoff (crash, context exhaustion) loses it outright; "later" has two independent ways to never happen and costs the same as now

**The evidence.** Two items — `render-dispositions` rendering only the newest review, and a fixed
NOTE having no honest disposition kind — were identified during a wrap-up on 2026-07-30 and written
into `.handoff-notes.md` under the heading **"FILE THIS FIRST — a real gap, deliberately not filed
mid-wrap."** The routing note even argued its own timing: the next session was a backlog-triage
session with the skill loaded and the corpus open, "the natural place." That session ran a full
three hours, worked the backlog corpus directly, filed nothing, and routed **two more** items to the
handoff by the same mechanism. It then died to a Claude Code segfault before writing that handoff at
all. All four were filed on 2026-07-31 as `CRT-9K2P`, `CRT-3F7T`, `GOV-5N8R`, `GOV-2H6X`.

**Two independent failure modes, one cause.** The deferral targets an actor who does not yet exist.

1. *The successor deprioritizes it.* A handoff note is read as **context** by a session that arrives
   with its own plan. "FILE THIS FIRST" is an imperative to its author and a background fact to its
   reader. Being explicitly right about the timing did not help; the note correctly predicted the
   conditions and the successor still did not act.
2. *The handoff never gets written.* Everything between "decide to file" and "write the notes" is a
   window in which the item exists only in one process's context. Three of the four survived only
   because the disposition prose independently said "routed to the handoff" in durable text. A crash
   one round earlier would have left no trace that anything was owed.

**Why the mid-wrap objection is wrong.** The reason given for routing rather than filing was to
avoid doing unrelated work mid-wrap. But filing costs one skill invocation against a corpus already
open, whereas routing costs the same note *plus* the successor's re-reading, re-deciding, and
re-deriving the item body from prose written for a different purpose. The deferral is not cheaper;
it is the same cost paid later, with two ways of not being paid at all.

**Scope, and what this does not say.** This governs what happens *after* you have decided an item
should exist. Whether it should exist at all is a different question, already governed by
[[A review ending is not a filing event — dispose every non-blocking finding as FIX or ACCEPT, and treat FILE as the narrow case clearing THREE bars]]
— and that rule's preference for FIX over FILE is untouched here. If the answer is FIX, fix it now;
if the answer is FILE, file it now. "Route it" is not a third answer. Relates to Complete Delivery
(#2) — a routed item is a requirement in flight with no owner — and to Close the Learning Loop (#18),
since the same mechanism carries learnings forward and fails the same way.

**Operative form.** The wrap-up **files**; it does not route. A handoff note may *mention* what was
filed and why it matters next, but the item must already have an id by the time the note names it.

## Green is evidence ONLY about what could have made it red — for each test name the change that would turn it red; if you cannot, it measured nothing. The fixture may never reach the subject; a constant-equality assertion survives an inverted comparison while its NAME convinces the reader it is covered. Same for a live probe: say what a FAILING run would have looked like before recording one

Written 2026-08-01 from the discodon retrospective (`documentation/LEARNINGS_VERIFYING_TEST_
INFRASTRUCTURE.md` in that repo), which recorded four false claims across twelve Critic rounds.
Six mechanisms were named there; five of them are this one rule, and the sixth is the
text-anchored-edit rule below.

**The question that does the work is not "is this tested?" but "what change would turn this
red?"** Those feel identical and are not. The first is answered by the test's *existence*; the
second requires naming a concrete mutation, and the naming is where the defect surfaces. A test
whose falsifier you cannot state is a test that is passing for a reason you have not identified —
which is indistinguishable, from the outside, from passing for the right one.

**Why this rule needed writing when the corpus already had nine members of its family.** Each of
those nine named one *shape* of the failure: the constant that is pinned instead of the
threshold, the fixture frozen at one instant, the arg guard that rejects rather than accepts, the
substring that any longer sentence satisfies, the proxy that co-occurs with the event. A reader
meeting a new instance matched none of them, because the instance is always new. The general
question generates all nine and the tenth. That is the collapse this rule was written to head —
the nine retired *into* it on 2026-08-01, each leaving its instance behind in one of the four
destinations, because a general statement with no instances is exactly as inert as nine instances
with no general statement.

**The instances that are hardest to see, and why they are grouped where they are.** The fixture
that never reaches the subject is the one this repo reproduced three times in a single sitting
while *fixing* it (files committed into the baseline → empty diff; tests outside `tests/` → no
roots discovered; a negative case that fired because an uncommitted test file is itself a judged
change). Its sibling — the constant-equality assertion — is worse, because the assertion's *name*
does the convincing: `test_threshold_is_enforced` reads as coverage while the body compares a
literal to itself and survives an inverted comparison intact.

**The live-measurement half was a separate rule and should not have been.** Before recording a
probe's result as settled fact, state what a failing run would have looked like. It is the same
discipline pointed at measurement rather than at a test, and it fails the same way — a
measurement with no describable falsifying observation measured nothing, and the "fact" is an
artifact of the instrument. It was misfiled into the claims family by keyword and reclassified
here in the approved collapse map.

Relates to Tests Are Contracts (#1), Honest Confidence (#5), and Root Cause Discipline (#16).

## A text-anchored edit changes a NEIGHBORHOOD, not a point — the anchor names a line, but the insert lands in a structure extending past it, and both still compile. Inserting at a `def` puts the function between the next one and its decorator; restructuring `try/except` into `try/except/else` strands the fallback in `else`. Re-read the enclosing block after every anchored edit; the suite stays green

Written 2026-08-01 from the discodon retrospective's mechanism 3, plus the concrete defect its
mechanism 6 produced. **This is the defect class the agent's own editing tools manufacture**, and
nothing in the corpus covered it.

**The mismatch is between how the anchor is chosen and what the edit changes.** An anchor is a
line — a `def`, an `except`, a closing brace. The edit's *effect* is scoped to whatever syntactic
structure encloses that line, which extends past it in both directions and is invisible in the
matched text. So the operation reads as pointwise and is not.

Two instances, both observed:

- Inserting a new function "at" a `def` line places it between the *next* function and that
  function's decorator. The decorator now decorates the new function; the old one is bare. Both
  parse. Both import. Whatever the decorator registered is silently unregistered.
- Restructuring `try/except` into `try/except/else` moves the code after the `try` block into
  `else`, which runs *only when no exception was raised*. A fallback that existed to handle the
  exception path is now unreachable on exactly that path. The module compiles and the happy-path
  tests pass.

**Both stay green**, which is why this is not caught by the suite and has to be caught by the
edit. That is also the connection to the rule above: the tests that would have gone red are the
ones nobody wrote, because nobody knew the neighborhood had changed.

**The act:** after any text-anchored edit, re-read the *enclosing block*, not the diff hunk. A
diff shows the lines you changed; the defect is in the lines you did not, whose meaning your
change altered. Where the language has structural editing (an AST-aware tool, a language server
rename), prefer it — it operates on the structure the anchor only approximates.

Relates to Tests Are Contracts (#1) and Validate Before Propagating (#15).

## Exactness is owed to a number something RELIES ON for a decision, not one something merely READS — ask what branch is taken differently if it is wrong by two, and if none, the precision is waste. Reading is passive and nearly universal, so "something reads it" licenses precision everywhere; verify the CONSUMER before defending the cost you already paid for it

Owner-originated, 2026-08-01, correcting a formulation of mine that was one word too weak.

**The case.** `test-evidence record --no-rerun` restamped the suite record at 3125 while the
tree had 3127, because two tests had just been added. I re-ran a 96-second suite to correct it,
and justified the exactness with a *subtraction tripwire*: a count that drops from 3127 to 3100
means twenty-seven tests silently vanished, which a qualitative "more than 3000" cannot detect.

**The tripwire does not exist.** Checked afterwards, on the owner's push: in `plugin/lib/gates.py`
and `plugin/bin/prawduct-hook`, `passed` is *type-checked* (int, and explicitly not bool) and
displayed. Nothing compares it across runs. The only predicates on the counts anywhere are
`failed > 0` and `failed == 0`. So the re-run bought nothing, and the argument for it was
assembled after the fact to defend a choice already made.

**Why "relies on for a decision" beats "something reads it".** My version licensed precision
almost everywhere, because reading is passive and nearly universal — a human skimming a status
line reads it, a log aggregator reads it, a report prints it, and none of them do anything
different at 3125 than at 3127. A test that fails to exclude anything is not a test. The
owner's version names the mechanism instead: a number earns exactness **iff some branch is taken
differently at different values**, which reduces to one question you can actually answer —
*what decision changes if this is wrong by two?*

Note the shape it shares with the discrimination rule above it: green is evidence only about
what could have made it red; a number is worth precision only if some value of it would change
an action. Both are the same demand for a counterfactual, one aimed at tests and one at data.

**Two corollaries worth keeping.** (1) The reach is the tell — this is an instance of *the
rationale you reached for to defend a decision already made is the one to verify*, and it was
committed inside the very session that wrote that rule into the corpus. (2) Precision that a
**machine** maintains is still not automatically justified; free-to-maintain is not the same as
load-bearing. What genuinely survives from the weaker version is narrower: a number in *prose*
is a hand-maintained copy that drifts, which is why `record_lint`'s `suite-total-claim` check
exists.

Relates to Proportional Effort (#11), Honest Confidence (#5), and Retrieval Over Generation
(#24) — the cheapest check that could have changed this decision was one grep for the count's
consumers, and it cost seconds against a 96-second re-run.

## A completeness claim asserts the falsifying COMMAND now returns nothing — never a count of sites fixed, which is true of any prefix of the real set. The query is itself a mechanism and can carry the defect it hunts: normalize the text before searching, because line structure is not semantic structure, and query the CONCEPT, not the phrasings you already found wrong

Collapse destination written 2026-08-01 (learnings-firing Chunk 03), absorbing two rules whose
instances are inline above: the completeness-claim rule and the falsifying-query-carries-the-defect
rule. Both are about the *query*, which is why they merged rather than joining the general
claim rule.

The count-of-sites failure is the common one: "fixed 7 sites" is true of any prefix of the real
set, so it is compatible with 30 remaining. The query corollaries are less obvious and were
learned separately — a grep built from the spellings you already found wrong is an enumeration
wearing a query's clothes, and line structure is not semantic structure, so a claim spanning two
lines survives a search that assumes one.

**This rule caught its own author within the hour it was written.** An ad-hoc drift check matched
one hit and briefly convinced me the retirement had leaked lifecycle metadata into this file. It
had not: the hit was a *quoted example* inside the narrative of the learning about that very bug —
comment-shaped prose, not a comment. The authoritative guard is correctly narrower (it requires
the line to *start* with `<!--`). Same shape as `record_lint`'s `dangling-ref` check, removed
after measuring 0 true positives because every hit was path-shaped prose.

## Reads as evidence, is not: an absence-claim citing a path that does not RESOLVE, a missing directory returns the same empty result as the claim being true; a disposition recorded from intent, not the diff, which the next reader trusts INSTEAD of the findings; a commit crediting a backlog item by TITLE while its filed reproduction still reproduces; and a subagent's COUNT or LIST, a lead

Collapse destination written 2026-08-01, absorbing four rules that share one shape: **a thing
that occupies the position of evidence in an argument while establishing nothing.**

They were four separate rules because each was learned from a different accident, and the
instances are what let a reader recognize their own. The absence-claim case is the sharpest —
seven sites asserted "no GraphQL in `lib/backlog/`" after the tree became `plugin/lib/backlog/`,
so the grep that "confirmed" it was confirming only its own bad path, and a missing directory
returns exactly what a true claim returns. The disposition case is load-bearing because the
record is what the next reader trusts *instead of* re-reading the findings, so a wrong one is
worse than none. The backlog case: a fix aimed at an item's title routinely lands the adjacent
sub-case, passing every guard while the filed reproduction still reproduces.

## A passing assertion may be satisfied by something other than the property — an unimplemented flag passes because the arg guard REJECTED it (assert success BEFORE absence); a prose SUBSTRING stays green under any longer sentence containing it (when prose changes meaning, grep tests asserting FRAGMENTS, not just failing ones); a proxy passes every test you thought to write — gate on the named event

Collapse destination written 2026-08-01, absorbing three rules. The unifying question: *what,
other than the property, could satisfy this assertion?*

The arg-guard case inverts the usual reading — the test passed because the flag was **rejected**,
so "no output" was produced by the error path rather than the feature. Assert success first, and
absence only after. The substring case stops being a contract the moment someone writes a longer
sentence containing the fragment; its second half is the actionable one, because when prose
changes meaning the tests that need auditing are the ones asserting *fragments*, not the ones
that failed. The proxy case is the hardest to see from inside: a signal that usually co-occurs
with the event passes every test you thought to write, **because you wrote them believing the
proxy** — so the tests inherit the error rather than detect it.

## A fixture's world is narrower than the requirement it certifies — the COMMON instance narrows the requirement to itself, so check coverage against its stated BREADTH; the framework's OWN state stands in for the propagated contract, so assert what reaches consumer repos; one moment stands in for the procedure's transitions; and the collision case is unwritten when the fan-out key is not unique

Collapse destination written 2026-08-01, absorbing four rules. The shape: **the fixture is a
world, and it is smaller than the requirement.** The test is honest about its world and silent
about the gap.

The breadth case generalizes the rest — when a requirement says "across all cases" and the
available example is one case, the example silently becomes the requirement. The propagated-contract
case is the one that bit this very chunk: a guard reading *this repo's* `learnings.md` stayed
green while every newly onboarded product received an instruction pointing at a marker its
starter file did not contain. The single-moment case applies to any gate living inside a
procedure — the fixture encodes one instant and misses the step where the procedure changes the
data the gate reads.

## A test inherits inputs nobody declared and properties nothing observes — machine state, a load-dependent race in setup, and a value silent by construction, so a stage whose worth is SPEED needs a test that fails when it stops being fast. Mutation is one-directional — reverting removes the damage alongside the fix — so pair it with branch coverage of the function you touched

Written 2026-08-01 from the discodon retrospective's mechanisms 2, 4, 5 and 6.

**Undeclared inputs** are the ones a passing suite cannot distinguish from correctness: machine
state a branch happens to depend on, and a load-dependent race in setup that resolves the right
way on an unloaded laptop. **Silent-by-construction properties** are worse, because nothing is
even nominally watching — a stage whose entire value is *speed* has no failing observation when it
stops being fast, so its guarantee decays without a single red test.

**Mutation testing's blind spot is directional and easy to miss.** Reverting your change removes
the damage *alongside* the fix, so the run answers "is the line I added covered?" and never "what
did my change break beside it?" Pair it with branch coverage of the function you touched. This
was proved twice in one session: a guard whose print site was never exercised (only its predicate
was, so inverting the trigger left the suite green), and a `limit` guard added on 2026-08-01
whose first three tests all stayed green when it was removed, because every fixture reached the
subject by another route.

## A self-authored adversarial pass inherits the author's blind spots — the cases you think to attack are drawn from the same model that wrote the code, so the gap that survives is the one you cannot see. Get the adversarial read from a context that did not write the subject, or pick the attack from a roster you did not author

Split out on 2026-08-01 from the fan-out collision rule, whose second clause this was. It earns
its own entry because it is not test discipline — it is a claim about *who* can verify, and it is
the reason this project's Critic runs as a separate agent with its own context rather than as a
self-review step (Principle 14, Independent Review).

The mechanism is that your attack roster and your implementation come from one model of the
problem. Every case you think to test is a case you already considered while writing, which is
exactly the set that is already handled. What survives is what you never modelled — and no amount
of care applied from inside that model reaches it.

Evidence from this session: three reviewers running independently each found the same defect I
had not seen (retirement duplicating headings in this file), and the reviewer that found the
widest-reaching one — a shipped pointer resolving only in the framework repo — was reasoning
about consumer repos, which the author was not. Corollary for the cheap case: where a separate
context is not available, take the attack from a roster you did not author, so at least the
*selection* is not yours.

## Historical (structurally enforced)

Learnings retired by `audit-learnings --apply`, for one of two reasons, stated on each entry: a declared `sentinel=` test now passes, so the failure mode is structurally enforced; or a broader rule superseded it, in which case the entry names its replacement. Kept here as historical context.

## Pinning the CONSTANT a threshold uses is not testing the threshold — exercise the firing path and prove it by mutation, because a constant-equality assertion survives an inverted comparison while its name convinces the next reader the path is covered

*Retired 2026-08-01 — superseded by **Green is evidence ONLY about what could have made it red — for each test name the change that would turn it red; if you cannot, it measured nothing. The fixture may never reach the subject; a constant-equality assertion survives an inverted comparison while its NAME convinces the reader it is covered. Same for a live probe: say what a FAILING run would have looked like before recording one**. That rule is the active statement; this one is kept for readers who remember it.*

`TREE_COUNT_ADVISORY`'s test was named `test_advisory_fires_at_the_documented_trigger` and asserted exactly one thing: `== 10_000`. The class's only behavioural assertion was the *negative* case (`'NOTE:' not in stdout`, far below the trigger), so flipping `>=` to `>` — or breaking the f-string — shipped green. The recursion is the lesson: this was the test written to close a finding whose thesis was *"a trigger nothing observes"*, and it reproduced that defect one level up. The trap is that a constant feels like the behaviour because the constant is what the plan talks about; asserting it discharges the *documentation* of the threshold and none of the threshold. Mechanics: patch the trigger DOWN to meet a small fixture rather than building a fixture large enough to meet the trigger, and assert at the boundary (fires *at* the count, silent below) so `>=` vs `>` is pinned. Then mutate and watch it fail — four minutes, and it converts "this test looks right" into "this test detects the failure it names," which matters because the old test also looked right. Same discipline caught a narrow `startswith("archive")` masquerading as a four-word resolved-section check: the test only exercised `## Archive`, which both predicates excluded. Discovered 2026-07-29 (coverage-perf verify-resolutions; recurred in release-readiness). Relates to Tests Are Contracts (#1), [[A test that asserts a SUBSTRING of prose stops being a contract]].

## A gate that lives inside a procedure must be tested across the procedure's own state transitions, not at one instant — every fixture encoding a single moment will miss the step where the procedure changes the data the gate reads

*Retired 2026-08-01 — superseded by **A fixture's world is narrower than the requirement it certifies — the COMMON instance narrows the requirement to itself, so check coverage against its stated BREADTH; the framework's OWN state stands in for the propagated contract, so assert what reaches consumer repos; one moment stands in for the procedure's transitions; and the collision case is unwritten when the fan-out key is not unique**. That rule is the active statement; this one is kept for readers who remember it.*

`check-releasability` (release runbook Phase 0) enumerates release-pending scopes as "tagged, no `release=`". Phase 1 step 3 then *stamps* `release=` on the shipping set — so on any second Phase 0 run those scopes have left the pending set, and the orphan check reported every successfully classified scope as a stale table row. The gate would block the release it had just approved, and no test could have caught it because each fixture encoded one point in time. Generalises `building.md`'s multi-hop rule: there the hops are subsequent invocations of a function; here they are *phases of the runbook the gate is embedded in*. So when a gate reads state that a later step of its own procedure mutates, write the fixture for **after** that step too. Corollary found in the same pass: when adding such an exemption, scope it to the disposition that earns it — exempting `withheld` alongside `ships` made a withheld-then-shipped contradiction vanish from `pending`, from the orphan list, and from the summary at once, printing `releasable:`. Discovered 2026-07-29, release-readiness Chunk 01 (Critic warning). Relates to Root Cause Discipline (#16).

## Verify a disposition against the diff before recording it — "fixed" is a claim about the tree, not about intent, and a dispositions record is what the next reader trusts INSTEAD of re-reading the findings

*Retired 2026-08-01 — superseded by **Reads as evidence, is not: an absence-claim citing a path that does not RESOLVE, a missing directory returns the same empty result as the claim being true; a disposition recorded from intent, not the diff, which the next reader trusts INSTEAD of the findings; a commit crediting a backlog item by TITLE while its filed reproduction still reproduces; and a subagent's COUNT or LIST, a lead**. That rule is the active statement; this one is kept for readers who remember it.*

A dispositions change-log entry listed two findings under **FIXED** whose edits were never made; they had been written from what the author intended to do while fixing the others. The verify pass checked each claim against the tree and returned it as BLOCKING — correctly, because the entry's whole function is to let a reader skip re-deriving 30 findings, so one unverifiable claim devalues every acceptance beside it. Two forces produce this: dispositions get written in one sitting *after* the code work, when memory of "I'll fix that too" is indistinguishable from having done it; and the truthful-sounding sentence is cheaper to type than the edit. Fix: write dispositions **from `git diff`**, not from recall, and strike-through-with-annotation rather than silently rewriting when a claim turns out false — the false claim is part of the record. Companion rule from the same review: **record what you declined, not only what you did** — two other fixes landed the code half of a recommendation and dropped the test half, and the entry said "fixed" without noting the drop, which is the same defect one level down. Discovered 2026-07-29, release-readiness Chunk 01 (Critic blocking). Relates to Living Documentation (#3), Honest Confidence (#5).

## Before recording a probe's result as a settled fact, state what a FAILING run would have looked like — if you cannot describe the observation that would have falsified it, the probe measured nothing and the "fact" is an artifact of the measurement Same discipline as a discriminating regression test, applied to live measurement

*Retired 2026-08-01 — superseded by **Green is evidence ONLY about what could have made it red — for each test name the change that would turn it red; if you cannot, it measured nothing. The fixture may never reach the subject; a constant-equality assertion survives an inverted comparison while its NAME convinces the reader it is covered. Same for a live probe: say what a FAILING run would have looked like before recording one**. That rule is the active statement; this one is kept for readers who remember it.*

: SPIKE-S2 timed `pick` at 1/3/5 candidates and read flat latency as proof of a batched fan-out, but the candidate count IS `limit` and `limit` was applied only AFTER the fan-out ran over every eligible issue, so varying it varied nothing; the flatness measured the constant full-scan and the invalid inference was cited as settled across four documents plus the probe's own docstring.

## A completeness claim states the COMMAND that would falsify it and asserts that command now returns nothing — never a count of sites fixed, which is true of any prefix of the real set. Corollaries: run it **whitespace-normalized**, and query the **CONCEPT, not the phrasings you already found wrong** — a regex built from known-bad spellings is another enumeration wearing a query's clothes

*Retired 2026-08-01 — superseded by **A completeness claim asserts the falsifying COMMAND now returns nothing — never a count of sites fixed, which is true of any prefix of the real set. The query is itself a mechanism and can carry the defect it hunts: normalize the text before searching, because line structure is not semantic structure, and query the CONCEPT, not the phrasings you already found wrong**. That rule is the active statement; this one is kept for readers who remember it.*

A line-based pass misses wrapped occurrences, which is why the sweep must be whitespace-normalized.

: "corrected in three places" passed review while six surfaces still carried the claim, two in a file that pass had edited, and the re-run found a seventh (a probe docstring) no enumeration could have reached. Corollaries, each learned by the sweep failing again at the next level: run it **whitespace-normalized** (a line-based pass misses wrapped occurrences), and query the **CONCEPT, not the phrasings you already found to be wrong** — a regex built from the known-bad spellings is another enumeration wearing a query's clothes. Three passes here: named-sites → 7 more; phrase-regex → 4 more (including one asserting the retracted claim in the live tracker, and the probe's own step list)

## An absence-claim must cite a path that RESOLVES, or its verifying command returns empty for the wrong reason — the missing directory produces the same evidence as the claim being true: seven sites asserted "no GraphQL in `lib/backlog/`" after the tree became `plugin/lib/backlog/`, so the grep that "confirmed" it was confirming only its own bad path

*Retired 2026-08-01 — superseded by **Reads as evidence, is not: an absence-claim citing a path that does not RESOLVE, a missing directory returns the same empty result as the claim being true; a disposition recorded from intent, not the diff, which the next reader trusts INSTEAD of the findings; a commit crediting a backlog item by TITLE while its filed reproduction still reproduces; and a subagent's COUNT or LIST, a lead**. That rule is the active statement; this one is kept for readers who remember it.*

## When a commit claims to close a backlog item, verify the claim against the item's FILED CASE before crediting it — a fix aimed at the item's title routinely lands the ADJACENT sub-case, passing every guard while the filed reproduction still reproduces, so merging closes a still-broken item as shipped

*Retired 2026-08-01 — superseded by **Reads as evidence, is not: an absence-claim citing a path that does not RESOLVE, a missing directory returns the same empty result as the claim being true; a disposition recorded from intent, not the diff, which the next reader trusts INSTEAD of the findings; a commit crediting a backlog item by TITLE while its filed reproduction still reproduces; and a subagent's COUNT or LIST, a lead**. That rule is the active statement; this one is kept for readers who remember it.*

`feature/gate-fidelity` commit `af8350f` (preserved at tag `archive/gate-fidelity`) claimed it
addressed "vouching across bundle boundaries (CRT-6J4P)". It did not. CRT-6J4P's filed case is a
*same-lineage* cross-bundle chain: the previously released bundle merged to develop, the new branch
was cut from it, so the anchor's `commit_reviewed` **is** an ancestor of HEAD — `git merge-base
--is-ancestor` returns 0 and rule 1b fires anyway. The branch's ancestor guard closes only the
sibling-BRANCH sub-case, which is CRT-8H3R's territory. Both items live in the same fix family and
cross-reference each other, which is exactly what makes the mis-credit plausible. Diagnostic: before
crediting a fix, re-read the item's filed reproduction and ask whether the guard as written *fires*
on it — a shared area, a shared `refs:` line, and a confident commit message are not evidence.
Mirror of [[When reconciling a backlog item a PR *partly* shipped, read ALL that PR's build-plan
chunks before declaring any leg still open]] — that rule stops a shipped leg being reopened; this one
stops a broken item being closed. Discovered git-state audit (2026-07-19). Relates to Complete
Delivery (#2), Honest Confidence (#5), Validate Before Propagating (#15).

## A test written against a not-yet-implemented flag can pass because the arg guard REJECTED it — assert success before asserting absence

*Retired 2026-08-01 — superseded by **A passing assertion may be satisfied by something other than the property — an unimplemented flag passes because the arg guard REJECTED it (assert success BEFORE absence); a prose SUBSTRING stays green under any longer sentence containing it (when prose changes meaning, grep tests asserting FRAGMENTS, not just failing ones); a proxy passes every test you thought to write — gate on the named event**. That rule is the active statement; this one is kept for readers who remember it.*

Pre-implementation, 11 of 15 new tests failed and 4 passed; two of those passes were free. `--brief-only`
was unrecognized, so the command exited 2 having done nothing — and "no handoff was written" is true
when nothing ran. Absence-of-side-effect is precisely the assertion that cannot distinguish "correctly
skipped" from "never executed." Rule: any test whose assertion is a *negative* (file not created, state
not mutated) asserts `returncode == 0` (or equivalent liveness) first. The detection habit that caught
it: on a test-first run, read **which** tests passed and why, rather than being satisfied that most
failed. Sibling rule for fixtures: to detect "was this rewritten," the fixture must make a rewrite
*observable* — comparing hashes of a file that gets rewritten to identical content proves nothing, so
seed distinct sentinel content. Relates to Tests Are Contracts (#1).

## When a fan-out render keys on a field that isn't unique, test the collision case — and a self-authored adversarial pass inherits the author's blind spots

*Retired 2026-08-01 — superseded by **A fixture's world is narrower than the requirement it certifies — the COMMON instance narrows the requirement to itself, so check coverage against its stated BREADTH; the framework's OWN state stands in for the propagated contract, so assert what reaches consumer repos; one moment stands in for the procedure's transitions; and the collision case is unwritten when the fan-out key is not unique**. That rule is the active statement; this one is kept for readers who remember it.*

When a renderer (or any fan-out) groups/sub-sections by a field, the field's NON-uniqueness is the bug to test for. REL-4T8N-B (release-tooling, 2026-06-04) rendered `release-notes.md` as one `### ` sub-section per change-log ENTRY within a release — correct for distinct scopes (v2.0.5's four), but a single scope split across two change-log entries (v1.4.0's two `scope=v1.4` entries) produced two identical `### v1.4` headings, *worse* than the old collapse. My own new tests covered distinct-scope and no-scope multi-entry but NOT same-scope-multi-entry; the parallel adversarial-verification workflow I launched ALSO missed it — because I wrote its edge-case list, so it inherited my framing. The independent cumulative Critic caught it by reasoning from the actual committed `release-notes.md` artifact (it diffed the real file), not from my fixtures. Fix-shape: (1) when a fan-out keys on a field, add an explicit test for the field-COLLISION case (≥2 inputs sharing the key) — the correct model was "group by the key first" (`_group_release_entries_by_scope` merges same-scope, splits distinct); (2) a self-authored adversary only escapes the author's blind spots to the extent its prompt does — the durable catch is the *independent* reviewer working from real artifacts, not a skeptic whose checklist you wrote. Discovered release-tooling REL-4T8N-B (2026-06-04, develop). Relates to Independent Review (#14), Tests Are Contracts (#1), and Validate Before Propagating (#15).

## A subagent's reported COUNT or LIST is a lead, not ground truth — verify before a blanket edit

*Retired 2026-08-01 — superseded by **Reads as evidence, is not: an absence-claim citing a path that does not RESOLVE, a missing directory returns the same empty result as the claim being true; a disposition recorded from intent, not the diff, which the next reader trusts INSTEAD of the findings; a commit crediting a backlog item by TITLE while its filed reproduction still reproduces; and a subagent's COUNT or LIST, a lead**. That rule is the active statement; this one is kept for readers who remember it.*

When a subagent (Explore/general-purpose) reports an enumeration you're about to act on mechanically — "there are N occurrences of X", "these 4 call sites", "this list of files" — confirm it with a direct `grep -c`/`grep -n` before a `replace_all` or any uniform operation that assumes the count is complete. In v2.0.0 Chunk 5 an explore agent reported "4 lazy lib-import sites"; a direct grep found 5 (it missed `cmd_accept_operator_verification`). A blanket edit trusting "4" would have left the 5th site on the old `tools/`-relative path — a silent miss, not a loud failure. The verification is one cheap grep; the failure mode (an unedited site that looks edited) is expensive and invisible. Fix-shape: for any agent-reported set that drives a sweep, re-derive the set yourself with the precise query right before the sweep. Discovered v2.0.0 Chunk 5. Relates to Validate Before Propagating (#15) and Honest Confidence (#5).

## A plugin skill with unparseable YAML frontmatter loads with ALL metadata silently dropped — validate it in CI

*Retired 2026-08-01 — sentinel `tests/test_plugin_manifest.py::TestAllPluginSkillFrontmatter` passes, so the failure mode this warned about is structurally enforced.*

When shipping plugin skills (`skills/<name>/SKILL.md`), a frontmatter YAML parse error does NOT fail loud — the loader drops EVERY frontmatter field and the skill loads unusable (no `description`, not discoverable/invocable as intended). The unit suite is blind to this: it exercises skill *behavior* via direct subprocess/lib calls, never the loader's frontmatter parse, so the suite stays green while the skill is broken. v2.0.0 Chunk 6 shipped three reader skills (discovery/planning/reflection) whose `description:` value held an unquoted `: ` (colon-space) — YAML reads that as a nested mapping → parse error → empty metadata — and it went unnoticed for a chunk until `claude plugin validate` surfaced it during the Chunk-11 dogfood. Fix-shape: parse every `skills/*/SKILL.md` frontmatter with `yaml.safe_load` in a test AND run `claude plugin validate <path>` as part of plugin-chunk verification; quote any scalar containing `:` / `#` / `|` / leading-special chars. Discovered v2.0.0 Chunk 11. Relates to Validate Before Propagating (#15) and Tests Are Contracts (#1).

## When generalizing or detecting "across all cases", the COMMON / AVAILABLE instance silently narrows the requirement to itself — check coverage against the requirement's stated breadth

*Retired 2026-08-01 — superseded by **A fixture's world is narrower than the requirement it certifies — the COMMON instance narrows the requirement to itself, so check coverage against its stated BREADTH; the framework's OWN state stands in for the propagated contract, so assert what reaches consumer repos; one moment stands in for the procedure's transitions; and the collision case is unwritten when the fan-out key is not unique**. That rule is the active statement; this one is kept for readers who remember it.*

Writing general guidance, a transport-/protocol-neutral template, or a "detect X everywhere" scan, the most common instance (HTTP for APIs, Python for a code scan) and the most *available* primitive (a `*.py`-only `has_imports`, a Read/Glob-only skill) try to colonize the general framing — you ship something that silently covers only the common case. Before calling it general: state the requirement's stated breadth explicitly and check each instance (library/SDK, on-device, CLI — not just network/HTTP; JS/Go/Java manifests — not just Python imports), and confirm the primitive or tool-grant you build on can actually *see* that breadth (a Read/Glob skill can't grep source; a `*.py`-only scanner can't read `package.json`). Extend the primitive (or attribute the unreachable signal to the surface that can reach it) rather than narrow the requirement to fit the tool. Caught three times in one feature: the api-contract template framed HTTP-only, doctor #9's prose implied a grep its tool-grant lacked, and the advisory probe's base primitive saw only Python. Relates to Complete Delivery (#2), Honest Confidence (#5 — don't let prose imply a reach the tool grant lacks), Bring Expertise (#7), and [[detection of structural characteristics should not rely on mechanistic surface markers]].

## A test asserting the framework repo's OWN state instead of the propagated contract gives false coverage — assert the contract that reaches consumer repos

*Retired 2026-08-01 — superseded by **A fixture's world is narrower than the requirement it certifies — the COMMON instance narrows the requirement to itself, so check coverage against its stated BREADTH; the framework's OWN state stands in for the propagated contract, so assert what reaches consumer repos; one moment stands in for the procedure's transitions; and the collision case is unwritten when the fan-out key is not unique**. That rule is the active statement; this one is kept for readers who remember it.*

The plugin's defaults reach onboarded products only through **canonical carriers**, never through this framework repo's own files: gitignore defaults via `lib/core.py::GITIGNORE_ENTRIES` (written into a product `.gitignore` by `update_gitignore` on onboard/doctor) and its import-light inline mirror `bin/prawduct-hook::_SESSION_GITIGNORED_PATHS` (the `_untrack_session_files` set); format legends via `templates/`; default-behavior changes via `methodology/session-digest.md`. Dogfooding this repo creates a blind spot: state the framework repo *also* generates (because the plugin is active here too) can be made quiet by a hand-edit to *this* repo's tracked files, which does nothing for products. The work-model vocabulary index (PR #71) is the canonical instance. Two hooks generate `.prawduct/.work-model-index.json` on every session in *every* `.prawduct/`-bearing repo (SessionStart `build-index`, UserPromptSubmit `user-prompt-submit`). PR #71 correctly intended it ephemeral/gitignored and added the ignore line to this framework repo's own `.gitignore` (line 25) — but never to `GITIGNORE_ENTRIES` or `_SESSION_GITIGNORED_PATHS`. Result: `update_gitignore` never wrote an ignore rule for it into any product, so every onboarded repo regenerated the file each session and carried it as permanent untracked noise (the reported symptom). The damning part is the *test*: `tests/test_work_model_hooks.py::test_index_is_gitignored` existed and **passed continuously** — because it asserted `(ROOT / ".gitignore")`, i.e. *this repo's* file, the one surface that has no bearing on products. A green guard test on the wrong surface is worse than no test: it reads as "covered." Discovered 2026-06-25 from a user report that the file was noisy in both this repo (where it's actually fine) and consuming repos (where it wasn't). Fix: add `.prawduct/.work-model-index.json` to both contract lists (`TestSessionGitignoreMirror` pins them in sync); existing products self-heal — `update_gitignore` adds the line next session, and `_untrack_session_files` `git rm --cached`s it if a repo already committed it. The regression net was rebuilt to assert the *contract*: `test_index_is_in_gitignore_contract` (the entry is in `GITIGNORE_ENTRIES`) and `test_update_gitignore_writes_index_line` (end-to-end — a freshly reconciled product `.gitignore` contains the line). Fix-shape, general: when a feature ships any propagated default (an ignore line, a format field, a digest behavior), write the regression test against the canonical carrier AND an end-to-end propagation into a fresh `tmp_path` product — never against the framework repo's own dogfood copy; if the only assertion touches a file under this repo's root, ask "would this still hold in a *product* repo?" and if not, the test is false coverage. Same root shape as [[A format's schema legend lives in `templates/` (scaffold-only) — adding an optional field reaches already-onboarded repos only via a migrate/triage *refresh* step, not the template]] — anything living only in the framework repo does not reach onboarded repos. Relates to Tests Are Contracts (#1 — a contract test must test the contract, not the producer's private copy), Validate Before Propagating (#15), Complete Delivery (#2), and Clean Deployment (#10 — dev-time dogfood state masking a product-facing defect).

## A test that asserts a SUBSTRING of prose stops being a contract the moment someone writes a longer sentence containing it — when prose changes meaning, grep the tests that assert fragments of it, not just the ones that fail

*Retired 2026-08-01 — superseded by **A passing assertion may be satisfied by something other than the property — an unimplemented flag passes because the arg guard REJECTED it (assert success BEFORE absence); a prose SUBSTRING stays green under any longer sentence containing it (when prose changes meaning, grep tests asserting FRAGMENTS, not just failing ones); a proxy passes every test you thought to write — gate on the named event**. That rule is the active statement; this one is kept for readers who remember it.*

`test_pr_reviewer.py` asserted `"always run" in content` under a docstring reading "R-2 stays unconditional." Chunk 02 rewrote that prose to "always run **on this backend**" — the opposite claim — and the assertion sailed through a green 2453-test suite. A failing test renegotiates its contract in the open ([[When a deliberate change turns a passing test red, renegotiate the contract in the open]]); a test that keeps passing while its stated contract inverts is strictly worse, because nothing signals. So: when an edit changes what a prose surface *means*, `grep` the test corpus for fragments of the old sentence and re-read every hit against its docstring; and prefer assertions that pin the *discriminating* clause (`"always run on this backend"`), not a prefix any successor sentence will contain. Corollary: a chunk planned `doc-only` is mis-typed the moment its prose contradicts a test — re-type it rather than leave the substring passing. Discovered skills-cutover-awareness Chunk 02 (2026-07-20). Relates to Tests Are Contracts (#1) and Honest Confidence (#5).

## A rationale you reached for to defend a decision you'd already made is the one to verify BEFORE writing it into a durable spec — the reach itself is the tell

*Retired 2026-08-01 — superseded by **Anything in a durable artifact that one command could check is a CLAIM — an identifier, a count, a `file:line`, or a facet value, not just a rationale — so run its falsifying query first. The rationale you REACHED FOR to defend a decision already made is the one to verify, and a CORRECTION is itself a completeness claim: quoting the parent rule demonstrably does not prevent this**. That rule is the active statement; this one is kept for readers who remember it.*

Justifying "the janitor gets no post-cutover backlog context," I wrote into `skills/janitor/SKILL.md` that its `allowed-tools` grants no `Bash(prawduct-hook *)`, so "the janitor surveys, it does not query services." The frontmatter fact was true and the inference was unsound: Step 1 of the same file already instructs `prawduct-hook review-stats`, and every sibling skill instructing a hook call carries the matching grant — janitor is the sole exception, i.e. an oversight. The decision was actually made on other grounds (the owner's W1 read-through-cache ruling); the grant story was recruited afterward to make it look principled, and it laundered a bug into a recorded architectural position where a later builder could cite it. So: when you notice yourself supplying a *second* reason for a decision already settled, treat that reason as unverified — read the mechanism it rests on (Principle 24), and if it turns out to be a defect, file the defect and rest the prose on the premise that actually decided it. This is the requirement-invention tripwire (#6) in inverted form: not a requirement invented forward into code, but a rationale invented backward into a spec. Discovered skills-cutover-awareness Chunk 03 (2026-07-20, Critic warning). Relates to [[A decision reversed mid-chunk leaves stale rationale in prose you just wrote]] and Reasoned Decisions (#4).

## A falsifying query is itself a mechanism and can carry the defect it hunts — when proving a claim is ABSENT from a tree, normalize the text before searching, because line structure is not semantic structure

*Retired 2026-08-01 — superseded by **A completeness claim asserts the falsifying COMMAND now returns nothing — never a count of sites fixed, which is true of any prefix of the real set. The query is itself a mechanism and can carry the defect it hunts: normalize the text before searching, because line structure is not semantic structure, and query the CONCEPT, not the phrasings you already found wrong**. That rule is the active statement; this one is kept for readers who remember it.*

Fixing a "prose asserts a property the code lacks" finding (the REST-point meter charges per transport *method*, not per HTTP request, so its total is a floor), I corrected the sites the review named, ran `grep -rn "every.*REST call" plugin/`, got one hit — my own corrective comment quoting the phrase — and recorded the sweep as complete in a change-log entry. Four sites survived, because the claim **wraps across line breaks** (`charges every\n       migration REST call`) and a line-based grep structurally cannot match it. One of the survivors was `skills/backlog/migration-scrub.md`, which ships to every consumer and is the operator's runbook for an irreversible ~900-issue migration. The reviewer's own grep missed a fifth site for the same reason. Replacing it with a whitespace-normalized sweep (`" ".join(text.split())`, then regex) found every one. The general form: **a negative result is only as strong as the query's ability to represent the claim**, and the default text tools represent *lines*, while prose claims are sentences that wrap, hyphenate, and get reflowed by formatters. So: to prove absence, flatten first; and treat "my grep found nothing" as evidence about the grep until you have shown the query matches a known-positive. Sharpest form of the tell — I wrote a comment warning that a mechanism overclaims what it measures, and in the same commit used a verification method that overclaimed what it checked. Discovered 2026-07-28 (v3.2.0 develop-integration, verify-resolutions warning). Relates to [[A fix lands at the instance a review named; the defect lives in the class]], [[When a guarantee names a specific event, gate on THAT event]], Honest Confidence (#5), Validate Before Propagating (#15).

## When a guarantee names a specific event, gate on THAT event — a signal that usually co-occurs with it passes every test you think to write, because you wrote them believing the proxy

*Retired 2026-08-01 — superseded by **A passing assertion may be satisfied by something other than the property — an unimplemented flag passes because the arg guard REJECTED it (assert success BEFORE absence); a prose SUBSTRING stays green under any longer sentence containing it (when prose changes meaning, grep tests asserting FRAGMENTS, not just failing ones); a proxy passes every test you thought to write — gate on the named event**. That rule is the active statement; this one is kept for readers who remember it.*

Session-handoff Chunk 01 introduced `.handoff-notes.md`, a model-authored note consumed into the generated handoff and then deleted. The stated guarantee — written into the docstring, the call-site comment, `architecture.md` and the change-log — was "a note is deleted only once its text is durably in the handoff." The code gated the delete on `handoff_written`, which is true whenever *any* section produced content, while the notes reader collapsed absent / empty / **unreadable** into one empty string. So an undecodable note was deleted with its text carried nowhere — unrecoverable, through the documented happy path — and the chunk's own test walked that exact path while asserting nothing about the notes file. All three Critic reviewers found it independently, which is the tell: convergence from unrelated lenses means it was never subtle, the author was reading their own comment instead of the code. So: when you write "only after X," find the expression that *is* X and gate on it; if X isn't representable, that absence is the finding — make it representable (here, the reader returning a state rather than a string whose emptiness meant three different things). Corollary: an invariant asserted in N prose locations is N places that will keep asserting it after the code stops honoring it, so the prose count is a risk multiplier, not evidence. Discovered session-handoff-continuity Chunk 01 (2026-07-26, Critic warning ×3). Relates to [[A test that asserts a SUBSTRING of prose stops being a contract the moment someone writes a longer sentence containing it]], Tests Are Contracts (#1), Independent Review (#14).

## When you write a CORRECTION it is itself a completeness claim — run the query that would falsify it across the whole class BEFORE asserting the fix, because a correction that repaired only the site a review named is false about its own subject, and quoting the parent rule demonstrably does not prevent this

*Retired 2026-08-01 — superseded by **Anything in a durable artifact that one command could check is a CLAIM — an identifier, a count, a `file:line`, or a facet value, not just a rationale — so run its falsifying query first. The rationale you REACHED FOR to defend a decision already made is the one to verify, and a CORRECTION is itself a completeness claim: quoting the parent rule demonstrably does not prevent this**. That rule is the active statement; this one is kept for readers who remember it.*

Confirmed 2026-07-31 (fleet-migration-triage), four instances in one session, each one occurring
*after* the parent rule had been quoted. **(1)** Struck the `legacy.py` retirement leg in `BKL-6M4T`
and wrote a change-log entry presenting the fix as complete; the same instruction was still live in
four other surfaces, including `migration-scrub.md` — a runbook an agent **executes**. So the repo
contradicted itself across five surfaces with the correction applied to one, and the executed one
still said to retire it. **(2)** Told that a warning box transcribed a figure the box itself
forbids, deleted the one figure the review named and left three more in the same block. **(3)** Then
wrote *"No figures are quoted here on purpose"* directly above the survivors — the correction was now
false about itself, strictly worse than the defect it replaced, because a reader trusts the bolded
claim and skips the instrument. **(4)** Carried in from the same day's earlier session: the
`learnings-entry-shape` guard, repaired three times, each repair addressing the instance the review
named.

**Why a third rule rather than a louder restatement of the two parents.** Both parents already exist
here — [[A fix lands at the instance a review named; the defect lives in the class]] and
[[A completeness claim states the COMMAND that would falsify it and asserts that command now returns nothing]].
They were quoted in a session reflection and in a commit message on the day of the violations, and
the violations followed each quotation within minutes. Restating them is therefore proven not to be
the fix. What was missing is the **composition**, and specifically its trigger: the parents fire on
"closing a finding" and "claiming completeness," neither of which felt like what I was doing. Writing
a correction did not present itself as either — it felt like *repair*, which is why nothing engaged.

Operative form: the moment you write text asserting that other text was wrong, you have made a claim
about the whole class of that wrongness. Before committing it, grep for the correction's own subject —
the file name, the instruction, the figure, the claim — and confirm the query returns only the sites
you fixed plus the legitimate contexts. For prose corrections this costs one grep. All four instances
above would have been caught by it. Relates to Root Cause Discipline (#16) and Honest Confidence (#5)
— the false-about-itself case is the sharp one, because it converts a partial fix into an active
misdirection.

---

## Enumerate the sites answering a question by GREP, never by memory — and the grep is itself a site

A fix that threads a resolved value through the two call sites you remembered leaves the third
reading the old source, and the comment you write above it ("both fields") is accurate for exactly
one commit — the same shape as the bug being fixed, one field over.

**Four instances, all on the branch that wrote this rule down.** The first two were value-threading.
The third and fourth were the *query* carrying the defect it hunted:

- A find-and-replace over quoted tree-id literals in `test_coverage_algebra.py` fixed sixteen of
  seventeen fixtures. The seventeenth built its ids as `f"t{i}"` — a literal sweep is a **prefix**
  of the real set wherever the code also *constructs* the string.
- A sweep for prawduct-internal ids in emitted text scoped itself to literals passed **as
  arguments** to `print`/`error`/`log_diag`/`TransportError`, and reported clean. Emitted text is
  not a syntactic category: it missed a string returned and printed by its caller
  (`_worktree_redirect_note` → `cmd_stop`), one appended to a list printed at session end (the
  designer-handoff waiver note), and one assembled into a document written for a human (the
  restructure-preview title). Two independent reviewers found the first; only widening to *every
  non-docstring literal, read by eye* found the other two.

So the rule has a second half. A completeness claim rests on a falsifying command, and the command
is a mechanism that can be wrong in the same way the code is: too narrow, matching the shape you
already have in mind. Widen it until it would catch a case you have not thought of, and treat a
clean result from a query you wrote yourself as the weakest evidence available.
See [[a completeness claim asserts the falsifying command]].

---

## A filed item's stated MECHANISM is a hypothesis, not a finding

#532 was titled *"stage-less items vanish from counts"* and its Repro said so. That is not what
happened. Stage-less items **were** counted and landed in the `(none)` stage bucket — which the
item itself reported seeing at 64. What vanished was anything failing `is_prawduct_issue`: no
namespaced label **and** no `prawduct:` block, which is how a human-filed or product-filed issue
arrives.

**The item's own evidence contained the disproof.** It recorded `total` moving 374 → 383 after
labelling nine issues, and a stage-bucket bug cannot change a total. Nobody read it that way,
including the reporter, because the correlation was clean: labels went on, the count went up.

The catch came from measurement, not from re-reading. `gh issue list --state open` said 159 and
`counts` said 158 — a **one**-item gap where the item predicted nine. That forced "which one?", and
the answer (#533, filed by a human, no block) was the mechanism. The plan had already inherited the
wrong number into a `[DECISION:]` block predicting 158 → 167, and would have shipped it into the
change-log as measured fact.

Pairs with [[when you correct an inherited number recount the SET]] — same failure, one rung
earlier: that rule is about re-measuring inside an inherited frame; this one is about the frame
arriving in the item text and reading like a finding because it sits under a "Problem" heading.


## A token budget is raised only when the framework is provably better FOR THE RAISE and upleveling has no headroom left

Two Critic controls had to land in files with 2 and 12 words of headroom. Word-shaving looked
hopeless, and the estimator is `len(text.split()) * 1.3`, so reflowing buys literally nothing.

What worked was cutting whole classes of content rather than tightening sentences:

- **Definitions another file owns.** `goals-1-3.md` told the reviewer to read `record_lint`'s output
  and *never re-derive it*, then spent forty words re-deriving what each lint id means — including a
  400-char threshold no reviewer applies, because code computes it. `review-protocol.md` did the same
  with the four Framework-Specific Checks, immediately after pointing at `framework-checks.md` for
  the definitions. Both cuts are safe *because* the file already ordered the reader elsewhere.
- **Machine output quoted verbatim.** A WARNING's exact wording, reproduced in prose, when the
  reviewer composes the message anyway.
- **History.** "Reviewer-model tiering was removed" — what a mechanism *used* to do, carried in an
  instruction payload where it can only cost. Note the near-miss: "an undeclared repo is never
  reviewed less than before" *looks* like the same class and is not — it is a **live invariant**,
  still asserted in `review-cycle.md`. Cutting it was right for a different reason (the fact has one
  home and the payload already points at it), and filing a live invariant under "history" is how a
  true statement gets deleted next time on a false premise. Check which one you have before cutting.
- **Rationale aimed at a maintainer, inside a payload aimed at a reviewer.** The most self-defeating
  instance: a citation explaining *why this file is short*, in the file whose purpose is minimum
  reviewer payload.

Both files ended up smaller than they started while each gained a check.

**Two guards caught real damage, and both were worth more than the tokens saved.** Deleting Goal 4's
`**Norms**` bullet as a "pure restatement" broke `test_project_preferences_blocking`, which contracts
on a single line carrying both `project-preferences` and `blocking` — that bullet is the only line
satisfying it. The budget comment recorded a previous editor doing exactly this and reverting; I did
it anyway, which is why the note now names the trap instead of narrating the incident. Separately,
compressing "the chunk *inferred from* build-plan Status" to "the chunk from build-plan Status"
broke a guard pinning that the assumption shape names both its causes — a compressed reading there
had previously produced a recurring false BLOCKING no `--chunk` could clear.

The general form: **prose that reads as redundant may be the only witness to a contract.** Uplevel
aggressively, then run the suite — the guards, not the reading, decide what was redundant.

## Exactness is owed to a number something RELIES ON for a decision, not one something merely READS

Instance, 2026-08-02: restoring one word to a budgeted file moved its token reading by 1, which then
had to be updated in `LAST_MEASURED_TOKENS`, a change-log paragraph, and a build-plan Status
paragraph. Three edits, one word, and no decision anywhere depended on the digit — the *ceiling*
assertion is what decides. The prose figures were removed and the table left owning the reading.
`LAST_MEASURED_TOKENS` itself is the open question: it is an exact-equality pin that drives no
branch, so every edit to a budgeted file pays a mandatory update whose only function is to force the
author to notice. That may be worth it, but it is exact-number churn by construction and should be
decided deliberately rather than inherited.

## A rule you must RECALL at the right moment is its weakest form

Three failures in one work cycle, all of the same shape: the rule was **in context** and the instance
went unrecognised.

1. Deleted a bullet a budget comment explicitly warns against deleting — while reading that comment.
2. Missed the second site on three of four review warnings, against a *second-site sweep* rule this
   same branch wrote two chunks earlier.
3. Wrote a retire rule counting PR reviews from a store PR findings never reach — about a hundred
   lines below my own paragraph explaining that this ledger is per-worktree and gitignored, which I
   had just applied correctly to a different item.

The tempting conclusion is "read more carefully." The evidence says otherwise: **every catch came
from something that runs.** The suite caught both bad cuts. `render-dispositions` caught a
disposition claiming a fix I had not yet made. Two independent reviewers caught a schema assumption.
Nothing was caught by remembering a rule at the moment it applied — including rules authored minutes
earlier, because familiarity reads as compliance.

So the operational form is not vigilance but conversion: when a rule governs a class of claim that a
query could settle, spend the effort building the query rather than restating the rule. This is
exactly what the stable-token mechanism does for control yield — it turns "did this check ever fire?"
from a memory into a grep — and why the structured `check:` field is the better version still.

Corollary for review economics: this is an argument for *mechanising*, not for more review rounds.
Two of the three failures were caught by a reviewer, which is expensive; the first was caught by a
test, which is free and repeats forever.

## The RHETORICAL ROLE of a sentence can select its content over a fact you already hold

`pr/SKILL.md`, one paragraph, written in a single pass:

> The durable record of a review is the *fact*, and facts live in the shared evidence store …
> **Known cost, accepted:** PR findings are therefore not queryable from the shared store …

Both sentences are mine, two apart. The first is false for PR reviews (`evidence.KNOWN_KINDS` is
`{review, resolution, disposition}`, all written by `critic-consolidate`; a PR review lands in a
gitignored per-worktree ledger). The second states that correctly. I had been corrected on exactly
this by a review round the same day.

This is not forgetting, and no recall-based guard would have caught it — I *held* the fact, and
demonstrated so in the same paragraph. What happened is that the two sentences had different jobs.
The justification slot wanted a reason that made the decision sound principled, and "the durable
record lives in the shared store" is a better-sounding reason than "it lives in a gitignored
per-worktree ledger event." The caveat slot wanted a limitation, and there the true fact fit.

The operational form: when writing a rationale, identify the **load-bearing clause** — the one the
decision rests on — and check that one against the mechanism, separately from reading the paragraph
for sense. Reading for sense will pass it, because it reads well; that is the property that selected
it. Pairs with [[A rule you must RECALL at the right moment is its weakest form]]: that rule covers
rules you fail to apply, this one covers facts you apply *away from* where they are needed.

## A disposition claiming "fixed" must restate the finding's own predicate

**Where it came from.** `fix/drift-burndown` Chunk 01 (#193), 2026-08-02. The chunk review's R-3
said: *the `plugin/` root fallback means the check cannot see the root-`bin/` → `plugin/bin/`
relocation its own docstring cites as the reason it exists.* The fallback resolves a bare
`bin/prawduct-hook` against `plugin/bin/prawduct-hook`, so the motivating defect was invisible.

**What I did.** Scoped the fallback by FILE — allowed only for files under `plugin/` and for build
plans under `.prawduct/artifacts/` (which carry a declared `build_plan_ref_root: plugin`). That
immediately surfaced **seven real defects**: every `tests/scenarios/*.md` told a reader to run
`python3 bin/prawduct-hook init-product …` from the repo root, where no such file has existed since
the relocation. I fixed them, dispositioned R-3 as "fixed beyond the ask", and wrote in the
change-log: *"the reviewer asked for a hedge on the claim; the claim turned out to be fixable
instead."*

**Why it was wrong.** The motivating defect lived in five **skills'** prose and `allowed-tools:`
grants. Skills live at `plugin/skills/*/SKILL.md` — **inside the scope I retained**. Two of the
three covered forms, on the exact files, of the exact class, still resolved. The finding was
untouched. The verify pass caught it by checking the tree rather than the fix notes.

**The mechanism of the error.** I verified *the fix I made* instead of *the finding as stated*. My
question was "did offenders appear, and are they real?" — which returns yes for a neighbouring
surface. R-3's question was "can the check see this specific relocation, in these specific files?"
Seven genuine fixes made the false claim feel earned; had the scoping found nothing I would have
looked harder.

**Aggravating context.** This shipped inside a batch whose subject is *records asserting what the
code does not support*, in the chunk building the detector for that class. The failure mode does not
care that you are writing about it.

**The closing fix, and why it is better than the hedge R-3 asked for.** Scope by FORM as well as
file. The fallback is justified by *naming* a file — plugin docs refer to siblings the way the
plugin ships them (`skills/critic/review-cycle.md`, `methodology/building.md`, dozens more) — and is
justified for nothing when *running* one, because a reader executes from a working directory, which
in this repo means `plugin/bin/prawduct-hook` (all fifteen in-tree invocations say so). Denied to
`command` and `allowed-tools`. That bought four more live fixes in build plans and is pinned by
`test_the_plugin_fallback_is_denied_to_invocation_forms`, red-verified by restoring the wider form.

**The rule.** A "fixed" disposition restates the finding's predicate and demonstrates it false,
ideally as an assertion. Tell: the fix note argues from what the change caught rather than from what
the finding said.

## Scope an exemption by the property that justifies it, not by the container

**Same chunk, the structural half of the above.** The `plugin/` fallback's rationale is a verb —
*naming* a file — but the boundary I wrote was a path prefix: `containing.startswith("plugin/")`.
Those coincide for most files and diverge exactly where the defect lives, because a skill both names
sibling files (legitimate) and invokes executables (not). Container-scoping looked complete: it had
a stated rationale, a declared config backing half of it (`build_plan_ref_root`), and it produced
real catches.

**The generalisation trap.** Going from "plugin docs name paths as the plugin ships them" to "files
under `plugin/` get the fallback" is one step, feels like the same sentence, and silently widens the
exemption from a *form* to a *location*. The correct boundary needed both: entitled file **and**
non-invocation form.

**Tell.** The exemption's boundary is expressed as a path prefix while its rationale is expressed as
a verb. When those two shapes disagree, the prefix is the approximation.
