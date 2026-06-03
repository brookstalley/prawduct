"""Tests for the v2.0.0 plugin runtime: bin/prawduct-hook, lib/, hooks (Chunk 5).

The architectural keystone. These enforce the load-bearing invariants of the
ported runtime:

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
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "bin" / "prawduct-hook"
HOOKS_JSON = ROOT / "hooks" / "hooks.json"

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

    def test_clear_briefing_namespaces_status_hints(self, tmp_path):
        # ADV-3K7Q (whole-briefing coherence): the plugin clear briefing's status
        # lines — backlog triage and learnings lookup — must name the
        # plugin-namespaced skills, not the bare file-sync forms that do not
        # resolve in a plugin repo's command namespace. (The file-sync engine that
        # kept the bare forms was retired in M4.)
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        # A structured backlog (two items) so the count line fires and we isolate
        # the status-line hints.
        (prawduct / "project-state.yaml").write_text("backlog_format_version: 2\n")
        (prawduct / "backlog.md").write_text(
            "# Backlog\n\n## Open\n- [ABC-0001] a pending item\n- [ABC-0002] another\n"
        )
        (prawduct / "learnings.md").write_text("# Learnings\n\n- a standing rule\n")
        result = run_plugin_hook("clear", tmp_path)
        assert result.returncode == 0, result.stderr
        # Both status hints name the plugin-namespaced skills...
        assert "/prawduct:backlog to triage" in result.stdout
        assert "/prawduct:learnings <topic>" in result.stdout
        # ...and the bare file-sync forms do not leak into a plugin briefing.
        assert "(/backlog to triage)" not in result.stdout
        assert "/learnings <topic>" not in result.stdout


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
        # The gate names the plugin-namespaced skill — a bare `/critic` does not
        # resolve in a plugin repo's command namespace. Pin the command form, not
        # just the word: the message also cites the file `.prawduct/critic-review.md`
        # (contains `/critic`), so the negative must target the backtick command form.
        assert "`/prawduct:critic`" in result.stderr
        assert "`/critic`" not in result.stderr

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


class TestStopGateAttribution:
    """Design §5a: a blocking message names the version + gate that caused it,
    so a surprise block is always traceable to the update, never mysterious."""

    PLUGIN_VERSION = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())["version"]

    def test_critic_block_names_version_and_gate(self, tmp_path):
        prawduct = tmp_path / ".prawduct"
        (prawduct / "artifacts").mkdir(parents=True)
        (prawduct / "artifacts" / "build-plan.md").write_text(
            "# Build Plan\n\n## Status\n- [ ] Chunk 1\n"
        )
        (prawduct / ".session-reflected").write_text(
            "Session reflection: implemented the chunk and verified all tests pass cleanly."
        )
        (prawduct / ".session-git-baseline").write_text("")
        _make_session_start(prawduct)
        result = run_plugin_hook("stop", tmp_path, git_status=" M src/app.py")
        assert result.returncode == 2, (result.stdout, result.stderr)
        assert "gate: critic-review" in result.stderr
        assert f"prawduct v{self.PLUGIN_VERSION}" in result.stderr

    def test_reflection_block_names_gate(self, tmp_path):
        # Critic satisfied (fresh blocking-free findings) but reflection missing
        # -> only the reflection gate blocks, and it carries its own attribution.
        prawduct = tmp_path / ".prawduct"
        (prawduct / "artifacts").mkdir(parents=True)
        (prawduct / "artifacts" / "build-plan.md").write_text(
            "# Build Plan\n\n## Status\n- [ ] Chunk 1\n"
        )
        (prawduct / ".session-git-baseline").write_text("")
        _make_session_start(prawduct)
        (prawduct / ".critic-findings.json").write_text(json.dumps({
            "findings": [], "files_reviewed": ["src/app.py"], "summary": "No issues found.",
        }))
        result = run_plugin_hook("stop", tmp_path, git_status=" M src/app.py")
        assert result.returncode == 2, (result.stdout, result.stderr)
        assert "REFLECTION" in result.stderr
        assert "gate: reflection" in result.stderr


class TestPluginRuntimeNamespacing:
    """Full-coherence namespace sweep: the plugin runtime names the
    /prawduct:-namespaced skills in ALL agent-facing gate output AND its own
    docstrings/comments. A bare `/critic` or `/pr` does not resolve in a plugin
    repo's command namespace. (The frozen file-sync runtime that kept the bare
    forms was retired in M4.) Source-scan, matching this module's other
    structural-invariant tests (test_sync_cluster_excised): assert the BAD form
    is ABSENT, because a presence-only check lets sibling leaks survive (the
    prior namespace sweep's recurring failure mode — see learnings.md)."""

    # Bare command phrases that must never appear in the plugin hook. Each is
    # collision-free with file paths and prose: the command+arg phrases contain a
    # space (no path does), and the backtick forms only ever wrap a command
    # invocation. (Legit survivors are file paths like `.prawduct/critic-review.md`
    # and the prose `critic/pr skills` — none match these needles.)
    FORBIDDEN_BARE = (
        "/critic chunk",
        "/critic final",
        "/critic cumulative",
        "/critic verify-resolutions",
        "`/critic`",
        "/pr create",
        "`/pr`",
        "Run /pr ",
        # The hyphenated `/prawduct-advisory` is the FROZEN file-sync skill name;
        # the plugin skill is `/prawduct:advisory`. (Collision-free with the binary
        # path `bin/prawduct-hook`, which contains `/prawduct-hook`, not `-advisory`.)
        "/prawduct-advisory",
    )

    def test_hook_emits_no_bare_command_forms(self):
        src = HOOK.read_text()
        leaked = [needle for needle in self.FORBIDDEN_BARE if needle in src]
        assert not leaked, (
            f"bin/prawduct-hook leaks bare command form(s) {leaked} — the plugin "
            "runtime must name the /prawduct:-namespaced skills in agent-facing "
            "output and docstrings alike (a bare form does not resolve in a plugin "
            "repo). The frozen file-sync copies keep the bare forms; the plugin "
            "diverges."
        )
        # ...and the namespaced forms ARE present (the sweep replaced, not deleted).
        assert "`/prawduct:critic`" in src, "stop-hook Critic gate must name /prawduct:critic"
        assert "/prawduct:critic cumulative" in src, "pr-create gate must name /prawduct:critic cumulative"
        assert "Run /prawduct:pr to invoke" in src, "stop-hook PR gate must name /prawduct:pr"


class TestPluginDocsNamespacing:
    """The plugin-bundled TEACHING PROSE names /prawduct:-namespaced commands, not
    bare /critic / /pr forms. These files are read by an agent ONLY when the plugin
    governs (the skills point at them via ${CLAUDE_SKILL_DIR}/../../methodology/…),
    so a bare `/critic chunk` would not resolve in the repo's command namespace —
    the same leak class as the runtime sweep (TestPluginRuntimeNamespacing), one
    surface over. Source-scan, assert the bad form is ABSENT.

    The needle is the FULL skill-command vocabulary (not just the tokens that
    happened to leak), encoding the learnings.md rule: a partial sweep that pins
    only the spellings present today silently passes over a sibling added later.
    (The file-sync copies under tools/ + templates/ that once kept the bare forms
    were deleted with the engine in M4 — only these plugin-bundled files remain.)"""

    DOCS = (
        "methodology/building.md",
        "methodology/planning.md",
        "methodology/reflection.md",
        "skills/critic/review-cycle.md",
        "skills/critic/review-protocol.md",
        "skills/pr/review-protocol.md",
    )
    # A genuine command-invocation token: a `/` that starts a command (NOT preceded
    # by a word/path char — so paths like `skills/critic/…`, `.prawduct/backlog.md`,
    # and the already-namespaced `/prawduct:critic` are excluded) followed by a
    # skill name on a word boundary (so `/pr` does not match inside `/prawduct`).
    # `/clear` is a Claude Code built-in, not a prawduct skill — deliberately absent.
    BARE_INVOCATION = re.compile(
        r"(?<![\w/:.\-])/(critic|pr|backlog|learnings|janitor|discovery|planning"
        r"|building|reflection|methodology|doctor|advisory)\b"
    )

    @pytest.mark.parametrize("rel", DOCS)
    def test_no_bare_command_invocations(self, rel):
        src = (ROOT / rel).read_text(encoding="utf-8")
        leaks = sorted({m.group(0) for m in self.BARE_INVOCATION.finditer(src)})
        assert not leaks, (
            f"{rel} carries bare command invocation(s) {leaks} — plugin-bundled "
            "teaching prose must name the /prawduct:-namespaced skill (a bare form "
            "does not resolve in a plugin repo's command namespace). Frozen "
            "tools/ + templates/ copies keep the bare forms; these plugin files diverge."
        )

    def test_namespaced_forms_present(self):
        # The sweep REPLACED bare forms; it didn't delete the references.
        cycle = (ROOT / "skills/critic/review-cycle.md").read_text(encoding="utf-8")
        assert "/prawduct:critic" in cycle and "/prawduct:pr create" in cycle
        planning = (ROOT / "methodology/planning.md").read_text(encoding="utf-8")
        assert "/prawduct:learnings" in planning
        building = (ROOT / "methodology/building.md").read_text(encoding="utf-8")
        assert "/prawduct:critic" in building and "/prawduct:pr" in building


class TestPluginSubcommandsResolveViaLib:
    def _repo(self, tmp_path) -> Path:
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text("backlog_format_version: 2\n")
        return prawduct

    def test_infer_critic_mode(self, tmp_path):
        self._repo(tmp_path)
        result = run_plugin_hook("infer-critic-mode", tmp_path)
        # Resolves through the bundled lib/ (exit 0, a real `<mode>|<rationale>`).
        # The pre-2.0 `final|fallback-no-tools-lib` degradation was removed in M4 —
        # a failed import now exits non-zero, so a clean run proves lib resolved.
        assert result.returncode == 0, result.stderr
        mode, sep, _rationale = result.stdout.strip().partition("|")
        assert sep == "|", result.stdout
        assert mode in {"chunk", "final", "cumulative", "verify-resolutions"}, result.stdout

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


class TestValidateEvidenceSchema:
    """`prawduct-hook validate-evidence` requires the full F4a coverage schema.

    The pre-v1.4 compat path that accepted ``verifier``-less "legacy" evidence
    was removed in M4 (file-sync retirement): the plugin runtime always emits
    the F4a fields (directly, or via ``test-reference-verify --merge-into``), so
    no remaining writer produces the legacy shape.
    """

    _COMPLETE = {
        "timestamp": "2026-06-03T12:00:00Z",
        "passed": 10, "failed": 0, "skipped": 0,
        "duration_seconds": 1, "command": "pytest",
        "verifier": "test-reference-verify (floor: symbol-grep)",
        "tests_executed": ["tests/test_x.py"],
        "changes_referenced": ["lib/x.py"],
        "coverage_level": "referenced",
    }

    def _write_evidence(self, tmp_path: Path, evidence: dict) -> Path:
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir(exist_ok=True)
        (prawduct / ".test-evidence.json").write_text(json.dumps(evidence))
        return tmp_path

    def test_complete_f4a_evidence_accepted(self, tmp_path):
        repo = self._write_evidence(tmp_path, self._COMPLETE)
        result = _run_in(repo, "validate-evidence")
        assert result.returncode == 0, result.stderr
        assert "valid" in result.stdout

    def test_legacy_no_verifier_evidence_rejected(self, tmp_path):
        # The pre-v1.4 "legacy" shape: the 6 base fields, no F4a coverage fields.
        legacy = {k: self._COMPLETE[k] for k in (
            "timestamp", "passed", "failed", "skipped", "duration_seconds", "command",
        )}
        repo = self._write_evidence(tmp_path, legacy)
        result = _run_in(repo, "validate-evidence")
        assert result.returncode == 1, result.stdout
        # Names the now-required F4a fields so the writer bug is obvious.
        assert "verifier" in result.stderr
        assert "coverage_level" in result.stderr


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


class TestVerifyOperatorVerificationSubcommand:
    """`prawduct-hook verify-operator-verification <VRF-id>` (Chunk 11) is the
    plugin-native replacement for the legacy `prawduct-setup.py verify` path,
    which no longer exists in a migrated consumer. It flips one pending entry
    to verified, operating only on the consumer's own
    .prawduct/operator-verification.md — the /prawduct:pr and /prawduct:doctor
    skills invoke it.
    """

    def _seed(self, tmp_path: Path, body: str) -> Path:
        repo = tmp_path / "consumer"
        prawduct = repo / ".prawduct"
        prawduct.mkdir(parents=True)
        (prawduct / "operator-verification.md").write_text(body)
        return repo

    def test_flips_pending_to_verified(self, tmp_path):
        repo = self._seed(tmp_path, "## VRF-001 — a\n**Status:** pending\n")
        result = _run_in(repo, "verify-operator-verification", "VRF-001")
        assert result.returncode == 0, result.stderr
        assert "VRF-001" in result.stdout
        assert "pending" in result.stdout and "verified" in result.stdout
        queue = (repo / ".prawduct" / "operator-verification.md").read_text()
        assert "**Status:** verified" in queue

    def test_missing_id_errors_and_leaves_queue_untouched(self, tmp_path):
        repo = self._seed(tmp_path, "## VRF-001 — a\n**Status:** pending\n")
        result = _run_in(repo, "verify-operator-verification")
        assert result.returncode == 1
        assert "requires a VRF id" in result.stderr
        queue = (repo / ".prawduct" / "operator-verification.md").read_text()
        assert "**Status:** pending" in queue

    def test_unknown_id_errors(self, tmp_path):
        repo = self._seed(tmp_path, "## VRF-001 — a\n**Status:** pending\n")
        result = _run_in(repo, "verify-operator-verification", "VRF-999")
        assert result.returncode == 1
        assert "VRF-999" in result.stderr

    def test_accepted_entry_refuses_verify(self, tmp_path):
        repo = self._seed(tmp_path, "## VRF-001 — a\n**Status:** accepted\n")
        result = _run_in(repo, "verify-operator-verification", "VRF-001")
        assert result.returncode == 1
        assert "accepted" in result.stderr.lower()

    def test_subcommand_listed_in_usage(self, tmp_path):
        repo = tmp_path / "r"
        repo.mkdir()
        result = _run_in(repo, "bogus-subcommand")
        assert result.returncode == 1
        assert "verify-operator-verification" in result.stderr


class TestAuditLearningsSubcommand:
    """`prawduct-hook audit-learnings [--apply] [--json]` (Chunk 13) is the
    plugin-native replacement for the legacy `prawduct-setup.py audit-learnings`
    path, gone in a migrated consumer. It operates purely on the consumer's own
    `.prawduct/learnings.md`; `/prawduct:doctor`'s Audit-Learnings flow invokes
    it with --json. (Entries here carry NO `sentinel=` so no pytest subprocess
    runs — the runner only shells out for retirement-candidate sentinels.)
    """

    def _seed(self, tmp_path: Path, learnings: str | None) -> Path:
        repo = tmp_path / "consumer"
        prawduct = repo / ".prawduct"
        prawduct.mkdir(parents=True)
        if learnings is not None:
            (prawduct / "learnings.md").write_text(learnings)
        return repo

    def test_promotion_candidate_surfaced_json(self, tmp_path):
        repo = self._seed(
            tmp_path,
            "# Learnings\n\n## A confirmed rule\n"
            "<!-- prawduct-learning: confirmations=2; created=2026-01-01 -->\n\nBody.\n",
        )
        result = _run_in(repo, "audit-learnings", "--json")
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["applied"] is False
        assert [p["title"] for p in data["promotions"]] == ["A confirmed rule"]

    def test_stale_flag_surfaced_json(self, tmp_path):
        repo = self._seed(
            tmp_path,
            "# Learnings\n\n## An old unconfirmed rule\n"
            "<!-- prawduct-learning: confirmations=1; created=2020-01-01 -->\n\nBody.\n",
        )
        result = _run_in(repo, "audit-learnings", "--json")
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert [s["title"] for s in data["stale_flags"]] == ["An old unconfirmed rule"]

    def test_missing_learnings_is_clean_empty_not_error(self, tmp_path):
        # A .prawduct/ with no learnings.md is a clean empty result, not an error.
        repo = self._seed(tmp_path, None)
        result = _run_in(repo, "audit-learnings", "--json")
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["promotions"] == [] and data["retirements"] == []
        assert "error" not in data

    def test_non_prawduct_dir_errors(self, tmp_path):
        repo = tmp_path / "bare"
        repo.mkdir()
        result = _run_in(repo, "audit-learnings", "--json")
        assert result.returncode == 1
        data = json.loads(result.stdout)
        assert "error" in data

    def test_human_summary_without_json(self, tmp_path):
        repo = self._seed(
            tmp_path,
            "# Learnings\n\n## A confirmed rule\n"
            "<!-- prawduct-learning: confirmations=2; created=2026-01-01 -->\n\nBody.\n",
        )
        result = _run_in(repo, "audit-learnings")
        assert result.returncode == 0, result.stderr
        assert "promotion candidate" in result.stdout
        assert "A confirmed rule" in result.stdout

    def test_subcommand_listed_in_usage(self, tmp_path):
        repo = tmp_path / "r"
        repo.mkdir()
        result = _run_in(repo, "bogus-subcommand")
        assert result.returncode == 1
        assert "audit-learnings" in result.stderr


class TestNoBareSkillShadowing:
    """A bare `.claude/skills/<name>/` in this framework repo would double-load as
    a `/<name>` skill and shadow the plugin's `/prawduct:<name>`. Chunk 14 first
    relocated the six file-sync skill *sources* out of `.claude/skills/` into
    `templates/skill-<name>.md`; M4 Chunk 4 deleted those templates outright when
    the file-sync engine retired (governance ships from the plugin's `skills/`).
    This guards the structure so a future edit can't silently re-introduce a bare
    shadowing skill dir.
    """

    SHADOWABLE = ("pr", "janitor", "learnings", "backlog", "prawduct-advisory", "prawduct-doctor")

    @pytest.mark.parametrize("name", SHADOWABLE)
    def test_no_shadowing_bare_skill_dir(self, name):
        assert not (ROOT / ".claude" / "skills" / name).exists(), (
            f".claude/skills/{name}/ re-introduced — a bare /{name} skill would "
            f"shadow the plugin's /prawduct:{name} with a stale file-sync copy "
            "(Chunk 14 relocation / M4 Chunk 4 deletion)"
        )
