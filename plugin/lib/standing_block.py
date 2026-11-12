"""The close's vocabulary, and how to read its verdict off a turn.

A turn that ends a work cycle or leaves work outstanding closes on ONE line:
a DISPOSITION label, a CLEAR verdict, then a short reason —
``RUNNING · DO NOT CLEAR — the review is in flight, about 4 minutes``, with
the labels backticked (``methodology/session-hygiene.md`` owns the shape;
``methodology/session-digest.md`` injects it into every session). The line is
last unless the turn needs the user: then the ASKS BLOCK follows it and ends
the turn — the :data:`ASKS_HEADER` line, then the numbered asks — so what the
reader must do is the last thing they see. This module is the one code home
for the labels and the header. The prose names them; a test pins the prose to
the constants below in both directions, so a label or the header renamed in
either place fails rather than drifting.

Sessions on an older digest still close with the three-paragraph form — a
``---`` rule, then paragraphs led by ``STATE``, the disposition and the
verdict — so that form is read too: a turn whose last line is not a one-line
close, and which has no asks block, is read the old way.

Code reads the close for one reason: the Stop hook fires at EVERY turn end, but
its reflection and Critic gates are about SESSION end, and the agent's clear
verdict is the agent's own statement of which one this is. A turn that says
``RUNNING`` and ``DO NOT CLEAR`` is telling the user it is still working, so
those gates defer to the next turn that does not
(``lib/gates.turn_declares_in_flight``).

Because that reading relaxes an authority gate, it is deliberately narrow — a
verdict counts only where the close puts it:

* the ONE-LINE close is the turn's last non-blank line, and only when it
  BEGINS with a disposition label followed directly (across markdown
  decoration and at most one separator such as ``·``, ``/``, ``|`` or a dash)
  by a clear label;
* when the turn has an ASKS BLOCK — a line that LEADS, after markdown
  decoration only, with :data:`ASKS_HEADER`, and everything after it — the
  one-line close is instead the last non-blank line BEFORE that header, and
  nothing inside the block is read. Two header lines, or a header with no line
  before it, yield no verdict, and the three-paragraph form is not read;
* otherwise, the three-paragraph close: the CLOSING BLOCK is the text after
  the last ``---`` rule line (with no rule, the final paragraph alone), and
  the verdict is its FINAL paragraph, only if that paragraph BEGINS with a
  clear label;
* a close naming BOTH clear labels — on the line, or anywhere in the block —
  is ambiguous and yields no verdict.

So a label quoted mid-prose or inside the asks, a verdict followed by further
text other than the asks block, a close separated from the asks block by
anything, or a close that says both, all read as "no verdict" — which the gate
treats as a session end and blocks. Labels and the header match
case-sensitively: the close's labels are upper-case tokens, and lower-case
"do not clear" in a sentence is prose.

The two labels are not independent. ``DO NOT CLEAR`` says something a clear
would kill is in flight. ``COMPLETE`` says nothing is, so it owes
``SAFE TO CLEAR``. ``YOUR TURN`` hands the session to someone who may read it
hours or days later, so it owes ``SAFE TO CLEAR`` too, unless that work really
is running: whatever only the conversation holds is written to disk before the
turn is handed over. :func:`contradiction` names a handed-over disposition
paired with ``DO NOT CLEAR``. It reads the text alone, so the Stop hook decides
whether the work behind a ``YOUR TURN`` is observable.

``SAFE TO CLEAR`` is a claim about disk and process state, so its stated reason
must point at something a clear leaves behind. A reason that points at the turn
itself ("the questions are in this message") names the one thing a clear
deletes; :func:`self_citation` finds it so the Stop hook can record it.

Under any verdict, the reason says what the asks are, or nothing — never where
they are. A reason that points by position ("the one ask above is for you")
sends the reader searching, and once the asks follow the close, an "above"
points the wrong way; :func:`positional_pointer_match` finds it so the Stop
hook can record it too.
"""

from __future__ import annotations

import re

RUNNING = "RUNNING"
YOUR_TURN = "YOUR TURN"
COMPLETE = "COMPLETE"

SAFE_TO_CLEAR = "SAFE TO CLEAR"
DO_NOT_CLEAR = "DO NOT CLEAR"

#: The disposition line: exactly one, chosen by what produces the next turn.
DISPOSITION_LABELS: tuple[str, ...] = (RUNNING, YOUR_TURN, COMPLETE)

#: The clear line: exactly one, the verdict on what survives a clear.
CLEAR_LABELS: tuple[str, ...] = (SAFE_TO_CLEAR, DO_NOT_CLEAR)

#: The dispositions that hand the session over — to the person, or to nobody.
#: ``COMPLETE`` always owes ``SAFE TO CLEAR``; ``YOUR TURN`` does unless work a
#: clear would kill is running, which ``cmd_stop`` decides from what it observes.
HANDED_OVER_DISPOSITIONS: tuple[str, ...] = (YOUR_TURN, COMPLETE)


def handed_over_reason(disposition_label: str) -> str:
    """The reason the clear-verdict check records for a handed-over disposition
    it found paired with ``DO NOT CLEAR`` (``handed-over-your-turn``, ...)."""
    return "handed-over-" + disposition_label.lower().replace(" ", "-")


#: Every reason the clear-verdict check can record.
CLEAR_VERDICT_REASONS: tuple[str, ...] = tuple(
    handed_over_reason(d) for d in HANDED_OVER_DISPOSITIONS
)

#: Every label the close uses, in the order the close states them.
ALL_LABELS: tuple[str, ...] = (*DISPOSITION_LABELS, *CLEAR_LABELS)

#: The header that opens the asks block — what the turn needs from the user,
#: numbered, after the one-line close and last in the turn. Only a line that
#: LEADS with it (after markdown decoration) opens the block.
ASKS_HEADER = "**Needs you:**"

# A horizontal-rule line: three or more dashes and nothing else.
_RULE_LINE = re.compile(r"^\s*-{3,}\s*$")

# Markdown decoration allowed in front of a label: emphasis, code ticks,
# a blockquote marker. Anything else before the label means the paragraph
# does not LEAD with it.
_LEADING_DECORATION = re.compile(r"^[\s>*_`]*")

# Between the one-line close's two labels: decoration, and at most one
# separator. A word there means the disposition was prose ("RUNNING the suite,
# so DO NOT CLEAR"), not a close.
_LINE_SEPARATOR = re.compile(r"^[\s*_`]*(?:[\u00b7\u2022|/+,;:\u2014\u2013-][\s*_`]*)?")


def _paragraphs(text: str) -> list[str]:
    """Non-empty paragraphs, split on blank lines."""
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def closing_block(text: str) -> str:
    """The three-paragraph close's region of a turn: after the last ``---``
    rule line, or the final paragraph when the turn has no rule. Empty for
    empty input."""
    if not isinstance(text, str) or not text.strip():
        return ""
    lines = text.splitlines()
    for idx in range(len(lines) - 1, -1, -1):
        if _RULE_LINE.match(lines[idx]):
            return "\n".join(lines[idx + 1:]).strip()
    paragraphs = _paragraphs(text)
    return paragraphs[-1] if paragraphs else ""


def _lead(paragraph: str, labels: tuple[str, ...]) -> "tuple[str, int] | None":
    """``(label, end)`` for the label ``paragraph`` LEADS with, from ``labels``
    — after markdown decoration only, and not when the label is the prefix of
    a longer word. ``end`` is the index just past the label."""
    start = _LEADING_DECORATION.match(paragraph).end()
    lead = paragraph[start:]
    for label in labels:
        if not lead.startswith(label):
            continue
        after = lead[len(label):len(label) + 1]
        if after and (after.isalnum() or after == "_"):
            continue  # a longer word that merely starts with the label
        return label, start + len(label)
    return None


def _leading_label(paragraph: str, labels: tuple[str, ...]) -> str | None:
    """The label ``paragraph`` LEADS with, from ``labels`` (:func:`_lead`)."""
    found = _lead(paragraph, labels)
    return found[0] if found else None


# The header with its decoration stripped: what a line must lead with.
_ASKS_HEADER_TEXT = ASKS_HEADER.strip("*_`")


def _opens_asks(line: str) -> bool:
    """Whether ``line`` LEADS with :data:`ASKS_HEADER`, after markdown
    decoration only — so a header named mid-sentence opens nothing."""
    return line[_LEADING_DECORATION.match(line).end():].startswith(_ASKS_HEADER_TEXT)


def _asks_start(lines: list[str]) -> "int | None":
    """The index in ``lines`` (non-blank, stripped) of the line opening the
    asks block, or ``None`` when no line does. ``-1`` when the block cannot be
    placed — more than one header line, which leaves which block is the asks
    ambiguous."""
    starts = [idx for idx, line in enumerate(lines) if _opens_asks(line)]
    if not starts:
        return None
    return starts[0] if len(starts) == 1 else -1


def _close_line(line: str) -> "tuple[str, str | None, str] | None":
    """``(disposition, verdict, line)`` when ``line`` is a one-line close,
    else ``None``. ``verdict`` is ``None`` when the line names both clear
    labels: it is still the close, and it states none."""
    disposition_found = _lead(line, DISPOSITION_LABELS)
    if disposition_found is None:
        return None
    label, end = disposition_found
    rest = line[end:]
    rest = rest[_LINE_SEPARATOR.match(rest).end():]
    if _lead(rest, CLEAR_LABELS) is None:
        return None
    present = [c for c in CLEAR_LABELS if c in line]
    return label, (present[0] if len(present) == 1 else None), line


def _has_asks(text: str) -> bool:
    """Whether the turn carries an asks block, so its close can only be the
    one-line close just before it (the three-paragraph form is not read)."""
    if not isinstance(text, str):
        return False
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return _asks_start(lines) is not None


def _one_line_close(text: str) -> "tuple[str, str | None, str] | None":
    """The turn's one-line close as :func:`_close_line` reads it, else
    ``None``.

    Without an asks block, the close is the turn's last non-blank line. With
    one, it is the last non-blank line before the block's header, and nothing
    in the block is read: an asks block opened at the turn's first line, or
    two header lines, yields no close."""
    if not isinstance(text, str):
        return None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    start = _asks_start(lines)
    if start is None:
        return _close_line(lines[-1])
    if start <= 0:
        return None
    return _close_line(lines[start - 1])


def verdict_line(text: str) -> str:
    """The text that carries the turn's clear verdict and its reason: the
    one-line close (never the asks block after it), or the three-paragraph
    close's final paragraph. Empty when there is neither."""
    one = _one_line_close(text)
    if one is not None:
        return one[2]
    if _has_asks(text):
        return ""
    paragraphs = _paragraphs(closing_block(text))
    return paragraphs[-1] if paragraphs else ""


def disposition(text: str) -> str | None:
    """The disposition a turn's close states — ``RUNNING``, ``YOUR TURN`` or
    ``COMPLETE`` — or ``None`` when it states no single one.

    The one-line close's lead label is its disposition. In the three-paragraph
    form a disposition counts only as the LEAD of a closing-block paragraph, so
    a label mentioned inside another line's copy is prose, and two paragraphs
    leading with different dispositions state none.
    """
    one = _one_line_close(text)
    if one is not None:
        return one[0]
    if _has_asks(text):
        return None
    block = closing_block(text)
    if not block:
        return None
    found = {
        label
        for paragraph in _paragraphs(block)
        if (label := _leading_label(paragraph, DISPOSITION_LABELS)) is not None
    }
    return found.pop() if len(found) == 1 else None


def contradiction(text: str) -> str | None:
    """The handed-over disposition a turn pairs with ``DO NOT CLEAR`` — the
    block's own two lines disagreeing — or ``None`` when they do not.

    Only a clearly stated pair counts: the verdict as :func:`clear_verdict`
    reads it, and a single disposition as :func:`disposition` reads it. Any
    reading that is not certain returns ``None``, because the caller records
    what this returns as a firing, and a firing on an ambiguous turn would be
    a false one.
    """
    if clear_verdict(text) != DO_NOT_CLEAR:
        return None
    stated = disposition(text)
    return stated if stated in HANDED_OVER_DISPOSITIONS else None


# A SAFE TO CLEAR reason that cites the turn as the record: something said to
# BE in the turn ("the questions are in this message", "exists only in this
# reply"), the turn said to hold it, or something said to be above or below at
# the end of a clause. A bare "in this turn" means "during this turn" ("nothing
# changed in this turn") and is not a citation, so the "in" form needs a verb of
# being in front of it. "Conversation" is deliberately absent: "nothing lives
# only in this conversation" is a sound reason, not a self-citation. Each form
# carries the kind the clear-reason check records when it fires, so its firings
# can be counted by shape without recording the turn's words.
_SELF_CITATIONS = (
    ("in-this-message", re.compile(
        r"(?:\b(?:is|are|lives?|sits?|stays?|exists?)|'re)(?: (?:all|only|still))? "
        r"in (?:this|the|my) (?:message|reply|response|turn)\b",
        re.I,
    )),
    ("message-holds", re.compile(
        r"\b(?:this|the|my) (?:message|reply|response|turn) "
        r"(?:itself|holds|has|contains|carries|records)\b",
        re.I,
    )),
    ("above-below", re.compile(
        r"(?:\b(?:is|are)|'re)(?: all)? (?:above|below)(?=\s*(?:[.;,:)]|$))|\bsee above\b",
        re.I,
    )),
)

#: Every kind :func:`self_citation_match` can return.
SELF_CITATION_KINDS: tuple[str, ...] = tuple(kind for kind, _ in _SELF_CITATIONS)

# A reason that also names a durable record is not resting on the turn alone
# ("everything in this reply is also in the handoff notes").
_DURABLE_RECORD = re.compile(
    r"\bhandoff\b|\bnotes?\b|\bon disk\b|\bcommit(?:ted|s)?\b|\.md\b|\bbacklog\b"
    r"|#\d+|\bfiles?\b|\bpushed\b|\bchange-log\b|\bissues?\b",
    re.I,
)

# A clause that denies ("No open question is in this message", "nothing
# produced here lives only in this message", "this reply has nothing unsaved")
# is the sound reason, stated negatively. Judged per clause, so "Nothing is
# running, and the plan is all in this message" is still a citation.
_CLAUSE_BREAK = re.compile(r"[.;,:!?\u2014\u2013]|\s-\s|\b(?:and|but|so)\b", re.I)
_DENIAL = re.compile(r"\b(?:no|nothing|none)\b", re.I)


def _clause_around(text: str, start: int, end: int) -> str:
    """The clause of ``text`` holding ``text[start:end]``."""
    left = max((m.end() for m in _CLAUSE_BREAK.finditer(text, 0, start)), default=0)
    right = _CLAUSE_BREAK.search(text, end)
    return text[left:right.start() if right else len(text)]


def self_citation(text: str) -> str | None:
    """The phrase by which a ``SAFE TO CLEAR`` turn gives itself as the record,
    or ``None`` (:func:`self_citation_match` without the kind)."""
    match = self_citation_match(text)
    return match[0] if match else None


def self_citation_match(text: str) -> "tuple[str, str] | None":
    """``(phrase, kind)`` for the self-citation a ``SAFE TO CLEAR`` turn makes,
    or ``None``; ``kind`` is one of :data:`SELF_CITATION_KINDS`.

    Reads only what follows the verdict on its line or paragraph
    (:func:`verdict_line`), and only when :func:`clear_verdict` reads
    ``SAFE TO CLEAR`` there. A reason that also names a durable record (notes,
    a commit, a file, an issue) returns ``None``, and so does a citation inside
    a clause that denies ("no open question is in this message"): neither rests
    on the turn alone. The match is narrow on purpose: the caller records each
    hit as a firing, and a false hit would count a sound reason as a catch or
    a slip.
    """
    if clear_verdict(text) != SAFE_TO_CLEAR:
        return None
    reason = verdict_line(text)
    at = reason.find(SAFE_TO_CLEAR)
    if at < 0:  # unreachable while clear_verdict matches the label exactly
        return None
    reason = reason[at + len(SAFE_TO_CLEAR):]
    if _DURABLE_RECORD.search(reason):
        return None
    for kind, pattern in _SELF_CITATIONS:
        for found in pattern.finditer(reason):
            if not _DENIAL.search(_clause_around(reason, found.start(), found.end())):
                return found.group(0), kind
    return None


# A close's reason that points at the turn's own content by POSITION — "the
# one ask above is for you", "see below" — rather than saying what it is. The
# reader came to the bottom to be told; a pointer sends them searching, and
# with the asks block after the close an "above" points the wrong way. A
# positional "above"/"below" is followed by the end of a clause or a verb ("is
# above.", "above is for you", "below need you"); a comparative one by what it
# compares to ("above the floor", "below 5 minutes"), so that is not matched,
# nor is a hyphenated compound ("above-mentioned"). "see above/below" always
# points. Each form carries the kind the close-pointer check records.
_POSITIONAL_TAIL = (
    r"(?=\s*(?:[.;,:)!?\u2014\u2013]|$|(?:is|are|for|needs?|waits?)\b))"
)
_POSITIONAL_POINTERS = (
    ("points-above", re.compile(r"\bsee above\b|\babove\b" + _POSITIONAL_TAIL, re.I)),
    ("points-below", re.compile(r"\bsee below\b|\bbelow\b" + _POSITIONAL_TAIL, re.I)),
)

#: Every kind :func:`positional_pointer_match` can return.
POSITIONAL_POINTER_KINDS: tuple[str, ...] = tuple(kind for kind, _ in _POSITIONAL_POINTERS)


def positional_pointer_match(text: str) -> "tuple[str, str] | None":
    """``(phrase, kind)`` for the first place a turn's close points by
    position in its reason, or ``None``; ``kind`` is one of
    :data:`POSITIONAL_POINTER_KINDS`.

    Under any disposition and either verdict: the close's reason says what
    the asks are, or nothing, never where. Reads only what follows the verdict
    on the close (:func:`verdict_line`) — never the turn's body or its asks
    block — and only when :func:`clear_verdict` reads a single verdict, since
    the caller records each hit as a firing and an uncertain reading would
    record a false one.
    """
    verdict = clear_verdict(text)
    if verdict is None:
        return None
    line = verdict_line(text)
    at = line.find(verdict)
    if at < 0:  # unreachable while clear_verdict matches the label exactly
        return None
    reason = line[at + len(verdict):]
    found = [
        (match.start(), match.group(0), kind)
        for kind, pattern in _POSITIONAL_POINTERS
        if (match := pattern.search(reason)) is not None
    ]
    if not found:
        return None
    _, phrase, kind = min(found)
    return phrase, kind


def clear_verdict(text: str) -> str | None:
    """The clear verdict a turn closes on — ``SAFE_TO_CLEAR``, ``DO_NOT_CLEAR``,
    or ``None`` when the turn states no single verdict where the close puts it.

    ``None`` covers: no text, no close, a last line (or, with an asks block,
    a line just before its header) that is not a one-line close over a final
    paragraph that does not lead with a clear label, and a close naming both
    labels. Callers that relax a gate on a verdict must treat
    ``None`` as "no permission".
    """
    one = _one_line_close(text)
    if one is not None:
        return one[1]
    if _has_asks(text):
        return None
    block = closing_block(text)
    if not block:
        return None
    present = [label for label in CLEAR_LABELS if label in block]
    if len(present) != 1:
        return None
    final = _paragraphs(block)[-1]
    return _leading_label(final, (present[0],))
