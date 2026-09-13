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


def _intake_reading(state: ProjectState, codebase: Codebase) -> tuple[int | None, bool]:
    """``(count, sync_is_stuck)`` — how many filed reports are waiting, and whether
    the number is still being refreshed.

    ``count`` is ``None`` when the cache cannot say, and the caller must not
    flatten that to zero: a store that has never synced and a store holding no
    reports look identical from the outside, and only one of them means there is
    nothing to do.

    ``sync_is_stuck`` is the second axis and it is separate for a reason. A store
    whose last sync FAILED still answers ``ok``, carrying its rows plus
    ``sync_error`` — so *readable* and *current* are different questions, and
    reading only the first turns a week of failed syncs into a confident number.
    Both branches need it, in opposite directions: a stale count can only
    UNDER-report (a report filed since the failure is missing, never invented), so
    a positive one is still worth saying as *at least N*; a stale ZERO is a false
    all-clear, which is the one thing a triage nudge must never emit.
    """
    result = cachequery.unstaged_items(
        codebase.root, scope=_backlog_store(state), now=datetime.now(timezone.utc)
    )
    if result.get("status") != "ok":
        return None, False
    data = result.get("data", {})
    stuck = bool(data.get("sync_error"))
    items = data.get("items", [])
    count = sum(
        1 for item in items if str(item.get("title") or "").startswith(upstream.TITLE_PREFIX)
    )
    return count, stuck


# The advisory says a sync is failing; it never says WHAT the failure was. The
# reviewer's fix proposed carrying `sync_error` into the trigger summary, and the
# text is free to vary (only `evidence` is hashed into the id, D14) — but that
# string is a provider message relayed through `gh`, and advisory text is rendered
# into the model's context at session start. The probe's whole posture is that no
# provider-authored bytes cross that line; widening it for an error message would
# trade the guarantee for a detail the operator gets by running the sync.
#
# EVIDENCE is shared between the two stalled shapes and the owner-facing COPY is
# not, which looks inconsistent and is the point. Evidence is what the advisory id
# hashes (D14), so one constant is what makes "your feed stopped" a single thing to
# dismiss whether or not it currently has rows behind it. Copy is duplicated below
# because `tests/test_advisory_actionability.py` reads advisory text statically at
# each construction site and skips what it cannot read — hoisting the strings put
# them out of the lint's reach, which is the evasion that test exists to make
# impossible rather than merely unlikely.
_SYNC_STUCK_EVIDENCE = (
    "the local copy of this tracker has stopped refreshing — its last sync failed, "
    "so any report filed since then is not counted below"
)


def _degraded_candidate() -> AdvisoryCandidate:
    """The cache could not be read at all — no rows, no age, no count."""
    return AdvisoryCandidate(
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


def probe_untriaged_upstream_reports(state: ProjectState, codebase: Codebase):
    """Fire when ≥1 filed report is waiting, or when the count cannot be trusted.

    Inert everywhere but the upstream target. There, three shapes — a count, a
    stalled feed, or a cache that could not be read at all — and the second is the
    one that has to exist for the first to mean anything. *Advice fails soft* is
    not *advice fails silent*, and a nudge that goes quiet because its data source
    stopped reads exactly like a nudge that found nothing to say.
    """
    if not _is_the_upstream_target(state):
        return []
    count, stuck = _intake_reading(state, codebase)
    if count is None:
        return [_degraded_candidate()]
    # prawduct:allow prawduct/duplication -- advisory copy must be literal at each
    # construction site or the actionability lint cannot read it (see above)
    if count == 0:
        if not stuck:
            return []
        # A stale zero is the false all-clear this probe exists to avoid. Distinct
        # evidence from the unreadable case on purpose: the two are different
        # states and the operator does different things about them, and evidence
        # is what keys the advisory id.
        return [
            AdvisoryCandidate(
                type="untriaged-upstream-reports",
                evidence=(_SYNC_STUCK_EVIDENCE,),
                trigger_summary=(
                    "reports filed by downstream products may be waiting, unread — "
                    "the local copy of this tracker stopped refreshing, so a count "
                    "of none is not evidence that none arrived"
                ),
                owner_action=(
                    "Nothing to approve. The count you are being shown is not "
                    "current and may be low; say go and the local copy is "
                    "refreshed, which is also what surfaces why it stopped."
                ),
                recommended_action="/prawduct:backlog",
                priority="info",
            )
        ]
    if stuck:
        return [
            AdvisoryCandidate(
                type="untriaged-upstream-reports",
                evidence=(_SYNC_STUCK_EVIDENCE,),
                trigger_summary=(
                    f"at least {count} bug report(s) filed by downstream products are "
                    "waiting to be read — at least, because the local copy of this "
                    "tracker stopped refreshing and anything filed since is uncounted"
                ),
                owner_action=(
                    "Nothing to approve. The count you are being shown is not "
                    "current and may be low; say go and the local copy is "
                    "refreshed, which is also what surfaces why it stopped."
                ),
                recommended_action="/prawduct:backlog",
                priority="info",
            )
        ]
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
