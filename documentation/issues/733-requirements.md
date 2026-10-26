# Issue #733 — Release Notes: One Declared Changelog, Read at Phase 0 and Written at the Cut: Requirements

`status: revised · stage: requirements · area: release-tooling · added: 2026-09-03 · revised:
2026-10-25 (folds #1069; ships in v3.8.0) · issue: https://github.com/brookstalley/prawduct/issues/733`

Related: #1069 (folded into this item 2026-10-25, owner's call: the cut's write path), #576 /
`release_version_files:` (the declaration-shape precedent), #259 and #702 (prawduct-side digest
checks, out of scope), PR #734 (shipped the two prawduct-only Phase 0 checks this item
generalizes). Prior art studied: changie (changie.dev, v1.26.0, source read 2026-10-25).

**Revision note.** The 2026-09-03 draft covered only the Phase 0 reader and kept prawduct's own
path hard-coded beside a new declared one. #1069 showed the larger gap: the cut is the half that
delivers notes, and it was prawduct-only too. This revision makes one declaration serve both the
reader and the writer, moves prawduct onto it, and replaces the `open-heading-pattern` strategy
with `release-heading` (Decision 2). DIG1, DIG3, DIG5 and DIG8 keep their ids and meaning; DIG2,
DIG4, DIG6 and DIG7 are restated; the CDW requirements are new.

## Problem

Every product on change fragments must write a `## Consumer note` per scope. The PR probe refuses
a fragment without one, and the PR reviewer flags a `none:` on work a user would notice. The
template promises the payoff: "Where the repo publishes release notes, the release cut copies
this text into them" (`plugin/templates/change-fragment.md`). That holds only in prawduct's own
repo. Everywhere else, the note is written, reviewed and then filed in
`.prawduct/change-log-archive/` where no consumer reads it. The product's changelog never
receives it. The channel is produced and never consumed.

Three hard-coded facts make this prawduct-only:

1. **Which file.** `release_readiness._DIGEST_REL_PATH = "plugin/CHANGELOG.md"`, used by the
   Phase 0 reader and by the cut's writer (`change_cut._digest_write`).
2. **Which section.** The reader takes the topmost `## ` heading unconditionally. The writer takes
   the topmost and also requires it to name the release (`_names_release`: `vX.Y.Z` or
   `vX.Y.Z-dev…`), refusing `wrong-section` otherwise. Both are prawduct's editorial procedure,
   not a property of changelogs.
3. **What goes in it.** The writer refuses a section with no headline (`no-headline`) and renders
   every note as a `**`scope`**: text` paragraph. A Keep a Changelog file wants `- text` bullets
   under `### Added` / `### Fixed`.

A fourth fact makes the gap hard to see. Two different predicates answer "does this repo have a
digest": `_ships_the_plugin_tree` (is `plugin/VERSION` present) for the reader, and
`plugin/CHANGELOG.md` being a file for the writer. Neither reads anything a product declares.

**The motivating case** (#1069): a high-throughput monorepo product with one root `CHANGELOG.md`.
About 1,000 of its commits in 30 days touched that file, which makes it a merge-conflict hotspot.
It wants per-PR fragments composed into that durable file at release, which is what the fragment
model was built to give it.

## Grounding facts

Re-verified against `develop` at `0964afa1` (v3.8.0-dev, 2026-10-25):

- **The cut is silent about the gap, but not entirely mute.** On a repo without
  `plugin/CHANGELOG.md`, `cut-change-log` prints `consumer notes: this repo publishes no consumer
  digest; the notes stay in the archive entries` and exits 0 (`change_cut.cut_cmd`). #1069's "no
  warning" is accurate in effect: the line names no way to change it, and the template says the
  opposite.
- **The writer normalizes line endings.** `_digest_write` reads with `read_text`, splits with
  `splitlines()` and joins with `"\n"`. On a CRLF changelog every line would change, which hides
  the real edit in a whole-file rewrite (hook-surface.md, "Preserve line endings"). This is
  harmless on prawduct's LF file and a defect for any CRLF product.
- **Idempotency today is a text search.** The writer skips a fragment when the section already
  contains `**`<scope>`**:`. That marker exists only in the paragraphs rendering. A bullets
  rendering has no such marker, so the text search cannot carry idempotency beyond prawduct's
  format.
- **The archive is a format-independent witness.** The cut writes the archive month file and the
  digest in one all-or-nothing write (`core.write_all_or_none`), then removes fragments. So after
  any successful write, the archive holds an entry for each scope tagged `release=<version>`, and
  the digest holds its note. A re-run after a removal failure can read "this scope already has an
  archive entry for this release" and skip its note. That answer holds whatever the rendered note
  looks like.
- **Phase 0 coverage is already legacy-only.** `check_releasability` passes `legacy_pending` to
  `_digest_advisories`: a fragment's note is required and written by the cut, so matching its
  scope name against prose would be a fuzzy check of an exact fact. For a product on fragments
  the coverage advisory has nothing to ask. The headline advisory is the reader check that
  matters to them.
- **The reader runs before the version resolves, but the release is known.**
  `_digest_advisories` is called before `_resolve_version`, deliberately, so the advice arrives
  while the notes can still be written. The `--release` argument is already parsed at that point.
- **The plugin banner is a different reader of a different file.** `plugin/hooks/banner.py` parses
  the *bundled* `CHANGELOG.md` at the installed plugin's root, to show upgrading repos prawduct's
  own headlines. It never reads a product's changelog, and nothing here changes it. Prawduct's
  `plugin/CHANGELOG.md` format stays what the banner parses.
- **changie's model** (source: `cmd/merge.go`, v1.26.0). `changie batch <version>` renders the
  unreleased fragments into a per-version file (`.changes/v1.2.3.md`) that can be edited, then
  deletes the fragments. `changie merge` then **regenerates** the whole changelog: `os.Create`
  truncates it, then writes the header file, then every version file newest first. It also has
  kinds (each with its own section header and format), per-entry `changeFormat` templates, a
  `--dry-run` that prints the output, `--include-unreleased` to preview pending fragments, and
  `projects` for one changelog per monorepo package.

## Decisions

**1. One declaration, one owner, both halves.** `consumer_digest:` in `project-state.yaml` answers
"which file, which section, what shape" for the Phase 0 reader and for the cut's writer, and one
reader function parses it. Prawduct declares its own `plugin/CHANGELOG.md` through it.
`_DIGEST_REL_PATH` and the digest's use of `_ships_the_plugin_tree` are deleted, leaving one
predicate. *Reverses the 2026-09-03 Decision 2* (keep prawduct's path hard-coded beside the new
one). That draft kept two parallel paths to protect prawduct's release from the change, and two
paths answering one question is the shape #1069 found. Prawduct's protection is now a pinned
byte-for-byte test of its cut output instead (CDW9). `[DECISION: prawduct moves onto its own
declaration | one owner for "which file, which section" (#1069 acceptance); risk carried by a
golden test, not by a second code path | owner can veto]`

**2. Two keying strategies: `sentinel-heading` and `release-heading`.** Plain
"topmost heading" is still not offered, for the false all-clear reason the 2026-09-03 draft gave.
`release-heading` replaces `open-heading-pattern`:

- **`sentinel-heading`**: a fixed heading text that is never renamed, such as Keep a Changelog's
  `## [Unreleased]` or `## Unreleased`. The open section is the first heading matching it. It
  needs no version to locate, and it is the strategy that works alongside an external tool that
  dates or renames the section after the cut (Decision 6).
- **`release-heading`**: the open section is the topmost `## ` heading that names the release
  being prepared. It names the release when the heading's first version-shaped token equals the
  release, with an optional `v` prefix and optional `[ ]` brackets, and with or without a `-dev…` /
  pre-release suffix. That covers prawduct (`## v3.8.0-dev.4`, renamed `## v3.8.0`), Keep a
  Changelog with the version written in advance (`## [1.4.0] - 2026-10-25`), and
  `## 1.4.0 (unreleased)`. It locks out stale sections by construction: last release's section
  names a different version.

*Why not `open-heading-pattern`.* It asked the operator for a regex that "only an unshipped heading
satisfies", and put that regex's correctness outside the checks. Prawduct's own writer has never
keyed on its `-dev` suffix. It keys on the version name, because the runbook renames the section
before the cut. A pattern strategy would therefore not reproduce prawduct's own behavior. It also
cannot say whether a match is *this* release's section, which is what the writer must know before
adding notes to it. `release-heading` makes that check structural and needs no regex, so Decision
3 of the design (an uncompilable pattern) disappears with it. `[DECISION: replace
open-heading-pattern with release-heading | a writer must know the section is this release's, and
the version is the self-verifying signal prawduct already uses | owner can veto]`

**3. Insert, don't regenerate (changie's split, not its merge).** The cut writes rendered notes
into the declared section of the existing file and changes no byte outside the inserted span. It
does not rebuild the file from per-version sources the way `changie merge` does. A product
arriving with a monolithic changelog (the motivating case) has no per-version source files for
its history. Regenerating would force a migration, and every hand edit outside the generator's
sources would be lost at the next cut. What we take from changie instead:

- rendering is a pure function of (shipping fragments, declaration), so a dry run can print the
  exact bytes;
- a per-entry format template (changie's `changeFormat`);
- kinds rendered as subsections (changie's kinds and `kindFormat`): our fragment `type`, mapped to
  headings;
- a preview of what the pending fragments would render (changie's `--include-unreleased` /
  `batch --dry-run`).

Per-version release-notes files are left for later (Scope-out), because no consumer for them
exists yet (core.md: name the consumer when adding the producer).

**4. The archive is the idempotency witness.** A shipping scope gets no note if the archive
already holds its entry tagged `release=<version>` from an earlier run of this cut. The text
search for `**`scope`**:` retires. One owner, independent of rendering, and it survives an
operator rewording the note in the changelog after the cut.

**5. A declared changelog is a contract; an undeclared one is unchanged and says so usefully.**
A declared path that is missing, holds no locatable section, or has an invalid declaration makes
the cut **refuse** with a named code. It is never a silent skip. The reader still **advises**,
because Phase 0 checks never touch the exit code (2026-09-03 draft, DIG1). With no declaration,
the cut writes nothing to any changelog, as today. Its output line names the `consumer_digest:`
key, and the template stops promising unconditionally.

**6. Coexist with an external release tool by documented order, not by integration.** Where a
product uses another tool to date the section or bump versions (release-please, changie,
semantic-release, a script), the order is: the cut writes the notes into the declared section,
then the external tool renames or dates it. Under `sentinel-heading` the cut never needs a rename
it does not own. Prawduct does not invoke or detect the other tool.

**7. Writing a product's changelog needs an owner ruling on a binding norm (pending).**
`architecture.md` § Direction: "The plugin writes nothing into a governed repo except its own
`.prawduct/` state, the shared evidence store, and the files it must reconcile — `.gitignore`,
`.claude/settings*.json`, and `CLAUDE.md`'s governance anchor — never framework files." A
product's declared changelog is in none of those classes, so CDW1 is a new write. The case for
allowing it uses the norm's own reasoning: the carve-out turns on "the *product's own* file, which
the plugin edits at a declared seam rather than authors wholesale". A declared changelog is the
product's own file. The seam is the section the product declared. Nothing is written until the
product opts in with `consumer_digest:` and an operator runs `cut-change-log --apply`. In
prawduct's own repo the file is the framework's own, so there is nothing to rule on there. The
builder cannot supply this authority (core.md), so the clause stays as ratified and the build
does not start until the owner rules. `[DECISION: pending owner ruling | read a declared
consumer_digest: path as a product-owned file edited at a declared seam, written only by an
operator-run cut | owner rules]`

## Requirements

MUST unless marked SHOULD.

### Declaration

- **DIG1** `project-state.yaml` supports a `consumer_digest:` mapping with these fields:
  - `path` (repo-relative, required);
  - `keying` (`sentinel-heading` | `release-heading`, required);
  - `heading` (required with `sentinel-heading`, refused with `release-heading`);
  - `headline` (`required` | `none`, default `none`);
  - `layout` (`paragraphs` | `bullets` | `by-type`, default `bullets`);
  - `entry` (an entry template, optional, CDW4);
  - `types` (optional, `by-type` only, CDW5).

  A missing required field, an unknown `keying` / `layout` / `headline` value, a field that
  conflicts with the declared strategy or layout, or an `entry` naming an unknown placeholder makes
  the declaration **invalid**. Invalid is reported, never treated as undeclared.
- **DIG2** One function reads the declaration, and both the Phase 0 reader and the cut call it.
  Both read the working tree's `.prawduct/project-state.yaml`: the cut runs on the candidate tree,
  and Phase 0 runs before any tag exists (`733-design.md` Decision 1). An unreadable or absent
  state file reads as undeclared.
- **DIG8** A repo with no `consumer_digest:` sees no new Phase 0 output, and its cut writes no
  changelog (CDW8 for what the cut prints).

### Locating the open section

- **DIG3** `sentinel-heading` finds the first `## ` heading whose text, with the marker and
  surrounding whitespace stripped, equals `heading` case-insensitively. The section runs to the
  next `## ` heading or end of file.
- **DIG4** `release-heading` finds the topmost `## ` heading whose first version-shaped token names
  the release being prepared, as Decision 2 defines it. The token is compared after stripping one
  leading `v` and enclosing `[ ]`. A `-dev…` or other pre-release suffix still names its base
  release. The reader takes the release from `--release`, or from the version fallback where one
  exists. With no release known, it notes that the digest was not checked and why, and does not
  guess.
- **DIG7** No declaration can make either half read or write a section other than the one it
  names. Each strategy's match is self-verifying (a sentinel is a reserved literal; a release
  heading names this release), and an invalid declaration stops the reader's checks with a
  warning and the writer with a refusal.

### Phase 0 reader

- **DIG5** The headline and coverage advisories run, unforked, on the section the declaration
  locates, with every message naming the declared path. The headline advisory runs only when
  `headline: required`. Coverage stays legacy-scopes-only, as today.
- **DIG6** Prawduct's own Phase 0 output is unchanged for its normal state (top section names the
  release being prepared). One deliberate change: when the top section names a *different*
  version, the reader now notes "no section for vX.Y.Z" instead of judging the stale section.

### The cut's write

- **CDW1** For a declared changelog, the cut writes every shipping fragment's consumer text
  (fragments whose note is `none:` contribute nothing, as today) into the located section, in one
  all-or-nothing write with the archive. The cut's result names the file, the section heading and
  the scopes written.
- **CDW2** The cut refuses before writing anything, with a named code:
  - `digest-declaration-invalid`: the reason from DIG1;
  - `digest-missing`: the declared path is not a file;
  - `digest-no-section`: no section matches the keying, and the detail says what to add;
  - `digest-no-headline`: `headline: required` and the section has no first line.
- **CDW3** Bytes outside the inserted span are unchanged: the line-ending style (LF or CRLF), a
  UTF-8 BOM, the trailing-newline state, and every line before and after. Pinned with a CRLF
  fixture and a byte-equality check outside the span.
- **CDW4** Each note is rendered by an entry template with the placeholders `{note}`, `{scope}`,
  `{type}` and `{title}`. A literal brace is written doubled. Each layout has a default:
  `paragraphs` → `**`{scope}`**: {note}`, the bullet layouts → `- {note}`. A multi-line note
  under a bullet layout continues indented beneath its bullet, so the list stays one item per
  note.
- **CDW5** Placement by layout:
  - `paragraphs`: after the headline paragraph when `headline: required`, otherwise at the top of
    the section.
  - `bullets`: one list at the top of the section, above existing content.
  - `by-type`: under `### <heading>` subsections, one per fragment type, using the `types` map
    (default: `feature`→`Added`, `fix`→`Fixed`, all other types→`Changed`). An existing
    subsection with the mapped heading receives the bullets at its top. A missing one is created
    in the order the map lists them, placed before the section's other `###` subsections.

  Within a layout, entries are ordered newest first, ties broken by scope (today's
  `render_consumer_section` order).
- **CDW6** Idempotency is witnessed by the archive (Decision 4). A scope whose archive entry for
  this release already exists before this run gets no note, and a re-run after any failure adds
  nothing twice. The `**`scope`**:` text search is removed.
- **CDW7** The dry run (no `--apply`) prints the exact text it would insert, with the file and the
  heading it goes under. A release PR can paste that output as the notes preview. No fragment is
  touched and nothing is written.
- **CDW8** With no declaration, the cut's output says the notes stay in the archive, and names
  `consumer_digest:` in `.prawduct/project-state.yaml` as the way to have them written to a
  changelog. `plugin/templates/change-fragment.md` says the copy happens where the repo declares
  `consumer_digest:`.
- **CDW9** Prawduct's own cut, run on its declaration (`path: plugin/CHANGELOG.md`, `keying:
  release-heading`, `headline: required`, `layout: paragraphs`), produces output byte-identical to
  today's for the same fragments and file. Pinned by a golden test captured before the change.
- **CDW10** The two refusals today's writer encodes for prawduct carry over under the
  declaration. `wrong-section` becomes a case of `digest-no-section` (no heading names the
  release). `no-headline` becomes `digest-no-headline`, which fires only when the declaration
  asks for a headline.

### Documentation

- **CDOC1** `plugin/templates/project-state.yaml` carries a commented `# CONSUMER DIGEST (opt-in)`
  block after `# RELEASE VERSION FILES`, with one example per strategy, the layouts, and the
  external-tool order (Decision 6). It does not show an invalid combination.
- **CDOC2** `documentation/release-process.md` and the cut-and-publish runbook describe the cut in
  terms of the declaration rather than `plugin/CHANGELOG.md`, and prawduct's own procedure as one
  declared value.
- **CDOC3** `plugin/docs/project-state-keys.md` (the key registry) lists `consumer_digest:`.

## Acceptance

- [ ] One declaration and one reader serve both halves; prawduct declares its own (Decision 1,
      DIG1, DIG2). Shared with #1069's first acceptance bullet.
- [ ] A declared, present changelog receives every shipping fragment's consumer note at the cut
      (CDW1, CDW4, CDW5).
- [ ] A declared path that is missing, unlocatable or invalid refuses with a named reason (CDW2).
- [ ] Re-running the cut adds nothing twice, and bytes outside the written span are unchanged
      (CDW3, CDW6).
- [ ] The documented order with an external release tool works without the cut renaming a heading
      (Decision 6, DIG3, CDOC1).
- [ ] Undeclared products are unchanged except for a more useful line, and prawduct's own cut
      output is byte-identical (DIG8, CDW8, CDW9).
- [ ] No declaration shape can yield a false all-clear or a write into the wrong section (DIG7).
- [ ] Ships in v3.8.0: listed as a release requirement in `.prawduct/artifacts/release-plan-v3.8.0.md`.

## Scope-out (this item)

- **Regenerating the changelog from per-version files** (changie `merge`). Decision 3. Revisit
  when a product asks for a fully derived changelog, or a consumer appears for per-version notes
  files. The most likely one is the GitHub Release body, which prawduct extracts today with `awk`
  from `plugin/CHANGELOG.md` (release-process.md).
- **More than one changelog per repo** (changie `projects`). A product has one `consumer_digest:`.
  Revisit when a monorepo asks for per-package changelogs. The mapping shape leaves room for a
  list form later.
- **Creating a missing section.** The cut refuses `digest-no-section` with the heading to add. It
  does not invent one (changie's `versionFormat`). Revisit if operators report the refusal as
  friction.
- **Version-file bumping** (`release_version_files:`, #576 owns it) and **any integration with an
  external release tool** beyond the documented order.
- **Prawduct-side digest checks** (#702, #259), and the coverage advisory's fuzzy-match
  false-positive rate (inherited, tracked separately).

## Evidence / references

- `plugin/lib/release_readiness.py`: `_DIGEST_REL_PATH`, `_ships_the_plugin_tree`, `_read_digest`,
  `_open_digest_section`, `_headline_advisory`, `_coverage_advisory`, `_digest_advisories`, and
  `check_releasability`'s digest call site (passes `legacy_pending`, before `_resolve_version`).
- `plugin/lib/change_cut.py`: `_names_release`, `_digest_write` (refusals, text-marker
  idempotency, `"\n".join` rewrite), `plan_cut`, `cut_cmd`'s undeclared line.
- `plugin/lib/change_fragments.py`: `TYPES`, `consumer_text`, `render_consumer_section`.
- `plugin/templates/change-fragment.md`, "Consumer note".
- `plugin/hooks/banner.py`: the bundled-changelog reader, unaffected.
- changie v1.26.0 `cmd/merge.go` (`mergeProject`: `os.Create`, header, version files, optional
  unreleased); changie.dev `/config/` (kinds, `changeFormat`, `kindFormat`, `projects`,
  `replacements`); `/cli/changie_batch/`, `/cli/changie_merge/`.
- #1069 body (motivating case, proposed changes 1–5, acceptance), folded here 2026-10-25.
