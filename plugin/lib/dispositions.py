"""Finding dispositions as facts, and the census as a derived view.

A review produces findings. The ones that get **fixed** already leave a
machine-readable trace: a ``resolution`` fact recorded by a
``verify-resolutions`` pass. The ones that get **accepted** or **filed** left
no trace at all — they lived only in hand-written change-log prose, which is
why censuses drifted and their corrections bought review rounds. Measured on
this repo, 2026-07-29: one census asserted "10 accepted notes", corrected
itself to "9 accepted and one discharged question" in its own closing
sentence, and separately claimed "all 13 blocking/warning FIXED" when the
store records one of the thirteen as *waived*. Three of those four errors are
arithmetic over data the store already held.

So dispositions become facts and the census becomes a rendering of them.

**Vocabulary warning.** "Disposition" already names two other things in this
codebase: a *release* scope is ``ships``/``withheld``
(``release_readiness.py``) and a *resolution* fact carries
``fixed``/``waived`` (``coverage_algebra._RESOLVING_DISPOSITIONS``). To keep
one field name from meaning three things across the store, this fact's field
is ``action`` — ``accept``, ``file`` or ``fixed``.

**Why ``fixed`` is here at all, when a resolution fact already records a fix.**
A fix confined to non-judgeable paths buys no review round — which is the
outcome the framework steers toward — so no ``verify-resolutions`` pass runs
and no resolution fact is ever written, and the census reports the finding
``undispositioned`` forever. That inverts the gradient one level up: an agent
wanting a clean census can ACCEPT (free) or buy a round (ten minutes), and the
cheapest correct action — fix it for free — is the only one the record cannot
see. So a free fix becomes recordable, **verified at record time against the
same predicate that prices the edit**: a path set holding anything judgeable is
refused, so this can never launder a judgeable fix past a gate. A BLOCKING
finding is refused outright and still clears only through a real resolution
fact; nothing about gating changes.

**A disposition can never weaken a gate.** ``coverage_algebra`` filters
``kind != "resolution"`` before reading any body, so a BLOCKING finding stays
blocking until a verify pass records a real resolution. That is the
load-bearing safety property here, and it is pinned by a regression test
rather than left resting on the filter staying where it is.

**Observations are answerable too, and the id domain is what carries that.**
A ``verify-resolutions`` pass demotes every non-BLOCKING finding to an
*observation*. Until observations reached the review fact they could be
discharged in exactly two ways — FIX one, which moves the tree and buys a
review round, or say nothing, which loses the reasoning. So an agent that had
decided an observation was not worth acting on had no way to say so, and fixing
it was the only answer that left a trace; measured on one consumer branch, two
such fix commits bought rounds 4 and 5 of six. :func:`record` therefore joins
against findings **and** observations, whose id namespaces are disjoint
(``R-1`` against ``O-1``). Nothing else changes: an observation lives outside
the review fact's ``findings`` array, which is the only one the coverage
algebra walks, so answering one gates exactly what it gated before.

**Re-disposition appends; it never edits.** ``evidence.read_facts`` dedupes
``(kind, id)`` keeping the *first* occurrence, so reusing a fact id would make
a changed answer silently vanish. Each disposition therefore carries a
per-finding sequence in its id, and an unchanged re-run is caught by comparing
against the newest recorded answer — reported as a no-op, never left to
accidental dedupe. Last answer wins, resolved by store order.

Errors are return values per project-preferences; exit codes follow
``api-contract.md``'s scheme (writer fails closed at 1, usage error at 2).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from . import evidence

KIND = "disposition"

ACCEPT = "accept"
FILE = "file"
FIXED = "fixed"
ACTIONS = (ACCEPT, FILE, FIXED)

#: The ``--json`` shape is a machine contract; key changes bump this.
#: 2 added each review's ``observations`` list and the summary's
#: ``observations``/``observations_answered`` pair. Additive — a version-1
#: reader that ignores unknown keys still reads a version-2 report correctly —
#: but the number is what lets a consumer say which shape it was written for,
#: and a bump costs nothing next to a consumer guessing.
REPORT_SCHEMA_VERSION = 2

#: Display states a census row can carry, in the order the summary reports
#: them. ``resolved-*`` covers a resolution fact whose disposition this
#: plugin does not recognize: shown verbatim rather than hidden, because for a
#: *display* consumer an unrecognized value is information, where for the gate
#: it correctly counts as unresolved.
STATE_FIXED = "fixed"
STATE_WAIVED = "waived"
STATE_ACCEPTED = "accepted"
STATE_FILED = "filed"
#: A fix recorded by :data:`FIXED` rather than by a resolution fact. Kept
#: DISTINCT from :data:`STATE_FIXED`, which only a verify pass can produce: both
#: say the defect is gone, and only one of them says an independent reviewer
#: looked. Collapsing them would let the census claim a review that never ran.
STATE_FIXED_FREE = "fixed-unreviewed"
STATE_OPEN = "undispositioned"
#: An observation nobody answered. Deliberately NOT :data:`STATE_OPEN`: that
#: word names a debt, and the summary counts it as one. An observation is work
#: the record explicitly does not demand, so a census that reported unanswered
#: observations as undispositioned would rebuild, one layer down, the very
#: obligation the verify-mode demotion exists to remove.
STATE_NOTED = "noted"

_SEVERITY_ORDER = ("blocking", "warning", "note")


def _nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _severity_of(finding: dict) -> str:
    severity = finding.get("severity")
    return severity.strip().lower() if isinstance(severity, str) else ""


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def _target(fact: dict) -> "tuple[str, str] | None":
    """The ``(review_id, fid)`` a fact points at, or ``None`` when it points at
    nothing usable.

    ``read_facts`` validates the *envelope* — that ``body`` is an object — and
    never the body's shape. So a JSON-valid fact whose ``finding`` is a string
    or a list does reach these readers, and calling ``.get`` on it would raise
    an unattributed ``AttributeError`` straight out of the CLI, which is the one
    thing the error model forbids. One guarded reader for every site that joins
    on a finding: the precondition gets checked instead of assumed, and callers
    stop repeating the extraction.
    """
    body = fact.get("body")
    if not isinstance(body, dict):
        return None
    target = body.get("finding")
    if not isinstance(target, dict):
        return None
    review_id = target.get("review_id")
    fid = target.get("fid")
    if _nonempty(review_id) and _nonempty(fid):
        return review_id, fid
    return None


def disposition_facts(store: dict) -> list[dict]:
    """Every well-formed disposition fact, in store (append) order.

    The one filter both readers below share, so "well-formed" is decided in a
    single place rather than re-derived per query."""
    return [
        fact
        for fact in evidence.facts_of_kind(store, KIND)
        if _target(fact) is not None
    ]


def disposition_index(store: dict) -> dict[tuple[str, str], dict]:
    """``(review_id, fid)`` → the *newest* disposition fact for that finding.

    Last answer wins, by store order — which is append order, so a changed
    answer supersedes its predecessor without either being edited away."""
    return {_target(fact): fact for fact in disposition_facts(store)}


#: Prior-disposition entries a dispatch manifest will carry. A reviewer reads
#: this block before it reads the diff, so it competes with the review for
#: attention — and the whole point is to SHORTEN the review, not to prepend a
#: second document to it. Truncation is reported, never silent.
PRIOR_DISPOSITION_LIMIT = 15


def _unavailable(reason: str) -> dict:
    """An empty prior-dispositions block that SAYS it is empty for want of a
    readable store, rather than because nothing was dispositioned."""
    return {"entries": [], "matched": 0, "shown": 0, "truncated": 0, "unavailable": reason}


def prior_dispositions(
    store: dict,
    files_changed: "list[str] | None",
    *,
    scope: "str | None" = None,
    limit: int = PRIOR_DISPOSITION_LIMIT,
) -> dict:
    """The answers already given about findings in the files this review will
    look at — so a fresh review can decline to re-litigate them.

    Dispositions are facts, but nothing put them where a REVIEWER could see one:
    a cumulative dispatched after an ``--accept`` hands its reviewers a diff and
    no memory, and they find the same true thing again. Measured on one consumer
    branch, round 9 re-raised six of round 7's findings verbatim, several of
    them already accepted.

    **Scoped by work AND by cited file — the file alone is not a filter.** A
    store shared across every worktree accumulates hundreds of dispositions (652
    on this repo), and the first cut of this used the cited file alone. Measured
    on a live dispatch it carried 92 entries and the block was **91% of the
    manifest, ~5,700 tokens — 2.7× the protocol file it exists to shorten**,
    because a repo's hottest files are cited by nearly every finding it has ever
    recorded, so the filter was weakest exactly where reviews concentrate. A
    control that costs more attention than it saves is not a control.

    So ``scope`` (the build-plan scope the dispatch resolved) narrows it to
    answers given about *this body of work*, which is what "already answered"
    was ever supposed to mean — a disposition from another chunk that happens to
    touch the same hot file is not an answer about this diff. Reviews recorded
    without a scope match nothing rather than everything: an unscoped fact
    cannot claim to be about this work, and failing toward carrying LESS is
    right for an advisory block whose failure mode is drowning the review.
    Passing ``scope=None`` disables that half and falls back to files alone.

    The file test stays, because it is what makes the protocol instruction
    checkable against the evidence the reviewer holds: *not re-raised absent
    material change in its cited files*.

    A finding whose disposition exists but whose review fact no longer records
    it (a hand-edited store) is skipped: there is no title to show and nothing
    a reviewer could match against.

    Returns::

        {"entries": [{"review_id", "fid", "title", "severity", "action",
                      "reason", "backlog_id", "files"}, ...],
         "matched": int, "shown": int, "truncated": int,
         "unavailable"?: str}

    ``entries`` is newest-first, so a truncated block keeps the answers most
    likely to still be live.

    **A degraded store answers ``unavailable``, never an empty block.** The
    reviewer protocol reads a block with no ``unavailable`` as "nothing was
    dispositioned here", so returning ``entries: []`` for a store this reader
    could not fully see states a falsehood — and states it in the one case where
    re-litigating an accepted finding is most likely, because the answers are
    there and simply unreadable. Both degraded states are *returned* by
    ``evidence.read_facts`` rather than raised, so a caller's ``except`` cannot
    catch them; they are answered here, the same way ``record_disposition`` and
    the census reader refuse loudly on the identical two fields.
    """
    if store.get("status") == "error":
        return _unavailable(
            store.get("reason") or "the evidence store could not be read"
        )
    if store.get("schema_ahead"):
        return _unavailable(
            f"{len(store['schema_ahead'])} evidence record(s) carry a newer "
            "schema than this reader — the dispositions they record are "
            "invisible here. Update the plugin (/reload-plugins or restart "
            "Claude Code) to see them."
        )
    in_scope_files = {f for f in (files_changed or []) if isinstance(f, str) and f}
    findings = evidence.findings_index(store)
    # (review id) → the scope that review recorded, so the work filter costs one
    # pass rather than a lookup per disposition.
    review_scope = {
        fact.get("id"): (fact.get("body") or {}).get("scope")
        for fact in evidence.facts_of_kind(store, "review")
    }
    entries: list[dict] = []
    # Newest-last in store order; reverse so the newest answer leads and any
    # truncation drops the oldest. Re-disposition APPENDS rather than editing
    # (see the module docstring), so a finding can appear more than once here —
    # reversed order makes the first sighting the live answer and every later
    # one a superseded predecessor to skip. Showing both would hand a reviewer
    # two contradictory answers about one finding.
    seen: set[tuple[str, str]] = set()
    for fact in reversed(disposition_facts(store)):
        key = _target(fact)
        if key in seen:
            continue
        seen.add(key)
        finding = findings.get(key)
        if finding is None:
            # Observations are NOT joined here, deliberately. This block is
            # budgeted payload a reviewer reads before the diff — the docstring
            # above is the story of it costing 2.7x the protocol file it exists
            # to shorten — and an accepted observation is the lowest-value entry
            # it could carry: nothing gated on it, so a reviewer re-raising one
            # costs the builder a sentence, where a re-raised accepted FINDING
            # costs a round. Widening this is its own decision with its own
            # token bill, not a free consequence of observations becoming
            # recordable.
            continue
        if scope is not None and review_scope.get(key[0]) != scope:
            continue
        cited = [f for f in (finding.get("files") or []) if isinstance(f, str)]
        if in_scope_files and not (in_scope_files & set(cited)):
            continue
        body = fact.get("body") or {}
        entries.append(
            {
                "review_id": key[0],
                "fid": key[1],
                "title": evidence.finding_title(finding),
                "severity": finding.get("severity"),
                "action": body.get("action"),
                "reason": body.get("reason"),
                "backlog_id": body.get("backlog_id"),
                "files": cited,
            }
        )
    matched = len(entries)
    shown = entries[:limit]
    return {
        "entries": shown,
        "matched": matched,
        "shown": len(shown),
        "truncated": matched - len(shown),
    }


def disposition_history(store: dict, review_id: str, fid: str) -> list[dict]:
    """Every disposition recorded for one finding, oldest first."""
    return [
        fact for fact in disposition_facts(store) if _target(fact) == (review_id, fid)
    ]


def resolution_detail_index(store: dict) -> dict[tuple[str, str], str]:
    """``(review_id, fid)`` → the resolution fact's disposition string.

    Deliberately *not* ``coverage_algebra.resolution_index``: that one answers
    the gate's boolean question and must fail toward stricter, so it discards
    both which disposition resolved a finding and any value it does not
    recognize. A census has to show what was actually recorded."""
    index: dict[tuple[str, str], str] = {}
    for fact in evidence.facts_of_kind(store, "resolution"):
        key = _target(fact)
        disposition = (fact.get("body") or {}).get("disposition")
        if key is not None and _nonempty(disposition):
            index[key] = disposition.strip()
    return index


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


def record(
    project_dir: Path,
    review_id: str,
    fid: str,
    action: str,
    *,
    reason: str | None = None,
    backlog_id: str | None = None,
    owner_ruling: str | None = None,
    paths: "list[str] | None" = None,
) -> dict:
    """Append one disposition fact.

    ``paths`` belongs to :data:`FIXED` alone — the files the free fix touched,
    every one of which must be non-judgeable.

    Returns ``{"status": "recorded", "id", "action", "severity"}``,
    ``{"status": "unchanged", "id", ...}`` when the newest recorded answer is
    already identical, or ``{"status": "error", "reason"}``. Every refusal is
    a return value; nothing raises across this boundary.
    """
    if action not in ACTIONS:
        return {
            "status": "error",
            "reason": f"unknown action {action!r} (expected one of: "
            f"{', '.join(ACTIONS)})",
        }
    if not _nonempty(review_id) or not _nonempty(fid):
        return {
            "status": "error",
            "reason": "review id and finding id must both be non-empty",
        }
    if action == ACCEPT:
        if not _nonempty(reason):
            return {
                "status": "error",
                "reason": "an ACCEPT records why the finding will not be fixed "
                "— pass --accept <reason>",
            }
        if _nonempty(backlog_id):
            return {
                "status": "error",
                "reason": "an ACCEPT carries no backlog id — a finding is "
                "either accepted (no item) or filed (an item), never both",
            }
    if action == FILE:
        if not _nonempty(backlog_id):
            return {
                "status": "error",
                "reason": "a FILE records the backlog item that will carry the "
                "work — pass --file <backlog-id>",
            }
        if _nonempty(reason):
            return {
                "status": "error",
                "reason": "a FILE's reasoning belongs on the backlog item, not "
                "the fact — pass --file <backlog-id> alone",
            }
    clean_paths: list[str] = []
    if action == FIXED:
        if _nonempty(reason) or _nonempty(backlog_id):
            return {
                "status": "error",
                "reason": "a FIXED records the files the fix touched, not a "
                "reason or a backlog id — pass --fixed <path>[,<path>...] alone",
            }
        clean_paths = [p.strip() for p in (paths or []) if _nonempty(p)]
        if not clean_paths:
            return {
                "status": "error",
                "reason": "a FIXED names the files the fix touched — pass "
                "--fixed <path>[,<path>...]. Naming them is what makes the "
                "claim checkable, and the check is the whole warrant for "
                "recording a fix no reviewer saw",
            }
        from . import coverage_algebra  # noqa: PLC0415 — lazy; keeps the import graph flat

        judgeable = [p for p in clean_paths if coverage_algebra.is_judgeable_path(p)]
        if judgeable:
            return {
                "status": "error",
                "reason": "a FIXED is only for a fix that bought no review "
                "round, and these paths buy one: "
                f"{', '.join(judgeable)}. Run /prawduct:critic "
                "verify-resolutions — the round is already paid for by the "
                "edit, so recording it here would claim a review nobody ran",
            }
    elif paths:
        return {
            "status": "error",
            "reason": f"paths belong to a FIXED, not to a {action.upper()}",
        }

    store = evidence.read_facts(project_dir)
    if store["status"] == "error":
        return {"status": "error", "reason": store["reason"]}
    if store["schema_ahead"]:
        # Fail closed: a review fact written by a newer plugin is invisible to
        # this reader, so the join below could reject a finding that really
        # exists. Refusing is the only answer that cannot record a falsehood.
        return {
            "status": "error",
            "reason": f"{len(store['schema_ahead'])} evidence record(s) carry a "
            "newer schema than this reader — the finding join cannot be "
            "trusted. Update the plugin (/reload-plugins or restart Claude "
            "Code) before recording dispositions.",
        }

    # The id domain is findings PLUS observations — the widening
    # ``api-contract.md``'s additive-first norm sanctions, and the reason
    # ``--accept`` needed no new spelling. An observation is a
    # ``verify-resolutions`` demotion: it gates nothing, and before it had an
    # id the only ways to discharge one were to FIX it (moving the tree and
    # buying a round) or to say nothing (losing the reasoning). Findings are
    # tried first and the namespaces are disjoint (``R-1`` against ``O-1``), so
    # neither lookup can shadow the other.
    finding = evidence.findings_index(store).get((review_id, fid))
    if finding is None:
        finding = evidence.observations_index(store).get((review_id, fid))
    if finding is None:
        return {
            "status": "error",
            "reason": f"no finding or observation {fid!r} recorded for review "
            f"{review_id!r} — a disposition must reference a recorded one "
            "(prawduct-hook evidence list --kind review)",
        }

    # An observation carries no severity by construction, so every
    # severity-keyed guard below reads "" and stands down. That is correct
    # rather than incidental: those guards exist to stop a BLOCKING finding
    # being answered without an owner, and a BLOCKING item can never be an
    # observation — ``_validate_observations`` refuses the array outright.
    severity = _severity_of(finding)
    if severity == "blocking" and action == ACCEPT and not _nonempty(owner_ruling):
        return {
            "status": "error",
            "reason": f"{fid} is BLOCKING: gates compose on it, so it cannot be "
            "accepted without an explicit owner decision "
            "(--owner-ruling <text>). Fixing it and running "
            "/prawduct:critic verify-resolutions is the ordinary path.",
        }
    if severity == "blocking" and action == FIXED:
        # No owner-ruling escape here, unlike ACCEPT. A blocking finding on a
        # free interval is exactly the case `begin_review`'s free-interval
        # refusal deliberately does NOT refuse — its second conjunct keeps a
        # verify pass dispatchable precisely so these stay clearable. So the
        # real route exists, costs nothing extra, and produces the resolution
        # fact the gate reads; a disposition here would leave the census saying
        # "fixed" while the gate says "blocked", with nothing reconciling them.
        return {
            "status": "error",
            "reason": f"{fid} is BLOCKING: a blocking finding clears only "
            "through a resolution fact, so a free fix still takes "
            "/prawduct:critic verify-resolutions — which the free-interval "
            "refusal lets through for this exact case. Recording it here "
            "would say 'fixed' in the census while the gate stays blocked.",
        }

    body = {
        "finding": {"review_id": review_id, "fid": fid},
        "action": action,
        "reason": reason.strip() if _nonempty(reason) else None,
        "backlog_id": backlog_id.strip() if _nonempty(backlog_id) else None,
        "owner_ruling": owner_ruling.strip() if _nonempty(owner_ruling) else None,
        "paths": clean_paths or None,
    }

    history = disposition_history(store, review_id, fid)
    if history:
        newest = history[-1]["body"]
        if all(
            newest.get(key) == body.get(key)
            for key in ("action", "reason", "backlog_id", "owner_ruling", "paths")
        ):
            return {
                "status": "unchanged",
                "id": history[-1].get("id"),
                "action": action,
                "severity": severity,
            }

    # The id must not collide with one the store already holds: a colliding
    # append is silently discarded by (kind, id) dedupe while this function
    # still reports success — a lost answer that nothing surfaces. History
    # length alone cannot promise that, because a pruned or malformed
    # superseded line shortens the history and recycles a live id, and the
    # store's own growth advisory actively invites pruning. So step past every
    # id that exists rather than trusting the count.
    #
    # Two concurrent *different* answers still resolve to one recorded answer
    # (both compute the same free sequence; dedupe keeps the first), which is
    # the right outcome for a race — the append itself is atomic either way.
    existing_ids = {f.get("id") for f in evidence.facts_of_kind(store, KIND)}
    seq = len(history) + 1
    while f"disp:{review_id}:{fid}:{seq}" in existing_ids:
        seq += 1
    fact_id = f"disp:{review_id}:{fid}:{seq}"
    result = evidence.append_fact(project_dir, KIND, fact_id, body)
    if result["status"] != "appended":
        return {"status": "error", "reason": result["reason"]}
    return {
        "status": "recorded",
        "id": fact_id,
        "action": action,
        "severity": severity,
        "superseded": history[-1].get("id") if history else None,
    }


def auto_accept(
    project_dir: Path, review_ids: "list[str]", *, reason: str
) -> dict:
    """ACCEPT every still-open non-blocking finding across ``review_ids``.

    The round budget's other half: refusing a further round would otherwise
    leave the outstanding findings open forever, since the loop that would have
    dispositioned them is the loop that just ended. So exhaustion answers them
    — with the budget itself as the reason, which is a true and reviewable
    answer rather than a silent drop.

    **BLOCKING is untouchable, twice over.** This filters blocking findings out
    before calling :func:`record`, and :func:`record` independently refuses an
    ACCEPT on one without an owner ruling that no caller here supplies. Either
    guard alone would do it; both are here because a budget that could open a
    gate would be a way to *merge* unreviewed work, which is the one thing this
    plan may not build. Pinned by a regression test.

    Returns ``{"status": "swept", "accepted", "skipped_blocking", "failed":
    [{"review_id", "fid", "reason"}]}`` or ``{"status": "error", "reason"}``
    when the store cannot be read. Never raises.
    """
    store = evidence.read_facts(project_dir)
    if store["status"] == "error":
        return {"status": "error", "reason": store["reason"]}
    if store["schema_ahead"]:
        return {
            "status": "error",
            "reason": f"{len(store['schema_ahead'])} evidence record(s) carry a "
            "newer schema than this reader — the findings it would sweep are "
            "not all visible. Update the plugin (/reload-plugins or restart "
            "Claude Code).",
        }

    # Findings only — the sweep never touches observations. It exists because a
    # refused round would otherwise strand findings the loop still owed an
    # answer on; an observation is owed nothing, so sweeping one would mint a
    # fact recording a decision nobody made.
    wanted = set(review_ids)
    dispositions = disposition_index(store)
    resolutions = resolution_detail_index(store)
    accepted = 0
    skipped_blocking = 0
    failed: list[dict] = []
    for fact in evidence.facts_of_kind(store, "review"):
        rid = fact.get("id")
        if rid not in wanted:
            continue
        findings = (fact.get("body") or {}).get("findings")
        for finding in findings if isinstance(findings, list) else []:
            if not isinstance(finding, dict):
                continue
            fid = finding.get("fid")
            if not _nonempty(fid):
                continue
            key = (rid, fid)
            if key in dispositions or key in resolutions:
                continue
            if _severity_of(finding) == "blocking":
                skipped_blocking += 1
                continue
            result = record(project_dir, rid, fid, ACCEPT, reason=reason)
            if result["status"] == "error":
                failed.append(
                    {"review_id": rid, "fid": fid, "reason": result["reason"]}
                )
            else:
                accepted += 1
    return {
        "status": "swept",
        "accepted": accepted,
        "skipped_blocking": skipped_blocking,
        "failed": failed,
    }


# ---------------------------------------------------------------------------
# Census (derived view)
# ---------------------------------------------------------------------------


def census(
    store: dict,
    *,
    review_id: str | None = None,
    scope: str | None = None,
    review_ids: "list[str] | None" = None,
) -> dict:
    """Derive the disposition census.

    Returns ``{"status": "ok", "reviews": [...], "summary": {...}}`` or
    ``{"status": "error", "reason": ...}`` when an explicitly requested review
    or scope matches nothing — a renderer that silently prints an empty table
    for a typo'd id is worse than one that says so.

    ``review_ids`` renders an explicit SET, which is what a caller that has
    already computed which reviews it is talking about needs: selecting by scope
    when the set was derived some other way makes the rendered table and the
    caller's actual subject two different things.

    With no selector, the newest review fact is rendered.
    """
    review_facts = evidence.facts_of_kind(store, "review")
    if not review_facts:
        return {"status": "error", "reason": "no review facts recorded yet"}

    if review_id is not None:
        selected = [f for f in review_facts if f.get("id") == review_id]
        if not selected:
            return {
                "status": "error",
                "reason": f"no review fact {review_id!r} in the store",
            }
    elif review_ids is not None:
        wanted = set(review_ids)
        selected = [f for f in review_facts if f.get("id") in wanted]
        if not selected:
            return {
                "status": "error",
                "reason": f"none of the {len(wanted)} requested review id(s) is "
                "in the store",
            }
    elif scope is not None:
        selected = [
            f for f in review_facts if (f.get("body") or {}).get("scope") == scope
        ]
        if not selected:
            return {
                "status": "error",
                "reason": f"no review facts for scope {scope!r} in the store",
            }
    else:
        selected = [review_facts[-1]]

    dispositions = disposition_index(store)
    resolutions = resolution_detail_index(store)

    reviews = []
    for fact in selected:
        body = fact.get("body") or {}
        rid = fact.get("id")
        rows = []
        findings = body.get("findings")
        for finding in findings if isinstance(findings, list) else []:
            if not isinstance(finding, dict):
                continue
            fid = finding.get("fid")
            if not _nonempty(fid):
                continue
            rows.append(_row(rid, finding, dispositions, resolutions))
        observation_rows = []
        observations = body.get("observations")
        for observation in observations if isinstance(observations, list) else []:
            if not isinstance(observation, dict):
                continue
            oid = observation.get("oid")
            if not _nonempty(oid):
                continue
            observation_rows.append(_observation_row(rid, observation, dispositions))
        reviews.append(
            {
                "review_id": rid,
                "ts": fact.get("ts"),
                "mode": body.get("mode"),
                "scope": body.get("scope"),
                "chunk": body.get("chunk"),
                "rows": rows,
                # A SEPARATE list, never appended to ``rows``. Every consumer of
                # ``rows`` — the summary's severity tally, its undispositioned
                # count, the markdown table — asks questions that presuppose a
                # finding, and answering them over observations would report
                # debt nobody owes and severities nothing assigned.
                "observations": observation_rows,
            }
        )

    all_rows = [row for r in reviews for row in r["rows"]]
    all_observations = [row for r in reviews for row in r["observations"]]
    return {
        "status": "ok",
        "reviews": reviews,
        "summary": _summarize(all_rows, all_observations),
    }


def _row(
    review_id: str,
    finding: dict,
    dispositions: dict,
    resolutions: dict,
) -> dict:
    fid = finding["fid"]
    key = (review_id, fid)
    resolution = resolutions.get(key)
    disposition_fact = dispositions.get(key)
    disposition = (disposition_fact or {}).get("body") or {}

    if resolution in (STATE_FIXED, STATE_WAIVED):
        state = resolution
    elif resolution is not None:
        state = f"resolved-{resolution}"
    elif disposition.get("action") == ACCEPT:
        state = STATE_ACCEPTED
    elif disposition.get("action") == FILE:
        state = STATE_FILED
    elif disposition.get("action") == FIXED:
        state = STATE_FIXED_FREE
    else:
        state = STATE_OPEN

    return {
        "fid": fid,
        "severity": _severity_of(finding),
        "goal": finding.get("goal"),
        "title": evidence.finding_title(finding),
        "state": state,
        "reason": disposition.get("reason"),
        "backlog_id": disposition.get("backlog_id"),
        "owner_ruling": disposition.get("owner_ruling"),
        "paths": disposition.get("paths"),
        # A finding carrying both a resolution and a disposition has been
        # answered twice (accepted, then actually fixed — or the reverse).
        # Which answer is current is a judgement the renderer must not make
        # silently, so it counts them and says so.
        "conflict": bool(resolution is not None and disposition),
    }


def _observation_row(
    review_id: str, observation: dict, dispositions: dict
) -> dict:
    """One observation, with whatever answer the builder recorded against it.

    No resolution lookup: a resolution may only target a finding
    (``critic_consolidate`` checks the finding index alone before persisting
    one), so an observation can never carry one — and therefore can never carry
    the answered-twice conflict either.
    """
    oid = observation["oid"]
    disposition = (dispositions.get((review_id, oid)) or {}).get("body") or {}
    action = disposition.get("action")
    if action == ACCEPT:
        state = STATE_ACCEPTED
    elif action == FILE:
        state = STATE_FILED
    elif action == FIXED:
        state = STATE_FIXED_FREE
    else:
        state = STATE_NOTED

    return {
        "oid": oid,
        "goal": observation.get("goal"),
        "title": evidence.finding_title(observation),
        "state": state,
        "reason": disposition.get("reason"),
        "backlog_id": disposition.get("backlog_id"),
        "paths": disposition.get("paths"),
    }


def _summarize(rows: list[dict], observations: "list[dict] | None" = None) -> dict:
    by_severity: dict[str, int] = {}
    by_state: dict[str, int] = {}
    for row in rows:
        by_severity[row["severity"]] = by_severity.get(row["severity"], 0) + 1
        by_state[row["state"]] = by_state.get(row["state"], 0) + 1
    return {
        "findings": len(rows),
        "by_severity": by_severity,
        "by_state": by_state,
        # The gap `review-cycle.md`'s "severity does not exempt" rule asserts
        # but which nothing measured before this renderer existed.
        "undispositioned": by_state.get(STATE_OPEN, 0),
        "owner_ruled": sum(1 for r in rows if _nonempty(r.get("owner_ruling"))),
        "conflicts": sum(1 for r in rows if r["conflict"]),
        # Reported beside the findings and never mixed into them. The pair is
        # the demotion control's yield: how much a verify pass declined to
        # raise, and how much of that the builder went on to answer. Before the
        # observations reached the fact body the first number could only be
        # asserted by the reviewer about its own output.
        "observations": len(observations or []),
        "observations_answered": sum(
            1 for o in (observations or []) if o["state"] != STATE_NOTED
        ),
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_markdown(report: dict) -> str:
    """The census as markdown — the form that lands in a change-log entry or a
    PR body, which is why it is a table and not a paragraph."""
    lines: list[str] = []
    for review in report["reviews"]:
        header = f"**{review['review_id']}**"
        meta = [
            part
            for part in (
                review.get("scope") and f"scope `{review['scope']}`",
                review.get("chunk") and f"chunk {review['chunk']}",
                review.get("ts"),
            )
            if part
        ]
        if meta:
            header += " — " + ", ".join(meta)
        lines.append(header)
        lines.append("")
        if not review["rows"]:
            lines.append("_No findings._")
            lines.append("")
            # Not `continue`-ing past the observations: a verify pass that
            # demoted everything it saw records exactly zero findings, so the
            # clean-review branch is the ONE this block most needs to reach.
            lines.extend(_observation_block(review["observations"]))
            continue
        lines.append("| Finding | Severity | State | Detail |")
        lines.append("|---|---|---|---|")
        for row in review["rows"]:
            lines.append(
                f"| {row['fid']} | {row['severity'] or '-'} | {_state_label(row)} "
                f"| {_detail(row)} |"
            )
        lines.append("")
        lines.extend(_observation_block(review["observations"]))

    summary = report["summary"]
    # Known severities in their ratified order, then anything else — a census
    # whose parenthetical does not sum to its own total is the exact class of
    # defect this renderer exists to retire.
    counts = summary["by_severity"]
    ordered = [name for name in _SEVERITY_ORDER if counts.get(name)]
    ordered += sorted(k for k in counts if k not in _SEVERITY_ORDER and counts[k])
    severity = ", ".join(f"{counts[name]} {name or 'unrated'}" for name in ordered)
    if not summary["findings"]:
        # A clean pass records an empty findings array, so this is an ordinary
        # case rather than an edge one — and the severity and state clauses both
        # collapse to nothing, which used to leave a dangling "— ." in text
        # written to be pasted into a change-log entry.
        lines.append("**No findings** — a clean pass.")
        # The observation tally rides this branch too. A `verify-resolutions`
        # pass that demoted everything it saw records exactly ZERO findings, so
        # the clean-pass early return is the case where observations are most
        # likely to exist — returning without them would print "a clean pass"
        # over a review that had things to say.
        lines.extend(_observation_summary(summary))
        return "\n".join(lines)

    state = ", ".join(
        f"{name}: {n}" for name, n in sorted(summary["by_state"].items())
    )
    noun = "finding" if summary["findings"] == 1 else "findings"
    lines.append(f"**{summary['findings']} {noun}** ({severity}) — {state}.")
    if summary["undispositioned"]:
        lines.append(
            f"**{summary['undispositioned']} undispositioned** — every finding "
            "takes an ACCEPT, FIX or FILE regardless of severity "
            "(`review-cycle.md`)."
        )
    if summary["conflicts"]:
        lines.append(
            f"**{summary['conflicts']} answered twice** — recorded as both "
            "resolved and dispositioned; check which answer is current."
        )
    lines.extend(_observation_summary(summary))
    return "\n".join(lines)


def _observation_summary(summary: dict) -> list[str]:
    """The demotion tally, stated as a separate sentence from the findings one.

    Separate because the two report different kinds of thing, and a reader who
    reads them as one total concludes the review found more than it did — the
    census's oldest failure mode. The answered count is stated without comment:
    an unanswered observation is not a gap, and prose nudging toward answering
    them would reintroduce the obligation the demotion removed.
    """
    total = summary.get("observations") or 0
    if not total:
        return []
    noun = "observation" if total == 1 else "observations"
    return [
        f"**{total} {noun} demoted** — {summary['observations_answered']} "
        "answered. An observation gates nothing; answering one is optional."
    ]


def _observation_block(observations: list[dict]) -> list[str]:
    """The observations a review demoted, as their own table — or nothing.

    Rendered only when there are some: a heading over an empty table trains its
    reader to skip the section, and most reviews demote nothing because only
    ``verify-resolutions`` demotes at all. No severity column, because an
    observation has no severity to show.
    """
    if not observations:
        return []
    lines = ["_Observations — read, not owed. Answering one is optional._", ""]
    lines.append("| Observation | State | Detail |")
    lines.append("|---|---|---|")
    for row in observations:
        lines.append(f"| {row['oid']} | {row['state']} | {_detail(row)} |")
    lines.append("")
    return lines


def _state_label(row: dict) -> str:
    if row["state"] == STATE_ACCEPTED and _nonempty(row.get("owner_ruling")):
        return "accepted (owner ruling)"
    return row["state"]


def _detail(row: dict) -> str:
    """The cell shared by both tables — every field it reads is one an
    observation row may also carry, or one ``.get`` tolerates."""
    parts = []
    if _nonempty(row.get("backlog_id")):
        parts.append(f"`{row['backlog_id']}`")
    if row.get("paths"):
        parts.append("fixed in " + ", ".join(f"`{p}`" for p in row["paths"]))
    if _nonempty(row.get("reason")):
        parts.append(row["reason"])
    if _nonempty(row.get("owner_ruling")):
        parts.append(f"owner ruling: {row['owner_ruling']}")
    if not parts:
        parts.append(row.get("title") or "-")
    # A cell cannot carry a raw pipe or newline without breaking the table.
    return " — ".join(parts).replace("|", "\\|").replace("\n", " ")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_RECORD_USAGE = (
    # `<fid|oid>`, not `<fid>`: the id domain is findings PLUS observations
    # (see `record`), and this string is what a REFUSED invocation prints —
    # exactly the moment a builder needs to know an observation id is legal.
    "Usage: prawduct-hook disposition <review-id> <fid|oid> "
    "{--accept <reason>|--file <backlog-id>|--fixed <path>[,<path>...]} "
    "[--owner-ruling <text>]"
)
_RENDER_USAGE = (
    "Usage: prawduct-hook render-dispositions "
    "[--review <id>|--scope <s>] [--json]"
)


def disposition_cmd(project_dir: Path, argv: list[str]) -> int:
    """Record one disposition. Exit 0 recorded/unchanged, 1 refused
    (fail-closed writer), 2 usage error — ``api-contract.md``'s scheme."""
    positional: list[str] = []
    action: str | None = None
    reason: str | None = None
    backlog_id: str | None = None
    owner_ruling: str | None = None
    paths: list[str] | None = None

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("--accept", "--file", "--fixed", "--owner-ruling"):
            if i + 1 >= len(argv):
                print(f"{_RECORD_USAGE}\n{arg} needs a value", file=sys.stderr)
                return 2
            value = argv[i + 1]
            if arg == "--owner-ruling":
                owner_ruling = value
            elif action is not None:
                print(
                    f"{_RECORD_USAGE}\na finding takes one disposition, not both",
                    file=sys.stderr,
                )
                return 2
            elif arg == "--accept":
                action, reason = ACCEPT, value
            elif arg == "--fixed":
                action, paths = FIXED, [p for p in value.split(",") if p.strip()]
            else:
                action, backlog_id = FILE, value
            i += 2
        elif arg.startswith("--"):
            print(f"{_RECORD_USAGE}\nunknown flag {arg}", file=sys.stderr)
            return 2
        else:
            positional.append(arg)
            i += 1

    if len(positional) != 2 or action is None:
        print(_RECORD_USAGE, file=sys.stderr)
        return 2

    result = record(
        project_dir,
        positional[0],
        positional[1],
        action,
        reason=reason,
        backlog_id=backlog_id,
        owner_ruling=owner_ruling,
        paths=paths,
    )
    if result["status"] == "error":
        print(f"disposition: {result['reason']}", file=sys.stderr)
        return 1
    review_id, fid = positional
    if result["status"] == "unchanged":
        print(f"disposition: {fid} of {review_id} already {action.upper()} — no-op")
        return 0
    print(f"disposition: {fid} of {review_id} recorded {action.upper()}")
    if result.get("superseded"):
        print(f"  supersedes {result['superseded']}")
    if result["severity"] == "blocking":
        # An owner ruling records the decision; it does not satisfy the gate.
        print(
            "NOTE: this finding is BLOCKING — the gate stays blocked until it is "
            "cleared. A /prawduct:critic verify-resolutions pass recording a "
            "resolution fact is the ordinary route; if the gate reports the "
            "finding as superseded, only a spanning /prawduct:critic cumulative "
            "clears it.",
            file=sys.stderr,
        )
    return 0


def render_dispositions_cmd(project_dir: Path, argv: list[str]) -> int:
    """Render the census. Exit 0 rendered, 1 nothing to render / store
    unreadable, 2 usage error."""
    review_id: str | None = None
    scope: str | None = None
    as_json = False

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--json":
            as_json = True
            i += 1
        elif arg in ("--review", "--scope"):
            if i + 1 >= len(argv):
                print(f"{_RENDER_USAGE}\n{arg} needs a value", file=sys.stderr)
                return 2
            if review_id is not None or scope is not None:
                print(
                    f"{_RENDER_USAGE}\n--review and --scope are exclusive",
                    file=sys.stderr,
                )
                return 2
            if arg == "--review":
                review_id = argv[i + 1]
            else:
                scope = argv[i + 1]
            i += 2
        else:
            print(f"{_RENDER_USAGE}\nunknown argument {arg}", file=sys.stderr)
            return 2

    store = evidence.read_facts(project_dir)
    if store["status"] == "error":
        print(f"render-dispositions: {store['reason']}", file=sys.stderr)
        return 1
    if store["schema_ahead"]:
        print(
            f"render-dispositions: {len(store['schema_ahead'])} evidence "
            "record(s) carry a newer schema than this reader — the census "
            "would be incomplete. Update the plugin (/reload-plugins or "
            "restart Claude Code).",
            file=sys.stderr,
        )
        return 1

    report = census(store, review_id=review_id, scope=scope)
    if report["status"] == "error":
        print(f"render-dispositions: {report['reason']}", file=sys.stderr)
        return 1

    if as_json:
        print(
            json.dumps(
                {"schema_version": REPORT_SCHEMA_VERSION, **report},
                indent=2,
            )
        )
    else:
        print(render_markdown(report))
    return 0
