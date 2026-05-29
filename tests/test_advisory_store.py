"""Tests for tools/lib/advisory_store.py — post-sync advisory infrastructure.

Loads prawduct-setup.py via importlib (hyphenated filename) and reaches the
advisory module through the `_lib_advisory_store` submodule alias, mirroring the
`_lib_sync_cmd` access pattern used in test_prawduct_sync.py.

Covers Chunk 01 (spine): store I/O, id-hash, ProjectState/Codebase loaders, the
probe registry, the active/resolved reconcile diff, and the run_sync_advisories
orchestration. Dismissal (Ch 02), supersession (Ch 03), and compaction (Ch 04)
are tested in their own chunks.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

# Load prawduct-setup.py via importlib
_TOOL_PATH = Path(__file__).resolve().parent.parent / "tools" / "prawduct-setup.py"
_spec = importlib.util.spec_from_file_location("prawduct_setup", _TOOL_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

_adv = _mod._lib_advisory_store

AdvisoryCandidate = _adv.AdvisoryCandidate
Codebase = _adv.Codebase
ProjectState = _adv.ProjectState
clear_registry = _adv.clear_registry
compute_id = _adv.compute_id
dismiss = _adv.dismiss
undismiss = _adv.undismiss
load_project_state = _adv.load_project_state
make_codebase = _adv.make_codebase
read_store = _adv.read_store
reconcile = _adv.reconcile
register_probe = _adv.register_probe
run_all_probes = _adv.run_all_probes
run_sync_advisories = _adv.run_sync_advisories
write_store = _adv.write_store
EVIDENCE_CAP = _adv.EVIDENCE_CAP
SCHEMA_VERSION = _adv.SCHEMA_VERSION


@pytest.fixture(autouse=True)
def _clean_registry():
    """Keep the module-level probe registry empty around every test so a
    synthetic registration never leaks into another test (or the no-op ship)."""
    clear_registry()
    yield
    clear_registry()


def _candidate(evidence=("sig-1",), probe_version=1, ctype="synthetic-condition"):
    return AdvisoryCandidate(
        type=ctype,
        evidence=tuple(evidence),
        trigger_summary="Synthetic trigger present and not yet resolved.",
        recommended_action="/prawduct-advisory list",
        feature="synthetic",
        probe_version=probe_version,
    )


# ---------------------------------------------------------------------------
# compute_id
# ---------------------------------------------------------------------------


class TestComputeId:
    def test_format(self):
        aid = compute_id("synthetic", "synthetic-condition", 1, ["a", "b"])
        assert aid.startswith("synthetic-synthetic-condition-v1-")
        assert len(aid.rsplit("-", 1)[-1]) == 6

    def test_idempotent_same_evidence_same_version(self):
        a = compute_id("f", "t", 1, ["x", "y"])
        b = compute_id("f", "t", 1, ["x", "y"])
        assert a == b

    def test_different_evidence_changes_id(self):
        a = compute_id("f", "t", 1, ["x"])
        b = compute_id("f", "t", 1, ["y"])
        assert a != b

    def test_version_bump_changes_id(self):
        a = compute_id("f", "t", 1, ["x"])
        b = compute_id("f", "t", 2, ["x"])
        assert a != b


# ---------------------------------------------------------------------------
# Store I/O
# ---------------------------------------------------------------------------


class TestStoreIO:
    def test_missing_file_returns_empty(self, tmp_path: Path):
        store = read_store(tmp_path)
        assert store == {"schema_version": SCHEMA_VERSION, "advisories": []}

    def test_corrupt_file_returns_empty(self, tmp_path: Path):
        (tmp_path / ".prawduct").mkdir()
        (tmp_path / ".prawduct" / ".advisories.json").write_text("not json{{{")
        store = read_store(tmp_path)
        assert store["advisories"] == []

    def test_wrong_shape_returns_empty(self, tmp_path: Path):
        (tmp_path / ".prawduct").mkdir()
        (tmp_path / ".prawduct" / ".advisories.json").write_text(json.dumps({"advisories": "nope"}))
        store = read_store(tmp_path)
        assert store["advisories"] == []

    def test_roundtrip(self, tmp_path: Path):
        store = {"schema_version": SCHEMA_VERSION, "advisories": [{"id": "x", "state": "active"}]}
        result = write_store(tmp_path, store)
        assert result["status"] == "ok"
        assert read_store(tmp_path) == store

    def test_write_creates_prawduct_dir(self, tmp_path: Path):
        result = write_store(tmp_path, {"schema_version": 1, "advisories": []})
        assert result["status"] == "ok"
        assert (tmp_path / ".prawduct" / ".advisories.json").is_file()


# ---------------------------------------------------------------------------
# ProjectState / Codebase
# ---------------------------------------------------------------------------


class TestLoadProjectState:
    def test_missing_file(self, tmp_path: Path):
        state = load_project_state(tmp_path)
        assert state.get("anything") is None

    def test_scalar_coercion(self, tmp_path: Path):
        (tmp_path / ".prawduct").mkdir()
        (tmp_path / ".prawduct" / "project-state.yaml").write_text(
            "uses_llm_inference: true\n"
            "count: 7\n"
            "name: My App\n"
            "missing: null\n"
            "nested:\n"
            "  child: ignored\n"
        )
        state = load_project_state(tmp_path)
        assert state.get("uses_llm_inference") is True
        assert state.get("count") == 7
        assert state.get("name") == "My App"
        assert state.get("missing") is None
        # nested-block header is skipped; indented child not a top-level scalar
        assert state.get("nested") is None
        assert state.get("child") is None

    def test_comment_stripped(self, tmp_path: Path):
        (tmp_path / ".prawduct").mkdir()
        (tmp_path / ".prawduct" / "project-state.yaml").write_text(
            "flag: false  # a trailing comment\n"
        )
        assert load_project_state(tmp_path).get("flag") is False

    def test_construct_directly(self):
        state = ProjectState({"k": "v"})
        assert state.get("k") == "v"
        assert state.as_dict() == {"k": "v"}


class TestCodebase:
    def test_make_codebase_roots_at_dir(self, tmp_path: Path):
        cb = make_codebase(tmp_path)
        assert cb.root == tmp_path

    def test_has_files_matching(self, tmp_path: Path):
        (tmp_path / ".claude" / "skills" / "foo").mkdir(parents=True)
        (tmp_path / ".claude" / "skills" / "foo" / "SKILL.md").write_text("x")
        cb = Codebase(root=tmp_path)
        assert cb.has_files_matching(".claude/skills/*/SKILL.md") is True
        assert cb.has_files_matching("nope/*.txt") is False

    def test_has_imports(self, tmp_path: Path):
        (tmp_path / "client.py").write_text("import anthropic\nfrom os import path\n")
        cb = Codebase(root=tmp_path)
        assert cb.has_imports(["anthropic", "openai"]) is True
        assert cb.has_imports(["openai"]) is False
        assert cb.has_imports([]) is False

    def test_has_imports_skips_vendored_dirs(self, tmp_path: Path):
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "dep.py").write_text("import anthropic\n")
        cb = Codebase(root=tmp_path)
        assert cb.has_imports(["anthropic"]) is False


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_register_and_run(self, tmp_path: Path):
        register_probe("synthetic", "synthetic-condition", 3, lambda s, c: [_candidate()])
        candidates = run_all_probes(ProjectState(), make_codebase(tmp_path))
        assert len(candidates) == 1
        # feature + probe_version stamped from registration
        assert candidates[0].feature == "synthetic"
        assert candidates[0].probe_version == 3

    def test_type_defaults_to_probe_type(self, tmp_path: Path):
        register_probe(
            "synthetic",
            "the-type",
            1,
            lambda s, c: [AdvisoryCandidate(type="", evidence=("e",))],
        )
        candidates = run_all_probes(ProjectState(), make_codebase(tmp_path))
        assert candidates[0].type == "the-type"

    def test_faulty_probe_skipped(self, tmp_path: Path):
        def _boom(state, codebase):
            raise RuntimeError("probe blew up")

        register_probe("bad", "boom", 1, _boom)
        register_probe("good", "ok", 1, lambda s, c: [_candidate()])
        candidates = run_all_probes(ProjectState(), make_codebase(tmp_path))
        # The faulty probe is skipped; the good one still produces its candidate.
        assert len(candidates) == 1

    def test_clear_registry(self, tmp_path: Path):
        register_probe("synthetic", "c", 1, lambda s, c: [_candidate()])
        clear_registry()
        assert run_all_probes(ProjectState(), make_codebase(tmp_path)) == []


# ---------------------------------------------------------------------------
# reconcile
# ---------------------------------------------------------------------------


class TestReconcile:
    def test_new_candidate_becomes_active(self):
        store = {"schema_version": 1, "advisories": []}
        new = reconcile(store, [_candidate()], now="2026-05-29T00:00:00Z", sync_version="v1.6.0")
        assert len(new["advisories"]) == 1
        adv = new["advisories"][0]
        assert adv["state"] == "active"
        assert adv["feature"] == "synthetic"
        assert adv["triggered_by_sync_version"] == "v1.6.0"
        assert adv["resolved_at"] is None

    def test_idempotent_no_duplicate(self):
        store = {"schema_version": 1, "advisories": []}
        first = reconcile(store, [_candidate()], now="2026-05-29T00:00:00Z")
        second = reconcile(first, [_candidate()], now="2026-05-30T00:00:00Z")
        assert len(second["advisories"]) == 1
        # triggered_at not bumped on re-fire
        assert second["advisories"][0]["triggered_at"] == "2026-05-29T00:00:00Z"

    def test_active_not_reproduced_is_resolved(self):
        store = {"schema_version": 1, "advisories": []}
        active = reconcile(store, [_candidate()], now="2026-05-29T00:00:00Z")
        # candidate no longer fires (resolution fact landed)
        resolved = reconcile(active, [], now="2026-05-31T00:00:00Z")
        adv = resolved["advisories"][0]
        assert adv["state"] == "resolved"
        assert adv["resolved_by"] == "sync"
        assert adv["resolved_at"] == "2026-05-31T00:00:00Z"

    def test_resolved_reactivates_when_candidate_returns(self):
        store = {"schema_version": 1, "advisories": []}
        active = reconcile(store, [_candidate()], now="2026-05-29T00:00:00Z")
        resolved = reconcile(active, [], now="2026-05-31T00:00:00Z")
        reactivated = reconcile(resolved, [_candidate()], now="2026-06-01T00:00:00Z")
        adv = reactivated["advisories"][0]
        assert adv["state"] == "active"
        assert adv["resolved_at"] is None
        # original first-seen timestamp preserved
        assert adv["triggered_at"] == "2026-05-29T00:00:00Z"

    def test_evidence_capped_in_store(self):
        many = tuple(f"sig-{i}" for i in range(EVIDENCE_CAP + 4))
        store = {"schema_version": 1, "advisories": []}
        new = reconcile(store, [_candidate(evidence=many)], now="2026-05-29T00:00:00Z")
        assert len(new["advisories"][0]["evidence"]) == EVIDENCE_CAP


# ---------------------------------------------------------------------------
# run_sync_advisories (orchestration end-to-end)
# ---------------------------------------------------------------------------


class TestRunSyncAdvisories:
    def _trigger_probe(self, state, codebase):
        # Resolution condition: project answered the question.
        if state.get("synthetic_resolved") is True:
            return []
        # Trigger condition: a fake codebase signal.
        if not codebase.has_files_matching("SYNTHETIC_TRIGGER"):
            return []
        return [_candidate(evidence=("SYNTHETIC_TRIGGER present",))]

    def test_empty_roster_writes_empty_store(self, tmp_path: Path):
        result = run_sync_advisories(tmp_path, now="2026-05-29T00:00:00Z", sync_version="v1.6.0")
        assert result["active"] == 0
        assert read_store(tmp_path)["advisories"] == []

    def test_trigger_then_resolve(self, tmp_path: Path):
        (tmp_path / ".prawduct").mkdir()
        (tmp_path / "SYNTHETIC_TRIGGER").write_text("x")
        register_probe("synthetic", "synthetic-condition", 1, self._trigger_probe)

        first = run_sync_advisories(tmp_path, now="2026-05-29T00:00:00Z", sync_version="v1.6.0")
        assert first["active"] == 1

        # Running again with unchanged state does not duplicate (A2).
        again = run_sync_advisories(tmp_path, now="2026-05-29T00:01:00Z", sync_version="v1.6.0")
        assert again["active"] == 1
        assert len(read_store(tmp_path)["advisories"]) == 1

        # Team answers the question in the shared store → probe stops firing →
        # advisory auto-resolves (spec §4.2 / §7.1).
        (tmp_path / ".prawduct" / "project-state.yaml").write_text("synthetic_resolved: true\n")
        resolved = run_sync_advisories(tmp_path, now="2026-06-01T00:00:00Z", sync_version="v1.6.0")
        assert resolved["active"] == 0
        assert resolved["newly_resolved"]
        adv = read_store(tmp_path)["advisories"][0]
        assert adv["state"] == "resolved"
        assert adv["resolved_by"] == "sync"


# ---------------------------------------------------------------------------
# Dismissal lifecycle (Chunk 02)
# ---------------------------------------------------------------------------


class TestDismissal:
    def _seed_active(self, tmp_path: Path):
        store = reconcile(
            {"schema_version": 1, "advisories": []},
            [_candidate(evidence=("e",))],
            now="2026-05-29T00:00:00Z",
        )
        write_store(tmp_path, store)
        return store["advisories"][0]["id"]

    def test_dismiss_sets_fields(self, tmp_path: Path):
        aid = self._seed_active(tmp_path)
        result = dismiss(tmp_path, aid, reason="not relevant", now="2026-05-29T01:00:00Z")
        assert result["status"] == "ok"
        adv = read_store(tmp_path)["advisories"][0]
        assert adv["state"] == "dismissed"
        assert adv["dismissed_at"] == "2026-05-29T01:00:00Z"
        assert adv["dismissed_reason"] == "not relevant"

    def test_dismiss_reason_optional(self, tmp_path: Path):
        aid = self._seed_active(tmp_path)
        dismiss(tmp_path, aid)
        assert read_store(tmp_path)["advisories"][0]["dismissed_reason"] is None

    def test_dismiss_not_found(self, tmp_path: Path):
        self._seed_active(tmp_path)
        assert dismiss(tmp_path, "no-such-id")["status"] == "not_found"

    def test_dismissal_is_sticky_across_sync(self, tmp_path: Path):
        """A4: a dismissed advisory does not re-surface even if the trigger persists."""
        aid = self._seed_active(tmp_path)
        dismiss(tmp_path, aid, now="2026-05-29T01:00:00Z")
        # Re-sync with the candidate STILL firing.
        store = reconcile(
            read_store(tmp_path),
            [_candidate(evidence=("e",))],
            now="2026-05-30T00:00:00Z",
        )
        adv = store["advisories"][0]
        assert adv["state"] == "dismissed"

    def test_undismiss_returns_to_active(self, tmp_path: Path):
        aid = self._seed_active(tmp_path)
        dismiss(tmp_path, aid, now="2026-05-29T01:00:00Z")
        result = undismiss(tmp_path, aid)
        assert result["status"] == "ok"
        adv = read_store(tmp_path)["advisories"][0]
        assert adv["state"] == "active"
        assert adv["dismissed_at"] is None
        # And a subsequent sync with the probe still firing keeps it active.
        store = reconcile(read_store(tmp_path), [_candidate(evidence=("e",))], now="2026-06-01T00:00:00Z")
        assert store["advisories"][0]["state"] == "active"

    def test_undismiss_not_found(self, tmp_path: Path):
        assert undismiss(tmp_path, "no-such-id")["status"] == "not_found"
