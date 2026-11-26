"""Where a repo's boundary review runs: the one reader of ``boundary_review:``.

``per_pr`` (the default) runs the boundary review at every PR. ``per_release``
lets derived-eligible work move its boundary review to a release batch, which
the release check then blocks on (``nonfunctional-requirements.md``, the
stage-keyed clause's 2026-11-25 amendment). Moving a review is a lightening, so
the value that counts is the one on the integration branch: a branch that adds
``per_release`` is still ``per_pr`` until that change has merged, because a
governance change cannot supply its own authority. A branch may opt out, never
in. Every value this module cannot read, and every value but exactly
``per_release``, is ``per_pr``, the stricter policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .core import (
    BOUNDARY_REVIEW_KEY,
    YAML_SCALAR_VALUE,
    read_scalar_yaml_key,
    read_scalar_yaml_text,
)

PER_PR = "per_pr"
PER_RELEASE = "per_release"
VALUES = (PER_PR, PER_RELEASE)


@dataclass(frozen=True)
class Policy:
    """The boundary-review policy in force. ``value`` is :data:`PER_PR` or
    :data:`PER_RELEASE`; ``source`` names the revision it was read at (empty
    when none could be); ``note`` is empty or says, in a sentence, why a value
    someone wrote is not the one in force."""

    value: str
    source: str
    note: str = ""

    @property
    def per_release(self) -> bool:
        return self.value == PER_RELEASE


def _declared(text: "str | None") -> "str | None":
    """The value ``text`` declares, or ``None`` when it declares none."""
    state, raw = read_scalar_yaml_text(text, BOUNDARY_REVIEW_KEY)
    return raw if state == YAML_SCALAR_VALUE else None


def _unknown_note(raw: str, where: str) -> str:
    return (
        f"`{BOUNDARY_REVIEW_KEY}: {raw}` {where} is not a value prawduct reads "
        f"({PER_PR} or {PER_RELEASE}), so {PER_PR} is in force"
    )


def boundary_review_policy(project_dir: Path, base_ref: "str | None" = None) -> Policy:
    """The policy a branch's PR is judged under.

    ``per_release`` only when the merge-base with the integration branch
    declares it (``coverage.integration_base``, which refuses the ``HEAD~1``
    fallback) **and** the working tree still does. ``base_ref`` is the caller's
    already-resolved base; ``None`` resolves it here.
    """
    from . import coverage  # noqa: PLC0415 — lazy, as coverage's own evidence imports are

    project_dir = Path(project_dir)
    base = coverage.integration_base(project_dir, base_ref)
    on_base = _declared(base.state)
    _state, working = read_scalar_yaml_key(
        project_dir / ".prawduct" / "project-state.yaml", BOUNDARY_REVIEW_KEY
    )
    source = f"merge-base {base.merge_base[:12]}" if base.merge_base else ""
    in_force = PER_RELEASE if on_base == PER_RELEASE and working == PER_RELEASE else PER_PR

    note = ""
    if working is not None and working not in VALUES:
        note = _unknown_note(working, "in this checkout")
    elif on_base is not None and on_base not in VALUES:
        note = _unknown_note(on_base, "on the integration branch")
    elif working == PER_RELEASE and in_force == PER_PR:
        why = (
            "is not yet on the integration branch" if base.merge_base
            else "has no integration branch to be read from (set `base_branch:`)"
        )
        note = (
            f"`{BOUNDARY_REVIEW_KEY}: {PER_RELEASE}` {why}, so {PER_PR} is in force: "
            "a branch cannot opt itself in"
        )
    elif on_base == PER_RELEASE and in_force == PER_PR:
        note = (
            f"this checkout no longer declares `{BOUNDARY_REVIEW_KEY}: {PER_RELEASE}`, "
            f"so {PER_PR} is in force: a branch may opt out, never in"
        )
    return Policy(in_force, source, note)


def boundary_review_policy_at(project_dir: Path, rev: str) -> Policy:
    """The policy ``rev`` declares, for the release check, which reads it at
    the integration branch's tip. A ``project-state.yaml`` that does not read at
    ``rev`` is :data:`PER_PR`."""
    from . import coverage  # noqa: PLC0415

    text = coverage._state_in(Path(project_dir), rev)
    declared = _declared(text)
    if declared == PER_RELEASE:
        return Policy(PER_RELEASE, rev)
    if text is None:
        return Policy(PER_PR, rev, f"no project-state.yaml reads at {rev}, so {PER_PR} is in force")
    if declared is not None and declared not in VALUES:
        return Policy(PER_PR, rev, _unknown_note(declared, f"at {rev}"))
    return Policy(PER_PR, rev)
