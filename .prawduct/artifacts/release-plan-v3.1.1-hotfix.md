---
artifact: release-plan
version: 1
scope: v3-1-1-hotfix
depends_on:
  - artifact: release-plan-backlog-service-golive
last_validated: 2026-07-21
---

# Release Plan — v3.1.1 Hotfix

## Execution status — read this first

**Steps 1–8 landed (2026-07-21). Next action: release mechanics step 9 — the promotion.**
Paused there deliberately at owner request: step 9 is the first irreversible, outward-facing action.

| step | state | result |
|---|---|---|
| 1 merge to `develop` | ✅ | `M = e5ec3d2` (two merges + the fold-in commit) |
| 2 tree-set + checkpoint A | ✅ | `T = fcb4e5f`; all six items pass |
| 3 `feature/backlog-service` | ✅ | `R = 7fc00e1`, **pushed**; tree == `M`, not an ancestor of `develop` |
| 4 version bump ×3 | ✅ | `VERSION`, `plugin.json`, `pyproject.toml` → `3.1.1` |
| 5 change-log flip | ✅ | 9 flipped, 10 held |
| 6 `CHANGELOG.md` | ✅ | `## v3.1.1` headline |
| 7 `active_build_plan: null` | ✅ | |
| 8 `regen-views` + checkpoint B | ✅ | `c4fd21a`; delta is exactly the 8 expected files |
| 8b **packaging boundary** (GOV-4H7T) | ✅ | added after the Critic pass — see below |
| 9 promote, tag, push | ⏸ | **awaiting owner** |
| 10 confirm banner | ⏸ | next session after 9 |

**Step 8b — scope added mid-release, deliberately.** The Critic's Principle 10 finding (two `.js`
files held by hand while 256 KB of raw research shipped) led to the owner stating a requirement this
plan had not carried: *prawduct's internal requirements and documentation must not land in consumer
plugin caches — not secret, but confusing to models working on consuming projects.* The owner
explicitly rejected deferring it as pre-existing: **"our whole ethos is to fix what you find, and
this may have a material impact on prawduct's performance for users."** Recorded because it changed
the release's scope after construction was verified, which is exactly the kind of decision that
looks arbitrary six weeks later.

The fix is `plugin/`, a curated plugin root holding the distributed files as **real files**, with
`marketplace.json` pointing at it. A relative-symlink farm was built first and rejected on evidence:
with `core.symlinks=false` (the Git-for-Windows default) every entry checks out as a few-byte text
stub and the plugin installs inert. Moving the files for real costs a wide diff and buys
correctness on every platform. Verified by **real install into an isolated `CLAUDE_CONFIG_DIR` from a fresh clone** — **109
files / 1.7 MB**, down from 203 files / ~6.7 MB — not by reading the docs. (An intermediate
measurement of 120 / 1.8 MB predates the `docs/` curation and should not be quoted.) Two findings only the
install produced: `VERSION` must ship (read at runtime by `lib/core.py:36` and `lib/evidence.py:85`,
so a code-directories-only curation would have broken evidence writes for everyone), and a
local-path install copies untracked working-tree files, putting 132 `.pyc` files into the cache
including `lib/backlog/__pycache__` — compiled bytecode of the modules this release withholds. Every
check run before that one queried *git* and was structurally blind to it.

`tests/test_plugin_packaging.py` pins the boundary and is mutation-tested against three regressions.
Ten change-log entries now ship rather than nine.

**Nothing is published.** `origin/develop` is still `43dda9c` and `origin/main` is still `b08c301`
(= `v3.1.0`). The only thing pushed is `feature/backlog-service`, which is purely additive. Every
step above is undone by `git reset --hard 43dda9c` on `develop` plus deleting that branch.

Checkpoint A evidence (2026-07-21): path-set equality **54 = 54** exact; completeness precondition
**31 take + 65 held = 96**; all five negative-grep strings **0** across `skills/ lib/ bin/ hooks/
methodology/ documentation/ docs/ templates/`; every partial-take marker at its expected count
(`cmd_backlog` → 0, `cmd_version` → 2, `prawduct-hook version` dispatches and prints); suite
**1965 passed / 0 failed**; briefing renders with the migration advisory **resolved**.

Update this block as each step lands — it is the only cross-session record of *where execution
stands*, and the steps are stateful — later steps consume names earlier steps produce, so a step
done out of order has nothing to bind to.

Two orientation notes for a session picking this up cold:

- **The session briefing will misdirect you.** `project-state.yaml` still carries
  `active_build_plan: artifacts/build-plan-skills-cutover-awareness.md`, so the briefing announces
  `Work: Skills Cutover Awareness` and resumes that plan's first unchecked chunk. That pointer is
  *correct* state — that plan is unfinished work moving to `feature/backlog-service` — but it is
  **not** the active work. This release plan is. (Release mechanics now clears it to `null` at
  release-prep, so this note expires with the release.)
- **Nothing is pushed yet.** `origin/develop` still points at the pre-merge commit and does not
  move until the promotion step; that, plus the reflog, is the safety net. `feature/backlog-service`
  becomes the durable holder of the migration work at the branch-creation step.

**Owner decision (2026-07-20):** ship the release-pending fixes now carrying **zero
backlog-service surface**, by **isolating the migration work off `develop`**. Current `develop` is
snapshotted as `feature/backlog-service`; `develop`'s *tree* is then set to the v3.1.1 candidate,
and v3.1.1 ships as an ordinary `develop` → `main` promotion. The v3.2.0 go-live plan is unchanged
and still owns the migration.

**Amendment — owner decision (2026-07-21): fold in the runbook feature.** `feature/runbook-authoring`
(docs, skill, template, and the four registration edits) ships in v3.1.1 rather than waiting. This
changes the plan's *premise*, not its construction: the release is no longer "fixes only," it is
"everything independent of the migration," and the runbook work qualifies on exactly the test the
What-ships table already applies. Consequences, each carried into the sections below rather than
left here: **+10 changed paths** (96 non-`.prawduct`, not 86), **a ninth shipping change-log entry**,
**a fourth partial-take file**, and **two new grep scopes** (`docs/`, `templates/`).

**The version stays v3.1.1, and that is the norm, not a departure.** An earlier draft of this
paragraph called it "a departure worth naming" on the grounds that a new user-invocable skill is a
minor bump "by the convention `CHANGELOG.md` records." **That was wrong, and the error is
instructive.** The convention was inferred from reading past `CHANGELOG.md` entries; the actual rule
is a **ratified norm** in `operational-spec.md` `## Direction` (2026-07-17), with a pointer row in
`project-preferences.md`:

> **Versioning is conservative: a small feature is a patch bump, not a minor-per-feature.**
> A departure (a minor bump for a small change, or the reverse) is a recorded decision, not a reflex.
> Status: steady-state. Judgment norm — no mechanical size test.

So v3.1.1 is the *compliant* number for one small skill, and nothing here needs recording as an
exception. Keeping `v3.2.0` bound to the go-live is a happy consequence, not the justification.

This is Principle 24 (Retrieval Over Generation) failing in its most ordinary form: a plausible
convention was *generated* from sampled evidence when one grep of the governing artifact would have
returned the binding rule. It cost an unnecessary owner decision — the owner was asked to choose
between "semver-correct minor" and "conservative patch" when the norm already prescribed the patch.
Surfaced by the Critic (sustainability, BLOCKING) before the release shipped.

**Also folded in: two release-prep steps this plan was missing**, found by *deriving*
`.prawduct/runbooks/cut-and-publish-a-plugin-release.md` from the guide this release ships.
`pyproject.toml` carries a version — stale at `3.0.3` across v3.0.4, v3.0.5 and v3.1.0 — and
`project-state.yaml`'s `active_build_plan` wants clearing at release. Neither appears in
`docs/release-process.md`; that source-level gap is REL-3M7K's neighborhood and stays open.

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

`develop` plus this branch are release-pending on **19** change-log entries. **10 are
backlog-service migration work; 9 are independent.**

(Was 18/10/8 before the runbook fold-in. The runbook entry did not exist when this was first
counted — the feature shipped its code with **no change-log entry at all**, carried as an
unresolved Critic warning (R-2) across two sessions. That is REL-2N8K inverted: not an entry that
never flips, but code with no entry to flip. Authored 2026-07-21 before the count was re-derived.)

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

All **nine** change-log entries independent of the migration. (Three drafts of this table were
short: the first omitted `worktree-salvage`, the second `stale-remote-base-diagnostics`, and the
third predated the runbook entry's existence. All three were caught by re-deriving rather than by
re-reading. Enumerate, don't sample.)

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
| runbook authoring (2026-07-21, **folded in**) | `/prawduct:runbook`, `docs/runbook-authoring.md`, `templates/runbook.md`, and registration from the methodology skill and the three templates that already pointed at runbooks with nothing behind the pointer (MET-7B3X). The only *new capability* in the release — everything else is a fix. Its entry was authored at fold-in; the code had shipped to `develop` with none |

## Construction — allowlist, verified as an exact diff

**Prerequisite: `fix/archive-scope-preservation-claim` merges to `develop` first.** It carries
`lib/critic_consolidate.py` at **128 insertions / 8 deletions over `develop`**, including the
wait-side cache-warm directive that is a row in the table above. Constructing before that merge
ships the entry's change-log row without its code. The branch is mixed — its `lib/backlog/*` and
`skills/backlog/migration-scrub.md` work lands on `develop` too, and is then held back by this
allowlist like the rest of the migration surface.

**The branch was cut back before merging, and the reason generalizes.** By 2026-07-21 it had grown
six runbook commits on top of `dc517a9` — the commit every count in this section was measured
against. Those six were superseded by `feature/runbook-authoring`, which carries the same work
rebased plus 25 further refinements. Merging both would have duplicated and conflicted, and worse,
pushed unclassified paths through a construction whose entire safety argument is set equality
against an exhaustive list. So the branch was reset to `dc517a9` (backup ref
`backup/fix-archive-scope-with-runbook`) and the runbook work came in through its own branch, where
it is classified. **A release measured against one commit must be built from that commit** — a
branch that moves under a verified take-list silently invalidates it.

Build the candidate as **`v3.1.0`'s tree plus allowlisted paths from `develop`**, then set
`develop`'s tree to it. Allowlist rather than subtraction for one reason — it **fails closed**:
anything forgotten is *absent* rather than *shipped*. (Measured **post-merge**, i.e. against the
tree `develop` will have at `M`: **119** files differ from `v3.1.0`, split **96** outside
`.prawduct/` and **23** within. Neither direction is meaningfully less typing; safety is the whole
argument. Two earlier figures are superseded and neither should be carried forward: 101/84/17 was
the query run against *pre-merge* `origin/develop`, wrong once merging first became a prerequisite;
104/86/18 was correct for the fix-branch merge alone, before the runbook fold-in added 10
non-`.prawduct` and 5 `.prawduct` paths.)

**The construction is verified by set equality over paths, not spot-checked.** After the tree-set
and before release-prep, `git diff --name-only v3.1.0 develop | sort` **must equal the fully
expanded take-list** — every `.prawduct/` path enumerated, not globbed. That invariant is
directional-agnostic: it catches a migration file that survived and a needed file that never
arrived, which no negative grep can do alone.

**Two limits of that check, stated so they are covered elsewhere rather than assumed away.**
(a) It compares *paths*, so for the **four** partial-take files — `skills/critic/review-cycle.md`,
`bin/prawduct-hook`, `skills/critic/review-protocol.md`, `skills/runbook/SKILL.md`;
`lib/probe_families.py` is a **whole-file**
take — it cannot see *which* hunks landed. Their content is verified by the positive assertions in
checkpoint A item 2, not by the negative grep, which catches leaks but is blind to omissions.
(b) `CHANGELOG.md` is **identical** between
`v3.1.0` and `develop`, so it is not a take-list entry at all; it changes only at release-prep and
is verified at checkpoint B. **`pyproject.toml` is the same shape** — identical at `v3.1.0` and
`develop` (both `3.0.3`), so it is not a take-list entry either and is bumped at release-prep.

**Whole-file, safe to take from `develop`:**
`hooks/banner.py` · `lib/gitstate.py` · `lib/coverage.py` · `lib/gates.py` · `lib/buildplan_refs.py` ·
`lib/critic_consolidate.py` · `lib/stale_base_probes.py` · `methodology/building.md` ·
`skills/ping/SKILL.md` · and their tests (`test_plugin_version_banner` ·
`test_project_dir_resolution` · `test_cumulative_gate` · `test_buildplan_walkers` ·
`test_build_plan_resolution` · `test_critic_consolidate` · `test_stale_base_probes` ·
`test_v5_methodology`).

**The runbook fold-in — 10 paths, 8 taken and 2 held.** Whole-file takes:
`docs/runbook-authoring.md` · `templates/runbook.md` · `skills/methodology/SKILL.md` ·
`templates/observability-strategy.md` · `templates/operational-spec.md` ·
`templates/unattended-operation/failure-recovery-spec.md` · `.gitignore`. Each of the four
registration edits was diffed against `v3.1.0` and carries **only** a runbook pointer — no
migration surface. `.gitignore`'s whole delta is the `.prawduct/research/**/raw/` rule the taken
research files need, so it is a take, not a release-prep edit.

`skills/runbook/SKILL.md` is a **partial take** — see the hunk-level list below.

**Held: `.claude/workflows/runbook-claim-verify-4.js` and `.claude/workflows/runbook-depth-2-claims.js`.**
Owner decision 2026-07-21, on Principle 10 (dev tooling never reaches production). These are
research scaffolding for the runbook work, and the plugin's `marketplace.json` declares
`"source": "./"` — **whatever is in the tree lands in every consumer's plugin cache.** Nothing
loads them, so they are inert rather than dangerous, which is exactly why they are easy to ship by
accident. The accepted cost is stated once: the tree-set *removes them from `develop`*, and they
survive only on `feature/backlog-service` and `feature/runbook-authoring` until deliberately
restored. The durable fix is a packaging boundary so repo-local tooling stops shipping at all —
filed, not fixed here.

**`.prawduct/**` — take whole from `develop`, and it is load-bearing.** Do **not** transcribe its
member paths into this document. Expand the glob **from `M`**, the pre-tree-set merge commit
(`git diff --name-only v3.1.0 M -- .prawduct/`) — never from `develop`, which *is* the tree under
test by the time the check runs (see checkpoint A item 1). It is **23** paths post-merge (18 before
the runbook fold-in added the four `research/runbook-authoring/` files and
`runbooks/cut-and-publish-a-plugin-release.md`), and **this
plan file is one of them**, so a transcribed list goes stale on the edit that transcribes it. An earlier draft
left it unaddressed, which breaks the release two ways. (a) The change-log flip in release mechanics
flips nine entries; if the tree carried `v3.1.0`'s `.prawduct/change-log.md`, **none of the
nineteen entries exist there to flip.** (b) `regen-views` validation is fail-closed on an
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

**`pyproject.toml` needs the same bump, and it has been missed three times.** It carries
`version = "3.0.3"` — stale across v3.0.4, v3.0.5 and v3.1.0. Identical at `v3.1.0` and `develop`,
so like `CHANGELOG.md` it is a release-prep edit, not a take-list entry. `docs/release-process.md`
does not name it either. **This was found by *deriving* the release runbook from the guide this
release ships** — not by reading the process doc, which has been read many times and does not
contain the fact. That is the strongest available evidence for the capability being folded in.

(An earlier draft of this paragraph closed by praising the runbook's `🚧 UNVERIFIED` marker over the
version-bump convention as "honest rather than lazy: no written version policy exists in this repo."
**That closing claim was false** — `operational-spec.md` `## Direction` has carried a ratified
versioning norm since 2026-07-17 — and it survived 220 lines below this document's own correction of
the same error. Removed 2026-07-21. The marker was honest about the *major/minor tiers*, which
genuinely are unratified practice; it was wrong about the conservative-bump rule, which binds.)

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
- `skills/runbook/SKILL.md` — **new at the fold-in, and the negative grep is what found it.** The
  file is otherwise a whole-file take, but its `allowed-tools` frontmatter grants
  `Bash(prawduct-hook backlog *)` **and** `Bash(python3 bin/prawduct-hook backlog *)`. Take the file
  with both grants **removed**; every other token on the line stays.

  **Why it is wrong in this tree specifically.** The grants are correct on `develop`, where
  `/prawduct:backlog` is the Issues adapter and the `backlog` subcommand exists. In the tree this
  plan builds they are wrong twice over: the `bin/prawduct-hook` partial take **deletes the
  `backlog` subcommand**, so the grant names a route the binary denies; and the held
  `skills/backlog/SKILL.md` at `v3.1.0` grants no Bash at all, so the skill's one actual use —
  "File it with `/prawduct:backlog add`" at line 214 — is a slash-command invocation that needs no
  Bash grant from *this* file in the first place. Shipping them would also reintroduce the
  wildcard-Bash-grant shape that is one of the five v3.2.0 blockers this release exists to withhold.

  This is the `cmd_version` self-contradiction argument (below) arriving from the opposite
  direction: there, a dropped hunk would have made `_USAGE` advertise a subcommand the dispatcher
  denies; here, a taken line makes a *skill* advertise a subcommand the binary denies. Both are
  trees that contradict themselves, and neither is visible to the path-set check.

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

Final split after classification: **23 taken, 63 held, 86 total** — and after the 2026-07-21
runbook fold-in added 10 more paths (8 taken, 2 held), **31 taken, 65 held, 96 total.** The 96 is
the number checkpoint A's completeness precondition asserts against; 86 is retained above only
because the ten-file classification below was reasoned against it.

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

That made the partial-take set **three** files, not two: `skills/critic/review-cycle.md`,
`bin/prawduct-hook`, and `skills/critic/review-protocol.md`. (`lib/probe_families.py` remains a
whole-file take.) The runbook fold-in added a **fourth** — `skills/runbook/SKILL.md`, for the two
`Bash(... backlog *)` grants — so the partial-take set is now four files, and checkpoint A item 2
owes a positive assertion for each.

## Verification

**Checkpoint A — after the tree-set, before release-prep.**

1. **The path-set invariant is the load-bearing check.** `git diff --name-only v3.1.0 develop | sort`
   equals the take-list, with `.prawduct/**` expanded **from `M`** (`git diff --name-only v3.1.0 M
   -- .prawduct/`) — never transcribed, and never expanded from `develop`.

   **Expanding from `develop` at check time is self-referential and passes unconditionally.**
   Checkpoint A runs *after* the tree-set, so `develop` **is** `T` — the tree under test. Both
   sides of the comparison become the same command against the same tree, matching in both
   directions for exactly the 23 `.prawduct/` paths the plan argues hardest about (a missing
   `change-log.md` means none of the nineteen entries exist to flip; a missing scope-tagged build
   plan aborts `regen-views` fail-closed). Pinning to `M` is what makes it a check.

   Set equality is what makes an omission as visible as a leak. It compares **paths only**;
   `CHANGELOG.md` and `pyproject.toml` are correctly absent because both are identical at `v3.1.0`
   and change only at release-prep.

   **Completeness precondition — run this first, or item 1 grades itself.** Assert
   `take ∪ held == git diff --name-only v3.1.0 M -- . ':(exclude).prawduct/'` (**96** paths post
   fold-in; was 86). An
   unlisted file defaults to held and is therefore *absent from both sides* of item 1, so item 1
   cannot see it — that is how ten files went unclassified. This precondition is the only check
   that fails on an omission from the lists themselves.
2. **Positive assertions for the four partial-take files.** The path-set check cannot see *which*
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
   - `skills/runbook/SKILL.md` — present → `runbook-authoring.md` (the guide pointer, i.e. the file
     arrived at all) and `user-invocable: true`; absent → `backlog` (zero occurrences on the
     `allowed-tools` line). Assert the *line*, not the file: `/prawduct:backlog add` at line 214 is
     legitimate prose that must survive, so a whole-file `backlog` count is the wrong marker and
     would fail on correct content. Grep the frontmatter line specifically.

   **Why the negative marker is `cmd_backlog` and not `_USAGE`.** `backlog` is absent from
   `_USAGE` at **both** ends — `cmd_backlog` is defined and dispatched without ever being listed —
   so "assert `backlog` omitted from `_USAGE`" would pass unconditionally, checking nothing. The
   symbol that actually moves is the one to assert on.
3. **Negative grep, scoped to the executable and instructional surface** — `skills/`, `lib/`,
   `bin/`, `hooks/`, `methodology/`, `documentation/`, and (added at the runbook fold-in, because
   the fold-in puts take-list files there) `docs/`, `templates/`: zero occurrences of `migration-scrub`,
   `adapter-mode`, `backlog_service_repo`, `prawduct-hook backlog`, and
   `backlog-service-migration-required`. **`.prawduct/` is excluded by design** — its backlog items
   and artifacts legitimately discuss all five strings (BKL-2Q7F names `migration-scrub.md` in its
   title), so an unscoped grep fails on correct content. The scoping is the point: what makes the
   migration reachable is a *skill a model can route into*, not a record describing one.

   **Widening the scope to `docs/` and `templates/` is what caught the `skills/runbook/SKILL.md`
   grant** — though note it would have been caught by the original `skills/` scope too, since that
   is where the file lives. The genuine lesson is narrower and worth keeping: *adding take-list
   files in a directory the grep does not cover silently shrinks the check.* The grep scope is a
   function of the take-list, not a constant.
4. Assert `skills/backlog/` holds exactly one file; assert `skills/backlog/SKILL.md` grants no Bash
   tool. **Assert the same of `skills/runbook/SKILL.md`'s `backlog` grants** (item 2's marker) —
   the two are the same invariant: in this tree, no skill may grant a `prawduct-hook backlog`
   route, because the tree has no such subcommand.
5. Full suite green. **No taken test may import any held module** — not just `lib.backlog`:
   `lib.backlog_probes`, `lib.briefing`, `lib.norm_probes` and the held fixtures/fakes all count.
   (The narrower `lib.backlog` wording missed `test_cutover_prose_coherence.py`, which imports
   `lib.backlog_probes`; it is now explicitly held.) Check before running — a green suite that
   silently skipped collection is not evidence.
6. A session opens against the tree and the briefing renders with no migration advisory.

**Checkpoint B — after release-prep.** The delta from checkpoint A is exactly `VERSION`,
`.claude-plugin/plugin.json`, `pyproject.toml`, `CHANGELOG.md`, `.prawduct/change-log.md`,
`.prawduct/project-state.yaml`, and the files `regen-views` regenerates. Anything else in that
delta is unintended. (`pyproject.toml` and `project-state.yaml` were absent from this list until
2026-07-21 — both were found by deriving the release runbook, not by reading the process doc.)

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
   without it `autoUpdate` keeps the cached copy and the release does not ship. Bump
   `pyproject.toml` to the same number: it is at `3.0.3`, three releases stale, and
   `docs/release-process.md` does not name it.
5. Change-log: the **nine** independent entries flip to `status=shipped` + `release=v3.1.1`. **The
   other ten — every one of them migration work — stay release-pending and must not be flipped.**
   Enumerate all nine against the table above; do not sample (REL-2N8K shipped 8 of 10 that way).
   **One of the nine sits *below* the `release=v3.1.0` boundary**, so a positional sweep will miss
   it — walk the table, not the file order. The release runbook's Phase 1 steps 2–3 prescribe
   exactly that positional sweep; for this release they are **wrong**, and the runbook carries the
   defect. Do not follow them here.
6. Add the `## v3.1.1` headline to `CHANGELOG.md` (one paragraph, consumer-facing).
7. Set `.prawduct/project-state.yaml`'s `active_build_plan` to `null` — it points at
   `build-plan-skills-cutover-awareness.md`, whose remaining work is leaving on
   `feature/backlog-service`, so a shipped tree carrying that pointer misdirects every session that
   opens against it.
8. `regen-views --check` → `regen-views`. Verify checkpoint B.
9. Promote `develop` → `main` by tree-set per `docs/release-process.md` step 1 mechanics; the
   `git diff --stat origin/develop HEAD` content-identical invariant must be empty. Tag `v3.1.1`,
   push.
10. Confirm the version-delta banner on the next session.

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

Added at the 2026-07-21 runbook fold-in:

- **The plugin ships `"source": "./"`, so the repo *is* the distribution.** Two
  `.claude/workflows/*.js` research scripts are held out of this release by hand. Hand-holding does
  not scale and does not survive the next contributor: there is no packaging boundary, so every
  repo-local file is shipped-by-default and the only defence is someone noticing. Filed as durable
  work, not fixed here. Note the tree-set *deletes* the two files from `develop` — they survive on
  `feature/backlog-service` and `feature/runbook-authoring`.
- **`docs/release-process.md` is missing three things** the last two releases needed:
  `CHANGELOG.md` (REL-3M7K, open), `pyproject.toml`, and clearing `active_build_plan`. Each was
  rediscovered rather than read. This plan patches all three for v3.1.1 only.
- **The release runbook prescribes a positional change-log sweep** (Phase 1 steps 2–3), which is
  the exact method this plan's own derivation section proves wrong — it drops entries that merged
  below the last release boundary. The runbook is otherwise sound and was used for this release;
  that step needs correcting before anyone follows it unsupervised. It is also
  `last_verified: null`, which is honest, and this release is the run that could set it.
- **`skills/runbook/SKILL.md` grants `Bash(prawduct-hook backlog *)` on `develop` too.** Held out of
  v3.1.1 as a partial take. On `develop` the grant resolves, so it is not a defect there — but the
  skill's only backlog use is a `/prawduct:backlog add` slash-command invocation, which needs no
  Bash grant from this file. Worth removing at source rather than re-patching every release.
