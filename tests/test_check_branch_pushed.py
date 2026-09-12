"""Tests for the pre-merge push-completeness gate — ``prawduct-hook check-branch-pushed``.

The gates around a merge all validate a ref that agrees with itself: coverage and
cumulative-Critic read local HEAD, CI grades the pushed tip, and the merge takes what is
on the remote. So a commit made after the last push — very often the change-log entry a
review just forced — is absent from the merge with every signal green. This gate asserts
the branch's upstream ref resolves to exactly local HEAD, and every non-zero outcome
blocks (#248; the defect fired in production 2026-09-12, PR #803 merging one commit short).

Exit codes are the contract (``api-contract.md`` § Error Model): 0 pushed, 1 a push state
that was read and is unsatisfied, **3** a subject that could not be read. Both codes block
at the caller; the split exists so the remedy printed is one that can actually apply, and
each is pinned here — a refusal mapped to the wrong code is the failure mode the artifact's
third-outcome rule was written against.

Uses real ``git`` with a real bare ``origin`` remote so tracking refs, ancestry and
``%(upstream:short)`` behave exactly as in production.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"

sys.path.insert(0, str(ROOT))
from lib import gitstate  # noqa: E402


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
    """A repo with a bare ``origin`` remote and ``branch`` pushed at HEAD with ``-u``."""
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


# --- exit 0: the branch is fully pushed --------------------------------------

def test_fully_pushed_passes(tmp_path):
    repo = _repo_on_pushed_branch(tmp_path)
    r = _run(repo)
    assert r.returncode == 0, r.stderr
    assert r.stdout.startswith("pushed:")


def test_the_pass_line_names_the_ref_and_the_bound_on_the_answer(tmp_path):
    """The answer is this clone's view, and says so where the answer is read.

    Without it the gate reads as having certified the PR head, which it cannot —
    that is the caller's `gh pr view --json headRefOid` comparison — and a reader
    who believes otherwise deletes the check that does it.
    """
    repo = _repo_on_pushed_branch(tmp_path)
    r = _run(repo)
    assert "origin/feature/x" in r.stdout
    assert "as far as this clone knows" in r.stdout
    assert "separate question" in r.stdout


# --- exit 1: the push state was read and is unsatisfied ----------------------

def test_unpushed_commit_fails(tmp_path):
    """The reported defect: a commit made after the last push."""
    repo = _repo_on_pushed_branch(tmp_path)
    _commit(repo, "late.py", "y = 2\n", "commit after last push")
    r = _run(repo)
    assert r.returncode == 1
    assert "unpushed-commits" in r.stderr
    assert "DROPPED" in r.stderr
    assert "git push" in r.stderr


def test_local_behind_remote_fails(tmp_path):
    """origin is ahead: the merge would take commits no gate here validated."""
    repo = _repo_on_pushed_branch(tmp_path)
    _commit(repo, "more.py", "m = 1\n", "more work")
    _git(repo, "push", "--quiet", "origin", "feature/x")
    _git(repo, "reset", "--hard", "--quiet", "HEAD~1")
    r = _run(repo)
    assert r.returncode == 1
    assert "local-behind-remote" in r.stderr
    assert "never force-push" in r.stderr


def test_diverged_fails(tmp_path):
    """Each side carries a commit the other lacks."""
    repo = _repo_on_pushed_branch(tmp_path)
    _commit(repo, "remote_side.py", "r = 1\n", "remote-side commit")
    _git(repo, "push", "--quiet", "origin", "feature/x")
    _git(repo, "reset", "--hard", "--quiet", "HEAD~1")
    _commit(repo, "local_side.py", "l = 1\n", "local-side commit")
    r = _run(repo)
    assert r.returncode == 1
    assert "diverged" in r.stderr
    assert "never force-push" in r.stderr


def test_neither_direction_is_reported_as_the_other(tmp_path):
    """Ancestry decides the direction, so the three exit-1 shapes are distinct.

    A classifier that keyed off "the shas differ" would produce one message for
    all three, and two of the three remedies it names would be wrong: pushing a
    local-behind branch is a no-op, and force-pushing a diverged one voids the
    review evidence.
    """
    repo = _repo_on_pushed_branch(tmp_path)
    _commit(repo, "late.py", "y = 2\n", "commit after last push")
    ahead = _run(repo).stderr
    assert "local-behind-remote" not in ahead and "diverged" not in ahead


def test_branch_never_pushed_fails(tmp_path):
    """A brand-new branch: no upstream configured, so nothing says what would merge."""
    repo = _repo_on_pushed_branch(tmp_path)
    _git(repo, "checkout", "--quiet", "-b", "feature/never-pushed")
    _commit(repo, "new.py", "z = 3\n", "unpushed branch")
    r = _run(repo)
    assert r.returncode == 1
    assert "no-upstream" in r.stderr
    assert "git push -u origin feature/never-pushed" in r.stderr


def test_configured_upstream_whose_ref_is_gone_fails(tmp_path):
    """The shape a branch reused after its PR merged lands in: tracking config
    survives, the remote branch does not. Kept distinct from `no-upstream`
    because `git push -u` is not the remedy — and because `git rev-parse @{u}`
    conflates the two, printing a plausible `@{u}` on stdout while exiting 128,
    which is why the probe reads the config ref instead."""
    repo = _repo_on_pushed_branch(tmp_path)
    _git(repo, "update-ref", "-d", "refs/remotes/origin/feature/x")
    r = _run(repo)
    assert r.returncode == 1
    assert "upstream-ref-missing" in r.stderr
    assert "origin/feature/x" in r.stderr


# --- exit 3: the subject could not be read -----------------------------------

def test_detached_head_takes_the_third_outcome(tmp_path):
    """No branch is no subject. Exit 1 would hand the caller a push with nothing
    to push and no branch to push it from; exit 0 would certify a check that
    never ran. Both codes block — this pins WHICH, because the remedy differs."""
    repo = _repo_on_pushed_branch(tmp_path)
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _git(repo, "checkout", "--quiet", head)
    r = _run(repo)
    assert r.returncode == 3
    assert "detached-head" in r.stderr
    assert "Check out the branch" in r.stderr


def test_an_unreadable_repository_takes_the_third_outcome_and_says_nothing_was_checked(
    tmp_path,
):
    """A directory that is not a work tree. The gate must not report a clean
    bill, and must not claim a push would fix it."""
    outside = tmp_path / "not-a-repo"
    outside.mkdir()
    env = {
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "HOME": str(tmp_path / "_home"),
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "CLAUDE_PROJECT_DIR": str(outside),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    r = subprocess.run(
        ["python3", str(HOOK), "check-branch-pushed"],
        cwd=str(outside), capture_output=True, text=True, env=env, timeout=30,
    )
    assert r.returncode == 3
    assert "git-failed" in r.stderr
    assert "Nothing was checked" in r.stderr


# --- the probe, directly -----------------------------------------------------

def test_probe_reports_git_failed_without_a_work_tree(tmp_path):
    outside = tmp_path / "bare-dir"
    outside.mkdir()
    state = gitstate.branch_push_state(outside)
    assert state["state"] == "git-failed"
    assert state["detail"]


def test_probe_counts_do_not_decide_the_direction(tmp_path):
    """The counts are for the sentence; ancestry is the verdict. Pinned because
    swapping the two reads as a simplification and silently inverts the
    local-behind and unpushed messages against each other."""
    repo = _repo_on_pushed_branch(tmp_path)
    _commit(repo, "late.py", "y = 2\n", "commit after last push")
    state = gitstate.branch_push_state(repo)
    assert state["state"] == "unpushed-commits"
    assert state["ahead"] == "1"
    assert state["behind"] == "0"
    assert state["upstream"] == "origin/feature/x"
    assert state["head"] != state["upstream_sha"]
