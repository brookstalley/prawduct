"""``prawduct-hook plan check-claims`` — BR3: every plan claim names a real branch.

A live plan's ``branch:`` and ``working-branches:`` entries bind checkouts to it.
A claim on a branch nobody has binds nothing. Usually the branch merged and
was deleted while the plan stayed live. Each claimed name must exist locally
or on a remote, and each miss is reported on its own line. "Git could not
list branches" is exit 3, never a list of misses. Driven through the real
binary over real git repos, with ``HOME`` outside the repo.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"


def _env(repo: Path) -> dict[str, str]:
    home = repo.parent / "_home"
    home.mkdir(exist_ok=True)
    return {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
        "CLAUDE_PROJECT_DIR": str(repo),
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@e.com", "-c", "user.name=T", *args],
        cwd=str(repo), capture_output=True, text=True, env=_env(repo), check=True, timeout=10,
    )


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "seed.txt").write_text("seed\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "seed")
    (repo / ".prawduct" / "artifacts").mkdir(parents=True)
    (repo / ".prawduct" / "project-state.yaml").write_text("")
    return repo.resolve()


def _plan(repo: Path, name: str, frontmatter: str, *, archived: bool = False) -> None:
    base = repo / ".prawduct" / "artifacts" / ("archive" if archived else "")
    base.mkdir(parents=True, exist_ok=True)
    (base / name).write_text(
        f"---\nartifact: build-plan\n{frontmatter}---\n\n# Build Plan\n\n## Build Chunks\n"
    )


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK), "plan", "check-claims", *args],
        cwd=str(repo), capture_output=True, text=True, env=_env(repo), timeout=60,
    )


def test_a_claim_on_an_existing_local_branch_resolves(tmp_path):
    repo = _repo(tmp_path)
    _git(repo, "branch", "feature/a")
    _plan(repo, "build-plan-a.md", "scope: a\nbranch: feature/a\n")
    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ok: 1 claim(s) across 1 live plan(s)" in result.stdout


def test_a_missing_local_branch_is_reported_and_exits_1(tmp_path):
    repo = _repo(tmp_path)
    _git(repo, "branch", "feature/a")
    _plan(repo, "build-plan-a.md", "scope: a\nbranch: feature/a\n")
    _plan(repo, "build-plan-gone.md", "scope: gone\nbranch: feature/merged-and-deleted\n")
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stdout.splitlines() == [
        ".prawduct/artifacts/build-plan-gone.md: branch feature/merged-and-deleted does not exist"
    ]


def test_a_branch_only_on_a_remote_resolves(tmp_path):
    repo = _repo(tmp_path)
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True, timeout=10, env=_env(repo))
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "branch", "feature/pushed")
    _git(repo, "push", "-q", "origin", "feature/pushed")
    _git(repo, "branch", "-D", "feature/pushed")
    _plan(repo, "build-plan-p.md", "scope: p\nbranch: feature/pushed\n")
    result = _run(repo, "--json")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["claims"] == [{
        "plan": ".prawduct/artifacts/build-plan-p.md", "field": "branch",
        "branch": "feature/pushed", "where": "remote", "outcome": "exists",
    }]


def test_a_missing_working_branch_is_reported_by_its_field(tmp_path):
    repo = _repo(tmp_path)
    _git(repo, "branch", "feature/unit")
    _git(repo, "branch", "feature/unit-a")
    _plan(
        repo, "build-plan-unit.md",
        "scope: unit\nbranch: feature/unit\nworking-branches:\n  - feature/unit-a\n  - feature/unit-b\n",
    )
    result = _run(repo)
    assert result.returncode == 1
    assert result.stdout.splitlines() == [
        ".prawduct/artifacts/build-plan-unit.md: working-branches feature/unit-b does not exist"
    ]


def test_every_miss_is_listed_not_just_the_first(tmp_path):
    repo = _repo(tmp_path)
    _plan(repo, "build-plan-x.md", "scope: x\nbranch: gone-1\nworking-branches: [gone-2]\n")
    _plan(repo, "build-plan-y.md", "scope: y\nbranch: gone-3\n")
    result = _run(repo)
    assert result.returncode == 1
    assert len(result.stdout.splitlines()) == 3
    assert {line.split(" ")[-4] for line in result.stdout.splitlines()} == {"gone-1", "gone-2", "gone-3"}


def test_an_archived_plan_claims_nothing(tmp_path):
    repo = _repo(tmp_path)
    _plan(repo, "build-plan-old.md", "scope: old\nbranch: long-gone\n", archived=True)
    result = _run(repo)
    assert result.returncode == 0, result.stdout
    assert "ok: no live plan claims a branch" in result.stdout


def test_an_unreadable_claim_is_not_a_resolving_one(tmp_path):
    repo = _repo(tmp_path)
    _plan(repo, "build-plan-bad.md", "scope: bad\nworking-branches: just-a-string\n")
    result = _run(repo)
    assert result.returncode == 1, result.stdout
    assert "build-plan-bad.md: claim unreadable" in result.stdout


def test_unreadable_git_exits_3_and_accuses_no_claim(tmp_path):
    """A directory git cannot read: the answer is "could not ask", not a list
    of misses. Control: the same plans in a real repo report the miss."""
    notgit = tmp_path / "notgit"
    (notgit / ".prawduct" / "artifacts").mkdir(parents=True)
    _plan(notgit, "build-plan-a.md", "scope: a\nbranch: feature/a\n")
    result = _run(notgit)
    assert result.returncode == 3, result.stdout + result.stderr
    assert "does not exist" not in result.stdout
    assert "could not list" in result.stderr

    repo = _repo(tmp_path)
    _plan(repo, "build-plan-a.md", "scope: a\nbranch: feature/a\n")
    assert _run(repo).returncode == 1


def test_an_extra_argument_is_a_usage_error(tmp_path):
    repo = _repo(tmp_path)
    assert _run(repo, "extra").returncode == 2
    assert _run(repo, "--bogus").returncode == 2


# ---------------------------------------------------------------------------
# release-pending: gitflow retention, not a miss (D-BR5)
# ---------------------------------------------------------------------------

_FRAGMENT = (
    "---\nschema: 1\ntype: feature\nscope: {scope}\ndate: 2026-10-01\n"
    "title: Ship the thing\n---\nNarrative, naming Chunk 01.\n\n"
    "## Consumer note\nnone: test fixture\n"
)


def _fragment(repo: Path, scope: str) -> None:
    changes = repo / ".prawduct" / "changes"
    changes.mkdir(parents=True, exist_ok=True)
    (changes / f"{scope}.md").write_text(_FRAGMENT.format(scope=scope))


class TestReleasePending:
    """A merged child's plan rides along until release (D-BR5, release.md):
    its branch is deleted, its plan stays live, and its change record is
    still pending. That is the retention policy working, so it gets its own
    line and does not fail the check. A missing branch with no pending record
    is still a miss."""

    def test_a_pending_fragment_makes_a_missing_branch_release_pending(self, tmp_path):
        repo = _repo(tmp_path)
        _plan(repo, "build-plan-shipped.md", "scope: shipped\nbranch: feature/merged\n")
        _fragment(repo, "shipped")
        result = _run(repo)
        assert result.returncode == 0, result.stdout + result.stderr
        assert (
            ".prawduct/artifacts/build-plan-shipped.md: branch claims feature/merged, which no "
            "longer exists; its fragment is pending release — archive at the release"
        ) in result.stdout.splitlines()
        assert "does not exist" not in result.stdout

    def test_without_a_pending_record_it_stays_a_miss(self, tmp_path):
        repo = _repo(tmp_path)
        _plan(repo, "build-plan-shipped.md", "scope: shipped\nbranch: feature/merged\n")
        _fragment(repo, "some-other-scope")
        result = _run(repo)
        assert result.returncode == 1, result.stdout
        assert "branch feature/merged does not exist" in result.stdout
        assert "pending release" not in result.stdout

    def test_an_untagged_change_log_entry_counts_in_a_single_file_log_repo(self, tmp_path):
        repo = _repo(tmp_path)
        _plan(repo, "build-plan-shipped.md", "scope: shipped\nbranch: feature/merged\n")
        (repo / ".prawduct" / "change-log.md").write_text(
            "# Change Log\n\n## 2026-10-01: shipped it\n<!-- prawduct: scope=shipped -->\n\nBody.\n"
        )
        result = _run(repo)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "its change-log entry is pending release — archive at the release" in result.stdout

    def test_a_released_change_log_entry_is_not_pending(self, tmp_path):
        repo = _repo(tmp_path)
        _plan(repo, "build-plan-shipped.md", "scope: shipped\nbranch: feature/merged\n")
        (repo / ".prawduct" / "change-log.md").write_text(
            "# Change Log\n\n## 2026-10-01: shipped it\n<!-- prawduct: scope=shipped | release=v1.0.0 -->\n\nBody.\n"
        )
        result = _run(repo)
        assert result.returncode == 1, result.stdout
        assert "branch feature/merged does not exist" in result.stdout

    def test_an_existing_branch_is_unchanged_by_a_pending_fragment(self, tmp_path):
        repo = _repo(tmp_path)
        _git(repo, "branch", "feature/live")
        _plan(repo, "build-plan-live.md", "scope: live\nbranch: feature/live\n")
        _fragment(repo, "live")
        result = _run(repo, "--json")
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["claims"] == [{
            "plan": ".prawduct/artifacts/build-plan-live.md", "field": "branch",
            "branch": "feature/live", "where": "local", "outcome": "exists",
        }]

    def test_json_names_the_outcome(self, tmp_path):
        repo = _repo(tmp_path)
        _plan(repo, "build-plan-shipped.md", "scope: shipped\nbranch: feature/merged\n")
        _plan(repo, "build-plan-gone.md", "scope: gone\nbranch: feature/gone\n")
        _fragment(repo, "shipped")
        result = _run(repo, "--json")
        assert result.returncode == 1
        outcomes = {c["branch"]: c["outcome"] for c in json.loads(result.stdout)["claims"]}
        assert outcomes == {"feature/merged": "release-pending", "feature/gone": "missing"}

    def test_an_invalid_fragment_exempts_nothing(self, tmp_path):
        """A fragment that fails validation may carry the wrong scope, so the
        pending set refuses it, and the missing branch stays a miss."""
        repo = _repo(tmp_path)
        _plan(repo, "build-plan-shipped.md", "scope: shipped\nbranch: feature/merged\n")
        changes = repo / ".prawduct" / "changes"
        changes.mkdir(parents=True)
        (changes / "shipped.md").write_text("---\nscope: shipped\n---\nNo schema.\n")
        result = _run(repo)
        assert result.returncode == 1, result.stdout
        assert "branch feature/merged does not exist" in result.stdout
        assert "could not be trusted" in result.stderr
