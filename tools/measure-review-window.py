#!/usr/bin/env python3
"""Read the measurement window: did the review-economy changes move the fleet?

Run:  python3 tools/measure-review-window.py [--cut 3.6.0] [--since 2026-09-01] [--json]

This is written BEFORE the window's data is read, so the question is fixed
before anyone has seen the answer. Every Critic review fact since `--since` is
put in a cohort by the plugin version that WROTE it: before `--cut`, from
`--cut` on, or unknown. Each cohort reports the same numbers, and every number
is printed with the size of the population it came from.

Hazards, each of which has already produced a wrong reading once:

* **The cohort key is the version on the fact, not the date.** Consumers run
  the develop tip, and the plugin cache is keyed by version string, so one
  `-dev.N` string can mean different code on different machines. #831 and #833
  landed inside `3.5.1-dev.2`. That is why the default cut is a RELEASED
  version: every fact at or after it carries all of that release's code.
* **Empty rates are computed only over facts that record `observations`.**
  That array began being written on 2026-09-16. A fact without it cannot tell
  "found nothing" from "found notes and demoted them", so it is counted as
  unrecorded and kept out of the rate (review-cost investigation §8.1).
* **Durations come in two kinds and are never pooled.** `clock` is a dispatch
  interval read by code (`review_dispatch.event_interval_seconds`, joined from
  the ledger by `fact_id`). Everything else is the reviewing model's estimate
  and is not reported as a duration at all.
* **A cell below `--min-cell` is printed and marked THIN.** A thin cell is a
  count, not a rate anyone should act on.
* **Cohorts are not a controlled comparison.** What each product was building
  differs between them. This reports the window; it does not attribute it.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import importlib.util
import json
import re
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "plugin" / "lib"))

from review_dispatch import event_interval_seconds  # noqa: E402

UTC = dt.timezone.utc
VERIFY = "verify-resolutions"


def _load_economy():
    """Ledger discovery and clone grouping live in `measure-review-loop-economy.py`.

    Reused rather than copied: that module's `find_ledgers` walks to any depth
    because a one-level glob missed every delegated worktree, and a second copy
    would be the one that forgets why.
    """
    path = REPO_ROOT / "tools" / "measure-review-loop-economy.py"
    spec = importlib.util.spec_from_file_location("measure_review_loop_economy_w", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["measure_review_loop_economy_w"] = module
    spec.loader.exec_module(module)
    return module


_VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$")


def version_key(text) -> tuple | None:
    """A sortable key for a plugin version, or ``None`` when it is not one.

    Semver order: a pre-release sorts before its release (`3.6.0-dev` <
    `3.6.0`), and pre-release parts compare numerically where they are numbers.
    """
    if not isinstance(text, str):
        return None
    m = _VERSION.match(text.strip())
    if not m:
        return None
    core = tuple(int(g) for g in m.group(1, 2, 3))
    pre = m.group(4)
    if pre is None:
        return core + (1, ())
    parts = tuple((0, int(p), "") if p.isdigit() else (1, 0, p) for p in pre.split("."))
    return core + (0, parts)


def cohort_of(version, cut: tuple) -> str:
    key = version_key(version)
    if key is None:
        return "unknown"
    return "after" if key >= cut else "before"


def _instant(text) -> dt.datetime | None:
    if not isinstance(text, str):
        return None
    try:
        return dt.datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def ledger_clocks(ledgers: list[Path]) -> tuple[dict[str, float], list[dict]]:
    """``fact_id -> clocked seconds`` for Critic events, plus the PR events.

    A Critic ledger event carries its evidence fact's id in the payload, which is
    what joins the clock to the fact that carries the version.
    """
    clocks: dict[str, float] = {}
    prs: list[dict] = []
    for path in ledgers:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            kind = event.get("event")
            if kind == "review.pr":
                prs.append({"when": _instant(event.get("ts")),
                            "clock": event_interval_seconds(event)})
                continue
            if kind != "review.critic":
                continue
            review = event.get("review") if isinstance(event.get("review"), dict) else {}
            fact_id = review.get("fact_id")
            secs = event_interval_seconds(event)
            if isinstance(fact_id, str) and secs is not None:
                clocks[fact_id] = secs
    return clocks, prs


def read_facts(store: Path, product: str, since: dt.datetime, clocks: dict) -> list[dict]:
    """One row per Critic review fact in ``store`` since ``since``."""
    rows = []
    for line in store.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            fact = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(fact, dict) or fact.get("kind") != "review":
            continue
        when = _instant(fact.get("ts"))
        if when is None or when < since:
            continue
        body = fact.get("body") if isinstance(fact.get("body"), dict) else {}
        actor = fact.get("actor") if isinstance(fact.get("actor"), dict) else {}
        findings = [f for f in body.get("findings") or [] if isinstance(f, dict)]
        observations = body.get("observations")
        rows.append({
            "product": product,
            "version": actor.get("plugin"),
            "mode": (body.get("mode") or "?").split(" ")[0],
            "scope": body.get("scope"),
            "findings": len(findings),
            "blocking": sum(1 for f in findings if f.get("severity") == "blocking"),
            "observations": len(observations) if isinstance(observations, list) else None,
            "clock": clocks.get(fact.get("id")),
        })
    return rows


def _median(values):
    return statistics.median(values) if values else None


def summarise(rows: list[dict], min_cell: int) -> dict:
    """The same numbers for any set of rows. Every rate carries its ``n``."""
    verify = [r for r in rows if r["mode"] == VERIFY]
    recorded = [r for r in verify if r["observations"] is not None]
    per_scope = collections.defaultdict(lambda: {"verify": 0, "cumulative": 0})
    for r in rows:
        if r["scope"]:
            cell = per_scope[(r["product"], r["scope"])]
            if r["mode"] == VERIFY:
                cell["verify"] += 1
            elif r["mode"] == "cumulative":
                cell["cumulative"] += 1
    cumulatives = [c["cumulative"] for c in per_scope.values() if c["cumulative"]]
    clocked_verify = [r["clock"] for r in verify if r["clock"] is not None]
    clocked_cum = [r["clock"] for r in rows if r["mode"] == "cumulative" and r["clock"] is not None]

    def rate(part, whole):
        return {"n": whole, "share": (part / whole) if whole else None, "thin": whole < min_cell}

    return {
        "reviews": len(rows),
        "products": len({r["product"] for r in rows}),
        "scopes": len(per_scope),
        "verify_share_of_runs": rate(len(verify), len(rows)),
        "verify_per_scope_median": _median([c["verify"] for c in per_scope.values()]),
        "repeat_cumulative_share": rate(sum(c - 1 for c in cumulatives), sum(cumulatives)),
        "verify_blocking_rate": rate(sum(1 for r in verify if r["blocking"]), len(verify)),
        "verify_nothing_gating": rate(sum(1 for r in recorded if r["findings"] == 0), len(recorded)),
        "verify_nothing_at_all": rate(
            sum(1 for r in recorded if r["findings"] == 0 and r["observations"] == 0), len(recorded)),
        "verify_unrecorded": len(verify) - len(recorded),
        "clock_verify": {"n": len(clocked_verify), "median_s": _median(clocked_verify),
                         "thin": len(clocked_verify) < min_cell},
        "clock_cumulative": {"n": len(clocked_cum), "median_s": _median(clocked_cum),
                             "thin": len(clocked_cum) < min_cell},
    }


def build(root: Path, since: dt.datetime, cut: str, min_cell: int) -> dict:
    economy = _load_economy()
    cut_key = version_key(cut)
    if cut_key is None:
        raise SystemExit(f"--cut {cut!r} is not a version")
    ledgers = economy.find_ledgers(root)
    clocks, prs = ledger_clocks(ledgers)
    clones: dict[str, list[Path]] = collections.defaultdict(list)
    for ledger in ledgers:
        clones[economy.clone_of(ledger)].append(ledger)
    rows, stores_missing = [], []
    for common_dir in sorted(clones):
        store = Path(common_dir) / "prawduct" / "evidence.jsonl"
        if not store.is_file():
            stores_missing.append(common_dir)
            continue
        product = Path(common_dir).parent.name if Path(common_dir).name == ".git" else Path(common_dir).name
        rows.extend(read_facts(store, product, since, clocks))
    cohorts = {name: [r for r in rows if cohort_of(r["version"], cut_key) == name]
               for name in ("before", "after", "unknown")}
    pr_window = [p for p in prs if p["when"] is not None and p["when"] >= since]
    return {
        "since": since.date().isoformat(),
        "cut": cut,
        "min_cell": min_cell,
        "ledgers": len(ledgers),
        "clones": len(clones),
        "stores_missing": stores_missing,
        "versions": dict(collections.Counter(r["version"] or "?" for r in rows)),
        "cohorts": {name: summarise(rs, min_cell) for name, rs in cohorts.items()},
        "pr": {"reviews": len(pr_window),
               "clocked": sum(1 for p in pr_window if p["clock"] is not None)},
    }


def _fmt_rate(cell: dict) -> str:
    if not cell["n"]:
        return "     —  (n=0)"
    flag = "  THIN" if cell["thin"] else ""
    return f"{cell['share'] * 100:5.0f}%  (n={cell['n']}){flag}"


def _fmt_clock(cell: dict) -> str:
    if not cell["n"]:
        return "     —  (n=0)"
    flag = "  THIN" if cell["thin"] else ""
    return f"{cell['median_s']:5.0f}s  (n={cell['n']}){flag}"


def render(report: dict) -> None:
    print(f"WINDOW  Critic review facts since {report['since']}, cohort cut at plugin "
          f"{report['cut']}  ·  {report['ledgers']} ledgers in {report['clones']} clones")
    if report["stores_missing"]:
        print(f"  NO EVIDENCE STORE at: {', '.join(report['stores_missing'])}")
        print("    (a worktree whose gitdir was pruned resolves to itself; any facts it wrote "
              "are in its clone's store)")
    print("VERSIONS  " + ", ".join(f"{v}={n}" for v, n in sorted(report["versions"].items())))
    lines = [
        ("reviews / products / scopes", lambda c: f"{c['reviews']} / {c['products']} / {c['scopes']}"),
        ("verify share of runs", lambda c: _fmt_rate(c["verify_share_of_runs"])),
        ("verify rounds per scope, median", lambda c: f"{c['verify_per_scope_median']}"),
        ("repeat cumulatives share", lambda c: _fmt_rate(c["repeat_cumulative_share"])),
        ("verify rounds finding a blocker", lambda c: _fmt_rate(c["verify_blocking_rate"])),
        ("verify: nothing that gates*", lambda c: _fmt_rate(c["verify_nothing_gating"])),
        ("verify: nothing at all*", lambda c: _fmt_rate(c["verify_nothing_at_all"])),
        ("verify: no observations field", lambda c: f"{c['verify_unrecorded']}"),
        ("clock, verify median", lambda c: _fmt_clock(c["clock_verify"])),
        ("clock, cumulative median", lambda c: _fmt_clock(c["clock_cumulative"])),
    ]
    cohorts = report["cohorts"]
    print(f"\n{'':34}{'before':<24}{'after':<24}{'unknown'}")
    for label, fn in lines:
        print(f"  {label:<32}" + "".join(f"{fn(cohorts[k]):<24}" for k in ("before", "after", "unknown")))
    print("  * over verify rounds that record `observations` only")
    pr = report["pr"]
    print(f"\nPR REVIEWS  {pr['reviews']} since {report['since']}, {pr['clocked']} with a "
          f"dispatch clock (PR events carry no version, so they are not cohorted)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", type=Path, default=Path.home() / "source")
    parser.add_argument("--since", default="2026-09-01")
    parser.add_argument("--cut", default="3.6.0",
                        help="first plugin version counted as 'after' (default: 3.6.0)")
    parser.add_argument("--min-cell", type=int, default=30)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    since = _instant(args.since + ("T00:00:00Z" if "T" not in args.since else ""))
    if since is None:
        parser.error(f"--since {args.since!r} is not an ISO date")
    report = build(args.root.expanduser(), since, args.cut, args.min_cell)
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        render(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
