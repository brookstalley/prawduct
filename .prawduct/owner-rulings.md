# Owner Rulings

<!-- The owner's own words, each time they decided something about this product, committed with
     the work each ruling governs (methodology/building.md "When the Owner Rules").

     Why it exists: a ruling given in conversation is gone by the next session, and the harness's
     auto-memory is per account, so the next person, or the same person on another account,
     never sees it. This file is the one place a later session looks for what the owner said.

     What goes here: a decision, a correction, or a constraint or preference about the product,
     in the owner's words, with the date. Write it before replying to them, and cite it in the
     reply, so they can see it was taken down as they meant it. Your own inferences do not go
     here; they stay marked as inferred where you made them, until the owner confirms one.

     What does not: the decision's working-out. Each entry says where the decision landed (the
     plan's Goals, a norm in a `## Direction` section or `project-preferences.md`, a design
     artifact, a backlog item) and the governing text lives there. A ruling on the edge of a
     norm still goes in that norm's Rulings field as well; this entry keeps the words that
     settled it.

     A later ruling that reverses an earlier one is a new entry that says which one it replaces.
     Leave the earlier entry in place: what the owner once said, and when it changed, is the
     record.

     When work spans repos, keep the rulings in the repo that owns the decision, and have the
     other repo cite that file rather than copy it.

     Newest first. Plain prose; nothing parses this file. -->

**2026-11-24.** "Yes, and get to prawduct-live as well" — answering whether to open a PR for
`feature/test-determinism` (#1243). The PR into `develop` is opened through `/prawduct:pr` and merged,
and `../prawduct-live` is advanced to the new `origin/develop` (the dogfood track, as on 2026-11-22).

**2026-11-24.** "Any first-party import (Recommended)" — answering the boundary review's question on
#1243 (rev-20261124T234435Z-e6b3faf9, R-11). The ruling's "an autouse fixture … that imports
everything" reads as: an autouse fixture in a `conftest.py` that imports any first-party module
blocks at the merge boundary. That is the same cost as a root conftest's single module-level import,
and "everything" cannot be checked statically for a fixture. The rule is restricted to `conftest.py`,
because an autouse fixture in a test module reaches only that module. Landed in
`plugin/lib/determinism_lint.py` and `plugin/docs/test-determinism.md`.

**2026-11-24.** "Janitor only (Recommended)" — answering where the scan of a product's existing
test-determinism sites lives. `/prawduct:janitor`'s Test Fitness theme runs
`prawduct-hook determinism-scan`, and doctor and onboard do not, per `docs/doctor-vs-janitor.md`'s
placement rule (the product's own test craft is the janitor's). This replaces the "onboard/doctor"
part of the earlier 2026-11-24 #1243 entry below, item 3. Landed in
`.prawduct/artifacts/build-plan-test-determinism.md` (Decisions made mid-build).

**2026-11-24.** "Remember that prawduct does not require testament, but I think these are all
best practices anyway right?" — a constraint on #1243 and its follow-up #1244. No part of the test
determinism work may depend on testament. The patterns are defined tool-agnostically
(`plugin/docs/test-determinism.md`), the detector reads only source and git
(`plugin/lib/determinism_lint.py`), and #1244's measured check runs only when the project's runner
reports per-test causes, doing nothing otherwise. Agreed in reply: each pattern is general
practice. The clock, randomness, in-tree-state and write patterns cost correctness on any runner.
The import-scope patterns cost collection time and isolation on any runner, and reuse on any
incremental runner (pytest-testmon, Bazel/Pants, Jest's changed-files mode, testament).

**2026-11-24.** "Agreed on all counts" (said in the testament session and relayed here by it), then
"Agreed to all recommendations" here — the design of #1243 (test determinism and dependency-scope
patterns P1–P8):
1. The measured check (test-evidence keeps the runner's per-test determinism causes so the Critic
   can flag a cause site a diff introduced) is a follow-up, gated on #1096's ledger.
2. A newly introduced P1 (a root conftest's module-level import of the app or its core modules) or
   P2 (an autouse fixture or package `__init__` that imports everything) is BLOCKING at the
   merge-boundary review.
3. That verdict comes from a mechanical base-vs-head detector, not the reviewer's reading, and is
   waivable with `prawduct:allow prawduct/test-scope -- reason`; the detector also feeds
   onboard/doctor and the janitor sweep.
4. P1–P8 and their remedies live in one doc, `plugin/docs/test-determinism.md`, which
   `building.md` points to in one sentence and the discipline table registers as a row.
5. The issue's "measured improvement on two products" acceptance item moves to the follow-up as
   its success measure, since a merge cannot verify it.
These land in #1243's build plan and the follow-up backlog item.

**2026-11-22.** "1. yes keep running 2. yes agred 3. yes please do fix" — answering three asks
from the post-v3.9.0 orientation:
1. The #1130 paired experiment runs to its stop condition (four weeks, about 2026-12-10), even
   though the 60-boundary-pair sample is already met (104). Before the final blind check,
   #1170 (consolidation duplicates inflate Critic-only counts) is fixed and native-review token
   cost is measured (`compare.py --transcripts`). No fourth interim check. Lands on #1130.
2. The next build is #1141 + #1198 (shared design `documentation/issues/1141-1198-design.md`),
   then #1207.
3. The delegation brief's verification ceiling names the whole-tree guard class, as the
   scratch-subdirectory item does for scratch. Lands in `plugin/methodology/delegation.md`.

**2026-11-22.** "yes update prawduct live" — `../prawduct-live` is advanced to `origin/develop` after
the v3.9.0 release (the dogfood track, `documentation/release-process.md` § Dogfooding the develop
track), so this machine's sessions run the released plugin plus the 3.9.1-dev reopen.

**2026-11-22.** "1. agree confirm 2. yes agreed" — answering the two open asks on the #1141/#1198
design:
1. The plan-order rule binds only chunks proposed because the diff touched their paths. `--chunks`,
   a scoped `(Chunk N)` commit subject and span credit still certify out of order, so data-model D1
   and its #1199 departure stand unamended. Lands in `documentation/issues/1141-1198-design.md`.
2. The `chunk`-mode refusal (a proposal still naming two chunks) exits 8, a new code. Lands in
   `documentation/issues/1141-1198-design.md`.

**2026-11-22.** "1. yes 3.9.0 2. agreed 3. agred 4. agreed" — answering four asks together (asks 5
and 6, on the #1141/#1198 design, were not answered and stay open):
1. The release is v3.9.0, a minor, replacing the v3.8.2 named in the ruling below: it ships
   `release-fragments-only` and `retire-chunk-status-shims`, which break what consumers run. Lands in
   `.prawduct/artifacts/release-plan-v3.9.0.md` (Version).
2. No rework item for the alignment pass yet, despite the asked-first fall in the #981 re-run (14.5% →
   3.2%): hand-read corrections also fell, and the counts wait on #1211.
3. #1207 Q2: budget-sweep ACCEPTs (`auto_accept`) travel to other clones like any other ACCEPT. Lands
   in `documentation/issues/1207-design.md`.
4. #1207: dispositions on already-merged branches are not swept; the backfill covers in-flight
   branches through `reconcile`. Lands in `documentation/issues/1207-design.md`.

**2026-11-22.** "yes to all" — answering six asks together:
1. Cut v3.8.2 now: write the release plan classifying the 55 release-pending scopes and the
   headline. Lands in `.prawduct/artifacts/release-plan-v3.8.2.md` and `.prawduct/release-headline.md`.
2. #981 is run now rather than renewed or lapsed. Lands in
   `.prawduct/artifacts/requirements-alignment-discovery.md` § Yield re-run 2026-11.
3. #1198 Q1: shipping one plan in two PRs is a supported shape. `planning.md` says so, and keeps the
   advice to split a plan known in advance to ship in waves.
4. #1198 Q2–Q3: the plan-order rule (option (b): no chunk is certified while an earlier chunk is open),
   and #1141 and #1198 stay two backlog items with one shared design document.
5. #1207: disposition facts (accept, file, fixed) travel between clones like resolutions, and
   dispositions recorded before the change are sent too (Q1 backfill: send them).
6. #855 is reworked as an advisory, not a blocking Stop gate, to fit the 2026-09-19 tax ruling.

**2026-11-18.** "yes let's run now, 12-10 is too long to wait. yes to triage"
In reply to two asks: (1) whether to blind-verify the Critic-vs-native comparison now, at 68 paired
reviews (54 boundary pairs), or wait for #1130's stop at about 2026-12-10. It settles: verify now.
This reverses the agent's recommendation to wait, and does not move the stop condition. (2) whether
to triage the one untriaged downstream bug report now. Yes. The result lands as a comment on #1130,
and the triage on the backlog.

**2026-11-14.** "Yes to both of your recommendations."
In reply to two asks after `feature/ci-testament` merged (PR #1172). It settles: (1) the norm row
in `project-preferences.md` that the testament key is held by a CI job that runs no test and
reaches no fork's code, which the agent originated on 2026-11-11, is confirmed by the owner;
(2) CI does not pass `--fresh --no-cache` for now, and it is revisited if a cached pass ever hides
a real failure. Landed in that row's provenance and in `build-plan-ci-testament.md` Chunk 03.

**2026-11-14.** "Step one, but we also do need to move CI onto Testament so that we will take some work to update I suppose"
In reply to the advice after the interim comparison: ship `feature/native-review-inner` first, then
revive `feature/ci-testament` instead of parking it. Landed as PR #1171 and this branch's sync onto
develop.

**2026-11-14.** "Yes, let's do it"
In reply to running the blind verification of the Critic-vs-native comparison at 12 paired reviews.
It overrides the 2026-11-13 ruling's wait for about twenty. The interim result is posted on #1130 as
a baseline, not a decision.

**2026-11-13.** "1. yes file and build, and let's wait on 2"
In reply to two asks after the early Critic-vs-native comparison. It settles: file three follow-ups
to #1130 (#1164, a severity breakdown in `compare.py`; #1166, pairing a sample of `chunk` and
`verify-resolutions` reviews; #1165, the native review's re-raise rate) and build them. #1166
replaces #1130's scope-out of `chunk` and `verify-resolutions` reviews for the pairing; the
2026-11-10 ruling ("BOTH each time") still governs the boundary review. The blind verification of
the comparison waits for more paired reviews (about twenty). Landed in
`.prawduct/artifacts/build-plan-native-review-inner.md` Goals.

**2026-11-12.** "and then 1161"
Sent as #1130's PR was being opened: once that merge and the `../prawduct-live` advance are done,
build #1161 (harden the native text parse before the first monthly comparison). Landed on
`fix/native-review-parse`.

**2026-11-12.** "1. yes PR and mege and push to prawduct-live"
In reply to two asks at the end of #1130's build: open the PR and merge `feature/native-review-paired`
to develop, then advance `../prawduct-live` to it — which turns the paired native review on in every
repo that runs the development build. Landed as the merge and the live checkout's advance; #1130
stays open until its stop condition.

**2026-11-12.** "yes to high, and yes to changes, and yes build"
In reply to three asks on #1130's plan. It settles: every paired native review runs at `high`;
each native run is recorded as a per-clone ledger event rather than an evidence-store fact, and its
text is kept in `.prawduct/.native-reviews/` rather than beside the partials (both departures from
#1130's wording); and the build proceeds. Landed in
`.prawduct/artifacts/build-plan-native-review-paired.md` Goals.

**2026-11-11.** "let's get ci using testament", with a client key for the pool supplied as
"(github secret)" and the coordinator's address as "(variable I think, not secret)". The previous
session's handoff quotes the owner on the same question: "We should be. I can get a key if
needed". Landed in `.prawduct/artifacts/build-plan-ci-testament.md` (Goals), which marks as
inferred everything these words do not settle: that an unreachable pool falls back to the job
rather than failing it, that a refused key fails the job, and that a third setting (the console's
address) is needed beside the two supplied.

**2026-11-11.** "yes please do PR and merge and advance, anc close 669"
In reply to three numbered decisions at the hand-over of #1129. It settles two: the branch
`feature/pr-reviewer-fold` is opened as a PR to `develop`, merged, #1129 closed, and
`../prawduct-live` advanced to the result; and #669 is closed as overtaken, the backlog walk it
set out to repair and the `affecting` query that served it both being gone. It says nothing on the
third, the list of PR-review judgment checks that were dropped rather than moved to the Critic;
that list stays marked as inferred in `build-plan-pr-reviewer-fold.md`. Landed in that plan, on
#669 and on #1143 (the item-level `affected` field has no reader left).

**2026-11-11.** "yes to recs"
In reply to one decision put to the owner after #1129's boundary review, with two options and a
recommendation. The review found that removing `learnings-files --for-diff` (ruled 2026-11-10,
entry below) conflicts with the owner's ruling D-7 on #928, which names that flag as how a host
with no on-read rule loading gets its area learnings; the removal had been put to the owner as
having "no shipped reader" without #928 in view. The recommended option, now ruled: the flag stays
removed, and #928 and its requirements document record that D-7's named mechanism is gone and that
the adapter's design stage supplies the explicit read. The option not taken was restoring the flag
in #1129's branch. The same message recommended starting framework sessions with `claude
--plugin-dir <this checkout>/plugin`; that is advice about how sessions are started and lands
nowhere in the repo. Landed beneath D-7 in `documentation/issues/928-requirements.md`, on #928, and
in `build-plan-pr-reviewer-fold.md`.

**2026-11-11.** "yes to both of your recommendations"
In reply to two numbered questions put to the owner while #1129 was building, each with a
recommendation. It settles both as recommended. First: a small credential-shape check on a PR's
added lines stays at the PR gate, reusing the denylist the plugin already keeps for its own
output, as a bounded exception to `architecture.md` § Direction ("prawduct never re-implements
what a product's own tooling already does"); no debug-code check is built, that being a linter's
rule. Second: the retired commands (`pr-review-dispatch`, `pr-review-payload`, `ledger-append
--event review.pr`, `learnings-files --for-diff`, and the cache queries `affecting` and
`created-since`) are removed outright in this release rather than kept callable and inert until a
major, with the dispatcher naming each retired command and what replaced it; put to the owner with
its cost, that a session whose plugin loaded before the update cannot open a PR until it restarts.
Landed in `build-plan-pr-reviewer-fold.md` (Goals and `governed_by:`), in the Rulings of the
architecture norm, and in `api-contract.md` § Deprecation & Compatibility.

**2026-11-11.** "my one concern with 1129 is making sure it honors repo standards like PR templates -- or, if the boundary agent doesn't do that, SOMETHING does it"
Said while #1129 (the PR reviewer folded into the boundary Critic) was being planned. It sets a
constraint on that work: when `/prawduct:pr` opens a PR with no reviewer agent, the repo's own
standards for a PR, its PR template named first, are still honoured by some step of the flow.
Checked the same day: nothing in the plugin read a PR template before this, neither the reviewer's
protocol nor the step that drafts the description, so this is a requirement the fold adds, not one
it has to preserve. It brings the PR description into #1129, which the issue had scoped out.
Landed in `build-plan-pr-reviewer-fold.md` (Goals, and the chunk that adds the PR gate's checks).

**2026-11-11.** "1. Yes PR and merge to develop, update prawduct-live. I meant 1136 first, which I think you got. yes I think that session rule is good. Agree with your take on review-stats vs stats. ok as built for #4"
In reply to four numbered asks at the end of the #1136 build. It settles: #1136 is opened as a PR,
merged to `develop`, and `../prawduct-live` is advanced to the result; "1138 first" meant #1136
first (the entry below records the doubt, now closed); a session model not recognisably Haiku,
Sonnet or Opus, and a dispatcher that does not say what it runs on, get Opus-class reviewers; the
count of reviews above the ceiling lives in `review-stats` and `stats` is unchanged; a single-pass
boundary review is capped by the same hand-off, and dispatch-time instructions reach a handed-off
reviewer through the manifest. Landed in `build-plan-reviewer-model-cap.md`, whose four inferences
it confirms.

**2026-11-11.** "Hand off to Opus (Recommended)"
Chosen from three options put to the owner on how chunk and verify reviews, which run inside the
forked `/prawduct:critic` on the session's model, are capped on a session above Opus-class. The
option as put: the fork only routes, and dispatches one Opus-class reviewer instead of reviewing
inline; sessions at or below Opus-class are unchanged. The two not chosen were pinning the skill to
Opus on every session, and leaving the fork uncapped for now. Landed in
`build-plan-reviewer-model-cap.md` (#1136).

**2026-11-11.** "Sonnet for both (Recommended)"
Chosen from three options on what the forked `/prawduct:backlog` and `/prawduct:advisory` run on,
given that a skill can name only a fixed model. Both name Sonnet-class on every session. Put to
the owner with its cost: on an Opus-class session they drop a tier, backlog triage included.
Landed in `build-plan-reviewer-model-cap.md` (#1136).

**2026-11-11.** "yes let's do 1138 first, so we don't have a few runs in a different cnfig"
In reply to whether #1136 should land before `../prawduct-live` is advanced, where the session
had recommended advancing it first. The words name 1138, a PR that had already merged. Unconfirmed
which was meant. The session read it as "#1136 first" and built #1136 on that reading without
advancing the installed plugin. The installed checkout was then advanced to `fe0fee97` (`develop`
without #1136) at 08:35 on 2026-11-11 by someone other than that session, which fits the other
reading: yes, advance it first. Put back to the owner on 2026-11-11, who confirmed the first
reading (the entry above); who advanced the checkout that morning is not known.

**2026-11-10.** "yes please open and  merge PR's.  and also  yes to your recommendations"
In reply to six numbered decisions put to the owner at the end of the first build wave. It
settles: the one-line close keeps its existing labels; this file keeps the name
`.prawduct/owner-rulings.md`; the mid-build decisions list is dropped from the review and no
reader is built for it; `learnings-files --for-diff` and the backlog cache queries `affecting`
and `created-since` are removed with #1129; the next items run in the order #1136, #1129, #1130.
Landed in the build plans for `audit-guidance` and `critic-trim`, and on #1129.

**2026-11-10.** "Yes cap at opus. In fact we need to be very careful to not accidentally spam fable subagents anywhere, given the cost. Sometimes it makes sense, but most fable orchestrators should use opus and sonnet for most delegation"
Landed in `plugin/methodology/delegation.md` ("Always name the model at dispatch") for delegates,
and as #1136 for reviewers and forked skills, where it amends the norm "reviewers run on the
session model".

**2026-11-10.** "Yes clear-reason to stop blocking"
Landed in the Stop hook (`clear-reason` records a `stop-observed:` fact) and in
`nonfunctional-requirements.md` § Direction. Closes the decision #1044 asked for.

**2026-11-10.** "Yes every consumer that takes ../prawduct-live as its prawduct version"
On where the paired native-review run happens: every governed repo running the development build
of the plugin. Landed on #1130.

**2026-11-10.** "actually, maybe not A/B -- maybe BOTH each time for the develop repo at ../prawduct-live, and record all results and then compare"
Replaces the same day's "how about we A/B test it in our next develop version? Can we do 50/50 and
compare results (quality, performance) between current critic and native?". Landed on #1130 as a
paired run.

**2026-11-10.** "Cut to one line. And as long as we're touching this, another major pet peeve: when the agent wraps up and says "your turn: answer the avove questions" and the questions are like 500 lines above. This may need its own item and research but we need to get much sharper about what's needed from the user and surfacing it where the user will actually see it"
Landed in `plugin/methodology/session-hygiene.md` and the session digest's closing section (#1131),
with the research half on #1132.

**2026-11-10.** "yes fold PR reviewer in"
Reverses the 2026-07 decision to keep both reviewers. Landed on #1129.

**2026-11-10.** "Yes delete those"
On deleting the Critic's model-relayed checks and notes-as-findings. Landed in #1128.

**2026-11-10.** "Yes to delegation draft"
The draft is quoted in #1133 and opens `plugin/methodology/delegation.md`.

**2026-11-10.** "Yes to your recommendation"
On delegation telemetry: a monthly transcript script first, a hook-recorded fact only if two runs
show the numbers are used. Landed on #1134.

**2026-11-10.** "Yes adopt"
On the four requirements changes (see it first, a ruling is written before the reply, mark what
the agent originated, a third fix stops for a definition). Landed in #1135.

**2026-11-11.** "yes build the three part fix and triage the reports"
On whether a Critic review should catch a read that costs more than it returns (a lookup that
scans for want of an index, a fetch of whole records where a few values are used). The three
parts — an Access Paths section in the data-model template, one Goal 7 line in the Critic
protocol rated WARNING at most, and a corrected Performance row in the concerns registry — are
recorded in `.prawduct/changes/read-cost-review.md`. The two upstream reports were staged the
same day, on #1137 and #1141.

**2026-11-11.** "Yes to all of your recommendations"
On four recommendations made after an ad hoc test of the read-cost check: run more blind reviewer
replicates before merging, to see whether the new check draws attention from other defects; leave
a per-item query rated by the rule as written rather than warned on regardless of the store; open
the pull request for `feature/read-cost-review` once the replicates are in; and fix #1137 on its
own branch. The replicate result is recorded in `.prawduct/changes/read-cost-review.md`.

**2026-11-11.** "Yeah try the shorten approach. If that fails, perhaps a preamble somewhere that code may have multiple defects, don't assume the first round is the only one."
On the read-cost check after the blind test found the new protocol missing a blocking defect the
old one caught: shorten the Critic line and re-test on the same fixture first; if that does not
recover the catch, try a preamble telling the reviewer a file can hold more than one defect. The
outcome of each is recorded in `.prawduct/changes/read-cost-review.md`.

**2026-11-11.** "I like the pseudo defect check, but I wonder if we should actually set it up in a separate repo that pulls from either the develop branch or a dedicated test branch, with that repo having a realistic app, but with the seeded defects."
**2026-11-11.** "Yes agreed on all counts, including expense tracking domain"
On how review-protocol changes get tested for what they do to reviewer behaviour: a seeded-defect
check in a separate private repo holding a realistic expense-tracking app, run as a paired
comparison of two refs, with the answer key kept out of anything a reviewer or a protocol author
reads; a backlog item at requirements stage first, and requirements before any build. The same
reply approved one more batch of six runs on the existing fixture and a pull request for the
#1137 fix. The shape is carried by the backlog item filed the same day.

**2026-11-11.** "Yes to both opens, the database efficiency catches are more important than the missed finding"
On the read-cost check after a blind test showed it catching every planted read-cost mistake
while a defect the old protocol usually caught went unraised: the check ships, and the trade is
accepted. Pull requests are opened for both branches, `feature/read-cost-review` and the #1137
fix. Recorded in `.prawduct/changes/read-cost-review.md`.

**2026-11-11.** "yes merge then we'll clear and do requirements"
On pull requests #1146 (the #1137 fix) and #1148 (the read-cost check): both merge to `develop`.
The requirements for the seeded-defect check (#1147) are the next session's work.

**2026-11-11.** "Yes please for 937, 890, 961, 900, 1000, 682, and 1098 using subagents, opus or sonnet, each with appropriate effort level and following our delegation protocol"
On next priorities for consumer QOL and performance, the owner chose seven backlog items, built by
Opus- or Sonnet-class delegates under the delegation protocol, and set aside the seeded-defect test
repo until 3tears-evals is ready. The work is three plans: `build-plan-gate-clarity.md` (#937,
#1000, #1098, #682), `build-plan-review-round-cost.md` (#961, #900) and
`build-plan-bounded-cumulative.md` (#890).

**2026-11-11.** "1. yes, follow your recommendation 2. Yes 3. yes 4. Yes please."
Four answers to four questions asked together:
1. #890 Decision 2 is re-ruled. The bounded cumulative is built without the vanished-token sweep. The
   test-evidence relays grade the full merge-base → HEAD span, as record-lint already does under
   Decision 3, and Chunk 04 measures the real blocking loss against the design's falsifier. This
   replaces the 2026-09-22 "rated sweep" answer after Chunk 01 measured the sweep catching none of the
   nine stale-prose losses through a token the finding names, and the same-base loss at about 6%. The
   amended decision lands in `build-plan-bounded-cumulative.md` and the design's Decisions.
2. #1098: the Stop gate's relax-only third arm stands. That is the [DECISION] in
   `build-plan-gate-clarity.md`, with the four narrowings recorded there.
3. #682: `changes_unjudged` narrows to symbol-less Python files and deleted files. Non-Python paths
   move to `changes_out_of_remit`, and `changes_unchecked` stays as a deprecated alias until a major
   release. This is a bounded exception to api-contract's additive-first norm, on the #303 precedent:
   every reader ships with the plugin.
4. Pull requests are opened for `feature/gate-clarity` and `feature/review-round-cost`.

**2026-11-11.** "So the new dev version is improvef in most ways, but this is really hard for a human to parse: [a turn that listed its one ask, then closed `YOUR TURN · DO NOT CLEAR — … The one ask above is for you.`] ... if there ares asks for the user, it's confusing to say "don't clear, waiting on you, look above". Let's try to tune things so any actions required of the user are the last thing shown, and prominent."
The close changes order: the one status line comes first, and any asks follow it as the turn's last
block, under a fixed prominent header, so nothing points "above". The Stop hook's reading of the
close learns that trailing block. Lands in `methodology/session-hygiene.md`, the session digest and
`lib/standing_block.py` on `feature/asks-last`.

**2026-11-11.** "1. Yes 2. Yes" — answering (1) whether a turn interrupted by a Stop block repeats its
`**Needs you:**` block, so the asks stay last, and (2) whether to keep the `close-pointer` record of a
close whose reason points "above"/"below". Both were built on `feature/asks-last` as the coordinator's
inference from the ruling above; this confirms them. Lands in `STOP_BLOCK_ANSWER`,
`methodology/session-hygiene.md` and `lib/standing_block.py`.

**2026-11-11.** "3. Confirmed" — answering whether #890's falsifier may be restated against the same-base
old-only blocking rate (about 7 in 114 on the 2026-11-11 dated reading, re-derived by
`tools/measure-repeat-cumulative-yield.py`) instead of the design's all-rows ~1%. Lands in
`build-plan-bounded-cumulative.md` § Goals (Falsifier) and the design's "Falsifies the lever".

**2026-11-11.** "4. Yes PR and merge both and update prawduct-live"
`feature/bounded-cumulative` and `feature/asks-last` are opened as PRs into `develop` and merged, and the
`prawduct-live` worktree (the lumens profile's plugin source) is advanced to the merged `develop`.

**2026-11-12.** "yes to all of your recommendations" — answering four asks together:
1. PR #1151 (`feature/gate-clarity`) syncs with `develop` and merges first, then #1152
   (`feature/review-round-cost`) syncs with the result and merges. `../prawduct-live` is advanced once,
   after both.
2. Where #1152's protocol text no longer fits the reviewer payload ceilings that #890 set, its wording
   is trimmed rather than the ceilings raised; a trim that would lose meaning comes back to the owner.
3. PR #1118 (Codex Phase 1 spike) stays out of this batch.
4. The merged local branch `worktree-agent-a76c0614686964c8c` is removed (done by `git-tidy --apply`).

**2026-11-12.** "1. Yes" — answering whether, when `feature/review-round-cost` (#1152) syncs with `develop`, the
reviewer payload ceilings may rise to the merged readings rather than #1152's partial-validation and refusal-remedy
wording being cut to fit `develop`'s ceilings. They rise: each merged reading is `develop`'s plus the raises #1152
already declared and had reviewed (within one token of rounding), and the merge adds no new text. This narrows the
same day's ruling that a trim, not a raise, pays for fitting #1152 under the ceilings — that ask assumed the ceilings
were fixed limits, when each is one over its last reading. Lands in `tests/test_reviewer_payload_budget.py` and
`tests/test_v5_methodology.py`.

**2026-11-18.** "yes to to all of your recommendations" — answering three triage asks together:
1. #1187 (git-tidy reap with submodules), #1189 (testament probe wrapper scripts) and #1192 (gitignore
   probe evidence changed without a PROBE_VERSION bump) are fixed together on one branch off `develop`;
   #1188 (strict decoding in the shared git runner) follows on its own branch.
2. #1190: the SAFE TO CLEAR / DO NOT CLEAR label keys on what a `/clear` would actually lose (output
   that lives only in the conversation), not on whether anything is in flight. This is conditional on
   first establishing whether `/clear` terminates background subagents in Claude Code. Lands in
   `methodology/session-hygiene.md` and the digest's closing-the-turn rule.
3. The twelve stale August `ready` items come back to the owner as a keep/drop list. #270 (opt-in
   output style) is dropped; #686 (retire three principles) and #641 (stale assertions after a
   mechanism is deleted) are decided separately, as design calls.

**2026-11-18.** "background agents do survive clear, but it can be confusing of the handoff notes don't
carry what they were working on and why ("Task 23 complete!" is not super useful)." This narrows the
same day's #1190 ruling. A clear stops no background agent, and its completion still arrives, but into
a session that has lost its context. So what makes an in-flight delegate `SAFE TO CLEAR` is forward
notes that carry what it was working on and why, beside where its result lands and what integration it
owes. Lands in `methodology/session-hygiene.md` (the clear verdict's delegate paragraph).

**2026-11-18.** "yes to all of your recommendations" — answering four asks together:
1. The #1187 departure from #1041 R2 is confirmed: git-tidy passes `--force` only to remove a worktree
   that holds submodules, and only after the submodule proof (each submodule clean, and nothing any of
   its refs reaches missing from its remote-tracking branches). Lands in
   `documentation/issues/1041-requirements.md` R2.
2. `fix/triage-batch-2026-11-18` goes to `develop` as a PR and is merged.
3. #323 (handoff net misses an appended file) and #598 (a new review does not retire the prior findings
   report) are dropped.
4. #686 (retire three principles) is scheduled after #1188. #641 (stale assertions after a mechanism is
   deleted) is closed, pointing at the `Retires:` check (`retired-claim-survives`).

**2026-11-18.** "Yes to your recs and merge and push" — answering two asks together:
1. The #1199 departure from the #1082 ruling is confirmed. A clean edge review's span also credits
   the first-parent commits on the merged-in side of a non-base merge in its interval, when the
   subject carries the plan's scope and the chunk. A base merge still carries nothing. Lands in
   `.prawduct/artifacts/data-model.md` D1 (the departure line) and `plan_status._Spans`.
2. PR #1206 (`integration/backlog-roi-2026-11-18` → `develop`, the backlog ROI batch) is merged.

**2026-11-19.** "Yes merge" — PR #1209 (`integration/backlog-roi-wave2-2026-11-18` → `develop`, backlog ROI wave 2) is merged.

**2026-11-23.** "Yes backlog, and yes pr and merge" — answering two asks:
1. "verify-resolutions facts record the id of the review they verify" is filed as a backlog item, separate from `fix/stop-final-nudge`.
2. PR `fix/stop-final-nudge` → `develop` is created and merged once its gates pass, and `../prawduct-live` is advanced to the new `origin/develop`.

**2026-11-23.** "Yes it's fine to push" — the testament-cache-areas review notes (rev-20261123T164037Z-5f10b40c, rev-20261123T175253Z-0e03ed11) go to the public remote through `evidence sync`, even though they quote small internals of the private testament repo (a module and function name, one CLI line).

**2026-11-23.** "Yes please do. Also see why we got stop hook noise there" — PR `chore/testament-cache-areas` → `develop` (#1215, #1216) is created and merged once its gates pass. The Stop hook's output at that turn's close is investigated.

**2026-11-23.** "Yes agreed and update 1218 with these learnings" — on whether tests need a real wall clock:
1. `chore/testament-cache-areas` keeps the real-clock dates and `uncacheable` marks for tests that compare commits with a real-clock session stamp, as a stopgap. It makes those tests correct, though not cacheable.
2. #1218's clock item becomes "one test clock shared by git and production code": production time reads go through one seam, which tests set to the same instant as `GIT_*_DATE`. That change removes the stopgap's marks. Lands on #1218.

**2026-11-23.** "Yes pr and merge and push to prawduct-live" — PR `fix/dispositions-travel` → `develop` (#1207) is created and merged once its gates pass, and `../prawduct-live` is then advanced to the new `origin/develop` (the dogfood track, `documentation/release-process.md` § Dogfooding the develop track).

**2026-11-23.** "Yes to both git and areas, it will help understand where time is going. Subagents are fine for implementing" — answering whether to act on testament's two pieces of run advice:
1. The test suite's git subprocesses are made cacheable: an autouse fixture isolates git config and fixes git dates for the children tests spawn (testament advice `cache`, first site `gitstate.git_common_dir`).
2. The suite declares areas in `.testament.toml`, so runs report and time by area.
Both are filed as backlog items and built by delegates on their own branch off `develop`, separate from `fix/dispositions-travel`.

**2026-11-23.** "Yes to all of your recommendations" — answering four asks together:
1. The `chunk-plan-order` boundary `cumulative` is bought past the exhausted round budget with `--force`, as a
   one-off round. Six `chunk` reviews (Chunks 01 to 06) had spent the budget before Chunk 07 was reviewed. The
   refusal's census goes into the PR body.
2. R-9(a), left open in `archive/build-plan-review-loop-termination.md` ("chunk-mode reviews spend budget, so a
   6+-chunk plan exhausts on cadence alone"), is answered. The budget stops counting the first `chunk` review of
   each chunk and the first boundary review (`final`/`cumulative`) of a scope. It keeps 6 as the cap on every full
   round after those. The fix goes on its own branch off `develop`. Lands in `critic_consolidate._round_budget_verdict`,
   `plugin/docs/project-state-keys.md` (`review_round_budget`) and `plugin/skills/critic/review-cycle.md`.
   **2026-11-23, transcription corrected:** the ask the owner approved said "not counting the first review of
   each chunk or the first branch-wide review", with no mode. The entry above narrowed it to `chunk` reviews,
   and `fix/round-budget-cadence`'s boundary review (R-2 of rev-20261123T135555Z-05b709ab) found that a mid-plan
   `final` was then charged. The implementation follows the approved words: a chunk's first full review in any
   mode, and the first whole-plan review that names no new chunk.
   **2026-11-23, later:** the boundary half changed after that review's round 4
   (rev-20261123T142904Z-0bd6c78e). "The first branch-wide review" is the scope's first `cumulative`, the first
   review in the boundary stage, whatever it names. The no-new-chunk test gave the slot to a chunk's second
   `final` and denied it to a `cumulative-final` chunk's boundary review.
3. `develop`'s two unpushed commits (a04758d4, 792d8c06, the delegate-ceiling whole-tree guards) ship as a PR after
   `fix/chunk-plan-order`'s.
   **2026-11-23, later:** "That's fine one PR works." `fix/chunk-plan-order` was cut after those two commits
   landed on `develop`, so they are in its history and ship in its PR, which the body names. There is no separate
   PR. Raised by R-5 of rev-20261123T132423Z-278552aa.
4. The two inferred design calls in `build-plan-chunk-plan-order.md` Goals are confirmed as written: D8's exclusion
   rule as revised in Chunk 07 (only the code's own naming of a done chunk is questioned), and D3's refusal
   recorded as one `guard-refusal` fact through `evidence.append_guard_refusal` (the #596 one-sink ruling).

**2026-11-23.** "Merge when ready" — PR #1212 (`fix/chunk-plan-order` → `develop`) and the `fix/round-budget-cadence`
PR are each merged once their gates pass.

**2026-11-23.** "yes pr and merge, and yes to 1220 call. Yes file remaining, and yes report to testament" — answering four asks:
1. PRs `chore/testament-cache-blockers` (#1218) and `fix/verify-links-review-id` (#1220) → `develop` are created and merged once their gates pass, #1218 first; #1220 takes develop and re-runs its suite before its PR.
2. #1220's link rule is confirmed: an anchored verify-resolutions pass links to its recorded anchor alone. The accepted cost is that, in one worktree, a pass anchored to a `chunk` re-review of an already cumulative-reviewed tree does not credit that cumulative. Lands in `coverage_algebra.linked_reviews` and `critic_mode.review_chain`'s docstring.
3. #1218's remaining cacheability blockers are filed as one backlog item.
4. Testament's reading of an absolute `git log --since=<stamp>` / `HEAD@{@<epoch>}` as a clock read is reported to the testament repo.

**2026-11-23.** "Yes to all": the six decisions in `documentation/issues/1222-1223-design.md` are accepted as
recommended there:
1. A blocker-free fix tail may reach the integration branch before a review reads it, as a deferral to the
   release review only, and only together with the release check. No file-level coverage grant.
2. The NFR "Review rigor is stage-keyed … the boundary runs everything and is never skipped" is to be amended
   so the boundary may run per release batch for eligible work, as a per-repo opt-in.
3. Eligibility is derived (no risk surface touched, judgeable files at or under a bound, the plan
   short-plan-eligible), never declared. No `Review lane:` field.
4. The opt-in is one repo-level key, `boundary_review: per_pr | per_release`, defaulting to `per_pr`. This repo
   stays `per_pr`.
5. The release check is one `check-boundary-coverage` op, called by `check-releasability` and the PR skill's
   release guard. It ships advisory first, to count uncovered merges.
6. A free interval after a review whose only open findings are warnings is refused as needing no round:
   `pending_actionable` counts blocking findings only. This is its own small change.
The same message also answered the #987 ask; #987's re-run is not due until its `revisit: 2026-12-01`.

**2026-11-24.** "Yes agreed" — the "covered" definition wave 1 of #1223 shipped (`check-boundary-coverage`,
PR #1233) is accepted as written, and wave 2 (#1232) gates on it. A merge is covered at its PR when a
boundary-stage review read the branch from where it left the integration branch, and only
`verify-resolutions` passes (and free edges) composed what followed. The composition over all facts must also
read `covered`. This settles the three inferences in `build-plan-boundary-coverage-check.md` Goals:
1. The release unit is the pending fragment set. Each fragment is joined to the first-parent commit that added
   `.prawduct/changes/<scope>.md`, not to the merges since a tag.
2. A verify-resolutions pass is trusted to carry only fixes, so a verify-only tail after the boundary review
   keeps the merge covered. A tail containing a new chunk review does not.
3. A blocker-free boundary review counts as `batch-covered` when its base and head trees bracket the merge
   on the integration branch's first-parent line.
This also settles the correction to design doc §3 that was marked "pending the owner's ruling".

**2026-11-24.** "Yes, agreed. PR and merge." — the credential check's placeholder exemption set is accepted
as the plan states it (`build-plan-credential-placeholders.md` Goals), residual risk included. A url-embedded
password needs no waiver when it is three characters or fewer, equal to its user, a placeholder word, a
template or variable whose content is a single-case name, or a mask. A real secret of one of those forms
passes `check-pr-hygiene`; a mixed-case secret in a wrapper, or one holding an unencoded `@`, still refuses.
The same message asked for both of the session's branches (`fix/yaml-inline-comment`,
`fix/credential-placeholders`) to be opened as PRs and merged.

**2026-11-24.** "Yep, let's PR and merge. And let's take care of the static documents. I agree with your
interpretation about making it light rather than skipped." Answering the triage of #1239 (a branch of
static documents pays the full code path):
1. A repo-declared set of static-document paths gets a **lighter** review at the PR boundary (one
   independent reviewer, no paired native review), **not** the doc-only route that skips review. The
   review on the reporting branch found real defects in such content, and the standing ruling in
   `coverage_algebra.is_judgeable_path` is to make review cheap, not skippable.
2. `fix/report-bug-triage-sync` is to be opened as a PR and merged.
The #1239 work lands in that item's build plan.

**2026-11-24.** "Yes on both, pr, merge, and get to develop and ../prawduct-live" — answering the two
asks on PR #1241 (#1239, static content):
1. PR #1241 is merged.
2. The plan's reading of the 2026-11-24 "light rather than skipped" ruling is confirmed: the paired
   native review stays out of scope, because it runs only on development builds and so is no
   consumer cost (`.prawduct/artifacts/build-plan-static-content.md` Goals).
The same message asked for this checkout to return to `develop` and for `../prawduct-live` to be
advanced to `origin/develop` (the dogfood track, as on 2026-11-22).

**2026-11-24.** "Yes to your recommendations" — PR #1242 (`fix/live-review-writes`) is merged, this
checkout returns to `develop`, and `../prawduct-live` is advanced to the new `origin/develop`.

**2026-11-25.** "let's get 1246 and 1238 in this release, both are important" — answering the release
readiness report: #1246 (the install tripwire misses a disabled plugin) and #1238 (handoff notes survive
only one session boundary) are fixed before the next release is cut, not deferred to a later one. The
designs for each land in their build plans (`build-plan-tripwire-disabled.md`,
`build-plan-handoff-notes-persist.md`).

**2026-11-25.** "yes to all of your recommendations" — answering the three asks after #1238's PR and
#1246's review:
1. PR #1248 (#1238, handoff notes persist) is merged. The release-plan go-ahead given in the same
   message covers merging #1246's PR once its gates pass, since the release needs it.
2. The two #1238 decisions made on the owner's behalf are confirmed
   (`build-plan-handoff-notes-persist.md` Goals): an empty notes file does not end inherited notes,
   and inherited notes have no expiry, showing the count of boundaries carried instead.
3. The next release is **v3.10.0**, a minor, because test-determinism adds a boundary-blocking
   class a consumer's PR can meet. All release-pending scopes ship; the cut follows
   `.prawduct/runbooks/cut-and-publish-a-plugin-release.md`.

**2026-11-25.** "when done also be sure ../prawduct-live is on this release" — after the v3.10.0 cut,
`../prawduct-live` (the machine plugin every governed repo here runs) is moved onto the `v3.10.0`
tag, detached, rather than onto `develop`.

**2026-11-25.** "yes to all of your recommendations" — answering four asks on the #1247 cluster:
1. #1232 is built in two steps. Chunks 01-02 of `build-plan-boundary-review-per-release.md` first; then
   `prawduct-hook check-boundary-coverage --json` runs in `~/source/discodon` (the repo #1222/#1223's figures
   came from; the run writes only its tree-key memo there), and its per-merge counts decide go/no-go on
   Chunks 03-06.
2. The NFR amendment text in that plan's Goals (decision 1) is confirmed as written: recorded beneath the
   stage-keyed clause in `nonfunctional-requirements.md`, the clause keeping its ratified words. A
   `boundary_review: per_release` repo runs the boundary review for derived-eligible work once per release
   batch; it is moved, not skipped; a blocker-free fix tail may merge as a deferral to the release check,
   never as coverage.
3. That plan's decisions 2-5 as recommended: the release anchor is whichever sits nearer the base's tip of
   (A) the newest first-parent commit adding a `.prawduct/releases/` file and (B) the oldest first-parent
   commit containing the newest version tag reachable from the base; a single-parent base commit whose
   judgeable changes are all declared `release_version_files:` reads `release-bookkeeping`, counted covered;
   the eligibility bound is 10 judgeable files, a constant beside `SHORT_PLAN_MAX_CHUNKS`, not a key; the
   fix-tail deferral applies to any PR in a per_release repo whose tail meets `diagnose_fix_churn`'s
   conditions and touches no risk surface.
4. #1247's six decisions in `documentation/issues/1247-design.md` as recommended: a per-repo
   `chunk_review: per_chunk | per_plan` key, default `per_chunk`; `per_plan` keeps the risk-surface
   condition; under `per_plan` a chunk declaring `Critic mode:` is a keystone that alone owes its review;
   `per_release` eligibility stays fixed at three chunks independent of `chunk_review`; #1247's ask 3 gets no
   new mechanism (test-impact reuse is #1096/#1088; #367 stands). #1247 stays open at stage design (effort
   M, impact S), built after #1232's Chunk 04.

**2026-11-26.** "Yes to all recommendations" — answering four asks:
1. #1232 Chunks 03-06 of `build-plan-boundary-review-per-release.md` are built (go). The pay test ran read-only on
   `~/source/discodon`'s ledger and git history (2026-10-23 on: 67 releases, 281 PR merges into develop, 110
   `cumulative` rounds / 17.0 h, 154 `verify-resolutions` / 11.3 h; re-derive with
   `documentation/issues/1247-measure/measure.py` and `git for-each-ref refs/tags`), not by running the op there.
2. Decision 2's tag candidate (B) of that plan changes: the anchor's tag candidate is the oldest first-parent commit of
   the base containing the merge-base of the base and the newest version tag, so a release tagged on a merge commit the
   base never sees (discodon: `v2.22.0` on `main`) anchors on the develop commit it released. Where the tag is reachable
   from the base, the answer is unchanged. Candidate (A) and "the nearer to the tip wins" stand.
3. PR #1251 (`fix/ci-pr-dedupe` → `develop`) is merged.
4. #1250: a merge the PR gate passed by base-advance transfer counts as covered at the release, as its own class
   `pr-transferred`. This extends the 2026-11-24 "covered" definition, whose text stands: the transfer requires the
   branch's diff byte-identical to the reviewed span, a base advance touching none of its files, and a suite run that met
   the merged tree, and the release op reads the PR gate's recorded grant before re-deciding.

**2026-11-26, later.** "yes agreed with your recs, let's do it" — answering two asks:
1. A release batch review (`span: release`, #1232) is never charged to `review_round_budget` and takes no scope's
   boundary slot (`critic_consolidate._cadence_round_ids`). This widens the 2026-11-23 ruling's item 2, whose
   not-counted set was a chunk's first full review and a scope's first boundary review. Why: it is the release's own
   step, not a round on any scope; charging it would leave `--force` the only route past a held `per_release`
   release, and a re-run is owed only when new merges land (fixes clear through `verify-resolutions`). Recorded as
   M2 in `build-plan-boundary-review-per-release.md`; key doc `review_round_budget` updated.
2. PR #1252 (#1250, `fix/boundary-coverage-transfer` → `develop`) is merged, ahead of #1232's PR, so #1232's PR does
   not carry it.

**2026-11-26 (doctor/janitor).** "can you figure out why agents say they cant run doctor and/or janitor and need the
human to do it, and fix so agents can run both?" — an agent may invoke both skills, not only a human typing the
command. Janitor's `disable-model-invocation: true` (85753fda) is lifted by removing the grants that made it
necessary (an interpreter pre-approved for a model-invoked skill reaches every op an allow-list withholds), not by
exempting it; doctor runs the repairs it offers on the owner's yes instead of handing the command to the owner.
Owner judgments (norm ratification, which plans are done, delegation policy) stay the owner's.

**2026-11-26 (round-4 review asks).** "yes to your recommendations" — answering two asks:
1. #1232 R-4 (rev at f2512df9): a release entry whose changes are all back to the release span's starting content
   (merged, then fully reverted before the release) is credited covered under its own named class, not owed a
   review. Why: nothing of it ships, so nothing is left unread — the batch rule's own condition 2 reasoning (a file
   back at the interval's base content needs no reading), applied to the whole entry. Recorded beneath the
   2026-11-25 amendment ("the boundary review is moved, not skipped"), whose words stand: what is moved is the
   review of what ships. The alternative (dispatching an empty-subject release review) was declined as a full
   boundary review that reads nothing.
2. The critic-reviewer agent's `git -C * <verb> *` grants, which also admit `git -C <dir> -c alias.x='!cmd' x`, stay
   as a recorded reach exemption (later moot: the reach rails retired with "what was over-built" below; `_REACH_EXEMPT` in `tests/test_backlog_skill_metadata.py`, branch
   `fix/agent-runnable-doctor-janitor`): the agent is dispatched only by the Critic under a no-execution contract,
   and narrowing it means redesigning the `git -C <dir>` form its own tests require.

**2026-11-26 (design stance).** "trying to close an open set makes no sense. Don't do that. We have to assume good faith
by humans and competence by models." Defenses whose premise is a human acting in bad faith (bypassing a gate to hide
work, rewriting a version file into a command) or a model ignoring its instructions (self-invoking a skill to reach an
op it was not asked to run) are not built, and an enumerated list is never extended toward completeness of an open set
(every spelling a prefix grant can reach). `allowed-tools` exists to cut prompts for a competent model; it is not a
security boundary. What stays: guards against accidents and real failure modes (crashes, git errors, stale state),
and a confirmation before an irreversible, outward-facing act the person asked for.

**2026-11-26 (what was over-built).** "Yes to all recommendations" — applying the design-stance ruling above:
1. The grant-reach rails retire (the must-prompt probe set, its witnesses, exemption tables and controls, and the
   semantic irreversible-op rail of 85753fda). Kept: `test_every_instructed_command_is_granted` (a skill can run what
   it instructs) and one literal check that no skill grants `backlog import|merge|file-upstream` by name.
2. The grant narrowings that only added prompts are reverted: janitor's `python3 *`, `npm *`, `git *`; pr's `git *`;
   runbook's `find *`; onboard's `git -C` grants. Janitor stays model-invocable and doctor runs its repairs on the
   owner's yes.
3. #1232's merged-branch-blocker route retires (W2's entry trees in the batch rule, M12's owed blockers in the verify
   roll-call, f2512df9, R-2, native 2), as do the version-shape checks on declared version files (bare and json/toml).
   A release batch review settles its own findings only. This narrows the 2026-11-25 NFR amendment's "BLOCKING
   findings clear only through `verify-resolutions`, at either point": the PR point stands; the release no longer
   re-checks a merge the owner made over a blocker.
4. The Critic's review protocol gains a severity rule: a finding whose failure needs a human acting in bad faith or a
   model ignoring its instructions is an observation at most, never a warning. Its own change, off `develop`.

**2026-11-26 (test cacheability).** "yes to all" — answering three asks:
1. `plugin/docs/test-determinism.md` gains the patterns this repo's own cache work (#1226) proved and never shipped:
   tests that run the product's own CLI as a subprocess (run it in-process), tool children that read ambient state
   (one helper that isolates and dates them), production code reading the clock or randomness directly (one
   replaceable owner), and declaring a test uncacheable on purpose. The testament cacheability advisory names each
   cause's remedy pattern. One change off `develop`; no new mechanical detectors (the design-stance ruling).
2. This repo fixes its own two largest remaining blockers (evidence-id randomness; the subprocess hook runner) and
   measures the gain, as a separate change.
3. An issue on testament proposes a `testament guide cacheable` page, its exact text shown to the owner before it
   is posted.
   **2026-11-26, later:** "yes post" — filed as brookstalley/testament#1013.

**2026-11-26 (later).** "yes PR and merge" — PR #1255 (`fix/critic-good-faith-severity` → `develop`, the Critic's good-faith
severity cap) is merged.

**2026-11-26 (later).** "yes to all recs" — PR #1254 (`fix/agent-runnable-doctor-janitor` → `develop`, agents can run doctor
and janitor; grant-reach rails retired) is merged.

**2026-11-26 (afternoon).** "Yes to all recommendations", answering two asks on PR #1258 (#1232):
1. Merge PR #1258 (`feature/boundary-review-per-release` → `develop`).
2. Keep every inferred design call in the build plan (M10–M21), M15's second clause included. That clause
   relaxes the release gate: an entry whose read diff brought no judgeable file onto the base is `reverted`
   and covered without a review, because nothing of it ships. It is owner-confirmed now, no longer only the
   builder's call.

**2026-11-26 (late afternoon).** "Yep merge and keep all three and delete merged and dismiss oversized advisory":
1. Merge PR #1259 (`fix/fork-project-dir` → `develop`, #1253).
2. Keep its three named decisions: `--project-dir` goes after the subcommand; a subdirectory is refused rather
   than walked up to its toplevel; every `--project-dir` refusal exits 1, not 2.
3. Delete the merged local branches `git-tidy` lists, and dismiss the oversized-build-plan advisory: the plan is
   archived at the next release, which is when its size stops being paid.
