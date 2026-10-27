"""Tests for lib/git_hygiene.py — what may be removed, and the proof for each.

Every "kept" test pairs with a control in the same fixture that IS proposed, so an
implementation that proposes nothing cannot pass a keep test.
"""

from __future__ import annotations

import json
import sys
import os
import subprocess
import time
from pathlib import Path

import pytest

from lib import git_hygiene as gh
from lib.git_hygiene import DELETE_BRANCH, DELETE_REMOTE_BRANCH, PRUNE_WORKTREE, REMOVE_WORKTREE

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / "plugin" / "bin" / "prawduct-hook"
DAY = 86400


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com",
         "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main", *args],
        cwd=str(cwd), capture_output=True, text=True, check=True,
    )
    return result.stdout


def commit(repo: Path, name: str, text: str = "x") -> str:
    (repo / name).write_text(text)
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", name)
    return git(repo, "rev-parse", "HEAD").strip()


def merge(repo: Path, branch: str, into: str = "main") -> None:
    git(repo, "checkout", "-q", into)
    git(repo, "merge", "-q", "--no-ff", "-m", f"merge {branch}", branch)


def feature(repo: Path, name: str, base: str = "main") -> str:
    git(repo, "checkout", "-q", "-b", name, base)
    sha = commit(repo, name.replace("/", "-") + ".txt")
    git(repo, "checkout", "-q", base)
    return sha


@pytest.fixture
def clone(tmp_path):
    """A clone of a bare origin with `main` pushed and origin/HEAD set."""
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", str(origin))
    repo = tmp_path / "repo"
    git(tmp_path, "init", "-q", str(repo))
    commit(repo, "a.txt")
    git(repo, "remote", "add", "origin", str(origin))
    git(repo, "push", "-q", "-u", "origin", "main")
    git(repo, "remote", "set-head", "origin", "main")
    return repo


def plan(repo: Path, *, idle: bool = True) -> gh.Plan:
    """The plan as of a clock far enough ahead that every worktree reads idle,
    or as of now, when every worktree just touched reads active."""
    now = time.time() + (8 * DAY if idle else 0)
    return gh.plan(repo, now=now, roots=[])


def targets(p: gh.Plan, kind: str) -> set[str]:
    return {a.target for a in p.actions if a.kind == kind}


# --- branches -----------------------------------------------------------------


class TestLocalBranches:
    def test_a_branch_merged_into_main_is_proposed_with_its_proof(self, clone):
        sha = feature(clone, "feat/done")
        merge(clone, "feat/done")
        p = plan(clone)
        [action] = [a for a in p.actions if a.kind == DELETE_BRANCH]
        assert (action.target, action.sha) == ("feat/done", sha)
        # Merged locally and not yet pushed: local main is what reaches it.
        assert action.proof == "reachable from main"
        assert action.command == ("git", "update-ref", "-d", "refs/heads/feat/done", sha)

    def test_merged_into_develop_counts_as_integrated(self, clone):
        git(clone, "branch", "develop", "main")
        feature(clone, "feat/gitflow", base="develop")
        merge(clone, "feat/gitflow", into="develop")
        git(clone, "checkout", "-q", "main")
        p = plan(clone)
        assert "feat/gitflow" in targets(p, DELETE_BRANCH)
        assert "develop" not in targets(p, DELETE_BRANCH), "develop is long-lived"

    def test_unmerged_branches_are_kept_pushed_or_not(self, clone):
        feature(clone, "feat/local-only")
        feature(clone, "feat/pushed")
        git(clone, "push", "-q", "origin", "feat/pushed")
        feature(clone, "feat/control")
        merge(clone, "feat/control")
        p = plan(clone)
        assert targets(p, DELETE_BRANCH) == {"feat/control"}
        assert "origin/feat/pushed" not in targets(p, DELETE_REMOTE_BRANCH)

    def test_a_commit_past_the_merged_tip_keeps_the_branch(self, clone):
        feature(clone, "feat/reused")
        merge(clone, "feat/reused")
        git(clone, "checkout", "-q", "feat/reused")
        commit(clone, "more.txt")
        git(clone, "checkout", "-q", "main")
        feature(clone, "feat/control")
        merge(clone, "feat/control")
        assert targets(plan(clone), DELETE_BRANCH) == {"feat/control"}

    def test_the_checked_out_branch_is_never_proposed(self, clone):
        feature(clone, "feat/here")
        merge(clone, "feat/here")
        feature(clone, "feat/control")
        merge(clone, "feat/control")
        git(clone, "checkout", "-q", "feat/here")
        assert targets(plan(clone), DELETE_BRANCH) == {"feat/control"}

    def test_proof_is_ancestry_never_age(self, clone):
        """An old unmerged branch is kept and a brand-new merged one goes: the
        proof is reachability, and the clock has no say in it."""
        feature(clone, "feat/ancient")
        feature(clone, "feat/fresh")
        merge(clone, "feat/fresh")
        far = gh.plan(clone, now=time.time() + 3650 * DAY, roots=[])
        assert targets(far, DELETE_BRANCH) == {"feat/fresh"}


class TestLongLived:
    def test_fixed_names_and_release_branches_are_never_proposed(self, clone):
        for name in ("master", "develop", "trunk", "release/1.0"):
            git(clone, "branch", name, "main")
        feature(clone, "feat/control")
        merge(clone, "feat/control")
        p = plan(clone)
        assert targets(p, DELETE_BRANCH) == {"feat/control"}
        assert {"develop", "main", "master", "release/1.0", "trunk"} <= set(p.long_lived)

    def test_a_hotfix_branch_is_not_long_lived(self, clone):
        feature(clone, "hotfix/1.0.1")
        merge(clone, "hotfix/1.0.1")
        assert "hotfix/1.0.1" in targets(plan(clone), DELETE_BRANCH)

    def test_merged_into_a_release_branch_is_integrated(self, clone):
        git(clone, "branch", "release/2.0", "main")
        feature(clone, "fix/for-release", base="release/2.0")
        merge(clone, "fix/for-release", into="release/2.0")
        git(clone, "checkout", "-q", "main")
        assert "fix/for-release" in targets(plan(clone), DELETE_BRANCH)

    def test_the_configured_base_branch_is_long_lived(self, clone):
        git(clone, "branch", "integration", "main")
        git(clone, "push", "-q", "origin", "integration")
        (clone / ".prawduct").mkdir()
        (clone / ".prawduct" / "project-state.yaml").write_text("base_branch: integration\n")
        p = plan(clone)
        assert "integration" in p.long_lived
        assert "integration" not in targets(p, DELETE_BRANCH)
        assert "origin/integration" not in targets(p, DELETE_REMOTE_BRANCH)

    def test_the_remote_default_branch_is_long_lived(self, clone):
        git(clone, "branch", "stable", "main")
        git(clone, "push", "-q", "origin", "stable")
        git(clone, "remote", "set-head", "origin", "stable")
        p = plan(clone)
        assert "stable" in p.long_lived
        assert "stable" not in targets(p, DELETE_BRANCH)

    def test_the_preference_row_adds_names_and_keeps_their_case(self, clone):
        git(clone, "branch", "Staging", "main")
        git(clone, "branch", "qa", "main")
        git(clone, "branch", "scratch", "main")
        artifacts = clone / ".prawduct" / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "project-preferences.md").write_text(
            "- **Long-lived branches**: Staging, qa (environment branches kept level with main)\n"
        )
        p = plan(clone)
        assert targets(p, DELETE_BRANCH) == {"scratch"}
        assert {"Staging", "qa"} <= set(p.long_lived)


class TestRemoteBranches:
    def test_a_merged_remote_branch_is_proposed_but_unchecked_offline(self, clone):
        feature(clone, "feat/pushed")
        git(clone, "push", "-q", "origin", "feat/pushed")
        merge(clone, "feat/pushed")
        git(clone, "push", "-q", "origin", "main")
        p = plan(clone)
        [remote] = [a for a in p.actions if a.kind == DELETE_REMOTE_BRANCH]
        assert remote.target == "origin/feat/pushed"
        assert remote.command == ("git", "push", "origin", "--delete", "refs/heads/feat/pushed")
        assert remote.unchecked == gh.OPEN_PR_UNCHECKED
        assert not p.fully_checked, "an unchecked removal is not a fully checked plan"

    def test_only_a_remote_long_lived_branch_proves_a_remote_deletion(self, clone):
        """Merged into local main and not pushed: deleting the remote copy would
        leave the merge on this machine alone. Pushing main is what proves it."""
        feature(clone, "feat/pushed")
        git(clone, "push", "-q", "origin", "feat/pushed")
        merge(clone, "feat/pushed")
        assert targets(plan(clone), DELETE_REMOTE_BRANCH) == set()
        assert "feat/pushed" in targets(plan(clone), DELETE_BRANCH), "the local copy is proven locally"
        git(clone, "push", "-q", "origin", "main")
        assert targets(plan(clone), DELETE_REMOTE_BRANCH) == {"origin/feat/pushed"}

    def test_a_remote_branch_whose_local_namesake_is_in_use_is_kept(self, clone):
        for name in ("feat/reused", "feat/control"):
            feature(clone, name)
            git(clone, "push", "-q", "origin", name)
            merge(clone, name)
        git(clone, "push", "-q", "origin", "main")
        git(clone, "checkout", "-q", "feat/reused")  # local is held, so its remote stays
        assert targets(plan(clone), DELETE_REMOTE_BRANCH) == {"origin/feat/control"}

    def test_the_remote_head_and_long_lived_remotes_are_never_proposed(self, clone):
        git(clone, "branch", "develop", "main")
        git(clone, "push", "-q", "origin", "develop")
        p = plan(clone)
        assert targets(p, DELETE_REMOTE_BRANCH) == set()
        assert p.fully_checked


# --- worktrees ----------------------------------------------------------------


class TestWorktrees:
    def _finished_worktree(self, clone, tmp_path, name: str) -> Path:
        wt = tmp_path / name
        git(clone, "worktree", "add", "-q", "-b", f"feat/{name}", str(wt))
        commit(wt, f"{name}.txt")
        merge(clone, f"feat/{name}")
        return wt

    def test_a_finished_idle_sibling_is_proposed_and_frees_its_branch(self, clone, tmp_path):
        wt = self._finished_worktree(clone, tmp_path, "done")
        p = plan(clone)
        assert targets(p, REMOVE_WORKTREE) == {str(wt.resolve())}
        [branch] = [a for a in p.actions if a.kind == DELETE_BRANCH]
        assert branch.target == "feat/done"
        assert "worktree removed first" in branch.proof
        kinds = [a.kind for a in p.actions]
        assert kinds.index(REMOVE_WORKTREE) < kinds.index(DELETE_BRANCH), "the worktree goes first"

    def test_an_active_sibling_is_kept(self, clone, tmp_path):
        self._finished_worktree(clone, tmp_path, "busy")
        p = plan(clone, idle=False)
        assert targets(p, REMOVE_WORKTREE) == set()
        assert "feat/busy" not in targets(p, DELETE_BRANCH), "its branch is still held"
        assert targets(plan(clone), REMOVE_WORKTREE), "control: the same tree idle is proposed"

    @pytest.mark.parametrize("make_dirty", [
        lambda wt: (wt / "a.txt").write_text("edited"),
        lambda wt: (wt / "new-untracked.txt").write_text("u"),
    ], ids=["tracked-change", "untracked-file"])
    def test_a_dirty_sibling_is_kept(self, clone, tmp_path, make_dirty):
        dirty = self._finished_worktree(clone, tmp_path, "dirty")
        make_dirty(dirty)
        self._finished_worktree(clone, tmp_path, "clean")
        removed = targets(plan(clone), REMOVE_WORKTREE)
        assert len(removed) == 1 and next(iter(removed)).endswith("clean")

    def test_an_ignored_file_does_not_make_a_tree_dirty(self, clone, tmp_path):
        (clone / ".gitignore").write_text("*.log\n")
        git(clone, "add", ".gitignore")
        git(clone, "commit", "-q", "-m", "ignore logs")
        wt = self._finished_worktree(clone, tmp_path, "logs")
        (wt / "build.log").write_text("noise")
        assert targets(plan(clone), REMOVE_WORKTREE)

    def test_a_locked_sibling_is_kept(self, clone, tmp_path):
        locked = self._finished_worktree(clone, tmp_path, "agent")
        git(clone, "worktree", "lock", "--reason", "claude agent running", str(locked))
        self._finished_worktree(clone, tmp_path, "control")
        removed = targets(plan(clone), REMOVE_WORKTREE)
        assert len(removed) == 1 and next(iter(removed)).endswith("control")

    def test_a_detached_checkout_is_kept_even_clean_merged_and_idle(self, clone, tmp_path):
        """An install a plugin runs from looks exactly like this: detached at a
        merged commit, clean, quiet for days. Being merged says nothing about it
        being finished."""
        install = tmp_path / "install"
        git(clone, "worktree", "add", "-q", "--detach", str(install), "main")
        self._finished_worktree(clone, tmp_path, "control")
        removed = targets(plan(clone), REMOVE_WORKTREE)
        assert len(removed) == 1 and next(iter(removed)).endswith("control")

    def test_a_long_lived_branch_checkout_is_kept(self, clone, tmp_path):
        git(clone, "branch", "develop", "main")
        git(clone, "worktree", "add", "-q", str(tmp_path / "dev"), "develop")
        self._finished_worktree(clone, tmp_path, "control")
        removed = targets(plan(clone), REMOVE_WORKTREE)
        assert len(removed) == 1 and next(iter(removed)).endswith("control")

    def test_an_unmerged_sibling_is_kept(self, clone, tmp_path):
        wip = tmp_path / "wip"
        git(clone, "worktree", "add", "-q", "-b", "feat/wip", str(wip))
        commit(wip, "wip.txt")
        self._finished_worktree(clone, tmp_path, "control")
        removed = targets(plan(clone), REMOVE_WORKTREE)
        assert len(removed) == 1 and next(iter(removed)).endswith("control")

    def test_the_main_worktree_is_never_proposed_from_a_linked_one(self, clone, tmp_path):
        feature(clone, "feat/main-on")
        merge(clone, "feat/main-on")
        git(clone, "checkout", "-q", "feat/main-on")
        linked = tmp_path / "linked"
        git(clone, "worktree", "add", "-q", "-b", "feat/linked", str(linked), "main")
        p = gh.plan(linked, now=time.time() + 8 * DAY, roots=[])
        assert not any(a.target == str(clone) or a.target == str(clone.resolve()) for a in p.actions)
        assert "feat/main-on" not in targets(p, DELETE_BRANCH)

    def test_a_missing_worktree_entry_is_pruned_unless_locked(self, clone, tmp_path):
        gone = tmp_path / "gone"
        away = tmp_path / "away"
        git(clone, "worktree", "add", "-q", "-b", "feat/gone", str(gone))
        git(clone, "worktree", "add", "-q", "-b", "feat/away", str(away))
        git(clone, "worktree", "lock", "--reason", "on a usb stick", str(away))
        subprocess.run(["rm", "-rf", str(gone), str(away)], check=True)
        p = plan(clone)
        pruned = targets(p, PRUNE_WORKTREE)
        assert len(pruned) == 1 and next(iter(pruned)).endswith("gone")
        [action] = [a for a in p.actions if a.kind == PRUNE_WORKTREE]
        assert action.command == ("git", "worktree", "prune")


# --- the plan as a whole ------------------------------------------------------


class TestFingerprint:
    def test_order_does_not_matter_and_a_moved_tip_does(self):
        a = gh.Action(DELETE_BRANCH, "x", "1" * 40, "p", ("git",))
        b = gh.Action(DELETE_BRANCH, "y", "2" * 40, "p", ("git",))
        moved = gh.Action(DELETE_BRANCH, "y", "3" * 40, "p", ("git",))
        assert gh.fingerprint([a, b]) == gh.fingerprint([b, a])
        assert gh.fingerprint([a, b]) != gh.fingerprint([a, moved])
        assert len(gh.fingerprint([a])) == 12

    def test_a_new_commit_on_a_proposed_branch_changes_the_fingerprint(self, clone):
        feature(clone, "feat/a")
        merge(clone, "feat/a")
        before = plan(clone).fingerprint
        git(clone, "checkout", "-q", "-b", "feat/b")
        commit(clone, "b.txt")
        git(clone, "checkout", "-q", "main")
        merge(clone, "feat/b")
        assert plan(clone).fingerprint != before


class TestFailures:
    def test_git_failing_is_a_problem_never_nothing_to_tidy(self, clone, monkeypatch):
        from lib import gitstate
        monkeypatch.setattr(gitstate, "worktree_records", lambda _d: None)
        p = plan(clone)
        assert p.problems and not p.fully_checked
        assert "Nothing to tidy." not in gh.render(p)
        assert "not everything was checked" in gh.render(p)

    def test_a_plain_directory_is_tidy_and_says_so(self, tmp_path):
        plain = tmp_path / "plain"
        plain.mkdir()
        p = gh.plan(plain, roots=[])
        assert p.actions == [] and p.fully_checked
        assert "Nothing to tidy." in gh.render(p)


class TestNotes:
    def test_a_pushed_branch_level_with_main_gets_the_long_lived_hint(self, clone):
        git(clone, "branch", "staging", "main")
        git(clone, "push", "-q", "origin", "staging")
        git(clone, "branch", "scratch", "main")  # unpushed and level: no hint
        notes = " ".join(plan(clone).notes)
        assert "staging points at the same commit as main" in notes
        assert "scratch" not in notes


# --- the command --------------------------------------------------------------


def run_hook(cwd: Path, *args: str, home: Path) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}
    env["HOME"] = str(home)
    return subprocess.run(
        [sys.executable, str(HOOK), "git-tidy", *args], cwd=str(cwd),
        capture_output=True, text=True, env=env, timeout=60,
    )


class TestCommand:
    def test_the_dry_run_lists_actions_and_changes_nothing(self, clone, tmp_path):
        feature(clone, "feat/done")
        merge(clone, "feat/done")
        before = git(clone, "for-each-ref")
        result = run_hook(clone, "--offline", home=tmp_path / "home")
        assert result.returncode == 0, result.stderr
        assert "feat/done" in result.stdout and "git update-ref -d refs/heads/feat/done" in result.stdout
        assert "fingerprint" in result.stdout
        assert git(clone, "for-each-ref") == before

    def test_json_carries_the_fingerprint_and_the_actions(self, clone, tmp_path):
        feature(clone, "feat/done")
        merge(clone, "feat/done")
        result = run_hook(clone, "--offline", "--json", home=tmp_path / "home")
        payload = json.loads(result.stdout)
        assert payload["schema_version"] == gh.SCHEMA_VERSION
        assert [a["target"] for a in payload["actions"]] == ["feat/done"]
        assert payload["fingerprint"] == gh.fingerprint([gh.Action(**{
            **payload["actions"][0], "command": tuple(payload["actions"][0]["command"])})])

    def test_an_unknown_argument_is_usage_exit_2(self, clone, tmp_path):
        result = run_hook(clone, "--bogus", home=tmp_path / "home")
        assert result.returncode == 2
        assert "usage" in result.stderr

    def test_git_unreadable_exits_3_and_never_says_tidy(self, clone, monkeypatch, capsys):
        from lib import gitstate
        assert gh.git_tidy_cmd(clone, []) == 0, "control: the same repo readable exits 0"
        capsys.readouterr()
        monkeypatch.setattr(gitstate, "worktree_records", lambda _d: None)
        assert gh.git_tidy_cmd(clone, []) == 3
        out = capsys.readouterr().out
        assert "Nothing to tidy." not in out and "could not list worktrees" in out


@pytest.mark.requires_history
class TestThisClone:
    """Invariants over the real clone, whatever its current state: the subject is
    reached (worktrees and branches exist) and nothing protected is proposed."""

    def test_nothing_protected_is_ever_proposed_here(self):
        from lib import gitstate
        records = gitstate.worktree_records(REPO_ROOT)
        assert records, "the subject was reached: this clone lists its worktrees"
        p = gh.plan(REPO_ROOT, now=time.time() + 8 * DAY)
        held = gitstate.held_branches(records)
        current = git(REPO_ROOT, "rev-parse", "--abbrev-ref", "HEAD").strip()
        assert p.long_lived, "the long-lived set was resolved"
        for action in p.actions:
            name = action.target.removeprefix(f"{p.remote}/")
            if action.kind in (DELETE_BRANCH, DELETE_REMOTE_BRANCH):
                assert not gh.is_long_lived(name, set(p.long_lived))
                assert name != current
            if action.kind == DELETE_BRANCH:
                assert name not in held or "removed first" in action.proof
        locked = {r["worktree"] for r in records if "locked" in r}
        assert not targets(p, REMOVE_WORKTREE) & locked
