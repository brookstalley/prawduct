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


def _release_verification():
    """Lazy — `release_verification` imports `json`/`tomllib` machinery this
    module needs only to answer which release line is open."""
    from . import release_verification  # noqa: PLC0415

    return release_verification

#: The two files this module moves entries between, both named here so a caller
#: reaches them by one route. The hook used to read the live path through this
#: module's private import alias for `change_log`, which is a second way in to a
#: fact with a home.
CHANGE_LOG_REL_PATH = change_log_mod.CHANGE_LOG_REL_PATH
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

#: What counts as a shipped ``release=`` — **the change-log's own definition**,
#: reused rather than restated. A second regex here accepted `3.2.0` and
#: `v3.2.0+b`, which `validate_change_log_tags` rejects: the archiver would have
#: moved entries the release gate calls malformed, on the strength of its own
#: laxer reading of a value neither of them owns.
_RELEASE_VALUE_RE = change_log_mod.RELEASE_VALUE_RE


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
    if not _RELEASE_VALUE_RE.match(release_value.strip()):
        return None
    return parse_minor_line(release_value)


def current_minor_line(project_dir: Path) -> MinorLine | None:
    """The release line this product is currently on, or ``None``.

    **Read from the product's own ``release_version_files:`` declaration**, not
    from a layout. This module ships to every governed product and none of them
    has a ``plugin/`` directory; reading ``plugin/VERSION`` here would make the
    documented default refuse in every repo but this one, while naming a path
    that repo does not contain. Which files carry the version is the product's
    to state — the same rule ``release_verification`` follows, through the same
    reader, so a product declares it once.

    Prawduct's own layout remains as a labelled fallback for a product that has
    declared nothing, and it is a guess: it can supply a default, and a wrong
    guess here costs a dry run rather than a bad write, because nothing is
    archived without ``--apply``.

    A ``-dev`` suffix is fine and is the common case — this asks which LINE is
    open, and ``3.4.1-dev.2`` answers that exactly.
    """
    verification = _release_verification()
    try:
        state_text = (project_dir / verification._STATE_PATH).read_text(
            encoding="utf-8"
        )
    except OSError:
        state_text = ""
    declared = verification._read_declaration(state_text) if state_text else None
    # `is not None`, never truthiness. `_read_declaration` returns THREE
    # outcomes and its docstring turns on the distinction: `None` is undeclared
    # (the guess applies) and `[]` is declared-empty or flow-style, which is
    # honoured exclusively. Reading `[]` as "nothing declared" hands a product
    # that wrote a real declaration prawduct's layout instead — the same
    # layout-over-declaration defect this function was rewritten to close,
    # re-entered through its own fix. `release_verification` spells it
    # `is not None` at its own call site for this reason.
    specs = declared if declared is not None else list(
        verification._FALLBACK_VERSION_FILES
    )

    for spec in specs:
        try:
            content = (project_dir / spec.path).read_text(encoding="utf-8")
        except OSError:
            continue
        read = verification._read_version(spec, content)
        if read.value:
            line = parse_minor_line(read.value)
            if line is not None:
                return line
    return None


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
    """The release-pending sets a log yields — computed by the gate's own readers.

    Two sets, both keyed by title, and both must be IDENTICAL across a run:
    an entry leaving either is work that stops being release-pending with no
    error anywhere downstream.

    Tag diagnostics are deliberately not here; :func:`new_diagnostics` carries
    them, and the difference is direction. A warning attached to an entry that
    legitimately archives leaves with it, so requiring equality would refuse a
    correct run — and prawduct's own log contains that case: a 2026-08-13 entry
    carries two tag lines and a `release=`, so it becomes eligible at the first
    3.5 release and would have refused the archiver on its own corpus.
    """
    entries = change_log_mod.parse_change_log(content)
    pending = tuple(sorted(e.title for e in release_pending_entries(entries)))
    unclassifiable = tuple(
        sorted(e.title for e in unclassifiable_pending_entries(entries))
    )
    return pending, unclassifiable


def new_diagnostics(before_content: str, after_content: str) -> list[str]:
    """Tag errors/warnings the run would CREATE, which is the direction that matters.

    Diagnostics disappearing is expected — they ride the entries that archive.
    A diagnostic appearing means the rewrite changed how the remaining log
    parses, which is the one thing a move of whole entries must never do.
    """
    def _diags(content: str) -> set[str]:
        entries = change_log_mod.parse_change_log(content)
        errors, warnings = change_log_mod.validate_change_log_tags(entries)
        # The validator names each entry with its line number. A staying entry
        # below a moved one keeps its diagnostic and loses its line, so the same
        # fact would read as a NEW diagnostic and refuse a correct run. Compare
        # the fact, not the position.
        return {re.sub(r"\(line \d+\)", "(line ?)", d) for d in (*errors, *warnings)}

    return sorted(_diags(after_content) - _diags(before_content))


def _compose(
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

    # Every piece is joined on a line boundary. The last entry of a file with no
    # trailing newline has none, and gluing history's newest `## ` header onto
    # its final line is how the parser loses an entry — the one thing a move of
    # whole entries must never do.
    new_live = _nl(preamble) + "".join(_nl(text) for _entry, text in staying)
    moved_text = "".join(_nl(text) for _entry, text in moving)

    if history_content is None:
        new_history = HISTORY_HEADER + "\n" + moved_text
    else:
        h_preamble, h_pairs = split_entries(history_content)
        existing = "".join(_nl(text) for _entry, text in h_pairs)
        new_history = _nl(h_preamble) + moved_text + existing
    return new_live, new_history, moving


def _nl(text: str) -> str:
    """``text`` ending in a newline, unless it is empty."""
    return text if not text or text.endswith("\n") else text + "\n"


@dataclass(frozen=True)
class ArchiveResult:
    """What an archive run WOULD do, and whether it is allowed to.

    The decision lives here rather than in the command because the state it
    guards against — a selection that also takes release-pending entries — is
    unreachable from any input, by construction: `select_for_archive` is what
    makes it so. A guard living inside a CLI branch could then only be reached
    across a subprocess boundary that no fixture can drive, so it would ship
    ungraded. Here the tests provoke it directly, and a second test drives the
    command in-process to prove it ACTS on the refusal rather than printing it.

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
    new_live, new_history, moved = _compose(live_content, history_content, keep_from)
    before = pending_fingerprint(live_content)
    after = pending_fingerprint(new_live)
    refused: list[str] = []
    if before != after:
        # Named individually where they can be — the operator's next question is
        # always "which entry" — and reported as a set change when the two
        # differ in a way no title diff explains.
        refused = sorted(set(before[0]) - set(after[0])) or ["<pending-set changed>"]
    refused.extend(
        f"new diagnostic: {d}" for d in new_diagnostics(live_content, new_live)
    )
    return ArchiveResult(new_live, new_history, moved, refused)
