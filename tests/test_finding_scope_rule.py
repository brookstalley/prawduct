"""Every Critic mode that can raise a finding reaches the instance-or-class rule.

The rule — a site-naming finding says whether the defect is only where it
pointed or everywhere that pattern appears — shipped stated in exactly one
place, `review-protocol.md` § Severity Levels. `final` and `cumulative` load
that file. `chunk` and `verify-resolutions` load `goals-1-3.md` and are
forbidden to open the protocol, so for those two the rule did not exist, and
the release notes claimed it did.

That gap is not visible from either carrier: `review-protocol.md` states the
rule correctly and always did, and `goals-1-3.md` reads as complete because a
payload's job is to be self-contained. Only the MAP — which mode loads which
carrier — shows the hole, which is why the map is what this file pins.

**These are a construction, not an enumeration**, which is the rule applied to
itself. A test naming today's two carriers is a longer list of names: it passes
unchanged when a fifth mode is added, or when a payload is split again, and
both of those are how the gap arrived the first time. So the mode set is read
from `MODE_TOKEN_TO_VERBOSE` — the dict that defines what a mode IS — and every
member must be accounted for by one carrier or the other. A new mode fails here
until someone says which carrier serves it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"
sys.path.insert(0, str(ROOT))
from lib import critic_consolidate as cc  # noqa: E402

PROTOCOL = ROOT / "skills" / "critic" / "review-protocol.md"

#: The two carriers, and the only two. A mode reaches the rule through the
#: payload file it loads, or through the directive code hands it at dispatch.
PROTOCOL_TEXT = PROTOCOL.read_text(encoding="utf-8")
DIRECTIVE = cc.FINDING_SCOPE_DIRECTIVE


def _carrier_for(mode_token: str) -> str:
    """Which text a reviewer in ``mode_token`` actually meets the rule in.

    Deliberately total: an unknown mode raises rather than defaulting, because
    a mode silently defaulting to "the protocol carries it" is exactly the
    failure this file exists to catch — that is what `verify-resolutions` did.
    """
    if mode_token in cc.GOALS_1_3_MODES:
        return DIRECTIVE
    return PROTOCOL_TEXT


def test_every_mode_is_accounted_for() -> None:
    """The partition is total. No mode falls outside both carriers."""
    unaccounted = {
        token
        for token in cc.MODE_TOKEN_TO_VERBOSE
        if token not in cc.GOALS_1_3_MODES and token not in {"final", "cumulative"}
    }
    assert not unaccounted, (
        f"mode(s) {sorted(unaccounted)} are neither in GOALS_1_3_MODES nor known "
        "to load review-protocol.md, so nothing here checks that their reviewer "
        "ever meets the instance-or-class rule. Say which carrier serves them."
    )


@pytest.mark.parametrize("mode_token", sorted(cc.MODE_TOKEN_TO_VERBOSE))
def test_the_mode_reaches_the_rule(mode_token: str) -> None:
    carrier = _carrier_for(mode_token)
    assert "`instance`" in carrier and "`class`" in carrier, (
        f"a reviewer in `{mode_token}` mode never meets the instance-or-class "
        "rule. Its findings go back to naming two files when the defect is in "
        "six, which costs a full extra fix round every time."
    )


@pytest.mark.parametrize("mode_token", sorted(cc.MODE_TOKEN_TO_VERBOSE))
def test_the_mode_reaches_the_test_that_decides_it(mode_token: str) -> None:
    # The label without its decision procedure is a field to fill in, not a
    # rule: the whole mechanism is that the one-sentence reason is what tells
    # you which answer is right, and it is mechanical rather than a judgement
    # call precisely because the sentence either names your site or does not.
    carrier = _carrier_for(mode_token)
    assert "one sentence" in carrier, (
        f"`{mode_token}`'s carrier states instance-vs-class without the "
        "one-sentence test that decides it — the label becomes a guess."
    )


@pytest.mark.parametrize("mode_token", sorted(cc.MODE_TOKEN_TO_VERBOSE))
def test_the_mode_reaches_the_withholding(mode_token: str) -> None:
    # The half with teeth, and the half a trim reaches for first because it
    # reads as elaboration. Without it a class finding closes by listing more
    # addresses, which is the resolution the rule exists to refuse — and the
    # next member to be written is on nobody's list.
    carrier = _carrier_for(mode_token)
    assert "construction" in carrier.lower(), (
        f"`{mode_token}`'s carrier no longer says an unbounded class closes "
        "only by a construction, so a longer list of names reads as a fix."
    )


@pytest.mark.parametrize("mode_token", sorted(cc.MODE_TOKEN_TO_VERBOSE))
def test_the_mode_reaches_the_no_defect_answer(mode_token: str) -> None:
    # The mandated cross-checks (priors, learnings, backlog reconciliation)
    # must report even when clean, so they raise notes bounding no defect at
    # all. Without a third answer their reviewers invent one — three findings
    # in one observed review already had — and an invented vocabulary is how a
    # rule with teeth acquires an escape hatch nobody ruled on.
    carrier = _carrier_for(mode_token)
    assert "`none`" in carrier, (
        f"`{mode_token}`'s carrier offers no answer for a mandated cross-check "
        "carrying no defect, so its reviewers will coin one."
    )


def test_the_directive_is_delivered_at_dispatch() -> None:
    """Existing is not reaching. The directive is only worth anything if the
    dispatch command prints it, and prints it for the modes whose payload
    cannot carry the rule.

    Asserted against the module the way its two siblings are: `critic-begin` is
    the one moment code speaks to the reviewer before it writes a finding.
    """
    begin_src = HOOK.read_text(encoding="utf-8")
    assert "FINDING_SCOPE_DIRECTIVE" in begin_src, (
        "the dispatch command no longer emits the finding-scope directive, so "
        "the modes that read goals-1-3.md meet the rule nowhere at all"
    )
    assert "GOALS_1_3_MODES" in begin_src, (
        "the emission no longer selects its modes from GOALS_1_3_MODES. Spelled "
        "at the call site instead, the set that reads goals-1-3.md and the set "
        "that gets handed the rule can drift apart silently — which is the "
        "shape of the defect this directive was written to close."
    )


def test_the_directive_has_a_size_ceiling() -> None:
    """Pinned for the reason its two siblings are, and pinned now because this
    is the edit that created it.

    It is delivered on every `chunk` dispatch — the mode with the tightest
    wall-clock target in the system — so it competes with the review it is
    trying to improve. Two numbers, two jobs: the pin fails on any drift and
    carries the new figure; the ceiling says how much drift is allowed before a
    clause has to move out.
    """
    tokens = int(len(DIRECTIVE.split()) * 1.3)
    assert tokens == 148, (
        f"FINDING_SCOPE_DIRECTIVE is ~{tokens} tokens; this pin says 148. "
        f"Update it to {tokens} and say in the docstring what paid for the "
        "change — the ceiling below is not a budget to spend."
    )
    assert tokens < 200, (
        f"the directive is ~{tokens} tokens. It rides every chunk dispatch, "
        "which targets 1-2 minutes end to end. Trim, or move a clause to the "
        "file that owns it."
    )
