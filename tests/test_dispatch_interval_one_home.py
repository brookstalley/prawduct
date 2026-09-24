"""The dispatch-interval predicate has ONE home, and all three readers use it.

`architecture.md` § Direction: *every fact has one home; every other mention is a
reference to it* — if changing a fact requires editing N places, N−1 of them are
already wrong.

The fact here is "how many seconds does a dispatch mark attest, and which values
are refused". Three readers grade that same field for the same before/after
comparison: `review-stats`, `tools/pr-review-yield.py` and
`tools/measure-consumer-overhead.py`. Written out at each of them it diverged at
birth — one carried the plausibility bound, the other two refused only a negative
interval — so a stale same-tree mark inflated exactly the medians the comparison
is read from.

These tests assert AGREEMENT on the inputs where a copy would differ, and pin the
DIRECTION separately at the home itself: agreement alone is satisfiable by
teaching every reader the same wrong bound.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "plugin"))
sys.path.insert(0, str(REPO_ROOT / "plugin" / "lib"))

from lib import review_dispatch, telemetry  # noqa: E402


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "tools" / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


yield_tool = _load("pr_review_yield_oh", "pr-review-yield.py")
overhead = _load("measure_consumer_overhead_oh", "measure-consumer-overhead.py")

WROTE = "2026-09-18T12:00:00Z"
#: Just past MAX_PLAUSIBLE_REVIEW_SECONDS. The discriminating input: every copy
#: of this predicate accepted it except the one that carried the bound.
STALE_MARK = "2026-09-18T05:00:00Z"   # 7h before the write
GOOD_MARK = "2026-09-18T11:55:00Z"    # 5m before the write


def _event(dispatched_at: str) -> dict:
    return {
        "event": "review.pr",
        "ts": WROTE,
        "dispatched_at": dispatched_at,
        "duration_seconds": 420,
        "review": {"mode": "pr", "findings": [], "files_reviewed": ["a.py"]},
    }


class TestThePredicateItself:
    """Direction, pinned with absolute values. A test written RELATIVE to the
    constant (`MAX - 1`) moves with the constant and passes at every setting of
    it, so the bound is stated here in seconds."""

    def test_a_five_minute_interval_is_measured(self):
        assert review_dispatch.measured_interval_seconds(GOOD_MARK, WROTE) == 300.0

    def test_a_seven_hour_interval_is_refused(self):
        assert review_dispatch.measured_interval_seconds(STALE_MARK, WROTE) is None

    def test_the_bound_is_six_hours(self):
        """The bound is a historical fact about what shipped, not a variable —
        pin the value, not `MAX_PLAUSIBLE_REVIEW_SECONDS` compared to itself."""
        assert review_dispatch.MAX_PLAUSIBLE_REVIEW_SECONDS == 21600

    def test_the_boundary_itself_is_accepted(self):
        """Exactly at the bound is plausible; one second past is not. Red if the
        comparison flips between `>` and `>=`."""
        assert review_dispatch.measured_interval_seconds(
            "2026-09-18T06:00:00Z", WROTE
        ) == 21600.0
        assert review_dispatch.measured_interval_seconds(
            "2026-09-18T05:59:59Z", WROTE
        ) is None


class TestAllThreeReadersAgree:
    """Red if any reader reacquires its own copy of the predicate.

    Each assertion enters at the reader's OWN door — the function the reader
    actually calls in production — rather than at the shared helper, because
    pinning the shared helper proves the helper and not the wiring.
    """

    def test_a_stale_mark_is_refused_by_every_reader(self):
        event = _event(STALE_MARK)

        secs, measured = yield_tool.duration(event)
        assert measured is False, "pr-review-yield accepted a 7h interval"
        assert secs == 420, "the estimate must survive as the fallback"

        assert overhead._dispatch_clock_seconds(event) is None, (
            "measure-consumer-overhead accepted a 7h interval"
        )

        assert telemetry._measured_duration(event) is None, (
            "review-stats accepted a 7h interval"
        )

    def test_a_good_mark_is_measured_by_every_reader(self):
        """The positive control. Without it, a predicate that refused EVERYTHING
        would satisfy the agreement test above."""
        event = _event(GOOD_MARK)

        secs, measured = yield_tool.duration(event)
        assert (secs, measured) == (300, True)
        assert overhead._dispatch_clock_seconds(event) == 300.0
        assert telemetry._measured_duration(event) == 300.0

    @pytest.mark.parametrize(
        "mark", [None, 1758196800, "not-a-timestamp", "2026-09-18T13:00:00Z"]
    )
    def test_every_reader_refuses_the_same_bad_marks(self, mark):
        """Missing, wrong-typed, unparseable, and out-of-order — the four ways a
        mark attests nothing. All three readers must fall back together, or the
        populations they report are not the same partition."""
        event = _event(GOOD_MARK)
        event["dispatched_at"] = mark

        assert yield_tool.duration(event) == (420, False), mark
        assert overhead._dispatch_clock_seconds(event) is None, mark
        assert telemetry._measured_duration(event) is None, mark


def test_no_reader_defines_its_own_bound():
    """Red if a second copy of the constant reappears anywhere.

    The divergence this file exists to prevent did not look like a bug — it
    looked like three reasonable local implementations. A reader that redefines
    the bound is the shape to catch, not a wrong value.
    """
    for rel in ("tools/pr-review-yield.py", "tools/measure-consumer-overhead.py",
                "plugin/lib/telemetry.py"):
        source = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert "MAX_PLAUSIBLE_REVIEW_SECONDS =" not in source, (
            f"{rel} redefines the bound instead of importing it"
        )
        assert "6 * 60 * 60" not in source, f"{rel} inlines the bound"


def test_every_reader_ends_a_pr_interval_at_the_evidence_write():
    """Red if any reader ends the interval at `ts`. On a PR event, `ts` is
    the append, which comes after the caller fixed the review's findings."""
    event = _event(GOOD_MARK)
    event["ts"] = "2026-09-18T12:30:00Z"            # the append, 35m after the mark
    event["review_written_at"] = WROTE              # the review ended at 5m

    secs, measured = yield_tool.duration(event)
    assert (secs, measured) == (300, True)
    assert overhead._dispatch_clock_seconds(event) == 300.0
    assert telemetry._measured_duration(event) == 300.0
