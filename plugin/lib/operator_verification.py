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
        for raw in self.body_lines:
            stripped = raw.strip()
            if not stripped:
                continue
            match = _STATUS_LINE_RE.match(stripped)
            if not match:
                # First non-blank body line that isn't a Status line means
                # the entry is malformed — treat as pending so the gate
                # surfaces it rather than silently passing.
                return _STATUS_PENDING
            status = match.group("status").lower()
            return status if status in _VALID_STATUSES else _STATUS_PENDING
        return _STATUS_PENDING


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

    preamble = "\n".join(preamble_lines)
    if preamble and not preamble.endswith("\n"):
        preamble += "\n"
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
    """Rewrite the first ``**Status:**`` line in place.

    Returns True if the status line was found and changed, False otherwise.
    Used by ``mark_verified`` and ``mark_accepted`` — the caller appends
    timestamp/rationale lines after this returns.
    """
    for idx, raw in enumerate(entry.body_lines):
        match = _STATUS_LINE_RE.match(raw.strip())
        if match:
            entry.body_lines[idx] = f"**Status:** {new_status}"
            return True
    return False


def mark_verified(entry: VerificationEntry, *, today: date | None = None) -> None:
    """Flip pending → verified and append a ``**Verified:**`` line.

    Idempotent on already-verified entries (no-op). Refuses to verify an
    ``accepted`` entry — accept is a deliberate override and shouldn't be
    silently upgraded to verified.
    """
    if entry.status == _STATUS_VERIFIED:
        return
    if entry.status == _STATUS_ACCEPTED:
        raise ValueError(
            f"Entry {entry.vrf_id} was accepted via --accept-pending-verification; "
            "verifying an accepted entry would erase the override rationale. "
            "If verification is now genuine, edit the file by hand."
        )
    today = today or date.today()
    _set_status_line(entry, _STATUS_VERIFIED)
    entry.body_lines.append("")
    entry.body_lines.append(f"**Verified:** {today.isoformat()}")


def mark_accepted(
    entry: VerificationEntry,
    *,
    rationale: str,
    today: date | None = None,
) -> None:
    """Flip pending → accepted and append a ``**Accepted:** ... rationale: ...`` line.

    Idempotent on already-accepted entries (no-op). No-op on already-verified
    entries (a verified entry is drained — no rationale needed).
    """
    if entry.status in {_STATUS_ACCEPTED, _STATUS_VERIFIED}:
        return
    if not rationale or not rationale.strip():
        raise ValueError(
            "Acceptance requires a non-empty rationale — the override "
            "is recorded in the queue file as the work-log entry."
        )
    today = today or date.today()
    _set_status_line(entry, _STATUS_ACCEPTED)
    entry.body_lines.append("")
    entry.body_lines.append(
        f"**Accepted:** {today.isoformat()} — rationale: {rationale.strip()}"
    )


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


def _write_queue(
    queue_path: Path, preamble: str, entries: list[VerificationEntry]
) -> None:
    atomic_write_text(
        queue_path, format_operator_verification(preamble, entries)
    )


# =============================================================================
# Runners — JSON-mode callers (the ``prawduct-hook`` subcommands, the
# ``/prawduct:doctor`` and ``/prawduct:pr`` skills) see a consistent dict shape.
# =============================================================================


def run_check_operator_verification(product_dir: str | Path) -> dict:
    """Read-only gate check. Mirrors ``check-cumulative-critic`` semantics.

    Returns ``{"required", "pending", "queue_status", "unparsed_lines",
    "queue_path", "first_pending", "message"}`` — the same keys on every branch,
    so a caller never has to know which one produced its result.

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
            "queue_path": str(queue_path),
            "first_pending": None,
            "message": (
                f"operator-verification queue is empty ({queue_path})"
                if queue_path.is_file()
                else f"operator-verification queue is empty (no queue file at {queue_path})"
            ),
        }
    first = pending[0]
    return {
        "required": True,
        "pending": len(pending),
        "queue_status": QUEUE_OK,
        "unparsed_lines": 0,
        "queue_path": str(queue_path),
        "first_pending": first.vrf_id,
        "message": (
            f"blocking: {len(pending)} pending operator-verification "
            f"entr{'y' if len(pending) == 1 else 'ies'} "
            f"({first.vrf_id}{', ...' if len(pending) > 1 else ''}). "
            f"Drain via `prawduct-hook verify-operator-verification <ID>` "
            "or override with `/prawduct:pr create --accept-pending-verification \"rationale\"`."
        ),
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
    ``{"error": "..."}`` on lookup failures (no ``.prawduct/``, no queue
    file, unknown ID).
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
        mark_verified(target, today=today)
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
        mark_accepted(entry, rationale=rationale, today=today)
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
