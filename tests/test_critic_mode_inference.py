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
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib import infer_mode  # noqa: E402 — sys.path mutated above


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
) -> None:
    """Write a ``.critic-findings.json`` for inference rule fixtures."""
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


# ---------------------------------------------------------------------------
# Rule 2 — cumulative
# ---------------------------------------------------------------------------


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
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")
        _checkout_new_branch(tmp_path, "feature/work")
        _write(tmp_path, "src/a.py", "# a\n")
        _commit(tmp_path, "feat: a")  # only 1 ahead

        mode, _ = infer_mode(tmp_path, None)
        assert mode != "cumulative"

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

    def test_does_not_fire_when_no_base_branch(self, tmp_path: Path):
        """Detached/orphan branch without main/master/develop → cumulative
        can't detect base. No active plan + no diff signal → rule-4
        fail-safe → final."""
        _init_repo(tmp_path, branch="feature/standalone")
        _write(tmp_path, "src/a.py", "# a\n")
        _commit(tmp_path, "a")
        _write(tmp_path, "src/b.py", "# b\n")
        _commit(tmp_path, "b")

        mode, _ = infer_mode(tmp_path, None)
        # No main/master/develop → cumulative can't detect base; no plan,
        # clean tree → rule-4 fail-safe → final.
        assert mode == "final"


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
            ("rule-2 cumulative:", "cumulative"),
            ("rule-3 final:", "final"),
            ("rule-4 chunk:", "chunk_default"),
        ],
    )
    def test_rationale_starts_with_rule_identifier(
        self, tmp_path: Path, expected_prefix: str, setup: str
    ):
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
    """

    def test_product_state_and_install_reference_are_metadata(self):
        from lib.critic_mode import _is_metadata_path

        assert _is_metadata_path(".prawduct/project-state.yaml")
        assert _is_metadata_path(".claude/settings.json")

    def test_retired_filesync_prefixes_are_not_metadata(self):
        from lib.critic_mode import _is_metadata_path

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


def _setup_views_branch(
    tmp_path: Path,
    items: list[tuple[str, str]],
    *,
    chunk_modes: dict[str, str] | None = None,
    committed: list[str] | None = None,
    views_enabled: bool = True,
    chunk_commit_subjects: bool = True,
    uncommitted: bool = True,
) -> None:
    """Stand up a views-enabled feature branch where the Status checkboxes are
    an unflipped derived view (all ``- [ ]``) and progress lives in git.

    Commits the plan (a non-chunk subject) then one commit per ``committed``
    chunk id; ``chunk_commit_subjects`` controls whether those commits reference
    ``(Chunk NN)``. Leaves uncommitted work when ``uncommitted`` (the chunk in
    progress). Mirrors the real CRT-7B4M condition.
    """
    _init_repo(tmp_path, branch="main")
    _write(tmp_path, "README.md", "x\n")
    _commit(tmp_path, "initial")
    prawduct = tmp_path / ".prawduct"
    prawduct.mkdir(parents=True, exist_ok=True)
    (prawduct / "project-state.yaml").write_text(
        f"views_enabled: {'true' if views_enabled else 'false'}\n"
    )
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
    """On a views-enabled feature branch the Status checkboxes never flip
    (derived view), so progress must come from git, not the first ``- [ ]``
    (which is always Chunk 01). CRT-7B4M."""

    def test_midchunk_no_override_infers_chunk_not_chunk01_final(self, tmp_path):
        # Chunk 01 declares final; checkboxes all [ ]; chunks 01-02 committed.
        # Pre-fix: first-[ ]=Chunk 01 → override final on EVERY chunk.
        # Fixed: current chunk = 03 (first uncommitted), no mode → rule-4 chunk.
        _setup_views_branch(
            tmp_path, _FIVE_CHUNKS, chunk_modes={"01": "final"}, committed=["01", "02"]
        )
        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "chunk", rationale

    def test_current_chunk_override_is_honored_on_branch(self, tmp_path):
        # The CURRENT chunk (03) declares final → override reads chunk 03, not 01.
        _setup_views_branch(
            tmp_path, _FIVE_CHUNKS, chunk_modes={"03": "final"}, committed=["01", "02"]
        )
        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "final"
        assert "plan-override" in rationale

    def test_last_chunk_infers_final_via_git(self, tmp_path):
        # 3-chunk plan, chunks 01-02 committed, last chunk in progress → rule-3.
        three = [(" ", f"Chunk 0{i}: step {i}") for i in range(1, 4)]
        _setup_views_branch(tmp_path, three, committed=["01", "02"])
        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "final"
        assert "rule-3" in rationale

    def test_first_chunk_in_progress_no_override(self, tmp_path):
        # Nothing committed yet (current = chunk 01). Chunk 02 declares final, but
        # the current chunk is 01 (no mode) → chunk, not chunk-02's final.
        _setup_views_branch(
            tmp_path, _FIVE_CHUNKS, chunk_modes={"02": "final"}, committed=[]
        )
        mode, _ = infer_mode(tmp_path, None)
        assert mode == "chunk"

    def test_degrades_to_checkboxes_when_views_disabled(self, tmp_path):
        # views_enabled false → git path off → first-[ ]=Chunk 01 → its final wins
        # (the prior behavior; the fix never makes a non-views repo worse).
        _setup_views_branch(
            tmp_path,
            _FIVE_CHUNKS,
            chunk_modes={"01": "final"},
            committed=["01", "02"],
            views_enabled=False,
        )
        mode, _ = infer_mode(tmp_path, None)
        assert mode == "final"

    def test_degrades_when_commits_dont_reference_chunks(self, tmp_path):
        # views on, but commit subjects lack "Chunk NN" → no git signal →
        # checkbox fallback (first-[ ]=Chunk 01 → its final).
        _setup_views_branch(
            tmp_path,
            _FIVE_CHUNKS,
            chunk_modes={"01": "final"},
            committed=["01", "02"],
            chunk_commit_subjects=False,
        )
        mode, _ = infer_mode(tmp_path, None)
        assert mode == "final"

    def test_gitflow_base_excludes_develop_side_chunk_commits(self, tmp_path):
        # base_branch=develop; develop carries an unrelated (Chunk 03) commit
        # BEFORE the feature fork. The canonical resolver picks develop, so
        # develop..HEAD excludes it and only chunk 01 counts → current=02 → chunk.
        # The old main-first resolver would scan main..HEAD, count develop's
        # Chunk 03, inflate complete to 2/3 → mis-fire rule-3 final. Guards the
        # gitflow base-resolution fix (CRT-7B4M / the _resolve_base_branch class).
        _init_repo(tmp_path, branch="main")
        _write(tmp_path, "README.md", "x\n")
        _commit(tmp_path, "initial")
        _checkout_new_branch(tmp_path, "develop")
        _write(tmp_path, "old.py", "# old\n")
        _commit(tmp_path, "feat: prior feature (Chunk 03)")  # develop-side chunk ref
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir(parents=True, exist_ok=True)
        (prawduct / "project-state.yaml").write_text(
            "views_enabled: true\nbase_branch: develop\n"
        )
        three = [(" ", f"Chunk 0{i}: step {i}") for i in range(1, 4)]
        _write_build_plan_with_chunks(prawduct, three)
        _checkout_new_branch(tmp_path, "feature/x")
        _commit(tmp_path, "plan: write build plan")
        _write(tmp_path, "src/c01.py", "# 1\n")
        _commit(tmp_path, "feat: do it (Chunk 01)")
        _write(tmp_path, "src/wip.py", "# wip\n")  # chunk 02 in progress
        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "chunk", rationale
