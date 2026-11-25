# Release Plan — v3.10.0

**Status:** in progress (2026-11-25).

**Version:** v3.10.0, a **minor**, confirmed by the owner 2026-11-25 ("yes to all of your
recommendations", `.prawduct/owner-rulings.md`). Conservative versioning (`operational-spec.md`
`## Direction`) makes a minor a recorded decision, not a reflex; the reason it is one here:
- `test-determinism` adds a blocking class to the boundary review: a change that adds a first-party
  import to a root `conftest.py`, an autouse fixture that imports first-party code, or a package
  `__init__.py` importing every submodule now blocks a consumer's merge. Release history has
  treated a new capability that changes what a consumer's review can block as a minor, not a patch.
- Three more scopes are features (`static-content`, `boundary-coverage-check`,
  `pick-log-names-item`), and `tripwire-disabled` changes the committed tripwire hook text, so every
  governed repo's doctor reports it stale until `install-tripwire --apply`.
Nothing breaks a persisted format or removes a command, so it is not a major.

## Release classification

| Scope | Disposition | Blocker |
|---|---|---|
| alignment-yield-windows | ships | |
| boundary-coverage-check | ships | |
| chunk-plan-order | ships | |
| credential-placeholders | ships | |
| delegate-ceiling-whole-tree-guards | ships | |
| dispositions-travel | ships | |
| free-interval-warnings | ships | |
| handoff-notes-persist | ships | |
| live-review-writes | ships | |
| pick-log-names-item | ships | |
| recorder-temp-session-file | ships | |
| release-v3.9.0 | ships | |
| report-bug-triage-sync | ships | |
| review-chain-merge-base | ships | |
| round-budget-cadence | ships | |
| scan-and-staging-classes | ships | |
| static-content | ships | |
| stop-final-nudge | ships | |
| test-determinism | ships | |
| testament-cache-areas | ships | |
| testament-cache-blockers | ships | |
| tripwire-disabled | ships | |
| verify-links-review-id | ships | |
| yaml-inline-comment | ships | |

## Notes

- Nothing is withheld, so `K = 0` and Phase 2 promotes the whole of `develop`.
- `release-v3.9.0` is the fragment the v3.9.0 reopen commit added. It is pending by design and
  ships here.
- `handoff-notes-persist` (#1238) and `tripwire-disabled` (#1246) were built for this release on
  the owner's ruling of 2026-11-25, and merged as #1248 and #1249.
- Scopes that shipped to `develop` without a build plan draw a `check-releasability` warning each.
  Accepted, as at v3.9.0: the work is merged and reviewed.
- `check-releasability` notes `tripwire-disabled` as uncovered. It was reviewed: boundary review
  rev-20261125T230216Z-7af05777 and verify pass rev-20261125T231645Z-d07f7323, and the PR gate passed
  #1249 by carrying that coverage across the branch's `develop` sync. `check-boundary-coverage` does
  not apply that transfer; filed as #1250. `release-v3.9.0` reads `direct`: it is the v3.9.0 reopen
  commit, version files only.
- Phase 1: two fragments (`alignment-yield-windows`, `testament-cache-areas`) wrote their consumer
  note as "None. …" rather than `none: …`, which the cut would have published as consumer text;
  corrected before the cut. The four `none:` reasons were read and are true.
- Step 10 (minor bump): `README.md` re-read. Still true; one sentence added under
  `/prawduct:repo-disable`, since a governed repo switched off now hears so from the tripwire at
  each session start (`tripwire-disabled`).
- Step 11: `plan-backfill --apply` archived 9 plans.
