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
import subprocess
import sys
from pathlib import Path

import pytest

from test_critic_consolidate import (
    CUMULATIVE_MODE,
    FINDINGS_REL,
    HOOK,
    PARTIALS_REL,
    ROOT,
    _commit_file,
    _full_roster_partials,
    _git,
    _git_env,
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


def _two_branches_each_reviewed(tmp_path: Path, b_mode: "str | None" = None) -> "tuple[Path, dict]":
    """``main`` ← ``feature/b`` (reviewed, rev-b) and ``main`` ← ``feature/a``
    (reviewed after it, rev-a), with ``feature/a`` checked out — so the single
    slot names rev-a, which is off ``feature/b``'s lineage. ``b_mode`` sets
    rev-b's mode (the manifest default, `final`, when ``None``)."""
    repo = tmp_path / "r"
    _init_repo(repo)
    _commit_file(repo, ".gitignore", ".prawduct/\n", "ignore review bookkeeping")
    _commit_file(repo, "src/app.py", "x = 1\n", "init")
    (repo / ".prawduct").mkdir(exist_ok=True)

    _git(repo, "checkout", "--quiet", "-b", "feature/b")
    b_tip = _commit_file(repo, "src/b.py", "b = 1\n", "feat: b")
    _consolidate_review(repo, "rev-b-000001", b_tip,
                        head_tree=_tree(repo), head_commit=b_tip,
                        files_changed=["src/b.py"], files_reviewed=["src/b.py"],
                        **({"mode": b_mode} if b_mode else {}))

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


def _infer(repo: Path) -> "tuple[str, str]":
    """Bare `/prawduct:critic`'s mode resolution: `infer-critic-mode`, no args."""
    result = subprocess.run(  # noqa: S603 — fixed argv, no shell
        [sys.executable, str(HOOK), "infer-critic-mode"],
        cwd=str(repo), capture_output=True, text=True, timeout=30,
        env={**_git_env(repo), "CLAUDE_PLUGIN_ROOT": str(ROOT), "CLAUDE_PROJECT_DIR": str(repo)},
    )
    assert result.returncode == 0, result.stderr
    mode, rationale = result.stdout.strip().split("|", 1)
    return mode, rationale


class TestInferenceAfterABranchSwitch:
    """The THIRD answerer of "which review is this branch's" (#1150 follow-up):
    mode inference's rule 1 read the cache directly, so after a switch it saw
    the other branch's review, refused it as off-lineage, and fell through to
    `chunk` — while the dispatch it feeds would have anchored on this branch's
    own review. It now asks the same owner, read-only."""

    def test_bare_inference_picks_verify_on_the_switched_to_branchs_review(self, tmp_path):
        repo, _refs = _two_branches_each_reviewed(tmp_path)
        _git(repo, "checkout", "--quiet", "feature/b")
        (repo / "src/b.py").write_text("b = 2  # the fix, uncommitted\n")
        before = (repo / FINDINGS_REL).read_text()

        mode, rationale = _infer(repo)

        assert mode == "verify-resolutions", rationale
        assert rationale.startswith("rule-1 "), rationale
        # Inference asks; it does not write. The dispatch re-points the slot
        # when it anchors — a question must not move the view it is asking about.
        assert (repo / FINDINGS_REL).read_text() == before

    def test_and_the_dispatch_it_names_anchors_there(self, tmp_path):
        """Inference and dispatch agree: the mode inferred dispatches, on B."""
        repo, _refs = _two_branches_each_reviewed(tmp_path)
        _git(repo, "checkout", "--quiet", "feature/b")
        (repo / "src/b.py").write_text("b = 2  # the fix, uncommitted\n")

        mode, _rationale = _infer(repo)
        result = _run_begin(repo, "--mode", mode)

        assert result.returncode == 0, result.stderr
        assert _cached_fact_id(repo) == "rev-b-000001"

    def test_a_committed_fix_after_this_branchs_cumulative_infers_rule_1b(self, tmp_path):
        """Rule 1b asks the same question of the same owner: B's own
        `cumulative`, then a committed fix on B, is a verify pass — whatever
        review the slot last named on A."""
        repo, _refs = _two_branches_each_reviewed(tmp_path, b_mode=CUMULATIVE_MODE)
        _git(repo, "checkout", "--quiet", "feature/b")
        _commit_file(repo, "src/b.py", "b = 2  # the fix, committed\n", "fix: b")
        before = (repo / FINDINGS_REL).read_text()

        mode, rationale = _infer(repo)

        assert mode == "verify-resolutions", rationale
        assert rationale.startswith("rule-1b "), rationale
        assert (repo / FINDINGS_REL).read_text() == before

    def test_a_fix_outside_this_branchs_review_does_not_infer_verify(self, tmp_path):
        """Control: rule 1's subset check now runs against B's review, so new
        work outside B's reviewed files is not a verify pass."""
        repo, _refs = _two_branches_each_reviewed(tmp_path)
        _git(repo, "checkout", "--quiet", "feature/b")
        (repo / "src/elsewhere.py").write_text("new = 1\n")

        mode, rationale = _infer(repo)

        assert mode != "verify-resolutions", rationale


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


#: The ways the findings cache can fail to point at a review: the cache is
#: per-worktree and the store clone-shared, so a fresh worktree of a reviewed
#: branch has none at all.
def _no_cache(cache: Path) -> None:
    cache.unlink()


def _undecodable_cache(cache: Path) -> None:
    cache.write_bytes(b"\xff\xfe not utf-8\n")


def _cache_without_fact_id(cache: Path) -> None:
    data = json.loads(cache.read_text(encoding="utf-8"))
    del data["fact_id"]
    cache.write_text(json.dumps(data), encoding="utf-8")


def _cache_naming_a_gone_fact(cache: Path) -> None:
    data = json.loads(cache.read_text(encoding="utf-8"))
    data["fact_id"] = "rev-gone-000001"
    cache.write_text(json.dumps(data), encoding="utf-8")


POINTERLESS = [_no_cache, _undecodable_cache, _cache_without_fact_id, _cache_naming_a_gone_fact]


class TestAMissingPointerIsAStaleViewToo:
    """A wrong pointer defers to the owner (#1150); a MISSING one used to
    demote — no cache, an undecodable one, no `fact_id`, or a fact the store
    does not hold — though the store could answer. Each now asks
    `select_branch_review` and refuses only when it finds nothing."""

    @pytest.mark.parametrize("break_cache", POINTERLESS, ids=lambda f: f.__name__)
    def test_verify_anchors_on_this_branchs_review_without_a_usable_pointer(
        self, tmp_path, break_cache
    ):
        repo, _refs = _two_branches_each_reviewed(tmp_path)
        break_cache(repo / FINDINGS_REL)
        (repo / "src/a.py").write_text("a = 2  # the fix, uncommitted\n")

        result = _run_begin(repo, "--mode", "verify-resolutions")

        assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        rev_a = next(f for f in _store_facts(repo, "review") if f["id"] == "rev-a-000001")
        assert manifest["base_tree"] == rev_a["body"]["head_tree"]
        # The slot is re-pointed, so the verify reviewer reads A's findings.
        assert _cached_fact_id(repo) == "rev-a-000001"
        assert "rev-a-000001" in result.stderr, result.stderr
        # The note says why the pointer was passed over in words, not in a raw
        # exception: no errno, and no absolute path into this checkout.
        assert "Errno" not in result.stderr and str(repo) not in result.stderr, result.stderr

    @pytest.mark.parametrize("break_cache, said", [
        (_no_cache, "no findings cache in this worktree"),
        (_undecodable_cache, "the findings cache is not valid UTF-8"),
    ], ids=["absent", "undecodable"])
    def test_the_dispatch_note_says_why_in_words(self, tmp_path, break_cache, said):
        """A fresh worktree's verify dispatch note used to read "no readable
        prior findings cache ([Errno 2] No such file or directory: '/abs/...')"
        — an error, for the ordinary state of a new worktree, and a path."""
        repo, _refs = _two_branches_each_reviewed(tmp_path)
        break_cache(repo / FINDINGS_REL)
        (repo / "src/a.py").write_text("a = 2  # the fix, uncommitted\n")

        result = _run_begin(repo, "--mode", "verify-resolutions")

        assert result.returncode == 0, result.stderr
        note = next(ln for ln in result.stderr.splitlines() if "verify anchored on review" in ln)
        assert f"pointer: {said}." in note, note
        assert "Errno" not in note and "/" not in note.split("pointer:", 1)[1].split(".", 1)[0], note

    @pytest.mark.parametrize("break_cache", POINTERLESS, ids=lambda f: f.__name__)
    def test_bare_inference_picks_verify_without_a_usable_pointer(self, tmp_path, break_cache):
        repo, _refs = _two_branches_each_reviewed(tmp_path)
        cache = repo / FINDINGS_REL
        break_cache(cache)
        before = cache.read_bytes() if cache.exists() else None
        (repo / "src/a.py").write_text("a = 2  # the fix, uncommitted\n")

        mode, rationale = _infer(repo)

        assert mode == "verify-resolutions", rationale
        assert rationale.startswith("rule-1 "), rationale
        assert (cache.read_bytes() if cache.exists() else None) == before

    def test_with_no_review_on_the_branch_a_missing_cache_still_refuses(self, tmp_path):
        """Control: the owner finds nothing, so the pass demotes (exit 1), with
        the pointer's reason first."""
        repo, _refs = _two_branches_each_reviewed(tmp_path)
        _git(repo, "checkout", "--quiet", "main")
        _git(repo, "checkout", "--quiet", "-b", "feature/c")
        _commit_file(repo, "src/c.py", "c = 1\n", "feat: c")
        (repo / "src/c.py").write_text("c = 2\n")
        (repo / FINDINGS_REL).unlink()

        result = _run_begin(repo, "--mode", "verify-resolutions")

        assert result.returncode == 1, result.stderr
        # Renegotiated from "no readable prior findings cache (<errno + path>)":
        # a missing cache is the ordinary state of a fresh worktree, said so.
        assert "no findings cache in this worktree" in result.stderr, result.stderr
        assert "Errno" not in result.stderr and str(repo) not in result.stderr, result.stderr
        assert "no review anchors on this branch" in result.stderr, result.stderr
        assert not (repo / PARTIALS_REL / "manifest.json").exists()


class TestInferenceRendersThroughTheBriefingsRenderer:
    def test_a_rederived_verify_record_carries_its_anchors_blockers(self, tmp_path):
        """Rules 1 and 1b judge a re-derived review as `branch_review_record`
        renders it — the record the dispatch writes and the briefing shows. A
        bare projection drops what a verify pass carries: its anchor's
        unresolved blockers, so a clean-delta verify read as nothing to fix."""
        from lib import critic_mode

        repo, _refs = _two_branches_each_reviewed(tmp_path)
        _git(repo, "checkout", "--quiet", "feature/b")
        rev_b = next(f for f in _store_facts(repo, "review") if f["id"] == "rev-b-000001")
        verify = {**rev_b, "id": "rev-b-verify1", "ts": "2099-01-01T00:00:00Z",
                  "body": {**rev_b["body"], "findings": [],
                           "mode": cc._VERBOSE_VERIFY_RESOLUTIONS,
                           "base_tree": rev_b["body"]["head_tree"]}}
        assert evidence.append_envelope(repo, verify)["status"] == "appended"
        prawduct = repo / ".prawduct"
        facts = evidence.read_facts(repo)["facts"]

        record = critic_mode._verify_prior_record(prawduct, repo)

        assert record == cc.branch_review_record(prawduct, verify, facts)
        # Control: on this fixture the bare projection says something else —
        # it does not carry rev-b's blocker into the sentence the builder acts on.
        bare = cc.fact_to_cache_record(verify, store={"facts": facts})
        assert record["next_action"] != bare["next_action"], record["next_action"]
