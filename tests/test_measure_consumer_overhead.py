"""Guards for the dispatch-clock reading in `tools/measure-consumer-overhead.py`.

This tool had no test file before the dispatch clock reached it. These pin the
surface that was added, not the whole tool — its commit-density attribution, its
window logic and its PR fetching remain uncovered, and that gap is named in the
chunk's handoff rather than silently inherited.

What matters here is the SPLIT. The tool already uses the word "measured" for
interval-attributed time, which is a weaker and differently-biased thing than a
clock read either side of a dispatch. Pooling the two, or letting one borrow the
other's name, is the hazard the clock was added to retire.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_TOOL = Path(__file__).resolve().parent.parent / "tools" / "measure-consumer-overhead.py"


def _load():
    """Import the hyphenated script by path — not an importable module name."""
    spec = importlib.util.spec_from_file_location("measure_consumer_overhead", _TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["measure_consumer_overhead"] = module
    spec.loader.exec_module(module)
    return module


tool = _load()


def _event(**kw) -> dict:
    row = {"ts": "2026-09-18T12:05:00Z"}
    row.update(kw)
    return row


class TestDispatchClockReading:
    def test_a_marked_dispatch_yields_the_interval(self):
        assert tool._dispatch_clock_seconds(
            _event(dispatched_at="2026-09-18T12:00:00Z")
        ) == 300.0

    def test_an_unmarked_event_is_not_measured_rather_than_zero(self):
        """Red if absence ever becomes 0. Every event written before the clock
        existed lacks the mark, which is the whole of any existing ledger, so a
        zero here would drown every real reading it was averaged with."""
        assert tool._dispatch_clock_seconds(_event()) is None

    def test_an_out_of_order_pair_is_refused(self):
        """A clock skew or a hand-edited row can stamp the dispatch after the
        write. A negative interval parses cleanly and would be counted."""
        assert tool._dispatch_clock_seconds(
            _event(dispatched_at="2026-09-18T13:00:00Z")
        ) is None

    def test_a_malformed_or_non_string_stamp_degrades_rather_than_raising(self):
        """Three routes to the same guarantee: a malformed string fails inside
        `fromisoformat`, and a number or a null fails the type check before it.
        The tool reads a corpus it does not control; one bad row must not end a
        measurement run."""
        for stamp in ("not-a-timestamp", 1758196800, None, {"at": "x"}):
            assert tool._dispatch_clock_seconds(_event(dispatched_at=stamp)) is None, stamp

    def test_a_missing_ts_is_not_measured(self):
        """The interval needs both ends. An event with a mark and no `ts` is not
        half-measured."""
        row = {"dispatched_at": "2026-09-18T12:00:00Z"}
        assert tool._dispatch_clock_seconds(row) is None


class TestTheTwoMeasurementsStayApart:
    def test_the_clock_columns_are_named_distinctly_from_interval_measurement(self):
        """Red if the dispatch clock ever adopts the word `measured`.

        `critic_hours_measured` is interval-attributed time, biased by commit
        density (the tool's own hazard 2). The dispatch clock is a stronger
        reading. A shared name in a published row is a collision on a key
        readers already trust, and no test of either one alone would see it.
        """
        source = _TOOL.read_text(encoding="utf-8")
        assert '"pr_clock_runs"' in source
        assert '"pr_clock_hours"' in source
        assert '"pr_clock_measured"' not in source
        assert '"pr_hours_measured"' not in source

    def test_a_window_the_clock_never_reached_reports_none_not_zero(self):
        """Zero clocked reviews must render as "not measured", never as a window
        whose reviews were free. Every window of every existing ledger is this
        case, so it is the default rendering rather than an edge one."""
        assert tool._clock_columns(0, 0) == {
            "pr_clock_runs": 0,
            "pr_clock_hours": None,
            "pr_clock_minutes_per_review": None,
        }

    def test_the_hours_and_the_run_count_always_travel_together(self):
        """A clock figure without its denominator is unreadable: 0.3 hours over
        2 of a window's 40 reviews is not that window's cost. Red if a figure
        can ever ship without the count that makes it legible."""
        for total, runs in ((1800.0, 2), (300.0, 1), (0.0, 3)):
            cols = tool._clock_columns(total, runs)
            assert cols["pr_clock_runs"] == runs
            assert (cols["pr_clock_hours"] is None) == (cols["pr_clock_runs"] == 0)
            assert (cols["pr_clock_minutes_per_review"] is None) == (cols["pr_clock_runs"] == 0)

    def test_the_per_review_figure_divides_by_the_clocked_runs_only(self):
        """Red if the average is ever taken over ALL of a window's reviews
        rather than the clocked ones — that would silently dilute a real
        measurement with reviews the clock never saw."""
        assert tool._clock_columns(1800.0, 2)["pr_clock_minutes_per_review"] == 15.0
