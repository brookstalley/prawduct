"""The scope record, end to end — producer, reader, and the CLI refusal.

The contract is `plugin/docs/test-report-contract.md`. Three layers are pinned
here, deliberately at different fidelities:

* **the reader** (`lib/report_scope.py`) against hand-written records, one per
  rule, because the rules are what it exists to apply;
* **the CLI** (`test-evidence record --from-junit`), because that is the layer
  a defect would be reported at and a lib-level pass proves nothing about the
  wiring — with a no-record control, so a refusal cannot be a fixture that
  never reached the subject;
* **the producer** (`tests/conftest.py`) both as a branch matrix over fake
  pytest configs and, once, under REAL pytest against a copy of the file
  itself — a fake config can only encode what I believe pytest passes, and the
  copy is the artifact rather than a replica that can drift from it.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugin"
HOOK = PLUGIN_ROOT / "bin" / "prawduct-hook"

sys.path.insert(0, str(PLUGIN_ROOT))

from lib import report_scope  # noqa: E402

from conftest import (  # noqa: E402
    FULL,
    PARTIAL,
    SCOPE_RECORD_SUFFIX,
    classify_invocation,
    write_scope_record,
)


# =============================================================================
# The reader — one case per rule in the contract's table
# =============================================================================


def _record_beside(report_path: Path, **fields) -> Path:
    """Write a scope record beside `report_path`, defaulting to a valid `full`
    one so each test states only the field it is about."""
    payload = {"v": 1, "scope": FULL, "report": str(report_path),
               "at": "2026-09-18T05:00:00Z"}
    payload.update(fields)
    path = report_scope.record_path(report_path)
    path.write_text(json.dumps({k: v for k, v in payload.items() if v is not None}) + "\n")
    return path


@pytest.fixture
def report(tmp_path) -> Path:
    path = tmp_path / ".test-report.xml"
    path.write_text("<testsuites/>\n")
    return path


class TestTheReader:
    def test_no_record_proceeds(self, report):
        # The permissive case, and the reason it is permissive: every repo that
        # has not wired a producer looks exactly like this.
        assert report_scope.read_scope_record(report) == (True, None, None)

    def test_a_full_record_proceeds(self, report):
        _record_beside(report)
        assert report_scope.read_scope_record(report) == (True, None, None)

    def test_a_partial_record_refuses_and_quotes_its_own_reason(self, report):
        _record_beside(report, scope=PARTIAL, why="-k 'billing' narrowed the selection")
        ok, reason, cause = report_scope.read_scope_record(report)
        assert ok is False
        assert cause == report_scope.CAUSE_NARROWED
        assert "billing" in reason, "the refusal must say what narrowed the run"
        assert "2026-09-18T05:00:00Z" in reason, "and when the record was written"

    def test_a_partial_record_with_no_reason_still_refuses(self, report):
        _record_beside(report, scope=PARTIAL, why=None)
        ok, reason, cause = report_scope.read_scope_record(report)
        assert ok is False
        assert "no reason recorded" in reason

    def test_malformed_json_refuses(self, report):
        report_scope.record_path(report).write_text("{not json")
        ok, reason, cause = report_scope.read_scope_record(report)
        assert ok is False and "not valid JSON" in reason
        assert cause == report_scope.CAUSE_MALFORMED

    def test_a_non_object_record_refuses(self, report):
        report_scope.record_path(report).write_text("[]")
        ok, reason, cause = report_scope.read_scope_record(report)
        assert ok is False and "not a JSON object" in reason
        assert cause == report_scope.CAUSE_MALFORMED

    def test_an_unreadable_record_refuses(self, report):
        # A directory at the record's path: the OSError branch, which would
        # otherwise traceback out of a command whose errors are return values.
        report_scope.record_path(report).mkdir()
        ok, reason, cause = report_scope.read_scope_record(report)
        assert ok is False and "could not be read" in reason
        assert cause == report_scope.CAUSE_UNREADABLE

    @pytest.mark.parametrize("version", [2, "1", None, 0])
    def test_an_unknown_schema_version_refuses(self, report, version):
        _record_beside(report, v=version)
        ok, reason, cause = report_scope.read_scope_record(report)
        assert ok is False
        assert "schema version" in reason and repr(version) in reason
        assert cause == report_scope.CAUSE_SCHEMA

    @pytest.mark.parametrize("scope", ["complete", "", None, "FULL"])
    def test_an_unknown_scope_value_refuses(self, report, scope):
        _record_beside(report, scope=scope)
        ok, reason, cause = report_scope.read_scope_record(report)
        assert ok is False and "scope=" in reason
        assert cause == report_scope.CAUSE_SCOPE

    def test_a_record_naming_another_report_refuses(self, report):
        # A copied or moved report does not inherit the record's authority.
        _record_beside(report, report=str(report.parent / "somewhere-else.xml"))
        ok, reason, cause = report_scope.read_scope_record(report)
        assert ok is False and "some other run" in reason
        assert cause == report_scope.CAUSE_MISMATCH

    def test_a_record_with_no_report_field_refuses(self, report):
        _record_beside(report, report=None)
        ok, reason, cause = report_scope.read_scope_record(report)
        assert ok is False and "does not name the report" in reason
        assert cause == report_scope.CAUSE_MALFORMED, (
            "a record naming NO report is malformed, not a record about another "
            "run — the mismatch remedy ('fetch the report without its record') "
            "is nonsense advice for a record that was never written correctly"
        )

    def test_a_report_path_that_cannot_be_resolved_refuses_rather_than_raising(self, report):
        """`Path("\\x00").resolve()` raises ValueError, and this module's
        contract is that errors come back as values — a traceback out of
        `test-evidence record` is not a refusal, it is a crash."""
        _record_beside(report, report="\x00")
        ok, reason, cause = report_scope.read_scope_record(report)
        assert ok is False
        assert cause == report_scope.CAUSE_MALFORMED, (
            "an unresolvable report path is malformed content, not a record "
            "about another run — the same reasoning the no-`report`-field "
            "sibling above states, and the mismatch remedy ('fetch the report "
            "without its record') is nonsense for both"
        )
        assert "cannot be" in reason

    def test_unknown_keys_are_tolerated(self, report):
        # Additive-first (`artifacts/api-contract.md` § Direction): a v1 reader
        # must not refuse a record that grew a field it does not know.
        _record_beside(report, selected=417, runner="dotnet test")
        assert report_scope.read_scope_record(report) == (True, None, None)

    def test_the_record_path_is_the_reports_path_plus_the_suffix(self, tmp_path):
        assert report_scope.record_path(tmp_path / "r.xml") == tmp_path / ("r.xml" + SCOPE_RECORD_SUFFIX)


# =============================================================================
# The CLI — the layer the defect would be reported at
# =============================================================================


def _run_hook(repo: Path, *args: str, **env_extra: str) -> subprocess.CompletedProcess:
    """Run the hook against `repo` with a pinned environment.

    `env_extra` exists for `TMPDIR`: a test that asserts on the recorder's temp
    files has to look where the SUBPROCESS put them, and the subprocess does not
    inherit this process's `TMPDIR` — the first version of the cleanup test
    globbed this process's temp dir, found nothing either way, and passed with
    the cleanup deleted.
    """
    home = repo.parent / "_home"
    home.mkdir(exist_ok=True)
    return subprocess.run(
        [sys.executable, str(HOOK), *args],
        capture_output=True, text=True, timeout=90,
        env={"HOME": str(home), "CLAUDE_PROJECT_DIR": str(repo),
             "CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT),
             "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
             "PYTHONDONTWRITEBYTECODE": "1", **env_extra},
    )


@pytest.fixture
def repo_with_report(tmp_path) -> tuple[Path, Path]:
    """A git repo carrying prior GREEN evidence and a fresh report to ingest.

    The prior record matters: the refusal's whole point is that it writes
    nothing, so the test needs something that would be overwritten.
    """
    repo = tmp_path / "repo"
    (repo / ".prawduct").mkdir(parents=True)
    (repo / "test_sample.py").write_text("def test_ok():\n    assert True\n")
    for cmd in (("init", "-b", "main"), ("add", "-A"), ("-c", "user.email=t@t",
                "-c", "user.name=t", "commit", "-m", "c1")):
        subprocess.run(["git", *cmd], cwd=repo, capture_output=True, check=True)
    (repo / ".prawduct" / ".test-evidence.json").write_text(json.dumps({
        "timestamp": "2026-09-17T00:00:00Z", "command": "pytest", "passed": 9,
        "failed": 0, "skipped": 0, "duration_seconds": 1,
        "verifier": "pytest", "coverage_level": "referenced",
        "tests_executed": [], "changes_referenced": [], "changes_unjudged": [],
    }, indent=2) + "\n")
    report = repo / "report.xml"
    report.write_text(
        '<testsuites><testsuite name="pytest" tests="2" failures="0" errors="0" '
        'skipped="0" time="1.0"><testcase name="a"/><testcase name="b"/>'
        "</testsuite></testsuites>\n"
    )
    return repo, report


class TestTheCliRefusal:
    @staticmethod
    def _evidence(repo: Path) -> str:
        return (repo / ".prawduct" / ".test-evidence.json").read_text()

    def test_a_report_with_no_record_is_ingested(self, repo_with_report):
        """The control. Without it a refusal below could be a fixture that never
        reached the subject, which reads identically to a working guard."""
        repo, report = repo_with_report
        res = _run_hook(repo, "test-evidence", "record", "--from-junit", str(report))
        assert res.returncode == 0, res.stderr
        assert json.loads(self._evidence(repo))["passed"] == 2

    def test_a_full_record_is_ingested(self, repo_with_report):
        repo, report = repo_with_report
        _record_beside(report)
        res = _run_hook(repo, "test-evidence", "record", "--from-junit", str(report))
        assert res.returncode == 0, res.stderr
        assert json.loads(self._evidence(repo))["passed"] == 2

    def test_a_partial_record_refuses_and_leaves_the_prior_record_alone(self, repo_with_report):
        repo, report = repo_with_report
        before = self._evidence(repo)
        _record_beside(report, scope=PARTIAL, why="-k 'billing' narrowed the selection")

        res = _run_hook(repo, "test-evidence", "record", "--from-junit", str(report))

        assert res.returncode == 2, res.stdout + res.stderr
        assert "billing" in res.stderr
        # Refusing rather than recording something degraded is the whole design:
        # a partial ingest would overwrite a green record with counts covering
        # less than they appear to.
        assert self._evidence(repo) == before

    def test_the_refusal_names_a_remedy_that_reaches_the_state(self, repo_with_report):
        repo, report = repo_with_report
        _record_beside(report, scope=PARTIAL, why="-x can stop the run early")
        res = _run_hook(repo, "test-evidence", "record", "--from-junit", str(report))
        assert "prawduct-hook test-evidence record" in res.stderr
        # And says the cheap way past it is not one of the ways.
        assert "deleting" in res.stderr.lower()

    def test_one_bad_record_refuses_the_whole_multi_report_ingest(self, repo_with_report):
        """No partial evidence: a `test_commands` product ingesting several
        reports must not record the good ones and drop the narrowed one."""
        repo, report = repo_with_report
        second = repo / "report2.xml"
        second.write_text(report.read_text())
        before = self._evidence(repo)
        _record_beside(second, scope=PARTIAL, why="-m 'smoke' narrowed the selection")

        res = _run_hook(repo, "test-evidence", "record",
                        "--from-junit", str(report), "--from-junit", str(second))

        assert res.returncode == 2, res.stdout + res.stderr
        assert self._evidence(repo) == before


class TestTheRefusalSpeaksForItsOwnCause:
    """Six conditions refuse, and they do not share a remedy.

    The first version printed the `partial` advice for all of them, which told
    an operator holding a CI report+record pair that deleting the record "buys
    a record that says the suite passed when part of it never ran" — true of a
    narrowed run, false of theirs, and it crowds out the remedy the contract
    actually gives for that case. Each cause is asserted on the message it
    gets AND on the message it must not get.
    """

    def test_a_mismatched_record_is_not_told_that_deleting_it_is_laundering(self, repo_with_report):
        repo, report = repo_with_report
        _record_beside(report, report=str(report.parent / "produced-on-ci.xml"))
        res = _run_hook(repo, "test-evidence", "record", "--from-junit", str(report))
        assert res.returncode == 2, res.stdout + res.stderr
        assert "different run" in res.stderr
        assert "WITHOUT its record" in res.stderr, (
            "the mismatched case must name the contract's own remedy — fetch the "
            "report alone, which lands in the permissive absent case"
        )
        assert "says the suite passed when part of it never ran" not in res.stderr

    def test_an_unreadable_record_is_not_told_to_find_an_unnarrowed_report(self, repo_with_report):
        repo, report = repo_with_report
        report_scope.record_path(report).write_text("{not json")
        res = _run_hook(repo, "test-evidence", "record", "--from-junit", str(report))
        assert res.returncode == 2, res.stdout + res.stderr
        assert "Fix the producer" in res.stderr
        assert "was not narrowed" not in res.stderr, (
            "a malformed record says nothing about narrowing, so advice about "
            "finding an un-narrowed report answers a question nobody asked"
        )
        # It still refuses the cheap way out, for a different reason than the
        # narrowed case does: unknown scope is not known-good scope.
        assert "not a way forward" in res.stderr

    def test_the_narrowed_case_keeps_the_clause_that_was_written_for_it(self, repo_with_report):
        repo, report = repo_with_report
        _record_beside(report, scope=PARTIAL, why="-k 'billing' narrowed the selection")
        res = _run_hook(repo, "test-evidence", "record", "--from-junit", str(report))
        assert "says the suite passed when part of it never ran" in res.stderr


class TestTheUndeclaredRunPath:
    """The record is consulted on ingest because a DECLARED command is the
    definition of the suite — and extra args are refused there. The interpreter
    fallback has no declaration and appends the operator's args verbatim, so
    `record -k billing` would run a subset and record it as the suite's.
    """

    @pytest.fixture
    def undeclared_repo(self, tmp_path) -> Path:
        repo = tmp_path / "undeclared"
        (repo / ".prawduct").mkdir(parents=True)
        shutil.copy(REPO_ROOT / "tests" / "conftest.py", repo / "conftest.py")
        (repo / "test_two.py").write_text(
            "def test_a():\n    assert True\n\n\ndef test_b():\n    assert True\n"
        )
        # No `test_command:` — this is the interpreter-fallback state, which the
        # template ships as the default.
        (repo / ".prawduct" / "project-state.yaml").write_text("project_name: undeclared\n")
        for cmd in (("init", "-b", "main"), ("add", "-A"), ("-c", "user.email=t@t",
                    "-c", "user.name=t", "commit", "-m", "c1")):
            subprocess.run(["git", *cmd], cwd=repo, capture_output=True, check=True)
        return repo

    def test_a_full_fallback_run_records(self, undeclared_repo):
        """The control. Without it the refusal below could be any failure of the
        fallback path rather than the guard doing its job."""
        res = _run_hook(undeclared_repo, "test-evidence", "record")
        assert res.returncode == 0, res.stdout + res.stderr
        evidence = json.loads(
            (undeclared_repo / ".prawduct" / ".test-evidence.json").read_text()
        )
        assert evidence["passed"] == 2

    def test_a_narrowed_fallback_run_is_refused(self, undeclared_repo):
        res = _run_hook(undeclared_repo, "test-evidence", "record", "-k", "test_a")
        assert res.returncode == 2, res.stdout + res.stderr
        assert "did not cover the whole suite" in res.stderr
        assert not (undeclared_repo / ".prawduct" / ".test-evidence.json").exists(), (
            "a refused run must write no evidence at all"
        )


#: A minimal producer-wired runner: emits the JUnit report the recorder asked
#: for, and the scope record the contract says rides beside it.
_FAKE_RUNNER = (
    "import json, sys\n"
    "from pathlib import Path\n"
    "report = Path(sys.argv[1])\n"
    "report.write_text('<testsuites><testsuite name=\"t\" tests=\"1\" "
    "failures=\"0\" errors=\"0\" skipped=\"0\" time=\"0.1\">"
    "<testcase name=\"a\"/></testsuite></testsuites>')\n"
    "record = report.with_name(report.name + '.scope.json')\n"
    "record.write_text(json.dumps({'v': 1, 'scope': 'full', "
    "'report': str(report.resolve()), 'at': '2026-09-18T05:00:00Z'}))\n"
)


class TestTheRunPathCleansUpAfterItself:
    """The recorder's temp report gets a scope record beside it, because the
    product's runner writes one wherever the report lands. Nothing paired the
    producer's write location with the recorder's delete location until this.
    """

    def test_the_temp_scope_record_does_not_survive_a_recorded_run(self, tmp_path):
        repo = tmp_path / "declared"
        (repo / ".prawduct").mkdir(parents=True)
        # A stand-in runner: writes a JUnit report AND a scope record beside it,
        # exactly as a producer-wired repo's real runner would.
        (repo / "fake_runner.py").write_text(_FAKE_RUNNER)
        (repo / ".prawduct" / "project-state.yaml").write_text(
            f"test_command: {sys.executable} {repo / 'fake_runner.py'} {{junit_xml}}\n"
        )
        for cmd in (("init", "-b", "main"), ("add", "-A"), ("-c", "user.email=t@t",
                    "-c", "user.name=t", "commit", "-m", "c1")):
            subprocess.run(["git", *cmd], cwd=repo, capture_output=True, check=True)

        tmpdir = tmp_path / "hooktmp"
        tmpdir.mkdir()
        res = _run_hook(repo, "test-evidence", "record", TMPDIR=str(tmpdir))
        assert res.returncode == 0, res.stdout + res.stderr

        left = sorted(tmpdir.glob("prawduct-junit-*"))
        assert not left, f"the recorded run left temp files behind: {left}"

    def test_the_stand_in_runner_really_does_write_both_files(self, tmp_path):
        """The positive control for the test above. Its subject is an ABSENCE,
        and an absence is what a fixture that never reached the subject also
        produces — so the runner is driven once on its own and both files are
        asserted present."""
        report = tmp_path / "r.xml"
        runner = tmp_path / "fake_runner.py"
        runner.write_text(_FAKE_RUNNER)
        subprocess.run([sys.executable, str(runner), str(report)], check=True)
        assert report.is_file()
        assert report_scope.record_path(report).is_file()


# =============================================================================
# The producer — the classifier's branches, over fake pytest configs
# =============================================================================


class _Option:
    """Only the attributes `classify_invocation` reads; each default is the
    value real pytest passes for an un-narrowed run (verified in the plan's
    § Verify-api probe)."""

    def __init__(self, **overrides):
        self.keyword = ""
        self.markexpr = ""
        self.deselect = None
        self.ignore = None
        self.ignore_glob = None
        self.lf = False
        self.stepwise = False
        self.collectonly = False
        self.maxfail = None
        self.xmlpath = None
        self.__dict__.update(overrides)


class _Config:
    def __init__(self, rootpath: Path, args=("tests",), testpaths=("tests",), **opts):
        self.rootpath = rootpath
        self.args = list(args)
        self.option = _Option(**opts)
        self._testpaths = list(testpaths)
        self.invocation_params = type("_P", (), {"dir": rootpath})()

    def getini(self, name):
        assert name == "testpaths", f"unexpected ini read: {name}"
        return self._testpaths


class TestTheClassifier:
    def test_the_default_invocation_is_full(self, tmp_path):
        assert classify_invocation(_Config(tmp_path), 0) == (FULL, None)

    def test_a_red_but_complete_run_is_still_full(self, tmp_path):
        # Exit 1 is "tests failed", which is a complete run — record-on-red
        # depends on this not being read as truncation.
        assert classify_invocation(_Config(tmp_path), 1) == (FULL, None)

    def test_the_declared_commands_trailing_slash_is_the_same_selection(self, tmp_path):
        # `pytest tests/` vs `testpaths = tests` — the same set, two spellings.
        # This repo's own declared command takes this path.
        assert classify_invocation(_Config(tmp_path, args=("tests/",)), 0) == (FULL, None)

    @pytest.mark.parametrize(
        "opts, expected_in_why",
        [
            ({"keyword": "billing"}, "-k"),
            ({"markexpr": "smoke"}, "-m"),
            ({"deselect": ["tests/test_a.py::test_b"]}, "--deselect"),
            ({"ignore": ["tests/slow"]}, "--ignore"),
            ({"ignore_glob": ["tests/slow*"]}, "--ignore"),
            ({"lf": True}, "--lf"),
            ({"stepwise": True}, "--lf"),
            ({"collectonly": True}, "--collect-only"),
            ({"maxfail": 1}, "--maxfail"),
        ],
    )
    def test_each_narrowing_option_is_partial(self, tmp_path, opts, expected_in_why):
        scope, why = classify_invocation(_Config(tmp_path, **opts), 0)
        assert scope == PARTIAL
        assert expected_in_why in why

    @pytest.mark.parametrize("args", [
        ("tests/test_a.py",),
        ("tests/test_a.py::test_b",),
        ("tests", "extra"),
        (),
    ])
    def test_a_changed_selection_is_partial(self, tmp_path, args):
        scope, why = classify_invocation(_Config(tmp_path, args=args), 0)
        assert scope == PARTIAL, f"{args} should not read as the default selection"
        assert why

    @pytest.mark.parametrize("exitstatus", [2, 3, 4, 5])
    def test_an_incomplete_exit_status_is_partial(self, tmp_path, exitstatus):
        scope, why = classify_invocation(_Config(tmp_path), exitstatus)
        assert scope == PARTIAL
        assert str(exitstatus) in why

    def test_failed_first_alone_is_not_narrowing(self, tmp_path):
        # `--ff` reorders the selection without reducing it. Pinned because the
        # obvious grouping ("the last-failed family") would wrongly refuse it.
        assert classify_invocation(_Config(tmp_path, failedfirst=True), 0) == (FULL, None)

    def test_no_testpaths_configured_reads_the_bare_run_as_full(self, tmp_path):
        config = _Config(tmp_path, args=(str(tmp_path),), testpaths=())
        assert classify_invocation(config, 0) == (FULL, None)


class TestTheWriter:
    def test_nothing_is_written_without_a_report_to_describe(self, tmp_path):
        assert write_scope_record(_Config(tmp_path), FULL, None) is None

    def test_an_xdist_worker_writes_nothing(self, tmp_path):
        """Workers share the controller's options and write no report of their
        own; five of them racing on one path is what this guard prevents."""
        config = _Config(tmp_path, xmlpath=str(tmp_path / "r.xml"))
        config.workerinput = {"workerid": "gw0"}
        assert write_scope_record(config, FULL, None) is None
        assert not list(tmp_path.glob("*.scope.json"))

    def test_the_record_it_writes_is_one_the_reader_accepts(self, tmp_path):
        """Producer and reader pinned against each other rather than each
        against my belief about the format."""
        report = tmp_path / "r.xml"
        config = _Config(tmp_path, xmlpath=str(report))
        written = write_scope_record(config, FULL, None)
        assert written == report_scope.record_path(report)
        assert report_scope.read_scope_record(report) == (True, None, None)

    def test_a_partial_record_it_writes_is_one_the_reader_refuses(self, tmp_path):
        report = tmp_path / "r.xml"
        write_scope_record(_Config(tmp_path, xmlpath=str(report)), PARTIAL, "because")
        ok, reason, cause = report_scope.read_scope_record(report)
        assert ok is False and "because" in reason

    def test_a_write_that_fails_degrades_to_absence_and_says_so(self, tmp_path, capsys):
        """Both halves, because the contract now demands both of every producer.

        A record that cannot be written must not take the SUITE down with it —
        this describes the run, it is not part of it — and it must not fail
        SILENTLY either, because absence is the permissive case, so a producer
        that quietly stops writing turns the guard off and nothing anywhere
        notices. The obligation is on every producer author
        (`docs/test-report-contract.md` § What a producer owes), and the
        framework's own worked example is where it has to hold first.

        The failure is forced structurally rather than with a chmod: the
        record's parent is a regular FILE, so `mkdir` raises `FileExistsError`
        — deterministic, and it works for root, who can write anywhere.
        """
        blocked = tmp_path / "blocked"
        blocked.write_text("a file where the record's directory should be\n")
        report = blocked / "r.xml"

        written = write_scope_record(_Config(tmp_path, xmlpath=str(report)), FULL, None)

        assert written is None, "a failed write must return None, not raise"
        err = capsys.readouterr().err
        assert "could not write the test-report scope record" in err
        assert "trusted rather than checked" in err, (
            "the NOTE must name the CONSEQUENCE — that an ingest of this report "
            "is now trusted rather than checked — not merely report an errno"
        )

    def test_the_record_lands_beside_a_report_in_a_directory_that_does_not_exist_yet(self, tmp_path):
        # pytest creates the report's directory when it writes; the record is
        # written FIRST, at configure time, so it cannot rely on that.
        report = tmp_path / ".prawduct" / ".test-report.xml"
        written = write_scope_record(_Config(tmp_path, xmlpath=str(report)), PARTIAL, "x")
        assert written.is_file()


#: The path the contract fixes. Written here once, and every surface that has to
#: carry it is checked against THIS spelling rather than against each other
#: pairwise — five copies with no single reader is how a convention becomes four
#: conventions.
CONVENTIONAL_REPORT = ".prawduct/.test-report.xml"


def test_this_repos_runner_emits_the_report_from_every_run():
    """Property 1, for this repo, asserted where it is configured.

    Nothing else fails if the flag is dropped from `addopts`: the suite stays
    green, every test above still passes, and the only symptom is that a
    hand-run stops being recoverable — months later, to whoever next runs the
    suite by hand. That is precisely the class this file exists for.
    """
    pyproject = (REPO_ROOT / "pyproject.toml").read_text()
    assert f'"--junit-xml={CONVENTIONAL_REPORT}"' in pyproject, (
        "pyproject.toml's pytest addopts no longer carry the conventional "
        "--junit-xml path, so a run outside the recorder leaves nothing to ingest"
    )


def test_the_conventional_path_is_spelled_the_same_on_every_surface():
    """Four carriers, one spelling. A typo in any of them is silent: the
    ignore rules stop covering the file, or the boundary stops clearing it,
    and nothing goes red."""
    from lib import core

    record = CONVENTIONAL_REPORT + SCOPE_RECORD_SUFFIX
    assert {CONVENTIONAL_REPORT, record} <= set(core.GITIGNORE_ENTRIES), (
        "the managed .gitignore contract no longer covers both files"
    )
    hook_source = (PLUGIN_ROOT / "bin" / "prawduct-hook").read_text()
    for path in (CONVENTIONAL_REPORT, record):
        assert f'"{path}"' in hook_source, f"the hook's untrack set is missing {path}"
        # The boundary deletes them by bare filename, under `.prawduct/`.
        assert f'"{path.split("/")[-1]}"' in hook_source, (
            f"the session boundary no longer clears {path}"
        )
    contract = (PLUGIN_ROOT / "docs" / "test-report-contract.md").read_text()
    assert CONVENTIONAL_REPORT in contract and record in contract, (
        "the contract doc no longer publishes the paths it fixes"
    )


def test_the_two_surfaces_spell_the_vocabulary_the_same_way():
    """`tests/conftest.py` states the verdict values literally so the file can
    be copied into a repo with no `plugin/` beside it. That is only safe while
    the two spellings agree, and nothing but this asserts it."""
    assert (FULL, PARTIAL) == (report_scope.FULL, report_scope.PARTIAL)
    assert SCOPE_RECORD_SUFFIX == report_scope.RECORD_SUFFIX


# =============================================================================
# The producer under real pytest — the wiring, not the logic
# =============================================================================


class TestUnderRealPytest:
    """A fake config asserts what I believe pytest passes. This asserts what it
    does — and, because the scratch project runs a COPY of `tests/conftest.py`
    rather than a replica, it is the only check that the hooks are wired at all.
    """

    @pytest.fixture
    def scratch(self, tmp_path) -> Path:
        project = tmp_path / "scratch"
        (project / "tests").mkdir(parents=True)
        shutil.copy(REPO_ROOT / "tests" / "conftest.py", project / "conftest.py")
        (project / "tests" / "test_x.py").write_text(
            "def test_a():\n    assert True\n\n\ndef test_b():\n    assert True\n"
        )
        (project / "pytest.ini").write_text(
            "[pytest]\ntestpaths = tests\naddopts = --junit-xml=report.xml\n"
        )
        return project

    @staticmethod
    def _run(project: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *args],
            cwd=project, capture_output=True, text=True, timeout=180,
        )

    def test_a_plain_run_leaves_a_report_and_a_full_record(self, scratch):
        res = self._run(scratch)
        assert res.returncode == 0, res.stdout + res.stderr
        report = scratch / "report.xml"
        assert report.is_file(), "addopts alone must produce the report"
        record = json.loads(report_scope.record_path(report).read_text())
        assert record["scope"] == FULL
        assert Path(record["report"]) == report.resolve()
        # The reader is what this is for.
        assert report_scope.read_scope_record(report) == (True, None, None)

    def test_a_narrowed_run_leaves_a_record_the_reader_refuses(self, scratch):
        res = self._run(scratch, "-k", "test_a")
        assert res.returncode == 0, res.stdout + res.stderr
        report = scratch / "report.xml"
        ok, reason, cause = report_scope.read_scope_record(report)
        assert ok is False, "a -k run must not read as suite evidence"
        assert "test_a" in reason

    def test_a_run_from_a_SUBDIRECTORY_still_writes_under_the_project_root(self, scratch):
        """pytest resolves `--junit-xml` against the invocation directory, so
        without the anchoring in `pytest_configure` this run would leave
        `tests/.prawduct/` — untracked output that the managed ignore patterns
        do not match (a pattern with a slash anchors to the repo root) and the
        session boundary does not clear, one `git add -A` from being committed.
        """
        (scratch / "pytest.ini").write_text(
            "[pytest]\ntestpaths = tests\naddopts = --junit-xml=.prawduct/.test-report.xml\n"
        )
        res = subprocess.run(
            [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q"],
            cwd=scratch / "tests", capture_output=True, text=True, timeout=180,
        )
        assert res.returncode == 0, res.stdout + res.stderr
        assert (scratch / ".prawduct" / ".test-report.xml").is_file()
        assert not (scratch / "tests" / ".prawduct").exists(), (
            "the report landed under the invocation directory, not the project root"
        )
        # And the record beside it still describes the report it sits beside.
        assert report_scope.read_scope_record(
            scratch / ".prawduct" / ".test-report.xml"
        ) == (True, None, None)

    def test_a_run_that_writes_no_report_writes_no_record(self, tmp_path):
        """No `--junit-xml` anywhere, so there is nothing to describe. A record
        written anyway would describe a report that is not there, and the next
        run that DID produce one would inherit it.

        The project is its own root — deliberately not a subdirectory of the
        scratch fixture, because pytest walks upward for an ini file and would
        inherit its `addopts`, which is how the first draft of this test passed
        a report to a run that was supposed to have none."""
        bare = tmp_path / "bare"
        bare.mkdir()
        shutil.copy(REPO_ROOT / "tests" / "conftest.py", bare / "conftest.py")
        (bare / "pytest.ini").write_text("[pytest]\n")
        (bare / "test_y.py").write_text("def test_c():\n    assert True\n")
        res = subprocess.run(
            [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q"],
            cwd=bare, capture_output=True, text=True, timeout=180,
        )
        assert res.returncode == 0, res.stdout + res.stderr
        assert not list(bare.glob("*.scope.json"))
        assert not list(bare.glob("*.xml"))


class TestConfigureClaimsTheRunIncomplete:
    """`pytest_configure` writes `partial` BEFORE the run, and that one line is
    the whole crash-safety guarantee.

    A run that is killed, crashes or is interrupted never reaches
    `pytest_sessionfinish`, so what it leaves behind is a truncated report. The
    configure-time write means the record beside it says `partial` rather than
    the PREVIOUS run's `full` verdict sitting there vouching for a report it
    never saw.

    That guarantee is published in the conftest docstring, in
    `docs/test-report-contract.md` and in the change-log — and until this class
    existed, deleting the line left the suite green: no test called
    `pytest_configure`, and `TestUnderRealPytest` asserts only post-`sessionfinish`
    state, which is written by a different hook and would repair the record
    anyway.

    What turns these red: removing the `write_scope_record(...PARTIAL...)` call
    from `pytest_configure`, or writing any scope other than `partial` there.
    Both verified by mutation.
    """

    def _conftest(self):
        import tests.conftest as conftest  # the producer this repo runs

        return conftest

    def _config(self, tmp_path: Path, xmlpath: str):
        class _Option:
            pass

        option = _Option()
        option.xmlpath = xmlpath

        class _Config:
            def __init__(self):
                self.option = option
                self.rootpath = tmp_path
                self.args = ["tests"]

            def getini(self, name):
                return ["tests"]

        return _Config()

    def test_configure_leaves_a_partial_record_before_the_run(self, tmp_path):
        report = tmp_path / ".prawduct" / ".test-report.xml"
        report.parent.mkdir(parents=True)
        config = self._config(tmp_path, str(report))

        conftest = self._conftest()
        conftest.pytest_configure(config)

        record = Path(str(report) + conftest.SCOPE_RECORD_SUFFIX)
        assert record.is_file(), (
            "pytest_configure wrote no scope record — a crashed run would leave "
            "the previous run's verdict beside a truncated report"
        )
        assert json.loads(record.read_text())["scope"] == conftest.PARTIAL

    def test_a_stale_full_record_is_overwritten_at_configure(self, tmp_path):
        """The case the guarantee is actually FOR.

        An empty directory makes the assertion above pass for a writer that
        merely creates a file. The danger is a PREVIOUS run's `full` record
        surviving beside this run's truncated report, so the fixture starts
        from exactly that state.
        """
        report = tmp_path / ".prawduct" / ".test-report.xml"
        report.parent.mkdir(parents=True)
        conftest = self._conftest()
        record = Path(str(report) + conftest.SCOPE_RECORD_SUFFIX)
        record.write_text(json.dumps({"scope": conftest.FULL, "why": None}) + "\n")

        conftest.pytest_configure(self._config(tmp_path, str(report)))

        assert json.loads(record.read_text())["scope"] == conftest.PARTIAL, (
            "a previous run's `full` verdict survived into this run — it now "
            "vouches for a report it never saw"
        )
