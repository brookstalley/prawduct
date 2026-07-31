# Learnings

Active rules from this project's development. Surfaced via the `/learnings [topic]` skill — topic headers shown in the session briefing for ambient context. Entries use "When X, do Y because Z" format. Each entry's full narrative lives in `learnings-detail.md` under the same heading — keep narrative THERE, not here.

---

## Before implementing against a mechanism, grep the BACKLOG for that mechanism's name — and when claiming something is "provably equivalent," name the proposition the proof actually establishes, because equivalence under one model is not equivalence under the one that governs behaviour

## Under a single-parent promotion model, "did this ship?" is a question about TREE CONTENT and never about ancestry — `git tag --contains` cannot return a positive answer for any scope, so it fails as a confident false negative, and the content test needs a control that fails plus a functional-surface target

## The fix for a review finding needs the same adversarial pass as the original work — dispatch a delta review of the fix commit, because "I am correcting a known defect" feels like lower-risk work than writing new code and the verification reflex relaxes exactly where the last round proved it shouldn't

## A governance change cannot supply its own authority — when an agent amends a binding norm mid-build, land the owner's confirmation somewhere the amendment isn't, because a change that is its own only witness is indistinguishable from laundering however sound the substance

## Pinning the CONSTANT a threshold uses is not testing the threshold — exercise the firing path and prove it by mutation, because a constant-equality assertion survives an inverted comparison while its name convinces the next reader the path is covered

## When you "correct" an inherited number, recount the SET and not just the count — re-measuring inside the frame you inherited reproduces the frame's error while feeling exactly like verification

## A gate that lives inside a procedure must be tested across the procedure's own state transitions, not at one instant — every fixture encoding a single moment will miss the step where the procedure changes the data the gate reads

## Verify a disposition against the diff before recording it — "fixed" is a claim about the tree, not about intent, and a dispositions record is what the next reader trusts INSTEAD of re-reading the findings

## Before recording a probe's result as a settled fact, state what a FAILING run would have looked like — if you cannot describe the observation that would have falsified it, the probe measured nothing and the "fact" is an artifact of the measurement Same discipline as a discriminating regression test, applied to live measurement

## A review ending is not a filing event — dispose every non-blocking finding as FIX or ACCEPT, and treat FILE as the narrow case clearing THREE bars: it names its trigger, the work is **large** (a chunk's worth, not an hour's), and it cannot be absorbed into the current work. **Deep context on a small problem is a FIX signal, not a filing signal.**

## A completeness claim states the COMMAND that would falsify it and asserts that command now returns nothing — never a count of sites fixed, which is true of any prefix of the real set. Corollaries: run it **whitespace-normalized**, and query the **CONCEPT, not the phrasings you already found wrong** — a regex built from known-bad spellings is another enumeration wearing a query's clothes

## Widening a predicate takes TWO searches: grepping the pattern finds its DUPLICATE COPIES, never the CALLERS that branch on the predicate it backs. So grep the *shape* for copies, then the *predicate's name* for branches; a survey that ran only the first is incomplete however clean it looked. Generalizes to any shared predicate — a validator, a feature flag, a type guard

## An absence-claim must cite a path that RESOLVES, or its verifying command returns empty for the wrong reason — the missing directory produces the same evidence as the claim being true: seven sites asserted "no GraphQL in `lib/backlog/`" after the tree became `plugin/lib/backlog/`, so the grep that "confirmed" it was confirming only its own bad path

## When a scope narrowing is recorded (a chunk deferred, work cut from a release), it is a CASCADE, not an annotation — the summary describes, but the bodies INSTRUCT, and they compute against the fact you just changed: recording "v3.2.0 stops after Chunk 06" in § Status left Chunk 09 owing six backlog flips for deferred work, announcing a drop-box retirement that was no longer happening, and declaring `Depends on: Chunks 01–08`. Following it literally would have marked unbuilt work shipped. The edit is not done until every section naming that chunk has been opened

## When a release ships a PRUNED tree, a clean `git apply` is NOT evidence of a sound tree — the shipping code can depend on a symbol the WITHHELD work introduced, which a textual patch tool cannot see: v3.1.2's ship set called `sys.stderr` while `import sys` had arrived in `briefing.py` with the withheld backlog-service work, so `git apply` reported the file applied cleanly and produced a `NameError` in a shipped path (11 test failures). Run the suite against the candidate tree, and diff every shipped file's imports against its `develop` counterpart

## When determining what a PREVIOUS release actually shipped, test its CODE against that release's tree — never the change-log's prose or heading presence, which a pruned release leaves behind: v3.1.1's tree carries all ten backlog-service change-log entries whose code it deliberately withheld, so a heading-presence test called them shipped and would have mis-tagged them, silently dropping ten entries from v3.1.2's release notes. This is the runbook's own REL-7D4X rule and it is load-bearing in both directions

## When work is authored ON TOP OF work you may later need to withhold, the two become inseparable by file — pruning is by commit range, so everything merged in between ships or waits together: v3.1.2's ship and withhold sets overlapped in 11 files including `prawduct-hook` and `briefing.py`, so "ship only the session work" also withheld an unrelated refactor and five skills' prose. Sequence a release-gated subsystem BEHIND independently-shippable work, not before it

## When deferring something to a live/operator check, SPLIT it into "can this be true in principle" (static — test it now) and "does the harness actually do it" (live — queue it) — bundling them defers the testable half indefinitely, and that half is where the bug usually is: CRT-2J8N deferred all of "does the SubagentStop matcher fire" as un-unit-testable because *anchoring semantics vary by version*, true of delivery but false of matchability, and the bare-name matcher could never have matched the plugin-scoped `agent_type` on any version

## When defense-in-depth is offered as the reason a risk needn't be verified, check the defense is REACHABLE from the failure it is meant to absorb — a guard downstream of the thing that fails never runs, so it buys nothing: `cmd_subagent_stop`'s `agent_type.endswith(...)` check was cited as making matcher uncertainty tolerable, but it sits behind the matcher, and a matcher that never fires never reaches it

## A deferral queue whose enforcing gate is disabled is a WRITE-ONLY queue — check the gate is ON at the moment you defer work into it, because the deferral itself feels like diligence: `operator-verification.md` named the CRT-2J8N matcher as the thing to investigate 17 days before it was found, and sat `pending` the whole time behind `operator_verification_required: false`, with 6 of 8 entries in the same state

## When a test asserts a VALUE and its comment claims that value feeds a downstream contract, assert the CONTRACT instead — the comment does the reasoning the test never performs, so it reads as coverage while providing none: `test_name_is_critic_reviewer` checked the agent's frontmatter name and commented that the name "is the SubagentStop matcher target", true of dispatch and false of the matcher, and never opened `hooks.json`

## When a decision defers a SET of findings rather than fixing them, enumerate the set against the filings before calling it done — deferral converts every item into a filing obligation and nothing reconciles the two lists automatically: a "file all ten" call produced six items covering eight, and the two dropped ones were found only because an independent reviewer counted

## When a commit claims to close a backlog item, verify the claim against the item's FILED CASE before crediting it — a fix aimed at the item's title routinely lands the ADJACENT sub-case, passing every guard while the filed reproduction still reproduces, so merging closes a still-broken item as shipped

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

## Correcting a false claim is authoring a new claim — verify the replacement and the artifacts it cites, because the fixing mood generates claims faster than the checking reflex fires

## Before writing any sentence of the shape "X now covers/catches/handles Y" or "there is no Y", run the one query that would falsify it — a coverage claim is the highest-frequency error class here and is almost always checkable in under a minute, so treat the SENTENCE as the trigger, not your confidence in it

## When building from a review/audit artifact, verify each cited gap and fix-instruction against HEAD before planning — the artifact's file-state claims aged the moment it was written, and some were never true. A `file:line` you did not personally resolve is a claim, not a citation: its precision reads as evidence of having been read, which is exactly why it survives into your own durable artifacts unchecked. Resolve every inherited ref (does the path exist? does that line say this?) before it becomes an argument you build on — an inherited premise gets the same falsification query as one you wrote from memory. See learnings-detail.md for the v3.2.0 Chunk 05c instance.

## When a backlog item's `refs:` names several surfaces, treat them as candidates and let the mechanism pick the surface — implement only where the condition can actually manifest (and grep for existing coverage first), because mechanically touching every listed ref adds dead or duplicative surfaces the item never needed. STH-3R8K listed SessionStart `digest.py`/`banner.py` alongside the Stop hook, but SessionStart runs in the launch dir *before* any mid-cycle worktree move, so it provably cannot observe the redirect — the Stop path was the only load-bearing surface, and a SessionStart line would have duplicated BRF-6K2D. Descope the dead surfaces explicitly in the item note (Principle 2 — a deliberate scope call, not a silent drop). Relates to Scope Discipline (#12) and [[When building from a review/audit artifact, verify each cited gap and fix-instruction against HEAD before planning]].

## When you add an ingest/IO surface to a platform-agnostic framework, expose the minimal data primitive — not one ecosystem's file format — or you silently lock out the toolchains the agnosticism promised

## When you add a fallback lookup INSIDE a per-item loop, amortize it AND make it a no-op on the common path — a naive fallback that fires on every miss is O(N²) at scale, and the fresh case is all-misses

## When a test injects a fixed clock, EVERY actor in the scenario must share that clock domain — one real-clock participant (a CLI front, an un-injected default) turns fixed-timestamp + TTL into a scheduled deterministic failure at stamp+TTL wall time

## When a build plan ships in a different release than it targeted, its frontmatter `scope:` must be the scope-NAME (not a version) — `regen-views` resolves plans by it and a version there silently skips Status flipping at release

## When serially merging several stale feature branches into develop for one batched release, expect additive bookkeeping conflicts every time — and watch for a duplicate `active_build_plan:` key the auto-merge creates

## When a session switches branches after SessionStart, pass the Critic mode explicitly — `infer-critic-mode` trusts the stale session-start branch marker

## When prose picks which model a reviewer/subagent runs on, express it as an ordered fallback chain resolved at dispatch — never a pinned alias

## When you disable a mechanism at its wiring point but keep its implementation, reconcile the retained code's self-descriptions in the same change — or its prose reads as false

## When verifying a framework-repo `lib/`/`bin/` change by running the hook, invoke the repo-local `python3 plugin/bin/prawduct-hook` — the bare `prawduct-hook` on PATH is the installed plugin cache, not your working tree

## A review finding is about a CLAIM, not a file — resolve it by grepping the claim's wording, and never truncate the recommendation you are acting on

## Verifying an inventory against the code cannot catch a wrong CATEGORY — the check confirms the frame it was built from

## A mechanism that collapses a distinction forces every downstream rule to hold for the WEAKEST member of the collapsed set

## When a finding is "harmless by coincidence," check what makes it harmless before deferring it

## When verifying an assumption, build the instrument WIDER than the proposition — the confirm/deny answer is rarely where the value is

## A test written against a not-yet-implemented flag can pass because the arg guard REJECTED it — assert success before asserting absence

## After a clean cumulative (0 blocking/0 warning), NOTEs are advisory — don't chase cosmetic ones; fixing them reopens the coverage gate on judgeable governance files and forces a no-value review pass

## A new build plan with `scope: null` and low chunk numbers inherits another scope's shipped checkbox flips — set `scope:` from the start

## New change-log entries on a feature branch are statusless — `status=in-progress` is deprecated and trips the regen-views typo-guard

## A change-log `chunks=` tag must match the build plan's chunk-heading numbering *exactly* (zero-padding included) or `regen-views` flips only the matching chunks

## When a feature's logic lives in a `context:fork` skill (no Bash), `lib/` holds the DATA, not the LOGIC — logic helpers nothing imports are dead code

## At release, flip *statusless* unreleased change-log entries to `status=shipped` too — not just `status=merged`

## "I'm just codifying their guidance" is not an exemption from the research trigger — and volatility is a separate axis from knowledge-confidence

## The "canonical" mechanism for a capability can be disqualified by a plugin's composability + always-on constraints — verify the constraint before adopting the recommendation

## When a fan-out render keys on a field that isn't unique, test the collision case — and a self-authored adversarial pass inherits the author's blind spots

## When fanning out a batch build to parallel worktree-isolated workflow agents, partition by disjoint file ownership (integrator owns shared files) and force-clean leftover worktrees before the integration suite

## When a fresh-eyes review's advice about a CONVENTION conflicts with a durable learning + the process doc, the documented convention wins — re-verify before acting

## A reviewer's NOTE/severity is a prior, not a verdict — re-scope any "harmless" change that touches a governance-gate input

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

## A subagent's reported COUNT or LIST is a lead, not ground truth — verify before a blanket edit

## Verify the platform's copy/packaging boundary before duplicating a shared bundled file — a prior "duplicate into each consumer" choice may be an unverified-constraint workaround

## A plugin skill with unparseable YAML frontmatter loads with ALL metadata silently dropped — validate it in CI
<!-- prawduct-learning: confirmations=1; created=2026-06-02; sentinel=tests/test_plugin_manifest.py::TestAllPluginSkillFrontmatter -->

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

## When generalizing or detecting "across all cases", the COMMON / AVAILABLE instance silently narrows the requirement to itself — check coverage against the requirement's stated breadth

## Before "fixing" an apparent forgotten-manual-update, check whether the artifact is a GENERATED / DERIVED view — the real fix is upstream

## A test asserting the framework repo's OWN state instead of the propagated contract gives false coverage — assert the contract that reaches consumer repos

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

## A test that asserts a SUBSTRING of prose stops being a contract the moment someone writes a longer sentence containing it — when prose changes meaning, grep the tests that assert fragments of it, not just the ones that fail

## A rationale you reached for to defend a decision you'd already made is the one to verify BEFORE writing it into a durable spec — the reach itself is the tell

## Before filing a finding against a mechanism, read that mechanism's own documented degradations — a design that enumerates its deliberate weaknesses has usually already considered yours

## A channel that is produced and never consumed is a DEFECT, not an inefficiency — name the consumer in the same change that adds the producer, or don't produce

## Anything in a durable artifact that one command could check is a CLAIM — including an identifier, a count, or a facet value, not just a rationale

## A status surface that reports the ABSENCE of expected output must say whether absence is the normal in-flight state — a bare zero invites the reader to invent a death story and take recovery action against healthy work

## When auditing guidance material, have a fresh agent USE it before you recommend changing it — analytic review predicts defects that do not survive contact with practice, and the trial is what tells you which findings are real

## A falsifying query is itself a mechanism and can carry the defect it hunts — when proving a claim is ABSENT from a tree, normalize the text before searching, because line structure is not semantic structure

## In an append-heavy file, a union merge is safe only when neither side RELOCATED an entry — a moved item reads as "absent here, present there," which is exactly the shape a union is built to merge

## When a guarantee names a specific event, gate on THAT event — a signal that usually co-occurs with it passes every test you think to write, because you wrote them believing the proxy

## "Advice fails soft" is not "advice fails silent" — a degraded advisory path must still name its consequence, or it manufactures the false success it was meant to prevent

## A fix lands at the instance a review named; the defect lives in the class — so before closing a finding, name the class and route it through one owner, because every local fix looks complete from inside itself

## A CLI on `$PATH` is a different checkout from the worktree you are editing — an interactive command's exit code is not verification evidence for a change to that command

## When a durable plan asserts VCS state ("the code lives on branch X, not develop", "resuming means landing Y", an ahead/behind count), re-derive it from git before acting on or copying it — plan prose about branches and merges is a snapshot that expires the instant the next merge lands, so run `gh pr view` / `git merge-base --is-ancestor` / compare tree hashes first; a since-merged "land this branch" step is a no-op a plain merge performs silently, and the check costs under a minute

## When you relocate importable code behind a conftest sys.path shim, standalone/non-collected scripts do NOT get the shim — grep for `__main__` scripts that self-insert the old root and fix each, because conftest only fires under pytest

## Before predicting a per-minute rate ceiling will engage, check whether serial round-trip latency already caps throughput below it — a rate ceiling is bounded by requests/min = 60 / round-trip-seconds, so it never binds on TOTAL volume no matter how large; it binds only when you issue requests concurrently/batched faster than one round-trip drains

## When a release has two documents tracking its state, one is already wrong — designate a single live tracker and demote the other to a decision record; and author each build chunk from the TREE, never from the upstream plan, because a plan derived from a plan describes intent the code may have overtaken

## When a guard test pins a safety claim, assert the PROPERTY, not one spelling of it — a test that matches a literal (an exact flag token, an exact grant string, a substring anywhere in a file) passes for every rewording of the same defect, so write the check to answer the question the property asks and verify it red against a DIFFERENT phrasing than the one that prompted it

## When the deliverable is INSTRUCTIONS, at least one guardrail must model the READER — tests that measure the artifact (size, budget, "the right words are present") all pass while the instruction has no effect, because none of them read the file in the order an agent reads it

## A spike that discards its code leaves its numbers unfalsifiable — commit the derivation as a runnable script and cite the command, never the digits, because a count transcribed into prose goes stale silently as the corpus grows; the fix is not counting more carefully but moving the count out of prose entirely
