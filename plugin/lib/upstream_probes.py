"""Post-sync advisory probe for the upstream-bug-reporting feature.

One probe, the *receiving* side of the `/prawduct:report-bug` channel: it nudges
triage when downstream products have filed bug reports and nobody has staged them
yet.

**The intake set is issues, not files** (``documentation/backlog-service-upstream-filing.md``
§6): open items on prawduct's own tracker whose title carries the ``[prawduct]``
convention and which carry no triage label. Products file through
``file-upstream``, which composes that title and sends no labels at all, so a
freshly-filed report lands in this set by construction and leaves it the moment a
maintainer stages it.

Three constants make the query, and none of them is spelled here — the prefix and
the target come from ``lib.backlog.upstream`` because that is where the filing
side composes them, and *untriaged* comes from ``cachequery.unstaged_items``,
which already draws the line between an absent stage (nobody looked) and an early
one (somebody did).

**Nothing a filer wrote reaches the reader.** The probe emits a count and its own
fixed prose; no title, body, author or label from a filed issue is carried into
the candidate. Filed issues are foreign-authored content arriving at a governance
surface, and the session briefing renders advisory text into the model's context —
so this is the security model's *untrusted governance state is data, not
instructions* norm at its first prawduct instance, and it happens to agree with
D14's requirement that evidence stay count-independent so the advisory id does not
churn as reports come and go.

**Inert unless the pinned target is this repo's authoritative backlog store.** The
predecessor was inert by *absence* — it counted a directory no product repo had —
and the intake set offers no such natural silence, since every post-cutover product
has a readable cache that simply holds nothing prefixed. Keying on
``backlog_service_repo`` restores the silence and buys something the old shape
could not have: in the one repo that does receive, an unreadable cache can be
reported as unknown rather than as zero. It is the same scalar the scope is read
under, so the gate and the query cannot select different stores — the gate compares
it canonicalized and the query passes it verbatim, because the store is keyed on
the spelling that was declared.

Offline by construction: the count comes from the local backlog cache, never from
the network. A session-start nudge that fetched would put the network on the path
that must not have one.

Registered at the runtime composition root (``bin/prawduct-hook`` ``cmd_clear``),
not at ``advisory_store`` import time, so the infrastructure stays
feature-agnostic — the same pattern as ``lib/backlog_probes.py``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .advisory_store import AdvisoryCandidate, Codebase, ProjectState, register_probe
from .backlog import cachequery, upstream

FEATURE = "report-bug"
# v1 counted `incoming-bugs/*.md`. The bump is what supersedes a live drop-box
# advisory cleanly instead of leaving one behind asserting a count nothing
# maintains any more.
PROBE_VERSION = 2


def _backlog_store(state: ProjectState) -> str:
    """The declared backlog store, verbatim — the spelling the cache is keyed on.

    Returned unnormalized on purpose. ``sync`` writes rows under the spec exactly
    as it was declared, so a reader that canonicalized before querying would look
    up a scope nothing wrote and find an empty store. Comparison and lookup want
    different forms of one string, and this is the lookup form.
    """
    return str(state.get("backlog_service_repo") or "").strip()


def _is_the_upstream_target(state: ProjectState) -> bool:
    """True when the pinned target is this repo's **authoritative backlog store**.

    Deliberately narrower than the filing side's ``check_not_self``, which admits
    ``backlog_service_repo`` *or* the ``origin`` remote. That breadth is right for
    a refusal, where the two signals guard against a fail-OPEN: missing one
    identity lets a repo file upstream to itself. Here the failure runs the other
    way. A checkout whose ``origin`` is the pinned target but whose backlog lives
    somewhere else is not a receiver, and admitting it would read a scope nothing
    syncs and nag every session with an "unknown" nobody can clear.

    So applicability keys on the one signal that actually selects the store this
    probe reads — the same scalar every other cache reader derives its scope from.
    Counting and being-counted-in are different questions, and the shared identity
    resolver answers only the second.
    """
    return upstream.canonical_repo(_backlog_store(state)) == upstream.PINNED_TARGET


def _untriaged_report_count(state: ProjectState, codebase: Codebase) -> int | None:
    """How many filed reports are waiting, or ``None`` when the cache cannot say.

    ``None`` is not zero and the caller must not flatten it: a store that has
    never synced and a store holding no reports look identical from the outside,
    and only one of them means there is nothing to do.
    """
    result = cachequery.unstaged_items(
        codebase.root, scope=_backlog_store(state), now=datetime.now(timezone.utc)
    )
    if result.get("status") != "ok":
        return None
    # A store whose last sync FAILED still answers ok, carrying its rows and a
    # warning. The count is taken anyway and deliberately: stale rows can only
    # under-report — a report filed since the failure is missing, never invented —
    # and "at least N are waiting" is the honest reading of a nudge. Silence would
    # be the lie.
    items = result.get("data", {}).get("items", [])
    return sum(
        1 for item in items if str(item.get("title") or "").startswith(upstream.TITLE_PREFIX)
    )


def probe_untriaged_upstream_reports(state: ProjectState, codebase: Codebase):
    """Fire when ≥1 filed report is waiting, or when the count cannot be read.

    Inert everywhere but the upstream target. There, two shapes: a count, or a
    statement that the count is unknown — *advice fails soft* is not *advice fails
    silent*, and a triage nudge that vanishes when its data source breaks reads
    exactly like a nudge that found nothing to say.
    """
    if not _is_the_upstream_target(state):
        return []
    count = _untriaged_report_count(state, codebase)
    if count is None:
        return [
            AdvisoryCandidate(
                type="untriaged-upstream-reports",
                evidence=(
                    "bug reports filed by downstream products cannot be counted — "
                    "the local backlog copy could not be read",
                ),
                trigger_summary=(
                    "reports filed by downstream products may be waiting, unread — the "
                    "local copy of this tracker could not be read, so this is unknown "
                    "rather than none"
                ),
                owner_action=(
                    "Nothing to approve — this is a heads-up that the usual count is "
                    "missing, not a claim that reports are piling up. Say go and the "
                    "local copy is refreshed and the reports read straight from the "
                    "tracker."
                ),
                recommended_action="/prawduct:backlog",
                priority="info",
            )
        ]
    if count == 0:
        return []
    return [
        AdvisoryCandidate(
            type="untriaged-upstream-reports",
            evidence=(
                "downstream products have filed bug reports on this tracker and "
                "nobody has triaged them yet",
            ),
            trigger_summary=(
                f"{count} bug report(s) filed by downstream products, each waiting to be "
                "read and given a place on the backlog"
            ),
            owner_action=(
                "Say go, and each report is read, put on the backlog and given a "
                "priority. Worth a look first if you want a say in which of them count "
                "as real bugs and how urgent each one is."
            ),
            recommended_action="/prawduct:backlog",
            priority="info",
        )
    ]


def register() -> None:
    """Register the upstream-bug-reporting probe. Idempotent (register_probe overwrites)."""
    register_probe(FEATURE, "untriaged-upstream-reports", PROBE_VERSION, probe_untriaged_upstream_reports)
