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

**And any NESTED CHECKOUT, by the property rather than by name.** A linked
git worktree added inside the primary checkout (`git worktree add ./devchk`,
a dev-check tree, a release-cut tree) carries a complete duplicate `tests/`
tree whose files are not this checkout's and are correctly skipped by
`testpaths`. The `.claude/` exclusion above was the first instance of this
class (TST-9K4W) and was fixed by naming that one path — which held only
until a worktree appeared somewhere else, at which point every session in
the clone got a red suite for another session's directory. The predicate is
"does this directory carry its own `.git`", so it now covers all of them,
including ones nobody has thought of. `.claude/` stays excluded on its own
merits: it is agent scratch whether or not it holds a checkout.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TESTS_DIR = REPO_ROOT / "tests"
EXCLUDED_DIRS = frozenset(
    {".git", ".claude", "__pycache__", "node_modules", ".venv", "venv", ".pytest_cache"}
)


def _is_nested_checkout(directory: Path) -> bool:
    """Does ``directory`` carry its own ``.git``, making it a separate checkout?

    A linked worktree writes a ``.git`` FILE (``gitdir: …``); a clone or
    submodule writes a directory. Both mean the same thing here — the tests
    below it belong to that checkout, not this one — so neither is inspected
    further. Never called on the repo root, which is where the walk starts.
    """
    return (directory / ".git").exists()


def _all_test_files(root: Path = REPO_ROOT) -> list[Path]:
    matches: list[Path] = []

    def walk(directory: Path) -> None:
        for entry in directory.iterdir():
            if entry.name in EXCLUDED_DIRS:
                continue
            if entry.is_dir():
                if _is_nested_checkout(entry):
                    continue
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

    def test_walk_excludes_a_linked_worktree_anywhere_in_the_tree(self, tmp_path: Path):
        """A worktree added inside the primary checkout under an arbitrary name.

        Observed live: `git worktree add ./devchk` at the repo root turned this
        assertion red for every session in the clone, over a directory belonging
        to another session that must not be deleted to make a test pass. A
        linked worktree's `.git` is a FILE, which is why the check is `.exists()`
        and not `.is_dir()`."""
        (tmp_path / "tests").mkdir()
        real = tmp_path / "tests" / "test_real.py"
        real.write_text("def test_x(): pass\n")
        nested = tmp_path / "devchk"
        (nested / "tests" / "preferences").mkdir(parents=True)
        (nested / ".git").write_text("gitdir: /elsewhere/.git/worktrees/devchk\n")
        (nested / "tests" / "preferences" / "test_dummy.py").write_text("def test_y(): pass\n")

        # Exact, not depth-coupled. The first cut asserted
        # `nested not in [p.parent.parent.parent for p in found]`, which only
        # detects a leak at the one depth this fixture plants — a leak from
        # `devchk/tests/test_x.py` or `devchk/a/b/c/test_x.py` would have
        # satisfied it. The sibling below already pins the predicate this way.
        assert _all_test_files(tmp_path) == [real]

    def test_walk_excludes_a_nested_clone_or_submodule(self, tmp_path: Path):
        """The same predicate covers a `.git` DIRECTORY — a nested clone or a
        submodule checkout — so the fix is not worktree-specific."""
        (tmp_path / "tests").mkdir()
        real = tmp_path / "tests" / "test_real.py"
        real.write_text("def test_x(): pass\n")
        nested = tmp_path / "vendor" / "thing"
        (nested / "tests").mkdir(parents=True)
        (nested / ".git").mkdir()
        (nested / "tests" / "test_dummy.py").write_text("def test_y(): pass\n")

        assert _all_test_files(tmp_path) == [real]

    def test_a_plain_directory_is_still_walked(self, tmp_path: Path):
        """The pruning must key on `.git`, not on depth or on having a `tests/`
        child — a genuinely misplaced test in an ordinary subdirectory is the
        whole point of this module and must still be caught."""
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_real.py").write_text("def test_x(): pass\n")
        stray = tmp_path / "plugin" / "lib"
        stray.mkdir(parents=True)
        misplaced = stray / "test_oops.py"
        misplaced.write_text("def test_z(): pass\n")

        assert misplaced in _all_test_files(tmp_path)
