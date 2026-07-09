"""Tests for the pre-merge push-completeness gate — ``prawduct-hook check-branch-pushed``.

PR-7T2K: ``/prawduct:pr`` squash-merges ``origin/<branch>`` (the GitHub PR head),
but every Create/coverage/cumulative-Critic gate validates *local* HEAD — so a
commit made after the last push is silently dropped from the merge. This gate
asserts ``origin/<current-branch>`` resolves to exactly local HEAD, and fails
loud (a merge that drops commits is worse than a false block) otherwise.

Uses real ``git`` with a real bare ``origin`` remote so ``rev-parse`` and the
remote-tracking refs behave exactly as in production.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "bin" / "prawduct-hook"


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


def _commit(repo: Path, rel: str, content: str, msg: str) -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    _git(repo, "add", rel)
    _git(repo, "commit", "-m", msg, "--quiet")
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _repo_on_pushed_branch(tmp_path: Path, branch: str = "feature/x") -> Path:
    """A repo with a bare ``origin`` remote and ``branch`` pushed at HEAD."""
    origin = tmp_path / "origin.git"
    origin.mkdir()
    _git(origin, "init", "--quiet", "--bare", "-b", "main")

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--quiet", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "remote", "add", "origin", str(origin))
    _commit(repo, "app.py", "print(1)\n", "init")
    _git(repo, "checkout", "--quiet", "-b", branch)
    _commit(repo, "feature.py", "x = 1\n", "feature work")
    _git(repo, "push", "--quiet", "-u", "origin", branch)
    return repo


def _run(repo: Path) -> subprocess.CompletedProcess:
    env = dict(_git_env(repo))
    env["CLAUDE_PROJECT_DIR"] = str(repo)
    return subprocess.run(
        ["python3", str(HOOK), "check-branch-pushed"],
        cwd=str(repo), capture_output=True, text=True, env=env, timeout=30,
    )


def test_fully_pushed_passes(tmp_path):
    repo = _repo_on_pushed_branch(tmp_path)
    r = _run(repo)
    assert r.returncode == 0, r.stderr
    assert "pushed" in r.stdout and "safe to merge" in r.stdout


def test_unpushed_commit_fails(tmp_path):
    repo = _repo_on_pushed_branch(tmp_path)
    _commit(repo, "late.py", "y = 2\n", "commit after last push")  # not pushed
    r = _run(repo)
    assert r.returncode == 1
    assert "unpushed-commits" in r.stderr
    assert "would be DROPPED" in r.stderr


def test_local_behind_remote_fails(tmp_path):
    # origin/<branch> is ahead of local HEAD (someone pushed elsewhere, local not
    # pulled): the merge would include commits not in the validated local HEAD.
    repo = _repo_on_pushed_branch(tmp_path)
    _commit(repo, "more.py", "m = 1\n", "more work")
    _git(repo, "push", "--quiet", "origin", "feature/x")  # origin advances
    _git(repo, "reset", "--hard", "--quiet", "HEAD~1")  # local now behind by 1
    r = _run(repo)
    assert r.returncode == 1
    assert "local-behind-remote" in r.stderr


def test_diverged_fails(tmp_path):
    # local and origin/<branch> each carry a commit the other lacks.
    repo = _repo_on_pushed_branch(tmp_path)
    _commit(repo, "remote_side.py", "r = 1\n", "remote-side commit")
    _git(repo, "push", "--quiet", "origin", "feature/x")  # origin at R
    _git(repo, "reset", "--hard", "--quiet", "HEAD~1")  # back to shared base
    _commit(repo, "local_side.py", "l = 1\n", "local-side commit")  # HEAD diverges
    r = _run(repo)
    assert r.returncode == 1
    assert "diverged" in r.stderr


def test_branch_never_pushed_fails(tmp_path):
    # A brand-new branch with no origin/<branch> ref at all.
    repo = _repo_on_pushed_branch(tmp_path)
    _git(repo, "checkout", "--quiet", "-b", "feature/never-pushed")
    _commit(repo, "new.py", "z = 3\n", "unpushed branch")
    r = _run(repo)
    assert r.returncode == 1
    assert "branch-not-pushed" in r.stderr
    assert "feature/never-pushed" in r.stderr


def test_detached_head_fails(tmp_path):
    repo = _repo_on_pushed_branch(tmp_path)
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _git(repo, "checkout", "--quiet", head)  # detach
    r = _run(repo)
    assert r.returncode == 1
    assert "detached-head" in r.stderr
