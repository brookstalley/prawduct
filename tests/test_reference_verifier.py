"""Tests for bin/test-reference-verify — F4a floor coverage verifier.

The verifier runs git inside a real on-disk repo, so each test builds a
miniature repo under tmp_path: init, commit a baseline, mutate / add files,
then invoke the verifier and parse its JSON output. No mocking — the
verifier's job is exactly to interact with git, and mocking that would test
nothing useful.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
VERIFIER_PATH = REPO_ROOT / "bin" / "test-reference-verify"


def _load_verifier_module():
    """Import bin/test-reference-verify as a module.

    The verifier ships as a CLI verb with no ``.py`` suffix, so the usual
    import machinery can't find it by name — load it explicitly by path. Used
    by the in-process cache tests, which need to count reads without a
    subprocess boundary in the way.
    """
    spec = importlib.util.spec_from_loader(
        "trv",
        importlib.machinery.SourceFileLoader("trv", str(VERIFIER_PATH)),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(cwd: Path, *args: str) -> None:
    env = os.environ.copy()
    env.setdefault("GIT_AUTHOR_NAME", "test")
    env.setdefault("GIT_AUTHOR_EMAIL", "test@example.com")
    env.setdefault("GIT_COMMITTER_NAME", "test")
    env.setdefault("GIT_COMMITTER_EMAIL", "test@example.com")
    subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        env=env,
        check=True,
        capture_output=True,
    )


def _run_verifier(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VERIFIER_PATH), "--repo", str(repo), *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.fixture
def mini_repo(tmp_path: Path) -> Path:
    """A baseline repo on `main` with one src file and one test that
    references it. Subsequent test methods mutate / add files on top.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    (repo / "src").mkdir()
    (repo / "src" / "core.py").write_text(
        "def existing_helper():\n    return 1\n"
    )
    (repo / "tests").mkdir()
    (repo / "tests" / "test_core.py").write_text(
        "from src.core import existing_helper\n\n"
        "def test_existing_helper():\n"
        "    assert existing_helper() == 1\n"
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "baseline")
    return repo


class TestEvidenceShape:
    """The verifier always emits the four F4a fields, in any execution path."""

    def test_default_run_prints_all_four_fields(self, mini_repo: Path):
        result = _run_verifier(mini_repo)

        assert result.returncode == 0, result.stderr
        evidence = json.loads(result.stdout)
        assert set(evidence.keys()) == {
            "verifier",
            "coverage_level",
            "tests_executed",
            "changes_referenced",
        }

    def test_coverage_level_is_referenced_floor(self, mini_repo: Path):
        """The floor verifier MUST declare ``referenced`` — products that
        plug in a stronger verifier opt into ``executed`` themselves."""
        result = _run_verifier(mini_repo)

        evidence = json.loads(result.stdout)
        assert evidence["coverage_level"] == "referenced"

    def test_verifier_string_identifies_floor(self, mini_repo: Path):
        result = _run_verifier(mini_repo)

        evidence = json.loads(result.stdout)
        # The string is what surfaces in evidence + Critic messages — make
        # sure it carries the "floor" qualifier so readers don't mistake
        # it for a real-coverage signal.
        assert "floor" in evidence["verifier"]


class TestChangedFileDetection:
    """The diff base + working-tree + untracked sources all feed
    `changes_referenced`. The whole point of the F4a check is catching
    untested NEW code, so untracked files must be visible to the verifier.
    """

    def test_modified_file_referenced(self, mini_repo: Path):
        """A changed file whose symbol appears in a test is referenced."""
        (mini_repo / "src" / "core.py").write_text(
            "def existing_helper():\n    return 2\n"
        )

        result = _run_verifier(mini_repo, "--base", "main")

        assert result.returncode == 0, result.stderr
        evidence = json.loads(result.stdout)
        assert "src/core.py" in evidence["changes_referenced"]

    def test_untracked_new_file_visible(self, mini_repo: Path):
        """Untracked files participate in the diff — this is the silent-
        failure mode the verifier exists to catch (NEW code with no test
        reference)."""
        (mini_repo / "src" / "untested.py").write_text(
            "def brand_new_thing():\n    return 'unreferenced'\n"
        )

        result = _run_verifier(mini_repo, "--base", "main")

        assert result.returncode == 0, result.stderr
        evidence = json.loads(result.stdout)
        # New file should NOT be in changes_referenced because no test
        # mentions ``brand_new_thing``.
        assert "src/untested.py" not in evidence["changes_referenced"]

    def test_untracked_file_with_test_reference_is_referenced(self, mini_repo: Path):
        """Adding both the file AND a test that references it: counted."""
        (mini_repo / "src" / "fresh.py").write_text(
            "def fresh_function():\n    return 42\n"
        )
        (mini_repo / "tests" / "test_fresh.py").write_text(
            "def test_fresh_function():\n"
            "    from src.fresh import fresh_function\n"
            "    assert fresh_function() == 42\n"
        )

        result = _run_verifier(mini_repo, "--base", "main")

        evidence = json.loads(result.stdout)
        assert "src/fresh.py" in evidence["changes_referenced"]

    def test_unchanged_file_not_in_changes(self, mini_repo: Path):
        """Files unchanged since base don't appear, even if a test
        references them."""
        # No mutation; baseline is the diff base.
        result = _run_verifier(mini_repo, "--base", "main")

        evidence = json.loads(result.stdout)
        assert evidence["changes_referenced"] == []


class TestSymbolExtraction:
    """Naive Python symbol extraction: defs + classes get matched textually."""

    def test_class_symbol_referenced(self, mini_repo: Path):
        (mini_repo / "src" / "model.py").write_text(
            "class Widget:\n    pass\n"
        )
        (mini_repo / "tests" / "test_model.py").write_text(
            "def test_widget_exists():\n"
            "    from src.model import Widget\n"
            "    assert Widget is not None\n"
        )

        result = _run_verifier(mini_repo, "--base", "main")

        evidence = json.loads(result.stdout)
        assert "src/model.py" in evidence["changes_referenced"]

    def test_async_def_extracted(self, mini_repo: Path):
        (mini_repo / "src" / "asyncio_thing.py").write_text(
            "async def async_helper():\n    return None\n"
        )
        (mini_repo / "tests" / "test_asyncio_thing.py").write_text(
            "def test_async_helper_exists():\n"
            "    from src.asyncio_thing import async_helper\n"
            "    assert callable(async_helper)\n"
        )

        result = _run_verifier(mini_repo, "--base", "main")

        evidence = json.loads(result.stdout)
        assert "src/asyncio_thing.py" in evidence["changes_referenced"]

    def test_shebang_python_script_extracts_defs(self, mini_repo: Path):
        """Files without `.py` but with a Python shebang are extracted as Python.
        Catches the `tools/foo` CLI-verb pattern (no .py suffix, fully Python)."""
        cli = mini_repo / "tools_cli"
        cli.write_text(
            "#!/usr/bin/env python3\n"
            "def cli_entry_point():\n    return 1\n"
        )
        (mini_repo / "tests" / "test_cli.py").write_text(
            "def test_cli_entry_point_exists():\n"
            "    assert 'cli_entry_point' == 'cli_entry_point'\n"
        )

        result = _run_verifier(mini_repo, "--base", "main")

        evidence = json.loads(result.stdout)
        assert "tools_cli" in evidence["changes_referenced"]

    def test_non_python_file_uses_stem(self, mini_repo: Path):
        """A non-Python changed file is "referenced" iff some test mentions
        the filename stem. This is the floor heuristic; products with
        non-trivial config-file coverage concerns plug in a stronger
        verifier."""
        (mini_repo / "config.yaml").write_text("key: value\n")
        (mini_repo / "tests" / "test_config.py").write_text(
            "def test_config_loads():\n"
            "    assert 'config' in 'open config.yaml here'\n"
        )

        result = _run_verifier(mini_repo, "--base", "main")

        evidence = json.loads(result.stdout)
        assert "config.yaml" in evidence["changes_referenced"]


class TestOutputModes:
    """--output and --merge-into write modes."""

    def test_output_writes_standalone_file(self, mini_repo: Path):
        out = mini_repo / "coverage.json"

        result = _run_verifier(mini_repo, "--base", "main", "--output", str(out))

        assert result.returncode == 0, result.stderr
        evidence = json.loads(out.read_text())
        assert "verifier" in evidence
        assert "coverage_level" in evidence
        # When using --output, only the F4a fields are written — fingerprint
        # fields are the test runner's job to merge.
        assert "timestamp" not in evidence

    def test_merge_into_overlays_existing_evidence(self, mini_repo: Path):
        """--merge-into preserves fingerprint fields while adding F4a fields,
        producing schema-valid coverage evidence in one file."""
        existing = mini_repo / ".test-evidence.json"
        existing.write_text(
            json.dumps({
                "timestamp": "2026-05-18T10:00:00Z",
                "passed": 10,
                "failed": 0,
                "skipped": 0,
                "duration_seconds": 1,
                "command": "pytest",
            })
        )

        result = _run_verifier(
            mini_repo, "--base", "main", "--merge-into", str(existing)
        )

        assert result.returncode == 0, result.stderr
        merged = json.loads(existing.read_text())
        # Fingerprint preserved
        assert merged["passed"] == 10
        assert merged["command"] == "pytest"
        # F4a overlaid
        assert merged["verifier"]
        assert merged["coverage_level"] == "referenced"
        assert "tests_executed" in merged
        assert "changes_referenced" in merged

    def test_merge_into_missing_file_errors(self, mini_repo: Path):
        result = _run_verifier(
            mini_repo, "--base", "main", "--merge-into", str(mini_repo / "nope.json")
        )

        assert result.returncode == 1
        assert "merge-into failed" in result.stderr

    def test_output_and_merge_into_mutually_exclusive(self, mini_repo: Path):
        result = _run_verifier(
            mini_repo, "--output", "a.json", "--merge-into", "b.json"
        )

        assert result.returncode == 1
        assert "mutually exclusive" in result.stderr


class TestBaseResolution:
    """The diff base picker — explicit --base, auto-detection, failure modes."""

    def test_explicit_base_resolves(self, mini_repo: Path):
        result = _run_verifier(mini_repo, "--base", "main")

        assert result.returncode == 0, result.stderr

    def test_nonexistent_base_errors(self, mini_repo: Path):
        result = _run_verifier(mini_repo, "--base", "no-such-rev")

        assert result.returncode == 2
        assert "does not resolve" in result.stderr

    def test_auto_detects_main_when_no_origin(self, mini_repo: Path):
        """No --base, no origin remote, but `main` exists — verifier picks main."""
        # Verify the mini_repo fixture is on main with no origin
        result = _run_verifier(mini_repo)

        assert result.returncode == 0, result.stderr
        evidence = json.loads(result.stdout)
        # Should produce a valid evidence shape — proves it resolved a base
        assert "verifier" in evidence


class TestSelfCompat:
    """The verifier's emitted shape must satisfy the schema validator that
    the plugin runtime (bin/prawduct-hook validate-evidence) uses.
    Cross-validation here catches drift between the two sides of the contract.
    """

    def test_emitted_fields_satisfy_schema_validator(self, mini_repo: Path):
        """Take what the verifier writes, glue on fingerprint fields, and
        run it through the plugin runtime's validate-evidence. Failure here
        means the verifier and the schema disagree on shape."""
        out = mini_repo / "coverage.json"
        _run_verifier(mini_repo, "--base", "main", "--output", str(out))
        coverage = json.loads(out.read_text())

        fingerprint = {
            "timestamp": "2026-05-18T10:00:00Z",
            "passed": 10,
            "failed": 0,
            "skipped": 0,
            "duration_seconds": 1,
            "command": "pytest",
        }
        evidence = fingerprint | coverage

        # validate-evidence operates against ``.prawduct/.test-evidence.json``
        # in a project dir.
        prawduct = mini_repo / ".prawduct"
        prawduct.mkdir(exist_ok=True)
        (prawduct / ".test-evidence.json").write_text(json.dumps(evidence))

        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "bin" / "prawduct-hook"), "validate-evidence"],
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "CLAUDE_PROJECT_DIR": str(mini_repo),
                "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT),
            },
        )

        assert result.returncode == 0, result.stderr


class TestReferenceCache:
    """Test-file contents are read ONCE and matched against every changed
    file from that cache — not re-read per changed file. These tests load the
    verifier in-process (no subprocess) so they can count reads directly.
    """

    def test_each_test_file_read_once_regardless_of_changed_count(
        self, mini_repo: Path, monkeypatch
    ):
        """The cache reads each test file exactly once even when many changed
        files are matched against it. Before the cache, ``_has_reference`` ran
        per changed file and re-opened every test — O(changed × tests) reads.
        """
        trv = _load_verifier_module()

        # Five changed files, each with a distinct symbol; none referenced so
        # every changed file forces a full scan of the test list (worst case).
        for i in range(5):
            (mini_repo / "src" / f"mod{i}.py").write_text(
                f"def helper_{i}():\n    return {i}\n"
            )

        # Count reads of the discovered test files by their resolved path.
        test_dir = (mini_repo / "tests").resolve()
        reads: dict[str, int] = {}
        real_read_text = Path.read_text

        def counting_read_text(self, *args, **kwargs):
            resolved = self.resolve()
            if test_dir in resolved.parents:
                reads[str(resolved)] = reads.get(str(resolved), 0) + 1
            return real_read_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", counting_read_text)

        fields = trv._build_evidence_fields(
            mini_repo.resolve(), "main", test_dir
        )

        # The single baseline test file must be read exactly once despite the
        # five changed files matched against it.
        assert reads, "expected at least one test file to be read"
        assert all(count == 1 for count in reads.values()), reads
        # Sanity: the run still produced valid evidence.
        assert fields["coverage_level"] == "referenced"

    def test_multi_changed_file_result_parity(self, mini_repo: Path):
        """Result parity check: with several changed files — some referenced,
        some not — exactly the referenced ones land in ``changes_referenced``.
        Confirms the cache refactor preserved matching behavior."""
        # Referenced: a test mentions its symbol.
        (mini_repo / "src" / "alpha.py").write_text(
            "def alpha_fn():\n    return 'a'\n"
        )
        (mini_repo / "tests" / "test_alpha.py").write_text(
            "def test_alpha_fn():\n"
            "    from src.alpha import alpha_fn\n"
            "    assert alpha_fn() == 'a'\n"
        )
        # Not referenced: no test mentions its symbol.
        (mini_repo / "src" / "beta.py").write_text(
            "def beta_fn():\n    return 'b'\n"
        )
        # Also referenced via the pre-existing baseline test.
        (mini_repo / "src" / "core.py").write_text(
            "def existing_helper():\n    return 99\n"
        )

        result = _run_verifier(mini_repo, "--base", "main")

        assert result.returncode == 0, result.stderr
        evidence = json.loads(result.stdout)
        referenced = set(evidence["changes_referenced"])
        assert "src/alpha.py" in referenced
        assert "src/core.py" in referenced
        assert "src/beta.py" not in referenced
