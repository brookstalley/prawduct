#!/usr/bin/env python3
"""Measure where the fleet's Critic rounds go, and how much of that the round budget can reach.

The derivation behind `documentation/consumer-build-metrics.md` § "Why the
verify-resolutions share is not moving". Kept runnable so its numbers are
falsifiable: the 2026-09-16 consumer-overhead triage set its baseline with a
query that lived in a scratchpad and is gone, which is why its figures cannot be
re-derived. Cite this command, never the digits.

    tools/measure-review-loop-economy.py
    tools/measure-review-loop-economy.py --root ~/source --since 2026-08-01
    tools/measure-review-loop-economy.py --json

Sibling of `measure-consumer-overhead.py`, which asks a different question: that
one is per-repo and windowed by prawduct version, and reports a consumer's whole
build economy. This one pools the fleet and asks a control question — given where
rounds actually go, how much of that spend can the review round budget ever
refuse? Ledger parsing has one home, in that script, and this imports it.

**The budget's parameters are READ FROM THE PLUGIN, never restated here**
(`lib.core.REVIEW_ROUND_BUDGET_DEFAULT`, `lib.critic_consolidate.FULL_ROUND_MODES`).
A tool that hardcoded them would keep reporting a reach the code no longer has,
and the finding this script exists to support is precisely a claim about which
modes the ceiling counts.

Hazards, in the order they will burn you. The first is inherited and decisive:

* **`duration_seconds` is self-reported by the reviewing model, not a measured
  clock** — hazard 2 of `consumer-build-metrics.md`. Against the dispatch clock
  it sits near five minutes whatever the real duration, so it is close only
  where reviews take about that long. Every hour figure here is therefore
  labelled `self-reported`, and the run counts, which are one row per real
  dispatch, are the series to lean on. The CLOCK line reports how many rows carry
  a true dispatch interval; where that is a handful, no hour figure here is
  measured.
* **A scope-less review is not a scope.** ~10% of rows record no `scope`, and the
  budget returns `unavailable` for them, which never refuses. They are counted and
  reported separately, never pooled into a scope's round count — pooling them
  would invent one enormous scope per repo and overstate the ceiling's reach.
* **Worktrees of one clone are separate ledgers of one product.** Each worktree
  has its own gitignored ledger, so a fleet glob counts them as distinct repos.
  They are grouped by git common dir and the grouping is printed; read the repo
  count with that line in view.
* **The reach figure is an upper bound, not a saving.** "Hours in scopes the
  budget can reach" counts every hour in scopes that ever hit the ceiling,
  including the rounds spent before it would have fired. The realisable saving is
  strictly smaller and this script does not estimate it.
* **Version windows are confounded with what each consumer was building**, and
  the fleet runs a spread of versions at any moment (see the MARKERS table).
  These are pooled correlations, not a controlled comparison.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import importlib.util
import json
import os
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_sibling():
    """Import `measure-consumer-overhead.py` by path — hyphenated, not a module name.

    Ledger parsing lives there and is shared rather than re-implemented: two
    parsers over one format drift, and the one that drifts is the one nobody is
    reading when the format changes.
    """
    tool = REPO_ROOT / "tools" / "measure-consumer-overhead.py"
    spec = importlib.util.spec_from_file_location("measure_consumer_overhead", tool)
    module = importlib.util.module_from_spec(spec)
    sys.modules["measure_consumer_overhead"] = module
    spec.loader.exec_module(module)
    return module


def _load_budget_params() -> tuple[int, tuple[str, ...], tuple[str, ...]]:
    """Read the ceiling and the modes it counts from the plugin that enforces them."""
    sys.path.insert(0, str(REPO_ROOT / "plugin"))
    from lib import core  # noqa: PLC0415 — path is set above, not at import time
    from lib import critic_consolidate as cc  # noqa: PLC0415

    return (
        core.REVIEW_ROUND_BUDGET_DEFAULT,
        tuple(cc.FULL_ROUND_MODES),
        tuple(cc.MODE_TOKEN_TO_VERBOSE),
    )


LEDGER_NAME = ".governance-ledger.jsonl"


def find_ledgers(root: Path) -> list[Path]:
    """Every governed ledger under `root`, at ANY depth.

    A one-level glob reads as complete and is not: delegated work runs in
    worktrees that sit INSIDE a repo (`<repo>/.claude/worktrees/<name>/`), and a
    clone may be parked under a hidden directory. Three of this machine's twenty
    ledgers were invisible to `*/.prawduct/...` on 2026-09-21, and the excluded
    set is not random — it is exactly the delegated work. The corpus is the
    instrument's most basic claim, so it is bounded by the PROPERTY (a
    `.prawduct/` ledger) rather than by depth.

    `.git` is pruned because a bare/objects walk dominates the runtime and can
    hold no ledger.
    """
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        if Path(dirpath).name == ".prawduct" and LEDGER_NAME in filenames:
            found.append(Path(dirpath) / LEDGER_NAME)
    return sorted(found)


def clone_of(ledger: Path) -> str:
    """Group worktrees of one clone. Falls back to the directory name."""
    import subprocess  # noqa: PLC0415 — only needed on this path

    repo = ledger.parent.parent
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return str((repo / out.stdout.strip()).resolve())
    except (OSError, subprocess.SubprocessError):
        pass
    return str(repo.resolve())


def count_products(clones: dict[str, list[str]], rows: list[dict]) -> int:
    """How many PRODUCTS contributed rows — not how many ledger directories did.

    Counting distinct `row["repo"]` counts every worktree as its own repo, which
    is this module's third docstring hazard in full — NOT the doc's hazard 3,
    which is a different list and a different subject — and it is the reason the
    grouping line is printed at all. One
    clone with four worktrees is one product; a count that does not go through
    the git common dir overstates the fleet by however many worktrees happen to
    be open at the time, and that number moves for reasons nothing to do with the
    fleet. A clone whose ledgers are all silent in the window is not counted.
    """
    contributing = {row["repo"] for row in rows}
    return sum(1 for names in clones.values()
               if any(name in contributing for name in names))


def marker_of(ledger: Path) -> tuple[str | None, str | None]:
    """The repo's last-seen plugin version, and when it first saw it.

    The banner rewrites the marker only when the version DIFFERS, so its mtime
    dates that transition and not the last session.
    """
    marker = ledger.parent / ".prawduct-version"
    if not marker.is_file():
        return None, None
    when = dt.datetime.fromtimestamp(marker.stat().st_mtime).astimezone()
    return marker.read_text(encoding="utf-8").strip(), when.isoformat(timespec="minutes")


def collect(ledgers: list[Path], since: dt.datetime, tool) -> list[dict]:
    """One row per Critic dispatch since `since`, carrying repo, scope and mode.

    PR reviews are a different event kind with a different cost and a very
    different yield, and are deliberately not pooled in.
    """
    rows = []
    for path in ledgers:
        repo = path.parent.parent.name
        for event in tool.read_ledger(path):
            if event["cat"] != "critic" or event["when"] < since:
                continue
            rows.append({
                "repo": repo,
                "scope": event.get("scope"),
                "mode": event["mode"],
                "seconds": event["duration"] or 0,
                "clock": event.get("clock_seconds"),
                "when": event["when"],
            })
    return rows


def analyse(rows: list[dict], budget: int, full_modes: tuple[str, ...]) -> dict:
    total = len(rows)
    hours = sum(r["seconds"] for r in rows) / 3600
    by_mode: dict[str, dict] = {}
    for mode in sorted({r["mode"] for r in rows}):
        runs = [r for r in rows if r["mode"] == mode]
        secs = sum(r["seconds"] for r in runs)
        by_mode[mode] = {
            "runs": len(runs),
            "run_share": len(runs) / total if total else 0,
            "hours_self_reported": secs / 3600,
            "hour_share_self_reported": (secs / 3600 / hours) if hours else 0,
            "counts_against_budget": mode in full_modes,
        }

    scopeless = [r for r in rows if not r["scope"]]

    per_scope: dict[tuple[str, str], dict] = collections.defaultdict(
        lambda: {"full": 0, "verify": 0, "seconds": 0.0, "cumulative": 0})
    for row in rows:
        if not row["scope"]:
            continue
        cell = per_scope[(row["repo"], row["scope"])]
        cell["full" if row["mode"] in full_modes else "verify"] += 1
        cell["seconds"] += row["seconds"]
        if row["mode"] == "cumulative":
            cell["cumulative"] += 1

    scopes = list(per_scope.values())
    at_ceiling = [c for c in scopes if c["full"] >= budget]
    reach_hours = sum(c["seconds"] for c in at_ceiling) / 3600

    cums = [c["cumulative"] for c in scopes if c["cumulative"]]
    repeat = sum(c - 1 for c in cums)
    cum_runs = sum(cums)

    return {
        "reviews": total,
        "hours_self_reported": hours,
        "clock_rows": sum(1 for r in rows if r["clock"] is not None),
        "by_mode": by_mode,
        "scopeless_reviews": len(scopeless),
        "scopeless_hours_self_reported": sum(r["seconds"] for r in scopeless) / 3600,
        "scopes": len(scopes),
        "scopes_at_ceiling": len(at_ceiling),
        "budget": budget,
        "full_modes": list(full_modes),
        "reach_hours_self_reported": reach_hours,
        "reach_share": (reach_hours / hours) if hours else 0,
        "full_rounds_per_scope": _spread([c["full"] for c in scopes]),
        "verify_per_scope": _spread([c["verify"] for c in scopes]),
        "scopes_with_cumulative": len(cums),
        "scopes_with_repeat_cumulative": sum(1 for c in cums if c > 1),
        "cumulative_runs": cum_runs,
        "repeat_cumulative_runs": repeat,
        "repeat_cumulative_share": (repeat / cum_runs) if cum_runs else 0,
    }


def _spread(values: list[int]) -> dict:
    if not values:
        return {"n": 0}
    ordered = sorted(values)
    return {
        "n": len(ordered),
        "mean": statistics.mean(ordered),
        "median": statistics.median(ordered),
        "p90": ordered[min(len(ordered) - 1, int(len(ordered) * 0.9))],
        "max": ordered[-1],
    }


def render(report: dict, markers: list[tuple[str, str, str]], clones: dict[str, list[str]]) -> None:
    r = report
    print(f"\nCORPUS  {r['reviews']} Critic reviews  ·  {r['scopes']} scopes  "
          f"·  {r.get('repos', '?')} repos  ·  {r.get('ledgers', '?')} ledgers  "
          f"·  {r['hours_self_reported']:.0f}h self-reported")
    print(f"CLOCK   {r['clock_rows']} of {r['reviews']} rows carry a measured dispatch interval — "
          f"every hour figure below is self-reported unless that number is large")
    shared = {k: v for k, v in clones.items() if len(v) > 1}
    if shared:
        print("WORKTREES  one clone, several ledgers: "
              + "; ".join(" + ".join(sorted(v)) for v in shared.values()))

    print(f"\nBY MODE                     runs   share    hours*   share   counts against budget?")
    for mode, cell in sorted(r["by_mode"].items(), key=lambda kv: -kv[1]["runs"]):
        print(f"  {mode:<24}{cell['runs']:>5}  {cell['run_share']*100:>5.0f}%  "
              f"{cell['hours_self_reported']:>7.1f}  {cell['hour_share_self_reported']*100:>5.0f}%   "
              f"{'yes' if cell['counts_against_budget'] else 'NO'}")
    print("  * self-reported by the reviewing model, not a measured clock")

    print(f"\nBUDGET REACH  (ceiling {r['budget']} full rounds per scope; "
          f"counts {', '.join(r['full_modes'])})")
    fr, vr = r["full_rounds_per_scope"], r["verify_per_scope"]
    if fr.get("n"):
        print(f"  full rounds per scope        mean {fr['mean']:.1f}  median {fr['median']:.0f}  "
              f"p90 {fr['p90']}  max {fr['max']}")
        print(f"  verify-resolutions per scope mean {vr['mean']:.1f}  median {vr['median']:.0f}  "
              f"p90 {vr['p90']}  max {vr['max']}")
    print(f"  scopes that ever reach the ceiling: {r['scopes_at_ceiling']} of {r['scopes']} "
          f"({r['scopes_at_ceiling']/r['scopes']*100:.0f}%)" if r["scopes"] else "  no scopes")
    print(f"  reviews recording NO scope: {r['scopeless_reviews']} "
          f"({r['scopeless_reviews']/r['reviews']*100:.0f}%) — the budget returns "
          f"`unavailable`, which never refuses")
    print(f"  upper bound on hours the ceiling can ever touch: "
          f"{r['reach_hours_self_reported']:.0f}h of {r['hours_self_reported']:.0f}h "
          f"({r['reach_share']*100:.0f}%) — an UPPER BOUND, not a saving: it counts "
          f"every hour in scopes that ever hit the ceiling, including the rounds "
          f"spent before it would have fired")

    print(f"\nREPEAT CUMULATIVES")
    print(f"  scopes running >1 cumulative: {r['scopes_with_repeat_cumulative']} of "
          f"{r['scopes_with_cumulative']}")
    print(f"  cumulative runs beyond the first per scope: {r['repeat_cumulative_runs']} of "
          f"{r['cumulative_runs']} ({r['repeat_cumulative_share']*100:.0f}%)")

    if markers:
        print(f"\nMARKERS  last-seen plugin version per repo (mtime dates the TRANSITION)")
        for repo, version, when in sorted(markers, key=lambda m: m[1]):
            print(f"  {repo:<34}{version:<16}{when}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure where the fleet's Critic rounds go and what the budget can reach.")
    parser.add_argument("--root", type=Path, default=Path.home() / "source",
                        help="directory holding the governed repos (default: ~/source)")
    parser.add_argument("--since", default="2026-08-01",
                        help="ISO date to start from (default: 2026-08-01)")
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    args = parser.parse_args()

    tool = _load_sibling()
    budget, full_modes, all_modes = _load_budget_params()

    ledgers = find_ledgers(args.root.expanduser())
    if not ledgers:
        sys.exit(f"no governance ledgers under {args.root}")

    # The sibling owns this parse (`_parse_instant`), and routing through it is
    # what the one-home rule asks for rather than a second copy here. It buys two
    # things a local `fromisoformat` does not: `Z` is normalised (3.10 rejects it,
    # 3.11+ accepts it, so a direct call is a CI-only crash), and a STATED offset
    # is converted rather than relabelled — `.replace(tzinfo=UTC)` on an aware
    # value silently moves the boundary, which is most of a short window.
    since = tool._parse_instant(args.since)  # noqa: SLF001 — the documented one home
    rows = collect(ledgers, since, tool)
    if not rows:
        sys.exit(f"no Critic reviews since {args.since} in {len(ledgers)} ledger(s)")

    report = analyse(rows, budget, full_modes)
    report["modes_known_to_the_plugin"] = list(all_modes)
    # The corpus SIZE is the instrument's most basic claim, so it is reported rather
    # than left for a reader to assert from outside: "every governed ledger on this
    # machine" was written in the doc while the scan was one level deep and missing
    # three. A completeness claim nobody can check is the one that goes stale silently.
    report["ledgers"] = len(ledgers)

    clones: dict[str, list[str]] = collections.defaultdict(list)
    markers = []
    for path in ledgers:
        repo = path.parent.parent.name
        clones[clone_of(path)].append(repo)
        version, when = marker_of(path)
        if version:
            markers.append((repo, version, when))

    report["repos"] = count_products(clones, rows)

    if args.json:
        report["markers"] = [{"repo": m[0], "version": m[1], "since": m[2]} for m in markers]
        print(json.dumps(report, indent=2))
    else:
        render(report, markers, clones)
    return 0


if __name__ == "__main__":
    sys.exit(main())
