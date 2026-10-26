# Release Plan — v3.8.0

**Status:** DRAFT, opened 2026-10-25 to record a release requirement before the cut. Phase 0 has
not run. The classification below is incomplete by design: the cut-and-publish runbook's Phase 1
completes it, row by row, against `prawduct-hook check-releasability --release v3.8.0`.

**Version:** v3.8.0, a **minor**, provisionally. `plugin/VERSION` reads `3.8.0-dev` on `develop`
(2026-10-25), and the release requirement below adds a project-state key (`consumer_digest:`) and
new cut behavior for governed products. Phase 1 re-derives the tier from the final scope set.
This draft's number does not decide it (release.md).

## Release requirements

These must ship in v3.8.0. If one cannot, the owner decides whether to hold the release or move
the requirement. The cut does not decide it.

- **`consumer-digest`**: #733, which #1069 folded into (owner, 2026-10-25). One declared
  changelog, read at Phase 0 and written at the cut, so a governed product's consumer notes reach
  its own changelog. Requirements: `documentation/issues/733-requirements.md`. The build plan
  lives on `feature/733-consumer-digest`.

**How this is enforced, not just stated.** Each requirement has a `ships` row in the table below
before its work merges. Until the scope's fragment reaches `develop`, `check-releasability
--release v3.8.0` refuses with "classified scope(s) with nothing release-pending behind them",
naming it. So the release cannot pass Phase 0 while a requirement is missing. Do not delete such
a row to get past that refusal. Deleting it is the decision this section reserves for the owner.

## Release classification

Every row must account for one release-pending scope. Phase 1 adds the rest.

| Scope | Disposition | Blocker |
|---|---|---|
| consumer-digest | ships | |
