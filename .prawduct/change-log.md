# Change Log — Prawduct Framework

<!-- Append new entries at the top. Each entry is a ## section.
     Historical entries (pre-2026-03-22) are in project-state.yaml under change_log_history. -->

<!-- Older entries live in .prawduct/change-log-archive/YYYY-MM.md, moved there verbatim by `prawduct-hook archive-change-log`. -->

## 2026-09-22: A fix made after a clean review rides the next review instead of buying a round

<!-- prawduct: type=feature | scope=review-interval-extension -->

**Toward #167.** Across the fleet, 150 of 242 `verify-resolutions` rounds between 2026-09-13 and
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

**Nothing tells the builder to buy that round any more.** When the branch's plan still owes a later
review (two or more unticked chunks; a lone unticked chunk is ambiguous and keeps today's answers)
and a covered frontier exists:

- `infer-critic-mode` answers `deferred` instead of `verify-resolutions` for a non-blocking fix, and
  instead of `cumulative` for a clean tree mid-plan.
- The Stop gate warns (`deferred-boundary-review`) instead of blocking.
- The review close's NEXT-ACTION leads with the later review, replacing the cost of a round, the
  "third route" and the price.
- `cost-of-commit` answers `free` and says which review will cover the commit (`rides_next_review`
  in `--json`).
- The widened-verify fallback recommends `final` over `cumulative` when a frontier sits behind the
  committed work.

Blockers are never deferred, and the PR gate is unchanged.

**Docs.** `review-cycle.md`, the Critic `SKILL.md` and `review-protocol.md` describe the new interval
in place. The reviewer-payload readings went down, and their ceilings were ratcheted with them.

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
