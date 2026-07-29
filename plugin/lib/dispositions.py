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
is ``action`` — ``accept`` or ``file``.

**A disposition can never weaken a gate.** ``coverage_algebra`` filters
``kind != "resolution"`` before reading any body, so a BLOCKING finding stays
blocking until a verify pass records a real resolution. That is the
load-bearing safety property here, and it is pinned by a regression test
rather than left resting on the filter staying where it is.

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
ACTIONS = (ACCEPT, FILE)

#: The ``--json`` shape is a machine contract; key changes bump this.
REPORT_SCHEMA_VERSION = 1

#: Display states a census row can carry, in the order the summary reports
#: them. ``resolved-*`` covers a resolution fact whose disposition this
#: plugin does not recognize: shown verbatim rather than hidden, because for a
#: *display* consumer an unrecognized value is information, where for the gate
#: it correctly counts as unresolved.
STATE_FIXED = "fixed"
STATE_WAIVED = "waived"
STATE_ACCEPTED = "accepted"
STATE_FILED = "filed"
STATE_OPEN = "undispositioned"

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
    """Every well-formed disposition fact, in store (append) order."""
    return [
        fact
        for fact in evidence.facts_of_kind(store, KIND)
        if _target(fact) is not None
    ]


def disposition_index(store: dict) -> dict[tuple[str, str], dict]:
    """``(review_id, fid)`` → the *newest* disposition fact for that finding.

    Last answer wins, by store order — which is append order, so a changed
    answer supersedes its predecessor without either being edited away."""
    index: dict[tuple[str, str], dict] = {}
    for fact in evidence.facts_of_kind(store, KIND):
        key = _target(fact)
        if key is not None:
            index[key] = fact
    return index


def disposition_history(store: dict, review_id: str, fid: str) -> list[dict]:
    """Every disposition recorded for one finding, oldest first."""
    return [
        fact
        for fact in evidence.facts_of_kind(store, KIND)
        if _target(fact) == (review_id, fid)
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
) -> dict:
    """Append one disposition fact.

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

    findings = evidence.findings_index(store)
    finding = findings.get((review_id, fid))
    if finding is None:
        return {
            "status": "error",
            "reason": f"no finding {fid!r} recorded for review {review_id!r} — "
            "a disposition must reference a recorded finding "
            "(prawduct-hook evidence list --kind review)",
        }

    severity = _severity_of(finding)
    if severity == "blocking" and action == ACCEPT and not _nonempty(owner_ruling):
        return {
            "status": "error",
            "reason": f"{fid} is BLOCKING: gates compose on it, so it cannot be "
            "accepted without an explicit owner decision "
            "(--owner-ruling <text>). Fixing it and running "
            "/prawduct:critic verify-resolutions is the ordinary path.",
        }

    body = {
        "finding": {"review_id": review_id, "fid": fid},
        "action": action,
        "reason": reason.strip() if _nonempty(reason) else None,
        "backlog_id": backlog_id.strip() if _nonempty(backlog_id) else None,
        "owner_ruling": owner_ruling.strip() if _nonempty(owner_ruling) else None,
    }

    history = disposition_history(store, review_id, fid)
    if history:
        newest = history[-1]["body"]
        if all(
            newest.get(key) == body.get(key)
            for key in ("action", "reason", "backlog_id", "owner_ruling")
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


# ---------------------------------------------------------------------------
# Census (derived view)
# ---------------------------------------------------------------------------


def census(
    store: dict, *, review_id: str | None = None, scope: str | None = None
) -> dict:
    """Derive the disposition census.

    Returns ``{"status": "ok", "reviews": [...], "summary": {...}}`` or
    ``{"status": "error", "reason": ...}`` when an explicitly requested review
    or scope matches nothing — a renderer that silently prints an empty table
    for a typo'd id is worse than one that says so.

    With neither selector, the newest review fact is rendered.
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
        reviews.append(
            {
                "review_id": rid,
                "ts": fact.get("ts"),
                "mode": body.get("mode"),
                "scope": body.get("scope"),
                "chunk": body.get("chunk"),
                "rows": rows,
            }
        )

    all_rows = [row for r in reviews for row in r["rows"]]
    return {
        "status": "ok",
        "reviews": reviews,
        "summary": _summarize(all_rows),
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
    else:
        state = STATE_OPEN

    return {
        "fid": fid,
        "severity": _severity_of(finding),
        "goal": finding.get("goal"),
        "title": finding.get("title"),
        "state": state,
        "reason": disposition.get("reason"),
        "backlog_id": disposition.get("backlog_id"),
        "owner_ruling": disposition.get("owner_ruling"),
        # A finding carrying both a resolution and a disposition has been
        # answered twice (accepted, then actually fixed — or the reverse).
        # Which answer is current is a judgement the renderer must not make
        # silently, so it counts them and says so.
        "conflict": bool(resolution is not None and disposition),
    }


def _summarize(rows: list[dict]) -> dict:
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
            continue
        lines.append("| Finding | Severity | State | Detail |")
        lines.append("|---|---|---|---|")
        for row in review["rows"]:
            lines.append(
                f"| {row['fid']} | {row['severity'] or '-'} | {_state_label(row)} "
                f"| {_detail(row)} |"
            )
        lines.append("")

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
    return "\n".join(lines)


def _state_label(row: dict) -> str:
    if row["state"] == STATE_ACCEPTED and _nonempty(row.get("owner_ruling")):
        return "accepted (owner ruling)"
    return row["state"]


def _detail(row: dict) -> str:
    parts = []
    if _nonempty(row.get("backlog_id")):
        parts.append(f"`{row['backlog_id']}`")
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
    "Usage: prawduct-hook disposition <review-id> <fid> "
    "{--accept <reason>|--file <backlog-id>} [--owner-ruling <text>]"
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

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("--accept", "--file", "--owner-ruling"):
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
            "NOTE: this finding is BLOCKING — the gate stays blocked until a "
            "/prawduct:critic verify-resolutions pass records a resolution fact.",
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
