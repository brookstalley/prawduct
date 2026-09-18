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
        assert report_scope.read_scope_record(report) == (True, None)

    def test_a_full_record_proceeds(self, report):
        _record_beside(report)
        assert report_scope.read_scope_record(report) == (True, None)

    def test_a_partial_record_refuses_and_quotes_its_own_reason(self, report):
        _record_beside(report, scope=PARTIAL, why="-k 'billing' narrowed the selection")
        ok, reason = report_scope.read_scope_record(report)
        assert ok is False
        assert "billing" in reason, "the refusal must say what narrowed the run"
        assert "2026-09-18T05:00:00Z" in reason, "and when the record was written"

    def test_a_partial_record_with_no_reason_still_refuses(self, report):
        _record_beside(report, scope=PARTIAL, why=None)
        ok, reason = report_scope.read_scope_record(report)
        assert ok is False
        assert "no reason recorded" in reason

    def test_malformed_json_refuses(self, report):
        report_scope.record_path(report).write_text("{not json")
        ok, reason = report_scope.read_scope_record(report)
        assert ok is False and "not valid JSON" in reason

    def test_a_non_object_record_refuses(self, report):
        report_scope.record_path(report).write_text("[]")
        ok, reason = report_scope.read_scope_record(report)
        assert ok is False and "not a JSON object" in reason

    def test_an_unreadable_record_refuses(self, report):
        # A directory at the record's path: the OSError branch, which would
        # otherwise traceback out of a command whose errors are return values.
        report_scope.record_path(report).mkdir()
        ok, reason = report_scope.read_scope_record(report)
        assert ok is False and "could not be read" in reason

    @pytest.mark.parametrize("version", [2, "1", None, 0])
    def test_an_unknown_schema_version_refuses(self, report, version):
        _record_beside(report, v=version)
        ok, reason = report_scope.read_scope_record(report)
        assert ok is False
        assert "schema version" in reason and repr(version) in reason

    @pytest.mark.parametrize("scope", ["complete", "", None, "FULL"])
    def test_an_unknown_scope_value_refuses(self, report, scope):
        _record_beside(report, scope=scope)
        ok, reason = report_scope.read_scope_record(report)
        assert ok is False and "scope=" in reason

    def test_a_record_naming_another_report_refuses(self, report):
        # A copied or moved report does not inherit the record's authority.
        _record_beside(report, report=str(report.parent / "somewhere-else.xml"))
        ok, reason = report_scope.read_scope_record(report)
        assert ok is False and "some other run" in reason

    def test_a_record_with_no_report_field_refuses(self, report):
        _record_beside(report, report=None)
        ok, reason = report_scope.read_scope_record(report)
        assert ok is False and "does not name the report" in reason

    def test_unknown_keys_are_tolerated(self, report):
        # Additive-first (`artifacts/api-contract.md` § Direction): a v1 reader
        # must not refuse a record that grew a field it does not know.
        _record_beside(report, selected=417, runner="dotnet test")
        assert report_scope.read_scope_record(report) == (True, None)

    def test_the_record_path_is_the_reports_path_plus_the_suffix(self, tmp_path):
        assert report_scope.record_path(tmp_path / "r.xml") == tmp_path / ("r.xml" + SCOPE_RECORD_SUFFIX)


# =============================================================================
# The CLI — the layer the defect would be reported at
# =============================================================================


def _run_hook(repo: Path, *args: str) -> subprocess.CompletedProcess:
    home = repo.parent / "_home"
    home.mkdir(exist_ok=True)
    return subprocess.run(
        [sys.executable, str(HOOK), *args],
        capture_output=True, text=True, timeout=90,
        env={"HOME": str(home), "CLAUDE_PROJECT_DIR": str(repo),
             "CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT),
             "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
             "PYTHONDONTWRITEBYTECODE": "1"},
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
        assert report_scope.read_scope_record(report) == (True, None)

    def test_a_partial_record_it_writes_is_one_the_reader_refuses(self, tmp_path):
        report = tmp_path / "r.xml"
        write_scope_record(_Config(tmp_path, xmlpath=str(report)), PARTIAL, "because")
        ok, reason = report_scope.read_scope_record(report)
        assert ok is False and "because" in reason

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
        assert report_scope.read_scope_record(report) == (True, None)

    def test_a_narrowed_run_leaves_a_record_the_reader_refuses(self, scratch):
        res = self._run(scratch, "-k", "test_a")
        assert res.returncode == 0, res.stdout + res.stderr
        report = scratch / "report.xml"
        ok, reason = report_scope.read_scope_record(report)
        assert ok is False, "a -k run must not read as suite evidence"
        assert "test_a" in reason

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
