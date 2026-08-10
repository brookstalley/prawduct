---
artifact: release-plan
version: 1
release: v3.3.0
last_validated: 2026-08-10
---

# Release plan — v3.3.0

**Cut from:** **whole-develop at Phase 2** — the tip as of the promotion, not a pinned commit.
*(`K withheld = 0` selects the whole-develop shape, which makes the tip the answer. Stated
relationally rather than pinned to a sha, because v3.2.3's plan recorded five instances of a
measurement that was true when typed and false when read.)*
**Previous release:** v3.2.7 (`a6a1794`, tagged)

## Version decision

**Minor bump, 3.2.7 → 3.3.0.** Owner ruling 2026-08-10, taken at release prep against a
standing draft that assumed a patch.

**This is the "subsystem going live" tier, and it is the second half of a release the project
already started.** The observed minor precedent (`operational-spec.md`, descriptive tiers) is
*"a substantial new capability or a subsystem going live"* — and names **v3.2.0 — planned for
the backlog service shipping dormant** as an instance. That is precisely the fact that decides
this release: v3.2.0 shipped the backlog service **dormant**, and `backlog-cache` Chunk 06
(*"the last dormant readers come back, and the advisory that announced them retires"*) is where
it **wakes up**. The Critic's reconciliation walk and four hygiene checks, the PR reviewer's R-1
and R-2, and the janitor's Backlog Health block each lose their "the live backlog is frozen
markdown, so skip and announce it" branch and gain a cache-backed query. Numbering the go-live
as a patch would make the dormant half a minor and the live half smaller than it.

**Recorded as a decision because the conservative norm points the other way and was the standing
assumption.** `project-preferences.md` § Direction (ratified 2026-07-17) binds *"versioning is
conservative: a small feature is a patch bump, not a minor-per-feature,"* and the pre-written
`## v3.2.8` CHANGELOG draft had already assumed a patch. The norm is not departed from here — it
forbids **minor-per-feature**, not a minor for a subsystem going live, and it explicitly makes
either direction *"a recorded decision, not a reflex."* This is that record.

**Not a major.** The major tier is *"a break in gate semantics or persisted state formats."*
`governance-artifact-lifecycle` retires `views_enabled` and deletes `views.py`, but `regen-views`
and `stamp-merged` stay callable and **still exit 0** with a stderr notice — their removal is
deferred to a major precisely so this release is not one. No fact-schema field changes and no
gate semantics change; a repo that never converges still runs.

## Release classification

| Scope | Disposition | Blocker |
|---|---|---|
| backlog-cache | ships | |
| backlog-cache-write-path | ships | |
| governance-artifact-lifecycle | ships | |

**Owner decision 2026-08-10: all scopes ship, nothing withheld.** `K withheld = 0` →
**whole-develop promotion** (runbook Phase 2 steps 14–20), not the pruned path.

### The set was derived, not recalled

Measured 2026-08-10 on `develop` @ `50d99594` (tree-identical to `origin/develop` — verified by
`git diff --quiet`, not assumed):

- **9 statusless change-log entries**, at `.prawduct/change-log.md` lines 8, 72, 135, 164, 221,
  326, 380, 419 and 454. Statuslessness — the absence of a `release=` tag — **is** the
  release-pending state, which is the sound per-candidate test rather than the
  "everything above the prior boundary" search hint the release process warns against.
- They **partition exactly into the three scopes above**: `backlog-cache` (7 entries),
  `backlog-cache-write-path` (1), `governance-artifact-lifecycle` (1). No fourth scope appears,
  and no scope in the table is absent from the enumeration — the table is an exact partition of
  the gate-visible pending set, which is what the gate requires.
- `check-releasability --release v3.3.0` enumerated the same three scopes independently before
  this plan existed. Two derivations, one answer.
- The prior boundary (`release=v3.2.7`) is at line 468, and all nine entries sit above it. That
  is recorded as **corroboration, not as the derivation** — an entry can merge below the boundary
  and still be unreleased, so the boundary is never the test.

### Verification recorded by hand

`check-releasability` reports `cannot-verify-blockers` on this repo (GitHub Issues backend —
`backlog.md` is frozen history), so blocker liveness is confirmed by hand. **Nothing is withheld
in this release, so there are no withholding blockers to confirm.** Every other check the gate
runs still applies.

## Pre-cut evidence (2026-08-10)

Recorded because this release's two largest surfaces are a **fleet data migration** and a **new
subsystem going live**, and neither is graded by the suite alone.

- **Suite:** 4328 passed, 10 skipped. Clean.
- **Fleet migration, dogfooded on a foreign repo.** The convergence flow was applied end-to-end
  to `scriob` — an unrelated product with a `v0.x` scheme, carrying all three repair legs. Result:
  `plan-backfill` archived 14 shipped plans (deriving each release mechanically) and left 8;
  `lifecycle-repair` then removed the retired flag and its 161-line `scope_rollups` block, labelled
  the derived `release-notes.md` as history, and edited **1** live plan. Both re-run clean
  (idempotent), the state-file diff is a **pure deletion**, and archived plans carry correct
  `lifecycle: completed` / `released_in:` frontmatter.
  **The documented ordering was confirmed under load, not just read:** running `plan-backfill`
  first reduced `lifecycle-repair`'s edits from 7 plans to 1, because 6 were already archived —
  exactly the waste the doctor flow's ordering note predicts for the other order.
  `unreadable: []`, so the sweep graded a set it had fully read.
- **Backlog cache, exercised against a real corpus.** Full sync on `pacepace/discodon`: 451 items
  in 24s with FTS built; incremental re-sync 1.0s / 0 written (~24× cheaper); every `cache-query`
  shape (`open`, `unstaged`, `by-area`, `stale`, `search`) returned offline at exit 0.
- **Fresh onboard is clean.** `init-product` on an empty repo scaffolds no retired flag, opt-in
  flags matching measured code defaults, and `lifecycle-repair` correctly a no-op.
- **Whole-tree promotion loses nothing by accident.** 76 paths exist on `main` and not on
  `develop`; **73 are plans relocated into `archive/`** by this bundle's own backfill, and the
  remaining 3 (`plugin/lib/views.py`, `tests/test_views.py`, `tests/test_backlog_claim.py`) are
  the deliberate retirements. Checked by comparing the two trees, not inferred from the diffstat.

## Step 6: two shipping plans carry unticked boxes, and they were NOT ticked

Runbook Phase 1 step 6 asks whether each shipping scope's build plan is closed out.
`build-plan-governance-artifact-lifecycle.md` is (5 ticked, 0 unticked).
**`build-plan-backlog-cache.md` (0/6) and `build-plan-backlog-cache-write-path.md` (0/3) are not** —
and they were deliberately left alone, per that step's standing instruction that a release-prep tick
is a claim made by whoever happens to be cutting the release.

**They are not incomplete work.** `views_enabled: true` was live in this repo while both plans were
built (verified at `74d1dca6`, the Chunk 06 commit), so their `## Status` blocks were a *generated
view* that only flipped at release and therefore read all-unchecked throughout development. The
generator was retired by this very release, freezing them as they stood. The completion evidence is
the change log, which records every chunk closed: `chunks=01` … `chunks=06` for `backlog-cache` and
`chunks=01,02,03` for `backlog-cache-write-path`, each with its review outcome.

**This is the defect the release ships the fix for, met one last time in its own release prep** —
which is also why it is recorded rather than quietly corrected. Both plans are archived at step 11,
and an archived plan's boxes are read by nothing; the archive preserves unticked boxes on purpose,
as a fact about how the work ended rather than a claim about whether it finished.

## What this plan does NOT authorise

**The cut has not happened and is not authorised by this file.** At owner instruction
(2026-08-10) the release trigger is deliberately left **unarmed**:

- `plugin/VERSION`, `plugin/.claude-plugin/plugin.json` and `pyproject.toml` still read **3.2.7**.
  The bump is the release trigger and belongs to the `release: prep` commit.
- `plugin/CHANGELOG.md`'s section is renumbered to v3.3.0 and its headline widened to cover all
  three scopes, but it **retains its `— DRAFT` suffix and its RELEASE-PREP comment**, so it
  cannot read as shipped. Restoring the heading to a bare `## v3.3.0` is a release-time step:
  release-checklist step 6 extracts notes with an **anchored** match (`/^## vX.Y.Z$/`), so a
  forgotten suffix publishes **empty** release notes and no test catches it.

Resuming the cut means the release checklist from step 1, with this table as its Phase 0 answer.
