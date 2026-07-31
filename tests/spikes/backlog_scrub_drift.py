"""Scrub-decision drift — are the recorded migration dispositions still current?

`.prawduct/artifacts/migration-scrub-decisions.md` records owner-approved merge and
drop dispositions against a corpus snapshot, and tells its reader to *"regenerate it
if the source drifts materially before the run."* This is that regeneration check.

Committed rather than discarded for the same reason as the dispositions' own caveat
("144 items at 964d03b; re-derive at use"): the corpus grows continuously, so any
transcribed count is stale by the next filing. Run this before executing the scrub.

    python3 tests/spikes/backlog_scrub_drift.py            # vs the recorded snapshot
    python3 tests/spikes/backlog_scrub_drift.py 4e08a6c    # vs any other ref

What it answers:

  * How far has the corpus moved since the dispositions were approved?
  * Does every recorded merge pair still resolve — duplicate present, survivor
    present and not already archived?
  * Is every recorded drop still an open item (a drop of an already-disposed item
    is a no-op, not a decision)?
  * Which items have appeared since the snapshot and have therefore never been
    surveyed for staleness or duplication at all?

A `promoted` survivor is NOT a failure: promoted means in-flight, and folding a
duplicate into an in-flight survivor is exactly as sound as into an open one.

Not a pytest test: it measures a living corpus against a dated decision, so it has no
fixed expected value. It is a measuring instrument, deliberately kept runnable.
"""
from __future__ import annotations

import re
import subprocess
import sys

BACKLOG = ".prawduct/backlog.md"
DECISIONS = ".prawduct/artifacts/migration-scrub-decisions.md"
SNAPSHOT = "964d03b"  # the ref the recorded dispositions were derived against

HEAD_RE = re.compile(r"^- \*\*\[([A-Z]{2,4}-[A-Z0-9]{4})\]\*\* (.+)$")
META_RE = re.compile(r"^\s+`(.*(?:status|added):.*)`\s*$")
# The two tables differ in shape: merges are `| duplicate | survivor | reason |`,
# drops are `| item | reason |` with prose in the second column. Match each on its
# own terms — a single regex demanding an id in column 2 silently drops every drop.
MERGE_ROW_RE = re.compile(
    r"^\|\s*([A-Z]{2,4}-[A-Z0-9]{4})\s*\|\s*([A-Z]{2,4}-[A-Z0-9]{4})\s*\|"
)
DROP_ROW_RE = re.compile(r"^\|\s*([A-Z]{2,4}-[A-Z0-9]{4})\s*\|")
LIVE_STATUSES = {"open", "promoted"}


def _show(ref: str, path: str) -> str:
    out = subprocess.run(["git", "show", f"{ref}:{path}"],
                         capture_output=True, text=True, check=True)
    return out.stdout


def parse(text: str) -> dict[str, dict]:
    items: dict[str, dict] = {}
    cur = None
    archived = False
    for line in text.splitlines():
        if line.startswith("## Archive"):
            archived = True
        head = HEAD_RE.match(line)
        if head:
            cur = head.group(1)
            items[cur] = {"title": head.group(2), "status": "?",
                          "added": "?", "archived": archived}
            continue
        if cur is None:
            continue
        meta = META_RE.match(line)
        if meta and items[cur]["status"] == "?":
            bar = meta.group(1)
            st = re.search(r"status:\s*([a-z-]+)", bar)
            ad = re.search(r"added:\s*([0-9-]+)", bar)
            if st:
                items[cur]["status"] = st.group(1)
            if ad:
                items[cur]["added"] = ad.group(1)
    return items


def recorded_dispositions(text: str) -> tuple[list[tuple[str, str]], list[str]]:
    """Parse the merge table (duplicate -> survivor) and the drop table from the artifact."""
    merges: list[tuple[str, str]] = []
    drops: list[str] = []
    section = None
    for line in text.splitlines():
        low = line.lower()
        if low.startswith("merges"):
            section = "merge"
        elif low.startswith("drops"):
            section = "drop"
        elif line.startswith("## "):
            section = None
        if section == "merge":
            row = MERGE_ROW_RE.match(line)
            if row:
                merges.append((row.group(1), row.group(2)))
        elif section == "drop":
            row = DROP_ROW_RE.match(line)
            if row:
                drops.append(row.group(1))
    if not merges or not drops:
        raise SystemExit(
            f"{DECISIONS}: parsed {len(merges)} merge(s) and {len(drops)} drop(s) — "
            "at least one table did not match. The artifact's shape changed; fix the "
            "parser rather than trusting a silently empty disposition set."
        )
    return merges, drops


def main(argv: list[str]) -> int:
    ref = argv[1] if len(argv) > 1 else SNAPSHOT
    with open(BACKLOG, encoding="utf-8") as fh:
        now = parse(fh.read())
    then = parse(_show(ref, BACKLOG))
    with open(DECISIONS, encoding="utf-8") as fh:
        merges, drops = recorded_dispositions(fh.read())

    open_then = sum(1 for v in then.values() if v["status"] == "open")
    open_now = sum(1 for v in now.values() if v["status"] == "open")
    growth = (100 * open_now // open_then - 100) if open_then else 0
    print(f"== corpus drift since {ref} ==")
    print(f"items: {len(then)} -> {len(now)}   open: {open_then} -> {open_now} (+{growth}%)")

    print(f"\n-- recorded merges ({len(merges)}) --")
    stale_merges = 0
    for dup, surv in merges:
        problems = []
        d, s = now.get(dup), now.get(surv)
        if d is None:
            problems.append(f"{dup} absent")
        elif d["status"] not in LIVE_STATUSES:
            problems.append(f"{dup} already {d['status']}")
        if s is None:
            problems.append(f"survivor {surv} absent")
        elif s["status"] not in LIVE_STATUSES:
            problems.append(f"survivor {surv} already {s['status']}")
        stale_merges += bool(problems)
        note = "; ".join(problems) if problems else f"ok ({d['status']} -> {s['status']})"
        print(f"  {dup} -> {surv}: {note}")

    print(f"\n-- recorded drops ({len(drops)}) --")
    stale_drops = 0
    for did in drops:
        item = now.get(did)
        if item is None:
            print(f"  {did}: absent")
            stale_drops += 1
        elif item["status"] != "open":
            print(f"  {did}: already {item['status']} — drop is a no-op")
            stale_drops += 1
        else:
            print(f"  {did}: ok (open)")

    new_open = {k: v for k, v in now.items()
                if k not in then and v["status"] == "open"}
    share = (100 * len(new_open) // open_now) if open_now else 0
    print(f"\n-- never surveyed --")
    print(f"  {len(new_open)} open item(s) filed since {ref} — {share}% of the open corpus, "
          f"outside every recorded disposition")
    for key in sorted(new_open):
        print(f"    {key}  {new_open[key]['added']}  {new_open[key]['title'][:96]}")

    verdict = "CURRENT" if not (stale_merges or stale_drops or new_open) else "STALE"
    print(f"\nverdict: dispositions are {verdict} "
          f"({stale_merges} merge issue(s), {stale_drops} drop no-op(s), "
          f"{len(new_open)} unsurveyed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
