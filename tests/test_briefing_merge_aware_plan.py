"""Tests for the merge-aware "delete the plan" session-briefing nudge (BRF-6K2D).

The stale-plan nudge recommended deleting a completed build plan whenever all
its chunks were checked — but a session-local plan persists across branch
switches, so it could fire while the plan's feature branch is still unmerged,
and following it would orphan live, unshipped work. ``staleness_scan`` now says
"keep until merged" instead of "delete" when the plan's work is plausibly still
unmerged (foreign-branch WIP, or the current feature branch not yet an ancestor
of the base).

Real ``git`` so ``merge-base --is-ancestor`` and branch resolution behave as in
production.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from lib import briefing  # noqa: E402


def _git_env(repo: Path) -> dict[str, str]:
    return {
        "HOME": str(repo.parent / "_home"),
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
    }


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True,
        env=_git_env(repo), check=True, timeout=10,
    )


_PLAN = """# Build Plan — Test

## Status

- [x] Chunk 01: done
- [x] Chunk 02: done
Context: all chunks landed.
"""


def _setup(tmp_path: Path, *, base_branch: str = "main", wip: str = "") -> Path:
    repo = tmp_path / "repo"
    (repo / ".prawduct" / "artifacts").mkdir(parents=True)
    _git(repo, "init", "--quiet", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".prawduct" / "project-state.yaml").write_text(
        "active_build_plan: artifacts/build-plan-test.md\n"
        f"base_branch: {base_branch}\n"
        + wip
    )
    (repo / ".prawduct" / "artifacts" / "build-plan-test.md").write_text(_PLAN)
    (repo / "app.py").write_text("print(1)\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init", "--quiet")
    return repo


def _plan_findings(repo: Path) -> list[str]:
    return [f for f in briefing.staleness_scan(repo) if "build plan:" in f]


def test_on_base_branch_merged_says_delete(tmp_path):
    # On the base branch, work merged, no foreign WIP → the plan is safe to delete.
    repo = _setup(tmp_path, base_branch="main")
    findings = _plan_findings(repo)
    assert any("all chunks complete" in f and "delete the plan" in f for f in findings), findings
    assert not any("keep the plan until it merges" in f for f in findings)


def test_feature_branch_unmerged_says_keep(tmp_path):
    # On a feature branch with a commit not in base → keep until merged.
    repo = _setup(tmp_path, base_branch="main")
    _git(repo, "checkout", "--quiet", "-b", "feature/x")
    (repo / "feature.py").write_text("x = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "feature work", "--quiet")
    findings = _plan_findings(repo)
    assert any("keep the plan until it merges" in f for f in findings), findings
    assert not any("if work is done, delete the plan" in f for f in findings)
    assert any("feature/x" in f for f in findings)


def test_foreign_branch_wip_says_keep(tmp_path):
    # On the base branch, but WIP is recorded for another (unmerged) branch —
    # the shared plan may belong to it, so keep rather than delete.
    wip = "work_in_progress:\n  feature/y:\n    description: building y\n"
    repo = _setup(tmp_path, base_branch="main", wip=wip)
    findings = _plan_findings(repo)
    assert any("keep the plan until it merges" in f for f in findings), findings
    assert any("feature/y" in f for f in findings)
    assert not any("if work is done, delete the plan" in f for f in findings)
