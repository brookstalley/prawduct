"""``prawduct-hook plan import-status`` — MG2: ticked boxes become ``chunk-imported`` facts.

The writer moves an answer the reader already gives: ``plan_status.chunk_states``
reads each ticked ``## Status`` box as ``done, imported`` in memory (MG1), and
the import writes exactly those chunks as facts. So after ``--apply`` the
chunk table is unchanged except that each imported row now cites its fact.
``--remove-block`` deletes the ``## Status`` section, and it is a writer
reusing a reader's bounds (``plan_index.status_section_bounds``), so every
shape whose extent the reader would guess at is refused, never deleted.

Driven in-process through ``cmd_plan`` — the CLI's own dispatch — so the
``chunk-imported`` kind can be admitted to ``evidence.KNOWN_KINDS`` with
monkeypatch until Chunk 02 (delegate A) adds it. After that merge the patch
is a no-op superset. The ephemeral guard's view of the op is pinned in
``test_ephemeral_worktree.py::TestPlanImportStatusUnderTheGuard``.
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

_loader = importlib.machinery.SourceFileLoader("prawduct_hook_import_status", str(HOOK))
_hook = importlib.util.module_from_spec(
    importlib.util.spec_from_loader("prawduct_hook_import_status", _loader)
)
_loader.exec_module(_hook)

REL = ".prawduct/artifacts/build-plan-unit.md"

_HEAD = "---\nartifact: build-plan\nscope: unit\nbranch: main\n---\n\n# Build Plan\n\n## Goals\n\nShip it.\n\n"
_STATUS = (
    "## Status\n\n"
    "<!-- the old rule: tick when built and reviewed -->\n\n"
    "- [x] Chunk 01: one\n"
    "- [ ] Chunk 02: two\n"
    "- [x] Chunk 03: three\n\n"
    "Context: two of three landed.\n\n"
)
_TAIL = (
    "## Build Chunks\n\n### Chunk 01: one\n\nBody.\n\n### Chunk 02: two\n\nBody.\n\n"
    "### Chunk 03: three\n\nBody.\n"
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@e.com", "-c", "user.name=T", *args],
        cwd=str(repo), capture_output=True, text=True, check=True, timeout=10,
    )


@pytest.fixture(autouse=True)
def _kind_admitted(monkeypatch):
    """Admit the kind at the writer until Chunk 02 lands it in KNOWN_KINDS."""
    monkeypatch.setattr(evidence, "KNOWN_KINDS", evidence.KNOWN_KINDS | {plan_status.IMPORTED_KIND})


def _repo(tmp_path: Path, plan: str, *, newline: str = "\n") -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "seed.txt").write_text("seed\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "seed")
    artifacts = repo / ".prawduct" / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "build-plan-unit.md").write_bytes(plan.replace("\n", newline).encode("utf-8"))
    return repo.resolve()


def _imports(repo: Path) -> list[dict]:
    return evidence.facts_of_kind(evidence.read_facts(repo), plan_status.IMPORTED_KIND)


def _store_bytes(repo: Path) -> bytes:
    path = evidence.store_path(repo)
    return path.read_bytes() if path is not None and path.is_file() else b""


def _run(repo: Path, capsys, *args: str) -> tuple[int, str, str]:
    rc = _hook.cmd_plan(repo, ["import-status", *args])
    out, err = capsys.readouterr()
    return rc, out, err


class TestPreviewAndApply:
    def test_the_preview_writes_nothing(self, tmp_path, capsys):
        repo = _repo(tmp_path, _HEAD + _STATUS + _TAIL)
        plan_before = (repo / REL).read_bytes()
        store_before = _store_bytes(repo)
        rc, out, _err = _run(repo, capsys, REL, "--remove-block")
        assert rc == 0
        assert "would write 2 chunk-imported fact(s)" in out
        assert "would write: chunk 01" in out and "would write: chunk 03" in out
        assert "chunk 02" not in out
        assert "would remove the `## Status` block" in out
        assert (repo / REL).read_bytes() == plan_before
        assert _store_bytes(repo) == store_before

    def test_apply_writes_one_fact_per_ticked_box_and_keeps_the_block(self, tmp_path, capsys):
        repo = _repo(tmp_path, _HEAD + _STATUS + _TAIL)
        plan_before = (repo / REL).read_bytes()
        before = plan_status.chunk_states(repo / REL, evidence.read_facts(repo), repo_dir=repo)

        rc, out, _err = _run(repo, capsys, REL, "--apply")

        assert rc == 0, out
        facts = _imports(repo)
        assert [f["body"]["chunk"] for f in facts] == ["01", "03"]
        for fact in facts:
            assert set(fact["body"]) == {"scope", "chunk", "source", "imported_at"}
            assert fact["body"]["scope"] == "unit" and fact["body"]["source"] == "status-box"
        assert (repo / REL).read_bytes() == plan_before
        assert "`## Status` block kept" in out
        # The answer moved, it did not change: same states, now citing facts.
        after = plan_status.chunk_states(repo / REL, evidence.read_facts(repo), repo_dir=repo)
        assert {k: s.state for k, s in after.items()} == {k: s.state for k, s in before.items()}
        assert [after[k].fact_id for k in ("01", "03")] == [f["id"] for f in facts]
        assert after["02"].state == "open"

    def test_a_rerun_writes_nothing_again(self, tmp_path, capsys):
        repo = _repo(tmp_path, _HEAD + _STATUS + _TAIL)
        assert _run(repo, capsys, REL, "--apply")[0] == 0
        rc, out, _err = _run(repo, capsys, REL, "--apply")
        assert rc == 0
        assert len(_imports(repo)) == 2
        assert "wrote 0 chunk-imported fact(s)" in out
        assert out.count("already imported:") == 2

    def test_the_json_envelope(self, tmp_path, capsys):
        repo = _repo(tmp_path, _HEAD + _STATUS + _TAIL)
        rc, out, _err = _run(repo, capsys, REL, "--json")
        assert rc == 0
        payload = json.loads(out)
        assert payload["status"] == "ok" and payload["apply"] is False
        assert payload["plan_path"] == REL and payload["scope"] == "unit"
        assert [(f["chunk"], f["action"]) for f in payload["facts"]] == [
            ("01", "would-write"), ("03", "would-write"),
        ]
        assert payload["block"] == {"action": "kept", "lines": None}


class TestRemoveBlock:
    def test_it_removes_exactly_the_block_and_nothing_else(self, tmp_path, capsys):
        repo = _repo(tmp_path, _HEAD + _STATUS + _TAIL)
        rc, out, _err = _run(repo, capsys, REL, "--apply", "--remove-block")
        assert rc == 0, out
        assert (repo / REL).read_text() == _HEAD + _TAIL
        assert len(_imports(repo)) == 2
        # After the block is gone the facts carry the answer the boxes gave.
        states = plan_status.chunk_states(repo / REL, evidence.read_facts(repo), repo_dir=repo)
        assert {k: s.state for k, s in states.items()} == {"01": "done", "02": "open", "03": "done"}

    def test_crlf_line_endings_survive(self, tmp_path, capsys):
        repo = _repo(tmp_path, _HEAD + _STATUS + _TAIL, newline="\r\n")
        rc, out, _err = _run(repo, capsys, REL, "--apply", "--remove-block")
        assert rc == 0, out
        assert (repo / REL).read_bytes() == (_HEAD + _TAIL).replace("\n", "\r\n").encode("utf-8")

    def test_a_header_comment_above_the_block_survives(self, tmp_path, capsys):
        """No walk-back: a banner comment directly above `## Status` is not the
        block's, and the only span deleted starts at the heading."""
        banner = "<!-- hand-written: this plan's history lives in the change record -->\n"
        repo = _repo(tmp_path, _HEAD + banner + _STATUS + _TAIL)
        rc, out, _err = _run(repo, capsys, REL, "--apply", "--remove-block")
        assert rc == 0, out
        assert (repo / REL).read_text() == _HEAD + banner + _TAIL

    @pytest.mark.parametrize(
        "plan, code",
        [
            (_HEAD + _STATUS, "status-block-undelimited"),  # runs to end of file
            (_HEAD + _STATUS.replace("Context:", "```\n## Not a heading\n```\nContext:") + _TAIL,
             "status-block-undelimited"),  # a fence inside the span
            (_HEAD + _STATUS + "<!-- never closes\n\n" + _TAIL, "status-block-undelimited"),
            (_HEAD + _STATUS + "<!-- banner for the next section -->\n\n" + _TAIL,
             "status-block-trailing-comment"),
            (_HEAD + _STATUS + "```\n## Status\n```\n\n" + _TAIL, "status-block-ambiguous"),
        ],
        ids=["to-eof", "fence", "unclosed-comment", "trailing-banner", "duplicate-heading"],
    )
    def test_an_undelimitable_block_is_refused_and_nothing_is_written(
        self, tmp_path, capsys, plan, code
    ):
        repo = _repo(tmp_path, plan)
        plan_before = (repo / REL).read_bytes()
        store_before = _store_bytes(repo)
        rc, _out, err = _run(repo, capsys, REL, "--apply", "--remove-block")
        assert rc == 1
        assert f"refused: {code}:" in err
        assert (repo / REL).read_bytes() == plan_before
        assert _store_bytes(repo) == store_before  # refused BEFORE any fact

    def test_the_same_plan_imports_fine_without_remove_block(self, tmp_path, capsys):
        """Control for the refusals: they are about deleting, not importing."""
        repo = _repo(tmp_path, _HEAD + _STATUS)
        rc, out, _err = _run(repo, capsys, REL, "--apply")
        assert rc == 0, out
        assert len(_imports(repo)) == 2

    def test_no_block_to_remove_is_said_and_succeeds(self, tmp_path, capsys):
        repo = _repo(tmp_path, _HEAD + _TAIL)
        rc, out, _err = _run(repo, capsys, REL, "--apply", "--remove-block")
        assert rc == 0
        assert "no `## Status` block to remove" in out
        assert _imports(repo) == []


class TestRefusals:
    def test_no_scope(self, tmp_path, capsys):
        repo = _repo(tmp_path, (_HEAD + _STATUS + _TAIL).replace("scope: unit\n", ""))
        rc, _out, err = _run(repo, capsys, REL, "--apply")
        assert rc == 1 and "refused: no-scope:" in err
        assert _imports(repo) == []

    def test_an_archived_plan(self, tmp_path, capsys):
        repo = _repo(tmp_path, _HEAD + _STATUS + _TAIL)
        archived = repo / ".prawduct" / "artifacts" / "archive" / "build-plan-unit.md"
        archived.parent.mkdir()
        (repo / REL).rename(archived)
        rc, _out, err = _run(repo, capsys, ".prawduct/artifacts/archive/build-plan-unit.md", "--apply")
        assert rc == 1 and "refused: archived-plan:" in err
        assert _imports(repo) == []

    def test_an_append_failure_is_refused_and_the_block_stays(self, tmp_path, capsys, monkeypatch):
        """Without the kind admitted the writer refuses it — the state before
        Chunk 02 — and a block must never be removed with a fact missing."""
        monkeypatch.setattr(evidence, "KNOWN_KINDS", evidence.KNOWN_KINDS - {plan_status.IMPORTED_KIND})
        repo = _repo(tmp_path, _HEAD + _STATUS + _TAIL)
        plan_before = (repo / REL).read_bytes()
        rc, _out, err = _run(repo, capsys, REL, "--apply", "--remove-block")
        assert rc == 1
        assert "refused: fact-append-failed: chunk 01" in err
        assert "block was NOT removed" in err
        assert (repo / REL).read_bytes() == plan_before

    @pytest.mark.parametrize(
        "argv",
        [[], ["a.md", "b.md"], [REL, "--bogus"], ["missing.md"], [".prawduct/notes.md"]],
        ids=["no-path", "two-paths", "unknown-flag", "unreadable", "not-a-plan"],
    )
    def test_usage_errors_exit_2(self, tmp_path, capsys, argv):
        repo = _repo(tmp_path, _HEAD + _STATUS + _TAIL)
        (repo / ".prawduct" / "notes.md").write_text("---\nartifact: product-brief\n---\n\n# Notes\n")
        rc, _out, _err = _run(repo, capsys, *argv)
        assert rc == 2


def test_this_repos_own_plan_previews_its_ticked_chunks(capsys):
    """The real artifact: the live chunk-status plan previews as importable. Its
    block must delimit, since Chunk 06 removes it with `--remove-block`. The
    preview writes nothing, so this reads the real repo safely. It names which
    emptiness it rejects: a plan with no ticked box yet previews 0 facts and
    still delimits."""
    repo = ROOT.parent
    rel = ".prawduct/artifacts/build-plan-chunk-status.md"
    if not (repo / rel).is_file():
        pytest.skip("the chunk-status plan has been archived")
    rc, out, err = _run(repo, capsys, rel, "--remove-block", "--json")
    assert rc == 0, err
    payload = json.loads(out)
    assert payload["block"]["action"] in ("would-remove", "absent"), payload
    assert all(f["action"] in ("would-write", "already-imported") for f in payload["facts"])
