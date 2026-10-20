---
artifact: build-plan
version: 2
scope: change-log-fragments-wave-2
branch: feature/change-log-fragments-wave-2
depends_on:
  - artifact: documentation/issues/1012-requirements.md
  - artifact: documentation/issues/1012-design.md
  - artifact: .prawduct/artifacts/build-plan-change-log-fragments.md
governed_by:
  - artifact: data-model
    dispositions:
      - "Critic-data-plane verdicts come from the fact ledger → inapplicable because fragments are not Critic facts and no Critic verdict reads them"
      - "facts immutable and append-only → inapplicable because that norm's stated scope is the evidence store; the trunk cut moves fragment content verbatim into the append-only archive and never edits archived history"
      - "governance documents archived, never deleted → inapplicable because the norm covers .prawduct/artifacts/; this wave writes .prawduct/changes/ and the change-log archive"
      - "newer-schema facts block loudly → conforms: unchanged from wave 1 (`schema: 1` required, higher refused)"
      - "two stores, two lifetimes → conforms: fragments are committed shared answers; the Step 1c untracked path reads the on-disk copy only where git cannot answer, and says so"
      - "backlog_service_repo selects the store → conforms: the merge-time close reads `closes:` through the change-record owner and routes through /prawduct:backlog"
      - "derived views never authoritative → conforms: the cut still writes the digest only at plugin/CHANGELOG.md, and no gate reads it"
      - "backlog issues conform to the title standard on every write path → inapplicable because fragments create no backlog issue; the close only changes status through /prawduct:backlog"
  - artifact: architecture
    dispositions:
      - "local-first, stdlib-only governance runtime → conforms: Python stdlib only"
      - "authority fails closed, advice fails soft → conforms: the change-record owner refuses when git cannot answer; the union-attribute probe stays advisory in both directions"
      - "the plugin writes nothing into a governed repo except its own `.prawduct/` state and the files it must reconcile → conforms, and this is the re-decision wave 1 owed: init_product and the migration write only under `.prawduct/`; the cut writes a digest only at `plugin/CHANGELOG.md`, which only prawduct's own repo publishes, so no consumer repo's digest is ever written (a product-declared digest is #733's); `.gitattributes` stays advice, never written"
      - "written in Python, never specific to Python → conforms: no reader dispatches by language"
      - "reviewer never mutates the session it reviews → inapplicable because no review path writes fragments or the archive"
      - "guides and reviews, never implements → conforms: this governs the product's own change record and writes no product code"
      - "goals and verification bind, prescribed method is advice → conforms"
      - "every fact has one home → conforms: `change_fragments.branch_change_record` becomes the one home for 'this PR's change record', which Step 1c, pr_payload and the merge-time close all read"
  - artifact: api-contract
    dispositions:
      - "whole-surface semver; CLI subcommands internal → conforms: any new subcommand joins the internal/unstable tier"
      - "exit codes are the contract on a documented scheme → conforms if new verdicts keep the existing scheme (0 pass, 1 refused with a named reason); checked at review"
      - "additive-first evolution → conforms: check-change-log-entry keeps every verdict name; new ones are added beside them"
partition: serial — 02's migration and scaffold rely on 01's readers accepting a repo with no live log, and 03's trunk owner is read by the Step 1c path 02 changes
last_validated: 2026-10-20
---

# Build Plan — Change-Log Fragments, Wave 2: onboarded repos (#1023)

## Goals

**Response taken:** Proceed citing #1023 (wave 2 of #1012), its eight scope items, and the wave 1
plan's mid-build decisions that deferred each one here. Design: `documentation/issues/1012-design.md`
(D4 trunk paragraph, D6 migration and probe gating).

**Product:** Wave 1 moved prawduct itself onto `.prawduct/changes/` fragments. Onboarded product
repos still scaffold, migrate and check against the single shared `change-log.md`, so none can
adopt fragments, and #1022 (dual-shape expiry) cannot land. Wave 2 makes a fragments-only repo a
first-class, correctly-read repo and gives existing repos a tested path onto it.

Measured 2026-10-20 over the onboarded repos under `~/source`: most are gitflow, a few trunk, and
several gitflow repos hold dozens of release-pending legacy entries (they never cut releases), so
the migration converts many entries per repo and its refusals will meet real data.

**Inferred where the issue is silent** *(flagged for the boundary review)*:
- **No consumer digest writes.** The cut writes notes only to `plugin/CHANGELOG.md`, which consumer
  repos do not publish; a product-declared digest is #733. This is the architecture-norm
  re-decision wave 1 owed, and it needs no code.
- **Trunk, versioned:** Step 1d cuts the branch's own fragments (`cut-change-log --scope … --release
  vX.Y.Z --apply`), after one owner (`branch_change_record`) lets every later reader find the record
  as an archive entry. **Trunk, unversioned:** fragments stay pending, exactly as legacy entries
  stayed untagged there.
- **The union probe has two states, not one:** pending legacy entries and no union → recommend
  adding it (today's advice); fragments recorded, no pending legacy entries, union still set →
  recommend removing it, because union on a log that only archive moves edit is the #857
  resurrection path. Still advice only.
- **The "dual-shape readers" check (D6 risk)** is a check of the repo's committed install reference:
  a `ref` pinned to a version tag older than the release that introduced fragment readers. A plugin
  running this code trivially has the readers; other clones read the committed ref.
- The migration does not delete the live log; shipped history stays in it until the existing size
  archive moves it.

**Constraints:** Python stdlib only. Archived history is never rewritten. Nothing may require a
post-merge commit (`/prawduct:pr` Step 1d). `.gitattributes` is never written.

**Decisions made mid-build:** *(one line each, naming what settled it)*
- Chunk 01: `load_all_text` lost its opt-in `missing_live_ok`; an absent live log is empty for
  every caller, and only an unreadable one is `None`. One owner, not a flag at each caller.
  Settled by core.md (fix the class through one owner).
- Chunk 01: the union probe keys its direction on the fragment directory existing, not on
  pending legacy entries alone (D6's wording). A legacy repo with nothing pending today will
  prepend tomorrow, so the add-advice stays on for it; the pending check gates only the removal.
  Settled by what each direction protects.
- Chunk 01: this repo's `.gitattributes` held only the union line, so it is deleted. Our own new
  advisory fired here, and complying was the right answer (gates.md: a nudge firing on this repo
  is signal).
- Chunk 01: `init-product` leaves a repo that already has a legacy log on it (no fragment
  directory), because scaffolding one would split its record; `migrate-change-log` is that
  repo's path. `templates/change-log.md` stays for the dual-shape window; #1022 retires it.
- Chunk 02: the migration converts what real logs carry instead of refusing it. A dry run over copies of the 22 onboarded repos' logs refused on 17 (missing types, retired `chunks=`/`status=` keys, dash headers, one repo with four pending entries in one scope). Extra keys become a `Legacy tags:` narrative line, shared scopes merge, dash headers parse, more synonyms map, and a missing or unmappable type takes an owner-chosen `--default-type`, listed per entry. With `--default-type chore` 20 of 22 convert; the other two hold genuine two-tag-line entries their authors must merge. Design D6 is amended. Settled by the goal (a tested migration path for onboarded repos) and hook-surface.md (tolerate the natural encoding variant). *Changes D6's refusal contract; flagged for the boundary review.*
- Chunk 02: the install-pin check is `change_migrate.install_pin_too_old`, which the migration refuses on (`plugin-pin-too-old`) and doctor reaches through the same dry run. Only a ref that is a release older than v3.7.2 is judged; a branch or commit is not a pin it can read.
- Chunk 02: Step 1c in a repo that ignores the fragment directory answers `fragment-present-untracked` from the valid fragments on disk, the twin of `entry-present-untracked`, and both its remedies name the un-ignore pattern.
- Chunk 02 (review observations, fixed after commit): a log with nothing pending still adopts fragments (the migration writes `.gitkeep`), so doctor #22 can clear; and a merge or default keeps every entry's own type in its `Legacy tags:` line, the newest valid type deciding.
- Chunk 03: the owner is two functions in `change_fragments`: `branch_change_record(base)` for readers with a branch diff (Step 1c, `pr_payload`), and `scope_change_record(scope)` for the merge-time close, which runs after the merge, when no branch diff is left. An archive entry counts as the branch's only when its text is in neither the base's archive nor the base's live log, so size-archive moves are history, not a record. Settled by D4's requirement that every reader go through one owner.
- Chunk 03: `change-record` is a read-only subcommand (exit 0 found, 1 one missing, 2 usage), granted to the PR skill with `cut-change-log` for the trunk step.
- Chunk 03, verified 2026-10-20: in a repo `init-product` created, one fragment went through `check-releasability`, `cut-change-log --scope … --apply`, `plan-backfill` (archives the plan as shipped in v1.0.0), `check-releasability` (releasable) and `change-record` (archive entry). The trunk walk is pinned in `tests/test_change_record.py`.
- Chunk 01 → Chunk 03: `oversized_state_probes` still advises moving an inline `change_log` key
  into `.prawduct/change-log.md`; that is item 8 prose, swept in Chunk 03.

**Level:** Medium-high. Every item was scoped in wave 1's decisions; the trunk owner is the one
piece of new design.

## Status

- [x] Chunk 01: A fragments-only repo reads correctly (scope items 1, 3, 4, 5)
- [x] Chunk 02: Existing repos migrate; Step 1c works where `.prawduct/` is ignored (items 2, 6)
- [x] Chunk 03: Trunk PRs own their change record; methodology prose (items 7, 8)
Context: all three chunks are built. 01 and 02 are committed and chunk-reviewed (0 blocking); 03 is committed and owes the cumulative review, which is this plan's boundary. For the owner at that boundary: the inferences in Goals, and the D6 refusal-contract amendment (Chunk 02).

## Verification Strategy

Beyond unit tests: a scratch repo scaffolded by `init-product` (no live log) runs
`check-releasability`, `plan-backfill`, `record-lint` and a `cut-change-log` against an archive.
Chunk 02 dry-runs `migrate-change-log` on copies of real onboarded repos (never the originals) and
records each refusal code met. Chunk 03 runs a trunk PR's Step 1c → 1d cut → Step 1c re-run →
payload → close list in a scratch trunk repo.

## Build Chunks

### Chunk 01: A fragments-only repo reads correctly

- **Description:**
  - `change_log_archive.load_all_text`: an absent live log means an empty one for every history
    reader. Remove the opt-in `missing_live_ok` rather than passing it at each caller, so the class
    (a reader that assumes the live log exists) is fixed in its owner. Callers by query:
    `release_readiness._history_entries`, `plan_backfill`, both `record_lint` sites.
  - `archive_would_be_ignored` keys on whichever record the repo tracks: the live log, or the
    fragment directory.
  - `gitattributes_probes`: the add-union advice fires only while the legacy log has pending entries;
    the remove-union advice fires when fragments are recorded, no legacy entry is pending and union
    is still in force. Doctor item 17 states the same two states.
  - `init_product` scaffolds `.prawduct/changes/.gitkeep` and no `change-log.md`; onboard and doctor
    "core state" text follow.
- **Depends on:** none
- **Deliverables:** `plugin/lib/change_log_archive.py`, `release_readiness.py`, `plan_backfill.py`,
  `record_lint.py`, `gitattributes_probes.py`, `init_product.py`; doctor and onboard skill text.
- **Tests:** a fragments-only fixture (archive, no live log) for `_history_entries`, `plan_backfill`
  shipped-scope reading and `record_lint`; `archive_would_be_ignored` with a tracked fragment
  directory; each union-probe state, including silence on a fully migrated repo with no union;
  `init_product` output has the `.gitkeep` and no log. Each red-verified.
- **Acceptance criteria:** in a repo `init-product` just created, after one fragment is cut to the
  archive, `plan-backfill` reads that scope as shipped and `check-releasability` sees its history.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: Existing repos migrate; Step 1c works where `.prawduct/` is ignored

- **Description:**
  - `/prawduct:migrate` runs `migrate-change-log` (dry run, then `--apply` with the owner's approval)
    after the plugin move; `/prawduct:doctor` offers it when a repo has a legacy log with pending
    entries and no fragment directory.
  - The install-reference check: `migrate-change-log` refuses (`plugin-pin-too-old`) when the
    committed install reference pins a version tag older than the fragment readers; doctor reports
    the same function's answer.
  - Step 1c, `.prawduct/` ignored: when git cannot see the fragment directory, the probe answers from
    the on-disk fragments (`fragment-present-untracked`, a manual-confirm pass like
    `entry-present-untracked`) and its remedy names the un-ignore pattern, so following the advice
    can clear the gate.
- **Depends on:** Chunk 01
- **Deliverables:** `plugin/lib/change_migrate.py`, `plugin/lib/coverage.py`, migrate / doctor / pr
  skill text.
- **Tests:** pin check (pinned old tag refused, branch ref and newer tag pass); Step 1c in a repo that
  ignores `.prawduct/`, with and without a valid fragment on disk, and an invalid one refused.
- **Acceptance criteria:** a dry run on copies of the onboarded repos completes or refuses with a
  named code on every one; each code met is listed in Decisions with what its author must do.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: Trunk PRs own their change record; methodology prose

- **Description:**
  - `change_fragments.branch_change_record(project_dir, base)` is the one owner of "this PR's change
    record": fragments the branch added, plus archive entries the branch added (a trunk cut), each
    with its scope and `closes`. Step 1c, `pr_payload`'s change-log section and the merge-time close
    read through it; the close gets a CLI (`prawduct-hook change-record [--json]`) so the skill stops
    reading a path that a trunk cut removed.
  - PR Step 1d gains the trunk instruction: on a versioned trunk, cut the branch's own scopes before
    the review gates; unversioned, leave them pending.
  - Item 8: reword plugin methodology and skill text that still describes the legacy log as the only
    shape (onboard, migrate, doctor, PR). Sweep by the claim ("append an entry", "release-pending is
    the absence of `release=`"), not by edited tokens.
- **Depends on:** Chunk 02
- **Deliverables:** `plugin/lib/change_fragments.py`, `coverage.py`, `pr_payload.py`,
  `plugin/bin/prawduct-hook`, PR skill Step 1c/1d/merge step 6, the swept prose; this branch's own
  fragment.
- **Tests:** in a scratch trunk repo, a branch that added then cut its fragment passes Step 1c, shows
  its record in the payload and yields its `closes` list; a branch with neither is `no-entry`.
- **Acceptance criteria:** the trunk walk in Verification Strategy passes end to end; the claim
  search returns only history or the explicitly legacy path.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk after its Critic review. The last chunk's cumulative
review makes the branch PR-ready.

- After chunk 02: report the migration dry-run results across the onboarded repos to the owner
  before any real repo is migrated (this branch migrates none).
