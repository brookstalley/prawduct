"""`tools/ci-suite.py`: where CI's suite runs, and which of its two jobs can fail.

The runner has two stages, run as two jobs: `pool`, which holds the key to testament's pool and
never runs a test, and `tests`, which runs pytest and is never given the key. The table is the
contract:

| The workflow                                        | `pool` job           | `tests` job runs       |
|-----------------------------------------------------|----------------------|------------------------|
| has no key (a fork's pull request)                  | passes, says so      | the whole suite        |
| has a key and the pool answers                      | the pool's result    | what the pool left out |
| has a key and the pool cannot be reached            | passes, with warning | the whole suite        |
| has a key and the pool refuses, or settings are off | fails                | the whole suite        |

The last two rows are the ones a reader would merge, and the difference is the point: an outage
is nobody's to fix and must not turn CI red, while a refused key means CI has stopped using the
pool and nothing but a red job says so. In every row the tree gets a verdict from somewhere.

The stages' outside calls (install the pool's CLI, run on the pool, run pytest) are replaced in
most of these tests; what is exercised is every decision between them. The last class drives the
entry point with nothing handed to it.
"""

from __future__ import annotations

import hashlib
import http.client
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
PASSED = (0, {"exit_code": 0, "verdict": "passed", "verdict_reason": "passed", "report": {"counts": {"passed": 3}, "items": [], "missing": []}})
FAILED = (
    1,
    {
        "exit_code": 1,
        "verdict": "failed",
        "verdict_reason": "tests_failed",
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
# The envelopes below follow testament's frozen exit codes (`testament run --help`: "These codes
# are frozen ... key scripts on verdict"). They replaced fixtures written before `verdict`
# existed, when an outage was exit 2 with `retryable`; the runner now decides by `verdict`.
UNAVAILABLE = (
    75,
    {"exit_code": 75, "verdict": "unavailable", "verdict_reason": "coordinator_unreachable",
     "error": {"code": "coordinator_unreachable", "retryable": True, "ran": 0}},
)
REFUSAL = (
    2,
    {"exit_code": 2, "verdict": "failed", "verdict_reason": "unauthorized",
     "error": {"code": "unauthorized", "retryable": False, "ran": 0}},
)
# A test failed, then the pool lost a batch: exit 2 with `retryable`, and still a failed verdict.
# testament: "a test that failed before the pool cut the run short ... never retry it away".
FAILED_THEN_CUT = (
    2,
    {"exit_code": 2, "verdict": "failed", "verdict_reason": "tests_failed",
     "error": {"code": "batches_lost", "retryable": True, "ran": 3},
     "report": {"counts": {"passed": 2, "failed": 1},
                "items": [{"id": "tests/test_a.py::test_b", "outcome": "failed",
                           "message": "E   assert 1 == 2", "runner": "a-machine-name"}],
                "missing": ["tests/test_c.py::test_d"]}},
)


def _load():
    """Import the hyphenated script by path: it is not an importable module name."""
    spec = importlib.util.spec_from_file_location("ci_suite", _TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ci_suite"] = module
    spec.loader.exec_module(module)
    return module


ci = _load()


class Said:
    """Everything a stage said: its annotations and its summary."""

    def __init__(self):
        self.stream = io.StringIO()
        self.summary: list[str] = []
        self.report = ci.Report(self.stream, self.summary.append)

    @property
    def annotations(self) -> list[str]:
        return self.stream.getvalue().splitlines()

    @property
    def all(self) -> str:
        return self.stream.getvalue() + "\n".join(self.summary)


class PoolJob(Said):
    """The `pool` stage with its two outside calls as fakes.

    `pool` answers are taken in order; an answer may be an exception to raise. `takes` is how
    long each pool call lasts on the stage's clock, which only this fake advances.
    """

    def __init__(self, pool=(), install_error=None, takes=0.0):
        super().__init__()
        self.answers = list(pool)
        self.install_error = install_error
        self.takes = takes
        self.now = 1000.0
        self.installs = 0
        self.waits: list[float] = []

    def _install(self, settings):
        self.installs += 1
        if self.install_error is not None:
            raise self.install_error
        return Path("/nonexistent/testament")

    def _pool(self, testament, settings, wait):
        self.waits.append(wait)
        self.now += self.takes
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    def run(self, env, manifest=MANIFEST):
        return ci.pool_stage(
            env,
            install=self._install,
            pool=self._pool,
            report=self.report,
            manifest=manifest,
            clock=lambda: self.now,
        )


class SuiteJob(Said):
    """The `tests` stage with pytest as a fake that records what it was asked to run."""

    def __init__(self, codes=()):
        super().__init__()
        self.codes = list(codes)
        self.calls: list[list[str]] = []

    def _pytest(self, args):
        self.calls.append(list(args))
        return self.codes.pop(0) if self.codes else 0

    def run(self, ran_on, manifest=MANIFEST):
        return ci.tests_stage(ran_on, pytest=self._pytest, report=self.report, manifest=manifest)


class TestThePoolJobWithNoKey:
    def test_passes_and_leaves_the_suite_to_the_test_job_without_asking_the_pool(self):
        job = PoolJob()

        answer = job.run({})

        assert answer == (0, ci.ON_JOB)
        assert (job.installs, job.waits) == (0, [])

    def test_says_so_without_a_warning(self):
        job = PoolJob()

        job.run({})

        assert [line.split("::")[1] for line in job.annotations] == ["notice"]
        assert "TESTAMENT_KEY" in job.all

    def test_an_empty_key_is_no_key(self):
        # A fork's pull request does not get an unset secret: the expression renders "".
        job = PoolJob()

        answer = job.run({**FULL, "TESTAMENT_KEY": ""})

        assert answer == (0, ci.ON_JOB) and job.installs == 0


class TestThePoolJobWhosePoolAnswers:
    def test_a_passing_run_passes_and_says_the_pool_ran_the_suite(self):
        job = PoolJob(pool=[PASSED])

        assert job.run(dict(FULL)) == (0, ci.ON_POOL)

    def test_a_failing_run_fails_the_job_and_is_still_the_pools_run(self):
        # The test job must run only what the pool left out: the pool did run the suite.
        job = PoolJob(pool=[FAILED])

        assert job.run(dict(FULL)) == (1, ci.ON_POOL)

    def test_a_run_that_collected_nothing_fails_the_job(self):
        # Exit 5 from the pool means the selection matched no test: never a pass.
        job = PoolJob(pool=[(5, {"exit_code": 5, "verdict": "failed", "verdict_reason": "no_tests",
                                 "report": {"counts": {}}})])

        code, _ = job.run(dict(FULL))

        assert code == 5

    def test_the_summary_says_how_the_run_came_out(self):
        job = PoolJob(pool=[FAILED])

        job.run(dict(FULL))

        assert "Ran on the pool: 2 passed, 1 failed" in job.summary

    def test_a_failing_test_is_annotated_under_its_own_id(self):
        # The exact line. A pytest id is full of `:`, and an annotation's title ends at the
        # first `::` it is allowed to contain: unencoded, every failing test's annotation would
        # be cut at the file name and the message would begin with the test's.
        job = PoolJob(pool=[FAILED])

        job.run(dict(FULL))

        assert "::error title=tests/test_a.py%3A%3Atest_b::assert 1 == 2" in job.annotations

    def test_the_summary_names_the_failing_test_and_no_runner(self):
        # The run's log is public. A runner's name is one of the owner's machines.
        job = PoolJob(pool=[FAILED])

        job.run(dict(FULL))

        assert "- `tests/test_a.py::test_b` failed: assert 1 == 2" in job.summary
        assert "a-machine-name" not in job.all

    def test_a_test_that_failed_before_the_run_was_cut_short_is_never_retried_away(self):
        # Retrying would let a flaky or order-dependent failure pass on attempt two and vanish.
        job = PoolJob(pool=[FAILED_THEN_CUT, PASSED])

        code, ran_on = job.run(dict(FULL))

        assert code != 0 and ran_on == ci.ON_POOL
        assert len(job.waits) == 1
        assert "- `tests/test_a.py::test_b` failed: assert 1 == 2" in job.summary
        assert "tests/test_c.py::test_d" in job.all, "the tests the cut left unrun are named"

    def test_tests_the_pool_never_reported_are_named(self):
        answer = (2, {"exit_code": 2, "verdict": "failed", "verdict_reason": "population_mismatch",
                      "error": {"code": "population_mismatch", "retryable": False},
                      "report": {"counts": {"passed": 1}, "missing": ["tests/test_a.py::test_gone"]}})
        job = PoolJob(pool=[answer])

        job.run(dict(FULL))

        assert "tests/test_a.py::test_gone" in job.all


class TestThePoolJobWhosePoolCannotBeReached:
    def test_exit_75_is_an_outage_and_never_a_refused_key(self):
        job = PoolJob(pool=[UNAVAILABLE, UNAVAILABLE])

        code, ran_on = job.run(dict(FULL))

        assert (code, ran_on) == (0, ci.ON_JOB)
        assert not [line for line in job.annotations if line.startswith("::error")]
        assert "key" not in " ".join(job.annotations).lower()

    def test_a_retryable_end_is_tried_once_more(self):
        job = PoolJob(pool=[UNAVAILABLE, PASSED])

        assert job.run(dict(FULL)) == (0, ci.ON_POOL)
        assert len(job.waits) == 2

    def test_two_retryable_ends_pass_the_job_and_leave_the_suite_to_the_test_job(self):
        job = PoolJob(pool=[UNAVAILABLE, UNAVAILABLE])

        assert job.run(dict(FULL)) == (0, ci.ON_JOB)
        assert len(job.waits) == 2

    def test_the_fallback_is_a_warning_naming_why_and_not_an_error(self):
        job = PoolJob(pool=[UNAVAILABLE, UNAVAILABLE])

        job.run(dict(FULL))

        levels = [line.split("::")[1] for line in job.annotations]
        assert "warning" in levels and "error" not in levels
        assert "coordinator_unreachable" in job.all

    def test_a_console_that_cannot_be_reached_passes_the_job(self):
        job = PoolJob(install_error=ci.Unavailable("the pool's console could not be reached"))

        assert job.run(dict(FULL)) == (0, ci.ON_JOB)
        assert job.waits == []

    def test_a_pool_run_that_does_not_finish_in_time_is_not_tried_again(self):
        # It already waited the whole allowance.
        job = PoolJob(pool=[ci.Unavailable("the pool did not finish in time")])

        assert job.run(dict(FULL)) == (0, ci.ON_JOB)
        assert len(job.waits) == 1

    def test_both_attempts_share_one_allowance(self):
        # The workflow's time limit for this job is set from the allowance. Two full waits
        # would outlast it and end the job with no answer for the test job to act on.
        job = PoolJob(pool=[UNAVAILABLE, PASSED], takes=450.0)

        job.run(dict(FULL))

        assert job.waits == [ci.POOL_WAIT_SECONDS, ci.POOL_WAIT_SECONDS - 450.0]

    def test_a_run_lost_at_the_end_of_the_allowance_is_not_tried_again(self):
        job = PoolJob(pool=[UNAVAILABLE, PASSED], takes=float(ci.POOL_WAIT_SECONDS))

        assert job.run(dict(FULL)) == (0, ci.ON_JOB)
        assert len(job.waits) == 1

    def test_the_allowance_is_ten_minutes(self):
        # Pinned as a number: `tests.yml`'s limit for the pool job is derived from it.
        assert ci.POOL_WAIT_SECONDS == 600


class TestThePoolJobThePoolRefuses:
    def test_a_refusal_fails_the_job_and_leaves_the_suite_to_the_test_job(self):
        job = PoolJob(pool=[REFUSAL])

        code, ran_on = job.run(dict(FULL))

        assert code != 0 and ran_on == ci.ON_JOB, "the tree still gets its verdict, from the test job"
        assert [line for line in job.annotations if line.startswith("::error::")]
        assert "unauthorized" in job.all

    def test_a_refusal_is_not_tried_again(self):
        job = PoolJob(pool=[REFUSAL])

        job.run(dict(FULL))

        assert len(job.waits) == 1

    def test_a_build_that_cannot_be_installed_fails_the_job(self):
        job = PoolJob(install_error=ci.Refused("the pool's console answered 401"))

        code, ran_on = job.run(dict(FULL))

        assert code != 0 and ran_on == ci.ON_JOB and job.waits == []

    @pytest.mark.parametrize("missing", ["TESTAMENT_COORDINATOR", "TESTAMENT_CONSOLE"])
    def test_a_key_without_an_address_fails_and_names_the_setting(self, missing):
        env = {k: v for k, v in FULL.items() if k != missing}
        job = PoolJob()

        code, ran_on = job.run(env)

        assert code != 0 and ran_on == ci.ON_JOB and job.installs == 0
        assert missing in job.all

    def test_a_console_that_is_not_https_is_refused_before_the_key_is_sent(self):
        job = PoolJob()

        code, _ = job.run({**FULL, "TESTAMENT_CONSOLE": "http://console.example/"})

        assert code != 0 and job.installs == 0
        assert "https" in job.all

    @pytest.mark.parametrize(
        "answer",
        [
            (0, None),  # a pass with no envelope is a pass nobody can read
            (1, None),  # a crash exits 1 too; without an envelope it is not a test failure
            (-9, None),
            (3, {"exit_code": 3}),
            (2, None),
            (2, {"exit_code": 2}),  # exit 2 with no error named is not known to be an outage
            # Written before `verdict` existed: retryable, but no verdict says it is an outage.
            (2, {"exit_code": 2, "error": {"code": "coordinator_unreachable", "retryable": True}}),
            (0, {"exit_code": 0, "report": {"counts": {"passed": 3}}}),  # a pass with no verdict
            (130, {"exit_code": 130, "verdict": "failed", "verdict_reason": "interrupted"}),
            (2, {"exit_code": 2, "verdict": "maybe", "verdict_reason": "x"}),  # a verdict it has never seen
        ],
    )
    def test_an_end_that_is_not_a_known_result_is_a_refusal(self, answer):
        job = PoolJob(pool=[answer])

        code, ran_on = job.run(dict(FULL))

        assert code != 0 and ran_on == ci.ON_JOB

    def test_a_manifest_whose_selection_cannot_be_read_is_refused_before_the_pool_is_asked(self, tmp_path):
        # Otherwise the pool would run its part and nothing could say what was left.
        manifest = tmp_path / ".testament.toml"
        manifest.write_text('name = "x"\n')
        job = PoolJob(pool=[PASSED])

        code, ran_on = job.run(dict(FULL), manifest=manifest)

        assert code != 0 and ran_on == ci.ON_JOB and job.waits == []

    def test_nothing_the_job_says_holds_the_key(self):
        for job in (PoolJob(pool=[PASSED]), PoolJob(pool=[REFUSAL]), PoolJob(pool=[UNAVAILABLE, UNAVAILABLE])):
            job.run(dict(FULL))
            assert KEY not in job.all


class TestTheTestJob:
    def test_runs_only_what_the_pool_left_out_when_the_pool_ran_the_suite(self):
        job = SuiteJob()

        code = job.run(ci.ON_POOL)

        assert code == 0
        assert job.calls == [["-m", ci.selected_out(MANIFEST)]]

    @pytest.mark.parametrize("ran_on", [ci.ON_JOB, "", "POOL", "pool ", "yes"])
    def test_runs_the_whole_suite_on_any_other_word(self, ran_on):
        # Empty is what a pool job that died before answering leaves behind. Anything that is
        # not exactly the pool's word costs a full run here, never a suite that ran nowhere.
        job = SuiteJob()

        code = job.run(ran_on)

        assert code == 0 and job.calls == [[]], "the whole suite, with no selection"

    @pytest.mark.parametrize("ran_on", [ci.ON_POOL, ci.ON_JOB])
    def test_a_failing_test_fails_the_job(self, ran_on):
        job = SuiteJob(codes=[1])

        assert job.run(ran_on) == 1

    def test_selected_out_tests_that_match_nothing_are_not_a_failure(self):
        # pytest exits 5 when every test is deselected. If the manifest selects out a marker
        # no test carries, the pool ran everything and there is nothing left to run here.
        job = SuiteJob(codes=[5])

        assert job.run(ci.ON_POOL) == 0

    def test_a_whole_suite_that_collects_nothing_is_a_failure(self):
        job = SuiteJob(codes=[5])

        assert job.run(ci.ON_JOB) == 5

    def test_a_manifest_that_selects_nothing_out_leaves_nothing_to_run(self, tmp_path):
        manifest = tmp_path / ".testament.toml"
        manifest.write_text('command = ["python", "-m", "pytest"]\n')
        job = SuiteJob()

        code = job.run(ci.ON_POOL, manifest=manifest)

        assert code == 0 and job.calls == []

    def test_a_manifest_it_cannot_read_runs_the_whole_suite_and_fails(self, tmp_path):
        # The tests the pool left out would otherwise stop running anywhere, silently.
        manifest = tmp_path / ".testament.toml"
        manifest.write_text('name = "x"\n')
        job = SuiteJob()

        code = job.run(ci.ON_POOL, manifest=manifest)

        assert code != 0 and job.calls == [[]]
        assert [line for line in job.annotations if line.startswith("::error::")]

    def test_the_summary_says_which_it_ran(self):
        left_out, whole = SuiteJob(), SuiteJob()

        left_out.run(ci.ON_POOL)
        whole.run(ci.ON_JOB)

        assert "selects out" in "\n".join(left_out.summary)
        assert "whole suite ran here" in "\n".join(whole.summary)


class TestWhatTheTestJobRunsBesideAPoolRun:
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

    def test_a_manifest_that_sets_pytest_addopts_is_refused(self, tmp_path):
        # The other way a manifest could narrow the pool's run without its command saying so.
        manifest = tmp_path / ".testament.toml"
        manifest.write_text('command = ["python", "-m", "pytest", "-m", "not a"]\n[env]\nPYTEST_ADDOPTS = "-k fast"\n')

        with pytest.raises(ci.Refused):
            ci.selected_out(manifest)

    @pytest.mark.parametrize("body", ["", "[tool.pytest.ini_options]\ntestpaths = \"tests\"\n", "not toml ["])
    def test_test_paths_it_cannot_read_are_a_refusal_not_a_crash(self, tmp_path, body):
        # A crash at import would stop the tests stage, whose contract is to always run the suite.
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(body)

        with pytest.raises(ci.Refused):
            ci.test_paths(pyproject)

    def test_the_suites_own_test_paths_are_no_narrowing(self, tmp_path):
        manifest = tmp_path / ".testament.toml"
        manifest.write_text('command = ["python", "-m", "pytest", "-q", "-m", "not a"]\ndefault_selection = ["tests/"]\n')

        assert ci.selected_out(manifest) == "not (not a)"

    def test_no_selection_is_nothing_selected_out(self, tmp_path):
        manifest = tmp_path / ".testament.toml"
        manifest.write_text('command = ["python", "-m", "pytest", "-q"]\n')

        assert ci.selected_out(manifest) is None

    @pytest.mark.parametrize(
        "body",
        [
            'name = "x"\n',
            'command = ["swift", "test"]\n',
            'command = ["python", "-m", "pytest", "-m"]\n',
            # pytest takes the LAST -m, and these forms are not the separate `-m EXPR` this reads.
            'command = ["python", "-m", "pytest", "-m", "a", "-m", "b"]\n',
            'command = ["python", "-m", "pytest", "-mnot slow"]\n',
            # Narrowing it cannot complement: the tests it drops would run in neither job.
            'command = ["python", "-m", "pytest", "-m", "not a", "-k", "fast"]\n',
            'command = ["python", "-m", "pytest", "-m", "not a", "--deselect", "tests/t.py::x"]\n',
            'command = ["python", "-m", "pytest", "-m", "not a", "--ignore=tests/slow"]\n',
            'command = ["python", "-m", "pytest", "tests/unit"]\n',
            'command = ["python", "-m", "pytest", "-m", "not a"]\ndefault_selection = ["tests/unit"]\n',
        ],
    )
    def test_a_command_it_cannot_read_is_refused_not_guessed(self, tmp_path, body):
        manifest = tmp_path / ".testament.toml"
        manifest.write_text(body)

        with pytest.raises(ci.Refused):
            ci.selected_out(manifest)


class TestTheAgentGuideAgrees:
    """`documentation/running-tests.md` is where AGENTS.md sends every agent. Its envelope legend
    once said a retryable exit 2 should be run again, which reruns a failed test away."""

    GUIDE = REPO_ROOT / "documentation" / "running-tests.md"

    def test_the_legend_keys_on_verdict_and_never_reruns_a_failure(self):
        text = " ".join(self.GUIDE.read_text().split())
        assert "`verdict` first" in text
        assert "never rerun it away" in text
        assert "which is **not** a test result" not in text
        assert "when `error.retryable` is true, run again" not in text

    def test_a_reason_is_named_when_the_envelope_names_no_error(self):
        assert "`interrupted`" in ci._why(130, {"verdict": "failed", "verdict_reason": "interrupted"})


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

    @pytest.mark.parametrize("status", [408, 429, 500, 502, 503])
    def test_a_console_that_is_failing_or_busy_is_an_outage(self, tmp_path, status):
        # 408 and 429 are "not now", like a 5xx. Read as a refusal they would turn CI red and
        # send the reader to replace a key that is fine.
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

    def test_a_console_that_drops_mid_download_is_an_outage(self, tmp_path):
        class Dropped(_Response):
            def read(self):
                raise http.client.IncompleteRead(b"partial", 100)

        with pytest.raises(ci.Unavailable):
            ci.fetch_cli(self.settings, tmp_path, opener=lambda request, timeout: Dropped(b"", {}))

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

    def test_pytest_is_handed_nothing_of_testaments(self):
        # A suite run here sees what it saw before CI knew of a pool, on a developer's machine
        # too. This is not what keeps the key from a test (the two jobs are); it is what keeps
        # a test from behaving differently because a setting happened to be exported.
        calls, run = self._recording()

        ci.run_pytest(["-m", "x"], dict(self.ENV), run=run)

        argv, kwargs = calls[0]
        assert argv == [sys.executable, "-m", "pytest", "-m", "x"]
        assert not [name for name in kwargs["env"] if name.startswith("TESTAMENT_")]
        assert kwargs["env"]["PATH"] == "/usr/bin"

    def test_the_pool_run_never_falls_back_and_gets_the_key_the_address_and_the_branch(self, tmp_path):
        settings, _ = ci.read_settings(dict(self.ENV))
        calls, run = self._recording(stdout=b'{"exit_code": 0, "report": {"counts": {"passed": 1}}}')

        code, envelope = ci.pool_run(Path("/x/testament"), settings, 77.0, dict(self.ENV), tmp_path, run=run)

        argv, kwargs = calls[0]
        assert argv[:2] == ["/x/testament", "run"]
        assert "--no-fallback" in argv, "the client must never run the suite in the job that holds the key"
        assert kwargs["env"]["TESTAMENT_KEY"] == KEY
        assert kwargs["env"]["TESTAMENT_COORDINATOR"] == FULL["TESTAMENT_COORDINATOR"]
        assert kwargs["env"]["TESTAMENT_BRANCH"] == "feature/x"
        assert kwargs["timeout"] == 77.0
        # testament finds `.testament.toml` from where it starts; the tests stage complements
        # the repo root's, so the pool run must read that one too.
        assert kwargs["cwd"] == ci.REPO_ROOT
        assert (code, envelope["exit_code"]) == (0, 0)

    def test_output_that_is_not_an_envelope_is_no_envelope(self, tmp_path):
        settings, _ = ci.read_settings(dict(self.ENV))
        _, run = self._recording(returncode=1, stdout=b"Traceback (most recent call last):")

        answer = ci.pool_run(Path("/x/testament"), settings, 77.0, dict(self.ENV), tmp_path, run=run)

        assert answer == (1, None)

    def test_a_pool_run_that_outlasts_its_wait_is_an_outage(self, tmp_path):
        settings, _ = ci.read_settings(dict(self.ENV))

        def run(argv, **kwargs):
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])

        with pytest.raises(ci.Unavailable):
            ci.pool_run(Path("/x/testament"), settings, 77.0, dict(self.ENV), tmp_path, run=run)

    def test_the_build_is_installed_into_its_own_environment_from_the_file_alone(self, tmp_path):
        # `--no-index`: the job that holds the key installs the pool's build and nothing from a
        # package index, which is what lets it hold the key at all.
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
        said = Said()

        said.report.warning("first line\n::error::forged 100%")

        assert said.annotations == ["::warning::first line%0A::error::forged 100%25"]

    def test_a_title_cannot_end_itself_or_add_a_property(self):
        said = Said()

        said.report.error("m", title="a::b,file=x\n100%")

        assert said.annotations == ["::error title=a%3A%3Ab%2Cfile=x%0A100%25::m"]


class TestTheEntryPointBuildsItsOwnSeams:
    """Every test above hands a stage its outside calls. These drive `main`, which has to
    build them itself: a seam nothing constructs is green in all of the above."""

    @pytest.fixture(autouse=True)
    def _a_job_environment(self, monkeypatch, tmp_path):
        for name in list(os.environ):
            if name.startswith("TESTAMENT_") or name == ci.RAN_ON:
                monkeypatch.delenv(name)
        self.summary = tmp_path / "summary.md"
        self.output = tmp_path / "output.txt"
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(self.summary))
        monkeypatch.setenv("GITHUB_OUTPUT", str(self.output))
        self.pytest_calls = []

        def run_pytest(args, env, run=None):
            self.pytest_calls.append(list(args))
            return 0

        monkeypatch.setattr(ci, "run_pytest", run_pytest)

    def test_the_pool_stage_with_no_key_answers_job_and_runs_no_test(self):
        code = ci.main(["ci-suite.py", "pool"])

        assert code == 0
        assert self.output.read_text() == "suite=job\n"
        assert self.pytest_calls == []
        assert "Not sent to the pool" in self.summary.read_text()

    def test_the_pool_stage_fetches_then_installs_then_asks_the_pool_and_runs_no_test(self, monkeypatch):
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

        def pool_run(testament, settings, wait, env, work):
            order.append("pool")
            assert settings.key == KEY and 0 < wait <= ci.POOL_WAIT_SECONDS
            return FAILED

        monkeypatch.setattr(ci, "fetch_cli", fetch_cli)
        monkeypatch.setattr(ci, "install_cli", install_cli)
        monkeypatch.setattr(ci, "pool_run", pool_run)

        code = ci.main(["ci-suite.py", "pool"])

        assert code == 1 and order == ["fetch", "install", "pool"]
        assert self.output.read_text() == "suite=pool\n"
        assert self.pytest_calls == [], "the job that holds the key never runs a test"

    def test_the_tests_stage_reads_the_pool_jobs_word(self, monkeypatch):
        monkeypatch.setenv(ci.RAN_ON, ci.ON_POOL)

        code = ci.main(["ci-suite.py", "tests"])

        assert code == 0
        assert self.pytest_calls == [["-m", ci.selected_out(MANIFEST)]]

    def test_the_tests_stage_with_no_word_runs_the_whole_suite(self):
        code = ci.main(["ci-suite.py", "tests"])

        assert code == 0 and self.pytest_calls == [[]]

    def test_the_tests_stage_never_asks_the_pool_even_when_handed_a_key(self, monkeypatch):
        for name, value in FULL.items():
            monkeypatch.setenv(name, value)
        monkeypatch.setattr(ci, "fetch_cli", lambda *a, **k: pytest.fail("the tests stage fetched the CLI"))

        ci.main(["ci-suite.py", "tests"])

        assert self.pytest_calls == [[]]

    @pytest.mark.parametrize("argv", [["ci-suite.py"], ["ci-suite.py", "both"], ["ci-suite.py", "pool", "tests"]])
    def test_anything_else_is_a_usage_error_that_runs_nothing(self, argv, capsys):
        code = ci.main(argv)

        assert code == 2 and self.pytest_calls == []
        assert "usage" in capsys.readouterr().err
