"""Tests for worktree-aware project-dir resolution (STH-4K7N).

``lib.gitstate.resolve_project_dir`` makes ``.prawduct/`` state follow the
session into a git worktree instead of pinning to the launch dir
(``CLAUDE_PROJECT_DIR``). Without this, hook-read gate state and agent-written
gate state land in different ``.prawduct/`` trees in a worktree session, breaking
the Stop / cumulative-critic gates. ``bin/prawduct-hook``'s ``get_project_dir``
delegates here, so the bin and lib resolution agree.

Real ``git`` repos, sterile env (HOME outside the repo — pyc-cache learning),
mirroring ``tests/test_governance_ledger.py``.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Helpers (real git, sterile env)
# ---------------------------------------------------------------------------


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
    }


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True,
        env=_git_env(repo), check=True, timeout=10,
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "--quiet", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-m", "init", "--quiet")


def _add_worktree(repo: Path, dest: Path, branch: str) -> Path:
    """Linked worktree of ``repo`` on a new ``branch``. Returns the resolved root."""
    _git(repo, "worktree", "add", "-q", "-b", branch, str(dest), "HEAD")
    return dest.resolve()


@pytest.fixture
def gitstate():
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from lib import gitstate as gs
    return gs


def _load_hook():
    """Load the extensionless hook as a module to exercise get_project_dir."""
    loader = importlib.machinery.SourceFileLoader(
        "prawduct_hook_project_dir", str(ROOT / "bin" / "prawduct-hook")
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# resolve_project_dir
# ---------------------------------------------------------------------------


def test_follows_worktree_when_cwd_in_worktree(tmp_path, gitstate):
    """The core fix: a worktree session resolves to the worktree, not the launch
    dir — so hook-read and agent-written .prawduct/ land on the same tree."""
    primary = tmp_path / "primary"
    _init_repo(primary)
    wt = _add_worktree(primary, tmp_path / "wt", "feature")
    # env pinned to the primary checkout (as the harness pins CLAUDE_PROJECT_DIR)
    assert gitstate.resolve_project_dir(str(primary.resolve()), wt) == wt


def test_follows_worktree_when_env_unset(tmp_path, gitstate):
    """Agent Bash invocations may run with CLAUDE_PROJECT_DIR unset — cwd in the
    worktree must still resolve to the worktree."""
    primary = tmp_path / "primary"
    _init_repo(primary)
    wt = _add_worktree(primary, tmp_path / "wt", "feature")
    assert gitstate.resolve_project_dir(None, wt) == wt


def test_resolves_repo_root_from_subdirectory(tmp_path, gitstate):
    """A launch-in-subdirectory normalizes to the repo root (toplevel walk-up)."""
    primary = tmp_path / "primary"
    _init_repo(primary)
    sub = primary / "lib" / "deep"
    sub.mkdir(parents=True)
    assert gitstate.resolve_project_dir(None, sub) == primary.resolve()


def test_no_regression_single_checkout(tmp_path, gitstate):
    """Ordinary single-checkout repo: resolution == the env pin (a no-op)."""
    primary = tmp_path / "primary"
    _init_repo(primary)
    assert gitstate.resolve_project_dir(str(primary.resolve()), primary) == primary.resolve()


def test_unrelated_repo_cwd_honors_env_pin(tmp_path, gitstate):
    """Same-repo guard: cwd in an *unrelated* repo (different git-common-dir)
    must NOT redirect state there — honor the launch pin instead."""
    primary = tmp_path / "primary"
    other = tmp_path / "other"
    _init_repo(primary)
    _init_repo(other)
    assert gitstate.resolve_project_dir(str(primary.resolve()), other) == primary.resolve()


def test_falls_back_when_cwd_not_a_git_repo(tmp_path, gitstate):
    """cwd outside any git work tree → env pin (or cwd when env is unset)."""
    primary = tmp_path / "primary"
    _init_repo(primary)
    nogit = tmp_path / "nogit"
    nogit.mkdir()
    assert gitstate.resolve_project_dir(str(primary.resolve()), nogit) == primary.resolve()
    assert gitstate.resolve_project_dir(None, nogit) == nogit.resolve()


def test_common_dir_identifies_same_repo(tmp_path, gitstate):
    """The same-repo identity test: a primary checkout and its linked worktree
    share one common dir; an unrelated repo does not."""
    primary = tmp_path / "primary"
    other = tmp_path / "other"
    _init_repo(primary)
    _init_repo(other)
    wt = _add_worktree(primary, tmp_path / "wt", "feature")
    assert gitstate.git_common_dir(primary) == gitstate.git_common_dir(wt)
    assert gitstate.git_common_dir(primary) != gitstate.git_common_dir(other)


# ---------------------------------------------------------------------------
# bin/prawduct-hook get_project_dir delegation
# ---------------------------------------------------------------------------


def test_get_project_dir_delegates_to_resolver(tmp_path, gitstate, monkeypatch):
    """bin and lib agree: get_project_dir() == resolve_project_dir(env, cwd)."""
    primary = tmp_path / "primary"
    _init_repo(primary)
    wt = _add_worktree(primary, tmp_path / "wt", "feature")
    hook = _load_hook()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(primary.resolve()))
    monkeypatch.chdir(wt)
    expected = gitstate.resolve_project_dir(str(primary.resolve()), wt)
    assert hook.get_project_dir() == expected == wt


def test_get_project_dir_falls_back_when_lib_unimportable(tmp_path, monkeypatch):
    """Bootstrap resilience: get_project_dir runs before command dispatch, so a
    broken/absent plugin lib/ must not crash it — it falls back to the env/cwd
    behavior, letting the command that needs lib surface its own import error."""
    primary = tmp_path / "primary"
    _init_repo(primary)
    hook = _load_hook()
    monkeypatch.setattr(hook, "_gitstate", _raise_import_error)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(primary.resolve()))
    assert hook.get_project_dir() == primary.resolve()


def _raise_import_error():
    raise ImportError("no module named 'lib'")


def test_get_project_dir_self_check_this_checkout(monkeypatch):
    """Don't-saw-your-own-branch: from this very checkout the session-governing
    runtime must resolve to this checkout (a wrong signal silently disables the
    live Stop gate, with no test failure to warn — so assert it explicitly)."""
    hook = _load_hook()
    monkeypatch.chdir(ROOT)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(ROOT))
    assert hook.get_project_dir() == ROOT
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    assert hook.get_project_dir() == ROOT
