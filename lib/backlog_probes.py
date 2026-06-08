"""Post-sync advisory probes for the backlog feature (requirements §8.2).

Four probes registered against the shared advisory infrastructure
(:mod:`lib.advisory_store`). Each is a pure ``ProbeFn(state, codebase)`` that
reads the consumer's own ``.prawduct/`` and returns at most one
:class:`~lib.advisory_store.AdvisoryCandidate`. They never write — resolution is
a *fact* the consumer records in ``project-state.yaml`` (the answer store), which
resolves the advisory for everyone on next sync.

``legacy-backlog-format`` is the primary one — the nudge a repo hits right after
adopting a new prawduct version with an unmigrated backlog (``/prawduct:backlog
migrate``). It was the single production probe in framework v1.7.0
(``tools/lib/backlog_probes.py``), deleted with the file-sync engine in M4, and
re-ported here. The other three (``external-backlog-detected``,
``legacy-section-schema``, ``backlog-overdue-grooming``) were the v0.2-deferred
roster.

Registration is wired at the runtime composition root (``bin/prawduct-hook``
``cmd_clear``), not at ``advisory_store`` import time, so the infrastructure stays
feature-agnostic. Call :func:`register` once before the probe roster runs.

Counts are derived on read (D14) — no count is persisted; only the
``backlog_last_groomed_at`` *timestamp* is (written by ``/prawduct:backlog``'s
``list``/``pick``), which is an event marker, not a derivable aggregate.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .advisory_store import AdvisoryCandidate, ProjectState, Codebase, register_probe
from .backlog import parse_backlog

FEATURE = "backlog"
PROBE_VERSION = 1

# External backlog files a project may already keep (requirements §8.2/§8.3).
EXTERNAL_BACKLOG_NAMES = ("TODO.md", "BACKLOG.md", "ROADMAP.md", "IDEAS.md")
EXTERNAL_BACKLOG_DIRS = ("", ".github")

# Old section-schema headings the structured format replaced (requirements §8.2).
# `## Active — next up` and `## Queue` are the documented legacy headings; we don't
# also list a bare `## Active` because it's a substring of the former (it would
# double-cite in the evidence) and isn't itself the documented schema.
LEGACY_SECTION_HEADINGS = ("## Active — next up", "## Queue")

# Overdue-grooming thresholds (requirements §8.2 — tune against real products).
GROOMING_MIN_OPEN_ITEMS = 20
GROOMING_STALE_DAYS = 90

# Legacy-format trigger floor (requirements §8.2): fire when the backlog carries
# MORE than this many items and none is structured.
LEGACY_FORMAT_MIN_ITEMS = 5


def _backlog_path(codebase: Codebase) -> Path:
    return codebase.root / ".prawduct" / "backlog.md"


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def probe_external_backlog(state: ProjectState, codebase: Codebase):
    """Fire when an external backlog file exists and hasn't been audited.

    Resolution: the file is gone, OR its name appears in the
    ``backlog_external_imports`` fact (recorded by ``/prawduct:backlog import``).

    Resolution contract: the check is ``bare_filename not in recorded`` — a
    substring test on the bare name (``TODO.md``), so it resolves whether
    ``import`` recorded the bare name or the full path (``.github/TODO.md``).
    Both forms contain the bare filename, so the skill and probe stay in step.
    """
    recorded = str(state.get("backlog_external_imports", "") or "")
    found: list[str] = []
    for d in EXTERNAL_BACKLOG_DIRS:
        for name in EXTERNAL_BACKLOG_NAMES:
            rel = f"{d}/{name}" if d else name
            if (codebase.root / rel).is_file() and name not in recorded:
                found.append(rel)
    if not found:
        return []
    return [
        AdvisoryCandidate(
            type="external-backlog-detected",
            evidence=tuple(found),
            trigger_summary=f"External backlog file(s) not yet imported: {', '.join(found)}",
            recommended_action=f"/prawduct:backlog import {found[0]}",
            priority="info",
        )
    ]


def probe_legacy_section_schema(state: ProjectState, codebase: Codebase):
    """Fire when backlog.md uses the old ``## Active``/``## Queue`` schema.

    Resolution: ``backlog_format_version: 2`` recorded (migration folds the
    headings into the canonical Open/Promoted/Archive).
    """
    if str(state.get("backlog_format_version", "")) == "2":
        return []
    text = _read_text(_backlog_path(codebase))
    if not text:
        return []
    present = [h for h in LEGACY_SECTION_HEADINGS if h in text]
    if not present:
        return []
    return [
        AdvisoryCandidate(
            type="legacy-section-schema",
            evidence=tuple(present),
            trigger_summary="backlog.md uses the legacy section schema",
            recommended_action="/prawduct:backlog migrate --sections",
            priority="info",
        )
    ]


def _is_stale(groomed_at: str | None, *, now: datetime) -> bool:
    """True if never groomed, or groomed > GROOMING_STALE_DAYS ago.

    A present-but-unparseable timestamp degrades safe (treated as NOT stale —
    don't nag on bad data; only a clean signal fires).
    """
    if not groomed_at:
        return True  # never groomed
    raw = str(groomed_at).strip().rstrip("Z")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (now - parsed).days > GROOMING_STALE_DAYS


def probe_overdue_grooming(state: ProjectState, codebase: Codebase):
    """Fire when the backlog is large (>N open) and hasn't been groomed in >90d.

    The open-item count is derived on read (never persisted, D14). ``now`` is
    computed here because the locked ``ProbeFn`` signature carries no clock.
    Resolution: ``backlog_last_groomed_at`` updated (by ``/prawduct:backlog``).
    """
    text = _read_text(_backlog_path(codebase))
    if not text:
        return []
    open_count = len(parse_backlog(text).open_items())
    if open_count <= GROOMING_MIN_OPEN_ITEMS:
        return []
    if not _is_stale(state.get("backlog_last_groomed_at"), now=datetime.now(timezone.utc)):
        return []
    return [
        AdvisoryCandidate(
            type="backlog-overdue-grooming",
            evidence=(f"{open_count} open items", "last groomed: "
                      + str(state.get("backlog_last_groomed_at") or "never")),
            trigger_summary=f"{open_count} open backlog items and no grooming in over {GROOMING_STALE_DAYS} days",
            recommended_action="/prawduct:backlog list",
            priority="info",
        )
    ]


def probe_legacy_backlog_format(state: ProjectState, codebase: Codebase):
    """Fire when backlog.md has >5 items and none carries a ``[PFX-XXXX]`` id.

    The primary "your backlog predates the structured format" nudge — the one a
    repo hits right after adopting a new prawduct version with an unmigrated
    backlog. Resolution: ``backlog_format_version: 2`` recorded by
    ``/prawduct:backlog migrate`` (the shared answer store — a teammate's
    committed migration resolves the advisory for everyone on next sync).

    Partial migration does **not** fire: once *any* item carries a structured id
    the file is mid-flight, and ``backlog_format_version`` is the authoritative
    "done" signal. ``parse_backlog`` already excludes HTML-comment and
    code-fence bullets, so template example bullets are not miscounted.
    """
    if str(state.get("backlog_format_version", "")) == "2":
        return []
    text = _read_text(_backlog_path(codebase))
    if not text:
        return []
    items = parse_backlog(text).items
    if len(items) <= LEGACY_FORMAT_MIN_ITEMS or any(i.item_id for i in items):
        return []
    # Evidence is qualitative and count-independent (it is hashed into the
    # advisory id) so the id stays put as items come and go; the live count
    # lives in the summary.
    return [
        AdvisoryCandidate(
            type="legacy-backlog-format",
            evidence=(".prawduct/backlog.md contains items without [PFX-XXXX] structured ids",),
            trigger_summary=(
                f"{len(items)} backlog items lack [PFX-XXXX] structured ids — run "
                "/prawduct:backlog migrate to add metadata and enable pick/find/list filtering"
            ),
            recommended_action="/prawduct:backlog migrate",
            priority="info",
        )
    ]


def register() -> None:
    """Register the four backlog probes. Idempotent (register_probe overwrites)."""
    register_probe(FEATURE, "legacy-backlog-format", PROBE_VERSION, probe_legacy_backlog_format)
    register_probe(FEATURE, "external-backlog-detected", PROBE_VERSION, probe_external_backlog)
    register_probe(FEATURE, "legacy-section-schema", PROBE_VERSION, probe_legacy_section_schema)
    register_probe(FEATURE, "backlog-overdue-grooming", PROBE_VERSION, probe_overdue_grooming)
