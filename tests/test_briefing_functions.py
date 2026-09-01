"""Per-branch unit coverage for the lib/briefing functions (STH-9V4K ch.7).

The SessionStart briefing/handoff functions were extracted into `lib/briefing.py`
behavior-preserving (AST byte-identical to the pre-refactor hook). Before this,
they were exercised ONLY through the `clear` CLI integration path — their
conditional branches (WIP-format detection, worktree porcelain parsing, the
previous-session gate logic, the optional briefing sections, the handoff
assembly) had no direct coverage. These are characterization tests: they pin the
existing, long-standing behavior so a future edit to a now-isolated module can't
silently regress a branch the integration tests don't reach.

Pure/file-driven branches use tmp_path fixtures. The git-subprocess branches use
a real throwaway repo where the real interaction matters, and a monkeypatched
`subprocess.run` where it's the porcelain *parsing* that's regression-prone. The
gate/handoff functions that delegate to sibling lib modules monkeypatch those
siblings (the modules briefing imports), keeping each test to one function.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

import pytest

from lib import briefing, gates, gitstate


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _prawduct(tmp_path: Path) -> Path:
    p = tmp_path / ".prawduct"
    p.mkdir(exist_ok=True)
    return p


def _init_git_repo(path: Path, branch: str = "work") -> None:
    env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}

    def run(*args: str) -> None:
        subprocess.run(["git", *args], cwd=str(path), env=env,
                       capture_output=True, text=True, check=True)

    run("init", "-q")
    run("config", "user.email", "t@example.com")
    run("config", "user.name", "Test")
    run("checkout", "-q", "-b", branch)
    (path / "f.txt").write_text("x")
    run("add", ".")
    run("commit", "-q", "-m", "init commit")


class _FakeProc:
    def __init__(self, returncode: int = 0, stdout: str = ""):
        self.returncode = returncode
        self.stdout = stdout


def _plan(prawduct: Path, rel: str, body: str) -> Path:
    path = prawduct / "artifacts" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    return path


class TestBranchScopedPlanBriefing:
    """What the briefing says about `branch:`-declaring plans.

    All of it is advice — the briefing must still be produced whatever it finds.
    """

    def test_a_failed_resolution_is_attributed_not_swallowed(
        self, tmp_path: Path, monkeypatch
    ):
        """Advice fails soft; it does not fail silent.

        The contested-claim line is the ONLY surface that ever says a branch is
        contested, and the fail-closed route that used to backstop it is gone by
        design. It is emitted from inside a broad `except`, so without this test
        a refactor back to a bare `pass` restores the silence and nothing
        notices — which is the defect a previous review found here.
        """
        _init_git_repo(tmp_path, branch="work")
        prawduct = _prawduct(tmp_path)
        (prawduct / "project-state.yaml").write_text("")

        def _boom(_prawduct_dir):
            raise OSError("the plan directory could not be read")

        monkeypatch.setattr(briefing, "resolve_branch_claim", _boom)
        text = briefing.assemble_session_briefing(tmp_path, [])
        assert "== SESSION BRIEFING ==" in text, "the briefing must still be produced"
        assert "could not be reported" in text
        assert "OSError" in text, "the reader is owed what actually failed"

    def test_a_retained_plan_with_its_pointer_cleared_says_nothing(self, tmp_path: Path):
        """The gitflow retention window, after a branch-declaring plan merges.

        Its branch is deleted, so the claim resolves for nobody; with the pointer
        cleared, nothing resolves the finished plan and the briefing is silent.
        Leaving the pointer aimed at it is what produced an "archive the plan"
        advisory during the one window the PR skill says to retain it — an
        advisory whose only correct action was to ignore it.
        """
        _init_git_repo(tmp_path, branch="develop")
        prawduct = _prawduct(tmp_path)
        (prawduct / "project-state.yaml").write_text("")  # pointer cleared
        _plan(
            prawduct,
            "build-plan-shipped.md",
            "---\nartifact: build-plan\nbranch: feat/long-merged\n---\n\n"
            "## Status\n\n- [x] Chunk 01: shipped\n",
        )
        findings = briefing.staleness_scan(tmp_path)
        assert not any("archive the plan" in f for f in findings), findings
        assert "== SESSION BRIEFING ==" in briefing.assemble_session_briefing(
            tmp_path, findings
        )

    def test_the_same_plan_still_nags_when_the_pointer_names_it(self, tmp_path: Path):
        """The control, and the pointer-resolved case the rule keeps.

        Without it the assertion above passes on any repo where the advisory is
        broken rather than on one where the pointer was cleared.
        """
        _init_git_repo(tmp_path, branch="develop")
        prawduct = _prawduct(tmp_path)
        (prawduct / "project-state.yaml").write_text(
            "active_build_plan: artifacts/build-plan-shipped.md\n"
        )
        _plan(
            prawduct,
            "build-plan-shipped.md",
            "---\nartifact: build-plan\nbranch: feat/long-merged\n---\n\n"
            "## Status\n\n- [x] Chunk 01: shipped\n",
        )
        findings = briefing.staleness_scan(tmp_path)
        assert any("archive the plan" in f for f in findings), findings

    def test_a_plan_claiming_a_missing_branch_is_reported(self, tmp_path: Path):
        _init_git_repo(tmp_path, branch="work")
        prawduct = _prawduct(tmp_path)
        (prawduct / "project-state.yaml").write_text("")
        _plan(
            prawduct,
            "build-plan-gone.md",
            "---\nartifact: build-plan\nbranch: feat/long-merged\n---\n\n"
            "## Status\n\n- [ ] Chunk 01: a chunk\n",
        )
        findings = briefing.staleness_scan(tmp_path)
        assert any("feat/long-merged" in f and "not a branch in this repo" in f
                   for f in findings), findings

    def test_a_FINISHED_plan_claiming_a_missing_branch_says_nothing(self, tmp_path: Path):
        """The gitflow retention window, which is the whole point of the narrowing.

        A merged branch goes away, so a plan with every box ticked and a claim on
        a branch that is gone is the documented end state — `/prawduct:pr`'s Merge
        Flow "Confirm the bookkeeping merged WITH the PR" step says to RETAIN it there until the release archives it. Firing would nag
        every session for weeks with the one remedy that flow forbids.

        This is the test that fails if the `_has_unfinished_chunk` filter is
        deleted; the sibling above passes either way, because its plan has an
        open chunk.
        """
        _init_git_repo(tmp_path, branch="work")
        prawduct = _prawduct(tmp_path)
        (prawduct / "project-state.yaml").write_text("")
        _plan(
            prawduct,
            "build-plan-merged.md",
            "---\nartifact: build-plan\nbranch: feat/long-merged\n---\n\n"
            "## Status\n\n- [x] Chunk 01: a chunk\n",
        )
        findings = briefing.staleness_scan(tmp_path)
        assert not any("not a branch in this repo" in f for f in findings), findings

    def test_a_plan_claiming_an_existing_branch_is_not_reported(self, tmp_path: Path):
        # The paired negative, or the assertion above passes against a scan that
        # reports every branch-declaring plan.
        _init_git_repo(tmp_path, branch="work")
        prawduct = _prawduct(tmp_path)
        (prawduct / "project-state.yaml").write_text("")
        _plan(
            prawduct,
            "build-plan-live.md",
            "---\nartifact: build-plan\nbranch: work\n---\n\n"
            "## Status\n\n- [ ] Chunk 01: a chunk\n",
        )
        findings = briefing.staleness_scan(tmp_path)
        assert not any("not a branch in this repo" in f for f in findings), findings

    def test_an_unaskable_git_accuses_nobody(self, tmp_path: Path, monkeypatch):
        # `local_branches` returning None means "could not ask", which is not
        # evidence that the branch is missing. Treating the two alike would
        # accuse every plan in every repo where git is unavailable — the
        # fail-open shape, pointed the other way.
        _init_git_repo(tmp_path, branch="work")
        prawduct = _prawduct(tmp_path)
        (prawduct / "project-state.yaml").write_text("")
        _plan(
            prawduct,
            "build-plan-gone.md",
            "---\nartifact: build-plan\nbranch: feat/long-merged\n---\n\n"
            "## Status\n\n- [ ] Chunk 01: a chunk\n",
        )
        monkeypatch.setattr(gitstate, "local_branches", lambda _p: None)
        findings = briefing.staleness_scan(tmp_path)
        assert not any("not a branch in this repo" in f for f in findings), findings

    def test_two_claimants_resolve_and_the_briefing_names_both(self, tmp_path: Path):
        # Two plans on one branch is an ordinary arrangement, so the briefing's
        # job is attribution, not alarm: it must name the plan that governs, why
        # it won, and the one it passed over. A session that learns which plan
        # governed by watching a gate grade the wrong one was told too late.
        _init_git_repo(tmp_path, branch="work")
        prawduct = _prawduct(tmp_path)
        (prawduct / "project-state.yaml").write_text("")
        for name, boxes in (("a", "- [x] Chunk 01: shipped"), ("b", "- [ ] Chunk 01: open")):
            _plan(
                prawduct,
                f"build-plan-{name}.md",
                "---\nartifact: build-plan\nbranch: work\n---\n\n"
                f"## Status\n\n{boxes}\n",
            )
        findings = briefing.staleness_scan(tmp_path)
        text = briefing.assemble_session_briefing(tmp_path, findings)
        assert "== SESSION BRIEFING ==" in text
        assert "2 live plans declare `branch: work`" in text
        assert "build-plan-b.md" in text          # the one with chunks left
        assert "build-plan-a.md" in text          # named as passed over
        assert "chunks left" in text              # and why
        # Attribution belongs in ONE place: repeating it as a staleness finding
        # teaches the reader to skip both copies.
        assert not any("live plans declare" in f for f in findings), findings

    def test_the_dangling_pointer_warning_defers_to_a_branch_claim(self, tmp_path: Path):
        # A plan claiming this branch outranks the scalar, so a stale pointer
        # misleads nobody — and a ⚠ that is usually wrong trains the reader to
        # scroll past it.
        _init_git_repo(tmp_path, branch="work")
        prawduct = _prawduct(tmp_path)
        (prawduct / "project-state.yaml").write_text(
            "active_build_plan: artifacts/build-plan-vanished.md\n"
        )
        _plan(
            prawduct,
            "build-plan-live.md",
            "---\nartifact: build-plan\nbranch: work\n---\n\n"
            "## Status\n\n- [ ] Chunk 01: a chunk\n",
        )
        text = briefing.assemble_session_briefing(tmp_path, [])
        assert "points at a MISSING file" not in text

    def test_the_dangling_pointer_warning_still_fires_without_a_claim(
        self, tmp_path: Path
    ):
        """STH-5P2W's guard, unchanged where it is still true — the case the
        narrowing above must not have swallowed."""
        _init_git_repo(tmp_path, branch="work")
        prawduct = _prawduct(tmp_path)
        (prawduct / "artifacts").mkdir(exist_ok=True)
        (prawduct / "project-state.yaml").write_text(
            "active_build_plan: artifacts/build-plan-vanished.md\n"
        )
        text = briefing.assemble_session_briefing(tmp_path, [])
        assert "points at a MISSING file" in text


# --------------------------------------------------------------------------- #
# _extract_dependency_names
# --------------------------------------------------------------------------- #
class TestExtractDependencyNames:
    def test_requirements_txt_skips_comments_blanks_options_and_lowercases(self, tmp_path):
        f = tmp_path / "requirements.txt"
        f.write_text("# comment\n\nDjango==4.2\nrequests>=2\n-e .\n--index-url x\nPyYAML\n")
        assert briefing._extract_dependency_names(f) == ["django", "requests", "pyyaml"]

    def test_package_json_merges_deps_and_devdeps(self, tmp_path):
        f = tmp_path / "package.json"
        f.write_text(json.dumps({"dependencies": {"react": "1"}, "devDependencies": {"jest": "2"}}))
        assert briefing._extract_dependency_names(f) == ["react", "jest"]

    def test_package_json_malformed_returns_empty(self, tmp_path):
        f = tmp_path / "package.json"
        f.write_text("{not valid json")
        assert briefing._extract_dependency_names(f) == []

    def test_unknown_filename_returns_empty(self, tmp_path):
        f = tmp_path / "Cargo.toml"
        f.write_text("[package]\nname = 'x'\n")
        assert briefing._extract_dependency_names(f) == []

    def test_unreadable_file_returns_empty(self, tmp_path):
        assert briefing._extract_dependency_names(tmp_path / "nope.txt") == []


# --------------------------------------------------------------------------- #
# _get_product_name
# --------------------------------------------------------------------------- #
class TestGetProductName:
    def test_reads_name_under_product_identity(self, tmp_path):
        pr = _prawduct(tmp_path)
        (pr / "project-state.yaml").write_text("product_identity:\n  name: Acme\n")
        assert briefing._get_product_name(pr) == "Acme"

    def test_missing_file_is_unknown(self, tmp_path):
        assert briefing._get_product_name(_prawduct(tmp_path)) == "Unknown"

    def test_null_name_is_unknown(self, tmp_path):
        pr = _prawduct(tmp_path)
        (pr / "project-state.yaml").write_text("product_identity:\n  name: null\n")
        assert briefing._get_product_name(pr) == "Unknown"

    def test_template_placeholder_is_unknown(self, tmp_path):
        pr = _prawduct(tmp_path)
        (pr / "project-state.yaml").write_text("product_identity:\n  name: {{product_name}}\n")
        assert briefing._get_product_name(pr) == "Unknown"


# --------------------------------------------------------------------------- #
# _get_current_branch  (git subprocess)
# --------------------------------------------------------------------------- #
class TestGetCurrentBranch:
    def test_returns_actual_branch_in_repo(self, tmp_path):
        _init_git_repo(tmp_path, branch="feature/x")
        assert briefing._get_current_branch(tmp_path) == "feature/x"

    def test_non_git_dir_falls_back_to_main(self, tmp_path):
        assert briefing._get_current_branch(tmp_path) == "main"


# --------------------------------------------------------------------------- #
# _parse_wip
# --------------------------------------------------------------------------- #
class TestParseWip:
    def test_flat_format(self, tmp_path):
        pr = _prawduct(tmp_path)
        (pr / "project-state.yaml").write_text(
            "work_in_progress:\n  description: build\n  size: small\n  type: feature\n"
        )
        assert briefing._parse_wip(pr, branch="anything") == {
            "description": "build", "size": "small", "type": "feature"
        }

    def test_branch_keyed_selects_named_branch(self, tmp_path):
        pr = _prawduct(tmp_path)
        (pr / "project-state.yaml").write_text(
            "work_in_progress:\n"
            "  main:\n    description: main work\n"
            "  feature/x:\n    description: x work\n    size: medium\n"
        )
        assert briefing._parse_wip(pr, branch="feature/x") == {
            "description": "x work", "size": "medium"
        }

    def test_branch_keyed_unknown_branch_is_empty(self, tmp_path):
        pr = _prawduct(tmp_path)
        (pr / "project-state.yaml").write_text(
            "work_in_progress:\n  main:\n    description: main work\n"
        )
        assert briefing._parse_wip(pr, branch="nope") == {}

    def test_null_values_skipped(self, tmp_path):
        pr = _prawduct(tmp_path)
        (pr / "project-state.yaml").write_text(
            "work_in_progress:\n  description: foo\n  size: null\n"
        )
        assert briefing._parse_wip(pr, branch="b") == {"description": "foo"}

    def test_missing_file_is_empty(self, tmp_path):
        assert briefing._parse_wip(_prawduct(tmp_path), branch="b") == {}


# --------------------------------------------------------------------------- #
# _parse_all_wip_branches
# --------------------------------------------------------------------------- #
class TestParseAllWipBranches:
    def test_branch_keyed_returns_all(self, tmp_path):
        pr = _prawduct(tmp_path)
        (pr / "project-state.yaml").write_text(
            "work_in_progress:\n"
            "  main:\n    description: m\n"
            "  feature/y:\n    description: y\n"
        )
        assert briefing._parse_all_wip_branches(pr) == {
            "main": {"description": "m"}, "feature/y": {"description": "y"}
        }

    def test_flat_returns_under_flat_key(self, tmp_path):
        pr = _prawduct(tmp_path)
        (pr / "project-state.yaml").write_text(
            "work_in_progress:\n  description: flatwork\n  size: small\n"
        )
        assert briefing._parse_all_wip_branches(pr) == {
            "_flat": {"description": "flatwork", "size": "small"}
        }

    def test_missing_file_is_empty(self, tmp_path):
        assert briefing._parse_all_wip_branches(_prawduct(tmp_path)) == {}


# --------------------------------------------------------------------------- #
# _get_active_work  (build-plan Status preferred over WIP)
# --------------------------------------------------------------------------- #
class TestGetActiveWork:
    def test_prefers_build_plan_status(self, tmp_path, monkeypatch):
        # `_get_active_work` takes the PROJECT dir rather than `.prawduct/`.
        # That signature outlived its original reason — "which chunk is current"
        # was git-derived on repos whose checkboxes were a derived view — and is
        # kept because the project dir is what resolves the branch's plan
        # (BLD-7K3Q).
        _prawduct(tmp_path)
        monkeypatch.setattr(
            briefing.buildplan_refs, "_parse_build_plan_status",
            lambda d: {"description": "from plan", "current_chunk": "C1"},
        )
        assert briefing._get_active_work(tmp_path) == {
            "description": "from plan", "current_chunk": "C1",
        }

    def test_falls_back_to_wip_when_no_plan_description(self, tmp_path, monkeypatch):
        pr = _prawduct(tmp_path)
        monkeypatch.setattr(briefing.buildplan_refs, "_parse_build_plan_status", lambda d: {})
        (pr / "project-state.yaml").write_text(
            "work_in_progress:\n  description: wip work\n"
        )
        assert briefing._get_active_work(tmp_path) == {"description": "wip work"}

    def test_completed_plan_is_not_active_work(self, tmp_path, monkeypatch):
        """A plan with every chunk done must NOT be reported as active work.

        `staleness_scan` reads the same parse and says "all chunks complete";
        this function said "in progress" from the same bytes, so the handoff
        stamped a finished plan as the next session's **Task** (SCN-4H9T).
        """
        pr = _prawduct(tmp_path)
        monkeypatch.setattr(
            briefing.buildplan_refs, "_parse_build_plan_status",
            lambda d: {"description": "finished plan", "_has_status_items": "true"},
        )
        (pr / "project-state.yaml").write_text(
            "work_in_progress:\n  description: wip work\n"
        )
        assert briefing._get_active_work(tmp_path) == {"description": "wip work"}


# --------------------------------------------------------------------------- #
# _get_work_in_progress  (one-line formatting)
# --------------------------------------------------------------------------- #
class TestGetWorkInProgress:
    def test_formats_with_qualifiers(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            briefing, "_get_active_work",
            lambda d: {"description": "do it", "size": "small", "type": "refactor"},
        )
        assert briefing._get_work_in_progress(tmp_path) == "do it (small, refactor)"

    def test_description_only(self, tmp_path, monkeypatch):
        monkeypatch.setattr(briefing, "_get_active_work", lambda d: {"description": "do it"})
        assert briefing._get_work_in_progress(tmp_path) == "do it"

    def test_none_active(self, tmp_path, monkeypatch):
        monkeypatch.setattr(briefing, "_get_active_work", lambda d: {})
        assert briefing._get_work_in_progress(tmp_path) == "none active"


# --------------------------------------------------------------------------- #
# _detect_worktrees  (porcelain parsing)
# --------------------------------------------------------------------------- #
class TestDetectWorktrees:
    def test_non_git_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(briefing.subprocess, "run", lambda *a, **k: _FakeProc(returncode=128))
        assert briefing._detect_worktrees(tmp_path) == []

    def test_single_worktree_returns_empty(self, tmp_path, monkeypatch):
        out = f"worktree {tmp_path}\nHEAD abc\nbranch refs/heads/main\n"
        monkeypatch.setattr(briefing.subprocess, "run", lambda *a, **k: _FakeProc(stdout=out))
        assert briefing._detect_worktrees(tmp_path) == []

    def test_multiple_worktrees_marks_active_and_parses_detached(self, tmp_path, monkeypatch):
        other = tmp_path.parent / "other-wt"
        out = (
            f"worktree {tmp_path}\nHEAD a\nbranch refs/heads/main\n\n"
            f"worktree {other}\nHEAD b\ndetached\n"
        )
        monkeypatch.setattr(briefing.subprocess, "run", lambda *a, **k: _FakeProc(stdout=out))
        wts = briefing._detect_worktrees(tmp_path)
        assert len(wts) == 2
        active = [w for w in wts if w["is_active"] == "true"]
        assert len(active) == 1 and active[0]["branch"] == "main"
        detached = [w for w in wts if w.get("branch") == "(detached)"]
        assert len(detached) == 1 and detached[0]["is_active"] == "false"


# --------------------------------------------------------------------------- #
# _get_other_branch_wip
# --------------------------------------------------------------------------- #
class TestGetOtherBranchWip:
    def test_excludes_current_and_flat_keeps_described(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            briefing, "_parse_all_wip_branches",
            lambda d: {
                "main": {"description": "main work"},
                "feature/a": {"description": "a work"},
                "feature/b": {},               # no description -> dropped
                "_flat": {"description": "flat"},  # _flat -> dropped
            },
        )
        result = briefing._get_other_branch_wip(tmp_path, current_branch="main")
        assert result == ["feature/a: a work"]


# --------------------------------------------------------------------------- #
# _extract_critical_rules
# --------------------------------------------------------------------------- #
class TestExtractCriticalRules:
    def test_missing_claude_md_returns_fallback(self, tmp_path):
        rules = briefing._extract_critical_rules(tmp_path)
        assert rules and all(r.startswith("- ") for r in rules)
        assert any("Never weaken a test" in r for r in rules)

    def test_extracts_bold_bullets_from_section(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text(
            "# Title\n\n## Critical Rules\n\n- **Do X** always\n- plain bullet ignored\n"
            "- **Do Y** never\n\n## Next\n- **Not a rule** here\n"
        )
        rules = briefing._extract_critical_rules(tmp_path)
        assert rules == ["- **Do X** always", "- **Do Y** never"]

    def test_section_without_bold_bullets_falls_back(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("## Critical Rules\n\n- plain only\n")
        rules = briefing._extract_critical_rules(tmp_path)
        assert any("Fix the code" in r for r in rules)  # fallback set


# --------------------------------------------------------------------------- #
# generate_subagent_briefing
# --------------------------------------------------------------------------- #
class TestGenerateSubagentBriefing:
    def test_writes_file_with_name_rules_and_learnings(self, tmp_path):
        pr = _prawduct(tmp_path)
        (pr / "project-state.yaml").write_text("product_identity:\n  name: Widget\n")
        (pr / "learnings.md").write_text("# Learnings\n- be careful\n")
        briefing.generate_subagent_briefing(tmp_path)
        text = (pr / ".subagent-briefing.md").read_text()
        assert "# Subagent Briefing — Widget" in text
        assert "## Governance Rules" in text
        assert "## Active Learnings" in text and "be careful" in text

    def test_no_prawduct_dir_is_noop(self, tmp_path):
        # project dir has no .prawduct -> returns without writing
        briefing.generate_subagent_briefing(tmp_path)
        assert not (tmp_path / ".prawduct").exists()


# --------------------------------------------------------------------------- #
# _git_session_commits  (git subprocess)
# --------------------------------------------------------------------------- #
class TestGitSessionCommits:
    def test_no_session_start_returns_empty(self, tmp_path):
        _prawduct(tmp_path)
        assert briefing._git_session_commits(tmp_path) == []

    def test_lists_commits_since_session_start(self, tmp_path):
        _init_git_repo(tmp_path)
        pr = _prawduct(tmp_path)
        (pr / ".session-start").write_text("2000-01-01T00:00:00Z")
        commits = briefing._git_session_commits(tmp_path)
        assert any("init commit" in c for c in commits)


# --------------------------------------------------------------------------- #
# _summarize_critic_findings
# --------------------------------------------------------------------------- #
class TestSummarizeCriticFindings:
    def test_missing_file_returns_none(self, tmp_path):
        assert briefing._summarize_critic_findings(_prawduct(tmp_path)) is None

    def test_empty_summary_and_findings_returns_none(self, tmp_path):
        pr = _prawduct(tmp_path)
        (pr / ".critic-findings.json").write_text(json.dumps({"summary": "", "findings": []}))
        assert briefing._summarize_critic_findings(pr) is None

    def test_a_superseded_record_says_so_before_anything_it_qualifies(self, tmp_path):
        """The marker `critic-begin` stamps must survive into THIS renderer.

        `_mark_cache_superseded` writes `superseded_by`/`superseded_at`/
        `superseded_notice` first in the record so a direct reader meets them
        before the findings and the `next_action` they qualify — but this
        function reads the same file and rebuilds the section field by field, so
        it dropped all three and presented a superseded review's counts and
        `NEXT-ACTION:` as current. That reader is the one the marker was written
        for: definitionally the builder who lost the reviewer's report, and so
        the one who cannot compare what they are holding against a review id
        they never saw.

        Reachable in normal operation despite `clear` refusing to run while a
        review is active: a dispatched review's marker expires by TTL and is
        swept at the next session boundary, so the record outlives every
        in-session signal that a newer review was dispatched.
        """
        pr = _prawduct(tmp_path)
        (pr / ".critic-findings.json").write_text(json.dumps({
            "superseded_by": "rev-20260805T165453Z-2cf52cde",
            "superseded_at": "2026-08-05T16:55:14Z",
            "superseded_notice": "SUPERSEDED — …",
            "summary": "0 blocking, 4 warning, 0 note across 3 reviewer(s).",
            "findings": [{"severity": "warning", "summary": "a stale warning"}],
            "next_action": "0 blocking — THE REVIEW IS OVER.",
        }))
        out = briefing._summarize_critic_findings(pr)
        assert out is not None
        assert "SUPERSEDED" in out
        assert "rev-20260805T165453Z-2cf52cde" in out, "name the review that displaced it"
        # BEFORE the summary and the directive it qualifies — a reader that stops
        # early must stop on the warning, not on the stale next_action.
        assert out.index("SUPERSEDED") < out.index("0 blocking, 4 warning")
        assert out.index("SUPERSEDED") < out.index("NEXT-ACTION")

    def test_an_unsuperseded_record_carries_no_marker_prose(self, tmp_path):
        """The ordinary case stays clean — the notice appears only when the
        record actually carries the marker, so its presence is information."""
        pr = _prawduct(tmp_path)
        (pr / ".critic-findings.json").write_text(json.dumps({
            "summary": "0 blocking, 0 warning, 0 note across 1 reviewer(s).",
            "findings": [],
            "next_action": "0 blocking — THE REVIEW IS OVER.",
        }))
        out = briefing._summarize_critic_findings(pr)
        assert out is not None
        assert "SUPERSEDED" not in out

    def test_an_unreadable_record_says_so_rather_than_going_quiet(self, tmp_path):
        """A record that EXISTS but cannot be parsed is not the same answer as
        no record, and rendering them identically is the failure this whole
        surface exists to prevent.

        `None` drops the entire `## Critic Findings` section from the briefing,
        which reads exactly like "no review has run" — and the reader here is
        definitionally the builder who lost the reviewer's report across
        `/clear`, the one context where that difference decides whether a round
        gets run. The missing-FIELD paths are covered above; this is the
        missing-RECORD path.

        Same rule its sibling advisory follows in `coverage.diagnose_fix_churn`
        (`unavailable` vs `None`), and the same learning both cite: "'advice
        fails soft' is not 'advice fails silent'."
        """
        pr = _prawduct(tmp_path)
        (pr / ".critic-findings.json").write_text('{"summary": "truncated mid-w')
        out = briefing._summarize_critic_findings(pr)
        assert out is not None, (
            "an unparseable findings record renders identically to no review "
            "having run — the builder inherits silence and re-reviews"
        )
        assert "could not be read" in out
        assert "NOT a statement" in out, "the degraded path must name its consequence"
        assert "critic-consolidate" in out, "and the route back to the real record"

    def test_counts_and_lists_blocking_and_warnings(self, tmp_path):
        pr = _prawduct(tmp_path)
        (pr / ".critic-findings.json").write_text(json.dumps({
            "summary": "Review done.",
            "findings": [
                {"severity": "blocking", "summary": "must fix"},
                {"severity": "warning", "summary": "should fix"},
                {"severity": "note", "summary": "fyi"},
            ],
        }))
        out = briefing._summarize_critic_findings(pr)
        assert "Review done." in out
        assert "1 blocking" in out and "1 warning" in out and "1 note" in out
        assert "BLOCKING: must fix" in out and "WARNING: should fix" in out

    def test_next_action_reaches_the_cross_session_builder(self, tmp_path):
        """The handoff is the ONLY carrier of the loop-termination rule that
        survives `/clear`, and its reader is by definition the one who lost the
        reviewer's report — so a silent loss here is unobservable in-session,
        which is the exact failure mode this whole change exists to close.
        Every sibling carrier is pinned; this one was not."""
        pr = _prawduct(tmp_path)
        (pr / ".critic-findings.json").write_text(json.dumps({
            "summary": "0 blocking, 4 warning, 2 note.",
            "findings": [{"severity": "warning", "summary": "should fix"}],
            "next_action": "0 blocking — THE REVIEW IS OVER. They gate NOTHING.",
        }))
        out = briefing._summarize_critic_findings(pr)
        assert "NEXT-ACTION: 0 blocking — THE REVIEW IS OVER" in out
        # Inheriting a warning list with no statement that warnings gate
        # nothing is the state the measured ten-round failure started from.
        assert out.index("1 warning") < out.index("NEXT-ACTION:")

    def test_next_action_survives_a_clean_pass_with_no_findings(self, tmp_path):
        """The clean pass is where "the review is over" is the entire message,
        and it is the one shape the early `not summary and not findings` return
        can swallow: with an empty `findings` list, only the summary keeps the
        record from short-circuiting to `None` and taking `next_action` with it.
        Pinned with a summary present because that is what `fact_to_cache_record`
        writes; the summary-less case is `test_empty_summary_and_findings_returns_none`."""
        pr = _prawduct(tmp_path)
        (pr / ".critic-findings.json").write_text(json.dumps({
            "summary": "0 blocking, 0 warning, 0 note across 1 reviewer(s).",
            "findings": [],
            "next_action": "0 blocking, 0 other findings — THE REVIEW IS OVER.",
        }))
        out = briefing._summarize_critic_findings(pr)
        assert out is not None
        assert "NEXT-ACTION: 0 blocking, 0 other findings" in out

    def test_a_record_without_next_action_still_summarizes(self, tmp_path):
        # Records written before the field existed must not lose their summary.
        pr = _prawduct(tmp_path)
        (pr / ".critic-findings.json").write_text(json.dumps({
            "summary": "Legacy record.", "findings": [],
        }))
        out = briefing._summarize_critic_findings(pr)
        assert out == "Legacy record."


# --------------------------------------------------------------------------- #
# generate_session_handoff
# --------------------------------------------------------------------------- #
class TestGenerateSessionHandoff:
    def test_assembles_wip_and_reflection_sections(self, tmp_path, monkeypatch):
        pr = _prawduct(tmp_path)
        (pr / "project-state.yaml").write_text(
            "work_in_progress:\n  description: ship it\n  current_chunk: C3\n"
        )
        (pr / ".session-reflected").write_text("learned a thing during this session here")
        monkeypatch.setattr(briefing.buildplan_refs, "_parse_build_plan_status", lambda d: {})
        monkeypatch.setattr(briefing.gitstate, "_get_session_changed_files", lambda d: [])
        briefing.generate_session_handoff(tmp_path)
        text = (pr / ".session-handoff.md").read_text()
        assert "## Work In Progress" in text and "ship it" in text
        assert "**Current chunk**: C3" in text
        assert "## Previous Session Reflection" in text and "learned a thing" in text

    def test_no_content_writes_nothing(self, tmp_path, monkeypatch):
        pr = _prawduct(tmp_path)
        (pr / "project-state.yaml").write_text("product_identity:\n  name: X\n")  # no WIP
        monkeypatch.setattr(briefing.buildplan_refs, "_parse_build_plan_status", lambda d: {})
        monkeypatch.setattr(briefing.gitstate, "_get_session_changed_files", lambda d: [])
        briefing.generate_session_handoff(tmp_path)
        assert not (pr / ".session-handoff.md").exists()

    def test_no_prawduct_dir_is_noop(self, tmp_path):
        briefing.generate_session_handoff(tmp_path)
        assert not (tmp_path / ".prawduct").exists()


# --------------------------------------------------------------------------- #
# _check_previous_session_gates  (governance warnings — delegates to siblings)
# --------------------------------------------------------------------------- #
class TestCheckPreviousSessionGates:
    def _patch(self, monkeypatch, *, changes=True, doc_only=False, code=True,
               waivers=None, build_plan=True):
        # Stubs accept the optional status_output param (STH-6Q9D) the real
        # signatures gained — the gate now captures porcelain once and threads it.
        monkeypatch.setattr(briefing.gitstate, "git_has_session_changes", lambda d, s=None: changes)
        monkeypatch.setattr(briefing.gates, "session_changes_all_non_judgeable", lambda d, s=None: doc_only)
        monkeypatch.setattr(briefing.gitstate, "git_has_code_changes", lambda d, s=None: code)
        monkeypatch.setattr(briefing.gates, "_read_gates_waived", lambda d: waivers or {})
        # Accepts the plan-path argument the briefing now passes (it resolves the
        # BRANCH's plan, the same one the Stop gate reads, so the advisory cannot
        # go silent where the gate blocks). The stub ignores it: what is under
        # test is the advisory's reaction, not which file it was pointed at.
        monkeypatch.setattr(
            briefing.gates, "_has_active_build_plan_file",
            lambda d, _plan_path=None: build_plan,
        )
        monkeypatch.setattr(briefing.gates, "_has_build_plan_in_state", lambda d: False)
        monkeypatch.setattr(
            briefing.gates, "session_review_verdict", lambda d, **_kw: {"status": "uncovered", "reason": "no facts"}
        )

    def test_no_changes_short_circuits(self, tmp_path, monkeypatch):
        self._patch(monkeypatch, changes=False)
        assert briefing._check_previous_session_gates(tmp_path) == []

    def test_missing_reflection_warns(self, tmp_path, monkeypatch):
        _prawduct(tmp_path)
        self._patch(monkeypatch, build_plan=False)  # isolate reflection gate
        assert "reflection not captured" in briefing._check_previous_session_gates(tmp_path)

    def test_doc_only_skips_reflection(self, tmp_path, monkeypatch):
        _prawduct(tmp_path)
        self._patch(monkeypatch, doc_only=True, build_plan=False)
        assert briefing._check_previous_session_gates(tmp_path) == []

    def test_reflection_waiver_skips(self, tmp_path, monkeypatch):
        _prawduct(tmp_path)
        self._patch(monkeypatch, waivers={"reflection": "n/a"}, build_plan=False)
        assert briefing._check_previous_session_gates(tmp_path) == []

    def test_sufficient_reflection_no_warning(self, tmp_path, monkeypatch):
        pr = _prawduct(tmp_path)
        (pr / ".session-reflected").write_text("x" * 60)
        self._patch(monkeypatch, build_plan=False)
        assert briefing._check_previous_session_gates(tmp_path) == []

    def test_build_plan_with_code_and_no_findings_warns_critic(self, tmp_path, monkeypatch):
        pr = _prawduct(tmp_path)
        (pr / ".session-reflected").write_text("x" * 60)  # silence reflection gate
        self._patch(monkeypatch, build_plan=True, code=True)
        assert "Critic review not recorded" in briefing._check_previous_session_gates(tmp_path)

    def test_critic_waiver_skips_critic_gate(self, tmp_path, monkeypatch):
        pr = _prawduct(tmp_path)
        (pr / ".session-reflected").write_text("x" * 60)
        self._patch(monkeypatch, build_plan=True, code=True, waivers={"critic": "n/a"})
        assert briefing._check_previous_session_gates(tmp_path) == []


# --------------------------------------------------------------------------- #
# assemble_session_briefing  (optional-section branches)
# --------------------------------------------------------------------------- #
class TestAssembleSessionBriefingSections:
    def _state(self, tmp_path, body: str) -> Path:
        pr = _prawduct(tmp_path)
        (pr / "project-state.yaml").write_text("product_identity:\n  name: P\n" + body)
        return pr

    def test_resume_and_truncated_context(self, tmp_path, monkeypatch):
        pr = self._state(tmp_path, "")
        long_ctx = "C" * 300
        monkeypatch.setattr(
            briefing, "_get_active_work",
            lambda d: {"description": "w", "current_chunk": "CH1", "context": long_ctx},
        )
        out = briefing.assemble_session_briefing(tmp_path, [])
        assert "Resume: CH1" in out
        ctx_line = next(line for line in out.splitlines() if line.startswith("Context: "))
        assert ctx_line.endswith("...") and len(ctx_line) < 300

    def test_other_branches_section(self, tmp_path, monkeypatch):
        self._state(tmp_path, "")
        monkeypatch.setattr(briefing, "_get_other_branch_wip",
                            lambda d, cb: ["feature/z: z work"])
        out = briefing.assemble_session_briefing(tmp_path, [])
        assert "Other active branches: 1" in out and "feature/z: z work" in out

    def test_worktree_orientation_without_sibling_enumeration(self, tmp_path, monkeypatch):
        # The briefing orients the agent to ITS worktree but must NOT enumerate
        # sibling worktrees' branches/paths — that list read as a menu of
        # adoptable work and lured agents into working in the wrong worktree.
        self._state(tmp_path, "")
        monkeypatch.setattr(briefing, "_detect_worktrees", lambda d: [
            {"path": "/a", "branch": "main", "is_active": "true"},
            {"path": "/b", "branch": "side", "is_active": "false"},
        ])
        out = briefing.assemble_session_briefing(tmp_path, [])
        assert "operating on 'main'" in out
        assert "scoped to THIS worktree only" in out
        # Regression guard: the old "- <branch> @ <path>" sibling enumeration must not
        # return. Guard the enumeration format and the sibling path — not the bare word
        # "side", which collides with "conSIDEr" elsewhere in the briefing vocabulary.
        assert "- side @ /b" not in out
        assert "/b" not in out

    def test_staleness_lines_rendered(self, tmp_path):
        self._state(tmp_path, "")
        out = briefing.assemble_session_briefing(tmp_path, ["thing A", "thing B"])
        assert "Stale: thing A" in out and "Stale: thing B" in out

    def test_dangling_build_plan_pointer_warns_loudly(self, tmp_path):
        # STH-5P2W: a SET pointer resolving to no file = governance is blind;
        # the briefing must say so (this failure shipped silently once).
        self._state(tmp_path, "active_build_plan: artifacts/gone-plan.md\n")
        out = briefing.assemble_session_briefing(tmp_path, [])
        assert "active_build_plan" in out and "MISSING" in out
        assert "gone-plan.md" in out
        assert "no active plan" in out  # the consequence is taught

    def test_pointer_to_existing_plan_no_warning(self, tmp_path):
        pr = self._state(tmp_path, "active_build_plan: artifacts/x-plan.md\n")
        (pr / "artifacts").mkdir(exist_ok=True)
        (pr / "artifacts" / "x-plan.md").write_text("# plan\n")
        out = briefing.assemble_session_briefing(tmp_path, [])
        assert "MISSING" not in out

    def test_repo_relative_pointer_to_existing_plan_no_warning(self, tmp_path):
        # The repo-relative spelling now RESOLVES (stripped prefix) — no warning.
        pr = self._state(tmp_path, "active_build_plan: .prawduct/artifacts/x-plan.md\n")
        (pr / "artifacts").mkdir(exist_ok=True)
        (pr / "artifacts" / "x-plan.md").write_text("# plan\n")
        out = briefing.assemble_session_briefing(tmp_path, [])
        assert "MISSING" not in out

    def test_unset_pointer_no_warning(self, tmp_path):
        self._state(tmp_path, "")
        out = briefing.assemble_session_briefing(tmp_path, [])
        assert "active_build_plan" not in out

    def test_null_pointer_no_warning(self, tmp_path):
        # VWS-7N3K: `active_build_plan: null` is the canonical "no active plan"
        # opt-out — it must NOT trip the dangling-pointer guard (which used to
        # mis-fire with "'null' resolved to .prawduct/null").
        self._state(tmp_path, "active_build_plan: null\n")
        out = briefing.assemble_session_briefing(tmp_path, [])
        assert "MISSING" not in out
        assert ".prawduct/null" not in out

    def test_handoff_pointer_when_present(self, tmp_path):
        pr = self._state(tmp_path, "")
        (pr / ".session-handoff.md").write_text("prior")
        out = briefing.assemble_session_briefing(tmp_path, [])
        assert "Previous session context available" in out

    def test_handoff_pointer_on_a_continuation_leads_with_applicability(self, tmp_path):
        # SCN-5B8Q Chunk 02: the pointer is boundary-scoped, the briefing carrying
        # it is not. On resume/compact/fork the reader's transcript already covers
        # the handoff, so the line must lead with THAT fact — source is the fact,
        # age is only a proxy for it.
        pr = self._state(tmp_path, "")
        (pr / ".session-handoff.md").write_text("prior")
        out = briefing.assemble_session_briefing(tmp_path, [], continuation=True)
        pointer = next(ln for ln in out.splitlines() if ".session-handoff.md" in ln)
        assert "predates THIS session" in pointer
        assert "continuation" in pointer
        # Applicability LEADS; age trails it rather than opening the line.
        assert pointer.index("predates THIS session") < pointer.index("(just now)")
        # ...and it is never withheld: advice fails soft, so the path is still named.
        assert ".prawduct/.session-handoff.md" in pointer

    def test_handoff_pointer_at_a_boundary_is_unchanged_but_dated(self, tmp_path):
        pr = self._state(tmp_path, "")
        (pr / ".session-handoff.md").write_text("prior")
        out = briefing.assemble_session_briefing(tmp_path, [], continuation=False)
        assert (
            "Previous session context available: read .prawduct/.session-handoff.md (just now)"
            in out
        )
        assert "predates THIS session" not in out

    def test_handoff_pointer_defaults_to_the_boundary_reading(self, tmp_path):
        # A caller that does not know its source must not be told a possibly-false
        # thing about its own context.
        pr = self._state(tmp_path, "")
        (pr / ".session-handoff.md").write_text("prior")
        assert "predates THIS session" not in briefing.assemble_session_briefing(tmp_path, [])

    def test_handoff_pointer_reports_a_real_age(self, tmp_path):
        pr = self._state(tmp_path, "")
        handoff = pr / ".session-handoff.md"
        handoff.write_text("prior")
        old = time.time() - 3 * 86400
        os.utime(handoff, (old, old))
        for continuation in (False, True):
            out = briefing.assemble_session_briefing(tmp_path, [], continuation=continuation)
            assert "(3d old)" in out, continuation

    def test_handoff_pointer_survives_an_unreadable_mtime(self, tmp_path):
        # An unreadable stat is a reason to say LESS, never a reason to withhold
        # the pointer — the handoff is advice, and advice fails soft.
        gone = tmp_path / "nope" / ".session-handoff.md"  # stat() raises OSError
        for continuation in (False, True):
            pointer = briefing._handoff_pointer(gone, continuation=continuation)
            assert ".prawduct/.session-handoff.md" in pointer
            assert "old)" not in pointer and "just now" not in pointer
        assert "predates THIS session" in briefing._handoff_pointer(gone, continuation=True)

    def test_learnings_and_backlog_counts(self, tmp_path):
        pr = self._state(tmp_path, "")
        (pr / "learnings.md").write_text("# L\n- rule one\n- rule two\n")
        (pr / "backlog.md").write_text("# Backlog\n## Open\n- [A-1] one\n- [A-2] two\n")
        out = briefing.assemble_session_briefing(tmp_path, [])
        assert "Learnings (2 rules): /prawduct:learnings <topic>" in out
        assert "Backlog: 2 pending (/prawduct:backlog to triage)" in out

    def test_backlog_excludes_resolved_section_and_strikethrough(self, tmp_path):
        pr = self._state(tmp_path, "")
        (pr / "backlog.md").write_text(
            "# Backlog\n## Open\n- [A-1] keep\n- ~~[A-2] struck~~\n## Resolved\n- [A-3] done\n"
        )
        out = briefing.assemble_session_briefing(tmp_path, [])
        assert "Backlog: 1 pending" in out

    def test_learnings_entry_format_counts_headings(self, tmp_path):
        # The documented format is one rule per `## ` entry; bullet counting
        # alone reported 0 rules and silently dropped the Learnings line.
        pr = self._state(tmp_path, "")
        (pr / "learnings.md").write_text(
            "# L\n\n## Rule one\n\nBody.\n\n## Rule two\n\nBody with\n- an inner bullet\n"
        )
        out = briefing.assemble_session_briefing(tmp_path, [])
        assert "Learnings (2 rules)" in out  # headings win; inner bullet not counted

    def test_learnings_size_nudge_over_threshold(self, tmp_path):
        # MET-6W3J: every lookup reads the whole file — nudge when oversized.
        pr = self._state(tmp_path, "")
        big = "# L\n" + ("- rule\n" + "x" * 100 + "\n") * 500  # > 40KB
        (pr / "learnings.md").write_text(big)
        out = briefing.assemble_session_briefing(tmp_path, [])
        assert "learnings.md is large" in out
        assert "learnings-detail.md" in out  # the fix is taught, not just the size

    def test_learnings_size_nudge_silent_under_threshold(self, tmp_path):
        pr = self._state(tmp_path, "")
        (pr / "learnings.md").write_text("# L\n- rule one\n- rule two\n")
        out = briefing.assemble_session_briefing(tmp_path, [])
        assert "learnings.md is large" not in out

    def test_claude_md_size_warning_over_threshold(self, tmp_path):
        self._state(tmp_path, "")
        (tmp_path / "CLAUDE.md").write_text("\n".join(f"line {i}" for i in range(260)))
        out = briefing.assemble_session_briefing(tmp_path, [])
        assert "CLAUDE.md is large" in out

    def test_active_advisories_section(self, tmp_path, monkeypatch):
        self._state(tmp_path, "")
        monkeypatch.setattr(briefing.gitstate, "_read_advisory_store", lambda d: {"advisories": [
            {"id": "ADV-1", "state": "active", "feature": "feat", "trigger_summary": "do x",
             "recommended_action": "/prawduct:doctor", "priority": "warn", "triggered_at": "2026-01-01"},
        ]})
        out = briefing.assemble_session_briefing(tmp_path, [])
        assert "ADVISORIES (post-sync, 1 active):" in out
        assert "• [feat] do x" in out
        assert "→ Run /prawduct:doctor (or /prawduct:advisory dismiss ADV-1)" in out


class TestAdvisoryRelayDirective:
    """The briefing renders to stdout — the agent-facing channel — so an advisory
    is an instruction the model reads, never a nudge the owner reads. A `warn`
    that needs an owner decision therefore has to be relayed into conversation or
    it goes unanswered every session while appearing, from the inside, delivered.

    Scoped to `warn`/`urgent`: relaying `info` every session is nagging, which
    trains the reader to tune the channel out and costs more than it buys.
    """

    def _state(self, tmp_path: Path, body: str) -> Path:
        pr = tmp_path / ".prawduct"
        pr.mkdir(parents=True, exist_ok=True)
        (pr / "project-state.yaml").write_text(body)
        return pr

    def _advisories(self, monkeypatch, *advisories):
        monkeypatch.setattr(
            briefing.gitstate, "_read_advisory_store", lambda d: {"advisories": list(advisories)}
        )

    def _adv(self, priority: str, aid: str = "ADV-1") -> dict:
        return {
            "id": aid, "state": "active", "feature": "feat",
            "trigger_summary": "do x", "recommended_action": "/prawduct:doctor",
            "priority": priority, "triggered_at": "2026-01-01",
        }

    def test_warn_triggers_the_relay(self, tmp_path, monkeypatch):
        self._state(tmp_path, "")
        self._advisories(monkeypatch, self._adv("warn"))
        assert briefing.ADVISORY_RELAY_MARKER in briefing.assemble_session_briefing(tmp_path, [])

    def test_urgent_triggers_the_relay(self, tmp_path, monkeypatch):
        self._state(tmp_path, "")
        self._advisories(monkeypatch, self._adv("urgent"))
        assert briefing.ADVISORY_RELAY_MARKER in briefing.assemble_session_briefing(tmp_path, [])

    def test_info_only_is_silent(self, tmp_path, monkeypatch):
        self._state(tmp_path, "")
        self._advisories(monkeypatch, self._adv("info"), self._adv("info", "ADV-2"))
        assert briefing.ADVISORY_RELAY_MARKER not in briefing.assemble_session_briefing(tmp_path, [])

    def test_no_active_advisories_is_silent(self, tmp_path, monkeypatch):
        self._state(tmp_path, "")
        self._advisories(monkeypatch)
        assert briefing.ADVISORY_RELAY_MARKER not in briefing.assemble_session_briefing(tmp_path, [])

    def test_resolved_advisory_does_not_trigger_the_relay(self, tmp_path, monkeypatch):
        # State, not priority, decides: a resolved `warn` has nothing to relay.
        self._state(tmp_path, "")
        resolved = self._adv("warn") | {"state": "resolved", "resolved_at": "2026-01-02"}
        self._advisories(monkeypatch, resolved)
        assert briefing.ADVISORY_RELAY_MARKER not in briefing.assemble_session_briefing(tmp_path, [])

    def test_relay_is_last_in_the_block(self, tmp_path, monkeypatch):
        # The directive refers to everything above it, so trailing block content
        # would make it read as covering only the part it precedes. Its banner twin
        # is pinned by an equivalent test; this site was moved to satisfy a review
        # finding with nothing holding it there, so the position is pinned now.
        # `dismissed`/`resolved` are the lines that follow the advisory list, so a
        # regression puts them after the directive.
        self._state(tmp_path, "")
        (tmp_path / ".prawduct" / ".session-start").write_text("2026-01-01T00:00:00Z")
        dismissed = self._adv("info", "ADV-D") | {
            "state": "dismissed", "dismissed_at": "2026-01-02T00:00:00Z"
        }
        self._advisories(monkeypatch, self._adv("warn"), dismissed)
        out = briefing.assemble_session_briefing(tmp_path, [])
        block_lines = out.splitlines()
        assert "Dismissed since last session" in out, "fixture must produce a trailing line"
        relay_at = block_lines.index(briefing.ADVISORY_RELAY_TEXT)
        dismissed_at = next(
            i for i, ln in enumerate(block_lines) if "Dismissed since last session" in ln
        )
        assert relay_at > dismissed_at, "relay must follow every line of its block"

    def test_display_cap_can_never_hide_a_consequential_advisory(self, tmp_path, monkeypatch):
        # The block displays 5 of N. That cap can only mislead if a relay-priority
        # advisory is ever pushed out of the visible set — which the priority sort
        # forbids: `urgent`/`warn` rank ahead of `info`, so the only thing that can
        # displace a `warn` is an `urgent`, itself worth relaying. This pins the
        # sort, not the relay: reorder it to newest-first and a `warn` buried under
        # six fresh `info`s would be relayed but never shown, so the person is told
        # to look at something they cannot see.
        self._state(tmp_path, "")
        infos = [self._adv("info", f"ADV-{i}") for i in range(6)]
        monkeypatch.setattr(briefing.gitstate, "_read_advisory_store", lambda d: {
            "advisories": infos + [self._adv("warn", "ADV-LATE")]
        })
        out = briefing.assemble_session_briefing(tmp_path, [])
        assert briefing.ADVISORY_RELAY_MARKER in out
        assert "... and 2 more" in out, "expected 7 active with 5 displayed"
        # Bound the "displayed" set by the overflow line rather than by the relay's
        # position: the relay moved once already, and a proxy that tracks it would
        # keep passing while measuring something else.
        overflow_at = next(
            i for i, ln in enumerate(out.splitlines()) if "... and 2 more" in ln
        )
        shown = "\n".join(out.splitlines()[:overflow_at])
        assert "ADV-LATE" in shown, "a warn must be inside the displayed set, not just relayed"

    def test_relay_names_no_internal_identifier(self, tmp_path, monkeypatch):
        self._state(tmp_path, "")
        self._advisories(monkeypatch, self._adv("warn"))
        out = briefing.assemble_session_briefing(tmp_path, [])
        line = next(ln for ln in out.splitlines() if briefing.ADVISORY_RELAY_MARKER in ln)
        assert not re.search(r"\b[A-Z]{2,4}-[A-Z0-9]{3,4}\b", line), line


# --------------------------------------------------------------------------- #
# _backlog_pending_line — cutover-aware backlog rollup (BKL-8P2R)
# --------------------------------------------------------------------------- #
class _PopenRecorder:
    """Records the spawn; blows up if anything WAITS on the child (the briefing
    must be fire-and-forget)."""

    def __init__(self):
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        return self

    def wait(self, *a, **k):  # pragma: no cover - reaching this IS the failure
        raise AssertionError("briefing waited on the detached refresh child")

    communicate = wait
    poll = wait


def _warmed_ops(recorder: _PopenRecorder) -> set[str]:
    """The backlog ops the recorder saw warmed, by name.

    Two stores are warmed at session start — the briefing counts snapshot
    (`refresh-counts`) and the backlog cache (`sync`) — and they are separate
    subprocesses on purpose: two ops against two stores, where deriving a count is
    not the sync that fills the item rows the review-time consumers read.
    """
    return {argv[argv.index("backlog") + 1] for argv, _kwargs in recorder.calls}


def _warm_argv(recorder: _PopenRecorder, op: str) -> list[str]:
    """The argv of the warm for ``op``. Fails loudly if it never fired, so a
    missing warm reads as a missing warm rather than as an index error."""
    for argv, _kwargs in recorder.calls:
        if argv[argv.index("backlog") + 1] == op:
            return argv
    raise AssertionError(f"no detached warm fired for `backlog {op}`")


_ABSENT = object()  # "the snapshot has no `untriaged` key at all" — the pre-#532 shape


class TestBacklogPendingLine:
    def _state(self, prawduct_dir: Path, scope: str | None):
        text = "product_name: t\n"
        if scope:
            text += f"backlog_service_repo: {scope}\n"
        (prawduct_dir / "project-state.yaml").write_text(text, encoding="utf-8")

    def _snapshot(self, project_dir: Path, scope: str, by_status: dict, untriaged=_ABSENT):
        from lib.backlog import snapshot

        path = snapshot.snapshot_path(project_dir)
        assert path is not None
        counts = {"total": sum(by_status.values()), "by_status": by_status, "by_stage": {}}
        if untriaged is not _ABSENT:
            counts["untriaged"] = untriaged
        snapshot.write(path, scope, counts)

    def test_pre_cutover_reads_markdown(self, tmp_path):
        prawduct = _prawduct(tmp_path)
        self._state(prawduct, None)
        (prawduct / "backlog.md").write_text(
            "# Backlog\n\n## Open\n\n- **[X-0001]** One thing\n- **[X-0002]** Another\n",
            encoding="utf-8",
        )
        line = briefing._backlog_pending_line(prawduct, tmp_path, popen=_PopenRecorder())
        assert line == "Backlog: 2 pending (/prawduct:backlog to triage)"

    def test_post_cutover_reads_snapshot_with_age_and_warms(self, tmp_path):
        _init_git_repo(tmp_path)
        prawduct = _prawduct(tmp_path)
        self._state(prawduct, "octo/backlog")
        self._snapshot(tmp_path, "octo/backlog",
                       {"open": 3, "in-progress": 1, "submitted": 1, "shipped": 9})
        recorder = _PopenRecorder()
        line = briefing._backlog_pending_line(prawduct, tmp_path, popen=recorder)
        assert line is not None
        assert "5 pending on octo/backlog" in line
        assert "snapshot just now" in line
        # Both warms fired, detached, and neither was waited on. Asserting the
        # OPS rather than a count: the number is the thing that changes when a
        # third store gains a trigger, and a count assertion turns that into a
        # failure about arithmetic instead of about which warms ran.
        assert _warmed_ops(recorder) == {"refresh-counts", "sync"}
        for _argv, kwargs in recorder.calls:
            assert kwargs.get("start_new_session") is True
        for op in ("refresh-counts", "sync"):
            argv = _warm_argv(recorder, op)
            assert argv[-4:] == ["backlog", op, "--repo", "octo/backlog"]
        # The cache warm is incremental — never `--rebuild`. A rebuild on every
        # session start would refetch the whole backlog to learn nothing changed.
        assert "--rebuild" not in _warm_argv(recorder, "sync")

    def test_post_cutover_no_snapshot_degrades_visibly(self, tmp_path):
        _init_git_repo(tmp_path)
        prawduct = _prawduct(tmp_path)
        self._state(prawduct, "octo/backlog")
        recorder = _PopenRecorder()
        line = briefing._backlog_pending_line(prawduct, tmp_path, popen=recorder)
        assert line == "Backlog: counts warming for octo/backlog (/prawduct:backlog to triage)"
        assert _warmed_ops(recorder) == {"refresh-counts", "sync"}  # warms still fired

    def test_post_cutover_zero_pending_suppresses_line_but_warms(self, tmp_path):
        _init_git_repo(tmp_path)
        prawduct = _prawduct(tmp_path)
        self._state(prawduct, "octo/backlog")
        self._snapshot(tmp_path, "octo/backlog", {"shipped": 7, "dropped": 2})
        recorder = _PopenRecorder()
        line = briefing._backlog_pending_line(prawduct, tmp_path, popen=recorder)
        assert line is None
        assert _warmed_ops(recorder) == {"refresh-counts", "sync"}

    def test_untriaged_is_surfaced_by_exception_when_non_zero(self, tmp_path):
        # #532's thesis: an untriaged item is invisible to the tooling, so it must
        # be LOUDER than a triaged one. The briefing is the most-read governance
        # line in the product; absorbing untriaged into an undifferentiated
        # "N pending" is the quietest possible treatment.
        _init_git_repo(tmp_path)
        prawduct = _prawduct(tmp_path)
        self._state(prawduct, "octo/backlog")
        self._snapshot(tmp_path, "octo/backlog", {"open": 5}, untriaged=2)
        line = briefing._backlog_pending_line(prawduct, tmp_path, popen=_PopenRecorder())
        assert line == (
            "Backlog: 5 pending (2 untriaged) on octo/backlog "
            "(snapshot just now; /prawduct:backlog to triage)"
        )

    def test_zero_untriaged_adds_nothing_to_the_line(self, tmp_path):
        _init_git_repo(tmp_path)
        prawduct = _prawduct(tmp_path)
        self._state(prawduct, "octo/backlog")
        self._snapshot(tmp_path, "octo/backlog", {"open": 5}, untriaged=0)
        line = briefing._backlog_pending_line(prawduct, tmp_path, popen=_PopenRecorder())
        assert line == (
            "Backlog: 5 pending on octo/backlog (snapshot just now; /prawduct:backlog to triage)"
        )

    def test_snapshot_predating_the_untriaged_key_renders_unchanged(self, tmp_path):
        # Tolerant reader: the snapshot on disk was written by whatever version
        # last ran `refresh-counts`, which may predate the key entirely. A
        # briefing line is not the place to refuse an old cache.
        _init_git_repo(tmp_path)
        prawduct = _prawduct(tmp_path)
        self._state(prawduct, "octo/backlog")
        self._snapshot(tmp_path, "octo/backlog", {"open": 5})  # no `untriaged` key
        line = briefing._backlog_pending_line(prawduct, tmp_path, popen=_PopenRecorder())
        assert line == (
            "Backlog: 5 pending on octo/backlog (snapshot just now; /prawduct:backlog to triage)"
        )

    def test_untriaged_of_a_junk_type_is_ignored_not_rendered(self, tmp_path):
        # A hand-edited or half-written snapshot must not put `(None untriaged)`
        # or `(True untriaged)` on the most-read line in the product.
        _init_git_repo(tmp_path)
        prawduct = _prawduct(tmp_path)
        self._state(prawduct, "octo/backlog")
        for junk in (None, True, "3", -1, 1.5):
            self._snapshot(tmp_path, "octo/backlog", {"open": 5}, untriaged=junk)
            line = briefing._backlog_pending_line(prawduct, tmp_path, popen=_PopenRecorder())
            assert line is not None
            assert "untriaged" not in line, junk

    def test_never_blocks_even_with_a_hanging_backend(self, tmp_path):
        # The G2 real-slowness contract: the briefing path touches no network
        # and never waits on the child, so a backend that WOULD hang forever
        # (the recorder's wait raises if touched) cannot slow session start.
        import time

        _init_git_repo(tmp_path)
        prawduct = _prawduct(tmp_path)
        self._state(prawduct, "octo/backlog")
        self._snapshot(tmp_path, "octo/backlog", {"open": 1})
        start = time.monotonic()
        line = briefing._backlog_pending_line(prawduct, tmp_path, popen=_PopenRecorder())
        elapsed = time.monotonic() - start
        assert line is not None
        assert elapsed < 2.0  # NFR §6 "few s" — structural, not timeout-dependent

    def test_post_cutover_warm_that_never_starts_does_not_claim_warming(self, tmp_path):
        # Regression: the warm's bool return was discarded, so a warm that could
        # not launch still printed "counts warming" — indistinguishable from one
        # genuinely in flight, every session, forever, with the child's stderr on
        # DEVNULL. Degrade visibly (G3) means saying which of the two it is.
        _init_git_repo(tmp_path)
        prawduct = _prawduct(tmp_path)
        self._state(prawduct, "octo/backlog")  # no snapshot written — warm path

        def _spawn_refuses(argv, **kwargs):
            raise OSError("cannot exec")  # spawn_detached swallows this → False

        line = briefing._backlog_pending_line(prawduct, tmp_path, popen=_spawn_refuses)
        assert line is not None
        assert "warming" not in line
        assert "counts unavailable for octo/backlog" in line
        assert "refresh-counts --repo octo/backlog" in line  # the manual path

    def test_humanize_age_buckets(self):
        assert briefing._humanize_age(5) == "just now"
        assert briefing._humanize_age(240) == "4m old"
        assert briefing._humanize_age(7200) == "2h old"
        assert briefing._humanize_age(172800) == "2d old"
        assert briefing._humanize_age(None) == "age unknown"
