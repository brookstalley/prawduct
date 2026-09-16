# Change Log — Prawduct Framework

<!-- Append new entries at the top. Each entry is a ## section.
     Historical entries (pre-2026-03-22) are in project-state.yaml under change_log_history. -->

<!-- Older entries live in .prawduct/change-log-archive/YYYY-MM.md, moved there verbatim by `prawduct-hook archive-change-log`. -->

## 2026-09-16: the change log stays bounded — history moves to a monthly archive

<!-- prawduct: type=feature | scope=change-log-archive -->

Nothing ever shortened `.prawduct/change-log.md`: the release adds `release=` and nothing more, so
this repo's log reached 1.5 MB and every product's is on the same curve. The oversized advisory
could not help — its only advice forbade deleting tagged entries, which is nearly every byte — so it
nagged every product with nothing to do. New `prawduct-hook archive-change-log [--apply] [--json]`
moves entries verbatim into `.prawduct/change-log-archive/YYYY-MM.md` once the live log passes the
repo's oversized threshold, cutting it to half; release-pending entries (in a product that versions)
and undated entries never move, and a malformed tag refuses with nothing written. `plan-backfill`
and record-lint's scope witness now read live + archive; `check-releasability` stays on the live
log, which holds every pending entry by construction. `/prawduct:pr` Step 1d runs the archiver on
every PR (a no-op under the threshold) and the release checklist runs it after tagging, so no repo
needs a person to decide to compact. Before writing, it re-reads the log it would leave with the
release gate's own predicates and refuses on any difference; it writes every file all-or-nothing
(`core.write_all_or_none`), and it refuses when git tracks the live log but would ignore the archive.
The release gate's "already tagged for this release" lookup reads the archive too, so a Phase 0
re-run after archiving still recognises shipped scopes. The oversized-change-log advisory now asks the archiver: it
hands the runtime the command when history can move and says why otherwise. Its old guarded-bullet
tests are replaced by tests of that contract — the guard's reason (pending work is never offered
for removal) is still asserted. Amends CL5 and adds CL8 in the lifecycle requirements. This repo's
own log is archived on this branch.
Supersedes the unmerged `fix/change-log-lifecycle` branch and `documentation/issues/802-design.md`
(one history file, current-minor-line retention — 326 KB left live, no archiving in unversioned
products); its result invariant, `write_all_or_none` and parser-line-number entry boundaries are
ported. Resolves #802 and #793.

## 2026-09-16: review-stats counts what verify passes demote

<!-- prawduct: type=feature | scope=review-stats-observations -->

`verify-resolutions` rates new findings BLOCKING-only and demotes the rest to observations, so its
`findings` undercount what it saw by construction. `review-stats` showed only that undercount: a
narrowing that fires too rarely was visible, one that suppresses real findings was not. The
observations already ride every `review.critic` ledger event (review-loop-termination ch.01), so this
is a read, not a new record. Every stat block now carries `observations` and
`reviews_recording_observations`; an event written before the array existed is excluded rather than
counted as zero, because "nothing demoted" and "not measured" must not render the same. Two keys
changed the `--json` shape, so the report `schema_version` goes 1 → 2 (nothing parses version 1
today). Closes the last acceptance box of #585.

## 2026-09-16: the churn coverage grant is cut; the observations close prices fixing

<!-- prawduct: type=fix | scope=review-loop-termination -->

The plan's last chunk was to compose `diagnose_fix_churn`'s condition as covered — a round the
diagnosis called provably unnecessary would be granted instead of narrated and charged. **It was
cut before any code, on two findings from re-reading what it would have stood on.** The predicate
is file-granular, and its own docstring says the message it feeds must not claim content-level
certainty: it cannot tell a fix from new work written into a file some finding named. Today a false
positive routes to `verify-resolutions`, which still blocks on weakened tests and fudged fixes; a
grant would have routed the same false positive to no review at all. And #167's design holds that
the first verify pass after a full round always runs, because it is the pass that covers the fix
commit — the exact pass the grant would have skipped. The plan's Chunk 03 records both reasons and
what would reopen it.

**What ships is the two items that were riding on that chunk.** The `0 blocking, 0 findings, N
observations` close — the one clean close that still carries fixable items — ended at its coverage
clause, so it never said what fixing costs, how to price a batch before committing it, or that a
fix can ride the next chunk's commit. It now carries all three, exactly as the warnings close does:
the cost-of-fixing guidance moved into one constant both closes share, and the duration guard that
scanned it inside the function now scans the constants directly. And observation-cited files stay
out of the churn predicate by decision rather than by omission — widening it would widen what the
gate calls churn, from items the reviewer did not even rate as findings — pinned by a test that
fails if they are ever counted.

## 2026-09-16: a clean delta stops reading as branch clearance

<!-- prawduct: type=fix | scope=review-loop-termination -->

A `verify-resolutions` pass covers its own delta and nothing else. On a clean close it said
`0 blocking, 0 other findings — THE REVIEW IS OVER`, and the only thing standing between that
sentence and "the branch is clean" was a parenthetical telling the reader to go **ask** the gate
about coverage. In #716 the author relayed branch clearance upward after round 3; round 4's
cumulative found a BLOCKING defect that had been present since chunk 1, structurally invisible to
every verify round because it never sat inside one of their diffs. Both facts were true — the delta
was clean, the span was never reviewed — and nothing said the second.

A clean verify close now **states** the span verdict instead of inviting a question about it:
*this delta is clean; the branch is NOT covered, N commit(s) since the base unspanned*. A covered
branch gets the covered sentence and no manufactured hedge — but it names what the span ends at,
because a verify pass routinely reviews a dirty tree and the fix about to be committed is not in
the span just called covered; a span carrying unresolved blocking
findings from earlier rounds says how many; a span nobody could read degrades to the text that
shipped before, because "go ask the gate" is the honest answer for unknown and advice failing soft
is not advice failing silent.

**It renders the value the gate already computes rather than a second one.** `check-cumulative-critic`'s
composition — the same span, the same base-advance transfer — is now a function returning data, and
the gate is its printer. Two implementations of "is the branch covered" would disagree the first
time either moved, and the copy the builder reads while deciding what to report is the advisory
one: the worse half to be stale. The advisory read records no transfer grant, on the standing
split that authority records its own yield and advice observes and writes nothing.

**Scoped to the one close where the misreading happens.** With blocking findings the next move is
to fix them and the branch question is moot; with a blocker carried from the review being verified
the line already says NOT DONE; and every other mode ships exactly the text it shipped before. A
silent widening would have been a requirement nobody wrote.

**It does not order a round.** The clause points at `check-cumulative-critic` for the cheapest
route and says not to assume that route is another full review — a clause ending in "run a
cumulative" would spend a round on every clean verify close, which is a worse pump than the one
this closes.

**Two things the Critic caught, both fixed in this commit.** The clean arm said *"there is nothing
to disposition"* while the cache beside it held `O-n` observations — and since `verify-resolutions`
demotes everything below BLOCKING, "0 findings, N observations" is that mode's *modal* close, not an
edge. It now names them and the command that answers one. The same gap had left the relayed
`NEXT-ACTION:` line printing `disposition <fid>`: the one carrier the `<fid|oid>` correction below
skipped, and the strongest of them, because on the single-pass path it is the only text that
reaches the builder at all. Separately, the covered arm asserted branch coverage over a *vacuously
empty* span — merge-base == HEAD, zero commits, no evidence composed — which is the permanent state
of a trunk-based governed product. An empty span now gets its own sentence: there is nothing here
for a review to span, and that is not a claim about review evidence.

**The verify pass closed clean and demonstrated the chunk on itself**: its close named its own
three demoted observations by `O-n` id and stated the branch verdict with the dirty-tree anchor —
`0 blocking, 0 findings ... 3 item(s) were demoted to observations ... The BRANCH is covered too, at
HEAD`. All three observations are answered on the record, one of them carried into Chunk 03's
commit with its home written into the plan.

**rev-20260916T182912Z-d994f53c** — scope `review-loop-termination`, chunk 01, 2026-09-16T18:30:55Z

_No findings._

_Observations — read, not owed. Answering one is optional._

| Observation | State | Detail |
|---|---|---|
| O-1 | accepted | The coverage claim stays true; only the explanation is wrong, and only in the add-then-revert state where merge-base tree == HEAD tree with commits > 0. Not worth a round on its own. The fix for whoever next touches span_clause: let `commits` drive the wording and `path` drive the arm — two disjuncts, two jobs. |
| O-2 | accepted | Operator-facing help text that nothing parses, so a regression to <fid> costs a reader one confusing moment and no gate. The relayed NEXT-ACTION line — the carrier that reaches the builder on the single-pass path and the one this chunk was correcting — IS pinned, negative assertion included. If the class is ever wanted as a whole it belongs in tests/preferences/, where it can also record why prawduct-hook:1734 keeps the narrow <fid> (the sweep is findings-only by recorded decision). |
| O-3 | accepted | Correct, and it rides Chunk 03's commit rather than buying a round of its own — written into the plan's Chunk 03 section so it is a deferral with a home, not a drop. Chunk 03 edits critic_consolidate.py (the plan's partition says so), so it will meet this function. |

**No findings** — a clean pass.
**3 observations demoted** — 3 answered. An observation gates nothing; answering one is optional.

Two notes from the previous chunk's review ride this commit rather than buying their own round:
`goals-1-3.md`'s `observations` key is now pinned by the test that guards what the file's raised
ceiling bought, and the disposition usage string — what a **refused** invocation prints — says
`<fid|oid>`, which is the moment a builder needs to know an observation id is legal.

## 2026-09-16: an observation can be accepted on the record, not only fixed

<!-- prawduct: type=feat | scope=review-loop-termination -->

`verify-resolutions` demotes every non-BLOCKING finding to an *observation*. Observations lived
only in the reviewer's prose report, so a builder could discharge one in exactly two ways: **fix
it**, which moves the tree and buys a review round, or **say nothing**, which loses the reasoning.
There was no "considered, declined, here's why". #716 reports its author fixing observations
*because accepting them left no trace*, and two of those fix commits bought rounds 4 and 5 of six.

A `verify-resolutions` reviewer now writes its demoted items into the partial's `observations`
array, `build_fact_body` carries them onto the review fact with `O-n` ids, and
`prawduct-hook disposition <review-id> O-1 --accept "<reason>"` answers one.

**The observations sit BESIDE `findings`, never inside it, and that placement is the whole safety
argument.** They are carried on `record_lint`'s terms — data *about* the review, not a finding *in*
it — so they never reach `counts`, and composition walks `findings` alone. "No gate's verdict
changes" is therefore true by construction rather than by audit, and it is asserted: a test pins
that an accepted observation leaves a blocking finding blocking, never enters `findings_index`
(the index a resolution must pass to weaken a gate), and produces no resolution. The census keeps
its severity tallies and its `undispositioned` count over findings alone; an unanswered observation
reads `noted`, because counting it as a debt would rebuild one layer down the obligation the
demotion exists to remove.

**The array is refused outside `verify-resolutions`, and that closes a hole this design opened.**
Every property that makes an observation safe for GATES — nothing counts it, nothing composes on
it — makes it unsafe as a RECORD, because nothing checks it either. Demotion is a verify-mode rule;
an array outside `findings` that every mode could write would let a `final` reviewer file nine
warnings where nothing counts them and consolidate a 0/0/0 review. Consolidation now fail-closes on
`observations` from a non-verify dispatch, mirroring the rule that has always governed
`resolutions`.

**The ids reach the builder through `.critic-findings.json`.** They are assigned at consolidation —
the reviewer wrote prose and never saw an `O-n` — so the derived view is the only surface on which
a builder told it may ACCEPT an observation can name the one it means. Without that leg the feature
would have passed every test and been unreachable in practice.

**The fork was a persisted-format decision and was put to the owner rather than recorded by the
builder.** Three routes, weighed against three named consumer queries written down before any field
was designed — the census, the proportionality norm's yield query, and a human reading back why a
round was not spent. The table is in the build plan. Persisting observations *as findings* answers
the census for free but inflates `counts` and makes every un-accepted observation read
`undispositioned`; relaxing the fid domain alone needs no reviewer change but never captures the
subject, so the yield query becomes unanswerable.

**A recorded position was departed from, and it is #585's.** That item scopes out *"persisting the
demoted observations themselves (deliberately not facts)"* and asks for a **count**. A count cannot
be dispositioned, so it cannot deliver what the round-buying was actually about. The departure is
narrower than it reads: nothing here mints an observation *fact* — the array is a field on the
review fact — so the store grows no new kind and `SCHEMA_VERSION` does not move. #585's own
acceptance falls out as a by-product; its remaining leg is surfacing the count in `review-stats`.

**Two prose surfaces were carrying claims this makes false, and both are corrected rather than
left to rot.** `review-cycle.md` owned the argument and said an observation *"is not a recorded
fact: it cannot be `disposition`ed"* and that yield was *"half-emitted, and that is a known gap"*.
The cost it names now is the one that is still real — the fix delta's own content is rated at
BLOCKING only. The `review-loop-termination` row of `cross-cutting-concerns.md` carried the same
gap in two places, both closed. The test that pinned the old cost pins the new one, with the
change of subject stated in its docstring.

**Two ceilings moved and both raises are declared, not trimmed to fit.** `goals-1-3.md` 2345 →
2400 (measured 2399): the JSON block is the schema a reviewer transcribes, and a key it must
write while no example carries it is the seam where an identifier degrades silently. Paid in place
first — step 4's "Nothing else executes" restated the bolded never-run rule three lines above it.
`VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE` 707 → 770 tokens, under its unchanged 900 ceiling,
buying the entry shape and the refusal of a `blocking` entry. `review-cycle.md` came in *under* its
previous reading, so its ceiling did not move. Every one of these figures is re-derived by a test
that carries it; this entry transcribes them, which is why it is the copy that goes stale — it did
once already, before the commit, and the corrected reading is the one above.

**Review census** (`chunk`, one reviewer, 8 subject / 5 oracle files — 0 blocking):

**rev-20260916T174427Z-ddbc0bc7** — scope `review-loop-termination`, chunk 01, 2026-09-16T17:47:11Z

| Finding | Severity | State | Detail |
|---|---|---|---|
| R-1 | warning | fixed-unreviewed | fixed in `.prawduct/artifacts/build-plan-review-loop-termination.md` |
| R-2 | note | accepted | Inert in both homes and wrong by 14 in each. Fixing only the free copy (the change-log) would leave the two records disagreeing, and the test comment is judgeable, so correcting both buys a round to move a number nothing reads — which is the exact trade this repo's inert-count cap exists to refuse. The reviewer said no edit wanted and it is right. |
| R-3 | note | accepted | Real gap, judgeable fix, riding Chunk 02's commit rather than buying its own round — written into the plan's Chunk 02 section as deliverable 1 of its ride-along block, so it is a deferral with a home and not a drop. Mitigated meanwhile: the twin carrier in VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE is pinned and is delivered at dispatch for the only mode that writes the array. |
| R-4 | note | fixed-unreviewed | fixed in `.prawduct/artifacts/build-plan-review-loop-termination.md` |
| R-5 | note | accepted | Riding Chunk 02's commit with R-3; recorded as deliverable 2 of the plan's Chunk 02 ride-along block. Both halves are judgeable and neither is a contradiction — the widened domain is stated in the same file eight lines earlier, and the rendered census shows O-n ids directly. |
| R-6 | note | accepted | Informational: the priors block did its job — thirteen prior dispositions in these files and none re-raised. There is nothing to action in a control reporting that it worked. |

**6 findings** (1 warning, 5 note) — accepted: 4, fixed-unreviewed: 2.

The warning was the one thing this work owed outside the tree: #585's Scope-out still said
prawduct deliberately does *not* persist demoted observations, which this makes false. It and #167
now carry comments — #585 recording the departure and keeping its `review-stats` leg, #167 told
that the gap its design calls "currently-unfiled" has landed. Two notes ride Chunk 02's commit
rather than buying their own round, and both are written into that chunk's section, because an
unwritten deferral is a drop.

**Two widenings were declined on purpose.** `prior_dispositions` stays findings-only: it is
budgeted payload a reviewer reads before the diff — the block that once measured 2.7× the protocol
file it exists to shorten — and a re-raised accepted observation costs the builder a sentence where
a re-raised accepted finding costs a round. `auto_accept` stays findings-only too: it exists
because a refused round strands findings the loop still owed an answer on, and an observation is
owed nothing, so sweeping one would mint a fact recording a decision nobody made. Both are
comments in the code at the point of decision.

## 2026-09-13: v3.5.0 is cut, and develop reopens on 3.5.1-dev

<!-- prawduct: type=chore | scope=release-v3.5.0 -->

The largest batch since the tag convention began: **32 release-pending scopes, 63 change-log
entries**, all shipping, nothing withheld — `K = 0`, so the whole-develop promotion path. `main` is
at `45902920`, tag `v3.5.0` published with the CHANGELOG section as its Release notes,
`check-released v3.5.0` reports 3 of 3 verified.

**A minor, and the call is recorded rather than reflexive.** `develop` had been running `3.4.1-dev`
since the last cut, so the patch was the default the marker implied and the ratified
conservative-versioning norm argued for. It was raised as a framed decision before the cut and the
maintainer chose the minor, on the runbook's unratified precedent that *a subsystem going live* is a
minor: `/prawduct:report-bug` files upstream through a new network egress surface that carried a
norm amendment to ship, `review_round_budget` puts a declared stop on a review loop that had none,
and the subject/oracle split changes what a review rates. Full reasoning in
`.prawduct/artifacts/release-plan-v3.5.0.md`.

**The release prep turned the suite red, in two ways Phase 0 cannot see.** `check-releasability`'s
`unproven-suite:` gate reads the tree you have *now*; Phase 1 then rewrites four files, and the
runbook says as much. Both breaks were real, not bookkeeping. The new CHANGELOG headline was wrapped
across two physical lines, so the version-delta banner — which reads the section's first *line* —
would have shipped an unpaired `**` on the single most-read line prawduct emits, the exact defect
`silent-clear-checks` fixed one release earlier. And `plan-backfill`'s sixteen archive moves left
the index still naming the old paths, so `_governance_prose()`'s `git ls-files` walk opened files
that were no longer there. Staging fixed the second; unwrapping the headline fixed the first. **A
suite re-run between Phase 1's edits and Phase 2's tree-set is what caught both** — it is not a step
in the runbook, and this entry is the argument that it should be.

**`build-plan-branch-claim-multiplicity.md` ships with Chunk 04 open and stays live**, which is the
plan's own recorded decision: the develop-track dogfooding recipe is written and nobody has run a
session on it, because it installs from `ref: develop` and could not be exercised until it merged.
`plan-backfill --apply` archived the other sixteen plans and refused this one on the Status-roster
reason — the correct outcome, and the one refusal `archive-plan` does not share. The release notes
say the track is undogfooded rather than implying otherwise, as the plan asks. The briefing's
staleness scan will keep firing on `develop` and both remedies it prints are still wrong; the
correct action is VRF-017, then a tick.

`develop` reopens on `3.5.1-dev` — guessed low on purpose, so every possible next cut is a forward
move for anyone running the develop track.

**Two `Done when` items graded a correct release wrong, and both are fixed in the runbook rather
than filed.** The content-identity bullet enumerated *five* files and this cut's reopen commit
carries seven — the release plan's `Status:` line and step 11a itself — so a correct release reads
as "Phase 2 did not finish"; the bullet now says what the reopen commit carries and points at step
17, which is the check that actually proved identity, before the promotion. And the install triage
fatals on a **prerelease** installed version: this machine's cache is keyed `3.4.1-dev.2`, no such
tag exists, `git rev-parse "v3.4.1-dev.2:plugin"` errors, and the `||` branch prints *cache holds a
NON-release plugin — case 2 or 3*, routing a perfectly correct develop-track install at the
delete-the-cache remedy. That is the same false-negative shape #646 removed from the ancestry test,
surviving one layer up. A `case 0` now names it with a test that applies — does the cached plugin's
own `plugin/VERSION` equal the key it is cached under — and the old command is gated behind ruling
it out.
