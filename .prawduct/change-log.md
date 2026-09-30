# Change Log — Prawduct Framework

<!-- Append new entries at the top. Each entry is a ## section.
     Historical entries (pre-2026-03-22) are in project-state.yaml under change_log_history. -->

<!-- Older entries live in .prawduct/change-log-archive/YYYY-MM.md, moved there verbatim by `prawduct-hook archive-change-log`. -->

## 2026-09-30: four governance frictions found in consumer transcripts

<!-- prawduct: type=bugfix | scope=sibling-hook-perf | chunks=02 -->

Found by the same investigation of consumer sessions as #931.

**A process running on its own no longer reads as a reason for `DO NOT CLEAR` (#932).** The
`clear-verdict` gate fired nine times across fabulous, discodon, puzzles and this repo. Every
block was correct and each cost a turn. The cause was one belief: that a server or recorder the
session had started would die with a `/clear`. The digest's precedence line, the verdict paragraph
in `session-hygiene.md`, and the gate's own message now say that a clear ends the conversation,
not the process. One test pins all three places. The digest pays for its clause in place by
dropping an opening sentence that restated "Read on demand", so both injected totals fall and
their ceilings ratchet down.

**Telemetry labels a repo by its identity, not its directory (#933).** Discodon's devcontainer
mounts every workspace at `/opt/venv`, so every ledger event since 09-21 read `project: "venv"`.
`gitstate.project_label` is now the one owner, shared by the ledger and the review-stats header.
It tries, in order: the committed `product_identity.name` (as a slug), the origin remote's
repository name, the main checkout's directory (which a worktree shares), and only then the
directory itself. `gitstate.declared_product_name` becomes the one reader of
`product_identity.name`, and the briefing delegates to it.
`[DECISION: clones of one repository share a label | identity is what the committed name and the origin carry, and no path survives a container | this changes future labels for three checkouts: samsung-frame-art-loader becomes curatarr (its origin), fabulous-tips becomes fabulous, and prawduct-learning becomes prawduct; worktrees take their main checkout's name; existing rows are not relabelled]`

**`**Type:** bugfix` parses (#934).** `building.md` sizes governance by work type (feature,
bugfix, refactor, …), and authors carried the word into a chunk's `Type:` field, which reported
it as unknown on a chunk that ran as `code` anyway. The work types are now aliases for `code`,
the full protocol, so an alias can never lighten a review. `planning.md` names them.

**The code-without-tests canary check is deleted (#935, part of #164).** It fired on every
session that changed code without a test file, a research spike under `docs/` included, and it
could not recognise test files beyond Python and JS naming. #164, owner-ruled, deletes it with
Critic Goal 1 as its covering surface. `_is_test_file` goes with it, and `architecture.md`'s
retroactivity inventory no longer lists it. The surviving canary checks had no tests at all; they
have them now, including a control showing that the canary still runs when the deleted check
would have been its only finding. The rest of #164 is still open.

## 2026-09-30: hook latency no longer grows with the evidence store

<!-- prawduct: type=bugfix | scope=sibling-hook-perf | chunks=01 -->

**Root cause (verified by profile and A/B).** Every SessionStart and Stop composes a coverage
verdict whose free-edge search keys every tree the evidence store mentions, one `git ls-tree`
each. The keys were memoised only within the process, and the store is append-only and shared by
every worktree, so hook latency grew with the store's age rather than with the work at hand. On a
snapshot of the puzzles repo (231 trees), each cached plugin version from 3.5.1-dev.2 to
3.7.0-dev.2 took about 6.4 s per Stop, of which 4 s was this keying. Field data from the
transcripts shows the growth: the puzzles Stop p90 went from 3 s to 15 s as its store grew from 20
trees to 231 between 09-12 and 09-30, and discodon (1,743 trees) reached a p90 of 62 s (#931).

**Fix.** `lib/tree_key_memo.py` persists each computed key beside the evidence store, keyed by the
tree and by the classifier's code identity (the plugin version, plus the plugin tree on a
checkout). Each tree now costs one `git ls-tree` per clone and per code change. An unreadable tree
is never remembered, so it still denies the free edge and is asked again next time. A second
cost of the same kind: trees that git has collected, which the store keeps naming, cost a failed
`ls-tree` apiece on every hook (198 of 1,326 here). One `git cat-file --batch-check` now answers
all of them (`evidence.missing_objects`, reached through the key function's `prime`). The memo
saves every 100 new keys and at exit, so a cold run that the harness kills keeps its progress.

Measured on the same snapshot, with an edit before each Stop as in a real session: warm Stop hooks
went from about 6.0 s to about 2.1 s, and the coverage verdict itself from 4.1 s to 0.05 s, with
identical gate output. This repo's warm Stop went from 34 s to about 6.3 s. The rest is a fixed
set of git calls spread across other gates, plus the base-advance diagnosis's per-candidate diffs,
filed separately.

**SessionStart's api-versioning probe (#936).** `Codebase` ran an `rglob` per pattern, four per
sync, each descending into `.git`, `.venv` and `node_modules` before discarding what it found. It
now walks once, pruning the skip set as it descends, and every scan filters that listing: about
1.1 s down to 0.18 s on the snapshot, returning exactly the same files as before on puzzles and on
this repo.

## 2026-09-29: develop opens 3.7.0-dev.2

<!-- prawduct: type=chore | scope=dev-track-bump-3.7.0-dev.2 -->

The dev track's version moves from `3.7.0-dev.1` to `3.7.0-dev.2` in the four carriers, so repos on
the develop track pick up `opus-55-w6-reference-docs` (#926). Owner-directed, 2026-09-29.

## 2026-09-29: the reference docs are retuned for Opus 5.5 (audit wave W6)

<!-- prawduct: type=feature | scope=opus-55-w6-reference-docs -->

Wave W6 of `opus-55-prompt-audit-2026-09.md`, ruled in full on 2026-09-28, and the audit's last.
It applies slice E's 19 decisions to `plugin/docs/`. `runbook-authoring.md` no longer calls length
the best-evidenced finding in the literature, which its own evidence section contradicted, and
drops five competing superlatives (E-1, E-6). Its three self-review passes become the bar a
finished runbook meets; the subtraction pass stays (E-5, F3). Dated model statistics, a volatile
benchmark and the guide's research history give way to the rules they supported (E-7 to E-9).
`norms.md`'s enforcement table points at § Severity instead of restating it as "ratified", the
threshold the Critic protocol had already dropped in W3 (E-4), and loses a correctness proof and
three history clauses (E-3, E-10 to E-13). `waivers.md` loses its argument against the retired
per-rule literals and no longer names a region form it does not parse (E-14, E-15).
`test-report-contract.md` stops addressing prawduct's maintainers and trims the reviewer-talk
comments consumers paste (E-2, E-16, E-17). `governance-telemetry.md` and `discipline.md` lose
ticket ids, audit citations and row history (E-18, E-19). The runbook skill's three copies of
E-5's self-review instruction are aligned with the guide. No parsed table changed shape, and no
token ceiling applies to these files.

The Fable final-coherence pass the audit owed ran over the whole cycle (W1 to W6) before this wave
lands, and its fixes ride here. It found seams between waves, not disagreements of intent. The
chunk-boundary review exception in `session-hygiene.md` and root `CLAUDE.md` now allows for a short
plan's single boundary review. `review-cycle.md` no longer quotes a `building.md` sentence that is
gone, or claims the close directive prints its paragraph verbatim. The backlog skill names the
change-log's `release=` tag, not the inert `status=shipped`. Two pointers to a nonexistent
"Coverage Evidence" section, and the preferences template's Goal 4 for norms (it is Goal 3), are
corrected. The pr skill loses its issue ids, and the backlog and janitor skills their pointers to spec decisions D4 and D14. A `reviews.md` rule loses its
whole-diff self-scrub, and a `core.md` Tell no longer assumes file-list deliverables. The
methodology index drops its between-phase validation (B-19's class), and three reviewer directives
in `critic_consolidate.py` lose their capitals, as A-5 did for NEXT-ACTION.
`review-cycle.md`'s and the injected footprint's ceilings ratchet down with their readings.

## 2026-09-29: develop opens 3.7.0-dev.1

<!-- prawduct: type=chore | scope=dev-track-bump-3.7.0-dev.1 -->

The dev track's version moves from `3.6.2-dev.7` to `3.7.0-dev.1` in the four carriers, so repos
on the develop track pick up `opus-55-w5-operational-skills`. The track now heads for a minor
release rather than a patch. Owner-directed, 2026-09-29. It rides this PR.

## 2026-09-29: the operational skills are retuned for Opus 5.5 (audit wave W5)

<!-- prawduct: type=feature | scope=opus-55-w5-operational-skills -->

Wave W5 of `opus-55-prompt-audit-2026-09.md`, ruled in full on 2026-09-28. It applies slice D's
61 decisions to every skill except `critic` and `pr`. Doctor states "degraded because ungraded"
once instead of seven times, and its checks keep their statuses and lose the history of why each was
built (D-1 to D-8, D-30 to D-33). The migration scrub keeps every command, gate and ordering and
loses its incident stories, version pins, spec ids and a misplaced, duplicated `duplicate_alias`
remedy (D-9 to D-14, D-35 to D-40). The backlog files drop an envelope no code emits (D-15),
prohibitions naming retired ops, and second copies of facts that have a home elsewhere (D-24, D-25,
D-45, D-51). `add` lists delegation last (D-26, F4). `pick` ranks by value per effort and flags
unassessed items, where it used to compute a score (D-28). The janitor points at
`/prawduct:methodology` instead of a product `CLAUDE.md` that no longer carries planning guidance
(D-18). Shouted headings lose their caps (D-54, D-58, D-61). The runbook skill and template lose
their copies of the overstated "best-evidenced finding" claim and the dated hallucination rate
(E-1, E-8). The backlog half was built by one worktree delegate. D-23's and D-29's maintainer
rationale moved into test docstrings, and D-29's two sentence asserts went with it. The
writable-block-field guard follows D-25's moved sentence to `adapter-mode.md`, and was
red-verified there. One regression probe (D-28, Opus 5.5) found no regression. No token ceiling
moved, because no file in this wave has one.

Two changes are more than prose. The janitor's neglected-hygiene check (Backlog Health check 5)
now runs on the Issues backend too, over `in-progress` rows whose `working_branch` appears merged;
it had been off there since #529 (now #729), which has shipped. And a test now checks the
cache-query grant on all four readers of the backlog cache (two agents and two skills), where before only the PR
reviewer's grant was tested.

## 2026-09-29: the methodology guides and templates are retuned for Opus 5.5 (audit wave W4)

<!-- prawduct: type=feature | scope=opus-55-w4-methodology-templates -->

Wave W4 of `opus-55-prompt-audit-2026-09.md`, ruled in full on 2026-09-28. It applies slice B's
decisions to the six methodology guides and the artifact templates: B-1 to B-40 except B-41, a
flag. The guides no longer license ending a turn with work in hand (B-9, B-16, B-35): a chunk
boundary ends the turn only when the plan is done, the next chunk needs the user, or the cycle
has reached what one review covers. The builder is no longer told to scrub its own diff while the
Critic runs, to review every artifact phase, or to redo a delegate's sweep (B-1, B-19, B-36,
B-10 to B-12); instead a delegate's brief asks for the output that shows a removal or sweep
complete. Delegation stops being the default for tangents and no longer requires a subagent for a
consumer grep (B-2, B-13 to B-15); the delegate criterion is the owner's, wall clock gained
without conflict. Chunk shape, file-list deliverables and phase choreography become advice
(B-17 to B-19), which closes #341. `architecture.md`'s "goals bind; method is advice" norm
therefore moves from `in-transition` to steady-state: its stopgap goes, and its Retroactivity
line records the migrated sites. B-21 and B-22, discovery's domain-concern table and question
quotas, were held until a Sonnet 5.5 probe and ship here. On the probe, the new text raised every
critical concern the old text raised. Templates lose dead component headers, unnamespaced
commands, incident stories and caps-lock register (B-3 to B-7, B-29 to B-32, B-37, B-38). The
build-plan template's worked example states deliverables as outcomes, and its cadence line points
at the short-plan rule. The template half was built by one isolated-worktree delegate. Carried
from the W3 handoff: `building.md`'s fix-order sentence takes W2's register, and a delegate brief
names the budgets its files sit under. Token readings drop on five guides. `delegation.md` rises
by 14, a recorded raise. The fix-order pin now asserts `gates.FIX_ORDER` verbatim, the suite-at-boundary pin follows
its de-bolded sentence, and
`docs/discipline.md`'s anchors for rows 4 and 9 follow B-2 and B-24. The template
`project-state.yaml` loses the removed question quotas, its version fossils, and a claim that
the backlog probes were unbuilt. The owed Sonnet 5.5 probes
ran through `claude -p`, because the Agent tool's alias cannot select that model:
- W3's reviewer surfaces showed no regression.
- B-12 is the first decision whose control failed and whose treatment fixed it.
- The longer early-stop probe on Opus 5.5 did not stop early, even on the pre-W1 text. The audit
  records what that means for per-wave probing.

Also shipping:
- The scaffolded backlog legend's `closed-by:` names a scope, branch or release tag, never a bare
  chunk id (B-5), which closes #779. `documentation/backlog-system-requirements.md` takes the
  same fix.
- `reflection.md`'s stopping rule and its bug-fix protocol are compressed into one statement each
  and point at Step 3, rather than restating it.
- `authoring.md` gains a learning: a new project-wide concept cascades to the product anchor, the
  Critic and PR protocols, methodology, templates and their budget tests.

Two departures from the owner's ruled text, both vetoable (the plan's cumulative-review record):
- R-7: B-25's replacement dropped the 3-4-file size, which decides whether a Critic review runs.
  It is restored as small.
- R-10: B-24's "file the rest" contradicted `core.md`'s fix-the-class rule. Post-Fix now fixes
  the class through its one owner when it can be changed here.

Plan: `build-plan-opus-55-w4-methodology-templates.md`.

## 2026-09-29: develop opens 3.6.2-dev.7

<!-- prawduct: type=chore | scope=dev-track-bump-3.6.2-dev.7 -->

The dev track's version moves from `3.6.2-dev.6` to `3.6.2-dev.7` in the four carriers, so repos
on the develop track pick up `opus-55-w3b-review-cycle-split`. Owner-directed, 2026-09-28. It rides
this PR.

## 2026-09-28: the Critic's reviewer payload loses the builder lifecycle (audit wave W3b)

<!-- prawduct: type=feature | scope=opus-55-w3b-review-cycle-split -->

Wave W3b of `opus-55-prompt-audit-2026-09.md` (C-8, C-20), split out of W3 by its plan.
`review-cycle.md`'s reviewer-facing half moves verbatim to a new `skills/critic/cross-checks.md`:
the chunk `Type:` selector, the rule that a finding never names a destination, and the
Final-Mode Cross-Checks. `critic/SKILL.md` now routes `final`/`cumulative` reviewers to it, and
`review-cycle.md` stays as the builder's lifecycle, which no reviewer loads. The Coordinator Pattern
moves out of `review-protocol.md` into a new `skills/critic/coordinator.md`. Only the coordinator
fork reads it, rather than `SKILL.md` as the slice proposed, because `SKILL.md` is on the cheap
`chunk`/`verify` route (a vetoable decision in the plan).

The dispatched-reviewer payload drops by 7,843 tokens, about 23.5k per three-reviewer review.
Single-pass `final`/`cumulative` drops by 7,855. Every reviewer- and builder-facing citation of a moved
section points at its new file. Two inert comments in `backlog/cli.py` and `test_backlog_cli.py`
still say "the Critic's review-cycle"; they were accepted as O-2. That covers the Critic and PR protocols, `critic-reviewer.md`, `backlog/cache-reads.md`,
`planning.md`, the build-plan template and `governance-telemetry.md`. Tests that read a moved
section now read it from its new home. The Critic's surface-grants map and the bare-command
sweep are now derived from the files on disk rather than hand-listed, and every `skills/critic/*.md`
must be a reviewer surface or be named as not one. Both new files carry token
ceilings, and a `coordinator-fork` payload route prices the fork. The cheap-route relation bound
moves from 1/2 to 11/20, because the full route shrank beneath it. Plan:
`build-plan-opus-55-w3b-review-cycle-split.md`.

## 2026-09-28: develop opens 3.6.2-dev.6

<!-- prawduct: type=chore | scope=dev-track-bump-3.6.2-dev.6 -->

The dev track's version moves from `3.6.2-dev.5` to `3.6.2-dev.6` in the four carriers, so repos
on the develop track pick up `opus-55-w3-review-machinery`. Owner-directed, 2026-09-28. It rides this
PR.

## 2026-09-28: the review machinery is retuned for Opus 5.5 (audit wave W3)

<!-- prawduct: type=feature | scope=opus-55-w3-review-machinery -->

Wave W3 of `opus-55-prompt-audit-2026-09.md`, ruled in full on 2026-09-28. It applies slice C's
in-place decisions to `skills/critic/*`, `skills/pr/*` and both reviewer agent definitions:
C-1 to C-7, C-9 to C-19 and C-21 to C-24, plus the Critic goal files' threshold for norm
departures, which moves from "ratified" to "adopted". The review protocol names `norms.md`'s
"Severity, stated once" paragraph, and `goals-1-3.md` states the scope inline so it stays
self-contained. The PR
reviewer reports every release-readiness defect at its severity. Its value filters are gone, and
disposition is left to the builder (C-1, F6). The Critic reviewer loses its work-size coaching and
its "do not invent findings" line (C-22, C-23). Copies of protocol rules in both agent
definitions become pointers, and issue ids, dates, harness-version provenance and
migration-relative phrasing come out of the instructions. Token readings drop on every Critic file
and route, and the ceilings drop with them. `review-cycle.md` no longer states a wait cadence. The
one home for the cadence stays `critic_consolidate._CACHE_WARM_INTERVAL_MINUTES`, and the test
that bound the two now pins that the prose names no interval. `test_signals_and_work_scaling` is
retired with the text it pinned. Sentence pins this wave touched are retired or re-anchored on
structure or an interface token. That includes one `test_pr_reviewer_agent.py` assertion deleted
outright, and the `#254`, C-4 and findings-step pins. The two absence guards that remain (C-1's
value filters, and the cadence pattern) are a recorded, vetoable exception. The caller's rule never
to move `commit_reviewed` is restated in `/prawduct:pr`, and `critic-reviewer.md` keeps the "stay
inside your `tools:` line" contract. C-5's and C-10's trims had dropped both. Two `_NOT_GRANTED` exemption rows are removed, because the skill
no longer names those commands. The two structural moves, C-8 and C-20, go to their own plan, W3b.
F6's rounds-per-PR baseline is recorded in the audit artifact. The PR-side half was built by one
isolated-worktree delegate and merged here. `documentation/issues/712-design.md` and
`830-requirements.md` stop citing text this wave rewrote. The probe ran on Sonnet 5, not 5.5,
because the Agent tool's alias could not select it. The Sonnet 5.5 rerun is owed with W4's probe.
Plan: `build-plan-opus-55-w3-review-machinery.md`.

## 2026-09-28: develop opens 3.6.2-dev.5

<!-- prawduct: type=chore | scope=dev-track-bump-3.6.2-dev.5 -->

The dev track's version moves from `3.6.2-dev.4` to `3.6.2-dev.5` in the four carriers, so repos
on the develop track pick up `opus-55-w2-hook-gate-text`. Owner-directed, 2026-09-28. It rides this
PR.

## 2026-09-28: hook and gate text is retuned for Opus 5.5 (audit wave W2)

<!-- prawduct: type=feature | scope=opus-55-w2-hook-gate-text -->

Wave W2 of `opus-55-prompt-audit-2026-09.md` (A-5, A-6, A-7, A-27 to A-30), which the owner ruled
in full on 2026-09-28. NEXT-ACTION states the decision, the command and the cost, and stops
re-arguing them: the common warnings close drops from about 347 to 232 words, with no capitals
except the `BLOCKING` severity token. The batch-fix directive loses its dangling pointer to
NEXT-ACTION. `gates.blocking_remedy_lines` composes the fix order instead of restating it. The
Stop gate prints one escape-hatch footer after the `BLOCKED` list in place of a recipe per
blocker. The footer writes one JSON object: the blocking gates' keys plus the waivers
already in the file, because each `echo … >` recipe replaced the file and erased the others. Every
gate's waiver check, `KNOWN_WAIVER_KEYS` and the footer read one gate-to-key map. The fix order's
one home moves to `gates.FIX_ORDER`, and `critic_consolidate` imports it with one top-level import
of `gates` in place of four lazy ones. The reflection blocker's cadence paragraph is one line.
Three reviewer dispatch directives lose their "spend this on…" closers (F6: compare
`review-stats` rounds per PR before and after W3). The briefing's advisory relay ends by saying the user's own request goes ahead.
What applying it found is in the plan. Plan: `build-plan-opus-55-w2-hook-gate-text.md`.

## 2026-09-28: develop opens 3.6.2-dev.4

<!-- prawduct: type=chore | scope=dev-track-bump-3.6.2-dev.4 -->

The dev track's version moves from `3.6.2-dev.3` to `3.6.2-dev.4` in the four carriers, so repos
on the develop track pick up `opus-55-w1-always-on` and `short-plan-tick`. Owner-directed,
2026-09-28. It rides this PR.

## 2026-09-28: a short plan's earlier chunks are ticked at commit

<!-- prawduct: type=bugfix | scope=short-plan-tick -->

On a short plan, inference counts two or more unticked boxes as mid-plan and answers `deferred`,
while the tick rule said to tick only after a chunk's review. A deferred chunk's review is the
boundary `cumulative`, so a builder following the rule never reached it. W1 of the Opus 5.5 audit
hit this. `planning.md` now defines a deferred chunk's tick as due at commit, and the digest's tick
bullet carries the trigger (a declared raise of 11 tokens). The deferral rationale says so, and no
longer claims to key on commits. The next step now has one owner, `critic_mode.short_plan_next_step`. The
rationale and both Stop-gate short-plan messages (the non-final warning and the last-chunk
block) are built from it, so the gate names the open boxes and no longer says "commit it and
carry on". The owner confirmed the direction. Plan:
`build-plan-short-plan-tick.md`.

## 2026-09-28: the always-on surface is retuned for Opus 5.5 (audit wave W1)

<!-- prawduct: type=feature | scope=opus-55-w1-always-on -->

Wave W1 of `opus-55-prompt-audit-2026-09.md`, which the owner ruled in full on 2026-09-28. The
digest gains a take-the-next-step rule and plainer standing-block and bullet text. The
stance bar "verify your own work before done" is now "show evidence for done". `CLAUDE.md` and
`principles.md` drop text that duplicates the digest. `core.md` goes from 38 rules to 17, the area
files drop their copies of core, and every rule sheds issue ids, dates and incident specimens.
`CORE_HEADER` asks for a citation only where a rule changed the work. The injected footprint went
from 3280 to 3134 tokens (framework) and from 2221 to 2191 (product); the tick fix above then adds
11. Things the audit missed are recorded in the artifact's "Found while applying" section. Two
bookkeeping changes ride along: the research artifact itself (the `opus-55-prompt-audit` scope,
with no code) and, by the same ruling, the archived `release-plan-backlog-service-golive.md`.
`authoring.md`'s 18KB budget raise is removed, because the trim left the file under the default. Plan:
`build-plan-opus-55-w1-always-on.md`.

## 2026-09-28: release= accepts four-part versions

<!-- prawduct: type=bugfix | scope=four-part-release-versions -->

Reported upstream as #901. A product whose git tags have four numeric parts (`v1.2.3.4`) could
not stamp them. Every `release=` was refused as "not a version", so `archive-change-log` moved
nothing, `check-releasability` failed, and the oversized-change-log advisory could not be
resolved. The refusal also told the author to delete the tag, and on an entry that had shipped,
that would have marked shipped work as pending.

**Root cause (verified):** `RELEASE_VALUE_RE` in `lib/change_log.py` allowed exactly three
numeric parts. It is the only parser of the value. `validate_change_log_tags`, which both
commands call, is its one caller. Every other reader compares the value by presence or equality.

**Fix.** The pattern takes an optional fourth numeric part, before the existing optional
`-suffix`. It is explicit rather than open-ended, so `v1.2`, `v1.2.3.4.5`, a missing `v` and
`release=unreleased` all still fail closed. The diagnostic names both shapes with examples and
now gives the remedy for each case: correct the value if the entry shipped, delete the tag if it
did not. The docstring, the template's `release` key description and
`documentation/release-process.md` say the same thing, as does the plugin-release runbook's
`bad-change-log-tag:` remedy. The template's tag-line example is left
alone, because #765 rewrites it. Tests cover acceptance and rejection at the validator, through
archive selection and the `archive-change-log` CLI, and through `check-releasability`,
including a four-part product version being cut.

## 2026-09-28: stranded branches raise an advisory; the briefing counts idle worktrees

<!-- prawduct: type=feature | scope=stranded-work -->

Finished work was getting stranded where no reader looks. #898 and #818 sat reviewed on a
never-pushed local branch while the next triage session planned to build #898 again; #640's fix
sat on a local branch 281 commits behind develop until #853 re-applied it. Nothing surfaced a
branch that exists only locally when no build plan names it. A clone also collects worktrees
with no signal of which still have an agent in them.

**What changed.** New `lib/stranded_work.py` scans, read-only, for three readers. Each stranded
branch — checked out in no worktree whose directory still exists, tip reachable from no
remote-tracking ref (one `rev-list --branches --not --remotes` walk answers every branch) —
raises its own `branch-landing:stranded-branch` advisory (`lib/stranded_branch_probes.py`):
named, dismissible, self-resolving. That is #843's local-only arm; its plan-ticked, never-PR'd
arm needs a network call and stays open on #843. Sibling worktrees reach the briefing as one
line of counts that names nothing (owner ruling on #410, reaffirmed 2026-09-28).
`prawduct-hook worktrees [--json]` lists both. There is no age floor on branches: a 3-day floor
was drafted and dropped when the scan, run on this repo, showed it excluded the 18-hour-old #898
branch that motivated the feature. A repo with no remote reports no branches, since every branch
would qualify.

**How it got here.** The first boundary review (2 blocking, 11 warnings) found the design had
never consulted `documentation/issues/843-design.md`, which already ruled this signal a
dismissible advisory (owner, 2026-09-19). The owner chose, 2026-09-28, to move branches to the
advisory roster and keep worktree counts in the briefing. The same pass gave `git worktree list`
parsing one home — `gitstate.worktree_records`, moved from `adhoc_delegate_probes` as #843's
Decision 4 specifies — where `briefing._detect_worktrees`, the delegate probe and this scan had
three copies that disagreed about prunable and detached entries. `worktree_records` returns
`None` when git fails in a real repo: the delegate probe and this scan name what they lost, and
`briefing._detect_worktrees` drops its orientation line, which the worktree line covers. The two blocking
findings: the scan's private git runner raised on non-UTF-8 output, which the briefing did not
guard, so one odd filename could replace the whole briefing with a failure line; and a
per-branch `rev-list` ran on every session start for a count nothing there used. The scan now
goes through the shared `evidence.run_git`, which already converts a decode failure into a
failed call and gains a `strip=False` opt-out because stripping shifts a porcelain parse. It
counts commits only for the table, has a 4-second total budget, and the briefing guards its one
line. A scan that could not list worktrees now says so rather than printing nothing.
A second boundary review (0 blocking, 6 warnings) led to: `%(refname:lstrip=2)` rather than
`short`, which git lengthens when a tag shares a branch's name; silence in a folder that is not a
repository; `gitstate` reading git itself instead of importing `evidence` upward, with
`record_branch` / `record_is_gone` as the one reading of a worktree record; the orientation line
reconciled with the worktree line; and quoted branch names and paths in the three probes that
interpolate them into commands (`stranded-branch`, `unintegrated-delegate-worktree`,
`unpromoted-release-prep`). Their tests check the quoting without a shell — the suite bans
`shell=True` — by tokenizing as a shell does (`shlex.shlex(punctuation_chars=True)`) and pinning
`shlex.join`'s single quotes, since a shell still expands `$(` inside double ones.

**Liveness is the newest of four signals**, and the report names the winner: transcripts over
every Claude config root (owner, 2026-09-28: several accounts keep transcripts of different ages
for one worktree), the HEAD reflog, `.prawduct/.session-start`, and the newest dirty file. The
git index mtime is excluded because any observer's `git status` rewrites it — the plan's own
first probe did — and every call runs with `GIT_OPTIONAL_LOCKS=0`. A process cwd check was tried
and dropped: a desktop-app session runs with cwd `/`, so it failed its positive control.
verify-api for the transcript layout, observed on this machine's six roots: every
non-alphanumeric character maps to `-`, paths appear resolved (`/tmp` as `-private-tmp`),
subagent transcripts live under the parent session's directory, and the longest name seen was
173 characters with no truncation. No path containing `_` existed to confirm that character.

## 2026-09-28: develop opens 3.6.2-dev.3

<!-- prawduct: type=chore | scope=dev-track-bump-3.6.2-dev.3 -->

The dev track's version moves from `3.6.2-dev.2` to `3.6.2-dev.3` in the four carriers
(`plugin/VERSION`, `plugin.json`, `pyproject.toml`, and the open `plugin/CHANGELOG.md` heading), so
repos on the develop track pick up `test-evidence-pre-run-tree` and `test-evidence-root-testcases`.
The version string is the plugin cache key, so a repo that already resolved `3.6.2-dev.2` would
otherwise never see them. Owner-directed, 2026-09-28. It rides this branch's PR, so one review
covers the bump instead of a PR of its own.

**The release number is still the cut's.** This bump labels the dev track only.

**No consumer notes were owed.** Both scopes already carry their entries in the open
`plugin/CHANGELOG.md` section.

## 2026-09-28: test evidence counts a failing top-level node:test case

<!-- prawduct: type=bugfix | scope=test-evidence-root-testcases -->

Reported upstream twice, independently: #912 (@Jason-Vaughan) and #913 (@L13w, merged into
#912). node:test's JUnit reporter writes a top-level `test()` as a `<testcase>` directly under
`<testsuites>`, and `test-evidence record` never counted it. A failing one recorded `failed: 0`.
A live run still exited 1, but `--from-junit` exited 0, and the Stop gate, the Critic and
`/prawduct:pr` all read that record as green. A report whose tests were all top-level was
refused as `no <testsuite>`.

**Root cause (verified):** the aggregation built its unit list from `root.findall("testsuite")`
and counted only the leaves inside those suites. Separately, a command's exit status set the
hook's exit code but was never checked against the counts it recorded.

**Fix.** A `<testsuites>` root's direct `<testcase>` children are now units of their own, read
in document order, so `failed_tests` keeps report order. A report with no suite but with cases
records normally. One with neither is still refused. As defense in depth, a live command that
exits nonzero while its own report shows no failing test is refused (exit 2, nothing written).
The check is per command, so another command's real failure can't cover for it. It refuses
rather than marking the record `degraded`, which only a coordinator asserts. A report known to be
complete, say from a run failed only by a coverage threshold, can still be ingested with
`--from-junit`. The refusal also stops a pytest run that collected nothing (exit 5) from
recording a green `0 passed, 0 failed`. Tests pin both reported shapes, the all-top-level
report, the empty report, the `--from-junit` exit status, and the refusal, including the case
where another command's failure would cover for it, and the undeclared pytest fallback that
collected nothing. A durable-worktree guard test forbade the
bare word "refusing" in stderr, which only passed because of that exit-5 green. It now asserts
only that `BLOCKED` is absent. That already covers the guard's `BLOCKED: refusing`, and a
positive control confirmed the guard still emits that phrase.

## 2026-09-27: test evidence vouches only for a tree its run held still on

<!-- prawduct: type=bugfix | scope=test-evidence-pre-run-tree -->

Found in this repo's own session. A file edited while `test-evidence record` was running the
suite was stamped into `evidence_tree`. A later session, or another worktree through the shared
run index, would then treat the edit as tested by a run that may never have loaded it.

**Root cause (verified):** `cmd_test_evidence` captured `evidence_tree` once, after the suite
finished, and nothing compared it with the tree the run began on. A mid-run edit therefore
landed in the stamp and matched the working tree exactly. The shared run index inherited the same
tree, so other worktrees would trust it too.

**Fix.** A live run captures the tree before its first command and asks
`_test_evidence_tree_valid` at the end whether it held. It uses that check, not raw tree
equality, because every run writes caches and reports of its own. If the tree held, the run
stamps it as before. If it moved, or either capture failed, the record carries no
`evidence_tree` and stderr says why. When the capture before the run failed, the warning carries
that capture's reason and gives no re-run advice, since it would fail the same way next time. The
end-of-run check does not tell a moved tree from a failed comparison, so both still get the
re-run advice. The record then stays current for
this session through the unchanged timestamp clause, but no later session, and no other worktree
through the shared run index, reuses it. That is the existing "a capture failure omits the field" path, so the
recorder still never marks a record `degraded`, which only a coordinator asserts, and a quiet
run reads exactly as before. The first cut derived `degraded` from the diff and was reverted in
review. That broke the field's coordinator-only contract, and a suite writing its own files
would have gone stale on every run. The `gates.py` schema comment and tree-validity docstring
and `data-model.md` now say when the tree is captured.

## 2026-09-27: only a turn still working may say DO NOT CLEAR

<!-- prawduct: type=bugfix | scope=clear-verdict-coherence -->

The owner reported this from this repo and every consuming repo: agents closed turns on `YOUR TURN`
(decide something) with `DO NOT CLEAR`. The reader may not see that turn for days, and the pair is
incoherent. `DO NOT CLEAR` means the agent is still working, and `YOUR TURN` hands the session over.
Owner rule, 2026-09-26: `YOUR TURN` MUST mean safe to clear.

**Root cause: the framework prescribed the pair.** There were three sources:
1. The precedence rule in `session-hygiene.md` and the digest said "if they must speak it is
   `YOUR TURN` even when something also runs". A live review is `DO NOT CLEAR`, so a decision
   needed during a review produced exactly the pair.
2. `gates.turn_declares_in_flight` deferred reflection and Critic on any `DO NOT CLEAR` turn, and
   its docstring named "an ask the user must answer first" as a proper use. The digest's Enforcement
   line said the Stop hook "BLOCKS any turn not closing on `DO NOT CLEAR`". Together they taught the
   label as the way past the session-end gates. This came from review-friction's verdict deferral
   (owner ruling "Defer both", built for "press the button, then tell me" turns).
3. `building.md` said "`SAFE TO CLEAR` only when … nothing is outstanding", which an agent reads as
   covering a decision it is waiting on. `digest-behavior-inventory.md` A10 also offered "or says
   DO NOT CLEAR" as the alternative to persisting findings.

**Fix.** Only `RUNNING` may say `DO NOT CLEAR`:
- `lib/standing_block.py` gains `disposition()` and `contradiction()`, and the one shared
  label-lead parser that `clear_verdict()` now uses too.
- The verdict deferral requires `RUNNING` + `DO NOT CLEAR`.
- A new Stop gate, `clear-verdict` (`gates.json`, `since: 3.7.0`, with the other gates this
  unreleased track adds), refuses `YOUR TURN`/`COMPLETE` + `DO NOT CLEAR`. It is held apart from
  both deferrals, so in-flight background work cannot swallow it.
- Prose: the precedence rule gains its exception (work a clear would kill → `RUNNING`, the ask in
  the copy) in the hygiene guide and the digest. `building.md` says a recorded decision is not
  outstanding. The unreleased review-friction release note now describes the narrowed deferral.

**Owner decision (2026-09-26): both gates fire on a `YOUR TURN` turn.** Mid-work question turns
face reflection and Critic again. The alternatives were deferring Critic, or both gates, on
`YOUR TURN`. They were rejected because after a `/clear` the session git baseline goes blind to
files that were already modified, so an unreviewed chunk handed over as clear-safe can slip past the
next session's gate. Some of the friction review-friction removed comes back, deliberately. The
owner asked in the same exchange whether reflection pays for its gate; that question is filed as #908,
separately, and does not touch this fix.

**Decision the owner can still veto.** `nonfunctional-requirements.md` records `clear-verdict` as a bounded
exception to the proportionality norm's emission arm. It states its expected yield and has no ledger kind,
because a `gate.*` kind for one gate is lock-in. Its clock is `#563`. The final Critic review raised it.
`digest-behavior-inventory.md` gains row A14 for the invariant, and A10 drops its "or says DO NOT CLEAR"
alternative.

**Budgets.** The digest is held at 9,499 of its 9,500-character working budget. That was paid in
place: the new rule absorbed the findings-only sentence, which stated the same obligation. The
injected-token ceilings get a declared +2, and `building.md` a declared +6; the reasons are
recorded at each pin.

## 2026-09-26: develop opens 3.6.2-dev.2

<!-- prawduct: type=chore | scope=dev-track-bump-3.6.2-dev.2 -->

The dev track's version moves from `3.6.2-dev.1` to `3.6.2-dev.2` in the four carriers
(`plugin/VERSION`, `plugin.json`, `pyproject.toml`, and the open `plugin/CHANGELOG.md` heading), so
repos on the develop track pick up `drop-risk-surface-ask` and `onboard-ux`. The version string is
the plugin cache key, so a repo that already resolved `3.6.2-dev.1` would otherwise never see them.
Owner-directed, 2026-09-26. It rides the `onboard-ux` PR, the second of the two to merge, so one
review covers the bump instead of a PR of its own.

**The release number is still the cut's.** This bump labels the dev track only.

**No consumer notes were owed.** Both scopes already carry their entries in the open
`plugin/CHANGELOG.md` section.

## 2026-09-26: onboarding recommends an Issues backlog and ends in discovery

<!-- prawduct: type=feature | scope=onboard-ux -->

Two owner observations from onboarding `../fabulous`, one skill.

**Backlog backend.** `plugin/skills/onboard/SKILL.md` called markdown "the default backlog backend"
and offered Issues only on explicit request. That contradicted the framework's own direction.
`backlog-service-migration-required` warns every session once a markdown backlog holds structured
items, and `--backlog-repo` is honoured only at the first scaffold; after that, adopting Issues is
the scrub cutover. Onboard now recommends Issues, and the owner names and confirms the `owner/repo`,
never inferred from a remote. Markdown remains the answer for products with no GitHub home, and
onboard routes those to `decline-migration`, since without it the warning can never resolve. The
section now states what each choice costs before the owner picks, as an invariant rather than a
tally. That closes #158, which asked for exactly this. This conforms to `architecture.md` § Direction
*Local-first*: the Issues backend stays opt-in, because the owner still chooses it and names the
repo, and an unconfigured product still gets markdown. Only onboard's recommendation moved. The `init_product.py` comment and two test
comments that called markdown-first "the normal path" now say otherwise.

**Ending.** Onboard ended on a checklist: commit these, open a new session, run discovery,
contributors install. The owner's read was "so what, now what". Onboarding now offers to commit
the scaffold as a pathspec commit of its own paths, so work the owner had already staged stays
out, and a refused commit is reported as uncommitted. When it runs in the target's own session with the plugin
active, it goes straight into discovery's reconciliation mode: read, lead with its own take, confirm,
fill the gaps. Otherwise it ends on one next step. The report keeps only what the owner must act
on. The owner chose both behaviours (inline discovery only in-target; offer-then-commit) on
2026-09-26. Discovery is not run cross-directory, because that session's hooks and gates govern the
launch directory, not the target. The skill gains `git status`/`add`/`commit` grants for the commit
step. `discovery.md` § Reconciling no longer claims nothing backfills the state after onboarding;
its token reading grows by 16, declared in the budget table.

**Observed, not changed.** In the fabulous session the reflection gate fired on onboarding alone,
because the scaffold writes `CLAUDE.md` and `.gitignore`, which `is_judgeable_path` counts. That is
correct under the path rule, so it is left as it is.

## 2026-09-26: nothing asks for risk surfaces any more

<!-- prawduct: type=feature | scope=drop-risk-surface-ask -->

Owner ruling, 2026-09-26, on the question as it reached a product session ("Where would a missed
defect cost you most? I'd propose this list..."): *"annoying and not helpful — can we expunge?"*
This reverses #163 (the discovery question, 2026-08-02) and the prompting leg that review-stages
added on 2026-09-17 (the advisory, doctor Check #20 and the `coverage-status` row).

**Why the ruling holds on the merits.** A declaration trades the derived defaults and the
`boundary-patterns.md` contract paths for the owner's own list (a present key is exclusive). For
a product whose tree the framework-shaped defaults don't match, that mostly buys more review: a
matched path gets the coordinator roster at any size, and a short plan touching one loses its
per-chunk deferral. Where it doesn't, it silently drops contract-path escalation. Undeclared
repos still escalate on the derived defaults, on the contract paths and at 12+ judgeable files,
and the boundary review runs everything. The stage-keyed rigor norm (`nonfunctional-requirements.md`
§ Direction) already treats over-review as a defect, priced in minutes and in the rounds it
manufactures. So the question nudged every product into a review-cost trade that is better made
deliberately. It also had the agent hand the owner work it could have inferred from the code.

**Removed:** `plugin/lib/risk_surface_probes.py` and its tests, the `probe_families` registration,
`discovery.md` § Surface Risk Surfaces, and `undeclared` as a finding in doctor Check #20 and in
`coverage-status`. An existing `risk-surfaces-undeclared` advisory resolves on the next sync,
because `advisory_store.reconcile` resolves any active entry its probes stop producing.

**Kept:** the `risk_surfaces:` key and everything that reads it (`lib/risk.py`,
`classify-diff-risk`, the roster, short-plan eligibility). `coverage-status` is in
`api-contract.md`'s stable tier, where `--json` keys are never removed or repurposed within a
major, so `risk_surfaces: {status, fix}` stays with the same status values. The classification
moves to `lib/risk.risk_surfaces_status`, and `fix` is now set only for `unparseable`. Check #20
survives as "risk surfaces readable": only an unparseable key is degraded, because it escalates
every review, and an absent key is healthy. The discovery section and Check #20 were the only
places that explained a present key is exclusive, so the project-state template comment now
carries it, together with the flow-style trap. `TestRiskSurfacesAreNotAsked` pins the absence of
the ask at the health report and the advisory roster, each with a positive control. It also pins
every `risk_surfaces.status` value through the real command, and the null status on a raising
classification. Each was red-verified: a registered risk-surface probe, a fix set for
`undeclared`, a suppressed unparseable line, and the guard removed. #854 (`[]` buys less
review than omitting the key) is untouched, and matters less now that nothing invites an owner to
write `[]`.

## 2026-09-26: develop opens 3.6.2-dev.1

<!-- prawduct: type=chore | scope=dev-track-bump-3.6.2-dev.1 -->

The dev track's version moves from `3.6.2-dev` to `3.6.2-dev.1` in the four carriers
(`plugin/VERSION`, `plugin.json`, `pyproject.toml`, and the open `plugin/CHANGELOG.md` heading). This
is so repos on the develop track pick up `learnings-one-line` (#902) and `review-friction`, which
merged after the v3.6.1 cut reopened `develop`. The version string is the plugin cache key, so a repo
that already resolved `3.6.2-dev` would otherwise never see them. Owner-directed, 2026-09-26.

**The release number is still the cut's.** `learnings-one-line` registers its two gates
`since: 3.7.0`, and its entry says what a cut under any other number owes. This bump labels the dev
track only.

**No consumer notes were owed.** Both scopes already carry their entries in the open
`plugin/CHANGELOG.md` section.

## 2026-09-25: reviews and Stop blocks cost what they earn

<!-- prawduct: type=feature | scope=review-friction -->

A survey of the sibling repos on 3.6.1-dev found three causes of review and Stop friction. Plan:
`.prawduct/artifacts/build-plan-review-friction.md`, which records the owner's four rulings of 2026-09-25.

**Mid-plan cumulatives.** `building.md`'s chunk close said "Commit, then Critic", while
`review-cycle.md` said a chunk review runs before committing and the consolidate directive said
"ONE commit, then verify". A builder who committed first left a clean tree, and rule 2 escalated to
a `cumulative`. That happened 33 times from 09-20 to 09-25. The router now answers `chunk`
mid-plan: 2+ unticked chunks of the plan found through the branch's scope. The interval starts at
the last reviewed commit, or at the merge-base when nothing is reviewed and nothing judgeable is
uncommitted (a plan tick or change-log line does not count). It answers
`deferred` when nothing is unreviewed. `critic_consolidate.working_tree_interval_base` is the one
owner of where the interval starts. The owner's stage ruling ("key on cycle position") is recorded
beneath the stage-keyed rigor clause in `nonfunctional-requirements.md`, which is otherwise
unedited. Four real puzzles states reproduce in a scratch clone and ran `cumulative` at the time. Three now answer
`chunk` and one `deferred`: a 61-file cumulative that had found 0 blocking findings. The other four states did not
reproduce in the clone.

**One fix order everywhere.** The chunk close is now review, fix, then commit, in `building.md`,
`review-cycle.md` and the consolidate directives. `_FIX_ORDER` in `critic_consolidate.py` is the one
sentence the batch directive, the if-you-fix-some advice and the blocking arm all compose, and the
post-`cumulative` exception is stated once beside it (`TestOneFixOrderEverywhere`).

**An explicit mode stands mid-plan.** `/prawduct:critic chunk` or `final` on a clean tree mid-plan
keeps the named mode over the unreviewed interval instead of redirecting to `cumulative`. With
nothing unreviewed, dispatch answers exit 3 (no review needed) rather than refusing. Every exit 3
records a `guard-refusal` fact, this one as `critic-dispatch-head-covered`. The Stop gate's advice
for unreviewed committed work asks the same interval owner, so it names `cumulative` when a chunk
review could not reach the commits (code in flight, nothing reviewed behind HEAD). A widened verify
pass is re-dispatched as `final` when `final`'s interval reaches the commits.

**Stop blocks on mid-work turns.** 17 of 32 critic/reflection blocks since 09-14 landed on turns
closing DO NOT CLEAR. The Stop payload carries `last_assistant_message` (Claude Code 2.1.282, found
by a live verify-api probe). `lib/standing_block.py` is now the one code home for the closing-block
labels, and the digest and session-hygiene prose are pinned to it. A DO NOT CLEAR verdict defers
reflection and critic-review through the existing STH-3W7F path. Anything ambiguous blocks. A
replay of every block since 09-14 through the detector: 14/14 DO NOT CLEAR turns defer, and 13/13
SAFE TO CLEAR turns plus the one unlabelled turn still block. Contract change: `stop` now reads
`last_assistant_message` (`api-contract.md` § Inputs & Outputs).

**Siblings ran this checkout.** A user-level `directory` marketplace pointed at the development
checkout, so sibling sessions ran unmerged, uncommitted work. It now points at a detached
`origin/develop` worktree. `documentation/release-process.md` describes that variant and its refresh step.

**Durations are clocked where a clock exists (#882, owner ruling: option 1).** The review fact body gains an
optional `dispatched_at` (UTC ISO-8601), written only when the critic dispatch mark belongs to this
review. `critic-consolidate` reads the mark without consuming it (`review_dispatch.peek`, one `_judge`
shared with `consume`), and the ledger still consumes it. The interval runs to the fact's `ts`
(`review_dispatch.fact_interval_seconds`). `coverage.count_branch_rounds` returns `measured` and
`estimated` (`{rounds, seconds}`), replacing `seconds`/`timed`, which had no reader outside the formatter
and tests. The gate's tally prints the clock first and never sums the two. The `review-stats` human line
leads with the clocked population. Its `--json` keys keep their meaning, so `schema_version` stays 7.
Contract change: `critic-consolidate` writes the new fact key (`api-contract.md`). Persisted schema:
`data-model.md`.

A clean-tree `chunk` that starts at the merge-base now says why it had no reviewed state to extend from. `gates.covered_frontier` names which clean `None` it
returned (`FRONTIER_ABSENT_*`), and `critic_consolidate.merge_base_start_reason` is the one renderer. An
open blocker on the nearest reviewed state is named with its remedy, never called "nothing reviewed".

Budget raises are declared with their price in `test_v5_methodology.py` and
`test_reviewer_payload_budget.py`.

## 2026-09-26: the suite-at-boundary release-note pin finds its own version section

<!-- prawduct: type=fix | scope=suite-at-boundary-note-window -->

v3.6.1's release opened an empty v3.6.2-dev section above the suite-at-boundary entry in
`plugin/CHANGELOG.md`, so `tests/test_suite_at_boundary.py`, which read the first section, went red
on `develop` at the cut with nothing else changed. The test now requires the note in exactly one
version section, with its default-change sentence beside it. The fix was built on
`fix/suite-at-boundary-note-window` and reaches `develop` inside the learnings-one-line PR, so it
does not need a review cycle of its own. Test-only: nothing changes for consumers.

## 2026-09-24: learnings are one line each, and core.md stays small

<!-- prawduct: type=feature | scope=learnings-one-line -->

The always-loaded learnings corpus had regrown for the fourth time: 107KB here, 139KB in discodon,
57KB in hallucinote and bankmachine. That is roughly 15–35k tokens in every session. Each earlier
pass had paired a one-off sweep with a control that could be walked around: an advisory nudge, a
per-rule length check that v2 deleted, an agent-raisable budget (six raises here in five days), an
agent-written waiver, and a migration credit that measured discodon's `core.md` against the 176KB
legacy file, so its growth never registered. This removes each bypass, owner-directed 2026-09-24. **Under `api-contract.md`'s versioning rule it is a minor (3.7.0):** it adds two blocking gates (`learnings-rule-too-long`, `learnings-rule-body`, registered `since: 3.7.0` in `gates.json`, so the version banner announces them), and it changes the `learnings_budgets.core.md` contract. The owner holds the release number for the cut (`develop` was marked 3.6.2-dev.1 after this merged, 2026-09-26). **If the cut ships this under any other number,** it must restamp both gates' `since` to that number, because the banner announces only gates whose `since` falls in the range a repo crosses. It must also record the departure from the versioning rule as a ruling on that norm, and rewrite this sentence.

**The format is enforced** (`record_lint`, the Stop gate, the Critic's severity table):
- Every rule is one line of at most 250 characters, with no body, in every rules file.
- `core.md` is capped at 12KB, and only an `owner_approved:` date on `learnings_budgets.core.md`
  raises it.
- A raise never counts in the interval that writes it.
- A compacted corpus blocks on any violation. One not yet compacted is frozen: no file over budget
  may grow, and every added line must already be a one-line rule.
  A line moved from one rules file to another is not added: the check reads the whole corpus at the base.
- The migration session is judged on the corpus total, replacing the per-file legacy credit.
- The Stop hook measures against HEAD when there is no base marker, instead of skipping.
- The `learnings-budget` waiver key is retired.
- The session briefing names an over-limit corpus with an agent directive.

**`prawduct-hook learnings-compact`** converts a corpus:
- `--plan` writes a worksheet (text, body, size, citations, candidate area files and related rows
  per rule).
- The agent records a decision per rule, and a drop needs the owner's approval date.
- `--apply` writes one-line rules as one revertible commit.
- A `learning.compacted` ledger event per rewritten rule keeps its citation history, and the Stop
  hook does not count a rewrite as a written rule.
- `/prawduct:doctor` runs the flow.

**The write-side guidance changed with it:** reflection Step 4, the Stop reflection blocker, the
janitor skill, the `core.md` scaffold, the budget template and `principles.md` all state the
one-line form. "Never trim a rule to fit" is gone. `nonfunctional-requirements.md` records the owner
exception to the state-file advisory norm, beneath the norm.

**Rulings move to the norm they rule on.** `plugin/docs/norms.md` said rulings live in the learnings
rules, linked from the norm. A ruling is a record a reader consults, not a rule every session
carries, and it cannot be one line. It now lives in the norm's `Rulings:` field, named `[[like-this]]`
and stated in full. Names are unchanged, so existing citations still resolve to their norm.

**This repo's own corpus is compacted** (owner-approved drop list, 2026-09-24):
- 338 units became 314 one-line rules, 17 merges, 5 rulings moved to their norms in `api-contract.md`
  and `architecture.md`, and 2 approved drops (a section heading, and a rule another rule
  supersedes).
- `core.md` went from 104KB to 9.4KB. Its self-raised 105KB budget entry is gone.
- The rules now live in eight area files, three of them new (`release.md`, `backlog.md`, `pr.md`)
  plus `gates.md` split from `hook-surface.md`.
- The tests that read this corpus now floor the whole corpus against an independent line count,
  instead of pinning a `core.md` size that compaction was always going to change.

**The PR reviewer sees a rise in `core.md`'s cap.** `owner_approved:` is text an agent can write, so
the PR review payload gains a `learnings_cap` section. It compares the cap in force at the merge-base
and at HEAD. A rise asks for the owner's approval to be quoted in the PR description, or it is a
WARNING. A lowered or removed override, which is what compaction does, is reported as not a rise.

## 2026-09-24: v3.6.1 is cut, and develop reopens on 3.6.2-dev

<!-- prawduct: type=chore | scope=release-v3.6.1 -->

**26 scopes and 27 change-log entries. `K = 0`, so this took the whole-develop promotion path with
nothing withheld.** `main` is at `e2a07086`. Tag `v3.6.1` was published with the CHANGELOG section as
its Release notes. `check-released v3.6.1` reports 3 of 3 verified, and the hand-dispatched
`verify-release` run is green. To re-derive the scope set, grep for `release=v3.6.1` in
`change-log.md` and `change-log-archive/`.

**A patch, as the owner named it.** `.prawduct/artifacts/release-plan-v3.6.1.md` records why the
bundle's weight did not argue for a minor. `learnings-one-line` stays off this release. It
registers its gates `since: 3.7.0`, but its branch does not touch the version files. Merging it
leaves `develop` on `3.6.2-dev` until someone bumps it on purpose, in that PR or at the 3.7.0 cut.

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
