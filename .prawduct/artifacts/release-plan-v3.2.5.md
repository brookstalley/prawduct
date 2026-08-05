# Release plan — v3.2.5

**Cut from:** **whole-develop at Phase 2** — the tip as of the promotion, not a pinned commit.
`K withheld = 0` selects whole-develop promotion, which makes the tip the answer. (Stated as a
rule rather than a sha deliberately: v3.2.3 recorded a pinned commit and had to walk it back
five times as the release grew.)
**Previous release:** v3.2.4

## Version decision

**Patch bump, 3.2.4 → 3.2.5.** Owner-directed ("+0.0.1"), and consistent with the ratified norm
(`operational-spec.md` § Direction, 2026-07-17): *versioning is conservative — a small feature is a
patch bump, not a minor-per-feature.*

**Recorded because two things in this release are arguably more than a fix, and a minor was not
taken.** `review-round-pricing` adds a genuinely new hook subcommand (`cost-of-commit`, with a
registered `--json` emitter), and `ephemeral-worktrees` adds a **pre-dispatch refusal** — a path
that previously accepted a write now rejects it. Under the observed (unratified) minor tier —
*a substantial new capability or a subsystem going live* — neither qualifies:

- `cost-of-commit` **prints and advises; it gates nothing.** It answers "does this commit buy a
  review round?" ahead of the commit. No caller is required to consult it and no gate reads it.
- The ephemeral-worktree refusal **is the fix, not a new bound.** The prior behaviour was to accept
  a backlog write inside a disposable subagent worktree, report success, and lose it at merge
  (#594). Refusing is what makes the reported success true. Nothing an adopter depends on changes
  shape — the writes that used to survive still survive.
- No persisted format changes and no gate semantic breaks.

`release-integrity` Chunk 05 is CI, repo-local to prawduct, and not consumer-visible at all.

## Release classification

| Scope | Disposition | Blocker |
|---|---|---|
| review-round-pricing | ships | |
| ephemeral-worktrees | ships | |
| release-integrity | ships | |

`K withheld = 0` → **whole-develop promotion** (runbook Phase 2 steps 14–20), not the pruned path.
Content-identity between `main` and `develop` was re-established at v3.2.0 and has held through
v3.2.4; this release holds it.

### Blocker liveness — vacuous by construction, not skipped

This repo is on the GitHub Issues backlog backend (`backlog_service_repo: brookstalley/prawduct`),
so `.prawduct/backlog.md` is frozen history and blocker liveness cannot be read from it — the
condition that makes `check-releasability` refuse with `cannot-verify-blockers:`. It does not fire
here for the same reason it did not at v3.2.3: **the gate reads blocker liveness only for rows that
name a blocker, and no row here does.** Every scope ships, so there is no withholding decision whose
premise could have expired.

Recorded rather than passed over, because a release later "there was nothing to check" and "I did
not check" look identical in hindsight. The first release that **withholds** a scope is where
`cannot-verify-blockers` will actually bite.

### The release-pending set — how it was derived

Per runbook step 2, the boundary (topmost tag line carrying `release=`) is
`.prawduct/change-log.md:433` (`release=v3.2.4`). Nine statusless entries sit above it and **none
below** — the whole-file statusless sweep returns exactly those nine, across exactly the three
scopes `check-releasability` enumerated. Every entry carries a `scope=` key, so there is no
unscoped-and-invisible entry of the kind v3.2.3 had to tag by hand.

The per-candidate **code test** was run rather than inferred from position:

| Probe | v3.2.4 | develop |
|---|---|---|
| `cost-of-commit` in `plugin/bin/prawduct-hook` | 0 occurrences | 4 |
| `ephemeral` in `plugin/lib/evidence.py` | 0 occurrences | 9 |

Both absent from the previous release's tree ⇒ both genuinely unreleased.

**`release-integrity` is the third case and needs stating precisely, because the code test does not
decide it.** Chunk 05 already shipped in v3.2.4 (`change-log.md:881`), and
`.github/workflows/verify-release.yml` is present at that tag. What is release-pending is a
**second entry against the same chunk** (`change-log.md:360`) recording that the chunk's last
acceptance item was discharged *after* the v3.2.4 promotion — which is the only time it could be,
since GitHub registers a workflow from the default branch and the workflow therefore could not run
until a promotion carried it there. So the scope is release-pending on the **tag test** (statusless
entry) rather than the file test, and after this release its rollup correctly reads
`releases: ["v3.2.4", "v3.2.5"]` for chunks `["04", "05"]`.

*(Counts are a measurement of one tree on 2026-08-05, not a property of the repo.
`check-releasability` is the live answer.)*

## Consumer-facing headline

> A review round now has a price you can see before the commit that buys it — and a write that
> would have vanished with a disposable subagent worktree is refused instead of silently lost.

## What ships

**`review-round-pricing` (Chunks 01–03) — the flagship.** v3.2.4 shipped the fix for the review
loop over-running, and a consumer on v3.2.4 read those carriers and ran six Critic rounds anyway.
This is the second attempt, and it moves the answer from prose to a mechanism that fires *before*
the commit rather than diagnosing after it:

- **`prawduct-hook cost-of-commit`** — the first mechanism that answers "does this buy a review
  round?" ahead of the commit. It asks `coverage_algebra.is_judgeable_path` rather than carrying a
  second copy of the rule, so it cannot disagree with the gate that charges.
- **The round is priced, never quoted** — `telemetry.round_price` derives the figure from this
  repo's own ledger at call time with a sample floor, and `telemetry.format_minutes` is the one home
  for rendering it. `duration_seconds` is stated as a reviewer self-estimate, so the number is not
  defended as measured.
- **The gate knows which round this is** — `coverage.count_branch_rounds` leads the `uncovered:`
  block, so round five stops reading like round one.
- **The ride-along route** — carrying a small fix into the next chunk's commit costs nothing extra:
  the option the fix/accept/file trio never named.
- **A new PR-review leg** — `skills/pr/review-protocol.md` now tells the reviewer, above every
  finding-producing section, that its own non-blocking findings cost the builder a delta round.

**`ephemeral-worktrees` (Chunks 01–03).** `methodology/building.md` recommends
`isolation: "worktree"` for parallel chunks; following that advice puts a subagent in a worktree
forked from HEAD **of which only the code commit is merged back**. prawduct had no representation of
that, so `resolve_project_dir` followed the session in and governed the worktree as an ordinary peer
checkout — an agent obeying prawduct's own rule ("file it via `/prawduct:backlog`") produced a write
that died at merge and was told it had succeeded. Reported from a product repo (**#594**).
`gitstate.is_ephemeral_worktree` is the missing predicate and a pre-dispatch guard refuses the
write. Evidence facts now carry visible worktree provenance, and delegation guidance states the
snapshot and the shared index.

Riding the same branch by owner decision, and stamped without flipping a plan checkbox:
**the findings view now says which review it is** (#595) — `.critic-findings.json` survived every
dispatch carrying nothing that marked it stale, and the briefing's own summariser rebuilt the
section field by field, dropping all three supersession keys and presenting a superseded review's
counts as current to the one reader who definitionally cannot check; and a **norm birth**,
`project-preferences.md` § Workflow **Backlog filing** — a strong bias to fix rather than file, with
a new item justified only when the finding is both orthogonal to the current work and medium or
larger.

**`release-integrity` (Chunk 05 residual).** The chunk itself shipped in v3.2.4; what ships here is
the discharge of **#581**, its last acceptance item and the only one that could not be met at merge —
GitHub registers a workflow from the **default branch**, so `verify-release.yml` could not run at all
until the promotion that carried it to `main`. It ran three ways once the v3.2.4 promotion landed.
Repo-local to prawduct; no consumer-visible surface.

`build-plan-release-integrity.md` keeps Chunks 01–03 unchecked after this release — 03's probe half
is blocked behind `feat/advisory-actionability`, and 01/02 are the deprioritised pair. A partially
shipped plan is the normal case here (cf. `v3.2.0-golive`), not an omission.

## Runbook step 11 — `active_build_plan` cleared, no departure

The pointer held `artifacts/build-plan-ephemeral-worktrees.md`, and this release's `regen-views`
flipped all three of that plan's chunks to shipped. It names a **completed** plan, so clearing it
orphans nothing and step 11 was executed normally. It was deliberately *not* repointed at
`build-plan-release-integrity.md` (which does keep three unchecked chunks): `project-state.yaml`'s
own comment block records three stale-pointer incidents, each one the pointer naming a plan that was
not the plan under review, each producing a wrong verdict. `null` is the honest value when no work
is in flight.

**Known consequence, chosen rather than discovered** — the same one v3.2.3 recorded. `develop` names
no declared scope, so with the pointer null `has_build_plan` is False from the next session, which
downgrades the reflection gate to advisory and skips the Stop-hook Critic gate entirely. The prep
commit and the Phase 2 promotion therefore run ungated. Accepted: Phase 2 authors nothing (it is
`git read-tree` plus a push), its real protections are the runbook's step 17/18 content-identity and
version checks, and buying gate coverage by feeding the gate a false input is the stale-pointer shape
that caused three wrong verdicts already. Re-arming is automatic at the next `/prawduct:backlog pick`.

## Ship-time actions

- **Close #581 by hand.** Its change-log entry records why: a `Closes #NNN` in a *file body* is
  prose, and this repo merges to `develop` rather than the default branch, so neither a commit
  message nor a PR body would auto-close it either.
- Confirm #594, #595 and #600 are closed or closed at ship time by the same reasoning.

## Owner release gate

**None declared for v3.2.5.** v3.2.3 carried three blocking items because it took the backlog
service live and changed fleet-visible governance invisible to this repo's own suite. This release
carries no go-live, no persisted-format change, and no advisory whose audience widens. The
sibling-repo exercise that item 1 of that gate demanded is *not* re-imposed here — recorded as a
decision rather than an oversight, on the argument that the consumer-visible surface is one new
advisory-only subcommand and one refusal that fixes a data-loss path.

**Residual risk, stated:** the ephemeral-worktree refusal is the one change that can turn a
previously-succeeding call into a failure. It is confined to worktrees the predicate identifies as
ephemeral, and the prior behaviour on exactly that path was silent data loss — so a false positive
costs a refused write that would have been lost anyway, and a false negative restores the status
quo ante. That asymmetry is why this is accepted without a live fleet exercise.
