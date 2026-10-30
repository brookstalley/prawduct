"""``lib/evidence_sync.py`` — the notes ref moves between clones (#1052).

``evidence_notes`` writes and reads ``refs/notes/prawduct`` inside one clone;
this module is the step that moves it: fetch the remote's notes into a tracking
ref, merge them by ``cat_sort_uniq``, attach any stored fact whose note is
missing, ingest, push. And ``configure`` sets the clone up so a plain
``git fetch`` carries the notes and a rebase carries them along.

Fixtures are real git — a bare origin and clones of it — because every claim
here is about what git does with the ref: a first push to a remote that has no
notes, a non-fast-forward rejection, a merge left unfinished.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import evidence, evidence_notes, evidence_sync  # noqa: E402

NOTES_REF = "refs/notes/prawduct"
TRACKING_REF = "refs/notes/origin/prawduct"
#: The pattern form. A configured EXACT refspec makes a plain ``git fetch`` die
#: (``couldn't find remote ref``) while the remote has no notes, which is every
#: fresh onboard (R-1, probed on git 2.54); a pattern matching nothing is not an
#: error.
REFSPEC = f"+{NOTES_REF}*:{TRACKING_REF}*"


@pytest.fixture(autouse=True)
def _sterile_git(monkeypatch, tmp_path):
    """The module runs git in-process through ``evidence.run_git``, which
    inherits this env: no operator config, and an identity for notes commits."""
    home = tmp_path / "_home"
    home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", "/dev/null")
    monkeypatch.setenv("GIT_TERMINAL_PROMPT", "0")
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "T")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "t@example.com")
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    monkeypatch.delenv("PRAWDUCT_ALLOW_EPHEMERAL_WRITES", raising=False)


def _git(repo: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, check=check, timeout=20,
    )
    return proc.stdout.strip()


def _commit(repo: Path, rel: str, text: str, subject: str) -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    _git(repo, "add", rel)
    _git(repo, "commit", "-qm", subject)
    return _git(repo, "rev-parse", "HEAD")


def _ref(repo: Path, ref: str) -> "str | None":
    return _git(repo, "rev-parse", "-q", "--verify", ref, check=False) or None


def _note_records(repo: Path, commit: str, ref: str = NOTES_REF) -> list[str]:
    proc = subprocess.run(
        ["git", "notes", "--ref", ref, "show", commit],
        cwd=str(repo), capture_output=True, text=True, timeout=20,
    )
    return [ln for ln in proc.stdout.splitlines() if ln.strip()] if proc.returncode == 0 else []


def _keys(repo: Path) -> set[tuple[str, str]]:
    return {(f["kind"], f["id"]) for f in evidence.read_facts(repo)["facts"]}


@pytest.fixture
def origin(tmp_path: Path) -> Path:
    """A bare origin holding `main` and `feature/unit` (one commit past main)."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    seed = tmp_path / "seed"
    _git(tmp_path, "init", "-q", "-b", "main", str(seed))
    _commit(seed, ".gitignore", ".prawduct/\n", "seed")
    _git(seed, "remote", "add", "origin", str(origin))
    _git(seed, "push", "-q", "origin", "main")
    _git(seed, "checkout", "-q", "-b", "feature/unit")
    _commit(seed, "src/app.py", "x = 1\n", "work")
    _git(seed, "push", "-q", "origin", "feature/unit")
    return origin


def _clone(tmp_path: Path, origin: Path, name: str) -> Path:
    repo = tmp_path / name
    _git(tmp_path, "clone", "-q", str(origin), str(repo))
    _git(repo, "checkout", "-q", "feature/unit")
    return repo.resolve()


@pytest.fixture
def a(tmp_path: Path, origin: Path) -> Path:
    return _clone(tmp_path, origin, "a")


@pytest.fixture
def b(tmp_path: Path, origin: Path) -> Path:
    return _clone(tmp_path, origin, "b")


def _review(repo: Path, fact_id: str, *, attach: bool = True) -> str:
    """A review fact on HEAD; its note written unless ``attach=False`` (the
    state a consolidation leaves that appended and never attached)."""
    head = _git(repo, "rev-parse", "HEAD")
    appended = evidence.append_fact(repo, "review", fact_id, {"head_commit": head})
    assert appended["status"] == "appended", appended
    if attach:
        assert evidence_notes.attach(repo, appended["envelope"], head)["status"] == "attached"
    return head


# ---------------------------------------------------------------------------
# sync
# ---------------------------------------------------------------------------


class TestSync:
    def test_first_sync_with_no_remote_notes_pushes_and_reports_pushed(self, a, origin):
        head = _review(a, "r-a")
        assert _ref(origin, NOTES_REF) is None
        result = evidence_sync.sync(a)
        assert result["status"] == "ok", result
        assert (result["step"], result["pushed"]) == (None, True)
        assert _ref(origin, NOTES_REF) == _ref(a, NOTES_REF)
        assert len(_note_records(origin, head)) == 1

    def test_two_clones_noting_one_commit_both_end_with_both_records_once(self, a, b):
        head = _review(a, "r-a")
        assert _review(b, "r-b") == head
        assert evidence_sync.sync(a)["pushed"] is True
        second = evidence_sync.sync(b)
        assert (second["status"], second["ingested"], second["pushed"]) == ("ok", 1, True), second
        third = evidence_sync.sync(a)
        assert (third["status"], third["ingested"]) == ("ok", 1), third

        both = {("review", "r-a"), ("review", "r-b")}
        for clone in (a, b):
            records = _note_records(clone, head)
            assert len(records) == 2, records  # each once, no blank residue
            assert {(json.loads(r)["kind"], json.loads(r)["id"]) for r in records} == both
            assert _keys(clone) == both
        assert _ref(a, NOTES_REF) == _ref(b, NOTES_REF)

    def test_a_clone_behind_the_remote_gains_the_other_clones_facts(self, a, b):
        _review(a, "r-1")
        _commit(a, "src/app.py", "x = 2\n", "fix")
        _review(a, "r-2")
        _git(a, "push", "-q", "origin", "feature/unit")
        assert evidence_sync.sync(a)["pushed"] is True

        _git(b, "pull", "-q", "--ff-only")
        assert _ref(b, NOTES_REF) is None
        result = evidence_sync.sync(b, push=False)
        assert (result["status"], result["ingested"]) == ("ok", 2), result
        assert _keys(b) == _keys(a) == {("review", "r-1"), ("review", "r-2")}
        assert _ref(b, NOTES_REF) == _ref(a, NOTES_REF)

    def test_push_false_pushes_nothing(self, a, origin):
        _review(a, "r-a")
        result = evidence_sync.sync(a, push=False)
        assert (result["status"], result["pushed"]) == ("ok", False), result
        assert _ref(origin, NOTES_REF) is None
        # Control: the same clone with push on does reach the origin.
        assert evidence_sync.sync(a)["pushed"] is True
        assert _ref(origin, NOTES_REF) is not None

    def test_a_rejected_push_reports_step_push_and_leaves_the_local_ref(self, a, origin):
        head = _review(a, "r-a")
        hook = origin / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\necho 'notes are not welcome here' >&2\nexit 1\n")
        hook.chmod(0o755)
        before = _ref(a, NOTES_REF)
        result = evidence_sync.sync(a)
        assert (result["status"], result["step"], result["pushed"]) == ("error", "push", False), result
        assert "notes are not welcome here" in result["reason"]
        assert _ref(a, NOTES_REF) == before
        assert len(_note_records(a, head)) == 1
        assert _ref(origin, NOTES_REF) is None

    def test_an_unfinished_notes_merge_reports_step_merge_and_is_left_alone(self, a, b):
        head = _review(a, "r-a")
        assert evidence_sync.sync(a)["pushed"] is True
        _review(b, "r-b")
        _git(b, "fetch", "-q", "origin", REFSPEC)
        # A manual-strategy merge of conflicting notes stops half-way, as a
        # person's own `git notes merge` would.
        stuck = subprocess.run(
            ["git", "notes", "--ref", NOTES_REF, "merge", "-s", "manual", TRACKING_REF],
            cwd=str(b), capture_output=True, text=True, timeout=20,
        )
        assert stuck.returncode != 0, stuck
        merge_ref = Path(_git(b, "rev-parse", "--git-path", "NOTES_MERGE_REF"))
        merge_ref = merge_ref if merge_ref.is_absolute() else b / merge_ref
        assert merge_ref.exists()
        before = _ref(b, NOTES_REF)

        result = evidence_sync.sync(b)
        assert (result["status"], result["step"], result["pushed"]) == ("error", "merge", False), result
        assert "merge --abort" in result["reason"]
        # O-19: the reason says what was observed — the merge-state path exists.
        assert f"{merge_ref.name} exists" in result["reason"], result["reason"]
        assert merge_ref.exists(), "the unfinished merge is the person's; sync must not clear it"
        assert _ref(b, NOTES_REF) == before
        assert len(_note_records(b, head)) == 1

    def test_git_failing_to_locate_the_merge_state_is_not_reported_as_an_unfinished_merge(self, a, monkeypatch):
        """O-19: when ``rev-parse --git-path`` fails nothing was seen of a merge,
        so the reason must not prescribe finishing or aborting one."""
        _review(a, "r-a")
        real_run_git = evidence.run_git

        def failing_git_path(project_dir, *args, **kw):
            if args[:2] == ("rev-parse", "--git-path"):
                return 128, "", "fatal: simulated"
            return real_run_git(project_dir, *args, **kw)

        monkeypatch.setattr(evidence, "run_git", failing_git_path)
        result = evidence_sync.sync(a)
        assert (result["status"], result["step"], result["pushed"]) == ("error", "merge", False), result
        assert "could not answer" in result["reason"] and "fatal: simulated" in result["reason"], result
        assert "unfinished" not in result["reason"] and "--abort" not in result["reason"], result

    def test_a_remote_that_cannot_be_reached_reports_step_fetch(self, a):
        _review(a, "r-a")
        _git(a, "remote", "set-url", "origin", str(a.parent / "nowhere.git"))
        result = evidence_sync.sync(a)
        assert (result["status"], result["step"], result["pushed"]) == ("error", "fetch", False), result
        assert result["reason"]

    def test_no_remote_is_ok_with_the_reason_and_nothing_done(self, tmp_path):
        repo = tmp_path / "solo"
        _git(tmp_path, "init", "-q", "-b", "main", str(repo))
        _commit(repo, "a.txt", "a\n", "seed")
        result = evidence_sync.sync(repo)
        assert (result["status"], result["step"], result["pushed"]) == ("ok", None, False), result
        assert "no remote" in result["reason"]


class TestSyncReconciles:
    def test_a_stored_fact_with_no_note_is_attached_and_sent(self, a, b):
        head = _review(a, "r-lost", attach=False)
        assert _ref(a, NOTES_REF) is None
        first = evidence_sync.sync(a)
        assert (first["status"], first["reconciled"], first["pushed"]) == ("ok", 1, True), first
        assert len(_note_records(a, head)) == 1
        second = evidence_sync.sync(a)
        assert (second["status"], second["reconciled"]) == ("ok", 0), second
        assert len(_note_records(a, head)) == 1

        # And it reaches the other clone, which is the point of re-sending it.
        assert evidence_sync.sync(b, push=False)["ingested"] == 1
        assert _keys(b) == {("review", "r-lost")}


def _unpushed_lines(repo: Path, capsys) -> list[str]:
    capsys.readouterr()
    assert evidence.evidence_cmd(repo, ["status"]) == 0
    return [ln for ln in capsys.readouterr().out.splitlines()
            if "not yet pushed" in ln or "never pushed" in ln]


class TestStatusNamesUnpushedNotes:
    """O-17/O-8: a failed or skipped push leaves every fact attached locally, so
    the no-note count reads 0 while nothing has left the clone. The local ref
    against the push remote's tracking ref is the durable view of that leg."""

    def test_an_attach_after_a_sync_is_one_unpushed_note_commit_and_a_sync_clears_it(self, a, capsys):
        _review(a, "r-1")
        assert evidence_sync.sync(a)["pushed"] is True
        assert _unpushed_lines(a, capsys) == ["0 note commit(s) not yet pushed"]

        _commit(a, "src/app.py", "x = 2\n", "fix")
        _review(a, "r-2")
        assert _unpushed_lines(a, capsys) == [
            "1 note commit(s) not yet pushed — run `prawduct-hook evidence sync`"
        ]
        assert evidence_sync.sync(a)["pushed"] is True
        assert _unpushed_lines(a, capsys) == ["0 note commit(s) not yet pushed"]

    def test_a_refused_push_stays_visible_after_the_run(self, a, origin, capsys):
        _review(a, "r-1")
        assert evidence_sync.sync(a)["pushed"] is True
        _commit(a, "src/app.py", "x = 2\n", "fix")
        _review(a, "r-2")
        hook = origin / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        assert evidence_sync.sync(a)["step"] == "push"
        assert _unpushed_lines(a, capsys) == [
            "1 note commit(s) not yet pushed — run `prawduct-hook evidence sync`"
        ]

    def test_a_local_ref_with_no_tracking_ref_is_named_as_never_pushed(self, a, origin, capsys):
        """Renegotiated (R-10): this pinned silence — "nothing to compare
        against" — but a clone whose FIRST push failed is exactly that state,
        every fact attached locally and none sent, and the no-note count reads
        0. The local ref alone is the count: every commit on it is unsent."""
        _review(a, "r-1")
        assert _ref(a, TRACKING_REF) is None
        assert _unpushed_lines(a, capsys) == [
            "1 note commit(s) never pushed from this clone — run `prawduct-hook evidence sync`"
        ]

    def test_a_refused_first_push_leaves_the_never_pushed_line(self, a, origin, capsys):
        _review(a, "r-1")
        hook = origin / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        assert evidence_sync.sync(a)["step"] == "push"
        assert _ref(a, TRACKING_REF) is None
        assert _unpushed_lines(a, capsys) == [
            "1 note commit(s) never pushed from this clone — run `prawduct-hook evidence sync`"
        ]
        # Control: once a push lands the line becomes the tracked count.
        hook.unlink()
        assert evidence_sync.sync(a)["pushed"] is True
        assert _unpushed_lines(a, capsys) == ["0 note commit(s) not yet pushed"]

    def test_no_local_ref_prints_no_unpushed_line(self, a, capsys):
        """Nothing attached here: nothing to push, so no line (the no-note
        line already names the stored facts)."""
        _review(a, "r-1", attach=False)
        assert _ref(a, NOTES_REF) is None
        assert _unpushed_lines(a, capsys) == []


class TestNetworkDiscipline:
    NETWORK = {"fetch", "push", "ls-remote", "pull", "clone"}

    def test_every_network_call_goes_through_run_git_with_the_floor(self, a, monkeypatch):
        _review(a, "r-a")
        through_run_git: list[tuple[str, ...]] = []
        real_run_git = evidence.run_git

        def recording(project_dir, *args, **kw):
            through_run_git.append(args)
            return real_run_git(project_dir, *args, **kw)

        launched: list[tuple[list[str], object]] = []
        real_run = subprocess.run

        def spy_run(argv, *args, **kw):
            launched.append((list(argv), kw.get("timeout")))
            return real_run(argv, *args, **kw)

        monkeypatch.setattr(evidence, "run_git", recording)
        monkeypatch.setattr(subprocess, "run", spy_run)
        assert evidence_sync.sync(a)["status"] == "ok"

        network = [(argv, t) for argv, t in launched if argv[:1] == ["git"] and argv[1] in self.NETWORK]
        assert {argv[1] for argv, _t in network} == {"fetch", "push"}, launched
        for argv, timeout in network:
            assert tuple(argv[1:]) in through_run_git, argv
            assert timeout is not None and timeout >= evidence.NETWORK_TIMEOUT_FLOOR, (argv, timeout)

    def test_no_gh_anywhere_in_the_module(self):
        source = Path(evidence_sync.__file__).read_text(encoding="utf-8")
        literals = [
            node.value for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        ]
        assert literals, "the walk found no string literal — it would pass any module"
        assert "gh" not in literals
        assert not any(lit.startswith("gh ") for lit in literals)
        assert "_gh_json" not in source and "shutil.which" not in source

    def test_a_credential_in_git_output_is_scrubbed_before_it_is_reported(self, a, origin):
        """git relays the remote's stderr verbatim (`remote: …`), so a token a
        server-side hook prints reaches the reason unless it is scrubbed."""
        _review(a, "r-a")
        token = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
        hook = origin / "hooks" / "pre-receive"
        hook.write_text(f"#!/bin/sh\necho 'denied for {token}' >&2\nexit 1\n")
        hook.chmod(0o755)
        result = evidence_sync.sync(a)
        assert (result["status"], result["step"]) == ("error", "push"), result
        assert "denied for" in result["reason"], "the remote's message must reach the reason"
        assert token not in json.dumps(result)
        assert "[REDACTED]" in result["reason"]


# ---------------------------------------------------------------------------
# configure
# ---------------------------------------------------------------------------


def _config(repo: Path, key: str) -> list[str]:
    out = _git(repo, "config", "--get-all", key, check=False)
    return out.splitlines() if out else []


class TestConfigure:
    def test_preview_writes_nothing_and_names_both_changes(self, a):
        before = (a / ".git" / "config").read_text()
        result = evidence_sync.configure(a, apply=False)
        assert (result["status"], result["applied"]) == ("ok", False), result
        # R-4: a change is what is added, nothing else — no released version
        # wrote another notes refspec, so there is nothing to replace.
        assert all(set(c) == {"key", "value"} for c in result["changes"]), result
        assert [(c["key"], c["value"]) for c in result["changes"]] == [
            ("remote.origin.fetch", REFSPEC),
            ("notes.rewriteRef", NOTES_REF),
        ]
        assert (a / ".git" / "config").read_text() == before

    def test_apply_writes_both_keys_and_a_second_apply_changes_nothing(self, a):
        fetch_before = _config(a, "remote.origin.fetch")
        result = evidence_sync.configure(a, apply=True)
        assert (result["status"], result["applied"]) == ("ok", True), result
        assert _config(a, "remote.origin.fetch") == fetch_before + [REFSPEC]
        assert _config(a, "notes.rewriteRef") == [NOTES_REF]

        again = evidence_sync.configure(a, apply=True)
        assert (again["status"], again["applied"], again["changes"]) == ("ok", False, []), again
        assert _config(a, "remote.origin.fetch") == fetch_before + [REFSPEC]
        assert _config(a, "notes.rewriteRef") == [NOTES_REF]

    def test_an_existing_rewrite_ref_is_kept_beside_ours(self, a):
        _git(a, "config", "notes.rewriteRef", "refs/notes/commits")
        assert evidence_sync.configure(a, apply=True)["applied"] is True
        assert _config(a, "notes.rewriteRef") == ["refs/notes/commits", NOTES_REF]

    def test_no_remote_is_ok_with_the_reason(self, tmp_path):
        repo = tmp_path / "solo"
        _git(tmp_path, "init", "-q", "-b", "main", str(repo))
        _commit(repo, "a.txt", "a\n", "seed")
        result = evidence_sync.configure(repo, apply=True)
        assert (result["status"], result["applied"], result["changes"]) == ("ok", False, []), result
        assert "no remote" in result["reason"]

    def test_after_apply_a_plain_fetch_carries_the_notes(self, a, b):
        head = _review(a, "r-a")
        assert evidence_sync.sync(a)["pushed"] is True
        _git(b, "fetch", "-q")
        assert _ref(b, TRACKING_REF) is None, "control: unconfigured, a plain fetch leaves notes behind"
        assert evidence_sync.configure(b, apply=True)["applied"] is True
        _git(b, "fetch", "-q")
        assert _ref(b, TRACKING_REF) == _ref(a, NOTES_REF)
        assert len(_note_records(b, head, ref=TRACKING_REF)) == 1

    def test_after_apply_a_plain_fetch_succeeds_while_the_remote_has_no_notes(self, a, b, origin):
        """R-1: the normal state right after onboarding. An exact refspec makes
        every plain ``git fetch`` (and ``pull``) exit 128 until some clone
        pushes notes; the pattern form matches nothing and fetches the rest."""
        assert _ref(origin, NOTES_REF) is None
        assert evidence_sync.configure(b, apply=True)["applied"] is True
        fetched = subprocess.run(["git", "fetch", "-q"], cwd=str(b), capture_output=True, text=True, timeout=20)
        assert fetched.returncode == 0, fetched.stderr
        assert _ref(b, TRACKING_REF) is None

        head = _review(a, "r-a")
        assert evidence_sync.sync(a)["pushed"] is True
        again = subprocess.run(["git", "fetch", "-q"], cwd=str(b), capture_output=True, text=True, timeout=20)
        assert again.returncode == 0, again.stderr
        assert _ref(b, TRACKING_REF) == _ref(a, NOTES_REF)
        assert len(_note_records(b, head, ref=TRACKING_REF)) == 1

    def test_a_sibling_notes_ref_the_pattern_fetches_is_never_read(self, a, b):
        """The pattern also carries ``refs/notes/prawduct-other`` to
        ``refs/notes/origin/prawduct-other``; the readers' roster must not
        take it for the tracking ref."""
        head = _git(a, "rev-parse", "HEAD")
        sibling = evidence.envelope_line({
            "schema": 1, "kind": "review", "id": "r-sibling", "ts": "2026-10-25T10:00:00Z",
            "actor": {"plugin": "9.9.9"}, "body": {"head_commit": head},
        })
        _git(a, "notes", "--ref", "refs/notes/prawduct-other", "add", "-m", sibling.strip(), head)
        _git(a, "push", "-q", "origin", "refs/notes/prawduct-other")
        assert evidence_sync.configure(b, apply=True)["applied"] is True
        _git(b, "fetch", "-q")
        assert _ref(b, "refs/notes/origin/prawduct-other") is not None, "the instrument reached nothing"
        assert evidence_notes.notes_refs(b) == []
        assert evidence_notes.ingest(b, bound=False)["appended"] == 0
        assert ("review", "r-sibling") not in _keys(b)

    def test_after_apply_a_rebase_carries_the_note_along(self, a):
        _commit(a, "src/app.py", "x = 2\n", "fix")
        head = _review(a, "r-a")
        assert evidence_sync.configure(a, apply=True)["applied"] is True
        _git(a, "commit", "-q", "--amend", "-m", "fix (amended)")
        amended = _git(a, "rev-parse", "HEAD")
        assert amended != head
        assert len(_note_records(a, amended)) == 1


# ---------------------------------------------------------------------------
# The hook-facing functions
# ---------------------------------------------------------------------------


class TestCmdEvidenceSync:
    def test_json_reports_the_result_and_exits_0(self, a, capsys):
        _review(a, "r-a")
        assert evidence_sync.cmd_evidence_sync(a, ["--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert set(payload) == {"status", "step", "pushed", "ingested", "reconciled", "reason"}
        assert (payload["status"], payload["pushed"]) == ("ok", True)

    def test_no_push_is_honoured(self, a, origin, capsys):
        _review(a, "r-a")
        assert evidence_sync.cmd_evidence_sync(a, ["--no-push"]) == 0
        assert _ref(origin, NOTES_REF) is None
        assert "not pushed" in capsys.readouterr().out

    def test_a_reported_failure_exits_1_naming_the_step(self, a, origin, capsys):
        _review(a, "r-a")
        hook = origin / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        assert evidence_sync.cmd_evidence_sync(a, []) == 1
        assert "failed at push" in capsys.readouterr().err

    def test_an_unknown_argument_is_a_usage_error_and_does_nothing(self, a, origin, capsys):
        _review(a, "r-a")
        assert evidence_sync.cmd_evidence_sync(a, ["--bogus"]) == 2
        assert "Usage" in capsys.readouterr().err
        assert _ref(origin, NOTES_REF) is None


def _evidence_ops(text: str) -> set[str]:
    import re  # noqa: PLC0415

    match = re.search(r"\bevidence \{([^}]*\|[^}]*)\}", text)
    assert match, "no `evidence {...}` usage line"
    return {alt.strip().split()[0] for alt in match.group(1).split("|") if alt.strip()}


class TestLibUsageOffersEveryOp:
    """O-3/O-6, R-6: the lib's router dispatches every op and prints the usage
    an unknown one gets, so its line must offer the same five ops the hook's
    usage line does."""

    def test_the_lib_usage_and_the_hook_usage_offer_the_same_ops(self):
        hook_text = (ROOT / "bin" / "prawduct-hook").read_text(encoding="utf-8")
        hook_ops = _evidence_ops(hook_text)
        assert {"sync", "configure"} <= hook_ops, "control: the hook's line offers the two"
        assert _evidence_ops(evidence._CLI_USAGE) == hook_ops

    def test_an_unknown_op_is_a_usage_error_exit_2_naming_sync_and_configure(self, a, capsys):
        """Renegotiated (R-6): an unknown op exited 1, the code a reported
        failure uses; it is a usage error, 2, like every op's bad flag."""
        assert evidence.evidence_cmd(a, ["bogus"]) == 2
        err = capsys.readouterr().err
        assert "sync [--no-push] [--json]" in err and "configure [--apply] [--json]" in err, err

    @pytest.mark.parametrize("op", ["sync", "configure"])
    def test_the_lib_router_reaches_sync_and_configure_itself(self, a, origin, capsys, op):
        """R-6: one router. The lib's `evidence_cmd` dispatches `sync` and
        `configure` (it printed a usage and exited 1 for both while the hook
        routed them around it)."""
        assert evidence.evidence_cmd(a, [op, "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] == "ok", payload
        assert evidence.evidence_cmd(a, [op, "--bogus"]) == 2


class TestCmdEvidenceConfigure:
    def test_preview_lists_the_changes_and_writes_nothing(self, a, capsys):
        assert evidence_sync.cmd_evidence_configure(a, []) == 0
        out = capsys.readouterr().out
        assert f"remote.origin.fetch {REFSPEC}" in out and "--apply" in out
        assert REFSPEC not in _config(a, "remote.origin.fetch")

    def test_apply_writes_and_json_reports(self, a, capsys):
        assert evidence_sync.cmd_evidence_configure(a, ["--apply", "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert set(payload) == {"status", "changes", "applied", "reason"}
        assert payload["applied"] is True
        assert REFSPEC in _config(a, "remote.origin.fetch")

    def test_an_unknown_argument_is_a_usage_error(self, a, capsys):
        assert evidence_sync.cmd_evidence_configure(a, ["--force"]) == 2
        assert "Usage" in capsys.readouterr().err
        assert REFSPEC not in _config(a, "remote.origin.fetch")


class TestApiContractAgrees:
    """R-4/R-6: the contract's transport entry is what a caller codes against;
    it must not promise a ``replaces`` key ``configure`` no longer returns, and
    must state the one exit convention every op now shares."""

    def _entry(self) -> str:
        text = (ROOT.parent / ".prawduct" / "artifacts" / "api-contract.md").read_text(encoding="utf-8")
        start = text.index("- **Evidence transport**")
        return " ".join(text[start: text.index("\n- **", start + 1)].split())

    def test_configure_promises_no_replaces_key(self):
        entry = self._entry()
        assert "`evidence configure [--apply] [--json]`" in entry, "the instrument reached the entry"
        assert "replaces" not in entry and "replaced" not in entry, entry

    def test_ingest_states_usage_as_exit_2(self):
        entry = self._entry()
        ingest = entry[entry.index("`evidence ingest [--all] [--json]`"): entry.index("`evidence sync [--no-push]")]
        assert "2 usage" in ingest, ingest
        assert "1 on an error or an unknown argument" not in ingest, ingest
