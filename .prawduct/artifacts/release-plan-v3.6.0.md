# Release Plan — v3.6.0, Whole-Develop Promotion

**Status:** PREP ONLY as of 2026-09-20. By owner decision this cut runs the runbook's Phases 0–1
and stops at the **Checkpoint** after step 13 — `origin/develop` carries the whole release, and
nothing has reached `main` or any consumer. Phases 2–3 (promote, publish, verify, reopen `develop`)
are not authorized yet. Re-derive the current state with `git log --oneline origin/main -1` and
`prawduct-hook check-releasability --release v3.6.0`; do not read this paragraph as a measurement.

**Version:** v3.6.0 — **minor**, and the call is a recorded decision that *overturns a standing
ruling*, so both sides are written down.

The ratified norm (`operational-spec.md` `## Direction`, 2026-07-17, pointer row in
`project-preferences.md`) is *"Versioning is conservative: a small feature is a patch bump, not a
minor-per-feature."* Read alone it argues a patch. A patch is also what the repo had already
committed to: the owner ruled **3.5.1** on 2026-09-15 (recorded in
`build-plan-learnings-v2-docs.md` Chunk 05), `plugin/hooks/gates.json` carries three learnings
rows stamped `since: 3.5.1`, and `develop` has been running `3.5.1-dev.N` since 2026-09-17.

**Maintainer decision, 2026-09-20: minor (+0.1.0).** Raised as a framed decision before Phase 1,
with the standing 3.5.1 ruling as the named alternative; the maintainer chose the minor. The
reason the question was reopened at all is that **the 3.5.1 ruling priced three scopes and the
bundle now holds seventeen** — it was taken over the learnings-v2 program, and fourteen scopes
landed after it. Consequence of the change: the three `since: 3.5.1` rows in `gates.json` move to
`3.6.0`, so the version-delta banner announces those gates on the bump that actually ships them.

Supporting the minor reading — the runbook's unratified precedent reads *a substantial new
capability or a subsystem going live* as a minor, and warns explicitly against treating "not a
major" as "therefore a patch", which erases the minor tier:

- **A subsystem goes live and rewrites the consumer's repo on first session.** The learnings corpus
  leaves `.prawduct/learnings.md` for `.claude/rules/learnings/`, where the harness loads it; a
  skill and three verbs retire; the reflection gate widens to every session that wrote code, plan
  or no plan. This is the one change in the bundle that touches a consumer's tree without being
  asked.
- **Gate semantics move, on by default.** `review-stages` makes rigor stage-keyed and **retires the
  5-file coordinator fallback**, reversing two statements v3.2.2 made to consumers in as many
  words. Some changes that drew three reviewers now draw one.
- **A persisted format gains a one-way door.** `change-log-archive` moves shipped history into
  `.prawduct/change-log-archive/YYYY-MM.md`, and the notes carry an explicit downgrade caution: an
  older plugin reads only the live log, so a repo that has archived must not roll back past this
  release. A patch number tells a consumer rollback is safe while the notes tell them it is not —
  that asymmetry is the sharpest argument against 3.5.1 and it was decisive.
- **A new verb reaches the builder's hands.** `prawduct-hook disposition <review-id> O-n --accept`
  gives a non-blocking review finding a third disposition that did not exist on v3.5.0.

Not a major: no persisted format *breaks*. The evidence store's path and record shape are
unchanged, no consumer loses evidence, coverage or backlog state on upgrade, and the learnings
migration is a rewrite the plugin performs rather than a format the consumer must repair.

## Release classification

Seventeen release-pending scopes, **all shipping**. `check-releasability --release v3.6.0`
enumerates them; this table is the partition it grades against, and it is a partition rather than a
checklist — every release-pending scope appears exactly once and nothing appears that is not
release-pending.

| Scope | Disposition | Blocker |
|---|---|---|
| change-log-archive | ships | |
| critic-dispatch-clock | ships | |
| learnings-v2-core | ships | |
| learnings-v2-delete | ships | |
| learnings-v2-docs | ships | |
| mcp-quotation-audit | ships | |
| pr-review-payload | ships | |
| pr-step1-recorder | ships | |
| release-v3.5.0 | ships | |
| review-convergence | ships | |
| review-cost-decision | ships | |
| review-loop-termination | ships | |
| review-stages | ships | |
| review-stats-observations | ships | |
| review-yield-instrument | ships | |
| test-report-scope | ships | |
| test-status-clause | ships | |

**Nothing is withheld — `K = 0`, so this is a standard whole-develop promotion**, not a pruned one.
`K` is taken from the gate's own output, not from this file's prose.

**No blocker liveness to verify.** No row withholds anything, so `cannot-verify-blockers:` has no
subject and the gate did not raise it.

**Three advisory `WARNING: … has no build-plan file` lines are expected and do not block.** Each
names a scope that shipped as a small fix or as release mechanics that never earned a plan:
`pr-step1-recorder`, `review-stats-observations`, `release-v3.5.0`. Noted rather than suppressed.

## The pending set was derived twice and code-tested, not read positionally

Phase 1 step 2's per-candidate test was run over the whole file rather than above a boundary.

- The gate's scope list and an independent `grep`-histogram of untagged `scope=` keys return the
  **same 17 scopes over 20 entries**, with `0 unclassifiable`.
- Three entries are dated 2026-09-02/03, *before* the v3.5.0 cut on 2026-09-13 — exactly the shape
  a positional sweep gets wrong in both directions. The code test settles them: `v3.5.0`'s tree
  carries **none** of the three learnings gates in `plugin/hooks/gates.json`, no
  `.claude/rules/learnings/` path, and no `learnings-files` verb in `plugin/bin/prawduct-hook`
  (7 occurrences on `develop`). They are genuinely pending.
- That probe was run with a **positive control** — `plugin/skills/report-bug/`, which v3.5.0 did
  ship, returns 1 from the same `git ls-tree` query — so a zero is a measurement rather than a
  broken probe.
- `release-v3.5.0` is release-pending and that is correct, not a leftover: it is the `develop`
  reopen bookkeeping, which by construction happens *after* the tag it is named for.

Re-derive rather than citing these counts:

```
prawduct-hook check-releasability --release v3.6.0
grep -o '<!-- prawduct:[^>]*-->' .prawduct/change-log.md | grep -v 'release=' \
  | grep -oE 'scope=[A-Za-z0-9._-]+' | sort | uniq -c | sort -rn
```

## Digest coverage was walked by hand, because the mechanical check cannot answer it

`check-releasability` reports `digest coverage: 2 of 17`. **That is the documented false-positive
class, not a finding** — the check matches a scope's literal *name* in the section, and consumer
notes are written in consumer words, so only `test-report-scope` and `change-log-archive` happen to
be named. The runbook says to open the section and look. The walk, at this commit:

| Scope | Consumer note in `## v3.5.1-dev.2` |
|---|---|
| change-log-archive | "The change log stays bounded." |
| critic-dispatch-clock | "Critic reviews are now timed, not estimated." |
| learnings-v2-core | "Your learnings corpus moves, and this release deletes the old files." |
| learnings-v2-delete | "The learnings lifecycle verbs are deprecated and inert." + "`reflections.md` is no longer written." + "The learning loop measures itself." |
| learnings-v2-docs | "The reflection guide is about the learning loop again…" + "Ten portable rules the fleet kept re-learning…" |
| mcp-quotation-audit | **none, deliberately** — internal corpus-mining debt with no consumer surface |
| pr-review-payload | "The PR review is one payload call and a measured interval." |
| pr-step1-recorder | "`/prawduct:pr` Step 1 names the command that records a suite run…" |
| release-v3.5.0 | **none, by design** — release mechanics never have a consumer note |
| review-convergence | "When a written rule has no enforcer…" + "A `final` or `cumulative` reviewer now receives every learnings area file…" |
| review-cost-decision | "The close prices the fix/accept decision instead of asking you to." + "Two rules that caused over-fixing now carry a severity bound…" |
| review-loop-termination | "A review finding you decide not to fix can now be recorded instead." + "A clean verify pass no longer reads as branch clearance." |
| review-stages | "Review rigor is now stage-keyed…" + "A short plan now owes one boundary review…" + "A product is asked once where its risk lives." |
| review-stats-observations | covered inside the learnings-v2-delete schema note (`4 for the verify-pass observations counts`) |
| review-yield-instrument | "`review-stats` can window by date and report whether a finding ships a remedy." |
| test-report-scope | "Your test runner can make every run recordable" |
| test-status-clause | "`test-status` says which of its two disjuncts bought the exit 0." |

**Nine of these notes were written at this Phase 0**, for the six scopes from 2026-09-16 → 09-19
that had accumulated no consumer note at all. That is the failure mode Phase 0 names: v3.4.0 shipped
`tactical-efficiency` with no note because a section full of good notes reads as a finished section.

## Fitness evidence

Gathered 2026-09-20 on `develop` at `2b5c9bdc`.

- **Suite green** — recorded into the evidence store by `prawduct-hook test-evidence record` rather
  than asserted, against the repo's declared `test_command`. `check-releasability` reports
  `suite: green — tree-valid, and recorded this session`. Cite `prawduct-hook test-status` for the
  figures. **This grades the pre-prep tree and says so**; step 11a's re-run after the version and
  archive edits is the only control that reads the tree being tagged, and it is not optional — the
  v3.5.0 cut turned red there twice on a suite that had been green forty minutes earlier.
- **`develop` == `origin/develop`** at Phase 0 (the one unpushed commit was pushed first).
- **`active_build_plan` is already `null`**, so nothing has to be cleared before `plan-backfill`.
  Confirm rather than assume: the sweep refuses to archive the plan the pointer names, so a pointer
  left set is a plan left live.
- **No state migration that loses anything** — the learnings corpus is rewritten in place by the
  plugin; no consumer loses evidence, coverage or backlog state.

## Two plans stay live, for different reasons

`plan-backfill --apply` is expected to exit 1 with two plans under `NOT moving`. Neither is a
failed release step.

1. **`build-plan-branch-claim-multiplicity.md`** — unticked Chunk 04, refused on the Status-roster
   reason. This is the plan's own recorded decision and it is unchanged since v3.5.0: the box opens
   only when a sibling repo has actually run a session on the develop track, and this repo runs
   `operator_verification_required: false`, so no gate will ever raise it. Do not tick it to
   silence the advisory. Its `branch:` frontmatter also names a deleted branch, which is why the
   session briefing's staleness scan fires on it with two remedies that are both wrong here.
2. **`build-plan-learnings-v2-docs.md`** — unticked **Chunk 05, which *is* this release**. It
   cannot be ticked at the Phase 1 Checkpoint, because Phases 2–3 are exactly what it asks for
   ("Runbook Phases 0–3 complete with their checkpoints green"). It ticks when the promotion lands,
   and the plan archives on the same pass. Its `branch:` frontmatter likewise names a merged-away
   branch and draws the same staleness advisory.

## Deferred issues — prose, not table rows

A deferred *issue* is not a withheld *scope*, and the classification table has room only for the
second. Nothing built and sitting on `develop` is being held back, so the table has no `withheld`
row and `K` stays 0. The open items this cycle did not take are the pending backlog items on
`brookstalley/prawduct` — including **#724**, the review-cost program, whose remaining requirements
(R2/R4/R7/R8) are unclaimed and unpriced, and **#167**, which stays open after its implementation
was built and withdrawn in `review-convergence`. None of them has a change-log entry, so none is
release-pending, and a row for any of them would stop the release with
`nothing release-pending behind them` while wrongly routing Phase 2 to the pruned path.

## Cut-time reminders

The runbook owns the full procedure; these are the steps this repo has rediscovered at past cuts.

1. **Rename `## v3.5.1-dev.2` to `## v3.6.0`** in `plugin/CHANGELOG.md` — rename, never add a
   second section — and replace the seeded "Prerelease under test" first line with this release's
   headline. **Write the headline paragraph as one long unwrapped line**: the banner reads the
   section's first physical line, so a bold lead-in wrapped across two ships an unpaired `**` on
   the most-read line prawduct emits (measured at the v3.5.0 cut).
2. **This is a minor, so `README.md`'s `## Recent Changes` is in scope** — rewrite the section to
   cover this line rather than appending a per-release bullet.
3. **Bump all three version carriers**: `plugin/VERSION`, `plugin/.claude-plugin/plugin.json`,
   `pyproject.toml`. The version string is the marketplace update cache key — a promotion without
   it does not ship.
4. **Move the three `since: 3.5.1` rows in `plugin/hooks/gates.json` to `3.6.0`.** They were
   stamped under the superseded ruling; left alone, the banner announces the learnings gates at a
   version that never exists.
5. **Tag the shipped entries `release=v3.6.0`** using Phase 1 step 2's per-candidate code test over
   the whole file — not a positional sweep above the topmost `release=` boundary, and not a grep
   for the one scope you happen to remember.
6. **Step 11a is not bookkeeping.** `git add -A`, then re-record the suite, before the prep commit.
