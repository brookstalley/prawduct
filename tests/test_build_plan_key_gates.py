"""Editing the `build_plan:` key of project-state.yaml cannot switch off a gate (#856).

Removing `build_plan:` was once recorded as "verified inert to tooling" while it
silently downgraded the reflection gate and turned the Critic gate off, through
`gates._has_build_plan_in_state`. A later `active_build_plan: null` clearing did
the same through a different key. Both were caught only in review.

What is pinned here is the DECIDED half: while an active build-plan FILE governs
the work, the state key is not what decides whether the Critic or reflection gate
runs, so any spelling of "the key is gone" must leave both at full strength. The
spellings are the key absent, present with a null value, present with no value,
and `active_build_plan` nulled.

The other half was decided by #1051 (ST7): the state key's chunks are no longer
a gate input at all, so a repo whose ONLY plan source is that key arms nothing —
pinned in `test_critic_gate_fallthrough.py::TestTheGateArmsOnTheBinding`.
"""
from __future__ import annotations

import pytest

from test_critic_gate_fallthrough import _CODE_DIFF, _active_plan_repo, _run_stop

_STATE_SPELLINGS = {
    "key_absent": "product:\n  name: demo\n",
    "key_null": "product:\n  name: demo\nbuild_plan: null\n",
    "key_empty": "product:\n  name: demo\nbuild_plan:\n",
    "active_build_plan_null": "product:\n  name: demo\nactive_build_plan: null\n",
    "key_with_completed_chunks": (
        "product:\n  name: demo\nbuild_plan:\n  strategy: s\n  chunks:\n"
        "    - id: 1\n      status: complete\n"
    ),
}


def _with_state(tmp_path, state: str):
    prawduct = _active_plan_repo(tmp_path, chunk_type="code")
    (prawduct / "project-state.yaml").write_text(state)
    return prawduct


@pytest.mark.parametrize("spelling", sorted(_STATE_SPELLINGS))
def test_critic_gate_still_fires_with_state_key_edited(tmp_path, spelling):
    _with_state(tmp_path, _STATE_SPELLINGS[spelling])
    result = _run_stop(tmp_path, status=_CODE_DIFF)
    assert result.returncode == 2, (
        f"{spelling}: the Critic gate went quiet when the state key changed. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "CRITIC" in result.stderr, result.stderr


@pytest.mark.parametrize("spelling", sorted(_STATE_SPELLINGS))
def test_reflection_gate_still_fires_with_state_key_edited(tmp_path, spelling):
    prawduct = _with_state(tmp_path, _STATE_SPELLINGS[spelling])
    (prawduct / ".session-reflected").write_text("")
    result = _run_stop(tmp_path, status=_CODE_DIFF)
    assert result.returncode == 2, (
        f"{spelling}: the reflection gate went quiet when the state key changed. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "REFLECTION" in result.stderr, result.stderr


def test_control_critic_gate_is_not_simply_always_on(tmp_path):
    """Contrast: a designer-handoff chunk skips the Critic gate with the same
    state edit, so the assertions above are about the key and not a gate that
    fires regardless."""
    prawduct = _active_plan_repo(tmp_path, chunk_type="designer-handoff")
    (prawduct / "project-state.yaml").write_text(_STATE_SPELLINGS["key_absent"])
    result = _run_stop(tmp_path, status=_CODE_DIFF)
    assert result.returncode == 0, result.stderr
