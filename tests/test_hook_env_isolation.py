"""Pins for ``fixtures.hook_env.isolated_hook_run``.

The helper exists because tests asserting on all of ``prawduct-hook``'s stderr
passed in CI and failed in every agent worktree: the hook prints a
linked-worktree NOTE there, before dispatch. These tests show three things: the
NOTE really fires from an agent-worktree checkout (so the isolation has
something to remove), the helper removes it, and the helper does not do that by
hiding stderr (a real stderr line still reaches the caller).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_TESTS_DIR = str(Path(__file__).resolve().parent)
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

from fixtures.hook_env import HOOK, PLUGIN_ROOT, isolated_hook_run  # noqa: E402

# A retired hook subcommand: inert and silent on both streams wherever it runs,
# so anything on its stderr came from the pre-dispatch guards.
_SILENT_COMMAND = "build-index"
_WORKTREE_NOTE = "a linked agent worktree"


def _git(cwd: Path, *args: str) -> None:
    home = cwd.parent / "_home"
    home.mkdir(exist_ok=True)
    subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        check=True,
        timeout=15,
        env={
            "HOME": str(home),
            "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_AUTHOR_NAME": "T",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "T",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        },
    )


def _agent_worktree(tmp_path: Path) -> Path:
    """A repo with an agent-path worktree on a named branch, the shape a
    worktree-isolated agent runs the suite from."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / ".prawduct").mkdir()
    (repo / ".prawduct" / "project-state.yaml").write_text("product_name: T\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    wt = repo / ".claude" / "worktrees" / "agent-0123456789abcdef0"
    wt.parent.mkdir(parents=True)
    _git(repo, "worktree", "add", "-q", "-b", "fix/thing", str(wt), "HEAD")
    return wt.resolve()


def _run(*args: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK), *args],
        capture_output=True,
        text=True,
        timeout=30,
        **kwargs,
    )


def test_the_note_fires_from_an_agent_worktree(tmp_path: Path) -> None:
    """The control: run the way the failing tests used to (the project is the
    checkout the suite runs in), and the NOTE is on stderr. Without this the
    test below could pass because the NOTE never fires at all."""
    wt = _agent_worktree(tmp_path)
    proc = _run(
        _SILENT_COMMAND,
        cwd=str(wt),
        env={**isolated_hook_run(wt)["env"]},
    )
    assert proc.returncode == 0
    assert _WORKTREE_NOTE in proc.stderr


def test_isolation_removes_the_note_even_when_the_suite_runs_in_one(
    tmp_path: Path,
) -> None:
    """The ambient checkout is an agent worktree, as it is for an agent running
    the suite; the helper still resolves the project to the test's own dir."""
    wt = _agent_worktree(tmp_path)
    neutral = tmp_path / "neutral"
    neutral.mkdir()
    base = {**isolated_hook_run(wt)["env"]}  # the env a run from `wt` would carry
    proc = _run(_SILENT_COMMAND, **isolated_hook_run(neutral, env=base))
    assert proc.returncode == 0
    assert proc.stderr == ""


def test_isolation_does_not_hide_real_stderr(tmp_path: Path) -> None:
    """A positive control: an unknown command prints usage to stderr, and an
    isolated run still shows it. A helper that passed by swallowing stderr
    would turn every empty-stderr assertion into a tautology."""
    proc = _run("no-such-command-xyz", **isolated_hook_run(tmp_path))
    assert proc.returncode != 0
    assert "Usage: prawduct-hook" in proc.stderr


def test_plugin_root_is_pinned_to_this_checkout(tmp_path: Path) -> None:
    kwargs = isolated_hook_run(tmp_path, env={"CLAUDE_PLUGIN_ROOT": "/elsewhere"})
    assert kwargs["env"]["CLAUDE_PLUGIN_ROOT"] == str(PLUGIN_ROOT)
    assert kwargs["env"]["CLAUDE_PROJECT_DIR"] == str(tmp_path)
    assert kwargs["cwd"] == str(tmp_path)
