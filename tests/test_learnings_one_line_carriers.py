"""Every surface that tells an agent how to WRITE a learnings rule states the
one-line form, and none still carries the guidance that caused four regrowths.

The corpus regrew because the write-side instruction ("a heading that carries
the rule, its brief why, and the instance that earned it, inline … never trim
a rule to fit") fired on every reflection and pulled against every budget. A
rewrite that adds the new rule beside the old sentence leaves the old sentence
governing whoever stops reading there, so the retired phrases are asserted
ABSENT across all shipped prose, not only at the carriers edited.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugin"
sys.path.insert(0, str(PLUGIN))

from lib import learnings_files as lf  # noqa: E402

#: Each carrier, and the words by which it states the form. Found by two
#: vocabularies on 2026-09-24 ("heading that carries"/"instance"/"trim" and
#: "add a rule"/"capture learnings"/"concise standing rules").
CARRIERS = {
    "methodology/reflection.md": "one `- ` line",
    # No number here on purpose: this message is the REFLECTION gate's, and a
    # character count in it reads as a length the reflection must meet
    # (`test_reflection_gate.py::test_it_never_mentions_a_character_count`).
    "bin/prawduct-hook": "as ONE line — the rules file",
    "skills/janitor/SKILL.md": "as one-line rules",
    "docs/principles.md": "as one-line rules",
    "templates/project-state.yaml": "Every rule is ONE line of at most 250 characters",
}

#: Retired wording. Each one is the instruction that produced the regrowth, so
#: a copy anywhere in shipped prose is that instruction still in force.
RETIRED = (
    "never trim a rule",
    "heading that carries the rule",
    "the instance that earned it, inline",
    "Good rules have",
    "raise the budget with its reason",
)


@pytest.mark.parametrize("rel,phrase", sorted(CARRIERS.items()))
def test_each_carrier_states_the_one_line_form(rel, phrase):
    text = " ".join((PLUGIN / rel).read_text(encoding="utf-8").split())
    assert phrase in text, f"{rel} no longer states the one-line form"


def test_the_scaffold_states_it_too():
    """A new repo's core.md is the first thing its sessions read."""
    assert "one line of at most 250 characters" in lf.CORE_HEADER


def _shipped_prose() -> "list[Path]":
    return [
        p for p in PLUGIN.rglob("*")
        if p.is_file() and p.suffix in (".md", ".yaml", ".py", "") and p.name != "CHANGELOG.md"
        and "__pycache__" not in p.parts
    ]


def test_the_corpus_scanned_is_not_empty():
    """A zero from a scan is suspicious until the scan can return non-zero."""
    files = _shipped_prose()
    assert any(p.name == "reflection.md" for p in files)
    assert len(files) > 50


@pytest.mark.parametrize("phrase", RETIRED)
def test_no_shipped_prose_still_carries_the_retired_instruction(phrase):
    """Whitespace is normalized first, so a phrase wrapped across lines is
    still found. The consumer CHANGELOG is exempt: it quotes history."""
    hits = [
        p.relative_to(ROOT).as_posix() for p in _shipped_prose()
        if phrase.lower() in " ".join(p.read_text(encoding="utf-8", errors="replace").split()).lower()
    ]
    assert not hits, f"{phrase!r} still instructs in: {hits}"
