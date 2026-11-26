"""``review_lane``: the one reader of ``boundary_review:``.

Driven on real git repositories, because which value is in force is a question
about which tree holds it. The tests that matter most pin the strict direction:
a branch that adds ``per_release`` must not read it, and nothing but exactly
``per_release`` on the integration branch may.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from lib import core  # noqa: E402
from lib import coverage  # noqa: E402
from lib import review_lane  # noqa: E402

PLUGIN = Path(__file__).resolve().parent.parent / "plugin"
STATE = ".prawduct/project-state.yaml"
OPT_IN = "boundary_review: per_release\n"


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, timeout=15)
    assert proc.returncode == 0, f"git {args} failed: {proc.stderr}"
    return proc.stdout.strip()


def _state(repo: Path, text: str) -> None:
    path = repo / STATE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("project: demo\n" + text, encoding="utf-8")


def _commit(repo: Path, text: str, msg: str) -> str:
    _state(repo, text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "--allow-empty", "-m", msg)
    return _git(repo, "rev-parse", "HEAD")


def _repo(tmp_path: Path, on_main: str, *, branch: str = "main") -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", branch)
    _commit(repo, on_main, "base")
    return repo


def _feature(repo: Path, text: str) -> None:
    _git(repo, "checkout", "-q", "-b", "feat")
    _commit(repo, text, "work")


class TestReadFromTheIntegrationBranch:
    def test_a_value_on_the_integration_branch_is_in_force(self, tmp_path):
        repo = _repo(tmp_path, OPT_IN)
        _feature(repo, OPT_IN + "other: 1\n")
        policy = review_lane.boundary_review_policy(repo)
        assert policy.value == review_lane.PER_RELEASE
        assert policy.per_release
        assert policy.note == ""
        merge_base = _git(repo, "merge-base", "main", "HEAD")
        assert policy.source == f"merge-base {merge_base[:12]}"

    def test_a_branch_cannot_opt_itself_in(self, tmp_path):
        """The branch commits `per_release`; the integration branch does not.
        Read from the working tree or HEAD, this branch would buy its own lane."""
        repo = _repo(tmp_path, "")
        _feature(repo, OPT_IN)
        policy = review_lane.boundary_review_policy(repo)
        assert policy.value == review_lane.PER_PR
        assert "not yet on the integration branch" in policy.note
        assert "cannot opt itself in" in policy.note

    def test_an_uncommitted_opt_in_on_the_integration_branch_is_not_in_force(self, tmp_path):
        repo = _repo(tmp_path, "")
        _state(repo, OPT_IN)
        policy = review_lane.boundary_review_policy(repo)
        assert policy.value == review_lane.PER_PR
        assert "not yet on the integration branch" in policy.note

    def test_a_branch_may_opt_out(self, tmp_path):
        """Dropping the key on a branch is the stricter direction, so it counts."""
        repo = _repo(tmp_path, OPT_IN)
        _feature(repo, "boundary_review: per_pr\n")
        policy = review_lane.boundary_review_policy(repo)
        assert policy.value == review_lane.PER_PR
        assert "opt out, never in" in policy.note

    def test_the_head_tilde_one_fallback_authorises_nothing(self, tmp_path):
        """A `master` trunk with no `main` resolves only the moving fallback, whose
        merge-base is the branch's own previous commit."""
        repo = _repo(tmp_path, OPT_IN, branch="master")
        _commit(repo, OPT_IN, "work")
        assert coverage._resolve_base_branch(repo)[0] == coverage.MOVING_FALLBACK_BASE, "fixture"
        policy = review_lane.boundary_review_policy(repo)
        assert policy.value == review_lane.PER_PR
        assert policy.source == ""
        assert "no integration branch" in policy.note

    def test_a_branch_forked_while_the_base_opted_in_loses_it_when_the_base_reverts(self, tmp_path):
        """The merge-base still says `per_release`, and so does the branch; the
        integration branch has since gone back to `per_pr`. The tip narrows."""
        repo = _repo(tmp_path, OPT_IN)
        _feature(repo, OPT_IN + "other: 1\n")
        assert review_lane.boundary_review_policy(repo).per_release, "control: before the revert"
        _git(repo, "checkout", "-q", "main")
        _commit(repo, "boundary_review: per_pr\n", "back to per_pr")
        _git(repo, "checkout", "-q", "feat")
        policy = review_lane.boundary_review_policy(repo)
        assert policy.value == review_lane.PER_PR
        assert "tip (main) no longer declares `boundary_review: per_release`" in policy.note, policy

    def test_a_base_that_opted_in_after_the_fork_is_not_in_force_until_synced(self, tmp_path):
        repo = _repo(tmp_path, "")
        _feature(repo, OPT_IN)
        _git(repo, "checkout", "-q", "main")
        _commit(repo, OPT_IN, "main opts in")
        _git(repo, "checkout", "-q", "feat")
        policy = review_lane.boundary_review_policy(repo)
        assert policy.value == review_lane.PER_PR
        assert "sync the branch to take it" in policy.note, policy
        _git(repo, "merge", "-q", "--no-edit", "main")
        assert review_lane.boundary_review_policy(repo).per_release, "after the sync"

    @pytest.mark.parametrize("main_declares", [False, True], ids=["stack-opts-in", "control"])
    def test_a_stacked_unit_cannot_opt_in_through_its_unit_base(self, tmp_path, monkeypatch, main_declares):
        """Native review round 6, candidate 4: a unit stacked on `stack` (its
        plan's `base:`) used to read the policy at `stack`, so `stack` adding
        `per_release` unmerged authorised every unit cut from it. A branch may
        opt out of per_release, never in: the reading is at the repo's
        integration branch. Control: main declaring it puts the stack in force."""
        repo = _repo(tmp_path, OPT_IN if main_declares else "")
        _git(repo, "checkout", "-q", "-b", "stack")
        _commit(repo, OPT_IN, "stack opts in")
        _feature(repo, OPT_IN + "other: 1\n")
        monkeypatch.setattr(coverage, "_bound_plan_base", lambda _p: "stack")
        assert coverage._resolve_base_branch(repo)[0] == "stack", "fixture: the unit's own base"
        policy = review_lane.boundary_review_policy(repo)
        assert policy.per_release is main_declares, policy
        if not main_declares:
            assert "cannot opt itself in" in policy.note, policy

    def test_an_explicit_base_ref_is_the_one_read(self, tmp_path):
        repo = _repo(tmp_path, "")
        _git(repo, "checkout", "-q", "-b", "develop")
        _commit(repo, OPT_IN, "develop opts in")
        _feature(repo, OPT_IN)
        assert review_lane.boundary_review_policy(repo, "develop").per_release
        assert not review_lane.boundary_review_policy(repo, "main").per_release, "control"


class TestOnlyExactlyPerReleaseOptsIn:
    def test_absent_reads_per_pr_with_no_note(self, tmp_path):
        repo = _repo(tmp_path, "")
        _feature(repo, "other: 1\n")
        policy = review_lane.boundary_review_policy(repo)
        assert (policy.value, policy.note) == (review_lane.PER_PR, "")

    @pytest.mark.parametrize(
        "typo", ["per_relase", "Per_Release", "per-release", "release", "true", "per_release_batch"]
    )
    def test_a_typo_reads_per_pr_and_says_why(self, tmp_path, typo):
        line = f"boundary_review: {typo}\n"
        repo = _repo(tmp_path, line)
        _feature(repo, line)
        policy = review_lane.boundary_review_policy(repo)
        assert policy.value == review_lane.PER_PR, typo
        assert f"`boundary_review: {typo}`" in policy.note
        assert "not a value prawduct reads" in policy.note

    def test_a_typo_on_the_integration_branch_is_named_there(self, tmp_path):
        """The checkout's own value is valid (here, absent); the typo is the
        integration branch's, and the note says where it is."""
        repo = _repo(tmp_path, "boundary_review: per_relase\n")
        _feature(repo, "other: 1\n")
        policy = review_lane.boundary_review_policy(repo)
        assert policy.value == review_lane.PER_PR
        assert policy.note == (
            "`boundary_review: per_relase` on the integration branch is not a value prawduct "
            "reads (per_pr or per_release), so per_pr is in force"
        ), policy.note

    @pytest.mark.parametrize(
        "text", ["boundary_review:\n", "boundary_review: null\n", "boundary_review: ~\n"]
    )
    def test_a_null_or_empty_value_reads_per_pr(self, tmp_path, text):
        repo = _repo(tmp_path, text)
        _feature(repo, text)
        assert review_lane.boundary_review_policy(repo).value == review_lane.PER_PR, text

    def test_a_quoted_or_commented_value_is_the_yaml_value(self, tmp_path):
        """Quotes and an inline comment are YAML, not part of the value."""
        line = "boundary_review: 'per_release'  # moved to the release\n"
        repo = _repo(tmp_path, line)
        _feature(repo, line)
        assert review_lane.boundary_review_policy(repo).per_release

    def test_an_indented_key_is_not_the_top_level_one(self, tmp_path):
        line = "nested:\n  boundary_review: per_release\n"
        repo = _repo(tmp_path, line)
        _feature(repo, line)
        assert review_lane.boundary_review_policy(repo).value == review_lane.PER_PR


class TestTheBaseTipReader:
    def test_reads_the_named_revision(self, tmp_path):
        repo = _repo(tmp_path, OPT_IN)
        _feature(repo, "boundary_review: per_pr\n")
        assert review_lane.boundary_review_policy_at(repo, "main") == review_lane.Policy(
            review_lane.PER_RELEASE, "main"
        )
        assert review_lane.boundary_review_policy_at(repo, "feat").value == review_lane.PER_PR

    def test_a_working_tree_value_is_not_read(self, tmp_path):
        repo = _repo(tmp_path, "")
        _state(repo, OPT_IN)
        assert review_lane.boundary_review_policy_at(repo, "main").value == review_lane.PER_PR

    def test_a_typo_at_the_tip_reads_per_pr_and_says_why(self, tmp_path):
        repo = _repo(tmp_path, "boundary_review: per_relase\n")
        policy = review_lane.boundary_review_policy_at(repo, "main")
        assert policy.value == review_lane.PER_PR
        assert "not a value prawduct reads" in policy.note

    def test_an_unreadable_revision_reads_per_pr_and_says_so(self, tmp_path):
        repo = _repo(tmp_path, OPT_IN)
        policy = review_lane.boundary_review_policy_at(repo, "no-such-branch")
        assert policy.value == review_lane.PER_PR
        assert "no project-state.yaml reads at no-such-branch" in policy.note

    def test_absent_at_the_tip_has_no_note(self, tmp_path):
        repo = _repo(tmp_path, "")
        assert review_lane.boundary_review_policy_at(repo, "main") == review_lane.Policy(
            review_lane.PER_PR, "main"
        )


class TestTheMergedBranchReader:
    """``boundary_review_policy_of_merge``: the one combined reading for a branch
    that has already merged (the fix-tail deferral at release time). Both its
    merge-base and its tip must declare per_release; the working tree has no say."""

    @pytest.mark.parametrize("on_base, on_branch, expected", [
        (OPT_IN, OPT_IN, review_lane.PER_RELEASE),
        ("", OPT_IN, review_lane.PER_PR),  # a branch cannot opt itself in
        (OPT_IN, "boundary_review: per_pr\n", review_lane.PER_PR),  # it may opt out
    ], ids=["both", "branch-opts-in", "branch-opts-out"])
    def test_both_revisions_must_declare_it(self, tmp_path, on_base, on_branch, expected):
        repo = _repo(tmp_path, on_base)
        _feature(repo, on_branch)
        merge_base = _git(repo, "merge-base", "main", "feat")
        _git(repo, "checkout", "-q", "main")
        _state(repo, OPT_IN)  # the working tree, which must not count
        policy = review_lane.boundary_review_policy_of_merge(repo, merge_base, "feat")
        assert policy.value == expected, policy

    def test_a_tip_that_cannot_be_read_says_so(self, tmp_path):
        repo = _repo(tmp_path, OPT_IN)
        policy = review_lane.boundary_review_policy_of_merge(repo, _git(repo, "rev-parse", "HEAD"), "gone")
        assert policy.value == review_lane.PER_PR and "no project-state.yaml reads at gone" in policy.note

    def test_the_fix_tail_deferral_reads_it(self, tmp_path, monkeypatch):
        """W5: the deferral of a merged branch asks this reader, not its own
        combination: a per_pr answer from it is what the deferral obeys."""
        from lib import boundary_coverage as bc  # noqa: PLC0415
        from test_fix_tail_deferral import _merged  # noqa: PLC0415

        repo, merge = _merged(tmp_path)
        assert bc.classify_merge(repo, merge).classification == bc.TAIL_DEFERRED  # the control
        monkeypatch.setattr(review_lane, "boundary_review_policy_of_merge",
                            lambda *_a: review_lane.Policy(review_lane.PER_PR, "x"))
        assert bc.classify_merge(repo, merge).classification == bc.UNCOVERED


class TestTheReleasePolicyNeverRaises:
    def test_a_failed_read_falls_back_to_the_checkout_and_says_so(self, tmp_path, monkeypatch):
        repo = _repo(tmp_path, OPT_IN)

        def boom(_p):
            raise RuntimeError("read boom")

        monkeypatch.setattr(review_lane, "_release_policy", boom)
        policy = review_lane.release_policy(repo)
        assert (policy.value, policy.read_failed) == (review_lane.PER_RELEASE, True), policy
        assert "(RuntimeError: read boom)" in policy.note and "stands (per_release)" in policy.note
        _state(repo, "")
        policy = review_lane.release_policy(repo)
        assert (policy.value, policy.read_failed) == (review_lane.PER_PR, True), policy

    def test_a_read_that_works_is_not_marked_failed(self, tmp_path):
        repo = _repo(tmp_path, OPT_IN)
        assert review_lane.release_policy(repo).read_failed is False


class TestTheDocTemplateAndConstantAgree:
    """One key, written in three places: the constant the reader uses, the
    reference entry and the template hint."""

    def test_the_constant_names_the_key(self):
        assert core.BOUNDARY_REVIEW_KEY == "boundary_review"

    def test_the_reference_documents_the_key_and_both_values(self):
        text = (PLUGIN / "docs" / "project-state-keys.md").read_text(encoding="utf-8")
        # The heading names the key alone: the key-reference test reads every
        # snake_case word in a heading as a key the template must hint.
        heading = next(ln for ln in text.splitlines() if re.match(rf"## {core.BOUNDARY_REVIEW_KEY}\b", ln))
        section = text.split(heading, 1)[1].split("\n## ", 1)[0]
        for value in review_lane.VALUES:
            assert f"`{value}`" in section, value

    def test_uncommenting_the_template_hint_opts_in(self, tmp_path):
        lines = (PLUGIN / "templates" / "project-state.yaml").read_text(encoding="utf-8").splitlines()
        hints = [ln for ln in lines if ln.startswith(f"# {core.BOUNDARY_REVIEW_KEY}:")]
        assert len(hints) == 1, hints
        state, value = core.read_scalar_yaml_text(hints[0][2:] + "\n", core.BOUNDARY_REVIEW_KEY)
        assert (state, value) == (core.YAML_SCALAR_VALUE, review_lane.PER_RELEASE)

    def test_the_template_leaves_the_key_unset(self):
        """A scaffolded repo must start on the default."""
        text = (PLUGIN / "templates" / "project-state.yaml").read_text(encoding="utf-8")
        assert core.read_scalar_yaml_text(text, core.BOUNDARY_REVIEW_KEY)[0] == core.YAML_SCALAR_ABSENT
