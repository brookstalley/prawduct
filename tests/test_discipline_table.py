"""`plugin/docs/discipline.md` and the surfaces it names are pinned against EACH
OTHER — the table says where each portable rule lives, and the only thing that
keeps that true is reading the surface for the row's anchor phrase.

Read through the plugin root, not a fixture: a fixture would encode the belief
the table already states, and could only ever confirm it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
TABLE = ROOT / "docs" / "discipline.md"


def _rows() -> list[dict]:
    rows = []
    for line in TABLE.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| ") or line.startswith("| #") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 6 or not cells[0].isdigit():
            continue
        rows.append(dict(zip(("n", "rule", "learned_by", "channel", "surface", "anchor"), cells)))
    return rows


def _strip_ticks(s: str) -> str:
    return s.strip("`")


def test_the_table_has_the_ten_rows():
    rows = _rows()
    assert [r["n"] for r in rows] == [str(i) for i in range(1, 11)], (
        "the discipline table must carry exactly the ten audit rules, numbered 1-10"
    )


@pytest.mark.parametrize("row", _rows(), ids=lambda r: f"rule-{r['n']}")
def test_each_rows_anchor_is_present_in_its_surface(row):
    surface = ROOT / _strip_ticks(row["surface"])
    assert surface.is_file(), f"row {row['n']} names a surface that does not exist: {row['surface']}"
    text = surface.read_text(encoding="utf-8")
    anchor = _strip_ticks(row["anchor"])
    assert anchor in text, (
        f"row {row['n']} ({row['rule'][:50]}…) claims its sentence lives in {row['surface']} "
        f"but the anchor {anchor!r} is not there — move the row with the sentence"
    )


def _line_containing(text: str, needle: str) -> str:
    hits = [ln.strip() for ln in text.splitlines() if needle in ln]
    assert len(hits) == 1, f"{needle!r} must appear on exactly one line, found {len(hits)}"
    return hits[0]


def test_critic_goal_rows_agree_across_both_protocol_files():
    """A Goal sentence carried by two files is one rule with two readers; the
    chunk/verify-resolutions modes read goals-1-3.md alone, final/cumulative
    read review-protocol.md, and the two must say the same thing."""
    goals = (ROOT / "skills" / "critic" / "goals-1-3.md").read_text(encoding="utf-8")
    protocol = (ROOT / "skills" / "critic" / "review-protocol.md").read_text(encoding="utf-8")
    # The carrier set is derived from the Channel cell and asserted, so a reworded
    # cell cannot empty the loop silently; the WHOLE bullet is compared, severity
    # included — a re-severitied copy in one carrier is two bars for one decision.
    carried = [r for r in _rows() if "critic goal" in r["channel"].lower()]
    assert {r["n"] for r in carried} == {"5", "6", "7"}, (
        "the rows the table carries through a Critic goal changed — update this "
        "set deliberately, and check both protocol files carry the newcomer"
    )
    for row in carried:
        anchor = _strip_ticks(row["anchor"])
        assert _line_containing(goals, anchor) == _line_containing(protocol, anchor), (
            f"row {row['n']}'s Goal bullet differs between goals-1-3.md and review-protocol.md"
        )


def test_every_row_passes_the_three_generality_tests_by_construction():
    """The promotion test the owner ratified: nothing in the table names a
    stack, a prawduct internal, or one codebase. Checked as a NEGATIVE
    substring test over the rule column — the cheap half of a judgement a
    reader still owes when adding a row."""
    banned = re.compile(r"\b(pytest|python|prawduct-hook|critic-consolidate|\.prawduct/|discodon|samsung)\b", re.I)
    for row in _rows():
        assert not banned.search(row["rule"]), f"row {row['n']} is not stack-agnostic or names an internal: {row['rule']}"
