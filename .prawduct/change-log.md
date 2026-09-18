# Change Log — Prawduct Framework

<!-- Append new entries at the top. Each entry is a ## section.
     Historical entries (pre-2026-03-22) are in project-state.yaml under change_log_history. -->

<!-- Older entries live in .prawduct/change-log-archive/YYYY-MM.md, moved there verbatim by `prawduct-hook archive-change-log`. -->

## 2026-09-18: The PR reviewer reads one payload, reviews what it actually catches, and is timed

<!-- prawduct: type=feat | scope=pr-review-payload -->

**Two chunks, one loop: build the instrument, then change the thing it measures.** The PR review at
the boundary was ~115k tokens of context assembled over 13–18 sequential tool round-trips, against a
≤ 7-minute wall-clock target that had never been measured — `duration_seconds` was the reviewing
model's own estimate of its own runtime, 122 times running.

**Chunk 01 — the data plane.** `prawduct-hook pr-review-dispatch --begin` marks a dispatch and
`ledger-append` consumes the mark, so a review's duration becomes an interval two clocks in code
agree on rather than a recollection. The mark is tree-anchored (it records its `HEAD`; consumption
requires the same one) rather than age-thresholded, and only `review.pr` may consume it — a
`review.critic` append that cleared it would silently delete a concurrent PR review's measurement,
which is exactly the timing Chunk 02 introduces. `prawduct-hook pr-review-payload` assembles the
reviewer's whole context in one deterministic pass — base, commits, diffstat, work description, the
`test-status` verdict, the build plan's `## Status` boxes, the change-log entry, and every backlog
id the commits or that entry cite, already resolved. It fails **per section**, and every degraded
section names the check it leaves unanswered, because a silent empty section reads as "checked,
nothing found". `review-stats --json` went to schema 6 for the measured/self-reported split, and the
dispatch-interval predicate — including its 6-hour plausibility bound — now has one home
(`review_dispatch.measured_interval_seconds`) that all three readers call.

**The measurement toolchain ships with it**, and it is roughly a fifth of this bundle rather than a
footnote. `tools/pr-review-yield.py` is **new**: it reads the ledger's `review.pr` events and
reports PR-review duration, findings per review and yield by goal and severity, splitting measured
rows from self-reported ones rather than pooling them. `tools/measure-consumer-overhead.py` gains a
`pr_clock_*` trio so the same split is visible in a consumer repo's history. Both are what make the
before/after in `nonfunctional-requirements.md` § Performance re-derivable from a command instead of
quotable from prose — the tools are the deliverable, not the figures.

**Chunk 02 — the protocol.** The reviewer's six numbered activation reads collapse to three: the
payload, the diff, and the artifacts the diff sends it to. The learnings read is **deleted** — not
because the corpus arrives another way, but because the goal consuming it returned **1 finding in
122 reviews** and `review-protocol.md`'s own Learnings Cross-Check assigns that scan to the
`final`/`cumulative` Critic, so the reviewer was carrying a corpus it was forbidden to use. The
markdown `## PR Review` block and the `### PR Draft` go too: the caller reads the JSON and re-drafts
the description at Step 5, so both were outputs with no consumer.

**The four goals are re-pointed, and that is a recorded decision rather than documentation
freshness.** They were written for product code; across 279 findings the subject is governance
bookkeeping — 48% change-log coherence, 25% build-plan status and dangling pointers, 15% backlog
reconciliation, 10% tag keys, against 0.7% on the debug-code and stray-file bullets the goals led
with. `.prawduct/` is non-judgeable by the coverage algebra, so no Critic layer reads it and this
reviewer is its only reader. Goals 2 and 3 are renamed to *The Record Matches What Ships* and
*Governance Bookkeeping Is Coherent*; every bullet survives, the merge-hygiene set now carrying its
measured rarity beside it.

**A named agent, and the rule it retires.** `plugin/agents/pr-reviewer.md` ships with a scoped tool
allow-list and `omitClaudeMd: true` — measured against Claude Code 2.1.277 before it was written: an
agent carrying the field reported `CLAUDE.md`, `.claude/rules/learnings/core.md` and `MEMORY.md` all
absent, while the identical agent without it quoted a `core.md` heading verbatim. That is ~108KB of
prose the reviewer no longer receives. The payload grant names `pr-review-payload` **exactly**,
because a Bash grant is a prefix match and the sibling `pr-review-dispatch` writes. A `core.md` rule
forbidding named tool-restricted reviewer agents is **superseded** (owner-confirmed): its warrant
was that the frontmatter cannot express `Bash(...)` granularity, and the tool-level bound is real —
an agent granted no `Bash` has no Bash tool at all. What replaces it is the half that survives: a
`Bash(pattern)` grant is *declared*, not verified-enforcing, so scope by which tools exist and never
call a pattern structural. Whether patterns narrow within an exposed tool could not be measured
here — every probe ran under a `permissions.defaultMode: dontAsk` that no flag overrode — and that
limit is written down rather than rounded off.

**And the two boundary reviews now run concurrently (#678)**, which `nonfunctional-requirements.md`
§ Performance has required all along and `pr/SKILL.md` did not do. Neither consumes the other's
verdict; the one real cost — a blocking cumulative spends the concurrent PR review — is stated in
the step rather than discovered.

**Measured, not projected.** The before-readings and the commands that re-derive them are in
`nonfunctional-requirements.md` § Performance: 420s median over 122 reviews, **0 measured / 122
self-reported**, and 14.1 min/review on a consumer repo with zero clock rows. The after-reading is
owed at this bundle's own PR — the first dispatch that can produce a `measured` row — and is
recorded there beside them, including if it misses.

**A defect surfaced, not fixed:** `nonfunctional-requirements.md`'s 2026-09-16 ruling keeping the
`pr-scoped` review mode graded a control that had been collapsed into `pr` two months earlier. The
ruling stands and is annotated with what it actually decided; amending a norm to match the tree is
the laundering tell.

## 2026-09-17: Step 1 names the recorder; develop opens 3.5.1-dev.1 so consumers pick up review-stages

<!-- prawduct: type=fix | scope=pr-step1-recorder -->

**Small work, no build plan** — two prose surfaces, one machine-read grant, a version bump and the
consumer note the bump makes load-bearing. The grant is the surface easiest to miss in a change
described as prose: naming a command in `SKILL.md` is inert until `allowed-tools` permits it, so
`Bash(prawduct-hook test-evidence record*)` joins the pr skill's no-prompt list. It permits running
whatever the repo's own `project-state.yaml` declares as `test_command:` — the same checked-in
trust boundary `building.md` already relies on, stated here because a no-prompt list should never
grow silently. Found by dogfooding: creating PR #821 cost two full suite runs instead of one.

**The defect, and it was paid in wall clock rather than correctness.** `/prawduct:pr` Step 1 told
the caller to run the suite and then *"write fresh evidence so the next caller can skip it"* — and
named no command. Following it literally means running the declared suite by hand and asking
`test-evidence record` to ingest the counts afterwards. With a `test_command:` declared that is
refused (the runner emits JUnit, so hand-typed counts are the weakest posture available), and a
hand-run emits no report to ingest instead, because `{junit_xml}` is the hook's to substitute — so
the only way forward is a second full suite run. Step 1 now says to run it AS the recorder:
`prawduct-hook test-evidence record` runs the suite and writes the record in one step — the
declared `test_command` where the repo has one, else a pytest fallback, which is the DEFAULT
consumer state because the template ships the key commented out. That fallback is why the
sentence names the ingest routes too: a non-Python product declares the command or ingests an
existing run. `test-status` still leads the paragraph, because running nothing at
all is the better outcome and that exit code is what licenses it.

**The same claim had a second carrier, and it is the one that actually misrouted the caller.** The
`--from-counts` refusal said *"run each once and ingest the report(s) with `--from-junit`"* — advice
for someone already holding a report, and useless to someone who has not run yet, which is who hits
it. It now names both ways out, and its comment and the `cmd_test_evidence` docstring say why both
are named rather than one. Enumerating carriers first found that one: `building.md` and
`delegation.md` were already correct.

**The enumeration still stopped short, and the correction is the more useful record.** It swept
sibling FILES and missed a third carrier inside the file being edited — `SKILL.md`'s own
`## Important` checklist, which restated the procedure and named only `test-status`. An independent
review found it. The remedy is a construction rather than a third copy: that bullet now points at
Step 1 and says why it deliberately does not restate it, so there is one home. The general form is
that a cross-file sweep reads as exhaustive precisely because it crossed files, and the carrier
sitting a hundred lines below your own edit is the one it cannot see.

**Guards.** `TestStepOneNamesTheRecorder` bounds itself to the Step 1 paragraph rather than the file
(`SKILL.md` names `test-evidence` elsewhere, so a file-wide check passes with the instruction
silent), asserts the recorder is named, and separately asserts `test-status` still precedes it — the
second with its precondition stated as an assert, so it cannot report the first's defect as its own.
`test_refusal_names_the_path_for_a_caller_who_has_not_run_yet` pins the message. All three
red-verified against the exact pre-fix text; the ordering guard additionally red-verified against a
reordering, since absence and disorder are different failures.

**Scope deliberately NOT taken.** Step 1's sync-before-suite ordering is load-bearing and unchanged —
running the suite before the base sync denies the base-advance coverage transfer, which line 51
argues and line 53 closes with. Today's re-run was *correct*: the sync moved `documentation/`, which
this repo declares in `suite_coupled_prefixes`. The freshness gate and that declaration are untouched.

**`develop` opens `3.5.1-dev.1`.** `version` is the plugin cache key, so consumers pinned to the
develop ref pick up the merged review-stages work only on a new key. Four files, per the release
process: the manifest, `plugin/VERSION`, `pyproject.toml`, and the open `plugin/CHANGELOG.md`
heading, which `test_changelog_has_current_version_entry` keys by the exact manifest string.
`-dev.N` is the only prerelease form permitted — `banner.version_tuple` matches
`dev(?:\.(\d+))?` and returns the malformed sentinel otherwise, which sorts below every real
version and shows no banner at all; `3.5.1-dev2` was verified red against `test_version_is_semver`
before the correct string was written.

**The consumer note that bump makes load-bearing.** Shipping a new cache key means consumers receive
review-stages, which reverses two statements v3.2.2 made them: *"no repo is reviewed less than
before"* and *"beneath them the old 5-file rule stands untouched"*. `plugin/CHANGELOG.md` now quotes
both and says what replaced them, carries the fleet measurement behind the retirement with its
stated limit (no per-review yield advantage for the third reviewer; how many of the 48 blocking
findings one reviewer would have missed is not measurable from the record), and names the short-plan
deferral and the `risk_surfaces:` ask. This closes the PR review's note 3 on PR #821.

## 2026-09-17: review stages — rigor is stage-keyed; the inner loop blocks on eight things; unsure defaults cheap

<!-- prawduct: type=feat | scope=review-stages -->

The owner's 2026-09-17 trade (wall-clock for a bounded miss-rate increase; plan
`build-plan-review-stages.md`, drawn from `review-proportionality-assessment-2026-09-17.md`), built
as six chunks. **Chunk 01:** the norm — `nonfunctional-requirements.md` § Direction,
*Review rigor is stage-keyed*: the inner stage (`chunk`, `final`, `verify-resolutions`) blocks only on
the inner BLOCKING set and reports everything else as an observation; the boundary (`cumulative`, the
PR review) runs the full table and is never inferred away; both failure directions are defects.
Principle 11 gains one sentence (the inner loop proves the change, the boundary proves the bundle).
Both ratified the same day. The entry names the sentences it retires and a strict-xfail grep pin held
them red until Chunk 03. **Chunk 02:** `stage` derived once (`critic_consolidate.stage_of`) at
`critic-begin`, written on the manifest with `judgeable_files`, `chunk_type` and a code-rendered
`signals` line, carried to the review fact, the findings cache, the `review.critic` ledger event and
`review-stats --json` (`by_stage`, report schema 5); the inner BLOCKING set stated in the norm's own
sentence on `goals-1-3.md`, `review-protocol.md`, `review-cycle.md` and the verify directive, pinned
identical; consolidation accepts `observations` from any inner-stage dispatch and refuses them at the
boundary. **Chunk 03:** the defaults flip. `infer_mode` rule 4 answers `chunk` when nothing else
fires — the inner-stage review of the uncommitted interval — and `cumulative` on a clean tree with a
bundle; `final` is never a default (rule 3's size and last-chunk signals still infer it). The
`SKILL.md` fall-through and failure path follow (`infer-failed-fallback-chunk`), and its per-mode
scope line states the inner-set rule for every inner mode, not `verify-resolutions` alone.
`_derive_roster` loses the file-count fallback (coordinator at 5+ changed files for a repo with no
`risk_surfaces:`): an undeclared repo runs the same two escalators as a declared one — a matched
surface at any size, or 12+ judgeable files — and what declaring buys is the paths it names.
Measured before retiring, fleet-wide over 2026-08-01 → 09-17 (`python3
tests/spikes/fallback_roster_yield.py`; six undeclared product repos, evidence stores deduplicated by
clone): the fallback alone sent 87 `final`/`cumulative` reviews to three reviewers, and those reviews
carried 48 blocking findings (0.55 per review) against 0.78 per review for the 18 single-pass reviews
beside them. **That corrects the plan's inherited claim** that no blocking finding was attributable to
the fallback in the window — the assessment's survey had not run the query. The record shows no
per-review yield advantage for the third reviewer; how many of the 48 one reviewer would have missed
is not measurable from the store, and the retirement stands on the owner's recorded decision, not on
a zero. The prose sweep by grep: `review-cycle.md`'s canonical statement is now *default when unsure*
(the inner-stage review of whatever interval exists) and its risk-surface paragraph no longer
promises an undeclared repo is "never reviewed less than before"; `planning.md` stops calling
under-declaring Type safe and its "Fail-safe default" paragraph is "Default when unsure";
`discovery.md` § Surface Risk Surfaces promises size-independence on the named paths and nothing
else; `building.md`'s Modes pointer, the build-plan and project-state templates, the
`critic_mode.py` and `infer-critic-mode` docstrings and `risk.py`'s declaration predicate follow. The
xfail pin flips to a plain assertion. The yield-floor sentence (a full round returns 13–18 findings
regardless of round, diagnosis fix #6) was confirmed present in `review-cycle.md` ("Yield does not
decay"), so nothing was added for it. Contracts renegotiated in the open: the per-mode scope pin asks
the stage-keyed property instead of the fragment "BLOCKING only"; the roster tests that pinned the
fallback now pin its absence (five files, the count it keyed on, is single-pass) and the two
escalators that survive; token readings — SKILL +7 raised by declaration, review-cycle net 0 (its
chunk review found the `final` row's "any time the right answer is unclear", the retired rule reworded,
and the cut paid for the new canonical statement), building −6 and discovery −34 ratcheted, planning
+22 recorded. **Chunk 04:** a short plan owes one boundary review, not one per chunk (#292). A
plan of at most three chunks, declaring no `Critic mode:` on any chunk, whose branch has changed no
risk-surface path (the tier predicate — declared `risk_surfaces:` when present, else the derived
defaults plus contract paths — over the paths committed since the merge-base and in the working
tree) and is not the base branch itself, defers its per-chunk reviews: `infer_mode` answers a fifth,
output-only token `deferred` on such a plan whenever code is in flight (between rules 2 and 3, so a
fix-in-progress still gets `verify-resolutions` and a committed bundle still gets `cumulative`), the
skill dispatches nothing on it and reports the rationale, and the Stop gate's Critic check on a
non-final chunk emits a WARNING naming the deferred boundary review instead of blocking — delivered
as a JSON `systemMessage` plus `additionalContext` on stdout, because at exit 0 the harness logs
stderr and delivers it to no one. On the last chunk the gate blocks as ever and says the boundary
review is that chunk's review (`Type: cumulative-final` sequencing without the declaration); a
`blocked` verdict or an unreadable store still blocks on any chunk, and `check-cumulative-critic` is
untouched — one `cumulative` fact spanning merge-base…HEAD passes it alone. Every condition fails
closed (an unreadable plan, an unresolvable base, a detached HEAD, a failed git listing, an
unparseable `risk_surfaces:` all leave per-chunk review standing), and `buildplan_refs` exports the
roster's chunk ids (`status_chunk_ids`) so the opt-out scan reads Status through its one owner. The
predicate is one function read by both consumers; `tests/test_short_plan_deferral.py` carries the
guardrail #292 made load-bearing — a four-chunk plan, a risk-surface plan, an opted-out plan and
base-branch work all still infer `chunk` and still block — with every guard mutation-verified red.
`review-cycle.md` (the required-review row, the precedence list, the cumulative-final paragraph),
`SKILL.md` (the `deferred` bullet) and `planning.md` (the "Short plan" heuristic) say it; SKILL
3484 → 3615 and review-cycle 10864 → 11090 raised by declaration, planning 5597 → 5704 recorded.
Three inference fixtures widened from three chunks to four, one of them a renegotiated contract
(the last chunk of a short plan is no longer a rule-3 `final`). **Chunk 05:** the inner loop has a
verification ceiling of its own, and the suite runs at Verify and at the boundary. `building.md`'s
baseline leads with the evidence check (`test-status` current, else one run of the declared suite)
instead of prescribing a suite run; a build-cycle paragraph states the ceiling once for the builder
and the delegate — the project's `Inner-loop verification` row where it has one, else the tests for
the files touched — and the delegation section keeps its mechanics and drops the duplicated why
(building 4780 → 4910, the remainder raised by declaration because this file is the ceiling's only
home). The preferences template gains the `Inner-loop verification` row beside `Delegate
verification`, unset, in the product's own words, and the norm-table sentence names it as its own
norm row; the test-specifications template says the testing floor is a product floor checked at the
boundary, never a per-chunk bar; the build-plan template's example acceptance criterion reads "the
declared suite passes" and a pin refuses a runner name on any acceptance line (the scaffolding
section that declares the suite is exempt by design). The `test-evidence record` directive keeps the
cheap half (name what would turn each test red; the three vacuous shapes) and the mutation-watch
rule moves to the PR skill's Step 2, before the one cumulative run — the run-per-claim cost belongs
at the boundary; `docs/discipline.md` row 1 follows it there, row 2 stays, and the header's channel
enumeration gains the skill step. Chunk 04's owed short-plan sentence lands as one pointer per
surface at `review-cycle.md`'s "When Review Is Required" row — the Critic-review step, the "Skipping
`final` mode" trap, the build-plan template's field reference and its `cumulative-final` comment
(which notes the example plan opts back in via `Critic mode:`) — with the conditions asserted absent
from both files. Built by a delegate in an isolated worktree under a three-file verification ceiling
and integrated by the coordinator. **Chunk 06:** the product-facing surfaces say it, and a product
is asked once where its risk lives. The session digest gains one hardest-rules bullet (rigor is
stage-keyed; inner-loop reviews block only on ships-broken; the boundary runs everything and is
never skipped; unsure defaults cheap), paid in place by cutting the size-scale parenthetical
`building.md` owns (9,361 → 9,422 stripped characters against the 10,000 spill wall). The scaffolded
anchor's Critic line carries the same sentence in product terms, and `anchor_repair.py` archives the
superseded text as a frozen literal beside V1 and V2 with a second substance probe (`stage-keyed`),
so an onboarded repo carrying the previous anchor grades `stale` and is repaired, a hand-edited one
lacking the sentence grades `stale-modified` and is told which sentence it lacks, and the detail is
derived from the missing rows rather than fixed. A new probe family (`lib/risk_surface_probes.py`)
fires once — one stable advisory id across repos and sessions — when a repo has product code and a
state file but no `risk_surfaces:` key, in the product's terms (where would a missed defect cost you
most?), landing on `discovery.md` § Surface Risk Surfaces; any declared key including `[]` is
silent (the opt-out, read through `risk.read_declared_surfaces`, never the non-empty predicate),
an unparseable key is the doctor row's finding rather than the ask's, and no judgeable work is
silent. `coverage-status` reports the same classification as a row outside the chain
(`risk_surfaces` in `--json`; doctor Check #20 grades `undeclared` and `unparseable` degraded with
the fix). Doctor Check #18 widens to the third preferences row — an unset third row is the
ordinary blank state, what excludes a row is shipping filled — and the Delegation Policy Flow
drafts and ratifies it as its own norm row. At integration: `planning.md`'s mode heuristic bullets
qualified to the short-plan condition, `risk.py`'s non-empty predicate docstring corrected to say
the ask does not read it, `api-contract.md` documents the new key, and the delegation-policy test
that Chunk 06 left red by construction (the template row it asserts is Chunk 05's) went green on
the merge. The bundle's `cumulative` review found one correctness edge in Chunk 04's Stop gate:
`last_chunk` was read from the working tree's ticks, so a chunk ticked and not yet committed at a
Stop read as the last chunk and blocked for a boundary review one chunk early — chunk N would
then owe a second one. It now reads the ticks committed at HEAD
(`buildplan_refs.committed_chunk_progress`, the same checkbox parser on the committed plan, never a
git-derived progress), falling back to the working tree only when the plan is not tracked; the
two-tree fixture and the Stop-gate case are pinned and mutation-verified. Both chunks were built
by delegates in isolated worktrees under named verification ceilings; the combined suite, the
reviews, and the records are the coordinator's.

## 2026-09-03: learnings v2 docs — the guides say what the code does; the discipline corpus has a home; the program ships

<!-- prawduct: type=feat | scope=learnings-v2-docs -->

Wave 3 of the learning-system v2 program (#744; plan `build-plan-learnings-v2-docs.md`, serial).
**Chunk 01 (R8, D2):** `methodology/reflection.md` rewritten to the four-route write path (episode /
product rule with its instance inline / upstream friction / portable discipline not written) with the
budget's payment rule and the lifecycle whose end state is a deletion; 5,003 → 2,780 tokens. The
standing-block specification moved verbatim to the new `methodology/session-hygiene.md` (2,811
tokens) with its own `/prawduct:methodology session-hygiene` topic at all four routing sites; every
pin that named `reflection.md` as the carrier repointed; the lifecycle and cross-reference pins
renegotiated to the rules directory; `docs/norms.md` stops naming `learnings.md`; the single-resolver
allowlist is at its end state (`learnings_migrate.py` and `prawduct-hook`, both `none`). **Chunk 02
(R10, R13):** one digest bullet — auto-memory holds no project state or product rules — raised both
injected ceilings by declaration (+33 each; 9,455 of 10,000 characters); `api-contract.md` records
`learnings-migrate` and `learnings-files`, the stable-tier footing of the latter, and the program's
contract change in one paragraph, and its inert-tier count is relational; review-cycle's ordering
rule states a rule unit from the writer (`rule_units`: a heading or a top-level bullet) and drops
the stale narrative-body clause (net -5). **Chunk 03 (R12):** `docs/discipline.md` — ten rows, seven
already homed; row 7 is a Goal 2 bullet in both protocol files (goals-1-3 and review-protocol raised by
declaration; the removal-is-repo-wide row re-homed on Goal 4's existing drift bullet after the
PR-boundary review found it re-owned that subject), row 1's clause extends `_GREEN_IS_EVIDENCE_DIRECTIVE`, row 9
is one sentence in the post-fix step; `tests/test_discipline_table.py` pins each row against its
surface and the two protocol files against each other. **Chunk 04:** the program's cumulative review
and the PR to `develop`; at the base sync one rule develop had added to the legacy `learnings.md` was ported into
`core.md` with its instance inline, and `learnings_budgets.core.md` was declared at 99 KB — just above the corpus, so the next addition pays — with its reason (the
migrated corpus is over the default by construction; the port, not new authoring, is what the raise covers). **Chunk 05:** the release (version framed for the owner; the three learnings
gate rows carry the release's own `since`).

Closes the program for #685 (the reflection gate), #347 (reflection.md's two stale limbs), #295 (the
memory triple-track converges on `.session-reflected` + the rules files), and Wave 2's #661 by
deletion; #343 gets its first entry (R12) and stays open for the mechanical-promotion half — its ruling's (a) read-at-query-time and (b) distinct-store halves stand as `docs/discipline.md` plus the surfaces it names, while (c)'s named reader `/prawduct:learnings` retired with the lookup model (audit §3.2); #304
stays open holding the Critic gate's span flip.

## 2026-09-02: learnings v2 delete — the lookup, audit and archive mechanisms retired; the reflection gate fires on the common case; the loop measures itself

<!-- prawduct: type=feat | scope=learnings-v2-delete -->

Wave 2 of the learning-system v2 program (#744; plan `build-plan-learnings-v2-delete.md`, five
chunks, four opus delegates in isolated worktrees, one merged `final` review). **Chunk 01:**
`audit-learnings`, `learnings-obligation` and `check-learnings-pairing` are deprecated-inert stubs
(exit 0, stderr `WARNING:`, nothing written — the `regen-views` shape, pinned in
`test_deprecated_inert_commands.py`) per the api-contract deprecation norm rather than dispatcher
deletions; their modules (2,107 lines) and tests (4,222 lines) are deleted, with the record-lint
`learnings-entry-shape` check, the `sentinel_command` template key, and doctor's checks 13/13a and
audit flow. **Chunk 02:** the `/prawduct:learnings` skill, the `reflections.md` archive and its
provenance header, the `.subagent-briefing.md` learnings embedding, and every instruction site
(planning/building/reflection guides, the digest, pr/methodology/doctor skills, README, CLAUDE.md)
are deleted or rewritten to the harness-loaded model; the single-resolver allowlist shrinks to four
entries. **Chunk 03 (#685):** the Stop hook's reflection gate reads `gates.session_work_span` (base
tree → working tree; porcelain when the marker is missing) and grades shape via
`gates.reflection_shape` (expected/actual + root cause or "no defect"); the plan conjunct and the
50-character floor are gone; the Critic gate keeps its porcelain guard (#304 holds that flip). The
merge-only false fire is measured by a real `git merge` in `test_reflection_gate.py` and costs two
lines once. The session-start advisory in `briefing.py` reads the same span and shape. **Chunk 04:**
`learning.written` (Stop, one per new rule unit, idempotent by session+file+hash) and
`learning.fired` (`critic-consolidate`, a finding containing a unit's opening eight words, joined
by review id) — `lib.ledger` stays the one writer and the CLI refuses `learning.*`; a rule unit is a
`##`/`###` heading or top-level bullet, hashed by `learnings_files.unit_hash`; units under three
words cannot fire. This repo's core.md: 288 units, 288 distinct hashes. **Chunk 05:** the grep-clean
re-derivation `grep -rnE "audit_learnings|learnings_obligation|learnings_pairing|learnings-entry-shape|_check_learnings_shape|prawduct:learnings|reflections\.md|reflection_provenance|sentinel_command|sentinel_ungraded|Active Learnings|learning_families" plugin tests README.md CLAUDE.md documentation .prawduct/cross-cutting-concerns.md .prawduct/artifacts .claude/rules/learnings`
(widened after the review found the two governing corpora outside the first sweep) returns only the three stubs, plan/discovery/audit prose recording the retirement, test assertion strings that guard the absence, one budget-ledger
comment, and `plugin/CHANGELOG.md` / `documentation/issues/` history.

Token ceilings moved by declaration in Chunk 03 (`building.md` 4757→4788, digest framework
3198→3214 / product 2086→2101: the gate's predicate changed on the one surface every session
receives) and were ratcheted down by Chunks 01/02 (`review-cycle.md` 9600→9597 net of Chunk 04's
citation sentence; `goals-1-3.md` 2280→2278). `learning.written` and the budget gate both read
`gates.session_work_span` rather than the porcelain list, so a rule written AND committed in one
turn is charged and recorded at that turn's Stop — one span, because the ceiling question and the
written question are the same comparison against the same base.

## 2026-09-02: learnings v2 core — the corpus moves to `.claude/rules/learnings/`, loaded by the harness

<!-- prawduct: type=feat | scope=learnings-v2-core -->

Wave 1 of the learning-system v2 program (#744; discovery `learning-system-v2-discovery.md`).
The plugin stops re-reading `.prawduct/learnings.md` into context through a lookup skill and
lets the harness load `.claude/rules/learnings/core.md` (every session) plus `<area>.md` files
whose `paths:` frontmatter matches a file being read. Five chunks: the resolver every reader goes
through (`lib/learnings_files.py`), `prawduct-hook learnings-migrate` (lossless relayout of the
fleet's formats, byte-accounted against the written tree), a budget gate in record-lint AND at
Stop (`learnings-over-budget`: over budget and grown — pay from duplication, never trim a rule),
detection of an unmigrated repo (briefing directive + Stop floor `learnings-unmigrated`), and the
Critic/PR cross-check repointed at `learnings-files --for-diff`.

This repo migrated with its own command: 287 rules → one `core.md` of 100,181 bytes under
`## Unsorted` (the corpus was paragraph-rules only, so the map proposal was empty — splitting it
into area files is #343's content program). `learnings-detail.md` and `learnings-history.md` are
deleted (owner-ruled 2026-09-02; git history is the archive). The budget check passes on this file
because it is over budget and NOT grown; every future addition pays. Wave 2 (`learnings-v2-delete`)
removes the lookup skill, the audit lifecycle and the obligation repair (the size nudge already
went in Chunk 04); until
then `/prawduct:learnings` and doctor #5/#13/#13a point at a file this repo no longer has.
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
**Rollback:** an older plugin reads only the live log, so after a repo archives, downgrading past this
release hides archived release tags from plan-backfill and the release gate — copy the month files'
entries back into `change-log.md` first, or do not downgrade (noted in `plugin/CHANGELOG.md`).

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
