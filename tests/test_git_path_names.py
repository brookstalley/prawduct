"""git C-quotes a path name holding a non-ASCII byte, a double quote, a backslash or a
control character (``core.quotepath``): ``skills/café.md`` prints as
``"skills/caf\\303\\251.md"``. A reader comparing that text with names on disk misses the
file. ``lib.gitstate.unquote_git_path`` is the one decoder; these tests read git's own
quoting of real files, so the fixture is git's behaviour, not a transcription of it.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from lib import gitstate

#: Names whose quoting differs: non-ASCII, a quote, a backslash, tab, newline, a control
#: byte, a space (never quoted), a leading space, and " -> " (the rename arrow's text).
HARD_NAMES = [
    "skills/café.md",
    'docs/say "hi".md',
    "back\\slash.py",
    "tab\there.txt",
    "new\nline.txt",
    "bell\x07.txt",
    "plain name.md",
    " leading.md",
    "arrow -> inside.md",
    "日本/語.py",
]


def git(repo: Path, *args: str, check: bool = True) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main", *args],
        cwd=repo, capture_output=True, check=check, env=env,
        encoding="utf-8", errors="surrogateescape",
    ).stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "t@example.invalid")
    git(repo, "config", "user.name", "t")
    (repo / "base.txt").write_text("base\n")
    git(repo, "add", "base.txt")
    git(repo, "commit", "-q", "-m", "base")
    return repo


def write(repo: Path, names: list[str]) -> None:
    for name in names:
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{name}\n", encoding="utf-8")


# -- The decoder ------------------------------------------------------------------------


def test_every_name_git_prints_decodes_to_the_name_on_disk(repo):
    write(repo, HARD_NAMES)
    git(repo, "add", "-A")
    out = git(repo, "ls-files")
    # The fixture's own control: git quotes all but the two plain names, or this proves nothing.
    assert sum(line.startswith('"') for line in out.split("\n")) == len(HARD_NAMES) - 3, out
    assert '"skills/caf\\303\\251.md"' in out.split("\n")
    assert set(gitstate.git_path_lines(out)) == set(HARD_NAMES) | {"base.txt"}


def test_invalid_utf8_bytes_survive_as_surrogates():
    """git prints a byte that is not UTF-8 as its octal escape (``bad\\377.txt``); the decode
    keeps it as a surrogate, which ``os.fsencode`` turns back into the byte. Not made on disk:
    some filesystems (APFS) refuse such a name."""
    name = gitstate.unquote_git_path('"bad\\377.txt"')
    assert os.fsencode(name) == b"bad\xff.txt"


@pytest.mark.parametrize("text", [
    "plain.md", "", '"', '"unterminated', '"bad \\q escape"', '"short \\30 octal"',
    '"trailing"after', 'a"b"',
])
def test_text_that_is_not_a_whole_quoted_name_is_returned_unchanged(text):
    assert gitstate.unquote_git_path(text) == text


def test_lines_split_on_newline_only():
    """An unquoted name may hold a character `str.splitlines` splits on (git prints U+2028
    raw under ``core.quotepath=false``); only git's own newline separates records."""
    assert gitstate.git_path_lines("a b.md\nc.md\n") == ["a b.md", "c.md"]


# -- Porcelain ----------------------------------------------------------------------------


def test_porcelain_lines_name_the_real_files(repo):
    write(repo, HARD_NAMES)
    out = git(repo, "status", "--porcelain", "-uall")
    parsed = [gitstate.parse_porcelain_line(line) for line in out.split("\n") if line]
    assert {path for _status, _src, path in parsed} == set(HARD_NAMES)


def test_a_porcelain_rename_names_both_real_files(repo):
    write(repo, ["skills/café.md"])
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "add")
    (repo / "docs").mkdir()
    git(repo, "mv", "skills/café.md", 'docs/say "hi".md')
    (line,) = [line for line in git(repo, "status", "--porcelain").split("\n") if line]
    assert gitstate.parse_porcelain_line(line) == ("R ", "skills/café.md", 'docs/say "hi".md')


def test_an_unquoted_rename_source_with_an_arrow_in_a_non_rename_is_one_path():
    """`` -> `` splits a rename only when the status says rename."""
    assert gitstate.parse_porcelain_line("?? arrow -> inside.md") == ("??", None, "arrow -> inside.md")


# -- The readers (chunk 01): each sees the real names ---------------------------------------
#
# Two names stand for the class: a non-ASCII byte and a double quote, the two quotings a
# reader's `.strip()` and `str.startswith` got wrong in different ways.

NAMES = ["skills/café.md", 'docs/say "hi".md']


def commit_all(repo: Path, message: str) -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD").strip()


def test_critic_mode_paths_since_tree_names_the_files(repo):
    from lib import critic_mode
    tree = git(repo, "rev-parse", "HEAD^{tree}").strip()
    write(repo, NAMES[:1])
    commit_all(repo, "one")
    write(repo, NAMES[1:])  # untracked
    assert critic_mode._paths_since_tree(tree, repo) == set(NAMES)


def test_critic_mode_committed_files_since_names_the_files(repo):
    from lib import critic_mode
    base = git(repo, "rev-parse", "HEAD").strip()
    write(repo, NAMES)
    commit_all(repo, "two")
    assert critic_mode._committed_files_since(repo, base) == set(NAMES)


def test_critic_mode_uncommitted_code_files_names_the_files(repo):
    from lib import critic_mode
    write(repo, NAMES)
    assert critic_mode._get_uncommitted_code_files(repo) == set(NAMES)


def test_coverage_changed_files_names_the_files(repo):
    from lib import coverage
    base = git(repo, "rev-parse", "HEAD").strip()
    write(repo, NAMES[:1])
    commit_all(repo, "one")
    write(repo, NAMES[1:])
    assert set(coverage._coverage_changed_files(repo, base)) == set(NAMES)


def test_coverage_working_tree_paths_names_the_files(repo):
    from lib import coverage
    write(repo, NAMES)
    paths, reason = coverage._working_tree_paths(repo)
    assert reason is None and set(paths) == set(NAMES)


def test_a_doc_only_branch_with_a_non_ascii_doc_reads_as_doc_only(repo, monkeypatch, capsys):
    """A quoted name read raw keeps its quotes and ends in `.md"`, so it reads as a judgeable
    file and a doc-only branch is told it needs a review and a change record."""
    from lib import coverage
    base = git(repo, "rev-parse", "HEAD").strip()
    (repo / "docs").mkdir()
    (repo / "docs" / "café.md").write_text("doc\n")
    commit_all(repo, "doc")
    monkeypatch.setattr(coverage, "_coverage_resolve_base", lambda _p: (base, None))
    is_doc_only, message = coverage._pr_diff_is_doc_only(repo)
    assert is_doc_only, message
    assert coverage.check_change_log_entry(repo) == 0
    (repo / "docs" / "x.py").write_text("x = 1\n")  # control: a judgeable file still needs review
    commit_all(repo, "code")
    assert coverage._pr_diff_is_doc_only(repo)[0] is False


def test_plan_status_log_commits_names_the_files(repo):
    from lib import plan_status
    write(repo, NAMES)
    commit_all(repo, "two")
    (latest, *_rest) = plan_status._log_commits(repo, "-1", "HEAD")
    assert set(latest.files) == set(NAMES)


def test_buildplan_refs_changed_on_branch_names_the_files(repo, monkeypatch):
    from lib import buildplan_refs
    git(repo, "branch", "base")
    write(repo, ["plans/café.md"])
    commit_all(repo, "one")
    write(repo, ['plans/say "hi".md'])
    monkeypatch.setattr(buildplan_refs, "_resolve_base_branch", lambda _p: ("base", None))
    assert buildplan_refs._changed_on_branch(repo, repo / "plans") == {
        (repo / "plans" / "café.md").resolve(), (repo / "plans" / 'say "hi".md').resolve(),
    }


def test_change_fragments_branch_record_finds_a_non_ascii_fragment(repo):
    """A quoted name passed to `git show HEAD:<name>` names no file, so the record would
    report a git error instead of the fragment."""
    from lib import change_fragments
    base = git(repo, "rev-parse", "HEAD").strip()
    fragment = repo / ".prawduct" / "changes" / "café.md"
    fragment.parent.mkdir(parents=True)
    fragment.write_text("---\nschema: 1\n---\n")
    commit_all(repo, "fragment")
    record = change_fragments.branch_change_record(repo, base)
    assert record.error is None, record.error
    assert [change.path for change in record.changes] == [".prawduct/changes/café.md"]


def test_native_review_tree_moved_reads_a_prawduct_file_as_prawduct(repo):
    """A quoted `.prawduct/` name begins with `"`, so read raw it looks like a source file
    and the tree counts as moved."""
    from lib import native_review
    state = repo / ".prawduct" / "café.md"
    state.parent.mkdir()
    state.write_text("a\n")
    commit_all(repo, "a")
    base_tree = git(repo, "rev-parse", "HEAD^{tree}").strip()
    state.write_text("b\n")
    commit_all(repo, "b")
    head_tree = git(repo, "rev-parse", "HEAD^{tree}").strip()
    state.write_text("c\n")  # moved again after the review, inside .prawduct/ only
    sidecar = {"base_tree": base_tree, "head_tree": head_tree}
    assert native_review._tree_moved(repo, sidecar) is False
    (repo / "src.py").write_text("x = 1\n")  # control: a source file in the interval that moved
    git(repo, "add", "src.py")
    git(repo, "commit", "-q", "-m", "src")
    head_tree = git(repo, "rev-parse", "HEAD^{tree}").strip()
    (repo / "src.py").write_text("x = 2\n")
    sidecar = {"base_tree": base_tree, "head_tree": head_tree}
    assert native_review._tree_moved(repo, sidecar) is True
