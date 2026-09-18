"""Guards for the dispatch-clock reading in `tools/measure-consumer-overhead.py`.

This tool had no test file before the dispatch clock reached it. These pin the
surface that was added, not the whole tool — its commit-density attribution, its
window logic and its PR fetching remain uncovered, and that gap is named in the
chunk's handoff rather than silently inherited.

`render()` is covered only where this change touched it. That is deliberate but
it was also a real gap: the clock columns were added to the row dict and to the
`--json` output while the human renderer printed neither, so the docstring
telling readers to consult them described output that did not exist. Nothing
caught it, and nothing caught the rule line that went two characters short of
its header either, because no test had ever run the renderer.

What matters here is the SPLIT. The tool already uses the word "measured" for
interval-attributed time, which is a weaker and differently-biased thing than a
clock read either side of a dispatch. Pooling the two, or letting one borrow the
other's name, is the hazard the clock was added to retire.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_TOOL = REPO_ROOT / "tools" / "measure-consumer-overhead.py"


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


def _fixture_repo(root: Path) -> Path:
    """A repo that is its own product AND its own framework.

    Hermetic on purpose. The first version of these tests pointed `build_report`
    at this checkout, and `.prawduct/.governance-ledger.jsonl` is GITIGNORED — so
    on a fresh clone `build_report` hits its own `sys.exit("no governance
    ledger")` and every renderer test dies. CI runs a bare `python -m pytest` on
    exactly that clone, so the local green was evidence about one machine.

    Skipping when the ledger is absent would be worse than the bug: the test
    would be red only where it can already see, and green in the one environment
    that cannot. So the fixture brings its own ledger, its own commits and its
    own release tags.
    """
    repo = root / "repo"
    (repo / ".prawduct").mkdir(parents=True)
    env = dict(
        os.environ,
        GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
        GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t",
        GIT_AUTHOR_DATE="2026-05-01T00:00:00", GIT_COMMITTER_DATE="2026-05-01T00:00:00",
    )

    def git(*args, when: str | None = None):
        e = dict(env)
        if when:
            e["GIT_AUTHOR_DATE"] = e["GIT_COMMITTER_DATE"] = when
        return subprocess.run(["git", *args], cwd=repo, capture_output=True, env=e, text=True)

    def event(kind: str, ts: str, duration: int, dispatched_at: str | None = None) -> dict:
        row = {
            "schema_version": 1, "event": kind, "ts": ts,
            "duration_seconds": duration, "project": "p", "scope": "s", "chunk": None,
            "actor": {"role": "pr" if kind == "review.pr" else "critic", "model": "opus"},
            "git": {"head": "a" * 40, "base": "main"},
            "review": {"mode": "pr", "files_reviewed": ["a.py"], "findings": []},
        }
        if dispatched_at:
            row["dispatched_at"] = dispatched_at
        return row

    git("init", "-q", "-b", "main")
    (repo / ".prawduct" / ".governance-ledger.jsonl").write_text(
        "\n".join(json.dumps(e) for e in [
            event("review.pr", "2026-05-02T12:00:00Z", 600),
            event("review.critic", "2026-05-02T13:00:00Z", 300),
        ]) + "\n"
    )
    (repo / "app.py").write_text("print(1)\n")
    git("add", "-A"); git("commit", "-qm", "feat: a thing"); git("tag", "v1.0.0")
    (repo / "b.py").write_text("print(2)\n")
    git("add", "-A", when="2026-05-10T00:00:00")
    git("commit", "-qm", "feat: two", when="2026-05-10T00:00:00")
    git("tag", "v1.1.0", when="2026-05-10T00:00:00")
    return repo


def _report(tmp_path: Path, **row_overrides) -> dict:
    """A report built by the tool's OWN producer over the hermetic fixture.

    Hand-authoring this dict encodes a belief about the row's shape rather than
    the shape itself — an earlier attempt invented `hours` and `lines_written`
    where the real keys are `engaged_hours` and a nested `lines` map, so it could
    only ever have confirmed what its author already thought.
    """
    repo = _fixture_repo(tmp_path)
    report = tool.build_report(
        repo, repo, tool._parse_instant("2026-05-01"),
        want_prs=False, until_override=tool._parse_instant("2026-06-01"),
    )
    assert report["windows"], "build_report produced no windows — the test would be vacuous"
    row = dict(report["windows"][-1])
    row.update(row_overrides)
    report = dict(report)
    report["windows"] = [row]
    return report


def _column(out: str, section_heading: str, series: str, label: str) -> str:
    """The value under `label` in `series`'s row of the named section.

    Asserting against the whole ROW is not asserting against the column: section
    C already prints an em dash for `merged` and for `median open h`, so a bare
    `assert "—" in line` passes whenever EITHER of those is absent — which is
    always, without `--prs`. A mutation sweep caught exactly that. The columns
    are fixed-width and right-aligned, so the header's own span for a label is
    the span the value occupies.
    """
    lines = out.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith(section_heading))
    header = next(ln for ln in lines[start:] if label in ln)
    end = header.index(label) + len(label)
    begin = end - len(label)
    # Widen left to the previous column's end so a right-aligned value that is
    # longer than its header still falls inside the slice.
    while begin > 0 and header[begin - 1] == " ":
        begin -= 1
    row = _section_row(out, section_heading, series)
    return row[begin:end].strip()


def _section_row(out: str, section_heading: str, series: str) -> str:
    """The window row for `series` inside the named section.

    Every section prints a row per window, each starting with the series name,
    so an assertion that greps the whole output binds to whichever section came
    first — which is not the one under test.
    """
    lines = out.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith(section_heading))
    for ln in lines[start:]:
        if ln.startswith(series):
            return ln
    raise AssertionError(f"no {series!r} row under {section_heading!r}")


class TestTheHumanRenderer:
    """The default output — the surface a reader actually meets. Every assertion
    here exists because the `--json`-only tests above could not see it."""

    def test_the_clock_columns_reach_the_default_output(self, tmp_path, capsys):
        """The fix's own promise, and the POSITIVE half of the dash control.

        A window the clock reached prints its figure in the clock column. Paired
        with the dash test below, this is what makes either one a control: a
        renderer that dashed the whole trio would pass the dash test alone, and
        one that printed 0.0 everywhere would pass this one alone.

        The earlier version of this pair used `min/review != "—"` as its
        positive — but that column is printed `{...:12.1f}` with no `None`
        branch, so it can never be a dash and the assertion could not fail.
        """
        report = _report(tmp_path, pr_clock_runs=3, pr_clock_hours=0.5,
                         pr_clock_minutes_per_review=10.0)
        series = report["windows"][0]["series"]
        tool.render(report)
        out = capsys.readouterr().out
        assert "clk runs" in out
        assert "clk min/rev" in out
        assert _column(out, "C. PR LAYER", series, "clk min/rev") == "10.0"
        assert _column(out, "C. PR LAYER", series, "clk runs") == "3"

    def test_a_window_the_clock_never_reached_renders_a_dash_not_a_zero(self, tmp_path, capsys):
        """A 0.0 in the minutes column would read as reviews that took no time,
        rather than as a window the clock had not reached."""
        report = _report(tmp_path)
        series = report["windows"][0]["series"]
        tool.render(report)
        # Scoped to the PR-layer section: EVERY section prints a row starting
        # with the series name, so an unscoped match grades section A and passes
        # or fails for reasons that have nothing to do with the clock.
        out = capsys.readouterr().out
        # The CLOCK column specifically — not "is there a dash anywhere in the
        # row", which every unfetched `--prs` run satisfies for free.
        assert _column(out, "C. PR LAYER", series, "clk min/rev") == "—"

    def test_every_rule_line_matches_the_header_above_it(self, tmp_path, capsys):
        """Red if any section's rule is a hand-counted second copy of its
        header's width. Section C drifted to two characters short the moment two
        columns were added, and no test had ever run this function.
        """
        tool.render(_report(tmp_path, ))
        lines = capsys.readouterr().out.splitlines()
        rules = [(i, ln) for i, ln in enumerate(lines) if set(ln) == {"-"} and len(ln) > 10]
        assert rules, "found no rule lines — the test would be vacuous"
        for i, rule in rules:
            header = lines[i - 1]
            assert len(rule) == len(header), (
                f"rule is {len(rule)} chars under a {len(header)}-char header: {header!r}"
            )

    def test_the_pr_section_says_which_population_its_hours_are(self, tmp_path, capsys):
        """Section B names its population ("the ledger's self-report"); C did
        not, so its `hours` column was unlabelled beside a clock column."""
        tool.render(_report(tmp_path, ))
        out = capsys.readouterr().out
        assert "self-rep" in out
