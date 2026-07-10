"""Tests for `prawduct-hook subagent-stop` — the event-driven consolidation trigger
(critic-persistence-redesign Ch.04).

Registered as a `SubagentStop` hook (matcher `critic-reviewer`), this command fires as
each reviewer subagent finishes and runs `critic-consolidate` best-effort. Its contract:
resolve the project from the payload `cwd`, gate on `agent_type` defensively, delegate to
the (already exhaustively tested) consolidation core, and — load-bearing — ALWAYS exit 0
so it never blocks the subagent. The enforcing gate is the session-end backstop.

The hook WIRING (does the harness fire it?) is validated live and recorded in
`.prawduct/operator-verification.md` — a hook fire is not unit-observable. These tests pin
the command BODY, which is unit-testable via subprocess with a SubagentStop-shaped stdin.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "bin" / "prawduct-hook"

PARTIALS_REL = ".prawduct/.critic-partials"
FINDINGS_REL = ".prawduct/.critic-findings.json"
MARKER_REL = ".prawduct/.critic-active"
FINAL_MODE = "final (full review, ready for push)"


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
        "CLAUDE_PLUGIN_ROOT": str(ROOT),
    }


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True,
        env=_git_env(repo), check=True, timeout=10,
    )


def _init_repo(repo: Path) -> str:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "--quiet", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("x = 1\n")
    _git(repo, "add", "src/app.py")
    _git(repo, "commit", "-m", "init", "--quiet")
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _partials_dir(repo: Path) -> Path:
    d = repo / PARTIALS_REL
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_manifest(repo: Path, head: str) -> None:
    (_partials_dir(repo) / "manifest.json").write_text(json.dumps({
        "mode": FINAL_MODE, "mode_chosen_by": "rule-3",
        "roster": ["correctness", "design", "sustainability"],
        "commit_reviewed": head, "files_reviewed": ["src/app.py"],
        "scope": "demo", "model": "opus",
    }))


def _write_partial(repo: Path, role: str, head: str) -> None:
    (_partials_dir(repo) / f"{role}.json").write_text(json.dumps({
        "role": role, "goals": "1-3", "commit_reviewed": head,
        "model": "opus", "duration_seconds": 60, "findings": [],
        "summary": f"{role} clean.",
    }))


def _full_roster(repo: Path, head: str) -> None:
    for role in ("correctness", "design", "sustainability"):
        _write_partial(repo, role, head)


def _set_marker(repo: Path) -> None:
    (repo / ".prawduct").mkdir(parents=True, exist_ok=True)
    (repo / MARKER_REL).write_text(json.dumps({"started_at": "2026-07-09T00:00:00Z"}))


def _run(repo: Path, stdin_obj: dict, *, run_cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(HOOK), "subagent-stop"],
        cwd=str(run_cwd or repo), capture_output=True, text=True,
        env=_git_env(repo), input=json.dumps(stdin_obj), timeout=30,
    )


class TestSubagentStopDelegates:
    def test_complete_roster_consolidates(self, tmp_path):
        repo = tmp_path / "r"
        head = _init_repo(repo)
        _set_marker(repo)
        _write_manifest(repo, head)
        _full_roster(repo, head)
        result = _run(repo, {"agent_type": "critic-reviewer", "cwd": str(repo)})
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert (repo / FINDINGS_REL).is_file()
        assert not (repo / PARTIALS_REL).exists()  # removed after consolidation
        assert not (repo / MARKER_REL).is_file()

    def test_scoped_plugin_agent_type_also_consolidates(self, tmp_path):
        repo = tmp_path / "r"
        head = _init_repo(repo)
        _set_marker(repo)
        _write_manifest(repo, head)
        _full_roster(repo, head)
        result = _run(repo, {"agent_type": "prawduct:critic-reviewer", "cwd": str(repo)})
        assert result.returncode == 0
        assert (repo / FINDINGS_REL).is_file()

    def test_incomplete_roster_is_noop_but_exit_0(self, tmp_path):
        repo = tmp_path / "r"
        head = _init_repo(repo)
        _set_marker(repo)
        _write_manifest(repo, head)
        _write_partial(repo, "correctness", head)  # only 1 of 3
        result = _run(repo, {"agent_type": "critic-reviewer", "cwd": str(repo)})
        assert result.returncode == 0
        assert not (repo / FINDINGS_REL).is_file()
        assert (repo / PARTIALS_REL / "manifest.json").is_file()  # left for the rest


class TestSubagentStopNeverBlocks:
    def test_no_manifest_exit_0(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        result = _run(repo, {"agent_type": "critic-reviewer", "cwd": str(repo)})
        assert result.returncode == 0

    def test_stale_consolidation_still_exit_0(self, tmp_path):
        """consolidate() returns 1 when HEAD moved (stale) — subagent-stop must
        NOT propagate that as a block; it exits 0 and leaves the marker/manifest
        for the session-end backstop."""
        repo = tmp_path / "r"
        head = _init_repo(repo)
        _set_marker(repo)
        _write_manifest(repo, head)
        _full_roster(repo, head)
        # Move HEAD after dispatch → consolidate would exit 1.
        (repo / "src" / "app.py").write_text("x = 2\n")
        _git(repo, "add", "src/app.py")
        _git(repo, "commit", "-m", "later", "--quiet")
        result = _run(repo, {"agent_type": "critic-reviewer", "cwd": str(repo)})
        assert result.returncode == 0, "advisory hook must never block the subagent"
        assert not (repo / FINDINGS_REL).is_file()
        assert (repo / MARKER_REL).is_file()  # backstop will catch it


class TestSubagentStopGating:
    def test_wrong_agent_type_does_not_consolidate(self, tmp_path):
        """A non-critic-reviewer SubagentStop (defensive gate, in case matcher
        drift lets one through) must not touch a pending manifest."""
        repo = tmp_path / "r"
        head = _init_repo(repo)
        _set_marker(repo)
        _write_manifest(repo, head)
        _full_roster(repo, head)
        result = _run(repo, {"agent_type": "some-other-agent", "cwd": str(repo)})
        assert result.returncode == 0
        assert not (repo / FINDINGS_REL).is_file()  # untouched
        assert (repo / PARTIALS_REL / "manifest.json").is_file()

    def test_cwd_locates_project_when_run_elsewhere(self, tmp_path):
        """Project resolution comes from the payload cwd (the reviewer's cwd),
        not the process cwd — the hook may run from anywhere."""
        repo = tmp_path / "r"
        head = _init_repo(repo)
        _set_marker(repo)
        _write_manifest(repo, head)
        _full_roster(repo, head)
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        # Run from `elsewhere`, but the payload cwd points at the repo.
        result = _run(repo, {"agent_type": "critic-reviewer", "cwd": str(repo)}, run_cwd=elsewhere)
        assert result.returncode == 0
        assert (repo / FINDINGS_REL).is_file(), "cwd from payload must locate the project"
