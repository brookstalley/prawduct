"""``coverage_algebra.walk_links`` owns stepping back along the review link and
ending the walk, for every walker that loops over the link.

The link rule finds a recorded anchor by id wherever it sits in the store, so
store order does not end a walk; a loop over the link needs a revisit guard,
and the helper holds the one guard. The reference copies below are each
walker's loop with a guard of its own, keyed two ways (``id()`` of the dict, or
the fact id). The helper must reach exactly what those loops reached, so these
tests run each reference copy beside the walker on the helper, over
adversarial stores, and ask for identical answers.

The stores are written as JSONL and read back through ``evidence.read_facts``,
the reader every production walker's facts come through: it drops a fact with
no non-empty string id and keeps the first of a repeated ``(kind, id)``. Over
what it can return the two identity keys agree, which is why the helper's one
rule (the fact id, the object only for an id-less fact) changes nothing there.
A raw list holding a repeated id or two id-less facts is not a store any
walker is handed; the helper's rule on those is pinned directly at the end.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
sys.path.insert(0, str(ROOT))
from lib import coverage_algebra as ca  # noqa: E402
from lib import critic_mode, evidence, gates, gitstate, plan_status  # noqa: E402

VERIFY = gates._CRITIC_MODE_VERIFY_RESOLUTIONS
CHUNK = "chunk (lighter pass, not ready for push)"
CUMULATIVE = "cumulative (bundle review, ready for merge)"
FINAL = "final (full review, ready for push)"
T0, T1, T2, T3 = (c * 40 for c in "0123")
ELSEWHERE = "rev-20261123T120000Z-0e1f2a3b"
_ABSENT = object()


# ---------------------------------------------------------------------------
# Reference copies: each walker's loop as it stood with its own revisit guard
# ---------------------------------------------------------------------------


def _old_stand_on(reviews, fact):
    current = fact
    last = fact
    seen = set()
    while current is not None and gates._review_mode(current) == VERIFY:
        if id(current) in seen:
            return None, last
        seen.add(id(current))
        last = current
        current = ca.prior_review(reviews, current)
    return current, last


def _old_extended(reviews, fact):
    line = []
    current = fact
    seen = {id(fact)}
    while not gitstate.is_object_id((current.get("body") or {}).get("base_commit")):
        if not gitstate.is_object_id((current.get("body") or {}).get("base_tree")):
            return None
        prior = ca.prior_review(reviews, current)
        if prior is None or id(prior) in seen:
            return None
        seen.add(id(prior))
        current = prior
        line.append(current)
    return line or None


def _old_review_chain(facts, newest):
    reviews = [f for f in facts if f.get("kind") == "review"]
    chain = []
    seen = set()
    current = newest
    while current is not None and current.get("id") not in seen:
        seen.add(current.get("id"))
        chain.append(current)
        linked = ca.linked_reviews(reviews, current)
        if not linked or linked[-1].get("id") in seen:
            break
        for other in linked[:-1]:
            if other.get("id") not in seen:
                seen.add(other.get("id"))
                chain.append(other)
        current = linked[-1]
    return chain


# ---------------------------------------------------------------------------
# Stores
# ---------------------------------------------------------------------------


def _review(rid, mode, base, head, *, verifies=_ABSENT, base_commit=None, kind="review"):
    body = {"mode": mode, "base_tree": base, "head_tree": head, "findings": [],
            "base_commit": base_commit}
    if verifies is not _ABSENT:
        body["verifies"] = verifies
    fact = {"schema": 1, "kind": kind, "ts": "2026-11-23T00:00:00Z",
            "actor": {"worktree": "/here", "branch": "main"}, "body": body}
    if rid is not _ABSENT:
        fact["id"] = rid
    return fact


#: Named shapes, each one a way the old loops' guards and the helper's could
#: part: a cycle the claims name, a cycle closed through the tree link, a
#: repeated id and id-less facts (dropped or deduped by the reader), an anchor
#: appended after its pass, siblings that are also spine members, a sibling
#: the walk later links to, and every unresolved claim.
NAMED_STORES = {
    "claim-cycle-beside-an-unrelated-review": [
        _review("rev-r", CHUNK, T0, T2),
        _review("rev-p1", VERIFY, T2, T1, verifies="rev-p2"),
        _review("rev-p2", VERIFY, T1, T2, verifies="rev-p1"),
    ],
    "cycle-closed-through-the-tree-link": [
        _review("rev-a", VERIFY, T2, T1, verifies="rev-c"),
        _review("rev-b", VERIFY, T1, T2),
        _review("rev-c", VERIFY, T1, T2, verifies="rev-b"),
    ],
    "a-repeated-id-and-id-less-facts": [
        _review("rev-a", CHUNK, T0, T1),
        _review("rev-a", VERIFY, T1, T2),
        _review(_ABSENT, VERIFY, T1, T2),
        _review("", VERIFY, T2, T3),
        _review("rev-b", VERIFY, T1, T2, verifies="rev-a"),
        _review("rev-c", VERIFY, T2, T3),
    ],
    "an-anchor-appended-after-its-pass": [
        _review("rev-pass", VERIFY, T1, T2, verifies="rev-anchor"),
        _review("rev-other", CUMULATIVE, T0, T1),
        _review("rev-anchor", CHUNK, T0, T1, base_commit="a" * 40),
    ],
    "siblings-that-are-also-spine-members": [
        _review("rev-p", CHUNK, T3, T0),
        _review("rev-a", CHUNK, T0, T1),
        _review("rev-b", CHUNK, T1, T1),
        _review("rev-c", CHUNK, T1, T2),
        _review("rev-v", VERIFY, T2, T3),
    ],
    "a-sibling-the-walk-later-links-to": [
        _review("rev-a", CHUNK, T0, T1),
        _review("rev-b", FINAL, T0, T1),
        _review("rev-x", VERIFY, T1, T0, verifies="rev-b"),
        _review("rev-c", VERIFY, T1, T2),
        _review("rev-d", VERIFY, T2, T1, verifies="rev-c"),
    ],
    # From rev-y: its claim reaches rev-s, which links by tree to rev-x and
    # rev-y. rev-y is already walked, so the walk ends there and rev-x, an
    # older review at that tree nothing walked to, stays off the chain.
    "a-linked-review-already-walked-beside-an-unwalked-sibling": [
        _review("rev-x", CHUNK, T0, T1),
        _review("rev-y", VERIFY, T2, T1, verifies="rev-s"),
        _review("rev-s", CHUNK, T1, T2),
    ],
    "every-unresolved-claim": [
        _review("rev-a", CHUNK, T0, T1),
        _review("rev-self", VERIFY, T1, T2, verifies="rev-self"),
        _review("rev-junk", VERIFY, T1, T2, verifies="not-a-review-id"),
        _review("rev-num", VERIFY, T1, T2, verifies=5),
        _review("rev-empty", VERIFY, T1, T2, verifies=""),
        _review("rev-gone", VERIFY, T1, T2, verifies=ELSEWHERE),
        _review("rev-mismatch", VERIFY, T2, T3, verifies="rev-a"),
        _review("rev-nobase", VERIFY, None, T3, verifies="rev-a"),
        _review("rev-oddbase", VERIFY, "not-a-tree", T3),
    ],
    "an-extended-line-to-a-commit": [
        _review("rev-a", CHUNK, T0, T1, base_commit="a" * 40),
        _review("rev-b", VERIFY, T1, T2),
        _review("rev-c", VERIFY, T2, T3, verifies="rev-b"),
        _review("rev-note", VERIFY, T2, T3, kind="note"),
    ],
}

_TREES = [T0, T1, T1, T2, T2, T3, None, "", "not-a-tree"]
_MODES = [VERIFY, VERIFY, CHUNK, CHUNK, CUMULATIVE, FINAL, 7]
_IDS = [f"rev-{n}" for n in "abcdefghijkl"]


def _random_store(rng: random.Random) -> list[dict]:
    """A small store drawn from few trees and few ids, so cycles, repeated
    ids and several reviews at one tree are common."""
    store = []
    for _ in range(rng.randint(1, 10)):
        roll = rng.random()
        rid = _ABSENT if roll < 0.05 else rng.choice(_IDS)
        claim = rng.choice([_ABSENT] * 4 + [None, "self", "known", "known", ELSEWHERE, "junk", 3])
        if claim == "self":
            claim = rid if isinstance(rid, str) else "rev-a"
        elif claim == "known":
            claim = rng.choice(_IDS)
        store.append(_review(
            rid, rng.choice(_MODES), rng.choice(_TREES), rng.choice(_TREES),
            verifies=claim,
            base_commit=rng.choice([None, None, "a" * 40, "not-a-commit"]),
            kind="review" if rng.random() > 0.1 else "note",
        ))
    return store


def _read_back(tmp_path: Path, monkeypatch, raw: list[dict]) -> list[dict]:
    """``raw`` written as the store and read through ``evidence.read_facts``."""
    path = tmp_path / "evidence.jsonl"
    path.write_text("".join(json.dumps(f) + "\n" for f in raw), encoding="utf-8")
    monkeypatch.setattr(evidence, "store_path", lambda _project_dir: path)
    read = evidence.read_facts(tmp_path)
    assert read["status"] == "ok", read
    return read["facts"]


def _identity(value):
    """A walker's answer with every fact replaced by its object identity, so
    two answers match only when they name the very same store facts."""
    if value is None:
        return None
    if isinstance(value, dict):
        return id(value)
    return tuple(_identity(v) for v in value)


class _Tally:
    """What the comparison exercised, so a corpus that never reaches a cycle
    or a sibling cannot pass as a proof about them."""

    def __init__(self):
        self.stores = self.starts = 0
        self.deduped = self.revisits = self.siblings = 0
        self.stood_on_none = self.stood_on_review = self.lines = 0


def _compare(facts: list[dict], tally: _Tally) -> list[str]:
    reviews = evidence.facts_of_kind({"facts": facts}, "review")
    diffs = []
    tally.stores += 1
    for fact in reviews:
        tally.starts += 1
        old, new = _old_stand_on(reviews, fact), gates._review_verified_passes_stand_on(reviews, fact)
        if _identity(old) != _identity(new):
            diffs.append(f"stand_on from {fact['id']}: {_ids(old)} != {_ids(new)}")
        tally.stood_on_none += old[0] is None
        tally.stood_on_review += old[0] is not None and old[0] is not fact
        old, new = _old_extended(reviews, fact), plan_status._extended_reviews(reviews, fact)
        if _identity(old) != _identity(new):
            diffs.append(f"extended from {fact['id']}: {_ids(old)} != {_ids(new)}")
        tally.lines += bool(old)
        # The chain is also asked of a copy of a stored fact: the envelope a
        # consolidation just appended, or an anchor from another read.
        for start in (fact, json.loads(json.dumps(fact))):
            old, new = _old_review_chain(facts, start), critic_mode.review_chain(facts, start, bound=None)
            if _identity(old) != _identity(new):
                diffs.append(f"chain from {fact['id']}: {_ids(old)} != {_ids(new)}")
        chain = _old_review_chain(facts, fact)
        on_chain = {id(f) for f in chain}
        # A fact on the chain linking back into it is where a walk met a fact
        # it had already visited.
        tally.revisits += any(
            id(prior) in on_chain
            for step in chain
            for prior in ca.linked_reviews(reviews, step)[-1:]
        )
        tally.siblings += any(
            id(other) in on_chain
            for step in chain
            for other in ca.linked_reviews(reviews, step)[:-1]
        )
    return diffs


def _ids(value):
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get("id")
    return [_ids(v) for v in value]


class TestTheWalkersReachWhatTheirOwnLoopsReached:
    @pytest.mark.parametrize("name", sorted(NAMED_STORES))
    def test_a_named_adversarial_store(self, name, tmp_path, monkeypatch):
        raw = NAMED_STORES[name]
        facts = _read_back(tmp_path, monkeypatch, raw)
        assert facts, "the reader dropped the whole store"
        tally = _Tally()
        assert _compare(facts, tally) == []
        assert tally.starts > 0

    def test_seeded_random_stores(self, tmp_path, monkeypatch):
        rng = random.Random(1220)
        tally = _Tally()
        diffs = []
        for n in range(600):
            raw = _random_store(rng)
            facts = _read_back(tmp_path, monkeypatch, raw)
            tally.deduped += len(facts) < len(raw)
            diffs += [f"store {n}: {d}" for d in _compare(facts, tally)]
        assert diffs == [], "\n".join(diffs[:20])
        # The corpus reached every shape the guards differ on.
        assert tally.stores == 600 and tally.starts > 1000
        assert tally.deduped > 50, tally.deduped
        assert tally.revisits > 50, tally.revisits
        assert tally.siblings > 20, tally.siblings
        assert tally.stood_on_none > 50 and tally.stood_on_review > 25
        assert tally.lines > 20, tally.lines


class TestTheOneIdentityRule:
    """The helper's key, asked directly of inputs the store reader never
    returns, so the rule itself (not only its agreement with the old loops
    over a store) is pinned."""

    def test_a_copy_of_a_stored_fact_is_that_review(self):
        """A pass and the review it verifies name each other; the walk starts
        from a copy of the pass. Back at the stored pass it ends: by id it is
        the review already walked."""
        a = _review("rev-a", VERIFY, T2, T1, verifies="rev-b")
        b = _review("rev-b", VERIFY, T1, T2, verifies="rev-a")
        copy = json.loads(json.dumps(b))
        assert [f["id"] for f in ca.walk_links([a, b], copy)] == ["rev-b", "rev-a"]

    def test_id_less_facts_are_each_their_own(self):
        """Two hand-built facts with no id, the newer starting at the older's
        tree: both are walked, since an absent id names no one fact."""
        older = _review(_ABSENT, CHUNK, T0, T1)
        newer = _review(_ABSENT, VERIFY, T1, T2)
        assert list(ca.walk_links([older, newer], newer)) == [newer, older]

    def test_each_review_is_yielded_once_by_its_id(self):
        """A raw list repeating an id at one tree: S links to both, the older
        is yielded as a sibling, and the newer, the same review by id, is not
        walked to again."""
        older = _review("rev-a", CHUNK, T0, T1)
        newer = _review("rev-a", CHUNK, T0, T1)
        start = _review("rev-s", CHUNK, T1, T2)
        walk = list(ca.walk_links([older, newer, start], start, siblings=True))
        assert walk == [start, older] and walk[1] is older

    def test_none_walks_nothing(self):
        assert list(ca.walk_links([], None)) == []

    def test_the_next_link_waits_for_the_caller(self, monkeypatch):
        """A walker that stops at the first fact pays no link lookup for it."""
        calls = []
        real = ca.linked_reviews
        monkeypatch.setattr(ca, "linked_reviews", lambda r, f: calls.append(f) or real(r, f))
        fact = _review("rev-a", CHUNK, T0, T1)
        walk = ca.walk_links([fact], fact)
        assert next(walk) is fact
        assert calls == []
