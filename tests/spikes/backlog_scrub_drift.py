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
  * Does every recorded merge pair still resolve — and is folding it still SAFE?
  * Is every recorded drop still an open item (a drop of an already-disposed item
    is a no-op, not a decision)?
  * Which items have appeared since the snapshot and have therefore never been
    surveyed for staleness or duplication at all?

**On `promoted`, the two roles are not symmetric.** A promoted *survivor* is fine:
promoted means in-flight, and folding a duplicate into in-flight work is exactly as
sound as folding it into an open item. A promoted *duplicate* is not: it is work
someone has started, and the recorded disposition would close it as a duplicate.
That pairing is flagged, not waved through.

Reads through ``lib.backlog.legacy.parse_backlog`` — the parser the importer itself
reads the source through — so the item set measured here is the item set the
migration will act on.

Not a pytest test: it measures a living corpus against a dated decision, so it has no
fixed expected value. It is a measuring instrument, deliberately kept runnable.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_SPIKE_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _SPIKE_DIR.parent.parent / "plugin"
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from lib.backlog import legacy  # noqa: E402

BACKLOG = ".prawduct/backlog.md"
DECISIONS = ".prawduct/artifacts/migration-scrub-decisions.md"
SNAPSHOT = "964d03b"  # the ref the recorded dispositions were derived against

# The two tables differ in shape: merges are `| duplicate | survivor | reason |`,
# drops are `| item | reason |` with prose in the second column. Match each on its
# own terms — a single regex demanding an id in column 2 silently drops every drop.
MERGE_ROW_RE = re.compile(
    r"^\|\s*([A-Z]{2,4}-[A-Z0-9]{4})\s*\|\s*([A-Z]{2,4}-[A-Z0-9]{4})\s*\|"
)
DROP_ROW_RE = re.compile(r"^\|\s*([A-Z]{2,4}-[A-Z0-9]{4})\s*\|")

SURVIVOR_OK = {"open", "promoted"}  # in-flight is a fine fold target
DUPLICATE_OK = {"open"}             # in-flight work must not be folded away


def _show(ref: str, path: str) -> str:
    out = subprocess.run(["git", "show", f"{ref}:{path}"],
                         capture_output=True, text=True, check=True)
    return out.stdout


def _by_id(text: str) -> dict[str, legacy.BacklogItem]:
    parsed = legacy.parse_backlog(text)
    items = {i.item_id: i for i in parsed.items if i.item_id}
    if not items:
        raise SystemExit(
            f"{BACKLOG}: parsed {len(parsed.items)} bullet(s), none with an item id — "
            "refusing to report drift against an empty parse."
        )
    return items


def recorded_dispositions(text: str) -> tuple[list[tuple[str, str]], list[str]]:
    """Parse the merge table (duplicate -> survivor) and the drop table."""
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
    now = _by_id(Path(BACKLOG).read_text(encoding="utf-8"))
    then = _by_id(_show(ref, BACKLOG))
    merges, drops = recorded_dispositions(Path(DECISIONS).read_text(encoding="utf-8"))

    open_then = sum(1 for i in then.values() if i.status == "open")
    open_now = sum(1 for i in now.values() if i.status == "open")
    growth = (100 * open_now // open_then - 100) if open_then else 0
    print(f"== corpus drift since {ref} (via lib.backlog.legacy) ==")
    print(f"items: {len(then)} -> {len(now)}   open: {open_then} -> {open_now} (+{growth}%)")

    print(f"\n-- recorded merges ({len(merges)}) --")
    stale_merges = 0
    for dup, surv in merges:
        problems = []
        d, s = now.get(dup), now.get(surv)
        if d is None:
            problems.append(f"{dup} absent")
        elif d.status == "promoted":
            # In-flight work the recorded fold would close as a duplicate.
            problems.append(f"{dup} is promoted — folding it would close in-flight work")
        elif d.status not in DUPLICATE_OK:
            # Already disposed some other way: the fold is a no-op, not a hazard.
            problems.append(f"{dup} is already {d.status} — the merge is a no-op")
        if s is None:
            problems.append(f"survivor {surv} absent")
        elif s.status not in SURVIVOR_OK:
            problems.append(f"survivor {surv} is {s.status}")
        stale_merges += bool(problems)
        note = ("; ".join(problems) if problems
                else f"ok ({d.status} -> {s.status})")
        print(f"  {dup} -> {surv}: {note}")

    print(f"\n-- recorded drops ({len(drops)}) --")
    stale_drops = 0
    for did in drops:
        item = now.get(did)
        if item is None:
            print(f"  {did}: absent")
            stale_drops += 1
        elif item.status != "open":
            print(f"  {did}: already {item.status} — drop is a no-op")
            stale_drops += 1
        else:
            print(f"  {did}: ok (open)")

    new_open = {k: v for k, v in now.items() if k not in then and v.status == "open"}
    share = (100 * len(new_open) // open_now) if open_now else 0
    print("\n-- never surveyed --")
    print(f"  {len(new_open)} open item(s) filed since {ref} — {share}% of the open corpus, "
          f"outside every recorded disposition")
    for key in sorted(new_open):
        added = new_open[key].metadata.get("added", "?")
        print(f"    {key}  {added}  {new_open[key].title[:96]}")

    verdict = "CURRENT" if not (stale_merges or stale_drops or new_open) else "STALE"
    print(f"\nverdict: dispositions are {verdict} "
          f"({stale_merges} merge issue(s), {stale_drops} drop no-op(s), "
          f"{len(new_open)} unsurveyed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
