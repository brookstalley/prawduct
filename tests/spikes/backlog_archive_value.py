"""Backlog archive value — the derivation behind MG4(b)'s reference-closure invariant.

Committed rather than discarded because every figure it produces is a count over a
corpus that grows: each one is stale the moment another item is filed or archived.
The requirement it backs (`documentation/backlog-service-requirements.md` MG4(b))
cites this command instead of the digits, deliberately.

    python3 tests/spikes/backlog_archive_value.py            # working tree
    python3 tests/spikes/backlog_archive_value.py 4e08a6c    # any git ref

What it answers, in one pass:

  * Is an archived item inert once shipped? (body substance, per status)
  * Which archived items are load-bearing for LIVE work — i.e. named by a
    non-archived item anywhere: its title, ANY metadata value, or its body. Not
    just `related:` / `closes:` / `refs:`, because DM1 makes the field vocabulary
    extensible, so an id can live in a field this instrument has never heard of.
  * Would a status-keyed narrow archive scope (`--archive-scope open`, or an
    "open + dropped" pole) preserve the referenced set, or discard it?

The third question is the one that matters at migration time. After cutover the
backlog skill treats the source markdown as frozen history and stops reading it for
live state, so an excluded reference target is *unresolvable*, not merely absent.
That is why MG4(b) makes reference-closure the invariant and treats any status- or
date-keyed window as a starting selection to be closed over, never a final answer.

Reads through ``lib.backlog.legacy.parse_backlog`` — the same parser the importer
reads the source through (``migrate.py`` → ``legacy.parse_backlog``). A hand-rolled
parser here would measure a different item set than the migration acts on, which is
precisely the divergence this instrument exists to rule out.

Not a pytest test: it measures a living corpus, so it has no fixed expected value to
assert. It is a measuring instrument, deliberately kept runnable.
"""
from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

_SPIKE_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _SPIKE_DIR.parent.parent / "plugin"
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from lib.backlog import legacy  # noqa: E402

BACKLOG = ".prawduct/backlog.md"
ARCHIVE_SECTION = "Archive"
ID_RE = re.compile(r"\b[A-Z]{2,4}-[A-Z0-9]{4}\b")
SUBSTANTIAL = 800  # chars of body above which an item is a record, not a stub
STUB = 40          # chars of body below which an item carries no recoverable content


def _load(ref: str | None) -> str:
    if ref is None:
        return Path(BACKLOG).read_text(encoding="utf-8")
    out = subprocess.run(
        ["git", "show", f"{ref}:{BACKLOG}"],
        capture_output=True, text=True, check=True,
    )
    return out.stdout


def _outbound_ids(item: legacy.BacklogItem) -> set[str]:
    """Every item id this item points at — from its title, metadata bar and body.

    MG4(b) names `related:` / `refs:` / `closes:` as the load-bearing edges, but this
    scans **every** metadata value plus the title and the body, because a reference
    that breaks at cutover breaks wherever it was written. A title routinely names the
    item it supersedes or blocks; body prose naming an id is as much a reference as a
    metadata field.

    **Why every metadata value, not just the three named fields.** `legacy`
    keeps the metadata bar out of `.body`, so reading only `related`/`refs`/`closes`
    would silently drop ids living in any other field (`closed-by:`, `revisit:`, a
    project's own soft-enum facet — DM1 makes the vocabulary extensible, so the field
    set is open by design). Missing a reference biases toward calling a narrow scope
    reference-closed, which is the fail-open direction this instrument must not have.
    """
    ids: set[str] = set()
    for value in item.metadata.values():
        ids.update(ID_RE.findall(value))
    ids.update(ID_RE.findall(item.title))
    ids.update(ID_RE.findall(item.body))
    ids.discard(item.item_id or "")
    return ids


def main(argv: list[str]) -> int:
    ref = argv[1] if len(argv) > 1 else None
    backlog = legacy.parse_backlog(_load(ref))

    identified = [i for i in backlog.items if i.item_id]
    if not identified:
        raise SystemExit(
            f"{BACKLOG}: parsed {len(backlog.items)} bullet(s) but none carried an item id. "
            "The file's shape changed or the wrong path was read — refusing to report, "
            "because an empty parse makes every narrow scope look reference-closed."
        )

    archive = [i for i in identified if i.section.strip().lower() == ARCHIVE_SECTION.lower()]
    live = [i for i in identified if i.section.strip().lower() != ARCHIVE_SECTION.lower()]
    if not archive:
        raise SystemExit(
            f"{BACKLOG}: parsed {len(identified)} item(s) but found no '{ARCHIVE_SECTION}' "
            "section. Refusing to report a reference-closure verdict against an archive "
            "this instrument could not find."
        )

    where = ref or "working tree"
    print(f"== {BACKLOG} @ {where} (via lib.backlog.legacy) ==")
    print(f"live: {len(live)} item(s) | archive: {len(archive)} item(s)")
    print("archive by status:", dict(Counter(i.status or "?" for i in archive)))

    # Everything live work points at, from its structured edges and its prose.
    live_targets: set[str] = set()
    for item in live:
        live_targets |= _outbound_ids(item)

    by_status: dict[str, list[legacy.BacklogItem]] = {}
    for item in archive:
        by_status.setdefault(item.status or "?", []).append(item)

    print("\n-- is an archived item inert? --")
    for status, group in sorted(by_status.items(), key=lambda kv: -len(kv[1])):
        sizes = sorted(len(i.body.strip()) for i in group)
        median = sizes[len(sizes) // 2] if sizes else 0
        stubs = sum(1 for s in sizes if s < STUB)
        rich = sum(1 for s in sizes if s > SUBSTANTIAL)
        refd = [i for i in group if i.item_id in live_targets]
        pct = (100 * len(refd) // len(group)) if group else 0
        print(
            f"  {status:<8} n={len(group):<4} median body {median:>6} chars  "
            f"stub<{STUB}ch={stubs:<3} >{SUBSTANTIAL}ch={rich:<4} "
            f"referenced by live work: {len(refd)} ({pct}%)"
        )

    print("\n-- would a status-keyed narrow scope be reference-closed? --")
    for label, kept in (
        ("--archive-scope open  (drop all archived)", set()),
        ("open + dropped        (keep dropped only)", {"dropped"}),
    ):
        excluded = [i for i in archive if (i.status or "?") not in kept]
        broken = [i for i in excluded if i.item_id in live_targets]
        verdict = "REFERENCE-CLOSED" if not broken else f"BREAKS {len(broken)} reference(s)"
        print(f"  {label}: excludes {len(excluded):<4} -> {verdict}")

    total_refd = sum(1 for i in archive if i.item_id in live_targets)
    print(f"\narchive items referenced by live work, all statuses: {total_refd} of {len(archive)}")
    print(
        "MG4(b): reference-closure is the invariant; a status or date window is a "
        "starting selection, not a final answer."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
