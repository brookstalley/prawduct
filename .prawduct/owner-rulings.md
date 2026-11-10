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
