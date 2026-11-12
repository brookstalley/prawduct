"""The base-advance diagnosis costs the same however many review facts exist (#937).

``coverage.diagnose_base_advance_transfer`` checks condition 2 — a candidate
endpoint agrees with the required span's endpoint on every branch file — for
every distinct prior base and head the store's review facts name. It used to
spend one ``git diff`` subprocess per candidate: ~140 on this repo, ~2.9 s of a
warm Stop, growing with the store. Every pair now goes to git in ONE
``diff-tree --stdin`` (``evidence.tree_diffs``).

What must not move with it: the comparison is still git's own, so a mode-only
change on a branch file still denies the transfer (``cat-file --batch-check
<tree>:<path>`` would not see one — the fail-open the issue warns of), and a
tree git cannot read still degrades and denies, naming the tree.

Facts are passed to the diagnosis as plain dicts: it reads only the list it is
given, so no store is written.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
sys.path.insert(0, str(ROOT))
from lib import coverage, coverage_algebra, evidence  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0, f"git {args} failed: {proc.stderr}"
    return proc.stdout.strip()


def _commit(repo: Path, rel: str, content: str, msg: str, *, executable: bool = False) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    if executable:
        os.chmod(path, 0o755)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)


def _tree(repo: Path, rev: str = "HEAD") -> str:
    return _git(repo, "rev-parse", f"{rev}^{{tree}}")


def _review(base: str, head: str, files: "list[str]", fid: str) -> dict:
    return {
        "kind": "review",
        "id": fid,
        "body": {
            "base_tree": base,
            "head_tree": head,
            "files_changed": list(files),
            "files_reviewed": list(files),
            "findings": [],
        },
    }


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "core.fileMode", "true")
    _commit(repo, "code.py", "x = 1\n", "c1")
    return repo


def _advance_and_merge(repo: Path) -> None:
    _git(repo, "checkout", "-q", "main")
    _commit(repo, "upstream.py", "u = 1\n", "u1")
    _git(repo, "checkout", "-q", "feature")
    _git(repo, "merge", "-q", "--no-ff", "-m", "merge main", "main")


def _diagnose(repo: Path, facts: "list[dict]") -> "dict | None":
    """The diagnosis over merge-base(main, feature) → feature's tree, wired the
    way the gates wire it, with an in-memory key so nothing is persisted."""
    base = _tree(repo, _git(repo, "merge-base", "main", "feature"))
    head = _tree(repo, "feature")

    def diff_fn(a: str, b: str):
        return evidence.tree_diff(repo, a, b)

    def key_fn(tree: str):
        from lib import tree_key_memo

        entries = evidence.tree_entries(repo, tree)
        return None if entries is None else tree_key_memo.judgeable_key(entries)

    def verdict_fn(f, b, t):
        return coverage_algebra.coverage_verdict(f, b, t, diff_fn, key_fn)

    return coverage.diagnose_base_advance_transfer(repo, facts, base, head, diff_fn, verdict_fn)


@pytest.fixture
def git_calls(monkeypatch):
    """Every git subprocess the evidence layer spawns, by argv."""
    calls: list[tuple[str, ...]] = []
    real = evidence.run_git

    def counting(project_dir, *args, **kwargs):
        calls.append(args)
        return real(project_dir, *args, **kwargs)

    monkeypatch.setattr(evidence, "run_git", counting)
    return calls


def _stale_candidates(repo: Path, count: int) -> "list[dict]":
    """``count`` review facts whose endpoints are distinct trees git holds and
    that survive the ``files_changed`` prune, yet none of which agrees with the
    required span on feature.py — so each costs a condition-2 comparison and
    none reaches condition 1."""
    facts = []
    _git(repo, "checkout", "-q", "-b", "stale", "main")
    for i in range(count):
        _commit(repo, "feature.py", f"y = {100 + 2 * i}\n", f"s{i}a")
        before = _tree(repo)
        _commit(repo, "feature.py", f"y = {101 + 2 * i}\n", f"s{i}b")
        facts.append(_review(before, _tree(repo), ["feature.py"], f"rev-stale-{i}"))
    _git(repo, "checkout", "-q", "feature")
    return facts


# ---------------------------------------------------------------------------
# The cost does not grow with the review-fact count
# ---------------------------------------------------------------------------


class TestCostIsFlatInTheFactCount:
    def _calls_for(self, tmp_path: Path, git_calls, count: int) -> int:
        repo = _repo(tmp_path / f"n{count}")
        _git(repo, "checkout", "-q", "-b", "feature")
        _commit(repo, "feature.py", "y = 2\n", "f1")
        facts = _stale_candidates(repo, count)
        _advance_and_merge(repo)
        git_calls.clear()
        assert _diagnose(repo, facts) is None  # nothing agrees, nothing degraded
        return len(git_calls)

    def test_subprocess_count_does_not_grow_with_the_candidates(self, tmp_path, git_calls):
        few = self._calls_for(tmp_path, git_calls, 2)
        many = self._calls_for(tmp_path, git_calls, 12)
        # 2 → 12 facts is 4 → 24 distinct candidate endpoints. Per-candidate
        # diffs would spend 20 more subprocesses on the larger store.
        assert many == few, (few, many)

    def test_every_candidate_is_compared_in_one_git_call(self, tmp_path, git_calls):
        self._calls_for(tmp_path, git_calls, 6)
        comparisons = [args for args in git_calls if args[:1] in (("diff",), ("diff-tree",))]
        # The branch diff (diff_fn) plus ONE batched comparison.
        assert [args[0] for args in comparisons] == ["diff", "diff-tree"], comparisons


# ---------------------------------------------------------------------------
# What the batching must not loosen
# ---------------------------------------------------------------------------


class TestVerdictsAreUnchanged:
    def _reviewed_then_merged(self, tmp_path: Path, *, chmod_after_review: bool) -> "tuple[Path, list[dict]]":
        repo = _repo(tmp_path)
        _git(repo, "checkout", "-q", "-b", "feature")
        _commit(repo, "feature.py", "y = 2\n", "f1")
        facts = [_review(_tree(repo, "main"), _tree(repo), ["feature.py"], "rev-1")]
        if chmod_after_review:
            # Same blob, new mode: git's diff reports it; a (path, oid)
            # comparison would not.
            _commit(repo, "feature.py", "y = 2\n", "chmod", executable=True)
        _advance_and_merge(repo)
        return repo, facts

    def test_a_clean_advance_still_matches(self, tmp_path, git_calls):
        # The control: without it the denial below could come from a fixture
        # that never reaches the grant.
        repo, facts = self._reviewed_then_merged(tmp_path, chmod_after_review=False)
        result = _diagnose(repo, facts)
        assert result is not None and result["status"] == coverage.TRANSFER_MATCH, result
        assert result["files"] == ["feature.py"]

    def test_a_mode_only_change_on_a_branch_file_denies(self, tmp_path, git_calls):
        repo, facts = self._reviewed_then_merged(tmp_path, chmod_after_review=True)
        reviewed_head = facts[0]["body"]["head_tree"]
        assert _git(
            repo, "diff", "--name-only", reviewed_head, _tree(repo, "feature"), "--", "feature.py"
        ) == "feature.py"
        assert _diagnose(repo, facts) is None
        # ...and it was the batched comparison that saw it, not a fallback.
        assert any(args[:1] == ("diff-tree",) for args in git_calls)
        assert not any(
            args[:1] == ("diff",) and reviewed_head in args for args in git_calls
        ), "the mode-only candidate was re-asked per pair; the batch did not answer it"

    @pytest.mark.parametrize("bad", ["0" * 40, "not-a-tree"])
    def test_an_unreadable_candidate_tree_degrades_and_denies(self, tmp_path, monkeypatch, bad):
        repo, facts = self._reviewed_then_merged(tmp_path, chmod_after_review=False)
        facts[0]["body"]["head_tree"] = bad
        # Git cannot say which objects it holds, so nothing is pruned and the
        # comparison itself meets the unreadable tree.
        monkeypatch.setattr(evidence, "missing_objects", lambda *a, **k: None)
        result = _diagnose(repo, facts)
        assert result is not None and result["status"] == "unavailable", result
        assert result["reason"] == "a candidate tree could not be diffed"
        assert bad in result["unresolved_trees"]
        assert _tree(repo, "feature") in result["unresolved_trees"]

    def test_an_unreadable_candidate_does_not_mask_a_readable_match(self, tmp_path, monkeypatch):
        repo, facts = self._reviewed_then_merged(tmp_path, chmod_after_review=False)
        ghost = dict(facts[0], id="rev-ghost", body=dict(facts[0]["body"], head_tree="0" * 40))
        monkeypatch.setattr(evidence, "missing_objects", lambda *a, **k: None)
        result = _diagnose(repo, [facts[0], ghost])
        assert result is not None and result["status"] == coverage.TRANSFER_MATCH, result


# ---------------------------------------------------------------------------
# evidence.tree_diffs answers exactly as tree_diff does, pair by pair
# ---------------------------------------------------------------------------


class TestTreeDiffsAgreesWithTreeDiff:
    @pytest.fixture
    def trees(self, tmp_path):
        repo = _repo(tmp_path)
        _commit(repo, "a.py", "a\n", "a")
        _commit(repo, "d/b.py", "b\n", "b")
        t1 = _tree(repo)
        _commit(repo, "a.py", "a\n", "chmod a", executable=True)
        t2 = _tree(repo)
        _commit(repo, "d/b.py", "bb\n", "edit b")
        t3 = _tree(repo)
        return repo, t1, t2, t3

    def test_every_pair_matches_the_per_pair_answer(self, trees, git_calls):
        repo, t1, t2, t3 = trees
        pairs = [(t1, t2), (t2, t3), (t1, t3), (t3, t3), (t2, t3), (t1, "0" * 40), ("bad", t1)]
        paths = ["a.py", "d/b.py"]
        batched = evidence.tree_diffs(repo, pairs, paths)
        assert batched[(t1, t2)] == ["a.py"]  # mode-only
        assert batched[(t3, t3)] == []
        assert batched[(t1, "0" * 40)] is None
        assert batched[("bad", t1)] is None
        for a, b in pairs:
            assert batched[(a, b)] == evidence.tree_diff(repo, a, b, paths=paths), (a, b)

    def test_readable_pairs_cost_one_call(self, trees, git_calls):
        repo, t1, t2, t3 = trees
        git_calls.clear()
        evidence.tree_diffs(repo, [(t1, t2), (t2, t3), (t1, t3), (t3, t1)], ["a.py", "d/b.py"])
        assert [args[0] for args in git_calls] == ["diff-tree"]

    def test_a_pair_git_skips_is_asked_again_not_read_as_agreement(self, trees, git_calls):
        repo, t1, t2, _t3 = trees
        git_calls.clear()
        answers = evidence.tree_diffs(repo, [("0" * 40, t2), (t1, t2)], ["a.py"])
        assert answers == {("0" * 40, t2): None, (t1, t2): ["a.py"]}
        assert [args[0] for args in git_calls] == ["diff-tree", "diff"]

    def test_a_failed_batch_falls_back_per_pair(self, trees, monkeypatch):
        repo, t1, t2, t3 = trees
        real = evidence.run_git

        def failing_batch(project_dir, *args, **kwargs):
            if args[:1] == ("diff-tree",):
                return 1, "", "boom"
            return real(project_dir, *args, **kwargs)

        monkeypatch.setattr(evidence, "run_git", failing_batch)
        answers = evidence.tree_diffs(repo, [(t1, t2), (t2, t3)], ["a.py", "d/b.py"])
        assert answers == {(t1, t2): ["a.py"], (t2, t3): ["d/b.py"]}

    def test_a_newline_in_a_requested_path_skips_the_batch(self, trees, git_calls):
        repo, t1, t2, _t3 = trees
        git_calls.clear()
        answers = evidence.tree_diffs(repo, [(t1, t2)], ["a.py", "odd\nname.py"])
        assert answers == {(t1, t2): ["a.py"]}
        assert [args[0] for args in git_calls] == ["diff"]

    def test_an_empty_path_set_skips_the_batch(self, trees, git_calls):
        repo, t1, t2, _t3 = trees
        git_calls.clear()
        assert evidence.tree_diffs(repo, [(t1, t2)], []) == {(t1, t2): ["a.py"]}
        assert [args[0] for args in git_calls] == ["diff"]

    def test_a_path_holding_a_newline_beneath_a_requested_directory_parses(self, tmp_path):
        repo = _repo(tmp_path)
        _commit(repo, "d/x.py", "1\n", "x")
        t1 = _tree(repo)
        _commit(repo, f"d/{t1} {t1}\nz.py", "1\n", "hostile name")
        t2 = _tree(repo)
        answers = evidence.tree_diffs(repo, [(t1, t2), (t2, t2), (t1, t1)], ["d"])
        assert answers == {(t1, t2): [f"d/{t1} {t1}\nz.py"], (t2, t2): [], (t1, t1): []}


class TestParse:
    A, B, C = "a" * 40, "b" * 40, "c" * 40

    def test_headers_out_of_order_are_not_trusted(self):
        batch = [(self.A, self.B), (self.B, self.C)]
        out = f"{self.B} {self.C}\nx.py\0{self.A} {self.B}\n"
        assert evidence._parse_diff_tree_stdin(out, batch) is None

    def test_a_path_before_any_header_is_not_trusted(self):
        assert evidence._parse_diff_tree_stdin("x.py\0", [(self.A, self.B)]) is None

    def test_an_unterminated_path_is_not_trusted(self):
        out = f"{self.A} {self.B}\nx.py"
        assert evidence._parse_diff_tree_stdin(out, [(self.A, self.B)]) is None

    def test_a_missing_header_leaves_that_pair_out(self):
        batch = [(self.A, self.B), (self.B, self.C)]
        out = f"{self.B} {self.C}\nx.py\0"
        assert evidence._parse_diff_tree_stdin(out, batch) == {(self.B, self.C): ["x.py"]}
