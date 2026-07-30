"""Project-preferences enforcement: durable governance prose carries no
suite-total test count.

A number like "1724 tests pass" is true the day it is written and drifts the
next. Nothing consumes it — `prawduct-hook test-evidence record` already holds
pass/fail per tree in the evidence store, which is what every gate reads. The
prose copy exists only to be corrected, and each correction is a commit, and a
commit extends HEAD, which is how a record defect buys a review round. That
mechanism was measured on 2026-07-29: 57% of the day's Critic findings targeted
hand-authored records rather than shipped behavior.

**The subtraction this pins is an absence, and the falsifying command is stated
rather than a count of sites fixed** (learnings: a completeness claim names the
query that would disprove it). Run it yourself:

    grep -rnE '[0-9]{3,6} *(tests?|passing|green)' plugin --include='*.md'

It returns nothing today. It returned nothing before this test existed either —
the sweep found the plugin surface already clean, and no surface *demanded* a
count in the first place. That is exactly why the guard is worth having: the
habit lives in agents, not in a template, so there is no instruction to delete
and nothing but a tripwire will keep the surface clean. `lib/record_lint.py`
carries the runtime half — the same pattern, over the added lines of changed
records, reported to the builder at Critic dispatch.

`plugin/CHANGELOG.md` is in scope: it is the most durable prose the framework
publishes. It is clean, and it should stay that way.

Detection is a property scan, not a literal: the pattern matches any phrasing
that puts a 3+ digit number next to a test/pass word, or any "full suite"/"total"
framing with a number, so a reworded claim fails the same way the one that
prompted it would. The lint module owns the pattern; this test imports it rather
than restating it, so the two can never drift into disagreeing about what a
suite-total claim is.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PLUGIN_ROOT = REPO_ROOT / "plugin"

sys.path.insert(0, str(PLUGIN_ROOT))
from lib import record_lint  # noqa: E402


def _markdown_surfaces() -> list[Path]:
    """Every durable markdown surface the plugin ships — methodology guides,
    templates, skill prose, docs, and the published changelog."""
    return sorted(p for p in PLUGIN_ROOT.rglob("*.md") if p.is_file())


def test_no_plugin_surface_exhibits_a_suite_total() -> None:
    offenders: list[str] = []
    for path in _markdown_surfaces():
        text = path.read_text(encoding="utf-8")
        for line_num, line in enumerate(text.splitlines(), start=1):
            match = record_lint._SUITE_TOTAL_RE.search(line)
            if match:
                rel = path.relative_to(REPO_ROOT)
                offenders.append(f"{rel}:{line_num}: {match.group(0).strip()!r}")
    assert not offenders, (
        "durable plugin prose must not carry a suite-total test count — the "
        "evidence store records pass/fail per tree and a prose copy only drifts:\n"
        + "\n".join(offenders)
    )


#: The DEMAND side: a template or instruction that asks for a count leaves a
#: *slot* for one — `**Tests:** N passing`, `<count> tests`, `[number] tests`.
#: Scanning for the slot rather than for the words "test count" is what keeps
#: this from firing on prose that merely discusses the rule (this file, and the
#: review-cycle table that documents the check, both do). A guard that cannot
#: tell a prohibition from a demand gets deleted the first time it cries wolf.
#: The slot must plausibly hold a NUMBER. A bracketed placeholder alone is not
#: enough — `test-specifications.md` legitimately writes `**Test: [descriptive
#: name]**`, and a guard that reads that as a count slot would be wrong about
#: the one template most likely to be edited. Case is load-bearing on the bare
#: placeholders: `N`/`X` are uppercase by convention, and matching them
#: case-insensitively fires on any prose containing "x tests" or "n passing".
_NUM_WORD = r"(?:[Nn]{1,3}|[Xx]|[Cc]ount|[Nn]umber|[Tt]otal|[Nn]um|#)"
_SLOT = rf"(?:N|X|NNN|<\s*{_NUM_WORD}\s*>|\[\s*{_NUM_WORD}\s*\])"
_COUNT_SLOT_RE = re.compile(
    rf"(?<![\w`]){_SLOT}\s*(?:[Tt]ests?|[Pp]assing|[Aa]ssertions?)\b"
    rf"|\b(?:[Tt]ests?|[Ss]uite)\s*:\s*{_SLOT}(?![\w-])"
)


def test_no_plugin_surface_requests_a_test_count() -> None:
    """The demand side. No template field, methodology step, or skill
    instruction may leave an author a slot to write a suite total into."""
    offenders: list[str] = []
    for path in _markdown_surfaces():
        text = path.read_text(encoding="utf-8")
        for line_num, line in enumerate(text.splitlines(), start=1):
            match = _COUNT_SLOT_RE.search(line)
            if match:
                rel = path.relative_to(REPO_ROOT)
                offenders.append(f"{rel}:{line_num}: {match.group(0).strip()!r}")
    assert not offenders, (
        "no plugin surface may leave a slot for a suite-total test count:\n"
        + "\n".join(offenders)
    )


def test_the_demand_detector_is_red_on_a_planted_slot() -> None:
    for planted in ("**Tests:** N passing", "<count> tests pass", "Tests: [number]"):
        assert _COUNT_SLOT_RE.search(planted), (
            f"the demand detector missed the slot in {planted!r}"
        )


def test_the_demand_detector_ignores_prose_about_the_rule() -> None:
    """This file and `review-cycle.md`'s check table both say the words "test
    count" while forbidding one. Neither may trip the guard."""
    for benign in (
        "A suite-total test claim in durable prose is a NOTE.",
        "no plugin surface may request a suite-total test count",
        "- **Tests:** unit — `store.py` CRUD; integration — GET / renders seeded items",
        "     **Test: [descriptive name]**",
        "     **Test: [Entity] [StartState] → [EndState]**",
    ):
        assert not _COUNT_SLOT_RE.search(benign), (
            f"the demand detector fired on {benign!r}, which forbids or omits a count"
        )


def test_the_detector_is_red_on_a_planted_claim() -> None:
    """Mutation proof — the scan above passes because the surface is clean, not
    because the pattern matches nothing. Phrasings here are deliberately
    DIFFERENT from each other and from anything the repo ever wrote, so the
    guard is a property and not one remembered sentence."""
    for planted in (
        "**Tests:** 1812 passing (+8).",
        "1012 tests pass.",
        "full suite 849 green",
        "the whole suite (2913 tests) is clean",
    ):
        assert record_lint._SUITE_TOTAL_RE.search(planted), (
            f"the suite-total detector missed {planted!r} — a guard that only "
            "matches the phrasing that prompted it passes for every rewording"
        )


def test_the_detector_ignores_scoped_and_delta_counts() -> None:
    """The counter-direction: a delta or a scoped count is a different claim and
    must not trip the guard, or the tripwire becomes noise and gets ignored."""
    for benign in (
        "New regression class `TestFoo` (+14 tests).",
        "28 tests cover the recognizer.",
        "0 blocking, 3 warning, 2 note across 1 reviewer(s).",
        "Released as v3.2.1 with 2 fixes.",
    ):
        assert not record_lint._SUITE_TOTAL_RE.search(benign), (
            f"the suite-total detector fired on {benign!r}, which is not a suite total"
        )
