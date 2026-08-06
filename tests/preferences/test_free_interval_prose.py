"""The prose surfaces must not teach the review treadmill they now prevent.

`critic-begin` refuses a review the coverage gate would not require (exit 3,
"no review needed") — measured 2026-08-06 at 62 of 492 recorded reviews, 12.6%,
~5.2 opus-hours of reviewer time spent on intervals that were free the whole
time. The mechanism is only half the fix. The other half is that the surfaces a
builder reads *at the moment they decide whether to spend a round* stop telling
them to spend one unconditionally, and start telling them the cheaper truth:
**asking is free, so ask instead of reasoning.**

Prose is the load-bearing part here, not decoration. Skill and methodology files
in this framework are behavioral logic executed by a model — which is why
`is_judgeable_path` classifies them as judgeable code — and the measured waste
was produced by builders following exactly these instructions correctly.

**Structural, not a content audit** (same posture as
`test_critic_skill_structure.py`): each surface must *carry the qualifier*, and
must not carry the specific unconditional phrasing that predates the guard. It
does not check that the surrounding explanation is good — that is the Critic's
job (Goal 4: Coherence).

**Why `methodology/building.md` is deliberately NOT in `_SURFACES`.** Its
"Resolve findings" paragraph is the fifth carrier a builder reads, and it says
"every fix in ONE commit, then ONE `/prawduct:critic verify-resolutions`" — which
is *correct unchanged* under this design: running it and letting the exit code
answer is exactly the desired behaviour, and the guard makes that instruction
cheaper rather than wrong. Adding the qualifier there would spend that file's
token budget restating a mechanism the command itself now enforces, on the one
surface whose job is the shape of the cycle rather than the cost of a round.
Recorded here because the omission is a judgement, not an oversight (cumulative
`rev-20260806T215117Z-31201027`, R-15).
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PLUGIN = REPO_ROOT / "plugin"

#: Every surface that tells a builder whether to spend a review round, with the
#: token proving it carries the free-interval answer. `exit 3` / `exits 3` is
#: the load-bearing token: it names the observable outcome, so a rewrite that
#: keeps the advice but drops the mechanism still fails here.
_SURFACES = [
    pytest.param(
        PLUGIN / "skills" / "pr" / "SKILL.md",
        ("exit 3",),
        id="pr-skill-step-2-sequencing",
    ),
    pytest.param(
        PLUGIN / "skills" / "critic" / "review-cycle.md",
        ("exits 3", "no review needed"),
        id="review-cycle-close-coverage",
    ),
    pytest.param(
        PLUGIN / "skills" / "critic" / "SKILL.md",
        ("Exit 3", "--force"),
        id="critic-skill-dispatch",
    ),
    pytest.param(
        PLUGIN / "lib" / "critic_consolidate.py",
        ("exits 3",),
        id="next-action-text",
    ),
]


@pytest.mark.parametrize(("path", "tokens"), _SURFACES)
def test_the_surface_names_the_free_interval_answer(path: Path, tokens):
    assert path.is_file(), f"{path} moved — this test's subject no longer exists"
    text = path.read_text()
    missing = [t for t in tokens if t not in text]
    assert not missing, (
        f"{path.relative_to(REPO_ROOT)} decides whether a review round is spent "
        f"but never tells the reader the dispatcher answers that for free "
        f"(missing: {missing}). A builder reading it will reason about "
        f"judgeability, or spend the round to be safe — which is the measured "
        f"waste the guard exists to end."
    )


def test_the_next_action_text_does_not_prescribe_an_unconditional_round():
    """The clean-review arms must keep their condition.

    `_next_action` has three arms. The BLOCKING arm's "then run ONE
    verify-resolutions" is CORRECT and deliberately untouched: a blocking
    finding is cleared only by the resolution facts a verify pass records, which
    is exactly why the refusal predicate's second conjunct exists — refusing
    that pass would wedge the gate with no command that clears it.

    The 0-blocking arms are the ones that must stay conditional. This asserts
    the condition survives, phrased against the two tokens that carry it.
    """
    text = (PLUGIN / "lib" / "critic_consolidate.py").read_text()
    assert "ONLY if that commit touched judgeable files" in text, (
        "the 0-blocking arm lost its condition — it now prescribes a "
        "re-cover round regardless of whether the commit moved any coverage"
    )
    assert "cost-of-commit" in text, (
        "the 0-blocking arm no longer names the pre-commit price check"
    )
