"""Session start and the handoff survive a pathname that is not UTF-8 (#1188).

git status decodes with ``surrogateescape``, so a byte of a legacy encoding in a
pathname arrives as a lone surrogate. With ``core.quotePath=false`` (common
among people whose filenames are not ASCII) porcelain prints such a name raw
instead of octal-quoting it. Two writers then meet it:

- ``.session-git-baseline`` mirrors ``git status`` byte for byte, because the
  Stop gate compares it line by line with fresh output. It is written and read
  with ``surrogateescape``, so the pre-existing entry is not counted as this
  session's work.
- ``.session-handoff.md`` lists the files a session changed. It is written with
  ``backslashreplace``, so it stays valid UTF-8 for the next session's reader.

A strict writer raised at either point: session start stopped before its
anchors were recorded, and the handoff was lost whole.

The name is staged through plumbing, with no file on disk, because some
filesystems (APFS) refuse to store it. ``git status`` still prints it.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fixtures.hook_env import isolated_hook_run  # noqa: E402
from lib import gitstate  # noqa: E402

NAME = b"n\xe9.cfg"


def _env(home: Path) -> dict[str, str]:
    return {
        **os.environ,
        "HOME": str(home),
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


@pytest.fixture
def home(tmp_path: Path) -> Path:
    path = tmp_path / "_home"  # outside the repo: macOS pyc caches land under HOME
    path.mkdir()
    return path


def _git(repo: Path, home: Path, *args: str | bytes, stdin: bytes | None = None) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=str(repo), input=stdin, capture_output=True,
        env=_env(home), check=True, timeout=20,
    ).stdout


@pytest.fixture
def repo(tmp_path: Path, home: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, home, "init", "-q", "-b", "main")
    for key, value in (("user.email", "t@example.com"), ("user.name", "T"),
                       ("commit.gpgsign", "false"), ("core.quotePath", "false")):
        _git(repo, home, "config", key, value)
    (repo / ".gitignore").write_text(".prawduct/\n.claude/\n")
    (repo / "src.py").write_text("x = 1\n")
    _git(repo, home, "add", "-A")
    _git(repo, home, "commit", "-qm", "seed")
    (repo / ".prawduct" / "artifacts").mkdir(parents=True)
    (repo / ".prawduct" / "project-state.yaml").write_text("backlog_format_version: 2\n")
    (repo / ".prawduct" / "artifacts" / "project-preferences.md").write_text("- **Language**: Python\n")
    return repo.resolve()


def _stage_legacy_name(repo: Path, home: Path) -> None:
    blob = _git(repo, home, "hash-object", "-w", "--stdin", stdin=b"k = v\n").strip()
    _git(repo, home, "update-index", "--add", "--cacheinfo", b"100644," + blob + b"," + NAME)


def _clear(repo: Path, home: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK), "clear", "--session-start"],
        capture_output=True, text=True, timeout=120, **isolated_hook_run(repo, env=_env(home)),
    )


def test_status_names_the_legacy_path_raw(repo, home):
    """The precondition the rest relies on: porcelain prints the byte, not an
    octal escape, so a surrogate reaches the writers."""
    _stage_legacy_name(repo, home)
    assert NAME in _git(repo, home, "status", "--porcelain")
    assert "\udce9" in gitstate.git_status_output(repo)


def test_session_start_records_a_byte_exact_baseline(repo, home):
    _stage_legacy_name(repo, home)
    r = _clear(repo, home)
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert "Traceback" not in r.stderr and "UnicodeEncodeError" not in r.stderr
    baseline = repo / ".prawduct" / ".session-git-baseline"
    assert NAME in baseline.read_bytes()
    assert not (repo / ".prawduct" / ".session-git-baseline.tmp").exists()
    # The entry was there before the session began, so it is not this session's.
    assert gitstate.git_has_session_changes(repo) == ""
    assert gitstate._get_session_changed_files(repo) == []
    # A real change in the session is still seen. Without this, a baseline its
    # reader cannot decode (read as "no baseline", answering "") passes above.
    (repo / "src.py").write_text("x = 2\n")
    assert gitstate.git_has_session_changes(repo).endswith(" src.py")
    assert gitstate._get_session_changed_files(repo) == ["src.py"]


def test_the_handoff_names_a_legacy_path_and_stays_utf8(repo, home):
    first = _clear(repo, home)
    assert first.returncode == 0, (first.stdout, first.stderr)
    _stage_legacy_name(repo, home)
    # The control: the session's change is seen as the session's.
    assert gitstate._get_session_changed_files(repo) == ["n\udce9.cfg"]

    second = _clear(repo, home)
    assert second.returncode == 0, (second.stdout, second.stderr)
    handoff = (repo / ".prawduct" / ".session-handoff.md").read_bytes()
    text = handoff.decode("utf-8")  # strict: the file is valid UTF-8
    assert "## Files Changed This Session" in text
    assert "- n\\udce9.cfg" in text
