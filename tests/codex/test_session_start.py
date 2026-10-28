"""Recorded Codex SessionStart shapes and the experimental boundary contract."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "adapters" / "codex" / "session_start.py"
CANONICAL_PLUGIN = REPO / "plugin"


def test_registration_uses_installed_adapter_root():
    registration = json.loads((SCRIPT.parent / "hooks" / "hooks.json").read_text())
    command = registration["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert command == 'python3 "${PLUGIN_ROOT}/session_start.py"'
    assert "PRAWDUCT_CANONICAL_PLUGIN_ROOT" in SCRIPT.read_text()


def _repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "develop"], cwd=repo, check=True)
    (repo / ".prawduct").mkdir()
    core = repo / ".claude" / "rules" / "learnings"
    core.mkdir(parents=True)
    (core / "core.md").write_text("- Keep the current project rules.\n")
    return repo


def _fire(repo, tmp_path, source, *, script=SCRIPT, canonical_root=None,
          expect_unavailable=False):
    env = os.environ.copy()
    env["CODEX_HOME"] = str(tmp_path / "codex-home")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PLUGIN_ROOT"] = str(script.parent)
    env.pop("PRAWDUCT_CANONICAL_PLUGIN_ROOT", None)
    if canonical_root is not None:
        env["PRAWDUCT_CANONICAL_PLUGIN_ROOT"] = str(canonical_root)
    payload = {"session_id": "0199-test", "cwd": str(repo)}
    if source is not None:
        payload["source"] = source
    result = subprocess.run(
        [sys.executable, str(script)], input=json.dumps(payload),
        capture_output=True, text=True, cwd=repo, env=env, timeout=120,
    )
    if expect_unavailable:
        assert result.returncode == 1
        assert not result.stdout
        return result.stderr
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]


def _isolated_script(tmp_path):
    root = tmp_path / "isolated-codex-plugin"
    root.mkdir()
    script = root / "session_start.py"
    script.write_bytes(SCRIPT.read_bytes())
    (root / "observation.py").write_bytes((SCRIPT.parent / "observation.py").read_bytes())
    return script


def test_isolated_plugin_uses_explicit_canonical_root(tmp_path):
    repo = _repo(tmp_path)
    output = _fire(repo, tmp_path, "startup", script=_isolated_script(tmp_path),
                   canonical_root=CANONICAL_PLUGIN)
    assert output.startswith("Prawduct experimental Codex Phase 1")
    assert "═══ Prawduct v" in output
    assert "Keep the current project rules" in output
    assert (repo / ".prawduct" / ".session-start").exists()


@pytest.mark.parametrize("canonical_root", [None, "/missing/prawduct/plugin", "relative/plugin"])
def test_isolated_plugin_without_valid_canonical_root_refuses(tmp_path, canonical_root):
    repo = _repo(tmp_path)
    before = sorted(p.name for p in (repo / ".prawduct").iterdir())
    output = _fire(repo, tmp_path, "startup", script=_isolated_script(tmp_path),
                   canonical_root=canonical_root, expect_unavailable=True)
    assert "canonical plugin root missing or invalid" in output
    assert "no session state changed" in output
    assert sorted(p.name for p in (repo / ".prawduct").iterdir()) == before


@pytest.mark.parametrize("source,boundary", [
    ("startup", True), ("clear", True), ("resume", False), ("compact", False),
])
def test_recorded_sources_select_boundary_and_inject_core(tmp_path, source, boundary):
    repo = _repo(tmp_path)
    output = _fire(repo, tmp_path, source)
    assert output.startswith("Prawduct experimental Codex Phase 1")
    assert "Keep the current project rules" in output
    assert "═══ Prawduct v" in output
    assert (repo / ".prawduct" / ".session-start").exists() == boundary
    if not boundary:
        # The canonical clear hook prints this notice to stderr; the adapter
        # must carry it into Codex's model-facing SessionStart context.
        assert "no .prawduct/.session-base-tree" in output


@pytest.mark.parametrize("source", [None, "fork", "something-new"])
def test_unverified_source_refuses_before_state_writes(tmp_path, source):
    repo = _repo(tmp_path)
    before = sorted(p.name for p in (repo / ".prawduct").iterdir())
    output = _fire(repo, tmp_path, source)
    assert "refused" in output
    assert sorted(p.name for p in (repo / ".prawduct").iterdir()) == before


def test_overflow_notice_is_first(tmp_path):
    spec = importlib.util.spec_from_file_location("codex_session_start", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = module._context([module.EXPERIMENTAL, "x" * 25000])
    assert output.startswith("Prawduct experimental Codex SessionStart context exceeds")
    assert module.EXPERIMENTAL in output
