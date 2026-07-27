"""Prose pin: nothing may promise that a *continuation* resets session state.

SCN-5B8Q split `clear` into a boundary path (`startup`/`clear`) and an
orientation-only continuation path (`resume`/`compact`/`fork`). Four separate
review rounds then found surfaces still asserting the pre-split behaviour — a
docstring, a skill instruction, an operator-facing message, a change-log entry,
a test docstring, a plan table, a plan assumption, a verification step, and
finally the backlog item all of them were copied from. Each round the fix was
"sweep the claim again," and each round something survived.

At the third recurrence the branch's own learning says to stop sweeping and make
it enforceable. This is that pin. It does NOT try to prove every sentence is
accurate — prose can't be validated by regex. It pins the one phrasing family
that recurred, so the next copy fails a test instead of shipping and being found
by a reviewer four rounds later.

Deliberately narrow, and the limits are stated rather than implied:

* It keys on "next session start"-style phrasings near a session-state noun.
  A sentence that makes the same wrong promise in different words passes. That
  is accepted: this catches the *copy*, and copying is how all four recurrences
  actually happened.
* It exempts text that is explicitly marked as corrected history (struck through,
  or quoted as a prior claim), because the fix for several of these was to KEEP
  the old sentence with a correction beside it.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
PLUGIN = ROOT / "plugin"

# Files whose text is read by an agent or an operator as instruction.
SURFACES = [
    PLUGIN / "bin" / "prawduct-hook",
    PLUGIN / "methodology" / "building.md",
    PLUGIN / "methodology" / "reflection.md",
    PLUGIN / "methodology" / "session-digest.md",
    PLUGIN / "methodology" / "session-digest-slim.md",
    PLUGIN / "skills" / "critic" / "SKILL.md",
    PLUGIN / "lib" / "critic_marker.py",
]

# The phrasing family that recurred: "<happens> at/on next session start",
# without naming which sources actually qualify.
_BARE_NEXT_SESSION = re.compile(
    r"(?:on|at|the)\s+next\s+session\s+start\b|auto-?clears?\s+next\s+session\b",
    re.IGNORECASE,
)

# A line is fine if it names the boundary sources, or is marked as corrected history.
_QUALIFIED = re.compile(
    r"boundar|/clear|startup|struck|originally|previously|corrected|~~", re.IGNORECASE
)


def _offending_lines(path: Path) -> list[tuple[int, str]]:
    if not path.is_file():
        return []
    out: list[tuple[int, str]] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines, 1):
        if not _BARE_NEXT_SESSION.search(line):
            continue
        # Allow the qualifier to land on the neighbouring line — these strings are
        # wrapped across source lines, which is exactly how one of them hid.
        window = " ".join(lines[max(0, i - 2) : i + 2])
        if _QUALIFIED.search(window):
            continue
        out.append((i, line.strip()))
    return out


class TestNoUnqualifiedNextSessionPromise:
    def test_the_pin_has_something_to_check(self):
        """Guard against the pin silently covering nothing — if the phrasing is
        renamed wholesale, this fails rather than passing vacuously."""
        assert any(p.is_file() for p in SURFACES)
        corpus = "\n".join(
            p.read_text(encoding="utf-8") for p in SURFACES if p.is_file()
        )
        assert "session" in corpus and "boundary" in corpus, (
            "the surfaces no longer discuss session boundaries — re-point this pin"
        )

    def test_no_surface_promises_a_reset_at_bare_next_session_start(self):
        """`resume`/`compact`/`fork` reset nothing, so "next session start" is
        wrong unless the sentence says which sources it means."""
        offenders = {
            str(p.relative_to(ROOT)): found
            for p in SURFACES
            if (found := _offending_lines(p))
        }
        assert not offenders, (
            "unqualified 'next session start' promise — a continuation "
            "(resume/compact/fork) resets nothing, so name the boundary "
            f"sources or mark the text as corrected history:\n{offenders}"
        )
