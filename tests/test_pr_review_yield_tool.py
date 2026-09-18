"""Guards for `tools/pr-review-yield.py`, the derivation behind
`.prawduct/artifacts/pr-review-payload-discovery.md`.

A spike that discards its code leaves its numbers unfalsifiable, so the discovery
artifact cites the command rather than the digits. That only helps if the command is
itself pinned: these tests exist so a later edit cannot silently change what the
artifact's cited numbers mean.

What turns each of these red is named beside it. The two that matter most are the
measured/self-reported split (the whole point of the tool is that it can tell a
measured interval from the reviewing model's estimate, and pooling them re-creates
the hazard it exists to retire) and the non-empty assertion (a report built from zero
rows would otherwise pass every shape check while having examined nothing).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_TOOL = Path(__file__).resolve().parent.parent / "tools" / "pr-review-yield.py"


def _load():
    """Import the hyphenated script by path — it is not an importable module name."""
    spec = importlib.util.spec_from_file_location("pr_review_yield", _TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["pr_review_yield"] = module
    spec.loader.exec_module(module)
    return module


yield_tool = _load()


def _event(ts, *, dispatched_at=None, duration=None, findings=(), files=()):
    row = {
        "schema_version": 1,
        "event": "review.pr",
        "ts": ts,
        "review": {
            "findings": [
                {"goal": g, "severity": s, "summary": "x"} for g, s in findings
            ],
            "files_reviewed": list(files),
        },
    }
    if dispatched_at is not None:
        row["dispatched_at"] = dispatched_at
    if duration is not None:
        row["duration_seconds"] = duration
    return row


def _ledger(tmp_path, rows):
    repo = tmp_path / "repo"
    (repo / ".prawduct").mkdir(parents=True)
    (repo / ".prawduct" / ".governance-ledger.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n"
    )
    return repo


class TestDurationProvenance:
    """The measured/self-reported split — the tool's reason to exist."""

    def test_a_dispatch_timestamp_yields_a_measured_interval(self):
        """Red if `duration` stops preferring the measured interval over the estimate.

        The estimate here (9999) disagrees with the measured interval (300) on
        purpose: a tool that returned 9999 would be reporting the model's
        recollection while claiming to report a clock.
        """
        secs, measured = yield_tool.duration(
            _event(
                "2026-09-18T12:05:00Z",
                dispatched_at="2026-09-18T12:00:00Z",
                duration=9999,
            )
        )
        assert measured is True
        assert secs == 300

    def test_no_dispatch_timestamp_falls_back_and_says_so(self):
        """Red if a self-reported row is ever labelled measured."""
        secs, measured = yield_tool.duration(_event("2026-09-18T12:05:00Z", duration=420))
        assert measured is False
        assert secs == 420

    def test_a_row_with_neither_reports_no_duration_rather_than_zero(self):
        """Red if absence degrades to 0 — which would average a missing value
        into the real ones and drag every median down silently."""
        secs, measured = yield_tool.duration(_event("2026-09-18T12:05:00Z"))
        assert secs is None
        assert measured is False

    def test_an_unparseable_dispatch_timestamp_degrades_to_self_reported(self):
        """Red if a malformed stamp raises instead of falling back. The tool is
        advice over a corpus it does not control; one bad row must not end the run."""
        secs, measured = yield_tool.duration(
            _event("2026-09-18T12:05:00Z", dispatched_at="not-a-timestamp", duration=420)
        )
        assert measured is False
        assert secs == 420


class TestReport:
    def test_the_split_is_counted_not_pooled(self, tmp_path):
        """Red if `measured_durations` stops distinguishing the two populations."""
        repo = _ledger(
            tmp_path,
            [
                _event("2026-09-18T12:05:00Z", dispatched_at="2026-09-18T12:00:00Z"),
                _event("2026-09-18T13:00:00Z", duration=420),
            ],
        )
        data = yield_tool.report(yield_tool.load(repo, None, None))
        assert data["reviews"] == 2
        assert data["with_duration"] == 2
        assert data["measured_durations"] == 1

    def test_findings_are_split_by_goal_and_severity(self, tmp_path):
        """Red if the goal x severity breakdown collapses — that table is what a
        protocol change is graded against, so it must survive one."""
        repo = _ledger(
            tmp_path,
            [
                _event(
                    "2026-09-18T12:00:00Z",
                    duration=300,
                    findings=[("Merge Hygiene", "note"), ("Merge Hygiene", "warning")],
                    files=["a.py"],
                )
            ],
        )
        data = yield_tool.report(yield_tool.load(repo, None, None))
        assert data["findings"] == 2
        assert data["by_severity"] == {"note": 1, "warning": 1}
        assert data["by_goal"]["Merge Hygiene / note"] == 1
        assert data["by_goal"]["Merge Hygiene / warning"] == 1

    def test_non_pr_events_are_excluded(self, tmp_path):
        """Red if Critic reviews leak into the PR figures — the pooling defect
        `review-stats` has and this tool exists to avoid."""
        rows = [_event("2026-09-18T12:00:00Z", duration=300)]
        rows.append({**_event("2026-09-18T12:30:00Z", duration=600), "event": "review.critic"})
        data = yield_tool.report(yield_tool.load(_ledger(tmp_path, rows), None, None))
        assert data["reviews"] == 1

    def test_a_corrupt_line_is_skipped_not_fatal(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / ".prawduct").mkdir(parents=True)
        (repo / ".prawduct" / ".governance-ledger.jsonl").write_text(
            "{not json\n" + json.dumps(_event("2026-09-18T12:00:00Z", duration=300)) + "\n"
        )
        assert len(yield_tool.load(repo, None, None)) == 1

    def test_the_window_bounds_filter(self, tmp_path):
        repo = _ledger(
            tmp_path,
            [
                _event("2026-08-01T12:00:00Z", duration=300),
                _event("2026-09-18T12:00:00Z", duration=300),
            ],
        )
        assert len(yield_tool.load(repo, "2026-09-01", None)) == 1
        assert len(yield_tool.load(repo, None, "2026-09-01")) == 1


class TestAgainstTheRealLedger:
    """One test reads the real artifact, because a fixture I wrote encodes my belief
    about the input and can only confirm it.

    This asserts the corpus is REACHABLE and classifiable, never a count — a count
    would pin this repo's current phase as an invariant and go red on the next PR.
    """

    def test_this_repos_ledger_parses_and_yields_pr_reviews(self):
        repo = Path(__file__).resolve().parent.parent
        if not (repo / yield_tool.LEDGER).is_file():
            pytest.skip("no governance ledger in this checkout")
        rows = yield_tool.load(repo, None, None)
        assert rows, "the real ledger yielded no review.pr rows — the tool examined nothing"
        data = yield_tool.report(rows)
        assert data["findings"] > 0
        assert data["by_goal"], "findings exist but none classified by goal"
