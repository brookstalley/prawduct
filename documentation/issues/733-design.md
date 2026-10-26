# Issue #733 — Release Notes as a Release File Inserted Into a Declared Changelog: Design

`status: design · stage: design · area: release-tooling · added: 2026-09-18 · rewritten:
2026-10-25 for the release-file model · issue: https://github.com/brookstalley/prawduct/issues/733`

Builds on `documentation/issues/733-requirements.md` (CD1–CD15, CDOC1–CDOC3, Decisions 1–8).
This replaces the 2026-09-18 design, which located an open section by a keying strategy. The
owner's 2026-10-25 choice of the release-file model removed that problem, so none of that design
survives. The build plan is `.prawduct/artifacts/build-plan-consumer-digest.md`.

## Summary of what ships

1. **A new module, `plugin/lib/consumer_digest.py`.** It is the one home for "which file, what
   shape, where it goes". It holds the declaration reader, the version-heading predicate, the text
   model that preserves bytes, insertion-point selection, and every renderer. It has no CLI and
   writes nothing. `change_cut` writes; `release_readiness` advises.
2. **The cut** (`plugin/lib/change_cut.py`). It renders the shipping notes into one section. It
   writes that section to `.prawduct/releases/<version>.md` and inserts it into the declared
   changelog. Both writes join the archive in one all-or-nothing write. The fragments and the
   headline file are removed last.
3. **Phase 0** (`plugin/lib/release_readiness.py`). Its two prawduct-only digest checks become two
   declaration-driven advisories: the headline file, and a section already present for this
   release. The coverage check and all section-reading machinery are deleted.
4. **Prawduct's procedure.** Prawduct declares its own digest. Its changelog loses the open
   `-dev` section. The banner test and the unreleased-claims scan read the new shape. The runbooks
   take the GitHub Release body from the release file.

## Section 1 — the declaration (CD1, CD2)

```python
@dataclass(frozen=True)
class Declaration:
    path: str                         # repo-relative, validated (below)
    heading: str = "## {version} - {date}"
    headline: str = "none"            # "required" | "none"
    layout: str = "bullets"           # "paragraphs" | "bullets" | "by-type"
    entry: str | None = None          # None → the layout's default (Section 4)
    types: tuple[tuple[str, str], ...] = ()   # ordered (fragment type, subheading); by-type only
    marker: str | None = None

def read_declaration(project_dir: Path) -> tuple[Declaration | None, str | None]: ...
```

**Three outcomes.**
- `(None, None)`: undeclared. That covers an absent key, or no `.prawduct/project-state.yaml` at
  all (`FileNotFoundError`). A state file that exists but cannot be read (`OSError`,
  `UnicodeDecodeError`) is invalid, because it may hold a declaration (A6).
- `(None, reason)`: invalid.
- `(decl, None)`: valid.

**Parsing.**
- `core.read_yaml_block(text, "consumer_digest")` supplies the block. `YAML_UNPARSEABLE` is
  invalid. An inline value such as `consumer_digest: {…}` is unparseable by that reader's own rule.
- Each body line splits on its **first** `:` into field and value. Values go through
  `core.unquote_scalar`.
- `read_yaml_block` trims indentation, so a nested mapping cannot be read. `types` is therefore
  written as one flow mapping: `types: {feature: Added, fix: Fixed, refactor: Changed}`. It is
  parsed by splitting on `,`, then on the first `:` of each item. Subheadings may not contain `,`,
  `{` or `}`.

**Invalid, each with its own reason string.**

| Problem | Reason names |
|---|---|
| `path` is absent or empty | the field |
| `path` is absolute, contains a `..` segment, or does not resolve under `project_dir.resolve()` | the path, and that it must stay inside the repo |
| `path` has a component naming `.git` anywhere, or `.prawduct` first, under any filesystem's equivalence: case-folded, HFS+'s ignored format characters removed, NTFS's trailing dots and spaces removed, and NTFS 8.3 short names (`GIT~1`) counted, as git's own `.git` checks do (a nested repo's config is as executable as the top one's) | the path |
| a field is not one of the seven | the field |
| a field appears twice | the field (stricter than the repo's other readers, because this one drives a writer) |
| `headline` or `layout` holds an unknown value | the field and the allowed values |
| `heading`, after unquoting, does not start with `## ` | the heading. An unquoted `heading: ## {version}` reads as a comment and arrives empty, so the reason says to quote it |
| `heading` names a placeholder other than `{version}`, `{version_no_prefix}`, `{date}` | the placeholder |
| `entry` names a placeholder other than `{note}`, `{scope}`, `{type}`, `{title}` | the placeholder |
| `types` is set without `layout: by-type` | the conflict |
| `types` does not parse, or names a type outside `change_fragments.TYPES` | the item |
| `marker` is empty after unquoting | the field |
| `heading`, rendered with a sample version, does not lead with it (`heading_version` is `None`) | that the next cut could not recognise its sections, so releases would stack out of order and a second cut would not be refused |
| `entry` lacks `{note}` | that the notes would be dropped |

Placeholders are validated with `string.Formatter().parse`. Formatting uses `str.format_map`, so
`{{` and `}}` render as literal braces.

**`path` containment** comes from the hook-surface learning: "a validator refusing only the
malformed can still fail open when a value is interpolated into a filesystem path". The check
resolves the path and requires the result to sit under the repo root, which rejects a symlink
pointing out of the repo as well as `..`.

**Prawduct's declaration**, added to `.prawduct/project-state.yaml` in Chunk 03:

```yaml
consumer_digest:
  path: plugin/CHANGELOG.md
  heading: "## {version}"
  headline: required
  layout: paragraphs
```

## Section 2 — versions and headings

```python
def heading_version(line: str) -> str | None: ...
def names_release(line: str, version: str) -> bool: ...
```

- **`heading_version(line)`** returns a version for a `## ` line whose first whitespace-separated
  token is a version once enclosing `[ ]` and one leading `v` are stripped. A version here is
  `\d+\.\d+\.\d+(\.\d+)?(-[0-9A-Za-z.]+)?`, the shape `change_log.RELEASE_VALUE_RE` admits less
  its required `v`. Anything else returns `None`: `## [Unreleased]`, `## Contents`, `### 1.0.0`,
  `## 1.0` (two parts), `##1.0.0` (no space).
- **`names_release(line, version)`** is true when `heading_version(line)` equals the release
  exactly, prerelease suffix included, after stripping the release's own leading `v`. So
  `## v3.8.0` and `## [3.8.0] - 2026-10-25` name `v3.8.0`. `## v3.8.0-rc.1`, `## v3.8.0-dev.4`,
  `## v3.8.0.1` and `## v3.7.2` do not.

  The exact match is deliberate (amendment A5). A product that publishes `v1.4.0-rc.1` has
  released it, so its section is history and must not block the cut of `v1.4.0` or `-rc.2`. A
  leftover unreleased `## vX.Y.Z-dev` section is a prawduct-only convention, and prawduct's own
  banner test catches it (CD15, Section 8), so a product predicate never has to know about it.

## Section 3 — the text model (CD5)

```python
@dataclass(frozen=True)
class ChangelogText:
    bom: bool
    eol: str                 # "\r\n" or "\n": the first line ending in the file, else "\n"
    lines: tuple[str, ...]   # each line keeps its own terminator (\r\n, \n or \r)
    def render(self) -> str: ...   # BOM restored as U+FEFF; written with newline="" it is the original bytes

def read_changelog(path: Path) -> ChangelogText: ...      # raises DigestUnreadable
def place_section(text: ChangelogText, index: int, section: list[str]) -> tuple[ChangelogText, int]: ...  # also returns the heading's 1-based line
```

- **Reading.** `read_changelog` reads bytes and strips a leading `\xef\xbb\xbf` into `bom`. It
  decodes UTF-8 strictly, and a decode error raises `DigestUnreadable`, which the cut reports as
  `digest-unreadable` (requirement amendment A3). It splits with `keepends=True`, so every existing
  line keeps its own terminator. A file mixing line endings keeps each line's own, and only the
  inserted lines use `eol`.
- **Inserting.** `place_section` splices before `lines[index]`; `index == len(lines)` means the
  end. `section` arrives as lines without endings, and is terminated with `eol` and separated by
  blank lines:
  - **Before:** if the line before the insertion point is not blank, one blank line goes in
    first. At `index == 0` nothing goes before; the section becomes the file's first line. A file that does not end in a line ending, with the insert at the end, gets `eol`
    after its last line first. This is the one byte added outside the section, and it is required
    to start a line.
  - **After:** when the insert is not at the end, one blank line follows the section, unless the
    line at `index` is already blank.
  - **At the end of a file that had no trailing newline,** the section's last line takes no
    terminator, so the file still ends without one (CD5).
- **Rendering.** `render` re-emits the BOM and concatenates `lines`. Lines before the insertion
  point and from `index` onward come out byte-for-byte as read. That is the property the tests
  check with byte comparison.

## Section 4 — the section renderer (CD3, CD6)

```python
def render_section(decl: Declaration, version: str, date: str,
                   headline: str | None, fragments: list[Fragment]) -> list[str]: ...
```

Output is lines without endings, in this order:

1. The heading, formatted from `decl.heading` with `version` as normalized `vX.Y.Z`,
   `version_no_prefix` (no `v`) and `date`. `date` is `YYYY-MM-DD`, the operator's local date (an evening cut west of UTC must not be dated tomorrow); `plan_cut`
   takes `today: date | None = None` so tests can fix it.
2. A blank line, then the headline text if one is present, verbatim and stripped, possibly several
   lines.
3. A blank line, then the notes (below). With no notes, only a `none:`-only release has this
   case, and the section ends after the headline. With neither headline nor notes, the section is
   the heading alone. That is legitimate, because the release did ship.

**Note order** is today's `render_consumer_section` order: newest `date` first, ties broken by
`scope`, two stable sorts. Only fragments with `consumer_text` appear. `render_consumer_section`
moves here as `ordered_notes(fragments)` and is deleted from `change_fragments.py`, with its test
moving to `tests/test_consumer_digest.py`.

**Layouts.** Placeholders are `note`, which is `consumer_text`, plus `scope`, `type` and `title`
from the fragment. A note may be several lines.

| Layout | Default `entry` | Separator | Continuation of a multi-line note |
|---|---|---|---|
| `paragraphs` | `` **`{scope}`**: {note} `` | blank line between entries | verbatim (today's form) |
| `bullets` | `- {note}` | none | each later line indented 2 spaces; a blank line inside a note stays an empty line |
| `by-type` | `- {note}` | none, inside each subsection | as `bullets` |

**`by-type` subsections.**
- One `### <subheading>` per subheading that receives at least one note. The order is first
  appearance in the effective map.
- The effective map is `decl.types` when given; otherwise `feature→Added, fix→Fixed`, then every
  other member of `TYPES`→`Changed`, in `TYPES` order.
- A type absent from a declared map falls into a final `Changed` subsection. One is appended if
  the map has none, so no note is dropped.
- Subsections are separated by a blank line, and a blank line follows each `###` heading.

The `paragraphs` default plus the `## {version}` heading reproduce today's prawduct section
exactly: headline paragraph, blank line, notes joined by blank lines. This is what CD11's golden
test checks.

**Worked Keep a Changelog example.** The declaration is
`heading: "## [{version_no_prefix}] - {date}"`, `layout: by-type`, no headline. The cut is
`v1.4.0` on 2026-10-25, and the shipping fragments are `feature`/`search` (a two-line note),
`fix`/`login` and `chore`/`deps` (`none:`). The section rendered:

```
## [1.4.0] - 2026-10-25

### Added

- Search across projects.
  Results rank by recency.

### Fixed

- Login no longer loops on an expired token.
```

It is inserted into:

```
# Changelog\r\n
\r\n
## [Unreleased]\r\n
\r\n
## [1.3.0] - 2026-09-01\r\n
...
```

The insert goes before `## [1.3.0]`, the first line `heading_version` accepts. `## [Unreleased]`
stays on top, the inserted lines end in `\r\n`, and every other byte is unchanged.

## Section 5 — insertion point (CD4)

```python
def insertion_index(text: ChangelogText, marker: str | None) -> int: ...  # raises MarkerMissing
```

- **With `marker`:** the index just after the first line whose `rstrip("\r\n")` equals the marker
  exactly. If no line matches, the cut refuses `marker-missing`.
- **Without a marker:** the index of the first line for which `heading_version` is not `None`.
- **With no such line:** `len(lines)`, meaning the end of the file.

A `### ` or deeper heading is never a candidate, so subsections of a past release cannot attract
the insert.

## Section 6 — the cut (CD3, CD7–CD10)

### `plan_cut(project_dir, release, scopes=None, *, today=None)`

The order matters, and the first refusal wins with nothing written.

1. **Version validation and the pending-set read**, with their refusals, unchanged.
2. **The declaration.** `decl, reason = consumer_digest.read_declaration(project_dir)`.
   - With a `reason`, refuse `digest-declaration-invalid`.
   - With `decl is None`, take the CD10 path: today's flow (empty-pending and empty-cut early
     returns, `archive-ignored`, classification, archive writes) and nothing more.
     `result.digest = None`, and the output names `consumer_digest:`.
3. **The release file decides next, before any early return.** If `.prawduct/releases/<version>.md`
   exists, CD8 governs and step 4 onward is skipped. This step sits ahead of the empty-pending and
   empty-cut returns because its two cleanup cases are reached with nothing left to cut.
   - **Which fragments are already published is decided by entry identity, not by scope name.**
     For each pending fragment, the cut renders `render_entry(fragment, release=version)`, splits
     it into its `Block`, and asks `change_log_archive.holds_entry(prawduct_dir, block)`. That is a
     new public function: the block's `key` is present in its bucket's month file. This is the
     identity `_compose_bucket` already dedupes by.
   - A held fragment goes in `result.cleanup`; it is removed and nothing is written.
   - Scope names are reused, so a later fragment for an already-cut scope renders a different
     entry and is not held. Every pending fragment that is not held and not withheld, by the
     release plan's classification or by `--scope` naming, refuses `release-already-cut` with its
     scope. It belongs to the next release.
   - The classification is consulted only when non-held fragments exist. A re-run whose only
     leftovers are held fragments, or only a headline file, needs no release plan.
   - **A lingering `.prawduct/release-headline.md` is removed only if it is the headline this cut
     already published.** It is compared line by line, not as raw text: the file's lines, each
     with line endings and trailing whitespace stripped and with leading and trailing blank lines
     dropped, must occur as a consecutive run of the release file's lines. That is the form
     `render_section` wrote them in. So a CRLF or trailing-space headline file still matches the
     text it produced. A
     headline file whose text is not in the release file is someone's headline for the *next*
     release. It is kept, and the output says so.
   - The result has `cut == []`. The cut is applied when `cleanup` or `headline_file` is
     non-empty (`cut_cmd`, below).
4. **Today's flow** for a declared repo with no release file: the empty-pending and empty-cut
   early returns, `archive-ignored`, the classification, the archive writes. Then:
5. `releases-ignored`: `change_log_archive.record_is_tracked(project_dir)` holds and git ignores
   `.prawduct/releases/0000.md`. `record_is_tracked` is extracted from
   `archive_would_be_ignored`'s first half, and `archive_would_be_ignored` then calls it, so the
   "is the change record tracked" rule has one body.
6. `digest-missing`: the resolved `decl.path` is not a file. `digest-unreadable`:
   `read_changelog` raised.
7. `release-in-changelog`: some line of the changelog satisfies `names_release(line, version)`.
   The detail names that line's number, and says to remove the section, or to move its first
   paragraph into `.prawduct/release-headline.md` if it was a headline.
8. `no-headline`: `decl.headline == "required"`, and `.prawduct/release-headline.md` is absent or
   has no non-blank line. Otherwise the headline is that file's text, stripped. It is still used
   when present under `headline: none`. A headline file that is not valid UTF-8 refuses
   `no-headline` too, with that detail, in either mode, because it cannot go in the release.
9. `marker-missing` comes from `insertion_index`.

After those checks, the cut renders `section = render_section(...)` and adds two writes to
`result.writes` beside the archive buckets. Every rule behind them is `consumer_digest`'s to
answer, and the cut asks rather than computing it again:
- `(releases/<version>.md, release_file_text(section))`. The release file is always LF and
  newline-terminated, and its text is the section.
- `(decl.path, placed.render())`, where `placed, insert_line = place_section(text, index,
  section)`. `place_section` owns the blank-line rule, so it also owns the line the heading lands
  on.
- On a re-run, the headline check is `headline_published(headline, release_text)`. That function
  and `render_section` both use `headline_lines`, so "published" means "rendered from this file".
  Trailing whitespace is ignored on both sides, so a release file an editor or a hook trimmed
  after commit still holds its published headline.

`core.write_all_or_none` takes `(Path, str)`, and it captures each prior with `read_text`, whose
universal-newline decoding turns `\r\n` into `\n`. So a rollback would re-line-end a CRLF
changelog even if the forward write were exact. The changelog needs exact bytes **in both
directions**: the forward write, and the prior captured for rollback and restored by it.

Chunk 02 settles this one of two ways:
- a bytes-capable sibling, `write_all_or_none_bytes`, which reads priors with `read_bytes` and
  writes and restores bytes;
- widening the function, with the same priors-as-bytes rule.

**Settled in Chunk 02:** neither. `atomic_write_text` already takes `newline=""`, which writes a `str` through untranslated, so `write_all_or_none` reads every prior with `newline=""` and writes and restores with `newline=""`. The changelog stays a `str` (`ChangelogText.render`), and the round trip is byte-exact with no bytes API. The cut passes every write through it, archive and release file included, so there is
one transaction rather than two. Its test injects a failure after the changelog write and
compares the restored file byte for byte. Chunk 02 records which option it took in the plan's
Decisions.

### `CutPlan`

The existing fields stay, and these are added:
- `release_file: Path | None`;
- `section_text: str | None` (the release file's text);
- `insert_line: int | None` (1-based, for the preview);
- `cleanup: list[FragmentFile]`;
- `headline_file: Path | None`;
- `headline_kept: Path | None` and `headline_kept_reason: str`: a re-run's headline file that is
  kept, and why (the next release's headline, or unreadable, so unknown);
- `legacy_shipping: list[str]`: the legacy scopes this release's plan ships. With nothing else
  pending, the plan is read only for this, and a missing plan means none ship;
- `has_work` (property): any cut, cleanup or headline removal.

`digest` now carries `decl.path` rather than a heading. `notes_added` keeps its meaning.

### `apply_cut`

1. `mkdir(parents=True, exist_ok=True)` for **every** write's parent. Today it does only the
   first, which would miss `.prawduct/releases/`.
2. `write_all_or_none` over all the writes.
3. Unlink the cut fragments, then the cleanup fragments, then the headline file. A failure here
   is `FragmentRemovalFailed`, as today, and the re-run completes it through CD8.

### Re-run table (CD8)

| Release file | Pending fragment | Headline file | Result |
|---|---|---|---|
| absent | — | — | normal cut (steps 4–9) |
| present | its own entry is in the archive (held) | — | fragment removed, nothing written |
| present | not held, not withheld (includes a later fragment reusing a cut scope's name) | — | refuse `release-already-cut`, naming it |
| present | not held, withheld | — | kept pending; not this release's |
| present | none left | its text is in the release file | headline file removed |
| present | none left | its text is not in the release file | kept, as the next release's headline; output says so |
| present | none left | absent | `nothing to do` |

### Output (`cut_cmd`)

The existing lines stay. The consumer-notes line becomes one of:

- `  consumer notes: N written to <decl.path> as a new section at line L (release file <rel path>)`;
- `  consumer notes: this repo declares no consumer_digest:, so the notes stay in the archive entries. Declare consumer_digest: in .prawduct/project-state.yaml to have the cut write them to your changelog`;
- `  consumer notes: the release file exists; removing K fragment(s) the archive already holds, writing nothing`.

`cut_cmd` reports `nothing to do` only when `cut`, `cleanup` and the headline-file removal are all
empty. Otherwise it applies the plan, so CD8's cleanup cases are reachable from the command.

When the shipping set includes legacy change-log entries, the output adds: `legacy entries carry
no consumer note; /prawduct:doctor offers the move to fragments`.

On a dry run, the output adds `--- section (as written to <rel path>) ---`, then the section text
verbatim, then `--- end ---`. That block is CD9's preview, the same text `--apply` writes to the
release file.

Refusals print as today: `refused: <code>: <detail>. Nothing was written.`

## Section 7 — Phase 0 (CD12, CD13)

`_digest_advisories(project_dir, release)` is called where it is today, before `_resolve_version`.
It is given `normalize_version(release)` when `--release` was passed, and `None` otherwise. It
never gets the `plugin/VERSION` fallback, which is prawduct's path and carries a deliberately low
`-dev` marker, not a release. It returns `(warnings, note, emissions)`, as today:

- undeclared → `([], None, [])`.
- invalid → `([f"{reason}; the consumer digest checks did not run"], None, [])`.
- `--release` known and `.prawduct/releases/<version>.md` existing → no checks, only a note that
  the release is already cut, and the emission `digest: <version> already cut (<release file> →
  <decl.path>)`. After the cut the headline file is consumed and the section is the cut's own;
  checking again would tell the operator to remove that section, and a re-cut would not restore
  it (A6).
- The headline file is read once, through `consumer_digest.read_headline`, the one reader the cut
  also uses:
  - unreadable → a warning in either mode, because the cut refuses `no-headline` on it either way;
  - absent or blank → a warning only under `headline: required`;
  - first non-empty line a heading → a warning in either mode, because the cut uses a present
    file either way, and the banner reads no headline from a section that opens on a heading.
- With `release` known, any heading `consumer_digest.release_sections` finds → a warning, the CD7
  `release-in-changelog` condition reported early, ending in the same
  `RELEASE_IN_CHANGELOG_REMEDY` the cut's refusal uses. With `release` unknown, a note that this check
  did not run.
- Emissions: `digest headline: '<first line>' (.prawduct/release-headline.md → <decl.path>)`, or
  `digest headline: none`.

**Deleted:**
- `_DIGEST_REL_PATH`, `_DIGEST_SECTION_RE`, `_read_digest`, `_open_digest_section`,
  `_section_headline`, `_headline_advisory`, `_coverage_advisory`, `_digest_mentions`;
- `_SEEDED_HEADLINE`, because under this model nothing seeds the headline file (requirement
  amendment A4);
- the `legacy_pending` argument at the call site, whose only consumer was the coverage check;
- the docstring paragraph explaining why the checks stayed prawduct-only.

`_ships_the_plugin_tree` stays, for the VERSION-fallback hint at `no-version:`.

**The test that pinned agreement on emptiness between `_section_headline` and the banner** is
replaced by a stronger pin. Render a release section with `render_section` and parse it with
`banner.parse_changelog`. The banner's headline must equal the headline file's first line. The
property that matters, "what the operator wrote is what consumers see", is then checked through
the real banner parser.

## Section 8 — prawduct's own procedure (CD14, CD15)

- **`plugin/CHANGELOG.md`.** Remove the `## v3.8.0-dev` section. Its text is the "Rolling notes"
  placeholder, not a headline, so nothing moves. Phase 0 will warn about the missing headline file
  until v3.8.0's headline is written.
- **`tests/test_plugin_version_banner.py::test_changelog_has_current_version_entry`**, renamed
  `test_changelog_matches_the_current_version`, gets the
  CD15 contract:
  - a released version must have its section, with a non-empty headline;
  - a prerelease version must have no section for its **base** release, neither the `-dev`
    heading nor the final one. This is a base-version match of the test's own, not
    `names_release`, which is exact (A5) and would catch neither.

  Red is shown both ways, by fixture, not against the live file.
- **`tests/test_suite_at_boundary.py`.** `_corpus`'s `CHANGELOG.md#unreleased` slice reads the
  first `## ` section as the live unreleased claims. Under this model the first section is the
  latest release, and the unreleased claims are the consumer notes in `.prawduct/changes/*.md` and
  `.prawduct/release-headline.md`. The slice is replaced by those files, keyed
  `changes#<scope>` and `release-headline`, so the retired-wording scan keeps a subject. The
  carrier assertion names a `changes#…` key. These files are not shipped yet, but they become the
  shipped section at the cut. This is a requirement change (CD14), recorded in the commit.
- **`.prawduct/runbooks/cut-and-publish-a-plugin-release.md`.** Enumerated 2026-10-25 by
  `grep -n "CHANGELOG\|-dev\|headline\|awk"`:
  - step 2: write the headline to `.prawduct/release-headline.md`, as one unwrapped line;
  - the cut's expected output and its refusal list (`no-headline`, `wrong-section` →
    `release-in-changelog`, and the new codes);
  - step 10: the rename is deleted;
  - step 16: the commit message takes the headline from the release file;
  - step 20: the body is `tail -n +3 .prawduct/releases/vX.Y.Z.md`, which drops the heading and its
    blank line, in place of `awk`;
  - step 22: no section is opened at reopen, and the "not bookkeeping" warning block goes;
  - the version-files list (line ~892): `plugin/CHANGELOG.md` stays, because the cut writes it.

  `.prawduct/runbooks/promote-a-pruned-release.md`'s `awk` step changes the same way.
- **`documentation/release-process.md`:** the cut description; the dev-track bump, which no longer
  edits the changelog; the reopen step; and the release-notes extraction.

## Section 9 — documentation (CDOC1–CDOC3)

- **`plugin/templates/project-state.yaml`:** a `# CONSUMER DIGEST (opt-in)` block after
  `# RELEASE VERSION FILES`, in that section's comment style. It explains:
  - what it buys;
  - that the cut writes `.prawduct/releases/<version>.md` and inserts it, never searching or
    renaming;
  - where it inserts;
  - the headline file;
  - the external-tool order.

  It shows two commented examples, a Keep a Changelog one and a minimal one, each valid on its
  own.
- **`plugin/templates/change-fragment.md`:** "Where the repo declares `consumer_digest:`, the
  release cut writes this text into its changelog."
- **`plugin/docs/project-state-keys.md`:** a `consumer_digest (opt-in)` section beside
  `release_version_files`, with the field table.
- **Module docstrings** of `change_cut.py` (its point 2) and `release_readiness.py`.
- **Swept by claim** in Chunk 06, from the 2026-10-25 enumeration:
  - `documentation/project-structure.md`;
  - `documentation/governance-artifact-lifecycle-requirements.md`;
  - `plugin/skills/critic/cross-checks.md`;
  - every hit of `consumer digest`, `release cut copies` and `open section`.

## Requirement amendments made in design

These are applied to `733-requirements.md` in the same commit as this document. They are builder
amendments made in design, not owner rulings, and the owner can veto any of them. A4 retires a
check and A5 narrows one.

- **A1 (CD1).** `path` must resolve inside the repo, and no component may name `.git` (anywhere)
  or `.prawduct` (first) under any filesystem's equivalence (Section 1's table). A field that
  appears twice is invalid.
- **A2 (CD3).** The release file is LF and newline-terminated. The changelog receives the same
  lines in its own line-ending style, with blank-line separation (Section 3). "Exactly the text"
  means the same lines.
- **A3 (CD7).** A new refusal, `digest-unreadable`: the declared changelog is not valid UTF-8.
- **A4 (CD12).** The "seeded placeholder" clause is dropped, because nothing seeds the headline
  file. New warning: the headline's first line is a heading.
- **A6 (CD2, CD12), from Chunk 03's review.** An unreadable state file is invalid, not undeclared.
  A present headline file is checked in either mode, with absence owed only under `required`.
  Phase 0 steps aside once the release file exists. `read_headline`, `release_sections` and
  `RELEASE_IN_CHANGELOG_REMEDY` join `consumer_digest`, so neither caller restates them, and
  `insert_section` (which only tests called) gives way to `place_section`.
- **A5 (CD7, CD12).** `release-in-changelog` matches the exact version, prerelease included, so a
  published prerelease section never blocks a later cut. Prawduct's leftover-`-dev`-section guard
  moves to its own banner test (CD15).

## Test plan

| Requirement | Test (file) |
|---|---|
| CD1, A1 | each invalid reason, parametrized; quoted versus unquoted heading; `..`, absolute and symlink-escape paths; duplicate field (`test_consumer_digest.py`) |
| CD2 | unreadable state file reads as undeclared; one reader, pinned by grep that `release_readiness` and `change_cut` read `consumer_digest` only through `read_declaration` (`test_consumer_digest.py`) |
| CD4 | marker, past `[Unreleased]`, `### 1.0.0` ignored, end of file (`test_consumer_digest.py`) |
| CD5, A2 | CRLF, BOM, mixed endings, no trailing newline at end of file: byte equality outside the span by slicing `render()` (`test_consumer_digest.py`); end to end through the cut (`test_change_cut.py`) |
| CD6 | each layout; by-type default and declared maps; type missing from the map; multi-line bullets; `{{` and `}}` (`test_consumer_digest.py`) |
| CD3, CD9 | release file text equals the dry-run block; release file plus changelog plus archive all-or-nothing, with an injected write failure leaving all three untouched (`test_change_cut.py`) |
| CD7, A3, A5 | each code, with nothing written and the fragments present; a published `## v1.4.0-rc.1` does not block the `v1.4.0` cut (`test_change_cut.py`) |
| CD8 | every row of the re-run table, run through `cut_cmd`, not only `plan_cut`, so reachability is pinned: a removal failure injected on a fragment and on the headline file; a later fragment reusing a cut scope's name refuses and is still on disk; a next-release headline file survives; a CRLF and trailing-space headline file that was published is still removed (`test_change_cut.py`) |
| CD10 | the undeclared line names the key; the legacy line (`test_change_cut.py`) |
| CD11 | `TestPrawductGolden` in `test_change_cut.py`: `GOLDEN_PRAWDUCT_CHANGELOG`, captured from the section-flow cut, must also be what the release-file flow produces from the same fragments with the headline in `.prawduct/release-headline.md` and no section |
| write path | an injected failure after the changelog write restores a CRLF + BOM changelog byte for byte (`test_core` or `test_change_cut.py`) |
| CD12, A4 | each warning; exit code unchanged on pass and on fail; undeclared prints nothing new (`test_release_readiness.py`) |
| CD13 | grep pin that the deleted names are absent from `plugin/lib` (`test_release_readiness.py`) |
| CD14 | `test_suite_at_boundary.py` carrier assertion on the new corpus keys |
| CD15 | the banner contract both ways, plus banner-and-renderer agreement (`test_plugin_version_banner.py`) |

**Red-first discipline.** Each guard test names the input that must trip it, as the build cycle
requires. The golden test is shown red with a one-byte mutation of the expected output. The CRLF
test is shown red by a test-only writer that uses `"\n".join`.

## Requirement-to-section trace

| Requirement | Section |
|---|---|
| CD1, CD2 | 1 |
| CD3 | 4, 6 |
| CD4 | 5 |
| CD5 | 3 |
| CD6 | 4 |
| CD7 | 6 (steps 1–9) |
| CD8 | 6 (re-run table) |
| CD9, CD10 | 6 (output) |
| CD11 | 4 (paragraphs default), test plan |
| CD12, CD13 | 7 |
| CD14, CD15 | 8 |
| CDOC1–CDOC3 | 8, 9 |

## Evidence / references

- `plugin/lib/core.py`: `read_yaml_block` (trims indentation, so nested maps cannot be read),
  `strip_scalar_comment` (a quoted `#` is data), `unquote_scalar`, `write_all_or_none`.
- `plugin/lib/release_readiness.py`: `normalize_version`, `_resolve_version`, and the digest call
  site.
- `plugin/lib/change_log_archive.py`: `archive_would_be_ignored` (its tracked-record half becomes
  `record_is_tracked`); `Block.key` and `_compose_bucket`'s dedupe by it. That key is the entry
  identity CD8's new `holds_entry` reads. A scope-name lookup such as `scopes_tagged_for` is
  deliberately not used, because scope names are reused.
- `plugin/lib/change_fragments.py`: `TYPES`, `Fragment` (`scope`, `type`, `date`, `title`,
  `consumer_text`), `render_entry` (archive entries carry `scope=` and `release=` tags),
  `render_consumer_section`.
- `plugin/hooks/banner.py`: `_SEMVER_HEADER`, `parse_changelog`.
- `tests/test_suite_at_boundary.py`: `_corpus`'s unreleased slice.
- changie v1.26.0: `cmd/batch.go` (`errVersionExists`, `--header-path`), `cmd/merge.go`.
