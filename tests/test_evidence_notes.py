"""``lib/evidence_notes.py`` — review facts travel between clones as git notes (#1052).

The store lives inside ``.git`` and is never pushed, so a second clone sees no
coverage at all. The transport is ``refs/notes/prawduct``: each transported fact
is written, as the very line the store holds, onto a note on its **anchor**
commit (a review's ``head_commit`` or, for a dirty-tree review, its
``dispatch_commit``; a resolution's verifying review's anchor; HEAD for a
``chunk-imported`` fact), and ``evidence ingest`` appends the lines this clone
does not hold yet.

Fixtures are real git repos — the anchor rules, the ``merge_base..HEAD`` bound
and the blank line ``git notes append`` inserts between records are git's
behaviour, not a model of it — and the consolidation cases run the real hook.
"""

from __future__ import annotations

import functools
import importlib.machinery
import importlib.util
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import coverage, coverage_algebra, evidence, evidence_notes  # noqa: E402

NOTES_REF = "refs/notes/prawduct"
FINAL_MODE = "final (full review, ready for push)"
VERIFY_MODE = "verify-resolutions (delta review, prior findings only)"
PARTIALS_REL = ".prawduct/.critic-partials"
ROLES = ("correctness", "design", "sustainability")


# ---------------------------------------------------------------------------
# Fixtures — real git, sterile env
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _sterile_git(monkeypatch, tmp_path):
    """In-process git calls (the module under test runs git through
    ``evidence.run_git``, which inherits this env) must not read the operator's
    global config — a signing or hooks setting there changes what a notes
    commit does."""
    home = tmp_path / "_home"
    home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", "/dev/null")
    monkeypatch.setenv("GIT_TERMINAL_PROMPT", "0")
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    monkeypatch.delenv("PRAWDUCT_ALLOW_EPHEMERAL_WRITES", raising=False)


def _env() -> dict[str, str]:
    return {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}


def _git(repo: Path, *args: str, input: "str | None" = None) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True,
        env=_env(), check=True, timeout=20, input=input,
    ).stdout.strip()


def _configure(repo: Path) -> None:
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "commit.gpgsign", "false")


def _commit(repo: Path, rel: str, text: str, subject: str) -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    _git(repo, "add", rel)
    _git(repo, "commit", "-qm", subject)
    return _git(repo, "rev-parse", "HEAD")


def _tree(repo: Path, commit: str) -> str:
    return _git(repo, "rev-parse", f"{commit}^{{tree}}")


def _seed(repo: Path) -> str:
    """`main` with a seed commit; `.prawduct/` ignored so review state written
    under it never changes a captured tree."""
    _configure(repo)
    return _commit(repo, ".gitignore", ".prawduct/\n", "seed")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _seed(repo)
    _git(repo, "checkout", "-q", "-b", "feature/unit")
    return repo.resolve()


@pytest.fixture
def origin_and_clone(tmp_path: Path) -> "tuple[Path, Path]":
    """A bare origin and clone A of it, `main` pushed, on `feature/unit`."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    a = tmp_path / "a"
    _git(tmp_path, "init", "-q", "-b", "main", str(a))
    _seed(a)
    _git(a, "remote", "add", "origin", str(origin))
    _git(a, "push", "-q", "-u", "origin", "main")
    _git(a, "remote", "set-head", "origin", "main")
    _git(a, "checkout", "-q", "-b", "feature/unit")
    return origin, a.resolve()


def _run_hook(repo: Path, *args: str, env_extra: "dict | None" = None) -> subprocess.CompletedProcess:
    env = _env()
    env["CLAUDE_PROJECT_DIR"] = str(repo)
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, str(HOOK), *args],
        cwd=str(repo), capture_output=True, text=True, env=env, timeout=60,
    )


def _store_lines(repo: Path) -> list[str]:
    path = evidence.store_path(repo)
    if path is None or not path.is_file():
        return []
    return [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _line_of(repo: Path, kind: str, fact_id: str) -> str:
    for line in _store_lines(repo):
        record = json.loads(line)
        if record.get("kind") == kind and record.get("id") == fact_id:
            return line
    raise AssertionError(f"no {kind} {fact_id} in the store")


def _note(repo: Path, commit: str) -> "str | None":
    proc = subprocess.run(
        ["git", "notes", "--ref", NOTES_REF, "show", commit],
        cwd=str(repo), capture_output=True, text=True, env=_env(), timeout=20,
    )
    return proc.stdout if proc.returncode == 0 else None


def _note_records(repo: Path, commit: str) -> list[str]:
    text = _note(repo, commit) or ""
    return [ln for ln in text.splitlines() if ln.strip()]


def _annotated(repo: Path) -> set[str]:
    out = subprocess.run(
        ["git", "notes", "--ref", NOTES_REF, "list"],
        cwd=str(repo), capture_output=True, text=True, env=_env(), timeout=20,
    ).stdout
    return {line.split()[1] for line in out.splitlines() if line.strip()}


def _block_notes_ref(repo: Path) -> None:
    """Make `refs/notes/prawduct` uncreatable: a ref UNDER that name exists, so
    git refuses the notes ref itself (a directory/file conflict). git does not
    check that a note's target object exists, so a missing anchor is no way to
    make a notes write fail."""
    _git(repo, "update-ref", f"{NOTES_REF}/blocker", "HEAD")


def _wipe_store(repo: Path) -> None:
    path = evidence.store_path(repo)
    if path is not None and path.exists():
        path.unlink()


def _keys(repo: Path) -> set[tuple[str, str]]:
    return {(f["kind"], f["id"]) for f in evidence.read_facts(repo)["facts"]}


def _envelope(kind: str, fact_id: str, body: dict, schema: int = 1) -> dict:
    return {"schema": schema, "kind": kind, "id": fact_id, "ts": "2026-10-25T10:00:00Z",
            "actor": {"session": None, "worktree": "/elsewhere", "plugin": "9.9.9"},
            "body": body}


def _verdict(repo: Path, base_tree: str, target_tree: str) -> dict:
    """The coverage verdict over the store as it stands, with the real tree
    diff the gates inject (``gates._merge_base_verdict``)."""
    facts = evidence.read_facts(repo)["facts"]
    return coverage_algebra.coverage_verdict(
        facts, base_tree, target_tree, lambda a, b: evidence.tree_diff(repo, a, b)
    )


# ---------------------------------------------------------------------------
# Consolidation — the real hook, hand-written manifest and partials
# ---------------------------------------------------------------------------


def _manifest(review_id: str, *, commit_reviewed: str, base_commit: str, base_tree: str,
              head_tree: str, head_commit: "str | None", mode: str = FINAL_MODE,
              roster=ROLES) -> dict:
    return {
        "id": review_id,
        "mode": mode,
        "mode_chosen_by": "rule-3 final",
        "roster": list(roster),
        "roster_chosen_by": "test",
        "commit_reviewed": commit_reviewed,
        "base_commit": base_commit,
        "base_tree": base_tree,
        "head_tree": head_tree,
        "head_commit": head_commit,
        "files_changed": ["src/app.py"],
        "files_reviewed": ["src/app.py"],
        "tier": None,
        "scope": "unit",
        "chunk": "01",
        "base_reviewed": None,
        "rendezvous": {
            role: {
                "partial": f"{PARTIALS_REL}/{role}.{review_id}.json",
                "started": f"{PARTIALS_REL}/{role}.{review_id}.started",
            }
            for role in roster
        },
    }


def _consolidate(repo: Path, manifest: dict, *, findings: "dict | None" = None,
                 resolutions: "list | None" = None) -> subprocess.CompletedProcess:
    partials = repo / PARTIALS_REL
    partials.mkdir(parents=True, exist_ok=True)
    (repo / ".prawduct" / ".critic-active").write_text(
        json.dumps({"started_at": "2026-07-09T00:00:00Z"})
    )
    (partials / "manifest.json").write_text(json.dumps(manifest))
    for role in manifest["roster"]:
        partial = {
            "role": role, "goals": "1-3", "dispatch_id": manifest["id"],
            "commit_reviewed": manifest["commit_reviewed"], "model": "opus",
            "duration_seconds": 90, "findings": (findings or {}).get(role, []),
            "summary": f"{role} review complete.",
        }
        if resolutions is not None:
            partial["resolutions"] = resolutions
        (partials / f"{role}.{manifest['id']}.json").write_text(json.dumps(partial))
    env = _env()
    env["CLAUDE_PLUGIN_ROOT"] = str(ROOT)
    return subprocess.run(
        [sys.executable, str(HOOK), "critic-consolidate"],
        cwd=str(repo), capture_output=True, text=True, env=env, timeout=60,
    )


BLOCKER = {"correctness": [{"name": "Broken invariant", "goal": "Nothing Is Broken",
                            "severity": "blocking", "recommendation": "Fix it",
                            "files": ["src/app.py"]}]}


def _reviewed_branch(repo: Path) -> dict:
    """Two committed rounds on the branch, consolidated for real:
    R1 reviews seed→C1 and records a blocker; C2 fixes it; R2 is a
    verify-resolutions pass over C1→C2 that resolves the blocker. The verdict
    seed→C2 is `covered` only if the resolution is held too."""
    seed = _git(repo, "rev-parse", "main")
    c1 = _commit(repo, "src/app.py", "x = 1\n", "feat: work (Chunk 01)")
    r1 = _consolidate(repo, _manifest(
        "rev-r1", commit_reviewed=c1, base_commit=seed, base_tree=_tree(repo, seed),
        head_tree=_tree(repo, c1), head_commit=c1,
    ), findings=BLOCKER)
    assert r1.returncode == 0, r1.stderr
    c2 = _commit(repo, "src/app.py", "x = 2\n", "fix: the invariant")
    r2 = _consolidate(repo, _manifest(
        "rev-r2", commit_reviewed=c2, base_commit=c1, base_tree=_tree(repo, c1),
        head_tree=_tree(repo, c2), head_commit=c2, mode=VERIFY_MODE, roster=("reviewer",),
    ), resolutions=[{"review_id": "rev-r1", "fid": "R-1", "disposition": "fixed"}])
    assert r2.returncode == 0, r2.stderr
    return {"seed": seed, "c1": c1, "c2": c2,
            "base_tree": _tree(repo, seed), "c2_tree": _tree(repo, c2)}


# ---------------------------------------------------------------------------
# attach — where a note lands and what it holds
# ---------------------------------------------------------------------------


class TestNotesWrittenAtConsolidation:
    def test_a_consolidated_review_leaves_one_note_on_its_anchor_holding_the_identical_line(self, repo):
        seed = _git(repo, "rev-parse", "main")
        c1 = _commit(repo, "src/app.py", "x = 1\n", "work")
        result = _consolidate(repo, _manifest(
            "rev-a", commit_reviewed=c1, base_commit=seed, base_tree=_tree(repo, seed),
            head_tree=_tree(repo, c1), head_commit=c1,
        ))
        assert result.returncode == 0, result.stderr
        assert _annotated(repo) == {c1}
        assert _note_records(repo, c1) == [_line_of(repo, "review", "rev-a")]
        # Byte-for-byte, newline included — the note IS a store line.
        assert _note(repo, c1) == _line_of(repo, "review", "rev-a") + "\n"

    def test_a_resolution_note_lands_on_its_verifying_reviews_anchor(self, repo):
        refs = _reviewed_branch(repo)
        resolution = _line_of(repo, "resolution", "rev-r2:rev-r1:R-1")
        # The verifying review (R2) anchors on C2; the finding it resolves was
        # recorded by R1 on C1. The resolution rides with the review that
        # verified it, never with the one that raised the finding.
        assert _note_records(repo, refs["c2"]) == [_line_of(repo, "review", "rev-r2"), resolution]
        assert _note_records(repo, refs["c1"]) == [_line_of(repo, "review", "rev-r1")]

    def test_a_dirty_tree_review_anchors_on_its_dispatch_commit(self, repo):
        seed = _git(repo, "rev-parse", "main")
        c1 = _commit(repo, "src/app.py", "x = 1\n", "work")
        # A chunk review of uncommitted work records `head_commit: null`.
        result = _consolidate(repo, _manifest(
            "rev-dirty", commit_reviewed=c1, base_commit=seed, base_tree=_tree(repo, seed),
            head_tree="f" * 40, head_commit=None,
        ))
        assert result.returncode == 0, result.stderr
        fact = evidence.read_facts(repo)["facts"][0]
        assert fact["body"]["head_commit"] is None and fact["body"]["dispatch_commit"] == c1
        assert _note_records(repo, c1) == [_line_of(repo, "review", "rev-dirty")]


class TestAttach:
    def test_a_session_start_fact_attaches_nothing(self, repo):
        head = _git(repo, "rev-parse", "HEAD")
        appended = evidence.append_session_start(repo)
        assert appended["status"] == "appended"
        outcome = evidence_notes.attach(repo, appended["envelope"], head)
        assert outcome["status"] == "skipped"
        assert _annotated(repo) == set()
        # Control: the same anchor takes a transported kind.
        review = evidence.append_fact(repo, "review", "r-1", {"head_commit": head})
        assert evidence_notes.attach(repo, review["envelope"], head)["status"] == "attached"
        assert _annotated(repo) == {head}

    def test_every_kind_outside_the_transported_set_is_skipped(self, repo):
        head = _git(repo, "rev-parse", "HEAD")
        local_kinds = evidence.KNOWN_KINDS - evidence.TRANSPORTED_KINDS
        assert local_kinds, "the store-only kinds must be non-empty or this test checks nothing"
        for kind in sorted(local_kinds):
            outcome = evidence_notes.attach(repo, _envelope(kind, f"x-{kind}", {}), head)
            assert outcome["status"] == "skipped", kind
        assert _annotated(repo) == set()

    @pytest.mark.parametrize("anchor", [None, "", "abc123", "HEAD", "--upload-pack=x"])
    def test_an_anchor_that_is_not_an_object_id_is_skipped(self, repo, anchor):
        outcome = evidence_notes.attach(repo, _envelope("review", "r-1", {}), anchor)
        assert outcome["status"] == "skipped"
        assert _annotated(repo) == set()

    def test_a_git_failure_is_an_error_not_a_raise(self, repo):
        head = _git(repo, "rev-parse", "HEAD")
        _block_notes_ref(repo)
        outcome = evidence_notes.attach(repo, _envelope("review", "r-1", {}), head)
        assert outcome["status"] == "error"
        assert outcome["reason"]


# ---------------------------------------------------------------------------
# ingest
# ---------------------------------------------------------------------------


class TestIngestRoundTrip:
    def test_a_wiped_store_re_ingested_holds_the_same_facts_and_verdict(self, repo):
        refs = _reviewed_branch(repo)
        before_keys = _keys(repo)
        before_lines = sorted(_store_lines(repo))
        before = _verdict(repo, refs["base_tree"], refs["c2_tree"])
        assert before["status"] == "covered", before
        assert {k for k, _ in before_keys} == {"review", "resolution"}

        _wipe_store(repo)
        # Control: with the store gone the interval is not covered, so the
        # equality below is evidence about ingest, not about a fixture.
        assert _verdict(repo, refs["base_tree"], refs["c2_tree"])["status"] == "uncovered"

        result = evidence_notes.ingest(repo)
        assert result["status"] == "ok", result
        assert result["appended"] == len(before_keys) == 3
        assert result["commits"] == 2
        assert _keys(repo) == before_keys
        assert sorted(_store_lines(repo)) == before_lines, "ingest must append the bytes the writer appended"
        assert _verdict(repo, refs["base_tree"], refs["c2_tree"]) == before

    def test_ingest_twice_appends_nothing_the_second_time(self, repo):
        _reviewed_branch(repo)
        _wipe_store(repo)
        first = evidence_notes.ingest(repo)
        lines = _store_lines(repo)
        second = evidence_notes.ingest(repo)
        assert first["appended"] == 3
        assert second == {**second, "status": "ok", "appended": 0, "seen": 3}
        assert _store_lines(repo) == lines

    def test_a_record_already_in_the_store_is_not_appended_again(self, repo):
        """Ingest after consolidation in the SAME clone: every note line is a
        fact this store already holds."""
        _reviewed_branch(repo)
        lines = _store_lines(repo)
        result = evidence_notes.ingest(repo)
        assert (result["appended"], result["seen"]) == (0, 3)
        assert _store_lines(repo) == lines

    def test_known_is_used_instead_of_a_second_store_read(self, repo, monkeypatch):
        head = _git(repo, "rev-parse", "HEAD")
        evidence_notes.attach(repo, _envelope("review", "r-1", {}), head)
        known = evidence.read_facts(repo)

        def no_read(*_a, **_kw):
            raise AssertionError("ingest re-read the store although `known` was given")

        monkeypatch.setattr(evidence, "read_facts", no_read)
        assert evidence_notes.ingest(repo, known=known)["appended"] == 1


class TestIngestBound:
    def test_a_note_outside_merge_base_head_is_ignored_bounded_and_read_with_all(self, repo):
        head = _commit(repo, "src/app.py", "x = 1\n", "work")
        _git(repo, "checkout", "-q", "main")
        elsewhere = _commit(repo, "other.txt", "o\n", "main moves on")
        _git(repo, "checkout", "-q", "feature/unit")
        evidence_notes.attach(repo, _envelope("review", "r-here", {}), head)
        evidence_notes.attach(repo, _envelope("review", "r-there", {}), elsewhere)

        bounded = evidence_notes.ingest(repo)
        assert bounded["status"] == "ok"
        assert (bounded["appended"], bounded["commits"]) == (1, 1)
        assert _keys(repo) == {("review", "r-here")}

        everything = evidence_notes.ingest(repo, bound=False)
        assert (everything["appended"], everything["commits"]) == (1, 2)
        assert _keys(repo) == {("review", "r-here"), ("review", "r-there")}

    def test_the_merge_base_itself_is_inside_the_bound(self, repo):
        """A chunk review of uncommitted work on a fresh branch anchors on the
        commit the branch was cut from — the merge base. Excluding it would
        drop exactly the first round of every branch."""
        merge_base = _git(repo, "rev-parse", "main")
        evidence_notes.attach(repo, _envelope("review", "r-first", {}), merge_base)
        result = evidence_notes.ingest(repo)
        assert (result["appended"], result["commits"]) == (1, 1)

    def test_no_resolvable_base_is_ok_with_nothing_appended_and_a_reason(self, tmp_path):
        repo = tmp_path / "lone"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "trunk")
        head = _seed(repo)
        evidence_notes.attach(repo, _envelope("review", "r-1", {}), head)
        result = evidence_notes.ingest(repo)
        assert result["status"] == "ok"
        assert result["appended"] == 0
        assert result["reason"]
        # --all still reads it.
        assert evidence_notes.ingest(repo, bound=False)["appended"] == 1


class TestIngestParsing:
    def test_a_blank_separated_note_body_ingests_every_record(self, repo):
        head = _git(repo, "rev-parse", "HEAD")
        for fact_id in ("r-1", "r-2", "r-3"):
            assert evidence_notes.attach(repo, _envelope("review", fact_id, {}), head)["status"] == "attached"
        assert "\n\n" in _note(repo, head), "git notes append separates records with a blank line"
        result = evidence_notes.ingest(repo)
        assert (result["appended"], result["seen"], result["commits"]) == (3, 3, 1)
        assert result["reason"] is None, "a blank separator is not a malformed line"
        assert _keys(repo) == {("review", "r-1"), ("review", "r-2"), ("review", "r-3")}

    def test_whitespace_around_records_is_tolerated(self, repo):
        head = _git(repo, "rev-parse", "HEAD")
        line = evidence.envelope_line(_envelope("review", "r-ws", {})).strip()
        _git(repo, "notes", "--ref", NOTES_REF, "add", "-f", "-F", "-", head,
             input=f"\n\n   {line}   \n\n\n")
        assert evidence_notes.ingest(repo)["appended"] == 1

    def test_a_schema_ahead_line_is_appended_verbatim_and_read_as_schema_ahead(self, repo):
        head = _git(repo, "rev-parse", "HEAD")
        ahead = _envelope("review", "r-future", {"new": True}, schema=evidence.SCHEMA_VERSION + 1)
        _git(repo, "notes", "--ref", NOTES_REF, "add", "-f", "-F", "-", head,
             input=evidence.envelope_line(ahead))
        result = evidence_notes.ingest(repo)
        assert result["appended"] == 1
        assert _store_lines(repo) == [evidence.envelope_line(ahead).rstrip("\n")]
        read = evidence.read_facts(repo)
        assert [(s["kind"], s["id"]) for s in read["schema_ahead"]] == [("review", "r-future")]
        assert read["facts"] == []
        # And it is known on the next pass, not re-appended every session.
        assert evidence_notes.ingest(repo)["appended"] == 0

    def test_a_malformed_line_is_skipped_with_its_count_in_reason(self, repo):
        head = _git(repo, "rev-parse", "HEAD")
        good = evidence.envelope_line(_envelope("review", "r-good", {}))
        body = "".join([
            "not json at all\n",
            "[1, 2]\n",
            json.dumps({"schema": 1, "kind": "review", "id": "r-nobody"}) + "\n",
            good,
        ])
        _git(repo, "notes", "--ref", NOTES_REF, "add", "-f", "-F", "-", head, input=body)
        result = evidence_notes.ingest(repo)
        assert result["status"] == "ok"
        assert (result["appended"], result["seen"]) == (1, 1)
        assert "3 malformed" in result["reason"]
        assert _keys(repo) == {("review", "r-good")}

    def test_a_store_only_kind_found_in_a_note_is_not_ingested(self, repo):
        head = _git(repo, "rev-parse", "HEAD")
        body = (evidence.envelope_line(_envelope("test-run", "t-1", {}))
                + evidence.envelope_line(_envelope("review", "r-1", {})))
        _git(repo, "notes", "--ref", NOTES_REF, "add", "-f", "-F", "-", head, input=body)
        result = evidence_notes.ingest(repo)
        assert result["appended"] == 1
        assert _keys(repo) == {("review", "r-1")}
        assert "test-run" not in {k for k, _ in _keys(repo)}
        assert result["reason"] and "not transported" in result["reason"]


class TestIngestCost:
    def _spy(self, monkeypatch) -> list[list[str]]:
        calls: list[list[str]] = []
        real = subprocess.Popen

        class Recording(real):  # type: ignore[misc, valid-type]
            def __init__(self, args, *a, **kw):
                calls.append(list(args))
                super().__init__(args, *a, **kw)

        monkeypatch.setattr(subprocess, "Popen", Recording)
        return calls

    def test_no_notes_ref_costs_exactly_one_subprocess(self, repo, monkeypatch):
        calls = self._spy(monkeypatch)
        result = evidence_notes.ingest(repo)
        assert (result["status"], result["appended"]) == ("ok", 0)
        assert calls == [["git", "rev-parse", "-q", "--verify", NOTES_REF]]

    def test_the_spy_sees_the_work_when_a_ref_exists(self, repo, monkeypatch):
        """Positive control: with notes present the same instrument records the
        listing and the batch read."""
        head = _git(repo, "rev-parse", "HEAD")
        evidence_notes.attach(repo, _envelope("review", "r-1", {}), head)
        calls = self._spy(monkeypatch)
        evidence_notes.ingest(repo)
        assert len(calls) > 1
        assert ["git", "notes", "--ref", NOTES_REF, "list"] in calls
        assert any(c[:3] == ["git", "cat-file", "--batch"] for c in calls)
        # One batch read however many notes there are.
        assert sum(1 for c in calls if c[:2] == ["git", "cat-file"]) == 1


class TestNoNetwork:
    NETWORK = {"fetch", "push", "ls-remote", "pull", "clone"}

    def test_attach_and_ingest_make_no_network_call(self, origin_and_clone, monkeypatch):
        _origin, repo = origin_and_clone
        head = _commit(repo, "src/app.py", "x = 1\n", "work")
        argv: list[tuple[str, ...]] = []
        real_run_git = evidence.run_git

        def recording(project_dir, *args, **kw):
            argv.append(args)
            return real_run_git(project_dir, *args, **kw)

        def no_socket(*_a, **_kw):
            raise AssertionError("a socket was opened")

        monkeypatch.setattr(evidence, "run_git", recording)
        monkeypatch.setattr(socket, "socket", no_socket)
        monkeypatch.setattr(socket, "create_connection", no_socket)

        assert evidence_notes.attach(repo, _envelope("review", "r-1", {}), head)["status"] == "attached"
        _wipe_store(repo)
        assert evidence_notes.ingest(repo)["appended"] == 1
        assert evidence_notes.ingest(repo, bound=False)["status"] == "ok"
        assert argv, "the instrument saw no git call — it would pass any implementation"
        assert {a[0] for a in argv} & {"notes", "cat-file"}, argv
        assert not [a for a in argv if a and a[0] in self.NETWORK], argv


class TestBareOriginRoundTrip:
    def test_clone_b_reaches_clone_as_verdict_from_the_pushed_notes(self, origin_and_clone, tmp_path):
        origin, a = origin_and_clone
        refs = _reviewed_branch(a)
        verdict_a = _verdict(a, refs["base_tree"], refs["c2_tree"])
        assert verdict_a["status"] == "covered", verdict_a
        _git(a, "push", "-q", "origin", "feature/unit", NOTES_REF)

        b = tmp_path / "b"
        _git(tmp_path, "clone", "-q", str(origin), str(b))
        _configure(b)
        b = b.resolve()
        _git(b, "checkout", "-q", "feature/unit")
        _git(b, "fetch", "-q", "origin", f"{NOTES_REF}:{NOTES_REF}")
        assert evidence.read_facts(b)["status"] == "empty"
        assert _verdict(b, refs["base_tree"], refs["c2_tree"])["status"] == "uncovered"

        result = evidence_notes.ingest(b)
        assert result["status"] == "ok", result
        assert result["appended"] == 3
        assert _keys(b) == _keys(a)
        assert _verdict(b, refs["base_tree"], refs["c2_tree"]) == verdict_a


# ---------------------------------------------------------------------------
# append_envelope — the store side of ingest
# ---------------------------------------------------------------------------


class TestAppendEnvelope:
    def test_round_trip_is_byte_stable(self, repo):
        written = evidence.append_fact(repo, "review", "r-1", {"head_tree": "a" * 40, "n": [1, 2.5, None]})
        line = _store_lines(repo)[0]
        _wipe_store(repo)
        again = evidence.append_envelope(repo, json.loads(line))
        assert again["status"] == "appended"
        assert _store_lines(repo) == [line]
        assert evidence.envelope_line(written["envelope"]) == line + "\n"

    def test_an_unknown_kind_and_a_newer_schema_are_appended(self, repo):
        for env in (_envelope("future-kind", "f-1", {}), _envelope("review", "r-9", {}, schema=7)):
            assert evidence.append_envelope(repo, env)["status"] == "appended"
        assert len(_store_lines(repo)) == 2

    @pytest.mark.parametrize("broken", [
        {"schema": 1, "id": "x", "body": {}},
        {"schema": 1, "kind": "review", "body": {}},
        {"schema": "1", "kind": "review", "id": "x", "body": {}},
        {"schema": True, "kind": "review", "id": "x", "body": {}},
        {"schema": 1, "kind": "review", "id": "x", "body": []},
        ["not", "an", "object"],
    ])
    def test_a_non_envelope_is_refused(self, repo, broken):
        assert evidence.append_envelope(repo, broken)["status"] == "error"
        assert _store_lines(repo) == []


# ---------------------------------------------------------------------------
# The CLI: `evidence ingest [--all] [--json]`
# ---------------------------------------------------------------------------


class TestIngestCli:
    def test_no_notes_ref_exits_0_appending_nothing(self, repo):
        proc = _run_hook(repo, "evidence", "ingest")
        assert proc.returncode == 0, proc.stderr
        assert "appended 0" in proc.stdout

    def test_json_reports_the_counts(self, repo):
        head = _git(repo, "rev-parse", "HEAD")
        evidence_notes.attach(repo, _envelope("review", "r-1", {}), head)
        proc = _run_hook(repo, "evidence", "ingest", "--json")
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)
        assert (payload["status"], payload["appended"], payload["seen"], payload["commits"]) == ("ok", 1, 1, 1)
        again = json.loads(_run_hook(repo, "evidence", "ingest", "--json").stdout)
        assert again["appended"] == 0

    def test_all_reads_notes_outside_the_bound(self, repo):
        _git(repo, "checkout", "-q", "main")
        elsewhere = _commit(repo, "other.txt", "o\n", "main moves on")
        _git(repo, "checkout", "-q", "feature/unit")
        evidence_notes.attach(repo, _envelope("review", "r-there", {}), elsewhere)
        assert "appended 0" in _run_hook(repo, "evidence", "ingest").stdout
        proc = _run_hook(repo, "evidence", "ingest", "--all")
        assert proc.returncode == 0, proc.stderr
        assert "appended 1" in proc.stdout

    def test_an_unknown_flag_is_a_usage_error(self, repo):
        proc = _run_hook(repo, "evidence", "ingest", "--bogus")
        assert proc.returncode == 1
        assert "Usage" in proc.stderr
        assert _store_lines(repo) == []


@functools.lru_cache(maxsize=1)
def _hook_module():
    loader = importlib.machinery.SourceFileLoader("prawduct_hook_notes", str(HOOK))
    spec = importlib.util.spec_from_loader("prawduct_hook_notes", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class TestIngestIsADataPlaneWrite:
    """`ingest` appends to the clone's shared store, so it is classified as a
    write by both pre-dispatch guards, while `status` and `list` stay reads."""

    def test_the_ephemeral_guard_refuses_ingest_and_admits_the_reads(self, repo):
        hook = _hook_module()
        assert hook._ephemeral_command_writes("evidence", ["ingest"], repo) is True
        assert hook._ephemeral_command_writes("evidence", ["ingest", "--all"], repo) is True
        for argv in ([], ["status"], ["list"], ["list", "--kind", "review"]):
            assert hook._ephemeral_command_writes("evidence", argv, repo) is False, argv

    def test_ingest_is_refused_inside_a_disposable_agent_worktree(self, repo):
        wid = "c0ffee0123456789a"
        wt = repo / ".claude" / "worktrees" / f"agent-{wid}"
        wt.parent.mkdir(parents=True)
        _git(repo, "worktree", "add", "-q", "-b", f"worktree-agent-{wid}", str(wt), "HEAD")
        refused = _run_hook(wt.resolve(), "evidence", "ingest")
        assert refused.returncode == 1
        assert "BLOCKED" in refused.stderr
        # Control: the read beside it proceeds.
        assert "BLOCKED" not in _run_hook(wt.resolve(), "evidence", "status").stderr

    def test_ingest_is_a_data_plane_op_and_status_is_not(self):
        hook = _hook_module()
        assert hook._is_data_plane_write("evidence", ["ingest"]) is True
        assert hook._is_data_plane_write("evidence", ["status"]) is False
        assert hook._is_data_plane_write("evidence", []) is False
        assert hook._is_data_plane_write("critic-consolidate", []) is True


# ---------------------------------------------------------------------------
# chunk-imported — the hook's import writer attaches on HEAD
# ---------------------------------------------------------------------------


class TestImportedFactsTravel:
    def test_plan_import_status_apply_attaches_each_fact_on_head(self, repo):
        plan = repo / ".prawduct" / "artifacts" / "build-plan-unit.md"
        plan.parent.mkdir(parents=True)
        plan.write_text("\n".join([
            "---", "artifact: build-plan", "scope: unit", "branch: feature/unit", "base: main", "---",
            "", "# Build Plan", "", "## Status", "",
            "- [x] Chunk 01: one", "- [ ] Chunk 02: two", "",
            "## Build Chunks", "", "### Chunk 01: one", "", "- **Deliverables:** `a.py`", "",
            "### Chunk 02: two", "", "- **Deliverables:** `b.py`", "",
        ]) + "\n")
        head = _git(repo, "rev-parse", "HEAD")
        proc = _run_hook(repo, "plan", "import-status", str(plan), "--apply", "--json")
        assert proc.returncode == 0, proc.stderr
        imported = [f for f in evidence.read_facts(repo)["facts"] if f["kind"] == "chunk-imported"]
        assert [f["body"]["chunk"] for f in imported] == ["01"]
        assert _note_records(repo, head) == [_line_of(repo, "chunk-imported", imported[0]["id"])]
