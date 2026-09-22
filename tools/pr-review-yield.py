#!/usr/bin/env python3
"""What the PR reviewer costs and what it catches, from a repo's governance ledger.

The consumer-overhead tool (`tools/measure-consumer-overhead.py`) answers what a
governed repo spends in total. This answers the narrower question that tool's open
question #2 asks and cannot: *is the PR reviewer worth what it costs* — by splitting
its findings by goal and severity, so a payload change can be graded against yield
rather than against wall clock alone.

Run it before and after any change to `skills/pr/review-protocol.md`. A payload
change that holds findings-per-review flat while cutting duration is the win; one
that drops findings is a quality trade and has to be argued as one.

    tools/pr-review-yield.py                 # this repo
    tools/pr-review-yield.py ../discodon     # a consumer
    tools/pr-review-yield.py --json

HAZARD, and it governs every duration this prints: `duration_seconds` is
**self-reported by the reviewing model**, not a measured clock. Against the dispatch
clock it runs high, worst on short reviews, and a PR review is short: about 3x on
this repo's clocked rows (see `documentation/consumer-build-metrics.md` hazard 2).
A target stated against it is a
target stated against an estimate. Where
the envelope carries `dispatched_at`, this tool prefers the measured interval and
says how many rows it had.
"""

from __future__ import annotations

import argparse
import collections
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "plugin" / "lib"))

from review_dispatch import event_interval_seconds  # noqa: E402
from timewindow import in_window  # noqa: E402


LEDGER = ".prawduct/.governance-ledger.jsonl"


def load(repo: Path, since: str | None, until: str | None) -> list[dict]:
    path = repo / LEDGER
    if not path.is_file():
        raise SystemExit(f"no ledger at {path}")
    rows = []
    corrupt = 0
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            corrupt += 1
            continue
        if obj.get("event") != "review.pr":
            continue
        # One home, shared with `review-stats` (`lib/timewindow`): these two
        # instruments grade the same before/after split, and while each kept
        # its own copy the lower bound had already diverged — this one
        # compared it as a bare string while the library parsed it, so the
        # same `--since` selected different populations in each.
        if not in_window(obj.get("ts") or "", since, until):
            continue
        rows.append(obj)
    if corrupt:
        print(f"note: skipped {corrupt} corrupt line(s)", file=sys.stderr)
    return rows


def duration(row: dict) -> tuple[int | None, bool]:
    """Return (seconds, measured).

    A measured interval wins over the self-reported estimate, but only when the
    mark attests one: `event_interval_seconds` is the framework's own
    predicate — the plausibility bound, the out-of-order refusal and the
    not-measured semantics — shared with `review-stats` and
    `measure-consumer-overhead.py` so the three readers of this field cannot
    disagree about what it says. A refused stamp is not an error; it falls back
    to the estimate exactly as a missing stamp does, and the row is counted in
    the self-reported population rather than dropped.
    """
    review = row.get("review") or {}
    secs = event_interval_seconds(row)
    if secs is not None:
        return int(secs), True
    reported = row.get("duration_seconds") or review.get("duration_seconds")
    return (int(reported), False) if reported else (None, False)


def report(rows: list[dict]) -> dict:
    durs, measured_n = [], 0
    by_month: dict[str, list[int]] = collections.defaultdict(list)
    by_goal: collections.Counter = collections.Counter()
    by_sev: collections.Counter = collections.Counter()
    files: list[int] = []
    for row in rows:
        secs, measured = duration(row)
        if secs is not None:
            durs.append(secs)
            by_month[(row.get("ts") or "")[:7]].append(secs)
            measured_n += measured
        review = row.get("review") or {}
        n = len(review.get("files_reviewed") or [])
        if n:
            files.append(n)
        for finding in review.get("findings") or []:
            by_goal[(finding.get("goal") or "(none)", finding.get("severity") or "(none)")] += 1
            by_sev[finding.get("severity") or "(none)"] += 1
    total_findings = sum(by_sev.values())
    return {
        "reviews": len(rows),
        "with_duration": len(durs),
        "measured_durations": measured_n,
        "median_seconds": statistics.median(durs) if durs else None,
        "total_hours": round(sum(durs) / 3600, 1) if durs else None,
        "findings": total_findings,
        "findings_per_review": round(total_findings / len(rows), 2) if rows else None,
        "by_severity": dict(by_sev),
        "by_goal": {f"{g} / {s}": n for (g, s), n in by_goal.most_common()},
        "median_files_reviewed": statistics.median(files) if files else None,
        "by_month": {
            m: {"n": len(v), "median_seconds": statistics.median(v)}
            for m, v in sorted(by_month.items())
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo", nargs="?", default=".", type=Path)
    ap.add_argument("--since", help="ISO timestamp lower bound (inclusive)")
    ap.add_argument("--until", help="ISO timestamp upper bound (inclusive)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rows = load(args.repo, args.since, args.until)
    if not rows:
        print("no review.pr events in range", file=sys.stderr)
        return 1
    data = report(rows)

    if args.json:
        json.dump(data, sys.stdout, indent=2)
        print()
        return 0

    print(f"PR review yield — {args.repo} ({data['reviews']} review(s))")
    est = data["with_duration"] - data["measured_durations"]
    print(
        f"  duration: median {data['median_seconds']}s, {data['total_hours']}h total"
        f"  [{data['measured_durations']} measured, {est} self-reported]"
    )
    print(f"  median files reviewed: {data['median_files_reviewed']}")
    print(f"  findings: {data['findings']} ({data['findings_per_review']}/review) {data['by_severity']}")
    print("\n  by goal x severity:")
    for label, n in data["by_goal"].items():
        print(f"    {n:5d}  {label}")
    print("\n  by month:")
    for month, v in data["by_month"].items():
        print(f"    {month}: n={v['n']:3d} median={v['median_seconds']:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
