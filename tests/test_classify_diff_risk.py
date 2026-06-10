"""Tests for `prawduct-hook classify-diff-risk` (review-proportionality ch.04).

The classifier picks the reviewer tier for final/cumulative/PR reviews, so its
load-bearing branches are the asymmetric failure rules: fail-OPEN to
`standard` only when no surfaces are declared; fail-CLOSED to `escalate` when
surfaces are declared but the diff can't be evaluated — declared risk with an
unverifiable diff must never silently get the cheap reviewer.

Resolution order pinned here: an explicit `risk_surfaces:` list in
project-state.yaml is EXCLUSIVE (derived defaults stop applying; an empty
list is a deliberate opt-out); without it, the derived defaults (`skills/`,
`lib/gates*`, `bin/*hook*`) plus literal backticked paths from
boundary-patterns.md apply.

Real git repos, sterile env (HOME outside the repo — pyc-cache learning),
mirroring tests/test_governance_ledger.py.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "bin" / "prawduct-hook"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.risk import (  # noqa: E402
    DERIVED_DEFAULT_SURFACES,
    _read_list_yaml_key,
    _surface_matches,
)


def _git_env(repo: Path) -> dict[str, str]:
    home = repo.parent / "_home"
    home.mkdir(exist_ok=True)
    return {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True,
        env=_git_env(repo), check=True, timeout=10,
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    (repo / ".prawduct").mkdir()
    _git(repo, "init", "--quiet", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")


def _commit_file(repo: Path, rel: str, content: str, msg: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    _git(repo, "add", rel)
    _git(repo, "commit", "-m", msg, "--quiet")


def _feature_repo(repo: Path) -> None:
    """Repo on a feature branch with one base commit on main."""
    _init_repo(repo)
    _commit_file(repo, "README.md", "x\n", "init")
    _git(repo, "checkout", "-q", "-b", "feature")


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(_git_env(repo))
    env["CLAUDE_PROJECT_DIR"] = str(repo)
    return subprocess.run(
        ["python3", str(HOOK), "classify-diff-risk", *args],
        cwd=str(repo), capture_output=True, text=True, env=env, timeout=30,
    )


def _declare_surfaces(repo: Path, yaml_block: str) -> None:
    (repo / ".prawduct" / "project-state.yaml").write_text(yaml_block)


class TestSurfaceMatching:
    """Pattern semantics: trailing `/` = directory prefix; else fnmatch glob
    (no metacharacters = exact path)."""

    def test_directory_prefix(self):
        assert _surface_matches("skills/critic/SKILL.md", "skills/")
        assert not _surface_matches("myskills/x.md", "skills/")

    def test_glob(self):
        assert _surface_matches("lib/gates.py", "lib/gates*")
        assert _surface_matches("bin/prawduct-hook", "bin/*hook*")
        assert not _surface_matches("lib/gitstate.py", "lib/gates*")

    def test_exact_path(self):
        assert _surface_matches("src/api/contract.py", "src/api/contract.py")
        assert not _surface_matches("src/api/contract.pyc", "src/api/contract.py")

    def test_derived_defaults_are_framework_governance_paths(self):
        assert DERIVED_DEFAULT_SURFACES == ("skills/", "lib/gates*", "bin/*hook*")


class TestRiskSurfacesYamlList:
    """`_read_list_yaml_key` distinguishes undeclared (None) from
    declared-but-empty ([]) — the branch point of the failure asymmetry."""

    def test_absent_key_is_none(self, tmp_path):
        state = tmp_path / "project-state.yaml"
        state.write_text("base_branch: develop\n")
        assert _read_list_yaml_key(state, "risk_surfaces") is None

    def test_missing_file_is_none(self, tmp_path):
        assert _read_list_yaml_key(tmp_path / "absent.yaml", "risk_surfaces") is None

    def test_inline_empty_list(self, tmp_path):
        state = tmp_path / "project-state.yaml"
        state.write_text("risk_surfaces: []\n")
        assert _read_list_yaml_key(state, "risk_surfaces") == []

    def test_block_list_with_comments_and_quotes(self, tmp_path):
        state = tmp_path / "project-state.yaml"
        state.write_text(
            "views_enabled: true\n"
            "risk_surfaces:  # governance hot spots\n"
            "  - 'src/core/'\n"
            "  - src/api/contract.py  # the shared shape\n"
            "next_key: x\n"
        )
        assert _read_list_yaml_key(state, "risk_surfaces") == [
            "src/core/", "src/api/contract.py",
        ]

    def test_indented_same_name_key_ignored(self, tmp_path):
        state = tmp_path / "project-state.yaml"
        state.write_text("nested:\n  risk_surfaces:\n    - a/\n")
        assert _read_list_yaml_key(state, "risk_surfaces") is None


class TestDerivedDefaults:
    def test_governance_path_escalates(self, tmp_path):
        repo = tmp_path / "repo"
        _feature_repo(repo)
        _commit_file(repo, "lib/gates.py", "x = 1\n", "touch gate")
        result = _run(repo, "main")
        assert result.returncode == 0
        assert result.stdout.strip() == "escalate"
        assert "lib/gates.py matched lib/gates*" in result.stderr

    def test_non_risk_diff_is_standard(self, tmp_path):
        repo = tmp_path / "repo"
        _feature_repo(repo)
        _commit_file(repo, "src/app.py", "x = 1\n", "app change")
        result = _run(repo, "main")
        assert result.returncode == 0
        assert result.stdout.strip() == "standard"

    def test_uncommitted_work_counts(self, tmp_path):
        # A final review covers uncommitted work — an untracked file on a
        # risk surface must escalate even with a clean committed diff.
        repo = tmp_path / "repo"
        _feature_repo(repo)
        (repo / "skills").mkdir()
        (repo / "skills" / "new.md").write_text("draft\n")
        result = _run(repo, "main")
        assert result.stdout.strip() == "escalate"
        assert "skills/new.md matched skills/" in result.stderr

    def test_hook_glob_matches(self, tmp_path):
        repo = tmp_path / "repo"
        _feature_repo(repo)
        _commit_file(repo, "bin/prawduct-hook", "#!/usr/bin/env python3\n", "hook")
        result = _run(repo, "main")
        assert result.stdout.strip() == "escalate"


class TestExplicitDeclarationIsExclusive:
    def test_declared_list_beats_defaults(self, tmp_path):
        # skills/ is a derived default, but the explicit list replaces the
        # defaults entirely — only docs/ escalates now.
        repo = tmp_path / "repo"
        _feature_repo(repo)
        _declare_surfaces(repo, "risk_surfaces:\n  - docs/\n")
        _commit_file(repo, "skills/x.md", "x\n", "skill change")
        assert _run(repo, "main").stdout.strip() == "standard"
        _commit_file(repo, "docs/risky.md", "x\n", "doc change")
        result = _run(repo, "main")
        assert result.stdout.strip() == "escalate"
        assert "docs/risky.md matched docs/" in result.stderr

    def test_declared_empty_is_an_opt_out(self, tmp_path):
        repo = tmp_path / "repo"
        _feature_repo(repo)
        _declare_surfaces(repo, "risk_surfaces: []\n")
        _commit_file(repo, "lib/gates.py", "x\n", "gate change")
        result = _run(repo, "main")
        assert result.returncode == 0
        assert result.stdout.strip() == "standard"
        assert "declared empty" in result.stderr


class TestBoundaryPatternsSurfaces:
    def test_backticked_contract_path_escalates(self, tmp_path):
        repo = tmp_path / "repo"
        _feature_repo(repo)
        artifacts = repo / ".prawduct" / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "boundary-patterns.md").write_text(
            "## Contract Surfaces\n"
            "Producer: `src/api/contract.py` defines the shape.\n"
            "Glob in prose: `docs/*.md` (named set, not a surface).\n"
            "Slash-command: `/prawduct:pr` (not a path).\n"
        )
        _commit_file(repo, "src/api/contract.py", "x\n", "contract change")
        result = _run(repo, "main")
        assert result.stdout.strip() == "escalate"
        assert "src/api/contract.py matched src/api/contract.py" in result.stderr

    def test_glob_and_command_tokens_are_not_surfaces(self, tmp_path):
        repo = tmp_path / "repo"
        _feature_repo(repo)
        artifacts = repo / ".prawduct" / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "boundary-patterns.md").write_text(
            "Glob: `docs/*.md`. Command: `/prawduct:pr`.\n"
        )
        _commit_file(repo, "docs/readme.md", "x\n", "doc change")
        assert _run(repo, "main").stdout.strip() == "standard"


class TestFailureAsymmetry:
    def test_fail_open_without_declared_surfaces(self, tmp_path):
        # Not a git repo, nothing declared: standard, exit 0, honest note.
        repo = tmp_path / "repo"
        (repo / ".prawduct").mkdir(parents=True)
        result = _run(repo)
        assert result.returncode == 0
        assert result.stdout.strip() == "standard"
        assert "git failure" in result.stderr

    def test_fail_closed_with_declared_surfaces(self, tmp_path):
        # Not a git repo, surfaces declared: declared risk + unverifiable
        # diff must NOT get the standard-tier reviewer.
        repo = tmp_path / "repo"
        (repo / ".prawduct").mkdir(parents=True)
        _declare_surfaces(repo, "risk_surfaces:\n  - src/core/\n")
        result = _run(repo)
        assert result.returncode == 0
        assert result.stdout.strip() == "escalate"
        assert "could not be evaluated" in result.stderr

    def test_unknown_flag_rejected(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / ".prawduct").mkdir(parents=True)
        result = _run(repo, "--bogus")
        assert result.returncode == 1
        assert "unknown argument" in result.stderr

    def test_two_positional_args_rejected(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / ".prawduct").mkdir(parents=True)
        result = _run(repo, "main", "develop")
        assert result.returncode == 1
        assert "at most one" in result.stderr
