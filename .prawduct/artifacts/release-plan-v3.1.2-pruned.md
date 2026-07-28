# Release Plan — v3.1.2, Pruned Promotion

**Status:** **SHIPPED 2026-07-27.** `origin/main` = `09a2862`, tagged `v3.1.2`, published
`plugin/VERSION` = `3.1.2`. Owner go/no-go given after the gate table below was verified.
**Version:** v3.1.2 — patch, per the ratified conservative-versioning norm
(`operational-spec.md` § Direction). The bundle is a feature (session-handoff continuity) plus
two fixes, but the subsystem that would have made this a minor is **withheld** (below), so a
patch is the honest number. Owner-decided 2026-07-27.

## Why this release is pruned

`main`'s tree is **not** `develop`'s tree for v3.1.2. This is a departure from
`runbooks/cut-and-publish-a-plugin-release.md` Phase 2, which does a whole-tree
`git read-tree --reset -u origin/develop`. Recording it because the runbook does not cover this
shape and the next maintainer will otherwise read the divergence as an accident.

`develop` carries the entire **backlog-service** subsystem (GitHub Issues as system-of-record,
the `plugin/lib/backlog/` adapter package, the skill repointed onto it, cutover awareness).
Shipping it would publish the four blockers `release-plan-backlog-service-golive.md` lists as
items 18–21, all still `status: open` and all verified live on 2026-07-27:

| item | verified state at prep time |
|---|---|
| BKL-6J2X | `probe_migration_required` fires in **every** un-migrated repo with a structured backlog and pending items; `recommended_action: /prawduct:backlog scrub` |
| BKL-5N9W | `skills/backlog/SKILL.md` pairs `disable-model-invocation: false` with a wildcard `Bash(prawduct-hook backlog *)` grant |
| BKL-8V3D | no `--apply` / dry-run exists anywhere in `plugin/lib/backlog/` — the safety contract the instructions cite is absent |
| BKL-2Q7F | `migration-scrub.md` still never binds `--repo` |

Together those route the whole installed fleet into a migration path that can write 100–250 real
issues into a real repo while an agent believes a dry-run guarded it. That chain is **why v3.1.1
itself shipped from `v3.1.0`'s tree rather than from `develop`** — this release continues that
withholding rather than reversing it by default.

## What ships, and what does not

**Ships (5 change-log entries, tagged `release=v3.1.2 | status=shipped`):** CRT-2J8N (the
`SubagentStop` matcher), `session-boundary-events` Chunk 01, `session-handoff-continuity`
Chunks 01–03.

**Withheld (11 entries, deliberately left untagged so a later release claims them):** the
`2026-07-21` backlog-service relayout entry plus the ten `2026-07-17`–`2026-07-20`
backlog-service / skills-cutover / archive-scope entries.

**Collateral: the withheld range also holds improvements that are not backlog-service.** Pruning is
by commit range, not by feature, so anything that merged between `v3.1.1` and `e597b21` waits —
notably the `_get_current_branch` → `gitstate.current_branch` refactor (PDT-WT9K, so the
Critic's visibility print cannot be misled about which tree it resolved) and prose changes in the
critic / pr / janitor / report-bug / runbook skills and both session digests. None is a regression
(v3.1.1 consumers never had them either), but do not describe this release as "session-continuity
only" when asked what a consumer is missing — the honest answer is "everything after PR #139."

> ⚠️ **Do not identify the withheld set by change-log position or by heading presence in the
> previous release's tree.** Both readings are wrong here. All ten of those entries' *prose* is
> present in `v3.1.1:.prawduct/change-log.md` while their *code* is not — the v3.1.1 candidate-tree
> prune removed the code and left the entries. The sound test is the runbook's (REL-7D4X): per
> candidate, no `release=` tag **and** its code absent from the previous release's tree. Verified
> here by content, e.g. `v3.1.1` has `plugin/lib/backlog.py` where `develop` has the
> `plugin/lib/backlog/` package.

## How the candidate tree was built (repeatable)

The ship set is the commit range `e597b21..<develop HEAD>` — everything after the PR #139 merge.
The withhold set is `v3.1.1..e597b21`. They overlap in **11 files**, so a file-level split is
impossible; the tree is built by patching instead:

1. `git worktree add --detach <scratch> v3.1.1`
2. `git diff e597b21 <develop-HEAD> > ship.patch`
3. `git apply --3way ship.patch` in the scratch tree — 3 conflicts:
   - `plugin/lib/briefing.py` (import block) — resolve to **v3.1.1's** `from . import backlog, …`
     (single module) and **keep** the ship set's `from .coverage import _resolve_base_branch`.
   - `.prawduct/backlog.md` (×3), `.prawduct/change-log.md` (×1) — this repo's own state, not
     shipped to consumers; resolve so the file describes the tree it ships with.
4. **Add `import sys` to `plugin/lib/briefing.py`.** See below — this is the one line of shipped
   code on `main` that exists in no reviewed commit.
5. Commit the tree with `v3.1.1` as its parent, then publish **by ref**:
   `git push origin <sha>:refs/heads/main`, then `git tag vX.Y.Z <sha> && git push origin vX.Y.Z`.

### Two deviations from the runbook, both deliberate

- **Step 14 (`git checkout main && git pull`) was not run.** `main` was checked out in the sibling
  worktree `/Users/brookstalley/source/prawduct`, which belongs to its own session, and moving the
  `main` ref under it would have left that worktree's index inconsistent with its HEAD. Publishing
  by ref from the scratch worktree touches no other worktree. **Any pruned release should do this**
  — it is strictly safer than checking `main` out, and it also skips steps 15–16's in-place
  `read-tree --reset -u`, which the runbook itself flags as destroying anything uncommitted on `main`.
- **Step 17 (`git diff --stat origin/develop HEAD` must print nothing) does not apply** and was
  replaced. A pruned promotion leaves a delta by design. The substitute check is a *partition*
  verification: diff the candidate against `develop` per overlapping file and confirm every
  difference is either the intended prune resolution or withheld code — i.e. that no shipping work
  was silently dropped. Run on `plugin/lib/briefing.py`, the one shipped file where the two streams
  genuinely collide. Post-release the delta is **32 `plugin/` files, +6938/-61**.

### The one hand-authored line, and the trap it represents

`git apply` reported `plugin/bin/prawduct-hook` and `briefing.py` applied **cleanly**, and the
result was a broken program: `NameError: name 'sys' is not defined` in the `handoff preview` path,
11 test failures. Cause: the ship set's new code uses `sys.stderr`, but `import sys` was added to
`briefing.py` by the **withheld** backlog-service work, not by the session-continuity work. So the
ship set has a latent dependency on the set being withheld, and a textual patch tool cannot see it.

**The general rule for any future pruned release:** a clean `git apply` is not evidence of a sound
tree. Run the suite, and check every shipped Python file for imports its `develop` counterpart has
and the pruned copy lacks. That check was run across all 23 shipped Python files here and found
exactly this one instance.

This line disappears on the next release that ships the backlog service, because `main` then takes
`develop`'s tree wholesale and the divergence resolves itself.

## Verification evidence (pruned tree, 2026-07-27)

- Suite: **2131 passed, 1 skipped** (vs 2683 on `develop` — the difference is the withheld
  subsystem's own tests, which do not exist in this tree).
- Every `plugin/lib` module imports cleanly.
- Withheld surfaces confirmed absent: no `plugin/lib/backlog/` package, no
  `Bash(prawduct-hook backlog *)` grant, and **zero** occurrences of
  `backlog-service-migration-required` in `v3.1.1`'s `backlog_probes.py` (so the fleet-routing
  advisory is genuinely not published).
- Shipped surfaces confirmed present: the `(^|:)critic-reviewer$` matcher, the handoff forward
  channel, the session-continuity code.

## Done when

- `git ls-remote --tags origin` shows `refs/tags/v3.1.2`.
- `git show origin/main:plugin/VERSION` is `3.1.2`.
- `git diff --stat origin/main origin/develop` is **non-empty** — unlike a normal release. The
  remaining delta is exactly the withheld backlog-service work, and that is the expected
  post-condition here. The runbook's "Done when" test does not apply to a pruned promotion.
