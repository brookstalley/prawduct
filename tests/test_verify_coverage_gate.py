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
        an on-disk file not in changes_referenced still blocks — the producer
        that doesn't declare unjudged files gets the old contract.

        **Re-anchored from `NOTES.md` to a `.py` (COV-8R2K).** The old subject
        proved the legacy contract through a file the gate should never have
        been gating in the first place: prose is not executable, so a
        missing-coverage line on it was the defect, not the contract. The
        contract this case is named for — absent field means empty, not
        lenient — needs a subject the gate legitimately owns.
        """
        (gated_repo / "src" / "legacy.py").write_text("def legacy():\n    return 0\n")
        _git(gated_repo, "add", ".")
        _git(gated_repo, "commit", "-q", "-m", "undeclared code")
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


class TestNonExecutableFilesAreNotGated:
    """COV-8R2K — the floor measures whether a test REFERENCES a file, so it
    may only be applied to files a test could execute.

    The floor is a symbol grep. Applied to prose it demands a reference that
    can only be satisfied by a token test naming the file, and
    `review-protocol.md` Goal 1 records a missing-coverage line as BLOCKING per
    file with no softening — so a chunk whose deliverables legitimately include
    a `.md` had no honest way through.

    **Reachable, despite looking dormant.** A freshly-run stock
    `bin/test-reference-verify` routes non-Python into `changes_unjudged`,
    which masks the symptom. The gate recomputes `changed` at gate time,
    independently of when the evidence was written, so any misalignment reopens
    it: evidence written before a doc edit, product-authored evidence, legacy
    evidence with no field, or a `coverage_level: executed` verifier. These
    fixtures reproduce that window by declaring nothing unjudged.
    """

    def test_a_prose_file_is_a_note_not_a_blocker(self, gated_repo: Path):
        (gated_repo / "NOTES.md").write_text("notes\n")
        _git(gated_repo, "add", ".")
        _git(gated_repo, "commit", "-q", "-m", "doc only")
        _write_evidence(gated_repo, changes_referenced=[], changes_unjudged=[])

        result = _run_gate(gated_repo)

        assert result.returncode == 0, result.stderr
        assert "missing-coverage" not in result.stderr
        assert "no test can execute" in result.stdout
        assert "NOTES.md" in result.stdout, (
            "reported, not gated — a silent exemption teaches the operator "
            "nothing about why the file was let through"
        )

    def test_framework_state_is_a_note_not_a_blocker(self, gated_repo: Path):
        """The item's second repro: a branch editing `project-state.yaml` on an
        otherwise-clean tree exited 1 with a missing-coverage line."""
        (gated_repo / ".prawduct" / "project-state.yaml").write_text(
            "coverage_required: true\nproject_name: x\n"
        )
        _git(gated_repo, "add", ".")
        _git(gated_repo, "commit", "-q", "-m", "state edit")
        _write_evidence(gated_repo, changes_referenced=[], changes_unjudged=[])

        result = _run_gate(gated_repo)

        assert result.returncode == 0, result.stderr
        assert "missing-coverage" not in result.stderr

    def test_a_governance_protected_md_is_also_not_executable(
        self, gated_repo: Path
    ):
        """Protection makes fork-skill prose review-worthy, which is a
        different claim from testable. A second suffix table would have had to
        answer this one way; deriving it from `is_judgeable_path` plus the
        single `.md` clause answers it correctly."""
        (gated_repo / "methodology").mkdir()
        (gated_repo / "methodology" / "building.md").write_text("# build\n")
        _git(gated_repo, "add", ".")
        _git(gated_repo, "commit", "-q", "-m", "governance prose")
        _write_evidence(gated_repo, changes_referenced=[], changes_unjudged=[])

        result = _run_gate(gated_repo)

        assert result.returncode == 0, result.stderr
        assert "missing-coverage" not in result.stderr

    def test_the_gate_keeps_its_teeth_on_a_mixed_change(self, gated_repo: Path):
        """The true-positive guard. Without it the exemption above could be a
        gate that stopped gating: an uncovered `.py` shipped beside the prose
        must still block, and must still be named."""
        (gated_repo / "NOTES.md").write_text("notes\n")
        (gated_repo / "src" / "untested.py").write_text("def lonely():\n    return 1\n")
        _git(gated_repo, "add", ".")
        _git(gated_repo, "commit", "-q", "-m", "prose + untested code")
        _write_evidence(gated_repo, changes_referenced=[], changes_unjudged=[])

        result = _run_gate(gated_repo)

        assert result.returncode == 1
        assert "missing-coverage: src/untested.py" in result.stderr
        assert "missing-coverage: NOTES.md" not in result.stderr

    def test_a_product_owned_config_file_still_gates(self, gated_repo: Path):
        """The recorded residual, pinned so it is a decision and not a silent
        gap: a non-code config OUTSIDE the metadata boundary is still
        executable by this reading and still blocks. Closing it needs the
        `coverage_exempt_paths:` knob COV-6T3P asks the owner for."""
        (gated_repo / "config").mkdir()
        (gated_repo / "config" / "app.yaml").write_text("debug: true\n")
        _git(gated_repo, "add", ".")
        _git(gated_repo, "commit", "-q", "-m", "config")
        _write_evidence(gated_repo, changes_referenced=[], changes_unjudged=[])

        result = _run_gate(gated_repo)

        assert result.returncode == 1
        assert "missing-coverage: config/app.yaml" in result.stderr

    def test_the_unjudged_declaration_still_takes_precedence(
        self, gated_repo: Path
    ):
        """Bucket order is asserted rather than assumed: a file the verifier
        disclaimed is out of jurisdiction whatever its suffix, so it is
        reported by the `skipped` note and counted once, not twice."""
        (gated_repo / "NOTES.md").write_text("notes\n")
        _git(gated_repo, "add", ".")
        _git(gated_repo, "commit", "-q", "-m", "doc only")
        _write_evidence(
            gated_repo, changes_referenced=[], changes_unjudged=["NOTES.md"]
        )

        result = _run_gate(gated_repo)

        assert result.returncode == 0, result.stderr
        assert "outside the verifier's judgment" in result.stdout
        nonexec_lines = [
            line for line in result.stdout.splitlines()
            if "no test can execute" in line
        ]
        assert all("NOTES.md" not in line for line in nonexec_lines), (
            "a disclaimed file counted in both buckets would be reported twice "
            "and subtracted twice from the covered count"
        )
        assert "ok: 0 judged changed file(s) covered" in result.stdout
