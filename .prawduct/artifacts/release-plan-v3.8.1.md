# Release Plan — v3.8.1

**Status:** in preparation, 2026-11-10. Owner go-ahead for the release: 2026-11-10 ("Yes to
3.8.1 when ready"). The promotion to `main` waits for the owner's final go.

**Version:** v3.8.1, a **patch**. The scopes are a fix (`revisit-due-issues`), a non-blocking
advisory (`change-log-fragments-advisory`), a Stop check that stops blocking
(`retire-clear-verdict`), and research tooling (`escape-rerun`). None adds a capability or
breaks a persisted format consumers depend on. `stats --json` moves to schema 3, which is
additive. Conservative versioning (`operational-spec.md` `## Direction`) makes this a patch.

**Why now, and what follows.** v3.8.1 carries the `change-log-fragments-available` advisory,
which offers consumers the move onto change fragments. The next release makes the change record
fragment-only (#1125, owner 2026-11-10, its lead item) and refuses legacy logs. Shipping the
advisory first gives every consumer one release of warning before that.

## Release classification

| Scope | Disposition | Blocker |
|---|---|---|
| change-log-fragments-advisory | ships | |
| escape-rerun | ships | |
| release-v3.8.0 | ships | |
| retire-clear-verdict | ships | |
| revisit-due-issues | ships | |

## Notes

- `change-log-fragments-advisory` (#1123) shipped to `develop` without a build plan, and
  `check-releasability` warns about it. That is accepted rather than backfilled: the work is
  merged and reviewed, and a plan written afterwards would describe nothing a reader needs.
- `release-v3.8.0` is the fragment the v3.8.0 reopen commit added. It is pending by design, and
  ships here.
- `escape-rerun`'s plan reported chunk 01 `open` at the cut: chunk state comes from review facts,
  and no review covers `.prawduct/research/`, which the Critic classes as needing none (its
  cumulative dispatch exited 3). The chunk's acceptance is a known-answer test that was seen to
  fail with the guard removed, so the work is complete. The plan was archived with
  `archive-plan --state completed`, as the runbook directs for a completeness refusal.
