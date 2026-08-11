"""Post-sync advisory probes for the norm-lifecycle feature (``docs/norms.md``).

Five deterministic ``ProbeFn(state, codebase)`` probes surfacing the *time-domain,
cheap* enforcement row of ``docs/norms.md`` § Enforcement — the Session-sync
contract. Each reads only **machine-readable hooks** (dated ``revisit:`` values,
backlog-item citations on norm ``Why:``/``Status:`` lines, the ``Status:
in-transition`` token, structural presence/absence of ``## Direction`` sections,
strategy-class artifacts, and the Enforcement index table's norm columns) —
never prose interpretation. Each yields at most
**one** :class:`~lib.advisory_store.AdvisoryCandidate` with *count-independent*
evidence, so the advisory id is one stable nudge (no churn as the firing set
changes; the live list lives in ``trigger_summary``). Rare-and-high-signal is a
hard bar: when a signal is missing or ambiguous, the probe fails toward silence.

Probes are read-only. Resolution is a *fact* the consumer records — a committed
answer-store scalar (``norm_registry_ratified``, ``norm_health_last_run``) or a
committed change to the norms themselves (a ``## Direction`` section appearing, a
backlog item's status flipping) — so a teammate's commit clears the advisory for
everyone on next sync. Nag/dismissal state stays in the gitignored advisory store
(the shared-answer / personal-nag split learning).

Registration is wired at the runtime composition root (``bin/prawduct-hook``),
not at ``advisory_store`` import time, so the infrastructure stays
feature-agnostic — the same pattern as ``lib/backlog_probes.py`` and
``lib/api_versioning_probes.py``. Call :func:`register` once before the roster
runs.

Design note — per-probe lock-in (fires / clears / reader-action)
----------------------------------------------------------------

- **revisit-due** — *Fires:* an open (non-closed) backlog item's metadata bar
  carries ``revisit: YYYY-MM-DD`` with a date strictly before today. Non-date
  ``revisit:`` values (event triggers) are IGNORED — those are the janitor Norm
  Health sweep's job. *Clears:* the item is closed (``status: shipped|dropped``
  or moved to Archive), or its ``revisit:`` is renewed to a future date /
  removed. *Reader-action:* the summary names each past-due item so the reader
  can renew the exception (fresh ``revisit:`` + reason) or schedule its removal.
  **Markdown-backend only**, and unlike its two siblings that is not dormancy the
  cache can end — see the function.

**Two of the five read the LIVE backlog, and which backlog depends on the product.**
``dead-why`` and ``stalled-transition`` both need to know whether a cited item is
live and when it last moved. Pre-cutover they read ``.prawduct/backlog.md``;
post-cutover they resolve through the backlog cache, which holds the live store
and resolves aliases, so a norm citing a pre-migration ``PFX`` id still finds the
issue that carries it. A store that cannot answer raises one shared advisory
rather than silence — the distinction between *ran and found nothing* and *could
not look* is the whole reason these two were made to announce themselves.

- **dead-why** — *Fires:* a ``## Direction`` entry's ``Why:`` line, or a
  ``Status:`` line **still reading ``in-transition``**, in a
  ``.prawduct/artifacts/*.md`` artifact cites a backlog item that is
  shipped/dropped/archived (decay — the norm's rationale rests on
  completed/abandoned work). A *settled* ``Status:`` line naming the item that
  completed the transition is excluded, and :func:`_in_flight_status` records
  why. *Clears:* the norm is retired/amended (the id
  removed from the why) or the cited item returns to live. *Reader-action:* the
  summary names each ``artifact→id`` pair so the reader can re-affirm-and-cleanup
  or retire the norm.

- **stalled-transition** — *Fires:* a ``## Direction`` entry contains the literal
  ``Status: in-transition`` and its tracking backlog item (the id on that Status
  line) is still live but unchanged for more than :data:`STALL_WINDOW_DAYS`.
  "Unchanged" is the provider's ``updated_at`` post-cutover and the item's own
  metadata-bar dates before it (see :func:`_item_floor_date`); no git shell-out
  (no existing probe shells to git, and a probe must stay cheap). No date signal
  on the item ⇒ no fire (fail toward
  silence). A *dead* tracking item is dead-why's job, not this one. *Clears:* the
  tracking item is touched, the
  transition completes (Status leaves ``in-transition``), or a stopgap is
  recorded. *Reader-action:* the summary names each ``artifact→id`` and its
  staleness so the reader can accelerate the migration or record a stopgap.

- **norm-registry-unratified** — *Fires:* one-shot post-upgrade — a strategy-class
  artifact exists (:data:`STRATEGY_CLASS_ARTIFACTS`) AND the registry is
  unratified on either arm: (a) no ``## Direction`` **entry** exists in ANY
  ``.prawduct/artifacts/*.md`` (the heading alone is not one), or (b) the
  preferences Enforcement index table
  lacks the norm columns (:data:`_NORM_INDEX_COLUMNS` — ratification began but
  the index cannot carry it). Both arms are gated on a strategy-class artifact
  existing (``docs/norms.md`` § Adoption scopes the advisory so): a product with
  no architectural-direction artifacts has nothing to ratify, and nagging it
  would break the rare-and-high-signal bar. *Clears:* the ``/prawduct:doctor``
  ratification flow resolving both arms (Direction sections written / table
  extended) OR the shared-state answer :data:`RATIFIED_FACT` is recorded (a
  valid "no norms to ratify" outcome — one teammate's answer clears it for
  everyone). *Reader-action:* points at the ``/prawduct:doctor`` ratification
  flow. The evidence string is arm-independent so the advisory id stays stable
  as the firing arm changes; the live arm(s) are named in ``trigger_summary``.

- **norm-health-sweep-overdue** — *Fires:* norms exist under either homing
  (``## Direction`` entries or populated preferences Enforcement rows) AND
  neither the janitor Norm Health sweep stamp :data:`SWEEP_STAMP` nor the
  ratification date (:data:`RATIFIED_FACT`'s leading date) falls within
  :data:`SWEEP_WINDOW_DAYS`. The stamp is a committed top-level project-state
  scalar the sweep writes (the janitor theme lands the *write* side; this probe
  is read-only, mirroring how ``backlog-overdue-grooming`` reads
  ``backlog_last_groomed_at``). Ratifying the registry is itself a deep pass over
  every norm, so it seeds the baseline the same as a sweep — otherwise this nudge
  would trip the same day ratification clears ``norm-registry-unratified``.
  *Clears:* running the sweep (which stamps a fresh date), or a fresh
  ratification. *Reader-action:* points at ``/prawduct:janitor`` (Norm Health).
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path

from .advisory_store import AdvisoryCandidate, Codebase, ProjectState, register_probe
from .backlog.encode import parse_iso as encode_parse_iso
from .backlog.legacy import BacklogItem, parse_backlog
from .backlog_probes import post_cutover

# Strategy-class artifact filenames (docs/norms.md § Where Norms Live). Presence of
# any is the heuristic for "this product has architectural direction that may carry
# norms" — the trigger half of the one-shot unratified nudge. Imported from
# coverage_probes, which owns the coverage expectation table this set is the union
# of, rather than transcribed — one home for the list (the structural-coverage
# plan's Module Boundaries; transcription across surfaces flattens quantifiers).
from .coverage_probes import STRATEGY_CLASS_ARTIFACTS

FEATURE = "norm-lifecycle"
PROBE_VERSION = 1

# Stall window (docs/norms.md § Transitions). WHY 30: a declared-substrate
# migration whose tracking item's backlog entry hasn't moved in a month is not
# progressing — that is a forcing event (accelerate or record a stopgap), not
# noise. The spec calls this "default 30 days, configurable"; no config surface
# exists yet, so it is a module constant (the backlog probes' thresholds do the
# same) — wire a config read here when one lands, don't relax the default.
STALL_WINDOW_DAYS = 30

# Norm Health sweep window (docs/norms.md § Trajectory). WHY 60: erosion/decay
# are slow trends measured by a *deep* periodic sweep, not a per-session concern;
# 60 days keeps the sweep current enough to catch drift while staying well clear
# of nagging a repo whose norms are healthy and recently swept.
SWEEP_WINDOW_DAYS = 60

# The norm columns the preferences Enforcement index table gains at ratification
# (templates/project-preferences.md). Exact cell text — these are machine-readable
# markers, not prose; missing either one means the table predates the norm index.
_NORM_INDEX_COLUMNS = ("Audit home", "Why")

# Shared-state answer that clears norm-registry-unratified (mirrors
# api_versioning_probes.RESOLUTION_FACT). Truthy — including a recorded "none —
# no norms to ratify" — suppresses for everyone on next sync. Top-level scalar:
# load_project_state reads only column-0 keys.
RATIFIED_FACT = "norm_registry_ratified"

# Committed stamp the janitor Norm Health sweep writes (the write side lands with
# the janitor theme); this probe only READS it, exactly as backlog-overdue-grooming
# reads backlog_last_groomed_at. Top-level scalar, ``YYYY-MM-DD``.
SWEEP_STAMP = "norm_health_last_run"

# A backlog-id literal (docs/norms.md Session-sync row). 2–4 upper letters + ``-``
# + 4 base36 chars — deliberately a shade broader than the canonical 2–3-letter
# prefix; a false id-shape (e.g. ``ISO-8601``) is harmless because it only fires
# after resolving to a REAL archived/live backlog item, which no incidental token
# does.
_BACKLOG_ID_RE = re.compile(r"\b[A-Z]{2,4}-[A-Z0-9]{4}\b")

# The other spelling a norm cites an item by, once the backlog lives on an issue
# tracker: `#621`, or `owner/repo#621` when the norm names a repo other than the
# one it lives in. Both are ordinary prose in this codebase's own Direction
# sections, and neither matches the PFX shape above — a probe reading only PFX
# ids post-cutover would scan every artifact and find nothing to resolve, which
# looks exactly like a clean bill of health.
#
# False shapes are as harmless here as they are above and for the same reason:
# an extracted token only produces a finding after resolving to a REAL item, and
# a bare `#4` in prose resolves to nothing (or to a real item, in which case the
# citation was real). The owner/repo prefix is optional and non-capturing so both
# spellings come back verbatim for the resolver to normalize.
_ISSUE_REF_RE = re.compile(r"(?<![\w#])(?:[\w.-]+/[\w.-]+)?#\d+\b")

# A markdown heading line: capture level and text so a ``## Direction`` heading is
# distinguishable from prose that merely mentions ``## Direction`` in a code span.
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")

# A physical line that STARTS a new logical unit inside a Direction section: a
# list item (``- `` / ``* ``) or a capitalized ``Field:`` label (``Why:``,
# ``Status:``, ``Retroactivity:``, ``Rulings:``). Anything else non-blank is a
# markdown soft-wrap continuation of the previous logical line.
#
# The label may carry markdown emphasis (``**Why:**``, ``_Why:_``). Without
# that, an emphasised marker is not a line start, so it soft-wraps onto the
# bullet above and :data:`_WHY_RE` — anchored at ``^`` — can never see it. The
# two must widen together or widening either alone accomplishes nothing.
# ``**Statement.**`` is unaffected: the label alternative needs a single word
# followed immediately by a colon, and a bold statement has neither.
_FIELD_OR_ITEM_RE = re.compile(r"^\s*(?:[-*]\s|(?:\*{1,2}|_{1,2})?[A-Z][A-Za-z-]*:)")

# A leading markdown blockquote prefix: one or more `>` (nesting is ordinary
# markdown), each optionally followed by a space, at the head of a line.
#
# Stripped in `_direction_lines` rather than tolerated in each matcher, because
# EVERY field matcher below anchors at `^\s*` and `>` is not whitespace — so a
# product writing `> **Why:** ...` lost entry detection, the ratification
# signal, dead-why and stalled-transition together. Widening the four regexes
# instead would put the same concession in four places for the next edit to
# desynchronize (`_STATUS_RE`'s prefix/closer split is exactly that failure,
# one field over), and would leave the soft-wrap joiner still folding a `>`
# into the middle of the prose the citation scans read.
#
# One strip point also keeps `_FIELD_MARKER_RE` byte-identical for
# `record_lint._norm_field_re`, which imports it. That is NOT sufficient on its
# own and the first cut of this comment wrongly said it was: record_lint walks
# raw text rather than `_direction_lines`, so an identical regex answered
# differently on identical input until it imported this prefix too. Sharing the
# matcher shares syntax; sharing the matcher AND the reader that feeds it is
# what shares the definition.
_BLOCKQUOTE_PREFIX_RE = re.compile(r"^\s*(?:>\s?)+")

# Norm-entry field markers (docs/norms.md § Anatomy). Case-sensitive to the
# canonical capitalization — these are machine-readable markers, not prose —
# but tolerant of markdown emphasis around them.
#
# Emphasis tolerance is an owner decision (2026-08-03), not a convenience: since
# the `Why:` marker began deciding whether a norm registry EXISTS (not merely
# whether an entry has decayed), a product writing ``**Why:**`` lost the
# ratification signal, the Norm Health sweep reminder, dead-why and
# stalled-transition — four signals, silently, for a formatting choice the spec
# never forbade. `docs/norms.md` § Anatomy still shows the bare form as
# canonical; this reads what authors write.
_EMPH = r"(?:\*{1,2}|_{1,2})?"
_WHY_RE = re.compile(rf"^\s*{_EMPH}Why:")

# What makes a bullet a NORM ENTRY rather than a list item: it carries one of
# the anatomy's fields. Deliberately NOT `Why:` alone, though `Why` is the
# required field — because doctor Health Check #10 exists to report "every
# Direction entry carries a Why", and a Why-only definition makes that check
# vacuous: the whyless entries it is meant to flag would stop being entries.
# The roadmap case #567 is about is still excluded, since a prioritised list of
# undone work carries no fields at all.
_NORM_FIELDS = ("Why", "Status", "Rulings", "Retroactivity")
_FIELD_MARKER_RE = re.compile(
    rf"^\s*{_EMPH}(?:{'|'.join(_NORM_FIELDS)}):"
)
_STATUS_RE = re.compile(rf"^\s*{_EMPH}Status:")
# The closer must mirror the PREFIX. An earlier cut accepted `_{1,2}` before
# `Status:` but only `*` after it, so `__Status:__ in-transition` counted as
# a norm entry and was scanned by dead-why while stalled-transition could
# never see it — #569's own defect surviving #569's fix, one field over.
# Emphasis can sit on either side of the colon AND around the value:
# `**Status:** in-transition`, `Status: **in-transition**`. An earlier cut
# allowed it only immediately after the colon, so `Status: **in-transition**`
# was entry-visible and stall-invisible — the same defect as the `__Status:__`
# case one position over, which is why this is written as "optional emphasis
# anywhere between the marker and the token" rather than patched per-form.
_IN_TRANSITION_RE = re.compile(rf"Status:{_EMPH}\s*{_EMPH}in-transition")

# A bare ISO date, matched in full — a partial/free-text ``revisit:`` trigger must
# NOT parse as a date (it belongs to the janitor sweep, not this probe).
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# A date at the START of a string, ignoring any trailing text. The
# ``norm_registry_ratified`` fact leads with the ratification date (the doctor
# flow's contract) but is commonly embellished ("2026-07-17 — 20 norms…"), so its
# baseline date needs leading-match, not the strict full-match above.
_LEADING_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")

# Terminal backlog statuses — an item in one of these (or under an Archive
# heading) is "dead" for decay purposes.
_TERMINAL_STATUSES = ("shipped", "dropped")


# =============================================================================
# Shared read helpers (read-only, non-raising — the probe convention)
# =============================================================================


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _backlog_path(codebase: Codebase) -> Path:
    return codebase.root / ".prawduct" / "backlog.md"


def _artifact_paths(codebase: Codebase) -> list[Path]:
    """The product's generated artifacts (``.prawduct/artifacts/*.md``), sorted.

    Sorted so a probe's summary of ``artifact→id`` pairs is deterministic. A
    missing directory yields ``[]`` (``glob`` on an absent dir is empty, no raise).
    """
    artifacts = codebase.root / ".prawduct" / "artifacts"
    try:
        return sorted(p for p in artifacts.glob("*.md") if p.is_file())
    except OSError:
        return []


def _backlog_index(codebase: Codebase) -> dict[str, BacklogItem]:
    """Map ``item_id`` → item for the consumer's backlog (id-less items skipped)."""
    text = _read_text(_backlog_path(codebase))
    if not text:
        return {}
    return {i.item_id: i for i in parse_backlog(text).items if i.item_id}


def _parse_date(value) -> date | None:
    """Parse a full ``YYYY-MM-DD`` string to a date, else ``None``.

    Strict full-match: a free-text ``revisit:`` trigger ("when export ships") does
    not parse, so the dated and event-bound expiry paths stay honestly split
    (docs/norms.md § Exceptions expire)."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not _DATE_RE.match(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _leading_date(value) -> date | None:
    """Parse a date at the START of a string (trailing text ignored), else ``None``.

    For the ``norm_registry_ratified`` fact, whose contract leads with the
    ratification date but often carries a descriptive suffix. A dateless answer
    ("none — no norms to ratify") returns ``None``, which simply contributes no
    baseline date — the sweep probe then falls back to :data:`SWEEP_STAMP`
    alone. (An earlier version of this note claimed such an answer meant no
    ``## Direction`` sections existed and that the caller never reached here.
    It does reach here: the answer is a recorded human judgement, not a
    structural fact, and since the sweep guard now also admits norms homed in
    the preferences Enforcement index, the two can disagree outright.)"""
    if not isinstance(value, str):
        return None
    match = _LEADING_DATE_RE.match(value.strip())
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def _is_dead(item: BacklogItem) -> bool:
    """True when a backlog item is shipped/dropped or lives under an Archive heading."""
    if (item.status or "").lower() in _TERMINAL_STATUSES:
        return True
    return "archive" in item.section.lower()


def _item_floor_date(item: BacklogItem) -> date | None:
    """Best available "last touched" floor for an item: the later of its
    ``reviewed:`` and ``added:`` metadata dates, or ``None`` if neither parses.

    This is the deterministic, cheap stall signal (chosen over a git shell-out —
    no existing probe shells to git, and a probe must not). It is a *floor*, not
    the true last-edit time: a body edit that doesn't touch ``reviewed:`` won't
    advance it, so the probe under-fires rather than over-fires — the right bias
    for the rare-and-high-signal bar. ``/prawduct:backlog update`` stamps
    ``reviewed:`` on every touch, so a genuinely-tended item advances its floor."""
    candidates = [
        d
        for d in (_parse_date(item.metadata.get("reviewed")), _parse_date(item.metadata.get("added")))
        if d is not None
    ]
    return max(candidates) if candidates else None


def _label(item: BacklogItem) -> str:
    """A short, stable handle for an item in a summary line."""
    if item.item_id:
        return item.item_id
    title = (item.title or "").strip()
    return (title[:40] or "(untitled)")


def _direction_lines(text: str) -> list[str]:
    """Every LOGICAL line inside a ``## Direction`` section (heading lines excluded).

    A section opens at a heading whose text is exactly ``Direction`` (any level)
    and closes at the next heading of equal-or-higher level. Heading lines are
    never yielded, so a ``Why:``/``Status:`` scan sees only entry content. Prose
    that mentions ``## Direction`` inside a paragraph or code span is not a
    heading and never opens a section.

    Physical lines that don't start a new logical unit (:data:`_FIELD_OR_ITEM_RE`)
    and don't follow a blank line are markdown soft-wrap continuations, joined
    onto the previous logical line — the spec's own Anatomy example wraps its
    ``Why:`` across physical lines, and a backlog id cited after the wrap point
    must still be seen by the mechanical scans (dead-why, stalled-transition).
    A paragraph after a blank line stands alone: detached descriptive
    surroundings never merge into a field line.

    Leading blockquote markers are stripped (:data:`_BLOCKQUOTE_PREFIX_RE`)
    before any of that, so `> **Why:** ...` behaves exactly as the unquoted form
    does — as a line start for the soft-wrap rule and as a field marker
    downstream. A line that is only a marker (`>`) becomes blank, which is the
    correct reading: an empty quoted line separates logical units just as an
    empty plain one does.

    **The strip runs before HEADING detection too, so `> ## Direction` opens a
    section and a quoted sibling heading closes one.** That is deliberate and
    wider than the field lines the change was aimed at: a heading inside a
    blockquote is still a heading of the quoted document, and stripping for
    fields but not for headings would leave a wholly-quoted artifact with field
    lines belonging to no section — a silent zero rather than a visible error.
    Both directions are pinned by ``TestBlockquotedHeadingsOpenASection``,
    because a strip applied when opening but not when closing would swallow the
    rest of the document."""
    out: list[str] = []
    in_section = False
    section_level = 0
    for raw in text.splitlines():
        line = _BLOCKQUOTE_PREFIX_RE.sub("", raw)
        heading = _HEADING_RE.match(line)
        if heading:
            level = len(heading.group(1))
            if heading.group(2).strip() == "Direction":
                in_section, section_level = True, level
            elif in_section and level <= section_level:
                in_section = False
            continue  # never treat a heading line itself as entry content
        if not in_section:
            continue
        if line.strip() and not _FIELD_OR_ITEM_RE.match(line) and out and out[-1].strip():
            out[-1] = out[-1].rstrip() + " " + line.strip()
        else:
            out.append(line)
    return out


def _has_direction_entry(text: str) -> bool:
    """True if the text carries a real ``## Direction`` **entry**, not just the heading.

    The heading alone is not evidence of a norm registry. An entry is a bullet
    carrying one of the anatomy's **fields** (:data:`_NORM_FIELDS`) — that is
    what separates a norm from a roadmap item, whose bullets carry none.

    Field-bearing rather than ``Why``-bearing, although ``docs/norms.md``
    § Anatomy makes ``Why`` the *required* field: doctor Health Check #10
    exists to report "every Direction entry carries a Why", and a Why-only
    definition makes that check vacuous, since the whyless entries it is meant
    to flag would stop being entries at all. Requiredness is a property the
    checks assert ABOUT entries, not the test for whether something IS one.

    Matching on the heading alone meant a section **empty of the thing being
    checked did not fail the check, it passed it silently** — the same shape as
    an unfilled template counting as a present artifact. Observed in the wild:
    a repo whose only ``## Direction`` section was a prioritized list of undone
    work certified as a ratified registry.

    :func:`_direction_lines` already yields exactly the right lines — heading
    lines excluded, soft-wraps joined — so this needs no parsing of its own.
    """
    return any(_FIELD_MARKER_RE.match(line) for line in _direction_lines(text))


def _any_direction_entry(codebase: Codebase) -> bool:
    """True if ANY generated artifact carries a ``## Direction`` norm entry."""
    return any(_has_direction_entry(_read_text(p)) for p in _artifact_paths(codebase))


def _extract_ids(line: str) -> list[str]:
    """Every backlog-item citation on ``line``, in both spellings, de-duplicated.

    Order is PFX-first then issue-refs, and stable within each — the summaries
    these feed are sorted anyway, so the ordering matters only for determinism.
    """
    seen: list[str] = []
    for found in (_BACKLOG_ID_RE.findall(line), _ISSUE_REF_RE.findall(line)):
        for token in found:
            if token not in seen:
                seen.append(token)
    return seen


# =============================================================================
# The cache-backed half: resolving citations once the backlog is on a service
# =============================================================================

#: The advisory raised when the backlog cache cannot answer. **One type and one
#: evidence string, shared by both probes that read it**, because
#: ``advisory_store.compute_id`` hashes ``(feature, type, version, evidence)`` —
#: so two probes reporting the same outage mint the same id and the store keeps
#: one nag. Two spellings would mean two advisories for one cause, which is the
#: pattern that trains dismissal and makes the next real signal invisible.
_CACHE_UNAVAILABLE_TYPE = "backlog-cache-unreadable"
_CACHE_UNAVAILABLE_EVIDENCE = (
    "the backlog cache could not be read, so norm citations cannot be resolved to items",
)


class _CacheUnanswerable(Exception):
    """A resolution that could not be attempted, carrying the store's own verdict.

    Raised rather than returned so a probe's scan loop stays a scan loop. It never
    leaves this module: :func:`_cache_advisory` turns it into the one advisory
    above. **Reporting it is the point** — a probe that swallowed it and returned
    ``[]`` would be indistinguishable from a probe that ran and found nothing,
    which is the exact silence these checks were made to announce.

    It carries the error ``code`` as well as the message because the two failures
    it covers send a reader to different places: an unreadable or never-synced
    store is repaired by a sync, while an ``alias_collision`` means the store was
    read perfectly well and what it holds is the problem — telling that reader to
    sync would send them to re-fetch a faithful mirror of a broken backlog.
    """

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


def _cache_advisory(exc: "_CacheUnanswerable", scope: str) -> list[AdvisoryCandidate]:
    """The one advisory both probes raise, with both repairs named.

    **Both routes are named unconditionally rather than one being chosen from the
    error code**, which is the opposite of what it should be and is deliberate.
    The id is hashed over the constant evidence above so two probes failing in one
    run collapse to a single nag — but ``reconcile`` builds its candidate map
    last-write-wins, so a *varying* remedy would mean the surviving advisory
    carried whichever probe happened to register later. That is reachable:
    ``dead-why`` resolves a strict superset of the citations ``stalled-transition``
    does, so a collision on a ``Why:``-only citation is invisible to the other
    probe and the two fail for different reasons in the same run. A remedy that
    silently depends on registration order is worse than one that names both.

    The scope is interpolated because this is the advisory a fresh clone of any
    post-cutover product meets at every session start until a sync runs, so it is
    the first line an operator copy-pastes — and a literal ``<placeholder>`` in
    that position is a command that does not run.
    """
    return [
        AdvisoryCandidate(
            type=_CACHE_UNAVAILABLE_TYPE,
            evidence=_CACHE_UNAVAILABLE_EVIDENCE,
            trigger_summary=(
                f"Norm decay checks could not run: {exc.reason}. They are reporting "
                "nothing because they could not look, not because there is nothing "
                "to find. If the store is missing or behind, sync it; if it reports "
                "an alias collision, the repair is on the items, not on the store."
            ),
            recommended_action=f"prawduct-hook backlog sync --repo {scope}   (or /prawduct:backlog for an alias collision)",
            priority="info",
        )
    ]


def _resolve_citation(codebase: Codebase, scope: str, cited: str) -> dict | None:
    """Resolve one cited id against the backlog cache, or ``None`` if it names
    nothing this store holds.

    Raises :class:`_CacheUnanswerable` when the store could not answer — which is
    a different fact from "no such item" and must not read alike. An unresolvable
    citation is a *successful* answer here, and one this probe deliberately does
    nothing with: a norm citing an id no backlog holds is the doctor's
    registry-integrity check, not a decay signal.
    """
    from .backlog import cachequery  # noqa: PLC0415 — lazy: only the post-cutover arm

    default_owner = scope.split("/", 1)[0] if "/" in scope else None
    result = cachequery.resolve(
        codebase.root,
        scope=scope,
        id_raw=cited,
        now=datetime.now(timezone.utc),
        default_owner=default_owner,
    )
    if result.get("status") != "ok":
        err = result.get("error") or {}
        raise _CacheUnanswerable(err.get("code") or "unavailable", err.get("message") or "unknown reason")
    data = result["data"]
    return data if data.get("resolved") else None


def _in_flight_status(line: str) -> bool:
    """Is this a ``Status:`` line whose transition is still running?

    **A settled status line is not decay, and this is the distinction the check
    was missing.** ``Status:`` carries two very different sentences. An
    in-transition one cites the item *tracking* the migration, so that item
    going dead while the status still says in-transition is genuine decay — the
    work stopped and the norm never noticed. A ``steady-state`` one commonly
    cites the item that *completed* the transition ("steady-state as of X —
    transitioned when #209 closed the last sites"), and that item being closed is
    precisely why the status is settled: it is the transition's own record, the
    healthiest state a norm reaches.

    Treating both alike reported every well-documented completed transition as
    rotting rationale — three at once in this repo's own observability strategy —
    which is the shape of finding that teaches a reader to stop reading the
    advisory. The ``Why:`` arm is untouched: rationale resting on finished work
    is decay whatever the status says.

    The handoff with ``stalled-transition`` is preserved rather than incidental:
    that probe skips a dead tracking item explicitly, calling it this one's job,
    so the in-transition arm has to stay.
    """
    return bool(_STATUS_RE.match(line)) and bool(_IN_TRANSITION_RE.search(line))


def _live_scope(state: ProjectState) -> str | None:
    """The backlog scope to resolve citations against, or ``None`` pre-cutover.

    ``None`` rather than ``""`` or ``False``: the two backends are a genuine
    either/or and every caller branches on it, so the pre-cutover value has to be
    a type the annotations can name. An earlier cut wrote ``post_cutover(state)
    and str(...)``, which yields ``False`` — a ``bool`` flowing into three
    parameters annotated ``str``, type-safe only because ``post_cutover`` happens
    to return exactly ``bool(...)`` today.
    """
    if not post_cutover(state):
        return None
    return str(state.get("backlog_service_repo") or "") or None


def _scan_direction_citations(codebase: Codebase, state: ProjectState, line_wanted, collect):
    """Walk the ``## Direction`` lines the caller wants and hand it their citations.

    The two backlog-reading probes share four moves — select the backend, load the
    markdown index when there is one, walk the artifacts' Direction lines, and turn
    an unanswerable store into the shared advisory. Only the line filter and what
    to make of a citation differ, so those are the two arguments and the rest has
    one home; the backend selection in particular is a thing to get wrong once,
    not twice.

    ``line_wanted(line)`` selects lines; ``collect(scope, index, cited)`` returns
    this probe's finding for a citation, or ``None``. Returns
    ``(findings_by_artifact_and_id, advisory)`` — at most one is non-empty, since a
    store that could not answer has no findings and findings mean it did.
    """
    scope = _live_scope(state)
    index = {} if scope else _backlog_index(codebase)
    if scope is None and not index:
        return {}, []
    found: dict[tuple[str, str], object] = {}
    try:
        for path in _artifact_paths(codebase):
            text = _read_text(path)
            if not text:
                continue
            for line in _direction_lines(text):
                if not line_wanted(line):
                    continue
                for cited in _extract_ids(line):
                    outcome = collect(scope, index, cited)
                    if outcome is not None:
                        found[(path.name, cited)] = outcome
    except _CacheUnanswerable as exc:
        return {}, _cache_advisory(exc, scope or "<backlog_service_repo>")
    return found, []


def _cited_is_dead(codebase: Codebase, scope: str | None, index: dict, cited: str) -> bool:
    """Is the item ``cited`` names shipped, dropped or archived?

    ``False`` for a citation that names nothing — a norm citing an unknown id is
    the doctor's registry-integrity finding, not decay, and answering "dead"
    about an item nobody can find would put the wrong repair in front of a reader.
    """
    if scope:
        resolved = _resolve_citation(codebase, scope, cited)
        return bool(resolved and resolved.get("dead"))
    item = index.get(cited)
    return item is not None and _is_dead(item)


def _cited_stall_age(
    codebase: Codebase, scope: str | None, index: dict, cited: str, *, today: date
) -> int | None:
    """Days since the **live** item ``cited`` names was last touched, or ``None``.

    ``None`` covers every fail-toward-silence case at once: an unresolvable
    citation, a dead item (dead-why's finding, not this one), and a stamp too
    malformed to date. Collapsing them is safe because they lead to the same
    action — none — and separating them would invite this probe to report on
    conditions two other checks already own.
    """
    if scope:
        resolved = _resolve_citation(codebase, scope, cited)
        if not resolved or resolved.get("dead"):
            return None
        touched = encode_parse_iso(resolved.get("updated_at"))
        return None if touched is None else (today - touched.date()).days
    item = index.get(cited)
    if item is None or _is_dead(item):
        return None
    floor = _item_floor_date(item)
    return None if floor is None else (today - floor).days


def _preferences_lines(codebase: Codebase) -> list[str]:
    """The product's `project-preferences.md`, split into lines (``[]`` if absent)."""
    text = _read_text(codebase.root / ".prawduct" / "artifacts" / "project-preferences.md")
    return text.splitlines() if text else []


def _norm_index_header(lines: list[str]) -> "tuple[int, list[str]] | None":
    """Locate the Enforcement **index** table: ``(header line number, cells)``.

    The index table is identified by its header row — a markdown table row whose
    first cell starts with ``Preference`` (the ratified header reads
    ``Preference / norm``; the pre-norm template read ``Preference``). The FIRST
    matching header decides, per the template's one-index-table-per-file shape.

    One locator, deliberately: both the "does the index carry the norm columns"
    question and the "does it carry a populated norm row" question must be
    answered about the SAME table. Locating it twice with different acceptance
    rules — the first ``Preference`` header vs. the first one carrying the
    columns — lets a file with two such tables get contradictory nudges out of a
    single read.
    """
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if cells and cells[0].startswith("Preference"):
            return idx, cells
    return None


def _norm_index_lacks_columns(codebase: Codebase) -> bool:
    """True when the preferences Enforcement index table exists but lacks the norm columns.

    Lacking either :data:`_NORM_INDEX_COLUMNS` cell means the table predates the
    norm index. No preferences file, or no such table, fails toward silence —
    there is nothing to extend, and structural absence of the registry is the
    first trigger arm's job."""
    header = _norm_index_header(_preferences_lines(codebase))
    if header is None:
        return False
    return not all(col in header[1] for col in _NORM_INDEX_COLUMNS)


def _has_enforcement_norm_rows(codebase: Codebase) -> bool:
    """True when the preferences Enforcement index table carries a populated norm row.

    ``docs/norms.md`` § Where Norms Live makes that table the product's norm
    **index** — "each norm has a row assigning its enforcement mechanism and its
    audit home" — so a populated row is a norm homed there exactly as a
    ``## Direction`` entry is one homed in an artifact. A product may home its
    norms entirely this way and carry no Direction section at all.

    Requires the norm columns AND a data row whose cells for them are non-empty:
    columns with nothing under them are the *shape* of a registry, not a
    registry, and treating the header as sufficient would nag every repo whose
    template ships it. The header separator row is skipped, and a non-table line
    ends the table.

    Reads the index through the shared :func:`_norm_index_header` locator, so
    this and :func:`_norm_index_lacks_columns` are always answering about the
    same table.
    """
    lines = _preferences_lines(codebase)
    header = _norm_index_header(lines)
    if header is None:
        return False
    start, cells = header
    if not all(col in cells for col in _NORM_INDEX_COLUMNS):
        return False
    cols = [cells.index(col) for col in _NORM_INDEX_COLUMNS]
    for line in lines[start + 1:]:
        stripped = line.strip()
        if not stripped.startswith("|"):
            break  # the table ended
        row = [c.strip() for c in stripped.strip("|").split("|")]
        if all(c and set(c) <= {"-", ":"} for c in row):
            continue  # the header separator row
        if max(cols) < len(row) and all(row[i] for i in cols):
            return True
    return False


def _norms_exist(codebase: Codebase) -> bool:
    """True when the product homes norms under EITHER homing.

    ``docs/norms.md`` § Where Norms Live gives norms two homes — ``## Direction``
    entries in strategy-class artifacts, and rows in the preferences Enforcement
    index. Asking only about the first is what made the time-domain audit
    unreachable for a repo that legitimately uses only the second: not a soft
    degradation but permanent silence, with no signal that the probe was inert.
    "Advice fails soft" is not "advice fails silent".

    Deliberately NOT used by :func:`probe_norm_registry_unratified`'s first arm,
    which asks a different question. That arm asks whether *architectural
    direction* has been ratified, and its answer lives in Direction sections by
    definition; this asks whether there are *any* norms to audit.
    """
    return _any_direction_entry(codebase) or _has_enforcement_norm_rows(codebase)


# =============================================================================
# Probes
# =============================================================================


def probe_revisit_due(state: ProjectState, codebase: Codebase):
    """Fire when an open backlog item's ``revisit: YYYY-MM-DD`` clock is past due.

    Non-date ``revisit:`` values are ignored (the janitor Norm Health sweep walks
    event triggers). One stable advisory; the past-due items are listed in the
    summary (id-independent evidence keeps the advisory id put).

    **Live on the markdown backend, dark on the Issues one — and unlike its two
    siblings the cache did not change that, because no query could.** ``revisit:``
    records *this exception was granted until date X*, which is intent rather than
    state; two exceptions granted the same day with different clocks are
    indistinguishable to any age-based query, so there is nothing for a cache to
    serve. What is missing post-cutover is a *write path* for the field, not a
    read path (#550/#564) — which is why this probe keeps its cutover early return
    rather than gaining a cache arm.

    An earlier pass retired the function outright, on the reasoning that exception
    clocks had already migrated to prose on the norm. **That is true of this repo
    and of no other**: for every markdown-backend product the probe was live and
    working, and ``docs/norms.md`` § Exceptions expire states the two-path split
    normatively — dated values fire mechanically here, event-bound ones in the
    janitor's sweep, which explicitly declines dated clocks *because* this fires
    them. Removing it would have taken a working control away from a whole class
    of products to suit one repo's arrangement, and left four surfaces promising a
    mechanism that no longer existed.
    """
    if post_cutover(state):
        return []  # item liveness now lives on GitHub Issues; the file is frozen
    today = datetime.now(timezone.utc).date()
    text = _read_text(_backlog_path(codebase))
    if not text:
        return []
    due: list[BacklogItem] = []
    for item in parse_backlog(text).items:
        if _is_dead(item):
            continue
        revisit = _parse_date(item.revisit)
        if revisit is not None and revisit < today:
            due.append(item)
    if not due:
        return []
    listed = ", ".join(sorted(_label(i) for i in due))
    return [
        AdvisoryCandidate(
            type="revisit-due",
            evidence=("one or more open backlog items carry a past-dated `revisit:` exception clock",),
            trigger_summary=(
                f"Exception clock expired — `revisit:` past due on: {listed}. "
                "Renew (fresh `revisit:` date + reason) or schedule removal."
            ),
            recommended_action=(
                "Review each listed item: renew the exception with a fresh `revisit:` date and "
                "reason, or schedule its removal (docs/norms.md § Exceptions expire)."
            ),
            priority="info",
        )
    ]


def probe_dead_why(state: ProjectState, codebase: Codebase):
    """Fire when a norm's Why/Status line cites a shipped/archived backlog id (decay).

    Scans ``## Direction`` entries in ``.prawduct/artifacts/*.md`` for backlog-id
    literals on ``Why:``/``Status:`` lines; a literal resolving to a dead item
    means the rationale rests on completed/abandoned work. One stable advisory;
    the ``artifact→id`` pairs are listed in the summary.

    **Two backends, one question.** Pre-cutover the item's liveness is read from
    the markdown backlog; post-cutover it is resolved through the backlog cache,
    which answers the same question about a store that is actually live —
    including through aliases, so a norm citing a pre-migration ``PFX`` id still
    resolves to the issue that carries it.

    *Expected yield*, named because re-adding a control is adding one: norm
    rationale that rests on finished work, at a rate of a handful per repo per
    quarter. If it fires on nothing over a year of real use it should be retired,
    not defended.
    """
    found, advisory = _scan_direction_citations(
        codebase,
        state,
        lambda line: bool(_WHY_RE.match(line)) or _in_flight_status(line),
        lambda scope, index, cited: _cited_is_dead(codebase, scope, index, cited) or None,
    )
    if advisory:
        return advisory
    pairs = set(found)
    if not pairs:
        return []
    listed = "; ".join(f"{name}→{cid}" for name, cid in sorted(pairs))
    return [
        AdvisoryCandidate(
            type="dead-why",
            evidence=("a norm's Why/Status line cites a backlog id whose item is shipped or archived (decay)",),
            trigger_summary=(
                f"Norm rationale references completed/abandoned work (decay): {listed}. "
                "Re-affirm and schedule cleanup, or retire the norm."
            ),
            recommended_action=(
                "Review each norm whose cited work is shipped/archived: re-affirm it and file a "
                "cleanup item, or retire it via a recorded amendment (docs/norms.md § Trajectory)."
            ),
            priority="info",
        )
    ]


def probe_stalled_transition(state: ProjectState, codebase: Codebase):
    """Fire when an in-transition norm's tracking item is live but unchanged past the window.

    Extracts the tracking backlog id from each ``Status: in-transition`` line in a
    ``## Direction`` entry; fires when that item is still live and its last-touched
    floor is older than :data:`STALL_WINDOW_DAYS`. A missing item (doctor's
    registry-integrity job), a dead item (dead-why's job), and an item with no
    date signal all fail toward silence. One stable advisory; the stalled
    ``artifact→id`` pairs and their staleness are listed.

    **The date floor differs by backend, and the cached one is the better
    signal.** Pre-cutover it is the later of the item's ``reviewed:``/``added:``
    stamps (:func:`_item_floor_date`) — a *floor*, since a body edit that misses
    ``reviewed:`` never advances it. Post-cutover it is the provider's
    ``updated_at``, which is always present, moves on any edit, and cannot be
    forgotten. That trades a stored field nobody had a write path for against an
    observed one, which is the same trade the staleness nag made.

    *Expected yield*: declared substrate migrations that quietly stopped moving —
    rare by construction, since a repo rarely has more than one or two in flight.
    A year with no fire means transitions here complete promptly and the check has
    no remaining yield.
    """
    today = datetime.now(timezone.utc).date()

    def _stalled(scope, index, cited):
        age = _cited_stall_age(codebase, scope, index, cited, today=today)
        return age if age is not None and age > STALL_WINDOW_DAYS else None

    stalled, advisory = _scan_direction_citations(
        codebase, state, lambda line: bool(_IN_TRANSITION_RE.search(line)), _stalled
    )
    if advisory:
        return advisory
    if not stalled:
        return []
    listed = "; ".join(f"{name}→{cid} ({age}d)" for (name, cid), age in sorted(stalled.items()))
    return [
        AdvisoryCandidate(
            type="stalled-transition",
            evidence=("an in-transition norm's tracking backlog item is unchanged past the stall window",),
            trigger_summary=(
                f"Stalled transition(s) — tracking item unchanged >{STALL_WINDOW_DAYS}d: {listed}. "
                "Accelerate the migration or record a stopgap."
            ),
            recommended_action=(
                "For each stalled transition: accelerate the tracked migration, or record a stopgap "
                "(a bounded exception whose expiry ties to the tracking item) — never improvise a "
                "parallel system (docs/norms.md § Transitions)."
            ),
            priority="info",
        )
    ]


def probe_norm_registry_unratified(state: ProjectState, codebase: Codebase):
    """Fire once post-upgrade: strategy-class artifacts exist but the registry is unratified.

    Two trigger arms, one stable advisory: (a) no ``## Direction`` **entry**
    exists in ANY artifact — a heading with nothing normative under it is not a
    registry (:func:`_has_direction_entry`); (b) the preferences Enforcement index
    table lacks the norm columns (:func:`_norm_index_lacks_columns`) —
    ratification began but the index cannot carry it. Both arms are gated on a
    strategy-class artifact existing. Suppressed when the shared-state
    :data:`RATIFIED_FACT` answer is recorded (a "no norms to ratify" outcome is
    valid and clears it for everyone). Points at the ``/prawduct:doctor``
    ratification flow, which resolves both arms."""
    if state.get(RATIFIED_FACT):
        return []
    paths = _artifact_paths(codebase)
    if not any(p.name in STRATEGY_CLASS_ARTIFACTS for p in paths):
        return []
    arms: list[str] = []
    if not any(_has_direction_entry(_read_text(p)) for p in paths):
        arms.append("no `## Direction` section is ratified in any artifact")
    if _norm_index_lacks_columns(codebase):
        arms.append("the preferences Enforcement table lacks the norm columns (Audit home / Why)")
    if not arms:
        return []
    return [
        AdvisoryCandidate(
            type="norm-registry-unratified",
            evidence=(
                "strategy-class artifacts exist but the norm registry is unratified "
                "(no `## Direction` sections, or the Enforcement table lacks the norm columns)",
            ),
            trigger_summary=(
                f"Norm registry unratified: {'; '.join(arms)}. Ratify the direction the "
                "owner already declared, or record that there are none to ratify."
            ),
            recommended_action="/prawduct:doctor",
            priority="info",
        )
    ]


def probe_norm_health_sweep_overdue(state: ProjectState, codebase: Codebase):
    """Fire when norms exist but the janitor Norm Health sweep is overdue / never run.

    Reads the committed :data:`SWEEP_STAMP` (the janitor theme writes it; this
    probe is read-only). Guarded on norms existing under **either** homing
    (:func:`_norms_exist`), so a repo with no norms never sees it while a repo
    that homes them only in the preferences Enforcement index still does. The
    earlier guard asked only about ``## Direction`` headings, which gave a
    table-homed product no time-domain norm audit at all, ever, with no signal
    that the probe was inert. The effective "last full engagement" is the
    NEWER of the sweep stamp and the ratification date (:data:`RATIFIED_FACT`):
    ratifying the registry is itself a deep pass over every norm, so a
    freshly-ratified repo is not overdue for a sweep until the window elapses —
    otherwise ratification would trip this nudge the same day it clears
    ``norm-registry-unratified``. Absent-or-stale on both fires; either being
    fresh suppresses. Points at ``/prawduct:janitor`` (Norm Health)."""
    if not _norms_exist(codebase):
        return []
    engaged = [
        d
        for d in (_parse_date(state.get(SWEEP_STAMP)), _leading_date(state.get(RATIFIED_FACT)))
        if d is not None
    ]
    if engaged:
        age = (datetime.now(timezone.utc).date() - max(engaged)).days
        if age <= SWEEP_WINDOW_DAYS:
            return []
    return [
        AdvisoryCandidate(
            type="norm-health-sweep-overdue",
            # This string is an IDENTITY KEY, not prose: `advisory_store.compute_id`
            # hashes the evidence list, so editing it mints a new id and every repo
            # that dismissed this advisory sees it return. It now under-describes the
            # trigger — the guard also fires on norms homed in the preferences
            # Enforcement index, not only on `## Direction` sections — and is left
            # verbatim anyway, because a dismissal means "I don't want this nudge" and
            # a widened trigger does not revoke that. Say it accurately in
            # `trigger_summary` (which is id-free) and, when the wording must change,
            # bump PROBE_VERSION so the supersession is deliberate.
            evidence=("norms exist (`## Direction` sections) but the janitor Norm Health sweep is overdue or never run",),
            # The route lives HERE, not only in `alternative_actions`: no surface
            # renders that field — briefing, `advisory list` and `advisory show`
            # all print `trigger_summary` + `recommended_action` — so setting it
            # alone left the reader still sent to a sweep over an empty registry.
            # `trigger_summary` is rendered AND is not part of `compute_id`, so
            # it is the one place this can be said without minting a new id.
            trigger_summary=(
                f"Norm Health sweep overdue (>{SWEEP_WINDOW_DAYS}d or never run) while norms exist — "
                "erosion and decay go unmeasured. If this repo has ratified nothing, the rows are "
                "probably leftover template scaffold: run `/prawduct:doctor` Health Check #14 "
                "(`norm-index-scaffold`) instead of a sweep."
            ),
            recommended_action="/prawduct:janitor",
            # A repo that is here because it still carries the TEMPLATE's
            # scaffold rows owes no sweep at all — the fix is the repair, not
            # the audit. The probe cannot tell the two apart (it sees populated
            # rows either way), so it names both routes rather than sending
            # every reader to the one that is wrong for some of them.
            alternative_actions=("/prawduct:doctor (Health Check #14 — leftover norm-index scaffold rows)",),
            priority="info",
        )
    ]


def register() -> None:
    """Register the norm-lifecycle probes. Idempotent (register_probe overwrites)."""
    register_probe(FEATURE, "revisit-due", PROBE_VERSION, probe_revisit_due)
    register_probe(FEATURE, "dead-why", PROBE_VERSION, probe_dead_why)
    register_probe(FEATURE, "stalled-transition", PROBE_VERSION, probe_stalled_transition)
    register_probe(FEATURE, "norm-registry-unratified", PROBE_VERSION, probe_norm_registry_unratified)
    register_probe(FEATURE, "norm-health-sweep-overdue", PROBE_VERSION, probe_norm_health_sweep_overdue)
