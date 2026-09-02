"""Post-sync advisory probes for the backlog feature (requirements §8.2).

Six probes registered against the shared advisory infrastructure
(:mod:`lib.advisory_store`). Each is a pure ``ProbeFn(state, codebase)`` that
reads the consumer's own ``.prawduct/`` and returns at most one
:class:`~lib.advisory_store.AdvisoryCandidate`. They never write — resolution is
a *fact* the consumer records in ``project-state.yaml`` (the answer store), which
resolves the advisory for everyone on next sync.

``legacy-backlog-format`` is the primary one — the nudge a repo hits right after
adopting a new prawduct version with an unmigrated backlog (``/prawduct:backlog
migrate``). It was the single production probe in framework v1.7.0
(``tools/lib/backlog_probes.py``), deleted with the file-sync engine in M4, and
re-ported here. ``backlog-service-migration-required`` is its structured-format
sibling (GV7): once a backlog *is* structured, this one nudges it onward onto the
GitHub Issues service, so a repo that upgraded past prawduct's own cutover is told
to migrate rather than silently losing its briefing count when the shared markdown
read path eventually retires (MG3). The other three
(``external-backlog-detected``, ``legacy-section-schema``,
``backlog-overdue-grooming``) were the v0.2-deferred roster.

A sixth probe stood here — ``backlog-checks-dormant``, which named every backlog
reader with no Issues-backend path so the dormancy was stated rather than read as
a clean bill of health. It is **gone because there is nothing left for it to
name**: the readers it enumerated now query the backlog cache
(``skills/backlog/cache-reads.md``), and a reader that cannot reach the store says
so at the point of use, which is a better place to say it than a session-start
advisory. The one check still dark post-cutover — the janitor's neglected-hygiene
sweep — waits on the ``promoted`` status value having no Issues equivalent, not on
anything this probe could announce, and it states that in its own block. Removal
rather than rewording was always the intended end state: the advisory shrank as
each reader landed.

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
from .backlog.legacy import parse_backlog

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
            # No file list here: the summary above already names them, and a second
            # copy would drift from the first the moment one is imported.
            owner_action=(
                "Say go and the items in these files are folded into the tracked backlog — "
                "a committed file, so you will see a diff to review before anything is "
                "staged. Tell me instead if one of them is deliberately kept separate: I "
                "will leave it alone, though the reminder stays until it is imported or removed."
            ),
            recommended_action=f"/prawduct:backlog import {found[0]}",
            priority="info",
        )
    ]


def post_cutover(state: ProjectState) -> bool:
    """True once the backlog lives on GitHub Issues (``backlog_service_repo``
    set at migration cutover). Every probe whose premise is "the markdown file
    IS the live backlog" retires on this switch — post-cutover the file is
    frozen history and any nudge derived from it would be stale by construction.
    Shared across probe families (this module's **four** markdown probes —
    ``legacy-backlog-format``, ``backlog-service-migration-required``,
    ``legacy-section-schema``, ``backlog-overdue-grooming`` — AND
    ``norm_probes.probe_revisit_due``, which reads exception clocks from the same
    file: one predicate, not per-module copies). ``external-backlog-detected``
    keeps firing: stray TODO.md files are a problem regardless of where the real
    backlog lives.

    **Two former callers now use it to CHOOSE a backend rather than to retire.**
    ``norm_probes``' ``dead-why`` and ``stalled-transition`` resolve their
    citations against the markdown file before the cutover and against the backlog
    cache after it, so for them this predicate selects a reader instead of
    silencing one. Anyone adding a guard here should decide which of the two
    shapes they are writing.

    **No caller *fires* on this switch any more.** One did — the dormancy advisory
    existed to say out loud what the retiring probes' silence would otherwise hide
    — and it went when the readers it named came back on the backlog cache. So the
    predicate now has exactly two shapes and no third: retire, or choose a
    backend."""
    return bool(state.get("backlog_service_repo"))


def probe_legacy_section_schema(state: ProjectState, codebase: Codebase):
    """Fire when backlog.md uses the old ``## Active``/``## Queue`` schema.

    Resolution: ``backlog_format_version: 2`` recorded (migration folds the
    headings into the canonical Open/Promoted/Archive).
    """
    if post_cutover(state):
        return []
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
            owner_action=(
                "Say go — this rewrites the section headings in a committed file, so you "
                "will see a diff to review before anything is staged. No item is dropped "
                "or reworded; only the headings they sit under change."
            ),
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
    if post_cutover(state):
        return []
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
            owner_action=(
                "Tell me when you want to walk the open items together. I can pull them up, "
                "rank them and close out the ones you are done with, but only you can say "
                "which ones stopped mattering — and dropping an item is your call, not mine."
            ),
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
    if post_cutover(state):
        return []
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
            # States the condition, not the fix — this line is relayed to the owner,
            # and the fix now has its two audience-specific homes below.
            trigger_summary=(
                f"{len(items)} backlog items lack [PFX-XXXX] structured ids, so they cannot "
                "be filtered, ranked or picked up by id"
            ),
            owner_action=(
                "Say go — this rewrites every item in a committed file to carry structured "
                "metadata, so you will see a diff to review before anything is staged. "
                "Nothing is dropped and no item's text is rewritten; each one gains an id "
                "and a few fields."
            ),
            recommended_action="/prawduct:backlog migrate",
            priority="info",
        )
    ]


def probe_migration_required(state: ProjectState, codebase: Codebase):
    """Fire when a **structured** markdown backlog holds live items and the project
    has not cut over to the GitHub Issues service (``backlog_service_repo`` unset).

    The GV7 migration-required signal. When the shared plugin eventually retires
    its markdown read path at portfolio-wide migration (MG3), a repo that upgraded
    but never migrated would lose its briefing count and grooming nudges
    *silently* — the exact opposite of a "migration required" signal. This probe
    makes it loud and early: as long as a structured backlog sits unmigrated, every
    session says so.

    **Distinct from ``legacy-backlog-format``**, which nudges a *pre-structured*
    file toward the structured format and fires only when NO item carries a
    ``[PFX-XXXX]`` id. This one nudges a *structured* file onto the service and
    fires only when the structured format is already in use (≥1 ``[PFX-XXXX]`` id).
    The two partition the space, so a backlog trips at most one of them.

    Resolution: ``backlog_service_repo`` set at cutover (``post_cutover``) — the
    same switch that retires the other markdown probes. ``warn`` priority (above
    the ``info`` format/grooming nudges): unmigrated-at-upgrade is a real
    signal-loss risk — though, like every advisory, never blocking.
    """
    if post_cutover(state):
        return []
    text = _read_text(_backlog_path(codebase))
    if not text:
        return []
    parsed = parse_backlog(text)
    if not any(item.item_id for item in parsed.items):
        return []  # pre-structured file → legacy-backlog-format owns the nudge
    pending = parsed.pending_items()
    if not pending:
        return []  # a frozen all-archived file has nothing live to migrate
    # Evidence is qualitative and count-independent (it is hashed into the advisory
    # id) so the id stays put as items come and go; the live count is in the summary.
    return [
        AdvisoryCandidate(
            type="backlog-service-migration-required",
            evidence=(
                ".prawduct/backlog.md is a structured backlog not yet migrated to "
                "GitHub Issues (backlog_service_repo unset)",
            ),
            trigger_summary=(
                f"{len(pending)} pending items in the markdown backlog and no "
                "backlog_service_repo — migrate to GitHub Issues before an upgrade "
                "retires the shared markdown read path"
            ),
            # The cost of yes, in the sentence the owner actually reads. Both the
            # volume and the irreversibility are load-bearing and neither is
            # decoration: GitHub has no ordinary issue delete and never reuses a
            # number, so this batch cannot be walked back the way a bad commit can.
            # Stating it here rather than leaving it to the summary is what makes the
            # approval an informed one — the same count appears above as the *trigger*
            # ("this many items are unmigrated"); here it is the *price* ("this many
            # issues get created"). One expression, two different facts.
            owner_action=(
                f"Decide whether to migrate now: this creates {len(pending)} real GitHub "
                "issues in one batch and cannot be undone — GitHub has no ordinary delete "
                "for an issue and never reuses a number. You review and approve the "
                "proposed batch before anything is written."
            ),
            recommended_action="/prawduct:backlog scrub",
            priority="warn",
        )
    ]


def register() -> None:
    """Register the five backlog probes. Idempotent (register_probe overwrites).

    ``backlog-service-migration-required`` fires live. It spent several releases
    wired to a no-op while the migration path was unproven, because its
    ``recommended_action`` routes into an irreversible bulk write (100-250 real
    GitHub issues; GitHub has no ordinary issue-delete and never reuses numbers),
    and a fleet-wide nudge toward that is not a cosmetic default. The stated
    conditions for wiring it up were: the scrub runbook binds an owner-confirmed
    target repo, is honest about its absent dry-run, and runs under a narrowed
    adapter grant — plus at least one proven real end-to-end migration. All are
    discharged, and the owner ruled it live rather than leaving the probe's default
    to decide by silence.

    **What makes it safe is not the probe — it is that the advisory now reaches a
    person.** The briefing prints to stdout, the agent-facing channel, so before
    the relay directive this advisory could route the *model* toward those writes
    with nobody informed. It is a `warn`, so it trips the relay
    (``briefing.ADVISORY_RELAY_TEXT``) and the migration becomes the owner's call,
    which is the only form in which it was ever meant to be offered. Do not
    silence the relay for `warn` without re-deciding this.
    """
    register_probe(FEATURE, "legacy-backlog-format", PROBE_VERSION, probe_legacy_backlog_format)
    register_probe(
        FEATURE,
        "backlog-service-migration-required",
        PROBE_VERSION,
        probe_migration_required,
    )
    register_probe(FEATURE, "external-backlog-detected", PROBE_VERSION, probe_external_backlog)
    register_probe(FEATURE, "legacy-section-schema", PROBE_VERSION, probe_legacy_section_schema)
    register_probe(FEATURE, "backlog-overdue-grooming", PROBE_VERSION, probe_overdue_grooming)
