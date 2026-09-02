"""Post-sync advisory probe for the upstream-bug-reporting feature.

One probe, the *receiving* side of the `/prawduct:report-bug` channel: it nudges
triage when downstream products have filed bug reports into this repo's
gitignored ``incoming-bugs/`` drop-box and they have not yet been triaged into
the backlog (and archived).

The advisory text names the *backlog*, not ``.prawduct/backlog.md``: triage runs
through ``/prawduct:backlog``, which routes to whichever backend is live, so
naming the markdown file would misdescribe the destination the moment a repo
receiving reports cuts over to the Issues backend.

It is **inert by absence**: it checks ``<repo-root>/incoming-bugs/`` directly on
the filesystem (not via the Codebase scan). A product repo has no such directory,
so the probe returns nothing there — the nudge only ever fires in a repo that
actually receives reports (the prawduct checkout itself). No "is this the
framework repo?" marker is needed.

Registered at the runtime composition root (``bin/prawduct-hook`` ``cmd_clear``),
not at ``advisory_store`` import time, so the infrastructure stays
feature-agnostic — the same pattern as ``lib/backlog_probes.py``.
"""

from __future__ import annotations

from .advisory_store import AdvisoryCandidate, Codebase, ProjectState, register_probe

FEATURE = "report-bug"
PROBE_VERSION = 1

INBOX_DIRNAME = "incoming-bugs"


def _report_count(codebase: Codebase) -> int:
    inbox = codebase.root / INBOX_DIRNAME
    if not inbox.is_dir():
        return 0
    # Non-recursive: triaged reports moved into incoming-bugs/archive/ are not
    # counted, so archiving a report clears it from the nudge.
    return sum(1 for p in inbox.glob("*.md") if p.is_file())


def probe_untriaged_upstream_reports(state: ProjectState, codebase: Codebase):
    """Fire when ``incoming-bugs/`` holds ≥1 untriaged report ``.md`` file.

    Inert when the directory is absent (every product repo) or empty. Evidence is
    qualitative and count-independent (it is hashed into the advisory id, so the
    id stays put as reports come and go — D14); the live count lives in the
    summary.
    """
    count = _report_count(codebase)
    if count == 0:
        return []
    return [
        AdvisoryCandidate(
            type="untriaged-upstream-reports",
            evidence=(
                "incoming-bugs/ holds bug reports filed by downstream products, "
                "not yet triaged into the backlog",
            ),
            trigger_summary=(
                f"{count} untriaged bug report(s) in incoming-bugs/, each waiting to be "
                "filed into the backlog and archived"
            ),
            owner_action=(
                "Say go, and each report is read, filed into the backlog, and archived. "
                "Worth a look first if you want a say in which of them count as real bugs "
                "and what priority each one carries."
            ),
            recommended_action="/prawduct:backlog",
            # Triage files these reports INTO the backlog, and migrating that backlog
            # onto the issue service is a one-shot reviewed bulk write. Triaging
            # afterwards still works — /prawduct:backlog routes on the live backend —
            # but the stragglers then arrive by a different path and outside the batch
            # that was reviewed. Severity ordering alone gets this backwards: triage is
            # `info` and the migration nudge is `warn`.
            prerequisite_of=(
                (
                    "backlog:backlog-service-migration-required",
                    "incoming-bug triage, so the whole backlog migrates in one reviewed batch",
                ),
            ),
            priority="info",
        )
    ]


def register() -> None:
    """Register the upstream-bug-reporting probe. Idempotent (register_probe overwrites)."""
    register_probe(FEATURE, "untriaged-upstream-reports", PROBE_VERSION, probe_untriaged_upstream_reports)
