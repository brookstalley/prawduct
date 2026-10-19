# Release Plan — v3.7.1, Whole-Develop Promotion

**Status:** IN PROGRESS. Phase 0 classified the set and Phase 1 prepared `develop` on 2026-10-19:
27 entries tagged `release=v3.7.1`, 13 plans archived, versions bumped. Re-derive rather than
reading this paragraph as a measurement: `prawduct-hook check-releasability --release v3.7.1`.

**Version:** v3.7.1, a **patch**, by owner decision (2026-10-19: "3.7.1, we're conservative
here"). The agent recommended 3.8.0 on release-history precedent: the alignment pass changes how
the agent behaves in every governed session, and `clear-reason` is a new default-on gate
(`plugin/hooks/gates.json`, `since: 3.7.1`). The owner chose the ratified conservative-versioning
norm (`operational-spec.md` § Direction) over that unratified minor-tier precedent. The facts that
support a patch: everything else new is opt-in or backward-compatible. Telemetry contribution is
off unless the owner opts in. The `AGENTS.md` anchor move rewrites nothing without
`reanchor --apply`. Plans that still carry Requirements Confidence are still accepted. The
`since: 3.7.1` gate stamp matches the cut number, so the banner announces the gate on the
v3.7.0 → v3.7.1 crossing.

## Release classification

Every release-pending scope ships. Phase 1 step 2's per-candidate test ran over all 26 untagged
entries present before #1019 merged. No entry's heading appears in the v3.7.0 tree's change log
or its archive. The control matched two headings tagged `release=v3.7.0` against that same tree.
`backlog-file-path` merged afterwards (#1019) and is new since v3.7.0 by construction: its branch
forked after the cut. `release-v3.7.0` is the post-cut reopen commit.

No open issue is a release blocker.

| Scope | Disposition | Blocker |
|---|---|---|
| agents-md-anchor | ships | |
| backlog-file-path | ships | |
| consolidate-trigger | ships | |
| critic-tree-unchanged | ships | |
| delegate-isolation-dispatch | ships | |
| dev-track-bump-3.7.1-dev.1 | ships | |
| dev-track-bump-3.7.1-dev.2 | ships | |
| empty-verify-rounds | ships | |
| field-bugs-2026-10 | ships | |
| field-bugs-790-813-765-915 | ships | |
| governance-roi-study | ships | |
| junit-unreached-963-strip-code-966 | ships | |
| learnings-migrate-punctuation-930 | ships | |
| norm-inline-why | ships | |
| post-discovery-friction | ships | |
| release-v3.7.0 | ships | |
| requirements-alignment | ships | |
| requirements-alignment-w2 | ships | |
| self-citing-clear | ships | |
| telemetry-aggregate | ships | |
| telemetry-collector | ships | |
| telemetry-contribution | ships | |
| telemetry-stats | ships | |
| test-git-maintenance-race | ships | |
| testament-onboarding | ships | |
| transfer-pruned-trees | ships | |
| upstream-intake-enumeration | ships | |

**Nothing is withheld, so `K = 0`** and this is a standard whole-develop promotion. `K` is taken
from the gate's own output.

## Digest coverage

Before this cut, the gate's scope-name match found 10 of the 26 pre-#1019 scopes in the open
`plugin/CHANGELOG.md` section. Walking the rest by hand:

- **Already noted when merged:** `backlog-file-path` (#1019 wrote its note).
- **Notes written at this cut** (consumer-visible): `norm-inline-why`, `empty-verify-rounds`, `consolidate-trigger`, `critic-tree-unchanged`,
  `delegate-isolation-dispatch`, `requirements-alignment-w2`, `field-bugs-2026-10`,
  `telemetry-aggregate`, `transfer-pruned-trees`.
- **No consumer note owed:**
  - Release mechanics: `dev-track-bump-3.7.1-dev.1`, `dev-track-bump-3.7.1-dev.2`, `release-v3.7.0`.
  - Test-only: `test-git-maintenance-race`.
  - Repo-internal, outside the distributed `plugin/` tree: `testament-onboarding` (this repo's
    test pool), `governance-roi-study` (a `.prawduct/` research artifact) and
    `telemetry-collector` (`collector/`, deployed from the owner's account). The contribution
    note already tells consumers where reports go.

## Plans

Live plans declaring a shipping scope: `agents-md-anchor`, `backlog-file-path`,
`empty-verify-rounds`, `field-bugs-2026-10`, `post-discovery-friction`, `requirements-alignment`
(`build-plan-requirements-alignment-w1.md`), `requirements-alignment-w2`, `self-citing-clear`,
`telemetry-aggregate`, `telemetry-collector`, `telemetry-contribution`, `telemetry-stats` and
`testament-onboarding`. To find them, grep `.prawduct/artifacts/*.md` for a `scope:` line.
`requirements-alignment-discovery.md` also declares `scope: requirements-alignment`. It is a
discovery artifact, not a build plan, so the sweep's handling of it is checked at Phase 1 rather
than assumed. `active_build_plan` is already `null` on `develop`.
