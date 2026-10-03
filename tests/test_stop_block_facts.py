"""Every Stop-hook block, and every session boundary, leaves a countable fact.

A gate that blocks a turn used to leave nothing behind but the model's
transcript, so "does this gate earn its cost?" had no answer short of mining
Claude Code's session logs, which are kept for weeks. The nonfunctional norm
*a control names the yield it expects and emits it observably* asks for the
answer to be queryable, so:

* a blocked Stop appends one ``guard-refusal`` fact per blocking gate, through
  the class sink every other control already uses (``guard`` is
  ``stop-gate:<gate id>``; facts from one Stop share a ``stop`` id);
* a session boundary appends one ``session-start`` fact, the denominator that
  turns a block count into a rate.

Recording is advice: it never changes the Stop exit code, and a deferred gate
records nothing because it did not block. Fixture shape mirrors
``tests/test_reflection_gate.py``: a real git repo, the hook called in-process.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent / "plugin"

sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from conftest import SHAPED_REFLECTION  # noqa: E402
from lib import evidence  # noqa: E402

_hook_loader = importlib.machinery.SourceFileLoader(
    "prawduct_hook_stop_block_facts", str(_ROOT / "bin" / "prawduct-hook")
)
_hook_spec = importlib.util.spec_from_loader("prawduct_hook_stop_block_facts", _hook_loader)
_hook = importlib.util.module_from_spec(_hook_spec)
_hook_loader.exec_module(_hook)


def _block(disposition: str, verdict: str) -> str:
    return (
        "Did the work.\n\n---\n\n`STATE` — one file changed.\n\n"
        f"`{disposition}` — the next thing.\n\n`{verdict}` — the reason."
    )


DNC_TURN = _block("RUNNING", "DO NOT CLEAR")
ASK_DNC_TURN = _block("YOUR TURN", "DO NOT CLEAR")
SAFE_TURN = _block("COMPLETE", "SAFE TO CLEAR")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(repo), capture_output=True, text=True, timeout=15, check=True,
    ).stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    (repo / "code.py").write_text("x = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c1")
    (repo / ".prawduct").mkdir()
    (repo / ".prawduct" / ".session-git-baseline").write_text(
        _git(repo, "status", "--porcelain")
    )
    (repo / ".prawduct" / ".session-base-tree").write_text(
        _git(repo, "rev-parse", "HEAD^{tree}")
    )
    return repo


def _commit_code(repo: Path) -> None:
    (repo / "code.py").write_text("x = 2\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c2")


def _stop_facts(repo: Path) -> list[dict]:
    return [
        f
        for f in evidence.facts_of_kind(evidence.read_facts(repo), "guard-refusal")
        if str(f["body"].get("guard", "")).startswith("stop-gate:")
    ]


def _stop(repo: Path, message: "str | None" = None) -> int:
    stop_input = {} if message is None else {"last_assistant_message": message}
    return _hook.cmd_stop(repo, stop_input)


class TestABlockedStopIsRecorded:
    def test_one_fact_per_blocking_gate(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _commit_code(repo)
        assert _stop(repo) == 2
        facts = _stop_facts(repo)
        assert [f["body"]["gate"] for f in facts] == ["reflection"]
        assert facts[0]["body"]["guard"] == "stop-gate:reflection"
        assert facts[0]["body"]["co_gates"] == []

    def test_gates_blocking_one_stop_share_its_id_and_name_each_other(self, tmp_path, capsys):
        """Reflection and clear-verdict block together: two facts, one Stop."""
        repo = _repo(tmp_path)
        _commit_code(repo)
        assert _stop(repo, ASK_DNC_TURN) == 2
        facts = _stop_facts(repo)
        gates = sorted(f["body"]["gate"] for f in facts)
        assert gates == ["clear-verdict", "reflection"]
        assert len({f["body"]["stop"] for f in facts}) == 1
        by_gate = {f["body"]["gate"]: f["body"] for f in facts}
        assert by_gate["reflection"]["co_gates"] == ["clear-verdict"]
        assert by_gate["clear-verdict"]["co_gates"] == ["reflection"]

    def test_two_blocked_stops_are_two_events(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _commit_code(repo)
        _stop(repo)
        _stop(repo)
        facts = _stop_facts(repo)
        assert len(facts) == 2
        assert facts[0]["body"]["stop"] != facts[1]["body"]["stop"]


class TestNothingIsRecordedWithoutABlock:
    def test_a_clean_stop_records_nothing(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _commit_code(repo)
        (repo / ".prawduct" / ".session-reflected").write_text(SHAPED_REFLECTION)
        assert _stop(repo, SAFE_TURN) == 0
        assert _stop_facts(repo) == []

    def test_a_deferred_gate_records_nothing(self, tmp_path, capsys):
        """RUNNING + DO NOT CLEAR defers the reflection gate: it did not block."""
        repo = _repo(tmp_path)
        _commit_code(repo)
        assert _stop(repo, DNC_TURN) == 0
        assert _stop_facts(repo) == []


class TestRecordingIsAdvice:
    def test_a_store_failure_keeps_the_block_and_says_so(self, tmp_path, capsys, monkeypatch):
        repo = _repo(tmp_path)
        _commit_code(repo)
        monkeypatch.setattr(
            evidence, "append_fact",
            lambda *a, **k: {"status": "error", "reason": "disk full"},
        )
        assert _stop(repo) == 2
        err = capsys.readouterr().err
        assert "NOTE:" in err and "disk full" in err


class TestSessionStartFacts:
    def _starts(self, repo: Path) -> list[dict]:
        return evidence.facts_of_kind(evidence.read_facts(repo), "session-start")

    def test_a_boundary_appends_one(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        assert _hook.cmd_clear(repo, ["--session-start"]) == 0
        assert len(self._starts(repo)) == 1

    def test_a_continuation_appends_none(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        assert _hook.cmd_clear(repo, ["--session-start", "--brief-only"]) == 0
        assert self._starts(repo) == []

    def test_a_session_start_line_does_not_move_the_coverage_fingerprint(self, tmp_path, capsys):
        """Observational: a session boundary must not evict every cached verdict."""
        repo = _repo(tmp_path)
        assert evidence.append_session_start(repo)["status"] == "appended"
        before = evidence.read_facts(repo)["coverage_fingerprint"]
        assert before is not None
        assert evidence.append_session_start(repo)["status"] == "appended"
        assert evidence.read_facts(repo)["coverage_fingerprint"] == before
