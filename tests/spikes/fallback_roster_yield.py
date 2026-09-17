#!/usr/bin/env python3
"""Measure what the retired no-declaration roster fallback bought, fleet-wide.

**Not a CI test** — it reads every sibling repo's machine-local evidence store
(``<git-common-dir>/prawduct/evidence.jsonl``), which is never committed, so the
offline suite cannot assert on it. It is committed because the figure in the
``critic_consolidate`` roster config block and in the change-log entry that
retired the fallback is a *claim about history*, and a claim about history
ships with the way to recompute it.

Run from the repo root::

    python3 tests/spikes/fallback_roster_yield.py [--since 2026-08-01] [--until 2026-09-17]
    python3 tests/spikes/fallback_roster_yield.py --root ~/source

**The rule being measured.** Until the review-stages plan retired it, a repo
that declared no ``risk_surfaces:`` got the three-reviewer coordinator on any
``final``/``cumulative`` review of 5+ changed files, whatever their risk — the
pre-2026-07-30 file-count rule, "retained as the conservative fallback". The
question this answers: across the fleet, how many blocking findings landed in
reviews that ONLY that fallback sent to the coordinator — reviews touching no
risk surface, below the 12-judgeable volume threshold, in a repo with no
declaration? Those are the findings a single reviewer would have had to find
alone; how many it would actually have missed is an upper bound on the loss,
because a single reviewer still runs all seven goals.

**What a fact records, and what is reconstructed.** A review fact carries the
roster that ran (``roster``) and the files (``files_changed``, falling back to
``files_reviewed`` for older facts), but not WHY the roster was chosen — the
rationale lives on the transient manifest. So the fallback's firing set is
re-derived from the fact's files against the repo's *current* declaration
state, which is the one caveat: a repo that declared surfaces after the window
reads here as declared throughout. The ``roster agrees`` column is the check
that the reconstruction matches what actually ran.
"""

from __future__ import annotations

import argparse
import collections
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "plugin"))

from lib import coverage_algebra as ca  # noqa: E402
from lib import critic_consolidate as cc  # noqa: E402
from lib import risk  # noqa: E402

#: Total changed files at which the retired rule bought the coordinator.
RETIRED_FILE_THRESHOLD = 5


def _store(repo: Path) -> Path | None:
    try:
        common = subprocess.check_output(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=repo, text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, OSError):
        return None
    store = (repo / common) / "prawduct" / "evidence.jsonl"
    return store if store.is_file() else None


def _reviews(store: Path, since: str, until: str):
    with store.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                fact = json.loads(line)
            except json.JSONDecodeError:
                continue
            if fact.get("kind") != "review":
                continue
            ts = (fact.get("ts") or "")[:10]
            if not (since <= ts <= until):
                continue
            body = fact["body"]
            if (body.get("mode") or "").split(" ")[0] not in ("final", "cumulative"):
                continue
            sev = collections.Counter(
                (f.get("severity") or "").lower() for f in (body.get("findings") or [])
            )
            files = body.get("files_changed") or body.get("files_reviewed") or []
            yield {
                "ts": ts,
                "files": files,
                "n": len(files),
                "nj": len(ca.judgeable_files(files)),
                "ran_coordinator": len(body.get("roster") or []) == 3,
                "blocking": sev["blocking"],
                "warning": sev["warning"],
                "note": sev["note"],
            }


def _fallback_only(row: dict, prawduct_dir: Path) -> bool:
    """True when the retired rule was the ONLY escalator that would have fired."""
    touched, _ = risk.paths_touch_risk_surface(prawduct_dir, row["files"])
    if touched:
        return False
    if row["nj"] >= cc.COORDINATOR_JUDGEABLE_THRESHOLD:
        return False
    return row["n"] >= RETIRED_FILE_THRESHOLD


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", default=str(REPO.parent), help="directory holding sibling repos")
    ap.add_argument("--since", default="2026-08-01", help="first day of the window (inclusive)")
    ap.add_argument("--until", default="2026-09-17", help="last day of the window (inclusive)")
    args = ap.parse_args(argv)

    root = Path(args.root).expanduser()
    repos = sorted(p for p in root.iterdir() if (p / ".prawduct").is_dir())
    if not repos:
        print(f"no repos with a .prawduct/ under {root}", file=sys.stderr)
        return 1

    print(f"window {args.since} → {args.until}; root {root}\n")
    hdr = f"{'repo':<30} {'declared':>8} {'reviews':>7} {'fallback-only':>13} {'agrees':>6} {'blocking':>8} {'warning':>7} {'note':>5}"
    print(hdr)
    tot = collections.Counter()
    for repo in repos:
        store = _store(repo)
        if store is None:
            continue
        prawduct_dir = repo / ".prawduct"
        declared = risk.has_product_risk_declaration(prawduct_dir)
        rows = list(_reviews(store, args.since, args.until))
        if not rows:
            continue
        if declared:
            # The fallback never fired here; the row is printed for scale only.
            print(f"{repo.name:<30} {'yes':>8} {len(rows):>7} {'-':>13} {'-':>6} {'-':>8} {'-':>7} {'-':>5}")
            continue
        fired = [r for r in rows if _fallback_only(r, prawduct_dir)]
        agrees = sum(1 for r in fired if r["ran_coordinator"])
        b = sum(r["blocking"] for r in fired)
        w = sum(r["warning"] for r in fired)
        n = sum(r["note"] for r in fired)
        print(
            f"{repo.name:<30} {'no':>8} {len(rows):>7} {len(fired):>13} "
            f"{agrees:>6} {b:>8} {w:>7} {n:>5}"
        )
        tot.update(reviews=len(rows), fired=len(fired), agrees=agrees, blocking=b, warning=w, note=n)

    print()
    print(
        f"undeclared repos: {tot['reviews']} final/cumulative reviews in the window; "
        f"{tot['fired']} sent to the coordinator by the file-count fallback alone "
        f"({tot['agrees']} of those actually ran three reviewers); "
        f"those {tot['fired']} reviews carried {tot['blocking']} blocking, "
        f"{tot['warning']} warning, {tot['note']} note findings"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
