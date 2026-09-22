"""F10 — Operator-verification queue.

Append-only queue of pre-merge human-verification items for visual or
live-integration changes. Each entry is a ``## VRF-NNN — <Chunk N> — title``
section whose first non-blank body line carries ``**Status:**
pending | verified | accepted``.

The queue is gated by ``operator_verification_required: true`` in
``project-state.yaml``. When the flag is on, ``/prawduct:pr create`` blocks if
any entry's status is ``pending``; the user drains entries via
``prawduct-hook verify-operator-verification <ID>``, or overrides for the
current PR via ``/prawduct:pr create --accept-pending-verification "rationale"``.

The schema is read-first / append-only by design: this module exposes a
parser, in-memory mutators, and a round-tripping serializer. Mutators
preserve every body line outside the status line so user-authored
``**Where to verify:**`` / ``**Verify:**`` prose stays intact across
``verify``/``accept`` operations.

**The queue is an operator-authored record, and every write here is bounded by
that.** Two consequences run through the module. An entry whose status line
cannot be read is REFUSED rather than partially written — the mutators report
it, nothing is appended, and the caller renders the reason and the exact edit
from :attr:`VerificationEntry.status_defect`; the file is never repaired on the
operator's behalf. And a write changes only what the operation names: the
serializer preserves the body lines and the file's terminator, and
:func:`_write_queue` keeps the file's existing line endings, so flipping one
status word never hands back a reformatted file. Byte-identity is the stronger
claim and is not the one made here: the serializer terminates a final line that
had no terminator, and ``str.splitlines()`` breaks on \x0b, \x0c and \u2028,
which come back written as the file's ordinary terminator.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .core import atomic_write_text

# Recognized status tokens. ``pending`` is the only status that blocks
# ``/prawduct:pr create``; ``verified`` and ``accepted`` are both drained states
# kept in the file as append-only history.
_STATUS_PENDING = "pending"
_STATUS_VERIFIED = "verified"
_STATUS_ACCEPTED = "accepted"
_VALID_STATUSES = frozenset({_STATUS_PENDING, _STATUS_VERIFIED, _STATUS_ACCEPTED})

_VRF_HEADING_RE = re.compile(r"^##\s+(?P<vrf_id>VRF-\S+?)(?:\s+|$)")
_STATUS_LINE_RE = re.compile(
    r"^\*\*Status:\*\*\s+(?P<status>\S+)\s*$"
)

# Why an entry's status could not be read. Every one of these classifies as
# ``pending`` for gating — the gate's behaviour is byte-identical to before, and
# deliberately so. The kind exists for the commands that REFUSE, so they can name
# the edit that fixes the entry, which is the one thing the tooling could not
# previously tell an operator.
STATUS_DEFECT_NO_STATUS_LINE = "no-status-line"
STATUS_DEFECT_UNPARSED_LINE = "unparsed-status-line"
STATUS_DEFECT_UNKNOWN_TOKEN = "unknown-status-token"


@dataclass(frozen=True)
class StatusDefect:
    """Why an entry's status is unreadable, and the line that made it so.

    ``line`` is the offending body line verbatim so a refusal can quote it back;
    it is ``None`` for :data:`STATUS_DEFECT_NO_STATUS_LINE`, where the fault is
    that no such line exists.
    """

    kind: str
    line: str | None


def _read_status_line(
    body_lines: list[str],
) -> tuple[int | None, str, StatusDefect | None]:
    """Locate and interpret an entry's status line — one walk, for every reader.

    Returns ``(index, status, defect)``. ``index`` is where the status line sits
    in ``body_lines``, and is ``None`` in exactly the cases where ``defect`` is
    set, so a caller meaning to REWRITE the line cannot act on an entry the
    reader calls malformed.

    That coupling is the repair. The status reader used to require the status on
    the first non-blank body line while the writer rewrote the first line
    matching the pattern *anywhere* in the body — two carriers of "which line is
    the status line", free to disagree. An entry whose header ran the status into
    a longer metadata line read as ``pending`` forever while the writer either
    found nothing to change or silently edited some later line. One walk is what
    keeps them from disagreeing again.
    """
    for idx, raw in enumerate(body_lines):
        stripped = raw.strip()
        if not stripped:
            continue
        match = _STATUS_LINE_RE.match(stripped)
        if not match:
            # The first non-blank body line is not a status line at all. The
            # entry is malformed; it is NOT a licence to go looking further down
            # for something that parses.
            return None, _STATUS_PENDING, StatusDefect(
                STATUS_DEFECT_UNPARSED_LINE, stripped
            )
        status = match.group("status").lower()
        if status not in _VALID_STATUSES:
            return None, _STATUS_PENDING, StatusDefect(
                STATUS_DEFECT_UNKNOWN_TOKEN, stripped
            )
        return idx, status, None
    return None, _STATUS_PENDING, StatusDefect(STATUS_DEFECT_NO_STATUS_LINE, None)


def describe_status_defect(vrf_id: str, defect: StatusDefect) -> str:
    """The refusal an operator reads when an entry's status cannot be flipped.

    One carrier for three callers (verify, accept, the gate check), because the
    remedy is the same wherever the entry is met and three copies would drift.

    States the defect and the edit that fixes it, and claims nothing about what
    the caller did — the gate check mutates nothing, so a shared string asserting
    "nothing was changed" would be false there. Each caller says that for itself.

    The message has to name the edit that actually WORKS. Correcting the status
    word in place, inside the combined line, changes nothing — the reader never
    looks at that line's interior — so an operator who is told only "malformed"
    makes that edit, sees no improvement, and concludes the tool is broken.
    """
    if defect.kind == STATUS_DEFECT_NO_STATUS_LINE:
        return (
            f"{vrf_id} has no status line, so there is nothing to flip. Add "
            "`**Status:** pending` as the entry's first non-blank line, beneath "
            "its `## ` heading."
        )
    if defect.kind == STATUS_DEFECT_UNKNOWN_TOKEN:
        return (
            f"{vrf_id} carries a status this queue does not recognise:"
            f"\n    {defect.line}\n"
            "The status is one bare word — pending, verified or accepted. "
            "`superseded`, `n/a` and `wontfix` are not statuses: an entry that "
            "must not be drained by running its steps is `accepted`, with the "
            "reason as its rationale."
        )
    if defect.kind != STATUS_DEFECT_UNPARSED_LINE:
        # A kind added later must not inherit the sentence below, which
        # prescribes a specific edit ("split the line") that would be wrong
        # advice for a defect that is not this one. Naming the kind is a worse
        # message than a tailored one and a far better one than a confident
        # wrong instruction — the same reasoning the status classifier applies
        # when it refuses to guess.
        return (
            f"{vrf_id}'s status could not be read ({defect.kind}):"
            f"\n    {defect.line}\n"
            "The status line is `**Status:** <one bare word>` and nothing else, "
            "on its own line, as the entry's first non-blank line."
        )
    return (
        f"{vrf_id}'s status is not on a line of its own, so it cannot be read "
        f"or rewritten:\n    {defect.line}\n"
        "The status line is `**Status:** <one bare word>` and nothing else, on "
        "its own line, as the entry's first non-blank line. Editing the status "
        "word inside the line above will NOT help — the whole line has to be "
        "split, with the rest of its metadata moved to lines of their own. Put "
        "dates, chunk ids and prose on the `**Verified:**` / `**Accepted:**` "
        "line, which is where draining the entry writes them anyway."
    )


@dataclass
class VerificationEntry:
    """A single ``## VRF-NNN`` block.

    ``body_lines`` is the verbatim slice between the heading and the next
    heading (or end-of-file), excluding the heading itself but including
    blank lines, the ``**Status:**`` line, and any trailing
    ``**Verified:**`` / ``**Accepted:**`` lines. This lets the serializer
    round-trip user-authored content without reconstruction.
    """

    vrf_id: str
    heading: str  # full ``## VRF-NNN — ...`` line, verbatim
    body_lines: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        """Returns the entry's status token, or ``pending`` if unparseable.

        Missing or invalid ``**Status:**`` lines fall back to ``pending`` —
        "unknown" classification defaults to blocked (the cautious branch),
        matching the "Escape hatches in classification create silent
        failures" learning.
        """
        return _read_status_line(self.body_lines)[1]

    @property
    def status_defect(self) -> StatusDefect | None:
        """Why :attr:`status` fell back to ``pending``, or ``None`` if it did not.

        The diagnostic twin of :attr:`status`, and strictly additive: ``status``
        answers what the gate counts, this answers why, and only a caller that
        can act on the reason needs it. A gate reading ``status`` alone behaves
        exactly as it did before this existed.
        """
        return _read_status_line(self.body_lines)[2]


#: Statuses a queue check can report. ``unreadable`` is the third outcome, and
#: it exists for the same reason the other third outcomes in this codebase do:
#: a file that yielded nothing is not the same answer as a file that held
#: nothing, and folding them reports a drained queue on a queue nobody parsed.
QUEUE_OK = "ok"
QUEUE_UNREADABLE = "unreadable"


def unparsed_content_lines(preamble: str) -> list[str]:
    """Preamble lines that look like queue CONTENT rather than file header.

    :func:`parse_operator_verification` is deliberately lenient — a heading it
    does not recognise becomes preamble, so a trailing ``## Notes`` section a
    user appended does not break the parser. That leniency is right and stays.
    What it costs is that everything the parser failed to recognise lands in the
    preamble *silently*, and the gate then throws the preamble away.

    So this is the discriminator, and it is a filter rather than a guess: strip
    the level-1 title and any HTML comment (both of which the shipped template
    uses, and neither of which is an entry), and report what is left. A queue
    written in a format this parser cannot read has its entries here; a
    correctly-formatted queue — empty or full — has nothing here.

    Measured against the real corpora before it was written: the shipped
    template and this repo's live 16-entry queue each yield 0, and the
    bullets-under-one-pending-heading shape from the field report yields 4.
    """
    out: list[str] = []
    in_comment = False
    for line in preamble.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if in_comment:
            if "-->" in stripped:
                in_comment = False
            continue
        if stripped.startswith("<!--"):
            if "-->" not in stripped:
                in_comment = True
            continue
        # The level-1 title only. A `## ` heading IS content the parser did not
        # recognise, and is exactly what the reported failure looked like.
        if stripped.startswith("#") and not stripped.startswith("##"):
            continue
        out.append(stripped)
    return out


def parse_operator_verification(content: str) -> tuple[str, list[VerificationEntry]]:
    """Split ``operator-verification.md`` content into (preamble, entries).

    ``preamble`` is the file header up to (but not including) the first
    ``## VRF-`` heading — kept verbatim so round-tripping preserves
    user-authored intro prose and HTML comments.

    Entries are returned in file order. A heading without a recognizable
    ``VRF-<id>`` shape is ignored (treated as preamble continuation) — the
    parser is lenient on headings unrelated to the queue (e.g. ``## Notes``
    sections users may append).
    """
    lines = content.splitlines(keepends=False)

    preamble_lines: list[str] = []
    entries: list[VerificationEntry] = []
    current: VerificationEntry | None = None

    for line in lines:
        match = _VRF_HEADING_RE.match(line)
        if match:
            if current is not None:
                entries.append(current)
            current = VerificationEntry(
                vrf_id=match.group("vrf_id"),
                heading=line,
                body_lines=[],
            )
        elif current is not None:
            current.body_lines.append(line)
        else:
            preamble_lines.append(line)

    if current is not None:
        entries.append(current)

    # Terminate each line rather than joining with separators. `"\n".join`
    # followed by a single trailing newline cannot tell "the last preamble line
    # was blank" from "there was no trailing newline", and collapses the first
    # into the second — so a no-mutation round trip deleted the blank line
    # between the file's header comment and its first entry, once per drain.
    preamble = "".join(line + "\n" for line in preamble_lines)
    return preamble, entries


def format_operator_verification(
    preamble: str, entries: list[VerificationEntry]
) -> str:
    """Round-trip serializer for ``operator-verification.md``.

    The preamble is emitted verbatim, then each entry's heading + body. A
    trailing newline is enforced so re-reads parse cleanly. Body lines are
    written without trailing-whitespace normalization to preserve any
    user-applied formatting (markdown table alignment, etc.).
    """
    parts: list[str] = []
    if preamble:
        parts.append(preamble)
        if not preamble.endswith("\n"):
            parts.append("\n")
    for entry in entries:
        parts.append(entry.heading + "\n")
        for line in entry.body_lines:
            parts.append(line + "\n")
    out = "".join(parts)
    if not out.endswith("\n"):
        out += "\n"
    return out


def _set_status_line(entry: VerificationEntry, new_status: str) -> bool:
    """Rewrite the entry's status line in place.

    Returns True if the status line was found and changed, False otherwise —
    and **the caller must branch on it**. Discarding this return is what turned
    a clean refusal into a half-write: the status stayed put, a ``**Verified:**``
    footer was appended beneath it saying otherwise, and the command reported
    success. Nothing here appends; a False return leaves ``body_lines``
    untouched, so a caller that stops on False has written nothing at all.

    Which line counts as the status line is :func:`_read_status_line`'s to say,
    not this function's — see its docstring for why that is load-bearing.
    """
    idx, _, _ = _read_status_line(entry.body_lines)
    if idx is None:
        return False
    entry.body_lines[idx] = f"**Status:** {new_status}"
    return True


def _append_drain_footer(entry: VerificationEntry, footer: str) -> None:
    """Append a drain footer under exactly one blank line, keeping the body's tail.

    Two separate things, and each was wrong in a different direction before.

    ABOVE the footer: exactly one blank line. Appending one unconditionally
    stacked a second onto an entry whose body already ended in a blank, and the
    queue is append-only, so every drain ran through here.

    BELOW it: whatever the body already had, put back verbatim -- ORDER
    INCLUDED, which a pop-then-extend does not do. The tail is taken by slice
    for that reason: a tail mixing "" with a whitespace-only line is the only
    shape that can tell the two apart, and "verbatim" is the claim being made.
    Body lines run
    to the next ``## `` heading, so an entry's trailing blank IS the separator
    from the entry below it — a middle entry carries one and the last entry in
    the file carries none. Appending a fixed trailing blank welds nothing, but
    it invents an end-of-file blank line on the last entry and flattens an
    operator's deliberate double spacing, and this module's contract is that a
    write changes only what the operation names. Restoring the tail keeps the
    separator where one exists without authoring one where none did.
    """
    cut = len(entry.body_lines)
    while cut and not entry.body_lines[cut - 1].strip():
        cut -= 1
    tail = entry.body_lines[cut:]
    del entry.body_lines[cut:]
    entry.body_lines.append("")
    entry.body_lines.append(footer)
    entry.body_lines.extend(tail)


def mark_verified(entry: VerificationEntry, *, today: date | None = None) -> bool:
    """Flip pending → verified and append a ``**Verified:**`` line.

    Returns True when the entry carries ``verified`` on return, False when it
    was **refused** because its status line cannot be read — and a refusal
    leaves ``body_lines`` exactly as it found them, so the caller has written
    nothing. Render the reason from :attr:`VerificationEntry.status_defect`.

    Idempotent on already-verified entries (no-op, True). Refuses to verify an
    ``accepted`` entry — accept is a deliberate override and shouldn't be
    silently upgraded to verified.
    """
    if entry.status == _STATUS_VERIFIED:
        return True
    if entry.status == _STATUS_ACCEPTED:
        raise ValueError(
            f"Entry {entry.vrf_id} was accepted via --accept-pending-verification; "
            "verifying an accepted entry would erase the override rationale. "
            "If verification is now genuine, edit the file by hand."
        )
    today = today or date.today()
    if not _set_status_line(entry, _STATUS_VERIFIED):
        return False
    _append_drain_footer(entry, f"**Verified:** {today.isoformat()}")
    return True


def mark_accepted(
    entry: VerificationEntry,
    *,
    rationale: str,
    today: date | None = None,
) -> bool:
    """Flip pending → accepted and append a ``**Accepted:** ... rationale: ...`` line.

    Returns True when the entry needs nothing further, False when it was
    **refused** because its status line cannot be read — a refusal leaves
    ``body_lines`` untouched, so the caller has written nothing. Render the
    reason from :attr:`VerificationEntry.status_defect`.

    Idempotent on already-accepted entries (no-op). No-op on already-verified
    entries (a verified entry is drained — no rationale needed).
    """
    if entry.status in {_STATUS_ACCEPTED, _STATUS_VERIFIED}:
        return True
    if not rationale or not rationale.strip():
        raise ValueError(
            "Acceptance requires a non-empty rationale — the override "
            "is recorded in the queue file as the work-log entry."
        )
    today = today or date.today()
    if not _set_status_line(entry, _STATUS_ACCEPTED):
        return False
    _append_drain_footer(
        entry,
        f"**Accepted:** {today.isoformat()} — rationale: {rationale.strip()}",
    )
    return True


def count_pending(entries: list[VerificationEntry]) -> int:
    return sum(1 for e in entries if e.status == _STATUS_PENDING)


def pending_entries(entries: list[VerificationEntry]) -> list[VerificationEntry]:
    return [e for e in entries if e.status == _STATUS_PENDING]


def is_operator_verification_required(state_path: Path) -> bool:
    """Read ``operator_verification_required`` from ``project-state.yaml``.

    Column-0 scanner mirroring the convention shared with
    ``coverage_required`` (see
    ``core.read_bool_yaml_key``): only top-level keys count; commented-out
    and indented occurrences are ignored. Defaults to ``False`` when the file
    or key is absent — the explicit-opt-in posture for v1.4 enforcement features.
    """
    if not state_path.is_file():
        return False
    try:
        content = state_path.read_text(encoding="utf-8")
    except OSError:
        return False
    for raw in content.splitlines():
        if raw[:1] in (" ", "\t"):
            continue
        stripped = raw.split("#", 1)[0].rstrip()
        if stripped.startswith("operator_verification_required:"):
            return stripped.split(":", 1)[1].strip().lower() == "true"
    return False


def _load_queue(queue_path: Path) -> tuple[str, list[VerificationEntry]]:
    """Read the queue as utf-8 — the encoding :func:`_write_queue` writes.

    The two were previously self-inverse by accident: both used the locale
    encoding, so a mangled write was mangled back on read. Now that the shared
    writer is utf-8, a bare ``read_text()`` here would make the pair asymmetric
    and transcode a committed product file on the next status mutation.
    """
    if not queue_path.is_file():
        return "", []
    return parse_operator_verification(queue_path.read_text(encoding="utf-8"))


def _existing_line_ending(queue_path: Path) -> str:
    """The line terminator the queue file on disk already uses.

    Defaults to ``"\n"`` when the file does not exist or holds no newline yet:
    with nothing on disk to preserve there is nothing to infer from, and LF is
    what the repo commits. The point is to KEEP what a file already has, never
    to impose the writing machine's convention on it.

    **The limit, since the guarantee reads as unconditional otherwise:** this
    samples the FIRST terminator only, and the caller applies it to every line.
    A uniformly-LF or uniformly-CRLF queue round-trips exactly, which is the
    case this exists for. A file with MIXED endings is normalized to whichever
    came first — still a rewrite of lines nobody named, just from a rarer input.
    """
    try:
        raw = queue_path.read_bytes()
    except OSError:
        return "\n"
    idx = raw.find(b"\n")
    if idx > 0 and raw[idx - 1 : idx] == b"\r":
        return "\r\n"
    return "\n"


def _write_queue(
    queue_path: Path, preamble: str, entries: list[VerificationEntry]
) -> None:
    """Serialize the queue back, keeping the line endings it arrived with.

    ``atomic_write_text`` translates newlines by default, which is right for
    framework-owned state and wrong here: this file is operator-authored, and
    the default hands back a whole-file re-line-ending in exchange for a
    two-word status edit. That helper's own docstring asks any writer editing a
    file the product wrote to pass ``newline=""``; this call site is exactly
    that, so it does, and re-applies whatever terminator the file already used —
    the first one it finds, which is exact for a consistently-ended file and
    normalizing for a mixed one (see :func:`_existing_line_ending`).
    """
    text = format_operator_verification(preamble, entries)
    ending = _existing_line_ending(queue_path)
    if ending != "\n":
        text = text.replace("\n", ending)
    atomic_write_text(queue_path, text, newline="")


# =============================================================================
# Runners — JSON-mode callers (the ``prawduct-hook`` subcommands, the
# ``/prawduct:doctor`` and ``/prawduct:pr`` skills) see a consistent dict shape.
# =============================================================================


def run_check_operator_verification(product_dir: str | Path) -> dict:
    """Read-only gate check. Mirrors ``check-cumulative-critic`` semantics.

    Returns ``{"required", "pending", "queue_status", "unparsed_lines",
    "unparsed_status_entries", "queue_path", "first_pending", "message"}`` — the
    same keys on every branch, so a caller never has to know which one produced
    its result.

    ``unparsed_status_entries`` names the pending entries whose status could not
    be READ, a strict subset of ``pending``. It is reported separately because
    no remedy the blocking message can offer will move them, and counting them
    silently among genuinely-outstanding work is what let such an entry block a
    queue indefinitely with no clue why.

    The exit-code mapping is deliberately NOT restated here.
    ``api-contract.md`` § Error Model owns it, and a second copy is exactly what
    went stale: this sentence still described a two-outcome wrapper after the
    check grew a third.
    """
    product_path = Path(product_dir).resolve()
    prawduct_dir = product_path / ".prawduct"
    state_path = prawduct_dir / "project-state.yaml"
    queue_path = prawduct_dir / "operator-verification.md"

    required = is_operator_verification_required(state_path)
    if not required:
        return {
            "required": False,
            "pending": 0,
            "queue_status": QUEUE_OK,
            "unparsed_lines": 0,
            "unparsed_status_entries": [],
            "queue_path": str(queue_path),
            "first_pending": None,
            "message": (
                "operator-verification gate not required "
                "(operator_verification_required is false or unset)"
            ),
        }

    preamble, entries = _load_queue(queue_path)

    # A gate that could not read its input has not found an empty queue. The
    # preamble is where every line this parser failed to recognise ends up, and
    # discarding it here (the frame that actually loses the information) is what
    # let a 32-entry queue in another format report as drained while the gate
    # blocked on nothing. Scoped to the required case by construction — the
    # not-required branch returned above — so only a repo that opted into this
    # gate can be stopped by it, which is where being stopped is correct.
    if not entries:
        unparsed = unparsed_content_lines(preamble)
        if unparsed:
            return {
                "required": True,
                "pending": 0,
                "queue_status": QUEUE_UNREADABLE,
                "unparsed_lines": len(unparsed),
                "unparsed_status_entries": [],
                "queue_path": str(queue_path),
                "first_pending": None,
                "message": (
                    f"blocking: parsed 0 entries from a queue file that is not "
                    f"empty — {len(unparsed)} line(s) in {queue_path} were not "
                    "recognised as entries. An entry is a level-2 heading "
                    "`## VRF-<id> - <title>` whose first body line is "
                    "`**Status:** pending|verified|accepted`. This is NOT a "
                    "clear queue: nothing was read, so nothing could be found "
                    "pending.\n"
                    "DO NOT rewrite the queue to satisfy this check. It is an "
                    "operator-authored record and reformatting it is a silent "
                    "edit nobody reviewed - report the mismatch to the operator "
                    "and let them decide."
                ),
            }

    pending = pending_entries(entries)
    if not pending:
        return {
            "required": True,
            "pending": 0,
            "queue_status": QUEUE_OK,
            "unparsed_lines": 0,
            "unparsed_status_entries": [],
            "queue_path": str(queue_path),
            "first_pending": None,
            "message": (
                f"operator-verification queue is empty ({queue_path})"
                if queue_path.is_file()
                else f"operator-verification queue is empty (no queue file at {queue_path})"
            ),
        }
    first = pending[0]
    # Entries counted pending only because their status line could not be read.
    # They are the reason this survey exists: the drain remedy named below
    # provably cannot move them, so offering it and nothing else is how an
    # operator spends weeks re-running a command that refuses every time.
    defective = [e for e in pending if e.status_defect is not None]
    drainable = [e for e in pending if e.status_defect is None]
    message = (
        f"blocking: {len(pending)} pending operator-verification "
        f"entr{'y' if len(pending) == 1 else 'ies'} "
        f"({first.vrf_id}{', ...' if len(pending) > 1 else ''})."
    )
    if not defective:
        message += (
            " Drain via `prawduct-hook verify-operator-verification <ID>` "
            "or override with `/prawduct:pr create --accept-pending-verification \"rationale\"`."
        )
    else:
        # Name only the remedies that can actually run. The override is
        # all-or-nothing across the pending set, so ONE unreadable entry stops
        # it for every entry — offering it here would be the same defect this
        # block exists to close, one level up.
        ids = ", ".join(e.vrf_id for e in defective)
        if drainable:
            message += (
                f" {len(drainable)} can be drained via `prawduct-hook "
                "verify-operator-verification <ID>`."
            )
        message += (
            f"\n\n{len(defective)} "
            f"entr{'y' if len(defective) == 1 else 'ies'} cannot be drained or "
            f"overridden at all until edited by hand: {ids}. "
            f"{'Its' if len(defective) == 1 else 'Their'} status counts as "
            "pending because it could not be READ, which is not the same as "
            "work that is genuinely outstanding. The per-PR override is "
            "unavailable while "
            "any of them remain — it covers every pending entry or none, so "
            "that a recorded bypass never quietly skips one.\n\n"
            f"Taking {defective[0].vrf_id} as the example:\n"
            + describe_status_defect(defective[0].vrf_id, defective[0].status_defect)
        )
    return {
        "required": True,
        "pending": len(pending),
        "queue_status": QUEUE_OK,
        "unparsed_lines": 0,
        "unparsed_status_entries": [e.vrf_id for e in defective],
        "queue_path": str(queue_path),
        "first_pending": first.vrf_id,
        "message": message,
    }


def run_verify_entry(
    product_dir: str | Path,
    vrf_id: str,
    *,
    today: date | None = None,
) -> dict:
    """Drain a single pending entry to ``verified``.

    Returns ``{"product_dir", "vrf_id", "previous_status", "status",
    "queue_path", "actions": [str], "notes": [str]}`` or
    ``{"error": "..."}`` on any refusal, whose text is the operator-facing
    reason (a lookup that found nothing, and any entry this operation declines
    to write).
    """
    product_path = Path(product_dir).resolve()
    prawduct_dir = product_path / ".prawduct"
    if not prawduct_dir.is_dir():
        return {
            "error": (
                f"Not a prawduct product: {product_path} has no .prawduct/ directory"
            )
        }

    queue_path = prawduct_dir / "operator-verification.md"
    if not queue_path.is_file():
        return {
            "error": (
                f"No operator-verification queue at {queue_path}. "
                "Enable the gate by setting `operator_verification_required: true` in "
                "`.prawduct/project-state.yaml` (see `/prawduct:doctor`); the queue is "
                "populated as visual / live-integration chunks enqueue entries."
            )
        }

    preamble, entries = _load_queue(queue_path)
    target = next((e for e in entries if e.vrf_id == vrf_id), None)
    if target is None:
        known = [e.vrf_id for e in entries]
        return {
            "error": (
                f"Unknown verification ID {vrf_id!r}. "
                f"Known IDs in {queue_path}: {known if known else '(empty queue)'}"
            )
        }

    previous_status = target.status
    actions: list[str] = []
    notes: list[str] = []

    if previous_status == _STATUS_VERIFIED:
        notes.append(
            f"{vrf_id} is already verified — no change. Edit the queue file "
            "directly if the entry needs to be re-opened."
        )
    elif previous_status == _STATUS_ACCEPTED:
        return {
            "error": (
                f"{vrf_id} was accepted via --accept-pending-verification; "
                "verifying an accepted entry would erase the override rationale. "
                "Edit the file by hand if the verification is now genuine."
            )
        }
    else:
        # Branch on the mutator's answer. It reports refusal rather than
        # raising, and the whole defect this guards was the previous caller
        # ignoring it: the write below ran regardless, so a status that never
        # moved got a `**Verified:**` footer and an operator got told it worked.
        if not mark_verified(target, today=today):
            return {
                "error": describe_status_defect(vrf_id, target.status_defect)
                + "\n\nNothing was changed."
            }
        _write_queue(queue_path, preamble, entries)
        actions.append(
            f"Marked {vrf_id} verified in {queue_path.relative_to(product_path)}"
        )

    return {
        "product_dir": str(product_path),
        "vrf_id": vrf_id,
        "previous_status": previous_status,
        "status": target.status,
        "queue_path": str(queue_path),
        "actions": actions,
        "notes": notes,
    }


def run_accept_pending(
    product_dir: str | Path,
    rationale: str,
    *,
    today: date | None = None,
) -> dict:
    """Flip all pending entries to ``accepted`` with the supplied rationale.

    Used by ``/prawduct:pr create --accept-pending-verification "rationale"`` — the
    override is recorded in the queue file itself so the work-log shows
    why the gate was bypassed for this PR.

    Returns ``{"product_dir", "accepted_ids": [str], "queue_path",
    "actions", "notes"}`` or ``{"error": "..."}``.
    """
    product_path = Path(product_dir).resolve()
    prawduct_dir = product_path / ".prawduct"
    if not prawduct_dir.is_dir():
        return {
            "error": (
                f"Not a prawduct product: {product_path} has no .prawduct/ directory"
            )
        }
    if not rationale or not rationale.strip():
        return {
            "error": (
                "Rationale required: `/prawduct:pr create --accept-pending-verification` "
                "must record why the operator-verification gate was bypassed."
            )
        }

    queue_path = prawduct_dir / "operator-verification.md"
    preamble, entries = _load_queue(queue_path)
    pending = pending_entries(entries)

    # The override reaches the same queue by a different door, so it inherits
    # the same defect: with nothing parsed it would report the gate "already
    # satisfied" and record `accepted_ids: []` — an override that overrode
    # nothing, on entries nobody read. Refusing here matters more than in the
    # check, because this is the path an operator takes when they have DECIDED
    # to bypass the gate, and a bypass that silently covers zero entries is a
    # recorded decision about work that was never seen.
    if not entries and unparsed_content_lines(preamble):
        return {
            "error": (
                f"Cannot accept: parsed 0 entries from a queue file that is not "
                f"empty ({queue_path}). Nothing was read, so there is nothing to "
                "accept and an override here would record a bypass covering no "
                "entries. Fix the queue's format — an entry is a level-2 heading "
                "`## VRF-<id> - <title>` whose first body line is "
                "`**Status:** pending|verified|accepted` — or clear "
                "`operator_verification_required`. Do NOT reformat the queue on "
                "the operator's behalf."
            )
        }

    if not pending:
        return {
            "product_dir": str(product_path),
            "accepted_ids": [],
            "queue_path": str(queue_path),
            "actions": [],
            "notes": [
                "No pending entries to accept — operator-verification gate "
                "already satisfied."
            ],
        }

    accepted_ids: list[str] = []
    for entry in pending:
        # All-or-nothing by construction: the single write is after the loop, so
        # returning here leaves the file untouched and the entries mutated so
        # far are discarded with the in-memory list. An override that covered
        # every entry but one, silently, would record a decision about work
        # nobody read — the same failure the unreadable-queue refusal above
        # exists to prevent, arriving one entry at a time instead of all at once.
        if not mark_accepted(entry, rationale=rationale, today=today):
            return {
                "error": describe_status_defect(entry.vrf_id, entry.status_defect)
                + "\n\nNothing was changed and no entries were accepted — this "
                "override covers every "
                "pending entry or none, so that a recorded bypass never quietly "
                "skips one."
            }
        accepted_ids.append(entry.vrf_id)

    _write_queue(queue_path, preamble, entries)

    return {
        "product_dir": str(product_path),
        "accepted_ids": accepted_ids,
        "queue_path": str(queue_path),
        "actions": [
            f"Marked {vid} accepted in {queue_path.relative_to(product_path)}"
            for vid in accepted_ids
        ],
        "notes": [
            f"Rationale recorded in {queue_path.name} for {len(accepted_ids)} "
            "entr" + ("y" if len(accepted_ids) == 1 else "ies") + "."
        ],
    }
