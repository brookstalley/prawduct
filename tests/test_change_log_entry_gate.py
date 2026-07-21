"""Tests for the missing-change-log-entry probe — ``prawduct-hook check-change-log-entry``.

REL-6C3W: a code-changing branch could merge with NO change-log entry and
nothing flagged it — the gap surfaced only at release reconstruction
(CRT-7B4M/#82, found at the v2.0.16 release). The probe runs at the PR
boundary (`/prawduct:pr` Create Step 1c): a non-``.md`` diff in
``merge-base...HEAD`` must ADD an entry header (``+## `` line) to
``.prawduct/change-log.md``. Doc-only and empty diffs are exempt;
un-evaluable git state fails closed (named reason, exit 1) so the caller
falls back to manual judgment rather than silently skipping the probe —
learnings: a skip-gate needs the most adversarial coverage, so the exempt
paths are pinned alongside the failing ones.

Uses real ``git`` repos (mirrors test_cumulative_gate.py) so merge-base and
name-only diffs behave as in production.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"

CHANGE_LOG = ".prawduct/change-log.md"


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


def _commit_file(repo: Path, rel: str, content: str, msg: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    _git(repo, "add", rel)
    _git(repo, "commit", "-m", msg, "--quiet")


def _make_branched_repo(tmp_path: Path) -> Path:
    """A repo with a ``main`` baseline (code + change-log) and a checked-out
    ``feature/x`` branch ready for branch commits. The probe's base resolution
    falls back to ``main`` (no origin, no ``base_branch:`` knob)."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "--quiet", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    _commit_file(repo, "app.py", "print(1)\n", "baseline code")
    _commit_file(
        repo, CHANGE_LOG,
        "# Change Log\n\n## 2026-06-01: baseline entry\n\nBody.\n",
        "baseline change-log",
    )
    _git(repo, "checkout", "-q", "-b", "feature/x")
    return repo


def _run_probe(repo: Path) -> subprocess.CompletedProcess:
    env = dict(_git_env(repo))
    env["CLAUDE_PROJECT_DIR"] = str(repo)
    return subprocess.run(
        ["python3", str(HOOK), "check-change-log-entry"],
        cwd=str(repo), capture_output=True, text=True, env=env, timeout=30,
    )


# ---------------------------------------------------------------------------
# Passing cases
# ---------------------------------------------------------------------------


def test_code_change_with_new_entry_passes(tmp_path):
    repo = _make_branched_repo(tmp_path)
    _commit_file(repo, "app.py", "print(2)\n", "code change")
    _commit_file(
        repo, CHANGE_LOG,
        "# Change Log\n\n## 2026-06-10: new work\n"
        "<!-- prawduct: type=fix | chunks=01 | scope=x -->\n\n"
        "## 2026-06-01: baseline entry\n\nBody.\n",
        "add entry",
    )
    result = _run_probe(repo)
    assert result.returncode == 0, result.stderr
    assert "entry-present" in result.stdout


def test_doc_only_branch_exempt(tmp_path):
    repo = _make_branched_repo(tmp_path)
    _commit_file(repo, "docs/notes.md", "notes\n", "doc change")
    result = _run_probe(repo)
    assert result.returncode == 0, result.stderr
    assert "doc-only" in result.stdout


def test_empty_diff_exempt(tmp_path):
    repo = _make_branched_repo(tmp_path)
    # No branch commits: merge-base...HEAD is empty.
    result = _run_probe(repo)
    assert result.returncode == 0, result.stderr
    assert "empty-diff" in result.stdout


# ---------------------------------------------------------------------------
# Failing cases (the load-bearing coverage)
# ---------------------------------------------------------------------------


def test_code_change_without_entry_fails(tmp_path):
    repo = _make_branched_repo(tmp_path)
    _commit_file(repo, "app.py", "print(2)\n", "code change")
    result = _run_probe(repo)
    assert result.returncode == 1
    assert "no-entry" in result.stderr
    assert "app.py" in result.stderr


def test_entry_edited_but_not_added_fails(tmp_path):
    """Touching the change-log (rewording an OLD entry) must not vouch for the
    branch's code changes — a new ``+## `` header is required."""
    repo = _make_branched_repo(tmp_path)
    _commit_file(repo, "app.py", "print(2)\n", "code change")
    _commit_file(
        repo, CHANGE_LOG,
        "# Change Log\n\n## 2026-06-01: baseline entry\n\nReworded body.\n",
        "reword old entry",
    )
    result = _run_probe(repo)
    assert result.returncode == 1
    assert "entry-edited-not-added" in result.stderr


def test_unresolvable_base_fails_closed(tmp_path):
    """No git repo at all → no base resolves → exit 1 with a named reason
    (manual judgment, never a silent skip)."""
    plain = tmp_path / "plain"
    (plain / ".prawduct").mkdir(parents=True)
    (plain / CHANGE_LOG).write_text("# Change Log\n")
    result = _run_probe(plain)
    assert result.returncode == 1
    assert "no-base" in result.stderr or "git-failed" in result.stderr


# ---------------------------------------------------------------------------
# Edge: header-add detection is diff-line anchored
# ---------------------------------------------------------------------------


def test_plus_h2_in_body_prose_does_not_count(tmp_path):
    """A body line that merely CONTAINS '## ' (e.g. markdown quoting) is not an
    added entry header — only a diff line starting '+## ' counts."""
    repo = _make_branched_repo(tmp_path)
    _commit_file(repo, "app.py", "print(2)\n", "code change")
    _commit_file(
        repo, CHANGE_LOG,
        "# Change Log\n\n## 2026-06-01: baseline entry\n\n"
        "Body now mentions a header-like token: `## not a header`.\n",
        "edit body only",
    )
    result = _run_probe(repo)
    assert result.returncode == 1
    assert "entry-edited-not-added" in result.stderr
