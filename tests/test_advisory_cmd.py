"""Tests for tools/lib/advisory_cmd.py — the /prawduct-advisory management CLI.

Loads prawduct-setup.py via importlib (hyphenated filename) and reaches the CLI
module through the `_lib_advisory_cmd` submodule alias (mirroring the
`_lib_advisory_store` pattern in test_advisory_store.py).

Covers Chunk 05: the five subcommands (list/show/dismiss/undismiss/resolve), the
Q5 evidence-reconstruction-on-show path, action-driven resolve, and the argv
dispatcher (`run`) including flag parsing and fail-closed exit codes.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_TOOL_PATH = Path(__file__).resolve().parent.parent / "tools" / "prawduct-setup.py"
_spec = importlib.util.spec_from_file_location("prawduct_setup", _TOOL_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

_cmd = _mod._lib_advisory_cmd
_adv = _mod._lib_advisory_store

AdvisoryCandidate = _adv.AdvisoryCandidate
EVIDENCE_CAP = _adv.EVIDENCE_CAP
clear_registry = _adv.clear_registry
register_probe = _adv.register_probe
read_store = _adv.read_store
write_store = _adv.write_store
run_sync_advisories = _adv.run_sync_advisories


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_registry()
    yield
    clear_registry()


# ---------------------------------------------------------------------------
# Store-builder helpers
# ---------------------------------------------------------------------------


def _active(advisory_id, feature, ctype="synthetic-condition", triggered_at="2026-05-01T00:00:00Z"):
    return {
        "id": advisory_id,
        "feature": feature,
        "type": ctype,
        "probe_version": 1,
        "triggered_at": triggered_at,
        "triggered_by_sync_version": "",
        "trigger_summary": f"{feature} trigger present.",
        "evidence": ["sig-a", "sig-b"],
        "recommended_action": f"/{feature} fix",
        "alternative_actions": [],
        "priority": "info",
        "state": "active",
        "superseded_by": None,
        "dismissed_at": None,
        "dismissed_reason": None,
        "resolved_at": None,
        "resolved_by": None,
    }


def _dismissed_compact(advisory_id):
    return {
        "id": advisory_id,
        "state": "dismissed",
        "dismissed_at": "2026-05-02T00:00:00Z",
        "dismissed_reason": "not now",
    }


def _resolved_compact(advisory_id):
    return {
        "id": advisory_id,
        "state": "resolved",
        "resolved_at": "2026-05-03T00:00:00Z",
        "resolved_by": "sync",
    }


def _seed_store(product, advisories):
    write_store(product, {"schema_version": 1, "advisories": advisories})


def _synthetic_probe(evidence):
    """Register a synthetic probe (feature `synthetic`) returning fixed evidence."""

    def fn(state, codebase):
        return [
            AdvisoryCandidate(
                type="synthetic-condition",
                evidence=tuple(evidence),
                trigger_summary="Synthetic trigger present.",
                recommended_action="/prawduct-advisory list",
            )
        ]

    register_probe("synthetic", "synthetic-condition", 1, fn)


# ---------------------------------------------------------------------------
# list_advisories (A6)
# ---------------------------------------------------------------------------


class TestListFilters:
    def _mixed(self, product):
        _seed_store(
            product,
            [
                _active("synthetic-synthetic-condition-v1-aaa111", "synthetic"),
                _active("backlog-legacy-format-v1-bbb222", "backlog"),
                _dismissed_compact("backlog-external-detected-v1-ccc333"),
                _resolved_compact("synthetic-old-v1-ddd444"),
            ],
        )

    def test_default_state_is_active(self, tmp_path):
        self._mixed(tmp_path)
        result = _cmd.list_advisories(str(tmp_path))
        assert result["state"] == "active"
        assert result["count"] == 2
        assert {a["feature"] for a in result["advisories"]} == {"synthetic", "backlog"}

    def test_state_dismissed(self, tmp_path):
        self._mixed(tmp_path)
        result = _cmd.list_advisories(str(tmp_path), state="dismissed")
        assert result["count"] == 1
        assert result["advisories"][0]["id"] == "backlog-external-detected-v1-ccc333"

    def test_state_resolved(self, tmp_path):
        self._mixed(tmp_path)
        result = _cmd.list_advisories(str(tmp_path), state="resolved")
        assert result["count"] == 1
        assert result["advisories"][0]["state"] == "resolved"

    def test_state_all(self, tmp_path):
        self._mixed(tmp_path)
        result = _cmd.list_advisories(str(tmp_path), state="all")
        assert result["count"] == 4

    def test_feature_filter_active(self, tmp_path):
        self._mixed(tmp_path)
        result = _cmd.list_advisories(str(tmp_path), feature="synthetic")
        assert result["count"] == 1
        assert result["advisories"][0]["feature"] == "synthetic"

    def test_feature_filter_matches_compact_by_id_prefix(self, tmp_path):
        """Compact entries drop `feature`; the id-prefix recovers the match."""
        self._mixed(tmp_path)
        result = _cmd.list_advisories(str(tmp_path), state="all", feature="backlog")
        ids = {a["id"] for a in result["advisories"]}
        # active backlog + the compact dismissed backlog entry (no feature field)
        assert ids == {"backlog-legacy-format-v1-bbb222", "backlog-external-detected-v1-ccc333"}

    def test_empty_store(self, tmp_path):
        result = _cmd.list_advisories(str(tmp_path))
        assert result["count"] == 0
        assert result["advisories"] == []


# ---------------------------------------------------------------------------
# show_advisory + Q5 evidence reconstruction
# ---------------------------------------------------------------------------


class TestShow:
    def test_not_found(self, tmp_path):
        result = _cmd.show_advisory(str(tmp_path), "nope-v1-000000")
        assert result["status"] == "not_found"

    def test_active_returns_stored_evidence(self, tmp_path):
        _seed_store(tmp_path, [_active("synthetic-synthetic-condition-v1-aaa111", "synthetic")])
        result = _cmd.show_advisory(str(tmp_path), "synthetic-synthetic-condition-v1-aaa111")
        assert result["status"] == "ok"
        assert result["evidence_reconstructed"] is False
        assert result["advisory"]["evidence"] == ["sig-a", "sig-b"]

    def test_compact_entry_reconstructs_full_evidence(self, tmp_path):
        """A dismissed (compact) entry whose probe still fires gets its full,
        uncapped evidence list rebuilt on show (Q5)."""
        evidence = [f"src/file{i}.py:1" for i in range(8)]  # > EVIDENCE_CAP
        _synthetic_probe(evidence)
        # Trigger → store has active advisory (evidence capped at 5).
        run_sync_advisories(str(tmp_path))
        store = read_store(str(tmp_path))
        advisory_id = store["advisories"][0]["id"]
        assert len(store["advisories"][0]["evidence"]) == EVIDENCE_CAP
        # Dismiss, then sync again → entry compacts to dismissed form (no evidence).
        _cmd.dismiss_advisory(str(tmp_path), advisory_id, "later")
        run_sync_advisories(str(tmp_path))
        compact = read_store(str(tmp_path))["advisories"][0]
        assert compact["state"] == "dismissed"
        assert "evidence" not in compact
        # show re-runs the probe (still registered/firing) → full 8-item list.
        result = _cmd.show_advisory(str(tmp_path), advisory_id)
        assert result["evidence_reconstructed"] is True
        assert result["advisory"]["evidence"] == evidence
        assert len(result["advisory"]["evidence"]) > EVIDENCE_CAP

    def test_compact_entry_unrecoverable_when_probe_silent(self, tmp_path):
        """When no probe produces the id, show returns the compact form, not reconstructed."""
        _seed_store(tmp_path, [_resolved_compact("synthetic-old-v1-ddd444")])
        result = _cmd.show_advisory(str(tmp_path), "synthetic-old-v1-ddd444")
        assert result["status"] == "ok"
        assert result["evidence_reconstructed"] is False
        assert not result["advisory"].get("evidence")


# ---------------------------------------------------------------------------
# resolve_advisory (action-driven, §4.3)
# ---------------------------------------------------------------------------


class TestResolve:
    def test_resolve_writes_action_without_sync(self, tmp_path):
        _seed_store(tmp_path, [_active("synthetic-synthetic-condition-v1-aaa111", "synthetic")])
        result = _cmd.resolve_advisory(str(tmp_path), "synthetic-synthetic-condition-v1-aaa111")
        assert result["status"] == "ok"
        entry = read_store(str(tmp_path))["advisories"][0]
        assert entry["state"] == "resolved"
        assert entry["resolved_by"] == "action"
        assert entry["resolved_at"]

    def test_resolve_not_found(self, tmp_path):
        result = _cmd.resolve_advisory(str(tmp_path), "missing-v1-000000")
        assert result["status"] == "not_found"


# ---------------------------------------------------------------------------
# dismiss / undismiss delegation
# ---------------------------------------------------------------------------


class TestUndismissAfterCompaction:
    """Regression: undismiss reaches a *compacted* entry (Chunk 05 exposes the
    verb). Compaction drops feature/evidence/summary/action; undismiss only
    flips the state. The next sync must rehydrate (probe fires) or auto-resolve
    (probe silent) — never leave a blank-summary advisory live forever."""

    def test_rehydrates_on_next_sync_when_probe_fires(self, tmp_path):
        evidence = ["src/a.py:1", "src/b.py:2"]
        _synthetic_probe(evidence)
        run_sync_advisories(str(tmp_path))
        advisory_id = read_store(str(tmp_path))["advisories"][0]["id"]
        _cmd.dismiss_advisory(str(tmp_path), advisory_id, "later")
        run_sync_advisories(str(tmp_path))  # compacts dismissed (drops fields)
        assert "trigger_summary" not in read_store(str(tmp_path))["advisories"][0]
        _cmd.undismiss_advisory(str(tmp_path), advisory_id)  # active stub, no triggered_at
        stub = read_store(str(tmp_path))["advisories"][0]
        assert stub["state"] == "active" and not stub.get("trigger_summary")
        run_sync_advisories(str(tmp_path))  # reconcile rehydrates from candidate
        full = read_store(str(tmp_path))["advisories"][0]
        assert full["state"] == "active"
        assert full["feature"] == "synthetic"
        assert full["trigger_summary"] == "Synthetic trigger present."
        assert full["recommended_action"] == "/prawduct-advisory list"
        assert full["triggered_at"]
        assert full["evidence"]

    def test_autoresolves_on_next_sync_when_probe_silent(self, tmp_path):
        _synthetic_probe(["src/a.py:1"])
        run_sync_advisories(str(tmp_path))
        advisory_id = read_store(str(tmp_path))["advisories"][0]["id"]
        _cmd.dismiss_advisory(str(tmp_path), advisory_id, "later")
        run_sync_advisories(str(tmp_path))  # compact dismissed
        _cmd.undismiss_advisory(str(tmp_path), advisory_id)  # active stub
        clear_registry()  # probe goes silent
        run_sync_advisories(str(tmp_path))
        entry = read_store(str(tmp_path))["advisories"][0]
        assert entry["state"] == "resolved"
        assert entry["resolved_by"] == "sync"


class TestDismissUndismiss:
    def test_dismiss_then_undismiss(self, tmp_path):
        _seed_store(tmp_path, [_active("synthetic-synthetic-condition-v1-aaa111", "synthetic")])
        assert _cmd.dismiss_advisory(str(tmp_path), "synthetic-synthetic-condition-v1-aaa111", "nope")["status"] == "ok"
        entry = read_store(str(tmp_path))["advisories"][0]
        assert entry["state"] == "dismissed"
        assert entry["dismissed_reason"] == "nope"
        assert _cmd.undismiss_advisory(str(tmp_path), "synthetic-synthetic-condition-v1-aaa111")["status"] == "ok"
        assert read_store(str(tmp_path))["advisories"][0]["state"] == "active"

    def test_dismiss_not_found(self, tmp_path):
        assert _cmd.dismiss_advisory(str(tmp_path), "missing-v1-000000")["status"] == "not_found"


# ---------------------------------------------------------------------------
# run() — argv dispatcher (the CLI boundary)
# ---------------------------------------------------------------------------


class TestRunDispatcher:
    def test_no_args_is_usage_error(self, tmp_path, capsys):
        assert _cmd.run(str(tmp_path), []) == 1
        assert "Usage" in capsys.readouterr().err

    def test_unknown_subcommand(self, tmp_path, capsys):
        assert _cmd.run(str(tmp_path), ["frobnicate"]) == 1
        assert "Usage" in capsys.readouterr().err

    def test_list_default(self, tmp_path, capsys):
        _seed_store(tmp_path, [_active("synthetic-synthetic-condition-v1-aaa111", "synthetic")])
        assert _cmd.run(str(tmp_path), ["list"]) == 0
        out = capsys.readouterr().out
        assert "synthetic-synthetic-condition-v1-aaa111" in out

    def test_list_state_flag(self, tmp_path, capsys):
        _seed_store(tmp_path, [_dismissed_compact("backlog-x-v1-ccc333")])
        assert _cmd.run(str(tmp_path), ["list", "--state=dismissed"]) == 0
        assert "backlog-x-v1-ccc333" in capsys.readouterr().out

    def test_list_invalid_state(self, tmp_path, capsys):
        assert _cmd.run(str(tmp_path), ["list", "--state=bogus"]) == 1
        assert "Invalid --state" in capsys.readouterr().err

    def test_list_feature_flag(self, tmp_path, capsys):
        _seed_store(
            tmp_path,
            [
                _active("synthetic-synthetic-condition-v1-aaa111", "synthetic"),
                _active("backlog-legacy-format-v1-bbb222", "backlog"),
            ],
        )
        assert _cmd.run(str(tmp_path), ["list", "--feature=backlog"]) == 0
        out = capsys.readouterr().out
        assert "backlog-legacy-format-v1-bbb222" in out
        assert "synthetic-synthetic-condition-v1-aaa111" not in out

    def test_list_unknown_flag(self, tmp_path, capsys):
        assert _cmd.run(str(tmp_path), ["list", "--bogus"]) == 1
        assert "Unknown flag" in capsys.readouterr().err

    def test_show_missing_id(self, tmp_path, capsys):
        assert _cmd.run(str(tmp_path), ["show"]) == 1
        assert "requires an advisory id" in capsys.readouterr().err

    def test_show_not_found_exit_code(self, tmp_path, capsys):
        assert _cmd.run(str(tmp_path), ["show", "missing-v1-000000"]) == 1
        assert "not found" in capsys.readouterr().err.lower()

    def test_dismiss_with_reason_separate_token(self, tmp_path):
        _seed_store(tmp_path, [_active("synthetic-synthetic-condition-v1-aaa111", "synthetic")])
        assert _cmd.run(str(tmp_path), ["dismiss", "synthetic-synthetic-condition-v1-aaa111", "--reason", "later"]) == 0
        entry = read_store(str(tmp_path))["advisories"][0]
        assert entry["state"] == "dismissed"
        assert entry["dismissed_reason"] == "later"

    def test_dismiss_with_reason_equals_form(self, tmp_path):
        _seed_store(tmp_path, [_active("synthetic-synthetic-condition-v1-aaa111", "synthetic")])
        assert _cmd.run(str(tmp_path), ["dismiss", "synthetic-synthetic-condition-v1-aaa111", "--reason=busy"]) == 0
        assert read_store(str(tmp_path))["advisories"][0]["dismissed_reason"] == "busy"

    def test_dismiss_missing_id(self, tmp_path, capsys):
        assert _cmd.run(str(tmp_path), ["dismiss"]) == 1
        assert "requires an advisory id" in capsys.readouterr().err

    def test_undismiss_dispatch(self, tmp_path):
        _seed_store(tmp_path, [_dismissed_compact("synthetic-synthetic-condition-v1-aaa111")])
        assert _cmd.run(str(tmp_path), ["undismiss", "synthetic-synthetic-condition-v1-aaa111"]) == 0
        assert read_store(str(tmp_path))["advisories"][0]["state"] == "active"

    def test_resolve_dispatch(self, tmp_path):
        _seed_store(tmp_path, [_active("synthetic-synthetic-condition-v1-aaa111", "synthetic")])
        assert _cmd.run(str(tmp_path), ["resolve", "synthetic-synthetic-condition-v1-aaa111"]) == 0
        assert read_store(str(tmp_path))["advisories"][0]["resolved_by"] == "action"
