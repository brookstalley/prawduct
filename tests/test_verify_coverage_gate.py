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

from lib.coverage import coverage_exempt_globs, is_non_executable_path

ROOT = Path(__file__).resolve().parent.parent
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


class TestNonExecutableFilesAreExempt:
    """COV-8R2K: prose docs + non-code config are exempt from the symbol-grep
    floor — reported as an informational NOTE, never BLOCKING — so a doc/config
    change on an otherwise-clean tree no longer forces a waiver or a token
    reference-test. The floor keeps its teeth on executable files."""

    def test_md_only_change_passes_as_note(self, gated_repo: Path):
        (gated_repo / "docs.md").write_text("# new docs\n")
        _git(gated_repo, "add", ".")
        _git(gated_repo, "commit", "-q", "-m", "docs only")
        _write_evidence(gated_repo, changes_referenced=[], changes_unjudged=[])

        result = _run_gate(gated_repo)

        assert result.returncode == 0, result.stderr
        assert "missing-coverage" not in result.stderr
        assert "non-executable" in result.stdout  # reported, not gated

    def test_yaml_only_change_passes(self, gated_repo: Path):
        (gated_repo / "config.yaml").write_text("key: value\n")
        _git(gated_repo, "add", ".")
        _git(gated_repo, "commit", "-q", "-m", "config only")
        _write_evidence(gated_repo, changes_referenced=[], changes_unjudged=[])

        result = _run_gate(gated_repo)

        assert result.returncode == 0, result.stderr
        assert "missing-coverage" not in result.stderr

    def test_mixed_change_only_executable_blocks(self, gated_repo: Path):
        """A .md + .toml + an uncovered .py: only the .py BLOCKS — the
        true-positive a relaxed floor must still catch."""
        (gated_repo / "notes.md").write_text("# notes\n")
        (gated_repo / "settings.toml").write_text("a = 1\n")
        (gated_repo / "src" / "untested.py").write_text("def x():\n    return 1\n")
        _git(gated_repo, "add", ".")
        _git(gated_repo, "commit", "-q", "-m", "mixed")
        _write_evidence(gated_repo, changes_referenced=[], changes_unjudged=[])

        result = _run_gate(gated_repo)

        assert result.returncode == 1
        assert "missing-coverage: src/untested.py" in result.stderr
        assert "notes.md" not in result.stderr
        assert "settings.toml" not in result.stderr

    def test_override_glob_exempts_extra_path(self, gated_repo: Path):
        """The optional project-state ``coverage_exempt_paths`` override exempts
        a path whose extension looks executable but isn't (e.g. a generated
        .py fixture) — the anti-opinionated-default escape hatch."""
        (gated_repo / ".prawduct" / "project-state.yaml").write_text(
            "coverage_required: true\n"
            "coverage_exempt_paths:\n"
            "  - generated/*\n"
        )
        (gated_repo / "generated").mkdir()
        (gated_repo / "generated" / "schema.py").write_text("X = 1\n")
        _git(gated_repo, "add", ".")
        _git(gated_repo, "commit", "-q", "-m", "generated")
        _write_evidence(gated_repo, changes_referenced=[], changes_unjudged=[])

        result = _run_gate(gated_repo)

        assert result.returncode == 0, result.stderr
        assert "missing-coverage" not in result.stderr


class TestLegacyEvidenceCompat:
    def test_evidence_without_unjudged_field_keeps_old_behavior(
        self, gated_repo: Path
    ):
        """Product-authored evidence predating the field: absent ⇒ empty, so
        an on-disk EXECUTABLE file not in changes_referenced still blocks — the
        producer that doesn't declare unjudged files gets the old contract.
        (Uses a .py file, not a doc: COV-8R2K now exempts non-executable files
        by type regardless of the unjudged field, so a .md no longer demonstrates
        gating — the legacy-compat contract under test is the absent⇒empty
        field, which only an executable file can still exercise.)"""
        (gated_repo / "src" / "legacy.py").write_text("def legacy():\n    return 1\n")
        _git(gated_repo, "add", ".")
        _git(gated_repo, "commit", "-q", "-m", "legacy code")
        _write_evidence(gated_repo, changes_referenced=[])
        # Strip the new field to simulate a legacy/product writer.
        evidence_path = gated_repo / ".prawduct" / ".test-evidence.json"
        record = json.loads(evidence_path.read_text())
        del record["changes_unjudged"]
        evidence_path.write_text(json.dumps(record))

        result = _run_gate(gated_repo)

        assert result.returncode == 1
        assert "missing-coverage: src/legacy.py" in result.stderr

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


class TestNonExecutableClassifier:
    """Unit coverage of the pure classifier the gate routes through (COV-8R2K)."""

    @pytest.mark.parametrize(
        "path",
        ["docs.md", "config.yaml", "a.yml", "data.json", "p.toml",
         "x.ini", "y.cfg", "notes.txt", "nested/dir/README.md", "UPPER.MD"],
    )
    def test_known_non_executable_extensions(self, path: str):
        assert is_non_executable_path(path)

    @pytest.mark.parametrize("path", ["src/core.py", "run.sh", "main.go", "Makefile"])
    def test_executable_paths_are_not_exempt_by_default(self, path: str):
        assert not is_non_executable_path(path)

    def test_override_glob_exempts_matching_path(self):
        globs = ("generated/*", "vendor/*")
        assert is_non_executable_path("generated/schema.py", exempt_globs=globs)
        assert is_non_executable_path("vendor/lib.py", exempt_globs=globs)
        assert not is_non_executable_path("src/core.py", exempt_globs=globs)

    def test_exempt_globs_reads_block_list(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "coverage_required: true\n"
            "coverage_exempt_paths:\n"
            "  - generated/*\n"
            "  - 'vendor/*.py'\n"
        )
        assert coverage_exempt_globs(tmp_path) == ("generated/*", "vendor/*.py")

    def test_exempt_globs_absent_is_empty(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text("coverage_required: true\n")
        assert coverage_exempt_globs(tmp_path) == ()
