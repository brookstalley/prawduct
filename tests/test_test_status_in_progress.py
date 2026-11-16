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
        running = gates.SuiteStep(gates.SUITE_RUNNING, gates.WAIT_FOR_RUN)
        waiting = gates.transfer_remedy(transfer, "a suite run is in progress", suite_step=running)
        assert "wait" in waiting and "Run the suite" not in waiting
        control = gates.transfer_remedy(transfer, "stale")
        assert "Run the suite" in control
        interrupted = gates.SuiteStep(gates.SUITE_INTERRUPTED, gates.RUN_AND_RECORD)
        assert "Run the suite" in gates.transfer_remedy(transfer, "x", suite_step=interrupted)


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


# =============================================================================
# Round 2 (Critic R-2/R-7, R-4, R-8; native review): every in-progress state has
# an end, every remedy comes from one owner, and a first run is announced too.
# =============================================================================


def _ts(seconds_ago: float = 0.0) -> str:
    return datetime.fromtimestamp(time.time() - seconds_ago, timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _stamp_record(repo: Path, stamp: dict, *, duration: float = 42.0) -> dict:
    """A void record carrying `stamp`, in the shape `_void_test_evidence`
    writes, so every reader meets exactly what a recorder leaves."""
    record = {
        "timestamp": _ts(), "passed": 3, "failed": 0, "skipped": 0,
        "duration_seconds": duration, "command": "x", "verifier": "v",
        "tests_executed": [], "changes_referenced": [], "coverage_level": "referenced",
        "void": "record attempt at now (x) did not complete",
        "degraded": "record attempt did not complete",
        "in_progress": stamp,
    }
    path = repo / ".prawduct" / ".test-evidence.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record))
    return record


def _foreign(seconds_ago: float) -> dict:
    """A stamp written on another machine, whose processes this one cannot see."""
    return {"pid": os.getpid(), "host": "other-box", "machine": "machine-of-other-box",
            "started_at": _ts(seconds_ago), "command": "x"}


def _local(pid: "int | None" = None) -> dict:
    return {"pid": pid or os.getpid(), "host": record_progress.this_host(),
            "machine": record_progress.this_machine(), "started_at": _ts(), "command": "x"}


@pytest.fixture(autouse=True)
def _fresh_probe_memo():
    record_progress.forget()
    yield
    record_progress.forget()


class TestAForeignStampHasAnEnd:
    """R-2/R-7: a stamp from another machine used to read as running forever,
    and every remedy said not to start another run."""

    def test_within_its_bound_it_reads_as_running_elsewhere(self):
        state, why = record_progress.recorder_state(_foreign(60), 42.0)
        assert state == record_progress.ELSEWHERE, why
        assert "other-box" in why

    def test_past_its_bound_it_reads_as_interrupted(self):
        bound = record_progress.unverified_bound(42.0)
        state, why = record_progress.recorder_state(_foreign(bound + 60), 42.0)
        assert state == record_progress.GONE, why
        assert "other-box" in why

    def test_the_bound_scales_with_the_last_run_and_has_a_floor(self):
        floor = record_progress.UNVERIFIED_FLOOR_SECONDS
        assert record_progress.unverified_bound(None) == floor
        assert record_progress.unverified_bound(0) == floor
        assert record_progress.unverified_bound(1.0) == floor
        long_run = floor  # a run as long as the floor gets several times it
        assert record_progress.unverified_bound(long_run) == (
            record_progress.UNVERIFIED_FACTOR * long_run
        )
        # The same age reads differently against a long and a short last run.
        age = floor + 120
        assert record_progress.recorder_state(_foreign(age), long_run)[0] == record_progress.ELSEWHERE
        assert record_progress.recorder_state(_foreign(age), 10.0)[0] == record_progress.GONE

    def test_an_undatable_foreign_stamp_is_interrupted(self):
        stamp = _foreign(0)
        stamp["started_at"] = "not a time"
        assert record_progress.recorder_state(stamp, 42.0)[0] == record_progress.GONE

    def test_the_refusal_names_when_waiting_ends_and_the_way_out(self, tmp_path):
        record = _stamp_record(tmp_path, _foreign(60))
        why = gates.run_refusal(record)
        assert "other-box" in why
        assert "interrupted" in why, "the refusal must say when waiting stops"
        assert "if no run is going on other-box" in why, why

    def test_past_the_bound_the_refusal_says_run_the_suite(self, tmp_path):
        record = _stamp_record(tmp_path, _foreign(10 * 3600))
        why = gates.run_refusal(record)
        assert "Run the suite" in why and "do not start another" not in why, why

    def test_test_status_and_wait_end_on_an_old_foreign_stamp(self, tmp_path):
        repo = _repo(tmp_path)
        _stamp_record(repo, _foreign(10 * 3600))
        started = time.time()
        res = _run_in(repo, "test-status", "--wait", "--timeout", "20")
        assert time.time() - started < 15, "--wait waited on a stamp past its bound"
        assert res.returncode == 1, res.stdout + res.stderr
        assert res.stdout.splitlines()[0].startswith("stale (interrupted):"), res.stdout


class TestTheMachineNotTheHostnameDecidesWhereARunIs:
    def test_the_stamp_carries_a_machine_identity(self):
        assert record_progress.this_machine(), (
            "precondition: this platform yields a machine identity, or the "
            "hostname fallback is all that is tested here"
        )
        assert record_progress.stamp("x", _ts())["machine"] == record_progress.this_machine()

    def test_a_renamed_host_on_the_same_machine_is_checked_locally(self):
        """macOS renames the host with the network; the machine is the same,
        so the pid is checked here rather than read as another host's run."""
        stamp = _local()
        stamp["host"] = "the-name-this-laptop-had-on-another-network"
        state, why = record_progress.recorder_state(stamp, 42.0)
        assert state == record_progress.RUNNING, why

    def test_a_dead_recorder_under_a_renamed_host_is_interrupted(self):
        child = subprocess.Popen([sys.executable, "-c", "pass"])
        child.wait()
        stamp = _local(child.pid)
        stamp["host"] = "renamed"
        assert record_progress.recorder_state(stamp, 42.0)[0] == record_progress.GONE

    def test_a_stamp_without_a_machine_falls_back_to_the_hostname(self):
        stamp = _local()
        del stamp["machine"]
        stamp["host"] = "some-other-host"
        assert record_progress.recorder_state(stamp, 42.0)[0] == record_progress.ELSEWHERE


class TestOneProbePerVerdict:
    """Native finding: every verdict reader re-ran `ps` for the same stamp."""

    def test_the_readers_of_one_record_probe_the_recorder_once(self, tmp_path, monkeypatch):
        repo = _repo(tmp_path)
        _stamp_record(repo, _local())
        calls = []
        real = record_progress.subprocess.run

        def counting(*args, **kwargs):
            # `subprocess` is one module: git's calls come through here too.
            argv = args[0] if args else kwargs.get("args")
            if isinstance(argv, list) and argv and argv[0] == "ps":
                calls.append(argv)
            return real(*args, **kwargs)

        monkeypatch.setattr(record_progress.subprocess, "run", counting)
        assert gates.tests_are_current(repo)[0] is False
        assert gates.suite_vouches_for_tree(repo)[0] is False
        assert gates.suite_remedy(repo).state == gates.SUITE_RUNNING
        assert len(calls) == 1, f"ps ran {len(calls)} times for one stamp"

    def test_forgetting_reprobes_so_a_wait_sees_the_recorder_die(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            time.sleep(0.2)
            stamp = _local(child.pid)
            assert record_progress.recorder_state(stamp)[0] == record_progress.RUNNING
        finally:
            child.kill()
            child.wait()
        assert record_progress.recorder_state(stamp)[0] == record_progress.RUNNING, (
            "control: within one verdict the memo answers"
        )
        record_progress.forget()
        assert record_progress.recorder_state(stamp)[0] == record_progress.GONE

    def test_wait_reprobes_each_poll(self, tmp_path):
        repo = _repo(tmp_path)
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        try:
            time.sleep(0.2)
            _stamp_record(repo, _local(child.pid))
            killer = subprocess.Popen([
                sys.executable, "-c",
                f"import os, signal, time; time.sleep(1.5); os.kill({child.pid}, signal.SIGKILL)",
            ])
            started = time.time()
            # Unreaped after the kill, the child is a zombie, which the probe
            # reads as gone — but only if the wait asks the probe again.
            rc = gates.test_status(repo, wait=True, timeout=20)
            killer.wait()
            assert rc == 1
            assert time.time() - started < 15, "--wait never re-probed the recorder"
        finally:
            child.kill()
            child.wait()


class TestAFirstRunIsAnnounced:
    """R-8: with no standing record the void wrote nothing, so a fresh
    worktree's first run was invisible and `--wait` returned at once."""

    def _fresh(self, tmp_path) -> Path:
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
        assert not (repo / ".prawduct" / ".test-evidence.json").exists()
        return repo

    def test_a_first_run_reads_as_running_and_never_vouches(self, tmp_path):
        repo = self._fresh(tmp_path)
        recorder = _start_run(repo)
        try:
            stub = _evidence(repo)
            assert gates.run_refusal(stub), "the stub must not vouch"
            ok, why = gates._validate_evidence_schema(stub)
            assert ok, why
            res = _run_in(repo, "test-status")
            assert res.returncode == 1
            assert res.stdout.splitlines()[0].startswith("running:"), res.stdout
            waiter = _popen(repo, "test-status", "--wait", "--timeout", "120")
            time.sleep(1.0)
            assert waiter.poll() is None, "--wait returned while the first run was going"
            (repo / "release").touch()
            out, err = waiter.communicate(timeout=60)
            assert waiter.returncode == 0, out + err
        finally:
            (repo / "release").touch()
            recorder.wait(timeout=60)
            _stop_runner(repo)
        landed = _evidence(repo)
        assert "in_progress" not in landed and "void" not in landed and landed["passed"] == 1

    def test_a_killed_first_run_reads_as_interrupted(self, tmp_path):
        repo = self._fresh(tmp_path)
        recorder = _start_run(repo)
        recorder.send_signal(signal.SIGKILL)
        recorder.wait(timeout=30)
        _stop_runner(repo)
        first = _run_in(repo, "test-status").stdout.splitlines()[0]
        assert first.startswith("stale (interrupted):"), first

    @pytest.mark.parametrize("prior", ["{not json", "[1, 2]", '{"timestamp": "x"}'])
    def test_an_unusable_prior_record_is_replaced_by_the_stub(self, tmp_path, prior):
        """Unreadable, not an object, or failing the schema: a void copied from
        any of them is refused before `in_progress` is read, so the run would be
        invisible exactly as with no record at all."""
        repo = self._fresh(tmp_path)
        (repo / ".prawduct" / ".test-evidence.json").write_text(prior)
        recorder = _start_run(repo)
        try:
            res = _run_in(repo, "test-status")
            assert res.stdout.splitlines()[0].startswith("running:"), res.stdout
        finally:
            (repo / "release").touch()
            recorder.wait(timeout=60)
            _stop_runner(repo)


class TestOneOwnerOfTheSuiteRemedy:
    """R-4: callers wrapped the verdict in their own 'run the suite', so a run
    in progress was told to start a second one."""

    def test_the_states(self, tmp_path):
        repo = _repo(tmp_path)
        assert gates.suite_remedy(repo).state == gates.SUITE_NOT_CURRENT
        _stamp_record(repo, _local())
        step = gates.suite_remedy(repo)
        assert step.state == gates.SUITE_RUNNING
        assert "test-status --wait" in step.remedy and "test-evidence record" not in step.remedy
        dead = subprocess.Popen([sys.executable, "-c", "pass"])
        dead.wait()
        _stamp_record(repo, _local(dead.pid))
        step = gates.suite_remedy(repo)
        assert step.state == gates.SUITE_INTERRUPTED
        assert "test-evidence record" in step.remedy
        _stamp_record(repo, _foreign(60))
        step = gates.suite_remedy(repo)
        assert step.state == gates.SUITE_RUNNING and "other-box" in step.remedy

    def test_the_transfer_note_takes_its_wait_from_the_owner(self, tmp_path):
        repo = _repo(tmp_path)
        _stamp_record(repo, _foreign(60))
        step = gates.suite_remedy(repo)
        transfer = {"prior_fact_id": "rev-x", "files": ["a.py"], "reason": ""}
        note = gates.transfer_remedy(transfer, "r", suite_step=step)
        assert step.remedy in note and "if no run is going on other-box" in note

    def test_the_skill_and_review_cycle_rows_defer_to_the_printed_remedy(self):
        for rel in ("skills/critic/SKILL.md", "skills/critic/review-cycle.md"):
            text = " ".join((ROOT / rel).read_text(encoding="utf-8").split())
            assert "the suite runs, then this mode again" not in text, rel
            assert "run the suite, then this mode again" not in text, rel
            at = text.index("**exit 7**") if "**exit 7**" in text else text.index("| **7** |")
            row = text[at:at + 260]
            assert "printed" in row, (rel, row)
