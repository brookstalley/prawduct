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


# ---------------------------------------------------------------------------
# --rerun-failed: the recorder's own retry of a live run's failures
# ---------------------------------------------------------------------------

#: A stand-in for a declared test command. It reads a plan of outcomes per test
#: (one per invocation, the last repeating), writes JUnit for the tests it was
#: asked to run — all of them with no selection, else only the node ids given —
#: logs its argv, and exits 1 when anything failed, as a real runner does.
_FAKE_RUNNER = r'''
import json, sys
from pathlib import Path
from xml.sax.saxutils import quoteattr
args = sys.argv[1:]
junit = args[args.index("--junit-xml") + 1]
selection = [a for a in args if "::" in a]
here = Path(__file__).parent
plan = json.loads((here / "plan.json").read_text())
calls = here / "calls.json"
seen = json.loads(calls.read_text()) if calls.exists() else []
seen.append(args)
calls.write_text(json.dumps(seen))
if selection and (here / "edit-on-rerun").exists():  # an edit landing mid-retry
    (here / "tests" / "test_x.py").write_text("def test_a():\n    assert 1\n")
cases, bad, summary = [], False, ""
for node, outcomes in plan.items():
    if selection and node not in selection:
        continue
    path, _, rest = node.partition("::")
    parts = rest.split("::")
    classname = ".".join([path[:-3].replace("/", "."), *parts[:-1]])
    count = sum(1 for call in seen if not [a for a in call if "::" in a] or node in call)
    outcome = outcomes[min(count, len(outcomes)) - 1]
    if "--always-fail" in args:  # a second environment that is simply red
        outcome = "fail"
    body = ""
    if outcome == "summary":  # a suite that died before naming its cases
        bad = True
        summary = '<testsuite name="agg" tests="1" failures="1" time="1"/>'
        continue
    if outcome == "fail":
        bad = True
        body = '<failure message="timed out after 5s">trace</failure>'
    elif outcome == "skip":
        body = "<skipped/>"
    cases.append(f"<testcase classname={quoteattr(classname)} name={quoteattr(parts[-1])}>{body}</testcase>")
Path(junit).write_text(
    '<?xml version="1.0"?><testsuites><testsuite name="s" time="1">'
    + "".join(cases) + "</testsuite>" + summary + "</testsuites>")
sys.exit(1 if bad else 0)
'''

_RUN = "python3 runner.py --junit-xml {junit_xml}"
_RERUN = "python3 runner.py --junit-xml {junit_xml} {pytest_node_ids}"


def _declared_repo(tmp_path: Path, plan: dict, state: str) -> Path:
    repo = _repo(tmp_path)
    (repo / "runner.py").write_text(_FAKE_RUNNER)
    (repo / "plan.json").write_text(json.dumps(plan))
    (repo / "tests").mkdir()
    (repo / "tests" / "test_x.py").write_text("def test_a():\n    pass\n")
    (repo / ".prawduct" / "project-state.yaml").write_text(state)
    # the runner's own bookkeeping, like any runner's cache, is not the tree
    (repo / ".gitignore").write_text("calls.json\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "runner")
    return repo


def _rerun_record(repo: Path, *flags: str):
    res = _run_in(repo, "test-evidence", "record", *flags)
    path = repo / ".prawduct" / ".test-evidence.json"
    ev = json.loads(path.read_text()) if path.is_file() else None
    return res, ev


def _calls(repo: Path) -> list[list[str]]:
    return json.loads((repo / "calls.json").read_text())


_ONE_RERUN = f"test_command: {_RUN}\ntest_rerun_command: {_RERUN}\n"
_FLAKE = "tests/test_x.py::TestPool::test_timeout"


class TestRerunFailed:
    def test_a_failure_that_passes_on_rerun_is_a_green_with_one_flake(self, tmp_path):
        repo = _declared_repo(tmp_path, {
            _FLAKE: ["fail", "pass"],
            "tests/test_x.py::test_ok": ["pass"],
        }, _ONE_RERUN)
        res, ev = _rerun_record(repo, "--rerun-failed")
        assert res.returncode == 0, res.stdout + res.stderr
        assert (ev["passed"], ev["failed"]) == (2, 0)
        assert "failed_tests" not in ev
        assert ev["flaky"] == [{
            "id": "tests.test_x.TestPool::test_timeout",
            "first_failure": "timed out after 5s",
            "attempts": 1,
            "source": "rerun",
            "file": "tests/test_x.py",
        }]
        # the rerun ran only the failure, by node id
        assert [a for a in _calls(repo)[1] if "::" in a] == [_FLAKE]
        assert "evidence_tree" in ev

    def test_an_edit_during_the_rerun_vouches_for_no_tree(self, tmp_path):
        """The retries run inside the run's tree bracket: a green assembled
        from a run on one tree and a retry on another vouches for neither."""
        repo = _declared_repo(tmp_path, {_FLAKE: ["fail", "pass"]}, _ONE_RERUN)
        (repo / "edit-on-rerun").write_text("")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "arm")
        res, ev = _rerun_record(repo, "--rerun-failed")
        assert res.returncode == 0, res.stdout + res.stderr
        assert ev["failed"] == 0 and len(ev["flaky"]) == 1
        assert "evidence_tree" not in ev
        assert "tests/test_x.py" in res.stderr

    def test_a_test_that_fails_every_attempt_stays_red(self, tmp_path):
        repo = _declared_repo(tmp_path, {_FLAKE: ["fail"]}, _ONE_RERUN)
        res, ev = _rerun_record(repo, "--rerun-failed=2")
        assert res.returncode == 1
        assert ev["failed"] == 1
        assert ev["failed_tests"] == ["tests.test_x.TestPool::test_timeout"]
        assert "flaky" not in ev
        assert len(_calls(repo)) == 3  # the run and two retries

    def test_n_retries_and_the_attempts_count_every_failure(self, tmp_path):
        repo = _declared_repo(tmp_path, {_FLAKE: ["fail", "fail", "pass"]}, _ONE_RERUN)
        res, ev = _rerun_record(repo, "--rerun-failed=3")
        assert res.returncode == 0, res.stdout + res.stderr
        assert ev["flaky"][0]["attempts"] == 2
        assert len(_calls(repo)) == 3  # stops at the pass

    def test_a_test_skipped_on_rerun_has_not_passed(self, tmp_path):
        repo = _declared_repo(tmp_path, {_FLAKE: ["fail", "skip"]}, _ONE_RERUN)
        res, ev = _rerun_record(repo, "--rerun-failed")
        assert res.returncode == 1
        assert ev["failed"] == 1
        assert "flaky" not in ev
        assert "still failing after 1 retry" in res.stderr

    def test_a_failure_with_no_test_id_is_not_retried(self, tmp_path):
        repo = _declared_repo(tmp_path, {
            _FLAKE: ["fail", "pass"], "tests/test_x.py::test_dead": ["summary"],
        }, _ONE_RERUN)
        res, ev = _rerun_record(repo, "--rerun-failed")
        assert res.returncode == 1
        assert ev["failed"] == 2
        assert len(_calls(repo)) == 1
        assert "carry no test id" in res.stderr

    def test_without_the_flag_nothing_is_retried(self, tmp_path):
        repo = _declared_repo(tmp_path, {_FLAKE: ["fail", "pass"]}, _ONE_RERUN)
        res, ev = _rerun_record(repo)
        assert res.returncode == 1
        assert ev["failed"] == 1
        assert len(_calls(repo)) == 1

    def test_too_many_failures_is_a_broken_run_and_is_not_retried(self, tmp_path):
        plan = {f"tests/test_x.py::test_{i}": ["fail", "pass"] for i in range(6)}
        repo = _declared_repo(tmp_path, plan, _ONE_RERUN)
        res, ev = _rerun_record(repo, "--rerun-failed")
        assert res.returncode == 1
        assert ev["failed"] == 6
        assert len(_calls(repo)) == 1
        assert "not retried" in res.stderr and "6 tests failed" in res.stderr

    def test_a_command_whose_template_is_none_is_not_retried_and_says_so(self, tmp_path):
        state = (
            "test_commands:\n"
            f"  - {_RUN}\n"
            "  - python3 runner.py --junit-xml {junit_xml} --always-fail\n"
            "test_rerun_commands:\n"
            f"  - {_RERUN}\n"
            "  - none\n"
        )
        repo = _declared_repo(tmp_path, {_FLAKE: ["fail", "pass"]}, state)
        res, ev = _rerun_record(repo, "--rerun-failed")
        # the first command's failure is retried and passes; the second's
        # has no template and stays red
        assert res.returncode == 1, res.stdout + res.stderr
        assert ev["failed"] == 1
        assert [e["id"] for e in ev["flaky"]] == ["tests.test_x.TestPool::test_timeout"]
        assert "no rerun template" in res.stderr

    def test_an_id_that_resolves_to_no_file_is_not_retried(self, tmp_path):
        repo = _declared_repo(tmp_path, {"tests/test_gone.py::test_t": ["fail", "pass"]}, _ONE_RERUN)
        res, ev = _rerun_record(repo, "--rerun-failed")
        assert res.returncode == 1
        assert ev["failed"] == 1
        assert len(_calls(repo)) == 1
        assert "tests.test_gone::test_t" in res.stderr

    def test_the_rerun_declaration_is_checked_before_any_suite_runs(self, tmp_path):
        bad = {
            "no placeholder": f"test_command: {_RUN}\ntest_rerun_command: python3 runner.py --junit-xml {{junit_xml}}\n",
            "no junit": f"test_command: {_RUN}\ntest_rerun_command: python3 runner.py {{pytest_node_ids}}\n",
            "misaligned": (
                f"test_commands:\n  - {_RUN}\n  - {_RUN}\n"
                f"test_rerun_commands:\n  - {_RERUN}\n"
            ),
            "wrong pairing": f"test_command: {_RUN}\ntest_rerun_commands:\n  - {_RERUN}\n",
            "wrong pairing plural": f"test_commands:\n  - {_RUN}\ntest_rerun_command: {_RERUN}\n",
            "none declared": f"test_command: {_RUN}\n",
        }
        for label, state in bad.items():
            (tmp_path / label.replace(" ", "_")).mkdir()
            repo = _declared_repo(tmp_path / label.replace(" ", "_"), {_FLAKE: ["fail", "pass"]}, state)
            res, _ = _rerun_record(repo, "--rerun-failed")
            assert res.returncode == 2, (label, res.stdout, res.stderr)
            assert not (repo / "calls.json").exists(), label
            if label.startswith("wrong pairing"):
                # the message names the pairing, not a missing template
                assert "pairs with" in res.stderr, res.stderr

    def test_the_flag_needs_a_live_run(self, tmp_path):
        repo = _repo(tmp_path)
        junit = repo / "r.xml"
        junit.write_text('<testsuites><testsuite name="s"><testcase classname="c" name="t"/></testsuite></testsuites>')
        for flags in (["--from-junit", str(junit)], ["--from-counts", "passed=1", "failed=0"], ["--no-rerun"]):
            res = _run_in(repo, "test-evidence", "record", "--rerun-failed", *flags)
            assert res.returncode == 2, (flags, res.stderr)
            assert "--rerun-failed" in res.stderr

    def test_a_bad_count_is_refused(self, tmp_path):
        repo = _repo(tmp_path)
        for flag in ("--rerun-failed=0", "--rerun-failed=6", "--rerun-failed=x"):
            res = _run_in(repo, "test-evidence", "record", flag)
            assert res.returncode == 2, (flag, res.stderr)


class TestPytestNodeIds:
    """The JUnit id is ``classname::name`` with a dotted module path; pytest
    selects by ``path.py::Class::name``. The longest dotted prefix naming a
    file in the repo is the module; the rest are classes."""

    def _resolve(self, tmp_path, classname, name, files, file_attr=None):
        import importlib.machinery
        import importlib.util
        import xml.etree.ElementTree as ET
        hook = Path(__file__).resolve().parent.parent / "plugin" / "bin" / "prawduct-hook"
        loader = importlib.machinery.SourceFileLoader("_hook_for_ids", str(hook))
        spec = importlib.util.spec_from_loader("_hook_for_ids", loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
        for f in files:
            (tmp_path / f).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / f).write_text("")
        case = ET.Element("testcase", {"classname": classname, "name": name,
                                       **({"file": file_attr} if file_attr else {})})
        return mod._pytest_node_id(case, tmp_path)

    def test_a_class_method_with_params(self, tmp_path):
        assert self._resolve(tmp_path, "tests.test_x.TestY", "test_z[a-b]", ["tests/test_x.py"]) == (
            "tests/test_x.py::TestY::test_z[a-b]", "tests/test_x.py")

    def test_a_module_level_test(self, tmp_path):
        assert self._resolve(tmp_path, "tests.test_x", "test_z", ["tests/test_x.py"]) == (
            "tests/test_x.py::test_z", "tests/test_x.py")

    def test_the_file_attribute_wins(self, tmp_path):
        assert self._resolve(tmp_path, "pkg.test_x.TestY", "t", [], file_attr="src/pkg/test_x.py") == (
            "src/pkg/test_x.py::TestY::t", "src/pkg/test_x.py")

    def test_no_file_is_no_id(self, tmp_path):
        assert self._resolve(tmp_path, "tests.test_gone", "t", ["tests/test_x.py"]) == (None, None)
        assert self._resolve(tmp_path, "", "t", []) == (None, None)


_REAL_FLAKY_TEST = '''
from pathlib import Path
import pytest

COUNTER = Path(__file__).parent.parent / "attempts.txt"


def _attempt(key):
    seen = COUNTER.read_text().splitlines() if COUNTER.exists() else []
    COUNTER.write_text("\\n".join([*seen, key]) + "\\n")
    return seen.count(key) + 1


class TestPool:
    @pytest.mark.parametrize("size", ["a-b"])
    def test_timeout(self, size):
        assert _attempt("timeout") > 1, "timed out under load"


def test_ok():
    assert True
'''


class TestAgainstRealPytest:
    """The fake runner proves the recorder's logic; this proves its reading of
    what pytest actually writes — the dotted classname, a parametrized name —
    and that the node ids it derives select the test in a real rerun."""

    def _repo(self, tmp_path: Path, state: str) -> Path:
        repo = _repo(tmp_path)
        (repo / "tests").mkdir()
        (repo / "tests" / "test_x.py").write_text(_REAL_FLAKY_TEST)
        (repo / ".gitignore").write_text("attempts.txt\n__pycache__/\n")
        if state:
            (repo / ".prawduct" / "project-state.yaml").write_text(state)
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "real")
        return repo

    def _assert_one_flake(self, repo: Path, res, ev):
        assert res.returncode == 0, res.stdout + res.stderr
        assert ev["failed"] == 0
        assert ev["flaky"] == [{
            "id": "tests.test_x.TestPool::test_timeout[a-b]",
            "first_failure": ev["flaky"][0]["first_failure"],
            "attempts": 1,
            "source": "rerun",
            "file": "tests/test_x.py",
        }]
        assert "timed out under load" in ev["flaky"][0]["first_failure"]
        # the run, then a rerun of the one test alone
        assert (repo / "attempts.txt").read_text().split() == ["timeout", "timeout"]

    def test_a_declared_pytest_command_with_a_rerun_template(self, tmp_path):
        pytest_cmd = "python3 -m pytest -p no:cacheprovider -q --junit-xml={junit_xml}"
        repo = self._repo(tmp_path, (
            f"test_command: {pytest_cmd} tests\n"
            f"test_rerun_command: {pytest_cmd} {{pytest_node_ids}}\n"
        ))
        res, ev = _rerun_record(repo, "--rerun-failed")
        self._assert_one_flake(repo, res, ev)

    def test_the_fallback_pytest_path_needs_no_template(self, tmp_path):
        repo = self._repo(tmp_path, "")
        res, ev = _rerun_record(repo, "--rerun-failed", "--", "-p", "no:cacheprovider")
        self._assert_one_flake(repo, res, ev)
