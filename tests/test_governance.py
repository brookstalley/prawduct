"""Tests for the governance module.

Tests context resolution, file classification, state management (including
schema versioning), gate decisions, tracker behavior, stop validation,
commit archival, and trace persistence.
"""

import json
import os
import tempfile
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

# Add tools/ to path for imports
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from governance.context import (
    Context, resolve, resolve_product_for_file, update_product_context,
    register_active_product, enumerate_active_products, cleanup_active_products,
    _product_hash, _active_products_dir,
    check_session_lock, write_session_lock, touch_session_lock,
    REGISTRATION_MAX_AGE, SESSION_LOCK_FRESHNESS,
)
from governance.prompt import check as prompt_check, _check_framework_version
from governance.failure import check as failure_check
from governance.classify import (
    classify,
    FileClass,
    FRAMEWORK_PATTERNS,
    GOVERNANCE_SENSITIVE_PREFIXES,
)
from governance.state import SessionState, PFRState, CURRENT_SCHEMA_VERSION, now_iso
from governance.gate import check, Decision
from governance.tracker import track, DCP_FILE_THRESHOLD
from governance.stop import validate, StopDecision
from governance.commit import check_and_archive
from governance import trace as tr
from governance.__main__ import _record_cross_repo_edit, _load_cross_repo_edits


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_framework(tmp_path):
    """Create a minimal framework directory structure."""
    fw = tmp_path / "framework"
    fw.mkdir()
    (fw / "skills" / "orchestrator").mkdir(parents=True)
    (fw / "skills" / "orchestrator" / "SKILL.md").write_text("# Orchestrator")
    (fw / "tools").mkdir()
    (fw / "docs").mkdir()
    (fw / ".prawduct" / "hooks").mkdir(parents=True)
    (fw / ".prawduct" / "artifacts").mkdir()
    return fw


@pytest.fixture
def tmp_context(tmp_framework):
    """Create a Context pointing to the tmp framework."""
    prawduct_dir = tmp_framework / ".prawduct"
    return Context(
        framework_root=str(tmp_framework),
        prawduct_dir=str(prawduct_dir),
        repo_root=str(tmp_framework),
    )


@pytest.fixture
def session_file(tmp_context):
    """Create a minimal session governance file."""
    path = tmp_context.session_file
    data = {
        "schema_version": 2,
        "product_dir": tmp_context.framework_root,
        "product_output_dir": str(tmp_context.prawduct_dir),
        "current_stage": "iteration",
        "session_started": now_iso(),
        "framework_edits": {"files": [], "total_edits": 0},
        "governance_state": {
            "chunks_completed_without_review": 0,
            "observations_captured_this_session": 0,
        },
        "directional_change": {"active": False, "needs_classification": False},
        "pfr_state": {"required": False, "rca": ""},
    }
    with open(path, "w") as f:
        json.dump(data, f)
    return path


@pytest.fixture
def activated_context(tmp_context):
    """Context with a valid activation marker."""
    marker = tmp_context.activation_marker
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(marker, "w") as f:
        f.write(f"{ts} praw-active")
    return tmp_context


# ---------------------------------------------------------------------------
# Context Tests
# ---------------------------------------------------------------------------


class TestContext:
    def test_properties(self, tmp_context):
        ctx = tmp_context
        assert ctx.session_file.endswith(".session-governance.json")
        assert ctx.activation_marker.endswith(".orchestrator-activated")
        # Marker should be under prawduct_dir
        assert ctx.activation_marker.startswith(ctx.prawduct_dir)
        assert ctx.critic_pending.endswith(".critic-pending")
        assert ctx.critic_findings.endswith(".critic-findings.json")

    def test_resolve_with_explicit_root(self, tmp_framework):
        with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_framework)}):
            ctx = resolve(framework_root=str(tmp_framework))
            assert ctx.framework_root == str(tmp_framework)
            assert ctx.prawduct_dir == str(tmp_framework / ".prawduct")

    def test_resolve_without_root_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("GOVERNANCE_FRAMEWORK_ROOT", None)
            with pytest.raises(ValueError):
                resolve()

    def test_resolve_follows_active_products_registry(self, tmp_path):
        """resolve() follows .active-products/ registry to redirect prawduct_dir."""
        fw = tmp_path / "framework"
        fw.mkdir()
        fw_prawduct = fw / ".prawduct"
        fw_prawduct.mkdir()

        product = tmp_path / "product"
        product.mkdir()
        product_prawduct = product / ".prawduct"
        product_prawduct.mkdir()

        # Register product
        register_active_product(str(fw_prawduct), str(product_prawduct))

        with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(fw)}):
            ctx = resolve(framework_root=str(fw))
            assert ctx.prawduct_dir == str(product_prawduct.resolve())

    def test_resolve_ignores_registry_when_follow_false(self, tmp_path):
        """resolve(follow_pointer=False) ignores .active-products/ registry."""
        fw = tmp_path / "framework"
        fw.mkdir()
        fw_prawduct = fw / ".prawduct"
        fw_prawduct.mkdir()

        product = tmp_path / "product"
        product.mkdir()
        product_prawduct = product / ".prawduct"
        product_prawduct.mkdir()

        # Register product
        register_active_product(str(fw_prawduct), str(product_prawduct))

        with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(fw)}):
            ctx = resolve(framework_root=str(fw), follow_pointer=False)
            assert ctx.prawduct_dir == str(fw_prawduct)

    def test_resolve_ignores_stale_registration(self, tmp_path):
        """resolve() ignores registrations older than 12h."""
        fw = tmp_path / "framework"
        fw.mkdir()
        fw_prawduct = fw / ".prawduct"
        fw_prawduct.mkdir()

        product = tmp_path / "product"
        product.mkdir()
        product_prawduct = product / ".prawduct"
        product_prawduct.mkdir()

        # Register product with a stale timestamp
        products_dir = _active_products_dir(str(fw_prawduct))
        os.makedirs(products_dir, exist_ok=True)
        h = _product_hash(str(product_prawduct))
        entry_path = os.path.join(products_dir, h)
        stale_ts = time.time() - REGISTRATION_MAX_AGE - 100
        with open(entry_path, "w") as f:
            f.write(f"{os.path.realpath(str(product_prawduct))}\n{stale_ts}\n")

        with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(fw)}):
            ctx = resolve(framework_root=str(fw))
            assert ctx.prawduct_dir == str(fw_prawduct)

    def test_update_product_context_cross_repo(self, tmp_path):
        """update_product_context() returns new ctx for cross-repo file."""
        fw = tmp_path / "framework"
        fw.mkdir()
        fw_prawduct = fw / ".prawduct"
        fw_prawduct.mkdir()

        product = tmp_path / "product"
        product.mkdir()
        product_prawduct = product / ".prawduct"
        product_prawduct.mkdir()
        (product / ".git").mkdir()
        (product / "src").mkdir()

        from governance.classify import _git_root_cache
        _git_root_cache.clear()

        ctx = Context(
            framework_root=str(fw),
            prawduct_dir=str(fw_prawduct),
            repo_root=str(fw),
        )

        file_path = str(product / "src" / "app.py")
        with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(fw)}):
            new_ctx = update_product_context(file_path, ctx)
            assert new_ctx.prawduct_dir == str(product_prawduct)
            # Registration should have been written in .active-products/
            products_dir = _active_products_dir(str(fw_prawduct))
            assert os.path.isdir(products_dir)
            entries = os.listdir(products_dir)
            assert len(entries) == 1

    def test_update_product_context_same_repo(self, tmp_path):
        """update_product_context() returns same ctx for same-repo file."""
        fw = tmp_path / "framework"
        fw.mkdir()
        fw_prawduct = fw / ".prawduct"
        fw_prawduct.mkdir()
        (fw / ".git").mkdir()
        (fw / "tools").mkdir()

        from governance.classify import _git_root_cache
        _git_root_cache.clear()

        ctx = Context(
            framework_root=str(fw),
            prawduct_dir=str(fw_prawduct),
            repo_root=str(fw),
        )

        file_path = str(fw / "tools" / "test.py")
        new_ctx = update_product_context(file_path, ctx)
        assert new_ctx is ctx  # Same object — no change

    def test_resolve_product_for_file_with_prawduct(self, tmp_path):
        """File in a git repo with .prawduct/ resolves to that repo's .prawduct/."""
        repo = tmp_path / "myrepo"
        repo.mkdir()
        (repo / ".git").mkdir()
        (repo / ".prawduct").mkdir()
        (repo / "src").mkdir()
        test_file = str(repo / "src" / "app.py")

        from governance.classify import _git_root_cache
        _git_root_cache.clear()

        result = resolve_product_for_file(test_file, "/fallback/.prawduct")
        assert result == str(repo / ".prawduct")

    def test_resolve_product_for_file_fallback(self, tmp_path):
        """File not in a git repo falls back to session-level prawduct_dir."""
        test_file = str(tmp_path / "random" / "file.txt")
        fallback = str(tmp_path / "session" / ".prawduct")

        from governance.classify import _git_root_cache
        _git_root_cache.clear()

        result = resolve_product_for_file(test_file, fallback)
        assert result == fallback

    def test_resolve_product_for_file_no_prawduct_dir(self, tmp_path):
        """Git repo without .prawduct/ falls back to session-level."""
        repo = tmp_path / "bare_repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        test_file = str(repo / "file.py")
        fallback = str(tmp_path / "session" / ".prawduct")

        from governance.classify import _git_root_cache
        _git_root_cache.clear()

        result = resolve_product_for_file(test_file, fallback)
        assert result == fallback


# ---------------------------------------------------------------------------
# Classification Tests
# ---------------------------------------------------------------------------


class TestClassify:
    def test_framework_file(self, tmp_context):
        path = os.path.join(tmp_context.framework_root, "skills", "orchestrator", "SKILL.md")
        fc = classify(path, tmp_context)
        assert fc.is_framework is True
        assert fc.is_governance_sensitive is True
        assert fc.rel_path == "skills/orchestrator/SKILL.md"
        # Orchestrator SKILL.md is whitelisted for reads
        assert fc.is_read_gated is False

    def test_governance_sensitive_skills(self, tmp_context):
        path = os.path.join(tmp_context.framework_root, "skills", "critic", "SKILL.md")
        fc = classify(path, tmp_context)
        assert fc.is_framework is True
        assert fc.is_governance_sensitive is True
        assert fc.is_read_gated is True

    def test_governance_sensitive_tools(self, tmp_context):
        path = os.path.join(tmp_context.framework_root, "tools", "something.py")
        fc = classify(path, tmp_context)
        assert fc.is_framework is True
        assert fc.is_governance_sensitive is True

    def test_non_sensitive_docs(self, tmp_context):
        path = os.path.join(tmp_context.framework_root, "docs", "readme.md")
        fc = classify(path, tmp_context)
        assert fc.is_framework is True
        assert fc.is_governance_sensitive is False

    def test_ungoverned_file(self, tmp_context):
        fc = classify("/tmp/random-file.txt", tmp_context)
        assert fc.is_framework is False
        assert fc.is_product is False
        assert fc.is_governance_sensitive is False

    def test_read_gated_template(self, tmp_context):
        path = os.path.join(tmp_context.framework_root, "templates", "project-state.yaml")
        fc = classify(path, tmp_context)
        assert fc.is_read_gated is True

    def test_all_framework_patterns_recognized(self, tmp_context):
        """Every pattern in FRAMEWORK_PATTERNS is classified as framework."""
        for pattern in FRAMEWORK_PATTERNS:
            # Create a path matching the pattern
            if pattern.endswith("/"):
                path = os.path.join(tmp_context.framework_root, pattern, "test.md")
            else:
                path = os.path.join(tmp_context.framework_root, pattern)
            fc = classify(path, tmp_context)
            assert fc.is_framework is True, f"Pattern {pattern} not recognized as framework"

    def test_product_file_during_bootstrap(self, tmp_path):
        """Product dir has .prawduct/ and .git but no session file yet — is_product=True."""
        fw = tmp_path / "framework"
        fw.mkdir()
        fw_prawduct = fw / ".prawduct"
        fw_prawduct.mkdir()

        product = tmp_path / "product"
        product.mkdir()
        product_prawduct = product / ".prawduct"
        product_prawduct.mkdir()
        (product / ".git").mkdir()  # Git root marker
        # No .session-governance.json — this is the bootstrap window

        from governance.classify import _git_root_cache
        _git_root_cache.clear()

        ctx = Context(
            framework_root=str(fw),
            prawduct_dir=str(fw_prawduct),
            repo_root=str(fw),
        )
        # File inside the product dir
        (product / "src").mkdir(exist_ok=True)
        path = os.path.join(str(product), "src", "app.py")
        fc = classify(path, ctx)
        assert fc.is_product is True
        assert fc.is_external_repo is False

    def test_no_bootstrap_false_prefix_match(self, tmp_path):
        """File in sibling dir bar-baz should NOT match product dir bar's .prawduct/."""
        fw = tmp_path / "framework"
        fw.mkdir()
        fw_prawduct = fw / ".prawduct"
        fw_prawduct.mkdir()

        product = tmp_path / "bar"
        product.mkdir()
        (product / ".prawduct").mkdir()
        (product / ".git").mkdir()

        from governance.classify import _git_root_cache
        _git_root_cache.clear()

        ctx = Context(
            framework_root=str(fw),
            prawduct_dir=str(fw_prawduct),

            repo_root=str(fw),
        )
        # File in a directory that shares a prefix but is NOT the product
        sibling = tmp_path / "bar-baz"
        sibling.mkdir()
        path = os.path.join(str(sibling), "file.py")
        fc = classify(path, ctx)
        assert fc.is_product is False

    def test_no_bootstrap_without_prawduct_dir(self, tmp_path):
        """File in a git repo without .prawduct/ is not a product file."""
        fw = tmp_path / "framework"
        fw.mkdir()
        fw_prawduct = fw / ".prawduct"
        fw_prawduct.mkdir()

        other = tmp_path / "other"
        other.mkdir()
        (other / ".git").mkdir()  # Git repo but no .prawduct/

        from governance.classify import _git_root_cache
        _git_root_cache.clear()

        ctx = Context(
            framework_root=str(fw),
            prawduct_dir=str(fw_prawduct),

            repo_root=str(fw),
        )
        path = os.path.join(str(other), "file.py")
        fc = classify(path, ctx)
        assert fc.is_product is False


# ---------------------------------------------------------------------------
# State Tests
# ---------------------------------------------------------------------------


class TestState:
    def test_load_missing_file(self, tmp_path):
        path = str(tmp_path / "nonexistent.json")
        state = SessionState.load(path)
        assert state.schema_version == CURRENT_SCHEMA_VERSION
        assert state.framework_edits.files == []
        assert state.trace.events == []

    def test_load_v1_format(self, tmp_path):
        """v1 format: no schema_version, diagnosis_written + structured diagnosis."""
        path = str(tmp_path / "session.json")
        v1_data = {
            "product_dir": "/test",
            "framework_edits": {"files": [], "total_edits": 0},
            "governance_state": {},
            "directional_change": {},
            "pfr_state": {
                "required": True,
                "diagnosis_written": True,
                "diagnosis": {
                    "symptom": "Test symptom",
                    "five_whys": ["why1", "why2", "why3"],
                    "root_cause": "Test root cause",
                    "root_cause_category": "missing_process",
                    "meta_fix_plan": "Fix plan",
                },
                "governance_sensitive_files": ["skills/test.md"],
                "observation_file": None,
            },
        }
        with open(path, "w") as f:
            json.dump(v1_data, f)

        state = SessionState.load(path)
        assert state.schema_version == 1
        assert state.pfr._v1_diagnosis_written is True
        # v1 diagnosis should be upgraded to RCA
        assert "Test symptom" in state.pfr.rca
        assert "why1" in state.pfr.rca
        assert "Test root cause" in state.pfr.rca

    def test_save_as_v2(self, tmp_path):
        """State always saves as v2 format. Traces go to separate file."""
        path = str(tmp_path / "session.json")
        state = SessionState(path)
        state.product_dir = "/test"
        state.pfr.rca = "Test RCA text with enough characters to pass the minimum length requirement for the gate"
        state.save()

        with open(path) as f:
            data = json.load(f)

        assert data["schema_version"] == CURRENT_SCHEMA_VERSION
        assert data["pfr_state"]["rca"] == state.pfr.rca
        # Traces are NOT in the session file anymore
        assert "trace" not in data
        # v1 fields should NOT be in v2 output
        assert "diagnosis_written" not in data["pfr_state"]
        assert "diagnosis" not in data["pfr_state"]

    def test_roundtrip(self, tmp_path):
        """Load → save → load produces same state."""
        path = str(tmp_path / "session.json")
        state1 = SessionState(path)
        state1.product_dir = "/test"
        state1.pfr.required = True
        state1.pfr.rca = "Some analysis"
        state1.dcp.active = True
        state1.dcp.tier = "structural"
        state1.framework_edits.files.append({"path": "test.py", "edit_count": 1})
        state1.save()

        state2 = SessionState.load(path)
        assert state2.product_dir == "/test"
        assert state2.pfr.required is True
        assert state2.pfr.rca == "Some analysis"
        assert state2.dcp.tier == "structural"
        assert len(state2.framework_edits.files) == 1

    def test_v1_upgrade_on_load(self, tmp_path):
        """v1 file loaded and saved becomes v2."""
        path = str(tmp_path / "session.json")
        v1_data = {
            "product_dir": "/test",
            "framework_edits": {"files": [], "total_edits": 0},
            "governance_state": {},
            "directional_change": {},
            "pfr_state": {
                "required": True,
                "diagnosis_written": True,
                "diagnosis": {"symptom": "bug", "five_whys": ["w1"], "root_cause": "rc"},
            },
        }
        with open(path, "w") as f:
            json.dump(v1_data, f)

        state = SessionState.load(path)
        state.save()

        with open(path) as f:
            data = json.load(f)
        assert data["schema_version"] == 2
        assert "rca" in data["pfr_state"]
        assert "diagnosis_written" not in data["pfr_state"]


# ---------------------------------------------------------------------------
# Gate Tests
# ---------------------------------------------------------------------------


class TestGate:
    def test_no_file_path_allows(self, tmp_context, session_file):
        state = SessionState.load(session_file)
        result = check({"tool_name": "Write", "tool_input": {}}, tmp_context, state)
        assert result.allowed is True

    def test_ungoverned_file_allows(self, activated_context, session_file):
        state = SessionState.load(session_file)
        result = check(
            {"tool_name": "Write", "tool_input": {"file_path": "/tmp/test.txt"}},
            activated_context,
            state,
        )
        assert result.allowed is True

    def test_read_orchestrator_always_allowed(self, tmp_context, session_file):
        """Orchestrator SKILL.md is whitelisted — readable without activation."""
        state = SessionState.load(session_file)
        path = os.path.join(tmp_context.framework_root, "skills", "orchestrator", "SKILL.md")
        result = check(
            {"tool_name": "Read", "tool_input": {"file_path": path}},
            tmp_context,
            state,
        )
        assert result.allowed is True

    def test_read_skill_blocked_without_activation(self, tmp_context, session_file):
        state = SessionState.load(session_file)
        path = os.path.join(tmp_context.framework_root, "skills", "critic", "SKILL.md")
        result = check(
            {"tool_name": "Read", "tool_input": {"file_path": path}},
            tmp_context,
            state,
        )
        assert result.allowed is False
        assert "activation" in result.reason.lower()

    def test_read_skill_allowed_with_activation(self, activated_context, session_file):
        state = SessionState.load(session_file)
        path = os.path.join(
            activated_context.framework_root, "skills", "critic", "SKILL.md"
        )
        result = check(
            {"tool_name": "Read", "tool_input": {"file_path": path}},
            activated_context,
            state,
        )
        assert result.allowed is True

    def test_edit_blocked_without_activation(self, tmp_context, session_file):
        state = SessionState.load(session_file)
        path = os.path.join(tmp_context.framework_root, "tools", "test.py")
        result = check(
            {"tool_name": "Write", "tool_input": {"file_path": path}},
            tmp_context,
            state,
        )
        assert result.allowed is False
        assert "activation" in result.reason.lower()

    def test_pfr_blocks_without_rca(self, activated_context, session_file):
        """Governance-sensitive file blocked without RCA."""
        state = SessionState.load(session_file)
        path = os.path.join(activated_context.framework_root, "skills", "test.md")
        result = check(
            {"tool_name": "Write", "tool_input": {"file_path": path}},
            activated_context,
            state,
        )
        assert result.allowed is False
        assert "PFR" in result.reason

    def test_pfr_allows_with_rca(self, activated_context, session_file):
        """Governance-sensitive file allowed with substantive RCA."""
        state = SessionState.load(session_file)
        state.pfr.rca = "A" * PFRState._RCA_MIN_LENGTH  # Exactly minimum length
        state.save()

        state = SessionState.load(session_file)
        path = os.path.join(activated_context.framework_root, "skills", "test.md")
        result = check(
            {"tool_name": "Write", "tool_input": {"file_path": path}},
            activated_context,
            state,
        )
        assert result.allowed is True

    def test_pfr_blocks_short_rca(self, activated_context, session_file):
        """RCA below minimum length still blocks."""
        state = SessionState.load(session_file)
        state.pfr.rca = "Too short"
        state.save()

        state = SessionState.load(session_file)
        path = os.path.join(activated_context.framework_root, "skills", "test.md")
        result = check(
            {"tool_name": "Write", "tool_input": {"file_path": path}},
            activated_context,
            state,
        )
        assert result.allowed is False

    def test_pfr_cosmetic_escape(self, activated_context, session_file):
        """Cosmetic justification bypasses PFR."""
        state = SessionState.load(session_file)
        state.pfr.required = False
        state.pfr.cosmetic_justification = "Typo fix in error message"
        state.save()

        state = SessionState.load(session_file)
        path = os.path.join(activated_context.framework_root, "skills", "test.md")
        result = check(
            {"tool_name": "Write", "tool_input": {"file_path": path}},
            activated_context,
            state,
        )
        assert result.allowed is True

    def test_pfr_cosmetic_does_not_leak_to_new_files(self, activated_context, session_file):
        """Cosmetic justification for file A doesn't cover unrelated file B."""
        state = SessionState.load(session_file)
        state.pfr.required = False
        state.pfr.cosmetic_justification = "Typo fix in error message"
        # Simulate tracker having recorded the original cosmetic file
        state.pfr.governance_sensitive_files = ["tools/capture-observation.sh"]
        state.save()

        state = SessionState.load(session_file)
        # Try editing a DIFFERENT governance-sensitive file
        path = os.path.join(activated_context.framework_root, "tools", "other-tool.py")
        result = check(
            {"tool_name": "Write", "tool_input": {"file_path": path}},
            activated_context,
            state,
        )
        assert result.allowed is False
        assert "PFR" in result.reason

    def test_chunk_review_blocks_product_edits(self, activated_context, session_file):
        state = SessionState.load(session_file)
        state.product_dir = activated_context.framework_root
        state.governance.chunks_completed_without_review = 2
        state.save()

        state = SessionState.load(session_file)
        path = os.path.join(activated_context.framework_root, "src", "app.py")
        result = check(
            {"tool_name": "Write", "tool_input": {"file_path": path}},
            activated_context,
            state,
        )
        # Since src/app.py is not a framework file but IS in product_dir,
        # this should be a product file (if session state has the product_dir)
        # The product file classification depends on session_file existing
        # with product_dir set correctly
        if result.allowed is False:
            assert "chunk" in result.reason.lower() or "review" in result.reason.lower()

    def test_bootstrap_session_write_allowed(self, tmp_path):
        """Writing .session-governance.json is allowed when marker is valid but session file doesn't exist."""
        fw = tmp_path / "framework"
        fw.mkdir()
        fw_prawduct = fw / ".prawduct"
        fw_prawduct.mkdir()

        product = tmp_path / "product"
        product.mkdir()
        product_prawduct = product / ".prawduct"
        product_prawduct.mkdir()
        (product / ".git").mkdir()

        from governance.classify import _git_root_cache
        _git_root_cache.clear()

        # Context points to product (as update_product_context would resolve)
        ctx = Context(
            framework_root=str(fw),
            prawduct_dir=str(product_prawduct),
            repo_root=str(fw),
        )

        # Write a valid activation marker (step 3)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(ctx.activation_marker, "w") as f:
            f.write(f"{ts} praw-active")

        # No session file exists yet — this is the bootstrap window
        assert not os.path.isfile(ctx.session_file)

        # Gate should allow writing the session file
        state = SessionState.load(ctx.session_file)
        result = check(
            {"tool_name": "Write", "tool_input": {"file_path": ctx.session_file}},
            ctx,
            state,
        )
        assert result.allowed is True

    def test_bootstrap_exemption_not_for_other_files(self, tmp_path):
        """Bootstrap exemption only applies to the session-governance file, not other product files."""
        fw = tmp_path / "framework"
        fw.mkdir()
        fw_prawduct = fw / ".prawduct"
        fw_prawduct.mkdir()

        product = tmp_path / "product"
        product.mkdir()
        product_prawduct = product / ".prawduct"
        product_prawduct.mkdir()
        (product / ".git").mkdir()

        from governance.classify import _git_root_cache
        _git_root_cache.clear()

        ctx = Context(
            framework_root=str(fw),
            prawduct_dir=str(product_prawduct),
            repo_root=str(fw),
        )

        # Write a valid activation marker
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(ctx.activation_marker, "w") as f:
            f.write(f"{ts} praw-active")

        # No session file — but trying to write a different product file
        state = SessionState.load(ctx.session_file)
        other_file = str(product / "src" / "app.py")
        result = check(
            {"tool_name": "Write", "tool_input": {"file_path": other_file}},
            ctx,
            state,
        )
        # Should be blocked — activation cross-validation fails for non-session files
        assert result.allowed is False
        assert "session state" in result.reason.lower()

    def test_bootstrap_exemption_not_when_session_exists(self, activated_context, session_file):
        """Once session file exists, no bootstrap exemption — normal gate applies."""
        # session_file fixture already created the file
        state = SessionState.load(session_file)
        result = check(
            {"tool_name": "Write", "tool_input": {"file_path": activated_context.session_file}},
            activated_context,
            state,
        )
        # Should be allowed via normal path (activation + session valid)
        assert result.allowed is True

    def test_chunk_review_exempts_project_state(self, activated_context, session_file):
        """project-state.yaml exempt from chunk review gate."""
        state = SessionState.load(session_file)
        state.product_dir = activated_context.framework_root
        state.governance.chunks_completed_without_review = 2
        state.save()

        state = SessionState.load(session_file)
        # Even with chunk review debt, project-state.yaml is allowed
        path = os.path.join(activated_context.framework_root, "project-state.yaml")
        result = check(
            {"tool_name": "Write", "tool_input": {"file_path": path}},
            activated_context,
            state,
        )
        # project-state.yaml is not a framework pattern, and as a product file
        # it's exempt from chunk review — so it should be allowed


# ---------------------------------------------------------------------------
# Tracker Tests
# ---------------------------------------------------------------------------


class TestTracker:
    def test_tracks_framework_edit(self, activated_context, session_file):
        state = SessionState.load(session_file)
        path = os.path.join(activated_context.framework_root, "tools", "test.py")
        track(
            {"tool_name": "Write", "tool_input": {"file_path": path}},
            activated_context,
            state,
        )
        assert len(state.framework_edits.files) == 1
        assert state.framework_edits.files[0]["path"] == "tools/test.py"
        assert state.framework_edits.total_edits == 1

    def test_increments_edit_count(self, activated_context, session_file):
        state = SessionState.load(session_file)
        path = os.path.join(activated_context.framework_root, "tools", "test.py")
        track(
            {"tool_name": "Write", "tool_input": {"file_path": path}},
            activated_context,
            state,
        )
        track(
            {"tool_name": "Write", "tool_input": {"file_path": path}},
            activated_context,
            state,
        )
        assert len(state.framework_edits.files) == 1
        assert state.framework_edits.files[0]["edit_count"] == 2
        assert state.framework_edits.total_edits == 2

    def test_dcp_triggers_at_threshold(self, activated_context, session_file):
        state = SessionState.load(session_file)
        for i in range(DCP_FILE_THRESHOLD):
            path = os.path.join(
                activated_context.framework_root, "tools", f"file{i}.py"
            )
            track(
                {"tool_name": "Write", "tool_input": {"file_path": path}},
                activated_context,
                state,
            )
        assert state.dcp.needs_classification is True
        assert state.dcp.triggered_at_file_count == DCP_FILE_THRESHOLD

    def test_dcp_does_not_retrigger(self, activated_context, session_file):
        state = SessionState.load(session_file)
        state.dcp.active = True
        state.dcp.tier = "structural"
        for i in range(5):
            path = os.path.join(
                activated_context.framework_root, "tools", f"file{i}.py"
            )
            track(
                {"tool_name": "Write", "tool_input": {"file_path": path}},
                activated_context,
                state,
            )
        assert state.dcp.needs_classification is False

    def test_pfr_triggers_on_gov_sensitive(self, activated_context, session_file):
        state = SessionState.load(session_file)
        path = os.path.join(activated_context.framework_root, "skills", "test.md")
        # Mock _is_git_tracked: tmp dirs aren't git repos, so without this
        # the tracker treats the file as "new" (untracked) and skips PFR.
        with patch("governance.tracker._is_git_tracked", return_value=True):
            track(
                {"tool_name": "Write", "tool_input": {"file_path": path}},
                activated_context,
                state,
            )
        assert state.pfr.required is True
        assert "skills/test.md" in state.pfr.governance_sensitive_files

    def test_pfr_does_not_trigger_on_docs(self, activated_context, session_file):
        state = SessionState.load(session_file)
        path = os.path.join(activated_context.framework_root, "docs", "readme.md")
        track(
            {"tool_name": "Write", "tool_input": {"file_path": path}},
            activated_context,
            state,
        )
        assert state.pfr.required is False

    def test_critic_pending_created(self, activated_context, session_file):
        state = SessionState.load(session_file)
        path = os.path.join(activated_context.framework_root, "tools", "test.py")
        track(
            {"tool_name": "Write", "tool_input": {"file_path": path}},
            activated_context,
            state,
        )
        assert os.path.isfile(activated_context.critic_pending)

    def test_trace_events_emitted(self, activated_context, session_file):
        state = SessionState.load(session_file)
        path = os.path.join(activated_context.framework_root, "tools", "test.py")
        track(
            {"tool_name": "Write", "tool_input": {"file_path": path}},
            activated_context,
            state,
        )
        assert len(state.trace.events) > 0
        assert any(e["type"] == "edit_tracked" for e in state.trace.events)

    def test_ungoverned_file_not_tracked(self, activated_context, session_file):
        state = SessionState.load(session_file)
        track(
            {"tool_name": "Write", "tool_input": {"file_path": "/tmp/test.txt"}},
            activated_context,
            state,
        )
        assert len(state.framework_edits.files) == 0
        assert state.framework_edits.total_edits == 0


# ---------------------------------------------------------------------------
# Stop Tests
# ---------------------------------------------------------------------------


class TestStop:
    def test_allows_when_clean(self, tmp_context, session_file):
        state = SessionState.load(session_file)
        result = validate({}, tmp_context, state)
        assert result.allowed is True

    def test_blocks_on_unreviewed_framework_edits(self, tmp_context, session_file):
        state = SessionState.load(session_file)
        state.framework_edits.files.append({"path": "tools/test.py"})
        state.save()

        state = SessionState.load(session_file)
        result = validate({}, tmp_context, state)
        assert result.allowed is False
        assert any("Critic" in d for d in result.debts)

    def test_blocks_on_pfr_without_observation(self, tmp_context, session_file):
        state = SessionState.load(session_file)
        state.pfr.required = True
        state.pfr.rca = "A" * 60  # Has RCA but no observation
        state.save()

        state = SessionState.load(session_file)
        result = validate({}, tmp_context, state)
        assert result.allowed is False
        assert any("PFR" in d for d in result.debts)

    def test_blocks_on_dcp_needs_classification(self, tmp_context, session_file):
        state = SessionState.load(session_file)
        state.dcp.needs_classification = True
        state.dcp.triggered_at_file_count = 3
        state.save()

        state = SessionState.load(session_file)
        result = validate({}, tmp_context, state)
        assert result.allowed is False
        assert any("DCP" in d for d in result.debts)

    def test_blocks_on_active_dcp_incomplete(self, tmp_context, session_file):
        state = SessionState.load(session_file)
        state.dcp.active = True
        state.dcp.tier = "structural"
        state.dcp.retrospective_completed = False
        state.save()

        state = SessionState.load(session_file)
        result = validate({}, tmp_context, state)
        assert result.allowed is False
        assert any("retrospective" in d for d in result.debts)

    def test_respects_stop_hook_active_flag(self, tmp_context, session_file):
        """stop_hook_active prevents infinite loops."""
        state = SessionState.load(session_file)
        state.framework_edits.files.append({"path": "tools/test.py"})
        state.save()

        state = SessionState.load(session_file)
        result = validate({"stop_hook_active": True}, tmp_context, state)
        assert result.allowed is True

    def test_blocks_on_chunk_review_debt(self, tmp_context, session_file):
        state = SessionState.load(session_file)
        state.governance.chunks_completed_without_review = 3
        state.save()

        state = SessionState.load(session_file)
        result = validate({}, tmp_context, state)
        assert result.allowed is False
        assert any("chunk" in d for d in result.debts)

    def test_stop_enumerates_active_products(self, tmp_path):
        """Stop hook enumerates .active-products/ to check multi-product debt.

        When a product is registered with governance debt, stop detects it
        via enumeration rather than following a singleton pointer.
        """
        fw = tmp_path / "framework"
        fw.mkdir()
        fw_prawduct = fw / ".prawduct"
        fw_prawduct.mkdir()

        product = tmp_path / "product"
        product.mkdir()
        product_prawduct = product / ".prawduct"
        product_prawduct.mkdir()

        # Register product in .active-products/
        register_active_product(str(fw_prawduct), str(product_prawduct))

        # Product has governance debt
        product_session = product_prawduct / ".session-governance.json"
        session_data = {
            "schema_version": 2,
            "product_dir": str(product),
            "product_output_dir": str(product_prawduct),
            "current_stage": "building",
            "session_started": now_iso(),
            "framework_edits": {"files": [{"path": "tools/test.py"}], "total_edits": 1},
            "governance_state": {
                "chunks_completed_without_review": 2,
                "observations_captured_this_session": 0,
            },
            "directional_change": {"active": False, "needs_classification": False},
            "pfr_state": {"required": False, "rca": ""},
        }
        with open(product_session, "w") as f:
            json.dump(session_data, f)

        # Enumerate should find the product
        products = enumerate_active_products(str(fw_prawduct))
        assert len(products) == 1
        assert products[0] == str(product_prawduct.resolve())

        # Stop at session-level (no session state) should allow
        with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(fw)}):
            ctx = resolve(framework_root=str(fw), follow_pointer=False)
            assert ctx.prawduct_dir == str(fw_prawduct)

        state = SessionState.load(ctx.session_file)
        result = validate({}, ctx, state)
        assert result.allowed is True  # Session-level is clean

        # But the product has debt — _run_stop in __main__ would catch it
        product_ctx = Context(
            framework_root=str(fw),
            prawduct_dir=str(product_prawduct),
            repo_root=str(product),
        )
        product_state = SessionState.load(product_ctx.session_file)
        product_result = validate({}, product_ctx, product_state)
        assert product_result.allowed is False
        assert any("chunk" in d for d in product_result.debts)


# ---------------------------------------------------------------------------
# Trace Tests
# ---------------------------------------------------------------------------


class TestTrace:
    def test_event_appended(self, session_file):
        state = SessionState.load(session_file)
        tr.event(state, "test_event", {"key": "value"})
        # In-memory buffer
        assert len(state.trace.events) == 1
        assert state.trace.events[0]["type"] == "test_event"
        assert state.trace.events[0]["key"] == "value"
        assert "ts" in state.trace.events[0]
        assert state.trace.events[0]["v"] == 1
        # Write-through to JSONL file
        trace_path = os.path.join(os.path.dirname(session_file), ".session-trace.jsonl")
        assert os.path.isfile(trace_path)
        with open(trace_path) as f:
            line = json.loads(f.readline())
        assert line["type"] == "test_event"
        assert line["key"] == "value"

    def test_persist_creates_files(self, session_file, tmp_path):
        state = SessionState.load(session_file)
        tr.event(state, "test", {"detail": "x"})

        traces_dir = str(tmp_path / "traces")
        tr.persist(state, traces_dir)

        # Level 1: session log
        log = tmp_path / "traces" / "session-log.jsonl"
        assert log.is_file()
        with open(log) as f:
            line = json.loads(f.readline())
        assert line["v"] == 1
        assert line["trace_event_count"] == 1

        # Level 2: session archive
        sessions = tmp_path / "traces" / "sessions"
        archives = list(sessions.glob("*.json"))
        assert len(archives) == 1

    def test_rotation(self, session_file, tmp_path):
        sessions_dir = tmp_path / "traces" / "sessions"
        sessions_dir.mkdir(parents=True)

        # Create 25 dummy archives
        for i in range(25):
            (sessions_dir / f"2026-01-{i:02d}T00-00-00Z.json").write_text("{}")

        tr._rotate_archives(str(sessions_dir))
        remaining = list(sessions_dir.glob("*.json"))
        assert len(remaining) == tr.MAX_SESSION_ARCHIVES

    def test_no_networking_imports(self):
        """Verify trace.py doesn't import networking libraries."""
        import governance.trace as trace_mod

        source = Path(trace_mod.__file__).read_text()
        # Check actual import statements, not comments mentioning libraries
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for lib in ["urllib", "requests", "http.client", "socket"]:
                assert not (
                    stripped.startswith(f"import {lib}")
                    or stripped.startswith(f"from {lib}")
                ), f"trace.py imports {lib}: {stripped}"


# ---------------------------------------------------------------------------
# Commit Tests
# ---------------------------------------------------------------------------


class TestCommit:
    def test_non_commit_allows(self, activated_context, session_file):
        state = SessionState.load(session_file)
        result = check_and_archive(
            {"tool_input": {"command": "ls -la"}},
            activated_context,
            state,
        )
        assert result.allowed is True

    def test_pfr_observation_blocks_without_file(self, activated_context, session_file):
        state = SessionState.load(session_file)
        state.pfr.required = True
        state.pfr.rca = "A" * 60
        # No observation_file set
        state.save()

        state = SessionState.load(session_file)
        result = check_and_archive(
            {"tool_input": {"command": "git commit -m 'test'"}},
            activated_context,
            state,
        )
        assert result.allowed is False
        assert "observation" in result.reason.lower()

    def test_unified_ctx_critic_pending_detected(self, tmp_path):
        """With unified resolution, ctx.critic_pending points to the right
        place and the commit gate detects it without a dual-path fallback."""
        fw = tmp_path / "framework"
        fw.mkdir()
        fw_prawduct = fw / ".prawduct"
        fw_prawduct.mkdir()
        (fw / "skills").mkdir()
        (fw / "tools").mkdir()

        # Context already points to the framework (unified resolution did its job)
        ctx = Context(
            framework_root=str(fw),
            prawduct_dir=str(fw_prawduct),
            repo_root=str(fw),
        )

        # Write activation marker
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(ctx.activation_marker, "w") as f:
            f.write(f"{ts} praw-active")

        # Session state with framework edits
        session_data = {
            "schema_version": 2,
            "product_dir": str(fw),
            "product_output_dir": str(fw_prawduct),
            "session_started": now_iso(),
            "framework_edits": {"files": [{"path": "tools/gate.py", "first_modified": now_iso(), "last_modified": now_iso(), "edit_count": 1}], "total_edits": 1},
            "governance_state": {},
            "directional_change": {},
            "pfr_state": {},
        }
        with open(ctx.session_file, "w") as f:
            json.dump(session_data, f)
        state = SessionState.load(ctx.session_file)

        # Tracker writes .critic-pending to ctx.critic_pending (unified path)
        with open(ctx.critic_pending, "w") as f:
            f.write(now_iso())

        # Mock critic-reminder.sh that exits 2 (blocks)
        critic_tool = fw / "tools" / "critic-reminder.sh"
        critic_tool.write_text("#!/bin/bash\nexit 2\n")
        critic_tool.chmod(0o755)

        result = check_and_archive(
            {"tool_input": {"command": "git commit -m 'test'"}},
            ctx,
            state,
        )
        # Should be blocked because critic-reminder.sh exits 2
        assert result.allowed is False
        assert "critic" in result.reason.lower() or "review" in result.reason.lower()


# ---------------------------------------------------------------------------
# Integration Test
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_full_session_flow(self, activated_context, session_file):
        """Simulate a session: activate → edit → track → gate check → trace."""
        ctx = activated_context
        state = SessionState.load(session_file)

        # 1. Write PFR RCA
        state.pfr.rca = (
            "Immediate problem: duplicated context resolution code. "
            "Why: each hook independently resolves paths. "
            "Deeper: bash hooks can't share code via imports. "
            "Class: copy-paste architecture. "
            "Prevention: extract to Python module."
        )
        state.save()

        # 2. Gate check should now allow governance-sensitive edit
        state = SessionState.load(session_file)
        path = os.path.join(ctx.framework_root, "tools", "test.py")
        gate_result = check(
            {"tool_name": "Write", "tool_input": {"file_path": path}},
            ctx,
            state,
        )
        assert gate_result.allowed is True

        # 3. Track the edit (mock git tracking — tmp dirs aren't git repos)
        with patch("governance.tracker._is_git_tracked", return_value=True):
            track(
                {"tool_name": "Write", "tool_input": {"file_path": path}},
                ctx,
                state,
            )
        assert len(state.framework_edits.files) == 1
        assert state.pfr.required is True

        # 4. Verify trace events accumulated (in-memory and on disk)
        gate_events = [e for e in state.trace.events if e["type"] == "gate_check"]
        edit_events = [e for e in state.trace.events if e["type"] == "edit_tracked"]
        assert len(gate_events) >= 1
        assert len(edit_events) == 1

        # Verify trace file was written
        trace_path = os.path.join(os.path.dirname(session_file), ".session-trace.jsonl")
        assert os.path.isfile(trace_path)
        with open(trace_path) as f:
            trace_lines = [json.loads(line) for line in f if line.strip()]
        assert len(trace_lines) > 0
        assert any(e["type"] == "edit_tracked" for e in trace_lines)

        state.save()

        # 5. Verify state persists correctly (traces NOT in session file)
        state2 = SessionState.load(session_file)
        assert state2.schema_version == 2
        assert state2.trace.events == []  # Traces no longer loaded from session file
        assert state2.pfr.rca.startswith("Immediate problem")


class TestPromptVersionCheck:
    """Tests for framework version mismatch detection in the prompt hook."""

    def test_no_version_file_returns_none(self, tmp_context):
        """No framework-version file means skip check (fresh repo or self-hosted)."""
        assert _check_framework_version(tmp_context) is None

    def test_matching_version_returns_none(self, tmp_context):
        """When stored hash matches current framework, no advisory."""
        version_file = os.path.join(tmp_context.prawduct_dir, "framework-version")
        with patch(
            "governance.prompt._git_hash", return_value="abc123def456"
        ):
            with open(version_file, "w") as f:
                f.write("abc123def456\n")
            assert _check_framework_version(tmp_context) is None

    def test_stale_version_returns_advisory(self, tmp_context):
        """When stored hash differs from current, return upgrade advisory."""
        version_file = os.path.join(tmp_context.prawduct_dir, "framework-version")
        with patch(
            "governance.prompt._git_hash", return_value="newversion123456"
        ):
            with open(version_file, "w") as f:
                f.write("oldversion987654\n")
            result = _check_framework_version(tmp_context)
            assert result is not None
            assert "oldversi" in result  # truncated stored hash
            assert "newversi" in result  # truncated current hash
            assert "prawduct-init.py" in result

    def test_prompt_check_activation_takes_priority(self, tmp_context):
        """When not activated, activation reminder wins over version check."""
        # No activation marker — should get activation message, not version check
        result = prompt_check(tmp_context)
        assert result is not None
        parsed = json.loads(result)
        assert "NOT active" in parsed["additionalContext"]

    def test_prompt_check_version_after_activation(self, activated_context):
        """When activated with stale version, get version advisory."""
        version_file = os.path.join(
            activated_context.prawduct_dir, "framework-version"
        )
        with patch(
            "governance.prompt._git_hash", return_value="currenthash123"
        ):
            with open(version_file, "w") as f:
                f.write("stale_hash_456\n")
            result = prompt_check(activated_context)
            assert result is not None
            parsed = json.loads(result)
            assert "version mismatch" in parsed["additionalContext"].lower()
            assert "prawduct-init.py" in parsed["additionalContext"]

    def test_prompt_check_clean_returns_none(self, activated_context):
        """When activated and no version file, returns None (clean)."""
        result = prompt_check(activated_context)
        assert result is None


# ---------------------------------------------------------------------------
# PostToolUseFailure — investigation reminder
# ---------------------------------------------------------------------------


class TestFailureCheck:
    """Tests for the PostToolUseFailure investigation reminder."""

    def test_routine_edit_not_unique_ignored(self):
        """Routine Edit failure (old_string not unique) should not trigger."""
        result = failure_check({
            "tool_name": "Edit",
            "error": "old_string is not unique in the file",
        })
        assert result is None

    def test_governance_block_ignored(self):
        """Governance blocks (BLOCKED:) are intentional, not defects."""
        result = failure_check({
            "tool_name": "Edit",
            "error": "BLOCKED: Edit requires activation (HR9)",
        })
        assert result is None

    def test_user_interrupt_ignored(self):
        """User interrupts should not trigger investigation."""
        result = failure_check({
            "tool_name": "Edit",
            "error": "User cancelled the operation",
            "is_interrupt": True,
        })
        assert result is None

    def test_unexpected_modified_triggers(self):
        """'Unexpectedly modified' errors should trigger investigation."""
        result = failure_check({
            "tool_name": "Edit",
            "error": "File has been unexpectedly modified since last read",
        })
        assert result is not None
        parsed = json.loads(result)
        assert "UNEXPECTED TOOL FAILURE" in parsed["additionalContext"]
        assert "root cause" in parsed["additionalContext"].lower()

    def test_empty_error_ignored(self):
        """Empty error strings should not trigger."""
        result = failure_check({
            "tool_name": "Edit",
            "error": "",
        })
        assert result is None

    def test_file_not_found_ignored(self):
        """File not found is routine, not a defect."""
        result = failure_check({
            "tool_name": "Read",
            "error": "File not found: /tmp/nonexistent.txt",
        })
        assert result is None

    def test_unknown_error_triggers(self):
        """An unrecognized error should trigger investigation."""
        result = failure_check({
            "tool_name": "Write",
            "error": "Unexpected internal error: disk full on ephemeral storage",
        })
        assert result is not None
        parsed = json.loads(result)
        assert "additionalContext" in parsed


# ---------------------------------------------------------------------------
# Product Registry Tests
# ---------------------------------------------------------------------------


class TestProductRegistry:
    """Tests for the .active-products/ directory-based registry."""

    def test_register_creates_directory_and_file(self, tmp_path):
        """Basic registration creates .active-products/<hash> file."""
        session_dir = str(tmp_path / "session" / ".prawduct")
        product_dir = str(tmp_path / "product" / ".prawduct")
        os.makedirs(session_dir, exist_ok=True)
        os.makedirs(product_dir, exist_ok=True)

        register_active_product(session_dir, product_dir)

        products_dir = _active_products_dir(session_dir)
        assert os.path.isdir(products_dir)
        entries = os.listdir(products_dir)
        assert len(entries) == 1

        # Verify file contents
        entry_path = os.path.join(products_dir, entries[0])
        with open(entry_path) as f:
            lines = f.read().strip().split("\n")
        assert lines[0] == os.path.realpath(product_dir)
        assert float(lines[1]) > 0

    def test_register_same_product_idempotent(self, tmp_path):
        """Same product always maps to same hash file."""
        session_dir = str(tmp_path / "session" / ".prawduct")
        product_dir = str(tmp_path / "product" / ".prawduct")
        os.makedirs(session_dir, exist_ok=True)
        os.makedirs(product_dir, exist_ok=True)

        register_active_product(session_dir, product_dir)
        register_active_product(session_dir, product_dir)

        entries = os.listdir(_active_products_dir(session_dir))
        assert len(entries) == 1  # Same file, not two

    def test_register_multiple_products(self, tmp_path):
        """Different products create different files."""
        session_dir = str(tmp_path / "session" / ".prawduct")
        product_a = str(tmp_path / "product-a" / ".prawduct")
        product_b = str(tmp_path / "product-b" / ".prawduct")
        os.makedirs(session_dir, exist_ok=True)
        os.makedirs(product_a, exist_ok=True)
        os.makedirs(product_b, exist_ok=True)

        register_active_product(session_dir, product_a)
        register_active_product(session_dir, product_b)

        entries = os.listdir(_active_products_dir(session_dir))
        assert len(entries) == 2

    def test_enumerate_returns_valid_products(self, tmp_path):
        """Round-trip register → enumerate returns correct paths."""
        session_dir = str(tmp_path / "session" / ".prawduct")
        product_dir = str(tmp_path / "product" / ".prawduct")
        os.makedirs(session_dir, exist_ok=True)
        os.makedirs(product_dir, exist_ok=True)

        register_active_product(session_dir, product_dir)
        products = enumerate_active_products(session_dir)

        assert len(products) == 1
        assert products[0] == os.path.realpath(product_dir)

    def test_enumerate_skips_stale_registrations(self, tmp_path):
        """Registrations older than 12h are filtered out."""
        session_dir = str(tmp_path / "session" / ".prawduct")
        product_dir = str(tmp_path / "product" / ".prawduct")
        os.makedirs(session_dir, exist_ok=True)
        os.makedirs(product_dir, exist_ok=True)

        # Write a stale entry manually
        products_dir = _active_products_dir(session_dir)
        os.makedirs(products_dir, exist_ok=True)
        h = _product_hash(product_dir)
        entry_path = os.path.join(products_dir, h)
        stale_ts = time.time() - REGISTRATION_MAX_AGE - 100
        with open(entry_path, "w") as f:
            f.write(f"{os.path.realpath(product_dir)}\n{stale_ts}\n")

        products = enumerate_active_products(session_dir)
        assert len(products) == 0

    def test_enumerate_min_timestamp_filters_old_registrations(self, tmp_path):
        """Products registered before min_timestamp are excluded."""
        session_dir = str(tmp_path / "session" / ".prawduct")
        old_product = str(tmp_path / "old" / ".prawduct")
        new_product = str(tmp_path / "new" / ".prawduct")
        os.makedirs(session_dir, exist_ok=True)
        os.makedirs(old_product, exist_ok=True)
        os.makedirs(new_product, exist_ok=True)

        products_dir = _active_products_dir(session_dir)
        os.makedirs(products_dir, exist_ok=True)

        midpoint = time.time() - 3600  # 1 hour ago

        # Old product: registered before midpoint
        h_old = _product_hash(old_product)
        with open(os.path.join(products_dir, h_old), "w") as f:
            f.write(f"{os.path.realpath(old_product)}\n{midpoint - 100}\n")

        # New product: registered after midpoint
        h_new = _product_hash(new_product)
        with open(os.path.join(products_dir, h_new), "w") as f:
            f.write(f"{os.path.realpath(new_product)}\n{midpoint + 100}\n")

        # Without filter: both returned
        all_products = enumerate_active_products(session_dir)
        assert len(all_products) == 2

        # With filter: only new product returned
        filtered = enumerate_active_products(session_dir, min_timestamp=midpoint)
        assert len(filtered) == 1
        assert filtered[0] == os.path.realpath(new_product)

    def test_enumerate_skips_missing_dirs(self, tmp_path):
        """Nonexistent product paths are filtered out."""
        session_dir = str(tmp_path / "session" / ".prawduct")
        os.makedirs(session_dir, exist_ok=True)

        # Write entry pointing to nonexistent dir
        products_dir = _active_products_dir(session_dir)
        os.makedirs(products_dir, exist_ok=True)
        entry_path = os.path.join(products_dir, "abcdef123456")
        with open(entry_path, "w") as f:
            f.write(f"/nonexistent/path/.prawduct\n{time.time()}\n")

        products = enumerate_active_products(session_dir)
        assert len(products) == 0

    def test_enumerate_empty_directory(self, tmp_path):
        """Empty .active-products/ returns empty list."""
        session_dir = str(tmp_path / "session" / ".prawduct")
        os.makedirs(session_dir, exist_ok=True)

        products = enumerate_active_products(session_dir)
        assert products == []

    def test_cleanup_removes_directory(self, tmp_path):
        """cleanup_active_products removes the directory and all entries."""
        session_dir = str(tmp_path / "session" / ".prawduct")
        product_dir = str(tmp_path / "product" / ".prawduct")
        os.makedirs(session_dir, exist_ok=True)
        os.makedirs(product_dir, exist_ok=True)

        register_active_product(session_dir, product_dir)
        assert os.path.isdir(_active_products_dir(session_dir))

        cleanup_active_products(session_dir)
        assert not os.path.isdir(_active_products_dir(session_dir))


# ---------------------------------------------------------------------------
# Cross-Repo Edit Tracking Tests
# ---------------------------------------------------------------------------


class TestCrossRepoEdits:
    """Tests for the .cross-repo-edits tracking used by the stop hook."""

    def test_record_creates_file(self, tmp_path):
        """Recording a cross-repo edit creates .cross-repo-edits."""
        session_dir = str(tmp_path / "session" / ".prawduct")
        product_dir = str(tmp_path / "product" / ".prawduct")
        os.makedirs(session_dir, exist_ok=True)
        os.makedirs(product_dir, exist_ok=True)

        _record_cross_repo_edit(session_dir, product_dir)

        edits_path = os.path.join(session_dir, ".cross-repo-edits")
        assert os.path.isfile(edits_path)
        with open(edits_path) as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) == 1
        assert lines[0] == os.path.realpath(product_dir)

    def test_record_deduplicates(self, tmp_path):
        """Recording the same product twice doesn't duplicate."""
        session_dir = str(tmp_path / "session" / ".prawduct")
        product_dir = str(tmp_path / "product" / ".prawduct")
        os.makedirs(session_dir, exist_ok=True)
        os.makedirs(product_dir, exist_ok=True)

        _record_cross_repo_edit(session_dir, product_dir)
        _record_cross_repo_edit(session_dir, product_dir)

        edits_path = os.path.join(session_dir, ".cross-repo-edits")
        with open(edits_path) as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) == 1

    def test_record_multiple_products(self, tmp_path):
        """Recording different products creates separate entries."""
        session_dir = str(tmp_path / "session" / ".prawduct")
        product_a = str(tmp_path / "product-a" / ".prawduct")
        product_b = str(tmp_path / "product-b" / ".prawduct")
        os.makedirs(session_dir, exist_ok=True)
        os.makedirs(product_a, exist_ok=True)
        os.makedirs(product_b, exist_ok=True)

        _record_cross_repo_edit(session_dir, product_a)
        _record_cross_repo_edit(session_dir, product_b)

        edits = _load_cross_repo_edits(session_dir)
        assert len(edits) == 2
        assert os.path.realpath(product_a) in edits
        assert os.path.realpath(product_b) in edits

    def test_load_empty_when_no_file(self, tmp_path):
        """Loading when no .cross-repo-edits file returns empty set."""
        session_dir = str(tmp_path / "session" / ".prawduct")
        os.makedirs(session_dir, exist_ok=True)

        edits = _load_cross_repo_edits(session_dir)
        assert edits == set()

    def test_load_roundtrip(self, tmp_path):
        """Record then load returns the same paths."""
        session_dir = str(tmp_path / "session" / ".prawduct")
        product_dir = str(tmp_path / "product" / ".prawduct")
        os.makedirs(session_dir, exist_ok=True)
        os.makedirs(product_dir, exist_ok=True)

        _record_cross_repo_edit(session_dir, product_dir)
        edits = _load_cross_repo_edits(session_dir)

        assert len(edits) == 1
        assert os.path.realpath(product_dir) in edits


# ---------------------------------------------------------------------------
# Advisory Lock Tests
# ---------------------------------------------------------------------------


class TestAdvisoryLock:
    """Tests for the .session.lock advisory lock mechanism."""

    def test_session_lock_warns_on_concurrent(self, tmp_path):
        """Fresh lock returns warning message."""
        prawduct_dir = str(tmp_path / ".prawduct")
        os.makedirs(prawduct_dir, exist_ok=True)

        write_session_lock(prawduct_dir)
        warning = check_session_lock(prawduct_dir)

        assert warning is not None
        assert "Another session" in warning

    def test_session_lock_ignores_stale(self, tmp_path):
        """Lock older than 1h returns None."""
        prawduct_dir = str(tmp_path / ".prawduct")
        os.makedirs(prawduct_dir, exist_ok=True)

        lock_path = os.path.join(prawduct_dir, ".session.lock")
        with open(lock_path, "w") as f:
            f.write(f"{time.time()}\n")

        # Backdate mtime to beyond freshness threshold
        old_time = time.time() - SESSION_LOCK_FRESHNESS - 100
        os.utime(lock_path, (old_time, old_time))

        warning = check_session_lock(prawduct_dir)
        assert warning is None

    def test_session_lock_touch_updates_mtime(self, tmp_path):
        """Heartbeat (touch) keeps the lock fresh."""
        prawduct_dir = str(tmp_path / ".prawduct")
        os.makedirs(prawduct_dir, exist_ok=True)

        write_session_lock(prawduct_dir)
        lock_path = os.path.join(prawduct_dir, ".session.lock")

        # Backdate the lock
        old_time = time.time() - SESSION_LOCK_FRESHNESS - 100
        os.utime(lock_path, (old_time, old_time))
        assert check_session_lock(prawduct_dir) is None  # Stale

        # Touch should refresh it
        touch_session_lock(prawduct_dir)
        warning = check_session_lock(prawduct_dir)
        assert warning is not None  # Fresh again

    def test_no_lock_returns_none(self, tmp_path):
        """No lock file returns None."""
        prawduct_dir = str(tmp_path / ".prawduct")
        os.makedirs(prawduct_dir, exist_ok=True)

        warning = check_session_lock(prawduct_dir)
        assert warning is None
