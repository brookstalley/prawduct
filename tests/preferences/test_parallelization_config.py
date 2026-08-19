"""Project-preferences enforcement: pytest parallelization config.

Enforces the Parallelization preference in
`.prawduct/artifacts/project-preferences.md`:
- `pyproject.toml` configures pytest-xdist with `-n 5 --dist loadfile`
- `tests/conftest.py` assigns xdist_group markers by directory so
  same-directory tests run serially on one worker
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TestPyprojectAddopts:
    def test_addopts_pins_the_xdist_worker_count(self):
        """The worker count is FIXED, not `auto` (owner ruling 2026-08-19).

        `auto` takes every core, which makes a full-suite run own the
        developer's machine for its whole duration — the preference row records
        the load average that prompted the change. So this pins the number and
        also asserts `auto` is GONE: a revert to `auto` is the regression, and a
        check that merely finds *some* `-n` value passes straight through it.
        """
        pyproject = (REPO_ROOT / "pyproject.toml").read_text()
        assert '"-n", "5"' in pyproject, (
            "pyproject.toml addopts must pin the xdist worker count to 5 — see "
            "the Parallelization row in project-preferences.md, which records "
            "why this is a developer-ergonomics setting rather than a "
            "throughput one"
        )
        assert '"-n", "auto"' not in pyproject, (
            "pyproject.toml is back on '-n auto', which takes every core; the "
            "owner ruling of 2026-08-19 replaced it with a fixed count"
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
