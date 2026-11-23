#!/usr/bin/env python3
"""Measure whether findings about governance records still buy review rounds (#771).

Records (`coverage_algebra.RECORD_PREFIXES`) are oracle, not review subject: read
by every review, rated by none, except that `final`/`cumulative` rate them against
the three Records Pass bars. What nobody has measured is whether record findings
still BUY ROUNDS now that the structure is in place. This reads that off the
evidence store.

    tools/measure-record-findings.py
    tools/measure-record-findings.py --root ~/source --since 2026-08-01
    tools/measure-record-findings.py --json

**Source.** Review facts from each clone's evidence store through
`lib.evidence.read_facts` (deduped by id), once per clone: worktrees of one clone
share a store, so they are grouped by git common dir and read once. The store is
used over the per-worktree ledger because it is clone-shared, carries
`findings[].files` and `actor.plugin`, and survives worktree deletion.

**Classification.** A finding is record-only when every file it names is under a
prefix imported from `coverage_algebra.RECORD_PREFIXES` (never restated here),
subject-only when none is, mixed otherwise, and no-files when it names none. The
no-files share is reported beside every figure: those findings cannot be
classified, so a high share means the record-only share is a floor.

**Round-buying.** A finding bought a round when it resolved `fixed`, by the one
rule `lib.dispositions.finding_state` applies (a resolution fact outranks a
disposition). Share of ALL findings is also printed, but the headline is the
record-only share of round-buying ones, per stage and era, because rounds are the
cost.

**Stages.** `inner` = chunk / final / verify-resolutions, `boundary` = cumulative,
by `critic_consolidate.stage_of_manifest` (the one home of that mapping).

**Eras.** Windowed by the fact's `actor.plugin`: `post` is a plugin version at or
after `3.4.1-dev.2`, the first build carrying commit `429ac2df` (eligibility
narrowed to review subjects); `pre` is the control; `unknown` is a fact with no
parseable plugin version. Dev builds of one version share a version string, so a
`3.4.1-dev.2` fact may predate the commit by a few commits. That blur is one dev
build wide.

**Decision rule (fixed in #771 before the data).** Keep the structure as-is if,
in the post era, record-only findings are under 10% of round-buying findings at
the boundary stage and under 5% at the inner stage. Otherwise the smallest remedy
is filed, in order: narrow the Records Pass bars; cap the Records Pass at NOTE at
`final`; only then revisit the prefixes. A stage with no round-buying findings in
the post era has no verdict, and the rule is then undecided, never "keep".
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import importlib.util
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "plugin"))

from lib import coverage_algebra, critic_consolidate, dispositions, evidence  # noqa: E402

CLASSES = ("record-only", "subject-only", "mixed", "no-files")
STAGES = ("inner", "boundary")
ERAS = ("pre", "post", "unknown")
#: The first plugin version carrying commit 429ac2df.
ERA_BOUNDARY = "3.4.1-dev.2"
#: Decision rule thresholds, fixed on #771: record-only share of round-buying findings.
THRESHOLDS = {"boundary": 0.10, "inner": 0.05}


def _load_economy():
    """Import the sibling tool by path (hyphenated name): clone discovery lives there."""
    tool = REPO_ROOT / "tools" / "measure-review-loop-economy.py"
    spec = importlib.util.spec_from_file_location("measure_review_loop_economy", tool)
    module = importlib.util.module_from_spec(spec)
    sys.modules["measure_review_loop_economy"] = module
    spec.loader.exec_module(module)
    return module


_VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-dev\.(\d+))?$")


def version_key(version: object) -> "tuple | None":
    """Orderable key for ``X.Y.Z`` or ``X.Y.Z-dev.N`` (a dev build sorts below its release)."""
    m = _VERSION.match(version.strip()) if isinstance(version, str) else None
    if not m:
        return None
    x, y, z, dev = m.groups()
    return (int(x), int(y), int(z), 0, int(dev)) if dev is not None else (int(x), int(y), int(z), 1, 0)


def era_of(plugin_version: object) -> str:
    key = version_key(plugin_version)
    if key is None:
        return "unknown"
    return "post" if key >= version_key(ERA_BOUNDARY) else "pre"


def classify(files: object) -> str:
    """record-only / subject-only / mixed / no-files, by the plugin's own prefixes."""
    names = [f.strip().removeprefix("./") for f in files if isinstance(f, str) and f.strip()] if isinstance(files, list) else []
    if not names:
        return "no-files"
    record = [n.startswith(coverage_algebra.RECORD_PREFIXES) for n in names]
    if all(record):
        return "record-only"
    return "mixed" if any(record) else "subject-only"


def _cell() -> dict:
    return {"all": collections.Counter(), "fixed": collections.Counter()}


def collect(stores: "list[dict]", since: "dt.datetime | None") -> dict:
    """Tally the findings of every review fact in ``stores`` (one read_facts result per clone)."""
    cells: dict = collections.defaultdict(_cell)  # (era, stage) -> counts
    sev: dict = collections.defaultdict(_cell)  # (era, stage, severity) -> counts
    facts_read = findings_read = 0
    for store in stores:
        resolutions = dispositions.resolution_detail_index(store)
        dispos = dispositions.disposition_index(store)
        for fact in evidence.facts_of_kind(store, "review"):
            ts = _instant(fact.get("ts"))
            if since is not None and (ts is None or ts < since):
                continue
            facts_read += 1
            body = fact.get("body") or {}
            try:
                stage = critic_consolidate.stage_of_manifest(body)
            except ValueError:
                stage = "unknown"
            era = era_of((fact.get("actor") or {}).get("plugin"))
            for finding in body.get("findings") or []:
                if not isinstance(finding, dict):
                    continue
                findings_read += 1
                cls = classify(finding.get("files"))
                severity = dispositions._severity_of(finding) or "unrated"  # noqa: SLF001 — the one severity reader
                fixed = dispositions.finding_state(
                    (fact.get("id"), finding.get("fid")), dispos, resolutions
                ) == dispositions.STATE_FIXED
                for cell in (cells[(era, stage)], sev[(era, stage, severity)]):
                    cell["all"][cls] += 1
                    if fixed:
                        cell["fixed"][cls] += 1
    return {"facts": facts_read, "findings": findings_read, "cells": cells, "severity": sev}


def _instant(value: object) -> "dt.datetime | None":
    if not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def _counts(c: collections.Counter) -> dict:
    total = sum(c.values())
    out = {k: c[k] for k in CLASSES}
    out["total"] = total
    out["record_only_share"] = (c["record-only"] / total) if total else None
    out["no_files_share"] = (c["no-files"] / total) if total else None
    return out


def decide(report_cells: dict) -> dict:
    """Apply the fixed decision rule to the post era's round-buying findings."""
    per_stage, undecided, breached = {}, [], []
    for stage, limit in THRESHOLDS.items():
        fixed = report_cells.get("post", {}).get(stage, {}).get("fixed", {})
        share, total = fixed.get("record_only_share"), fixed.get("total", 0)
        per_stage[stage] = {"share": share, "round_buying": total, "limit": limit}
        if not total:
            undecided.append(stage)
        elif share >= limit:
            breached.append(stage)
    if breached:
        outcome = "remedy: file one build item for the smallest remedy (narrow the Records Pass bars first)"
    elif undecided:
        outcome = "undecided: no post-era round-buying findings at " + ", ".join(undecided)
    else:
        outcome = "keep-as-is: record-only share is under both thresholds"
    return {"outcome": outcome, "stages": per_stage, "breached": breached, "undecided": undecided}


def build_report(stores: "list[dict]", since: "dt.datetime | None", clones: int) -> dict:
    tally = collect(stores, since)
    cells: dict = {}
    for (era, stage), cell in tally["cells"].items():
        cells.setdefault(era, {})[stage] = {"all": _counts(cell["all"]), "fixed": _counts(cell["fixed"])}
    severity: dict = {}
    for (era, stage, sev), cell in tally["severity"].items():
        severity.setdefault(era, {}).setdefault(stage, {})[sev] = {
            "all": _counts(cell["all"]), "fixed": _counts(cell["fixed"])}
    total_all = collections.Counter()
    for cell in tally["cells"].values():
        total_all.update(cell["all"])
    return {
        "clones": clones,
        "review_facts": tally["facts"],
        "findings": tally["findings"],
        "no_files_share": (total_all["no-files"] / tally["findings"]) if tally["findings"] else None,
        "era_boundary": ERA_BOUNDARY,
        "record_prefixes": list(coverage_algebra.RECORD_PREFIXES),
        "cells": cells,
        "severity": severity,
        "decision": decide(cells),
    }


def _pct(x: "float | None") -> str:
    return "n/a" if x is None else f"{x:.0%}"


def render(report: dict) -> str:
    lines = [
        f"CORPUS  {report['clones']} clones  ·  {report['review_facts']} review facts  ·  "
        f"{report['findings']} findings  ·  no-files share {_pct(report['no_files_share'])}",
        f"RECORD PREFIXES  {', '.join(report['record_prefixes'])}  ·  era boundary: plugin >= {report['era_boundary']}",
    ]
    for era in ERAS:
        for stage in (*STAGES, "unknown"):
            cell = report["cells"].get(era, {}).get(stage)
            if not cell:
                continue
            lines.append(f"\n{era.upper()} era, {stage} stage")
            for label in ("all", "fixed"):
                c = cell[label]
                name = "all findings" if label == "all" else "round-buying (fixed)"
                lines.append(
                    f"  {name:<22} n={c['total']:<5} record-only {c['record-only']} ({_pct(c['record_only_share'])})  "
                    f"subject-only {c['subject-only']}  mixed {c['mixed']}  no-files {c['no-files']} ({_pct(c['no_files_share'])})")
            for sev, s in sorted(report["severity"].get(era, {}).get(stage, {}).items()):
                if s:
                    lines.append(
                        f"    {sev:<10} all {s['all']['total']} (record-only {s['all']['record-only']})  "
                        f"fixed {s['fixed']['total']} (record-only {s['fixed']['record-only']})")
    d = report["decision"]
    lines.append("\nDECISION RULE  post era, record-only share of round-buying findings")
    for stage, s in d["stages"].items():
        lines.append(f"  {stage}: {_pct(s['share'])} of {s['round_buying']} (keep if under {s['limit']:.0%})")
    lines.append(f"  outcome: {d['outcome']}")
    return "\n".join(lines)


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description="Measure whether record findings still buy review rounds.")
    parser.add_argument("--root", type=Path, default=Path.home() / "source",
                        help="directory holding the governed repos (default: ~/source)")
    parser.add_argument("--since", default=None, help="ISO date: only review facts at or after it (default: all)")
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    args = parser.parse_args(argv)

    economy = _load_economy()
    ledgers = economy.find_ledgers(args.root.expanduser())
    if not ledgers:
        sys.exit(f"no governed repos under {args.root}")
    since = None
    if args.since:
        since = _instant(args.since if "T" in args.since else args.since + "T00:00:00+00:00")
        if since is None:
            sys.exit(f"unparseable --since {args.since!r}")

    # One read per clone: worktrees share a store, so the first worktree stands for all.
    by_clone: dict[str, Path] = {}
    for ledger in ledgers:
        by_clone.setdefault(economy.clone_of(ledger), ledger.parent.parent)
    stores = []
    for repo in by_clone.values():
        store = evidence.read_facts(repo)
        if store.get("status") == "ok":
            stores.append(store)
    report = build_report(stores, since, len(stores))
    print(json.dumps(report, indent=2) if args.json else render(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
