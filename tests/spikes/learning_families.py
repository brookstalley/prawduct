#!/usr/bin/env python3
"""Classify `.prawduct/learnings.md` into the near-duplicate families a collapse
would target, and print the roster.

**Not a CI test.** It is committed because every count about the corpus in
`build-plan-learnings-firing.md` is a *claim about the corpus*, and a claim about
a set that grows should ship with the way to recompute it rather than a digit
transcribed into prose (`learnings.md`: "a spike that discards its code leaves
its numbers unfalsifiable — commit the derivation as a runnable script and cite
the command, never the digits").

Run from the repo root::

    python3 tests/spikes/learning_families.py
    python3 tests/spikes/learning_families.py --family assertion --full

**This is a CANDIDATE GENERATOR, not an authority.** It matches heading text,
which is a proxy for what a rule is about. Two consequences the caller must hold
on to. A rule can belong to a family and use none of its words — a false
negative this script cannot see, and the reason the keep/merge map is read
against the whole corpus rather than against this output alone. And membership
is not the collapse decision: the test for retiring a member is *does it
contribute an instance the general statement cannot generate?*, which no keyword
match can answer. Everything is "covered by" the general rule; that is exactly
what makes collapse feel like progress while it removes discriminating power.

Plan path note: the plan named `scripts/learning-families.py`. There is no
`scripts/` directory; `tests/spikes/` is where this repo already keeps committed
derivations (`roster_rule_replay.py`, `backlog_archive_value.py`, …) with a
stated convention. The goal — the derivation ships as a runnable command — is
met; the prescribed path was method (`architecture.md`: goals bind, prescribed
method is advice).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LEARNINGS = REPO_ROOT / ".prawduct" / "learnings.md"

#: General rules each family would collapse into, by heading prefix. These are
#: the *destinations*, and they are excluded from their own family's roster —
#: a general rule is not a duplicate of itself.
#: `assertion` collapses into a rule that already exists. `discriminating` does
#: NOT: its destination is the new rule Chunk 03(a) adds, so until that lands
#: there is nothing to exclude and every match is a member — including
#: "model the READER", which is a member of the family, not its head. Naming an
#: existing rule as the destination here (the first cut named line 320) silently
#: drops that rule from its own roster and understates the family by one.
FAMILY_GENERALS = {
    "assertion": "Anything in a durable artifact that one command could check is a CLAIM",
    "discriminating": None,   # added by Chunk 03(a): "green is evidence only about what could have made it red"
}

#: Signatures, deliberately narrow. A broad net (`test|assert|verify|claim`)
#: matches ~60 of 159 headings, which is not a family — it is the topic of the
#: whole corpus. Each pattern below names a *mechanism*, not a subject area.
FAMILIES: dict[str, list[str]] = {
    # Family 1 — a durable statement is a claim, and a claim needs its
    # falsifier RUN. Collapses into line 292.
    "assertion": [
        r"\bis a CLAIM\b",
        r"\bcompleteness claim\b",
        r"\babsence-claim\b",
        r"\bfalsif(y|ying|ies)\b",
        r"\bthe (one )?query that would falsify\b",
        r"\bverify .*before (writing|recording|asserting|crediting)\b",
        r"\bis a claim about the tree\b",
        r"\bstate what a FAILING run would have looked like\b",
        r"\ba lead, not ground truth\b",
        r"\brationale you reached for\b",
    ],
    # Family 2 — green is evidence only about what could have made it red: the
    # test/guard that cannot discriminate the defect it names.
    "discriminating": [
        r"\bmodel the READER\b",
        r"\bassert the PROPERTY, not one spelling\b",
        r"\basserts a SUBSTRING\b",
        r"\bprove it by mutation\b",
        r"\bgate on THAT event\b",
        r"\bfixture\b",
        r"\bfalse coverage\b",
        r"\bnon-?discriminating\b",
        r"\bsilently narrows the requirement\b",
        r"\bpassed for the wrong reason\b",
        r"\bcan pass because\b",
        r"\btest the collision case\b",
    ],
}


def headings(text: str) -> list[tuple[int, str]]:
    """(1-based line number, heading text) for every `## ` entry."""
    return [
        (i + 1, line[3:].strip())
        for i, line in enumerate(text.split("\n"))
        if line.startswith("## ")
    ]


def classify(entries: list[tuple[int, str]]) -> dict[str, list[tuple[int, str]]]:
    out: dict[str, list[tuple[int, str]]] = {name: [] for name in FAMILIES}
    for lineno, title in entries:
        for name, patterns in FAMILIES.items():
            general = FAMILY_GENERALS[name]
            if general is not None and title.startswith(general):
                continue  # the destination is not a member of its own family
            if any(re.search(p, title, re.IGNORECASE) for p in patterns):
                out[name].append((lineno, title))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--family", choices=sorted(FAMILIES), help="one family only")
    ap.add_argument("--full", action="store_true", help="whole heading, not truncated")
    args = ap.parse_args()

    if not LEARNINGS.is_file():
        print(f"no learnings file at {LEARNINGS}", file=sys.stderr)
        return 1

    entries = headings(LEARNINGS.read_text(encoding="utf-8"))
    families = classify(entries)
    width = 10_000 if args.full else 108

    print(f"corpus: {len(entries)} rules in {LEARNINGS.relative_to(REPO_ROOT)}\n")

    both = set()
    for name in sorted(families):
        if args.family and name != args.family:
            continue
        members = families[name]
        print(f"=== family '{name}' — {len(members)} candidate member(s) ===")
        dest = FAMILY_GENERALS[name]
        print("    collapse destination: " + (dest or
              "NEW rule, added by Chunk 03(a) — does not exist yet, so nothing is excluded"))
        for lineno, title in members:
            shown = title if len(title) <= width else title[: width - 1] + "…"
            print(f"    :{lineno:<4} {shown}")
        print()

    for name, members in families.items():
        for lineno, title in members:
            if sum(1 for m in families.values() if (lineno, title) in m) > 1:
                both.add((lineno, title))
    if both and not args.family:
        print(f"=== in BOTH families — {len(both)}, each needs a per-rule call ===")
        for lineno, title in sorted(both):
            print(f"    :{lineno:<4} {title[:width]}")
        print()

    print(
        "Membership is a candidate, not a verdict. The keep/merge test is NOT\n"
        "'is this covered by the general rule?' — everything is. It is 'does this\n"
        "contribute an instance the general statement cannot generate?' A member\n"
        "that does retires and its instance moves INTO the successor's heading."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
