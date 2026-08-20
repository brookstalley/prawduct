"""The composed verdict is memoized, and the memo can never decide a gate.

`coverage_algebra.coverage_verdict` is pure and expensive — its free-edge search
keys every tree the store mentions, one `git ls-tree` each. Measured on the
framework repo (2,715 facts / 701 trees): 17.4 s cold, 0.01 s with the
per-invocation key cache warm. The store only grows, so every gate call paid it
again; a consumer session recorded nine invocations at 29–120 s, two of which hit
the 2-minute Bash ceiling.

What this file pins is the *distinction* that makes the memo legitimate under
`data-model.md`'s "derived views are disposable and never authoritative — no gate
reads a view to reach a verdict": the key covers every input the verdict is a
function of, so a hit replays a computation whose inputs are provably unchanged.
Each way an input can move gets an invalidation test, and each way the cache can
be unusable gets a recompute test.
"""

from __future__ import annotations

import itertools
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
sys.path.insert(0, str(ROOT))
from lib import coverage_algebra, evidence, gates, verdict_cache  # noqa: E402

_ids = itertools.count(1)


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(repo), capture_output=True, text=True, timeout=15,
    )
    assert proc.returncode == 0, f"git {args} failed: {proc.stderr}"
    return proc.stdout.strip()


def _commit(repo: Path, rel: str, content: str, msg: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _commit(repo, "code.py", "x = 1\n", "c1")
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "feature.py", "y = 2\n", "f1")
    return repo


def _tree(repo: Path, rev: str = "HEAD") -> str:
    return _git(repo, "rev-parse", f"{rev}^{{tree}}")


def _fact(repo: Path, base_tree: str, head_tree: str, files: list[str]) -> str:
    fact_id = f"rev-cache-{next(_ids):04d}"
    result = evidence.append_fact(
        repo, "review", fact_id,
        {
            "base_tree": base_tree, "head_tree": head_tree,
            "files_changed": list(files), "files_reviewed": list(files),
            "findings": [], "mode": "cumulative",
        },
    )
    assert result["status"] == "appended", result
    return fact_id


def _fns(repo: Path):
    return gates._cached_diff_fn(repo), gates._tree_key_fn(repo)


def _fresh(repo: Path) -> verdict_cache.VerdictCache:
    """A cache built now, from a fresh read — the way a separate gate
    invocation would build one."""
    return verdict_cache.VerdictCache.for_read(repo, evidence.read_facts(repo))


class TestHitsAndInvalidation:
    def test_a_second_invocation_replays_without_recomputing(self, tmp_path, monkeypatch):
        # The load-bearing assertion is not "it is faster" — it is that the
        # answer comes back with the computation made IMPOSSIBLE. A timing
        # assertion on a two-commit fixture would pass whether or not the cache
        # was ever consulted.
        repo = _repo(tmp_path)
        base, head = _tree(repo, "main"), _tree(repo)
        _fact(repo, base, head, ["feature.py"])
        diff_fn, key_fn = _fns(repo)
        facts = evidence.read_facts(repo).get("facts", [])
        first = _fresh(repo)
        expected = first.verdict(facts, base, head, diff_fn, key_fn)
        assert expected["status"] == "covered"
        assert first.flush() is True

        def explode(*_a, **_k):
            raise AssertionError("recomputed when the memo should have answered")

        monkeypatch.setattr(coverage_algebra, "coverage_verdict", explode)
        second = _fresh(repo)
        assert second.verdict(facts, base, head, diff_fn, key_fn) == expected
        assert second.hits == 1 and second.misses == 0

    def test_a_store_append_invalidates(self, tmp_path):
        repo = _repo(tmp_path)
        base, head = _tree(repo, "main"), _tree(repo)
        diff_fn, key_fn = _fns(repo)
        cold = _fresh(repo)
        facts = evidence.read_facts(repo).get("facts", [])
        assert cold.verdict(facts, base, head, diff_fn, key_fn)["status"] == "uncovered"
        cold.flush()
        # The review that changes the answer.
        _fact(repo, base, head, ["feature.py"])
        facts = evidence.read_facts(repo).get("facts", [])
        warm = _fresh(repo)
        assert warm.verdict(facts, base, head, diff_fn, key_fn)["status"] == "covered"
        assert warm.misses == 1, "a stale `uncovered` was replayed over a new review fact"

    def test_a_tree_change_invalidates(self, tmp_path):
        repo = _repo(tmp_path)
        base, head = _tree(repo, "main"), _tree(repo)
        _fact(repo, base, head, ["feature.py"])
        diff_fn, key_fn = _fns(repo)
        facts = evidence.read_facts(repo).get("facts", [])
        first = _fresh(repo)
        assert first.verdict(facts, base, head, diff_fn, key_fn)["status"] == "covered"
        first.flush()
        _commit(repo, "more.py", "z = 3\n", "unreviewed")
        moved = _tree(repo)
        second = _fresh(repo)
        assert second.verdict(facts, base, moved, diff_fn, key_fn)["status"] == "uncovered"
        assert second.misses == 1

    def test_a_plugin_upgrade_invalidates(self, tmp_path, monkeypatch):
        """The verdict depends on `coverage_algebra.is_judgeable_path`, which
        decides what needs review at all — and this cache outlives the plugin in
        `.git/prawduct/`. Widen judgeability in a release and every entry the
        older one wrote becomes a `covered` the new rules would not grant, so
        the computing code is an input to the key like any other.

        `CACHE_SCHEMA` was the intended guard and is a hand bump nothing
        enforces: a maintainer changing judgeability has no reason to open a
        cache module. The version is derived, which is what makes it a real
        input rather than a remembered one — and what this test pins.
        """
        repo = _repo(tmp_path)
        base, head = _tree(repo, "main"), _tree(repo)
        _fact(repo, base, head, ["feature.py"])
        diff_fn, key_fn = _fns(repo)
        facts = evidence.read_facts(repo).get("facts", [])
        monkeypatch.setattr(evidence, "_plugin_version", lambda: "3.3.4")
        first = _fresh(repo)
        assert first.verdict(facts, base, head, diff_fn, key_fn)["status"] == "covered"
        first.flush()
        # Same repo, same store, same trees — a newer plugin.
        monkeypatch.setattr(evidence, "_plugin_version", lambda: "3.4.0")
        second = _fresh(repo)
        assert second.verdict(facts, base, head, diff_fn, key_fn)["status"] == "covered"
        assert second.misses == 1, (
            "an entry written by a different plugin version was replayed — a "
            "judgeability change in that release would ship as a stale `covered`"
        )

    def test_an_unversioned_plugin_still_keys_deterministically(self, tmp_path, monkeypatch):
        """`_plugin_version()` is nullable by contract (never invented). The key
        has to survive that without collapsing two versions into one bucket or
        raising."""
        repo = _repo(tmp_path)
        base, head = _tree(repo, "main"), _tree(repo)
        _fact(repo, base, head, ["feature.py"])
        diff_fn, key_fn = _fns(repo)
        facts = evidence.read_facts(repo).get("facts", [])
        monkeypatch.setattr(evidence, "_plugin_version", lambda: None)
        first = _fresh(repo)
        assert first.verdict(facts, base, head, diff_fn, key_fn)["status"] == "covered"
        first.flush()
        second = _fresh(repo)
        assert second.verdict(facts, base, head, diff_fn, key_fn)["status"] == "covered"
        assert second.hits == 1

    def test_the_two_endpoints_are_not_interchangeable(self, tmp_path):
        # Both trees are in the key, so a reversed span is a different question
        # and must not collide with the forward one.
        repo = _repo(tmp_path)
        base, head = _tree(repo, "main"), _tree(repo)
        _fact(repo, base, head, ["feature.py"])
        diff_fn, key_fn = _fns(repo)
        facts = evidence.read_facts(repo).get("facts", [])
        cache = _fresh(repo)
        assert cache.verdict(facts, base, head, diff_fn, key_fn)["status"] == "covered"
        assert cache.verdict(facts, head, base, diff_fn, key_fn)["status"] == "uncovered"


class TestFailsToRecompute:
    def test_a_corrupt_cache_file_recomputes_without_error(self, tmp_path):
        repo = _repo(tmp_path)
        base, head = _tree(repo, "main"), _tree(repo)
        _fact(repo, base, head, ["feature.py"])
        diff_fn, key_fn = _fns(repo)
        facts = evidence.read_facts(repo).get("facts", [])
        verdict_cache.cache_path(repo).write_text("{not json at all")
        cache = _fresh(repo)
        assert cache.verdict(facts, base, head, diff_fn, key_fn)["status"] == "covered"
        assert cache.misses == 1

    def test_an_entry_from_another_schema_is_ignored(self, tmp_path):
        repo = _repo(tmp_path)
        base, head = _tree(repo, "main"), _tree(repo)
        _fact(repo, base, head, ["feature.py"])
        diff_fn, key_fn = _fns(repo)
        facts = evidence.read_facts(repo).get("facts", [])
        first = _fresh(repo)
        first.verdict(facts, base, head, diff_fn, key_fn)
        first.flush()
        path = verdict_cache.cache_path(repo)
        data = json.loads(path.read_text())
        data["schema"] = verdict_cache.CACHE_SCHEMA + 1
        path.write_text(json.dumps(data))
        second = _fresh(repo)
        assert second.verdict(facts, base, head, diff_fn, key_fn)["status"] == "covered"
        assert second.misses == 1, "an entry written under a different verdict shape was replayed"

    def test_a_malformed_entry_is_ignored(self, tmp_path):
        repo = _repo(tmp_path)
        base, head = _tree(repo, "main"), _tree(repo)
        _fact(repo, base, head, ["feature.py"])
        diff_fn, key_fn = _fns(repo)
        facts = evidence.read_facts(repo).get("facts", [])
        first = _fresh(repo)
        first.verdict(facts, base, head, diff_fn, key_fn)
        first.flush()
        path = verdict_cache.cache_path(repo)
        data = json.loads(path.read_text())
        data["entries"] = {k: {"status": None} for k in data["entries"]}
        path.write_text(json.dumps(data))
        second = _fresh(repo)
        assert second.verdict(facts, base, head, diff_fn, key_fn)["status"] == "covered"
        assert second.misses == 1

    def test_outside_a_git_repo_the_cache_is_inert_not_fatal(self, tmp_path):
        plain = tmp_path / "plain"
        plain.mkdir()
        cache = verdict_cache.VerdictCache.for_read(plain, evidence.read_facts(plain))
        assert cache.enabled is False
        assert cache.verdict([], "a" * 40, "b" * 40, lambda *_: None, lambda _: None) == {
            "status": "uncovered",
            "reason": (
                f"no evidence path composes from {'a' * 12} to {'b' * 12} — "
                "a review at the current tree closes the gap"
            ),
        }
        assert cache.flush() is False

    def test_a_returned_verdict_cannot_be_mutated_into_the_memo(self, tmp_path):
        # `check_cumulative_critic` annotates the verdict it gets back. If that
        # landed in the cached object, the next reader would see a verdict
        # carrying another call's endpoints.
        repo = _repo(tmp_path)
        base, head = _tree(repo, "main"), _tree(repo)
        _fact(repo, base, head, ["feature.py"])
        diff_fn, key_fn = _fns(repo)
        facts = evidence.read_facts(repo).get("facts", [])
        cache = _fresh(repo)
        first = cache.verdict(facts, base, head, diff_fn, key_fn)
        first["status"] = "tampered"
        first["path"].clear()
        second = cache.verdict(facts, base, head, diff_fn, key_fn)
        assert second["status"] == "covered"
        assert second["path"], "the cached path was emptied through a returned reference"


class TestGateIntegration:
    def test_the_schema_ahead_block_precedes_any_cached_answer(self, tmp_path, capsys):
        # The precheck must not become skippable by having asked the same
        # question once before: a newer plugin's fact blocks on every call.
        repo = _repo(tmp_path)
        base, head = _tree(repo, "main"), _tree(repo)
        _fact(repo, base, head, ["feature.py"])
        assert gates.check_cumulative_critic(repo) == 0
        capsys.readouterr()
        store = evidence.store_path(repo)
        lines = [json.loads(line) for line in store.read_text().splitlines()]
        lines[-1]["schema"] = 99
        store.write_text("".join(json.dumps(line) + "\n" for line in lines))
        assert gates.check_cumulative_critic(repo) == 1
        assert "schema-ahead" in capsys.readouterr().err

    def test_the_gate_output_is_byte_identical_cached_and_uncached(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        base, head = _tree(repo, "main"), _tree(repo)
        _fact(repo, base, head, ["feature.py"])
        assert gates.check_cumulative_critic(repo) == 0
        uncached = capsys.readouterr()
        assert verdict_cache.cache_path(repo).is_file(), "nothing was persisted to replay"
        assert gates.check_cumulative_critic(repo) == 0
        cached = capsys.readouterr()
        assert cached.out == uncached.out
        assert cached.err == uncached.err

    @pytest.mark.parametrize("shape", ["uncovered", "blocked"])
    def test_failure_paths_persist_their_verdict_too(self, tmp_path, capsys, shape):
        # The memo exists for the repeated-poll case, and polling happens most
        # when the gate is NOT passing. A flush that only ran on success would
        # leave exactly that case uncached.
        repo = _repo(tmp_path)
        base, head = _tree(repo, "main"), _tree(repo)
        # A store must EXIST for there to be a fingerprint to key on: with no
        # facts at all there is also no expensive composition to memoize, so the
        # cache stays inert by design. The uncovered shape therefore gets a real
        # fact that simply does not span the required interval.
        _fact(repo, "9" * 40, "8" * 40, ["elsewhere.py"])
        if shape == "blocked":
            evidence.append_fact(
                repo, "review", "rev-blocked-0001",
                {
                    "base_tree": base, "head_tree": head,
                    "files_changed": ["feature.py"], "files_reviewed": ["feature.py"],
                    "findings": [{"fid": "R-1", "severity": "BLOCKING", "title": "no"}],
                    "mode": "cumulative",
                },
            )
        assert gates.check_cumulative_critic(repo) == 1
        capsys.readouterr()
        path = verdict_cache.cache_path(repo)
        assert path.is_file(), f"a {shape} verdict was not persisted"
        assert json.loads(path.read_text())["entries"], "the cache file holds no entry"


class TestBounds:
    def test_the_cache_does_not_grow_without_bound(self, tmp_path):
        repo = _repo(tmp_path)
        _fact(repo, _tree(repo, "main"), _tree(repo), ["feature.py"])
        path = verdict_cache.cache_path(repo)
        path.parent.mkdir(parents=True, exist_ok=True)
        fingerprint = evidence.read_facts(repo)["fingerprint"]
        cache = verdict_cache.VerdictCache(path, fingerprint)
        # More distinct spans than the bound, each a trivial equal-tree verdict.
        for i in range(verdict_cache.MAX_ENTRIES + 20):
            tree = f"{i:040d}"
            cache.verdict([], tree, "f" * 40, lambda *_: None, lambda _: None)
        assert cache.flush() is True
        entries = json.loads(path.read_text())["entries"]
        assert len(entries) == verdict_cache.MAX_ENTRIES
