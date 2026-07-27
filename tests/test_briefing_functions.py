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
import subprocess
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
        # `_get_active_work` takes the PROJECT dir now: on a views_enabled repo
        # "which chunk is current" is git-derived, so the repo root is part of
        # the question (BLD-7K3Q).
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
        monkeypatch.setattr(briefing.gates, "_has_active_build_plan_file", lambda d: build_plan)
        monkeypatch.setattr(briefing.gates, "_has_build_plan_in_state", lambda d: False)
        monkeypatch.setattr(
            briefing.gates, "session_review_verdict", lambda d: {"status": "uncovered", "reason": "no facts"}
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


class TestBacklogPendingLine:
    def _state(self, prawduct_dir: Path, scope: str | None):
        text = "product_name: t\n"
        if scope:
            text += f"backlog_service_repo: {scope}\n"
        (prawduct_dir / "project-state.yaml").write_text(text, encoding="utf-8")

    def _snapshot(self, project_dir: Path, scope: str, by_status: dict):
        from lib.backlog import snapshot

        path = snapshot.snapshot_path(project_dir)
        assert path is not None
        counts = {"total": sum(by_status.values()), "by_status": by_status, "by_stage": {}}
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
        # The warm fired, detached, with the refresh argv — and was never waited on.
        assert len(recorder.calls) == 1
        argv, kwargs = recorder.calls[0]
        assert argv[-4:] == ["backlog", "refresh-counts", "--repo", "octo/backlog"]
        assert kwargs.get("start_new_session") is True

    def test_post_cutover_no_snapshot_degrades_visibly(self, tmp_path):
        _init_git_repo(tmp_path)
        prawduct = _prawduct(tmp_path)
        self._state(prawduct, "octo/backlog")
        recorder = _PopenRecorder()
        line = briefing._backlog_pending_line(prawduct, tmp_path, popen=recorder)
        assert line == "Backlog: counts warming for octo/backlog (/prawduct:backlog to triage)"
        assert len(recorder.calls) == 1  # warm still fired

    def test_post_cutover_zero_pending_suppresses_line_but_warms(self, tmp_path):
        _init_git_repo(tmp_path)
        prawduct = _prawduct(tmp_path)
        self._state(prawduct, "octo/backlog")
        self._snapshot(tmp_path, "octo/backlog", {"shipped": 7, "dropped": 2})
        recorder = _PopenRecorder()
        line = briefing._backlog_pending_line(prawduct, tmp_path, popen=recorder)
        assert line is None
        assert len(recorder.calls) == 1

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
