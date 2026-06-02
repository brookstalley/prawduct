"""Tests for the v2.0.0 version-delta banner + new-gate attribution (Chunk 7).

The banner is the *safety net* for always-latest distribution (design §5/§5a):
because the plugin auto-updates, every version move must be VISIBLE.

  * **Unit** — the pure parse/range/render helpers in hooks/banner.py against the
    real bundled CHANGELOG.md + hooks/gates.json, plus synthetic inputs for the
    range math (highlights and new-gate selection over (last, current]).
  * **Behavioral** — banner.py executed as a subprocess with CLAUDE_PLUGIN_ROOT +
    CLAUDE_PROJECT_DIR: first run records the marker quietly, an unchanged
    version stays quiet, a bumped version prints `vX → vY` + a highlight and
    advances the marker, and the ONLY thing written is the gitignored marker
    under .prawduct/ (the §2 write-isolation + no-noise guarantee).
  * **Attribution** — the Stop hook's blocking messages name the version + gate
    (design §5a), via helpers imported from bin/prawduct-hook.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BANNER = ROOT / "hooks" / "banner.py"
GATES_JSON = ROOT / "hooks" / "gates.json"
CHANGELOG = ROOT / "CHANGELOG.md"
HOOK = ROOT / "bin" / "prawduct-hook"
PLUGIN_VERSION = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())["version"]


@pytest.fixture(scope="module")
def banner():
    """Import hooks/banner.py as a module (its main() runs only under __main__)."""
    spec = importlib.util.spec_from_file_location("prawduct_banner", BANNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def hook_mod():
    """Import bin/prawduct-hook (no .py extension) for its attribution helpers."""
    loader = SourceFileLoader("prawduct_hook_under_test", str(HOOK))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def _run_banner(plugin_root: Path, project_dir: Path | None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    env.pop("CLAUDE_PROJECT_DIR", None)
    if project_dir is not None:
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, str(BANNER)], capture_output=True, text=True, env=env, timeout=20
    )


def _repo(tmp_path: Path) -> Path:
    prawduct = tmp_path / ".prawduct"
    prawduct.mkdir()
    return prawduct


# =============================================================================
# Bundled data — CHANGELOG.md + gates.json are well-formed
# =============================================================================


class TestBundledData:
    def test_changelog_has_current_version_entry(self, banner):
        pairs = dict(banner.parse_changelog(ROOT))
        assert PLUGIN_VERSION in pairs, f"CHANGELOG.md must carry the current version {PLUGIN_VERSION}"
        assert pairs[PLUGIN_VERSION], "the current version's changelog headline must be non-empty"

    def test_gates_json_well_formed(self):
        data = json.loads(GATES_JSON.read_text())
        gates = data["gates"]
        assert {g["id"] for g in gates} >= {"reflection", "critic", "pr", "trivial"}
        for g in gates:
            assert g["name"] and g["since"] and g["summary"]
            parts = g["since"].split(".")
            assert len(parts) == 3 and all(p.isdigit() for p in parts), g

    def test_parse_gates_reads_registry(self, banner):
        ids = {g["id"] for g in banner.parse_gates(ROOT)}
        assert {"reflection", "critic", "pr", "trivial"} <= ids


# =============================================================================
# Unit — version math, highlight + new-gate range selection
# =============================================================================


class TestVersionMath:
    def test_version_tuple_orders(self, banner):
        assert banner.version_tuple("1.8.0") < banner.version_tuple("1.8.1")
        assert banner.version_tuple("1.8.1") < banner.version_tuple("2.0.0")
        assert banner.version_tuple("garbage") == (-1,)  # sorts below everything

    def test_highlights_select_open_lower_closed_upper(self, banner):
        cl = [("1.8.1", "patch"), ("1.8.0", "minor"), ("1.7.0", "old")]
        picked = banner.highlights_in_range(cl, "1.7.0", "1.8.1")
        # (1.7.0, 1.8.1] excludes 1.7.0, includes 1.8.0 and 1.8.1, newest first
        assert [v for v, _ in picked] == ["1.8.1", "1.8.0"]

    def test_highlights_empty_on_same_version(self, banner):
        cl = [("1.8.1", "patch")]
        assert banner.highlights_in_range(cl, "1.8.1", "1.8.1") == []

    def test_highlights_empty_on_downgrade(self, banner):
        cl = [("1.8.1", "patch"), ("1.8.0", "minor")]
        assert banner.highlights_in_range(cl, "1.8.1", "1.8.0") == []

    def test_new_gates_in_range(self, banner):
        gates = [
            {"id": "old", "name": "old", "since": "1.0.0", "summary": "s"},
            {"id": "mid", "name": "mid", "since": "1.5.0", "summary": "s"},
            {"id": "new", "name": "new", "since": "2.1.0", "summary": "s"},
        ]
        # crossing 2.0.0 -> 2.1.0 surfaces only the gate introduced in 2.1.0
        picked = banner.new_gates_in_range(gates, "2.0.0", "2.1.0")
        assert [g["id"] for g in picked] == ["new"]
        # a foundational gate surfaces when its introduction is freshly crossed
        assert [g["id"] for g in banner.new_gates_in_range(gates, "1.0.0", "1.5.0")] == ["mid"]

    def test_render_delta_includes_arrow_and_highlight(self, banner):
        lines = banner.render_delta("1.8.0", "1.8.1", ROOT)
        assert lines[0] == "↑ Prawduct updated: v1.8.0 → v1.8.1"
        assert any(line.startswith("  • ") for line in lines), "expected a changelog highlight"

    def test_render_delta_announces_new_gate(self, banner, tmp_path):
        # A synthetic plugin root whose gates.json introduces a gate in 2.1.0.
        root = tmp_path / "plugin"
        (root / "hooks").mkdir(parents=True)
        (root / "CHANGELOG.md").write_text("# CL\n\n## v2.1.0\nNew release.\n")
        (root / "hooks" / "gates.json").write_text(json.dumps({"gates": [
            {"id": "cumulative-critic", "name": "cumulative-critic", "since": "2.1.0",
             "summary": "PR bundle review required"}
        ]}))
        lines = banner.render_delta("2.0.0", "2.1.0", root)
        assert any("new gate" in line and "cumulative-critic" in line for line in lines)


# =============================================================================
# Behavioral — marker lifecycle + write isolation
# =============================================================================


class TestBannerBehavior:
    def test_identity_line_always_prints(self, tmp_path):
        prawduct = _repo(tmp_path)
        r = _run_banner(ROOT, tmp_path)
        assert r.returncode == 0, r.stderr
        assert f"Prawduct v{PLUGIN_VERSION}" in r.stdout

    def test_first_run_records_marker_quietly(self, tmp_path):
        prawduct = _repo(tmp_path)
        r = _run_banner(ROOT, tmp_path)
        assert r.returncode == 0, r.stderr
        assert "→" not in r.stdout, "first run has no prior version to diff against"
        assert (prawduct / ".prawduct-version").read_text().strip() == PLUGIN_VERSION

    def test_same_version_is_quiet(self, tmp_path):
        prawduct = _repo(tmp_path)
        (prawduct / ".prawduct-version").write_text(PLUGIN_VERSION + "\n")
        r = _run_banner(ROOT, tmp_path)
        assert r.returncode == 0, r.stderr
        assert "→" not in r.stdout
        assert "updated:" not in r.stdout

    def test_bumped_version_shows_delta_and_advances_marker(self, tmp_path):
        prawduct = _repo(tmp_path)
        (prawduct / ".prawduct-version").write_text("1.8.0\n")
        r = _run_banner(ROOT, tmp_path)
        assert r.returncode == 0, r.stderr
        assert f"v1.8.0 → v{PLUGIN_VERSION}" in r.stdout
        assert "  • " in r.stdout, "expected at least one changelog highlight"
        # marker advanced so the next session is quiet
        assert (prawduct / ".prawduct-version").read_text().strip() == PLUGIN_VERSION

    def test_no_prawduct_dir_is_identity_only_no_crash(self, tmp_path):
        # tmp_path has no .prawduct/
        r = _run_banner(ROOT, tmp_path)
        assert r.returncode == 0, r.stderr
        assert f"Prawduct v{PLUGIN_VERSION}" in r.stdout
        assert not (tmp_path / ".prawduct").exists()

    def test_no_project_dir_writes_nothing(self, tmp_path):
        # Without CLAUDE_PROJECT_DIR the marker logic is skipped entirely, so a
        # bare run never mutates whatever repo happens to be cwd.
        prawduct = _repo(tmp_path)
        r = _run_banner(ROOT, project_dir=None)
        assert r.returncode == 0, r.stderr
        assert f"Prawduct v{PLUGIN_VERSION}" in r.stdout
        assert not (prawduct / ".prawduct-version").exists()

    def test_writes_only_the_marker(self, tmp_path):
        project = tmp_path / "repo"
        project.mkdir()
        prawduct = project / ".prawduct"
        prawduct.mkdir()
        (project / "app.py").write_text("print('hi')\n")
        (prawduct / "project-state.yaml").write_text("backlog_format_version: 2\n")
        (prawduct / ".prawduct-version").write_text("1.8.0\n")

        def snapshot() -> dict[str, bytes]:
            return {
                str(p.relative_to(project)): p.read_bytes()
                for p in project.rglob("*")
                if p.is_file() and p.name != ".prawduct-version"
            }

        before = snapshot()
        r = _run_banner(ROOT, project)
        after = snapshot()
        assert r.returncode == 0, r.stderr
        assert before == after, "banner wrote outside the version marker"
        assert (prawduct / ".prawduct-version").read_text().strip() == PLUGIN_VERSION

    def test_corrupt_manifest_degrades_gracefully(self, tmp_path):
        root = tmp_path / "plugin"
        (root / ".claude-plugin").mkdir(parents=True)
        (root / ".claude-plugin" / "plugin.json").write_text("{ not json")
        r = _run_banner(root, tmp_path)
        assert r.returncode == 0  # never breaks session start
        assert "NOTE: Prawduct banner could not read plugin version" in r.stderr


# =============================================================================
# Attribution — Stop-hook block messages name version + gate (design §5a)
# =============================================================================


class TestGateAttributionHelpers:
    def test_attribution_names_version_and_gate(self, hook_mod):
        reg = hook_mod._load_gate_registry()
        out = hook_mod._gate_attribution("critic", reg, "2.0.0")
        assert "prawduct v2.0.0" in out and "gate: critic-review" in out

    def test_attribution_flags_new_gate_when_since_equals_current(self, hook_mod):
        reg = {"foo": {"id": "foo", "name": "foo-gate", "since": "2.1.0", "summary": "s"}}
        out = hook_mod._gate_attribution("foo", reg, "2.1.0")
        assert "NEW this release (v2.1.0)" in out

    def test_attribution_falls_back_when_registry_empty(self, hook_mod):
        out = hook_mod._gate_attribution("critic", {}, "2.0.0")
        assert "gate: critic" in out  # bare id, no crash

    def test_attribution_handles_missing_version(self, hook_mod):
        out = hook_mod._gate_attribution("critic", hook_mod._load_gate_registry(), None)
        assert "gate: critic-review" in out and "v" not in out.split("gate:")[0].replace("prawduct", "")

    def test_load_registry_reads_real_gates(self, hook_mod):
        reg = hook_mod._load_gate_registry()
        assert reg["critic"]["name"] == "critic-review"
        assert reg["reflection"]["since"] == "1.0.0"

    def test_manifest_version_matches_file(self, hook_mod):
        assert hook_mod._plugin_manifest_version() == PLUGIN_VERSION
