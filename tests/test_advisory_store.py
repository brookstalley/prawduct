"""Tests for lib/advisory_store.py — advisory infrastructure (store + registry).

Imports the advisory module directly from the plugin's `lib/`.

Covers Chunk 01 (spine): store I/O, id-hash, ProjectState/Codebase loaders, the
probe registry, the active/resolved reconcile diff, and the run_sync_advisories
orchestration. Dismissal (Ch 02), supersession (Ch 03), and compaction (Ch 04)
are tested in their own chunks.
"""

from __future__ import annotations

import sys
import json
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib import advisory_store as _adv  # noqa: E402

AdvisoryCandidate = _adv.AdvisoryCandidate
Codebase = _adv.Codebase
ProjectState = _adv.ProjectState
apply_retention = _adv.apply_retention
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
RESOLVED_TTL_DAYS = _adv.RESOLVED_TTL_DAYS
ACTIVE_CAP = _adv.ACTIVE_CAP
RESOLVED_CAP = _adv.RESOLVED_CAP
DISMISSED_CAP = _adv.DISMISSED_CAP


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

    def test_corrupt_file_preserves_bytes_in_sentinel(self, tmp_path: Path):
        """ADV-9K2T: an existing unparseable store is stashed aside as
        ``.advisories.json.corrupt`` (carrying the original bytes) before the
        empty default is returned — corruption is surfaced, not swallowed."""
        (tmp_path / ".prawduct").mkdir()
        original = "not json{{{"
        (tmp_path / ".prawduct" / ".advisories.json").write_text(original)
        store = read_store(tmp_path)
        assert store == {"schema_version": SCHEMA_VERSION, "advisories": []}
        sentinel = tmp_path / ".prawduct" / ".advisories.json.corrupt"
        assert sentinel.is_file()
        assert sentinel.read_text() == original

    def test_wrong_shape_returns_empty(self, tmp_path: Path):
        (tmp_path / ".prawduct").mkdir()
        (tmp_path / ".prawduct" / ".advisories.json").write_text(json.dumps({"advisories": "nope"}))
        store = read_store(tmp_path)
        assert store["advisories"] == []

    def test_wrong_shape_writes_sentinel(self, tmp_path: Path):
        """ADV-9K2T: a store that parses but has the wrong shape (advisories not
        a list / not a dict) is also preserved aside before returning empty."""
        (tmp_path / ".prawduct").mkdir()
        original = json.dumps({"advisories": "nope"})
        (tmp_path / ".prawduct" / ".advisories.json").write_text(original)
        store = read_store(tmp_path)
        assert store["advisories"] == []
        sentinel = tmp_path / ".prawduct" / ".advisories.json.corrupt"
        assert sentinel.is_file()
        assert sentinel.read_text() == original

    def test_missing_file_writes_no_sentinel(self, tmp_path: Path):
        """A missing store is the normal first-run empty path — never corruption,
        so no ``.corrupt`` sentinel is written."""
        read_store(tmp_path)
        assert not (tmp_path / ".prawduct" / ".advisories.json.corrupt").exists()

    def test_valid_file_writes_no_sentinel(self, tmp_path: Path):
        """A valid store reads cleanly with no ``.corrupt`` sentinel written."""
        write_store(tmp_path, {"schema_version": SCHEMA_VERSION, "advisories": [{"id": "x", "state": "active"}]})
        read_store(tmp_path)
        assert not (tmp_path / ".prawduct" / ".advisories.json.corrupt").exists()

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

    def test_undecodable_file_degrades_to_empty_state(self, tmp_path: Path):
        # A non-UTF-8 project-state.yaml must read as "no facts", never raise:
        # this loader runs inside the session-start probe sync and `advisory
        # show`, where a UnicodeDecodeError killed the whole advisory subsystem
        # (only OSError was caught before the fix).
        (tmp_path / ".prawduct").mkdir()
        (tmp_path / ".prawduct" / "project-state.yaml").write_bytes(
            b"\xff\xfeuses_llm_inference: true\n"
        )
        state = load_project_state(tmp_path)
        assert state.get("uses_llm_inference") is None
        assert state.as_dict() == {}


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

    def test_has_source_matching_existence(self, tmp_path: Path):
        (tmp_path / "openapi.yaml").write_text("openapi: 3.0.0\n")
        cb = Codebase(root=tmp_path)
        # needles omitted → existence alone is the signal
        assert cb.has_source_matching(["openapi*.yaml", "*.proto"]) is True
        assert cb.has_source_matching(["*.proto"]) is False
        assert cb.has_source_matching([]) is False

    def test_has_source_matching_content(self, tmp_path: Path):
        (tmp_path / "package.json").write_text('{"dependencies": {"express": "^4"}}\n')
        cb = Codebase(root=tmp_path)
        assert cb.has_source_matching(["package.json"], ['"express"']) is True
        assert cb.has_source_matching(["package.json"], ['"fastify"']) is False

    def test_has_source_matching_skips_vendored_dirs(self, tmp_path: Path):
        nm = tmp_path / "node_modules" / "dep"
        nm.mkdir(parents=True)
        (nm / "package.json").write_text('{"dependencies": {"express": "^4"}}\n')
        cb = Codebase(root=tmp_path)
        # the only express manifest is vendored → pruned, no match (existence or content)
        assert cb.has_source_matching(["package.json"], ['"express"']) is False
        assert cb.has_source_matching(["package.json"]) is False


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

    def test_faulty_probe_skipped(self, tmp_path: Path, capsys):
        def _boom(state, codebase):
            raise RuntimeError("probe blew up")

        register_probe("bad", "boom", 1, _boom)
        register_probe("good", "ok", 1, lambda s, c: [_candidate()])
        candidates = run_all_probes(ProjectState(), make_codebase(tmp_path))
        # The faulty probe is skipped; the good one still produces its candidate.
        assert len(candidates) == 1
        # ... and the skip is attributed on stderr, never silent.
        err = capsys.readouterr().err
        assert "advisory probe bad/boom skipped" in err
        assert "probe blew up" in err

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
# Probe versioning & supersession (Chunk 03, spec §2.8 / A8)
# ---------------------------------------------------------------------------


class TestSupersession:
    def test_version_bump_supersedes_old_active(self):
        """A8: bumping probe_version retires the old advisory with
        resolved_by=probe-update + superseded_by, and surfaces the new one active."""
        v1 = reconcile({"schema_version": 1, "advisories": []}, [_candidate(probe_version=1)], now="2026-05-29T00:00:00Z")
        old_id = v1["advisories"][0]["id"]

        bumped = reconcile(v1, [_candidate(probe_version=2)], now="2026-05-30T00:00:00Z")
        advs = {a["id"]: a for a in bumped["advisories"]}

        old = advs[old_id]
        assert old["state"] == "resolved"
        assert old["resolved_by"] == "probe-update"
        assert old["resolved_at"] == "2026-05-30T00:00:00Z"
        new_id = old["superseded_by"]
        assert new_id is not None and new_id != old_id

        new = advs[new_id]
        assert new["state"] == "active"
        assert new["probe_version"] == 2
        # One current (active) + one retired (resolved) — no duplicate active.
        assert len(bumped["advisories"]) == 2

    def test_supersession_stable_on_resync(self):
        """Re-syncing at v2 does not re-resolve the retired entry or duplicate the new one."""
        v1 = reconcile({"schema_version": 1, "advisories": []}, [_candidate(probe_version=1)], now="2026-05-29T00:00:00Z")
        v2 = reconcile(v1, [_candidate(probe_version=2)], now="2026-05-30T00:00:00Z")
        again = reconcile(v2, [_candidate(probe_version=2)], now="2026-05-31T00:00:00Z")
        assert sorted(a["state"] for a in again["advisories"]) == ["active", "resolved"]
        retired = [a for a in again["advisories"] if a["state"] == "resolved"][0]
        # The probe-update linkage is preserved — sync does not overwrite it.
        assert retired["resolved_by"] == "probe-update"

    def test_dismissed_v1_not_superseded_by_v2(self, tmp_path: Path):
        """A dismissed v1 stays dismissed (sticky, A4); v2 is a distinct condition
        that surfaces as a fresh active advisory — the user dismissed the old
        probe's finding, so a materially-refined probe gets a new chance to nag."""
        v1 = reconcile({"schema_version": 1, "advisories": []}, [_candidate(probe_version=1)], now="2026-05-29T00:00:00Z")
        write_store(tmp_path, v1)
        old_id = v1["advisories"][0]["id"]
        dismiss(tmp_path, old_id, now="2026-05-29T01:00:00Z")

        bumped = reconcile(read_store(tmp_path), [_candidate(probe_version=2)], now="2026-05-30T00:00:00Z")
        advs = {a["id"]: a for a in bumped["advisories"]}

        # Dismissed v1 untouched — never superseded, no resolved fields written.
        old = advs[old_id]
        assert old["state"] == "dismissed"
        assert old["superseded_by"] is None
        assert old["resolved_by"] is None

        # v2 is a new, distinct active advisory.
        new = [a for a in bumped["advisories"] if a["id"] != old_id][0]
        assert new["state"] == "active"
        assert new["probe_version"] == 2


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

    def test_sync_compacts_resolved_entry(self, tmp_path: Path):
        """The sync-persist retention pass shrinks an auto-resolved advisory to
        compact form on disk (Chunk 04 / spec §3.4)."""
        (tmp_path / ".prawduct").mkdir()
        (tmp_path / "SYNTHETIC_TRIGGER").write_text("x")
        register_probe("synthetic", "synthetic-condition", 1, self._trigger_probe)
        run_sync_advisories(tmp_path, now="2026-05-29T00:00:00Z", sync_version="v1.6.0")
        # Answer the question → probe stops firing → advisory resolves & compacts.
        (tmp_path / ".prawduct" / "project-state.yaml").write_text("synthetic_resolved: true\n")
        run_sync_advisories(tmp_path, now="2026-06-01T00:00:00Z", sync_version="v1.6.0")
        entry = read_store(tmp_path)["advisories"][0]
        assert entry["state"] == "resolved"
        assert set(entry) == {"id", "state", "resolved_at", "resolved_by"}


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


# ---------------------------------------------------------------------------
# Retention: compaction, TTL GC, soft caps (Chunk 04, spec §3.4 / Q4)
# ---------------------------------------------------------------------------


def _full_resolved(aid, resolved_at, *, resolved_by="sync", superseded_by=None):
    """A resolved advisory carrying the full (pre-compaction) payload."""
    return {
        "id": aid,
        "feature": "synthetic",
        "type": "synthetic-condition",
        "probe_version": 1,
        "triggered_at": "2026-01-01T00:00:00Z",
        "triggered_by_sync_version": "v1.6.0",
        "trigger_summary": "full payload still present",
        "evidence": ["sig-1", "sig-2"],
        "recommended_action": "/prawduct-advisory list",
        "alternative_actions": [],
        "priority": "info",
        "state": "resolved",
        "superseded_by": superseded_by,
        "dismissed_at": None,
        "dismissed_reason": None,
        "resolved_at": resolved_at,
        "resolved_by": resolved_by,
    }


def _full_dismissed(aid, dismissed_at, reason="not relevant"):
    """A dismissed advisory carrying the full (pre-compaction) payload."""
    return {
        "id": aid,
        "feature": "synthetic",
        "type": "synthetic-condition",
        "probe_version": 1,
        "triggered_at": "2026-01-01T00:00:00Z",
        "triggered_by_sync_version": "v1.6.0",
        "trigger_summary": "full payload still present",
        "evidence": ["sig-1"],
        "recommended_action": "/prawduct-advisory list",
        "alternative_actions": [],
        "priority": "info",
        "state": "dismissed",
        "superseded_by": None,
        "dismissed_at": dismissed_at,
        "dismissed_reason": reason,
        "resolved_at": None,
        "resolved_by": None,
    }


def _ordered_ts(i):
    """Unique, lexicographically-increasing ISO stamps for cap tests
    (month 1-12, day 1-28 — both within valid ranges for i up to ~300)."""
    return f"2026-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}T00:00:00Z"


class TestRetention:
    def test_resolved_compacted_to_minimal_form(self):
        store = {"schema_version": 1, "advisories": [_full_resolved("r1", "2026-06-20T00:00:00Z")]}
        entry = apply_retention(store, now="2026-06-30T00:00:00Z")["advisories"][0]
        assert set(entry) == {"id", "state", "resolved_at", "resolved_by"}
        assert entry["resolved_by"] == "sync"
        assert entry["resolved_at"] == "2026-06-20T00:00:00Z"

    def test_resolved_probe_update_keeps_superseded_by(self):
        store = {
            "schema_version": 1,
            "advisories": [_full_resolved("r1", "2026-06-20T00:00:00Z", resolved_by="probe-update", superseded_by="r2")],
        }
        entry = apply_retention(store, now="2026-06-30T00:00:00Z")["advisories"][0]
        assert set(entry) == {"id", "state", "resolved_at", "resolved_by", "superseded_by"}
        assert entry["superseded_by"] == "r2"

    def test_dismissed_compacted_to_minimal_form(self):
        store = {"schema_version": 1, "advisories": [_full_dismissed("d1", "2026-06-20T00:00:00Z", "irrelevant")]}
        entry = apply_retention(store, now="2026-06-30T00:00:00Z")["advisories"][0]
        assert set(entry) == {"id", "state", "dismissed_at", "dismissed_reason"}
        assert entry["dismissed_reason"] == "irrelevant"

    def test_active_payload_untouched(self):
        active = reconcile({"schema_version": 1, "advisories": []}, [_candidate()], now="2026-06-20T00:00:00Z")
        out = apply_retention(active, now="2026-06-30T00:00:00Z")
        # Active entries keep the full payload byte-for-byte.
        assert out["advisories"][0] == active["advisories"][0]

    def test_resolved_ttl_gc_removes_old_keeps_young(self):
        store = {
            "schema_version": 1,
            "advisories": [
                _full_resolved("old", "2026-05-15T00:00:00Z"),    # 46 days → expired
                _full_resolved("young", "2026-06-20T00:00:00Z"),  # 10 days → kept
            ],
        }
        out = apply_retention(store, now="2026-06-30T00:00:00Z")
        assert [a["id"] for a in out["advisories"]] == ["young"]

    def test_resolved_ttl_boundary_kept(self):
        # Exactly 30 days old → not strictly past the TTL → kept.
        store = {"schema_version": 1, "advisories": [_full_resolved("edge", "2026-05-31T00:00:00Z")]}
        out = apply_retention(store, now="2026-06-30T00:00:00Z")
        assert [a["id"] for a in out["advisories"]] == ["edge"]

    def test_resolved_with_unparseable_timestamp_kept(self):
        # A missing/garbled resolved_at must never silently delete an entry.
        store = {"schema_version": 1, "advisories": [_full_resolved("r1", None)]}
        out = apply_retention(store, now="2026-06-30T00:00:00Z")
        assert [a["id"] for a in out["advisories"]] == ["r1"]

    def test_dismissed_kept_forever(self):
        store = {"schema_version": 1, "advisories": [_full_dismissed("d1", "2020-01-01T00:00:00Z")]}
        out = apply_retention(store, now="2026-06-30T00:00:00Z")
        assert [a["id"] for a in out["advisories"]] == ["d1"]

    def test_resolved_soft_cap_keeps_newest(self):
        advs = [_full_resolved(f"r{i:02d}", f"2026-06-29T00:{i:02d}:00Z") for i in range(RESOLVED_CAP + 10)]
        out = apply_retention({"schema_version": 1, "advisories": advs}, now="2026-06-30T00:00:00Z")
        kept = [a["id"] for a in out["advisories"]]
        assert len(kept) == RESOLVED_CAP
        assert "r00" not in kept  # oldest dropped
        assert f"r{RESOLVED_CAP + 9:02d}" in kept  # newest kept

    def test_dismissed_soft_cap_keeps_newest(self):
        advs = [_full_dismissed(f"d{i:03d}", _ordered_ts(i)) for i in range(DISMISSED_CAP + 5)]
        out = apply_retention({"schema_version": 1, "advisories": advs}, now="2026-12-31T00:00:00Z")
        kept = {a["id"] for a in out["advisories"]}
        assert len(kept) == DISMISSED_CAP
        for i in range(5):
            assert f"d{i:03d}" not in kept  # 5 oldest dropped
        assert f"d{DISMISSED_CAP + 4:03d}" in kept

    def test_active_soft_cap_keeps_newest(self):
        advs = [{"id": f"a{i:03d}", "state": "active", "triggered_at": _ordered_ts(i)} for i in range(ACTIVE_CAP + 5)]
        out = apply_retention({"schema_version": 1, "advisories": advs}, now="2026-12-31T00:00:00Z")
        kept = {a["id"] for a in out["advisories"]}
        assert len(kept) == ACTIVE_CAP
        assert "a000" not in kept

    def test_order_preserved_within_bounds(self):
        store = {
            "schema_version": 1,
            "advisories": [
                {"id": "a1", "state": "active", "triggered_at": "2026-06-20T00:00:00Z"},
                _full_resolved("r1", "2026-06-20T00:00:00Z"),
                _full_dismissed("d1", "2026-06-20T00:00:00Z"),
            ],
        }
        out = apply_retention(store, now="2026-06-25T00:00:00Z")
        assert [a["id"] for a in out["advisories"]] == ["a1", "r1", "d1"]

    def test_idempotent(self):
        store = {
            "schema_version": 1,
            "advisories": [
                _full_resolved("r1", "2026-06-20T00:00:00Z", resolved_by="probe-update", superseded_by="r2"),
                _full_dismissed("d1", "2026-06-20T00:00:00Z"),
            ],
        }
        once = apply_retention(store, now="2026-06-25T00:00:00Z")
        twice = apply_retention(once, now="2026-06-25T00:00:00Z")
        assert once == twice

    def test_stays_within_all_caps(self):
        # Resolved stamps stay within the 30-day TTL of `now` so the cap (not the
        # GC) is what bounds them; (day, hour) pairs keep them unique & ordered.
        advs = (
            [{"id": f"a{i:03d}", "state": "active", "triggered_at": _ordered_ts(i)} for i in range(ACTIVE_CAP + 20)]
            + [_full_resolved(f"r{i:03d}", f"2026-12-{(i % 28) + 1:02d}T{i // 28:02d}:00:00Z") for i in range(RESOLVED_CAP + 20)]
            + [_full_dismissed(f"d{i:03d}", _ordered_ts(i)) for i in range(DISMISSED_CAP + 20)]
        )
        out = apply_retention({"schema_version": 1, "advisories": advs}, now="2026-12-31T23:00:00Z")
        by_state: dict[str, int] = {}
        for a in out["advisories"]:
            by_state[a["state"]] = by_state.get(a["state"], 0) + 1
        assert by_state["active"] <= ACTIVE_CAP
        assert by_state["resolved"] <= RESOLVED_CAP
        assert by_state["dismissed"] <= DISMISSED_CAP


# ---------------------------------------------------------------------------
# Schema-version read-tolerance / forward migration (Chunk 04, spec A7)
# ---------------------------------------------------------------------------


class TestSchemaMigration:
    def _write_raw(self, tmp_path: Path, payload: dict):
        (tmp_path / ".prawduct").mkdir(exist_ok=True)
        (tmp_path / ".prawduct" / ".advisories.json").write_text(json.dumps(payload))

    def test_v0_store_migrates_forward(self, tmp_path: Path):
        self._write_raw(tmp_path, {"schema_version": 0, "advisories": [{"id": "x", "state": "active"}]})
        store = read_store(tmp_path)
        assert store["schema_version"] == SCHEMA_VERSION
        assert store["advisories"] == [{"id": "x", "state": "active"}]  # data preserved

    def test_absent_schema_version_migrates(self, tmp_path: Path):
        self._write_raw(tmp_path, {"advisories": []})
        assert read_store(tmp_path)["schema_version"] == SCHEMA_VERSION

    def test_garbage_schema_version_migrates(self, tmp_path: Path):
        self._write_raw(tmp_path, {"schema_version": "not-an-int", "advisories": []})
        assert read_store(tmp_path)["schema_version"] == SCHEMA_VERSION

    def test_higher_schema_version_read_not_crashed(self, tmp_path: Path):
        # A store written by a newer prawduct reads as-is — unknown fields round-trip.
        self._write_raw(tmp_path, {"schema_version": 99, "advisories": [{"id": "y", "state": "active", "future_field": 1}]})
        store = read_store(tmp_path)
        assert store["schema_version"] == 99
        assert store["advisories"][0]["future_field"] == 1

    def test_migrated_version_persists_on_write(self, tmp_path: Path):
        self._write_raw(tmp_path, {"schema_version": 0, "advisories": []})
        write_store(tmp_path, read_store(tmp_path))
        raw = json.loads((tmp_path / ".prawduct" / ".advisories.json").read_text())
        assert raw["schema_version"] == SCHEMA_VERSION
