"""A record attempt that does not land must not leave the old green vouching (#679).

`test-evidence record` keeps one record per worktree and rewrites it only when a
record LANDS. Every refusal (exit 2) returned before that write, so a previous
green went on vouching for a tree whose latest run failed or never finished:
`test-status`, the Stop gate, `/prawduct:pr` and `/prawduct:critic` all read
the record through `gates.run_refusal`, and the refusal's stderr reached none
of them.

The fix is a write-ahead void: once the arguments are known good and before the
suite runs or a report is read, the standing record is rewritten as a void. A
record that lands replaces it; anything else (a refusal, a crash, Ctrl-C)
leaves it void. The void is carried in the shape every reader already refuses
(`degraded`, which `run_refusal` refuses), so no reader had to learn a new key.

Pinned at the CLI, because that is where the defect was reported: every case
asserts `test-status`, the reader, not the record's bytes alone.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "plugin"))

from test_plugin_runtime import _git, _run_in  # noqa: E402

from lib import evidence, gates  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]

_GREEN = (
    '<testsuites><testsuite name="s" time="1.0">'
    '<testcase classname="c" name="ok"/><testcase classname="c" name="ok2"/>'
    "</testsuite></testsuites>"
)

#: A stand-in for a declared test command. Its first argument picks what the
#: "run" does; the second is the `{junit_xml}` path the recorder substitutes.
_RUNNER = '''\
import shutil, sys
from pathlib import Path
mode, report = sys.argv[1], Path(sys.argv[2])
green = %r
if mode == "green":
    report.write_text(green)
elif mode == "garbage":
    report.write_text("<testsuites><not-closed")
elif mode == "empty":
    report.write_text("<testsuites/>")
elif mode == "bad-count":
    report.write_text('<testsuites><testsuite name="s" tests="x"/></testsuites>')
elif mode == "exit1-green":
    report.write_text(green)
    sys.exit(1)
elif mode == "copy-evidence":
    shutil.copy(".prawduct/.test-evidence.json", "evidence-during-run.json")
    report.write_text(green)
''' % _GREEN


def _evidence_path(repo: Path) -> Path:
    return repo / ".prawduct" / ".test-evidence.json"


def _record(repo: Path) -> dict:
    return json.loads(_evidence_path(repo).read_text())


def _declare(repo: Path, mode: str | None) -> None:
    state = repo / ".prawduct" / "project-state.yaml"
    if mode is None:
        state.write_text("project_name: void\n")
    else:
        state.write_text(
            f"test_command: {sys.executable} runner.py {mode} {{junit_xml}}\n"
        )


def _repo(tmp_path: Path, mode: str | None = None) -> Path:
    """A committed repo with a session marker older than anything recorded, so
    a green recorded here reads current by the session clause whatever later
    edits do to the tree — the control each test asserts before its subject."""
    repo = tmp_path / "repo"
    (repo / ".prawduct").mkdir(parents=True)
    (repo / "runner.py").write_text(_RUNNER)
    (repo / "test_sample.py").write_text("def test_ok():\n    assert True\n")
    _declare(repo, mode)
    _git(repo, "init", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "c1")
    (repo / ".prawduct" / ".session-start").write_text("2000-01-01T00:00:00Z")
    return repo


def _seed_green(repo: Path) -> None:
    report = repo / "green.xml"
    report.write_text(_GREEN)
    res = _run_in(repo, "test-evidence", "record", "--from-junit", str(report))
    assert res.returncode == 0, res.stderr
    assert "degraded" not in _record(repo) and "void" not in _record(repo)
    status = _run_in(repo, "test-status")
    assert status.returncode == 0, (
        "control: the seeded green must read current, or a stale verdict below "
        f"proves nothing about the void — {status.stdout}"
    )


def _assert_voided(repo: Path, res) -> None:
    assert res.returncode == 2, res.stdout + res.stderr
    status = _run_in(repo, "test-status")
    assert status.returncode == 1, (
        "a refused record attempt left the earlier green vouching: "
        f"{status.stdout}"
    )
    first = status.stdout.splitlines()[0]
    # Since #1178 the void names the recorder, so once it has exited the line
    # reads `stale (interrupted)`: refused, failed or killed, it did not land.
    assert first.startswith("stale (interrupted):") and "did not land" in first, first


class TestEveryRefusalAfterTheSuiteOrReportVoids:
    """One case per exit-2 path in `cmd_test_evidence` that is reached after
    the suite ran or a report was named — the issue's list, plus the paths a
    grep of the same shape found (a launch failure, a malformed count)."""

    @pytest.mark.parametrize("args, case", [
        (["--from-junit", "missing.xml"], "ingest: report not found"),
        (["--from-junit", "garbage.xml"], "ingest: report unparseable"),
        (["--from-junit", "partial.xml"], "ingest: scope record says partial"),
        (["--from-junit", "empty.xml"], "ingest: no <testsuite>/<testcase>"),
    ])
    def test_an_ingest_refusal_voids_the_standing_green(self, tmp_path, args, case):
        repo = _repo(tmp_path)
        (repo / "garbage.xml").write_text("<testsuites><not-closed")
        (repo / "empty.xml").write_text("<testsuites/>")
        (repo / "partial.xml").write_text(_GREEN)
        (repo / "partial.xml.scope.json").write_text(json.dumps({
            "v": 1, "scope": "partial", "report": str((repo / "partial.xml").resolve()),
            "why": "-k billing narrowed the selection",
        }))
        _seed_green(repo)
        _assert_voided(repo, _run_in(repo, "test-evidence", "record", *args))

    @pytest.mark.parametrize("mode, case", [
        ("garbage", "live run: report unparseable"),
        ("empty", "live run: no tests collected"),
        ("bad-count", "live run: malformed count attribute"),
        ("exit1-green", "live run: nonzero exit, no failing test (#912)"),
    ])
    def test_a_live_run_refusal_voids_the_standing_green(self, tmp_path, mode, case):
        repo = _repo(tmp_path, mode)
        _seed_green(repo)
        _assert_voided(repo, _run_in(repo, "test-evidence", "record"))

    def test_a_command_that_cannot_launch_voids_the_standing_green(self, tmp_path):
        repo = _repo(tmp_path)
        (repo / ".prawduct" / "project-state.yaml").write_text(
            "test_command: /nonexistent/runner {junit_xml}\n"
        )
        _seed_green(repo)
        res = _run_in(repo, "test-evidence", "record")
        assert "could not launch" in res.stderr
        _assert_voided(repo, res)

    def test_the_fallbacks_zero_pass_guard_voids_the_standing_green(self, tmp_path):
        repo = _repo(tmp_path)
        (repo / "test_sample.py").write_text("def test_bad():\n    assert False\n")
        _seed_green(repo)
        res = _run_in(repo, "test-evidence", "record")
        assert "zero passes" in res.stderr
        _assert_voided(repo, res)

    def test_a_narrowed_fallback_run_voids_the_standing_green(self, tmp_path):
        repo = _repo(tmp_path)
        shutil.copy(REPO_ROOT / "tests" / "conftest.py", repo / "conftest.py")
        _seed_green(repo)
        res = _run_in(repo, "test-evidence", "record", "-k", "test_ok")
        assert "did not cover the whole suite" in res.stderr
        _assert_voided(repo, res)


class TestTheVoidIsWrittenAhead:
    def test_a_running_suite_already_sees_the_void(self, tmp_path):
        """Stands in for a run killed before it records (Ctrl-C on a hung
        suite), which no refusal path reaches: the void must be on disk BEFORE
        the command starts, not written on the way out."""
        repo = _repo(tmp_path, "copy-evidence")
        _seed_green(repo)
        res = _run_in(repo, "test-evidence", "record")
        assert res.returncode == 0, res.stderr
        during = json.loads((repo / "evidence-during-run.json").read_text())
        assert during.get("void"), during
        assert gates.run_refusal(during), "the in-flight record must not vouch"
        assert "evidence_tree" not in during, (
            "a void that kept its tree would still answer the tree question"
        )

    def test_the_void_keeps_the_prior_counts_and_names_the_attempt(self, tmp_path):
        repo = _repo(tmp_path)
        _seed_green(repo)
        prior = _record(repo)
        _run_in(repo, "test-evidence", "record", "--from-junit", "missing.xml")
        after = _record(repo)
        for key in ("passed", "failed", "skipped", "command"):
            assert after[key] == prior[key], key
        assert "--from-junit missing.xml" in after["void"]
        assert prior["timestamp"] in after["degraded"], (
            "the reason must say which run the kept counts came from"
        )
        assert after["timestamp"] >= prior["timestamp"]
        ok, why = gates._validate_evidence_schema(after)
        assert ok, why

    def test_a_record_that_lands_after_a_void_clears_it(self, tmp_path):
        repo = _repo(tmp_path)
        _seed_green(repo)
        _run_in(repo, "test-evidence", "record", "--from-junit", "missing.xml")
        assert _run_in(repo, "test-status").returncode == 1
        report = repo / "again.xml"
        report.write_text(_GREEN)
        res = _run_in(repo, "test-evidence", "record", "--from-junit", str(report))
        assert res.returncode == 0, res.stderr
        landed = _record(repo)
        assert "void" not in landed and "degraded" not in landed
        assert _run_in(repo, "test-status").returncode == 0

    def test_no_record_on_disk_stays_no_record(self, tmp_path):
        repo = _repo(tmp_path)
        res = _run_in(repo, "test-evidence", "record", "--from-junit", "missing.xml")
        assert res.returncode == 2
        assert not _evidence_path(repo).exists()


class TestWhatDoesNotVoid:
    @pytest.mark.parametrize("args, mode, case", [
        (["--from-junit", "green.xml", "--from-counts", "passed=1", "failed=0"],
         None, "mutually exclusive sources"),
        (["--from-counts", "passed=1", "failed=0"], "green",
         "--from-counts with a declared command"),
        (["-k", "x"], "green", "extra args with a declared command"),
        (["--degraded"], None, "a flag missing its value"),
    ])
    def test_a_usage_error_leaves_the_green_byte_identical(self, tmp_path, args, mode, case):
        repo = _repo(tmp_path, mode)
        _seed_green(repo)
        before = _evidence_path(repo).read_bytes()
        res = _run_in(repo, "test-evidence", "record", *args)
        assert res.returncode == 2, (case, res.stdout, res.stderr)
        assert _evidence_path(repo).read_bytes() == before, case

    def test_a_restamp_of_a_void_record_refuses_and_writes_nothing(self, tmp_path):
        """A restamp reuses the record's counts and stamps the current tree, so
        allowing it would launder the void into fresh-looking evidence."""
        repo = _repo(tmp_path)
        _seed_green(repo)
        _run_in(repo, "test-evidence", "record", "--from-junit", "missing.xml")
        before = _evidence_path(repo).read_bytes()
        res = _run_in(repo, "test-evidence", "record", "--no-rerun")
        assert res.returncode == 2, res.stdout + res.stderr
        assert "did not complete" in res.stderr
        assert _evidence_path(repo).read_bytes() == before

    def test_a_restamp_of_a_green_record_still_works(self, tmp_path):
        """The control for the refusal above."""
        repo = _repo(tmp_path)
        _seed_green(repo)
        res = _run_in(repo, "test-evidence", "record", "--no-rerun")
        assert res.returncode == 0, res.stderr


class TestTheStoreCannotAnswerForAVoidRecord:
    def test_a_green_fact_for_this_tree_does_not_make_a_void_record_current(self, tmp_path):
        """A green run on this exact tree from another worktree is a `test-run`
        fact the store fallback consults. The void is this worktree's newest
        word, so it must deny rather than let the fact vouch."""
        repo = _repo(tmp_path)
        _seed_green(repo)
        tree = evidence.capture_tree(repo)["tree"]
        appended = evidence.append_test_run(repo, {
            "tree": tree, "passed": 5, "failed": 0, "skipped": 0,
            "duration_seconds": 1.0, "source": "run",
        })
        assert appended.get("status") == "appended", appended
        # Control: with no local record at all the fact vouches, so a stale
        # verdict below is the void denying, not a fact that never matched.
        saved = _evidence_path(repo).read_bytes()
        _evidence_path(repo).unlink()
        assert _run_in(repo, "test-status").returncode == 0
        _evidence_path(repo).write_bytes(saved)

        _assert_voided(repo, _run_in(repo, "test-evidence", "record", "--from-junit", "missing.xml"))

    def test_run_refusal_refuses_a_void_record(self):
        assert gates.run_refusal({"failed": 0, "degraded": "x"})
