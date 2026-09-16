"""Keeping ``.prawduct/change-log.md`` bounded by moving history into an archive.

The live log is read by people and agents every session, and nothing else ever
shortened it: the release adds a ``release=`` tag and nothing more, so the log
only grew — this repo's reached 1.5 MB, and every product's is on the same curve.
Deleting old entries is not the answer, because the change log is the record of
which work shipped in which release and three readers interpret that history.
So entries **move**, verbatim, into ``.prawduct/change-log-archive/YYYY-MM.md``,
and every reader that interprets history loads both through :func:`load_all_text`.

**What may move** (:func:`select`) is decided by three rules, each for a reason:

* **Release-pending entries never move** in a product that versions. The release
  gate enumerates pending work by the absence of ``release=``, and the live log is
  where the people cutting a release look for it. A product that has never tagged a
  release has no pending set, so its tagged entries age out like any other.
* **Undated entries never move** — there is no bucket to put them in, and keeping
  them live is the direction that loses nothing.
* **Newest first, and once one entry does not fit, everything older goes.** Keeping
  small old entries around a large recent one would leave a log that is neither
  recent nor complete.

**Hysteresis.** Nothing moves until the live log exceeds the repo's oversized
threshold; then it is cut to half of it. Run on every PR, it is a no-op almost
always, so concurrent branches rarely move entries at the same time.

**It refuses on a malformed tag** (:class:`ArchiveRefused`), because a bad
``release=`` value is precisely what makes a pending entry look shipped, and the
move would then take unreleased work out of the release's sight.

**And it checks its own result with the release gate's readers.** The selection
rule keeps pending entries by construction, but checking a rule against itself is
how a selection bug proves its own correctness. So before anything is written, the
log the run would leave is re-read by ``release_readiness``'s own predicates: the
release-pending and unclassifiable sets must be identical and no tag diagnostic may
appear. Any difference refuses the run. The move is then written all-or-nothing
across every file it touches (:func:`core.write_all_or_none`), so an interrupted
run leaves the log as it was rather than entries in two places.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import change_log

ARCHIVE_DIR_REL = ".prawduct/change-log-archive"
#: The same directory, relative to the ``.prawduct`` directory callers hold.
ARCHIVE_DIR_NAME = "change-log-archive"
LIVE_NAME = "change-log.md"

#: The live log's pointer to its archive, inserted once after the preamble so a
#: reader of the live file learns that older entries exist and where.
ARCHIVE_POINTER = (
    "<!-- Older entries live in .prawduct/change-log-archive/YYYY-MM.md, moved there "
    "verbatim by `prawduct-hook archive-change-log`. -->"
)

_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-\d{2}\b")
_RELEASE_TAG_RE = re.compile(r"release\s*=\s*\S")


class ArchiveRefused(Exception):
    """The log holds a tag the release validator rejects; nothing was written."""


@dataclass
class Block:
    """One entry's raw text and its parse. ``text`` ends with a newline."""

    text: str
    entry: change_log.ChangeLogEntry
    index: int  # position in the file it came from

    @property
    def date(self) -> str | None:
        match = _DATE_RE.match(self.entry.title)
        return match.group(0) if match else None

    @property
    def bucket(self) -> str | None:
        match = _DATE_RE.match(self.entry.title)
        return f"{match.group(1)}-{match.group(2)}" if match else None

    @property
    def size(self) -> int:
        return len(self.text.encode("utf-8"))


def split(content: str) -> tuple[str, list[Block]]:
    """``(preamble, blocks)`` — the file cut where its parser says entries start.

    Boundaries come from :func:`change_log.parse_change_log`'s own header line
    numbers rather than a second header regex, so this module and every reader
    of the log share one definition of where an entry begins and ends.
    """
    entries = change_log.parse_change_log(content)
    lines = content.splitlines(keepends=True)
    if not entries:
        return content, []
    preamble = "".join(lines[: entries[0].line_number - 1])
    blocks: list[Block] = []
    for n, entry in enumerate(entries):
        start = entry.line_number - 1
        end = entries[n + 1].line_number - 1 if n + 1 < len(entries) else len(lines)
        text = "".join(lines[start:end])
        if not text.endswith("\n"):
            text += "\n"
        blocks.append(Block(text=text, entry=entry, index=n))
    return preamble, blocks


def product_versions(live_text: str, archive_dir: Path) -> bool:
    """Whether any entry, live or archived, carries a ``release=`` tag.

    Asked of the archive too because the live log of a versioned product holds
    almost no released entries once it has been archived — deciding from the live
    file alone would, after the first run, declare the product unversioned and let
    its pending work move. A substring scan, newest file first, stopping at the
    first hit: this runs in the session-start advisory, so it must stay cheap.
    """
    if any(entry.tags.get("release") for entry in change_log.parse_change_log(live_text)):
        return True
    for path in _archive_files(archive_dir):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            # Unreadable history cannot prove the product is unversioned, and
            # assuming it is would let pending entries move. Fail toward keeping.
            return True
        if any(
            _RELEASE_TAG_RE.search(match.group(1))
            for match in change_log.TAG_LINE_RE.finditer(text)
        ):
            return True
    return False


def _pinned(block: Block, versions: bool) -> bool:
    entry = block.entry
    if block.bucket is None:
        return True
    if entry.unconsumed_tag_lines:
        # A tag line nobody parsed may carry the `release=` (or its absence) that
        # decides this entry's status. Unknown status stays live.
        return True
    if not versions:
        return False
    # The release gate's own predicate, not a restatement of it: what this module
    # keeps live must be exactly what `check-releasability` calls pending.
    from .release_readiness import release_pending_entries  # noqa: PLC0415 — lazy; avoids an import cycle through gates

    return bool(release_pending_entries([entry]))


@dataclass
class Selection:
    """What an archive run would do. ``moved`` is empty when nothing needs to."""

    preamble: str
    kept: list[Block]
    moved: list[Block]
    live_bytes: int
    threshold: int
    pinned_bytes: int = 0
    buckets: dict[str, list[Block]] = field(default_factory=dict)
    #: The live log this run would leave — the exact text the invariant was
    #: checked over, and the exact text :func:`apply` writes.
    new_live: str = ""

    @property
    def kept_bytes(self) -> int:
        return len(self.preamble.encode("utf-8")) + sum(b.size for b in self.kept)


def select(content: str, *, threshold: int, versions: bool) -> Selection:
    """Decide which entries leave the live log. Pure; reads nothing but its input.

    Raises :class:`ArchiveRefused` when the release validator reports errors.
    """
    preamble, blocks = split(content)
    live_bytes = len(content.encode("utf-8"))
    errors, _warnings = change_log.validate_change_log_tags([b.entry for b in blocks])
    if errors:
        raise ArchiveRefused(
            "the change log carries a tag the release gate rejects, and a bad `release=` "
            "is what makes pending work look shipped — nothing moved. Fix: " + "; ".join(errors)
        )

    selection = Selection(preamble=preamble, kept=list(blocks), moved=[],
                          live_bytes=live_bytes, threshold=threshold)
    if live_bytes <= threshold:
        return selection

    pinned = [b for b in blocks if _pinned(b, versions)]
    selection.pinned_bytes = sum(b.size for b in pinned)
    budget = threshold // 2 - len(preamble.encode("utf-8")) - len(ARCHIVE_POINTER) - 2
    budget -= selection.pinned_bytes

    # Newest first by header date; the file's own order breaks ties, since
    # entries are appended at the top by convention.
    candidates = sorted(
        (b for b in blocks if not _pinned(b, versions)),
        key=lambda b: (b.date or "", -b.index),
        reverse=True,
    )
    keep: set[int] = {b.index for b in pinned}
    used = 0
    overflow = False
    for block in candidates:
        if not overflow and used + block.size <= budget:
            keep.add(block.index)
            used += block.size
        else:
            overflow = True
    selection.kept = [b for b in blocks if b.index in keep]
    selection.moved = [b for b in blocks if b.index not in keep]
    for block in selection.moved:
        selection.buckets.setdefault(block.bucket or "", []).append(block)
    if selection.moved:
        selection.new_live = _compose_live(preamble, selection.kept)
        problems = invariant_violations(content, selection.new_live, versions=versions)
        if problems:
            raise ArchiveRefused(
                "the move would change what the release gate sees, so nothing was "
                "written: " + "; ".join(problems)
            )
    return selection


def _fingerprint(content: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    from .release_readiness import (  # noqa: PLC0415 — lazy; avoids an import cycle through gates
        release_pending_entries,
        unclassifiable_pending_entries,
    )

    entries = change_log.parse_change_log(content)
    return (
        tuple(sorted(e.title for e in release_pending_entries(entries))),
        tuple(sorted(e.title for e in unclassifiable_pending_entries(entries))),
    )


def _diagnostics(content: str) -> set[str]:
    errors, warnings = change_log.validate_change_log_tags(change_log.parse_change_log(content))
    # The validator names each entry by line number, and a staying entry below a
    # moved one changes line without changing anything else. Compare the fact.
    return {re.sub(r"\(line \d+\)", "(line ?)", d) for d in (*errors, *warnings)}


def invariant_violations(before: str, after: str, *, versions: bool) -> list[str]:
    """What the release gate would see differently in ``after``. Empty means safe.

    In a product that versions, the release-pending and unclassifiable sets must be
    identical. In one that does not, there is no pending set to protect, so only
    the diagnostics check applies. Diagnostics may disappear (they leave with the
    entries they describe) but never appear: a move of whole entries that changes
    how the remaining log parses has broken an entry boundary.
    """
    problems: list[str] = []
    if versions:
        was, now = _fingerprint(before), _fingerprint(after)
        lost = sorted(set(was[0]) - set(now[0]))
        if was[0] != now[0]:
            problems.append(
                "release-pending entries would leave the live log: " + (", ".join(lost) or "set changed")
            )
        if was[1] != now[1]:
            problems.append("the unclassifiable pending set would change")
    for diag in sorted(_diagnostics(after) - _diagnostics(before)):
        problems.append(f"new tag diagnostic: {diag}")
    return problems


def _archive_files(archive_dir: Path) -> list[Path]:
    try:
        return sorted(archive_dir.glob("*.md"), reverse=True)
    except OSError:
        return []


def _bucket_header(bucket: str) -> str:
    return (
        f"# Change log archive — {bucket}\n\n"
        "<!-- Entries moved verbatim from .prawduct/change-log.md by "
        "`prawduct-hook archive-change-log`, newest first. History: plan-backfill and "
        "record-lint read these alongside the live log; nothing here is release-pending. "
        "Never edit or delete an entry. -->\n\n"
    )


def _join(blocks: list[Block]) -> str:
    return "".join(b.text if b.text.endswith("\n\n") else b.text + "\n" for b in blocks)


def _compose_live(preamble: str, kept: list[Block]) -> str:
    return _with_pointer(preamble) + _join(kept).rstrip("\n") + "\n"


def _compose_bucket(existing: str, incoming: list[Block], bucket: str) -> str:
    """The month file with ``incoming`` merged in, newest first, never duplicated.

    The header is rewritten every time rather than preserved: it is not an entry,
    and a header that describes the file wrongly should be corrected by the next
    run rather than kept forever.
    """
    _preamble, current = split(existing) if existing else ("", [])
    present = {b.text.rstrip("\n") for b in current}
    fresh = [b for b in incoming if b.text.rstrip("\n") not in present]
    merged = fresh + current
    # Stable sort, newest first: incoming blocks were newer in the live log, so on
    # an equal date they precede what an earlier run already archived.
    merged.sort(key=lambda b: b.date or "", reverse=True)
    return _bucket_header(bucket) + _join(merged).rstrip("\n") + "\n"


def _with_pointer(preamble: str) -> str:
    if ARCHIVE_POINTER in preamble:
        return preamble
    return preamble.rstrip("\n") + "\n\n" + ARCHIVE_POINTER + "\n\n"


def archive_would_be_ignored(project_root: Path) -> bool:
    """True when git tracks the live log but would ignore the archive.

    A repo that commits only ``.prawduct/change-log.md`` out of an ignored
    ``.prawduct/`` would commit the entries' REMOVAL and silently drop the archive
    they moved to — history leaving git with no error. Asked before writing, so
    the run can refuse instead. Where the live log is not tracked either, nothing
    is committed on either side and there is nothing to lose.
    """
    from . import gitstate  # noqa: PLC0415 — lazy; git is only asked on the write path

    if gitstate.git_path_is_tracked(project_root, change_log.CHANGE_LOG_REL_PATH) is not True:
        return False
    return gitstate.git_path_is_ignored(project_root, f"{ARCHIVE_DIR_REL}/0000-00.md")


def apply(prawduct_dir: Path, selection: Selection) -> list[Path]:
    """Write the move, all-or-nothing across the live log and every month file.

    Returns the files written. Raises ``OSError`` with every file restored when any
    write fails (:func:`core.write_all_or_none`).
    """
    if not selection.moved:
        return []
    from . import core  # noqa: PLC0415 — lazy keeps this module's import surface small

    archive_dir = prawduct_dir / ARCHIVE_DIR_NAME
    archive_dir.mkdir(parents=True, exist_ok=True)
    writes: list[tuple[Path, str]] = []
    for bucket, blocks in sorted(selection.buckets.items()):
        path = archive_dir / f"{bucket}.md"
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
        writes.append((path, _compose_bucket(existing, blocks, bucket)))
    live = prawduct_dir / LIVE_NAME
    writes.append((live, selection.new_live))
    core.write_all_or_none(writes)
    return [path for path, _ in writes]


def load_all_text(prawduct_dir: Path) -> str | None:
    """The live log followed by every archive file — the whole history, one text.

    For readers that interpret history (which scopes shipped, which scopes were
    ever declared). ``None`` when the live log itself cannot be read, which callers
    already treat as their unreadable case; an unreadable archive file is skipped,
    since the live log alone is what those readers saw before archiving existed.
    Concatenation is safe because no reader depends on document position across
    files — plan-backfill and record-lint decide by tag and by header date.
    """
    try:
        parts = [(prawduct_dir / LIVE_NAME).read_text(encoding="utf-8")]
    except (OSError, UnicodeDecodeError):
        return None
    for path in _archive_files(prawduct_dir / ARCHIVE_DIR_NAME):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        parts.append(text)
    return "\n".join(part.rstrip("\n") + "\n" for part in parts)
