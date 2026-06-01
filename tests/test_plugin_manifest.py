"""Tests for the v2.0.0 plugin package: manifest, hooks, banner, ping skill (Chunk 1).

These enforce the load-bearing invariants of the thin vertical slice:
  * plugin.json is valid and its ``version`` mirrors the VERSION file — the
    release model (design §5b) makes the version bump the release trigger, so
    plugin.json and VERSION must never drift.
  * hooks/hooks.json declares a SessionStart hook that runs the bundled banner
    via ${CLAUDE_PLUGIN_ROOT}.
  * hooks/banner.py reads the version from the bundled plugin.json and prints it
    (behavioral: the script is actually executed, not just inspected).
  * skills/ping/SKILL.md exists with a description so /prawduct:ping resolves.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_MANIFEST = ROOT / ".claude-plugin" / "plugin.json"
HOOKS_JSON = ROOT / "hooks" / "hooks.json"
BANNER = ROOT / "hooks" / "banner.py"
PING_SKILL = ROOT / "skills" / "ping" / "SKILL.md"


def _env_without_plugin_root(**overrides):
    env = dict(os.environ)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    env.update(overrides)
    return env


@pytest.fixture(scope="module")
def manifest():
    return json.loads(PLUGIN_MANIFEST.read_text(encoding="utf-8"))


class TestPluginManifest:
    def test_manifest_is_valid_json_object(self, manifest):
        assert isinstance(manifest, dict)

    def test_name_is_prawduct(self, manifest):
        # Drives skill namespacing: /prawduct:*
        assert manifest["name"] == "prawduct"

    def test_version_mirrors_VERSION_file(self, manifest):
        version_file = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        assert manifest["version"] == version_file, (
            "plugin.json version must mirror VERSION — the release model "
            "(design §5b) makes the version bump the release trigger; drift "
            "would ship the wrong version or silently skip an update."
        )

    def test_version_is_semver(self, manifest):
        parts = manifest["version"].split(".")
        assert len(parts) == 3 and all(p.isdigit() for p in parts), (
            f"version must be semver major.minor.patch, got {manifest['version']!r}"
        )


class TestHooksJson:
    def test_hooks_json_valid(self):
        data = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
        assert "SessionStart" in data["hooks"]

    def test_sessionstart_runs_bundled_banner(self):
        data = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
        commands = [
            h["command"]
            for entry in data["hooks"]["SessionStart"]
            for h in entry["hooks"]
        ]
        assert any(
            "${CLAUDE_PLUGIN_ROOT}" in c and "banner.py" in c for c in commands
        ), "SessionStart must run the bundled banner via ${CLAUDE_PLUGIN_ROOT}"


class TestBanner:
    def test_banner_prints_version_from_manifest(self, manifest):
        # Behavioral: execute banner.py with CLAUDE_PLUGIN_ROOT set to the repo.
        result = subprocess.run(
            [sys.executable, str(BANNER)],
            capture_output=True,
            text=True,
            env=_env_without_plugin_root(CLAUDE_PLUGIN_ROOT=str(ROOT)),
        )
        assert result.returncode == 0
        assert manifest["version"] in result.stdout

    def test_banner_resolves_root_without_env(self):
        # No CLAUDE_PLUGIN_ROOT -> falls back to hooks/ parent (the repo root).
        result = subprocess.run(
            [sys.executable, str(BANNER)],
            capture_output=True,
            text=True,
            env=_env_without_plugin_root(),
        )
        assert result.returncode == 0
        assert "Prawduct v" in result.stdout

    def test_banner_never_breaks_session_start(self, tmp_path):
        # Missing manifest under CLAUDE_PLUGIN_ROOT -> still exit 0.
        result = subprocess.run(
            [sys.executable, str(BANNER)],
            capture_output=True,
            text=True,
            env=_env_without_plugin_root(CLAUDE_PLUGIN_ROOT=str(tmp_path)),
        )
        assert result.returncode == 0


class TestPingSkill:
    def test_ping_skill_has_description_frontmatter(self):
        text = PING_SKILL.read_text(encoding="utf-8")
        assert text.startswith("---"), "SKILL.md must open with YAML frontmatter"
        front = text.split("---", 2)[1]
        assert "description:" in front, "plugin skill requires a description"
