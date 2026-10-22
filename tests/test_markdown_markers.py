"""Operator-facing markdown carries no invalid ordered-list markers (#577).

`NNa.` (`13a.`, `5b.`) is not a CommonMark ordered-list marker: it ends the list, so a runbook
step renders as body text of the item above it and the procedure reads wrong. This is the
small in-repo check the issue asked for: marker validity only, no prose style.

Scope: every `*.md` under `plugin/` (runbooks, skills, methodology, docs, templates) and the live
`.prawduct/artifacts/` plans and specs. `.prawduct/artifacts/archive/` is history, left as written.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

#: A line that opens like an ordered item but with a letter suffix on the number.
_BAD_MARKER = re.compile(r"^\s*\d+[a-z]\.\s+\S")


def _scanned() -> list[Path]:
    files = sorted((REPO / "plugin").rglob("*.md"))
    files += sorted(
        p for p in (REPO / ".prawduct" / "artifacts").rglob("*.md") if "archive" not in p.parts
    )
    return files


def bad_markers(text: str) -> list[tuple[int, str]]:
    """(line number, line) of each invalid marker outside fenced code blocks.

    A line starting `30s. ` is wrapped prose ("... within\n30s. The"), not a marker attempt, so
    the number must be followed by a single letter and a period then a space-separated word AND
    the letter must not be an `s` unit suffix.
    """
    out, fenced = [], False
    for i, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if not fenced and _BAD_MARKER.match(line) and not re.match(r"^\s*\d+[sm]\.\s", line):
            out.append((i, line.strip()[:60]))
    return out


def test_the_scan_reads_a_real_corpus():
    files = _scanned()
    assert len(files) > 50
    assert any(p.name == "runbook-authoring.md" for p in files)


def test_the_checker_catches_what_it_names_and_spares_what_it_must():
    assert bad_markers("1. a\n2a. b\n") == [(2, "2a. b")]
    assert bad_markers("   - 4b. nested\n") == []  # a bullet, not a marker at line start
    assert bad_markers("```\n2a. in a fence\n```\n") == []
    assert bad_markers("within\n30s. The next\n") == []
    assert bad_markers("1. ok\n   - (2a) ok\n") == []


@pytest.mark.parametrize("path", _scanned(), ids=lambda p: str(p.relative_to(REPO)))
def test_no_invalid_ordered_list_marker(path: Path):
    assert bad_markers(path.read_text(encoding="utf-8")) == [], (
        f"{path.relative_to(REPO)}: `NNa.` is not a CommonMark list marker and ends the list; "
        "renumber, or nest as `   - (2a) ...` under its parent item"
    )
