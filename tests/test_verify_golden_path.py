"""The batch-fix golden path, pinned where agents act rather than where it is taught.

The discipline itself is not new — `methodology/building.md` and `critic-consolidate`
both say fix everything in one pass and verify once. What produced the observed
verify loops is that neither surface is loaded at the moment of the decision: the
agent is reading a gate's stderr, or a verify pass's observations, or the PR update
step. So the rule is restated at each of those three points of action, and pinned
here because a restated rule is exactly what a later trim deletes as redundant.

The gate's own remedy string is pinned next to the function that builds it
(`test_cumulative_gate.TestBlockingRemedyLines`). This module covers the two prose
surfaces, neither of which had a pin before.
"""

from __future__ import annotations

from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent / "plugin"

GOALS_1_3 = PLUGIN / "skills/critic/goals-1-3.md"
PR_SKILL = PLUGIN / "skills/pr/SKILL.md"


def flowed(path: Path) -> str:
    """The file with every run of whitespace collapsed to one space.

    These files are hard-wrapped, so a phrase pinned as written breaks the
    moment a reflow moves a word across a line boundary — a failure that says
    nothing about whether the rule survived. Matching the flowed text asks the
    question the pin is for: is the sentence still there?
    """
    return " ".join(path.read_text().split())


class TestVerifyObservationsArePrePriced:
    """A verify pass's observations arrive AFTER the builder has decided to fix
    them — the deciding happens while reading the report. Pricing them in the
    report is the only placement that reaches that decision: an observation with
    no price on it reads as a small free improvement, and fixing one re-opens the
    gate for the next round's observations to do the same thing again."""

    def test_the_default_disposition_travels_with_the_observations(self) -> None:
        content = flowed(GOALS_1_3)
        assert "**Deliver every observation pre-priced:**" in content, (
            "goals-1-3.md no longer prices verify-mode observations. They go back "
            "to arriving as unpriced suggestions, which is what turns one clean "
            "verify pass into the next one."
        )
        # Renegotiated: an observation is owed no disposition, so the price
        # says so rather than naming ACCEPT as the default answer to give.
        assert "it needs no disposition" in content

    def test_the_price_is_named_as_a_round(self) -> None:
        # "Consider whether it is worth it" is not a price. The cost has to be
        # the concrete thing the builder is about to spend.
        content = flowed(GOALS_1_3)
        assert "re-opens the gate and costs a round" in content

    def test_survivors_are_routed_into_an_existing_commit(self) -> None:
        # Without the batching half, the rule reads as "never fix these", which
        # is wrong and will be ignored the first time an observation is worth
        # fixing. The out is to carry it, not to spend a round on it.
        content = flowed(GOALS_1_3)
        assert "rides an already-planned commit" in content


class TestPrUpdateDecidesNothingByEye:
    """`If substantive changes` was once the whole test, so "substantive" was
    decided by eye — and a delta of records plus a base sync reads as changes.
    The answer was a command per shape (`cost-of-commit` over the delta since
    the PR reviewer's `commit_reviewed`). With the reviewer retired (#1129) the
    question is the coverage gate's own: it composes over trees at HEAD, passes
    a delta that needs no review and names what one that does needs. So the
    Update flow runs it, and the hygiene check, on every update — and the
    property survives: nothing there is judged by eye."""

    def _step_2(self) -> str:
        update = flowed(PR_SKILL).split("## Update Flow", 1)[1].split(" ## ", 1)[0]
        return update.split(" 2. ", 1)[1].split(" 3. ", 1)[0]

    def test_every_update_reruns_both_gates(self) -> None:
        step = self._step_2()
        assert "prawduct-hook check-cumulative-critic" in step
        assert "prawduct-hook check-pr-hygiene" in step
        assert "on every update" in step, (
            "the Update flow runs its gates on a condition again — a condition is "
            "a call someone makes by eye"
        )

    def test_the_gate_not_the_reader_decides_what_needed_review(self) -> None:
        step = self._step_2()
        assert "nothing here is judged by eye" in step
        # The free shapes are named, so a reader does not skip the run on a
        # guess about which delta is free.
        for shape in ("`.prawduct/` records", "non-governance `.md`", "base sync"):
            assert shape in step, shape

    def test_the_retired_delta_pricing_is_gone(self) -> None:
        """The cheap reading of `cost-of-commit` (a bare call prices the clean
        working tree and reads as free) was the fail-open the old step guarded.
        The step no longer prices anything, so the instrument must not be named
        as if it still did."""
        content = flowed(PR_SKILL)
        assert "cost-of-commit" not in content
        assert "commit_reviewed" not in content
