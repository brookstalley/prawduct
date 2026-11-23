# Release Plan — v3.9.0

**Status:** COMPLETE as measured 2026-11-22: `main` promoted at `e2ff6a0b`, tag and Release
`v3.9.0` published in one call, `check-released v3.9.0` verified 3 of 3, develop reopened on
`3.9.1-dev`. Owner go-ahead: 2026-11-22 ("yes to all"; version "yes 3.9.0"). Re-derive rather than
reading this as a measurement: `prawduct-hook check-released v3.9.0`.

**Version:** v3.9.0, a **minor**, confirmed by the owner 2026-11-22. The first go-ahead named
v3.8.2; reading the 56 pending scopes (57 with one found during the cut) changed the recommendation, and the owner agreed. Two of them break what a consumer runs:
- `release-fragments-only` (#1125): releases and the PR gate read change fragments only, and refuse
  a `.prawduct/change-log.md` that still holds an unreleased entry.
- `retire-chunk-status-shims`: `critic-begin --chunk` is gone, so `--chunks` is required.
Others change behaviour a consumer sees: `pr-reviewer-fold` (no PR reviewer), `retire-three-principles`
(the principles roster) and `asks-last` / `audit-guidance` (the turn close).
Precedent (runbook "Before you start") has treated a gate-semantics break as a major and a
substantial capability as a minor. Conservative versioning (`operational-spec.md` `## Direction`)
argues against a major. The v3.8.1 reopen fragment already anticipated this cut as a minor
("if the fragment-only release (#1125) ships as a minor"), and v3.8.1's headline gave consumers
one release of warning. A minor is the conservative reading that still tells consumers something
broke.

## Release classification

| Scope | Disposition | Blocker |
|---|---|---|
| advisory-evidence-pins | ships | |
| asks-last | ships | |
| audit-guidance | ships | |
| backlog-service | ships | |
| blind-sheet | ships | |
| blind-verification-join | ships | |
| bounded-cumulative | ships | |
| branch-review-one-owner | ships | |
| branch-review-set | ships | |
| chunk-credit-merged-verified | ships | |
| ci-testament | ships | |
| class-finding-members | ships | |
| clear-verdict-delegates | ships | |
| closes-cache-miss | ships | |
| coherence-pass | ships | |
| control-check-field | ships | |
| critic-trim | ships | |
| delegate-scratch-and-revisit-wording | ships | |
| detached-refresh-outcome | ships | |
| evidence-graph-once | ships | |
| exit1-covering-mode | ships | |
| gate-clarity | ships | |
| gate-flags-fail-closed | ships | |
| gate-review-concurrency | ships | |
| gate-span-and-coverage-slips | ships | |
| git-tidy-submodule-worktrees | ships | |
| gitignore-contract-semantics | ships | |
| import-status-remove-block | ships | |
| late-requirement-capture | ships | |
| ledger-outcomes | ships | |
| measure-record-findings | ships | |
| none-reason-wraps | ships | |
| native-review-inner | ships | |
| native-review-paired | ships | |
| native-review-parse | ships | |
| operator-verification | ships | |
| pin-native-trees | ships | |
| post-fix-rule-one-home | ships | |
| pr-reviewer-fold | ships | |
| pre-dispatch-notice-one-owner | ships | |
| pushed-branch-never-prd | ships | |
| read-cost-review | ships | |
| release-fragments-only | ships | |
| release-v3.8.1 | ships | |
| retire-chunk-status-shims | ships | |
| retire-three-principles | ships | |
| review-never-moves-head | ships | |
| review-round-cost | ships | |
| reviewer-model-cap | ships | |
| round-tally-at-next-action | ships | |
| stop-span-bash-authorship | ships | |
| subprocess-utf8-decoding | ships | |
| test-evidence-no-stale-green | ships | |
| testament-evidence-wiring | ships | |
| testament-evidence-wrapper-scripts | ships | |
| verify-coverage-stub-remedy | ships | |
| verify-resolutions-lineage | ships | |

## Notes

- Nothing is withheld, so `K = 0` and Phase 2 promotes the whole of `develop`.
- `release-v3.8.1` is the fragment the v3.8.1 reopen commit added. It is pending by design and
  ships here.
- Many scopes shipped to `develop` without a build plan, and `check-releasability` warns about
  each one. That is accepted, as at v3.8.1: the work is merged and reviewed, and a plan written
  afterwards would describe nothing a reader needs.
- `build-plan-backlog-roi-2026-11-18.md` and `build-plan-backlog-roi-wave2-2026-11-18.md` have
  no fragment under their own scope: their work shipped under the item scopes above. So
  `plan-backfill` does not sweep them, and step 11 archives them by hand. Wave 1 reports chunks
  02–05 and 07–10 `open` because those delegates' commit subjects lacked the plan scope, so no
  span credits them. The work is built and covered by the integration branch's cumulative review
  (rev-20261118T232657Z-72818172, merged in #1206). It is archived `--state completed` with that
  reason, as the runbook directs for a completeness refusal.
- `none-reason-wraps` was found and fixed during this cut: the Phase 1 preview published three
  wrapped `none:` notes as consumer text. It ships here.
- Step 10 (minor bump): `README.md` re-read against this release. Its prerequisites, install and
  onboard steps, commands and "How it works" are still true; `pr-reviewer-fold` had already updated
  the `/prawduct:pr` line. No change.
- Step 11: `plan-backfill --apply` archived 12 plans. Both backlog-ROI plans were archived by hand
  with `archive-plan --state completed --release v3.9.0`; wave 1 records 8 of 11 chunks
  `unbuilt_at_archive`, for the reason given above.
