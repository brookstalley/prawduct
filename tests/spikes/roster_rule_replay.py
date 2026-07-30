#!/usr/bin/env python3
"""Replay the coordinator-roster rule over this clone's real review history.

**Not a CI test** — it reads the machine-local evidence store
(``<git-common-dir>/prawduct/evidence.jsonl``), which is never committed, so the
offline suite cannot assert on it. It is committed because the numbers in
``build-plan-record-mechanization.md`` Chunk 04, in the ``critic_consolidate``
roster config block, and in the change-log entry are *claims about history*, and
a claim about history should ship with the way to recompute it.

Run from the repo root::

    python3 tests/spikes/roster_rule_replay.py

What it prints, per candidate rule: the share of ``final``/``cumulative``
reviews sent to the coordinator, and the blocking findings that landed in
reviews the rule would have sent single-pass.

**Reading the two risk numbers.** "blockers demoted" scores every rule the same
way — blocking findings in reviews the rule sends single-pass — which is what
makes the rows comparable, and it is an upper bound on loss (a single reviewer
still covers all 7 goals). "TRUE demotions" is the narrower, more honest figure:
reviews that *actually ran* the coordinator and would now run single-pass.

**Scope caveat, which is the whole reason this file exists.** These figures
describe THIS repo, where the declared risk surfaces match ~77% of reviews. They
do not transfer to a product repo, and reading them as if they did is the defect
the Chunk 04 review caught as blocking. A product that declares no
``risk_surfaces:`` keeps the older file-count rule precisely because no replay
like this one has ever been run against its history.
"""

from __future__ import annotations

import collections
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "plugin"))

from lib import coverage_algebra as ca  # noqa: E402
from lib import critic_consolidate as cc  # noqa: E402


#: The gate kernel — the row the plan's table scores as an alternative to the
#: shipped rule. Named by module rather than by risk surface, because that row
#: asks a narrower question than `risk_surfaces:` does.
_KERNEL = (
    "gates.py", "coverage_algebra.py", "critic_consolidate.py",
    "evidence.py", "ledger.py", "risk.py", "coverage.py",
)


def _touches_kernel(files: "list[str]") -> bool:
    return any(f.endswith(k) for f in files for k in _KERNEL)


def _store() -> Path:
    common = subprocess.check_output(
        ["git", "rev-parse", "--git-common-dir"], cwd=REPO, text=True
    ).strip()
    return (REPO / common) / "prawduct" / "evidence.jsonl"


def _reviews(store: Path):
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
            body = fact["body"]
            if (body.get("mode") or "").split(" ")[0] not in ("final", "cumulative"):
                continue
            sev = collections.Counter(
                (f.get("severity") or "").lower() for f in (body.get("findings") or [])
            )
            # Production derives the roster from files_CHANGED
            # (critic_consolidate.begin_review), so score the same list. They are
            # element-identical across every final/cumulative fact measured so
            # far and divergent in a majority of verify-resolutions facts, so the
            # equivalence is a property of the data rather than of the schema —
            # which is why this reads what production reads instead of relying
            # on it.
            files = body.get("files_changed") or body.get("files_reviewed") or []
            yield {
                "files": files,
                "n": len(files),
                "nj": len(ca.judgeable_files(files)),
                "ran_coordinator": len(body.get("roster") or []) == 3,
                "blocking": sev["blocking"],
                "warning": sev["warning"],
            }


def main() -> int:
    store = _store()
    if not store.is_file():
        print(f"no evidence store at {store} — nothing to replay", file=sys.stderr)
        return 1

    rows = list(_reviews(store))
    if not rows:
        print("no final/cumulative review facts in the store", file=sys.stderr)
        return 1

    prawduct_dir = REPO / ".prawduct"
    total_blocking = sum(r["blocking"] for r in rows)

    rules = {
        "total files >= 5 (pre-2026-07-30)": lambda r: r["n"] >= cc.COORDINATOR_FILE_THRESHOLD,
        "judgeable >= 12 (rejected)": lambda r: r["nj"] >= cc.COORDINATOR_JUDGEABLE_THRESHOLD,
        "judgeable >= 5 (rejected)": lambda r: r["nj"] >= 5,
        "gate-kernel OR judgeable >= 12": lambda r: _touches_kernel(r["files"])
        or r["nj"] >= cc.COORDINATOR_JUDGEABLE_THRESHOLD,
        "SHIPPED (_derive_roster)": lambda r: len(
            cc._derive_roster("final", r["files"], prawduct_dir)[0]
        ) == 3,
    }

    print(f"{len(rows)} final/cumulative reviews, {total_blocking} blocking findings")
    print(f"store: {store}\n")
    print(f"{'rule':<36} {'coord':>6} {'%':>5} {'blockers demoted':>18}")
    for name, fn in rules.items():
        coordinator = [r for r in rows if fn(r)]
        demoted = [r for r in rows if not fn(r)]
        db = sum(r["blocking"] for r in demoted)
        pct = 100 * len(coordinator) / len(rows)
        share = 100 * db / total_blocking if total_blocking else 0.0
        print(f"{name:<36} {len(coordinator):>6} {pct:>4.0f}% {db:>8} ({share:>3.0f}%)")

    true_demotions = [
        r
        for r in rows
        if r["ran_coordinator"]
        and len(cc._derive_roster("final", r["files"], prawduct_dir)[0]) == 1
    ]
    print(
        f"\nTRUE demotions under the shipped rule (ran coordinator, would now run "
        f"single-pass): {len(true_demotions)} reviews, "
        f"{sum(r['blocking'] for r in true_demotions)} blocking, "
        f"{sum(r['warning'] for r in true_demotions)} warning"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
