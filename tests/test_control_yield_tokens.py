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

    def test_it_stays_out_of_the_chunk_mode_payload(self) -> None:
        # Deliberately NOT a chunk-mode check: it asks whether a capability should
        # exist and is consumed end-to-end, which needs the whole bundle to answer.
        # It also must not drift into Goals 1-3, where the copies-agree drift
        # detector would then require it in goals-1-3.md as well.
        assert self.TOKEN not in CRITIC_GOALS_13.read_text(), (
            "the scope pressure-test reached goals-1-3.md — it is scoped to "
            "`final`/`cumulative` and PR review, where the full bundle is in view."
        )


def _section(text: str, start: str, end: str) -> str:
    begin = text.index(start)
    return text[begin : text.index(end, begin)]
