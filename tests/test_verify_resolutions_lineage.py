"""Which review is this branch's review — the verify-resolutions anchor after a
branch switch (#1150) and the findings cache at a shared merge base (#1116).

Both defects are one class: the single-slot ``.critic-findings.json`` names
whichever review this clone last consolidated or ingested, and the two places
that read "this branch's newest review" out of it answered the question
differently. ``critic_consolidate.derive_branch_cache`` selected by commit range
alone, so at the merge base — a commit every sibling branch shares — it could
not tell this branch's review from a sibling's (#1116). ``_prior_review_fact``
never selected at all: it trusted the cached pointer, refused one that was off
this lineage, and never asked which review on this branch should have been
there instead (#1150). The fix gives the question one owner
(``derive_branch_cache``'s selection) and has the verify dispatch defer to it
whenever the cached pointer is not this branch's.

Real git throughout, through ``bin/prawduct-hook`` where the defect was
reported at the CLI.
"""

from __future__ import annotations

import json
from pathlib import Path

from test_critic_consolidate import (
    FINDINGS_REL,
    PARTIALS_REL,
    _commit_file,
    _full_roster_partials,
    _git,
    _init_repo,
    _run_begin,
    _run_consolidate,
    _set_marker,
    _store_facts,
    _write_manifest,
)

from lib import critic_consolidate as cc
from lib import evidence

BLOCKER = {
    "correctness": [{"name": "Broken invariant", "goal": "Nothing Is Broken",
                     "severity": "blocking", "recommendation": "Fix it",
                     "files": ["src/app.py"]}],
}


def _tree(repo: Path, rev: str = "HEAD") -> str:
    return _git(repo, "rev-parse", f"{rev}^{{tree}}").stdout.strip()


def _consolidate_review(repo: Path, review_id: str, head: str, **overrides) -> None:
    """Consolidate one review with a blocking finding; the cache then names it."""
    _set_marker(repo)
    _write_manifest(repo, head, id=review_id, **overrides)
    _full_roster_partials(repo, head, findings_by_role=BLOCKER)
    result = _run_consolidate(repo)
    assert result.returncode == 0, f"seed {review_id} failed: {result.stderr!r}"


def _cached_fact_id(repo: Path) -> str:
    return json.loads((repo / FINDINGS_REL).read_text())["fact_id"]


def _two_branches_each_reviewed(tmp_path: Path) -> "tuple[Path, dict]":
    """``main`` ← ``feature/b`` (reviewed, rev-b) and ``main`` ← ``feature/a``
    (reviewed after it, rev-a), with ``feature/a`` checked out — so the single
    slot names rev-a, which is off ``feature/b``'s lineage."""
    repo = tmp_path / "r"
    _init_repo(repo)
    _commit_file(repo, ".gitignore", ".prawduct/\n", "ignore review bookkeeping")
    _commit_file(repo, "src/app.py", "x = 1\n", "init")
    (repo / ".prawduct").mkdir(exist_ok=True)

    _git(repo, "checkout", "--quiet", "-b", "feature/b")
    b_tip = _commit_file(repo, "src/b.py", "b = 1\n", "feat: b")
    _consolidate_review(repo, "rev-b-000001", b_tip,
                        head_tree=_tree(repo), head_commit=b_tip,
                        files_changed=["src/b.py"], files_reviewed=["src/b.py"])

    _git(repo, "checkout", "--quiet", "main")
    _git(repo, "checkout", "--quiet", "-b", "feature/a")
    a_tip = _commit_file(repo, "src/a.py", "a = 1\n", "feat: a")
    _consolidate_review(repo, "rev-a-000001", a_tip,
                        head_tree=_tree(repo), head_commit=a_tip,
                        files_changed=["src/a.py"], files_reviewed=["src/a.py"])
    assert _cached_fact_id(repo) == "rev-a-000001"
    return repo, {"a_tip": a_tip, "b_tip": b_tip}


class TestVerifyAfterABranchSwitch:
    """#1150 — the dispatch finds the checked-out branch's newest review."""

    def test_verify_anchors_on_the_switched_to_branchs_own_review(self, tmp_path):
        repo, refs = _two_branches_each_reviewed(tmp_path)
        _git(repo, "checkout", "--quiet", "feature/b")
        (repo / "src/b.py").write_text("b = 2  # the fix, uncommitted\n")

        result = _run_begin(repo, "--mode", "verify-resolutions")

        assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        rev_b = next(f for f in _store_facts(repo, "review") if f["id"] == "rev-b-000001")
        assert manifest["base_tree"] == rev_b["body"]["head_tree"]
        assert "src/b.py" in manifest["files_changed"]
        assert "src/a.py" not in manifest["files_changed"], (
            "the delta spans the divergence — the sibling's review anchored it"
        )
        # The slot follows, so the verify reviewer reads B's findings as the
        # prior record, not A's.
        assert _cached_fact_id(repo) == "rev-b-000001"
        # Said out loud, naming both reviews: a re-anchor nobody sees is how a
        # reader concludes the cache was right all along.
        assert "rev-a-000001" in result.stderr and "rev-b-000001" in result.stderr, result.stderr

    def test_no_review_on_the_switched_to_branch_still_refuses_as_another_lineage(self, tmp_path):
        """Control: the fallback finds nothing to anchor on, so the existing
        refusal stands, with its reason and the cached id still named."""
        repo, _refs = _two_branches_each_reviewed(tmp_path)
        _git(repo, "checkout", "--quiet", "main")
        _git(repo, "checkout", "--quiet", "-b", "feature/c")
        _commit_file(repo, "src/c.py", "c = 1\n", "feat: c")
        (repo / "src/c.py").write_text("c = 2\n")

        result = _run_begin(repo, "--mode", "verify-resolutions")

        assert result.returncode == 1
        assert "another lineage" in result.stderr, result.stderr
        assert "rev-a-000001" in result.stderr
        assert not (repo / PARTIALS_REL / "manifest.json").exists()

    def test_an_on_lineage_cache_is_trusted_without_rederiving(self, tmp_path, monkeypatch):
        """The fallback is a fallback: a cached anchor that is this branch's is
        used as-is, and the selection is never asked."""
        repo, _refs = _two_branches_each_reviewed(tmp_path)

        def boom(*_a, **_k):
            raise AssertionError("derive_branch_cache must not run for an on-lineage cache")

        monkeypatch.setattr(cc, "derive_branch_cache", boom)
        fact, note = cc._prior_review_fact(repo, repo / ".prawduct", evidence.read_facts(repo))
        assert fact is not None and fact["id"] == "rev-a-000001"
        assert note == ""


def _merge_base_review(tmp_path: Path) -> "tuple[Path, dict, str]":
    """``feature/b`` cut at ``main``'s tip with no commits of its own, and one
    dirty-tree review of it — anchored, like every first review of a fresh
    branch, at the merge base. Returns (repo, that fact, the merge base)."""
    repo = tmp_path / "r"
    _init_repo(repo)
    _commit_file(repo, ".gitignore", ".prawduct/\n", "ignore review bookkeeping")
    base = _commit_file(repo, "src/app.py", "x = 1\n", "init")
    (repo / ".prawduct").mkdir(exist_ok=True)
    _git(repo, "checkout", "--quiet", "-b", "feature/b")
    (repo / "src/app.py").write_text("x = 2  # b's work, dirty\n")
    _consolidate_review(repo, "rev-own-00001", base,
                        head_tree=evidence.capture_tree(repo)["tree"], head_commit=None)
    own = next(f for f in _store_facts(repo, "review") if f["id"] == "rev-own-00001")
    assert own["actor"].get("branch") == "feature/b", own["actor"]
    assert evidence.review_anchor(own["body"]) == base
    return repo, own, base


def _as_sibling(fact: dict, review_id: str, branch: str) -> dict:
    """The same review shape, recorded later on another branch — what ingest
    appends when a sibling's first dirty-tree review travels on the merge
    base's note."""
    return {**fact, "id": review_id, "ts": "2099-01-01T00:00:00Z",
            "actor": {**fact["actor"], "branch": branch}}


class TestTheMergeBaseIsShared:
    """#1116 — at the merge base only, this branch's review is preferred."""

    def test_a_later_siblings_merge_base_review_does_not_take_the_slot(self, tmp_path):
        repo, own, base = _merge_base_review(tmp_path)
        sibling = _as_sibling(own, "rev-sibling-1", "feature/a")

        result = cc.derive_branch_cache(repo / ".prawduct", [own, sibling], [base])

        assert result["review"] == "rev-own-00001", result
        assert _cached_fact_id(repo) == "rev-own-00001"

    def test_a_siblings_merge_base_review_in_the_slot_moves_to_this_branchs(self, tmp_path):
        """The slot already names the sibling (the pre-fix ingest, or a branch
        switch at the merge base): the next derivation moves it."""
        repo, own, base = _merge_base_review(tmp_path)
        sibling = _as_sibling(own, "rev-sibling-1", "feature/a")
        cache = repo / FINDINGS_REL
        cache.write_text(json.dumps({**json.loads(cache.read_text()), "fact_id": "rev-sibling-1"}))

        result = cc.derive_branch_cache(repo / ".prawduct", [own, sibling], [base])

        assert result == {"status": "derived", "review": "rev-own-00001", "reason": None}

    def test_with_no_review_of_its_own_a_siblings_merge_base_review_still_answers(self, tmp_path):
        """Prefer, not exclude: a branch renamed since its review, or one whose
        review predates `actor.branch`, must not lose its anchor."""
        repo, own, base = _merge_base_review(tmp_path)
        sibling = _as_sibling(own, "rev-sibling-1", "feature/a")

        result = cc.derive_branch_cache(repo / ".prawduct", [sibling], [base])

        assert result["review"] == "rev-sibling-1", result

    def test_the_preference_is_the_merge_base_only(self, tmp_path):
        """Further along the branch, depth then time decide, as before: a commit
        of this branch is this branch's, so two reviews on it are told apart by
        `ts`, whatever branch name either carries (a rename, a delegate's
        worktree branch)."""
        repo, own, base = _merge_base_review(tmp_path)
        tip = _commit_file(repo, "src/app.py", "x = 3\n", "feat: b")
        at_tip = {**own["body"], "head_commit": tip, "dispatch_commit": tip,
                  "head_tree": _tree(repo)}
        earlier_ours = {**own, "id": "rev-tip-ours-1", "body": at_tip,
                        "ts": "2098-01-01T00:00:00Z"}
        later_renamed = {**_as_sibling(own, "rev-tip-later", "renamed/b"), "body": at_tip}

        result = cc.derive_branch_cache(
            repo / ".prawduct", [own, later_renamed, earlier_ours], [tip, base]
        )

        assert result["review"] == "rev-tip-later", result

    def test_verify_dispatch_prefers_this_branchs_merge_base_review(self, tmp_path):
        """The same preference at the dispatch, which reads the slot: a cache
        naming a sibling's merge-base review re-anchors on this branch's."""
        repo, own, _base = _merge_base_review(tmp_path)
        sibling = _as_sibling(own, "rev-sibling-1", "feature/a")
        assert evidence.append_envelope(repo, sibling)["status"] == "appended"
        cache = repo / FINDINGS_REL
        cache.write_text(json.dumps({**json.loads(cache.read_text()), "fact_id": "rev-sibling-1"}))

        fact, note = cc._prior_review_fact(repo, repo / ".prawduct", evidence.read_facts(repo))

        assert fact is not None and fact["id"] == "rev-own-00001", note
        assert "rev-sibling-1" in note and "feature/a" in note, note
