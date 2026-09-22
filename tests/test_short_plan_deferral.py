"""A short plan owes one boundary review, not one per chunk (#292).

The deferral is a REMOVAL of a control — the per-chunk review on a plan of at
most ``SHORT_PLAN_MAX_CHUNKS`` chunks touching no risk surface — and #292 named
the guardrail it must ship with: a regression test proving a NON-eligible plan
(more chunks, or a risk surface touched) still gets per-chunk review and still
blocks at Stop. The retired PR trivial fast-path shipped with zero adversarial
coverage and failed for exactly that reason, so the non-eligible half of this
file is the load-bearing half; the eligible half pins what the deferral buys.

Three mechanisms, one predicate (``critic_mode.short_plan_deferral``):

- ``infer_mode`` answers ``deferred`` — output-only, dispatching nothing — on an
  eligible plan with code in flight, and ``cumulative`` as ever once the tree
  is clean, so the boundary review is inferred exactly where it always was.
- The Stop hook's Critic gate WARNS instead of blocking on an eligible plan's
  non-final chunk, naming the boundary review, and delivers the warning on the
  one channel the harness reads at exit 0 (a JSON ``systemMessage`` +
  ``additionalContext`` on stdout); on the last chunk it blocks as ever and
  says what the boundary review is.
- ``check-cumulative-critic`` is untouched: the plan's acceptance criterion is
  that one ``cumulative`` fact spanning merge-base…HEAD passes the PR gate on
  its own, and a control here shows the gate can still fail.

Fixtures are REAL git repos: the predicate reads merge-base and the branch's
changed paths, and the Stop harness's tree capture has to agree with them.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from conftest import SHAPED_REFLECTION
from lib import buildplan_refs, critic_mode, evidence, gates
from lib.critic_mode import infer_mode
from test_critic_mode_inference import (
    _checkout_new_branch,
    _commit,
    _git,
    _init_repo,
    _write,
    _write_build_plan_with_chunks,
    _write_findings,
)

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"

_MODE_CUMULATIVE = "cumulative (bundle review, ready for merge)"
_MODE_CHUNK = "chunk (lighter pass, not ready for push)"
_GENERIC_BLOCK = "CRITIC REVIEW: no composed review coverage"


def _short_plan_branch(
    tmp_path: Path,
    *,
    chunks: int = 3,
    committed: tuple[str, ...] = (),
    chunk_modes: dict[str, str] | None = None,
    state_extra: str = "",
    dirty: bool = True,
    dirty_path: str = "src/wip.py",
    branch: str | None = "feature/short",
    committed_paths: dict[str, str] | None = None,
    plan_committed: bool = False,
) -> Path:
    """A real repo whose branch builds a ``chunks``-chunk plan.

    ``committed`` names the chunk ids already landed (each gets a commit and a
    tick), ``dirty`` leaves the current chunk's work uncommitted, ``branch``
    ``None`` stays on ``main`` itself. ``state_extra`` is appended to
    ``project-state.yaml`` — a ``risk_surfaces:`` block, or a different
    ``base_branch:``. ``.prawduct/`` is gitignored so session markers never
    read as work — unless ``plan_committed``, which tracks ``.prawduct/`` the
    way a real repo does (only its dot-files ignored) and lands each landed
    chunk's tick IN that chunk's commit, so HEAD's plan and the working tree's
    can be told apart.
    """
    _init_repo(tmp_path, branch="main")
    _write(tmp_path, ".gitignore", ".prawduct/.*\n" if plan_committed else ".prawduct/\n")
    _write(tmp_path, "README.md", "x\n")
    prawduct = tmp_path / ".prawduct"
    prawduct.mkdir(parents=True, exist_ok=True)
    (prawduct / "project-state.yaml").write_text("base_branch: main\n" + state_extra)
    ticked = {cid.lstrip("0") or "0" for cid in committed}

    def _items(ticked_ids: set[str]) -> list[tuple[str, str]]:
        return [
            ("x" if str(i).lstrip("0") in ticked_ids else " ", f"Chunk {i:02d}: step {i}")
            for i in range(1, chunks + 1)
        ]

    if plan_committed:
        _write_build_plan_with_chunks(prawduct, _items(set()), chunk_modes)
        _commit(tmp_path, "initial")
    else:
        _commit(tmp_path, "initial")
        _write_build_plan_with_chunks(prawduct, _items(ticked), chunk_modes)
    if branch is not None:
        _checkout_new_branch(tmp_path, branch)
    committed_paths = committed_paths or {}
    landed: set[str] = set()
    for cid in committed:
        rel = committed_paths.get(cid, f"src/chunk_{cid}.py")
        _write(tmp_path, rel, f"# chunk {cid}\n")
        if plan_committed:
            landed.add(cid.lstrip("0") or "0")
            _write_build_plan_with_chunks(prawduct, _items(landed), chunk_modes)
        _commit(tmp_path, f"feat: land it (Chunk {cid})")
    if dirty:
        _write(tmp_path, dirty_path, "# work in progress\n")
    return prawduct


def _tick_in_working_tree(prawduct: Path, chunk_id: str) -> None:
    """Tick one chunk's Status box on disk and commit nothing — the state a
    builder is in between finishing a chunk and committing it."""
    plan = prawduct / "artifacts" / "build-plan.md"
    text = plan.read_text()
    needle = f"- [ ] Chunk {chunk_id}:"
    assert needle in text, text
    plan.write_text(text.replace(needle, f"- [x] Chunk {chunk_id}:"))


def _deferral(repo: Path):
    prawduct = repo / ".prawduct"
    plan = buildplan_refs.resolve_branch_plan(repo, prawduct)
    progress = buildplan_refs.resolve_chunk_progress(repo, plan.path)
    return critic_mode.short_plan_deferral(repo, prawduct, plan, progress)


# ---------------------------------------------------------------------------
# The guardrail #292 named: non-eligible plans are untouched
# ---------------------------------------------------------------------------


class TestNonEligiblePlansStillReviewPerChunk:
    """Every shape the deferral must NOT cover, each inferring the inner-stage
    review it always did. Failing any of these means a skip-gate widened."""

    def test_four_chunks_still_infer_chunk(self, tmp_path: Path):
        _short_plan_branch(tmp_path, chunks=4)
        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "chunk", rationale
        assert rationale.startswith("rule-4 chunk:")
        d = _deferral(tmp_path)
        assert not d.defers
        assert "4 chunks" in d.reason and "at most 3" in d.reason

    def test_a_dirty_risk_surface_path_still_infers_chunk(self, tmp_path: Path):
        _short_plan_branch(
            tmp_path,
            state_extra="risk_surfaces:\n  - src/payments/\n",
            dirty_path="src/payments/ledger.py",
        )
        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "chunk", rationale
        d = _deferral(tmp_path)
        assert not d.defers
        assert "risk surface" in d.reason and "src/payments/ledger.py" in d.reason

    def test_a_risk_surface_touched_by_an_earlier_chunk_still_counts(self, tmp_path: Path):
        """The predicate reads the BRANCH's changed paths, committed ones
        included — a chunk that landed on a surface two commits ago keeps the
        plan out, even though the current chunk's file is elsewhere."""
        _short_plan_branch(
            tmp_path,
            committed=("01",),
            committed_paths={"01": "src/payments/ledger.py"},
            state_extra="risk_surfaces:\n  - src/payments/\n",
            dirty_path="src/other.py",
        )
        mode, _ = infer_mode(tmp_path, None)
        assert mode == "chunk"
        assert "src/payments/ledger.py" in _deferral(tmp_path).reason

    def test_a_critic_mode_on_any_chunk_opts_the_plan_out(self, tmp_path: Path):
        """Chunk 02 declares a mode while chunk 01 is current: the CURRENT
        chunk has no override, so inference runs — and answers `chunk`, not
        `deferred`, because a declaration anywhere is the plan opting out."""
        _short_plan_branch(tmp_path, chunk_modes={"02": "final"})
        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "chunk", rationale
        d = _deferral(tmp_path)
        assert not d.defers
        assert "Chunk 02 declares Critic mode: final" in d.reason

    def test_the_last_chunk_of_an_opted_out_plan_still_infers_final(self, tmp_path: Path):
        """Rule 3's last-chunk arm is untouched wherever the deferral does not
        apply — here it does not, because chunk 01 declared a mode."""
        _short_plan_branch(
            tmp_path, committed=("01", "02"), chunk_modes={"01": "chunk"}
        )
        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "final", rationale
        assert "rule-3" in rationale

    def test_work_on_the_base_branch_itself_has_no_boundary(self, tmp_path: Path):
        """On `main` itself merge-base…HEAD is empty: there is no boundary
        review to defer to, so deferring would defer every chunk to nothing."""
        _short_plan_branch(tmp_path, branch=None)
        mode, _ = infer_mode(tmp_path, None)
        assert mode == "chunk"
        d = _deferral(tmp_path)
        assert not d.defers
        assert "base branch main itself" in d.reason

    def test_an_unresolvable_base_fails_closed(self, tmp_path: Path):
        _short_plan_branch(tmp_path, state_extra="")
        (tmp_path / ".prawduct" / "project-state.yaml").write_text(
            "base_branch: nowhere\n"
        )
        d = _deferral(tmp_path)
        assert not d.defers
        assert "no base branch resolves" in d.reason
        assert infer_mode(tmp_path, None)[0] == "chunk"

    def test_unparseable_risk_surfaces_fail_closed(self, tmp_path: Path):
        """Flow style is the shape `read_declared_surfaces` refuses; a refusal
        must read as "touched", never as "no surfaces" (the direction that
        relaxes a gate on a syntax slip)."""
        _short_plan_branch(tmp_path, state_extra="risk_surfaces: [src/]\n")
        d = _deferral(tmp_path)
        assert not d.defers
        assert "cannot parse" in d.reason
        assert infer_mode(tmp_path, None)[0] == "chunk"

    def test_a_finished_plan_defers_nothing(self, tmp_path: Path):
        _short_plan_branch(tmp_path, committed=("01", "02", "03"), dirty=False)
        d = _deferral(tmp_path)
        assert not d.defers and "nothing left to defer" in d.reason

    def test_deferred_is_never_an_input_token(self, tmp_path: Path):
        """`deferred` is output-only: typed as an argument it is unrecognized
        and inference runs (on a non-eligible plan, to `chunk`)."""
        assert critic_mode.MODE_DEFERRED not in critic_mode._VALID_ARG_MODES
        _short_plan_branch(tmp_path, chunks=4)
        mode, rationale = infer_mode(tmp_path, "deferred")
        assert mode == "chunk" and "explicit-args" not in rationale


# ---------------------------------------------------------------------------
# What the deferral buys on an eligible plan
# ---------------------------------------------------------------------------


class TestEligiblePlanDefers:
    def test_non_final_chunk_with_code_in_flight_is_deferred(self, tmp_path: Path):
        _short_plan_branch(tmp_path)
        mode, rationale = infer_mode(tmp_path, None)
        assert mode == critic_mode.MODE_DEFERRED
        assert rationale.startswith("short-plan deferral:")
        assert "commit this chunk and carry on" in rationale
        assert "`cumulative`" in rationale
        # The way back is named, because a deferral nobody can decline is a gate.
        assert "/prawduct:critic chunk" in rationale
        assert "Critic mode:" in rationale
        d = _deferral(tmp_path)
        assert d.defers and not d.last_chunk and d.total == 3
        assert "no risk-surface paths" in d.reason or "no risk surfaces" in d.reason

    def test_a_tick_made_but_not_committed_belongs_to_the_chunk_just_finished(self, tmp_path: Path):
        """Chunk 02 of 3 built, ticked on disk, not committed: the session's
        work is chunk 02, not the last chunk — reading the working-tree tick
        would call it the last and demand the boundary review one chunk early
        (chunk 03 then owing a second one). What turns this red: computing
        ``last_chunk`` from the working tree's ticks instead of HEAD's."""
        prawduct = _short_plan_branch(tmp_path, committed=("01",), plan_committed=True)
        _tick_in_working_tree(prawduct, "02")
        plan = buildplan_refs.resolve_branch_plan(tmp_path, prawduct)
        # Precondition: the two trees really disagree, so the subject is reached.
        assert buildplan_refs.resolve_chunk_progress(tmp_path, plan.path).complete == 2
        head = buildplan_refs.committed_chunk_progress(tmp_path, plan.path)
        assert head is not None and head.complete == 1
        d = _deferral(tmp_path)
        assert d.defers, d.reason
        assert d.last_chunk is False
        # And once chunk 02's tick is committed, chunk 03's work IS the last chunk.
        _commit(tmp_path, "feat: land it (Chunk 02)")
        _write(tmp_path, "src/wip3.py", "# chunk 03 in flight\n")
        assert _deferral(tmp_path).last_chunk is True

    def test_last_chunk_is_the_boundary_review_not_a_final(self, tmp_path: Path):
        """`Type: cumulative-final` semantics without the declaration: rule 3
        would have inferred `final` here; the deferral says commit, then the
        cumulative that IS this chunk's review."""
        _short_plan_branch(tmp_path, committed=("01", "02"))
        mode, rationale = infer_mode(tmp_path, None)
        assert mode == critic_mode.MODE_DEFERRED, rationale
        assert "this is the last chunk" in rationale
        assert "infers `cumulative`" in rationale
        assert "no separate `final`" in rationale
        assert _deferral(tmp_path).last_chunk

    def test_clean_tree_still_infers_the_boundary_review(self, tmp_path: Path):
        """The deferral withholds only inner-stage answers. Once the chunks
        are committed the boundary review is inferred exactly as before —
        which is what the deferral defers TO."""
        _short_plan_branch(tmp_path, committed=("01", "02", "03"), dirty=False)
        # Tick nothing more: the plan is finished as far as Status knows, and
        # a clean tree two commits ahead of main is rule 2's shape.
        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "cumulative", rationale
        assert rationale.startswith("rule-2 cumulative:")

    def test_a_record_only_diff_is_not_deferred(self, tmp_path: Path):
        """No code in flight means no chunk work to defer: rule 4's honest
        answer stands. ONE commit ahead, deliberately — two would let rule 2
        answer first and the conjunct under test would never be reached (the
        first cut of this test survived its own mutant that way). The fixture
        tracks `.prawduct/` for this one case so the record is visible to git."""
        prawduct = _short_plan_branch(tmp_path, dirty=False)
        (tmp_path / ".gitignore").write_text("")
        _commit(tmp_path, "track the records")
        (prawduct / "artifacts" / "build-plan.md").write_text(
            (prawduct / "artifacts" / "build-plan.md").read_text() + "\nContext: edited.\n"
        )
        assert _deferral(tmp_path).defers  # eligible — and still not deferred:
        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "chunk", rationale
        assert rationale.startswith("rule-4 chunk:")

    def test_explicit_mode_beats_the_deferral(self, tmp_path: Path):
        _short_plan_branch(tmp_path)
        mode, rationale = infer_mode(tmp_path, "chunk")
        assert mode == "chunk" and rationale == "explicit-args"

    def test_a_fix_in_progress_still_gets_verify_resolutions(self, tmp_path: Path):
        """Rules 1–2 sit above the deferral: findings a prior review DID
        record (a forced chunk review, say) are still resolved by a verify
        pass, never stranded behind `deferred`."""
        _short_plan_branch(tmp_path, dirty=False)
        _write(tmp_path, "src/wip.py", "# reviewed once\n")
        head = _commit(tmp_path, "feat: chunk 01 first cut")
        _write_findings(
            tmp_path / ".prawduct",
            commit_reviewed=head,
            files_reviewed=["src/wip.py"],
            severity="blocking",
        )
        _write(tmp_path, "src/wip.py", "# fixing the finding\n")
        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "verify-resolutions", rationale

    def test_subcommand_prints_the_deferred_token(self, tmp_path: Path):
        _short_plan_branch(tmp_path)
        env = {
            "HOME": str(tmp_path.parent / "_home"),
            "CLAUDE_PROJECT_DIR": str(tmp_path),
            "CLAUDE_PLUGIN_ROOT": str(ROOT),
            "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        (tmp_path.parent / "_home").mkdir(exist_ok=True)
        proc = subprocess.run(
            ["python3", str(HOOK), "infer-critic-mode"],
            capture_output=True, text=True, env=env, cwd=str(tmp_path), timeout=30,
        )
        assert proc.returncode == 0, proc.stderr
        mode, _, rationale = proc.stdout.strip().partition("|")
        assert mode == "deferred"
        assert rationale.startswith("short-plan deferral:")


class TestProseCarriesTheConstant:
    """The chunk bound is one rule on four carriers — the constant and three
    prose surfaces that state it as a number. A change to either side without
    the other is the drift this pins."""

    @pytest.mark.parametrize(
        "rel",
        [
            "skills/critic/SKILL.md",
            "skills/critic/review-cycle.md",
            "methodology/planning.md",
        ],
    )
    def test_each_surface_states_the_bound_the_code_enforces(self, rel: str):
        text = (ROOT / rel).read_text()
        assert f"at most {critic_mode.SHORT_PLAN_MAX_CHUNKS} chunks" in text, rel

    def test_planning_heuristic_bullets_are_qualified_by_the_short_plan_rule(self):
        """`planning.md`'s single-chunk and multi-chunk heuristic bullets promise
        `final` / `chunk`; on a short plan `infer_mode` answers `deferred` and
        neither runs. Each bullet must carry the exception relationally, or
        the two bullets contradict the third and the code. What turns this
        red: dropping "unless the plan is short" from either bullet."""
        text = (ROOT / "methodology/planning.md").read_text()
        heuristic = text.split("**Heuristic — what inference will pick")[1]
        single = next(l for l in heuristic.splitlines() if l.startswith("- **Single-chunk plan**"))
        multi = next(l for l in heuristic.splitlines() if l.startswith("- **Multi-chunk plan**"))
        assert "unless the plan is short" in single, single
        assert "unless the plan is short" in multi, multi


class TestStatusChunkIds:
    """The exporter the predicate reads the roster through — the answer, not
    the walker (BLD-7K3Q's structural guard has no exception for it)."""

    def test_returns_every_chunk_id_in_order_ticked_or_not(self):
        content = (
            "# Plan\n\n## Status\n\n"
            "- [x] Chunk 01: done\n"
            "- [ ] Chunk 02: open\n"
            "- [ ] Not a chunk item\n"
            "- [ ] Chunk 1.2 (ID) — dotted\n\n"
            "## Chunk 01: done\n"
        )
        assert buildplan_refs.status_chunk_ids(content) == ["01", "02", "1.2"]

    def test_no_status_section_is_empty(self):
        assert buildplan_refs.status_chunk_ids("# Plan\n\nno roster\n") == []


# ---------------------------------------------------------------------------
# The Stop gate: WARNING on a non-final chunk, BLOCK on the last, BLOCK elsewhere
# ---------------------------------------------------------------------------


def _arm_stop(prawduct: Path) -> None:
    """Pre-satisfy every gate but the Critic one, as the sibling harnesses do."""
    (prawduct / ".session-reflected").write_text(SHAPED_REFLECTION)
    (prawduct / ".session-git-baseline").write_text("")
    ts = datetime.now(timezone.utc) - timedelta(seconds=60)
    (prawduct / ".session-start").write_text(ts.strftime("%Y-%m-%dT%H:%M:%SZ"))


def _run_stop(repo: Path) -> subprocess.CompletedProcess:
    home = repo.parent / "_home"
    home.mkdir(exist_ok=True)
    env = {
        "HOME": str(home),
        "CLAUDE_PROJECT_DIR": str(repo),
        "CLAUDE_PLUGIN_ROOT": str(ROOT),
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    return subprocess.run(
        ["python3", str(HOOK), "stop"],
        capture_output=True, text=True, env=env, cwd=str(repo), timeout=30,
        input="",
    )


class TestStopGateOnShortPlans:
    def test_non_final_chunk_warns_and_names_the_boundary_review(self, tmp_path: Path):
        prawduct = _short_plan_branch(tmp_path)
        _arm_stop(prawduct)
        result = _run_stop(tmp_path)
        assert result.returncode == 0, result.stderr
        assert _GENERIC_BLOCK not in result.stderr
        assert "deferred-boundary-review" in result.stderr
        # Delivered where exit 0 is read: ONE JSON object is the whole of stdout,
        # carrying the same text for the user and for the model.
        payload = json.loads(result.stdout)
        assert set(payload) == {"systemMessage", "additionalContext"}
        assert payload["systemMessage"] == payload["additionalContext"]
        text = payload["systemMessage"]
        assert "deferred-boundary-review" in text
        assert "`cumulative`" in text and "/prawduct:critic chunk" in text
        assert "gate: critic-review" in text  # attributed like a block would be

    def test_four_chunk_plan_still_blocks(self, tmp_path: Path):
        prawduct = _short_plan_branch(tmp_path, chunks=4)
        _arm_stop(prawduct)
        result = _run_stop(tmp_path)
        assert result.returncode == 2, result.stderr
        assert _GENERIC_BLOCK in result.stderr
        assert result.stdout.strip() == ""

    def test_risk_surface_plan_still_blocks(self, tmp_path: Path):
        prawduct = _short_plan_branch(
            tmp_path,
            state_extra="risk_surfaces:\n  - src/payments/\n",
            dirty_path="src/payments/ledger.py",
        )
        _arm_stop(prawduct)
        result = _run_stop(tmp_path)
        assert result.returncode == 2, result.stderr
        assert _GENERIC_BLOCK in result.stderr

    def test_declared_critic_mode_restores_the_block(self, tmp_path: Path):
        prawduct = _short_plan_branch(tmp_path, chunk_modes={"03": "final"})
        _arm_stop(prawduct)
        result = _run_stop(tmp_path)
        assert result.returncode == 2, result.stderr
        assert _GENERIC_BLOCK in result.stderr

    def test_a_ticked_but_uncommitted_penultimate_chunk_still_warns(self, tmp_path: Path):
        """The Stop between finishing chunk 02 of 3 and committing it: the
        gate must WARN (deferral), not BLOCK for a boundary review that chunk
        03 would then owe again."""
        prawduct = _short_plan_branch(tmp_path, committed=("01",), plan_committed=True)
        _tick_in_working_tree(prawduct, "02")
        _arm_stop(prawduct)
        result = _run_stop(tmp_path)
        assert result.returncode == 0, result.stderr
        assert _GENERIC_BLOCK not in result.stderr
        assert "deferred-boundary-review" in result.stderr

    def test_last_chunk_blocks_with_the_plan_tracked_too(self, tmp_path: Path):
        """Same block as below, on a repo that commits its plan: chunks 01–02
        landed with their ticks, chunk 03 in flight."""
        prawduct = _short_plan_branch(tmp_path, committed=("01", "02"), plan_committed=True)
        _arm_stop(prawduct)
        result = _run_stop(tmp_path)
        assert result.returncode == 2, result.stderr
        assert "it infers `cumulative`, which is this chunk's" in result.stderr

    def test_last_chunk_blocks_and_says_the_boundary_review_is_its_review(self, tmp_path: Path):
        prawduct = _short_plan_branch(tmp_path, committed=("01", "02"))
        _arm_stop(prawduct)
        result = _run_stop(tmp_path)
        assert result.returncode == 2, result.stderr
        assert _GENERIC_BLOCK in result.stderr
        assert "deferred to this" in result.stderr
        assert "it infers `cumulative`, which is this chunk's" in result.stderr
        assert "no separate `final`" in result.stderr

    def test_an_unresolved_blocking_finding_still_blocks(self, tmp_path: Path):
        """`blocked` is authority: a recorded blocker on an eligible plan's
        non-final chunk is not softened to a warning."""
        prawduct = _short_plan_branch(tmp_path)
        _arm_stop(prawduct)
        head_tree = _git(tmp_path, "rev-parse", "HEAD^{tree}").stdout.strip()
        captured = evidence.capture_tree(tmp_path)
        assert captured["status"] == "ok", captured
        result = evidence.append_fact(
            tmp_path, "review", "rev-test-block", {
                "base_tree": head_tree,
                "head_tree": captured["tree"],
                "files_changed": ["src/wip.py"],
                "files_reviewed": ["src/wip.py"],
                "findings": [{"fid": "R-1", "severity": "blocking", "title": "boom",
                              "goal": "Nothing Is Broken", "summary": "boom"}],
                "mode": _MODE_CHUNK,
            },
        )
        assert result["status"] == "appended", result
        stop = _run_stop(tmp_path)
        assert stop.returncode == 2, stop.stderr
        assert "unresolved blocking" in stop.stderr
        assert "deferred-boundary-review" not in stop.stderr

    def test_a_crashed_predicate_fails_closed_and_says_so(self, tmp_path: Path, capsys):
        """A relaxation that cannot be evaluated relaxes nothing — and says
        so, because a crashed predicate otherwise reads exactly like an
        ineligible plan and the builder never learns the deferral never got a
        look. In-process, because the crash cannot be injected across the
        subprocess boundary."""
        import importlib.machinery
        import importlib.util

        loader = importlib.machinery.SourceFileLoader("prawduct_hook_deferral", str(HOOK))
        spec = importlib.util.spec_from_loader("prawduct_hook_deferral", loader)
        hook = importlib.util.module_from_spec(spec)
        loader.exec_module(hook)

        class _Exploding:
            @property
            def path(self):
                raise RuntimeError("plan resolution exploded")

        prawduct = _short_plan_branch(tmp_path)
        assert hook._short_plan_deferral(tmp_path, prawduct, _Exploding()) is None
        err = capsys.readouterr().err
        assert "short-plan deferral could not be evaluated" in err
        assert "RuntimeError: plan resolution exploded" in err
        assert "applied in full" in err

    def test_an_unreadable_evidence_store_still_blocks(self, tmp_path: Path):
        """`error` is not a coverage verdict, so it is not softened either: the
        deferral is asked only of `uncovered`. The one status that reaches the
        same `else` branch as `uncovered` is `error`, induced here by making the
        store unreadable. (A DIRECTORY at the store path reads as `empty`, not
        `error` — the first cut of this test built that and never reached the
        subject; the precondition below is an assert so it cannot again.)"""
        prawduct = _short_plan_branch(tmp_path)
        _arm_stop(prawduct)
        store = evidence.store_path(tmp_path)
        assert store is not None
        store.parent.mkdir(parents=True, exist_ok=True)
        store.write_text("")
        store.chmod(0o000)
        assert evidence.read_facts(tmp_path)["status"] == "error", (
            "the fixture must reach the `error` verdict — an unreadable store; "
            "a root user can read a mode-000 file, and then this test cannot run"
        )
        stop = _run_stop(tmp_path)
        assert stop.returncode == 2, stop.stderr
        assert "deferred-boundary-review" not in stop.stderr
        assert stop.stdout.strip() == ""


# ---------------------------------------------------------------------------
# Acceptance: one cumulative fact is the whole review record, and the PR gate
# passes on it alone — the boundary gate never knew the plan was short
# ---------------------------------------------------------------------------


class TestOneBoundaryReviewIsEnough:
    def test_one_cumulative_fact_passes_the_pr_gate(self, tmp_path: Path, capsys):
        _short_plan_branch(tmp_path, committed=("01", "02", "03"), dirty=False)
        # Nothing reviewed yet: the boundary gate can and does fail (control).
        assert gates.check_cumulative_critic(tmp_path) != 0
        capsys.readouterr()
        assert infer_mode(tmp_path, None)[0] == "cumulative"
        base_tree = _git(tmp_path, "rev-parse", "main^{tree}").stdout.strip()
        head_tree = _git(tmp_path, "rev-parse", "HEAD^{tree}").stdout.strip()
        files = evidence.tree_diff(tmp_path, base_tree, head_tree)
        result = evidence.append_fact(
            tmp_path, "review", "rev-test-boundary", {
                "base_tree": base_tree,
                "head_tree": head_tree,
                "files_changed": files,
                "files_reviewed": files,
                "findings": [],
                "mode": _MODE_CUMULATIVE,
            },
        )
        assert result["status"] == "appended", result
        assert gates.check_cumulative_critic(tmp_path) == 0, capsys.readouterr()
        reviews = evidence.facts_of_kind(evidence.read_facts(tmp_path), "review")
        assert [f["body"]["mode"] for f in reviews] == [_MODE_CUMULATIVE]
