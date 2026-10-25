"""``plan_status.gate_arms`` — the one Stop-gate arming predicate (ST2, Wave 2 of #1050).

Red-first against the old rule: develop's ``cmd_stop`` armed on an unticked-box count, so a
plan with every box ticked disarmed. Here arming is binding-derived and box-blind.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from lib import plan_status, work_unit


def _binding(state: str, plan_path: Path | None) -> work_unit.Binding:
    return work_unit.Binding(
        state=state,
        scope="s" if state == "bound" else None,
        plan_path=plan_path,
        role="integration" if state == "bound" else None,
        reason=None,
        chosen_by="binding" if state == "bound" else "none",
    )


def _live_plan(tmp_path: Path, ticked: bool) -> Path:
    art = tmp_path / ".prawduct" / "artifacts"
    art.mkdir(parents=True)
    box = "[x]" if ticked else "[ ]"
    p = art / "build-plan-s.md"
    p.write_text(
        "---\nartifact: build-plan\nversion: 2\nscope: s\nbranch: feature/s\n---\n\n## Status\n\n"
        f"- {box} Chunk 01: a\n\n## Build Chunks\n\n### Chunk 01: a\n\n- **Deliverables:** x\n",
        encoding="utf-8",
    )
    return p


def test_bound_live_plan_arms_with_every_box_unticked(tmp_path):
    assert plan_status.gate_arms(_binding("bound", _live_plan(tmp_path, ticked=False))) is True


def test_bound_live_plan_arms_with_every_box_ticked(tmp_path):
    # The old rule disarmed here (unticked count == 0). The tick is not a carrier any more.
    assert plan_status.gate_arms(_binding("bound", _live_plan(tmp_path, ticked=True))) is True


def test_broken_binding_arms_fail_closed():
    assert plan_status.gate_arms(_binding("broken", None)) is True


def test_unbound_never_arms():
    assert plan_status.gate_arms(_binding("unbound", None)) is False


def test_bound_to_an_archived_plan_does_not_arm(tmp_path):
    p = tmp_path / ".prawduct" / "artifacts" / "archive" / "build-plan-s.md"
    p.parent.mkdir(parents=True)
    p.write_text("---\nartifact: build-plan\nscope: s\n---\n", encoding="utf-8")
    assert plan_status.gate_arms(_binding("bound", p)) is False


def test_bound_to_a_missing_plan_file_does_not_arm(tmp_path):
    assert plan_status.gate_arms(_binding("bound", tmp_path / "nope.md")) is False


def test_a_repo_rooted_under_an_archive_directory_still_arms(tmp_path):
    """Cumulative R-1: the archive test read the WHOLE absolute path, so a checkout at
    `~/archive/<repo>` read every bound live plan as archived and the Stop gates never
    armed. Only an `archive` component BELOW the repo's `artifacts/` archives a plan."""
    root = tmp_path / "archive" / "repo"
    plan = _live_plan(root, ticked=False)
    assert "archive" in plan.resolve().parts  # the fixture reaches the defect's shape
    assert plan_status.gate_arms(_binding("bound", plan)) is True


def test_under_an_archive_root_an_archived_plan_still_does_not_arm(tmp_path):
    # The control: the same placement, the plan under `artifacts/archive/`.
    p = tmp_path / "archive" / "repo" / ".prawduct" / "artifacts" / "archive" / "build-plan-s.md"
    p.parent.mkdir(parents=True)
    p.write_text("---\nartifact: build-plan\nscope: s\n---\n", encoding="utf-8")
    assert plan_status.gate_arms(_binding("bound", p)) is False


# #856 — "pin that a build_plan key edit cannot switch off two gates"
_STATE_SPELLINGS = {
    "key_absent": "product:\n  name: demo\n",
    "key_null": "product:\n  name: demo\nbuild_plan: null\n",
    "chunks_all_complete": (
        "product:\n  name: demo\nbuild_plan:\n  strategy: s\n  chunks:\n"
        "    - id: 1\n      status: complete\n"
    ),
}


@pytest.mark.parametrize("spelling", sorted(_STATE_SPELLINGS))
def test_a_build_plan_key_edit_cannot_disarm_a_bound_live_plan(tmp_path, spelling):
    """#856, at the predicate both gates read. With a bound live plan, no spelling
    of "project-state.yaml's `build_plan:` is gone or finished" — absent, null, or
    every chunk `status: complete` — may disarm: `gate_arms` reads the binding, never
    the state key, so the Critic and reflection gates keep full strength.

    The hook-level twin (both gates, through `cmd_stop`, five spellings) is
    `tests/test_build_plan_key_gates.py`; the inverse — an unbound checkout whose
    state lists an unfinished chunk arms nothing — is
    `test_critic_gate_fallthrough.py::TestTheGateArmsOnTheBinding::test_unfinished_state_chunks_on_an_unbound_branch_arm_nothing`.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    for args in (
        ("init", "-q", "-b", "feature/s"),
        ("config", "user.email", "t@example.com"),
        ("config", "user.name", "T"),
    ):
        subprocess.run(["git", *args], cwd=str(repo), check=True, capture_output=True)
    _live_plan(repo, ticked=False)
    (repo / ".prawduct" / "project-state.yaml").write_text(_STATE_SPELLINGS[spelling])
    binding = work_unit.resolve(repo)
    assert binding.state == "bound", binding  # the subject is reached
    assert plan_status.gate_arms(binding) is True

