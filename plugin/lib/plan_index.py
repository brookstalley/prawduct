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


def _display_path(path: Path, artifacts_dir: Path) -> str:
    """A plan path as written for a human, relative to the artifacts dir when possible.

    Bare ``path.name`` was adequate while discovery was flat. Recursive
    discovery makes ``build-plan.md`` a near-certain collision across
    ``plans/<id>/`` directories, so a duplicate-scope message naming two files
    called ``build-plan.md`` tells the operator nothing about which two.
    """
    try:
        return str(path.relative_to(artifacts_dir))
    except ValueError:
        return path.name


def frontmatter_lines(content: str) -> list[str] | None:
    """The frontmatter block's body lines, or ``None`` when there is no block.

    ONE walker, so ``scope:`` and ``artifact:`` are read the same way. Two
    independent walkers over the same block is the shape that lets a file be a
    build plan to one reader and not to another, which is exactly the class of
    disagreement the scope collectors were already exhibiting.

    Tolerances, and load-bearing — a third of this repo's build plans open with
    a comment header before the frontmatter (16 of 48 as of 2026-07-27, counted
    with ``for f in .prawduct/artifacts/build-plan*.md; do head -1 "$f"; done``):
    leading blank lines and one leading HTML comment block are skipped before
    the opening ``---``. An UNCLOSED comment header or an unterminated
    frontmatter both read as *absent* rather than raising — a deliberately
    lenient reading of a malformed header, so one hand-corrupted file cannot
    make a governance path fail instead of degrade.
    """
    lines = content.splitlines()
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
    if i >= len(lines) or lines[i].strip() != "---":
        return None
    body: list[str] = []
    for j in range(i + 1, len(lines)):
        if lines[j].strip() == "---":
            return body
        body.append(lines[j])
    return None  # unterminated frontmatter reads as absent


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
    for line in fm:
        if line[:1] in (" ", "\t"):
            continue
        stripped = line.split("#", 1)[0].rstrip()
        if not stripped.startswith("scope:"):
            continue
        value = stripped.split(":", 1)[1].strip().strip('"').strip("'")
        # Key is present. An empty or null-literal value is an explicit
        # opt-out, not an absence — return (True, None) so callers can
        # suppress inference.
        if not value or value.lower() in ("null", "~"):
            return (True, None)
        return (True, value)
    return (False, None)


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
    a live plan still wins its scope.

    Ordering is by sorted path so the first-wins tie-break in both consumers
    stays deterministic, which makes *directory depth* part of that tie-break.
    Consumers report paths via :func:`_display_path` rather than ``Path.name`` —
    see its docstring for why nesting makes that necessary.
    """
    if not artifacts_dir.is_dir():
        return
    yield from _walk_for_scopes(artifacts_dir, artifacts_dir, prune_archive=True)
    if include_archived:
        archive_dir = artifacts_dir / ARCHIVE_DIR_NAME
        if archive_dir.is_dir():
            yield from _walk_for_scopes(archive_dir, artifacts_dir, prune_archive=False)


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
                    f"{_display_path(plan_path, artifacts_dir)} also declares it "
                    f"(keeping {_display_path(first_seen[scope], artifacts_dir)}); "
                    f"one plan is malformed.",
                )
            )
        else:
            first_seen[scope] = plan_path
    return errors
