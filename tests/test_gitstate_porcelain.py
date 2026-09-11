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

from lib import gates, gitstate


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
    as doc-only — the regression that falsely blocked the reflection gate.
    (The carveout now lives in gates.session_changes_all_non_judgeable —
    kernel-v3 chunk 04 — but the quoted-path parse it depends on is this
    module's, so the regression stays pinned here.)"""

    def test_quoted_md_path_is_doc_only(self, tmp_path, monkeypatch):
        project = _repo(tmp_path)
        monkeypatch.setattr(
            gitstate, "git_status_output", lambda _: ' M "my doc.md"\n'
        )
        assert gates.session_changes_all_non_judgeable(project) is True

    def test_quoted_code_path_is_not_doc_only(self, tmp_path, monkeypatch):
        project = _repo(tmp_path)
        monkeypatch.setattr(
            gitstate, "git_status_output", lambda _: ' M "my module.py"\n'
        )
        assert gates.session_changes_all_non_judgeable(project) is False

    def test_mixed_quoted_and_plain_all_md(self, tmp_path, monkeypatch):
        project = _repo(tmp_path)
        monkeypatch.setattr(
            gitstate,
            "git_status_output",
            lambda _: ' M "my doc.md"\n M README.md\n',
        )
        assert gates.session_changes_all_non_judgeable(project) is True


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


# =============================================================================
# local_branches — "could not ask" is not "none exist"
# =============================================================================


class TestLocalBranches:
    """The whole contract is the distinction between ``None`` and ``set()``.

    Its consumer tells an operator that a plan claims a branch nobody has.
    Collapsing a failed probe into an empty set makes that a confident
    accusation on every repo where git cannot answer — the fail-open shape,
    pointed at the operator instead of past them.
    """

    def _git(self, repo: Path, *args: str):
        import subprocess
        return subprocess.run(
            ["git", *args], cwd=str(repo), capture_output=True, text=True, check=True
        )

    def _repo(self, tmp_path: Path, branch: str = "main") -> Path:
        repo = tmp_path / "repo"
        repo.mkdir()
        self._git(repo, "init", "-q", "-b", branch)
        self._git(repo, "config", "user.email", "t@example.com")
        self._git(repo, "config", "user.name", "T")
        (repo / "f.txt").write_text("x\n")
        self._git(repo, "add", "f.txt")
        self._git(repo, "commit", "-qm", "init")
        return repo

    def test_lists_every_local_branch(self, tmp_path: Path):
        repo = self._repo(tmp_path)
        self._git(repo, "branch", "feat/a")
        self._git(repo, "branch", "feat/b")
        assert gitstate.local_branches(repo) == {"main", "feat/a", "feat/b"}

    def test_slashed_names_are_not_truncated(self, tmp_path: Path):
        # `%(refname:short)` keeps the full name; a `basename`-style read would
        # make `feat/x` and `fix/x` the same branch to the caller.
        repo = self._repo(tmp_path)
        self._git(repo, "branch", "feat/x")
        self._git(repo, "branch", "fix/x")
        assert {"feat/x", "fix/x"} <= gitstate.local_branches(repo)

    def test_outside_a_repo_is_none_not_empty(self, tmp_path: Path):
        outside = tmp_path / "plain"
        outside.mkdir()
        assert gitstate.local_branches(outside) is None


class TestCurrentBranchFastPath:
    """``current_branch`` reads git's HEAD file and shells out only when it can't.

    The fast path is worth pinning separately because its failure mode is
    silence: a wrong-but-plausible branch name would be believed by plan
    resolution, review dispatch and every gate. So each case asserts BOTH that
    the reader answered (or declined) and that the public function agrees with
    the subprocess it replaced.
    """

    def _git(self, repo: Path, *args: str):
        import subprocess
        return subprocess.run(
            ["git", *args], cwd=str(repo), capture_output=True, text=True, check=True
        )

    def _repo(self, tmp_path: Path, branch: str = "main") -> Path:
        repo = tmp_path / "repo"
        repo.mkdir()
        self._git(repo, "init", "-q", "-b", branch)
        self._git(repo, "config", "user.email", "t@example.com")
        self._git(repo, "config", "user.name", "T")
        (repo / "f.txt").write_text("x\n")
        self._git(repo, "add", "f.txt")
        self._git(repo, "commit", "-qm", "init")
        return repo

    def test_a_plain_checkout_is_answered_without_git(self, tmp_path: Path):
        repo = self._repo(tmp_path, "feat/x")
        assert gitstate._branch_from_head_file(repo) == (True, "feat/x")
        assert gitstate.current_branch(repo) == "feat/x"

    def test_a_detached_head_is_answered_as_none(self, tmp_path: Path):
        # ANSWERED, not declined: a raw object id in HEAD is exactly what the
        # subprocess reports as None, so spawning it would buy nothing.
        repo = self._repo(tmp_path)
        head = self._git(repo, "rev-parse", "HEAD").stdout.strip()
        self._git(repo, "checkout", "-q", "--detach", head)
        assert gitstate._branch_from_head_file(repo) == (True, None)
        assert gitstate.current_branch(repo) is None

    def test_a_linked_worktree_reports_its_OWN_branch(self, tmp_path: Path):
        # The case that makes this more than an optimisation. A worktree's
        # `.git` is a file naming a per-worktree git dir; reading the shared
        # common dir instead would report the PRIMARY checkout's branch —
        # silently, and to every gate.
        repo = self._repo(tmp_path, "main")
        wt = tmp_path / "wt"
        self._git(repo, "worktree", "add", "-q", "-b", "feat/side", str(wt))
        assert gitstate._branch_from_head_file(wt) == (True, "feat/side")
        assert gitstate.current_branch(wt) == "feat/side"
        # ...and the primary checkout is unaffected by the worktree existing.
        assert gitstate.current_branch(repo) == "main"

    def test_a_subdirectory_declines_and_falls_back(self, tmp_path: Path):
        # No `.git` here, so the reader must decline rather than guess — and the
        # public function must still answer, because `git symbolic-ref` searches
        # upward and callers pass subdirectories.
        repo = self._repo(tmp_path, "feat/x")
        sub = repo / "src" / "deep"
        sub.mkdir(parents=True)
        assert gitstate._branch_from_head_file(sub) == (False, None)
        assert gitstate.current_branch(sub) == "feat/x"

    def test_outside_a_work_tree_is_none(self, tmp_path: Path):
        plain = tmp_path / "plain"
        plain.mkdir()
        assert gitstate._branch_from_head_file(plain) == (False, None)
        assert gitstate.current_branch(plain) is None

    def test_a_gitdir_file_it_cannot_parse_declines(self, tmp_path: Path):
        # Declining is the only safe answer for a layout this reader does not
        # understand; the subprocess then gets its say.
        repo = tmp_path / "odd"
        repo.mkdir()
        (repo / ".git").write_text("something else entirely\n")
        assert gitstate._branch_from_head_file(repo) == (False, None)
