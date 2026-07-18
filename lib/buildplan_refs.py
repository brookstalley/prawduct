"""Build-plan reference parsing + trivial-change classification for the runtime.

Extracted from ``bin/prawduct-hook`` (STH-9V4K, Chunk 3) — the build-plan
parsing cluster: it reads the active build plan's Status section and per-chunk
sections (file-path refs, ``Type:`` declaration, ``Trivial because:`` rationale)
and classifies a single file change against the ``Type: trivial`` / doc-only
file-set bounds. Pure parsing + path inspection — no git mutation, no network.

Depends only on its lib siblings ``gitstate`` (for ``_is_metadata_path``) and
``core`` (for ``resolve_build_plan_path``) plus the stdlib — a clean DAG node
(``gitstate`` ← ``buildplan_refs``). The hook's inline build-plan-resolution
mirror (``_resolve_build_plan_path``) stays in the hook for its import-light hot
path; this module is a lib citizen and reaches the canonical resolver in
``lib.core`` directly, exactly as ``critic_mode`` and ``views`` do.

``_parse_build_plan_status`` was reassigned here from the briefing cluster (it is
build-plan parsing, not briefing assembly) — that reassignment turns the hook's
concern clusters into an acyclic dependency graph (STH-9V4K constraint 2). The
hook calls these lazily via ``_buildplan_refs()``, keeping its top level lib-free.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import gitstate
from .core import resolve_build_plan_path


def _iter_status_section_lines(content: str):
    """Yield stripped lines inside the build plan's ``## Status`` section.

    The one canonical Status-section walk (BLD-6Q1N): starts after a line that
    is exactly ``## Status``, stops at the next ``## `` heading, and skips
    HTML-comment spans (``<!-- ... -->``, multi-line). This skeleton was
    previously copied in five readers across ``buildplan_refs`` / ``gates`` /
    ``critic_mode``; all of them now fold onto this generator. (The index-based
    Status *rewriter* in ``lib/views.py`` is deliberately separate — it splices
    lines back into the file, so it needs positions, not a reader's view.)
    """
    in_status = False
    in_comment = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "## Status":
            in_status = True
            continue
        if not in_status:
            continue
        if stripped.startswith("## ") and stripped != "## Status":
            break
        if "<!--" in stripped:
            in_comment = True
        if "-->" in stripped:
            in_comment = False
            continue
        if in_comment:
            continue
        yield stripped


def _iter_status_section_items(content: str):
    """Yield ``(checked, text)`` for each ``- [ ]`` / ``- [x]`` Status item."""
    for stripped in _iter_status_section_lines(content):
        if stripped.startswith("- [ ]"):
            yield False, stripped[5:].strip()
        elif stripped.startswith("- [x]") or stripped.startswith("- [X]"):
            yield True, stripped[5:].strip()


# Build-plan chunk id extraction — the two supported forms:
#   "### Chunk 02: Name"            (H3, colon — the template default)
#   "## Chunk 2 (RES-K3QP) — Name"  (H2, optional "(ID)", en/em dash — research plans)
# The id is the first whitespace-delimited word after "Chunk", and it MUST be
# followed by a separator (``: — – - (``) or end-of-line — so a notes heading
# like "### Chunk 2 build-session decisions" is NOT mistaken for chunk 2's
# deliverable heading. Leading zeros are tolerated downstream ("2" matches
# "### Chunk 02:"). Previously only the colon form parsed, so an em-dash heading
# silently disabled Goal-2 ref verification and per-chunk mode scoping for the
# whole plan.
_CHUNK_ID_SEP = r"\s*(?:[:—–(-]|$)"
_CHUNK_HEADING_RE = re.compile(r"^#{2,3}\s+Chunk\s+(\w+)" + _CHUNK_ID_SEP)
_CHUNK_ITEM_RE = re.compile(r"^Chunk\s+(\w+)" + _CHUNK_ID_SEP)


def _chunk_id_from_item_text(text: str) -> str | None:
    """``"Chunk 02: name"`` / ``"Chunk 2 (ID) — name"`` → ``"02"`` / ``"2"``;
    ``None`` for non-chunk items. Accepts the colon (``### Chunk N:``) and the
    em/en-dash + optional ``(ID)`` (``## Chunk N (ID) — name``) forms."""
    m = _CHUNK_ITEM_RE.match(text)
    return m.group(1) if m else None


def _count_build_plan_chunks(prawduct_dir: Path) -> tuple[int, int]:
    """Count chunks in the active build plan's Status section.

    Resolves the plan via the ``active_build_plan:`` pointer (falls back to
    ``artifacts/build-plan.md``), so scope-named plans are counted too.
    Returns ``(total, complete)``; ``(0, 0)`` if the plan or its Status section
    is missing or unreadable. The single canonical implementation — consumed by
    ``lib.gates`` (end-of-cycle synthesis gate) and ``lib.critic_mode`` (mode
    inference), which carried near-duplicate copies until STH-2K8R/BLD-6Q1N.
    """
    plan_path = resolve_build_plan_path(prawduct_dir)
    if not plan_path.is_file():
        return 0, 0
    try:
        content = plan_path.read_text()
    except (OSError, UnicodeDecodeError):
        return 0, 0
    total = 0
    complete = 0
    for checked, _text in _iter_status_section_items(content):
        total += 1
        if checked:
            complete += 1
    return total, complete


def _chunk_ids_in_status_order(prawduct_dir: Path) -> list[str]:
    """Raw chunk ids (e.g. ``"01"``) in build-plan Status order, both states.

    Returns the ordered ``Chunk <id>:`` ids for ``- [ ]`` and ``- [x]`` items
    alike, so a git-derived progress count can map to the right current chunk
    (CRT-7B4M — see ``lib.critic_mode._git_aware_progress``, its consumer).
    Empty list when the plan or its Status section is missing or unreadable.
    """
    plan_path = resolve_build_plan_path(prawduct_dir)
    if not plan_path.is_file():
        return []
    try:
        content = plan_path.read_text()
    except (OSError, UnicodeDecodeError):
        return []
    ids: list[str] = []
    for _checked, text in _iter_status_section_items(content):
        cid = _chunk_id_from_item_text(text)
        if cid:
            ids.append(cid)
    return ids


def _parse_build_plan_status(prawduct_dir: Path) -> dict[str, str]:
    """Parse work context from build-plan.md Status section.

    Returns dict with keys matching _parse_wip output:
    description, size, type, current_chunk, context, governance_level.
    Returns empty dict if no build plan or no Status section.
    """
    plan_path = resolve_build_plan_path(prawduct_dir)
    if not plan_path.is_file():
        return {}
    try:
        content = plan_path.read_text()
        result: dict[str, str] = {}

        # Extract title from header: "# Build Plan — Title (date)"
        for line in content.splitlines():
            if line.startswith("# Build Plan"):
                title = line.lstrip("# ").removeprefix("Build Plan").strip()
                if title.startswith("—") or title.startswith("-"):
                    title = title.lstrip("—- ").strip()
                # Remove trailing date in parens
                if title.endswith(")") and "(" in title:
                    title = title[:title.rfind("(")].strip()
                if title:
                    result["description"] = title
                break

        # Extract Size and Type from metadata line: **Size**: X | **Type**: Y
        for line in content.splitlines():
            if "**Size**:" in line:
                for segment in line.split("|"):
                    segment = segment.strip()
                    if segment.startswith("**Size**:"):
                        result["size"] = segment.removeprefix("**Size**:").strip()
                    elif segment.startswith("**Type**:"):
                        result["type"] = segment.removeprefix("**Type**:").strip()
                    elif segment.startswith("**Governance**:"):
                        result["governance_level"] = segment.removeprefix("**Governance**:").strip()
                break

        # Parse Status section for current chunk and context
        has_any_items = False
        for stripped in _iter_status_section_lines(content):
            # Current chunk = first unchecked item
            if stripped.startswith("- [ ]") and "current_chunk" not in result:
                has_any_items = True
                result["current_chunk"] = stripped[5:].strip()
            elif stripped.startswith("- [x]") or stripped.startswith("- [X]"):
                has_any_items = True
            # Context line
            if stripped.startswith("Context:"):
                result["context"] = stripped.removeprefix("Context:").strip()

        # Mark whether Status section had items (for staleness detection)
        if has_any_items:
            result["_has_status_items"] = "true"

        return result
    except Exception:  # prawduct:allow prawduct/broad-except -- build plan parsing is best-effort
        return {}


_BUILD_PLAN_PATH_RE = re.compile(r"`([^`\s]+)`")
_BUILD_PLAN_NEW_QUALIFIER_RE = re.compile(r"\bnew\s+`([^`\s]+)`")
# Per-chunk Type declaration (v1.4 F6 — proportional Critic via chunk type).
# Matches `- **Type:** <token>` or `**Type:** <token>` as a list item; trailing
# parenthetical prose is allowed and ignored.
_BUILD_PLAN_TYPE_RE = re.compile(r"^[\s\-\*]*\*\*Type:\*\*\s*([A-Za-z][\w\-]*)")
# v1.5 Chunk 04 — `trivial` joins the allowed set. File-set bounds (no
# edits under skills/, methodology/, templates/; no CLAUDE.md edit; no
# test deletion; no new files) + required `**Trivial because:**`
# rationale are enforced structurally; semantic-fit is Critic Goal 3 in
# Chunk 05. Size is unbounded — trivial is a semantic claim, not a LOC
# metric.
_BUILD_PLAN_ALLOWED_TYPES = frozenset(
    {"code", "doc-only", "cleanup", "designer-handoff", "cumulative-final", "trivial"}
)
# `**Trivial because:** <rationale>` — first line; continuation lines (no
# list-item / heading prefix) are joined onto the rationale until the next
# field. Empty after the colon → missing-rationale.
_BUILD_PLAN_TRIVIAL_RATIONALE_RE = re.compile(
    r"^[\s\-\*]*\*\*Trivial because:\*\*\s*(.*)$"
)


def _looks_like_file_path(token: str) -> bool:
    """A backticked token is a precise file-path reference only when it
    contains ``/`` — i.e. the chunk author wrote a specific relative path.
    Bare filenames in prose (e.g. ``backlog.md``, ``SKILL.md``) are usually
    conceptual references whose actual location varies, so they're not
    verifiable in a useful way.

    Slash-commands (``/prawduct:pr``, ``/prawduct:learnings``, ``/prawduct:critic``) also contain
    ``/`` but are not file paths. Exclude tokens that start with ``/``,
    have no further ``/``, and contain no ``.`` — that shape is a single
    slash-command identifier, not a path.

    Glob patterns written in prose (e.g. ``docs/requirements/*.md`` in a Tests
    bullet) also contain ``/`` but name a *set*, not a literal file — a literal
    source path never contains the shell-glob metacharacters ``*``, ``?``, or
    ``[``, so a token carrying one is a glob to skip rather than a missing file
    to flag (BLD-2R9X). Sibling of the ``path::symbol`` carveout the chunk-ref
    parser applies before calling this.

    Write-target templates with angle-bracket placeholders (e.g.
    ``<inbox>/<kebab-slug>.md``) and URLs (e.g. ``https://example.com/x``) also
    contain ``/`` but are not literal on-disk paths — a token carrying ``<``,
    ``>``, or ``://`` is a placeholder/URL to skip, not a missing file to flag
    (BLD-4K7P; same form-family as the glob carveout above)."""
    if "/" not in token:
        return False
    if token.startswith("/") and "/" not in token[1:] and "." not in token:
        return False
    if any(ch in token for ch in "*?["):
        return False
    if "<" in token or ">" in token:
        return False
    if "://" in token:
        return False
    return True


def _chunk_section_lines(
    content: str, chunk_id: str
) -> tuple[bool, list[tuple[int, str]]]:
    """Locate the ``Chunk <chunk_id>`` section and return its body lines.

    The one canonical chunk-section walk: name-anchored with leading-zero
    tolerance (``"02"`` matches ``### Chunk 2:`` and vice versa), matches both
    supported heading forms (``### Chunk NN: Name`` and ``## Chunk N (ID) — Name``
    via ``_CHUNK_HEADING_RE``), stops at the next sibling chunk heading or a
    non-chunk ``## `` heading, and drops fenced code blocks (project-structure
    diagrams aren't load-bearing prose). Returns
    ``(found, [(line_num, raw_line), ...])`` with 1-based line numbers into
    ``content``. This skeleton was previously copied in the three chunk-field
    parsers below and ``lib.critic_mode``'s ``**Critic mode:**`` reader; all
    four now fold onto it.
    """
    target = chunk_id.lstrip("0") or "0"
    in_section = False
    in_fence = False
    section_lines: list[tuple[int, str]] = []
    for line_num, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        heading = _CHUNK_HEADING_RE.match(stripped)
        if heading:
            head_norm = heading.group(1).lstrip("0") or "0"
            if in_section:
                # Entered a sibling chunk; stop accumulating.
                break
            if head_norm == target:
                in_section = True
            continue
        if not in_section:
            continue
        if stripped.startswith("## "):
            # Left the Build Chunks section entirely (a non-chunk H2).
            break
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        section_lines.append((line_num, line))
    return in_section, section_lines


def _parse_build_plan_chunk_refs(prawduct_dir: Path, chunk_id: str) -> dict:
    """Extract backticked file-path references from a single chunk's section
    in ``.prawduct/artifacts/build-plan.md``.

    The section is located by ``_chunk_section_lines`` (both the ``### Chunk NN:``
    and ``## Chunk N (ID) — Name`` heading forms, leading zeros tolerant), and
    parsing stops at the next sibling chunk heading or a non-chunk ``## `` heading
    — sibling chunks' refs are NOT returned. Fenced code blocks (```...```)
    are skipped because project-structure diagrams aren't load-bearing prose.
    Paths preceded by the word ``new`` on the same line are skipped as
    intra-chunk forward references (files the chunk creates rather than
    modifies).

    Returns ``{"file_paths": [{"line_num": int, "ref": str}, ...],
    "error": str | None}``. For a ``path::symbol`` token the stored ``ref`` is
    the pre-``::`` path only (existence-checked), and the symbol is ignored —
    symbol and backlog-ID verification remain deferred (BLD-5V8F).
    """
    result: dict = {"file_paths": [], "error": None}
    plan_path = resolve_build_plan_path(prawduct_dir)
    if not plan_path.is_file():
        result["error"] = f"missing build-plan: {plan_path}"
        return result
    try:
        content = plan_path.read_text()
    except OSError as exc:
        result["error"] = f"unreadable build-plan: {exc}"
        return result

    found, section_lines = _chunk_section_lines(content, chunk_id)
    if not found:
        result["error"] = f"chunk {chunk_id!r} not found in build-plan"
        return result

    seen: set[tuple[str, int]] = set()
    for line_num, line in section_lines:
        # Collect spans preceded by "new " — these get filtered out.
        excluded_spans: list[tuple[int, int]] = [
            m.span(1) for m in _BUILD_PLAN_NEW_QUALIFIER_RE.finditer(line)
        ]
        for match in _BUILD_PLAN_PATH_RE.finditer(line):
            token = match.group(1)
            # A `path::symbol` token (e.g. `lib/views.py::is_views_enabled`) is
            # verified by its FILE path only — existence-check the pre-`::` part,
            # not the whole token, so a valid file isn't reported missing
            # (BLD-8F2Q). The symbol half stays deferred (BLD-5V8F).
            path_part = token.split("::", 1)[0]
            if not _looks_like_file_path(path_part):
                continue
            # The `new ` forward-ref exclusion keys on the token START offset,
            # which a trailing `::symbol` does not move, so it still composes.
            if any(start == match.start(1) for start, _ in excluded_spans):
                continue
            key = (path_part, line_num)
            if key in seen:
                continue
            seen.add(key)
            result["file_paths"].append({"line_num": line_num, "ref": path_part})
    return result


def _parse_build_plan_chunk_type(
    prawduct_dir: Path, chunk_id: str
) -> tuple[str | None, str | None]:
    """Extract the `Type:` declaration from a chunk's build-plan section.

    Returns ``(chunk_type, error)``. ``chunk_type`` is one of
    ``code | doc-only | cleanup | designer-handoff | cumulative-final | trivial``.
    Default (field absent) is ``code`` — fail-closed so a missing declaration
    runs the full Critic protocol rather than silently triggering a carveout
    (learnings: "escape hatches in classification create silent failures").
    Unknown values surface as ``(None, "unknown type: <value>")`` so the
    author fixes the typo instead of getting silent fall-through.

    Section discovery is the shared ``_chunk_section_lines`` walker —
    name-anchored on ``### Chunk <chunk_id>:`` with leading-zero tolerance;
    fenced code blocks are skipped.
    """
    plan_path = resolve_build_plan_path(prawduct_dir)
    if not plan_path.is_file():
        return None, f"missing build-plan: {plan_path}"
    try:
        content = plan_path.read_text()
    except OSError as exc:
        return None, f"unreadable build-plan: {exc}"

    found, section_lines = _chunk_section_lines(content, chunk_id)
    if not found:
        return None, f"chunk {chunk_id!r} not found in build-plan"

    declared: str | None = None
    for _line_num, line in section_lines:
        m = _BUILD_PLAN_TYPE_RE.match(line)
        if m:
            declared = m.group(1)
            break

    if declared is None:
        return "code", None  # fail-closed default
    if declared not in _BUILD_PLAN_ALLOWED_TYPES:
        allowed = ", ".join(sorted(_BUILD_PLAN_ALLOWED_TYPES))
        return None, f"unknown type: {declared!r} (allowed: {allowed})"
    return declared, None


def _parse_build_plan_chunk_trivial_rationale(
    prawduct_dir: Path, chunk_id: str
) -> tuple[str | None, str | None]:
    """Extract the ``**Trivial because:**`` rationale from a chunk's section.

    Returns ``(rationale, error)``. Empty or absent field → ``(None,
    "missing-rationale: Type: trivial requires non-empty **Trivial
    because:** field")``. Multi-line rationale (continuation lines without
    a list-item / heading prefix) is joined into a single string until the
    next field.

    Section discovery is the shared ``_chunk_section_lines`` walker —
    name-anchored on ``### Chunk <chunk_id>:`` with leading-zero tolerance;
    fenced code blocks are skipped.
    """
    plan_path = resolve_build_plan_path(prawduct_dir)
    if not plan_path.is_file():
        return None, f"missing build-plan: {plan_path}"
    try:
        content = plan_path.read_text()
    except OSError as exc:
        return None, f"unreadable build-plan: {exc}"

    found, section_lines = _chunk_section_lines(content, chunk_id)
    if not found:
        return None, f"chunk {chunk_id!r} not found in build-plan"

    capturing = False
    rationale_lines: list[str] = []
    for _line_num, line in section_lines:
        stripped = line.strip()
        m = _BUILD_PLAN_TRIVIAL_RATIONALE_RE.match(line)
        if m:
            capturing = True
            first = m.group(1).strip()
            if first:
                rationale_lines.append(first)
            continue
        if capturing:
            # Stop at the next list-item field, bolded label, or sub-heading.
            if (
                stripped.startswith("- **")
                or stripped.startswith("* **")
                or stripped.startswith("**")
                or stripped.startswith("#")
            ):
                break
            if stripped:
                rationale_lines.append(stripped)

    if not capturing:
        return None, (
            "missing-rationale: Type: trivial requires non-empty "
            "**Trivial because:** field"
        )
    rationale = " ".join(rationale_lines).strip()
    if not rationale:
        return None, (
            "missing-rationale: Type: trivial requires non-empty "
            "**Trivial because:** field"
        )
    return rationale, None


# STH-1W5N — single source of truth for the unconditional ``Type: trivial`` /
# doc-only protected-path bounds. Each entry is ``(path, is_exact, reason_label)``:
# a change touching ``path`` (prefix match unless ``is_exact``) is a
# catastrophic-blast-radius edit that a trivial/doc-only chunk may never make,
# and the violation is reported as ``"<reason_label>: <path>"``. Centralized
# here (was inline in ``_classify_trivial_change``) so the stop-hook gate and
# the PR-boundary gate share one provably-identical list — and so the bound set
# is testable as data. The conditional bounds (test-file removals, newly-tracked
# files) stay in ``_classify_trivial_change`` because they depend on the change
# verb, not just the path.
#   skills/       — the critic/pr/etc. SKILL definitions + bundled protocols ARE
#                   the governance; editing one changes the framework itself.
#   methodology/  — the build/discovery/planning/reflection guides Claude reads
#                   as operating instructions; a "trivial" rewrite is never trivial.
#   templates/    — the artifact templates every product's specs are generated
#                   from; a silent change propagates to all downstream output.
#   CLAUDE.md     — the project's top-level operating contract (exact match —
#                   a nested ``foo/CLAUDE.md`` is ordinary product doc).
_TRIVIAL_PROTECTED_PATHS: frozenset[tuple[str, bool, str]] = frozenset({
    ("skills/", False, "skill-file-edited"),
    ("methodology/", False, "methodology-edited"),
    ("templates/", False, "template-edited"),
    ("CLAUDE.md", True, "claude-md-edited"),
})


def protected_path_violation(path: str) -> str | None:
    """Return the violation label (``"<reason_label>: <path>"``) when *path*
    falls under a governance-protected bound (``skills/``, ``methodology/``,
    ``templates/``, root ``CLAUDE.md``), else ``None``.

    Shared by the ``Type: trivial`` gate (via ``_classify_trivial_change``)
    and the PR-boundary doc-only gate (``lib/coverage.py``, PR-5K8D): fork-
    skill prose is behavioral logic in this framework, so a ``skills/*.md``
    change must never ride a doc-only fast path past the reviewers."""
    for protected, is_exact, reason_label in _TRIVIAL_PROTECTED_PATHS:
        matched = path == protected if is_exact else path.startswith(protected)
        if matched:
            return f"{reason_label}: {path}"
    return None


def _classify_trivial_change(
    *,
    path: str,
    src_path: str | None,
    is_addition: bool,
    is_deletion: bool,
) -> str | None:
    """Single-file path-rule check for the ``Type: trivial`` file-set
    bounds. Returns the violation reason or ``None`` when the change
    is eligible. Used by ``_is_trivial_fileset_eligible`` (Chunk 04 —
    working-tree porcelain) to enforce a *declared* ``Type: trivial``
    chunk at session-end. (The ``_pr_diff_is_trivial`` PR-boundary
    co-consumer was retired — it used these bounds as a triviality
    *detector* at the bundle boundary, with no link to a ``Type: trivial``
    declaration, so multi-chunk feature work that only touched existing
    files skipped both review gates.)

    The unconditional path bounds live in the module-level
    ``_TRIVIAL_PROTECTED_PATHS`` constant (STH-1W5N — single source of
    truth, referenced from this one call site). The conditional bounds
    (test-file removals, newly-tracked files) stay inline below because
    they depend on the change verb, not just the path.

    Metadata paths (``.prawduct/``, ``.claude/settings.json``, etc. —
    see ``_is_metadata_path``) are treated as out-of-scope and return
    ``None``. The check applies to BOTH ``path`` (rename dst / single-
    file change) AND ``src_path`` (rename src) — without that
    symmetry, a rename FROM a metadata path that landed somewhere
    interesting would silently be classified, and a rename TO a
    metadata path would be classified differently depending on which
    gate ran (the callers previously did dst-only filtering before
    calling this helper — v1.5.1 Chunk 04(b) consolidates).

    The caller translates its status format into the boolean inputs
    (porcelain handles 2-char codes; name-status handles single-char).
    Path bounds are catastrophic-blast-radius classes regardless of
    size — size is intentionally not a bound.
    """
    if gitstate._is_metadata_path(path):
        return None
    if src_path is not None and gitstate._is_metadata_path(src_path):
        return None
    # Unconditional path bounds — shared with the PR-boundary doc-only gate
    # via protected_path_violation (one provably-identical list).
    violation = protected_path_violation(path)
    if violation is not None:
        return violation
    if is_deletion and path.startswith("tests/"):
        return f"test-file-deleted: {path}"
    if src_path is not None and src_path.startswith("tests/"):
        return f"test-file-deleted: {src_path} (renamed out)"
    if is_addition:
        return f"new-file: {path}"
    return None


def _current_chunk_id_from_status(prawduct_dir: Path) -> str | None:
    """Extract the chunk id of the first `- [ ]` item in the build-plan Status
    section, e.g. ``"03"`` for ``- [ ] Chunk 03: Foo`` and ``"2"`` for
    ``- [ ] Chunk 2 (ID) — Foo``. Returns ``None`` if Status is missing, has no
    current chunk (all complete), or the item isn't a recognized chunk form.

    Mirrors the resolution logic in ``cmd_verify_chunk_refs`` so the stop
    hook and the Critic helper agree on "which chunk is current."
    """
    status = _parse_build_plan_status(prawduct_dir)
    return _chunk_id_from_item_text(status.get("current_chunk", ""))


def _verify_chunk_refs(project_dir: Path, refs: dict) -> list[dict]:
    """Verify each file-path ref exists relative to ``project_dir``.
    Returns a list of ``{"kind", "ref", "line_num", "reason"}`` for missing
    entries. Empty list = all refs resolved.
    """
    missing: list[dict] = []
    for entry in refs.get("file_paths", []):
        ref = entry["ref"]
        target = project_dir / ref
        if not target.exists():
            if gitstate.git_path_is_ignored(project_dir, ref):
                # BLD-4K7P: an intentionally-gitignored managed path (e.g.
                # `.prawduct/.bug-inbox`) is a generated/managed file,
                # legitimately absent from a fresh checkout — not a missing
                # deliverable. Skip rather than cry wolf.
                continue
            missing.append({
                "kind": "file_path",
                "ref": ref,
                "line_num": entry["line_num"],
                "reason": "file does not exist",
            })
    return missing
