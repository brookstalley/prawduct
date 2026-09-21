# Change Log — Prawduct Framework

<!-- Append new entries at the top. Each entry is a ## section.
     Historical entries (pre-2026-03-22) are in project-state.yaml under change_log_history. -->

<!-- Older entries live in .prawduct/change-log-archive/YYYY-MM.md, moved there verbatim by `prawduct-hook archive-change-log`. -->

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
identically. The `--apply` output now names the staging remedy; the dry run does not, because it
moved nothing. It rides this commit rather than one of its own: this commit is judgeable and owes a
review anyway, so the rider buys no round.

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

## 2026-09-19: The review loop converges — one finding per class, and the cost lead stops saying free

<!-- prawduct: type=feat | scope=review-convergence | release=v3.6.0 -->

The convergence half of #724. Where `review-cost-decision` made the cost of a round VISIBLE, this
makes two of them not happen — and withdraws a third that would have made things worse.

**#640 — when a written rule has no enforcer, the finding is the rule, once.** A reviewer files ONE
finding naming the rule and what would mechanize it, at the severity an instance would have
carried, opening it with `rule-unenforced:` — in the field each copy's own store persists, which is
NOT the same field on both: a Critic partial's `name` becomes the fact's `title`, while a PR
finding persists `summary` and carries no title. Two stores, two field names, one token — so the
yield stays countable from either side. Substitution, never suppression: the
report still happens and still carries its weight; it names the cause that can end the class rather
than one member of it. A class re-filed per instance buys a round every branch, forever. The item
was CLOSED while its fix sat unmerged for nine days on a branch 281 commits behind — re-applied
here rather than merged, because the branch predates the learnings-v2 migration and its
`learnings.md` edits have no destination.

**#851 — the cost lead stops saying "free" when it is not.** Filed the same day from a live
reproduction in this scope's own predecessor: `commit_cost` asks only whether paths are judgeable
and cannot know a review just anchored on this tree. Once one has, the commit the lead would call
free is already covered and the next edit opens a NEW delta, judgeable or not. It told the builder
a batch was free and it bought a full round.

**A dispatched reviewer's Learnings Cross-Check now scopes to the REVIEW interval, not the
session.** Found by the cumulative that reviewed this branch. `learnings-files --for-diff` computed
a reviewer's read list from `learnings_change_set`, which judges *this session* — and for a
`cumulative` over already-committed work that span is EMPTY, because the session began after the
commits, so a clean tree diffs to nothing. Measured here: the cumulative reviewing a five-commit
branch was handed `core.md` alone, at exit 0, indistinguishable from "no area file applies", while
the interval touched the areas owned by `reviews.md`, `hook-surface.md`, `tests.md` and
`authoring.md`. The Cross-Check is a `final`/`cumulative`-only pass with no other owner, so it read
one file on exactly the reviews it exists for. New `gates.learnings_review_change_set` takes the
interval from the **dispatch manifest** — the artifact that already records what a review spans,
written by code at `critic-begin` — so nothing new is declared or maintained: no flag, no field, no
second copy of the span. `learnings_change_set` is unchanged and still owns the Stop nudge; the two
ask different questions, which is why they are two functions and not one. **Consumer-visible:** a
`final`/`cumulative` reviewer that previously received `core.md` alone now receives every area file
the interval touches.

**#167 was built and then WITHDRAWN — no exit 5 ships.** A refusal for a verify pass anchored on a
clean verify pass was implemented to `documentation/issues/167-design.md` D1–D5, reviewed, and
reverted in full. Two independent reviewers converged on the defect and the numbers settle it: the
refusal fires only on a non-empty judgeable delta, and no `guard-refusal` fact composes a coverage
edge, so every firing left `check-cumulative-critic` reporting `uncovered` — prescribing the very
pass that had just been refused. Priced over 1,047 recorded reviews, that traded a 300s median
`verify-resolutions` for a 720s median `cumulative`: the control more than doubled the cost in the
case it existed to cheapen. The general lesson is recorded in `core.md` under "A refusal hands
the caller a REPLACEMENT route, and it is checked by its PROPERTIES, never its name" — a refusal is
priced against the route it FORCES, not the one it declines — and the
sharper half is about evidence strength: `diagnose_fix_churn` is file-level by its own docstring
(it rules out work in a file the review never saw, not new work written into one it named), which
is advisory strength, while a refusal is authority. #167 stays open. Refusing a round needs
content-level evidence that the delta is churn; until something supplies that, the existing
advisory NOTE plus a free `disposition --accept` is the right strength for what is known.

**A mutation sweep returned a survivor that was a finding about the code rather than the tests**,
recorded because the shape recurs: a comparison inlined where only a pure renderer was under test
(extracted, so the three survivors in it could be killed). The remaining known limit is stated
rather than implied: the AST wiring check proves a call is PRESENT, not reachable.

## 2026-09-19: The fix/accept decision is priced, and the two over-fixing rules are bounded

<!-- prawduct: type=feat | scope=review-cost-decision | release=v3.6.0 -->

**The measured problem.** `verify-resolutions` is 58% of all review volume at the worst yield of
any mode — 26.3 minutes per blocking finding against `chunk`'s 10.2 — and **41 of the 83 scopes
with two or more verify rounds found ZERO blocking findings across all of them**. Half the
repeat-verify population is pure cost. Re-derive with `prawduct-hook review-stats` and the scan in
`.prawduct/artifacts/review-cost-investigation-2026-09-19.md` §6; the program is #724, and this
scope lands #831 and #833 from it.

**#831 — the close answers the cost question instead of delegating it.** The fix/accept call was
evaluative ("is this worth fixing?"), which is unanswerable with a complete remedy already in hand
because it always reads yes. The mechanical replacement is *"am I already making a judgeable
commit?"* — and both inputs were already computed and neither reached the builder:
`coverage.commit_cost` prices the working tree, `telemetry.round_price` prices a round, and the
message told the builder to go run the first himself. `critic_consolidate.cost_lead` now renders
the verdict and its recommendation, and the two zero-blocking arms that carry a fix decision lead
with it. The blocking arm and the empty close deliberately do not: a cost verdict where there is no
fix decision is a number with nothing attached, and on the blocking arm it would read as a reason
to weigh not fixing a blocker. No digit is restated — `format_round_price` keeps sole ownership of
what a round costs, and a degraded git read renders its reason rather than a reassuring default.

**#833 — the two over-fixing rules carry a severity bound, at every carrier.** "There is no
pre-existing exception" and "deep context on a small problem is a FIX signal" are both correct
about blockers and actively harmful about notes: unbounded, they are the pull that #831 prices.
Each now states that the obligation to FIX is bounded to BLOCKING, and that below it a recorded
accept is the complete discharge rather than the lesser half of the sentence.

**[DECISION: the bound reaches all ten carriers, consumer-facing text included | the four-surface
option — the Critic protocol files plus `core.md` — was offered against it and declined, because a
rule stated with its bound in the reviewer's file and without it in the always-injected digest, in
Principle 22, and in the `CLAUDE.md` anchor every governed product carries is the drift this scope
exists to end | owner-directed 2026-09-19, and the owner may still narrow it]**. The witness is not
this amendment: #833 was filed by the owner on 2026-09-18 carrying the ledger measurement above,
and `core.md` requires an amended norm's authority to live somewhere the amendment is not.

**What the full reach cost, and the two regressions it surfaced.** `anchor_repair` grades a repo
by matching its `CLAUDE.md` anchor byte for byte, so changing the current anchor strands whatever
was current before it. **The stranded cohort is the develop track, not v3.5.0** — v3.5.0 ships
`ANCHOR_V3`, which was already archived. `ANCHOR_V4` archives the develop anchor no release tag
carries, and it is the entry that matters most: those bytes hold both `SUBSTANCE` probes, so an
unarchived V4 grades silently **`ok`** rather than `stale-modified`, reporting the cohort healthy
and never offering the repair. (V1–V3 predate `stage-keyed`, so an unarchived one of those DOES
refuse loudly.) Separately, two edits to `ANCHOR_V1`/`ANCHOR_V3` were made and reverted: that tuple
is the bytes sitting in already-onboarded repos, and rewriting it breaks repair for exactly the
cohorts it serves. `test_the_archive_covers_every_anchor_prawduct_ever_shipped` caught that, and
the cumulative review caught the warrant this paragraph originally recorded for the first.

**Budgets: a declared raise, and a reserve deliberately not spent.** Four per-file readings and
both injected-session aggregates moved, each ratcheted in the same commit. This is a declared raise
with its reason, not a trim — the bound is a new obligation, not a restatement, so there was no
duplication to pay from, and funding it by cutting someone else's clause is the failure mode that
loses whichever clause is least defended. The digest's 500-character reserve, held for the next
framework-wide default, is untouched: its sentence is written at that surface's compressed register
(9,497 of 9,500).

**A clean verify close now says WHEN it was true, at both carriers.** The cumulative review found
that a clause measured from the live working tree was being frozen into `.critic-findings.json` and
replayed by the briefing in later sessions — so a review run against a dirty tree told a future
session "a fix buys no extra round" after the builder had already committed, inverting the advice at
the moment it is acted on. Closed as a class rather than at the site that surfaced it: the other
live-state clause is `span_clause`'s covered arm, and **that one changes a sentence every governed
product reads.** It now reads *"The BRANCH was covered too, at the HEAD this review saw … work you
had not committed yet is not in that span. Re-derive with `prawduct-hook check-cumulative-critic`
if the branch has moved since."* Past tense plus a re-derivation, in place of a present-tense claim
about a branch that may have moved. Its negative arms already sent the reader to the gate, so only
the arm making a durable positive claim changed — a stale "not covered" costs a gate call the reader
was told to make anyway, while a stale "covered" reads as clearance for work no review has seen.

**#850 — the reviewer's payload gets an owner, and the item's own number was wrong.** Every
governance prose file carries a budget and every budget is green; nothing priced the total, and the
total is what a reviewer pays. The item quoted ~26k tokens read before a line of diff. The dispatch
path falsifies it: `SKILL.md` sends a `chunk`/`verify-resolutions` reviewer to `goals-1-3.md` and
tells it to read *"nothing else"*, so the cheap protocol route is a fraction of the full one. That
changes the control rather than just the arithmetic — `verify-resolutions` is 58% of review volume
and pays the SMALL payload, so one ceiling over the union would price what nobody loads and let the
cheap route double with nothing red. `tests/test_reviewer_payload_budget.py` ships **three**
ceilings keyed by **route**, not by stage: the cumulative review found that `review-cycle.md` puts
`final` in the INNER stage while routing it to the full protocol, so a stage-keyed sum priced it at
a third of what it loads — and that single-pass modes dispatch no subagent, so charging them the
agent definition priced a file nobody reads. The three routes are the single-pass fork on each
protocol and one dispatched reviewer, whose system prompt replaces `SKILL.md`. A relational pin
keeps the cheap route under half the full one — the property the `goals-1-3.md` split exists for,
which survives every number moving. Member lists are derived from `SKILL.md`'s routing prose, not
listed here, so a protocol file cannot join the dispatch without joining a sum; the classes that
derivation cannot see are enumerated in the module's own docstring rather than left implied.
Re-derive the readings with `python3 -m pytest tests/test_reviewer_payload_budget.py` — they are in
the module, dated, and they moved once already inside this same bundle. Per the NFR
norm's requirement that a new control name its expected yield: this refuses an undeclared payload
raise and shrinks nothing today; if a year passes with no reading moved and no raise declared, it
fired zero times and should be retired rather than defended.

**The bound is enforced, not remembered.** `tests/test_severity_bounded_rules.py` walks the tree
for either rule and asserts every carrier states its bound — including carriers added later, which
a hand-maintained list cannot see. It carries a positive control, and five mutations against the
real corpus were run to prove it discriminates: the first cut bound the assertion to the blank-line
block, so a neighbouring bullet's `**BLOCKING**` satisfied the check for a whole list and two true
reversions survived green.

## 2026-09-19: three files the freshness gate called untestable, and the clause that made it moot

<!-- prawduct: type=fix | scope=critic-dispatch-clock | release=v3.6.0 -->

**`suite_coupled_prefixes` gains three named files, each read by a test that anchors on the real
repo.** `.prawduct/artifacts/data-model.md` (`TestTheMarkerNormKeepsItsReason`),
`.prawduct/operator-verification.md` (`test_operator_verification`'s `LIVE_QUEUE`), and
`.claude/rules/learnings/core.md` (`TestAgainstTheRealCorpus`, which asserts distinct rules get
distinct ids, so a colliding heading turns the suite red). Named files rather than
`.prawduct/artifacts/`, which is the cost argument the build-plan prefix beside them already makes
and which still holds. The learnings entry carries a stated cost: reflections write to `core.md`,
so adding a rule there now marks evidence stale.

**The learnings entry was a DIRECTORY for one commit, and review caught it.** `TestAgainstTheRealCorpus`
reads `RULES_DIR_REL / CORE_NAME` and no real-repo test reads an area file, so the directory form
bought a suite re-run on every area-file reflection write that no test outcome depends on — the
exact tax the same commit's own control assertion forbids two entries above, whose message reads
*"Name the file, not its parent."* The guard could not see it: its registry key IS `core.md`, so
narrowing leaves all nine cases green. A guard pins what it was told to pin, and the thing it was
told is the thing worth reviewing.

**`.prawduct/change-log.md` is deliberately NOT added.** It is read by a real-repo test too, and its
exclusion is a priced decision pinned by `test_the_held_out_bookkeeping_files_are_recorded_as_a_residual`.
Flipping it is a deliberate edit there with its own reason, not a line quietly added to a
declaration — so the new guard asserts it stays out, in the file where someone fixing a freshness
miss will be standing.

**The guard is mutation-verified, survivor included.** Six mutants: dropping each of the three
entries turns exactly its own parametrized case red; widening the declaration to `.prawduct/` turns
two red (the control artifact and the held-out change log); emptying it turns four red; and adding
an inert prefix leaves all nine green. That last one is the point — a sweep where every mutant dies
is a claim about the harness, not the subject, so the guard is shown to discriminate rather than to
fail on any edit at all. The assertions ask `affects_test_outcome` rather than grepping the YAML,
and a reachability case refuses an empty declaration or an empty registry.

**What this does NOT fix, measured rather than assumed.** It would not have caught the failure that
prompted it. `tests_are_current` is a disjunction and its first clause — evidence written during
this session — returns `current` without ever examining the tree. Measured on the live tree with the
new coupling in place: clause 2 answers `False, 2 suite-coupled path(s) changed since the run`, and
the gate still answers `True, evidence from this session`. A suite run, an edit after it, and a push
inside one session is therefore invisible to the gate at any setting of this declaration. This entry
closes the *predates-session* path — the one that catches an inherited red at a base sync, which is
how this branch found `develop` red at `4537d604` — and names the other as open. Making clause 2
conjunctive would close it, and that is a deliberate reversal of the recorded relax-only decision
(the clause is documented as *structurally incapable of a false stale*, the failure class that
retired the `fingerprint` and `git_sha` mechanisms), so it is the owner's to take, not a fix to
slip in beside this one.
