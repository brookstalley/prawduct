#!/usr/bin/env python3
"""Score the post-cutoff escape re-run (#987) without changing the study's instrument.

Usage: rerun.py <landings-rerun.jsonl> <repo_f.txt> [--now <unix-ts>]

Reads ONE escape.py output file. Write the re-run there, never into landings.jsonl, which stats.py
reads by name. Scope: landings with ts after stats.CUTOFF. A landing whose 30-day window is still
open at run time (ts > now - escape.WINDOW_DAYS) is counted as `window-open` and left out of the
rate. The metric is stats.edge_rates's rule: rework edges with gap_h >= 24 per kLOC of
src_added, over landings with src_added >= 1. The groups are disjoint: repo F; ungoverned
excluding repo F; governed (stats.mode(bucket) != "none", excluding repo F).

Fails, rather than skips, when a (repo, sha) pair appears twice. A duplicate means an input was
wired wrong (a --branch run appended to the main run, say), and a skip would hide that. The
output gives rates and counts only. No repo, branch or sha is printed (the study's privacy rule).
"""
import collections
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from escape import WINDOW_DAYS  # noqa: E402
from stats import CUTOFF, mode  # noqa: E402

GROUPS = ("repo F", "ungoverned excl. F", "governed")


def duplicates(rows):
    seen = collections.Counter((r["repo"], r["sha"]) for r in rows)
    return sum(1 for n in seen.values() if n > 1)


def group_of(row, repo_f):
    if row["repo"] == repo_f:
        return "repo F"
    return "ungoverned excl. F" if mode(row["bucket"]) == "none" else "governed"


def score(rows, repo_f, now):
    dup = duplicates(rows)
    if dup:
        raise SystemExit(f"rerun.py: {dup} (repo, sha) pair(s) appear more than once; an input is "
                         "wired twice (a --branch run appended to the main run?). Refusing to score.")
    open_after = now - WINDOW_DAYS * 86400
    out = {g: {"landings": 0, "window_open": 0, "scoreable": 0, "src_added": 0, "edges": 0} for g in GROUPS}
    for r in rows:
        if r["ts"] <= CUTOFF:
            continue
        a = out[group_of(r, repo_f)]
        a["landings"] += 1
        if r["ts"] > open_after:
            a["window_open"] += 1
            continue
        a["scoreable"] += 1
        if r["src_added"] < 1:
            continue
        a["src_added"] += r["src_added"]
        a["edges"] += sum(1 for e in r["reworked"] if e["gap_h"] >= 24)
    for a in out.values():
        a["rate_per_kloc"] = round(1000 * a["edges"] / a["src_added"], 2) if a["src_added"] else None
    return out


def instrument_sha():
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        return subprocess.run(["git", "log", "-1", "--format=%H", "--", "escape.py"], cwd=here,
                              capture_output=True, text=True, check=True).stdout.strip() or "unknown"
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main(argv):
    if len(argv) not in (2, 4) or (len(argv) == 4 and argv[2] != "--now"):
        raise SystemExit(__doc__)
    rows = [json.loads(line) for line in open(argv[0]) if line.strip()]
    repo_f = open(argv[1]).read().strip()
    now = float(argv[3]) if len(argv) == 4 else time.time()
    result = score(rows, repo_f, now)
    print(f"instrument escape.py {instrument_sha()}")
    print(f"window: ts > {time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(CUTOFF))}, scored when closed by "
          f"{time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(now))} (window {WINDOW_DAYS} days)")
    for g in GROUPS:
        a = result[g]
        rate = "n/a" if a["rate_per_kloc"] is None else f"{a['rate_per_kloc']:.2f}"
        print(f"  {g:20} landings {a['landings']:5}  window-open {a['window_open']:5}  "
              f"scoreable {a['scoreable']:5}  kLOC {a['src_added'] / 1000:7.1f}  edges {a['edges']:5}  "
              f"rate/kLOC {rate}")
    return result


if __name__ == "__main__":
    main(sys.argv[1:])
