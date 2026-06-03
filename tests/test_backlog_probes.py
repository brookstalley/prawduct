"""Tests for lib/backlog_probes.py — the legacy-backlog-format probe.

Imports the probe module (and its advisory_store dependency) directly from the
plugin's `lib/`. Covers v1.7.0 Chunk 03: the content-scan helper, the probe's trigger and
resolution conditions, idempotency (stable id across incidental count changes),
the >5-item / none-structured floor, and that registration is idempotent.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib import backlog_probes as _bp  # noqa: E402
from lib import advisory_store as _adv  # noqa: E402

count_backlog_items = _bp.count_backlog_items
legacy_backlog_format_probe = _bp.legacy_backlog_format_probe
register_backlog_probes = _bp.register_backlog_probes
ProjectState = _adv.ProjectState
Codebase = _adv.Codebase
compute_id = _adv.compute_id
run_all_probes = _adv.run_all_probes
clear_registry = _adv.clear_registry


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_registry()
    yield
    clear_registry()


def _make_backlog(tmp_path: Path, body: str) -> Codebase:
    """Write .prawduct/backlog.md under a temp product and return its Codebase."""
    prawduct = tmp_path / ".prawduct"
    prawduct.mkdir(parents=True, exist_ok=True)
    (prawduct / "backlog.md").write_text(body, encoding="utf-8")
    return Codebase(root=tmp_path)


# Six legacy items, old headings, no structured ids.
_LEGACY_BACKLOG = """# Backlog — test

<!-- A comment with a bullet that must NOT be counted:
     - **[PFX-XXXX]** example item in the conventions header -->

## Active — next up

- **First thing** (reflection) some body

## Queue

- **Second** (critic)
- **Third** thing
- **Fourth** thing
- **Fifth** thing
- **Sixth** thing
"""


# =============================================================================
# count_backlog_items — content-scan helper
# =============================================================================


class TestCountBacklogItems:
    def test_counts_top_level_items_ignoring_comments(self):
        total, structured = count_backlog_items(_LEGACY_BACKLOG)
        assert total == 6  # the commented example bullet is excluded
        assert structured == 0

    def test_counts_structured_items(self):
        text = (
            "## Open\n\n"
            "- **[STH-K7p2]** structured one\n"
            "  `effort: M · impact: M · area: stop-hook · status: open`\n"
            "- **legacy two** no id\n"
        )
        total, structured = count_backlog_items(text)
        assert total == 2
        assert structured == 1

    def test_empty_backlog(self):
        assert count_backlog_items("# Backlog\n\n## Open\n") == (0, 0)


# =============================================================================
# legacy_backlog_format_probe — trigger / resolution
# =============================================================================


class TestLegacyBacklogFormatProbe:
    def test_fires_on_legacy_backlog(self, tmp_path: Path):
        codebase = _make_backlog(tmp_path, _LEGACY_BACKLOG)
        cands = legacy_backlog_format_probe(ProjectState({}), codebase)
        assert len(cands) == 1
        c = cands[0]
        assert c.type == "legacy-backlog-format"
        assert c.recommended_action == "/prawduct:backlog migrate"
        assert "6 backlog items" in c.trigger_summary
        # Legacy headings surface as supporting (stable) evidence.
        assert any("legacy section headings" in e for e in c.evidence)

    def test_resolved_when_format_version_set(self, tmp_path: Path):
        codebase = _make_backlog(tmp_path, _LEGACY_BACKLOG)
        state = ProjectState({"backlog_format_version": 2})
        assert legacy_backlog_format_probe(state, codebase) == []

    def test_silent_below_item_floor(self, tmp_path: Path):
        # 5 items — at the floor, does not fire (requirements: >5).
        body = "## Open\n\n" + "".join(f"- **item {i}**\n" for i in range(5))
        codebase = _make_backlog(tmp_path, body)
        assert legacy_backlog_format_probe(ProjectState({}), codebase) == []

    def test_silent_when_any_item_structured(self, tmp_path: Path):
        # >5 items but one is already migrated → mid-flight, don't nag.
        body = "## Open\n\n- **[STH-aaaa]** done\n" + "".join(
            f"- **item {i}**\n" for i in range(6)
        )
        codebase = _make_backlog(tmp_path, body)
        assert legacy_backlog_format_probe(ProjectState({}), codebase) == []

    def test_silent_when_no_backlog_file(self, tmp_path: Path):
        (tmp_path / ".prawduct").mkdir()
        codebase = Codebase(root=tmp_path)
        assert legacy_backlog_format_probe(ProjectState({}), codebase) == []

    def test_id_stable_across_count_change(self, tmp_path: Path):
        """Adding a legacy item changes the live summary but NOT the id —
        evidence is count-independent, so the advisory doesn't churn (A2)."""
        cb1 = _make_backlog(tmp_path, _LEGACY_BACKLOG)
        c1 = legacy_backlog_format_probe(ProjectState({}), cb1)[0]
        cb2 = _make_backlog(tmp_path, _LEGACY_BACKLOG + "- **Seventh** thing\n")
        c2 = legacy_backlog_format_probe(ProjectState({}), cb2)[0]
        id1 = compute_id("backlog", c1.type, 1, c1.evidence)
        id2 = compute_id("backlog", c2.type, 1, c2.evidence)
        assert id1 == id2
        assert c1.trigger_summary != c2.trigger_summary  # live count differs


# =============================================================================
# registration
# =============================================================================


class TestRegisterBacklogProbes:
    def test_registers_and_runs_via_roster(self, tmp_path: Path):
        register_backlog_probes()
        codebase = _make_backlog(tmp_path, _LEGACY_BACKLOG)
        cands = run_all_probes(ProjectState({}), codebase)
        # run_all_probes enriches feature/probe_version from the registration.
        assert any(c.type == "legacy-backlog-format" for c in cands)
        c = next(c for c in cands if c.type == "legacy-backlog-format")
        assert c.feature == "backlog"
        assert c.probe_version == 1

    def test_registration_idempotent(self, tmp_path: Path):
        register_backlog_probes()
        register_backlog_probes()
        codebase = _make_backlog(tmp_path, _LEGACY_BACKLOG)
        cands = [
            c for c in run_all_probes(ProjectState({}), codebase)
            if c.type == "legacy-backlog-format"
        ]
        assert len(cands) == 1  # not duplicated
