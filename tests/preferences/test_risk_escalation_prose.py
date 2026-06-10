"""Risk-surface escalation dispatch prose: the classifier is wired into every
model-dispatching review surface (review-proportionality ch.04).

The classifier (`prawduct-hook classify-diff-risk`) only changes anything if
the skills that dispatch reviewer models actually consult it. Three surfaces
declare a reviewer tier: the Critic coordinator pattern (review-protocol.md),
the Critic entry skill (SKILL.md — which also needs the subcommand on its
allowed-tools, or the forked review can't run it), and the PR reviewer
dispatch (pr/SKILL.md step 3). Losing the prose on any one of them silently
reverts that surface to the flat default tier — exactly the drift class the
critic-skill-structure pins exist for.

Structural assertion, not a content audit: literal substring checks that each
surface names the subcommand and the escalation tier.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

_CRITIC_SKILL = REPO_ROOT / "skills" / "critic" / "SKILL.md"
_CRITIC_PROTOCOL = REPO_ROOT / "skills" / "critic" / "review-protocol.md"
_PR_SKILL = REPO_ROOT / "skills" / "pr" / "SKILL.md"


@pytest.mark.parametrize(
    "path",
    [_CRITIC_SKILL, _CRITIC_PROTOCOL, _PR_SKILL],
    ids=["critic_skill", "critic_protocol", "pr_skill"],
)
def test_dispatch_surface_consults_the_classifier(path: Path) -> None:
    content = path.read_text()
    assert "classify-diff-risk" in content, (
        f"{path.relative_to(REPO_ROOT)} no longer references "
        "`classify-diff-risk` — this dispatch surface has silently reverted "
        "to the flat reviewer tier (review-proportionality ch.04)."
    )


@pytest.mark.parametrize(
    "path",
    [_CRITIC_PROTOCOL, _PR_SKILL],
    ids=["critic_protocol", "pr_skill"],
)
def test_escalation_tier_declared(path: Path) -> None:
    content = path.read_text()
    assert "model: fable" in content, (
        f"{path.relative_to(REPO_ROOT)} does not declare the escalation tier "
        "(`model: fable`) — on `escalate` the dispatch would have no tier to "
        "switch to."
    )


def test_critic_allowed_tools_can_run_the_classifier() -> None:
    # The Critic runs as a restricted fork: a subcommand absent from
    # allowed-tools is structurally unrunnable no matter what the prose says.
    frontmatter = _CRITIC_SKILL.read_text().split("---", 2)[1]
    assert "Bash(prawduct-hook classify-diff-risk)" in frontmatter, (
        "skills/critic/SKILL.md allowed-tools is missing "
        "`Bash(prawduct-hook classify-diff-risk)` — the forked Critic cannot "
        "resolve the reviewer tier."
    )


def test_pr_skill_allowed_tools_can_run_the_classifier() -> None:
    # Step 3's dispatch prose runs the classifier, so the declared tool list
    # must carry the subcommand too (ch.04 wired the prose but missed the
    # frontmatter — found and fixed in ch.05).
    frontmatter = _PR_SKILL.read_text().split("---", 2)[1]
    assert "Bash(prawduct-hook classify-diff-risk)" in frontmatter, (
        "skills/pr/SKILL.md allowed-tools is missing "
        "`Bash(prawduct-hook classify-diff-risk)` — the /pr skill cannot "
        "resolve the reviewer tier its Step 3 prose calls for."
    )
