"""Tests for the v2.0.0 plugin runtime: bin/prawduct-hook, lib/, hooks (Chunk 5).

The architectural keystone. These enforce the load-bearing invariants of the
ported runtime:

  * **Lib parity** — the seven bundled governance modules are byte-identical to
    their tools/lib/ counterparts (a mirror that cannot drift during Phase-1
    coexistence), and the trimmed lib/__init__.py imports NONE of the excluded
    file-sync transport modules.
  * **Structure** — bin/prawduct-hook is an executable, parseable Python script
    with the sync cluster excised; hooks.json wires the briefing (clear) +
    Critic/reflection gate (stop) via ${CLAUDE_PLUGIN_ROOT}/bin/, and keeps the
    Chunk-1 banner.
  * **Behavioral** — invoked as a subprocess with CLAUDE_PLUGIN_ROOT +
    CLAUDE_PROJECT_DIR, the briefing renders, the Stop-hook Critic gate BLOCKS
    (exit 2) when code changed against an active plan with no findings, the
    lib-backed subcommands resolve, and NOTHING is written outside .prawduct/
    (the design §2 invariant).
  * **Gitflow base resolution** — the 2.0.0 ship-blocker fix: a configured
    base_branch (develop) drives resolve-base AND the PR gates' diff range, so a
    feature branch is reviewed against develop..HEAD, not the develop..main
    range; a repo with no base_branch is unchanged (main fallback).
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "bin" / "prawduct-hook"
PLUGIN_LIB = ROOT / "lib"
FRAMEWORK_LIB = ROOT / "tools" / "lib"
HOOKS_JSON = ROOT / "hooks" / "hooks.json"

# The governance subset bundled into the plugin (design §11, Chunk 5).
GOVERNANCE_MODULES = (
    "core",
    "critic_mode",
    "operator_verification",
    "views",
    "advisory_cmd",
    "advisory_store",
    "backlog_probes",
)
# The file-sync transport explicitly NOT bundled into the plugin runtime.
EXCLUDED_MODULES = (
    "sync_cmd",
    "migrate_cmd",
    "init_cmd",
    "validate_cmd",
    "views_cmd",
    "audit_learnings_cmd",
)


# =============================================================================
# Lib parity — the bundled governance modules mirror tools/lib byte-for-byte
# =============================================================================


class TestPluginLibParity:
    @pytest.mark.parametrize("module", GOVERNANCE_MODULES)
    def test_governance_module_is_byte_identical(self, module):
        plugin = (PLUGIN_LIB / f"{module}.py").read_bytes()
        framework = (FRAMEWORK_LIB / f"{module}.py").read_bytes()
        assert plugin == framework, (
            f"lib/{module}.py drifted from tools/lib/{module}.py — the plugin lib "
            "is a byte-parity mirror of the framework governance modules during "
            "Phase-1 coexistence (Chunk 5). Re-copy or update both together."
        )

    @pytest.mark.parametrize("module", EXCLUDED_MODULES)
    def test_excluded_sync_module_not_bundled(self, module):
        assert not (PLUGIN_LIB / f"{module}.py").exists(), (
            f"lib/{module}.py is file-sync transport — the plugin runtime must "
            "NOT bundle sync-only machinery (build-plan Chunk 5)."
        )

    def test_init_imports_no_excluded_module(self):
        tree = ast.parse((PLUGIN_LIB / "__init__.py").read_text())
        imported_submodules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
                imported_submodules.add(node.module)
            elif isinstance(node, ast.ImportFrom) and node.level == 1 and node.module is None:
                # `from . import views`
                imported_submodules.update(a.name for a in node.names)
        leaked = imported_submodules & set(EXCLUDED_MODULES)
        assert not leaked, (
            f"lib/__init__.py imports excluded file-sync modules {sorted(leaked)} — "
            "importing the plugin lib would pull in the sync transport it is meant "
            "to exclude (Chunk 5)."
        )

    def test_import_lib_does_not_load_excluded_modules(self):
        # Behavioral: importing the package + the governance entrypoints must not
        # transitively load any excluded module.
        probe = (
            "import sys; sys.path.insert(0, %r);\n"
            "from lib import infer_mode, advisory_cmd, views, operator_verification\n"
            "leaked=[m for m in %r if 'lib.'+m in sys.modules]\n"
            "print(','.join(leaked))\n"
        ) % (str(ROOT), list(EXCLUDED_MODULES))
        result = subprocess.run(
            [sys.executable, "-c", probe], capture_output=True, text=True, cwd="/tmp"
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "", (
            f"importing the plugin lib loaded excluded modules: {result.stdout.strip()}"
        )


# =============================================================================
# Structure — the ported hook script + wiring
# =============================================================================


class TestPluginHookStructure:
    def test_hook_exists_and_executable(self):
        assert HOOK.is_file(), "bin/prawduct-hook must exist"
        assert os.access(HOOK, os.X_OK), (
            "bin/prawduct-hook must be executable — bin/ is on the Bash PATH and "
            "skills invoke it as bare `prawduct-hook`"
        )

    def test_hook_has_python_shebang(self):
        first = HOOK.read_text().splitlines()[0]
        assert first == "#!/usr/bin/env python3", first

    def test_hook_parses(self):
        ast.parse(HOOK.read_text())  # raises on syntax error

    def test_sync_cluster_excised(self):
        src = HOOK.read_text()
        for sym in ("def try_sync(", "def _check_framework_version(", "def _compute_framework_freshness("):
            assert sym not in src, (
                f"{sym!r} is sync-only machinery and must be excised from the "
                "plugin runtime (Chunk 5)"
            )
        assert "try_sync(" not in src, "cmd_clear must not call try_sync in the plugin runtime"
        # The sync entry-point script is never spawned by the plugin runtime.
        assert "prawduct-setup.py" not in src and "prawduct-sync.py" not in src

    def test_resolve_base_subcommand_wired(self):
        src = HOOK.read_text()
        assert 'command == "resolve-base"' in src
        assert "def cmd_resolve_base(" in src
        assert "def _resolve_base_branch(" in src
        assert "resolve-base" in src.split("_USAGE = (", 1)[1].split(")", 1)[0]

    def test_lib_imported_via_plugin_root(self):
        src = HOOK.read_text()
        assert "def _plugin_root(" in src
        assert "CLAUDE_PLUGIN_ROOT" in src
        # The legacy tools/-relative lib path must be gone from the import sites.
        assert "tools_dir = str(Path(__file__).resolve().parent)" not in src

    def test_hooks_json_wires_briefing_and_gate(self):
        data = json.loads(HOOKS_JSON.read_text())
        ss = data["hooks"]["SessionStart"]
        stop = data["hooks"]["Stop"]
        ss_cmds = [h["command"] for e in ss for h in e["hooks"]]
        stop_cmds = [h["command"] for e in stop for h in e["hooks"]]
        # Briefing (clear) wired via the bundled hook, by plugin root.
        assert any(
            "${CLAUDE_PLUGIN_ROOT}" in c and "bin/prawduct-hook" in c and c.rstrip().endswith("clear")
            for c in ss_cmds
        ), "SessionStart must run the bundled prawduct-hook clear briefing"
        # Stop gate wired.
        assert any(
            "${CLAUDE_PLUGIN_ROOT}" in c and "bin/prawduct-hook" in c and c.rstrip().endswith("stop")
            for c in stop_cmds
        ), "Stop must run the bundled prawduct-hook stop gate"
        # Chunk-1 banner is preserved.
        assert any("banner.py" in c for c in ss_cmds), "the version banner must stay wired"

    def test_clear_matcher_excludes_compact(self):
        # cmd_clear resets the git baseline + archives reflection — that is a
        # session boundary, not a compaction event (building.md). The clear
        # entry's matcher must not include `compact`.
        data = json.loads(HOOKS_JSON.read_text())
        for entry in data["hooks"]["SessionStart"]:
            cmds = [h["command"] for h in entry["hooks"]]
            if any(c.rstrip().endswith("clear") for c in cmds):
                assert "compact" not in entry["matcher"], (
                    "the clear (state-reset) hook must not fire on compact"
                )


# =============================================================================
# Behavioral — subprocess invocation with a mock git
# =============================================================================


def _write_mock_git(mock_bin: Path, *, status: str = "", branch: str = "main", head: str = "deadbeef" * 5):
    mock_bin.mkdir(parents=True, exist_ok=True)
    status_file = mock_bin / "_status"
    status_file.write_text(status)
    git = mock_bin / "git"
    git.write_text(
        "#!/bin/bash\n"
        'if [[ "$1" == "rev-parse" && "$2" == "HEAD" ]]; then echo "%s"; exit 0; fi\n'
        'if [[ "$1" == "rev-parse" ]]; then echo ".git"; exit 0; fi\n'
        'if [[ "$1" == "status" ]]; then cat "%s"; exit 0; fi\n'
        'if [[ "$1" == "branch" && "$2" == "--show-current" ]]; then echo "%s"; exit 0; fi\n'
        'if [[ "$1" == "worktree" ]]; then exit 0; fi\n'
        'if [[ "$1" == "ls-files" ]]; then exit 1; fi\n'
        "exit 0\n" % (head, status_file, branch)
    )
    git.chmod(0o755)
    gh = mock_bin / "gh"
    gh.write_text("#!/bin/bash\necho '[]'\nexit 0\n")
    gh.chmod(0o755)


def run_plugin_hook(
    command: str,
    project_dir: Path,
    *,
    git_status: str = "",
    branch: str = "main",
    mock_bin: Path | None = None,
) -> subprocess.CompletedProcess:
    """Invoke bin/prawduct-hook as Claude Code would: CLAUDE_PLUGIN_ROOT points
    at the plugin (this repo), CLAUDE_PROJECT_DIR at the consuming repo, and a
    mock git on PATH. mock_bin defaults OUTSIDE project_dir so the §2
    write-isolation assertion can snapshot the project dir cleanly.
    """
    if mock_bin is None:
        mock_bin = project_dir.parent / "_mock_bin"
    _write_mock_git(mock_bin, status=git_status, branch=branch)
    # HOME outside project_dir so per-user caches don't land under the project
    # (would confound the §2 write-isolation snapshot). PYTHONDONTWRITEBYTECODE
    # keeps the plugin-lib import from writing .pyc into this repo during tests.
    home = mock_bin.parent / "_home"
    home.mkdir(exist_ok=True)
    env = {
        "HOME": str(home),
        "CLAUDE_PROJECT_DIR": str(project_dir),
        "CLAUDE_PLUGIN_ROOT": str(ROOT),
        "PATH": f"{mock_bin}:/usr/bin:/bin:/usr/sbin:/sbin",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    return subprocess.run(
        ["python3", str(HOOK), command],
        capture_output=True, text=True, env=env, timeout=20,
    )


def _make_session_start(prawduct: Path, offset_seconds: int = -60) -> None:
    ts = datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)
    (prawduct / ".session-start").write_text(ts.strftime("%Y-%m-%dT%H:%M:%SZ"))


class TestPluginClearBriefing:
    def test_clear_renders_briefing_and_writes_session_markers(self, tmp_path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text("backlog_format_version: 2\n")
        result = run_plugin_hook("clear", tmp_path, git_status=" M src/app.py")
        assert result.returncode == 0, result.stderr
        # Session markers written under .prawduct/
        assert (prawduct / ".session-start").is_file()
        assert (prawduct / ".session-git-baseline").is_file()
        assert (prawduct / ".session-git-baseline").read_text() == " M src/app.py"

    def test_clear_does_not_sync_even_with_manifest(self, tmp_path):
        # A sync-manifest would trigger file-sync in the legacy hook. The plugin
        # runtime must never sync (design §2/§7) — no "PRAWDUCT SYNC" output.
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "sync-manifest.json").write_text(
            json.dumps({"framework_version": "1.8.1", "framework_source": "/nonexistent"})
        )
        result = run_plugin_hook("clear", tmp_path)
        assert result.returncode == 0, result.stderr
        assert "PRAWDUCT SYNC" not in result.stdout
        assert "framework file(s) updated" not in result.stdout


class TestPluginStopGate:
    def _active_plan_repo(self, tmp_path) -> Path:
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
        (prawduct / ".session-reflected").write_text(
            "Session reflection: implemented the chunk and verified all tests pass cleanly."
        )
        (prawduct / ".session-git-baseline").write_text("")
        _make_session_start(prawduct)
        return prawduct

    def test_stop_blocks_when_critic_findings_absent(self, tmp_path):
        """Keystone acceptance: code changed vs active plan + no findings -> exit 2."""
        self._active_plan_repo(tmp_path)
        result = run_plugin_hook("stop", tmp_path, git_status=" M src/app.py")
        assert result.returncode == 2, (result.stdout, result.stderr)
        assert "CRITIC" in result.stderr

    def test_stop_passes_with_fresh_blocking_free_findings(self, tmp_path):
        prawduct = self._active_plan_repo(tmp_path)
        # A fresh, schema-valid, blocking-free findings file clears the gate
        # (files_reviewed non-empty; mode omitted — it is optional, and bare
        # short tokens are rejected by validate_critic_findings).
        (prawduct / ".critic-findings.json").write_text(json.dumps({
            "findings": [], "files_reviewed": ["src/app.py"], "summary": "No issues found.",
        }))
        result = run_plugin_hook("stop", tmp_path, git_status=" M src/app.py")
        assert result.returncode == 0, (result.stdout, result.stderr)

    def test_stop_passes_with_no_build_plan(self, tmp_path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")
        _make_session_start(prawduct)
        result = run_plugin_hook("stop", tmp_path, git_status=" M src/app.py")
        assert result.returncode == 0, (result.stdout, result.stderr)


class TestPluginSubcommandsResolveViaLib:
    def _repo(self, tmp_path) -> Path:
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text("backlog_format_version: 2\n")
        return prawduct

    def test_infer_critic_mode(self, tmp_path):
        self._repo(tmp_path)
        result = run_plugin_hook("infer-critic-mode", tmp_path)
        assert result.returncode == 0, result.stderr
        # `<mode>|<rationale>` — and NOT the missing-lib fallback.
        assert "|" in result.stdout
        assert "fallback-no-tools-lib" not in result.stdout

    def test_advisory_list(self, tmp_path):
        # `advisory` takes a subcommand; invoke `advisory list` via argv. Proves
        # the advisory CLI resolves through the bundled lib (not the missing-lib
        # fallback message).
        self._repo(tmp_path)
        result = subprocess.run(
            ["python3", str(HOOK), "advisory", "list"],
            capture_output=True, text=True, timeout=20,
            env={"HOME": str(tmp_path / "_home"), "CLAUDE_PROJECT_DIR": str(tmp_path),
                 "CLAUDE_PLUGIN_ROOT": str(ROOT), "PATH": "/usr/bin:/bin",
                 "PYTHONDONTWRITEBYTECODE": "1"},
        )
        assert result.returncode == 0, result.stderr
        assert "advisory CLI unavailable" not in (result.stdout + result.stderr)


class TestWriteIsolationInvariant:
    """Design §2: the runtime reads/writes ONLY .prawduct/ — never elsewhere."""

    def test_clear_and_stop_write_only_under_prawduct(self, tmp_path):
        project = tmp_path / "repo"
        project.mkdir()
        prawduct = project / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
        # Product files OUTSIDE .prawduct that must be untouched.
        (project / "app.py").write_text("print('hi')\n")
        (project / "README.md").write_text("# Repo\n")
        src = project / "src"
        src.mkdir()
        (src / "lib.py").write_text("x = 1\n")

        def snapshot() -> dict[str, bytes]:
            out: dict[str, bytes] = {}
            for p in project.rglob("*"):
                if p.is_file() and ".prawduct" not in p.relative_to(project).parts:
                    out[str(p.relative_to(project))] = p.read_bytes()
            return out

        before = snapshot()
        r1 = run_plugin_hook("clear", project, git_status=" M src/lib.py", mock_bin=tmp_path / "_mock_bin")
        _make_session_start(prawduct)
        r2 = run_plugin_hook("stop", project, git_status=" M src/lib.py", mock_bin=tmp_path / "_mock_bin")
        after = snapshot()
        assert before == after, (
            "the plugin runtime modified files outside .prawduct/ — violates the "
            f"§2 write-isolation invariant. clear={r1.returncode} stop={r2.returncode}"
        )


# =============================================================================
# Gitflow base resolution — the 2.0.0 ship-blocker fix (real git repo)
# =============================================================================


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, timeout=30, check=True,
        env={**os.environ,
             "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e"},
    )


def _run_in(repo: Path, *args: str) -> subprocess.CompletedProcess:
    home = repo.parent / "_home"
    home.mkdir(exist_ok=True)
    return subprocess.run(
        ["python3", str(HOOK), *args],
        capture_output=True, text=True, timeout=20,
        env={"HOME": str(home), "CLAUDE_PROJECT_DIR": str(repo),
             "CLAUDE_PLUGIN_ROOT": str(ROOT), "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
             "PYTHONDONTWRITEBYTECODE": "1"},
    )


@pytest.fixture
def gitflow_repo(tmp_path):
    """A gitflow topology where develop..main diverges from the feature branch:

        main:    M1 ──────────── M2        (M2 = a .py change on main after branch)
                  \\
        develop:   └─ D1                    (D1 = a .py change on develop)
                       \\
        feature:        └─ F1 ─ F2          (F1, F2 = .md-only changes)

    With base_branch=develop the PR diff is develop..feature = {F1,F2 .md only}
    (doc-only). With the main fallback the diff main..feature includes D1's .py
    -> NOT doc-only. That difference proves the base knob drives the range.
    """
    repo = tmp_path / "gitflow"
    repo.mkdir()
    prawduct = repo / ".prawduct"
    prawduct.mkdir()
    _git(repo, "init", "-b", "main")
    (repo / "README.md").write_text("# r\n")
    (repo / "code.py").write_text("x = 0\n")
    (prawduct / "project-state.yaml").write_text("backlog_format_version: 2\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "M1")
    # Branch develop, make a .py change (the develop..main pollution).
    _git(repo, "checkout", "-b", "develop")
    (repo / "code.py").write_text("x = 1\n")
    _git(repo, "commit", "-am", "D1 py change on develop")
    # Feature off develop: two .md-only commits.
    _git(repo, "checkout", "-b", "feature/x")
    (repo / "README.md").write_text("# r\n\nfeature line 1\n")
    _git(repo, "commit", "-am", "F1 doc")
    (repo / "README.md").write_text("# r\n\nfeature line 1\nfeature line 2\n")
    _git(repo, "commit", "-am", "F2 doc")
    # Advance main past the branch point (M2, a .py change) so develop..main is non-trivial.
    _git(repo, "checkout", "main")
    (repo / "code.py").write_text("x = 99\n")
    _git(repo, "commit", "-am", "M2 py change on main")
    _git(repo, "checkout", "feature/x")
    return repo


class TestGitflowBaseResolution:
    def test_resolve_base_honors_configured_develop(self, gitflow_repo):
        (gitflow_repo / ".prawduct" / "project-state.yaml").write_text(
            "backlog_format_version: 2\nbase_branch: develop\n"
        )
        r = _run_in(gitflow_repo, "resolve-base")
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == "develop"

    def test_resolve_base_falls_back_to_main_without_knob(self, gitflow_repo):
        # No base_branch set -> historical candidate list (trunk repos unchanged).
        r = _run_in(gitflow_repo, "resolve-base")
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == "main"

    def test_doc_only_gate_uses_develop_range(self, gitflow_repo):
        # base_branch=develop: feature diff is develop..HEAD = README.md only -> doc-only.
        (gitflow_repo / ".prawduct" / "project-state.yaml").write_text(
            "backlog_format_version: 2\nbase_branch: develop\n"
        )
        r = _run_in(gitflow_repo, "check-pr-doc-only")
        assert r.returncode == 0, (r.stdout, r.stderr)
        assert "develop" in (r.stdout + r.stderr)

    def test_doc_only_gate_pollutes_with_main_base(self, gitflow_repo):
        # No knob -> base resolves to main; main..HEAD includes develop's .py change
        # (D1) -> NOT doc-only. This is the bug the knob fixes.
        r = _run_in(gitflow_repo, "check-pr-doc-only")
        assert r.returncode == 1, (r.stdout, r.stderr)
        assert "code.py" in (r.stdout + r.stderr) or "not-doc-only" in (r.stdout + r.stderr)

    def test_configured_base_unresolvable_fails_closed(self, gitflow_repo):
        (gitflow_repo / ".prawduct" / "project-state.yaml").write_text(
            "backlog_format_version: 2\nbase_branch: nonexistent-branch\n"
        )
        r = _run_in(gitflow_repo, "resolve-base")
        assert r.returncode == 1
        assert "nonexistent-branch" in r.stderr
