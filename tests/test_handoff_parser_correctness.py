"""Build-plan read-path correctness — the parse that feeds the session handoff.

Four independent wrong-output defects were reproduced against this repo's own
live build plan (SCN-4H9T, BLD-7K3Q), all in the path from build-plan Status to
``.session-handoff.md``:

* a completed plan was reported as the next session's active ``**Task**`` —
  ``staleness_scan`` applied a done-predicate and ``_get_active_work`` read the
  *identical* parse without one;
* on a ``views_enabled`` repo the current chunk was "first ``- [ ]``", which is
  Chunk 01 forever because the checkboxes only flip at release;
* a frontmatter-style plan (no ``# Build Plan`` H1) produced no description, and
  description is the sole key gating the handoff's whole Work In Progress
  section, so the section silently vanished;
* ``Context:`` was read as one physical line, truncating the multi-paragraph
  block ``building.md`` calls "the cross-session handoff".

Real ``git init`` repos where the behavior is git-derived: the defect survived
unit-level correctness for months precisely because nothing exercised the real
path.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib import briefing, buildplan_refs, critic_mode, gates  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git_env(repo: Path) -> dict[str, str]:
    return {
        "HOME": str(repo.parent / "_home"),
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
    }


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=_git_env(repo),
        check=True,
        timeout=10,
    )


def _init_repo(repo: Path, *, branch: str = "main") -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "--quiet", "-b", branch)
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")


def _commit(repo: Path, msg: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", msg, "--quiet", "--allow-empty")


def _write_plan(project_dir: Path, content: str) -> Path:
    plan = project_dir / ".prawduct" / "artifacts" / "build-plan.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(content)
    return plan


def _write_state(project_dir: Path, content: str) -> None:
    state = project_dir / ".prawduct" / "project-state.yaml"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(content)


# A views_enabled plan mid-flight: every box is `- [ ]` because the Status
# section is a derived view that only flips at release.
VIEWS_PLAN = """---
artifact: build-plan
scope: session-handoff-continuity
---

## Status

<!-- views_enabled: true — these checkboxes are a DERIVED VIEW. -->

- [ ] Chunk 01: The forward channel
- [ ] Chunk 02: Parser correctness
- [ ] Chunk 03: Proactive close
- [ ] Chunk 04: The Critic summary

Context: Chunks 01-03 shipped.

## Build Chunks

### Chunk 02: Parser correctness
- **Type:** code

### Chunk 04: The Critic summary
- **Type:** code
- **Critic mode:** final

Touches `.prawduct/artifacts/build-plan.md`.
"""


def _views_repo(tmp_path: Path, *, committed_chunks: int = 3) -> Path:
    """A views_enabled repo on a feature branch off ``develop``, with the first
    ``committed_chunks`` chunks recorded by commit subject and NO box flipped —
    the state that reported "Chunk 01" live for an entire branch."""
    repo = tmp_path / "repo"
    _init_repo(repo, branch="develop")
    _write_state(repo, "views_enabled: true\nbase_branch: develop\n")
    _write_plan(repo, VIEWS_PLAN)
    _commit(repo, "chore: plan")
    _git(repo, "checkout", "-b", "feature/session-handoff-continuity", "--quiet")
    for n in range(1, committed_chunks + 1):
        _commit(repo, f"feat(continuity): land it (Chunk 0{n})")
    return repo


# ---------------------------------------------------------------------------
# Defect 3 — the done-predicate
# ---------------------------------------------------------------------------


class TestCompletedPlanIsNotActiveWork:
    def test_all_boxes_checked_is_not_active_work(self, tmp_path: Path):
        """A finished plan must never be stamped as the next session's Task."""
        _write_plan(
            tmp_path,
            "# Build Plan — Done (2026-07-26)\n\n"
            "## Status\n\n- [x] Chunk 01: A\n- [x] Chunk 02: B\n",
        )
        status = buildplan_refs._parse_build_plan_status(tmp_path)
        assert status["_has_status_items"] == "true"
        assert "current_chunk" not in status
        assert buildplan_refs.build_plan_is_complete(status) is True
        assert briefing._get_active_work(tmp_path) == {}

    def test_in_flight_plan_is_still_active_work(self, tmp_path: Path):
        _write_plan(
            tmp_path,
            "# Build Plan — Doing (2026-07-26)\n\n"
            "## Status\n\n- [x] Chunk 01: A\n- [ ] Chunk 02: B\n",
        )
        status = buildplan_refs._parse_build_plan_status(tmp_path)
        assert buildplan_refs.build_plan_is_complete(status) is False
        assert briefing._get_active_work(tmp_path)["current_chunk"] == "Chunk 02: B"

    def test_plan_with_no_status_items_is_not_complete(self, tmp_path: Path):
        """No items means nothing to be complete — distinct from all-done, and
        the caller must not read it as a finished plan."""
        _write_plan(tmp_path, "# Build Plan — Empty (2026-07-26)\n\n## Status\n\nContext: soon.\n")
        status = buildplan_refs._parse_build_plan_status(tmp_path)
        assert buildplan_refs.build_plan_is_complete(status) is False

    def test_handoff_omits_work_section_for_a_completed_plan(self, tmp_path: Path):
        _init_repo(tmp_path)
        _write_plan(
            tmp_path,
            "# Build Plan — Done (2026-07-26)\n\n## Status\n\n- [x] Chunk 01: A\n",
        )
        (tmp_path / ".prawduct" / ".session-reflected").write_text("did the thing")
        briefing.generate_session_handoff(tmp_path)
        handoff = (tmp_path / ".prawduct" / ".session-handoff.md").read_text()
        assert "## Work In Progress" not in handoff
        assert "did the thing" in handoff


# ---------------------------------------------------------------------------
# Defect 4 — views_enabled, at EVERY consumer
# ---------------------------------------------------------------------------


class TestViewsEnabledCurrentChunk:
    """Three chunks committed, no box flipped. Every consumer must say 04."""

    def test_parse_reports_the_chunk_actually_in_flight(self, tmp_path: Path):
        repo = _views_repo(tmp_path)
        status = buildplan_refs._parse_build_plan_status(repo)
        assert status["current_chunk"] == "Chunk 04: The Critic summary"

    def test_current_chunk_id(self, tmp_path: Path):
        repo = _views_repo(tmp_path)
        assert buildplan_refs._current_chunk_id_from_status(repo) == "04"

    def test_verify_chunk_refs_grades_the_right_chunk(self, tmp_path: Path):
        """BLD-7K3Q: the gate reported `ok: chunk 01` for a whole branch while
        chunks 02..N went unverified — silently, and green.

        Asserted POSITIVELY. A `"01" not in stdout` check passes on empty
        stdout, which is what a `cannot-verify` exit produces — so it would
        have gone green against the pre-fix code too.
        """
        repo = _views_repo(tmp_path)
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "bin" / "prawduct-hook"), "verify-chunk-refs"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            env={**_git_env(repo), "CLAUDE_PROJECT_DIR": str(repo)},
            timeout=30,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "ok: chunk 04" in proc.stdout, proc.stdout + proc.stderr

    def test_progress_counts_committed_chunks(self, tmp_path: Path):
        """CRT-7B4M's derivation keeps its answer after the move."""
        repo = _views_repo(tmp_path)
        progress = buildplan_refs.resolve_chunk_progress(repo)
        assert (progress.complete, progress.current_id) == (3, "04")
        assert progress.git_derived is True

    def test_mode_inference_routes_through_the_single_owner(
        self, tmp_path: Path, monkeypatch
    ):
        """`infer_mode` must not re-derive the git-vs-checkbox precedence.

        Asserted by DEPENDENCE, not by agreement: two functions returning "04"
        is equally true of an `infer_mode` that derives "04" for itself. So
        redirect the owner and require `infer_mode`'s answer to move with it.
        Chunk 04 declares `**Critic mode:** final`; Chunk 02 declares none, so
        the plan-override appears only when 04 is the resolved chunk. An
        `infer_mode` that composed the precedence itself would still resolve 04
        from git and stay green.
        """
        repo = _views_repo(tmp_path)
        mode, rationale = critic_mode.infer_mode(repo)
        assert (mode, rationale) == ("final", "plan-override: final")

        redirected = buildplan_refs.resolve_chunk_progress(repo)._replace(
            current_id="02", current_text="Chunk 02: Parser correctness"
        )
        monkeypatch.setattr(
            critic_mode.buildplan_refs, "resolve_chunk_progress", lambda _d: redirected
        )
        assert critic_mode.infer_mode(repo)[1] != "plan-override: final", (
            "infer_mode ignored the resolver — it is re-deriving which chunk is "
            "current for itself"
        )

    def test_briefing_resume_line_names_the_right_chunk(self, tmp_path: Path):
        repo = _views_repo(tmp_path)
        text = briefing.assemble_session_briefing(repo, [])
        assert "Resume: Chunk 04: The Critic summary" in text

    def test_handoff_names_the_right_chunk(self, tmp_path: Path):
        repo = _views_repo(tmp_path)
        briefing.generate_session_handoff(repo)
        handoff = (repo / ".prawduct" / ".session-handoff.md").read_text()
        assert "**Current chunk**: Chunk 04: The Critic summary" in handoff

    def test_all_chunks_committed_clears_the_current_chunk(self, tmp_path: Path):
        """Every chunk has a commit → the plan is complete, so there is no
        current chunk even though every box still reads `- [ ]`."""
        repo = _views_repo(tmp_path, committed_chunks=4)
        status = buildplan_refs._parse_build_plan_status(repo)
        assert "current_chunk" not in status
        assert buildplan_refs.build_plan_is_complete(status) is True

    def test_a_prior_releases_shipped_chunk_is_never_current(self, tmp_path: Path):
        """A `[x]` chunk shipped in an EARLIER release has no commit on this
        branch, so a commit-only reading walks back and names it current —
        strictly worse than the checkbox fallback the derivation promises never
        to be worse than. Completion is `[x]` OR committed, never commits alone.
        """
        repo = tmp_path / "repo"
        _init_repo(repo, branch="develop")
        _write_state(repo, "views_enabled: true\nbase_branch: develop\n")
        _write_plan(
            repo,
            VIEWS_PLAN.replace("- [ ] Chunk 01", "- [x] Chunk 01").replace(
                "- [ ] Chunk 02", "- [x] Chunk 02"
            ),
        )
        _commit(repo, "chore: plan")
        _git(repo, "checkout", "-b", "feature/next", "--quiet")
        _commit(repo, "feat: continue (Chunk 03)")
        progress = buildplan_refs.resolve_chunk_progress(repo)
        assert progress.current_id == "04"
        assert progress.complete == 3


class TestGateSemanticsUnchanged:
    """Success criterion 6 of the governing plan: no gate semantics change.

    The gate trigger deliberately stays on the CHECKBOX reading. Git answers
    "which chunk is in flight," which is right for reporting; the gate asks "is
    there still governed work," and a chunk's last commit lands BEFORE its
    Critic pass and its reflection. Deriving the gate from git switched the
    blocking reflection and Critic gates off for the entire complete-but-
    unmerged window — the PR-fix and finding-resolution sessions.
    """

    def test_gate_armed_mid_branch(self, tmp_path: Path):
        repo = _views_repo(tmp_path)
        assert gates._has_active_build_plan_file(repo / ".prawduct") is True

    def test_gate_stays_armed_through_the_complete_but_unmerged_window(
        self, tmp_path: Path
    ):
        repo = _views_repo(tmp_path, committed_chunks=4)
        assert gates._has_active_build_plan_file(repo / ".prawduct") is True

    def test_gate_disarms_once_the_release_flips_the_boxes(self, tmp_path: Path):
        repo = _views_repo(tmp_path, committed_chunks=4)
        _write_plan(repo, VIEWS_PLAN.replace("- [ ] Chunk", "- [x] Chunk"))
        assert gates._has_active_build_plan_file(repo / ".prawduct") is False

    def test_git_failure_degrades_to_the_checkboxes_not_to_nothing(
        self, tmp_path: Path, monkeypatch
    ):
        """A raising git call (absent binary, timeout) must fall back to the
        checkbox reading. Collapsing the whole parse to `{}` would blank the
        handoff's work section AND read as "no build plan" to the gates —
        authority failing OPEN, on a transient hiccup.
        """
        repo = _views_repo(tmp_path)

        def _boom(*_a, **_k):
            raise subprocess.TimeoutExpired(cmd="git", timeout=10)

        monkeypatch.setattr(buildplan_refs.subprocess, "run", _boom)
        status = buildplan_refs._parse_build_plan_status(repo)
        assert status["description"] == "session-handoff-continuity"
        assert status["current_chunk"] == "Chunk 01: The forward channel"
        assert "Chunks 01-03 shipped." in status["context"]
        assert gates._has_active_build_plan_file(repo / ".prawduct") is True

    def test_non_views_repo_still_uses_checkboxes(self, tmp_path: Path):
        """The git path is opt-in; a hand-maintained plan is unaffected."""
        repo = tmp_path / "repo"
        _init_repo(repo, branch="develop")
        _write_state(repo, "views_enabled: false\nbase_branch: develop\n")
        _write_plan(repo, VIEWS_PLAN)
        _commit(repo, "chore: plan")
        _git(repo, "checkout", "-b", "feature/x", "--quiet")
        _commit(repo, "feat: land it (Chunk 01)")
        assert buildplan_refs._current_chunk_id_from_status(repo) == "01"


class TestOneCurrentChunkImplementation:
    """The sweep's structural guarantee: the derivation has ONE home, and no
    consumer re-derives "first unchecked" for itself. CRT-7B4M fixed this at one
    consumer and the defect recurred at two more — the recurrence is the reason
    this pin exists."""

    MOVED_OUT_OF_CRITIC_MODE = (
        "_git_aware_progress",
        "_commits_ahead_of_base",
        "_committed_chunk_ids",
        "_CHUNK_COMMIT_RE",
    )

    def test_critic_mode_no_longer_defines_the_derivation(self):
        for name in self.MOVED_OUT_OF_CRITIC_MODE:
            assert name not in vars(critic_mode), (
                f"{name} is back in lib/critic_mode.py — the git-derived "
                "current-chunk path belongs to lib/buildplan_refs.py so every "
                "consumer gets the same answer (BLD-7K3Q)."
            )

    def test_buildplan_refs_owns_it(self):
        for name in self.MOVED_OUT_OF_CRITIC_MODE:
            assert name in vars(buildplan_refs)

    def test_no_consumer_walks_the_status_section_itself(self):
        """Only ``buildplan_refs`` may consume the Status-section walkers.

        Deriving currency means walking Status and testing checkboxes; a module
        that reaches for the walker is a module about to re-derive "current" for
        itself, which is exactly how this defect reached three consumers. A bare
        ``- [ ]`` grep is NOT the guard — backlog acceptance-checkbox lint and
        docstring prose both match it — so the pin is on the walkers instead.
        (``lib/views.py`` rewrites Status by line index rather than reading it,
        and is deliberately separate.)
        """
        walkers = ("_iter_status_section_lines", "_iter_status_section_items")
        offenders = []
        for path in sorted((REPO_ROOT / "lib").rglob("*.py")):
            if path.name == "buildplan_refs.py":
                continue
            text = path.read_text()
            if any(w in text for w in walkers):
                offenders.append(path.relative_to(REPO_ROOT).as_posix())
        assert not offenders, (
            f"{offenders} walk the build-plan Status section directly; resolve "
            "the current chunk via buildplan_refs._parse_build_plan_status so "
            "every consumer gets the same (git-aware) answer."
        )


# ---------------------------------------------------------------------------
# Defect 5a — a frontmatter-style plan with no H1
# ---------------------------------------------------------------------------


class TestDescriptionFallback:
    def test_frontmatter_scope_names_a_plan_with_no_h1(self, tmp_path: Path):
        _write_plan(
            tmp_path,
            "---\nartifact: build-plan\nscope: session-handoff-continuity\n---\n\n"
            "## Status\n\n- [ ] Chunk 01: A\n",
        )
        status = buildplan_refs._parse_build_plan_status(tmp_path)
        assert status["description"] == "session-handoff-continuity"

    def test_filename_is_the_last_resort(self, tmp_path: Path):
        plan_dir = tmp_path / ".prawduct" / "artifacts"
        plan_dir.mkdir(parents=True)
        (plan_dir / "build-plan-widgets.md").write_text("## Status\n\n- [ ] Chunk 01: A\n")
        _write_state(tmp_path, "active_build_plan: artifacts/build-plan-widgets.md\n")
        status = buildplan_refs._parse_build_plan_status(tmp_path)
        assert status["description"] == "widgets"

    def test_h1_still_wins_when_present(self, tmp_path: Path):
        _write_plan(
            tmp_path,
            "---\nscope: ignored-when-h1-present\n---\n\n"
            "# Build Plan — Real Title (2026-07-26)\n\n## Status\n\n- [ ] Chunk 01: A\n",
        )
        assert buildplan_refs._parse_build_plan_status(tmp_path)["description"] == "Real Title"

    def test_handoff_work_section_survives_a_missing_h1(self, tmp_path: Path):
        """The section vanished entirely on a live four-chunk plan, because
        `description` is the only key gating it."""
        _init_repo(tmp_path)
        _write_plan(
            tmp_path,
            "---\nscope: session-handoff-continuity\n---\n\n"
            "## Status\n\n- [ ] Chunk 02: Parser correctness\n",
        )
        briefing.generate_session_handoff(tmp_path)
        handoff = (tmp_path / ".prawduct" / ".session-handoff.md").read_text()
        assert "## Work In Progress" in handoff
        assert "**Task**: session-handoff-continuity" in handoff
        assert "**Current chunk**: Chunk 02: Parser correctness" in handoff


# ---------------------------------------------------------------------------
# Defect 5b — the Context block
# ---------------------------------------------------------------------------


MULTI_PARAGRAPH_PLAN = """# Build Plan — Context (2026-07-26)

## Status

- [ ] Chunk 01: A

Context: **Chunk 01 complete** — the forward channel shipped and the
generator stopped destroying what it found.

Plan written on a feature branch off develop. Parents: SCN-4H9T.

The last paragraph, which used to be lost.

## Problem, Success, Scope

Prose that is NOT context.
"""


class TestContextBlock:
    def test_multi_paragraph_context_survives_whole(self, tmp_path: Path):
        _write_plan(tmp_path, MULTI_PARAGRAPH_PLAN)
        context = buildplan_refs._parse_build_plan_status(tmp_path)["context"]
        assert context.startswith("**Chunk 01 complete**")
        assert "generator stopped destroying" in context
        assert "Parents: SCN-4H9T." in context
        assert "The last paragraph, which used to be lost." in context

    def test_context_stops_at_the_next_heading(self, tmp_path: Path):
        _write_plan(tmp_path, MULTI_PARAGRAPH_PLAN)
        context = buildplan_refs._parse_build_plan_status(tmp_path)["context"]
        assert "Prose that is NOT context" not in context

    def test_context_stops_at_a_later_chunk_item(self, tmp_path: Path):
        """Context is conventionally last, but a plan that interleaves must not
        swallow its own checklist into the handoff."""
        _write_plan(
            tmp_path,
            "# Build Plan — Interleaved (2026-07-26)\n\n## Status\n\n"
            "- [ ] Chunk 01: A\n\nContext: mid-plan note.\n\n- [ ] Chunk 02: B\n",
        )
        status = buildplan_refs._parse_build_plan_status(tmp_path)
        assert status["context"] == "mid-plan note."
        assert status["current_chunk"] == "Chunk 01: A"

    def test_a_second_context_line_is_kept_as_block_text(self, tmp_path: Path):
        """Block semantics dissolve the first-wins/last-wins question: the first
        `Context:` opens the block and a later one is text inside it, so neither
        wins and nothing is dropped."""
        _write_plan(
            tmp_path,
            "# Build Plan — Two (2026-07-26)\n\n## Status\n\n- [ ] Chunk 01: A\n\n"
            "Context: first note.\n\nContext: second note.\n",
        )
        context = buildplan_refs._parse_build_plan_status(tmp_path)["context"]
        assert "first note." in context
        assert "second note." in context

    def test_handoff_carries_the_whole_block(self, tmp_path: Path):
        _init_repo(tmp_path)
        _write_plan(tmp_path, MULTI_PARAGRAPH_PLAN)
        briefing.generate_session_handoff(tmp_path)
        handoff = (tmp_path / ".prawduct" / ".session-handoff.md").read_text()
        assert "The last paragraph, which used to be lost." in handoff

    def test_briefing_flattens_and_caps_the_block(self, tmp_path: Path):
        """The briefing has a token budget; the handoff is where it lands whole.
        A multi-line block must not blow up the one-line `Context:` field."""
        _init_repo(tmp_path)
        _write_plan(tmp_path, MULTI_PARAGRAPH_PLAN)
        text = briefing.assemble_session_briefing(tmp_path, [])
        context_lines = [ln for ln in text.splitlines() if ln.startswith("Context: ")]
        assert len(context_lines) == 1
        assert len(context_lines[0]) <= len("Context: ") + 200


# ---------------------------------------------------------------------------
# BRF-6K2D — the delete-the-plan nudge is merge-aware
# ---------------------------------------------------------------------------


COMPLETE_PLAN = "# Build Plan — Done (2026-07-26)\n\n## Status\n\n- [x] Chunk 01: A\n"


class TestDeleteNudgeIsMergeAware:
    def test_unmerged_feature_branch_says_keep(self, tmp_path: Path):
        """The plan is session-local and gitignored, so it survives a branch
        switch — the nudge told the user to delete a plan whose work had not
        shipped, which would orphan it."""
        repo = tmp_path / "repo"
        _init_repo(repo, branch="develop")
        _write_state(repo, "base_branch: develop\n")
        _commit(repo, "chore: init")
        _git(repo, "checkout", "-b", "feature/x", "--quiet")
        _write_plan(repo, COMPLETE_PLAN)
        _commit(repo, "feat: land it (Chunk 01)")
        findings = "\n".join(briefing.staleness_scan(repo))
        assert "keep the plan until it merges" in findings
        assert "delete the plan" not in findings

    def test_merged_branch_still_gets_the_delete_nudge(self, tmp_path: Path):
        """Merge-awareness may only ADD a keep-recommendation on positive
        evidence — a plan that really is finished and merged must still be
        cleaned up, or the nudge silently stops working."""
        repo = tmp_path / "repo"
        _init_repo(repo, branch="develop")
        _write_state(repo, "base_branch: develop\n")
        _write_plan(repo, COMPLETE_PLAN)
        _commit(repo, "feat: land it (Chunk 01)")
        findings = "\n".join(briefing.staleness_scan(repo))
        assert "delete the plan" in findings
        assert "keep the plan" not in findings

    def test_foreign_branch_wip_says_keep(self, tmp_path: Path):
        """The reported repro: a plan surviving a switch onto the base branch,
        with project-state.yaml still recording work on the feature branch."""
        repo = tmp_path / "repo"
        _init_repo(repo, branch="develop")
        _write_state(
            repo,
            "base_branch: develop\n"
            "work_in_progress:\n  feature/elsewhere:\n    description: unshipped work\n",
        )
        _write_plan(repo, COMPLETE_PLAN)
        _commit(repo, "feat: land it (Chunk 01)")
        findings = "\n".join(briefing.staleness_scan(repo))
        assert "keep the plan until it merges" in findings

    def test_non_git_directory_fails_toward_the_ordinary_nudge(self, tmp_path: Path):
        _write_plan(tmp_path, COMPLETE_PLAN)
        assert briefing._plan_work_possibly_unmerged(
            tmp_path, tmp_path / ".prawduct"
        ) == (False, "")
