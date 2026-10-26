---
artifact: build-plan
version: 2
scope: consumer-digest
branch: feature/733-consumer-digest
base: develop
working-branches: []
last_validated: 2026-10-25
depends_on:
  - documentation/issues/733-requirements.md
  - documentation/issues/733-design.md
governed_by:
  - .prawduct/artifacts/architecture.md
  - .prawduct/artifacts/api-contract.md
  - .prawduct/artifacts/data-model.md
  - .prawduct/artifacts/nonfunctional-requirements.md
partition: >-
  01 and 02 serial (coordinator; 02 fixes the shared module's signatures every later chunk calls).
  03 and 04 delegated after 02 commits, two isolated worktrees with disjoint files — A (03):
  plugin/lib/release_readiness.py, tests/test_release_readiness.py, .prawduct/project-state.yaml;
  B (04): plugin/lib/change_cut.py, tests/test_change_cut.py. The coordinator owns
  plugin/lib/consumer_digest.py; a delegate needing a change there reports it rather than making
  it. 05–07 serial: 05 changes prawduct's own procedure on top of 03 and 04, 06 describes it, 07
  integrates.
---

## Goals

**Response taken:** Proceed, citing #733 (#1069 folded in by the owner on 2026-10-25) and
`documentation/issues/733-requirements.md` as revised that day. All three owner decisions are in:
- the plugin may write a product's declared changelog (Decision 7, ruled "1 yes" and recorded
  beneath the `architecture.md` clause);
- prawduct declares its own changelog "like any other" (Decision 1);
- the release-file model, chosen from three options after reading changie's source ("yeah c",
  Decisions 2 and 3).

The owner asked for this "as a requirement for the 3.8.0 release".

**Product:** Every governed product on change fragments writes a consumer note per scope, and
today only prawduct's own cut delivers it. After this plan, a product declares its changelog once.
At the cut, the shipping notes become `.prawduct/releases/<version>.md`, and that text is inserted
into the changelog as a new section. Nothing is searched for and nothing is renamed. The motivating
product, a monorepo whose one root `CHANGELOG.md` is a merge-conflict hotspot, stops editing that
file per PR. Its existing history stays untouched.

**Architecture:**
- **One owner.** "Which file, what shape, where it goes" lives in one place: new
  `plugin/lib/consumer_digest.py` (Chunk 02). Phase 0 and the cut both call it. Neither keeps a
  path constant or a section locator.
- **A release's identity is a file the cut creates** (changie's model). The file existing is the
  re-run guard. The changelog is written, never searched for an open section.
- **Insert, never regenerate.** The cut changes no byte outside the inserted span.
- **Authority fails closed, advice fails soft.** The cut refuses with a named reason. Phase 0 warns
  and never changes an exit code.
- **Must stay possible:** a list form of `consumer_digest:` for per-package changelogs, and
  regeneration from release files if a product ever wants a fully derived changelog.

**Constraints:**
- **Golden test.** Prawduct's changelog result is byte-identical for the same inputs (CD11). The
  golden test is captured from today's code in Chunk 02, before the cut changes.
- **Ships in v3.8.0.** `.prawduct/artifacts/release-plan-v3.8.0.md`'s `ships` row refuses Phase 0
  until this merges. The plan stays live after the merge to `develop` until v3.8.0 ships
  (release.md).
- **The banner is not changed.** `plugin/hooks/banner.py` still parses `## vX.Y.Z` headings. It
  shows no highlight for a dev version, which degrades softly (CD15).

**Tradeoffs accepted:**
- *Develop-pinned consumers lose the dev-version highlight* (CD15). The placeholder it showed
  ("Rolling notes for the next release") carried no information. Revisit if a develop-pinned
  owner misses it.
- *Inferred, owner can veto:*
  - The coverage check retires (Decision 8), because it has no subject under this model.
  - The `by-type` default map is `feature`→Added, `fix`→Fixed, every other type→Changed, Keep a
    Changelog's vocabulary as changie's defaults use it.
  - The default heading is `## {version} - {date}`, with the date taken as the cut's UTC date.
- *Scope not taken:* regeneration, backfilling release files, several changelogs per repo,
  version-file bumps, and integration with external release tools.

**Decisions made mid-build:** (appended while building)
- Chunk 02, write path (2026-10-26). `core.write_all_or_none` is widened, not given a bytes
  sibling. Every prior is read and every write and restore is made with `newline=""`, so the
  rollback no longer re-line-ends a CRLF file. Settled by Architecture's "every fact has one home":
  one transaction body. `ChangelogText.render` returns `str` accordingly, where the design had
  `bytes`; the design is updated. The forward-write test cannot go red on POSIX, which never
  translates `\n` on write; the rollback test is the one that does, and it was shown red against a
  `read_text` prior.
- Chunk 02, declaration validity (2026-10-26). Two refusals the design lacked, both added to the
  design's table:
  - a `heading` that does not lead with the version, because the next cut could not recognise its
    sections;
  - an `entry` without `{note}`, because the notes would be dropped.

  Settled by "authority fails closed".
- Chunk 02, scope (2026-10-26). `ordered_notes` lands in `consumer_digest.py`.
  `change_fragments.render_consumer_section` and its test are deleted in Chunk 04, when the cut
  stops calling it, so no chunk leaves the cut broken.

**Level:** High. The model is chosen by the owner and its prior art read in source, every code
site is read, and the one hard problem (locating a section) is removed rather than solved. What
remains is mechanical: rendering, byte-preserving insertion, refusals.

### Norm reconciliation (`governed_by`)

- `architecture.md` "the plugin writes nothing into a governed repo except its own `.prawduct/`
  state…" — **conforms under the 2026-10-25 owner ruling** recorded beneath the clause: a declared
  changelog is written at a declared seam, by an operator-run cut. `.prawduct/releases/` is
  `.prawduct/` state.
- `architecture.md` "never implements" — **conforms**: release notes the product's authors wrote,
  at an operator's command; no code, config or tooling.
- `architecture.md` "authority fails closed; advice fails soft" — **conforms** (CD7, CD12).
- `architecture.md` "every fact has one home" — **conforms**: `consumer_digest.py`, with the old
  homes deleted (CD13; `_DIGEST_REL_PATH`, `_names_release`, `_digest_write`,
  `_open_digest_section`). Chunk 07 counts the deletions.
- `architecture.md` "Local-first" and "Python but never Python-specific" — **conforms**: stdlib
  only, markdown changelogs in any language's repo.
- `api-contract.md` "exit codes are the contract", "additive-first" — **conforms**: cut exit codes
  unchanged (0 / 1 refused / 2 usage); refusal codes added; nothing repurposed.
- `api-contract.md` versioning — **conforms**: an opt-in project-state key under the plugin semver,
  a minor.
- `nonfunctional-requirements.md` "proportionality ratchets both ways" — **conforms**: Decision 8
  deletes a control whose subject this model removes.
- `data-model.md` norms (fact ledger, append-only facts, derived views, two stores) — **inapplicable
  because** this plan writes no fact or view. Release files are committed answers, like the archive.

## Build Chunks

### Chunk 01: Design — `733-design.md` rewritten for the release-file model

- **Description:** Rewrite `documentation/issues/733-design.md` against the revised requirements.
  The design covers:
  - the `consumer_digest.py` API: the declaration type and reader; the version-heading predicate;
    the insertion-point rule (marker, then first version heading, then end of file); heading,
    entry and layout renderers; and the byte-preserving insert with BOM and CRLF handling;
  - the cut's write set and ordering under `write_all_or_none`;
  - the CD8 re-run decision table;
  - which `release_readiness` and `change_cut` functions are deleted;
  - a worked Keep a Changelog example, and a requirement-to-section trace table.

  The superseded keying-strategy design is deleted, not kept alongside.
- **Depends on:** none
- **Artifacts consumed:** `documentation/issues/733-requirements.md`, `plugin/lib/release_readiness.py`, `plugin/lib/change_cut.py`, `plugin/lib/change_fragments.py`, `plugin/lib/change_log_archive.py`, `plugin/hooks/banner.py`
- **Deliverables:** the rewritten design document
- **Type:** doc-only
- **Tests:** none (doc-only); the design's test plan names each test by requirement id
- **Acceptance criteria:**
  - every CD and CDOC requirement maps to a design section;
  - no paragraph describes section keying or a hard-coded prawduct path as current;
  - the insertion rule and the re-run table are stated precisely enough to test.
- **Done when:**
  1. Acceptance criteria met
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed

### Chunk 02: `consumer_digest.py`, plus the golden baseline

- **Description:**
  - **Golden first.** A test runs today's `cut-change-log --apply` on a prawduct-shaped fixture and
    pins the resulting `plugin/CHANGELOG.md` bytes. The fixture has two fragments (one `none:`) and
    a `## v9.9.9` section (already renamed, as the runbook does before the cut) holding a headline. The test passes on the unmodified code, and its
    red is shown by mutating one expected byte. A second, new-model fixture is kept skipped until
    Chunk 04 un-skips it: the same fragments, the headline in `.prawduct/release-headline.md`, and
    no section.
  - **Then the module.** The declaration reader (CD1, CD2), the version-heading predicate,
    insertion-point selection (CD4), the renderers (heading, entry, layouts; CD6), and a
    byte-preserving insert (CD5). All pure functions with unit tests; nothing calls them yet.
- **Depends on:** Chunk 01
- **Artifacts consumed:** `documentation/issues/733-design.md`; `plugin/lib/core.py` (`read_yaml_block`)
- **Deliverables:** new `plugin/lib/consumer_digest.py`; new `tests/test_consumer_digest.py`; the golden pair in `tests/test_change_cut.py`
- **Tests:** unit —
  - each invalid-declaration reason is reported, and is not read as undeclared;
  - an unreadable state file reads as undeclared;
  - the version-heading predicate accepts `## v3.7.2`, `## [1.4.0] - 2026-10-25` and
    `## 1.4.0 (unreleased)`, and rejects `## [Unreleased]` and `## Contents`;
  - insertion lands below a marker, above the first version heading past an Unreleased section, or
    at the end of a file with none;
  - CRLF + BOM round-trips byte-equal outside the span;
  - each layout renders, including `by-type` order, multi-line bullets, and `{{`/`}}`.
- **Acceptance criteria:** the module tests pass. The golden passes on unmodified `change_cut.py`
  and fails on a one-byte mutation.
- **Critic mode:** final
  <!-- Override: this chunk fixes the signatures 03 and 04 are briefed against in parallel. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed

### Chunk 03: Phase 0 reads the declaration (delegate A)

- **Description:**
  - `_digest_advisories` becomes the CD12 checks: the headline file under `headline: required`, and
    an early `release-in-changelog` warning, both naming the declared path.
  - Delete `_coverage_advisory`, `_digest_mentions`, `_open_digest_section`, `_read_digest`'s
    section use and `_DIGEST_REL_PATH` (CD13). The digest stops using `_ships_the_plugin_tree`; the
    VERSION-fallback hint keeps it.
  - Prawduct declares its own digest in `.prawduct/project-state.yaml`.
- **Depends on:** Chunk 02
- **Artifacts consumed:** `documentation/issues/733-design.md` Phase 0 section; `tests/test_release_readiness.py`
- **Deliverables:** the declaration-driven Phase 0 checks, prawduct's declaration, tests
- **Tests:** integration via `check_releasability` —
  - a declared non-prawduct fixture warns on a missing headline file and names `CHANGELOG.md`;
  - an undeclared fixture prints nothing new;
  - an invalid declaration warns, with the exit code unchanged;
  - the advisory never flips a passing or failing verdict;
  - tests of the deleted coverage check are removed with it, as a requirement change (CD13), and
    nothing else is weakened.
- **Acceptance criteria:** tests pass, and `grep -n "_DIGEST_REL_PATH\|_coverage_advisory"
  plugin/lib/release_readiness.py` is empty.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed

### Chunk 04: The cut writes the release file and inserts it (delegate B)

- **Description:**
  - `plan_cut` adds `.prawduct/releases/<version>.md` and the changelog insert to the
    all-or-nothing write set (CD3). It consumes `.prawduct/release-headline.md`, removing it last
    alongside the fragments.
  - It refuses per CD7, implements CD8's re-run table, and prints CD9's exact preview on the dry
    run.
  - The undeclared and legacy lines follow CD10.
  - Delete `_digest_write`, `_names_release`, the `**`scope`**:` text search and
    `_DIGEST_REL_PATH`.
  - Un-skip the new-model golden fixture. It must equal Chunk 02's captured bytes (CD11).
- **Depends on:** Chunk 02
- **Artifacts consumed:** `documentation/issues/733-design.md` cut section; `plugin/lib/change_log_archive.py` (`archive_would_be_ignored`); `plugin/lib/core.py` (`write_all_or_none`)
- **Deliverables:** the release-file cut in `plugin/lib/change_cut.py`, tests
- **Tests:**
  - both golden fixtures produce identical bytes;
  - each CD7 code leaves nothing written and the fragments present;
  - a CRLF + BOM Keep a Changelog fixture with `## [Unreleased]` on top gets the section below
    Unreleased, byte-equal elsewhere;
  - re-run after a simulated removal failure removes the leftovers and writes nothing;
  - a new fragment after the cut refuses `release-already-cut`;
  - the dry-run text equals the release file's text;
  - the undeclared line names the key.
- **Acceptance criteria:** tests pass with the golden test unmodified, and `grep -n
  "_DIGEST_REL_PATH\|_names_release\|_digest_write" plugin/lib/change_cut.py` is empty.
- **Critic mode:** final
  <!-- Override: the writer is the keystone that publishes into a product's file. -->
- **Visual change:** yes — one look at the rendered Keep a Changelog result and the dry-run preview before merge
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed

### Chunk 05: Prawduct's own procedure moves onto the release file

- **Description:** CD14 and CD15:
  - remove the `## v3.8.0-dev` section from `plugin/CHANGELOG.md`, moving any real headline text
    to `.prawduct/release-headline.md`;
  - change `test_changelog_has_current_version_entry` to its CD15 contract. It is cited as a
    requirement change in the commit, not as a relaxation;
  - remove the changelog edit from the dev-track bump and reopen steps;
  - take the GitHub Release body from the release file.

  Sweep tests and procedures that read an open dev section, and enumerate them by query
  (`grep -rn "\-dev" ` over `tests/` and the runbook for changelog headings) before editing.
- **Depends on:** Chunks 03, 04
- **Artifacts consumed:** `tests/test_plugin_version_banner.py`; `documentation/release-process.md`; `.prawduct/runbooks/cut-and-publish-a-plugin-release.md`
- **Deliverables:** prawduct's changelog without an open section; the banner test's new contract; procedure text for bumps, reopen and the release body
- **Tests:** the banner test under CD15, with its red shown both ways (a dev section present on a
  dev version fails; a released version with no section fails); the full release-tooling test
  files.
- **Acceptance criteria:**
  - `python3 plugin/bin/prawduct-hook check-releasability --release v3.8.0` on this repo shows no
    digest warning except a missing headline file, if none has been written yet;
  - a throwaway-worktree `cut-change-log --release v3.8.0` dry run renders prawduct's section in
    today's format.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed

### Chunk 06: Every product-facing surface agrees

- **Description:** CDOC1 and CDOC2:
  - the `# CONSUMER DIGEST (opt-in)` block in `plugin/templates/project-state.yaml`;
  - the "Consumer note" sentence in `plugin/templates/change-fragment.md`;
  - `plugin/docs/project-state-keys.md`;
  - the `change_cut.py` and `release_readiness.py` module docstrings.

  Search for the claim ("plugin/CHANGELOG.md", "consumer digest", "release cut copies", "open
  section"), not for the tokens edited (core.md). Delete superseded sentences rather than adding
  beside them.
- **Depends on:** Chunk 05
- **Artifacts consumed:** the diff of Chunks 02–05
- **Deliverables:** templates, key registry and docstrings describing the release-file model
- **Type:** doc-only
- **Tests:** existing template and budget tests stay green; `test_path_reference_resolution`
- **Acceptance criteria:**
  - no product-facing sentence promises a copy into release notes without the declaration;
  - `grep -rn "plugin/CHANGELOG.md" plugin/lib plugin/templates` finds only prawduct's own
    declaration.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed

### Chunk 07: End-to-end on a scratch product, then the boundary review

- **Description:**
  - In a scratch repo outside this one (no `plugin/`), stage a product: a CRLF root `CHANGELOG.md`
    in Keep a Changelog form with an `## [Unreleased]` section, `consumer_digest:` with `by-type`,
    three fragments (one `none:`), a headline file and a release plan.
  - Run the repo-local `check-releasability`, then `cut-change-log` dry run, `--apply`, and
    `--apply` again. Diff the changelog and read the release file.
  - Repeat prawduct's dry run on a throwaway worktree.
  - Write the change fragment's narrative and consumer note.
  - Count the deletions the Architecture goal promised.
- **Depends on:** Chunk 06
- **Deliverables:** the verification record in this plan's Decisions; the completed `.prawduct/changes/consumer-digest.md`
- **Type:** cumulative-final
- **Tests:** full suite via `testament run`
- **Acceptance criteria:**
  - the second `--apply` writes nothing;
  - the bytes outside the inserted span compare equal (`cmp`), line endings included;
  - the release file equals the inserted text;
  - the suite is green and recorded.
- **Done when:**
  1. Acceptance criteria met and the suite passes
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved

## Verification Strategy

Drive the real command against real file shapes:
- Chunk 04 looks at a rendered Keep a Changelog result and the dry-run preview.
- Chunk 05 dry-runs prawduct's own cut on a throwaway worktree.
- Chunk 07 runs Phase 0 → dry run → apply → re-apply on a scratch CRLF product.

Every run uses `python3 plugin/bin/prawduct-hook` from this checkout, never the PATH binary, which
is the `-live` plugin (hook-surface.md). Byte claims are checked with `cmp` over the regions
outside the span, not by reading a diff.

## Governance Checkpoints

**Commit & PR cadence:** one commit per chunk after its review. The branch merges to `develop`
through `/prawduct:pr` when the owner asks, and must merge before the v3.8.0 cut (the release
plan's `ships` row enforces it).

- After Chunk 02 (`final`): confirm the module's signatures before delegates are briefed against
  them.
- After Chunk 04 (`final`): the writer is the keystone; confirm both golden fixtures and the CRLF
  byte-equality before prawduct's own procedure moves onto it.
- After Chunk 07 (cumulative): full-bundle review against this plan's Goals.
