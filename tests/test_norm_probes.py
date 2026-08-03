"""Tests for the norm-lifecycle post-sync advisory probes (docs/norms.md).

Each probe is a pure, deterministic ``ProbeFn(state, codebase)`` reading only
machine-readable hooks (dated ``revisit:`` values, backlog-id literals on norm
Why/Status lines, the ``Status: in-transition`` token, structural presence of
``## Direction`` sections and strategy-class artifacts). Per probe we drive the
positive fire, the named negative-silence conditions, and advisory-id stability
(one stable id across two runs with different firing items). A final
repo-coupled tripwire test asserts ZERO norm-lifecycle advisories fire against
THIS repo's committed state (the rare-and-high-signal bar) — deliberately not
hermetic, so drift trips it (the ratification ageing past the sweep window with
no janitor run, a dated ``revisit:`` expiring). Registry isolation mirrors the
sibling probe tests (autouse ``clear_registry``).
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
from lib import core, norm_probes as np


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

# The norm columns exist but no norm has been entered under them: the SHAPE of a
# registry rather than a registry. Distinguishing this from the populated table
# is what keeps "norms are homed here" from meaning "someone added two columns".
# Two shapes, because they exercise different code: a header with no data rows
# at all, and — the discriminating one — data rows whose norm cells are BLANK.
# Only the second reaches the populated-cell check; a fixture with no rows exits
# the loop before it and passes whether that check exists or not.
_PREFS_NORM_COLUMNS_NO_ROWS = (
    "# Project Preferences\n\n## Enforcement\n\n"
    "| Preference / norm | Mechanism | Enforcement artifact | Audit home | Why |\n"
    "|---|---|---|---|---|\n"
)
_PREFS_NORM_COLUMNS_EMPTY_CELLS = (
    "# Project Preferences\n\n## Enforcement\n\n"
    "| Preference / norm | Mechanism | Enforcement artifact | Audit home | Why |\n"
    "|---|---|---|---|---|\n"
    "| naming | Critic | reviewer reads the diff |  |  |\n"
    "| imports | Test | `tests/preferences/test_imports.py` |  |  |\n"
)


def _roadmap_direction_artifact() -> str:
    """A `## Direction` section holding a ROADMAP — bold bullets, no `Why:`.

    The exact shape the field report hit: a prioritized list of undone work
    under the heading the norm machinery keys on. `docs/norms.md` § Anatomy
    makes `Why` required, so none of these bullets is a norm entry.
    """
    return (
        "# Architecture\n\nDescriptive prose.\n\n## Direction\n\n"
        "- **Ship the importer.** Targeted for Q3.\n"
        "- **Then the exporter.** Q4, depends on the importer.\n"
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

    # --- first arm keys on an ENTRY, not on the heading ----------------------

    def test_fires_when_direction_heading_carries_no_entries(self, tmp_path):
        """A heading with nothing normative under it is not a ratified registry.

        Presence of the heading was the whole test, so a section empty of the
        thing being checked did not fail the check — it passed it silently. The
        field case: the repo's only `## Direction` section was a prioritized
        list of undone work, which satisfied the arm completely and would have
        left doctor check #10 reporting findings against a roadmap
        indefinitely.
        """
        _write_artifact(tmp_path, "architecture.md", _roadmap_direction_artifact())
        out = np.probe_norm_registry_unratified(ProjectState({}), _cb(tmp_path))
        assert len(out) == 1
        assert "no `## Direction` section is ratified" in out[0].trigger_summary

    def test_emphasised_why_markers_are_recognised_as_entries(self, tmp_path):
        """Owner decision 2026-08-03: emphasis is tolerated.

        This test previously asserted the OPPOSITE and was rewritten, not
        deleted — the boundary it pinned still needs a pin, it just moved. The
        reason it moved: since Chunk 02 the `Why:` marker decides whether a norm
        registry EXISTS, not merely whether an entry has decayed, so a product
        writing `**Why:**` silently lost four signals for a formatting choice
        `docs/norms.md` never forbade.

        `_FIELD_OR_ITEM_RE` had to widen alongside `_WHY_RE`: without it the
        emphasised marker is not a line start, soft-wraps onto the bullet above,
        and the `^`-anchored `_WHY_RE` can never see it however tolerant it is.
        """
        for marker in ("**Why:**", "__Why:__", "*Why:*", "_Why:_"):
            _write_artifact(
                tmp_path,
                "architecture.md",
                _direction_artifact(f"- **X.**\n  {marker} because of the reason.\n"),
            )
            assert np.probe_norm_registry_unratified(ProjectState({}), _cb(tmp_path)) == [], (
                f"{marker} must count as a norm entry"
            )

    def test_a_word_that_merely_starts_with_why_is_not_a_marker(self, tmp_path):
        """The widened match must not swallow prose. `Why not:` is not `Why:`."""
        _write_artifact(
            tmp_path,
            "architecture.md",
            _direction_artifact("- **X.**\n  Why not: this is a different field.\n"),
        )
        out = np.probe_norm_registry_unratified(ProjectState({}), _cb(tmp_path))
        assert len(out) == 1, "`Why not:` is not the `Why:` marker"

    def test_silent_when_one_artifact_has_a_real_entry_among_roadmaps(self, tmp_path):
        # The arm asks whether ANY artifact carries a norm — one real entry
        # elsewhere answers it, so a roadmap section is not itself disqualifying.
        _write_artifact(tmp_path, "architecture.md", _roadmap_direction_artifact())
        _write_artifact(
            tmp_path, "security-model.md", _direction_artifact("- **X.**\n  Why: because.\n")
        )
        assert np.probe_norm_registry_unratified(ProjectState({}), _cb(tmp_path)) == []

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

    def test_silent_when_ratified_within_window(self, tmp_path):
        # Ratifying the registry is a full pass over every norm — a just-ratified
        # repo is not overdue for a sweep, even with no janitor stamp yet.
        _write_artifact(tmp_path, "architecture.md", _direction_artifact("- **X.**\n  Why: because.\n"))
        state = ProjectState({np.RATIFIED_FACT: _days_ago(5)})
        assert np.probe_norm_health_sweep_overdue(state, _cb(tmp_path)) == []

    def test_silent_when_ratified_fact_has_description_suffix(self, tmp_path):
        # The fact leads with the date then describes it — the leading date seeds
        # the baseline (strict full-match would miss it).
        _write_artifact(tmp_path, "architecture.md", _direction_artifact("- **X.**\n  Why: because.\n"))
        state = ProjectState({np.RATIFIED_FACT: f"{_days_ago(5)} — 20 Direction norms across the artifacts"})
        assert np.probe_norm_health_sweep_overdue(state, _cb(tmp_path)) == []

    def test_fires_when_ratified_beyond_window_and_no_stamp(self, tmp_path):
        # Ratified long ago with no sweep since → genuinely overdue.
        _write_artifact(tmp_path, "architecture.md", _direction_artifact("- **X.**\n  Why: because.\n"))
        state = ProjectState({np.RATIFIED_FACT: _days_ago(np.SWEEP_WINDOW_DAYS + 5)})
        assert len(np.probe_norm_health_sweep_overdue(state, _cb(tmp_path))) == 1

    def test_uses_newer_of_stamp_and_ratification(self, tmp_path):
        # Ratified long ago but swept recently → the fresher engagement wins → silent.
        _write_artifact(tmp_path, "architecture.md", _direction_artifact("- **X.**\n  Why: because.\n"))
        state = ProjectState(
            {
                np.RATIFIED_FACT: _days_ago(np.SWEEP_WINDOW_DAYS + 30),
                np.SWEEP_STAMP: _days_ago(5),
            }
        )
        assert np.probe_norm_health_sweep_overdue(state, _cb(tmp_path)) == []

    # --- the guard asks whether norms exist under EITHER homing --------------

    def test_fires_when_norms_homed_only_in_the_enforcement_table(self, tmp_path):
        """No Direction heading anywhere, norms in the preferences table.

        A legitimate homing under `docs/norms.md` § Where Norms Live — that
        table IS the product's norm index. Gating the reminder on a Direction
        heading gave such a repo no time-domain norm audit at all, ever, with
        no signal that it was missing. The janitor sweep already covers table
        rows, so the coverage existed; only the reminder was gated.
        """
        _write_artifact(tmp_path, "architecture.md", "# Architecture\n\nProse, no Direction.\n")
        _write_artifact(tmp_path, "project-preferences.md", _PREFS_WITH_NORM_COLUMNS)
        out = np.probe_norm_health_sweep_overdue(ProjectState({}), _cb(tmp_path))
        assert len(out) == 1
        assert out[0].type == "norm-health-sweep-overdue"
        assert out[0].recommended_action == "/prawduct:janitor"

    def test_fires_for_table_homed_norms_after_a_roadmap_rename(self, tmp_path):
        """The field sequence: fixing defect 1 must not silence this probe.

        Renaming the misleading roadmap section left the repo with zero
        Direction headings — which, under the old guard, would have silenced
        this probe permanently *in the same commit that created the norm it
        exists to audit*, while the session's own "all probes return []" check
        reported the short-circuit as health.
        """
        _write_artifact(tmp_path, "architecture.md", "# Architecture\n\nRoadmap renamed away.\n")
        _write_artifact(tmp_path, "project-preferences.md", _PREFS_WITH_NORM_COLUMNS)
        state = ProjectState({np.SWEEP_STAMP: _days_ago(np.SWEEP_WINDOW_DAYS + 5)})
        assert len(np.probe_norm_health_sweep_overdue(state, _cb(tmp_path))) == 1

    def test_silent_when_table_has_norm_columns_but_no_rows(self, tmp_path):
        # Columns are the SHAPE of a registry, not a registry. Without this the
        # widened guard would nag every repo whose template carries the header.
        _write_artifact(tmp_path, "architecture.md", "# Architecture\n\nProse.\n")
        _write_artifact(tmp_path, "project-preferences.md", _PREFS_NORM_COLUMNS_NO_ROWS)
        assert np.probe_norm_health_sweep_overdue(ProjectState({}), _cb(tmp_path)) == []

    def test_silent_when_norm_rows_exist_but_their_norm_cells_are_blank(self, tmp_path):
        """Rows under the norm columns, with nothing in them.

        This is the case that actually reaches the populated-cell check — the
        header-only fixture above exits the row loop before it, so it passes
        whether that check exists or not. A pre-norm table that gained the two
        columns but was never filled in is a real migration state, and reading
        it as "norms are homed here" would nag a repo that has ratified nothing.
        """
        _write_artifact(tmp_path, "architecture.md", "# Architecture\n\nProse.\n")
        _write_artifact(tmp_path, "project-preferences.md", _PREFS_NORM_COLUMNS_EMPTY_CELLS)
        assert np.probe_norm_health_sweep_overdue(ProjectState({}), _cb(tmp_path)) == []

    def test_silent_when_neither_homing_carries_norms(self, tmp_path):
        # The over-fire guard: a pre-norm table plus a roadmap-only Direction
        # section is a repo with NO norms, and a genuine absence must stay quiet.
        _write_artifact(tmp_path, "architecture.md", _roadmap_direction_artifact())
        _write_artifact(tmp_path, "project-preferences.md", _PREFS_WITHOUT_NORM_COLUMNS)
        assert np.probe_norm_health_sweep_overdue(ProjectState({}), _cb(tmp_path)) == []

    def test_silent_against_the_shipped_preferences_template(self, tmp_path):
        """A freshly-onboarded repo has no norms — read the REAL template to say so.

        `init_product` copies `templates/project-preferences.md` verbatim (only
        `{{PRODUCT_NAME}}`/`{{PRAWDUCT_VERSION}}` are substituted), and the
        template's state file carries neither a sweep stamp nor a ratification
        date. So if the shipped norm-index table contains any row this predicate
        reads as populated, `norm-health-sweep-overdue` fires on the **first
        session sync of every new product** — nagging a repo that has ratified
        nothing, which is the exact over-fire the widened guard was written to
        avoid.

        This reads the template through :data:`core.TEMPLATES_DIR` rather than a
        hand-written fixture on purpose: the two hand-written over-fire fixtures
        above resemble what I *expected* the template to look like, and both
        stayed green while the shipped file said otherwise. Template and
        predicate can only be kept honest by testing them against each other.
        """
        template = (core.TEMPLATES_DIR / "project-preferences.md").read_text(encoding="utf-8")
        _write_artifact(tmp_path, "project-preferences.md", template)
        _write_artifact(tmp_path, "architecture.md", "# Architecture\n\nProse, no Direction.\n")

        assert np._has_enforcement_norm_rows(_cb(tmp_path)) is False, (
            "the shipped norm-index table must ship EMPTY — a populated row is a "
            "homed norm, and the template's rows would be every new product's"
        )
        assert np._norms_exist(_cb(tmp_path)) is False
        assert np.probe_norm_health_sweep_overdue(ProjectState({}), _cb(tmp_path)) == []

    def test_window_boundary_is_inclusive(self, tmp_path):
        # age == SWEEP_WINDOW_DAYS is still "fresh" (the guard is `<=`); one day past fires.
        _write_artifact(tmp_path, "architecture.md", _direction_artifact("- **X.**\n  Why: because.\n"))
        at_window = ProjectState({np.RATIFIED_FACT: _days_ago(np.SWEEP_WINDOW_DAYS)})
        assert np.probe_norm_health_sweep_overdue(at_window, _cb(tmp_path)) == []
        past_window = ProjectState({np.RATIFIED_FACT: _days_ago(np.SWEEP_WINDOW_DAYS + 1)})
        assert len(np.probe_norm_health_sweep_overdue(past_window, _cb(tmp_path))) == 1


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
# repo-coupled tripwire: NO norm-lifecycle advisory fires against THIS repo today.
# The registry is ratified (`norm_registry_ratified` recorded + `## Direction`
# sections present), which clears `norm-registry-unratified`; the ratification
# date also seeds the Norm Health sweep baseline, so `norm-health-sweep-overdue`
# stays silent inside the window. Deliberately NOT hermetic: it must fail the
# moment this repo's norm state drifts — the ratification ageing past the sweep
# window with no janitor sweep, a dated `revisit:` expiring, a dead-why, an
# in-transition stall — forcing a human to re-baseline (and, for the sweep case,
# to actually run `/prawduct:janitor`).
# =============================================================================


class TestSilentAgainstThisRepo:
    def test_no_norm_lifecycle_advisory_fires_here_today(self):
        # Steady state after ratifying prawduct's own registry (norm-lifecycle
        # Layer 2): `norm_registry_ratified` is recorded and the seven strategy
        # artifacts carry `## Direction` sections, so `norm-registry-unratified`
        # is cleared and — because the ratification date seeds the Norm Health
        # sweep baseline — `norm-health-sweep-overdue` is suppressed inside the
        # window. No dated `revisit:` is live, no dead-why, no in-transition
        # stall, so every norm-lifecycle probe is silent. This tripwire re-fires
        # when the state drifts (the sweep window lapses without a janitor run, a
        # `revisit:` expires, …); that required re-baseline is the forcing function.
        repo_root = Path(__file__).resolve().parents[1]
        state = load_project_state(repo_root)
        codebase = make_codebase(repo_root)
        np.register()
        fired = sorted(
            c.type for c in run_all_probes(state, codebase) if c.feature == "norm-lifecycle"
        )
        assert fired == [], (
            f"expected no norm-lifecycle advisory to fire here; got: {fired}"
        )


def _id(candidate) -> str:
    return compute_id(np.FEATURE, candidate.type, np.PROBE_VERSION, candidate.evidence)


class TestPostCutoverRetirement:
    """The norm trio judges item liveness from `.prawduct/backlog.md`; once
    `backlog_service_repo` is set (migration cutover) that file is frozen
    history and all three retire (shared predicate: backlog_probes.post_cutover)."""

    _CUTOVER = {"backlog_service_repo": "octo/backlog"}

    def test_revisit_due_retires(self, tmp_path):
        _write_backlog(tmp_path, _item("EXC-1A2B", extra=f"revisit: {_days_ago(3)}"))
        assert np.probe_revisit_due(ProjectState(dict(self._CUTOVER)), _cb(tmp_path)) == []

    def test_dead_why_retires(self, tmp_path):
        _write_backlog(tmp_path, _item("MIG-4C1K", section="Archive", status="shipped"))
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact(
                "- **All telemetry rides OpenTelemetry.**\n"
                "  Why: the MIG-4C1K migration made a second system redundant.\n"
            ),
        )
        assert np.probe_dead_why(ProjectState(dict(self._CUTOVER)), _cb(tmp_path)) == []

    def test_stalled_transition_retires(self, tmp_path):
        _write_backlog(tmp_path, _item("OBS-4C1K", status="open"))
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact("- **X.**\n  Status: in-transition — export tracked in OBS-4C1K\n"),
        )
        assert np.probe_stalled_transition(ProjectState(dict(self._CUTOVER)), _cb(tmp_path)) == []


class TestNormIndexLocatorIsShared:
    """Both index questions must be answered about the SAME table.

    Locating the index twice with different acceptance rules — the first
    `Preference`-headed table for one question, the first one *carrying the norm
    columns* for the other — lets a file with two such tables produce
    contradictory nudges out of a single read: "your index lacks the norm
    columns" and "norms are homed in your index", simultaneously.
    """

    _TWO_TABLES = (
        "# Project Preferences\n\n## Enforcement\n\n"
        "| Preference | Mechanism | Enforcement artifact |\n|---|---|---|\n"
        "| naming | Critic | reviewer reads the diff |\n\n"
        "| Preference / norm | Mechanism | Enforcement artifact | Audit home | Why |\n"
        "|---|---|---|---|---|\n"
        "| imports | Test | `tests/preferences/test_imports.py` | janitor | uniformity |\n"
    )

    def test_both_questions_read_the_first_index_table(self, tmp_path):
        _write_artifact(tmp_path, "project-preferences.md", self._TWO_TABLES)
        cb = _cb(tmp_path)
        # The first table predates the norm columns, so that is the answer to
        # both questions — not "lacks columns" AND "carries norms" at once.
        assert np._norm_index_lacks_columns(cb) is True
        assert np._has_enforcement_norm_rows(cb) is False

    def test_locator_returns_none_without_a_preferences_file(self, tmp_path):
        cb = _cb(tmp_path)
        assert np._norm_index_header(np._preferences_lines(cb)) is None
        assert np._norm_index_lacks_columns(cb) is False
        assert np._has_enforcement_norm_rows(cb) is False


class TestOneDefinitionOfANormEntry:
    """#568 — `record_lint` and `norm_probes` must agree what a norm entry is.

    They disagreed exactly in the roadmap case: `direction_norm_count` counted
    every top-level bullet, `_has_direction_entry` required a field, so a
    `## Direction` section holding a prioritised list of undone work made the
    `governed_by` under-disposition lint demand dispositions for items the
    probes correctly ignored. One fact, one home.
    """

    # Blank lines and trailing prose are deliberate. An earlier cut had two
    # ADJACENT bullets then EOF, so no line ever followed a pending bullet and
    # a mutation that counts every bullet still returned 0 — a fixture that
    # could not reach the code path it was written to discriminate. Real
    # roadmaps are spaced; so is this one now.
    _ROADMAP = (
        "# Architecture\n\n## Direction\n\n"
        "- **Ship the importer.** Targeted for Q3.\n"
        "  Blocked on the schema freeze.\n"
        "\n"
        "- **Then the exporter.** Q4.\n"
        "\n"
        "Not a bullet at all.\n"
    )
    _NORMS = (
        "# Architecture\n\n## Direction\n\n"
        "- **Bare marker.**\n  Why: canonical form.\n"
        "- **Emphasised marker.**\n  **Why:** authors write this too.\n"
        "- **Whyless but ratified-shaped.**\n  Status: steady-state.\n"
    )

    def test_roadmap_counts_zero_in_both(self, tmp_path):
        from lib import record_lint

        assert record_lint.direction_norm_count(self._ROADMAP) == 0
        assert np._has_direction_entry(self._ROADMAP) is False

    def test_field_bearing_entries_count_in_both(self, tmp_path):
        from lib import record_lint

        assert record_lint.direction_norm_count(self._NORMS) == 3, (
            "emphasised markers and a whyless-but-Status-bearing entry all count"
        )
        assert np._has_direction_entry(self._NORMS) is True

    def test_a_whyless_entry_is_still_an_entry(self, tmp_path):
        """Load-bearing for doctor Health Check #10.

        That check reports "every Direction entry carries a **Why**". A
        Why-only definition would make it vacuous — the whyless entries it
        exists to flag would stop being entries at all — which is why the
        shared definition is field-bearing rather than Why-bearing.
        """
        from lib import record_lint

        whyless = "## Direction\n\n- **X.**\n  Status: steady-state.\n"
        assert record_lint.direction_norm_count(whyless) == 1
        assert np._has_direction_entry(whyless) is True


class TestEmphasisAcrossEveryNormField:
    """#569 widened `Why:`; the other fields had to move with it.

    An earlier cut widened the `Status:` PREFIX to accept `_{1,2}` but left the
    `in-transition` closer accepting only `*`. `__Status:__ in-transition` then
    counted as a norm entry and was scanned by dead-why, while
    `probe_stalled_transition` could never see it — the defect this chunk exists
    to fix, surviving one field over. Prefix and closer are now the same class.
    """

    MARKERS = ("Why:", "**Why:**", "__Why:__", "*Why:*", "_Why:_")
    STATUS = ("Status:", "**Status:**", "__Status:__", "*Status:*", "_Status:_")

    def test_every_emphasis_form_of_why_is_an_entry(self, tmp_path):
        for m in self.MARKERS:
            body = _direction_artifact(f"- **X.**\n  {m} because.\n")
            assert np._has_direction_entry(body) is True, f"{m} must be an entry"

    def test_every_emphasis_form_of_status_is_an_entry(self, tmp_path):
        for m in self.STATUS:
            body = _direction_artifact(f"- **X.**\n  {m} steady-state.\n")
            assert np._has_direction_entry(body) is True, f"{m} must be an entry"

    def test_stalled_transition_fires_through_every_status_emphasis(self, tmp_path):
        """Drives the PROBE, not the regex.

        An earlier cut asserted `_IN_TRANSITION_RE.search(...)` directly, which
        pins the implementation rather than the behaviour: it stays green if the
        constant keeps its emphasis while the probe stops reaching it. If the
        entry counts but the transition scan cannot read it, a stalled norm goes
        unaudited while every other check treats it as live.
        """
        for m in self.STATUS:
            _write_backlog(
                tmp_path, _item("MIG-4C1K", extra=f"added: {_days_ago(400)}")
            )
            _write_artifact(
                tmp_path,
                "observability-strategy.md",
                _direction_artifact(
                    "- **All telemetry rides OpenTelemetry.**\n"
                    "  Why: one substrate for causality.\n"
                    f"  {m} in-transition — tracked by MIG-4C1K.\n"
                ),
            )
            out = np.probe_stalled_transition(ProjectState({}), _cb(tmp_path))
            assert len(out) == 1, (
                f"stalled-transition must reach `{m} in-transition` — the "
                "closer must not be narrower than the prefix"
            )

    def test_emphasis_on_the_value_is_seen_too(self, tmp_path):
        """`Status: **in-transition**` — emphasis on the VALUE, not the marker.

        The first cut allowed optional emphasis only immediately after the
        colon, so this form was entry-visible and stall-invisible: the same
        defect as the `__Status:__` case, one position over. Written as a
        separate test because it is a separate position, and the earlier bug
        proves per-form patching is how this gets missed.
        """
        for value in ("**in-transition**", "__in-transition__", "*in-transition*"):
            _write_backlog(
                tmp_path, _item("MIG-4C1K", extra=f"added: {_days_ago(400)}")
            )
            _write_artifact(
                tmp_path,
                "observability-strategy.md",
                _direction_artifact(
                    "- **All telemetry rides OpenTelemetry.**\n"
                    "  Why: one substrate for causality.\n"
                    f"  Status: {value} — tracked by MIG-4C1K.\n"
                ),
            )
            out = np.probe_stalled_transition(ProjectState({}), _cb(tmp_path))
            assert len(out) == 1, f"stalled-transition must reach `Status: {value}`"

    def test_dead_why_fires_through_every_emphasis_form(self, tmp_path):
        """`_WHY_RE`/`_STATUS_RE` have ONE consumer, and it is this probe.

        The marker-matrix tests above route through `_has_direction_entry` →
        `_FIELD_MARKER_RE`, a *different constant*. So `_WHY_RE` and
        `_STATUS_RE` could lose their emphasis tolerance with the whole suite
        green while `probe_dead_why` went silent for `**Why:**` — testing the
        constant I was thinking about instead of the one the behaviour routes
        through. This drives the probe.
        """
        for m in self.MARKERS + self.STATUS:
            _write_backlog(
                tmp_path, _item("MIG-4C1K", section="Archive", status="shipped")
            )
            _write_artifact(
                tmp_path,
                "observability-strategy.md",
                _direction_artifact(
                    "- **All telemetry rides OpenTelemetry.**\n"
                    f"  {m} the MIG-4C1K migration made a second system redundant.\n"
                ),
            )
            out = np.probe_dead_why(ProjectState({}), _cb(tmp_path))
            assert len(out) == 1, f"dead-why must reach a `{m}` line"

    def test_both_consumers_agree_across_the_marker_matrix(self, tmp_path):
        """The plan's 'marker matrix x BOTH consumers' — the second consumer.

        The first cut delivered the matrix against `norm_probes` only, which is
        exactly the asymmetry #568 is about.
        """
        from lib import record_lint

        for m in self.MARKERS + self.STATUS:
            body = f"## Direction\n\n- **X.**\n  {m} value.\n\n- **Y.**\n  {m} value.\n\nTail.\n"
            assert record_lint.direction_norm_count(body) == 2, f"record_lint: {m}"
            assert np._has_direction_entry(body) is True, f"norm_probes: {m}"
