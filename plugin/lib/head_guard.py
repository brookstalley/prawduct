"""Did the session's HEAD leave its branch while a review ran? (#1177)

A review reads the session's checkout and must never move it. In the field one
did: the host's native ``/code-review``, started beside a Critic review, ran
``git checkout <head>`` in the session's checkout, which detached HEAD at the
branch's own tip. Nothing changed on disk, so nothing looked wrong, and every
commit after that landed on no branch while a push sent the stale one.

The native review now runs in a worktree of its own (``native_review.prepare``),
which is the fix. This module is the detection under it, for any cause: given
the branch a review began on, it says whether HEAD has since been detached and
the command that puts the work back on the branch. Its callers are the surfaces
that already reach someone at the right time — the review's ``NEXT-ACTION``
(``native_review.next_action_clause`` for a paired review, and
``critic_consolidate.consolidate`` for any review, on every path that
consolidates — the explicit command, the SubagentStop hook and the Stop
backstop — and on every exit: in the record's ``next_action`` when one is
written, and on stderr ahead of a refusal when none is) and
``native-review record``'s output.

Only a DETACHED HEAD is reported. A switch to another branch is a deliberate
act, and no reviewer makes one; a detached HEAD is what a checkout of a commit
leaves, and it is the state in which work silently stops landing on a branch.
"""

from __future__ import annotations

from pathlib import Path


def left_branch(project_dir: Path, branch: "str | None") -> "dict | None":
    """``None`` when HEAD is still on a branch, or there was no branch to leave;
    otherwise what happened and how to recover:

    ``{"branch", "head", "tip", "contains_tip", "recovery"}`` — ``head`` the
    detached commit, ``tip`` the branch's commit now (``None`` when the branch
    is gone), and ``recovery`` the command that puts HEAD back on ``branch``
    keeping every commit made since. When HEAD cannot be read the dict carries
    ``error`` instead, so a failed probe is said rather than read as "fine"."""
    from . import evidence  # noqa: PLC0415 — lazy, matching the lib's other imports

    if not isinstance(branch, str) or not branch:
        return None
    rc, _out, err = evidence.run_git(project_dir, "symbolic-ref", "--quiet", "HEAD")
    if rc == 0:
        return None
    if rc != 1:
        return {"branch": branch, "error": err or f"git symbolic-ref exited {rc}"}
    rc, head, err = evidence.run_git(project_dir, "rev-parse", "--verify", "--quiet", "HEAD")
    if rc != 0 or not head:
        return {"branch": branch, "error": err or "HEAD does not name a commit"}
    rc, tip, _err = evidence.run_git(
        project_dir, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}^{{commit}}"
    )
    tip = tip if rc == 0 and tip else None
    if tip is None:
        recovery = f"git switch -c {branch}"
        contains = True
    elif tip == head:
        recovery = f"git switch {branch}"
        contains = True
    else:
        rc, _out, _err = evidence.run_git(project_dir, "merge-base", "--is-ancestor", tip, head)
        contains = rc == 0
        recovery = (
            f"git branch -f {branch} HEAD && git switch {branch}" if contains
            else f"git switch {branch}"
        )
    return {"branch": branch, "head": head, "tip": tip, "contains_tip": contains, "recovery": recovery}


def message(left: dict) -> str:
    """One loud sentence for a :func:`left_branch` answer."""
    branch = left["branch"]
    if "error" in left:
        return (
            f"HEAD CHECK FAILED: could not tell whether HEAD is still on `{branch}` "
            f"({left['error']}); run `git status` before committing."
        )
    head = left["head"][:12]
    said = (
        f"HEAD LEFT BRANCH `{branch}`: the checkout is detached at {head}, so a commit "
        f"made now lands on no branch and a push sends the stale `{branch}`. "
    )
    if left["contains_tip"]:
        return said + f"Recover, keeping every commit: `{left['recovery']}`."
    return said + (
        f"HEAD does not contain `{branch}`'s tip, so the branch is not moved: "
        f"`{left['recovery']}`, then carry over any commit made on the detached HEAD "
        f"from {head} (`git log {left['tip'][:12]}..{head}` lists them)."
    )
