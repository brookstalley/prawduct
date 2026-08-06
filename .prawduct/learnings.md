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

This is why entries carry their instances inline rather than in `learnings-detail.md` (read on
demand, when debugging a known area — not at the moment a rule has to fire). A general statement
is what makes a rule storable *and* what makes it inert; the instances are what you pattern-match
your own case against. Rules are collapsed by merging statements and unioning instances, never by
dropping them.

---

## RULING (regen-views-is-advice) — when two norms reach one command, its OUTPUT decides the posture: a writer whose only product is a DERIVED VIEW fails soft one view at a time, because no gate reads a view to reach a verdict. Soft is not blanket — input it cannot interpret at all still fails closed. Skip-and-report a bad view, never write it half-right
<!-- anchor: regen-views-is-advice — linked from architecture.md and data-model.md Rulings: -->

## `grep -rn <new symbol> tests/` before calling a behaviour change done — a guard with no test is one a regression deletes silently. Three rounds running found that, the last two in code written to FIX the previous instance: applying a rule to the finding in front of you is not applying it to the code you write while applying it

## An exception APPENDED to standing advice still leads with the advice — so before appending, ask whether the exception can cover the WHOLE set, and if it can, it must be able to REPLACE the lead sentence rather than follow it. #536's own fix shipped #536: the superseded clause was appended after "run verify-resolutions", so when every blocker was superseded the operator's first instruction was still the route that cannot work. Tell: the exception's predicate is a count over the same set the advice addresses. Fix shape — one function owns the whole message and decides which route *leads*, so no call site can reintroduce a lead of its own

## When you TRANSCRIBE a rule between two records, its identifiers are the part that silently degrades — re-verify every field, symbol and path against the code, because a paraphrase reads exactly like a faithful copy. Copying the retire rule from build plan to change-log turned `title` into `summary`: plausible, adjacent, and wrong for the store the query runs against, so the sweep would have returned zero for every review and retired a firing control. Fifth instance of two-copies-of-one-idea on this branch and the FIRST with the plan correct and the durable copy wrong — the direction flips at transcription, so carry the *reason* alongside the token ("`title`, because a partial's `name` becomes the fact's `title`"), not the token alone

## Enumerate the sites answering a question by GREP, never by memory — and the grep is itself a site: it is a PREFIX of the real set wherever the code BUILDS the string rather than spelling it, or emits it somewhere the query cannot see. Widen it until it is falsifiable, then have someone else run it

## A fix ships TWO artifacts that can independently be false — the change, and the evidence that it works. This branch put every defect in the second: a test that could not see the bug it pinned, then a comment asserting the rule its own assertion disproves. When you fix something, sweep the NEIGHBOURING PROSE in the same pass, or a reviewer finds it one comment at a time

## A mutation test is only evidence if the MUTANT IS THE DEFECT — hand-reverting to "something wrong" tests nothing. Restore the code that actually shipped the bug, gate conditions included: drop a guard the real defect sat behind and the test exercises a path the bug never reached, passing against the very code it was written to catch. And mutate each independently falsifiable CONJUNCT, never the guard as a unit: a compound condition is N guards wearing one name, and `A and B` reverted whole goes red on A's test while B stays unpinned. `anchor_is_ahead`'s second conjunct could be deleted with the entire suite green, because every existing fixture agreed on both sides of it — the absent case was the one the conjunct existed for

## A `[DECISION]` block is a CLAIM ABOUT THE CODE and carries a test's verification duty — but nothing checks it, so re-derive it from the implementation before writing the next record that cites it. Records written FROM a decision rather than from the code all agree with each other and all disagree with the tree: "binary identity, not version equality" went into a decision block, a deliverable, two docstrings and a change-log draft while the code read `$CLAUDE_PLUGIN_ROOT` — five mutually-consistent records, one implementation, no overlap. The tell is copying a claim forward from the previous record instead of opening the mechanism; the mechanism's own docstring said it preferred the env var, and it had been read earlier in the same session. Corollary: tests written from the same mental model inherit its blind spot — the first matrix here varied only the env var, so it could not have discriminated the two implementations it was written to distinguish

## When you cite a precedent, COPY ITS TEST FILE FIRST — a module that says "shape mirrors X" and does not mirror `test_X.py` has borrowed the design and left the coverage behind, and the gap is invisible because the code looks right. Twice in one chunk: a new hook subcommand modelled on `learnings-obligation` shipped ~50 untested lines (both exit-code mappings, the confirmation block, `--json`, unknown-arg, the dispatch arm) because that precedent's `TestCommand` was never carried across; then the failure policy added to CLOSE that finding shipped untested too, because the same precedent's monkeypatched-writer test was also left behind. The precedent's tests enumerate the branches its design creates — that is most of what makes it a precedent worth citing. Open `test_<precedent>.py` and port its cases before writing your own

## When a predicate's job is to classify REAL artifacts, at least one test must read the real artifact — a fixture you wrote encodes your belief about the input, so it can only ever confirm that belief, and a suite made of them is green precisely where the belief is wrong. Widening a norm-detection guard, I wrote TWO over-fire fixtures aimed at exactly the failure that shipped, and never opened `templates/project-preferences.md`: it ships illustrative rows whose cells are non-empty placeholders, which `init_product` copies verbatim, so the guard fired on every freshly-onboarded repo while both fixtures passed. Pin the artifact and the predicate against EACH OTHER (read through `core.TEMPLATES_DIR`), or they drift apart the moment either moves. Mutation testing does not cover this — it probes the line you wrote, and says nothing about inputs you never supplied

## A dry run that validates IDENTICALLY to the real run is not a safety device — it is where drift hides, because it reports clean while the artifact it checks rots. Delete the mode and always write. Tell: the check and the real command share a validation path and differ only in whether they persist

## Before implementing against a mechanism, grep the BACKLOG for that mechanism's name — and when claiming something is "provably equivalent," name the proposition the proof actually establishes, because equivalence under one model is not equivalence under the one that governs behaviour

## Under a single-parent promotion model, "did this ship?" is a question about TREE CONTENT and never about ancestry — `git tag --contains` cannot return a positive answer for any scope, so it fails as a confident false negative, and the content test needs a control that fails plus a functional-surface target

## The fix for a review finding needs the same adversarial pass as the original work — dispatch a delta review of the fix commit, because "I am correcting a known defect" feels like lower-risk work than writing new code and the verification reflex relaxes exactly where the last round proved it shouldn't. **A fix commit is a code commit**: everything the chunk protocol demands of new code — a test, red-verified, in the same pass — applies unchanged to code written to close a finding, and applies MORE, because that code is written under time pressure and never gets a chunk review of its own. A reader guard added to close a utf-8 round-trip finding shipped with no test at all and the suite stayed green, because on a UTF-8 host the guard is a no-op; the delta review caught it. Third under-tested guard on one branch — an unpinned conjunct, a fixture that could not reach the guard it named, then this — so the failure is not the rule being unknown but the *reflex* not firing on correction work

## A background agent's liveness is answered by ITS OWN completion signal, never by reading the files it is midway through writing — a death verdict from a directory listing is how a re-dispatch clobbers a live review. And the grep that "confirms" it may be matching the failure mode's own DOCUMENTATION, which feels exactly like verification

## A safety argument and its counterexample can sit two paragraphs apart in YOUR OWN writing and never meet, because each answers a different question — before clearing a reader/caller/path as unaffected, re-read what you just wrote about the mechanism's lifetime and ask it against the clearance, not against the wording it was written for

## A test asserts what would BREAK, not what you just built — red-verify mechanically (break the subject, watch that specific test go red, restore), because the vacuous shapes all look correct while proving nothing

## Apparent duplication across governing docs may be the RECEIPT for a token budget already paid — check for a pinning test before cutting it, never fund a budget by moving prose between files, and raise the ceiling rather than spend redundancy twice

## Justify at the ALTITUDE OF THE DECISION, never the mechanism — a mechanism claim carries the same verification duty as the instruction it supports but escapes the check by reading as commentary. Test: must the reader reason PAST this instruction? No → mechanism is liability; yes (a norm, a recorded decision) → verify it like code. Same species as over-precise counts. Altitude, never omission

## A finding of the form "A is pinned, B is not" is discharged by PINNING B, never by changing B — changing shipped behaviour to satisfy the letter of such a finding relocates the asymmetry from the code to the test layer, where the next review finds it again and charges you another round against a P0 wall-clock budget. Generalise it: the fix commit carries the cheap check that closes the loop it opens — the test beside the moved behaviour, the parser run before a hand-authored machine-parsed record — because a check deferred to the review that follows costs a whole review run to deliver

## A governance change cannot supply its own authority — when an agent amends a binding norm mid-build, land the owner's confirmation somewhere the amendment isn't, because a change that is its own only witness is indistinguishable from laundering however sound the substance

## When you "correct" an inherited number, recount the SET and not just the count — re-measuring inside the frame you inherited reproduces the frame's error while feeling exactly like verification

## A review ending is not a filing event — dispose every non-blocking finding as FIX or ACCEPT, and treat FILE as the narrow case clearing THREE bars: it names its trigger, the work is **large** (a chunk's worth, not an hour's), and it cannot be absorbed into the current work. **Deep context on a small problem is a FIX signal, not a filing signal.**

## Widening a predicate takes TWO searches: grepping the pattern finds its DUPLICATE COPIES, never the CALLERS that branch on the predicate it backs. So grep the *shape* for copies, then the *predicate's name* for branches; a survey that ran only the first is incomplete however clean it looked. Generalizes to any shared predicate — a validator, a feature flag, a type guard

## When a scope narrowing is recorded (a chunk deferred, work cut from a release), it is a CASCADE, not an annotation — the summary describes, but the bodies INSTRUCT, and they compute against the fact you just changed: recording "v3.2.0 stops after Chunk 06" in § Status left Chunk 09 owing six backlog flips for deferred work, announcing a drop-box retirement that was no longer happening, and declaring `Depends on: Chunks 01–08`. Following it literally would have marked unbuilt work shipped. The edit is not done until every section naming that chunk has been opened

## When a release ships a PRUNED tree, a clean `git apply` is NOT evidence of a sound tree — the shipping code can depend on a symbol the WITHHELD work introduced, which a textual patch tool cannot see: v3.1.2's ship set called `sys.stderr` while `import sys` had arrived in `briefing.py` with the withheld backlog-service work, so `git apply` reported the file applied cleanly and produced a `NameError` in a shipped path (11 test failures). Run the suite against the candidate tree, and diff every shipped file's imports against its `develop` counterpart

## When determining what a PREVIOUS release actually shipped, test its CODE against that release's tree — never the change-log's prose or heading presence, which a pruned release leaves behind: v3.1.1's tree carries all ten backlog-service change-log entries whose code it deliberately withheld, so a heading-presence test called them shipped and would have mis-tagged them, silently dropping ten entries from v3.1.2's release notes. This is the runbook's own REL-7D4X rule and it is load-bearing in both directions

## When work is authored ON TOP OF work you may later need to withhold, the two become inseparable by file — pruning is by commit range, so everything merged in between ships or waits together: v3.1.2's ship and withhold sets overlapped in 11 files including `prawduct-hook` and `briefing.py`, so "ship only the session work" also withheld an unrelated refactor and five skills' prose. Sequence a release-gated subsystem BEHIND independently-shippable work, not before it

## When deferring something to a live/operator check, SPLIT it into "can this be true in principle" (static — test it now) and "does the harness actually do it" (live — queue it) — bundling them defers the testable half indefinitely, and that half is where the bug usually is: CRT-2J8N deferred all of "does the SubagentStop matcher fire" as un-unit-testable because *anchoring semantics vary by version*, true of delivery but false of matchability, and the bare-name matcher could never have matched the plugin-scoped `agent_type` on any version

## When defense-in-depth is offered as the reason a risk needn't be verified, check the defense is REACHABLE from the failure it is meant to absorb — a guard downstream of the thing that fails never runs, so it buys nothing: `cmd_subagent_stop`'s `agent_type.endswith(...)` check was cited as making matcher uncertainty tolerable, but it sits behind the matcher, and a matcher that never fires never reaches it

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

## A red version/release-hygiene test on a feature branch is often a branch-STALENESS symptom, not a doc defect — check distance from the integration branch before patching the changelog

## When `check-cumulative-critic` reports `uncovered` on a branch whose code you know was reviewed, suspect a stale base before running a fresh review — the gate anchors to `origin/<base>` by design, so unpushed integration commits drag already-shipped work into the required span

## When a docstring makes an absolute robustness claim (never raises / always returns / idempotent), make it literally true and test the claimed-safe path — an absolute claim beside a call that *can* violate it is a coherence gap reviewers reliably flag

## When developing requirements to replace a working system, sweep every consumer's actual usage before finalizing — reported pain is a hypothesis, and the loudest complaint is often not the deepest failure

## When a fail-closed validator guards a model-written field, tolerate the natural encoding variant — reserve the hard fail for genuine ambiguity, because incidental strictness at a model-output seam is a latent fail-close

## When the success path threads advisory/audit data through a result envelope, add it to EVERY error-return path too — in an envelope-heavy codebase the error return is built by a *different* constructor (here `core.from_transport_error` vs `core.ok(data, warnings)`) that has no slot for the field and silently drops it; the damage is permanent, not cosmetic, when the datum is one-shot (a self-heal audit line that won't re-run on resume, so it can never be re-emitted). Second instance of this class in backlog-service import (BKL-3K9N rate-limit path, BKL-9V2W TransportError path — both funnel through one outer `except`). Grep the error/exception returns whenever you enrich a success envelope.

## When designing any flow step that records status or bookkeeping, make it ride IN the PR that does the work — a step that can only run post-merge on the integration branch is structurally broken for protected-branch consumers

## When a governance checkpoint verifies a required side-effect happened, put it OUTSIDE the control flow that produces the side-effect — a check inside the fallible flow can't catch that flow's own skip

## Correcting a false claim is authoring a new claim — verify the replacement and the artifacts it cites, because the fixing mood generates claims faster than the checking reflex fires. The trigger is WRITING the replacement, not reading the original — a correction drafted from the impression left by auditing the source is unchecked. Tell: this cell got a conclusion where every other got a query

## Never write a present-tense state claim ("Phase 1 is complete", "the branch holds X") into a durable document — write the dated measurement plus the command that re-derives it, because the claim is false the moment the next step runs and a reader cannot tell when it was true. This is the WRITE side of [[When a durable plan asserts VCS state]] and it fires hardest *inside a correction*, where explanatory mode about someone else's stale claim coexists with authoring your own: v3.2.3's release plan recorded three stale-measurement instances, and the paragraph correcting the third asserted "Phase 1 is complete now" with the commit and push not yet run — [[Correcting a false claim is authoring a new claim]] did not fire because the replacement's *facts* were verified and only its summary sentence was not

## Before writing any sentence of the shape "X now covers/catches/handles Y" or "there is no Y", run the one query that would falsify it — a coverage claim is the highest-frequency error class here and is almost always checkable in under a minute, so treat the SENTENCE as the trigger, not your confidence in it

## Verify a review artifact's cited gaps against HEAD first — its file-state claims aged the moment it was written, some were never true. A `file:line` you did not resolve yourself is a claim, not a citation: its precision reads as evidence of having been read. Anchor on symbols and headings, not digits — one that visibly breaks gets fixed; one still arithmetically valid under a rewrite never does

## When a backlog item's `refs:` names several surfaces, treat them as candidates and let the mechanism pick the surface — implement only where the condition can actually manifest (and grep for existing coverage first), because mechanically touching every listed ref adds dead or duplicative surfaces the item never needed. STH-3R8K listed SessionStart `digest.py`/`banner.py` alongside the Stop hook, but SessionStart runs in the launch dir *before* any mid-cycle worktree move, so it provably cannot observe the redirect — the Stop path was the only load-bearing surface, and a SessionStart line would have duplicated BRF-6K2D. Descope the dead surfaces explicitly in the item note (Principle 2 — a deliberate scope call, not a silent drop). Relates to Scope Discipline (#12) and [[Verify a review artifact's cited gaps against HEAD first]].

## When you add an ingest/IO surface to a platform-agnostic framework, expose the minimal data primitive — not one ecosystem's file format — or you silently lock out the toolchains the agnosticism promised

## When you add a fallback lookup INSIDE a per-item loop, amortize it AND make it a no-op on the common path — a naive fallback that fires on every miss is O(N²) at scale, and the fresh case is all-misses

## When a test injects a fixed clock, EVERY actor in the scenario must share that clock domain — one real-clock participant (a CLI front, an un-injected default) turns fixed-timestamp + TTL into a scheduled deterministic failure at stamp+TTL wall time

## When a build plan ships in a different release than it targeted, its frontmatter `scope:` must be the scope-NAME (not a version) — `regen-views` resolves plans by it and a version there silently skips Status flipping at release

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

## A new build plan with `scope: null` and low chunk numbers inherits another scope's shipped checkbox flips — set `scope:` from the start

## New change-log entries on a feature branch are statusless — `status=in-progress` is deprecated and trips the regen-views typo-guard

## A change-log `chunks=` tag must match the build plan's chunk-heading numbering *exactly* (zero-padding included) or `regen-views` flips only the matching chunks

## When a feature's logic lives in a `context:fork` skill (no Bash), `lib/` holds the DATA, not the LOGIC — logic helpers nothing imports are dead code

## At release, flip *statusless* unreleased change-log entries to `status=shipped` too — not just `status=merged`

## "I'm just codifying their guidance" is not an exemption from the research trigger — and volatility is a separate axis from knowledge-confidence

## The "canonical" mechanism for a capability can be disqualified by a plugin's composability + always-on constraints — verify the constraint before adopting the recommendation

## When fanning out a batch build to parallel worktree-isolated workflow agents, partition by disjoint file ownership (integrator owns shared files) and force-clean leftover worktrees before the integration suite

## When a fresh-eyes review's advice about a CONVENTION conflicts with a durable learning + the process doc, the documented convention wins — re-verify before acting

## A reviewer's NOTE/severity is a prior, not a verdict — re-scope any "harmless" change that touches a governance-gate input, and `grep` the value's READERS before concluding it isn't one: a field's comment block tells you what it is for and how it has failed, never who consumes it, so inheriting that framing feels like coverage and isn't (clearing `active_build_plan: null` was argued from its own long comment block — record-lint, Critic mode inference — and silently flipped the reflection gate to advisory and skipped the Critic gate entirely, caught only in review)

## A new framework-wide DEFAULT must land in the session digest — place-once preferences and the thin anchor don't reach migrated repos

## Single-repo plugin+marketplace: the marketplace entry's plugin `source` must be a RELATIVE PATH, not `{source:github,ref}` — and that path is a curated subdirectory, not the repo root

## Release-bound work merged feature→develop under gitflow: KEEP the build plan — it's a live release artifact, not spent

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

## Build-plan chunk parsers accept `### Chunk N:` AND `## Chunk N (ID) — Name` (BLD-5J8N) — but `regen-views`/`chunks=` still key on the colon Status form

## Submodule and same-name function in __init__ shadow each other

## Detection of structural characteristics should not rely on mechanistic surface markers

## Shared "answer" state and personal "nag" state belong in separate stores

## Framework ownership follows the write strategy, not just registry membership
<!-- prawduct-learning: confirmations=1; created=2026-05-19; sentinel=tests/test_prawduct_sync.py::TestAutoCommitSafety::test_user_authored_place_once_edits_treated_as_wip -->

## A leftover marker is not an in-progress signal — and a test using the canonical marker leaves the real-world branch untested

## A near-verbatim file PORT carries the source's prose — adapt the docs, not just the logic

## Verify the platform's copy/packaging boundary before duplicating a shared bundled file — a prior "duplicate into each consumer" choice may be an unverified-constraint workaround

## Dogfooding the generator on its own output masks output-relative bugs the real consumer would hit

## Relocating a source file: sweep every READER of the old path, not just the data-key references

## A review's "inert / harmless" verdict on a latent bug is conditional on the current call graph

## Excising a subsystem silently kills the incidental work it happened to host — re-home the orphaned call, and test the positive

## A "renders-but-doesn't-resolve" leak is a SURFACE, not a line — sweep the whole renderer and assert the bad form is ABSENT

## An "assert the bad form is ABSENT" sweep is only as good as the pattern that defines the bad form — enumerate the whole FORM-FAMILY, not one spelling

## An untested governance bound rots silently across a migration — sweep the guards (with tests), not just the prose

## In a leaf-first decomposition, dependency-scan a chunk's COMMAND bodies against later-chunk symbols before moving — and never move a parity-pinned mirror just because a deliverable lists it

## A format's schema legend lives in `templates/` (scaffold-only) — adding an optional field reaches already-onboarded repos only via a migrate/triage *refresh* step, not the template

## A structural bound that ENFORCES a declaration is not a DETECTOR of the declared property — reusing it at a new boundary silently drops its justification

## A rebuild scoped to a subsystem's "remaining / deferred" parts silently omits an already-shipped part that was deleted in between — re-port against the spec roster, not the open-work list

## A persisted schema's requirements are its consumers' future queries — lock-in is reversal cost, not LOC, so "small format" never exempts it from decision research

## Test-evidence freshness is `test-status` (session timestamp) ONLY — `git_sha` was retired as misleading (TST-4K2P)

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

## A fix lands at the instance a review named; the defect lives in the class — so before closing a finding, name the class and route it through one owner, because every local fix looks complete from inside itself

## A CLI on `$PATH` is a different checkout from the worktree you are editing — an interactive command's exit code is not verification evidence for a change to that command

## When a durable plan asserts VCS state ("the code lives on branch X, not develop", "resuming means landing Y", an ahead/behind count), re-derive it from git before acting on or copying it — plan prose about branches and merges is a snapshot that expires the instant the next merge lands, so run `gh pr view` / `git merge-base --is-ancestor` / compare tree hashes first; a since-merged "land this branch" step is a no-op a plain merge performs silently, and the check costs under a minute

## When you relocate importable code behind a conftest sys.path shim, standalone/non-collected scripts do NOT get the shim — grep for `__main__` scripts that self-insert the old root and fix each, because conftest only fires under pytest

## Before predicting a per-minute rate ceiling will engage, check whether serial round-trip latency already caps throughput below it — a rate ceiling is bounded by requests/min = 60 / round-trip-seconds, so it never binds on TOTAL volume no matter how large; it binds only when you issue requests concurrently/batched faster than one round-trip drains

## When a triggered job must observe a state that a LATER step creates, you have found a RACE, not a certainty — the ordering argument yields the hazard and only the wall clock yields the verdict, so read the dispatch/observation/conclusion timestamps before writing EITHER outcome into a durable document. v3.2.4's release plan asserted the tag-push `verify-release` job was "red by construction" because the GitHub Release is published one runbook step later; it went GREEN — runner spin-up plus `checkout` burned the first 11s of a 20s job while the publish landed at +11s, winning by ~9s. Same root as the rate-ceiling rule above: the mechanism was reasoned about and never given a number. And a race that usually passes is a WORSE finding than the deterministic red, because a deterministic red gets fixed and an intermittent one gets learned as noise — so the wrong prediction would have buried the more valuable result, not merely mis-stated it

## When you change a MECHANISM, cascade-search the CLAIM as well as the code — grep the tokens you edited and you find every site that runs the old procedure, but not the prose that merely DESCRIBES the old behaviour, which shares no token with it. Fixing the tag/publish order caught both runbooks and the process doc via `git tag`/`gh release create`; the Critic then found a stale "on every tag push" in `architecture.md`, a superseded command in a historical release plan, and one doc asserting flatly what another hedged — none reachable from the command strings. Search for what the system is said to DO, in the vocabulary a describing sentence would use

## A durable record inherits the confidence of its DERIVATION, not the authority of its author — before propagating a claim out of an issue comment, release plan, or prior reflection, check the mechanism it rests on, exactly as you would a claim you generated. #581's disposition read a tag-push CI run as proof that workflows resolve from the tagged commit's own tree; the promotion had pushed `main` first, so ordinary default-branch registration explained the run completely and the evidence isolated nothing. It was copied into the change-log unchecked because it was owner-authored and already written down. Both are the same failure the record itself was warning about: reasoning about a mechanism without measuring it

## When one fix must hold for N procedures, cost it against the WORST of them, not the one that surfaced the bug — the cheap option is usually cheap only for the case you were looking at. Narrowing the tag→publish window was defensible for the whole-develop runbook (a 9-second margin) and impossible for the pruned one, whose release notes need a hand-edit inside that same window; reading the second document before choosing is what eliminated the option that looked cheapest

## When a release has two documents tracking its state, one is already wrong — designate a single live tracker and demote the other to a decision record; and author each build chunk from the TREE, never from the upstream plan, because a plan derived from a plan describes intent the code may have overtaken

## When a guard test pins a safety claim, assert the PROPERTY, not one spelling of it — a test that matches a literal (an exact flag token, an exact grant string, a substring anywhere in a file) passes for every rewording of the same defect, so write the check to answer the question the property asks and verify it red against a DIFFERENT phrasing than the one that prompted it

## When the deliverable is INSTRUCTIONS, at least one guardrail must model the READER — tests that measure the artifact (size, budget, "the right words are present") all pass while the instruction has no effect, because none of them read the file in the order an agent reads it

## A spike that discards its code leaves its numbers unfalsifiable — commit the derivation as a runnable script and cite the command, never the digits, because a count transcribed into prose goes stale silently as the corpus grows; the fix is not counting more carefully but moving the count out of prose entirely

## Routing a filing to the handoff is NOT filing it — file the item the moment you decide it should exist, because a handoff note is read by a session that arrives with its own plan and treats an inherited instruction as context rather than work, and an unwritten handoff (crash, context exhaustion) loses it outright; "later" has two independent ways to never happen and costs the same as now

## A completeness claim asserts the falsifying COMMAND now returns nothing — never a count of sites fixed, which is true of any prefix of the real set. The query is itself a mechanism and can carry the defect it hunts: normalize the text before searching, because line structure is not semantic structure, and query the CONCEPT, not the phrasings you already found wrong

## A falsifying grep queries a PHRASING; only a reader queries a concept — the same stale state written in words your query does not contain is invisible, so the sites that survive a sweep are exactly the ones that paraphrase. Name the STATE being asserted, then search two or three vocabularies that share no word with each other. Tell: every hit came back in the words you typed

## Reads as evidence, is not: an absence-claim citing a path that does not RESOLVE, a missing directory returns the same empty result as the claim being true; a disposition recorded from intent, not the diff, which the next reader trusts INSTEAD of the findings; a commit crediting a backlog item by TITLE while its filed reproduction still reproduces; and a subagent's COUNT or LIST, a lead

## Green is evidence ONLY about what could have made it red — for each test name the change that would turn it red; if you cannot, it measured nothing. The fixture may never reach the subject; a constant-equality assertion survives an inverted comparison while its NAME convinces the reader it is covered. Same for a live probe: say what a FAILING run would have looked like before recording one

## A passing assertion may be satisfied by something other than the property — an unimplemented flag passes because the arg guard REJECTED it (assert success BEFORE absence); a prose SUBSTRING stays green under any longer sentence containing it (when prose changes meaning, grep tests asserting FRAGMENTS, not just failing ones); a proxy passes every test you thought to write — gate on the named event

## A fixture's world is narrower than the requirement it certifies — the COMMON instance narrows the requirement to itself, so check coverage against its stated BREADTH; the framework's OWN state stands in for the propagated contract, so assert what reaches consumer repos; one moment stands in for the procedure's transitions; the collision case is unwritten when the fan-out key is not unique; and an acceptance criterion written in the same breath as its guard inherits the guard's scope silently — "the shape appears in exactly one place in the CODEBASE", pinned by a test scanning three directories, read as verified while six sites outside the scan stayed stale

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

## Scope an exemption by the PROPERTY that justifies it, not by the container it lives in — an exemption justified by *naming* a file belongs to naming forms, not to every file under that directory, and the container is one cheap generalisation away from correct while looking complete. Tell: the boundary is a path prefix while the rationale is a verb

## "Make A agree with B" has two solutions and the cheap one hands A the defects of B — an agreement criterion is satisfied by teaching A the narrower predicate, so it cannot tell correctness from consensus and goes green with both wrong together. Pin the DIRECTION separately, on a fixture from the population that predicate is worst at. Tell: every fixture sits inside its allowlist

## Citing a named procedure is a claim that you RAN that procedure — re-read the named step before citing it, because two independent recalls fire and each feels verified by the other: you reach for the test you KNOW and attach the authority you REMEMBER. A right conclusion on a substituted warrant is the durable defect, since conclusions get re-derived by the next reader and warrants get copied. Repair by running the named test, never by softening the citation

## An edit that changes a COUNT or a SET falsifies every sentence stating the old one — and noticing one of them feels like completing a search rather than starting one, because the catch arrives with the satisfaction of thoroughness. The instance you found is the one you happened to be reading, not the first of an enumerated set. Grep the document for the old value before committing; prefer a relational statement ("the table's rows") over a literal count, which is the part that goes stale

## A guardrail whose anchors come from your MENTAL MODEL of a file is a second copy of the claim, not a check on it — derive them by reading the file, line by line, as you write the test, because otherwise the test encodes the same error the claim does and goes green over it. Tell: you can write the anchors without opening the file

## A green suite is evidence about the ONE environment that ran it — a suite only ever run by its maintainer has untested dependencies on that machine rather than no dependencies, and the second environment is what finds them. Expect the first CI run to be red and treat that as the run working; the recurring shapes are in [learnings-detail.md]

## When you fix a defect of a named class, re-run that class's own check against your fix — the fix is the likeliest place to reintroduce the class, because attention sits on the content of the claim and not on its mechanics. A citation repaired by renaming it, then line-wrapped inside its backticks, is still unresolvable to the grep that would find it

## When a trim is justified by the surrounding prose's OWN instruction, that is exactly when to run the suite before trusting it — the dangerous cut is not the one you cannot justify but the one the file appears to endorse. A record-lint explanation read as redundant under its own "raise it, don't restate it" rule, and was the only witness to a two-shape contract. Second instance, same shape: a budget comment's "the next addition trims or relocates" licensed cutting a closing sentence that RESTATED a rule 30 lines above — but its job was PLACEMENT, sitting exactly where the reader shortcuts the rule, and a test pinned its phrase for that reason. Ask whether the sentence sits where the rule gets skipped; if it does, it is not a copy

## Making a capability conditional on the RUNTIME retroactively conditions every existing test whose fixture touches it — the affected set is not the set you wrote, since shared fixtures carry it into tests that never mention it. Simulate the degraded runtime over the whole file before commit; a reviewer surfaces one and it reads like the one — [learnings-detail.md]

## When you add a validator because a value became DANGEROUS, sweep every existing use of that value, not the uses you are writing — the vulnerable line is the one already in the file and therefore not in your diff, and reviewing your own change shows you only the new call sites. A review id became a filename component, `_path_component_safe` was added and applied to both new paths, and the pre-existing `_archive_leftovers` kept deriving a directory name from the same id unchecked; it degrades to DELETE on failure, so the traversal was silent. Tell: the helper is new, and `grep` for the value's other readers was never run
