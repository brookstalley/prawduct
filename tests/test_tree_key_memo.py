"""A tree's judgeable-content key is computed once per clone, and the memo can
never grant a free edge the slow path would deny.

Every SessionStart and Stop keys every tree the evidence store mentions, one
`git ls-tree` each. A memo that lived only for the process paid for the whole
store on every hook, so hook latency grew with the store's age: about 4 s of a
6.4 s Stop on a consumer snapshot of 231 trees, and a minute or more at 1,743.

What these tests pin is the cost itself (a warm key runs no `git ls-tree`),
plus each way the memo could lie: a `None` from an unreadable tree replayed as
if it were a key, a corrupt or foreign file read as entries, entries from other
code replayed, and a concurrent writer's entries lost.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
sys.path.insert(0, str(ROOT))
from lib import coverage_algebra, evidence, gates, tree_key_memo  # noqa: E402


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(repo), capture_output=True, text=True, timeout=15,
    )
    assert proc.returncode == 0, f"git {args} failed: {proc.stderr}"
    return proc.stdout.strip()


def _commit(repo: Path, rel: str, content: str, msg: str) -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)
    return _git(repo, "rev-parse", "HEAD^{tree}")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _commit(repo, "code.py", "x = 1\n", "c1")
    return repo


@pytest.fixture(autouse=True)
def _fresh_process():
    """Each test starts, and ends, as a process holding no memo — the state a
    new hook invocation starts in."""
    tree_key_memo._MEMOS.clear()
    yield
    tree_key_memo._MEMOS.clear()


def _new_process() -> None:
    """Save what this 'process' computed, then forget it in memory, so the next
    key function reads only what a new hook would read: the file."""
    tree_key_memo.flush_all()
    tree_key_memo._MEMOS.clear()


def _count_ls_tree(monkeypatch) -> list[str]:
    calls: list[str] = []
    real = evidence.tree_entries

    def counting(project_dir, tree):
        calls.append(tree)
        return real(project_dir, tree)

    monkeypatch.setattr(evidence, "tree_entries", counting)
    return calls


def _entries(repo: Path) -> dict:
    return json.loads(tree_key_memo.memo_path(repo).read_text())["entries"]


class TestTheCostIsPaidOncePerClone:
    def test_a_new_process_keys_a_known_tree_without_git(self, repo, monkeypatch):
        tree = _git(repo, "rev-parse", "HEAD^{tree}")
        cold = gates._tree_key_fn(repo)(tree)
        assert cold is not None
        _new_process()

        calls = _count_ls_tree(monkeypatch)
        warm = gates._tree_key_fn(repo)(tree)
        assert warm == cold
        assert calls == [], "a remembered tree was listed with git again"

    def test_the_memo_file_sits_beside_the_evidence_store(self, repo):
        gates._tree_key_fn(repo)(_git(repo, "rev-parse", "HEAD^{tree}"))
        _new_process()
        path = tree_key_memo.memo_path(repo)
        assert path.parent == evidence.store_path(repo).parent
        assert path.is_file()

    def test_a_large_cold_run_saves_before_the_process_ends(self, repo, monkeypatch):
        # A hook killed by the harness never reaches its exit handler, and a
        # cold store big enough to be killed is the one that must keep its
        # progress, so saving cannot wait for exit.
        monkeypatch.setattr(tree_key_memo, "FLUSH_EVERY", 2)
        trees = [_commit(repo, f"f{i}.py", f"v = {i}\n", f"c{i}") for i in range(3)]
        key_fn = gates._tree_key_fn(repo)
        for tree in trees[:2]:
            key_fn(tree)
        # No exit handler has run, yet the file already holds both keys.
        assert len(_entries(repo)) == 2


class TestTheMemoCannotGrantWhatGitWouldDeny:
    def test_an_unreadable_tree_is_never_remembered(self, repo, monkeypatch):
        tree = _git(repo, "rev-parse", "HEAD^{tree}")
        monkeypatch.setattr(evidence, "tree_entries", lambda _p, _t: None)
        assert gates._tree_key_fn(repo)(tree) is None
        _new_process()
        assert not tree_key_memo.memo_path(repo).exists() or _entries(repo) == {}

        # Once git can read it, it is asked again rather than replayed as None.
        monkeypatch.undo()
        calls = _count_ls_tree(monkeypatch)
        assert gates._tree_key_fn(repo)(tree) is not None
        assert calls == [tree]

    def test_free_edges_are_the_same_cold_and_warm(self, repo):
        # Two trees differing only in governance metadata share a key (a free
        # edge); a judgeable change gives a different key. The memo must
        # reproduce both answers, not just the first one it saw.
        base = _git(repo, "rev-parse", "HEAD^{tree}")
        metadata_only = _commit(repo, ".prawduct/change-log.md", "entry\n", "meta")
        judgeable = _commit(repo, "code.py", "x = 2\n", "code")
        cold_fn = gates._tree_key_fn(repo)
        cold = [cold_fn(t) for t in (base, metadata_only, judgeable)]
        assert cold[0] == cold[1] != cold[2]
        _new_process()
        warm_fn = gates._tree_key_fn(repo)
        assert [warm_fn(t) for t in (base, metadata_only, judgeable)] == cold


class TestAnUnusableMemoIsAMiss:
    @pytest.mark.parametrize(
        "content",
        [
            "{not json",
            json.dumps({"schema": 999, "entries": {}}),
            json.dumps({"schema": tree_key_memo.MEMO_SCHEMA, "entries": ["a"]}),
            json.dumps(["a", "list"]),
        ],
        ids=["corrupt", "foreign-schema", "entries-not-a-mapping", "not-an-object"],
    )
    def test_an_unreadable_file_recomputes_without_error(self, repo, monkeypatch, content):
        tree = _git(repo, "rev-parse", "HEAD^{tree}")
        path = tree_key_memo.memo_path(repo)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        calls = _count_ls_tree(monkeypatch)
        assert gates._tree_key_fn(repo)(tree) is not None
        assert calls == [tree]

    def test_a_malformed_entry_is_not_replayed(self, repo, monkeypatch):
        tree = _git(repo, "rev-parse", "HEAD^{tree}")
        gates._tree_key_fn(repo)(tree)
        _new_process()
        path = tree_key_memo.memo_path(repo)
        data = json.loads(path.read_text())
        data["entries"] = {k: "not-a-digest" for k in data["entries"]}
        path.write_text(json.dumps(data))

        calls = _count_ls_tree(monkeypatch)
        assert len(gates._tree_key_fn(repo)(tree)) == 64
        assert calls == [tree]

    def test_keys_from_other_code_are_not_replayed(self, repo, monkeypatch):
        # A classifier change ships in a new version (installed copies) or a
        # new plugin tree (a checkout); either must re-key every tree.
        tree = _git(repo, "rev-parse", "HEAD^{tree}")
        gates._tree_key_fn(repo)(tree)
        _new_process()
        monkeypatch.setattr(evidence, "_plugin_version", lambda: "999.0.0")
        calls = _count_ls_tree(monkeypatch)
        gates._tree_key_fn(repo)(tree)
        assert calls == [tree]

    def test_outside_a_git_repo_the_memo_is_inert_not_fatal(self, tmp_path):
        memo = tree_key_memo.for_project(tmp_path / "not-a-repo")
        memo.put("a" * 40, "b" * 64)
        assert memo.get("a" * 40) is None
        assert memo.flush() is False


class TestTheFileStaysBoundedAndShared:
    def test_the_memo_evicts_the_least_recently_used(self, repo, monkeypatch):
        monkeypatch.setattr(tree_key_memo, "MAX_ENTRIES", 2)
        trees = [_commit(repo, f"f{i}.py", f"v = {i}\n", f"c{i}") for i in range(3)]
        key_fn = gates._tree_key_fn(repo)
        key_fn(trees[0])
        key_fn(trees[1])
        _new_process()
        # Reading trees[0] again makes trees[1] the oldest.
        key_fn = gates._tree_key_fn(repo)
        key_fn(trees[0])
        key_fn(trees[2])
        _new_process()
        kept = {k.split(":", 1)[1] for k in _entries(repo)}
        assert kept == {trees[0], trees[2]}

    def test_a_concurrent_writers_entries_survive_a_flush(self, repo):
        first, second = (_commit(repo, f"w{i}.py", f"w = {i}\n", f"w{i}") for i in range(2))
        path = tree_key_memo.memo_path(repo)
        one = tree_key_memo.TreeKeyMemo(path, tree_key_memo._identity())
        other = tree_key_memo.TreeKeyMemo(path, tree_key_memo._identity())
        one.put(first, "1" * 64)
        other.put(second, "2" * 64)
        assert one.flush() and other.flush()
        kept = {k.split(":", 1)[1] for k in _entries(repo)}
        assert kept == {first, second}

    def test_a_warm_run_rewrites_nothing(self, repo):
        # Rewriting the file just to reorder it would put a whole-file write on
        # every warm hook.
        tree = _git(repo, "rev-parse", "HEAD^{tree}")
        gates._tree_key_fn(repo)(tree)
        _new_process()
        path = tree_key_memo.memo_path(repo)
        before = path.stat().st_mtime_ns
        gates._tree_key_fn(repo)(tree)
        assert tree_key_memo.for_project(repo).flush() is False
        assert path.stat().st_mtime_ns == before


def test_the_verdict_is_identical_with_the_memo_warm(repo):
    """End to end through `coverage_verdict`: a span covered through a review
    edge plus a metadata-only free edge reads the same from a warm memo."""
    base = _git(repo, "rev-parse", "HEAD^{tree}")
    head = _commit(repo, "feature.py", "y = 2\n", "f1")
    evidence.append_fact(
        repo, "review", "rev-memo-0001",
        {"base_tree": base, "head_tree": head, "files_changed": ["feature.py"],
         "files_reviewed": ["feature.py"], "findings": [], "mode": "cumulative"},
    )
    target = _commit(repo, ".prawduct/change-log.md", "entry\n", "meta")
    facts = evidence.read_facts(repo).get("facts", [])

    cold = coverage_algebra.coverage_verdict(
        facts, base, target, gates._cached_diff_fn(repo), gates._tree_key_fn(repo)
    )
    assert cold["status"] == "covered"
    _new_process()
    warm = coverage_algebra.coverage_verdict(
        facts, base, target, gates._cached_diff_fn(repo), gates._tree_key_fn(repo)
    )
    assert warm == cold


def test_put_refuses_anything_but_a_computed_digest(repo):
    """The second layer behind the caller's never-put-None: even a caller that
    passed an unreadable tree's None, or garbage, stores nothing."""
    tree = _git(repo, "rev-parse", "HEAD^{tree}")
    memo = tree_key_memo.for_project(repo)
    for bad in (None, "", "not-a-digest", "A" * 64):
        memo.put(tree, bad)
    assert memo.get(tree) is None
    assert memo.flush() is False


class TestTreesGitNoLongerHolds:
    """A store keeps naming trees after git has collected them (a rebased
    branch's), and such a tree is never remembered, so each hook asked git for
    it again, one failed `ls-tree` apiece. One batch check answers them all."""

    def test_missing_objects_answers_in_one_call(self, repo, monkeypatch):
        present = _git(repo, "rev-parse", "HEAD^{tree}")
        gone = "0" * 39 + "1"
        calls: list[tuple] = []
        real = evidence.run_git

        def counting(project_dir, *args, **kwargs):
            calls.append(args)
            return real(project_dir, *args, **kwargs)

        monkeypatch.setattr(evidence, "run_git", counting)
        assert evidence.missing_objects(repo, [present, gone, "not-an-id"]) == {gone, "not-an-id"}
        assert [a[0] for a in calls] == ["cat-file"]

    def test_missing_objects_is_none_when_git_cannot_answer(self, tmp_path):
        assert evidence.missing_objects(tmp_path, ["0" * 40]) is None

    def test_a_collected_tree_is_denied_without_a_per_tree_call(self, repo, monkeypatch):
        present = _git(repo, "rev-parse", "HEAD^{tree}")
        gone = "0" * 39 + "1"
        calls = _count_ls_tree(monkeypatch)
        key_fn = gates._tree_key_fn(repo)
        adjacency = coverage_algebra._free_classes({present, gone}, key_fn)
        assert key_fn(gone) is None, "a tree git does not hold must deny a free edge"
        assert gone not in adjacency
        assert calls == [present], "the collected tree still cost its own ls-tree"
        _new_process()
        assert all(not k.endswith(gone) for k in _entries(repo)), "a denial was persisted"

    def test_when_the_batch_check_fails_each_tree_is_asked_the_slow_way(self, repo, monkeypatch):
        present = _git(repo, "rev-parse", "HEAD^{tree}")
        gone = "0" * 39 + "1"
        monkeypatch.setattr(evidence, "missing_objects", lambda _p, _ids: None)
        calls = _count_ls_tree(monkeypatch)
        key_fn = gates._tree_key_fn(repo)
        coverage_algebra._free_classes({present, gone}, key_fn)
        assert key_fn(gone) is None and key_fn(present) is not None
        assert sorted(calls) == sorted([present, gone])
