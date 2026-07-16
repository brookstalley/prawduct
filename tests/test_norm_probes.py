"""Tests for the norm-lifecycle post-sync advisory probes (docs/norms.md).

Each probe is a pure, deterministic ``ProbeFn(state, codebase)`` reading only
machine-readable hooks (dated ``revisit:`` values, backlog-id literals on norm
Why/Status lines, the ``Status: in-transition`` token, structural presence of
``## Direction`` sections and strategy-class artifacts). Per probe we drive the
positive fire, the named negative-silence conditions, and advisory-id stability
(one stable id across two runs with different firing items). A final
repo-coupled tripwire test asserts ZERO norm-lifecycle advisories fire against
THIS repo's committed state (the rare-and-high-signal bar) — deliberately not
hermetic, so ratifying a Direction section here without the sweep stamp fails it. Registry isolation mirrors the sibling
probe tests (autouse ``clear_registry``).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lib.advisory_store import (
    Codebase,
    ProjectState,
    clear_registry,
    compute_id,
    load_project_state,
    make_codebase,
    run_all_probes,
)
from lib import norm_probes as np


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_registry()
    yield
    clear_registry()


# --- fixtures / helpers -------------------------------------------------------


def _cb(tmp_path) -> Codebase:
    return Codebase(root=tmp_path)


def _write_backlog(tmp_path, body: str) -> None:
    d = tmp_path / ".prawduct"
    d.mkdir(parents=True, exist_ok=True)
    (d / "backlog.md").write_text(body, encoding="utf-8")


def _write_artifact(tmp_path, name: str, body: str) -> None:
    d = tmp_path / ".prawduct" / "artifacts"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(body, encoding="utf-8")


def _days_ago(n: int) -> str:
    return (datetime.now(timezone.utc).date() - timedelta(days=n)).isoformat()


def _days_ahead(n: int) -> str:
    return (datetime.now(timezone.utc).date() + timedelta(days=n)).isoformat()


def _item(item_id: str, *, section: str = "Open", status: str = "open", extra: str = "") -> str:
    """A single structured backlog item under its section heading."""
    bar = f"effort: M · impact: M · area: x · source: user · added: {_days_ago(120)} · status: {status}"
    if extra:
        bar += f" · {extra}"
    return f"## {section}\n- **[{item_id}]** a norm-relevant item\n  `{bar}`\n"


def _direction_artifact(*entries: str) -> str:
    """A strategy-class-shaped artifact with a `## Direction` section."""
    body = "# Observability Strategy\n\nSome descriptive prose.\n\n## Direction\n\n"
    body += "\n".join(entries)
    return body + "\n"


# Preferences files for the unratified probe's second arm: an Enforcement index
# table without / with the norm columns (Audit home, Why). Both carry the
# mechanism-descriptions table too, so the header scan must pick the right one.
_PREFS_WITHOUT_NORM_COLUMNS = (
    "# Project Preferences\n\n## Enforcement\n\n"
    "| Mechanism | Where it lives | What it catches | Trade-off |\n|---|---|---|---|\n"
    "| **Test** | `tests/` | structural rules | re-validation cost |\n\n"
    "| Preference | Mechanism | Enforcement artifact |\n|---|---|---|\n"
    "| naming | Critic | reviewer reads the diff |\n"
)
_PREFS_WITH_NORM_COLUMNS = (
    "# Project Preferences\n\n## Enforcement\n\n"
    "| Mechanism | Where it lives | What it catches | Trade-off |\n|---|---|---|---|\n"
    "| **Test** | `tests/` | structural rules | re-validation cost |\n\n"
    "| Preference / norm | Mechanism | Enforcement artifact | Audit home | Why |\n"
    "|---|---|---|---|---|\n"
    "| naming | Critic | reviewer reads the diff | janitor | consistency |\n"
)


# =============================================================================
# revisit-due
# =============================================================================


class TestRevisitDueProbe:
    def test_fires_on_past_dated_revisit_open_item(self, tmp_path):
        _write_backlog(tmp_path, _item("EXC-1A2B", extra=f"revisit: {_days_ago(3)}"))
        out = np.probe_revisit_due(ProjectState({}), _cb(tmp_path))
        assert len(out) == 1
        assert out[0].type == "revisit-due"
        assert "EXC-1A2B" in out[0].trigger_summary

    def test_silent_when_no_revisit(self, tmp_path):
        _write_backlog(tmp_path, _item("EXC-1A2B"))
        assert np.probe_revisit_due(ProjectState({}), _cb(tmp_path)) == []

    def test_silent_on_future_date(self, tmp_path):
        _write_backlog(tmp_path, _item("EXC-1A2B", extra=f"revisit: {_days_ahead(10)}"))
        assert np.probe_revisit_due(ProjectState({}), _cb(tmp_path)) == []

    def test_silent_on_non_date_trigger_value(self, tmp_path):
        # Event-bound trigger — janitor's job, never probe-fired.
        _write_backlog(tmp_path, _item("EXC-1A2B", extra="revisit: when the collector export ships"))
        assert np.probe_revisit_due(ProjectState({}), _cb(tmp_path)) == []

    def test_silent_when_item_closed(self, tmp_path):
        # A shipped item's clock is moot even if past-due.
        _write_backlog(
            tmp_path,
            _item("EXC-1A2B", section="Archive", status="shipped", extra=f"revisit: {_days_ago(30)}"),
        )
        assert np.probe_revisit_due(ProjectState({}), _cb(tmp_path)) == []

    def test_no_backlog_file(self, tmp_path):
        assert np.probe_revisit_due(ProjectState({}), _cb(tmp_path)) == []

    def test_advisory_id_stable_across_different_due_items(self, tmp_path):
        # Run 1: EXC-1A2B due. Run 2: a different item ABC-9Z8Y due. Same id.
        _write_backlog(tmp_path, _item("EXC-1A2B", extra=f"revisit: {_days_ago(3)}"))
        a = np.probe_revisit_due(ProjectState({}), _cb(tmp_path))[0]
        _write_backlog(tmp_path, _item("ABC-9Z8Y", extra=f"revisit: {_days_ago(9)}"))
        b = np.probe_revisit_due(ProjectState({}), _cb(tmp_path))[0]
        assert _id(a) == _id(b)
        assert a.trigger_summary != b.trigger_summary  # the message lists the (different) items


# =============================================================================
# dead-why
# =============================================================================


class TestDeadWhyProbe:
    def test_fires_when_why_cites_shipped_id(self, tmp_path):
        _write_backlog(tmp_path, _item("MIG-4C1K", section="Archive", status="shipped"))
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact(
                "- **All telemetry rides OpenTelemetry.**\n"
                "  Why: the MIG-4C1K migration made a second system redundant.\n"
                "  Status: steady-state\n"
            ),
        )
        out = np.probe_dead_why(ProjectState({}), _cb(tmp_path))
        assert len(out) == 1
        assert out[0].type == "dead-why"
        assert "observability-strategy.md→MIG-4C1K" in out[0].trigger_summary

    def test_fires_when_status_cites_archived_id(self, tmp_path):
        _write_backlog(tmp_path, _item("OBS-4C1K", section="Archive", status="dropped"))
        _write_artifact(
            tmp_path,
            "architecture.md",
            _direction_artifact(
                "- **Spans everywhere.**\n"
                "  Why: causality across turns.\n"
                "  Status: in-transition — tracked in OBS-4C1K\n"
            ),
        )
        out = np.probe_dead_why(ProjectState({}), _cb(tmp_path))
        assert len(out) == 1 and "architecture.md→OBS-4C1K" in out[0].trigger_summary

    def test_silent_when_cited_id_is_open(self, tmp_path):
        _write_backlog(tmp_path, _item("OBS-4C1K", status="open"))
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact("- **X.**\n  Why: tracked in OBS-4C1K.\n"),
        )
        assert np.probe_dead_why(ProjectState({}), _cb(tmp_path)) == []

    def test_silent_when_no_direction_section(self, tmp_path):
        # The id is on a Why-looking line but NOT under a ## Direction heading.
        _write_backlog(tmp_path, _item("OBS-4C1K", section="Archive", status="shipped"))
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            "# Strategy\n\n## Notes\n\nWhy: OBS-4C1K shipped.\n",
        )
        assert np.probe_dead_why(ProjectState({}), _cb(tmp_path)) == []

    def test_silent_when_id_not_in_backlog(self, tmp_path):
        _write_backlog(tmp_path, _item("KEEP-0000", status="open"))
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact("- **X.**\n  Why: tracked in GONE-9Z9Z.\n"),
        )
        assert np.probe_dead_why(ProjectState({}), _cb(tmp_path)) == []

    def test_fires_when_cited_id_is_on_a_wrapped_why_continuation(self, tmp_path):
        # The spec's own Anatomy example wraps its Why: across physical lines —
        # an id after the wrap point must still be mechanically detectable.
        _write_backlog(tmp_path, _item("MIG-4C1K", section="Archive", status="shipped"))
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact(
                "- **All telemetry rides OpenTelemetry.**\n"
                "  Why: one substrate for causality across turns, tools, and eval;\n"
                "  the MIG-4C1K migration made a second correlation system redundant.\n"
            ),
        )
        out = np.probe_dead_why(ProjectState({}), _cb(tmp_path))
        assert len(out) == 1 and "observability-strategy.md→MIG-4C1K" in out[0].trigger_summary

    def test_detached_paragraph_after_blank_line_does_not_join_the_why(self, tmp_path):
        # Descriptive surroundings separated by a blank line stand alone — an id
        # there is not part of the Why and must not fire.
        _write_backlog(tmp_path, _item("MIG-4C1K", section="Archive", status="shipped"))
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact(
                "- **X.**\n  Why: because reasons.\n\n  current-state note: MIG-4C1K shipped last quarter.\n"
            ),
        )
        assert np.probe_dead_why(ProjectState({}), _cb(tmp_path)) == []

    def test_iso_datestamp_shape_does_not_false_fire(self, tmp_path):
        # `ISO-8601` matches the id regex but resolves to no backlog item → no fire.
        _write_backlog(tmp_path, _item("KEEP-0000", status="open"))
        _write_artifact(
            tmp_path,
            "api-contract.md",
            _direction_artifact("- **UTC.**\n  Why: all timestamps are ISO-8601.\n"),
        )
        assert np.probe_dead_why(ProjectState({}), _cb(tmp_path)) == []

    def test_advisory_id_stable_across_different_pairs(self, tmp_path):
        _write_backlog(tmp_path, _item("MIG-4C1K", section="Archive", status="shipped"))
        _write_artifact(
            tmp_path, "observability-strategy.md", _direction_artifact("- **X.**\n  Why: MIG-4C1K done.\n")
        )
        a = np.probe_dead_why(ProjectState({}), _cb(tmp_path))[0]
        # Different artifact + different dead id → same advisory id, different message.
        (tmp_path / ".prawduct" / "artifacts" / "observability-strategy.md").unlink()
        _write_backlog(tmp_path, _item("SEC-8H3R", section="Archive", status="dropped"))
        _write_artifact(
            tmp_path, "security-model.md", _direction_artifact("- **Y.**\n  Why: SEC-8H3R dropped.\n")
        )
        b = np.probe_dead_why(ProjectState({}), _cb(tmp_path))[0]
        assert _id(a) == _id(b)
        assert a.trigger_summary != b.trigger_summary


# =============================================================================
# stalled-transition
# =============================================================================


class TestStalledTransitionProbe:
    def test_fires_on_stale_in_transition_tracking_item(self, tmp_path):
        # Open tracking item whose only date floor (added:) is well past the window.
        _write_backlog(tmp_path, _item("OBS-4C1K", status="open"))  # added: 120 days ago
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact("- **X.**\n  Status: in-transition — export tracked in OBS-4C1K\n"),
        )
        out = np.probe_stalled_transition(ProjectState({}), _cb(tmp_path))
        assert len(out) == 1
        assert out[0].type == "stalled-transition"
        assert "observability-strategy.md→OBS-4C1K" in out[0].trigger_summary

    def test_fires_when_tracking_id_is_on_a_wrapped_status_continuation(self, tmp_path):
        # A Status: line that soft-wraps before naming its tracking item (the
        # Anatomy example's shape) must still be seen by the stall scan.
        _write_backlog(tmp_path, _item("OBS-4C1K", status="open"))  # added: 120 days ago
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact(
                "- **X.**\n"
                "  Status: in-transition — collector export\n"
                "  tracked in OBS-4C1K; interim: new work emits spans anyway.\n"
            ),
        )
        out = np.probe_stalled_transition(ProjectState({}), _cb(tmp_path))
        assert len(out) == 1 and "observability-strategy.md→OBS-4C1K" in out[0].trigger_summary

    def test_silent_when_tracking_item_recently_edited(self, tmp_path):
        # A fresh `reviewed:` floor advances past the window → healthy transition.
        _write_backlog(
            tmp_path,
            _item("OBS-4C1K", status="open", extra=f"reviewed: {_days_ago(2)}"),
        )
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact("- **X.**\n  Status: in-transition — tracked in OBS-4C1K\n"),
        )
        assert np.probe_stalled_transition(ProjectState({}), _cb(tmp_path)) == []

    def test_silent_when_no_date_signal(self, tmp_path):
        # Legacy id-only item with no metadata bar → no floor → fail toward silence.
        _write_backlog(tmp_path, "## Open\n- **[OBS-4C1K]** legacy item, no bar\n")
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact("- **X.**\n  Status: in-transition — tracked in OBS-4C1K\n"),
        )
        assert np.probe_stalled_transition(ProjectState({}), _cb(tmp_path)) == []

    def test_silent_when_not_in_transition(self, tmp_path):
        _write_backlog(tmp_path, _item("OBS-4C1K", status="open"))
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact("- **X.**\n  Status: steady-state\n  Why: tracked in OBS-4C1K\n"),
        )
        assert np.probe_stalled_transition(ProjectState({}), _cb(tmp_path)) == []

    def test_silent_when_tracking_item_shipped(self, tmp_path):
        # A dead tracking item is dead-why's job, not the stall probe's.
        _write_backlog(tmp_path, _item("OBS-4C1K", section="Archive", status="shipped"))
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact("- **X.**\n  Status: in-transition — tracked in OBS-4C1K\n"),
        )
        assert np.probe_stalled_transition(ProjectState({}), _cb(tmp_path)) == []

    def test_advisory_id_stable_across_different_stalls(self, tmp_path):
        _write_backlog(tmp_path, _item("OBS-4C1K", status="open"))
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact("- **X.**\n  Status: in-transition — tracked in OBS-4C1K\n"),
        )
        a = np.probe_stalled_transition(ProjectState({}), _cb(tmp_path))[0]
        (tmp_path / ".prawduct" / "artifacts" / "observability-strategy.md").unlink()
        _write_backlog(tmp_path, _item("SEC-9Z8Y", status="open"))
        _write_artifact(
            tmp_path,
            "security-model.md",
            _direction_artifact("- **Y.**\n  Status: in-transition — tracked in SEC-9Z8Y\n"),
        )
        b = np.probe_stalled_transition(ProjectState({}), _cb(tmp_path))[0]
        assert _id(a) == _id(b)


# =============================================================================
# norm-registry-unratified
# =============================================================================


class TestNormRegistryUnratifiedProbe:
    def test_fires_when_strategy_artifact_but_no_direction(self, tmp_path):
        _write_artifact(tmp_path, "security-model.md", "# Security Model\n\nDescriptive prose only.\n")
        out = np.probe_norm_registry_unratified(ProjectState({}), _cb(tmp_path))
        assert len(out) == 1
        assert out[0].type == "norm-registry-unratified"
        assert out[0].recommended_action == "/prawduct:doctor"

    def test_silent_when_direction_present(self, tmp_path):
        _write_artifact(tmp_path, "security-model.md", _direction_artifact("- **X.**\n  Why: because.\n"))
        assert np.probe_norm_registry_unratified(ProjectState({}), _cb(tmp_path)) == []

    def test_silent_when_ratified_fact_recorded(self, tmp_path):
        # "no norms to ratify" is a valid recorded answer that clears it for everyone.
        _write_artifact(tmp_path, "security-model.md", "# Security Model\n\nProse.\n")
        state = ProjectState({np.RATIFIED_FACT: "none — no norms to ratify"})
        assert np.probe_norm_registry_unratified(state, _cb(tmp_path)) == []

    def test_silent_when_no_strategy_artifact(self, tmp_path):
        # A non-strategy artifact with no Direction section must not trip it.
        _write_artifact(tmp_path, "build-plan-foo.md", "# Build Plan\n\nChunks.\n")
        assert np.probe_norm_registry_unratified(ProjectState({}), _cb(tmp_path)) == []

    # --- second arm: the Enforcement index table lacks the norm columns -------

    def test_fires_when_direction_present_but_table_lacks_norm_columns(self, tmp_path):
        # Ratification began (Direction exists) but the index can't carry it.
        _write_artifact(tmp_path, "security-model.md", _direction_artifact("- **X.**\n  Why: because.\n"))
        _write_artifact(tmp_path, "project-preferences.md", _PREFS_WITHOUT_NORM_COLUMNS)
        out = np.probe_norm_registry_unratified(ProjectState({}), _cb(tmp_path))
        assert len(out) == 1
        assert "Enforcement table lacks the norm columns" in out[0].trigger_summary
        assert out[0].recommended_action == "/prawduct:doctor"

    def test_silent_when_direction_present_and_table_has_norm_columns(self, tmp_path):
        _write_artifact(tmp_path, "security-model.md", _direction_artifact("- **X.**\n  Why: because.\n"))
        _write_artifact(tmp_path, "project-preferences.md", _PREFS_WITH_NORM_COLUMNS)
        assert np.probe_norm_registry_unratified(ProjectState({}), _cb(tmp_path)) == []

    def test_silent_when_table_lacks_columns_but_no_strategy_artifact(self, tmp_path):
        # The strategy-artifact gate scopes BOTH arms (docs/norms.md § Adoption):
        # a product with no architectural-direction artifacts — this repo's own
        # shape — has nothing to ratify, so a pre-norm table alone never fires.
        _write_artifact(tmp_path, "build-plan-foo.md", "# Build Plan\n\nChunks.\n")
        _write_artifact(tmp_path, "project-preferences.md", _PREFS_WITHOUT_NORM_COLUMNS)
        assert np.probe_norm_registry_unratified(ProjectState({}), _cb(tmp_path)) == []

    def test_silent_when_prefs_has_no_index_table(self, tmp_path):
        # Only the mechanism-descriptions table (no `Preference…` header): nothing
        # to extend → fail toward silence; structural absence is arm 1's job.
        _write_artifact(tmp_path, "security-model.md", _direction_artifact("- **X.**\n  Why: because.\n"))
        prefs = (
            "# Project Preferences\n\n## Enforcement\n\n"
            "| Mechanism | Where it lives | What it catches | Trade-off |\n|---|---|---|---|\n"
            "| **Test** | `tests/` | structural rules | re-validation cost |\n"
        )
        _write_artifact(tmp_path, "project-preferences.md", prefs)
        assert np.probe_norm_registry_unratified(ProjectState({}), _cb(tmp_path)) == []

    def test_ratified_fact_suppresses_second_arm_too(self, tmp_path):
        _write_artifact(tmp_path, "security-model.md", _direction_artifact("- **X.**\n  Why: because.\n"))
        _write_artifact(tmp_path, "project-preferences.md", _PREFS_WITHOUT_NORM_COLUMNS)
        state = ProjectState({np.RATIFIED_FACT: "2026-07-16"})
        assert np.probe_norm_registry_unratified(state, _cb(tmp_path)) == []

    def test_advisory_id_stable_across_arms(self, tmp_path):
        # Arm 1 (no Direction anywhere) and arm 2 (Direction present, columns
        # missing) must share one advisory id — the evidence is arm-independent.
        _write_artifact(tmp_path, "security-model.md", "# Security Model\n\nProse.\n")
        a = np.probe_norm_registry_unratified(ProjectState({}), _cb(tmp_path))[0]
        _write_artifact(tmp_path, "security-model.md", _direction_artifact("- **X.**\n  Why: because.\n"))
        _write_artifact(tmp_path, "project-preferences.md", _PREFS_WITHOUT_NORM_COLUMNS)
        b = np.probe_norm_registry_unratified(ProjectState({}), _cb(tmp_path))[0]
        assert _id(a) == _id(b)
        assert a.trigger_summary != b.trigger_summary  # the live arm(s) are named


# =============================================================================
# norm-health-sweep-overdue
# =============================================================================


class TestNormHealthSweepOverdueProbe:
    def test_fires_when_direction_and_no_stamp(self, tmp_path):
        _write_artifact(tmp_path, "architecture.md", _direction_artifact("- **X.**\n  Why: because.\n"))
        out = np.probe_norm_health_sweep_overdue(ProjectState({}), _cb(tmp_path))
        assert len(out) == 1
        assert out[0].type == "norm-health-sweep-overdue"
        assert out[0].recommended_action == "/prawduct:janitor"

    def test_fires_when_stamp_stale(self, tmp_path):
        _write_artifact(tmp_path, "architecture.md", _direction_artifact("- **X.**\n  Why: because.\n"))
        state = ProjectState({np.SWEEP_STAMP: _days_ago(np.SWEEP_WINDOW_DAYS + 5)})
        assert len(np.probe_norm_health_sweep_overdue(state, _cb(tmp_path))) == 1

    def test_silent_when_stamp_recent(self, tmp_path):
        _write_artifact(tmp_path, "architecture.md", _direction_artifact("- **X.**\n  Why: because.\n"))
        state = ProjectState({np.SWEEP_STAMP: _days_ago(5)})
        assert np.probe_norm_health_sweep_overdue(state, _cb(tmp_path)) == []

    def test_silent_when_no_direction(self, tmp_path):
        # No norms → nothing to sweep, even with a strategy artifact present.
        _write_artifact(tmp_path, "architecture.md", "# Architecture\n\nProse.\n")
        assert np.probe_norm_health_sweep_overdue(ProjectState({}), _cb(tmp_path)) == []


# =============================================================================
# registration + roster integration
# =============================================================================


class TestRegistration:
    def test_register_adds_five_probes(self):
        from lib import advisory_store

        np.register()
        keys = set(advisory_store._REGISTRY)
        assert keys == {
            "norm-lifecycle:revisit-due",
            "norm-lifecycle:dead-why",
            "norm-lifecycle:stalled-transition",
            "norm-lifecycle:norm-registry-unratified",
            "norm-lifecycle:norm-health-sweep-overdue",
        }

    def test_run_all_probes_stamps_feature_and_version(self, tmp_path):
        _write_backlog(tmp_path, _item("EXC-1A2B", extra=f"revisit: {_days_ago(3)}"))
        np.register()
        np.register()  # idempotent — register_probe overwrites
        cands = run_all_probes(ProjectState({}), make_codebase(tmp_path))
        fired = [c for c in cands if c.type == "revisit-due"]
        assert fired and fired[0].feature == "norm-lifecycle"
        assert fired[0].probe_version == np.PROBE_VERSION


# =============================================================================
# repo-coupled tripwire: ZERO norm-lifecycle advisories against THIS repo today
# (deliberately NOT hermetic — it must fail the moment this repo ratifies a
# Direction section without the janitor sweep stamp, forcing that pairing)
# =============================================================================


class TestSilentAgainstThisRepo:
    def test_no_norm_lifecycle_advisories_fire_here_today(self):
        # The rare-and-high-signal bar: this repo has no dated `revisit:` values,
        # no `## Direction` heading in any .prawduct/artifacts/*.md, and no
        # strategy-class artifact present — so every norm-lifecycle probe is
        # silent. (This repo's own preferences Enforcement table predates the
        # norm columns, which is exactly why the unratified probe's second arm
        # is gated on strategy-class artifacts existing.)
        repo_root = Path(__file__).resolve().parents[1]
        state = load_project_state(repo_root)
        codebase = make_codebase(repo_root)
        np.register()
        fired = [c for c in run_all_probes(state, codebase) if c.feature == "norm-lifecycle"]
        assert fired == [], f"norm-lifecycle probes must be silent here; fired: {[c.type for c in fired]}"


def _id(candidate) -> str:
    return compute_id(np.FEATURE, candidate.type, np.PROBE_VERSION, candidate.evidence)
