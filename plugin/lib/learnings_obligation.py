"""The descent obligation in a product's ``learnings.md`` — its one home, plus the
detector and the offered repair for a product that never received it.

``/prawduct:learnings`` ends by telling its caller to apply "the obligation stated
in ``.prawduct/learnings.md``'s header, marked ``prawduct:descent-obligation``" —
deliberately a *pointer*, so the statement has one home rather than a copy in the
skill and another in every product. The pointer only resolves if the product's
learnings file actually carries the marker, and until now exactly one path wrote it:
``init_product``'s starter corpus, guarded by ``if not learnings.is_file()``. Every
repo onboarded before that guard, and every repo that arrived by migration or by
hand-authoring its learnings file, got the instruction and no target (#351). The
defect is closed for the empty set and open for the real one — the live fleet is
entirely already-onboarded, and nothing backfills it.

So this module owns three things:

* :data:`OBLIGATION_BLOCK` — the prose, consumed by the scaffold (``init_product``)
  and by the repair, so a reworded obligation cannot reach new products and skip
  repaired ones.
* :func:`check` — does this product's learnings file carry the marker, **above the
  first rule**? Position is not a refinement of presence, it is the other half of
  it: a reader who meets the obligation after the rules it governs has met it too
  late, which is precisely the inertness the statement exists to prevent.
* :func:`repair` — the offered insertion, dry-run by default.

**The repair is insert-only, and that is a constraint, not an implementation
detail.** ``learnings.md`` is the product's own authored corpus — place-once state
the framework creates and never re-touches. Inserting a block the framework already
ships to new products is a bounded, reviewable act; rewriting, reordering, or
deleting a line the owner wrote is not, and no repair here does it. The consequence
is deliberate: a *misplaced* marker is reported and declined rather than moved,
because moving it means deleting a line. The owner moves it.
"""

from __future__ import annotations

from pathlib import Path

from . import core

#: What the skill points at and the guards key on. The marker is the mechanism; the
#: prose beneath it is free to be reworded (a test that matched the wording would
#: pass for every rewrite of the same defect), and a product may rewrite it entirely.
MARKER = "prawduct:descent-obligation"

#: Where a product's learnings corpus lives, repo-relative.
LEARNINGS_REL = ".prawduct/learnings.md"

#: The obligation's one home: the marker comment plus the statement it introduces.
#: Written by ``init_product`` into a new product's starter corpus and by
#: :func:`repair` into an existing product's. Ends with a newline; the caller
#: supplies surrounding blank lines.
OBLIGATION_BLOCK = (
    "<!-- prawduct:descent-obligation — the statement below is the HOME of the\n"
    "     descent rule; `/prawduct:learnings` points here rather than restating\n"
    "     it. Reword the prose freely; keep this marker, above the first rule. -->\n"
    "\n"
    "**Reading a rule is not applying it.** The failure mode of a learnings file "
    "is not absence, it is assent: a rule arrives at the right moment, is read, "
    "is agreed with, and changes nothing, because nothing made you recognize the "
    "case in hand as an instance of it. So for any rule you read here, name the "
    "decision you are about to make and say what the rule changes about it — or "
    "say that it does not apply, which is also an answer.\n"
)

#: Statuses :func:`check` reports. ``ok`` and ``missing`` are the two states a
#: healthy fleet moves between; the other three are all "declined", for three
#: different reasons the owner needs told apart.
STATUS_OK = "ok"
STATUS_MISSING = "missing"
STATUS_MISPLACED = "misplaced"
STATUS_ABSENT = "absent"
STATUS_UNREADABLE = "unreadable"


def _first_rule_index(lines: list[str]) -> int | None:
    """Index of the first ``## `` rule heading, or ``None`` when there are no rules.

    ``## `` is the corpus's rule heading — the same anchor ``audit-learnings`` walks
    and the framework repo's own position guard reads, so the detector and the
    lifecycle audit agree about where the rules start.
    """
    return next((i for i, line in enumerate(lines) if line.startswith("## ")), None)


def _read_text(path: Path) -> str | None:
    """The file's exact decoded text, or ``None`` when it cannot be read.

    ``newline=""`` disables universal-newline translation, so a CRLF corpus
    arrives with its ``\\r`` intact instead of silently becoming LF in memory
    and LF on disk at the next write. This is the OWNER'S authored corpus, and
    :func:`repair` writes it back — a read that normalises is a write that
    rewrites every line.
    """
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError):
        return None


def _split_lines(text: str) -> list[str]:
    """``text`` as lines, splitting on ``\\n`` ONLY — never ``splitlines()``.

    :func:`repair` turns a line index into a **byte offset** into the raw text
    (``sum(len(line) + 1)``), so the split has to account for exactly one
    character per break. ``str.splitlines()`` breaks that twice over: it also
    splits on ``\\v``, ``\\f``, ``\\x1c``-``\\x1e``, ``\\x85``, ``U+2028`` and
    ``U+2029``, and it consumes ``\\r\\n`` as a single break though it is two
    characters — either way the arithmetic drifts and the block lands somewhere
    the dry run did not name. Splitting on ``\\n`` leaves the exotic separators
    inside their line and leaves a CRLF line's ``\\r`` as its last character, so
    the ending travels with the line it belongs to.

    (Under an earlier design that rebuilt the file from this list, the same
    choice mattered for a second reason — a rejoin on ``\\n`` would have replaced
    every one of those separators with a newline. The raw-text splice removed
    that hazard; the offset one is why the rule still stands.)

    The trailing ``""`` that ``split`` produces for a file ending in a newline is
    dropped, so indices mean what ``_insertion`` and the 1-based
    ``insert_before_line`` assume.
    """
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _line_ending(text: str) -> str:
    """The corpus's own line ending, so an inserted block matches it.

    CRLF only when the file is *consistently* CRLF; a mixed file gets ``\\n``,
    because guessing on a file that already disagrees with itself would just
    pick a side.
    """
    crlf = text.count("\r\n")
    return "\r\n" if crlf and crlf == text.count("\n") else "\n"


def _read_lines(path: Path) -> list[str] | None:
    """The file's lines, or ``None`` when it cannot be read as text."""
    text = _read_text(path)
    return None if text is None else _split_lines(text)


def check(project_dir: str | Path) -> dict:
    """Grade a product's ``learnings.md`` for the descent obligation.

    Returns ``{"status", "path", "marker", "detail", "marker_lines", "first_rule_line"}``.
    Line numbers are 1-based for human output, ``None`` when the thing is absent.

    The statuses, and why each is its own answer rather than a boolean:

    **The home is the FIRST occurrence of the marker**, which is the rule the
    framework repo's own position guard already uses. An earlier cut graded on
    *every* occurrence, reasoning that one well-placed marker should not excuse a
    second copy further down — but the marker is an ordinary string, and a product
    that writes a rule *about* the obligation (a natural thing for a prawduct-derived
    corpus to do) then earns ``misplaced``: the one status the repair declines, so
    doctor tells an owner to move a block that is already in the right place and
    offers nothing. A dead-end verdict on a healthy corpus is how a check teaches its
    reader to skip it. Duplicate-copy detection was never asked for and is not worth
    that; the first occurrence decides.

    ``ok``
        A marker exists above the first rule.
    ``missing``
        No marker anywhere — ``/prawduct:learnings`` ships this product an
        instruction aimed at a hole. Repairable.
    ``misplaced``
        The first marker sits at or below the first rule. Not repairable here:
        fixing it means moving a line, and this repair only ever inserts.
    ``absent``
        No ``learnings.md`` at all. Reported, not repaired — a missing core-state
        file is the health check's own finding (doctor #5), and scaffolding one from
        a repair path would paper over it.
    ``unreadable``
        Present but not decodable as UTF-8 text. Declined rather than guessed at.
    """
    path = Path(project_dir) / LEARNINGS_REL
    base = {"path": LEARNINGS_REL, "marker": MARKER, "marker_lines": [], "first_rule_line": None}

    if not path.is_file():
        return {
            **base,
            "status": STATUS_ABSENT,
            "detail": (
                f"no {LEARNINGS_REL} in this repo — the learnings corpus is core "
                "state (doctor Health Check #5 owns its absence); nothing to grade "
                "for the descent obligation until it exists."
            ),
        }

    lines = _read_lines(path)
    if lines is None:
        return {
            **base,
            "status": STATUS_UNREADABLE,
            "detail": (
                f"{LEARNINGS_REL} could not be read as UTF-8 text — reporting rather "
                "than guessing at its structure."
            ),
        }

    marker_at = [i for i, line in enumerate(lines) if MARKER in line]
    first_rule = _first_rule_index(lines)
    found = {
        **base,
        "marker_lines": [i + 1 for i in marker_at],
        "first_rule_line": None if first_rule is None else first_rule + 1,
    }

    if not marker_at:
        return {
            **found,
            "status": STATUS_MISSING,
            "detail": (
                f"{LEARNINGS_REL} carries no `{MARKER}` marker, so "
                "/prawduct:learnings points every reader of this product at a "
                "statement that is not there."
            ),
        }

    if first_rule is not None and marker_at[0] >= first_rule:
        return {
            **found,
            "status": STATUS_MISPLACED,
            "detail": (
                f"the first `{MARKER}` marker is at line {marker_at[0] + 1}, at or "
                f"below the first rule (line {first_rule + 1}) — a reader meets the "
                "obligation after the rules it governs, which is the inertness it "
                "exists to prevent. Move the block above the first rule; this repair "
                "inserts only and will not move or delete an authored line."
            ),
        }

    return {
        **found,
        "status": STATUS_OK,
        "detail": f"the `{MARKER}` marker is present and above the first rule.",
    }


def _insertion(lines: list[str]) -> tuple[int, str]:
    """Where the block goes and what gets written, as ``(index, text)``.

    Immediately **above the first rule** — the position the starter corpus already
    puts it in, so a repaired product ends up shaped like a newly-scaffolded one
    rather than like a third variant. That is the last thing a reader passes before
    the rules the obligation governs, which is where a standing read-instruction
    does its work. With no rules yet, it goes at the end of the preamble (the same
    place, in a file whose rules have not been written).

    Blank-line hygiene is part of the insertion, not cosmetics: a block welded to
    the preceding paragraph renders as one run-on paragraph in every markdown
    reader, and the marker comment would stop introducing anything.
    """
    first_rule = _first_rule_index(lines)
    at = len(lines) if first_rule is None else first_rule
    block = OBLIGATION_BLOCK.splitlines()
    before_needs_blank = at > 0 and lines[at - 1].strip() != ""
    after_needs_blank = at < len(lines) and lines[at].strip() != ""
    new = ([""] if before_needs_blank else []) + block + ([""] if after_needs_blank else [])
    return at, "\n".join(new)


def repair(project_dir: str | Path, *, apply: bool = False) -> dict:
    """Offer (``apply=False``) or perform (``apply=True``) the obligation insertion.

    Returns :func:`check`'s keys plus ``repairable``, ``applied``,
    ``insert_before_line`` (the 1-based line the block goes above — one past the end
    when the corpus has no rules yet), and ``insert_text`` — the exact lines that
    would be, or were, written.

    **Dry run is the confirmation seam, not a rehearsal.** It exists because the
    target is a file the framework did not author: the security model requires an
    informed confirmation naming what changes, and printing the exact text at the
    exact line IS that naming. (The corpus's own warning about dry runs — that one
    validating identically to the real run is where drift hides — is about a *check*
    standing in for a later write by another actor. Here the command is the
    operation and ``--apply`` is the owner's yes.)

    Only ``missing`` is repairable. ``ok`` is an idempotent no-op — the point of a
    repair the fleet may run more than once — and the three declined statuses stay
    declined, each carrying the reason :func:`check` gave.
    """
    result = check(project_dir)
    result.update({"repairable": result["status"] == STATUS_MISSING, "applied": False,
                   "insert_before_line": None, "insert_text": None})
    if not result["repairable"]:
        return result

    path = Path(project_dir) / LEARNINGS_REL
    raw = _read_text(path)
    if raw is None:  # raced between check() and here
        result.update({"status": STATUS_UNREADABLE, "repairable": False,
                       "detail": f"{LEARNINGS_REL} became unreadable; nothing written."})
        return result
    lines = _split_lines(raw)

    at, text = _insertion(lines)
    result["insert_before_line"] = at + 1
    result["insert_text"] = text
    if not apply:
        return result

    # Splice the block into the RAW text at a character offset rather than
    # rebuilding the file from a list of lines. Everything outside the insertion
    # is then the owner's bytes verbatim — their line endings, their trailing
    # newline or lack of one, any separator character `splitlines()` would have
    # eaten. Rebuilding cannot promise that: it re-emits every line, so the
    # insert-only constraint this module states about itself would hold for the
    # *content* of each line and quietly fail for its bytes.
    eol = _line_ending(raw)
    offset = min(sum(len(line) + 1 for line in lines[:at]), len(raw))
    head, tail = raw[:offset], raw[offset:]
    if head and not head.endswith("\n"):
        head += eol  # an unterminated last line has to be closed before appending
    body = head + text.replace("\n", eol) + eol + tail
    try:
        # Atomic (tmp sibling + os.replace) via the shared writer, not because a
        # reader of this file fails open — nothing reads it as state — but because
        # the file is the OWNER'S authored corpus. A torn write on the framework's
        # own state costs a regenerated file; here it costs prose nobody else has.
        # utf-8 and newline="" are passed EXPLICITLY: the shared writer's defaults
        # are the locale encoding and newline translation (`#562`), which on a
        # cp1252 or latin-1 host would encode this block cleanly and silently
        # re-encode every non-ASCII character the OWNER wrote — a corruption that
        # succeeds, leaving the next check() to report `unreadable` against a
        # corpus this repair broke.
        core.atomic_write_text(path, body, encoding="utf-8", newline="")
    except (OSError, UnicodeError) as exc:
        # With the encode pinned to utf-8, UnicodeError is no longer the locale
        # gap — it is a genuine "this text cannot be encoded" (a lone surrogate
        # carried in from elsewhere). Rare, but this module promises "reported,
        # never half-applied", and a traceback is not a report.
        result.update({"repairable": False,
                       "detail": f"could not write {LEARNINGS_REL}: {exc}"})
        return result
    result.update({"applied": True, "status": STATUS_OK,
                   "detail": f"inserted the `{MARKER}` block above line {at + 1}."})
    return result
