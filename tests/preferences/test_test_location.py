"""Project-preferences enforcement: test files live only under `tests/`.

Enforces the Test location preference in
`.prawduct/artifacts/project-preferences.md`: test files are colocated under
`tests/`, not scattered across the repo. Tests outside `tests/` are silently
skipped by `pyproject.toml`'s `testpaths = ["tests"]` configuration, which
is the worst kind of failure mode — a test that exists but never runs.

Detection: file-tree walk. Searches the entire repo for `test_*.py` files
and asserts every match is under `tests/`. Excludes `.git/`, `__pycache__/`,
and other non-source directories.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TESTS_DIR = REPO_ROOT / "tests"
EXCLUDED_DIRS = frozenset({".git", "__pycache__", "node_modules", ".venv", "venv", ".pytest_cache"})


def _all_test_files() -> list[Path]:
    matches: list[Path] = []

    def walk(directory: Path) -> None:
        for entry in directory.iterdir():
            if entry.name in EXCLUDED_DIRS:
                continue
            if entry.is_dir():
                walk(entry)
            elif entry.is_file() and entry.name.startswith("test_") and entry.suffix == ".py":
                matches.append(entry)

    walk(REPO_ROOT)
    return sorted(matches)


class TestTestLocation:
    def test_all_test_files_live_under_tests_directory(self):
        misplaced: list[str] = []
        for path in _all_test_files():
            try:
                path.relative_to(TESTS_DIR)
            except ValueError:
                misplaced.append(path.relative_to(REPO_ROOT).as_posix())
        assert not misplaced, (
            "Test files found outside `tests/` — pyproject.toml's testpaths=[\"tests\"] "
            "would silently skip these:\n  - "
            + "\n  - ".join(misplaced)
        )
