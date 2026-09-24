"""The evidence record keeps WHICH tests failed, not only how many (#792).

A record reading ``failed: 2`` and nothing else sent its reader back to a second
full-suite run just to learn the two names. The junit report the recorder
parses already carries them, so ``test-evidence record`` keeps them as
``failed_tests`` and every surface that prints the failing-record reason
(``test-status``, the PR-gate transfer, the PR review payload) names them.

``failed_tests`` is present only when the recorder saw per-test ids for at least
one failure. Its absence means "no ids were available", never "nothing failed" —
``failed`` stays the count of record, which is why the cap test checks both.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_plugin_runtime import _git, _run_in  # noqa: E402


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "ids"
    repo.mkdir()
    (repo / ".prawduct").mkdir()
    (repo / "test_sample.py").write_text("def test_ok():\n    assert True\n")
    _git(repo, "init", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "c1")
    return repo


def _record(repo: Path, xml: str, *extra: str):
    junit = repo / "report.xml"
    junit.write_text('<?xml version="1.0" encoding="utf-8"?>\n' + xml)
    res = _run_in(repo, "test-evidence", "record", "--from-junit", str(junit), *extra)
    ev = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
    return res, ev


_MIXED = """
<testsuites>
  <testsuite name="one" time="1.0">
    <testcase classname="tests.test_a.TestX" name="test_passes"/>
    <testcase classname="tests.test_a.TestX" name="test_fails"><failure message="f"/></testcase>
    <testcase classname="tests.test_a" name="test_skipped"><skipped/></testcase>
  </testsuite>
  <testsuite name="two" time="1.0">
    <testcase name="bare_errors"><error message="e"/></testcase>
    <testcase classname="tests.test_b" name="test_both"><failure/><error/></testcase>
  </testsuite>
</testsuites>
"""

_EXPECTED = [
    "tests.test_a.TestX::test_fails",
    "bare_errors",
    "tests.test_b::test_both",
]


class TestTheRecordKeepsTheNames:
    def test_failures_and_errors_are_recorded_in_report_order(self, tmp_path):
        res, ev = _record(_repo(tmp_path), _MIXED)
        assert res.returncode == 1
        assert ev["failed"] == 3
        assert ev["failed_tests"] == _EXPECTED
        # the plugin's own validator accepts what the plugin produced
        assert _run_in(tmp_path / "ids", "validate-evidence").returncode == 0

    def test_a_passing_run_writes_no_key(self, tmp_path):
        """Absence is the passing shape; a writer emitting ``[]`` would give
        every pre-existing reader a key it never had to reason about."""
        res, ev = _record(_repo(tmp_path), """
<testsuites><testsuite name="s" time="1.0">
  <testcase classname="c" name="ok"/>
</testsuite></testsuites>
""")
        assert res.returncode == 0, res.stderr
        assert ev["failed"] == 0
        assert "failed_tests" not in ev

    def test_a_summary_only_suite_has_no_ids_to_keep(self, tmp_path):
        """The failures are real (``failed`` says so); the report named none."""
        res, ev = _record(_repo(tmp_path), """
<testsuites><testsuite name="agg" tests="5" failures="2" errors="0" skipped="0" time="1.0"/></testsuites>
""")
        assert ev["failed"] == 2
        assert "failed_tests" not in ev

    def test_from_counts_has_no_ids_to_keep(self, tmp_path):
        repo = _repo(tmp_path)
        _run_in(repo, "test-evidence", "record", "--from-counts",
                "passed=3", "failed=2", "skipped=0")
        ev = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert ev["failed"] == 2
        assert "failed_tests" not in ev

    def test_a_case_with_no_name_still_gets_an_id(self, tmp_path):
        _, ev = _record(_repo(tmp_path), """
<testsuites><testsuite name="s" time="1.0">
  <testcase classname="c"><failure/></testcase>
</testsuite></testsuites>
""")
        assert ev["failed_tests"] == ["c::(unnamed)"]

    def test_the_list_is_capped_and_the_count_stays_true(self, tmp_path):
        cases = "".join(
            f'<testcase classname="m" name="t{i:03d}"><failure/></testcase>'
            for i in range(130)
        )
        _, ev = _record(_repo(tmp_path),
                        f'<testsuites><testsuite name="s" time="1">{cases}</testsuite></testsuites>')
        assert ev["failed"] == 130
        assert len(ev["failed_tests"]) == 100
        assert ev["failed_tests"][0] == "m::t000"
        assert ev["failed_tests"][-1] == "m::t099"

    def test_a_restamp_carries_the_names_with_the_counts(self, tmp_path):
        """A restamp reuses the prior run's counts, so it must reuse the names
        that explain them — dropping them would print ``failed: 3`` with the
        answer to "which?" silently gone."""
        repo = _repo(tmp_path)
        _record(repo, _MIXED)
        res = _run_in(repo, "test-evidence", "record", "--no-rerun")
        ev = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert "restamped" in res.stdout
        assert ev["failed"] == 3
        assert ev["failed_tests"] == _EXPECTED


class TestTheNamesArePrinted:
    def test_the_recorded_line_names_them(self, tmp_path):
        res, _ = _record(_repo(tmp_path), _MIXED)
        for name in _EXPECTED:
            assert name in res.stdout

    def test_test_status_names_them(self, tmp_path):
        repo = _repo(tmp_path)
        _record(repo, _MIXED)
        res = _run_in(repo, "test-status")
        assert res.returncode == 1
        assert "3 test(s) failing in saved evidence" in res.stdout
        for name in _EXPECTED:
            assert name in res.stdout
        assert "(+" not in res.stdout

    def test_test_status_says_how_many_it_did_not_print(self, tmp_path):
        """Ten names on the line; the rest split into names the record holds
        and failures it holds no name for, counted from ``failed`` so a capped
        record still reports the true total it left out."""
        repo = _repo(tmp_path)
        cases = "".join(
            f'<testcase classname="m" name="t{i:03d}"><failure/></testcase>'
            for i in range(130)
        )
        _record(repo, f'<testsuites><testsuite name="s" time="1">{cases}</testsuite></testsuites>')
        res = _run_in(repo, "test-status")
        assert "m::t009" in res.stdout
        assert "m::t010" not in res.stdout
        assert "(+90 more in .prawduct/.test-evidence.json; +30 unnamed)" in res.stdout

    def test_failures_the_report_did_not_name_are_still_counted(self, tmp_path):
        """One report can mix a populated suite with a summary-only one, so
        some failures have ids and some do not; the line must not claim the
        named ones are all of them."""
        repo = _repo(tmp_path)
        _record(repo, """
<testsuites>
  <testsuite name="one" time="1.0">
    <testcase classname="c" name="named"><failure/></testcase>
  </testsuite>
  <testsuite name="agg" tests="4" failures="2" errors="0" skipped="0" time="1.0"/>
</testsuites>
""")
        res = _run_in(repo, "test-status")
        assert "3 test(s) failing in saved evidence: c::named" in res.stdout
        assert "c::named (+2 unnamed)" in res.stdout

    def test_a_fully_named_remainder_claims_no_unnamed_failures(self, tmp_path):
        repo = _repo(tmp_path)
        cases = "".join(
            f'<testcase classname="m" name="t{i:02d}"><failure/></testcase>'
            for i in range(12)
        )
        _record(repo, f'<testsuites><testsuite name="s" time="1">{cases}</testsuite></testsuites>')
        res = _run_in(repo, "test-status")
        assert "m::t09 (+2 more in .prawduct/.test-evidence.json)" in res.stdout
        assert "unnamed" not in res.stdout


class TestTheKeyCannotMoveAVerdict:
    """``failed_tests`` is only ever printed, so it is deliberately left out of
    the evidence schema: validating its type would let a writer that put
    something else under the name turn a passing record stale."""

    def _edit(self, repo: Path, value) -> None:
        path = repo / ".prawduct" / ".test-evidence.json"
        ev = json.loads(path.read_text())
        ev["failed_tests"] = value
        path.write_text(json.dumps(ev))

    def test_a_malformed_value_on_a_passing_record_stays_current(self, tmp_path):
        repo = _repo(tmp_path)
        res, _ = _record(repo, """
<testsuites><testsuite name="s" time="1.0"><testcase classname="c" name="ok"/></testsuite></testsuites>
""")
        assert res.returncode == 0, res.stderr
        self._edit(repo, 3)
        status = _run_in(repo, "test-status")
        assert status.returncode == 0, status.stdout
        assert status.stdout.startswith("current")

    def test_non_string_ids_print_no_names(self, tmp_path):
        repo = _repo(tmp_path)
        _record(repo, _MIXED)
        self._edit(repo, [1, 2])
        status = _run_in(repo, "test-status")
        assert status.returncode == 1
        assert status.stdout.strip() == "stale: 3 test(s) failing in saved evidence"
