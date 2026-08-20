# Release Plan — v3.4.0, Whole-Develop Promotion

**Status:** Phase 1 complete — release prep committed on `develop` (change-log entries tagged `release=v3.4.0`, all three version carriers bumped, `plugin/CHANGELOG.md` section renamed, `active_build_plan` cleared and ten plans archived). Phases 2–3 pending.

**Version:** v3.4.0 — **minor**, and the call is recorded rather than reflexive because the ratified
norm pulls the other way. The norm (`operational-spec.md` `## Direction`, 2026-07-17) is
*"Versioning is conservative: a small feature is a patch bump, not a minor-per-feature."* Read alone
that argues v3.3.5.

**Maintainer decision, 2026-08-19: minor (+0.1.0).** Raised as a framed decision before cutting; the
maintainer chose the minor. Recorded here because the norm requires a close call in either direction
to be a recorded decision rather than a reflex.

Supporting the minor reading — the runbook's unratified precedent reads *a substantial new capability
or a subsystem going live* as a minor, and explicitly warns against treating "not a major" as
"therefore a patch," which would erase the minor tier:

- **A new subsystem**: `lib/verdict_cache.py`, a memo layer under the composed-coverage verdict, with
  its own schema constant, eviction policy and on-disk file beside the evidence store.
- **Gate semantics move**: base-advance coverage transfer means a clean base sync no longer voids
  review coverage, and `session_review_verdict` grows a `record_grants` write path. Consumers'
  sessions will gate differently than they did on 3.3.4 — not more loosely, but differently.
- **A shipped file is deleted**: `methodology/session-digest-slim.md`, along with the repo-shape
  classifier that chose between the two digests.
- **A consumer-visible contract is rewritten**: the standing block's second line moves from
  topic-named (`NEXT` / `CLEAR`) to verdict-named (`RUNNING` / `YOUR TURN` / `COMPLETE`).
- **New advisories fire in consumer sessions**, including the urgent `PRAWDUCT IS NOT SET UP`.

Not a major: no persisted format breaks. The evidence store's path and record shape are unchanged
(`evidence.store_path` is identical across `main`→`develop`), the verdict cache is a disposable memo
keyed on a fingerprint that includes the plugin version, and the only write into pre-existing
consumer state is the test-tracking nested-key strip — prawduct's own key, reached through doctor and
migrate.

## Release classification

Fourteen release-pending scopes, all shipping. `check-releasability --release v3.4.0` enumerates
them; this table is the partition it grades against.

| scope | disposition | blocker |
|---|---|---|
| critic-reliability | ships |  |
| clear-cadence | ships |  |
| governance-surface-dedup | ships |  |
| standing-block-expressive-labels | ships |  |
| change-log-gate-predicate | ships |  |
| instance-vs-class | ships |  |
| fleet-feedback-661 | ships |  |
| release-cut-checklist | ships |  |
| scope-widened-demotion | ships |  |
| test-tracking-advisory | ships |  |
| test-tracking-treadmill | ships |  |
| tactical-efficiency | ships |  |
| purpose-and-cession | ships |  |
| durable-agent-worktrees | ships |  |

**Nothing is withheld — `K = 0`, so this is a standard Phase 2 whole-develop promotion**, not a
pruned one. The pruned path exists for content sitting on `develop` that must not reach `main`;
after this batch, `develop`'s shippable content and the release's content are the same tree.

**Blocker liveness was not machine-verified, and that is expected.** This repo has cut over to the
GitHub Issues backlog, so `backlog.md` is frozen history and `check-releasability` reports
`cannot-verify-blockers:` by design. No row withholds anything, so there is no blocker to
hand-confirm — the check has nothing to withhold on. Every other check in the gate still ran.

**Four advisory `WARNING: … has no build-plan file` lines are expected and do not block**:
`standing-block-expressive-labels`, `change-log-gate-predicate`, `release-cut-checklist`,
`scope-widened-demotion`. Each shipped as a small fix that never earned a plan. Noted rather than
suppressed.

## Fitness evidence

Gathered 2026-08-19 on `develop` at `0ff8fe73`, plus the `fix/escape-hatch-archives` commit below.

- **Suite green** — zero failures, recorded into the evidence store from a JUnit report rather than
  asserted. Cite `prawduct-hook test-status` for the figures; a total copied into prose here is one
  more carrier to keep in sync and nothing reads it (`building.md`, "a count nothing reads").
- **Nothing half-landed** — all ten live build plans have every `## Status` chunk ticked. No
  partially-built scope is riding along.
- **`develop` == `origin/develop`**, tree clean.
- **No state migration** — `evidence.store_path` unchanged; no consumer loses coverage evidence on
  upgrade.

## Why this is worth cutting rather than accumulating

`verdict_cache.py` fixes a **measured** consumer defect, not a hypothetical one. Its docstring
records the field observation: nine composed-coverage gate invocations in one consumer session ran
29–120 s each, two hit the 2-minute Bash ceiling, and the agent resorted to `timeout 200`. A cold
verdict on this repo costs 17.4 s against 2,715 facts and 701 distinct trees; warm it is 0.01 s.
That cost grows monotonically with the append-only store, so every session still on v3.3.4 pays more
of it than the last. Holding the release makes that worse, not better.

## One fix taken during release prep

**#604 — the Stop hook's escape recipe.** Found while assessing releasability: the abandoned-review
blocker printed `rm -rf .prawduct/.critic-partials`, and all four branches that print it are reached
only when reviewer output is on disk. This release is the one that teaches the marker to protect a
finished-but-unrecorded review, so shipping the guard beside the contradicting recipe would have been
worse than shipping neither — the operator now has reason to trust the mechanism.

Strictly it was **not a regression**: v3.3.4 carries the same recipe with none of the protection. It
was fixed inside the release rather than after it because the incongruity is one this release
creates. The hatch now names `prawduct-hook critic-discard`, which archives and prints its own
`critic-restore <id>` recovery.

## Known gaps shipping stated

Both are already in `plugin/CHANGELOG.md`, where consumers read them:

- **#668** — the verdict cache keys on the version *string*, which is fixed across a development
  cycle, so it separates prerelease from release but not one `develop` push from the next. Irrelevant
  to `main`-pinned consumers, which is every consumer following the documented install reference.
- **`chunk`-mode Critic reviews do not carry the instance-vs-class rule** — that instruction payload
  is at its size ceiling. `final`, `cumulative` and `verify-resolutions` all carry it, and a
  `chunk`-mode finding meets the rule one round later when its fix is graded.

## Cut-time reminders

These are the steps this repo has rediscovered at past cuts; the runbook owns the full procedure.

1. **Rename `## v3.3.5-dev` to `## v3.4.0` in `plugin/CHANGELOG.md`.** The runbook's frontmatter
   carries `last_verified: null` precisely because this step was added after the v3.3.4 cut and has
   never been executed.

   *What actually goes wrong if it is missed, checked against `banner.py` rather than assumed:*
   `_SEMVER_HEADER` matches the prerelease spelling, and `version_tuple("3.3.5-dev")` is
   `(3,3,5,0,0)`, which **does** fall inside a v3.3.4 → v3.4.0 consumer's `lo < v <= hi` window. So
   the headline is **not** lost — it renders, mislabeled `v3.3.5-dev`, telling a consumer who just
   received the release that they are on a prerelease build. The one case that loses the entry
   outright is a **develop-pinned** repo already reporting `3.3.5-dev`: there `lo` equals the
   entry's own tuple, the comparison is strict, and the section is skipped. Cosmetic for nearly
   everyone, silent for the few on `develop` — still rename it.
2. **Bump all three version carriers**: `plugin/.claude-plugin/plugin.json`, `plugin/VERSION`,
   `pyproject.toml`. The version is the update cache key — a promotion without it does not ship.
3. **Clear `active_build_plan` BEFORE running `plan-backfill`.** The sweep refuses to archive the
   plan the pointer names, so a pointer left set is a plan left live. It currently names
   `build-plan-instance-vs-class.md`.
4. **Tag the shipped entries `release=v3.4.0`** using Phase 1 step 2's per-candidate test — do not
   re-derive the set from `release-process.md`'s search hint.
