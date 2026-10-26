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
partition: >-
  01 and 02 serial (coordinator; 02 fixes the shared module's signatures every later chunk calls).
  03 and 04 delegated after 02 commits, two isolated worktrees with disjoint files — A (03):
  plugin/lib/release_readiness.py, tests/test_release_readiness.py, .prawduct/project-state.yaml;
  B (04): plugin/lib/change_cut.py, tests/test_change_cut.py. The coordinator owns
  plugin/lib/consumer_digest.py, so a delegate needing a change there reports it rather than
  making it. 05–07 serial: 05 extends 04's writer, 06 describes what 03–05 built, and 07 integrates.
---

## Goals

**Response taken:** Proceed, citing #733 (which #1069 was folded into by the owner on 2026-10-25)
and `documentation/issues/733-requirements.md` as revised that day. The owner asked for the fold,
the requirements, and this plan "as a requirement for the 3.8.0 release", and pointed at changie
(changie.dev) for inspiration. **Building waits on one owner ruling** (requirements Decision 7:
whether the plugin may write a product's declared changelog under `architecture.md` § Direction).
Chunk 01 is doc-only, and Chunk 02 onward starts only once the ruling is recorded.

**Product:** Every governed product on change fragments writes a consumer note per scope, and
today only prawduct's own cut delivers that note anywhere. After this plan, a product declares its
changelog once in `consumer_digest:`. The cut then writes each shipping note into that file's open
section, refusing by name when it cannot. Phase 0 asks the same declared section its headline
question. The motivating product is a monorepo whose one root `CHANGELOG.md` is a merge-conflict
hotspot: it gets per-PR fragments composed into that file at release time.

**Architecture:**
- **One owner** for "which file, which section, what shape": a new module,
  `plugin/lib/consumer_digest.py` (created in Chunk 02). Both the Phase 0 reader and the cut call
  it, and neither carries its own path constant or locator (`architecture.md`: every fact has one
  home). Prawduct's `plugin/CHANGELOG.md` becomes one declared value.
- **Authority fails closed, advice fails soft.** The cut refuses on an invalid, missing or
  unlocatable declared changelog. Phase 0 warns and never changes an exit code.
- **Insert, never regenerate** (requirements Decision 3). The writer changes no byte outside the
  span it inserts.
- **Must stay possible:** a list form of `consumer_digest:` (one changelog per monorepo package,
  changie's `projects`), and per-version notes files once a consumer for them exists.

**Constraints:**
- Prawduct's own cut output stays byte-identical (CDW9). The golden test is captured in Chunk 02,
  before the writer changes, and must pass unmodified at Chunk 07.
- Ships in v3.8.0 (owner). `.prawduct/artifacts/release-plan-v3.8.0.md` carries the `ships` row
  that makes Phase 0 refuse until this merges.
- The build plan stays live after the merge to `develop` until v3.8.0 ships, because
  `check-releasability` pairs the pending scope with its plan (release.md).
- The plugin banner (`plugin/hooks/banner.py`) reads the bundled changelog and is out of scope.
  Prawduct's changelog format stays what it parses.

**Tradeoffs accepted:**
- *Phase 0 reader gets stricter for prawduct (DIG6).* When the top section names a different
  version, the reader now notes "no section for vX.Y.Z" instead of judging the stale section. This
  is a deliberate behavior change. Revisit if it fires on a normal release (it should not: the
  runbook opens the next section at reopen).
- *Inferred, owner can veto:* Decisions 1 (prawduct onto its own declaration, reversing the
  2026-09-03 draft) and 2 (`release-heading` replaces `open-heading-pattern`) were taken by the
  builder, with the reasons recorded in the requirements.
- *Inferred:* the `by-type` default map (`feature`→Added, `fix`→Fixed, everything else→Changed)
  follows Keep a Changelog's vocabulary as changie's defaults do. Products override it with
  `types:`.
- *Scope not taken* (requirements Scope-out): regenerating from per-version files, several
  changelogs per repo, creating a missing section, version-file bumps, and external release-tool
  integration beyond the documented order.

**Decisions made mid-build:** (appended while building)

**Level:** Medium. The requirements are concrete, and every code site is read. Two things would
raise it. (1) The owner's ruling on Decision 7, plus a veto check on Decisions 1 and 2. (2) Chunk
01's design pass confirming the `by-type` insertion rule against two real-world Keep a Changelog
files (subsection order, an existing `### Added`). That is the one place layout behavior is still
described rather than specified.

### Norm reconciliation (`governed_by`)

- `architecture.md` "the plugin writes nothing into a governed repo except its own `.prawduct/`
  state, the shared evidence store, and the files it must reconcile" — **ruling needed**
  (requirements Decision 7). The clause stays as ratified, and no code writes a product changelog
  until the owner rules. Chunk 06 records the ruling beneath the clause if one is given, in the
  form the 2026-07-30 and 2026-10-25 decisions use there.
- `architecture.md` "Prawduct guides and reviews; it never implements" — **conforms**. The cut
  writes release notes the product's own authors wrote, at an operator's command. It writes no
  code, config or tooling.
- `architecture.md` "authority fails closed; advice fails soft" — **conforms** (CDW2 refusals;
  DIG5 advisories never touch the exit code).
- `architecture.md` "every fact has one home" — **conforms**. `consumer_digest.py` is the home.
  `_DIGEST_REL_PATH`, `_names_release` and the writer's text-marker check are deleted, not
  wrapped. Chunk 07 counts the deletions.
- `architecture.md` "Local-first", "Python but never Python-specific" — **conforms**. Stdlib only,
  and a changelog is markdown in any language's repo.
- `api-contract.md` "exit codes are the contract", "additive-first" — **conforms**. The cut's exit
  codes keep their meaning (0 / 1 refused / 2 usage). The new refusal codes are added. No flag or
  `--json` key is repurposed, and the cut has no `--json`.
- `api-contract.md` versioning — **conforms**. A new opt-in project-state key under the plugin's
  semver, as a minor.
- `data-model.md` norms (fact ledger, append-only facts, derived views, two stores) —
  **inapplicable because** this plan writes no fact and no view. The archive is the change
  record, read here only as the idempotency witness.

## Build Chunks

### Chunk 01: Design revision — `733-design.md` covers both halves

- **Description:** Rewrite `documentation/issues/733-design.md` against the revised requirements,
  so code is written from a design rather than from the requirements' Decisions. It specifies:
  - the `consumer_digest.py` API (declaration type and reader, the two locators, `names_release`,
    the renderer per layout, the byte-preserving insertion function);
  - which current functions move there and which are deleted;
  - the `by-type` insertion rule, checked against two real Keep a Changelog files;
  - the CRLF/BOM handling;
  - the archive-witness query (which `change_log_archive` reader answers "this scope has an entry
    tagged `release=<v>`").

  Superseded sections (`open-heading-pattern`, Decision 3's regex compile, the hard-coded
  prawduct branch) are deleted rather than kept beside the new text.
- **Depends on:** none
- **Artifacts consumed:** `documentation/issues/733-requirements.md` (all), `plugin/lib/release_readiness.py`, `plugin/lib/change_cut.py`, `plugin/lib/change_fragments.py`, `plugin/lib/change_log_archive.py`
- **Deliverables:** the design doc, section per module, with a requirement-to-section trace table
- **Type:** doc-only
- **Tests:** none (doc-only). The design's test plan names each test by requirement id.
- **Acceptance criteria:** every DIG/CDW/CDOC requirement maps to a design section. No paragraph
  describes `open-heading-pattern` or a hard-coded prawduct path as current. The `by-type` rule is
  stated as an algorithm with a worked example.
- **Done when:**
  1. Acceptance criteria met
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed

### Chunk 02: `consumer_digest.py` — declaration, locators, and the golden baseline

- **Description:** First, capture CDW9's golden. A test runs today's `cut-change-log --apply` on a
  prawduct-shaped fixture (two fragments, one `none:`, a `## v9.9.9-dev.1` section with a
  headline) and pins the resulting `plugin/CHANGELOG.md` bytes. It passes on the unmodified code
  and is committed in this chunk. Then create the module with the declaration reader (DIG1, DIG2),
  `sentinel-heading` and `release-heading` locators (DIG3, DIG4, DIG7), and `names_release`. Unit
  tests only; nothing calls it yet.
- **Depends on:** Chunk 01; **the Decision 7 ruling** (recorded before this chunk starts)
- **Artifacts consumed:** `documentation/issues/733-design.md` (Chunk 01), `plugin/lib/core.py` (`read_yaml_block`)
- **Deliverables:** new `plugin/lib/consumer_digest.py`; new `tests/test_consumer_digest.py`; the golden test in `tests/test_change_cut.py`
- **Tests:** unit — each invalid-declaration reason (missing field, unknown enum, conflicting
  field, unknown `entry` placeholder) is reported, not treated as undeclared. An unreadable state
  file reads as undeclared. `release-heading` matches `v3.8.0-dev.4`, `v3.8.0`, `[3.8.0] -
  2026-10-25` and `3.8.0 (unreleased)`, and rejects `v3.7.2` and `v3.8.0.1`. The sentinel match is
  case-insensitive and exact. Golden — passes against today's code (record its red by mutating one
  byte of the fixture's expected output).
- **Acceptance criteria:** the module's tests pass. The golden test passes on unmodified
  `change_cut.py`, and it is shown to fail on a one-byte change.
- **Critic mode:** final
  <!-- Override: this chunk fixes the signatures 03 and 04 are briefed against in parallel. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed

### Chunk 03: Phase 0 reads the declared section (delegate A)

- **Description:** `_digest_advisories` takes its file and section from `consumer_digest`, passing
  the `--release` value for `release-heading`. The headline advisory runs only under `headline:
  required`. Every message names the declared path (DIG5). Delete `_DIGEST_REL_PATH` and the
  digest's use of `_ships_the_plugin_tree`; the VERSION-fallback hint keeps the predicate.
  Prawduct declares its own digest in `.prawduct/project-state.yaml` (`path: plugin/CHANGELOG.md`,
  `keying: release-heading`, `headline: required`, `layout: paragraphs`).
- **Depends on:** Chunk 02
- **Artifacts consumed:** `documentation/issues/733-design.md` reader section; `tests/test_release_readiness.py` (`TestDigestCoverageIsAdvisory` style, `_make_project`)
- **Deliverables:** the rewired reader in `plugin/lib/release_readiness.py`, prawduct's declaration, and the tests
- **Tests:** integration via `check_releasability` — a declared non-prawduct fixture under each
  keying gets the headline warning naming `CHANGELOG.md`, not `plugin/CHANGELOG.md`. An undeclared
  fixture is silent (DIG8). An invalid declaration warns with the exit code unchanged. Prawduct's
  normal state is unchanged. The new DIG6 case notes "no section for vX.Y.Z". The advisory never
  flips a passing or failing verdict. Existing fixtures that relied on `plugin/VERSION` implying a
  digest now declare one. That is a fixture setup change, and no assertion is weakened.
- **Acceptance criteria:** tests pass, `grep -rn _DIGEST_REL_PATH plugin/lib/release_readiness.py`
  is empty, and `python3 plugin/bin/prawduct-hook check-releasability --release v3.8.0` on this
  repo prints the same digest lines it printed before the chunk.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed

### Chunk 04: The cut writes the declared section — paragraphs layout, refusals, byte-preserving insert (delegate B)

- **Description:** `_digest_write` is replaced by a call into `consumer_digest`: read the
  declaration, locate the section, refuse per CDW2/CDW10, and render the `paragraphs` layout. The
  rendered text is inserted with the line-ending style, BOM and trailing newline preserved (CDW3).
  Idempotency moves to the archive witness (CDW6). The undeclared line names `consumer_digest:`
  (CDW8). Delete `_names_release`, the `**`scope`**:` text search and `_DIGEST_REL_PATH` from
  `change_cut.py`.
- **Depends on:** Chunk 02
- **Artifacts consumed:** `documentation/issues/733-design.md` writer section; `plugin/lib/change_log_archive.py` (the witness reader); `plugin/lib/core.py` (`write_all_or_none`)
- **Deliverables:** the declaration-driven writer in `plugin/lib/change_cut.py` and its tests
- **Tests:** the CDW9 golden passes, unmodified, through the declaration path (this fixture
  declares prawduct's values). Each CDW2 code, with nothing written and the fragments still present.
  A CRLF + BOM fixture is byte-equal outside the inserted span (CDW3). A re-run after a simulated
  removal failure adds nothing, and a note reworded in the changelog after the cut is still not
  re-added (CDW6). The undeclared line names the key.
- **Acceptance criteria:** tests pass, the golden test is unmodified, and `grep -n
  "_DIGEST_REL_PATH\|_names_release" plugin/lib/change_cut.py` is empty.
- **Critic mode:** final
  <!-- Override: the writer is the keystone that publishes into a product's file. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed

### Chunk 05: `bullets` and `by-type` layouts, entry templates, and the dry-run preview

- **Description:** Add the two bullet layouts and the `entry` template (CDW4, CDW5), with
  multi-line notes continuing indented under their bullet, and `by-type` subsections created or
  reused per the design's algorithm. The dry run prints the exact inserted text with its file and
  heading (CDW7), so a release PR can show the notes before tagging.
- **Depends on:** Chunk 04
- **Artifacts consumed:** `documentation/issues/733-design.md` layout section and its worked example
- **Deliverables:** layout rendering and preview output, with tests
- **Tests:** a Keep a Changelog fixture (`## [Unreleased]` holding an existing `### Fixed`) gains
  `### Added` in map order and has bullets prepended to `### Fixed`. A `bullets` fixture gets one
  list at the top of the section. A custom `entry` renders each placeholder, and a doubled brace
  renders as a literal. A multi-line note stays one list item. The dry-run output equals the bytes
  `--apply` inserts. `paragraphs` and the golden test are untouched.
- **Acceptance criteria:** tests pass. Running the dry run on the KaC fixture shows text a reviewer
  can paste as release notes.
- **Visual change:** yes — the rendered changelog and the preview are read by people; one look at a real KaC file before merge
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed

### Chunk 06: Every surface describing the cut agrees

- **Description:** CDOC1–CDOC3 and the prose the mechanism change falsifies:
  - the `# CONSUMER DIGEST (opt-in)` block in `plugin/templates/project-state.yaml`, with one
    example per keying, the layouts, and the external-tool order;
  - `plugin/templates/change-fragment.md`'s "Consumer note" sentence;
  - `plugin/docs/project-state-keys.md`;
  - `documentation/release-process.md` and `.prawduct/runbooks/cut-and-publish-a-plugin-release.md`,
    describing prawduct's procedure as one declared value;
  - the `change_cut.py` module docstring.

  Search for the claim ("plugin/CHANGELOG.md", "consumer digest", "release cut copies"), not for
  the tokens edited (core.md). If the owner ruled on Decision 7, record the ruling beneath the
  `architecture.md` clause and leave the clause's wording alone.
- **Depends on:** Chunks 03, 04, 05
- **Artifacts consumed:** the diff of Chunks 03–05
- **Deliverables:** updated templates, key registry, release process, runbook and docstrings
- **Type:** doc-only
- **Tests:** existing template and budget tests stay green. `test_path_reference_resolution` passes.
- **Acceptance criteria:** `grep -rn "plugin/CHANGELOG.md" plugin/lib plugin/templates` names only
  prawduct's own declaration in examples. No sentence promises a copy into release notes without
  the declaration.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed

### Chunk 07: End-to-end on a scratch product, then the boundary review

- **Description:** In a scratch repo outside this one (no `plugin/`), stage a product setup: a
  CRLF root `CHANGELOG.md` in Keep a Changelog form, `consumer_digest:` with `sentinel-heading` /
  `by-type`, three fragments (one `none:`) and a release plan. Run the repo-local `prawduct-hook
  check-releasability`, `cut-change-log` (dry run, then `--apply`, then `--apply` again), and diff
  the file. Repeat on this repo's own tree in a throwaway worktree for the prawduct declaration
  and compare with the golden. Write the change fragment's narrative and consumer note. Count the
  deletions the Architecture goal promised.
- **Depends on:** Chunk 06
- **Deliverables:** the verification record in this plan's Decisions; the completed `.prawduct/changes/consumer-digest.md`
- **Type:** cumulative-final
- **Tests:** full suite via `testament run`
- **Acceptance criteria:** the second `--apply` writes nothing. The diff outside the inserted span
  is empty, including line endings. Prawduct's throwaway cut matches the golden. The suite is
  green and recorded.
- **Done when:**
  1. Acceptance criteria met and the suite passes
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved

## Verification Strategy

Beyond the tests, drive the real command against real file shapes. Chunk 05 looks at a real Keep a
Changelog file's rendered result. Chunk 07 runs the whole Phase 0 → dry run → apply → re-apply
sequence on a scratch product with CRLF line endings, and on a throwaway copy of this repo. Every
run uses `python3 plugin/bin/prawduct-hook` from this checkout, never the PATH binary, which is the
`-live` plugin (hook-surface.md). The writer's byte claim is checked with `cmp` on the regions
outside the span, not by reading a diff.

## Governance Checkpoints

**Commit & PR cadence:** one commit per chunk after its review. The branch merges to `develop` by
`/prawduct:pr` when the owner asks, and must merge before the v3.8.0 cut (the release plan's
`ships` row enforces that).

- Before Chunk 02: the owner's Decision 7 ruling is recorded, and Decisions 1 and 2 have not been
  vetoed.
- After Chunk 02 (`final`): confirm the module's signatures before delegates are briefed against
  them.
- After Chunk 04 (`final`): the writer is the keystone. Confirm the golden test and the CRLF
  byte-equality hold before layouts widen it.
- After Chunk 07 (cumulative): full-bundle review against this plan's Goals.
