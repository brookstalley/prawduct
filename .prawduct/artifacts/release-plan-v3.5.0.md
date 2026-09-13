# Release Plan — v3.5.0, Whole-Develop Promotion

**Status:** IN PROGRESS. Phase 0 completed 2026-09-12 on `develop` at `90f04b91`.

**Version:** v3.5.0 — **minor**, and the call is a recorded decision rather than a reflex, because
the ratified norm pulls the other way. The norm (`operational-spec.md` `## Direction`, 2026-07-17,
pointer row in `project-preferences.md`) is *"Versioning is conservative: a small feature is a patch
bump, not a minor-per-feature."* Read alone that argues v3.4.1, which is also the number `develop`
has been running as its `-dev` marker since the v3.4.0 cut.

**Maintainer decision, 2026-09-12: minor (+0.1.0).** Raised as a framed decision before cutting,
against the alternative of the patch the `-dev` marker implied; the maintainer chose the minor.

Supporting the minor reading — the runbook's unratified precedent reads *a substantial new
capability or a subsystem going live* as a minor, and warns explicitly against treating "not a
major" as "therefore a patch", which erases the minor tier:

- **A subsystem goes live, and it is the first one that sends bytes off the machine to a foreign
  owner.** `/prawduct:report-bug` is rewritten onto the `file-upstream` adapter: it recomposes a
  report in prawduct's terms, previews the exact outbound payload, and files an issue on prawduct's
  own public tracker on a human's approval of those bytes. Five independent refusal checks guard the
  send path and identity fails closed. This is not a feature inside an existing surface — it is a
  new egress surface, and it carried a norm amendment to ship (`security-model.md` § Direction moves
  `in-transition` → `steady-state`; `architecture.md`'s Local-first norm admits a second network
  surface as a recorded, vetoable decision).
- **Gate semantics move, on by default.** `review_round_budget` — six full review rounds per
  build-plan scope — is a *declared stop* where the review loop previously had none. A review can now
  be refused for a reason that did not exist on v3.4.0. Consumers' sessions will gate differently.
- **What a review RATES changes shape.** The subject/oracle split narrows the set of files a finding
  may be *about* to judgeable paths while still delivering the rest to every reviewer to read — 39%
  of file-slots and 36% of findings were in the shed class — and every finding now carries a
  `fix_cost` saying whether acting on it buys a round.
- **A new methodology guide ships** (`/prawduct:methodology delegation`) with a project-authored
  delegation policy in `project-preferences.md`, and `/prawduct:doctor` proposes one from what the
  repo already encodes.

Not a major: no persisted format breaks. The evidence store's path and record shape are unchanged,
no consumer state is rewritten on upgrade, and the two deprecations in this line (`bug-inbox`)
retire through the inert-retention window rather than by removal.

## Release classification

Thirty-two release-pending scopes, **all shipping**. `check-releasability --release v3.5.0`
enumerates them; this table is the partition it grades against, and it is a partition rather than a
checklist — every release-pending scope appears exactly once and nothing appears that is not
release-pending.

| Scope | Disposition | Blocker |
|---|---|---|
| adhoc-delegation | ships | |
| audit-followups | ships | |
| backlog-burndown-2026-09 | ships | |
| backlog-metadata | ships | |
| branch-claim-multiplicity | ships | |
| branch-pushed-gate | ships | |
| change-log-gate | ships | |
| closing-keyword-classifier | ships | |
| coverage-socket-1-docs | ships | |
| critic-mode-field-parse | ships | |
| delegation | ships | |
| gate-accuracy | ships | |
| instruction-surface-truth | ships | |
| manifest-state-diagnosis | ships | |
| norm-lifecycle-stopgaps | ships | |
| plugin-absent-governance-anchor | ships | |
| pr-evidence-reviewed-commit | ships | |
| pr-issues-backend-close | ships | |
| pr-push-head-divergence | ships | |
| release-gate-blindness | ships | |
| release-v3.4.0 | ships | |
| review-loop-termination | ships | |
| shipped-merge-check | ships | |
| silent-clear-checks | ships | |
| silent-governance-failures | ships | |
| small-batch-2026-09-02 | ships | |
| test-location-nested-checkout | ships | |
| upstream-filing-adapter | ships | |
| upstream-intake-repoint | ships | |
| upstream-report-bug | ships | |
| verification-drain-half-write | ships | |
| verify-resolutions-exit3 | ships | |

**Nothing is withheld — `K = 0`, so this is a standard Phase 2 whole-develop promotion**, not a
pruned one. `K` is taken from the gate's own output, not from this file's prose.

**Blocker liveness was not machine-verified, and that is expected.** This repo runs the GitHub
Issues backlog, so `.prawduct/backlog.md` is frozen history and `check-releasability` reports
`cannot-verify-blockers:` by design. No row withholds anything, so there is no blocker to
hand-confirm — the check has nothing to withhold on. Every other check in the gate still ran.

**Fifteen advisory `WARNING: … has no build-plan file` lines are expected and do not block.** Each
names a scope that shipped as a small fix, a batch, or release mechanics that never earned a plan:
`pr-push-head-divergence`, `closing-keyword-classifier`, `coverage-socket-1-docs`,
`audit-followups`, `critic-mode-field-parse`, `shipped-merge-check`, `change-log-gate`,
`backlog-burndown-2026-09`, `norm-lifecycle-stopgaps`, `pr-evidence-reviewed-commit`,
`pr-issues-backend-close`, `test-location-nested-checkout`, `manifest-state-diagnosis`,
`backlog-metadata`, `release-v3.4.0`. Noted rather than suppressed.

## Deferred issues — prose, not table rows

A deferred *issue* is not a withheld *scope*, and the classification table has room only for the
second. Nothing built and sitting on `develop` is being held back, so the table has no `withheld`
row and `K` stays 0. The open items this cycle did not take are the 165 pending backlog items
(3 untriaged at cut time), including the audit follow-ups filed as #776–#787 — none of them has a
change-log entry, so none of them is release-pending, and a row for any of them would stop the
release with `nothing release-pending behind them` while wrongly routing Phase 2 to the pruned path.

## Fitness evidence

Gathered 2026-09-12 on `develop` at `90f04b91`.

- **Suite green** — zero failures, recorded into the evidence store by
  `prawduct-hook test-evidence record` rather than asserted. Cite `prawduct-hook test-status` for
  the figures; a total copied into prose here is one more carrier to keep in sync and nothing reads
  it.
- **`develop` == `origin/develop`** at Phase 0; the only uncommitted file was the
  `backlog_last_groomed_at` stamp, which rides in the prep commit.
- **One plan is deliberately not closed out**, and it is the only unticked box across all seventeen
  live plans — see below. The other sixteen have every `## Status` chunk ticked.
- **No state migration** — no consumer loses evidence, coverage or backlog state on upgrade.
- **A prior release's audit is part of the evidence.** Five read-only auditors graded twenty-three
  of these scopes against their code, tests and plans (`audit-develop-since-v3.4.0.md`): five
  complete, sixteen complete with nits, two incomplete, none defective, every scope's tests
  confirmed red against v3.4.0. Three findings that would have failed or degraded this cut were
  fixed before it rather than filed.

## `branch-claim-multiplicity` ships with Chunk 04 open, and the notes say so

`build-plan-branch-claim-multiplicity.md` keeps an unticked Chunk 04 — *"Release notes and a
develop-track dogfooding path for sibling repos"* — and that is the plan's own recorded decision,
not an oversight. The release notes and the dogfooding recipe are written; what is missing is that
**nobody has yet run a session on the develop track**, because the recipe installs from `ref:
develop` and could not be exercised until it merged. The plan says in as many words: *do not tick
Chunk 04 to silence the advisory — that trades a noisy-but-true advisory for a false record*, and
*a release cut before then should say in its notes that the track is undogfooded*. This release
does say so, in `plugin/CHANGELOG.md`.

Two mechanical consequences, both expected here:

- `plan-backfill --apply` **refuses** this plan with the Status-roster reason and leaves it live.
  That is the correct outcome — the plan is not dead, it has an open obligation — and it is the one
  refusal `archive-plan` does not share. Neither remedy the sweep offers (tick, or
  `--state superseded`) applies; the correct action is VRF-017, then a tick, folded into the next
  PR that touches the repo.
- The session briefing's staleness scan will keep firing on `develop`, because the plan declares a
  `branch:` that no longer exists and has a chunk left. Both remedies it prints are wrong here.
  This is the first live instance of the feature's own advisory misdirecting, and the plan carries
  that as its durable home.

## Cut-time reminders

The runbook owns the full procedure; these are the steps this repo has rediscovered at past cuts.

1. **Rename `## v3.4.1-dev.2` to `## v3.5.0`** in `plugin/CHANGELOG.md` — rename, never add a second
   section — and replace the seeded "Prerelease under test" first line with this release's headline.
   Phase 0 warned on exactly this: the v3.4.0 cut went out still leading with the seed after eight
   weeks of good notes had accumulated underneath it, because a section full of good notes reads as
   a finished section.
2. **This is a minor, so `README.md`'s `## Recent Changes` is in scope** — rewrite the current
   `### 3.1–3.4` section to cover this line rather than appending a per-release bullet.
3. **Bump all three version carriers**: `plugin/VERSION`, `plugin/.claude-plugin/plugin.json`,
   `pyproject.toml`. The version string is the marketplace update cache key — a promotion without it
   does not ship.
4. **`active_build_plan` is already `null`**, so nothing has to be cleared before `plan-backfill`.
   Confirm rather than assume: the sweep refuses to archive the plan the pointer names, so a pointer
   left set is a plan left live.
5. **Tag the shipped entries `release=v3.5.0`** using Phase 1 step 2's per-candidate code test over
   the whole file — not a positional sweep above the topmost `release=` boundary, and not a grep for
   the one scope you happen to remember.
