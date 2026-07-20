---
artifact: release-plan
version: 1
scope: v3-1-1-hotfix
depends_on:
  - artifact: release-plan-backlog-service-golive
last_validated: 2026-07-20
---

# Release Plan — v3.1.1 Hotfix

**Owner decision (2026-07-20):** ship the release-pending fixes now, from `v3.1.0`'s tree, carrying
**zero backlog-service surface**. The v3.2.0 go-live plan is unchanged and still owns the migration.

## Why a hotfix rather than promoting `develop`

`develop` plus this branch are release-pending on **17** change-log entries (re-derived 2026-07-20
by counting `## ` headings above the first `release=v3.1.0` tag — 18 matches, less the boundary
entry's own heading). **10 are backlog-service migration work; 7 are independent.** Promoting the
tree would put a complete, self-triggering path to an unproven data migration into every consumer:

1. `backlog-service-migration-required` (new since v3.1.0, `warn`, fires for **every** repo with a
   structured markdown backlog and no `backlog_service_repo`) recommends `/prawduct:backlog scrub`.
2. `skills/backlog/SKILL.md` sets `disable-model-invocation: false` — a model may route there
   unprompted.
3. Its `scrub` section points at `migration-scrub.md`, which **never establishes the target repo** —
   `--repo <owner/repo>` appears as a placeholder in six steps and `provision` (which installs the
   label taxonomy) appears in no skill file at all.
4. `allowed-tools` grants `Bash(prawduct-hook backlog *)` — a wildcard, and this skill's first-ever
   Bash grant. `--repo` is shape-validated only, with no owner constraint.
5. `adapter-mode.md:96` tells the model it is protected by "the adapter's own `--apply`/dry-run and
   crash-safety contracts." **`--apply`, `--dry-run`, and `dry_run` have zero occurrences in
   `lib/backlog/`.** The safety contract the instructions cite does not exist.

A model that infers the repo from the git remote and follows the runbook writes 100–250 real issues
into a real repository, believing a dry-run guarded the step. Gating the advisory alone does not
close this: the runbook stays on disk, greppable, inside a model-invocable skill.

**Nothing on the migration path has been run end-to-end.** VRF-005, VRF-006, VRF-007 and VRF-008 are
all `pending`; VRF-006 states it outright. Only VRF-004 (the walking skeleton) is verified.

## What ships

All **seven** change-log entries independent of the migration. (An earlier draft of this table
listed six and silently omitted `worktree-salvage` — caught by re-deriving the count rather than
carrying the one in prose. Enumerate, don't sample: that is the REL-2N8K failure, and it is the
same class as the claim defects this branch spent the day correcting.)

| entry | what it fixes for a consumer |
|---|---|
| discodon upstream defects | 4 defects filed by a governed product **against v3.1.0**: `critic-consolidate` fail-closing on a file-less finding; `verify-chunk-refs` mis-parsing `## Chunk N (ID)` headings; `verify-resolutions` mis-anchoring so the cumulative gate stays `uncovered`; `critic-begin` blind to a wrong worktree |
| `verify-chunk-refs` false positives | stops bogus `missing-ref` on `path:line` citations and chunk-local `new` declarations |
| `critic-consolidate` liveness verdict | the incomplete no-op states whether reviewers are in flight or dead — stops duplicate roster dispatch |
| wait-side cache-warm directive | a waiting session stays audible instead of idling its prompt cache into expiry (`CRT-8Q6R`) |
| SessionStart banner provenance | the banner names which plugin code is actually loaded (`BRF-7Q4M`) |
| Stop-hook worktree redirect note | names the tree the gates actually evaluated (`STH-3R8K`) |
| worktree-salvage | `regen-views` no longer fails closed on a bad `scope=` tag; digest single-copy test works under `.claude/worktrees/`; dead `current_branch` removed (runtime no-op). Internal polish, but independent and already merged — shipping it keeps the release the *whole* independent set rather than a judgment call about which fixes "count" |

## Construction — allowlist, not subtraction

Build from **`v3.1.0`'s tree**, taking only allowlisted paths from `HEAD`. Everything unlisted stays
at v3.1.0, so no migration file can arrive by omission. Subtracting from `develop` was rejected: it
fails open — anything forgotten ships.

**Whole-file, safe to take from `HEAD`:**
`hooks/banner.py` · `lib/gitstate.py` · `lib/coverage.py` · `lib/gates.py` · `lib/buildplan_refs.py` ·
`lib/critic_consolidate.py` · `lib/stale_base_probes.py` · `methodology/building.md` ·
`skills/ping/SKILL.md` · and their tests (`test_plugin_version_banner` ·
`test_project_dir_resolution` · `test_cumulative_gate` · `test_buildplan_walkers` ·
`test_build_plan_resolution` · `test_critic_consolidate` · `test_stale_base_probes` ·
`test_v5_methodology`).

**Hunk-level selection required — these mix both workstreams:**

- `skills/critic/review-cycle.md` — carries the critic fixes **and** backlog-dormancy prose
  (`DORMANT_CHECKS` names it for the reconciliation walk and the four hygiene checks). Take the
  critic hunks only.
- `bin/prawduct-hook` — take the critic/worktree hunks; **drop** the `backlog` subcommand
  registration. `version` is independent and may stay (it is what `report-bug` sources instead of
  recalling a version).

**Explicitly held at v3.1.0 (do not take):**
`lib/backlog/**` · `skills/backlog/**` · `lib/backlog_probes.py` (this is what drops
`probe_migration_required`) · `lib/probe_families.py` · `lib/briefing.py` · `lib/norm_probes.py` ·
`skills/janitor/SKILL.md` · `skills/pr/**` · `skills/report-bug/SKILL.md` · both session digests ·
`documentation/backlog-service-*` · all `tests/test_backlog_*` · `tests/fakes/**` ·
`tests/fixtures/**` · `tests/spikes/**`.

## Verification

1. **Negative check is the load-bearing one.** In the built tree, assert zero occurrences of
   `migration-scrub`, `adapter-mode`, `backlog_service_repo`, `prawduct-hook backlog`, and
   `backlog-service-migration-required`; assert `skills/backlog/` holds exactly one file; assert
   `skills/backlog/SKILL.md` grants no Bash tool.
2. Full suite green on the built tree. Test files arriving from `HEAD` must not import
   `lib.backlog` or the fixtures/fakes held back — check before running, since a green suite that
   silently skipped collection is not evidence.
3. `prawduct-hook regen-views --check` passes.
4. A session opens against the tree and the briefing renders with no migration advisory.

## Release mechanics

1. Branch `release/v3.1.1` from `v3.1.0`; construct the tree per the allowlist.
2. Bump `VERSION` **and** `.claude-plugin/plugin.json` to `3.1.1` — this is the release trigger;
   without it `autoUpdate` keeps the cached copy and the release does not ship.
3. Change-log: the **seven** independent entries flip to `status=shipped` + `release=v3.1.1`. **The
   other ten — every one of them migration work — stay release-pending and must not be flipped.**
   Enumerate all seven against the table above; do not sample (REL-2N8K shipped 8 of 10 that way).
4. `regen-views --check` → `regen-views`.
5. Promote to `main` (tree snapshot, per the existing release lineage), tag `v3.1.1`, push.
6. Confirm the version-delta banner on the next session.

## Carried forward, not resolved

- `develop` keeps all migration work; the v3.2.0 plan is unchanged.
- The five defects this review surfaced in the migration surface — no repo-selection step, the
  fictional `--apply`/dry-run contract, `provision` absent from every skill, the wildcard Bash grant,
  and the advisory pointing at all of it — are **v3.2.0 blockers** and belong on that plan's ship
  list. They are not fixed here; they are excluded from shipping.
