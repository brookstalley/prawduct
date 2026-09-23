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

from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent / "plugin"


def _read(rel: str) -> str:
    return (PLUGIN / rel).read_text(encoding="utf-8")


class TestTheBuilderIsToldWhenTheSuiteIsOwed:
    def test_the_ceiling_paragraph_moves_the_suite_to_the_boundary(self):
        text = _read("methodology/building.md")
        assert (
            "The declared suite runs once, at the boundary (before `cumulative` and "
            "the PR), unless that row asks for it per chunk." in text
        )

    def test_verify_records_at_the_boundary_run(self):
        text = _read("methodology/building.md")
        assert "Record **once**, at the boundary run" in text
        assert "Record **once**, at Verify" not in text


class TestTheOwnersRowCarriesThePerChunkOptIn:
    def test_the_template_row_names_the_default_and_the_opt_in(self):
        row = next(
            line for line in _read("templates/project-preferences.md").splitlines()
            if line.startswith("- **Inner-loop verification**")
        )
        assert "at each chunk's Verify, before the declared suite runs once, at the boundary review" in row
        assert "say here that this project wants the declared suite at every chunk" in row
        assert "runs at Verify and at the boundary" not in row

    def test_the_doctor_drafts_the_row_against_the_same_default(self):
        text = _read("skills/doctor/SKILL.md")
        assert "at each chunk's Verify before the declared suite runs once at the boundary review" in text
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
        assert "stale/missing → **WARNING** at `cumulative`, none at `final`" in text

    def test_the_coordinator_step_agrees(self):
        text = _read("skills/critic/SKILL.md")
        assert "(exit 1 = stale, or evidence missing → WARNING at `cumulative` only)" in text
        assert "→ WARNING in your review)" not in text

    def test_failures_stay_blocking_at_every_stage(self):
        """Only staleness moved. A red record is still the builder's to fix
        before any review passes, inner or boundary."""
        for rel in ("skills/critic/goals-1-3.md", "skills/critic/review-protocol.md"):
            assert "Test failures in evidence → **BLOCKING**" in _read(rel), rel
