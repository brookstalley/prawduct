"""Porcelain-parsing regression tests for ``lib/gitstate.py`` (review-fixes Chunk 1).

Git quotes paths containing spaces (`` M "my doc.md"``) and renders renames as
``R  old -> new``. The previous ``line.split()[-1]`` parse returned ``doc.md"``
for the quoted form, so the ``.endswith(".md")`` doc-only check failed on the
trailing quote and a doc-only session touching a space-containing path was
falsely blocked by the Critic/reflection gates. These tests pin the shared
``parse_porcelain_line`` helper and exercise each consumer with the messy
inputs real repos produce — per the learning "test each input path with the
messy inputs real systems produce, not just the clean canonical marker".
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lib import gitstate


# =============================================================================
# parse_porcelain_line — the shared parser
# =============================================================================


class TestParsePorcelainLine:
    def test_plain_path(self):
        assert gitstate.parse_porcelain_line(" M src/app.py") == (" M", None, "src/app.py")

    def test_quoted_path_with_spaces(self):
        parsed = gitstate.parse_porcelain_line(' M "my doc.md"')
        assert parsed is not None
        _, src, path = parsed
        assert src is None
        assert path == "my doc.md"  # NOT 'doc.md"'

    def test_untracked_quoted_path(self):
        parsed = gitstate.parse_porcelain_line('?? "notes from review.md"')
        assert parsed == ("??", None, "notes from review.md")

    def test_rename_returns_src_and_dst(self):
        parsed = gitstate.parse_porcelain_line("R  old/name.py -> new/name.py")
        assert parsed == ("R ", "old/name.py", "new/name.py")

    def test_rename_with_quoted_paths(self):
        parsed = gitstate.parse_porcelain_line('R  "old dir/a.md" -> "new dir/a.md"')
        assert parsed == ("R ", "old dir/a.md", "new dir/a.md")

    def test_blank_and_malformed_lines(self):
        assert gitstate.parse_porcelain_line("") is None
        assert gitstate.parse_porcelain_line(" M ") is None
        assert gitstate.parse_porcelain_line("xy") is None


# =============================================================================
# Consumers — quoted/space paths through each baseline-diff function
# =============================================================================


def _repo(tmp_path: Path, *, baseline: str = "") -> Path:
    prawduct = tmp_path / ".prawduct"
    prawduct.mkdir()
    (prawduct / ".session-git-baseline").write_text(baseline)
    return tmp_path


class TestDocOnlyWithQuotedPaths:
    """A doc-only session touching a space-containing .md path must classify
    as doc-only — the regression that falsely blocked the reflection gate."""

    def test_quoted_md_path_is_doc_only(self, tmp_path, monkeypatch):
        project = _repo(tmp_path)
        monkeypatch.setattr(
            gitstate, "git_status_output", lambda _: ' M "my doc.md"\n'
        )
        assert gitstate._session_changes_are_doc_only(project) is True

    def test_quoted_code_path_is_not_doc_only(self, tmp_path, monkeypatch):
        project = _repo(tmp_path)
        monkeypatch.setattr(
            gitstate, "git_status_output", lambda _: ' M "my module.py"\n'
        )
        assert gitstate._session_changes_are_doc_only(project) is False

    def test_mixed_quoted_and_plain_all_md(self, tmp_path, monkeypatch):
        project = _repo(tmp_path)
        monkeypatch.setattr(
            gitstate,
            "git_status_output",
            lambda _: ' M "my doc.md"\n M README.md\n',
        )
        assert gitstate._session_changes_are_doc_only(project) is True


class TestSessionChangesWithQuotedPaths:
    def test_quoted_metadata_path_is_excused(self, tmp_path, monkeypatch):
        """A quoted .prawduct/ path must still match the metadata prefix —
        with the old parse the leading quote defeated startswith()."""
        project = _repo(tmp_path)
        monkeypatch.setattr(
            gitstate,
            "git_status_output",
            lambda _: ' M ".prawduct/my notes.md"\n',
        )
        assert gitstate.git_has_session_changes(project) == ""

    def test_quoted_code_path_counts_as_change(self, tmp_path, monkeypatch):
        project = _repo(tmp_path)
        monkeypatch.setattr(
            gitstate, "git_status_output", lambda _: ' M "my module.py"\n'
        )
        assert gitstate.git_has_session_changes(project) != ""

    def test_changed_files_strips_quotes(self, tmp_path, monkeypatch):
        project = _repo(tmp_path)
        monkeypatch.setattr(
            gitstate,
            "git_status_output",
            lambda _: ' M "my doc.md"\nR  old.py -> new.py\n',
        )
        assert gitstate._get_session_changed_files(project) == ["my doc.md", "new.py"]

    def test_changed_files_tolerates_unreadable_baseline(self, tmp_path, monkeypatch):
        """The corrupted-baseline guard its sibling readers already had."""
        project = _repo(tmp_path)
        (project / ".prawduct" / ".session-git-baseline").write_bytes(b"\xff\xfe\x00bad")
        monkeypatch.setattr(
            gitstate, "git_status_output", lambda _: " M src/app.py\n"
        )
        assert gitstate._get_session_changed_files(project) == ["src/app.py"]
