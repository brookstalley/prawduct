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
  non-final chunk, naming the boundary review. At exit 0 the warning goes to
  the hook's stderr log only: nobody there can act on it (the model never sees
  exit-0 output, and the user has nothing to do), so it is not put in the
  transcript as a ``systemMessage`` every turn. When another gate blocks it
  rides the exit-2 stderr beside the blockers, where the model reads it. On
  the last chunk it blocks as ever and says what the boundary review is.
- ``check-cumulative-critic`` is untouched: the plan's acceptance criterion is
  that one ``cumulative`` fact spanning merge-base…HEAD passes the PR gate on
  its own, and a control here shows the gate can still fail.

Fixtures are REAL git repos: the predicate reads merge-base and the branch's
changed paths, and the Stop harness's tree capture has to agree with them.
"""
from __future__ import annotations

import json
import sys
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from conftest import SHAPED_REFLECTION
from lib import critic_mode, evidence, gates, plan_index, work_unit
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
    binding = work_unit.resolve(repo)
    progress = critic_mode.binding_progress(repo, binding)
    return critic_mode.short_plan_deferral(repo, prawduct, binding, progress)


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
        # Renegotiated (#1051): the next step is "commit, naming the chunk" —
        # a committed chunk is `built` to inference, and nothing is ticked.
        assert "commit this chunk, naming it in the subject" in rationale
        assert "tick" not in rationale
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
        plan_path = work_unit.resolve(tmp_path).plan_path
        # Precondition: the two trees really disagree, so the subject is reached.
        # (Counted here directly; the box readers this used are deleted, #1051.)
        rel = plan_path.resolve().relative_to(tmp_path.resolve()).as_posix()
        head_text = _git(tmp_path, "show", f"HEAD:{rel}").stdout
        ticks = [
            sum(checked for checked, _t in plan_index.iter_status_section_items(text))
            for text in (plan_path.read_text(encoding="utf-8"), head_text)
        ]
        assert ticks == [2, 1], ticks
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
            [sys.executable, str(HOOK), "infer-critic-mode"],
            capture_output=True, text=True, env=env, cwd=str(tmp_path), timeout=30,
        )
        assert proc.returncode == 0, proc.stderr
        mode, _, rationale = proc.stdout.strip().partition("|")
        assert mode == "deferred"
        assert rationale.startswith("short-plan deferral:")


class TestAChunkShippedAsItsOwnPR:
    """The deferral knows one boundary, the plan's last chunk, because it
    assumes one PR per plan. A chunk merged as its own PR is a boundary too,
    and `Critic mode: cumulative` on it is the existing way to say so (#999)."""

    def _untick(self, prawduct: Path, chunk_id: str) -> None:
        plan = prawduct / "artifacts" / "build-plan.md"
        text = plan.read_text()
        needle = f"- [x] Chunk {chunk_id}:"
        assert needle in text, text
        plan.write_text(text.replace(needle, f"- [ ] Chunk {chunk_id}:"))

    def test_without_a_declaration_the_committed_first_chunk_defers(self, tmp_path: Path):
        """Today's behaviour, the control: Chunk 01 committed but unticked and
        an uncommitted non-plan file in flight — nothing knows a PR is coming.
        (On a clean tree with nothing reviewed, rule 4 already answers
        `cumulative`, so that state cannot be the control.)"""
        prawduct = _short_plan_branch(tmp_path, chunks=2, committed=("01",))
        self._untick(prawduct, "01")
        mode, rationale = infer_mode(tmp_path, None)
        assert mode == critic_mode.MODE_DEFERRED, rationale

    @pytest.mark.parametrize("dirty", [True, False])
    @pytest.mark.parametrize("ticked", [True, False])
    def test_the_declared_chunk_infers_cumulative_once_committed(
        self, tmp_path: Path, ticked: bool, dirty: bool
    ):
        prawduct = _short_plan_branch(
            tmp_path, chunks=2, committed=("01",), dirty=dirty,
            chunk_modes={"01": "cumulative", "02": "cumulative"},
        )
        if not ticked:
            self._untick(prawduct, "01")
        mode, rationale = infer_mode(tmp_path, None)
        assert mode == "cumulative", rationale

    def test_the_deferred_rationale_names_the_way_to_a_per_chunk_pr(self, tmp_path: Path):
        _short_plan_branch(tmp_path)
        mode, rationale = infer_mode(tmp_path, None)
        assert mode == critic_mode.MODE_DEFERRED, rationale
        assert critic_mode.SHORT_PLAN_OWN_PR_NOTE in rationale
        assert "/prawduct:critic cumulative" in rationale and "own PR" in rationale

    def test_the_stop_warning_names_it_too(self, tmp_path: Path):
        prawduct = _short_plan_branch(tmp_path)
        _arm_stop(prawduct)
        result = _run_stop(tmp_path)
        assert result.returncode == 0, result.stderr
        flat = " ".join(result.stderr.split())
        assert critic_mode.SHORT_PLAN_OWN_PR_NOTE in flat, flat

    @pytest.mark.parametrize("rel", ["methodology/planning.md", "templates/build-plan.md"])
    def test_the_guide_and_template_carry_the_rule(self, rel: str):
        text = (ROOT / rel).read_text()
        line = next((l for l in text.splitlines() if "own PR" in l), "")
        assert "Critic mode: cumulative" in line, rel


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
        [sys.executable, str(HOOK), "stop"],
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
        # Renegotiated (2026-10-27, owner: "pure noise"): this used to be a
        # `systemMessage` — the user's transcript, every turn while the deferral
        # held — for a status the user cannot act on and the model never sees at
        # exit 0. It is now log-only there; the exit-2 case below still carries
        # it to the model. `additionalContext` stays unused: it would start a
        # model turn on every Stop (#822).
        shown = json.loads(result.stdout)["systemMessage"] if result.stdout.strip() else ""
        assert "deferred-boundary-review" not in shown
        text = result.stderr
        assert "`cumulative`" in text and "/prawduct:critic chunk" in text
        assert "gate: critic-review" in text  # attributed like a block would be
        # The next step is the ONE statement `short_plan_next_step` owns: commit
        # the chunk naming it, naming the open chunks. Renegotiated (#1051): it
        # used to say "tick its box"; a committed chunk is now `built` to
        # inference, so nothing is ticked. What turns this red: the gate stating
        # its own "commit it and carry on", which drops the subject that makes
        # the chunk `built` and the boundary review reachable.
        flat = " ".join(text.split())
        assert "naming it in the subject" in flat and "waits for none" in flat, flat
        assert "open now: Chunk 01, Chunk 02, Chunk 03" in flat, flat
        assert "tick" not in flat
        assert "carry on" not in flat

    def test_the_advisory_rides_the_block_when_another_gate_blocks(self, tmp_path: Path):
        """#822: exit 2 used to drop the queued advisory. Same non-final chunk,
        plus an unshaped reflection over judgeable work, so the reflection gate
        blocks while the Critic gate only defers."""
        prawduct = _short_plan_branch(tmp_path)
        _arm_stop(prawduct)
        (prawduct / ".session-reflected").write_text("did stuff\n")
        result = _run_stop(tmp_path)
        assert result.returncode == 2, result.stderr
        assert "REFLECTION:" in result.stderr
        assert "ADVISORIES (not blocking):" in result.stderr
        advisories = result.stderr.split("ADVISORIES (not blocking):", 1)[1]
        assert "deferred-boundary-review" in advisories
        assert result.stdout.strip() == ""

    def test_every_stop_exit_after_the_advisories_delivers_them(self):
        """Each `return` in `cmd_stop` after `stop_advisories` is declared goes
        through `_deliver_stop_advisories` on the line before it."""
        src = HOOK.read_text()
        body = src[src.index("def cmd_stop("):]
        body = body[: body.index("\ndef ", 1)]
        after = body[body.index("stop_advisories: list[str] = []"):]
        lines = after.splitlines()
        returns = [i for i, ln in enumerate(lines) if ln.strip() in ("return 0", "return 2")]
        assert len(returns) == 4, returns
        for i in returns:
            window = "\n".join(lines[max(0, i - 12):i])
            assert "_deliver_stop_advisories(stop_advisories" in window, lines[i - 3:i + 1]

    def test_every_box_ticked_still_arms_the_gate(self, tmp_path: Path):
        """Renegotiated for #1051 (ST2): ticking the last box used to DISARM
        the Critic gate, since `has_build_plan` counted unticked boxes and a
        fully ticked plan read as no plan. So all three chunks landed and
        ticked with unreviewed work over them stopped silently, and the boundary
        review this file says the plan owes was owed to nobody. The gate now
        arms on the binding, so the same state blocks, naming no deferral:
        nothing is left to defer to."""
        prawduct = _short_plan_branch(tmp_path, committed=("01", "02", "03"))
        _arm_stop(prawduct)
        result = _run_stop(tmp_path)
        assert result.returncode == 2, f"stdout={result.stdout!r} stderr={result.stderr!r}"
        assert _GENERIC_BLOCK in result.stderr
        assert "deferred-boundary-review" not in result.stderr

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
        assert "infers `cumulative`, which is this chunk's review" in " ".join(result.stderr.split())

    def test_last_chunk_blocks_and_says_the_boundary_review_is_its_review(self, tmp_path: Path):
        prawduct = _short_plan_branch(tmp_path, committed=("01", "02"))
        _arm_stop(prawduct)
        result = _run_stop(tmp_path)
        assert result.returncode == 2, result.stderr
        assert _GENERIC_BLOCK in result.stderr
        flat = " ".join(result.stderr.split())
        assert "deferred to this" in flat
        assert "infers `cumulative`, which is this chunk's review" in flat
        assert "no separate `final`" in flat

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
            # Stands in for the `work_unit.Binding` the gate passes straight
            # through (#1050) — `plan_path` is the field the helper reads.
            @property
            def plan_path(self):
                raise RuntimeError("plan resolution exploded")

        prawduct = _short_plan_branch(tmp_path)
        assert hook._short_plan_deferral(tmp_path, prawduct, _Exploding()) is None
        err = capsys.readouterr().err
        assert "short-plan deferral could not be evaluated" in err
        assert "RuntimeError: plan resolution exploded" in err
        assert "applied in full" in err

    @pytest.mark.non_root
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


# ---------------------------------------------------------------------------
# #1051: a box-free short plan — committed chunks are `built` to inference
# ---------------------------------------------------------------------------


def _box_free_short_plan(tmp_path: Path, chunks: int, committed: tuple[str, ...]) -> Path:
    """A branch CLAIMED by a ``chunks``-chunk plan with no ``## Status`` block,
    committed on ``main`` before the branch; each id in ``committed`` lands as
    one commit whose subject names it (``Chunk NN``). Clean tree. Session
    state is ignored the way a real repo ignores it."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    _init_repo(tmp_path, branch="main")
    _write(tmp_path, ".gitignore", ".prawduct/.*\n")
    _write(tmp_path, "README.md", "x\n")
    _write(tmp_path, ".prawduct/project-state.yaml", "base_branch: main\n")
    lines = ["---", "artifact: build-plan", "scope: short", "branch: feature/short",
             "base: main", "---", "", "# Build Plan", ""]
    for i in range(1, chunks + 1):
        lines += [f"### Chunk {i:02d}: step {i}", "", "- **Type:** code",
                  "- **Deliverables:** stuff", ""]
    _write(tmp_path, ".prawduct/artifacts/build-plan-short.md", "\n".join(lines) + "\n")
    _commit(tmp_path, "initial")
    _checkout_new_branch(tmp_path, "feature/short")
    for cid in committed:
        _write(tmp_path, f"src/chunk_{cid}.py", f"# chunk {cid}\n")
        _commit(tmp_path, f"feat: land it (Chunk {cid})")
    return tmp_path / ".prawduct"


class TestBoxFreeShortPlanReadsBuilt:
    """With no box to tick, a short plan's earlier chunks stay OPEN until the
    boundary review names them, so "one chunk left" can only be seen through
    ``plan_status.built_chunks`` (``read_built``) — which may arm the Stop
    gate's last-chunk block, never clear it."""

    def test_two_of_three_committed_infers_the_boundary_cumulative(self, tmp_path):
        _box_free_short_plan(tmp_path, 3, ("01", "02"))
        mode, why = infer_mode(tmp_path, None)
        assert mode == "cumulative", why

    def test_one_of_three_committed_still_defers(self, tmp_path):
        _box_free_short_plan(tmp_path, 3, ("01",))
        mode, why = infer_mode(tmp_path, None)
        assert mode == critic_mode.MODE_DEFERRED, why
        assert why.startswith("short-plan deferral:"), why
        assert "naming it in the subject" in why and "tick" not in why, why
        # The boundary proposal counts only a subject carrying the plan's scope
        # (#1075), so the advice gives that form.
        assert "(`<type>(<scope>): … (Chunk <id>)`" in why, why

    def test_inference_walks_built_only_for_a_short_plan(self, tmp_path, monkeypatch):
        """The one place inference may call ``built_chunks`` is the short-plan
        rule, and only within ``SHORT_PLAN_MAX_CHUNKS``: a spy counts the walk
        on a 3-chunk plan, and on a 5-chunk plan it must never run."""
        from lib import plan_status

        calls: list = []
        real = plan_status.built_chunks

        def spy(*args, **kwargs):
            calls.append(args)
            return real(*args, **kwargs)

        monkeypatch.setattr(plan_status, "built_chunks", spy)
        _box_free_short_plan(tmp_path / "short", 3, ("01", "02"))
        infer_mode(tmp_path / "short", None)
        assert calls, "the short plan's last-chunk rule never asked built_chunks"

        def forbidden(*_a, **_k):
            raise AssertionError("inference walked built_chunks for a long plan")

        monkeypatch.setattr(plan_status, "built_chunks", forbidden)
        _box_free_short_plan(tmp_path / "long", 5, ("01", "02", "03", "04"))
        infer_mode(tmp_path / "long", None)

    # Renegotiated in the open (coordinator ruling, 2026-10-25): this class
    # pinned "the Stop gate's reading never walks built". The ruling is that a
    # git-derived signal may ARM a gate, never disarm one, so the gate now
    # passes `read_built=True` and the tests below pin the DIRECTION instead.

    def test_the_stop_gate_blocks_at_a_box_free_boundary(self, tmp_path):
        """Two of three chunks committed by subject, the third in flight: the
        Stop gate blocks for the boundary review on the uncovered tree."""
        prawduct = _box_free_short_plan(tmp_path, 3, ("01", "02"))
        _write(tmp_path, "src/wip.py", "# chunk 03 in flight\n")
        _arm_stop(prawduct)
        result = _run_stop(tmp_path)
        assert result.returncode == 2, result.stderr
        flat = " ".join(result.stderr.split())
        assert "deferred to this" in flat and "no separate `final`" in flat, flat

    def test_the_stop_gate_warns_mid_plan_on_a_box_free_plan(self, tmp_path):
        """Control: one of three committed — mid-plan, so the gate warns."""
        prawduct = _box_free_short_plan(tmp_path, 3, ("01",))
        _write(tmp_path, "src/wip.py", "# chunk 02 in flight\n")
        _arm_stop(prawduct)
        result = _run_stop(tmp_path)
        assert result.returncode == 0, result.stderr
        assert "deferred-boundary-review" in result.stderr
        assert _GENERIC_BLOCK not in result.stderr

    _STUB = (
        "---\nschema: 1\ntype: fix\nscope: short\ndate: 2026-10-26\ntitle: t\n---\n\n"
        "## Consumer note\n"
    )

    def _record_chunk_plan(self, tmp_path: Path, fragment: str) -> Path:
        """A two-chunk box-free plan whose change-record chunk 02 lists the
        fragment, committed on the branch as `plan new` commits it, with Chunk
        01 in flight."""
        prawduct = _box_free_short_plan(tmp_path, 2, ())
        plan = prawduct / "artifacts" / "build-plan-short.md"
        plan.write_text(plan.read_text().replace(
            "### Chunk 02: step 2\n\n- **Type:** code\n- **Deliverables:** stuff",
            "### Chunk 02: step 2\n\n- **Type:** code\n- **Deliverables:** `.prawduct/changes/short.md`",
        ))
        _write(tmp_path, ".prawduct/changes/short.md", fragment)
        _commit(tmp_path, "docs(short): build plan")
        _write(tmp_path, "src/wip.py", "# chunk 01 in flight\n")
        _arm_stop(prawduct)
        return prawduct

    def test_a_committed_fragment_stub_does_not_arm_the_last_chunk(self, tmp_path):
        """#1075: the stub `plan new` commits is no chunk's work, so with Chunk
        01 in flight the gate warns mid-plan rather than blocking for the
        boundary review a chunk early. Control: the same history with the
        fragment written reads 02 as built, and the gate arms."""
        self._record_chunk_plan(tmp_path / "stub", self._STUB)
        warned = _run_stop(tmp_path / "stub")
        assert warned.returncode == 0, warned.stderr
        assert "deferred-boundary-review" in warned.stderr

        self._record_chunk_plan(
            tmp_path / "written", self._STUB.replace("---\n\n", "---\nWhat changed.\n", 1)
        )
        assert _run_stop(tmp_path / "written").returncode == 2

    def test_built_arms_the_last_chunk_the_boxes_do_not(self, tmp_path):
        """A Status block whose boxes are all unticked (three open) and commits
        naming 01 and 02: `built` says last chunk, the boxes say mid-plan, and
        the gate's reading takes the arming side — it blocks."""
        _short_plan_branch(tmp_path, committed=("01", "02"), plan_committed=True)
        plan = work_unit.resolve(tmp_path).plan_path
        plan.write_text(plan.read_text().replace("- [x] ", "- [ ] "))
        _commit(tmp_path, "untick every box")
        _write(tmp_path, "src/wip3.py", "# chunk 03 in flight\n")
        assert critic_mode.binding_progress(tmp_path, work_unit.resolve(tmp_path)).open_count == 3
        binding = work_unit.resolve(tmp_path)
        progress = critic_mode.binding_progress(tmp_path, binding)
        prawduct = tmp_path / ".prawduct"
        assert not critic_mode.short_plan_deferral(tmp_path, prawduct, binding, progress).last_chunk
        armed = critic_mode.short_plan_deferral(
            tmp_path, prawduct, binding, progress, read_built=True
        )
        assert armed.defers and armed.last_chunk, armed
        _arm_stop(prawduct)
        assert _run_stop(tmp_path).returncode == 2

    def test_built_never_clears_what_the_facts_closed(self, tmp_path, monkeypatch):
        """`built` says mid-plan (no commit names a chunk), but a review fact
        closed 01 and 02: the facts' "last chunk" stands, and the walk is not
        even asked. And with the facts closing every chunk the plan is finished,
        so nothing defers whatever `built` would say."""
        from lib import plan_status

        prawduct = _box_free_short_plan(tmp_path, 3, ())
        head = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()

        def review(fid, chunks):
            assert evidence.append_fact(tmp_path, "review", fid, {
                "scope": "short", "mode": _MODE_CHUNK, "chunks": chunks,
                "chunk": chunks[0], "head_commit": head, "dispatch_commit": head,
                "findings": [], "counts": {"blocking": 0, "warning": 0, "note": 0},
            })["status"] == "appended"

        review("rev-a", ["01", "02"])
        _write(tmp_path, "src/wip3.py", "# chunk 03 in flight\n")
        binding = work_unit.resolve(tmp_path)
        assert plan_status.built_chunks(binding.plan_path, tmp_path) == set()

        def forbidden(*_a, **_k):
            raise AssertionError("built was asked where the facts already answered")

        monkeypatch.setattr(plan_status, "built_chunks", forbidden)
        d = critic_mode.short_plan_deferral(
            tmp_path, prawduct, binding, critic_mode.binding_progress(tmp_path, binding),
            read_built=True,
        )
        assert d.defers and d.last_chunk, d
        review("rev-b", ["03"])
        done = critic_mode.short_plan_deferral(
            tmp_path, prawduct, binding, critic_mode.binding_progress(tmp_path, binding),
            read_built=True,
        )
        assert not done.defers and not done.last_chunk, done


class TestOneStoreReadPerInference:
    """The fact store is read once per ``infer_mode`` call and threaded
    (``PlanProgress.facts``), into ``gates.covered_frontier`` too (``read=``),
    so the count is the whole inference's — nothing is stubbed."""

    def _count(self, monkeypatch) -> list:
        calls: list = []
        real = evidence.read_facts

        def counting(project_dir):
            calls.append(project_dir)
            return real(project_dir)

        monkeypatch.setattr(evidence, "read_facts", counting)
        return calls

    def test_a_deferring_short_plan_reads_the_store_once(self, tmp_path, monkeypatch):
        _short_plan_branch(tmp_path)
        calls = self._count(monkeypatch)
        assert infer_mode(tmp_path, None)[0] == critic_mode.MODE_DEFERRED
        assert len(calls) == 1, calls

    def test_the_boundary_answer_reads_the_store_once(self, tmp_path, monkeypatch):
        _box_free_short_plan(tmp_path, 3, ("01", "02"))
        calls = self._count(monkeypatch)
        assert infer_mode(tmp_path, None)[0] == "cumulative"
        assert len(calls) == 1, calls

    def test_the_mid_plan_redirect_reads_the_store_once(self, tmp_path, monkeypatch):
        """This answer walks the covered frontier (the mid-plan interval owner),
        so it pins `covered_frontier` taking the threaded read."""
        _box_free_short_plan(tmp_path, 3, ("01",))
        frontier_calls: list = []
        real_frontier = gates.covered_frontier

        def frontier_spy(*args, **kwargs):
            frontier_calls.append(kwargs.get("read"))
            return real_frontier(*args, **kwargs)

        monkeypatch.setattr(gates, "covered_frontier", frontier_spy)
        calls = self._count(monkeypatch)
        assert infer_mode(tmp_path, None)[0] == critic_mode.MODE_DEFERRED
        assert frontier_calls and all(r is not None for r in frontier_calls), frontier_calls
        assert len(calls) == 1, calls
