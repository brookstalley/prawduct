#!/usr/bin/env python3
"""Measure parsed backlog title lengths against the issue standard's budgets.

The derivation behind `artifacts/backlog-import-title-boundary-discovery.md`, kept
runnable so its numbers are falsifiable. A count transcribed into prose goes stale
silently as a corpus grows; cite this command rather than the digits.

    tools/measure-backlog-titles.py .prawduct/backlog.md
    tools/measure-backlog-titles.py ../discodon/.prawduct/backlog.md

Reports, per corpus: how many parsed titles exceed the authoring budget
(`issuefmt.TITLE_MAX`, 72) and how many exceed GitHub's hard 422 boundary
(`legacy.GITHUB_TITLE_HARD_CAP`, 256), plus how many items carry an `[areas: …]`
marker. The marker count is the load-bearing one: it is what distinguishes a corpus
whose long titles are *prose bleed* from one whose long titles are genuinely
authored, and the boundary rule is only correct for the first.

Two things to know before citing a number from this script:

* It imports the **current** parser, so it always reports the post-fix state. To
  measure a corpus against the pre-boundary parser, run it against that revision's
  ``legacy.py`` — this tree cannot reproduce a "before" figure.
* The marker count is an **upper bound** on the boundary rule's reach. It matches
  title *and* body, because the rule moves the marker into the body — so a corpus
  that authors ``[areas: …]`` on a following body line, which the rule never cuts
  at, is counted here too.

Exit 1 if any title exceeds the hard cap — that corpus cannot be imported.
"""

from __future__ import annotations

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "plugin" / "lib"))

from backlog import issuefmt, legacy  # noqa: E402


def measure(path: Path) -> int:
    items = legacy.parse_backlog(path.read_text(encoding="utf-8")).pending_items()
    if not items:
        print(f"{path}: no pending items")
        return 0
    lengths = [len(i.title) for i in items]
    marked = sum(1 for i in items if legacy.INLINE_AREAS_RE.search(i.title + i.body))
    over_cap = sum(1 for n in lengths if n > legacy.GITHUB_TITLE_HARD_CAP)
    print(f"{path}")
    print(f"  pending items        {len(items)}")
    print(f"  title length         max {max(lengths)}  median {int(statistics.median(lengths))}")
    print(f"  over authoring norm  {sum(1 for n in lengths if n > issuefmt.TITLE_MAX)} (> {issuefmt.TITLE_MAX})")
    print(f"  over GitHub's cap    {over_cap} (> {legacy.GITHUB_TITLE_HARD_CAP}) <- blocks import")
    print(f"  carry [areas:] marker {marked} (title or body — upper bound)")
    return 1 if over_cap else 0


def main(argv: list[str]) -> int:
    paths = [Path(a) for a in argv[1:]] or [Path(".prawduct/backlog.md")]
    missing = [p for p in paths if not p.is_file()]
    if missing:
        for p in missing:
            print(f"error: no such backlog: {p}", file=sys.stderr)
        return 2
    return max(measure(p) for p in paths)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
