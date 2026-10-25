"""``lib.work_unit.resolve`` — one owner, three answers (#1050 Wave 1).

Each shipped misattribution shape is pinned red-first: the fixture is built,
the two resolvers ``resolve()`` replaces are asked the same question, and their
answer is asserted alongside the new one so the test documents the defect it
closes. Where an old resolver already answers a shape correctly (the #1049 fix
closed one route), the comment says so instead of asserting a wrong answer.

Real git repos in a sterile env, as ``test_ephemeral_worktree.py`` builds them:
the detached-HEAD, no-work-tree and scratch-worktree cases only exist in git.
"""

from __future__ import annotations

import io
import socket
import subprocess
import sys
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import buildplan_refs, core, work_unit  # noqa: E402
from lib.work_unit import Binding, resolve  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures (real git, sterile env)
# ---------------------------------------------------------------------------


def _git_env(repo: Path) -> dict[str, str]:
    # HOME outside the repo: macOS Python's pyc cache under HOME would land as
    # untracked files inside the fixture otherwise.
    home = repo.parent / "_home"
    home.mkdir(exist_ok=True)
    return {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
    }


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True,
        env=_git_env(repo), check=True, timeout=10,
    )


def _repo(tmp_path: Path, branch: str, state: str = "") -> Path:
    """A work tree on ``branch`` with an empty ``.prawduct/artifacts/`` inside."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", branch)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-qm", "seed")
    prawduct = repo / ".prawduct"
    (prawduct / "artifacts").mkdir(parents=True)
    (prawduct / "project-state.yaml").write_text(state)
    return repo


def _plan(
    repo: Path,
    rel: str,
    *,
    scope: str | None = "the-unit",
    branch: str | None = None,
    working: list[str] | None = None,
    artifact: str | None = "build-plan",
    chunks: str = "- [ ] Chunk 01: a chunk\n",
) -> Path:
    path = repo / ".prawduct" / "artifacts" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = ["---"]
    if artifact is not None:
        fm.append(f"artifact: {artifact}")
    if scope is not None:
        fm.append(f"scope: {scope}")
    if branch is not None:
        fm.append(f"branch: {branch}")
    if working is not None:
        fm.append("working-branches:" + ("" if working else " []"))
        fm.extend(f"  - {name}" for name in working)
    fm.append("---")
    path.write_text("\n".join(fm) + f"\n\n## Status\n\n{chunks}")
    return path


def _scratch_worktree(repo: Path, wid: str = "a287823214767feaa") -> Path:
    """The disposable shape Claude Code's Agent tool produces: an ``agent-<hex>``
    directory under ``.claude/worktrees`` on a ``worktree-agent-<hex>`` branch.

    Forked from HEAD, as the harness forks it — so the primary's plan is
    committed first, or the scratch tree would carry no ``.prawduct/`` at all
    and every resolver would answer "nothing" for the wrong reason."""
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "plan")
    dest = repo / ".claude" / "worktrees" / f"agent-{wid}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", "-q", "-b", f"worktree-agent-{wid}", str(dest), "HEAD")
    return dest.resolve()


def _old_core(repo: Path) -> Path | None:
    return core.resolve_build_plan_path(repo / ".prawduct")


def _old_refs(repo: Path) -> buildplan_refs.ReviewedPlan:
    return buildplan_refs.resolve_branch_plan(repo, repo / ".prawduct")


FINISHED = "- [x] Chunk 01: done\n- [x] Chunk 02: done\n"


# ---------------------------------------------------------------------------
# The API
# ---------------------------------------------------------------------------


class TestBindingShape:
    def test_fields_in_the_order_the_design_states(self):
        assert [f.name for f in fields(Binding)] == [
            "state", "scope", "plan_path", "role", "reason", "chosen_by",
        ]

    def test_frozen(self):
        binding = Binding("unbound", None, None, None, "x", "none")
        with pytest.raises(FrozenInstanceError):
            binding.state = "bound"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Shipped misattribution shapes, red first
# ---------------------------------------------------------------------------


class TestShippedShapes:
    def test_1049_finished_plan_at_the_default_path_governs_no_other_branch(self, tmp_path):
        """#1049: a finished plan retained live at ``artifacts/build-plan.md``
        (gitflow keeps it until the release) went back into force on every
        branch no plan claimed, and a Critic review of an unrelated fix branch
        was written to the ledger under its scope."""
        repo = _repo(tmp_path, "fix/plan-archive-scope-name")
        _plan(
            repo, "build-plan.md", scope="review-stats-dispositions",
            branch="feature/941-review-stats-dispositions", chunks=FINISHED,
        )
        # Post-#1049 both old resolvers already refuse this plan: the core
        # resolver's foreign-claim rule and, through it, the branch-plan
        # resolver. The route that wrote the ledger event was
        # `ledger._scope_from_plan`, which is Chunk 02's to delete.
        assert _old_core(repo) is None
        assert _old_refs(repo).path is None

        binding = resolve(repo)
        assert binding == Binding(
            "unbound", None, None, None,
            "no live plan claims `fix/plan-archive-scope-name`", "none",
        )

    def test_1007a_lone_plan_declaring_no_branch_binds_through_the_legacy_window(self, tmp_path):
        """#1007 shape (a): a lone plan at the conventional path that declares no
        branch. The old resolvers served it silently — the same file, with no
        signal that a fallback answered. Inside the window it still governs,
        and the binding says which route answered and how to end the window."""
        repo = _repo(tmp_path, "feat/anything")
        plan = _plan(repo, "build-plan.md", scope="lonely")
        assert _old_core(repo) == plan
        old = _old_refs(repo)
        assert old.path == plan
        assert old.gap is None  # nothing said a fallback answered

        binding = resolve(repo)
        assert binding.state == "bound"
        assert binding.chosen_by == "legacy-default"
        assert (binding.scope, binding.plan_path, binding.role) == ("lonely", plan, None)
        assert binding.reason.startswith(f"{work_unit.LEGACY_ADVISORY_KEY}:")
        assert f"{work_unit.BIND_COMMAND} build-plan.md --branch feat/anything" in binding.reason

    def test_1007a_the_pointer_route_is_named_as_such(self, tmp_path):
        repo = _repo(tmp_path, "feat/anything", "active_build_plan: artifacts/v2-plan.md\n")
        plan = _plan(repo, "v2-plan.md", scope="v2")
        assert _old_core(repo) == plan

        binding = resolve(repo)
        assert (binding.state, binding.chosen_by) == ("bound", "legacy-pointer")
        assert binding.plan_path == plan
        assert "`active_build_plan`" in binding.reason

    def test_208_a_branch_named_like_an_unrelated_plans_scope_is_unbound(self, tmp_path):
        """#208: mode inference matched the branch's last segment against a
        declared scope and graded the review against that plan. A name is not
        a claim."""
        repo = _repo(tmp_path, "fix/telemetry")
        other = _plan(repo, "build-plan-telemetry.md", scope="telemetry", branch="feature/telemetry")
        # The old branch-plan resolver infers `telemetry` from the branch name
        # and answers the plan another branch is building.
        assert _old_refs(repo).path == other
        assert _old_refs(repo).scope == "telemetry"

        binding = resolve(repo)
        assert binding.state == "unbound"
        assert binding.plan_path is None
        assert binding.reason == "no live plan claims `fix/telemetry`"

    def test_two_claimants_is_broken_never_resolved_by_precedence(self, tmp_path):
        repo = _repo(tmp_path, "release/2-0")
        a = _plan(repo, "build-plan-a.md", scope="a", branch="release/2-0")
        b = _plan(repo, "build-plan-b.md", scope="b", branch="release/2-0", chunks=FINISHED)
        # The old resolver picks one by precedence (here: the claimant with
        # open chunks) and the other plan governs nothing, silently.
        assert _old_core(repo) == a

        binding = resolve(repo)
        assert binding.state == "broken"
        assert (binding.scope, binding.plan_path, binding.chosen_by) == (None, None, "none")
        assert "2 live plans claim `release/2-0`" in binding.reason
        assert "build-plan-a.md" in binding.reason and "build-plan-b.md" in binding.reason
        del b

    def test_a_declared_working_branch_binds_with_role_working(self, tmp_path):
        repo = _repo(tmp_path, "feature/x-delegate")
        plan = _plan(
            repo, "build-plan-x.md", scope="x", branch="feature/x",
            working=["feature/x-delegate", "feature/x-other"],
        )
        # Neither old resolver knows working branches: core answers the
        # conventional path, which does not exist, and the branch-plan
        # resolver answers no plan at all.
        assert _old_core(repo) != plan
        assert _old_refs(repo).path is None

        binding = resolve(repo)
        assert binding == Binding("bound", "x", plan, "working", None, "binding")

    def test_the_integration_branch_binds_with_role_integration(self, tmp_path):
        repo = _repo(tmp_path, "feature/x")
        plan = _plan(repo, "build-plan-x.md", scope="x", branch="feature/x", working=[])
        assert resolve(repo) == Binding("bound", "x", plan, "integration", None, "binding")

    def test_a_scratch_worktree_forked_from_a_bound_branch_is_unbound(self, tmp_path):
        """BR6: a harness scratch worktree resolves no unit — it builds, the
        coordinator governs. The old resolvers happen to answer "no plan" here
        because the plan declares a branch; they cannot say WHY, which is what
        the Stop hook needs to arm no gate (#648)."""
        repo = _repo(tmp_path, "feature/x")
        _plan(repo, "build-plan-x.md", scope="x", branch="feature/x")
        assert resolve(repo).state == "bound"
        scratch = _scratch_worktree(repo)
        assert _old_core(scratch) != resolve(repo).plan_path
        assert _old_refs(scratch).path is None

        binding = resolve(scratch)
        assert binding.state == "unbound"
        assert "scratch worktree (agent)" in binding.reason

    def test_a_scratch_worktree_in_a_legacy_window_repo_is_still_unbound(self, tmp_path):
        """The red half of the scratch shape: inside the legacy window the old
        resolvers serve the conventional plan to the scratch tree, so a
        delegate's Stop armed the coordinator's gate."""
        repo = _repo(tmp_path, "feature/x")
        plan = _plan(repo, "build-plan.md", scope="lonely")
        scratch = _scratch_worktree(repo)
        assert _old_core(scratch) == scratch / ".prawduct" / "artifacts" / "build-plan.md"
        assert _old_refs(scratch).path is not None

        assert resolve(scratch).state == "unbound"
        assert resolve(repo).plan_path == plan  # the primary still binds

    def test_detached_head_is_unbound_and_says_so(self, tmp_path):
        """BR3/BR6: a detached HEAD has no branch to be claimed. The old
        resolver fell through to the pointer here (pinned by
        ``test_build_plan_resolution.test_detached_head_falls_through_to_the_scalar``),
        which Chunk 06 rewrites when it becomes a shim."""
        repo = _repo(tmp_path, "feat/x")
        plan = _plan(repo, "build-plan.md", scope="lonely")
        head = _git(repo, "rev-parse", "HEAD").stdout.strip()
        _git(repo, "checkout", "-q", "--detach", head)
        assert _old_core(repo) == plan

        binding = resolve(repo)
        assert binding.state == "unbound"
        assert binding.reason == "HEAD is detached, so no branch can be claimed"

    def test_outside_a_work_tree_is_unbound_and_says_so(self, tmp_path):
        project = tmp_path / "plain"
        (project / ".prawduct" / "artifacts").mkdir(parents=True)
        (project / ".prawduct" / "project-state.yaml").write_text("")
        plan = _plan(project, "build-plan.md", scope="lonely")
        assert _old_core(project) == plan

        binding = resolve(project)
        assert binding.state == "unbound"
        assert binding.reason == "not inside a git work tree, so no branch can be claimed"


# ---------------------------------------------------------------------------
# The legacy window: both halves
# ---------------------------------------------------------------------------


class TestLegacyWindow:
    def test_a_plan_declaring_a_branch_is_never_served_by_the_pointer(self, tmp_path):
        repo = _repo(tmp_path, "feat/me", "active_build_plan: artifacts/other-plan.md\n")
        _plan(repo, "other-plan.md", scope="other", branch="feature/other")
        # Already refused by the old core resolver since #1049 (the one route
        # that fix closed); `resolve()` makes it the whole rule.
        assert _old_core(repo) is None

        assert resolve(repo).state == "unbound"

    def test_a_plan_declaring_a_branch_is_never_served_by_the_default(self, tmp_path):
        repo = _repo(tmp_path, "feat/me")
        _plan(repo, "build-plan.md", scope="other", branch="feature/other")
        assert _old_core(repo) is None
        assert resolve(repo).state == "unbound"

    def test_one_claim_anywhere_closes_the_window_for_the_whole_repo(self, tmp_path):
        """The pointer names a plan that declares no branch, but another live
        plan does declare one: this repo binds by claims, so the pointer
        answers nothing. The old resolver still served the pointed plan."""
        repo = _repo(tmp_path, "feat/me", "active_build_plan: artifacts/old-plan.md\n")
        old_plan = _plan(repo, "old-plan.md", scope="old")
        _plan(repo, "build-plan-new.md", scope="new", branch="feature/new")
        assert _old_core(repo) == old_plan

        binding = resolve(repo)
        assert binding == Binding(
            "unbound", None, None, None, "no live plan claims `feat/me`", "none"
        )

    def test_an_archived_claim_does_not_close_the_window(self, tmp_path):
        """Archived plans are history: the 78 archived plans in this repo that
        declare a branch must not end a live pointer-only plan's window."""
        repo = _repo(tmp_path, "feat/me")
        plan = _plan(repo, "build-plan.md", scope="lonely")
        _plan(repo, "archive/build-plan-done.md", scope="done", branch="feature/done")
        binding = resolve(repo)
        assert (binding.state, binding.chosen_by, binding.plan_path) == (
            "bound", "legacy-default", plan,
        )

    def test_a_pointer_naming_an_archived_plan_binds_nothing(self, tmp_path):
        repo = _repo(tmp_path, "feat/me", "active_build_plan: artifacts/archive/old.md\n")
        _plan(repo, "archive/old.md", scope="old")
        assert resolve(repo).state == "unbound"

    def test_a_pointer_naming_a_missing_plan_binds_nothing(self, tmp_path):
        repo = _repo(tmp_path, "feat/me", "active_build_plan: artifacts/gone.md\n")
        # The old resolver returns the path and leaves "does it exist" to each
        # of its callers; a binding answers the question once.
        assert _old_core(repo) == repo / ".prawduct" / "artifacts" / "gone.md"
        assert resolve(repo).state == "unbound"

    def test_a_non_plan_artifact_at_the_default_path_binds_nothing(self, tmp_path):
        repo = _repo(tmp_path, "feat/me")
        _plan(repo, "build-plan.md", scope="notes", artifact="discovery")
        assert resolve(repo).state == "unbound"

    def test_a_legacy_plan_without_a_scope_still_binds_with_none(self, tmp_path):
        """Pre-identity plans exist on consumers; the window exists for them.
        The binding names the file and no scope rather than inventing one."""
        repo = _repo(tmp_path, "feat/me")
        plan = _plan(repo, "build-plan.md", scope=None)
        binding = resolve(repo)
        assert (binding.state, binding.scope, binding.plan_path) == ("bound", None, plan)
        assert binding.chosen_by == "legacy-default"


# ---------------------------------------------------------------------------
# Claims: what counts, what breaks
# ---------------------------------------------------------------------------


class TestClaims:
    def test_a_claimant_without_a_scope_is_broken_not_unbound(self, tmp_path):
        """A plan that claims the branch but names no unit governed it under
        the old resolver. Answering "unbound" would disarm every gate it armed
        yesterday — authority fails closed, so the claim is reported broken."""
        repo = _repo(tmp_path, "feature/x")
        plan = _plan(repo, "build-plan-x.md", scope=None, branch="feature/x")
        assert _old_core(repo) == plan

        binding = resolve(repo)
        assert binding.state == "broken"
        assert "declares no `scope:`" in binding.reason

    def test_an_archived_plan_claims_nothing(self, tmp_path):
        repo = _repo(tmp_path, "feature/x")
        _plan(repo, "archive/build-plan-x.md", scope="x", branch="feature/x")
        _plan(repo, "build-plan-live.md", scope="live", branch="feature/live")
        assert resolve(repo).state == "unbound"

    def test_a_non_plan_artifact_cannot_claim(self, tmp_path):
        repo = _repo(tmp_path, "feature/x")
        _plan(repo, "notes.md", scope="x", branch="feature/x", artifact="discovery")
        assert resolve(repo).state == "unbound"

    def test_a_nested_plan_can_claim(self, tmp_path):
        repo = _repo(tmp_path, "feature/x")
        plan = _plan(repo, "plans/x/build-plan.md", scope="x", branch="feature/x")
        assert resolve(repo).plan_path == plan

    def test_a_plan_naming_its_own_branch_twice_is_one_claimant(self, tmp_path):
        repo = _repo(tmp_path, "feature/x")
        plan = _plan(repo, "build-plan-x.md", scope="x", branch="feature/x", working=["feature/x"])
        assert resolve(repo) == Binding("bound", "x", plan, "integration", None, "binding")

    def test_a_working_branch_claimed_by_two_plans_is_broken(self, tmp_path):
        repo = _repo(tmp_path, "feature/shared")
        _plan(repo, "build-plan-a.md", scope="a", branch="feature/a", working=["feature/shared"])
        _plan(repo, "build-plan-b.md", scope="b", branch="feature/b", working=["feature/shared"])
        assert resolve(repo).state == "broken"

    def test_an_unparseable_working_branches_declaration_claims_nothing(self, tmp_path):
        """Flow style is a real declaration this reader cannot read; a partial
        list would bind some of what was declared and silently drop the rest,
        so it binds none. Minting validates the shape where it is written."""
        repo = _repo(tmp_path, "feature/x-wip")
        path = repo / ".prawduct" / "artifacts" / "build-plan-x.md"
        path.write_text(
            "---\nartifact: build-plan\nscope: x\nbranch: feature/x\n"
            "working-branches: [feature/x-wip]\n---\n\n## Status\n\n- [ ] Chunk 01: a\n"
        )
        assert resolve(repo).state == "unbound"

    def test_an_explicit_branch_skips_the_probe_but_not_the_scratch_test(self, tmp_path):
        """A caller that has already read the branch passes it. The scratch
        test is then made against THAT branch through the same decision
        function the ephemeral guard uses (#648: an agent-path tree on a named
        branch is durable; on the scratch branch it is not), so resolver and
        guard cannot disagree about one tree."""
        repo = _repo(tmp_path, "main")
        plan = _plan(repo, "build-plan-x.md", scope="x", branch="feature/x")
        assert resolve(repo).state == "unbound"
        assert resolve(repo, branch="feature/x").plan_path == plan
        scratch = _scratch_worktree(repo)
        assert resolve(scratch, branch="worktree-agent-a287823214767feaa").state == "unbound"
        as_named = resolve(scratch, branch="feature/x")
        assert as_named.state == "bound"
        assert as_named.plan_path == scratch / ".prawduct" / "artifacts" / "build-plan-x.md"


# ---------------------------------------------------------------------------
# Cost: no network, the archive never read
# ---------------------------------------------------------------------------


class TestCost:
    @pytest.mark.parametrize("window", ["closed", "open"])
    def test_the_archive_directory_is_never_read(self, tmp_path, monkeypatch, window):
        """BP9/NF1: the walk runs at every session boundary. An archived plan
        claiming this very branch, and a pointer naming an archived plan, must
        both cost no read — pruned at directory level, not filtered after.

        Both window states, because they take different routes to "unbound":
        with a live claim in the repo the pointer is never consulted, and with
        none the legacy step must refuse the archived file BEFORE opening it."""
        repo = _repo(tmp_path, "feature/x", "active_build_plan: artifacts/archive/old.md\n")
        _plan(repo, "archive/old.md", scope="old")
        _plan(repo, "archive/build-plan-x.md", scope="x", branch="feature/x")
        _plan(repo, "plans/x/archive/build-plan-x.md", scope="x2", branch="feature/x")
        live = _plan(
            repo, "build-plan-live.md", scope="live",
            branch="feature/live" if window == "closed" else None,
        )
        opened: list[str] = []
        real_open = io.open

        def recording_open(file, *args, **kwargs):
            opened.append(str(file))
            return real_open(file, *args, **kwargs)

        monkeypatch.setattr(io, "open", recording_open)
        monkeypatch.setattr("builtins.open", recording_open)
        binding = resolve(repo)
        assert binding.state == "unbound"
        # The instrument saw the live plan, so a clean archive is a finding.
        assert str(live) in opened
        assert [p for p in opened if "/archive/" in p] == []

    def test_no_network(self, tmp_path, monkeypatch):
        def refuse(*_args, **_kwargs):
            raise AssertionError("resolve() opened a socket")

        monkeypatch.setattr(socket, "socket", refuse)
        monkeypatch.setattr(socket, "create_connection", refuse)
        repo = _repo(tmp_path, "feature/x")
        _plan(repo, "build-plan-x.md", scope="x", branch="feature/x")
        assert resolve(repo).state == "bound"
