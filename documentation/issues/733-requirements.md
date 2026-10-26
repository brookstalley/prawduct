# Issue #733 — Release Notes: Each Release Is a File the Cut Writes, Inserted Into a Declared Changelog: Requirements

`status: revised · stage: requirements · area: release-tooling · added: 2026-09-03 · revised:
2026-10-25 (folds #1069; owner chose the release-file model; ships in v3.8.0) · issue:
https://github.com/brookstalley/prawduct/issues/733`

Related: #1069 (folded in 2026-10-25 by owner decision; the cut's write path), #576 /
`release_version_files:` (the declaration-shape precedent), #259 and #702 (prawduct-side digest
checks, out of scope), PR #734 (shipped the two prawduct-only Phase 0 checks this item replaces).
Prior art: changie (changie.dev, v1.26.0, source read 2026-10-25).

**Revision note.** The 2026-09-03 draft asked how to *find* the open section of a changelog, and
proposed two keying strategies. The owner chose the model changie uses instead, on 2026-10-25,
from three options (find by heading / full regeneration / release file plus insertion). In that
model there is no open section to find. A release becomes a file the cut creates, and the cut
inserts that file's text into the changelog as a new section. Requirement ids from earlier drafts
are retired, not renumbered. This document replaces them.

## Problem

Every product on change fragments must write a `## Consumer note` per scope. The PR probe refuses
a fragment without one, and the PR reviewer flags a `none:` on work a user would notice.
`plugin/templates/change-fragment.md` promises the payoff: "Where the repo publishes release
notes, the release cut copies this text into them."

That holds only in prawduct's own repo. Everywhere else the note is written, reviewed, and then
filed in `.prawduct/change-log-archive/`, where no consumer reads it. The product's changelog never
receives it.

The cause is that the release cut and the Phase 0 check are built around prawduct's own changelog
procedure:

- **The file** is hard-coded: `_DIGEST_REL_PATH = "plugin/CHANGELOG.md"`.
- **The section** is found by position (the topmost `## `). The writer also requires the heading to
  name the release (`vX.Y.Z` or `vX.Y.Z-dev…`).
- **The shape** is prawduct's: a required hand-written headline line, and `**`scope`**: text`
  paragraphs.

Two different predicates decide whether a repo has a digest at all, and neither reads anything a
product declares.

Finding "the section for this release" inside a changelog is the hard part of generalizing this.
It needs a convention for opening the section, a rename at release time, and a guard against
writing into a section that already shipped. Every product would have to get that convention
right.

**The motivating case** (#1069) is a high-throughput monorepo product with one root
`CHANGELOG.md`. About 1,000 of its commits in 30 days touched that file, which makes it a
merge-conflict hotspot. It wants per-PR fragments composed into the file at release time.

## Grounding facts

Re-verified against `develop` at `0964afa1` (v3.8.0-dev), 2026-10-25:

- **The cut does print something on an undeclared repo, but it is a dead end.** It prints
  `consumer notes: this repo publishes no consumer digest; the notes stay in the archive entries`
  and exits 0 (`change_cut.cut_cmd`). The line names no way to change that, and the template
  promises otherwise.
- **The current writer converts line endings.** It reads with `read_text`, splits with
  `splitlines()`, and joins with `"\n"`. On a CRLF file every line would change.
- **The coverage check has nothing left to check.** `check_releasability` already passes only
  legacy (non-fragment) scopes to it, because the cut writes fragment notes exactly. Under this
  design no notes are hand-written into a changelog at all.
- **Prawduct keeps an open dev section on purpose.** `plugin/CHANGELOG.md` starts with
  `## v3.8.0-dev`, which holds a placeholder headline: "Rolling notes for the next release".
  `tests/test_plugin_version_banner.py::test_changelog_has_current_version_entry` requires a
  section and a non-empty headline for the exact running version, prerelease included. The
  dev-track bump procedure edits that heading at every `-dev.N` move
  (`documentation/release-process.md`).
- **The banner degrades softly.** `plugin/hooks/banner.py` `parse_changelog` reads the bundled
  `CHANGELOG.md`'s `## vX.Y.Z` headings and headlines. A version with no section still shows the
  version move, just with no highlight ("highlights are best-effort, the version move is not").
- **changie's model** (from the source):
  - `changie batch <version>` renders `.changes/unreleased/*` into a new file `.changes/<version>.md`.
    It refuses with `version already exists` unless given `--force`. It can prepend a
    per-version header file (`--header-path`), then deletes the fragments.
  - `changie merge` lists `.changes/`, parses each filename as a version, sorts newest first, and
    truncates and rewrites `CHANGELOG.md` as a header followed by every version file.
  - The changelog is never read, only written. So "which section" never arises. The release's
    identity is a filename.
  - The cost is that hand edits to `CHANGELOG.md` are lost at the next merge, and adopting changie
    means moving existing history into version files. `changie init` writes a fresh
    `CHANGELOG.md` (`cmd/init.go`).

## Decisions

**1. One declaration, read by Phase 0 and the cut, and prawduct declares its own.**
`consumer_digest:` in `.prawduct/project-state.yaml` is read by one function, which both halves
call. Prawduct's `plugin/CHANGELOG.md` becomes one declared value. `_DIGEST_REL_PATH` and the
digest's use of `_ships_the_plugin_tree` are deleted.

*Owner confirmed, 2026-10-25* ("yes like any other"). This reverses the 2026-09-03 draft, which
kept prawduct's path hard-coded beside a declared one.

**2. A release is a file the cut creates (changie's identity model).** The cut renders the
shipping fragments into `.prawduct/releases/<version>.md`: a generated heading, the headline,
then the notes. That file's existence is the record that the release has been written. The cut
never searches the changelog for a section that belongs to this release.

*Owner chose this, 2026-10-25* ("yeah c"), over finding a section by heading and over full
regeneration.

**3. Insert, don't regenerate.** The cut inserts the release file's text into the declared
changelog as a new section, placed above the newest existing release section. It changes no byte
outside the inserted span. Existing history stays where it is and needs no migration. This is
where we depart from `changie merge`: the motivating product's large existing changelog stays as
it is, and hand edits to past sections survive.

**4. Pending notes live only in fragments, and the headline in one pending file.** Between
releases nothing is written into the changelog. The release's one-line judgement, which prawduct
requires and the banner shows, is written to `.prawduct/release-headline.md` (changie's
per-version header file). The cut moves it into the release file and removes it, the same way it
removes fragments.

**5. The cut refuses rather than skipping.** A declared changelog that is missing, a release file
that already exists, a changelog that already has a section for this release, or a required
headline that is absent each stop the cut before anything is written, and each is named. Phase 0
still only advises; it never changes the exit code. A product with no declaration gets no
changelog write, as today, and the cut's output tells it how to declare one.

**6. An external release tool runs after the cut.** Some products date sections, tag, or bump
versions with another tool (release-please, semantic-release, a script). The documented order is:
the cut inserts the release section, then the other tool does its work. The cut never needs a
heading renamed, because it writes a finished section.

**7. The plugin may write a product's declared changelog.** *Owner ruling, 2026-10-25* ("1 yes").
This was put to the owner against `architecture.md` § Direction, "The plugin writes nothing into a
governed repo except its own `.prawduct/` state…". The ruling is recorded beneath that clause, and
the clause's wording is left as ratified. The write happens only when the product has declared
`consumer_digest:` and an operator runs `cut-change-log --apply`. It touches only the inserted
span of the product's own file.

**8. The coverage check retires.** `_coverage_advisory` and `_digest_mentions` asked whether a
hand-written open section mentioned each pending scope. Under Decisions 2 and 4 no such section
exists: fragment notes reach the changelog exactly, and legacy entries carry no consumer note to
write. With no subject, the check is deleted rather than kept with nothing to check (the
proportionality norm in `nonfunctional-requirements.md`). Legacy products are pointed at fragments
instead (CDW8). *Inferred, owner can veto.*

## Requirements

MUST unless marked SHOULD.

### Declaration

- **CD1** `consumer_digest:` in `.prawduct/project-state.yaml` is a mapping with these fields:

  | Field | Values | Default |
  |---|---|---|
  | `path` | repo-relative path to the changelog | required |
  | `heading` | heading template; placeholders `{version}`, `{version_no_prefix}`, `{date}` | `## {version} - {date}` |
  | `headline` | `required` or `none` | `none` |
  | `layout` | `paragraphs`, `bullets` or `by-type` | `bullets` |
  | `entry` | entry template; placeholders `{note}`, `{scope}`, `{type}`, `{title}` | per layout (CD6) |
  | `types` | map of fragment type to subheading; `by-type` only | CD6 |
  | `marker` | a literal line the section is inserted directly below | none |

  Any of these makes the declaration invalid:
  - a missing `path`, or one that does not resolve inside the repo, or that has a `.git` component
    anywhere or `.prawduct` first, compared case-folded (amendment A1);
  - a field given twice (A1);
  - an unknown enum value or placeholder;
  - a heading template that does not start with `## `;
  - `types` without `by-type`.

  An invalid declaration is reported. It is never treated as undeclared.
- **CD2** Exactly one function reads the declaration, from the working tree. Phase 0 and the cut
  both call it. An absent or unreadable state file reads as undeclared.

### The cut

- **CD3** With a valid declaration, the cut writes all of the following in one all-or-nothing
  write, then removes the cut fragments and the headline file:
  - the archive entries, as today;
  - `.prawduct/releases/<version>.md`;
  - the changelog, with that file's text inserted.

  The release file holds the same lines that are inserted into the changelog. In order: the
  rendered heading, the headline paragraph when present, and the notes. The release file is
  LF-terminated. The changelog receives those lines in its own line-ending style, separated from
  its neighbours by blank lines (amendment A2, `733-design.md` § 3). Fragments whose note is
  `none:` contribute no note, as today.
- **CD4** The inserted section goes directly below `marker` when one is declared. Otherwise it goes
  directly above the first `## ` heading that names a version, meaning its first token is
  version-shaped after stripping `[ ]` and a leading `v`. With no version heading in the file, it
  is appended at the end. A non-version heading such as `## [Unreleased]` or `## Contents` is
  therefore never displaced downward.
- **CD5** Bytes outside the inserted span are unchanged: line-ending style (LF or CRLF), a UTF-8
  BOM, trailing-newline state, and every line before and after. The inserted text uses the file's
  own line-ending style. A CRLF fixture pins this with byte equality outside the span.
- **CD6** Notes render by layout:

  | Layout | Shape | Default entry template |
  |---|---|---|
  | `paragraphs` | paragraphs, one per note | `**`{scope}`**: {note}` (prawduct's form) |
  | `bullets` | one bullet list | `- {note}` |
  | `by-type` | a `### <heading>` subsection per fragment type, in `types` order | `- {note}` |

  The `by-type` default map is `feature`→`Added`, `fix`→`Fixed`, every other type→`Changed`. A
  multi-line note under a bullet continues indented beneath its bullet. Within a list, notes are
  ordered newest first, ties broken by scope, as today. `{{` and `}}` render literal braces.
- **CD7** The cut refuses before writing anything, with a named code:

  | Code | When |
  |---|---|
  | `digest-declaration-invalid` | the declaration fails CD1 |
  | `digest-missing` | the declared path is not a file |
  | `digest-unreadable` | the declared changelog is not valid UTF-8 (amendment A3) |
  | `marker-missing` | a declared `marker` is not in the file |
  | `release-in-changelog` | the changelog already has a `## ` heading naming exactly this version, prerelease included, so a published `-rc.1` section never blocks a later cut (amendment A5); the detail says to remove it or move its text to the headline file |
  | `no-headline` | `headline: required` and `.prawduct/release-headline.md` is absent or empty |
  | `releases-ignored` | git would ignore `.prawduct/releases/` (same check as `archive-ignored`) |
  | `release-already-cut` | see CD8 |

- **CD8** Re-runs. When `.prawduct/releases/<version>.md` already exists, the cut writes nothing,
  and this is decided before any "nothing to cut" early return.
  - A pending fragment whose own archive entry, the entry it renders to for this release, is
    already in the archive is removed. This completes a run that failed during removal, and adds
    nothing twice. Identity is the entry, not the scope name, because scope names are reused.
  - Any other pending fragment that is not withheld refuses `release-already-cut`, naming it. That
    includes a later fragment reusing a cut scope's name. It belongs to the next release.
  - A leftover `.prawduct/release-headline.md` is removed only when its text appears in the
    release file. Otherwise it is the next release's headline and is kept.
- **CD9** The dry run (without `--apply`) prints the release file's exact text, the changelog path,
  and the line it would be inserted at. Nothing is written or removed. A release PR can paste this
  output as its notes preview.
- **CD10** With no declaration, the cut writes no changelog and no release file. Its output names
  `consumer_digest:` in `.prawduct/project-state.yaml` as the way to have notes written. When the
  shipping set includes legacy entries, it says those carry no consumer note and names
  `/prawduct:doctor`'s fragment migration.
- **CD11** For the same fragments, prawduct's own result under its declaration is a
  `plugin/CHANGELOG.md` byte-identical to today's. The declaration is `path: plugin/CHANGELOG.md`,
  `heading: "## {version}"`, `headline: required`, `layout: paragraphs`. Today's starting state is
  an open section renamed to `## vX.Y.Z` carrying the headline line. The new starting state is the
  same headline in `.prawduct/release-headline.md` and no section. A golden test pins this. Its
  expected output is captured from today's code before the change.

### Phase 0

- **CD12** Under `headline: required`, Phase 0 warns when `.prawduct/release-headline.md` is absent
  or empty, or when its first non-empty line is a heading, which the banner would not show
  (amendment A4: nothing seeds the file, so the seeded-placeholder check retires). It also warns when the changelog already has a
  section naming the release (the CD7 `release-in-changelog` condition, reported early). Messages
  name the declared path. Neither warning changes the exit code. An invalid declaration warns. An
  undeclared repo sees no new output.
- **CD13** `_coverage_advisory` and `_digest_mentions` are deleted (Decision 8), along with
  `_open_digest_section` and the section-reading machinery that only they and the headline
  advisory used.

### Prawduct's own procedure

- **CD14** `plugin/CHANGELOG.md` no longer carries an open `## vX.Y.Z-dev` section. The
  `## v3.8.0-dev` section is removed. If its text is a real headline, that text moves to
  `.prawduct/release-headline.md`.
  - Dev-track bumps no longer edit the changelog.
  - The reopen step no longer opens a section.
  - The GitHub Release body comes from `.prawduct/releases/vX.Y.Z.md`, not from `awk` over the
    changelog.
- **CD15** `test_changelog_has_current_version_entry`'s contract changes with this decision. It is
  stated here so the change is not read as a weakened test. The new contract has two parts:
  - A released version (no prerelease suffix) must have its section and a non-empty headline,
    unchanged.
  - A prerelease version must have **no** section for its release, neither its `-dev` heading nor
    the final one. This is prawduct's guard against a leftover open section, which the product
    predicate no longer catches (amendment A5).

  Consequence: develop-pinned consumers see the version move without a highlight. The banner
  already degrades this way.

### Documentation

- **CDOC1** `plugin/templates/project-state.yaml` carries a commented `# CONSUMER DIGEST (opt-in)`
  block. It has a Keep a Changelog example (`heading: "## [{version_no_prefix}] - {date}"`,
  `layout: by-type`) and a minimal one, and states the external-tool order (Decision 6).
- **CDOC2** `plugin/templates/change-fragment.md` says the cut copies the note where the repo
  declares `consumer_digest:`. `plugin/docs/project-state-keys.md` lists the key.
- **CDOC3** `documentation/release-process.md` and
  `.prawduct/runbooks/cut-and-publish-a-plugin-release.md` describe prawduct's procedure under
  CD14: headline file, no rename, no reopen section, and the release body taken from the release
  file.

## Acceptance

- [ ] One declaration and one reader serve Phase 0 and the cut, and prawduct declares its own
      (Decision 1, CD1, CD2).
- [ ] A declared changelog receives every shipping fragment's consumer note at the cut, as a new
      section mirrored by `.prawduct/releases/<version>.md` (CD3, CD4, CD6).
- [ ] A missing, invalid or conflicting state refuses with a named reason, and nothing is written
      (CD7).
- [ ] Re-running adds nothing twice, and bytes outside the inserted span are unchanged (CD5, CD8).
- [ ] An external release tool can run after the cut with no rename owed to the cut (Decision 6).
- [ ] Undeclared products are unchanged apart from a more useful line. Prawduct's changelog result
      is byte-identical for the same inputs (CD10, CD11).
- [ ] Ships in v3.8.0. Its `ships` row in `.prawduct/artifacts/release-plan-v3.8.0.md` makes
      `check-releasability --release v3.8.0` refuse until it merges.

## Scope-out (this item)

- **Regenerating the changelog** from the release files (`changie merge`). Decision 3. Revisit if a
  product asks for a fully derived changelog.
- **Backfilling release files** for releases cut before this change. Revisit if a consumer needs
  history as files.
- **More than one changelog per repo** (changie `projects`). Revisit when a monorepo asks for
  per-package changelogs. The mapping leaves room for a list form later.
- **Version-file bumping** (`release_version_files:`, #576) and any integration with external
  release tools beyond the documented order.
- **Prawduct-side digest checks** (#702, #259).

## Evidence / references

- `plugin/lib/release_readiness.py`: `_DIGEST_REL_PATH`, `_SEEDED_HEADLINE`,
  `_ships_the_plugin_tree`, `_read_digest`, `_open_digest_section`, `_digest_mentions`,
  `_section_headline`, `_headline_advisory`, `_coverage_advisory`, `_digest_advisories`.
- `plugin/lib/change_cut.py`: `_names_release`, `_digest_write`, `plan_cut`, `apply_cut`, `cut_cmd`.
- `plugin/lib/change_fragments.py`: `TYPES`, `consumer_text`, `render_consumer_section`.
- `plugin/lib/change_log_archive.py`: `archive_would_be_ignored`, `_compose_bucket`.
- `plugin/hooks/banner.py`: `parse_changelog`.
- `tests/test_plugin_version_banner.py`: `test_changelog_has_current_version_entry`.
- `plugin/templates/change-fragment.md`, "Consumer note".
- changie v1.26.0: `cmd/batch.go` (`errVersionExists`, `--force`, `--header-path`, fragment
  removal), `cmd/merge.go` (`mergeProject`), `core/utils.go` (`GetAllVersions`), `cmd/init.go`.
- #1069 body (motivating case, proposed changes, acceptance), folded here 2026-10-25.
