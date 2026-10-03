"""``prawduct-hook stats`` — what governance cost and what it caught, per plugin version.

``review-stats`` answers "what does a review cost, by mode and model?" from the
per-worktree ledger. This report answers the question a plugin release has to
answer — *did version N cost more or protect more than N-1?* — so it reads the
clone-shared evidence store, where every fact carries the plugin version that
wrote it (``actor.plugin``) and nothing is lost when a worktree is deleted.

Every number is bucketed by plugin ``major.minor`` and defined in
``docs/governance-telemetry.md`` (§ ``prawduct-hook stats``), which is the one
home of the definitions; the code below implements them and does not restate
them.

Cost: review rounds per scope, measured review time (a self-estimate is never
summed as a measurement), empty verify-resolutions rounds, re-reviews of an
interval or tree already reviewed, Stop-hook blocks, and guard refusals.
Benefit: findings raised and what became of them, by the rule
``render-dispositions`` uses; blocking and warning findings fixed per scope;
blocking fixed by goal; red recorded suite runs; and base-advance transfer
grants, which share the guard-refusal sink but are passes, not refusals.

Informational only: no gate reads it.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import dispositions, evidence, gitstate
from .review_dispatch import fact_interval_seconds
from .timewindow import in_window, is_usable_bound

REPORT_SCHEMA_VERSION = 1

#: Severities whose findings a review is expected to act on.
_ACTIONABLE = ("blocking", "warning")
_SEVERITIES = ("blocking", "warning", "note")
#: How each state :func:`dispositions.finding_state` can return is reported.
#: A state it adds later lands in ``other`` rather than vanishing.
_OUTCOME_OF_STATE = {
    dispositions.STATE_FIXED: "fixed",
    dispositions.STATE_FIXED_FREE: "fixed_unreviewed",
    dispositions.STATE_FILED: "filed",
    dispositions.STATE_ACCEPTED: "accepted",
    dispositions.STATE_WAIVED: "waived",
    dispositions.STATE_OPEN: "undispositioned",
}
_OUTCOMES = (*_OUTCOME_OF_STATE.values(), "other")
#: Outcomes that say the defect is gone. ``fixed_unreviewed`` counts: it is a
#: fix nobody re-reviewed, not a fix that did not happen.
_FIXED = ("fixed", "fixed_unreviewed")
#: One gate blocking this many times in one session is reported as a loop.
LOOP_THRESHOLD = 3


def version_bucket(plugin) -> str:
    """``3.7.1-dev.2`` → ``3.7``; anything unreadable → ``unknown``."""
    if not isinstance(plugin, str) or not plugin.strip():
        return "unknown"
    parts = plugin.strip().split(".")
    if len(parts) < 2 or not parts[0].isdigit():
        return "unknown"
    minor = "".join(ch for ch in parts[1] if ch.isdigit())
    return f"{parts[0]}.{minor}" if minor else "unknown"


def _bucket(fact: dict) -> str:
    actor = fact.get("actor")
    return version_bucket(actor.get("plugin") if isinstance(actor, dict) else None)


def _body(fact: dict) -> dict:
    body = fact.get("body")
    return body if isinstance(body, dict) else {}


def _mode(body: dict) -> str:
    mode = body.get("mode")
    return mode.split()[0] if isinstance(mode, str) and mode.split() else "unknown"


def _scope(fact: dict) -> str:
    scope = _body(fact).get("scope")
    if isinstance(scope, str) and scope:
        return scope
    actor = fact.get("actor")
    branch = actor.get("branch") if isinstance(actor, dict) else None
    return f"branch:{branch}" if isinstance(branch, str) and branch else "unscoped"


def _population(values: list) -> dict:
    if not values:
        return {"n": 0, "median": None, "p90": None, "max": None}
    ordered = sorted(values)
    return {
        "n": len(ordered),
        "median": statistics.median(ordered),
        # Nearest rank: the smallest value at or above 90% of the population.
        "p90": ordered[math.ceil(0.9 * len(ordered)) - 1],
        "max": ordered[-1],
    }


def _rate(numerator, denominator):
    return round(numerator / denominator, 3) if denominator else None


def finding_outcome(store: dict):
    """A function ``(review_id, fid)`` → this report's outcome name, using
    :func:`dispositions.finding_state`, the rule ``render-dispositions`` uses,
    so the two reports never disagree about one finding."""
    disposition_index = dispositions.disposition_index(store)
    resolution_index = dispositions.resolution_detail_index(store)

    def outcome(key) -> str:
        state = dispositions.finding_state(key, disposition_index, resolution_index)
        return _OUTCOME_OF_STATE.get(state, "other")

    return outcome


def _new_bucket() -> dict:
    return {
        "sessions": set(),
        "reviews": Counter(),
        "rounds": Counter(),  # scope -> reviews
        "measured": [],
        "measured_by_scope": defaultdict(float),
        "estimated": [],
        "verify_rounds": 0,
        "empty_verify_rounds": 0,
        "exact_rereviews": 0,
        "same_head_rereviews": 0,
        "findings": {s: Counter() for s in _SEVERITIES},
        "blocking_fixed_by_goal": Counter(),
        "stops": [],  # (stop id, session) per blocking-gate fact
        "blocks_by_gate": Counter(),
        "blocks_by_session": defaultdict(Counter),
        "guard_refusals": [],  # (guard, session)
        "transfer_grants": [],  # (guard, session)
        "test_runs": 0,
        "red_test_runs": 0,
    }


def aggregate(facts: list[dict], since=None, until=None, bucket=None) -> dict:
    """The per-version report body over ``facts`` (one ``read_facts`` result).

    ``bucket`` maps a fact to its bucket key, by default its plugin
    ``major.minor``. Pure: no I/O, so every definition is testable against a
    fact list."""
    bucket_of = bucket or _bucket
    store = {"facts": facts}
    outcome = finding_outcome(store)
    verified_by = Counter(
        v for v in (_body(f).get("verified_by") for f in facts if f.get("kind") == "resolution")
        if isinstance(v, str)
    )
    buckets: dict = defaultdict(_new_bucket)
    seen_intervals: set = set()
    seen_heads: set = set()
    # Store order is append order, so "already reviewed" means earlier in it.
    for fact in facts:
        if not in_window(fact.get("ts"), since, until):
            # Out of the window but still history: a review inside the window
            # of a tree reviewed before it is a re-review, as finding outcomes
            # are read from every fact whatever its date.
            if fact.get("kind") == "review":
                _remember_interval(_body(fact), seen_intervals, seen_heads)
            continue
        kind, body, b = fact.get("kind"), _body(fact), buckets[bucket_of(fact)]
        session = _session(fact)
        if kind == "session-start":
            if session:
                b["sessions"].add(session)
        elif kind == "review":
            _add_review(b, fact, body, outcome, verified_by, seen_intervals, seen_heads)
        elif kind == "guard-refusal":
            guard = body.get("guard")
            if isinstance(guard, str) and guard.startswith(evidence.STOP_GATE_PREFIX):
                gate = guard[len(evidence.STOP_GATE_PREFIX):]
                stop = body.get("stop") if isinstance(body.get("stop"), str) else fact.get("id")
                b["stops"].append((stop, session))
                b["blocks_by_gate"][gate] += 1
                b["blocks_by_session"][session][gate] += 1
            elif guard == evidence.TRANSFER_GRANT_GUARD:
                b["transfer_grants"].append((guard, session))
            elif isinstance(guard, str) and guard:
                b["guard_refusals"].append((guard, session))
        elif kind == "test-run":
            b["test_runs"] += 1
            failed = body.get("failed")
            if isinstance(failed, int) and failed > 0:
                b["red_test_runs"] += 1
    return {version: _finish(b) for version, b in sorted(buckets.items())}


def _session(fact: dict) -> "str | None":
    actor = fact.get("actor")
    session = actor.get("session") if isinstance(actor, dict) else None
    return session if isinstance(session, str) and session else None


def _interval(body: dict) -> "tuple[str, str] | None":
    base, head = body.get("base_tree"), body.get("head_tree")
    return (base, head) if isinstance(base, str) and isinstance(head, str) and base and head else None


def _remember_interval(body: dict, seen_intervals: set, seen_heads: set) -> None:
    interval = _interval(body)
    if interval:
        seen_intervals.add(interval)
        seen_heads.add(interval[1])


def _add_review(b, fact, body, outcome, verified_by, seen_intervals, seen_heads):
    mode = _mode(body)
    b["reviews"][mode] += 1
    scope = _scope(fact)
    b["rounds"][scope] += 1
    measured = fact_interval_seconds(fact)
    if measured is not None:
        b["measured"].append(measured)
        b["measured_by_scope"][scope] += measured
    elif isinstance(body.get("duration_seconds"), (int, float)):
        b["estimated"].append(body["duration_seconds"])
    findings = [f for f in body.get("findings") or [] if isinstance(f, dict)]
    if mode == "verify-resolutions":
        b["verify_rounds"] += 1
        raised = any(f.get("severity") in _ACTIONABLE for f in findings)
        if not raised and not verified_by.get(fact.get("id")):
            b["empty_verify_rounds"] += 1
    interval = _interval(body)
    if interval:
        if interval in seen_intervals:
            b["exact_rereviews"] += 1
        if interval[1] in seen_heads:
            b["same_head_rereviews"] += 1
        _remember_interval(body, seen_intervals, seen_heads)
    for finding in findings:
        severity = finding.get("severity")
        if severity not in b["findings"]:
            continue
        fid = finding.get("fid")
        result = outcome((fact.get("id"), fid)) if isinstance(fid, str) else "other"
        b["findings"][severity]["raised"] += 1
        b["findings"][severity][result] += 1
        if severity == "blocking" and result in _FIXED:
            b["blocking_fixed_by_goal"][str(finding.get("goal") or "unknown")] += 1


def _per_session(events: list, sessions: set):
    """Events per session, over sessions that recorded their start only: an
    event from a session with no ``session-start`` fact (one older than the
    fact, or whose append failed) has no denominator, and counting it against
    the sessions that do would inflate the rate."""
    if not sessions:
        return None
    return _rate(sum(1 for _, session in events if session in sessions), len(sessions))


def _finish(b: dict) -> dict:
    reviews = sum(b["reviews"].values())
    scopes = len(b["rounds"])
    sessions = b["sessions"]
    stops = list(dict.fromkeys(b["stops"]))  # one entry per blocked Stop
    findings = {}
    for severity, c in b["findings"].items():
        acted = sum(c[o] for o in _FIXED) + c["filed"]
        answered = acted + c["accepted"] + c["waived"]
        findings[severity] = {
            "raised": c["raised"],
            **{o: c[o] for o in _OUTCOMES},
            # The rate's denominator, exported so a reader that floors on it
            # (the contribution report) uses this count rather than its own.
            "answered": answered,
            "acted_on_rate": _rate(acted, answered),
        }
    loops = sum(
        1
        for gates in b["blocks_by_session"].values()
        for count in gates.values()
        if count >= LOOP_THRESHOLD
    )
    refusals = Counter(guard for guard, _ in b["guard_refusals"])
    return {
        "sessions": len(sessions),
        "scopes": scopes,
        "reviews": {"total": reviews, "by_mode": dict(sorted(b["reviews"].items()))},
        "rounds_per_scope": _population(list(b["rounds"].values())),
        "review_seconds": {
            "measured": {
                "reviews": len(b["measured"]),
                "total": round(sum(b["measured"])),
                "median": _population(b["measured"])["median"],
                "per_scope": _population(list(b["measured_by_scope"].values())),
            },
            "estimated": {
                "reviews": len(b["estimated"]),
                "total": round(sum(b["estimated"])),
            },
        },
        "verify_rounds": {"total": b["verify_rounds"], "empty": b["empty_verify_rounds"]},
        "rereviews": {
            "same_interval": b["exact_rereviews"],
            "same_head_tree": b["same_head_rereviews"],
        },
        "stop_blocks": {
            "blocks": sum(b["blocks_by_gate"].values()),
            "stops_blocked": len(stops),
            "stops_blocked_per_session": _per_session(stops, sessions),
            "by_gate": dict(b["blocks_by_gate"].most_common()),
            "loops": loops,
        },
        "guard_refusals": {
            "total": len(b["guard_refusals"]),
            "per_session": _per_session(b["guard_refusals"], sessions),
            "by_guard": dict(refusals.most_common()),
        },
        "transfer_grants": {
            "total": len(b["transfer_grants"]),
            "per_session": _per_session(b["transfer_grants"], sessions),
        },
        "findings": findings,
        "blocking_fixed_by_goal": dict(b["blocking_fixed_by_goal"].most_common()),
        "blocking_fixed_per_scope": _rate(
            sum(b["findings"]["blocking"][o] for o in _FIXED), scopes
        ),
        "warnings_fixed_per_scope": _rate(
            sum(b["findings"]["warning"][o] for o in _FIXED), scopes
        ),
        "test_runs": {"total": b["test_runs"], "red": b["red_test_runs"]},
    }


def _fmt(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def _minutes(seconds) -> str:
    return "-" if seconds is None else f"{seconds / 60:.1f}m"


def render_human(report: dict) -> str:
    lines = [f"prawduct stats — {report['project']}"]
    window = report["window"]
    if window["since"] or window["until"]:
        lines.append(f"window: {window['since'] or 'start'} → {window['until'] or 'now'}")
    for version, v in report["by_version"].items():
        f = v["findings"]
        sb = v["stop_blocks"]
        measured = v["review_seconds"]["measured"]
        lines += [
            "",
            f"plugin {version}: {v['sessions']} session(s), {v['scopes']} scope(s), "
            f"{v['reviews']['total']} review(s)",
            "  cost",
            f"    rounds per scope   median {_fmt(v['rounds_per_scope']['median'])}, "
            f"p90 {_fmt(v['rounds_per_scope']['p90'])}",
            f"    review time        measured on {measured['reviews']} review(s): "
            f"median {_minutes(measured['median'])}, per scope median "
            f"{_minutes(measured['per_scope']['median'])}; "
            f"{v['review_seconds']['estimated']['reviews']} more carry only a self-estimate",
            f"    empty verify rounds {v['verify_rounds']['empty']} of {v['verify_rounds']['total']}",
            f"    re-reviews         {v['rereviews']['same_interval']} same interval, "
            f"{v['rereviews']['same_head_tree']} same head tree",
            f"    stops blocked      {sb['stops_blocked']} "
            f"({_fmt(sb['stops_blocked_per_session'])} per recorded session), loops {sb['loops']}"
            + (
                " — " + ", ".join(f"{g} {n}" for g, n in sb["by_gate"].items())
                if sb["by_gate"] else ""
            ),
            f"    guard refusals     {v['guard_refusals']['total']} "
            f"({_fmt(v['guard_refusals']['per_session'])} per recorded session)",
            "  benefit",
        ]
        for severity in _SEVERITIES:
            s = f[severity]
            lines.append(
                f"    {severity:<9} raised {s['raised']}: fixed {s['fixed']} "
                f"(+{s['fixed_unreviewed']} unreviewed), filed {s['filed']}, "
                f"accepted {s['accepted']}, waived {s['waived']}, "
                f"undispositioned {s['undispositioned']} (acted on {_fmt(s['acted_on_rate'])})"
            )
        lines.append(
            f"    fixed per scope    blocking {_fmt(v['blocking_fixed_per_scope'])}, "
            f"warning {_fmt(v['warnings_fixed_per_scope'])}; "
            f"red suite runs {v['test_runs']['red']} of {v['test_runs']['total']}"
        )
        grants = v["transfer_grants"]
        lines.append(
            f"    transfer grants    {grants['total']} "
            f"({_fmt(grants['per_session'])} per recorded session), each a review round saved"
        )
    if not report["by_version"]:
        lines.append("no governance history in this clone's evidence store")
    if report.get("schema_ahead"):
        lines.append(
            f"{report['schema_ahead']} fact(s) written by a newer plugin are not counted; "
            "run a newer prawduct to include them"
        )
    return "\n".join(lines)


def stats_cmd(project_dir: Path, argv: list[str]) -> int:
    """Body of ``prawduct-hook stats``. Exit 0 with a report (an empty store
    is an answer); exit 1 on bad arguments or a store that cannot be read."""
    usage = "usage: stats [--json] [--since <stamp>] [--until <stamp>]"
    as_json = False
    since = until = None
    rest = list(argv)
    while rest:
        arg = rest.pop(0)
        if arg == "--json":
            as_json = True
        elif arg in ("--since", "--until"):
            if not rest:
                print(f"stats: {arg} needs a value ({usage})", file=sys.stderr)
                return 1
            value = rest.pop(0)
            if not is_usable_bound(value):
                print(
                    f"stats: {arg} value {value!r} is not a date, month or ISO timestamp ({usage})",
                    file=sys.stderr,
                )
                return 1
            if arg == "--since":
                since = value
            else:
                until = value
        else:
            print(f"stats: unknown argument {arg!r} ({usage})", file=sys.stderr)
            return 1

    read = evidence.read_facts(project_dir)
    if read["status"] == "error":
        print(f"stats: {read['reason']}", file=sys.stderr)
        return 1
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "project": gitstate.project_label(project_dir),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window": {"since": since, "until": until},
        # Facts a newer plugin wrote are not counted, and the report says how many.
        "schema_ahead": len(read.get("schema_ahead") or []),
        "by_version": aggregate(read["facts"], since, until),
    }
    if as_json:
        print(json.dumps(report, indent=2))
    else:
        print(render_human(report))
    return 0
