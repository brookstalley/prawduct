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
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent / "plugin"
PLUGIN_MANIFEST = ROOT / ".claude-plugin" / "plugin.json"
HOOKS_JSON = ROOT / "hooks" / "hooks.json"
BANNER = ROOT / "hooks" / "banner.py"
PING_SKILL = ROOT / "skills" / "ping" / "SKILL.md"
ALL_SKILLS = sorted((ROOT / "skills").glob("*/SKILL.md"))


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
        # Bare major.minor.patch, or the one permitted prerelease form: a
        # `-dev` / `-dev.N` suffix, which develop carries between releases so
        # the verdict cache's version key and the session banner distinguish a
        # prerelease plugin from the release it precedes. Releases stay bare
        # because the runbook's step 7 overwrites all three version files with
        # the bare number — that is the only PREVENTIVE control.
        # `check_version_files` compares against `git show <tag>:…`, so it runs
        # after the tag exists: it detects a `-dev` residue that shipped, it
        # cannot stop one.
        version = manifest["version"]
        base, dash, prerelease = version.partition("-")
        parts = base.split(".")
        assert len(parts) == 3 and all(p.isdigit() for p in parts), (
            f"version must be semver major.minor.patch, got {version!r}"
        )
        if dash:
            assert re.fullmatch(r"dev(\.\d+)?", prerelease), (
                f"the only permitted prerelease suffix is -dev or -dev.N, got {version!r}"
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


class TestAllPluginSkillFrontmatter:
    """Every plugin skill must carry *parseable* YAML frontmatter with a
    non-empty description — the loader silently drops ALL fields when the
    frontmatter fails to parse, so a skill with a broken header loads
    unusable. Regression guard for the Chunk-6 defect (discovery / planning /
    reflection had an unquoted ``: `` colon-space in the description scalar,
    which YAML reads as a nested mapping → parse error → empty metadata). It
    was invisible to the suite and only surfaced via ``claude plugin
    validate`` during the Chunk-11 dogfood; this test makes the loader's own
    parse a CI invariant.
    """

    def test_skills_directory_is_populated(self):
        names = {p.parent.name for p in ALL_SKILLS}
        # Core skills must be in scope of this guard. (The original trio the
        # Chunk-6 bug broke — discovery/planning/reflection delegators — was
        # folded into /prawduct:methodology by the prose-diet.)
        assert {"methodology", "critic", "backlog"} <= names

    @pytest.mark.parametrize("skill", ALL_SKILLS, ids=lambda p: p.parent.name)
    def test_frontmatter_parses_with_nonempty_description(self, skill):
        text = skill.read_text(encoding="utf-8")
        assert text.startswith("---"), f"{skill} must open with YAML frontmatter"
        parts = text.split("---", 2)
        assert len(parts) >= 3, f"{skill} frontmatter is not closed with ---"
        front = yaml.safe_load(parts[1])  # raises on the colon-space bug
        assert isinstance(front, dict), f"{skill} frontmatter is not a YAML mapping"
        desc = front.get("description")
        assert isinstance(desc, str) and desc.strip(), (
            f"{skill} frontmatter must declare a non-empty description"
        )
