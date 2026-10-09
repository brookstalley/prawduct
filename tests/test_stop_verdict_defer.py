"""A turn that is still working defers the session-end gates; a turn that
hands the session over may not say DO NOT CLEAR.

The Stop hook fires at every turn end; its reflection and Critic gates are about
SESSION end. A turn whose standing block says ``RUNNING`` and closes on
``DO NOT CLEAR`` is the agent's own statement that it is still working, so those
two gates defer through the same exit-0 path the in-flight-background-work
deferral uses. Every other gate keeps blocking, and every uncertain reading of
the turn keeps blocking, because this relaxes an authority gate and authority
fails closed.

``YOUR TURN`` or ``COMPLETE`` with ``DO NOT CLEAR`` is a contradiction — the
reader is handed the session and told not to end it, and may sit on both for
days — so it defers nothing and the clear-verdict gate refuses it. The same
gate refuses a ``SAFE TO CLEAR`` whose stated reason is the turn itself ("the
questions are in this message"), because a clear deletes exactly that (#977).

Three layers, each pinned where it can fail:

* ``standing_block`` — what counts as the closing verdict and the disposition,
  and when the two contradict;
* ``gates.turn_declares_in_flight`` / ``turn_contradicts_its_verdict`` /
  ``turn_cites_itself_as_record`` — the payload degradation ladder;
* ``prawduct-hook stop`` end to end — which blockers defer and which do not.

The payload shape is the one Claude Code 2.1.282 writes to a Stop hook's stdin,
captured live: ``last_assistant_message`` beside ``transcript_path``,
``background_tasks`` and ``session_crons``.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from conftest import SHAPED_REFLECTION
from lib import gates, standing_block
from test_plugin_runtime import _make_session_start, run_plugin_hook

PLUGIN = Path(__file__).resolve().parent.parent / "plugin"

_CODE_DIFF = " M src/app.py"


def _block(disposition: str, verdict: str, copy: str = "the reason.") -> str:
    """A standing block in the shape the methodology prescribes."""
    return (
        "Did the work; details above.\n\n"
        "---\n\n"
        "`STATE` — two files changed, committed, suite green.\n\n"
        f"`{disposition}` — the next thing.\n\n"
        f"`{verdict}` — {copy}"
    )


DNC_TURN = _block("RUNNING", "DO NOT CLEAR", "the review is still running.")
SAFE_TURN = _block("COMPLETE", "SAFE TO CLEAR", "nothing is outstanding.")
# The reported defect: an ask handed to the reader, who is told not to clear.
ASK_DNC_TURN = _block("YOUR TURN", "DO NOT CLEAR", "I need your decision first.")
COMPLETE_DNC_TURN = _block("COMPLETE", "DO NOT CLEAR", "the notes are only above.")
ASK_SAFE_TURN = _block("YOUR TURN", "SAFE TO CLEAR", "the decision is in the notes.")
# The puzzles session's own bolded form: `**LABEL:** copy`.
DNC_BOLD_TURN = (
    "The coupon is on your Desktop.\n\n---\n\n"
    "**STATE:** The coupon files are on your Desktop.\n\n"
    "**RUNNING:** The review of this session's code is still going.\n\n"
    "**DO NOT CLEAR:** the review is still running, and clearing now would lose its findings."
)


def _payload(message=None, **extra) -> str:
    body = {
        "session_id": "s-1",
        "transcript_path": "/nonexistent/transcript.jsonl",
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        "background_tasks": [],
        "session_crons": [],
    }
    if message is not None:
        body["last_assistant_message"] = message
    body.update(extra)
    return json.dumps(body)


# ---------------------------------------------------------------------------
# What counts as the closing verdict
# ---------------------------------------------------------------------------


class TestClearVerdict:
    def test_closing_dnc_is_read(self):
        assert standing_block.clear_verdict(DNC_TURN) == standing_block.DO_NOT_CLEAR

    def test_bolded_label_form_is_read(self):
        assert standing_block.clear_verdict(DNC_BOLD_TURN) == standing_block.DO_NOT_CLEAR

    def test_closing_safe_is_read(self):
        assert standing_block.clear_verdict(SAFE_TURN) == standing_block.SAFE_TO_CLEAR

    def test_no_rule_reads_the_final_paragraph(self):
        text = "Stopped here.\n\n`DO NOT CLEAR` — waiting on your answer."
        assert standing_block.clear_verdict(text) == standing_block.DO_NOT_CLEAR

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "   \n\n  ",
            "Just answering a question; no block at all.",
            # A disposition with no clear line.
            "---\n\n`STATE` — done.\n\n`COMPLETE` — nothing needs to.",
            # DO NOT CLEAR mid-prose inside the closing block, not leading it.
            "---\n\n`STATE` — done.\n\n`COMPLETE` — nothing.\n\n"
            "Nothing here says DO NOT CLEAR as a verdict.",
            # Both labels in the closing block.
            "---\n\n`STATE` — done.\n\n`RUNNING` — a review.\n\n"
            "`DO NOT CLEAR` — not SAFE TO CLEAR until the review lands.",
            # The verdict is followed by further text: it is no longer the close.
            DNC_TURN + "\n\nOne more thing I forgot to mention.",
            # Lower-case prose is not the label.
            "---\n\n`STATE` — done.\n\n`RUNNING` — a review.\n\ndo not clear — please.",
            # A longer word that merely starts with the label.
            "---\n\n`STATE` — done.\n\nDO NOT CLEARLY decide yet.",
        ],
        ids=[
            "empty", "blank", "no-block", "no-clear-line",
            "mid-prose-in-block", "both-labels", "trailing-text", "lower-case", "longer-word",
        ],
    )
    def test_no_single_closing_verdict_reads_as_none(self, text):
        assert standing_block.clear_verdict(text) is None

    def test_a_label_above_the_rule_is_outside_the_block(self):
        """The closing block starts after the last `---`: a SAFE TO CLEAR quoted
        above it does not make the block ambiguous."""
        text = "Last turn was SAFE TO CLEAR; this one is not.\n\n" + DNC_TURN
        assert standing_block.clear_verdict(text) == standing_block.DO_NOT_CLEAR

    def test_with_no_rule_only_the_final_paragraph_is_the_block(self):
        text = (
            "Earlier this was SAFE TO CLEAR.\n\n"
            "`DO NOT CLEAR` — the review I just dispatched is running."
        )
        assert standing_block.clear_verdict(text) == standing_block.DO_NOT_CLEAR

    def test_label_quoted_earlier_does_not_count(self):
        """DO NOT CLEAR earlier in the turn; the block closes SAFE: the verdict is
        the close, never a mention."""
        text = "Earlier I wrote DO NOT CLEAR while the review ran.\n\n" + SAFE_TURN
        assert standing_block.clear_verdict(text) == standing_block.SAFE_TO_CLEAR

    def test_non_string_reads_as_none(self):
        assert standing_block.clear_verdict(None) is None  # type: ignore[arg-type]


class TestDisposition:
    @pytest.mark.parametrize(
        "label", ["RUNNING", "YOUR TURN", "COMPLETE"],
    )
    def test_each_disposition_is_read(self, label):
        assert standing_block.disposition(_block(label, "SAFE TO CLEAR")) == label

    def test_bolded_label_form_is_read(self):
        assert standing_block.disposition(DNC_BOLD_TURN) == standing_block.RUNNING

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "Just answering a question; no block at all.",
            # A disposition named inside another line's copy is prose.
            "---\n\n`STATE` — the review is RUNNING.\n\n`SAFE TO CLEAR` — fine.",
            # Two different dispositions lead paragraphs: the block owes one.
            "---\n\n`STATE` — done.\n\n`RUNNING` — a review.\n\n"
            "`YOUR TURN` — pick A.\n\n`DO NOT CLEAR` — the review.",
            # A longer word that merely starts with the label.
            "---\n\n`STATE` — done.\n\nCOMPLETED everything.\n\n`SAFE TO CLEAR` — ok.",
            # Above the rule is outside the block.
            "`YOUR TURN` — earlier.\n\n---\n\n`STATE` — done.\n\n`SAFE TO CLEAR` — ok.",
        ],
        ids=["empty", "no-block", "mid-copy", "two-dispositions", "longer-word", "above-rule"],
    )
    def test_no_single_disposition_reads_as_none(self, text):
        assert standing_block.disposition(text) is None


class TestContradiction:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [(ASK_DNC_TURN, "YOUR TURN"), (COMPLETE_DNC_TURN, "COMPLETE")],
        ids=["your-turn", "complete"],
    )
    def test_a_handed_over_turn_saying_dnc_contradicts(self, text, expected):
        assert standing_block.contradiction(text) == expected

    def test_the_reported_bolded_form_contradicts(self):
        text = (
            "Here is where things stand.\n\n---\n\n"
            "**STATE:** two files changed, uncommitted.\n\n"
            "**YOUR TURN:** decide whether the cache is per-user or global.\n\n"
            "**DO NOT CLEAR:** the analysis above is not on disk yet."
        )
        assert standing_block.contradiction(text) == standing_block.YOUR_TURN

    @pytest.mark.parametrize(
        "text",
        [
            DNC_TURN,
            DNC_BOLD_TURN,
            SAFE_TURN,
            ASK_SAFE_TURN,
            # A verdict with no disposition line: nothing clearly contradicts.
            "Stopped here.\n\n`DO NOT CLEAR` — waiting on your answer.",
            # Both verdicts: no single verdict, so no contradiction to name.
            "---\n\n`STATE` — done.\n\n`YOUR TURN` — pick.\n\n"
            "`DO NOT CLEAR` — not SAFE TO CLEAR yet.",
        ],
        ids=["running-dnc", "running-dnc-bold", "complete-safe", "your-turn-safe",
             "no-disposition", "both-verdicts"],
    )
    def test_everything_else_is_coherent(self, text):
        assert standing_block.contradiction(text) is None

    def test_only_running_may_close_on_dnc(self):
        assert set(standing_block.HANDED_OVER_DISPOSITIONS) == (
            set(standing_block.DISPOSITION_LABELS) - {standing_block.RUNNING}
        )


# Self-citing reasons, verbatim from the 2026-10-09 wave-1 trial (#977) and from
# consumer-repo transcripts, plus session-hygiene.md's own example of the tell.
SELF_CITING_REASONS = [
    ("the questions are in this message", "in this message"),
    ("this message holds the whole ask", "this message holds"),
    ("the analysis is above", "is above"),
    ("The plan exists only in this reply, so clearing now would lose it.", "in this reply"),
    ("Nothing is in flight. This message has the full recommendation.", "This message has"),
]
# Sound reasons that use the same words: each must pass.
SOUND_REASONS = [
    "the decision is in the notes.",
    "nothing lives only in this conversation.",
    "the findings above are in .prawduct/.handoff-notes.md.",
    "no files changed in this turn.",
    "nothing is outstanding.",
    "everything in this reply is also in the handoff notes.",
    "No work is in flight and nothing produced here lives only in this message.",
    "Every finding is saved as a comment on its issue, so none of it exists only in this message.",
]


class TestSelfCitation:
    @pytest.mark.parametrize(("reason", "phrase"), SELF_CITING_REASONS)
    def test_a_reason_that_is_the_turn_is_named(self, reason, phrase):
        assert standing_block.self_citation(
            _block("YOUR TURN", "SAFE TO CLEAR", reason)
        ) == phrase

    def test_the_bolded_label_form_is_read(self):
        text = (
            "Three questions.\n\n---\n\n**STATE:** nothing changed.\n\n"
            "**YOUR TURN:** answer them.\n\n"
            "**SAFE TO CLEAR:** the questions are in this message"
        )
        assert standing_block.self_citation(text) == "in this message"

    @pytest.mark.parametrize("reason", SOUND_REASONS)
    def test_a_sound_reason_passes(self, reason):
        assert standing_block.self_citation(
            _block("YOUR TURN", "SAFE TO CLEAR", reason)
        ) is None

    @pytest.mark.parametrize(
        "text",
        [
            # DO NOT CLEAR says nothing about what survives a clear.
            _block("RUNNING", "DO NOT CLEAR", "the questions are in this message."),
            # The phrase outside the verdict paragraph is prose, not the reason.
            "The questions are in this message.\n\n---\n\n`STATE` — none.\n\n"
            "`YOUR TURN` — answer.\n\n`SAFE TO CLEAR` — the questions are in the notes.",
            "Just an answer; it is all in this message.",
            "",
        ],
        ids=["dnc", "phrase-above-verdict", "no-block", "empty"],
    )
    def test_no_safe_verdict_names_nothing(self, text):
        assert standing_block.self_citation(text) is None


# ---------------------------------------------------------------------------
# The payload ladder
# ---------------------------------------------------------------------------


class TestTurnDeclaresInFlight:
    def test_dnc_turn_defers(self):
        assert gates.turn_declares_in_flight(json.loads(_payload(DNC_TURN))) == (
            True, "DO NOT CLEAR",
        )

    @pytest.mark.parametrize(
        "stop_input",
        [
            None,
            "not a dict",
            [DNC_TURN],
            {},
            {"last_assistant_message": None},
            {"last_assistant_message": 42},
            {"last_assistant_message": ["DO NOT CLEAR"]},
            {"last_assistant_message": "   "},
            {"last_assistant_message": SAFE_TURN},
            {"last_assistant_message": ASK_DNC_TURN},
            {"last_assistant_message": COMPLETE_DNC_TURN},
            {"last_assistant_message": "Stopped.\n\n`DO NOT CLEAR` — waiting on you."},
        ],
        ids=["none", "str", "list", "empty", "null", "int", "list-field", "blank", "safe",
             "your-turn-dnc", "complete-dnc", "dnc-no-disposition"],
    )
    def test_everything_else_blocks(self, stop_input):
        assert gates.turn_declares_in_flight(stop_input) == (False, None)

    @pytest.mark.parametrize(
        ("stop_input", "expected"),
        [
            ({"last_assistant_message": ASK_DNC_TURN}, "YOUR TURN"),
            ({"last_assistant_message": COMPLETE_DNC_TURN}, "COMPLETE"),
            ({"last_assistant_message": DNC_TURN}, None),
            ({"last_assistant_message": ASK_SAFE_TURN}, None),
            ({"last_assistant_message": None}, None),
            ({}, None),
            ("not a dict", None),
        ],
        ids=["your-turn-dnc", "complete-dnc", "running-dnc", "your-turn-safe", "null",
             "empty", "str"],
    )
    def test_contradiction_ladder(self, stop_input, expected):
        assert gates.turn_contradicts_its_verdict(stop_input) == expected

    @pytest.mark.parametrize(
        ("stop_input", "expected"),
        [
            ({"last_assistant_message": _block(
                "YOUR TURN", "SAFE TO CLEAR", "the questions are in this message.")},
             "in this message"),
            ({"last_assistant_message": ASK_SAFE_TURN}, None),
            ({"last_assistant_message": ASK_DNC_TURN}, None),
            ({"last_assistant_message": None}, None),
            ({}, None),
            ("not a dict", None),
        ],
        ids=["self-citing", "your-turn-safe", "your-turn-dnc", "null", "empty", "str"],
    )
    def test_self_citation_ladder(self, stop_input, expected):
        assert gates.turn_cites_itself_as_record(stop_input) == expected

    def test_transcript_is_not_a_fallback(self, tmp_path):
        """With the field absent, a transcript that DOES close on DO NOT CLEAR is
        not read: an older client behaves exactly as before the signal existed."""
        transcript = tmp_path / "t.jsonl"
        transcript.write_text(json.dumps({
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": DNC_TURN}]},
        }) + "\n")
        assert gates.turn_declares_in_flight({"transcript_path": str(transcript)}) == (
            False, None,
        )

    def test_deferred_gate_ids_are_the_registrys_session_end_gates(self):
        """The set names real gate ids, and only the two session-end ones — a
        typo here would silently defer nothing, a widening would defer a gate the
        ruling kept blocking."""
        registry = json.loads((PLUGIN / "hooks" / "gates.json").read_text())
        ids = {g["id"] for g in registry["gates"]}
        assert gates.VERDICT_DEFERRED_GATES == {"reflection", "critic"}
        assert gates.VERDICT_DEFERRED_GATES <= ids


# ---------------------------------------------------------------------------
# End to end through `prawduct-hook stop`
# ---------------------------------------------------------------------------


def _plan_repo(tmp_path: Path, *, reflected: bool) -> Path:
    """Active plan + code diff: the Critic gate blocks. ``reflected=False`` makes
    the reflection gate block too."""
    prawduct = tmp_path / ".prawduct"
    artifacts = prawduct / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
    if reflected:
        (prawduct / ".session-reflected").write_text(SHAPED_REFLECTION)
    (prawduct / ".session-git-baseline").write_text("")
    _make_session_start(prawduct)
    return prawduct


def _blocked_section(stderr: str) -> str:
    """The part of stderr the BLOCKED report prints (empty when nothing blocked)."""
    idx = stderr.find("BLOCKED — resolve before ending session:")
    return stderr[idx:] if idx >= 0 else ""


class TestStopDefersOnTheVerdict:
    def test_dnc_defers_the_critic_gate(self, tmp_path):
        _plan_repo(tmp_path, reflected=True)
        result = run_plugin_hook(
            "stop", tmp_path, git_status=_CODE_DIFF, stdin=_payload(DNC_TURN)
        )
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert "GATES DEFERRED" in result.stderr
        # The note names the VERDICT as the reason, not background tasks.
        assert "says RUNNING and closed on DO NOT CLEAR" in result.stderr
        assert "background task" not in result.stderr
        assert "deferred: [prawduct" in result.stderr and "critic-review" in result.stderr

    def test_dnc_defers_the_reflection_gate(self, tmp_path):
        # No build plan, so no Critic gate: reflection is the only blocker.
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")
        _make_session_start(prawduct)
        blocked = run_plugin_hook("stop", tmp_path, git_status=_CODE_DIFF, stdin=_payload(SAFE_TURN))
        assert blocked.returncode == 2 and "REFLECTION" in blocked.stderr, blocked.stderr
        result = run_plugin_hook("stop", tmp_path, git_status=_CODE_DIFF, stdin=_payload(DNC_TURN))
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert re.search(r"deferred: \[prawduct[^\n]*gate: reflection", result.stderr)

    def test_dnc_defers_both_gates_together(self, tmp_path):
        _plan_repo(tmp_path, reflected=False)
        result = run_plugin_hook(
            "stop", tmp_path, git_status=_CODE_DIFF, stdin=_payload(DNC_BOLD_TURN)
        )
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert "gate: reflection" in result.stderr
        assert "gate: critic-review" in result.stderr

    def test_deferral_rearms_on_the_next_turn(self, tmp_path):
        """Stateless: a DO NOT CLEAR Stop followed by a SAFE TO CLEAR Stop on the
        same fixture blocks — the verdict defers, it does not waive."""
        _plan_repo(tmp_path, reflected=True)
        first = run_plugin_hook("stop", tmp_path, git_status=_CODE_DIFF, stdin=_payload(DNC_TURN))
        assert first.returncode == 0, first.stderr
        second = run_plugin_hook("stop", tmp_path, git_status=_CODE_DIFF, stdin=_payload(SAFE_TURN))
        assert second.returncode == 2, second.stderr
        assert "CRITIC" in _blocked_section(second.stderr)


class TestStopStillBlocks:
    @pytest.mark.parametrize(
        "stdin",
        [
            _payload(SAFE_TURN),
            _payload("---\n\n`STATE` — done.\n\n`COMPLETE` — nothing needs to."),
            _payload("Here is the answer to your question."),
            _payload(
                "---\n\n`STATE` — done.\n\n`RUNNING` — a review.\n\n"
                "`DO NOT CLEAR` — not SAFE TO CLEAR until it lands."
            ),
            _payload("I said DO NOT CLEAR earlier, but that is over.\n\n" + SAFE_TURN),
            _payload(),  # field absent; transcript_path points at a missing file
            "not json {{{",
            json.dumps(["DO NOT CLEAR"]),
            "",
        ],
        ids=[
            "safe-to-clear", "complete-no-clear-line", "no-label", "both-labels",
            "label-quoted-earlier", "missing-transcript", "garbage", "non-object", "no-stdin",
        ],
    )
    def test_blocks_exactly_as_before(self, tmp_path, stdin):
        _plan_repo(tmp_path, reflected=True)
        result = run_plugin_hook("stop", tmp_path, git_status=_CODE_DIFF, stdin=stdin)
        assert result.returncode == 2, (result.stdout, result.stderr)
        assert "CRITIC" in _blocked_section(result.stderr)
        assert "GATES DEFERRED" not in result.stderr

    def test_unreadable_transcript_with_no_field_blocks(self, tmp_path):
        _plan_repo(tmp_path, reflected=True)
        transcript = tmp_path / "t.jsonl"
        transcript.write_text("\x00 not json\n")
        transcript.chmod(0o000)
        try:
            result = run_plugin_hook(
                "stop", tmp_path, git_status=_CODE_DIFF,
                stdin=_payload(transcript_path=str(transcript)),
            )
        finally:
            transcript.chmod(0o644)
        assert result.returncode == 2, (result.stdout, result.stderr)
        assert "GATES DEFERRED" not in result.stderr

    def test_a_non_session_end_gate_still_blocks_on_a_dnc_turn(self, tmp_path):
        """The verdict defers the session-end gates ONLY. A `Type: trivial` chunk
        outside its fileset bounds still blocks, and the Critic blocker that
        deferred is named rather than hidden, and is not in the BLOCKED report."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text(
            "# Build Plan\n\n## Status\n- [ ] Chunk 01: tweak a skill\n\n"
            "## Build Chunks\n\n"
            "### Chunk 01: tweak a skill\n"
            "**Type:** trivial\n"
            "**Trivial because:** a one-word typo fix in a skill doc.\n"
        )
        (prawduct / ".session-reflected").write_text(SHAPED_REFLECTION)
        (prawduct / ".session-git-baseline").write_text("")
        _make_session_start(prawduct)
        result = run_plugin_hook(
            "stop", tmp_path, git_status=" M skills/critic/SKILL.md", stdin=_payload(DNC_TURN)
        )
        assert result.returncode == 2, (result.stdout, result.stderr)
        blocked = _blocked_section(result.stderr)
        assert "TYPE: TRIVIAL" in blocked
        assert "gate: critic-review" not in blocked
        assert "GATES DEFERRED" in result.stderr
        assert "deferred: [prawduct" in result.stderr


class TestClearVerdictGate:
    """A turn that hands the session over while saying DO NOT CLEAR is refused,
    whatever else the Stop would do — and neither deferral can swallow it."""

    @staticmethod
    def _quiet_repo(tmp_path: Path) -> None:
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")
        _make_session_start(prawduct)

    @pytest.mark.parametrize(
        ("message", "label"),
        [(ASK_DNC_TURN, "YOUR TURN"), (COMPLETE_DNC_TURN, "COMPLETE")],
        ids=["your-turn", "complete"],
    )
    def test_blocks_on_a_clean_tree(self, tmp_path, message, label):
        """No changes, so no other gate fires: the contradiction alone blocks."""
        self._quiet_repo(tmp_path)
        result = run_plugin_hook("stop", tmp_path, git_status="", stdin=_payload(message))
        assert result.returncode == 2, (result.stdout, result.stderr)
        blocked = _blocked_section(result.stderr)
        assert "gate: clear-verdict" in blocked
        assert f"closes on `{label}` and `DO NOT CLEAR`" in blocked
        assert ".prawduct/.handoff-notes.md" in blocked
        # The belief behind most of this gate's fires in consumer repos: that a
        # server or recorder the session started would die with a clear.
        assert "a clear ends the conversation, not the process" in blocked

    @pytest.mark.parametrize(
        "message",
        [DNC_TURN, ASK_SAFE_TURN, SAFE_TURN, "Just an answer."],
        ids=["running-dnc", "your-turn-safe", "complete-safe", "no-block"],
    )
    def test_a_coherent_turn_passes(self, tmp_path, message):
        self._quiet_repo(tmp_path)
        result = run_plugin_hook("stop", tmp_path, git_status="", stdin=_payload(message))
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert "CLEAR VERDICT" not in result.stderr

    def test_a_handed_over_dnc_defers_no_session_end_gate(self, tmp_path):
        """The old dodge: YOUR TURN + DO NOT CLEAR used to defer the Critic and
        reflection gates. Now both fire beside the contradiction."""
        _plan_repo(tmp_path, reflected=False)
        result = run_plugin_hook(
            "stop", tmp_path, git_status=_CODE_DIFF, stdin=_payload(ASK_DNC_TURN)
        )
        assert result.returncode == 2, (result.stdout, result.stderr)
        blocked = _blocked_section(result.stderr)
        assert "gate: clear-verdict" in blocked
        assert "gate: critic-review" in blocked
        assert "gate: reflection" in blocked
        assert "GATES DEFERRED" not in result.stderr

    def test_background_work_defers_the_gates_but_not_the_contradiction(self, tmp_path):
        """In-flight work defers every session-end blocker; the message is still
        wrong for the person reading it, so the contradiction still blocks."""
        _plan_repo(tmp_path, reflected=True)
        stdin = _payload(
            ASK_DNC_TURN,
            background_tasks=[{"id": "t-1", "type": "subagent", "agent_type": "Explore"}],
        )
        result = run_plugin_hook("stop", tmp_path, git_status=_CODE_DIFF, stdin=stdin)
        assert result.returncode == 2, (result.stdout, result.stderr)
        assert "GATES DEFERRED" in result.stderr
        blocked = _blocked_section(result.stderr)
        assert "gate: clear-verdict" in blocked
        assert "gate: critic-review" not in blocked

    @pytest.mark.parametrize(("reason", "phrase"), SELF_CITING_REASONS[:3])
    def test_a_self_citing_safe_to_clear_blocks(self, tmp_path, reason, phrase):
        """The trial's phrasings: no other gate fires, so the reason alone blocks."""
        self._quiet_repo(tmp_path)
        message = _block("YOUR TURN", "SAFE TO CLEAR", reason)
        result = run_plugin_hook("stop", tmp_path, git_status="", stdin=_payload(message))
        assert result.returncode == 2, (result.stdout, result.stderr)
        blocked = _blocked_section(result.stderr)
        assert "gate: clear-verdict" in blocked
        assert f'("{phrase}")' in blocked
        assert ".prawduct/.handoff-notes.md" in blocked

    def test_background_work_does_not_swallow_a_self_citation(self, tmp_path):
        _plan_repo(tmp_path, reflected=True)
        stdin = _payload(
            _block("YOUR TURN", "SAFE TO CLEAR", "the questions are in this message."),
            background_tasks=[{"id": "t-1", "type": "subagent", "agent_type": "Explore"}],
        )
        result = run_plugin_hook("stop", tmp_path, git_status=_CODE_DIFF, stdin=stdin)
        assert result.returncode == 2, (result.stdout, result.stderr)
        assert "gate: clear-verdict" in _blocked_section(result.stderr)

    def test_the_gate_has_a_registry_row(self):
        registry = json.loads((PLUGIN / "hooks" / "gates.json").read_text())
        assert "clear-verdict" in {g["id"] for g in registry["gates"]}


# ---------------------------------------------------------------------------
# The vocabulary has one code home, and the prose states exactly it
# ---------------------------------------------------------------------------


_METHODOLOGY = PLUGIN / "methodology"
_LABEL_TOKEN = re.compile(r"`([A-Z][A-Z ]+[A-Z])`")


def _section(text: str, heading: str) -> str:
    start = text.index(heading)
    nxt = text.find("\n## ", start + len(heading))
    return text[start:] if nxt < 0 else text[start:nxt]


class TestVocabularyHasOneHome:
    """The labels live in ``lib/standing_block``; the two prose surfaces that
    teach the block must name exactly that set — no label missing, none extra —
    so a rename in either place fails here instead of drifting."""

    def test_session_hygiene_template_states_exactly_the_vocabulary(self):
        text = (_METHODOLOGY / "session-hygiene.md").read_text(encoding="utf-8")
        fence = re.search(r"```\n(---.*?)```", text, re.S)
        assert fence, "session-hygiene.md lost its fenced standing-block template"
        assert set(_LABEL_TOKEN.findall(fence.group(1))) == set(standing_block.ALL_LABELS)

    def test_digest_closing_section_states_exactly_the_vocabulary(self):
        text = (_METHODOLOGY / "session-digest.md").read_text(encoding="utf-8")
        section = _section(text, "## Closing the turn")
        assert set(_LABEL_TOKEN.findall(section)) == set(standing_block.ALL_LABELS)

    def test_the_tuples_partition_the_vocabulary(self):
        assert standing_block.ALL_LABELS == (
            standing_block.STATE,
            *standing_block.DISPOSITION_LABELS,
            *standing_block.CLEAR_LABELS,
        )
        assert len(set(standing_block.ALL_LABELS)) == len(standing_block.ALL_LABELS)
