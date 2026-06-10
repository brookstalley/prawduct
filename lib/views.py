"""Derived-view builders for the prawduct work-log canonical store.

When `.prawduct/project-state.yaml` has `views_enabled: true`, the build-plan
`## Status` block becomes a derived view of `.prawduct/change-log.md` tagged
entries — `prawduct-hook regen-views` rewrites the checkboxes from
`status=shipped` tags. Chunk titles, the `## Status` heading, the introductory
HTML comment, and the freeform `Context:` line are author-curated; regen never
touches them.

Tagged-entry format (in change-log.md, on a line after each ``## YYYY-MM-DD:``
header — blank lines between are tolerated):

    <!-- prawduct: chunks=00,01,02 | release=v1.3.18 | status=shipped | scope=v1.4 -->

Recognized keys:

* ``chunks``  comma-separated chunk IDs (zero-padded, matching build-plan headers)
* ``release`` version string (used by release-notes view, Chunk 06)
* ``status``  ``shipped`` | ``merged`` — the two recognized values. Only
  ``shipped`` flips a checkbox to ``[x]``; ``merged`` is the release-pending
  intermediate (PR merged to develop, develop→main release still pending) and
  does NOT flip a checkbox.
* ``scope``   rollup identifier, e.g., ``v1.4``

Entries without a tag line are ignored — untagged historical entries coexist
with tagged ones. Only chunks with a ``status=shipped`` tag flip to ``[x]``;
all other Chunk lines flip to ``[ ]`` so the view is fully derived.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .core import read_bool_yaml_key, resolve_build_plan_path


TAG_LINE_RE = re.compile(r"<!--\s*prawduct:\s*(.+?)\s*-->")
H2_RE = re.compile(r"^##\s+(.+?)\s*$")
CHUNK_LINE_RE = re.compile(
    r"^(?P<prefix>\s*-\s+)\[(?P<state>[ xX])\](?P<rest>\s+Chunk\s+(?P<id>[A-Za-z0-9_-]+):.*)$"
)
# Safe charset for a chunk ID, mirroring CHUNK_LINE_RE's `id` group. A chunk ID
# is only ever a build-plan header token, so anything outside this set (a quote,
# `}`, `:`, whitespace) is malformed and — left unquoted/quoted naively — would
# corrupt the generated scope_rollups YAML (e.g. `chunks: ["0"a]`). Such IDs are
# dropped before they reach a derived view.
CHUNK_ID_SAFE_RE = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass
class ChangeLogEntry:
    """A change-log entry with optional tagged metadata."""

    title: str
    tags: dict[str, object] = field(default_factory=dict)
    line_number: int = 0  # 1-indexed line of the H2 header
    # How many `<!-- prawduct: ... -->` lines headed this entry. The canonical
    # format is exactly one; >1 means the tags above are a union (VWS-4D8J) and
    # validate_tag_line_multiplicity will warn.
    tag_line_count: int = 0
    # Scalar keys that appeared on a later tag line with a DIFFERENT value than
    # an earlier one — first-wins, the losing value recorded here for the warning.
    tag_conflicts: list[str] = field(default_factory=list)

    @property
    def shipped_chunks(self) -> list[str]:
        """Chunk IDs marked shipped by this entry, or []."""
        if self.tags.get("status") != "shipped":
            return []
        chunks = self.tags.get("chunks")
        if isinstance(chunks, list):
            return [c for c in chunks if isinstance(c, str)]
        return []


def parse_tag_line(tag_body: str) -> dict[str, object]:
    """Parse the body of a tag-line (between ``prawduct:`` and ``-->``).

    Pipe-delimited ``key=value`` pairs. ``chunks`` is split on commas into a list;
    other keys are kept as plain strings. Unknown keys are preserved as-is so
    future views can read them without a schema bump.
    """
    tags: dict[str, object] = {}
    for part in tag_body.split("|"):
        part = part.strip()
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        k = k.strip()
        v = v.strip()
        if not k:
            continue
        if k == "chunks":
            tags[k] = [c.strip() for c in v.split(",") if c.strip()]
        else:
            tags[k] = v
    return tags


def _merge_tag_line(entry: ChangeLogEntry, new_tags: dict[str, object]) -> None:
    """Merge a subsequent tag line's pairs into an entry, union semantics.

    ``chunks`` lists are concatenated with order-preserving dedup; a key not
    yet present is adopted; a scalar key already present with a *different*
    value is first-wins, the ignored value recorded in ``tag_conflicts`` so
    :func:`validate_tag_line_multiplicity` can surface it.
    """
    for k, v in new_tags.items():
        if k not in entry.tags:
            entry.tags[k] = v
            continue
        existing = entry.tags[k]
        if k == "chunks" and isinstance(existing, list) and isinstance(v, list):
            entry.tags[k] = existing + [c for c in v if c not in existing]
        elif existing != v:
            entry.tag_conflicts.append(f"{k}: kept {existing!r}, ignored {v!r}")


def parse_change_log(content: str) -> list[ChangeLogEntry]:
    """Parse change-log markdown into a list of entries.

    An entry is ``## YYYY-MM-DD: title`` followed (after up to a few blank
    lines) by ``<!-- prawduct: key=value | ... -->``. The tag block, if
    present, must begin before the next non-blank content line under the H2.

    The canonical format is ONE tag line per entry, but **all consecutive**
    tag lines at the head of the body are consumed (blank lines between them
    tolerated, the same leniency as before the first one) — the historical
    first-line-only parse silently dropped the later lines' ``chunks=`` at
    release time (VWS-4D8J). Multiple lines are unioned per
    :func:`_merge_tag_line`, ``tag_line_count`` records how many were seen,
    and :func:`validate_tag_line_multiplicity` warns on >1. A tag line after
    intervening prose is still later body content, never entry metadata.
    """
    entries: list[ChangeLogEntry] = []
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        m = H2_RE.match(lines[i])
        if not m:
            i += 1
            continue
        entry = ChangeLogEntry(title=m.group(1), line_number=i + 1)
        j = i + 1
        while j < len(lines):
            stripped = lines[j].strip()
            if not stripped:
                j += 1
                continue
            tag_match = TAG_LINE_RE.search(lines[j])
            if not tag_match:
                # First non-blank non-tag line ends the tag block.
                break
            new_tags = parse_tag_line(tag_match.group(1))
            entry.tag_line_count += 1
            if entry.tag_line_count == 1:
                entry.tags = new_tags
            else:
                _merge_tag_line(entry, new_tags)
            j += 1
        entries.append(entry)
        i += 1
    return entries


VALID_STATUS_VALUES = frozenset({"shipped", "merged"})


def validate_status_values(entries: list[ChangeLogEntry]) -> list[str]:
    """Return a warning string for each entry with an unrecognized ``status=`` tag.

    A change-log ``status=`` typo (e.g. ``status=shippd``) silently fails to flip
    a checkbox — the entry parses fine but ``shipped_chunks`` returns ``[]``, so
    the chunk never marks complete and the release driver sees no error. This
    pure helper surfaces those typos as non-fatal warnings: it flags every entry
    whose ``status=`` tag is PRESENT but not in ``{shipped, merged}``. Entries
    with no ``status=`` tag (untagged historical entries) are not flagged.

    Returns ``[]`` when every status value is valid or absent.
    """
    warnings: list[str] = []
    for entry in entries:
        status = entry.tags.get("status")
        if status is None:
            continue
        if status not in VALID_STATUS_VALUES:
            warnings.append(
                f"change-log entry {entry.title!r} (line {entry.line_number}) "
                f"has unrecognized status={status!r} — expected one of "
                f"{sorted(VALID_STATUS_VALUES)}; this entry will not flip any "
                f"checkbox. Likely a typo."
            )
    return warnings


def validate_tag_line_multiplicity(entries: list[ChangeLogEntry]) -> list[str]:
    """Return a warning string for each entry parsed from >1 tag line.

    The canonical change-log format is one ``<!-- prawduct: ... -->`` line per
    entry. :func:`parse_change_log` now unions consecutive tag lines rather
    than silently dropping the later ones (VWS-4D8J — a second line's
    ``chunks=`` nearly shipped unflipped at v2.1.0), but the union is a repair,
    not a blessing: this pure helper (mirroring :func:`validate_status_values`)
    surfaces each multi-tag entry as a non-fatal warning so the author merges
    the lines. Conflicting scalar keys were kept first-wins; the warning names
    the ignored values.

    Returns ``[]`` when every entry has at most one tag line.
    """
    warnings: list[str] = []
    for entry in entries:
        if entry.tag_line_count <= 1:
            continue
        msg = (
            f"change-log entry {entry.title!r} (line {entry.line_number}) has "
            f"{entry.tag_line_count} prawduct tag lines — the canonical format "
            f"is one per entry; chunks= lists were unioned across them"
        )
        if entry.tag_conflicts:
            msg += (
                "; conflicting keys kept first-wins ("
                + "; ".join(entry.tag_conflicts)
                + ")"
            )
        msg += ". Merge them into a single tag line."
        warnings.append(msg)
    return warnings


def stamp_merged(content: str) -> tuple[str, list[str]]:
    """Stamp ``status=merged`` onto every statusless *tagged* entry.

    The change-log lifecycle is statusless (feature branch) → ``merged``
    (integrated) → ``shipped`` (released), but the merge flow historically
    never applied the middle stamp, so most entries reached release-prep
    statusless and a literal reading of the release checklist silently dropped
    them (REL-2N8K — v2.0.14 shipped 8 of 10 entries unflipped). This pure
    function is the stamping mechanism the ``stamp-merged`` hook command (and
    `/prawduct:pr` merge-flow step 6) applies on the integration branch.

    Semantics — deliberately convergent and idempotent: EVERY entry that has a
    tag line and no ``status=`` key is stamped, not only the just-merged
    branch's, so a previously missed stamp is repaired by the next merge.
    Entries with no tag line at all (historical, pre-convention) are never
    touched; entries already carrying any ``status=`` (including typos — the
    typo-guard owns those) are left alone. The stamp is appended to the FIRST
    tag line, preserving the existing pairs verbatim.

    Returns ``(new_content, stamped_titles)``; ``new_content is content`` is
    not guaranteed, but the text is unchanged when ``stamped_titles`` is empty.
    """
    lines = content.splitlines(keepends=True)
    stamped: list[str] = []
    for entry in parse_change_log(content):
        if entry.tag_line_count == 0 or "status" in entry.tags:
            continue
        # Locate the entry's first tag line: scan forward from the H2,
        # skipping blanks (the same leniency parse_change_log applies).
        for j in range(entry.line_number, len(lines)):
            if not lines[j].strip():
                continue
            m = TAG_LINE_RE.search(lines[j])
            # parse_change_log said tag_line_count > 0, so the first non-blank
            # line IS a tag line; the guard keeps a parser/scan drift from
            # corrupting a prose line.
            if m:
                body = m.group(1)
                lines[j] = lines[j].replace(
                    m.group(0), f"<!-- prawduct: {body} | status=merged -->", 1
                )
                stamped.append(entry.title)
            break
    return "".join(lines), stamped


def collect_shipped_chunks(
    entries: list[ChangeLogEntry], scope: str | None = None
) -> set[str]:
    """Aggregate shipped chunk IDs across all entries.

    When ``scope`` is set, only entries whose ``scope=`` tag equals ``scope``
    contribute — this prevents cross-version chunk-ID collisions (e.g., v1.4's
    ``chunks=05 | scope=v1.4`` flipping v1.5's chunk 05). When ``scope`` is
    ``None``, all shipped entries contribute (legacy unfiltered behavior).
    """
    shipped: set[str] = set()
    for entry in entries:
        if scope is not None and entry.tags.get("scope") != scope:
            continue
        shipped.update(entry.shipped_chunks)
    return shipped


def _parse_build_plan_frontmatter_scope(content: str) -> tuple[bool, str | None]:
    """Parse ``scope:`` from a build-plan's YAML frontmatter block.

    The frontmatter is the block bounded by ``---`` on its own line. A leading
    HTML comment block (``<!-- ... -->``) and blank lines before the opening
    ``---`` are tolerated — every real build-plan in the codebase begins with a
    comment header before the frontmatter, so requiring ``---`` on line 1 would
    make the field inert in practice.

    Returns a ``(present, value)`` tuple. ``present`` distinguishes "the
    ``scope:`` key appears in the frontmatter" from "the key is absent" — a
    distinction that matters because the two cases drive different fallback
    behavior in :func:`_detect_active_scope` (see BLD-4Q9X):

    * ``(True, "v1.5")`` — key present with a real value (quotes stripped).
    * ``(True, None)``   — key present but set to the YAML null literal
      (``null`` / ``~``) or left empty. This is the documented *explicit
      opt-out* form: the author is saying "do not scope-filter," and inference
      MUST be suppressed rather than silently inheriting a change-log scope.
    * ``(False, None)``  — key absent, nested inside another key, outside the
      frontmatter, the file lacks a frontmatter entirely, OR a leading HTML
      comment header is never closed (no ``-->``). The unclosed-comment case is
      handled LENIENTLY: the comment scan walks to EOF without finding ``-->``,
      so no ``---`` opener is located and the result is ``(False, None)`` — a
      safe "absent" reading that lets inference fall back to the change-log
      rather than raising on a malformed file. A real build-plan always closes
      its header, so this only affects hand-corrupted input.
    """
    lines = content.splitlines()
    i = 0
    # Skip leading blank lines, then any leading HTML comment block (possibly
    # multi-line). Build-plans conventionally start with a comment header.
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines) and lines[i].lstrip().startswith("<!--"):
        # Walk to the closing `-->` (inclusive). If the comment is UNCLOSED,
        # this walks to EOF; `i` then lands past the last line so the consume
        # below is skipped and the `i >= len(lines)` guard returns (False, None)
        # — a deliberately lenient reading of a malformed header (see docstring).
        while i < len(lines) and "-->" not in lines[i]:
            i += 1
        if i < len(lines):
            i += 1  # consume the line containing `-->`
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i >= len(lines) or lines[i].strip() != "---":
        return (False, None)
    for j in range(i + 1, len(lines)):
        line = lines[j]
        if line.strip() == "---":
            return (False, None)
        if line[:1] in (" ", "\t"):
            continue
        stripped = line.split("#", 1)[0].rstrip()
        if not stripped.startswith("scope:"):
            continue
        value = stripped.split(":", 1)[1].strip().strip('"').strip("'")
        # Key is present. An empty or null-literal value is an explicit
        # opt-out, not an absence — return (True, None) so callers can
        # suppress change-log inference.
        if not value or value.lower() in ("null", "~"):
            return (True, None)
        return (True, value)
    return (False, None)


def _detect_active_scope(
    build_plan_content: str, change_log_content: str | None = None
) -> str | None:
    """Detect the active scope for filtering change-log entries.

    Resolution order (highest precedence first):

    1. ``scope:`` field in build-plan YAML frontmatter — explicit, preferred.
       An explicit null/empty ``scope:`` is the author's opt-out: it pins the
       result to ``None`` and SKIPS change-log inference, so a stale prior
       ``scope=`` tag can't silently override the author's intent (BLD-4Q9X).
    2. Most recent change-log entry's ``scope=`` tag — inferred, but only when
       the build-plan ``scope:`` key is *absent* (not merely null).
    3. ``None`` — no scope detected; fail-safe to legacy unfiltered union.
    """
    present, fm_scope = _parse_build_plan_frontmatter_scope(build_plan_content)
    if fm_scope:
        return fm_scope
    if present:
        # Key was explicitly present but null/empty — an author opt-out.
        # Suppress inference: do not inherit a change-log scope.
        return None
    if change_log_content:
        entries = parse_change_log(change_log_content)
        for entry in entries:
            scope = entry.tags.get("scope")
            if isinstance(scope, str) and scope:
                return scope
    return None


def extract_status_section(content: str) -> tuple[int, int, list[str]]:
    """Find the ``## Status`` section.

    Returns ``(start_idx, end_idx_exclusive, section_lines)``. Section runs from
    the ``## Status`` line to (but not including) the next ``## `` H2 — matching
    the conventional build-plan layout. Returns ``(-1, -1, [])`` if absent.
    """
    lines = content.splitlines()
    start = -1
    for i, line in enumerate(lines):
        if line.startswith("## Status"):
            start = i
            break
    if start < 0:
        return (-1, -1, [])
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    return (start, end, lines[start:end])


def regenerate_status_section(
    section_lines: list[str], shipped_chunks: set[str]
) -> tuple[list[str], list[tuple[str, str, str]]]:
    """Rewrite Chunk checkbox lines from the shipped-chunks set.

    Returns ``(new_lines, changes)`` where each change is
    ``(chunk_id, old_state, new_state)`` with ``state`` in ``{" ", "x"}``.
    Non-chunk lines (the ``## Status`` heading, HTML comments, blanks, the
    ``Context:`` line) pass through unchanged. Order is preserved.
    """
    out: list[str] = []
    changes: list[tuple[str, str, str]] = []
    for line in section_lines:
        m = CHUNK_LINE_RE.match(line)
        if not m:
            out.append(line)
            continue
        chunk_id = m.group("id")
        current = m.group("state")
        new_state = "x" if chunk_id in shipped_chunks else " "
        if current.lower() != new_state:
            changes.append((chunk_id, current, new_state))
        out.append(f"{m.group('prefix')}[{new_state}]{m.group('rest')}")
    return out, changes


def build_status_view(
    change_log_content: str, build_plan_content: str
) -> tuple[str | None, list[tuple[str, str, str]]]:
    """Produce updated build-plan content with regenerated Status section.

    Returns ``(new_content, changes)``. ``new_content`` is ``None`` when no
    checkbox flips were needed (idempotent no-op). ``changes`` is empty in
    that case.
    """
    entries = parse_change_log(change_log_content)
    active_scope = _detect_active_scope(build_plan_content, change_log_content)
    shipped = collect_shipped_chunks(entries, scope=active_scope)
    start, end, section = extract_status_section(build_plan_content)
    if start < 0:
        return None, []
    new_section, changes = regenerate_status_section(section, shipped)
    if not changes:
        return None, []
    lines = build_plan_content.splitlines()
    new_lines = lines[:start] + new_section + lines[end:]
    trailing = "\n" if build_plan_content.endswith("\n") else ""
    return "\n".join(new_lines) + trailing, changes


def build_scope_to_plan_map(artifacts_dir: Path) -> dict[str, Path]:
    """Map each frontmatter ``scope:`` to its build-plan FILE under artifacts/.

    Scans ``artifacts_dir/*.md`` and records ``{scope_value: path}`` for every
    file whose YAML frontmatter declares a non-empty ``scope:`` (parsed by
    :func:`_parse_build_plan_frontmatter_scope`). This is the scope→FILE
    resolver that lets ``regen-views`` regenerate every release-pending plan in
    one pass instead of via the single ``active_build_plan`` pointer (REL-4T8N).

    On a duplicate scope across two files, the first by sorted filename wins
    (deterministic; a duplicate scope is malformed — surfaced separately by
    :func:`diagnose_scope_plan_coverage`). Returns ``{}`` when the directory is
    absent or holds no scope-tagged plans. Read-only.
    """
    result: dict[str, Path] = {}
    if not artifacts_dir.is_dir():
        return result
    for path in sorted(artifacts_dir.glob("*.md")):
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        _present, scope = _parse_build_plan_frontmatter_scope(content)
        if scope and scope not in result:
            result[scope] = path
    return result


def collect_release_pending_scopes(entries: list[ChangeLogEntry]) -> list[str]:
    """Distinct ``scope=`` values from shipped/merged entries, newest-first.

    Enumerates every scope that has at least one change-log entry whose
    ``status`` is in :data:`VALID_STATUS_VALUES` (``shipped`` or ``merged``), in
    change-log order (newest-first by file position), de-duplicated. ``merged``
    is the release-pending intermediate; ``shipped`` is the just-released (or
    historical) state. Both are included so ``regen-views`` flips the right
    plans regardless of which value the release operator used (the v2.0.5
    release, for instance, tagged its four scopes ``status=shipped`` directly).
    """
    seen: set[str] = set()
    ordered: list[str] = []
    for entry in entries:
        if entry.tags.get("status") not in VALID_STATUS_VALUES:
            continue
        scope = entry.tags.get("scope")
        if isinstance(scope, str) and scope and scope not in seen:
            seen.add(scope)
            ordered.append(scope)
    return ordered


def diagnose_scope_plan_coverage(
    change_log_content: str, artifacts_dir: Path
) -> list[str]:
    """Warn about release-pending scopes with no plan file + duplicate scopes.

    Pure diagnostic (mirrors :func:`validate_status_values`): the caller
    (``cmd_regen_views``) prints the returned strings on stderr. Two cases:

    * An unreleased scope with NO matching build-plan file — its ``## Status``
      cannot be regenerated, a real release-process error. "Unreleased" covers
      both ``status=merged`` (release-pending) and **statusless tagged**
      entries (the merge-flow stamp was missed — REL-9F2T audit finding: a
      statusless entry with a bad ``scope=`` was undetected until release).
      A ``status=shipped`` scope with no file is deliberately NOT flagged:
      its plan is a retired historical artifact or predates the ``scope:``
      frontmatter convention, so the absence is expected, not an error.
    * Two ``artifacts/*.md`` files declaring the same ``scope:`` — ambiguous; the
      map keeps the first by sorted filename.

    Returns ``[]`` when coverage is clean.
    """
    warnings: list[str] = []
    if artifacts_dir.is_dir():
        first_seen: dict[str, str] = {}
        for path in sorted(artifacts_dir.glob("*.md")):
            try:
                content = path.read_text(encoding="utf-8")
            except OSError:
                continue
            _present, scope = _parse_build_plan_frontmatter_scope(content)
            if not scope:
                continue
            if scope in first_seen:
                warnings.append(
                    f"duplicate scope={scope!r}: {path.name} also declares it "
                    f"(keeping {first_seen[scope]}); one plan is malformed."
                )
            else:
                first_seen[scope] = path.name

    plan_map = build_scope_to_plan_map(artifacts_dir)
    seen: set[str] = set()
    for entry in parse_change_log(change_log_content):
        status = entry.tags.get("status")
        if status == "merged":
            label = "release-pending (status=merged)"
        elif status is None and entry.tag_line_count > 0:
            # A statusless TAGGED entry is unreleased work whose merge-flow
            # status=merged stamp was missed — same release-integrity stakes,
            # previously invisible to this diagnostic (REL-9F2T).
            label = "unreleased (statusless — merge stamp missed?)"
        else:
            # shipped (retired plan is expected), typos (typo-guard owns
            # those), and untagged historical entries.
            continue
        scope = entry.tags.get("scope")
        if not (isinstance(scope, str) and scope) or scope in seen:
            continue
        seen.add(scope)
        if scope not in plan_map:
            warnings.append(
                f"change-log scope={scope!r} is {label} "
                f"but has no matching build-plan file in artifacts/ — its "
                f"## Status cannot be regenerated."
            )
    return warnings


YAML_TOP_LEVEL_KEY_RE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_]*):\s*")


def extract_yaml_top_level_block(
    content: str, key: str
) -> tuple[int, int, list[str]]:
    """Find a column-0 YAML key and its body block.

    Returns ``(start_idx, end_idx_exclusive, block_lines)``. The block starts at
    the ``key:`` line and continues across all subsequent indented or blank
    lines, ending at the first column-0 non-blank line (next key or comment
    header). Trailing blank lines are excluded so they belong to the next
    block's leading whitespace. Returns ``(-1, -1, [])`` if the key is absent.
    """
    lines = content.splitlines()
    start = -1
    key_re = re.compile(rf"^{re.escape(key)}:\s*")
    for i, line in enumerate(lines):
        if key_re.match(line):
            start = i
            break
    if start < 0:
        return (-1, -1, [])
    end = len(lines)
    for j in range(start + 1, len(lines)):
        line = lines[j]
        if not line.strip():
            continue
        if line[:1] in (" ", "\t"):
            continue
        end = j
        break
    # Drop trailing blank lines so they stay with the following block.
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    return (start, end, lines[start:end])


def _collect_scope_rollups(
    entries: list[ChangeLogEntry],
) -> dict[str, dict[str, list[str]]]:
    """Aggregate shipped entries by ``scope`` tag.

    Returns ``{scope_id: {"chunks": [...], "releases": [...]}}`` with chunks
    sorted, releases sorted, scope IDs sorted alphabetically. Only entries with
    ``status=shipped`` AND a non-empty ``scope=`` tag contribute.
    """
    raw: dict[str, dict[str, set[str]]] = {}
    for entry in entries:
        if entry.tags.get("status") != "shipped":
            continue
        scope = entry.tags.get("scope")
        if not isinstance(scope, str) or not scope:
            continue
        rec = raw.setdefault(scope, {"chunks": set(), "releases": set()})
        chunks = entry.tags.get("chunks")
        if isinstance(chunks, list):
            # Drop any chunk ID outside the safe charset so a malformed ID
            # (quote / brace / colon) cannot corrupt the scope_rollups YAML.
            rec["chunks"].update(
                c
                for c in chunks
                if isinstance(c, str) and CHUNK_ID_SAFE_RE.match(c)
            )
        release = entry.tags.get("release")
        if isinstance(release, str) and release:
            rec["releases"].add(release)
    return {
        scope: {
            "chunks": sorted(raw[scope]["chunks"]),
            "releases": sorted(raw[scope]["releases"]),
        }
        for scope in sorted(raw)
    }


def _format_scope_rollups_block(scopes: dict[str, dict[str, list[str]]]) -> str:
    """Format the ``scope_rollups:`` YAML block from the aggregated dict.

    Chunk IDs are quoted to preserve leading zeros (unquoted ``00`` is the
    integer 0 in YAML's octal/leading-zero handling).
    """
    if not scopes:
        return "scope_rollups: {}"
    lines = ["scope_rollups:"]
    for scope_id in scopes:
        rec = scopes[scope_id]
        lines.append(f"  {scope_id}:")
        chunks_yaml = ", ".join(f'"{c}"' for c in rec["chunks"])
        lines.append(f"    chunks: [{chunks_yaml}]")
        releases_yaml = ", ".join(f'"{r}"' for r in rec["releases"])
        lines.append(f"    releases: [{releases_yaml}]")
    return "\n".join(lines)


SCOPE_ROLLUPS_HEADER = (
    "# =============================================================================\n"
    "# SCOPE ROLLUPS (derived view, v1.4+)\n"
    "# =============================================================================\n"
    "# Auto-generated by `prawduct-hook regen-views` from\n"
    "# .prawduct/change-log.md `scope=` tags. Do not hand-edit — edits will be\n"
    "# overwritten on next regen.\n"
)


def build_scope_view(
    change_log_content: str, project_state_content: str
) -> tuple[str | None, dict[str, dict[str, list[str]]]]:
    """Regenerate the ``scope_rollups:`` block in project-state.yaml.

    Returns ``(new_content, scopes)``. ``new_content`` is ``None`` when the
    existing block already matches (idempotent no-op). ``scopes`` is the
    computed mapping so callers can render human-readable diffs.

    If no ``scope_rollups:`` block exists, one is appended at end-of-file with
    a comment header. If the block exists, only the key + body is replaced;
    surrounding comments and other keys are preserved verbatim.
    """
    entries = parse_change_log(change_log_content)
    scopes = _collect_scope_rollups(entries)
    new_block = _format_scope_rollups_block(scopes)
    new_block_lines = new_block.splitlines()

    start, end, existing_block = extract_yaml_top_level_block(
        project_state_content, "scope_rollups"
    )

    if start < 0:
        # No existing block — append at end of file with header comment.
        sep = "" if project_state_content.endswith("\n") else "\n"
        appended = (
            project_state_content
            + sep
            + "\n"
            + SCOPE_ROLLUPS_HEADER
            + "\n"
            + new_block
            + "\n"
        )
        return appended, scopes

    if existing_block == new_block_lines:
        return None, scopes

    lines = project_state_content.splitlines()
    new_lines = lines[:start] + new_block_lines + lines[end:]
    trailing = "\n" if project_state_content.endswith("\n") else ""
    return "\n".join(new_lines) + trailing, scopes


def _collect_releases(
    entries: list[ChangeLogEntry],
) -> list[dict[str, object]]:
    """Group shipped entries by ``release`` tag, preserving change-log order.

    Returns a list of ``{release, entries}`` dicts in the order releases first
    appear in the change-log (newest-first by convention). Each release keeps a
    LIST of its contributing entries — ``{title, chunks (sorted, de-duped),
    scope}`` in change-log order — WITHOUT collapsing them. A batched release
    (one version, several scopes) thus preserves every scope's own title and own
    chunk set, instead of overwriting title/scope from the first entry seen and
    unioning all chunks under it (the REL-4T8N mis-aggregation bug).
    """
    seen: dict[str, dict[str, object]] = {}
    order: list[str] = []
    for entry in entries:
        if entry.tags.get("status") != "shipped":
            continue
        release = entry.tags.get("release")
        if not isinstance(release, str) or not release:
            continue
        if release not in seen:
            seen[release] = {"release": release, "entries": []}
            order.append(release)
        chunks = entry.tags.get("chunks")
        chunk_list = (
            sorted({c for c in chunks if isinstance(c, str)})
            if isinstance(chunks, list)
            else []
        )
        scope = entry.tags.get("scope")
        seen[release]["entries"].append(
            {
                "title": entry.title,
                "chunks": chunk_list,
                "scope": scope if isinstance(scope, str) and scope else None,
            }
        )
    return [seen[release] for release in order]


RELEASE_NOTES_HEADER = (
    "# Release Notes\n"
    "\n"
    "<!-- Auto-generated by `prawduct-hook regen-views` from\n"
    "     .prawduct/change-log.md `release=` tags. Do not hand-edit — edits will\n"
    "     be overwritten on next regen. See change-log.md for full per-release\n"
    "     bodies; this file is a digest. -->\n"
)


def _group_release_entries_by_scope(
    entries: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Collapse a release's contributing entries into sub-release groups.

    A "sub-release" is a distinct ``scope`` within the release: entries sharing a
    scope MERGE (chunks union'd + sorted, first entry's title kept), so the same
    scope never renders as two sub-sections. Scope-less entries (``scope=None``)
    never merge — each stays its own group, keyed by title — since there is no
    scope to disambiguate them. Groups appear in first-seen (change-log) order.

    This makes the multi-scope render a function of distinct SCOPES, not raw
    entry count, so a single scope split across two change-log entries (e.g.
    v1.4.0's two ``scope=v1.4`` entries) collapses to one block rather than two
    identical ``### v1.4`` headings.
    """
    groups: list[dict[str, object]] = []
    by_scope: dict[str, int] = {}
    for entry in entries:
        scope = entry["scope"]
        if scope is not None and scope in by_scope:
            group = groups[by_scope[scope]]
            group["chunks"] = sorted(set(group["chunks"]) | set(entry["chunks"]))
            continue
        if scope is not None:
            by_scope[scope] = len(groups)
        groups.append(
            {"title": entry["title"], "chunks": list(entry["chunks"]), "scope": scope}
        )
    return groups


def build_release_notes_view(change_log_content: str) -> str | None:
    """Generate release-notes.md content from release-tagged shipped entries.

    Returns the full desired file content, or ``None`` if no shipped+released
    entries exist (caller decides whether to create an empty placeholder or
    leave any existing file alone).

    A release with a SINGLE sub-release (one scope, or one scope-less entry)
    renders flat (``**Entry:**`` / ``**Chunks shipped:**`` / ``**Scope:**`` under
    the ``## <release>`` heading) — byte-compatible with the historical 1:1
    layout, including a single scope split across multiple change-log entries
    (their chunks union under one block). A release with MULTIPLE sub-releases (a
    batched release: one version, several distinct scopes) renders one
    ``### <scope|title>`` sub-section per sub-release, each with its OWN chunk
    list (NOT the union across scopes), followed by a single shared
    ``See change-log`` trailer for the whole release (REL-4T8N).
    """
    entries = parse_change_log(change_log_content)
    releases = _collect_releases(entries)
    if not releases:
        return None
    out: list[str] = [RELEASE_NOTES_HEADER]
    for rec in releases:
        contributing = _group_release_entries_by_scope(rec["entries"])  # type: ignore[arg-type]
        out.append(f"## {rec['release']}\n")
        if len(contributing) == 1:
            entry = contributing[0]
            out.append(f"**Entry:** {entry['title']}\n")
            if entry["chunks"]:
                out.append(f"**Chunks shipped:** {', '.join(entry['chunks'])}\n")
            if entry["scope"]:
                out.append(f"**Scope:** {entry['scope']}\n")
        else:
            # Batched release: one sub-section per scope, each with its own
            # chunks. The ### heading carries the scope, so **Scope:** is omitted
            # as redundant; the title fills in when an entry has no scope= tag.
            for entry in contributing:
                out.append(f"### {entry['scope'] or entry['title']}\n")
                out.append(f"**Entry:** {entry['title']}\n")
                if entry["chunks"]:
                    out.append(f"**Chunks shipped:** {', '.join(entry['chunks'])}\n")
        out.append("See `.prawduct/change-log.md` for full details.\n")
    return "\n".join(out).rstrip() + "\n"


@dataclass
class ViewRegenResult:
    """Outcome of one view's regen pass."""

    name: str  # "status" | "release-notes" | "scope-rollups"
    action: str  # "noop" | "write" | "create"
    summary: str  # human-readable detail
    new_content: str | None = None  # new file content (None for noop)
    path_relative: str = ""  # path relative to prawduct_dir, for caller to write


def _plan_status_results(
    prawduct_dir: Path, change_log_content: str
) -> list[ViewRegenResult]:
    """One status :class:`ViewRegenResult` per release-pending build plan (REL-4T8N).

    Multi-scope model: enumerate every scope-tagged plan FILE whose scope appears
    in the change-log as shipped/merged, regenerate each plan's ``## Status``
    (each plan re-detects its OWN scope via :func:`build_status_view`, so chunk
    flips never leak across scopes), and ALWAYS include the ``active_build_plan``
    pointer's plan so an in-progress pinned plan is regenerated mid-batch. Plans
    are de-duped by resolved path (two scopes → one file, or the pointer
    coinciding with a scope mapping).

    Backward-compat: when no scope-tagged plan and no existing pointer/default
    plan resolve, fall back to the historical single-plan contract — resolve via
    :func:`resolve_build_plan_path` and raise ``FileNotFoundError`` if it is
    missing, exactly as the pre-REL-4T8N single-plan path did.
    """
    entries = parse_change_log(change_log_content)
    relevant_scopes = set(collect_release_pending_scopes(entries))
    plan_map = build_scope_to_plan_map(prawduct_dir / "artifacts")

    plan_paths: list[Path] = []
    seen: set[Path] = set()

    def _add(path: Path) -> None:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            plan_paths.append(path)

    # Plans whose scope is present (shipped/merged) in the change-log.
    for scope, path in plan_map.items():
        if scope in relevant_scopes and path.exists():
            _add(path)

    # Always include the explicitly-pinned active plan, even when its scope is
    # not (yet) release-pending — the in-progress plan mid-batch.
    pointer_plan = resolve_build_plan_path(prawduct_dir)
    if pointer_plan.exists():
        _add(pointer_plan)

    if not plan_paths:
        # Back-compat: no scope-tagged plan resolved AND no pointer/default plan
        # exists. Preserve today's contract — require the resolved plan.
        fallback = resolve_build_plan_path(prawduct_dir)
        if not fallback.exists():
            raise FileNotFoundError(f"build-plan not found at {fallback}")
        plan_paths.append(fallback)

    results: list[ViewRegenResult] = []
    for plan_path in plan_paths:
        plan_rel = plan_path.relative_to(prawduct_dir).as_posix()
        plan_content = plan_path.read_text(encoding="utf-8")
        status_new, status_changes = build_status_view(change_log_content, plan_content)
        if status_new is None:
            results.append(
                ViewRegenResult(
                    name="status",
                    action="noop",
                    summary=f"Status ({plan_rel}): up to date",
                    path_relative=plan_rel,
                )
            )
            continue
        shipped = sorted(cid for cid, _, new in status_changes if new == "x")
        unshipped = sorted(cid for cid, _, new in status_changes if new == " ")
        parts: list[str] = []
        if shipped:
            parts.append(f"shipped [{', '.join(shipped)}]")
        if unshipped:
            parts.append(f"unshipped [{', '.join(unshipped)}]")
        results.append(
            ViewRegenResult(
                name="status",
                action="write",
                summary=(
                    f"Status ({plan_rel}): {len(status_changes)} chunk(s) flipped — "
                    + "; ".join(parts)
                ),
                new_content=status_new,
                path_relative=plan_rel,
            )
        )
    return results


def plan_regen(prawduct_dir: Path) -> tuple[bool, list[ViewRegenResult]]:
    """Compute what regen-views would do; do NOT write.

    Returns ``(enabled, results)``. ``enabled`` is False when views_enabled is
    not set — in that case results is empty. Otherwise results contains a
    ``status`` entry PER release-pending build plan (the multi-scope model, see
    :func:`_plan_status_results`), followed by a single ``release-notes`` and a
    single ``scope-rollups`` entry, each describing the intended action and the
    new content to write.

    Callers (prawduct-hook regen-views) decide whether to apply the changes, and
    may call :func:`diagnose_scope_plan_coverage` to surface release-pending
    scopes that have no resolvable plan file.
    """
    state_path = prawduct_dir / "project-state.yaml"
    if not is_views_enabled(state_path):
        return False, []

    change_log_path = prawduct_dir / "change-log.md"
    release_notes_path = prawduct_dir / "release-notes.md"
    if not change_log_path.exists():
        raise FileNotFoundError(f"change-log not found at {change_log_path}")

    change_log = change_log_path.read_text(encoding="utf-8")
    project_state = state_path.read_text(encoding="utf-8")

    results: list[ViewRegenResult] = []

    # --- Status view (one result per release-pending plan; REL-4T8N) ---
    # The build plan is no longer resolved here. _plan_status_results enumerates
    # every scope-tagged plan (driven by the change-log) plus the pinned active
    # plan, and falls back to the single-plan resolve_build_plan_path contract
    # (including its FileNotFoundError) when no scope-tagged plan resolves.
    results.extend(_plan_status_results(prawduct_dir, change_log))

    # --- Release-notes view ---
    rn_new = build_release_notes_view(change_log)
    if rn_new is None:
        results.append(
            ViewRegenResult(
                name="release-notes",
                action="noop",
                summary="Release notes: no release-tagged shipped entries",
                path_relative="release-notes.md",
            )
        )
    else:
        existing_rn = (
            release_notes_path.read_text(encoding="utf-8")
            if release_notes_path.exists()
            else None
        )
        if existing_rn == rn_new:
            results.append(
                ViewRegenResult(
                    name="release-notes",
                    action="noop",
                    summary="Release notes: up to date",
                    path_relative="release-notes.md",
                )
            )
        else:
            action = "write" if existing_rn is not None else "create"
            results.append(
                ViewRegenResult(
                    name="release-notes",
                    action=action,
                    summary=f"Release notes: {action} release-notes.md",
                    new_content=rn_new,
                    path_relative="release-notes.md",
                )
            )

    # --- Scope-rollups view ---
    scope_new, scopes = build_scope_view(change_log, project_state)
    if scope_new is None:
        results.append(
            ViewRegenResult(
                name="scope-rollups",
                action="noop",
                summary="Scope rollups: up to date",
                path_relative="project-state.yaml",
            )
        )
    else:
        if scopes:
            scope_summary = ", ".join(
                f"{s}={len(scopes[s]['chunks'])} chunk(s)" for s in scopes
            )
            summary = f"Scope rollups: {scope_summary}"
        else:
            summary = "Scope rollups: empty (no scope tags)"
        results.append(
            ViewRegenResult(
                name="scope-rollups",
                action="write",
                summary=summary,
                new_content=scope_new,
                path_relative="project-state.yaml",
            )
        )

    return True, results


def apply_regen(prawduct_dir: Path, results: list[ViewRegenResult]) -> None:
    """Write the new content for each result whose action is not 'noop'."""
    for r in results:
        if r.action == "noop" or r.new_content is None:
            continue
        target = prawduct_dir / r.path_relative
        target.write_text(r.new_content, encoding="utf-8")


def is_views_enabled(project_state_path: Path) -> bool:
    """True if project-state.yaml has top-level ``views_enabled: true``.

    Scans for a column-0 ``views_enabled:`` key, ignoring comments. Returns
    False on any error or missing key — opt-in by design. Delegates to the
    shared ``core.read_bool_yaml_key`` scan.
    """
    return read_bool_yaml_key(project_state_path, "views_enabled")
