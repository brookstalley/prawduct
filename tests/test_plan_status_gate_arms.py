"""``plan_status.gate_arms`` — the one Stop-gate arming predicate (ST2, Wave 2 of #1050).

Red-first against the old rule: develop's ``cmd_stop`` armed on an unticked-box count, so a
plan with every box ticked disarmed. Here arming is binding-derived and box-blind.
"""
from __future__ import annotations

from pathlib import Path

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
