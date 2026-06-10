"""Review telemetry — aggregate the governance ledger (review-proportionality ch.03).

Visible Costs (Principle 9) applied to the framework itself: ``prawduct-hook
review-stats`` turns the append-only event history
(``.prawduct/.governance-ledger.jsonl``) into the numbers the proportionality
arguments need — cost and actionable-finding yield per reviewer role × model ×
mode (the build plan's data requirement 1), a findings-by-file rollup from
finding-level attribution (requirement 2's first cut), and per-``scope``
rollups (the seam requirement 3's phase events will join later).

v1 reports on ``review.*`` event kinds only; other kinds are skipped WITH A
COUNT (forward-compat: a future ``build.chunk`` producer must not crash or
silently vanish from an old reader). Corrupt lines likewise skip-and-count.
Telemetry is pulled, not pushed — nothing in the session hooks calls this.

The reader deliberately does NOT reuse ``ledger.iter_events_newest_first``:
that iterator serves the PR-gate fallback (newest-first, per-line stderr
notes); this one is a quiet oldest-first sweep whose contract is honest
*counts* of what was skipped. The ``--json`` shape (top-level
``schema_version`` / ``project`` / ``generated_at``) is the stable machine
contract the cross-project aggregator (TEL-7A4X) builds on — documented in
``docs/governance-telemetry.md``; key changes bump ``REPORT_SCHEMA_VERSION``.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

from . import gitstate
from .ledger import ledger_path

REPORT_SCHEMA_VERSION = 1

# Severities with first-class columns. Anything else a record carries lands in
# "other" — counted, never dropped (the validator only requires a non-empty
# severity string, so an unexpected value must stay visible).
_SEVERITIES = ("blocking", "warning", "note")
_ACTIONABLE = frozenset({"blocking", "warning"})

# Findings-by-file rollup cap (build plan: "top-N paths by actionable
# findings"). The human and JSON views share the cap; the JSON carries
# `files_attributed_total` so a truncated list is visible, never silent.
TOP_FILES_LIMIT = 10


def _short_mode(mode) -> str:
    """Grouping key from the persisted verbose mode string —
    ``"final (full review, ready for push)"`` -> ``"final"``."""
    if not isinstance(mode, str) or not mode.strip():
        return "unknown"
    return mode.split(" (", 1)[0].strip()


def _read_events(path: Path) -> tuple[list[dict], dict]:
    """All reportable ``review.*`` events oldest-first, plus skip counts.

    ``corrupt_lines``: unparseable JSON, a non-object line, or an envelope
    without a string ``event`` kind. ``unknown_kinds``: a valid envelope whose
    kind is not ``review.*`` (v1 reports reviews only). ``invalid_payloads``:
    a ``review.*`` envelope whose ``review`` payload is missing a findings
    list (unusable for aggregation).
    """
    skipped = {"corrupt_lines": 0, "unknown_kinds": 0, "invalid_payloads": 0}
    events: list[dict] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        print(f"review-stats: ledger unreadable ({exc})", file=sys.stderr)
        return events, skipped
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            skipped["corrupt_lines"] += 1
            continue
        if not isinstance(event, dict) or not isinstance(event.get("event"), str):
            skipped["corrupt_lines"] += 1
            continue
        if not event["event"].startswith("review."):
            skipped["unknown_kinds"] += 1
            continue
        payload = event.get("review")
        if not isinstance(payload, dict) or not isinstance(payload.get("findings"), list):
            skipped["invalid_payloads"] += 1
            continue
        events.append(event)
    return events, skipped


def _extract_row(event: dict) -> dict:
    """The per-event record aggregation runs over (envelope + payload reads
    in one place, so every grouping sees identical values)."""
    actor = event.get("actor") if isinstance(event.get("actor"), dict) else {}
    model = actor.get("model")
    role = actor.get("role")
    duration = event.get("duration_seconds")
    if not isinstance(duration, (int, float)) or isinstance(duration, bool):
        duration = None
    scope = event.get("scope")
    findings = [f for f in event["review"]["findings"] if isinstance(f, dict)]
    severities = [
        f["severity"] if f.get("severity") in _SEVERITIES else "other"
        for f in findings
        if isinstance(f.get("severity"), str)
    ]
    return {
        "role": role if isinstance(role, str) else None,
        "model": model if isinstance(model, str) else None,
        "mode": _short_mode(event["review"].get("mode")),
        "scope": scope if isinstance(scope, str) else None,
        "duration": duration,
        "severities": severities,
        "findings": findings,
    }


def _group_stats(rows: list[dict]) -> dict:
    """The stat block every grouping (overall / role×model×mode / scope)
    shares: review count, duration totals, findings by severity,
    actionable rate, findings-per-review."""
    durations = [r["duration"] for r in rows if r["duration"] is not None]
    by_severity = {sev: 0 for sev in (*_SEVERITIES, "other")}
    actionable_reviews = 0
    total_findings = 0
    for r in rows:
        for sev in r["severities"]:
            by_severity[sev] += 1
        total_findings += len(r["severities"])
        if any(sev in _ACTIONABLE for sev in r["severities"]):
            actionable_reviews += 1
    n = len(rows)
    return {
        "reviews": n,
        "duration_total_seconds": round(sum(durations), 1) if durations else 0,
        "duration_median_seconds": round(median(durations), 1) if durations else None,
        "findings": by_severity,
        "findings_per_review": round(total_findings / n, 2) if n else 0.0,
        "actionable_rate": round(actionable_reviews / n, 3) if n else 0.0,
    }


def _top_files(rows: list[dict]) -> tuple[list[dict], int]:
    """Findings-by-file rollup from per-finding ``files`` attribution —
    (top entries by actionable findings, total attributed paths)."""
    per_path: dict[str, dict[str, int]] = {}
    for r in rows:
        for finding in r["findings"]:
            files = finding.get("files")
            if not isinstance(files, list):
                continue
            actionable = finding.get("severity") in _ACTIONABLE
            for path in files:
                if not isinstance(path, str) or not path.strip():
                    continue
                entry = per_path.setdefault(path, {"actionable_findings": 0, "findings": 0})
                entry["findings"] += 1
                if actionable:
                    entry["actionable_findings"] += 1
    ranked = sorted(
        ({"path": path, **counts} for path, counts in per_path.items()),
        key=lambda e: (-e["actionable_findings"], -e["findings"], e["path"]),
    )
    return ranked[:TOP_FILES_LIMIT], len(per_path)


def aggregate_review_stats(events: list[dict], skipped: dict) -> dict:
    """The report body (everything below the ``project``/``generated_at``
    header the CLI adds) — pure, deterministic, fully derived from events."""
    rows = [_extract_row(e) for e in events]

    by_rmm: dict[tuple, list[dict]] = {}
    by_scope: dict[str | None, list[dict]] = {}
    for row in rows:
        by_rmm.setdefault((row["role"], row["model"], row["mode"]), []).append(row)
        by_scope.setdefault(row["scope"], []).append(row)

    top_files, files_attributed_total = _top_files(rows)
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "events_total": len(rows),
        "skipped": dict(skipped),
        "overall": _group_stats(rows),
        "by_role_model_mode": [
            {"role": role, "model": model, "mode": mode, **_group_stats(group)}
            for (role, model, mode), group in sorted(
                by_rmm.items(), key=lambda kv: (kv[0][0] or "", kv[0][1] or "", kv[0][2])
            )
        ],
        "by_scope": [
            {"scope": scope, **_group_stats(group)}
            for scope, group in sorted(by_scope.items(), key=lambda kv: kv[0] or "")
        ],
        "top_files": top_files,
        "files_attributed_total": files_attributed_total,
    }


def _fmt_stats(stats: dict) -> str:
    """One stat block as a human line fragment (shared by every grouping)."""
    f = stats["findings"]
    med = stats["duration_median_seconds"]
    pct = round(stats["actionable_rate"] * 100)
    return (
        f"{stats['reviews']} review(s) | duration total {stats['duration_total_seconds']}s, "
        f"median {med if med is not None else '-'}s | "
        f"B/W/N/other {f['blocking']}/{f['warning']}/{f['note']}/{f['other']} | "
        f"actionable {pct}% | {stats['findings_per_review']} findings/review"
    )


def _render_human(report: dict, ledger_rel: str) -> str:
    sk = report["skipped"]
    lines = [
        f"review-stats — {report['project']} ({ledger_rel})",
        f"events: {report['events_total']} review event(s); skipped: "
        f"{sk['corrupt_lines']} corrupt line(s), {sk['unknown_kinds']} unknown kind(s), "
        f"{sk['invalid_payloads']} invalid payload(s)",
        "",
        f"overall: {_fmt_stats(report['overall'])}",
        "",
        "by role x model x mode:",
    ]
    for entry in report["by_role_model_mode"]:
        label = f"{entry['role'] or '(unknown)'} / {entry['model'] or '(unknown)'} / {entry['mode']}"
        lines.append(f"  {label}: {_fmt_stats(entry)}")
    lines += ["", "by scope:"]
    for entry in report["by_scope"]:
        lines.append(f"  {entry['scope'] or '(none)'}: {_fmt_stats(entry)}")
    lines += ["", f"top files by actionable findings (cap {TOP_FILES_LIMIT}):"]
    if report["top_files"]:
        for entry in report["top_files"]:
            lines.append(
                f"  {entry['path']}: {entry['actionable_findings']} actionable / "
                f"{entry['findings']} total"
            )
        shown = len(report["top_files"])
        if report["files_attributed_total"] > shown:
            lines.append(
                f"  (+{report['files_attributed_total'] - shown} more attributed path(s) below the cap)"
            )
    else:
        lines.append("  (none — no finding carries file attribution yet)")
    return "\n".join(lines)


def review_stats(project_dir: Path, argv: list[str]) -> int:
    """Body of ``prawduct-hook review-stats [--json]`` — see module docstring.

    Exit 0 always when the report can be produced, including a missing ledger
    ("no review history" is an answer, not an error); exit 1 only on bad args.
    """
    as_json = False
    for arg in argv:
        if arg == "--json":
            as_json = True
        else:
            print(f"review-stats: unknown argument {arg!r} (usage: review-stats [--json])", file=sys.stderr)
            return 1

    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    path = ledger_path(prawduct_dir)
    if path.is_file():
        events, skipped = _read_events(path)
    else:
        events, skipped = [], {"corrupt_lines": 0, "unknown_kinds": 0, "invalid_payloads": 0}

    report = aggregate_review_stats(events, skipped)
    # Header fields the pure aggregation can't know — added once, here, so the
    # JSON and human renderings always agree.
    report = {
        "schema_version": report.pop("schema_version"),
        "project": project_dir.resolve().name,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        **report,
    }

    if as_json:
        print(json.dumps(report, indent=2))
        return 0
    if not path.is_file():
        print(f"no review history ({path.name} not found — reviews append to it via ledger-append)")
        return 0
    print(_render_human(report, f".prawduct/{path.name}"))
    return 0
