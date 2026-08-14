"""Which files under ``artifacts/`` are build plans, and what scope each declares.

This module knows **plans and nothing about tags**. Change-log tag reading lives
in :mod:`lib.change_log`; the two were one module named ``views`` that did both
jobs under a name describing neither.

Three governance paths ask this module, two of them on every session: review
dispatch, the session briefing at SessionStart, and the Stop hook at session end
(which resolves the branch's plan *before* deciding whether a plan is active, so
the scan runs whenever the hook runs). That is why the archive is pruned at walk
level rather than filtered per file, and why nothing here imports a heavy module.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path


ARCHIVE_DIR_NAME = "archive"

#: Frontmatter key by which a build plan declares the branch it governs.
#: Chosen against real data rather than for being the obvious short word: on
#: 2026-08-13 ``grep -rn '^branch:' --include='*.md' .`` matched nothing in this
#: repo or the shipped templates, and no other reader parses that key out of
#: frontmatter. Re-run that grep before adding a second meaning to it.
BRANCH_KEY = "branch"

#: Characters read from a plan's head when only its frontmatter is wanted. The
#: largest frontmatter in this repo is ~2.5 KiB, so this covers it several times
#: over; a block that does not close inside it makes the file be re-read WHOLE
#: (:func:`_frontmatter_probe`) rather than read as having no frontmatter. A
#: bounded read that silently drops a plan's claim is worse than a slow one.
_FRONTMATTER_PROBE_CHARS = 16384


def display_path(path: Path, artifacts_dir: Path) -> str:
    """A plan path as written for a human, relative to the artifacts dir when possible.

    Bare ``path.name`` was adequate while discovery was flat. Recursive
    discovery makes ``build-plan.md`` a near-certain collision across
    ``plans/<id>/`` directories, so a duplicate-scope message naming two files
    called ``build-plan.md`` tells the operator nothing about which two.

    Public because the lifecycle commands need it for the same reason and got it
    wrong first: a backfill preview listing four plans as ``build-plan.md`` is
    the list a single operation-level approval rests on, and consent to an
    unidentifiable list is not informed consent. Found by running against a real
    consumer repo that nests plans under ``plans/<id>/`` — every fixture here is
    flat, so no fixture could have shown it.
    """
    try:
        return str(path.relative_to(artifacts_dir))
    except ValueError:
        return path.name


def frontmatter_body_start(lines: list[str]) -> int:
    """Index of the line where a frontmatter block may legally open.

    The prelude skip, factored out so the reader and the writer cannot disagree
    about where a block begins: leading blank lines and one leading HTML comment
    block. That tolerance is load-bearing — a third of this repo's build plans
    open with a comment header before the frontmatter (16 of 48 as of
    2026-07-27, counted with ``for f in .prawduct/artifacts/build-plan*.md; do
    head -1 "$f"; done``).

    An UNCLOSED comment header runs off the end and returns ``len(lines)``,
    which reads downstream as "no frontmatter" rather than raising — a
    deliberately lenient reading, so one hand-corrupted file cannot make a
    governance path fail instead of degrade.
    """
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines) and lines[i].lstrip().startswith("<!--"):
        while i < len(lines) and "-->" not in lines[i]:
            i += 1
        if i < len(lines):
            i += 1  # consume the line containing `-->`
    while i < len(lines) and not lines[i].strip():
        i += 1
    return i


def frontmatter_span(content: str) -> tuple[int, int] | None:
    """``(opening ---, closing ---)`` line indices, or ``None`` when there is none.

    ONE walker, so ``scope:``, ``artifact:`` and any writer that has to put a key
    INTO the block all locate it the same way. Two independent walkers over the
    same block is the shape that lets a file be a build plan to one reader and
    not to another — exactly the class of disagreement the scope collectors were
    already exhibiting — and a writer with its own walker is the same defect
    pointed at the file rather than at a verdict.

    An unterminated frontmatter reads as *absent*, for the same
    degrade-don't-fail reason as :func:`frontmatter_body_start`'s unclosed
    comment.
    """
    lines = content.splitlines()
    i = frontmatter_body_start(lines)
    if i >= len(lines) or lines[i].strip() != "---":
        return None
    for j in range(i + 1, len(lines)):
        if lines[j].strip() == "---":
            return (i, j)
    return None  # unterminated frontmatter reads as absent


def frontmatter_lines(content: str) -> list[str] | None:
    """The frontmatter block's body lines, or ``None`` when there is no block."""
    span = frontmatter_span(content)
    if span is None:
        return None
    return content.splitlines()[span[0] + 1 : span[1]]


def _frontmatter_scalar(fm: list[str], key: str) -> tuple[bool, str | None]:
    """``(present, value)`` for a top-level ``key:`` in already-extracted frontmatter.

    ONE value-level reader, for the reason :func:`frontmatter_span` gives for
    being one block-level walker: two independent readers over the same block let
    a later fix to quoting, inline-comment or whitespace handling land on one key
    and not the other, so one plan's frontmatter comes to mean different things
    to the scope map and to the branch claim. ``scope:`` and ``branch:`` were
    line-for-line twins here, differing only in the key.

    Indented lines are skipped as nested rather than read; ``#`` starts a comment;
    surrounding quotes are stripped. ``present`` distinguishes a key set to the
    YAML null literal (``(True, None)`` — an explicit opt-out) from an absent one
    (``(False, None)``), because ``scope:`` has a caller that must tell them apart.
    """
    for line in fm:
        if line[:1] in (" ", "\t"):
            continue  # nested key, not a top-level declaration
        stripped = line.split("#", 1)[0].rstrip()
        if not stripped.startswith(f"{key}:"):
            continue
        value = stripped.split(":", 1)[1].strip().strip('"').strip("'")
        if not value or value.lower() in ("null", "~"):
            return (True, None)
        return (True, value)
    return (False, None)


def parse_build_plan_frontmatter_scope(content: str) -> tuple[bool, str | None]:
    """Parse ``scope:`` from a build plan's YAML frontmatter block.

    Returns a ``(present, value)`` tuple. ``present`` distinguishes "the
    ``scope:`` key appears in the frontmatter" from "the key is absent" — a
    distinction that matters because the two cases drive different fallback
    behaviour in every caller that infers a scope:

    * ``(True, "v1.5")`` — key present with a real value (quotes stripped).
    * ``(True, None)``   — key present but set to the YAML null literal
      (``null`` / ``~``) or left empty. This is the documented *explicit
      opt-out* form: the author is saying "do not scope-filter," and inference
      MUST be suppressed rather than silently inheriting a change-log scope.
    * ``(False, None)``  — key absent, nested inside another key, outside the
      frontmatter, the file has no frontmatter at all, OR a leading HTML comment
      header is never closed. The unclosed-comment case is handled leniently by
      :func:`frontmatter_lines` and reads as "absent", which lets inference fall
      back rather than raising on a malformed file.
    """
    fm = frontmatter_lines(content)
    if fm is None:
        return (False, None)
    # A present key with an empty or null-literal value is an explicit opt-out,
    # not an absence — `(True, None)`, so callers can suppress inference rather
    # than fall back.
    return _frontmatter_scalar(fm, "scope")


def parse_build_plan_frontmatter_branch(content: str) -> str | None:
    """The branch a build plan declares it governs, or ``None``.

    The inverse of the ``active_build_plan:`` scalar: *which branch is this plan
    for* is a fact about the plan, so the plan holds it. Two concurrent branches
    can then each carry their own plan without editing one shared line, and a
    merged branch's plan simply stops matching instead of having to be un-pointed.

    Absence, an empty value, and the YAML null literal (``null`` / ``~``) all read
    as "claims no branch" — unlike ``scope:``, no caller needs to tell an explicit
    opt-out apart from an absent key, because both mean the same thing here: fall
    through to the scalar.
    """
    fm = frontmatter_lines(content)
    if fm is None:
        return None
    # Unlike `scope:`, the two "no claim" cases collapse: an absent key and an
    # explicit null both mean "fall through to the scalar", so `present` is
    # discarded rather than returned.
    _present, value = _frontmatter_scalar(fm, BRANCH_KEY)
    return value


def _frontmatter_probe(path: Path) -> str | None:
    """Enough of ``path``'s text to contain its whole frontmatter block, or ``None``.

    A bounded read, because the branch scan opens every live markdown file under
    ``artifacts/`` and only ever wants the header. The bound is not trusted to be
    enough: when the block has not closed inside it AND the read hit the limit,
    the file is re-read whole. Without that second half the bound would be a
    silent correctness knob — a plan with long frontmatter would read as
    declaring nothing, and nothing would say so.
    """
    try:
        with path.open("r", encoding="utf-8") as handle:
            head = handle.read(_FRONTMATTER_PROBE_CHARS)
    except (OSError, UnicodeDecodeError):
        # As in `_walk_for_scopes`: one unreadable file must not blind the scan
        # to every other plan. `UnicodeDecodeError` is a `ValueError`, so a
        # narrower `except OSError` would let it escape to the caller.
        return None
    if frontmatter_span(head) is not None or len(head) < _FRONTMATTER_PROBE_CHARS:
        return head
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def branch_claiming_plans(artifacts_dir: Path) -> list[tuple[Path, str]]:
    """``(path, branch)`` for every live build plan declaring a ``branch:``.

    Sorted by path and archive-pruned on the same walk the scope map uses, so an
    archived plan's ``branch:`` claims nothing — moving a plan under ``archive/``
    ends its claim, which is what makes archiving the whole retirement step.

    Returns EVERY claim rather than resolving one. Several plans may claim one
    branch, and the caller both chooses among them and names the ones it passed
    over — a function that returned the first match could tell it apart from
    neither the only match nor the rest.
    """
    if not artifacts_dir.is_dir():
        return []
    claims: list[tuple[Path, str]] = []
    for plan_path in _markdown_files(artifacts_dir, prune_archive=True):
        content = _frontmatter_probe(plan_path)
        if content is None or _declares_non_build_plan_artifact(content):
            continue  # declares itself something other than a build plan
        branch = parse_build_plan_frontmatter_branch(content)
        if branch:
            claims.append((plan_path, branch))
    return claims


def _declares_non_build_plan_artifact(content: str) -> bool:
    """True when frontmatter declares an ``artifact:`` type that is NOT a build plan.

    Both scope collectors that preceded this module treated ANY file with a
    frontmatter ``scope:`` as a build plan. That is detection by surface marker
    rather than by declared type, and several files in this repo already carry a
    scope while being a design note, a discovery, a reference, a release plan or
    a collapse map. Enumerate rather than trust a digit::

        grep -l '^scope:' .prawduct/artifacts/*.md \\
          | xargs grep -l '^artifact:' \\
          | xargs grep -L '^artifact: build-plan'

    The middle stage is load-bearing: ``grep -L`` alone cannot distinguish
    "declares another type" from "declares NO type" — precisely the distinction
    this predicate draws. Omitting it wrongly condemns
    ``build-plan-release-readiness.md`` (a real plan, the counter-example below)
    and a file whose ``scope:`` sits inside an HTML comment and never parses.

    Absence is treated as a build plan, not excluded: `build-plan-release-
    readiness.md` declares no ``artifact:`` key at all, so requiring
    ``artifact: build-plan`` would silently drop a real plan. Excluding only an
    explicit *other* type fails safe in the direction that keeps plans.
    """
    fm = frontmatter_lines(content)
    if fm is None:
        return False
    for line in fm:
        if line[:1] in (" ", "\t"):
            continue  # nested key, not a top-level declaration
        stripped = line.split("#", 1)[0].rstrip()
        if not stripped.startswith("artifact:"):
            continue
        value = stripped.split(":", 1)[1].strip().strip('"').strip("'")
        return bool(value) and value != "build-plan"
    return False


def is_build_plan(content: str) -> bool:
    """Whether this document is a build plan, by its DECLARED type.

    The positive spelling of :func:`_declares_non_build_plan_artifact`, added
    when a second module needed the question asked forward rather than as a
    negation. It inherits that predicate's fail-safe direction exactly: a
    document declaring no ``artifact:`` at all counts as a build plan, because
    at least one real plan in this repo declares none.

    Callers that care about a build plan's *chunks* — a Status roster, its
    completeness — must ask this first. A release plan or a discovery note has
    no roster by design, and reading its silence as "unreadable" reports a
    problem about a document that never had the thing being looked for.
    """
    return not _declares_non_build_plan_artifact(content)


def iter_scoped_plan_candidates(
    artifacts_dir: Path, *, include_archived: bool = False
) -> Iterator[tuple[Path, str]]:
    """Yield ``(path, scope)`` for every scope-declaring build plan under ``artifacts_dir``.

    The ONE home for "which files are build plans, and what scope does each
    declare." Its two consumers were line-for-line twins of this loop, and both
    carried a docstring warning that letting them diverge would make the
    diagnostic condemn a file the map never considered — which is exactly what
    happened on 2026-08-01. A warning that a duplicate must be kept in sync is
    worth less than not having the duplicate.

    **Discovery is recursive.** A flat ``glob("*.md")`` saw only the top level,
    so a repo organizing plans as ``artifacts/plans/<id>/build-plan.md`` had
    every one of them invisible. Four surveyed repos carry 16 nested plans each
    (2026-07-21 fleet survey).

    **The archive subtree is never descended.** An archived plan is history,
    not a live assertion — the same rule every record check applies. Skipping
    the directory outright, rather than walking it and discarding what it
    yielded, is what keeps this bounded as the archive grows without limit: the
    walk runs at every session start and every session end, so anything less
    makes each session pay for every plan the repo has ever completed. See
    :func:`_markdown_files` for why that rules out ``Path.rglob``. Pass
    ``include_archived=True`` only from a cold path that must resolve a name
    into history.

    Pruning is also load-bearing for correctness, and was so before it was a
    cost question: discovery is ``sorted()`` and its consumers are first-wins,
    and ``archive/build-plan-foo.md`` sorts BEFORE ``build-plan-foo.md``, so an
    archived copy would shadow its own live sibling. When ``include_archived``
    is set the live tree is therefore walked FIRST and the archive appended, so
    a live plan still wins its scope. "The archive" is every directory named
    ``archive`` at any depth (:func:`_archive_roots`), because that is exactly
    what the live pass pruned — the two rules are one rule, and they were not.

    Ordering is by sorted path so the first-wins tie-break in both consumers
    stays deterministic, which makes *directory depth* part of that tie-break.
    Consumers report paths via :func:`display_path` rather than ``Path.name`` —
    see its docstring for why nesting makes that necessary.
    """
    if not artifacts_dir.is_dir():
        return
    yield from _walk_for_scopes(artifacts_dir, artifacts_dir, prune_archive=True)
    if include_archived:
        for archive_dir in _archive_roots(artifacts_dir):
            yield from _walk_for_scopes(archive_dir, artifacts_dir, prune_archive=False)


def _archive_roots(artifacts_dir: Path) -> list[Path]:
    """Every directory named ``archive`` at any depth, sorted, outermost only.

    **The two passes have to prune and re-walk on the SAME rule.** The live pass
    drops any path component named ``archive`` at every depth; re-walking only
    ``artifacts_dir/archive`` therefore left a nested ``plans/<id>/archive/``
    pruned from the live pass AND absent from the archived one — invisible to
    every reader, which the live-then-archive resolution rule assumes cannot
    happen. That shape is not hypothetical: repos that organize plans as
    ``plans/<id>/build-plan.md`` archive beside the plan, and a flat fixture
    passes under either rule, so only a nested one can tell them apart.

    An ``archive`` inside an ``archive`` is not sought separately — the walk
    rooted at the outer one already yields its whole subtree, and descending
    further would yield the same file twice.
    """
    roots: list[Path] = []
    for dirpath, dirnames, _filenames in os.walk(artifacts_dir):
        dirnames.sort()
        roots.extend(Path(dirpath) / d for d in dirnames if d == ARCHIVE_DIR_NAME)
        # In-place, for the same reason `_markdown_files` says: rebinding leaves
        # `os.walk` holding the original list and descends anyway.
        dirnames[:] = [d for d in dirnames if d != ARCHIVE_DIR_NAME]
    return sorted(roots)


def _markdown_files(root: Path, *, prune_archive: bool) -> list[Path]:
    """Every ``*.md`` under ``root``, sorted, without descending pruned dirs.

    ``os.walk`` rather than ``Path.rglob`` because pruning is the entire point
    and ``rglob`` has no pruning hook: it yields every path under the tree, so a
    caller can only *discard* archived entries after the walk has already
    descended into them and stat-ed every file. That is the shape BP9 forbids,
    and it is indistinguishable from real pruning in any test that only checks
    which files were opened. Assigning to ``dirnames[:]`` in place is what makes
    ``os.walk`` skip a subtree outright.

    The result is sorted because both consumers are first-wins and their
    tie-break must be deterministic; sorting the collected list preserves that
    without giving up the prune.
    """
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        if prune_archive:
            # In-place, and it must stay in-place — rebinding the name leaves
            # `os.walk` holding the original list and descends anyway.
            dirnames[:] = [d for d in dirnames if d != ARCHIVE_DIR_NAME]
        dirnames.sort()
        base = Path(dirpath)
        found.extend(base / name for name in filenames if name.endswith(".md"))
    return sorted(found)


def _walk_for_scopes(
    root: Path, artifacts_dir: Path, *, prune_archive: bool
) -> Iterator[tuple[Path, str]]:
    """Yield ``(path, scope)`` for scope-declaring plans under ``root``.

    ``artifacts_dir`` is unused for filtering — pruning happens during the walk
    — but stays in the signature because callers pass it and the archive rule is
    anchored to it: "any path component named ``archive``", including a nested
    ``plans/<id>/archive/``, not merely the top-level one.
    """
    for plan_path in _markdown_files(root, prune_archive=prune_archive):
        try:
            content = plan_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            # One malformed file under artifacts/ must not blind the scan to
            # every other plan. `UnicodeDecodeError` is a `ValueError`, so a
            # narrower `except OSError` would let it escape to the caller.
            continue
        if _declares_non_build_plan_artifact(content):
            continue  # scope-tagged, but declares itself a non-plan artifact
        _present, scope = parse_build_plan_frontmatter_scope(content)
        if scope:
            yield plan_path, scope


def unreadable_candidates(artifacts_dir: Path) -> list[dict]:
    """Markdown files under ``artifacts_dir`` that cannot be read as utf-8 text.

    :func:`iter_scoped_plan_candidates` deliberately swallows these — one
    malformed file must not blind the scan to every other plan, and that is the
    right call for a *map*. It is the wrong call for a *repair*: a plan the
    repair cannot read may hold the residue it exists to remove, and silently
    skipping it lets the command report "already in the target state" about a
    file nothing looked at.

    So the swallow stays where the map needs it and the fact is published here
    instead. Cold path only — nothing on a session boundary calls this, which is
    why it re-reads rather than being folded into the walk the gates pay for.
    The archive is pruned for the same reason the map prunes it: an archived
    plan is a record, and nothing is going to repair it.
    """
    found: list[dict] = []
    if not artifacts_dir.is_dir():
        return found
    for path in _markdown_files(artifacts_dir, prune_archive=True):
        try:
            path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            found.append({"path": str(path), "reason": str(exc)})
    return found


def build_scope_to_plan_map(
    artifacts_dir: Path, *, include_archived: bool = False
) -> dict[str, Path]:
    """Map each frontmatter ``scope:`` to its build-plan FILE under ``artifacts_dir``.

    Records ``{scope_value: path}`` for every file whose YAML frontmatter
    declares a non-empty ``scope:`` (parsed by
    :func:`parse_build_plan_frontmatter_scope`) **and does not declare an**
    ``artifact:`` **type other than** ``build-plan`` (see
    :func:`_declares_non_build_plan_artifact` — a design note, discovery,
    reference, release plan or collapse map may legitimately carry a scope and
    is not a plan). Both keys are stated here, not only in the private helper,
    because the question a reader arrives with is "why doesn't my scope
    resolve?" and the answer is two keys rather than one.

    On a duplicate scope across two files, the first by sorted path wins
    (deterministic; a duplicate scope is malformed and is reported separately).
    With ``include_archived=True`` a live plan always beats an archived one of
    the same scope, because the live tree is walked first.

    Returns ``{}`` when the directory is absent or holds no scope-tagged plans.
    Read-only.
    """
    result: dict[str, Path] = {}
    for plan_path, scope in iter_scoped_plan_candidates(
        artifacts_dir, include_archived=include_archived
    ):
        if scope not in result:
            result[scope] = plan_path
    return result


def duplicate_scope_errors(artifacts_dir: Path) -> list[tuple[str, str]]:
    """``(scope, message)`` per scope declared by more than one live build plan.

    A duplicate scope makes a scope→plan lookup a coin toss decided by sort
    order — the same ambiguity that let a diagnostic condemn a file the map
    never considered. Reported rather than raised: :func:`build_scope_to_plan_map`
    still answers deterministically, so this is information for the author, not
    a reason to stop.

    The scope is returned alongside its message because a caller may need to
    attribute the failure to one scope rather than treat it as global.
    """
    errors: list[tuple[str, str]] = []
    first_seen: dict[str, Path] = {}
    for plan_path, scope in iter_scoped_plan_candidates(artifacts_dir):
        if scope in first_seen:
            errors.append(
                (
                    scope,
                    f"duplicate scope={scope!r}: "
                    f"{display_path(plan_path, artifacts_dir)} also declares it "
                    f"(keeping {display_path(first_seen[scope], artifacts_dir)}); "
                    f"one plan is malformed.",
                )
            )
        else:
            first_seen[scope] = plan_path
    return errors
