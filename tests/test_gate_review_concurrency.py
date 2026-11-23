"""The test gate and a Critic review may run together (#678).

The prose in ``building.md`` § The Critic rests on three code facts; each is
pinned here beside it, so the sentence cannot outlive the reason it is true:

1. The recorder's own writes in the worktree are session files consolidation
   exempts by path, so a suite recorded during a review does not refuse it as a
   changed tree (``critic_consolidate.tree_changed_since_dispatch``).
2. Any other file the suite leaves behind is NOT exempt — that is the ordering
   the paragraph states, and the control below keeps it honest.
3. ``verify-resolutions`` refuses while a record is in flight; the other modes
   do not (pinned in ``tests/test_critic_dispatch_stale_evidence.py``).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
sys.path.insert(0, str(ROOT))
from lib import critic_consolidate  # noqa: E402

BUILDING = ROOT / "methodology" / "building.md"
LEAD = "**The test gate and a review may run together.**"


def _paragraph() -> str:
    text = BUILDING.read_text()
    start = text.index(LEAD)
    end = text.find("\n\n", start)
    return text[start:end if end != -1 else None]


class TestTheParagraph:
    def test_it_sits_in_the_critic_section(self):
        text = BUILDING.read_text()
        critic = text[text.index("## The Critic"):text.index("## Creating Pull Requests")]
        assert LEAD in critic

    def test_it_states_the_order_to_start_them(self):
        para = _paragraph()
        assert para.index("`test-evidence record`") < para.index("then dispatch")
        assert "`running:`, never a finding" in para

    def test_it_states_both_orderings_that_remain(self):
        para = _paragraph()
        assert "a file git does not ignore" in para and "consolidation refuses" in para
        assert "`verify-resolutions` refuses mid-run" in para

    def test_it_names_the_reconcile_point(self):
        para = _paragraph()
        assert "reconcile at `/prawduct:pr` Steps 1-2" in para
        assert "not in the review" in para


class TestThePremises:
    @pytest.mark.parametrize("path", [
        ".prawduct/.test-evidence.json",
        ".prawduct/.test-report.xml",
        ".prawduct/.test-report.xml.scope.json",
        "pkg/__pycache__/mod.cpython-314.pyc",
    ])
    def test_the_recorders_writes_are_exempt_from_the_tree_check(self, path):
        assert critic_consolidate._is_session_file(path, "") is True

    @pytest.mark.parametrize("path", [".coverage", "tests/__snapshots__/a.snap", "out/report.html"])
    def test_any_other_file_a_suite_leaves_is_not(self, path):
        assert critic_consolidate._is_session_file(path, "") is False

    def test_the_refusal_mid_run_is_pinned_where_it_lives(self):
        pins = (Path(__file__).parent / "test_critic_dispatch_stale_evidence.py").read_text()
        assert "def test_a_run_in_progress_is_told_to_wait_not_to_run_the_suite" in pins
        assert "def test_other_modes_behave_as_without_evidence" in pins
