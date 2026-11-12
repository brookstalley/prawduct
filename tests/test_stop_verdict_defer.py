"""A turn that is still working defers the session-end gates; a turn that
hands the session over may not say DO NOT CLEAR.

The Stop hook fires at every turn end; its reflection and Critic gates are about
SESSION end. A turn whose close says ``RUNNING`` and ``DO NOT CLEAR`` — on the
one line the methodology now prescribes, or in the older three-paragraph
block sessions on an older digest still write — is the agent's own statement that it is still working, so those
two gates defer through the same exit-0 path the in-flight-background-work
deferral uses. Every other gate keeps blocking, and every uncertain reading of
the turn keeps blocking, because this relaxes an authority gate and authority
fails closed.

``COMPLETE`` with ``DO NOT CLEAR`` is a contradiction — the reader is handed
the session and told not to end it, and may sit on both for days — so it defers
nothing, and the clear-verdict check records it without refusing it. So does
``YOUR TURN`` with ``DO NOT CLEAR``, unless the hook observes work a clear would
kill (a harness background task or a live Critic review): then the hold is as
true as ``RUNNING``'s and nothing is recorded. The clear-reason check records,
without refusing, a ``SAFE TO CLEAR`` whose stated reason is the turn itself
("the questions are in this message"), because a clear deletes exactly that
(#977, retired from blocking by #1131).

Three layers, each pinned where it can fail:

* ``standing_block`` — what counts as the closing verdict and the disposition,
  and when the two contradict;
* ``gates.turn_declares_in_flight`` / ``turn_contradicts_its_verdict`` /
  ``turn_self_citation`` — the payload degradation ladder;
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
from lib import gates, host, standing_block
from test_plugin_runtime import _make_session_start, run_plugin_hook

PLUGIN = Path(__file__).resolve().parent.parent / "plugin"

_CODE_DIFF = " M src/app.py"


def _block(disposition: str, verdict: str, copy: str = "the reason.") -> str:
    """The three-paragraph close sessions on an older digest still write."""
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


def _line(disposition: str, verdict: str, reason: str = "the reason.") -> str:
    """A turn closing on the one-line close the methodology prescribes."""
    return f"Did the work; details above.\n\n`{disposition}` · `{verdict}` — {reason}"


DNC_LINE = _line("RUNNING", "DO NOT CLEAR", "the cumulative review is in flight, about 4 minutes.")
SAFE_LINE = _line("COMPLETE", "SAFE TO CLEAR", "nothing is outstanding.")
ASK_DNC_LINE = _line("YOUR TURN", "DO NOT CLEAR", "I need your decision first.")
# The older hand-over shape: the asks just above the line, which follows them
# without a blank line — the last LINE is the close, not the last paragraph.
# Still read, since a turn with no asks header closes on its last line.
ASK_SAFE_LINE = (
    "Two decisions for you.\n\n"
    "1. Merge commit or squash? Recommended: merge commit.\n"
    "2. Keep the flag one more release? Recommended: yes.\n"
    "`YOUR TURN` · `SAFE TO CLEAR` — the plan is in the handoff notes."
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


class TestTheOneLineClose:
    """The close is one line, last: disposition, clear verdict, a short reason.
    The older three-paragraph close is still read (above), because sessions on
    an older digest still write it."""

    @pytest.mark.parametrize(
        ("text", "disposition", "verdict"),
        [
            (DNC_LINE, "RUNNING", "DO NOT CLEAR"),
            (SAFE_LINE, "COMPLETE", "SAFE TO CLEAR"),
            (ASK_DNC_LINE, "YOUR TURN", "DO NOT CLEAR"),
            (ASK_SAFE_LINE, "YOUR TURN", "SAFE TO CLEAR"),
            # Natural variants of the separator and decoration.
            ("Done.\n\n**RUNNING · DO NOT CLEAR** — the review.", "RUNNING", "DO NOT CLEAR"),
            ("Done.\n\n`RUNNING` / `DO NOT CLEAR` — the review.", "RUNNING", "DO NOT CLEAR"),
            ("Done.\n\n`RUNNING` — `DO NOT CLEAR`: the review.", "RUNNING", "DO NOT CLEAR"),
            ("Done.\n\n`COMPLETE` | `SAFE TO CLEAR`", "COMPLETE", "SAFE TO CLEAR"),
            ("Done.\n\n`COMPLETE` `SAFE TO CLEAR`", "COMPLETE", "SAFE TO CLEAR"),
            # After a rule line.
            ("Done.\n\n---\n\n`RUNNING` · `DO NOT CLEAR` — x.", "RUNNING", "DO NOT CLEAR"),
            # A label quoted earlier in the turn does not move the line's verdict.
            ("Last turn said SAFE TO CLEAR.\n\n" + DNC_LINE, "RUNNING", "DO NOT CLEAR"),
        ],
        ids=["running-dnc", "complete-safe", "your-turn-dnc", "asks-above",
             "bold-whole", "slash", "dash-colon", "pipe", "space-only", "after-rule",
             "label-quoted-earlier"],
    )
    def test_disposition_and_verdict_are_read(self, text, disposition, verdict):
        assert standing_block.disposition(text) == disposition
        assert standing_block.clear_verdict(text) == verdict

    @pytest.mark.parametrize(
        "text",
        [
            # Labels quoted mid-prose: the line does not LEAD with a disposition.
            "Done.\n\nThe suite is RUNNING · DO NOT CLEAR until it lands.",
            "Done.\n\nI said `RUNNING` · `DO NOT CLEAR` last turn; now it is over.",
            # A disposition followed by prose, then a verdict later on the line.
            "Done.\n\n`RUNNING` the suite now, so DO NOT CLEAR yet.",
            # Both verdicts on the line.
            "Done.\n\n`RUNNING` · `DO NOT CLEAR` — not SAFE TO CLEAR until it lands.",
            # Text after the line: it is no longer the close.
            DNC_LINE + "\n\nOne more thing I forgot.",
            # Lower-case prose is not the label.
            "Done.\n\nrunning · do not clear — the review.",
            # A longer word that starts with the label.
            "Done.\n\n`RUNNING` · DO NOT CLEARLY decide.",
        ],
        ids=["mid-prose", "quoted-in-sentence", "prose-between", "both-verdicts",
             "trailing-text", "lower-case", "longer-word"],
    )
    def test_no_verdict_where_the_line_does_not_state_one(self, text):
        assert standing_block.clear_verdict(text) is None

    def test_mid_prose_states_no_disposition_either(self):
        assert standing_block.disposition(
            "Done.\n\nThe suite is RUNNING · DO NOT CLEAR until it lands."
        ) is None

    def test_a_handed_over_line_saying_dnc_contradicts(self):
        assert standing_block.contradiction(ASK_DNC_LINE) == standing_block.YOUR_TURN
        assert standing_block.contradiction(DNC_LINE) is None
        assert standing_block.contradiction(ASK_SAFE_LINE) is None

    @pytest.mark.parametrize(("reason", "phrase"), [
        ("the questions are in this message.", "are in this message"),
        ("see above.", "see above"),
    ])
    def test_a_self_citing_line_is_named(self, reason, phrase):
        assert standing_block.self_citation(_line("YOUR TURN", "SAFE TO CLEAR", reason)) == phrase

    def test_the_asks_above_the_line_are_not_its_reason(self):
        """Only what follows the verdict on the line is its reason: an ask
        above it that happens to say 'this message' is not a citation."""
        text = (
            "1. The whole plan is in this message: approve it? Recommended: yes.\n"
            "`YOUR TURN` · `SAFE TO CLEAR` — nothing is running."
        )
        assert standing_block.self_citation(text) is None
        assert standing_block.verdict_line(text).startswith("`YOUR TURN`")


def _with_asks(close: str, *asks: str, header: str = "**Needs you:**") -> str:
    """A turn whose asks for the user come last: the one-line close, a blank
    line, then the asks block under its header — the shape the methodology now
    prescribes for a turn that needs the user."""
    numbered = "\n".join(f"{i}. {ask}" for i, ask in enumerate(asks, 1))
    return f"Did the work; details above.\n\n{close}\n\n{header}\n{numbered}"


_DNC_CLOSE = "`RUNNING` · `DO NOT CLEAR` — the verify pass is running; a clear would lose it."
_ASK_SAFE_CLOSE = "`YOUR TURN` · `SAFE TO CLEAR` — the plan is in the handoff notes."
_ASK = "Store format 16 for the servable figure? I recommend yes."
DNC_ASKS = _with_asks(_DNC_CLOSE, _ASK)
# The same turn with the header dropped: the last line is an ask, not a close.
DNC_ASKS_NO_HEADER = f"Did the work; details above.\n\n{_DNC_CLOSE}\n\n1. {_ASK}"


class TestTheAsksBlock:
    """A turn that needs the user ends with its asks, under the fixed
    ``**Needs you:**`` header, AFTER the one-line close. The close is then read
    from the line just before that header — and only there, because this
    reading relaxes an authority gate: only the exact header opens the block,
    the close must be the line immediately before it, and nothing inside the
    block is ever read as the verdict."""

    def test_the_header_is_the_module_constant(self):
        assert standing_block.ASKS_HEADER == "**Needs you:**"

    @pytest.mark.parametrize(
        ("text", "disposition", "verdict"),
        [
            (DNC_ASKS, "RUNNING", "DO NOT CLEAR"),
            (_with_asks(_ASK_SAFE_CLOSE, _ASK, "Keep the flag? I recommend yes."),
             "YOUR TURN", "SAFE TO CLEAR"),
            # No blank line between the close and the header.
            (f"Done.\n\n{_DNC_CLOSE}\n**Needs you:**\n1. {_ASK}", "RUNNING", "DO NOT CLEAR"),
            # The header's decoration is the module's usual tolerance.
            (_with_asks(_DNC_CLOSE, _ASK, header="Needs you:"), "RUNNING", "DO NOT CLEAR"),
            (_with_asks(_DNC_CLOSE, _ASK, header="`Needs you:`"), "RUNNING", "DO NOT CLEAR"),
            # The first ask on the header's own line.
            (f"Done.\n\n{_DNC_CLOSE}\n\n**Needs you:** {_ASK}", "RUNNING", "DO NOT CLEAR"),
        ],
        ids=["running-dnc", "your-turn-safe", "no-blank-line", "plain-header",
             "backticked-header", "ask-on-header-line"],
    )
    def test_the_close_before_the_asks_is_read(self, text, disposition, verdict):
        assert standing_block.disposition(text) == disposition
        assert standing_block.clear_verdict(text) == verdict

    def test_the_verdict_line_is_the_close_not_the_asks(self):
        assert standing_block.verdict_line(DNC_ASKS) == _DNC_CLOSE

    @pytest.mark.parametrize(
        "text",
        [
            # No header: the last line is an ask, so there is no close.
            DNC_ASKS_NO_HEADER,
            # Not the exact header.
            _with_asks(_DNC_CLOSE, _ASK, header="## Needs you:"),
            _with_asks(_DNC_CLOSE, _ASK, header="**needs you:**"),
            _with_asks(_DNC_CLOSE, _ASK, header="**Needs you**"),
            _with_asks(_DNC_CLOSE, _ASK, header="**Needs your input:**"),
            _with_asks(_DNC_CLOSE, _ASK, header="Here is what **Needs you:**"),
            # The close is not the line immediately before the header.
            f"Done.\n\n{_DNC_CLOSE}\n\nOne more thing.\n\n**Needs you:**\n1. {_ASK}",
            # The header opens the turn: nothing precedes it.
            f"**Needs you:**\n1. {_ASK}\n\n{_DNC_CLOSE}",
            # Two headers: which block is the asks is ambiguous.
            f"Done.\n\n{_DNC_CLOSE}\n\n**Needs you:**\n1. {_ASK}\n\n**Needs you:**\n2. x",
            # Both verdicts on the close before the block.
            _with_asks("`RUNNING` · `DO NOT CLEAR` — not SAFE TO CLEAR yet.", _ASK),
        ],
        ids=["no-header", "heading-header", "lower-case-header", "no-colon",
             "other-wording", "header-mid-line", "close-not-adjacent", "header-first",
             "two-headers", "both-verdicts"],
    )
    def test_no_verdict_unless_the_close_immediately_precedes_the_header(self, text):
        assert standing_block.clear_verdict(text) is None
        assert standing_block.contradiction(text) is None

    @pytest.mark.parametrize(
        ("text", "verdict"),
        [
            # A close-shaped line as the asks block's last line: under the old
            # reading it was the turn's last line, so it was THE close.
            (_with_asks(_ASK_SAFE_CLOSE, _ASK) + "\n`RUNNING` · `DO NOT CLEAR` — quoted.",
             "SAFE TO CLEAR"),
            # A close-shaped line inside the block with no real close before it.
            (f"Done.\n\n**Needs you:**\n1. {_ASK}\n`RUNNING` · `DO NOT CLEAR` — quoted.", None),
            # The three-paragraph close followed by an asks block whose last
            # paragraph leads with a clear label: the block is not read.
            (_block("RUNNING", "DO NOT CLEAR") + "\n\n**Needs you:**\n1. x\n\n`DO NOT CLEAR` — y.",
             None),
        ],
        ids=["close-shaped-ask-after-a-close", "close-shaped-ask-alone", "legacy-then-asks"],
    )
    def test_a_label_inside_the_asks_block_is_never_the_verdict(self, text, verdict):
        assert standing_block.clear_verdict(text) == verdict
        assert _on_event(
            gates.turn_declares_in_flight, {"last_assistant_message": text}
        ) == (False, None)

    def test_the_three_paragraph_form_is_not_read_across_an_asks_block(self):
        """Every reader skips the older form's block once an asks block is
        present: its region would run into the asks."""
        text = _block("RUNNING", "DO NOT CLEAR") + "\n\n**Needs you:**\n1. x\n\n`DO NOT CLEAR` — y."
        assert standing_block.disposition(text) is None
        assert standing_block.verdict_line(text) == ""
        # Control: without the header, the same block is read.
        bare = _block("RUNNING", "DO NOT CLEAR")
        assert standing_block.disposition(bare) == standing_block.RUNNING

    def test_a_handed_over_dnc_before_the_asks_contradicts(self):
        text = _with_asks("`YOUR TURN` · `DO NOT CLEAR` — I need your decision.", _ASK)
        assert standing_block.contradiction(text) == standing_block.YOUR_TURN

    def test_the_reason_is_the_close_alone(self):
        """An ask that happens to say 'this message' is not the close's
        reason; a reason that cites the turn still is."""
        sound = _with_asks(
            "`YOUR TURN` · `SAFE TO CLEAR` — nothing is running.",
            "The whole plan is in this message: approve it? I recommend yes.",
        )
        assert standing_block.self_citation(sound) is None
        citing = _with_asks(
            "`YOUR TURN` · `SAFE TO CLEAR` — the questions are in this message.", _ASK,
        )
        assert standing_block.self_citation(citing) == "are in this message"

    def test_the_payload_ladder_sees_the_close_through_the_asks(self):
        assert _on_event(
            gates.turn_declares_in_flight, {"last_assistant_message": DNC_ASKS}
        ) == (True, "DO NOT CLEAR")
        assert _on_event(
            gates.turn_declares_in_flight, {"last_assistant_message": DNC_ASKS_NO_HEADER}
        ) == (False, None)


class TestACloseThatPointsByPosition:
    """The close's reason says what the asks are, or nothing — never where.
    The owner's own example closed ``YOUR TURN`` · ``DO NOT CLEAR`` with "The
    one ask above is for you." ``standing_block.positional_pointer_match``
    finds such a reason under ANY disposition and verdict, so the Stop hook can
    record it (``close-pointer``) without refusing it."""

    @pytest.mark.parametrize(
        ("close", "phrase", "kind"),
        [
            ("`YOUR TURN` · `DO NOT CLEAR` — the verify pass runs. The one ask above is for you.",
             "above", "points-above"),
            ("`YOUR TURN` · `SAFE TO CLEAR` — answer the questions above.", "above", "points-above"),
            ("`RUNNING` · `DO NOT CLEAR` — the review runs; see above for the ask.",
             "see above", "points-above"),
            ("`COMPLETE` · `SAFE TO CLEAR` — the summary is above.", "above", "points-above"),
            ("`RUNNING` · `DO NOT CLEAR` — the review runs; the asks below need you.",
             "below", "points-below"),
            ("`YOUR TURN` · `SAFE TO CLEAR` — two decisions below — the plan is in the notes.",
             "below", "points-below"),
            ("`YOUR TURN` · `SAFE TO CLEAR` — see below.", "see below", "points-below"),
            # Both directions: the first pointer in the reason is the one named.
            ("`YOUR TURN` · `SAFE TO CLEAR` — the decision below, not the notes above.",
             "below", "points-below"),
        ],
        ids=["owner-example", "answer-above", "see-above", "complete-above", "asks-below",
             "dash-after", "see-below", "first-of-two"],
    )
    def test_a_positional_reason_is_named(self, close, phrase, kind):
        text = f"Did the work.\n\n{close}"
        assert standing_block.positional_pointer_match(text) == (phrase, kind)
        # The same close before an asks block is read through it.
        assert standing_block.positional_pointer_match(_with_asks(close, _ASK)) == (phrase, kind)

    @pytest.mark.parametrize(
        "text",
        [
            # Comparatives, not positions.
            "Done.\n\n`COMPLETE` · `SAFE TO CLEAR` — coverage is above the floor.",
            "Done.\n\n`RUNNING` · `DO NOT CLEAR` — the suite stays below 5 minutes; I re-check then.",
            "Done.\n\n`COMPLETE` · `SAFE TO CLEAR` — the above-mentioned file is committed.",
            # A sound reason.
            _with_asks(_ASK_SAFE_CLOSE, _ASK),
            # Positional words elsewhere in the turn, not in the close's reason.
            "The asks are above.\n\n`YOUR TURN` · `SAFE TO CLEAR` — one decision on the flag.",
            _with_asks(_ASK_SAFE_CLOSE, "The table above: keep it? I recommend yes."),
            # No close the reader can place: the caller records a firing, so
            # an uncertain reading names nothing.
            "Done.\n\nThe ask above is for you.",
            _with_asks("`RUNNING` · `DO NOT CLEAR` — not SAFE TO CLEAR; the ask above.", _ASK),
            None,
        ],
        ids=["comparative-above", "comparative-below", "hyphenated", "sound-reason",
             "body-text", "inside-asks", "no-close", "both-verdicts", "none"],
    )
    def test_nothing_else_is_named(self, text):
        assert standing_block.positional_pointer_match(text) is None  # type: ignore[arg-type]

    def test_the_kinds_are_every_kind_the_matcher_returns(self):
        assert standing_block.POSITIONAL_POINTER_KINDS == ("points-above", "points-below")

    @pytest.mark.parametrize(
        ("stop_input", "expected"),
        [
            ({"last_assistant_message": _line("YOUR TURN", "DO NOT CLEAR", "the one ask above.")},
             "points-above"),
            ({"last_assistant_message": DNC_LINE}, None),
            ({"last_assistant_message": None}, None),
            ({}, None),
            ("not a dict", None),
        ],
        ids=["pointer", "sound", "null", "empty", "str"],
    )
    def test_the_payload_ladder(self, stop_input, expected):
        match = _on_event(gates.turn_positional_pointer, stop_input)
        assert (match[1] if match else None) == expected


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
    ("the questions are in this message", "are in this message"),
    ("this message holds the whole ask", "this message holds"),
    ("the analysis is above", "is above"),
    ("The plan exists only in this reply, so clearing now would lose it.",
     "exists only in this reply"),
    ("Nothing is in flight. This message has the full recommendation.", "This message has"),
    ("The three SHAs are the only thing worth keeping, and they're in this message.",
     "'re in this message"),
    # A denial in ANOTHER clause does not excuse the citation.
    ("Nothing is running, and the recommendation is all in this message.",
     "is all in this message"),
]
# Sound reasons that use the same words: each must pass. The first four name no
# durable record, so only the patterns' own shape lets them through.
SOUND_REASONS = [
    "Nothing changed in this turn.",
    "nothing was started in this turn.",
    "context is below half.",
    "context stays below the limit.",
    "the decision is in the notes.",
    "nothing lives only in this conversation.",
    "the findings above are in .prawduct/.handoff-notes.md.",
    "no files changed in this turn.",
    "nothing is outstanding.",
    "everything in this reply is also in the handoff notes.",
    "No work is in flight and nothing produced here lives only in this message.",
    "Every finding is saved as a comment on its issue, so none of it exists only in this message.",
    "No open question is in this message.",
    "Nothing this turn has produced needs keeping.",
    "This reply has nothing unsaved.",
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
        assert standing_block.self_citation(text) == "are in this message"

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


def _on_event(gate, payload):
    """Ask ``gate`` as the Stop hook does: the raw payload, garbage included,
    read through the host seam (``host.read_event``) first."""
    return gate(host.read_event("stop", payload))


class TestTurnDeclaresInFlight:
    def test_dnc_turn_defers(self):
        assert _on_event(gates.turn_declares_in_flight, json.loads(_payload(DNC_TURN))) == (
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
        assert _on_event(gates.turn_declares_in_flight, stop_input) == (False, None)

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
        assert _on_event(gates.turn_contradicts_its_verdict, stop_input) == expected

    @pytest.mark.parametrize(
        ("stop_input", "expected"),
        [
            ({"last_assistant_message": _block(
                "YOUR TURN", "SAFE TO CLEAR", "the questions are in this message.")},
             "are in this message"),
            ({"last_assistant_message": ASK_SAFE_TURN}, None),
            ({"last_assistant_message": ASK_DNC_TURN}, None),
            ({"last_assistant_message": None}, None),
            ({}, None),
            ("not a dict", None),
        ],
        ids=["self-citing", "your-turn-safe", "your-turn-dnc", "null", "empty", "str"],
    )
    def test_self_citation_ladder(self, stop_input, expected):
        match = _on_event(gates.turn_self_citation, stop_input)
        assert (match[0] if match else None) == expected

    def test_transcript_is_not_a_fallback(self, tmp_path):
        """With the field absent, a transcript that DOES close on DO NOT CLEAR is
        not read: an older client behaves exactly as before the signal existed."""
        transcript = tmp_path / "t.jsonl"
        transcript.write_text(json.dumps({
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": DNC_TURN}]},
        }) + "\n")
        assert _on_event(gates.turn_declares_in_flight, {"transcript_path": str(transcript)}) == (
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

    def test_a_one_line_dnc_close_defers_both_gates(self, tmp_path):
        """The close the digest now prescribes: one line, last."""
        _plan_repo(tmp_path, reflected=False)
        result = run_plugin_hook(
            "stop", tmp_path, git_status=_CODE_DIFF, stdin=_payload(DNC_LINE)
        )
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert "says RUNNING and closed on DO NOT CLEAR" in result.stderr
        assert "gate: reflection" in result.stderr
        assert "gate: critic-review" in result.stderr

    def test_a_one_line_safe_close_defers_nothing(self, tmp_path):
        """Control for the test above: the same fixture blocks on SAFE TO CLEAR."""
        _plan_repo(tmp_path, reflected=False)
        result = run_plugin_hook(
            "stop", tmp_path, git_status=_CODE_DIFF, stdin=_payload(SAFE_LINE)
        )
        assert result.returncode == 2, (result.stdout, result.stderr)
        assert "GATES DEFERRED" not in result.stderr

    def test_asks_after_a_dnc_close_still_defer_both_gates(self, tmp_path):
        """The asks come last now; the close above them still defers."""
        _plan_repo(tmp_path, reflected=False)
        result = run_plugin_hook(
            "stop", tmp_path, git_status=_CODE_DIFF, stdin=_payload(DNC_ASKS)
        )
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert "says RUNNING and closed on DO NOT CLEAR" in result.stderr
        assert "gate: reflection" in result.stderr
        assert "gate: critic-review" in result.stderr

    def test_the_same_asks_without_the_header_defer_nothing(self, tmp_path):
        """Control for the test above: only the header opens the asks block."""
        _plan_repo(tmp_path, reflected=False)
        result = run_plugin_hook(
            "stop", tmp_path, git_status=_CODE_DIFF, stdin=_payload(DNC_ASKS_NO_HEADER)
        )
        assert result.returncode == 2, (result.stdout, result.stderr)
        assert "GATES DEFERRED" not in result.stderr

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

    @pytest.mark.non_root
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
        """The verdict defers the session-end gates ONLY. An unmigrated legacy
        learnings corpus still blocks, and the Critic blocker that deferred is
        named rather than hidden, and is not in the BLOCKED report. (This used
        the `Type: trivial` file-set gate until #301 retired it.)"""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
        (prawduct / "learnings.md").write_text("# L\n\n## a rule\n")
        (prawduct / ".session-reflected").write_text(SHAPED_REFLECTION)
        (prawduct / ".session-git-baseline").write_text("")
        _make_session_start(prawduct)
        result = run_plugin_hook(
            "stop", tmp_path, git_status=_CODE_DIFF, stdin=_payload(DNC_TURN)
        )
        assert result.returncode == 2, (result.stdout, result.stderr)
        blocked = _blocked_section(result.stderr)
        assert "LEARNINGS UNMIGRATED" in blocked
        assert "gate: critic-review" not in blocked
        assert "GATES DEFERRED" in result.stderr
        assert "deferred: [prawduct" in result.stderr


class TestClearVerdictGate:
    """A turn that hands the session over while saying DO NOT CLEAR is recorded
    but not refused (#1044). These run the hook against a
    mock git, which has no evidence store, so what each firing RECORDS is
    pinned in-process in `test_stop_block_facts.py`; here, only that nothing
    blocks. The same holds for the clear-reason check below (#1131)."""

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
    def test_does_not_block_on_a_clean_tree(self, tmp_path, message, label):
        """No changes, so no other gate fires: the contradiction alone used to
        block; now the Stop passes."""
        self._quiet_repo(tmp_path)
        result = run_plugin_hook("stop", tmp_path, git_status="", stdin=_payload(message))
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert "CLEAR VERDICT" not in result.stderr
        assert "clear-verdict" not in result.stderr

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
        assert "gate: clear-verdict" not in blocked
        assert "gate: critic-review" in blocked
        assert "gate: reflection" in blocked
        assert "GATES DEFERRED" not in result.stderr

    def test_background_work_defers_the_gates_and_the_contradiction_blocks_nothing(self, tmp_path):
        """In-flight work defers every session-end blocker, and the
        contradiction no longer blocks in their place."""
        _plan_repo(tmp_path, reflected=True)
        stdin = _payload(
            COMPLETE_DNC_TURN,
            background_tasks=[{"id": "t-1", "type": "subagent", "agent_type": "Explore"}],
        )
        result = run_plugin_hook("stop", tmp_path, git_status=_CODE_DIFF, stdin=stdin)
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert "GATES DEFERRED" in result.stderr
        assert "CLEAR VERDICT" not in result.stderr

    def test_your_turn_beside_observed_background_work_stands(self, tmp_path):
        """The hold is true while work a clear would kill runs, and the ask is
        the reader's either way: `YOUR TURN` + `DO NOT CLEAR` is not refused."""
        self._quiet_repo(tmp_path)
        stdin = _payload(
            ASK_DNC_TURN,
            background_tasks=[{"id": "t-1", "type": "subagent", "agent_type": "Explore"}],
        )
        result = run_plugin_hook("stop", tmp_path, git_status="", stdin=stdin)
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert "CLEAR VERDICT" not in result.stderr

    def test_your_turn_beside_a_live_review_stands(self, tmp_path):
        from lib import critic_marker

        self._quiet_repo(tmp_path)
        assert critic_marker.write_marker(tmp_path / ".prawduct")
        result = run_plugin_hook("stop", tmp_path, git_status="", stdin=_payload(ASK_DNC_TURN))
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert "CLEAR VERDICT" not in result.stderr


    @pytest.mark.parametrize(
        "message",
        [
            *(_block("YOUR TURN", "SAFE TO CLEAR", r) for r, _ in SELF_CITING_REASONS[:3]),
            _line("YOUR TURN", "SAFE TO CLEAR", "the questions are in this message."),
        ],
        ids=["in-this-message", "message-holds", "above-below", "one-line"],
    )
    def test_a_self_citing_safe_to_clear_does_not_block(self, tmp_path, message):
        """The trial's phrasings: no other gate fires, and the reason alone used
        to block. It is recorded instead (pinned in `test_stop_block_facts.py`),
        and the hook prints nothing about it on a Stop that passes."""
        self._quiet_repo(tmp_path)
        assert standing_block.self_citation(message), "fixture must self-cite"
        result = run_plugin_hook("stop", tmp_path, git_status="", stdin=_payload(message))
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert "clear-reason" not in result.stderr
        assert "CLEAR VERDICT" not in result.stderr

    def test_a_self_citation_does_not_keep_a_deferred_stop_blocked(self, tmp_path):
        """Background work defers every session-end blocker, and the
        self-citation no longer blocks in their place."""
        _plan_repo(tmp_path, reflected=True)
        stdin = _payload(
            _block("YOUR TURN", "SAFE TO CLEAR", "the questions are in this message."),
            background_tasks=[{"id": "t-1", "type": "subagent", "agent_type": "Explore"}],
        )
        result = run_plugin_hook("stop", tmp_path, git_status=_CODE_DIFF, stdin=stdin)
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert "GATES DEFERRED" in result.stderr
        assert "clear-reason" not in _blocked_section(result.stderr)

    def test_neither_clear_check_has_a_registry_row(self):
        """The registry lists gates that BLOCK; both clear checks observe."""
        registry = json.loads((PLUGIN / "hooks" / "gates.json").read_text())
        ids = {g["id"] for g in registry["gates"]}
        assert ids, "the registry read came back empty"
        assert "reflection" in ids  # control: a blocking gate is listed
        assert "clear-reason" not in ids
        assert "clear-verdict" not in ids


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
    teach the close must name exactly that set — no label missing, none extra —
    so a rename in either place fails here instead of drifting."""

    def test_session_hygiene_section_states_exactly_the_vocabulary(self):
        text = (_METHODOLOGY / "session-hygiene.md").read_text(encoding="utf-8")
        section = _section(text, "## The closing line")
        assert set(_LABEL_TOKEN.findall(section)) == set(standing_block.ALL_LABELS)

    def test_each_fenced_example_is_a_close_the_reader_reads(self):
        """The guide's examples are what agents copy, so each must parse to
        the disposition and verdict it shows — a separator the reader does not
        accept would teach a close the Stop hook cannot see."""
        text = (_METHODOLOGY / "session-hygiene.md").read_text(encoding="utf-8")
        fences = re.findall(r"```\n(.*?)```", _section(text, "## The closing line"), re.S)
        assert len(fences) == 2, fences
        assert standing_block.disposition(fences[0]) == standing_block.RUNNING
        assert standing_block.clear_verdict(fences[0]) == standing_block.DO_NOT_CLEAR
        assert standing_block.disposition(fences[1]) == standing_block.YOUR_TURN
        assert standing_block.clear_verdict(fences[1]) == standing_block.SAFE_TO_CLEAR
        # The hand-over example opens on the line and ENDS with its asks,
        # numbered, under the header — the asks are the last thing it shows.
        lines = [line for line in fences[1].splitlines() if line.strip()]
        assert lines[0] == standing_block.verdict_line(fences[1])
        assert lines[1] == standing_block.ASKS_HEADER
        assert [line[:3] for line in lines[2:]] == ["1. ", "2. "]
        assert standing_block.self_citation(fences[1]) is None

    @pytest.mark.parametrize(
        ("guide", "heading"),
        [("session-hygiene.md", "## The closing line"),
         ("session-digest.md", "## Closing the turn")],
    )
    def test_each_carrier_names_exactly_the_asks_header(self, guide, heading):
        """Both directions: the prose names the constant, and every bold
        "Needs ...:" header the prose names is the constant — so a header
        renamed in the code or in either carrier fails here."""
        section = _section((_METHODOLOGY / guide).read_text(encoding="utf-8"), heading)
        named = set(re.findall(r"\*\*Needs[^*\n]*\*\*", section))
        assert named == {standing_block.ASKS_HEADER}, named

    def test_digest_closing_section_states_exactly_the_vocabulary(self):
        text = (_METHODOLOGY / "session-digest.md").read_text(encoding="utf-8")
        section = _section(text, "## Closing the turn")
        assert set(_LABEL_TOKEN.findall(section)) == set(standing_block.ALL_LABELS)

    def test_the_guide_names_every_close_check_the_hook_records(self):
        """The Stop-hook paragraph lists the checks that record a close without
        refusing it; the pointer check is one of them."""
        text = (_METHODOLOGY / "session-hygiene.md").read_text(encoding="utf-8")
        para = text[text.index("**The Stop hook reads this verdict.**"):]
        para = para[: para.index("\n")]
        for check in ("`clear-verdict`", "`clear-reason`", "`close-pointer`"):
            assert check in para, check

    def test_the_tuples_partition_the_vocabulary(self):
        # `STATE` led the three-paragraph close's first paragraph. No reader
        # keys on it, so it left the vocabulary with the paragraph (#1131).
        assert standing_block.ALL_LABELS == (
            *standing_block.DISPOSITION_LABELS,
            *standing_block.CLEAR_LABELS,
        )
        assert len(set(standing_block.ALL_LABELS)) == len(standing_block.ALL_LABELS)


# ---------------------------------------------------------------------------
# How a blocked turn is told to answer (#1095)
# ---------------------------------------------------------------------------

_HEADING = "BLOCKED — resolve before ending session:"


def _answer_line(stderr: str) -> str:
    """The line right after the block heading — where every block says how to
    answer it, ahead of the items."""
    assert stderr.count(_HEADING) == 1, stderr
    return stderr.split(_HEADING, 1)[1].lstrip("\n").splitlines()[0]


def assert_block_says_how_to_answer(stderr: str) -> None:
    """A blocked turn's answer and close are already written: the block asks
    for only what is missing, and says when the close is written again — only
    when the turn must now close `RUNNING` · `DO NOT CLEAR`, because the
    deferral reads the close from the last message only (keeping a deferral,
    or having just started work a clear would kill). No gate faults the close
    itself since `clear-reason` stopped blocking, so the block no longer says
    one might."""
    line = _answer_line(stderr)
    assert "Do not repeat your answer" in line, line
    assert (
        "Write the closing line again only if you must now close `RUNNING` · `DO NOT CLEAR` "
        "(to keep a deferral, or because what you just started"
    ) in line, line
    assert "an item faults it" not in line, line
    # The one exception to not repeating (owner-confirmed 2026-11-11,
    # asks-last): a turn that ended with its asks ends with them again, so the
    # asks stay the last thing the user sees after the block.
    assert_the_asks_are_restated(line)


def assert_the_asks_are_restated(text: str) -> None:
    """``text`` tells a blocked turn to end with its asks block again, under
    the header the reader reads past, unchanged and after any close."""
    flat = " ".join(text.split())
    assert standing_block.ASKS_HEADER in flat, flat
    clause = flat[flat.index(standing_block.ASKS_HEADER):]
    assert "again, unchanged" in clause, clause


class TestABlockSaysHowToAnswerIt:
    def test_the_guide_says_the_same_as_the_hook(self):
        """The rule has two carriers — the hook's answer line and the guide's
        "Answering a block" sentence — so both are read here: a rule reworded
        in one is two rules."""
        text = (_METHODOLOGY / "session-hygiene.md").read_text(encoding="utf-8")
        sentence = text[text.index("**Answering a block:**"):]
        sentence = sentence[: sentence.index("\n")]
        assert_the_asks_are_restated(sentence)
        assert "before the asks" in sentence, sentence

    def test_a_gate_block_says_it_before_the_items(self, tmp_path):
        _plan_repo(tmp_path, reflected=True)
        result = run_plugin_hook("stop", tmp_path, git_status=_CODE_DIFF, stdin=_payload(SAFE_TURN))
        assert result.returncode == 2, (result.stdout, result.stderr)
        assert_block_says_how_to_answer(result.stderr)
        blocked = _blocked_section(result.stderr)
        assert blocked.index("Do not repeat your answer") < blocked.index("CRITIC")

    def test_a_turn_that_does_not_block_is_not_told(self, tmp_path):
        """Control: the deferred Stop exits 0 and prints no block, so no answer line."""
        _plan_repo(tmp_path, reflected=True)
        result = run_plugin_hook("stop", tmp_path, git_status=_CODE_DIFF, stdin=_payload(DNC_TURN))
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert "Do not repeat your answer" not in result.stderr + result.stdout
