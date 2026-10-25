"""A plan's lifecycle, observed — the one derivation of LC1 (#1050 § 5).

A work unit is ``in-progress``, ``merged-unreleased``, ``released`` or
``superseded``, and which one is already written down elsewhere: in the plan's
archive stamp, in the change record's release tags and pending fragments, and in
git's answer to whether the plan's branch reached its base. So the lifecycle is
stored nowhere; :func:`observe` reads it off those, and says ``unknown`` — with
what was missing — when they do not answer.

The rule, in precedence order, each step's ``reason`` naming what it observed:

1. The plan carries an archive stamp (``plan_archive.read_completion``):
   ``superseded``, or ``released`` for ``completed`` with the stamp's
   ``released_in``. No git call.
2. Its scope is shipped in the change record (``plan_backfill.shipped_scopes``
   over the live log and its archive): ``released``, with the tag. No git call.
3. Its ``branch:`` exists, locally or as ``<remote>/<branch>``, and its tip is
   not contained in its base: ``in-progress``.
4. The tip is contained in the base: ``merged-unreleased``.
5. The branch is gone: the newest review fact for the scope whose anchor the
   base contains → ``merged-unreleased`` (a merge-commit merge keeps the
   reviewed commits in the base's history); else a pending change record for the
   scope (``release_readiness.pending_scopes``) → ``merged-unreleased``, inferred
   from the deleted branch and the pending record.
6. Otherwise ``unknown``. With ``probe_pr=True``, ``gh`` is asked first whether a
   pull request from the branch merged (``git_hygiene.merged_pr_for``) — the one
   route for a squash or rebase merge, whose reviewed commits the base never
   holds.

**The base.** The plan's ``base:``, or the repo's integration base
(``coverage.repo_base_branch``) when it declares none. A declared base is looked
for locally and on every remote, and "contained in the base" means contained in
any of them: a merge GitHub made is on ``origin/<base>`` before the local branch
is pulled, and a merge made locally is on ``<base>`` before it is pushed. Both
are merges.

**Advice fails soft.** Nothing here gates: ``plan status`` prints it and
``plan check-claims`` reads its ``merged-unreleased``. So :func:`observe` never
raises; git failing, an unreadable plan or an unreadable change record each
yield ``unknown`` (or let a later step answer) with the reason saying which.

**Cost (NF1).** Steps 1–2 read files only. Steps 3–4 cost two git calls with a
declared base: one ``for-each-ref`` resolving the branch and base refs together,
one ``for-each-ref --contains`` asking whether any base ref holds the tip. Step 5
costs one ``--contains`` per distinct anchor, newest fact first, stopping at the
first hit. A plan with no ``base:`` adds what ``coverage.repo_base_branch``
costs. No network call unless ``probe_pr`` — pinned by spy in
``tests/test_plan_lifecycle.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from . import (
    change_log_archive,
    coverage,
    evidence,
    git_hygiene,
    gitstate,
    plan_archive,
    plan_backfill,
    plan_index,
    plan_status,
    release_readiness,
)

State = Literal["in-progress", "merged-unreleased", "released", "superseded", "unknown"]

IN_PROGRESS: State = "in-progress"
MERGED_UNRELEASED: State = "merged-unreleased"
RELEASED: State = "released"
SUPERSEDED: State = "superseded"
UNKNOWN: State = "unknown"


@dataclass(frozen=True)
class Lifecycle:
    """One plan's lifecycle.

    ``reason`` is one sentence naming what was observed (or, for ``unknown``,
    what was missing). ``released_in`` is the release tag for ``released`` when
    the record names one, else ``None``. ``probed`` is true when ``gh`` was
    asked — the one network call, made only under ``probe_pr``.
    """

    state: State
    reason: str
    released_in: str | None = None
    probed: bool = False


def observe(
    plan_path: Path, *, repo_dir: Path, facts: object = None, probe_pr: bool = False
) -> Lifecycle:
    """The lifecycle of the plan at ``plan_path`` in the repo at ``repo_dir``.

    ``facts`` is an ``evidence.read_facts`` result when the caller holds one;
    omitted, the store is read only if step 5 needs it. Never raises.
    """
    repo_dir = Path(repo_dir)
    try:
        content = Path(plan_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return Lifecycle(UNKNOWN, f"the plan could not be read ({exc})")

    # (1) The archive stamp — the one stored field this reads, because archival
    # is the act that ended the plan's live presence and the stamp is its record.
    stamp = plan_archive.read_completion(content)
    if stamp is not None:
        if stamp.get(plan_archive.LIFECYCLE_KEY) == plan_archive.SUPERSEDED:
            by = stamp.get(plan_archive.SUPERSEDED_BY_KEY)
            return Lifecycle(
                SUPERSEDED,
                "its archive stamp records `lifecycle: superseded`"
                + (f" by {by}" if by else ""),
            )
        release = stamp.get(plan_archive.RELEASE_KEY) or None
        return Lifecycle(
            RELEASED,
            "its archive stamp records `lifecycle: completed`"
            + (f", released in {release}" if release else ""),
            released_in=release,
        )

    _present, scope = plan_index.parse_build_plan_frontmatter_scope(content)
    prawduct_dir = gitstate.get_prawduct_dir(repo_dir)

    # (2) Shipped in the change record.
    record_note = ""
    if scope:
        text = change_log_archive.load_all_text(prawduct_dir)
        if text is None:
            record_note = "; the change log could not be read, so whether it shipped is unread"
        else:
            tag = plan_backfill.shipped_scopes(text).get(scope)
            if tag:
                return Lifecycle(
                    RELEASED,
                    f"the change record ships scope `{scope}` in {tag}, with no later "
                    "unreleased entry for it",
                    released_in=tag,
                )

    branch = _ref_token(plan_index.parse_build_plan_frontmatter_branch(content))
    if branch is None:
        return Lifecycle(
            UNKNOWN,
            "the plan declares no `branch:`, so there is no branch whose merge could be "
            f"observed{record_note}",
        )

    declared_base = _ref_token(plan_index.parse_build_plan_frontmatter_base(content))
    patterns = [f"refs/heads/{branch}", f"refs/remotes/*/{branch}"]
    if declared_base:
        patterns += [f"refs/heads/{declared_base}", f"refs/remotes/*/{declared_base}"]
    code, out, err = evidence.run_git(
        repo_dir, "for-each-ref", "--format=%(objectname) %(refname)", *patterns
    )
    if code != 0:
        return Lifecycle(
            UNKNOWN, f"git could not list this repo's refs ({err or f'exit {code}'})"
        )
    refs = _exact_refs(out)
    branch_refs = {r: sha for r, sha in refs.items() if _names(r, branch)}
    if declared_base:
        base_refs = sorted(r for r in refs if _names(r, declared_base))
        base_label = f"`{declared_base}`"
        base_missing = None if base_refs else f"its base `{declared_base}` is on no local or remote branch"
    else:
        base_ref, why = coverage.repo_base_branch(repo_dir)
        if base_ref and not base_ref.startswith("HEAD"):
            # `origin/develop` or `develop`: whichever full name exists answers.
            base_refs = [f"refs/heads/{base_ref}", f"refs/remotes/{base_ref}"]
            base_label, base_missing = f"`{base_ref}`", None
        else:
            base_refs, base_label = [], "its base"
            base_missing = (
                "the plan declares no `base:` and the repo's integration base did not "
                f"resolve ({why if not base_ref else 'only a HEAD-relative fallback'})"
            )

    # (3)/(4) The branch exists: is its tip in the base?
    tip = branch_refs.get(f"refs/heads/{branch}") or next(
        (sha for _r, sha in sorted(branch_refs.items())), None
    )
    if tip is not None:
        where = "locally" if f"refs/heads/{branch}" in branch_refs else "on a remote"
        if base_missing:
            return Lifecycle(UNKNOWN, f"`{branch}` exists {where}, but {base_missing}")
        contained = _contained_in(repo_dir, tip, base_refs)
        if contained is None:
            return Lifecycle(
                UNKNOWN,
                f"`{branch}` exists {where}, but git could not say whether {base_label} "
                "contains its tip",
            )
        if contained:
            return Lifecycle(
                MERGED_UNRELEASED,
                f"`{branch}` exists {where} and its tip is in `{contained}`'s history",
            )
        return Lifecycle(
            IN_PROGRESS, f"`{branch}` exists {where} and its tip is not in {base_label}'s history"
        )

    # (5) The branch is gone. A review the scope recorded, anchored in the base.
    gone = f"`{branch}` is on no local or remote branch"
    if scope and not base_missing:
        store = facts if isinstance(facts, dict) else evidence.read_facts(repo_dir)
        for fact_id, anchor in _anchors_newest_first(store, scope):
            contained = _contained_in(repo_dir, anchor, base_refs)
            if contained:
                return Lifecycle(
                    MERGED_UNRELEASED,
                    f"{gone}, and review {fact_id}'s commit {anchor[:12]} is in "
                    f"`{contained}`'s history",
                )

    # A pending change record for the scope: the branch was merged and deleted
    # and the release has not cut its record yet (gitflow retention).
    pending_note = ""
    if scope:
        pending = release_readiness.pending_scopes(repo_dir)
        if pending.read_error is not None:
            pending_note = f"; the pending change records could not be read ({pending.read_error})"
        else:
            record = (
                "change-log entry" if scope in pending.legacy_scopes
                else "fragment" if scope in pending.fragment_scopes
                else None
            )
            if record is not None:
                return Lifecycle(
                    MERGED_UNRELEASED,
                    f"inferred: {gone}, and its {record} for scope `{scope}` is pending "
                    "release",
                )
            if pending.refusals:
                pending_note = (
                    "; the pending change records were refused ("
                    + "; ".join(pending.refusals) + ")"
                )

    # (6) Nothing local answers. Ask GitHub only when told to.
    if not scope:
        looked = "the plan declares no `scope:` to find its reviews or change record by"
    elif base_missing:
        looked = f"{base_missing}, and no change record for scope `{scope}` is pending"
    else:
        looked = (
            f"no review fact for scope `{scope}` has its commit in {base_label}'s history, "
            "and no change record for it is pending"
        )
    missing = f"{gone}; {looked}{pending_note}{record_note}"
    if probe_pr:
        number = git_hygiene.merged_pr_for(repo_dir, branch)
        if isinstance(number, int) and not isinstance(number, bool):
            return Lifecycle(
                MERGED_UNRELEASED,
                f"{gone}, and `gh` lists pull request #{number} from it as merged",
                probed=True,
            )
        asked = (
            "`gh` lists no merged pull request from it"
            if number is False
            else "`gh` could not be asked whether a pull request from it merged"
        )
        return Lifecycle(UNKNOWN, f"{missing}; {asked}", probed=True)
    return Lifecycle(UNKNOWN, missing)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ref_token(value: str | None) -> str | None:
    """A frontmatter branch name fit for a git argv, else ``None`` — a value
    opening with ``-`` would be read as an option."""
    value = (value or "").strip()
    return value if value and not value.startswith("-") else None


def _exact_refs(out: str) -> dict[str, str]:
    """``refname → objectname`` from ``for-each-ref --format='%(objectname) %(refname)'``."""
    refs: dict[str, str] = {}
    for line in out.splitlines():
        sha, _sp, ref = line.strip().partition(" ")
        if gitstate.is_object_id(sha) and ref:
            refs[ref] = sha
    return refs


def _names(ref: str, branch: str) -> bool:
    """Whether ``ref`` is exactly ``branch``, local or on one remote.

    ``for-each-ref`` patterns also match by prefix up to a slash
    (``refs/heads/feature`` lists ``refs/heads/feature/x``), so every listed
    ref is checked for the exact name here.
    """
    if ref == f"refs/heads/{branch}":
        return True
    prefix = "refs/remotes/"
    if not ref.startswith(prefix) or not ref.endswith(f"/{branch}"):
        return False
    remote = ref[len(prefix) : -len(branch) - 1]
    return bool(remote) and "/" not in remote


def _contained_in(repo_dir: Path, commit: str, base_refs: list[str]) -> str | None | bool:
    """The short name of a base ref whose history holds ``commit``; ``False``
    when none does; ``None`` when git could not answer (a commit this clone does
    not hold is such a case). ``base_refs`` are full ref names, and the output
    is filtered to exactly them, because ``for-each-ref`` patterns also match by
    prefix."""
    code, out, _err = evidence.run_git(
        repo_dir, "for-each-ref", "--contains", commit, "--format=%(refname)", *base_refs
    )
    if code != 0:
        return None
    wanted = set(base_refs)
    for line in out.splitlines():
        ref = line.strip()
        if ref in wanted:
            return ref.removeprefix("refs/heads/").removeprefix("refs/remotes/")
    return False


def _anchors_newest_first(store: dict, scope: str) -> list[tuple[str, str]]:
    """``(fact id, anchor)`` for each review fact of ``scope`` with a placeable
    anchor, newest first (by ``ts``, then store order), one per distinct anchor."""
    reviews = [
        (i, f) for i, f in enumerate(evidence.facts_of_kind(store, "review"))
        if isinstance(f.get("id"), str) and (f.get("body") or {}).get("scope") == scope
    ]
    reviews.sort(key=lambda p: (str(p[1].get("ts") or ""), p[0]), reverse=True)
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for _i, fact in reviews:
        anchor = plan_status.review_anchor(fact.get("body") or {})
        if gitstate.is_object_id(anchor) and anchor not in seen:
            seen.add(anchor)
            out.append((fact["id"], anchor))
    return out
