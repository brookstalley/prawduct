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
        assert "ACCEPT is the default disposition" in content

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
        assert "batch any survivor into an already-planned commit" in content


class TestPrUpdateDefinesSubstantive:
    """`If substantive changes` was the whole test, so "substantive" was decided
    by eye — and a delta of records plus a base sync reads as changes. Both
    non-substantive shapes get a command that answers instead."""

    def test_substantive_is_defined_by_judgeability(self) -> None:
        # "authored on this branch" is load-bearing, not decoration: a base-sync
        # merge's diff DOES contain judgeable paths, so without it the definition
        # contradicts the second bullet it introduces.
        content = flowed(PR_SKILL)
        assert "at least one **judgeable path authored on this branch**" in content, (
            "the PR Update flow no longer defines substantive, so the reviewer "
            "re-runs on whatever the agent's judgement calls a change."
        )

    def test_neither_case_is_decided_by_eye(self) -> None:
        content = flowed(PR_SKILL)
        assert "neither is judged by eye" in content
        # One command per shape, or the definition is unactionable.
        assert "cost-of-commit" in content
        assert "check-cumulative-critic" in content

    def test_the_cheap_reading_of_cost_of_commit_is_ruled_out(self) -> None:
        """The fail-open this step invites. `cost-of-commit` with no arguments —
        or with a directory — prices the WORKING tree, and by this step the
        working tree is clean because the delta is already committed. It then
        returns an empty `judgeable` list having read none of the delta, and an
        agent testing only for that emptiness skips the independent reviewer
        entirely. So the paths must be passed explicitly, and an empty priced
        set must read as substantive rather than as free."""
        content = flowed(PR_SKILL)
        assert "git diff --name-only" in content, "no way to obtain the delta's paths"
        assert "**explicit file arguments**" in content
        assert "`paths` non-empty **and** `judgeable` empty" in content
        assert "unknown is never free" in content

    def test_the_content_equivalence_limit_is_stated(self) -> None:
        """The honest half. A comment-only edit to a `.py` or a workflow file
        classifies as judgeable and still re-runs the reviewer — paths classify,
        contents do not. Stating it here stops the rule from being read as
        broader than it is and then applied by eye after all, which is the
        failure it was written to remove."""
        content = flowed(PR_SKILL)
        assert "a comment-only edit to a `.py` or a CI workflow **is** judgeable" in content
