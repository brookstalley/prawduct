# Change Log — Prawduct Framework

<!-- Append new entries at the top. Each entry is a ## section.
     Historical entries (pre-2026-03-22) are in project-state.yaml under change_log_history. -->

<!-- Older entries live in .prawduct/change-log-archive/YYYY-MM.md, moved there verbatim by `prawduct-hook archive-change-log`. -->

## 2026-09-23: test evidence names the failing tests, not just the count

<!-- prawduct: type=fix | scope=failing-test-ids -->

`test-evidence record` wrote `failed: 2` and nothing else, and deleted the junit report it had
parsed, so `test-status` exited 1 with no names and finding the two failures cost a second
full-suite run (#792). The recorder now keeps the failing ids from that report as `failed_tests`,
written `classname::name` because that is the one id every junit reporter emits, in report order,
up to 100. The `recorded:` line and the failing-record reason name the first ten and count the rest
from `failed`. That reason is what `test-status`, the PR-gate transfer and the PR review payload
print, so all three name the failures. A restamp carries the names forward with the counts they
explain. The key is absent when no ids were visible (a pass, `--from-counts`, a summary-only suite),
and `failed` stays the count of record.

## 2026-09-22: the PR reviewer's context claim now names path-scoped rules

<!-- prawduct: type=fix | scope=pr-reviewer-path-scoped-rules -->

`pr/SKILL.md` Step 3, the `pr-reviewer` agent and `review-protocol.md`'s Learnings Cross-Check
all said the reviewer is given no learnings (`omitClaudeMd: true` keeps `.claude/rules/` out). It keeps out the always-loaded files, but not a
path-scoped one (#888). Measured this session: a `pr-reviewer` that Read `plugin/skills/pr/SKILL.md`
received `.claude/rules/learnings/authoring.md` as a system message and quoted its headings
verbatim, and a control that Read `documentation/purpose.md` received nothing. Claude Code's
subagent documentation describes no per-agent setting that stops this. All three surfaces now
state the limit, and the agent is told to treat an arriving area file as learnings it was not
given, not as a checklist. `tests/test_pr_reviewer_agent.py` pins each correction by its own
sentence; a first cut searched the agent's whole body for "path-scoped", which it already held.

The `critic-reviewer`, which declares no `omitClaudeMd`, received `core.md`, both `CLAUDE.md` files
and `MEMORY.md` at dispatch, then `authoring.md` the same way. It uses learnings on purpose, so
that is recorded, not changed.

Ride-along owed from an earlier review: Step 1 now says a `merge=union` record "can resurrect
entries the base archived" rather than "resurrects every entry".
## 2026-09-22: `learnings-migrate --local` for repos that keep learnings out of git

<!-- prawduct: type=fix | scope=learnings-migrate-local -->

A repo that keeps its learnings out of git on purpose could not clear `learnings-unmigrated` (#889,
filed by a downstream product). The migration's undo is the commit that follows it, so it refuses
a corpus git cannot give back and a gitignored `.claude/rules/`. For a public repo whose learnings
hold private operational notes, both remedies it offered (commit it, unignore it) publish the notes.
Its only way through was a `learnings` gate waiver re-declared every session.

`--local` swaps the undo. Before it writes anything, it copies every file it will delete to
`<git-common-dir>/prawduct/learnings-backup/<UTC stamp>/` and reads each copy back. The git dir is
the one place in the tree no `git add` reaches, and the common dir survives `git worktree remove`.
Under `--local`, the refusals that exist because git is the undo give way to the backup: a corpus git
cannot give back, uncommitted changes, git unable to say whether there are any, and the ignored
destination. The refusals that guard against loss still stand: the byte accounting, a map key naming
no section, and a two-corpus `both`. Outside a git repo `--local` refuses and says to run without it,
since there is no git undo to replace there. The two refusals whose own remedy (commit it, unignore
it) would publish the notes now name `--local`, so an operator stuck on one is pointed to the route
that reaches the migrated state. Undoing a `--local` migration is two steps, and the success message
says both: delete the rules files it wrote, then copy the backup back. Copying back alone leaves both
layouts on disk, which the Stop gate blocks.

The session briefing's gitignored-rules suffix no longer says "unignore .claude/rules/". After a
`--local` migration the tree is ignored on purpose, and an agent told every session to unignore it
is one `git add -A` from publishing the notes. It now states the consequence: the tree exists only
in this checkout and a clone will not have it. `test_gitignored_rules_tree_is_named` pins the new
wording, and a new test pins the absence of the instruction on a `--local`-migrated repo.

Checked before building: Claude Code loads `.claude/rules/` from disk whether or not git ignores it
(a headless session in a repo ignoring `.claude/*` quoted a canary rule verbatim), so a local
migration's rules are loaded, which a waiver would never achieve.

## 2026-09-22: develop opens 3.6.1-dev.6

<!-- prawduct: type=chore | scope=dev-track-bump-3.6.1-dev.6 -->

The dev track's version moves to `3.6.1-dev.6` in the four carriers (`plugin/VERSION`,
`plugin.json`, `pyproject.toml`, the open `plugin/CHANGELOG.md` heading), so repos on the develop
track pick up `reviewer-prompt-file-list`, which merged after `-dev.5` was opened. The version
string is the plugin cache key; a repo that already resolved the `3.6.1-dev.5` cache would
otherwise never see it. #885 waits on a consumer running a build that includes it.

**No consumer notes were owed.** `reviewer-prompt-file-list` already carries its entry in the open
`plugin/CHANGELOG.md` section.

## 2026-09-22: Coordinator reviewers read their file sets from the manifest, not the prompt

<!-- prawduct: type=perf | scope=reviewer-prompt-file-list -->

The coordinator pattern pasted `files_reviewed` and `files_oracle` into each of the three
`critic-reviewer` prompts. The coordinator writes those prompts as output, one after another, so the
last reviewer's start grew with the file count. `.prawduct/artifacts/cumulative-latency-discovery.md`
ranks it second among the drivers of discodon's slow cumulative reviews: small but well measured.
The template in `review-protocol.md` now substitutes `<MANIFEST>` (`[dir]` joined to
`.prawduct/.critic-partials/manifest.json`) in place of both lists. `agents/critic-reviewer.md` says
the sets come from the manifest, which each reviewer already opened for `prior_dispositions` and
its rendezvous paths, so the pointer adds no read.

**The risk it opens is a reviewer with no subject set**, which reads exactly like a clean review.
`critic-begin` already refuses a manifest with an empty `files_reviewed`, and `critic-consolidate`
already refuses a partial whose `dispatch_id` is not the manifest's `id`. The reviewer's tree check
now covers the remaining case: a manifest it cannot read, whose `id` is not the review id in its
prompt, or whose `files_reviewed` is empty ends in the existing `dispatch-mismatch` partial, which
keeps the roster complete so the builder is told. That partial takes its commit and review id from
the prompt, not the manifest: in each of these cases the manifest's are missing or another review's,
and consolidation would reject a partial carrying them.

`TestReviewerFileSetsRideTheManifest` pins it. The template may substitute only fixed-size slots,
which catches any list-valued slot coming back, whatever its spelling, not just these two. It must name the manifest for
both sets, the reviewer contract must read them from there, and the guard must cover all three
conditions. Each assertion was red-verified by restoring the old wording.

**Token budgets, a declared raise.** `review-protocol.md` +43, which the single-pass-full reviewer
payload takes too because it loads the same file, and the dispatched-reviewer payload +138. Each is
recorded with its reason beside `LAST_MEASURED_TOKENS` or `LAST_MEASURED_PAYLOAD_TOKENS`.
The guard is the price of taking the lists out of the prompt, and the coordinator stops writing each
list three times, which on a large review is far more than the raise.

**Not measured yet.** The saving is expected to be the prompt-writing time the lists cost. The
next coordinator review on a large diff gives the number: its reviewers' start offsets, read
from the transcripts as the discovery did. Tracked as #885.
## 2026-09-22: develop opens 3.6.1-dev.5

<!-- prawduct: type=chore | scope=dev-track-bump-3.6.1-dev.5 -->

The dev track's version moves to `3.6.1-dev.5` in the four carriers (`plugin/VERSION`,
`plugin.json`, `pyproject.toml`, the open `plugin/CHANGELOG.md` heading), so repos on the develop
track pick up `measured-round-price`, which merged after `-dev.4` was opened. The version string is
the plugin cache key; a repo that already resolved the `3.6.1-dev.4` cache would otherwise never see
it.

**No consumer notes were owed.** `measured-round-price` already carries its entry in the open
`plugin/CHANGELOG.md` section.

## 2026-09-22: A round is priced from the clock, not from the reviewer's estimate

<!-- prawduct: type=fix | scope=measured-round-price -->

`telemetry.round_price` quoted what one more review round costs as the median of `duration_seconds`,
which is the reviewing model's own estimate. Read against the dispatch clock on the same rounds,
that estimate runs high, and worst on short reviews: this repo's `verify-resolutions` clocks at a
median of about 3 minutes against about 5 estimated, and its PR review at about 1 minute against 4.
Re-derive both with `prawduct-hook review-stats --json` (`by_role_model_mode`, the
`duration_measured` and `duration_self_reported` populations). The price is the number a builder
weighs a fix against, so an inflated one misprices the decision it exists to inform.

**What changed.** With at least `MIN_PRICED_SAMPLE` clocked rounds of the priced mode, the price is
their median and nothing else. The two populations never pool. Below that, the estimate still prices
the round, as before. The result carries `basis` (`measured` or `self-reported`), and the rendered
sentence names which: "median of N measured rounds", or "as the reviewing models reported them".
Tests in `tests/test_cost_of_commit.py::TestRoundPrice` pin the clock-first rule, the no-pooling rule
(red-verified with a pooling mutant), the fallback and its label, and the mode filter over clocked
rows.

**Records corrected in the same change.** `documentation/consumer-build-metrics.md` summary items 1
and 3, hazard 2 and open questions 2–4 all rested on self-reported durations. Hazard 2 said the
estimate was "corroborated within 16%". That held for discodon's verify rounds, which really take
about as long as the estimate says, and not elsewhere, so the licence is withdrawn. Hazard 2 is now
the one home for the measured comparison, and the code and tools point to it rather than restating
it. The same sentence is corrected
in `lib/review_dispatch.py`, `tools/pr-review-yield.py` and `tools/measure-review-loop-economy.py`.
`.prawduct/artifacts/pr-review-payload-discovery.md` gets a dated correction block beside its 13.1
figure, and `api-contract.md`'s `cost-of-commit --json` row lists the new `basis` key.
discodon's 13-minute PR figure is left marked unverified, not wrong: its PR reviews carry no clock
yet.

**Also shipped: the cumulative-latency discovery**
(`.prawduct/artifacts/cumulative-latency-discovery.md`). It asks why discodon's cumulative Critic
takes 7–17 minutes by the clock. Its answer is the volume of reviewer output, driven mainly by
re-reviewing a whole campaign branch against a fixed base. Serial reviewer dispatch and auto-loaded
context come second, and tools take under 4% of the time. It records findings only; no fix is
chosen from it yet.

**Not changed.** The per-branch tally in `coverage.format_branch_rounds` ("costing N so far") still
sums self-reported durations. It reads evidence-store facts, and those carry no dispatch clock, so
fixing it needs the clock recorded on the fact. Filed as #882.

## 2026-09-22: develop opens 3.6.1-dev.4

<!-- prawduct: type=chore | scope=dev-track-bump-3.6.1-dev.4 -->

The dev track's version moves to `3.6.1-dev.4` in the four carriers (`plugin/VERSION`,
`plugin.json`, `pyproject.toml`, the open `plugin/CHANGELOG.md` heading), so repos on the develop
track pick up the four scopes merged since `-dev.3`: `review-scrub-seams`,
`standing-block-closing-section`, `coverage-honesty` and `far-behind-branch-guidance`. The version
string is the plugin cache key; without the bump those repos keep resolving the `3.6.1-dev.3` cache.

The purpose is a holistic test: every efficiency and wall-clock change pending since `v3.6.0` runs
together on real consumer work before the tier and the cut are decided. The owner chose this over
cutting a release on 2026-09-22.

**No consumer notes were owed this time.** Each of the four new scopes already carries its entry in
the open `plugin/CHANGELOG.md` section. Besides this bump, the release-pending scopes that section
does not name are the same four as at `-dev.3`: two earlier bump chores, a fix folded into a
neighbouring note (`scope-note-plan-less-silence`), and a repo-internal instrument
(`review-loop-economy`, which changed only `tools/`, `tests/` and `documentation/`).

## 2026-09-22: Landing a far-behind branch becomes shipped guidance

<!-- prawduct: type=docs | scope=far-behind-branch-guidance -->

Up-levelled from this session's retrospective at the owner's request, after checking which lessons
shipped guidance already carried. Most did — the inner-loop verification ceiling, accept as the
default disposition, the concurrent PR reviewer, delegation's "serial by default" tell — and were
misses of application, not of guidance. One was genuinely absent and ships here: `pr/SKILL.md`
Step 1 on landing a branch far behind its base. Three salvages in one session showed the shape —
decide what landed by tree content; audit what the sync REMOVED **and ADDED** against the base,
since keep-both drops the base's revision and a `merge=union` record resurrects archived entries
as additions (#857, twice in three days); move relocated content to its new home and do not
re-add retired content; re-check the branch's own claims about the base, which is what produced a
blocking finding on PR #879. `TestFarBehindBranchGuidance` pins it.

**A second instruction was built and withdrawn in the same branch.** "Record the suite while the
Critic review runs" went into `building.md`, and the cumulative review showed it is not safe as a
one-liner: it contradicts "Record once, at Verify" in the same file, and the review's own
`test-status` check depends on the run — overlapping it either buys a stale-evidence warning per
review or lets older session-fresh evidence hide a failing suite from the review. That is the
ordering dependency #678 asks to have stated, so the analysis went there and `building.md` and its
ceiling are unchanged. The waste it targeted was mostly re-runs, which "Record once" already
forbids.

## 2026-08-20: a build plan with no `scope:` stops being invisible to everything that scans artifacts/

<!-- prawduct: type=fix | scope=coverage-honesty -->

`plan_index.iter_scoped_plan_candidates` yields on `if scope:` and nothing else. That is right for
a *map* — a map keyed on scope has no key for a plan declaring none — and it means every consumer
of that walk reports a set that reads as the whole artifacts directory while silently omitting
those plans. `plan-backfill`'s three buckets are the loudest case: they partition what the walk
yielded, not what is on disk, and in a surveyed consumer repo they described 60 plans out of 134.
The same walk is behind the scope→plan map, so a dispatch naming a scope whose plan declares none
reached the reviewer as `chunk-ref-missing unchecked` — a check that could not run, in a sentence
that reads like one that did (#642 cause 1).

**The remedy is the one this module already uses for an unreadable file**: the swallow stays where
the map needs it, and the fact is published separately on a cold path, outside the walk — a check
inside the fallible flow cannot catch that flow's own skip. The walk's yield is unchanged in
every case the corpus contains, which is what keeps the archival norm's guarantee about it intact —
with one honest exception, found in review rather than claimed away. Folding the `artifact:` read
onto the module's one scalar reader (it had a hand-rolled twin, the shape that lets `scope:` and
`artifact:` come to mean different things) made `artifact: null` read as *no declaration* rather
than as the literal type "null". The document is now kept as a plan instead of excluded, which is
the fail-safe direction the module documents. Zero documents in this repo carry that form, so the
yield is identical here; the change is real all the same and `tests/test_plan_index.py` pins it at
the walk, not only at the predicate.

**What made this more than a filter is deciding what an unscoped document has to be.** The walk's
existing predicate excludes only a document declaring some *other* `artifact:` type and treats one
declaring none as a plan — a fail-safe direction chosen where a declared `scope:` is already
evidence of plan-ness. The unscoped population carries no such evidence, and the predicate had
never been asked about it. Measured against this repo's live `artifacts/`: **22 documents pass it
and 20 are not build plans** — release plans, spikes, audits, `project-preferences.md`. A control
naming 20 non-plans on its first run is one nobody reads twice.

So `buildplan_refs.has_build_plan_shape` requires positive evidence, in the three forms a plan in
the wild actually carries: it declares the type, it has a `## Status` roster item, or it has a
chunk heading. Any one suffices, and each is load-bearing — one plan in this repo's own corpus is
reachable by that signal and no other. Across the 91 known-real plans here the three score 90, 90
and 91 and their union 91; against the 22 unscoped live candidates the union names exactly the 2
that are genuinely plans. Those are measurements, not estimates, and
`tests/test_unscoped_plan_fact.py` re-runs both halves against the real corpus rather than
restating the numbers.

An explicit `scope: null` — the parser's documented opt-out — is **not** reported. It is a
declared choice, and a control that fires on one can never be settled.

**Four surfaces state their coverage now** — every reader of that walk which reports a set.
`plan_backfill.survey` gains `unevaluated`; `plan-backfill` names the count and the paths under
both arms of the release-tag fork, in the same breath as the buckets rather than leaving it to
`--json`; `lifecycle-repair` gains its own `unscoped` key and sentence, and its stale-Status walk
now covers unscoped plans too, because whether a plan carries a stale derived-Status note has
nothing to do with whether it declares a scope; and the release gate **caveats** its "no
build-plan file" warning rather than suppressing it, since which scope an unscoped plan belongs to
is exactly what nothing there can know. That last one was not incomplete but FALSE — it said "work
is shipping with no plan describing it" about a plan in the same directory, which is the v3.3.4
recurrence this plan cites as its motivation.

**A fifth surface, Critic dispatch, ships through `develop`'s channel.** This branch first hung a
footnote on the dispatch gap sentence; `develop` meanwhile added
`buildplan_refs.deliverable_check_gaps`, which names each unresolved plan *with its remedy*, so the
footnote was dropped as a duplicate. That rested on the two covering the same plans, and they did
not: `deliverable_check_gaps` walked `iter_live_plan_files` (declared type or `build-plan` filename)
and missed a plan recognized only by its `## Status` roster. Found by the merge-forward's cumulative
review; its fallback now walks the UNION with `plans_missing_scope`, and
`test_a_plan_recognized_only_by_its_shape_is_named_too` pins it. The same review found
`lifecycle-repair` reporting scope-less plans it never edited, so `--apply` now removes the retired
derived-Status note from them too — report and edit loop walk one set, `_plan_documents`.

All five are diagnostic — no exit code moves and no gate reads any of it. That is a requirement
rather than a preference, and the first attempt broke it: routing the fact onto
`lifecycle-repair`'s `unreadable` list made it fatal and made `/prawduct:doctor` report degraded
forever, since `--apply` cannot add a `scope:` key. A diagnostic that pins a verdict is the
"control that can never go quiet" this chunk's own opt-out rule disqualifies.

Riding this commit: the per-mode payload meter added by the previous entry now derives each mode's
directive set from the dispatch it actually ran, and its ceilings are keyed by mode, so a fifth
mode or a fourth directive is metered rather than skipped.

**What the base sync settled about the rest of the plan** (2026-09-10, merging 333 commits of
`develop`). Chunk 04 — warn when a release-pending scope is absent from the consumer digest —
shipped on `develop` from PR #734 as `release_readiness._digest_advisories` and closed #702, so it
is superseded rather than built here. Chunk 03 — the base-advance transfer's silent denial — is
unchanged on `develop` and moved to #672, which now carries the chunk text as its spec. The plan
closes on Chunks 01–02; Chunks 03 and 04 stay unticked, with the reason under each heading.

The meter's own ceiling for `final` / `cumulative` moved 3900 → 4035, and the number is not this
branch's to spend: `review-protocol.md` grew on `develop` under its own ratified ceiling, which is
the figure the per-mode meter now tracks for the two modes that read that file and receive no
directive. Pinning below it would red-line on a raise the file already ratified; pinning above it
would let a directive added to those modes ride in free.

**Landed 2026-09-22 by a merge forward, not a rebase.** The branch sat a month behind `develop`
after its chunks closed; a triage by tree content found both chunks' code still absent there, so
`develop` was merged in. Code conflicts in `plan_index.py`, `buildplan_refs.py` and `prawduct-hook`
were both-sides-added and keep both. `develop` had since retired `.prawduct/learnings.md` /
`learnings-detail.md` for `.claude/rules/learnings/`, so this branch's four learnings were
re-derived rather than re-homed verbatim: two are already carried by `core.md` (*surveying takes
TWO searches … callers that branch on it*; *fix a defect at the LAYER IT WAS REPORTED AT*), the
transitive-consumer rule became one clause on the surveying rule (*and any WRAPPER's name too*),
and the size-capped-file-is-a-budget rule went to `authoring.md`, which loads on `.prawduct/**`
where plans are written. The `union` merge driver on this file re-added every entry `develop` had
archived, so the log was rebuilt as `develop`'s plus this branch's two entries.

## 2026-08-20: the finding-scope rule reaches the two modes whose payload had no room for it

<!-- prawduct: type=fix | scope=coverage-honesty -->

v3.4.0 shipped the instance-or-class rule stated in exactly one place — `review-protocol.md`
§ Severity Levels, which `final` and `cumulative` load. `chunk` and `verify-resolutions` load
`goals-1-3.md` and are forbidden to open the protocol, so for those two the rule did not exist.
The release note claimed otherwise: it named `chunk` as the one known gap and asserted that
`final`, `cumulative` and `verify-resolutions` all had it.

**What was actually true, and it is a distinction the note collapsed.** Two halves of the rule
ship separately. The GRADING half — re-run the finding's own reason as a search before writing
`fixed` — does reach `verify-resolutions`, through `RESOLUTION_IS_A_CLAIM_DIRECTIVE`. The
AUTHORING half — label the findings you raise — reached only the protocol's readers. So a
`verify-resolutions` reviewer was told to grade a class finding rigorously and never told to
label the ones it raises. A consumer repo's first post-upgrade `verify-resolutions` raised a
site-naming blocking finding with no scope answer, an hour after a `cumulative` on the same
branch labelled 29 of 30.

**Why this is a directive and not payload prose.** The rule is ~110 tokens in the form that
works and `goals-1-3.md` sat 3 tokens under a hard pin. Porting it means finding ~110 tokens in
the tightest payload in the system, against receipts recorded in that pin's own docstring. The
route is not novel — the grading half took it for the identical reason, and
`VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE` already records the general precedent that for the modes
it serves, a rating can live nowhere but in the dispatch directive. `FINDING_SCOPE_DIRECTIVE` is
delivered at `critic-begin` to the modes named by `GOALS_1_3_MODES`, so the set that reads
`goals-1-3.md` and the set handed the rule cannot drift apart at a call site.

**The vocabulary gained a third value it was already being asked for.** Three findings in that
same consumer review answered `Scope: none` — the priors cross-check, the learnings cross-check
and the backlog reconciliation, all mandated passes that must report even when clean and so bound
no defect. The protocol defined only `instance | class`, so the reviewers coined one. `none` is
now stated in both carriers.

**Cost, stated rather than absorbed.** The directive is ~148 tokens on every `chunk` and
`verify-resolutions` dispatch, pinned with a ceiling. `review-protocol.md` paid for its `none`
wording by dropping a worked example that was also Python-specific, in a file governing a
framework whose architecture norm says it must never be — net zero against its ceiling, and
`goals-1-3.md` was not touched at all.

`tests/test_finding_scope_rule.py` pins the map rather than the carriers, and pins DELIVERY by
running the dispatch. Three things are derived rather than listed: the mode set from
`MODE_TOKEN_TO_VERBOSE`, so a fifth mode fails until someone says which carrier serves it; the
mode→payload map from `review-cycle.md`'s `Protocol read` row, so re-routing a mode in the docs
reddens the map instead of silently leaving that mode with no rule; and delivery from
`critic-begin`'s stdout per mode, positive and negative.

**The first draft of that file got delivery wrong in the shape the rule it pins describes**, and
two reviewers found it independently. It asserted `"FINDING_SCOPE_DIRECTIVE" in begin_src` — a
grep of the hook's source — and that string also occurs in the comment above the emission, so
deleting the `print` left the pin green. The natural refactor `if verbose_mode in
GOALS_1_3_MODES` (comparing a verbose string against a set of tokens) dropped the directive for
both modes with the whole suite still green. Four mutations are now exercised: both of those,
re-routing `cumulative` in `review-cycle.md`, and removing `none` from the protocol.

Unit-cost is also metered per MODE now, not per file. `nonfunctional-requirements.md` § Direction
governs "what a given mode must load to answer its goals", and until this pin existed only the
files were measured — so moving a rule out of a full payload into a directive left every
individual meter green while raising what the reader loads. A `chunk` reviewer loads ~2395 tokens
and `verify-resolutions` ~3382; both are pinned.

The category ruling the plan opened as RULING NEEDED is recorded on architecture.md's own norm: a
rule whose readers load disjoint payloads may carry one statement per carrier, provided a
construction pins their agreement. It is at category level because the same edge had already been
decided twice case-by-case and a third case still re-derived it from scratch.

## 2026-09-22: The standing block is the digest's last word

<!-- prawduct: type=fix | scope=standing-block-closing-section -->

Salvaged from the unmerged `fix/standing-block-digest-tail` branch (2026-08-20), whose digest edit
conflicted with `develop`'s since-rewritten bullet: the MOVE and its tests were re-applied onto the
current text rather than merging the branch's stale copy.

**Why: a reported symptom, and placement is the surviving hypothesis, not a demonstrated cause.**
The branch was cut after a consumer on v3.4.1-dev reported sessions had stopped closing with the
standing block, and this repo's had too. It excluded two causes with evidence (as measured then):
delivery (`hooks/digest.py` gates only on `.prawduct/` existing, and the installed digest was
byte-identical, rule included) and the ~10,000-character `additionalContext` spill (9,811
characters). What remained was placement — the rule sat mid-way through "The hardest rules" with
four whole sections after it, since v3.4.0's `governance-surface-dedup` made the digest its only
always-loaded carrier. A third candidate was NOT excluded: the digest is injected once at
SessionStart, so deep into a session distance-in-conversation may dominate position-in-payload.
The move is free either way; **if the omission recurs, read it as evidence for that third cause,
not as this fix failing mysteriously** — and the structural escalation is the Stop hook checking
the closing message itself, which it already has the session to do. (The rule's own "the bottom is
all they read" is about the USER reading the turn, not the model reading the digest, so it is not
itself the argument.)

**The standing block moves to a closing `## Closing the turn` section.** `hooks/digest.py` injects
`plugin/methodology/session-digest.md` verbatim, so the file's bottom is the payload's bottom.
`TestTheStandingBlockIsTheDigestsLastWord` pins the property rather
than a line: the rule is carried, no `## ` section follows it, and no text follows its closing
pointer. Both structural assertions were mutated (a section appended after it, a trailing
sentence) and went red; a whitespace no-op survived. The section has its `DIGEST_SECTION_PLACEMENT`
entry, which the placement test requires of every section.

**Paid in place, and ratcheted.** The heading's tokens came out of two restatements inside the rule
itself — "last," beside "after every other word", and "on one axis" beside "what produces the next
turn" — so both injected shapes read 2 tokens LOWER (3280 -> 3278 framework, 2221 -> 2219 product),
and both ceilings are lowered with them in the same commit.

**Rider:** `TestDigestWiring`'s class-scoped fixture was an instance method, which pytest deprecates
(`PytestRemovedIn10Warning`, the one warning in the suite); it is now a module-level fixture.

## 2026-09-22: Review-gate seams that answered wrongly on a degraded input

<!-- prawduct: type=fix | scope=review-scrub-seams -->

Re-applied from the unmerged `fix/review-scrub-seams` branch (last commit 2026-09-10), which
conflicted with `develop`; triaged by tree content, every change below was still absent there. Ported fresh rather than merged, under a new scope, because the
branch's entries reused `tactical-efficiency` and `durable-agent-worktrees`, both already shipped.
**Its learnings are deliberately not ported:** the branch added a "never raises contract is a claim
about EVERY input" rule and a correction block to the since-retired `learnings.md` /
`learnings-history.md` pair, and `core.md` already carries the rule twice over — *make an absolute
robustness claim literally true and test the claimed-safe path*, and *a `try/except` around a
producer that RETURNS its degraded states guards nothing*. The old branch is archived after merge.

**Every transfer decision reads one classifier.** `_merge_base_verdict` tested "anything but
`unavailable`" while `check_cumulative_critic` tested `== "match"`. On `develop` the difference was
not cosmetic: an unrecognized status reached the Stop gate's grant path and raised
`KeyError: 'prior_base'`. The first cut named `coverage.TRANSFER_MATCH` and had both gates test it
positively; the review (R-3) found that still left three sites — the Stop gate, the PR gate's
verdict and the PR gate's rendered remedy — each reading the status for itself, agreeing but not
by construction. `coverage.classify_transfer` is now the one reading, mapping any status it does
not know to `"unknown"`: denied, and rendered with no remedy. The test asserts all three sites
deny an unknown status (verdict, exit, and no *could not run* NOTE), and each site was mutated to
a negative test independently — each went red. The contract and its sweep rule are registered in
`boundary-patterns.md`.

**`verify-resolutions` tells a degraded store from a missing anchor.** `_prior_review_fact`
iterated a store it never graded, so an unreadable store and one carrying newer-schema records
both reported *prior review fact … not found* — pointing at a re-review instead of the store or
the plugin version. It now answers both states (`_store_unusable`), and `critic-begin` exits
**6** for them rather than 1 (R-1): the skill's exit-1 row on `verify-resolutions` demotes and
re-dispatches, which cannot repair a store and on an unreadable one would append its fact to a file
nothing parses. The skill's exit table, the command's docstring and `api-contract.md`'s sentinel
list carry the new code — the docstring had also been missing exit 4. **5 is withdrawn, not free**:
#167's reverted `self-inflicted-refusal` held it on `develop` (never in a release), so it is not
given a new meaning. A missing anchor on a healthy store keeps exit 1, pinned as the control.
The exit-table row is a **declared +29-token raise** on `SKILL.md` and both single-pass route sums
(`test_v5_methodology.py`, `test_reviewer_payload_budget.py`), priced against the full round the
exit-1 fallback would buy each time; drafted at +81, the remedy moved to the refusal's stderr,
which is read only when it fires.
The anchor lookup takes the store from `begin_review`, which
reads it ONCE for the anchor lookup and the prior-dispositions block so the two see the same
moment of a store every worktree of the clone appends to. The read is lazy, so a dispatch
reaching neither reader parses nothing. No write lies between the two readers on the path that
continues; the only writes are refusals that return first.

**`evidence.read_facts` and `_plugin_version` catch `UnicodeDecodeError`.** It is a `ValueError`,
so `except OSError` let a non-UTF-8 store escape a function whose contract is to return a status
dict; `_plugin_version` feeds `verdict_cache`'s memo key, where a raise crashes the gate.
`_plugin_version` also pins `encoding="utf-8"`.

**The #648 inseparability note is restated against the tool contract.**
`gitstate.is_ephemeral_worktree` and its `prawduct-hook` call site said the branch/code inseparability was
ASSUMED, not measured. The worktree tool contract — no merge operation; `remove` refusing on
uncommitted or unmerged work unless `discard_changes`; isolation worktrees auto-cleaned only if
unchanged — was checked against the live tool schema on 2026-09-22 and is cited, with the
falsifier and residual kept.

## 2026-09-22: develop opens 3.6.1-dev.3

<!-- prawduct: type=chore | scope=dev-track-bump-3.6.1-dev.3 -->

The dev track's version moves to `3.6.1-dev.3` in the four carriers (`plugin/VERSION`,
`plugin.json`, `pyproject.toml`, the open `plugin/CHANGELOG.md` heading), so repos on the develop
track pick up the three scopes that landed since `-dev.2`: `scope-note-plan-less-silence`,
`review-interval-extension` (#167) and `pin-status-tick-meaning`. The version string is the plugin
cache key; without the bump those repos keep resolving the `3.6.1-dev.2` cache and dogfood nothing
while believing otherwise.

**The track stays on `3.6.1-dev.N`, which does not commit the release tier.** Two entries in the
release-pending set are typed `feature`/`feat`, and on the consumer-visible one
(`review-interval-extension`) that reads as a minor. The prerelease is deliberately guessed LOW
(`release-process.md` release checklist step 10, *Guess low*): a prerelease sorts just below its own release, so from
`3.6.1-dev` every possible cut — patch, minor or major — is a forward move, where a high guess
makes a patch cut a backward one. The tier is decided at the cut, in the release plan, not here.

**Two consumer notes that were owed are added in the same commit**, which is what the `-dev.2` bump
did for `unresolved-scope-diagnosis`. `pin-status-tick-meaning` changed `plugin/methodology/`
and `plugin/templates/` and carried no note at all; `review-budget-trunk-shape` changed
`plugin/lib/coverage.py`, `critic_consolidate.py`, `evidence.py` and `prawduct-hook` and had
gone two bumps with none, so a dev-track repo has been running a newly-live round budget with
nothing telling it the ceiling now reaches dispatches it never reached before.
`check-releasability` reported both as release-pending scopes absent from the open section.

**The bump also pins every declared carrier, which nothing did between releases.**
`test_version_mirrors_VERSION_file` pinned `plugin.json` against `VERSION` and stopped there, so a
bump that moved two of the three carriers left `pyproject.toml` behind with a green suite;
`check_version_files` compares against `git show <tag>:…`, so it runs only once a tag exists and
cannot stop a `-dev` drift on develop. `test_every_declared_release_carrier_agrees` derives the
carrier set from `release_version_files:` rather than a hand-kept list, so a carrier added later is
covered the day it lands. Red-verified twice: with `pyproject.toml` left at `-dev.2` it fails while
101 other tests pass — which is the measurement of the gap — and dropping `pyproject.toml` from the
declaration fails the in-declaration assert. Both mutations were restored by inversion. It is the
Critic's R-1 on this branch, closed here rather than filed. Two observations were accepted on the
record; the second was accepted as DISPROVEN — `affects_test_outcome` is a three-way disjunct, and
both paths it named answer True on the first two, so the hazard it described cannot occur.

**The consumer note's `api-contract.md` citation is now relational.** `plugin/CHANGELOG.md` is read
from consumer repos, where that filename names the consumer's own contract, so the sentence leads
with the `project-state.yaml` template comment that actually ships to them.

**The scope is named for the version, not the date.** `dev-track-bump-20260922` is already taken by
the `-dev.2` bump earlier today, and `scope=` is collapsed to a set by `release_readiness`: a
second entry under that name would merge two bumps into one scope, so one of them would be
invisible to the release classification that must account for every scope.

## 2026-09-22: A Status tick means built and reviewed — never merged or released

<!-- prawduct: type=docs | scope=pin-status-tick-meaning -->

**Owner decision.** A build plan's `## Status` tick had three working meanings: "the chunk's review
passed" (the digest, the PR skill), "the work shipped" (left over from when the boxes flipped at
release), and "verified in the field" (`build-plan-branch-claim-multiplicity.md` Chunk 04). Readers
that assumed different ones disagreed. #167's extension deferral had to guess around the difference.

`planning.md` now carries the one definition: **a tick means the chunk is built, committed and
reviewed on the branch — never merged or released**. Merged and released belong to the plan (live
until archived) and to the change-log's `release=` tag. The build-plan template's Status comment
names the same meaning. The digest's existing line, "tick after the chunk's review", was already
consistent and is unchanged, because it injects into every session and has no room for a copy.

**`build-plan-branch-claim-multiplicity.md` is ticked and archived.** Its Chunk 04 waited on a
sibling repo running a session on the develop track. The fleet's evidence stores show seven have,
from 2026-08-20, so the condition its own paragraph set is met. The scope shipped in v3.5.0, so the
plan is archived as completed. VRF-017's status in `operator-verification.md` is left for the owner
to flip.

## 2026-09-22: A fix made after a clean review rides the next review instead of buying a round

<!-- prawduct: type=feature | scope=review-interval-extension -->

**Closes #167**, by a different mechanism than its title proposed: rounds are not refused, the next review covers them. Across the fleet, 150 of 242 `verify-resolutions` rounds between 2026-09-13 and
09-22 ran when nothing blocking was outstanding. 63 of those were followed on the same branch by
another full review, which re-read the same edits. The previous attempt (#167's withdrawn Chunk 02)
refused such rounds and left a gap that only a 720-second `cumulative` could close. This change
refuses nothing.

**A `chunk`/`final` review now starts at the covered frontier.** `gates.covered_frontier` walks
HEAD's first-parent history for the newest commit whose tree review evidence reaches, with no
unresolved blocker and at least one review on the path. When commits after it are unreviewed —
typically a non-blocking fix committed after the last review — `critic-begin` starts the interval
there. One review covers the fix and the next chunk's work, and the edge it records composes for
every gate, so no gap is left. The manifest and the review fact record `base_extended_from`; the
evidence schema version is unchanged. Nothing extends past an open blocker (only
`verify-resolutions` clears those), on a branch with no review yet, or across a judgeable base sync
(no pre-sync review composes from the new merge-base, so the interval stays at HEAD). The Stop
gate's merge-base fallback now also runs when the session-base marker is missing, and
`cost-of-commit` asks the same merge-base question through `_merge_base_verdict`.

**Nothing tells the builder to buy that round any more.** Deferral applies when all four of these
hold:

1. The newest review on the branch is of the current, still-unticked chunk (by the chunk id the fact
   records).
2. That review left no unresolved blocker. It is checked on the fact itself, because a review of
   uncommitted work leaves its tree nowhere a history walk can see.
3. The plan has another chunk after this one.
4. A covered frontier exists.

When they do:

- `infer-critic-mode` answers `deferred` instead of `verify-resolutions` for a non-blocking fix, and
  instead of `cumulative` for a clean tree mid-plan.
- The Stop gate warns (`deferred-boundary-review`) instead of blocking.
- The review close's NEXT-ACTION leads with the later review: commit the reviewed tree first, then
  the fix. It replaces the cost of a round, the "third route" and the price.
- `cost-of-commit` answers `free` and says which review will cover the commit (`rides_next_review`
  in `--json`).
- The widened-verify fallback recommends `final` over `cumulative` when a frontier sits behind the
  committed work.

A chunk nobody reviewed, a blocker any review on the chain still holds, and anything after a boundary `cumulative` are never deferred. A frontier that could
not be looked for (an unreadable store, git failure, the walk bound) is named at dispatch rather
than read as "none". The PR gate is unchanged.

**Docs.** `review-cycle.md`, the Critic `SKILL.md` and `review-protocol.md` describe the new interval
in place. `building.md`'s "Resolve findings" now scopes fix → verify → commit to while a blocker
remains, and points at NEXT-ACTION for a non-blocking fix mid-plan. The reviewer-payload readings went down, and their ceilings were ratcheted with them.

## 2026-09-22: The unresolved-scope note stays quiet on plan-less work

<!-- prawduct: type=fix | scope=scope-note-plan-less-silence -->

The `no-claim` diagnosis added by `unresolved-scope-diagnosis` fired on every branch that no plan
claims, including chores and small fixes that have no plan and need none. It told them to add
`branch:` to "the plan this work belongs to", which is advice with nothing to act on. It first
showed up on the `3.6.1-dev.2` bump PR. `no-claim` now fires only when a live build plan was created
or edited on this branch without claiming it, and the note names that plan. A branch that touched no
plan gets no note. The other three causes are unchanged, and none of them depends on the branch
touching a plan. The git read behind this ("which files did this branch change since it left the
base") is now one helper, `_changed_on_branch`, shared with the finished-plan liveness check. The
check therefore answers the same question it did before, from one place.

## 2026-09-22: develop opens 3.6.1-dev.2

<!-- prawduct: type=chore | scope=dev-track-bump-20260922 -->

The dev track's version moves to `3.6.1-dev.2` in the four carriers (`plugin/VERSION`,
`plugin.json`, `pyproject.toml`, the open `plugin/CHANGELOG.md` heading), so repos on the develop
track pick up #868 (unresolved-scope diagnosis) and #869 (`cost-of-commit` stops pricing a covered
tree as a round). The version string is the plugin cache key; without the bump, those repos keep
running the `3.6.1-dev.1` cache. Also adds the consumer note for `unresolved-scope-diagnosis`,
which #868 did not carry.

## 2026-09-21: cost-of-commit stops pricing a Critic-covered tree as a round

<!-- prawduct: type=fix | scope=866-cost-of-commit-covered -->

**Closes #866.** `cost-of-commit` classified the pending paths by `is_judgeable_path` alone and never
asked whether a review already covered the tree. Observed on `fix/845-pr-review-clock`: a chunk Critic
reviewed the uncommitted tree with 0 blocking, `cost-of-commit` then said `costs-a-round — 8 of 13
path(s)`, and after the commit `check-cumulative-critic` was satisfied with no new round. The false
price is read at the fix/accept decision, where it pushes a builder to accept findings a fix would
have closed for free.

**The no-argument form now asks the gates' own composition.** `gates.commit_coverage` runs
`coverage_verdict` over `HEAD^{tree}` → working tree. When that composes with no unresolved blocker and
at least one review on the path, the verdict is `free` and names the covering review(s), and `--json`
carries them as `covered_by`. Because a plain `git commit` records the index, the relaxation also
requires the index to be untouched (equal to HEAD, the `git add -A && git commit` flow) or fully staged;
a partially staged index commits a tree no review saw, and keeps the path price. It uses composition rather than the issue's proposed `head_tree` equality
(#851's `tree_is_covered_by`), so a docs-only edit after the review still rides free and blockers
settle exactly as the gate settles them. Blocked, uncovered, and unreadable all leave the path price
standing.

**Two surfaces deliberately keep the old answer.** The explicit-paths form is never relaxed: a path
list may be a partial commit whose tree no review saw, and `/prawduct:pr` prices a post-review delta
with exactly that form. `commit_cost` itself is unchanged, because the Critic close's cost lead reads
it right after writing a review of this very tree, and #851's arm there prices the *next* edit.

**Residual:** coverage that reaches the working tree without passing through HEAD's tree (a cumulative
spanning merge-base → working tree) still reads as a round. It errs toward the conservative price.
One narrow optimistic case remains: from an untouched index, `git commit -a` commits tracked files
only, so a reviewed untracked file is left out while the verdict said `free`. The message says to
commit the tree verbatim, which is `git add -A`.

Guards: `TestCoveredTree` in `tests/test_cost_of_commit.py`. Four mutants were each killed by a named
test: dropping the verdict flip, relaxing the explicit-paths form, removing the index-staging check
(partial staging, and a staged change reverted in the working tree), and skipping the store precheck
(a newer plugin's fact must leave the path price, never read as free).

## 2026-09-22: A review whose scope did not resolve now says why

<!-- prawduct: type=fix | scope=unresolved-scope-diagnosis -->

**A third of Critic reviews across seven repos recorded no scope, and nothing said so.** From
2026-09-13 to 2026-09-22, 131 of 382 review facts recorded `scope_chosen_by: not-resolved`. Each
one is invisible to the round budget and to scope-matched dispositions. The only trace was a
parenthetical on the record-lint line. Repos whose plans put `branch:` in frontmatter resolved
about 90% of the time; the others about 35%.

**`critic-begin` now names the cause and the edit that fixes it.** When no scope resolves it
prints a `PRAWDUCT NOTE` for the first cause it finds: a plan claims the branch but declares no
`scope:`; a plan names the branch on a `branch:` line *below* its frontmatter, where nothing reads
it (the commonest shape in the repos measured); the active plan claims a different
branch; or nothing claims the branch at all. It says nothing on the integration branch, where no
plan should claim it. The cause is recorded as `scope_unresolved_cause` in the dispatch manifest
and the review fact, so how often each fires can be counted. The field is additive; the evidence
schema version is unchanged.

**A finished plan still matches its branch name when this branch edited it.** Branch-name
inference used to reject a plan with every Status box ticked, on the grounds that boxes flipped at
release. They no longer do: they are ticked after each chunk's review, so every box is ticked by the
plan's own final cumulative, and that review lost its scope. A fully ticked plan now matches when
this branch created or changed the plan file since it left the base branch. The plan's own branch
wrote its ticks; a later branch that only reuses the name did not. That keeps a merged plan, live on
gitflow until the release, from capturing a follow-up branch. This matters beyond review
attribution, because the Stop hook, the briefing, mode inference and the PR payload resolve their
plan the same way. The remedy that reaches all of them is a frontmatter `branch:` on the plan being
built; `--scope` reaches review dispatch only.

## 2026-09-21: The PR review clock survives its findings being fixed

<!-- prawduct: type=fix | scope=pr-review-clock -->

**Closes #845.** `/prawduct:pr` marks the PR reviewer's dispatch (Step 3) and appends the
`review.pr` ledger event later (Step 4). The caller fixes the review's findings in between, so
`ledger-append` compared the mark against a HEAD that had moved. It refused the mark as *"for a
different tree"* and fell back to the reviewer's own estimate. So every PR review that found
something lost its clock, and the measured population leaned toward clean reviews. #845's third
reproduction put the cost at a real 228s recorded as a self-reported 300s.

**The mark is now checked against the tree the reviewer read, and the interval ends when the
reviewer wrote its evidence.** For `review.pr`, `ledger-append` resolves the evidence's
`commit_reviewed` (an abbreviated sha resolves; one naming no commit is refused by name) and checks
the mark against that instead of HEAD. It also records the evidence file's mtime as the new
optional envelope key `review_written_at`. The mtime is used because the reviewer writes the
`timestamp` field itself, which would put a model back into a code-read clock. Evidence older than
the mark is an earlier review's file and is refused by name. `review.critic` is unchanged: its
append is the end of its review. The three readers (`review-stats`, `tools/pr-review-yield.py`,
`tools/measure-consumer-overhead.py`) now go through one helper,
`review_dispatch.event_interval_seconds`, which ends the interval at `review_written_at` when it is
present and at `ts` otherwise, so older rows read exactly as before. The tree check was not relaxed:
a mark from a tree other than the one reviewed is still refused. Recorded as a `[DECISION]` beneath
`data-model.md`'s staleness clause.

**`tools/measure-review-window.py` reads the window v3.6.1 is waiting on**, written before its
data. It puts every Critic review fact since `--since` in a cohort by the plugin version that
wrote it (`actor.plugin` on the fact), split at a released `--cut` (default 3.6.0). The cut is a
release and not a date because consumers run the develop tip, the plugin cache is keyed by version
string, and #831/#833 landed inside `3.5.1-dev.2`, so a `-dev` string does not identify the code
that ran. Empty rates count only facts that record `observations`, clocks are joined from the
ledger by `fact_id`, and every rate and clock median prints its `n` and is marked THIN below
`--min-cell`. On
2026-09-21 the post-3.6.0 cohort held 13 facts from 2 products. Re-run the script rather than cite
that figure.

Guards: `TestPrClockSurvivesFixingItsFindings`, and a reader-agreement case in
`test_dispatch_interval_one_home.py`. Six independent mutants were each killed by a named test:
anchoring back on HEAD, ending at `ts`, dropping the evidence-predates-mark check, dropping the
unresolvable-sha refusal, text-matching instead of resolving, and not writing the key. For the
script, `tests/test_measure_review_window.py`: seven mutants killed (pre-release order, numeric
pre-release parts, unknown versions counted as before, unrecorded facts pooled into empty rates,
the THIN boundary, and both ends of the clock join). Five existing `test_governance_ledger.py`
fixtures now write the PR evidence after the dispatch mark, as real use does. The new
older-than-the-mark refusal made the old order pass only when both landed in the same second.

---

## 2026-09-21: The PR payload's backlog scan stops calling an unread input an answer

<!-- prawduct: type=fix | scope=863-payload-backlog-scan -->

**Closes #863.** `pr-review-payload`'s `backlog` section is R-2's only data source, and it scanned
two inputs that each fell back to `""` when unreadable: the commit messages (`_commit_bodies`, on a
failed `git log`) and the change-log entry (the `change_log` section's body, which is `None` whenever
it degrades). The ordinary trigger was the second one — a branch no build plan claims has no scope,
so the section degraded, the scan saw no entry text, and it printed *"no backlog ids cited … R-2 has
nothing to check (this is an answer, not a failure)"*. Reproduced on #864's own branch, whose entry
cited #672 and #845.

**Two changes, one per failure.** With no scope, `_section_change_log` pairs the entry the branch
ADDS against the base (`git diff --unified=0 base...HEAD`, matched by heading text so an uncommitted
working-tree edit cannot shift line numbers); a branch adding no entry is an answer, and an unreadable
diff still degrades. And `_section_backlog` takes the inputs it could not scan: an empty set over one
degrades with *R-2 is NOT answered*, and a non-empty set carries a `NOT SCANNED:` line, so a short list
never reads as the whole set. `_commit_bodies` returns `None` on failure rather than `""`.

**`review-protocol.md`'s degraded-backlog rule is split to match**: a store it could not read still
means NOTE and skip, but an input it could not scan means run R-2 by hand — a `backlog sync` cannot
help there, and skipping would repeat the false clean one layer up.

Guards: the tests in `TestAnUnscannedInputIsNeverAnAnswer`, red before the fix (the end-to-end one
failing on #863's exact sentence); four independent mutants — dropping the unscanned list, pairing
every entry instead of the added ones, removing the `NOT SCANNED:` line, restoring `""` on a failed
read — each killed by a named test, the last one through `assemble()` rather than only at the helper. Develop opens `3.6.1-dev.1`.

---

## 2026-09-21: Where the fleet's review rounds actually go — a committed instrument, not a scratchpad query

<!-- prawduct: type=feat | scope=review-loop-economy -->

**The consumer-overhead program's VR-share target had no instrument behind it.** Its 2026-09-16
triage set a baseline with a query that lived in a scratchpad and is gone, so its figures could not
be re-derived — the failure `core.md` names as *a spike that discards its code leaves its numbers
unfalsifiable*. `tools/measure-review-loop-economy.py` is that query, committed and tested, and
`documentation/consumer-build-metrics.md` gains the reading it produces.

**The tool reads the ceiling and the counted modes FROM the plugin that enforces them**
(`core.REVIEW_ROUND_BUDGET_DEFAULT`, `critic_consolidate.FULL_ROUND_MODES`), so a change to either
lands in the reading without anyone remembering to update prose. It does **not** read the plugin's
counting predicate — `analyse` pools a scope's whole history where `_round_budget_verdict` counts
only what `count_branch_rounds` admits — and the doc now says so, because that bound changed in
#776, which this branch picked up from `develop` rather than made. Parameters track; predicates do
not. Cite the command, never the digits.

**The finding: the v3.5.0 round budget is aimed elsewhere, by design.** `verify-resolutions` is 66%
of 2,248 Critic reviews and is not a mode the ceiling counts; the ceiling is 6 full rounds per scope
and the 90th percentile of full rounds per scope is also 6, so only 31 of 248 scopes (12%) ever
reach it; and 10% of reviews carry no scope, for which `_round_budget_verdict` returns `unavailable`
and never refuses. Together those bound what the control can ever touch at 118h of 294h — an **upper
bound, not a saving**, since it counts the rounds spent before the ceiling would have fired. The
largest addressable block is elsewhere: **322 of 534 cumulative runs (60%) are a repeat cumulative on
a scope already reviewed cumulatively**, which is WS5/#672's target and which that program ranks
fifth.

**Three hazards were added because this reading tripped on all three, and every one of them is a
completeness claim that was not checked.** Hazard 8: pooling the scope-less rows under one key per
repo invents one enormous scope and overstates the ceiling's reach — the first pass reported 14% and
64% where the truth is 12% and 60%, pinned by `TestAScopelessRowIsNeverAScope`. Hazard 9: the marker
paragraph asserted that every consumer marker was a `-dev` snapshot spanning `3.3.4` to
`3.5.1-dev.2`, which is the printed table with its first and last rows removed; three of the fifteen
are released versions, the oldest from 2026-07-16. Hazard 10: `find_ledgers` globbed one level deep
and so could not see a worktree ledger INSIDE a repo, finding 17 of 20 — and the excluded set was
exactly the delegated work, not a random sample — while the prose above it claimed *every governed
ledger on this machine*. The corpus size is now printed on the CORPUS line so that claim is
checkable, and `TestTheCorpusIsBoundedByPropertyNotByDepth` pins the depth against a control proving
the old predicate misses the fixture. All three times the conclusion survived the correction and the
warrant did not — the worse direction, because the next reader re-derives conclusions and copies
warrants.

**Two changes land in the SIBLING tool and outlive this branch.**
`TestEveryIsoParseSurvivesPython310` policed a hardcoded two-name `TOOLS` tuple — the container, not
the property — so a tool added later read as covered while nothing scanned it, which is exactly how
this branch's own `--since` shipped a Python 3.10 crash past the guard written for it. It now
enumerates `tools/*.py` with a non-vacuity assertion and a positive control, so **every future tool
in `tools/` is covered on the day it lands**, with nobody remembering to add it. And
`measure-consumer-overhead.py`'s shared `read_ledger` gained a `scope` field, which is what makes a
per-scope reading possible at all. Neither is scaffolding for this bundle.

**Durations remain self-reported** (hazard 2): 23 of 2,248 rows carry a measured dispatch interval.
Lean on the run counts, which are one row per real dispatch. #845 tracks why the measured clock is
lost on the ordinary path.

**The consumer-overhead program's own workstream table is now superseded, and § Related work says
so.** Measured against that branch on 2026-09-21: WS0 and WS2 (#744) have shipped, and #292 and
#767 — placed out of scope and deferred respectively — shipped in v3.6.0. Anyone planning from that
table re-derives first (`git log --oneline develop..docs/consumer-overhead-program`, and resolve
each issue it names); this reading bears directly on its WS1/WS5 ranking.

---

## 2026-09-20: The review round budget fires on a trunk repo — bounded by worktree, not by lineage

<!-- prawduct: type=fix | scope=review-budget-trunk-shape -->

**#776.** `_round_budget_verdict`'s docstring names trunk-based merge-base zeroing as the reason the
budget's unit is the SCOPE and not the branch — and then bounded the count by
`coverage.count_branch_rounds`, which admits a round only when its commit lies strictly after the
merge-base on HEAD's lineage. On a trunk-based repo, which `base_branch:` supports and the briefing
treats as ordinary, every push makes `merge_base == HEAD`, so that set is empty, an intersection with
it is empty, and `spent` was 0 on round twenty. The review loop's only declared stopping rule was
declared, documented, on by default and inert, on the exact repo shape its own docstring cites. It
shipped in v3.5.0 and was found by the v3.6.0 release audit.

**The fix bounds by `actor.worktree` when the span holds no commits.** Not by scope alone, which is
how the fix was first described: the evidence store sits in the clone's git common dir and every
worktree writes into it, so dropping the bound would charge a scope for rounds a sibling worktree
bought on the same plan. `count_branch_rounds`'s own docstring is explicit that overcounting "says
something false in the direction that discredits the whole message", and that is a stopping rule's
worst failure — it refuses a round the builder needed. Lineage was the only thing separating
worktrees; where it separates nothing, the worktree does. `actor.worktree` is written by
`evidence.append_fact` on every fact the plugin has ever appended (966 of 966 review facts in this
clone's store, earliest 2026-07-13, measured 2026-09-20), so no schema moves and nothing is
backfilled.

**Keyed on the SPAN being empty, never on the count being zero.** The two agree everywhere except on
a branch that has commits and has bought no round yet — where zero-keying would charge a first round
the scope's history from a previous branch. This fix makes the control work where it did not work at
all and leaves the working path alone; `test_a_branchs_first_round_is_not_charged_the_scopes_history`
is what "alone" means, and it is the assertion the plausible wrong implementation fails.
`coverage.count_branch_rounds` gains one reported field, `span_commits`, because the span is walked
there and a caller cannot otherwise tell an empty span from a branch with no rounds yet.

**Read the predicate, not the repo shape — two consequences follow from it.** A trunk repo is the
case that motivated this and is not the definition. A branch cut and not yet committed to has an
empty span too, so a branch RESUMING a scope inherits that scope's rounds from this worktree; the
budget's declared unit is the scope, so that is consistent, but it is a behaviour change on
branch-based repos and not only trunk ones. And nothing resets the worktree-bounded count: a branch
cut resets the lineage one, trunk has no cut, so reusing a scope name for a second body of work
inherits the first's rounds and can refuse its very first dispatch — auto-accepting the OLD work's
outstanding findings with it. Give each body of work its own scope name, or raise the budget. Both
are stated in `project-state.yaml`'s template comment and in `api-contract.md`, which consumers
receive; the build plan is deleted at release and is not a home for either.

**The same defect was live at the other reader of the same signal, and is fixed here too.**
`coverage.format_branch_rounds` — the line leading the `uncovered:` gate block — told a builder
*the next round is this branch's first* whenever `rounds == 0`, which on a trunk repo is round
twenty. That is #776's own root cause at a sibling call site, so it is keyed on `span_commits` in
both places rather than patched where it was noticed. An empty span now reads as the round count
being UNAVAILABLE, and a branch that genuinely is on its first round still says so.

**The verdict and the guard-refusal fact carry `bound` (`lineage` | `worktree`).** The two bounds
count different sets and returned indistinguishable verdicts, which would have left the control's
own retirement question — *did it ever refuse a round that turned out to be needed?* — unanswerable
from the record it appends for exactly that purpose. The refusal message names the bound too, since
"this work bought N rounds" denotes the branch on one and the worktree on the other. Reading it back
is `prawduct-hook evidence list`, which renders the field as a `bound=` column on the guard-refusal
row — the consumer-visible half, without which the retirement question stays unanswerable in
practice however faithfully the fact records it.

**What this does and does not buy a trunk repo.** The ceiling now reaches `chunk` and `final`
dispatches. It does not reach `cumulative` there and never could: a cumulative interval is a commit
range, so on trunk `critic-begin` refuses it as an empty diff long before the budget is consulted.
That is a different answer to a different question and is left alone. An exit 4 that was unreachable
on one repo shape becomes reachable there — additive, with `--force` as its escape hatch, and no
caller can have bound to its absence.

**Rider, #859.** `plan-backfill --apply` archives a plan by writing a stamped copy and unlinking the
original, staging neither. `tests/test_path_reference_resolution.py` enumerates from `git ls-files`
and reads from disk, so an unstaged archive makes two tests raise `FileNotFoundError` — a red that is
not a defect, at the moment a red suite is most alarming. It hit the v3.5.0 and v3.6.0 cuts
identically. The `--apply` output now names the staging remedy — the exact paths that
moved, each anchored at the repo root with `:/`, because a release cut leaves the operator's
in-flight artifacts in that same directory and a relative pathspec resolves against whatever
directory the line is pasted into. A run that moved nothing stays quiet, `--apply` or not. It rides
this commit rather than one of its own: this commit is judgeable and owes a review anyway, so the
rider buys no round.

---

## 2026-09-20: v3.6.0 is cut, and develop reopens on 3.6.1-dev

<!-- prawduct: type=chore | scope=release-v3.6.0 -->

**17 scopes, 20 change-log entries, `K = 0`** — the whole-develop promotion path, nothing withheld.
`main` is at `11dab896`, tag `v3.6.0` published with the CHANGELOG section as its Release notes,
`check-released v3.6.0` reports 3 of 3 verified. Re-derive the scope set with
`grep -o "scope=[a-z0-9.-]* | release=v3.6.0"` over `change-log.md` plus
`change-log-archive/2026-09.md`.

**A minor, and the number was re-derived rather than inherited.** The standing 2026-09-15 ruling was
3.5.1, taken when the bundle held three scopes; `gates.json` was already stamped `since: 3.5.1` and
`develop` had been running `3.5.1-dev.N`, so every in-repo signal agreed with a number chosen
fourteen scopes earlier. Re-derived from the final scope set at Phase 0 and put to the owner with
both sides. Full reasoning in `.prawduct/artifacts/release-plan-v3.6.0.md` § Version — that file is
the decision record, not a summary of it.

**No fourth review-cost lever joined this release, and that is a decision rather than an omission.**
Eight of the seventeen scopes are review-cost work directly (`review-loop-termination`,
`review-convergence`, `review-cost-decision`, `review-stages`, `review-stats-observations`,
`review-yield-instrument`, `pr-review-payload`, `critic-dispatch-clock`) and three more are adjacent
(`test-status-clause`, `test-report-scope`, `pr-step1-recorder`). A backlog audit at the Phase 1
Checkpoint asked whether any remaining review-tax item should ride the cut; the answer was no, on the
warrant already recorded in `.prawduct/artifacts/review-cost-investigation-2026-09-19.md` § 8.4:
*the honest next act is a measurement window, not a fourth mechanism.* The three shipped
interventions carry 15 post-intervention verify rounds and § 8.1 shows them confounded by the
`observations` array's 2026-09-16 start, so a fourth lever landing in the same release would make all
four unattributable. The window needs no build — `review-stats --since/--until` shipped here, and the
derivation is committed at `.prawduct/research/review-cost-2026-09-20/verify_population.py`. It needs
rounds, which is what promoting this release buys.

**One live defect the audit verified against HEAD, filed rather than fixed here.** #776 —
`critic_consolidate._round_budget_verdict` names trunk-based merge-base zeroing as the reason the
review round budget keys on SCOPE, then intersects with `coverage.count_branch_rounds`, which admits
a round only on `merge_base..HEAD` lineage. So the review loop's only declared stop is silently inert
on the repo shape its own docstring cites, and no test covers that shape. It shipped in **v3.5.0**,
not here, so it is a v3.6.1 candidate and not a reason to have reopened the cut.

**Phase 1 step 6 gets the exception it always needed**, deferred out of the prep commit on purpose
because `origin/develop` was what Phase 2 promoted. The step says *no unticked boxes on a plan whose
scope you just tagged*, which has a guaranteed false positive on the plan whose own acceptance is the
release being cut: `build-plan-learnings-v2-docs.md` Chunk 05 asks for "Runbook Phases 0–3 complete",
so at Phase 1 it is unticked *because* the step is running. It now names that case, says it ticks
after Phase 3, and asks the cutter to record which plan it is so the next reader can tell it from a
real miss.

`develop` reopens on `3.6.1-dev` — guessed low on purpose, so every possible next cut is a forward
move for anyone running the develop track.

---
