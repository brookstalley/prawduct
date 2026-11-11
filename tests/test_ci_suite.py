"""`tools/ci-suite.py`: where a CI job's suite runs, and what the job's result is.

The runner has four situations and each has a different answer. The table is the contract:

| The job                                             | Suite runs                          | Result  |
|-----------------------------------------------------|-------------------------------------|---------|
| has no key (a fork's pull request)                  | on the job                          | suite's |
| has a key and the pool answers                      | pool, plus selected-out on the job  | theirs  |
| has a key and the pool cannot be reached            | on the job, with a warning          | suite's |
| has a key and the pool refuses, or settings are off | on the job, for the tree's verdict  | failed  |

The last two rows are the ones a reader would merge, and the difference is the point: an outage
is nobody's to fix and must not turn CI red, while a refused key means CI has stopped using the
pool and nothing but a red job says so.

The runner's three outside calls (install the pool's CLI, run on the pool, run pytest here) are
replaced in these tests; what is exercised is every decision between them.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import os
import subprocess
import sys
import tomllib
import urllib.error
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
_TOOL = REPO_ROOT / "tools" / "ci-suite.py"
MANIFEST = REPO_ROOT / ".testament.toml"

KEY = "not-a-real-key"
FULL = {
    "TESTAMENT_KEY": KEY,
    "TESTAMENT_COORDINATOR": "tls://wire.example:443",
    "TESTAMENT_CONSOLE": "https://console.example/",
}
PASSED = (0, {"exit_code": 0, "report": {"counts": {"passed": 3}, "items": [], "missing": []}})
FAILED = (
    1,
    {
        "exit_code": 1,
        "report": {
            "counts": {"passed": 2, "failed": 1},
            "items": [
                {
                    "id": "tests/test_a.py::test_b",
                    "outcome": "failed",
                    "message": "def test_b():\nE   assert 1 == 2\ntests/test_a.py:3",
                    "runner": "a-machine-name",
                }
            ],
            "missing": [],
        },
    },
)
RETRYABLE = (2, {"exit_code": 2, "error": {"code": "coordinator_unreachable", "retryable": True}})
REFUSAL = (2, {"exit_code": 2, "error": {"code": "unauthorized", "retryable": False}})


def _load():
    """Import the hyphenated script by path: it is not an importable module name."""
    spec = importlib.util.spec_from_file_location("ci_suite", _TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ci_suite"] = module
    spec.loader.exec_module(module)
    return module


ci = _load()


class Job:
    """One job: the three outside calls as fakes, and everything the runner said."""

    def __init__(self, pool=(), pytest_codes=(), install_error=None):
        self.pool_answers = list(pool)
        self.pytest_codes = list(pytest_codes)
        self.install_error = install_error
        self.installs = 0
        self.pool_calls = 0
        self.pytest_calls: list[list[str]] = []
        self.stream = io.StringIO()
        self.summary: list[str] = []

    def install(self, settings):
        self.installs += 1
        if self.install_error is not None:
            raise self.install_error
        return Path("/nonexistent/testament")

    def pool(self, testament, settings):
        self.pool_calls += 1
        answer = self.pool_answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    def pytest(self, args):
        self.pytest_calls.append(list(args))
        return self.pytest_codes.pop(0) if self.pytest_codes else 0

    def run(self, env, manifest=MANIFEST):
        report = ci.Report(self.stream, self.summary.append)
        return ci.run(
            env,
            install=self.install,
            pool=self.pool,
            pytest=self.pytest,
            report=report,
            manifest=manifest,
        )

    @property
    def said(self) -> str:
        return self.stream.getvalue() + "\n".join(self.summary)


class TestAJobWithNoKey:
    def test_runs_the_whole_suite_on_the_job_and_never_asks_the_pool(self):
        job = Job()

        code = job.run({})

        assert code == 0
        assert job.pytest_calls == [[]], "the whole suite, with no selection of the runner's own"
        assert (job.installs, job.pool_calls) == (0, 0)

    def test_the_suites_failure_is_the_jobs(self):
        job = Job(pytest_codes=[1])

        assert job.run({}) == 1

    def test_says_where_the_suite_ran_without_a_warning(self):
        job = Job()

        job.run({})

        assert "::notice::" in job.said and "::warning::" not in job.said
        assert "on this job" in job.said

    def test_an_empty_key_is_no_key(self):
        # A fork's pull request does not get an unset secret: the expression renders "".
        job = Job()

        code = job.run({**FULL, "TESTAMENT_KEY": ""})

        assert code == 0 and job.installs == 0


class TestAJobWhosePoolAnswers:
    def test_a_passing_pool_run_then_runs_what_the_manifest_selects_out(self):
        job = Job(pool=[PASSED])

        code = job.run(dict(FULL))

        assert code == 0
        assert job.pytest_calls == [["-m", ci.selected_out(MANIFEST)]]

    def test_a_failing_pool_run_fails_the_job_and_the_rest_still_runs(self):
        # Every leg reports: the selected-out tests are not skipped because the pool's failed.
        job = Job(pool=[FAILED])

        code = job.run(dict(FULL))

        assert code == 1
        assert len(job.pytest_calls) == 1

    def test_a_failing_selected_out_test_fails_a_job_whose_pool_run_passed(self):
        job = Job(pool=[PASSED], pytest_codes=[1])

        assert job.run(dict(FULL)) == 1

    def test_a_pool_run_that_collected_nothing_fails_the_job(self):
        # Exit 5 from the pool means the selection matched no test: never a pass.
        job = Job(pool=[(5, {"exit_code": 5, "report": {"counts": {}}})])

        assert job.run(dict(FULL)) == 5

    def test_selected_out_tests_that_match_nothing_are_not_a_failure(self):
        # pytest exits 5 when every test is deselected. If the manifest selects out a marker
        # no test carries, the pool ran everything and there is nothing left to run here.
        job = Job(pool=[PASSED], pytest_codes=[5])

        assert job.run(dict(FULL)) == 0

    def test_a_manifest_that_selects_nothing_out_leaves_nothing_for_the_job(self, tmp_path):
        manifest = tmp_path / ".testament.toml"
        manifest.write_text('command = ["python", "-m", "pytest"]\n')
        job = Job(pool=[PASSED])

        code = job.run(dict(FULL), manifest=manifest)

        assert code == 0 and job.pytest_calls == []

    def test_the_summary_names_the_failing_test_and_no_runner(self):
        # The run's log is public. A runner's name is one of the owner's machines.
        job = Job(pool=[FAILED])

        job.run(dict(FULL))

        assert "tests/test_a.py::test_b" in job.said
        assert "assert 1 == 2" in job.said
        assert "a-machine-name" not in job.said

    def test_the_summary_says_the_suite_ran_on_the_pool_and_how_it_came_out(self):
        job = Job(pool=[FAILED])

        job.run(dict(FULL))

        assert "Ran on the pool: 2 passed, 1 failed" in job.summary

    def test_tests_the_pool_never_reported_are_named(self):
        answer = (2, {"exit_code": 2, "error": {"code": "population_mismatch", "retryable": False},
                      "report": {"counts": {"passed": 1}, "missing": ["tests/test_a.py::test_gone"]}})
        job = Job(pool=[answer])

        job.run(dict(FULL))

        assert "tests/test_a.py::test_gone" in job.said


class TestAJobWhosePoolCannotBeReached:
    def test_a_retryable_end_is_tried_once_more(self):
        job = Job(pool=[RETRYABLE, PASSED])

        code = job.run(dict(FULL))

        assert code == 0 and job.pool_calls == 2
        assert job.pytest_calls == [["-m", ci.selected_out(MANIFEST)]], "a pool verdict, not a fallback"

    def test_two_retryable_ends_run_the_whole_suite_on_the_job(self):
        job = Job(pool=[RETRYABLE, RETRYABLE])

        code = job.run(dict(FULL))

        assert code == 0 and job.pool_calls == 2
        assert job.pytest_calls == [[]]

    def test_the_fallback_is_a_warning_naming_why_and_the_job_takes_the_suites_result(self):
        job = Job(pool=[RETRYABLE, RETRYABLE], pytest_codes=[1])

        code = job.run(dict(FULL))

        assert code == 1
        assert "::warning::" in job.said and "coordinator_unreachable" in job.said
        assert "::error::" not in job.said

    def test_a_console_that_cannot_be_reached_runs_the_suite_on_the_job(self):
        job = Job(install_error=ci.Unavailable("the pool's console could not be reached"))

        code = job.run(dict(FULL))

        assert code == 0 and job.pool_calls == 0 and job.pytest_calls == [[]]
        assert "::warning::" in job.said

    def test_a_pool_run_that_does_not_finish_in_time_is_not_tried_again(self):
        # It already waited the whole allowance; a second wait would spend the job's own.
        job = Job(pool=[ci.Unavailable("the pool did not finish in time")])

        code = job.run(dict(FULL))

        assert code == 0 and job.pool_calls == 1 and job.pytest_calls == [[]]


class TestAJobThePoolRefuses:
    def test_a_refusal_fails_the_job_even_when_the_suite_passes_on_it(self):
        job = Job(pool=[REFUSAL])

        code = job.run(dict(FULL))

        assert code != 0
        assert job.pytest_calls == [[]], "the tree still gets its verdict"
        assert "::error::" in job.said and "unauthorized" in job.said

    def test_a_refusal_is_not_tried_again(self):
        job = Job(pool=[REFUSAL])

        job.run(dict(FULL))

        assert job.pool_calls == 1

    def test_a_refused_job_whose_suite_fails_reports_the_suites_code(self):
        job = Job(pool=[REFUSAL], pytest_codes=[1])

        assert job.run(dict(FULL)) == 1

    def test_a_build_that_cannot_be_installed_fails_the_job(self):
        job = Job(install_error=ci.Refused("the pool's console answered 401"))

        code = job.run(dict(FULL))

        assert code != 0 and job.pool_calls == 0 and job.pytest_calls == [[]]

    @pytest.mark.parametrize("missing", ["TESTAMENT_COORDINATOR", "TESTAMENT_CONSOLE"])
    def test_a_key_without_an_address_fails_and_names_the_setting(self, missing):
        env = {k: v for k, v in FULL.items() if k != missing}
        job = Job()

        code = job.run(env)

        assert code != 0 and job.installs == 0
        assert missing in job.said and "::error::" in job.said

    def test_a_console_that_is_not_https_is_refused_before_the_key_is_sent(self):
        job = Job()

        code = job.run({**FULL, "TESTAMENT_CONSOLE": "http://console.example/"})

        assert code != 0 and job.installs == 0
        assert "https" in job.said

    @pytest.mark.parametrize(
        "answer",
        [
            (0, None),  # a pass with no envelope is a pass nobody can read
            (1, None),  # a crash exits 1 too; without an envelope it is not a test failure
            (-9, None),
            (3, {"exit_code": 3}),
            (2, None),
            (2, {"exit_code": 2}),  # exit 2 with no error named is not known to be an outage
        ],
    )
    def test_an_end_that_is_not_a_known_result_is_a_refusal(self, answer):
        job = Job(pool=[answer])

        code = job.run(dict(FULL))

        assert code != 0 and job.pytest_calls == [[]]

    def test_a_manifest_whose_selection_cannot_be_read_fails_the_job(self, tmp_path):
        # Otherwise the tests the pool leaves out would stop running anywhere, silently.
        manifest = tmp_path / ".testament.toml"
        manifest.write_text('name = "x"\n')
        job = Job(pool=[PASSED])

        code = job.run(dict(FULL), manifest=manifest)

        assert code != 0 and "::error::" in job.said

    def test_nothing_the_runner_says_holds_the_key(self):
        for job in (Job(pool=[PASSED]), Job(pool=[REFUSAL]), Job(pool=[RETRYABLE, RETRYABLE])):
            job.run(dict(FULL))
            assert KEY not in job.said


class TestWhatTheJobRunsBesideAPoolRun:
    def test_it_is_the_complement_of_the_manifests_own_selection(self):
        command = tomllib.loads(MANIFEST.read_text())["command"]
        selection = command[command.index("pytest") + 1 :]
        manifest_expression = selection[selection.index("-m") + 1]

        assert ci.selected_out(MANIFEST) == f"not ({manifest_expression})"

    def test_pythons_own_dash_m_is_not_the_selection(self, tmp_path):
        # `python -m pytest` carries a `-m` before pytest's; reading that one would select
        # the tests marked `pytest`, which is none of them.
        manifest = tmp_path / ".testament.toml"
        manifest.write_text('command = ["uv", "run", "python", "-m", "pytest", "-m", "not slow"]\n')

        assert ci.selected_out(manifest) == "not (not slow)"

    def test_no_selection_is_nothing_selected_out(self, tmp_path):
        manifest = tmp_path / ".testament.toml"
        manifest.write_text('command = ["python", "-m", "pytest", "-q"]\n')

        assert ci.selected_out(manifest) is None

    @pytest.mark.parametrize(
        "body",
        ['name = "x"\n', 'command = ["swift", "test"]\n', 'command = ["python", "-m", "pytest", "-m"]\n'],
    )
    def test_a_command_it_cannot_read_is_refused_not_guessed(self, tmp_path, body):
        manifest = tmp_path / ".testament.toml"
        manifest.write_text(body)

        with pytest.raises(ci.Refused):
            ci.selected_out(manifest)


class _Response:
    def __init__(self, body: bytes, headers: dict[str, str]):
        self._body = body
        self.headers = headers

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _wheel_response(body=b"wheel-bytes", name="testament-0.44.1-py3-none-any.whl", checksum=None):
    headers = {"Content-Disposition": f'attachment; filename="{name}"'}
    if checksum is not False:
        headers["X-Testament-Wheel-SHA256"] = checksum or hashlib.sha256(body).hexdigest()
    return _Response(body, headers)


class TestFetchingThePoolsBuild:
    def setup_method(self):
        self.settings, problem = ci.read_settings(dict(FULL))
        assert problem is None

    def test_asks_the_console_with_the_key_as_a_bearer_token(self, tmp_path):
        seen = {}

        def opener(request, timeout):
            seen["url"] = request.full_url
            seen["authorization"] = request.get_header("Authorization")
            return _wheel_response()

        wheel = ci.fetch_cli(self.settings, tmp_path, opener=opener)

        assert seen == {
            "url": "https://console.example/api/v1/cli/wheel",
            "authorization": f"Bearer {KEY}",
        }
        assert wheel == tmp_path / "testament-0.44.1-py3-none-any.whl"
        assert wheel.read_bytes() == b"wheel-bytes"

    def test_bytes_that_do_not_match_the_pools_checksum_are_not_kept(self, tmp_path):
        opener = lambda request, timeout: _wheel_response(checksum="0" * 64)  # noqa: E731

        with pytest.raises(ci.Refused, match="sha256"):
            ci.fetch_cli(self.settings, tmp_path, opener=opener)
        assert list(tmp_path.iterdir()) == []

    def test_a_download_with_no_checksum_is_not_kept(self, tmp_path):
        opener = lambda request, timeout: _wheel_response(checksum=False)  # noqa: E731

        with pytest.raises(ci.Refused, match="checksum"):
            ci.fetch_cli(self.settings, tmp_path, opener=opener)

    @pytest.mark.parametrize(
        "name", ["../evil-1.0-py3-none-any.whl", "other-1.0-py3-none-any.whl", "testament.tar.gz", ""]
    )
    def test_a_name_that_is_not_testaments_wheel_is_not_written(self, tmp_path, name):
        opener = lambda request, timeout: _wheel_response(name=name)  # noqa: E731

        with pytest.raises(ci.Refused):
            ci.fetch_cli(self.settings, tmp_path, opener=opener)
        assert list(tmp_path.iterdir()) == []

    @pytest.mark.parametrize("status", [401, 403, 404, 302])
    def test_an_answer_that_is_not_the_build_is_a_refusal(self, tmp_path, status):
        def opener(request, timeout):
            raise urllib.error.HTTPError(request.full_url, status, "no", {}, None)

        with pytest.raises(ci.Refused, match=str(status)):
            ci.fetch_cli(self.settings, tmp_path, opener=opener)

    @pytest.mark.parametrize("status", [500, 502, 503])
    def test_a_console_that_is_failing_is_an_outage(self, tmp_path, status):
        def opener(request, timeout):
            raise urllib.error.HTTPError(request.full_url, status, "no", {}, None)

        with pytest.raises(ci.Unavailable):
            ci.fetch_cli(self.settings, tmp_path, opener=opener)

    @pytest.mark.parametrize(
        "error", [urllib.error.URLError("no route"), TimeoutError("slow"), ConnectionResetError("gone")]
    )
    def test_a_console_that_does_not_answer_is_an_outage(self, tmp_path, error):
        def opener(request, timeout):
            raise error

        with pytest.raises(ci.Unavailable):
            ci.fetch_cli(self.settings, tmp_path, opener=opener)

    def test_a_redirect_is_never_followed(self):
        # urllib would carry the Authorization header to wherever the redirect points.
        handler = ci.NoRedirect()

        assert handler.redirect_request(None, None, 302, "Found", {}, "https://elsewhere.example/") is None


class TestWhatEachProcessIsGiven:
    ENV = {**FULL, "TESTAMENT_BRANCH": "feature/x", "PATH": "/usr/bin", "HOME": "/home/ci"}

    def _recording(self, returncode=0, stdout=b""):
        calls = []

        def run(argv, **kwargs):
            calls.append((argv, kwargs))
            if kwargs.get("stdout") is not None and stdout:
                kwargs["stdout"].write(stdout)
            return subprocess.CompletedProcess(argv, returncode)

        return calls, run

    def test_pytest_on_the_job_sees_nothing_of_testaments(self):
        # The key must never reach a test process, and a test that reads the other settings
        # would behave differently on the job than on a developer's machine.
        calls, run = self._recording()

        ci.run_pytest(["-m", "x"], dict(self.ENV), run=run)

        argv, kwargs = calls[0]
        assert argv == [sys.executable, "-m", "pytest", "-m", "x"]
        assert not [name for name in kwargs["env"] if name.startswith("TESTAMENT_")]
        assert kwargs["env"]["PATH"] == "/usr/bin"

    def test_the_pool_run_never_falls_back_and_gets_the_key_the_address_and_the_branch(self, tmp_path):
        settings, _ = ci.read_settings(dict(self.ENV))
        calls, run = self._recording(stdout=b'{"exit_code": 0, "report": {"counts": {"passed": 1}}}')

        code, envelope = ci.pool_run(Path("/x/testament"), settings, dict(self.ENV), tmp_path, run=run)

        argv, kwargs = calls[0]
        assert argv[:2] == ["/x/testament", "run"]
        assert "--no-fallback" in argv, "the runner owns the fallback; the client must not also run the suite here"
        assert kwargs["env"]["TESTAMENT_KEY"] == KEY
        assert kwargs["env"]["TESTAMENT_COORDINATOR"] == FULL["TESTAMENT_COORDINATOR"]
        assert kwargs["env"]["TESTAMENT_BRANCH"] == "feature/x"
        assert kwargs["timeout"] == ci.POOL_WAIT_SECONDS
        assert (code, envelope["exit_code"]) == (0, 0)

    def test_output_that_is_not_an_envelope_is_no_envelope(self, tmp_path):
        settings, _ = ci.read_settings(dict(self.ENV))
        _, run = self._recording(returncode=1, stdout=b"Traceback (most recent call last):")

        assert ci.pool_run(Path("/x/testament"), settings, dict(self.ENV), tmp_path, run=run) == (1, None)

    def test_a_pool_run_that_outlasts_its_allowance_is_an_outage(self, tmp_path):
        settings, _ = ci.read_settings(dict(self.ENV))

        def run(argv, **kwargs):
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])

        with pytest.raises(ci.Unavailable):
            ci.pool_run(Path("/x/testament"), settings, dict(self.ENV), tmp_path, run=run)

    def test_the_build_is_installed_into_its_own_environment_from_the_file_alone(self, tmp_path):
        # Its own environment: testament in the suite's would put its pytest plugin in the
        # suite. `--no-index`: the job installs the pool's build and nothing it did not send.
        calls, run = self._recording()
        wheel = tmp_path / "testament-0.44.1-py3-none-any.whl"

        testament = ci.install_cli(wheel, tmp_path / "venv", dict(self.ENV), run=run)

        assert testament == tmp_path / "venv" / "bin" / "testament"
        assert calls[0][0] == [sys.executable, "-m", "venv", str(tmp_path / "venv")]
        assert "--no-index" in calls[1][0] and str(wheel) in calls[1][0]
        for _, kwargs in calls:
            assert "TESTAMENT_KEY" not in kwargs["env"]

    def test_an_install_that_fails_is_a_refusal(self, tmp_path):
        _, run = self._recording(returncode=1)

        with pytest.raises(ci.Refused):
            ci.install_cli(tmp_path / "w.whl", tmp_path / "venv", dict(self.ENV), run=run)


class TestWorkflowCommands:
    def test_a_message_cannot_end_its_own_command_or_start_another(self):
        stream = io.StringIO()
        report = ci.Report(stream, lambda line: None)

        report.warning("first line\n::error::forged 100%")

        assert stream.getvalue() == "::warning::first line%0A::error::forged 100%25\n"


class TestTheEntryPointBuildsItsOwnSeams:
    """Every test above hands `run` its three outside calls. These drive `main`, which has
    to build them itself: a seam nothing constructs is green in all of the above."""

    @pytest.fixture(autouse=True)
    def _a_job_environment(self, monkeypatch, tmp_path):
        for name in list(os.environ):
            if name.startswith("TESTAMENT_"):
                monkeypatch.delenv(name)
        self.summary = tmp_path / "summary.md"
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(self.summary))
        self.pytest_calls = []

        def run_pytest(args, env, run=None):
            self.pytest_calls.append((list(args), dict(env)))
            return 0

        monkeypatch.setattr(ci, "run_pytest", run_pytest)

    def test_with_no_key_it_runs_pytest_and_writes_the_summary_file(self):
        code = ci.main()

        assert code == 0
        assert [args for args, _ in self.pytest_calls] == [[]]
        assert "Ran on this job" in self.summary.read_text()

    def test_with_a_key_it_fetches_then_installs_then_asks_the_pool(self, monkeypatch):
        for name, value in FULL.items():
            monkeypatch.setenv(name, value)
        order = []

        def fetch_cli(settings, dest):
            order.append("fetch")
            assert dest.is_dir(), "the working directory exists before anything is written to it"
            return dest / "testament-0-py3-none-any.whl"

        def install_cli(wheel, venv, env):
            order.append("install")
            return venv / "bin" / "testament"

        def pool_run(testament, settings, env, work):
            order.append("pool")
            assert env["TESTAMENT_KEY"] == KEY and settings.key == KEY
            return PASSED

        monkeypatch.setattr(ci, "fetch_cli", fetch_cli)
        monkeypatch.setattr(ci, "install_cli", install_cli)
        monkeypatch.setattr(ci, "pool_run", pool_run)

        code = ci.main()

        assert code == 0 and order == ["fetch", "install", "pool"]
        assert [args for args, _ in self.pytest_calls] == [["-m", ci.selected_out(MANIFEST)]]
        assert "Ran on the pool" in self.summary.read_text()
