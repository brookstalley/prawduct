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
from lib import gates, gitstate  # noqa: E402


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


def test_the_no_upstream_remedy_names_the_repos_own_remote(tmp_path):
    """Not a literal `origin`. The probe reads the branch's configured upstream
    precisely so a differently-named remote gets a real answer; a remedy naming
    a remote the repo does not have undoes that in the one message an operator
    is most likely to act on."""
    repo = _repo_on_pushed_branch(tmp_path)
    _git(repo, "remote", "rename", "origin", "upstream")
    _git(repo, "checkout", "--quiet", "-b", "feature/elsewhere")
    _commit(repo, "new.py", "z = 3\n", "unpushed branch")
    r = _run(repo)
    assert r.returncode == 1
    assert "git push -u upstream feature/elsewhere" in r.stderr
    assert "origin" not in r.stderr


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
    assert state["local_sha"] != state["upstream_sha"]


# --- the branch argument: the merge flow's subject is the PR's branch ---------

def _run_for(repo: Path, branch: str) -> subprocess.CompletedProcess:
    env = dict(_git_env(repo))
    env["CLAUDE_PROJECT_DIR"] = str(repo)
    return subprocess.run(
        ["python3", str(HOOK), "check-branch-pushed", branch],
        cwd=str(repo), capture_output=True, text=True, env=env, timeout=30,
    )


def test_a_named_branch_is_the_subject_not_the_checked_out_one(tmp_path):
    """The merge-flow defect: a merge run from the base branch asked the
    argument-less gate, which answered about the base. Both answers are true and
    only one is about the PR, so a green verdict read as "this PR is pushed"."""
    repo = _repo_on_pushed_branch(tmp_path)
    _commit(repo, "late.py", "y = 2\n", "commit after last push")  # feature/x is behind
    _git(repo, "checkout", "--quiet", "main")
    _git(repo, "push", "--quiet", "-u", "origin", "main")

    checked_out = _run(repo)
    assert checked_out.returncode == 0, "main is genuinely pushed"

    the_prs_branch = _run_for(repo, "feature/x")
    assert the_prs_branch.returncode == 1
    assert "unpushed-commits" in the_prs_branch.stderr
    assert "feature/x" in the_prs_branch.stderr


def test_a_branch_this_clone_does_not_have_is_a_pass_that_says_what_it_certified(tmp_path):
    """A fork PR, or one nobody here checked out. There is no local commit to be
    dropped, so blocking would be a false block on every fork — but the message
    must not let that read as certifying the PR head."""
    repo = _repo_on_pushed_branch(tmp_path)
    r = _run_for(repo, "contributor/from-a-fork")
    assert r.returncode == 0
    assert "no-local-branch" in r.stdout
    assert "headRefOid" in r.stdout
    assert "still owed" in r.stdout


def test_a_named_branch_in_an_unreadable_repo_is_not_a_pass(tmp_path):
    """`rev-parse --verify refs/heads/<name>` exits 128 for BOTH "no such branch" and
    "not a git repository", so the named-branch path cannot read its own failure without
    a probe that proves the repo is readable first. Without one, a broken repo answers
    `no-local-branch` — exit 0 — which is an unreadable subject reported as a pass, the
    defect this gate exists to close, on the path the Merge Flow uses."""
    outside = tmp_path / "not-a-repo"
    outside.mkdir()
    state = gitstate.branch_push_state(outside, "feature/x")
    assert state["state"] == "git-failed", (
        "a named branch in a non-repo must not read as `no-local-branch`"
    )
    assert gates.check_branch_pushed(outside, "feature/x") == 3


def test_a_git_that_cannot_run_is_not_a_pass_on_the_named_branch_path(tmp_path):
    """The OTHER half of the named-branch guard, and independently falsifiable.

    Two distinct failures reach the same line: git RAN and exited 128 (no such
    branch, pinned above), and git could not be run at all — `_git_text`'s own
    `-1`, from a missing binary or the timeout. Without its own guard, `-1`
    falls into `ref_code != 0` and answers `no-local-branch` at exit 0. No
    fixture can produce it, because a fixture that makes git fail makes it fail
    for the HEAD probe too, which is a different verdict; the stub lets the
    probe through and fails only the ref lookup.
    """
    repo = _repo_on_pushed_branch(tmp_path)
    real = gitstate._git_text

    def _fail_ref_lookup(project_dir, *args):
        if args[:2] == ("rev-parse", "--verify") and args[2].startswith("refs/heads/"):
            return (-1, "", "FileNotFoundError('git')")
        return real(project_dir, *args)

    try:
        gitstate._git_text = _fail_ref_lookup
        state = gitstate.branch_push_state(repo, "feature/x")
        exit_code = gates.check_branch_pushed(repo, "feature/x")
    finally:
        gitstate._git_text = real
    assert state["state"] == "git-failed", (
        "a git that could not be run must not read as `no-local-branch`"
    )
    assert "git" in state["detail"]
    assert exit_code == 3


def test_a_named_detached_repo_still_answers(tmp_path):
    """Detachment is only fatal when nothing names the subject — the argument is
    the remedy the detached-head message offers, so it has to work."""
    repo = _repo_on_pushed_branch(tmp_path)
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _git(repo, "checkout", "--quiet", head)
    assert _run(repo).returncode == 3
    assert _run_for(repo, "feature/x").returncode == 0


# --- the two degradation paths, which no fixture can reach ------------------

def test_an_unreadable_count_does_not_change_the_verdict(tmp_path):
    """Design constraint: ancestry decides, counts only describe. The two agree
    on every readable repo, so this is the ONLY case that tells a counts-based
    classifier from an ancestry-based one — and `"?"` is exactly what a counts
    comparison mis-handles, turning `unpushed-commits` into `diverged`."""
    repo = _repo_on_pushed_branch(tmp_path)
    _commit(repo, "late.py", "y = 2\n", "commit after last push")
    real = gitstate._rev_count
    try:
        gitstate._rev_count = lambda *a, **k: "?"
        state = gitstate.branch_push_state(repo)
    finally:
        gitstate._rev_count = real
    assert state["state"] == "unpushed-commits"
    assert state["ahead"] == "?" and state["behind"] == "?"


def test_unreadable_ancestry_is_the_third_outcome_not_a_confident_diverged(tmp_path):
    """`--is-ancestor` exits 0 for yes, 1 for no, and 128 (or the probe's own -1
    on a missing binary or a timeout) for "could not answer". Collapsing the
    third into "no" reports `diverged` — and tells the operator to integrate —
    off a history nobody read."""
    repo = _repo_on_pushed_branch(tmp_path)
    _commit(repo, "late.py", "y = 2\n", "commit after last push")
    real = gitstate._git_text

    def _fail_ancestry(project_dir, *args):
        if args[:2] == ("merge-base", "--is-ancestor"):
            return (128, "", "fatal: could not read the object store")
        return real(project_dir, *args)

    try:
        gitstate._git_text = _fail_ancestry
        state = gitstate.branch_push_state(repo)
        # The exit code is asserted UNDER the patch: outside it the ancestry probe
        # works again and the gate correctly answers 1, which is what a check written
        # after the `finally` would have measured.
        exit_code = gates.check_branch_pushed(repo)
    finally:
        gitstate._git_text = real
    assert state["state"] == "git-failed"
    assert "could not read" in state["detail"]
    assert exit_code == 3


# --- dispatch ----------------------------------------------------------------

def test_a_flag_is_refused_and_nothing_runs(tmp_path):
    """The argument is a branch name, so a flag would have been recorded AS the
    branch name and answered about a branch nobody has — a pass, on a typo."""
    repo = _repo_on_pushed_branch(tmp_path)
    env = dict(_git_env(repo))
    env["CLAUDE_PROJECT_DIR"] = str(repo)
    r = subprocess.run(
        ["python3", str(HOOK), "check-branch-pushed", "--json"],
        cwd=str(repo), capture_output=True, text=True, env=env, timeout=30,
    )
    assert r.returncode == 2
    assert "Nothing ran" in r.stderr
