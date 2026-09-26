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
verdict is the agent's own statement of which one this is. A turn that closes
on ``DO NOT CLEAR`` is telling the user not to end the session, so those gates
defer to the next turn that does not (``lib/gates.turn_declares_in_flight``).

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
    lead = final[_LEADING_DECORATION.match(final).end():]
    label = present[0]
    if not lead.startswith(label):
        return None
    after = lead[len(label):len(label) + 1]
    if after and (after.isalnum() or after == "_"):
        return None  # a longer word that merely starts with the label
    return label
