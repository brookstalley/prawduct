"""One file per change: reading and validating `.prawduct/changes/<scope>.md`.

A branch records its change as one new file named for its scope, so two branches
never edit the same file and the change record merges without a union driver.
This module is the **single owner** of that format: no other module parses a
fragment, and readers ask it rather than knowing the layout.

A fragment is YAML-style frontmatter, a narrative, and a required consumer note::

    ---
    schema: 1
    type: fix
    scope: backlog-file-path
    date: 2026-10-17
    title: backlog file writes only to its own repo
    closes: [brookstalley/prawduct#1004, BKL-6J2X]
    ---
    What changed and why, naming every chunk shipped. Subheadings use ``###``.

    ## Consumer note
    What a user of the plugin needs to know, or exactly one line
    ``none: <reason>`` when there is nothing to tell them.

Every file in the directory is release-pending: the release cut moves a shipped
fragment's content into the change-log archive and removes the file, so a
``release`` key never appears here and is refused when it does.

The persisted schema answers a fixed set of consumer questions, and a key exists
only because one of them asks it: which scopes are pending, which plan a scope
belongs to, what a release tells its consumers, which backlog items a change
closes, which earlier scope a change reopens, and whether a newer plugin wrote
the file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date as _date
from pathlib import Path

from . import change_log as change_log_mod
from . import plan_index
from .backlog import ids

FRAGMENT_DIR_REL = ".prawduct/changes"

#: The schema version this plugin writes and reads. A fragment declaring a higher
#: one was written by a newer plugin and is refused rather than misread.
SCHEMA_VERSION = 1

#: The closed set of change types. Synonyms in the legacy log (`feat`, `bugfix`,
#: `improvement`) are normalised by the migration, never accepted here.
TYPES = ("feature", "fix", "chore", "docs", "refactor", "perf", "governance")

REQUIRED_KEYS = ("schema", "type", "scope", "date", "title")
OPTIONAL_KEYS = ("closes", "reopens")

CONSUMER_NOTE_HEADING = "## Consumer note"

# A scope is also a filename stem, so it must be a safe path component on every
# platform: lowercase, digits and hyphens, starting with a letter or digit.
_SCOPE_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
_KEY_LINE_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*):(.*)")
_NONE_RE = re.compile(r"none:(.*)", re.IGNORECASE)
# `date.fromisoformat` accepts compact and week forms from Python 3.11 on, so the
# shape is pinned first: the archive header is always `YYYY-MM-DD`.
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass(frozen=True)
class Problem:
    """One reason a fragment is refused: a stable code and what it found."""

    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


class FragmentError(ValueError):
    """The file cannot be read as a fragment at all, so no field can be checked."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.problem = Problem(code, detail)


@dataclass(frozen=True)
class Fragment:
    """A parsed fragment. Field values are as written; validation is separate."""

    filename_stem: str
    keys: dict[str, str | tuple[str, ...]]
    duplicate_keys: tuple[str, ...]
    narrative: str
    consumer_note: str | None
    consumer_note_headings: int
    body_h2_lines: tuple[str, ...]

    def _scalar(self, key: str) -> str | None:
        value = self.keys.get(key)
        return value if isinstance(value, str) else None

    @property
    def scope(self) -> str | None:
        return self._scalar("scope")

    @property
    def type(self) -> str | None:
        return self._scalar("type")

    @property
    def date(self) -> str | None:
        return self._scalar("date")

    @property
    def title(self) -> str | None:
        return self._scalar("title")

    @property
    def reopens(self) -> str | None:
        return self._scalar("reopens")

    @property
    def closes(self) -> tuple[str, ...]:
        value = self.keys.get("closes")
        return value if isinstance(value, tuple) else ()

    @property
    def none_reason(self) -> str | None:
        """The reason given by a ``none: <reason>`` consumer note, else ``None``."""
        if self.consumer_note is None:
            return None
        match = _NONE_RE.fullmatch(self.consumer_note.strip())
        return match.group(1).strip() if match else None

    @property
    def consumer_text(self) -> str | None:
        """The note's text for consumers, or ``None`` when it is absent or ``none:``."""
        if self.consumer_note is None or not self.consumer_note.strip():
            return None
        if _NONE_RE.fullmatch(self.consumer_note.strip()):
            return None
        return self.consumer_note.strip()


@dataclass(frozen=True)
class FragmentFile:
    """One file in the fragment directory and what reading it found."""

    path: Path
    fragment: Fragment | None
    problems: tuple[Problem, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return self.fragment is not None and not self.problems


def _strip_comment(raw: str) -> str:
    """Drop a trailing ``# comment``, YAML's way: only after whitespace.

    A bare ``#`` is part of the value, which is what lets ``owner/repo#1004``
    survive. The plan reader treats any ``#`` as a comment, which is right for the
    values it reads and would truncate every issue reference here.
    """
    in_quote: str | None = None
    for i, ch in enumerate(raw):
        if in_quote:
            if ch == in_quote:
                in_quote = None
        elif ch in ("'", '"'):
            in_quote = ch
        elif ch == "#" and (i == 0 or raw[i - 1] in (" ", "\t")):
            return raw[:i]
    return raw


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _parse_value(raw: str) -> str | tuple[str, ...]:
    value = _strip_comment(raw).strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return ()
        return tuple(_unquote(item.strip()) for item in inner.split(","))
    return _unquote(value)


def parse_fragment(text: str, *, filename: str) -> Fragment:
    """Split a fragment into frontmatter keys, narrative and consumer note.

    Raises :class:`FragmentError` only when there is no frontmatter block or a
    line in it is not ``key: value``, because then no field can be trusted.
    Everything else is collected for :func:`validate_fragment` to judge, so one
    run reports every problem rather than the first.
    """
    span = plan_index.frontmatter_span(text)
    if span is None:
        raise FragmentError(
            "no-frontmatter",
            "the file must open with a `---` frontmatter block closed by a second `---`",
        )
    lines = text.splitlines()
    keys: dict[str, str | tuple[str, ...]] = {}
    duplicates: list[str] = []
    for number, line in enumerate(lines[span[0] + 1 : span[1]], start=span[0] + 2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[:1] in (" ", "\t"):
            raise FragmentError(
                "bad-frontmatter-line",
                f"line {number} is indented; fragment frontmatter is flat `key: value` lines",
            )
        match = _KEY_LINE_RE.fullmatch(line.rstrip())
        if not match:
            raise FragmentError(
                "bad-frontmatter-line", f"line {number} is not `key: value`: {line.strip()!r}"
            )
        key = match.group(1)
        if key in keys:
            duplicates.append(key)
            continue
        keys[key] = _parse_value(match.group(2))

    body_lines = lines[span[1] + 1 :]
    note_indices = [i for i, line in enumerate(body_lines) if line.rstrip() == CONSUMER_NOTE_HEADING]
    if note_indices:
        first = note_indices[0]
        narrative_lines = body_lines[:first]
        note_lines = body_lines[first + 1 :]
        if len(note_indices) > 1:
            note_lines = body_lines[first + 1 : note_indices[1]]
        consumer_note: str | None = "\n".join(note_lines).strip()
    else:
        narrative_lines = body_lines
        consumer_note = None
    h2_lines = tuple(
        line.rstrip()
        for line in body_lines
        if line.startswith("## ") and line.rstrip() != CONSUMER_NOTE_HEADING
    )
    return Fragment(
        filename_stem=Path(filename).stem,
        keys=keys,
        duplicate_keys=tuple(duplicates),
        narrative="\n".join(narrative_lines).strip(),
        consumer_note=consumer_note,
        consumer_note_headings=len(note_indices),
        body_h2_lines=h2_lines,
    )


def _closes_problems(values: tuple[str, ...]) -> list[Problem]:
    problems = []
    for value in values:
        if ids.is_pfx(value) and value == value.strip():
            continue
        normalized = ids.normalize_id(value)
        if normalized.ok and normalized.canonical == value:
            continue
        problems.append(
            Problem(
                "bad-closes",
                f"{value!r} is not a backlog item ID; write `owner/repo#N` for an issue "
                "or the markdown backlog's `PFX-XXXX`",
            )
        )
    return problems


def validate_fragment(fragment: Fragment) -> list[Problem]:
    """Every schema problem in ``fragment``, in a stable order. Empty means valid."""
    problems: list[Problem] = []
    keys = fragment.keys

    for key in fragment.duplicate_keys:
        problems.append(Problem("duplicate-key", f"`{key}` is set more than once"))
    if "release" in keys:
        problems.append(
            Problem(
                "released-fragment",
                "`release` is never written on a fragment: the release cut moves a shipped "
                "fragment into the archive, so every file here is pending",
            )
        )
    for key in keys:
        if key in change_log_mod.RETIRED_TAG_KEYS:
            problems.append(Problem("retired-key", f"`{key}` is retired and read by nothing"))
        elif key not in REQUIRED_KEYS and key not in OPTIONAL_KEYS and key != "release":
            problems.append(
                Problem(
                    "unknown-key",
                    f"`{key}` is not a fragment key; the keys are "
                    f"{', '.join(REQUIRED_KEYS + OPTIONAL_KEYS)}",
                )
            )
    for key in REQUIRED_KEYS:
        if key not in keys or keys[key] in ("", ()):
            problems.append(Problem("missing-key", f"`{key}` is required"))

    schema = keys.get("schema")
    if isinstance(schema, str) and schema:
        if not schema.isdigit() or int(schema) < 1:
            problems.append(Problem("bad-schema", f"`schema` must be a whole number, got {schema!r}"))
        elif int(schema) > SCHEMA_VERSION:
            problems.append(
                Problem(
                    "schema-ahead",
                    f"written by schema {schema}, and this plugin reads schema "
                    f"{SCHEMA_VERSION}; update the plugin rather than editing the fragment",
                )
            )

    kind = fragment.type
    if kind and kind not in TYPES:
        problems.append(Problem("bad-type", f"{kind!r} is not one of {', '.join(TYPES)}"))

    scope = fragment.scope
    if scope:
        if not _SCOPE_RE.fullmatch(scope):
            problems.append(
                Problem("bad-scope-slug", f"{scope!r} must be lowercase letters, digits and hyphens")
            )
        if scope != fragment.filename_stem:
            problems.append(
                Problem(
                    "scope-mismatch",
                    f"`scope: {scope}` must equal the filename stem {fragment.filename_stem!r}",
                )
            )

    when = fragment.date
    if when:
        try:
            if not _DATE_RE.fullmatch(when):
                raise ValueError(when)
            _date.fromisoformat(when)
        except ValueError:
            problems.append(Problem("bad-date", f"{when!r} is not a YYYY-MM-DD date"))

    for key in ("type", "scope", "date", "title", "reopens"):
        if isinstance(keys.get(key), tuple):
            problems.append(Problem("bad-value", f"`{key}` takes one value, not a list"))

    closes = keys.get("closes")
    if isinstance(closes, str):
        problems.append(Problem("bad-closes", "`closes` is a list: `closes: [owner/repo#N]`"))
    elif closes:
        problems.extend(_closes_problems(closes))

    reopens = fragment.reopens
    if "reopens" in keys and not reopens:
        problems.append(Problem("bad-reopens", "`reopens` names the scope this change reopens"))
    elif reopens and not _SCOPE_RE.fullmatch(reopens):
        problems.append(Problem("bad-reopens", f"{reopens!r} is not a scope"))

    if not fragment.narrative:
        problems.append(Problem("empty-narrative", "say what changed and why above the consumer note"))
    for line in fragment.body_h2_lines:
        problems.append(
            Problem(
                "h2-in-body",
                f"{line!r}: only `{CONSUMER_NOTE_HEADING}` is a `##` heading here; use `###`, "
                "because `##` starts a new entry once the fragment is archived",
            )
        )

    if fragment.consumer_note_headings == 0:
        problems.append(
            Problem(
                "missing-consumer-note",
                f"add `{CONSUMER_NOTE_HEADING}` with the text for consumers, "
                "or `none: <reason>` when there is nothing to tell them",
            )
        )
    elif fragment.consumer_note_headings > 1:
        problems.append(Problem("duplicate-consumer-note", f"`{CONSUMER_NOTE_HEADING}` appears more than once"))
    elif not fragment.consumer_note:
        problems.append(
            Problem("empty-consumer-note", "write the note, or `none: <reason>` when there is nothing to tell consumers")
        )
    elif _NONE_RE.fullmatch(fragment.consumer_note.strip()) and not fragment.none_reason:
        problems.append(Problem("empty-consumer-note", "`none:` needs a reason after it"))

    return problems


def read_fragment_file(path: Path) -> FragmentFile:
    """Read and validate one fragment file; never raises for a bad fragment."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return FragmentFile(path, None, (Problem("unreadable", str(exc)),))
    try:
        fragment = parse_fragment(text, filename=path.name)
    except FragmentError as exc:
        return FragmentFile(path, None, (exc.problem,))
    return FragmentFile(path, fragment, tuple(validate_fragment(fragment)))


def load_pending(root: Path) -> list[FragmentFile]:
    """Every fragment file under ``root``, sorted by filename. Each one is pending.

    Only ``*.md`` files are fragments, so a ``.gitkeep`` that holds the directory
    open is not one. A missing directory is an empty pending set.
    """
    directory = root / FRAGMENT_DIR_REL
    if not directory.is_dir():
        return []
    return [read_fragment_file(path) for path in sorted(directory.glob("*.md"))]


def render_entry(fragment: Fragment, *, release: str | None = None) -> str:
    """The fragment as a block in the change-log archive's existing grammar.

    The archive keeps its format, so its parser and invariants are unchanged:
    ``## date: title``, one tag line, then the body. ``closes`` and ``reopens``
    ride the tag line as keys the legacy parser preserves, and the consumer note
    follows the narrative under a bold label rather than a heading, because a
    ``##`` would start a new archive entry.
    """
    tags = [f"type={fragment.type}", f"scope={fragment.scope}"]
    if fragment.closes:
        tags.append("closes=" + ",".join(fragment.closes))
    if fragment.reopens:
        tags.append(f"reopens={fragment.reopens}")
    if release is not None:
        if not change_log_mod.RELEASE_VALUE_RE.match(release):
            raise ValueError(f"release must be a version like v1.2.3, got {release!r}")
        tags.append(f"release={release}")
    note = fragment.consumer_note or ""
    return (
        f"## {fragment.date}: {fragment.title}\n\n"
        f"<!-- prawduct: {' | '.join(tags)} -->\n\n"
        f"{fragment.narrative}\n\n"
        f"**Consumer note:**\n\n{note}\n"
    )


def render_consumer_section(fragments: list[Fragment]) -> str:
    """The `plugin/CHANGELOG.md` paragraphs for ``fragments`` that have consumer text.

    Newest first, ties broken by scope, so the output is stable. ``none:`` notes
    contribute nothing here; :func:`none_reasons` lists them for the operator.
    """
    with_text = [f for f in fragments if f.consumer_text]
    # Two stable sorts: scope ascending, then date descending, so same-day scopes
    # read alphabetically under the newest-first order.
    ordered = sorted(with_text, key=lambda f: f.scope or "")
    ordered = sorted(ordered, key=lambda f: f.date or "", reverse=True)
    return "\n\n".join(f"**`{f.scope}`**: {f.consumer_text}" for f in ordered)


def none_reasons(fragments: list[Fragment]) -> list[tuple[str, str]]:
    """``(scope, reason)`` for every fragment whose consumer note is ``none:``."""
    return sorted(
        (f.scope or "", f.none_reason) for f in fragments if f.none_reason is not None
    )
