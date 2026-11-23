"""A verify-resolutions fact names the review it verifies, and every walker
follows that name.

A pass's interval starts at the ``head_tree`` of the review it anchored to, so
the tree link (``coverage_algebra.linked_reviews``: the newest earlier review
whose ``head_tree`` is the pass's ``base_tree``) found that review only while no
other review stood at the same tree. The store is shared by every worktree of a
clone, so two worktrees reviewing one tree made the link pick the newer of the
two whichever the pass verified: a wrong or missing Stop-hook synthesis NOTE,
and a roll-call carrying the wrong review's blockers.

Consolidation now records ``verifies: <review id>`` on the pass's fact, from the
dispatch's own choice. ``coverage_algebra.prior_review`` is the one owner of
"which review does this pass verify": the recorded anchor, else (a fact from
before the field) the tree link. A recorded anchor the store does not hold links
to nothing, never to the tree's newest review.

Every fixture here puts two reviews at one tree, the pass anchored to the OLDER,
so the tree link and the recorded anchor disagree.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from test_critic_consolidate import (
    FINAL_MODE,
    PARTIALS_REL,
    ROOT,
    VERIFY_MODE,
    _commit_file,
    _full_roster_partials,
    _git,
    _init_repo,
    _run_begin,
    _run_consolidate,
    _set_marker,
    _store_facts,
    _write_manifest,
    _write_partial,
)

sys.path.insert(0, str(ROOT))
from lib import coverage_algebra as ca  # noqa: E402
from lib import critic_consolidate as cc  # noqa: E402
from lib import critic_mode, evidence, gates, plan_status  # noqa: E402

CUMULATIVE = "cumulative (bundle review, ready for merge)"
CHUNK = "chunk (lighter pass, not ready for push)"

T0, T1, T2, T3 = (c * 40 for c in "0123")
OTHER_BASE = "9" * 40

_ABSENT = object()


def _review(rid, mode, base, head, *, verifies=_ABSENT, findings=None,
            base_commit=None, worktree="/here"):
    body = {
        "mode": mode, "base_tree": base, "head_tree": head,
        "files_changed": ["a.py"], "files_reviewed": ["a.py"],
        "findings": findings or [], "base_commit": base_commit,
    }
    if verifies is not _ABSENT:
        body["verifies"] = verifies
    return {
        "schema": 1, "kind": "review", "id": rid, "ts": "2026-11-23T00:00:00Z",
        "actor": {"session": "s", "worktree": worktree, "plugin": "x", "branch": "main"},
        "body": body,
    }


def _blocker(fid: str, title: str) -> dict:
    return {"fid": fid, "severity": "blocking", "title": title, "goal": "g",
            "recommendation": "r", "files": ["a.py"]}


def _two_reviews_of_one_tree(older_mode=CUMULATIVE, newer_mode=CHUNK, **pass_kw):
    """``rev-old`` and then ``rev-new`` (another worktree) both stand at T1;
    ``rev-pass`` starts at T1 and, unless told otherwise, verifies ``rev-old``."""
    pass_kw.setdefault("verifies", "rev-old")
    return [
        _review("rev-old", older_mode, T0, T1),
        _review("rev-new", newer_mode, OTHER_BASE, T1, worktree="/sibling"),
        _review("rev-pass", VERIFY_MODE, T1, T2, **pass_kw),
    ]


# ---------------------------------------------------------------------------
# The owner: coverage_algebra.prior_review / linked_reviews
# ---------------------------------------------------------------------------


class TestTheLinkFollowsTheRecordedAnchor:
    def test_the_pass_links_to_the_review_it_anchored_to(self):
        reviews = _two_reviews_of_one_tree()
        assert ca.prior_review(reviews, reviews[-1])["id"] == "rev-old"

    def test_the_tree_alone_picks_the_newer_review(self):
        """The control, and the defect: with nothing recorded the tree link
        picks the newest review at T1, which is not the one verified."""
        reviews = _two_reviews_of_one_tree(verifies=_ABSENT)
        assert ca.prior_review(reviews, reviews[-1])["id"] == "rev-new"

    @pytest.mark.parametrize("legacy", [_ABSENT, None], ids=["no-key", "null"])
    def test_a_fact_from_before_the_field_links_by_tree(self, legacy):
        reviews = _two_reviews_of_one_tree(verifies=legacy)
        assert [f["id"] for f in ca.linked_reviews(reviews, reviews[-1])] == [
            "rev-old", "rev-new",
        ]

    def test_an_anchored_pass_links_to_its_anchor_alone(self):
        """Neither a review of the same tree recorded before the anchor nor one
        recorded after it is linked: store order cannot say whose they are."""
        reviews = [_review("rev-first", CHUNK, T0, T1)] + _two_reviews_of_one_tree()
        assert [f["id"] for f in ca.linked_reviews(reviews, reviews[-1])] == ["rev-old"]

    def test_the_link_does_not_depend_on_store_order(self):
        """A sibling's review of the tree recorded BEFORE the anchor, or ingested
        ahead of the pass, is linked no more than one recorded after it."""
        sibling = _review("rev-sibling", CUMULATIVE, OTHER_BASE, T1, worktree="/sibling")
        anchor = _review("rev-anchor", CHUNK, T0, T1)
        pass_ = _review("rev-pass", VERIFY_MODE, T1, T2, verifies="rev-anchor")
        for order in ([sibling, anchor, pass_], [anchor, sibling, pass_], [sibling, pass_, anchor]):
            ids = [f["id"] for f in ca.linked_reviews(order, pass_)]
            assert ids == ["rev-anchor"], [f["id"] for f in order]

    def test_an_anchor_the_store_does_not_hold_links_to_nothing(self):
        """Not yet ingested from the clone that recorded it: the tree's newest
        review is the guess the record exists to stop, so there is no link."""
        reviews = _two_reviews_of_one_tree(verifies="rev-from-another-clone")
        assert ca.linked_reviews(reviews, reviews[-1]) == []
        assert ca.prior_review(reviews, reviews[-1]) is None

    @pytest.mark.parametrize("claim", [7, "", ["rev-old"], "rev-pass"],
                             ids=["int", "empty", "list", "itself"])
    def test_a_malformed_claim_links_to_nothing(self, claim):
        reviews = _two_reviews_of_one_tree(verifies=claim)
        assert ca.prior_review(reviews, reviews[-1]) is None

    def test_an_anchor_ingested_after_its_pass_still_resolves(self):
        """Ingest appends another clone's facts in note order, which can put a
        pass ahead of the review it verifies; the id still says which."""
        old, new, pass_ = _two_reviews_of_one_tree()
        reviews = [new, pass_, old]
        assert ca.prior_review(reviews, pass_)["id"] == "rev-old"

    @pytest.mark.parametrize("base", [None, ""], ids=["none", "empty"])
    @pytest.mark.parametrize("verifies", [_ABSENT, "rev-old"], ids=["tree", "anchored"])
    def test_a_pass_with_no_base_tree_links_to_nothing(self, base, verifies):
        """A pass whose interval cannot be placed is no link, anchored or not:
        the same safe reading as an anchor the store lacks."""
        reviews = _two_reviews_of_one_tree(verifies=verifies)
        reviews[-1]["body"]["base_tree"] = base
        # Another review "at" the missing tree, so the tree link has bait too.
        reviews.insert(0, _review("rev-treeless", CHUNK, T0, base))
        assert ca.linked_reviews(reviews, reviews[-1]) == []

    def test_an_anchor_at_another_tree_is_unresolved(self):
        """The dispatch takes the pass's base from its anchor's head, so a
        recorded pair that disagrees is malformed: no link, and not a review
        a later ingest could supply."""
        old, new, pass_ = _two_reviews_of_one_tree()
        old["body"]["head_tree"] = T3
        reviews = [old, new, pass_]
        assert ca.linked_reviews(reviews, pass_) == []
        assert ca.missing_anchor(reviews, pass_) is None

    def test_only_an_id_the_store_lacks_is_missing(self):
        reviews = _two_reviews_of_one_tree(verifies="rev-from-another-clone")
        assert ca.missing_anchor(reviews, reviews[-1]) == "rev-from-another-clone"
        resolved = _two_reviews_of_one_tree()
        assert ca.missing_anchor(resolved, resolved[-1]) is None
        legacy = _two_reviews_of_one_tree(verifies=_ABSENT)
        assert ca.missing_anchor(legacy, legacy[-1]) is None


# ---------------------------------------------------------------------------
# Walkers
# ---------------------------------------------------------------------------


def _finished_plan_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    _init_repo(repo)
    artifacts = repo / ".prawduct" / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "build-plan.md").write_text(
        "# Build Plan\n\n## Status\n"
        "- [x] Chunk 01: A\n- [x] Chunk 02: B\n- [x] Chunk 03: C\n"
    )
    return repo


def _append(repo: Path, fact: dict, *, here: bool) -> None:
    """Into the clone's store: through ``append_fact`` (this worktree's actor,
    as production stamps it) or as another worktree's line."""
    if here:
        appended = evidence.append_fact(repo, "review", fact["id"], fact["body"])
        assert appended["status"] == "appended", appended
        return
    store = evidence.store_path(repo)
    store.parent.mkdir(parents=True, exist_ok=True)
    with open(store, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(fact) + "\n")


class TestTheStopHookSynthesisFollowsTheAnchor:
    """``gates._critic_session_satisfies_gate`` judges the review the latest
    pass verifies; with two reviews of one tree, that is the anchored one."""

    def _gate(self, tmp_path, older_mode, newer_mode, **pass_kw):
        repo = _finished_plan_repo(tmp_path)
        old, new, pass_ = _two_reviews_of_one_tree(older_mode, newer_mode, **pass_kw)
        _append(repo, old, here=True)
        _append(repo, new, here=False)
        _append(repo, pass_, here=True)
        return gates._critic_session_satisfies_gate(repo)

    def test_a_pass_over_the_older_cumulative_is_satisfied(self, tmp_path):
        """A sibling's newer `chunk` at the same tree read as the verified
        review, and the NOTE asked for a final nobody owed."""
        assert self._gate(tmp_path, CUMULATIVE, CHUNK) == (True, "")

    def test_a_pass_over_the_older_chunk_still_nudges(self, tmp_path):
        """The mirror: a sibling's newer `cumulative` at the same tree silenced
        a NOTE this pass's own `chunk` owes."""
        ok, reason = self._gate(tmp_path, CHUNK, CUMULATIVE)
        assert not ok
        assert f"a verify-resolutions pass over a '{CHUNK}' review" in reason, reason

    def test_a_pass_from_before_the_field_still_links_by_tree(self, tmp_path):
        ok, reason = self._gate(tmp_path, CUMULATIVE, CHUNK, verifies=_ABSENT)
        assert not ok and f"over a '{CHUNK}' review" in reason, reason

    def test_an_anchor_not_in_the_store_names_it_and_asks_for_no_final(self, tmp_path):
        """A cumulative stands at the tree, but it is not the review the pass
        names, and that one has not been ingested: synthesis is unknown here,
        so the NOTE names the review and the repair, never a `final`."""
        ok, reason = self._gate(
            tmp_path, CUMULATIVE, CUMULATIVE, verifies="rev-from-another-clone"
        )
        assert not ok
        assert "the review it verifies (rev-from-another-clone) is not in this clone's" in reason
        assert "evidence sync" in reason, reason
        assert "/prawduct:critic final" not in reason, reason

    def test_a_pass_linking_to_nothing_it_names_still_asks_for_final(self, tmp_path):
        """The control for the message's other state: a pass from before the
        field with no review at its base tree names nothing to wait for."""
        repo = _finished_plan_repo(tmp_path)
        _append(repo, _review("rev-pass", VERIFY_MODE, T1, T2), here=True)
        ok, reason = gates._critic_session_satisfies_gate(repo)
        assert not ok
        assert "no review it verifies is on record" in reason, reason
        assert "/prawduct:critic final" in reason, reason

    def test_a_cycle_of_passes_ends(self, tmp_path):
        """Found by id wherever it sits, so store order no longer ends the walk;
        a malformed store naming a cycle must not hang the Stop hook."""
        repo = _finished_plan_repo(tmp_path)
        _append(repo, _review("rev-p1", VERIFY_MODE, T2, T1, verifies="rev-p2"), here=True)
        _append(repo, _review("rev-p2", VERIFY_MODE, T1, T2, verifies="rev-p1"), here=True)
        ok, reason = gates._critic_session_satisfies_gate(repo)
        assert not ok
        assert "no review it verifies is on record" in reason, reason


class TestTheRollCallFollowsTheAnchor:
    """``critic_consolidate.carried_blocking`` without a composition carries the
    anchor's own blockers — the anchored review's, not the tree's newest."""

    def _facts(self, **pass_kw):
        old, new, pass_ = _two_reviews_of_one_tree(**pass_kw)
        old["body"]["findings"] = [_blocker("F-1", "the anchored review's blocker")]
        new["body"]["findings"] = [_blocker("F-9", "a sibling's blocker")]
        return [old, new, pass_]

    @staticmethod
    def _named(carried):
        return [(c["review_id"], c["fid"]) for c in carried]

    def test_at_dispatch_the_chosen_anchor_is_carried(self):
        facts = self._facts()[:2]
        carried = cc.carried_blocking(facts, T1, "rev-pass", None, anchor_id="rev-old")
        assert self._named(carried) == [("rev-old", "F-1")]

    def test_a_recorded_pass_carries_its_recorded_anchor(self, tmp_path, monkeypatch):
        """Through the derived findings record a recorded pass renders: the
        fact's `verifies` must reach the roll-call."""
        facts = self._facts()
        seen = {}
        monkeypatch.setattr(cc, "gate_counted_blockers", lambda *a, **k: None)
        monkeypatch.setattr(
            cc, "fact_to_cache_record",
            lambda fact, *, carried, store, prawduct_dir: seen.setdefault("carried", carried),
        )
        (tmp_path / ".prawduct").mkdir()
        cc.branch_review_record(tmp_path / ".prawduct", facts[-1], facts)
        assert self._named(seen["carried"]) == [("rev-old", "F-1")]

    def test_an_anchor_not_in_the_store_carries_nothing(self):
        facts = self._facts()
        assert cc.carried_blocking(facts, T1, "rev-pass", None, anchor_id="rev-gone") == []

    def test_a_pass_from_before_the_field_carries_by_tree(self):
        facts = self._facts(verifies=_ABSENT)
        assert self._named(cc.carried_blocking(facts, T1, "rev-pass", None)) == [
            ("rev-new", "F-9"),
        ]


class TestTheChainsFollowTheAnchor:
    def test_review_chain_steps_back_through_the_anchor(self):
        reviews = _two_reviews_of_one_tree()
        chain = critic_mode.review_chain(reviews, reviews[-1])
        assert [f["id"] for f in chain] == ["rev-pass", "rev-old"]

    def test_the_extended_line_reaches_the_anchors_commit(self):
        """A pass recording no `base_commit` takes its commits from the line it
        extends; that is the anchored review's, not the sibling's."""
        old, new, pass_ = _two_reviews_of_one_tree()
        old["body"]["base_commit"] = "a" * 40
        new["body"]["base_commit"] = "b" * 40
        line = plan_status._extended_reviews([old, new, pass_], pass_)
        assert [f["id"] for f in line] == ["rev-old"]

    def test_review_chain_ends_at_an_anchor_already_on_it(self):
        """p2 and p1 name each other, and an unrelated review R stands at p1's
        base tree. Back at p2 the walk must end, not step on to R, which
        nothing links to."""
        unrelated = _review("rev-r", CHUNK, T0, T2)
        p1 = _review("rev-p1", VERIFY_MODE, T2, T1, verifies="rev-p2")
        p2 = _review("rev-p2", VERIFY_MODE, T1, T2, verifies="rev-p1")
        chain = critic_mode.review_chain([unrelated, p1, p2], p2)
        assert [f["id"] for f in chain] == ["rev-p2", "rev-p1"]

    def test_the_chain_and_the_stop_hook_agree_whatever_the_order(self, tmp_path):
        """Another worktree's `cumulative` of T1 recorded BEFORE this worktree's
        `chunk` of T1, and the pass verifies the chunk. The Stop hook judges
        the chunk and asks for a final; the chain must not credit the sibling's
        cumulative as this branch's boundary review."""
        repo = _finished_plan_repo(tmp_path)
        sibling = _review("rev-sibling", CUMULATIVE, OTHER_BASE, T1, worktree="/sibling")
        anchor = _review("rev-anchor", CHUNK, T0, T1)
        pass_ = _review("rev-pass", VERIFY_MODE, T1, T2, verifies="rev-anchor")
        _append(repo, sibling, here=False)
        _append(repo, anchor, here=True)
        _append(repo, pass_, here=True)
        ok, reason = gates._critic_session_satisfies_gate(repo)
        assert not ok and f"over a '{CHUNK}' review" in reason, reason
        facts = evidence.read_facts(repo)["facts"]
        newest = next(f for f in facts if f["id"] == "rev-pass")
        chain = critic_mode.review_chain(facts, newest)
        assert [f["id"] for f in chain] == ["rev-pass", "rev-anchor"]
        assert not critic_mode.boundary_review_on_chain(chain)

    def test_the_extended_line_ends_on_a_cycle(self):
        p1 = _review("rev-p1", VERIFY_MODE, T2, T1, verifies="rev-p2")
        p2 = _review("rev-p2", VERIFY_MODE, T1, T2, verifies="rev-p1")
        assert plan_status._extended_reviews([p1, p2], p2) is None


class TestReviewChainConsumersOnAnAnchoredPass:
    """What each reader of ``critic_mode.review_chain`` sees once an anchored
    pass links to its anchor alone: another review of the anchor's tree,
    recorded before the anchor, is no longer on the pass's chain. Each test is
    one consumer, on the shape where the old rule and this one differ."""

    def _chain(self, earlier_mode, *, earlier_chunks=None, earlier_findings=None,
               anchor_mode=CHUNK, anchor_chunks=None):
        earlier = _review("rev-earlier", earlier_mode, OTHER_BASE, T1,
                          findings=earlier_findings)
        anchor = _review("rev-anchor", anchor_mode, T0, T1)
        if earlier_chunks is not None:
            earlier["body"]["chunks"] = earlier_chunks
        if anchor_chunks is not None:
            anchor["body"]["chunks"] = anchor_chunks
        pass_ = _review("rev-pass", VERIFY_MODE, T1, T2, verifies="rev-anchor")
        facts = [earlier, anchor, pass_]
        return facts, critic_mode.review_chain(facts, pass_)

    def test_chunk_inheritance_takes_the_anchors_chunks(self):
        """`chain_named_chunks` (the verify proposal and `chain_certified_chunks`)
        reads the first naming fact on the chain. With the earlier review on
        it, that was the earlier review's chunk, ahead of the anchor's own."""
        _facts, chain = self._chain(CHUNK, earlier_chunks=["02"], anchor_chunks=["01"])
        assert critic_mode.chain_named_chunks(chain) == ["01"]

    def test_boundary_credit_needs_the_cumulative_on_the_walk(self):
        """`boundary_review_on_chain` (`review_owed_after`,
        `boundary_cumulative_still_owed`): a `cumulative` of the anchor's tree
        recorded before the anchor is not credited, as the Stop hook (which
        judges the anchor) never credited it either."""
        _facts, chain = self._chain(CUMULATIVE)
        assert not critic_mode.boundary_review_on_chain(chain)

    def test_open_blocker_on_chain_reads_the_walk_only(self):
        """`_open_blocker_on_chain` (the deferral) no longer sees a blocker on
        the earlier review of the anchor's tree. The gate's composition still
        counts it: it stands at a node the gate's path stands on."""
        facts, chain = self._chain(
            CHUNK, earlier_findings=[_blocker("F-1", "the earlier review's blocker")]
        )
        assert not critic_mode._open_blocker_on_chain(facts, chain)
        verdict = ca.coverage_verdict(
            [dict(f, body=dict(f["body"], files_changed=[], files_reviewed=[])) for f in facts],
            T0, T2, lambda a, b: None,  # no free edges: the reviews make the path
        )
        assert verdict["status"] == "blocked", verdict


# ---------------------------------------------------------------------------
# The writer: critic-begin records it, consolidation persists it
# ---------------------------------------------------------------------------


class TestTheManifestValidatesTheField:
    def _manifest(self, **overrides):
        from test_critic_consolidate import _manifest_dict  # noqa: PLC0415

        return _manifest_dict("a" * 40, **overrides)

    def test_absent_is_valid_on_any_mode(self):
        assert cc.validate_manifest(self._manifest(mode=VERIFY_MODE)) == (True, "")
        assert cc.validate_manifest(self._manifest()) == (True, "")

    def test_a_verify_manifest_may_name_its_anchor(self):
        ok, reason = cc.validate_manifest(self._manifest(mode=VERIFY_MODE, verifies="rev-old"))
        assert ok, reason

    def test_only_a_verify_manifest_may_carry_it(self):
        ok, reason = cc.validate_manifest(self._manifest(verifies="rev-old"))
        assert not ok and "verifies" in reason, reason

    def test_it_must_be_a_non_empty_string(self):
        ok, reason = cc.validate_manifest(self._manifest(mode=VERIFY_MODE, verifies=7))
        assert not ok and "verifies" in reason, reason


class TestConsolidationRecordsTheAnchor:
    """End to end through `critic-begin` and `critic-consolidate`: the pass
    anchors to this worktree's review while a sibling's review of the same tree
    is the newest in the store, and its fact names the one it verified."""

    BLOCKER = {
        "correctness": [{"name": "Broken invariant", "goal": "Nothing Is Broken",
                         "severity": "blocking", "recommendation": "Fix it",
                         "files": ["src/app.py"]}],
    }

    def _verified(self, tmp_path, close=None):
        """Seed this worktree's review, append a sibling's newer review of the
        same tree, fix, dispatch the pass and consolidate it — through the CLI,
        or ``close`` when given (an in-process close a test can instrument)."""
        repo = tmp_path / "r"
        _init_repo(repo)
        _commit_file(repo, ".gitignore", ".prawduct/\n", "ignore review bookkeeping")
        tip = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        tree = _git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()
        (repo / ".prawduct").mkdir(exist_ok=True)

        _set_marker(repo)
        _write_manifest(repo, tip, id="rev-old-000001", head_tree=tree, head_commit=tip,
                        mode=FINAL_MODE)
        _full_roster_partials(repo, tip, findings_by_role=self.BLOCKER)
        seeded = _run_consolidate(repo)
        assert seeded.returncode == 0, seeded.stderr

        sibling = _review("rev-new-000001", CHUNK, OTHER_BASE, tree, worktree="/sibling")
        sibling["body"].update(head_commit=tip, findings=[_blocker("F-9", "a sibling's blocker")])
        _append(repo, sibling, here=False)

        (repo / "src/app.py").write_text("x = 2  # the fix\n")
        begun = _run_begin(repo, "--mode", "verify-resolutions")
        assert begun.returncode == 0, f"stdout={begun.stdout!r} stderr={begun.stderr!r}"
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        for role in manifest["roster"]:
            _write_partial(repo, role, manifest["commit_reviewed"], findings=[])
        if close is not None:
            assert close(repo) == 0
            return repo, manifest
        closed = _run_consolidate(repo)
        assert closed.returncode == 0, closed.stderr
        return repo, manifest

    def test_the_manifest_and_the_fact_name_the_anchored_review(self, tmp_path):
        repo, manifest = self._verified(tmp_path)
        assert manifest["verifies"] == "rev-old-000001"
        reviews = _store_facts(repo, "review")
        pass_ = next(f for f in reviews if f["id"] == manifest["id"])
        assert pass_["body"]["verifies"] == "rev-old-000001"
        assert ca.prior_review(reviews, pass_)["id"] == "rev-old-000001"
        # The premise: by tree alone the sibling's newer review is the link.
        by_tree = {**pass_, "body": {k: v for k, v in pass_["body"].items() if k != "verifies"}}
        assert ca.prior_review(reviews, by_tree)["id"] == "rev-new-000001"

    def test_the_close_carries_the_anchored_reviews_blocker(self, tmp_path, monkeypatch, capsys):
        """When the gate's composition is unavailable the close carries the
        anchor's own unresolved blockers, and the anchor is the one recorded.
        (With a composition both reviews' blockers count: each stands at a tree
        the gate's path stands on.)"""
        monkeypatch.setattr(cc, "gate_counted_blockers", lambda *a, **k: None)
        self._verified(tmp_path, close=lambda repo: cc.consolidate(repo, trigger="explicit"))
        captured = capsys.readouterr()
        done = next(
            (line for line in (captured.out + captured.err).splitlines() if "NEXT-ACTION" in line),
            None,
        )
        assert done is not None and "NOT DONE" in done, captured
        assert "rev-old-000001/R-1" in done, done
        assert "rev-new-000001" not in done, done

    def test_a_non_verify_fact_carries_no_anchor(self, tmp_path):
        repo, _manifest = self._verified(tmp_path)
        seed = next(f for f in _store_facts(repo, "review") if f["id"] == "rev-old-000001")
        assert "verifies" not in seed["body"]
