"""Tests for the kernel-v3 evidence store (kernel-evidence-store ch.01).

The store is the keystone the whole v3 gate redesign composes over, so the
claims pinned here are the design's load-bearing ones (D1–D3, D9 in
``kernel-v3-evidence-design.md``):

* **D1 location/sharing** — the store lives in the clone's git common dir, so
  a fact appended in one worktree is read from another; unrelated repos never
  share; no git repo means no store (loud, no fallback).
* **D2 envelope** — schema on every record; (kind, id) dedupe (idempotent
  appends, CRT-4B7X); one-write O_APPEND concurrency.
* **D3 tree capture** — a temporary index captures the working tree without
  mutating the session's real index or working tree (R1), includes untracked,
  excludes gitignored, and a verbatim commit preserves the tree SHA.
* **D9 error posture** — every enumerated error path yields exactly its
  designed outcome: torn tail self-heals on next append, malformed interior
  lines are excluded loudly, schema-ahead records are surfaced (never
  silently dropped), and exclusion can only remove evidence, never invent it.

Real git repos, sterile config (commits via ``-c user.*``), mirroring the
sibling store tests (``test_governance_ledger.py``).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"

sys.path.insert(0, str(ROOT))
from lib import evidence  # noqa: E402


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


def _make_repo(base: Path, name: str = "repo") -> Path:
    repo = base / name
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "code.py").write_text("x = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c1")
    return repo


def _store_file(repo: Path) -> Path:
    path = evidence.store_path(repo)
    assert path is not None
    return path


# ---------------------------------------------------------------------------
# D1 — location and sharing
# ---------------------------------------------------------------------------


class TestStoreLocation:
    def test_store_lives_in_git_common_dir(self, tmp_path):
        repo = _make_repo(tmp_path)
        path = _store_file(repo)
        common = Path(_git(repo, "rev-parse", "--git-common-dir"))
        expected = (repo / common).resolve() / "prawduct" / "evidence.jsonl"
        assert path == expected

    def test_no_git_repo_means_no_store(self, tmp_path):
        plain = tmp_path / "plain"
        plain.mkdir()
        assert evidence.store_path(plain) is None
        result = evidence.append_fact(plain, "review", "r-1", {})
        assert result["status"] == "error"
        assert "no git repository" in result["reason"]
        read = evidence.read_facts(plain)
        assert read["status"] == "error"

    def test_absent_file_is_the_empty_store(self, tmp_path):
        repo = _make_repo(tmp_path)
        read = evidence.read_facts(repo)
        assert read["status"] == "empty"
        assert read["facts"] == []
        assert not _store_file(repo).exists()  # reading never creates it

    def test_fact_appended_in_one_worktree_reads_from_another(self, tmp_path):
        repo = _make_repo(tmp_path)
        wt = tmp_path / "wt"
        _git(repo, "worktree", "add", "-q", str(wt), "-b", "wtbranch")
        appended = evidence.append_fact(
            wt, "review", "r-wt", {"head_tree": "abc"}
        )
        assert appended["status"] == "appended"
        read = evidence.read_facts(repo)  # primary checkout sees it
        assert [f["id"] for f in read["facts"]] == ["r-wt"]
        assert read["facts"][0]["actor"]["worktree"] == str(wt)

    def test_unrelated_repos_do_not_share(self, tmp_path):
        repo_a = _make_repo(tmp_path, "a")
        repo_b = _make_repo(tmp_path, "b")
        evidence.append_fact(repo_a, "review", "r-a", {})
        assert evidence.read_facts(repo_b)["status"] == "empty"


# ---------------------------------------------------------------------------
# D2 — envelope, dedupe, concurrency
# ---------------------------------------------------------------------------


class TestEnvelope:
    def test_envelope_round_trip(self, tmp_path):
        repo = _make_repo(tmp_path)
        body = {"head_tree": "t1", "counts": {"blocking": 0}}
        result = evidence.append_fact(repo, "review", "r-1", body)
        assert result["status"] == "appended"
        fact = evidence.read_facts(repo)["facts"][0]
        assert fact["schema"] == evidence.SCHEMA_VERSION
        assert fact["kind"] == "review"
        assert fact["id"] == "r-1"
        assert fact["body"] == body
        assert fact["actor"]["worktree"] == str(repo)
        assert "ts" in fact
        # plugin version rides when the bundled VERSION exists (it does here)
        assert fact["actor"]["plugin"] == (ROOT / "VERSION").read_text().strip()

    def test_unknown_kind_rejected_at_write(self, tmp_path):
        repo = _make_repo(tmp_path)
        result = evidence.append_fact(repo, "vibes", "v-1", {})
        assert result["status"] == "error"
        assert "unknown fact kind" in result["reason"]
        assert not _store_file(repo).exists()

    def test_invalid_id_and_body_rejected(self, tmp_path):
        repo = _make_repo(tmp_path)
        assert evidence.append_fact(repo, "review", "", {})["status"] == "error"
        assert evidence.append_fact(repo, "review", "r", [])["status"] == "error"

    def test_duplicate_id_deduped_first_wins(self, tmp_path):
        repo = _make_repo(tmp_path)
        evidence.append_fact(repo, "review", "r-1", {"n": 1})
        evidence.append_fact(repo, "review", "r-1", {"n": 2})
        read = evidence.read_facts(repo)
        assert len(read["facts"]) == 1
        assert read["facts"][0]["body"] == {"n": 1}
        assert read["duplicates"] == 1

    def test_same_id_different_kind_is_not_a_duplicate(self, tmp_path):
        repo = _make_repo(tmp_path)
        evidence.append_fact(repo, "review", "x", {})
        evidence.append_fact(repo, "resolution", "x", {})
        assert len(evidence.read_facts(repo)["facts"]) == 2

    def test_has_fact_idempotency_probe(self, tmp_path):
        repo = _make_repo(tmp_path)
        assert not evidence.has_fact(repo, "review", "r-1")
        evidence.append_fact(repo, "review", "r-1", {})
        assert evidence.has_fact(repo, "review", "r-1")
        assert not evidence.has_fact(repo, "resolution", "r-1")

    def test_facts_of_kind_filters_unknown_future_kinds(self, tmp_path):
        repo = _make_repo(tmp_path)
        evidence.append_fact(repo, "review", "r-1", {})
        # A same-schema record of a kind this reader doesn't know (a newer
        # minor added it): coexists in facts, never satisfies a kind filter.
        store = _store_file(repo)
        future = {
            "schema": evidence.SCHEMA_VERSION,
            "kind": "promotion",
            "id": "p-1",
            "ts": "2026-07-12T00:00:00Z",
            "actor": {},
            "body": {},
        }
        with open(store, "a") as fh:
            fh.write(json.dumps(future) + "\n")
        read = evidence.read_facts(repo)
        assert len(read["facts"]) == 2
        assert [f["id"] for f in evidence.facts_of_kind(read, "review")] == ["r-1"]

    def test_concurrent_appends_stay_whole(self, tmp_path):
        repo = _make_repo(tmp_path)
        # Pre-create the store so threads race only on the append write.
        evidence.append_fact(repo, "review", "seed", {})
        errors: list[str] = []

        def worker(n: int) -> None:
            result = evidence.append_fact(
                repo, "review", f"r-{n}", {"payload": "x" * 200}
            )
            if result["status"] != "appended":
                errors.append(result["reason"])

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        read = evidence.read_facts(repo)
        assert read["excluded"] == 0
        assert len(read["facts"]) == 9  # seed + 8


# ---------------------------------------------------------------------------
# D9 — error posture, path by path
# ---------------------------------------------------------------------------


class TestErrorPosture:
    def test_torn_tail_excluded_loudly_then_healed_by_next_append(
        self, tmp_path, capsys
    ):
        repo = _make_repo(tmp_path)
        evidence.append_fact(repo, "review", "r-1", {})
        store = _store_file(repo)
        with open(store, "a") as fh:
            fh.write('{"schema": 1, "kind": "rev')  # crashed writer, no newline
        read = evidence.read_facts(repo)
        assert [f["id"] for f in read["facts"]] == ["r-1"]
        assert read["excluded"] == 1
        assert "torn tail" in capsys.readouterr().err
        # Self-heal: the next append leads with a newline, so it stays whole.
        evidence.append_fact(repo, "review", "r-2", {})
        assert "healed torn final line" in capsys.readouterr().err
        read = evidence.read_facts(repo)
        assert [f["id"] for f in read["facts"]] == ["r-1", "r-2"]
        assert read["excluded"] == 1  # the fragment stays excluded, attributed

    def test_terminated_malformed_final_line_not_called_torn_tail(
        self, tmp_path, capsys
    ):
        repo = _make_repo(tmp_path)
        evidence.append_fact(repo, "review", "r-1", {})
        with open(_store_file(repo), "a") as fh:
            fh.write("malformed but newline-terminated\n")  # will never heal
        read = evidence.read_facts(repo)
        assert read["excluded"] == 1
        err = capsys.readouterr().err
        assert "unparseable line" in err
        assert "torn tail" not in err  # no false heals-on-next-append promise

    def test_interior_corruption_excluded_never_crashes(self, tmp_path, capsys):
        repo = _make_repo(tmp_path)
        evidence.append_fact(repo, "review", "r-1", {})
        store = _store_file(repo)
        with open(store, "a") as fh:
            fh.write("not json at all\n")
            fh.write('["an", "array"]\n')
            fh.write('{"schema": "one", "kind": "review", "id": "bad"}\n')
        evidence.append_fact(repo, "review", "r-2", {})
        read = evidence.read_facts(repo)
        assert [f["id"] for f in read["facts"]] == ["r-1", "r-2"]
        assert read["excluded"] == 3
        err = capsys.readouterr().err
        assert "unparseable line" in err
        assert "non-object line" in err
        assert "invalid schema" in err

    def test_invalid_envelope_excluded(self, tmp_path, capsys):
        repo = _make_repo(tmp_path)
        store = _store_file(repo)
        store.parent.mkdir(parents=True, exist_ok=True)
        bad = {"schema": 1, "kind": "review", "id": "", "body": {}}
        store.write_text(json.dumps(bad) + "\n")
        read = evidence.read_facts(repo)
        assert read["facts"] == []
        assert read["excluded"] == 1
        assert "invalid envelope" in capsys.readouterr().err

    def test_schema_below_floor_excluded_as_malformed(self, tmp_path, capsys):
        repo = _make_repo(tmp_path)
        store = _store_file(repo)
        store.parent.mkdir(parents=True, exist_ok=True)
        zero = {"schema": 0, "kind": "review", "id": "r-0", "body": {}}
        store.write_text(json.dumps(zero) + "\n")
        read = evidence.read_facts(repo)
        assert read["facts"] == []
        assert read["excluded"] == 1
        assert read["schema_ahead"] == []
        assert "never a valid store version" in capsys.readouterr().err

    def test_schema_ahead_surfaced_never_silently_dropped(self, tmp_path, capsys):
        repo = _make_repo(tmp_path)
        evidence.append_fact(repo, "review", "r-1", {})
        store = _store_file(repo)
        ahead = {
            "schema": evidence.SCHEMA_VERSION + 1,
            "kind": "review",
            "id": "r-future",
            "ts": "2026-07-12T00:00:00Z",
            "actor": {},
            "body": {},
        }
        with open(store, "a") as fh:
            fh.write(json.dumps(ahead) + "\n")
        read = evidence.read_facts(repo)
        assert [f["id"] for f in read["facts"]] == ["r-1"]
        assert read["excluded"] == 0  # ahead is NOT lumped into excluded
        assert len(read["schema_ahead"]) == 1
        assert read["schema_ahead"][0]["id"] == "r-future"
        err = capsys.readouterr().err
        assert "newer prawduct" in err


# ---------------------------------------------------------------------------
# D3 — tree capture
# ---------------------------------------------------------------------------


class TestCaptureTree:
    def test_capture_does_not_mutate_session_state(self, tmp_path):
        repo = _make_repo(tmp_path)
        (repo / "code.py").write_text("x = 2\n")
        (repo / "untracked.py").write_text("y = 1\n")
        status_before = _git(repo, "status", "--porcelain")
        index_before = _git(repo, "ls-files", "-s")
        result = evidence.capture_tree(repo)
        assert result["status"] == "ok"
        assert _git(repo, "status", "--porcelain") == status_before
        assert _git(repo, "ls-files", "-s") == index_before

    def test_capture_includes_untracked_excludes_ignored(self, tmp_path):
        repo = _make_repo(tmp_path)
        (repo / ".gitignore").write_text("secret.txt\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "ignore")
        (repo / "untracked.py").write_text("y = 1\n")
        (repo / "secret.txt").write_text("no\n")
        result = evidence.capture_tree(repo)
        assert result["status"] == "ok"
        names = _git(repo, "ls-tree", "-r", "--name-only", result["tree"])
        assert "untracked.py" in names.splitlines()
        assert "secret.txt" not in names.splitlines()

    def test_clean_tree_equals_head_tree(self, tmp_path):
        repo = _make_repo(tmp_path)
        result = evidence.capture_tree(repo)
        assert result["status"] == "ok"
        assert result["clean"] is True
        assert result["tree"] == result["head_tree"]
        assert result["head_commit"] == _git(repo, "rev-parse", "HEAD")

    def test_verbatim_commit_preserves_captured_tree(self, tmp_path):
        repo = _make_repo(tmp_path)
        (repo / "code.py").write_text("x = 3\n")
        (repo / "new.py").write_text("z = 1\n")
        result = evidence.capture_tree(repo)
        assert result["status"] == "ok"
        assert result["clean"] is False
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "c2")
        assert _git(repo, "rev-parse", "HEAD^{tree}") == result["tree"]

    def test_capture_from_linked_worktree_visible_in_primary(self, tmp_path):
        repo = _make_repo(tmp_path)
        wt = tmp_path / "wt"
        _git(repo, "worktree", "add", "-q", str(wt), "-b", "wtbranch")
        (wt / "wtfile.py").write_text("w = 1\n")
        result = evidence.capture_tree(wt)
        assert result["status"] == "ok"
        # The tree object landed in the shared odb — readable from primary.
        typ = _git(repo, "cat-file", "-t", result["tree"])
        assert typ == "tree"

    def test_capture_outside_git_repo_returns_error(self, tmp_path):
        plain = tmp_path / "plain"
        plain.mkdir()
        result = evidence.capture_tree(plain)
        assert result["status"] == "error"
        assert result["reason"]  # attributed, never a silent empty dict

    def test_seed_copies_the_repo_index_when_it_exists(self, tmp_path, monkeypatch):
        """The stat-data seed, asserted at the mechanism rather than the clock.

        A timing assertion would be flaky on a loaded machine; what actually
        makes the capture cheap is that the temp index STARTS as a byte-for-
        byte copy of the repo's own, carrying its stat data, so ``add -A``
        can skip files whose stat still matches."""
        repo = _make_repo(tmp_path)
        seen = {}
        real_copy2 = evidence.shutil.copy2

        def spy(src, dst, *a, **k):
            seen["src"] = Path(src)
            return real_copy2(src, dst, *a, **k)

        monkeypatch.setattr(evidence.shutil, "copy2", spy)
        result = evidence.capture_tree(repo)
        assert result["status"] == "ok"
        assert result["seed"] == "index-copy"
        assert seen["src"] == Path(_git(repo, "rev-parse", "--absolute-git-dir")) / "index"

    def test_seed_falls_back_when_index_is_unreadable(self, tmp_path, monkeypatch, capsys):
        """A copy that cannot happen degrades to `read-tree HEAD` — slower,
        never wrong. Same tree either way."""
        repo = _make_repo(tmp_path)
        (repo / "code.py").write_text("x = 9\n")
        (repo / "extra.py").write_text("e = 1\n")
        expected = evidence.capture_tree(repo)["tree"]

        def refuse(src, dst, *a, **k):
            raise OSError("index unreadable")

        monkeypatch.setattr(evidence.shutil, "copy2", refuse)
        result = evidence.capture_tree(repo)
        assert result["status"] == "ok"
        assert result["tree"] == expected
        # The degradation is NOT silent: it is named in the result and on stderr,
        # so a capture that fell back is distinguishable from one that never had
        # a fast seed to lose.
        assert result["seed"] == "read-tree"
        assert "read-tree" in capsys.readouterr().err

    def test_seed_falls_back_when_a_partial_copy_is_left_behind(self, tmp_path, monkeypatch):
        """A copy that dies PART-way would leave a truncated index that git
        rejects as corrupt. The fallback must start from a clean slot."""
        repo = _make_repo(tmp_path)
        (repo / "extra.py").write_text("e = 1\n")

        def truncate_then_fail(src, dst, *a, **k):
            Path(dst).write_bytes(b"DIRC\x00garbage")
            raise OSError("disk full mid-copy")

        monkeypatch.setattr(evidence.shutil, "copy2", truncate_then_fail)
        result = evidence.capture_tree(repo)
        assert result["status"] == "ok"
        names = _git(repo, "ls-tree", "-r", "--name-only", result["tree"])
        assert "extra.py" in names.splitlines()

    def test_same_second_same_size_edit_is_still_captured(self, tmp_path):
        """The seed's sharpest failure mode, pinned with fixed timestamps
        rather than left to a race.

        Git's stat cache skips re-reading a file whose size and mtime still
        match the index entry. Its racily-clean rule is the escape hatch: an
        entry whose mtime is not older than the INDEX FILE's own may have been
        edited within the same timestamp tick, so git re-reads it. A copy of
        the index stamped with the CURRENT time silences that rule — and a
        same-second, same-size edit then vanishes from the captured tree,
        which would make a review vouch for a tree that never existed.

        Every timestamp here is forced equal because on a real clock the race
        lands only sometimes; the defect it exposes is permanent."""
        import os as _os

        stamp = 1_600_000_000  # any fixed epoch second — the point is they all MATCH
        repo = tmp_path / "racy"
        repo.mkdir()
        _git(repo, "init", "-q")
        # `utime` cannot move ctime, and git's default `core.trustctime` would
        # then re-read the file for the wrong reason, masking the very miss
        # under test.
        _git(repo, "config", "core.trustctime", "false")
        (repo / "code.py").write_text("x = 1\n")
        _os.utime(repo / "code.py", (stamp, stamp))
        _git(repo, "add", "-A")  # the entry records mtime == stamp
        _git(repo, "commit", "-q", "-m", "c1")

        (repo / "code.py").write_text("x = 9\n")  # same byte length as "x = 1\n"
        _os.utime(repo / "code.py", (stamp, stamp))
        _os.utime(Path(_git(repo, "rev-parse", "--absolute-git-dir")) / "index", (stamp, stamp))

        result = evidence.capture_tree(repo)
        assert result["status"] == "ok"
        blob = _git(repo, "ls-tree", "-r", result["tree"], "--", "code.py").split()[2]
        assert _git(repo, "cat-file", "-p", blob) == "x = 9"

    def test_capture_during_a_merge_conflict_resolves_to_the_working_tree(self, tmp_path):
        """The third case where the seeds differ going in and agree coming out.

        A copied index carries stage 1/2/3 entries that `read-tree HEAD` would
        have flattened. `add -A` re-stages an unmerged path from the working
        tree either way, so the capture is the conflicted file AS IT SITS ON
        DISK — markers included. `_seed_temp_index` says so in prose; this is
        the carrier for that claim, which otherwise rested on argument."""
        repo = _make_repo(tmp_path)
        _git(repo, "checkout", "-q", "-b", "other")
        (repo / "code.py").write_text("x = 2\n")
        _git(repo, "commit", "-q", "-am", "other")
        _git(repo, "checkout", "-q", "-")
        (repo / "code.py").write_text("x = 3\n")
        _git(repo, "commit", "-q", "-am", "mine")
        merge = subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "merge", "other"],
            cwd=str(repo), capture_output=True, text=True, timeout=15,
        )
        assert merge.returncode != 0, "fixture must actually conflict"
        assert _git(repo, "status", "--porcelain").startswith("UU"), "index must be unmerged"

        result = evidence.capture_tree(repo)
        assert result["status"] == "ok"
        assert result["seed"] == "index-copy"
        blob = _git(repo, "ls-tree", "-r", result["tree"], "--", "code.py").split()[2]
        assert "<<<<<<<" in _git(repo, "cat-file", "-p", blob)

    def test_capture_agrees_with_a_verbatim_commit_under_skip_worktree(self, tmp_path):
        """The one case where the two seeds genuinely disagree.

        ``--skip-worktree`` (what sparse checkout sets) tells ``add -A`` to
        leave a path alone. Copying the index preserves the flag, so the
        captured tree is what the user's own ``git add -A && git commit``
        would write — which is precisely the invariant `capture_tree`
        promises. A `read-tree HEAD` seed drops the flag and would stage a
        deletion for every file the checkout does not materialise."""
        repo = _make_repo(tmp_path)
        (repo / "sparse.py").write_text("s = 1\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "c2")
        _git(repo, "update-index", "--skip-worktree", "sparse.py")
        (repo / "sparse.py").unlink()  # outside the cone: not materialised

        result = evidence.capture_tree(repo)
        assert result["status"] == "ok"
        assert "sparse.py" in _git(
            repo, "ls-tree", "-r", "--name-only", result["tree"]
        ).splitlines()
        # And the user's own `add -A` agrees: nothing to stage, so a verbatim
        # commit of this state carries exactly the tree that was captured.
        _git(repo, "add", "-A")
        assert _git(repo, "status", "--porcelain") == ""
        assert result["tree"] == _git(repo, "rev-parse", "HEAD^{tree}")
        assert result["clean"] is True

    def test_capture_on_unborn_head(self, tmp_path):
        repo = tmp_path / "fresh"
        repo.mkdir()
        _git(repo, "init", "-q")
        (repo / "first.py").write_text("a = 1\n")
        result = evidence.capture_tree(repo)
        assert result["status"] == "ok"
        assert result["head_commit"] is None
        assert result["clean"] is False
        names = _git(repo, "ls-tree", "-r", "--name-only", result["tree"])
        assert names.splitlines() == ["first.py"]


class TestGitTimeoutBudget:
    """The per-call git budget, and what a capture that runs out of it leaves
    behind. A working tree reached over a network or bind mount pays mount
    latency per file, so the budget has to be raisable from outside — and the
    message that reports the overrun has to say so."""

    def test_default_applies_when_unset(self, monkeypatch):
        monkeypatch.delenv(evidence._GIT_TIMEOUT_ENV, raising=False)
        assert evidence._git_timeout() == (evidence._GIT_TIMEOUT_DEFAULT, None)

    def test_blank_is_treated_as_unset(self, monkeypatch):
        monkeypatch.setenv(evidence._GIT_TIMEOUT_ENV, "   ")
        assert evidence._git_timeout() == (evidence._GIT_TIMEOUT_DEFAULT, None)

    def test_override_reaches_the_subprocess_call(self, tmp_path, monkeypatch):
        repo = _make_repo(tmp_path)
        monkeypatch.setenv(evidence._GIT_TIMEOUT_ENV, "120")
        seen = []
        real_run = evidence.subprocess.run

        def spy(*args, **kwargs):
            seen.append(kwargs.get("timeout"))
            return real_run(*args, **kwargs)

        monkeypatch.setattr(evidence.subprocess, "run", spy)
        assert evidence.capture_tree(repo)["status"] == "ok"
        assert seen and set(seen) == {120}

    @pytest.mark.parametrize("bad", ["1O", "ten", "5.5", "0", "-3"])
    def test_malformed_override_is_refused_not_silently_defaulted(
        self, tmp_path, monkeypatch, bad
    ):
        """Someone who set the variable wanted a different budget. Quietly
        restoring the default hands them back the timeout they were trying to
        escape, with nothing on screen to say why."""
        repo = _make_repo(tmp_path)
        monkeypatch.setenv(evidence._GIT_TIMEOUT_ENV, bad)
        result = evidence.capture_tree(repo)
        assert result["status"] == "error"
        assert evidence._GIT_TIMEOUT_ENV in result["reason"]

    def test_a_refused_override_says_so_on_stderr(self, tmp_path, monkeypatch, capsys):
        """A refusal has to be visible at the SOURCE. Every `run_git` call fails
        while the variable is malformed, and not every caller reports the reason
        — `coverage` and `record_lint` both read a nonzero rc as an honest 'no
        answer' and go quiet, which is right for a real git failure and wrong
        for a typo in the operator's own environment."""
        monkeypatch.setattr(evidence, "_ATTRIBUTED_BAD_TIMEOUTS", set())
        monkeypatch.setenv(evidence._GIT_TIMEOUT_ENV, "1O")
        evidence.capture_tree(_make_repo(tmp_path))
        err = capsys.readouterr().err
        # Deduped AT THE SOURCE: the variable is read on every git call and
        # capture_tree makes several, so the refusal announces itself once.
        announcement = f"evidence: {evidence._GIT_TIMEOUT_ENV}"
        assert err.count(announcement) == 1
        # Downstream attribution may quote the refusal as the CAUSE of what it
        # is reporting — that is the knock-on being traceable, not a repeat.
        assert "seeding the capture with" in err

    def test_timeout_names_the_remedy_and_leaves_no_lock(self, tmp_path, monkeypatch):
        """`GIT_INDEX_FILE` moves git's index lock alongside the temp index,
        so a capture killed mid-`add` litters the temp dir — never
        `.git/index.lock`. Both the litter and the silence about the remedy
        are cleaned up here."""
        repo = _make_repo(tmp_path)
        real_run = evidence.subprocess.run

        def die_on_add(cmd, **kwargs):
            if "add" in cmd:
                # what a killed `git add` leaves: the lock it had taken out
                Path(kwargs["env"]["GIT_INDEX_FILE"] + ".lock").write_text("")
                raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 0))
            return real_run(cmd, **kwargs)

        monkeypatch.setattr(evidence.subprocess, "run", die_on_add)
        before = set(Path(tempfile.gettempdir()).glob("prawduct-idx-*"))
        result = evidence.capture_tree(repo)
        assert result["status"] == "error"
        assert evidence._GIT_TIMEOUT_ENV in result["reason"]
        assert set(Path(tempfile.gettempdir()).glob("prawduct-idx-*")) == before
        assert list(Path(_git(repo, "rev-parse", "--absolute-git-dir")).glob("*.lock")) == []


# ---------------------------------------------------------------------------
# CLI — the allowlistable surface
# ---------------------------------------------------------------------------


def _run_hook(repo: Path, *args: str) -> subprocess.CompletedProcess:
    home = repo.parent / "_home"
    home.mkdir(exist_ok=True)
    return subprocess.run(
        [sys.executable, str(HOOK), *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=25,
        env={
            "HOME": str(home),
            "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
            "CLAUDE_PROJECT_DIR": str(repo),
        },
    )


class TestEvidenceCli:
    def test_status_on_empty_store(self, tmp_path):
        repo = _make_repo(tmp_path)
        proc = _run_hook(repo, "evidence", "status")
        assert proc.returncode == 0
        assert "empty store" in proc.stdout

    def test_status_counts_and_list(self, tmp_path):
        repo = _make_repo(tmp_path)
        evidence.append_fact(repo, "review", "r-1", {"head_tree": "a" * 40})
        evidence.append_fact(repo, "resolution", "s-1", {"at_tree": "b" * 40})
        proc = _run_hook(repo, "evidence", "status")
        assert proc.returncode == 0
        assert "resolution=1" in proc.stdout and "review=1" in proc.stdout
        proc = _run_hook(repo, "evidence", "list", "--kind", "review")
        assert proc.returncode == 0
        assert "r-1" in proc.stdout and "s-1" not in proc.stdout

    def test_list_tolerates_opaque_body_values(self, tmp_path):
        repo = _make_repo(tmp_path)
        # Valid envelope, body fields this lister doesn't understand — a
        # non-string head_tree must not crash the CLI (D9 never-crash).
        evidence.append_fact(repo, "review", "r-odd", {"head_tree": 12345})
        proc = _run_hook(repo, "evidence", "list")
        assert proc.returncode == 0
        assert "r-odd" in proc.stdout

    def test_status_schema_ahead_exits_2_with_remedy(self, tmp_path):
        repo = _make_repo(tmp_path)
        evidence.append_fact(repo, "review", "r-1", {})
        with open(_store_file(repo), "a") as fh:
            fh.write(
                json.dumps(
                    {
                        "schema": evidence.SCHEMA_VERSION + 1,
                        "kind": "review",
                        "id": "r-f",
                        "body": {},
                    }
                )
                + "\n"
            )
        proc = _run_hook(repo, "evidence", "status")
        assert proc.returncode == 2
        assert "SCHEMA-AHEAD" in proc.stdout

    def test_status_outside_git_repo_fails_loud(self, tmp_path):
        plain = tmp_path / "plain"
        plain.mkdir()
        home = tmp_path / "_home"
        home.mkdir(exist_ok=True)
        proc = subprocess.run(
            [sys.executable, str(HOOK), "evidence", "status"],
            cwd=str(plain),
            capture_output=True,
            text=True,
            timeout=25,
            env={
                "HOME": str(home),
                "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
                "CLAUDE_PROJECT_DIR": str(plain),
            },
        )
        assert proc.returncode == 1
        assert "no git repository" in proc.stderr

    def test_unknown_subcommand_usage(self, tmp_path):
        repo = _make_repo(tmp_path)
        proc = _run_hook(repo, "evidence", "wipe")
        assert proc.returncode == 1
        assert "Usage" in proc.stderr


# ---------------------------------------------------------------------------
# tree_entries — the per-tree half of the free-edge question
# ---------------------------------------------------------------------------


class TestTreeEntries:
    """Two trees are free-connected iff they agree on every JUDGEABLE entry,
    which lets a caller key each tree once instead of diffing every pair.
    That substitution is only sound if this function's notion of "the same
    entry" is no looser than ``git diff``'s — a looser one grants free edges
    git itself refuses, which in a review gate is a fail-OPEN.
    """

    def test_entries_carry_mode_object_id_and_path(self, tmp_path):
        repo = _make_repo(tmp_path)
        tree = _git(repo, "rev-parse", "HEAD^{tree}")
        entries = evidence.tree_entries(repo, tree)
        assert entries is not None
        assert [p for _m, _o, p in entries] == ["code.py"]
        mode, object_id, _path = entries[0]
        assert mode == "100644"
        assert object_id and all(c in "0123456789abcdef" for c in object_id)

    def test_mode_only_change_is_not_the_same_tree(self, tmp_path):
        """``chmod +x`` changes no bytes, but git reports the path as
        changed. Keying by ``(object_id, path)`` alone would call these trees
        equal and hand out a free edge that git's own diff refuses."""
        repo = _make_repo(tmp_path)
        before = _git(repo, "rev-parse", "HEAD^{tree}")
        _git(repo, "update-index", "--chmod=+x", "code.py")
        _git(repo, "commit", "-q", "-m", "chmod")
        after = _git(repo, "rev-parse", "HEAD^{tree}")

        assert before != after
        assert evidence.tree_diff(repo, before, after) == ["code.py"]
        assert evidence.tree_entries(repo, before) != evidence.tree_entries(repo, after)

    def test_unreadable_tree_is_none_never_empty(self, tmp_path):
        # Empty would read as "a tree with no files", which is a real tree.
        repo = _make_repo(tmp_path)
        assert evidence.tree_entries(repo, "0" * 40) is None
        assert evidence.tree_entries(repo, "") is None
        assert evidence.tree_entries(repo, "not-a-sha") is None

    def test_malformed_tree_id_never_reaches_git_argv(self, tmp_path, monkeypatch):
        """The store is a plain file on disk shared by every worktree, so a
        corrupted or hand-edited fact can carry any string where a tree id
        belongs. argv is list-form with no shell, so the exposure is a token
        git reads as an OPTION — which is why the gate is a shape check
        *before* the call, not a nonzero exit code after it."""
        calls = []
        real = evidence.run_git
        monkeypatch.setattr(
            evidence, "run_git", lambda d, *a, **k: (calls.append(a), real(d, *a, **k))[1]
        )
        repo = _make_repo(tmp_path)
        good = _git(repo, "rev-parse", "HEAD^{tree}")

        for bad in ("--upload-pack=evil", "--output=/tmp/pwned", "HEAD", "not-a-sha",
                    "", good[:39], good + "\n", good.upper()):
            assert evidence.tree_diff(repo, good, bad) is None, bad
            assert evidence.tree_diff(repo, bad, good) is None, bad
            assert evidence.tree_entries(repo, bad) is None, bad
        assert calls == [], f"a malformed tree id reached git: {calls}"

    def test_shape_rejection_is_attributed_not_silent(self, tmp_path, capsys):
        """Skip WITH attribution is this module's posture for malformed input.
        A store holding an unreadable tree id is corrupted; answering a bare
        ``None`` would present that as an ordinary "cannot compute"."""
        evidence._ATTRIBUTED_BAD_TREES.clear()
        repo = _make_repo(tmp_path)
        good = _git(repo, "rev-parse", "HEAD^{tree}")
        assert evidence.tree_diff(repo, good, "--upload-pack=evil") is None
        err = capsys.readouterr().err
        assert "not a git object id" in err
        assert "hand-edited" in err

        # Deduped: one corrupt fact is probed once per composition path, and
        # the tenth copy of the same line teaches nothing.
        assert evidence.tree_entries(repo, "--upload-pack=evil") is None
        assert capsys.readouterr().err == ""

    def test_both_real_object_id_widths_are_accepted(self, tmp_path):
        """40-hex (SHA-1) and 64-hex (SHA-256) are the two real widths. The
        repo is SHA-1 today; the 64-hex leg is what keeps that from being
        baked into the gate. Both are *shape*-valid, so they get as far as
        git — which then honestly reports the SHA-256 tree as missing."""
        repo = _make_repo(tmp_path)
        assert evidence.tree_entries(repo, _git(repo, "rev-parse", "HEAD^{tree}")) is not None
        assert evidence.tree_entries(repo, "a" * 64) is None  # shape ok, object absent

    def test_paths_needing_quoting_survive(self, tmp_path):
        """``-z``, because git quotes paths with spaces or non-ASCII bytes in
        its default output and a quoted path classifies differently from the
        real one — the trap ``gitstate.parse_porcelain_line`` absorbs."""
        repo = _make_repo(tmp_path)
        (repo / "a file.md").write_text("hi\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "spaced")
        tree = _git(repo, "rev-parse", "HEAD^{tree}")
        entries = evidence.tree_entries(repo, tree)
        assert "a file.md" in [p for _m, _o, p in entries]

    def test_key_and_diff_agree_on_what_needs_review(self, tmp_path):
        """The equivalence the optimisation rests on, against real git: a
        doc-only interval keys equal (free edge), a code change does not."""
        from lib import gates

        repo = _make_repo(tmp_path)
        base = _git(repo, "rev-parse", "HEAD^{tree}")

        (repo / "notes.md").write_text("doc\n")  # non-judgeable
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "doc")
        doc_only = _git(repo, "rev-parse", "HEAD^{tree}")

        (repo / "code.py").write_text("x = 2\n")  # judgeable
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "code")
        code_changed = _git(repo, "rev-parse", "HEAD^{tree}")

        key = gates._tree_key_fn(repo)
        assert key(base) == key(doc_only), "doc-only interval must be a free edge"
        assert key(doc_only) != key(code_changed), "a code change is never free"
        assert key("0" * 40) is None, "an unreadable tree joins no class"


class TestStoreGrowthAdvisory:
    """The store never shrinks and composition is linear in distinct TREES,
    so that count is the one worth surfacing. Advisory, never blocking —
    state-file growth prompts compaction, it does not stop work."""

    def test_status_reports_tree_count(self, tmp_path):
        repo = _make_repo(tmp_path)
        evidence.append_fact(
            repo, "review", "rev-growth-1",
            {"base_tree": "t0", "head_tree": "t1", "files_changed": [],
             "files_reviewed": [], "mode": "chunk", "findings": []},
        )
        proc = _run_hook(repo, "evidence", "status")
        assert proc.returncode == 0
        assert "trees referenced: 2" in proc.stdout
        assert "NOTE:" not in proc.stdout  # far below the advisory threshold

    def test_distinct_trees_counts_both_edge_ends_once(self):
        facts = [
            {"kind": "review", "body": {"base_tree": "a", "head_tree": "b"}},
            {"kind": "review", "body": {"base_tree": "b", "head_tree": "c"}},
            {"kind": "resolution", "body": {"finding": {}}},
            {"kind": "review", "body": {"base_tree": "", "head_tree": None}},
        ]
        assert evidence.distinct_trees(facts) == {"a", "b", "c"}

    def test_only_review_facts_contribute_trees(self):
        """Nodes are what coverage composition walks, and only review facts
        become edges — so only their trees are nodes.

        The sibling assertion in `test_dispositions.py` states this intent for
        dispositions, but it holds there only because a disposition body has no
        `base_tree` key: it would pass unchanged against a kind-blind reader.
        This states it as the rule, with a fact that DOES carry the edge shape.
        A purely observational record inflating the tree count reads in
        `evidence status` as coverage that does not exist.
        """
        observational = [
            {"kind": "guard-refusal",
             "body": {"guard": "g", "base_tree": "x", "head_tree": "y"}},
            {"kind": "test-run", "body": {"base_tree": "p", "head_tree": "q"}},
        ]
        assert evidence.distinct_trees(observational) == set()
        assert evidence.distinct_trees(
            observational + [{"kind": "review",
                              "body": {"base_tree": "a", "head_tree": "b"}}]
        ) == {"a", "b"}

    def test_advisory_constant_matches_the_documented_trigger(self):
        # The compaction deferral's trigger is ~10,000 trees; the constant and
        # the plan must not drift apart silently.
        assert evidence.TREE_COUNT_ADVISORY == 10_000

    def test_advisory_fires_at_the_threshold_and_not_below(
        self, tmp_path, capsys, monkeypatch
    ):
        # The negative case above ("NOTE:" absent far below the trigger) cannot
        # catch an inverted comparison — only firing can. Patch the trigger down
        # rather than writing 10,000 trees; the boundary is the claim worth
        # pinning, since the advisory fires AT the count (>=), not past it.
        repo = _make_repo(tmp_path)
        evidence.append_fact(
            repo, "review", "rev-growth-2",
            {"base_tree": "t0", "head_tree": "t1", "files_changed": [],
             "files_reviewed": [], "mode": "chunk", "findings": []},
        )

        monkeypatch.setattr(evidence, "TREE_COUNT_ADVISORY", 2)
        assert evidence._cmd_status(repo) == 0, "advisory never blocks"
        assert "NOTE: 2 distinct trees" in capsys.readouterr().out

        monkeypatch.setattr(evidence, "TREE_COUNT_ADVISORY", 3)
        assert evidence._cmd_status(repo) == 0
        assert "NOTE:" not in capsys.readouterr().out


class TestDedupedGuardRefusal:
    """A guard on a POLLED path records the EVENT, not the observation.

    ``critic-begin`` fires once per dispatch, so its default id (timestamp +
    uuid) counts firings correctly. A gate is re-asked several times a session
    about an unchanged repo, and the composed-verdict memo keys on a content
    hash of this whole store — so a record per poll would both miscount the
    event and evict every memoized verdict on every poll. ``dedupe_key`` is the
    answer: a deterministic id, and a second observation that writes nothing.
    """

    def test_the_id_is_a_function_of_guard_and_key_only(self, tmp_path):
        repo = _make_repo(tmp_path)
        first = evidence.append_guard_refusal(
            repo, "polled-guard", {"n": 1}, dedupe_key="span-A"
        )
        assert first["status"] == "appended", first
        other = _make_repo(tmp_path, name="repo2")
        again = evidence.append_guard_refusal(
            other, "polled-guard", {"n": 2}, dedupe_key="span-A"
        )
        # Same guard + same key ⇒ same id in a different clone at a different
        # moment: nothing about *when* or *where* is in the digest, which is
        # what makes the dedupe hold across the polls of one session.
        assert again["id"] == first["id"]
        assert first["id"].startswith("guard-polled-guard-")

    def test_a_different_key_is_a_different_event(self, tmp_path):
        repo = _make_repo(tmp_path)
        a = evidence.append_guard_refusal(repo, "g", {}, dedupe_key="span-A")
        b = evidence.append_guard_refusal(repo, "g", {}, dedupe_key="span-B")
        assert a["id"] != b["id"]
        assert b["status"] == "appended"

    def test_a_second_observation_leaves_the_store_byte_identical(self, tmp_path):
        repo = _make_repo(tmp_path)
        assert (
            evidence.append_guard_refusal(repo, "g", {"n": 1}, dedupe_key="k")["status"]
            == "appended"
        )
        before = _store_file(repo).read_bytes()
        second = evidence.append_guard_refusal(repo, "g", {"n": 1}, dedupe_key="k")
        assert second["status"] == "duplicate"
        assert _store_file(repo).read_bytes() == before

    def test_known_facts_answers_the_probe_without_a_second_read(
        self, tmp_path, monkeypatch
    ):
        # The whole point of the parameter: a gate has already read the store,
        # and on a large one that read is a real slice of its budget. Passing
        # the read it is acting on must make the probe free — and keep it right.
        repo = _make_repo(tmp_path)
        first = evidence.append_guard_refusal(repo, "g", {}, dedupe_key="k")
        assert first["status"] == "appended"
        facts = evidence.read_facts(repo)["facts"]

        def _forbidden(*_args, **_kwargs):
            raise AssertionError("known_facts must answer the probe by itself")

        monkeypatch.setattr(evidence, "has_fact", _forbidden)
        assert (
            evidence.append_guard_refusal(
                repo, "g", {}, dedupe_key="k", known_facts=facts
            )["status"]
            == "duplicate"
        )

    def test_a_stale_known_facts_list_re_appends_rather_than_dropping(self, tmp_path):
        # The failure direction the parameter accepts: a caller whose read
        # predates the record writes a redundant line. `read_facts` dedupes
        # (kind, id) on the way out, so the store stays one event — never zero.
        repo = _make_repo(tmp_path)
        stale = evidence.read_facts(repo)["facts"]
        evidence.append_guard_refusal(repo, "g", {}, dedupe_key="k")
        again = evidence.append_guard_refusal(
            repo, "g", {}, dedupe_key="k", known_facts=stale
        )
        assert again["status"] == "appended"
        read = evidence.read_facts(repo)
        assert read["duplicates"] == 1
        assert sum(1 for f in read["facts"] if f["kind"] == "guard-refusal") == 1

    def test_a_review_fact_with_the_same_id_never_answers_the_probe(self, tmp_path):
        # The probe is (kind, id), not id: kinds are separate namespaces, and a
        # guard record silently skipped because some other kind squats its id
        # would lose the firing this whole mechanism exists to count.
        repo = _make_repo(tmp_path)
        minted = evidence.append_guard_refusal(repo, "g", {}, dedupe_key="k")
        _store_file(repo).write_text("")
        evidence.append_fact(
            repo, "review", minted["id"],
            {"base_tree": "a", "head_tree": "b", "files_changed": [],
             "files_reviewed": [], "findings": []},
        )
        assert (
            evidence.append_guard_refusal(repo, "g", {}, dedupe_key="k")["status"]
            == "appended"
        )

    def test_an_empty_key_is_rejected_rather_than_silently_undeduped(self, tmp_path):
        # Falling back to the random-id form here would be the worst outcome:
        # the caller asked for one-record-per-event and would get one per poll,
        # with nothing saying so.
        repo = _make_repo(tmp_path)
        result = evidence.append_guard_refusal(repo, "g", {}, dedupe_key="  ")
        assert result["status"] == "error"
        assert "dedupe key" in result["reason"]

    def test_the_undeduped_form_is_unchanged(self, tmp_path):
        repo = _make_repo(tmp_path)
        a = evidence.append_guard_refusal(repo, "g", {})
        b = evidence.append_guard_refusal(repo, "g", {})
        assert a["status"] == b["status"] == "appended"
        assert a["id"] != b["id"]
