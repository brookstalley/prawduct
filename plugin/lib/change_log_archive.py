"""Retiring shipped change-log entries into `.prawduct/change-log-history.md`.

**The change-log is the one durable record here that had no way out.**
`learnings.md` retires rules to `learnings-history.md` through `audit-learnings
--apply`; build plans move to `artifacts/archive/` through `archive-plan`. The
change-log's header told authors to append at the top and nothing ever took an
entry back out, so it grew monotonically to 1.5 MB across 387 entries — and the
one archive that did happen was a hand-move of pre-2026-03-22 entries INTO
`project-state.yaml`, which is a live contributor to that file's own oversized
advisory. A relocation is not a lifecycle. This module is the lifecycle.

**What may leave, and why the rule is asymmetric.** An entry carrying a
``release=`` has shipped, and no gate reads it afterwards: ``check-released``
verifies a release from the version files, the tag on the release branch and the
published release — it never opens this file — while
``check-releasability`` derives the release-pending set from the ABSENCE of
``release=``. So a shipped entry leaving the live log changes no answer. A
release-PENDING entry leaving it unships work silently, which is the whole
silent-drop family. Hence: only ``release=``-carrying entries are eligible, and
the command proves the pending set is unchanged before it writes anything.

**History is a redirect, not a hole.** Entries move whole — header, tag line and
body — into a file that is findable by name and never rewritten. Nothing is
deleted, and a reader who wants the six months of narrative reads one file over.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import change_log as change_log_mod
from .release_readiness import (
    release_pending_entries,
    unclassifiable_pending_entries,
)

HISTORY_REL_PATH = ".prawduct/change-log-history.md"

#: Leading text of the history file, written once when it is created. It says
#: what the file is FOR, because the failure it guards against is someone
#: reading a 1 MB file of shipped entries as live work.
HISTORY_HEADER = """# Change Log — History

<!-- Retired entries, moved here by `prawduct-hook archive-change-log`. Every entry here
     carries a `release=` tag: it shipped, and no gate reads it any more. Newest first,
     matching the live log.

     APPEND-ONLY. Nothing is deleted here and nothing is rewritten — an entry moved out of
     the live log is a redirect, not a hole. The live log at `.prawduct/change-log.md`
     holds release-pending work and the current release line. -->
"""

#: A release value this module is willing to act on. Anything else — a
#: placeholder, a range, an empty string — is refused rather than guessed at,
#: because guessing wrong here moves an entry nobody meant to move.
_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")


@dataclass(frozen=True)
class MinorLine:
    """A ``MAJOR.MINOR`` release line — the unit retention is expressed in.

    Retention is per LINE rather than per version because that is how the work
    actually clusters: a patch release carries whatever was pending when it was
    cut, so "keep v3.4.x" keeps a release's worth of context and "keep the last
    N entries" keeps an arbitrary slice of one.
    """

    major: int
    minor: int

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}"

    def __lt__(self, other: "MinorLine") -> bool:
        return (self.major, self.minor) < (other.major, other.minor)


def parse_minor_line(text: str) -> MinorLine | None:
    """``"3.4"`` / ``"v3.4"`` / ``"v3.4.1-dev.2"`` → :class:`MinorLine`, else ``None``."""
    cleaned = text.strip().lstrip("vV")
    m = re.match(r"^(\d+)\.(\d+)(?:\.|$)", cleaned)
    if not m:
        return None
    return MinorLine(int(m.group(1)), int(m.group(2)))


def release_minor_line(release_value: object) -> MinorLine | None:
    """The minor line a ``release=`` tag value names, or ``None`` if it names none.

    ``None`` is the refusal, and callers must treat it as "do not move this
    entry". A malformed ``release=`` is exactly the state
    ``validate_change_log_tags`` errors on, so an archiver that guessed at one
    would be moving an entry whose release nobody can name.
    """
    if not isinstance(release_value, str):
        return None
    if not _VERSION_RE.match(release_value.strip()):
        return None
    return parse_minor_line(release_value)


def current_minor_line(project_dir: Path) -> MinorLine | None:
    """The line this repo is currently on, read from ``plugin/VERSION``.

    The same file ``check-releasability`` falls back to, and read for the same
    reason: it is prawduct's version source of truth. A ``-dev`` suffix is fine
    here where it is a poor answer there — this asks which LINE is open, and
    ``3.4.1-dev.2`` answers that exactly.
    """
    try:
        raw = (project_dir / "plugin" / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return parse_minor_line(raw)


def split_entries(content: str) -> tuple[str, list[tuple[object, str]]]:
    """``(preamble, [(entry, text)])`` — the file as its parser sees it, plus the bytes.

    :func:`change_log.parse_change_log` answers what each entry MEANS and gives
    each one's 1-indexed header line; the text between one header and the next
    is the entry itself. Splitting here rather than re-parsing keeps one
    definition of where an entry starts: a second regex for H2 headers is how
    the live log and the archive would come to disagree about what moved.
    """
    entries = change_log_mod.parse_change_log(content)
    lines = content.splitlines(keepends=True)
    if not entries:
        return content, []

    preamble = "".join(lines[: entries[0].line_number - 1])
    out: list[tuple[object, str]] = []
    for idx, entry in enumerate(entries):
        start = entry.line_number - 1
        end = (
            entries[idx + 1].line_number - 1
            if idx + 1 < len(entries)
            else len(lines)
        )
        out.append((entry, "".join(lines[start:end])))
    return preamble, out


def select_for_archive(
    pairs: list[tuple[object, str]], keep_from: MinorLine
) -> tuple[list[tuple[object, str]], list[tuple[object, str]]]:
    """Split ``pairs`` into ``(moving, staying)``.

    An entry moves only when it carries a parseable ``release=`` whose line is
    STRICTLY below ``keep_from``. Everything else stays, and the three ways to
    stay are all deliberate: no tag line at all (pre-convention history, which
    no gate claims authority over), a tag line with no ``release=`` (the
    release-pending marker), and a ``release=`` this module will not parse
    (refused, not guessed).
    """
    moving: list[tuple[object, str]] = []
    staying: list[tuple[object, str]] = []
    for entry, text in pairs:
        line = release_minor_line(entry.tags.get("release"))
        if line is not None and line < keep_from:
            moving.append((entry, text))
        else:
            staying.append((entry, text))
    return moving, staying


def pending_fingerprint(content: str) -> tuple:
    """What must not change across an archive run.

    The release-pending set, the unclassifiable-pending subset, and the tag
    validation verdict — computed from the same functions the release gate uses,
    never re-derived here. Comparing this before and after is what turns "only
    shipped entries move" from a claim in a docstring into something the command
    refuses to violate.
    """
    entries = change_log_mod.parse_change_log(content)
    pending = tuple(sorted(e.title for e in release_pending_entries(entries)))
    unclassifiable = tuple(
        sorted(e.title for e in unclassifiable_pending_entries(entries))
    )
    errors, warnings = change_log_mod.validate_change_log_tags(entries)
    return pending, unclassifiable, tuple(errors), tuple(warnings)


def compose(
    live_content: str,
    history_content: str | None,
    keep_from: MinorLine,
) -> tuple[str, str, list[tuple[object, str]]]:
    """``(new_live, new_history, moved)`` — pure, so the caller can compare before writing.

    History keeps newest-first ordering to match the live log, and new arrivals
    go at its top for the same reason: the two files read the same way round, so
    moving between them is a change of file and not a change of convention.
    """
    preamble, pairs = split_entries(live_content)
    moving, staying = select_for_archive(pairs, keep_from)

    new_live = preamble + "".join(text for _entry, text in staying)
    moved_text = "".join(text for _entry, text in moving)

    if history_content is None:
        new_history = HISTORY_HEADER + "\n" + moved_text
    else:
        h_preamble, h_pairs = split_entries(history_content)
        existing = "".join(text for _entry, text in h_pairs)
        new_history = h_preamble + moved_text + existing
    return new_live, new_history, moving


@dataclass(frozen=True)
class ArchiveResult:
    """What an archive run WOULD do, and whether it is allowed to.

    The decision lives here rather than in the command for one reason: a guard
    that only exists inside a CLI branch can only be tested through a
    subprocess, and the failure it guards against — a selection that also takes
    release-pending entries — cannot be provoked through one. So the command
    prints this and the tests provoke it.

    ``refused_titles`` non-empty means write NOTHING. It is not a warning to
    print beside a successful write; the entries it names are work that would
    stop being release-pending, with no error anywhere downstream.
    """

    new_live: str
    new_history: str
    moved: list
    refused_titles: list


def archive_or_refuse(
    live_content: str,
    history_content: str | None,
    keep_from: MinorLine,
) -> ArchiveResult:
    """:func:`compose`, with the release-pending invariant checked over it.

    The comparison is between the log that exists and the log this run would
    leave — not between the selection and the rule that made it. Checking the
    rule against itself is how a selection bug proves its own correctness; this
    asks the release gate's own readers whether anything it can see has moved.
    """
    new_live, new_history, moved = compose(live_content, history_content, keep_from)
    before = pending_fingerprint(live_content)
    after = pending_fingerprint(new_live)
    if before == after:
        return ArchiveResult(new_live, new_history, moved, [])
    lost = sorted(set(before[0]) - set(after[0]))
    # A fingerprint can differ without an entry LEAVING the pending set — a tag
    # validation warning could change, say. Both are refusals: the invariant is
    # that the gate's whole answer is untouched, and a run that alters any part
    # of it is a run nobody sanctioned.
    return ArchiveResult(new_live, new_history, moved, lost or ["<pending-set changed>"])
