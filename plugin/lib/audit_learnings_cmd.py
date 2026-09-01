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

**The key set is closed.** ``confirmations``, ``created``, ``sentinel`` and
``superseded-by`` are the whole schema; any other well-formed ``key=value`` is
reported as an error rather than ignored, because a misspelled directive
(``sentinal=``) parses cleanly, does nothing, and still reads in the file as a
live lifecycle annotation. Fragments with no ``=`` remain tolerated — those are
prose that resembled metadata, not metadata that resembled a directive.

**Grading a ``sentinel=`` needs the product to say how.** ``sentinel_command:``
in ``project-state.yaml`` supplies the invocation, carrying a ``{sentinel}``
placeholder for the file to run (``sentinel_command: npx vitest run {sentinel}``).
Without it a sentinel is reported **ungraded**, never failed — prawduct governs
products in every language and does not guess at one's test runner.

**Ungraded is not failed, and the line between them is this.** A sentinel grades
``False`` only when a runner *returned a verdict about this rule*. Everything
else — no declared command, a malformed one, a path-shaped target that is gone,
a command that could not launch, one that timed out, and one that exited with a
code the product declared as "could not run" — is ``None``, ungraded, and raises
no error against the test. The distinction matters because this audit decides
which learnings are structurally enforced: a rule reported as failing when
nothing judged it argues for retiring a rule that is still enforced, which is
the one outcome this subsystem must never produce.

Prawduct cannot tell a broken environment from a real failure on its own —
exit codes are per-runner and prawduct must not learn them. So the product
declares it, in the same posture ``sentinel_command:`` already establishes::

    sentinel_command: npx vitest run {sentinel}
    sentinel_ungraded_exit_codes: 1

Any exit code listed there means *the runner could not judge this rule* and
grades ungraded instead of failed. Absent, every non-zero exit is a real
failure, which is the pre-existing behaviour and the right default for a runner
that does not distinguish. ``0`` may not be listed: a command that exited
successfully returned a verdict, and declaring it here would render every
green sentinel ungraded (``brookstalley/prawduct#720``).

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
import shlex
import subprocess
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

# Threshold for "stale" entries: confirmations <= 1 AND created >= this many
# days ago. 90d matches the v1.4 plan's F9 section.
_STALE_THRESHOLD_DAYS = 90

# Metadata fields the audit logic acts on, and — since #346 — the ALLOW-LIST the
# audit validates parsed metadata against. The parser still has no allow-list:
# it keeps every well-formed key it meets, so this module stays the one place
# that decides what a key means. What changed is that the audit no longer stays
# SILENT about a key it does not know.
#
# Silence was the defect. `sentinal=`, `superceded-by=`, `supersededby=` all
# parse cleanly, act on nothing, and leave the entry reading as fully annotated
# — a lifecycle directive that looks live in the file and is inert in the
# machinery, which is the same class of failure the detail-file metadata strip
# exists to prevent one file over. A typo in a `sentinel=` key does not fail
# loudly on its own: the entry simply falls through to "active, no lifecycle
# metadata", indistinguishable from an entry nobody annotated.
#
# It is a SCHEMA ROSTER, and until an earlier chunk it was decorative: the module
# had exactly one reference to it (this definition), while its comment claimed
# "the audit logic only consults this set" — a false statement about the code, in
# the one place a reader checks what the schema is. It is now pinned to the keys
# the logic actually reads, by ``TestKnownMetadataKeysMatchesTheLogic``, which
# parses this module's own ``meta.get(...)`` call sites. Drift in either
# direction fails: acting on a key not listed here, or listing one nothing reads.
_KNOWN_METADATA_KEYS = frozenset(
    {"confirmations", "created", "sentinel", "superseded-by"}
)

_METADATA_RE = re.compile(
    r"<!--\s*prawduct-learning:\s*(?P<body>.*?)\s*-->\s*$"
)

#: Filenames of the three-tier corpus. The split is the whole point of #350:
#: `learnings-detail.md` was an unbounded sink — 557KB across 4,748 lines and
#: growing 65% a month, with 182KB of it archive — and every `/prawduct:learnings`
#: lookup read the archive to answer a question about the active corpus.
#:
#: * `learnings.md`         — the active rule index (bounded; the briefing nudges
#:                            it past 40KB).
#: * `learnings-detail.md`  — the narrative for ACTIVE rules only.
#: * `learnings-history.md` — retired entries. Append-only, deliberately
#:                            unbounded, and read ONLY on a miss: a reader who
#:                            remembers a rule and cannot find it looks here for
#:                            the forwarding address, and nobody else pays for it.
#:
#: That is the route out. The archive still never loses an entry — retirement
#: stays a MOVE, and now it moves one file further, out of the read path instead
#: of into a section at the bottom of it.
DETAIL_FILENAME = "learnings-detail.md"
HISTORY_FILENAME = "learnings-history.md"

_HISTORY_FILE_PREAMBLE = (
    "# Learnings — Retired\n\n"
    "Entries retired by `audit-learnings --apply`, moved out of "
    "`learnings-detail.md` so the active corpus stays the thing a lookup reads. "
    "**Nothing is ever deleted from this file.** A reader who remembers a rule "
    "and cannot find it in `learnings.md` looks here: each entry carries the "
    "reason it was retired and, for a supersession, the heading that replaced "
    "it.\n"
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
    KEPT — parsing and validation are deliberately separate steps. The parser
    reports what the line says; :func:`audit_learnings` decides whether the keys
    mean anything, and raises an ``errors`` entry for one that does not (#346).
    Splitting them this way keeps the parser usable by callers that only want
    the raw pairs, and keeps the roster check in the one place that owns the
    schema.

    Malformed key/value pairs (no ``=``) are still dropped silently, and that
    tolerance is deliberate and NOT reconsidered by #346: this comment lives on
    a prose line, and a stray semicolon in an entry's narrative must not turn
    into a validation finding. A no-``=`` fragment is *prose that resembled
    metadata*; a well-formed ``key=value`` whose key nobody reads is *metadata
    that resembled a directive*. Only the second makes a claim worth grading.

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


#: The readiness vocabulary, in the order a renderer should prefer it. ``ready``
#: and ``blocked`` are verdicts about the rule; ``ungraded`` is the absence of a
#: verdict, and collapsing it into ``blocked`` is the false accusation this
#: subsystem keeps having to un-make — it tells an operator a test is failing
#: when prawduct never ran one.
RETIREMENT_READINESS_STATES = ("ready", "blocked", "ungraded")


def retirement_readiness(record: dict) -> dict:
    """The ONE place that decides whether a retirement candidate is retirable.

    Returns the three additive fields every ``retirements`` record carries —
    ``ready`` (the decision), ``readiness`` (its label, one of
    :data:`RETIREMENT_READINESS_STATES`), and ``why`` (the route-appropriate
    one-line reason a renderer prints). ``ready`` is exactly
    ``readiness == "ready"``, pinned by test rather than left to agree by
    convention.

    **Why this is a function and not three lines at each call site.** The
    predicate was re-derived in three places — here, the CLI printer, and
    doctor's prose — and the routes do not share a field: a sentinel candidate
    is ready when ``passed is True``, a supersession when ``resolved_to`` is not
    ``None``. A consumer reading ``passed`` for both reports every resolvable
    supersession as blocked, because its ``passed`` is ``None`` by construction.
    Each re-derivation is a chance to get that backwards, and the copy furthest
    from the producer (prose in a skill file) cannot be tested at all.

    **Dispatch is exhaustive on ``reason``, with no catch-all ``else``.** The
    printer's ``else`` arm meant "everything that is not ``superseded-by``",
    so a third retirement route would have been graded by reading its
    ``sentinel`` field — ``None`` — and rendered ``blocked``: a brand-new route
    reported as a failing test. An unrecognised ``reason`` is ``ungraded`` and
    says so by name, which is the honest reading and the one that surfaces the
    gap instead of hiding it.

    Consumers RENDER this. A consumer that recomputes it is the defect.
    """
    reason = record.get("reason")
    if reason == "superseded-by":
        resolved = record.get("resolved_to")
        target = resolved or record.get("superseded_by")
        return {
            "ready": resolved is not None,
            "readiness": "ready" if resolved is not None else "blocked",
            "why": f"superseded-by={target}",
        }
    if reason == "sentinel":
        passed = record.get("passed")
        # Three-valued, and `bool()` would flatten it. `None` is ungraded, not
        # blocked: no command declared, an unrunnable one, or the
        # `run_sentinels=False` seam.
        if passed is None:
            readiness = "ungraded"
        else:
            readiness = "ready" if passed is True else "blocked"
        return {
            "ready": passed is True,
            "readiness": readiness,
            "why": f"sentinel={record.get('sentinel')}",
        }
    return {
        "ready": False,
        "readiness": "ungraded",
        "why": (
            f"unrecognised retirement reason {reason!r} — prawduct has no rule "
            "for grading this route, so it reports no verdict rather than "
            "guessing one"
        ),
    }


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


def _take_active_narrative(
    lines: list[str], title: str, limit: int
) -> tuple[str, "str | None"]:
    """Cut the ``## title`` block living ABOVE ``limit`` out of ``lines`` and
    return ``(body, error)``. Mutates ``lines``. ``("", None)`` when there is
    no such block; ``("", <reason>)`` when it refuses, and then ``lines`` is
    untouched.

    ``limit`` is the historical section's index, so a heading already archived
    is never re-cut — otherwise a re-run would strip the note it wrote last
    time. Matching is exact on the title, mirroring how the pairing is
    maintained everywhere else; a heading that has drifted out of exact match
    is left alone rather than guessed at, because cutting the wrong block
    silently destroys an unrelated narrative.

    **A DUPLICATED title refuses, where a DRIFTED one is merely skipped.** The
    docstring above warned about drift and this function guarded it; nothing
    guarded duplication, and the two fail in opposite directions. A drifted
    title matches nothing, so the worst case is a narrative left behind — a
    no-op. A duplicated title matched twice and this took the FIRST: one block
    was cut and archived while its twin was left in the active section with no
    index entry pointing at it, orphaned, in a file whose stated invariant is
    *never delete an entry here*. Scanning all matches and refusing on a second
    is the only answer that cannot silently destroy prose: which of two
    identically-titled blocks is the real one is not a question this function
    can answer, and guessing is how the entry is lost.

    The refusal names both line numbers because the resolution is the
    operator's — retitle one, or merge them. It is deliberately NOT a
    de-duplication: an automatic fix here would delete an entry to satisfy a
    check, in the one file that says never to.
    """
    matches = [
        i for i in range(min(limit, len(lines)))
        if lines[i].startswith("## ") and lines[i][3:].strip() == title
    ]
    if len(matches) > 1:
        where = ", ".join(str(i + 1) for i in matches)
        return "", (
            f"learnings-detail.md carries {len(matches)} active blocks titled "
            f"{title!r} (lines {where}). Retiring it would archive one and "
            "orphan the rest — they would keep their prose and lose the index "
            "entry that points at it, in a file whose invariant is that no "
            "entry is ever deleted. Retitle the duplicates or merge them by "
            "hand; this refuses rather than choosing one, because which block "
            "is the real one is not something it can know."
        )
    start = matches[0] if matches else None
    if start is None:
        return "", None
    end = start + 1
    while end < limit and not lines[end].startswith("## "):
        end += 1
    body = "\n".join(lines[start + 1 : end]).strip("\n")
    del lines[start:end]
    return body, None


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


#: The token a declared ``sentinel_command`` must carry, marking where the one
#: test file to grade belongs. Spelled to match ``test_command``'s established
#: ``{junit_xml}``, so a product that has declared its suite already knows the
#: convention rather than meeting a second one.
SENTINEL_PLACEHOLDER = "{sentinel}"


def resolve_sentinel_command(product_dir: Path) -> tuple[list[str] | None, str | None]:
    """The product's declared sentinel invocation as an argv template.

    Returns ``(argv, None)`` when ``sentinel_command:`` is declared and usable,
    or ``(None, reason)`` when it is absent or malformed. The reason is written
    for an operator, not a log: it names the knob and what to put in it.

    **There is deliberately no default.** An earlier version ran
    ``sys.executable -m pytest`` whenever nothing was declared, which made every
    non-Python product's sentinels both inert *and* permanently failing — and a
    false-failing sentinel is worse than an ungraded one, because the audit
    decides which learnings are structurally enforced, so it argues for retiring
    a rule that is still enforced. No default can be written here without
    assuming the governed product shares this runtime's language, which
    ``architecture.md`` § Direction forbids: prawduct states the requirement
    ("grade this sentinel") and the product declares how to meet it.
    """
    # Read through the SAME reader as `test_command:`, deliberately: the two
    # keys are documented side by side and the template tells authors they share
    # a `#`-truncation caveat. Read by two different column-0 parsers that merely
    # agree today, that promise is a coincidence rather than a property — and
    # this one scalar would also pull the advisory subsystem into the audit's
    # import DAG for nothing.
    from . import core  # noqa: PLC0415 — lazy; only this path reads state

    state_path = Path(product_dir) / ".prawduct" / "project-state.yaml"
    declared = core.read_str_yaml_key(state_path, "sentinel_command")
    declared = declared.strip() if isinstance(declared, str) else ""
    if not declared:
        # "absent OR unreadable": the reader fails soft to None on both, so
        # naming only absence would tell a product that HAS declared the key to
        # go and declare it — a confident diagnostic prescribing an edit already
        # made. Cheaper to widen the sentence than to split the read.
        return None, (
            "no readable `sentinel_command:` in .prawduct/project-state.yaml "
            "(absent, empty, or the file could not be read) — prawduct cannot "
            "know how this product runs one test file, and will not guess. "
            f"Declare it with a {SENTINEL_PLACEHOLDER} placeholder, e.g. "
            f"`sentinel_command: npx vitest run {SENTINEL_PLACEHOLDER}`"
        )
    if SENTINEL_PLACEHOLDER not in declared:
        return None, (
            f"`sentinel_command: {declared}` carries no {SENTINEL_PLACEHOLDER} "
            "placeholder, so it names no test file to grade — it would run the "
            "whole suite and report its verdict as this one rule's. Put "
            f"{SENTINEL_PLACEHOLDER} where the test path belongs"
        )
    try:
        argv = shlex.split(declared)
    except ValueError as exc:
        return None, f"`sentinel_command:` is not a parseable command line: {exc}"
    if not argv:
        return None, "`sentinel_command:` is empty once parsed"
    return argv, None


#: The optional companion to ``sentinel_command``: exit codes that mean "this
#: runner could not judge the rule", not "the rule's test failed".
UNGRADED_EXIT_CODES_KEY = "sentinel_ungraded_exit_codes"


def resolve_ungraded_exit_codes(
    product_dir: Path,
) -> tuple[frozenset[int], str | None]:
    """Exit codes the product declares as *could not run*.

    Returns ``(codes, None)`` — possibly empty — or ``(frozenset(), reason)``
    when the declaration exists and is unusable.

    **Why the product declares this and prawduct does not infer it.** A runner
    that starts and then dies on a broken environment — absent `node_modules`,
    an unbuilt workspace, a missing plugin — exits non-zero and is
    indistinguishable, from outside, from a test that ran and failed. The three
    options weighed on #720 were: sniff the output for a recognisable result
    block; let the product declare the code; or leave it and document the
    boundary. The first requires prawduct to learn each runner's output format,
    which `architecture.md` § Direction forbids by the same rule that gives
    `sentinel_command:` no default. The third leaves the false accusation
    standing. The second is language-agnostic, costs a product nothing until it
    wants the distinction, and puts the knowledge where it lives — pytest's
    internal-error 3, vitest's 1-for-no-tests, whatever this product's runner
    does. The boundary is documented either way, in this module's docstring and
    in the state template, because "document it" was never the alternative to
    fixing it.

    **A malformed declaration is ungraded, not ignored.** Silently dropping it
    would mean an operator who asked for the distinction, and typo'd, keeps
    getting the false accusation they were trying to stop — with the file
    reading as though they had fixed it. That is the same silence
    `_KNOWN_METADATA_KEYS` validation closes one layer up, and
    ``resolve_sentinel_command`` already takes this posture for a malformed
    command.

    **``0`` is refused.** A command that exited successfully returned a verdict;
    listing it here would render every passing sentinel ungraded and quietly
    disable the whole retirement route.
    """
    from . import core  # noqa: PLC0415 — lazy; only this path reads state

    state_path = Path(product_dir) / ".prawduct" / "project-state.yaml"
    declared = core.read_str_yaml_key(state_path, UNGRADED_EXIT_CODES_KEY)
    declared = declared.strip() if isinstance(declared, str) else ""
    if not declared:
        # Absent is the DEFAULT, not an error: every non-zero exit is a real
        # failure, which is what a runner that does not distinguish means.
        return frozenset(), None

    codes: set[int] = set()
    for token in declared.replace(",", " ").split():
        try:
            code = int(token)
        except ValueError:
            return frozenset(), (
                f"`{UNGRADED_EXIT_CODES_KEY}: {declared}` is not a list of exit "
                f"codes ({token!r} is not an integer) — sentinels are reported "
                "ungraded rather than graded against a declaration prawduct "
                "could not read. Write it as space- or comma-separated "
                f"integers, e.g. `{UNGRADED_EXIT_CODES_KEY}: 3, 4`"
            )
        if code == 0:
            return frozenset(), (
                f"`{UNGRADED_EXIT_CODES_KEY}` lists 0, which is the code a "
                "runner returns when the test PASSED. Honouring it would report "
                "every green sentinel as ungraded and disable the retirement "
                "route entirely. List only the codes this runner uses for "
                "\"could not run\""
            )
        codes.add(code)
    return frozenset(codes), None


def run_sentinel(
    product_dir: Path, sentinel: str, *, timeout: int = 120
) -> tuple[bool | None, str]:
    """Grade one sentinel by running the product's declared command against it.

    Returns ``(passed, detail)`` on a **three-valued** verdict, and the third
    value carries the point:

    * ``True``  — the command exited 0; the rule is structurally enforced.
    * ``False`` — the command ran and exited non-zero; a real failure.
    * ``None``  — prawduct could not grade it at all. **Not a failure**: no
      command is declared, the declaration is malformed, the sentinel's target
      file is gone, or the command could not be launched or never finished.

    The line between ``False`` and ``None`` is *did a runner return a verdict
    about this rule* — not *did prawduct manage to spawn something*. A deleted
    target is on the ``None`` side even though a runner would happily exit
    non-zero on it, because "the test is missing" and "the test failed" are
    different facts and only one of them is about the rule.

    **A broken environment is on the ungraded side WHEN THE PRODUCT SAYS SO.**
    A runner that starts and then dies — absent dependencies, an unbuilt
    workspace — exits non-zero and is indistinguishable from a real failure from
    outside. No language-agnostic signal separates them, and prawduct must not
    learn per-runner exit-code tables, so the product declares the codes:
    ``sentinel_ungraded_exit_codes:`` in ``project-state.yaml``, read by
    :func:`resolve_ungraded_exit_codes`. An exit code listed there grades
    ``None`` with the declaration named in ``detail``. Undeclared, every
    non-zero exit stays ``False`` — the right default for a runner that does not
    distinguish, and the pre-existing behaviour for every product.

    **One known limit remains, erring toward running the command.** The
    missing-target check fires only for a *path-shaped* sentinel (one carrying a
    separator): an opaque runner id such as ``com.acme.BarTest#testX`` is not
    resolvable here, and prawduct will not claim a file is gone when it cannot
    tell "gone" from "not a path". **A bare filename is on the wrong side of
    that line** — ``auth.test.js`` with no directory is indistinguishable from
    an opaque id, so a deleted one still reaches the runner and can come back
    ``False``, which is the pre-fix false accusation surviving in the one shape
    the separator rule cannot catch (``brookstalley/prawduct#720``).

    Collapsing that third case into ``False`` is the whole defect this shape
    exists to prevent — it accuses a green test and argues for retiring a live
    rule. Callers must branch on ``is True`` / ``is False`` / ``is None`` and
    never on truthiness, where ``None`` and ``False`` are indistinguishable.

    A timeout and a launch failure both grade ``None`` rather than ``False``:
    a command that never started, and one that never finished, each reported no
    verdict, and "we do not know" is the honest reading of both.

    ``detail`` is the command's trailing combined output (~20 lines) on a real
    verdict, and the operator-facing reason on ``None``.
    """
    argv_template, reason = resolve_sentinel_command(product_dir)
    if argv_template is None:
        return None, reason or "sentinel could not be graded"
    # Resolved BEFORE the run, not after it. A declaration prawduct cannot read
    # is a fault in the grading setup, and finding that out only once a verdict
    # is in hand means spending the subprocess to produce a number nobody can
    # interpret. Failing here reports the fault against every sentinel, which is
    # what an unreadable grading rule actually affects.
    ungraded_codes, codes_error = resolve_ungraded_exit_codes(product_dir)
    if codes_error is not None:
        return None, codes_error
    # A sentinel naming a file that is GONE has no verdict either. Runners
    # disagree about this — some exit non-zero on an uncollectable target, which
    # would render "deleted" as "failing" and accuse a test that no longer
    # exists of breaking. Checked here so the answer does not depend on which
    # runner the product declared. Path only: the `::node` suffix names a case
    # inside the file and only the file's existence is knowable without running
    # anything.
    #
    # ONLY for a sentinel that is unambiguously a path, which here means it
    # carries a separator. A runner's id need not be a filename at all — JUnit's
    # `com.acme.BarTest#testX` and Go's `./pkg -run X` are ids this cannot
    # resolve — and claiming "does not exist, update the learning" about one of
    # those is a confident diagnostic naming the wrong fault, the exact shape of
    # the unreadable-state-file defect fixed a few lines above. When the sentinel
    # is not path-shaped prawduct cannot tell "gone" from "opaque id", so it
    # declines to guess and lets the declared runner answer.
    path_part = sentinel.split("::", 1)[0].strip()
    looks_like_path = "/" in path_part or "\\" in path_part
    if looks_like_path and not (Path(product_dir) / path_part).exists():
        return None, (
            f"sentinel target {path_part!r} does not exist — ungraded rather "
            "than failed, because a test that is gone returned no verdict. "
            "Update the learning's `sentinel=` to the test's new home, or drop "
            "it if the rule is no longer enforced"
        )
    argv = [tok.replace(SENTINEL_PLACEHOLDER, sentinel) for tok in argv_template]
    try:
        result = subprocess.run(
            argv,
            cwd=str(product_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None, (
            f"sentinel command timed out after {timeout}s — ungraded rather than "
            "failed, because a command that never finished returned no verdict"
        )
    except (OSError, FileNotFoundError) as exc:
        return None, (
            f"could not launch {argv[0]!r}: {exc} — ungraded rather than failed, "
            "because a launch failure is an environment fault, not a test result"
        )

    combined = (result.stdout or "") + (result.stderr or "")
    tail = "\n".join(combined.splitlines()[-20:])
    if result.returncode in ungraded_codes:
        # The product declared this code as "the runner could not judge it".
        # The command's output rides along in the reason, because the operator
        # fixing a broken environment needs to see what it said — and it is a
        # prawduct diagnostic now, not a test result, so it belongs in the
        # ungraded slot rather than `output_excerpt`.
        detail = (
            f"sentinel command exited {result.returncode}, declared in "
            f"`{UNGRADED_EXIT_CODES_KEY}` as \"could not run\" — ungraded rather "
            "than failed, because a runner that could not judge the rule "
            "returned no verdict about it"
        )
        return None, f"{detail}\n{tail}" if tail else detail
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
        ``output_excerpt``/``unevaluated_reason`` are meaningful on the sentinel
        route and ``None``/``""`` on the other, and
        ``superseded_by``/``resolved_to`` the reverse.

        Every record also carries the retirement's **readiness, decided once**
        by :func:`retirement_readiness` and never re-derived by a consumer:
        ``ready`` (bool), ``readiness`` (``ready`` | ``blocked`` | ``ungraded``)
        and ``why`` (the route-appropriate one-line reason). Readiness is asked
        of a different field per route — ``passed`` for a sentinel,
        ``resolved_to`` for a supersession — so a consumer that picks one field
        and branches reports every resolvable supersession as blocked. Render
        these; do not recompute them. Additive under `api-contract.md`'s norm:
        three new keys, no key repurposed.

        ``passed`` is three-valued on the sentinel route and a reader must treat
        it that way: ``True`` enforced, ``False`` genuinely failing, ``None``
        **ungraded** — no command declared, or one that could not run.
        ``unevaluated_reason`` is set only for that last case and says why, so
        "not attempted" (the ``run_sentinels=False`` seam) stays distinguishable
        from "attempted, no verdict". An ungraded sentinel raises no ``errors``
        entry: there is nothing to accuse the test of.
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
        resolve to exactly one other heading; entries declaring both
        retirement keys; and entries carrying a well-formed metadata key that is
        not in :data:`_KNOWN_METADATA_KEYS` (a misspelled directive reads as
        live and does nothing). Every one of these RETAINS the entry — the audit fails
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

        # Validate the parsed keys against the roster BEFORE acting on any of
        # them. A well-formed key nobody reads is the silent half of this
        # schema: `sentinal=tests/x.py::test_y` parses, matches no branch below,
        # and leaves the entry classified "active, no lifecycle metadata" — the
        # exact same outcome as an entry with no comment at all, so the author
        # who wrote a lifecycle directive gets no signal that it does nothing.
        #
        # Reported and then IGNORED, never fatal: the entry still flows through
        # every branch below on whatever keys it does declare. An unknown key
        # cannot retire anything, so fail-closed is already the behavior; adding
        # a refusal on top would let a typo elsewhere in the comment block a
        # retirement whose own key is correct.
        unknown_keys = sorted(set(meta) - _KNOWN_METADATA_KEYS)
        if unknown_keys:
            named = ", ".join(f"`{k}=`" for k in unknown_keys)
            known = ", ".join(f"`{k}=`" for k in sorted(_KNOWN_METADATA_KEYS))
            errors.append({
                "title": entry.title,
                "error": (
                    f"unknown lifecycle metadata: {named}. The audit acts on "
                    f"{known} and nothing else, so this key does nothing while "
                    "reading as a live directive. Fix the spelling or drop it"
                ),
            })

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
        # Distinct from `sentinel_passed is None`, which has two causes: the
        # `run_sentinels=False` seam, and a sentinel prawduct genuinely could not
        # grade. Only the second has something to tell the operator, so only the
        # second sets this — a caller can then tell "not attempted" from "attempted,
        # no verdict" without inferring it from an empty excerpt.
        sentinel_unevaluated: str | None = None
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
            resolved, resolve_error = resolve_supersession_target(
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
                "unevaluated_reason": None,
                "superseded_by": superseded_by,
                "resolved_to": resolved,
                "applied": False,
            }
            record.update(retirement_readiness(record))
            if not record["ready"]:
                errors.append({"title": entry.title, "error": resolve_error})
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
                if sentinel_passed is None:
                    # The runner returns its reason in the excerpt slot; move it
                    # to its own field so `output_excerpt` keeps meaning "what
                    # the test printed" rather than sometimes meaning "why no
                    # test ran". A reader scanning excerpts for failure context
                    # would otherwise read a prawduct diagnostic as test output.
                    sentinel_unevaluated = sentinel_excerpt
                    sentinel_excerpt = ""
            retirement_record = {
                "title": entry.title,
                "reason": "sentinel",
                "superseded_by": None,
                "resolved_to": None,
                "sentinel": sentinel,
                "passed": sentinel_passed,
                "output_excerpt": sentinel_excerpt,
                "unevaluated_reason": sentinel_unevaluated,
                "applied": False,
            }
            retirement_record.update(retirement_readiness(retirement_record))
            if retirement_record["readiness"] == "blocked":
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
            elif retirement_record["ready"]:
                if apply:
                    retirement_record["applied"] = True
                    retired_with_notes.append((entry, _retirement_note(
                        retired_on=today, sentinel=sentinel
                    )))
                else:
                    retained_entries.append(entry)
                retirements.append(retirement_record)
            else:
                # No verdict, from either cause: the `run_sentinels=False` seam,
                # or a sentinel prawduct could not grade (`unevaluated_reason`
                # says which). Recorded as a candidate and RETAINED either way,
                # and deliberately with no `errors[]` entry — an ungraded
                # sentinel has nothing to accuse the test of, and the old
                # "fix the test or update the learning" line was pointing at
                # green tests in every non-Python product.
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

    applied = apply
    if apply and retired_with_notes:
        refusal = _apply_retirements(
            learnings_path, retained_entries, retired_with_notes, content,
        )
        if refusal:
            # Nothing was written, and EVERY field that says otherwise has to be
            # walked back — not just the top-level one. `applied` reports what
            # HAPPENED, not what was asked for, and a record claiming a
            # retirement that never moved is this scope's own defect one field
            # down: the renderer branches on the per-entry flag, so leaving it
            # true prints `retire[retired]` for entries still sitting in the
            # active file.
            #
            # `refusal` is already a `{"title", "error"}` pair — the shape every
            # other member of this list has and the shape the renderer reads; a
            # bare string here is a `TypeError` traceback across the CLI
            # boundary, which api-contract forbids by name. It is built where
            # the refusal happens so it names the entry that refused.
            # `title` names the ENTRY, as every sibling error in this list
            # does — the renderer prints `error: <title>: <message>`, and
            # naming the file there repeats what the message already says.
            errors.append(refusal)
            applied = False
            for record in retirements:
                record["applied"] = False

    return {
        "product_dir": str(product_dir),
        "applied": applied,
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
) -> "dict | None":
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

    detail_path = learnings_path.parent / DETAIL_FILENAME
    history_path = learnings_path.parent / HISTORY_FILENAME
    detail_content, history_content, error = _compose_retirement_files(
        detail_path, history_path, retired_with_notes
    )
    if error:
        # Refuse BEFORE the first write. Both files are still exactly as found,
        # which is the whole reason composition happens ahead of I/O here — a
        # retirement that half-happens is data loss in a corpus that must never
        # lose an entry.
        return error

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
    # THREE files now, and the direction argument is unchanged: write the
    # ARCHIVE first, then the file the entry is leaving, then the index. Every
    # partial failure lands on the duplicate side — the entry visible in two
    # places, which a re-run reconciles — never on the deletion side.
    history_path.write_text(history_content)
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


def _lift_legacy_historical_section(
    lines: list[str],
) -> list[str]:
    """Cut a legacy in-file historical section out of ``lines`` and return its
    ENTRY blocks. Mutates ``lines``. Returns ``[]`` when there is no section.

    Every corpus split before #350 keeps its archive inside
    ``learnings-detail.md``. Leaving it there while new retirements go to
    ``learnings-history.md`` would give a product two archives and a route out
    that routes nothing — the old sink keeps being read on every lookup, which
    is the entire cost the split exists to remove. So the first `--apply` after
    the split MOVES it, in the same composed-before-any-write pass as the
    retirement that triggered it.

    Only the section's entry blocks are lifted. Its header line and the blurb
    beneath it are boilerplate the history file supplies itself, and carrying
    them across would file a second header inside the first section — so
    everything above the section's first ``## `` heading is dropped, which is
    exactly the boilerplate and nothing an author wrote.

    A detail file with no historical section is the post-split steady state and
    returns ``[]`` without touching ``lines``.
    """
    start = _find_historical_section(lines)
    if start is None:
        return []
    # Only a TOP-level heading closes the section, matching the writer's own
    # scan: retired entries are `## ` and belong inside it.
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("# ") and not lines[i].startswith("## "):
            end = i
            break
    section = lines[start + 1 : end]
    del lines[start:end]
    first_entry = next(
        (i for i, line in enumerate(section) if line.startswith("## ")), None
    )
    if first_entry is None:
        return []
    return section[first_entry:]


def _compose_retirement_files(
    detail_path: Path,
    history_path: Path,
    retired_with_notes: list[tuple[LearningEntry, str]],
) -> tuple["str | None", "str | None", "dict | None"]:
    """The full new text of ``learnings-detail.md`` AND ``learnings-history.md``,
    or a refusal.

    Returns ``(detail_text, history_text, None)`` normally and
    ``(None, None, {"title", "error"})`` when a retiring entry's title is
    duplicated in the detail file's active section — see
    :func:`_take_active_narrative`. The pair is carried rather than a bare reason
    so the refusal stays attributed to the entry that produced it.

    Pure — writes nothing either way, and the refusal returns BEFORE any cut is
    composed, so a rejected run leaves all three files exactly as it found them
    rather than half-moved.

    **Retirement is still a MOVE, now across two files.** The entry's active
    narrative is cut out of the detail file and folded into its historical block
    in the history file. Without the cut the corpus grows a second block under
    the same heading and the *undecorated* one sorts first, so a lookup returns
    a retired rule as current with no successor — the hole-that-reads-as-a-
    forwarding-address this lifecycle exists to prevent, reintroduced one file
    over. Found by all three reviewers independently on the first bulk
    ``--apply`` (2026-08-01), which duplicated 17 headings.
    """
    if detail_path.is_file():
        detail_content = detail_path.read_text()
    else:
        detail_content = (
            "# Learnings — Full Detail\n\n"
            "Full context for the ACTIVE rules in `learnings.md`, under the same "
            "headings. Retired entries live in `learnings-history.md`.\n"
        )

    lines = detail_content.split("\n")

    # Lift any pre-split archive out FIRST, so the cuts below run against a file
    # that is entirely active — which is what makes the boundary bookkeeping
    # unnecessary from here on.
    legacy_blocks = _lift_legacy_historical_section(lines)

    # Cut each retiring entry's ACTIVE narrative out of the detail file before
    # composing its historical block, so the prose MOVES rather than being
    # duplicated.
    narratives: list[str] = []
    for entry, _note in retired_with_notes:
        narrative, error = _take_active_narrative(lines, entry.title, len(lines))
        if error:
            # Attributed to the entry that actually refused, not to the first
            # candidate. This loop runs over EVERY retiring entry and returns on
            # the first duplicate it meets, so with a bulk `--apply` the two are
            # different entries — and `errors[].title` is the field doctor
            # relays, so a mismatch prints one line naming two entries.
            return None, None, {"title": entry.title, "error": error}
        narratives.append(narrative)

    detail_text = "\n".join(lines)
    if not detail_text.endswith("\n"):
        detail_text += "\n"

    appended_blocks = "\n".join(
        _historical_block(entry, note, narrative).rstrip("\n") + "\n"
        for (entry, note), narrative in zip(retired_with_notes, narratives)
    )
    if legacy_blocks:
        lifted = "\n".join(legacy_blocks).strip("\n")
        appended_blocks = lifted + "\n\n" + appended_blocks

    return detail_text, _history_with_blocks(history_path, appended_blocks), None


def _history_with_blocks(history_path: Path, blocks: str) -> str:
    """``learnings-history.md`` with ``blocks`` appended inside its section.

    Seeded with a preamble and the historical section header when absent. The
    section header is kept — verbatim, ``## Historical (structurally
    enforced)`` — for continuity with the entries already filed under it and
    with every reference that names it; the file around it is what changed, not
    the section.

    Appends at the END OF THE SECTION rather than at EOF. Those are the same
    place only while the section is last, and this file's contract has always
    been "under the historical section": once any later top-level section
    exists, EOF-appending files every retirement under a heading it does not
    belong to, with the file reading as though it did.
    """
    if history_path.is_file():
        content = history_path.read_text()
    else:
        content = ""

    lines = content.split("\n") if content else []
    start = _find_historical_section(lines)
    if start is None:
        head = content.rstrip("\n")
        if not head:
            head = _HISTORY_FILE_PREAMBLE.rstrip("\n")
        return (
            head + "\n\n"
            + _HISTORICAL_SECTION_HEADER + "\n\n"
            + _HISTORICAL_SECTION_BLURB
            + "\n" + blocks
        )

    end = len(lines)
    for i in range(start + 1, len(lines)):
        # Only a TOP-level heading closes the section: retired entries are `## `
        # and every block written here belongs inside.
        if lines[i].startswith("# ") and not lines[i].startswith("## "):
            end = i
            break
    tail = "\n".join(lines[end:])
    head = "\n".join(lines[:end]).rstrip("\n")
    out = head + "\n\n" + blocks
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


# ---------------------------------------------------------------------------
# Pairing check: `learnings.md` and `learnings-detail.md` mirror each other.
# ---------------------------------------------------------------------------

def _active_titles(content: str) -> list[str]:
    """Level-2 headings above the historical section, in file order.

    Above the boundary only, in both files: an archived entry is deliberately
    absent from the active index, so counting it would report a missing
    counterpart for every correctly retired entry.
    """
    lines = content.split("\n")
    boundary = _find_historical_section(lines)
    limit = boundary if boundary is not None else len(lines)
    return [
        lines[i][3:].strip()
        for i in range(min(limit, len(lines)))
        if lines[i].startswith("## ")
    ]


def check_learnings_pairing(product_dir: str | Path) -> dict:
    """Grade `learnings.md` against `learnings-detail.md`.

    **What is GRADED: duplicate active headings within either file.** That is
    the dimension with teeth. A duplicated title is what
    :func:`_take_active_narrative` refuses on, because a retirement would
    archive one block and orphan its twin — prose kept, index entry lost, in a
    file whose stated invariant is that no entry is ever deleted. The check and
    the refusal guard one defect at two times: this one before a retirement is
    attempted, the refusal at the moment it is.

    **What is MEASURED but not graded: counterparts and relative order.** #717
    asked for these as findings on the stated invariant that the two files
    "mirror each other's headings in the same order". Measured against this
    repo's own corpus before building to it, that invariant does not hold and
    was never held: 270 active index entries against 179 active detail entries,
    and the detail headings are a truncated PREFIX of the index heading rather
    than an exact copy. Grading it would have emitted ~117 findings on a
    corpus nobody considers broken — the misfiring probe `docs/norms.md` names
    by its cost, which is that it trains its reader to ignore the one real
    catch. So the counts ride the result for an operator who wants to work the
    drift down, and no finding is raised on them.

    That is a deliberate, recorded narrowing of the issue's ask, not a silent
    drop: the pairing dimension needs a decision about what the convention
    actually IS before anything can grade conformance to it.

    Reports; never repairs. Every repair here edits an authored corpus that must
    never lose an entry — de-duplicating picks a survivor, reordering rewrites
    prose positions, synthesising a counterpart invents narrative. All three are
    the operator's call, and an agent making them to satisfy a check is the
    silent mutation this plan exists to close.

    Returns ``{"status", "reason", "findings", "counts", "index_path",
    "detail_path"}``. ``status`` is ``ok`` | ``findings`` | ``unchecked`` — the
    third when a file could not be read, reported as ungraded and never as
    clean, because a check that could not run is otherwise indistinguishable
    from one that ran and found nothing.
    """
    prawduct_dir = Path(product_dir) / ".prawduct"
    index_path = prawduct_dir / "learnings.md"
    detail_path = prawduct_dir / "learnings-detail.md"
    base = {
        "index_path": str(index_path),
        "detail_path": str(detail_path),
        "findings": [],
        "counts": {},
    }

    if not index_path.is_file():
        # Deliberately `ok`, not `unchecked`. A missing `learnings.md` is doctor
        # Check #5's finding (core state present), and Check #13 in the same
        # file already rules that way for the same absence. Two checks reporting
        # one absence differently is how an operator learns to trust neither.
        # `unchecked` is reserved for a file that EXISTS and could not be read.
        return {**base, "status": "ok",
                "reason": f"no learnings.md at {index_path} — nothing to pair"}
    if not detail_path.is_file():
        # An unsplit corpus is an ordinary state, not drift between two files.
        return {**base, "status": "ok",
                "reason": "no learnings-detail.md — the corpus is not split"}
    try:
        index_titles = _active_titles(index_path.read_text(encoding="utf-8"))
        detail_titles = _active_titles(detail_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        return {**base, "status": "unchecked",
                "reason": f"could not read the pair ({exc.__class__.__name__})"}

    findings: list[dict] = []
    for label, titles in (("learnings.md", index_titles),
                          ("learnings-detail.md", detail_titles)):
        counts: dict[str, int] = {}
        for title in titles:
            counts[title] = counts.get(title, 0) + 1
        for title, n in sorted(counts.items()):
            if n > 1:
                findings.append({
                    "kind": "duplicate-heading",
                    "file": label,
                    "title": title,
                    "detail": (
                        f"{label} carries {n} active blocks titled {title!r}. A "
                        "retirement archives one and orphans the rest — prose "
                        "kept, index entry lost, in a file whose invariant is "
                        "that no entry is ever deleted. Retitle or merge them "
                        "by hand; this will not choose for you."
                    ),
                })

    # Prefix, not equality: a detail heading is the opening clause of its index
    # entry. Measured, never graded — see the docstring.
    def _index_position(detail_title: str) -> "int | None":
        for pos, title in enumerate(index_titles):
            if title.startswith(detail_title):
                return pos
        return None

    def _paired(detail_title: str) -> bool:
        return _index_position(detail_title) is not None

    # Order, actually measured rather than merely claimed. The prose said
    # "relative order" was measured while `counts` carried no ordering metric at
    # all — a record asserting a measurement nobody took, which is the shape
    # this scope exists to close, committed in its own description.
    positions = [
        p for p in (_index_position(d) for d in detail_titles) if p is not None
    ]
    out_of_order = sum(
        1 for a, b in zip(positions, positions[1:]) if b < a
    )

    return {
        **base,
        "status": "findings" if findings else "ok",
        "findings": findings,
        "counts": {
            "index_active": len(index_titles),
            "detail_active": len(detail_titles),
            "detail_without_index_prefix_match": sum(
                1 for d in detail_titles if not _paired(d)
            ),
            "paired_entries_out_of_order": out_of_order,
        },
        "reason": (
            f"{len(findings)} duplicate-heading finding(s)" if findings
            else f"no duplicate headings ({len(index_titles)} index, "
                 f"{len(detail_titles)} detail active entries)"
        ),
    }
