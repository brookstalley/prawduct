---
artifact: release-plan
version: 1
scope: v3-1-1-hotfix
depends_on:
  - artifact: release-plan-backlog-service-golive
last_validated: 2026-07-20
---

# Release Plan — v3.1.1 Hotfix

## Execution status — read this first

**Not started. Next action: release mechanics step 1** (merge
`fix/archive-scope-preservation-claim` → `develop` via `/prawduct:pr`).

Update this block as each step lands — it is the only cross-session record of *where execution
stands*, and the steps are stateful — later steps consume names earlier steps produce, so a step
done out of order has nothing to bind to.

Two orientation notes for a session picking this up cold:

- **The session briefing will misdirect you.** `project-state.yaml` still carries
  `active_build_plan: artifacts/build-plan-skills-cutover-awareness.md`, so the briefing announces
  `Work: Skills Cutover Awareness` and resumes that plan's first unchecked chunk. That pointer is
  *correct* state — that plan is unfinished work moving to `feature/backlog-service` — but it is
  **not** the active work. This release plan is.
- **Nothing is pushed yet.** `origin/develop` still points at the pre-merge commit and does not
  move until the promotion step; that, plus the reflog, is the safety net. `feature/backlog-service`
  becomes the durable holder of the migration work at the branch-creation step.

**Owner decision (2026-07-20):** ship the release-pending fixes now carrying **zero
backlog-service surface**, by **isolating the migration work off `develop`**. Current `develop` is
snapshotted as `feature/backlog-service`; `develop`'s *tree* is then set to the v3.1.1 candidate,
and v3.1.1 ships as an ordinary `develop` → `main` promotion. The v3.2.0 go-live plan is unchanged
and still owns the migration.

**Two alternatives were rejected.** A bespoke `release/v3.1.1` branch beside an untouched `develop`
works, but leaves `develop` unreleasable — so **every hotfix until v3.2.0 repeats the
construction.** Isolating pays that cost once. History surgery (rewinding or reverting the six
migration merges out of `develop`) was rejected as *unsafe*, not merely expensive: every
independent-work source branch is already deleted (`fix/worktree-salvage`,
`fix/verify-chunk-refs-token-fixes`, `fix/cov-7k4n-stale-base-advisory`,
`feature/discodon-upstream-defects`), the two streams interleave across six merge points, both
edited the same state files, and `fix/archive-scope-preservation-claim` is itself mixed. A tree-set
needs none of that untangling and loses nothing — the snapshot branch holds every commit.

**The accepted cost**, stated once so it is not rediscovered later: resuming v3.2.0 means merging
`feature/backlog-service` into a `develop` that has moved — one substantial conflict resolution.
The five v3.2.0 blockers below mean that merge is not imminent.

## Why `develop` cannot ship as-is

`develop` plus this branch are release-pending on **18** change-log entries. **10 are
backlog-service migration work; 8 are independent.**

**How that number is derived, and why the obvious method is wrong.** Counting `## ` headings above
the first `release=v3.1.0` tag gives 17 — and silently drops
`2026-07-14: Stale remote-base diagnostics`, which sits *below* the boundary and is genuinely
unreleased (`lib/stale_base_probes.py` is absent at `v3.1.0`). Position is not the field: an entry
lands wherever it merged, not above the last release. Counting by *field* instead (no `release=`
tag) over-corrects to 57, sweeping in entries that shipped before the tag convention existed —
mostly 2026-05 (25), plus 2026-04 (10) and 2026-03 (4), so "old" here means pre-convention, not
pre-May. **Neither count is trustworthy on its own.** The sound test is per-candidate and cheap:
an entry is release-pending iff it carries no `release=` tag **and** its code is absent from the
`v3.1.0` tree. Run that test; do not carry either number forward as a constant.

This is not a footnote — it is REL-2N8K, the failure this plan cites twice, reproducing itself
inside the plan written to avoid it. `docs/release-process.md` says "enumerate ALL tagged entries
**above** the prior boundary," and that instruction is what dropped the entry.

Promoting the tree would put a complete, self-triggering path to an unproven data migration into
every consumer:

1. `backlog-service-migration-required` (new since v3.1.0, `warn`, fires for **every** repo with a
   structured markdown backlog and no `backlog_service_repo`) recommends `/prawduct:backlog scrub`.
2. `skills/backlog/SKILL.md` sets `disable-model-invocation: false` — a model may route there
   unprompted.
3. Its `scrub` section points at `migration-scrub.md`, which **never establishes the target repo** —
   `--repo <owner/repo>` appears as an unbound placeholder in six commands across four steps
   (`export` 0, `list` 1, `import`/`merge`/`status` 3, `counts` 4) and `provision` (which installs
   the label taxonomy) appears in no skill file at all.
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

All **eight** change-log entries independent of the migration. (Two drafts of this table were
short: the first omitted `worktree-salvage`, the second `stale-remote-base-diagnostics`. Both were
caught by re-deriving rather than by re-reading. Enumerate, don't sample.)

| entry | what it fixes for a consumer |
|---|---|
| discodon upstream defects | 4 defects filed by a governed product **against v3.1.0**: `critic-consolidate` fail-closing on a file-less finding; `verify-chunk-refs` mis-parsing `## Chunk N (ID)` headings; `verify-resolutions` mis-anchoring so the cumulative gate stays `uncovered`; `critic-begin` blind to a wrong worktree |
| `verify-chunk-refs` false positives | stops bogus `missing-ref` on `path:line` citations and chunk-local `new` declarations |
| `critic-consolidate` liveness verdict | the incomplete no-op states whether reviewers are in flight or dead — stops duplicate roster dispatch |
| wait-side cache-warm directive | a waiting session stays audible instead of idling its prompt cache into expiry (`CRT-8Q6R`) |
| SessionStart banner provenance | the banner names which plugin code is actually loaded (`BRF-7Q4M`) |
| Stop-hook worktree redirect note | names the tree the gates actually evaluated (`STH-3R8K`) |
| worktree-salvage | `regen-views` no longer fails closed on a bad `scope=` tag; digest single-copy test works under `.claude/worktrees/`; dead `current_branch` removed (runtime no-op). Internal polish, but independent and already merged — shipping it keeps the release the *whole* independent set rather than a judgment call about which fixes "count" |
| stale-remote-base diagnostics (2026-07-14) | the cumulative-critic gate explains a stale `origin/<base>` instead of failing opaquely, plus the stale-base / unpromoted-release-prep advisory nudges. **Sits below the v3.1.0 boundary in the change-log and was missed by the first two drafts** — its code is absent at v3.1.0, so it is genuinely unreleased and its entry must flip |

## Construction — allowlist, verified as an exact diff

**Prerequisite: `fix/archive-scope-preservation-claim` merges to `develop` first.** It carries
`lib/critic_consolidate.py` at **128 insertions / 8 deletions over `develop`**, including the
wait-side cache-warm directive that is a row in the table above. Constructing before that merge
ships the entry's change-log row without its code. The branch is mixed — its `lib/backlog/*` and
`skills/backlog/migration-scrub.md` work lands on `develop` too, and is then held back by this
allowlist like the rest of the migration surface.

Build the candidate as **`v3.1.0`'s tree plus allowlisted paths from `develop`**, then set
`develop`'s tree to it. Allowlist rather than subtraction for one reason — it **fails closed**:
anything forgotten is *absent* rather than *shipped*. (Measured **post-merge**, i.e. against the
tree `develop` will have at `M`: 104 files differ from `v3.1.0`, split 86 outside `.prawduct/` and
18 within. Neither direction is meaningfully less typing; safety is the whole argument. An earlier
draft quoted 101/84/17 — the same query run against *pre-merge* `origin/develop`, which is the
wrong base once merging first became a prerequisite.)

**The construction is verified by set equality over paths, not spot-checked.** After the tree-set
and before release-prep, `git diff --name-only v3.1.0 develop | sort` **must equal the fully
expanded take-list** — every `.prawduct/` path enumerated, not globbed. That invariant is
directional-agnostic: it catches a migration file that survived and a needed file that never
arrived, which no negative grep can do alone.

**Two limits of that check, stated so they are covered elsewhere rather than assumed away.**
(a) It compares *paths*, so for the **three** partial-take files — `skills/critic/review-cycle.md`,
`bin/prawduct-hook`, `skills/critic/review-protocol.md`; `lib/probe_families.py` is a **whole-file**
take — it cannot see *which* hunks landed. Their content is verified by the positive assertions in
checkpoint A item 2, not by the negative grep, which catches leaks but is blind to omissions.
(b) `CHANGELOG.md` is **identical** between
`v3.1.0` and `develop`, so it is not a take-list entry at all; it changes only at release-prep and
is verified at checkpoint B.

**Whole-file, safe to take from `develop`:**
`hooks/banner.py` · `lib/gitstate.py` · `lib/coverage.py` · `lib/gates.py` · `lib/buildplan_refs.py` ·
`lib/critic_consolidate.py` · `lib/stale_base_probes.py` · `methodology/building.md` ·
`skills/ping/SKILL.md` · and their tests (`test_plugin_version_banner` ·
`test_project_dir_resolution` · `test_cumulative_gate` · `test_buildplan_walkers` ·
`test_build_plan_resolution` · `test_critic_consolidate` · `test_stale_base_probes` ·
`test_v5_methodology`).

**`.prawduct/**` — take whole from `develop`, and it is load-bearing.** Do **not** transcribe its
member paths into this document. Expand the glob **from `M`**, the pre-tree-set merge commit
(`git diff --name-only v3.1.0 M -- .prawduct/`) — never from `develop`, which *is* the tree under
test by the time the check runs (see checkpoint A item 1). It is 18 paths post-merge, and **this
plan file is one of them**, so a transcribed list goes stale on the edit that transcribes it. An earlier draft
left it unaddressed, which breaks the release two ways. (a) The change-log flip in release mechanics
flips eight entries; if the tree carried `v3.1.0`'s `.prawduct/change-log.md`, **none of the
eighteen entries exist there to flip.** (b) `regen-views` validation is fail-closed on an
unreleased `scope=` that resolves to no plan file — **eight of the ten** held entries are
scope-tagged (`skills-cutover-awareness` ×4, `backlog-service-v1` ×3, `backlog-skill-repoint` ×1;
the two `--archive-scope` entries carry no `scope=`), so those build plans must be present or the
whole regen aborts (exit 2, nothing written). `.prawduct/` is prawduct's own product state, not
consumer instruction: no skill routes a model into the plugin's own backlog. Consequence for
verification — the negative grep must exclude it (see below).

**`CHANGELOG.md` needs a `## v3.1.1` section — a release-prep edit, not a take-list entry.** The
file is identical at `v3.1.0` and `develop`, so nothing is taken; the section is authored during
release-prep. Missing from an earlier draft entirely. The version-delta banner reads
**`CHANGELOG.md` at the plugin root** (`hooks/banner.py:257`), *not* `.prawduct/change-log.md` —
the two are kept in sync by hand, one headline per shipped release. Without the section the release
still ships, but the closing "confirm the banner" confirms a version move with a blank headline.
(Step numbers are deliberately not cited here: this list has been renumbered twice already, and a
step reference in a document that renumbers is the line-number defect BKL-2Q7F records.) The durable form of
this gap is **REL-3M7K** (open): `docs/release-process.md` never mentions `CHANGELOG.md`, so every
release re-derives it. This plan patches the instance; REL-3M7K stays open for the process fix.

`hooks/gates.json` is **unchanged** since `v3.1.0` (verified), so the banner announces no
newly-active gate in this range and the file needs no handling either way.

**Hunk-level selection required — these mix both workstreams:**

- `skills/critic/review-cycle.md` — carries the critic fixes **and** backlog-dormancy prose
  (`DORMANT_CHECKS` names it for the reconciliation walk and the four hygiene checks). Take the
  critic hunks only.
- `bin/prawduct-hook` — take the critic / worktree / `verify-chunk-refs` / `version` hunks, each
  pinned by a marker in checkpoint A item 2 rather than by a count; **drop** the `backlog`
  subcommand (the `cmd_backlog` definition and its `main()` dispatch registration). `version`
  **ships**, and `tests/test_hook_version.py` ships with it. (An earlier draft left `version`
  optional; an optional item cannot be checked, so it is now decided.)

  **Its stated reason was wrong, and the correction matters.** Earlier drafts justified shipping
  `version` as "what `report-bug` sources instead of recalling a version." That is true of
  `develop` and **false of the tree this plan builds**: `skills/report-bug/SKILL.md` is on the held
  list, and at `v3.1.0` it contains `version` zero times — the `prawduct-hook version` instruction
  is a develop-only addition whose hunk also carries the migration prose this release withholds.
  In the built tree the subcommand's only in-tree reference is its own test. It still ships on the
  honest ground: it is a self-contained, tested, operator-invocable subcommand that leaks nothing,
  and it is already in place when the held `report-bug` guidance lands in v3.2.0. This is the same
  shape as the `probe_families` and `test_plugin_methodology_digest` corrections — a rationale
  verified against `develop` rather than against `T`.
- `skills/critic/review-protocol.md` — take the `cannot-verify:` hunk (the doc half of the
  `verify-chunk-refs` shipping row); **drop** the backlog-reconciliation hunk, which introduces
  `backlog_service_repo` into a `skills/` file the negative grep asserts is clean.

**`lib/probe_families.py` — take from `develop`, and the reason matters.** An earlier draft held it,
which would have shipped `lib/stale_base_probes.py` as **dead code**: `probe_families.register_all`
is its only importer, so holding one and taking the other registers nothing. Verified safe to take:
its entire v3.1.0→`develop` delta is the two `stale_base` lines (import + `register_stale_base()`), and
its `register_backlog()` call resolves against **v3.1.0's** `backlog_probes.register()`, which
exists and registers four probes — none of them `backlog-service-migration-required`. Taking this
file is therefore what makes the stale-base entry real, and it leaks no migration surface.

Note the split this exposed: the *gate diagnostic* half of that entry lives in `lib/coverage.py`
(`diagnose_stale_remote_base`, called from `lib/gates.py:980`) and would have shipped either way;
only the *advisory* half depended on `probe_families`. Ship both halves or neither — half an entry
is the REL-2N8K shape again.

**Explicitly held at v3.1.0 (do not take):**
`lib/backlog/**` · `skills/backlog/**` · `lib/backlog_probes.py` (this is what drops
`probe_migration_required`) · `lib/briefing.py` · `lib/norm_probes.py` ·
`skills/janitor/SKILL.md` · `skills/pr/**` · `skills/report-bug/SKILL.md` · both session digests ·
`documentation/backlog-service-*` · all `tests/test_backlog_*` · `tests/fakes/**` ·
`tests/fixtures/**` · `tests/spikes/**`.

**The remaining ten — classified, because "unlisted" was silently doing work.** The lists above
plus the held globs covered only **76 of the 86** non-`.prawduct` changed files (20 taken, 56
held). The other ten defaulted to *held*, which is safe against leaks — but checkpoint A compares
the diff against the take-list, so for an unlisted file both sides derive from the same omission
and the check passes in both directions. Silent defaults are invisible to the invariant. One of
the ten turned out to be **shipping code**, which is exactly the cost of leaving them implicit:

Final split after classification: **23 taken, 63 held, 86 total.**

| file | disposition | why |
|---|---|---|
| `skills/critic/review-protocol.md` | **partial take** | doc half of the `verify-chunk-refs` shipping row (`cannot-verify:`); its other hunk adds `backlog_service_repo`, which checkpoint A's grep over `skills/` asserts is zero. Neither whole-file disposition works |
| `tests/test_hook_version.py` | **take** (new at v3.1.0) | coverage for `prawduct-hook version`. This settles the "may stay" optionality: `version` **ships**, so its test ships with it |
| `docs/norms.md` | hold | norm-sweep guidance from `skills-cutover-awareness` chunk 04 — a held entry |
| `documentation/post-sync-advisory-spec.md` | hold | pure migration surface; documents `backlog-service-migration-required` and `backlog-checks-dormant`, and sits inside the grep scope |
| `lib/upstream_probes.py` | hold | its delta only makes advisory prose backend-agnostic ("the backlog" rather than `.prawduct/backlog.md`); v3.1.0's wording is the *correct* wording for a release with no Issues backend |
| `tests/test_briefing_functions.py` | hold | pairs with held `lib/briefing.py` |
| `tests/test_cutover_prose_coherence.py` | hold | imports held `lib.backlog_probes` (new at v3.1.0) |
| `tests/test_norm_probes.py` | hold | pairs with held `lib/norm_probes.py` |
| `tests/test_plugin_methodology_digest.py` | **take** | **not** "pairs with the held session digests" — that rationale was wrong. Its whole delta is `fix(tests): digest single-copy checks filter .claude/.git relative to root`, which **is** the second bullet of the `worktree-salvage` What-ships row ("digest single-copy test works under `.claude/worktrees/`"). Holding it flips that row to shipped without its code — REL-2N8K. Safe to take beside held digests: the filter change is digest-content-agnostic |
| `tests/test_pr_reviewer.py` | hold | pairs with held `skills/pr/**` |

That makes the partial-take set **three** files, not two: `skills/critic/review-cycle.md`,
`bin/prawduct-hook`, and `skills/critic/review-protocol.md`. (`lib/probe_families.py` remains a
whole-file take.)

## Verification

**Checkpoint A — after the tree-set, before release-prep.**

1. **The path-set invariant is the load-bearing check.** `git diff --name-only v3.1.0 develop | sort`
   equals the take-list, with `.prawduct/**` expanded **from `M`** (`git diff --name-only v3.1.0 M
   -- .prawduct/`) — never transcribed, and never expanded from `develop`.

   **Expanding from `develop` at check time is self-referential and passes unconditionally.**
   Checkpoint A runs *after* the tree-set, so `develop` **is** `T` — the tree under test. Both
   sides of the comparison become the same command against the same tree, matching in both
   directions for exactly the 18 paths the plan argues hardest about (a missing `change-log.md`
   means none of the eighteen entries exist to flip; a missing scope-tagged build plan aborts
   `regen-views` fail-closed). Pinning to `M` is what makes it a check.

   Set equality is what makes an omission as visible as a leak. It compares **paths only**;
   `CHANGELOG.md` is correctly absent because it is identical at `v3.1.0` and changes only at
   release-prep.

   **Completeness precondition — run this first, or item 1 grades itself.** Assert
   `take ∪ held == git diff --name-only v3.1.0 M -- . ':(exclude).prawduct/'` (86 paths). An
   unlisted file defaults to held and is therefore *absent from both sides* of item 1, so item 1
   cannot see it — that is how ten files went unclassified. This precondition is the only check
   that fails on an omission from the lists themselves.
2. **Positive assertions for the three partial-take files.** The path-set check cannot see *which*
   hunks landed, and the negative grep below catches only leaks — so without this, an omission is
   invisible: dropping the cache-warm hunk from `review-cycle.md` passes the path check, passes the
   grep, and still flips that row to shipped. REL-2N8K exactly.
   - `skills/critic/review-cycle.md` — **already bound by the suite.**
     `test_critic_consolidate.py::test_review_cycle_prose_matches_the_code_cadence` asserts the
     guide's cadence literal matches `_CACHE_WARM_INTERVAL_MINUTES`, so a dropped cache-warm hunk
     fails item 5's test run. No new check needed — just do not skip the suite.
   - `bin/prawduct-hook` — assert on **symbols the taken hunks introduce**, not on the usage
     string. Every count below is verified `0` at `v3.1.0` and non-zero at `develop`:
     present → `PDT-WT9K` (3), `_worktree_redirect_note` (2), `STH-3R8K` (1), `cannot-verify` (1),
     `resolve-base|version|` (1), `cmd_version` (2); absent → `cmd_backlog` (2 at `develop`, the
     subcommand registration this plan drops).

     `cannot-verify` covers the `cmd_verify_chunk_refs` hunk (shared current-chunk resolution) —
     the code half of a What-ships row, droppable while passing every other check without it.
     `cmd_version` (definition **and** `main()` dispatch arm) is the exact mirror of the
     `cmd_backlog` absent-marker, and it is load-bearing: `tests/test_hook_version.py` calls
     `cmd_version()` directly and never reaches `main()`, so dropping the dispatch arm — which sits
     four lines from the `cmd_backlog` arm the operator is told to delete — would ship a tree that
     **contradicts itself**: the taken `resolve-base|version|` hunk makes `_USAGE` advertise
     `version` while the dispatcher's terminal `else` denies it, printing that same usage text to
     stderr and returning 1 — indistinguishable from a typo, no traceback. Silent, too: nothing in
     the built tree calls `main()` for it. It would pass the path check, the grep, every other
     marker, and the suite.
     `resolve-base|version|` covers the one-token `_USAGE` hunk: now that `version` **ships**,
     asserting on `_USAGE` is meaningful, whereas the earlier "lists the taken subcommands"
     phrasing was inert — it would have detected only that token while `version` was still
     optional, and `tests/test_hook_version.py` calls `cmd_version()` directly without ever
     reading `_USAGE`. (`_current_chunk_id_from_status` is unusable as a marker: 2 at `v3.1.0`,
     3 at `develop`.)
   - `skills/critic/review-protocol.md` — present → `cannot-verify:`; absent →
     `backlog_service_repo`.

   **Why the negative marker is `cmd_backlog` and not `_USAGE`.** `backlog` is absent from
   `_USAGE` at **both** ends — `cmd_backlog` is defined and dispatched without ever being listed —
   so "assert `backlog` omitted from `_USAGE`" would pass unconditionally, checking nothing. The
   symbol that actually moves is the one to assert on.
3. **Negative grep, scoped to the executable and instructional surface** — `skills/`, `lib/`,
   `bin/`, `hooks/`, `methodology/`, `documentation/`: zero occurrences of `migration-scrub`,
   `adapter-mode`, `backlog_service_repo`, `prawduct-hook backlog`, and
   `backlog-service-migration-required`. **`.prawduct/` is excluded by design** — its backlog items
   and artifacts legitimately discuss all five strings (BKL-2Q7F names `migration-scrub.md` in its
   title), so an unscoped grep fails on correct content. The scoping is the point: what makes the
   migration reachable is a *skill a model can route into*, not a record describing one.
4. Assert `skills/backlog/` holds exactly one file; assert `skills/backlog/SKILL.md` grants no Bash
   tool.
5. Full suite green. **No taken test may import any held module** — not just `lib.backlog`:
   `lib.backlog_probes`, `lib.briefing`, `lib.norm_probes` and the held fixtures/fakes all count.
   (The narrower `lib.backlog` wording missed `test_cutover_prose_coherence.py`, which imports
   `lib.backlog_probes`; it is now explicitly held.) Check before running — a green suite that
   silently skipped collection is not evidence.
6. A session opens against the tree and the briefing renders with no migration advisory.

**Checkpoint B — after release-prep.** The delta from checkpoint A is exactly `VERSION`,
`.claude-plugin/plugin.json`, `CHANGELOG.md`, `.prawduct/change-log.md`, and the files
`regen-views` regenerates. Anything else in that delta is unintended.

## Release mechanics

1. Merge `fix/archive-scope-preservation-claim` → `develop` (`/prawduct:pr`). Call the result `M`.
   Until `develop` is pushed, unchanged `origin/develop` plus the reflog are the safety net.
2. **Set `develop`'s tree** to `v3.1.0` + the take-list. Ordinary commit `T` on `develop`, no
   history rewrite, no force-push. Verify checkpoint A.
3. **Create the migration branch as `T` with `T` reverted** — `git branch feature/backlog-service T`
   then `git revert --no-edit T` on it, giving `R`. Push it.

   **This ordering is the whole trick, and the obvious alternative is broken.** Branching the
   snapshot at `M` *before* the tree-set makes it a strict **ancestor** of `develop`: a later
   `git merge feature/backlog-service` reports "Already up to date" and restores nothing, because
   git correctly reads `T` as a deliberate later removal. Branching at `T` and reverting gives the
   branch a commit `develop` does not have, whose tree equals `M`'s — so it holds every migration
   file, diverges properly, and **merges back for real** when v3.2.0 resumes. v3.2.0 work continues
   on top of `R`. (Snapshotting at `M` also predates step 1's merge in the earlier draft, so it
   would have missed `fix/archive-scope-preservation-claim`'s own migration work.)
4. Bump `VERSION` **and** `.claude-plugin/plugin.json` to `3.1.1` — this is the release trigger;
   without it `autoUpdate` keeps the cached copy and the release does not ship.
5. Change-log: the **eight** independent entries flip to `status=shipped` + `release=v3.1.1`. **The
   other ten — every one of them migration work — stay release-pending and must not be flipped.**
   Enumerate all eight against the table above; do not sample (REL-2N8K shipped 8 of 10 that way).
   **One of the eight sits *below* the `release=v3.1.0` boundary**, so a positional sweep will miss
   it — walk the table, not the file order.
6. Add the `## v3.1.1` headline to `CHANGELOG.md` (one paragraph, consumer-facing).
7. `regen-views --check` → `regen-views`. Verify checkpoint B.
8. Promote `develop` → `main` by tree-set per `docs/release-process.md` step 1 mechanics; the
   `git diff --stat origin/develop HEAD` content-identical invariant must be empty. Tag `v3.1.1`,
   push.
9. Confirm the version-delta banner on the next session.

## Carried forward, not resolved

- All migration work lives on `feature/backlog-service` at `R`, whose tree equals `develop`'s
  immediately before the tree-set; the v3.2.0 plan is unchanged and still owns it. Resuming means
  merging that branch back into a `develop` that has moved — one substantial conflict resolution,
  accepted deliberately as the price of a releasable `develop`. The merge works because `R` is a
  revert commit `develop` does not contain; a plain snapshot branch would have been an ancestor and
  merged as a no-op.
- The five defects this review surfaced in the migration surface — no repo-selection step, the
  fictional `--apply`/dry-run contract, `provision` absent from every skill, the wildcard Bash grant,
  and the advisory pointing at all of it — are **v3.2.0 blockers** and belong on that plan's ship
  list. They are not fixed here; they are excluded from shipping.
