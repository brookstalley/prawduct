"""Tests for the plugin runtime's PR-review gate + PR-review prose.

Covers the stop-hook PR-review-evidence gate (bin/prawduct-hook stop) and the
PR-reviewer template/skill content. The file-sync init/sync/manifest behavior
(prawduct-setup.py) retired with the engine in M4.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = REPO_ROOT / "bin" / "prawduct-hook"
FRAMEWORK_DIR = REPO_ROOT


# =============================================================================
# Helpers
# =============================================================================


def run_hook(
    command: str,
    project_dir: Path,
    *,
    git_output: str | None = "",
    git_script: str | None = None,
    gh_script_body: str | None = None,
    env_extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Run the plugin runtime (bin/prawduct-hook) with controlled mocks for git and gh.

    If git_script is provided, it's used as the full git mock script body.
    Otherwise a basic git mock is generated from git_output.
    """
    env = {
        "HOME": str(project_dir),
        "CLAUDE_PROJECT_DIR": str(project_dir),
        "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT),
        "PATH": "",
    }

    mock_bin = project_dir / "_mock_bin"
    mock_bin.mkdir(exist_ok=True)

    if git_script is not None:
        mock_git = mock_bin / "git"
        mock_git.write_text("#!/bin/bash\n" + git_script + "\nexit 0\n")
        mock_git.chmod(0o755)
    elif git_output is not None:
        mock_git = mock_bin / "git"
        # Build script line by line to avoid f-string + dedent issues
        lines = [
            "#!/bin/bash",
            'if [[ "$1" == "rev-parse" ]]; then echo ".git"; exit 0; fi',
            f'if [[ "$1" == "status" ]]; then printf \'%s\' \'{git_output}\'; exit 0; fi',
            "exit 0",
        ]
        mock_git.write_text("\n".join(lines) + "\n")
        mock_git.chmod(0o755)

    if gh_script_body is not None:
        gh_script = mock_bin / "gh"
        gh_script.write_text("#!/bin/bash\n" + gh_script_body + "\nexit 0\n")
        gh_script.chmod(0o755)

    env["PATH"] = str(mock_bin) + ":/usr/bin:/bin:/usr/sbin:/sbin"

    if env_extra:
        env.update(env_extra)

    return subprocess.run(
        ["python3", str(HOOK_PATH), command],
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )


# =============================================================================
# Hook: Stop gate for PR review evidence
# =============================================================================


class TestStopPrReviewGate:
    def test_stop_clean_without_pr(self, tmp_path: Path):
        """Stop hook exits clean when there's no PR."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()

        result = run_hook("stop", tmp_path, git_output="")
        assert result.returncode == 0

    def test_stop_with_pr_no_evidence_blocks(self, tmp_path: Path):
        """When the session changed code and a PR exists with no review
        evidence, stop should BLOCK.

        Contract renegotiated in review-fixes Chunk 1: the gate now requires
        session changes (the fixture's code diff). The original test used an
        empty `git status` and pinned the old always-probe behavior, which made
        every turn-end of a pure Q&A session on a feature branch pay a
        `gh pr list` network call — see
        `test_stop_no_session_changes_skips_pr_gate` for the new short-circuit.
        """
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()

        git_script = "\n".join([
            'if [[ "$1" == "rev-parse" ]]; then echo ".git"; exit 0; fi',
            'if [[ "$1" == "status" ]]; then printf "%s" " M src/changed.py"; exit 0; fi',
            'if [[ "$1" == "branch" && "$2" == "--show-current" ]]; then echo "feature/test-pr"; exit 0; fi',
        ])

        gh_script = "\n".join([
            'if [[ "$1" == "pr" && "$2" == "list" ]]; then echo \'[{"number": 42}]\'; exit 0; fi',
        ])

        result = run_hook(
            "stop", tmp_path,
            git_script=git_script,
            gh_script_body=gh_script,
        )
        # PR without evidence is now a blocker, not advisory
        assert result.returncode == 2
        assert "PR REVIEW" in result.stderr
        assert "PR exists for branch" in result.stderr or "no review evidence" in result.stderr

    def test_stop_no_session_changes_skips_pr_gate(self, tmp_path: Path):
        """A session with NO changes incurs no review obligation: Gate 3 must
        exit clean AND never invoke `gh` (the probe is a network call that used
        to fire on every turn-end of a no-change session on a feature branch —
        review-fixes Chunk 1). The recording mock pins the absence of the call,
        not just the absence of the blocker."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        gh_log = tmp_path.parent / "gh_calls.log"

        git_script = "\n".join([
            'if [[ "$1" == "rev-parse" ]]; then echo ".git"; exit 0; fi',
            'if [[ "$1" == "status" ]]; then printf ""; exit 0; fi',  # no session changes
            'if [[ "$1" == "branch" && "$2" == "--show-current" ]]; then echo "feature/test-pr"; exit 0; fi',
        ])
        gh_script = "\n".join([
            f'echo "$@" >> "{gh_log}"',
            'if [[ "$1" == "pr" && "$2" == "list" ]]; then echo \'[{"number": 42}]\'; exit 0; fi',
        ])

        result = run_hook(
            "stop", tmp_path,
            git_script=git_script,
            gh_script_body=gh_script,
        )
        assert result.returncode == 0
        assert "PR REVIEW" not in result.stderr
        assert not gh_log.exists(), (
            f"gh was invoked on a no-change session: {gh_log.read_text() if gh_log.exists() else ''}"
        )

    def test_stop_with_pr_and_evidence_no_warning(self, tmp_path: Path):
        """When the session changed code, a PR exists AND review evidence
        exists, no warning. (Code diff per the renegotiated Gate 3 contract —
        see test_stop_with_pr_no_evidence_blocks.)"""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        reviews_dir = prawduct / ".pr-reviews"
        reviews_dir.mkdir()
        evidence = reviews_dir / "feature--test-pr.json"
        evidence.write_text(json.dumps({
            "timestamp": "2026-03-17T14:00:00Z",
            "branch": "feature/test-pr",
            "base": "main",
            "pr_number": 42,
            "findings": [],
            "summary": "No issues found.",
        }))

        git_script = "\n".join([
            'if [[ "$1" == "rev-parse" ]]; then echo ".git"; exit 0; fi',
            'if [[ "$1" == "status" ]]; then printf "%s" " M src/changed.py"; exit 0; fi',
            'if [[ "$1" == "branch" && "$2" == "--show-current" ]]; then echo "feature/test-pr"; exit 0; fi',
        ])

        gh_script = "\n".join([
            'if [[ "$1" == "pr" && "$2" == "list" ]]; then echo \'[{"number": 42}]\'; exit 0; fi',
        ])

        result = run_hook(
            "stop", tmp_path,
            git_script=git_script,
            gh_script_body=gh_script,
        )
        assert result.returncode == 0
        # No PR review blocker expected
        assert "PR REVIEW" not in result.stderr

    def test_stop_with_pr_and_malformed_json_blocks(self, tmp_path: Path):
        """When evidence file has malformed JSON, stop should block."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        reviews_dir = prawduct / ".pr-reviews"
        reviews_dir.mkdir()
        evidence = reviews_dir / "feature--test-pr.json"
        evidence.write_text("not valid json {{{")

        git_script = "\n".join([
            'if [[ "$1" == "rev-parse" ]]; then echo ".git"; exit 0; fi',
            'if [[ "$1" == "status" ]]; then printf "%s" " M src/changed.py"; exit 0; fi',
            'if [[ "$1" == "branch" && "$2" == "--show-current" ]]; then echo "feature/test-pr"; exit 0; fi',
        ])
        gh_script = "\n".join([
            'if [[ "$1" == "pr" && "$2" == "list" ]]; then echo \'[{"number": 42}]\'; exit 0; fi',
        ])

        result = run_hook("stop", tmp_path, git_script=git_script, gh_script_body=gh_script)
        assert result.returncode == 2
        assert "PR REVIEW" in result.stderr

    def test_stop_with_pr_and_evidence_missing_findings_blocks(self, tmp_path: Path):
        """When evidence file is missing 'findings' key, stop should block."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        reviews_dir = prawduct / ".pr-reviews"
        reviews_dir.mkdir()
        evidence = reviews_dir / "feature--test-pr.json"
        evidence.write_text(json.dumps({"summary": "No issues.", "branch": "feature/test-pr"}))

        git_script = "\n".join([
            'if [[ "$1" == "rev-parse" ]]; then echo ".git"; exit 0; fi',
            'if [[ "$1" == "status" ]]; then printf "%s" " M src/changed.py"; exit 0; fi',
            'if [[ "$1" == "branch" && "$2" == "--show-current" ]]; then echo "feature/test-pr"; exit 0; fi',
        ])
        gh_script = "\n".join([
            'if [[ "$1" == "pr" && "$2" == "list" ]]; then echo \'[{"number": 42}]\'; exit 0; fi',
        ])

        result = run_hook("stop", tmp_path, git_script=git_script, gh_script_body=gh_script)
        assert result.returncode == 2
        assert "PR REVIEW" in result.stderr

    def test_stop_with_pr_and_evidence_missing_summary_blocks(self, tmp_path: Path):
        """When evidence file is missing 'summary' key, stop should block."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        reviews_dir = prawduct / ".pr-reviews"
        reviews_dir.mkdir()
        evidence = reviews_dir / "feature--test-pr.json"
        evidence.write_text(json.dumps({"findings": [], "branch": "feature/test-pr"}))

        git_script = "\n".join([
            'if [[ "$1" == "rev-parse" ]]; then echo ".git"; exit 0; fi',
            'if [[ "$1" == "status" ]]; then printf "%s" " M src/changed.py"; exit 0; fi',
            'if [[ "$1" == "branch" && "$2" == "--show-current" ]]; then echo "feature/test-pr"; exit 0; fi',
        ])
        gh_script = "\n".join([
            'if [[ "$1" == "pr" && "$2" == "list" ]]; then echo \'[{"number": 42}]\'; exit 0; fi',
        ])

        result = run_hook("stop", tmp_path, git_script=git_script, gh_script_body=gh_script)
        assert result.returncode == 2
        assert "PR REVIEW" in result.stderr

    def test_stop_on_main_branch_skips_pr_check(self, tmp_path: Path):
        """PR review check should skip main/master/develop branches. (The
        fixture carries a code diff so the branch condition — not the
        no-session-changes short-circuit — is what's exercised.)"""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()

        git_script = "\n".join([
            'if [[ "$1" == "rev-parse" ]]; then echo ".git"; exit 0; fi',
            'if [[ "$1" == "status" ]]; then printf "%s" " M src/changed.py"; exit 0; fi',
            'if [[ "$1" == "branch" && "$2" == "--show-current" ]]; then echo "main"; exit 0; fi',
        ])

        result = run_hook(
            "stop", tmp_path,
            git_script=git_script,
        )
        assert result.returncode == 0

    def test_stop_skips_pr_gate_when_pr_diff_is_doc_only(self, tmp_path: Path):
        """Gate 3 skips when the PR diff (merge-base...HEAD) is all .md, even
        when the session has uncommitted non-.md changes. Symmetric with the
        `/pr create` Step 1b fast-path: a doc-only PR was legitimately opened
        without review evidence; Gate 3 should not retroactively demand it.
        """
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()

        # Session: uncommitted .py change → session_doc_only=False, Gate 3 enters
        # PR diff: only .md committed → pr_doc_only=True, new skip applies
        git_script = "\n".join([
            'if [[ "$1" == "rev-parse" && "$2" == "--verify" && "$3" == "origin/main" ]]; then echo "abc123"; exit 0; fi',
            'if [[ "$1" == "rev-parse" && "$2" == "--verify" ]]; then exit 1; fi',
            'if [[ "$1" == "rev-parse" ]]; then echo ".git"; exit 0; fi',
            'if [[ "$1" == "status" ]]; then printf "%s" " M src/changed.py"; exit 0; fi',
            'if [[ "$1" == "branch" && "$2" == "--show-current" ]]; then echo "feature/test-pr"; exit 0; fi',
            'if [[ "$1" == "diff" && "$2" == "--name-only" ]]; then echo ".prawduct/backlog.md"; echo "docs/notes.md"; exit 0; fi',
        ])

        gh_script = "\n".join([
            'if [[ "$1" == "pr" && "$2" == "list" ]]; then echo \'[{"number": 42}]\'; exit 0; fi',
        ])

        result = run_hook("stop", tmp_path, git_script=git_script, gh_script_body=gh_script)

        # Gate 3 should be skipped — no PR REVIEW blocker even though no
        # evidence file exists, because the PR is currently doc-only.
        assert "PR REVIEW" not in result.stderr

    def test_stop_still_blocks_when_pr_diff_includes_code(self, tmp_path: Path):
        """Confirms the doc-only skip is conditional, not unconditional:
        Gate 3 still BLOCKS when the PR's diff has any non-.md file and
        no evidence exists. Inverse of the previous test — guards against
        a future refactor accidentally over-broadening the skip.
        """
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()

        git_script = "\n".join([
            'if [[ "$1" == "rev-parse" && "$2" == "--verify" && "$3" == "origin/main" ]]; then echo "abc123"; exit 0; fi',
            'if [[ "$1" == "rev-parse" && "$2" == "--verify" ]]; then exit 1; fi',
            'if [[ "$1" == "rev-parse" ]]; then echo ".git"; exit 0; fi',
            'if [[ "$1" == "status" ]]; then printf "%s" " M src/changed.py"; exit 0; fi',
            'if [[ "$1" == "branch" && "$2" == "--show-current" ]]; then echo "feature/test-pr"; exit 0; fi',
            'if [[ "$1" == "diff" && "$2" == "--name-only" ]]; then echo "src/app.py"; echo "docs/notes.md"; exit 0; fi',
        ])

        gh_script = "\n".join([
            'if [[ "$1" == "pr" && "$2" == "list" ]]; then echo \'[{"number": 42}]\'; exit 0; fi',
        ])

        result = run_hook("stop", tmp_path, git_script=git_script, gh_script_body=gh_script)

        assert result.returncode == 2
        assert "PR REVIEW" in result.stderr

    def test_stop_blocks_fileset_eligible_code_pr_no_trivial_skip(self, tmp_path: Path):
        """Regression for the retired `Type: trivial` PR fast-path (incoming-bug:
        check-pr-trivial-passes-feature-clusters-that-only-touch-existing-files).

        A code PR whose commits ONLY modify existing non-.md files is
        "fileset-eligible" — the retired `check-pr-trivial` / `_pr_diff_is_trivial`
        path reported it `trivial` and skipped BOTH the cumulative-Critic and
        PR-reviewer gates. With that path gone, only a doc-only PR is
        evidence-exempt at Gate 3, so this PR must BLOCK when no review evidence
        exists.

        The `git log --name-status` mock returns a fileset-eligible modification
        (`M src/app.py`) — the exact diff the old trivial walk would have passed.
        It is inert today (nothing consumes the commit walk), but guards against a
        future re-introduction of a fileset-as-detector fast-path: that would make
        this PR skip the gate again and trip the assertions below.
        """
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()

        git_script = "\n".join([
            'if [[ "$1" == "rev-parse" && "$2" == "--verify" && "$3" == "origin/main" ]]; then echo "abc123"; exit 0; fi',
            'if [[ "$1" == "rev-parse" && "$2" == "--verify" ]]; then exit 1; fi',
            'if [[ "$1" == "rev-parse" ]]; then echo ".git"; exit 0; fi',
            # Session: uncommitted .py change → session not doc-only → Gate 3 enters.
            'if [[ "$1" == "status" ]]; then printf "%s" " M src/app.py"; exit 0; fi',
            'if [[ "$1" == "branch" && "$2" == "--show-current" ]]; then echo "feature/test-pr"; exit 0; fi',
            # PR diff (doc-only check): a modified existing .py → NOT doc-only.
            'if [[ "$1" == "diff" && "$2" == "--name-only" ]]; then echo "src/app.py"; exit 0; fi',
            # Fileset-eligible commit walk (latent re-introduction guard; see docstring).
            'if [[ "$1" == "log" ]]; then echo "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"; printf "M\\tsrc/app.py\\n"; exit 0; fi',
        ])

        gh_script = "\n".join([
            'if [[ "$1" == "pr" && "$2" == "list" ]]; then echo \'[{"number": 42}]\'; exit 0; fi',
        ])

        result = run_hook("stop", tmp_path, git_script=git_script, gh_script_body=gh_script)

        assert result.returncode == 2
        assert "PR REVIEW" in result.stderr


# =============================================================================
# Template content validation
# =============================================================================


class TestPrReviewSkillContent:
    """The PR-review prose now lives only in the plugin — the file-sync
    `templates/pr-review.md` + `templates/skill-pr.md` retired in M4 Chunk 4.
    `skills/pr/review-protocol.md` carries the reviewer's 4 release-readiness goals;
    `skills/pr/SKILL.md` carries the /pr lifecycle flows + the review gate."""

    def test_review_protocol_has_all_goals(self):
        """The PR review protocol should cover the 4 release-readiness goals.

        Contract change (PRR-4M9T): the PR reviewer's goals were trimmed to drop
        the ones that overlapped the Critic (No Bugs Shipped, Tests Cover the
        Change, Proportionality). With the layering now explicit — per-chunk
        Critic = local correctness, final/cumulative Critic = bundle synthesis,
        PR reviewer = release readiness — the reviewer owns only the
        release-specific lens: scope, narrative/coherence, merge hygiene, and
        bundle-level simplification. The dropped goals are asserted absent in
        test_review_protocol_dropped_critic_overlap_goals so the trim doesn't
        silently regrow.
        """
        content = (FRAMEWORK_DIR / "skills" / "pr" / "review-protocol.md").read_text()
        for goal in (
            "Right Scope", "Clear Narrative", "Merge Hygiene",
            "Bundle-Level Simplification",
        ):
            assert goal in content, f"skills/pr/review-protocol.md missing goal: {goal}"

    def test_review_protocol_dropped_critic_overlap_goals(self):
        """The Critic-overlapping PR-reviewer goals must stay removed (PRR-4M9T).

        Guards the trim's intent: these were retired as standalone goals because
        the Critic already owns bugs, test quality, and proportionality. The
        words may still appear in prose that delineates the layering (e.g.
        "do not re-litigate bugs ... or proportionality"), so we assert the
        absence of the goal *headings* specifically, not the bare terms.
        """
        content = (FRAMEWORK_DIR / "skills" / "pr" / "review-protocol.md").read_text()
        for heading in (
            "### 1. No Bugs Shipped",
            "### 2. Tests Cover the Change",
            "### 7. Proportionality",
            "## 7. Proportionality",
        ):
            assert heading not in content, (
                f"skills/pr/review-protocol.md still has dropped goal heading: {heading}"
            )

    def test_review_protocol_has_backlog_reconciliation(self):
        """R-1/R-2 backlog reconciliation (spec §7a) must stay in the PR review
        protocol — guards against a silent trim deleting the checks."""
        content = (FRAMEWORK_DIR / "skills" / "pr" / "review-protocol.md").read_text()
        assert "Backlog reconciliation" in content
        assert "R-1" in content and "R-2" in content
        assert "closes:" in content  # the R-2 data-inconsistency signal

    def test_pr_skill_has_all_flows(self):
        """The /pr skill should cover all 4 flows."""
        content = (FRAMEWORK_DIR / "skills" / "pr" / "SKILL.md").read_text()
        for flow in ("Create Flow", "Update Flow", "Merge Flow", "Status Flow"):
            assert flow in content, f"skills/pr/SKILL.md missing flow: {flow}"

    def test_pr_skill_has_review_gate(self):
        """The /pr skill must enforce review before PR creation."""
        content = (FRAMEWORK_DIR / "skills" / "pr" / "SKILL.md").read_text()
        # Must contain hard gate language, not just numbered steps
        assert "MANDATORY" in content
        assert "Do NOT proceed" in content or "DO NOT proceed" in content
        assert "evidence file" in content

    def test_merge_flow_step7_is_conditioned(self):
        """PR-7Q3M: build-plan cleanup must branch on whether THIS merge is the
        release — delete at the release surface, RETAIN while release-pending —
        not unconditionally delete. Guards against a revert to the old
        develop-merge=release assumption."""
        content = (FRAMEWORK_DIR / "skills" / "pr" / "SKILL.md").read_text()
        # The discriminator is resolve-base, and BOTH branches must be present.
        assert "resolve-base" in content, "step 7 must branch on resolve-base"
        assert "RETAIN" in content, "step 7 must keep the plan while release-pending"
        assert "active_build_plan" in content, (
            "deletion must resolve the pointer, not a hardcoded build-plan.md path"
        )
        # The release-pending branch must be tied to the develop base / status=merged.
        assert "release-pending" in content or "status=merged" in content

    def test_create_flow_redirects_release_promotion(self):
        """REL-8K3M: the /pr skill must detect a release/integration context
        (current branch is the integration base or release surface, not a feature
        branch) and redirect to the manual release process instead of running the
        feature-PR gates. Without this, the cumulative-Critic gate (Step 2)
        false-positives on a develop->main release because release-prep touches
        non-.md version files the gate's docs-only allowance doesn't cover.
        Guards the redirect against silent removal."""
        content = (FRAMEWORK_DIR / "skills" / "pr" / "SKILL.md").read_text()
        assert "Release-promotion guard" in content, (
            "the /pr skill must carry an explicit release-promotion guard"
        )
        assert "docs/release-process.md" in content, (
            "the guard must redirect a release promotion to docs/release-process.md"
        )
        # The redirect must be tied to being on develop/main (release surfaces),
        # not a feature branch — that's the discriminator.
        assert "release surface" in content or "release/integration context" in content, (
            "the guard must key off the release/integration branch context"
        )

    def test_release_process_documents_benign_cumulative_exit(self):
        """REL-8K3M (the doc half): release-process.md must document that a
        check-cumulative-critic exit-1 during release-prep is expected/benign and
        is neither a gate to satisfy nor a waiver case — so a contributor doing a
        release doesn't re-run the cumulative Critic over version bumps (the
        CRT-7M2D treadmill) or pollute the waiver file."""
        content = (FRAMEWORK_DIR / "docs" / "release-process.md").read_text()
        assert "not the release vehicle" in content, (
            "release-process.md must state /prawduct:pr is not the release vehicle"
        )
        assert "check-cumulative-critic" in content and "benign" in content, (
            "release-process.md must explain the benign cumulative-Critic exit-1"
        )
        # Must steer away from BOTH wrong moves: re-running the Critic and waiving.
        assert ".gates-waived" in content, (
            "release-process.md must say the benign exit-1 is not a waiver case"
        )

    def test_review_protocol_references_learnings(self):
        """PR reviewer must read learnings.md during setup."""
        content = (FRAMEWORK_DIR / "skills" / "pr" / "review-protocol.md").read_text()
        assert "learnings.md" in content

    def test_review_protocol_has_learnings_crosscheck(self):
        """PR reviewer must have a Learnings Cross-Check section."""
        content = (FRAMEWORK_DIR / "skills" / "pr" / "review-protocol.md").read_text()
        assert "Learnings Cross-Check" in content


class TestPrReviewerScoping:
    """PR-reviewer scoping (review-proportionality ch.05): the reviewer
    consumes the gate-qualifying Critic record as evidence, audits it with
    adversarial spot-checks, and falls back to a full code-soundness pass
    when the audit fails. Losing any one of these silently reverts the
    reviewer to re-deriving what the cumulative already certified — the
    duplication this chunk removed — or, worse, to trusting the record
    blindly (the independence this chunk preserved)."""

    @property
    def protocol(self) -> str:
        return (FRAMEWORK_DIR / "skills" / "pr" / "review-protocol.md").read_text()

    @property
    def skill(self) -> str:
        return (FRAMEWORK_DIR / "skills" / "pr" / "SKILL.md").read_text()

    def test_protocol_has_audit_duty(self):
        """The record is audited (≥2 adversarial spot-checks), never trusted
        blindly — the independence-preserving half of the scoping."""
        content = self.protocol
        assert "Evidence, Not Truth" in content
        assert "at least 2 substantive claims" in content
        assert "adversarial" in content.lower()

    def test_protocol_has_void_fallback(self):
        """Any failed spot-check voids the record → full code-soundness pass,
        stated in the output. Without this, a wrong record scopes the review
        anyway."""
        content = self.protocol
        assert "voids the record" in content
        assert "full code-soundness pass" in content
        assert "record_consumed" in content

    def test_protocol_resolves_record_like_the_gate(self):
        """The reviewer's record resolution mirrors check-cumulative-critic:
        latest findings file when its kind qualifies, else the newest
        qualifying review.critic ledger event."""
        content = self.protocol
        assert ".critic-findings.json" in content
        assert ".governance-ledger.jsonl" in content
        assert "extends_cumulative" in content

    def test_protocol_evidence_distinguishes_scoped_from_full(self):
        """Telemetry separates scoped from full runs by the evidence `mode`
        field (pr-scoped/pr-full) plus the audit trail (spot_checks)."""
        content = self.protocol
        assert "pr-scoped" in content
        assert "pr-full" in content
        assert "spot_checks" in content

    def test_skill_hands_record_to_reviewer(self):
        """Step 3 names the record source for the reviewer (file, or ledger
        line when Step 2 reported ledger-fallback)."""
        content = self.skill
        assert "gate-qualifying Critic record" in content
        assert "ledger-fallback" in content

    def test_skill_appends_review_pr_ledger_event(self):
        """Step 4 appends the review.pr event so both review roles are in the
        ledger (data requirement 1: model efficiency per role)."""
        content = self.skill
        assert "ledger-append --event review.pr" in content
        frontmatter = content.split("---", 2)[1]
        assert "Bash(prawduct-hook ledger-append *)" in frontmatter, (
            "skills/pr/SKILL.md allowed-tools is missing ledger-append — "
            "the skill cannot append the review.pr event."
        )


# =============================================================================
# Discoverability in the plugin guidance layer
# =============================================================================


class TestDiscoverability:
    def test_building_methodology_mentions_pr(self):
        """Building methodology should mention /pr."""
        content = (FRAMEWORK_DIR / "methodology" / "building.md").read_text()
        assert "/pr" in content
        assert "PR reviewer" in content or "PR review" in content

    def test_framework_claude_mentions_pr(self):
        """Framework CLAUDE.md should mention /pr."""
        content = (FRAMEWORK_DIR / "CLAUDE.md").read_text()
        assert "/pr" in content
