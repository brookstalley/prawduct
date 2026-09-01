"""Tests for the norm-lifecycle post-sync advisory probes (docs/norms.md).

Each probe is a pure, deterministic ``ProbeFn(state, codebase)`` reading only
machine-readable hooks (backlog-item citations on norm
Why/Status lines, the ``Status: in-transition`` token, structural presence of
``## Direction`` sections and strategy-class artifacts). Per probe we drive the
positive fire, the named negative-silence conditions, and advisory-id stability
(one stable id across two runs with different firing items). A final
repo-coupled tripwire test asserts ZERO norm-lifecycle advisories fire against
THIS repo's committed state (the rare-and-high-signal bar) — deliberately not
hermetic, so drift trips it (the ratification ageing past the sweep window with
no janitor run, a norm's rationale citing work that shipped). Registry isolation
mirrors the sibling probe tests (autouse ``clear_registry``).

**The two backlog-reading probes are driven on both backends.** Pre-cutover the
citation is resolved against ``.prawduct/backlog.md``; post-cutover against a real
SQLite cache built from the transport fake, because a probe restored against a
mocked-out store would prove only that the mock returns what the test told it to.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

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
from lib.backlog import core as backlog_core, encode, sync as backlog_sync
from fakes.fake_github import FakeGitHub


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

    def test_silent_when_a_settled_status_names_the_item_that_completed_it(self, tmp_path):
        """The false positive the restoration surfaced, on this repo's own norms.

        A `Status: steady-state … transitioned when OBS-4C1K closed` line cites a
        dead item *because the transition finished* — the healthiest state a norm
        reaches, and the previous rule reported three of them at once as rotting
        rationale. Only an in-flight `Status:` is decay; the `Why:` arm below is
        untouched, because rationale resting on finished work is decay whatever
        the status says."""
        _write_backlog(tmp_path, _item("OBS-4C1K", section="Archive", status="shipped"))
        _write_artifact(
            tmp_path,
            "architecture.md",
            _direction_artifact(
                "- **Spans everywhere.**\n"
                "  Why: causality across turns.\n"
                "  Status: steady-state as of 2026-08-02 — transitioned when OBS-4C1K closed.\n"
            ),
        )
        assert np.probe_dead_why(ProjectState({}), _cb(tmp_path)) == []

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


class TestStopgapClearsAndExpires:
    """The third clearing arm `docs/norms.md` § Transitions always named (#737).

    Until this landed, `Stopgap:` appeared in this module only in a docstring, a
    comment and two operator-facing strings — the advisory told the reader to
    record one and then could not read the one they recorded. So the ONLY thing
    that bought silence was touching the tracking item, which is also what resets
    the stall clock. That combination is why suppression alone is not the fix:
    an entry could carry a lapsed bound and still never fire, because the touch
    that silenced it moved the only clock being measured. Both directions are
    pinned here, and a suppression test without its expiry sibling would re-open
    exactly the hole #737 describes.
    """

    def _entry(self, stopgap: str) -> str:
        return (
            "- **X.**\n"
            "  Status: in-transition — export tracked in OBS-4C1K\n"
            f"  {stopgap}\n"
        )

    def test_silent_while_the_recorded_expiry_is_still_ahead(self, tmp_path):
        # The stall itself is real (added: 120 days ago, no reviewed:) — the
        # bounded exception is the only thing standing between it and a fire.
        _write_backlog(tmp_path, _item("OBS-4C1K", status="open"))
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact(
                self._entry(
                    f"Stopgap: recorded {_days_ago(1)}, expires {_days_ahead(90)}. "
                    "`[DECISION: interim rule stands | the norm's why is served | "
                    "user can veto/override]`"
                )
            ),
        )
        assert np.probe_stalled_transition(ProjectState({}), _cb(tmp_path)) == []

    def test_fires_once_the_expiry_has_passed(self, tmp_path):
        _write_backlog(tmp_path, _item("OBS-4C1K", status="open"))
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact(
                self._entry(f"Stopgap: recorded {_days_ago(200)}, expires {_days_ago(1)}.")
            ),
        )
        out = np.probe_stalled_transition(ProjectState({}), _cb(tmp_path))
        assert len(out) == 1
        assert "stopgap expired" in out[0].trigger_summary
        assert "observability-strategy.md→OBS-4C1K" in out[0].trigger_summary

    def test_lapsed_expiry_fires_even_when_the_tracking_item_is_fresh(self, tmp_path):
        # THE regression this item is about. A fresh `reviewed:` clears the stall
        # arm outright, so if the expiry were only ever read as a suppressor the
        # advisory would be silent and the recorded bound would be a note with no
        # clock behind it — the exact state commit ac6bbb8b left this repo in.
        _write_backlog(
            tmp_path,
            _item("OBS-4C1K", status="open", extra=f"reviewed: {_days_ago(1)}"),
        )
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact(
                self._entry(f"Stopgap: recorded {_days_ago(200)}, expires {_days_ago(1)}.")
            ),
        )
        out = np.probe_stalled_transition(ProjectState({}), _cb(tmp_path))
        assert len(out) == 1 and "stopgap expired" in out[0].trigger_summary

    def test_expiry_today_is_still_in_force(self, tmp_path):
        # Aligned with `revisit-due`, which fires on a date STRICTLY before today.
        # Two dated clocks in one feature disagreeing about "expires today" is a
        # bug report waiting to be filed.
        _write_backlog(tmp_path, _item("OBS-4C1K", status="open"))
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact(
                self._entry(f"Stopgap: recorded {_days_ago(90)}, expires {_days_ago(0)}.")
            ),
        )
        assert np.probe_stalled_transition(ProjectState({}), _cb(tmp_path)) == []

    def test_unbounded_stopgap_suppresses_nothing(self, tmp_path):
        # An exception with no clock is not a bounded exception. Failing toward
        # the advisory here is deliberate and is the opposite of this module's
        # usual default: the signal was read fine and says there is no bound.
        _write_backlog(tmp_path, _item("OBS-4C1K", status="open"))
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact(
                self._entry("Stopgap: recorded when we get to it; we will revisit eventually.")
            ),
        )
        out = np.probe_stalled_transition(ProjectState({}), _cb(tmp_path))
        assert len(out) == 1 and "unchanged >" in out[0].trigger_summary

    def test_stopgap_on_a_sibling_entry_does_not_cover_this_one(self, tmp_path):
        # Entry-scoped, not file-scoped: `_direction_entries` exists so a stopgap
        # covers the Status line it sits with and no other. A file-wide read
        # would let one bounded exception silence every transition in the artifact.
        _write_backlog(
            tmp_path,
            _item("OBS-4C1K", status="open") + _item("SEC-9Z8Y", status="open"),
        )
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact(
                self._entry(f"Stopgap: recorded {_days_ago(1)}, expires {_days_ahead(90)}."),
                "- **Y.**\n  Status: in-transition — tracked in SEC-9Z8Y\n",
            ),
        )
        out = np.probe_stalled_transition(ProjectState({}), _cb(tmp_path))
        assert len(out) == 1
        assert "SEC-9Z8Y" in out[0].trigger_summary
        assert "OBS-4C1K" not in out[0].trigger_summary

    def test_a_nested_bullet_does_not_split_an_entry(self, tmp_path):
        # The reason `_direction_entries` groups on bullet INDENT rather than on
        # "any bullet": a sub-list between the Status line and its Stopgap would
        # otherwise start a new entry and lose the association silently.
        _write_backlog(tmp_path, _item("OBS-4C1K", status="open"))
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact(
                "- **X.**\n"
                "  Status: in-transition — export tracked in OBS-4C1K\n"
                "  - sub-point about the interim rule\n"
                f"  Stopgap: recorded {_days_ago(1)}, expires {_days_ahead(90)}.\n"
            ),
        )
        assert np.probe_stalled_transition(ProjectState({}), _cb(tmp_path)) == []

    def test_latest_expiry_wins_when_an_entry_carries_two(self, tmp_path):
        # Successive recordings: covered while any bound still runs.
        _write_backlog(tmp_path, _item("OBS-4C1K", status="open"))
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact(
                "- **X.**\n"
                "  Status: in-transition — export tracked in OBS-4C1K\n"
                f"  Stopgap: recorded {_days_ago(200)}, expires {_days_ago(1)}.\n"
                f"  Stopgap: recorded {_days_ago(1)}, expires {_days_ahead(90)}.\n"
            ),
        )
        assert np.probe_stalled_transition(ProjectState({}), _cb(tmp_path)) == []

    def test_emphasised_stopgap_marker_is_read(self, tmp_path):
        # Every sibling field marker tolerates markdown emphasis (the #569 line of
        # defects); a new field that does not would be the same bug, one field over.
        _write_backlog(tmp_path, _item("OBS-4C1K", status="open"))
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact(
                self._entry(f"**Stopgap:** recorded {_days_ago(1)}, expires {_days_ahead(90)}.")
            ),
        )
        assert np.probe_stalled_transition(ProjectState({}), _cb(tmp_path)) == []

    def test_stopgap_is_not_itself_a_norm_entry(self):
        # `_NORM_FIELDS` is what makes a bullet an ENTRY. A stopgap qualifies an
        # entry a Status:/Why: line already established; admitting it would let a
        # roadmap bullet with a stopgap certify as a ratified registry.
        assert not np._has_direction_entry(
            _direction_artifact("- **X.**\n  Stopgap: recorded 2026-01-01, expires 2026-06-01.\n")
        )

    def test_a_lapsed_stopgap_is_reported_even_when_the_backlog_cannot_answer(self, tmp_path):
        # The expired arm reads only the artifact, so a store outage must not take
        # it down with the arm that needs the store. Both are reported: hiding the
        # departure would be worse, and hiding the outage would claim a clean scan.
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact(
                self._entry(f"Stopgap: recorded {_days_ago(200)}, expires {_days_ago(1)}.")
            ),
        )
        state = ProjectState({"backlog_service_repo": "acme/product"})
        out = np.probe_stalled_transition(state, _cb(tmp_path))
        types = sorted(c.type for c in out)
        assert types == ["backlog-cache-unreadable", "stalled-transition"], types
        stall = next(c for c in out if c.type == "stalled-transition")
        assert "stopgap expired" in stall.trigger_summary

    def test_advisory_id_is_stable_across_both_arms(self, tmp_path):
        # Arm-independent evidence, the `norm-registry-unratified` shape: the id
        # must not churn as the firing arm changes, or one nudge becomes two.
        _write_backlog(tmp_path, _item("OBS-4C1K", status="open"))
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact("- **X.**\n  Status: in-transition — tracked in OBS-4C1K\n"),
        )
        stall_only = np.probe_stalled_transition(ProjectState({}), _cb(tmp_path))[0]
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact(
                self._entry(f"Stopgap: recorded {_days_ago(200)}, expires {_days_ago(1)}.")
            ),
        )
        expired_only = np.probe_stalled_transition(ProjectState({}), _cb(tmp_path))[0]
        assert "stopgap expired" in expired_only.trigger_summary
        assert _id(stall_only) == _id(expired_only)

    def test_direction_entries_flatten_to_direction_lines(self):
        # The property dead-why depends on: grouping added a way to ask about an
        # entry, it did not change which lines are seen or in what order.
        text = _direction_artifact(
            "Some section prose before the first bullet.\n",
            "- **X.**\n  Status: in-transition — tracked in OBS-4C1K\n  - nested\n",
            "- **Y.**\n  Why: because.\n",
        )
        flat = [line for entry in np._direction_entries(text) for line in entry]
        assert flat == np._direction_lines(text)


# =============================================================================
# the five live stopgaps this repo recorded (ac6bbb8b) — the #737 fixture
# =============================================================================


class TestThisRepoRecordedStopgapsAreReadable:
    """Repo-coupled: the entries commit `ac6bbb8b` wrote must be machine-visible.

    #737 was filed because those five `Stopgap:` fields went into live artifacts
    while nothing could read them. Asserting the parse against the real entries
    rather than a synthetic fixture is the point: a synthetic one would have
    passed against the pre-#737 code too, since the defect was never in the
    regex — it was that no regex existed and nobody noticed, because the only
    corpus anyone checked was the one written to match.

    Deliberately NOT asserting that they are still in force: that clock belongs
    to `TestSilentAgainstThisRepo`, which goes red when the advisory fires. Two
    tests owning one date would make the expiry lapse twice.
    """

    def _artifacts(self):
        repo_root = Path(__file__).resolve().parents[1]
        return sorted((repo_root / ".prawduct" / "artifacts").glob("*.md"))

    def test_every_recorded_stopgap_names_a_parseable_bound(self):
        marked = [
            (path.name, line)
            for path in self._artifacts()
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if np._STOPGAP_RE.match(line)
        ]
        assert marked, "expected this repo to carry recorded stopgaps (ac6bbb8b wrote five)"
        unbounded = [name for name, line in marked if not np._STOPGAP_EXPIRES_RE.search(line)]
        assert unbounded == [], f"recorded stopgaps with no `expires YYYY-MM-DD` bound: {unbounded}"

    def test_each_recorded_stopgap_sits_in_an_in_transition_entry(self):
        # A stopgap the parser can read but that is grouped away from its Status
        # line suppresses nothing and expires against nothing — visible only by
        # asking the entry walker, not the line scan.
        orphaned = []
        for path in self._artifacts():
            text = path.read_text(encoding="utf-8", errors="replace")
            for entry in np._direction_entries(text):
                if not any(np._STOPGAP_RE.match(line) for line in entry):
                    continue
                if not any(np._IN_TRANSITION_RE.search(line) for line in entry):
                    orphaned.append(path.name)
        assert orphaned == [], f"stopgaps not grouped with an in-transition Status line: {orphaned}"


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

    def test_the_advisory_names_the_repair_route_not_only_the_sweep(self, tmp_path):
        """The pointer to Health Check #14 must live where a surface renders it.

        It was first set on `alternative_actions`, which briefing, `advisory
        list` and `advisory show` all ignore — so the fix was inert while
        looking complete. `trigger_summary` is rendered AND is not hashed into
        `compute_id`, so it is the one field that can carry this without
        resurrecting the advisory in every repo that dismissed it. Without this
        test a reword silently deletes the only rendered pointer to the repair.
        """
        _write_artifact(tmp_path, "architecture.md", _direction_artifact("- **X.**\n  Why: because.\n"))
        out = np.probe_norm_health_sweep_overdue(ProjectState({}), _cb(tmp_path))
        assert len(out) == 1
        assert "norm-index-scaffold" in out[0].trigger_summary, (
            "a repo whose rows are leftover template scaffold owes no sweep — "
            "the summary must offer the repair, not only the audit"
        )

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
        _write_backlog(tmp_path, _item("MIG-4C1K", section="Archive", status="shipped"))
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact(
                "- **All telemetry rides OpenTelemetry.**\n"
                "  Why: the MIG-4C1K migration made a second system redundant.\n"
            ),
        )
        np.register()
        np.register()  # idempotent — register_probe overwrites
        cands = run_all_probes(ProjectState({}), make_codebase(tmp_path))
        fired = [c for c in cands if c.type == "dead-why"]
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
        # window. No dead-why, no in-transition stall, so every norm-lifecycle
        # probe is silent. This tripwire re-fires when the state drifts (the sweep
        # window lapses without a janitor run, a norm's rationale citing work that
        # shipped); that required re-baseline is the forcing function.
        #
        # `backlog-cache-unreadable` is excluded, and the exclusion is the point
        # of the test rather than a hole in it: this asserts a property of the
        # repo's COMMITTED norm state, and the backlog cache is per-clone,
        # uncommitted and absent on a fresh checkout. Its absence says something
        # true about this machine and nothing about the norms — asserting on it
        # here would make a clean clone's first test run red for a correct
        # reason. That the probes report it at all is asserted directly, against
        # a store the test controls, in TestPostCutoverResolvesThroughTheCache.
        repo_root = Path(__file__).resolve().parents[1]
        state = load_project_state(repo_root)
        codebase = make_codebase(repo_root)
        np.register()
        fired = sorted(
            c.type
            for c in run_all_probes(state, codebase)
            if c.feature == "norm-lifecycle" and c.type != "backlog-cache-unreadable"
        )
        assert fired == [], (
            f"expected no norm-lifecycle advisory to fire here; got: {fired}"
        )


def _id(candidate) -> str:
    return compute_id(np.FEATURE, candidate.type, np.PROBE_VERSION, candidate.evidence)


class TestRevisitDueProbe:
    """Markdown-backend only, and that scoping is the point of this class.

    The cutover retires it — no `revisit:` write path exists on the Issues
    backend — but for every pre-cutover product it is live, and `docs/norms.md`
    § Exceptions expire states the two-path split normatively: dated clocks fire
    here, event-bound ones in the janitor's Norm Health sweep, which declines
    dated ones *because* this fires them. Retiring it outright would have taken a
    working control from a whole class of products on a rationale that held for
    exactly one repo.
    """

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

    def test_it_retires_on_the_cutover_and_the_cache_cannot_change_that(self, tmp_path):
        """The one of the three whose dormancy the cache does not end. `revisit:`
        records intent — *granted until date X* — which no age-based query can
        reconstruct, so what it waits on post-cutover is a WRITE path for the
        field, not a read path.

        The check that this is not *promised* as restored used to live here as an
        assertion about `DORMANT_CHECKS`. That roster and its advisory are gone
        (W1 Chunk 06), so the promise has no surface to be made on — and the
        durable form of the claim, that no probe registers to announce it,
        now sits with the retirement in `test_backlog_probes.py`. What stays here
        is this probe's own behaviour, which is the part this file owns."""
        _write_backlog(tmp_path, _item("EXC-1A2B", extra=f"revisit: {_days_ago(3)}"))
        cutover = ProjectState({"backlog_service_repo": "octo/backlog"})

        assert np.probe_revisit_due(cutover, _cb(tmp_path)) == []
        # Pre-cutover it still fires on the same fixture — otherwise this test
        # would pass just as well against a probe that had stopped working.
        assert np.probe_revisit_due(ProjectState({}), _cb(tmp_path))


class TestPostCutoverResolvesThroughTheCache:
    """Once `backlog_service_repo` is set, `.prawduct/backlog.md` is frozen
    history — so the two backlog-reading probes resolve their citations against
    the backlog cache instead. They went **dormant** at that cutover, returning
    `[]` in a shape indistinguishable from a clean bill of health; these tests are
    the restoration, driven against a real store built from the transport fake.
    """

    OWNER, REPO = "octo", "backlog"
    SCOPE = f"{OWNER}/{REPO}"
    _CUTOVER = {"backlog_service_repo": SCOPE}

    def _state(self):
        return ProjectState(dict(self._CUTOVER))

    def _cached(self, tmp_path, **items):
        """Build a real cache holding ``items`` (title → facets), returning the
        canonical id of each by keyword. Every id is a live provider id, which is
        also the spelling a post-cutover norm cites."""
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        fake = FakeGitHub(user={"login": "agent-a", "id": 1})
        ids = {}
        for name, spec in items.items():
            result = backlog_core.file_item(
                fake,
                owner=self.OWNER,
                repo=self.REPO,
                title=spec["title"],
                body="b",
                facets=spec.get("facets", {}),
            )
            assert result["status"] == "ok", result
            ids[name] = result["data"]["id"]
            if spec.get("status"):
                assert backlog_core.set_status(
                    fake, id_raw=ids[name], target=spec["status"]
                )["status"] == "ok"
            if spec.get("updated"):
                number = int(ids[name].rsplit("#", 1)[1])
                fake._repo(self.OWNER, self.REPO).issues[number]["updated_at"] = (
                    spec["updated"].isoformat().replace("+00:00", "Z")
                )
        assert backlog_sync.full_rebuild(
            fake, project_dir=tmp_path, owner=self.OWNER, repo=self.REPO
        )["status"] == "ok"
        return ids

    def test_dead_why_fires_on_a_cited_item_that_shipped(self, tmp_path):
        ids = self._cached(
            tmp_path,
            done={"title": "norms: the finished migration item", "status": "shipped"},
        )
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact(
                "- **All telemetry rides OpenTelemetry.**\n"
                f"  Why: the {ids['done']} migration made a second system redundant.\n"
            ),
        )

        out = np.probe_dead_why(self._state(), _cb(tmp_path))

        assert len(out) == 1 and out[0].type == "dead-why"
        assert ids["done"] in out[0].trigger_summary

    def test_dead_why_stays_quiet_while_the_cited_item_is_live(self, tmp_path):
        ids = self._cached(tmp_path, live={"title": "norms: the ongoing migration item"})
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact(
                f"- **X.**\n  Why: tracked by {ids['live']}.\n"
            ),
        )

        assert np.probe_dead_why(self._state(), _cb(tmp_path)) == []

    def test_dead_why_resolves_a_pre_migration_pfx_through_the_alias_table(self, tmp_path):
        """A norm written before the migration cites the id the markdown backlog
        used. The issue carries it as an alias, so the citation keeps working
        untouched — which is the whole argument for resolving through the table
        rather than parsing an id as live coordinates."""
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        fake = FakeGitHub(user={"login": "agent-a", "id": 1})
        issue = fake.create_issue(
            self.OWNER,
            self.REPO,
            title="norms: the migrated item",
            body=encode.compose_body("b", {"v": "1", "id_aliases": "[MIG-4C1K]"}),
            labels=[],
        )
        canonical = f"{self.SCOPE}#{issue['number']}"
        assert backlog_core.set_status(fake, id_raw=canonical, target="shipped")["status"] == "ok"
        assert backlog_sync.full_rebuild(
            fake, project_dir=tmp_path, owner=self.OWNER, repo=self.REPO
        )["status"] == "ok"
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact("- **X.**\n  Why: the MIG-4C1K migration settled it.\n"),
        )

        out = np.probe_dead_why(self._state(), _cb(tmp_path))

        assert len(out) == 1 and "MIG-4C1K" in out[0].trigger_summary

    def test_stalled_transition_fires_off_the_providers_updated_at(self, tmp_path):
        ids = self._cached(
            tmp_path,
            tracked={
                "title": "norms: the stalled export item",
                "updated": datetime.now(timezone.utc) - timedelta(days=np.STALL_WINDOW_DAYS + 10),
            },
        )
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact(
                f"- **X.**\n  Status: in-transition — export tracked in {ids['tracked']}\n"
            ),
        )

        out = np.probe_stalled_transition(self._state(), _cb(tmp_path))

        assert len(out) == 1 and out[0].type == "stalled-transition"
        assert ids["tracked"] in out[0].trigger_summary

    def test_stalled_transition_stays_quiet_on_a_recently_touched_item(self, tmp_path):
        ids = self._cached(
            tmp_path,
            tracked={
                "title": "norms: the moving export item",
                "updated": datetime.now(timezone.utc) - timedelta(days=2),
            },
        )
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact(
                f"- **X.**\n  Status: in-transition — export tracked in {ids['tracked']}\n"
            ),
        )

        assert np.probe_stalled_transition(self._state(), _cb(tmp_path)) == []

    def test_a_dead_tracking_item_is_dead_whys_finding_not_this_ones(self, tmp_path):
        ids = self._cached(
            tmp_path,
            tracked={
                "title": "norms: the abandoned export item",
                "status": "dropped",
                "updated": datetime.now(timezone.utc) - timedelta(days=np.STALL_WINDOW_DAYS + 10),
            },
        )
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact(
                f"- **X.**\n  Status: in-transition — export tracked in {ids['tracked']}\n"
            ),
        )

        assert np.probe_stalled_transition(self._state(), _cb(tmp_path)) == []

    @pytest.mark.parametrize(
        "probe", ["probe_dead_why", "probe_stalled_transition"], ids=["dead-why", "stalled"]
    )
    def test_an_unreachable_store_is_reported_never_answered_as_silence(self, tmp_path, probe):
        """The failure these two were made to announce. A probe that returned
        `[]` because it could not look reads exactly like a probe that looked and
        found nothing — which is how a norm exception stops expiring visibly."""
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)  # no cache in it
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact(
                f"- **X.**\n  Why: settled by {self.SCOPE}#7.\n"
                f"  Status: in-transition — tracked in {self.SCOPE}#7\n"
            ),
        )

        out = getattr(np, probe)(self._state(), _cb(tmp_path))

        assert len(out) == 1
        assert out[0].type == "backlog-cache-unreadable"
        assert "sync" in out[0].recommended_action

    def test_both_probes_report_one_outage_not_two(self, tmp_path):
        """One cause, one nag. `compute_id` hashes (feature, type, version,
        evidence), so the shared type and evidence collapse the two reports into
        a single advisory — the alternative trains the reader to dismiss."""
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact(
                f"- **X.**\n  Why: settled by {self.SCOPE}#7.\n"
                f"  Status: in-transition — tracked in {self.SCOPE}#7\n"
            ),
        )
        np.register()

        fired = [
            c for c in run_all_probes(self._state(), make_codebase(tmp_path))
            if c.type == "backlog-cache-unreadable"
        ]

        assert len(fired) == 2  # both probes report…
        assert len({_id(c) for c in fired}) == 1  # …and the store keeps one advisory


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
        # The two arms take different sentences, because only an in-flight
        # `Status:` is decay: a settled one naming the item that completed the
        # transition is that transition's own record. What is under test is the
        # emphasis tolerance of each marker, so each arm gets a line it would
        # legitimately fire on.
        lines = [
            (m, f"{m} the MIG-4C1K migration made a second system redundant.")
            for m in self.MARKERS
        ] + [
            (m, f"{m} in-transition — tracked in MIG-4C1K")
            for m in self.STATUS
        ]
        for m, line in lines:
            _write_backlog(
                tmp_path, _item("MIG-4C1K", section="Archive", status="shipped")
            )
            _write_artifact(
                tmp_path,
                "observability-strategy.md",
                _direction_artifact(
                    "- **All telemetry rides OpenTelemetry.**\n"
                    f"  {line}\n"
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


class TestBlockquotedNormFields:
    """A `Why:` inside a markdown blockquote is still a `Why:`.

    Found in the wild 2026-08-11: a product wrote every norm's rationale as
    `> **Why:** ...` and the norm-registry advisory told it, for a week and
    across several syncs, that "no `## Direction` section is ratified in any
    artifact" — while five ratified sections sat in its artifacts directory. An
    advisory that makes a claim the reader disproves by opening a file is a
    defect in the advisory.

    The blind spot was `^\\s*` in every field matcher: `>` is not whitespace.
    The fix strips blockquote markers in `_direction_lines`, the single point
    all four matchers read through, so entry detection and the soft-wrap joiner
    are fixed by one change rather than four regexes drifting apart later.

    The direct sibling of #569 (emphasis tolerance): same shape, same reason —
    `docs/norms.md` § Anatomy shows the canonical form; these read what authors
    actually write.
    """

    # The real shape from the affected repo: a BOLD STATEMENT PARAGRAPH (no
    # bullet) with a blockquoted Why. Both halves depart from the documented
    # anatomy, and it is the blockquote — not the missing bullet — that
    # `_has_direction_entry` trips on, since that function has never required a
    # bullet. Reproduced from the file rather than imagined, so a future edit
    # that "simplifies" this fixture into a bulleted one stops testing the bug.
    _WILD = (
        "# Architecture\n\n## Direction\n\n"
        "<!-- Ratified by the owner 2026-07-20. -->\n\n"
        "**The theme manifest file is the only channel from curation to display.** The\n"
        "display plane reads the manifest and the image tree.\n\n"
        "> **Why:** The availability norm says the display plane never requires the\n"
        "> curation plane to be reachable. A single file-shaped channel makes that\n"
        "> structurally true rather than carefully maintained.\n"
    )

    def test_the_wild_shape_is_an_entry(self):
        assert np._has_direction_entry(self._WILD) is True, (
            "a bold statement plus a blockquoted Why is a ratified norm entry"
        )

    def test_every_emphasis_form_survives_blockquoting(self):
        for marker in TestEmphasisAcrossEveryNormField.MARKERS:
            body = _direction_artifact(f"- **X.**\n\n> {marker} because.\n")
            assert np._has_direction_entry(body) is True, f"> {marker} must be an entry"

    def test_every_status_emphasis_form_survives_blockquoting(self):
        for marker in TestEmphasisAcrossEveryNormField.STATUS:
            body = _direction_artifact(f"- **X.**\n\n> {marker} steady-state.\n")
            assert np._has_direction_entry(body) is True, f"> {marker} must be an entry"

    def test_nested_blockquotes_are_stripped_too(self):
        body = _direction_artifact("- **X.**\n\n>> **Why:** quoted inside a quote.\n")
        assert np._has_direction_entry(body) is True

    def test_a_blockquote_marker_never_folds_into_the_prose(self):
        """The soft-wrap joiner's half of the same defect.

        A wrapped blockquoted field used to join as `"... says the > display
        plane ..."` — the marker landing mid-sentence in the text the citation
        scans read. Asserted on the joined line's CONTENT rather than on
        `_direction_lines`' length, because the bug was corruption, not count.
        """
        lines = np._direction_lines(self._WILD)
        why = [line for line in lines if "Why:" in line]
        assert why, "the blockquoted Why must survive as a logical line"
        assert ">" not in why[0], f"blockquote marker folded into prose: {why[0]!r}"
        assert "never requires the curation plane" in why[0], (
            "the wrapped continuation must still join onto the Why line"
        )

    def test_dead_why_reads_a_blockquoted_status(self, tmp_path):
        """Drives a PROBE end-to-end, not a regex.

        Following the #569 precedent: asserting the matcher directly stays green
        if the constant widens while the probe stops reaching it. `dead-why`
        scans lines that only exist if `_direction_lines` handed them over
        de-quoted, so this fails unless the whole path works.
        """
        _write_backlog(tmp_path, _item("OBS-1A2B", section="Archive", status="dead"))
        _write_artifact(
            tmp_path,
            "observability-strategy.md",
            _direction_artifact(
                "- **All telemetry rides OTel.**\n\n> **Why:** blocked on OBS-1A2B.\n"
            ),
        )
        found = np.probe_dead_why(ProjectState({}), _cb(tmp_path))
        assert found, "a dead citation inside a blockquoted Why must still be found"

    def test_a_blockquoted_roadmap_is_still_not_a_registry(self):
        """Loosening must not reopen the false-pass this detector exists for.

        #567: a `## Direction` section holding a prioritised list of undone work
        certified as a ratified registry. Blockquoting the roadmap must not buy
        it what plain formatting could not — the discriminator is the FIELD, and
        stripping `>` does not mint one.
        """
        body = (
            "# Architecture\n\n## Direction\n\n"
            "> - **Ship the importer.** Targeted for Q3.\n"
            "> - **Then the exporter.** Q4.\n"
        )
        assert np._has_direction_entry(body) is False

    def test_a_heading_only_direction_section_is_still_not_a_registry(self):
        body = "# Architecture\n\n## Direction\n\n> Nothing normative here.\n"
        assert np._has_direction_entry(body) is False


class TestBlockquotedEntriesCountTheSameInBothModules:
    """#568's invariant, re-asserted for the blockquote case.

    `record_lint.direction_norm_count` and `norm_probes._has_direction_entry`
    are one definition of a norm entry. When blockquote tolerance first landed
    it went into `_direction_lines` only — so the probes saw a blockquoted
    registry and record_lint saw an empty one, and `governed_by`'s
    `if not norms: continue` silently skipped exactly the products the
    tolerance was added for. Sharing the field regex was not enough; the
    blockquote prefix is part of the definition too.
    """

    _QUOTED = (
        "# Architecture\n\n## Direction\n\n"
        "- **The manifest is the only channel.**\n\n"
        "> **Why:** a single file-shaped channel makes the availability norm\n"
        "> structurally true rather than carefully maintained.\n"
    )
    _PLAIN = (
        "# Architecture\n\n## Direction\n\n"
        "- **The manifest is the only channel.**\n"
        "  Why: a single file-shaped channel makes it structurally true.\n"
    )

    def test_a_blockquoted_entry_counts_in_both(self):
        from lib import record_lint

        assert np._has_direction_entry(self._QUOTED) is True
        assert record_lint.direction_norm_count(self._QUOTED) == 1

    def test_quoting_an_entry_does_not_change_either_answer(self):
        """The two formats are the same registry, so both readers must agree
        across both of them — not merely agree with each other on one."""
        from lib import record_lint

        assert record_lint.direction_norm_count(self._QUOTED) == record_lint.direction_norm_count(
            self._PLAIN
        )
        assert np._has_direction_entry(self._QUOTED) == np._has_direction_entry(self._PLAIN)

    def test_a_blockquoted_roadmap_still_counts_zero_in_both(self):
        """The widening must not mint entries: the discriminator is the FIELD."""
        from lib import record_lint

        roadmap = (
            "# Architecture\n\n## Direction\n\n"
            "> - **Ship the importer.** Targeted for Q3.\n"
            "> - **Then the exporter.** Q4.\n"
        )
        assert record_lint.direction_norm_count(roadmap) == 0
        assert np._has_direction_entry(roadmap) is False


class TestBlockquotedHeadingsOpenASection:
    """The strip lands before heading detection, so `> ## Direction` opens a
    section. That is a widening beyond the field lines the fix was aimed at, and
    it is pinned here rather than left as an undocumented side effect.

    It is the correct reading — a heading inside a blockquote is still a heading
    of the quoted document, and the alternative (strip for fields but not for
    headings) would mean a wholly-quoted artifact had field lines belonging to
    no section, which is the inconsistency that produces a silent zero.
    """

    def test_a_quoted_direction_heading_opens_the_section(self):
        body = (
            "# Architecture\n\n> ## Direction\n\n"
            "> - **The manifest is the only channel.**\n"
            ">   Why: structurally true rather than carefully maintained.\n"
        )
        assert np._has_direction_entry(body) is True

    def test_a_quoted_heading_still_CLOSES_the_section(self):
        """The closing half must widen with the opening half. If `>` were
        stripped when opening but not when closing, a quoted sibling heading
        would leave the section open and swallow the rest of the document.
        """
        body = (
            "# Architecture\n\n> ## Direction\n\n"
            "> - **X.**\n>   Why: because.\n\n"
            "> ## Glossary\n\n"
            "> - **Y.**\n>   Why: this one is NOT in Direction.\n"
        )
        lines = np._direction_lines(body)
        joined = "\n".join(lines)
        assert "because" in joined
        assert "NOT in Direction" not in joined, "a quoted sibling heading must close the section"
