"""``prawduct-hook plan new|bind|resolve`` — the CLI over ``lib.plan_mint`` and
``lib.work_unit`` (#1050 Chunk 06).

Driven through the real binary: the subject is what the operator's command does
— its exit code on each binding state, its refusal conventions, and the
ephemeral-worktree guard's verdict (``resolve`` is a read, ``new``/``bind`` are
writes). ``lib.plan_mint``'s own refusals are pinned in ``test_plan_mint.py``;
these pin that each reaches the CLI as a stable ``refused: <code>:`` at exit 1.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import work_unit  # noqa: E402


def _env(repo: Path) -> dict[str, str]:
    home = repo.parent / "_home"  # outside the repo: macOS pyc caches land under HOME
    home.mkdir(exist_ok=True)
    return {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
        "CLAUDE_PROJECT_DIR": str(repo),
    }


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True,
        env=_env(repo), check=True, timeout=10,
    )


def _repo(tmp_path: Path, branch: str = "feature/unit") -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-qm", "seed")
    if branch != "main":
        _git(repo, "checkout", "-q", "-b", branch)
    (repo / ".prawduct" / "artifacts").mkdir(parents=True)
    (repo / ".prawduct" / "project-state.yaml").write_text("")
    return repo.resolve()


def _plan(repo: Path, rel: str, frontmatter: str) -> Path:
    path = repo / ".prawduct" / "artifacts" / rel
    path.write_text(
        f"---\nartifact: build-plan\n{frontmatter}---\n\n# Build Plan\n\n"
        "## Status\n\n- [ ] Chunk 01: open\n"
    )
    return path


def _run(cwd: Path, *args: str, env_repo: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK), "plan", *args],
        cwd=str(cwd), capture_output=True, text=True, timeout=60,
        env=_env(env_repo or cwd),
    )


class TestResolve:
    def test_bound_prints_the_plan_and_exits_0(self, tmp_path):
        repo = _repo(tmp_path)
        _plan(repo, "build-plan-unit.md", "scope: unit\nbranch: feature/unit\n")
        proc = _run(repo, "resolve")
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.splitlines()[0] == (
            "bound: .prawduct/artifacts/build-plan-unit.md "
            "(scope `unit`, integration branch; chosen by binding)"
        )

    def test_json_carries_every_binding_field(self, tmp_path):
        repo = _repo(tmp_path)
        _plan(repo, "build-plan-unit.md", "scope: unit\nbranch: feature/unit\nbase: feature/a\n")
        proc = _run(repo, "resolve", "--json")
        assert proc.returncode == 0, proc.stderr
        data = json.loads(proc.stdout)
        assert data == {
            "state": "bound",
            "scope": "unit",
            "plan_path": ".prawduct/artifacts/build-plan-unit.md",
            "role": "integration",
            "reason": None,
            "chosen_by": "binding",
            "claimants": [".prawduct/artifacts/build-plan-unit.md"],
            "case": "claim",
            "base": "feature/a",
        }
        # The key set is the Binding's field set — a field added there without
        # reaching the JSON fails here.
        from dataclasses import fields
        assert set(data) == {f.name for f in fields(work_unit.Binding)}

    def test_unbound_is_an_answer_and_exits_0(self, tmp_path):
        repo = _repo(tmp_path, "chore/bump")
        _plan(repo, "build-plan-unit.md", "scope: unit\nbranch: feature/unit\n")
        proc = _run(repo, "resolve")
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.splitlines() == [
            "unbound: no plan governs this checkout",
            "  no live plan claims `chore/bump`",
        ]

    def test_broken_exits_1_and_names_the_claimants(self, tmp_path):
        repo = _repo(tmp_path)
        _plan(repo, "build-plan-a.md", "scope: a\nbranch: feature/unit\n")
        _plan(repo, "build-plan-b.md", "scope: b\nbranch: feature/unit\n")
        proc = _run(repo, "resolve", "--json")
        assert proc.returncode == 1, proc.stdout
        data = json.loads(proc.stdout)
        assert (data["state"], data["case"], data["base"]) == ("broken", "two-claimants", None)
        assert data["claimants"] == [
            ".prawduct/artifacts/build-plan-a.md", ".prawduct/artifacts/build-plan-b.md",
        ]
        human = _run(repo, "resolve")
        assert human.returncode == 1
        assert human.stdout.startswith("broken: no binding can be decided")

    def test_it_runs_in_a_scratch_worktree_where_the_writers_are_refused(self, tmp_path):
        """`resolve` is a read, so the ephemeral guard lets it through — a
        delegate asking why its tree is unbound gets the answer. `bind` and
        `new` write a plan that dies with the tree, and are refused."""
        repo = _repo(tmp_path)
        _plan(repo, "build-plan-unit.md", "scope: unit\nbranch: feature/unit\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "plan")
        wid = "a287823214767feaa"
        scratch = repo / ".claude" / "worktrees" / f"agent-{wid}"
        scratch.parent.mkdir(parents=True)
        _git(repo, "worktree", "add", "-q", "-b", f"worktree-agent-{wid}", str(scratch), "HEAD")

        proc = _run(scratch, "resolve", "--json")
        assert proc.returncode == 0, proc.stderr
        assert json.loads(proc.stdout)["state"] == "unbound"
        assert "scratch worktree" in json.loads(proc.stdout)["reason"]

        for argv in (
            ("bind", ".prawduct/artifacts/build-plan-unit.md", "--branch", "feature/x"),
            ("new", "another", "--branch", "feature/another"),
        ):
            refused = _run(scratch, *argv)
            assert refused.returncode == 1, argv
            assert "BLOCKED: refusing `plan`" in refused.stderr, argv


def _status_plan(repo: Path) -> Path:
    """Three chunks: 01 ticked (in-memory import), 02 certified by a review
    fact, 03 dropped with a reason — every row shape the table renders."""
    path = repo / ".prawduct" / "artifacts" / "build-plan-unit.md"
    path.write_text(
        "---\nartifact: build-plan\nscope: unit\nbranch: feature/unit\nbase: main\n"
        "dropped:\n  - 03: folded into 02\n---\n\n# Build Plan\n\n"
        "## Status\n\n- [x] Chunk 01: one\n- [ ] Chunk 02: two\n- [ ] Chunk 03: three\n\n"
        "## Build Chunks\n\n"
        "### Chunk 01: one\n\n- **Deliverables:** `src/one.py`\n\n"
        "### Chunk 02: two\n\n- **Deliverables:** `src/two.py`\n\n"
        "### Chunk 03: three\n\n- **Deliverables:** `src/three.py`\n"
    )
    return path


def _status_fixture(repo: Path) -> Path:
    plan = _status_plan(repo)
    (repo / "src").mkdir()
    (repo / "src" / "two.py").write_text("x\n")
    _git(repo, "add", "src/two.py")
    _git(repo, "commit", "-qm", "feat(unit): the second (Chunk 02)")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    store = repo / ".git" / "prawduct" / "evidence.jsonl"
    store.parent.mkdir(parents=True)
    store.write_text(json.dumps({
        "schema": 1, "kind": "review", "id": "R-two", "ts": "2026-10-25T10:00:00Z",
        "actor": {}, "body": {
            "scope": "unit", "chunks": ["02"], "chunk": "02", "mode": "chunk",
            "head_commit": head, "findings": [], "counts": {"blocking": 0},
        },
    }) + "\n")
    return plan


class TestStatus:
    def test_json_carries_the_plan_and_every_chunk_field(self, tmp_path):
        repo = _repo(tmp_path)
        _status_fixture(repo)
        proc = _run(repo, "status", "--json")
        assert proc.returncode == 0, proc.stderr
        data = json.loads(proc.stdout)
        assert set(data) == {"plan_path", "scope", "finished", "chunks"}
        assert (data["plan_path"], data["scope"], data["finished"]) == (
            ".prawduct/artifacts/build-plan-unit.md", "unit", True,
        )
        assert data["chunks"] == [
            {"id": "01", "state": "done", "fact_id": None, "date": None,
             "imported": True, "built": False, "reason": None},
            {"id": "02", "state": "done", "fact_id": "R-two", "date": "2026-10-25",
             "imported": False, "built": True, "reason": None},
            {"id": "03", "state": "dropped", "fact_id": None, "date": None,
             "imported": False, "built": False, "reason": "folded into 02"},
        ]

    def test_the_human_table_renders_every_row_shape(self, tmp_path):
        repo = _repo(tmp_path)
        _status_fixture(repo)
        proc = _run(repo, "status", ".prawduct/artifacts/build-plan-unit.md")
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.splitlines() == [
            ".prawduct/artifacts/build-plan-unit.md (scope `unit`): finished (3 chunks)",
            "  chunk  state    fact   date        tags",
            "  01     done     -      -           imported",
            "  02     done     R-two  2026-10-25  built",
            "  03     dropped  -      -           -",
            "      folded into 02",
        ]

    def test_an_unfinished_plan_counts_its_open_chunks(self, tmp_path):
        """Control for the summary line: with no fact, 02 is open."""
        repo = _repo(tmp_path)
        _status_plan(repo)
        proc = _run(repo, "status")
        assert proc.returncode == 0, proc.stderr
        lines = proc.stdout.splitlines()
        assert lines[0] == ".prawduct/artifacts/build-plan-unit.md (scope `unit`): 1 of 3 open"
        assert lines[3] == "  02     open     -     -     -"

    def test_unbound_with_no_path_exits_1_with_the_reason(self, tmp_path):
        repo = _repo(tmp_path, "chore/bump")
        _status_plan(repo)
        proc = _run(repo, "status")
        assert proc.returncode == 1, proc.stdout
        assert proc.stdout == ""
        assert proc.stderr.splitlines() == [
            "plan status: unbound: no plan resolves for this checkout — "
            "no live plan claims `chore/bump`; name one"
        ]
        # A path answers on any checkout.
        named = _run(repo, "status", ".prawduct/artifacts/build-plan-unit.md")
        assert named.returncode == 0, named.stderr

    @pytest.mark.parametrize("rel", ["missing.md", "notes.md"])
    def test_a_path_that_is_not_a_build_plan_is_a_usage_error(self, tmp_path, rel):
        repo = _repo(tmp_path)
        # Declared some other artifact; a file declaring none counts as a plan.
        (repo / "notes.md").write_text("---\nartifact: architecture\n---\n\n# Notes\n")
        proc = _run(repo, "status", rel)
        assert proc.returncode == 2, proc.stdout
        assert proc.stderr.startswith(f"plan status: {'cannot read' if rel == 'missing.md' else 'notes.md is not a build plan'}")
        assert "usage: prawduct-hook plan" in proc.stderr

    def test_it_runs_in_a_scratch_worktree(self, tmp_path):
        """`status` is a read: the ephemeral guard admits it. A scratch tree is
        unbound, so it needs a path; given one, it answers."""
        repo = _repo(tmp_path)
        _status_plan(repo)
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "plan")
        wid = "a287823214767feab"
        scratch = repo / ".claude" / "worktrees" / f"agent-{wid}"
        scratch.parent.mkdir(parents=True)
        _git(repo, "worktree", "add", "-q", "-b", f"worktree-agent-{wid}", str(scratch), "HEAD")
        proc = _run(scratch, "status", ".prawduct/artifacts/build-plan-unit.md", "--json")
        assert proc.returncode == 0, proc.stderr
        assert [c["state"] for c in json.loads(proc.stdout)["chunks"]] == ["done", "open", "dropped"]
        unbound = _run(scratch, "status")
        assert unbound.returncode == 1
        assert "BLOCKED" not in unbound.stderr
        # The guard's scratch-tree NOTE precedes the command's own one line.
        assert unbound.stderr.splitlines()[-1].startswith("plan status: unbound:")


class TestNew:
    def test_new_mints_a_plan_the_binding_reads(self, tmp_path):
        repo = _repo(tmp_path)
        proc = _run(repo, "new", "unit", "--title", "The unit")
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.startswith("minted: unit `unit` — .prawduct/artifacts/build-plan-unit.md claims `feature/unit`")
        assert (repo / ".prawduct" / "changes" / "unit.md").is_file()
        binding = work_unit.resolve(repo)
        assert (binding.state, binding.scope, binding.chosen_by) == ("bound", "unit", "binding")

    def test_a_refusal_is_exit_1_with_its_code_and_writes_nothing(self, tmp_path):
        repo = _repo(tmp_path)
        _plan(repo, "build-plan-unit.md", "scope: unit\nbranch: feature/other\n")
        before = sorted(p.name for p in (repo / ".prawduct").rglob("*"))
        proc = _run(repo, "new", "unit")
        assert proc.returncode == 1, proc.stdout
        assert proc.stderr.startswith("refused: scope-taken: "), proc.stderr
        assert sorted(p.name for p in (repo / ".prawduct").rglob("*")) == before

    def test_working_takes_only_branch(self, tmp_path):
        repo = _repo(tmp_path)
        proc = _run(repo, "new", "unit", "--working", "--base", "develop")
        assert proc.returncode == 2
        assert "--base does not apply" in proc.stderr

    def test_working_joins_a_bound_unit(self, tmp_path):
        repo = _repo(tmp_path, "feature/unit-delegate")
        _plan(repo, "build-plan-unit.md", "scope: unit\nbranch: feature/unit\n")
        proc = _run(repo, "new", "unit", "--working")
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.startswith("working: `feature/unit-delegate` joins unit `unit`")
        assert work_unit.resolve(repo).role == "working"
        again = _run(repo, "new", "unit", "--working")
        assert (again.returncode, again.stdout.split(":")[0]) == (0, "unchanged")

    def test_an_omitted_scope_is_suggested_from_the_branch_and_printed(self, tmp_path):
        """R-1: `plan_mint.suggest_scope`'s one consumer. The kind prefix and the
        issue number are dropped, the slug is printed before the mint line so the
        identity used is on screen, and the plan the binding reads carries it."""
        repo = _repo(tmp_path, "feature/1050-the-unit")
        proc = _run(repo, "new")
        assert proc.returncode == 0, proc.stderr
        lines = proc.stdout.splitlines()
        assert lines[0] == "scope the-unit suggested from branch feature/1050-the-unit"
        assert lines[1].startswith("minted: unit `the-unit` — .prawduct/artifacts/build-plan-the-unit.md")
        binding = work_unit.resolve(repo)
        assert (binding.state, binding.scope, binding.case) == ("bound", "the-unit", "claim")

    def test_an_omitted_scope_is_suggested_from_the_branch_being_created(self, tmp_path):
        repo = _repo(tmp_path, "main")
        proc = _run(repo, "new", "--branch", "fix/other-thing")
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.splitlines()[0] == "scope other-thing suggested from branch fix/other-thing"
        assert (repo / ".prawduct" / "artifacts" / "build-plan-other-thing.md").is_file()

    def test_a_branch_that_suggests_nothing_is_refused_and_writes_nothing(self, tmp_path):
        """The integration line is never a unit's, so `main` suggests nothing:
        refused at exit 1 with a stable code, nothing written — never a mint
        under a guessed name."""
        repo = _repo(tmp_path, "main")
        proc = _run(repo, "new")
        assert proc.returncode == 1, proc.stdout
        assert proc.stderr.startswith("refused: no-scope-suggestion: branch `main`"), proc.stderr
        assert proc.stdout == ""
        assert list((repo / ".prawduct" / "artifacts").iterdir()) == []
        assert not (repo / ".prawduct" / "changes").exists()

    @pytest.mark.parametrize(
        "argv",
        [
            ("new", "--working"),
            ("new", "a", "b"),
            ("new", "a", "--branch"),
            ("new", "a", "--bogus"),
            ("bind", "plan.md"),
            ("bind", "--branch", "x"),
            ("resolve", "extra"),
            ("status", "a.md", "b.md"),
            ("status", "--bogus"),
            ("nope",),
            (),
        ],
    )
    def test_a_malformed_invocation_is_a_usage_error_and_runs_nothing(self, tmp_path, argv):
        repo = _repo(tmp_path)
        proc = _run(repo, *argv)
        assert proc.returncode == 2, (argv, proc.stdout, proc.stderr)
        assert "usage: prawduct-hook plan" in proc.stderr
        assert not (repo / ".prawduct" / "changes").exists()


class TestBind:
    def test_bind_claims_the_branch_then_is_idempotent(self, tmp_path):
        repo = _repo(tmp_path)
        _plan(repo, "build-plan.md", "scope: lonely\n")
        assert work_unit.resolve(repo).chosen_by == "legacy-default"
        proc = _run(repo, "bind", "build-plan.md", "--branch", "feature/unit")
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout == "bound: .prawduct/artifacts/build-plan.md claims `feature/unit`\n"
        assert work_unit.resolve(repo).chosen_by == "binding"
        again = _run(repo, "bind", "build-plan.md", "--branch", "feature/unit")
        assert again.returncode == 0
        assert again.stdout.startswith("unchanged: ")

    def test_bind_never_repoints_an_existing_claim(self, tmp_path):
        repo = _repo(tmp_path)
        plan = _plan(repo, "build-plan.md", "scope: lonely\nbranch: feature/elsewhere\n")
        before = plan.read_text()
        proc = _run(repo, "bind", "build-plan.md", "--branch", "feature/unit")
        assert proc.returncode == 1
        assert proc.stderr.startswith("refused: plan-claims-other-branch: ")
        assert plan.read_text() == before
