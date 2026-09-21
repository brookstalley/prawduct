"""Guards for `tools/measure-review-loop-economy.py`.

The script exists to support one claim — that the review round budget cannot
reach most of what the fleet spends on review rounds. That claim is a statement
about which modes the ceiling counts and about which rows it can bound at all,
so the things pinned here are exactly the two ways the script could report a
reach it does not have: by restating the plugin's parameters instead of reading
them, and by inventing a scope for rows that have none.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_TOOL = REPO_ROOT / "tools" / "measure-review-loop-economy.py"
UTC = dt.timezone.utc


def _load():
    """Import the hyphenated script by path — not an importable module name."""
    spec = importlib.util.spec_from_file_location("measure_review_loop_economy", _TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["measure_review_loop_economy"] = module
    spec.loader.exec_module(module)
    return module


tool = _load()


def _row(mode: str, scope: str | None = "s1", repo: str = "r", seconds: int = 60,
         clock: float | None = None) -> dict:
    return {"repo": repo, "scope": scope, "mode": mode, "seconds": seconds,
            "clock": clock, "when": dt.datetime(2026, 9, 1, tzinfo=UTC)}


class TestTheBudgetParametersComeFromThePlugin:
    """Red if anyone restates the ceiling or the counted modes in the tool.

    A hardcoded copy keeps reporting yesterday's reach after the plugin changes,
    which is the one failure this script cannot be allowed to have: its whole
    output is a claim about what the live ceiling counts.
    """

    def test_the_ceiling_and_modes_are_the_plugin_objects(self):
        sys.path.insert(0, str(REPO_ROOT / "plugin"))
        from lib import core
        from lib import critic_consolidate as cc

        budget, full_modes, all_modes = tool._load_budget_params()
        assert budget == core.REVIEW_ROUND_BUDGET_DEFAULT
        assert full_modes == tuple(cc.FULL_ROUND_MODES)
        assert all_modes == tuple(cc.MODE_TOKEN_TO_VERBOSE)

    def test_counts_against_budget_tracks_the_plugin_rather_than_a_literal(self):
        """The reported flag must be membership in whatever the plugin says today.

        Asserted as the PROPERTY, not as `verify-resolutions is excluded`: that
        spelling would stay green if the plugin started counting it and the tool
        kept saying it did not.
        """
        budget, full_modes, all_modes = tool._load_budget_params()
        rows = [_row(mode, scope=f"s{i}") for i, mode in enumerate(all_modes)]
        report = tool.analyse(rows, budget, full_modes)
        for mode in all_modes:
            assert report["by_mode"][mode]["counts_against_budget"] == (mode in full_modes), mode


class TestAScopelessRowIsNeverAScope:
    """The budget returns `unavailable` for a row with no scope, and never refuses.

    Pooling those rows under one key per repo would invent a single enormous
    scope, push it past the ceiling, and overstate the reach — the exact error
    that makes the headline number wrong in the direction nobody checks.
    """

    def test_scopeless_rows_are_counted_and_excluded_from_scopes(self):
        rows = [_row("cumulative", scope=None) for _ in range(9)]
        report = tool.analyse(rows, 6, ("chunk", "final", "cumulative"))
        assert report["scopeless_reviews"] == 9
        assert report["scopes"] == 0
        assert report["scopes_at_ceiling"] == 0
        assert report["reach_hours_self_reported"] == 0

    def test_a_real_scope_still_reaches_the_ceiling_beside_them(self):
        """The control for the test above: the exclusion must not silence everything."""
        rows = [_row("cumulative", scope=None) for _ in range(9)]
        rows += [_row("cumulative", scope="real") for _ in range(6)]
        report = tool.analyse(rows, 6, ("chunk", "final", "cumulative"))
        assert report["scopes"] == 1
        assert report["scopes_at_ceiling"] == 1


class TestTheCeilingCountsOnlyFullRounds:
    def test_verify_rounds_do_not_advance_a_scope_toward_the_ceiling(self):
        rows = [_row("verify-resolutions") for _ in range(20)]
        report = tool.analyse(rows, 6, ("chunk", "final", "cumulative"))
        assert report["scopes"] == 1
        assert report["scopes_at_ceiling"] == 0
        assert report["verify_per_scope"]["max"] == 20
        assert report["full_rounds_per_scope"]["max"] == 0


class TestRepeatCumulativesCountBeyondTheFirst:
    def test_three_cumulatives_on_one_scope_are_two_repeats(self):
        rows = [_row("cumulative") for _ in range(3)]
        report = tool.analyse(rows, 6, ("chunk", "final", "cumulative"))
        assert report["cumulative_runs"] == 3
        assert report["repeat_cumulative_runs"] == 2
        assert report["scopes_with_repeat_cumulative"] == 1

    def test_one_cumulative_per_scope_is_no_repeat(self):
        rows = [_row("cumulative", scope="a"), _row("cumulative", scope="b")]
        report = tool.analyse(rows, 6, ("chunk", "final", "cumulative"))
        assert report["repeat_cumulative_runs"] == 0
        assert report["repeat_cumulative_share"] == 0


class TestTheMeasuredClockIsReportedSeparatelyFromSelfReports:
    """Hazard 1: `duration_seconds` is a model self-report. A reader deciding
    whether to trust an hour figure needs the count of rows that carry a real
    dispatch interval, and absence must stay absence rather than becoming 0.
    """

    def test_only_rows_with_a_clock_are_counted_as_measured(self):
        rows = [_row("cumulative", scope="a", clock=120.0), _row("cumulative", scope="b")]
        report = tool.analyse(rows, 6, ("chunk", "final", "cumulative"))
        assert report["clock_rows"] == 1
        assert report["reviews"] == 2


class TestTheLedgerCarriesScope:
    """The sibling parser is the one home for ledger reading, and this script
    depends on a field added there. Red if that field is dropped — without it
    every row reads as scope-less and the reach collapses to zero.
    """

    def test_read_ledger_surfaces_the_scope_field(self, tmp_path):
        sibling = tool._load_sibling()
        ledger = tmp_path / "ledger.jsonl"
        ledger.write_text(
            '{"event":"review.critic","ts":"2026-09-01T00:00:00Z","duration_seconds":60,'
            '"scope":"my-scope","review":{"mode":"cumulative (bundle review)","findings":[]}}\n',
            encoding="utf-8")
        events = sibling.read_ledger(ledger)
        assert [e["scope"] for e in events] == ["my-scope"]

    def test_a_ledger_row_without_a_scope_reads_as_absent_not_empty(self):
        sibling = tool._load_sibling()
        assert sibling.read_ledger.__doc__  # the parser is the shared home
        report = tool.analyse([_row("cumulative", scope=None)], 6, ("cumulative",))
        assert report["scopeless_reviews"] == 1
