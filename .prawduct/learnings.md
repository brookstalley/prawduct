# Learnings

Active rules from this project's development. Surfaced via the `/learnings [topic]` skill — topic headers shown in the session briefing for ambient context. Entries use "When X, do Y because Z" format. Each entry's full narrative lives in `learnings-detail.md` under the same heading — keep narrative THERE, not here.

<!-- prawduct:descent-obligation — the structural statement below is the HOME of the
     descent rule; `/prawduct:learnings` points here rather than restating it. Reword the
     prose freely; keep this marker, and keep it above the first rule. -->

**Reading a rule is not applying it.** The failure mode of this file is not absence, it is
assent: a rule arrives at the right moment, is read, is agreed with, and changes nothing, because
nothing made you recognize the case in hand as an instance of it. Delivery is not descent. So for
any rule you read here, name the decision you are about to make and say what the rule changes
about it — or say that it does not apply, which is also an answer. A rule you nodded at and did
not spend has done nothing, and it will read exactly as true the next time you fail to spend it.

This is why an entry carries its **tell** inline — the shape of the case, concrete enough to
pattern-match your own situation against — while the full narrative sits in `learnings-detail.md`
(read on demand, when debugging a known area, not at the moment a rule has to fire). A general
statement is what makes a rule storable *and* what makes it inert; the tell is what makes it
recognizable. That is the line the `learnings-entry-shape` check enforces at 400 chars: enough to
fire on, not the whole account. Rules are collapsed by merging statements and unioning tells,
never by dropping them.

---

## RETIRED RULING (regen-views-is-advice), 2026-08-08 — subject removed, not overturned. Its generalisation was promoted onto the norm it ruled on (`architecture.md`: *a command's failure posture follows what it produces*). Kept as a heading because both norms link here — the link must find the retirement, not a 404 — [learnings-detail.md]
<!-- anchor: regen-views-is-advice — linked from architecture.md and data-model.md Rulings: -->

## When a long-lived branch syncs a base that moved a lot, diff the TESTS on both sides before resolving any hunk — a test states the rule the code only instantiates, so two sides that re-implemented one mechanism disagree visibly there. Tell: a hunk where both sides are coherent implementations of the same named thing — [learnings-detail.md]

## When a review finds the SAME class twice, stop fixing instances and enumerate the domain — two spot fixes in two rounds is one missing act, not two mistakes. List every state the thing can be in and make each a case. Tell: your fix cites the reviewer's example — [learnings-detail.md]

## Hand-verifying at the terminal leaves nothing behind — the corpus you ran the grep against IS a fixture, so make it one in the same breath. A guard warning over every repo's real data shipped with only its positive case asserted. Tell: "I checked it against the real file" with no test naming it — [learnings-detail.md]

## A docstring written in the same keystroke as its code describes the design you INTEND, not the code you shipped — "the one reader", "every surface", "always". Twice in one session, both wrong when written. Before a sentence claims reach, grep for the callers; a claim about scope is checkable in seconds and unfalsifiable once it ships — [learnings-detail.md]

## The prose that REPLACES a deleted control is load-bearing logic — pin every rendered branch of it. A message covering two states must be DERIVED from the state, never written for the one in mind: a sentence asserting "no plan has chunks left" met an operator whose plans had them. Tell: you changed a user-facing string and no assertion names it — [learnings-detail.md]

## When prose asserts what a system DOES, make the system do it — the pin is the check, not a formality. One pass here disproved the finding that opened it, then failed against the shipped docstring and exposed a `release=` tag that merged away read by nothing. Reading cannot find either. Tell: a caveat naming a downstream catch nobody has run — [learnings-detail.md]

## A zero from a scan is suspicious until the scan is shown able to return non-zero — `getattr(x, "body", "")` on a field the dataclass lacks measured nothing and reported clean. Before believing a count, feed it a case you know it should catch. Tell: a survey that confirms exactly what you hoped — [learnings-detail.md]

## When scoping a NEW framework feature, list unmerged branches before writing requirements — this repo parks proposals on branches, not in the working tree, so a grep of `plugin/` + `.prawduct/` + the backlog reads as "no prior art" while a finished investigation sits one `git branch` away. `docs/remote-test-execution-proposal` had already settled the config home, the reusable-surface size and the measured concurrency shape. Tell: your prior-art search touched only paths that exist on HEAD

## When you rewrite a MEASUREMENT into a BENEFIT, re-attach the number to the sentence you actually wrote — the rewrite is where a claim silently widens past its evidence, because the benefit sentence is shorter and short sentences generalize. v3.4.0 shipped *"the review gates are 57× faster"*; 57× was the gate CHECK, and reviews cost what they always did. Tell: you cannot point at the number behind the noun you just chose — [learnings-detail.md]
<!-- anchor: benefit-framing-widens-the-claim -->

## When a criterion, plan or rule DESCRIBES an artifact, open the artifact before building to the description — it was written from a framing and inherits that framing's blind spot. "Does not touch a block carrying other keys", authored before anyone read the block, would have left 7 of 8 repos broken. Tell: you can satisfy it fully without ever reading the thing it names — [learnings-detail.md]
<!-- anchor: build-from-the-thing-not-its-description -->

## When you retire a MECHANISM, sort its rules into three piles before deleting any — died / rewritten / **INVERTED**. "The tool is gone" reads like a licence to drop the lot, and the lesson usually outlived the tool. The third pile is the one nobody looks for and the only one that leaves a harmful rule standing. Tell: the rule is a prohibition whose reason was the tool — [learnings-detail.md]
<!-- anchor: the-derived-views-retirement -->

## When a field's ABSENCE carries the meaning, a value NAMING the absence is its opposite — it reads as deliberate, so review cannot see it. `release=unreleased` hid a finished branch from its own release. Ask the CONSUMER, not the reader, and guard by BLAST RADIUS. **Never write "verified" against a reader-check** — it promotes a guess to a fact review reads as settled — [learnings-detail.md]

## `grep -rn <new symbol> tests/` before calling a behaviour change done — a guard with no test is one a regression deletes silently. Three rounds running found that, the last two in code written to FIX the previous instance: applying a rule to the finding in front of you is not applying it to the code you write while applying it

## An exception APPENDED to standing advice still leads with the advice — so before appending, ask whether the exception can cover the WHOLE set, and if it can, it must be able to REPLACE the lead sentence rather than follow it. #536's own fix shipped #536: the superseded clause was appended after "run verify-resolutions", so when every blocker was superseded the operator's first instruction was still the route that cannot work. Tell: the exception's predicate is a count over the same set the advice addresses. Fix shape — one function owns the whole message and decides which route *leads*, so no call site can reintroduce a lead of its own

## When you TRANSCRIBE a rule between two records, its identifiers are the part that silently degrades — re-verify every field, symbol and path against the code, because a paraphrase reads exactly like a faithful copy. Copying the retire rule from build plan to change-log turned `title` into `summary`: plausible, adjacent, and wrong for the store the query runs against, so the sweep would have returned zero for every review and retired a firing control. Fifth instance of two-copies-of-one-idea on this branch and the FIRST with the plan correct and the durable copy wrong — the direction flips at transcription, so carry the *reason* alongside the token ("`title`, because a partial's `name` becomes the fact's `title`"), not the token alone

## When operator prose restates a PREDICATE, diff your sentence against the rule's canonical prose statement — never paraphrase from the code you just read, because reading it correctly and summarising it wrongly are the same afternoon. #722's own fix stated the verify-resolutions anchor test as a commit-SET question ("was anything committed?") in two surfaces at once; the code compares TREES, and the two disagree on the ordinary happy path where a commit materializes the reviewed tree verbatim and moves nothing — so the correction told a builder they owed the round the branch existed to remove. `review-cycle.md` already said it correctly and was never opened. Tell: you can state the rule but not point at the sentence you got it from — [learnings-detail.md]

## Enumerate the sites answering a question by GREP, never by memory — and the grep is itself a site: it is a PREFIX of the real set wherever the code BUILDS the string rather than spelling it, or emits it somewhere the query cannot see. Widen it until it is falsifiable, then have someone else run it

## A fix ships TWO artifacts that can independently be false — the change, and the evidence that it works. This branch put every defect in the second: a test that could not see the bug it pinned, then a comment asserting the rule its own assertion disproves. When you fix something, sweep the NEIGHBOURING PROSE in the same pass, or a reviewer finds it one comment at a time

## A mutant that SURVIVES on code you just wrote is a claim about the CODE, not the test — before writing a test to kill it, ask which existing branch already answers that case. Tell: no fixture makes the guarded and unguarded versions differ, which is unreachability, not coverage. Delete the guard; pin the GUARANTEE, not the mechanism — [learnings-detail.md]

## A mutation test is only evidence if the MUTANT IS THE DEFECT — hand-reverting to "something wrong" tests nothing. Restore the code that actually shipped the bug, gate conditions included: drop a guard the real defect sat behind and the test exercises a path the bug never reached, passing against the very code it was written to catch. And mutate each independently falsifiable CONJUNCT, never the guard as a unit: a compound condition is N guards wearing one name, and `A and B` reverted whole goes red on A's test while B stays unpinned. `anchor_is_ahead`'s second conjunct could be deleted with the entire suite green, because every existing fixture agreed on both sides of it — the absent case was the one the conjunct existed for
<!-- prawduct-learning: confirmations=2; created=2026-08-18 -->

## A `[DECISION]` block is a CLAIM ABOUT THE CODE and carries a test's verification duty — but nothing checks it, so re-derive it from the implementation before writing the next record that cites it. Records written FROM a decision rather than from the code all agree with each other and all disagree with the tree: "binary identity, not version equality" went into a decision block, a deliverable, two docstrings and a change-log draft while the code read `$CLAUDE_PLUGIN_ROOT` — five mutually-consistent records, one implementation, no overlap. The tell is copying a claim forward from the previous record instead of opening the mechanism; the mechanism's own docstring said it preferred the env var, and it had been read earlier in the same session. Corollary: tests written from the same mental model inherit its blind spot — the first matrix here varied only the env var, so it could not have discriminated the two implementations it was written to distinguish

## When you cite a precedent, COPY ITS TEST FILE FIRST — a module that says "shape mirrors X" and does not mirror `test_X.py` has borrowed the design and left the coverage behind, and the gap is invisible because the code looks right. Twice in one chunk: a new hook subcommand modelled on `learnings-obligation` shipped ~50 untested lines (both exit-code mappings, the confirmation block, `--json`, unknown-arg, the dispatch arm) because that precedent's `TestCommand` was never carried across; then the failure policy added to CLOSE that finding shipped untested too, because the same precedent's monkeypatched-writer test was also left behind. The precedent's tests enumerate the branches its design creates — that is most of what makes it a precedent worth citing. Open `test_<precedent>.py` and port its cases before writing your own

## When a predicate's job is to classify REAL artifacts, at least one test must read the real artifact — a fixture you wrote encodes your belief about the input, so it can only ever confirm that belief, and a suite made of them is green precisely where the belief is wrong. Widening a norm-detection guard, I wrote TWO over-fire fixtures aimed at exactly the failure that shipped, and never opened `templates/project-preferences.md`: it ships illustrative rows whose cells are non-empty placeholders, which `init_product` copies verbatim, so the guard fired on every freshly-onboarded repo while both fixtures passed. Pin the artifact and the predicate against EACH OTHER (read through `core.TEMPLATES_DIR`), or they drift apart the moment either moves. Mutation testing does not cover this — it probes the line you wrote, and says nothing about inputs you never supplied

## A dry run that validates IDENTICALLY to the real run is not a safety device — it is where drift hides, because it reports clean while the artifact it checks rots. Delete the mode and always write. Tell: the check and the real command share a validation path and differ only in whether they persist

## Before implementing against a mechanism, grep the BACKLOG for that mechanism's name — and when claiming something is "provably equivalent," name the proposition the proof actually establishes, because equivalence under one model is not equivalence under the one that governs behaviour

## Under a single-parent promotion model, "did this ship?" is a question about TREE CONTENT and never about ancestry — `git tag --contains` cannot return a positive answer for any scope, so it fails as a confident false negative, and the content test needs a control that fails plus a functional-surface target

## The fix for a review finding needs the same adversarial pass as the original work — dispatch a delta review of the fix commit, because "I am correcting a known defect" feels like lower-risk work than writing new code and the verification reflex relaxes exactly where the last round proved it shouldn't. **A fix commit is a code commit**: everything the chunk protocol demands of new code — a test, red-verified, in the same pass — applies unchanged to code written to close a finding, and applies MORE, because that code is written under time pressure and never gets a chunk review of its own. A reader guard added to close a utf-8 round-trip finding shipped with no test at all and the suite stayed green, because on a UTF-8 host the guard is a no-op; the delta review caught it. Third under-tested guard on one branch — an unpinned conjunct, a fixture that could not reach the guard it named, then this — so the failure is not the rule being unknown but the *reflex* not firing on correction work

## A background agent's liveness is answered by ITS OWN completion signal, never by reading the files it is midway through writing — a death verdict from a directory listing is how a re-dispatch clobbers a live review. And the grep that "confirms" it may be matching the failure mode's own DOCUMENTATION, which feels exactly like verification

## A safety argument and its counterexample can sit two paragraphs apart in YOUR OWN writing and never meet, because each answers a different question — before clearing a reader/caller/path as unaffected, re-read what you just wrote about the mechanism's lifetime and ask it against the clearance, not against the wording it was written for

## Naming a chunk/scope/tag freely writes into a MACHINE-READ field and can silently switch off the gate that reads it — check the parser's accepted form before inventing an id, because a value it cannot parse yields `null`, and null is NO ANSWER, not a pass. Tell: you chose an identifier or tag value for readability, in a field some gate keys on

## RESTORE THE WAY YOU MUTATED — after a red-verify mutation, invert the exact replacement rather than reaching for `git checkout -- <file>`, because checkout reverts to HEAD and silently takes every OTHER uncommitted edit in that file with it. Tell: the file you are about to restore also carries unrelated work-in-progress, and the mutation was applied surgically while the undo is file-wide

## A test asserts what would BREAK, not what you just built — red-verify mechanically (break the subject, watch that specific test go red, restore), because the vacuous shapes all look correct while proving nothing

## A NEGATIVE assertion forbids everything its wording matches, not the one thing you meant — match the exact string that carries the behaviour you are excluding, because a loose phrase quietly outlaws any OTHER output containing it, and the test then pins that deletion as if it were the requirement. Always pair it with a POSITIVE assertion for the behaviour that must survive

## Apparent duplication across governing docs may be the RECEIPT for a token budget already paid — check for a pinning test before cutting it, never fund a budget by moving prose between files, and raise the ceiling rather than spend redundancy twice

## Ratcheting the ceiling is part of a cut, not a follow-up — when a trim lands under a HARD budget, lower the ceiling in the same commit, because the drift pin only asks the next editor to update the READING while the ceiling is the only thing that refuses the spend; unratcheted slack is a loan the next edit collects silently and green. Corollary for the builder: a slack you flagged to the owner as a scope question is one you have already priced as optional — if it protects the win the chunk just took, take it

## Justify at the ALTITUDE OF THE DECISION, never the mechanism — a mechanism claim carries the same verification duty as the instruction it supports but escapes the check by reading as commentary. Test: must the reader reason PAST this instruction? No → mechanism is liability; yes (a norm, a recorded decision) → verify it like code. Same species as over-precise counts. Altitude, never omission

## A finding of the form "A is pinned, B is not" is discharged by PINNING B, never by changing B — changing shipped behaviour to satisfy the letter of such a finding relocates the asymmetry from the code to the test layer, where the next review finds it again and charges you another round against a P0 wall-clock budget. Generalise it: the fix commit carries the cheap check that closes the loop it opens — the test beside the moved behaviour, the parser run before a hand-authored machine-parsed record — because a check deferred to the review that follows costs a whole review run to deliver

## A governance change cannot supply its own authority — when an agent amends a binding norm mid-build, land the owner's confirmation somewhere the amendment isn't, because a change that is its own only witness is indistinguishable from laundering however sound the substance

## When you "correct" an inherited number, recount the SET and not just the count — re-measuring inside the frame you inherited reproduces the frame's error while feeling exactly like verification

## A review ending is not a filing event — dispose every non-blocking finding as FIX or ACCEPT, and treat FILE as the narrow case clearing THREE bars: it names its trigger, the work is **large** (a chunk's worth, not an hour's), and it cannot be absorbed into the current work. **Deep context on a small problem is a FIX signal, not a filing signal.**

## Surveying a shared thing takes TWO searches: grepping the thing finds its DUPLICATE COPIES, never what DEPENDS on it. Widen a predicate — grep the *shape*, then its *name* for callers that branch on it. Relocate a fact — grep the fact, then grep prose naming its OLD HOME, because "the rule lives in X" goes false the moment you empty X — [learnings-detail.md]

## When a scope narrowing is recorded (a chunk deferred, work cut from a release), it is a CASCADE, not an annotation — the summary describes, but the bodies INSTRUCT, and they compute against the fact you just changed: recording "v3.2.0 stops after Chunk 06" in § Status left Chunk 09 owing six backlog flips for deferred work, announcing a drop-box retirement that was no longer happening, and declaring `Depends on: Chunks 01–08`. Following it literally would have marked unbuilt work shipped. The edit is not done until every section naming that chunk has been opened

## When a release ships a PRUNED tree, a clean `git apply` is NOT evidence of a sound tree — the shipping code can depend on a symbol the WITHHELD work introduced, which a textual patch tool cannot see: v3.1.2's ship set called `sys.stderr` while `import sys` had arrived in `briefing.py` with the withheld backlog-service work, so `git apply` reported the file applied cleanly and produced a `NameError` in a shipped path (11 test failures). Run the suite against the candidate tree, and diff every shipped file's imports against its `develop` counterpart

## When determining what a PREVIOUS release actually shipped, test its CODE against that release's tree — never the change-log's prose or heading presence, which a pruned release leaves behind: v3.1.1's tree carries all ten backlog-service change-log entries whose code it deliberately withheld, so a heading-presence test called them shipped and would have mis-tagged them, silently dropping ten entries from v3.1.2's release notes. This is the runbook's own REL-7D4X rule and it is load-bearing in both directions

## When work is authored ON TOP OF work you may later need to withhold, the two become inseparable by file — pruning is by commit range, so everything merged in between ships or waits together: v3.1.2's ship and withhold sets overlapped in 11 files including `prawduct-hook` and `briefing.py`, so "ship only the session work" also withheld an unrelated refactor and five skills' prose. Sequence a release-gated subsystem BEHIND independently-shippable work, not before it

## When deferring something to a live/operator check, SPLIT it into "can this be true in principle" (static — test it now) and "does the harness actually do it" (live — queue it) — bundling them defers the testable half indefinitely, and that half is where the bug usually is: CRT-2J8N deferred all of "does the SubagentStop matcher fire" as un-unit-testable because *anchoring semantics vary by version*, true of delivery but false of matchability, and the bare-name matcher could never have matched the plugin-scoped `agent_type` on any version

## When defense-in-depth is offered as the reason a risk needn't be verified, check the defense is REACHABLE from the failure it is meant to absorb — a guard downstream of the thing that fails never runs, so it buys nothing: `cmd_subagent_stop`'s `agent_type.endswith(...)` check was cited as making matcher uncertainty tolerable, but it sits behind the matcher, and a matcher that never fires never reaches it

## A message that names the caller's NEXT step must ask the gate that will judge that step, never a cheaper proxy for it — else the promise and the gate disagree and the caller pays the difference. Fires on SUCCESS paths, not only refusals: "a refusal names a remedy that reaches the state" is this rule's better-known half — [learnings-detail.md]

## A deferral queue whose enforcing gate is disabled is a WRITE-ONLY queue — check the gate is ON at the moment you defer work into it, because the deferral itself feels like diligence: `operator-verification.md` named the CRT-2J8N matcher as the thing to investigate 17 days before it was found, and sat `pending` the whole time behind `operator_verification_required: false`, with 6 of 8 entries in the same state

## When a test asserts a VALUE and its comment claims that value feeds a downstream contract, assert the CONTRACT instead — the comment does the reasoning the test never performs, so it reads as coverage while providing none: `test_name_is_critic_reviewer` checked the agent's frontmatter name and commented that the name "is the SubagentStop matcher target", true of dispatch and false of the matcher, and never opened `hooks.json`

## When a decision defers a SET of findings rather than fixing them, enumerate the set against the filings before calling it done — deferral converts every item into a filing obligation and nothing reconciles the two lists automatically: a "file all ten" call produced six items covering eight, and the two dropped ones were found only because an independent reviewer counted

## Merge instructions written BEFORE the merge — a subagent's advice, or a note you wrote yourself — are verified against the merge's actual hunk shape, never applied literally: whoever reasons from the BRANCH cannot see a convention the DESTINATION adopted after the branch was cut

## When a feature's value rests on an invariant ("presence of X proves Y"), audit the DEGRADATION paths first — that is where the invariant actually lives: a helper that swallows failure into "" or False makes absence ambiguous and can render the signal's exact inverse, so pick each fallback's direction from what the invariant needs, not from what is locally safe

## When committing a consequential decision under momentum, do the cheapest check that could change it FIRST (read the mechanism before tuning it, search current practice before working around a behavior, re-read the artifact you're relying on before contradicting it) — because generation has a short head and a long tail: the plausible unchecked answer costs nothing now and detonates downstream, while retrieval is minutes, full stop

## When a skill/runbook has the model do a read-then-write CLI dance (read X's field, then write with `--if-<field>`), verify the READ actually SURFACES the field the write consumes — a write flag EXISTING in the CLI is not the same as its input being OBTAINABLE from the paired read, and static prose-vs-code review checks only the former; dogfood the handoff live (or write a read-then-feed test), because that gap survives even a clean multi-reviewer review

## When reconciling a backlog item a PR *partly* shipped, read ALL that PR's build-plan chunks before declaring any leg still open — a multi-chunk PR routinely lands the docs/methodology/skill leg in a LATER chunk than the code chunk, so crediting only the code chunk falsely marks the item open and sends the next picker to rebuild shipped work (the shipped-but-not-removed drift BKL-8T3W targets); diagnostic before writing requirements: read the delivering plan's `## Build Chunks`, or `git show --stat <merge>` for the doc paths the "open" leg names

## When compacting or migrating a file that tooling parses, classify every span by its CONSUMER before moving it — machine-read metadata (a parsed comment, a `sentinel=` tag, a status marker) is not "narrative" and must stay where its reader looks, because a content-loss guard that only proves "prose is preserved elsewhere" is blind to metadata it silently relocates or drops

## When a session finds uncommitted work in a worktree it did NOT launch in, treat it as another session's territory and leave it alone — a session works only in its own worktree, because sibling WIP belongs to a possibly-live session and adopting it collides with that work and writes into the clone-shared governance state

## When surfacing a batch of model-proposed candidates for owner confirm-or-correct (norm ratification, backlog reconcile, findings triage), triage by decision-worthiness FIRST — surface the few that carry a real fork individually, bulk-confirm the obvious rest, never a flat dump — because a flat list at scale buries the real decisions and trains the owner to rubber-stamp, defeating the review it exists to be

## When writing a durable artifact (code comment, docstring, long-lived spec), never anchor its meaning to an ephemeral build identifier — carry the *why* inline, because build plans are deleted after completion and every project has many "chunk 03"s

## When a durable prose surface holds both released and UNRELEASED sections, "it is history, leave it" is a per-SECTION test, not a per-file one — an unreleased section states pending claims, so a bundle that retires a vocabulary its own unreleased notes announce ships a consumer-facing banner contradicting what it shipped. Tell: a rationale that spares a file by its GENRE ("that's a changelog") rather than by its section's release state

## A red version/release-hygiene test on a feature branch is often a branch-STALENESS symptom, not a doc defect — check distance from the integration branch before patching the changelog

## When `check-cumulative-critic` reports `uncovered` on a branch whose code you know was reviewed, suspect a stale base before running a fresh review — the gate anchors to `origin/<base>` by design, so unpushed integration commits drag already-shipped work into the required span

## When a docstring makes an absolute robustness claim (never raises / always returns / idempotent), make it literally true and test the claimed-safe path — an absolute claim beside a call that *can* violate it is a coherence gap reviewers reliably flag

## When developing requirements to replace a working system, sweep every consumer's actual usage before finalizing — reported pain is a hypothesis, and the loudest complaint is often not the deepest failure

## When a fail-closed validator guards a model-written field, tolerate the natural encoding variant — reserve the hard fail for genuine ambiguity, because incidental strictness at a model-output seam is a latent fail-close

## When the success path threads advisory/audit data through a result envelope, add it to EVERY error-return path too — in an envelope-heavy codebase the error return is built by a *different* constructor (here `core.from_transport_error` vs `core.ok(data, warnings)`) that has no slot for the field and silently drops it; the damage is permanent, not cosmetic, when the datum is one-shot (a self-heal audit line that won't re-run on resume, so it can never be re-emitted). Second instance of this class in backlog-service import (BKL-3K9N rate-limit path, BKL-9V2W TransportError path — both funnel through one outer `except`). Grep the error/exception returns whenever you enrich a success envelope.

## When designing a flow step that records status or bookkeeping, make it ride IN the PR that does the work — a step that can only run post-merge on the integration branch is structurally broken for protected-branch consumers. Exception: bookkeeping that is not a commit. An API status change has no branch to ride, so run it AT the merge, before the artifacts recording the debt are deleted.

## When a governance checkpoint verifies a required side-effect happened, put it OUTSIDE the control flow that produces the side-effect — a check inside the fallible flow can't catch that flow's own skip

## Correcting a false claim is authoring a new claim — verify the replacement and the artifacts it cites, because the fixing mood generates claims faster than the checking reflex fires. The trigger is WRITING the replacement, not reading the original — a correction drafted from the impression left by auditing the source is unchecked. Tell: this cell got a conclusion where every other got a query

## Never write a present-tense state claim ("Phase 1 is complete", "the branch holds X") into a durable document — write the dated measurement plus the command that re-derives it, because the claim is false the moment the next step runs and a reader cannot tell when it was true. This is the WRITE side of [[When a durable plan asserts VCS state]] and it fires hardest *inside a correction*, where explanatory mode about someone else's stale claim coexists with authoring your own: v3.2.3's release plan recorded three stale-measurement instances, and the paragraph correcting the third asserted "Phase 1 is complete now" with the commit and push not yet run — [[Correcting a false claim is authoring a new claim]] did not fire because the replacement's *facts* were verified and only its summary sentence was not

## Before writing any sentence of the shape "X now covers/catches/handles Y" or "there is no Y", run the one query that would falsify it — a coverage claim is the highest-frequency error class here and is almost always checkable in under a minute, so treat the SENTENCE as the trigger, not your confidence in it

## Verify a review artifact's cited gaps against HEAD first — its file-state claims aged the moment it was written, some were never true. A `file:line` you did not resolve yourself is a claim, not a citation: its precision reads as evidence of having been read. Anchor on symbols and headings, not digits — one that visibly breaks gets fixed; one still arithmetically valid under a rewrite never does

## When a backlog item's `refs:` names several surfaces, treat them as candidates and let the mechanism pick the surface — implement only where the condition can actually manifest (and grep for existing coverage first), because mechanically touching every listed ref adds dead or duplicative surfaces the item never needed. STH-3R8K listed SessionStart `digest.py`/`banner.py` alongside the Stop hook, but SessionStart runs in the launch dir *before* any mid-cycle worktree move, so it provably cannot observe the redirect — the Stop path was the only load-bearing surface, and a SessionStart line would have duplicated BRF-6K2D. Descope the dead surfaces explicitly in the item note (Principle 2 — a deliberate scope call, not a silent drop). Relates to Scope Discipline (#12) and [[Verify a review artifact's cited gaps against HEAD first]].

## When you add an ingest/IO surface to a platform-agnostic framework, expose the minimal data primitive — not one ecosystem's file format — or you silently lock out the toolchains the agnosticism promised

## When you add a fallback lookup INSIDE a per-item loop, amortize it AND make it a no-op on the common path — a naive fallback that fires on every miss is O(N²) at scale, and the fresh case is all-misses

## When a test injects a fixed clock, EVERY actor in the scenario must share that clock domain — one real-clock participant (a CLI front, an un-injected default) turns fixed-timestamp + TTL into a scheduled deterministic failure at stamp+TTL wall time

## When a build plan ships in a different release than it targeted, its frontmatter `scope:` must be the scope-NAME (not a version) — `check-releasability` pairs a change-log `scope=` tag to its plan by exact string, and a version there means the release-pending scope resolves to no plan and reports as work shipping with nothing describing it. **A ONE-PLAN-MANY-SCOPES batch cannot satisfy this and must not try**: the field holds one string, so give each shipped scope its own plan (or accept that the batch plan is unpaired and archive it by hand). Recurred at v3.3.4 with `scope: v3.3.4-batch` covering five change-log scopes — five *no build-plan file* advisories and a `plan-backfill` that swept nothing, which is the **second consumer** the rule never named. Both instances were batch releases; the field is written by the builder and read only at release, so the loop is a whole cycle long and the writer never sees the cost — [learnings-detail.md]

## When serially merging several stale feature branches into develop for one batched release, expect additive bookkeeping conflicts every time — and watch for a duplicate `active_build_plan:` key the auto-merge creates

## When a session switches branches after SessionStart, pass the Critic mode explicitly — `infer-critic-mode` trusts the stale session-start branch marker

## When prose picks which model a reviewer/subagent runs on, express it as an ordered fallback chain resolved at dispatch — never a pinned alias

## When you disable a mechanism at its wiring point but keep its implementation, reconcile the retained code's self-descriptions in the same change — or its prose reads as false

## When verifying a framework-repo `lib/`/`bin/` change by running the hook, invoke the repo-local `python3 plugin/bin/prawduct-hook` — the bare one on PATH is the installed plugin cache. A HARNESS-dispatched governance action runs that cache and CANNOT be redirected, so "I ran the real thing and nothing happened" is a skew hypothesis before a bug hypothesis: verify out-of-band instead

## A review finding is about a CLAIM, not a file — resolve it by grepping the claim's wording, and never truncate the recommendation you are acting on

## Verifying an inventory against the code cannot catch a wrong CATEGORY — the check confirms the frame it was built from

## A mechanism that collapses a distinction forces every downstream rule to hold for the WEAKEST member of the collapsed set

## When a finding is "harmless by coincidence," check what makes it harmless before deferring it

## When verifying an assumption, build the instrument WIDER than the proposition — the confirm/deny answer is rarely where the value is

## After a clean cumulative (0 blocking/0 warning), NOTEs are advisory — don't chase cosmetic ones; fixing them reopens the coverage gate on judgeable governance files and forces a no-value review pass

## Hand-tick a build plan's `## Status` box the moment its chunk's review passes — nothing derives the boxes, so an unticked one claims the work is open and every reader believes it. Review first, tick after: the LAST tick disarms the Stop gates. **Inverted 2026-08-08** ([[the-derived-views-retirement]]) — prose calling the boxes untrustworthy is the old rule still running — [learnings-detail.md]

## A change-log entry's BODY must cover every chunk the entry shipped — the body IS the release note, so a deliverable the prose omits ships invisibly. Losing `chunks=` ([[the-derived-views-retirement]]) removed the *illusion* of a check: the tag counted chunks, never read the prose. Tell, now the only one: a multi-chunk narrative with ONE throughline — the last chunk's mechanism goes missing

## When a requirement is about a COST, assert the operation that costs — not a proxy that usually accompanies it. Tell: your test names a side effect ("was the file read") where the requirement names work ("was the directory walked"); the two come apart in exactly the implementation the requirement forbids

## When a feature's logic lives in a `context:fork` skill (no Bash), `lib/` holds the DATA, not the LOGIC — logic helpers nothing imports are dead code

## "I'm just codifying their guidance" is not an exemption from the research trigger — and volatility is a separate axis from knowledge-confidence

## The "canonical" mechanism for a capability can be disqualified by a plugin's composability + always-on constraints — verify the constraint before adopting the recommendation

## When fanning out a batch build to parallel worktree-isolated workflow agents, partition by disjoint file ownership (integrator owns shared files) and force-clean leftover worktrees before the integration suite

## When a fresh-eyes review's advice about a CONVENTION conflicts with a durable learning + the process doc, the documented convention wins — re-verify before acting

## A reviewer's NOTE/severity is a prior, not a verdict — re-scope any "harmless" change that touches a governance-gate input, and `grep` the value's READERS before concluding it isn't one: a field's comment block tells you what it is for and how it has failed, never who consumes it, so inheriting that framing feels like coverage and isn't (clearing `active_build_plan: null` was argued from its own long comment block — record-lint, Critic mode inference — and silently flipped the reflection gate to advisory and skipped the Critic gate entirely, caught only in review)

## A new framework-wide DEFAULT must land in the session digest — place-once preferences and the thin anchor don't reach migrated repos

## Single-repo plugin+marketplace: the marketplace entry's plugin `source` must be a RELATIVE PATH, not `{source:github,ref}` — and that path is a curated subdirectory, not the repo root

## Release-bound work merged feature→develop under gitflow: KEEP the build plan and the `active_build_plan` pointer until the release — `check-releasability` pairs each release-pending `scope=` against the plan declaring it, so deleting early turns your own shipped work into "work with no documented parent"

## A `--plugin-dir` read-block is a dev-flag artifact, not a self-containment bug — pair it with `--add-dir`

## Test subprocesses: HOME=tmp_path leaks Python's pyc cache into the test repo

## "Structurally enforced" requires verifying the harness actually enforces it

## Tool-restricted reviewer agents must be context:fork SKILLS, not named plugin subagents

## When a deliberate change turns a passing test red, renegotiate the contract in the open

## A behavior change isn't done until every artifact that DESCRIBES it is updated

## A decision reversed mid-chunk leaves stale rationale in prose you just wrote

## Editing a runtime that governs the current session: check your own signals first

## Pre-dispatch bootstrap code must fail open on a `lib/` ImportError

## Session-end signals must come AFTER handoff

## Artifacts drift silently during sustained building

## Structural gates must match natural workflow

## Growing files need structural nudges to prune

## Reactive systems can't detect missing things

## Governance complexity breeds governance complexity

## Principles need runtime enforcement, not just change-time checks

## Denormalized state drifts without mechanical validation

## Coherence cascades require checking summaries, not just primary locations
<!-- prawduct-learning: confirmations=2; created=2026-01-30 -->

## Escape hatches in classification create silent failures

## Cumulative-Critic finds first-use regressions chunk-Critic can't

## Auto-enable belongs with visibility, not with enforcement

## Removing a mechanism requires removing its name too

## Build-plan fields use `**Title Case:**`, not snake_case

## Build-plan chunk parsers accept `### Chunk N:` AND `## Chunk N (ID) — Name` (BLD-5J8N) — but number your chunks, because the unticked-committed-chunk advisory matches `Chunk <n>` with a NUMERIC id in a commit subject and a plan using `Chunk A` gets permanent silence from it, indistinguishable from every box being right

## Submodule and same-name function in __init__ shadow each other

## Detection of structural characteristics should not rely on mechanistic surface markers

## Shared "answer" state and personal "nag" state belong in separate stores

## Framework ownership follows the write strategy, not just registry membership
<!-- prawduct-learning: confirmations=1; created=2026-05-19 -->

## A leftover marker is not an in-progress signal — and a test using the canonical marker leaves the real-world branch untested

## A near-verbatim file PORT carries the source's prose — adapt the docs, not just the logic

## Verify the platform's copy/packaging boundary before duplicating a shared bundled file — a prior "duplicate into each consumer" choice may be an unverified-constraint workaround

## Dogfooding the generator on its own output masks output-relative bugs the real consumer would hit

## A review's "inert / harmless" verdict on a latent bug is conditional on the current call graph

## Excising a subsystem silently kills the incidental work it happened to host — re-home the orphaned call, and test the positive

## A deletion's SURVIVORS owe new coverage when their behaviour changed — the deleted thing's tests dying correctly is a different question

## In a leaf-first decomposition, dependency-scan a chunk's COMMAND bodies against later-chunk symbols before moving — and never move a parity-pinned mirror just because a deliverable lists it

## A format's schema legend lives in `templates/` (scaffold-only) — adding an optional field reaches already-onboarded repos only via a migrate/triage *refresh* step, not the template

## A structural bound that ENFORCES a declaration is not a DETECTOR of the declared property — reusing it at a new boundary silently drops its justification

## A rebuild scoped to a subsystem's "remaining / deferred" parts silently omits an already-shipped part that was deleted in between — re-port against the spec roster, not the open-work list

## A persisted schema's requirements are its consumers' future queries — lock-in is reversal cost, not LOC, so "small format" never exempts it from decision research

## Test-evidence freshness is the `test-status` exit code ONLY — never a commit/SHA field (`git_sha` retired as misleading, TST-4K2P); what that code composes has grown (session timestamp, the relax-only tree-validity clause, and the record's own `degraded` flag), so read the gate, not a remembered rule

## A cross-cutting concern can be UNCOVERED even when discovery names it once — audit the coverage matrix for "named-but-dropped", not just "absent"

## Before "fixing" an apparent forgotten-manual-update, check whether the artifact is a GENERATED / DERIVED view — the real fix is upstream

## When a plan sets a quantitative reduction/size floor over a corpus you cannot shrink by dropping content, derive the floor from a per-file compressibility sample — not a global intuition

## Never chain a test-evidence `record` after a suite run in the same command, and never read a piped suite's exit code — read the run's own summary first, because a false-green record pollutes the gate exactly like a false-red

## Re-attempting a mechanism rejected for a false-positive class: make it ADDITIVE and relax-only, and separate the framing from the primitive

## When validating a CLI's JSON output, feed the tool the raw bytes (direct pipe or file) — never `echo "$captured" | jq` under zsh, whose `echo` interprets `\n` and turns valid JSON into a false "malformed output" finding

## A proactive nudge narrowed to pass a "zero-fire against this repo" acceptance criterion suppresses the exact signal on the reference repo — check the repo is genuinely OUT of the target state before muting

## For a coverage / forcing-function opt-out, make the resolution a first-class recorded artifact (even a one-line stub), not a suppression flag

## When a later chunk extends an earlier chunk's module with a derived/richer version of a constant that module already defines by hand, grep for the name first — you otherwise create a SHADOWED DUPLICATE that silently works until the two drift, and the fix is to make the richer structure the source of truth the older constant derives from

## Idempotent-re-run crash-safety is only sound when SOME actor is guaranteed to re-run the same transition — when recovery depends on the crashed party specifically (the one who won't return), make the write ATOMIC, not merely re-run-convergent

## A human-mode output formatter that dispatches on "which key is present" silently shadows a new result type sharing a key with an earlier branch — order the checks most-specific-first, and TEST the human path because `--json`-only tests never exercise the formatter

## An "unverified / validated-when-run" honesty caveat covers only genuinely-unknowable facts (live behaviour, external state) — NEVER facts checkable now (a key path, a signature, a flag); verify the knowable, disclaim only the unknowable

## A repo-coupled (non-hermetic) test turns every "non-judgeable" doc/state change into a silent test-breaker — the doc-only and test-status classifiers assume non-code files can't change test outcomes

## A `/prawduct:*` skill fork writes `.prawduct/` state to the LAUNCH dir, not a worktree the session ENTERED mid-session — launch/`/clear` inside the worktree, or relocate the fork's output and restore the polluted checkout

## When salvaging work from a branch you are about to delete, diff the ID SETS of its state files — a commit-by-commit triage silently drops novel items that ride inside otherwise-obsolete commits

## Before filing a finding against a mechanism, read that mechanism's own documented degradations — a design that enumerates its deliberate weaknesses has usually already considered yours

## A channel that is produced and never consumed is a DEFECT, not an inefficiency — name the consumer in the same change that adds the producer, or don't produce

## Anything in a durable artifact that one command could check is a CLAIM — an identifier, a count, a `file:line`, or a facet value, not just a rationale — so run its falsifying query first. The rationale you REACHED FOR to defend a decision already made is the one to verify, and a CORRECTION is itself a completeness claim: quoting the parent rule demonstrably does not prevent this

## A sample you sliced for DISPLAY is not the set — if the command that formed your impression carried a `[:8]` or a `head`, re-run it unsliced before writing "all/every/entirely", because the slice is invisible in the output you read back. A RETRACTION is where this bites hardest

## A status surface that reports the ABSENCE of expected output must say whether absence is the normal in-flight state — a bare zero invites the reader to invent a death story and take recovery action against healthy work

## When auditing guidance material, have a fresh agent USE it before you recommend changing it — analytic review predicts defects that do not survive contact with practice, and the trial is what tells you which findings are real

## In an append-heavy file, a union merge is safe only when neither side RELOCATED an entry — a moved item reads as "absent here, present there," which is exactly the shape a union is built to merge

## "Advice fails soft" is not "advice fails silent" — a degraded advisory path must still name its consequence, or it manufactures the false success it was meant to prevent

## A fix lands at the instance a review named; the defect lives in the class — state why it broke in one sentence; if that sentence does not name the site you fixed, it defines the class, whose members sit OUTSIDE your diff and stay invisible. Route it through one owner, not a longer list. Tell: several findings share one sentence; your fix is one row — [learnings-detail.md]

## A CLI on `$PATH` is a different checkout from the worktree you are editing — an interactive command's exit code is not verification evidence for a change to that command

## When a durable plan asserts VCS state ("the code lives on branch X, not develop", "resuming means landing Y", an ahead/behind count), re-derive it from git before acting on or copying it — plan prose about branches and merges is a snapshot that expires the instant the next merge lands, so run `gh pr view` / `git merge-base --is-ancestor` / compare tree hashes first; a since-merged "land this branch" step is a no-op a plain merge performs silently, and the check costs under a minute

## When you relocate importable code behind a conftest sys.path shim, standalone/non-collected scripts do NOT get the shim — grep for `__main__` scripts that self-insert the old root and fix each, because conftest only fires under pytest

## Before predicting a per-minute rate ceiling will engage, check whether serial round-trip latency already caps throughput below it — a rate ceiling is bounded by requests/min = 60 / round-trip-seconds, so it never binds on TOTAL volume no matter how large; it binds only when you issue requests concurrently/batched faster than one round-trip drains

## When a triggered job must observe a state that a LATER step creates, you have found a RACE, not a certainty — the ordering argument yields the hazard and only the wall clock yields the verdict, so read the dispatch/observation/conclusion timestamps before writing EITHER outcome into a durable document. v3.2.4's release plan asserted the tag-push `verify-release` job was "red by construction" because the GitHub Release is published one runbook step later; it went GREEN — runner spin-up plus `checkout` burned the first 11s of a 20s job while the publish landed at +11s, winning by ~9s. Same root as the rate-ceiling rule above: the mechanism was reasoned about and never given a number. And a race that usually passes is a WORSE finding than the deterministic red, because a deterministic red gets fixed and an intermittent one gets learned as noise — so the wrong prediction would have buried the more valuable result, not merely mis-stated it

## When you change a MECHANISM, cascade-search the CLAIM as well as the code — grep the tokens you edited and you find every site that runs the old procedure, but not the prose that merely DESCRIBES the old behaviour, which shares no token with it. Fixing the tag/publish order caught both runbooks and the process doc via `git tag`/`gh release create`; the Critic then found a stale "on every tag push" in `architecture.md`, a superseded command in a historical release plan, and one doc asserting flatly what another hedged — none reachable from the command strings. Search for what the system is said to DO, in the vocabulary a describing sentence would use

## A durable record inherits the confidence of its DERIVATION, not the authority of its author — before propagating a claim out of an issue comment, release plan, or prior reflection, check the mechanism it rests on, exactly as you would a claim you generated. #581's disposition read a tag-push CI run as proof that workflows resolve from the tagged commit's own tree; the promotion had pushed `main` first, so ordinary default-branch registration explained the run completely and the evidence isolated nothing. It was copied into the change-log unchecked because it was owner-authored and already written down. Both are the same failure the record itself was warning about: reasoning about a mechanism without measuring it

## When one fix must hold for N procedures, cost it against the WORST of them, not the one that surfaced the bug — the cheap option is usually cheap only for the case you were looking at. Narrowing the tag→publish window was defensible for the whole-develop runbook (a 9-second margin) and impossible for the pruned one, whose release notes need a hand-edit inside that same window; reading the second document before choosing is what eliminated the option that looked cheapest

## When a release has two documents tracking its state, one is already wrong — designate a single live tracker and demote the other to a decision record; and author each build chunk from the TREE, never from the upstream plan, because a plan derived from a plan describes intent the code may have overtaken

## State precedence among named alternatives RELATIONALLY ("`BLOCKED` wins any overlap"), never by position ("the earlier one wins") — list order is presentational and gets reordered the moment someone improves the prose, so the ordinal inverts while every word still reads true; the tell is a worked example that is the only thing keeping the general rule honest

## When a shape changes, re-read every rule that POINTED AT the old shape — one exact under the old shape ("takes the second line") degrades to a location rather than an instruction once that slot holds several meanings, and it degrades silently because the sentence stays grammatical; a presence test pinning the rule passes throughout

## When a guard test pins a safety claim, assert the PROPERTY, not one spelling of it — a test that matches a literal (an exact flag token, an exact grant string, a substring anywhere in a file) passes for every rewording of the same defect, so write the check to answer the question the property asks and verify it red against a DIFFERENT phrasing than the one that prompted it

## When the deliverable is INSTRUCTIONS, at least one guardrail must model the READER — tests that measure the artifact (size, budget, "the right words are present") all pass while the instruction has no effect, because none of them read the file in the order an agent reads it

## A spike that discards its code leaves its numbers unfalsifiable — commit the derivation as a runnable script and cite the command, never the digits, because a count transcribed into prose goes stale silently as the corpus grows; the fix is not counting more carefully but moving the count out of prose entirely

## Routing a filing to the handoff is NOT filing it — file the item the moment you decide it should exist, because a handoff note is read by a session that arrives with its own plan and treats an inherited instruction as context rather than work, and an unwritten handoff (crash, context exhaustion) loses it outright; "later" has two independent ways to never happen and costs the same as now

## A completeness claim asserts the falsifying COMMAND now returns nothing — never a count of sites fixed, which is true of any prefix of the real set. The query is itself a mechanism and can carry the defect it hunts: normalize the text before searching, because line structure is not semantic structure, and query the CONCEPT, not the phrasings you already found wrong

## Reads as evidence, is not: an absence-claim citing a path that does not RESOLVE, a missing directory returns the same empty result as the claim being true; a disposition recorded from intent, not the diff, which the next reader trusts INSTEAD of the findings; a commit crediting a backlog item by TITLE while its filed reproduction still reproduces; and a subagent's COUNT or LIST, a lead

## Green is evidence ONLY about what could have made it red — for each test name the change that would turn it red; if you cannot, it measured nothing. The fixture may never reach the subject; a constant-equality assertion survives an inverted comparison while its NAME convinces the reader it is covered. Same for a live probe: say what a FAILING run would have looked like before recording one

## A passing assertion may be satisfied by something other than the property — an unimplemented flag passes because the arg guard REJECTED it (assert success BEFORE absence); a prose SUBSTRING stays green under any longer sentence containing it (when prose changes meaning, grep tests asserting FRAGMENTS, not just failing ones); a proxy passes every test you thought to write — gate on the named event

## A test inherits inputs nobody declared and properties nothing observes — machine state, a load-dependent race in setup, and a value silent by construction, so a stage whose worth is SPEED needs a test that fails when it stops being fast. Mutation is one-directional — reverting removes the damage alongside the fix — so pair it with branch coverage of the function you touched

## A self-authored adversarial pass inherits the author's blind spots — the cases you think to attack are drawn from the same model that wrote the code, so the gap that survives is the one you cannot see. Get the adversarial read from a context that did not write the subject, or pick the attack from a roster you did not author

## A text-anchored edit changes a NEIGHBORHOOD, not a point — the anchor names a line, but the insert lands in a structure extending past it, and both still compile. Inserting at a `def` puts the function between the next one and its decorator; restructuring `try/except` into `try/except/else` strands the fallback in `else`. Re-read the enclosing block after every anchored edit; the suite stays green

## Exactness is owed to a number something RELIES ON for a decision, not one something merely READS — ask what branch is taken differently if it is wrong by two, and if none, the precision is waste. Reading is passive and nearly universal, so "something reads it" licenses precision everywhere; verify the CONSUMER before defending the cost you already paid for it

## A filed item's stated MECHANISM is a hypothesis, not a finding — reproduce it against live data before designing the fix, because the reporter saw a correlation and wrote it up as a cause, and the item's own evidence often carries the disproof. Run the command and reconcile against the source of truth, THEN read the item again

## A deferral justified by "there is no consumer yet" is scoped to the surfaces that consumer does not touch — when one appears, the premise goes false without the decision going wrong, so restate the SCOPE rather than retiring the deferral or amending the decision. Record it as a ruling, and enumerate the now-supported surfaces in one place every other mention tracks — a count stated in four sentences drifts on the first correction

## A token budget is raised only when the framework is provably better FOR THE RAISE and upleveling has no headroom left — cut the class, not the words: dates, running tallies, worked examples, and definitions another file owns and tells the reader to open are removable outright, and rewrapping returns nothing against a word-count estimator. What looks unaffordable is usually history

## A rule you must RECALL at the right moment is its weakest form — when it governs a class of claim you can query, convert it into something that runs: a test, a lint, a rendered table. Recall fails hardest on rules you just wrote or read, because familiarity reads as compliance; if every catch in a work cycle came from a mechanism and none from memory, mechanise the next one

## A sentence's RHETORICAL ROLE can select its content over a fact you already hold — the justification slot pulls whatever makes a decision sound principled, while the caveat slot states the truth correctly two sentences later. Check the load-bearing clause against the mechanism, separately from reading the paragraph for sense: reading for sense passes it, because that is what selected it

## A disposition claiming "fixed" must restate the FINDING'S OWN predicate and show it false — arguing from what the change FOUND is satisfiable by fixing an adjacent surface. If the finding says *the check cannot see X*, the closing test asserts exactly that sentence. Tell: the fix note describes what the fix caught rather than what the finding said

## "Make A agree with B" has two solutions and the cheap one hands A the defects of B — an agreement criterion is satisfied by teaching A the narrower predicate, so it cannot tell correctness from consensus and goes green with both wrong together. Pin the DIRECTION separately, on a fixture from the population that predicate is worst at. Tell: every fixture sits inside its allowlist

## Citing a named procedure is a claim that you RAN that procedure — re-read the named step before citing it, because two independent recalls fire and each feels verified by the other: you reach for the test you KNOW and attach the authority you REMEMBER. A right conclusion on a substituted warrant is the durable defect, since conclusions get re-derived by the next reader and warrants get copied. Repair by running the named test, never by softening the citation

## A guardrail whose anchors come from your MENTAL MODEL of a file is a second copy of the claim, not a check on it — derive them by reading the file, line by line, as you write the test, because otherwise the test encodes the same error the claim does and goes green over it. Tell: you can write the anchors without opening the file

## A green suite is evidence about the ONE environment that ran it — a suite only ever run by its maintainer has untested dependencies on that machine rather than no dependencies, and the second environment is what finds them. Expect the first CI run to be red and treat that as the run working; the recurring shapes are in [learnings-detail.md]

## When you fix a defect of a named class, re-run that class's own check against your fix — the fix is the likeliest place to reintroduce the class, because attention sits on the content of the claim and not on its mechanics. A citation repaired by renaming it, then line-wrapped inside its backticks, is still unresolvable to the grep that would find it

## When a trim is justified by the surrounding prose's OWN instruction, run the suite before trusting it — the dangerous cut is the one the file appears to endorse, and a sentence that restates a nearby rule where the reader SKIPS it is placement, not a copy — [learnings-detail.md]

## Making a capability conditional on the RUNTIME retroactively conditions every existing test whose fixture touches it — the affected set is not the set you wrote, since shared fixtures carry it into tests that never mention it. Simulate the degraded runtime over the whole file before commit; a reviewer surfaces one and it reads like the one — [learnings-detail.md]

## When a check's subject is a SET (files scanned, paths matched, items collected), assert the set is non-empty and contains what the check names — otherwise green means "nothing was looked at", and the check passes forever

## When you add a member to an enumerated set in code (a fact kind, a waiver rule id, an exit code), the registry that DOCUMENTS that set is owed a row in the SAME commit — four went stale in one chunk, and three cost a full review round each because the gap is cheap to fix and expensive to notice

## A reviewer severity is a SCHEDULING decision, not just a risk rating — BLOCKING means "the tree must not move again without this", so a record gap that can ride a commit already owed is an observation; rating it BLOCKING spends a whole round on a one-row edit

## Before choosing block-vs-warn for a gate, establish WHO is at the write — a refusal in front of a human is a stop, but in front of an AGENT it is an auto-fix, and an auto-fix performed to satisfy a gate is a silent mutation nobody reviewed. Tell: you are weighing "strict vs lenient" and have not named the caller

## Promoting an advisory check to blocking changes what its false positives COST, so audit them as part of the wiring — a placeholder lint matched "fix it" inside "pre-FIX IT-em" harmlessly for years, then became a false refusal on an irreversible migration. Fix the classification, never the budget

## A gate on a value that nearly every fixture supplies will touch nearly every fixture — estimate that blast radius in the plan, because it changes the chunk's real size. Enforcing a title rule broke 126 tests across 8 modules, none of which asserted anything about titles; fixing fixture DATA (never assertions) is correct, but discovering the number at build time is a planning miss

## Derive what an instrument can OBSERVE before deciding what it is worth — recommendation formed first makes verification a correction instead of an input. Two over-claims in one session from this: a per-file coverage gate sold as catching branch-level gaps, and branch coverage sold as the lever when line coverage already catches an untested arm (its body never executes). Tell: you can name the gate's benefit but not the field it reads

## Search the backlog before proposing to ADD to it — the existing item is often not just a duplicate but a better-framed one, and adopting its framing beats re-deriving a worse one. A repo-local "install coverage here" proposal was already filed as a consumer-first, language-agnostic item six weeks earlier, found only because the owner asked a question that forced the search

## "Has this repo already decided it?" is the cheapest check that could change a design — run it BEFORE deriving, not after, and run it against **every document the thing you are planning from names as a parent**, not only the governing artifacts' `## Direction` sections. A derived answer arrives without its constraints attached: the socket architecture was ratified in `architecture.md` a week earlier and my reasoned-out version was missing the no-third-party-dependencies implication. **Refined 2026-08-07 after the narrow reading failed:** every Direction norm in `.prawduct/artifacts/` was dispositioned and a W1 build plan still invented a table schema and proposed AMENDING a norm to settle a question `documentation/backlog-service-data-model.md` §7 answered in one sentence — because the decisions for that subsystem lived in `documentation/`, not in the directory I had internalized as "where decisions live." Tell: you are pleased with an architecture you have not yet traced to a parent — or you are planning from a spec whose header says `**Parent:**` and you have not opened them

## A spec that deltas a parent corpus reads COMPLETE, and its omissions are deliberate — so treat "this document seems to cover everything" as evidence it is a delta, not evidence there is nothing else. The W1 cache spec was a well-written delta on a reviewed corpus (schema, schema-versioning, two security findings about that exact cache, NFR staleness rows, a test catalogue); planning from it alone produced a plan that re-derived the schema and missed both security findings, one of which was in live tension with a decision the spec itself made. Tell: a design document that answers every question you thought to ask, on a subsystem old enough to have been reviewed before

## Run the mechanical seeder BEFORE drafting, not after — used as an audit it finds the gap too late to be cheap. `prawduct-hook jurisdiction` ranks candidate governing artifacts by vocabulary overlap, and it surfaced a security model whose findings reshaped a build plan already written; run first, it would have been an input instead of a rewrite. Generalizes beyond this command: when a design feels finished, the cheapest reopener is a mechanical one, because unlike a careful re-read it is not subject to your having already decided. Tell: you are about to write up a design you are satisfied with

## Observable beats stored — when a signal can be derived from what git or the provider already maintains, do not add a field for it: a stored field can be forgotten, can lie, and needs a write path nobody has built. A branch's last commit beat a claim timestamp with an expiry policy; the provider's `updated_at` beat a `reviewed:` field that is currently unwritable, dissolving a "hard prerequisite" in the process. Tell: you are designing an expiry or freshness policy for a field you also have to remember to update

## A docstring stating a guarantee is an ASSERTION, not a verification — when you write a rule you know into a docstring, check the API can actually express it before believing the sentence. I wrote "the cursor is written in the same transaction as the rows it covers" *because* the learnings pass had handed me the rule, then shipped two functions each opening their own transaction; no test failed, because the chunk that had the bug degraded harmlessly and the chunk whose correctness argument depended on it was not written yet. Tell: a docstring that states a rule you were pleased to have remembered, on a guarantee no current caller exercises

## A number that disagrees with another number is a bug report, and "that source is stale" is the explanation that stops you reading it — chase two-digit discrepancies before explaining them away. The cache said 178 open and the session briefing said 182 pending; the snapshot genuinely WAS 27 minutes old, which made the wrong explanation available and correct-sounding. The real cause was a consumer query filtering `status = 'open'` literally and dropping `submitted`/`in-progress` — invisible to every fixture (which had no such items) and to live verification (ditto). Tell: you can name a plausible reason two counts differ without having checked that it is the actual reason

## A test written RELATIVE to the constant it polices can never detect that constant being wrong — pin the absolute value when the value is a historical fact (a version a real store was stamped with, a format that shipped), because `CONST - 1` moves with CONST and passes at every setting of it. Tell: the mutation you expected to go red stayed green

## A measurement with no POSITIVE CONTROL cannot support a claim — before believing "X costs nothing", confirm the instrument MOVES when it should, because a dead instrument reads zero for the treatment and the control alike, and zero is the answer you were hoping for. Tell: the confirming result arrived first try and the null case was never run

## For every value you plan to PERSIST from a provider, verify the exact request that will later REPLAY it, not just the one that produced it — a verify-api step scoped to the plan's own mechanism confirms that mechanism and misses the one the plan got wrong

## A build plan can name a CODE IDENTIFIER it never opened, and that is where a plan is most confidently wrong — before implementing a deliverable phrased as "add X to `Y`", open `Y` and check it does what the sentence assumes. Tell: the plan names a symbol and you are about to edit it without having read it

## A VALIDATOR that only refuses the malformed can still let a control fail OPEN — when a validated value is interpolated into a URL path, a filesystem path, or any other resolver, ask what ELSE the value could successfully resolve, not just whether it parses. Tell: your validator's rejections are all shaped like "this is not well-formed" and none like "this is not the thing"

## Changing HOW data ARRIVES silently re-scopes every aggregate over it — the code still computes, the value still looks plausible, and nothing fails, so no test catches it. After a switch from full scan to incremental (or batch to streaming, snapshot to log), walk every aggregate, watermark and age over that data and ask what each one MEANS now, not whether it still computes

## A retirement is one act PER SUBSTRATE the thing lives on — read your own rationale back before executing it, and bound the edit to the backends each clause is actually about. Tell: the rationale names a backend, a release or a provider, and the diff names none

## A rule enforced only as a SIDE EFFECT of some other failure is unenforced for every change whose failure mode differs — when a rule has a real incident behind it, ask what actually caught that incident; if the answer is "something else broke loudly," the rule has no guard of its own. Tell: a mutation you expected to be caught is not, and the rule it violates has a documented past incident

## A change-log `scope=` tag comes from the PLAN you are in, never the entry above it — `check-releasability` matches it to plan frontmatter by exact string, so a copied neighbouring scope attributes your work to someone else's plan and BOTH readings stay quiet: that scope does resolve to a plan, and yours reports as pending with nothing describing it. Tell: your branch narrows an existing scope

## A pattern narrowed to kill a false positive is validated against the case that PROVOKED it — which is the one case already known — so re-run it over the whole corpus before installing it, counting what it stops matching as well as what it starts. Tell: the narrowing was "verified against this branch's real subjects"

## A new key in a shared namespace needs a collision check against real DATA before it needs a test — grep the live corpus for the name and ask what already means something by it, because a writer that strips "its own" keys silently deletes a homonym and every test you wrote for your own semantics still passes. Tell: you picked the obvious short name for a frontmatter/config/tag key

## A parser shared between a READER and a WRITER inverts its safety on malformed input — "assume it runs to EOF" is tolerant for a reader and "delete to EOF" for a writer, so a writer must claim nothing it cannot delimit. Tell: you reused a reporting scanner inside something that edits files

## When defending a design with "we shouldn't lose the record", check whether the real reason is REVERSIBILITY — they take different fixes and the preservation framing gives the worse one. History earns its keep only by helping going forward; reversibility is answered by a preview plus version control, not by refusing to act. Tell: a second "report but don't touch" bucket appeared to protect prose

## A list an operation-level approval is given for must IDENTIFY its items — consent to four indistinguishable `build-plan.md` lines is not informed consent, and the repo's display helper usually already solves it one module over. Tell: your preview prints bare filenames and every fixture you wrote is flat

## A structural guard that fires on your own justified change is answered, never re-floored — record why the population moved in the assertion's own docstring, and add a companion assertion pinning the part that must NOT move, so the next widening cannot ride the same exemption. Tell: you are about to relax a floor because your change legitimately shrank what it counts

## Export the ANSWER, not the walker — a caller needing "which chunks are unticked" gets a finished list, because exposing the traversal is what lets the next consumer re-derive the question privately and give it a third answer. Tell: you are about to make a private parsing helper public so one new caller can use it

## When fixing a SILENT SWALLOW, find the frame that actually discards — it is usually one layer below where you noticed the symptom, so a report added at your call site is empty by construction and its test passes on a healthy repo. Tell: your new "problems found" list is structurally never populated

## A guard written against the EXAMPLE IN THE FINDING holds for that example and nothing else — restate the threat in your own words before coding it (`is_relative_to` is lexical, so one `..` walks through a containment check that passes the reported case). Tell: your fix quotes the report's scenario back at it

## Fix a defect at the LAYER IT WAS REPORTED AT — pinning the extracted predicate proves the predicate, not the wiring, so deleting the CLI branch leaves a lib-level test green while the reported defect returns. Tell: the finding says "at the CLI" and your new test imports the module

## A mechanical "is it finished?" test keyed on a REUSED identifier archives live work — a work-stream name that shipped once makes its next round look finished, so require that no LATER entry for that name is unreleased, and decide by DATE rather than document position (half a 14-repo fleet had out-of-order change logs). Tell: your predicate says "has a release tag somewhere"

## A file's own header comment is not the first key's — bound any comment walk-back at start-of-file, because with no preceding content line there is nothing distinguishing a section banner from the document header, and deleting the latter is content loss in a hand-authored file. Tell: your walk-back is `while start > 0`

## Preserve line endings in any writer that edits a file it did not create (`newline=""` on BOTH the read and the write) — a CRLF repo otherwise gets every line rewritten by an operation that promised to touch two keys, and the real change hides inside a whole-file reformat. Tell: you used `read_text`/`write_text` in a repair

## Moving a value into a NEW channel silently unwires whoever read the old one — when a fix relocates data (a refusal from `refused` into a pre-filtered `blocked`), grep for readers of the old key before committing, because the diff reads as "what this function returns" while it is also changing what the process EXITS with. Tell: your fix adds a return key and removes items from an existing one

## A REMEDY named in a checklist must be tested against the predicate that produced the condition — advice that cannot terminate is obeyed, unlike advice that is merely stale, so "run X then re-run until it exits 0" is wrong whenever X consults the same refusal the sweep just did. Tell: your recovery step names a command rather than sending the reader to the reason's own remedy

## Prove a new regression test DISCRIMINATES by running it against a stash of the pre-fix source — a fixture that fails one step early never reaches the subject and passes either way, which is indistinguishable from a working fix. Tell: you wrote a test for an error path and never saw it red

## A step is release-PREP only if undoing it costs nothing — if the step is what MAKES the release happen it belongs to the cut, whatever phase the checklist files it under. "Bump the version" sits under prep and is the trigger (`version` is the auto-update cache key); stripping a `— DRAFT` suffix is what makes a section publishable. Doing both while "not releasing" leaves the repo one promotion from shipping with every in-repo signal saying it already did. Tell: you are about to do a prep step you could not reverse by deleting a file — [learnings-detail.md]

## When you swap a mechanism's input for a COPY of a file, ask what the original's METADATA was load-bearing for — filesystem metadata is often a protocol, so a byte-identical copy is silently NOT an identical input. `copyfile` dropped the git index's mtime, silencing git's racily-clean rule, and the tree capture could then vouch for content never on disk — [learnings-detail.md]

## An exemption filter added to keep a self-referential test honest on a clean clone silently exempts every environment the subject is unreachable from — so the test is red where it can see and GREEN where it cannot, and CI, the blind one, is the copy people trust. `test_no_norm_lifecycle_advisory_fires_here_today` drops `backlog-cache-unreadable` candidates, which is correct (that condition is true about a machine, not the norms); but the backlog cache is gitignored, so in CI the probe reports unreadable instead of `stalled-transition` and the assertion passes having never reached its subject. Local 5553p/1f, CI 5554p/0f, same 5571 total. Whatever such a test exempts, assert its subject was REACHED — an exemption without a reachability assert is an environment-shaped hole. Tell: a `TestSilentAgainstThisRepo`-style test filters a candidate type whose cause is 'we could not read X', and X is gitignored — [learnings-detail.md]

## A test asserting against its OWN repo's live state pins the repo's current PHASE as an invariant — and a release is the event that ends that phase, so the suite goes red at the worst possible moment, under pressure to relax the assertion. Six `TestAgainstTheReal*` guards died together at v3.3.0 because tagging every change-log entry emptied the release-pending set and archiving every shipped plan emptied the live plan map — both steps working as designed. The guards were RIGHT (an earlier round added them to stop vacuous passes) and the release was RIGHT; they were still incompatible. Make such a test say WHICH emptiness it rejects, or it cannot tell "we just shipped" from "the join is broken". Tell: your test reads the real tree/log instead of a fixture and asserts something is non-empty — [learnings-detail.md]

## A test that derives its own fixture from the mechanism under test converts that mechanism's failure into a SKIP, and a skip is indistinguishable from a pass in a summary — so the bug ships green. The helper for `test_archiving_a_real_plan_removes_it_from_the_live_map` picked its victim plan as "in the archived map but not the live one", which reads as obviously correct; disabling archive pruning — the exact defect the test exists to catch — made that difference empty, and the test reported "nothing to perturb" instead of failing. Select fixtures from a source INDEPENDENT of what you are grading (walk the directory, don't ask the resolver), and make the precondition an `assert` with the defect named, not a `pytest.skip`. Tell: your setup calls the same function the assertions call, or a skip condition could be *caused by* the bug — [learnings-detail.md]

## Prove a guard can go red before believing it — mutate the real corpus and watch each assertion fail, because a guard nobody has falsified has measured nothing and its docstring will claim more than it does. Nine mutations against a copy of the real tree found two defects in a repair that was already green: a helper that skipped instead of failing, and a rewritten "this scope resolves" test that could no longer catch a WRONG scope value at all (the map is keyed from the same frontmatter the test re-reads, so a consistent lie agrees with itself). Neither was visible by reading. Where a limit survives, write it into the docstring under "what turns this red" rather than letting the prose imply coverage that is not there. Tell: you rewrote an assertion and ran only the passing case — [learnings-detail.md]

## A release-prep note enumerates the obligations ITS AUTHOR FORESAW, so re-derive the version TIER from the final scope set rather than inheriting the draft's number — a number chosen when the bundle held one scope is a guess about a release that now holds three, and `check-releasability` grades the partition while printing the version it never grades. A subsystem going live was about to ship as a patch because the draft predated the two scopes that made it a minor. Tell: your version number came from a document rather than from the scope set — [learnings-detail.md]

## RULING (harness-only-removal-is-not-a-major), 2026-08-11 — harness-only subcommands may be removed at any tier; the major-deferral governs the externally-callable surface only. **Warrant falsified same day (v3.3.3), scope settled by `[[deprecation-requires-an-inert-retention-window]]`** — read both before applying it — [learnings-detail.md]

## When you argue a deletion is safe because its only caller ships and updates in the same commit, check who INVOKES that caller — if it is the harness, that caller is the one that routinely runs against a mismatched binary, because plugin version pins are per project and lazily updated. Unregister now; keep the subcommand inert until no supported install still registers it — [learnings-detail.md]

## (one-home-is-the-predicate-not-the-token) — the case behind `architecture.md` § Direction's 2026-08-11 granularity amendment (#643). Sharing a MATCHER shares syntax, not the DEFINITION: the reader that feeds it is the other half. A shared symbol READS as agreement, so nobody re-checks it. Test: does the shared thing include the INPUT — [learnings-detail.md]

## When a negative reproduction seems to CLEAR a finding, prove the mechanism was live before believing it — anything that fails open answers "fine" when you break its inputs, so a clean result can mean the fixture never reached the code. Run a case that MUST trip it in the same fixture first. Tell: your repro exits 0 and you are about to tell a reviewer they were wrong — [learnings-detail.md]

## Editing a norm's STATEMENT in the same commit as the code it would bless is the amend-to-match-own-code tell, even when you are alert to it elsewhere in the same file — a settled-feeling decision arrives as an implementation detail, so the guard never fires. Record the departure beneath the clause; leave the clause alone. Tell: the edit admits just what you wrote — [learnings-detail.md]

## RULING (deprecation-requires-an-inert-retention-window), 2026-08-11 (v3.3.4) — when you retire a harness-invoked subcommand, unregister it now and keep it INERT until no supported install still registers it, because plugin pins are per-project and lazy. Settles the question `[[harness-only-removal-is-not-a-major]]` left open; the tier permission is unchanged — [learnings-detail.md]

## RULING (inert-retention-cannot-be-extended-across-norms), 2026-08-26 — when the behaviour an inert-retention window would preserve IS a violation of another ratified norm, withdraw it outright, because the window's bargain is that retention is CHEAP. Qualifies `[[deprecation-requires-an-inert-retention-window]]`; requires the withdrawal to fail CLOSED — [learnings-detail.md]

## When a re-measurement CORRECTS a prior test, run it against the QUESTION, not the prior test's conclusion — otherwise each new instrument re-grades the last one's output and a wrong verdict survives every correction. Ask what the check is a fact ABOUT, then pick the unit that carries it. Tell: your re-measurement reuses the previous framing — [learnings-detail.md]

## Copying a fix into a sibling procedure is a NEW change needing its own analysis — two documents share a paragraph, not their invariants, so one edit can repair one and break the other. Ask which invariant made the original wrong and whether it holds next door. Tell: you fixed one file and grep found the same lines elsewhere — [learnings-detail.md]

## A rule that LOWERS a severity outranks every rule that raises one unless you say so — state the floor with the ceiling, in one sentence, or the suppression quietly becomes the file's highest authority. The exits that LIFT a ceiling are not the severities it must never touch. Tell: your new rule caps a severity and all you wrote next was how to escape the cap — [learnings-detail.md]

## Scrub the WHOLE diff before dispatching a review, tests and their comments included, and scrub a grep-able ban BY GREP — a rule you just wrote is one you are still violating elsewhere in the same commit, re-reading missed it twice on one branch, and a reviewer's list of instances is a sample rather than a census. Tell: you scrubbed by re-reading — [learnings-detail.md]

## "Fail closed" means the CHANNEL's blocking value, not merely a non-zero one — mapping every refusal to a generic error code fails OPEN wherever the contract reads a SPECIFIC code as "block". Check the contract for the surface the refusal can REACH, not the one you were writing. Tell: you wrote "a refused gate is a blocked gate" and never opened the exit-code table — [learnings-detail.md]

## A recommendation an advisory prints ships to every consumer's repo, so test its EFFECT, not just that it fires — make the change on a fixture, observe the promised outcome, and keep the un-made case as the control. Tell: every test you wrote asserts on the advisory object and none on what following it does — [learnings-detail.md]

## A `try/except` around a producer that RETURNS its degraded states guards nothing — and the comment above it will read as if it does, so the intent survives while the mechanism does not. Read what the callee actually does on its bad paths before writing the guard, and answer the returned states where the read already is. Tell: your `except` names exception types the producer's docstring never mentions raising — [learnings-detail.md]

## A fallback must be checked against the SIZE of the interval it replaces, not its name — a mode name carries goal count, not span, so a demotion can hand back an interval narrower than the one just refused for being too wide. Have the refusal name the mode rather than let the reader pick. Tell: a refusal tells the caller to re-dispatch and does not say as what — [learnings-detail.md]

## A correct decision defended by an unread mechanism is still a defect — when you write the *reason* for a choice ("X forces this", "that span is a superset"), open X first, because review checks the code against the claim and rarely the claim itself, so a false reason outlives the round. Tell: your justification names a gate, flag or span you have not opened — [learnings-detail.md]

## A refusal predicate is not a severity predicate — a gate folding several conditions into one "cannot be trusted" answer must not also decide how hard to fail, because its mildest condition is ordinary and escalating on it punishes the common case. Split the reasons at the call site. Tell: you reached for the function whose NAME matched your sentence — [learnings-detail.md]

## A clean sweep usually indicts your QUERY, not the tree — grep returns sites phrased in your words, so survivors are the ones that paraphrase, assert the opposite in prose, or say nothing (silence satisfies an assert-absent guard). Name the state the change makes true or false, search two vocabularies sharing no word, pin positively. Tell: every hit used your words — [learnings-detail.md]

## Bound a class by the PROPERTY that justifies it, never by the container it sits in — a path prefix, a line range, or a fixture built from the feature's own subject each look complete while bounding the wrong set, so the claim reads as verified at the fixture's scope rather than the requirement's BREADTH. Tell: your boundary is a location, your rationale is a verb — [learnings-detail.md]

## An UNEXPECTED PASS is a signal, not a result — when a change you believed would break tests doesn't, find out which branch they are on before banking it, because green usually means confirmation and here it means your fixture never reached the subject. Tell: you predicted red, got green, and explained it to yourself in one sentence without opening anything — [learnings-detail.md]

## One home stops DIVERGENCE, not staleness — when you add a caller to shared copy, re-read the shared sentence AS THAT SURFACE'S READER, because a clause true of every existing caller can be flatly false at the new one and composition hands it over unexamined. Tell: you satisfied "route it through the one home" and never read the composed output — [learnings-detail.md]

## When you add a rule to the site that motivated it, ENUMERATE the siblings that perform the same ACT before calling it done — a criterion can be false at a surface your chunk never opened, and listing a reader is not asking whether the change reaches it. Tell: your fix names one call site and your acceptance criterion names a class ("cannot X without Y") — [learnings-detail.md]

## Re-invoking the thing you just edited verifies NOTHING in the same session — a skill body, hook payload or digest the harness loads once is served from ITS cache, so the render you are grading is the pre-edit one and a missing change looks like a working one. Verify against disk, or in a fresh session. Tell: your acceptance criterion is "run X and see the new thing" and X ran earlier this session — [learnings-detail.md]

## Funding a budget by deleting what ANOTHER surface already says is only valid for readers who RECEIVE that surface — the always-injected digest covers a session's main agent and not a subagent, so a `building.md` dedup against it is a dedup for you and a deletion for the delegate, and the delegate is the reader that instruction exists for. Enumerate who opens the file before crediting the cut. Tell: your justification is "the digest states this" and the file's reader is not the one the digest reaches — [learnings-detail.md]

## Adding the right rule is not the same act as DELETING the wrong one — a superseded sentence keeps governing every reader who stops at the file it lives in, and it survives most easily in the paragraph you just edited, because the diff shows you touching it and your attention is on what you added. When a rule exists because an existing one was wrong, name the wrong one and go remove it. Tell: your change adds a surface, and the sentence that caused the defect is still standing one line above your addition — [learnings-detail.md]

## A mutation sweep where EVERY mutant dies on the first pass is a claim about the HARNESS, not the subject — prove it can report a survivor: assert the test RAN (return code, never a substring of output) and include one mutant you expect to live. A bad pytest flag killed every subprocess on a usage error, read as a catch — 18 of 18 from a runner that never started — [learnings-detail.md]

## When editing `session-digest.md`, count CHARACTERS as well as tokens — it ships as SessionStart `additionalContext`, which Claude Code spills to a file above a hard 10,000, pinned in `test_plugin_methodology_digest.py` while the token ceilings sit in `test_v5_methodology.py`. A ceiling is policy; 10,000 is not. Tell: budget arithmetic green, never counted a character — [learnings-detail.md]

## A general policy sentence is NOT evidence that a specific procedure in the same document inherits what you are adding — read that procedure end to end and ask what it RE-STATES, because restating a step it would inherit means replacing, not supplementing. Tell: you answered "does B inherit from A?" from a sentence about the class — [learnings-detail.md]

## When one rule is carried by two surfaces on purpose, pin it in the module that reads BOTH — a bar reworded in one carrier is two bars for one decision, and no single-file guard sees that. Bound the assertion to the smallest region that must carry the phrase. Tell: a mutation stays green on a neighbouring sentence — [learnings-detail.md]

## Prose about what a new guard BUYS must state its PREDICATE, not its purpose — read the guard's deliberate-exclusion tests first, the ones pinning what it does NOT cover: they are the cheapest falsifier. Motivation and extension are one word apart in English and a set apart in code. Tell: the claim turns on a term defined in BOTH code and prose, with different extensions — [learnings-detail.md]

## Naming a prior fix as "the same family" IS the class finding, not a citation decorating an instance-level one — a recurrence says the FIRST fix was scoped too narrowly, so the remedy is the construction preventing both members, bounded by every site the shared predicate reaches. Tell: your note cites a prior finding as precedent and your fix touches fewer sites than it did — [learnings-detail.md]

## A documented "clears when X" / "exempt when X" arm is NOT evidence X is implemented — grep the module for the mechanism before you build the fix around it. `probe_stalled_transition` documents *Clears: … or a stopgap is recorded*; `stopgap` appears in `norm_probes.py` only in comments and two operator-facing strings, and the real levers are `updated_at` and the `Status: in-transition` literal. The cost is not a wasted hour: an operator who does the documented thing watches the symptom persist, and the natural next move is whatever lever DOES work — here, touching the tracking item, which is the silent departure the norm forbids wearing compliance's clothes. A contract that teaches unworkable compliance actively routes people to the forbidden lever. Tell: prose promises a state change your fix should produce, and the symptom does not move — [learnings-detail.md]

## When a fix is driven by a report's SUMMARY LIST, go back to the underlying scan before calling it complete — a summary that DEDUPES undercounts the sites needing the change, and the ones it hides are the ones nobody re-checks. The stalled-transition advisory prints one row per `(artifact, tracking-id)`; `architecture.md` held two distinct `## Direction` entries both tracking LNG-5W8R, so four printed rows meant five entries needing a stopgap. Fixing the four would have left a live norm governing new work with no exception recorded, and the advisory would have gone quiet anyway — the miss is invisible precisely because the report is satisfied. Tell: your remedy's count equals the report's row count, and you never opened the scan that produced it — [learnings-detail.md]
