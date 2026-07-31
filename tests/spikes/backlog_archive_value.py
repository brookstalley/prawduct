"""Backlog archive value — the derivation behind MG4(b)'s reference-closure invariant.

Committed rather than discarded because every figure it produces is a count over a
corpus that grows: each one is stale the moment another item is filed or archived.
The requirement it backs (`documentation/backlog-service-requirements.md` MG4(b))
cites this command instead of the digits, deliberately.

    python3 tests/spikes/backlog_archive_value.py            # working tree
    python3 tests/spikes/backlog_archive_value.py 4e08a6c    # any git ref

What it answers, in one pass:

  * Is an archived item inert once shipped? (body substance, per status)
  * Which archived items are load-bearing for LIVE work — i.e. referenced by a
    non-archived item through `related:` / `refs:` / `closes:` / body prose?
  * Would a status-keyed narrow archive scope (`--archive-scope open`, or an
    "open + dropped" pole) preserve the referenced set, or discard it?

The third question is the one that matters at migration time. After cutover the
backlog skill treats the source markdown as frozen history and stops reading it for
live state, so an excluded reference target is *unresolvable*, not merely absent.
That is why MG4(b) makes reference-closure the invariant and treats any status- or
date-keyed window as a starting selection to be closed over, never a final answer.

Not a pytest test: it measures a living corpus, so it has no fixed expected value to
assert. It is a measuring instrument, deliberately kept runnable.
"""
from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter

BACKLOG = ".prawduct/backlog.md"
HEAD_RE = re.compile(r"^- \*\*\[([A-Z]{2,4}-[A-Z0-9]{4})\]\*\* (.+)$")
META_RE = re.compile(r"^\s+`(.*(?:status|added):.*)`\s*$")
ARCHIVE_HEADING = "## Archive"
SUBSTANTIAL = 800  # chars of body below which an item is a stub, not a record


def _load(ref: str | None) -> str:
    if ref is None:
        with open(BACKLOG, encoding="utf-8") as fh:
            return fh.read()
    out = subprocess.run(
        ["git", "show", f"{ref}:{BACKLOG}"],
        capture_output=True, text=True, check=True,
    )
    return out.stdout


def parse(text: str) -> dict[str, dict]:
    """Item id -> {status, archived, meta, body}. Archive membership is positional."""
    items: dict[str, dict] = {}
    cur: str | None = None
    archived = False
    for line in text.splitlines():
        if line.startswith(ARCHIVE_HEADING):
            archived = True
        head = HEAD_RE.match(line)
        if head:
            cur = head.group(1)
            items[cur] = {"status": "?", "archived": archived, "meta": "", "body": []}
            continue
        if cur is None:
            continue
        meta = META_RE.match(line)
        if meta and not items[cur]["meta"]:
            items[cur]["meta"] = meta.group(1)
            found = re.search(r"status:\s*([a-z-]+)", meta.group(1))
            if found:
                items[cur]["status"] = found.group(1)
        else:
            items[cur]["body"].append(line)
    return items


def body_chars(item: dict) -> int:
    return sum(len(line.strip()) for line in item["body"])


def main(argv: list[str]) -> int:
    ref = argv[1] if len(argv) > 1 else None
    items = parse(_load(ref))
    archive = {k: v for k, v in items.items() if v["archived"]}
    live = {k: v for k, v in items.items() if not v["archived"]}

    where = ref or "working tree"
    print(f"== {BACKLOG} @ {where} ==")
    print(f"live: {len(live)} item(s) | archive: {len(archive)} item(s)")
    print("archive by status:", dict(Counter(v["status"] for v in archive.values())))

    # Every live item's text, as the reference surface.
    live_text = "\n".join(
        v["meta"] + "\n" + "\n".join(v["body"]) for v in live.values()
    )

    print("\n-- is an archived item inert? --")
    by_status: dict[str, list[str]] = {}
    for key, item in archive.items():
        by_status.setdefault(item["status"], []).append(key)

    referenced_total = 0
    for status, keys in sorted(by_status.items(), key=lambda kv: -len(kv[1])):
        sizes = sorted(body_chars(archive[k]) for k in keys)
        median = sizes[len(sizes) // 2] if sizes else 0
        stubs = sum(1 for s in sizes if s < 40)
        rich = sum(1 for s in sizes if s > SUBSTANTIAL)
        refd = [k for k in keys if k in live_text]
        referenced_total += len(refd)
        pct = (100 * len(refd) // len(keys)) if keys else 0
        print(
            f"  {status:<8} n={len(keys):<4} median body {median:>6} chars  "
            f"empty={stubs:<3} >{SUBSTANTIAL}ch={rich:<4} "
            f"referenced by live work: {len(refd)} ({pct}%)"
        )

    print("\n-- would a status-keyed narrow scope be reference-closed? --")
    for label, kept_statuses in (
        ("--archive-scope open  (drop all archived)", set()),
        ("open + dropped        (keep dropped only)", {"dropped"}),
    ):
        excluded = [k for k, v in archive.items() if v["status"] not in kept_statuses]
        broken = [k for k in excluded if k in live_text]
        verdict = "REFERENCE-CLOSED" if not broken else f"BREAKS {len(broken)} reference(s)"
        print(f"  {label}: excludes {len(excluded):<4} -> {verdict}")

    print(
        f"\narchive items referenced by live work, all statuses: "
        f"{referenced_total} of {len(archive)}"
    )
    print(
        "MG4(b): reference-closure is the invariant; a status or date window is a "
        "starting selection, not a final answer."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
