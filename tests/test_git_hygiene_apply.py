"""Tests for git-tidy's online legs and `--apply` (lib/git_hygiene.py).

`gh` is a fake on PATH that records its argv and serves canned JSON, so the real
subprocess seam is exercised; the remote is a bare repo on disk.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

from lib import git_hygiene as gh
from lib.git_hygiene import DELETE_BRANCH, DELETE_REMOTE_BRANCH, KEPT, REMOVE_WORKTREE, REMOVED, SKIPPED

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / "plugin" / "bin" / "prawduct-hook"
DAY = 86400

FAKE_GH = r'''#!/usr/bin/env python3
import json, os, sys
d = os.environ["FAKE_GH_DIR"]
with open(os.path.join(d, "calls.log"), "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\n")
if os.path.exists(os.path.join(d, "fail")):
    sys.exit(1)
args = sys.argv[1:]
state = args[args.index("--state") + 1] if "--state" in args else ""
if state == "open":
    name = "open.json"
else:
    name = "merged-" + args[args.index("--head") + 1].replace("/", "--") + ".json"
path = os.path.join(d, name)
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


def branch_with_commit(repo: Path, name: str, base: str = "main") -> str:
    git(repo, "checkout", "-q", "-b", name, base)
    sha = commit(repo, name.replace("/", "-") + ".txt")
    git(repo, "checkout", "-q", base)
    return sha


def merge(repo: Path, name: str, into: str = "main") -> None:
    git(repo, "checkout", "-q", into)
    git(repo, "merge", "-q", "--no-ff", "-m", f"merge {name}", name)


@pytest.fixture
def fake_gh(tmp_path, monkeypatch):
    d = tmp_path / "fakegh"
    (d / "bin").mkdir(parents=True)
    exe = d / "bin" / "gh"
    exe.write_text(FAKE_GH.replace("#!/usr/bin/env python3", f"#!{sys.executable}"))
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("FAKE_GH_DIR", str(d))
    monkeypatch.setenv("PATH", f"{d / 'bin'}{os.pathsep}{os.environ['PATH']}")
    (d / "open.json").write_text("[]")

    class Fake:
        dir = d

        def open_prs(self, prs):
            (d / "open.json").write_text(json.dumps(prs))

        def merged(self, branch, prs):
            (d / f"merged-{branch.replace('/', '--')}.json").write_text(json.dumps(prs))

        def fail(self):
            (d / "fail").write_text("")

        def calls(self):
            log = d / "calls.log"
            return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return Fake()


@pytest.fixture
def clone(tmp_path):
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", str(origin))
    repo = tmp_path / "repo"
    git(tmp_path, "init", "-q", str(repo))
    commit(repo, "a.txt")
    git(repo, "remote", "add", "origin", str(origin))
    git(repo, "push", "-q", "-u", "origin", "main")
    git(repo, "remote", "set-head", "origin", "main")
    return repo


def online(repo: Path, **kw) -> gh.Plan:
    return gh.plan(repo, roots=[], offline=False, **kw)


def targets(p: gh.Plan, kind: str) -> set[str]:
    return {a.target for a in p.actions if a.kind == kind}


def pushed_merged(repo: Path, name: str) -> str:
    sha = branch_with_commit(repo, name)
    git(repo, "push", "-q", "origin", name)
    merge(repo, name)
    git(repo, "push", "-q", "origin", "main")
    return sha


# --- the online dry run -------------------------------------------------------


class TestOnlinePlan:
    def test_it_fetches_with_prune_so_a_deleted_remote_branch_drops_out(self, clone, tmp_path, fake_gh):
        pushed_merged(clone, "feat/gone-upstream")
        other = tmp_path / "other"
        git(tmp_path, "clone", "-q", str(tmp_path / "origin.git"), str(other))
        git(other, "push", "-q", "origin", "--delete", "feat/gone-upstream")
        offline = gh.plan(clone, roots=[], offline=True)
        assert "origin/feat/gone-upstream" in targets(offline, DELETE_REMOTE_BRANCH), "control"
        assert "origin/feat/gone-upstream" not in targets(online(clone), DELETE_REMOTE_BRANCH)

    def test_with_no_open_requests_remote_deletions_are_checked(self, clone, fake_gh):
        pushed_merged(clone, "feat/a")
        p = online(clone)
        [remote] = [a for a in p.actions if a.kind == DELETE_REMOTE_BRANCH]
        assert remote.unchecked is None and p.fully_checked
        assert ["pr", "list", "--state", "open"] == fake_gh.calls()[0][:4]

    @pytest.mark.parametrize("pr, kept", [
        ({"number": 7, "headRefName": "feat/next", "baseRefName": "feat/a", "isCrossRepository": False}, True),
        ({"number": 8, "headRefName": "feat/a", "baseRefName": "main", "isCrossRepository": False}, True),
        # A cross-repository head is counted too: in a fork setup `gh` answers for the
        # upstream, where this clone's own branch heads its request as cross-repo.
        ({"number": 9, "headRefName": "feat/a", "baseRefName": "main", "isCrossRepository": True}, True),
    ], ids=["stacked-base", "same-repo-head", "cross-repo-head-as-a-fork-sees-it"])
    def test_an_open_request_using_the_branch_keeps_it(self, clone, fake_gh, pr, kept):
        pushed_merged(clone, "feat/a")
        fake_gh.open_prs([pr])
        p = online(clone)
        assert ("origin/feat/a" in targets(p, DELETE_REMOTE_BRANCH)) is not kept
        if kept:
            assert any(f"#{pr['number']}" in n for n in p.notes)

    def test_gh_unavailable_leaves_remote_deletions_unchecked(self, clone, fake_gh):
        pushed_merged(clone, "feat/a")
        fake_gh.fail()
        p = online(clone)
        [remote] = [a for a in p.actions if a.kind == DELETE_REMOTE_BRANCH]
        assert "could not list open pull requests" in remote.unchecked
        assert not p.fully_checked
        assert "feat/a" in targets(p, DELETE_BRANCH), "local removals need no network"

    def test_a_full_page_of_open_requests_proves_nothing(self, clone, fake_gh):
        pushed_merged(clone, "feat/a")
        fake_gh.open_prs([{"number": n, "headRefName": f"x{n}", "baseRefName": "main",
                           "isCrossRepository": False} for n in range(gh.OPEN_PR_LIMIT)])
        [remote] = [a for a in online(clone).actions if a.kind == DELETE_REMOTE_BRANCH]
        assert remote.unchecked

    def test_offline_starts_no_network_process(self, clone, fake_gh, monkeypatch):
        pushed_merged(clone, "feat/a")
        started = []
        real = subprocess.run
        monkeypatch.setattr(subprocess, "run", lambda a, *x, **k: (started.append(list(a)), real(a, *x, **k))[1])
        gh.plan(clone, roots=[], offline=True)
        assert started
        assert not [a for a in started if a[0] == "gh" or (a[0] == "git" and set(a) & {"fetch", "push", "ls-remote"})]
        assert fake_gh.calls() == []

    def test_network_legs_take_the_network_budget(self, clone, fake_gh, monkeypatch):
        """A `push --delete` that ran out of the 15s local budget is how this
        was found: every call that reaches the remote — git's and gh's — waits on
        a round-trip, so it takes the network floor while local reads keep 15s."""
        monkeypatch.delenv("PRAWDUCT_GIT_TIMEOUT", raising=False)
        pushed_merged(clone, "feat/a")
        seen = []
        real = subprocess.run
        monkeypatch.setattr(subprocess, "run",
                            lambda a, *x, **k: (seen.append((list(a), k.get("timeout"))), real(a, *x, **k))[1])
        online(clone)
        network = [t for a, t in seen if a[0] == "gh" or (a[0] == "git" and a[1] in {"fetch", "push", "ls-remote"})]
        local = [t for a, t in seen if a[0] == "git" and a[1] in {"for-each-ref", "rev-parse"}]
        assert network and set(network) == {gh.evidence.NETWORK_TIMEOUT_FLOOR}
        assert local and max(local) < gh.evidence.NETWORK_TIMEOUT_FLOOR, "local reads keep their own budget"

    def test_a_malformed_override_still_bounds_gh(self, monkeypatch):
        """The git legs refuse a malformed override; `gh` cannot be refused the
        same way without dropping its call, and `timeout=None` would let it run
        unbounded — so it takes the floor."""
        monkeypatch.setenv("PRAWDUCT_GIT_TIMEOUT", "1O")
        assert gh._gh_timeout() == gh.evidence.NETWORK_TIMEOUT_FLOOR


class TestSquashProof:
    def _squash_merged(self, clone, name="feat/sq") -> str:
        sha = branch_with_commit(clone, name)
        git(clone, "push", "-q", "-u", "origin", name)
        git(clone, "merge", "-q", "--squash", name)
        git(clone, "commit", "-q", "-m", f"squash {name}")
        git(clone, "push", "-q", "origin", "main", f":{name}")  # GitHub auto-deletes the head
        git(clone, "fetch", "-q", "--prune", "origin")
        return sha

    def test_a_merged_request_with_this_exact_head_proves_it(self, clone, fake_gh):
        sha = self._squash_merged(clone)
        fake_gh.merged("feat/sq", [{"number": 41, "headRefOid": sha, "isCrossRepository": False}])
        [action] = [a for a in online(clone).actions if a.kind == DELETE_BRANCH]
        assert (action.target, action.proven_by) == ("feat/sq", f"{gh.PR_PROOF}41")
        assert action.command == ("git", "update-ref", "-d", "refs/heads/feat/sq", sha)

    @pytest.mark.parametrize("pr", [
        {"number": 41, "headRefOid": "0" * 40, "isCrossRepository": False},
        {"number": 41, "headRefOid": "SHA", "isCrossRepository": True},
    ], ids=["different-head", "from-a-fork"])
    def test_anything_else_proves_nothing(self, clone, fake_gh, pr):
        sha = self._squash_merged(clone)
        fake_gh.merged("feat/sq", [{**pr, "headRefOid": pr["headRefOid"].replace("SHA", sha)}])
        assert "feat/sq" not in targets(online(clone), DELETE_BRANCH)

    def test_a_squash_strategy_asks_even_with_the_upstream_present(self, clone, fake_gh):
        sha = branch_with_commit(clone, "feat/kept-upstream")
        git(clone, "push", "-q", "-u", "origin", "feat/kept-upstream")
        fake_gh.merged("feat/kept-upstream", [{"number": 5, "headRefOid": sha, "isCrossRepository": False}])
        assert "feat/kept-upstream" not in targets(online(clone), DELETE_BRANCH), "control: not asked"
        d = clone / ".prawduct" / "artifacts"
        d.mkdir(parents=True)
        (d / "project-preferences.md").write_text("- **PR merge strategy**: squash\n")
        assert "feat/kept-upstream" in targets(online(clone), DELETE_BRANCH)

    def test_lookups_are_capped_and_the_rest_reported(self, clone, fake_gh):
        for i in range(gh.MAX_PR_PROOFS + 2):
            self._squash_merged(clone, f"feat/sq{i:02d}")
        p = online(clone)
        lookups = [c for c in fake_gh.calls() if "merged" in c]
        assert len(lookups) == gh.MAX_PR_PROOFS
        assert any("2 more branch(es)" in pr for pr in p.problems)


# --- apply --------------------------------------------------------------------


class TestApply:
    def test_it_removes_exactly_the_approved_set(self, clone, fake_gh):
        pushed_merged(clone, "feat/a")
        branch_with_commit(clone, "feat/unmerged")
        p = online(clone)
        result, outcomes = gh.apply(clone, p.fingerprint, roots=[])
        assert {(o.target, o.result) for o in outcomes} == {("feat/a", REMOVED), ("origin/feat/a", REMOVED)}
        assert "feat/a" not in git(clone, "branch", "--list", "feat/a")
        assert git(clone, "ls-remote", "origin", "refs/heads/feat/a") == ""
        assert "feat/unmerged" in git(clone, "branch", "--list", "feat/unmerged")
        after = online(clone)
        assert after.actions == [] and after.fully_checked

    def test_a_branch_merged_into_a_long_lived_branch_other_than_head(self, clone, fake_gh):
        """The case `git branch -d` refuses: merged into develop, with main checked out."""
        git(clone, "branch", "develop", "main")
        branch_with_commit(clone, "feat/gitflow", base="develop")
        merge(clone, "feat/gitflow", into="develop")
        git(clone, "checkout", "-q", "main")
        _, outcomes = gh.apply(clone, online(clone).fingerprint, roots=[])
        assert ("feat/gitflow", REMOVED) in {(o.target, o.result) for o in outcomes}

    def test_the_branch_config_goes_with_the_branch(self, clone, fake_gh):
        pushed_merged(clone, "feat/a")
        git(clone, "branch", "--set-upstream-to", "origin/feat/a", "feat/a")
        gh.apply(clone, online(clone).fingerprint, roots=[])
        assert "branch.feat/a" not in git(clone, "config", "--list")

    def test_a_changed_set_changes_nothing(self, clone, fake_gh):
        pushed_merged(clone, "feat/a")
        stale = online(clone).fingerprint
        pushed_merged(clone, "feat/b")
        result, outcomes = gh.apply(clone, stale, roots=[])
        assert outcomes == []
        assert "feat/a" in git(clone, "branch", "--list", "feat/a")
        assert "is now" in gh.render_applied(result, stale, outcomes)

    def test_a_branch_that_moves_after_the_plan_is_kept(self, clone, fake_gh, monkeypatch):
        pushed_merged(clone, "feat/a")
        approved = online(clone).fingerprint
        real_plan = gh.plan

        def plan_then_move(*a, **k):
            p = real_plan(*a, **k)
            git(clone, "checkout", "-q", "feat/a")
            commit(clone, "late.txt")
            git(clone, "checkout", "-q", "main")
            return p
        monkeypatch.setattr(gh, "plan", plan_then_move)
        _, outcomes = gh.apply(clone, approved, roots=[])
        [local] = [o for o in outcomes if o.kind == DELETE_BRANCH]
        assert (local.result, local.detail) == (KEPT, "it moved since the dry run")
        assert "feat/a" in git(clone, "branch", "--list", "feat/a")

    def test_the_delete_itself_compares_before_it_deletes(self, clone, fake_gh, monkeypatch):
        """Even past the re-proof, update-ref deletes only the proven commit."""
        pushed_merged(clone, "feat/a")
        approved = online(clone).fingerprint
        real_reprove = gh._reprove

        def reprove_then_race(project_dir, action, remote):
            verdict = real_reprove(project_dir, action, remote)
            if action.kind == DELETE_BRANCH:
                git(clone, "checkout", "-q", "feat/a")
                commit(clone, "race.txt")
                git(clone, "checkout", "-q", "main")
            return verdict
        monkeypatch.setattr(gh, "_reprove", reprove_then_race)
        _, outcomes = gh.apply(clone, approved, roots=[])
        [local] = [o for o in outcomes if o.kind == DELETE_BRANCH]
        assert local.result == gh.FAILED
        assert "feat/a" in git(clone, "branch", "--list", "feat/a")

    def test_one_failure_does_not_stop_the_rest(self, clone, tmp_path, fake_gh):
        pushed_merged(clone, "feat/a")
        pushed_merged(clone, "feat/b")
        hook = tmp_path / "origin.git" / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\nwhile read old new ref; do [ \"$ref\" = refs/heads/feat/a ] && exit 1; done\nexit 0\n")
        hook.chmod(0o755)
        _, outcomes = gh.apply(clone, online(clone).fingerprint, roots=[])
        results = {o.target: o.result for o in outcomes}
        assert results["origin/feat/a"] == gh.FAILED
        assert results["origin/feat/b"] == REMOVED
        assert results["feat/a"] == results["feat/b"] == REMOVED

    def test_offline_apply_skips_remote_deletions(self, clone, fake_gh):
        pushed_merged(clone, "feat/a")
        p = gh.plan(clone, roots=[], offline=True)
        _, outcomes = gh.apply(clone, p.fingerprint, roots=[], offline=True)
        results = {o.target: o.result for o in outcomes}
        assert results == {"feat/a": REMOVED, "origin/feat/a": SKIPPED}
        assert fake_gh.calls() == []
        assert git(clone, "ls-remote", "origin", "refs/heads/feat/a")

    def test_a_finished_sibling_worktree_and_its_branch(self, clone, tmp_path, fake_gh):
        wt = tmp_path / "side"
        git(clone, "worktree", "add", "-q", "-b", "feat/side", str(wt))
        commit(wt, "side.txt")
        merge(clone, "feat/side")
        later = time.time() + 8 * DAY
        p = gh.plan(clone, roots=[], offline=False, now=later)
        _, outcomes = gh.apply(clone, p.fingerprint, roots=[], now=later)
        assert {(o.kind, o.result) for o in outcomes} >= {(REMOVE_WORKTREE, REMOVED), (DELETE_BRANCH, REMOVED)}
        assert not wt.exists()

    def test_a_sibling_that_gets_dirty_after_the_plan_is_kept(self, clone, tmp_path, fake_gh, monkeypatch):
        wt = tmp_path / "side"
        git(clone, "worktree", "add", "-q", "-b", "feat/side", str(wt))
        commit(wt, "side.txt")
        merge(clone, "feat/side")
        later = time.time() + 8 * DAY
        approved = gh.plan(clone, roots=[], offline=False, now=later).fingerprint
        real_plan = gh.plan
        monkeypatch.setattr(gh, "plan", lambda *a, **k: (real_plan(*a, **k), (wt / "wip.txt").write_text("w"))[0])
        _, outcomes = gh.apply(clone, approved, roots=[], now=later)
        [w] = [o for o in outcomes if o.kind == REMOVE_WORKTREE]
        assert w.result == KEPT and wt.exists()


class TestCommand:
    def _run(self, cwd, *args, home):
        env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}
        env["HOME"] = str(home)
        return subprocess.run([sys.executable, str(HOOK), "git-tidy", *args], cwd=str(cwd),
                              capture_output=True, text=True, env=env, timeout=120)

    def test_dry_run_then_apply_through_the_command(self, clone, tmp_path, fake_gh):
        pushed_merged(clone, "feat/a")
        dry = self._run(clone, "--json", home=tmp_path / "h")
        fp = json.loads(dry.stdout)["fingerprint"]
        assert f"--apply {fp}" in self._run(clone, home=tmp_path / "h").stdout
        applied = self._run(clone, "--apply", fp, "--json", home=tmp_path / "h")
        assert applied.returncode == 0, applied.stdout + applied.stderr
        payload = json.loads(applied.stdout)
        assert payload["applied"] is True and {o["result"] for o in payload["outcomes"]} == {"removed"}

    def test_a_stale_fingerprint_exits_1_and_changes_nothing(self, clone, tmp_path, fake_gh):
        pushed_merged(clone, "feat/a")
        before = git(clone, "for-each-ref")
        result = self._run(clone, "--apply", "000000000000", home=tmp_path / "h")
        assert result.returncode == 1 and "nothing was changed" in result.stdout
        assert git(clone, "for-each-ref") == before

    def test_one_failed_removal_exits_1_through_the_command(self, clone, tmp_path, fake_gh):
        pushed_merged(clone, "feat/a")
        hook = tmp_path / "origin.git" / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        fp = json.loads(self._run(clone, "--json", home=tmp_path / "h").stdout)["fingerprint"]
        applied = self._run(clone, "--apply", fp, "--json", home=tmp_path / "h")
        results = {o["target"]: o["result"] for o in json.loads(applied.stdout)["outcomes"]}
        assert results == {"feat/a": "removed", "origin/feat/a": "failed"}
        assert applied.returncode == 1

    def test_a_skipped_removal_exits_1_through_the_command(self, clone, tmp_path, fake_gh):
        pushed_merged(clone, "feat/a")
        fp = json.loads(self._run(clone, "--offline", "--json", home=tmp_path / "h").stdout)["fingerprint"]
        applied = self._run(clone, "--offline", "--apply", fp, home=tmp_path / "h")
        assert "skipped" in applied.stdout and applied.returncode == 1

    def test_apply_without_a_fingerprint_is_usage(self, clone, tmp_path):
        result = self._run(clone, "--apply", home=tmp_path / "h")
        assert result.returncode == 2 and "fingerprint" in result.stderr


class TestCredentials:
    def test_a_token_in_git_output_never_reaches_ours(self, clone, fake_gh, monkeypatch):
        """git redacts URL credentials in its own messages today, so the fixture
        injects the message at the runner: what this guards is a git, a helper or
        a proxy that does not."""
        from lib import evidence
        token = "ghp_" + "a" * 36
        real = evidence.run_git

        def leaky(cwd, *args, **kw):
            if args[:1] == ("fetch",):
                return 128, "", f"fatal: unable to access 'https://{token}@github.com/o/r.git/'"
            return real(cwd, *args, **kw)
        monkeypatch.setattr(evidence, "run_git", leaky)
        p = online(clone)
        text = gh.render(p) + gh.to_json(p)
        assert any("could not fetch" in pr for pr in p.problems), "the failure was reached"
        assert token not in text and "[REDACTED]" in text
