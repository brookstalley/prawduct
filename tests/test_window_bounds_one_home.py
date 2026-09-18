"""The window predicate has ONE home, and both readers use it.

`architecture.md` § Direction: *every fact has one home; every other mention is a
reference to it* — if changing a fact requires editing N places, N−1 of them are
already wrong.

The fact here is "which events fall inside `[since, until]`". Two instruments
grade the same before/after split over the same governance ledger:
`review-stats` (`lib/telemetry.py`) and `tools/pr-review-yield.py`. Written out
at each of them it **had already diverged** — the tool compared a lower bound as
a bare string while the library parsed it — so the same `--since` selected
different populations in the two reports a person would naturally compare.

Shaped after `test_dispatch_interval_one_home.py`, and it carries that file's
warning: agreement alone is satisfiable by teaching every reader the same wrong
rule, so the DIRECTION is pinned separately at the home, with absolute values.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "plugin"))
sys.path.insert(0, str(REPO_ROOT / "plugin" / "lib"))

from lib import telemetry, timewindow  # noqa: E402


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "tools" / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


yield_tool = _load("pr_review_yield_wb", "pr-review-yield.py")

#: The discriminating input, and the exact shape the two copies disagreed on: a
#: zoned lower bound. `2026-08-04T12:00:00+02:00` IS 10:00Z, so an 11:00Z event
#: is inside the window — but as bare text "2026-08-04T11" sorts before
#: "2026-08-04T12", so a string compare drops it. Every PERIOD bound agrees
#: under both implementations, which is why no period fixture can catch this.
ZONED_SINCE = "2026-08-04T12:00:00+02:00"
INSIDE = "2026-08-04T11:00:00Z"
OUTSIDE = "2026-08-04T09:59:59Z"


class TestThePredicateItself:
    """Direction, pinned with absolute values at the home."""

    def test_a_zoned_lower_bound_is_interpreted(self):
        assert timewindow.in_window(INSIDE, ZONED_SINCE, None) is True
        assert timewindow.in_window(OUTSIDE, ZONED_SINCE, None) is False

    def test_a_period_bound_covers_its_whole_period(self):
        assert timewindow.in_window("2026-09-30T23:59:59Z", None, "2026-09") is True
        assert timewindow.in_window("2026-10-01T00:00:00Z", None, "2026-09") is False

    def test_an_impossible_period_is_not_a_usable_bound(self):
        assert timewindow.is_usable_bound("2026-09-30") is True
        assert timewindow.is_usable_bound("2026-09-31") is False
        assert timewindow.is_usable_bound("2026-02-29") is False, "2026 is not a leap year"


class TestBothReadersUseIt:
    """Agreement on the input where a copy WOULD differ."""

    # Identity is the WRONG test here and saying why is the point: the tool
    # loads `timewindow` off `sys.path` while this file imports it as a package
    # member, so Python holds two module objects for one file and `is` fails on
    # a correctly-shared predicate. The property is one SOURCE, not one object.
    HOME = timewindow.in_window.__code__.co_filename

    def test_the_library_reads_through_the_one_home(self):
        assert telemetry.in_window.__code__.co_filename == self.HOME

    def test_the_tool_reads_through_the_one_home(self):
        assert yield_tool.in_window.__code__.co_filename == self.HOME

    def test_the_pin_can_fail(self):
        """The control: a reader with its own copy must NOT satisfy the check
        above, or it passes for any function named `in_window`."""
        def in_window(ts, since, until):  # a private copy, defined right here
            return True
        assert in_window.__code__.co_filename != self.HOME

    def test_neither_reader_keeps_a_private_copy(self):
        # The copies that diverged. Their absence is the property; a reader that
        # re-grows one would pass every behavioural test above until it drifted.
        for module in (telemetry, yield_tool):
            for name in ("_parse", "_exceeds_upper", "_precedes_lower", "_parse_instant"):
                assert not hasattr(module, name), (
                    f"{module.__name__} has re-grown a private {name} — the window "
                    "predicate is one home, and a second copy is how it diverged before"
                )
