"""The declared suite runs once, at the boundary — not at every chunk (#820).

Owner decision 2026-09-23, recorded on #820: derive the default from stage and
add no vocabulary. A chunk's Verify runs the project's `Inner-loop verification`
row (else the tests for the files touched); the declared suite runs once, before
the `cumulative` review and the PR; a project wanting it per chunk says so in
that free-text row. The inner-stage reviewer therefore reads a stale or missing
record as the normal in-flight state rather than recommending a run.

The rule has several carriers, each with a different reader, so each is pinned
by its own sentence — and the retired per-chunk wording is pinned ABSENT, since
a superseded sentence left beside its replacement keeps governing whoever stops
reading at it.
"""

from __future__ import annotations

import re
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent / "plugin"


def _read(rel: str) -> str:
    return (PLUGIN / rel).read_text(encoding="utf-8")


class TestTheBuilderIsToldWhenTheSuiteIsOwed:
    def test_the_ceiling_paragraph_moves_the_suite_to_the_boundary(self):
        text = _read("methodology/building.md")
        # "The boundary" is where work LANDS on the integration branch, not a
        # review mode: a direct-commit repo, or work ending on a single `final`,
        # has no `cumulative` or PR, and the suite is still owed there.
        assert (
            "The declared suite runs at the boundary, before the work lands (the "
            "`cumulative` review and PR, where there are ones), unless that row asks "
            "for it per chunk." in text
        )

    def test_verify_records_at_the_boundary_run(self):
        text = _read("methodology/building.md")
        assert (
            "A chunk runs the ceiling above; record the declared suite **once**, "
            "at the boundary run" in text
        )
        assert "Record **once**, at Verify" not in text


class TestTheOwnersRowCarriesThePerChunkOptIn:
    def test_the_template_row_names_the_default_and_the_opt_in(self):
        row = next(
            line for line in _read("templates/project-preferences.md").splitlines()
            if line.startswith("- **Inner-loop verification**")
        )
        assert "at each chunk's Verify, before the declared suite runs at the boundary, before the work lands" in row
        assert "say here that this project wants the declared suite at every chunk" in row
        assert "runs at Verify and at the boundary" not in row

    def test_the_doctor_drafts_the_row_against_the_same_default(self):
        text = _read("skills/doctor/SKILL.md")
        assert "at each chunk's Verify before the declared suite runs at the boundary, before the work lands" in text
        assert "runs at Verify and at the boundary" not in text


class TestTheReviewerDoesNotAskForAPerChunkRun:
    def test_the_inner_stage_reads_stale_as_in_flight(self):
        text = _read("skills/critic/goals-1-3.md")
        assert (
            "stale/missing → no finding (**WARNING** only at the boundary, "
            "where the suite runs)" in text
        )
        assert "stale/missing → **WARNING** — that exit code" not in text

    def test_the_full_protocol_splits_the_verdict_by_mode(self):
        text = _read("skills/critic/review-protocol.md")
        assert (
            "stale/missing → **WARNING** at `cumulative`; at `final` an observation "
            "that the suite is owed before the work lands" in text
        )

    def test_the_coordinator_step_agrees(self):
        text = _read("skills/critic/SKILL.md")
        assert (
            "(exit 1 = stale, or evidence missing → WARNING at `cumulative`, an "
            "observation at `final`)" in text
        )
        assert "→ WARNING in your review)" not in text

    def test_failures_stay_blocking_at_every_stage(self):
        """Only staleness moved. A red record is still the builder's to fix
        before any review passes, inner or boundary."""
        for rel in ("skills/critic/goals-1-3.md", "skills/critic/review-protocol.md"):
            assert "Test failures in evidence → **BLOCKING**" in _read(rel), rel


class TestNoCarrierStillAsksForAPerChunkRun:
    """One scan, bounded by the property rather than by the files I thought of.

    The first sweep for this change searched my own phrasings and missed three
    carriers (the janitor skill, the build-plan template, and a fallback rule
    ``briefing.py`` hands delegates). So the scan covers every shipped prose
    file and every Python string under ``plugin/``, and asserts it REACHED the
    carriers that were missed — a scan that silently skipped them would pass.
    """

    RETIRED = [
        re.compile(r"\b[Rr]un the (?:full|whole|entire|declared) (?:test )?suite (?:after|at) (?:each|every) chunk"),
        re.compile(r"runs at Verify and at the boundary"),
        re.compile(r"Record \*\*once\*\*, at Verify"),
        re.compile(r"Run the full test suite before finishing work"),
        re.compile(r"Acceptance criteria:\*\* the declared suite passes"),
        re.compile(r"suite runs once,? at the boundary"),
        re.compile(r"runs once, before the `cumulative` review"),
    ]

    def _corpus(self) -> dict[str, str]:
        files = sorted(
            p for p in PLUGIN.rglob("*")
            if p.suffix in {".md", ".py"} and p.is_file()
            and p.name != "CHANGELOG.md"
            and "__pycache__" not in p.parts
        ) + [PLUGIN / "bin" / "prawduct-hook"]
        corpus = {str(p.relative_to(PLUGIN)): p.read_text(encoding="utf-8") for p in files}
        # The release notes: released sections are history and may quote the
        # old default, but the UNRELEASED section — the first `## ` heading's
        # body — makes live claims to consumers, so it is scanned.
        notes = (PLUGIN / "CHANGELOG.md").read_text(encoding="utf-8")
        first = notes.index("\n## ")
        second = notes.find("\n## ", first + 1)
        corpus["CHANGELOG.md#unreleased"] = notes[first:second if second != -1 else None]
        return corpus

    def test_the_scan_reaches_the_carriers_it_once_missed(self):
        corpus = self._corpus()
        for rel in ("skills/janitor/SKILL.md", "lib/briefing.py",
                    "templates/build-plan.md", "methodology/building.md",
                    "CHANGELOG.md#unreleased"):
            assert rel in corpus, f"the scan never read {rel}"

    def test_each_pattern_matches_the_wording_it_retires(self):
        samples = [
            "- Run the full test suite after each chunk",
            "The declared suite runs at Verify and at the boundary.",
            "- *Code:* Record **once**, at Verify — **not** after",
            '"- Run the full test suite before finishing work.",',
            "- **Acceptance criteria:** the declared suite passes; browser",
            "before the declared suite runs once, at the boundary review",
            "the declared suite runs once, before the `cumulative` review and the PR",
        ]
        for pattern, sample in zip(self.RETIRED, samples):
            assert pattern.search(sample), pattern.pattern

    def test_no_shipped_file_carries_a_retired_instruction(self):
        hits = [
            f"{rel}: {m.group(0)!r}"
            for rel, text in self._corpus().items()
            for pattern in self.RETIRED
            for m in pattern.finditer(text)
        ]
        assert not hits, hits

    def test_the_opt_in_is_not_mistaken_for_the_retired_rule(self):
        """The template's opt-in sentence names a per-chunk suite on purpose."""
        row = _read("templates/project-preferences.md")
        assert "wants the declared suite at every chunk" in row
        assert not any(p.search(row) for p in self.RETIRED)


class TestTheReplacementsSayTheNewRule:
    """The scan proves the old instructions are gone; these prove what took
    their place still tells the reader where the suite runs."""

    def test_the_delegate_fallback_rule(self):
        text = (PLUGIN / "lib" / "briefing.py").read_text(encoding="utf-8")
        assert (
            "While building, run the narrowest tests that prove the change; run the "
            "declared suite before the work lands." in text
        )

    def test_the_janitor_execute_step(self):
        text = _read("skills/janitor/SKILL.md")
        assert (
            "Verify each chunk with the narrowest tests that prove it; the declared "
            "suite runs at the boundary, before the work lands" in text
        )

    def test_the_release_note_names_the_default_change(self):
        notes = (PLUGIN / "CHANGELOG.md").read_text(encoding="utf-8")
        unreleased = notes[notes.index("\n## "):notes.find("\n## ", notes.index("\n## ") + 1)]
        assert "**`suite-at-boundary`**" in unreleased
        assert "This changes a default your repo inherits." in unreleased
