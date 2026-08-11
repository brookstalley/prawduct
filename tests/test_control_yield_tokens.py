"""Guards the observable-yield obligation on Critic controls.

`nonfunctional-requirements.md` § Direction: a control added from 2026-07-29
onward "names the yield it expects **and emits that yield observably**, so there
is something to measure it against later — a control whose findings are printed
and forgotten satisfies the letter and defeats the point, since it can never be
retired on evidence, only defended on principle."

Goal-level attribution cannot carry that weight. Findings do persist a `goal`
field into the review fact, but it is free text written by the reviewer and it
drifts: the same framework check appears in the shared evidence store under
several spellings. A check that lives as one bullet *inside* a goal is a
fortiori uncountable that way.

So each such control instructs the reviewer to open the finding title with a
stable token, which makes its yield a one-line query over the evidence store.
These tests pin the tokens. They exist because the surfaces they guard are
token-budgeted and under standing pressure to be trimmed — without a guard, the
countability is the easiest thing to lose to a reflow, and losing it is silent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parent.parent / "plugin"

CRITIC_PROTOCOL = PLUGIN / "skills/critic/review-protocol.md"
CRITIC_GOALS_13 = PLUGIN / "skills/critic/goals-1-3.md"
PR_PROTOCOL = PLUGIN / "skills/pr/review-protocol.md"
REVIEWER_AGENT = PLUGIN / "agents/critic-reviewer.md"


class TestCrossComponentContractToken:
    """The Goal 1 cross-component message-contract check (chunk mode, BLOCKING)."""

    TOKEN = "cross-component-contract:"

    @pytest.mark.parametrize(
        "path",
        [CRITIC_PROTOCOL, CRITIC_GOALS_13],
        ids=["review_protocol", "goals_1_3"],
    )
    def test_both_copies_instruct_the_stable_token(self, path: Path) -> None:
        assert self.TOKEN in path.read_text(), (
            f"{path.name} no longer tells the reviewer to open the finding title "
            f"with `{self.TOKEN}` — the check's yield stops being countable, which "
            "is the observable-yield obligation the control shipped under."
        )

    def test_the_check_runs_in_chunk_mode(self) -> None:
        # The whole point of folding this into Goal 1 rather than Goal 5 is that
        # chunk mode is the cheapest gate; goals-1-3.md IS chunk mode's payload.
        # A check that drifts out of this file stops running where it was meant to.
        goal_1 = _section(CRITIC_GOALS_13.read_text(), "## 1. Nothing Is Broken", "## 2.")
        assert self.TOKEN in goal_1, (
            "the cross-component contract check left Goal 1 in goals-1-3.md — it "
            "was placed there so it runs in `chunk` mode, the earliest gate."
        )

    def test_the_check_is_blocking(self) -> None:
        goal_1 = _section(CRITIC_GOALS_13.read_text(), "## 1. Nothing Is Broken", "## 2.")
        bullets = [l for l in goal_1.splitlines() if self.TOKEN in l]
        assert bullets, (
            f"no Goal 1 bullet carries `{self.TOKEN}` — the check is gone, so its "
            "severity cannot be pinned; see the sibling token test."
        )
        bullet = bullets[0]
        assert "**BLOCKING**" in bullet, (
            "the cross-component contract check is no longer BLOCKING — a consumer "
            "waiting forever on a signal that is never sent is a hang, not a warning."
        )


class TestScopeTraceToken:
    """The scope pressure-test on the cumulative and PR protocols."""

    TOKEN = "scope-trace:"

    @pytest.mark.parametrize(
        "path",
        [CRITIC_PROTOCOL, PR_PROTOCOL],
        ids=["critic_protocol", "pr_protocol"],
    )
    def test_both_protocols_instruct_the_stable_token(self, path: Path) -> None:
        assert self.TOKEN in path.read_text(), (
            f"{path.name} no longer tells the reviewer to open the finding title "
            f"with `{self.TOKEN}` — the check's yield stops being countable."
        )

    def test_the_pr_copy_targets_summary_not_a_title(self) -> None:
        # The two protocols persist DIFFERENT finding shapes and this is the
        # whole reason the PR bullet is worded differently. A Critic partial has
        # `name` (consolidated to `title`); a PR findings record is
        # {goal, severity, file, line, summary} with no title field at all, so
        # "open the title with ..." there names something that never persists.
        # Without this test, normalising the two bullets to match restores the
        # original defect with the suite green.
        bullet = next(
            l for l in PR_PROTOCOL.read_text().splitlines() if self.TOKEN in l
        )
        assert "`summary`" in bullet, (
            "the PR scope-trace bullet no longer targets `summary` — PR findings "
            "persist no title field, so any other target is uncountable."
        )
        # Assert the INSTRUCTION's target, not the absence of a word: the bullet
        # legitimately explains *why* (`findings here persist no title field`),
        # so a naive "title must not appear" check fails on correct prose.
        assert "open the title" not in bullet.lower(), (
            "the PR scope-trace bullet instructs opening a *title* — PR findings "
            "persist no title field, so that names something that never lands."
        )

    def test_it_stays_out_of_the_chunk_mode_payload(self) -> None:
        # Deliberately NOT a chunk-mode check: it asks whether a capability should
        # exist and is consumed end-to-end, which needs the whole bundle to answer.
        # It also must not drift into Goals 1-3, where the copies-agree drift
        # detector would then require it in goals-1-3.md as well.
        assert self.TOKEN not in CRITIC_GOALS_13.read_text(), (
            "the scope pressure-test reached goals-1-3.md — it is scoped to "
            "`final`/`cumulative` and PR review, where the full bundle is in view."
        )


class TestRuleUnenforcedToken:
    """The rule-over-instance instruction: a written rule with no enforcer is
    reported once, as the rule, instead of once per occurrence.

    Shipped 2026-08-11 after an audit of 141 PR-review records found 19% of the
    PR reviewer's warnings were a class whose rule already existed in three
    places — one finding even cites the learning while filing the instance.
    """

    TOKEN = "rule-unenforced:"
    HEADLINE = "no enforcer, the finding is the rule"

    @pytest.mark.parametrize(
        "path",
        [REVIEWER_AGENT, PR_PROTOCOL],
        ids=["critic_reviewer_agent", "pr_protocol"],
    )
    def test_both_copies_instruct_the_stable_token(self, path: Path) -> None:
        assert self.TOKEN in path.read_text(), (
            f"{path.name} no longer tells the reviewer to open the finding "
            f"`summary` with `{self.TOKEN}` — the instruction's own yield stops "
            "being countable, which is the observable-yield obligation it "
            "shipped under. It was reviewed as the sharpest finding against it: "
            "declining a lint for want of measured evidence while shipping an "
            "instruction that can never produce any."
        )

    def test_it_binds_every_reviewer_role_not_just_the_cross_check_owner(self) -> None:
        # The load-bearing placement. Two reviewers found this independently on
        # the first cut: the rule lived in review-cycle.md's Learnings
        # Cross-Check, which agents/critic-reviewer.md routes ONLY to the
        # sustainability role — while stale counts and citation drift are filed
        # under correctness (Goals 1-3) and design (Goal 4). Partials are
        # independent, so the role holding the rule cannot substitute for
        # another's finding. It has to live where all three roles read it.
        agent = REVIEWER_AGENT.read_text()
        assert self.HEADLINE in agent, (
            "the rule-over-instance instruction left agents/critic-reviewer.md — "
            "it is the only Critic surface every reviewer role reads, and in any "
            "other one it cannot reach the roles that file the class it targets."
        )
        assert "Every role" in _section(agent, self.HEADLINE, "## What to do") or (
            "binds all" in _section(agent, self.HEADLINE, "## What to do")
        ), (
            "the instruction no longer says it binds every role — without that, a "
            "reviewer reads it as the Learnings Cross-Check owner's job, which is "
            "exactly the routing defect it was moved here to fix."
        )

    @pytest.mark.parametrize(
        "path",
        [REVIEWER_AGENT, PR_PROTOCOL],
        ids=["critic_reviewer_agent", "pr_protocol"],
    )
    def test_the_dedupe_scope_is_decidable_and_agrees(self, path: Path) -> None:
        # First cut said "not again while it is open" — undecidable for a cold
        # reviewer fork with no state recording that a report is open, so it
        # resolved either to re-filing (no saving) or to silence indistinguishable
        # from suppression. Scope is one review; cross-branch dedupe is the
        # builder's disposition.
        text = path.read_text()
        assert "this review" in text, (
            f"{path.name} no longer scopes the instruction to THIS review — the "
            "only scope a stateless reviewer can actually decide."
        )
        assert "while it is open" not in text, (
            f"{path.name} re-grew the undecidable cross-branch clause: a reviewer "
            "fork cannot read whether a prior finding is still open."
        )

    @pytest.mark.parametrize(
        "path",
        [REVIEWER_AGENT, PR_PROTOCOL],
        ids=["critic_reviewer_agent", "pr_protocol"],
    )
    def test_it_is_substitution_not_suppression(self, path: Path) -> None:
        # R2 of the plan. Without this clause the instruction reads as a licence
        # to drop findings, which is strictly worse than the per-instance filing
        # it replaces.
        text = path.read_text()
        assert "not suppression" in text, (
            f"{path.name} lost the substitution-not-suppression clause — the "
            "instruction then reads as permission to drop the report entirely."
        )

    def test_the_single_pass_route_survives(self) -> None:
        # The narrowest carrier, and the one the ceiling punishes. A single-pass
        # `final`/`cumulative` fork reads review-cycle.md, NOT the agent
        # definition — SKILL.md routes it to four protocol files and that is not
        # one of them. So this pointer is the ONLY way the rule reaches that
        # fork. Its file sits at 9597 against `assert tokens < 9600` under a
        # standing "the next addition trims or relocates" rule, which means
        # deleting this sentence and lowering LAST_MEASURED_TOKENS is a green
        # suite. That is precisely why presence is asserted here rather than
        # left to the token record.
        cycle = (PLUGIN / "skills/critic/review-cycle.md").read_text()
        assert self.HEADLINE in cycle, (
            "review-cycle.md lost the rule-over-instance pointer — a single-pass "
            "final/cumulative reviewer now has no route to the rule at all, "
            "because SKILL.md never sends it to agents/critic-reviewer.md."
        )
        assert "agents/critic-reviewer.md" in cycle and "single-pass" in cycle, (
            "the pointer no longer names its target or its audience — it has to "
            "tell the single-pass fork to open the agent definition, which is "
            "the one file SKILL.md does not route it to."
        )
        assert self.TOKEN in cycle, (
            "the pointer dropped the `rule-unenforced:` token, so a single-pass "
            "reviewer would file the finding uncountably even when it reads the "
            "rule correctly."
        )

    @pytest.mark.parametrize(
        "path",
        [REVIEWER_AGENT, PR_PROTOCOL],
        ids=["critic_reviewer_agent", "pr_protocol"],
    )
    def test_the_second_condition_is_checked_not_assumed(self, path: Path) -> None:
        # The first cut's own worked example asserted stale pinned counts have no
        # check; `record_lint`'s suite-total-claim is exactly that check. A
        # reviewer following it would file "unenforced" about an enforced rule.
        text = path.read_text()
        assert "suite-total-claim" in text, (
            f"{path.name} dropped the worked counter-example — the instruction's "
            "second condition (no check owns it) is the one a reviewer is most "
            "likely to assume rather than verify, and pinned counts are the case "
            "where assuming it is wrong."
        )


def _section(text: str, start: str, end: str) -> str:
    begin = text.index(start)
    return text[begin : text.index(end, begin)]
