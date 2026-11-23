"""Late-requirement records — the one reader (#1034).

A requirement that surfaces mid-build is captured where the product already
keeps its requirements: a ``## Late requirements`` section in the governing
requirements artifact (the one ``prawduct-hook jurisdiction`` ranks first), or
in the active build plan when the product has none. One list item per record:

    - **LR-<n>** (<YYYY-MM-DD> · why: <reason> · surfaced: <chunk id or short sha>) — <sentence>.

``reason`` is one of :data:`WHY`. A record a later change contradicts keeps its
line and gains a trailing ``SUPERSEDED <date>: <reason>``; it is never edited to
match the code. The impact walk sits under the record as indented sub-items,
which are not records and are not read here.

**One parser, several consumers.** ``record_lint``'s ``late-requirement-record``
check reads records through :func:`parse` today; binding and measurement will
read them through it later, so "what a record is" has one answer. A malformed
item is still returned, with its ``problems`` named, because the lint's job is
to say what is wrong with it and a reader that dropped it would make a broken
record indistinguishable from an absent one.

**No index.** :func:`scan` finds the files holding the section with one
``git grep`` and parses only those, so its cost follows the number of records,
and a product that has never captured one pays a single search. The lint calls
it only when a change added a line inside the section.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from pathlib import Path

from . import evidence

#: Why the requirement is late, in the governance ROI study's terms: learned
#: from operating it, a new consumer, an owner change, a discovered constraint.
WHY = frozenset({"operating", "new-consumer", "owner-change", "constraint"})

#: The fields every record carries besides its id. ``statement`` is the one
#: sentence after the separator.
REQUIRED = ("date", "why", "surfaced", "statement")

SHAPE = (
    "`- **LR-<n>** (<YYYY-MM-DD> · why: <reason> · surfaced: <chunk id or short sha>)"
    " — <sentence>.`"
)

_HEADING_RE = re.compile(r"^##[ \t]+late requirements[ \t]*#*[ \t]*$", re.IGNORECASE)
#: A heading that closes the section: one at its level or above.
_CLOSER_RE = re.compile(r"^#{1,2}[ \t]")
_FENCE_RE = re.compile(r"^[ \t]{0,3}(```|~~~)")
#: A TOP-LEVEL list item — the record. Indented items are the impact walk.
_ITEM_RE = re.compile(r"^[-*+][ \t]+(?P<body>.*)$")
_ID_RE = re.compile(r"^\*\*(?P<id>LR-\d+)\*\*[ \t]*(?P<rest>.*)$")
_META_RE = re.compile(r"^\((?P<meta>[^)]*)\)[ \t]*(?P<rest>.*)$")
_SEPARATOR_RE = re.compile(r"^(?:—|–|--?)[ \t]*(?P<rest>.*)$")
_SUPERSEDED_RE = re.compile(r"[ \t]+SUPERSEDED\b(?P<tail>.*)$")
_SUPERSEDED_TAIL_RE = re.compile(r"^[ \t]+(?P<date>\d{4}-\d{2}-\d{2}):[ \t]*(?P<reason>\S.*)$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_KEYED_RE = re.compile(r"^(?P<key>[a-z][a-z-]*):[ \t]*(?P<value>.*)$")


class ScanError(Exception):
    """The product could not be searched — an unread product is not an empty one."""


@dataclass(frozen=True)
class Supersession:
    date: str
    reason: str


@dataclass(frozen=True)
class LateReq:
    """One record as written. A field the item does not carry is ``None`` and
    is named in ``problems``; a well-formed record has no problems."""

    id: "str | None"
    date: "str | None"
    why: "str | None"
    surfaced: "str | None"
    statement: "str | None"
    superseded: "Supersession | None"
    path: "str | None"
    line: int
    problems: "tuple[str, ...]" = ()

    @property
    def where(self) -> str:
        return f"{self.path}:{self.line}" if self.path else f"line {self.line}"


def section_ranges(text: str) -> "list[tuple[int, int]]":
    """``(first, last)`` 1-based line spans of each ``## Late requirements``
    section: its heading through the line before the next heading at level 2 or
    above, or the end of the text. A heading inside a fenced block is an example,
    not a section, and neither opens nor closes one."""
    ranges: list[tuple[int, int]] = []
    start: "int | None" = None
    in_fence = False
    lines = text.splitlines()
    for num, line in enumerate(lines, start=1):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if start is not None and _CLOSER_RE.match(line):
            ranges.append((start, num - 1))
            start = None
        if start is None and _HEADING_RE.match(line):
            start = num
    if start is not None:
        ranges.append((start, len(lines)))
    return ranges


def record_lines(text: str) -> "list[tuple[int, str]]":
    """``(line, text)`` of every top-level list item inside a section, fenced
    lines excluded — the lines :func:`parse` reads as records."""
    lines = text.splitlines()
    out: list[tuple[int, str]] = []
    for first, last in section_ranges(text):
        in_fence = False
        for num in range(first + 1, last + 1):
            line = lines[num - 1]
            if _FENCE_RE.match(line):
                in_fence = not in_fence
                continue
            if not in_fence and _ITEM_RE.match(line):
                out.append((num, line))
    return out


def parse_line(line: str, *, path: "str | None" = None, line_num: int = 0) -> LateReq:
    """One top-level item, parsed against the record shape."""
    item = _ITEM_RE.match(line)
    body = item.group("body").strip() if item else line.strip()
    head = _ID_RE.match(body)
    if head is None:
        return LateReq(None, None, None, None, None, None, path, line_num,
                       (f"not a late-requirement record — expected {SHAPE}",))
    rec_id, rest = head.group("id"), head.group("rest").strip()
    problems: list[str] = []
    fields: dict = {"date": None, "why": None, "surfaced": None, "statement": None}

    meta = _META_RE.match(rest)
    if meta is None:
        problems.append(f"{rec_id} has no `(<date> · why: … · surfaced: …)` group — expected {SHAPE}")
    else:
        rest = meta.group("rest").strip()
        for part in (p.strip() for p in meta.group("meta").split("·")):
            if not part:
                continue
            keyed = _KEYED_RE.match(part)
            if keyed and keyed.group("key") in ("why", "surfaced"):
                fields[keyed.group("key")] = keyed.group("value").strip() or None
            elif _DATE_RE.match(part):
                fields["date"] = part
            elif fields["date"] is None and re.match(r"^\d", part):
                fields["date"] = part  # graded below as an invalid date

    superseded: "Supersession | None" = None
    marker = _SUPERSEDED_RE.search(rest)
    if marker is not None:
        tail = _SUPERSEDED_TAIL_RE.match(marker.group("tail"))
        if tail is None or not _valid_date(tail.group("date")):
            problems.append(f"{rec_id}'s SUPERSEDED marker is not `SUPERSEDED <YYYY-MM-DD>: <reason>`")
        else:
            superseded = Supersession(tail.group("date"), tail.group("reason").strip())
        rest = rest[: marker.start()].rstrip()

    if meta is not None:
        sep = _SEPARATOR_RE.match(rest)
        statement = sep.group("rest").strip() if sep else ""
        fields["statement"] = statement or None
        if fields["date"] is None:
            problems.append(f"{rec_id} is missing its date")
        elif not _valid_date(fields["date"]):
            problems.append(f"{rec_id}'s date `{fields['date']}` is not a YYYY-MM-DD date")
        for key in ("why", "surfaced"):
            if fields[key] is None:
                problems.append(f"{rec_id} is missing `{key}`")
        if fields["why"] is not None and fields["why"] not in WHY:
            problems.append(
                f"{rec_id}'s `why: {fields['why']}` is not one of {', '.join(sorted(WHY))}"
            )
        if fields["statement"] is None:
            problems.append(f"{rec_id} is missing its one-sentence requirement after ` — `")

    return LateReq(rec_id, fields["date"], fields["why"], fields["surfaced"],
                   fields["statement"], superseded, path, line_num, tuple(problems))


def parse(text: str, path: "str | None" = None) -> "list[LateReq]":
    """Every record in ``text``'s ``## Late requirements`` sections, in order."""
    return [parse_line(line, path=path, line_num=num) for num, line in record_lines(text)]


def scan(project_dir: Path, tree: "str | None" = None) -> "list[LateReq]":
    """Every record in the product, sorted by path then line.

    ``tree`` reads a captured tree (paths repo-root relative, as ``git show``
    takes them); ``None`` reads the working tree, untracked files included and
    ignored ones not. Raises :class:`ScanError` when git cannot search, because
    an unread product must not read as one with no records."""
    pattern = r"^##[[:space:]]+late requirements[[:space:]]*#*[[:space:]]*$"
    if tree is None:
        args = ("grep", "-l", "-I", "-i", "-E", "--untracked", "-e", pattern, "--", "*.md")
    else:
        args = ("grep", "-l", "-I", "-i", "-E", "--full-name", "-e", pattern, tree, "--", "*.md")
    rc, out, err = evidence.run_git(project_dir, "-c", "core.quotepath=false", *args)
    if rc == 1 and not err:
        return []
    if rc != 0:
        raise ScanError(err or f"git grep exited {rc}")
    found: list[LateReq] = []
    for raw in sorted(p for p in out.splitlines() if p):
        rel = raw[len(tree) + 1:] if tree is not None and raw.startswith(f"{tree}:") else raw
        text = read_at(project_dir, rel, tree)
        if text is None:
            raise ScanError(f"could not read {rel}")
        found.extend(parse(text, path=rel))
    return found


def read_at(project_dir: Path, rel: str, tree: "str | None") -> "str | None":
    """``rel``'s text in ``tree`` (the working tree when ``None``), or ``None``
    when absent or unreadable. Unstripped, so line numbers match a diff's."""
    if tree is not None:
        rc, out, _err = evidence.run_git(project_dir, "show", f"{tree}:{rel}", strip=False)
        return out if rc == 0 else None
    try:
        return (project_dir / rel).read_text(encoding="utf-8", errors="surrogateescape")
    except OSError:
        return None


def _valid_date(value: str) -> bool:
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return bool(_DATE_RE.match(value))
