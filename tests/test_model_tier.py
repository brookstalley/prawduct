"""Which model a dispatched reviewer runs on, given the session's model.

One function owns the answer (`lib.model_tier.reviewer_model_for`). A session
recognisably at or below Opus-class gets no override, so its reviewer inherits
the session's model exactly as before. Anything else — a stronger tier, an id
the code does not recognise, or no id at all — gets the Opus-class alias, so a
new stronger tier is capped with no code change and a dispatcher that forgets
to say what it runs on cannot leave a reviewer uncapped.

The forms are the ones the host actually reports: a bare alias, a full id, and
a full id with a bracketed context suffix.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parent.parent / "plugin"
if str(PLUGIN) not in sys.path:
    sys.path.insert(0, str(PLUGIN))

from lib import model_tier, telemetry  # noqa: E402

AT_OR_BELOW = [
    "haiku", "sonnet", "opus", "Opus",
    "claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-8", "claude-opus-5-5",
    "claude-haiku-4-5[1m]", "claude-sonnet-4-5[1m]", "claude-opus-4-8[1m]",
    "  claude-opus-5-5  ",
]

ABOVE = [
    "fable", "Fable", "claude-fable-1", "claude-fable-5[1m]",
]

UNRECOGNISED = ["claude-mystery-9", "gpt-5", "some-new-tier[1m]"]

ABSENT = [None, "", "   "]


@pytest.mark.parametrize("session_model", AT_OR_BELOW)
def test_a_session_at_or_below_the_ceiling_gets_no_override(session_model):
    assert model_tier.reviewer_model_for(session_model) is None


@pytest.mark.parametrize("session_model", ABOVE + UNRECOGNISED + ABSENT)
def test_any_other_session_is_capped_at_the_ceiling(session_model):
    answer = model_tier.reviewer_model_for(session_model)
    assert answer == model_tier.CEILING_ALIAS
    # The cap names the ceiling itself, and the ceiling is a tier the
    # function treats as at-or-below: a capped reviewer is never re-capped.
    assert model_tier.reviewer_model_for(answer) is None


def test_the_ceiling_alias_is_the_opus_class_alias():
    """The one place the alias string is asserted by value: the owner's ruling
    caps reviewers at Opus-class, and the host accepts the bare alias."""
    assert model_tier.CEILING_ALIAS == "opus"


def test_review_stats_folds_models_with_the_same_matcher():
    """One family matcher, shared: the grouping `review-stats` reports and the
    ceiling the dispatch applies cannot disagree about what a model id names."""
    assert telemetry._canonical_model is model_tier.canonical_model
    for model in AT_OR_BELOW + ABOVE:
        assert model_tier.canonical_model(model) in model_tier.MODEL_FAMILIES


def test_the_alias_has_one_home_in_the_plugin_code():
    """No other module spells a model alias as a string literal, so nothing
    else can choose a reviewer's model or keep a second family list."""
    literal = re.compile(r"""["'](opus|sonnet|haiku|fable)["']""")
    offenders = []
    scanned = 0
    for path in sorted((PLUGIN / "lib").rglob("*.py")) + [PLUGIN / "bin" / "prawduct-hook"]:
        scanned += 1
        if path.name == "model_tier.py":
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if literal.search(line):
                offenders.append(f"{path.relative_to(PLUGIN)}:{lineno}: {line.strip()}")
    assert scanned > 10, "the sweep read almost nothing"
    assert not offenders, "a model alias is spelled outside lib/model_tier.py:\n" + "\n".join(offenders)
    assert literal.search((PLUGIN / "lib" / "model_tier.py").read_text(encoding="utf-8")), (
        "control: the sweep's pattern must match the module that owns the aliases"
    )


@pytest.mark.parametrize("answer", [None, "opus"])
def test_the_answer_line_names_what_to_pass(answer):
    """The dispatch line the skill prose acts on: it names the model to pass,
    or says plainly to pass none."""
    line = model_tier.reviewer_model_line(answer)
    assert line.startswith("reviewer model: ")
    value = line.split("reviewer model: ", 1)[1].split(" ", 1)[0]
    if answer is None:
        assert value == "none"
        assert "pass no `model`" in line
    else:
        assert value == answer
        assert f"`model: {answer}`" in line
