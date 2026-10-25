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

import os
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


def _raw_plan(repo: Path, rel: str, extra_frontmatter: str) -> Path:
    """A plan claiming ``feature/x`` as scope ``x``, with ``extra_frontmatter``
    written verbatim after the claim — for shapes ``_plan`` deliberately cannot
    spell (flow style, malformed keys)."""
    path = repo / ".prawduct" / "artifacts" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nartifact: build-plan\nscope: x\nbranch: feature/x\n{extra_frontmatter}"
        "---\n\n## Status\n\n- [ ] Chunk 01: a\n"
    )
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
        """The design's six, then ``claimants`` — added last with a default so
        every positional construction written against the six stays valid."""
        assert [f.name for f in fields(Binding)] == [
            "state", "scope", "plan_path", "role", "reason", "chosen_by", "claimants",
        ]

    def test_six_positional_fields_still_construct_with_no_claimants(self):
        assert Binding("unbound", None, None, None, "x", "none").claimants == ()

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
        assert binding.claimants == (plan,)
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
        assert binding.claimants == (a, b)

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
        assert binding == Binding("bound", "x", plan, "working", None, "binding", (plan,))

    def test_the_integration_branch_binds_with_role_integration(self, tmp_path):
        repo = _repo(tmp_path, "feature/x")
        plan = _plan(repo, "build-plan-x.md", scope="x", branch="feature/x", working=[])
        assert resolve(repo) == Binding(
            "bound", "x", plan, "integration", None, "binding", (plan,)
        )

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
        answers nothing. The old resolver still served the pointed plan.

        The operator still HAS that plan, so the reason names it and the bind
        command — "no live plan claims" alone reads as "no plan exists"."""
        repo = _repo(tmp_path, "feat/me", "active_build_plan: artifacts/old-plan.md\n")
        old_plan = _plan(repo, "old-plan.md", scope="old")
        _plan(repo, "build-plan-new.md", scope="new", branch="feature/new")
        assert _old_core(repo) == old_plan

        binding = resolve(repo)
        assert (binding.state, binding.plan_path, binding.chosen_by) == ("unbound", None, "none")
        assert binding.reason.startswith("no live plan claims `feat/me` — `active_build_plan` names old-plan.md")
        assert f"`{work_unit.BIND_COMMAND} old-plan.md --branch feat/me`" in binding.reason

    def test_a_pointer_only_plan_that_is_not_pointed_at_gets_no_remedy(self, tmp_path):
        """Control for the remedy: a branch-less plan the pointer does NOT name
        is not the operator's plan for this branch, so the reason stays bare."""
        repo = _repo(tmp_path, "feat/me")
        _plan(repo, "old-plan.md", scope="old")
        _plan(repo, "build-plan-new.md", scope="new", branch="feature/new")
        assert resolve(repo).reason == "no live plan claims `feat/me`"

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

    def test_a_pointer_naming_a_missing_plan_binds_nothing_and_names_the_path(self, tmp_path):
        repo = _repo(tmp_path, "feat/me", "active_build_plan: artifacts/gone.md\n")
        # The old resolver returns the path and leaves "does it exist" to each
        # of its callers; a binding answers the question once, and says which
        # file the pointer resolved to and what would bind this branch.
        assert _old_core(repo) == repo / ".prawduct" / "artifacts" / "gone.md"
        binding = resolve(repo)
        assert binding.state == "unbound"
        assert binding.reason.startswith("no live plan claims `feat/me` — `active_build_plan` names artifacts/gone.md")
        assert f"`{work_unit.BIND_COMMAND} <plan> --branch feat/me`" in binding.reason

    def test_a_missing_conventional_file_is_the_plain_unbound(self, tmp_path):
        """Control: no pointer and no ``build-plan.md`` is the ordinary case,
        not a dangling declaration, so nothing is named."""
        repo = _repo(tmp_path, "feat/me")
        assert resolve(repo).reason == "no live plan claims `feat/me`"

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
    def test_a_claimant_without_a_scope_is_bound_with_a_reason(self, tmp_path):
        """A plan that claims the branch but names no unit governed it under
        the old resolver, and nothing is reinterpreted until the repo migrates
        (MG1): it still binds, with no scope and a reason naming the omission.
        `broken` would change what its gates do; `unbound` would disarm them."""
        repo = _repo(tmp_path, "feature/x")
        plan = _plan(repo, "build-plan-x.md", scope=None, branch="feature/x")
        assert _old_core(repo) == plan

        binding = resolve(repo)
        assert binding == Binding(
            "bound", None, plan, "integration",
            "build-plan-x.md claims `feature/x` but declares no `scope:`, so facts "
            "about this work record no unit — add one",
            "binding", (plan,),
        )

    def test_a_scoped_claimant_has_nothing_to_explain(self, tmp_path):
        repo = _repo(tmp_path, "feature/x")
        _plan(repo, "build-plan-x.md", scope="x", branch="feature/x")
        assert resolve(repo).reason is None

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
        assert resolve(repo) == Binding(
            "bound", "x", plan, "integration", None, "binding", (plan,)
        )

    def test_a_working_branch_claimed_by_two_plans_is_broken(self, tmp_path):
        repo = _repo(tmp_path, "feature/shared")
        _plan(repo, "build-plan-a.md", scope="a", branch="feature/a", working=["feature/shared"])
        _plan(repo, "build-plan-b.md", scope="b", branch="feature/b", working=["feature/shared"])
        assert resolve(repo).state == "broken"

    @pytest.mark.parametrize("flow", ["[feature/x-wip, feature/x-other]", '["feature/x-wip", feature/x-other]'])
    def test_a_flow_style_working_branches_list_binds_the_working_branch(self, tmp_path, flow):
        """``[a, b]`` is the natural encoding of a short list and means what the
        block form means — refusing it would be a fail-close on a model-written
        seam, not safety."""
        repo = _repo(tmp_path, "feature/x-wip")
        path = _raw_plan(repo, "build-plan-x.md", f"working-branches: {flow}\n")
        assert resolve(repo) == Binding("bound", "x", path, "working", None, "binding", (path,))

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
# Authority fails closed: a plan that cannot be read is broken, not absent
# ---------------------------------------------------------------------------


class TestUnreadablePlanIsBroken:
    """A binding is a verdict's input (architecture.md § Direction: authority
    fails closed). A live plan the resolver cannot read MIGHT claim this
    branch; skipping it resolves as though it were absent, and absence is what
    disarms the gates — so the answer is ``broken``, naming the file."""

    def test_an_unparseable_working_branches_declaration_is_broken(self, tmp_path):
        """Shipped as fail-open: this shape resolved ``unbound`` and the
        working branch built with no gate armed."""
        repo = _repo(tmp_path, "feature/x-wip")
        path = _raw_plan(repo, "build-plan-x.md", "working-branches:\n  nested: map\n")
        binding = resolve(repo)
        assert (binding.state, binding.plan_path, binding.chosen_by) == ("broken", None, "none")
        assert binding.claimants == (path,)
        assert binding.reason == (
            "1 live plan cannot be read — build-plan-x.md (`working-branches:` is not a "
            "list of branch names) — so whether it claims `feature/x-wip` is unknown and "
            "no binding can be decided; repair the file"
        )

    @pytest.mark.parametrize("shape", ["branch: [feature/x, feature/y]\n", "branch:\n  name: feature/x\n"])
    def test_a_branch_that_is_not_one_name_is_broken(self, tmp_path, shape):
        """The scalar reader hands back ``"[feature/x, feature/y]"`` for the
        first and ``None`` for the second; one would claim a branch nobody has,
        the other nothing — both resolve a shape that has no meaning."""
        repo = _repo(tmp_path, "feature/x")
        path = repo / ".prawduct" / "artifacts" / "build-plan-x.md"
        path.write_text(f"---\nartifact: build-plan\nscope: x\n{shape}---\n\n## Status\n\n- [ ] Chunk 01: a\n")
        binding = resolve(repo)
        assert binding.state == "broken"
        assert "build-plan-x.md (`branch:` is not a single branch name)" in binding.reason
        assert binding.claimants == (path,)

    def test_unreadable_frontmatter_is_broken_and_the_pointer_is_not_served(self, tmp_path):
        """The pointer names a live plan declaring no branch and nothing else
        claims one — the legacy route WOULD bind it. A second plan whose
        frontmatter never closes may hold a claim nobody can read, so the
        route does not run: step 5 is reachable only when every live plan read
        cleanly. The control (fix the file) shows the pointer qualifying."""
        repo = _repo(tmp_path, "feat/me", "active_build_plan: artifacts/v2-plan.md\n")
        _plan(repo, "v2-plan.md", scope="v2")
        bad = repo / ".prawduct" / "artifacts" / "build-plan-x.md"
        bad.write_text("---\nartifact: build-plan\nscope: x\nbranch: feat/me\n\n## Status\n\n- [ ] Chunk 01: a\n")

        binding = resolve(repo)
        assert (binding.state, binding.plan_path, binding.chosen_by) == ("broken", None, "none")
        assert binding.claimants == (bad,)
        assert binding.reason == (
            "1 live plan cannot be read — build-plan-x.md (its frontmatter block never "
            "closes) — so whether it claims `feat/me` is unknown and no binding can be "
            "decided; repair the file"
        )
        bad.unlink()
        assert resolve(repo).chosen_by == "legacy-pointer"

    def test_unreadable_frontmatter_is_broken_even_beside_a_clean_claimant(self, tmp_path):
        """One clean claimant plus one unreadable plan is not "bound": the
        unreadable one may be the second claimant that makes it broken."""
        repo = _repo(tmp_path, "feature/x")
        _plan(repo, "build-plan-x.md", scope="x", branch="feature/x")
        bad = repo / ".prawduct" / "artifacts" / "build-plan-y.md"
        bad.write_text("---\nartifact: build-plan\nscope: y\nbranch: feature/y\n\n## Status\n")
        assert resolve(repo).state == "broken"
        assert resolve(repo).claimants == (bad,)

    def test_a_plan_named_file_that_is_not_text_is_broken(self, tmp_path):
        repo = _repo(tmp_path, "feature/x")
        _plan(repo, "build-plan-x.md", scope="x", branch="feature/x")
        bad = repo / ".prawduct" / "artifacts" / "build-plan-y.md"
        bad.write_bytes(b"\xff\xfe---\nbranch: feature/x\n---\n")
        binding = resolve(repo)
        assert binding.state == "broken"
        assert "build-plan-y.md (not UTF-8 text)" in binding.reason
        assert binding.claimants == (bad,)

    def test_the_file_the_pointer_names_is_plan_shaped_whatever_its_name(self, tmp_path):
        repo = _repo(tmp_path, "feature/x", "active_build_plan: artifacts/v2-plan.md\n")
        _plan(repo, "build-plan-x.md", scope="x", branch="feature/x")
        bad = repo / ".prawduct" / "artifacts" / "v2-plan.md"
        bad.write_bytes(b"\xff\xfe")
        binding = resolve(repo)
        assert binding.state == "broken"
        assert binding.claimants == (bad,)

    @pytest.mark.parametrize(
        "name, body",
        [
            ("architecture.md", b"\xff\xfe not text"),
            ("discovery-notes.md", "---\nA note that opens with a horizontal rule\n\nprose\n".encode()),
        ],
    )
    def test_an_unreadable_document_that_is_not_a_plan_breaks_nothing(self, tmp_path, name, body):
        """`artifacts/` holds the repo's other documents too (~70 here); one bad
        byte in a note, or a note opening with a `---` rule, must not fail
        every checkout closed. Only a file that could hold a claim — named
        like a plan, named by the pointer, or at the conventional path — does."""
        repo = _repo(tmp_path, "feature/x")
        plan = _plan(repo, "build-plan-x.md", scope="x", branch="feature/x")
        (repo / ".prawduct" / "artifacts" / name).write_bytes(body)
        binding = resolve(repo)
        assert (binding.state, binding.plan_path) == ("bound", plan)

    def test_two_unreadable_plans_are_both_named(self, tmp_path):
        repo = _repo(tmp_path, "feature/x")
        a = _raw_plan(repo, "build-plan-a.md", "working-branches: nope\n")
        b = _raw_plan(repo, "build-plan-b.md", "working-branches:\n  - \n")
        binding = resolve(repo)
        assert binding.state == "broken"
        assert binding.reason.startswith("2 live plans cannot be read — build-plan-a.md (")
        assert binding.claimants == (a, b)

    def test_a_file_with_no_frontmatter_at_all_declares_nothing(self, tmp_path):
        """Control: absence is not malformation. A note with no block claims
        nothing and breaks nothing; the legacy default may still serve it."""
        repo = _repo(tmp_path, "feat/me")
        plan = repo / ".prawduct" / "artifacts" / "build-plan.md"
        plan.write_text("# Build plan\n\n## Status\n\n- [ ] Chunk 01: a\n")
        (repo / ".prawduct" / "artifacts" / "notes.md").write_text("just prose\n")
        binding = resolve(repo)
        assert (binding.state, binding.chosen_by, binding.plan_path) == ("bound", "legacy-default", plan)

    def test_an_archived_unreadable_plan_breaks_nothing(self, tmp_path):
        repo = _repo(tmp_path, "feature/x")
        plan = _plan(repo, "build-plan-x.md", scope="x", branch="feature/x")
        (repo / ".prawduct" / "artifacts" / "archive").mkdir()
        (repo / ".prawduct" / "artifacts" / "archive" / "old.md").write_bytes(b"\xff\xfe")
        assert resolve(repo).plan_path == plan


class TestProbeFailures:
    def test_a_failed_git_probe_is_unbound_and_serves_no_plan(self, tmp_path, monkeypatch):
        """``current_branch`` answers ``None`` for a detached HEAD AND for git
        failing outright; with no common dir either, the checkout is outside
        any work tree. Either way no branch exists to be claimed, and the plan
        that would bind the branch is not served."""
        repo = _repo(tmp_path, "feature/x")
        _plan(repo, "build-plan-x.md", scope="x", branch="feature/x")
        assert resolve(repo).state == "bound"  # control: the probe is what changes the answer
        monkeypatch.setattr(work_unit.gitstate, "current_branch", lambda _d: None)
        monkeypatch.setattr(work_unit.gitstate, "git_common_dir", lambda _d: None)
        binding = resolve(repo)
        assert binding == Binding(
            "unbound", None, None, None,
            "not inside a git work tree, so no branch can be claimed", "none",
        )


# ---------------------------------------------------------------------------
# Cost: no network, the archive never read
# ---------------------------------------------------------------------------


class TestCost:
    @pytest.mark.parametrize("window", ["closed", "open"])
    def test_the_archive_directory_is_never_walked(self, tmp_path, monkeypatch, window):
        """BP9/NF1: the walk runs at every session boundary. An archived plan
        claiming this very branch, and a pointer naming an archived plan, must
        both cost nothing — pruned at directory level, not filtered after.

        The requirement is about the WALK, so the instrument is the directory
        listing (``os.walk`` lists through ``os.scandir``), not the file opens
        that usually accompany it: a walker that descends the archive and
        discards what it found opens nothing and still pays for every plan the
        repo has ever completed.

        Both window states, because they take different routes to "unbound":
        with a live claim in the repo the pointer is never consulted, and with
        none the legacy step must refuse the archived file before touching it."""
        repo = _repo(tmp_path, "feature/x", "active_build_plan: artifacts/archive/old.md\n")
        _plan(repo, "archive/old.md", scope="old")
        _plan(repo, "archive/build-plan-x.md", scope="x", branch="feature/x")
        _plan(repo, "plans/x/archive/build-plan-x.md", scope="x2", branch="feature/x")
        _plan(
            repo, "plans/x/build-plan-live.md", scope="live",
            branch="feature/live" if window == "closed" else None,
        )
        artifacts = repo / ".prawduct" / "artifacts"
        listed: list[Path] = []
        real_scandir = os.scandir

        def recording_scandir(path=".", *args, **kwargs):
            listed.append(Path(path))
            return real_scandir(path, *args, **kwargs)

        monkeypatch.setattr(os, "scandir", recording_scandir)
        binding = resolve(repo)
        assert binding.state == "unbound"
        # The instrument saw the walk reach the nested live plan's directory, so
        # a clean archive is a finding about pruning, not about a walk that
        # never ran.
        assert artifacts / "plans" / "x" in listed
        assert [p for p in listed if "archive" in p.parts] == []

    def test_no_network(self, tmp_path, monkeypatch):
        def refuse(*_args, **_kwargs):
            raise AssertionError("resolve() opened a socket")

        monkeypatch.setattr(socket, "socket", refuse)
        monkeypatch.setattr(socket, "create_connection", refuse)
        repo = _repo(tmp_path, "feature/x")
        _plan(repo, "build-plan-x.md", scope="x", branch="feature/x")
        assert resolve(repo).state == "bound"
