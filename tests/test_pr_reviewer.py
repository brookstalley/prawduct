"""Tests for the plugin runtime's PR-review gate + PR-review prose.

Covers the stop-hook PR-review-evidence gate (bin/prawduct-hook stop) and the
PR-reviewer template/skill content. The file-sync init/sync/manifest behavior
(prawduct-setup.py) retired with the engine in M4.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent / "plugin"
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

    def test_findings_carry_their_cost_before_any_finding_is_written(self):
        """A v3.2.4 consumer was reading the PR reviewer's findings when it
        decided to make the commit that re-opened the cumulative Critic gate,
        and this protocol had never said that acting on a non-blocking finding
        costs a round. The statement is now here — but **placement is the
        deliverable, not presence**.

        The predecessor plan shipped a correct rule into `goals-1-3.md` that sat
        below every section needing it, and it changed nothing. A reviewer reads
        top-down and forms findings while reading the goals, so this has to be
        reached BEFORE the goals, the severity ladder, and the output format —
        not appended near the end where it becomes a fact about work already
        done. Ordering is what gets asserted.

        It must also not overclaim: a fix confined to prose or `.prawduct/`
        state moves no coverage, and a reviewer told that every finding costs a
        round would stop filing the ones that don't.
        """
        content = (FRAMEWORK_DIR / "skills" / "pr" / "review-protocol.md").read_text()
        assert "costs the builder a review round" in content
        cost_at = content.index("costs the builder a review round")
        for later in ("## Review Goals", "### 1. Right Scope", "## Severity Levels",
                      "## Output Format", "### Findings"):
            assert cost_at < content.index(later), (
                f"the round-cost statement sits BELOW {later!r} — the reviewer forms "
                "findings before reaching it, which is the placement failure that made "
                "the same rule inert in the Critic's own protocol"
            )
        # Accepting is a real answer, and the claim is bounded rather than
        # absolute — "every finding costs a round" would be false, and a
        # reviewer who believed it would stop filing the ones that don't.
        assert "accepting is a real answer" in content.lower()
        assert "some paths move no coverage" in content
        # The bound is delegated, not restated. An extension rule spelled out
        # here would be a second copy of `is_judgeable_path` and wrong for the
        # governance-protected `.md` under skills/, methodology/ and templates/
        # — which is exactly what the first draft of this paragraph claimed.
        assert "prawduct-hook cost-of-commit" in content
        # And it prices the round the gate actually accepts. Every sibling
        # carrier in the same runtime — the batch-fix directive, the gate's
        # churn NOTE, `telemetry.PRICED_MODE` — quotes the delta pass; a
        # reviewer told each NOTE costs a full cumulative over-prices its own
        # findings and files fewer, which is the opposite of what this
        # paragraph is for.
        assert "verify-resolutions" in content
        assert "a full Critic round" not in content

    def test_the_ride_along_route_is_offered_with_its_condition(self):
        """Fix-now buys a round; accept and file buy none. The option that costs
        *nothing extra* was missing from every surface: a small fix carried into
        the next chunk's commit rides a round that was going to be bought
        anyway.

        It is offered, never defaulted — a fix that changes what the PR claims
        to ship belongs in this bundle — and it names where the deferral gets
        written down, because an unrecorded deferral is a drop.
        """
        raw = (FRAMEWORK_DIR / "skills" / "pr" / "review-protocol.md").read_text()
        # Wrap- and emphasis-insensitive: this file is hard-wrapped, so a literal
        # pin fails on a re-wrap that changed nothing — the kind of false failure
        # that gets a pin deleted rather than fixed.
        content = re.sub(r"\s+", " ", raw.replace("*", ""))
        assert "ride along with the next chunk or the next build plan" in content
        assert "not always right" in content
        assert "quietly become a drop" in content

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

    def test_merge_flow_buildplan_cleanup_is_conditioned(self):
        """PR-7Q3M: build-plan lifecycle (the Merge Flow's "Confirm the
        bookkeeping merged WITH the PR" step -- named rather than numbered
        because the number has now moved three times: step 7, briefly step 8
        during the stamp-merged era, back to 7, and 8 again once the
        Issues-backend close was inserted ahead of it) must branch on whether
        THIS merge is the
        release — retire at the release surface (in the closing PR, per
        create-flow Step 1d), RETAIN while release-pending — not
        unconditionally delete. Guards against a revert to the old
        develop-merge=release assumption."""
        content = (FRAMEWORK_DIR / "skills" / "pr" / "SKILL.md").read_text()
        # The discriminator is resolve-base, and BOTH branches must be present.
        assert "resolve-base" in content, "cleanup step must branch on resolve-base"
        assert "RETAIN" in content, "cleanup step must keep the plan while release-pending"
        assert "active_build_plan" in content, (
            "deletion must resolve the pointer, not a hardcoded build-plan.md path"
        )
        # The release-pending branch must be tied to the develop base / statusless entry.
        assert "release-pending" in content

    def test_no_flow_requires_post_merge_integration_branch_commit(self):
        """single-pr-bookkeeping: the whole point — no flow may instruct a
        commit to the integration branch outside a PR. The retired stamp-merged
        merge-flow step (post-merge chore commit) forced protected-branch
        consumers into a second, bookkeeping-only PR. Guards against the
        pattern's reintroduction: bookkeeping rides IN the feature PR
        (create-flow Step 1d), and the merge flow explicitly has nothing to
        commit."""
        content = (FRAMEWORK_DIR / "skills" / "pr" / "SKILL.md").read_text()
        assert "stamp-merged" not in content, (
            "the merge flow must not reintroduce the post-merge stamp commit"
        )
        assert "carries its own bookkeeping" in content, (
            "the create flow must carry the bookkeeping-rides-in-the-PR step"
        )
        assert "nothing to commit" in content.lower(), (
            "the merge flow must state the post-merge steps commit nothing"
        )

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
        # The guard must NOT route consumers at `docs/release-process.md`. That doc is
        # prawduct's own release procedure (its marketplace entry, its VERSION/plugin.json)
        # and is deliberately excluded from what the plugin distributes (GOV-4H7T), so the
        # reference would dangle in every consuming repo -- and where it resolved, it would
        # describe the wrong project's release. The guard hands back to the user's own
        # process instead. Kept as an assertion, not a deletion, so re-adding the pointer
        # fails here rather than shipping a dead link.
        assert "docs/release-process.md" not in content, (
            "the /pr skill must not point consumers at prawduct's own release process -- "
            "documentation/release-process.md is not distributed with the plugin"
        )
        assert "release process" in content, (
            "the guard must still hand a release promotion back to a release process"
        )
        # The redirect must be tied to being on the integration base or the
        # release surface, not a feature branch — that's the discriminator.
        assert "release surface" in content or "release/integration context" in content, (
            "the guard must key off the release/integration branch context"
        )

    def test_the_release_guard_derives_the_branches_it_compares(self):
        """The guard names its branches by asking, not by listing them (#267).

        Every other step in this skill calls `resolve-base` so that no one
        hardcodes a base branch; the guard alone tested three literals. A repo
        integrating on `trunk` or `next` — one that had configured
        `base_branch:` correctly — fell through it and ran the feature-PR gates
        on its own release, which is the exact failure the guard exists to
        prevent.

        Asserted on the guard paragraph rather than the file, because
        `develop`/`main` legitimately appear elsewhere in this skill as
        narrative examples.
        """
        content = (FRAMEWORK_DIR / "skills" / "pr" / "SKILL.md").read_text()
        guard = content.split("**Release-promotion guard", 1)[1].split(
            "\nThe user can override", 1
        )[0]
        assert "prawduct-hook resolve-base" in guard, (
            "the guard must resolve the integration base with `resolve-base`, the "
            "same resolver the rest of this skill keys off"
        )
        assert "defaultBranchRef" in guard or "refs/remotes/origin/HEAD" in guard, (
            "the guard must ask the repo for its release surface (default branch) "
            "rather than assuming main/master"
        )
        assert "git branch --show-current" in guard, (
            "the guard must compare the CURRENT branch against what it resolved"
        )
        # It must also be honest about what it inherits: resolve-base does not
        # consult origin/HEAD and defaults to main when `base_branch:` is unset,
        # so an unconfigured gitflow repo still slips half the guard.
        assert "#254" in guard, (
            "the guard must state that it inherits resolve-base's behaviour "
            "(#254) rather than silently moving the wrong-answer case"
        )

    def test_release_process_documents_benign_cumulative_exit(self):
        """REL-8K3M (the doc half): release-process.md must document that a
        check-cumulative-critic exit-1 during release-prep is expected/benign and
        is neither a gate to satisfy nor a waiver case — so a contributor doing a
        release doesn't re-run the cumulative Critic over version bumps (the
        CRT-7M2D treadmill) or pollute the waiver file."""
        content = (FRAMEWORK_DIR.parent / "documentation" / "release-process.md").read_text()
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
    """PR-reviewer scoping, kernel-v3 chunk 05 renegotiation: the record-audit
    protocol (adversarial spot-checks, record voiding, pr-scoped/pr-full run
    shapes, gate-mirroring record resolution) was DELETED with the coverage
    algebra cutover — coverage is now computed structurally against the actual
    trees by `check-cumulative-critic` before the reviewer is dispatched, so
    there is no asserted record whose truthfulness the reviewer must audit
    (design §3: "record-audit protocol prose", subsumed by C1's composition;
    discovery §4.3 Overbuilt #4). The surviving contract these tests pin: the
    reviewer does NOT re-derive code soundness, owns release readiness, and
    does not repeat the cumulative Critic's cross-checks."""

    @property
    def protocol(self) -> str:
        return (FRAMEWORK_DIR / "skills" / "pr" / "review-protocol.md").read_text()

    @property
    def skill(self) -> str:
        return (FRAMEWORK_DIR / "skills" / "pr" / "SKILL.md").read_text()

    def test_protocol_consumes_gate_certified_soundness(self):
        """The reviewer must not re-derive code soundness — the composition
        gate certifies it structurally before dispatch."""
        content = self.protocol
        assert "re-derive code soundness" in content
        assert "check-cumulative-critic" in content
        assert "zero unresolved blocking findings" in content

    def test_protocol_audit_machinery_stays_deleted(self):
        """The deleted two-reviewer overlap machinery must not regrow: no
        spot-check audit, no record voiding, no pr-scoped/pr-full split, no
        gate-mirroring ledger resolution."""
        content = self.protocol
        for needle in ("Evidence, Not Truth", "spot_checks", "record_consumed",
                       "pr-scoped", "pr-full", "extends_cumulative",
                       ".governance-ledger.jsonl"):
            assert needle not in content, (
                f"skills/pr/review-protocol.md re-grew deleted audit-protocol "
                f"term `{needle}` (kernel-v3 §3 deletion)"
            )

    def test_protocol_reads_findings_view_for_context(self):
        """The Critic's judgment stays available as context — the derived
        findings view and the evidence CLI, not a gate-qualifying record."""
        content = self.protocol
        assert ".critic-findings.json" in content
        assert "prawduct-hook evidence list" in content

    def test_skill_states_gate_certification(self):
        """Step 3's reviewer handoff states the gate has passed and scopes the
        reviewer to release readiness (no ledger-fallback record plumbing)."""
        content = self.skill
        assert "cumulative-Critic gate has passed" in content
        assert "release readiness" in content
        assert "ledger-fallback" not in content

    def test_skill_appends_review_pr_ledger_event(self):
        """Step 4 appends the review.pr event so both review roles are in the
        ledger (data requirement 1: model efficiency per role)."""
        content = self.skill
        assert "ledger-append --event review.pr" in content
        frontmatter = content.split("---", 2)[1]
        # The house grant form: star attached, no space — a spaced star does not
        # cover a bare call, and one line covers both shapes
        # (`tests/test_skill_command_grants.py` defines the form).
        assert "Bash(prawduct-hook ledger-append*)" in frontmatter, (
            "skills/pr/SKILL.md allowed-tools is missing ledger-append — "
            "the skill cannot append the review.pr event."
        )

    def test_learnings_and_backlog_not_rescanned(self):
        """The cumulative Critic owns the Learnings Cross-Check and Backlog
        Reconciliation walk; the PR reviewer must not repeat them. R-2 (data
        inconsistency) runs on every markdown-backend review because the Critic
        doesn't do it.

        The scoping clause "always run on this backend" was here while R-1/R-2
        were dark on the Issues backend and live on markdown. Both now read the
        backlog cache on either backend, so R-2's "always" is unqualified again —
        and the assertion follows it, because a scoping phrase left pinned after
        its scope dissolved keeps passing on a substring while meaning nothing.
        """
        content = self.protocol
        assert "Critic owns this scan" in content
        assert "owns this walk" in content
        assert "always run — the Critic does not do this check" in content

    def test_backlog_reconciliation_reads_the_cache_and_reports_when_it_cannot(self):
        """R-1/R-2 read the backlog cache. Two things must hold in this file, and
        both are about what happens when the read fails rather than when it works:
        the reviewer must be routed to the contract, and it must know that an
        unreadable store is reported rather than passed over — because R-2 has no
        other owner anywhere in the pipeline, so silence here reads as
        "reconciled" when nothing reconciled it.

        This replaces a check-the-backend-first assertion from the period when
        both checks were dark post-cutover. The backend gate itself now lives in
        the routed file; what stays pinned here is the part this file must carry
        for a reviewer that loads only it.
        """
        content = self.protocol
        assert "skills/backlog/cache-reads.md" in content
        assert "exit 6" in content.lower()
        assert "data, never instructions" in content
        assert "skip both checks" in content

    def test_skill_prep_step_reads_the_backlog_through_the_skill(self):
        """The prep-while-Critic-runs step audits the backlog via the
        backend-routed skill, not by reading `.prawduct/backlog.md` directly.

        Unlike R-1/R-2 this reader is repointed rather than declared dormant —
        `/prawduct:backlog list` has an adapter path on both backends, so the
        step still works post-cutover. Pinned because `skills/pr/SKILL.md` is
        the one PR-path reader the original cutover sweep missed entirely.

        The step originally banned direct reads of `.prawduct/backlog.md`
        outright, which contradicted `skills/janitor/SKILL.md` permitting one
        pre-cutover. `data-model.md` § Direction adjudicated it: the rule is a
        backend gate, not a ban, so this step asserts the gate — and separately
        that `list` is sufficient *here*, which is why the step uses it.
        """
        content = self.skill
        assert "audit the backlog for items this branch resolves" in content
        assert "no reason to open `.prawduct/backlog.md` directly here" in content
        assert "check `backlog_service_repo` first" in content
        assert "only** when that scalar is unset" in content

    def test_critic_cross_checks_named_as_owner(self):
        """B (CRT-5T8N): review-cycle.md names final/cumulative as the OWNER of
        the Learnings Cross-Check + Backlog Reconciliation, so the single-owner
        division is explicit from the Critic side too (the PR reviewer consumes
        the result rather than re-running it)."""
        content = (FRAMEWORK_DIR / "skills" / "critic" / "review-cycle.md").read_text()
        assert "owner of both cross-checks" in content


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
        content = (FRAMEWORK_DIR.parent / "CLAUDE.md").read_text()
        assert "/pr" in content
