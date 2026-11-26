"""The relax-only batch rule (#1232 Chunk 03): ``coverage_algebra.batch_review_covers``.

A release batch review rates only the files of the merges no boundary review read, so
it is not an edge, and composition cannot credit it. The rule credits it one release
entry at a time. Pure: facts and file lists in, an answer out, as the rest of the
algebra's tests are written.

The property this module owes: adding a release batch fact never turns any
``coverage_verdict`` (or ``excused_gap_verdict``) from not covered to covered. It is
checked over every combination of a small evidence universe, with a positive control
showing the same facts without their span DO flip some answer, so the property is not
vacuous.
"""

from __future__ import annotations

import hashlib
import itertools
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "plugin"
sys.path.insert(0, str(ROOT))
from lib import coverage_algebra as ca  # noqa: E402


def _tree(name: str) -> str:
    return hashlib.sha1(name.encode()).hexdigest()


ANCHOR, MID, HEAD, ELSEWHERE = (_tree(n) for n in ("anchor", "mid", "head", "elsewhere"))


def _review(rid: str, src: str, dst: str, changed: list, reviewed: "list | None" = None, *,
            blocking: bool = False, span: "str | None" = ca.RELEASE_SPAN) -> dict:
    body = {"base_tree": src, "head_tree": dst, "files_changed": changed,
            "files_reviewed": changed if reviewed is None else reviewed,
            "mode": "cumulative (bundle review, ready for PR)",
            "findings": [{"fid": "R-1", "severity": "BLOCKING", "title": "boom"}] if blocking else []}
    if span is not None:
        body["span"] = span
    return {"schema": 1, "kind": "review", "id": rid, "ts": "t", "body": body}


def _resolution(review_id: str, fid: str = "R-1", disposition: str = "fixed") -> dict:
    return {"schema": 1, "kind": "resolution", "id": f"res-{review_id}-{fid}", "ts": "t",
            "body": {"finding": {"review_id": review_id, "fid": fid}, "disposition": disposition}}


SPAN_FILES = ["src/a.py", "src/b.py", "src/c.py", ".prawduct/artifacts/plan.md"]


def _batch(reviewed: list, **kw) -> dict:
    return _review("rev-batch", ANCHOR, HEAD, SPAN_FILES, reviewed, **kw)


class TestTheRule:
    def test_it_covers_an_entry_whose_judgeable_files_it_rated(self):
        batch = _batch(["src/a.py", "src/b.py"])
        got = ca.batch_review_covers([batch], batch, ["src/a.py", "src/b.py"], brackets=True)
        assert got["status"] == "covered", got

    def test_a_file_outside_the_subject_refuses_and_is_named(self):
        batch = _batch(["src/a.py"])
        got = ca.batch_review_covers([batch], batch, ["src/a.py", "src/c.py"], brackets=True)
        assert (got["status"], got["outside"]) == ("not", ["src/c.py"]), got
        assert "src/c.py" in got["reason"]

    def test_a_file_back_at_the_anchor_s_content_needs_no_reading(self):
        """``src/gone.py`` changed in the entry but is not in the interval's diff."""
        batch = _batch(["src/a.py"])
        got = ca.batch_review_covers([batch], batch, ["src/a.py", "src/gone.py"], brackets=True)
        assert got["status"] == "covered", got

    def test_a_non_judgeable_file_outside_the_subject_does_not_refuse(self):
        batch = _batch(["src/a.py"])
        got = ca.batch_review_covers([batch], batch, ["src/a.py", ".prawduct/artifacts/plan.md"],
                                     brackets=True)
        assert got["status"] == "covered", got

    def test_a_review_not_bracketing_refuses(self):
        batch = _batch(["src/a.py"])
        got = ca.batch_review_covers([batch], batch, ["src/a.py"], brackets=False)
        assert got["status"] == "not" and "bracket" in got["reason"], got

    def test_unread_entry_files_refuse_rather_than_read_as_nothing_changed(self):
        batch = _batch(["src/a.py"])
        got = ca.batch_review_covers([batch], batch, None, brackets=True)
        assert got["status"] == "not" and "could not be read" in got["reason"], got

    def test_its_own_unresolved_blocker_refuses(self):
        batch = _batch(["src/a.py"], blocking=True)
        got = ca.batch_review_covers([batch], batch, ["src/a.py"], brackets=True)
        assert got["status"] == "blocked" and got["unresolved"][0]["review_id"] == "rev-batch", got

    def test_a_blocker_is_settled_even_when_facts_omit_the_review(self):
        batch = _batch(["src/a.py"], blocking=True)
        assert ca.batch_review_covers([], batch, ["src/a.py"], brackets=True)["status"] == "blocked"

    def test_a_resolution_fact_clears_it(self):
        batch = _batch(["src/a.py"], blocking=True)
        got = ca.batch_review_covers([batch, _resolution("rev-batch")], batch, ["src/a.py"], brackets=True)
        assert got["status"] == "covered", got

    def test_an_unrecognised_disposition_does_not_clear_it(self):
        batch = _batch(["src/a.py"], blocking=True)
        got = ca.batch_review_covers([batch, _resolution("rev-batch", disposition="meh")], batch,
                                     ["src/a.py"], brackets=True)
        assert got["status"] == "blocked", got

    def test_another_fact_s_blocker_at_either_of_its_trees_refuses(self):
        batch = _batch(["src/a.py"])
        for at_head, tree in ((True, HEAD), (False, ANCHOR)):
            other = _review("rev-other", MID if at_head else ELSEWHERE, tree, ["src/a.py"],
                            blocking=True, span=None)
            got = ca.batch_review_covers([batch, other], batch, ["src/a.py"], brackets=True)
            assert got["status"] == "blocked" and got["unresolved"][0]["review_id"] == "rev-other", got

    def test_a_blocker_at_a_tree_it_does_not_stand_on_does_not(self):
        batch = _batch(["src/a.py"])
        other = _review("rev-other", ANCHOR, MID, ["src/a.py"], blocking=True, span=None)
        got = ca.batch_review_covers([batch, other], batch, ["src/a.py"], brackets=True)
        assert got["status"] == "covered", got

    def test_a_malformed_review_refuses(self):
        broken = _batch(["src/a.py"])
        broken["body"]["files_reviewed"] = "src/a.py"
        assert ca.batch_review_covers([], broken, ["src/a.py"], brackets=True)["status"] == "not"
        bad_tree = _review("rev-x", "not-a-tree", HEAD, ["src/a.py"])
        assert ca.batch_review_covers([], bad_tree, ["src/a.py"], brackets=True)["status"] == "not"

    def test_a_whole_edge_review_is_the_special_case_and_covers_any_entry(self):
        """Wave 1's batch rule: a boundary review that is an edge rated every
        judgeable file, so every entry's files are within it."""
        edge = _review("rev-edge", ANCHOR, HEAD, SPAN_FILES, span=None)
        assert ca.review_edges([edge])
        got = ca.batch_review_covers([edge], edge, ["src/a.py", "src/b.py", "src/c.py"], brackets=True)
        assert got["status"] == "covered", got


class TestNeverAnEdge:
    def test_a_release_batch_rating_every_file_is_not_an_edge(self):
        full = _batch(SPAN_FILES)
        assert ca.review_edges([full]) == []
        assert ca.is_release_batch(full)
        plain = dict(full, body={k: v for k, v in full["body"].items() if k != "span"})
        assert not ca.is_release_batch(plain) and ca.review_edges([plain])


# ---------------------------------------------------------------------------
# The property: a batch fact never turns a verdict from not covered to covered
# ---------------------------------------------------------------------------

#: A small universe: four trees by content. T3 differs from T2 only in a record
#: (a free edge between them).
_CONTENT = {
    _tree("t0"): {"src/a.py": 0, "src/b.py": 0},
    _tree("t1"): {"src/a.py": 1, "src/b.py": 0},
    _tree("t2"): {"src/a.py": 1, "src/b.py": 1},
    _tree("t3"): {"src/a.py": 1, "src/b.py": 1, ".prawduct/notes.md": 1},
}
_TREES = list(_CONTENT)
T0, T1, T2, T3 = _TREES


def _diff(a: str, b: str) -> "list[str] | None":
    if a not in _CONTENT or b not in _CONTENT:
        return None
    left, right = _CONTENT[a], _CONTENT[b]
    return sorted(f for f in set(left) | set(right) if left.get(f) != right.get(f))


def _key(tree: str) -> "str | None":
    content = _CONTENT.get(tree)
    if content is None:
        return None
    return repr(sorted((f, v) for f, v in content.items() if ca.is_judgeable_path(f)))


#: The ordinary evidence the batch facts are added beside.
_POOL = [
    _review("e01", T0, T1, _diff(T0, T1), span=None),
    _review("e12", T1, T2, _diff(T1, T2), span=None),
    _review("e12-partial", T1, T2, _diff(T1, T2), [], span=None),
    _review("e02-blocked", T0, T2, _diff(T0, T2), span=None, blocking=True),
    _resolution("e02-blocked"),
    _review("e13", T1, T3, _diff(T1, T3), span=None),
]


def _batches() -> list:
    out = []
    for (src, dst), reviewed, blocking in itertools.product(
            itertools.permutations(_TREES, 2), ("all", "none"), (False, True)):
        changed = _diff(src, dst)
        out.append(_review(f"b-{src[:4]}-{dst[:4]}-{reviewed}-{blocking}", src, dst, changed,
                           changed if reviewed == "all" else [], blocking=blocking))
    for tree in _TREES:
        out.append(_review(f"b-loop-{tree[:4]}", tree, tree, [], blocking=True))
    return out


_ORDER = {"uncovered": 0, "blocked": 1, "covered": 2}


def _allowed(before: str, after: str) -> bool:
    """A fact that adds no edge can only add blockers: uncovered stays uncovered,
    blocked stays blocked, covered stays covered or becomes blocked."""
    return after == before or (before == "covered" and after == "blocked")


def _sweep(verdict_of) -> "tuple[list, int, set]":
    """Every pool subset × batch fact × span; returns (violations, cases, statuses seen)."""
    violations, cases, seen = [], 0, set()
    batches = _batches()
    for n in range(len(_POOL) + 1):
        for subset in itertools.combinations(_POOL, n):
            facts = list(subset)
            for src, dst in itertools.product(_TREES, repeat=2):
                before = verdict_of(facts, src, dst)
                seen.add(before)
                for batch in batches:
                    after = verdict_of(facts + [batch], src, dst)
                    cases += 1
                    if not _allowed(before, after):
                        violations.append((tuple(f["id"] for f in facts), batch["id"], src[:6], dst[:6],
                                           before, after))
    return violations, cases, seen


class TestRelaxOnly:
    def test_a_batch_fact_never_turns_coverage_verdict_toward_covered(self):
        def verdict(facts, src, dst):
            return ca.coverage_verdict(facts, src, dst, _diff)["status"]

        violations, cases, seen = _sweep(verdict)
        assert cases > 10_000 and seen == {"uncovered", "blocked", "covered"}, (cases, seen)
        assert violations == [], violations[:5]

    def test_the_key_form_agrees(self):
        def verdict(facts, src, dst):
            return ca.coverage_verdict(facts, src, dst, _diff, _key)["status"]

        violations, _cases, _seen = _sweep(verdict)
        assert violations == [], violations[:5]

    def test_a_batch_fact_never_turns_an_excused_gap_toward_covered(self):
        def verdict(facts, src, dst):
            return ca.excused_gap_verdict(facts, src, dst, _diff, None,
                                          lambda files: set(files) <= {"src/b.py"})["status"]

        violations, _cases, seen = _sweep(verdict)
        assert "covered" in seen and violations == [], violations[:5]

    def test_positive_control_the_same_facts_without_their_span_do_cover(self):
        """The sweep can see a violation: strip the span and a full-subject batch
        fact is an ordinary edge, which turns some uncovered span covered."""
        def verdict(facts, src, dst):
            plain = [dict(f, body={k: v for k, v in f["body"].items() if k != "span"})
                     if f.get("kind") == "review" else f for f in facts]
            return ca.coverage_verdict(plain, src, dst, _diff)["status"]

        violations, _cases, _seen = _sweep(verdict)
        assert any(v[4] == "uncovered" and v[5] == "covered" for v in violations)
