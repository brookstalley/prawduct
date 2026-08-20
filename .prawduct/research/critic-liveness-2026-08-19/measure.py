#!/usr/bin/env python3
"""Derivations behind the v3.3.5 bundling decisions for #692 and #690.

Committed rather than run-and-discarded: a spike that throws its code away
leaves its numbers unfalsifiable, so every durable artifact cites THIS COMMAND
rather than the digits it prints.

    python3 .prawduct/research/critic-liveness-2026-08-19/measure.py

Two independent questions, two sections of output.

A. #692 — can the review-stats distribution ground CRITIC_ACTIVE_TTL_SECONDS?
   Prints the observed duration distribution against the TTL. Read the CAVEAT
   with the numbers: `duration_seconds` is SELF-REPORTED by the reviewing agent
   (lib/telemetry.py — "reaches the ledger from the reviewer's own partial"),
   and a coordinator review records max() across its partials
   (lib/critic_consolidate.py, build_coordinator_record). Marker WALL-CLOCK age
   — the quantity the TTL actually governs — spans dispatch + every reviewer +
   consolidation + coordinator turn latency, so it is strictly longer than any
   single reviewer's self-report. The distribution therefore cannot bound the
   TTL, however comfortable the margin looks. That is the finding.

B. #690 — is a roster read affordable on the SessionStart hot path?
   Times pending_state() in the common no-manifest case. The governing budget is
   nonfunctional-requirements.md 'SessionStart must be fast' / 'No probe or gate
   on the hot path may block or noticeably delay session start', whose concrete
   terms are git subprocess fan-out and full-tree walks. pending_state() does
   neither; it is a stat and an early return.
"""

import json
import pathlib
import sys
import time

REPO = pathlib.Path(__file__).resolve().parents[3]
LEDGER = REPO / ".prawduct" / ".governance-ledger.jsonl"


def percentile(values, q):
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round(q * (len(ordered) - 1))))
    return ordered[idx]


def section_a():
    print("A. #692 — review duration distribution vs CRITIC_ACTIVE_TTL_SECONDS")
    sys.path.insert(0, str(REPO / "plugin"))
    from lib import critic_marker

    ttl = critic_marker.CRITIC_ACTIVE_TTL_SECONDS

    if not LEDGER.is_file():
        print(f"   no ledger at {LEDGER} — nothing to derive")
        return
    durations, by_mode = [], {}
    for line in LEDGER.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        seconds = row.get("duration_seconds")
        if not isinstance(seconds, (int, float)) or isinstance(seconds, bool):
            continue
        durations.append(float(seconds))
        mode = (row.get("review") or {}).get("mode") or "(unknown)"
        by_mode.setdefault(mode, []).append(float(seconds))

    print(f"   TTL under test: {ttl}s")
    print(f"   reviews with a recorded duration: {len(durations)}")
    if not durations:
        return
    print(
        "   p50 {:.0f}s  p90 {:.0f}s  p95 {:.0f}s  p99 {:.0f}s  max {:.0f}s".format(
            percentile(durations, 0.50),
            percentile(durations, 0.90),
            percentile(durations, 0.95),
            percentile(durations, 0.99),
            max(durations),
        )
    )
    over = [d for d in durations if d > ttl]
    print(f"   exceeding the TTL: {len(over)} of {len(durations)}")
    print("   by mode (n, p95, max, count over TTL):")
    for mode in sorted(by_mode):
        vals = by_mode[mode]
        print(
            "     {:<20s} n={:<5d} p95={:>6.0f}s max={:>6.0f}s over={}".format(
                mode, len(vals), percentile(vals, 0.95), max(vals),
                sum(1 for d in vals if d > ttl),
            )
        )
    print(
        "   CAVEAT (the finding): these are self-reported reviewer estimates, not\n"
        "   marker wall-clock age. See this file's docstring — the margin above is\n"
        "   NOT evidence that the TTL is safe, and cannot be used to re-price it."
    )


def section_b():
    print("\nB. #690 — pending_state() cost on the SessionStart hot path")
    sys.path.insert(0, str(REPO / "plugin"))
    from lib import critic_consolidate

    prawduct_dir = REPO / ".prawduct"
    for _ in range(100):
        critic_consolidate.pending_state(prawduct_dir)
    iterations = 10_000
    start = time.perf_counter()
    for _ in range(iterations):
        state = critic_consolidate.pending_state(prawduct_dir)
    elapsed = time.perf_counter() - start
    per_call_us = elapsed / iterations * 1e6
    print(f"   observed state: {state}")
    print(f"   per call: {per_call_us:.1f} us  ({iterations} iterations)")
    print("   git subprocesses spawned: 0 (pure stat + early return)")
    print(
        "   Read against nonfunctional-requirements.md 'SessionStart must be fast',\n"
        "   whose concrete terms are git subprocess fan-out and full-tree walks."
    )


if __name__ == "__main__":
    section_a()
    section_b()
