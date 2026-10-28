"""``lib/plan_lifecycle.py`` — a plan's lifecycle, observed and stored nowhere (LC1).

The subject is :func:`plan_lifecycle.observe`: ``in-progress``,
``merged-unreleased``, ``released``, ``superseded`` or ``unknown``, read off the
archive stamp, the change record and git, each answer's ``reason`` naming what
was observed. Fixtures are real git repos with a bare ``origin``, because the
answer is git's (does the base hold the branch's tip, or a reviewed commit),
and the ``gh`` probe runs against a fake ``gh`` on ``PATH``.
"""

from __future__ import annotations

import json
import os
import re
import socket
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import evidence, plan_lifecycle, plan_status  # noqa: E402

TS = "2026-10-25T10:00:00Z"
BRANCH = "feature/unit"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _env() -> dict[str, str]:
    return {
        **os.environ,
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_AUTHOR_NAME": "T",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "T",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args], cwd=str(cwd), capture_output=True,
        text=True, env=_env(), check=True, timeout=10,
    ).stdout.strip()


def _commit(repo: Path, name: str) -> str:
    (repo / name).write_text(name + "\n")
    _git(repo, "add", name)
    _git(repo, "commit", "-qm", name)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A clone of a bare ``origin`` holding ``main`` and ``develop``, checked
    out on ``develop``, with ``.prawduct/artifacts/`` (untracked — the plan is
    read from disk, and keeping it out of git keeps every merge clean) and an
    empty ``.prawduct/changes/``: a fragments repo with nothing pending, which
    ``release_readiness.pending_scopes`` reads as such rather than as a missing
    change log."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    repo = tmp_path / "repo"
    _git(tmp_path, "init", "-q", "-b", "main", str(repo))
    _commit(repo, "seed.txt")
    _git(repo, "remote", "add", "origin", str(origin))
    _git(repo, "branch", "develop")
    _git(repo, "push", "-q", "-u", "origin", "main", "develop")
    _git(repo, "checkout", "-q", "develop")
    (repo / ".prawduct" / "artifacts").mkdir(parents=True)
    (repo / ".prawduct" / "changes").mkdir()
    return repo.resolve()


def _plan(repo: Path, *, frontmatter: str = "", claim: str = f"branch: {BRANCH}\nbase: develop\n",
          scope: str = "unit") -> Path:
    path = repo / ".prawduct" / "artifacts" / "build-plan-unit.md"
    path.write_text(
        f"---\nartifact: build-plan\nscope: {scope}\n{claim}{frontmatter}---\n\n"
        "# Build Plan\n\n## Build Chunks\n\n### Chunk 01: c01\n"
    )
    return path


def _feature(repo: Path, branch: str = BRANCH, *, push: bool = True) -> str:
    """Cut ``branch`` from develop, commit on it, push it; back on develop."""
    _git(repo, "checkout", "-q", "-b", branch, "develop")
    sha = _commit(repo, branch.replace("/", "-") + ".txt")
    if push:
        _git(repo, "push", "-q", "-u", "origin", branch)
    _git(repo, "checkout", "-q", "develop")
    return sha


def _merge_no_ff(repo: Path, branch: str = BRANCH) -> None:
    _git(repo, "merge", "-q", "--no-ff", "-m", f"merge {branch}", branch)
    _git(repo, "push", "-q", "origin", "develop")


def _squash(repo: Path, branch: str = BRANCH) -> None:
    _git(repo, "merge", "-q", "--squash", branch)
    _git(repo, "commit", "-qm", f"squash {branch}")
    _git(repo, "push", "-q", "origin", "develop")


def _delete(repo: Path, branch: str = BRANCH) -> None:
    _git(repo, "branch", "-q", "-D", branch)
    _git(repo, "push", "-q", "origin", "--delete", branch)


def _review(fact_id: str, anchor: "str | None", *, scope: str = "unit",
            dispatch_commit: "str | None" = None, base_commit: "str | None" = None,
            ts: str = TS) -> dict:
    return {
        "schema": 1, "kind": "review", "id": fact_id, "ts": ts, "actor": {},
        "body": {
            "scope": scope, "mode": "chunk", "chunk": "01", "head_commit": anchor,
            "dispatch_commit": dispatch_commit or anchor, "base_commit": base_commit,
            "findings": [], "counts": {"blocking": 0, "warning": 0, "note": 0},
        },
    }


def _facts(*envelopes: dict) -> dict:
    return {"status": "ok", "facts": list(envelopes)}


def _write_store(repo: Path, *envelopes: dict) -> None:
    path = evidence.store_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e) + "\n" for e in envelopes))


_FRAGMENT = (
    "---\nschema: 1\ntype: feature\nscope: {scope}\ndate: 2026-10-01\n"
    "title: Ship the thing\n---\nNarrative, naming Chunk 01.\n\n"
    "## Consumer note\nnone: test fixture\n"
)


def _fragment(repo: Path, scope: str = "unit") -> None:
    changes = repo / ".prawduct" / "changes"
    changes.mkdir(parents=True, exist_ok=True)
    (changes / f"{scope}.md").write_text(_FRAGMENT.format(scope=scope))


def _plan_in_base(repo: Path) -> None:
    """Commit the plan to develop and push it: where any merge (merge commit,
    squash, rebase) leaves a plan, and what the change-record inference asks."""
    _plan(repo)
    _git(repo, "add", "-f", ".prawduct/artifacts/build-plan-unit.md")
    _git(repo, "commit", "-qm", "plan")
    _git(repo, "push", "-q", "origin", "develop")


def _observe(plan: Path, repo: Path, **kw) -> plan_lifecycle.Lifecycle:
    kw.setdefault("facts", _facts())
    return plan_lifecycle.observe(plan, repo_dir=repo, **kw)


# Responses are files named by what was asked; every call is logged in order
# (the shape of tests/test_git_hygiene_merge.py's fake).
FAKE_GH = r'''#!PYTHON
import json, os, sys
d = os.environ["FAKE_GH_DIR"]
args = sys.argv[1:]
with open(os.path.join(d, "calls.log"), "a") as f:
    f.write(json.dumps(args) + "\n")
def opt(name):
    return args[args.index(name) + 1].replace("/", "--") if name in args else ""
key = opt("--state") + "-head-" + opt("--head")
if os.path.exists(os.path.join(d, "fail-" + key)):
    sys.exit(1)
path = os.path.join(d, key + ".json")
print(open(path).read() if os.path.exists(path) else "[]")
'''


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

        def fails(self, key):
            (d / f"fail-{key.replace('/', '--')}").write_text("")

        def calls(self):
            log = d / "calls.log"
            return [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []
    return Fake()


def serve_merged(fake, branch: str, sha: str, number: int = 12, cross: bool = False) -> None:
    fake.serve(f"merged-head-{branch}", [{
        "number": number, "headRefName": branch, "headRefOid": sha,
        "isCrossRepository": cross}])


class _Spy:
    """Every subprocess by argv, and a socket that refuses to open."""

    def __init__(self, monkeypatch):
        self.calls: list[list[str]] = []
        real = subprocess.Popen
        spy = self

        class Recording(real):  # type: ignore[misc, valid-type]
            def __init__(self, args, *a, **kw):
                spy.calls.append(list(args))
                super().__init__(args, *a, **kw)

        monkeypatch.setattr(subprocess, "Popen", Recording)

        def no_network(*_a, **_kw):
            raise AssertionError("observe opened a socket")

        monkeypatch.setattr(socket, "socket", no_network)
        monkeypatch.setattr(socket, "create_connection", no_network)

    def git(self) -> list[list[str]]:
        return [c for c in self.calls if c[:1] == ["git"]]

    def gh(self) -> list[list[str]]:
        return [c for c in self.calls if Path(c[0]).name == "gh"]


# ---------------------------------------------------------------------------
# (3)/(4) — the branch exists
# ---------------------------------------------------------------------------


class TestBranchExists:
    def test_a_live_plan_on_an_unmerged_branch_is_in_progress(self, repo):
        _feature(repo)
        lc = _observe(_plan(repo), repo)
        assert lc.state == "in-progress", lc
        assert f"`{BRANCH}` exists locally" in lc.reason
        assert "not in `develop`'s history" in lc.reason
        assert (lc.released_in, lc.probed) == (None, False)

    def test_merged_with_no_ff_and_the_branch_kept_is_merged_unreleased(self, repo):
        _feature(repo)
        _merge_no_ff(repo)
        lc = _observe(_plan(repo), repo)
        assert lc.state == "merged-unreleased", lc
        assert f"`{BRANCH}` exists locally and its tip is in `develop`'s history" == lc.reason

    def test_a_merge_only_on_the_remote_base_counts(self, repo, tmp_path):
        """A merge GitHub made is on ``origin/develop`` before local ``develop``
        is pulled: the remote base answers too."""
        sha = _feature(repo)
        other = tmp_path / "merger"
        _git(tmp_path, "clone", "-q", str(tmp_path / "origin.git"), str(other))
        _git(other, "checkout", "-q", "develop")
        _git(other, "merge", "-q", "--no-ff", "-m", "merge", f"origin/{BRANCH}")
        _git(other, "push", "-q", "origin", "develop")
        plan = _plan(repo)
        assert _observe(plan, repo).state == "in-progress", "control: nothing fetched yet"
        _git(repo, "fetch", "-q", "origin")
        assert _git(repo, "rev-parse", "develop") != _git(repo, "rev-parse", "origin/develop")
        lc = _observe(plan, repo)
        assert lc.state == "merged-unreleased", lc
        assert "`origin/develop`'s history" in lc.reason
        assert sha  # the tip that origin/develop now holds

    def test_a_branch_only_on_the_remote_is_read_from_there(self, repo):
        _feature(repo)
        _git(repo, "branch", "-q", "-D", BRANCH)
        lc = _observe(_plan(repo), repo)
        assert lc.state == "in-progress", lc
        assert f"`{BRANCH}` exists on a remote" in lc.reason

    def test_a_branch_name_is_matched_exactly_not_by_prefix(self, repo):
        """``for-each-ref refs/heads/feature`` lists ``refs/heads/feature/unit``;
        a plan claiming ``feature`` must not read that branch as its own."""
        _feature(repo)  # feature/unit, unmerged
        lc = _observe(_plan(repo, claim="branch: feature\nbase: develop\n"), repo)
        assert lc.state == "unknown", lc
        assert "`feature` is on no local or remote branch" in lc.reason

    def test_a_base_on_no_branch_is_unknown_not_in_progress(self, repo):
        _feature(repo)
        lc = _observe(_plan(repo, claim=f"branch: {BRANCH}\nbase: nowhere\n"), repo)
        assert lc.state == "unknown", lc
        assert "its base `nowhere` is on no local or remote branch" in lc.reason

    def test_no_declared_base_falls_back_to_the_repo_base(self, repo):
        (repo / ".prawduct" / "project-state.yaml").write_text("base_branch: develop\n")
        _feature(repo)
        plan = _plan(repo, claim=f"branch: {BRANCH}\n")
        assert _observe(plan, repo).state == "in-progress"
        _merge_no_ff(repo)
        lc = _observe(plan, repo)
        assert lc.state == "merged-unreleased", lc
        assert "`origin/develop`'s history" in lc.reason


# ---------------------------------------------------------------------------
# (5) — the branch is gone
# ---------------------------------------------------------------------------


class TestBranchGone:
    def test_after_a_merge_commit_a_review_anchored_on_the_branch_answers(self, repo):
        sha = _feature(repo)
        _merge_no_ff(repo)
        _delete(repo)
        facts = _facts(
            _review("R-old", "0" * 40, ts="2026-10-20T00:00:00Z"),  # an anchor this clone lacks
            _review("R-other", sha, scope="other"),                  # another scope's fact
            _review("R1", sha),
        )
        lc = _observe(_plan(repo), repo, facts=facts)
        assert lc.state == "merged-unreleased", lc
        assert lc.reason == (
            f"`{BRANCH}` is on no local or remote branch, and review R1's commit "
            f"{sha[:12]} is in `develop`'s history"
        )

    def test_a_review_anchored_on_an_unmerged_deleted_branch_does_not_answer(self, repo):
        """Control for the anchor rule: the same fact, the branch deleted
        without merging, is not a merge."""
        sha = _feature(repo)
        _delete(repo)
        lc = _observe(_plan(repo), repo, facts=_facts(_review("R1", sha)))
        assert lc.state == "unknown", lc

    def test_a_dirty_tree_review_is_placed_by_its_dispatch_commit(self, repo):
        sha = _feature(repo)
        _merge_no_ff(repo)
        _delete(repo)
        fact = _review("R1", None, dispatch_commit=sha)
        lc = _observe(_plan(repo), repo, facts=_facts(fact))
        assert lc.state == "merged-unreleased", lc
        assert "review R1's commit" in lc.reason

    def test_the_store_is_read_when_no_facts_are_passed(self, repo):
        sha = _feature(repo)
        _merge_no_ff(repo)
        _delete(repo)
        _write_store(repo, _review("R1", sha))
        lc = plan_lifecycle.observe(_plan(repo), repo_dir=repo)
        assert lc.state == "merged-unreleased", lc
        assert "review R1" in lc.reason

    def test_a_pending_fragment_infers_merged_unreleased_and_says_so(self, repo):
        """The inference holds only for a plan in the base's tree, where the merge
        put it — so the plan is committed to develop here, as the merge would."""
        _feature(repo)
        _merge_no_ff(repo)
        _delete(repo)
        _fragment(repo)
        _plan_in_base(repo)
        lc = _observe(_plan(repo), repo)
        assert lc.state == "merged-unreleased", lc
        assert lc.reason == (
            f"inferred: `{BRANCH}` is on no local or remote branch, and its fragment for "
            "scope `unit` is pending release"
        )

    def test_a_fragment_committed_with_an_unmerged_plan_infers_nothing(self, repo):
        """#1106's control: the plan and its fragment are committed on a feature
        branch the base never merged, and the plan claims a branch that does not
        exist (a typo). `plan new` writes both together, so the pending fragment is
        no evidence of a merge; the in-base sibling above keeps inferring."""
        _git(repo, "checkout", "-q", "-b", "fix/real", "develop")
        _plan(repo)
        _fragment(repo)
        _git(repo, "add", ".prawduct")
        _git(repo, "commit", "-qm", "plan")
        lc = _observe(_plan(repo), repo)
        assert lc.state == "unknown", lc
        assert "which is not in `develop`'s tree" in lc.reason

    def test_a_fragment_beside_a_never_committed_plan_infers_nothing(self, repo):
        """Right after `plan new`, before its commit: the plan and fragment are on
        disk only. No merge brought them, so a mistyped `branch:` must not read as
        release-pending."""
        _plan(repo)
        _fragment(repo)
        lc = _observe(_plan(repo), repo)
        assert lc.state == "unknown", lc
        assert "which is not in `develop`'s tree" in lc.reason

    def test_another_scopes_fragment_infers_nothing(self, repo):
        _feature(repo)
        _delete(repo)
        _fragment(repo, "other")
        (repo / ".prawduct" / "artifacts" / "build-plan-other.md").write_text(
            "---\nartifact: build-plan\nscope: other\n---\n"
        )
        assert _observe(_plan(repo), repo).state == "unknown"

    def test_an_untagged_change_log_entry_infers_too(self, repo):
        _feature(repo)
        _delete(repo)
        (repo / ".prawduct" / "change-log.md").write_text(
            "# Change Log\n\n## 2026-10-01: unit work\n<!-- prawduct: scope=unit -->\n\nBody.\n"
        )
        _plan_in_base(repo)
        lc = _observe(_plan(repo), repo)
        assert lc.state == "merged-unreleased", lc
        assert "its change-log entry for scope `unit` is pending release" in lc.reason

    def test_squash_merged_and_deleted_with_no_fragment_is_unknown(self, repo):
        sha = _feature(repo)
        _squash(repo)
        _delete(repo)
        lc = _observe(_plan(repo), repo, facts=_facts(_review("R1", sha)))
        assert lc.state == "unknown", lc
        assert lc.probed is False
        assert lc.reason == (
            f"`{BRANCH}` is on no local or remote branch; no review fact for scope `unit` "
            "has its commit in `develop`'s history, and no change record for it is pending"
        )


# ---------------------------------------------------------------------------
# What is not evidence of a merge
# ---------------------------------------------------------------------------


class TestNotEvidenceOfAMerge:
    def test_a_fork_point_anchor_is_not_a_merge(self, repo):
        """A dirty-tree review dispatched on a fresh branch, before any commit,
        is anchored on the fork point — its own ``base_commit``, on ``develop``
        before the review ran. The branch deleted unmerged, nothing pending:
        ``unknown``. Control: the same shape anchored on a real branch commit
        that merged answers ``merged-unreleased``."""
        fork = _git(repo, "rev-parse", "develop")
        _git(repo, "branch", BRANCH, "develop")
        _git(repo, "push", "-q", "origin", BRANCH)
        _delete(repo)
        fresh = _review("R-fresh", None, dispatch_commit=fork, base_commit=fork)
        lc = _observe(_plan(repo), repo, facts=_facts(fresh))
        assert lc.state == "unknown", lc

        sha = _feature(repo)
        _merge_no_ff(repo)
        _delete(repo)
        real = _review("R-real", sha, base_commit=fork, ts="2026-10-26T00:00:00Z")
        lc = _observe(_plan(repo), repo, facts=_facts(fresh, real))
        assert lc.state == "merged-unreleased", lc
        assert "review R-real's commit" in lc.reason

    def test_a_dirty_tree_review_at_its_own_base_commit_merged_no_ff_is_a_merge(self, repo):
        """#1079's shape, in the lifecycle: a review of uncommitted work is anchored
        at its ``base_commit``, the branch HEAD the dirty tree sat on. A
        ``--no-ff`` merge brings that commit into develop through its second
        parent, off the first-parent history, so it shows the merge. The
        fork-point sibling above is the control: the same anchor-equals-base
        shape, on develop's first-parent history, shows nothing."""
        head = _feature(repo)
        _merge_no_ff(repo)
        _delete(repo)
        dirty = _review("R-dirty", None, dispatch_commit=head, base_commit=head)
        lc = _observe(_plan(repo), repo, facts=_facts(dirty))
        assert lc.state == "merged-unreleased", lc
        assert "review R-dirty's commit" in lc.reason

    def test_the_first_parent_question_failing_proves_no_merge(self, repo, monkeypatch):
        """Git unable to say where the anchor sits on develop: the review
        anchored at its own ``base_commit`` proves nothing (authority fails
        closed), where it would otherwise show the ``--no-ff`` merge."""
        head = _feature(repo)
        _merge_no_ff(repo)
        _delete(repo)
        dirty = _review("R-dirty", None, dispatch_commit=head, base_commit=head)
        assert _observe(_plan(repo), repo, facts=_facts(dirty)).state == "merged-unreleased"
        real = evidence.run_git

        def run_git(repo_dir, *args, **kw):
            if args[:1] == ("rev-list",):
                return 128, "", "fatal: injected failure"
            return real(repo_dir, *args, **kw)

        monkeypatch.setattr(evidence, "run_git", run_git)
        assert _observe(_plan(repo), repo, facts=_facts(dirty)).state == "unknown"

    def test_a_newer_base_commit_review_does_not_hide_the_older_one_after_a_fast_forward(self, repo):
        """A committed review R1 anchored at the branch commit, then a newer
        dirty-tree pass V1 dispatched at that same commit (so its anchor is its
        own ``base_commit``), then a fast-forward and the branch deleted. On the
        first-parent history V1's anchor cannot be told from a fork point, so
        it proves nothing — and it must not stand in for R1, which proves the
        merge from the same commit."""
        fork = _git(repo, "rev-parse", "develop")
        sha = _feature(repo)
        _git(repo, "merge", "-q", "--ff-only", BRANCH)
        _git(repo, "push", "-q", "origin", "develop")
        _delete(repo)
        older = _review("R1", sha, base_commit=fork, ts="2026-10-25T00:00:00Z")
        newer = _review("V1", None, dispatch_commit=sha, base_commit=sha, ts="2026-10-26T00:00:00Z")
        lc = _observe(_plan(repo), repo, facts=_facts(older, newer))
        assert lc.state == "merged-unreleased", lc
        assert "review R1's commit" in lc.reason
        # Control: V1 alone is the fork-point shape there, and proves nothing.
        assert _observe(_plan(repo), repo, facts=_facts(newer)).state == "unknown"

    def test_a_branch_with_no_commits_of_its_own_is_in_progress(self, repo):
        """A freshly cut branch's tip IS its base's tip, which git calls
        contained; it has no commits of its own, so it is not a merge."""
        _git(repo, "branch", BRANCH, "develop")
        lc = _observe(_plan(repo), repo)
        assert lc.state == "in-progress", lc
        assert lc.reason == (
            f"`{BRANCH}` exists locally and has no commits beyond `develop`, and no review "
            "fact for scope `unit` has a commit of its own in `develop`'s history"
        )

    def test_a_fast_forward_merge_is_certified_by_a_review_of_its_commits(self, repo):
        """Control for the rule above: fast-forward-merged after real work, the
        tip again equals the base tip, and a review anchored on one of the
        branch's commits is what says it merged."""
        fork = _git(repo, "rev-parse", "develop")
        sha = _feature(repo)
        _git(repo, "merge", "-q", "--ff-only", BRANCH)
        _git(repo, "push", "-q", "origin", "develop")
        assert _git(repo, "rev-parse", "develop") == sha, "fast-forwarded"
        lc = _observe(_plan(repo), repo, facts=_facts(_review("R1", sha, base_commit=fork)))
        assert lc.state == "merged-unreleased", lc
        assert lc.reason == (
            f"`{BRANCH}` exists locally and has no commits beyond `develop`, and review R1's "
            f"commit {sha[:12]} is in `develop`'s history"
        )

    def test_a_shipped_scope_with_a_pending_fragment_is_not_released(self, repo, monkeypatch):
        """The archive log ships scope ``unit``, and a newer fragment for it is
        pending: the later steps answer, not ``released``. Control: without
        the fragment the same log answers ``released``, with no git call."""
        _feature(repo)  # unmerged: the later steps say in-progress
        archive = repo / ".prawduct" / "change-log-archive"
        archive.mkdir()
        (archive / "2026-09.md").write_text(_SHIPPED)
        plan = _plan(repo)
        spy = _Spy(monkeypatch)
        assert _observe(plan, repo).state == "released"
        assert spy.git() == [], "the pending-set read costs no git call"
        _fragment(repo)
        lc = _observe(plan, repo)
        assert (lc.state, lc.released_in) == ("in-progress", None), lc


# ---------------------------------------------------------------------------
# (6) — the gh probe, only when asked
# ---------------------------------------------------------------------------


class TestProbePr:
    def test_a_merged_pull_request_answers_merged_unreleased_probed(self, repo, fake):
        sha = _feature(repo)
        _squash(repo)
        _delete(repo)
        serve_merged(fake, BRANCH, sha, number=41)
        lc = _observe(_plan(repo), repo, probe_pr=True)
        assert (lc.state, lc.probed) == ("merged-unreleased", True), lc
        assert "`gh` lists pull request #41 from it as merged" in lc.reason
        assert fake.calls() == [[
            "pr", "list", "--state", "merged", "--head", BRANCH,
            "--json", "number,headRefOid,isCrossRepository", "--limit", "20",
        ]]

    def test_no_merged_pull_request_stays_unknown_probed(self, repo, fake):
        _feature(repo)
        _delete(repo)
        lc = _observe(_plan(repo), repo, probe_pr=True)
        assert (lc.state, lc.probed) == ("unknown", True), lc
        assert lc.reason.endswith("`gh` lists no merged pull request from it")

    def test_a_cross_repository_pull_request_is_not_ours(self, repo, fake):
        sha = _feature(repo)
        _delete(repo)
        serve_merged(fake, BRANCH, sha, cross=True)
        assert _observe(_plan(repo), repo, probe_pr=True).state == "unknown"

    def test_gh_failing_is_unknown_and_says_it_could_not_ask(self, repo, fake):
        _feature(repo)
        _delete(repo)
        fake.fails(f"merged-head-{BRANCH}")
        lc = _observe(_plan(repo), repo, probe_pr=True)
        assert (lc.state, lc.probed) == ("unknown", True), lc
        assert "`gh` could not be asked" in lc.reason

    def test_the_probe_is_not_run_when_git_already_answers(self, repo, fake):
        _feature(repo)
        lc = _observe(_plan(repo), repo, probe_pr=True)
        assert (lc.state, lc.probed) == ("in-progress", False)
        assert fake.calls() == []


# ---------------------------------------------------------------------------
# (1)/(2) — the record answers before git
# ---------------------------------------------------------------------------


_SHIPPED = "# Change Log\n\n## 2026-09-01: unit shipped\n<!-- prawduct: scope=unit | release=v1.4.0 -->\n\nBody.\n"


class TestReleasedAndSuperseded:
    def test_a_scope_shipped_in_the_archive_log_is_released_even_with_the_branch_alive(
        self, repo, monkeypatch
    ):
        _feature(repo)  # unmerged: git alone would say in-progress
        archive = repo / ".prawduct" / "change-log-archive"
        archive.mkdir()
        (archive / "2026-09.md").write_text(_SHIPPED)
        spy = _Spy(monkeypatch)
        lc = _observe(_plan(repo), repo)
        assert (lc.state, lc.released_in) == ("released", "v1.4.0"), lc
        assert "the change record ships scope `unit` in v1.4.0" in lc.reason
        assert spy.git() == []

    def test_a_later_unreleased_entry_withholds_released(self, repo):
        _feature(repo)
        (repo / ".prawduct" / "change-log.md").write_text(
            _SHIPPED + "\n## 2026-10-01: more unit\n<!-- prawduct: scope=unit -->\n\nMore.\n"
        )
        assert _observe(_plan(repo), repo).state == "in-progress"

    @pytest.mark.parametrize(
        ("stamp", "state", "released_in", "said"),
        [
            ("lifecycle: superseded\narchived: 2026-10-01\nsuperseded_by: unit-2\n",
             "superseded", None, "`lifecycle: superseded` by unit-2"),
            ("lifecycle: completed\narchived: 2026-10-01\nreleased_in: v1.3.0\n",
             "released", "v1.3.0", "`lifecycle: completed`, released in v1.3.0"),
        ],
    )
    def test_an_archived_plan_answers_from_its_stamp_with_no_git_call(
        self, repo, monkeypatch, stamp, state, released_in, said
    ):
        _feature(repo)  # unmerged: git alone would say in-progress
        archive = repo / ".prawduct" / "artifacts" / "archive"
        archive.mkdir()
        plan = _plan(repo, frontmatter=stamp).rename(archive / "build-plan-unit.md")
        spy = _Spy(monkeypatch)
        lc = plan_lifecycle.observe(plan, repo_dir=repo)  # no facts: the store is not read either
        assert (lc.state, lc.released_in) == (state, released_in), lc
        assert said in lc.reason
        assert spy.calls == []


# ---------------------------------------------------------------------------
# Failure is unknown, never a raise; cost (NF1)
# ---------------------------------------------------------------------------


class TestFailsSoft:
    def test_git_failing_is_unknown_with_the_reason(self, tmp_path):
        not_a_repo = tmp_path / "plain"
        (not_a_repo / ".prawduct" / "artifacts").mkdir(parents=True)
        lc = _observe(_plan(not_a_repo), not_a_repo)
        assert lc.state == "unknown", lc
        assert lc.reason.startswith("git could not list this repo's refs")

    def test_an_unreadable_plan_is_unknown(self, repo):
        lc = _observe(repo / ".prawduct" / "artifacts" / "absent.md", repo)
        assert lc.state == "unknown"
        assert lc.reason.startswith("the plan could not be read")

    def test_an_unreadable_pending_set_is_named_in_the_unknown_reason(self, repo):
        """No change log and no fragment directory: ``pending_scopes`` cannot
        say what is pending, so nothing is inferred and the reason says why."""
        (repo / ".prawduct" / "changes").rmdir()
        _feature(repo)
        _delete(repo)
        lc = _observe(_plan(repo), repo)
        assert lc.state == "unknown", lc
        assert "the pending change records could not be read" in lc.reason

    def test_a_plan_with_no_branch_is_unknown(self, repo):
        lc = _observe(_plan(repo, claim=""), repo)
        assert lc.state == "unknown"
        assert "declares no `branch:`" in lc.reason


class TestCost:
    def test_in_progress_costs_two_git_calls(self, repo, monkeypatch):
        tip = _feature(repo)
        plan = _plan(repo)
        spy = _Spy(monkeypatch)
        assert _observe(plan, repo).state == "in-progress"
        assert spy.calls == [
            ["git", "for-each-ref", "--format=%(objectname) %(refname)",
             f"refs/heads/{BRANCH}", f"refs/remotes/*/{BRANCH}",
             "refs/heads/develop", "refs/remotes/*/develop"],
            ["git", "for-each-ref", "--contains", tip, "--format=%(refname)",
             "refs/heads/develop", "refs/remotes/origin/develop"],
        ]

    def test_the_anchor_walk_stops_at_the_first_hit_newest_first(self, repo, monkeypatch):
        sha = _feature(repo)
        _merge_no_ff(repo)
        _delete(repo)
        facts = _facts(
            _review("R-oldest", "1" * 40, ts="2026-10-01T00:00:00Z"),
            _review("R-newest", sha, ts="2026-10-24T00:00:00Z"),
            _review("R-middle", "2" * 40, ts="2026-10-10T00:00:00Z"),
        )
        spy = _Spy(monkeypatch)
        lc = _observe(_plan(repo), repo, facts=facts)
        assert lc.state == "merged-unreleased" and "R-newest" in lc.reason, lc
        contains = [c for c in spy.git() if "--contains" in c]
        assert [c[c.index("--contains") + 1] for c in contains] == [sha]

    def test_no_network_without_probe_pr(self, repo, monkeypatch, fake):
        """The unknown case is where the probe would run; without the flag no
        ``gh`` process starts and no socket opens."""
        sha = _feature(repo)
        _squash(repo)
        _delete(repo)
        serve_merged(fake, BRANCH, sha)
        spy = _Spy(monkeypatch)
        assert _observe(_plan(repo), repo).state == "unknown"
        assert spy.gh() == [] and fake.calls() == []
        assert spy.git(), "positive control: the spy saw the git calls"

    def test_the_spy_sees_the_probe(self, repo, monkeypatch, fake):
        """Positive control for the no-network pin: with the flag, gh runs."""
        _feature(repo)
        _delete(repo)
        spy = _Spy(monkeypatch)
        _observe(_plan(repo), repo, probe_pr=True)
        assert len(spy.gh()) == 1


# ---------------------------------------------------------------------------
# One home (LC1) and the rendered line
# ---------------------------------------------------------------------------


def test_merged_unreleased_is_spelled_only_by_plan_lifecycle():
    """The one derivation: a consumer compares against
    ``plan_lifecycle.MERGED_UNRELEASED`` rather than re-spelling the state."""
    sources = [*sorted((ROOT / "lib").rglob("*.py")), ROOT / "bin" / "prawduct-hook"]
    assert len(sources) > 50, "the walk reached plugin/"
    spelled = [
        str(p.relative_to(ROOT)) for p in sources
        if re.search(r"""["']merged-unreleased["']""", p.read_text(encoding="utf-8"))
    ]
    assert spelled == ["lib/plan_lifecycle.py"]
