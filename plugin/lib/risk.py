"""Risk-surface diff classifier (review-proportionality ch.04).

Two-sided proportionality: review depth should scale DOWN where assurance is
duplicated and UP where risk concentrates. The A/B/C reviewer experiment
(``.prawduct/artifacts/reviewer-model-ab-2026-06-10.md``) showed the top-tier
reviewer catching real warnings the default tier missed precisely on a
governance-gate bundle — that bundle class should buy depth. ``prawduct-hook
classify-diff-risk [<base>]`` answers one question for the dispatching skill:
does the review scope intersect a declared risk surface?

**PAUSED (2026-07-14):** the reviewer-model consumer of this verdict was removed
(emergency patch — reviewers now run on the session model, no tier→model chain).
``classify-diff-risk`` still runs and the Critic still records the verdict as
``--tier`` telemetry, but it currently selects **no** model. The A/B rationale
above and the resolution/failure semantics below are retained verbatim for the
planned restore of tiering (change-log ``reviewer-session-model``).

**Resolution order** (the build plan's open-assumption, user-vetoable):

1. An explicit ``risk_surfaces:`` list in ``project-state.yaml`` — the
   product-ownable declaration. When the key is PRESENT it is exclusive: the
   derived defaults below do not apply (an explicitly empty list is a
   deliberate "this product has no risk surfaces" opt-out).
2. Else derived defaults — paths matching ``skills/``, ``lib/gates*``,
   ``bin/*hook*``, each also in its ``plugin/``-prefixed form so both packaging
   layouts match (see :data:`DERIVED_DEFAULT_SURFACES`) — plus literal
   backticked contract-file paths parsed from
   ``.prawduct/artifacts/boundary-patterns.md`` when present.

**Pattern semantics**: a surface ending in ``/`` is a directory prefix;
anything else is an ``fnmatch`` glob (a bare path with no metacharacters is
an exact match). Matching is against the review scope = committed paths in
``merge-base(base)...HEAD`` plus the working tree's changed/untracked paths
(a ``final`` review covers uncommitted work too).

**Failure honesty** (the load-bearing asymmetry): when surfaces are DECLARED
but the diff cannot be evaluated (git failure), the verdict is ``escalate``
— declared risk plus an unverifiable diff must not silently get the cheap
reviewer (fail closed). Fail-open to ``standard`` is allowed ONLY when no
surfaces are declared (a product repo that never opted in loses nothing).

**Output contract**: the verdict — ``escalate`` or ``standard`` — is the
single stdout token; matched files (one ``risk: <path> matched <pattern>``
line each) and failure reasons go to stderr (teach at the boundary, like
every gate). Exit 0 whenever a verdict is printed; exit 1 only on bad args.
"""

from __future__ import annotations

import re
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path

from . import gitstate
from .buildplan_refs import _looks_like_file_path

# Derived-default risk surfaces (resolution order step 2). Framework-shaped on
# purpose — the governance machinery itself (skills, gates, the hook) is where
# a missed defect costs the most; products with different hot spots declare
# `risk_surfaces:` and these defaults stop applying entirely.
#
# **Two packaging layouts, both live.** A product repo carries these shapes at
# its root; the framework repo packages its own machinery under ``plugin/``
# (moved there by ``c6b8131``, 2026-07-21). The forms are therefore GENERATED
# from one list of shapes rather than written out, so a shape added later cannot
# land in only one layout.
#
# Do not flatten this back to literals. The 2026-07-21 restructure left
# root-only patterns in place, and the invariant that followed is: **a diff
# containing no pre-restructure root-layout path could not classify
# ``escalate``**, gate-kernel changes included — because none of ``skills/``,
# ``lib/gates*``, ``bin/*hook*`` matches a ``plugin/``-prefixed path. The
# boundary is visible in the evidence store: the last ``escalate`` matched only
# because the restructure's own diff still listed the root paths it was
# deleting, and every review after it went ``standard``. Nothing caught it: the
# verdict's only consumer
# had been removed on 2026-07-14 (``reviewer-session-model``), so the tier has
# been telemetry-only since and no gate could go wrong out loud. The test that
# should have caught it pinned this tuple's literal value, which stayed true
# while the repo's layout moved out from under it — so the regression test that
# replaced it asserts against THIS repo's real paths instead.
_FRAMEWORK_SURFACE_SHAPES = ("skills/", "lib/gates*", "bin/*hook*")
_PACKAGING_PREFIXES = ("", "plugin/")
DERIVED_DEFAULT_SURFACES = tuple(
    f"{prefix}{shape}"
    for shape in _FRAMEWORK_SURFACE_SHAPES
    for prefix in _PACKAGING_PREFIXES
)

_BACKTICK_RE = re.compile(r"`([^`]+)`")


def _read_list_yaml_key(state_path: Path, key: str) -> list[str] | None:
    """Items of a top-level (column-0) ``key:`` block list, or ``None`` when
    the key is absent/unreadable. Distinguishes declared-but-empty (``[]``,
    which is exclusive per the resolution order) from undeclared (``None``).
    Same minimal-YAML discipline as ``core.read_str_yaml_key`` — column-0 key,
    ``- item`` lines until the next column-0 key, inline comments stripped."""
    try:
        content = state_path.read_text(encoding="utf-8")
    except OSError:
        return None
    lines = content.splitlines()
    needle = f"{key}:"
    for i, raw in enumerate(lines):
        if raw[:1] in (" ", "\t"):
            continue
        line = raw.split("#", 1)[0].rstrip()
        if not line.startswith(needle):
            continue
        inline = line.split(":", 1)[1].strip()
        if inline == "[]":
            return []
        items: list[str] = []
        for follow in lines[i + 1:]:
            if follow[:1] not in (" ", "\t") and follow.strip():
                break  # next column-0 key — the block ended
            stripped = follow.split("#", 1)[0].strip()
            if stripped.startswith("- "):
                value = stripped[2:].strip().strip("\"'")
                if value:
                    items.append(value)
            elif stripped:
                break  # non-list content under the key — stop, take what parsed
        return items
    return None


def _boundary_pattern_paths(prawduct_dir: Path) -> list[str]:
    """Literal backticked file paths from ``boundary-patterns.md`` — the
    product's documented contract surfaces. Globs and slash-commands are
    excluded by the shared ``_looks_like_file_path`` rule; an unfilled
    template (paths only inside HTML comments, unbackticked) yields none."""
    path = prawduct_dir / "artifacts" / "boundary-patterns.md"
    if not path.is_file():
        return []
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return []
    seen: list[str] = []
    for token in _BACKTICK_RE.findall(content):
        token = token.strip()
        if _looks_like_file_path(token) and token not in seen:
            seen.append(token)
    return seen


def _surface_matches(path: str, surface: str) -> bool:
    if surface.endswith("/"):
        return path.startswith(surface)
    return fnmatch(path, surface)


#: Provenance labels for :func:`resolve_surfaces` — also the stderr text, so a
#: caller can tell a declared opt-in from the framework defaults.
SOURCE_DECLARED = "declared risk_surfaces"
SOURCE_DERIVED = "derived defaults"


def resolve_surfaces(prawduct_dir: Path) -> tuple[list[str], str]:
    """The risk surfaces in force plus their provenance — resolution order
    steps 1-2 of the module docstring, in ONE place so every consumer answers
    "is this a risk surface" identically.

    A ``risk_surfaces:`` key is exclusive when present (declared-empty is a
    deliberate opt-out and returns ``[]``); otherwise the derived defaults plus
    the product's documented contract paths.
    """
    declared = _read_list_yaml_key(prawduct_dir / "project-state.yaml", "risk_surfaces")
    if declared is not None:
        return list(declared), SOURCE_DECLARED
    return (
        [*DERIVED_DEFAULT_SURFACES, *_boundary_pattern_paths(prawduct_dir)],
        SOURCE_DERIVED,
    )


def has_product_risk_declaration(prawduct_dir: Path) -> bool:
    """True when THIS REPO has said where its risk concentrates — a non-empty
    ``risk_surfaces:`` list, or contract paths documented in
    ``boundary-patterns.md``.

    The derived defaults deliberately do NOT count. They are framework-shaped
    (``skills/``, ``lib/gates*``, ``bin/*hook*``), so in an onboarded product
    they describe the *plugin's* hot spots and typically match nothing in the
    product's own tree — and an as-scaffolded product declares neither key: the
    `project-state.yaml` template has no ``risk_surfaces:`` and the
    `boundary-patterns.md` template writes its examples inside HTML comments,
    unbackticked, so :func:`_boundary_pattern_paths` yields zero.

    So any consumer deciding on "no risk surface matched" MUST distinguish
    *"this diff is low-risk"* from *"this repo never had a risk signal to
    give"* — they look identical at the match site and mean opposite things.
    :func:`critic_consolidate._derive_roster` is the caller that cares.

    An explicit ``risk_surfaces: []`` reads as no signal here, not as an opt-in
    to risk-keyed behaviour. That is the safe direction: the empty list turns
    the risk predicate off permanently, and a consumer that treated it as a
    declaration would fall through to whatever its no-risk branch does.
    """
    declared = _read_list_yaml_key(prawduct_dir / "project-state.yaml", "risk_surfaces")
    if declared:
        return True
    return bool(_boundary_pattern_paths(prawduct_dir))


def surface_matches(
    paths: "list[str]", surfaces: "list[str]"
) -> list[tuple[str, str]]:
    """Every ``(path, surface)`` pair where a reviewed path lands on a risk
    surface. Empty means the scope touches no declared risk."""
    return [
        (path, surface)
        for path in paths
        for surface in surfaces
        if _surface_matches(path, surface)
    ]


def paths_touch_risk_surface(prawduct_dir: Path, paths: "list[str]") -> tuple[bool, str]:
    """``(touched, rationale)`` for a set of already-known paths — the
    pure-path entry point used by roster derivation, which has its diff in
    hand and must not shell out to git again.

    Distinct from :func:`classify_diff_risk`, which derives the scope from git
    and owns the fail-open/closed asymmetry: there is no git call here, so
    there is no unverifiable-diff case to fail closed on.
    """
    surfaces, source = resolve_surfaces(prawduct_dir)
    if not surfaces:
        return False, f"no risk surfaces ({source})"
    matches = surface_matches(paths, surfaces)
    if not matches:
        return False, f"no risk-surface paths ({source})"
    path, surface = matches[0]
    more = f" (+{len(matches) - 1} more)" if len(matches) > 1 else ""
    return True, f"{path} matched risk surface {surface}{more} ({source})"


def _git_lines(project_dir: Path, *args: str) -> list[str] | None:
    """Lines of one git read; ``None`` on any failure (callers decide whether
    that fails open or closed — see module docstring)."""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(project_dir), capture_output=True, text=True, timeout=30,
        )
    except Exception:  # prawduct:allow prawduct/broad-except -- verdict degrades per the declared fail-open/closed rule, never crashes
        return None
    if proc.returncode != 0:
        return None
    return [ln for ln in proc.stdout.splitlines() if ln.strip()]


def _review_scope_paths(project_dir: Path, base: str | None) -> list[str] | None:
    """The paths a final/cumulative review covers: committed names in
    ``merge-base(base)...HEAD`` plus working-tree changed/untracked names.
    ``None`` when git evaluation fails (the fail-open/closed branch point)."""
    paths: list[str] = []
    if base is not None:
        merge_base_lines = _git_lines(project_dir, "merge-base", base, "HEAD")
        if not merge_base_lines:
            return None
        committed = _git_lines(
            project_dir, "diff", "--name-only", f"{merge_base_lines[0]}..HEAD"
        )
        if committed is None:
            return None
        paths.extend(committed)
    # --untracked-files=all: the default collapses an untracked directory to
    # one "?? dir/" line, hiding the files inside it from glob surfaces
    # (e.g. `lib/gates*` never sees a file under an untracked `lib/`) — a
    # silently missed escalation. Caught by test_uncommitted_work_counts.
    porcelain = _git_lines(project_dir, "status", "--porcelain", "--untracked-files=all")
    if porcelain is None:
        return None
    for line in porcelain:
        body = line[3:] if len(line) > 3 else ""
        # Rename lines are "R  old -> new" — the new path is the review scope.
        if " -> " in body:
            body = body.split(" -> ", 1)[1]
        body = body.strip().strip('"')
        if body:
            paths.append(body)
    deduped: list[str] = []
    for p in paths:
        if p not in deduped:
            deduped.append(p)
    return deduped


def classify_diff_risk(project_dir: Path, argv: list[str]) -> int:
    """Body of ``prawduct-hook classify-diff-risk [<base>]`` — see module
    docstring for the resolution order, output contract, and failure rules."""
    base_arg: str | None = None
    for arg in argv:
        if arg.startswith("-"):
            print(
                f"classify-diff-risk: unknown argument {arg!r} "
                "(usage: classify-diff-risk [<base>])",
                file=sys.stderr,
            )
            return 1
        if base_arg is not None:
            print(
                "classify-diff-risk: at most one <base> argument",
                file=sys.stderr,
            )
            return 1
        base_arg = arg

    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    surfaces, source = resolve_surfaces(prawduct_dir)
    declared = surfaces if source == SOURCE_DECLARED else None

    if not surfaces:
        # Declared-empty opt-out: nothing can ever match, so the diff doesn't
        # need evaluating and git failures are moot.
        print("no risk surfaces (risk_surfaces declared empty)", file=sys.stderr)
        print("standard")
        return 0

    if base_arg is not None:
        base = base_arg
    else:
        from . import coverage  # noqa: PLC0415 — lazy keeps risk import light

        base, base_reason = coverage._resolve_base_branch(project_dir)
        if base is None:
            # No resolvable base: classify the working tree alone rather than
            # treating an un-based repo (fresh init) as a git failure.
            print(f"note: no diff base ({base_reason}); classifying working tree only", file=sys.stderr)

    paths = _review_scope_paths(project_dir, base)
    if paths is None:
        if declared is not None:
            print(
                "escalate: risk surfaces are declared but the diff could not "
                "be evaluated (git failure) — declared risk with an "
                "unverifiable diff must not get the standard-tier reviewer.",
                file=sys.stderr,
            )
            print("escalate")
        else:
            print(
                "note: diff could not be evaluated (git failure); no surfaces "
                "declared — defaulting to standard.",
                file=sys.stderr,
            )
            print("standard")
        return 0

    matches = surface_matches(paths, surfaces)
    if matches:
        for path, surface in matches:
            print(f"risk: {path} matched {surface}", file=sys.stderr)
        print(f"({source}; {len(matches)} matched path(s))", file=sys.stderr)
        print("escalate")
    else:
        print(f"no risk-surface paths in scope ({source}, {len(paths)} path(s))", file=sys.stderr)
        print("standard")
    return 0
