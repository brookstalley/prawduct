"""A product's declared changelog: what the release cut writes, and where.

A release is a file the cut creates, ``.prawduct/releases/<version>.md``, and
its text is inserted into the declared changelog as a new section above the
newest release. The changelog is written, never searched for an open section,
so a product needs no convention for opening, renaming or closing one, and a
note can never land in a section that already shipped.

This module is the one home for "which file, what shape, where it goes". It
reads the ``consumer_digest:`` declaration, recognises version headings,
renders a release section, and splices it into the changelog without touching
any other byte. It writes nothing. The release cut, which writes, and the
Phase 0 check, which advises, are meant to ask it rather than keep a path or
a heading rule of their own.

Everything here is pure except three reads of the filesystem:
:func:`read_declaration` and :func:`read_changelog` read one file each, and
declaration validation resolves the declared path to check where it really
points.
"""

from __future__ import annotations

import re
import string
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from . import change_fragments
from .core import YAML_ABSENT, YAML_UNPARSEABLE, read_yaml_block, unquote_scalar

DECLARATION_KEY = "consumer_digest"
STATE_FILE_REL = ".prawduct/project-state.yaml"
RELEASES_DIR_REL = ".prawduct/releases"
HEADLINE_FILE_REL = ".prawduct/release-headline.md"

LAYOUTS = ("paragraphs", "bullets", "by-type")
HEADLINE_MODES = ("required", "none")
DEFAULT_HEADING = "## {version} - {date}"
HEADING_FIELDS = ("version", "version_no_prefix", "date")
ENTRY_FIELDS = ("note", "scope", "type", "title")

#: The paragraphs default is prawduct's own section form, which the version
#: banner and every shipped section already use; the bullet layouts default to
#: the plain list a Keep a Changelog file expects.
DEFAULT_ENTRY = {
    "paragraphs": "**`{scope}`**: {note}",
    "bullets": "- {note}",
    "by-type": "- {note}",
}

#: Keep a Changelog's vocabulary for the fragment types that have a natural
#: home there; every other type is a change.
_DEFAULT_TYPE_HEADINGS = {"feature": "Added", "fix": "Fixed"}
_FALLBACK_TYPE_HEADING = "Changed"

_FIELDS = ("path", "heading", "headline", "layout", "entry", "types", "marker")

#: A release version as a heading spells it once ``[ ]`` and a leading ``v``
#: are stripped: the shape ``change_log.RELEASE_VALUE_RE`` admits, less its
#: required ``v``.
_VERSION_RE = re.compile(r"\d+\.\d+\.\d+(?:\.\d+)?(?:-[0-9A-Za-z.]+)?")
_H2_RE = re.compile(r"^##[ \t]+(\S+)")
_LINE_RE = re.compile(r"[^\r\n]*(?:\r\n|\n|\r)|[^\r\n]+\Z")
_SAMPLE_FIELDS = {"version": "v0.0.0", "version_no_prefix": "0.0.0", "date": "2000-01-01"}


@dataclass(frozen=True)
class Declaration:
    """A valid ``consumer_digest:`` declaration. ``path`` is repo-relative."""

    path: str
    heading: str = DEFAULT_HEADING
    headline: str = "none"
    layout: str = "bullets"
    entry: str | None = None
    types: tuple[tuple[str, str], ...] = ()
    marker: str | None = None

    @property
    def entry_template(self) -> str:
        return self.entry if self.entry is not None else DEFAULT_ENTRY[self.layout]


def read_declaration(project_dir: Path) -> tuple[Declaration | None, str | None]:
    """``(declaration, invalid_reason)`` from the working tree's project state.

    ``(None, None)`` is undeclared — an absent key, and equally an absent or
    unreadable state file, which cannot be told apart from one that never
    declared. ``(None, reason)`` is a declaration this reader refuses, and it is
    never read as undeclared: an operator who wrote the key meant something.
    """
    try:
        text = (project_dir / STATE_FILE_REL).read_text(encoding="utf-8")
    except (OSError, ValueError):
        return None, None
    return parse_declaration(text, project_dir)


def parse_declaration(text: str, project_dir: Path) -> tuple[Declaration | None, str | None]:
    """:func:`read_declaration` over the state file's ``text``."""
    status, body = read_yaml_block(text, DECLARATION_KEY)
    if status == YAML_ABSENT:
        return None, None
    if status == YAML_UNPARSEABLE:
        return None, f"{DECLARATION_KEY}: is written in a shape this reader cannot parse; use one `field: value` per line"
    fields: dict[str, str] = {}
    for line in body:
        name, sep, raw = line.partition(":")
        name = name.strip()
        if not sep or not name:
            return None, f"{DECLARATION_KEY}: line {line!r} is not a `field: value` pair"
        if name not in _FIELDS:
            return None, f"{DECLARATION_KEY}: unknown field {name!r} (fields: {', '.join(_FIELDS)})"
        if name in fields:
            # Stricter than the repo's other readers on purpose: this one
            # drives a writer, and "the last one wins" is a guess about which
            # line the operator meant.
            return None, f"{DECLARATION_KEY}: {name} is given twice"
        fields[name] = unquote_scalar(raw.strip())

    path, reason = _validated_path(fields.get("path", ""), project_dir)
    if reason:
        return None, reason
    headline = fields.get("headline", "none")
    if headline not in HEADLINE_MODES:
        return None, f"{DECLARATION_KEY}: headline: {headline!r} is not one of {', '.join(HEADLINE_MODES)}"
    layout = fields.get("layout", "bullets")
    if layout not in LAYOUTS:
        return None, f"{DECLARATION_KEY}: layout: {layout!r} is not one of {', '.join(LAYOUTS)}"
    heading = fields.get("heading", DEFAULT_HEADING)
    reason = _heading_problem(heading)
    if reason:
        return None, reason
    entry = fields.get("entry")
    if entry is not None:
        reason = _template_problem("entry", entry, ENTRY_FIELDS) or (
            None if "note" in _placeholders(entry) else f"{DECLARATION_KEY}: entry must contain {{note}}, or the notes are dropped"
        )
        if reason:
            return None, reason
    types: tuple[tuple[str, str], ...] = ()
    if "types" in fields:
        if layout != "by-type":
            return None, f"{DECLARATION_KEY}: types is only read by `layout: by-type` (layout is {layout!r})"
        types, reason = _parse_types(fields["types"])
        if reason:
            return None, reason
    marker = fields.get("marker")
    if marker is not None and not marker.strip():
        return None, f"{DECLARATION_KEY}: marker is empty"
    return Declaration(path, heading, headline, layout, entry, types, marker), None


def _validated_path(raw: str, project_dir: Path) -> tuple[str, str | None]:
    """The declared path, or why it may not be written.

    Containment is checked on the resolved path, not the spelling: the value is
    joined to the repo root and handed to a writer, so a symlink pointing out of
    the repo is as much an escape as ``..``.
    """
    if not raw:
        return "", f"{DECLARATION_KEY}: needs `path`, the changelog's repo-relative path"
    rel = Path(raw)
    if rel.is_absolute() or ".." in rel.parts:
        return "", f"{DECLARATION_KEY}: path {raw!r} must be repo-relative and stay inside the repo"
    root = project_dir.resolve()
    resolved = (project_dir / rel).resolve()
    if resolved != root and root not in resolved.parents:
        return "", f"{DECLARATION_KEY}: path {raw!r} resolves outside the repo ({resolved})"
    inside = resolved.relative_to(root).parts
    # A `.git` anywhere refuses, because a nested repository's config is as
    # executable as the top one's (a `core.fsmonitor` line runs on `git status`).
    if not inside or any(_names_dir(part, ".git") for part in inside) or _names_dir(inside[0], ".prawduct"):
        return "", f"{DECLARATION_KEY}: path {raw!r} names a location the cut must not write"
    return raw, None


def _names_dir(part: str, name: str) -> bool:
    """Whether path component ``part`` may name the directory ``name`` on some filesystem.

    ``resolve()`` keeps the spelling it was given, so equivalence is decided
    here, the way git's own `.git` checks decide it: case-folded (macOS and
    Windows are case-insensitive), with format characters HFS+ ignored removed,
    with the trailing dots and spaces NTFS drops removed, and with NTFS's 8.3
    short name (`GIT~1`, `PRAWDU~1`) counted as the name.
    """
    # HFS+ ignored the Unicode format characters (category Cf: zero-width
    # joiners, direction marks, U+FEFF), so `.g\u200cit` named `.git`.
    folded = "".join(ch for ch in part if unicodedata.category(ch) != "Cf").rstrip(". ").casefold()
    if folded == name:
        return True
    short = name.lstrip(".")[:6]
    return re.fullmatch(re.escape(short) + r"~\d+", folded) is not None


def _placeholders(template: str) -> list[str]:
    return [name for _lit, name, _spec, _conv in string.Formatter().parse(template) if name is not None]


def _template_problem(field: str, template: str, allowed: tuple[str, ...]) -> str | None:
    try:
        parsed = list(string.Formatter().parse(template))
    except ValueError as exc:
        return f"{DECLARATION_KEY}: {field} {template!r} has an unbalanced brace ({exc}); write a literal brace as {{{{ or }}}}"
    for _lit, name, spec, conv in parsed:
        if name is None:
            continue
        if name not in allowed or spec or conv:
            return f"{DECLARATION_KEY}: {field} placeholder {{{name}}} is not one of {', '.join('{' + a + '}' for a in allowed)}"
    return None


def _heading_problem(heading: str) -> str | None:
    if not heading.strip():
        # An unquoted `heading: ## {version}` reaches here empty: YAML reads
        # the `#` as the start of a comment.
        return f"{DECLARATION_KEY}: heading is empty; quote it (`heading: \"## {{version}}\"`), since an unquoted # starts a comment"
    if not heading.startswith("## "):
        return f"{DECLARATION_KEY}: heading {heading!r} must start with `## `"
    reason = _template_problem("heading", heading, HEADING_FIELDS)
    if reason:
        return reason
    # The next cut finds where to insert, and whether this release is already
    # written, by recognising version headings. A heading that does not lead
    # with the version would be invisible to both: releases would stack in the
    # wrong order and a second cut of one version would not be refused.
    if heading_version(heading.format_map(_SAMPLE_FIELDS)) is None:
        return (
            f"{DECLARATION_KEY}: heading {heading!r} must start with the version, "
            "as `## {version}…` or `## [{version_no_prefix}]…`, so the next cut can recognise it"
        )
    return None


def _parse_types(raw: str) -> tuple[tuple[tuple[str, str], ...], str | None]:
    """``types: {feature: Added, fix: Fixed}`` — one flow mapping on one line.

    One line because the block reader trims indentation, so a nested mapping
    cannot be read back; a subheading therefore cannot hold `,`, `{` or `}`.
    """
    text = raw.strip()
    if not (text.startswith("{") and text.endswith("}")):
        return (), f"{DECLARATION_KEY}: types must be one flow mapping, e.g. `types: {{feature: Added, fix: Fixed}}`"
    pairs: list[tuple[str, str]] = []
    for item in filter(None, (part.strip() for part in text[1:-1].split(","))):
        kind, sep, heading = item.partition(":")
        kind, heading = kind.strip(), unquote_scalar(heading.strip())
        if not sep or not heading or "{" in heading or "}" in heading:
            return (), f"{DECLARATION_KEY}: types item {item!r} is not `type: Subheading`"
        if kind not in change_fragments.TYPES:
            return (), f"{DECLARATION_KEY}: types names {kind!r}, not a fragment type ({', '.join(change_fragments.TYPES)})"
        if any(kind == seen for seen, _ in pairs):
            return (), f"{DECLARATION_KEY}: types maps {kind!r} twice"
        pairs.append((kind, heading))
    if not pairs:
        return (), f"{DECLARATION_KEY}: types is empty"
    return tuple(pairs), None


# --- versions and headings ---------------------------------------------------


def _bare(version: str) -> str:
    return version[1:] if version.startswith("v") else version


def heading_version(line: str) -> str | None:
    """The version a ``## `` heading leads with, without its ``v``, else ``None``.

    The first token is read once enclosing ``[ ]`` and one leading ``v`` are
    stripped, so ``## v3.7.2``, ``## [1.4.0] - 2026-10-25`` and
    ``## 1.4.0 (unreleased)`` lead with a version and ``## [Unreleased]`` does
    not. A ``###`` heading is never one: subsections of a past release must
    not attract the insert.
    """
    match = _H2_RE.match(line.rstrip("\r\n"))
    if not match:
        return None
    token = match.group(1)
    if token.startswith("[") and token.endswith("]"):
        token = token[1:-1]
    token = _bare(token)
    return token if _VERSION_RE.fullmatch(token) else None


def names_release(line: str, version: str) -> bool:
    """Whether ``line`` is a heading for exactly ``version``, prerelease included.

    Exact on purpose: a published ``-rc.1`` section is history, and must not
    block the cut of the release it previewed.
    """
    found = heading_version(line)
    return found is not None and found == _bare(version)


# --- the changelog as text ---------------------------------------------------


class DigestUnreadable(Exception):
    """The declared changelog exists but cannot be read as UTF-8 text."""


class MarkerMissing(Exception):
    """The declared marker line is not in the changelog."""


@dataclass(frozen=True)
class ChangelogText:
    """A changelog's text, held so that re-rendering it reproduces every byte.

    Each line keeps its own terminator, so a file mixing line endings comes back
    as it was; only lines this module adds use ``eol``. The byte-order mark is
    held apart so that heading recognition never sees it, and :meth:`render`
    puts it back. Rendered text is written with ``newline=""``, which encodes
    it to exactly the bytes it was read from.
    """

    bom: bool
    eol: str
    lines: tuple[str, ...]

    def render(self) -> str:
        return ("\ufeff" if self.bom else "") + "".join(self.lines)


def parse_changelog(data: bytes) -> ChangelogText:
    """:class:`ChangelogText` from a file's bytes. Raises :class:`DigestUnreadable`."""
    bom = data.startswith(b"\xef\xbb\xbf")
    try:
        text = (data[3:] if bom else data).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DigestUnreadable(f"not valid UTF-8 ({exc})") from exc
    lines = tuple(_LINE_RE.findall(text))
    eol = next((_terminator(line) for line in lines if _terminator(line)), "\n")
    return ChangelogText(bom=bom, eol=eol, lines=lines)


def read_changelog(path: Path) -> ChangelogText:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise DigestUnreadable(str(exc)) from exc
    return parse_changelog(data)


def _terminator(line: str) -> str:
    if line.endswith("\r\n"):
        return "\r\n"
    if line.endswith(("\n", "\r")):
        return line[-1]
    return ""


def insertion_index(text: ChangelogText, marker: str | None) -> int:
    """Where a new release section goes: below the marker, else above the newest release.

    With a marker, the line after the first line equal to it. Otherwise the
    first ``## `` heading that leads with a version, so a heading that does not
    (``## [Unreleased]``, ``## Contents``) stays above the new section. With no
    version heading at all, the end of the file.
    """
    if marker is not None:
        for index, line in enumerate(text.lines):
            if line.rstrip("\r\n") == marker:
                return index + 1
        raise MarkerMissing(marker)
    for index, line in enumerate(text.lines):
        if heading_version(line) is not None:
            return index
    return len(text.lines)


def insert_section(text: ChangelogText, index: int, section: list[str]) -> ChangelogText:
    """``text`` with ``section`` (lines without endings) spliced in before ``lines[index]``.

    Every existing line is kept byte for byte. Blank lines separate the section
    from its neighbours when they are not blank already. The one byte added
    outside the section is a terminator on a last line that lacked one, when the
    insert is at the end; the section's own last line then takes none, so the
    file still ends the way it did.
    """
    eol = text.eol
    before = list(text.lines[:index])
    after = list(text.lines[index:])
    unterminated_end = not after and bool(before) and not _terminator(before[-1])
    if unterminated_end:
        before[-1] = before[-1] + eol
    lead = [eol] if before and before[-1].strip() else []
    body = [line + eol for line in section]
    if after and after[0].strip():
        body.append(eol)
    if unterminated_end and body:
        body[-1] = body[-1][: -len(eol)]
    return ChangelogText(bom=text.bom, eol=eol, lines=tuple(before + lead + body + after))


# --- rendering -----------------------------------------------------------------


def ordered_notes(fragments: list[change_fragments.Fragment]) -> list[change_fragments.Fragment]:
    """The fragments that carry consumer text, newest first, ties by scope.

    Two stable sorts, scope ascending then date descending, so same-day scopes
    read alphabetically under the newest-first order. ``none:`` notes carry no
    text and so no entry.
    """
    with_text = [f for f in fragments if f.consumer_text]
    ordered = sorted(with_text, key=lambda f: f.scope or "")
    return sorted(ordered, key=lambda f: f.date or "", reverse=True)


def type_headings(decl: Declaration) -> list[tuple[str, str]]:
    """``(fragment type, subheading)`` for every type, in subsection order.

    A declared map comes first, in its own order. A type it leaves out falls
    into the fallback ``Changed`` subsection, so no note is dropped for want of
    a heading.
    """
    declared = list(decl.types) if decl.types else [
        (kind, _DEFAULT_TYPE_HEADINGS.get(kind, _FALLBACK_TYPE_HEADING)) for kind in _default_type_order()
    ]
    mapped = {kind for kind, _ in declared}
    return declared + [(kind, _FALLBACK_TYPE_HEADING) for kind in change_fragments.TYPES if kind not in mapped]


def _default_type_order() -> list[str]:
    preferred = [kind for kind in _DEFAULT_TYPE_HEADINGS if kind in change_fragments.TYPES]
    return preferred + [kind for kind in change_fragments.TYPES if kind not in preferred]


def _entry_lines(template: str, fragment: change_fragments.Fragment, *, bullet: bool) -> list[str]:
    rendered = template.format_map(
        {
            "note": fragment.consumer_text or "",
            "scope": fragment.scope or "",
            "type": fragment.type or "",
            "title": fragment.title or "",
        }
    )
    # Lines are kept verbatim: trailing whitespace can be a Markdown hard break,
    # and prawduct's own sections have always carried notes exactly as written.
    lines = rendered.splitlines()
    if not bullet:
        return lines
    # A bullet's continuation lines are indented under it, so a multi-line note
    # stays one list item; a blank line inside the note stays blank.
    return lines[:1] + [f"  {line}" if line.strip() else "" for line in lines[1:]]


def render_section(
    decl: Declaration,
    version: str,
    date: str,
    headline: str | None,
    fragments: list[change_fragments.Fragment],
) -> list[str]:
    """The release section as lines without endings: heading, headline, notes.

    ``version`` is the normalized ``vX.Y.Z``; ``date`` is ``YYYY-MM-DD``. With
    no notes (a release whose every fragment said ``none:``) the section ends
    after the headline, and with neither it is the heading alone, which is
    still true: the release shipped.
    """
    fields = {"version": version, "version_no_prefix": _bare(version), "date": date}
    out = [decl.heading.format_map(fields)]
    if headline and headline.strip():
        out += ["", *headline.strip().splitlines()]
    notes = ordered_notes(fragments)
    if not notes:
        return out
    out.append("")
    template = decl.entry_template
    if decl.layout == "paragraphs":
        for i, fragment in enumerate(notes):
            if i:
                out.append("")
            out += _entry_lines(template, fragment, bullet=False)
        return out
    if decl.layout == "bullets":
        for fragment in notes:
            out += _entry_lines(template, fragment, bullet=True)
        return out
    heading_of = dict(type_headings(decl))
    groups: dict[str, list[str]] = {}
    for _kind, sub in type_headings(decl):
        groups.setdefault(sub, [])
    for fragment in notes:
        groups.setdefault(heading_of.get(fragment.type or "", _FALLBACK_TYPE_HEADING), []).extend(
            _entry_lines(template, fragment, bullet=True)
        )
    first = True
    for sub, lines in groups.items():
        if not lines:
            continue
        if not first:
            out.append("")
        out += [f"### {sub}", "", *lines]
        first = False
    return out


def release_file_rel(version: str) -> str:
    """The release file's repo-relative path for the normalized ``version``."""
    return f"{RELEASES_DIR_REL}/{version}.md"
