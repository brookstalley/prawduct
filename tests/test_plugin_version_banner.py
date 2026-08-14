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
import re
import subprocess
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
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
        """The shipped version's headline must exist — and a PRERELEASE is
        satisfied by the release it is a prerelease OF.

        `develop` runs on `X.Y.Z-rc.N` so the version-keyed plugin cache
        re-fetches as it advances. Its content is the upcoming release's, so
        demanding a `## vX.Y.Z-rc.N` section would add a changelog edit to every
        rc bump and leave the file carrying sections for versions nobody ever
        released.
        """
        pairs = dict(banner.parse_changelog(ROOT))
        base = PLUGIN_VERSION.partition("-")[0]
        assert base in pairs, (
            f"CHANGELOG.md must carry {base} (the version {PLUGIN_VERSION} ships as)"
        )
        assert pairs[base], "the current version's changelog headline must be non-empty"

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

    def test_a_prerelease_sorts_below_its_own_release(self, banner):
        """The develop track's ordering. A prerelease parsed as unorderable made
        a dogfooding repo get no banner at all, and made the first real release
        after it replay every headline in the file."""
        vt = banner.version_tuple
        assert vt("3.3.4") < vt("3.4.0-rc.1") < vt("3.4.0-rc.2") < vt("3.4.0")
        assert vt("3.4.0") < vt("3.4.1-rc.1")
        assert vt("3.4.0-rc.1") != (-1,), "a prerelease must PARSE, not fall back"

    def test_a_prerelease_shows_only_the_headlines_it_crossed(self, banner):
        """The consequence the ordering exists for: moving 3.3.4 → 3.4.0-rc.1
        crosses 3.4.0's section (it is the release being prepared) and nothing
        older, and moving on to the real 3.4.0 crosses nothing new."""
        log = [("3.4.0", "the new one"), ("3.3.4", "the old one"), ("3.3.3", "older")]
        assert [v for v, _ in banner.highlights_in_range(log, "3.3.4", "3.4.0-rc.1")] == []
        assert [v for v, _ in banner.highlights_in_range(log, "3.3.3", "3.4.0-rc.1")] == ["3.3.4"]
        assert [v for v, _ in banner.highlights_in_range(log, "3.4.0-rc.1", "3.4.0")] == ["3.4.0"]

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


class TestUpgradeRelay:
    """The delta block is emitted on stdout — the agent-facing channel — and the
    marker advances immediately, so it renders exactly once and the human never
    sees it. Without an explicit instruction to pass it on, a shipped capability
    is announced to nobody: the relay directive is what closes that gap."""

    def test_delta_carries_a_relay_directive(self, banner):
        lines = banner.render_delta("1.8.0", "1.8.1", ROOT)
        assert any(
            line.startswith(banner.RELAY_MARKER) for line in lines
        ), "a delta the user cannot see must instruct the agent to relay it"

    def test_relay_directive_is_last(self, banner):
        # It has to follow the content it refers to; a directive above the
        # headlines reads as being about the version line alone.
        lines = banner.render_delta("1.8.0", "1.8.1", ROOT)
        assert lines[-1].startswith(banner.RELAY_MARKER)

    def test_relay_accompanies_a_new_gate_delta(self, banner, tmp_path):
        # A newly-enforced gate changes what blocks the user mid-session. That is
        # the delta they most need relayed, so it must not depend on the release
        # happening to carry a changelog headline.
        root = tmp_path / "plugin"
        (root / "hooks").mkdir(parents=True)
        (root / "CHANGELOG.md").write_text("# CL\n\n## v2.1.0\n\n")
        (root / "hooks" / "gates.json").write_text(json.dumps({"gates": [
            {"id": "cumulative-critic", "name": "cumulative-critic", "since": "2.1.0",
             "summary": "PR bundle review required"}
        ]}))
        lines = banner.render_delta("2.0.0", "2.1.0", root)
        assert any("new gate" in line for line in lines)
        assert lines[-1].startswith(banner.RELAY_MARKER)

    def test_relay_names_no_internal_identifier(self, banner):
        # § Direction: text emitted into a governed product carries the plain-language
        # reason, never a requirement/chunk/backlog id the reader cannot resolve.
        directive = next(
            line for line in banner.render_delta("1.8.0", "1.8.1", ROOT)
            if line.startswith(banner.RELAY_MARKER)
        )
        assert not re.search(r"\b[A-Z]{2,4}-[A-Z0-9]{3,4}\b", directive), directive

    def test_no_relay_when_version_is_unchanged(self, tmp_path, banner):
        # Assert the marker, not the word "relay": the identity line carries a
        # provenance segment naming the checked-out branch, so a loose substring
        # match here passes or fails on what the branch happens to be called.
        prawduct = _repo(tmp_path)
        (prawduct / ".prawduct-version").write_text(PLUGIN_VERSION + "\n")
        r = _run_banner(ROOT, tmp_path)
        assert r.returncode == 0, r.stderr
        assert banner.RELAY_MARKER not in r.stdout

    def test_no_relay_on_first_marker_write(self, tmp_path, banner):
        # First contact has no prior version to diff, so there is no news to pass
        # on — telling the user "something changed" here would be a false claim.
        prawduct = _repo(tmp_path)
        r = _run_banner(ROOT, tmp_path)
        assert r.returncode == 0, r.stderr
        assert banner.RELAY_MARKER not in r.stdout
        assert (prawduct / ".prawduct-version").read_text().strip() == PLUGIN_VERSION

    def test_relay_reaches_stdout_on_a_real_crossing(self, tmp_path, banner):
        prawduct = _repo(tmp_path)
        (prawduct / ".prawduct-version").write_text("1.8.0\n")
        r = _run_banner(ROOT, tmp_path)
        assert r.returncode == 0, r.stderr
        assert banner.RELAY_MARKER in r.stdout


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


# =============================================================================
# Load provenance — which plugin code is actually loaded
# =============================================================================


def _git_repo(path: Path, *, branch: str = "testbranch") -> Path:
    """A real git checkout with one commit, on a named branch."""
    path.mkdir(parents=True, exist_ok=True)
    run = lambda *a: subprocess.run(["git", "-C", str(path), *a], capture_output=True, check=True)
    run("init", "-q")
    run("config", "user.email", "t@example.com")
    run("config", "user.name", "T")
    run("checkout", "-q", "-b", branch)
    (path / "tracked.txt").write_text("one\n")
    run("add", "tracked.txt")
    run("commit", "-q", "-m", "init")
    return path


def _plugin_tree(root: Path, version: str = "9.9.9") -> Path:
    """Minimal plugin layout so read_version() succeeds."""
    manifest_dir = root / ".claude-plugin"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "plugin.json").write_text(json.dumps({"version": version}))
    return root


class TestManagedInstallDetection:
    def test_root_under_managed_dir_is_managed(self, banner, tmp_path, monkeypatch):
        cfg = tmp_path / "cfgdir"
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(cfg))
        root = cfg / "plugins" / "marketplaces" / "prawduct"
        root.mkdir(parents=True)
        assert banner.is_managed_install(root) is True

    def test_unresolvable_path_is_treated_as_managed(self, banner, tmp_path, monkeypatch):
        """Fail toward "managed": answering False would send a genuine managed
        install into the git probe, which succeeds (marketplace installs are
        clones) and would render a segment — inverting presence-is-proof."""
        def boom():
            raise RuntimeError("no home directory")
        monkeypatch.setattr(banner, "managed_plugin_home", boom)
        assert banner.is_managed_install(tmp_path) is True

    def test_root_outside_managed_dir_is_not_managed(self, banner, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfgdir"))
        root = tmp_path / "source" / "prawduct"
        root.mkdir(parents=True)
        assert banner.is_managed_install(root) is False

    def test_missing_root_is_not_managed(self, banner, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfgdir"))
        assert banner.is_managed_install(tmp_path / "does" / "not" / "exist") is False


class TestGitRunner:
    """`_git`'s contract is depended on by checkout_provenance's type test, so
    pin it directly rather than only through a stub that presumes it."""

    def test_returns_completed_process_on_success(self, banner, tmp_path):
        root = _git_repo(tmp_path / "src" / "ok")
        result = banner._git(root, "rev-parse", "HEAD")
        assert isinstance(result, subprocess.CompletedProcess)
        assert result.returncode == 0

    def test_returns_the_exception_on_launch_failure(self, banner, tmp_path, monkeypatch):
        def boom(*a, **k):
            raise FileNotFoundError("git")
        monkeypatch.setattr(banner.subprocess, "run", boom)
        result = banner._git(tmp_path, "status")
        assert isinstance(result, FileNotFoundError)

    def test_returns_the_exception_on_timeout(self, banner, tmp_path, monkeypatch):
        def boom(*a, **k):
            raise subprocess.TimeoutExpired(cmd="git", timeout=5)
        monkeypatch.setattr(banner.subprocess, "run", boom)
        assert isinstance(banner._git(tmp_path, "status"), subprocess.TimeoutExpired)

    def test_decode_error_does_not_escape(self, banner, tmp_path, monkeypatch):
        """`text=True` can raise UnicodeDecodeError (a ValueError, not an
        OSError/SubprocessError) on a non-UTF-8 ref name."""
        def boom(*a, **k):
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
        monkeypatch.setattr(banner.subprocess, "run", boom)
        assert isinstance(banner._git(tmp_path, "status"), UnicodeDecodeError)


class TestCheckoutProvenance:
    def test_unexpected_git_return_is_guarded_not_raised(self, banner, tmp_path, monkeypatch, capsys):
        """A `_git` regressing to None must take the guarded path, not explode on
        `.returncode` — main() calls this outside its try blocks."""
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfgdir"))
        root = _git_repo(tmp_path / "src" / "prawduct")
        monkeypatch.setattr(banner, "_git", lambda *a, **k: None)
        assert banner.checkout_provenance(root) == ""
        assert "could not read plugin load provenance" in capsys.readouterr().err


    def test_managed_install_reports_nothing(self, banner, tmp_path, monkeypatch):
        """A marketplace install has a .git dir too — the path gate must win so
        real users pay no subprocess cost and see an unchanged banner."""
        cfg = tmp_path / "cfgdir"
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(cfg))
        root = _git_repo(cfg / "plugins" / "marketplaces" / "prawduct")
        assert (root / ".git").is_dir()          # the naive discriminator WOULD fire
        assert banner.checkout_provenance(root) == ""

    def test_local_checkout_reports_ref_and_sha(self, banner, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfgdir"))
        root = _git_repo(tmp_path / "src" / "prawduct", branch="develop")
        prov = banner.checkout_provenance(root)
        sha = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True, text=True,
        ).stdout.strip()
        assert prov == f"develop@{sha[:banner._SHA_CHARS]}"

    def test_dirty_checkout_is_marked(self, banner, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfgdir"))
        root = _git_repo(tmp_path / "src" / "prawduct", branch="develop")
        (root / "tracked.txt").write_text("modified\n")
        assert banner.checkout_provenance(root).endswith("+dirty")

    def test_untracked_file_alone_is_not_dirty(self, banner, tmp_path, monkeypatch):
        """Untracked files are noise during local dev; only tracked edits change
        what the plugin actually executes."""
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfgdir"))
        root = _git_repo(tmp_path / "src" / "prawduct", branch="develop")
        (root / "scratch.txt").write_text("noise\n")
        assert not banner.checkout_provenance(root).endswith("+dirty")

    def test_non_git_checkout_reports_nothing(self, banner, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfgdir"))
        root = tmp_path / "src" / "plain"
        root.mkdir(parents=True)
        assert banner.checkout_provenance(root) == ""

    def test_unborn_branch_reports_nothing(self, banner, tmp_path, monkeypatch):
        """A freshly `git init`-ed tree has a branch but no commit — porcelain-v2
        reports `branch.oid (initial)`, which is not a sha to name."""
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfgdir"))
        root = tmp_path / "src" / "fresh"
        root.mkdir(parents=True)
        subprocess.run(["git", "-C", str(root), "init", "-q"], capture_output=True, check=True)
        assert banner.checkout_provenance(root) == ""

    def test_git_unavailable_reports_nothing_but_says_so(self, banner, tmp_path, monkeypatch, capsys):
        """Absence of a segment normally reads as "a managed install won", so a
        probe that could not run must not degrade into that same silence."""
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfgdir"))
        root = _git_repo(tmp_path / "src" / "prawduct")
        boom = subprocess.TimeoutExpired(cmd="git", timeout=5)
        monkeypatch.setattr(banner, "_git", lambda *a, **k: boom)
        assert banner.checkout_provenance(root) == ""
        err = capsys.readouterr().err
        assert "could not read plugin load provenance" in err
        # the cause must be named: "unavailable" and "timed out" want different fixes
        assert "TimeoutExpired" in err

    def test_plain_directory_stays_quiet(self, banner, tmp_path, monkeypatch, capsys):
        """The genuinely-nothing-to-report path emits no noise."""
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfgdir"))
        root = tmp_path / "src" / "plain2"
        root.mkdir(parents=True)
        assert banner.checkout_provenance(root) == ""
        assert capsys.readouterr().err == ""

    def test_detached_head_is_labelled(self, banner, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfgdir"))
        root = _git_repo(tmp_path / "src" / "prawduct")
        sha = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip()
        subprocess.run(["git", "-C", str(root), "checkout", "-q", sha], capture_output=True, check=True)
        assert banner.checkout_provenance(root).startswith("detached@")


class TestBannerIdentityLine:
    def test_managed_install_line_is_unchanged(self, tmp_path, monkeypatch):
        """Byte-for-byte the pre-provenance banner — real users see no change."""
        cfg = tmp_path / "cfgdir"
        root = _plugin_tree(_git_repo(cfg / "plugins" / "marketplaces" / "prawduct"))
        env = dict(os.environ)
        env["CLAUDE_CONFIG_DIR"] = str(cfg)
        env["CLAUDE_PLUGIN_ROOT"] = str(root)
        env.pop("CLAUDE_PROJECT_DIR", None)
        out = subprocess.run(
            [sys.executable, str(BANNER)], capture_output=True, text=True, env=env, timeout=20
        ).stdout
        assert out.splitlines()[0] == "═══ Prawduct v9.9.9 (plugin) ═══"

    def test_local_checkout_line_carries_provenance(self, tmp_path):
        root = _plugin_tree(_git_repo(tmp_path / "src" / "prawduct", branch="develop"))
        env = dict(os.environ)
        env["CLAUDE_CONFIG_DIR"] = str(tmp_path / "cfgdir")
        env["CLAUDE_PLUGIN_ROOT"] = str(root)
        env.pop("CLAUDE_PROJECT_DIR", None)
        out = subprocess.run(
            [sys.executable, str(BANNER)], capture_output=True, text=True, env=env, timeout=20
        ).stdout
        first = out.splitlines()[0]
        assert first.startswith("═══ Prawduct v9.9.9 (plugin · develop@")
        assert first.endswith(") ═══")
