"""The prose severity ceiling and its three remedies, pinned on all three surfaces.

Comment and doc wording was the largest single category of finding volume, and no
protocol constrained the *remedy*, so "reword the narration" was a legal
recommendation — which produced the next round's stale narration. The answer is
one policy: prose is NOTE unless load-bearing, and stale prose gets deleted, made
relational, or pinned with a test. Nothing else. (The measurement that motivated
this is in the change-log entry, where a figure is the record rather than a claim
that goes stale here.)

It is stated three times because the three surfaces have disjoint audiences —
`goals-1-3.md` is chunk mode's payload, `review-protocol.md` is what a
final/cumulative reviewer loads, and the PR reviewer reads neither. A pointer
across files would not be read by the reviewer who needs it.

That is also why these are pins rather than prose. All three files carry token
ceilings and stand under permanent pressure to be trimmed; this policy is the
newest and longest thing in each, so it is what the next editor looking for a
hundred tokens will find first. Trimming it out of one file leaves the other two
still saying it, which is the silent failure — the reviewers who lost it go on
rating wording WARNING and manufacturing the rounds this exists to stop.

The policy's own second remedy says the way to keep a claim true is to pin it
with a test. These are that pin, applied to the rule itself.
"""

from __future__ import annotations

from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parent.parent / "plugin"

SEVERITY_SURFACES = [
    PLUGIN / "skills/critic/goals-1-3.md",
    PLUGIN / "skills/critic/review-protocol.md",
    PLUGIN / "skills/pr/review-protocol.md",
]
SURFACE_IDS = ["goals_1_3", "critic_protocol", "pr_protocol"]


@pytest.mark.parametrize("path", SEVERITY_SURFACES, ids=SURFACE_IDS)
def test_the_ceiling_is_stated(path: Path) -> None:
    content = path.read_text()
    assert "**Prose is NOTE unless load-bearing**" in content, (
        f"{path.name} no longer states the prose severity ceiling. Its reviewers "
        "go back to rating comment and doc wording WARNING, which turns each one "
        "into a fix commit — the round-manufacturing loop this rule closed."
    )


@pytest.mark.parametrize("path", SEVERITY_SURFACES, ids=SURFACE_IDS)
def test_the_ceiling_names_what_lifts_it(path: Path) -> None:
    # A ceiling with no exit is a gag rule: the load-bearing cases are exactly
    # where prose findings earn their round, so the two ways out have to travel
    # with the ceiling rather than being inferable from it.
    content = path.read_text()
    assert "a test or a gate reads it" in content, (
        f"{path.name} states the prose ceiling without the read-by-a-test-or-gate "
        "exit — load-bearing prose stops being escalatable."
    )
    assert "concrete wrong action" in content, (
        f"{path.name} states the prose ceiling without the named-consequence exit "
        "— the existing WARNING bar is what lifts the ceiling, and it must be "
        "stated with it, not left to be inferred from the WARNING bullet."
    )


@pytest.mark.parametrize("path", SEVERITY_SURFACES, ids=SURFACE_IDS)
def test_the_ceiling_has_a_floor(path: Path) -> None:
    # The highest-stakes clause here. A ceiling stated with only an upward exit
    # reads as outranking
    # every other severity assignment: Goal 4 rates an actively misleading README
    # instruction BLOCKING, and a reviewer who names that wrong action lands on
    # WARNING instead — which gates nothing, so the wrong command ships. The
    # clause is what keeps a rule that exists to SUPPRESS findings from also
    # suppressing the ones another rule already promoted.
    content = path.read_text()
    assert "never lowers a severity another rule assigns explicitly" in content, (
        f"{path.name} states the prose ceiling with no floor. It now silently "
        "outranks every explicit severity in the file — including BLOCKING ones "
        "— so a finding another rule promoted comes back down to a NOTE or a "
        "WARNING and stops gating anything."
    )


@pytest.mark.parametrize("path", SEVERITY_SURFACES, ids=SURFACE_IDS)
def test_the_three_remedies_are_stated_and_closed(path: Path) -> None:
    # The remedy list is closed, not illustrative. Losing the prohibition while
    # keeping the list is the drift that matters: rewording stays *available*,
    # and it is the move that ships the next round's stale sentence.
    content = path.read_text()
    for remedy in ("delete the claim", "make it relational", "pin it with a test"):
        assert remedy in content, (
            f"{path.name} no longer offers `{remedy}` as a permitted remedy for "
            "stale prose — the three are the whole list, and dropping one narrows "
            "it toward the rewrite this policy exists to forbid."
        )
    assert "Never recommend rewording the narration" in content, (
        f"{path.name} lists the remedies but no longer forbids rewording the "
        "narration. The list stops being closed, and 'update the wording' — the "
        "recommendation that produces the next round's finding — is legal again."
    )


@pytest.mark.parametrize("path", SEVERITY_SURFACES, ids=SURFACE_IDS)
def test_shipped_comments_carry_no_review_history(path: Path) -> None:
    # Review pressure teaches agents to narrate fixes into comments, and the ids
    # they narrate dangle. The remedy is deletion rather than a rewrite, which is
    # the part that has to be explicit: a reviewer who only knows the id is stale
    # recommends correcting it, and the corrected id goes stale too.
    content = path.read_text()
    assert "never belong in a shipped comment" in content, (
        f"{path.name} no longer bans review/finding ids and review history from "
        "shipped comments — the archaeology this pass measured comes straight back."
    )
    assert "**deletion** finding" in content, (
        f"{path.name} bans comment archaeology without naming deletion as the "
        "remedy, which leaves 'fix the stale id' available — a rewrite that goes "
        "stale again on the next renumbering."
    )
