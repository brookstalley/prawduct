"""Which work unit a checkout is working on — one owner, three answers.

A live build plan **claims** the branch it governs (frontmatter ``branch:``), and
may name working branches that merge into it (``working-branches:``). A checkout
is **bound** to the one live plan claiming its branch, **unbound** when no plan
claims it, and **broken** when the claim cannot be decided: two live plans claim
it, or a live plan cannot be read. Unbound is a normal state: chores, small
fixes, integration and release branches. It never borrows another plan.

Every consumer takes the :class:`Binding` this module computes, not a walker of
its own. A second resolver composing the same routes a different way is how a
review gets graded against — and a ledger event attributed to — a plan the
branch has nothing to do with, with nothing on the surface to say so. A fallback
that *can* look right while being wrong is what this module has none of
(``1050-requirements.md`` BR1–BR6).

**A binding is authority, so it fails closed** (``architecture.md`` § Direction).
A live plan whose frontmatter does not close, whose ``branch:`` is not one
branch name, whose ``working-branches:`` is not a list of them, or which cannot
be read at all, might claim this branch — and so the answer is ``broken``,
naming the file and what could not be read, until the file is repaired.
Skipping it would resolve as though the plan were absent, which disarms the
gates exactly when the state is malformed. Only a file that could hold a claim
breaks it, though: one named like a plan, named by the pointer, or at the
conventional path. ``artifacts/`` is also where the repo's other documents
live, and an unreadable note is not a plan. The natural encoding variants are
read, not refused: ``working-branches: [a, b]`` means what the block form means.

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
served to another, and a pointer-only plan is named in ``reason`` with the
command that binds it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, NamedTuple

from . import core, gitstate, plan_index

#: Frontmatter key naming the branches that merge INTO a unit's integration
#: branch (``branch:``) and never into the base directly. A sequence of plain
#: strings, block or flow style; ``[]`` and absence both mean none.
WORKING_BRANCHES_KEY = "working-branches"

#: The advisory a legacy-window binding raises. Carried in ``Binding.reason`` so
#: the surface that renders the binding and the surface that registers the
#: advisory agree on the name without either importing the other.
LEGACY_ADVISORY_KEY = "plan-unbound-legacy"

#: The filename prefix that marks a plan with no frontmatter to say so — the
#: same convention ``plan_index.iter_live_plan_files`` falls back on.
PLAN_NAME_PREFIX = "build-plan"

#: The command that ends a plan's legacy window, named in the reason so the
#: remedy travels with the diagnosis.
BIND_COMMAND = "prawduct-hook plan bind"

State = Literal["bound", "unbound", "broken"]
Role = Literal["integration", "working"]
ChosenBy = Literal["binding", "legacy-pointer", "legacy-default", "none"]

#: Which branch of :func:`resolve` produced the answer — the discriminant a
#: consumer dispatches on, so none has to recover it from ``reason`` prose or
#: re-spell a ``chosen_by`` comparison. Every value is emitted by exactly one
#: route below (``tests/test_work_unit.py`` pins the set against the source):
#:
#: - ``claim`` — bound: one live plan claims the branch (``role`` says whether
#:   as its integration or a working branch);
#: - ``legacy-pointer`` / ``legacy-default`` — bound through the legacy window,
#:   by the ``active_build_plan`` pointer or the conventional path;
#: - ``no-claim`` — unbound: no live plan claims the branch (the window is shut,
#:   or no plan exists for it to serve);
#: - ``pointer-dangling`` — unbound: inside the window, the pointer names a file
#:   that is not a live plan;
#: - ``scratch-worktree``, ``detached-head``, ``no-work-tree`` — unbound before
#:   any plan is read: no branch can be claimed;
#: - ``two-claimants`` / ``unreadable-plan`` — broken: rival claims, or a live
#:   plan whose claim cannot be read.
Case = Literal[
    "claim",
    "legacy-pointer",
    "legacy-default",
    "no-claim",
    "pointer-dangling",
    "scratch-worktree",
    "detached-head",
    "no-work-tree",
    "two-claimants",
    "unreadable-plan",
]

#: The cases in which the legacy window answered.
LEGACY_CASES: frozenset[str] = frozenset({"legacy-pointer", "legacy-default"})

#: The route each bound case records as ``chosen_by``; every other case is
#: ``none``. ``chosen_by`` is derived from the case here, once, so the two
#: cannot disagree on a binding :func:`resolve` built.
_CHOSEN_BY: dict[str, ChosenBy] = {
    "claim": "binding",
    "legacy-pointer": "legacy-pointer",
    "legacy-default": "legacy-default",
}


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
    ``claimants`` are the plans the answer is about: the one plan when
    ``bound``, every plan involved when ``broken`` (the rival claimants, or the
    files that could not be read), none when ``unbound``.
    ``case`` is the :data:`Case` that answered — what a consumer dispatches on
    (``None`` only on a ``Binding`` built by hand, never on one :func:`resolve`
    returns). ``base`` is the bound plan's ``base:`` — the branch the unit's
    integration branch merges into — or ``None`` when it declares none or
    nothing is bound.
    """

    state: State
    scope: str | None
    plan_path: Path | None
    role: Role | None
    reason: str | None
    chosen_by: ChosenBy
    claimants: tuple[Path, ...] = ()
    case: Case | None = None
    base: str | None = None

    @property
    def is_legacy(self) -> bool:
        """Bound through the legacy window — a plan served without a claim."""
        return self.case in LEGACY_CASES

    @property
    def is_claim(self) -> bool:
        """Bound because a live plan claims this branch — nothing assumed."""
        return self.case == "claim"


def repo_rel(path: Path | str, project_dir: Path | str, *, within: str = "") -> str:
    """``path`` as a person reads it: relative to the repo root (or to
    ``within`` under it, e.g. ``.prawduct/artifacts``), POSIX-spelled.

    The one display rule for a binding's paths. Both sides are resolved: a
    :class:`Binding`'s paths are, and a project dir reached through a symlink
    is not, so a consumer comparing them unresolved falls to its fallback on
    exactly the checkouts where that matters. A path outside the root is shown
    absolute — it still identifies the file, which a bare name does not.
    """
    target = Path(path).resolve()
    root = Path(project_dir).resolve()
    if within:
        root = root / within
    try:
        return target.relative_to(root).as_posix()
    except ValueError:
        return target.as_posix()


class _Declaration(NamedTuple):
    """What one live plan says about itself: identity, claim, working branches."""

    path: Path
    scope: str | None
    branch: str | None
    working: tuple[str, ...]
    base: str | None = None


class _Unreadable(NamedTuple):
    """One live plan the resolver could not read, and what it could not read."""

    path: Path
    what: str


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
    2. Every live plan is read once. One that cannot be read — no closing
       frontmatter, a ``branch:`` that is not one name, a ``working-branches:``
       that is not a list, or bytes that are not text — makes the binding
       ``broken``: whether it claims this branch is unknown, so nothing below
       runs on the assumption that it does not.
    3. The claimants are the live plans whose ``branch:`` is this branch (role
       ``integration``) or whose working branches contain it (role ``working``).
    4. One claimant binds. Two or more is broken — reported, never resolved by
       precedence (BR5); it arises only from merging two claiming branches,
       since minting refuses a second claim. A claimant that declares no
       ``scope:`` still binds, with ``scope=None`` and a ``reason`` naming the
       omission: that plan governs its branch today, and nothing is
       reinterpreted until the repo migrates (MG1) — ``broken`` would change
       what its gates do, and ``unbound`` would disarm them.
    5. With no claimant, the legacy window: only while *no* live plan in the
       repo declares a branch, the pointer or the conventional path names a
       live plan that itself declares none. Anything else is unbound, and when
       a pointer names a plan that could be bound, ``reason`` says how.

    Never raises (lib convention): a failed git probe reads as no branch, and a
    plan that cannot be read is reported, not thrown.
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
            "scratch-worktree",
            f"a harness scratch worktree ({kind}) is unbound by construction — "
            "it builds, its coordinator governs",
        )
    if branch is None:
        if gitstate.git_common_dir(project_dir) is None:
            return _unbound(
                "no-work-tree", "not inside a git work tree, so no branch can be claimed"
            )
        return _unbound("detached-head", "HEAD is detached, so no branch can be claimed")

    prawduct_dir = project_dir / ".prawduct"
    artifacts_dir = prawduct_dir / "artifacts"
    declarations, unreadable = live_declarations(prawduct_dir, artifacts_dir)

    if unreadable:
        faults = "; ".join(
            f"{plan_index.display_path(u.path, artifacts_dir)} ({u.what})" for u in unreadable
        )
        return _broken(
            "unreadable-plan",
            f"{len(unreadable)} live plan{'s' if len(unreadable) > 1 else ''} cannot be read "
            f"— {faults} — so whether it claims `{branch}` is unknown and no binding "
            "can be decided; repair the file",
            tuple(u.path for u in unreadable),
        )

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
            "two-claimants",
            f"{len(claimants)} live plans claim `{branch}` ({names}) — a branch "
            "has one unit; archive or re-bind all but one",
            tuple(d.path for d, _ in claimants),
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
        return _bound("claim", decl.scope, decl.path, role, reason, decl.base)

    if any(d.branch is not None for d in declarations):
        # A claim exists somewhere in this repo, so claims are how its plans
        # bind; the demoted routes answer nothing here. A pointer-only plan is
        # named with its remedy, because "no plan claims" alone reads as "no
        # plan exists" to the operator who still has one.
        return _unbound(
            "no-claim", _closed_window_reason(prawduct_dir, artifacts_dir, branch, declarations)
        )
    return _legacy(prawduct_dir, artifacts_dir, branch)


def _closed_window_reason(
    prawduct_dir: Path, artifacts_dir: Path, branch: str, declarations: list[_Declaration]
) -> str:
    """Why an unclaimed branch is unbound in a repo that binds by claims.

    When the pointer or the default names a live plan that declares no branch,
    the operator has a plan the window would have served and the sentence says
    how to bind it. No file is read: the plan, if live, is already among the
    declarations.
    """
    base = f"no live plan claims `{branch}`"
    pointer = core.pointer_plan_path(prawduct_dir)
    candidate = core.fallback_plan_path(prawduct_dir).resolve()
    named = next((d for d in declarations if d.path.resolve() == candidate), None)
    if named is None or named.branch is not None:
        return base
    route = "`active_build_plan`" if pointer is not None else "the conventional path"
    rel = plan_index.display_path(named.path, artifacts_dir)
    return (
        f"{base} — {route} names {rel}, which declares no `branch:` and binds nothing "
        f"once any plan in the repo claims one; if this branch builds it, run "
        f"`{BIND_COMMAND} {rel} --branch {branch}`"
    )


def _legacy(prawduct_dir: Path, artifacts_dir: Path, branch: str) -> Binding:
    """Step 5: the pointer or the default, for a repo with no claims at all.

    The named file must be a live plan: under ``artifacts/`` and outside every
    ``archive`` component, present, readable, and not declaring itself some
    other artifact. It is read only after the archive test, so an archived plan
    the pointer still names costs no read and governs nothing. The "declares no
    ``branch:``" half is already true here — the caller established that no
    live plan declares one — and is re-read anyway, because this is the one
    route that could serve a plan the walk never saw.
    """
    pointer = core.pointer_plan_path(prawduct_dir)
    case: Case = "legacy-pointer" if pointer is not None else "legacy-default"
    plan_path = core.fallback_plan_path(prawduct_dir)
    # A missing conventional file is the ordinary unbound; a pointer naming
    # nothing it may serve is a declaration nobody honours, and says so.
    unserved: Case = "pointer-dangling" if pointer is not None else "no-claim"
    if not _is_live_plan_file(plan_path, artifacts_dir):
        return _unbound(unserved, _dangling_pointer_reason(prawduct_dir, pointer, branch))
    try:
        content = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return _unbound(unserved, _dangling_pointer_reason(prawduct_dir, pointer, branch))
    if not plan_index.is_build_plan(content):
        return _unbound(unserved, _dangling_pointer_reason(prawduct_dir, pointer, branch))
    if plan_index.parse_build_plan_frontmatter_branch(content) is not None:
        # Unreachable while `live_declarations` saw this file; kept so the
        # rule holds even for a plan the walk did not yield.
        return _unbound("no-claim", f"no live plan claims `{branch}`")
    _present, scope = plan_index.parse_build_plan_frontmatter_scope(content)
    route = "`active_build_plan`" if pointer is not None else "the conventional path"
    rel = plan_index.display_path(plan_path, artifacts_dir)
    return _bound(
        case,
        scope,
        plan_path,
        None,
        f"{LEGACY_ADVISORY_KEY}: {rel} governs `{branch}` through {route} and "
        f"declares no `branch:` — run `{BIND_COMMAND} {rel} --branch {branch}`",
        plan_index.parse_build_plan_frontmatter_base(content),
    )


def _dangling_pointer_reason(prawduct_dir: Path, pointer: Path | None, branch: str) -> str:
    """Unbound because the legacy route named nothing it may serve.

    A missing conventional file is the ordinary unbound and says only that. A
    pointer that names a file which is missing, archived, unreadable or not a
    plan is a declaration the operator wrote and nothing honours, so the
    sentence names the path it resolved to and both remedies.
    """
    base = f"no live plan claims `{branch}`"
    if pointer is None:
        return base
    try:
        shown = str(pointer.relative_to(prawduct_dir))
    except ValueError:
        shown = str(pointer)
    return (
        f"{base} — `active_build_plan` names {shown}, which is not a live plan "
        f"file; point it at one, or bind the plan this branch builds with "
        f"`{BIND_COMMAND} <plan> --branch {branch}`"
    )


def live_declarations(
    prawduct_dir: Path, artifacts_dir: Path
) -> tuple[list[_Declaration], list[_Unreadable]]:
    """Every live plan's identity, claim and working branches — and every live
    plan that could not be read, kept apart so the caller can refuse to decide.

    One walk over every live markdown file, each read once. A file declaring
    itself some other artifact is excluded on its own word. A file with no
    frontmatter declares nothing and is kept with no identity and no claim:
    the legacy route may still serve it.

    What cannot be read is returned as unreadable — never skipped, because a
    skipped plan resolves exactly as an absent one would, and absence is what
    arms nothing — but only when the file COULD hold a claim. A file whose
    text or frontmatter cannot be read says nothing about what it is, so the
    tell is where it sits: a plan-named file (``build-plan*.md``), the file the
    pointer names, or the conventional path. ``artifacts/`` also holds the
    repo's architecture docs and discovery notes, some opening with a ``---``
    rule; one bad byte in any of those must not fail every checkout closed. A
    readable block whose ``branch:`` or ``working-branches:`` is not the shape
    the reader reads is claim-bearing by its own content and is unreadable
    whatever the file is called.
    """
    declarations: list[_Declaration] = []
    unreadable: list[_Unreadable] = []
    legacy_target = core.fallback_plan_path(prawduct_dir).resolve()

    def can_hold_claim(path: Path) -> bool:
        return path.name.startswith(PLAN_NAME_PREFIX) or path.resolve() == legacy_target

    for path in plan_index.live_markdown_files(artifacts_dir):
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            if can_hold_claim(path):
                unreadable.append(_Unreadable(path, "not UTF-8 text"))
            continue
        except OSError as exc:
            if can_hold_claim(path):
                unreadable.append(_Unreadable(path, exc.strerror or type(exc).__name__))
            continue
        if not plan_index.is_build_plan(content):
            continue
        fm = plan_index.frontmatter_lines(content)
        if fm is None:
            if not _frontmatter_unterminated(content):
                declarations.append(_Declaration(path, None, None, ()))
            elif can_hold_claim(path):
                unreadable.append(_Unreadable(path, "its frontmatter block never closes"))
            continue
        branch_fault = _branch_claim_fault(fm)
        if branch_fault is not None:
            unreadable.append(_Unreadable(path, branch_fault))
            continue
        working = _working_branches(fm)
        if working is None:
            unreadable.append(
                _Unreadable(path, f"`{WORKING_BRANCHES_KEY}:` is not a list of branch names")
            )
            continue
        _present, scope = plan_index.parse_build_plan_frontmatter_scope(content)
        declarations.append(
            _Declaration(
                path,
                scope,
                plan_index.parse_build_plan_frontmatter_branch(content),
                working,
                plan_index.parse_build_plan_frontmatter_base(content),
            )
        )
    return declarations, unreadable


# The pre-#1051 private name, kept one release for any out-of-tree caller that
# imported it (the hook's `plan check-claims` reads `live_declarations`). Delete
# in the release after 3.7.x.
_live_declarations = live_declarations


def _frontmatter_unterminated(content: str) -> bool:
    """Whether the document opens a frontmatter block it never closes.

    The block walker reads that as "no frontmatter" so a map degrades instead of
    failing; an authority must tell the two apart, because a plan whose
    ``branch:`` sits in an unclosed block has a claim nobody can read.
    """
    lines = content.splitlines()
    start = plan_index.frontmatter_body_start(lines)
    return start < len(lines) and lines[start].strip() == "---"


def _inline_value(frontmatter: list[str], key: str) -> tuple[int, str] | None:
    """``(index, inline value)`` of the column-0 ``key:`` line, comment stripped."""
    needle = f"{key}:"
    for index, line in enumerate(frontmatter):
        if line[:1] in (" ", "\t"):
            continue
        stripped = core.strip_scalar_comment(line)
        if stripped.startswith(needle):
            return index, stripped[len(needle):].strip()
    return None


def _branch_claim_fault(frontmatter: list[str]) -> str | None:
    """What is wrong with ``branch:`` when it is not one branch name, else ``None``.

    The scalar reader returns a string for a flow collection and ``None`` for a
    block beneath the key; both would resolve — one as a claim on a branch
    named ``[a, b]``, the other as no claim — when the author wrote something
    the reader has no meaning for.
    """
    found = _inline_value(frontmatter, plan_index.BRANCH_KEY)
    if found is None:
        return None
    index, value = found
    if value[:1] in ("[", "{"):
        return f"`{plan_index.BRANCH_KEY}:` is not a single branch name"
    if not value:
        for follow in frontmatter[index + 1:]:
            if not core.strip_scalar_comment(follow):
                continue
            if follow[:1] in (" ", "\t"):
                return f"`{plan_index.BRANCH_KEY}:` is not a single branch name"
            break
    return None


def _working_branches(frontmatter: list[str]) -> tuple[str, ...] | None:
    """The ``working-branches:`` sequence, ``()`` for none, ``None`` when unreadable.

    Block style and flow style (``[a, b]``) are the same declaration and read
    the same; anything else — a nested mapping, a bare dash, a scalar — is
    unreadable, never a partial list: a branch silently dropped from the list
    is a working branch silently unbound.
    """
    text = "\n".join(frontmatter)
    status, items = core.read_block_sequence(text, WORKING_BRANCHES_KEY)
    if status == core.YAML_DECLARED:
        return items
    if status == core.YAML_ABSENT:
        return ()
    found = _inline_value(frontmatter, WORKING_BRANCHES_KEY)
    if found is None:
        return None
    return _flow_sequence(found[1])


def _flow_sequence(value: str) -> tuple[str, ...] | None:
    """``[a, "b"]`` as a tuple of plain strings, or ``None`` for any other shape."""
    if len(value) < 2 or value[0] != "[" or value[-1] != "]":
        return None
    inner = value[1:-1].strip()
    if not inner:
        return ()
    items: list[str] = []
    for raw in inner.split(","):
        item = core.unquote_scalar(raw.strip())
        if not item or any(ch in item for ch in "[]{},:\"'"):
            return None
        items.append(item)
    return tuple(items)


def _is_live_plan_file(path: Path, artifacts_dir: Path) -> bool:
    """Under ``artifacts/``, outside every ``archive`` component, and a file."""
    try:
        rel = path.resolve().relative_to(artifacts_dir.resolve())
    except ValueError:
        return False
    if plan_index.ARCHIVE_DIR_NAME in rel.parts:
        return False
    return path.is_file()


def _bound(
    case: Case,
    scope: str | None,
    plan_path: Path,
    role: Role | None,
    reason: str | None,
    base: str | None,
) -> Binding:
    return Binding(
        "bound", scope, plan_path, role, reason, _CHOSEN_BY[case], (plan_path,), case, base
    )


def _unbound(case: Case, reason: str) -> Binding:
    return Binding("unbound", None, None, None, reason, "none", (), case)


def _broken(case: Case, reason: str, claimants: tuple[Path, ...]) -> Binding:
    return Binding("broken", None, None, None, reason, "none", claimants, case)
