"""Project-preferences enforcement: test files live only under `tests/`.

Enforces the Test location preference in
`.prawduct/artifacts/project-preferences.md`: test files are colocated under
`tests/`, not scattered across the repo. Tests outside `tests/` are silently
skipped by `pyproject.toml`'s `testpaths = ["tests"]` configuration, which
is the worst kind of failure mode — a test that exists but never runs.

Detection: file-tree walk. Searches the entire repo for `test_*.py` files
and asserts every match is under `tests/`. Excludes `.git/`, `.claude/`
(agent scratch — worktree-isolated workflow checkouts live under
`.claude/worktrees/wf_*/` and carry a full duplicate `tests/` tree),
`__pycache__/`, and other non-source directories.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent / "plugin"
TESTS_DIR = REPO_ROOT / "tests"
EXCLUDED_DIRS = frozenset(
    {".git", ".claude", "__pycache__", "node_modules", ".venv", "venv", ".pytest_cache"}
)


def _all_test_files(root: Path = REPO_ROOT) -> list[Path]:
    matches: list[Path] = []

    def walk(directory: Path) -> None:
        for entry in directory.iterdir():
            if entry.name in EXCLUDED_DIRS:
                continue
            if entry.is_dir():
                walk(entry)
            elif entry.is_file() and entry.name.startswith("test_") and entry.suffix == ".py":
                matches.append(entry)

    walk(root)
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

    def test_walk_excludes_claude_worktree_checkouts(self, tmp_path: Path):
        # TST-9K4W: a worktree-isolated workflow leaves a full repo checkout under
        # .claude/worktrees/wf_*/, including a duplicate tests/ tree. The walk must
        # prune the whole .claude/ subtree so those copies don't fail the location
        # check (they are not "misplaced" tests — they are a nested checkout).
        (tmp_path / "tests").mkdir()
        real = tmp_path / "tests" / "test_real.py"
        real.write_text("def test_x(): pass\n")
        worktree = tmp_path / ".claude" / "worktrees" / "wf_abc" / "tests" / "preferences"
        worktree.mkdir(parents=True)
        (worktree / "test_dummy.py").write_text("def test_y(): pass\n")

        found = _all_test_files(tmp_path)
        assert real in found
        assert all(".claude" not in p.parts for p in found), (
            f"walk descended into .claude/: {[p for p in found if '.claude' in p.parts]}"
        )
