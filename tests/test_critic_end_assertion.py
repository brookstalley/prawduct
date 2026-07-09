"""Tests for the ``prawduct-hook critic-end`` exit-time persistence assertion (CRT-9K7T).

A fork-and-return Critic coordinator can report success without landing its two
writes — the consolidated ``.critic-findings.json`` and the ``review.critic``
governance-ledger anchor — silently deadlocking ``check-cumulative-critic``
(``chain-missing-anchor``) later. ``critic-end`` now, when a review was active
(marker present), asserts BOTH writes cover HEAD and fails loud otherwise, while
ALWAYS clearing the marker first (the CRT-3X9D resilience contract).

Real ``git`` + the real ``ledger-append`` writer so the envelope ``git.head``
and the findings ``commit_reviewed`` behave exactly as in production.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "bin" / "prawduct-hook"
CHUNK_MODE = "chunk (lighter pass, not ready for push)"
MARKER = ".prawduct/.critic-active"


def _git_env(repo: Path) -> dict[str, str]:
    return {
        "HOME": str(repo.parent / "_home"),
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


def _hook(repo: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(_git_env(repo))
    env["CLAUDE_PROJECT_DIR"] = str(repo)
    return subprocess.run(
        ["python3", str(HOOK), *args],
        cwd=str(repo), capture_output=True, text=True, env=env, timeout=30,
    )


def _init_repo(repo: Path) -> str:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "--quiet", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".prawduct").mkdir()
    (repo / "app.py").write_text("print(1)\n")
    _git(repo, "add", "app.py")
    _git(repo, "commit", "-m", "init", "--quiet")
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _write_findings(repo: Path, commit_reviewed: str) -> None:
    data = {
        "mode": CHUNK_MODE,
        "files_reviewed": ["app.py"],
        "findings": [],
        "summary": "No issues found.",
        "commit_reviewed": commit_reviewed,
    }
    (repo / ".prawduct" / ".critic-findings.json").write_text(json.dumps(data))


def _marker_present(repo: Path) -> bool:
    return (repo / MARKER).is_file()


def test_both_writes_cover_head_passes_and_clears(tmp_path):
    repo = tmp_path / "repo"
    head = _init_repo(repo)
    _hook(repo, "critic-begin")
    assert _marker_present(repo)
    _write_findings(repo, commit_reviewed=head)
    la = _hook(repo, "ledger-append", "--event", "review.critic", "--scope", "test")
    assert la.returncode == 0, la.stderr
    r = _hook(repo, "critic-end")
    assert r.returncode == 0, r.stderr
    assert "cover HEAD" in r.stdout
    assert not _marker_present(repo)


def test_no_marker_is_idempotent_pass(tmp_path):
    # Pure cleanup call with no active review — exit 0, nothing to verify.
    repo = tmp_path / "repo"
    _init_repo(repo)
    assert not _marker_present(repo)
    r = _hook(repo, "critic-end")
    assert r.returncode == 0, r.stderr


def test_stale_findings_fails_but_still_clears(tmp_path):
    # Marker present, but .critic-findings.json commit_reviewed predates HEAD
    # (the coordinator skipped the findings writeback).
    repo = tmp_path / "repo"
    old_head = _init_repo(repo)
    _hook(repo, "critic-begin")
    _write_findings(repo, commit_reviewed=old_head)
    _hook(repo, "ledger-append", "--event", "review.critic", "--scope", "test")
    # HEAD moves past the reviewed commit.
    (repo / "core.py").write_text("x = 2\n")
    _git(repo, "add", "core.py")
    _git(repo, "commit", "-m", "more", "--quiet")
    r = _hook(repo, "critic-end")
    assert r.returncode == 1
    assert "did not persist" in r.stderr and "commit_reviewed" in r.stderr
    assert not _marker_present(repo)  # marker cleared regardless


def test_missing_ledger_anchor_fails_but_still_clears(tmp_path):
    # Findings cover HEAD, but the review.critic ledger anchor was never appended.
    repo = tmp_path / "repo"
    head = _init_repo(repo)
    _hook(repo, "critic-begin")
    _write_findings(repo, commit_reviewed=head)  # no ledger-append
    r = _hook(repo, "critic-end")
    assert r.returncode == 1
    assert "review.critic" in r.stderr and "ledger" in r.stderr
    assert not _marker_present(repo)


def test_stale_ledger_anchor_fails(tmp_path):
    # Findings cover HEAD, but the newest review.critic ledger event anchors a
    # PRIOR head (findings rewritten for HEAD, ledger not re-appended).
    repo = tmp_path / "repo"
    old_head = _init_repo(repo)
    _hook(repo, "critic-begin")
    _write_findings(repo, commit_reviewed=old_head)
    _hook(repo, "ledger-append", "--event", "review.critic", "--scope", "test")  # anchors old_head
    (repo / "core.py").write_text("x = 2\n")
    _git(repo, "add", "core.py")
    _git(repo, "commit", "-m", "more", "--quiet")
    _write_findings(repo, commit_reviewed=_git(repo, "rev-parse", "HEAD").stdout.strip())  # findings now cover HEAD
    r = _hook(repo, "critic-end")
    assert r.returncode == 1
    assert "ledger head" in r.stderr
    assert not _marker_present(repo)


def test_absent_findings_fails_but_still_clears(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    _hook(repo, "critic-begin")
    r = _hook(repo, "critic-end")  # no findings at all
    assert r.returncode == 1
    assert "absent" in r.stderr
    assert not _marker_present(repo)
