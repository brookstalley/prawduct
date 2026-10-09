"""The standing block's vocabulary, and how to read its verdict off a turn.

The standing block closes a work-cycle turn (``methodology/session-hygiene.md``
owns its shape; ``methodology/session-digest.md`` injects it into every
session): a ``---`` rule, then three paragraphs led by backticked labels —
``STATE``, one DISPOSITION label, and one CLEAR verdict. This module is the one
code home for those labels. The prose names them; a test pins the prose to the
tuples below in both directions, so a label renamed in either place fails
rather than drifting.

Code reads the block for one reason: the Stop hook fires at EVERY turn end, but
its reflection and Critic gates are about SESSION end, and the agent's clear
verdict is the agent's own statement of which one this is. A turn that says
``RUNNING`` and closes on ``DO NOT CLEAR`` is telling the user it is still
working, so those gates defer to the next turn that does not
(``lib/gates.turn_declares_in_flight``).

Because that reading relaxes an authority gate, it is deliberately narrow — a
verdict counts only where the block puts it:

* the CLOSING BLOCK is the text after the last ``---`` rule line; with no rule,
  it is the final paragraph alone;
* the verdict is the closing block's FINAL paragraph, and only if that
  paragraph BEGINS with a clear label (markdown emphasis around the label is
  allowed; nothing else may precede it);
* a closing block naming BOTH clear labels anywhere is ambiguous and yields no
  verdict.

So a label quoted mid-prose, a verdict followed by further text, or a block
that says both, all read as "no verdict" — which the gate treats as a session
end and blocks. Labels match case-sensitively: the block's labels are
upper-case tokens, and lower-case "do not clear" in a sentence is prose.

The two lines are not independent. ``DO NOT CLEAR`` says the agent is still
working — something a clear would kill is in flight — and that is ``RUNNING``.
``YOUR TURN`` and ``COMPLETE`` hand the session to someone who may read it
hours or days later, so both owe ``SAFE TO CLEAR``: whatever only the
conversation holds is written to disk before the turn is handed over. A block
pairing either with ``DO NOT CLEAR`` tells its reader two incompatible things,
and :func:`contradiction` names it so the Stop hook can refuse it.

``SAFE TO CLEAR`` is a claim about disk and process state, so its stated reason
must point at something a clear leaves behind. A reason that points at the turn
itself ("the questions are in this message") names the one thing a clear
deletes; :func:`self_citation` finds it so the Stop hook can refuse that too.
"""

from __future__ import annotations

import re

STATE = "STATE"

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
#: Each owes ``SAFE TO CLEAR``; only ``RUNNING`` may close on ``DO NOT CLEAR``.
HANDED_OVER_DISPOSITIONS: tuple[str, ...] = (YOUR_TURN, COMPLETE)

#: Every label the standing block uses, in the order the block states them.
ALL_LABELS: tuple[str, ...] = (STATE, *DISPOSITION_LABELS, *CLEAR_LABELS)

# A horizontal-rule line: three or more dashes and nothing else.
_RULE_LINE = re.compile(r"^\s*-{3,}\s*$")

# Markdown decoration allowed in front of a label: emphasis, code ticks,
# a blockquote marker. Anything else before the label means the paragraph
# does not LEAD with it.
_LEADING_DECORATION = re.compile(r"^[\s>*_`]*")


def _paragraphs(text: str) -> list[str]:
    """Non-empty paragraphs, split on blank lines."""
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def closing_block(text: str) -> str:
    """The standing block's region of a turn: after the last ``---`` rule line,
    or the final paragraph when the turn has no rule. Empty for empty input."""
    if not isinstance(text, str) or not text.strip():
        return ""
    lines = text.splitlines()
    for idx in range(len(lines) - 1, -1, -1):
        if _RULE_LINE.match(lines[idx]):
            return "\n".join(lines[idx + 1:]).strip()
    paragraphs = _paragraphs(text)
    return paragraphs[-1] if paragraphs else ""


def _leading_label(paragraph: str, labels: tuple[str, ...]) -> str | None:
    """The label ``paragraph`` LEADS with, from ``labels`` — after markdown
    decoration only, and not when the label is the prefix of a longer word."""
    lead = paragraph[_LEADING_DECORATION.match(paragraph).end():]
    for label in labels:
        if not lead.startswith(label):
            continue
        after = lead[len(label):len(label) + 1]
        if after and (after.isalnum() or after == "_"):
            continue  # a longer word that merely starts with the label
        return label
    return None


def disposition(text: str) -> str | None:
    """The disposition a turn's closing block states — ``RUNNING``,
    ``YOUR TURN`` or ``COMPLETE`` — or ``None`` when it states no single one.

    A disposition counts only as the LEAD of a closing-block paragraph, so a
    label mentioned inside another line's copy is prose. Two paragraphs leading
    with different dispositions state none: the block owes exactly one.
    """
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
    reading that is not certain returns ``None``, because the caller blocks on
    what this returns and a block on an ambiguous turn would be a false one.
    """
    if clear_verdict(text) != DO_NOT_CLEAR:
        return None
    stated = disposition(text)
    return stated if stated in HANDED_OVER_DISPOSITIONS else None


# A SAFE TO CLEAR reason that cites the turn as the record: the turn named as
# where something is or what holds it, or something said to sit above or below.
# "Conversation" is deliberately absent: "nothing lives only in this
# conversation" is a sound reason, not a self-citation.
_SELF_CITATIONS = (
    re.compile(r"\b(?:in|is|are) (?:this|the|my) (?:message|reply|response|turn)\b", re.I),
    re.compile(
        r"\b(?:this|the|my) (?:message|reply|response|turn) "
        r"(?:itself|holds|has|contains|carries|records)\b",
        re.I,
    ),
    re.compile(r"\b(?:is|are|lives?|sits?|stays?) (?:above|below)\b|\bsee above\b", re.I),
)

# A reason that also names a durable record is not resting on the turn alone
# ("everything in this reply is also in the handoff notes").
_DURABLE_RECORD = re.compile(
    r"\bhandoff\b|\bnotes?\b|\bon disk\b|\bcommit(?:ted|s)?\b|\.md\b|\bbacklog\b"
    r"|#\d+|\bfiles?\b|\bpushed\b|\bchange-log\b|\bissues?\b",
    re.I,
)

# A sentence that denies anything rests on the turn alone ("nothing produced
# here lives only in this message") is the sound reason, stated negatively.
_DENIED_SELF_CITATION = re.compile(
    r"\b(?:nothing|none|no)\b[^.;]*\bonly in (?:this|the|my) (?:message|reply|response|turn)\b",
    re.I,
)


def self_citation(text: str) -> str | None:
    """The phrase by which a ``SAFE TO CLEAR`` turn gives itself as the record,
    or ``None``.

    Reads only the verdict paragraph, and only when :func:`clear_verdict` reads
    ``SAFE TO CLEAR`` there. A reason that also names a durable record (notes,
    a commit, a file, an issue), or denies that anything lives only in the
    turn, returns ``None``: it does not rest on the turn alone. The match is narrow on purpose, because the caller blocks on it: a
    miss leaves the prose rule as the only guard, as before, while a false hit
    costs a rewritten line.
    """
    if clear_verdict(text) != SAFE_TO_CLEAR:
        return None
    reason = _paragraphs(closing_block(text))[-1]
    reason = reason[reason.index(SAFE_TO_CLEAR) + len(SAFE_TO_CLEAR):]
    if _DURABLE_RECORD.search(reason) or _DENIED_SELF_CITATION.search(reason):
        return None
    for pattern in _SELF_CITATIONS:
        found = pattern.search(reason)
        if found:
            return found.group(0)
    return None


def clear_verdict(text: str) -> str | None:
    """The clear verdict a turn closes on — ``SAFE_TO_CLEAR``, ``DO_NOT_CLEAR``,
    or ``None`` when the turn states no single verdict where the block puts it.

    ``None`` covers: no text, no closing block, a final paragraph that does not
    lead with a clear label, and a closing block naming both labels. Callers
    that relax a gate on a verdict must treat ``None`` as "no permission".
    """
    block = closing_block(text)
    if not block:
        return None
    present = [label for label in CLEAR_LABELS if label in block]
    if len(present) != 1:
        return None
    final = _paragraphs(block)[-1]
    return _leading_label(final, (present[0],))
