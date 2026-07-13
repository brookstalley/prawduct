"""End-to-end reproduction scenarios for the kernel-v3 gate cutover (ch.04).

Discovery success criterion 2, verbatim: the two defect sequences that
motivated the redesign must pass against the REAL plugin surface — the
repo-local ``bin/prawduct-hook`` driving the full dispatch → partial →
consolidate → gate pipeline in a scratch git repo (no in-process shortcuts,
no hand-written facts):

* **CRT-J4PM** — chunk-mode reviews recorded per-chunk (pre-commit, committed
  verbatim) compose across commits, and ``check-cumulative-critic`` passes at
  HEAD with NO cumulative-labeled review ever run. In v2 the gate demanded a
  record whose mode LABEL matched, so this exact history forced a redundant
  full re-review.

* **CRT-5D8Q** — the metadata-boundary deadlock cannot occur. In v2, two
  predicates drew the metadata boundary differently: ``_record_covers_head``
  exempted only ``.md`` (a committed ``.prawduct/`` state file made the
  record "stale") while the verify-resolutions scope helper filtered metadata
  out (so the recommended remedy could never re-cover it) — a wedge with no
  exit. In v3 ONE predicate (``coverage_algebra.is_judgeable_path``) answers
  both gates: a metadata-only tail is a free edge and the gate passes; a
  judgeable tail still blocks and the verify-resolutions flow genuinely
  clears it (the exit exists).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
HOOK = ROOT / "bin" / "prawduct-hook"


# ---------------------------------------------------------------------------
# Harness — everything through subprocess, like production
# ---------------------------------------------------------------------------


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


def _hook(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(HOOK), *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=30,
        env={
            "CLAUDE_PROJECT_DIR": str(repo),
            "CLAUDE_PLUGIN_ROOT": str(ROOT),
            "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
            "HOME": str(repo.parent / "_home"),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    )


def _scratch_repo(tmp_path: Path) -> Path:
    (tmp_path / "_home").mkdir(exist_ok=True)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / ".gitignore").write_text(
        ".prawduct/.session-*\n.prawduct/.critic-*\n.prawduct/.gates-waived\n"
    )
    (repo / "code.py").write_text("x = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c1")
    (repo / ".prawduct").mkdir()
    _git(repo, "checkout", "-q", "-b", "feature")
    return repo


def _write_edit(repo: Path, rel: str, content: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _run_review(repo: Path, mode: str, *, findings: "list[dict] | None" = None) -> None:
    """One full review cycle exactly as the skill drives it: critic-begin
    (code-written manifest) → the single-pass reviewer partial → deterministic
    critic-consolidate."""
    begin = _hook(repo, "critic-begin", "--mode", mode, "--chosen-by", "scenario")
    assert begin.returncode == 0, begin.stderr
    manifest = json.loads(
        (repo / ".prawduct" / ".critic-partials" / "manifest.json").read_text()
    )
    assert manifest["roster"] == ["reviewer"], manifest["roster"]
    partial = {
        "role": "reviewer",
        "goals": ["Nothing Is Broken", "Nothing Is Missing", "Nothing Is Unintended"],
        "commit_reviewed": manifest["commit_reviewed"],
        "model": None,
        "duration_seconds": 1,
        "findings": findings or [],
        "summary": "scenario review",
    }
    (repo / ".prawduct" / ".critic-partials" / "reviewer.json").write_text(
        json.dumps(partial)
    )
    consolidate = _hook(repo, "critic-consolidate")
    assert consolidate.returncode == 0, consolidate.stderr


def _commit_all(repo: Path, msg: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)


def _gate(repo: Path) -> subprocess.CompletedProcess:
    return _hook(repo, "check-cumulative-critic")


# ---------------------------------------------------------------------------
# CRT-J4PM — composition replaces mode-label matching
# ---------------------------------------------------------------------------


class TestCrtJ4pmReproduction:
    def test_chunk_reviews_compose_to_pass_the_pr_gate_with_no_rerun(self, tmp_path):
        repo = _scratch_repo(tmp_path)

        # Chunk 1: edit → chunk review on the dirty tree → commit verbatim.
        _write_edit(repo, "feature.py", "y = 1\n")
        _run_review(repo, "chunk")
        _commit_all(repo, "chunk 1")

        # Chunk 2: same cycle again.
        _write_edit(repo, "more.py", "z = 1\n")
        _run_review(repo, "chunk")
        _commit_all(repo, "chunk 2")

        # The v2 defect: gate demanded a cumulative-labeled record and failed
        # here, forcing a redundant bundle re-review. v3: the two chunk facts
        # compose merge-base tree → HEAD tree — pass, no re-run.
        result = _gate(repo)
        assert result.returncode == 0, (
            f"CRT-J4PM repro must pass with no cumulative re-run.\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
        )
        assert "satisfied" in result.stdout
        assert "2 review fact(s)" in result.stdout

    def test_gate_passes_from_a_second_worktree(self, tmp_path):
        # The store is per-clone (D1): evidence recorded in the primary
        # checkout vouches for the same trees from a linked worktree.
        repo = _scratch_repo(tmp_path)
        _write_edit(repo, "feature.py", "y = 1\n")
        _run_review(repo, "chunk")
        _commit_all(repo, "chunk 1")

        wt = tmp_path / "wt"
        _git(repo, "worktree", "add", "-q", str(wt), "feature^0")
        (wt / ".prawduct").mkdir(exist_ok=True)
        result = _gate(wt)
        assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# CRT-5D8Q — one predicate, no metadata-boundary deadlock
# ---------------------------------------------------------------------------


class TestCrt5d8qReproduction:
    def test_metadata_only_tail_cannot_wedge_the_gate(self, tmp_path):
        repo = _scratch_repo(tmp_path)
        _write_edit(repo, "feature.py", "y = 1\n")
        _run_review(repo, "chunk")
        _commit_all(repo, "chunk 1")
        assert _gate(repo).returncode == 0

        # The v2 deadlock trigger: a committed non-.md METADATA change after
        # the review. _record_covers_head called it stale (non-.md), while
        # the verify-scope helper filtered it out (metadata) — no review the
        # gate recommended could ever re-cover it. v3: metadata is never
        # judgeable, the interval is a free edge, the gate stays green.
        _write_edit(repo, ".prawduct/project-state.yaml", "product_identity:\n  name: X\n")
        _commit_all(repo, "state bookkeeping")
        result = _gate(repo)
        assert result.returncode == 0, (
            f"metadata-only tail must not wedge the gate (CRT-5D8Q).\n"
            f"stderr={result.stderr!r}"
        )

    def test_judgeable_tail_blocks_and_verify_resolutions_genuinely_clears_it(self, tmp_path):
        # The contrast half: a judgeable tail still blocks (no silent
        # carveout), and the remedy the message names actually works — the
        # exit that v2's deadlock lacked.
        repo = _scratch_repo(tmp_path)
        _write_edit(repo, "feature.py", "y = 1\n")
        _run_review(repo, "chunk")
        _commit_all(repo, "chunk 1")

        _write_edit(repo, "hotfix.py", "h = 1\n")
        _commit_all(repo, "unreviewed hotfix")
        blocked = _gate(repo)
        assert blocked.returncode == 1
        assert "uncovered" in blocked.stderr
        assert "verify-resolutions" in blocked.stderr

        _run_review(repo, "verify-resolutions")
        cleared = _gate(repo)
        assert cleared.returncode == 0, (
            f"the named remedy must clear the gate.\nstderr={cleared.stderr!r}"
        )
