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

_TOOL = Path(__file__).resolve().parent.parent / "tools" / "pr-review-yield.py"


def _load():
    """Import the hyphenated script by path — it is not an importable module name."""
    spec = importlib.util.spec_from_file_location("pr_review_yield", _TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["pr_review_yield"] = module
    spec.loader.exec_module(module)
    return module


yield_tool = _load()


def _event_nested_duration_only(ts, seconds):
    """A row carrying the estimate ONLY under `review`, never at the envelope top level.

    This is the shape an evidence file written straight through by the PR reviewer has
    (`review-protocol.md`'s JSON schema puts `duration_seconds` inside the record), so
    `duration()`'s nested fallback is a real path and this is the fixture that reaches
    it — rows carrying both keys never do.
    """
    return {
        "schema_version": 1,
        "event": "review.pr",
        "ts": ts,
        "review": {"duration_seconds": seconds, "findings": [], "files_reviewed": []},
    }


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

    def test_the_estimate_is_read_from_the_nested_record_when_that_is_where_it_is(self):
        """Red if `duration()` stops falling back to `review.duration_seconds`.

        Deleting that operand turned nothing red before this test existed, because
        every real row and every fixture carried the top-level key too.
        """
        secs, measured = yield_tool.duration(
            _event_nested_duration_only("2026-09-18T12:00:00Z", 360)
        )
        assert measured is False
        assert secs == 360

    def test_a_row_with_neither_reports_no_duration_rather_than_zero(self):
        """Red if absence degrades to 0 — which would average a missing value
        into the real ones and drag every median down silently."""
        secs, measured = yield_tool.duration(_event("2026-09-18T12:05:00Z"))
        assert secs is None
        assert measured is False

    def test_a_stamp_after_the_write_is_refused_not_labelled_measured(self):
        """Red if the ordering bound goes. A clock skew or a hand-edited row yields a
        NEGATIVE interval that parses fine; labelling it measured is worse than the
        estimate it displaces, which is at least honest about being one."""
        secs, measured = yield_tool.duration(
            _event(
                "2026-09-18T12:00:00Z",
                dispatched_at="2026-09-18T12:05:00Z",
                duration=420,
            )
        )
        assert measured is False
        assert secs == 420

    def test_a_stale_marker_interval_is_refused(self):
        """Red if the upper bound goes. A run that dies between marking dispatch and
        appending leaves the marker behind, so the NEXT append attaches a stamp hours
        old — parseable, positive, and wrong."""
        secs, measured = yield_tool.duration(
            _event(
                "2026-09-18T20:00:00Z",
                dispatched_at="2026-09-18T02:00:00Z",
                duration=420,
            )
        )
        assert measured is False
        assert secs == 420

    def test_a_long_but_plausible_review_is_still_measured(self):
        """The control for the two above: the bound must refuse stale stamps WITHOUT
        refusing real long reviews. 25 minutes is longer than anything in this corpus
        and must still count."""
        secs, measured = yield_tool.duration(
            _event(
                "2026-09-18T12:25:00Z",
                dispatched_at="2026-09-18T12:00:00Z",
                duration=9999,
            )
        )
        assert measured is True
        assert secs == 1500

    def test_an_unparseable_dispatch_timestamp_degrades_to_self_reported(self):
        """Red if a malformed stamp raises instead of falling back. The tool is
        advice over a corpus it does not control; one bad row must not end the run."""
        secs, measured = yield_tool.duration(
            _event("2026-09-18T12:05:00Z", dispatched_at="not-a-timestamp", duration=420)
        )
        assert measured is False
        assert secs == 420

    def test_a_non_string_dispatch_timestamp_degrades_to_self_reported(self):
        """Red if `_parse` raises on a stamp that is not a string.

        Sibling of the malformed-string case above, and the same GUARANTEE reached by
        three routes: a malformed string fails inside `fromisoformat`, a number or a
        mapping fails one call earlier at `.replace()`, and a null never reaches
        `_parse` at all because `duration()`'s truthiness guard refuses it first. All
        three must fall back rather than raise — a hand-edited row or a writer from
        another toolchain produces them, and the tool is advice over a corpus it does
        not control.
        """
        for stamp in (1758196800, None, {"at": "2026-09-18T12:00:00Z"}):
            row = _event("2026-09-18T12:05:00Z", duration=420)
            row["dispatched_at"] = stamp
            secs, measured = yield_tool.duration(row)
            assert measured is False, stamp
            assert secs == 420, stamp


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

    def test_a_date_only_until_covers_that_whole_day(self, tmp_path):
        """Red if `--until` reverts to a bare string compare.

        `--until` documents itself inclusive. Compared as a raw string, a date-only
        bound excludes every timestamp on that date, which silently shortens the
        newest window — the one a before/after comparison is read from.
        """
        repo = _ledger(tmp_path, [_event("2026-09-01T23:59:00Z", duration=300)])
        assert len(yield_tool.load(repo, None, "2026-09-01")) == 1
        assert len(yield_tool.load(repo, None, "2026-08-31")) == 0

    def test_a_month_only_until_covers_that_whole_month(self, tmp_path):
        """Red if the bound reverts to special-casing the 10-character date.

        A month-only bound names a PERIOD: `--until 2026-09` covers the whole of
        September, and must agree with `--since 2026-09` about what the string means.
        """
        repo = _ledger(tmp_path, [_event("2026-09-30T23:59:00Z", duration=300)])
        assert len(yield_tool.load(repo, None, "2026-09")) == 1
        assert len(yield_tool.load(repo, None, "2026-08")) == 0

    def test_a_zoneless_until_matches_the_same_instant_in_utc(self, tmp_path):
        """Red if a bound typed without `Z` goes back to excluding its own instant —
        or, worse, raises on comparing a naive bound to an aware row."""
        repo = _ledger(tmp_path, [_event("2026-09-01T12:00:00Z", duration=300)])
        assert len(yield_tool.load(repo, None, "2026-09-01T12:00:00")) == 1
        assert len(yield_tool.load(repo, None, "2026-09-01T11:59:59")) == 0

    def test_a_full_timestamp_until_is_used_as_given(self, tmp_path):
        repo = _ledger(tmp_path, [_event("2026-09-01T12:00:00Z", duration=300)])
        assert len(yield_tool.load(repo, None, "2026-09-01T13:00:00Z")) == 1
        assert len(yield_tool.load(repo, None, "2026-09-01T11:00:00Z")) == 0


class TestAgainstRealLedgerRows:
    """These rows are REAL, captured verbatim from this repo's ledger and committed at
    `tests/fixtures/real-pr-reviews.jsonl`.

    The earlier version of this class read `.prawduct/.governance-ledger.jsonl` directly
    and skipped when absent. That file is gitignored, so the test was red only where it
    could see and silently skipped in CI — the one environment nobody watches — which is
    a `core.md` rule verbatim ("an exemption filter ... is red where it can see and GREEN
    where it cannot"). A skip is also indistinguishable from a pass in a summary. Real
    rows in the tree fix both: the point of reading a real artifact is that a fixture I
    wrote can only confirm what I already believed about the input, and that survives
    being committed.
    """

    FIXTURE = Path(__file__).resolve().parent / "fixtures" / "real-pr-reviews.jsonl"

    def _repo(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / ".prawduct").mkdir(parents=True)
        (repo / ".prawduct" / ".governance-ledger.jsonl").write_bytes(
            self.FIXTURE.read_bytes()
        )
        return repo

    def test_the_fixture_is_present_and_non_trivial(self):
        """Red if the fixture is deleted or emptied — without which every assertion
        below would pass having examined nothing."""
        assert self.FIXTURE.is_file(), "the captured real rows are missing"
        rows = [ln for ln in self.FIXTURE.read_text().splitlines() if ln.strip()]
        assert len(rows) >= 5

    def test_real_rows_parse_and_classify(self, tmp_path):
        """Red if the tool stops handling the shape real reviewers actually write —
        which is the shape no fixture of mine would have predicted."""
        data = yield_tool.report(yield_tool.load(self._repo(tmp_path), None, None))
        assert data["reviews"] >= 5
        assert data["findings"] > 0
        assert data["by_goal"], "real findings exist but none classified by goal"
        assert data["median_seconds"] is not None

    def test_real_rows_are_all_self_reported_today(self, tmp_path):
        """The provenance split, asserted against real data rather than my fixtures.

        Every historical row predates `dispatched_at`, so all of them must land in the
        self-reported population. This is the pre-change control for Chunk 01: when a
        measured row exists, it is because the mechanism works, not because the tool
        started guessing.
        """
        data = yield_tool.report(yield_tool.load(self._repo(tmp_path), None, None))
        assert data["with_duration"] == data["reviews"]
        assert data["measured_durations"] == 0
