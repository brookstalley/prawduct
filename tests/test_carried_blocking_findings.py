"""A verify pass cannot report the review over while a blocker it inherited stands.

The reported failure (#711): a `verify-resolutions` pass discharged one finding
by reference to another — "R-12 is implicitly closed by R-1's fix, same class" —
and wrote a resolution fact for R-1 only. Its own counts were 0 blocking, so it
printed THE REVIEW IS OVER and the operator relayed that. The gate disagreed:
R-12 had no resolution fact and still blocked. By then R-12 sat on a superseded
round no later verify pass would name, so the only route left was a full
`cumulative` — a whole round of bookkeeping for a defect fixed two rounds
earlier.

**Nothing here parses the reviewer's prose, and that is the design.** Minting
R-12's fact from "implicitly closed by" would record a judgment nobody made,
which `data-model.md` forbids outright (a resolution fact requires a
verify-resolutions origin and a pre-existing target finding), and the phrasings
are an open set so a parser that misses one fails silently in the bug's own
direction. The pass simply loses the ability to CLAIM it finished.

The anchor-matching tests are the load-bearing ones. Picking the wrong anchor
would either invent blockers on a clean pass (worse than the bug) or miss the
real one; the store is shared by every worktree of the clone, so "most recent
review fact" is specifically the wrong rule.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PLUGIN = str(Path(__file__).resolve().parent.parent / "plugin")
if _PLUGIN not in sys.path:
    sys.path.insert(0, _PLUGIN)

from lib import critic_consolidate as cc  # noqa: E402


def _review(rid, base, head, findings=()):
    return {
        "kind": "review",
        "id": rid,
        "body": {
            "base_tree": base,
            "head_tree": head,
            "findings": [dict(f) for f in findings],
        },
    }


def _resolution(rid, target_review, fid):
    return {
        "kind": "resolution",
        "id": rid,
        "body": {"finding": {"review_id": target_review, "fid": fid},
                 "disposition": "fixed"},
    }


def _blocking(fid, title="a defect"):
    return {"fid": fid, "severity": "blocking", "title": title}


def test_the_711_sequence_is_caught(tmp_path):
    """Two blocking findings, one fix, one resolution fact written."""
    facts = [
        _review("rev-A", "t0", "t1", [_blocking("R-1"), _blocking("R-12", "the other half")]),
        _resolution("res-1", "rev-A", "R-1"),
        _review("rev-B", "t1", "t2"),
    ]

    carried = cc.carried_blocking(facts, "t1", "rev-B")

    assert [c["fid"] for c in carried] == ["R-12"]
    assert carried[0]["review_id"] == "rev-A"
    assert carried[0]["title"] == "the other half"


def test_a_pass_that_named_everything_carries_nothing(tmp_path):
    """The negative that matters most: no invented blockers on a clean pass."""
    facts = [
        _review("rev-A", "t0", "t1", [_blocking("R-1"), _blocking("R-12")]),
        _resolution("res-1", "rev-A", "R-1"),
        _resolution("res-2", "rev-A", "R-12"),
        _review("rev-B", "t1", "t2"),
    ]

    assert cc.carried_blocking(facts, "t1", "rev-B") == []


def test_a_sibling_worktrees_newer_review_is_not_mistaken_for_the_anchor():
    """The store is shared by every clone worktree.

    "Most recent review fact" would pick `rev-OTHER` here and report its
    blocker as this branch's, which is a fabricated blocker on an unrelated
    branch. The tree link is what makes the anchor this branch's own.
    """
    facts = [
        _review("rev-A", "t0", "t1", [_blocking("R-1")]),
        _resolution("res-1", "rev-A", "R-1"),
        _review("rev-OTHER", "z0", "z1", [_blocking("R-99")]),
        _review("rev-B", "t1", "t2"),
    ]

    assert cc.carried_blocking(facts, "t1", "rev-B") == []


def test_no_anchor_carries_nothing():
    """With no prior review linked to this tree there is nothing inherited."""
    facts = [_review("rev-B", "t1", "t2")]

    assert cc.carried_blocking(facts, "t1", "rev-B") == []
    assert cc.carried_blocking(facts, None, "rev-B") == []


def test_the_pass_does_not_count_itself_as_its_own_anchor():
    facts = [_review("rev-B", "t1", "t1", [_blocking("R-1")])]

    assert cc.carried_blocking(facts, "t1", "rev-B") == []


def test_only_blocking_findings_are_carried():
    facts = [
        _review("rev-A", "t0", "t1", [
            {"fid": "R-2", "severity": "warning", "title": "w"},
            {"fid": "R-3", "severity": "note", "title": "n"},
        ]),
        _review("rev-B", "t1", "t2"),
    ]

    assert cc.carried_blocking(facts, "t1", "rev-B") == []


# --- the sentence the builder and the reviewer both read --------------------

def test_next_action_refuses_to_say_the_review_is_over(tmp_path):
    carried = [{"review_id": "rev-A", "fid": "R-12", "title": "the other half"}]

    line = cc.next_action_line("rev-B", 0, 0, 0, None, carried=carried)

    assert "THE REVIEW IS OVER" not in line
    assert "NOT DONE" in line
    assert "rev-A/R-12" in line
    assert "the other half" in line


def test_next_action_names_the_prose_forms_that_produce_the_bug():
    """The operator needs to recognise what they just did."""
    line = cc.next_action_line(
        "rev-B", 0, 0, 0, None,
        carried=[{"review_id": "rev-A", "fid": "R-12"}],
    )

    assert "implicitly closed by" in line
    assert "`resolutions`" in line


def test_next_action_warns_about_the_supersession_deadline():
    """Acting now is cheap; one more round makes it a full cumulative."""
    line = cc.next_action_line(
        "rev-B", 0, 0, 0, None,
        carried=[{"review_id": "rev-A", "fid": "R-12"}],
    )

    assert "cumulative" in line
    assert "supersede" in line


def test_carried_overrides_the_warning_note_arm_too():
    """A pass with warnings still must not claim the review is over."""
    line = cc.next_action_line(
        "rev-B", 0, 3, 2, None,
        carried=[{"review_id": "rev-A", "fid": "R-12"}],
    )

    assert "THE REVIEW IS OVER" not in line


def test_no_carried_findings_leaves_every_existing_arm_untouched():
    """The additive guarantee: nothing changes when nothing is carried."""
    for blocking, warning, note in [(0, 0, 0), (0, 2, 1), (3, 0, 0)]:
        with_none = cc.next_action_line("rev-B", blocking, warning, note, None)
        with_empty = cc.next_action_line(
            "rev-B", blocking, warning, note, None, carried=[]
        )
        assert with_none == with_empty


def test_every_carried_finding_is_named_not_just_counted():
    """A count tells the operator nothing they can act on."""
    carried = [
        {"review_id": "rev-A", "fid": "R-12"},
        {"review_id": "rev-A", "fid": "R-13"},
    ]

    line = cc.next_action_line("rev-B", 0, 0, 0, None, carried=carried)

    assert "R-12" in line and "R-13" in line
    assert "2 BLOCKING" in line


# --- the wiring, not just the parts -----------------------------------------
#
# Every test above is a unit test of one function. The lines that actually
# DELIVER the sentence are the `is_verify` guard, the store re-read, and the two
# hand-offs — and two plausible regressions there pass the whole suite above
# while restoring the bug: dropping `carried` at the call site (silently
# reinstates #711), and hoisting the computation ABOVE the resolution append
# (invents blockers on a clean pass, which is worse than the bug).

def test_blocking_arm_alone_would_lie_when_a_blocker_was_inherited():
    """The finding that ordering `if blocking:` first produced.

    That arm says "nothing else here does". With an inherited blocker it is
    false, and a builder who believes it fixes only this round's findings,
    re-verifies, and anchors the next pass on THIS review — orphaning the
    inherited id onto a superseded round.
    """
    carried = [{"review_id": "rev-A", "fid": "R-12"}]

    line = cc.next_action_line("rev-B", 2, 0, 0, None, carried=carried)

    assert "nothing else here does" not in line
    assert "R-12" in line
    assert "2 BLOCKING finding(s) of its own" in line


def test_carried_wins_over_every_own_count():
    """No combination of this pass's own counts may suppress the roll-call."""
    carried = [{"review_id": "rev-A", "fid": "R-12"}]
    for blocking, warning, note in [(0, 0, 0), (0, 5, 5), (3, 0, 0), (3, 2, 1)]:
        line = cc.next_action_line("rev-B", blocking, warning, note, None, carried=carried)
        assert "R-12" in line, (blocking, warning, note)
        assert "THE REVIEW IS OVER" not in line, (blocking, warning, note)


def test_cache_record_carries_the_sentence_to_the_builder():
    """`fact_to_cache_record` is the builder's only carrier of this."""
    fact = {
        "id": "rev-B",
        "ts": "2026-08-27T00:00:00Z",
        "body": {"counts": {"blocking": 0, "warning": 0, "note": 0},
                 "findings": [], "roster": [], "mode": "verify-resolutions"},
    }

    record = cc.fact_to_cache_record(
        fact, None, [{"review_id": "rev-A", "fid": "R-12"}]
    )

    assert "R-12" in record["next_action"]
    assert "THE REVIEW IS OVER" not in record["next_action"]


def test_cache_record_without_carried_is_unchanged():
    """The additive guarantee at the call site, not just in the formatter."""
    fact = {
        "id": "rev-B",
        "ts": "2026-08-27T00:00:00Z",
        "body": {"counts": {"blocking": 0, "warning": 0, "note": 0},
                 "findings": [], "roster": [], "mode": "verify-resolutions"},
    }

    assert cc.fact_to_cache_record(fact, None, []) == cc.fact_to_cache_record(fact, None)


def test_carried_is_computed_after_resolution_facts_land():
    """`carried_blocking` reads resolution facts — the property the ordering relies on.

    This is NOT the order-of-operations pin, and an earlier version of this
    docstring wrongly said it was: it never calls `consolidate()`, so it cannot
    catch the computation being hoisted above the resolution-append loop. That
    pin lives in `test_critic_consolidate.py`
    (`TestCarriedBlockersReachTheirReaders`), which drives the real call site.

    What this covers is the property that pin depends on — that a resolution
    fact present in the store removes its finding from the carried set — stated
    directly on two literal fact lists.
    """
    resolved_store = [
        _review("rev-A", "t0", "t1", [_blocking("R-1")]),
        _resolution("res-1", "rev-A", "R-1"),
        _review("rev-B", "t1", "t2"),
    ]
    unresolved_store = [f for f in resolved_store if f["kind"] != "resolution"]

    assert cc.carried_blocking(resolved_store, "t1", "rev-B") == []
    assert cc.carried_blocking(unresolved_store, "t1", "rev-B") != []


def test_the_dispatch_roll_call_names_every_inherited_blocker():
    """The half that acts BEFORE `resolutions` is written."""
    text = cc.account_for_prior_blockers_directive([
        {"review_id": "rev-A", "fid": "R-12", "title": "one"},
        {"review_id": "rev-A", "fid": "R-13", "title": "two"},
    ])

    assert "R-12" in text and "R-13" in text
    assert "must come back with a verdict" in text
    # The distinction the pre-existing claim directive does not draw.
    assert "still its own entry" in text
    assert "genuinely still broken" in text


def test_the_dispatch_roll_call_is_silent_when_there_is_nothing_to_account_for():
    """A directive that fires on every dispatch trains its reader to skip it."""
    assert cc.account_for_prior_blockers_directive([]) == ""
