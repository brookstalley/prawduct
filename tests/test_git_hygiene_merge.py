"""Tests for git-tidy's targeted moments: `--after-merge` and `--reap`."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from lib import git_hygiene as gh
from lib.git_hygiene import DONE, FAILED, KEPT, REMOVED, SKIPPED

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / "plugin" / "bin" / "prawduct-hook"

# Responses are files named by what was asked; every call is logged in order.
FAKE_GH = r'''#!PYTHON
import json, os, sys
d = os.environ["FAKE_GH_DIR"]
args = sys.argv[1:]
with open(os.path.join(d, "calls.log"), "a") as f:
    f.write(json.dumps(args) + "\n")
def opt(name):
    return args[args.index(name) + 1].replace("/", "--") if name in args else ""
if args[:2] == ["pr", "view"]:
    key = "view-" + args[2]
elif args[:2] == ["pr", "edit"]:
    sys.exit(1 if os.path.exists(os.path.join(d, "edit-fails")) else 0)
elif "--base" in args:
    key = "base-" + opt("--base")
else:
    key = opt("--state") + "-head-" + opt("--head")
path = os.path.join(d, key + ".json")
print(open(path).read() if os.path.exists(path) else "[]")
'''


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com",
         "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main", *args],
        cwd=str(cwd), capture_output=True, text=True, check=True,
    ).stdout


def commit(repo: Path, name: str) -> str:
    (repo / name).write_text(name)
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", name)
    return git(repo, "rev-parse", "HEAD").strip()


def tip(repo: Path, ref: str) -> str:
    return git(repo, "rev-parse", ref).strip()


def has_branch(repo: Path, name: str) -> bool:
    return bool(git(repo, "branch", "--list", name).strip())


def remote_has(repo: Path, name: str) -> bool:
    return bool(git(repo, "ls-remote", "origin", f"refs/heads/{name}").strip())


@pytest.fixture
def fake(tmp_path, monkeypatch):
    d = tmp_path / "fakegh"
    (d / "bin").mkdir(parents=True)
    exe = d / "bin" / "gh"
    exe.write_text(FAKE_GH.replace("#!PYTHON", f"#!{sys.executable}"))
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("FAKE_GH_DIR", str(d))
    monkeypatch.setenv("PATH", f"{d / 'bin'}{os.pathsep}{os.environ['PATH']}")

    class Fake:
        def serve(self, key, data):
            (d / f"{key.replace('/', '--')}.json").write_text(json.dumps(data))

        def edit_fails(self):
            (d / "edit-fails").write_text("")

        def calls(self):
            log = d / "calls.log"
            return [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []
    return Fake()


@pytest.fixture
def repo(tmp_path):
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", str(origin))
    r = tmp_path / "repo"
    git(tmp_path, "init", "-q", str(r))
    commit(r, "a.txt")
    git(r, "remote", "add", "origin", str(origin))
    git(r, "branch", "develop")
    git(r, "push", "-q", "-u", "origin", "main", "develop")
    git(r, "remote", "set-head", "origin", "main")
    return r


def merge_on_remote(repo: Path, tmp_path: Path, branch: str, base: str = "develop") -> None:
    """What GitHub does on a merge-commit merge: merge the head into base on the
    remote, from a clone that is not this one."""
    other = tmp_path / f"merger-{branch.replace('/', '-')}"
    if not other.exists():
        git(tmp_path, "clone", "-q", str(tmp_path / "origin.git"), str(other))
    git(other, "fetch", "-q", "origin")
    git(other, "checkout", "-q", "-B", base, f"origin/{base}")
    git(other, "merge", "-q", "--no-ff", "-m", f"merge {branch}", f"origin/{branch}")
    git(other, "push", "-q", "origin", base)


def feature_pushed(repo: Path, branch: str, base: str = "develop") -> str:
    git(repo, "checkout", "-q", "-b", branch, base)
    sha = commit(repo, branch.replace("/", "-") + ".txt")
    git(repo, "push", "-q", "-u", "origin", branch)
    return sha


def serve_merged(fake, branch: str, sha: str, base: str = "develop", number: int = 12, **extra):
    fake.serve(f"merged-head-{branch}", [{
        "number": number, "state": "MERGED", "headRefName": branch, "headRefOid": sha,
        "baseRefName": base, "isCrossRepository": False, **extra}])


class TestAfterMergeFromTheMainWorktree:
    def test_it_deletes_both_copies_and_lands_on_the_updated_base(self, repo, tmp_path, fake):
        sha = feature_pushed(repo, "feat/x")
        merge_on_remote(repo, tmp_path, "feat/x")
        serve_merged(fake, "feat/x", sha)
        steps = gh.after_merge(repo, "feat/x")
        assert [s.result for s in steps] == [REMOVED, DONE, REMOVED], steps
        assert not has_branch(repo, "feat/x") and not remote_has(repo, "feat/x")
        assert git(repo, "symbolic-ref", "--short", "HEAD").strip() == "develop"
        assert tip(repo, "develop") == tip(repo, "origin/develop"), "fast-forwarded"

    def test_a_named_pull_request_is_read_with_pr_view(self, repo, tmp_path, fake):
        sha = feature_pushed(repo, "feat/x")
        merge_on_remote(repo, tmp_path, "feat/x")
        fake.serve("view-31", {"number": 31, "state": "MERGED", "headRefName": "feat/x",
                               "headRefOid": sha, "baseRefName": "develop", "isCrossRepository": False})
        steps = gh.after_merge(repo, "feat/x", pr="31")
        assert not has_branch(repo, "feat/x")
        assert ["pr", "view", "31"] == fake.calls()[0][:3]
        assert steps[-1].result == REMOVED

    def test_an_unmerged_or_unknown_request_touches_nothing(self, repo, fake):
        feature_pushed(repo, "feat/x")
        steps = gh.after_merge(repo, "feat/x")
        assert [s.result for s in steps] == [SKIPPED]
        assert has_branch(repo, "feat/x") and remote_has(repo, "feat/x")


class TestAfterMergeFromALinkedWorktree:
    def test_it_detaches_at_the_base_when_another_worktree_holds_it(self, repo, tmp_path, fake):
        git(repo, "checkout", "-q", "develop")
        wt = tmp_path / "wt"
        git(repo, "worktree", "add", "-q", "-b", "feat/wt", str(wt), "develop")
        sha = commit(wt, "wt.txt")
        git(wt, "push", "-q", "-u", "origin", "feat/wt")
        merge_on_remote(repo, tmp_path, "feat/wt")
        serve_merged(fake, "feat/wt", sha)
        steps = gh.after_merge(wt, "feat/wt")
        assert [s.result for s in steps] == [REMOVED, DONE, REMOVED], steps
        assert "detach" in steps[1].name
        assert git(wt, "rev-parse", "HEAD").strip() == tip(repo, "origin/develop")
        assert not has_branch(repo, "feat/wt")


class TestTheGuards:
    def test_stacked_requests_are_retargeted_before_the_base_is_deleted(self, repo, tmp_path, fake):
        sha = feature_pushed(repo, "feat/base")
        merge_on_remote(repo, tmp_path, "feat/base")
        serve_merged(fake, "feat/base", sha)
        fake.serve("base-feat/base", [{"number": 44}])
        gh.after_merge(repo, "feat/base")
        calls = fake.calls()
        edit = calls.index(["pr", "edit", "44", "--base", "develop"])
        assert not remote_has(repo, "feat/base")
        later_lookups = [c for c in calls[edit + 1:] if c[:2] == ["pr", "list"]]
        assert later_lookups, "the remote delete's own open-request check came after the retarget"

    def test_a_failed_retarget_keeps_the_remote_branch(self, repo, tmp_path, fake):
        sha = feature_pushed(repo, "feat/base")
        merge_on_remote(repo, tmp_path, "feat/base")
        serve_merged(fake, "feat/base", sha)
        fake.serve("base-feat/base", [{"number": 44}])
        fake.edit_fails()
        steps = gh.after_merge(repo, "feat/base")
        assert steps[0].result == FAILED and steps[-1].result == KEPT
        assert remote_has(repo, "feat/base") and has_branch(repo, "feat/base")

    def test_local_commits_the_merge_did_not_take_keep_the_branch(self, repo, tmp_path, fake):
        sha = feature_pushed(repo, "feat/x")
        commit(repo, "late-unpushed.txt")
        merge_on_remote(repo, tmp_path, "feat/x")
        serve_merged(fake, "feat/x", sha)
        steps = gh.after_merge(repo, "feat/x")
        assert steps[-1].result == KEPT and "did not take" in steps[-1].detail
        assert has_branch(repo, "feat/x")

    def test_a_remote_branch_pushed_to_after_the_merge_is_kept(self, repo, tmp_path, fake):
        sha = feature_pushed(repo, "feat/x")
        merge_on_remote(repo, tmp_path, "feat/x")
        other = tmp_path / "merger-feat-x"
        git(other, "checkout", "-q", "-B", "feat/x", "origin/feat/x")
        commit(other, "after-merge.txt")
        git(other, "push", "-q", "origin", "feat/x")
        serve_merged(fake, "feat/x", sha)
        steps = gh.after_merge(repo, "feat/x")
        assert steps[0].result == KEPT and remote_has(repo, "feat/x")

    def test_an_already_deleted_remote_is_fine(self, repo, tmp_path, fake):
        sha = feature_pushed(repo, "feat/x")
        merge_on_remote(repo, tmp_path, "feat/x")
        git(repo, "push", "-q", "origin", "--delete", "feat/x")
        serve_merged(fake, "feat/x", sha)
        steps = gh.after_merge(repo, "feat/x")
        assert steps[0].result == SKIPPED and steps[-1].result == REMOVED

    def test_a_fork_head_is_never_pushed_to(self, repo, tmp_path, fake):
        sha = feature_pushed(repo, "feat/x")
        merge_on_remote(repo, tmp_path, "feat/x")
        fake.serve("view-9", {"number": 9, "state": "MERGED", "headRefName": "feat/x", "headRefOid": sha,
                              "baseRefName": "develop", "isCrossRepository": True})
        steps = gh.after_merge(repo, "feat/x", pr="9")
        assert steps[0].result == SKIPPED and "fork" in steps[0].detail
        assert remote_has(repo, "feat/x")

    def test_a_long_lived_head_is_kept_and_nothing_moves(self, repo, fake):
        git(repo, "branch", "release/1.0", "main")
        steps = gh.after_merge(repo, "release/1.0")
        assert [s.result for s in steps] == [KEPT] and has_branch(repo, "release/1.0")
        assert fake.calls() == []

    def test_cleanup_off_keeps_both_branches(self, repo, tmp_path, fake):
        sha = feature_pushed(repo, "feat/x")
        merge_on_remote(repo, tmp_path, "feat/x")
        serve_merged(fake, "feat/x", sha)
        prefs = repo / ".prawduct" / "artifacts"
        prefs.mkdir(parents=True)
        (prefs / "project-preferences.md").write_text("- **Branch cleanup**: off\n")
        gh.after_merge(repo, "feat/x")
        assert has_branch(repo, "feat/x") and remote_has(repo, "feat/x")
        assert git(repo, "symbolic-ref", "--short", "HEAD").strip() == "develop", "it still moves off the branch"

    def test_cleanup_off_does_not_survive_a_squash_strategy(self, repo, tmp_path, fake):
        sha = feature_pushed(repo, "feat/x")
        merge_on_remote(repo, tmp_path, "feat/x")
        serve_merged(fake, "feat/x", sha)
        prefs = repo / ".prawduct" / "artifacts"
        prefs.mkdir(parents=True)
        (prefs / "project-preferences.md").write_text(
            "- **Branch cleanup**: off\n- **PR merge strategy**: squash\n")
        gh.after_merge(repo, "feat/x")
        assert not has_branch(repo, "feat/x"), "single-use branches are deleted regardless"


class TestReap:
    def _delegate(self, repo, tmp_path, *, integrate=True):
        git(repo, "checkout", "-q", "-b", "feat/coordinator", "develop")
        wt = tmp_path / "agent-1"
        git(repo, "worktree", "add", "-q", "-b", "worktree-agent-1", str(wt), "develop")
        commit(wt, "delegate.txt")
        if integrate:
            git(repo, "merge", "-q", "--no-ff", "-m", "take delegate", "worktree-agent-1")
        return wt

    def test_an_integrated_delegate_goes_with_its_branch(self, repo, tmp_path):
        wt = self._delegate(repo, tmp_path)
        steps = gh.reap(repo, str(wt))
        assert [s.result for s in steps] == [REMOVED, REMOVED], steps
        assert not wt.exists() and not has_branch(repo, "worktree-agent-1")

    def test_an_unintegrated_delegate_is_kept(self, repo, tmp_path):
        wt = self._delegate(repo, tmp_path, integrate=False)
        [step] = gh.reap(repo, str(wt))
        assert step.result == KEPT and "not integrated" in step.detail
        assert wt.exists() and has_branch(repo, "worktree-agent-1")

    def test_a_dirty_delegate_is_kept(self, repo, tmp_path):
        wt = self._delegate(repo, tmp_path)
        (wt / "leftover.txt").write_text("x")
        [step] = gh.reap(repo, str(wt))
        assert step.result == KEPT and wt.exists()

    def test_a_locked_delegate_is_kept(self, repo, tmp_path):
        wt = self._delegate(repo, tmp_path)
        git(repo, "worktree", "lock", "--reason", "agent running", str(wt))
        [step] = gh.reap(repo, str(wt))
        assert step.result == KEPT and "locked" in step.detail and wt.exists()

    def test_the_main_worktree_cannot_be_reaped(self, repo, tmp_path):
        wt = self._delegate(repo, tmp_path)
        [step] = gh.reap(wt, str(repo))
        assert step.result == SKIPPED and repo.exists()


class TestCommand:
    def _run(self, cwd, *args, home):
        env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}
        env["HOME"] = str(home)
        return subprocess.run([sys.executable, str(HOOK), "git-tidy", *args], cwd=str(cwd),
                              capture_output=True, text=True, env=env, timeout=120)

    def test_after_merge_through_the_command(self, repo, tmp_path, fake):
        sha = feature_pushed(repo, "feat/x")
        merge_on_remote(repo, tmp_path, "feat/x")
        serve_merged(fake, "feat/x", sha)
        result = self._run(repo, "--after-merge", "feat/x", "--json", home=tmp_path / "h")
        assert result.returncode == 0, result.stdout + result.stderr
        assert [s["result"] for s in json.loads(result.stdout)["steps"]] == ["removed", "done", "removed"]

    def test_a_failed_step_exits_1(self, repo, tmp_path, fake):
        sha = feature_pushed(repo, "feat/base")
        merge_on_remote(repo, tmp_path, "feat/base")
        serve_merged(fake, "feat/base", sha)
        fake.serve("base-feat/base", [{"number": 44}])
        fake.edit_fails()
        assert self._run(repo, "--after-merge", "feat/base", home=tmp_path / "h").returncode == 1

    @pytest.mark.parametrize("args", [
        ["--pr", "3"], ["--reap"], ["--after-merge", "x", "--reap", "y"], ["--apply", "f", "--reap", "y"],
    ])
    def test_bad_combinations_are_usage(self, repo, tmp_path, args):
        assert self._run(repo, *args, home=tmp_path / "h").returncode == 2


class TestTheSurfacesDescribeThisMechanism:
    """The PR skill and the delegation guide are what an agent follows; pin that
    each names the command and that no surface still describes the old steps."""

    PLUGIN = REPO_ROOT / "plugin"

    def _step(self, text: str, marker: str) -> str:
        start = text.index(marker)
        end = text.find("\n", start)
        return text[start:end]

    def test_the_merge_flow_step_is_the_one_command(self):
        skill = (self.PLUGIN / "skills" / "pr" / "SKILL.md").read_text()
        step = self._step(skill, "7. **Clean up the branch")
        assert "prawduct-hook git-tidy --after-merge <headRefName> --pr <n>" in step
        assert "--delete-branch" in step, "it warns off the gh shortcut"

    def test_reaping_names_the_reap_command(self):
        guide = (self.PLUGIN / "methodology" / "delegation.md").read_text()
        para = self._step(guide, "**Reaping ends with the worktree")
        assert "prawduct-hook git-tidy --reap <worktree>" in para

    def test_no_shipped_surface_still_describes_the_old_cleanup(self):
        stale = ("switch to base branch, pull, delete local branch",
                 "only `git branch -d` notices", "`git branch -d` refusing the delete AFTER")
        hits = []
        for path in [*self.PLUGIN.rglob("*.md"), REPO_ROOT / ".claude" / "rules" / "learnings" / "pr.md"]:
            if path.name == "CHANGELOG.md":
                continue
            text = path.read_text()
            hits += [f"{path.relative_to(REPO_ROOT)}: {s}" for s in stale if s in text]
        assert hits == []
        assert any("git-tidy" in p.read_text() for p in self.PLUGIN.rglob("*.md")), "control: the sweep reads real files"
