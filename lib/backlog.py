"""Structured parser for ``.prawduct/backlog.md``.

The backlog is living triage markdown managed by the ``/prawduct:backlog`` skill.
Until now the only runtime reader was a textual line-count in :mod:`lib.briefing`;
every richer use (claim-filtering, stale detection, dedup, stage-aware pick, the
post-sync probes) needs to *parse* items, not regex the file. This module is that
substrate — the backlog's analogue of :mod:`lib.views` for the change-log.

Design mirrors ``lib/views.py``: a dataclass per item, a pure ``parse_backlog``
function, and small pure query helpers. No I/O coupling — callers read the file and
pass the text in — so the parser is trivially testable and never blocks a session.

Item shape (see ``documentation/backlog-system-requirements.md`` §4.1):

    - **[PFX-XXXX]** One-line title
      `effort: M · impact: M · area: critic · source: builder · added: 2026-06-08 · status: open`

      Optional free-form body.

The metadata bar is a single backticked, ``·``-delimited line of ``key: value``
pairs (distinct from the change-log's ``|``-delimited ``key=value`` tag line).
Legacy items (a top-level bullet with no metadata bar) remain valid and parse with
an empty ``metadata`` dict — tools treat them as ``area: untagged``, rank them
lower, and never drop them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# A heading line at any level — the section an item falls under is the most recent
# one of these seen above it. Matching ANY level (not just ``##``) mirrors the
# behavior the briefing's count relied on, so the section model is byte-identical.
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$")

# A top-level backlog item: a bullet at column 0. Body bullets are indented, so
# column-0 ``- `` is the item boundary (matches the briefing's count unit).
ITEM_RE = re.compile(r"^- (.+)$")

# An item ID ``[PFX-XXXX]``. Lenient on purpose: the canonical form is 2–3 upper
# letters + ``-`` + 4 base36 chars, but legacy/hand-written items use looser ids
# (e.g. ``[A-1]``), and we want to surface whatever ID-shaped token is present
# rather than silently treat the item as unidentified.
ID_RE = re.compile(r"\[([A-Za-z][A-Za-z0-9]*-[A-Za-z0-9]+)\]")

# A metadata bar: a backtick-wrapped line of ``·``-separated ``key: value`` pairs.
METADATA_BAR_RE = re.compile(r"^`(.+)`$")

# Section headers whose items are NOT "pending" work — the resolved/archive end of
# the lifecycle. Kept as the briefing's original word-set so the pending count is
# preserved exactly across the parser rewrite (Open + Promoted count; Archive and
# any Resolved/Done/Completed section do not).
RESOLVED_SECTION_WORDS = ("resolved", "done", "completed", "archive")

# Comma-separated metadata values (the parser splits these into lists on access).
_LIST_KEYS = ("related", "refs")


def parse_metadata_bar(text: str) -> dict[str, str]:
    """Parse the body of a metadata bar (the text *inside* the backticks).

    ``·``-delimited ``key: value`` pairs. Everything after the first ``:`` in a
    segment is the value (so values may contain spaces, e.g.
    ``accepted-by: @brooks (2026-06-08)``). Unknown keys are preserved verbatim so
    new keys can be read without a schema bump. Returns ``{}`` for an empty bar.
    """
    meta: dict[str, str] = {}
    for segment in text.split("·"):
        segment = segment.strip()
        if ":" not in segment:
            continue
        key, value = segment.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key:
            meta[key] = value
    return meta


@dataclass
class BacklogItem:
    """One backlog item — a top-level bullet plus its metadata bar and body."""

    title: str
    section: str  # raw heading text the item falls under (e.g. "Open")
    item_id: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    body: str = ""
    struck: bool = False  # title wrapped in ~~…~~ (a non-canonical "done" marker)
    line_number: int = 0  # 1-indexed line of the bullet

    @property
    def is_legacy(self) -> bool:
        """True when the item has no metadata bar (pre-structured item)."""
        return not self.metadata

    @property
    def status(self) -> str | None:
        return self.metadata.get("status")

    @property
    def area(self) -> str:
        return self.metadata.get("area", "untagged")

    @property
    def accepted_by(self) -> str | None:
        """The claim holder (``accepted-by``), or ``None`` if unclaimed.

        An optional trailing ``(timestamp)`` is informational only — claims do
        NOT auto-expire (requirements §3 D10), so the timestamp never drives
        filtering. Returned verbatim.
        """
        value = self.metadata.get("accepted-by")
        return value or None

    @property
    def is_claimed(self) -> bool:
        return self.accepted_by is not None

    @property
    def stage(self) -> str | None:
        """Lifecycle stage (``idea``/``research``/``requirements``/``design``/``ready``), or ``None``."""
        value = self.metadata.get("stage")
        return value or None

    @property
    def refs(self) -> list[str]:
        """Governing-artifact references (``refs``), split on commas."""
        return _split_list(self.metadata.get("refs"))

    @property
    def related(self) -> list[str]:
        """Related item IDs (``related``), split on commas."""
        return _split_list(self.metadata.get("related"))


def _split_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _is_resolved_section(header: str) -> bool:
    """True for the archive/resolved end of the lifecycle (not pending work)."""
    lower = header.lower()
    return any(word in lower for word in RESOLVED_SECTION_WORDS)


@dataclass
class Backlog:
    """A parsed backlog — the ordered list of items, with query helpers."""

    items: list[BacklogItem] = field(default_factory=list)

    def in_section(self, name: str) -> list[BacklogItem]:
        """Items whose section header equals ``name`` (case-insensitive)."""
        target = name.strip().lower()
        return [i for i in self.items if i.section.strip().lower() == target]

    def open_items(self) -> list[BacklogItem]:
        return self.in_section("Open")

    def promoted_items(self) -> list[BacklogItem]:
        return self.in_section("Promoted")

    def archived_items(self) -> list[BacklogItem]:
        return self.in_section("Archive")

    def pending_items(self) -> list[BacklogItem]:
        """Items that count as outstanding work for the session briefing.

        Replicates the briefing's original count semantics exactly: a non-struck
        item with a non-empty title, in a section that is NOT resolved/archive.
        This includes both ``## Open`` and ``## Promoted`` (only the resolved end
        is excluded), preserving the pre-parser count.
        """
        return [
            i
            for i in self.items
            if i.title and not i.struck and not _is_resolved_section(i.section)
        ]

    def items_by_area(self) -> dict[str, list[BacklogItem]]:
        grouped: dict[str, list[BacklogItem]] = {}
        for item in self.items:
            grouped.setdefault(item.area, []).append(item)
        return grouped


def _parse_title_line(raw: str) -> tuple[str | None, str, bool]:
    """From a bullet's text (after ``- ``) return ``(item_id, title, struck)``."""
    struck = "~~" in raw
    id_match = ID_RE.search(raw)
    item_id = id_match.group(1) if id_match else None
    # Title is the human text: strip bold markers and strikethrough tildes so the
    # briefing's display string matches the old ``stripped[2:].strip()`` behavior.
    title = raw.replace("~~", "").replace("**", "").strip()
    return item_id, title, struck


def parse_backlog(content: str) -> Backlog:
    """Parse backlog markdown into a :class:`Backlog`.

    Section = the most recent heading line. Items = column-0 ``- `` bullets
    outside fenced code blocks and HTML comment blocks. An item's metadata bar is
    the first backtick-wrapped line in its body; its body is the indented/blank
    run up to the next bullet or heading.
    """
    items: list[BacklogItem] = []
    lines = content.splitlines()
    section = ""
    in_code_block = False
    in_comment = False
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # Fenced code blocks and HTML comment blocks never contain items.
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            i += 1
            continue
        if in_code_block:
            i += 1
            continue
        if "<!--" in stripped and "-->" not in stripped:
            in_comment = True
            i += 1
            continue
        if in_comment:
            if "-->" in stripped:
                in_comment = False
            i += 1
            continue

        heading = HEADING_RE.match(line)
        if heading:
            section = heading.group(1).strip()
            i += 1
            continue

        item_match = ITEM_RE.match(line)
        if item_match:
            item_id, title, struck = _parse_title_line(item_match.group(1))
            item = BacklogItem(
                title=title,
                section=section,
                item_id=item_id,
                struck=struck,
                line_number=i + 1,
            )
            # Collect the body: lines until the next column-0 bullet or heading.
            # The body may itself contain a fenced code block (the item format
            # permits code blocks — requirements §4.1), so track fence state and
            # only treat a bullet/heading as a boundary when OUTSIDE a fence —
            # otherwise a ``## x`` or ``- y`` line inside a body fence would
            # truncate the item. Fence lines are kept as body.
            body_lines: list[str] = []
            j = i + 1
            body_in_fence = False
            while j < n:
                nxt = lines[j]
                if nxt.strip().startswith("```"):
                    body_in_fence = not body_in_fence
                    body_lines.append(nxt)
                    j += 1
                    continue
                if not body_in_fence and (ITEM_RE.match(nxt) or HEADING_RE.match(nxt)):
                    break
                body_lines.append(nxt)
                j += 1
            _attach_metadata_and_body(item, body_lines)
            items.append(item)
            i = j
            continue

        i += 1

    return Backlog(items=items)


def _attach_metadata_and_body(item: BacklogItem, body_lines: list[str]) -> None:
    """Split an item's raw body lines into its metadata bar + free-form body."""
    bar_index = None
    for idx, raw in enumerate(body_lines):
        stripped = raw.strip()
        if not stripped:
            continue
        bar_match = METADATA_BAR_RE.match(stripped)
        if bar_match and ":" in bar_match.group(1):
            item.metadata = parse_metadata_bar(bar_match.group(1))
            bar_index = idx
        # First non-blank body line settles whether a bar is present.
        break
    remaining = body_lines if bar_index is None else body_lines[bar_index + 1 :]
    item.body = "\n".join(remaining).strip()
