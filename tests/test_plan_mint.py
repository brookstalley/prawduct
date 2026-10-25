"""``lib.plan_mint`` — minting a unit's identity and binding a branch to it (#1050).

The acceptance oracle is the reader: whatever ``new``/``bind``/``join_working``
write, ``work_unit.resolve()`` must answer from it, and ``change_fragments``
must judge the stub. Each refusal is pinned by a fixture that would otherwise
produce the state the refusal exists to prevent — usually a ``broken`` binding,
or an identity spelled two ways — and asserts nothing was written.

Real git repos in a sterile env, as ``test_work_unit.py`` builds them: branch
creation, detached HEADs and scratch worktrees only exist in git.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import change_fragments, gitstate, plan_index, plan_mint, work_unit  # noqa: E402
from lib.plan_mint import PlanMintRefused  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _git_env(repo: Path) -> dict[str, str]:
    home = repo.parent / "_home"  # outside the repo: macOS pyc caches land under HOME
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


def _repo(tmp_path: Path, branch: str = "feature/1050-the-unit", state: str = "") -> Path:
    """A work tree cut from ``main`` onto ``branch``, with an empty ``.prawduct/``."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-qm", "seed")
    if branch != "main":
        _git(repo, "checkout", "-q", "-b", branch)
    prawduct = repo / ".prawduct"
    (prawduct / "artifacts").mkdir(parents=True)
    (prawduct / "project-state.yaml").write_text(state)
    return repo.resolve()


def _plan(repo: Path, rel: str, *, scope: str | None = "other-unit", branch: str | None = None,
          working: list[str] | None = None, newline: str = "\n") -> Path:
    path = repo / ".prawduct" / "artifacts" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = ["---", "artifact: build-plan"]
    if scope is not None:
        fm.append(f"scope: {scope}")
    if branch is not None:
        fm.append(f"branch: {branch}")
    if working is not None:
        fm.append("working-branches:" + ("" if working else " []"))
        fm.extend(f"  - {name}" for name in working)
    fm.append("---")
    text = "\n".join(fm) + "\n\n## Status\n\n- [ ] Chunk 01: a chunk\n"
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text.replace("\n", newline))
    return path


def _fragment(repo: Path, scope: str) -> Path:
    path = repo / change_fragments.FRAGMENT_DIR_REL / f"{scope}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(change_fragments.render_fragment(
        kind="fix", scope=scope, date="2026-10-24", title="t", narrative="n", consumer_note="none: x",
    ))
    return path


def _files(repo: Path) -> set[Path]:
    return {p for p in (repo / ".prawduct").rglob("*") if p.is_file()}


def _refused(code: str, call, repo: Path) -> PlanMintRefused:
    """Assert ``call`` refuses with ``code`` and that nothing under ``.prawduct`` moved."""
    before = {p: p.read_bytes() for p in _files(repo)}
    with pytest.raises(PlanMintRefused) as raised:
        call()
    assert raised.value.code == code, raised.value
    assert {p: p.read_bytes() for p in _files(repo)} == before
    return raised.value


# ---------------------------------------------------------------------------
# new — the acceptance criterion
# ---------------------------------------------------------------------------


class TestNewMintsWhatTheReadersAccept:
    def test_the_plan_binds_on_its_branch_with_its_scope(self, tmp_path):
        repo = _repo(tmp_path, state="base_branch: develop\n")
        result = plan_mint.new(repo, "the-unit", title="The unit lands")

        assert result.action == "minted"
        assert result.plan_path == repo / ".prawduct/artifacts/build-plan-the-unit.md"
        assert (result.branch, result.base, result.base_rule) == (
            "feature/1050-the-unit", "develop", "base_branch",
        )
        assert result.created_branch is False
        binding = work_unit.resolve(repo)
        assert (binding.state, binding.scope, binding.plan_path, binding.role, binding.chosen_by) == (
            "bound", "the-unit", result.plan_path, "integration", "binding",
        )
        assert binding.reason is None

    def test_the_frontmatter_is_in_the_form_the_resolver_parses(self, tmp_path):
        repo = _repo(tmp_path)
        text = plan_mint.new(repo, "the-unit").plan_path.read_text()
        fm = plan_index.frontmatter_lines(text)
        assert "scope: the-unit" in fm
        assert "branch: feature/1050-the-unit" in fm
        assert "base: main" in fm
        assert "working-branches: []" in fm
        assert f"last_validated: {date.today().isoformat()}" in fm
        # The template's example claim does not survive as a declaration, and its
        # body is what an author copying the template by hand would get.
        assert not any(line.startswith("scope: pantry") for line in fm)
        assert plan_index.is_build_plan(text)
        # Chunk status derives from review facts (#1051): the template carries no
        # `## Status` block any more, so a minted plan must not either — a block
        # here would be hand-authored state the readers import as legacy ticks.
        assert "## Build Chunks" in text
        assert "## Status" not in text

    def test_the_fragment_stub_shares_the_identity_and_is_refused_only_for_what_is_unwritten(
        self, tmp_path
    ):
        repo = _repo(tmp_path)
        result = plan_mint.new(repo, "the-unit", title="The unit lands", kind="fix")
        item = change_fragments.read_fragment_file(result.fragment_path)
        assert item.fragment is not None
        assert (item.fragment.scope, item.fragment.type, item.fragment.title) == (
            "the-unit", "fix", "The unit lands",
        )
        # The stub is not shippable as written — the narrative and the consumer
        # note are the author's — and nothing ELSE is wrong with it.
        assert sorted(p.code for p in item.problems) == ["empty-consumer-note", "empty-narrative"]

        text = result.fragment_path.read_text().replace(
            "---\n\n", "---\nWhat changed and why.\n", 1
        ).rstrip("\n") + "\nnone: internal\n"
        filled = change_fragments.check_fragment_text(text, result.fragment_path)
        assert filled.ok, filled.problems  # filled in, it validates against its own plan

    def test_an_absent_title_is_left_for_the_author_not_invented(self, tmp_path):
        repo = _repo(tmp_path)
        result = plan_mint.new(repo, "the-unit")
        codes = {p.code for p in change_fragments.read_fragment_file(result.fragment_path).problems}
        assert "missing-key" in codes

    def test_naming_a_branch_creates_it_from_the_base_and_binds_there(self, tmp_path):
        repo = _repo(tmp_path, branch="main")
        result = plan_mint.new(repo, "the-unit", branch="feature/new-one")
        assert result.created_branch is True
        assert (result.base, result.base_rule) == ("main", "main-family")
        assert gitstate.current_branch(repo) == "feature/new-one"
        binding = work_unit.resolve(repo)
        assert (binding.state, binding.scope, binding.role) == ("bound", "the-unit", "integration")

    def test_a_legacy_window_repo_may_mint_on_the_branch_its_pointer_serves(self, tmp_path):
        # The legacy binding is a fallback answering, not a claim: minting is how
        # such a repo starts having claims, and it closes the window.
        repo = _repo(tmp_path)
        _plan(repo, "build-plan.md", scope="old-unit")
        assert work_unit.resolve(repo).chosen_by == "legacy-default"
        plan_mint.new(repo, "the-unit")
        assert work_unit.resolve(repo).scope == "the-unit"


# ---------------------------------------------------------------------------
# new — refusals
# ---------------------------------------------------------------------------


class TestNewRefuses:
    def test_a_scope_that_is_not_a_slug(self, tmp_path):
        repo = _repo(tmp_path)
        _refused("bad-scope-slug", lambda: plan_mint.new(repo, "The_Unit"), repo)

    @pytest.mark.parametrize("where", ["live", "archived", "fragment", "history"])
    def test_a_scope_already_declared_anywhere(self, tmp_path, where):
        repo = _repo(tmp_path)
        if where == "live":
            _plan(repo, "build-plan-x.md", scope="the-unit")
        elif where == "archived":
            _plan(repo, "archive/build-plan-x.md", scope="the-unit")
        elif where == "fragment":
            _fragment(repo, "the-unit")
        else:
            archive = repo / ".prawduct" / "change-log-archive"
            archive.mkdir()
            (archive / "2026-03.md").write_text(
                "## 2026-03-01: shipped\n\n<!-- prawduct: type=fix | scope=the-unit | release=v1.0.0 -->\n\nbody\n"
            )
        _refused("scope-taken", lambda: plan_mint.new(repo, "the-unit"), repo)

    @pytest.mark.parametrize("neighbour", ["plan", "fragment"])
    def test_a_scope_one_spelling_away_from_a_plan_or_pending_fragment(self, tmp_path, neighbour):
        # Minting it would make the neighbour's own record ambiguous: the
        # fragment check would then refuse a file this call never touched.
        repo = _repo(tmp_path)
        if neighbour == "plan":
            _plan(repo, "build-plan-x.md", scope="work-binding")
        else:
            _fragment(repo, "work-binding")
        _refused("scope-near-taken", lambda: plan_mint.new(repo, "work-unit-binding"), repo)

    def test_an_unreadable_history_is_not_an_empty_one(self, tmp_path):
        repo = _repo(tmp_path)
        (repo / ".prawduct" / "change-log.md").mkdir()  # exists, cannot be read as text
        _refused("history-unreadable", lambda: plan_mint.new(repo, "the-unit"), repo)

    @pytest.mark.parametrize("claim", ["integration", "working"])
    def test_a_branch_a_live_plan_already_claims(self, tmp_path, claim):
        """The one way minting could make a `broken` binding — so it never does."""
        repo = _repo(tmp_path)
        if claim == "integration":
            _plan(repo, "build-plan-x.md", branch="feature/1050-the-unit")
        else:
            _plan(repo, "build-plan-x.md", branch="feature/parent", working=["feature/1050-the-unit"])
        err = _refused("branch-claimed", lambda: plan_mint.new(repo, "the-unit"), repo)
        assert "build-plan-x.md" in err.detail
        assert work_unit.resolve(repo).state == "bound"  # still one claimant, not two

    def test_a_second_mint_on_the_same_branch(self, tmp_path):
        repo = _repo(tmp_path)
        plan_mint.new(repo, "the-unit")
        _refused("branch-claimed", lambda: plan_mint.new(repo, "another-unit"), repo)

    def test_the_harness_scratch_branch(self, tmp_path):
        repo = _repo(tmp_path, branch="worktree-agent-a3a138988a630b3ff")
        _refused("scratch-branch", lambda: plan_mint.new(repo, "the-unit"), repo)

    def test_a_scratch_worktree_directory_even_on_a_named_branch_target(self, tmp_path):
        # The coordinator mints; a delegate in a scratch tree asking for a claim on
        # its own scratch branch is refused by the branch pattern, and naming a
        # scratch branch from anywhere is refused the same way.
        repo = _repo(tmp_path, branch="main")
        _refused(
            "scratch-branch",
            lambda: plan_mint.new(repo, "the-unit", branch="worktree-agent-0123456789"),
            repo,
        )

    def test_the_base_itself(self, tmp_path):
        repo = _repo(tmp_path, branch="develop", state="base_branch: develop\n")
        _refused("branch-is-base", lambda: plan_mint.new(repo, "the-unit"), repo)

    def test_a_detached_head(self, tmp_path):
        repo = _repo(tmp_path)
        _git(repo, "checkout", "-q", "--detach")
        _refused("no-branch", lambda: plan_mint.new(repo, "the-unit"), repo)

    def test_naming_a_branch_that_already_exists(self, tmp_path):
        repo = _repo(tmp_path, branch="main")
        _git(repo, "branch", "feature/exists")
        _refused(
            "branch-exists", lambda: plan_mint.new(repo, "the-unit", branch="feature/exists"), repo
        )
        assert gitstate.current_branch(repo) == "main"

    def test_a_base_that_does_not_exist_to_create_from(self, tmp_path):
        repo = _repo(tmp_path, branch="main")
        _refused(
            "base-not-found",
            lambda: plan_mint.new(repo, "the-unit", branch="feature/x", base="nowhere"),
            repo,
        )

    def test_a_plan_file_already_at_the_minted_path(self, tmp_path):
        repo = _repo(tmp_path)
        _plan(repo, "build-plan-the-unit.md", scope="something-else")
        _refused("file-exists", lambda: plan_mint.new(repo, "the-unit"), repo)

    def test_an_unknown_type(self, tmp_path):
        repo = _repo(tmp_path)
        _refused("bad-type", lambda: plan_mint.new(repo, "the-unit", kind="feat"), repo)


# ---------------------------------------------------------------------------
# new(working=True) — joining a bound unit
# ---------------------------------------------------------------------------


class TestJoinWorking:
    def _bound(self, tmp_path):
        repo = _repo(tmp_path, branch="feature/parent")
        plan = _plan(repo, "build-plan-parent.md", scope="parent", branch="feature/parent")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "plan")
        _git(repo, "checkout", "-q", "-b", "feature/parent-part")
        return repo, plan

    def test_the_checked_out_branch_becomes_a_working_branch_of_the_unit(self, tmp_path):
        repo, plan = self._bound(tmp_path)
        result = plan_mint.new(repo, "parent", working=True)
        assert (result.action, result.scope, result.branch) == ("working", "parent", "feature/parent-part")
        binding = work_unit.resolve(repo)
        assert (binding.state, binding.scope, binding.plan_path, binding.role) == (
            "bound", "parent", plan, "working",
        )
        # And the integration branch still binds the same plan.
        assert work_unit.resolve(repo, branch="feature/parent").role == "integration"
        # No fragment: the unit already has its one identity.
        assert not (repo / change_fragments.FRAGMENT_DIR_REL).exists()

    def test_a_second_working_branch_is_appended_and_a_repeat_is_unchanged(self, tmp_path):
        repo, plan = self._bound(tmp_path)
        plan_mint.new(repo, "parent", working=True)
        plan_mint.join_working(repo, "parent", branch="feature/parent-other")
        assert plan_mint.join_working(repo, "parent").action == "unchanged"
        fm = "\n".join(plan_index.frontmatter_lines(plan.read_text()))
        assert "working-branches:\n  - feature/parent-part\n  - feature/parent-other" in fm

    def test_an_empty_list_declaration_is_replaced_not_duplicated(self, tmp_path):
        repo = _repo(tmp_path, branch="feature/parent")
        plan = _plan(repo, "build-plan-parent.md", scope="parent", branch="feature/parent", working=[])
        plan_mint.join_working(repo, "parent", branch="feature/part")
        fm = plan_index.frontmatter_lines(plan.read_text())
        assert [line for line in fm if line.startswith("working-branches")] == ["working-branches:"]
        assert work_unit.resolve(repo, branch="feature/part").role == "working"

    def test_a_unit_that_claims_no_branch_is_refused(self, tmp_path):
        repo = _repo(tmp_path)
        _plan(repo, "build-plan-parent.md", scope="parent")
        _refused("unit-unbound", lambda: plan_mint.new(repo, "parent", working=True), repo)

    def test_a_broken_unit_is_refused(self, tmp_path):
        repo = _repo(tmp_path)
        _plan(repo, "build-plan-parent.md", scope="parent", branch="feature/parent")
        _plan(repo, "build-plan-rival.md", scope="rival", branch="feature/parent")
        _refused("unit-not-bound", lambda: plan_mint.new(repo, "parent", working=True), repo)

    def test_an_unknown_or_archived_unit_is_refused(self, tmp_path):
        repo = _repo(tmp_path)
        _refused("no-such-unit", lambda: plan_mint.new(repo, "parent", working=True), repo)
        _plan(repo, "archive/build-plan-parent.md", scope="parent", branch="feature/parent")
        err = _refused("no-such-unit", lambda: plan_mint.new(repo, "parent", working=True), repo)
        assert "archived" in err.detail

    def test_the_integration_branch_itself_is_refused(self, tmp_path):
        repo, _plan_path = self._bound(tmp_path)
        _refused(
            "branch-is-integration",
            lambda: plan_mint.join_working(repo, "parent", branch="feature/parent"),
            repo,
        )

    def test_a_branch_another_unit_claims_is_refused(self, tmp_path):
        repo, _plan_path = self._bound(tmp_path)
        _plan(repo, "build-plan-other.md", scope="other", branch="feature/parent-part")
        _refused("branch-claimed", lambda: plan_mint.new(repo, "parent", working=True), repo)

    def test_an_unparseable_list_is_refused_not_overwritten(self, tmp_path):
        repo = _repo(tmp_path, branch="feature/parent")
        plan = _plan(repo, "build-plan-parent.md", scope="parent", branch="feature/parent")
        plan.write_text(plan.read_text().replace("---\n\n", "working-branches: [a, b]\n---\n\n", 1))
        _refused(
            "working-branches-unparseable",
            lambda: plan_mint.join_working(repo, "parent", branch="feature/part"),
            repo,
        )


# ---------------------------------------------------------------------------
# bind
# ---------------------------------------------------------------------------


class TestBind:
    def test_binding_a_legacy_plan_ends_its_window(self, tmp_path):
        repo = _repo(tmp_path)
        plan = _plan(repo, "build-plan.md", scope="old-unit")
        assert work_unit.resolve(repo).chosen_by == "legacy-default"
        # The form the legacy advisory prints: relative to the artifacts dir.
        result = plan_mint.bind(repo, "build-plan.md", "feature/1050-the-unit")
        assert (result.action, result.scope, result.plan_path) == ("bound", "old-unit", plan)
        binding = work_unit.resolve(repo)
        assert (binding.state, binding.chosen_by, binding.scope) == ("bound", "binding", "old-unit")
        fm = plan_index.frontmatter_lines(plan.read_text())
        assert fm.index("branch: feature/1050-the-unit") == fm.index("scope: old-unit") + 1

    def test_a_null_branch_line_is_replaced_in_place(self, tmp_path):
        repo = _repo(tmp_path)
        plan = _plan(repo, "build-plan.md", scope="old-unit", branch="null")
        plan_mint.bind(repo, plan, "feature/1050-the-unit")
        fm = plan_index.frontmatter_lines(plan.read_text())
        assert [line for line in fm if line.startswith("branch:")] == ["branch: feature/1050-the-unit"]

    def test_crlf_line_endings_survive(self, tmp_path):
        repo = _repo(tmp_path)
        plan = _plan(repo, "build-plan.md", scope="old-unit", newline="\r\n")
        plan_mint.bind(repo, ".prawduct/artifacts/build-plan.md", "feature/1050-the-unit")
        raw = plan.read_bytes()
        assert b"branch: feature/1050-the-unit\r\n" in raw
        assert raw.count(b"\n") == raw.count(b"\r\n")

    def test_the_branch_already_claimed_by_this_plan_is_unchanged(self, tmp_path):
        repo = _repo(tmp_path)
        plan = _plan(repo, "build-plan.md", scope="u", branch="feature/1050-the-unit")
        assert plan_mint.bind(repo, plan, "feature/1050-the-unit").action == "unchanged"

    def test_a_plan_already_claiming_another_branch_is_refused(self, tmp_path):
        repo = _repo(tmp_path)
        plan = _plan(repo, "build-plan.md", scope="u", branch="feature/elsewhere")
        _refused("plan-claims-other-branch", lambda: plan_mint.bind(repo, plan, "feature/x"), repo)

    def test_a_second_claim_on_the_branch_is_refused(self, tmp_path):
        repo = _repo(tmp_path)
        _plan(repo, "build-plan-a.md", scope="a", branch="feature/1050-the-unit")
        plan = _plan(repo, "build-plan-b.md", scope="b")
        _refused(
            "branch-claimed", lambda: plan_mint.bind(repo, plan, "feature/1050-the-unit"), repo
        )

    def test_an_archived_plan_is_refused(self, tmp_path):
        repo = _repo(tmp_path)
        plan = _plan(repo, "archive/build-plan.md", scope="u")
        _refused("not-live", lambda: plan_mint.bind(repo, plan, "feature/x"), repo)

    def test_a_non_plan_is_refused(self, tmp_path):
        repo = _repo(tmp_path)
        doc = repo / ".prawduct" / "artifacts" / "notes.md"
        doc.write_text("---\nartifact: design-note\nscope: u\n---\n")
        _refused("not-a-plan", lambda: plan_mint.bind(repo, doc, "feature/x"), repo)

    def test_the_scratch_branch_is_refused(self, tmp_path):
        repo = _repo(tmp_path)
        plan = _plan(repo, "build-plan.md", scope="u")
        _refused(
            "scratch-branch", lambda: plan_mint.bind(repo, plan, "worktree-agent-0123456789"), repo
        )

    def test_a_branch_the_reader_would_truncate_is_refused_not_written(self, tmp_path):
        # Legal to git, but the frontmatter reader takes `#` as a comment, so the
        # plan would claim `feature/a` — a branch nobody named.
        repo = _repo(tmp_path)
        plan = _plan(repo, "build-plan.md", scope="u")
        _refused("unrepresentable", lambda: plan_mint.bind(repo, plan, "feature/a#b"), repo)

    def test_an_illegal_branch_name_is_refused(self, tmp_path):
        repo = _repo(tmp_path)
        plan = _plan(repo, "build-plan.md", scope="u")
        _refused("bad-branch-name", lambda: plan_mint.bind(repo, plan, "feature/a..b"), repo)


# ---------------------------------------------------------------------------
# default_base and suggest_scope
# ---------------------------------------------------------------------------


class TestDefaultBase:
    def test_the_repo_knob_wins_even_before_its_ref_is_fetched(self, tmp_path):
        repo = _repo(tmp_path, state="base_branch: develop\n")
        assert plan_mint.default_base(repo) == ("develop", "base_branch")

    def test_the_remote_default_outside_the_main_family(self, tmp_path):
        repo = _repo(tmp_path)
        _git(repo, "update-ref", "refs/remotes/origin/develop", "HEAD")
        _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/develop")
        assert plan_mint.default_base(repo) == ("develop", "origin-head")

    def test_the_main_family(self, tmp_path):
        repo = _repo(tmp_path)
        assert plan_mint.default_base(repo) == ("main", "main-family")

    def test_nothing_to_ask_falls_back_and_says_so(self, tmp_path):
        # The resolver's own last resort is `HEAD~1`, a commit, never a base.
        assert plan_mint.default_base(tmp_path) == ("main", "fallback")


@pytest.mark.parametrize("branch,expected", [
    ("feature/1050-work-unit-binding", "work-unit-binding"),
    ("fix/WU_Thing", "wu-thing"),
    ("feat/release-v3.7.1", "release-v3.7.1"),
    ("plans/foo/bar", "plans-foo-bar"),
    ("1050", "1050"),
    ("main", None),
    ("develop", None),
    ("release/v3.7.2", None),
    ("worktree-agent-a3a138988a630b3ff", None),
    ("feature/---", None),
    (None, None),
])
def test_suggest_scope_offers_a_slug_and_never_for_an_unbound_branch(tmp_path, branch, expected):
    repo = _repo(tmp_path, state="base_branch: develop\n")
    suggestion = plan_mint.suggest_scope(branch, repo)
    assert suggestion == expected
    if suggestion is not None:
        assert change_fragments.is_scope(suggestion)


def test_the_integration_roster_is_the_main_family_plus_the_repos_own_base(tmp_path):
    """One roster (R-11): `coverage.MAIN_FAMILY` and the repo's integration
    branch, never a second hand-kept list. `trunk` is unbound where the repo
    integrates onto it and an ordinary name where it does not — the control
    that shows the answer comes from the repo, not from a literal."""
    from lib import coverage

    trunk_repo = _repo(tmp_path / "t", state="base_branch: trunk\n")
    assert plan_mint.integration_branches(trunk_repo) == coverage.MAIN_FAMILY | {"trunk"}
    assert plan_mint.suggest_scope("trunk", trunk_repo) is None
    plain = _repo(tmp_path / "p")
    assert plan_mint.suggest_scope("trunk", plain) == "trunk"
    assert plan_mint.suggest_scope("master", plain) is None


def test_suggest_scope_is_only_a_suggestion():
    """D3: nothing in the library decides with it — its one consumer is the
    `plan new` CLI, which prints what it took. A library caller that bound
    through it would be name inference come back."""
    source = (ROOT / "lib" / "plan_mint.py").read_text()
    body_uses = [line for line in source.splitlines()
                 if "suggest_scope(" in line and not line.lstrip().startswith("def ")]
    assert body_uses == []


# ---------------------------------------------------------------------------
# known_scopes
# ---------------------------------------------------------------------------


def test_known_scopes_reads_plans_fragments_and_history(tmp_path):
    repo = _repo(tmp_path)
    _plan(repo, "build-plan-a.md", scope="live-plan")
    _plan(repo, "archive/build-plan-b.md", scope="archived-plan")
    _fragment(repo, "pending-fix")
    (repo / ".prawduct" / "change-log.md").write_text(
        "## 2026-03-01: x\n\n<!-- prawduct: type=fix | scope=shipped-fix | release=v1.0.0 -->\n\nb\n"
    )
    assert plan_mint.known_scopes(repo) == {"live-plan", "archived-plan", "pending-fix", "shipped-fix"}
