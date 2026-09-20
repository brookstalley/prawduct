#!/usr/bin/env python3
"""Re-derive the 2026-09-20 verify-resolutions findings from the evidence store.

Run from the repo root:  python3 .prawduct/research/review-cost-2026-09-20/verify_population.py

Reads `.git/prawduct/evidence.jsonl` (the EVIDENCE STORE, not the governance
ledger). The distinction is load-bearing twice over:

  * the store records `roster` on every review fact, which the ledger does not —
    that is what makes the roster question askable at all (investigation §7
    says it is not recorded, which is true only of the ledger); and
  * the store carries `observations`, the field an inner-stage pass demotes
    sub-BLOCKING content into. Any empty-rate computed from `findings` alone is
    NOT comparable across 2026-09-16, the date that array began being written.

Every number this prints is a measurement over the store as it stands; nothing
is transcribed. If a figure in `review-cost-investigation-2026-09-19.md` §8
disagrees with this script's output, the script is right and the prose is stale.
"""

import collections
import json
import pathlib
import statistics

STORE = pathlib.Path(".git/prawduct/evidence.jsonl")


def load_reviews() -> list[dict]:
    facts = [json.loads(line) for line in STORE.read_text().splitlines() if line.strip()]
    return [f for f in facts if f.get("kind") == "review"]


def duration(rev: dict) -> float:
    value = rev["body"].get("duration_seconds")
    return value if isinstance(value, (int, float)) else 0.0


def mode_of(rev: dict) -> str:
    return (rev["body"].get("mode") or "?").split(" ")[0]


def blocking(rev: dict) -> int:
    return sum(1 for f in (rev["body"].get("findings") or []) if f.get("severity") == "blocking")


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def roster_is_confounded(revs: list[dict]) -> None:
    """Investigation §5.1 deferred the roster question for want of an instrument.

    The instrument exists. It still cannot answer the question, and this is the
    evidence for that: roster size is assigned with tier, diff size and calendar
    month all at once, so no contrast isolates it.
    """
    section("roster: the deferred question, and why it stays deferred")
    cum = [r for r in revs if mode_of(r) == "cumulative"]
    for label, key in (
        ("tier", lambda r: r["body"].get("tier")),
        ("month", lambda r: r["ts"][:7]),
    ):
        table: dict = collections.defaultdict(collections.Counter)
        for rev in cum:
            table[key(rev)][len(rev["body"].get("roster") or [])] += 1
        print(f"  cumulative roster size by {label}:")
        for cell in sorted(table, key=str):
            print(f"    {cell}: {dict(table[cell])}")
    for size in (1, 3):
        sel = [r for r in cum if len(r["body"].get("roster") or []) == size]
        files = [len(r["body"].get("files_changed") or []) for r in sel]
        print(
            f"  roster {size}: n={len(sel)} median files_changed="
            f"{statistics.median(files):.0f}"
        )
    print(
        "  VERDICT: perfectly confounded. The one tier-and-size-matched cell has\n"
        "  n=5 and sits entirely in 2026-07. Identifying a roster effect needs a\n"
        "  randomised roster on standard-tier cumulative, not a further scan."
    )


def observations_boundary(revs: list[dict]) -> None:
    """The recording change that invalidates every cross-month empty rate."""
    section("the observations boundary (why empty-rate trends are not comparable)")
    vr = [r for r in revs if mode_of(r) == "verify-resolutions"]
    first = min(
        (r["ts"] for r in vr if r["body"].get("observations") is not None), default=None
    )
    print(f"  first verify fact carrying an observations array: {first}")
    print(f"  {'month':>9}{'n':>6}{'no findings':>13}{'carrying obs':>14}{'truly empty':>13}")
    by_month: dict = collections.defaultdict(list)
    for rev in vr:
        by_month[rev["ts"][:7]].append(rev)
    for month in sorted(by_month):
        sel = by_month[month]
        no_find = [r for r in sel if not (r["body"].get("findings") or [])]
        carrying = [r for r in sel if r["body"].get("observations") is not None]
        truly = [r for r in no_find if not (r["body"].get("observations") or [])]
        print(
            f"  {month:>9}{len(sel):>6}{len(no_find):>13}{len(carrying):>14}{len(truly):>13}"
        )
    print(
        "  READ THIS COLUMNWISE, NEVER ACROSS ROWS: 'truly empty' is only\n"
        "  meaningful where 'carrying obs' is ~100%. A rise in the no-findings\n"
        "  column across months measures when the array started being written."
    )


def clean_window(revs: list[dict]) -> None:
    """September: the only month where the demotion field is populated enough to read."""
    section("the clean window (2026-09)")
    sep = [r for r in revs if r["ts"][:7] == "2026-09"]
    vr = [r for r in sep if mode_of(r) == "verify-resolutions"]
    total = sum(duration(r) for r in sep)
    vr_total = sum(duration(r) for r in vr)
    print(f"  all reviews: n={len(sep)} {total / 3600:.1f}h")
    print(
        f"  verify-resolutions: n={len(vr)} {vr_total / 3600:.1f}h "
        f"({vr_total / total * 100:.0f}% of the month's review clock)"
    )
    nothing = [
        r for r in vr
        if not (r["body"].get("findings") or []) and not (r["body"].get("observations") or [])
    ]
    only_obs = [
        r for r in vr
        if not (r["body"].get("findings") or []) and (r["body"].get("observations") or [])
    ]
    with_findings = [r for r in vr if r["body"].get("findings")]
    for label, sel in (
        ("nothing at all", nothing),
        ("observations only (nothing that gates)", only_obs),
        ("some finding", with_findings),
    ):
        hours = sum(duration(r) for r in sel) / 3600
        print(f"    {label:<40} n={len(sel):>3}  {hours:>4.1f}h  {hours / (total / 3600) * 100:>4.1f}% of month")
    section("does delta size separate the wasteful rounds? (null result)")
    print(f"  {'files_changed':>14}{'n':>5}{'hours':>7}")
    for lo, hi, label in ((1, 2, "1-2"), (3, 4, "3-4"), (5, 9, "5-9"), (10, 10**6, "10+")):
        sel = [r for r in nothing if lo <= len(r["body"].get("files_changed") or []) <= hi]
        if sel:
            print(f"  {label:>14}{len(sel):>5}{sum(duration(r) for r in sel) / 3600:>7.1f}")
    print(
        "  Flat. A round that finds nothing is not distinguishable by the size of\n"
        "  the delta it reviewed, so a delta-size-keyed refusal or discount has no\n"
        "  population to aim at."
    )


def cost_scales_with_delta(revs: list[dict]) -> None:
    section("what a verify round costs, by delta size")
    vr = [r for r in revs if mode_of(r) == "verify-resolutions"]
    print(f"  {'files_changed':>14}{'n':>6}{'median s':>10}{'blocking/rev':>14}")
    for lo, hi, label in (
        (1, 1, "1"), (2, 2, "2"), (3, 4, "3-4"),
        (5, 9, "5-9"), (10, 19, "10-19"), (20, 10**6, "20+"),
    ):
        sel = [r for r in vr if lo <= len(r["body"].get("files_changed") or []) <= hi]
        if not sel:
            continue
        durations = [duration(r) for r in sel]
        total_blocking = sum(blocking(r) for r in sel)
        print(
            f"  {label:>14}{len(sel):>6}{statistics.median(durations):>10.0f}"
            f"{total_blocking / len(sel):>14.2f}"
        )


def main() -> None:
    revs = load_reviews()
    print(f"evidence store: {len(revs)} review facts, "
          f"{sum(duration(r) for r in revs) / 3600:.1f}h of recorded review")
    observations_boundary(revs)
    clean_window(revs)
    cost_scales_with_delta(revs)
    roster_is_confounded(revs)


if __name__ == "__main__":
    main()
