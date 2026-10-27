"""Tests that passed only on retry are recorded as flakes, not hidden in a green (#1087).

A runner that retries failed tests reports the pass, and a gate reading only the
counts sees a clean green — including when the retry hid a race the branch
introduced. The recorder keeps each such test as a ``flaky`` entry: its id, how
many times it failed first, the first failure's text, and where the retry came
from. The entry is printed and carried; it never moves a verdict by being read,
so it stays out of the evidence schema exactly as ``failed_tests`` does.

This file covers the JUnit half: Surefire's convention, which records a failed
attempt that a rerun then passed as ``<flakyFailure>``/``<flakyError>`` beside no
final ``<failure>``, and a test that failed every attempt as
``<rerunFailure>``/``<rerunError>`` beside one.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "plugin"))

from test_plugin_runtime import _git, _run_in  # noqa: E402

from lib import evidence  # noqa: E402


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "flaky"
    repo.mkdir()
    (repo / ".prawduct").mkdir()
    (repo / "test_sample.py").write_text("def test_ok():\n    assert True\n")
    _git(repo, "init", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "c1")
    return repo


def _record(repo: Path, cases: str, *extra: str):
    junit = repo / "report.xml"
    junit.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<testsuites><testsuite name="s" time="1.0">{cases}</testsuite></testsuites>'
    )
    res = _run_in(repo, "test-evidence", "record", "--from-junit", str(junit), *extra)
    ev = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
    return res, ev


_FLAKY_CASE = """
<testcase classname="tests.test_net.TestPool" name="test_timeout" file="tests/test_net.py">
  <flakyFailure message="Timeout after 5s" type="TimeoutError">
    <stackTrace>Traceback ...
TimeoutError: Timeout after 5s</stackTrace>
  </flakyFailure>
</testcase>
<testcase classname="tests.test_net" name="test_ok"/>
"""


class TestJunitFlakesAreRecorded:
    def test_a_flaky_failure_is_a_pass_that_carries_a_flake(self, tmp_path):
        res, ev = _record(_repo(tmp_path), _FLAKY_CASE)
        assert res.returncode == 0, res.stderr
        assert (ev["passed"], ev["failed"]) == (2, 0)
        assert "failed_tests" not in ev
        assert ev["flaky"] == [{
            "id": "tests.test_net.TestPool::test_timeout",
            "first_failure": "Timeout after 5s",
            "attempts": 1,
            "source": "junit",
            "file": "tests/test_net.py",
        }]
        # the plugin's own validator accepts what the plugin produced
        assert _run_in(tmp_path / "flaky", "validate-evidence").returncode == 0

    def test_a_flaky_error_counts_and_every_attempt_is_counted(self, tmp_path):
        """No ``message`` falls back to the stack trace's first line; two
        attempts before the pass are two, whichever element kind each is; and
        the first is the first in the report, which here is not the first by
        tag name — so a reader that groups by kind names the wrong attempt."""
        _, ev = _record(_repo(tmp_path), """
<testcase classname="m" name="t">
  <flakyFailure type="OSError"><stackTrace>
    OSError: connection reset
    at line 3</stackTrace></flakyFailure>
  <flakyError message="second"><stackTrace>x</stackTrace></flakyError>
</testcase>
""")
        assert ev["failed"] == 0
        (entry,) = ev["flaky"]
        assert entry["attempts"] == 2
        assert entry["first_failure"] == "OSError: connection reset"
        assert "file" not in entry  # unknown, never guessed

    def test_a_test_that_failed_every_rerun_stays_failed(self, tmp_path):
        """``rerunFailure`` rides beside the final ``failure``: the test never
        passed, so it is a failure and not a flake."""
        res, ev = _record(_repo(tmp_path), """
<testcase classname="m" name="always">
  <failure message="final"/>
  <rerunFailure message="retry 1"><stackTrace>x</stackTrace></rerunFailure>
</testcase>
""")
        assert res.returncode == 1
        assert ev["failed"] == 1
        assert ev["failed_tests"] == ["m::always"]
        assert "flaky" not in ev

    def test_a_run_with_no_flakes_writes_no_key(self, tmp_path):
        """Absence is the clean shape; ``[]`` would hand every reader a key it
        never had to reason about."""
        _, ev = _record(_repo(tmp_path), '<testcase classname="m" name="ok"/>')
        assert "flaky" not in ev

    def test_the_failure_text_is_bounded(self, tmp_path):
        long = "x" * 1000
        _, ev = _record(_repo(tmp_path), f"""
<testcase classname="m" name="t"><flakyFailure message="{long}"><stackTrace/></flakyFailure></testcase>
""")
        assert len(ev["flaky"][0]["first_failure"]) == 300

    def test_the_list_is_sorted_and_capped(self, tmp_path):
        cases = "".join(
            f'<testcase classname="m" name="t{i:02d}"><flakyFailure message="f"><stackTrace/></flakyFailure></testcase>'
            for i in reversed(range(25))
        )
        _, ev = _record(_repo(tmp_path), cases)
        assert ev["passed"] == 25
        assert [e["id"] for e in ev["flaky"]] == [f"m::t{i:02d}" for i in range(20)]

    def test_a_restamp_carries_the_flakes_with_the_counts(self, tmp_path):
        """A restamp reuses a green that passed only on retry; dropping the
        flakes would launder it into a clean one without running anything."""
        repo = _repo(tmp_path)
        _record(repo, _FLAKY_CASE)
        res = _run_in(repo, "test-evidence", "record", "--no-rerun")
        assert res.returncode == 0, res.stderr
        ev = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert [e["id"] for e in ev["flaky"]] == ["tests.test_net.TestPool::test_timeout"]

    def test_the_test_run_fact_carries_the_flakes(self, tmp_path):
        repo = _repo(tmp_path)
        _record(repo, _FLAKY_CASE)
        (fact,) = evidence.facts_of_kind(evidence.read_facts(repo), "test-run")
        body = fact["body"]
        assert [e["id"] for e in body["flaky"]] == ["tests.test_net.TestPool::test_timeout"]


class TestFlakesArePrinted:
    def test_the_recorded_line_names_them(self, tmp_path):
        res, _ = _record(_repo(tmp_path), _FLAKY_CASE)
        line = next(ln for ln in res.stdout.splitlines() if "passed only on retry" in ln)
        assert "tests.test_net.TestPool::test_timeout (failed 1×)" in line

    def test_a_clean_run_prints_no_flake_line(self, tmp_path):
        res, _ = _record(_repo(tmp_path), '<testcase classname="m" name="ok"/>')
        assert res.returncode == 0
        assert "passed only on retry" not in res.stdout

    def test_test_status_lists_them_after_the_verdict(self, tmp_path):
        repo = _repo(tmp_path)
        _record(repo, _FLAKY_CASE)
        res = _run_in(repo, "test-status")
        lines = res.stdout.splitlines()
        assert lines[0].startswith(("current", "stale"))
        assert lines[1] == (
            "flaky: tests.test_net.TestPool::test_timeout — passed on the runner's "
            "retry after 1 failure(s); first: Timeout after 5s"
        )

    def test_a_malformed_flaky_value_changes_nothing(self, tmp_path):
        """Not in the schema: a writer that put anything else under the key
        must not turn a passing record stale, nor crash the status line."""
        repo = _repo(tmp_path)
        _record(repo, '<testcase classname="m" name="ok"/>')
        before = _run_in(repo, "test-status")
        path = repo / ".prawduct" / ".test-evidence.json"
        for bad in ("oops", [1, {"no": "id"}], {"id": "x"}):
            ev = json.loads(path.read_text())
            ev["flaky"] = bad
            path.write_text(json.dumps(ev))
            res = _run_in(repo, "test-status")
            assert res.returncode == before.returncode, (bad, res.stdout, res.stderr)
            assert "flaky:" not in res.stdout
            assert "Traceback" not in res.stderr

