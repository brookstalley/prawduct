"""Minting a work unit's identity, and binding a branch to it — the writer side.

A unit's identity is its plan's ``scope:``. It is minted once, by :func:`new`,
which writes it to the plan and the change fragment in one act, so neither can
spell it differently from the other (WU1), and the plan claims its branch in
the same act, so the binding exists from the moment the work does (BR2) rather
than whenever someone remembers to add it. :func:`bind` gives an existing live
plan its claim — the migration path out of the legacy window — and
``new(..., working=True)`` adds a working branch to a bound unit.

``lib.work_unit`` is the reader; everything written here is in the exact form
its ``resolve()`` parses, and each write is read back through the same parsers
before it lands, so a value the reader would see differently is refused rather
than written. Two refusals exist only because of the reader's rules: a second
claim on a branch (two claimants are ``broken``, so minting never makes one),
and the harness scratch pattern (a scratch tree is unbound by construction, so
a claim on one would govern nothing).

Branch names are never read as identities here. :func:`suggest_scope` turns
one into a candidate slug for a person to confirm (D3); nothing calls it to
decide anything.

Refusals raise :class:`PlanMintRefused` with a stable ``code``, before anything
is written. No CLI here — ``prawduct-hook plan new|bind`` is wired separately.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from datetime import date as _date
from pathlib import Path
from typing import Literal

from . import change_fragments, core, gitstate, plan_index, work_unit

ARTIFACTS_REL = ".prawduct/artifacts"
STATE_REL = ".prawduct/project-state.yaml"

#: The keys this module owns in a plan's frontmatter, in the order it writes them.
#: ``base:`` is where the unit's integration branch merges — read back through
#: the binding as the unit's diff base (``coverage._resolve_base_branch``).
BASE_KEY = plan_index.BASE_KEY
_IDENTITY_KEYS = ("scope", plan_index.BRANCH_KEY, BASE_KEY, work_unit.WORKING_BRANCHES_KEY)

#: The fallback when neither the repo's knob nor git names an integration branch:
#: the head of the family the base resolver itself falls back to.
_FALLBACK_BASE = "main"

#: Prefixes a branch name carries for its KIND of work, not its identity —
#: stripped before a name is offered as a scope.
_KIND_PREFIXES = frozenset({
    "feature", "feat", "fix", "bugfix", "hotfix", "chore", "docs", "refactor", "perf",
    "governance", "wip", "topic",
})

Action = Literal["minted", "working", "bound", "unchanged"]


class PlanMintRefused(Exception):
    """The mint or bind cannot proceed; nothing was written. ``code`` names the reason."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class MintResult:
    """What a mint, a working-branch join or a bind did.

    ``base_rule`` says which rule chose ``base`` — ``given``, ``base_branch``
    (``project-state.yaml``), ``origin-head`` / ``main-family`` (what git says the
    remote integrates onto), or ``fallback`` — because a default the operator
    cannot see the reason for is one they cannot check. ``None`` when nothing
    chose a base (a join or a bind). ``created_branch`` is true when the call
    created the branch and checked it out.
    """

    action: Action
    scope: str | None
    branch: str
    plan_path: Path
    fragment_path: Path | None = None
    base: str | None = None
    base_rule: str | None = None
    created_branch: bool = False


# ---------------------------------------------------------------------------
# Known scopes — what "taken" means
# ---------------------------------------------------------------------------


def known_scopes(project_dir: Path) -> set[str] | None:
    """Every scope this repo has ever declared, or ``None`` when its history is unreadable.

    A scope is declared by a plan (live or archived — WU4: archiving never frees
    an identity), by a pending fragment (its filename is its scope), or by an
    entry in the change history (the live log and the archive), which is where a
    shipped fragment and every pre-fragment record went. ``None`` is not "none":
    callers that must not reuse an identity refuse on it, since an unreadable
    history can hold the very scope being minted.
    """
    from . import change_log as change_log_mod  # noqa: PLC0415 — lazy; only identity checks read history
    from . import change_log_archive  # noqa: PLC0415 — lazy, for the same reason

    project_dir = Path(project_dir)
    plans = change_fragments.plan_scopes_for(project_dir)
    scopes = set(plans)
    directory = project_dir / change_fragments.FRAGMENT_DIR_REL
    if directory.is_dir():
        for path in directory.glob("*.md"):
            scopes.add(path.stem)
            item = change_fragments.read_fragment_file(path, plan_scopes=plans)
            if item.fragment is not None and item.fragment.scope:
                scopes.add(item.fragment.scope)
    text = change_log_archive.load_all_text(project_dir / ".prawduct")
    if text is None:
        return None
    scopes.update(
        e.tags["scope"]
        for e in change_log_mod.parse_change_log(text)
        if isinstance(e.tags.get("scope"), str)
    )
    return scopes


def integration_branches(project_dir: Path | None) -> frozenset[str]:
    """Branches that are never a unit's: the ``main`` family (``coverage``'s one
    roster) plus this repo's own integration branch (:func:`default_base`).
    Without a repo to ask, the family alone."""
    from . import coverage  # noqa: PLC0415 — lazy; only scope suggestion and minting need it

    if project_dir is None:
        return coverage.MAIN_FAMILY
    return coverage.MAIN_FAMILY | {default_base(Path(project_dir))[0]}


def suggest_scope(branch: str | None, project_dir: Path | None = None) -> str | None:
    """A candidate scope from a branch name, for a person to confirm — never a binding.

    The one surviving use of name inference (D3), and its consumer is
    ``prawduct-hook plan new`` with the scope omitted, which prints what it
    took. Drops the kind prefix (``feature/``) and a leading issue number (an
    issue is a ``closes:`` reference, never the identity — D5), then folds what
    is left onto the slug rule. ``None`` for a branch that is never a unit's
    (:func:`integration_branches` for ``project_dir``, a release branch, a
    harness scratch branch) or that leaves nothing legal.
    """
    if not branch:
        return None
    if branch in integration_branches(project_dir) or gitstate.is_scratch_branch(branch):
        return None
    parts = [p for p in branch.split("/") if p]
    if parts and parts[0].casefold() == "release":
        return None
    while len(parts) > 1 and parts[0].casefold() in _KIND_PREFIXES:
        parts = parts[1:]
    name = "-".join(parts).casefold()
    name = re.sub(r"^\d+[-_]+(?=.)", "", name)  # a leading issue number is not the unit
    name = re.sub(r"[^a-z0-9.]+", "-", name)
    name = re.sub(r"\.{2,}", ".", name)
    name = re.sub(r"-{2,}", "-", name).strip("-.")
    return name if name and change_fragments.is_scope(name) else None


# ---------------------------------------------------------------------------
# Public writers
# ---------------------------------------------------------------------------


def new(
    project_dir: Path,
    scope: str,
    *,
    branch: str | None = None,
    base: str | None = None,
    title: str | None = None,
    working: bool = False,
    kind: str = "feature",
) -> MintResult:
    """Mint unit ``scope``: its plan, claiming ``branch``, and its fragment stub.

    Writes ``.prawduct/artifacts/build-plan-<scope>.md`` from the build-plan
    template with ``scope``, ``branch``, ``base`` and ``working-branches: []``,
    and ``.prawduct/changes/<scope>.md`` with the same ``scope``, ``type``
    (``kind``) and ``title``. The stub's narrative and ``## Consumer note`` are
    left empty, and an absent ``title`` is written empty, because those are the
    author's to write and the fragment validator already refuses each one
    unfilled — a placeholder that READ as written would ship.

    ``branch`` defaults to the checked-out branch. Naming another creates it from
    ``base`` and checks it out, after the files are written (untracked files
    survive the switch, and a failed switch removes them). ``base`` defaults to
    the repo's integration branch: ``base_branch:`` in ``project-state.yaml``,
    else what git says the remote integrates onto, else ``main``.

    ``working=True`` mints nothing: see :func:`join_working`.

    Refuses, writing nothing, when the scope is not a slug or is taken (by a
    live or archived plan, a fragment, or the change history), or a plan or
    pending fragment spells it within :func:`change_fragments.scope_near_match`;
    when the branch is a harness scratch branch, is already claimed by a live
    plan, or is the base itself; or when the plan or fragment file exists.
    """
    project_dir = Path(project_dir).resolve()
    if working:
        return join_working(project_dir, scope, branch=branch)

    _check_scope_is_free(project_dir, scope)
    if kind not in change_fragments.TYPES:
        raise PlanMintRefused(
            "bad-type", f"{kind!r} is not one of {', '.join(change_fragments.TYPES)}"
        )
    checked_out = gitstate.current_branch(project_dir)
    target = branch or checked_out
    if target is None:
        raise PlanMintRefused(
            "no-branch", "HEAD is detached, so there is no branch to claim — name one with --branch"
        )
    _check_claimable(project_dir, target)

    if base is not None:
        base_rule = "given"
    else:
        base, base_rule = default_base(project_dir)
    if target == base:
        raise PlanMintRefused(
            "branch-is-base",
            f"`{target}` is the integration branch this unit would merge into; a unit "
            "claims its own branch — name one with --branch",
        )

    start_point = None
    if target != checked_out:
        start_point = _creation_start_point(project_dir, target, base)

    plan_path = project_dir / ARTIFACTS_REL / f"build-plan-{scope}.md"
    fragment_path = project_dir / change_fragments.FRAGMENT_DIR_REL / f"{scope}.md"
    for path in (plan_path, fragment_path):
        if path.exists():
            raise PlanMintRefused(
                "file-exists", f"{path.relative_to(project_dir)} already exists; nothing was written"
            )
    plan_text = _render_plan(scope, target, base)
    fragment_text = change_fragments.render_fragment(
        kind=kind,
        scope=scope,
        date=_date.today().isoformat(),
        title=title or "",
        narrative="",
        consumer_note="",
    )
    _verify_plan(plan_text, scope=scope, branch=target, working=())

    plan_path.parent.mkdir(parents=True, exist_ok=True)
    fragment_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        core.write_all_or_none([(plan_path, plan_text), (fragment_path, fragment_text)])
    except OSError as exc:
        raise PlanMintRefused("write-failed", f"{exc}; every file was restored") from exc

    if start_point is not None:
        code, _out, err = gitstate._git_text(project_dir, "switch", "-c", target, start_point)
        if code != 0:
            # The files were written for a branch that does not exist; leaving
            # them would claim it from whatever branch is checked out instead.
            for path in (plan_path, fragment_path):
                path.unlink(missing_ok=True)
            raise PlanMintRefused(
                "branch-create-failed",
                f"`git switch -c {target} {start_point}` failed ({err or 'no output'}); "
                "nothing was left written",
            )
    return MintResult(
        "minted", scope, target, plan_path, fragment_path, base, base_rule,
        created_branch=start_point is not None,
    )


def join_working(project_dir: Path, scope: str, *, branch: str | None = None) -> MintResult:
    """Add a working branch (default: the checked-out one) to unit ``scope``'s plan.

    A working branch merges into the unit's integration branch and never into
    the base directly (D4), so the unit must be BOUND: its live plan claims an
    integration branch, and ``work_unit.resolve()`` on that branch answers with
    this plan. A unit with no claim, or one whose claim is broken, has no
    integration branch to merge into, and is refused. The scope is named rather
    than resolved from the checkout because the working branch is, until this
    call, claimed by nothing — which is the state that makes it joinable.

    Idempotent: a branch already listed returns ``unchanged``.
    """
    project_dir = Path(project_dir).resolve()
    target = branch or gitstate.current_branch(project_dir)
    if target is None:
        raise PlanMintRefused(
            "no-branch", "HEAD is detached, so there is no branch to add — name one with --branch"
        )
    artifacts = project_dir / ARTIFACTS_REL
    live = plan_index.build_scope_to_plan_map(artifacts)
    plan_path = live.get(scope)
    if plan_path is None:
        archived = scope in plan_index.build_scope_to_plan_map(artifacts, include_archived=True)
        raise PlanMintRefused(
            "no-such-unit",
            f"no live plan declares `scope: {scope}`"
            + (" — it is archived, and an ended unit takes no working branches; a "
               "follow-up is a new unit" if archived else ""),
        )
    content = _read(plan_path)
    integration = plan_index.parse_build_plan_frontmatter_branch(content)
    if integration is None:
        raise PlanMintRefused(
            "unit-unbound",
            f"{plan_index.display_path(plan_path, artifacts)} claims no `branch:`, so it has "
            f"no integration branch to merge into — run `{work_unit.BIND_COMMAND}` first",
        )
    binding = work_unit.resolve(project_dir, branch=integration)
    if not binding.is_claim or binding.plan_path != plan_path:
        raise PlanMintRefused(
            "unit-not-bound",
            f"`{integration}` does not bind to this plan: {binding.reason or binding.state}",
        )
    if target == integration:
        raise PlanMintRefused(
            "branch-is-integration", f"`{target}` is this unit's integration branch, not a working one"
        )

    status, listed = core.read_block_sequence(
        "\n".join(plan_index.frontmatter_lines(content) or []), work_unit.WORKING_BRANCHES_KEY
    )
    if status == core.YAML_UNPARSEABLE:
        raise PlanMintRefused(
            "working-branches-unparseable",
            f"{plan_index.display_path(plan_path, artifacts)} declares "
            f"`{work_unit.WORKING_BRANCHES_KEY}:` in a shape the resolver reads as none; "
            "write it as a block list (`  - name`) or `[]` first",
        )
    if target in listed:
        return MintResult("unchanged", binding.scope, target, plan_path)
    _check_claimable(project_dir, target)

    working = (*listed, target)
    updated = _set_working_branches(content, working)
    _verify_plan(updated, scope=binding.scope, branch=integration, working=working)
    _write_preserving_newlines(plan_path, updated)
    return MintResult("working", binding.scope, target, plan_path)


def bind(project_dir: Path, plan_path: Path | str, branch: str) -> MintResult:
    """Write ``branch:`` into an existing live plan — its claim on ``branch``.

    The way out of the legacy window: the advisory a pointer- or default-bound
    plan raises names this call. ``plan_path`` may be absolute, relative to the
    repo, or relative to ``.prawduct/artifacts/`` (the form the advisory prints).

    Refuses a plan that is not live (outside ``artifacts/``, archived, or not a
    build plan), one that already claims a different branch (re-pointing a
    unit's claim is an edit a person makes, not a side effect of this call), a
    branch some other live plan claims, and the harness scratch pattern.
    Binding the branch the plan already claims returns ``unchanged``.
    """
    project_dir = Path(project_dir).resolve()
    artifacts = project_dir / ARTIFACTS_REL
    path = _locate_plan(project_dir, Path(plan_path))
    content = _read(path)
    if not plan_index.is_build_plan(content) or plan_index.frontmatter_lines(content) is None:
        raise PlanMintRefused(
            "not-a-plan",
            f"{plan_index.display_path(path, artifacts)} is not a build plan with frontmatter",
        )
    rel = plan_index.display_path(path, artifacts)
    _present, scope = plan_index.parse_build_plan_frontmatter_scope(content)
    current = plan_index.parse_build_plan_frontmatter_branch(content)
    if current == branch:
        return MintResult("unchanged", scope, branch, path)
    if current is not None:
        raise PlanMintRefused(
            "plan-claims-other-branch",
            f"{rel} already claims `{current}`; re-pointing a unit's claim is an edit to "
            "make by hand, deliberately",
        )
    _check_claimable(project_dir, branch)
    updated = _set_scalar(content, plan_index.BRANCH_KEY, branch)
    # The working list is not this call's to judge, only to leave as it was.
    _verify_plan(updated, scope=scope, branch=branch, working=None)
    _write_preserving_newlines(path, updated)
    return MintResult("bound", scope, branch, path)


def default_base(project_dir: Path) -> tuple[str, str]:
    """``(base, rule)``: the integration branch a new unit merges into, and why.

    The repo's own declaration first — ``base_branch:`` in ``project-state.yaml``,
    the knob every gate that resolves a diff base reads — taken as written even
    when no ref resolves yet, because it is the repo's decision and a fresh clone
    may not have fetched it. Then the gates' own resolver (``coverage``), which
    asks the remote's default branch before the ``main`` family. Its last resort,
    ``HEAD~1``, names a commit rather than a branch, so it is not an answer here.
    git records no per-branch base for a checked-out branch, so there is no
    "this branch was cut from" to prefer over these.
    """
    project_dir = Path(project_dir)
    configured = core.read_str_yaml_key(project_dir / STATE_REL, "base_branch")
    if configured:
        return configured, "base_branch"
    from . import coverage  # noqa: PLC0415 — lazy; only minting needs the base resolver

    try:
        # The repo's base, not the checked-out unit's: a new unit's default is
        # the integration line, and a stacked one names its base with --base.
        ref, _reason = coverage.repo_base_branch(project_dir)
    except (OSError, subprocess.SubprocessError):
        ref = None
    if ref and ref != "HEAD~1":
        name = ref[len("origin/"):] if ref.startswith("origin/") else ref
        rule = "main-family" if name in coverage.MAIN_FAMILY else "origin-head"
        return name, rule
    return _FALLBACK_BASE, "fallback"


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def _check_scope_is_free(project_dir: Path, scope: str) -> None:
    if not change_fragments.is_scope(scope):
        raise PlanMintRefused(
            "bad-scope-slug",
            f"{scope!r} must be lowercase letters, digits, hyphens and single interior dots",
        )
    known = known_scopes(project_dir)
    if known is None:
        raise PlanMintRefused(
            "history-unreadable",
            "the change log cannot be read, so whether this scope was ever used cannot be "
            "known; fix the read error first",
        )
    if scope in known:
        raise PlanMintRefused(
            "scope-taken",
            f"`{scope}` is already a unit's identity (a plan, a fragment or the change "
            "history declares it); an identity is never reused — pick another, or "
            "`reopens:` it from a new scope",
        )
    # A near spelling of a plan or a pending fragment would make that one's record
    # ambiguous the moment this one exists; the fragment check would then refuse a
    # file nobody touched.
    neighbours = set(change_fragments.plan_scopes_for(project_dir))
    directory = project_dir / change_fragments.FRAGMENT_DIR_REL
    if directory.is_dir():
        neighbours.update(p.stem for p in directory.glob("*.md"))
    near = sorted(s for s in neighbours if change_fragments.scope_near_match(scope, s))
    if near:
        raise PlanMintRefused(
            "scope-near-taken",
            f"`{scope}` differs from {', '.join(f'`{s}`' for s in near)} only by spelling or one "
            "word; one unit has one spelling — name this one distinctly",
        )


def _check_claimable(project_dir: Path, branch: str) -> None:
    """Refuse a branch no live plan may claim: scratch, unrepresentable, or claimed."""
    if gitstate.is_scratch_branch(branch) or gitstate.ephemeral_kind_of(
        project_dir, branch
    ):
        raise PlanMintRefused(
            "scratch-branch",
            f"`{branch}` is a harness scratch branch or worktree — unbound by construction; "
            "the coordinator mints the unit on its own branch",
        )
    code, _out, _err = gitstate._git_text(project_dir, "check-ref-format", "--branch", branch)
    if code == -1:
        raise PlanMintRefused("git-unavailable", "git could not be run to check the branch name")
    if code != 0:
        raise PlanMintRefused("bad-branch-name", f"`{branch}` is not a legal git branch name")
    binding = work_unit.resolve(project_dir, branch=branch)
    # A legacy binding is the pointer or the default answering for a repo with no
    # claims; it is not a claim, and minting is how such a repo starts having them.
    if binding.state == "broken" or binding.is_claim:
        raise PlanMintRefused(
            "branch-claimed",
            f"`{branch}` is already claimed — {binding.reason or binding.plan_path}; a branch "
            "has one unit",
        )


def _creation_start_point(project_dir: Path, target: str, base: str) -> str:
    branches = gitstate.local_branches(project_dir)
    if branches is None:
        raise PlanMintRefused("git-unavailable", "git could not list branches")
    if target in branches:
        raise PlanMintRefused(
            "branch-exists",
            f"`{target}` already exists; check it out and mint there, or `plan bind` a plan to it",
        )
    for ref in (f"origin/{base}", base):
        code, _out, _err = gitstate._git_text(project_dir, "rev-parse", "--verify", "--quiet", ref)
        if code == 0:
            return ref
    raise PlanMintRefused(
        "base-not-found", f"neither origin/{base} nor {base} exists to create `{target}` from"
    )


def _locate_plan(project_dir: Path, plan_path: Path) -> Path:
    artifacts = (project_dir / ARTIFACTS_REL).resolve()
    candidates = (
        [plan_path] if plan_path.is_absolute() else [project_dir / plan_path, artifacts / plan_path]
    )
    found = next((c.resolve() for c in candidates if c.is_file()), None)
    if found is None:
        raise PlanMintRefused("no-such-plan", f"{plan_path} is not a file")
    try:
        rel = found.relative_to(artifacts)
    except ValueError:
        raise PlanMintRefused(
            "not-live", f"{plan_path} is not under {ARTIFACTS_REL}/, so it governs nothing"
        ) from None
    if plan_index.ARCHIVE_DIR_NAME in rel.parts:
        raise PlanMintRefused(
            "not-live", f"{rel} is archived — its claim ended when it was archived"
        )
    return found


def _read(path: Path) -> str:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError) as exc:
        raise PlanMintRefused("unreadable", f"{path.name}: {exc}") from exc


# ---------------------------------------------------------------------------
# Rendering and frontmatter edits
# ---------------------------------------------------------------------------


def _render_plan(scope: str, branch: str, base: str) -> str:
    """The template, with its identity keys replaced by this unit's.

    The template stays the one home of a plan's shape: its body, its field labels
    and its frontmatter guidance are copied as they are, exactly as an author
    copying it by hand would get them. Only the keys this module owns are
    rewritten — any declared form of them is removed and the unit's are written
    after ``version:`` — so a later edit to the template's examples cannot leave
    the minted plan claiming the example's branch. Comments are kept whole: one
    that merely shows a key is inert to every reader, and cutting comment lines
    by their first word would orphan the guidance around them.
    """
    try:
        template = (core.TEMPLATES_DIR / "build-plan.md").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise PlanMintRefused("template-unreadable", f"build-plan template: {exc}") from exc
    lines = template.splitlines(keepends=True)
    span = plan_index.frontmatter_span(template)
    if span is None:
        raise PlanMintRefused("template-unreadable", "the build-plan template has no frontmatter")
    start, end = span
    owned = (*_IDENTITY_KEYS, "last_validated")
    kept: list[str] = []
    skipping_block = False
    for line in lines[start + 1 : end]:
        if skipping_block and line[:1] in (" ", "\t"):
            continue  # the owned key's block items
        skipping_block = False
        if any(line.startswith(f"{key}:") for key in owned):
            skipping_block = True
            continue
        kept.append(line)
    identity = [
        f"scope: {scope}\n",
        f"{plan_index.BRANCH_KEY}: {branch}\n",
        f"{BASE_KEY}: {base}\n",
        f"{work_unit.WORKING_BRANCHES_KEY}: []\n",
        f"last_validated: {_date.today().isoformat()}\n",
    ]
    anchor = next((i for i, line in enumerate(kept) if line.startswith("version:")), None)
    insert_at = anchor + 1 if anchor is not None else 0
    body = kept[:insert_at] + identity + kept[insert_at:]
    return "".join(lines[: start + 1] + body + lines[end:])


def _frontmatter_bounds(content: str) -> tuple[list[str], int, int]:
    lines = content.splitlines(keepends=True)
    span = plan_index.frontmatter_span(content)
    if span is None:
        raise PlanMintRefused("not-a-plan", "the plan has no frontmatter block to write into")
    return lines, span[0], span[1]


def _eol(lines: list[str]) -> str:
    """The file's own line ending, so an edit does not reformat a CRLF file."""
    return "\r\n" if lines and lines[0].endswith("\r\n") else "\n"


def _set_scalar(content: str, key: str, value: str) -> str:
    """Set a top-level frontmatter scalar, replacing a declared one or adding it.

    A new key goes after ``scope:`` when there is one — identity, then claim — or
    else just before the closing ``---``.
    """
    lines, start, end = _frontmatter_bounds(content)
    eol = _eol(lines)
    for i in range(start + 1, end):
        if lines[i][:1] not in (" ", "\t") and lines[i].startswith(f"{key}:"):
            lines[i] = f"{key}: {value}{eol}"
            return "".join(lines)
    after = next(
        (i for i in range(start + 1, end) if lines[i].startswith("scope:")), end - 1
    )
    lines.insert(after + 1, f"{key}: {value}{eol}")
    return "".join(lines)


def _set_working_branches(content: str, working: tuple[str, ...]) -> str:
    """Rewrite ``working-branches:`` as a block list holding ``working``.

    The caller has established the existing declaration is absent, ``[]`` or a
    clean block list, so the span replaced is exactly the key line and its
    indented items — never "to the next key", which a comment could extend.
    """
    lines, start, end = _frontmatter_bounds(content)
    eol = _eol(lines)
    key = work_unit.WORKING_BRANCHES_KEY
    block = [f"{key}:{eol}", *(f"  - {name}{eol}" for name in working)]
    for i in range(start + 1, end):
        if lines[i][:1] not in (" ", "\t") and lines[i].startswith(f"{key}:"):
            j = i + 1
            while j < end and lines[j].lstrip().startswith("- ") and lines[j][:1] in (" ", "\t"):
                j += 1
            return "".join(lines[:i] + block + lines[j:])
    after = next(
        (i for i in range(start + 1, end) if lines[i].startswith(f"{plan_index.BRANCH_KEY}:")),
        end - 1,
    )
    return "".join(lines[: after + 1] + block + lines[after + 1 :])


def _verify_plan(
    text: str, *, scope: str | None, branch: str, working: tuple[str, ...] | None
) -> None:
    """Read the text back through the resolver's own parsers before it is written.

    A branch name the frontmatter reader would truncate (a ``#`` starts a comment
    there) or a list it would read as none is caught here, as a refusal, rather
    than as a plan that claims something other than what it was told to.
    """
    fm = plan_index.frontmatter_lines(text)
    _present, read_scope = plan_index.parse_build_plan_frontmatter_scope(text)
    read_branch = plan_index.parse_build_plan_frontmatter_branch(text)
    status, read_working = core.read_block_sequence(
        "\n".join(fm or []), work_unit.WORKING_BRANCHES_KEY
    )
    # An absent list and `[]` both mean none to the resolver; anything else must
    # read back as exactly what was written.
    working_ok = working is None or (
        read_working == tuple(working)
        and (status == core.YAML_DECLARED or (status == core.YAML_ABSENT and not working))
    )
    if (
        fm is None
        or not plan_index.is_build_plan(text)
        or read_scope != scope
        or read_branch != branch
        or not working_ok
    ):
        raise PlanMintRefused(
            "unrepresentable",
            f"the plan would not read back as scope={scope!r}, branch={branch!r}"
            + ("" if working is None else f", working-branches={list(working)!r}")
            + f" (read {read_scope!r}, {read_branch!r}, {list(read_working)!r}); "
            "nothing was written",
        )


def _write_preserving_newlines(path: Path, text: str) -> None:
    try:
        core.atomic_write_text(path, text, encoding="utf-8", newline="")
    except OSError as exc:
        raise PlanMintRefused("write-failed", f"{path.name}: {exc}") from exc
