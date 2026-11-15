"""`test-status` tells a run in progress from one that died, and can wait (#1178).

Since #679 the recorder voids the standing record before the suite runs, so
while a run is in flight every reader sees stale — the same answer an abandoned
or failed run gives — and an agent that sees stale starts a second suite on top
of the first. The void now carries `in_progress` (the recorder's pid, host,
start time and command), and `test-status` reports three states:

* **running** — the recorder is alive on this host: wait, do not re-run;
* **stale (interrupted)** — the recorder is gone and no record landed;
* stale / current, as before.

`test-status --wait [--timeout N]` blocks until the run lands or its recorder
dies, then prints the final verdict; a timeout exits 75 (EX_TEMPFAIL: the run is
still going, ask again). Pinned at the CLI with a REAL recorder process: a
declared command that blocks until the test releases it.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "plugin"))

from test_plugin_runtime import HOOK, ROOT, _git, _run_in  # noqa: E402

from lib import gates, record_progress  # noqa: E402

_GREEN = (
    '<testsuites><testsuite name="s" time="{time}">'
    '<testcase classname="c" name="ok"/></testsuite></testsuites>'
)

#: A declared test command that announces its pid, then blocks until the test
#: creates `release` (or two minutes pass), then writes a green report.
_BLOCKING_RUNNER = '''\
import os, sys, time
from pathlib import Path
Path("runner.pid").write_text(str(os.getpid()))
deadline = time.time() + 120
while not Path("release").exists() and time.time() < deadline:
    time.sleep(0.05)
Path(sys.argv[1]).write_text(%r)
''' % _GREEN.format(time="1.0")


def _env(repo: Path) -> dict:
    home = repo.parent / "_home"
    home.mkdir(exist_ok=True)
    return {"HOME": str(home), "CLAUDE_PROJECT_DIR": str(repo),
            "CLAUDE_PLUGIN_ROOT": str(ROOT), "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "PYTHONDONTWRITEBYTECODE": "1"}


def _popen(repo: Path, *args: str) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, str(HOOK), *args], env=_env(repo),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )


def _evidence(repo: Path) -> dict:
    return json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())


def _repo(tmp_path: Path, prior_time: str = "42.0") -> Path:
    """A repo with a green record whose run took `prior_time` seconds, and a
    declared command that blocks until released."""
    repo = tmp_path / "repo"
    (repo / ".prawduct").mkdir(parents=True)
    (repo / "runner.py").write_text(_BLOCKING_RUNNER)
    (repo / ".prawduct" / "project-state.yaml").write_text(
        f"test_command: {sys.executable} runner.py {{junit_xml}}\n"
    )
    _git(repo, "init", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "c1")
    (repo / ".prawduct" / ".session-start").write_text("2000-01-01T00:00:00Z")
    seed = repo / "seed.xml"
    seed.write_text(_GREEN.format(time=prior_time))
    res = _run_in(repo, "test-evidence", "record", "--from-junit", str(seed))
    assert res.returncode == 0, res.stderr
    assert _run_in(repo, "test-status").returncode == 0, "control: the seed reads current"
    return repo


def _until(predicate, timeout: float = 30.0, what: str = "condition") -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError(f"timed out waiting for {what}")


def _start_run(repo: Path) -> subprocess.Popen:
    recorder = _popen(repo, "test-evidence", "record")
    _until(lambda: (repo / "runner.pid").exists(), what="the runner to start")
    assert "in_progress" in _evidence(repo), "the void must carry in_progress before the run"
    return recorder


def _stop_runner(repo: Path) -> None:
    try:
        os.kill(int((repo / "runner.pid").read_text()), signal.SIGKILL)
    except (OSError, ValueError):
        pass


@pytest.fixture
def running(tmp_path):
    repo = _repo(tmp_path)
    recorder = _start_run(repo)
    yield repo, recorder
    if recorder.poll() is None:
        (repo / "release").touch()
        try:
            recorder.wait(timeout=60)
        except subprocess.TimeoutExpired:
            recorder.kill()
            recorder.wait()
    _stop_runner(repo)


class TestThreeStates:
    def test_a_live_run_reads_as_running_not_stale(self, running):
        repo, recorder = running
        res = _run_in(repo, "test-status")
        first = res.stdout.splitlines()[0]
        assert res.returncode == 1, res.stdout
        assert first.startswith("running:"), first
        assert "wait" in first and "test-status --wait" in first
        assert f"pid {recorder.pid}" in first

        (repo / "release").touch()
        assert recorder.wait(timeout=60) == 0, recorder.stderr.read()
        landed = _evidence(repo)
        assert "in_progress" not in landed and "void" not in landed
        assert _run_in(repo, "test-status").returncode == 0

    def test_a_killed_recorder_reads_as_interrupted(self, running):
        repo, recorder = running
        recorder.send_signal(signal.SIGKILL)
        recorder.wait(timeout=30)
        _stop_runner(repo)
        res = _run_in(repo, "test-status")
        first = res.stdout.splitlines()[0]
        assert res.returncode == 1, res.stdout
        assert first.startswith("stale (interrupted):"), first
        assert "no longer running" in first

    def test_elapsed_and_the_estimate_are_shown(self, running):
        repo, _ = running
        first = _run_in(repo, "test-status").stdout.splitlines()[0]
        assert "elapsed" in first
        assert "42s" in first and "estimate" in first, first
        assert "%" not in first


def test_no_estimate_without_a_previous_duration(tmp_path):
    repo = _repo(tmp_path, prior_time="0")
    recorder = _start_run(repo)
    try:
        first = _run_in(repo, "test-status").stdout.splitlines()[0]
        assert first.startswith("running:") and "elapsed" in first
        assert "estimate" not in first, first
    finally:
        (repo / "release").touch()
        recorder.wait(timeout=60)


class TestTheGatesSayWait:
    def test_run_refusal_says_wait_not_rerun(self, running):
        repo, _ = running
        why = gates.run_refusal(_evidence(repo))
        assert "in progress" in why and "wait" in why
        assert "Run the suite" not in why and "run the suite" not in why

    def test_tests_are_current_says_wait(self, running):
        repo, _ = running
        current, reason, _clause = gates.tests_are_current(repo)
        assert current is False
        assert "in progress" in reason and "wait" in reason

    def test_suite_vouches_says_wait(self, running):
        repo, _ = running
        vouches, reason = gates.suite_vouches_for_tree(repo)
        assert vouches is False and "wait" in reason

    def test_the_transfer_remedy_says_wait_not_rerun(self):
        transfer = {"prior_fact_id": "rev-x", "files": ["a.py"], "reason": ""}
        waiting = gates.transfer_remedy(transfer, "a suite run is in progress", in_progress=True)
        assert "wait" in waiting and "Run the suite" not in waiting
        control = gates.transfer_remedy(transfer, "stale")
        assert "Run the suite" in control


class TestWait:
    def test_wait_returns_when_the_record_lands(self, running):
        repo, _ = running
        waiter = _popen(repo, "test-status", "--wait", "--timeout", "120")
        time.sleep(1.0)
        assert waiter.poll() is None, "--wait returned while the run was still going"
        (repo / "release").touch()
        out, err = waiter.communicate(timeout=60)
        assert waiter.returncode == 0, out + err
        assert out.splitlines()[0].startswith("current"), out

    def test_wait_returns_when_the_recorder_dies(self, running):
        repo, recorder = running
        waiter = _popen(repo, "test-status", "--wait", "--timeout", "120")
        time.sleep(1.0)
        started = time.time()
        recorder.send_signal(signal.SIGKILL)
        recorder.wait(timeout=30)
        _stop_runner(repo)
        out, err = waiter.communicate(timeout=60)
        assert time.time() - started < 30, "--wait did not notice the recorder died"
        assert waiter.returncode == 1, out + err
        assert out.splitlines()[0].startswith("stale (interrupted):"), out

    def test_wait_honours_its_timeout(self, running):
        repo, _ = running
        started = time.time()
        res = _run_in(repo, "test-status", "--wait", "--timeout", "2")
        assert res.returncode == 75, res.stdout + res.stderr
        assert 1.5 <= time.time() - started < 30
        assert res.stdout.splitlines()[0].startswith("running:")
        assert "timed out" in res.stdout

    def test_wait_with_nothing_in_progress_answers_at_once(self, tmp_path):
        repo = _repo(tmp_path)
        res = _run_in(repo, "test-status", "--wait")
        assert res.returncode == 0, res.stdout + res.stderr

    @pytest.mark.parametrize("args", [
        ["--timeout", "5"],
        ["--wait", "--timeout"],
        ["--wait", "--timeout", "abc"],
        ["--wait", "--timeout", "0"],
        ["--wait", "--timeout", str(record_progress.WAIT_MAX_SECONDS + 1)],
        ["--bogus"],
    ])
    def test_a_bad_invocation_is_a_usage_error(self, tmp_path, args):
        repo = _repo(tmp_path)
        res = _run_in(repo, "test-status", *args)
        assert res.returncode == 2, (args, res.stdout, res.stderr)


class TestTheRecorderProbe:
    def _stamp(self, pid: int, started_at: str, host: str | None = None) -> dict:
        return {"pid": pid, "started_at": started_at, "command": "x",
                "host": host or record_progress.this_host()}

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def test_a_live_process_is_running(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            time.sleep(0.2)
            state, _ = record_progress.recorder_state(self._stamp(child.pid, self._now()))
            assert state == record_progress.RUNNING
        finally:
            child.kill()
            child.wait()

    def test_a_reused_pid_is_not_the_recorder(self):
        """A live process that started AFTER the stamp cannot be the recorder
        that wrote it: the pid was reused."""
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            time.sleep(0.2)
            state, why = record_progress.recorder_state(
                self._stamp(child.pid, "2000-01-01T00:00:00Z")
            )
            assert state == record_progress.GONE, why
            assert "reused" in why
        finally:
            child.kill()
            child.wait()

    def test_an_unreaped_zombie_is_gone(self):
        child = subprocess.Popen([sys.executable, "-c", "pass"])
        stamp = self._stamp(child.pid, self._now())
        _until(lambda: subprocess.run(
            ["ps", "-o", "stat=", "-p", str(child.pid)], capture_output=True, text=True
        ).stdout.strip().startswith("Z"), what="the child to exit")
        try:
            state, _ = record_progress.recorder_state(stamp)
            assert state == record_progress.GONE
        finally:
            child.wait()

    def test_a_dead_pid_is_gone(self):
        child = subprocess.Popen([sys.executable, "-c", "pass"])
        child.wait()
        state, _ = record_progress.recorder_state(self._stamp(child.pid, self._now()))
        assert state == record_progress.GONE

    def test_another_host_cannot_be_checked(self):
        state, why = record_progress.recorder_state(
            self._stamp(os.getpid(), self._now(), host="some-other-host")
        )
        assert state == record_progress.ELSEWHERE and "some-other-host" in why
