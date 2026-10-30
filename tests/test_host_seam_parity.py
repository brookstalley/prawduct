"""`tools/host-seam-parity.py` sees a difference when there is one.

The sweep's claim is "the host seam changed no hook output on real repos", so
its clean result is only worth something if the same instrument reports a
difference that exists, and refuses to call a run with nothing compared clean.
These cases run it against a throwaway governed repo:

* a plugin from well before the seam differs from the seam's commit (banner
  version, digest, briefing), so it must exit 1 and print DIFF;
* the commit before the seam and the seam's commit must match (exit 0);
* one commit given twice, two commits carrying one plugin tree, or only
  paths that are not directories, compare nothing: exit 2;
* a governed directory without git is compared, since the hooks run there;
* a linked worktree is compared without one byte of its real repository or
  worktree changing, though the Stop gate writes evidence into the git dir.

The refs are this repo's history, so the file needs it.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_history

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL = REPO_ROOT / "tools" / "host-seam-parity.py"
#: The commit the seam branched from, and the seam's own commit.
BEFORE_SEAM = "b9d9489d"
SEAM = "17f84cd6"
#: The commit after the seam's, which changed nothing under `plugin/`.
SEAM_TESTS_ONLY = "5aa0d02b"
#: Far enough back that the banner version and the digest text differ.
LONG_BEFORE = "377411d4"


def _governed_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "product"
    repo.mkdir()
    run = lambda *a: subprocess.run(  # noqa: E731
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *a],
        cwd=str(repo), capture_output=True, check=True, timeout=30,
    )
    run("init", "-q", "-b", "main")
    (repo / "app.py").write_text("x = 1\n")
    run("add", "-A")
    run("commit", "-q", "-m", "c1")
    (repo / ".prawduct").mkdir()
    return repo


def _sweep(
    tmp_path: Path, base: str, head: str, *repos: Path, extra: tuple[str, ...] = ()
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOL), "--work", str(tmp_path / "work"),
         "--base", base, "--head", head, *extra, *map(str, repos)],
        capture_output=True, text=True, timeout=600, cwd=str(REPO_ROOT),
    )


def test_a_plugin_that_differs_is_reported(tmp_path):
    repo = _governed_repo(tmp_path)
    result = _sweep(tmp_path, LONG_BEFORE, SEAM, repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "DIFF  product" in result.stdout
    assert "step `banner`" in result.stdout


def test_the_seam_matches_the_commit_before_it(tmp_path):
    repo = _governed_repo(tmp_path)
    result = _sweep(tmp_path, BEFORE_SEAM, SEAM, repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SAME  product" in result.stdout


def test_one_commit_twice_compares_nothing(tmp_path):
    repo = _governed_repo(tmp_path)
    result = _sweep(tmp_path, SEAM, SEAM, repo)
    assert result.returncode == 2
    assert "same plugin tree" in result.stderr


def test_two_commits_with_one_plugin_tree_compare_nothing(tmp_path):
    """The seam's commit and the next one differ only outside `plugin/`
    (tests, the parity tool, the change record), so their plugins are one
    tree and the sweep refuses, rather than calling the plugin equal to
    itself."""
    repo = _governed_repo(tmp_path)
    result = _sweep(tmp_path, SEAM, SEAM_TESTS_ONLY, repo)
    assert result.returncode == 2
    assert "same plugin tree" in result.stderr


def test_only_skipped_repos_compare_nothing(tmp_path):
    """Renegotiated: a directory that is not a git repo used to be the skip
    case, but the hooks run in such directories too, so the sweep now compares
    them (next test). A path that is not a directory is what is skipped."""
    missing = tmp_path / "missing"
    result = _sweep(tmp_path, BEFORE_SEAM, SEAM, missing)
    assert result.returncode == 2
    assert "SKIP  missing: not a directory" in result.stdout
    assert "nothing was compared" in result.stderr


def test_a_governed_directory_without_git_is_compared(tmp_path):
    plain = tmp_path / "plain"
    (plain / ".prawduct").mkdir(parents=True)
    result = _sweep(tmp_path, BEFORE_SEAM, SEAM, plain)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SAME  plain" in result.stdout


def _tree_digest(root: Path) -> str:
    """Every file under `root`, path and content, as one digest."""
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def test_a_linked_worktree_is_compared_without_touching_the_real_repo(tmp_path):
    repo = _governed_repo(tmp_path)
    worktree = tmp_path / "wt"
    subprocess.run(["git", "worktree", "add", "-q", "-b", "wt", str(worktree)],
                   cwd=str(repo), check=True, capture_output=True)
    (worktree / ".prawduct").mkdir(exist_ok=True)
    (worktree / "app.py").write_text("x = 2\n")  # judgeable work, so the Stop gate blocks
    before = (_tree_digest(repo / ".git"), _tree_digest(worktree))
    result = _sweep(tmp_path, BEFORE_SEAM, SEAM, worktree, extra=("--keep",))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SAME  wt" in result.stdout
    assert "hooks under " in result.stdout and "hook time: base " in result.stdout
    # Writes did happen — the Stop gate recorded its block in the COPY's git
    # dir — so the real repo being unchanged below is a real result.
    for side in ("base", "head"):
        copied_git = tmp_path / "work" / "copies" / side / "wt.repo" / ".git"
        assert (copied_git / "prawduct" / "evidence.jsonl").is_file()
    assert (_tree_digest(repo / ".git"), _tree_digest(worktree)) == before
