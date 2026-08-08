"""Reading `.prawduct/change-log.md` tag lines, and validating what they say.

This module knows **tags and nothing about plans**. Scope→plan resolution lives
in :mod:`lib.plan_index`; the two were one module named ``views`` that did both
jobs under a name describing neither, which is part of why a dual-reading defect
reached three consumers before anyone generalised it.

Tagged-entry format — one line after each ``## YYYY-MM-DD:`` header (blank lines
between are tolerated). **The format a new entry is written in is two keys**::

    <!-- prawduct: scope=v1.4 | release=v1.3.18 -->

Older entries carry two more, and the parser still accepts them because every
onboarded repo's committed log is full of them::

    <!-- prawduct: chunks=00,01,02 | release=v1.3.18 | status=shipped | scope=v1.4 -->

**Accepting is not the same as reading.** ``chunks`` and ``status`` are retired
and inert: nothing consults either, no value of them means anything, and they are
neither rewritten nor removed. Anything below describing them is describing what
a *historical* entry may contain. Keys, and who reads them:

* ``scope``   — the rollup identifier. Read by the release gate to enumerate
  what has not shipped, and by :mod:`lib.plan_index` to find the plan that
  declares the same scope in its frontmatter.
* ``release`` — the version that carried this entry. Its ABSENCE is what marks
  an entry release-pending, which is why a malformed value is an error rather
  than a curiosity (see :func:`validate_change_log_tags`).
* ``chunks``  — comma-separated chunk IDs. **RETIRED**, with the derived views
  that were its only reader. Which chunks an entry shipped belongs in the entry
  BODY, where release notes and readers actually look.
* ``status``  — ``shipped`` | ``merged``. **RETIRED**, with ``chunks``: nothing
  reads it and the commands that wrote it are inert. Release-pending is now
  carried by the ABSENCE of ``release=`` alone. Historical entries carrying
  either value still parse, because the parser preserves unknown keys and both
  are now among them.

Unknown keys are preserved verbatim so a future reader can pick them up without
a schema bump. Entries with no tag line are ignored — untagged historical
entries coexist with tagged ones.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


TAG_LINE_RE = re.compile(r"<!--\s*prawduct:\s*(.+?)\s*-->")
H2_RE = re.compile(r"^##\s+(.+?)\s*$")


@dataclass
class ChangeLogEntry:
    """A change-log entry with optional tagged metadata."""

    title: str
    tags: dict[str, object] = field(default_factory=dict)
    line_number: int = 0  # 1-indexed line of the H2 header
    # How many `<!-- prawduct: ... -->` lines headed this entry. The canonical
    # format is exactly one; >1 means the tags above are a union and
    # `validate_change_log_tags` will warn.
    tag_line_count: int = 0
    # Scalar keys that appeared on a later tag line with a DIFFERENT value than
    # an earlier one — first-wins, the losing value recorded here for the error.
    tag_conflicts: list[str] = field(default_factory=list)

    # A `shipped_chunks` property stood here, composing `status=shipped` with
    # `chunks=` to answer "which chunks did this entry ship". Both keys are
    # retired and its only caller — the derived-view regenerator that flipped
    # checkboxes from that answer — is gone, so it was retired with them rather
    # than left as a helper with no consumer. Both keys still PARSE: the parser
    # preserves unknown keys, so historical entries carrying them round-trip and
    # `tags["chunks"]` reads them directly if anything ever needs to.


def parse_tag_line(tag_body: str) -> dict[str, object]:
    """Parse the body of a tag line (between ``prawduct:`` and ``-->``).

    Pipe-delimited ``key=value`` pairs. ``chunks`` is split on commas into a
    list; other keys are kept as plain strings. Unknown keys are preserved as-is
    so a future reader can pick them up without a schema bump.
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


def _merge_tag_line(entry: ChangeLogEntry, new_tags: dict[str, object]) -> None:
    """Merge a subsequent tag line's pairs into an entry, union semantics.

    ``chunks`` lists are concatenated with order-preserving dedup; a key not yet
    present is adopted; a scalar key already present with a *different* value is
    first-wins, the ignored value recorded in ``tag_conflicts`` so
    :func:`validate_change_log_tags` can surface it.
    """
    for k, v in new_tags.items():
        if k not in entry.tags:
            entry.tags[k] = v
            continue
        existing = entry.tags[k]
        if k == "chunks" and isinstance(existing, list) and isinstance(v, list):
            entry.tags[k] = existing + [c for c in v if c not in existing]
        elif existing != v:
            entry.tag_conflicts.append(f"{k}: kept {existing!r}, ignored {v!r}")


def parse_change_log(content: str) -> list[ChangeLogEntry]:
    """Parse change-log markdown into a list of entries.

    An entry is ``## YYYY-MM-DD: title`` followed (after up to a few blank
    lines) by ``<!-- prawduct: key=value | ... -->``. The tag block, if present,
    must begin before the next non-blank content line under the H2.

    The canonical format is ONE tag line per entry, but **all consecutive** tag
    lines at the head of the body are consumed (blank lines between them
    tolerated, the same leniency as before the first one). The historical
    first-line-only parse silently dropped the later lines' pairs, which nearly
    shipped a second line's ``chunks=`` unflipped at v2.1.0. Multiple lines are
    unioned per :func:`_merge_tag_line`, ``tag_line_count`` records how many were
    seen, and :func:`validate_change_log_tags` warns on >1 and errors when they
    disagree. A tag line after intervening prose is still later body content,
    never entry metadata.
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
            if not tag_match:
                # First non-blank non-tag line ends the tag block.
                break
            new_tags = parse_tag_line(tag_match.group(1))
            entry.tag_line_count += 1
            if entry.tag_line_count == 1:
                entry.tags = new_tags
            else:
                _merge_tag_line(entry, new_tags)
            j += 1
        entries.append(entry)
        i += 1
    return entries


RELEASE_VALUE_RE = re.compile(r"^v\d+\.\d+\.\d+(?:-[0-9A-Za-z.]+)?$")


def validate_change_log_tags(
    entries: list[ChangeLogEntry],
) -> tuple[list[str], list[str]]:
    """Check the tag lines, returning ``(errors, warnings)``.

    One validator over the three failure shapes that can affect a **surviving**
    tag key — malformed value, the same key set twice to different values, and
    an entry assembled from more than one tag line. It replaces three separate
    per-shape functions whose only caller was the derived-view regenerator, and
    it moves the checks to the gate that has a reason to run them: the release
    gate is the thing that acts on ``release=`` and ``scope=``, so it is where a
    malformed one must be refused.

    **Errors** (the caller fails closed — this is an authority gate, and an
    unevaluable release state must never read as "fine"):

    * ``release=`` present but not a version. This fails in the worst possible
      direction. The release-pending set is every ``scope=``-tagged entry with
      NO ``release=``, so *any* value at all — including a placeholder naming
      the absence — removes the whole scope from that set, and the gate answers
      "nothing to cut" while the work never ships. That is not hypothetical:
      ``release=unreleased`` on six entries hid an entire branch from the
      v3.2.8 release, and it read as deliberate, which is exactly why nothing
      questioned it. Release-pending is *statusless with no* ``release=`` *tag*.
      Accepts ``vMAJOR.MINOR.PATCH`` with an optional ``-suffix``.
    * Tag lines that CONFLICT. When several tag lines set one scalar key to
      different values, :func:`_merge_tag_line` keeps the first — a repair that
      may have picked the wrong one (two ``release=`` lines disagreeing about
      whether something shipped). Fix the entry; do not guess.

    **Warnings** (the caller reports and proceeds):

    * More than one tag line on an entry. The union produces correct output, so
      this is a style problem the repair already fixed — surfaced so the author
      merges the lines, not to stop a release.

    Entries whose tags are absent are never flagged: an untagged historical
    entry is not a malformed tagged one.
    """
    errors: list[str] = []
    warnings: list[str] = []
    for entry in entries:
        where = f"change-log entry {entry.title!r} (line {entry.line_number})"

        release = entry.tags.get("release")
        if release is not None and not (
            isinstance(release, str) and RELEASE_VALUE_RE.match(release)
        ):
            errors.append(
                f"{where} has release={release!r}, which is not a version — "
                f"expected vMAJOR.MINOR.PATCH. Any release= tag marks this entry "
                f"as already released, so its whole scope drops out of the "
                f"release-pending set and the work never ships. Release-pending "
                f"is statusless with NO release= tag; delete the tag."
            )

        if entry.tag_conflicts:
            errors.append(
                f"{where} has conflicting values across its "
                f"{entry.tag_line_count} prawduct tag lines (kept first-wins: "
                + "; ".join(entry.tag_conflicts)
                + ") — the wrong value may have won. Merge the tag lines and "
                f"resolve the conflict."
            )

        if entry.tag_line_count > 1:
            warnings.append(
                f"{where} has {entry.tag_line_count} prawduct tag lines — the "
                f"canonical format is one per entry; the pairs were unioned "
                f"across them. Merge them into a single tag line."
            )
    return errors, warnings
