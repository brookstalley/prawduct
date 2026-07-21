"""Reviewer-dispatch model prose: reviewers run on the SESSION model — no
intelligent model switching.

Emergency patch (2026-07-14): the old reviewer-model-tiering scheme mapped a
diff's risk `tier` to a model chain (`escalate` → `model: fable` → `opus`;
`standard` → `opus` → `sonnet`) and pinned the Critic coordinator to
`model: opus`. In practice `classify-diff-risk` returned `escalate` for almost
any declared risk surface, so reviews escalated to Fable constantly. The
mechanism was removed: reviewers now inherit the current session model (opus
stays opus, fable stays fable) and no surface passes a `model:` override for the
reviewer.

These are structural regression pins against re-introducing intelligent
model switching. The `classify-diff-risk` command and the Critic `--tier`
telemetry are intentionally retained (tier is recorded but selects no model);
the model-recording plumbing and `review-stats` aggregation are unaffected.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent / "plugin"

_CRITIC_SKILL = REPO_ROOT / "skills" / "critic" / "SKILL.md"
_CRITIC_PROTOCOL = REPO_ROOT / "skills" / "critic" / "review-protocol.md"
_PR_SKILL = REPO_ROOT / "skills" / "pr" / "SKILL.md"


@pytest.mark.parametrize(
    "path",
    [_CRITIC_PROTOCOL, _PR_SKILL],
    ids=["critic_protocol", "pr_skill"],
)
def test_reviewer_dispatch_uses_the_session_model(path: Path) -> None:
    # The reviewer-dispatch surface must direct the reviewer onto the session
    # model — the whole point of the emergency patch. Losing this phrasing is
    # the drift signal that some tier→model rule crept back in.
    content = path.read_text()
    assert "session model" in content, (
        f"{path.relative_to(REPO_ROOT)} no longer directs the reviewer onto the "
        "**session model** — reviewer-model switching may have been "
        "re-introduced (emergency patch 2026-07-14)."
    )


@pytest.mark.parametrize(
    "path",
    [_CRITIC_PROTOCOL, _PR_SKILL],
    ids=["critic_protocol", "pr_skill"],
)
def test_no_reviewer_model_tiering(path: Path) -> None:
    # Any pinned reviewer model — `fable` (the escalation pin that caused the
    # over-escalation) OR a `standard`-tier chain (`opus`→`sonnet`) — means
    # tier→model switching is back. Reviewers must run on the session model with
    # no `model:` override. (`model: inherit` on the critic-reviewer AGENT is the
    # inherit-the-session posture, not a pin, and lives in a different file.)
    content = path.read_text()
    for pin in ("model: fable", "model: opus", "model: sonnet"):
        assert pin not in content, (
            f"{path.relative_to(REPO_ROOT)} pins `{pin}` — reviewer-model tiering "
            "is back. Reviewers must run on the session model with no `model:` "
            "override (emergency patch 2026-07-14)."
        )


def test_critic_skill_does_not_pin_a_reviewer_model() -> None:
    # The forked Critic must inherit the session model, so its frontmatter must
    # NOT carry a `model:` override (it previously pinned `model: opus`).
    frontmatter = _CRITIC_SKILL.read_text().split("---", 2)[1]
    model_lines = [
        line for line in frontmatter.splitlines() if line.strip().startswith("model:")
    ]
    assert not model_lines, (
        "skills/critic/SKILL.md frontmatter pins a reviewer model "
        f"({model_lines!r}) — the forked Critic must inherit the session model, "
        "so drop the `model:` override (emergency patch 2026-07-14)."
    )
