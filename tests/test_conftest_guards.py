"""Pins the two guards `tests/conftest.py` carries for the developer's own environment.

* #750: pytest outside the repo `.venv` warns, naming the expected path and the interpreter in use.
  Warn rather than fail (decided): CI installs into its own interpreter and must keep passing.
* #860: `@pytest.mark.non_root` skips a `chmod(0o000)` fixture test under root, one shared
  mechanism instead of a decorator copied into each module.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import conftest

REPO = Path(__file__).resolve().parent.parent


class TestVenvWarning:
    def test_out_of_venv_interpreter_warns_naming_both_paths(self, tmp_path: Path):
        msg = conftest.venv_warning("/usr/local/pyenv", "/usr/local/pyenv/bin/python", tmp_path, {})
        assert msg is not None
        assert str((tmp_path / ".venv").resolve()) in msg
        assert "/usr/local/pyenv/bin/python" in msg

    def test_interpreter_inside_the_venv_is_silent(self, tmp_path: Path):
        (tmp_path / ".venv").mkdir()
        assert conftest.venv_warning(str(tmp_path / ".venv"), "x", tmp_path, {}) is None

    def test_ci_and_explicit_opt_out_are_silent(self, tmp_path: Path):
        assert conftest.venv_warning("/elsewhere", "x", tmp_path, {"CI": "true"}) is None
        assert conftest.venv_warning("/elsewhere", "x", tmp_path, {"PRAWDUCT_ALLOW_ANY_PYTHON": "1"}) is None


class TestNonRootMarker:
    def test_marker_is_applied_to_every_chmod_000_fixture_test(self):
        """Every test file that makes its own fixture unreadable carries the marker."""
        unmarked = []
        for path in sorted((REPO / "tests").glob("test_*.py")):
            if path == Path(__file__):
                continue
            text = path.read_text()
            if "chmod(0o000)" in text and "pytest.mark.non_root" not in text:
                unmarked.append(path.name)
        assert unmarked == []

    @pytest.mark.parametrize("euid, skipped", [(0, True), (1000, False)])
    def test_non_root_test_is_skipped_only_under_root(self, monkeypatch, euid: int, skipped: bool):
        class Item:
            path = REPO / "tests" / "test_x.py"

            def __init__(self, marked: bool):
                self.marked, self.added = marked, []

            def get_closest_marker(self, name):
                return object() if name == "non_root" and self.marked else None

            def add_marker(self, mark):
                self.added.append(mark.name)

        class Config:
            rootpath = REPO

        monkeypatch.setattr(os, "geteuid", lambda: euid)
        marked, plain = Item(True), Item(False)
        conftest.pytest_collection_modifyitems(Config(), [marked, plain])
        assert ("skip" in marked.added) is skipped
        assert "skip" not in plain.added
