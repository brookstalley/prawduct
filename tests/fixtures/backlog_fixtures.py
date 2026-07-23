"""Recorded backlog fixtures (Test Specs §6) for the migration guard-sweep.

- ``DISCODON_MINI`` — a representative ``.prawduct/backlog.md`` slice + archive
  lines (drives MIG-1 / CRASH-4). Covers all five statuses across the three
  sections (Open / Promoted / Archive), a ``related`` cross-ref, and preserved
  metadata keys (``added``/``related``) that must round-trip through the block.
- ``multi_prefix_backlog`` — prawduct's own ``BKL/ADR/ADV/MET/CRT`` prefix set
  plus a synthetic single-use spread (MIG-2's 27–58 hand-minted prefixes).

The exact markdown shape (2-space-indented metadata bar + blank + body) mirrors
the real ``.prawduct/backlog.md`` so the same ``lib.backlog.legacy`` parser reads
both — the fixture is faithful to what the real migration will consume (Chunk 06).
"""

from __future__ import annotations

DISCODON_MINI = """# Backlog — discodon-mini

<!-- fixture: a representative backlog.md slice for the migration guard-sweep. -->

## Open

- **[DIS-0001]** Add the harbor map overlay
  `effort: M · impact: L · area: ui · source: user · added: 2026-05-01 · status: open · stage: ready`

  Players want a top-down harbor map. Renders the docks and the tide line.

- **[DIS-0002]** Rate-limit the trade API
  `effort: S · impact: M · area: backend · source: builder · added: 2026-05-02 · status: in-progress · stage: ready · related: DIS-0001`

  Bursts of trades exceed the upstream cap.

## Promoted

- **[DIS-0003]** Ship the onboarding tutorial
  `effort: L · impact: L · area: ux · source: user · added: 2026-04-20 · status: submitted · stage: design`

  A guided first-run flow that teaches docking and trading.

## Archive

- **[DIS-0004]** Fix the crash on empty inventory
  `effort: S · impact: M · area: backend · source: builder · added: 2026-03-01 · status: shipped`

  A null deref when the cargo hold is empty.

- **[DIS-0005]** Speculative fog-of-war idea
  `effort: S · impact: S · area: ui · source: user · added: 2026-02-01 · status: dropped`

  Decided against — too costly for the payoff.
"""

# The prawduct-style multi-prefix set: real recurring prefixes + single-use ones.
_PRAWDUCT_PREFIXES = ("BKL", "ADR", "ADV", "MET", "CRT")


def multi_prefix_backlog(single_use: int = 31) -> str:
    """A backlog with the prawduct recurring prefixes plus ``single_use`` prefixes
    used exactly once (the MIG-2 stress: 27–58 hand-minted prefixes/project, each
    → a permanent ``id:PFX`` alias, no new PFX minted)."""
    lines = ["# Backlog — multi-prefix", "", "## Open", ""]
    n = 0
    for prefix in _PRAWDUCT_PREFIXES:
        n += 1
        lines += _item(f"{prefix}-{1000 + n:04d}", f"{prefix} recurring item {n}")
    for i in range(single_use):
        n += 1
        # A distinct single-use prefix per item (P00, P01, …) — the once-only spread.
        lines += _item(f"P{i:02d}-{2000 + n:04d}", f"single-use prefix item {n}")
    return "\n".join(lines) + "\n"


def _item(pfx: str, title: str) -> list[str]:
    return [
        f"- **[{pfx}]** {title}",
        "  `effort: M · impact: M · area: core · source: builder · added: 2026-06-01 · status: open · stage: ready`",
        "",
        f"  Body for {pfx}.",
        "",
    ]
