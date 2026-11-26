"""Where a repo's boundary review runs: the one reader of ``boundary_review:``.

``per_pr`` (the default) runs the boundary review at every PR. ``per_release``
lets derived-eligible work move its boundary review to a release batch, which
the release check then blocks on (``nonfunctional-requirements.md``, the
stage-keyed clause's 2026-11-25 amendment). Moving a review is a lightening, so
the value that counts is the one on the integration branch, both where the
branch forked and at its tip now: a branch that adds ``per_release`` is still
``per_pr`` until that change has merged, because a governance change cannot
supply its own authority, and a branch forked while the integration branch said
``per_release`` loses the lane when the integration branch drops it. A branch may
opt out, never in. Every value this module cannot read, and every value but
exactly ``per_release``, is ``per_pr``, the stricter policy for a PR. For the
release check ``per_release`` is the stricter one, so :func:`release_policy`
lets a checkout's own ``per_release`` stand where the integration branch's tip
cannot be read at all, or the read fails.

The integration branch is the REPO's (``coverage.repo_base_branch``), never a
stacked unit's own ``base:``: read at the unit's base, a branch adding
``per_release`` unmerged would authorise every unit cut from it
(:func:`integration_revs`, which the relaxations' held risk surfaces read too).

Every combination of readings is made here, never by a caller: a live branch's
PR (:func:`boundary_review_policy`), one revision (:func:`boundary_review_policy_at`),
a merged branch (:func:`boundary_review_policy_of_merge`) and the release check
(:func:`release_policy`, which never raises).
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
    someone wrote is not the one in force. ``read_failed`` is True only on
    :func:`release_policy`'s fallback, where reading the integration branch
    raised: the value is then this checkout's, and the release gate cannot
    answer under it (``boundary_coverage.release_gate``)."""

    value: str
    source: str
    note: str = ""
    read_failed: bool = False

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


def integration_revs(project_dir: Path) -> "tuple[str | None, str | None]":
    """``(merge-base, integration branch)``: where a relaxation reads what the
    integration branch declares. The branch is ``coverage.repo_base_branch``'s,
    the repo's, never a stacked unit's own ``base:`` (``_resolve_base_branch``),
    which an unmerged branch can rewrite; the merge-base is
    ``coverage.integration_base``'s, which refuses the ``HEAD~1`` fallback.
    ``(None, branch)`` when no merge-base resolves, ``(None, None)`` with no
    integration branch."""
    from . import coverage  # noqa: PLC0415 — lazy, as coverage's own evidence imports are

    base_ref, _why = coverage.repo_base_branch(Path(project_dir))
    if not base_ref:
        return None, None
    return coverage.integration_base(Path(project_dir), base_ref).merge_base, base_ref


def boundary_review_policy(project_dir: Path, base_ref: "str | None" = None) -> Policy:
    """The policy a branch's PR is judged under.

    ``per_release`` only when all three declare it: the merge-base with the
    integration branch (``coverage.integration_base``, which refuses the
    ``HEAD~1`` fallback), the integration branch's tip, and the working tree.
    Each can only narrow: the merge-base stops a branch opting itself in, the
    tip stops a branch forked while the integration branch said ``per_release``
    keeping the lane after it went back to ``per_pr``, and the working tree lets
    a branch opt out. The integration branch is the repo's
    (:func:`integration_revs`), so a unit stacked on an unmerged branch cannot
    take that branch's opt-in. ``base_ref`` names another one explicitly;
    ``None`` reads the repo's.
    """
    from . import coverage  # noqa: PLC0415 — lazy, as coverage's own evidence imports are

    project_dir = Path(project_dir)
    if base_ref is None:
        base_ref, _why = coverage.repo_base_branch(project_dir)
    base = coverage.integration_base(project_dir, base_ref)
    on_base = _declared(base.state)
    # Read only where a merge-base resolved, so base_ref is a real integration
    # branch: never the HEAD~1 fallback, which integration_base refuses.
    at_tip = _declared(coverage._state_in(project_dir, base_ref)) if base.merge_base else None
    working = _working_declared(project_dir)
    source = f"merge-base {base.merge_base[:12]}" if base.merge_base else ""
    in_force = (
        PER_RELEASE if on_base == PER_RELEASE and at_tip == PER_RELEASE and working == PER_RELEASE
        else PER_PR
    )

    note = ""
    if working is not None and working not in VALUES:
        note = _unknown_note(working, "in this checkout")
    elif on_base is not None and on_base not in VALUES:
        note = _unknown_note(on_base, "on the integration branch")
    elif at_tip is not None and at_tip not in VALUES:
        note = _unknown_note(at_tip, f"at the integration branch's tip ({base_ref})")
    elif on_base == PER_RELEASE and at_tip != PER_RELEASE:
        note = (
            f"the integration branch's tip ({base_ref}) no longer declares "
            f"`{BOUNDARY_REVIEW_KEY}: {PER_RELEASE}`, so {PER_PR} is in force, though this "
            "branch forked while it did"
        )
    elif working == PER_RELEASE and in_force == PER_PR:
        why = (
            "is not yet on the integration branch where this branch forked"
            + (f" (its tip, {base_ref}, declares it: sync the branch to take it)"
               if at_tip == PER_RELEASE else "")
            if base.merge_base
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


def boundary_review_policy_of_merge(project_dir: Path, merge_base: str, tip: str,
                                    base_tip: "str | None" = None) -> Policy:
    """The policy a merged branch was judged under: :data:`PER_RELEASE` only when
    its merge-base, its tip and ``base_tip`` (the merge's first parent: the
    integration branch's tip the PR gate read) all declare it (each read by
    :func:`boundary_review_policy_at`), for a caller asking of a branch that has
    already merged, so the working tree has no say. The merge-base stops a branch
    opting itself in; the tip lets it opt out; the base's tip is the one the live
    PR gate also asked (:func:`boundary_review_policy`), so the two readings
    agree. The note is the first revision's that does not declare it."""
    revs = [merge_base, *([base_tip] if base_tip else []), tip]
    for rev in revs:
        at = boundary_review_policy_at(project_dir, rev)
        if not at.per_release:
            return Policy(PER_PR, at.source, at.note)
    return Policy(PER_RELEASE, f"merge-base {merge_base[:12]}"
                               + (f", the base's tip {base_tip[:12]}" if base_tip else "")
                               + f" and tip {tip[:12]}")


def per_release_since(project_dir: Path, base: str, since: str) -> bool:
    """Was ``per_release`` declared on ``base``'s first-parent line at ``since``
    or at any first-parent commit after it that changed ``project-state.yaml``?
    The declaration at every commit in between is one of those, so False means
    no merge since ``since`` was judged ``per_release`` by the PR gate, which
    also asks the integration branch's tip. Any read that fails is True: the
    caller then classifies rather than skips."""
    from . import coverage, evidence  # noqa: PLC0415

    rc, out, _err = evidence.run_git(
        Path(project_dir), "log", "--first-parent", "--format=%H", f"{since}..{base}", "--",
        ".prawduct/project-state.yaml",
    )
    if rc != 0:
        return True
    for rev in [since, *out.split()]:
        text = coverage._state_in(Path(project_dir), rev)
        if text is None and rev == since:
            continue  # no state file at the release: nothing declared there
        if _declared(text) == PER_RELEASE:
            return True
    return False


def _working_declared(project_dir: Path) -> "str | None":
    """What this checkout's ``project-state.yaml`` declares, or ``None``."""
    _state, working = read_scalar_yaml_key(
        Path(project_dir) / ".prawduct" / "project-state.yaml", BOUNDARY_REVIEW_KEY
    )
    return working


def release_policy(project_dir: Path) -> Policy:
    """The policy the release check gates under: the one ``check-boundary-coverage
    --gate`` and ``check-releasability`` both read, so the two cannot disagree.

    Never raises: a read that fails is answered by this checkout's own
    declaration, :data:`PER_RELEASE` only when it declares it, the stricter
    reading for a release check, with a note naming the failure and
    ``read_failed`` set, so a ``per_release`` checkout's release gate refuses
    as unevaluable rather than answering under a guess. See
    :func:`_release_policy` for the reading itself."""
    try:
        return _release_policy(project_dir)
    except Exception as exc:  # prawduct:allow prawduct/broad-except -- the release check must answer; the fallback is the stricter reading where this checkout declares per_release
        try:
            working = _working_declared(project_dir)
        except Exception:  # prawduct:allow prawduct/broad-except -- nothing readable declares per_release, so there is nothing to gate under
            working = None
        return Policy(PER_RELEASE if working == PER_RELEASE else PER_PR, "", (
            f"the policy could not be read at the integration branch ({type(exc).__name__}: {exc}), "
            f"so this checkout's declaration stands ({working if working in VALUES else PER_PR})"
        ), read_failed=True)


def _release_policy(project_dir: Path) -> Policy:
    """:func:`release_policy`'s reading, which may raise.

    It is the integration branch's tip (:func:`boundary_review_policy_at` at
    ``coverage.repo_base_branch``), because that is what the PRs it holds were
    judged against. For the release check ``per_release`` is the stricter
    reading, so where the tip cannot be read at all (no integration base, or no
    ``project-state.yaml`` git can show there) this checkout's own declaration
    stands: a repo that declares ``per_release`` is not let past its release
    check by an unreadable ref. Where the tip reads, a checkout declaring
    ``per_release`` that the tip does not is told so in the note, and is not
    gated: the PRs it would hold were judged ``per_pr``."""
    from . import coverage  # noqa: PLC0415

    project_dir = Path(project_dir)
    base, why = coverage.repo_base_branch(project_dir)
    working = _working_declared(project_dir)
    if base and coverage._state_in(project_dir, base) is not None:
        policy = boundary_review_policy_at(project_dir, base)
        if not policy.per_release and working == PER_RELEASE and not policy.note:
            return Policy(PER_PR, base, (
                f"this checkout declares `{BOUNDARY_REVIEW_KEY}: {PER_RELEASE}` and {base}'s tip "
                f"does not, so the release check reads {PER_PR}: the PRs it would hold were "
                f"judged {PER_PR}"
            ))
        return policy
    where = f"at {base}" if base else f"(no integration base resolves: {why})"
    if working == PER_RELEASE:
        return Policy(PER_RELEASE, "the working tree", (
            f"no project-state.yaml reads {where}, so this checkout's "
            f"`{BOUNDARY_REVIEW_KEY}: {PER_RELEASE}` is in force: the release check fails closed"
        ))
    # Nobody declared per_release anywhere this can read, so there is nothing to explain.
    return Policy(PER_PR, "")
