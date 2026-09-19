"""#167 — refuse a verify pass anchored on a CLEAN verify pass that found only its own churn.

Built to `documentation/issues/167-design.md` D1-D5, with one recorded departure
(`_anchor_named_files` reads observations as well as findings; the docstring there
carries the warrant and the measurement).

**Why the positive control leads this file.** The subject is a REFUSAL, and a guard
that never fires and a guard that *cannot* fire produce the same green. Every
negative case below is only meaningful because `test_the_guard_can_refuse` proves the
path is reachable with the fixtures this module builds.

**Each conjunct is mutated independently**, not the guard as a unit: the predicate is
`anchor-is-a-verify AND zero-unresolved-blocking AND delta-subset-of-named`, which is
three guards wearing one name. Reverted whole it goes red on the first fixture while
the other two stay unpinned.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
sys.path.insert(0, str(ROOT))

from lib import critic_consolidate as cc  # noqa: E402


VERIFY = cc._VERBOSE_VERIFY_RESOLUTIONS


def _anchor(mode=VERIFY, findings=None, observations=None, fid="rev-anchor"):
    return {
        "id": fid,
        "kind": "review",
        "body": {
            "mode": mode,
            "findings": findings if findings is not None else [],
            "observations": observations if observations is not None else [],
            "head_tree": "tree-anchor",
        },
    }


class TestTheNamedSet:
    """`_anchor_named_files` is the departure from D3, so it is pinned directly."""

    def test_the_guard_can_refuse(self):
        """THE POSITIVE CONTROL for this helper: a non-empty named set is
        reachable from an ordinary anchor shape."""
        named = cc._anchor_named_files(_anchor(findings=[{"files": ["a.py"]}])["body"])
        assert named == {"a.py"}

    def test_observations_count_toward_named(self):
        """The departure itself. The inner stage demotes everything below
        BLOCKING into observations, so on a verify anchor `findings` is empty in
        the ORDINARY case — reading findings alone ships the guard at roughly a
        quarter of its designed reach (20/114 September anchors vs 56/114).
        """
        body = _anchor(findings=[], observations=[{"files": ["b.md"]}])["body"]
        assert cc._anchor_named_files(body) == {"b.md"}, (
            "observations carry `files` since review-loop-termination shipped "
            "observation recording — D3's deferral premise is no longer true"
        )

    def test_both_sources_union(self):
        body = _anchor(findings=[{"files": ["a.py"]}], observations=[{"files": ["b.md"]}])["body"]
        assert cc._anchor_named_files(body) == {"a.py", "b.md"}

    def test_malformed_entries_are_skipped_not_raised(self):
        body = _anchor(
            findings=[{"files": [None, "", "a.py"]}, {}],
            observations=[{"files": None}],
        )["body"]
        assert cc._anchor_named_files(body) == {"a.py"}


class TestTheRefusalPayload:
    """`_refuse_self_inflicted` builds the answer the CLI renders."""

    def test_the_guard_can_refuse(self, tmp_path, monkeypatch):
        """THE POSITIVE CONTROL: the refusal path runs end to end and returns
        the status the CLI branches on. Without this, every assertion below
        could pass against a function nothing reaches."""
        monkeypatch.setattr(cc.evidence, "append_guard_refusal",
                            lambda *a, **k: {"status": "appended"})
        monkeypatch.setattr(cc.gitstate, "current_branch", lambda *a: "feature/x")
        out = cc._refuse_self_inflicted(
            tmp_path, _anchor(), ["a.py"], {"a.py", "b.md"},
            "verify-resolutions", "scope-x", None, "abc123", [],
        )
        assert out["status"] == "self-inflicted-refusal"
        assert out["anchor_fact_id"] == "rev-anchor"
        assert out["delta_files"] == ["a.py"]
        assert out["recorded"] is True

    def test_the_reason_names_the_anchor_and_both_file_sets(self, tmp_path, monkeypatch):
        """The reason is what a builder reads at the refusal. It has to name
        WHICH pass it anchored on, or the remedy (`disposition` against that
        anchor) cannot be carried out."""
        monkeypatch.setattr(cc.evidence, "append_guard_refusal",
                            lambda *a, **k: {"status": "appended"})
        monkeypatch.setattr(cc.gitstate, "current_branch", lambda *a: "feature/x")
        out = cc._refuse_self_inflicted(
            tmp_path, _anchor(), ["a.py"], {"a.py", "b.md"},
            "verify-resolutions", None, None, None, [],
        )
        assert "rev-anchor" in out["reason"]
        assert "a.py" in out["reason"]
        assert "0 unresolved blocking" in out["reason"]

    def test_a_lost_record_does_not_swallow_the_refusal(self, tmp_path, monkeypatch, capsys):
        """The refusal is correct whether or not the fact lands — but never
        silently, because a firing that vanishes leaves the yield question
        looking answered at zero. Same posture as the budget guard beside it."""
        monkeypatch.setattr(cc.evidence, "append_guard_refusal",
                            lambda *a, **k: {"status": "error", "reason": "disk full"})
        monkeypatch.setattr(cc.gitstate, "current_branch", lambda *a: "feature/x")
        out = cc._refuse_self_inflicted(
            tmp_path, _anchor(), ["a.py"], {"a.py"},
            "verify-resolutions", None, None, None, [],
        )
        assert out["status"] == "self-inflicted-refusal", "the refusal still stands"
        assert out["recorded"] is False
        err = capsys.readouterr().err
        assert "NOT" in err and "guard-refusal" in err, (
            "a lost firing must be announced — it makes the yield query a lower bound"
        )


class TestTheExitCodeIsWiredAndDistinct:
    """D4: exit 5 is a THIRD reason, not a reuse of 3 or 4."""

    def test_the_cli_branches_on_the_status(self):
        hook = (ROOT / "bin" / "prawduct-hook").read_text(encoding="utf-8")
        assert '"self-inflicted-refusal"' in hook, "the CLI cannot see the refusal"
        assert "return 5" in hook

    def test_the_exit_code_registry_carries_a_row(self):
        """A new member of an enumerated set owes the registry that DOCUMENTS
        the set a row in the same commit — four went stale in one chunk once,
        three of them costing a full review round each."""
        contract = (ROOT.parent / ".prawduct" / "artifacts" / "api-contract.md").read_text(
            encoding="utf-8"
        )
        assert "`critic-begin` **5**" in contract, (
            "exit 5 is undocumented in the contract that calls exit codes the contract"
        )

    def test_the_skill_tells_the_reader_it_is_a_success(self):
        """Exit 3's own row exists because the instinct to re-dispatch is what
        it fights. A refusal the reader treats as a failure gets re-run with
        --force, which spends exactly the round it saved."""
        skill = (ROOT / "skills" / "critic" / "SKILL.md").read_text(encoding="utf-8")
        assert "Exit 5 is a success" in skill
        assert "--force" in skill


class TestTheThreeConjunctsIndependently:
    """`A and B and C` is three guards wearing one name.

    Each case below leaves two conjuncts satisfied and breaks exactly one, so a
    deletion of any single conjunct turns exactly one of them red. Reverting the
    predicate as a unit would go red on the first and prove nothing about the
    other two.
    """

    # The REAL predicate, not a copy of it. The first version of this class
    # re-implemented the three conjuncts here, which pins the test's own copy:
    # deleting a conjunct from the dispatch left every case below green. That is
    # why `is_self_inflicted_verify` exists as a named function.
    _decide = staticmethod(cc.is_self_inflicted_verify)

    def test_the_guard_can_refuse(self):
        """POSITIVE CONTROL: all three conjuncts satisfied → refuse."""
        assert self._decide(_anchor(findings=[{"files": ["a.py"]}])["body"], ["a.py"], []) is True

    def test_conjunct_one_a_full_round_anchor_is_never_refused(self):
        """D2's floor, and it is unconditional: the FIRST verify pass after any
        full round always runs, whatever that round's severity mix. That is the
        pass which establishes coverage over the fix commit."""
        body = _anchor(mode="cumulative (bundle review, ready for merge)",
                       findings=[{"files": ["a.py"]}])["body"]
        assert self._decide(body, ["a.py"], []) is False

    def test_conjunct_two_an_unresolved_blocker_is_never_refused(self):
        """A round that still owes a real fix is out of scope before file
        identity is even asked — which is what keeps "the discriminator is what
        moved the tree, never a round counter" true."""
        body = _anchor(findings=[{"files": ["a.py"]}])["body"]
        assert self._decide(body, ["a.py"], [{"fid": "R-1"}]) is False

    def test_conjunct_three_a_file_outside_the_named_set_is_never_refused(self):
        """The counter-example #167 acquired from a live consumer: a merge
        brought thousands of unreviewed lines into files the branch had already
        changed, and refusing that round would have been wrong."""
        body = _anchor(findings=[{"files": ["a.py"]}])["body"]
        assert self._decide(body, ["a.py", "elsewhere.py"], []) is False

    def test_an_empty_named_set_is_not_a_match(self):
        """Explicit in D3, and load-bearing: an anchor that recorded nothing at
        all cannot have its delta be a subset of nothing. Without this, `set()
        <= set()` is vacuously true and every clean anchor refuses everything."""
        assert self._decide(_anchor()["body"], ["a.py"], []) is False

    def test_an_empty_delta_is_not_a_match(self):
        """An empty interval is exit 3's answer, not this one — and exit 3 runs
        first (D5), so reaching here with an empty delta should be impossible."""
        body = _anchor(findings=[{"files": ["a.py"]}])["body"]
        assert self._decide(body, [], []) is False


def test_the_guard_is_placed_after_the_free_interval_check():
    """D5. Order is behaviour: an empty verify-on-a-verify must read as
    "nothing to review" (exit 3), not "self-inflicted" (exit 5) — the more
    specific status is wasted on an interval already refused for a simpler
    reason. Asserted structurally rather than by eye."""
    src = (ROOT / "lib" / "critic_consolidate.py").read_text(encoding="utf-8")
    body = src[src.index("def begin_review("):]

    # CALL SITES, never definitions. Every `_refuse_*` helper is defined ABOVE
    # `begin_review`, so comparing where the guard-refusal KIND strings appear
    # in the module ranks the definitions and inverts the answer — which is
    # what the first version of this test did, and it went red for that reason
    # rather than for a placement defect.
    free = body.index("critic-dispatch-free-interval")
    mine = body.index("# SELF-INFLICTED VERIFY")
    budget = body.index("# ROUND BUDGET — the terminating rule.")
    assert free < mine, (
        "the self-inflicted guard preempts the free-interval refusal — an empty "
        "verify-on-a-verify would report exit 5 where exit 3 is the simpler and "
        "correct answer"
    )
    assert mine < budget, "D5 places this before the round-budget check"


def test_the_dispatch_calls_the_real_predicate():
    """Pinning an extracted predicate proves the PREDICATE, never the wiring —
    so this asserts the dispatch calls it, structurally. Without it,
    `is_self_inflicted_verify` could be perfect and unreferenced while every
    test above stays green and the refusal never fires.

    **What it cannot see, stated rather than implied:** it proves the call is
    PRESENT, not that it is reachable. A mutation wrapping the call in
    `if False and ...` survives this assertion — verified, not assumed. Deleting
    the call, which is the realistic shape of that regression, turns it red. The
    unreachable-but-present case is left to review.
    """
    import ast  # noqa: PLC0415

    src = (ROOT / "lib" / "critic_consolidate.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "begin_review")
    called = {
        (c.func.id if isinstance(c.func, ast.Name) else getattr(c.func, "attr", ""))
        for c in ast.walk(fn) if isinstance(c, ast.Call)
    }
    assert "is_self_inflicted_verify" in called, (
        "begin_review no longer asks the #167 predicate — the guard is dead code"
    )
    assert "_refuse_self_inflicted" in called, (
        "begin_review no longer builds the refusal, so the predicate's answer "
        "reaches nothing"
    )
