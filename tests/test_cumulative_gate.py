"""Tests for the cumulative-Critic PR gate — ``prawduct-hook check-cumulative-critic``.

CRT-7M2D: the gate judges a cumulative-Critic record by COMMIT-COVERAGE, not by
mtime-recency. A record satisfies the gate iff it is a clean, schema-valid,
cumulative-mode record whose ``commit_reviewed`` covers HEAD — meaning either
``commit_reviewed == HEAD`` OR the only files changed since are documentation
(``.md``). This kills two prior defects of the mtime-vs-``.session-start`` check:

  * **False-pass:** a record from this session whose ``commit_reviewed`` predated
    real code changes still passed (mtime was fresh). Now it FAILS.
  * **Treadmill:** every inert post-review fix moved HEAD past ``commit_reviewed``,
    forcing a full ``/prawduct:critic cumulative`` re-run. A doc-only delta now
    does NOT — coverage holds.

These tests had no predecessor — the gate shipped (v1.4 F2) with zero direct
coverage. Uses real ``git`` repos so ``rev-parse`` / ``diff`` behave as in
production (mock-git would diverge on commit resolution and name-only diffs).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "bin" / "prawduct-hook"
CUMULATIVE_MODE = "cumulative (bundle review, ready for merge)"
CHUNK_MODE = "chunk (lighter pass, not ready for push)"


# ---------------------------------------------------------------------------
# Helpers (real git, sterile env — mirrors test_critic_mode_inference.py)
# ---------------------------------------------------------------------------


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


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "--quiet", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")


def _commit_file(repo: Path, rel: str, content: str, msg: str) -> str:
    """Write one file, stage ONLY it, commit. Returns the new HEAD sha.

    Targeted ``git add <rel>`` (not ``-A``) so an untracked
    ``.prawduct/.critic-findings.json`` never lands in a commit and pollutes the
    ``commit_reviewed..HEAD`` diff the gate inspects.
    """
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    _git(repo, "add", rel)
    _git(repo, "commit", "-m", msg, "--quiet")
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _write_findings(
    repo: Path,
    *,
    commit_reviewed: str | None,
    mode: str = CUMULATIVE_MODE,
    blocking: bool = False,
    include_commit: bool = True,
) -> None:
    """Write an UNtracked ``.prawduct/.critic-findings.json`` for the gate."""
    data: dict = {
        "mode": mode,
        "files_reviewed": ["app.py"],
        "findings": (
            [{"goal": "Nothing Is Broken", "severity": "blocking", "summary": "boom"}]
            if blocking else []
        ),
        "summary": "Cumulative review.",
    }
    if include_commit:
        data["commit_reviewed"] = commit_reviewed
    prawduct = repo / ".prawduct"
    prawduct.mkdir(parents=True, exist_ok=True)
    (prawduct / ".critic-findings.json").write_text(json.dumps(data))


def _run_gate(repo: Path) -> subprocess.CompletedProcess:
    env = dict(_git_env(repo))
    env["CLAUDE_PROJECT_DIR"] = str(repo)
    return subprocess.run(
        ["python3", str(HOOK), "check-cumulative-critic"],
        cwd=str(repo), capture_output=True, text=True, env=env, timeout=30,
    )


# ---------------------------------------------------------------------------
# Coverage: the satisfying cases
# ---------------------------------------------------------------------------


def test_covers_head_exactly_passes(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    head = _commit_file(repo, "app.py", "print(1)\n", "init")
    _write_findings(repo, commit_reviewed=head)
    r = _run_gate(repo)
    assert r.returncode == 0, r.stderr
    assert "satisfied" in r.stdout and "covers HEAD" in r.stdout


def test_doc_only_delta_since_review_still_covered(tmp_path):
    # THE treadmill fix: HEAD moved past commit_reviewed but only a .md changed,
    # so the clean cumulative verdict still vouches for the code → no re-run.
    repo = tmp_path / "repo"
    _init_repo(repo)
    reviewed = _commit_file(repo, "app.py", "print(1)\n", "code")
    _commit_file(repo, "README.md", "# docs\n", "docs after review")  # HEAD moves
    _write_findings(repo, commit_reviewed=reviewed)
    r = _run_gate(repo)
    assert r.returncode == 0, f"doc-only delta must stay covered; stderr={r.stderr}"
    assert "satisfied" in r.stdout
    assert "stale" not in (r.stdout + r.stderr)


# ---------------------------------------------------------------------------
# Coverage: the failing cases (honest)
# ---------------------------------------------------------------------------


def test_code_delta_since_review_is_stale(tmp_path):
    # THE false-pass fix: a non-doc change since the review means the verdict no
    # longer covers the code being shipped → the gate must FAIL (re-run needed).
    repo = tmp_path / "repo"
    _init_repo(repo)
    reviewed = _commit_file(repo, "app.py", "print(1)\n", "code")
    _commit_file(repo, "core.py", "x = 2\n", "more code after review")  # HEAD moves
    _write_findings(repo, commit_reviewed=reviewed)
    r = _run_gate(repo)
    assert r.returncode == 1
    assert "stale" in r.stderr and "core.py" in r.stderr


def test_blocking_finding_fails(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    head = _commit_file(repo, "app.py", "print(1)\n", "init")
    _write_findings(repo, commit_reviewed=head, blocking=True)
    r = _run_gate(repo)
    assert r.returncode == 1
    assert "blocking" in r.stderr


def test_missing_commit_reviewed_fails(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    _commit_file(repo, "app.py", "print(1)\n", "init")
    _write_findings(repo, commit_reviewed=None, include_commit=False)
    r = _run_gate(repo)
    assert r.returncode == 1
    assert "no-commit-reviewed" in r.stderr


def test_unresolved_commit_reviewed_fails(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    _commit_file(repo, "app.py", "print(1)\n", "init")
    _write_findings(repo, commit_reviewed="0" * 40)  # well-formed but absent sha
    r = _run_gate(repo)
    assert r.returncode == 1
    assert "unresolved-commit" in r.stderr


def test_wrong_mode_fails(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    head = _commit_file(repo, "app.py", "print(1)\n", "init")
    _write_findings(repo, commit_reviewed=head, mode=CHUNK_MODE)
    r = _run_gate(repo)
    assert r.returncode == 1
    assert "wrong-mode" in r.stderr
    # Gate-soundness ch.4: the message teaches the sequencing rule that was
    # previously only learnable by paying a full cumulative re-review
    # (verify-resolutions can't certify the bundle; non-.md fixes land first).
    assert "verify-resolutions" in r.stderr
    assert "non-.md" in r.stderr


def test_missing_findings_file_fails(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    _commit_file(repo, "app.py", "print(1)\n", "init")
    (repo / ".prawduct").mkdir()  # no .critic-findings.json
    r = _run_gate(repo)
    assert r.returncode == 1
    assert "missing" in r.stderr
