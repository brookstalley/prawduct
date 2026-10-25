"""The diff base a checkout is measured against reads the bound plan's ``base:``
first (#1050, R-13).

git records no parent for a branch, so a stacked unit — ``feature/b`` cut from
``feature/a`` — is knowable only from its plan. ``coverage._resolve_base_branch``
is the one base resolver every gate, the PR payload and ``prawduct-hook
resolve-base`` share; these pin that a bound plan's ``base:`` steers it, and
that every checkout the plan does not govern keeps the answer it had.

Driven both at the library and through ``resolve-base``, the command the PR
skill runs, so the wiring is pinned at the layer the finding was reported at.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import coverage  # noqa: E402


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
        "CLAUDE_PLUGIN_ROOT": str(ROOT),
    }


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True,
        env=_env(repo), check=True, timeout=10,
    )


def _stacked_repo(tmp_path: Path, *, base_line: str, checkout: str = "feature/b",
                  working: str = "[]") -> Path:
    """``main`` → ``feature/a`` → ``feature/b``, with ``feature/b``'s plan
    carrying ``base_line`` and checked out on ``checkout``."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-qm", "seed")
    _git(repo, "checkout", "-q", "-b", "feature/a")
    (repo / "a.txt").write_text("a\n")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-qm", "a")
    _git(repo, "checkout", "-q", "-b", "feature/b")
    artifacts = repo / ".prawduct" / "artifacts"
    artifacts.mkdir(parents=True)
    (repo / ".prawduct" / "project-state.yaml").write_text("")
    (artifacts / "build-plan-b.md").write_text(
        f"---\nartifact: build-plan\nscope: b\nbranch: feature/b\n{base_line}"
        f"working-branches: {working}\n---\n\n## Status\n\n- [ ] Chunk 01: x\n"
    )
    if checkout != "feature/b":
        _git(repo, "checkout", "-q", "-b", checkout)
    return repo.resolve()


def _resolve_base_cli(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK), "resolve-base"], cwd=str(repo),
        capture_output=True, text=True, timeout=60, env=_env(repo),
    )


class TestThePlansBaseSteersTheResolver:
    def test_a_stacked_unit_resolves_to_its_plans_base(self, tmp_path):
        repo = _stacked_repo(tmp_path, base_line="base: feature/a\n")
        assert coverage._resolve_base_branch(repo) == ("feature/a", "feature/a")
        cli = _resolve_base_cli(repo)
        assert (cli.returncode, cli.stdout.strip()) == (0, "feature/a"), cli.stderr

    def test_the_remote_tracking_ref_is_preferred_as_for_the_repo_base(self, tmp_path):
        repo = _stacked_repo(tmp_path, base_line="base: feature/a\n")
        _git(repo, "update-ref", "refs/remotes/origin/feature/a", "feature/a")
        assert coverage._resolve_base_branch(repo)[0] == "origin/feature/a"

    def test_no_base_declared_is_the_repo_answer_unchanged(self, tmp_path):
        """The control: the same stacked repo with no ``base:`` resolves exactly
        what ``repo_base_branch`` does — the main line, not feature/a."""
        repo = _stacked_repo(tmp_path, base_line="")
        assert coverage._resolve_base_branch(repo) == coverage.repo_base_branch(repo)
        assert coverage._resolve_base_branch(repo)[0] == "main"
        assert _resolve_base_cli(repo).stdout.strip() == "main"

    def test_a_base_no_ref_resolves_falls_through_to_the_repo_answer(self, tmp_path):
        """A merged-and-deleted base is the ordinary way here; the repo's
        integration line is then the right base, not a failed resolution."""
        repo = _stacked_repo(tmp_path, base_line="base: feature/gone\n")
        assert coverage._resolve_base_branch(repo) == ("main", "main")

    def test_an_unbound_checkout_ignores_every_plans_base(self, tmp_path):
        repo = _stacked_repo(tmp_path, base_line="base: feature/a\n", checkout="chore/x")
        assert coverage._resolve_base_branch(repo)[0] == "main"

    def test_a_working_branch_keeps_the_repo_answer(self, tmp_path):
        """A working branch merges into its unit's integration branch, never the
        unit's base, so the unit's ``base:`` is not its base."""
        repo = _stacked_repo(
            tmp_path, base_line="base: feature/a\n", checkout="feature/b-wip",
            working="[feature/b-wip]",
        )
        from lib import work_unit

        assert work_unit.resolve(repo).role == "working"
        assert coverage._resolve_base_branch(repo)[0] == "main"

    def test_the_plans_base_outranks_the_repo_knob(self, tmp_path):
        """``base_branch:`` is the repo's integration line; the unit's own base is
        more specific and wins for the checkout it governs."""
        repo = _stacked_repo(tmp_path, base_line="base: feature/a\n")
        (repo / ".prawduct" / "project-state.yaml").write_text("base_branch: main\n")
        assert coverage._resolve_base_branch(repo)[0] == "feature/a"
        assert coverage.repo_base_branch(repo)[0] == "main"
