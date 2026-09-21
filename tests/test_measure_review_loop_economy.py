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

    def test_the_ceiling_FOLLOWS_the_plugin_rather_than_matching_it_today(self, monkeypatch):
        """The discriminating half: equality with the constant is not reading it.

        `budget == core.REVIEW_ROUND_BUDGET_DEFAULT` is green against a hardcoded
        `6`, because the constant IS 6 — so it pins the value the tool happens to
        report and says nothing about where the value came from. Move the plugin's
        constant and the tool must move with it; a literal stays behind.
        """
        sys.path.insert(0, str(REPO_ROOT / "plugin"))
        from lib import core
        from lib import critic_consolidate as cc

        monkeypatch.setattr(core, "REVIEW_ROUND_BUDGET_DEFAULT", 99)
        monkeypatch.setattr(cc, "FULL_ROUND_MODES", ("chunk",))
        budget, full_modes, _ = tool._load_budget_params()
        assert budget == 99, "the ceiling is restated in the tool, not read from the plugin"
        assert full_modes == ("chunk",), "the counted modes are restated, not read"

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

    def test_the_flag_FOLLOWS_the_argument_rather_than_a_literal(self):
        """The half the assertion above cannot make: it restates the expression.

        `flag == (mode in full_modes)` is computed from the same set the code
        computes it from, so it is true of any implementation that uses that set
        — including one that ignores the argument and closes over a literal.
        Feed a DELIBERATELY WRONG set and the flag must follow it.
        """
        _, _, all_modes = tool._load_budget_params()
        rows = [_row(mode, scope=f"s{i}") for i, mode in enumerate(all_modes)]
        inverted = ("verify-resolutions",)
        report = tool.analyse(rows, 6, inverted)
        assert report["by_mode"]["verify-resolutions"]["counts_against_budget"] is True
        for mode in ("chunk", "final", "cumulative"):
            assert report["by_mode"][mode]["counts_against_budget"] is False, mode


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

    def test_a_ledger_row_without_a_scope_reads_as_absent_not_empty(self, tmp_path):
        """Through the PARSER, because that is where the direction is decided.

        This asserted `read_ledger.__doc__` and then analysed a hand-built row,
        so it never reached `read_ledger`'s `obj.get("scope")` — the one
        expression the test is named for. A parser returning `""` instead of
        `None` would key every scope-less row under one empty-string scope,
        which is hazard 8 arriving through the front door, and this test would
        have stayed green through it.
        """
        sibling = tool._load_sibling()
        ledger = tmp_path / "ledger.jsonl"
        ledger.write_text(
            '{"event":"review.critic","ts":"2026-09-01T00:00:00Z","duration_seconds":60,'
            '"review":{"mode":"cumulative (bundle review)","findings":[]}}\n',
            encoding="utf-8")

        events = sibling.read_ledger(ledger)

        assert len(events) == 1, "the fixture never reached the parser"
        assert events[0]["scope"] is None, (
            "an absent scope must read as None; an empty string is a scope key and "
            "would pool every scope-less row into one enormous scope")
        assert events[0]["scope"] != ""

    def test_the_parser_and_the_analysis_agree_on_absence(self, tmp_path):
        """The two halves joined: what the parser yields is what `analyse` counts.

        Pinning them separately is what let the old version pass — it graded a
        row the parser never produced.
        """
        sibling = tool._load_sibling()
        ledger = tmp_path / "ledger.jsonl"
        ledger.write_text(
            '{"event":"review.critic","ts":"2026-09-01T00:00:00Z","duration_seconds":60,'
            '"review":{"mode":"cumulative (bundle review)","findings":[]}}\n',
            encoding="utf-8")
        rows = [{"repo": "r", "scope": e["scope"], "mode": "cumulative",
                 "seconds": 60, "clock": None, "when": e["when"]}
                for e in sibling.read_ledger(ledger)]

        report = tool.analyse(rows, 6, ("cumulative",))

        assert report["scopeless_reviews"] == 1
        assert report["scopes"] == 0


class TestTheCorpusIsBoundedByPropertyNotByDepth:
    """`find_ledgers` must find a ledger wherever it sits, not one level down.

    The corpus is the instrument's most basic claim. A one-level glob reads as
    complete and silently drops delegated work, which runs in worktrees INSIDE a
    repo — three of this machine's twenty ledgers on 2026-09-21, and the excluded
    set is exactly the delegated work rather than a random sample.
    """

    def _ledger(self, root: Path, *parts: str) -> Path:
        d = root.joinpath(*parts) / ".prawduct"
        d.mkdir(parents=True)
        p = d / ".governance-ledger.jsonl"
        p.write_text("", encoding="utf-8")
        return p

    def test_a_nested_worktree_ledger_is_found(self, tmp_path):
        top = self._ledger(tmp_path, "repo")
        nested = self._ledger(tmp_path, "repo", ".claude", "worktrees", "agent-1")
        hidden = self._ledger(tmp_path, ".parked", "worktrees", "other")

        found = tool.find_ledgers(tmp_path)

        assert top in found, "the one-level case must keep working"
        assert nested in found, "a worktree ledger inside a repo was dropped"
        assert hidden in found, "a clone parked under a hidden directory was dropped"
        assert len(found) == 3

    def test_a_one_level_glob_would_have_missed_them(self, tmp_path):
        """The control: prove the fixture actually distinguishes the two scans.

        Without this, the test above passes for an implementation that is still
        one-level if the fixture happens to be flat — the tree has to be one the
        old predicate demonstrably fails on.
        """
        self._ledger(tmp_path, "repo")
        self._ledger(tmp_path, "repo", ".claude", "worktrees", "agent-1")

        one_level = sorted(tmp_path.glob("*/.prawduct/.governance-ledger.jsonl"))

        assert len(one_level) == 1
        assert len(tool.find_ledgers(tmp_path)) == 2

    def test_a_git_directory_is_pruned(self, tmp_path):
        """`.git` cannot hold a governed ledger and dominates the walk."""
        self._ledger(tmp_path, "repo")
        self._ledger(tmp_path, "repo", ".git", "modules", "x")

        assert len(tool.find_ledgers(tmp_path)) == 1


class TestTheHumanRendererRuns:
    """The default output path — `--json` is the exception, not the norm.

    Ported from the sibling's `TestTheHumanRenderer`, which this file had
    borrowed the design from and left behind: a `--json`-only suite never
    executes the formatter, so a crash there ships green.
    """

    def test_render_prints_every_section_without_raising(self, capsys):
        budget, full_modes, _ = tool._load_budget_params()
        rows = [_row("cumulative", scope="a"), _row("verify-resolutions", scope="a"),
                _row("chunk", scope="b"), _row("final", scope=None)]
        report = tool.analyse(rows, budget, full_modes)
        report["modes_known_to_the_plugin"] = ["chunk", "final", "cumulative",
                                               "verify-resolutions"]

        tool.render(report, [("repo", "3.6.1-dev", "2026-09-20T19:20-06:00")],
                    {"clone-a": ["repo", "repo-wt"]})

        out = capsys.readouterr().out
        for section in ("CORPUS", "CLOCK", "BY MODE", "BUDGET REACH",
                        "REPEAT CUMULATIVES", "MARKERS"):
            assert section in out, f"{section} missing from the human report"

    def test_render_survives_an_empty_marker_and_clone_set(self, capsys):
        """The degraded shape: a fresh machine has neither, and a crash here
        would take the whole report with it rather than one line."""
        budget, full_modes, _ = tool._load_budget_params()
        report = tool.analyse([_row("cumulative", scope="a")], budget, full_modes)
        report["modes_known_to_the_plugin"] = ["cumulative"]

        tool.render(report, [], {})

        assert "CORPUS" in capsys.readouterr().out


class TestTheFleetIsCountedInProductsNotLedgers:
    """`repos` must go through the clone, or open worktrees inflate the fleet.

    Hazard 3: each worktree keeps its own ledger, so counting ledger directories
    reports a fleet that grows when somebody opens a worktree and shrinks when
    they close one — a number that moves for reasons nothing to do with the
    fleet. The published reading said "13 repos" on this basis; the products are
    11.
    """

    CLONES = {"/c/one": ["repo-a", "repo-a-wt1", "repo-a-wt2"],
              "/c/two": ["repo-b"],
              "/c/three": ["repo-c"]}

    def test_worktrees_of_one_clone_count_once(self):
        rows = [_row("cumulative", repo=r) for r in ("repo-a", "repo-a-wt1", "repo-a-wt2")]
        assert tool.count_products(self.CLONES, rows) == 1
        assert len({r["repo"] for r in rows}) == 3, "the naive count would say 3"

    def test_each_distinct_clone_counts_once(self):
        rows = [_row("cumulative", repo=r) for r in ("repo-a-wt2", "repo-b", "repo-c")]
        assert tool.count_products(self.CLONES, rows) == 3

    def test_a_clone_with_no_rows_in_the_window_is_not_counted(self):
        """A ledger that exists but is silent since `--since` is not a product
        that contributed to this reading."""
        rows = [_row("cumulative", repo="repo-b")]
        assert tool.count_products(self.CLONES, rows) == 1
