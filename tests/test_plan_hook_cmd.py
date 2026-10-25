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
        _plan(repo, "build-plan-unit.md", "scope: unit\nbranch: feature/unit\n")
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
        assert data["state"] == "broken"
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

    @pytest.mark.parametrize(
        "argv",
        [
            ("new",),
            ("new", "a", "b"),
            ("new", "a", "--branch"),
            ("new", "a", "--bogus"),
            ("bind", "plan.md"),
            ("bind", "--branch", "x"),
            ("resolve", "extra"),
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
