"""Tests for the `/prawduct:pr` skill and the Stop hook's posture toward a PR.

The PR boundary has one reviewer, the cumulative Critic: `/prawduct:pr`
dispatches no agent, and the Stop hook asks nothing of an open PR. What the
skill gates on is composed review coverage (`check-cumulative-critic`), the
hygiene check (`check-pr-hygiene`) and the template check (`check-pr-body`).
This file pins the skill's flows and the Stop hook's silence; the commands
themselves are tested beside their handlers.
"""

from __future__ import annotations

import json
import sys
import re
import subprocess
from pathlib import Path

import pytest

from conftest import SHAPED_REFLECTION

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
        [sys.executable, str(HOOK_PATH), command],
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )


# =============================================================================
# Hook: the Stop hook asks nothing of an open PR
# =============================================================================


_FEATURE_BRANCH_WITH_CODE = "\n".join([
    'if [[ "$1" == "rev-parse" ]]; then echo ".git"; exit 0; fi',
    'if [[ "$1" == "status" ]]; then printf "%s" " M src/changed.py"; exit 0; fi',
    'if [[ "$1" == "branch" && "$2" == "--show-current" ]]; then echo "feature/test-pr"; exit 0; fi',
])


class TestStopAsksNothingOfAPr:
    """The Stop hook's PR-review evidence gate left with the evidence it read.

    The fixture is the one that gate blocked on: a session that changed code,
    on a feature branch, with a PR open and no evidence file. It now passes,
    and — the cost the gate carried on every turn-end — `gh` is never run.
    The recording mock pins the absence of the call, not just of the blocker.
    """

    def _gh_logging(self, log: Path) -> str:
        return "\n".join([
            f'echo "$@" >> "{log}"',
            'if [[ "$1" == "pr" && "$2" == "list" ]]; then echo \'[{"number": 42}]\'; exit 0; fi',
        ])

    def test_a_pr_with_no_evidence_file_does_not_block_and_runs_no_gh(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        # Satisfy the reflection gate so nothing else can block this Stop.
        (prawduct / ".session-reflected").write_text(SHAPED_REFLECTION)
        gh_log = tmp_path.parent / "gh_calls.log"

        result = run_hook(
            "stop", tmp_path,
            git_script=_FEATURE_BRANCH_WITH_CODE,
            gh_script_body=self._gh_logging(gh_log),
        )
        assert result.returncode == 0, result.stderr
        assert "PR REVIEW" not in result.stderr
        assert "pr-reviews" not in result.stderr
        assert not gh_log.exists(), (
            f"the Stop hook ran gh: {gh_log.read_text() if gh_log.exists() else ''}"
        )

    def test_the_stop_hook_source_holds_no_pr_probe(self):
        """The behavioural test above sees one fixture; this sees the code. A
        `gh pr` call anywhere in `cmd_stop` is a network probe on every
        turn-end, whatever condition guards it."""
        import importlib.machinery
        import importlib.util
        import inspect

        loader = importlib.machinery.SourceFileLoader("prawduct_hook_pr_skill", str(HOOK_PATH))
        spec = importlib.util.spec_from_loader("prawduct_hook_pr_skill", loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        source = inspect.getsource(module.cmd_stop)
        assert '"gh"' not in source and "'gh'" not in source, "cmd_stop runs gh again"
        assert ".pr-reviews" not in source
        # Control: the reader reached the real Stop body.
        assert "_WAIVER_KEY_BY_GATE" in source

    def test_a_gates_waived_file_carrying_pr_raises_nothing_and_waives_nothing(self, tmp_path: Path):
        """An old session's `.gates-waived` may still carry a `pr` key. It is
        tolerated — no error, no traceback — and named as retired rather than
        as the typo an unknown key usually is. It waives nothing, because there
        is no gate left for it to waive."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-reflected").write_text(SHAPED_REFLECTION)
        (prawduct / ".gates-waived").write_text(json.dumps({"pr": "merge is not happening today"}))

        result = run_hook("stop", tmp_path, git_script=_FEATURE_BRANCH_WITH_CODE)
        assert result.returncode == 0, result.stderr
        assert "Traceback" not in result.stderr
        assert "retired keys (no effect): pr" in result.stderr
        assert "unknown keys" not in result.stderr
        # Nothing was waived, so no waiver note claims a suppression.
        assert "pr: waived" not in result.stderr

    def test_the_pr_waiver_key_is_retired_not_live(self):
        """The waiver map no longer names a `pr` gate, and the retired table
        does — the two tables are what the Stop hook's note reads."""
        import importlib.machinery
        import importlib.util

        loader = importlib.machinery.SourceFileLoader("prawduct_hook_pr_waiver", str(HOOK_PATH))
        spec = importlib.util.spec_from_loader("prawduct_hook_pr_waiver", loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        assert "pr" not in module._WAIVER_KEY_BY_GATE
        assert "pr" not in module._WAIVER_KEY_BY_GATE.values()
        assert "pr" in module._RETIRED_WAIVER_KEYS
        # A rewritten waiver file drops the retired key rather than carrying it.
        footer = module._waiver_footer(["critic"], False, {"pr": "old", "reflection": "kept"})
        assert '"pr"' not in footer and '"reflection"' in footer

    def test_the_gate_registry_names_no_pr_gate(self):
        registry = json.loads((REPO_ROOT / "hooks" / "gates.json").read_text())
        ids = {g["id"] for g in registry["gates"]}
        assert "critic" in ids, "control: the registry was read"
        assert "pr" not in ids


# =============================================================================
# Skill content
# =============================================================================


def _skill() -> str:
    return (FRAMEWORK_DIR / "skills" / "pr" / "SKILL.md").read_text()


def _frontmatter() -> str:
    return _skill().split("---", 2)[1]


def _step(text: str, start: str, end: str) -> str:
    at = text.index(start)
    return text[at:text.index(end, at)]


class TestNoReviewerIsDispatched:
    """`/prawduct:pr` opens a PR with no agent dispatched (#1129, owner ruling
    2026-11-10). Each pin names what would have to come back for it to fail."""

    def test_the_skill_grants_no_agent_tool(self):
        tools = [t.strip() for t in _frontmatter().split("allowed-tools:", 1)[1].splitlines()[0].split(",")]
        assert "Read" in tools and "Write" in tools, "control: the grant line was parsed"
        assert "Agent" not in tools, "the PR skill can spawn an agent again"

    def test_the_body_names_no_reviewer_dispatch(self):
        body = _skill().split("---", 2)[2]
        for retired in ("subagent_type", "pr-reviewer", "pr-review-dispatch",
                        "pr-review-payload", "Tell the reviewer agent",
                        "review-protocol.md", "release-readiness"):
            assert retired not in body, f"the skill body names {retired!r} again"
        assert "dispatches no agent" in body, (
            "control and contract: the skill says in its own words that it dispatches none"
        )

    def test_no_evidence_file_and_no_reviewed_commit_field(self):
        content = _skill()
        for retired in (".pr-reviews", "commit_reviewed", "ledger-append", "review.pr",
                        "evidence file"):
            assert retired not in content, f"the skill names {retired!r} again"

    def test_the_two_new_commands_are_granted_exactly(self):
        """House form (`tests/test_skill_command_grants.py`): the star attached,
        because both take arguments. And exact: neither grant may be a prefix
        another command name extends."""
        fm = _frontmatter()
        assert "Bash(prawduct-hook check-pr-hygiene*)" in fm
        assert "Bash(prawduct-hook check-pr-body*)" in fm
        assert "Bash(prawduct-hook check-pr*)" not in fm
        assert "Bash(prawduct-hook check-pr-*)" not in fm


class TestPrReviewSkillContent:
    """`skills/pr/SKILL.md` carries the /pr lifecycle flows and their gates."""

    def test_pr_skill_has_all_flows(self):
        """The /pr skill should cover all 4 flows."""
        content = (FRAMEWORK_DIR / "skills" / "pr" / "SKILL.md").read_text()
        for flow in ("Create Flow", "Update Flow", "Merge Flow", "Status Flow"):
            assert flow in content, f"skills/pr/SKILL.md missing flow: {flow}"

    def test_the_mutation_sweep_lands_before_the_one_boundary_review(self):
        """PLACEMENT, not presence — the sweep is a PRE-review obligation.

        The rule moved here from the `test-evidence record` directive because a
        mutation costs a run per claim: the inner loop keeps only the cheap half
        (name what would turn each test red) and the boundary pays for the
        mutations, once, over the whole bundle. `docs/discipline.md` row 1 names
        this file as its surface and `tests/test_discipline_table.py` reads the
        row, so presence is already covered there; what nothing else can see is
        WHICH step carries it.

        Step 2 is the boundary: it is the step that sends the builder to the one
        `cumulative` review, and its Sequencing paragraph already says to land
        everything BEFORE that run.

        What turns this red (each verified by relocating the real sentence):
        deleting it; MOVING it into the wait-time paragraph, which is prose read
        DURING the review and so too late to change the tree it grades; MOVING
        it into Step 3, which runs after the review has graded the tree. What it
        does NOT catch: a second copy parked elsewhere in the file — this
        asserts where the rule IS, not that it is stated once.
        """
        content = (FRAMEWORK_DIR / "skills" / "pr" / "SKILL.md").read_text()
        rule = "a mutation you did not watch go red applied nothing"
        assert rule in content, "the mutation sweep is gone from the PR flow"
        step2 = content.split("### Step 2: Cumulative-Critic gate", 1)
        assert len(step2) == 2, "the cumulative-Critic gate step is gone"
        step2 = step2[1].split("### Step 2b:", 1)[0]
        assert rule in step2, (
            "the mutation sweep left Step 2 — wherever it went, it no longer "
            "reaches the builder before the one boundary review runs"
        )
        wait = step2.split("While `/prawduct:critic cumulative` runs", 1)
        assert len(wait) == 2, "Step 2's wait-time paragraph is gone"
        assert rule in wait[0], (
            "the mutation sweep is inside the wait-time paragraph — that prose "
            "runs WHILE the review does, so the sweep would arrive too late to "
            "change the tree it grades"
        )

    def test_pr_skill_has_review_gate(self):
        """The /pr skill must enforce review before PR creation: hard gate
        language, on the coverage gate that is now the whole review gate."""
        content = _skill()
        assert "MANDATORY" in content
        assert "Do NOT proceed" in content or "DO NOT proceed" in content
        step2 = _step(content, "### Step 2:", "### Step 2b")
        assert "prawduct-hook check-cumulative-critic" in step2
        assert "Do NOT proceed until this gate passes" in step2

    def test_the_hygiene_step_runs_the_command_and_routes_every_exit(self):
        """Step 3 replaces the reviewer step. Each exit the command documents
        (Chunk 01: 0 nothing refuses, 1 something does, 3 could not answer) and
        each named result class has a route, so none is read under another's."""
        step3 = _step(_skill(), "### Step 3:", "### Step 4")
        assert "MANDATORY" in step3
        assert "prawduct-hook check-pr-hygiene" in step3
        for token in ("Exit 1", "Exit 3", "not a pass", "credential-shape",
                      "prawduct:allow prawduct/credential-shape --",
                      "closes-unresolved", "closes-still-open",
                      "close-owed-at-merge", "chunks-open", "review-tree-changed",
                      "unchecked"):
            assert token in step3, f"Step 3 no longer routes {token!r}"

    def test_the_hygiene_check_runs_on_a_doc_only_pr_too(self):
        """The doc-only fast path skips the coverage gate, not the hygiene
        check: a credential can sit in prose."""
        step1b = _step(_skill(), "### Step 1b:", "### Step 1c")
        assert "resume at Step 3" in step1b
        assert "Steps 2 and 2b" in step1b

    def test_the_description_is_drafted_to_a_file_and_checked_against_the_template(self):
        """The owner's constraint (2026-11-11): the PR honours the repo's PR
        template, by command. Order is the property — learn what to follow,
        draft to the file, check the file, create from the file, remove it."""
        step5 = _step(_skill(), "### Step 5:", "## Update Flow")
        path = ".prawduct/.pr-body.md"
        order = [
            step5.index("`prawduct-hook check-pr-body`"),
            step5.index(f"into `{path}`"),
            # Named by placeholder in this one span: a hook command's path
            # arguments must resolve in the tracked tree
            # (`test_path_reference_resolution`), and this file exists for one
            # step. Every other span names the literal.
            step5.index("prawduct-hook check-pr-body <body file>"),
            step5.index(f"gh pr create --title \"<title>\" --body-file {path}"),
            step5.index(f"git clean -fx -- {path}"),
        ]
        assert order == sorted(order), order
        assert "--template <path>" in step5
        assert "CONTRIBUTING" in step5
        # The path is a literal because skill shell state does not survive
        # between tool calls; a variable would read as working and be empty.
        assert "$" not in step5.split("**Create via", 1)[1].split("\n", 1)[0]

    def test_the_description_carries_what_the_flow_owes_it(self):
        step5 = _step(_skill(), "### Step 5:", "## Update Flow")
        for owed in ("`Closes #N`", "owed at merge", "close-owed-at-merge",
                     "chunks-open", "review-tree-changed", "Passed only on retry"):
            assert owed in step5, f"Step 5's description no longer carries {owed!r}"

    def test_the_update_flow_reruns_the_gates_and_the_template_check(self):
        update = _skill().split("## Update Flow", 1)[1].split("\n## ", 1)[0]
        assert "prawduct-hook check-cumulative-critic" in update
        assert "prawduct-hook check-pr-hygiene" in update
        assert "into `.prawduct/.pr-body.md`" in update
        assert "prawduct-hook check-pr-body <body file>" in update
        assert "gh pr edit <n> --body-file .prawduct/.pr-body.md" in update

    def test_step_4_catches_a_branch_that_moved_under_the_review(self):
        """Renegotiated with the reviewer's exit: the question survives, its
        answer moved. A commit landing after Step 2 passed (a hygiene fix, a
        change-record line) must not ship unreviewed; that used to be a delta
        check against the reviewer's `commit_reviewed`, and is now a re-run of
        the coverage gate, which composes over trees at HEAD. Pinned as the
        trigger (anything committed after Step 2) and the command, before the
        push."""
        step4 = _step(_skill(), "### Step 4:", "### Step 5")
        moved = step4[:step4.index("Push branch with `-u`")]
        assert "committed after Step 2 passed" in moved
        assert "prawduct-hook check-cumulative-critic" in moved
        assert "trees at HEAD" in moved

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
        develop-merge=release assumption.

        It also pinned that the step named `active_build_plan`, so retirement
        resolved the pointer rather than a hardcoded path. #1050 removed the
        pointer bookkeeping from the Merge Flow (a plan claims its branch, and
        a merged, deleted branch's claim resolves for nobody), so that anchor
        now pins the opposite: the Merge Flow says a `branch:`-declaring plan
        needs nothing at the merge, and names no pointer to maintain."""
        content = (FRAMEWORK_DIR / "skills" / "pr" / "SKILL.md").read_text()
        start = content.index("## Merge Flow")
        merge_flow = content[start:content.index("\n## ", start + 1)]
        # The discriminator is resolve-base, and BOTH branches must be present.
        assert "resolve-base" in merge_flow, "cleanup step must branch on resolve-base"
        assert "RETAIN" in merge_flow, "cleanup step must keep the plan while release-pending"
        # The release-pending branch must be tied to the develop base / statusless entry.
        assert "release-pending" in merge_flow
        assert "A plan declaring `branch:` needs nothing at this merge" in merge_flow, (
            "the Merge Flow must say a claiming plan needs no merge-time bookkeeping"
        )
        assert "active_build_plan" not in merge_flow, (
            "the Merge Flow must not prescribe pointer bookkeeping — a plan's "
            "claim, not the pointer, is what binds it (#1050)"
        )

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
        # The gap the guard cannot infer (origin/HEAD on `main`, integration on
        # `develop`) is closed by recording `base_branch:`, so the guard must
        # name that field. The field is the interface token; the sentence
        # around it is prose and is not pinned.
        assert "`base_branch:`" in guard, (
            "the guard must name the project-state field that closes the case "
            "it cannot infer"
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

class TestPushAndMergeChecks:
    """The push, transport and merge-head checks the Create, Update and Merge
    flows run — none of them about a reviewer, all of them surviving it."""

    @property
    def skill(self) -> str:
        return _skill()

    @property
    def push_step(self) -> str:
        return _step(self.skill, "### Step 4:", "### Step 5")

    def test_the_skill_appends_no_review_pr_event_and_holds_no_grant_for_one(self):
        """Contract inverted with the reviewer's exit: nothing writes a
        `review.pr` event now (`ledger-append` refuses the kind), so the skill
        neither instructs the append nor holds the grant for it."""
        assert "ledger-append" not in self.skill
        assert "ledger-append" not in _frontmatter()

    def test_create_step_5_pushes_with_upstream_and_verifies_the_pushed_ref(self):
        """Both halves, because the check depends on the flag.

        The verification is `check-branch-pushed`, which reads the branch's
        configured upstream — so a rewrite that drops `-u` leaves it answering
        `no-upstream` on the first push of a Create flow instead of certifying
        the push it just made. Asserting the check alone passed while that was
        true.
        """
        step5 = self.push_step
        # Scoped and literal: a bare `"-u" in content` passes on --json, on any
        # hyphen-u anywhere in the file, and on a step that pushes without it.
        assert "Push branch with `-u`" in step5, (
            "Step 5 must push with -u -- `check-branch-pushed` reads the "
            "branch's upstream, so without it the check answers no-upstream "
            "instead of certifying the push"
        )
        assert "prawduct-hook check-branch-pushed" in step5, (
            "Step 5 no longer runs the push-completeness gate -- a prose "
            "comparison an agent can skip is what #248 was filed against"
        )
        assert "AFTER the push" in step5, (
            "the ORDER is the whole check: run before the push it verifies, "
            "it certifies the previous one"
        )

    def test_merge_flow_verifies_the_prs_head_before_merging(self):
        """The merge-side check, pinned separately from the create-side one.

        These are not duplicates: the Create-flow check sits INSIDE the step
        whose skip causes the defect, so only this one is outside the control
        flow that produces the side effect. The skill no longer argues that to
        its editor (the defence was cut as maintainer prose, opus-55 slice-C
        C-16(c)); this test is where the argument now lives, and it pins the
        check itself.
        """
        content = self.skill
        merge_flow = content.split("## Merge Flow", 1)[1].split("## Status Flow", 1)[0]
        assert "headRefOid" in merge_flow, (
            "Merge Flow no longer verifies the PR head against local HEAD — "
            "an unpushed commit then merges silently."
        )

    def test_merge_flow_runs_the_push_gate_alongside_the_pr_head_check(self):
        """Two checks with two subjects, pinned together.

        `check-branch-pushed` computes its verdict and fails closed when it
        runs, but reads only this clone's refs; `headRefOid` sees a remote that
        moved but asks an agent to compare two strings. Whichever one a future
        editor calls redundant, half the defect comes back — so the file must
        carry both, and the reason. Neither is unskippable: both are sentences
        in one numbered step, and the gate's own omission is the one state it
        cannot detect.
        """
        merge_flow = self.skill.split("## Merge Flow", 1)[1].split("## Status Flow", 1)[0]
        assert "prawduct-hook check-branch-pushed <headRefName>" in merge_flow, (
            "Merge Flow must run the push gate ON THE PR'S BRANCH -- the "
            "argument-less form answers about whatever is checked out, so on a "
            "merge run from the base branch it reports the base is pushed and "
            "that reads as the PR being pushed"
        )
        assert "Neither check subsumes the other" in merge_flow, (
            "the reason the two merge-side checks are not duplicates is gone, "
            "which is what makes one of them look deletable"
        )

    def test_the_push_gate_is_granted_to_the_skill(self):
        """An ungranted command is a step that cannot run. The star must be
        ATTACHED: the gate takes an optional branch argument, and the Merge Flow
        passes one, which a bare grant would not cover
        (`tests/test_skill_command_grants.py` defines the form)."""
        frontmatter = self.skill.split("---", 2)[1]
        assert "Bash(prawduct-hook check-branch-pushed*)" in frontmatter, (
            "skills/pr/SKILL.md allowed-tools is missing check-branch-pushed* -- "
            "both flows call a gate the skill may not invoke, and the Merge Flow "
            "call passes the PR's branch"
        )

    def test_a_pushed_ref_mismatch_is_not_answered_with_force_push(self):
        """One remedy per shape. Force-pushing a remote-ahead branch discards
        what the remote holds, and rewriting your own commits opens a coverage
        gap — so the file must not answer every mismatch with "push again"."""
        step4 = self.push_step
        assert "never force-push" in step4
        # Scoped to the push step: the reason travels with the prohibition, or
        # it reads as mere preference.
        assert "coverage gap" in step4, (
            "the push step no longer says WHY a force-push is the wrong answer"
        )

    def test_create_step_5_syncs_the_evidence_notes_between_push_and_push_gate(self):
        """The notes ride the branch push (#1052): `evidence sync` runs after
        the push it travels with and before `check-branch-pushed`, which
        certifies the push and must stay the last word before `gh pr create`.
        Read in the order an agent reads Step 5, once each."""
        step5 = self.push_step
        assert step5.count("prawduct-hook evidence sync") == 1, step5
        push = step5.index("Push branch with `-u`")
        sync = step5.index("prawduct-hook evidence sync")
        gate = step5.index("prawduct-hook check-branch-pushed")
        assert push < sync < gate, (push, sync, gate)

    def test_a_failed_sync_is_reported_and_never_blocks_the_pr(self):
        """Coverage is the PR's gate; transport is not. Bound to the sentence
        that runs the sync, so a reword elsewhere cannot satisfy it."""
        step5 = self.push_step
        at = step5.index("prawduct-hook evidence sync")
        sentence = step5[at: step5.index("check-branch-pushed", at)]
        assert "never blocks the PR" in sentence
        assert "report" in sentence

    def test_the_update_flow_syncs_once_right_after_its_push(self):
        update = self.skill.split("## Update Flow", 1)[1].split("\n## ", 1)[0]
        assert update.count("prawduct-hook evidence sync") == 1, update
        first = update.split("\n2. ", 1)[0]
        assert first.index("Push new commits") < first.index("prawduct-hook evidence sync")
        assert "never blocks" in first

    def test_the_sync_is_granted_in_both_spellings(self):
        """The bare form a governed product runs, and this repo's
        `python3 plugin/bin/...` form — a self-hosted grant never stands alone
        (`tests/test_skill_command_grants.py`)."""
        frontmatter = self.skill.split("---", 2)[1]
        assert "Bash(prawduct-hook evidence sync*)" in frontmatter
        assert "Bash(python3 plugin/bin/prawduct-hook evidence sync*)" in frontmatter

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
        """cross-checks.md names final/cumulative as the OWNER of the final-mode
        cross-checks: the PR gate composes that review's coverage and runs no
        second copy of them.

        Asserted on the PROPERTY, ownership stated, rather than on a phrase
        carrying the count. The count moved the moment a third cross-check
        landed (the Records Pass), and a pin that breaks on arithmetic tests the
        sentence rather than the division it exists to protect.
        """
        content = (FRAMEWORK_DIR / "skills" / "critic" / "cross-checks.md").read_text()
        header = content.split("## Final-Mode Cross-Checks", 1)[1].split("\n### ", 1)[0]
        assert "`final`/`cumulative` owns" in header, (
            "cross-checks.md no longer names the cross-checks' owner"
        )


# =============================================================================
# Discoverability in the plugin guidance layer
# =============================================================================


class TestDiscoverability:
    def test_building_methodology_mentions_pr(self):
        """Building methodology sends the builder to the PR skill, and says what
        gates a PR there."""
        content = (FRAMEWORK_DIR / "methodology" / "building.md").read_text()
        section = content.split("## Creating Pull Requests", 1)[1].split("\n## ", 1)[0]
        assert "/prawduct:pr" in section
        assert "check-cumulative-critic" in section or "composed coverage" in section

    def test_framework_claude_mentions_pr(self):
        """The framework's contract should mention /pr. It lives in AGENTS.md;
        CLAUDE.md is the one line importing it."""
        content = (FRAMEWORK_DIR.parent / "AGENTS.md").read_text()
        assert "/pr" in content
