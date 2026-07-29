# Release Plan — v3.2.0, Whole-Develop Promotion

**Status:** **NOT YET SHIPPED — this is the plan, authored 2026-07-29.** Phase 0 of
`runbooks/cut-and-publish-a-plugin-release.md` reads the classification table below; nothing here is
evidence that a release happened. The status line flips at publish, with the tag and `plugin/VERSION`
recorded like v3.1.2's.

**Version:** v3.2.0 — **minor**, and the reasoning is inherited rather than invented. v3.1.2's own plan
recorded: *"The bundle is a feature … plus two fixes, but the subsystem that would have made this a minor
is **withheld** (below), so a patch is the honest number."* That subsystem — the GitHub-Issues backlog
service — **ships in this release**. The condition the previous plan named as the only thing holding the
number down is gone, so a minor is the honest number by the same conservative-versioning norm
(`operational-spec.md` § Direction). Owner-decided 2026-07-29.

**Promotion shape:** **whole-develop (non-pruned).** Every release-pending scope ships; nothing is
withheld. Owner decision 2026-07-29, confirming the standing Option A.

## Release classification

Read by `prawduct-hook check-releasability --release v3.2.0`. `ships` = goes out in this release;
`withheld` would require a named open blocker id. Nine scopes, all shipping.

| scope | disposition | blocker |
|---|---|---|
| release-readiness | ships |  |
| coverage-perf | ships |  |
| chunk-refs-gate | ships |  |
| critic-disposition | ships |  |
| review-loop-termination | ships |  |
| skills-cutover-awareness | ships |  |
| backlog-skill-repoint | ships |  |
| backlog-service-v1 | ships |  |
| v3.2.0-golive | ships |  |

**Withheld: none.** That is the load-bearing consequence — `check-releasability` must report **0
withheld**, and Phase 2 therefore takes the **whole-develop** path. See *Promotion mechanics* below.

## What ships

**The release-governance bundle** — the work that made this classification table possible in the first
place.

- **`release-readiness`** — Phase 0 releasability gate (`check-releasability`), the durable
  `promote-a-pruned-release.md` runbook, and the amended promotion norm (REL-8P6M a–d, f). Also carries
  the historical `release=` backfill that unblocked this plan.
- **`coverage-perf`** — the composed-coverage gate stops being quadratic.
- **`chunk-refs-gate`** — `verify-chunk-refs` sees the right chunk and only real deliverables.
- **`critic-disposition`** — findings are dispositioned rather than filed.
- **`review-loop-termination`** — the review loop gains an exit condition; the builder was previously the
  only thing that could end it.

**The backlog-service programme** — withheld by v3.1.1 *and* v3.1.2, shipping here.

- **`backlog-service-v1`** — GitHub Issues as the backlog system-of-record (`plugin/lib/backlog/`).
- **`backlog-skill-repoint`** — `/prawduct:backlog` repointed onto the Issues adapter.
- **`skills-cutover-awareness`** — the PR path, janitor Backlog Health and backlog checks stop being
  silently wrong post-cutover.
- **`v3.2.0-golive`** — the go-live bundle, including the completeness gate that counted the items it
  promised to name.

## It ships dormant — verified, not asserted

The backlog service lands **inert** in every consuming repo. Routing is opt-in per repo on the
`backlog_service_repo` key:

- `plugin/lib/backlog_probes.py` gates routing on `bool(state.get("backlog_service_repo"))` — unset means
  the markdown backend, unchanged.
- `plugin/lib/init_product.py` writes `backlog_service_repo: None` for newly onboarded products.
- `prawduct-hook advisory list` reports no active advisories, so the migration advisory does **not** fire
  on upgrade. The backlog advisory stays **HELD**.

So a repo that upgrades to v3.2.0 and does nothing sees no behaviour change in its backlog. Lifting the
hold is a later release, gated on BKL-2Q7F / BKL-8V3D / BKL-5N9W and on migrating prawduct's own backlog.

## Promotion mechanics

Non-pruned, so this release uses `cut-and-publish-a-plugin-release.md` **Phase 2 steps 14–20** — the
tree-set path — and **not** `promote-a-pruned-release.md`.

Content-identity between `main` and `develop` **is** the expected completion test here. Under the amended
norm that is not the invariant but the *outcome* of a whole-develop promotion — the binding property is
the partition, and with zero withheld the partition degenerates to content-identity. Step 17's check
applies unchanged.

**Two consequences recorded rather than discovered later:**

1. `promote-a-pruned-release.md` is **not exercised** by this release, so both runbooks keep
   `last_verified: null` and **REL-3K9P stays open**. Expected, not an oversight — its trigger is a
   promotion *shape*, and this release is the other shape.
2. This is the first release whose entry gate is Phase 0 rather than a tree diff. The `## When to use
   this` scope test and Phase 0 both run `check-releasability`; expect the entry invocation to exit **1**
   with `no-release-plan:` **only until this file exists** — once it does, the entry test reports
   `releasable:`/`not-releasable:` instead. Both name the scope list; neither means "nothing to cut."

## Verification evidence

Recorded at plan time; the release run re-checks all of it (Phase 0 is authoritative, not this list).

| check | state at 2026-07-29 |
|---|---|
| test suite | 2849 passed / 0 failed / 7 skipped |
| `check-releasability --release v3.2.0` | blocked on this file's absence — re-run after it lands |
| `regen-views --check` | passes (fails closed on any statusless scope lacking a build plan) |
| `verify-chunk-refs` | ok |
| `check-cumulative-critic` | satisfied on the release-readiness bundle at merge (PR #143) |
| historical `release=` backfill | 18 entries across `v1.4`/`v1.5`/`v1.5.1` (PR #144) |

## Done when

1. `check-releasability --release v3.2.0` reports **releasable** with **0 withheld**.
2. Every one of the nine scopes above carries `release=v3.2.0 | status=shipped` in `change-log.md`.
   **By hand, across all scopes** — REL-8P6M part (e) is held, so nothing automates this, and the sweep's
   selection rule is wrong in three known ways (REL-7D4X). Walk *Phase 0's enumeration*, not a re-grep.
3. `plugin/VERSION` = `3.2.0`, bumped **as part of the release** (Phase 1 step 7), never hand-bumped early.
4. `regen-views` run, so derived views and build-plan `## Status` boxes reflect the release.
5. `main`'s tree is content-identical to `develop`'s — the whole-develop test, valid *because* nothing is
   withheld.
6. `git ls-remote --tags origin` shows `refs/tags/v3.2.0`.
7. This file's **Status** line updated with the tag, the `main` sha and the published `plugin/VERSION`.
8. `git -C ~/source/prawduct pull` — the installed plugin checkout is a *different* worktree on `main` and
   does not update itself.
