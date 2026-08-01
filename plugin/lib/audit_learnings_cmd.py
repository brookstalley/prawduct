"""F9 — Learnings lifecycle tracker.

Parses `.prawduct/learnings.md` for optional per-entry metadata, identifies
promotion / retirement / stale candidates, and (with ``apply=True``) retires
entries to ``learnings-detail.md``'s historical section by either of two
routes — a passing ``sentinel=`` test, or a ``superseded-by=`` pointer at the
broader rule that replaced it.

Schema (all fields optional; absence → "active, no lifecycle metadata"):

    ## Entry title
    <!-- prawduct-learning: confirmations=N; created=YYYY-MM-DD; sentinel=path/to/test.py::test_name -->
    <!-- prawduct-learning: superseded-by=Heading prefix of the rule that replaced this one -->

The HTML comment must be on the line immediately after the ``## Title`` line.
A comment placed deeper in the entry body is ignored — the strict placement
avoids parsing surprises when entries quote example metadata in their prose.

**Two retirement reasons, never both on one entry.** ``sentinel=`` retires a
rule because the failure mode it warned about is now structurally enforced by a
passing test. ``superseded-by=`` retires it because a *broader rule replaced
it*, which is what every consolidation is — and without it, consolidation is an
unauditable hand-edit, which is how a corpus accumulates near-duplicate
families: adding is cheap and merging is not. An entry
declaring both is an error and retires under neither, because the two answer
different questions and picking one silently would let a failing sentinel be
bypassed by adding a supersession key.

Public surface mirrors the ``run_migrate_*`` runners so JSON-mode callers
see the same dict shape (``product_dir``, ``applied``, plus per-category
lists). The runner does not raise on partial-result conditions — missing
``learnings.md`` is a clean empty result; only structural problems
(``.prawduct/`` absent) surface as ``{"error": "..."}``.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

# Threshold for "stale" entries: confirmations <= 1 AND created >= this many
# days ago. 90d matches the v1.4 plan's F9 section.
_STALE_THRESHOLD_DAYS = 90

# Metadata fields the audit logic acts on. Unknown keys are preserved in the
# entry's metadata dict (so future fields don't break the parser) and simply
# ignored — the parser has no allow-list and this set is not one.
#
# It is a SCHEMA ROSTER, and until this chunk it was decorative: the module had
# exactly one reference to it (this definition), while its comment claimed "the
# audit logic only consults this set" — a false statement about the code, in the
# one place a reader checks what the schema is. It is now pinned to the keys the
# logic actually reads, by ``TestKnownMetadataKeysMatchesTheLogic``, which parses
# this module's own ``meta.get(...)`` call sites. Drift in either direction fails:
# acting on a key not listed here, or listing one nothing reads.
_KNOWN_METADATA_KEYS = frozenset(
    {"confirmations", "created", "sentinel", "superseded-by"}
)

_METADATA_RE = re.compile(
    r"<!--\s*prawduct-learning:\s*(?P<body>.*?)\s*-->\s*$"
)

_HISTORICAL_SECTION_HEADER = "## Historical (structurally enforced)"
#: The header stays for continuity with entries already filed under it; the
#: blurb no longer claims sentinels are the only route, because supersession
#: retires a rule for a different reason entirely (a broader rule replaced it,
#: not a test now enforces it). Each entry states its own reason inline, so a
#: reader never has to infer it from the section it landed in.
_HISTORICAL_SECTION_BLURB = (
    "Learnings retired by `audit-learnings --apply`, for one of two reasons, "
    "stated on each entry: a declared `sentinel=` test now passes, so the "
    "failure mode is structurally enforced; or a broader rule superseded it, "
    "in which case the entry names its replacement. Kept here as historical "
    "context.\n"
)


@dataclass
class LearningEntry:
    """A single ``## Title`` block from ``learnings.md``.

    ``body_lines`` is the verbatim slice between the title and the next entry
    (or end of file), excluding the title itself but INCLUDING the metadata
    comment line if present. This lets the serializer round-trip without
    reconstructing comments.
    """

    title: str
    body_lines: list[str]
    metadata: dict[str, str] = field(default_factory=dict)


def parse_learning_metadata(line: str) -> dict[str, str] | None:
    """Parse a single ``<!-- prawduct-learning: ... -->`` comment line.

    Returns the metadata dict on match, ``None`` otherwise. Unknown keys are
    kept (audit logic ignores them); malformed key/value pairs (no ``=``) are
    dropped silently so a stray semicolon in prose can't break parsing.

    Whitespace and trailing semicolons are tolerated. Multiple instances of
    the same key keep the first occurrence (typical of accidental
    duplication during manual editing).
    """
    match = _METADATA_RE.match(line.strip())
    if not match:
        return None

    body = match.group("body")
    result: dict[str, str] = {}
    for raw_pair in body.split(";"):
        pair = raw_pair.strip()
        if not pair or "=" not in pair:
            continue
        key, _, value = pair.partition("=")
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if key not in result:
            result[key] = value
    return result


def parse_learnings_file(content: str) -> list[LearningEntry]:
    """Segment ``learnings.md`` content into entries by ``## `` headers.

    The metadata comment is only honored when it appears on the line
    immediately following the title — a comment in the body is ignored. This
    matters because some entries quote example metadata in their prose
    (this module's own docstring, for instance).

    Lines before the first ``## `` heading (file preamble) are discarded —
    they belong to the file structure, not to any entry. The caller
    reconstructs them in :func:`serialize_learnings`.
    """
    entries: list[LearningEntry] = []
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("## "):
            title = line[3:].strip()
            body_start = i + 1
            # Find next entry boundary (next ## heading or EOF).
            j = body_start
            while j < len(lines) and not lines[j].startswith("## "):
                j += 1
            body_lines = lines[body_start:j]

            metadata: dict[str, str] = {}
            # Metadata must be on the first non-blank line of the body to
            # count. Blank lines between title and comment are tolerated.
            for body_line in body_lines:
                if not body_line.strip():
                    continue
                parsed = parse_learning_metadata(body_line)
                if parsed is not None:
                    metadata = parsed
                break

            entries.append(
                LearningEntry(
                    title=title, body_lines=body_lines, metadata=metadata
                )
            )
            i = j
        else:
            i += 1
    return entries


def _entry_block(entry: LearningEntry) -> str:
    """Serialize a single entry back to its original markdown form."""
    body = "\n".join(entry.body_lines)
    return f"## {entry.title}\n{body}"


def _strip_metadata_comment(body_lines: list[str]) -> list[str]:
    """Drop the lifecycle comment from a body on its way to the historical
    section, mirroring the parser's own placement rule (first non-blank line).

    A retired entry's ``sentinel=`` / ``superseded-by=`` keys are directives
    *for the active corpus*. Carried into ``learnings-detail.md`` they are
    inert — that file is never parsed — while still reading as live lifecycle
    state, and the repo pins their absence
    (``test_no_lifecycle_metadata_has_drifted_to_the_detail_file``) precisely
    because an inert comment in the detail file once disabled the whole
    mechanism. Verified against that guard: retiring any annotated entry
    without this strip fails it, which would have blocked Chunk 03's collapse
    the first time it ran ``--apply`` on this repo. The retirement note this
    module writes in its place carries the same facts in a form a reader can
    use.
    """
    out = list(body_lines)
    for idx, line in enumerate(out):
        if not line.strip():
            continue
        if parse_learning_metadata(line) is not None:
            del out[idx]
        break
    return out


def _retirement_note(
    *,
    retired_on: date,
    sentinel: str | None = None,
    superseded_by: str | None = None,
) -> str:
    """The one-line reason a historical entry carries, replacing its comment.

    For a supersession this is the **forwarding address** — the whole point of
    the lifecycle event. A reader who remembers the old rule and cannot find it
    must land on the rule that replaced it, not on a hole.
    """
    if superseded_by is not None:
        return (
            f"*Retired {retired_on.isoformat()} — superseded by "
            f"**{superseded_by}**. That rule is the active statement; this one "
            "is kept for readers who remember it.*"
        )
    return (
        f"*Retired {retired_on.isoformat()} — sentinel `{sentinel}` passes, so "
        "the failure mode this warned about is structurally enforced.*"
    )


def _historical_block(
    entry: LearningEntry, note: str, narrative: str = ""
) -> str:
    """A retired entry as it appears in the historical section: title, its
    retirement note, then the body with the live lifecycle comment removed.

    The note sits directly under the title because that is where a reader who
    followed a stale reference looks first — a forwarding address buried below
    the body is one they read the whole entry to find.

    ``narrative`` is the entry's pre-existing ``learnings-detail.md`` prose,
    folded in here so retirement stays a MOVE. Without it the detail file grows
    a second block under the same heading, and the *undecorated* one sorts
    first — so `/prawduct:learnings`, which reads that file for Key Context,
    returns a retired rule as current with no successor. That is precisely the
    hole-that-reads-as-a-forwarding-address this lifecycle exists to prevent,
    reintroduced one file over. Found by all three reviewers independently on
    the first bulk `--apply` (2026-08-01), which duplicated 17 headings.
    """
    body = "\n".join(_strip_metadata_comment(entry.body_lines)).strip("\n")
    parts = [f"## {entry.title}", "", note]
    if body:
        parts += ["", body]
    narrative = narrative.strip("\n")
    if narrative:
        parts += ["", narrative]
    return "\n".join(parts)


def _take_active_narrative(lines: list[str], title: str, limit: int) -> str:
    """Cut the ``## title`` block living ABOVE ``limit`` out of ``lines`` and
    return its body. Mutates ``lines``. Returns ``""`` when there is none.

    ``limit`` is the historical section's index, so a heading already archived
    is never re-cut — otherwise a re-run would strip the note it wrote last
    time. Matching is exact on the title, mirroring how the pairing is
    maintained everywhere else; a heading that has drifted out of exact match
    is left alone rather than guessed at, because cutting the wrong block
    silently destroys an unrelated narrative.
    """
    start = None
    for i in range(min(limit, len(lines))):
        if lines[i].startswith("## ") and lines[i][3:].strip() == title:
            start = i
            break
    if start is None:
        return ""
    end = start + 1
    while end < limit and not lines[end].startswith("## "):
        end += 1
    body = "\n".join(lines[start + 1 : end]).strip("\n")
    del lines[start:end]
    return body


def resolve_supersession_target(
    prefix: str, titles: list[str], own_title: str
) -> tuple[str | None, str | None]:
    """Resolve a ``superseded-by=`` heading prefix against ``learnings.md``
    titles. Returns ``(resolved_title, error)`` — exactly one is non-``None``.

    Fail-closed on every ambiguity, the same posture the failing-sentinel path
    takes, and the direct analogue of the corpus rule that an absence-claim must
    cite a path that resolves: a forwarding pointer nobody can follow is worse
    than no retirement, because the rule is gone AND the replacement is
    unfindable.

    Prefix matching is case-sensitive and anchored at the start of the heading.
    A case-insensitive or substring fallback would make the common near-miss
    resolve to *something*, which is the failure this returns an error for.
    """
    needle = prefix.strip()
    if not needle:
        return None, "`superseded-by=` is empty — name the heading that replaced this rule"

    matches = [t for t in titles if t.startswith(needle)]

    if own_title.startswith(needle) and len(matches) == 1:
        return None, (
            f"`superseded-by={needle}` resolves to this entry's own heading — "
            "a rule cannot supersede itself"
        )

    if not matches:
        return None, (
            f"`superseded-by={needle}` names a heading that does not resolve in "
            "learnings.md — a forwarding pointer nobody can follow is worse "
            "than no retirement"
        )
    if len(matches) > 1:
        shown = "; ".join(f"'{t[:60]}'" for t in matches[:3])
        more = f" (+{len(matches) - 3} more)" if len(matches) > 3 else ""
        return None, (
            f"`superseded-by={needle}` is ambiguous — it matches {len(matches)} "
            f"headings: {shown}{more}. Lengthen the prefix until it is unique"
        )
    return matches[0], None


def run_sentinel(
    product_dir: Path, sentinel: str, *, timeout: int = 120
) -> tuple[bool, str]:
    """Run ``python3 -m pytest <sentinel> -q`` from ``product_dir``.

    Returns ``(passed, excerpt)``. The excerpt is the trailing portion of
    pytest's combined stdout/stderr (last ~20 lines) so callers can surface
    actionable failure context without dumping the full transcript.

    Subprocess failures (timeout, missing pytest, OS errors) return
    ``(False, "<diagnostic>")`` rather than raising — the audit must keep
    walking through remaining entries even when one sentinel is misconfigured.
    """
    try:
        result = subprocess.run(
            ["python3", "-m", "pytest", sentinel, "-q"],
            cwd=str(product_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, f"sentinel timed out after {timeout}s"
    except (OSError, FileNotFoundError) as exc:
        return False, f"could not invoke pytest: {exc}"

    combined = (result.stdout or "") + (result.stderr or "")
    tail = "\n".join(combined.splitlines()[-20:])
    return result.returncode == 0, tail


def _parse_iso_date(value: str) -> date | None:
    """Parse ``YYYY-MM-DD``. Returns ``None`` on malformed input."""
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _coerce_int(value: str) -> int | None:
    try:
        return int(value.strip())
    except (ValueError, TypeError):
        return None


def audit_learnings(
    product_dir: Path,
    *,
    apply: bool = False,
    today: date | None = None,
    run_sentinels: bool = True,
) -> dict:
    """Classify entries in ``learnings.md`` by lifecycle stage.

    Returns a dict with five lists plus the run mode:

      * ``promotions`` — entries with ``confirmations >= 2``. Advisory only;
        no file mutation regardless of ``apply``. Promotion in this design
        means "surface the confirmation count" — `learnings.md` doesn't have
        a sectioned active/promoted split.
      * ``retirements`` — retirement candidates by EITHER route, discriminated
        by ``reason`` (``"sentinel"`` | ``"superseded-by"``). Every record
        carries the same keys, so a reader branches on ``reason`` rather than
        probing for which are present: ``sentinel``/``passed``/
        ``output_excerpt`` are meaningful on the sentinel route and ``None``/
        ``""`` on the other, and ``superseded_by``/``resolved_to`` the reverse.
        Both routes live in this one list on purpose — a consumer asking "what
        is being retired?" must see all of it, and a separate list would
        under-report to every existing reader while looking complete. Additive
        under `api-contract.md`'s norm: new keys, no key repurposed, and
        ``retirements`` still means exactly what it meant.

        With ``apply=True``, a passing sentinel or a *resolvable*
        ``superseded-by=`` moves the entry to ``learnings-detail.md`` under the
        historical section, carrying a one-line retirement note in place of its
        lifecycle comment.
      * ``stale_flags`` — entries with ``created`` more than 90 days ago and
        ``confirmations <= 1``. The ``created`` field is required for
        staleness detection — entries that lack it never appear here.
      * ``errors`` — entries whose declared sentinel exists but failed; entries
        with unparseable date fields; entries whose ``superseded-by=`` does not
        resolve to exactly one other heading; and entries declaring both
        retirement keys. Every one of these RETAINS the entry — the audit fails
        closed on an ambiguous retirement exactly as it does on a failing
        sentinel. The audit keeps going; the per-entry error string tells the
        user what to fix.
      * ``applied`` — bool mirror of the ``apply`` argument; surfaces in the
        result so JSON-mode callers know whether mutations happened.

    ``today`` and ``run_sentinels`` are test seams. ``today=None`` uses the
    real wall clock; ``run_sentinels=False`` short-circuits the subprocess
    call (entries with sentinels just appear in ``retirements`` with
    ``passed=None`` and don't trigger errors). Both default to production
    behavior.
    """
    if today is None:
        today = date.today()

    promotions: list[dict] = []
    retirements: list[dict] = []
    stale_flags: list[dict] = []
    errors: list[dict] = []

    learnings_path = product_dir / ".prawduct" / "learnings.md"
    if not learnings_path.is_file():
        return {
            "product_dir": str(product_dir),
            "applied": apply,
            "promotions": promotions,
            "retirements": retirements,
            "stale_flags": stale_flags,
            "errors": errors,
        }

    content = learnings_path.read_text()
    entries = parse_learnings_file(content)

    retained_entries: list[LearningEntry] = []
    #: (entry, note) in retirement order — a parallel LIST, not a dict keyed by
    #: title. Titles are not unique by construction: nothing in the parser or
    #: the audit rejects two `## ` entries with the same heading, so a dict
    #: would collapse two same-titled retirements to the last note written and
    #: stamp one entry's history with the other's reason. Silent, and wrong in
    #: the file a reader consults precisely when they cannot find a rule.
    retired_with_notes: list[tuple[LearningEntry, str]] = []

    #: Supersession targets resolve against the corpus as it stands BEFORE this
    #: run retires anything. A two-step consolidation (A superseded by B, B by
    #: C, both applied in one pass) therefore resolves both pointers rather
    #: than failing the first one for naming a heading the same run removed;
    #: the reader following A lands on B in the historical section, which
    #: carries its own pointer to C. A chain that terminates in history is a
    #: worse read than a direct pointer and a much better one than a hole.
    all_titles = [e.title for e in entries]

    for entry in entries:
        meta = entry.metadata
        if not meta:
            retained_entries.append(entry)
            continue

        # Promotions: confirmations >= 2. Advisory only — surface but never
        # rewrite the file.
        confirmations_raw = meta.get("confirmations")
        confirmations: int | None = None
        if confirmations_raw is not None:
            confirmations = _coerce_int(confirmations_raw)
            if confirmations is None:
                errors.append({
                    "title": entry.title,
                    "error": (
                        f"could not parse confirmations='{confirmations_raw}' "
                        "as integer"
                    ),
                })
            elif confirmations >= 2:
                promotions.append({
                    "title": entry.title,
                    "confirmations": confirmations,
                })

        # Sentinel handling: an entry with a declared sentinel is a
        # retirement candidate. Whether the sentinel currently passes
        # determines whether `apply=True` actually moves the entry.
        sentinel = meta.get("sentinel")
        superseded_by = meta.get("superseded-by")
        sentinel_passed: bool | None = None
        sentinel_excerpt = ""
        # `is not None`, NOT truthiness. `parse_learning_metadata` strips the
        # value, so a half-finished `superseded-by=` (or `superseded-by=   `)
        # arrives as `""` — falsy on every branch, so the entry fell through to
        # "active, no lifecycle metadata" with no error, no record, and no CLI
        # line, while three records promised an error. The empty-prefix branch
        # in `resolve_supersession_target` was unreachable from production for
        # the same reason, and its test passed only by calling the helper
        # directly with an input the parser cannot emit.
        if sentinel and superseded_by is not None:
            # Two retirement reasons on one entry is an authoring error, not a
            # precedence question. Picking either silently would let a FAILING
            # sentinel be bypassed by adding a supersession key — a gate
            # weakened by an edit to the thing it guards.
            errors.append({
                "title": entry.title,
                "error": (
                    "declares both `sentinel=` and `superseded-by=` — these are "
                    "different retirement reasons and the entry retires under "
                    "neither. Keep the one that is true: a passing test, or a "
                    "broader rule that replaced this one"
                ),
            })
            retained_entries.append(entry)
        elif superseded_by is not None:
            resolved, why = resolve_supersession_target(
                superseded_by, all_titles, entry.title
            )
            record = {
                "title": entry.title,
                "reason": "superseded-by",
                # Present-as-None rather than absent: every retirement record
                # keeps the same key set, so a reader can branch on `reason`
                # without probing for which keys exist.
                "sentinel": None,
                "passed": None,
                "output_excerpt": "",
                "superseded_by": superseded_by,
                "resolved_to": resolved,
                "applied": False,
            }
            if resolved is None:
                errors.append({"title": entry.title, "error": why})
                retained_entries.append(entry)
            elif apply:
                record["applied"] = True
                retired_with_notes.append((entry, _retirement_note(
                    retired_on=today, superseded_by=resolved
                )))
            else:
                retained_entries.append(entry)
            retirements.append(record)
        elif sentinel:
            if run_sentinels:
                sentinel_passed, sentinel_excerpt = run_sentinel(
                    product_dir, sentinel
                )
            retirement_record = {
                "title": entry.title,
                "reason": "sentinel",
                "superseded_by": None,
                "resolved_to": None,
                "sentinel": sentinel,
                "passed": sentinel_passed,
                "output_excerpt": sentinel_excerpt,
                "applied": False,
            }
            if sentinel_passed is False:
                # Failing sentinel: surfaced as both a retirement attempt
                # (record on disk) AND an error (so users see "fix me"
                # without needing to inspect every retirement entry).
                errors.append({
                    "title": entry.title,
                    "error": (
                        f"sentinel '{sentinel}' is failing — fix the test "
                        "or update the learning before retiring"
                    ),
                })
                retirements.append(retirement_record)
                retained_entries.append(entry)
            elif sentinel_passed is True:
                if apply:
                    retirement_record["applied"] = True
                    retired_with_notes.append((entry, _retirement_note(
                        retired_on=today, sentinel=sentinel
                    )))
                else:
                    retained_entries.append(entry)
                retirements.append(retirement_record)
            else:
                # run_sentinels=False — record as candidate without
                # actually trying to retire.
                retirements.append(retirement_record)
                retained_entries.append(entry)
        else:
            retained_entries.append(entry)

        # Staleness: created > 90d ago AND confirmations <= 1. The ``created``
        # field is required — entries without it never show up here. (Stale
        # check is independent of sentinel; a sentineled stale entry surfaces
        # in both lists, which is the right read for the user.)
        created_raw = meta.get("created")
        if created_raw:
            created = _parse_iso_date(created_raw)
            if created is None:
                errors.append({
                    "title": entry.title,
                    "error": (
                        f"could not parse created='{created_raw}' "
                        "as YYYY-MM-DD"
                    ),
                })
            else:
                age_days = (today - created).days
                effective_confirmations = (
                    confirmations if confirmations is not None else 0
                )
                if (
                    age_days >= _STALE_THRESHOLD_DAYS
                    and effective_confirmations <= 1
                ):
                    stale_flags.append({
                        "title": entry.title,
                        "created": created_raw,
                        "age_days": age_days,
                        "confirmations": effective_confirmations,
                    })

    if apply and retired_with_notes:
        _apply_retirements(
            learnings_path, retained_entries, retired_with_notes, content,
        )

    return {
        "product_dir": str(product_dir),
        "applied": apply,
        "promotions": promotions,
        "retirements": retirements,
        "stale_flags": stale_flags,
        "errors": errors,
    }


def _apply_retirements(
    learnings_path: Path,
    retained_entries: list[LearningEntry],
    retired_with_notes: list[tuple[LearningEntry, str]],
    original_content: str,
) -> None:
    """Rewrite ``learnings.md`` with retired entries removed, and append
    those entries to ``learnings-detail.md`` under the historical section.

    The preamble of ``learnings.md`` (everything before the first ``## ``
    heading) is preserved verbatim. The detail file is created with a
    minimal header if absent; the historical section is created if absent.

    ``retired_with_notes`` pairs each retired entry with the one-line reason
    its historical copy carries — the forwarding address for a supersession,
    the passing sentinel for the other route. A parallel list rather than a
    dict keyed by title, because titles are not unique by construction: two
    same-titled entries retiring in one pass would collapse to one note and
    stamp the earlier entry's history with the later one's reason. Required
    rather than optional-with-a-verbatim-fallback: the sole caller always
    builds it, so a fallback would be a branch no test can reach through the
    public API, and its behavior (copying the entry verbatim, lifecycle
    comment included) is exactly the defect this parameter exists to fix.
    """
    # Rebuild learnings.md preserving the preamble.
    lines = original_content.split("\n")
    preamble_end = len(lines)
    for idx, line in enumerate(lines):
        if line.startswith("## "):
            preamble_end = idx
            break

    preamble = "\n".join(lines[:preamble_end]).rstrip("\n")
    rebuilt_parts: list[str] = []
    if preamble:
        rebuilt_parts.append(preamble + "\n")
    for entry in retained_entries:
        rebuilt_parts.append(_entry_block(entry).rstrip("\n") + "\n")
    new_content = "\n".join(rebuilt_parts).rstrip("\n") + "\n"

    detail_path = learnings_path.parent / "learnings-detail.md"
    detail_content = _detail_with_retirements(detail_path, retired_with_notes)

    # BOTH files are composed before EITHER is written, and the ARCHIVE is
    # written before the active file. Retirement is a MOVE, and a move that can
    # half-happen is data loss — so the two-line window that remains is aimed
    # at the recoverable failure.
    #
    # Composing first removes every logic error from the window. There was one:
    # a guard that tested substring while its locator tested equality, raising
    # StopIteration on a decorated heading, after `learnings.md` had already
    # been rewritten — entries gone from the active file and filed nowhere.
    #
    # Ordering handles the I/O half, which composition cannot. Two writes across
    # two files are not atomic, but they have a DIRECTION: detail-then-learnings
    # fails toward a duplicate (the entry is in both files — visible, and a
    # re-run reconciles it), while learnings-then-detail fails toward deletion.
    # Same probability, opposite blast radius, and Chunk 03's bulk `--apply` is
    # the first caller.
    detail_path.write_text(detail_content)
    learnings_path.write_text(new_content)


def _find_historical_section(lines: list[str]) -> int | None:
    """Index of the historical section's heading, or ``None``.

    ONE predicate, used by both the "does it exist" question and the "where is
    it" question. Those were once a substring test and an equality test, which
    disagree on any decorated heading (``## Historical (structurally enforced)
    — 2026 archive``, or a ``###`` variant): the guard said present, the
    locator found nothing, and the bare ``next()`` raised.
    """
    for i, line in enumerate(lines):
        if line.strip().startswith(_HISTORICAL_SECTION_HEADER):
            return i
    return None


def _detail_with_retirements(
    detail_path: Path, retired_with_notes: list[tuple[LearningEntry, str]]
) -> str:
    """The full new text of ``learnings-detail.md``. Pure — writes nothing."""
    if detail_path.is_file():
        detail_content = detail_path.read_text()
    else:
        detail_content = (
            "# Learnings — Full Detail\n\n"
            "Historical record of learnings with their full context. "
            "See `learnings.md` for the active rule list.\n"
        )

    # Cut each retiring entry's ACTIVE narrative out of the detail file before
    # composing its historical block, so the prose MOVES rather than being
    # duplicated under a second copy of the same heading. Done against a live
    # `lines` list — and the historical boundary is re-found after every cut,
    # because each removal shifts it upward.
    lines = detail_content.split("\n")
    narratives: list[str] = []
    for entry, _note in retired_with_notes:
        boundary = _find_historical_section(lines)
        limit = boundary if boundary is not None else len(lines)
        narratives.append(_take_active_narrative(lines, entry.title, limit))

    appended_blocks = "\n".join(
        _historical_block(entry, note, narrative).rstrip("\n") + "\n"
        for (entry, note), narrative in zip(retired_with_notes, narratives)
    )

    start = _find_historical_section(lines)
    if start is None:
        # Rebuild from `lines`, NOT from `detail_content` — the narratives were
        # cut out of `lines`, and returning the original string here would put
        # every one of them back while also writing its historical copy, which
        # is the duplication this function now exists to prevent.
        remaining = "\n".join(lines)
        if not remaining.endswith("\n"):
            remaining += "\n"
        return remaining + (
            "\n" + _HISTORICAL_SECTION_HEADER + "\n\n"
            + _HISTORICAL_SECTION_BLURB
            + "\n" + appended_blocks
        )

    # The section EXISTS — insert at its end, not the file's. Appending to EOF
    # is the same place only while the section is last, and the docstring has
    # claimed "under the historical section" the whole time. Chunk 03's bulk
    # collapse is the first `--apply` here, so once any later top-level section
    # exists, EOF-appending files every retirement under a heading it does not
    # belong to — with the file reading as though it did.
    end = len(lines)
    for i in range(start + 1, len(lines)):
        # Only a TOP-level heading closes the section: retired entries are `## `
        # and every block this function writes belongs inside. A detail file
        # with no later top-level heading appends at EOF exactly as before.
        if lines[i].startswith("# ") and not lines[i].startswith("## "):
            end = i
            break
    tail = "\n".join(lines[end:])
    head = "\n".join(lines[:end]).rstrip("\n")
    out = head + "\n\n" + appended_blocks
    if tail.strip():
        out = out.rstrip("\n") + "\n\n" + tail
    return out


def run_audit_learnings(product_dir: str, *, apply: bool = False) -> dict:
    """User-facing runner for ``prawduct-hook audit-learnings``.

    Matches the ``run_migrate_*`` shape so the CLI dispatch and JSON-mode
    callers see a consistent contract:

        {
          "product_dir": "/abs/path",
          "applied": bool,
          "promotions": [...],
          "retirements": [...],
          "stale_flags": [...],
          "errors": [...],
        }

    Returns ``{"error": "..."}`` only for structural problems (no
    ``.prawduct/`` directory) — a missing ``learnings.md`` is a clean empty
    result, not an error. Sentinel subprocess failures are absorbed into
    per-entry ``errors`` entries; the runner itself does not raise.
    """
    product_path = Path(product_dir).resolve()
    prawduct_dir = product_path / ".prawduct"
    if not prawduct_dir.is_dir():
        return {
            "error": (
                f"Not a prawduct product: {product_path} has no .prawduct/ "
                "directory"
            )
        }

    return audit_learnings(product_path, apply=apply)
