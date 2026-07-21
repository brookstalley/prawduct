"""Tests for the F4b coverage gate — ``prawduct-hook verify-coverage``.

Gate-soundness ch.1: the gate compares the whole branch diff (+ untracked)
against the evidence, but its producer (``bin/test-reference-verify``) can only
judge Python files with symbols — so before the ``changes_unjudged`` split,
docs/config/deleted changes failed the gate by construction on every real
branch (scriob recurrence ×3, then the product neutralized the gate by
unioning the full diff into ``changes_referenced``). These tests pin the
reconciled contract:

  * files in ``changes_unjudged`` are reported, never ``missing-coverage``
  * files deleted on the branch are never ``missing-coverage``
  * a judged file with no test reference still BLOCKS (exit 1) — the gate
    keeps its teeth where the evidence actually vouches
  * legacy evidence without the field keeps pre-split behavior (absent ⇒ empty)

The gate shipped (v1.4 F4b) with no direct test module — these are its first.
Real git repos, real hook subprocess: the gate's job is git + filesystem
inspection, and mocking either would test nothing useful.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"


def _git(repo: Path, *args: str) -> None:
    env = os.environ.copy()
    env.setdefault("GIT_AUTHOR_NAME", "test")
    env.setdefault("GIT_AUTHOR_EMAIL", "test@example.com")
    env.setdefault("GIT_COMMITTER_NAME", "test")
    env.setdefault("GIT_COMMITTER_EMAIL", "test@example.com")
    subprocess.run(
        ["git", *args], cwd=str(repo), env=env, check=True, capture_output=True
    )


def _run_gate(repo: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(repo)
    return subprocess.run(
        [sys.executable, str(HOOK), "verify-coverage"],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


def _write_evidence(repo: Path, **overrides) -> None:
    record = {
        "timestamp": "2026-06-10T10:00:00Z",
        "passed": 5,
        "failed": 0,
        "skipped": 0,
        "duration_seconds": 1.0,
        "command": "pytest",
        "verifier": "test-reference-verify (floor: symbol-grep)",
        "coverage_level": "referenced",
        "tests_executed": ["tests/test_core.py"],
        "changes_referenced": [],
        "changes_unjudged": [],
    }
    record.update(overrides)
    (repo / ".prawduct" / ".test-evidence.json").write_text(
        json.dumps(record, indent=2)
    )


@pytest.fixture
def gated_repo(tmp_path: Path) -> Path:
    """A repo with ``coverage_required: true``, one committed baseline, and a
    feature branch carrying a judged code change + a doc change."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / ".prawduct").mkdir()
    (repo / ".prawduct" / "project-state.yaml").write_text(
        "coverage_required: true\n"
    )
    (repo / "src").mkdir()
    (repo / "src" / "core.py").write_text("def helper():\n    return 1\n")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_core.py").write_text(
        "from src.core import helper\n\ndef test_helper():\n    assert helper() == 1\n"
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "baseline")
    _git(repo, "checkout", "-q", "-b", "feature/x")
    return repo


class TestUnjudgedFilesAreNotGated:
    def test_doc_change_listed_unjudged_passes(self, gated_repo: Path):
        """A branch touching code (referenced) + a doc (unjudged) passes —
        the pre-split gate false-blocked exactly this shape."""
        (gated_repo / "src" / "core.py").write_text("def helper():\n    return 2\n")
        (gated_repo / "README.md").write_text("# docs\n")
        _git(gated_repo, "add", ".")
        _git(gated_repo, "commit", "-q", "-m", "code + docs")
        _write_evidence(
            gated_repo,
            changes_referenced=["src/core.py"],
            changes_unjudged=["README.md", ".prawduct/.test-evidence.json"],
        )

        result = _run_gate(gated_repo)

        assert result.returncode == 0, result.stderr
        assert "missing-coverage" not in result.stderr
        assert "outside the verifier's judgment" in result.stdout

    def test_deleted_file_is_not_missing_coverage(self, gated_repo: Path):
        """A file deleted on the branch has nothing to test — never a
        blocker, even when the evidence doesn't list it as unjudged."""
        _git(gated_repo, "rm", "-q", "src/core.py")
        (gated_repo / "tests" / "test_core.py").write_text(
            "def test_helper_gone():\n    assert True\n"
        )
        _git(gated_repo, "add", ".")
        _git(gated_repo, "commit", "-q", "-m", "delete core")
        _write_evidence(
            gated_repo,
            changes_referenced=["tests/test_core.py"],
            changes_unjudged=[".prawduct/.test-evidence.json"],
        )

        result = _run_gate(gated_repo)

        assert "src/core.py" not in result.stderr
        assert result.returncode == 0, result.stderr


class TestJudgedGapsStillBlock:
    def test_judged_file_missing_reference_blocks(self, gated_repo: Path):
        """The gate keeps its teeth: a Python file in neither list is a real
        gap and exits 1 with the per-file missing-coverage line."""
        (gated_repo / "src" / "untested.py").write_text(
            "def lonely():\n    return None\n"
        )
        _git(gated_repo, "add", ".")
        _git(gated_repo, "commit", "-q", "-m", "untested code")
        _write_evidence(
            gated_repo,
            changes_unjudged=[".prawduct/.test-evidence.json"],
        )

        result = _run_gate(gated_repo)

        assert result.returncode == 1
        assert "missing-coverage: src/untested.py" in result.stderr

    def test_only_listed_files_are_skipped_unlisted_judged_gaps_still_block(
        self, gated_repo: Path
    ):
        """Scope of the skip: a file in changes_unjudged is taken on the
        producer's word (the gate's threat model is honest-agent guidance —
        `changes_referenced` was always equally producer-attested); the
        contract pinned here is that the skip is PER-LISTED-FILE, so an
        unlisted judged file still blocks alongside a listed one."""
        (gated_repo / "src" / "a.py").write_text("def a():\n    return 1\n")
        (gated_repo / "src" / "b.py").write_text("def b():\n    return 2\n")
        _git(gated_repo, "add", ".")
        _git(gated_repo, "commit", "-q", "-m", "two files")
        _write_evidence(
            gated_repo,
            changes_unjudged=["src/a.py", ".prawduct/.test-evidence.json"],
        )

        result = _run_gate(gated_repo)

        assert result.returncode == 1
        assert "missing-coverage: src/b.py" in result.stderr
        assert "src/a.py" not in result.stderr


class TestLegacyEvidenceCompat:
    def test_evidence_without_unjudged_field_keeps_old_behavior(
        self, gated_repo: Path
    ):
        """Product-authored evidence predating the field: absent ⇒ empty, so
        an on-disk doc file not in changes_referenced still blocks — the
        producer that doesn't declare unjudged files gets the old contract."""
        (gated_repo / "NOTES.md").write_text("notes\n")
        _git(gated_repo, "add", ".")
        _git(gated_repo, "commit", "-q", "-m", "doc only")
        _write_evidence(gated_repo, changes_referenced=[])
        # Strip the new field to simulate a legacy/product writer.
        evidence_path = gated_repo / ".prawduct" / ".test-evidence.json"
        record = json.loads(evidence_path.read_text())
        del record["changes_unjudged"]
        evidence_path.write_text(json.dumps(record))

        result = _run_gate(gated_repo)

        assert result.returncode == 1
        assert "missing-coverage: NOTES.md" in result.stderr

    def test_wrong_typed_unjudged_field_is_schema_violation(
        self, gated_repo: Path
    ):
        (gated_repo / "src" / "core.py").write_text("def helper():\n    return 3\n")
        _git(gated_repo, "add", ".")
        _git(gated_repo, "commit", "-q", "-m", "change")
        _write_evidence(
            gated_repo,
            changes_referenced=["src/core.py"],
            changes_unjudged="not-a-list",
        )

        result = _run_gate(gated_repo)

        assert result.returncode == 1
        assert "changes_unjudged" in result.stderr
