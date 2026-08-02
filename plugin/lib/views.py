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
  ``shipped`` flips a checkbox to ``[x]``. A tagged entry with NO ``status=``
  is the normal release-pending state: the entry rides in the feature PR, so
  its presence on the integration branch means the work is merged — no stamp
  required (single-pr-bookkeeping). ``merged`` is an accepted legacy synonym
  of that state (older logs carry it from the retired ``stamp-merged`` flow
  step); neither flips a checkbox.
* ``scope``   rollup identifier, e.g., ``v1.4``

Entries without a tag line are ignored — untagged historical entries coexist
with tagged ones. Only chunks with a ``status=shipped`` tag flip to ``[x]``;
all other Chunk lines flip to ``[ ]`` so the view is fully derived.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from .core import (
    BUILD_PLAN_POINTER_KEY,
    read_bool_yaml_key,
    read_str_yaml_key,
    resolve_build_plan_path,
)


TAG_LINE_RE = re.compile(r"<!--\s*prawduct:\s*(.+?)\s*-->")
H2_RE = re.compile(r"^##\s+(.+?)\s*$")
# The Status-line twin of `buildplan_refs._CHUNK_ID_SEP`, kept character-for-
# character identical with it — `**` included. A plan author who writes
# `## Chunk A — Name` as a body heading writes `- [ ] **Chunk A** — Name` in
# Status, and before VWS-2F9K/#201-leg-3 only the colon form matched here, so
# those checkboxes could never flip and nothing said why.
#
# The two regexes are NOT shared code: this one also captures
# `prefix`/`state`/`rest` for rewriting, while the heading/item matchers only
# read. The SEPARATOR SET is the shared contract, and widening one side alone is
# a new defect rather than a partial fix — a bold Status line whose box flips
# here but whose id `buildplan_refs` cannot parse makes the plan read as having
# no current chunk, so `verify-chunk-refs` exits 0 having verified nothing.
# If you change this set, change `buildplan_refs._CHUNK_ID_SEP` in the same edit;
# `tests/test_build_plan_resolution.py` pins that they agree.
_CHUNK_LINE_SEP = r"\s*(?:[:—–(-]|\*\*|$)"
CHUNK_LINE_RE = re.compile(
    r"^(?P<prefix>\s*-\s+)\[(?P<state>[ xX])\]"
    r"(?P<rest>\s+(?:\*\*\s*)?Chunk\s+(?P<id>[A-Za-z0-9_-]+)" + _CHUNK_LINE_SEP + r".*)$"
)
# Safe charset for a chunk ID, mirroring CHUNK_LINE_RE's `id` group. A chunk ID
# is only ever a build-plan header token, so anything outside this set (a quote,
# `}`, `:`, whitespace) is malformed and — left unquoted/quoted naively — would
# corrupt the generated scope_rollups YAML (e.g. `chunks: ["0"a]`). Such IDs are
# dropped before they reach a derived view.
CHUNK_ID_SAFE_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class ScopedError(str):
    """A validation error that knows which scope's view it suppresses.

    Under the regen-views-is-advice ruling (2026-08-01) the unit of atomicity is
    the **view**, not the run: an error that can only make one scope's
    ``## Status`` view wrong must not stop release-notes and scope-rollups from
    being written. To partition, the caller needs each error to say what it
    affects — ``scope=None`` means "no single view owns this, treat it as
    global."

    It subclasses ``str`` rather than wrapping one so that every existing
    consumer and assertion — ``== []``, ``in errors[0]``, printing — keeps
    working on the message unchanged, and only the code that needs the
    attribution reaches for ``.scope``. The alternative (a dataclass with a
    ``.message``) would have meant rewriting assertions that currently pin real
    behaviour, to buy nothing the caller can use.
    """

    # A real class attribute, not just an annotation, so `.scope` is always
    # readable. A `str` subclass loses its instance dict through any operation
    # that returns a NEW str (slicing, concatenation, `.strip()`), and those
    # return plain `str` — but a caller holding one of these and reading
    # `.scope` should get a safe answer rather than `AttributeError`, and
    # `None` (= "no single view owns this") is the fail-closed answer.
    scope: str | None = None

    def __new__(cls, message: str, scope: str | None = None) -> "ScopedError":
        obj = super().__new__(cls, message)
        obj.scope = scope
        return obj


def _display_path(path: Path, artifacts_dir: Path) -> str:
    """A plan path as written for a human, relative to ``artifacts/`` when possible.

    Bare ``path.name`` was adequate while discovery was flat. Recursive
    discovery makes ``build-plan.md`` a near-certain collision across
    ``plans/<id>/`` directories, so a duplicate-scope message naming two files
    called ``build-plan.md`` tells the operator nothing about which two.
    """
    try:
        return str(path.relative_to(artifacts_dir))
    except ValueError:
        return path.name


def normalize_chunk_id(chunk_id: str) -> str:
    """Canonical form of a chunk ID for matching (VWS-6R4T).

    Matching between a change-log ``chunks=`` tag and a build-plan
    ``Chunk <id>:`` line was historically literal string equality, so
    ``chunks=1`` silently failed to flip ``Chunk 01`` — a partial, invisible
    failure. Tolerance rules, applied to BOTH sides of every comparison:

    * case-insensitive (``A`` ≡ ``a``)
    * ``_`` and ``-`` unify (``foo_bar`` ≡ ``foo-bar``)
    * purely-numeric IDs compare by integer value (``1`` ≡ ``01``)

    The zero-strip applies only when the WHOLE ID is digits, so a mixed ID
    like ``01a`` keeps its digits verbatim and cannot collide with ``1a``.
    """
    norm = chunk_id.strip().casefold().replace("_", "-")
    if norm.isdigit():
        norm = str(int(norm))
    return norm


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
    pure helper flags every entry whose ``status=`` tag is PRESENT but not in
    ``{shipped, merged}``. Entries with no ``status=`` tag (untagged historical
    entries) are not flagged. The regen-views caller treats these as fatal
    (fail closed, nothing written — VWS-6R4T); the function itself stays pure.

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
    surfaces each multi-tag entry so the author merges the lines. The caller
    treats these as WARNINGS — the union produces correct output. Conflicting
    scalar values across the lines do NOT (first-wins may pick the wrong one);
    those are surfaced separately by :func:`validate_tag_conflicts` and treated
    as errors (VWS-6R4T).

    Returns ``[]`` when every entry has at most one tag line.
    """
    warnings: list[str] = []
    for entry in entries:
        if entry.tag_line_count <= 1:
            continue
        warnings.append(
            f"change-log entry {entry.title!r} (line {entry.line_number}) has "
            f"{entry.tag_line_count} prawduct tag lines — the canonical format "
            f"is one per entry; chunks= lists were unioned across them. Merge "
            f"them into a single tag line."
        )
    return warnings


def validate_tag_conflicts(entries: list[ChangeLogEntry]) -> list[str]:
    """Return an error string per entry whose tag lines CONFLICT (VWS-6R4T).

    When multiple tag lines set the same scalar key to different values,
    :func:`_merge_tag_line` keeps the first and records the loser in
    ``tag_conflicts`` — a repair that may have picked the wrong value (e.g.
    two ``status=`` lines disagreeing about whether work shipped). Unlike mere
    multiplicity (a style problem the union fixes), a conflict means the
    derived views may be built from the wrong tag, so the caller treats these
    as fatal: fix the entry, don't guess.

    Returns ``[]`` when no entry has conflicting tag lines.
    """
    errors: list[str] = []
    for entry in entries:
        if not entry.tag_conflicts:
            continue
        errors.append(
            f"change-log entry {entry.title!r} (line {entry.line_number}) has "
            f"conflicting values across its {entry.tag_line_count} tag lines "
            f"(kept first-wins: " + "; ".join(entry.tag_conflicts) + ") — the "
            f"derived views may be built from the wrong value. Merge the tag "
            f"lines and resolve the conflict."
        )
    return errors


def stamp_merged(content: str) -> tuple[str, list[str]]:
    """Stamp ``status=merged`` onto every statusless *tagged* entry.

    DEPRECATED — no flow applies this stamp anymore. A statusless tagged
    entry is now first-class release-pending state: the entry rides in the
    feature PR, so its presence on the integration branch already proves the
    work is merged, and requiring a post-merge stamp commit forced consumers
    with protected integration branches into a second, bookkeeping-only PR
    (single-pr-bookkeeping). The function is kept because stamping remains
    harmless and idempotent, existing logs carry ``merged`` entries, and the
    ``stamp-merged`` hook command stays callable (with a deprecation notice)
    so consumer muscle-memory doesn't hit an unknown-command error.

    Historical context: the stamp was added for REL-2N8K (v2.0.14 shipped 8
    of 10 entries unflipped because a literal reading of the release
    checklist skipped statusless entries). The durable fixes for that
    incident are the ones still active — the ``check-change-log-entry`` PR
    probe, the "flip every unreleased entry, statusless OR merged" release
    rule, and fail-closed regen validation.

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
    ``---`` are tolerated — a third of this repo's build plans (16 of 48 as of
    2026-07-27) open with a comment header before the frontmatter, so requiring
    ``---`` on line 1 would make the field inert for all of them. (This sentence
    previously read "every real build-plan", which was never true and was
    copied into three other places before anyone checked it: ``for f in
    .prawduct/artifacts/build-plan*.md; do head -1 "$f"; done``.)

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
    fm = _frontmatter_lines(content)
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
        # suppress change-log inference.
        if not value or value.lower() in ("null", "~"):
            return (True, None)
        return (True, value)
    return (False, None)


def _frontmatter_lines(content: str) -> list[str] | None:
    """The frontmatter block's body lines, or ``None`` when there is no block.

    Extracted so ``scope:`` and ``artifact:`` are read by ONE walker. Two
    independent walkers over the same block is the shape that lets a file be a
    build plan to one reader and not to another, which is exactly the class of
    disagreement the scope collectors were already exhibiting.

    Tolerances (unchanged, and load-bearing — a third of this repo's build
    plans open with a comment header): leading blank lines and one leading HTML
    comment block are skipped before the opening ``---``. An UNCLOSED comment
    header or an unterminated frontmatter both read as *absent* rather than
    raising — a deliberately lenient reading of a malformed header.
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

    Membership is tested after :func:`normalize_chunk_id` on BOTH sides, so
    zero-padding / case / separator variants flip correctly (VWS-6R4T) —
    ``changes`` still reports the plan's verbatim chunk IDs.
    """
    out: list[str] = []
    changes: list[tuple[str, str, str]] = []
    shipped_norm = {normalize_chunk_id(c) for c in shipped_chunks}
    for line in section_lines:
        m = CHUNK_LINE_RE.match(line)
        if not m:
            out.append(line)
            continue
        chunk_id = m.group("id")
        current = m.group("state")
        new_state = "x" if normalize_chunk_id(chunk_id) in shipped_norm else " "
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


def _declares_non_build_plan_artifact(content: str) -> bool:
    """True when frontmatter declares an ``artifact:`` type that is NOT a build
    plan — i.e. this file is scope-tagged but is not a plan to regenerate.

    Both scope collectors below glob ``artifacts/*.md`` and treated ANY file
    with a frontmatter ``scope:`` as a build plan. That is detection by surface
    marker rather than by declared type, and several files in this repo already
    carry a scope while being a design note, a discovery, a reference, a
    release plan or a collapse map. Enumerate rather than trust a digit::

        grep -l '^scope:' .prawduct/artifacts/*.md \
          | xargs grep -l '^artifact:' \
          | xargs grep -L '^artifact: build-plan'

    The middle stage is load-bearing, and omitting it was this docstring's own
    first mistake: ``grep -L`` alone cannot distinguish "declares another type"
    from "declares NO type" — precisely the distinction this predicate draws —
    so it wrongly returns ``build-plan-release-readiness.md`` (a real plan, the
    counter-example named below) and a file whose ``scope:`` sits inside an
    HTML comment and never parses. They were invisible only because none
    happened to share a scope VALUE with a real plan; the first one that did
    (`collapse-map-learnings-firing.md`, 2026-08-01) made
    ``diagnose_scope_plan_coverage`` fatal and stopped ``regen-views`` writing
    views for EVERY scope — the mechanism release time depends on.

    Absence is treated as a build plan, not excluded: `build-plan-release-
    readiness.md` declares no ``artifact:`` key at all, so requiring
    ``artifact: build-plan`` would silently drop a real plan. Excluding only an
    explicit *other* type fails safe in the direction that keeps plans.
    """
    fm = _frontmatter_lines(content)
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


def build_scope_to_plan_map(artifacts_dir: Path) -> dict[str, Path]:
    """Map each frontmatter ``scope:`` to its build-plan FILE under artifacts/.

    Scans ``artifacts_dir`` **recursively** (see
    :func:`iter_scoped_plan_candidates`, which owns the scan) and records
    ``{scope_value: path}`` for every
    file whose YAML frontmatter declares a non-empty ``scope:`` (parsed by
    :func:`_parse_build_plan_frontmatter_scope`) **and does not declare an
    ``artifact:`` type other than ``build-plan``** (see
    :func:`_declares_non_build_plan_artifact` — a design note, discovery,
    reference, release plan or collapse map may legitimately carry a scope and
    is not a plan to regenerate). Both keys are stated here, not only in the
    private helper, because the question a reader arrives with is "why won't my
    scope regenerate?" and the answer is now two keys rather than one. This is
    the scope→FILE resolver that lets ``regen-views`` regenerate every
    release-pending plan in one pass instead of via the single
    ``active_build_plan`` pointer (REL-4T8N).

    On a duplicate scope across two files, the first by sorted filename wins
    (deterministic; a duplicate scope is malformed — surfaced separately by
    :func:`diagnose_scope_plan_coverage`). Returns ``{}`` when the directory is
    absent or holds no scope-tagged plans. Read-only.
    """
    result: dict[str, Path] = {}
    for plan_path, scope in iter_scoped_plan_candidates(artifacts_dir):
        if scope not in result:
            result[scope] = plan_path
    return result


def iter_scoped_plan_candidates(artifacts_dir: Path) -> Iterator[tuple[Path, str]]:
    """Yield ``(path, scope)`` for every scope-declaring build plan under ``artifacts_dir``.

    The ONE home for "which files are build plans, and what scope does each
    declare." :func:`build_scope_to_plan_map` and
    :func:`diagnose_scope_plan_coverage` were line-for-line twins of this loop,
    and both carried a docstring warning that letting them diverge would make
    the diagnostic condemn a file the map never considered — which is exactly
    what happened on 2026-08-01. A warning that a duplicate must be kept in sync
    is worth less than not having the duplicate.

    **Discovery is recursive** (VWS-4T9P / #201 leg 1). The previous
    ``glob("*.md")`` saw only the top level, so a repo organizing plans as
    ``artifacts/plans/<id>/build-plan.md`` had every one of them invisible: their
    scopes resolved to nothing, the coverage diagnostic errored, and — because
    the caller then failed closed for the whole run — release-notes and
    scope-rollups died with them. Four surveyed repos carry 16 nested plans each
    (2026-07-21 fleet survey on the item).

    Ordering is by sorted path so the first-wins tie-break in both consumers
    stays deterministic, which now makes *directory depth* part of that
    tie-break. Consumers report paths via :func:`_display_path` rather than
    ``Path.name`` — see its docstring for why nesting makes that necessary.
    """
    if not artifacts_dir.is_dir():
        return
    # Named `plan_path` because these ARE build-plan candidates — consistency
    # with every other reader, and NOT load-bearing. The decoding rule reaches
    # this module file-scoped (`tests/preferences/test_build_plan_decoding.py`),
    # so it no longer depends on a local's name.
    for plan_path in sorted(artifacts_dir.rglob("*.md")):
        # Archived plans are history, not live assertion — the same rule every
        # record check applies (`record_lint._ARCHIVE_MARKERS`). Load-bearing
        # once discovery went recursive: the scan is `sorted()` and first-wins,
        # and `artifacts/archive/build-plan-foo.md` sorts BEFORE
        # `artifacts/build-plan-foo.md`, so an archived copy would shadow its
        # own live sibling and regenerate the retired plan's Status instead.
        if any(part == "archive" for part in plan_path.relative_to(artifacts_dir).parts):
            continue
        try:
            content = plan_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            # One malformed file under artifacts/ must not blind the scan to
            # every other plan. `UnicodeDecodeError` is a `ValueError`, so the
            # narrower `except OSError` here let it escape to `regen-views`.
            continue
        if _declares_non_build_plan_artifact(content):
            continue  # scope-tagged, but declares itself a non-plan artifact
        _present, scope = _parse_build_plan_frontmatter_scope(content)
        if scope:
            yield plan_path, scope


def collect_release_pending_scopes(entries: list[ChangeLogEntry]) -> list[str]:
    """Distinct ``scope=`` values from unreleased/shipped entries, newest-first.

    Enumerates every scope that has at least one *tagged* change-log entry
    that is statusless, ``status=merged``, or ``status=shipped``, in
    change-log order (newest-first by file position), de-duplicated. A
    statusless tagged entry is the normal release-pending state (the entry
    merged inside its feature PR — single-pr-bookkeeping); ``merged`` is the
    accepted legacy stamp for the same state; ``shipped`` is the
    just-released (or historical) state. All three are included so
    ``regen-views`` flips the right plans regardless of which convention the
    log carries. A tag with an unrecognized ``status=`` (a typo) is excluded —
    the typo-guard owns that finding.
    """
    seen: set[str] = set()
    ordered: list[str] = []
    for entry in entries:
        status = entry.tags.get("status")
        statusless_tagged = status is None and entry.tag_line_count > 0
        if status not in VALID_STATUS_VALUES and not statusless_tagged:
            continue
        scope = entry.tags.get("scope")
        if isinstance(scope, str) and scope and scope not in seen:
            seen.add(scope)
            ordered.append(scope)
    return ordered


def diagnose_scope_plan_coverage(
    change_log_content: str, artifacts_dir: Path
) -> list[ScopedError]:
    """Flag release-pending scopes with no plan file + duplicate scopes.

    Pure diagnostic (mirrors :func:`validate_status_values`). Every error it
    returns is **scope-attributed** (:class:`ScopedError`), because both cases
    can only make ONE scope's ``## Status`` view wrong: the caller suppresses
    that view and still writes release-notes and scope-rollups, which have no
    plan-roster dependency (the regen-views-is-advice ruling, 2026-08-01 —
    ``learnings.md``). Until that ruling the caller treated these as fatal for
    the whole run (VWS-6R4T), so one unresolvable scope stopped every unrelated
    view from regenerating — realized on the reporting repo, and latent on the
    repos carrying the most nested plans, which were safe only because
    ``views_enabled`` was unset. Two cases:

    * An unreleased scope with NO matching build-plan file — its ``## Status``
      cannot be regenerated, a real release-process error. "Unreleased" covers
      both **statusless tagged** entries (the normal release-pending state —
      single-pr-bookkeeping; first flagged by the REL-9F2T audit, where a
      statusless entry with a bad ``scope=`` was undetected until release)
      and the legacy ``status=merged`` stamp.
      A ``status=shipped`` scope with no file is deliberately NOT flagged:
      its plan is a retired historical artifact or predates the ``scope:``
      frontmatter convention, so the absence is expected, not an error.
    * Two build-plan files declaring the same ``scope:`` — ambiguous; the
      map keeps the first by sorted path.

    **Both cases apply only to files this module considers build plans**, and
    that determination now has ONE home —
    :func:`iter_scoped_plan_candidates` — rather than a copy here that had to
    stay identical to :func:`build_scope_to_plan_map`'s. It did not: on
    2026-08-01 a scope-tagged collapse-map artifact made this function fatal and
    stopped ``regen-views`` writing views for EVERY scope, because the
    diagnostic condemned a file the map never considered.

    Returns ``[]`` when coverage is clean.
    """
    warnings: list[ScopedError] = []
    first_seen: dict[str, Path] = {}
    for plan_path, scope in iter_scoped_plan_candidates(artifacts_dir):
        if scope in first_seen:
            warnings.append(
                ScopedError(
                    f"duplicate scope={scope!r}: "
                    f"{_display_path(plan_path, artifacts_dir)} also declares it "
                    f"(keeping {_display_path(first_seen[scope], artifacts_dir)}); "
                    f"one plan is malformed.",
                    scope=scope,
                )
            )
        else:
            first_seen[scope] = plan_path

    plan_map = build_scope_to_plan_map(artifacts_dir)
    seen: set[str] = set()
    for entry in parse_change_log(change_log_content):
        status = entry.tags.get("status")
        if status == "merged":
            label = "release-pending (status=merged)"
        elif status is None and entry.tag_line_count > 0:
            # A statusless TAGGED entry is the normal release-pending state
            # (single-pr-bookkeeping) — same release-integrity stakes as
            # status=merged, so the no-plan-file check applies equally.
            label = "unreleased (statusless — release-pending)"
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
                ScopedError(
                    f"change-log scope={scope!r} is {label} "
                    f"but has no matching build-plan file under artifacts/ "
                    f"(searched recursively) — its ## Status cannot be "
                    f"regenerated. Other views are unaffected and were written.",
                    scope=scope,
                )
            )
    return warnings


def validate_chunk_roster(
    change_log_content: str, artifacts_dir: Path
) -> list[ScopedError]:
    """One error per ``chunks=`` ID that can never flip a checkbox (VWS-6R4T).

    Scope-attributed (:class:`ScopedError`), like
    :func:`diagnose_scope_plan_coverage`: a ``chunks=`` ID that matches no line
    in its plan's roster can only make THAT plan's ``## Status`` view wrong, so
    the caller suppresses that one view rather than the run.

    The silent-partial-flip failure class: a ``chunks=`` ID that matches no
    ``Chunk <id>:`` line in its plan's ``## Status`` section simply never
    flips, with no signal — the entry parses fine, the regen "succeeds", and
    the miss surfaces months later as a stale checkbox. This pure validator
    makes the miss loud: for every entry whose ``scope=`` resolves to a
    build-plan FILE (via :func:`build_scope_to_plan_map`), every ``chunks=``
    ID must match that plan's Status roster after :func:`normalize_chunk_id`
    on both sides. It also errors when the entry carries chunk IDs but the
    plan's roster is empty or the ``## Status`` section is absent.

    Validation applies to entries of EVERY status, shipped included —
    release-prep flips entries to ``shipped`` *before* running regen-views,
    so a shipped-exempt validator would never fire at the moment it matters.

    Deliberately outside the contract: entries with no ``scope=`` (legacy
    unfiltered single-plan repos — no roster to resolve against) and scopes
    with no plan file (historical/retired plans;
    :func:`diagnose_scope_plan_coverage` owns the unreleased subset of those).

    Returns ``[]`` when every resolvable ``chunks=`` ID matches its roster.
    """
    errors: list[ScopedError] = []
    plan_map = build_scope_to_plan_map(artifacts_dir)
    # Cache per plan file: (verbatim roster IDs, normalized roster set).
    rosters: dict[Path, tuple[list[str], set[str]]] = {}
    for entry in parse_change_log(change_log_content):
        scope = entry.tags.get("scope")
        chunks = entry.tags.get("chunks")
        if not (isinstance(scope, str) and scope):
            continue
        if not (isinstance(chunks, list) and chunks):
            continue
        plan_path = plan_map.get(scope)
        if plan_path is None:
            continue
        if plan_path not in rosters:
            try:
                plan_content = plan_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            _start, _end, section = extract_status_section(plan_content)
            roster = [
                m.group("id")
                for m in (CHUNK_LINE_RE.match(line) for line in section)
                if m
            ]
            rosters[plan_path] = (
                roster,
                {normalize_chunk_id(c) for c in roster},
            )
        roster, roster_norm = rosters[plan_path]
        missing = [
            c
            for c in chunks
            if isinstance(c, str) and normalize_chunk_id(c) not in roster_norm
        ]
        if missing:
            roster_desc = (
                ", ".join(roster)
                if roster
                else "(empty — no chunk checkboxes in ## Status)"
            )
            errors.append(
                ScopedError(
                    f"change-log entry {entry.title!r} (line {entry.line_number}) "
                    f"has chunks={','.join(missing)} not present in "
                    f"{_display_path(plan_path, artifacts_dir)}'s ## Status roster "
                    f"[{roster_desc}] — these IDs will never flip a checkbox "
                    f"(scope={scope!r}).",
                    scope=scope,
                )
            )
    return errors


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
    # The scope this view belongs to, for `status` results — resolved by
    # :func:`_detect_active_scope`, the same function that decides which
    # change-log entries the write consumes. `None` for the plan-independent
    # views (release-notes, scope-rollups) and for a plan that resolves to no
    # scope at all. The caller matches a scope-attributed validation error
    # (:class:`ScopedError`) against this to suppress exactly one view instead
    # of the whole run.
    scope: str | None = None


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

    When no scope-tagged plan and no existing pointer/default plan resolve, the
    behavior splits on whether a plan is genuinely *expected* (VWS-7N3K):

    * An ``active_build_plan`` pointer that is SET but resolves to a missing file
      is a real misconfiguration — raise ``FileNotFoundError`` (preserving the
      historical single-plan contract and keeping the STH-5P2W briefing guard
      meaningful).
    * An unset/null pointer with no resolvable plan is a legitimate "no active
      plan" state under the multi-scope model — return no status results (a
      no-op) so :func:`plan_regen` still regenerates the plan-independent
      release-notes and scope-rollups views instead of aborting the whole regen.
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
        # No scope-tagged plan resolved AND no pointer/default plan exists on
        # disk. Distinguish a genuine misconfiguration from a legitimate "no
        # active plan" (VWS-7N3K): an EXPLICITLY-pinned pointer to a missing file
        # is an error worth raising; an unset/null pointer is a clean-release
        # no-op that must NOT take down the plan-independent views.
        pointer = read_str_yaml_key(
            prawduct_dir / "project-state.yaml", BUILD_PLAN_POINTER_KEY
        )
        if pointer is not None:
            fallback = resolve_build_plan_path(prawduct_dir)
            raise FileNotFoundError(f"build-plan not found at {fallback}")
        return []

    results: list[ViewRegenResult] = []
    for plan_path in plan_paths:
        plan_rel = plan_path.relative_to(prawduct_dir).as_posix()
        try:
            plan_content = plan_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            # An unreadable plan is one plan's problem, not the whole regen's:
            # a multi-plan repo must still regenerate its other views. Reported
            # as a noop naming the cause rather than swallowed, so the operator
            # learns why a plan's Status did not move.
            results.append(
                ViewRegenResult(
                    name="status",
                    action="noop",
                    summary=f"Status ({plan_rel}): unreadable build-plan: {exc}",
                    path_relative=plan_rel,
                )
            )
            continue
        # The SAME resolution the write uses (`build_status_view` →
        # `_detect_active_scope`), not the raw frontmatter key. A plan with no
        # `scope:` key at all infers its scope from the most recent change-log
        # `scope=` tag, so keying suppression to the frontmatter would leave the
        # always-included pointer plan at `scope=None` — never matching
        # `suppressed_scopes`, yet written from the suppressed scope's tags.
        # Suppression must key on whatever decides the write, or it protects
        # nothing in exactly the case that needs protecting.
        plan_scope = _detect_active_scope(plan_content, change_log_content)
        status_new, status_changes = build_status_view(change_log_content, plan_content)
        if status_new is None:
            results.append(
                ViewRegenResult(
                    name="status",
                    action="noop",
                    summary=f"Status ({plan_rel}): up to date",
                    path_relative=plan_rel,
                    scope=plan_scope,
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
                scope=plan_scope,
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
