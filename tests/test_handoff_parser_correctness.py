"""Build-plan read-path correctness — the parse that feeds the session handoff.

Four independent wrong-output defects were reproduced against this repo's own
live build plan (SCN-4H9T, BLD-7K3Q), all in the path from build-plan Status to
``.session-handoff.md``:

* a completed plan was reported as the next session's active ``**Task**`` —
  ``staleness_scan`` applied a done-predicate and ``_get_active_work`` read the
  *identical* parse without one;
* the current chunk was read as "first ``- [ ]``" against Status checkboxes that
  were a derived view flipping only at release, so it was Chunk 01 forever;
* a frontmatter-style plan (no ``# Build Plan`` H1) produced no description, and
  description is the sole key gating the handoff's whole Work In Progress
  section, so the section silently vanished;
* ``Context:`` was read as one physical line, truncating the multi-paragraph
  block ``building.md`` calls "the cross-session handoff".

Real ``git init`` repos throughout: the defects survived unit-level correctness
for months precisely because nothing exercised the real path.

The second defect was fixed twice. First by deriving progress from git commits
when the checkboxes could not be trusted — two readings of one question, with a
precedence between them. Then by removing the reason for the second reading: the
derived view is retired and a ticked box is a statement the builder made. What
remains from the git era is a **report**, not a reading —
``unticked_committed_chunk_notice`` — because the single reading is only as good
as the ticking, and a chunk whose work is committed under an empty box is the way
back into exactly this defect.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib import briefing, buildplan_refs, critic_mode, gates, plan_index  # noqa: E402


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


# A plan mid-flight under the single reading: chunks 01-03 ticked by the builder,
# 04 open. `- [x]` is a statement, not a regenerated value.
LIVE_PLAN = """---
artifact: build-plan
scope: session-handoff-continuity
---

## Status

- [x] Chunk 01: The forward channel
- [x] Chunk 02: Parser correctness
- [x] Chunk 03: Proactive close
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


def _live_repo(tmp_path: Path, *, commit_chunk: int | None = 4) -> Path:
    """Chunks 01-03 ticked; 04 open and — by default — already COMMITTED.

    That combination is deliberate and makes the fixture discriminating rather
    than merely representative. Every consumer must answer "04", which is what
    the boxes say; the retired git-derived reading would have counted 04 as done
    too and answered "nothing current". So a consumer that quietly reintroduced a
    commit-derived reading fails here instead of agreeing by coincidence.

    It is also the exact state the tripwire exists to report, so one fixture
    carries both halves of the contract: the boxes decide, and the discrepancy is
    reported rather than silently resolved.
    """
    repo = tmp_path / "repo"
    _init_repo(repo, branch="develop")
    _write_state(repo, "base_branch: develop\n")
    _write_plan(repo, LIVE_PLAN)
    _commit(repo, "chore: plan")
    _git(repo, "checkout", "-b", "feature/session-handoff-continuity", "--quiet")
    if commit_chunk is not None:
        _commit(repo, f"feat(continuity): land it (Chunk 0{commit_chunk})")
    return repo


# Defect 4 — one reading of chunk progress, at EVERY consumer
# ---------------------------------------------------------------------------


class TestSingleReadingCurrentChunk:
    """Chunks 01-03 ticked, 04 open and committed. Every consumer must say 04."""

    def test_parse_reports_the_chunk_actually_in_flight(self, tmp_path: Path):
        repo = _live_repo(tmp_path)
        status = buildplan_refs._parse_build_plan_status(repo)
        assert status["current_chunk"] == "Chunk 04: The Critic summary"

    def test_current_chunk_id(self, tmp_path: Path):
        repo = _live_repo(tmp_path)
        assert buildplan_refs._current_chunk_id_from_status(repo) == "04"

    def test_verify_chunk_refs_grades_the_right_chunk(self, tmp_path: Path):
        """BLD-7K3Q: the gate reported `ok: chunk 01` for a whole branch while
        chunks 02..N went unverified — silently, and green.

        Asserted POSITIVELY. A `"01" not in stdout` check passes on empty
        stdout, which is what a `cannot-verify` exit produces — so it would
        have gone green against the pre-fix code too.
        """
        repo = _live_repo(tmp_path)
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

    def test_progress_counts_ticked_chunks(self, tmp_path: Path):
        repo = _live_repo(tmp_path)
        progress = buildplan_refs.resolve_chunk_progress(repo)
        assert (progress.complete, progress.current_id) == (3, "04")

    def test_progress_is_a_pure_function_of_the_plan_text(self, tmp_path: Path):
        """The collapse's structural claim: no git, no repo state, no I/O beyond
        reading the plan. Asserted by making every subprocess call raise — a
        reading that still consults git cannot survive it."""
        repo = _live_repo(tmp_path)

        def _boom(*_a, **_k):
            raise AssertionError("chunk progress must not shell out")

        import unittest.mock

        with unittest.mock.patch.object(buildplan_refs.subprocess, "run", _boom):
            progress = buildplan_refs.resolve_chunk_progress(repo)
        assert (progress.complete, progress.current_id) == (3, "04")

    def test_mode_inference_routes_through_the_single_owner(
        self, tmp_path: Path, monkeypatch
    ):
        """`infer_mode` must not re-derive which chunk is current.

        Asserted by DEPENDENCE, not by agreement: two functions returning "04"
        is equally true of an `infer_mode` that derives "04" for itself. So
        redirect the owner and require `infer_mode`'s answer to move with it.
        Chunk 04 declares `**Critic mode:** final`; Chunk 02 declares none, so
        the plan-override appears only when 04 is the resolved chunk.
        """
        repo = _live_repo(tmp_path)
        mode, rationale = critic_mode.infer_mode(repo)
        assert (mode, rationale) == ("final", "plan-override: final")

        redirected = buildplan_refs.resolve_chunk_progress(repo)._replace(
            current_id="02", current_text="Chunk 02: Parser correctness"
        )
        monkeypatch.setattr(
            critic_mode.buildplan_refs,
            "resolve_chunk_progress",
            # Accepts the plan-path argument `infer_mode` now passes (it resolves
            # this branch's plan rather than trusting the pointer). The stub
            # ignores it: what is under test is that the ANSWER comes from the
            # owner, not which file the owner was pointed at.
            lambda _d, _plan_path=None: redirected,
        )
        assert critic_mode.infer_mode(repo)[1] != "plan-override: final", (
            "infer_mode ignored the resolver — it is re-deriving which chunk is "
            "current for itself"
        )

    def test_briefing_resume_line_names_the_right_chunk(self, tmp_path: Path):
        repo = _live_repo(tmp_path)
        text = briefing.assemble_session_briefing(repo, [])
        assert "Resume: Chunk 04: The Critic summary" in text

    def test_handoff_names_the_right_chunk(self, tmp_path: Path):
        repo = _live_repo(tmp_path)
        briefing.generate_session_handoff(repo)
        handoff = (repo / ".prawduct" / ".session-handoff.md").read_text()
        assert "**Current chunk**: Chunk 04: The Critic summary" in handoff

    def test_all_boxes_ticked_clears_the_current_chunk(self, tmp_path: Path):
        repo = _live_repo(tmp_path)
        _write_plan(repo, LIVE_PLAN.replace("- [ ] Chunk", "- [x] Chunk"))
        status = buildplan_refs._parse_build_plan_status(repo)
        assert "current_chunk" not in status
        assert buildplan_refs.build_plan_is_complete(status) is True

    def test_an_unchecked_non_chunk_item_still_blocks_completion(self, tmp_path: Path):
        """A Status section may hold items that name no chunk (a plain to-do).
        Such an item is done iff its box is ticked — the walk covers EVERY Status
        item, not just the chunk-shaped ones. Skipping them once made a plan with
        every chunk done read as COMPLETE while an unchecked item sat right
        there, which retires a live plan and blanks the handoff's work section.
        """
        repo = _live_repo(tmp_path)
        _write_plan(
            repo,
            LIVE_PLAN.replace(
                "- [ ] Chunk 04: The Critic summary",
                "- [x] Chunk 04: The Critic summary\n- [ ] Retire the shim",
            ),
        )
        status = buildplan_refs._parse_build_plan_status(repo)
        assert buildplan_refs.build_plan_is_complete(status) is False
        assert status["current_chunk"] == "Retire the shim"

    def test_a_status_of_only_non_chunk_items_is_not_complete(self, tmp_path: Path):
        """The degenerate end of the same defect: nothing chunk-shaped to walk,
        so a chunk-only walk returned "0 complete, nothing current" and the
        done-predicate read that as *finished* with zero work done."""
        content = LIVE_PLAN
        for n in range(1, 5):
            content = re.sub(rf"- \[[ x]\] Chunk 0{n}: .*", f"- [ ] Task {n}", content)
        repo = _live_repo(tmp_path)
        _write_plan(repo, content)
        status = buildplan_refs._parse_build_plan_status(repo)
        assert buildplan_refs.build_plan_is_complete(status) is False
        assert status["current_chunk"] == "Task 1"

    def test_a_ticked_chunk_after_the_current_one_still_counts_as_done(
        self, tmp_path: Path
    ):
        """Done-ness is per-item and non-contiguous. The retired git reading
        reported a bare COUNT with the predicate locked in a closure, so callers
        had to approximate with the roster prefix before `current_id` and
        under-reported a ticked chunk sitting after it. With one reading the flag
        is exact, so this must be counted, not approximated."""
        repo = _live_repo(tmp_path)
        _write_plan(
            repo,
            LIVE_PLAN.replace("- [x] Chunk 03", "- [ ] Chunk 03").replace(
                "- [ ] Chunk 04", "- [x] Chunk 04"
            ),
        )
        progress = buildplan_refs.resolve_chunk_progress(repo)
        assert (progress.complete, progress.current_id) == (3, "03")
        assert buildplan_refs._completed_chunk_ids(
            (repo / ".prawduct" / "artifacts" / "build-plan.md").read_text()
        ) == {"1", "2", "4"}


class TestUntickedCommittedChunkTripwire:
    """DV7: the single reading is only as good as the ticking, so a chunk whose
    work is committed under an empty box is REPORTED — never silently resolved.

    This is the branch's own opening failure, generalized: a plan said a chunk
    was not done, every consumer believed it, and the next session inherited the
    false signal as testimony because a handoff is written by an agent reading
    the same surface.
    """

    def test_it_fires_and_names_the_chunk_and_the_commit(self, tmp_path: Path):
        repo = _live_repo(tmp_path)
        notice = buildplan_refs.unticked_committed_chunk_notice(repo)
        assert notice is not None
        assert buildplan_refs.UNTICKED_CHUNK_TOKEN in notice
        assert "Chunk 04: The Critic summary" in notice
        assert "land it (Chunk 04)" in notice, (
            "the notice must cite the commit — a report nobody can check is a "
            f"report nobody acts on (got {notice!r})"
        )

    def test_it_is_silent_when_the_boxes_match_the_commits(self, tmp_path: Path):
        repo = _live_repo(tmp_path)
        _write_plan(repo, LIVE_PLAN.replace("- [ ] Chunk 04", "- [x] Chunk 04"))
        assert buildplan_refs.unticked_committed_chunk_notice(repo) is None

    def test_it_is_silent_when_no_commit_names_a_chunk(self, tmp_path: Path):
        repo = _live_repo(tmp_path, commit_chunk=None)
        assert buildplan_refs.unticked_committed_chunk_notice(repo) is None

    def test_it_never_writes(self, tmp_path: Path):
        """Reporting-only, asserted rather than asserted-in-prose: the plan on
        disk must be byte-identical after the notice fires. A tripwire that
        'helpfully' ticked the box would be a model in a fact's write path."""
        repo = _live_repo(tmp_path)
        plan = repo / ".prawduct" / "artifacts" / "build-plan.md"
        before = plan.read_bytes()
        assert buildplan_refs.unticked_committed_chunk_notice(repo) is not None
        assert plan.read_bytes() == before

    def test_it_does_not_change_what_any_consumer_reads(self, tmp_path: Path):
        """The report must not become a second reading by the back door: with the
        tripwire firing on 04, the current chunk is STILL 04 (the boxes), not
        "nothing current" as a commit-derived reading would say."""
        repo = _live_repo(tmp_path)
        assert buildplan_refs.unticked_committed_chunk_notice(repo) is not None
        assert buildplan_refs.resolve_chunk_progress(repo).current_id == "04"

    def test_the_report_is_ordered_numerically_and_skips_alpha_ids(
        self, tmp_path: Path
    ):
        """Two properties, one fixture, because the second explains the first.

        Chunks are listed in NUMERIC order (`10` after `2`, not lexically), and
        the sort key is total on its domain — the report is built from a set, so
        a key with ties would leave tied ids in set-iteration order and the same
        repo could print the same finding two ways on two runs.

        The domain is digit strings only, and that is the second assertion: a
        `Chunk A` is never reported, because `_CHUNK_COMMIT_RE` captures `\\d+`
        and no commit subject can match one. Pinned as a KNOWN GAP rather than
        left to be discovered — a plan on alpha chunk ids gets no tripwire
        coverage, and a future widening of the commit pattern must widen the
        sort key with it.
        """
        repo = tmp_path / "repo"
        _init_repo(repo, branch="develop")
        _write_state(repo, "base_branch: develop\n")
        _write_plan(
            repo,
            "---\nartifact: build-plan\nscope: ordering\n---\n\n## Status\n\n"
            "- [ ] Chunk 02: two\n- [ ] Chunk 10: ten\n- [ ] Chunk 01: one\n"
            "- [ ] Chunk B: bee\n- [ ] Chunk A: ay\n",
        )
        _commit(repo, "chore: plan")
        _git(repo, "checkout", "-b", "feature/x", "--quiet")
        for cid in ("01", "02", "10", "A", "B"):
            _commit(repo, f"feat(ordering): land it (Chunk {cid})")

        notice = buildplan_refs.unticked_committed_chunk_notice(repo)
        assert notice is not None
        listed = [
            line.split("Chunk ", 1)[1].split(":", 1)[0]
            for line in notice.splitlines()
            if line.startswith("  - ")
        ]
        assert listed == ["01", "02", "10"], notice
        assert "Chunk A" not in notice and "Chunk B" not in notice, (
            "an alpha chunk id was reported — if the commit pattern widened to "
            "accept one, `flagged`'s `key=int` now raises on it"
        )

    def test_a_foreign_plans_chunk_ids_are_not_reported(self, tmp_path: Path):
        """Chunk ids are PER-PLAN (SCN-5B8Q R-2/R-7): a sibling plan's
        `(Chunk 02)` must not produce a report about THIS plan's chunk 02.
        Scoping by conventional-commit scope is what stops it."""
        repo = tmp_path / "repo"
        _init_repo(repo, branch="develop")
        _write_state(repo, "base_branch: develop\n")
        _write_plan(
            repo,
            "---\nartifact: build-plan\nscope: boundary-events\n---\n\n"
            "## Status\n\n"
            "- [x] Chunk 01: Split the acts\n- [ ] Chunk 02: Handoff vintage\n",
        )
        _commit(repo, "chore: plan")
        _git(repo, "checkout", "-b", "feature/x", "--quiet")
        _commit(repo, "fix(boundary-events): split the acts (Chunk 01)")
        _commit(repo, "feat(other-plan): unrelated work (Chunk 02)")

        notice = buildplan_refs.unticked_committed_chunk_notice(repo)
        assert notice is None, (
            f"a foreign plan's (Chunk 02) was reported against this plan: {notice!r}"
        )

    def test_an_unmatched_plan_scope_keeps_the_unscoped_reading(self, tmp_path: Path):
        """Scope tags are a convention, not a guarantee — on the branch that
        surfaced this, the continuity plan's commits said `session-continuity`
        while its frontmatter said `session-handoff-continuity`. A strict filter
        would erase the plan's whole signal, so when nothing matches the scope,
        the unscoped reading survives and the tripwire still reports."""
        repo = tmp_path / "repo"
        _init_repo(repo, branch="develop")
        _write_state(repo, "base_branch: develop\n")
        _write_plan(repo, LIVE_PLAN)  # scope: session-handoff-continuity
        _commit(repo, "chore: plan")
        _git(repo, "checkout", "-b", "feature/x", "--quiet")
        _commit(repo, "fix(session-continuity): the critic summary (Chunk 04)")

        notice = buildplan_refs.unticked_committed_chunk_notice(repo)
        assert notice is not None and "Chunk 04" in notice

    def test_a_git_failure_degrades_to_silence_not_to_a_claim(
        self, tmp_path: Path, monkeypatch
    ):
        """A raising git call (absent binary, timeout) must produce no report.
        The honest answer when the evidence cannot be read is nothing at all."""
        repo = _live_repo(tmp_path)

        def _boom(*_a, **_k):
            raise subprocess.TimeoutExpired(cmd="git", timeout=10)

        monkeypatch.setattr(buildplan_refs.subprocess, "run", _boom)
        assert buildplan_refs.unticked_committed_chunk_notice(repo) is None


class TestGateSemanticsUnchanged:
    """Success criterion 6 of the governing plan: no gate semantics change.

    The gate trigger reads the CHECKBOXES and must never read a commit-derived
    signal. The gate asks "is there still governed work", and a chunk's last
    commit lands BEFORE its Critic pass and its reflection. Deriving the gate
    from git switched the blocking reflection and Critic gates off for the entire
    complete-but-unmerged window — the PR-fix and finding-resolution sessions.

    The git-derived progress reading that caused it is gone, but the tripwire is
    a commit-derived signal still in the tree, and it reports precisely the state
    in which this gate must keep saying "governed". So the pin stays.
    """

    def test_gate_armed_mid_branch(self, tmp_path: Path):
        repo = _live_repo(tmp_path)
        assert gates._has_active_build_plan_file(repo / ".prawduct") is True

    def test_gate_stays_armed_through_the_complete_but_unmerged_window(
        self, tmp_path: Path
    ):
        """Every chunk COMMITTED but the last box not yet ticked — the window in
        which the Critic pass and the reflection still have to happen. This is
        also when the tripwire is firing, which is the temptation to disarm."""
        repo = _live_repo(tmp_path)
        assert buildplan_refs.unticked_committed_chunk_notice(repo) is not None
        assert gates._has_active_build_plan_file(repo / ".prawduct") is True

    def test_gate_disarms_once_every_box_is_ticked(self, tmp_path: Path):
        repo = _live_repo(tmp_path)
        _write_plan(repo, LIVE_PLAN.replace("- [ ] Chunk", "- [x] Chunk"))
        assert gates._has_active_build_plan_file(repo / ".prawduct") is False

    def test_a_git_failure_leaves_the_parse_and_the_gate_intact(
        self, tmp_path: Path, monkeypatch
    ):
        """Collapsing the parse to `{}` on a transient git hiccup would blank the
        handoff's work section AND read as "no build plan" to the gates —
        authority failing OPEN. Progress no longer consults git at all, so this
        now asserts the stronger property: a raising git call changes nothing.
        """
        repo = _live_repo(tmp_path)

        def _boom(*_a, **_k):
            raise subprocess.TimeoutExpired(cmd="git", timeout=10)

        monkeypatch.setattr(buildplan_refs.subprocess, "run", _boom)
        status = buildplan_refs._parse_build_plan_status(repo)
        assert status["description"] == "session-handoff-continuity"
        assert status["current_chunk"] == "Chunk 04: The Critic summary"
        assert "Chunks 01-03 shipped." in status["context"]
        assert gates._has_active_build_plan_file(repo / ".prawduct") is True


class TestOneCurrentChunkImplementation:
    """The sweep's structural guarantee: the derivation has ONE home, and no
    consumer re-derives "first unchecked" for itself. CRT-7B4M fixed this at one
    consumer and the defect recurred at two more — the recurrence is the reason
    this pin exists."""

    # `_git_aware_progress` was a member until the git-derived progress reading
    # was retired; it is deleted, so asserting `buildplan_refs` owns it would be
    # a pin on a name that no longer exists. The three survivors still belong
    # here: `_commits_ahead_of_base` is used by `critic_mode` and the rest feed
    # the unticked-chunk tripwire, so the "one home" rule still has subjects.
    MOVED_OUT_OF_CRITIC_MODE = (
        "_commits_ahead_of_base",
        "_committed_chunk_ids",
        "_CHUNK_COMMIT_RE",
    )

    def test_the_retired_derivation_is_really_gone(self):
        """The git-derived progress reading must not come back anywhere.

        Its absence is what makes the checkbox the single reading; a module
        quietly reintroducing it would restore the precedence this work removed
        without any test above going red.
        """
        for module in (buildplan_refs, critic_mode, gates, briefing):
            assert "_git_aware_progress" not in vars(module), (
                f"{module.__name__} defines _git_aware_progress — chunk progress "
                "has ONE reading (the Status checkboxes), and a second derived "
                "reading is the defect shape this work removed."
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
        The one module that used to be exempt — the derived-view regenerator,
        which rewrote Status by line index rather than reading it — no longer
        exists, so the rule is now without exception.
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


# ---------------------------------------------------------------------------
# A non-UTF-8 plan degrades, at each reader that has to survive one
# ---------------------------------------------------------------------------


class TestNonUtf8PlanDegrades:
    """The behavioral half of `tests/preferences/test_build_plan_decoding.py`.

    That pin is grep-level — it asserts each read names UTF-8 and each guard
    spells `UnicodeDecodeError`. It cannot assert the designed degradation
    actually *runs*, so a refactor that keeps the token and breaks the return
    would pass it. Shape and behavior are different claims; the gap between
    them is where this class lived for three review rounds.
    """

    UNDECODABLE = (
        b"# Build Plan \xff\xfe Bad Bytes (2026-07-27)\n\n"
        b"## Status\n\n- [ ] Chunk 01: A\n\n"
        b"### Chunk 01: A\n- **Type:** code\n"
    )

    def _write_undecodable_plan(self, project_dir: Path) -> Path:
        plan = project_dir / ".prawduct" / "artifacts" / "build-plan.md"
        plan.parent.mkdir(parents=True, exist_ok=True)
        plan.write_bytes(self.UNDECODABLE)
        return plan

    def test_chunk_refs_returns_its_error_instead_of_raising(self, tmp_path: Path):
        """The reachable symptom: `verify-chunk-refs --chunk <id>` bypasses the
        degrading resolver and calls this directly, so a raise here becomes a
        traceback where the CLI documents a `cannot-verify:` exit."""
        self._write_undecodable_plan(tmp_path)
        refs = buildplan_refs._parse_build_plan_chunk_refs(tmp_path / ".prawduct", "01")
        assert "unreadable build-plan" in refs["error"]

    def test_verify_chunk_refs_cli_reports_rather_than_tracebacks(self, tmp_path: Path):
        """End-to-end, because the boundary's recorded error model says no
        internal stack trace may cross it."""
        _init_repo(tmp_path)
        self._write_undecodable_plan(tmp_path)
        proc = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "bin" / "prawduct-hook"),
                "verify-chunk-refs",
                "--chunk",
                "01",
            ],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            env={**_git_env(tmp_path), "CLAUDE_PROJECT_DIR": str(tmp_path)},
            timeout=30,
        )
        assert proc.returncode == 1, proc.stdout + proc.stderr
        assert "cannot-verify" in proc.stderr, proc.stdout + proc.stderr
        assert "Traceback" not in proc.stderr, proc.stderr

    def test_duplicate_scope_diagnosis_survives_an_unreadable_plan(
        self, tmp_path: Path
    ):
        """`duplicate_scope_errors` is the twin of `build_scope_to_plan_map` and
        was the last reader still on the narrow guard — called bare with no
        global handler, so one bad file tracebacked out of its caller. Its
        duplicate-scope branch had no coverage at all, which is how a rename into
        it could have gone unnoticed.

        The check outlived the derived-view regenerator that used to host it: it
        guards frontmatter `scope:`, a field that survives, so it was rehomed to
        `plan_index` and is now reached through the release gate rather than
        dying with its old caller."""
        artifacts = tmp_path / ".prawduct" / "artifacts"
        artifacts.mkdir(parents=True)
        self._write_undecodable_plan(tmp_path)
        for name in ("build-plan-a.md", "build-plan-b.md"):
            (artifacts / name).write_text(
                "---\nscope: dup\n---\n\n## Status\n\n- [ ] Chunk 01: A\n",
                encoding="utf-8",
            )
        errors = plan_index.duplicate_scope_errors(artifacts)
        assert any(
            "duplicate scope=" in message and "build-plan-b.md" in message
            for _scope, message in errors
        ), errors
