"""Tests for ``lib/critic_mode.py`` — Critic mode inference.

Each rule has at least one fixture exercising the win condition AND a
companion fixture confirming a precedence neighbor takes over when the
win condition fails. Uses real ``git init`` repos so the inference
helper sees real commit history, branches, and untracked files —
mock-git would diverge from production behavior on rev-parse, rev-list,
and porcelain status output (the three subprocess shapes the helper
relies on).

The module under test lives in ``lib/critic_mode.py`` (the plugin's
governance lib) and is re-exported as ``lib.infer_mode``; tests import
the package-level name to confirm the re-export works end-to-end.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib import buildplan_refs, critic_mode, infer_mode  # noqa: E402 — sys.path mutated above


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git_env(repo: Path) -> dict[str, str]:
    """Sterile env for git calls. HOME points OUTSIDE the repo so OS-level
    caches (macOS' ``$HOME/Library/Caches/com.apple.python/...``) don't get
    seeded inside the test repo and show up as untracked files when the
    helper later runs ``git status --untracked-files=all``."""
    return {
        "HOME": str(repo.parent / "_home"),
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
    }


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command in ``repo`` with a sterile environment."""
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=_git_env(repo),
        check=check,
        timeout=10,
    )


def _init_repo(repo: Path, *, branch: str = "main") -> None:
    """Initialize an empty repo with deterministic config."""
    _git(repo, "init", "--quiet", "-b", branch)
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")


def _commit(repo: Path, msg: str) -> str:
    """Stage everything and commit. Returns the new HEAD SHA."""
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", msg, "--quiet")
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _checkout_new_branch(repo: Path, name: str) -> None:
    _git(repo, "checkout", "-b", name, "--quiet")


def _write(repo: Path, rel: str, content: str) -> Path:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def _write_findings(
    prawduct: Path,
    *,
    mode: str = "chunk (lighter pass, not ready for push)",
    commit_reviewed: str | None = None,
    files_reviewed: list[str] | None = None,
    severity: str = "blocking",
    include_finding: bool = True,
    extends_cumulative: str | None = None,
) -> None:
    """Write a ``.critic-findings.json`` for inference rule fixtures.

    ``extends_cumulative`` is the v2-era CRT-4J8W chain-anchor SHA (wrapped
    in the persisted ``{"commit_reviewed": <sha>}`` dict form). No writer
    emits it since the kernel-v3 cutover; the parameter survives ONLY so
    stays-deleted guards can prove a record carrying it is ignored.
    """
    data: dict = {
        "files_reviewed": files_reviewed or ["src/app.py"],
        "findings": (
            [{"goal": "Nothing Is Broken", "severity": severity, "summary": "x"}]
            if include_finding
            else []
        ),
        "summary": "Prior review.",
        "mode": mode,
    }
    if commit_reviewed is not None:
        data["commit_reviewed"] = commit_reviewed
    if extends_cumulative is not None:
        data["extends_cumulative"] = {"commit_reviewed": extends_cumulative}
    prawduct.mkdir(parents=True, exist_ok=True)
    (prawduct / ".critic-findings.json").write_text(json.dumps(data))


def _write_build_plan(prawduct: Path, items: list[tuple[str, str]]) -> None:
    """Write ``artifacts/build-plan.md`` with Status section.

    ``items`` is a list of ``(state, title)`` where state is ``"x"`` (complete)
    or ``" "`` (open). Order is preserved.
    """
    lines = ["# Build Plan", "", "## Status", ""]
    lines.extend(f"- [{state}] {title}" for state, title in items)
    artifacts = prawduct / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "build-plan.md").write_text("\n".join(lines) + "\n")


def _write_build_plan_with_chunks(
    prawduct: Path,
    items: list[tuple[str, str]],
    chunk_modes: dict[str, str] | None = None,
) -> None:
    """Write ``artifacts/build-plan.md`` with a Status section AND per-chunk
    ``### Chunk NN: …`` detail sections.

    ``items`` is a list of ``(state, title)`` where ``title`` is the full
    Status line text (e.g. ``"Chunk 02: F3 — widget"``). ``chunk_modes`` maps a
    chunk id (e.g. ``"02"``) to the value written in that chunk's
    ``- **Critic mode:** <value>`` field. Chunks absent from the map get no
    ``Critic mode:`` field (the omit-and-infer common case).
    """
    chunk_modes = chunk_modes or {}
    lines = ["# Build Plan", "", "## Status", ""]
    lines.extend(f"- [{state}] {title}" for state, title in items)
    lines.append("")
    lines.append("## Chunks")
    lines.append("")
    for _state, title in items:
        lines.append(f"### {title}")
        lines.append("")
        lines.append("- **Type:** code")
        # Extract the chunk id from "Chunk NN: …".
        chunk_id = title[len("Chunk "):].split(":", 1)[0].strip()
        mode = chunk_modes.get(chunk_id)
        if mode is not None:
            lines.append(f"- **Critic mode:** {mode}")
        lines.append("- **Deliverables:** stuff")
        lines.append("")
    artifacts = prawduct / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "build-plan.md").write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Explicit-args override
# ---------------------------------------------------------------------------


class TestExplicitArgsOverride:
    """When ``$ARGUMENTS`` carries a recognized mode token, that wins
    outright — no git/state inspection happens."""

    @pytest.mark.parametrize(
        "args",
        ["chunk", "final", "cumulative", "verify-resolutions"],
    )
    def test_recognized_token_is_returned_verbatim(
        self, tmp_path: Path, args: str
    ):
        mode, rationale = infer_mode(tmp_path, args)
        assert mode == args
        assert rationale == "explicit-args"

    def test_token_with_trailing_whitespace_still_recognized(self, tmp_path: Path):
        mode, rationale = infer_mode(tmp_path, "  final  ")
        assert mode == "final"
        assert rationale == "explicit-args"

    def test_unrecognized_args_fall_through_to_inference(self, tmp_path: Path):
        """Unknown mode token triggers inference. No plan + no diff → rule-4
        final (the fail-safe path, not chunk — chunk-mode requires an
        active plan to scope against)."""
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")
        mode, rationale = infer_mode(tmp_path, "ultra-thorough")
        assert mode == "final"
        assert rationale.startswith("rule-4 final:")

    def test_none_args_triggers_inference(self, tmp_path: Path):
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")
        mode, _ = infer_mode(tmp_path, None)
        # No plan, no diff → rule-4 fail-safe → final
        assert mode == "final"

    def test_empty_string_args_triggers_inference(self, tmp_path: Path):
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")
        mode, _ = infer_mode(tmp_path, "")
        # No plan, no diff → rule-4 fail-safe → final
        assert mode == "final"


# ---------------------------------------------------------------------------
# Rule 1 — verify-resolutions
# ---------------------------------------------------------------------------


class TestRule1VerifyResolutions:
    """Verify-resolutions wins when prior findings + commit_reviewed
    anchor + actionable severity + uncommitted diff ⊆ prior scope.

    Each failure mode below confirms the rule does NOT fire when its
    win condition is missing — and the helper falls through to a lower-
    precedence rule.
    """

    def test_wins_when_diff_is_subset_of_prior_scope(self, tmp_path: Path):
        _init_repo(tmp_path)
        _write(tmp_path, "src/app.py", "# v1\n")
        prior_sha = _commit(tmp_path, "v1")

        # Builder modifies a file that was in prior files_reviewed — the
        # fix-in-progress signal.
        _write(tmp_path, "src/app.py", "# v2\n")

        _write_findings(
            tmp_path / ".prawduct",
            commit_reviewed=prior_sha,
            files_reviewed=["src/app.py", "src/other.py"],
            severity="blocking",
        )

        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "verify-resolutions"
        assert rationale.startswith("rule-1 verify-resolutions:")

    def test_does_not_fire_when_diff_extends_beyond_prior_scope(
        self, tmp_path: Path
    ):
        """Builder added a new file alongside the fix → not a verify case."""
        _init_repo(tmp_path)
        _write(tmp_path, "src/app.py", "# v1\n")
        prior_sha = _commit(tmp_path, "v1")

        _write(tmp_path, "src/app.py", "# v2\n")
        _write(tmp_path, "src/unrelated.py", "# new chunk work\n")

        _write_findings(
            tmp_path / ".prawduct",
            commit_reviewed=prior_sha,
            files_reviewed=["src/app.py"],
            severity="blocking",
        )

        mode, _ = infer_mode(tmp_path, None)
        assert mode != "verify-resolutions"

    def test_does_not_fire_when_diff_is_empty(self, tmp_path: Path):
        """No uncommitted work means there's nothing to verify — the
        rule needs an active fix-in-progress signal."""
        _init_repo(tmp_path)
        _write(tmp_path, "src/app.py", "# v1\n")
        prior_sha = _commit(tmp_path, "v1")

        _write_findings(
            tmp_path / ".prawduct",
            commit_reviewed=prior_sha,
            files_reviewed=["src/app.py"],
        )

        mode, _ = infer_mode(tmp_path, None)
        assert mode != "verify-resolutions"

    def test_does_not_fire_when_no_actionable_findings(self, tmp_path: Path):
        """NOTE-only prior findings have nothing to verify."""
        _init_repo(tmp_path)
        _write(tmp_path, "src/app.py", "# v1\n")
        prior_sha = _commit(tmp_path, "v1")
        _write(tmp_path, "src/app.py", "# v2\n")

        _write_findings(
            tmp_path / ".prawduct",
            commit_reviewed=prior_sha,
            files_reviewed=["src/app.py"],
            severity="note",
        )

        mode, _ = infer_mode(tmp_path, None)
        assert mode != "verify-resolutions"

    def test_does_not_fire_when_commit_reviewed_unresolvable(self, tmp_path: Path):
        """SHA from a rebased/rewritten branch demotes the rule."""
        _init_repo(tmp_path)
        _write(tmp_path, "src/app.py", "# v1\n")
        _commit(tmp_path, "v1")
        _write(tmp_path, "src/app.py", "# v2\n")

        _write_findings(
            tmp_path / ".prawduct",
            commit_reviewed="deadbeef" * 5,  # not in history
            files_reviewed=["src/app.py"],
        )

        mode, _ = infer_mode(tmp_path, None)
        assert mode != "verify-resolutions"

    def test_does_not_fire_when_commit_reviewed_absent(self, tmp_path: Path):
        """Pre-v1.5 findings (no commit_reviewed key) can't anchor."""
        _init_repo(tmp_path)
        _write(tmp_path, "src/app.py", "# v1\n")
        _commit(tmp_path, "v1")
        _write(tmp_path, "src/app.py", "# v2\n")

        _write_findings(
            tmp_path / ".prawduct",
            commit_reviewed=None,
            files_reviewed=["src/app.py"],
        )

        mode, _ = infer_mode(tmp_path, None)
        assert mode != "verify-resolutions"

    def test_does_not_fire_when_anchor_is_non_ancestor(self, tmp_path: Path):
        """A sibling branch's anchor RESOLVES but is not on this lineage.

        The single-slot findings cache survives a branch switch, and worktrees of
        one clone share an object store — so the old guard (`_commit_resolves`)
        passed a sibling tip and the pass diffed across the divergence, reviewing
        changes this branch never made. The assertions below prove the OLD guard
        would have passed before asserting the demote: without that pair the test
        would stay green against a build that dropped the ancestor check.
        """
        _init_repo(tmp_path)
        _write(tmp_path, "src/app.py", "# base\n")
        _commit(tmp_path, "base")

        _checkout_new_branch(tmp_path, "feature/sibling")
        _write(tmp_path, "src/app.py", "# sibling work\n")
        sibling_tip = _commit(tmp_path, "sibling")

        _git(tmp_path, "checkout", "main", "--quiet")
        _checkout_new_branch(tmp_path, "feature/mine")
        _write(tmp_path, "src/app.py", "# my v1\n")
        _commit(tmp_path, "mine")
        _write(tmp_path, "src/app.py", "# my v2 (fix in progress)\n")

        _write_findings(
            tmp_path / ".prawduct",
            commit_reviewed=sibling_tip,
            files_reviewed=["src/app.py"],
        )

        assert critic_mode._commit_resolves(tmp_path, sibling_tip) is True, (
            "the old guard passes this anchor — that is the defect"
        )
        assert critic_mode._commit_is_ancestor(tmp_path, sibling_tip) is False

        mode, _ = infer_mode(tmp_path, None)
        assert mode != "verify-resolutions"

    def test_rule_1b_does_not_fire_when_anchor_is_non_ancestor(self, tmp_path: Path):
        """Rule 1b takes `<anchor>..HEAD` too, so it needs the same guard.

        Rule 1's test proves the guard exists; it does not prove this call site
        has it. `_committed_files_since` below the check is exactly the two-way
        diff that spans a divergence, so an unguarded 1b recommends a verify pass
        over a sibling branch's commits.
        """
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")

        _checkout_new_branch(tmp_path, "feature/sibling")
        _write(tmp_path, "src/sib.py", "# sibling\n")
        sibling_tip = _commit(tmp_path, "sibling work")

        _git(tmp_path, "checkout", "main", "--quiet")
        _checkout_new_branch(tmp_path, "feature/mine")
        _write(tmp_path, "src/a.py", "# a\n")
        _commit(tmp_path, "feat: a")
        _write(tmp_path, "src/a.py", "# a fixed\n")
        _commit(tmp_path, "fix: post-cumulative")  # clean tree, committed delta

        _write_findings(
            tmp_path / ".prawduct",
            mode="cumulative (bundle review, ready for merge)",
            commit_reviewed=sibling_tip,
            files_reviewed=["src/a.py"],
            include_finding=False,
        )

        assert critic_mode._commit_resolves(tmp_path, sibling_tip) is True, (
            "the old guard passes this anchor — that is the defect"
        )
        assert critic_mode._commit_is_ancestor(tmp_path, sibling_tip) is False

        mode, _ = infer_mode(tmp_path, None)
        assert mode != "verify-resolutions"

    def test_ancestor_check_fails_closed_on_git_failure(self, tmp_path: Path):
        """Not-an-ancestor and a broken git are the same answer: refuse.

        An anchor we cannot PLACE is one we cannot trust, so exit 1 and every
        other failure demote alike. A malformed SHA exercises the non-zero,
        non-1 path without mocking the subprocess away.
        """
        _init_repo(tmp_path)
        _write(tmp_path, "src/app.py", "# v1\n")
        _commit(tmp_path, "v1")

        assert critic_mode._commit_is_ancestor(tmp_path, "not-a-sha") is False
        assert critic_mode._commit_is_ancestor(tmp_path, "") is False


# ---------------------------------------------------------------------------
# Rule 2 — cumulative
# ---------------------------------------------------------------------------


class TestRule1bPostCumulativeFix:
    """Rule 1b (CRT-4J8W): a committed non-doc delta after a ``cumulative``
    review infers ``verify-resolutions`` — the delta-cost pass — instead of
    falling through to rule 2's full bundle re-review. The v2 multi-link
    chain arm (a verify record propagating an ``extends_cumulative``
    anchor) died in the kernel-v3 chunk-06 vestige sweep; its stays-deleted
    guard lives here.
    """

    def _reviewed_branch_repo(self, repo: Path) -> str:
        """main + feature branch ≥2 ahead; returns the cumulative-anchor SHA
        (HEAD at "review time"), BEFORE the post-review fix is committed."""
        _init_repo(repo)
        _write(repo, "README.md", "x\n")
        _commit(repo, "initial")
        _checkout_new_branch(repo, "feature/work")
        _write(repo, "src/a.py", "# a\n")
        _commit(repo, "feat: a")
        _write(repo, "src/b.py", "# b\n")
        return _commit(repo, "feat: b")

    def test_fires_for_committed_fix_after_clean_cumulative(self, tmp_path: Path):
        reviewed = self._reviewed_branch_repo(tmp_path)
        _write_findings(
            tmp_path / ".prawduct",
            mode="cumulative (bundle review, ready for merge)",
            commit_reviewed=reviewed,
            files_reviewed=["src/a.py", "src/b.py"],
            include_finding=False,  # clean cumulative
        )
        _write(tmp_path, "src/a.py", "# a fixed\n")
        _commit(tmp_path, "fix: post-cumulative")

        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "verify-resolutions"
        assert rationale.startswith("rule-1b verify-resolutions (post-cumulative fix):")

    def test_takes_precedence_over_rule_2_cumulative(self, tmp_path: Path):
        # Same state satisfies rule 2's win condition (clean tree, ≥2 ahead,
        # no cumulative record at HEAD) — 1b must win or the no-args flow
        # re-pays a full bundle review for every post-cumulative fix.
        reviewed = self._reviewed_branch_repo(tmp_path)
        _write_findings(
            tmp_path / ".prawduct",
            mode="cumulative (bundle review, ready for merge)",
            commit_reviewed=reviewed,
            files_reviewed=["src/a.py", "src/b.py"],
            severity="warning",
        )
        _write(tmp_path, "src/a.py", "# a fixed\n")
        _commit(tmp_path, "fix: post-cumulative")

        mode, _ = infer_mode(tmp_path, None)
        assert mode == "verify-resolutions"

    def test_v2_chain_record_prior_no_longer_extends(self, tmp_path: Path):
        # Stays-deleted guard (kernel-v3 ch.06 vestige sweep): a v2-era
        # multi-link chain record — verify-resolutions carrying an
        # ``extends_cumulative`` anchor — must NOT extend rule 1b. Nothing
        # writes the field anymore, so a record carrying it is v2 state;
        # inference falls through to rule 2's bundle recommendation.
        anchor = self._reviewed_branch_repo(tmp_path)
        _write(tmp_path, "src/a.py", "# a fixed\n")
        verify_head = _commit(tmp_path, "fix: round 1")
        _write_findings(
            tmp_path / ".prawduct",
            mode="verify-resolutions (delta review, prior findings only)",
            commit_reviewed=verify_head,
            files_reviewed=["src/a.py", "src/b.py"],
            include_finding=False,
            extends_cumulative=anchor,
        )
        _write(tmp_path, "src/b.py", "# b fixed\n")
        _commit(tmp_path, "fix: round 2")

        mode, rationale = infer_mode(tmp_path, None)
        assert not rationale.startswith("rule-1b"), rationale
        assert mode == "cumulative"

    def test_does_not_fire_for_non_cumulative_prior(self, tmp_path: Path):
        # A chunk-mode prior is not a cumulative → rule 2 takes over.
        reviewed = self._reviewed_branch_repo(tmp_path)
        _write_findings(
            tmp_path / ".prawduct",
            commit_reviewed=reviewed,  # default mode: chunk
            files_reviewed=["src/a.py", "src/b.py"],
            include_finding=False,
        )
        _write(tmp_path, "src/a.py", "# a fixed\n")
        _commit(tmp_path, "fix: post-chunk-review")

        mode, _ = infer_mode(tmp_path, None)
        assert mode == "cumulative"

    def test_does_not_fire_for_doc_only_delta(self, tmp_path: Path):
        # All-.md delta: the existing record already covers HEAD under the
        # gate's doc-only allowance — no review to recommend from 1b.
        reviewed = self._reviewed_branch_repo(tmp_path)
        _write_findings(
            tmp_path / ".prawduct",
            mode="cumulative (bundle review, ready for merge)",
            commit_reviewed=reviewed,
            files_reviewed=["src/a.py", "src/b.py"],
            include_finding=False,
        )
        _write(tmp_path, "docs.md", "# d\n")
        _commit(tmp_path, "docs: after review")

        mode, rationale = infer_mode(tmp_path, None)
        assert not rationale.startswith("rule-1b"), rationale

    def test_does_not_fire_when_delta_widens_past_threshold(self, tmp_path: Path):
        # prior surface 1 file → threshold 2*1+5 = 7; 8 changed files would
        # demote inside the verify pass, so 1b must not recommend it.
        reviewed = self._reviewed_branch_repo(tmp_path)
        _write_findings(
            tmp_path / ".prawduct",
            mode="cumulative (bundle review, ready for merge)",
            commit_reviewed=reviewed,
            files_reviewed=["src/a.py"],
            include_finding=False,
        )
        for i in range(8):
            _write(tmp_path, f"src/new{i}.py", f"# {i}\n")
        _commit(tmp_path, "feat: wide new work")

        mode, _ = infer_mode(tmp_path, None)
        assert mode == "cumulative"


class TestRule2Cumulative:
    """Cumulative wins when working tree is clean AND branch is ≥2
    commits ahead of base AND no fresh cumulative-mode findings record
    exists for current HEAD.

    Deviation from build-plan spec: the clean-tree guard is added on
    top of the literal "branch ≥2 ahead + no cumulative record" rule
    (see module docstring for rationale). The fixtures here verify the
    guard works — mid-build-plan with uncommitted work falls through
    to chunk mode rather than triggering a 4-10 min cumulative review
    on every commit.
    """

    def test_wins_when_branch_ahead_clean_no_record(self, tmp_path: Path):
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")
        _checkout_new_branch(tmp_path, "feature/work")

        _write(tmp_path, "src/a.py", "# a\n")
        _commit(tmp_path, "feat: a")
        _write(tmp_path, "src/b.py", "# b\n")
        _commit(tmp_path, "feat: b")

        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "cumulative"
        assert rationale.startswith("rule-2 cumulative:")

    def test_does_not_fire_when_working_tree_dirty(self, tmp_path: Path):
        """Mid-chunk uncommitted work → cumulative blocked by the
        clean-tree guard (keeps it from over-firing on every mid-build
        review). The fall-through mode depends on plan state."""
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")
        _checkout_new_branch(tmp_path, "feature/work")

        _write(tmp_path, "src/a.py", "# a\n")
        _commit(tmp_path, "feat: a")
        _write(tmp_path, "src/b.py", "# b\n")
        _commit(tmp_path, "feat: b")

        # Mid-chunk-3 uncommitted work
        _write(tmp_path, "src/c.py", "# c in progress\n")

        mode, _ = infer_mode(tmp_path, None)
        assert mode != "cumulative"

    def test_does_not_fire_when_only_one_commit_ahead(self, tmp_path: Path):
        """Rule 2's own ≥2-commit threshold holds — the rule does not fire.

        The ANSWER is still `cumulative`, from rule 4: the tree is clean, so
        chunk/final would dispatch an empty interval and refuse, and one commit
        ahead of a resolvable base is a reviewable bundle. This assertion used to
        read `mode != "cumulative"`, conflating "rule 2 declined" with "the
        answer isn't cumulative" — the same statement until rule 4 learned that a
        clean tree cannot be reviewed by a working-tree-scoped mode, and a
        standalone fix branch with all work committed is exactly the case that
        cost a wasted dispatch. It pins the rule now, which is what it meant.
        """
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")
        _checkout_new_branch(tmp_path, "feature/work")
        _write(tmp_path, "src/a.py", "# a\n")
        _commit(tmp_path, "feat: a")  # only 1 ahead

        mode, rationale = infer_mode(tmp_path, None)
        assert not rationale.startswith("rule-2"), rationale
        assert mode == "cumulative"
        assert rationale.startswith("rule-4 cumulative:")

    def test_does_not_fire_when_cumulative_record_covers_head(self, tmp_path: Path):
        """A fresh cumulative-mode findings file for current HEAD
        means cumulative was already run — no need to re-fire."""
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")
        _checkout_new_branch(tmp_path, "feature/work")
        _write(tmp_path, "src/a.py", "# a\n")
        _commit(tmp_path, "feat: a")
        _write(tmp_path, "src/b.py", "# b\n")
        head_sha = _commit(tmp_path, "feat: b")

        _write_findings(
            tmp_path / ".prawduct",
            mode="cumulative (bundle review, ready for merge)",
            commit_reviewed=head_sha,
            files_reviewed=["src/a.py", "src/b.py"],
            include_finding=False,  # clean review
        )

        mode, _ = infer_mode(tmp_path, None)
        assert mode != "cumulative"
        # No active plan + no uncommitted code → rule-4 fail-safe → final
        assert mode == "final"

    def test_v2_chain_record_at_head_no_longer_suppresses(self, tmp_path: Path):
        """Stays-deleted guard (kernel-v3 ch.06 vestige sweep): a v2-era
        chain record (verify-resolutions + ``extends_cumulative``) at HEAD
        no longer suppresses rule 2 — only a ``cumulative`` record at HEAD
        does. Under v3 the gates answer from composed facts regardless of
        what this rule recommends, so trusting an unwritten v2 cache field
        would only steer the builder wrong."""
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")
        _checkout_new_branch(tmp_path, "feature/work")
        _write(tmp_path, "src/a.py", "# a\n")
        anchor = _commit(tmp_path, "feat: a")
        _write(tmp_path, "src/b.py", "# b\n")
        head_sha = _commit(tmp_path, "fix: b")

        _write_findings(
            tmp_path / ".prawduct",
            mode="verify-resolutions (delta review, prior findings only)",
            commit_reviewed=head_sha,
            files_reviewed=["src/a.py", "src/b.py"],
            include_finding=False,
            extends_cumulative=anchor,
        )

        mode, _ = infer_mode(tmp_path, None)
        assert mode == "cumulative"

    def test_does_not_fire_without_main_master_or_develop(self, tmp_path: Path):
        """Rule 2 declines on a branch with no conventional base branch.

        Not because the base is unresolvable — `_resolve_base_branch` falls back
        to `HEAD~1`, so it resolves here and this test's original name and
        docstring both asserted a mechanism that has not held. It declines
        because `HEAD~1..HEAD` is one commit, under rule 2's ≥2 threshold. The
        answer is rule 4's clean-tree redirect, and pinning the *rationale* is
        what keeps the reason from silently becoming a different one again.
        """
        _init_repo(tmp_path, branch="feature/standalone")
        _write(tmp_path, "src/a.py", "# a\n")
        _commit(tmp_path, "a")
        _write(tmp_path, "src/b.py", "# b\n")
        _commit(tmp_path, "b")

        mode, rationale = infer_mode(tmp_path, None)
        assert not rationale.startswith("rule-2"), rationale
        assert mode == "cumulative"
        assert rationale.startswith("rule-4 cumulative:")


# ---------------------------------------------------------------------------
# Rule 3 — final
# ---------------------------------------------------------------------------


class TestRule3Final:
    """Final wins for end-of-plan (N-1 chunks [x] + current uncommitted)
    OR non-chunked medium+ work (no plan + ≥5 changed files)."""

    def test_wins_when_last_unchecked_chunk_in_progress(self, tmp_path: Path):
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")

        _write_build_plan(
            tmp_path / ".prawduct",
            [
                ("x", "Chunk 1"),
                ("x", "Chunk 2"),
                ("x", "Chunk 3"),
                (" ", "Chunk 4"),
            ],
        )

        # Last chunk in progress — uncommitted code
        _write(tmp_path, "src/final.py", "# last chunk work\n")

        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "final"
        assert rationale.startswith("rule-3 final:")
        assert "last unchecked chunk" in rationale

    def test_does_not_fire_when_multiple_chunks_unchecked(self, tmp_path: Path):
        """Mid-build-plan (>1 unchecked) → chunk wins."""
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")

        _write_build_plan(
            tmp_path / ".prawduct",
            [
                ("x", "Chunk 1"),
                (" ", "Chunk 2"),
                (" ", "Chunk 3"),
                (" ", "Chunk 4"),
            ],
        )
        _write(tmp_path, "src/c.py", "# c in progress\n")

        mode, _ = infer_mode(tmp_path, None)
        assert mode == "chunk"

    def test_does_not_fire_when_last_chunk_has_no_uncommitted_work(
        self, tmp_path: Path
    ):
        """N-1 done but current chunk hasn't started → chunk (mid-plan)."""
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")
        _write_build_plan(
            tmp_path / ".prawduct",
            [
                ("x", "Chunk 1"),
                ("x", "Chunk 2"),
                (" ", "Chunk 3"),
            ],
        )

        mode, _ = infer_mode(tmp_path, None)
        assert mode == "chunk"

    def test_wins_for_no_plan_medium_plus_work(self, tmp_path: Path):
        """No build plan + ≥5 changed files = medium+ work → final."""
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")

        for i in range(5):
            _write(tmp_path, f"src/file_{i}.py", f"# file {i}\n")

        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "final"
        assert "no build plan" in rationale

    def test_no_plan_small_work_falls_through_to_final(self, tmp_path: Path):
        """No plan + <5 files → rule-4 fail-safe → final. (Not chunk: chunk
        mode requires an active plan to scope against; without one, the
        SKILL's historical "missing/unrecognized → final" norm wins.)"""
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")

        for i in range(3):
            _write(tmp_path, f"src/file_{i}.py", f"# file {i}\n")

        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "final"
        assert rationale.startswith("rule-4 final:")

    def test_reads_scope_named_plan_via_active_build_plan_pointer(self, tmp_path: Path):
        """v1.6.0 Chunk 06: with `active_build_plan:` set and no build-plan.md,
        inference reads the scope-named plan's chunk count. The N-1-done +
        uncommitted scenario fires rule-3 ("last unchecked chunk"); without the
        pointer, the absent plan would instead fall through to rule-4."""
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")

        prawduct = tmp_path / ".prawduct"
        (prawduct / "artifacts").mkdir(parents=True, exist_ok=True)
        (prawduct / "project-state.yaml").write_text(
            "active_build_plan: artifacts/v1.6.0-foo-plan.md\n"
        )
        (prawduct / "artifacts" / "v1.6.0-foo-plan.md").write_text(
            "# Build Plan\n\n## Status\n\n"
            "- [x] Chunk 1\n- [x] Chunk 2\n- [x] Chunk 3\n- [ ] Chunk 4\n"
        )
        # No build-plan.md exists — only the pointed-to scope-named plan.
        assert not (prawduct / "artifacts" / "build-plan.md").exists()

        _write(tmp_path, "src/final.py", "# last chunk work\n")

        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "final"
        assert "last unchecked chunk" in rationale


# ---------------------------------------------------------------------------
# Rule 4 — chunk (default)
# ---------------------------------------------------------------------------


class TestRule4ChunkDefault:
    """Chunk fires when nothing else does — the catch-all for
    mid-build-plan reviews."""

    def test_mid_plan_with_prior_chunks_committed(self, tmp_path: Path):
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")

        _write_build_plan(
            tmp_path / ".prawduct",
            [
                ("x", "Chunk 1"),
                (" ", "Chunk 2"),
                (" ", "Chunk 3"),
            ],
        )
        # Mid-chunk-2 uncommitted work
        _write(tmp_path, "src/chunk2.py", "# work\n")

        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "chunk"
        assert rationale.startswith("rule-4 chunk:")

    def test_clean_tree_does_not_recommend_an_empty_working_tree_interval(
        self, tmp_path: Path
    ):
        """A plan grounds `chunk`, but a clean tree cannot BE chunk-reviewed.

        `chunk` and `final` both scope to HEAD-tree → working-tree, so on a clean
        tree `critic-begin` refuses with an empty diff. Recommending one anyway
        is a round-trip that names no remedy the caller lacked — the observed
        case was a standalone fix branch with all work committed, which the
        skill then re-dispatched as `cumulative` by hand.
        """
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _write_build_plan(
            tmp_path / ".prawduct",
            [("x", "Chunk 1"), (" ", "Chunk 2"), (" ", "Chunk 3")],
        )
        _commit(tmp_path, "initial")
        _checkout_new_branch(tmp_path, "fix/standalone")
        _write(tmp_path, "src/fix.py", "# fix\n")
        # EVERYTHING committed, records included. An uncommitted plan or
        # change-log would leave the interval non-empty — `capture_tree` stages
        # them — so a fixture that left them dirty would be exercising the
        # metadata blind spot rather than the clean-tree case.
        _commit(tmp_path, "fix: it")

        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "cumulative"
        assert "empty interval" in rationale

    def test_uncommitted_records_alone_still_have_something_to_review(
        self, tmp_path: Path
    ):
        """A record-only work cycle is not a clean tree.

        Uncommitted plan and change-log edits ARE in `chunk`'s interval, so
        redirecting them to `cumulative` would note-and-exclude the records just
        written and stamp "working tree is clean" into `mode_chosen_by` — a
        durable field of the review fact — over a dirty tree.
        """
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _write_build_plan(
            tmp_path / ".prawduct",
            [("x", "Chunk 1"), (" ", "Chunk 2"), (" ", "Chunk 3")],
        )
        _commit(tmp_path, "initial")
        _checkout_new_branch(tmp_path, "fix/records")
        _write(tmp_path, "src/fix.py", "# fix\n")
        _commit(tmp_path, "fix: it")
        # Code committed; only the records are in flight.
        _write(tmp_path, ".prawduct/change-log.md", "# Change Log\n\n## New entry\n")

        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "chunk", rationale
        assert "empty interval" not in rationale

    def test_no_redirect_when_cumulative_would_refuse_too(self, tmp_path: Path):
        """The redirect only fires when the redirect TARGET works.

        Zero commits beyond the base means cumulative's interval is empty as
        well, so swapping one refusal for another buys nothing — the fail-safe
        answer and its honest refusal stand.

        A GUARD, not evidence: it passes against the pre-fix code too, by
        design. What it pins is that the redirect beside it stays bounded.
        """
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")
        _write_build_plan(
            tmp_path / ".prawduct",
            [("x", "Chunk 1"), (" ", "Chunk 2"), (" ", "Chunk 3")],
        )

        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "chunk"
        assert rationale.startswith("rule-4 chunk:")

    def test_working_tree_probe_fails_toward_not_empty(
        self, tmp_path: Path, monkeypatch
    ):
        """The probe's docstring promises "any git failure returns False".

        The raise class is the half a `returncode` check misses: an absent
        binary (OSError) or the timeout. Returning False there keeps rule 4 on
        its fail-safe answer instead of redirecting on a tree it could not read
        — an unguarded call would propagate out of `infer_mode` instead.

        Lives here rather than beside the rule-1 anchor tests because rule 4 is
        the only caller, and uses `monkeypatch` rather than a hand-rolled
        reassignment so the stdlib module object is restored by the fixture
        rather than by this test remembering to.
        """
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")
        # Unpatched first: proves the call is REACHED, so the False below is the
        # guard answering and not a short circuit above it.
        assert critic_mode._working_tree_is_empty(tmp_path) is True

        for boom in (OSError("no git"), subprocess.TimeoutExpired("git", 10)):
            def _raise(*_a, _exc=boom, **_k):
                raise _exc

            monkeypatch.setattr(critic_mode.subprocess, "run", _raise)
            assert critic_mode._working_tree_is_empty(tmp_path) is False
            monkeypatch.undo()

    def test_grounds_on_the_branchs_own_plan_not_the_pointer(self, tmp_path: Path):
        """Rule 4 names the plan it grounded on, and prefers this branch's.

        `active_build_plan` answers "which plan is in progress in this repo" —
        on a repo running several plans across worktrees that is a different
        question, and rule 4 used to inherit whichever plan it named. The
        pointer's plan here has one chunk left (which would make rule 3 fire);
        the branch's plan has three, so an inference reading the pointer answers
        `final` and one reading the branch answers `chunk`.
        """
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")
        _checkout_new_branch(tmp_path, "feature/mine")

        artifacts = tmp_path / ".prawduct" / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        (artifacts / "build-plan-other.md").write_text(
            "---\nartifact: build-plan\nscope: other\n---\n\n"
            "# Build Plan\n\n## Status\n\n- [x] Chunk 01: done\n- [ ] Chunk 02: last\n"
        )
        (artifacts / "build-plan-mine.md").write_text(
            "---\nartifact: build-plan\nscope: mine\n---\n\n"
            "# Build Plan\n\n## Status\n\n"
            "- [x] Chunk 01: done\n- [ ] Chunk 02: current\n- [ ] Chunk 03: later\n"
        )
        (tmp_path / ".prawduct" / "project-state.yaml").write_text(
            "active_build_plan: artifacts/build-plan-other.md\n"
        )
        _write(tmp_path, "src/work.py", "# in progress\n")

        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "chunk", rationale
        assert "build-plan-mine.md" in rationale
        assert "declares this branch's scope 'mine'" in rationale

    def test_a_branch_named_after_a_finished_plan_does_not_match(self, tmp_path: Path):
        """The liveness narrowing: a matched plan must still have work in it.

        A long-lived repo accumulates dozens of released plans, all of them
        scope-declaring. Without this, a branch named after any of them
        attributes its review to a plan that shipped long ago — and record-lint
        would then raise a BLOCKING `chunk-ref-missing` about deliverables that
        shipped with it. Deleting `_has_unfinished_chunk` must not leave a green
        suite, which is why the fully-ticked plan here is otherwise identical to
        the one the sibling test matches on.
        """
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")
        _checkout_new_branch(tmp_path, "fix/shipped")

        artifacts = tmp_path / ".prawduct" / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        (artifacts / "build-plan-shipped.md").write_text(
            "---\nartifact: build-plan\nscope: shipped\n---\n\n"
            "# Plan\n\n## Status\n\n- [x] Chunk 01: done\n- [x] Chunk 02: also done\n"
        )
        (artifacts / "build-plan-live.md").write_text(
            "---\nartifact: build-plan\nscope: live\n---\n\n"
            "# Plan\n\n## Status\n\n- [x] Chunk 01: done\n- [ ] Chunk 02: current\n"
        )

        prawduct = tmp_path / ".prawduct"
        assert buildplan_refs.infer_scope_from_branch(tmp_path, prawduct) is None, (
            "a released plan is not what this branch is building"
        )

        # Control: the identical branch shape DOES match a plan with work left,
        # so the assertion above is about liveness and not about the fixture.
        _git(tmp_path, "checkout", "-b", "fix/live", "--quiet")
        assert buildplan_refs.infer_scope_from_branch(tmp_path, prawduct) == "live"

    def test_a_declared_branch_resolves_a_scope_no_name_rule_could(self, tmp_path: Path):
        """The observed miss this closes, in its real shape.

        `feat/tactical-efficiency-pass` matches the scope `tactical-efficiency`
        under neither candidate rule (whole name, last segment), so every
        dispatch from such a branch resolved NO scope — the ledger row said
        `(none)` and every scope-filtered consumer stayed inert. The plan's own
        `branch:` declaration is a statement, not a guess, so it answers.
        """
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")
        _checkout_new_branch(tmp_path, "feat/tactical-efficiency-pass")

        artifacts = tmp_path / ".prawduct" / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        (artifacts / "build-plan-te.md").write_text(
            "---\nartifact: build-plan\nscope: tactical-efficiency\n"
            "branch: feat/tactical-efficiency-pass\n---\n\n"
            "# Plan\n\n## Status\n\n- [ ] Chunk 01: current\n"
        )
        prawduct = tmp_path / ".prawduct"
        assert buildplan_refs.infer_scope_from_branch(tmp_path, prawduct) == (
            "tactical-efficiency"
        )

        # The paired negative: strip the declaration and the name rules are back
        # in charge, which is exactly what could not resolve this branch.
        (artifacts / "build-plan-te.md").write_text(
            "---\nartifact: build-plan\nscope: tactical-efficiency\n---\n\n"
            "# Plan\n\n## Status\n\n- [ ] Chunk 01: current\n"
        )
        assert buildplan_refs.infer_scope_from_branch(tmp_path, prawduct) is None

    def test_a_declared_branch_beats_a_name_match_on_another_plan(self, tmp_path: Path):
        """Precedence, where the two routes disagree — otherwise the ordering is
        untested and either arrangement passes."""
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")
        _checkout_new_branch(tmp_path, "fix/guessable")

        artifacts = tmp_path / ".prawduct" / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        (artifacts / "build-plan-guessable.md").write_text(
            "---\nartifact: build-plan\nscope: guessable\n---\n\n"
            "# Plan\n\n## Status\n\n- [ ] Chunk 01: current\n"
        )
        (artifacts / "build-plan-declared.md").write_text(
            "---\nartifact: build-plan\nscope: declared\nbranch: fix/guessable\n---\n\n"
            "# Plan\n\n## Status\n\n- [ ] Chunk 01: current\n"
        )
        prawduct = tmp_path / ".prawduct"
        assert buildplan_refs.infer_scope_from_branch(tmp_path, prawduct) == "declared"

    def test_a_finished_declared_plan_still_claims_its_branch(self, tmp_path: Path):
        """The liveness narrowing does NOT apply to a declaration.

        It exists to keep a *guess* from attributing work to a plan that shipped
        long ago. A plan that names this branch is not guessing, and the window
        the narrowing opens — every box ticked, branch not yet merged — is
        exactly when the `cumulative` review and the last gate run happen.
        """
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")
        _checkout_new_branch(tmp_path, "feat/all-done")

        artifacts = tmp_path / ".prawduct" / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        (artifacts / "build-plan-done.md").write_text(
            "---\nartifact: build-plan\nscope: done\nbranch: feat/all-done\n---\n\n"
            "# Plan\n\n## Status\n\n- [x] Chunk 01: done\n- [x] Chunk 02: done\n"
        )
        prawduct = tmp_path / ".prawduct"
        assert buildplan_refs.infer_scope_from_branch(tmp_path, prawduct) == "done"

    def test_two_plans_claiming_one_branch_infer_no_scope(self, tmp_path: Path):
        """Advice declines rather than picking; the resolver is where the refusal
        is raised, and a scope inference that failed closed would block advice on
        a condition authority already blocks on."""
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")
        _checkout_new_branch(tmp_path, "feat/contested")

        artifacts = tmp_path / ".prawduct" / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        for name in ("a", "b"):
            (artifacts / f"build-plan-{name}.md").write_text(
                f"---\nartifact: build-plan\nscope: {name}\nbranch: feat/contested\n---\n\n"
                "# Plan\n\n## Status\n\n- [ ] Chunk 01: current\n"
            )
        prawduct = tmp_path / ".prawduct"
        assert buildplan_refs.infer_scope_from_branch(tmp_path, prawduct) is None

    def test_a_declared_plan_with_no_scope_infers_nothing(self, tmp_path: Path):
        """A branch claim is not a scope. Inventing one would tag a change-log
        entry and a ledger row with a string no plan declares."""
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")
        _checkout_new_branch(tmp_path, "feat/scopeless")

        artifacts = tmp_path / ".prawduct" / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        (artifacts / "build-plan-scopeless.md").write_text(
            "---\nartifact: build-plan\nbranch: feat/scopeless\n---\n\n"
            "# Plan\n\n## Status\n\n- [ ] Chunk 01: current\n"
        )
        prawduct = tmp_path / ".prawduct"
        assert buildplan_refs.infer_scope_from_branch(tmp_path, prawduct) is None

    def test_archived_plans_do_not_shadow_their_live_siblings(self, tmp_path: Path):
        """Discovery went recursive; `archive/` had to stop being discoverable.

        The scan is `sorted()` and first-wins, and `artifacts/archive/x.md` sorts
        BEFORE `artifacts/x.md` — so an archived copy would win the scope and
        regenerate the retired plan instead of the live one. Every record check
        already honours the archive convention; discovery did not.
        """
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")
        _checkout_new_branch(tmp_path, "fix/shadowed")

        artifacts = tmp_path / ".prawduct" / "artifacts"
        (artifacts / "archive").mkdir(parents=True, exist_ok=True)
        # Same scope, both files. The archived one sorts first.
        (artifacts / "archive" / "build-plan-shadowed.md").write_text(
            "---\nartifact: build-plan\nscope: shadowed\n---\n\n"
            "# Retired\n\n## Status\n\n- [ ] Chunk 01: retired work\n"
        )
        (artifacts / "build-plan-shadowed.md").write_text(
            "---\nartifact: build-plan\nscope: shadowed\n---\n\n"
            "# Live\n\n## Status\n\n- [ ] Chunk 01: live work\n"
        )

        plan = buildplan_refs.resolve_branch_plan(tmp_path, tmp_path / ".prawduct")
        assert plan.scope == "shadowed"
        assert plan.path.name == "build-plan-shadowed.md"
        # By PARENT, not by substring: `tmp_path` embeds the test's own name,
        # which contains "archived" — a substring check would fail here for a
        # reason that has nothing to do with the behaviour under test.
        assert plan.path.parent.name == "artifacts", (
            f"an archived plan shadowed its live sibling: {plan.path}"
        )
        assert plan.path.read_text().startswith("---\nartifact: build-plan")
        assert "# Live" in plan.path.read_text()

    def test_has_unfinished_chunk_edge_readings(self, tmp_path: Path):
        """The two readings the docstring promises, pinned so they stay true.

        A plan with no Status section reads unfinished — an unparseable plan is
        not evidence of completion. An unreadable one reads finished, because a
        file we cannot open is not something to attribute a review to.
        """
        plan = tmp_path / "p.md"
        plan.write_text("# Plan\n\nNo Status section at all.\n")
        assert buildplan_refs._has_unfinished_chunk(plan) is True

        plan.write_text("# Plan\n\n## Status\n\n- [x] Chunk 01: done\n")
        assert buildplan_refs._has_unfinished_chunk(plan) is False

        assert buildplan_refs._has_unfinished_chunk(tmp_path / "absent.md") is False

    def test_an_unconfirmable_pointer_is_named_as_an_assumption(self, tmp_path: Path):
        """A branch matching no declared scope cannot be shown related OR
        unrelated — so the pointer stands and the rationale says it is assumed.

        Declining here would demote every repo whose branch names differ from
        its scopes; asserting relation silently is what misattributed three
        review records. The rationale is the record: it lands in
        `mode_chosen_by`.
        """
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")
        _checkout_new_branch(tmp_path, "feature/no-plan-of-its-own")
        _write_build_plan(
            tmp_path / ".prawduct", [("x", "Chunk 1"), (" ", "Chunk 2"), (" ", "Chunk 3")]
        )
        _write(tmp_path, "src/work.py", "# in progress\n")

        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "chunk"
        assert "assumed related" in rationale
        assert "matches no plan's declared scope" in rationale


# ---------------------------------------------------------------------------
# Plan-override — current chunk's `Critic mode:` field (CRT-3M8Q)
# ---------------------------------------------------------------------------


class TestPlanCriticModeOverride:
    """The active build plan's CURRENT chunk `Critic mode:` field is a
    successive override on top of inference: when the first-unchecked chunk
    declares a valid mode, inference returns it with a
    ``plan-override: <mode>`` rationale. Explicit `$ARGUMENTS` still wins on
    top (per-invocation override); an absent/blank/invalid field falls
    through to the ordinary inference rules.
    """

    def test_plan_override_final_beats_inferred_chunk(self, tmp_path: Path):
        """Mid-plan (chunk 2 of 4 unchecked) would infer ``chunk`` (rule-4),
        but the current chunk declares ``Critic mode: final`` — the plan
        override wins and rationale reflects it. This is the exact CRT-3M8Q
        scenario: a plan-mandated ``final`` that used to silently run as the
        inferred ``chunk``."""
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")

        _write_build_plan_with_chunks(
            tmp_path / ".prawduct",
            [
                ("x", "Chunk 01: keystone"),
                (" ", "Chunk 02: widget"),
                (" ", "Chunk 03: gadget"),
                (" ", "Chunk 04: wrap-up"),
            ],
            chunk_modes={"02": "final"},
        )
        # Mid-chunk-2 uncommitted work — inference alone would pick chunk.
        _write(tmp_path, "src/widget.py", "# chunk 2 work\n")

        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "final"
        assert rationale == "plan-override: final"

    def test_explicit_args_still_beats_plan_override(self, tmp_path: Path):
        """The slash-command argument is the per-invocation override and wins
        over the plan-level override."""
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")

        _write_build_plan_with_chunks(
            tmp_path / ".prawduct",
            [
                ("x", "Chunk 01: keystone"),
                (" ", "Chunk 02: widget"),
                (" ", "Chunk 03: gadget"),
            ],
            chunk_modes={"02": "final"},
        )
        _write(tmp_path, "src/widget.py", "# chunk 2 work\n")

        mode, rationale = infer_mode(tmp_path, "chunk")
        assert mode == "chunk"
        assert rationale == "explicit-args"

    def test_no_override_field_falls_through_to_inference(self, tmp_path: Path):
        """Current chunk with no ``Critic mode:`` field → ordinary inference
        (rule-4 chunk for a mid-plan review)."""
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")

        _write_build_plan_with_chunks(
            tmp_path / ".prawduct",
            [
                ("x", "Chunk 01: keystone"),
                (" ", "Chunk 02: widget"),
                (" ", "Chunk 03: gadget"),
            ],
            chunk_modes={},  # no declarations
        )
        _write(tmp_path, "src/widget.py", "# chunk 2 work\n")

        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "chunk"
        assert rationale.startswith("rule-4 chunk:")

    def test_invalid_override_value_falls_through_to_inference(self, tmp_path: Path):
        """An unrecognized ``Critic mode:`` value is ignored (not honored as
        an override) — inference proceeds as if the field were absent."""
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")

        _write_build_plan_with_chunks(
            tmp_path / ".prawduct",
            [
                ("x", "Chunk 01: keystone"),
                (" ", "Chunk 02: widget"),
                (" ", "Chunk 03: gadget"),
            ],
            chunk_modes={"02": "ultra-thorough"},
        )
        _write(tmp_path, "src/widget.py", "# chunk 2 work\n")

        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "chunk"
        assert rationale.startswith("rule-4 chunk:")

    def test_override_on_current_chunk_not_a_sibling(self, tmp_path: Path):
        """The override is read from the CURRENT chunk (first unchecked),
        not a later sibling. Chunk 02 is current with no declaration; chunk
        03 declares ``final`` — that later declaration must NOT leak into the
        chunk-02 review."""
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")

        _write_build_plan_with_chunks(
            tmp_path / ".prawduct",
            [
                ("x", "Chunk 01: keystone"),
                (" ", "Chunk 02: widget"),
                (" ", "Chunk 03: gadget"),
            ],
            chunk_modes={"03": "final"},  # sibling, not current
        )
        _write(tmp_path, "src/widget.py", "# chunk 2 work\n")

        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "chunk"
        assert rationale.startswith("rule-4 chunk:")


# ---------------------------------------------------------------------------
# Rationale string format
# ---------------------------------------------------------------------------


class TestRationaleFormat:
    """The rationale must be human-parseable and start with a rule
    identifier so post-hoc reading of ``mode_chosen_by`` shows which
    rule fired without consulting the source."""

    @pytest.mark.parametrize(
        "expected_prefix,setup",
        [
            ("rule-1 verify-resolutions:", "verify_resolutions"),
            ("rule-1b verify-resolutions (post-cumulative fix):", "postfix_fix"),
            ("rule-2 cumulative:", "cumulative"),
            ("rule-3 final:", "final"),
            ("rule-4 chunk:", "chunk_default"),
        ],
    )
    def test_rationale_starts_with_rule_identifier(
        self, tmp_path: Path, expected_prefix: str, setup: str
    ):
        if setup == "postfix_fix":
            _init_repo(tmp_path)
            _write(tmp_path, "README.md", "x\n")
            _commit(tmp_path, "initial")
            _checkout_new_branch(tmp_path, "feature/work")
            _write(tmp_path, "src/a.py", "# a\n")
            _commit(tmp_path, "feat: a")
            _write(tmp_path, "src/b.py", "# b\n")
            reviewed = _commit(tmp_path, "feat: b")
            _write_findings(
                tmp_path / ".prawduct",
                mode="cumulative (bundle review, ready for merge)",
                commit_reviewed=reviewed,
                files_reviewed=["src/a.py", "src/b.py"],
                include_finding=False,
            )
            _write(tmp_path, "src/a.py", "# fixed\n")
            _commit(tmp_path, "fix: post-cumulative")
        if setup == "verify_resolutions":
            _init_repo(tmp_path)
            _write(tmp_path, "src/app.py", "# v1\n")
            prior_sha = _commit(tmp_path, "v1")
            _write(tmp_path, "src/app.py", "# v2\n")
            _write_findings(
                tmp_path / ".prawduct",
                commit_reviewed=prior_sha,
                files_reviewed=["src/app.py"],
            )
        elif setup == "cumulative":
            _init_repo(tmp_path)
            _write(tmp_path, "README.md", "x\n")
            _commit(tmp_path, "initial")
            _checkout_new_branch(tmp_path, "feature/work")
            _write(tmp_path, "src/a.py", "# a\n")
            _commit(tmp_path, "a")
            _write(tmp_path, "src/b.py", "# b\n")
            _commit(tmp_path, "b")
        elif setup == "final":
            _init_repo(tmp_path)
            _write(tmp_path, "README.md", "x\n")
            _commit(tmp_path, "initial")
            for i in range(5):
                _write(tmp_path, f"src/f{i}.py", f"# {i}\n")
        elif setup == "chunk_default":
            _init_repo(tmp_path)
            _write(tmp_path, "README.md", "x\n")
            _commit(tmp_path, "initial")
            # Active plan grounds rule-4 chunk. Without it the
            # fail-safe fires final, not chunk.
            _write_build_plan(
                tmp_path / ".prawduct",
                [("x", "Chunk 1"), (" ", "Chunk 2"), (" ", "Chunk 3")],
            )
            _write(tmp_path, "src/chunk2.py", "# work\n")

        _, rationale = infer_mode(tmp_path, None)
        assert rationale.startswith(expected_prefix), (
            f"Expected rationale to start with {expected_prefix!r}, "
            f"got: {rationale!r}"
        )


# ---------------------------------------------------------------------------
# prawduct-hook subcommand integration
# ---------------------------------------------------------------------------


class TestInferCriticModeSubcommand:
    """``python3 bin/prawduct-hook infer-critic-mode`` is the
    structurally-bounded entrypoint the Critic SKILL uses. It must
    return ``<mode>|<rationale>`` on stdout and exit 0."""

    HOOK_PATH = REPO_ROOT / "bin" / "prawduct-hook"

    def _run_subcommand(
        self, project_dir: Path, extra_args: list[str] | None = None
    ) -> subprocess.CompletedProcess:
        cmd = [
            "python3", str(self.HOOK_PATH), "infer-critic-mode",
        ]
        if extra_args:
            cmd.extend(extra_args)
        env = _git_env(project_dir)
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)
        return subprocess.run(
            cmd, capture_output=True, text=True, env=env, timeout=15
        )

    def test_subcommand_outputs_pipe_separated_mode_and_rationale(
        self, tmp_path: Path
    ):
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")

        result = self._run_subcommand(tmp_path)
        assert result.returncode == 0, result.stderr
        assert "|" in result.stdout
        mode, rationale = result.stdout.strip().split("|", 1)
        # No plan, no diff → rule-4 fail-safe → final
        assert mode == "final"
        assert rationale.startswith("rule-4 final:")

    def test_subcommand_honors_explicit_args(self, tmp_path: Path):
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")

        result = self._run_subcommand(tmp_path, ["final"])
        assert result.returncode == 0
        mode, rationale = result.stdout.strip().split("|", 1)
        assert mode == "final"
        assert rationale == "explicit-args"


# ---------------------------------------------------------------------------
# Schema validator — mode_chosen_by field
# ---------------------------------------------------------------------------


class TestValidatorAcceptsModeChosenBy:
    """``validate_critic_findings`` must accept the new optional
    ``mode_chosen_by`` string and reject empty/non-string values
    (writer-drift surfaced at validation rather than later)."""

    @pytest.fixture(autouse=True)
    def _module(self):
        # validate_critic_findings moved to lib.gates (STH-9V4K ch.6); test it
        # where it now lives rather than through the hook.
        from lib import gates  # noqa: PLC0415

        self.mod = gates

    def _write_findings(self, path: Path, **overrides) -> Path:
        data = {
            "files_reviewed": ["bin/prawduct-hook"],
            "findings": [],
            "summary": "No issues.",
        }
        data.update(overrides)
        path.write_text(json.dumps(data))
        return path

    def test_validator_accepts_mode_chosen_by_with_rule_string(
        self, tmp_path: Path
    ):
        path = self._write_findings(
            tmp_path / "findings.json",
            mode_chosen_by="rule-3 final: last unchecked chunk in progress",
        )
        assert self.mod.validate_critic_findings(path) is True

    def test_validator_accepts_mode_chosen_by_explicit_args(self, tmp_path: Path):
        path = self._write_findings(
            tmp_path / "findings.json",
            mode_chosen_by="explicit-args",
        )
        assert self.mod.validate_critic_findings(path) is True

    def test_validator_accepts_findings_without_mode_chosen_by(
        self, tmp_path: Path
    ):
        """Optional field — back-compat with pre-v1.5 findings files."""
        path = self._write_findings(tmp_path / "findings.json")
        assert self.mod.validate_critic_findings(path) is True

    def test_validator_rejects_empty_mode_chosen_by(self, tmp_path: Path):
        path = self._write_findings(
            tmp_path / "findings.json",
            mode_chosen_by="",
        )
        assert self.mod.validate_critic_findings(path) is False

    def test_validator_rejects_whitespace_only_mode_chosen_by(
        self, tmp_path: Path
    ):
        path = self._write_findings(
            tmp_path / "findings.json",
            mode_chosen_by="   ",
        )
        assert self.mod.validate_critic_findings(path) is False

    def test_validator_rejects_non_string_mode_chosen_by(self, tmp_path: Path):
        path = self._write_findings(
            tmp_path / "findings.json",
            mode_chosen_by=42,
        )
        assert self.mod.validate_critic_findings(path) is False


# (TestValidatorExtendsCumulative removed — kernel-v3 chunk 04 retired the
# extends_cumulative chain: no writer emits the field and no gate reads it,
# so the validator no longer inspects it.)
# ---------------------------------------------------------------------------
# Metadata-path classification (file-sync-era prefixes retired post-M4)
# ---------------------------------------------------------------------------


class TestMetadataPathClassification:
    """Post-M4 the metadata allowlist is plugin-only: product-owned state
    (``.prawduct/``) and the committed install reference
    (``.claude/settings.json``). The file-sync-era prefixes
    (``.claude/skills/`` for synced framework skills, ``tools/product-hook``)
    were removed — a plugin repo never carries them, and a product's *own*
    skill under ``.claude/skills/`` is product code that must be gated, not
    excused from the reflection/Critic gates.

    The allowlist's canonical home is ``lib.gitstate`` — ``critic_mode``'s
    mirror was consolidated onto it (STH-2K8R), so these pins target the one
    copy every consumer (gates, critic_mode, the hook via lib) now reads.
    """

    def test_product_state_and_install_reference_are_metadata(self):
        from lib.gitstate import _is_metadata_path

        assert _is_metadata_path(".prawduct/project-state.yaml")
        assert _is_metadata_path(".claude/settings.json")

    def test_retired_filesync_prefixes_are_not_metadata(self):
        from lib.gitstate import _is_metadata_path

        # A product's own skill is product code, not excused framework metadata.
        assert not _is_metadata_path(".claude/skills/my-skill/SKILL.md")
        # The committed file-sync product hook is retired; never excused.
        assert not _is_metadata_path("tools/product-hook")

    def test_own_skill_edits_count_as_code_in_inference(self, tmp_path: Path):
        """End-to-end companion: 5 uncommitted ``.claude/skills/`` files with no
        build plan now drive the no-plan medium+ rule (→ ``final``, rationale
        ``"no build plan"``), proving the classifier change reaches the
        gate-relevant code-file count. Before the retirement these were metadata
        and the same repo fell through to rule-4 (``"rule-4 final:"``)."""
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")

        for i in range(5):
            _write(tmp_path, f".claude/skills/skill_{i}/SKILL.md", f"# skill {i}\n")

        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "final"
        assert "no build plan" in rationale


def _setup_progressed_branch(
    tmp_path: Path,
    items: list[tuple[str, str]],
    *,
    chunk_modes: dict[str, str] | None = None,
    committed: list[str] | None = None,
    chunk_commit_subjects: bool = True,
    uncommitted: bool = True,
) -> None:
    """Stand up a feature branch whose plan has its first ``committed`` chunks
    TICKED and the rest open — the state CRT-7B4M is about, expressed in the
    single reading.

    The chunks named in ``committed`` are both ticked in Status and given a
    ``(Chunk NN)`` commit, because that is what a finished chunk looks like:
    the box is the record, the commit is the work. Commits the plan (a non-chunk
    subject) first; ``chunk_commit_subjects`` controls whether the chunk commits
    reference ``(Chunk NN)``. Leaves uncommitted work when ``uncommitted`` (the
    chunk in progress).
    """
    _init_repo(tmp_path, branch="main")
    _write(tmp_path, "README.md", "x\n")
    _commit(tmp_path, "initial")
    prawduct = tmp_path / ".prawduct"
    prawduct.mkdir(parents=True, exist_ok=True)
    (prawduct / "project-state.yaml").write_text("base_branch: main\n")
    ticked = {cid.lstrip("0") or "0" for cid in (committed or [])}
    items = [
        ("x", text)
        if (m := re.search(r"Chunk\s+0*(\d+)", text)) and m.group(1).lstrip("0") in ticked
        else (mark, text)
        for mark, text in items
    ]
    _write_build_plan_with_chunks(prawduct, items, chunk_modes)
    _checkout_new_branch(tmp_path, "feature/x")
    _commit(tmp_path, "plan: write the build plan")  # non-chunk subject
    for cid in committed or []:
        _write(tmp_path, f"src/chunk_{cid}.py", f"# chunk {cid}\n")
        subject = (
            f"feat: do the work (Chunk {cid})"
            if chunk_commit_subjects
            else "feat: do the work"
        )
        _commit(tmp_path, subject)
    if uncommitted:
        _write(tmp_path, "src/wip.py", "# work in progress\n")


_FIVE_CHUNKS = [(" ", f"Chunk 0{i}: step {i}") for i in range(1, 6)]


class TestBranchProgressCRT7B4M:
    """Mode inference must read the CURRENT chunk, not the first item.

    CRT-7B4M was originally about Status checkboxes that never flipped because
    they were a derived view, which made "first ``- [ ]``" mean Chunk 01 for a
    whole branch and pinned every chunk's mode to Chunk 01's declaration. The
    derived view is retired and the boxes are now ticked by hand, so the fixture
    ticks them — but the property under test is unchanged and still worth
    pinning: inference resolves the current chunk through the single owner, and
    a plan whose early chunks are done must not be graded by its first chunk's
    `**Critic mode:**` field."""

    def test_midchunk_no_override_infers_chunk_not_chunk01_final(self, tmp_path):
        # Chunk 01 declares final; chunks 01-02 done (ticked + committed).
        # Pre-fix: first-[ ]=Chunk 01 → override final on EVERY chunk.
        # Fixed: current chunk = 03 (first uncommitted), no mode → rule-4 chunk.
        _setup_progressed_branch(
            tmp_path, _FIVE_CHUNKS, chunk_modes={"01": "final"}, committed=["01", "02"]
        )
        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "chunk", rationale

    def test_current_chunk_override_is_honored_on_branch(self, tmp_path):
        # The CURRENT chunk (03) declares final → override reads chunk 03, not 01.
        _setup_progressed_branch(
            tmp_path, _FIVE_CHUNKS, chunk_modes={"03": "final"}, committed=["01", "02"]
        )
        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "final"
        assert "plan-override" in rationale

    def test_last_chunk_infers_final(self, tmp_path):
        # 3-chunk plan, chunks 01-02 done, last chunk in progress → rule-3.
        three = [(" ", f"Chunk 0{i}: step {i}") for i in range(1, 4)]
        _setup_progressed_branch(tmp_path, three, committed=["01", "02"])
        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "final"
        assert "rule-3" in rationale

    def test_first_chunk_in_progress_no_override(self, tmp_path):
        # Nothing committed yet (current = chunk 01). Chunk 02 declares final, but
        # the current chunk is 01 (no mode) → chunk, not chunk-02's final.
        _setup_progressed_branch(
            tmp_path, _FIVE_CHUNKS, chunk_modes={"02": "final"}, committed=[]
        )
        mode, _ = infer_mode(tmp_path, None)
        assert mode == "chunk"

    def test_commit_subjects_do_not_influence_the_mode(self, tmp_path):
        """Two tests here once pinned DEGRADATION — what happened when the
        git-derived reading was unavailable (flag off, or commits lacking
        `(Chunk NN)`). There is no second reading to degrade from anymore, so
        the property worth pinning is the stronger one: commit subjects are
        irrelevant to which chunk is current.

        Asserted by DIFFERENCE, not by a single green: the same plan with and
        without `(Chunk NN)` subjects must infer the same mode. A reintroduced
        commit-derived reading would make these two disagree.
        """
        with_refs = tmp_path / "with-refs"
        without_refs = tmp_path / "without-refs"
        for path, refs in ((with_refs, True), (without_refs, False)):
            path.mkdir()
            _setup_progressed_branch(
                path,
                _FIVE_CHUNKS,
                chunk_modes={"03": "final"},
                committed=["01", "02"],
                chunk_commit_subjects=refs,
            )
        assert infer_mode(with_refs, None) == infer_mode(without_refs, None)
        # And the shared answer is the one the BOXES imply: 01/02 ticked, so the
        # current chunk is 03 and its declared mode is the override in force.
        assert infer_mode(with_refs, None)[0] == "final"

    def test_gitflow_base_excludes_develop_side_chunk_commits(self, tmp_path):
        # base_branch=develop; develop carries an unrelated (Chunk 03) commit
        # BEFORE the feature fork. The canonical resolver picks develop, so
        # develop..HEAD excludes it and that foreign chunk ref is never seen.
        # The old main-first resolver would scan main..HEAD and pick it up.
        #
        # Mode inference no longer reads commits at all, so the subject moved:
        # the base-resolution guard now belongs to the unticked-chunk tripwire,
        # which is the remaining consumer of `base..HEAD` chunk refs. Asserted
        # there, because asserting it through `infer_mode` would be vacuous —
        # an all-unticked plan infers from box 01 whatever git says.
        _init_repo(tmp_path, branch="main")
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")
        _checkout_new_branch(tmp_path, "develop")
        _write(tmp_path, "old.py", "# old\n")
        _commit(tmp_path, "feat: prior feature (Chunk 03)")  # develop-side chunk ref
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir(parents=True, exist_ok=True)
        (prawduct / "project-state.yaml").write_text("base_branch: develop\n")
        three = [(" ", f"Chunk 0{i}: step {i}") for i in range(1, 4)]
        _write_build_plan_with_chunks(prawduct, three)
        _checkout_new_branch(tmp_path, "feature/x")
        _commit(tmp_path, "plan: write build plan")
        _write(tmp_path, "src/c01.py", "# 1\n")
        _commit(tmp_path, "feat: do it (Chunk 01)")
        _write(tmp_path, "src/wip.py", "# wip\n")  # chunk 02 in progress

        notice = buildplan_refs.unticked_committed_chunk_notice(tmp_path)
        assert notice is not None and "Chunk 01" in notice
        assert "Chunk 03" not in notice, (
            "develop's pre-fork (Chunk 03) commit leaked past the base "
            f"resolution into base..HEAD: {notice!r}"
        )


# (TestChainAnchorParity removed — kernel-v3 chunk 04 deleted the PR gate's
# chain-anchor helper; critic_mode's copy is now the only one, so there is
# no second implementation to hold in lockstep. Chunk 06's vestige sweep
# then deleted that copy's multi-link ``extends_cumulative`` arm — the
# stays-deleted guards live in TestRule1bPostCumulativeFix and the rule-2
# class above.)
