"""Regression pins for two `bin/prawduct-hook` behaviors that were verified by
hand during discodon-upstream-defects and never tested (#228), so a regression
collapsing either would have passed CI.

1. ``cmd_verify_chunk_refs`` keeps its ``cannot-verify:`` exit message distinct
   from its ``missing-ref:`` one. The distinction is the whole point: "the
   Goal-2 deliverable check could not RUN" and "a named deliverable is missing"
   are different signals, and collapsing them lets a can't-parse exit be
   dismissed as noise while masking a real missing-deliverable BLOCKING.
2. ``cmd_critic_begin`` renders a sibling worktree that has no branch. Git emits
   ``bare`` — neither a ``branch`` nor a ``detached`` line — for a bare main
   worktree, so the entry carries no ``branch`` key at all and an unguarded read
   would raise at dispatch time.

Both behaviors are correct today and neither is changed here; the gap was
coverage. The bare-repo shape is built with real git rather than a stubbed
worktree list, because the guard exists for what git actually emits.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent / "plugin"

# Load the extensionless hook (SourceFileLoader — shebang script, no .py
# extension; the module name is not "__main__", so CLI dispatch stays inert).
_loader = importlib.machinery.SourceFileLoader(
    "prawduct_hook_cli_regressions", str(_ROOT / "bin" / "prawduct-hook")
)
_spec = importlib.util.spec_from_loader("prawduct_hook_cli_regressions", _loader)
_hook = importlib.util.module_from_spec(_spec)
_loader.exec_module(_hook)


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0, f"git {args} failed: {proc.stderr}"
    return proc.stdout.strip()


def _plan_repo(tmp_path: Path, plan_body: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "code.py").write_text("x = 1\n")
    artifacts = repo / ".prawduct" / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "build-plan.md").write_text(plan_body)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c1")
    return repo


_ONE_CHUNK_PLAN = """# Build Plan

## Status

- [ ] Chunk 01: the only chunk

## Build Chunks

### Chunk 01: the only chunk

- **Deliverables:** `plugin/lib/no_such_module_here.py`
"""


class TestVerifyChunkRefsExitMessagesStayDistinct:
    """Both paths exit 1, so the exit code cannot tell them apart and the text
    is the whole signal. Asserted as mutual exclusion — each message carries its
    own prefix and NOT the other's — because that is what actually goes red when
    the branches collapse: merely asserting the two strings differ survives a
    real collapse, since the interpolated detail differs either way."""

    def test_unparseable_chunk_says_the_check_did_not_run(self, tmp_path, capsys):
        repo = _plan_repo(tmp_path, _ONE_CHUNK_PLAN)

        rc = _hook.cmd_verify_chunk_refs(repo, "07")  # no such chunk section
        err = capsys.readouterr().err

        assert rc == 1
        assert "cannot-verify:" in err
        assert "missing-ref:" not in err
        # The distinction is only useful if it says WHY the check could not run.
        assert "did not run" in err

    def test_absent_deliverable_says_a_ref_is_missing(self, tmp_path, capsys):
        repo = _plan_repo(tmp_path, _ONE_CHUNK_PLAN)

        rc = _hook.cmd_verify_chunk_refs(repo, "01")
        err = capsys.readouterr().err

        assert rc == 1
        assert "missing-ref:" in err
        assert "cannot-verify:" not in err
        assert "no_such_module_here.py" in err  # names the deliverable, not the plan

class TestCriticBeginRendersABranchlessSiblingWorktree:
    """Driven as a real CLI in a real bare-repo worktree, not in-process:
    ``critic-begin`` refuses outright when the shell's cwd differs from the
    resolved project dir (a deliberate wrong-tree guard), so an in-process call
    never reaches the sibling listing this pins."""

    def test_bare_main_worktree_renders_without_raising(self, tmp_path):
        """A linked worktree whose MAIN worktree is bare: `git worktree list
        --porcelain` emits `bare` for that entry, so it has no `branch` key and
        the sibling-listing read must fall back rather than raise."""
        src = tmp_path / "src"
        src.mkdir()
        _git(src, "init", "-q", "-b", "main")
        (src / "code.py").write_text("x = 1\n")
        _git(src, "add", "-A")
        _git(src, "commit", "-q", "-m", "c1")

        bare = tmp_path / "bare.git"
        subprocess.run(
            ["git", "clone", "-q", "--bare", str(src), str(bare)],
            capture_output=True, text=True, timeout=30, check=True,
        )
        work = tmp_path / "wt"
        _git(bare, "worktree", "add", "-q", str(work), "main")

        # Guard the premise: against a sibling that HAS a branch this test would
        # pass without ever reaching the fallback it exists to exercise.
        from lib import briefing  # noqa: PLC0415 — after sys.path is set by _hook

        siblings = [
            w for w in briefing._detect_worktrees(work) if w.get("is_active") != "true"
        ]
        assert siblings, "expected the bare main worktree to be listed as a sibling"
        assert all("branch" not in w for w in siblings), siblings

        (work / ".prawduct").mkdir()
        (work / "code.py").write_text("x = 2\n")  # chunk mode reviews a live diff

        proc = subprocess.run(
            [
                "python3", str(_ROOT / "bin" / "prawduct-hook"),
                "critic-begin", "--mode", "chunk", "--chosen-by", "test",
            ],
            cwd=str(work),
            capture_output=True,
            text=True,
            timeout=60,
            env={
                "CLAUDE_PROJECT_DIR": str(work),
                "CLAUDE_PLUGIN_ROOT": str(_ROOT),
                "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
                "HOME": str(tmp_path / "_home"),
                "PYTHONDONTWRITEBYTECODE": "1",
            },
        )

        assert proc.returncode == 0, proc.stderr
        assert "other worktree(s) on this repo" in proc.stdout
        assert "[?]" in proc.stdout  # the branchless entry rendered via its fallback
