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
