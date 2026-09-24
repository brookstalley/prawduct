# Change Log — Prawduct Framework

<!-- Append new entries at the top. Each entry is a ## section.
     Historical entries (pre-2026-03-22) are in project-state.yaml under change_log_history. -->

<!-- Older entries live in .prawduct/change-log-archive/YYYY-MM.md, moved there verbatim by `prawduct-hook archive-change-log`. -->

## 2026-09-24: v3.6.1 is cut, and develop reopens on 3.6.2-dev

<!-- prawduct: type=chore | scope=release-v3.6.1 -->

**26 scopes and 27 change-log entries. `K = 0`, so this took the whole-develop promotion path with
nothing withheld.** `main` is at `e2a07086`. Tag `v3.6.1` was published with the CHANGELOG section as
its Release notes. `check-released v3.6.1` reports 3 of 3 verified, and the hand-dispatched
`verify-release` run is green. To re-derive the scope set, grep for `release=v3.6.1` in
`change-log.md` and `change-log-archive/`.

**A patch, as the owner named it.** `.prawduct/artifacts/release-plan-v3.6.1.md` records why the
bundle's weight did not argue for a minor. `learnings-one-line` stays off this release. It
registers its gates `since: 3.7.0`, so its merge moves `develop` to that number.

**The cut first needed a green `develop`, and it did not have one.** `a0e90e80`, the #672 design
doc, was committed straight to `develop` with no PR and no suite run. It tripped
`test_closing_keyword_is_never_named_without_its_condition`, and #899 fixed it before Phase 0.

**Phase 1 notes.** Seven plans were archived by `plan-backfill`.
`build-plan-coverage-honesty.md` was archived by an explicit `archive-plan`, because it closes on
Chunks 01–02 on purpose. `archive-change-log` moved 16 entries. One consumer note was added to the
digest, for `pr-reviewer-path-scoped-rules`. The first draft of the headline overclaimed
`review-interval-extension` (it covers warnings while plan chunks remain, not every fix), and it
was narrowed before the cut. `waiver-pragma-plan.md` still declares no `scope:`, so the sweep cannot
evaluate it. That is pre-existing, and it is unrelated to this release.

## 2026-09-23: the declared suite runs at the boundary, not at every chunk

<!-- prawduct: type=feature | scope=suite-at-boundary | release=v3.6.1 -->

`building.md` said the declared suite runs at Verify, so every chunk paid a full run on a tree that
changed again within the hour, and the inner-stage Critic reported the not-yet-run suite as stale
evidence and recommended a run (#820). **This changes a default every governed repo inherits.** A
chunk's Verify now runs the project's `Inner-loop verification` row (else the tests for the files
touched), and the declared suite runs at the boundary: before the work lands on the integration
branch (the `cumulative` review and the PR, where there are ones). A project that wants the suite at every chunk says so in that same free-text row. No new setting
and no framework vocabulary were added: the owner ruled on #820 to derive the default from the stage,
which the stage-keyed review-rigor norm and the #747 ruling (the testing burden "sits intentionally
at entry to develop") already imply. The inner-stage reviewer (`chunk`, `verify-resolutions`, `final`) now reads a
stale or missing record as the normal in-flight state and raises no finding; `cumulative` keeps it a
WARNING, and failing evidence stays BLOCKING at every stage. The template row, the doctor's
row-drafting guidance, the janitor's Execute step, the build-plan template's example Chunk 01
criterion (now "the chunk's own tests pass") and `briefing.py`'s fallback Critical Rules, which reach
delegates, say the same; `tests/test_suite_at_boundary.py` scans every shipped `.md`/`.py` under
`plugin/` and the release notes' unreleased section for the retired instructions. Also on this branch:
the consumer `plugin/CHANGELOG.md` gains the `failing-test-ids` paragraph that #894 merged without.

## 2026-09-23: a green run is remembered per tree, across branches and worktrees

<!-- prawduct: type=feature | scope=per-tree-test-evidence | release=v3.6.1 -->

`.test-evidence.json` holds one run per worktree, so switching branch replaced it. Switching back to
a branch whose tree already had a green run then re-ran the suite: in one consumer, one `/clear` cost
four ~7-minute re-runs (#653). Now every `test-evidence record` of a real run or an ingested report
also appends a `test-run` fact to the shared evidence store. The fact records the tree, the counts,
the commit and the branch. When a worktree's own record does not vouch for the current tree, or
it has none, `test-status` and the base-advance transfer at both the PR and Stop gates ask the
store, using at most three candidates:
the newest run for the exact tree, for the commit checked out, and for the branch. Each is judged
by the same judgeable tree diff as before. The newest run that met the tree decides it, so a red
re-run supersedes an earlier green one. A worktree's own red or degraded record for this tree (or
one naming no tree) competes too, so only a strictly newer run can vouch past it. A red run on
another branch is about a different tree, so switching away from half-fixed work to a branch with
a green run re-runs nothing. A record that cannot be validated, or a store holding a fact from a
newer plugin, lets nothing through. The store is only a fallback: a worktree's own green record
for its tree still answers first. A restamp records no fact, because it measured nothing.
`evidence list --kind test-run` shows each run's tree, counts, source, duration and a `DEGRADED` marker.

The coverage gates' verdict cache used to key on a hash of the whole store, so every such append
would have made the next gate recompute from cold. It now keys on `coverage_fingerprint`, which
leaves out the kinds the coverage verdict never reads (`test-run`, `guard-refusal`). As a side
effect, a guard firing no longer evicts the cache either.

## 2026-09-23: test evidence names the failing tests, not just the count

<!-- prawduct: type=fix | scope=failing-test-ids | release=v3.6.1 -->

`test-evidence record` wrote `failed: 2` and nothing else, and deleted the junit report it had
parsed, so `test-status` exited 1 with no names and finding the two failures cost a second
full-suite run (#792). The recorder now keeps the failing ids from that report as `failed_tests`,
written `classname::name` from junit's own attributes rather than any one runner's id, in report
order, up to 100. The `recorded:` line and the failing-record reason name the first ten, then count
the names the record holds but did not print apart from the failures it holds no name for. That reason is what `test-status`, the PR-gate transfer and the PR review payload
print, so all three name the failures. A restamp carries the names forward with the counts they
explain. The key is absent when no ids were visible (a pass, `--from-counts`, a summary-only suite),
and `failed` stays the count of record. It is kept out of the evidence schema on purpose: it is only
ever printed, so a malformed value is ignored rather than allowed to turn a passing record stale.

## 2026-09-22: the PR reviewer's context claim now names path-scoped rules

<!-- prawduct: type=fix | scope=pr-reviewer-path-scoped-rules | release=v3.6.1 -->

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

<!-- prawduct: type=fix | scope=learnings-migrate-local | release=v3.6.1 -->

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

<!-- prawduct: type=chore | scope=dev-track-bump-3.6.1-dev.6 | release=v3.6.1 -->

The dev track's version moves to `3.6.1-dev.6` in the four carriers (`plugin/VERSION`,
`plugin.json`, `pyproject.toml`, the open `plugin/CHANGELOG.md` heading), so repos on the develop
track pick up `reviewer-prompt-file-list`, which merged after `-dev.5` was opened. The version
string is the plugin cache key; a repo that already resolved the `3.6.1-dev.5` cache would
otherwise never see it. #885 waits on a consumer running a build that includes it.

**No consumer notes were owed.** `reviewer-prompt-file-list` already carries its entry in the open
`plugin/CHANGELOG.md` section.

## 2026-09-22: Coordinator reviewers read their file sets from the manifest, not the prompt

<!-- prawduct: type=perf | scope=reviewer-prompt-file-list | release=v3.6.1 -->

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

<!-- prawduct: type=chore | scope=dev-track-bump-3.6.1-dev.5 | release=v3.6.1 -->

The dev track's version moves to `3.6.1-dev.5` in the four carriers (`plugin/VERSION`,
`plugin.json`, `pyproject.toml`, the open `plugin/CHANGELOG.md` heading), so repos on the develop
track pick up `measured-round-price`, which merged after `-dev.4` was opened. The version string is
the plugin cache key; a repo that already resolved the `3.6.1-dev.4` cache would otherwise never see
it.

**No consumer notes were owed.** `measured-round-price` already carries its entry in the open
`plugin/CHANGELOG.md` section.

## 2026-09-22: A round is priced from the clock, not from the reviewer's estimate

<!-- prawduct: type=fix | scope=measured-round-price | release=v3.6.1 -->

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

<!-- prawduct: type=chore | scope=dev-track-bump-3.6.1-dev.4 | release=v3.6.1 -->

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

<!-- prawduct: type=docs | scope=far-behind-branch-guidance | release=v3.6.1 -->

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
