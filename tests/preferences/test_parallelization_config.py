"""Project-preferences enforcement: pytest parallelization config.

Enforces the Parallelization preference in
`.prawduct/artifacts/project-preferences.md`:
- `pyproject.toml` configures pytest-xdist with `-n auto --dist loadfile`
- `tests/conftest.py` assigns xdist_group markers by directory so
  same-directory tests run serially on one worker
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TestPyprojectAddopts:
    def test_addopts_enables_xdist_auto_workers(self):
        pyproject = (REPO_ROOT / "pyproject.toml").read_text()
        assert '"-n", "auto"' in pyproject, (
            "pyproject.toml addopts must contain '-n auto' to enable "
            "pytest-xdist with auto-detected worker count"
        )

    def test_addopts_enables_loadfile_distribution(self):
        pyproject = (REPO_ROOT / "pyproject.toml").read_text()
        assert '"--dist", "loadfile"' in pyproject, (
            "pyproject.toml addopts must contain '--dist loadfile' so "
            "tests in the same file run on the same worker"
        )

    def test_testpaths_points_to_tests_directory(self):
        pyproject = (REPO_ROOT / "pyproject.toml").read_text()
        assert 'testpaths = ["tests"]' in pyproject, (
            "pyproject.toml must set testpaths = [\"tests\"]"
        )


class TestConftestDirectoryGrouping:
    def test_conftest_exists(self):
        assert (REPO_ROOT / "tests" / "conftest.py").exists(), (
            "tests/conftest.py is required for directory-based xdist grouping"
        )

    def test_conftest_assigns_xdist_groups_in_collection_hook(self):
        conftest = (REPO_ROOT / "tests" / "conftest.py").read_text()
        assert "pytest_collection_modifyitems" in conftest, (
            "tests/conftest.py must define pytest_collection_modifyitems "
            "to assign xdist_group markers"
        )
        assert "xdist_group" in conftest, (
            "tests/conftest.py must apply pytest.mark.xdist_group to items"
        )
