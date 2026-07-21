"""Tests for /prawduct:repo-disable — the per-repo plugin-disable toggle.

Two surfaces:
  * `lib.repo_toggle.set_repo_disabled` — the safe settings merge (preserve every
    other key; abort, never clobber, on malformed JSON; idempotent).
  * `prawduct-hook repo-disable` — the CLI the skill calls (dry-run/apply/json),
    whose applied output MUST carry the take-effect-on-reload + manual-re-enable
    guidance (there is no enable counterpart, so dropping it silently strands users).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from lib.repo_toggle import PLUGIN_ID, set_repo_disabled  # noqa: E402

PROJECT_FILE = ".claude/settings.json"
LOCAL_FILE = ".claude/settings.local.json"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# =============================================================================
# lib.repo_toggle.set_repo_disabled — the merge
# =============================================================================


class TestSetRepoDisabledFreshRepo:
    def test_apply_creates_committed_settings(self, tmp_path):
        result = set_repo_disabled(tmp_path, apply=True)
        assert result["applied"] is True
        assert result["scope"] == "project"
        assert result["target"] == PROJECT_FILE
        assert result["file_existed"] is False
        assert result["previous_value"] is None
        data = _read(tmp_path / PROJECT_FILE)
        assert data == {"enabledPlugins": {PLUGIN_ID: False}}

    def test_local_scope_targets_gitignored_file(self, tmp_path):
        result = set_repo_disabled(tmp_path, local=True, apply=True)
        assert result["scope"] == "local"
        assert result["target"] == LOCAL_FILE
        assert (tmp_path / LOCAL_FILE).is_file()
        # The committed file is NOT created for a local-scope disable.
        assert not (tmp_path / PROJECT_FILE).exists()

    def test_dry_run_writes_nothing(self, tmp_path):
        result = set_repo_disabled(tmp_path, apply=False)
        assert result["applied"] is False
        assert result["change_needed"] is True
        assert not (tmp_path / PROJECT_FILE).exists(), "dry run must not write"


class TestSetRepoDisabledPreservesSettings:
    def _seed(self, tmp_path, payload: dict) -> Path:
        path = tmp_path / PROJECT_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path

    def test_unrelated_keys_preserved(self, tmp_path):
        self._seed(
            tmp_path,
            {
                "permissions": {"allow": ["Bash(ls *)"]},
                "env": {"FOO": "bar"},
                "extraKnownMarketplaces": {"prawduct": {"source": "x"}},
            },
        )
        set_repo_disabled(tmp_path, apply=True)
        data = _read(tmp_path / PROJECT_FILE)
        # Everything kept; only enabledPlugins added.
        assert data["permissions"] == {"allow": ["Bash(ls *)"]}
        assert data["env"] == {"FOO": "bar"}
        assert data["extraKnownMarketplaces"] == {"prawduct": {"source": "x"}}
        assert data["enabledPlugins"][PLUGIN_ID] is False

    def test_flips_existing_true_and_keeps_sibling_plugins(self, tmp_path):
        self._seed(
            tmp_path,
            {"enabledPlugins": {PLUGIN_ID: True, "other@mkt": True}},
        )
        result = set_repo_disabled(tmp_path, apply=True)
        assert result["previous_value"] is True
        data = _read(tmp_path / PROJECT_FILE)
        assert data["enabledPlugins"][PLUGIN_ID] is False
        assert data["enabledPlugins"]["other@mkt"] is True, "sibling plugin dropped"

    def test_previous_value_none_when_no_enabled_plugins_key(self, tmp_path):
        self._seed(tmp_path, {"env": {"A": "1"}})
        result = set_repo_disabled(tmp_path, apply=False)
        assert result["previous_value"] is None
        assert result["change_needed"] is True


class TestSetRepoDisabledIdempotent:
    def test_already_false_is_noop(self, tmp_path):
        path = tmp_path / PROJECT_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        original = json.dumps({"enabledPlugins": {PLUGIN_ID: False}}, indent=2) + "\n"
        path.write_text(original, encoding="utf-8")
        result = set_repo_disabled(tmp_path, apply=True)
        assert result["already_disabled"] is True
        assert result["change_needed"] is False
        assert result["applied"] is False
        assert path.read_text(encoding="utf-8") == original, "no-op must not rewrite the file"


class TestSetRepoDisabledNeverClobbers:
    def test_malformed_json_aborts_without_writing(self, tmp_path):
        path = tmp_path / PROJECT_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{ this is not json", encoding="utf-8")
        result = set_repo_disabled(tmp_path, apply=True)
        assert "error" in result
        assert result.get("applied") is not True, "an abort must not report a write"
        assert path.read_text(encoding="utf-8") == "{ this is not json", "must not overwrite"

    def test_non_object_json_aborts(self, tmp_path):
        path = tmp_path / PROJECT_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("[1, 2, 3]", encoding="utf-8")
        result = set_repo_disabled(tmp_path, apply=True)
        assert "error" in result
        assert path.read_text(encoding="utf-8") == "[1, 2, 3]"


# =============================================================================
# prawduct-hook repo-disable — the CLI the skill calls
# =============================================================================


def _run(project_dir: Path, *args: str) -> subprocess.CompletedProcess:
    home = project_dir.parent / "_home"
    home.mkdir(exist_ok=True)
    env = {
        "HOME": str(home),
        "CLAUDE_PROJECT_DIR": str(project_dir),
        "CLAUDE_PLUGIN_ROOT": str(ROOT),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    return subprocess.run(
        ["python3", str(HOOK), "repo-disable", *args],
        capture_output=True, text=True, env=env, timeout=20,
    )


class TestRepoDisableCli:
    def test_dry_run_json_plan(self, tmp_path):
        r = _run(tmp_path, "--json")
        assert r.returncode == 0, r.stderr
        plan = json.loads(r.stdout)
        assert plan["scope"] == "project"
        assert plan["change_needed"] is True
        assert plan["applied"] is False
        assert not (tmp_path / PROJECT_FILE).exists()

    def test_apply_writes_and_emits_reenable_guidance(self, tmp_path):
        r = _run(tmp_path, "--apply")
        assert r.returncode == 0, r.stderr
        assert _read(tmp_path / PROJECT_FILE)["enabledPlugins"][PLUGIN_ID] is False
        # The applied output must carry the load-bearing guidance — there is no
        # /prawduct:repo-enable, so this text is the user's only re-enable path.
        out = r.stdout
        assert "/reload-plugins" in out
        assert "true" in out and PLUGIN_ID in out, "must show how to re-enable"
        assert PROJECT_FILE in out

    def test_apply_local_scope(self, tmp_path):
        r = _run(tmp_path, "--local", "--apply")
        assert r.returncode == 0, r.stderr
        assert (tmp_path / LOCAL_FILE).is_file()
        assert LOCAL_FILE in r.stdout

    def test_malformed_settings_exits_nonzero(self, tmp_path):
        path = tmp_path / PROJECT_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{ broken", encoding="utf-8")
        r = _run(tmp_path, "--apply")
        assert r.returncode == 1
        assert path.read_text(encoding="utf-8") == "{ broken"
