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
