"""Session start takes in the review facts other clones sent (#1052).

A boundary ``clear --session-start`` runs ``evidence_notes.ingest`` bounded to the
branch's commits, before the briefing reads the store, so a second clone's
coverage verdict is computed from the same facts as the clone that ran the
reviews. The step is advice-shaped: a failure is a NOTE and the briefing still
renders; nothing is printed unless something was appended; a continuation
(``--brief-only``) and a disposable agent worktree ingest nothing — the main
checkout's own boundary ingests for the whole clone.

The cost half (one ``for-each-ref`` over ``refs/notes/`` when the clone has no notes ref) is pinned in
``tests/test_hot_path_git_batching.py`` beside the other session-start costs.

Real git repos and the real hook binary, with the environment notices removed
(``tests/fixtures/hook_env.py``).
"""

from __future__ import annotations

import json
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
from lib import evidence  # noqa: E402

NOTES_REF = "refs/notes/prawduct"
INGESTED = "1 evidence fact(s) ingested from refs/notes/prawduct"


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


def _git(repo: Path, home: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True,
        env=_env(home), check=True, timeout=20,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path, home: Path) -> Path:
    """A governed repo on `feature/unit`, one commit beyond `main`."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, home, "init", "-q", "-b", "main")
    for key, value in (("user.email", "t@example.com"), ("user.name", "T"),
                       ("commit.gpgsign", "false")):
        _git(repo, home, "config", key, value)
    (repo / ".gitignore").write_text(".prawduct/\n.claude/\n")
    _git(repo, home, "add", ".gitignore")
    _git(repo, home, "commit", "-qm", "seed")
    _git(repo, home, "checkout", "-q", "-b", "feature/unit")
    (repo / "src.py").write_text("x = 1\n")
    _git(repo, home, "add", "src.py")
    _git(repo, home, "commit", "-qm", "feat: the work (Chunk 01)")
    prawduct = repo / ".prawduct" / "artifacts"
    prawduct.mkdir(parents=True)
    (repo / ".prawduct" / "project-state.yaml").write_text("backlog_format_version: 2\n")
    # Filled preferences, so the CRITICAL nudge stays out of stdout.
    (prawduct / "project-preferences.md").write_text("- **Language**: Python\n")
    return repo.resolve()


def _envelope(fact_id: str, head: str) -> dict:
    return {
        "schema": 1, "kind": "review", "id": fact_id, "ts": "2026-10-25T10:00:00Z",
        "actor": {}, "body": {
            "scope": "unit", "chunks": ["01"], "chunk": "01", "mode": "chunk",
            "head_commit": head, "findings": [], "counts": {"blocking": 0},
        },
    }


def _note_on_head(repo: Path, home: Path, fact_id: str = "R-from-elsewhere") -> str:
    """Another clone's review, as it arrives: one store line on its anchor."""
    head = _git(repo, home, "rev-parse", "HEAD")
    line = json.dumps(_envelope(fact_id, head), sort_keys=True)
    _git(repo, home, "notes", "--ref", "prawduct", "add", "-m", line, head)
    return fact_id


def _ids(repo: Path) -> set[str]:
    return {f.get("id") for f in evidence.read_facts(repo).get("facts", [])}


def _clear(project: Path, home: Path, *flags: str) -> subprocess.CompletedProcess:
    kwargs = isolated_hook_run(project, env=_env(home))
    return subprocess.run(
        [sys.executable, str(HOOK), "clear", "--session-start", *flags],
        capture_output=True, text=True, timeout=120, **kwargs,
    )


def _ingest_lines(stdout: str) -> list[str]:
    return [line for line in stdout.splitlines() if "ingested from refs/notes/prawduct" in line]


class TestBoundaryIngests:
    def test_a_boundary_start_ingests_the_note_and_prints_the_count(self, repo, home):
        fact_id = _note_on_head(repo, home)
        assert fact_id not in _ids(repo)  # precondition: the store does not hold it

        result = _clear(repo, home)

        assert result.returncode == 0, result.stderr
        assert fact_id in _ids(repo)
        assert _ingest_lines(result.stdout) == [INGESTED]

    def test_a_second_start_appends_nothing_and_prints_nothing(self, repo, home):
        """Idempotent, and silent when there is nothing new — a zero line every
        session would be noise the reader learns to skip."""
        _note_on_head(repo, home)
        assert _clear(repo, home).returncode == 0
        again = _clear(repo, home)
        assert again.returncode == 0, again.stderr
        assert _ingest_lines(again.stdout) == []
        assert len([f for f in evidence.read_facts(repo)["facts"] if f["id"] == "R-from-elsewhere"]) == 1

    def test_no_notes_ref_prints_nothing(self, repo, home):
        result = _clear(repo, home)
        assert result.returncode == 0, result.stderr
        assert _ingest_lines(result.stdout) == []
        assert "evidence ingest" not in result.stderr

    def test_the_ingest_lands_before_the_briefing_reads_the_store(self, repo, home):
        """Order is the point: the line precedes the briefing's own output, so
        the briefing that follows was built from the ingested store."""
        _note_on_head(repo, home)
        lines = _clear(repo, home).stdout.splitlines()
        at = lines.index(INGESTED)
        assert any(line.strip() for line in lines[at + 1:]), "no briefing followed the ingest"


class TestWhereItDoesNotRun:
    def test_a_continuation_ingests_nothing(self, repo, home):
        fact_id = _note_on_head(repo, home)
        result = _clear(repo, home, "--brief-only")
        assert result.returncode == 0, result.stderr
        assert fact_id not in _ids(repo)
        assert _ingest_lines(result.stdout) == []
        # Control: the boundary it is not does ingest the same note.
        assert _ingest_lines(_clear(repo, home).stdout) == [INGESTED]

    def test_a_disposable_agent_worktree_ingests_nothing(self, repo, home):
        """The store is clone-wide, so a scratch tree's ingest would land — and
        race the main checkout's. The main checkout's boundary ingests."""
        fact_id = _note_on_head(repo, home)
        wid = "b16b00b5feedface1"
        scratch = repo / ".claude" / "worktrees" / f"agent-{wid}"
        scratch.parent.mkdir(parents=True)
        _git(repo, home, "worktree", "add", "-q", "-b", f"worktree-agent-{wid}", str(scratch), "HEAD")
        (scratch / ".prawduct" / "artifacts").mkdir(parents=True)
        (scratch / ".prawduct" / "project-state.yaml").write_text("backlog_format_version: 2\n")

        result = _clear(scratch.resolve(), home)

        assert result.returncode == 0, result.stderr
        assert fact_id not in _ids(repo)
        assert _ingest_lines(result.stdout) == []
        # Control: the main checkout's boundary takes it in.
        assert _ingest_lines(_clear(repo, home).stdout) == [INGESTED]


class TestFailsSoft:
    def test_an_unreadable_notes_ref_is_a_note_and_the_briefing_still_renders(self, repo, home):
        """A notes ref that is not a notes tree (here: a blob) cannot be listed.
        Ingest reports an error; session start says so on stderr and goes on."""
        blob = subprocess.run(
            ["git", "hash-object", "-w", "--stdin"], cwd=str(repo), input="not a notes tree\n",
            capture_output=True, text=True, env=_env(home), check=True,
        ).stdout.strip()
        _git(repo, home, "update-ref", NOTES_REF, blob)

        result = _clear(repo, home)

        assert result.returncode == 0, result.stderr
        notes = [line for line in result.stderr.splitlines() if line.startswith("NOTE: evidence ingest")]
        assert len(notes) == 1, result.stderr
        assert "session start" in notes[0]
        assert _ingest_lines(result.stdout) == []
        assert "== SESSION BRIEFING ==" in result.stdout.splitlines(), "the briefing did not render"

    def test_an_ingest_that_raises_is_a_note(self, repo, home, monkeypatch, capsys):
        """The step's own guard, in-process: whatever `ingest` raises becomes one
        NOTE, never a failed session start."""
        hook = _load_hook()
        from lib import evidence_notes

        def boom(*_a, **_k):
            raise RuntimeError("simulated ingest failure")

        monkeypatch.setattr(evidence_notes, "ingest", boom)
        hook._session_start_ingest(repo)
        err = capsys.readouterr().err
        assert "NOTE: evidence ingest" in err and "simulated ingest failure" in err

    def test_an_error_result_after_a_partial_append_says_both(self, repo, home, monkeypatch, capsys):
        hook = _load_hook()
        from lib import evidence_notes

        monkeypatch.setattr(
            evidence_notes, "ingest",
            lambda *_a, **_k: {"status": "error", "appended": 2, "seen": 3, "commits": 1,
                               "reason": "store append failed after 2 record(s) (disk full)"},
        )
        hook._session_start_ingest(repo)
        captured = capsys.readouterr()
        assert captured.out.splitlines() == ["2 evidence fact(s) ingested from refs/notes/prawduct"]
        assert "disk full" in captured.err


def _load_hook():
    import importlib.machinery
    import importlib.util

    loader = importlib.machinery.SourceFileLoader("prawduct_hook_session_ingest", str(HOOK))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module
