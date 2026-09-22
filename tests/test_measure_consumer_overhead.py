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

        Asserted against the keys the function RENDERS rather than against
        source literals: the columns are built per review kind now, so the
        names are composed and a `"pr_clock_runs" in source` check would pass
        for any spelling while testing nothing. Both kinds are covered, because
        the collision this forbids is per-key.
        """
        for kind in ("pr", "critic"):
            cols = tool._clock_columns(kind, 1800.0, 2)
            assert f"{kind}_clock_runs" in cols
            assert f"{kind}_clock_hours" in cols
            assert not any("measured" in k for k in cols), (
                f"a {kind} clock column adopted the word `measured`, which "
                "`critic_hours_measured` already means (interval-attributed, "
                f"density-biased): {sorted(cols)}"
            )

    def test_each_kind_gets_its_own_columns_and_they_do_not_collide(self):
        """The clock reaches both review kinds; a function that can only name
        one is how the other's measurement is accumulated and then dropped at
        render time."""
        pr = tool._clock_columns("pr", 1800.0, 2)
        critic = tool._clock_columns("critic", 600.0, 1)
        assert set(pr).isdisjoint(critic), (
            f"the two kinds' columns share a key: {set(pr) & set(critic)}"
        )
        assert critic["critic_clock_minutes_per_review"] == 10.0

    def test_a_window_the_clock_never_reached_reports_none_not_zero(self):
        """Zero clocked reviews must render as "not measured", never as a window
        whose reviews were free. Every window of every existing ledger is this
        case, so it is the default rendering rather than an edge one."""
        for kind in ("pr", "critic"):
            assert tool._clock_columns(kind, 0, 0) == {
                f"{kind}_clock_runs": 0,
                f"{kind}_clock_hours": None,
                f"{kind}_clock_minutes_per_review": None,
            }

    def test_the_hours_and_the_run_count_always_travel_together(self):
        """A clock figure without its denominator is unreadable: 0.3 hours over
        2 of a window's 40 reviews is not that window's cost. Red if a figure
        can ever ship without the count that makes it legible."""
        for kind in ("pr", "critic"):
            for total, runs in ((1800.0, 2), (300.0, 1), (0.0, 3)):
                cols = tool._clock_columns(kind, total, runs)
                assert cols[f"{kind}_clock_runs"] == runs
                assert (cols[f"{kind}_clock_hours"] is None) == (runs == 0)
                assert (cols[f"{kind}_clock_minutes_per_review"] is None) == (runs == 0)

    def test_the_per_review_figure_divides_by_the_clocked_runs_only(self):
        """Red if the average is ever taken over ALL of a window's reviews
        rather than the clocked ones — that would silently dilute a real
        measurement with reviews the clock never saw."""
        assert tool._clock_columns("pr", 1800.0, 2)["pr_clock_minutes_per_review"] == 15.0


def _fixture_repo(root: Path) -> Path:
    """A repo that is its own product AND its own framework.

    Hermetic because `build_report` reads a GITIGNORED file:
    `.prawduct/.governance-ledger.jsonl` is untracked, and without it the
    function hits its own `sys.exit("no governance ledger")`. CI runs a bare
    `python -m pytest` on a fresh clone, where that file does not exist, so any
    fixture pointing at the real checkout passes only on a machine that has
    already been used.

    Skipping when the ledger is absent is the wrong remedy: it leaves the test
    red only where it can already see and green in the one environment that
    cannot. So the fixture brings its own ledger, commits and release tags, and
    is its own framework repo — nothing reaches outside `tmp_path`.
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
            # Marked, so the critic clock has a POSITIVE case at the render
            # surface: 13:00:00 dispatched, 13:04:00 written = 240s clocked
            # against a 300s self-report. Without a mark here the new
            # `clocked`/`clock h` columns are only ever seen in their
            # negative state, which passes identically if they are wired to
            # the wrong kind.
            event("review.critic", "2026-05-02T13:04:00Z", 300,
                  dispatched_at="2026-05-02T13:00:00Z"),
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

    Built by the producer rather than hand-authored: a dict written out here
    would encode a belief about the row's shape rather than the shape itself, and
    could only ever confirm that belief. The real keys are `engaged_hours` and a
    nested `lines` map, which is not what they look like from memory.
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

        The control has to be the CLOCK column: `min/review` is printed
        `{...:12.1f}` with no `None` branch, so asserting it is not a dash holds
        for a renderer that dashes the entire clock trio.
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


class TestEveryIsoParseSurvivesPython310:
    """`datetime.fromisoformat` only learned the `Z` suffix in **3.11**, and CI
    runs 3.10.

    This shipped broken and the maintainer could not see it, because reproducing
    it needs TWO independent environment facts at once:

    * **A UTC host.** `git log --format=%aI` renders `Z` only when the commit's
      stored zone is `+0000`. On a developer machine in any other zone the same
      fixture yields `-06:00`, which every Python version parses. CI runs UTC.
    * **Python < 3.11.** On 3.11+ the `Z` parses regardless, so the bug is
      invisible even on a UTC host.

    Neither alone reproduces it; the local suite was green for months and four
    tests failed on the branch's first CI run.

    **A behavioural test here would be vacuous** — this suite's own interpreter
    parses `Z` fine, so `_parse_instant("...Z")` passes with or without the fix.
    So the pin is the source property, which holds on every version: no call
    reaches `fromisoformat` with a stamp that has not been normalised, either by
    routing through the one home or by replacing the suffix at the call site.
    """

    @property
    def TOOLS(self):
        """Every tool, enumerated — never a hand-kept list of filenames.

        This was a hardcoded two-name tuple, which bounds the rule by its
        CONTAINER rather than by the property that justifies it: a tool added
        later is outside the guard while reading as covered, and the guard goes
        green having examined nothing about it. That is exactly what happened —
        `measure-review-loop-economy.py` shipped with an unnormalised
        `fromisoformat(args.since)` and this guard, the one written for that
        defect, could not see it. Enumerating means the next tool is covered on
        the day it lands, with nobody remembering to add it.
        """
        tools = sorted(p for p in (REPO_ROOT / "tools").glob("*.py"))
        assert tools, "no tools found to scan — the guard would pass vacuously"
        return tuple(str(p.relative_to(REPO_ROOT)) for p in tools)

    def test_the_scan_covers_every_tool(self):
        """The corpus is the guard's most basic claim, so assert it was reached.

        A set-shaped rule that asserts emptiness is satisfied by looking at
        nothing; this pins that the enumeration finds the real directory and
        includes the tool whose absence caused the miss.
        """
        assert "tools/measure-review-loop-economy.py" in self.TOOLS
        assert "tools/measure-consumer-overhead.py" in self.TOOLS

    def test_no_unnormalised_fromisoformat_call(self):
        offenders = []
        for rel in self.TOOLS:
            text = (REPO_ROOT / rel).read_text()
            for n, line in enumerate(text.splitlines(), 1):
                if "fromisoformat(" not in line:
                    continue
                normalised = 'replace("Z"' in line or "replace('Z'" in line
                # The one home normalises on the line that does the parse, so it
                # satisfies the same rule rather than needing an exemption.
                if not normalised:
                    offenders.append(f"{rel}:{n}: {line.strip()}")
        assert not offenders, (
            "these parse an ISO stamp without normalising a `Z` suffix, which "
            "raises ValueError on Python 3.10 (in CI) while passing on 3.11+ "
            "(locally). Route them through the tool's `_parse_instant`:\n  "
            + "\n  ".join(offenders)
        )

    def test_the_guard_can_see_an_offender(self):
        """The control: a rule asserting a set is empty is satisfied by looking
        at nothing, so prove the scan reaches real lines and can reject one."""
        sample = 'x = dt.datetime.fromisoformat(iso).astimezone(UTC)'
        assert "fromisoformat(" in sample
        assert 'replace("Z"' not in sample
        scanned = sum(
            1
            for rel in self.TOOLS
            for line in (REPO_ROOT / rel).read_text().splitlines()
            if "fromisoformat(" in line
        )
        assert scanned >= 5, (
            f"the scan found only {scanned} parse sites across {self.TOOLS} — "
            "it is not reaching the code it is meant to police"
        )


class TestTheCriticClockReachesTheReader:
    """The critic clock is accumulated per kind; these assert it is also
    RENDERED, which is the half that was missing when the columns were added.

    `clock[series]["critic"]` was populated and never read: `_clock_columns`
    could only name `pr`, so an operator comparing Critic review cost — this
    tool's stated job — read the estimate and could not tell from the output
    whether any Critic round had been clocked at all. Produced and never
    consumed.
    """

    def test_the_critic_clock_reaches_the_json_row(self, tmp_path):
        repo = _fixture_repo(tmp_path)
        report = tool.build_report(
            repo, repo, tool._parse_instant("2026-05-01"),
            want_prs=False, until_override=tool._parse_instant("2026-06-01"),
        )
        row = next(w for w in report["windows"] if w["critic_clock_runs"])
        assert row["critic_clock_runs"] == 1, (
            "the marked critic event did not reach the clock population"
        )
        # 13:00:00 -> 13:04:00 is 240s; the self-report on the same row is 300s,
        # so an assertion on the clock cannot be satisfied by the estimate.
        assert row["critic_clock_hours"] == round(240 / 3600, 2)
        assert row["critic_clock_minutes_per_review"] == 4.0
        assert row["critic_hours_self_reported"] != row["critic_clock_hours"]

    def test_the_critic_clock_reaches_the_human_output(self, tmp_path, capsys):
        """The `--json`-only tests cannot see the renderer, which is how the
        columns came to be accumulated and never printed in the first place."""
        repo = _fixture_repo(tmp_path)
        tool.render(tool.build_report(
            repo, repo, tool._parse_instant("2026-05-01"),
            want_prs=False, until_override=tool._parse_instant("2026-06-01"),
        ))
        out = capsys.readouterr().out
        # Anchored on the section's own full heading, not the bare word: table B
        # names VALIDATION too, and `startswith("VALIDATION")` binds to whichever
        # line comes first.
        row = _section_row(out, "VALIDATION — measured-interval", "v1.0")
        assert row.split()[-2:] == ["1", "0.07"], (
            "the clocked run count and hours are not the row's last pair — the "
            f"header and the values have drifted apart: {row!r}"
        )
        # The control: a window the clock never reached prints the count and an
        # explicit n/a, never a zero that reads as reviews which took no time.
        quiet = _section_row(out, "VALIDATION — measured-interval", "v1.1")
        assert quiet.split()[-2:] == ["0", "n/a"], quiet
