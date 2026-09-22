"""The two over-fixing rules carry a severity bound at every surface that states them.

#833. Both rules are correct about blockers and actively harmful about notes:
unbounded, they pull a builder into fixing findings that gate nothing, and each
such fix on a judgeable file buys a whole review round. Measured over the
governance ledger on 2026-09-18: `verify-resolutions` is 58% of all review
volume at the worst yield of any mode, and **41 of the 83 scopes with two or
more verify rounds found ZERO blocking findings across all of them**.

**Why a test and not a careful edit.** These two sentences have ten carriers
across five directories, two of which (`migrate_plugin.py`, `anchor_repair.py`)
write the text into every governed product's own `CLAUDE.md`. A rule you must
remember to restate consistently across ten files is the weakest form of that
rule — `core.md` says to convert it into something that runs. This runs.

**What turns this red:** any carrier stating either rule without its bound, and
any NEW carrier appearing anywhere under the scanned roots. The second is the
half a hand-maintained list cannot deliver, and it is why the search is over the
tree rather than over `CARRIERS`.

**What it deliberately does not cover:** whether the bound is *correctly worded*
at each site. It asserts the bound is PRESENT in the same semantic unit as the
claim, not that the surrounding sentence is true. Prose sense is a reviewer's
job; presence is a grep's, and a grep does not get tired on the tenth file.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

#: Roots a carrier could legitimately live under. Deliberately wider than the
#: set of files that carry one today: the failure this guards against is a
#: carrier ADDED without its bound, which a list of known carriers cannot see.
SCAN_ROOTS = ("plugin", ".claude/rules")

#: Two vocabularies sharing no word. `core.md`: a clean sweep usually indicts
#: the query, because grep returns sites phrased in your words and the
#: survivors are the ones that paraphrase.
RULE_VOCAB = {
    # Anchored on the RULE, not on the phrase. A bare `pre-?existing` also
    # matches a dozen incidental docstring uses ("the pre-existing text",
    # "a pre-existing untracked file"), none of which state an obligation —
    # so the first version of this sweep reported nine false carriers and
    # would have taught its next reader to widen the bound, not the query.
    "no pre-existing exception": r'pre-?existing["*]{0,2}\s+(?:exception|is an escape hatch)',
    "deep context is a FIX signal": r"[Dd]eep context on a small problem",
}

#: Release history is excluded, and by FILENAME rather than by directory: a
#: shipped changelog section records what a past release said, and amending it
#: would be rewriting history rather than governing new work. This is a
#: per-file call only because these files are wholly historical — a file mixing
#: released and unreleased sections would need the per-SECTION test instead.
HISTORY = ("CHANGELOG.md", "change-log.md")

#: `anchor_repair.py` holds ONLY superseded `CLAUDE.md` anchors — the exact bytes
#: sitting in already-onboarded repos, which `repair` matches byte for byte to
#: decide whether a repo is repairable. Amending them to carry the bound would
#: grade every repo onboarded on that version `stale-modified` and refuse it a
#: repair, which is the failure the archive exists to prevent. So this is
#: history in the same sense a changelog section is, and it is excluded for the
#: same reason.
#:
#: The exclusion is only sound while the CURRENT anchor lives elsewhere, so
#: `test_the_anchor_archive_holds_no_current_anchor` pins that rather than
#: leaving it as a comment — an exemption with no reachability check is an
#: environment-shaped hole.
ARCHIVE_ONLY = ("anchor_repair.py",)

#: What counts as the bound being present. Matched against the whole semantic
#: unit, never one physical line — line structure is not semantic structure,
#: and every one of these bounds wraps.
BOUND = re.compile(r"BLOCKING|blocking severity")


#: Splits a document into the smallest span that can carry a claim AND its
#: bound: blank lines, list items, and table rows.
#:
#: **Not the blank-line block.** That was the first cut, and a mutation sweep
#: against the real tree caught it: in a bullet LIST the whole list is one
#: block, so a neighbouring bullet's "**BLOCKING**" satisfied the check for
#: every bullet in it. Reverting the bound in `goals-1-3.md` and in
#: `review-cycle.md` left the suite green — an assertion bound to a CONTAINER
#: passes on any part of it, and the container here was the wrong size by
#: exactly one nesting level.
_UNIT_BOUNDARY = re.compile(r"\n\s*\n|\n(?=\s*[-*|]\s)|\n(?=\s*\d+\.\s)")


def _semantic_units(text: str) -> list[str]:
    """The spans a claim and its bound must share, whitespace collapsed.

    Collapsing matters because every one of these bounds WRAPS: a line-based
    scan reported four of ten carriers unbounded when they were not, the first
    time this sweep was run by hand.
    """
    return [" ".join(block.split()) for block in _UNIT_BOUNDARY.split(text)]


def _carriers() -> list[tuple[Path, str, str]]:
    """Every (file, rule, unit) stating one of the two rules, found by walking
    the tree rather than by consulting a list."""
    found = []
    for root in SCAN_ROOTS:
        base = ROOT / root
        assert base.is_dir(), f"scan root {root!r} does not exist — this sweep would scan nothing"
        for path in sorted(base.rglob("*")):
            if path.suffix not in (".md", ".py") or not path.is_file():
                continue
            if path.name in HISTORY or path.name in ARCHIVE_ONLY:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for unit in _semantic_units(text):
                for rule, pattern in RULE_VOCAB.items():
                    if re.search(pattern, unit):
                        found.append((path, rule, unit))
    return found


def test_the_sweep_finds_the_carriers_it_claims_to_scan():
    """A check whose subject is a SET asserts the set is non-empty and holds
    what the check names — otherwise green means "nothing was looked at", and
    it means that forever.

    The three named files are the ones whose absence would be silent and
    expensive: `migrate_plugin.py` propagates into consumer repos,
    `session-digest.md` is always-injected, and `principles.md` is the principle
    itself. `anchor_repair.py` is the fourth consumer-facing carrier and is
    deliberately NOT required here — it is exempt from the sweep as archived
    history, and `test_the_anchor_archive_holds_no_current_anchor` guards it
    instead.
    """
    carriers = _carriers()
    assert carriers, "the sweep found no carriers at all — it is scanning the wrong tree"
    files = {p.relative_to(ROOT).as_posix() for p, _, _ in carriers}
    for required in (
        "plugin/docs/principles.md",
        "plugin/methodology/session-digest.md",
        "plugin/lib/migrate_plugin.py",
    ):
        assert required in files, (
            f"{required} no longer states either rule — if that is deliberate, drop it "
            "from this assertion; if it is not, the rule went missing from a surface "
            "that reaches consumer repos"
        )
    both = {rule for _, rule, _ in carriers}
    assert both == set(RULE_VOCAB), f"only found {both} — one rule's vocabulary stopped matching"


def test_every_carrier_states_its_severity_bound():
    """The requirement, stated as the falsifying query rather than as a count
    of sites fixed — a count is true of any prefix of the real set."""
    unbounded = [
        (path.relative_to(ROOT).as_posix(), rule, unit[:120])
        for path, rule, unit in _carriers()
        if not BOUND.search(unit)
    ]
    assert not unbounded, (
        "these carriers state an over-fixing rule with no severity bound (#833):\n"
        + "\n".join(f"  {p} [{r}]\n    {u}" for p, r, u in unbounded)
    )


@pytest.mark.parametrize(
    "corrupted",
    [
        'No "pre-existing" exception — every finding is yours regardless of when introduced.',
        "**Deep context on a small problem is a FIX signal, not a filing signal.**",
    ],
    ids=["rule-a-unbounded", "rule-b-unbounded"],
)
def test_the_sweep_can_report_a_violation(tmp_path, corrupted, monkeypatch):
    """The positive control.

    `core.md`: a zero from a scan is suspicious until the scan is shown able to
    return non-zero, and a measurement with no positive control cannot support
    a claim. Without this, both assertions above pass identically if
    `RULE_VOCAB` stops matching, if `_semantic_units` returns one giant blob
    containing the word BLOCKING somewhere, or if the walk silently skips every
    file.

    Deliberately phrased as text this repo does NOT contain, so the control
    tests the detector rather than re-testing the tree.
    """
    fake = tmp_path / "plugin" / "docs"
    fake.mkdir(parents=True)
    (fake / "invented.md").write_text(f"# Heading\n\n{corrupted}\n", encoding="utf-8")
    monkeypatch.setattr(f"{__name__}.ROOT", tmp_path)
    monkeypatch.setattr(f"{__name__}.SCAN_ROOTS", ("plugin",))

    carriers = _carriers()
    assert carriers, "the control's own fixture was not found — it proves nothing"
    assert [c for c in carriers if not BOUND.search(c[2])], (
        "the sweep did not flag a deliberately unbounded carrier — it cannot "
        "return non-zero, so its green on the real tree measures nothing"
    )


def test_the_anchor_archive_holds_no_current_anchor():
    """`anchor_repair.py` is exempt from the sweep because it holds only
    SUPERSEDED anchors. That premise is checkable, so it is checked here rather
    than trusted from a comment — the day someone moves the live anchor into
    that module, the exemption silently stops covering history and starts
    hiding the carrier that reaches every governed repo.

    `migrate_plugin.STATIC_ANCHOR` is the current anchor's one home; this
    asserts the archive module defines no competing one and that every name it
    does define is wired into `SUPERSEDED_ANCHORS`.
    """
    src = (ROOT / "plugin" / "lib" / "anchor_repair.py").read_text(encoding="utf-8")
    assert "STATIC_ANCHOR =" not in src, (
        "anchor_repair.py now defines a current anchor, so ARCHIVE_ONLY is "
        "exempting a live carrier from the #833 sweep — move the anchor back to "
        "migrate_plugin.py, or drop the exemption and bound the text"
    )
    declared = set(re.findall(r"^(ANCHOR_V\d+) =", src, re.M))
    assert declared, "no archived anchors found — the exemption is covering nothing"
    wired = re.search(r"SUPERSEDED_ANCHORS: tuple\[str, \.\.\.\] = \(([^)]*)\)", src)
    assert wired, "SUPERSEDED_ANCHORS tuple not found"
    listed = {n.strip() for n in wired.group(1).split(",") if n.strip()}
    assert declared == listed, (
        f"archived anchors {declared ^ listed} are declared but not wired into "
        "SUPERSEDED_ANCHORS (or vice versa) — an unwired archive entry matches "
        "nothing, so those repos are refused a repair"
    )
