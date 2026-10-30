"""Pins the pytest ``addopts`` that keep a timed-out or crashed xdist worker from hanging the run (#997).

The timeout-method and worker-restart flags are read from the ``addopts`` pytest itself
loaded (``pytestconfig.getini``) rather than restated, so the test follows the config it
protects.
"""

from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_BOUND = 120


def _flags(pytestconfig) -> list[str]:
    addopts = list(pytestconfig.getini("addopts"))
    out: list[str] = []
    for i, tok in enumerate(addopts):
        if tok in ("--timeout-method", "--max-worker-restart"):
            out += [tok, addopts[i + 1]]
    return out


def _run(tmp_path: Path, files: dict[str, str], flags: list[str]):
    for name, body in files.items():
        (tmp_path / name).write_text(body)
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    junit = tmp_path / "report.xml"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-n", "2", "--dist", "loadfile", "--timeout", "2",
         *flags, f"--junit-xml={junit}", "-p", "no:randomly", "-q"],
        cwd=tmp_path, capture_output=True, text=True, timeout=_BOUND,
    )
    return proc, junit


def test_addopts_pin_signal_timeout_and_no_worker_restart(pytestconfig):
    assert _flags(pytestconfig) == ["--timeout-method", "signal", "--max-worker-restart", "0"]


def test_a_timed_out_test_fails_alone_and_the_run_completes(tmp_path: Path, pytestconfig):
    proc, junit = _run(
        tmp_path,
        {
            "test_a.py": "def test_a():\n    pass\n",
            "test_b.py": "import time\n\ndef test_slow():\n    time.sleep(30)\n",
            "test_c.py": "def test_c():\n    pass\n",
        },
        _flags(pytestconfig),
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0
    assert "node down" not in out and "crashed" not in out, out
    results = {}
    for case in ET.parse(junit).getroot().iter("testcase"):
        bad = case.find("failure") if case.find("failure") is not None else case.find("error")
        results[case.get("name")] = bad
    assert set(results) == {"test_a", "test_slow", "test_c"}, out
    assert results["test_a"] is None and results["test_c"] is None
    assert "Timeout" in (results["test_slow"].get("message") or "") + (results["test_slow"].text or "")


def test_a_killed_worker_ends_the_run_non_zero_naming_it(tmp_path: Path, pytestconfig):
    proc, _ = _run(
        tmp_path,
        {
            "test_a.py": "def test_a():\n    pass\n",
            "test_b.py": "import os, signal\n\ndef test_die():\n    os.kill(os.getpid(), signal.SIGKILL)\n",
            "test_c.py": "def test_c():\n    pass\n",
        },
        _flags(pytestconfig),
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert "gw" in out and ("crashed" in out or "node down" in out), out
