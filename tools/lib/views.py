"""Derived-view builders for the prawduct work-log canonical store.

When `.prawduct/project-state.yaml` has `views_enabled: true`, the build-plan
`## Status` block becomes a derived view of `.prawduct/change-log.md` tagged
entries — `product-hook regen-views` rewrites the checkboxes from
`status=shipped` tags. Chunk titles, the `## Status` heading, the introductory
HTML comment, and the freeform `Context:` line are author-curated; regen never
touches them.

Tagged-entry format (in change-log.md, on a line after each ``## YYYY-MM-DD:``
header — blank lines between are tolerated):

    <!-- prawduct: chunks=00,01,02 | release=v1.3.18 | status=shipped | scope=v1.4 -->

Recognized keys:

* ``chunks``  comma-separated chunk IDs (zero-padded, matching build-plan headers)
* ``release`` version string (used by release-notes view, Chunk 06)
* ``status``  ``shipped`` | ``in-progress`` | ``deferred``
* ``scope``   rollup identifier, e.g., ``v1.4``

Entries without a tag line are ignored — untagged historical entries coexist
with tagged ones. Only chunks with a ``status=shipped`` tag flip to ``[x]``;
all other Chunk lines flip to ``[ ]`` so the view is fully derived.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


TAG_LINE_RE = re.compile(r"<!--\s*prawduct:\s*(.+?)\s*-->")
H2_RE = re.compile(r"^##\s+(.+?)\s*$")
CHUNK_LINE_RE = re.compile(
    r"^(?P<prefix>\s*-\s+)\[(?P<state>[ xX])\](?P<rest>\s+Chunk\s+(?P<id>[A-Za-z0-9_-]+):.*)$"
)


@dataclass
class ChangeLogEntry:
    """A change-log entry with optional tagged metadata."""

    title: str
    tags: dict[str, object] = field(default_factory=dict)
    line_number: int = 0  # 1-indexed line of the H2 header

    @property
    def shipped_chunks(self) -> list[str]:
        """Chunk IDs marked shipped by this entry, or []."""
        if self.tags.get("status") != "shipped":
            return []
        chunks = self.tags.get("chunks")
        if isinstance(chunks, list):
            return [c for c in chunks if isinstance(c, str)]
        return []


def parse_tag_line(tag_body: str) -> dict[str, object]:
    """Parse the body of a tag-line (between ``prawduct:`` and ``-->``).

    Pipe-delimited ``key=value`` pairs. ``chunks`` is split on commas into a list;
    other keys are kept as plain strings. Unknown keys are preserved as-is so
    future views can read them without a schema bump.
    """
    tags: dict[str, object] = {}
    for part in tag_body.split("|"):
        part = part.strip()
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        k = k.strip()
        v = v.strip()
        if not k:
            continue
        if k == "chunks":
            tags[k] = [c.strip() for c in v.split(",") if c.strip()]
        else:
            tags[k] = v
    return tags


def parse_change_log(content: str) -> list[ChangeLogEntry]:
    """Parse change-log markdown into a list of entries.

    An entry is ``## YYYY-MM-DD: title`` followed (after up to a few blank
    lines) by ``<!-- prawduct: key=value | ... -->``. The tag line, if present,
    must appear before the next non-blank content line under the H2.
    """
    entries: list[ChangeLogEntry] = []
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        m = H2_RE.match(lines[i])
        if not m:
            i += 1
            continue
        entry = ChangeLogEntry(title=m.group(1), line_number=i + 1)
        j = i + 1
        while j < len(lines):
            stripped = lines[j].strip()
            if not stripped:
                j += 1
                continue
            tag_match = TAG_LINE_RE.search(lines[j])
            if tag_match:
                entry.tags = parse_tag_line(tag_match.group(1))
            # First non-blank line settles the question — tag line or not.
            break
        entries.append(entry)
        i += 1
    return entries


def collect_shipped_chunks(entries: list[ChangeLogEntry]) -> set[str]:
    """Aggregate shipped chunk IDs across all entries."""
    shipped: set[str] = set()
    for entry in entries:
        shipped.update(entry.shipped_chunks)
    return shipped


def extract_status_section(content: str) -> tuple[int, int, list[str]]:
    """Find the ``## Status`` section.

    Returns ``(start_idx, end_idx_exclusive, section_lines)``. Section runs from
    the ``## Status`` line to (but not including) the next ``## `` H2 — matching
    the conventional build-plan layout. Returns ``(-1, -1, [])`` if absent.
    """
    lines = content.splitlines()
    start = -1
    for i, line in enumerate(lines):
        if line.startswith("## Status"):
            start = i
            break
    if start < 0:
        return (-1, -1, [])
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    return (start, end, lines[start:end])


def regenerate_status_section(
    section_lines: list[str], shipped_chunks: set[str]
) -> tuple[list[str], list[tuple[str, str, str]]]:
    """Rewrite Chunk checkbox lines from the shipped-chunks set.

    Returns ``(new_lines, changes)`` where each change is
    ``(chunk_id, old_state, new_state)`` with ``state`` in ``{" ", "x"}``.
    Non-chunk lines (the ``## Status`` heading, HTML comments, blanks, the
    ``Context:`` line) pass through unchanged. Order is preserved.
    """
    out: list[str] = []
    changes: list[tuple[str, str, str]] = []
    for line in section_lines:
        m = CHUNK_LINE_RE.match(line)
        if not m:
            out.append(line)
            continue
        chunk_id = m.group("id")
        current = m.group("state")
        new_state = "x" if chunk_id in shipped_chunks else " "
        if current.lower() != new_state:
            changes.append((chunk_id, current, new_state))
        out.append(f"{m.group('prefix')}[{new_state}]{m.group('rest')}")
    return out, changes


def build_status_view(
    change_log_content: str, build_plan_content: str
) -> tuple[str | None, list[tuple[str, str, str]]]:
    """Produce updated build-plan content with regenerated Status section.

    Returns ``(new_content, changes)``. ``new_content`` is ``None`` when no
    checkbox flips were needed (idempotent no-op). ``changes`` is empty in
    that case.
    """
    entries = parse_change_log(change_log_content)
    shipped = collect_shipped_chunks(entries)
    start, end, section = extract_status_section(build_plan_content)
    if start < 0:
        return None, []
    new_section, changes = regenerate_status_section(section, shipped)
    if not changes:
        return None, []
    lines = build_plan_content.splitlines()
    new_lines = lines[:start] + new_section + lines[end:]
    trailing = "\n" if build_plan_content.endswith("\n") else ""
    return "\n".join(new_lines) + trailing, changes


def is_views_enabled(project_state_path: Path) -> bool:
    """True if project-state.yaml has top-level ``views_enabled: true``.

    Scans for a column-0 ``views_enabled:`` key, ignoring comments. Returns
    False on any error or missing key — opt-in by design.
    """
    if not project_state_path.exists():
        return False
    try:
        content = project_state_path.read_text(encoding="utf-8")
    except OSError:
        return False
    for raw in content.splitlines():
        if raw[:1] in (" ", "\t"):
            continue
        line = raw.split("#", 1)[0].rstrip()
        if not line.startswith("views_enabled:"):
            continue
        value = line.split(":", 1)[1].strip().lower()
        return value == "true"
    return False
