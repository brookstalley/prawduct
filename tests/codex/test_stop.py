"""Recorded Codex Stop shapes and the reflection-only boundary."""

from __future__ import annotations

import json
import importlib.machinery
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "adapters" / "codex" / "stop.py"
PLUGIN = REPO / "plugin"
UNCOVERED = (
    "critic", "pr", "learnings-unmigrated", "learnings-budget",
    "clear-verdict", "clear-reason",
)


def _repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "develop"], cwd=repo, check=True)
    (repo / "code.py").write_text("value = 1\n")
    subprocess.run(["git", "add", "code.py"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test",
                    "commit", "-qm", "Fixture base"], cwd=repo, check=True)
    (repo / ".prawduct").mkdir()
    tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=repo, text=True).strip()
    (repo / ".prawduct" / ".session-base-tree").write_text(tree)
    (repo / "code.py").write_text("value = 2\n")
    return repo


def _fire(repo, payload):
    env = os.environ.copy()
    env["PRAWDUCT_CANONICAL_PLUGIN_ROOT"] = str(PLUGIN)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, str(SCRIPT)], input=json.dumps({"cwd": str(repo), **payload}),
        capture_output=True, text=True, cwd=repo, env=env, timeout=120,
    )


def _assert_uncovered(text):
    for gate in UNCOVERED:
        assert f"{gate}: not covered by the experimental Codex Phase 1 spike" in text


@pytest.mark.parametrize("payload", [
    {"session_id": "0199", "turn_id": "turn-1", "last_assistant_message": None},
    {"session_id": "0199", "stop_hook_active": True},
])
def test_reflection_repeats_until_marker_changes(tmp_path, payload):
    repo = _repo(tmp_path)
    for _ in range(2):
        result = _fire(repo, payload)
        assert result.returncode == 2
        assert not result.stdout
        assert "REFLECTION:" in result.stderr
        _assert_uncovered(result.stderr)
    (repo / ".prawduct" / ".session-reflected").write_text(
        "Expected value 1; actual value 2. No defect; the fixture deliberately changed code.\n"
    )
    result = _fire(repo, payload)
    assert result.returncode == 0, result.stderr
    advisory = json.loads(result.stdout)["systemMessage"]
    _assert_uncovered(advisory)
    assert "REFLECTION:" not in advisory


def test_waiver_and_background_deferral_are_visible(tmp_path):
    repo = _repo(tmp_path)
    result = _fire(repo, {"background_tasks": [{"type": "agent", "name": "fixture"}]})
    assert result.returncode == 0
    assert "REFLECTION DEFERRED" in json.loads(result.stdout)["systemMessage"]
    (repo / ".prawduct" / ".gates-waived").write_text('{"reflection": "fixture waiver"}')
    result = _fire(repo, {})
    assert result.returncode == 0
    assert "reflection: waived (fixture waiver)" in json.loads(result.stdout)["systemMessage"]


def test_missing_canonical_root_blocks_with_stderr(tmp_path):
    repo = _repo(tmp_path)
    env = os.environ.copy()
    env["PRAWDUCT_CANONICAL_PLUGIN_ROOT"] = str(tmp_path / "missing")
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], input=json.dumps({"cwd": str(repo)}),
        capture_output=True, text=True, cwd=repo, env=env,
    )
    assert result.returncode == 2
    assert "unavailable" in result.stderr
    assert not result.stdout


def test_unhandled_core_error_blocks_with_exit_two(monkeypatch, capsys):
    hook = PLUGIN / "bin" / "prawduct-hook"
    loader = importlib.machinery.SourceFileLoader("prawduct_codex_error_fixture", str(hook))
    spec = importlib.util.spec_from_loader("prawduct_codex_error_fixture", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    monkeypatch.setenv("PRAWDUCT_HOST", "codex")
    monkeypatch.setattr(sys, "argv", [str(hook), "stop"])
    monkeypatch.setattr(module, "_dispatch", lambda: (_ for _ in ()).throw(RuntimeError("fixture failure")))
    assert module.main() == 2
    assert "Codex Stop core error: RuntimeError: fixture failure" in capsys.readouterr().err


def test_registration_uses_installed_adapter_root():
    registration = json.loads((SCRIPT.parent / "hooks" / "hooks.json").read_text())
    command = registration["hooks"]["Stop"][0]["hooks"][0]["command"]
    assert command == 'python3 "${PLUGIN_ROOT}/stop.py"'


def test_ungoverned_stop_still_names_uncovered_gates(tmp_path):
    repo = tmp_path / "ungoverned"
    repo.mkdir()
    result = _fire(repo, {"last_assistant_message": None})
    assert result.returncode == 0
    _assert_uncovered(json.loads(result.stdout)["systemMessage"])


@pytest.mark.parametrize("host_source,error", [
    ('raise RuntimeError("broken host import")\n', "RuntimeError"),
    ("def broken(:\n", "SyntaxError"),
])
def test_host_import_failure_still_blocks(tmp_path, host_source, error):
    plugin = tmp_path / "broken-plugin"
    for name in ("lib/host.py", "hooks/banner.py", "hooks/digest.py",
                 "bin/prawduct-hook", "methodology/session-digest.md"):
        path = plugin / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(host_source if name == "lib/host.py" else "")
    env = os.environ.copy()
    env["PRAWDUCT_CANONICAL_PLUGIN_ROOT"] = str(plugin)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], input=json.dumps({"cwd": str(tmp_path)}),
        capture_output=True, text=True, cwd=tmp_path, env=env, timeout=120,
    )
    assert result.returncode == 2, result.stderr
    assert not result.stdout
    assert f"experimental Codex Stop entry error: {error}" in result.stderr
    assert "Traceback" not in result.stderr
