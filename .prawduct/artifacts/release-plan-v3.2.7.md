---
artifact: release-plan
version: 1
release: v3.2.7
last_validated: 2026-08-07
---

# Release plan — v3.2.7

A patch release. Four merged-and-unreleased PRs, all shipping; nothing withheld.

## Release classification

| Scope | Disposition | Blocker |
|---|---|---|
| backlog-title-enforcement | ships | |
| gate-as-dispatcher | ships | |
| critic-review-identity | ships | |

**Owner decision 2026-08-07: all scopes ship, all PRs included.** No scope is
withheld, so `K = 0` and Phase 2 takes the whole-tree promotion shape.

## The fourth PR, and why it is not a row above

**#615 (`fix/backlog-import-title-boundary`) is in this release and is not in the
table**, because `check-releasability` cannot see it: its change-log entry carries
`<!-- prawduct: type=fix -->` with no `scope=` key, so it is invisible to the
gate's scope enumeration. That is the REL-2N8K shape — the one that shipped 8 of
10 entries unrecorded at v2.0.14 — caught here rather than after the fact.

The table is required to be an exact partition of the **gate-visible**
release-pending scopes, so adding a row for a scope the gate does not enumerate
would fail the gate on "nothing appears that is not release-pending". The entry is
therefore stamped `release=v3.2.7 | status=shipped` directly, which is what makes
"what did v3.2.7 carry?" answerable from the record.

Whether it also gets a `scope=` tag is decided empirically at Phase 1 (owner
ruling: test, do not guess): tag it, run `regen-views`, and read the exit code.
`views._declares_non_build_plan_artifact` skips that branch's only artifact
(`artifact: discovery`, not `build-plan`), so the scope may resolve to no plan and
take the scope-local exit-3 path — a release blocker. Exit 0 keeps the tag; exit 3
drops it and keeps the release/status stamps.

## Verification recorded by hand

`check-releasability` reports `cannot-verify-blockers` on this repo (GitHub Issues
backend — `backlog.md` is frozen history), so blocker liveness is confirmed by
hand. **Nothing is withheld in this release, so there are no withholding blockers
to confirm.** Every other check the gate runs still applies.
