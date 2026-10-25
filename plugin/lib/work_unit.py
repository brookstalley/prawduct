"""Which work unit a checkout is working on — one owner, three answers.

A live build plan **claims** the branch it governs (frontmatter ``branch:``), and
may name working branches that merge into it (``working-branches:``). A checkout
is **bound** to the one live plan claiming its branch, **unbound** when no plan
claims it, and **broken** when two live plans claim it. Unbound is a normal
state: chores, small fixes, integration and release branches. It never borrows
another plan.

Every consumer takes the :class:`Binding` this module computes, not a walker of
its own. The two resolvers it replaces composed four routes two different ways,
and when they disagreed a review was graded against — and a ledger event
attributed to — a plan the branch had nothing to do with, with nothing on the
surface to say so. A fallback that *can* look right while being wrong is what
this module has none of (``1050-requirements.md`` BR1–BR6).

Two things a binding never is: typed, and read from history. The answer is
computed from the plan files and git, so the fact a gate or ledger writes from it
is what code resolved (``data-model.md``: no model in a fact's write path). The
archive is never descended — an archived plan's claim ended when it was archived,
and the walk runs at every session boundary (``plan_index`` prunes it at
directory level). No network.

**Legacy window.** A repo whose plans predate claims has a pointer
(``active_build_plan``) or the conventional ``artifacts/build-plan.md`` and no
``branch:`` anywhere. Such a plan still governs — ``chosen_by`` says it was the
pointer or the default that answered, and ``reason`` carries the
:data:`LEGACY_ADVISORY_KEY` so the briefing can say how to bind it. The moment
any live plan in the repo declares a branch, the window closes for that repo and
the demoted routes answer nothing: a plan that declares *some* branch is never
served to another.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, NamedTuple

from . import core, gitstate, plan_index

#: Frontmatter key naming the branches that merge INTO a unit's integration
#: branch (``branch:``) and never into the base directly. A block sequence of
#: plain strings; ``[]`` and absence both mean none.
WORKING_BRANCHES_KEY = "working-branches"

#: The advisory a legacy-window binding raises. Carried in ``Binding.reason`` so
#: the surface that renders the binding and the surface that registers the
#: advisory agree on the name without either importing the other.
LEGACY_ADVISORY_KEY = "plan-unbound-legacy"

#: The command that ends a plan's legacy window, named in the reason so the
#: remedy travels with the diagnosis.
BIND_COMMAND = "prawduct-hook plan bind"

State = Literal["bound", "unbound", "broken"]
Role = Literal["integration", "working"]
ChosenBy = Literal["binding", "legacy-pointer", "legacy-default", "none"]


@dataclass(frozen=True)
class Binding:
    """The answer to "which unit, and which plan, is this checkout working on".

    ``plan_path`` is set only when ``state`` is ``bound``, and so is ``scope``
    — unless the bound plan declares none, which a pre-identity plan may.
    ``role`` says which of the unit's branch kinds the checkout is, and is
    ``None`` for a legacy binding, which declared no branch to have a kind.
    ``reason`` is one sentence for the briefing: why the checkout is unbound or
    broken, or what a binding still lacks — the advisory key and the remedy for
    a legacy binding, the missing ``scope:`` for a claimant without one. It is
    ``None`` only for a binding with nothing to explain.
    """

    state: State
    scope: str | None
    plan_path: Path | None
    role: Role | None
    reason: str | None
    chosen_by: ChosenBy


class _Declaration(NamedTuple):
    """What one live plan says about itself: identity, claim, working branches."""

    path: Path
    scope: str | None
    branch: str | None
    working: tuple[str, ...]


def resolve(project_dir: Path, *, branch: str | None = None) -> Binding:
    """The :class:`Binding` for the checkout at ``project_dir``.

    ``project_dir`` is the work-tree root (the parent of ``.prawduct/``). The
    branch is probed from git unless ``branch`` is given — a caller that has
    already read it passes it, and no second subprocess runs. The scratch-tree
    test is made against that branch through the same decision function the
    ephemeral guard uses, so the resolver and the guard agree about one tree.

    1. A detached HEAD, a directory outside any work tree, or a harness scratch
       worktree is unbound, and ``reason`` names which. A scratch tree builds
       and its coordinator governs: it resolves no unit, owes no review, writes
       no fact (BR6).
    2. The claimants are the live plans whose ``branch:`` is this branch (role
       ``integration``) or whose working branches contain it (role ``working``).
    3. One claimant binds. Two or more is broken — reported, never resolved by
       precedence (BR5); it arises only from merging two claiming branches,
       since minting refuses a second claim. A claimant that declares no
       ``scope:`` still binds, with ``scope=None`` and a ``reason`` naming the
       omission: that plan governs its branch today, and nothing is
       reinterpreted until the repo migrates (MG1) — ``broken`` would change
       what its gates do, and ``unbound`` would disarm them.
    4. With no claimant, the legacy window: only while *no* live plan in the
       repo declares a branch, the pointer or the conventional path names a
       live plan that itself declares none. Anything else is unbound.

    Never raises (lib convention): an unreadable plan is skipped the way every
    other reader skips it, and a failed git probe reads as no branch.
    """
    project_dir = Path(project_dir).resolve()
    if branch is None:
        branch = gitstate.current_branch(project_dir)
    # Scratch first, with the branch already in hand: `ephemeral_kind_of` is the
    # one body that decides disposability, and for an `agent-` path a missing
    # branch is the restrictive answer, so a detached scratch tree reads as
    # scratch — the more useful of its two true descriptions.
    kind = gitstate.ephemeral_kind_of(project_dir, branch)
    if kind is not None:
        return _unbound(
            f"a harness scratch worktree ({kind}) is unbound by construction — "
            "it builds, its coordinator governs"
        )
    if branch is None:
        if gitstate.git_common_dir(project_dir) is None:
            return _unbound("not inside a git work tree, so no branch can be claimed")
        return _unbound("HEAD is detached, so no branch can be claimed")

    prawduct_dir = project_dir / ".prawduct"
    artifacts_dir = prawduct_dir / "artifacts"
    declarations = _live_declarations(artifacts_dir)

    claimants: list[tuple[_Declaration, Role]] = []
    for decl in declarations:
        if decl.branch == branch:
            claimants.append((decl, "integration"))
        elif branch in decl.working:
            claimants.append((decl, "working"))

    if len(claimants) > 1:
        names = ", ".join(
            plan_index.display_path(d.path, artifacts_dir) for d, _ in claimants
        )
        return _broken(
            f"{len(claimants)} live plans claim `{branch}` ({names}) — a branch "
            "has one unit; archive or re-bind all but one"
        )
    if len(claimants) == 1:
        decl, role = claimants[0]
        reason = None
        if decl.scope is None:
            reason = (
                f"{plan_index.display_path(decl.path, artifacts_dir)} claims "
                f"`{branch}` but declares no `scope:`, so facts about this work "
                "record no unit — add one"
            )
        return Binding("bound", decl.scope, decl.path, role, reason, "binding")

    if any(d.branch is not None for d in declarations):
        # A claim exists somewhere in this repo, so claims are how its plans
        # bind; the demoted routes answer nothing here.
        return _unbound(f"no live plan claims `{branch}`")
    return _legacy(prawduct_dir, artifacts_dir, branch)


def _legacy(prawduct_dir: Path, artifacts_dir: Path, branch: str) -> Binding:
    """Step 4: the pointer or the default, for a repo with no claims at all.

    The named file must be a live plan: under ``artifacts/`` and outside every
    ``archive`` component, present, readable, and not declaring itself some
    other artifact. It is read only after the archive test, so an archived plan
    the pointer still names costs no read and governs nothing. The "declares no
    ``branch:``" half is already true here — the caller established that no
    live plan declares one — and is re-read anyway, because this is the one
    route that could serve a plan the walk never saw.
    """
    pointer = core.pointer_plan_path(prawduct_dir)
    chosen_by: ChosenBy = "legacy-pointer" if pointer is not None else "legacy-default"
    plan_path = core.fallback_plan_path(prawduct_dir)
    if not _is_live_plan_file(plan_path, artifacts_dir):
        return _unbound(f"no live plan claims `{branch}`")
    try:
        content = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return _unbound(f"no live plan claims `{branch}`")
    if not plan_index.is_build_plan(content):
        return _unbound(f"no live plan claims `{branch}`")
    if plan_index.parse_build_plan_frontmatter_branch(content) is not None:
        # Unreachable while `_live_declarations` saw this file; kept so the
        # rule holds even for a plan the walk did not yield.
        return _unbound(f"no live plan claims `{branch}`")
    _present, scope = plan_index.parse_build_plan_frontmatter_scope(content)
    route = "`active_build_plan`" if pointer is not None else "the conventional path"
    rel = plan_index.display_path(plan_path, artifacts_dir)
    return Binding(
        "bound",
        scope,
        plan_path,
        None,
        f"{LEGACY_ADVISORY_KEY}: {rel} governs `{branch}` through {route} and "
        f"declares no `branch:` — run `{BIND_COMMAND} {rel} --branch {branch}`",
        chosen_by,
    )


def _live_declarations(artifacts_dir: Path) -> list[_Declaration]:
    """Every live plan's identity, claim and working branches, one read each.

    Two discoverers, because they find different things and both matter: the
    scope walk finds plans with an identity, and the claim walk finds plans that
    claim a branch. A plan in the second set and not the first is the claimant
    without a ``scope:`` that step 3 binds with a reason — found by one walker
    only, it would be silently unbound. Both prune the archive at directory level.
    """
    paths: set[Path] = {p for p, _ in plan_index.iter_scoped_plan_candidates(artifacts_dir)}
    paths.update(p for p, _ in plan_index.branch_claiming_plans(artifacts_dir))
    declarations: list[_Declaration] = []
    for path in sorted(paths):
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue  # one unreadable plan must not blind the resolver to the rest
        fm = plan_index.frontmatter_lines(content)
        if fm is None:
            continue
        _present, scope = plan_index.parse_build_plan_frontmatter_scope(content)
        declarations.append(
            _Declaration(
                path,
                scope,
                plan_index.parse_build_plan_frontmatter_branch(content),
                _working_branches(fm),
            )
        )
    return declarations


def _working_branches(frontmatter: list[str]) -> tuple[str, ...]:
    """The ``working-branches:`` sequence, or none.

    An unparseable declaration (flow style, a nested mapping) reads as none
    rather than as a partial list — a branch silently dropped from the list is
    a working branch silently unbound, and the plan's author will see the
    refusal at minting, where the writer validates the shape.
    """
    status, items = core.read_block_sequence("\n".join(frontmatter), WORKING_BRANCHES_KEY)
    return items if status == core.YAML_DECLARED else ()


def _is_live_plan_file(path: Path, artifacts_dir: Path) -> bool:
    """Under ``artifacts/``, outside every ``archive`` component, and a file."""
    try:
        rel = path.resolve().relative_to(artifacts_dir.resolve())
    except ValueError:
        return False
    if plan_index.ARCHIVE_DIR_NAME in rel.parts:
        return False
    return path.is_file()


def _unbound(reason: str) -> Binding:
    return Binding("unbound", None, None, None, reason, "none")


def _broken(reason: str) -> Binding:
    return Binding("broken", None, None, None, reason, "none")
