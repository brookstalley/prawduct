"""Model tiers: what a model id names, and which model a reviewer runs on.

Two answers live here, and they share one matcher so they cannot disagree about
what an id names:

- :func:`canonical_model` folds a recorded model id to its family label, the
  grouping key ``review-stats`` reports by. The same model arrives under several
  ids (``opus``, ``claude-opus-4-8``, ``claude-opus-4-8[1m]``), so a substring
  match folds a new version of a known family with no code change, and an id it
  does not recognise stays visible as itself rather than joining a known family.
- :func:`reviewer_model_for` answers which model an independent reviewer is
  dispatched on, given the model the dispatcher runs as. Reviewers are capped at
  Opus-class: a session at or below the ceiling gets no override and its
  reviewer inherits the session's model; any other session gets
  :data:`CEILING_ALIAS`. The owner ruled the cap because a stronger tier costs
  enough that a reviewer must never run on it by accident.

**The ceiling is decided by exclusion.** Only an id that names a family at or
below Opus-class is left alone. A stronger tier, an id nobody recognises, and no
id at all are all capped, so a new stronger tier is capped with no code change,
and a dispatcher that does not say what it runs on cannot leave its reviewer
uncapped. What that costs: a session on an unrecognised model, or one whose
dispatcher omits its model, gets Opus-class reviewers.

Nothing here reads a diff, a risk tier or a size: the reviewer's model follows
the session's model and nothing else.

The alias strings have this one home; ``tests/test_model_tier.py`` refuses a
model alias spelled as a literal anywhere else in the plugin's code.
"""

from __future__ import annotations

#: Model families a recorded id can fold to, matched as substrings of the
#: lowercased id.
MODEL_FAMILIES = ("opus", "sonnet", "haiku", "fable")

#: Families at or below the reviewer ceiling. A session on one of these
#: dispatches its reviewers with no model override.
_AT_OR_BELOW_CEILING = frozenset({"haiku", "sonnet", "opus"})

#: The alias a reviewer is dispatched on when the session is not recognisably at
#: or below the ceiling — an Agent call's ``model`` accepts it as given.
CEILING_ALIAS = "opus"


def canonical_model(model) -> str | None:
    """Fold a recorded model id to its family for grouping.

    Returns the family label when one is recognised, the trimmed original when
    it isn't (an unfamiliar model stays visible, never silently bucketed under a
    known family), and ``None`` when no model was recorded.
    """
    if not isinstance(model, str) or not model.strip():
        return None
    lowered = model.lower()
    for family in MODEL_FAMILIES:
        if family in lowered:
            return family
    return model.strip()


def reviewer_model_for(session_model) -> str | None:
    """The model to dispatch a reviewer on, given the dispatcher's own model.

    ``None`` means no override: the session is recognisably at or below the
    ceiling, so the reviewer inherits the session's model. Otherwise
    :data:`CEILING_ALIAS` — including for an unrecognised id and for no id.
    """
    if canonical_model(session_model) in _AT_OR_BELOW_CEILING:
        return None
    return CEILING_ALIAS


def reviewer_model_line(answer: str | None) -> str:
    """The dispatch line a skill acts on, rendered from :func:`reviewer_model_for`.

    It names the value first (``reviewer model: <alias>`` or ``reviewer model:
    none``) so the reader takes it without interpreting prose, then says what to
    do with it.
    """
    if answer is None:
        return (
            "reviewer model: none — pass no `model` on the Agent call; the "
            "reviewer runs on the session's model"
        )
    return (
        f"reviewer model: {answer} — pass `model: {answer}` on the Agent call "
        "that starts the reviewer (the session's model is above the reviewer "
        "ceiling, or was not given)"
    )


def session_model_missing_note(command: str) -> str:
    """The stderr note for a dispatch that did not say what model it runs on."""
    return (
        f"{command} was not told the session's model (--session-model), so a "
        f"reviewer model of {CEILING_ALIAS!r} was assumed — the cap applies "
        "unless the dispatcher says it runs at or below the ceiling"
    )
