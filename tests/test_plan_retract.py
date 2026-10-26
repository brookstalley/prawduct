"""``prawduct-hook plan retract`` — a recorded retraction of a wrong certification (#1072).

A review fact that names a chunk nobody built certified it, and a fact is never
edited. The answer is a new fact, ``chunk-retracted``, which withdraws exactly
one (fact, chunk) pair: ``plan_status.chunk_states`` stops counting that fact
for that chunk, so the chunk reads open with the retraction's reason, while
the fact's other chunks stay done and a later honest review certifies it again.
Which pair, and whether it may be withdrawn, is ``plan_status.retraction_target``;
the CLI writes behind it, so it is driven here through ``cmd_plan``, the CLI's
own dispatch. The ephemeral guard's view is pinned in
``test_ephemeral_worktree.py::TestPlanRetractUnderTheGuard``.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import evidence, plan_status  # noqa: E402

_loader = importlib.machinery.SourceFileLoader("prawduct_hook_plan_retract", str(HOOK))
_hook = importlib.util.module_from_spec(
    importlib.util.spec_from_loader("prawduct_hook_plan_retract", _loader)
)
_loader.exec_module(_hook)

REL = ".prawduct/artifacts/build-plan-unit.md"
_PLAN = (
    "---\nartifact: build-plan\nscope: unit\nbranch: main\n---\n\n# Build Plan\n\n"
    "## Build Chunks\n\n### Chunk 01: one\n\nBody.\n\n### Chunk 02: two\n\nBody.\n\n"
    "### Chunk 03: three\n\nBody.\n"
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@e.com", "-c", "user.name=T", *args],
        cwd=str(repo), capture_output=True, text=True, check=True, timeout=10,
    ).stdout.strip()


def _repo(tmp_path: Path, plan: str = _PLAN) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    artifacts = repo / ".prawduct" / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "build-plan-unit.md").write_text(plan)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "plan")
    return repo.resolve()


def _review(repo: Path, fact_id: str, chunks: list[str], *, scope: str = "unit") -> None:
    head = _git(repo, "rev-parse", "HEAD")
    body = {
        "scope": scope, "mode": "final", "chunk": chunks[0], "chunks": chunks,
        "head_commit": head, "dispatch_commit": head, "findings": [],
        "counts": {"blocking": 0, "warning": 0, "note": 0},
    }
    assert evidence.append_fact(repo, "review", fact_id, body)["status"] == "appended"


def _states(repo: Path) -> dict[str, tuple[str, "str | None"]]:
    states = plan_status.chunk_states(repo / REL, evidence.read_facts(repo), repo_dir=repo)
    return {k: (s.state, s.fact_id) for k, s in states.items()}


def _retractions(repo: Path) -> list[dict]:
    return evidence.facts_of_kind(evidence.read_facts(repo), plan_status.RETRACTED_KIND)


def _run(repo: Path, capsys, *args: str) -> tuple[int, str, str]:
    rc = _hook.cmd_plan(repo, ["retract", *args])
    out, err = capsys.readouterr()
    return rc, out, err


class TestRetract:
    def test_the_certifying_fact_is_withdrawn_for_that_chunk_only(self, tmp_path, capsys):
        """The #1072 shape: one review certified 01 and two unbuilt chunks."""
        repo = _repo(tmp_path)
        _review(repo, "R1", ["01", "02", "03"])
        assert _states(repo) == {"01": ("done", "R1"), "02": ("done", "R1"), "03": ("done", "R1")}

        rc, out, _err = _run(repo, capsys, "02", "--reason", "certified before it was built")
        assert rc == 0, out
        assert "retracted R1's certification of chunk 02" in out
        assert "chunk 02 now reads: open" in out
        assert _states(repo) == {"01": ("done", "R1"), "02": ("open", None), "03": ("done", "R1")}
        (fact,) = _retractions(repo)
        assert {k: fact["body"][k] for k in ("scope", "chunk", "fact_id", "reason")} == {
            "scope": "unit", "chunk": "02", "fact_id": "R1",
            "reason": "certified before it was built",
        }
        reason = plan_status.chunk_states(repo / REL, evidence.read_facts(repo), repo_dir=repo)["02"].reason
        assert reason == "review R1 names it, but it was retracted: certified before it was built"

    def test_a_later_review_certifies_the_chunk_again(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _review(repo, "R1", ["01", "02"])
        assert _run(repo, capsys, "02", "--reason", "unbuilt")[0] == 0
        (repo / "two.txt").write_text("built\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "Chunk 02")
        _review(repo, "R2", ["02"])
        assert _states(repo)["02"] == ("done", "R2")

    def test_another_fact_still_certifying_is_named(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _review(repo, "R1", ["02"])
        _review(repo, "R2", ["02"])
        rc, out, _err = _run(repo, capsys, "02", "--fact", "R1", "--reason", "wrong")
        assert rc == 0
        assert "chunk 02 now reads: done (certified by R2 — retract that too" in out

    @pytest.mark.parametrize("again", [["--fact", "R1"], []], ids=["fact-named", "same-command"])
    def test_a_rerun_writes_nothing_again(self, tmp_path, capsys, again):
        """The literal re-run — `--fact` omitted, so no fact certifies the
        chunk any more — is idempotent too, not `not-certified`."""
        repo = _repo(tmp_path)
        _review(repo, "R1", ["01", "02"])
        assert _run(repo, capsys, "02", "--reason", "unbuilt")[0] == 0
        rc, out, err = _run(repo, capsys, "02", *again, "--reason", "unbuilt")
        assert rc == 0, err
        assert "already retracted R1's certification of chunk 02" in out
        assert len(_retractions(repo)) == 1

    def test_the_chunk_id_is_normalized_to_the_plan(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _review(repo, "R1", ["01", "02"])
        assert _run(repo, capsys, "2", "--reason", "unbuilt")[0] == 0
        assert _retractions(repo)[0]["body"]["chunk"] == "02"

    def test_the_json_envelope(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _review(repo, "R1", ["01", "02"])
        rc, out, _err = _run(repo, capsys, "02", "--reason", "unbuilt", "--json")
        assert rc == 0
        payload = json.loads(out)
        assert {k: payload[k] for k in ("status", "action", "plan_path", "scope", "chunk", "fact_id",
                                         "state", "certified_by")} == {
            "status": "ok", "action": "retracted", "plan_path": REL, "scope": "unit", "chunk": "02",
            "fact_id": "R1", "state": "open", "certified_by": None,
        }
        assert payload["retraction_id"] == _retractions(repo)[0]["id"]

    def test_the_plan_defaults_to_the_one_this_checkout_is_bound_to(self, tmp_path, capsys):
        """`branch: main` claims the checked-out branch, so no --plan is needed;
        every other test here names nothing either. Control: the plan's
        scope is what the fact records."""
        repo = _repo(tmp_path)
        _review(repo, "R1", ["01"])
        assert _run(repo, capsys, "01", "--reason", "x")[0] == 0
        assert _retractions(repo)[0]["body"]["scope"] == "unit"


class TestTheRetractionTravels:
    def test_it_is_attached_as_a_note_on_head(self, tmp_path, capsys, monkeypatch):
        # `git notes append` commits to the notes ref, so it needs an identity
        # the machine's global config may not supply.
        for var in ("GIT_AUTHOR", "GIT_COMMITTER"):
            monkeypatch.setenv(f"{var}_NAME", "T")
            monkeypatch.setenv(f"{var}_EMAIL", "t@e.com")
        repo = _repo(tmp_path)
        _review(repo, "R1", ["01", "02"])
        assert _run(repo, capsys, "02", "--reason", "unbuilt")[0] == 0
        note = _git(repo, "notes", "--ref", "refs/notes/prawduct", "show", "HEAD")
        (fact,) = _retractions(repo)
        assert fact["id"] in note and plan_status.RETRACTED_KIND in note

    @pytest.mark.parametrize("status, noted", [("attached", False), ("present", False),
                                                ("skipped", True), ("error", True)])
    def test_only_a_note_that_was_not_written_is_a_note(
        self, tmp_path, capsys, monkeypatch, status, noted
    ):
        from lib import evidence_notes

        monkeypatch.setattr(
            evidence_notes, "attach", lambda *_a, **_k: {"status": status, "reason": "stubbed"}
        )
        repo = _repo(tmp_path)
        _review(repo, "R1", ["01"])
        rc, _out, err = _run(repo, capsys, "01", "--reason", "x")
        assert rc == 0
        assert ("its git note was not written" in err) is noted, err


class TestRefusals:
    def _refused(self, repo, capsys, code, *args):
        before = len(_retractions(repo))
        rc, _out, err = _run(repo, capsys, *args)
        assert rc == 1 and f"refused: {code}:" in err, err
        assert len(_retractions(repo)) == before
        return err

    def test_a_chunk_the_plan_does_not_declare(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _review(repo, "R1", ["01"])
        self._refused(repo, capsys, "unknown-chunk", "09", "--reason", "x")

    def test_an_open_chunk_with_no_fact_named(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        self._refused(repo, capsys, "not-certified", "01", "--reason", "x")

    def test_a_box_read_in_memory_says_to_untick_it(self, tmp_path, capsys):
        plan = _PLAN.replace("## Build Chunks", "## Status\n\n- [x] Chunk 01: one\n\n## Build Chunks")
        repo = _repo(tmp_path, plan)
        err = self._refused(repo, capsys, "box-import", "01", "--reason", "x")
        assert "untick the box first" in err

    @pytest.mark.parametrize("certifier", ["import", "review"])
    def test_a_ticked_box_refuses_any_facts_withdrawal(self, tmp_path, capsys, certifier):
        """The box is read after every fact, so withdrawing the fact would
        exit 0 and leave the chunk done — and a later `import-status --apply`
        would mint an import no retraction names. Control: unticked, the same
        withdrawal is written."""
        plan = _PLAN.replace("## Build Chunks", "## Status\n\n- [x] Chunk 01: one\n\n## Build Chunks")
        repo = _repo(tmp_path, plan)
        if certifier == "import":
            body = {"scope": "unit", "chunk": "01", "source": "status-box",
                    "imported_at": "2026-10-26T00:00:00Z"}
            evidence.append_fact(repo, plan_status.IMPORTED_KIND, "F1", body)
        else:
            _review(repo, "F1", ["01"])
        self._refused(repo, capsys, "box-import", "01", "--fact", "F1", "--reason", "x")
        (repo / REL).write_text(plan.replace("- [x] Chunk 01", "- [ ] Chunk 01"))
        assert _run(repo, capsys, "01", "--fact", "F1", "--reason", "x")[0] == 0

    def test_a_fact_not_in_the_store(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        self._refused(repo, capsys, "unknown-fact", "01", "--fact", "R9", "--reason", "x")

    def test_a_fact_of_another_scope(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _review(repo, "R1", ["01"], scope="other")
        self._refused(repo, capsys, "other-scope", "01", "--fact", "R1", "--reason", "x")

    def test_a_fact_that_does_not_name_the_chunk(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _review(repo, "R1", ["01"])
        self._refused(repo, capsys, "not-named", "02", "--fact", "R1", "--reason", "x")

    def test_no_scope(self, tmp_path, capsys):
        repo = _repo(tmp_path, _PLAN.replace("scope: unit\n", ""))
        self._refused(repo, capsys, "no-scope", "01", "--plan", REL, "--reason", "x")

    def test_no_plan_bound_and_none_named(self, tmp_path, capsys):
        repo = _repo(tmp_path, _PLAN.replace("branch: main\n", "branch: elsewhere\n"))
        self._refused(repo, capsys, "no-plan", "01", "--reason", "x")

    def test_an_archived_plan(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        archived = repo / ".prawduct" / "artifacts" / "archive" / "build-plan-unit.md"
        archived.parent.mkdir()
        (repo / REL).rename(archived)
        self._refused(repo, capsys, "archived-plan", "01", "--plan",
                      ".prawduct/artifacts/archive/build-plan-unit.md", "--reason", "x")

    def test_a_nested_archived_plan(self, tmp_path, capsys):
        """`plan_archive` writes a nested plan's archive beside it, so the
        `archive` component can sit at any depth (`work_unit.is_live_plan_file`)."""
        repo = _repo(tmp_path)
        nested = repo / ".prawduct" / "artifacts" / "plans" / "u" / "archive" / "build-plan-unit.md"
        nested.parent.mkdir(parents=True)
        (repo / REL).rename(nested)
        self._refused(repo, capsys, "archived-plan", "01", "--plan",
                      str(nested.relative_to(repo)), "--reason", "x")
        rc = _hook.cmd_plan(repo, ["import-status", str(nested.relative_to(repo)), "--apply"])
        assert rc == 1 and "refused: archived-plan:" in capsys.readouterr().err

    def test_an_append_failure(self, tmp_path, capsys, monkeypatch):
        """Without the kind registered the store refuses it — the state of any
        plugin that predates the kind."""
        repo = _repo(tmp_path)
        _review(repo, "R1", ["01"])
        monkeypatch.setattr(evidence, "KNOWN_KINDS", evidence.KNOWN_KINDS - {plan_status.RETRACTED_KIND})
        self._refused(repo, capsys, "fact-append-failed", "01", "--reason", "x")

    @pytest.mark.parametrize(
        "argv",
        [[], ["01", "02", "--reason", "x"], ["01"], ["01", "--reason", "  "], ["01", "--bogus"],
         ["01", "--reason", "x", "--plan", "missing.md"],
         ["01", "--reason", "x", "--plan", ".prawduct/notes.md"]],
        ids=["no-chunk", "two-chunks", "no-reason", "blank-reason", "unknown-flag", "unreadable",
             "not-a-plan"],
    )
    def test_usage_errors_exit_2(self, tmp_path, capsys, argv):
        repo = _repo(tmp_path)
        _review(repo, "R1", ["01"])
        (repo / ".prawduct" / "notes.md").write_text("---\nartifact: product-brief\n---\n\n# Notes\n")
        rc, _out, _err = _run(repo, capsys, *argv)
        assert rc == 2
        assert _retractions(repo) == []


def test_the_help_names_the_op(capsys):
    assert _hook.cmd_plan(Path("."), ["--help"]) == 0
    assert "plan retract <chunk> --reason R" in capsys.readouterr().out


class TestNoProposalRestoresARetraction:
    """A retraction withdraws a certification; a later dispatch that copies a
    chunk set forward without asking about it would restore it. Each route a
    proposal is derived by is pinned here."""

    def test_a_verify_pass_does_not_inherit_a_retracted_chunk(self, tmp_path, capsys):
        from lib import critic_consolidate as cc

        repo = _repo(tmp_path)
        _review(repo, "R1", ["01", "02", "03"])
        assert _run(repo, capsys, "03", "--fact", "R1", "--reason", "unbuilt")[0] == 0
        read = evidence.read_facts(repo)
        (anchor,) = [f for f in evidence.facts_of_kind(read, "review") if f["id"] == "R1"]
        proposed = cc._proposed_chunks(
            repo, repo / REL, lambda: read, [], "verify-resolutions", anchor,
        )
        assert proposed == ["01", "02"]

    def test_a_mid_plan_final_reads_subjects_in_its_own_interval_only(self, tmp_path, capsys):
        """Chunk 01 was built and its certification retracted; Chunk 02 is
        built after. A `final` whose interval starts after 01's commit must
        not name 01 by its subject. Control: with the plan's whole branch
        (`since` omitted), 01's subject is read."""
        repo = _repo(tmp_path)
        _git(repo, "checkout", "-q", "-b", "feature")
        (repo / ".prawduct" / "artifacts" / "build-plan-unit.md").write_text(
            _PLAN.replace("branch: main", "branch: feature\nbase: main"))
        _git(repo, "commit", "-qam", "claim")
        (repo / "one.txt").write_text("1\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "feat(unit): Chunk 01 — one")
        frontier = _git(repo, "rev-parse", "HEAD")
        (repo / "two.txt").write_text("2\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "feat(unit): Chunk 02 — two")
        facts = evidence.read_facts(repo)
        plan = repo / REL
        assert plan_status.propose_chunks(plan, facts, [], "final", repo_dir=repo, since=frontier) == ["02"]
        assert plan_status.propose_chunks(plan, facts, [], "final", repo_dir=repo) == ["01", "02"]
