"""Shared subprocess harness for the kernel-v3 end-to-end scenario files.

Everything drives the REAL plugin surface — the repo-local
``bin/prawduct-hook`` via subprocess in a scratch git repo (no in-process
shortcuts, no hand-written facts) — because the scenarios exist to prove
the production pipeline, not a simulation of it. Extracted verbatim from
``test_kernel_v3_gate_cutover.py`` when chunk 06 added a second scenario
file (``test_kernel_v3_upgrade.py``); the assertions live with the
scenarios, only the plumbing lives here.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"


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


def _hook(repo: Path, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(HOOK), *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=30,
        input=stdin,
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
    # Mirrors the product-repo gitignore contract (core.GITIGNORE_ENTRIES)
    # for every session/derived file these scenarios can produce, so
    # working-tree footprint assertions see what a real consumer would.
    (repo / ".gitignore").write_text(
        ".prawduct/.session-*\n"
        ".prawduct/.critic-*\n"
        ".prawduct/.gates-waived\n"
        ".prawduct/.governance-ledger.jsonl\n"
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
