"""The good-faith severity cap reaches every Critic mode, with its floor in the same sentence.

The owner's design stance (2026-11-26): assume good faith by humans and competence by models. A
finding whose failure needs a person acting in bad faith or a model ignoring its instructions, or
whose fix needs a list to close an open set, is an observation at most. Accidents and real failure
modes keep their severity.

The rule is carried by both severity sections because their readers are disjoint: `chunk` and
`verify-resolutions` read `goals-1-3.md` and are told not to open `review-protocol.md`. So the
carriers are derived per mode from `review-cycle.md`'s `Protocol read` row, the map a re-route
edits, rather than named here.

The floor is pinned hardest. A rule that lowers a severity outranks every rule that raises one, so
a cap stated without its floor would turn Goal 1's exploitable-input BLOCKING into an observation
the first time a reviewer calls an attacker "bad faith". `untrusted input` in the same sentence is
what keeps that from happening.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_finding_scope_rule import ALL_MODES, CRITIC, DOCUMENTED  # noqa: E402

RULE_LEAD = "- **Good faith caps severity**"
CEILING = "is an observation at most, whatever its goal says"
FLOOR = ("a crash, git error, stale state, untrusted input or competent mistake keeps its severity")


def _severity_section(text: str) -> str:
    """The `## Severity…` section: the span a reviewer reads to rate a finding."""
    start = text.index("\n## Severity")
    end = text.find("\n## ", start + 1)
    return text[start:] if end == -1 else text[start:end]


def _rule_line(text: str) -> str:
    lines = [ln for ln in _severity_section(text).splitlines() if ln.startswith(RULE_LEAD)]
    assert len(lines) == 1, f"the good-faith cap must be one bullet in the Severity section, found {len(lines)}"
    return lines[0]


def _sentence_with(line: str, clause: str) -> str:
    sentences = re.split(r"(?<=\.)\s+", line)
    hits = [s for s in sentences if clause in s]
    assert len(hits) == 1, f"{clause!r} must be in exactly one sentence, found {len(hits)}"
    return hits[0]


def _carrier(mode: str) -> str:
    return (CRITIC / DOCUMENTED[mode]).read_text(encoding="utf-8")


def test_the_modes_resolve_to_carriers() -> None:
    # Non-empty, and every mode resolves to a file that exists, so a parametrized pass below means
    # each mode's payload was actually read.
    assert ALL_MODES
    for mode in ALL_MODES:
        assert (CRITIC / DOCUMENTED[mode]).is_file(), mode


@pytest.mark.parametrize("mode", ALL_MODES)
def test_the_mode_reads_the_cap_with_its_floor_in_one_sentence(mode: str) -> None:
    sentence = _sentence_with(_rule_line(_carrier(mode)), CEILING)
    assert FLOOR in sentence, (
        f"`{mode}`'s carrier caps bad-faith findings without stating, in the same sentence, what keeps "
        "its severity. The cap then outranks every rule raising one, Goal 1's security BLOCKINGs included."
    )


@pytest.mark.parametrize("mode", ALL_MODES)
def test_the_mode_reads_what_a_competent_mistake_is(mode: str) -> None:
    # Without the definition, 'the person should have known' waves away a real bug as bad faith.
    line = _rule_line(_carrier(mode))
    tail = line[line.index("competent mistake keeps its severity"):]
    assert "a careful person's misread ambiguous step" in tail
    assert "wrong input the code took silently" in tail


@pytest.mark.parametrize("mode", ALL_MODES)
def test_the_cap_follows_the_observation_it_caps_to(mode: str) -> None:
    # Read in order: a reviewer meets what an observation is before a rule rating things one.
    section = _severity_section(_carrier(mode))
    assert section.index("- **Observation**") < section.index(RULE_LEAD)


def test_both_carriers_state_one_rule() -> None:
    carriers = sorted({DOCUMENTED[m] for m in ALL_MODES})
    lines = {c: _rule_line((CRITIC / c).read_text(encoding="utf-8")) for c in carriers}
    assert len(carriers) >= 2, carriers
    assert len(set(lines.values())) == 1, f"the good-faith cap differs between carriers: {lines}"


def test_a_floor_in_its_own_sentence_is_caught() -> None:
    # Control: the predicate must fail when the floor is split off into a sentence of its own.
    line = _rule_line(_carrier("cumulative")).replace(
        "whatever its goal says; a crash", "whatever its goal says. a crash"
    )
    assert FLOOR in line
    assert FLOOR not in _sentence_with(line, CEILING)
