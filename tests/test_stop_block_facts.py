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
import json
import subprocess
import sys
from pathlib import Path

import pytest

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


SELF_CITING_TURN = _block("COMPLETE", "SAFE TO CLEAR").replace(
    "the reason.", "the open questions are in this message."
)


def _clear_fact(repo: Path, gate: str) -> dict:
    (fact,) = [f["body"] for f in _stop_facts(repo) if f["body"]["gate"] == gate]
    return fact


class TestAClearGateRecordsWhyItFired:
    """The clear gates record which check failed and what the hook could see,
    so `stats` can tell a catch from a slip without any turn text."""

    def test_clear_verdict_names_the_disposition_it_paired(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        assert _stop(repo, ASK_DNC_TURN) == 2
        fact = _clear_fact(repo, "clear-verdict")
        assert fact["reason"] == "handed-over-your-turn"
        assert fact["observed"] == {
            "work_live": False, "notes_present": False, "session_changed": False,
        }

    def test_complete_is_its_own_reason(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        assert _stop(repo, _block("COMPLETE", "DO NOT CLEAR")) == 2
        assert _clear_fact(repo, "clear-verdict")["reason"] == "handed-over-complete"

    def test_background_work_is_observed_as_live(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        stop_input = {
            "last_assistant_message": ASK_DNC_TURN,
            "background_tasks": [{"id": "t1", "description": "suite"}],
        }
        assert _hook.cmd_stop(repo, stop_input) == 2
        assert _clear_fact(repo, "clear-verdict")["observed"]["work_live"] is True

    def test_a_live_critic_review_is_observed_as_live(self, tmp_path, capsys):
        from lib import critic_marker

        repo = _repo(tmp_path)
        assert critic_marker.write_marker(repo / ".prawduct")
        assert _stop(repo, ASK_DNC_TURN) == 2
        assert _clear_fact(repo, "clear-verdict")["observed"]["work_live"] is True

    def test_written_handoff_notes_are_observed(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        (repo / ".prawduct" / ".handoff-notes.md").write_text("# notes\nwhere I stopped\n")
        assert _stop(repo, SELF_CITING_TURN) == 2
        assert _clear_fact(repo, "clear-reason")["observed"]["notes_present"] is True

    def test_empty_handoff_notes_are_not_notes(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        (repo / ".prawduct" / ".handoff-notes.md").write_text("  \n")
        assert _stop(repo, SELF_CITING_TURN) == 2
        assert _clear_fact(repo, "clear-reason")["observed"]["notes_present"] is False

    def test_a_session_that_changed_nothing_is_observed_as_unchanged(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        assert _stop(repo, SELF_CITING_TURN) == 2
        assert _clear_fact(repo, "clear-reason")["observed"]["session_changed"] is False

    def test_a_session_that_committed_work_is_observed_as_changed(self, tmp_path, capsys):
        """Committed counts: the span is the session base tree, not porcelain."""
        repo = _repo(tmp_path)
        _commit_code(repo)
        _stop(repo, SELF_CITING_TURN)
        assert _clear_fact(repo, "clear-reason")["observed"]["session_changed"] is True

    def test_clear_reason_names_the_citation_kind_and_never_the_phrase(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        assert _stop(repo, SELF_CITING_TURN) == 2
        fact = _clear_fact(repo, "clear-reason")
        assert fact["reason"] == "in-this-message"
        assert "are in this message" not in json.dumps(fact)

    def test_a_gate_with_no_reason_records_none(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _commit_code(repo)
        assert _stop(repo) == 2
        (fact,) = _stop_facts(repo)
        assert "reason" not in fact["body"] and "observed" not in fact["body"]


class TestTheSinkKeepsOnlyMachineShapedDetail:
    """`reason` and `observed` must be machine-shaped. A value that is not is
    dropped and named in `refused_fields`, and the firing still lands: a lost
    count is the worse error, and the dropped value never reaches the store."""

    @pytest.mark.parametrize("reason", ["", "Has Spaces", "x" * 49, "trailing-", 3])
    def test_a_reason_that_is_not_a_slug_is_dropped_and_the_firing_kept(self, tmp_path, reason):
        repo = _repo(tmp_path)
        result = evidence.append_guard_refusal(repo, "g", {}, reason=reason)
        assert result["status"] == "appended"
        assert result["refused_fields"] == ["reason"]
        (fact,) = evidence.facts_of_kind(evidence.read_facts(repo), "guard-refusal")
        assert "reason" not in fact["body"]
        assert fact["body"]["refused_fields"] == ["reason"]

    @pytest.mark.parametrize(
        "observed",
        [
            {"note": "the questions are in this message"},
            {"nested": {"a": True}},
            {"Bad Key": True},
            ["not", "a", "dict"],
        ],
    )
    def test_an_observation_that_could_carry_prose_is_dropped(self, tmp_path, observed):
        repo = _repo(tmp_path)
        result = evidence.append_guard_refusal(repo, "g", {}, reason="spent", observed=observed)
        assert result["status"] == "appended" and result["refused_fields"] == ["observed"]
        (fact,) = evidence.facts_of_kind(evidence.read_facts(repo), "guard-refusal")
        assert "observed" not in fact["body"] and fact["body"]["reason"] == "spent"
        assert "this message" not in json.dumps(fact)

    def test_well_formed_values_land_in_the_body(self, tmp_path):
        repo = _repo(tmp_path)
        result = evidence.append_guard_refusal(
            repo, "g", {"k": 1}, reason="spent",
            observed={"live": True, "count": 2, "mode": "chunk", "seen": None},
        )
        assert result["status"] == "appended" and "refused_fields" not in result
        (fact,) = evidence.facts_of_kind(evidence.read_facts(repo), "guard-refusal")
        assert "refused_fields" not in fact["body"]
        assert fact["body"]["reason"] == "spent"
        assert fact["body"]["observed"] == {"live": True, "count": 2, "mode": "chunk", "seen": None}
        assert fact["body"]["k"] == 1

    def test_a_dropped_detail_on_a_stop_block_says_so_and_keeps_the_count(
        self, tmp_path, capsys, monkeypatch
    ):
        repo = _repo(tmp_path)
        monkeypatch.setattr(_hook, "_clear_observations", lambda *a: {"Bad Key": True})
        assert _stop(repo, ASK_DNC_TURN) == 2
        err = capsys.readouterr().err
        assert "recorded without its observed" in err
        (fact,) = _stop_facts(repo)
        assert fact["body"]["reason"] == "handed-over-your-turn"
        assert "observed" not in fact["body"]

    def test_a_well_formed_block_prints_no_dropped_detail_note(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        assert _stop(repo, ASK_DNC_TURN) == 2
        assert "recorded without its" not in capsys.readouterr().err


class TestEveryDeclaredReasonIsRecordable:
    """A declared reason the sink would drop is a firing counted as
    unspecified forever, and no single-case test would notice."""

    @pytest.mark.parametrize(
        "reason_text, kind",
        [
            ("the open questions are in this message.", "in-this-message"),
            ("this reply holds the plan.", "message-holds"),
            ("the questions are above.", "above-below"),
        ],
    )
    def test_each_citation_form_records_its_kind(self, tmp_path, capsys, reason_text, kind):
        repo = _repo(tmp_path)
        turn = _block("COMPLETE", "SAFE TO CLEAR").replace("the reason.", reason_text)
        assert _stop(repo, turn) == 2
        assert _clear_fact(repo, "clear-reason")["reason"] == kind

    def test_the_parametrized_kinds_are_every_kind(self):
        from lib import standing_block

        assert set(standing_block.SELF_CITATION_KINDS) == {
            "in-this-message", "message-holds", "above-below"
        }

    def test_every_declared_reason_is_a_slug(self):
        from lib import standing_block

        declared = (*standing_block.SELF_CITATION_KINDS, *standing_block.CLEAR_VERDICT_REASONS)
        assert declared and all(evidence._is_slug(r) for r in declared)

    def test_the_telemetry_doc_lists_every_declared_reason_in_its_gate_row(self):
        from lib import standing_block

        doc = (_ROOT / "docs" / "governance-telemetry.md").read_text()
        rows = {
            line.split("|")[1].strip(" `"): line
            for line in doc.splitlines()
            if line.startswith("| `clear-")
        }
        assert set(rows) == {"clear-verdict", "clear-reason"}
        for reason in standing_block.CLEAR_VERDICT_REASONS:
            assert f"`{reason}`" in rows["clear-verdict"]
        for kind in standing_block.SELF_CITATION_KINDS:
            assert f"`{kind}`" in rows["clear-reason"]


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


class TestEdges:
    def test_a_blocker_without_a_gate_id_records_as_unattributed(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _hook._record_stop_block(repo, ["a plain-string blocker"])
        assert [f["body"]["gate"] for f in _stop_facts(repo)] == ["unattributed"]

    def test_an_unexpected_error_while_recording_keeps_the_block(self, tmp_path, capsys, monkeypatch):
        repo = _repo(tmp_path)
        _commit_code(repo)

        def boom(*a, **k):
            raise ValueError("surprise")

        monkeypatch.setattr(evidence, "append_stop_block", boom)
        assert _stop(repo) == 2
        assert "ValueError: surprise" in capsys.readouterr().err

    def test_a_failed_session_start_append_says_so(self, tmp_path, capsys, monkeypatch):
        repo = _repo(tmp_path)
        monkeypatch.setattr(
            evidence, "append_session_start",
            lambda *a, **k: {"status": "error", "reason": "disk full"},
        )
        assert _hook.cmd_clear(repo, ["--session-start"]) == 0
        err = capsys.readouterr().err
        assert "NOTE:" in err and "disk full" in err

    def test_an_unexpected_error_while_recording_a_session_does_not_fail_session_start(
        self, tmp_path, capsys, monkeypatch
    ):
        repo = _repo(tmp_path)

        def boom(*a, **k):
            raise ValueError("surprise")

        monkeypatch.setattr(evidence, "append_session_start", boom)
        assert _hook.cmd_clear(repo, ["--session-start"]) == 0
        assert "ValueError: surprise" in capsys.readouterr().err

    def test_evidence_list_shows_both(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        evidence.append_session_start(repo)
        evidence.append_stop_block(repo, ["reflection"])
        assert evidence.evidence_cmd(repo, ["list"]) == 0
        out = capsys.readouterr().out
        assert "session-start" in out
        assert "guard=stop-gate:reflection" in out
