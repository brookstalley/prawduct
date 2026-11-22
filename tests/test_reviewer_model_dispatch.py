"""The reviewer's model reaches the dispatcher from code, at the commands it
already runs to dispatch.

`critic-begin --session-model <id>` writes the answer of
`model_tier.reviewer_model_for` into the dispatch manifest as `reviewer_model`
and prints it. The dispatch prose passes what it prints and never names a model
itself (`tests/preferences/test_reviewer_model_dispatch_prose.py`). (The PR
reviewer's dispatch mark printed the same answer until that reviewer was
retired, #1129; the Critic's is now the one reviewer dispatch.)

Absent the flag, the dispatcher has not said what it runs on, so the cap
applies and a note on stderr says it was assumed. `--tier` is telemetry and
never moves the answer.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import critic_consolidate, model_tier  # noqa: E402

MANIFEST_REL = ".prawduct/.critic-partials/manifest.json"


def _git_env(repo: Path) -> dict[str, str]:
    home = repo.parent / "_home"
    home.mkdir(exist_ok=True)
    return {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True,
        env=_git_env(repo), check=True, timeout=10,
    )


def _repo_with_dirty_change(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--quiet", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "config", "maintenance.auto", "false")
    (repo / ".prawduct").mkdir()
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("x = 1\n")
    _git(repo, "add", "src")
    _git(repo, "commit", "-m", "init", "--quiet")
    (repo / "src" / "app.py").write_text("x = 2\n")
    return repo


def _run_hook(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK), *args],
        cwd=str(repo), capture_output=True, text=True,
        env={**_git_env(repo), "CLAUDE_PLUGIN_ROOT": str(ROOT), "CLAUDE_PROJECT_DIR": str(repo)},
        timeout=30,
    )


def _begin(repo: Path, *args: str) -> tuple[subprocess.CompletedProcess, dict]:
    result = _run_hook(repo, "critic-begin", "--mode", "chunk", *args)
    assert result.returncode == 0, result.stderr
    return result, json.loads((repo / MANIFEST_REL).read_text())


def _printed_answer(stdout: str) -> str:
    """The value on the one stdout line that carries the answer."""
    lines = [ln for ln in stdout.splitlines() if "reviewer model: " in ln]
    assert len(lines) == 1, f"expected one reviewer-model line, got {lines!r}"
    return lines[0].split("reviewer model: ", 1)[1].split(" ", 1)[0]


ABOVE_IDS = ["fable", "claude-fable-1", "claude-fable-1[1m]", "claude-mystery-9"]
AT_OR_BELOW_IDS = [
    "haiku", "sonnet", "opus",
    "claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-5-5",
    "claude-haiku-4-5[1m]", "claude-sonnet-4-6[1m]", "claude-opus-4-8[1m]",
]


class TestCriticBeginWritesTheReviewerModel:
    @pytest.mark.parametrize("session_model", ABOVE_IDS)
    def test_a_session_above_the_ceiling_is_capped(self, tmp_path, session_model):
        repo = _repo_with_dirty_change(tmp_path)
        result, manifest = _begin(repo, "--session-model", session_model)
        assert manifest["reviewer_model"] == model_tier.CEILING_ALIAS
        assert _printed_answer(result.stdout) == model_tier.CEILING_ALIAS
        assert "--session-model" not in result.stderr, "the flag was given; nothing was assumed"

    @pytest.mark.parametrize("session_model", AT_OR_BELOW_IDS)
    def test_a_session_at_or_below_the_ceiling_gets_no_override(self, tmp_path, session_model):
        repo = _repo_with_dirty_change(tmp_path)
        result, manifest = _begin(repo, "--session-model", session_model)
        assert "reviewer_model" in manifest, "the answer is recorded even when it is none"
        assert manifest["reviewer_model"] is None
        assert _printed_answer(result.stdout) == "none"

    def test_an_absent_flag_is_capped_and_says_it_assumed(self, tmp_path):
        repo = _repo_with_dirty_change(tmp_path)
        result, manifest = _begin(repo)
        assert manifest["reviewer_model"] == model_tier.CEILING_ALIAS
        assert _printed_answer(result.stdout) == model_tier.CEILING_ALIAS
        notes = [ln for ln in result.stderr.splitlines() if "--session-model" in ln]
        assert len(notes) == 1, result.stderr
        assert notes[0].startswith("PRAWDUCT NOTE: ")
        assert "assumed" in notes[0]

    @pytest.mark.parametrize("tier", ["escalate", "standard"])
    @pytest.mark.parametrize(
        "session_model, expected",
        [("claude-sonnet-4-6", None), ("claude-fable-1", "opus")],
    )
    def test_the_tier_never_moves_the_answer(self, tmp_path, tier, session_model, expected):
        repo = _repo_with_dirty_change(tmp_path)
        _, manifest = _begin(repo, "--tier", tier, "--session-model", session_model)
        assert manifest["tier"] == tier, "control: the tier did reach the manifest"
        assert manifest["reviewer_model"] == expected

    def test_an_empty_session_model_says_the_cap_was_assumed(self, tmp_path):
        """Ported from the retired PR dispatch mark: an empty value is no answer
        about the session's model, so the cap applies and the note says so."""
        repo = _repo_with_dirty_change(tmp_path)
        result, manifest = _begin(repo, "--session-model", "")
        assert manifest["reviewer_model"] == model_tier.CEILING_ALIAS
        assert _printed_answer(result.stdout) == model_tier.CEILING_ALIAS
        assert "--session-model" in result.stderr and "assumed" in result.stderr

    def test_the_flag_requires_a_value(self, tmp_path):
        repo = _repo_with_dirty_change(tmp_path)
        result = _run_hook(repo, "critic-begin", "--mode", "chunk", "--session-model")
        assert result.returncode == 1
        assert "--session-model requires a value" in result.stderr
        assert not (repo / MANIFEST_REL).exists()


class TestTheManifestFieldValidates:
    def _valid(self, tmp_path) -> dict:
        repo = _repo_with_dirty_change(tmp_path)
        _, manifest = _begin(repo, "--session-model", "claude-fable-1")
        return manifest

    def test_a_written_manifest_validates(self, tmp_path):
        ok, reason = critic_consolidate.validate_manifest(self._valid(tmp_path))
        assert ok, reason

    @pytest.mark.parametrize("value", [None, "opus"])
    def test_null_and_an_alias_are_accepted(self, tmp_path, value):
        manifest = {**self._valid(tmp_path), "reviewer_model": value}
        assert critic_consolidate.validate_manifest(manifest)[0]

    def test_a_manifest_from_before_the_field_still_validates(self, tmp_path):
        manifest = self._valid(tmp_path)
        del manifest["reviewer_model"]
        assert critic_consolidate.validate_manifest(manifest)[0]

    @pytest.mark.parametrize("value", ["", 7, ["opus"]])
    def test_a_malformed_value_is_refused(self, tmp_path, value):
        manifest = {**self._valid(tmp_path), "reviewer_model": value}
        ok, reason = critic_consolidate.validate_manifest(manifest)
        assert not ok
        assert "reviewer_model" in reason
