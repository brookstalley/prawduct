"""The per-release lane at inference: an eligible last chunk answers `chunk` (#1232, Chunk 04).

A repo that declares ``boundary_review: per_release`` moves an eligible
branch's boundary review to the release batch. At the plan's last chunk that
means inference answers ``chunk`` over the unreviewed interval, naming every
chunk the boundary ``cumulative`` would have named, where it used to answer
``cumulative``; the deferral and the Stop gate name that review instead of the
boundary. Eligibility is ONE predicate (``critic_mode.lane_eligibility``) and
each of its conditions is pinned here by a fixture that flips it, against a
control where only that condition differs.

The other half is the guardrail: with the key absent (``per_pr``, the default)
every answer and every message is what it was before the lane existed. The
existing short-plan, inference and Stop-gate suites pin those answers on
``per_pr`` fixtures; this file adds the literal per-PR wordings the lane's
branches sit beside, so a lane branch leaking into ``per_pr`` turns red here.

Fixtures are REAL git repos: the policy is read from ``project-state.yaml`` at
the merge-base, which only a tracked state file can answer.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest

from conftest import SHAPED_REFLECTION, scrubbed_env, suite_now
from lib import critic_consolidate, critic_mode, evidence, gates, review_lane, work_unit
from lib.critic_mode import infer_mode
from test_critic_mode_inference import _checkout_new_branch, _commit, _git, _init_repo, _write

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"

_MODE_CHUNK = "chunk (lighter pass, not ready for push)"


def _lane_repo(
    tmp_path: Path,
    *,
    chunks: int = 3,
    committed: tuple[str, ...] = ("01", "02", "03"),
    key: "str | None" = "per_release",
    key_in_working_tree_only: bool = False,
    extra_files: int = 0,
    in_flight: "str | None" = None,
    state_extra: str = "",
    chunk_fields: "dict[str, str] | None" = None,
) -> Path:
    """A branch claimed by a box-free ``chunks``-chunk plan (scope ``lane``),
    whose ``project-state.yaml`` is tracked and declares ``boundary_review:
    <key>`` on ``main`` before the branch is cut — so the merge-base reads it.
    ``key_in_working_tree_only`` writes the key on the branch instead, uncommitted:
    the branch trying to opt itself in. Each id in ``committed`` lands as one
    commit adding ``src/chunk_<id>.py`` (its Deliverable) under a scoped
    subject. ``extra_files`` more judgeable files land in one commit;
    ``in_flight`` leaves that chunk's file uncommitted. ``chunk_fields`` adds a
    field line to a chunk (``{"02": "- **Critic mode:** final"}``)."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    _init_repo(tmp_path, branch="main")
    _write(tmp_path, ".gitignore", ".prawduct/.*\n")
    _write(tmp_path, "README.md", "x\n")
    state = "base_branch: main\n" + state_extra
    if key is not None and not key_in_working_tree_only:
        state += f"boundary_review: {key}\n"
    _write(tmp_path, ".prawduct/project-state.yaml", state)
    lines = ["---", "artifact: build-plan", "scope: lane", "branch: feature/lane",
             "base: main", "---", "", "# Build Plan", ""]
    for i in range(1, chunks + 1):
        cid = f"{i:02d}"
        field = (chunk_fields or {}).get(cid)
        # A `Type:` field replaces the default one; any other field joins it.
        type_line = field if field and field.startswith("- **Type:**") else "- **Type:** code"
        lines += [f"### Chunk {cid}: step {i}", "", type_line]
        if field and field != type_line:
            lines.append(field)
        lines += [f"- **Deliverables:** `src/chunk_{cid}.py`", ""]
    _write(tmp_path, ".prawduct/artifacts/build-plan-lane.md", "\n".join(lines) + "\n")
    _commit(tmp_path, "initial")
    _checkout_new_branch(tmp_path, "feature/lane")
    if extra_files:
        for i in range(extra_files):
            _write(tmp_path, f"src/extra_{i:02d}.py", f"# extra {i}\n")
        _commit(tmp_path, "feat(lane): supporting files (Chunk 01)")
    for cid in committed:
        _write(tmp_path, f"src/chunk_{cid}.py", f"# chunk {cid}\n")
        _commit(tmp_path, f"feat(lane): land it (Chunk {cid})")
    if key is not None and key_in_working_tree_only:
        _write(tmp_path, ".prawduct/project-state.yaml", state + f"boundary_review: {key}\n")
    if in_flight is not None:
        _write(tmp_path, f"src/chunk_{in_flight}.py", f"# chunk {in_flight} in flight\n")
    return tmp_path / ".prawduct"


def _eligibility(repo: Path) -> critic_mode.LaneEligibility:
    binding = work_unit.resolve(repo)
    progress = critic_mode.binding_progress(repo, binding)
    return critic_mode.lane_eligibility(repo, repo / ".prawduct", binding, progress)


def _deferral(repo: Path) -> critic_mode.ShortPlanDeferral:
    binding = work_unit.resolve(repo)
    progress = critic_mode.binding_progress(repo, binding)
    return critic_mode.short_plan_deferral(repo, repo / ".prawduct", binding, progress, read_built=True)


def _flat(text: str) -> str:
    return " ".join(text.split())


# ---------------------------------------------------------------------------
# The bounds are the owner's numbers, pinned absolutely
# ---------------------------------------------------------------------------


class TestTheBounds:
    def test_the_lane_bounds_are_three_chunks_and_ten_judgeable_files(self):
        """Owner decisions (NFR amendment; decision 4): absolute values, never
        relative to another constant."""
        assert critic_mode.LANE_MAX_CHUNKS == 3
        assert critic_mode.LANE_MAX_JUDGEABLE_FILES == 10

    def test_the_lane_keeps_three_chunks_when_the_short_plan_bound_widens(self, tmp_path, monkeypatch):
        """Seam with #1247: a cadence key may widen the short-plan deferral to
        long plans. The lane's bound is its own, so a four-chunk plan stays out
        of it even when `SHORT_PLAN_MAX_CHUNKS` would let the shape through.
        What turns this red: reading the chunk bound through the shape alone."""
        _lane_repo(tmp_path, chunks=4, committed=("01", "02", "03", "04"))
        monkeypatch.setattr(critic_mode, "SHORT_PLAN_MAX_CHUNKS", 5)
        lane = _eligibility(tmp_path)
        assert not lane.eligible
        assert "the plan has 4 chunks (the per-release lane takes at most 3)" in lane.reason


# ---------------------------------------------------------------------------
# Eligible: the last chunk's review is `chunk`
# ---------------------------------------------------------------------------


class TestAnEligibleLastChunkAnswersChunk:
    def test_clean_tree_answers_chunk_naming_every_chunk(self, tmp_path):
        _lane_repo(tmp_path)
        lane = _eligibility(tmp_path)
        assert lane.eligible, lane.reason
        mode, why = infer_mode(tmp_path, None)
        assert mode == "chunk", why
        assert why.startswith("per-release lane (rule-2): "), why
        assert "pass `--chunks 01,02,03` to `critic-begin`" in why, why
        assert critic_mode.LANE_BOUNDARY_MOVED in why, why
        assert "the interval runs from the merge-base" in why, why
        assert "An explicit `/prawduct:critic cumulative` still runs the per-PR boundary review" in why

    def test_control_the_same_branch_without_the_key_answers_cumulative(self, tmp_path):
        _lane_repo(tmp_path, key=None)
        mode, why = infer_mode(tmp_path, None)
        assert mode == "cumulative", why
        assert why.startswith("rule-2 cumulative:"), why

    def test_rule_4s_redirect_answers_chunk_too(self, tmp_path):
        """One commit ahead: rule 2 needs two, so this is rule 4's clean-tree
        redirect, the second site that used to name `cumulative`."""
        _lane_repo(tmp_path, chunks=1, committed=("01",))
        mode, why = infer_mode(tmp_path, None)
        assert mode == "chunk", why
        assert why.startswith("per-release lane (rule-4): "), why
        assert "`--chunks 01`" in why, why
        # Control: per_pr redirects to the boundary review.
        _lane_repo(tmp_path / "per_pr", chunks=1, committed=("01",), key=None)
        mode, why = infer_mode(tmp_path / "per_pr", None)
        assert (mode, why.startswith("rule-4 cumulative:")) == ("cumulative", True), why

    def test_dirty_last_chunk_defers_naming_the_lane_step(self, tmp_path):
        _lane_repo(tmp_path, committed=("01", "02"), in_flight="03")
        mode, why = infer_mode(tmp_path, None)
        assert mode == critic_mode.MODE_DEFERRED, why
        assert critic_mode.LAST_CHUNK_RELEASE_STEP in why, why
        assert critic_mode.LAST_CHUNK_BOUNDARY_STEP not in why
        # Control: the per-PR step, word for word.
        _lane_repo(tmp_path / "per_pr", committed=("01", "02"), in_flight="03", key=None)
        mode, why = infer_mode(tmp_path / "per_pr", None)
        assert mode == critic_mode.MODE_DEFERRED, why
        assert critic_mode.LAST_CHUNK_BOUNDARY_STEP in why
        assert critic_mode.LAST_CHUNK_RELEASE_STEP not in why

    def test_a_non_final_chunk_defers_to_the_lane_review(self, tmp_path):
        _lane_repo(tmp_path, committed=("01",), in_flight="02")
        mode, why = infer_mode(tmp_path, None)
        assert mode == critic_mode.MODE_DEFERRED, why
        assert f"infers {critic_mode.LANE_REVIEW_NAME} once one chunk is left" in why, why
        assert "infers the boundary `cumulative`" not in why

    def test_an_explicit_cumulative_still_buys_the_per_pr_boundary(self, tmp_path):
        _lane_repo(tmp_path)
        assert infer_mode(tmp_path, "cumulative") == ("cumulative", "explicit-args")

    def test_an_explicit_chunk_on_the_clean_tree_is_not_redirected(self, tmp_path):
        _lane_repo(tmp_path)
        mode, why = infer_mode(tmp_path, "chunk")
        assert mode == "chunk", why
        assert why.startswith("explicit-args chunk (per-release lane, not redirected): "), why
        assert "`--chunks 01,02,03`" in why
        _lane_repo(tmp_path / "per_pr", key=None)
        mode, why = infer_mode(tmp_path / "per_pr", "chunk")
        assert mode == "cumulative" and why.startswith("explicit-args chunk redirected:"), why

    def test_an_explicit_final_keeps_its_token_and_says_so(self, tmp_path):
        """An explicit `final` (all seven goals) is not turned into the lane's
        `chunk` (goals 1-3): that would silently downgrade the operator's
        request. It runs over the lane's interval, and the rationale, which
        `mode_chosen_by` records, names the `final` as what runs, never claims
        the lane's `chunk` covers the PR."""
        _lane_repo(tmp_path)
        mode, why = infer_mode(tmp_path, "final")
        assert mode == "final", why
        assert why.startswith("explicit-args final (per-release lane, not redirected): "), why
        assert (
            f"covered by the `final` you asked for, run over the interval of {critic_mode.LANE_REVIEW_NAME}"
            in why
        ), why
        assert f"covered by {critic_mode.LANE_REVIEW_NAME} and" not in why, why
        # Control: an explicit `chunk` IS the lane's review, and says so.
        assert f"covered by {critic_mode.LANE_REVIEW_NAME} and" in infer_mode(tmp_path, "chunk")[1]

    def test_the_lane_dispatch_names_every_chunk_and_is_not_refused(self, tmp_path):
        """The rationale's `--chunks` is what keeps a `chunk` dispatch proposing
        three chunks from exit 8. Control: the same dispatch without it is
        refused as ambiguous, so the flag is what the rationale must carry."""
        _lane_repo(tmp_path)
        mode, why = infer_mode(tmp_path, None)
        assert mode == "chunk", why
        named = why.split("`--chunks ", 1)[1].split("`", 1)[0].split(",")
        assert named == ["01", "02", "03"]
        bare = critic_consolidate.begin_review(tmp_path, "chunk", chosen_by=why)
        assert (bare.get("status"), bare.get("kind")) == ("error", "chunks-ambiguous"), bare
        result = critic_consolidate.begin_review(tmp_path, "chunk", chosen_by=why, chunks=named)
        assert result["status"] == "ok", result
        manifest = json.loads((tmp_path / ".prawduct/.critic-partials/manifest.json").read_text())
        assert manifest["chunks"] == ["01", "02", "03"], manifest
        base_tree = _git(tmp_path, "rev-parse", "main^{tree}").stdout.strip()
        assert manifest["base_tree"] == base_tree, manifest

    def test_the_pr_gate_passes_on_the_lanes_coverage(self, tmp_path, capsys):
        """No mode label is consulted: one blocker-free `chunk` fact spanning
        merge-base to HEAD covers the PR, as a `cumulative` would."""
        _lane_repo(tmp_path)
        assert gates.check_cumulative_critic(tmp_path) != 0  # control: nothing reviewed
        capsys.readouterr()
        base_tree = _git(tmp_path, "rev-parse", "main^{tree}").stdout.strip()
        head_tree = _git(tmp_path, "rev-parse", "HEAD^{tree}").stdout.strip()
        files = evidence.tree_diff(tmp_path, base_tree, head_tree)
        assert evidence.append_fact(tmp_path, "review", "rev-lane", {
            "base_tree": base_tree, "head_tree": head_tree, "files_changed": files,
            "files_reviewed": files, "findings": [], "mode": _MODE_CHUNK,
        })["status"] == "appended"
        assert gates.check_cumulative_critic(tmp_path) == 0, capsys.readouterr()


# ---------------------------------------------------------------------------
# Each eligibility condition, flipped against an otherwise-eligible branch
# ---------------------------------------------------------------------------


def _assert_not_lane(tmp_path: Path, reason_part: str, **fixture) -> None:
    """The branch is not eligible for the named reason, and inference answers
    exactly what the same branch answers with the key absent — the lane adds
    nothing anywhere it does not hold."""
    _lane_repo(tmp_path / "lane", **fixture)
    lane = _eligibility(tmp_path / "lane")
    assert not lane.eligible
    assert reason_part in lane.reason, lane.reason
    fixture.pop("key", None)
    fixture.pop("key_in_working_tree_only", None)
    _lane_repo(tmp_path / "per_pr", key=None, **fixture)
    got = infer_mode(tmp_path / "lane", None)
    assert not got[1].startswith("per-release lane"), got
    assert got[0] == infer_mode(tmp_path / "per_pr", None)[0], got


class TestEachConditionFlipsItBack:
    def test_per_pr(self, tmp_path):
        _lane_repo(tmp_path, key="per_pr")
        assert "`boundary_review:` is per_pr" in _eligibility(tmp_path).reason
        assert infer_mode(tmp_path, None)[0] == "cumulative"

    def test_a_branch_cannot_opt_itself_in(self, tmp_path):
        _assert_not_lane(tmp_path, "a branch cannot opt itself in", key_in_working_tree_only=True)

    def test_a_risk_surface(self, tmp_path):
        _assert_not_lane(
            tmp_path, "risk surface", state_extra="risk_surfaces:\n  - src/chunk_02.py\n"
        )

    def test_a_branch_cannot_drop_its_own_risk_surface(self, tmp_path):
        """main declares `src/chunk_02.py` a risk surface; the branch rewrites
        `risk_surfaces: []`. The short-plan shape reads this checkout, so it
        holds; the lane reads the integration branch too, so it does not."""
        _lane_repo(tmp_path, state_extra="risk_surfaces:\n  - src/chunk_02.py\n")
        _write(tmp_path, ".prawduct/project-state.yaml",
               "base_branch: main\nrisk_surfaces: []\nboundary_review: per_release\n")
        _commit(tmp_path, "chore: drop the risk surface")
        lane = _eligibility(tmp_path)
        assert not lane.eligible, lane.reason
        assert "src/chunk_02.py matched risk surface src/chunk_02.py" in lane.reason, lane.reason
        assert infer_mode(tmp_path, None)[0] == "cumulative"
        # The per_pr short-plan deferral is unchanged: it still reads this checkout.
        assert _deferral(tmp_path).defers

    @pytest.mark.parametrize("main_holds", [True, False], ids=["main-holds-it", "control"])
    def test_a_stacked_unit_s_base_cannot_drop_a_surface_main_holds(self, tmp_path, monkeypatch, main_holds):
        """Native review round 6, candidate 4: a unit stacked on `stack` (its
        plan's `base:`), which rewrote `risk_surfaces: []` unmerged. The lane
        reads the held surfaces at the repo's integration branch, never at the
        unit's base. Control: main never declaring it, the stacked branch is in
        the lane, so the fixture reaches eligibility."""
        _lane_repo(tmp_path, state_extra="risk_surfaces:\n  - src/chunk_02.py\n" if main_holds else "")
        _git(tmp_path, "checkout", "-q", "-b", "stack", "main")
        _write(tmp_path, ".prawduct/project-state.yaml",
               "base_branch: main\nrisk_surfaces: []\nboundary_review: per_release\n")
        _commit(tmp_path, "chore: drop the risk surface")
        _git(tmp_path, "checkout", "-q", "feature/lane")
        _git(tmp_path, "rebase", "-q", "stack")
        from lib import coverage  # noqa: PLC0415

        monkeypatch.setattr(coverage, "_bound_plan_base", lambda _p: "stack")
        lane = _eligibility(tmp_path)
        if main_holds:
            assert not lane.eligible, lane.reason
            assert "src/chunk_02.py matched risk surface src/chunk_02.py" in lane.reason, lane.reason
        else:
            assert lane.eligible, lane.reason

    def test_a_risk_surface_renamed_away(self, tmp_path):
        """Native finding 3 (round 5): git's rename detection lists only the new
        path, so a branch moving a risk surface away read untouched and took the
        lane. The lane reads the branch with renames off."""
        _lane_repo(tmp_path, state_extra="risk_surfaces:\n  - src/legacy.py\n")
        _git(tmp_path, "checkout", "-q", "main")
        _write(tmp_path, "src/legacy.py", "# the surface\n")
        _commit(tmp_path, "the surface")
        _git(tmp_path, "checkout", "-q", "feature/lane")
        _git(tmp_path, "rebase", "-q", "main")
        assert _eligibility(tmp_path).eligible  # control: the surface untouched, the lane holds
        _git(tmp_path, "mv", "src/legacy.py", "src/moved.py")
        _commit(tmp_path, "feat(lane): move it (Chunk 03)")
        lane = _eligibility(tmp_path)
        assert not lane.eligible, lane.reason
        assert "src/legacy.py matched risk surface src/legacy.py" in lane.reason, lane.reason
        assert infer_mode(tmp_path, None)[0] == "cumulative"

    def test_four_chunks(self, tmp_path):
        _assert_not_lane(
            tmp_path, "the plan has 4 chunks", chunks=4, committed=("01", "02", "03", "04")
        )

    def test_a_critic_mode_declared(self, tmp_path):
        _assert_not_lane(
            tmp_path, "declares Critic mode", chunk_fields={"02": "- **Critic mode:** final"}
        )

    def test_type_cumulative_final(self, tmp_path):
        _assert_not_lane(
            tmp_path, "Type: cumulative-final",
            chunk_fields={"03": "- **Type:** cumulative-final"},
        )

    def test_eleven_judgeable_files(self, tmp_path):
        """3 chunk files + 8 more = 11. The boundary case, 10, is eligible."""
        _assert_not_lane(tmp_path, "changes 11 judgeable files", extra_files=8)
        _lane_repo(tmp_path / "ten", extra_files=7)
        lane = _eligibility(tmp_path / "ten")
        assert lane.eligible and "changes 10 judgeable file(s)" in lane.reason, lane.reason

    def test_a_crashed_predicate_is_not_eligible_and_inference_survives(self, tmp_path, monkeypatch):
        _lane_repo(tmp_path)

        def boom(*_a, **_k):
            raise RuntimeError("policy read exploded")

        monkeypatch.setattr(review_lane, "boundary_review_policy", boom)
        lane = _eligibility(tmp_path)
        assert not lane.eligible and "RuntimeError: policy read exploded" in lane.reason
        assert infer_mode(tmp_path, None)[0] == "cumulative"


# ---------------------------------------------------------------------------
# After the lane's review: nothing owes a `cumulative`
# ---------------------------------------------------------------------------


class TestAfterTheLanesReview:
    def _reviewed(self, tmp_path: Path, key: "str | None") -> Path:
        _lane_repo(tmp_path, key=key)
        head = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()
        base_tree = _git(tmp_path, "rev-parse", "main^{tree}").stdout.strip()
        head_tree = _git(tmp_path, "rev-parse", "HEAD^{tree}").stdout.strip()
        files = evidence.tree_diff(tmp_path, base_tree, head_tree)
        assert evidence.append_fact(tmp_path, "review", "rev-lane", {
            "scope": "lane", "mode": _MODE_CHUNK, "chunks": ["01", "02", "03"],
            "head_commit": head, "dispatch_commit": head, "base_tree": base_tree,
            "head_tree": head_tree, "files_changed": files, "files_reviewed": files,
            "findings": [], "counts": {"blocking": 0, "warning": 0, "note": 0},
        })["status"] == "appended"
        return tmp_path

    def _owed(self, repo: Path):
        binding = work_unit.resolve(repo)
        progress = critic_mode.binding_progress(repo, binding)
        read = evidence.read_facts(repo)
        newest = critic_mode._newest_branch_review(repo, read)
        assert newest is not None
        chain = critic_mode.branch_review_chain(repo, read.get("facts") or [], newest)
        return critic_mode.review_owed_after(repo, repo / ".prawduct", binding, progress, chain)

    def test_nothing_is_owed_once_the_lane_review_finished_the_plan(self, tmp_path):
        assert self._owed(self._reviewed(tmp_path / "lane", "per_release")) is None
        # Control: per_pr still owes its boundary `cumulative` after a `chunk`.
        owed = self._owed(self._reviewed(tmp_path / "per_pr", None))
        assert owed is not None and owed[0] == critic_mode.OWED_BOUNDARY, owed

    def test_a_fix_deferred_to_the_last_review_names_the_lanes(self, tmp_path):
        """The extension deferral's boundary arm (reached on a plan whose review
        facts cannot certify chunks: a legacy-window plan with ticked boxes)
        says which review will cover the fix. Under the lane that is the lane's
        `chunk`, never "it infers the cumulative"; per_pr keeps its words."""
        from test_short_plan_deferral import _short_plan_branch  # noqa: PLC0415

        answers = {}
        for name, extra in (("lane", "boundary_review: per_release\n"), ("per_pr", "")):
            repo = tmp_path / name
            repo.mkdir()
            _short_plan_branch(repo, committed=("01", "02"), plan_committed=True, state_extra=extra)
            head = _git(repo, "rev-parse", "HEAD").stdout.strip()
            captured = evidence.capture_tree(repo)
            assert evidence.append_fact(repo, "review", "rev-03", {
                "mode": _MODE_CHUNK, "chunks": ["03"], "head_commit": head,
                "dispatch_commit": head,
                "base_tree": _git(repo, "rev-parse", "HEAD^{tree}").stdout.strip(),
                "head_tree": captured["tree"], "files_changed": ["src/wip.py"],
                "files_reviewed": ["src/wip.py"], "findings": [],
                "counts": {"blocking": 0, "warning": 0, "note": 0},
            })["status"] == "appended"
            _write(repo, "src/wip.py", "# a warning, fixed\n")
            binding = work_unit.resolve(repo)
            assert binding.is_legacy, binding
            progress = critic_mode.binding_progress(repo, binding)
            answers[name] = critic_mode.extension_deferral_owed(
                repo, repo / ".prawduct", binding, progress
            )
        lane, per_pr = answers["lane"], answers["per_pr"]
        # The owner names the lane's review in its KIND (`OWED_LANE`), so no
        # reader re-asks the lane to tell it from the per-PR boundary.
        assert lane is not None and lane[0] == critic_mode.OWED_LANE, lane
        assert per_pr is not None and per_pr[0] == critic_mode.OWED_BOUNDARY, per_pr
        assert lane[1].endswith(f"it infers {critic_mode.LANE_REVIEW_NAME}"), lane
        assert f"so {critic_mode.LANE_REVIEW_NAME} is every chunk's review" in lane[1], lane
        assert "cumulative" not in lane[1], lane
        assert per_pr is not None and per_pr[1].endswith("it infers the cumulative"), per_pr
        assert "so the boundary `cumulative` is every chunk's review" in per_pr[1], per_pr

    def test_the_close_names_the_lanes_review_not_a_cumulative(self, tmp_path):
        """The review close's ride-along lead (the extension deferral's twin):
        under the lane the review still owed is the lane's `chunk`, so it never
        promises a boundary `cumulative`; per_pr keeps its words."""
        from test_short_plan_deferral import _short_plan_branch  # noqa: PLC0415

        owed = {}
        for name, extra in (("lane", "boundary_review: per_release\n"), ("per_pr", "")):
            repo = tmp_path / name
            repo.mkdir()
            _short_plan_branch(repo, committed=("01", "02"), plan_committed=True, state_extra=extra)
            head = _git(repo, "rev-parse", "HEAD").stdout.strip()
            captured = evidence.capture_tree(repo)
            assert evidence.append_fact(repo, "review", "rev-03", {
                "mode": _MODE_CHUNK, "chunks": ["03"], "head_commit": head,
                "dispatch_commit": head,
                "base_tree": _git(repo, "rev-parse", "HEAD^{tree}").stdout.strip(),
                "head_tree": captured["tree"], "files_changed": ["src/wip.py"],
                "files_reviewed": ["src/wip.py"], "findings": [],
                "counts": {"blocking": 0, "warning": 0, "note": 0},
            })["status"] == "appended"
            facts = evidence.read_facts(repo)["facts"]
            fact = next(f for f in facts if f.get("id") == "rev-03")
            owed[name] = critic_consolidate._plan_owes_a_later_review(repo, repo / ".prawduct", facts, fact)
        assert owed == {"lane": critic_mode.OWED_LANE, "per_pr": critic_mode.OWED_BOUNDARY}, owed
        lane = critic_consolidate.next_action_line("rev-x", 0, 1, 0, rides_next_review=owed["lane"])
        lead = lane.split(" 0 blocking")[0]  # the ride-along lead, before the shared close
        assert lead.startswith(f"This plan still owes {critic_mode.LANE_REVIEW_NAME}"), lane
        assert "cumulative" not in lead, lead
        per_pr = critic_consolidate.next_action_line("rev-x", 0, 1, 0, rides_next_review=owed["per_pr"])
        assert "This plan still owes its boundary `cumulative`" in per_pr, per_pr

    def test_a_committed_fix_infers_the_lane_chunk_not_a_cumulative(self, tmp_path):
        repo = self._reviewed(tmp_path / "lane", "per_release")
        _write(repo, "src/chunk_02.py", "# chunk 02, a warning fixed\n")
        _commit(repo, "fix(lane): the warning (Chunk 02)")
        mode, why = infer_mode(repo, None)
        assert mode == "chunk", why
        assert why.startswith("per-release lane (rule-2): "), why
        assert "the interval runs from the last reviewed state" in why, why


# ---------------------------------------------------------------------------
# The Stop gate names the lane's review; per_pr keeps its words
# ---------------------------------------------------------------------------


def _arm_stop(prawduct: Path) -> None:
    (prawduct / ".session-reflected").write_text(SHAPED_REFLECTION)
    (prawduct / ".session-git-baseline").write_text("")
    ts = suite_now() - timedelta(seconds=60)
    (prawduct / ".session-start").write_text(ts.strftime("%Y-%m-%dT%H:%M:%SZ"))


def _run_stop(repo: Path) -> subprocess.CompletedProcess:
    home = repo.parent / f"_home_{repo.name}"
    home.mkdir(exist_ok=True)
    env = scrubbed_env(home, CLAUDE_PROJECT_DIR=str(repo), CLAUDE_PLUGIN_ROOT=str(ROOT))
    return subprocess.run(
        [sys.executable, str(HOOK), "stop"],
        capture_output=True, text=True, env=env, cwd=str(repo), timeout=30, input="",
    )


#: The per-PR wordings the lane's branches sit beside, copied from the gate as
#: it was before the lane: a lane branch leaking into `per_pr` changes them.
_PER_PR_NON_FINAL = (
    "  This chunk's review is deferred to the boundary. Next:\n",
    "  The boundary review is the PR gate's evidence. To review this chunk anyway, run\n"
    "  `/prawduct:critic chunk`, or declare `Critic mode:` on any chunk of\n"
    "  the plan to restore per-chunk review for the whole plan.\n",
)
_PER_PR_LAST = "  This plan is short and its per-chunk reviews were deferred to this\n  boundary review ("


class TestTheStopGate:
    def test_last_chunk_blocks_naming_the_lane_step(self, tmp_path):
        prawduct = _lane_repo(tmp_path / "lane", committed=("01", "02"), in_flight="03")
        _arm_stop(prawduct)
        result = _run_stop(tmp_path / "lane")
        assert result.returncode == 2, result.stderr
        flat = _flat(result.stderr)
        assert f"deferred to {critic_mode.LANE_REVIEW_NAME} (" in flat, flat
        assert _flat(critic_mode.LAST_CHUNK_RELEASE_STEP) in flat, flat
        assert _PER_PR_LAST not in result.stderr
        # Control: per_pr, the same branch without the key.
        prawduct = _lane_repo(tmp_path / "per_pr", committed=("01", "02"), in_flight="03", key=None)
        _arm_stop(prawduct)
        control = _run_stop(tmp_path / "per_pr")
        assert control.returncode == 2, control.stderr
        assert _PER_PR_LAST in control.stderr
        assert _flat(critic_mode.LAST_CHUNK_BOUNDARY_STEP) in _flat(control.stderr)
        assert critic_mode.LANE_REVIEW_NAME not in _flat(control.stderr)

    def test_a_non_final_chunk_warns_naming_the_lane_review(self, tmp_path):
        prawduct = _lane_repo(tmp_path / "lane", committed=(), in_flight="01")
        _arm_stop(prawduct)
        result = _run_stop(tmp_path / "lane")
        assert result.returncode == 0, result.stderr
        flat = _flat(result.stderr)
        assert "deferred-boundary-review" in flat
        assert f"This chunk's review is deferred to {critic_mode.LANE_REVIEW_NAME}. Next:" in flat
        assert _flat(critic_mode.LANE_BOUNDARY_MOVED) in flat, flat
        assert "/prawduct:critic chunk" in flat
        assert all(literal not in result.stderr for literal in _PER_PR_NON_FINAL)
        prawduct = _lane_repo(tmp_path / "per_pr", committed=(), in_flight="01", key=None)
        _arm_stop(prawduct)
        control = _run_stop(tmp_path / "per_pr")
        assert control.returncode == 0, control.stderr
        assert all(literal in control.stderr for literal in _PER_PR_NON_FINAL), control.stderr
        assert critic_mode.LANE_REVIEW_NAME not in _flat(control.stderr)


# ---------------------------------------------------------------------------
# per_pr: the composed step text is what it was, word for word
# ---------------------------------------------------------------------------


class TestPerPrStepTextIsUnchanged:
    """The step strings as they read before the lane, copied literally, so a
    rewording that leaks the lane into `per_pr` (or drifts the per-PR text)
    turns red here rather than only where a substring happens to be asserted."""

    _LAST = (
        "this is the last chunk and the boundary review is its review: "
        "commit it, then `/prawduct:critic` infers `cumulative`, which is "
        "this chunk's review and the PR gate's evidence — no separate `final`"
    )
    _NON_FINAL = (
        "commit this chunk, naming it in the subject under the plan's scope "
        "(`<type>(<scope>): … (Chunk <id>)`, `<scope>` being the plan's `scope:`) — a "
        "deferred chunk's review is the boundary's, so it waits for none (open now: Chunk 01). "
        "Then build the last chunk before asking for review: `/prawduct:critic` "
        "infers the boundary `cumulative` once one chunk is left uncommitted and "
        "the tree is clean, and that review names every chunk built and still "
        "open (a chunk built ahead of an open one is named by its scoped subject), and closes "
        "them together"
    )

    @pytest.mark.parametrize("lane", [None, False])
    def test_per_pr_steps(self, lane):
        last = critic_mode.ShortPlanDeferral(True, "r", True, 3, ("Chunk 01",), lane)
        non_final = critic_mode.ShortPlanDeferral(True, "r", False, 3, ("Chunk 01",), lane)
        assert critic_mode.LAST_CHUNK_BOUNDARY_STEP == self._LAST
        assert critic_mode.short_plan_next_step(last) == self._LAST
        assert critic_mode.short_plan_next_step(non_final) == self._NON_FINAL

    def test_lane_steps(self):
        last = critic_mode.ShortPlanDeferral(True, "r", True, 3, ("Chunk 01",), True)
        non_final = critic_mode.ShortPlanDeferral(True, "r", False, 3, ("Chunk 01",), True)
        assert critic_mode.short_plan_next_step(last) == critic_mode.LAST_CHUNK_RELEASE_STEP
        assert critic_mode.short_plan_next_step(non_final) == self._NON_FINAL.replace(
            "the boundary `cumulative`", critic_mode.LANE_REVIEW_NAME
        )

    def test_per_pr_inference_matches_a_repo_without_the_key(self, tmp_path):
        """`per_pr` declared and the key absent answer identically at every
        point of the plan the lane changes — the control the acceptance
        criterion names."""
        for name, kw in {
            "clean-last": {},
            "dirty-last": {"committed": ("01", "02"), "in_flight": "03"},
            "mid-plan": {"committed": ("01",), "in_flight": "02"},
        }.items():
            _lane_repo(tmp_path / f"{name}-declared", key="per_pr", **kw)
            _lane_repo(tmp_path / f"{name}-absent", key=None, **kw)
            declared = infer_mode(tmp_path / f"{name}-declared", None)
            absent = infer_mode(tmp_path / f"{name}-absent", None)
            assert declared[0] == absent[0], (name, declared, absent)
            assert declared[1].replace(f"{name}-declared", "X") == absent[1].replace(
                f"{name}-absent", "X"
            ), name


# ---------------------------------------------------------------------------
# Where the lane was in play and declined, the per-PR answer says why
# ---------------------------------------------------------------------------

_DECLINED = "the per-release lane does not take this branch: "


class TestTheDeclinedLaneSaysWhy:
    """Under per_release a branch the lane declines pays the boundary round the
    owner moved; every answer naming that round says why. Under per_pr the
    same answers are unchanged, word for word (`_assert_not_lane` and
    `TestPerPrStepTextIsUnchanged` pin the rest)."""

    def test_rule_2_names_the_reason_and_per_pr_is_unchanged(self, tmp_path):
        _lane_repo(tmp_path / "lane", extra_files=8)
        mode, why = infer_mode(tmp_path / "lane", None)
        assert mode == "cumulative" and why.startswith("rule-2 cumulative:"), why
        assert f"; {_DECLINED}the branch changes 11 judgeable files" in why, why
        _lane_repo(tmp_path / "per_pr", extra_files=8, key=None)
        control = infer_mode(tmp_path / "per_pr", None)
        assert control[0] == "cumulative" and _DECLINED not in control[1], control
        assert why.split("; " + _DECLINED, 1)[0] == control[1], (why, control)

    #: What a crashed predicate reads as, after the declined prefix.
    _CRASHED = "the per-release lane could not be evaluated (RuntimeError: lane exploded)"

    @staticmethod
    def _boom(monkeypatch) -> None:
        def boom(*_a, **_k):
            raise RuntimeError("lane exploded")

        monkeypatch.setattr(critic_mode, "_lane_eligibility", boom)

    def test_rule_2_names_a_crashed_lane_not_an_ineligible_one(self, tmp_path, monkeypatch):
        _lane_repo(tmp_path)
        self._boom(monkeypatch)
        mode, why = infer_mode(tmp_path, None)
        assert mode == "cumulative" and why.startswith("rule-2 cumulative:"), why
        assert why.endswith(f"; {_DECLINED}{self._CRASHED}"), why

    def test_an_unreachable_lane_interval_says_the_cumulative_stands(self, tmp_path, monkeypatch):
        """The lane takes the branch but its `chunk` interval cannot reach the
        unreviewed commits, so the boundary `cumulative` stands, and says so
        rather than reading like a branch the lane never took."""
        _lane_repo(tmp_path)
        assert _eligibility(tmp_path).eligible
        monkeypatch.setattr(critic_mode, "_reaches_committed_work", lambda _start: False)
        mode, why = infer_mode(tmp_path, None)
        assert mode == "cumulative" and why.startswith("rule-2 cumulative:"), why
        assert why.endswith(
            "; the per-release lane takes this branch, but its `chunk` interval cannot reach "
            "the unreviewed commits, so the boundary `cumulative` stands"
        ), why

    def test_rule_4_names_the_reason_and_per_pr_is_unchanged(self, tmp_path):
        """One commit ahead (rule 2 needs two), so the clean-tree redirect
        answers; the one chunk declares `Type: cumulative-final`, which the
        lane declines."""
        final = {"01": "- **Type:** cumulative-final"}
        _lane_repo(tmp_path / "lane", chunks=1, committed=("01",), chunk_fields=final)
        mode, why = infer_mode(tmp_path / "lane", None)
        assert mode == "cumulative" and why.startswith("rule-4 cumulative:"), why
        assert why.endswith(
            f"; {_DECLINED}the last chunk declares `Type: cumulative-final`, which names a "
            "boundary review"
        ), why
        _lane_repo(tmp_path / "per_pr", chunks=1, committed=("01",), chunk_fields=final, key=None)
        control = infer_mode(tmp_path / "per_pr", None)
        assert control[0] == "cumulative" and _DECLINED not in control[1], control
        assert why.split("; " + _DECLINED, 1)[0] == control[1], (why, control)

    def test_rule_4_names_a_crashed_lane(self, tmp_path, monkeypatch):
        _lane_repo(tmp_path, chunks=1, committed=("01",))
        self._boom(monkeypatch)
        mode, why = infer_mode(tmp_path, None)
        assert mode == "cumulative" and why.startswith("rule-4 cumulative:"), why
        assert why.endswith(f"; {_DECLINED}{self._CRASHED}"), why

    def test_an_explicit_redirect_names_the_reason_and_per_pr_is_unchanged(self, tmp_path):
        _lane_repo(tmp_path / "lane", extra_files=8)
        mode, why = infer_mode(tmp_path / "lane", "chunk")
        assert mode == "cumulative" and why.startswith("explicit-args chunk redirected:"), why
        assert why.endswith(
            f"; {_DECLINED}the branch changes 11 judgeable files (the per-release lane takes "
            f"at most {critic_mode.LANE_MAX_JUDGEABLE_FILES})"
        ), why
        _lane_repo(tmp_path / "per_pr", extra_files=8, key=None)
        control = infer_mode(tmp_path / "per_pr", "chunk")
        assert control[0] == "cumulative" and _DECLINED not in control[1], control
        assert why.split("; " + _DECLINED, 1)[0] == control[1], (why, control)

    def test_an_explicit_redirect_names_a_crashed_lane(self, tmp_path, monkeypatch):
        _lane_repo(tmp_path)
        self._boom(monkeypatch)
        for token in ("chunk", "final"):
            mode, why = infer_mode(tmp_path, token)
            assert mode == "cumulative", (token, why)
            assert why.startswith(f"explicit-args {token} redirected:"), why
            assert why.endswith(f"; {_DECLINED}{self._CRASHED}"), why

    def test_the_deferral_rationale_names_the_reason(self, tmp_path):
        _lane_repo(tmp_path / "lane", committed=("01", "02"), in_flight="03", extra_files=8)
        d = _deferral(tmp_path / "lane")
        assert d.defers and d.lane is False, d
        assert d.lane_note.startswith(f"{_DECLINED}the branch changes 11 judgeable files"), d
        mode, why = infer_mode(tmp_path / "lane", None)
        assert mode == critic_mode.MODE_DEFERRED and f"; {d.lane_note}. " in why, why
        _lane_repo(
            tmp_path / "per_pr", committed=("01", "02"), in_flight="03", extra_files=8, key=None
        )
        d_pr = _deferral(tmp_path / "per_pr")
        assert d_pr.defers and d_pr.lane is False and d_pr.lane_note == "", d_pr
        control = infer_mode(tmp_path / "per_pr", None)
        assert control[0] == critic_mode.MODE_DEFERRED and _DECLINED not in control[1], control
        assert why.replace(f"; {d.lane_note}", "") == control[1], (why, control)

    def test_the_deferral_rationale_names_a_crashed_lane(self, tmp_path, monkeypatch):
        _lane_repo(tmp_path, committed=("01", "02"), in_flight="03")
        self._boom(monkeypatch)
        d = _deferral(tmp_path)
        assert d.defers and d.lane is False and d.lane_note == f"{_DECLINED}{self._CRASHED}", d
        mode, why = infer_mode(tmp_path, None)
        assert mode == critic_mode.MODE_DEFERRED and f"; {_DECLINED}{self._CRASHED}. " in why, why

    def test_the_stop_gates_boundary_block_names_the_reason(self, tmp_path):
        prawduct = _lane_repo(
            tmp_path / "lane", committed=("01", "02"), in_flight="03", extra_files=8
        )
        _arm_stop(prawduct)
        result = _run_stop(tmp_path / "lane")
        assert result.returncode == 2, result.stderr
        assert _PER_PR_LAST in result.stderr
        assert (
            "The per-release lane does not take this branch: the branch changes 11 judgeable files"
            in _flat(result.stderr)
        ), result.stderr
        prawduct = _lane_repo(
            tmp_path / "per_pr", committed=("01", "02"), in_flight="03", extra_files=8, key=None
        )
        _arm_stop(prawduct)
        control = _run_stop(tmp_path / "per_pr")
        assert control.returncode == 2, control.stderr
        assert _PER_PR_LAST in control.stderr
        assert "per-release lane" not in _flat(control.stderr)

    def test_the_stop_gates_non_final_warning_names_the_reason(self, tmp_path):
        prawduct = _lane_repo(tmp_path / "lane", committed=(), in_flight="01", extra_files=10)
        _arm_stop(prawduct)
        result = _run_stop(tmp_path / "lane")
        assert result.returncode == 0, result.stderr
        assert all(literal in result.stderr for literal in _PER_PR_NON_FINAL), result.stderr
        assert (
            "The per-release lane does not take this branch: the branch changes 11 judgeable files"
            in _flat(result.stderr)
        ), result.stderr


# ---------------------------------------------------------------------------
# One owner says which review is owed; no reader re-asks the lane
# ---------------------------------------------------------------------------


class TestTheExitEightRowAgreesWithTheLane:
    def test_the_row_lets_a_lane_review_name_every_chunk_as_the_code_offers(self):
        """Round 6 R-4: the lane's review must name every open built chunk, and
        exit 8's refusal offers that line itself (`--chunks <all>` "if this
        review is all of their work"); the SKILL's row said to name only the
        chunk you built. The row now names the lane's case, as the code does."""
        from types import SimpleNamespace  # noqa: PLC0415

        reason = critic_consolidate._chunks_ambiguous_reason(
            SimpleNamespace(chunks=["01", "02"], evidence={}))
        assert "`--chunks 01,02`" in reason and "`--chunks 01`" in reason, reason
        skill = (ROOT / "skills" / "critic" / "SKILL.md").read_text(encoding="utf-8")
        (row,) = [ln for ln in skill.splitlines() if ln.strip().startswith("| **8** |")]
        assert "`per-release lane` rationale" in row and "never pass both" not in row, row


class TestTheLaneHasOneAsker:
    def test_only_the_owners_ask_lane_eligibility(self):
        """`review_owed_after` returns `OWED_LANE` and `short_plan_deferral`
        fills `lane`, so a reader branches on the answer and never re-derives
        it (the class the boundary review found: three re-askers, one of them
        already a bug). Every call site of `lane_eligibility` in the plugin."""
        import ast

        from conftest import plugin_python_sources  # noqa: PLC0415

        sources = plugin_python_sources()
        assert HOOK in sources, "the scan must reach the hook"
        callers: set = set()
        for path in sources:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for fn in ast.walk(tree):
                if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for node in ast.walk(fn):
                    if isinstance(node, ast.Call):
                        f = node.func
                        name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
                        if name == "lane_eligibility":
                            callers.add(f"{path.name}:{fn.name}")
        assert callers == {
            "critic_mode.py:short_plan_deferral",
            "critic_mode.py:review_owed_after",
            "critic_mode.py:_lane_interval",
        }, callers
        assert not hasattr(critic_mode, "with_lane")

    def test_the_deferral_carries_the_lane_without_a_second_step(self, tmp_path):
        _lane_repo(tmp_path / "lane", committed=("01", "02"), in_flight="03")
        assert _deferral(tmp_path / "lane").lane is True
        _lane_repo(tmp_path / "per_pr", committed=("01", "02"), in_flight="03", key=None)
        assert _deferral(tmp_path / "per_pr").lane is False

    def test_the_close_returns_the_kind_it_is_handed(self, monkeypatch):
        """The review close reads `review_owed_after`'s KIND and nothing else:
        handed `OWED_BOUNDARY` while the lane would say it holds, it keeps the
        per-PR boundary, and never asks the lane. Red while it re-asks
        `lane_eligibility` to turn a boundary into the lane."""
        from types import SimpleNamespace

        asked: list = []

        def eligible(*_a, **_k):
            asked.append(1)
            return critic_mode.LaneEligibility(True, "patched eligible", (), in_play=True)

        monkeypatch.setattr(critic_mode, "lane_eligibility", eligible)
        plan = SimpleNamespace(plan_path=Path("plan.md"), is_claim=True)
        monkeypatch.setattr(work_unit, "resolve", lambda _d: plan)
        progress = critic_mode.PlanProgress(3, 2, "03", ("03",), {}, False, {})
        monkeypatch.setattr(critic_mode, "binding_progress", lambda *_a, **_k: progress)
        for kind in (critic_mode.OWED_BOUNDARY, critic_mode.OWED_LANE, critic_mode.OWED_LATER_CHUNK):
            monkeypatch.setattr(
                critic_mode, "review_owed_after", lambda *_a, _k=kind, **_kw: (_k, "owed")
            )
            assert critic_consolidate._plan_owes_a_later_review(Path("."), Path(".prawduct")) == kind
        assert asked == [], "the close re-asked the lane"

    def test_the_extension_deferral_words_the_kind_it_is_handed(self, tmp_path, monkeypatch):
        """The extension deferral's wording follows the kind: on a per_release
        fixture the lane takes, an `OWED_BOUNDARY` answer still reads as the
        per-PR boundary (it infers the cumulative), and `OWED_LANE` as the
        lane's review. Red while it re-asks `lane_eligibility` on a boundary."""
        from test_short_plan_deferral import _short_plan_branch  # noqa: PLC0415

        repo = tmp_path / "lane"
        repo.mkdir()
        _short_plan_branch(repo, committed=("01", "02"), plan_committed=True,
                           state_extra="boundary_review: per_release\n")
        head = _git(repo, "rev-parse", "HEAD").stdout.strip()
        captured = evidence.capture_tree(repo)
        assert evidence.append_fact(repo, "review", "rev-03", {
            "mode": _MODE_CHUNK, "chunks": ["03"], "head_commit": head, "dispatch_commit": head,
            "base_tree": _git(repo, "rev-parse", "HEAD^{tree}").stdout.strip(),
            "head_tree": captured["tree"], "files_changed": ["src/wip.py"],
            "files_reviewed": ["src/wip.py"], "findings": [],
            "counts": {"blocking": 0, "warning": 0, "note": 0},
        })["status"] == "appended"
        _write(repo, "src/wip.py", "# a warning, fixed\n")
        binding = work_unit.resolve(repo)
        progress = critic_mode.binding_progress(repo, binding)
        # Precondition: the lane holds here, so a re-asker WOULD reword a boundary.
        assert critic_mode.lane_eligibility(repo, repo / ".prawduct", binding, progress).eligible
        worded = {}
        for kind in (critic_mode.OWED_BOUNDARY, critic_mode.OWED_LANE):
            monkeypatch.setattr(
                critic_mode, "review_owed_after", lambda *_a, _k=kind, **_kw: (_k, "the plan owes it")
            )
            worded[kind] = critic_mode.extension_deferral_owed(
                repo, repo / ".prawduct", binding, progress
            )
        boundary, lane = worded[critic_mode.OWED_BOUNDARY], worded[critic_mode.OWED_LANE]
        assert boundary is not None and boundary[1].endswith("it infers the cumulative"), boundary
        assert lane is not None and lane[1].endswith(f"it infers {critic_mode.LANE_REVIEW_NAME}"), lane

    def test_one_decision_reads_the_lane_once(self, tmp_path, monkeypatch, capsys):
        """The git work behind the lane (the policy at two revisions, the path
        listing, risk surfaces at two more) is paid once per decision: one
        inference, one review close, one Stop. Red for inference without
        `_one_lane_read`, where the deferral and the lane's `chunk` each ask;
        red for a close or a Stop that re-asks."""
        import importlib.machinery
        import importlib.util

        calls: list = []
        real = critic_mode._lane_eligibility

        def counting(*a, **k):
            calls.append(1)
            return real(*a, **k)

        monkeypatch.setattr(critic_mode, "_lane_eligibility", counting)

        _lane_repo(tmp_path / "clean")
        assert infer_mode(tmp_path / "clean", None)[0] == "chunk"
        assert len(calls) == 1, calls
        calls.clear()
        assert infer_mode(tmp_path / "clean", "chunk")[0] == "chunk"
        assert len(calls) == 1, calls
        # Two inferences are two decisions: the second reads again, so a
        # branch that grows past a bound leaves the lane at the next one.
        calls.clear()
        infer_mode(tmp_path / "clean", None)
        infer_mode(tmp_path / "clean", None)
        assert len(calls) == 2, calls
        # Inside an outer scope an inference joins it, and leaving the outer
        # scope leaves no read behind for the next decision.
        calls.clear()
        with critic_mode._one_lane_read():
            infer_mode(tmp_path / "clean", None)
            infer_mode(tmp_path / "clean", None)
        assert len(calls) == 1, calls
        assert critic_mode._LANE_READ.get() is None

        from test_short_plan_deferral import _short_plan_branch  # noqa: PLC0415

        repo = tmp_path / "close"
        repo.mkdir()
        _short_plan_branch(repo, committed=("01", "02"), plan_committed=True,
                           state_extra="boundary_review: per_release\n")
        head = _git(repo, "rev-parse", "HEAD").stdout.strip()
        captured = evidence.capture_tree(repo)
        assert evidence.append_fact(repo, "review", "rev-03", {
            "mode": _MODE_CHUNK, "chunks": ["03"], "head_commit": head, "dispatch_commit": head,
            "base_tree": _git(repo, "rev-parse", "HEAD^{tree}").stdout.strip(),
            "head_tree": captured["tree"], "files_changed": ["src/wip.py"],
            "files_reviewed": ["src/wip.py"], "findings": [],
            "counts": {"blocking": 0, "warning": 0, "note": 0},
        })["status"] == "appended"
        facts = evidence.read_facts(repo)["facts"]
        fact = next(f for f in facts if f.get("id") == "rev-03")
        calls.clear()
        assert critic_consolidate._plan_owes_a_later_review(
            repo, repo / ".prawduct", facts, fact
        ) == critic_mode.OWED_LANE
        assert len(calls) == 1, calls

        # The Stop, in-process so the count reaches it: the lane branch's last
        # chunk in flight, whose block names the lane's step.
        loader = importlib.machinery.SourceFileLoader("prawduct_hook_lane_reads", str(HOOK))
        hook = importlib.util.module_from_spec(
            importlib.util.spec_from_loader("prawduct_hook_lane_reads", loader)
        )
        loader.exec_module(hook)
        prawduct = _lane_repo(tmp_path / "stop", committed=("01", "02"), in_flight="03")
        _arm_stop(prawduct)
        capsys.readouterr()
        calls.clear()
        assert hook.cmd_stop(tmp_path / "stop", {}) == 2
        assert critic_mode.LANE_REVIEW_NAME in _flat(capsys.readouterr().err)
        assert len(calls) == 1, calls
