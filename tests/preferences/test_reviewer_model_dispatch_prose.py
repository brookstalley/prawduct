"""Reviewer-dispatch model prose: reviewers run on the session model up to the
reviewer ceiling, and no prose chooses a model.

The norm ("Reviewers run on the session model — no intelligent model
switching", `project-preferences.md` Enforcement) was amended by the owner on
2026-11-10 — "Yes cap at opus" — so a session above Opus-class dispatches its
reviewers on Opus-class, and every other session dispatches them on its own
model, as before. What stays forbidden is what the norm was written against: a
model chosen by the diff's risk `tier` (the removed scheme escalated nearly every
review to the most expensive tier), and a model pinned in prose or front matter.

So the answer comes from code: `critic-begin --session-model` and
`pr-review-dispatch --begin --session-model` answer it with
`model_tier.reviewer_model_for`, and the dispatch surfaces pass that answer as
the Agent call's `model`, or pass none. These pins hold the prose side:

- no dispatch surface spells a model alias, so none can pick a model itself;
- each names the session model and the ceiling, and takes the model from the
  code's answer;
- the reviewer agents keep `model: inherit` and the Critic skill's front matter
  names no model, since a fixed model there would raise a lower-tier session's
  reviews and fail where that model is not offered;
- the answer has no tier input: `reviewer_model_for` takes the session model
  alone, and the coordinator still says the tier selects no model.
"""

from __future__ import annotations

import inspect
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent / "plugin"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_CRITIC_SKILL = REPO_ROOT / "skills" / "critic" / "SKILL.md"
_COORDINATOR = REPO_ROOT / "skills" / "critic" / "coordinator.md"
_PR_SKILL = REPO_ROOT / "skills" / "pr" / "SKILL.md"
_CRITIC_REVIEWER = REPO_ROOT / "agents" / "critic-reviewer.md"
_PR_REVIEWER = REPO_ROOT / "agents" / "pr-reviewer.md"

#: Every surface that starts a reviewer, or is the reviewer started.
_DISPATCH_SURFACES = [_CRITIC_SKILL, _COORDINATOR, _PR_SKILL, _CRITIC_REVIEWER, _PR_REVIEWER]

#: The surfaces that write an Agent call for a reviewer, each with the token by
#: which it takes the model from the code's answer.
_DISPATCHERS = {
    _COORDINATOR: "`reviewer_model`",
    _PR_SKILL: "`reviewer model: <value>`",
}

_ALIAS = re.compile(r"\b(opus|sonnet|haiku|fable)\b", re.IGNORECASE)


def _ids(paths):
    return [str(p.relative_to(REPO_ROOT)) for p in paths]


@pytest.mark.parametrize("path", _DISPATCH_SURFACES, ids=_ids(_DISPATCH_SURFACES))
def test_no_dispatch_surface_names_a_model(path: Path) -> None:
    hits = [
        f"{lineno}: {line.strip()[:120]}"
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if _ALIAS.search(line)
    ]
    assert not hits, (
        f"{path.relative_to(REPO_ROOT)} names a model alias — a dispatch surface "
        "passes the model code answered and never picks one:\n" + "\n".join(hits)
    )


def test_the_alias_check_can_fire() -> None:
    """Control: the pattern catches the pins the old scheme wrote, and does not
    fire on the words a dispatch surface legitimately uses."""
    for pin in ("model: fable", "model: opus", "`model: sonnet`", "Opus-class", "haiku"):
        assert _ALIAS.search(pin), pin
    for fine in ("model: inherit", "the session model", "the reviewer ceiling", "reviewer_model"):
        assert not _ALIAS.search(fine), fine


@pytest.mark.parametrize("path", list(_DISPATCHERS), ids=_ids(_DISPATCHERS))
def test_each_dispatcher_takes_the_model_from_code(path: Path) -> None:
    content = path.read_text(encoding="utf-8")
    assert "session model" in content, (
        f"{path.relative_to(REPO_ROOT)} no longer names the session model, which "
        "is what an uncapped reviewer runs on"
    )
    assert "ceiling" in content, (
        f"{path.relative_to(REPO_ROOT)} no longer names the reviewer ceiling"
    )
    assert _DISPATCHERS[path] in content, (
        f"{path.relative_to(REPO_ROOT)} no longer takes the reviewer's model from "
        f"the code's answer ({_DISPATCHERS[path]})"
    )
    assert "pass no `model`" in content, (
        f"{path.relative_to(REPO_ROOT)} no longer says what to do when the answer "
        "names no model"
    )


@pytest.mark.parametrize("path", [_CRITIC_SKILL, _PR_SKILL], ids=_ids([_CRITIC_SKILL, _PR_SKILL]))
def test_each_dispatch_command_is_told_the_session_model(path: Path) -> None:
    """The answer is only as good as its input: the command each skill runs to
    dispatch carries the model the dispatcher runs as."""
    body = path.read_text(encoding="utf-8").split("---", 2)[2]  # the grant line is not an instruction
    command = "critic-begin --mode" if path == _CRITIC_SKILL else "pr-review-dispatch --begin"
    invocations = re.findall(r"`[^`\n]*" + re.escape(command) + r"[^`\n]*`", body)
    assert invocations, f"{path.relative_to(REPO_ROOT)} no longer instructs `{command}`"
    for invocation in invocations:
        assert "--session-model" in invocation, (
            f"{path.relative_to(REPO_ROOT)} runs {invocation} without "
            "--session-model, so the cap is assumed rather than answered"
        )


@pytest.mark.parametrize("path", [_CRITIC_REVIEWER, _PR_REVIEWER], ids=_ids([_CRITIC_REVIEWER, _PR_REVIEWER]))
def test_the_reviewer_agents_inherit(path: Path) -> None:
    frontmatter = path.read_text(encoding="utf-8").split("---", 2)[1]
    model_lines = [ln.strip() for ln in frontmatter.splitlines() if ln.strip().startswith("model:")]
    assert model_lines == ["model: inherit"], (
        f"{path.relative_to(REPO_ROOT)} declares {model_lines!r}; a reviewer agent "
        "inherits, and the dispatcher's Agent `model` is what caps it"
    )


def test_critic_skill_front_matter_names_no_model() -> None:
    frontmatter = _CRITIC_SKILL.read_text(encoding="utf-8").split("---", 2)[1]
    model_lines = [ln for ln in frontmatter.splitlines() if ln.strip().startswith("model:")]
    assert not model_lines, (
        f"skills/critic/SKILL.md front matter names a model ({model_lines!r}) — a "
        "fixed model would raise a lower-tier session's reviews and fail where it "
        "is not offered; the fork routes, and hands a capped review off instead"
    )


def test_the_reviewer_model_has_no_tier_input() -> None:
    from lib import model_tier

    params = list(inspect.signature(model_tier.reviewer_model_for).parameters)
    assert params == ["session_model"], (
        f"reviewer_model_for takes {params!r} — the reviewer's model follows the "
        "session's model alone; a tier or size input is model switching"
    )
    assert "`tier` is telemetry only and selects no model" in _COORDINATOR.read_text(encoding="utf-8")


#: The one forked skill that names no model, and why: `/prawduct:critic` runs on
#: the session's model because a fixed model would raise a lower-tier session's
#: reviews and fail where that model is not offered, and front matter cannot
#: express a ceiling. Above the ceiling it reviews nothing and hands the review to
#: reviewers dispatched on the capped model, so no review runs on the session's
#: tier there.
_FORKED_SKILLS_ON_THE_SESSION_MODEL = {"critic"}


def _forked_skills() -> dict[str, list[str]]:
    """Every skill whose front matter declares `context: fork`, with its
    `model:` lines — read from the files, not from a list."""
    found = {}
    for skill in sorted((REPO_ROOT / "skills").glob("*/SKILL.md")):
        frontmatter = skill.read_text(encoding="utf-8").split("---", 2)[1]
        lines = [ln.strip() for ln in frontmatter.splitlines()]
        if "context: fork" in lines:
            found[skill.parent.name] = [ln for ln in lines if ln.startswith("model:")]
    return found


def test_every_forked_skill_runs_at_or_below_the_ceiling() -> None:
    """A forked skill starts on its front matter's model, or on the session's
    when it names none — the most expensive choice available, made by accident
    on a session above the ceiling. So each one names a model the ceiling
    leaves alone, or is listed above with its reason."""
    from lib import model_tier

    forked = _forked_skills()
    assert {"critic", "backlog", "advisory"} <= set(forked), f"control: the sweep found {sorted(forked)}"
    for name, model_lines in forked.items():
        if name in _FORKED_SKILLS_ON_THE_SESSION_MODEL:
            assert not model_lines, f"skills/{name} is listed as running on the session model but names one"
            continue
        assert len(model_lines) == 1, f"skills/{name} is forked and names no model ({model_lines!r})"
        model = model_lines[0].split(":", 1)[1].strip()
        assert model != "inherit" and model_tier.reviewer_model_for(model) is None, (
            f"skills/{name} runs on {model!r}, which is not at or below the ceiling"
        )
