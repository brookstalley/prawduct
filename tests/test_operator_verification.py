"""Tests for F10 — operator-verification queue."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from lib import operator_verification as ov  # noqa: E402
from lib.migrate_cmd import (  # noqa: E402
    enable_v1_4_operator_verification,
    run_migrate_operator_verification,
)


# =============================================================================
# Parser + round-trip
# =============================================================================


class TestParseOperatorVerification:
    def test_empty_content(self):
        preamble, entries = ov.parse_operator_verification("")
        assert preamble == ""
        assert entries == []

    def test_preamble_only(self):
        preamble, entries = ov.parse_operator_verification(
            "# Header\n\nSome intro prose.\n"
        )
        assert "# Header" in preamble
        assert entries == []

    def test_single_entry(self):
        content = (
            "# Header\n"
            "\n"
            "## VRF-001 — Chunk 14 — sample\n"
            "\n"
            "**Status:** pending\n"
            "**Added:** 2026-05-19\n"
        )
        preamble, entries = ov.parse_operator_verification(content)
        assert "# Header" in preamble
        assert len(entries) == 1
        assert entries[0].vrf_id == "VRF-001"
        assert entries[0].status == "pending"

    def test_multiple_entries_in_order(self):
        content = (
            "## VRF-001 — Chunk 1 — first\n"
            "**Status:** verified\n"
            "\n"
            "## VRF-002 — Chunk 2 — second\n"
            "**Status:** pending\n"
            "\n"
            "## VRF-003 — Chunk 3 — third\n"
            "**Status:** accepted\n"
        )
        _, entries = ov.parse_operator_verification(content)
        assert [e.vrf_id for e in entries] == ["VRF-001", "VRF-002", "VRF-003"]
        assert [e.status for e in entries] == ["verified", "pending", "accepted"]

    def test_unrelated_heading_treated_as_preamble(self):
        # Headings that don't match ``## VRF-`` shouldn't accidentally be
        # parsed as queue entries (e.g. ``## Notes``).
        content = (
            "# Title\n"
            "## Notes\n"
            "Just a notes section, not a VRF entry.\n"
            "## VRF-001 — Chunk N — real entry\n"
            "**Status:** pending\n"
        )
        preamble, entries = ov.parse_operator_verification(content)
        assert "## Notes" in preamble
        assert "Just a notes section" in preamble
        assert len(entries) == 1
        assert entries[0].vrf_id == "VRF-001"

    def test_missing_status_line_defaults_to_pending(self):
        # Missing/malformed status falls back to pending so the gate
        # surfaces the problem rather than silently passing.
        content = (
            "## VRF-001 — sample\n"
            "Body without a Status line at all.\n"
        )
        _, entries = ov.parse_operator_verification(content)
        assert entries[0].status == "pending"

    def test_unknown_status_value_defaults_to_pending(self):
        content = (
            "## VRF-001 — sample\n"
            "**Status:** wibble\n"
        )
        _, entries = ov.parse_operator_verification(content)
        assert entries[0].status == "pending"

    def test_round_trip_preserves_body(self):
        content = (
            "# Header\n"
            "<!-- comment -->\n"
            "\n"
            "## VRF-001 — Chunk 14 — sample\n"
            "\n"
            "**Status:** pending\n"
            "**Added:** 2026-05-19\n"
            "**Where to verify:** somewhere\n"
            "\n"
            "**Verify:**\n"
            "- thing 1\n"
            "- thing 2\n"
        )
        preamble, entries = ov.parse_operator_verification(content)
        out = ov.format_operator_verification(preamble, entries)
        # Round-trip is byte-exact up to trailing newline normalization.
        re_preamble, re_entries = ov.parse_operator_verification(out)
        assert re_preamble == preamble
        assert len(re_entries) == 1
        assert re_entries[0].vrf_id == "VRF-001"
        assert "- thing 1" in "\n".join(re_entries[0].body_lines)
        assert "- thing 2" in "\n".join(re_entries[0].body_lines)


# =============================================================================
# Mutators (mark_verified / mark_accepted)
# =============================================================================


class TestMarkVerified:
    def _entry(self, status: str = "pending") -> ov.VerificationEntry:
        return ov.VerificationEntry(
            vrf_id="VRF-001",
            heading="## VRF-001 — sample",
            body_lines=[f"**Status:** {status}", "**Added:** 2026-05-19"],
        )

    def test_pending_to_verified(self):
        entry = self._entry("pending")
        ov.mark_verified(entry, today=date(2026, 5, 19))
        assert entry.status == "verified"
        joined = "\n".join(entry.body_lines)
        assert "**Verified:** 2026-05-19" in joined

    def test_already_verified_is_noop(self):
        entry = self._entry("verified")
        original_lines = list(entry.body_lines)
        ov.mark_verified(entry, today=date(2026, 5, 19))
        assert entry.body_lines == original_lines  # no Verified line appended

    def test_accepted_refuses_verify(self):
        entry = self._entry("accepted")
        with pytest.raises(ValueError, match="accepted"):
            ov.mark_verified(entry, today=date(2026, 5, 19))


class TestMarkAccepted:
    def _entry(self, status: str = "pending") -> ov.VerificationEntry:
        return ov.VerificationEntry(
            vrf_id="VRF-001",
            heading="## VRF-001 — sample",
            body_lines=[f"**Status:** {status}", "**Added:** 2026-05-19"],
        )

    def test_pending_to_accepted_with_rationale(self):
        entry = self._entry("pending")
        ov.mark_accepted(
            entry, rationale="shipping for demo", today=date(2026, 5, 19)
        )
        assert entry.status == "accepted"
        joined = "\n".join(entry.body_lines)
        assert "**Accepted:** 2026-05-19 — rationale: shipping for demo" in joined

    def test_empty_rationale_rejected(self):
        entry = self._entry("pending")
        with pytest.raises(ValueError, match="rationale"):
            ov.mark_accepted(entry, rationale="", today=date(2026, 5, 19))

    def test_whitespace_only_rationale_rejected(self):
        entry = self._entry("pending")
        with pytest.raises(ValueError, match="rationale"):
            ov.mark_accepted(entry, rationale="   ", today=date(2026, 5, 19))

    def test_already_accepted_is_noop(self):
        entry = self._entry("accepted")
        original_lines = list(entry.body_lines)
        ov.mark_accepted(
            entry, rationale="new reason", today=date(2026, 5, 19)
        )
        assert entry.body_lines == original_lines

    def test_already_verified_is_noop(self):
        # Verified is a drained state — no need to also accept.
        entry = self._entry("verified")
        original_lines = list(entry.body_lines)
        ov.mark_accepted(
            entry, rationale="overriding", today=date(2026, 5, 19)
        )
        assert entry.body_lines == original_lines


# =============================================================================
# Counting helpers
# =============================================================================


class TestPendingHelpers:
    def test_count_pending(self):
        entries = [
            ov.VerificationEntry("VRF-001", "## h", ["**Status:** pending"]),
            ov.VerificationEntry("VRF-002", "## h", ["**Status:** verified"]),
            ov.VerificationEntry("VRF-003", "## h", ["**Status:** pending"]),
            ov.VerificationEntry("VRF-004", "## h", ["**Status:** accepted"]),
        ]
        assert ov.count_pending(entries) == 2
        pending = ov.pending_entries(entries)
        assert [e.vrf_id for e in pending] == ["VRF-001", "VRF-003"]


# =============================================================================
# is_operator_verification_required (column-0 YAML scanner)
# =============================================================================


class TestIsOperatorVerificationRequired:
    def test_missing_file_is_false(self, tmp_path: Path):
        assert (
            ov.is_operator_verification_required(tmp_path / "nope.yaml")
            is False
        )

    def test_missing_key_is_false(self, tmp_path: Path):
        state = tmp_path / "state.yaml"
        state.write_text("other_key: true\n")
        assert ov.is_operator_verification_required(state) is False

    def test_true_value_recognized(self, tmp_path: Path):
        state = tmp_path / "state.yaml"
        state.write_text("operator_verification_required: true\n")
        assert ov.is_operator_verification_required(state) is True

    def test_false_value_recognized(self, tmp_path: Path):
        state = tmp_path / "state.yaml"
        state.write_text("operator_verification_required: false\n")
        assert ov.is_operator_verification_required(state) is False

    def test_indented_occurrence_ignored(self, tmp_path: Path):
        # Nested mention inside a YAML block must not count as the top-level
        # declaration.
        state = tmp_path / "state.yaml"
        state.write_text(
            "nested:\n  operator_verification_required: true\n"
        )
        assert ov.is_operator_verification_required(state) is False

    def test_inline_comment_tolerated(self, tmp_path: Path):
        # Mirrors the Chunk 10 detector/mutator inline-comment lesson.
        state = tmp_path / "state.yaml"
        state.write_text(
            "operator_verification_required: true  # F10 opt-in\n"
        )
        assert ov.is_operator_verification_required(state) is True


# =============================================================================
# run_check_operator_verification
# =============================================================================


def _make_product(tmp_path: Path, *, required: bool, queue_body: str = "") -> Path:
    product = tmp_path / "product"
    prawduct = product / ".prawduct"
    prawduct.mkdir(parents=True)
    state = (
        "operator_verification_required: "
        + ("true" if required else "false")
        + "\n"
    )
    (prawduct / "project-state.yaml").write_text(state)
    if queue_body:
        (prawduct / "operator-verification.md").write_text(queue_body)
    return product


class TestRunCheckOperatorVerification:
    def test_gate_off_returns_satisfied(self, tmp_path: Path):
        product = _make_product(tmp_path, required=False)
        result = ov.run_check_operator_verification(product)
        assert result["required"] is False
        assert result["pending"] == 0
        assert result["first_pending"] is None

    def test_gate_on_no_queue_file(self, tmp_path: Path):
        product = _make_product(tmp_path, required=True)
        result = ov.run_check_operator_verification(product)
        assert result["required"] is True
        assert result["pending"] == 0
        assert "no queue file" in result["message"]

    def test_gate_on_empty_queue(self, tmp_path: Path):
        product = _make_product(
            tmp_path, required=True, queue_body="# Empty queue\n"
        )
        result = ov.run_check_operator_verification(product)
        assert result["pending"] == 0

    def test_gate_on_pending_entry(self, tmp_path: Path):
        product = _make_product(
            tmp_path,
            required=True,
            queue_body=(
                "# Queue\n\n"
                "## VRF-001 — sample\n**Status:** pending\n"
            ),
        )
        result = ov.run_check_operator_verification(product)
        assert result["pending"] == 1
        assert result["first_pending"] == "VRF-001"
        assert "blocking" in result["message"]
        # Plural / singular phrasing — single pending uses singular.
        assert "entry" in result["message"]

    def test_gate_on_multiple_pending_pluralized(self, tmp_path: Path):
        product = _make_product(
            tmp_path,
            required=True,
            queue_body=(
                "## VRF-001 — a\n**Status:** pending\n\n"
                "## VRF-002 — b\n**Status:** pending\n"
            ),
        )
        result = ov.run_check_operator_verification(product)
        assert result["pending"] == 2
        assert "entries" in result["message"]

    def test_drained_entries_dont_block(self, tmp_path: Path):
        product = _make_product(
            tmp_path,
            required=True,
            queue_body=(
                "## VRF-001 — a\n**Status:** verified\n\n"
                "## VRF-002 — b\n**Status:** accepted\n"
            ),
        )
        result = ov.run_check_operator_verification(product)
        assert result["pending"] == 0


# =============================================================================
# run_verify_entry
# =============================================================================


class TestRunVerifyEntry:
    def test_no_prawduct_dir_errors(self, tmp_path: Path):
        result = ov.run_verify_entry(tmp_path / "nope", "VRF-001")
        assert "error" in result
        assert "Not a prawduct product" in result["error"]

    def test_no_queue_file_errors(self, tmp_path: Path):
        product = _make_product(tmp_path, required=True)
        result = ov.run_verify_entry(product, "VRF-001")
        assert "error" in result
        assert "No operator-verification queue" in result["error"]

    def test_unknown_id_errors(self, tmp_path: Path):
        product = _make_product(
            tmp_path,
            required=True,
            queue_body="## VRF-001 — a\n**Status:** pending\n",
        )
        result = ov.run_verify_entry(product, "VRF-999")
        assert "error" in result
        assert "VRF-999" in result["error"]

    def test_pending_to_verified(self, tmp_path: Path):
        product = _make_product(
            tmp_path,
            required=True,
            queue_body="## VRF-001 — a\n**Status:** pending\n",
        )
        result = ov.run_verify_entry(
            product, "VRF-001", today=date(2026, 5, 19)
        )
        assert "error" not in result
        assert result["previous_status"] == "pending"
        assert result["status"] == "verified"
        assert result["actions"]
        # File was written back.
        queue = (product / ".prawduct" / "operator-verification.md").read_text()
        assert "**Status:** verified" in queue
        assert "**Verified:** 2026-05-19" in queue

    def test_already_verified_is_noop(self, tmp_path: Path):
        product = _make_product(
            tmp_path,
            required=True,
            queue_body="## VRF-001 — a\n**Status:** verified\n",
        )
        result = ov.run_verify_entry(product, "VRF-001")
        assert result["previous_status"] == "verified"
        assert result["status"] == "verified"
        assert not result["actions"]
        assert result["notes"]

    def test_accepted_entry_refuses_verify(self, tmp_path: Path):
        product = _make_product(
            tmp_path,
            required=True,
            queue_body="## VRF-001 — a\n**Status:** accepted\n",
        )
        result = ov.run_verify_entry(product, "VRF-001")
        assert "error" in result
        assert "accepted" in result["error"]


# =============================================================================
# run_accept_pending
# =============================================================================


class TestRunAcceptPending:
    def test_empty_rationale_rejected(self, tmp_path: Path):
        product = _make_product(tmp_path, required=True)
        result = ov.run_accept_pending(product, "   ")
        assert "error" in result

    def test_no_pending_returns_clean(self, tmp_path: Path):
        product = _make_product(
            tmp_path,
            required=True,
            queue_body="## VRF-001 — a\n**Status:** verified\n",
        )
        result = ov.run_accept_pending(product, "rationale")
        assert "error" not in result
        assert result["accepted_ids"] == []
        assert result["notes"]

    def test_pending_to_accepted_with_rationale(self, tmp_path: Path):
        product = _make_product(
            tmp_path,
            required=True,
            queue_body=(
                "## VRF-001 — a\n**Status:** pending\n\n"
                "## VRF-002 — b\n**Status:** verified\n\n"
                "## VRF-003 — c\n**Status:** pending\n"
            ),
        )
        result = ov.run_accept_pending(
            product, "shipping for demo", today=date(2026, 5, 19)
        )
        assert result["accepted_ids"] == ["VRF-001", "VRF-003"]
        queue = (product / ".prawduct" / "operator-verification.md").read_text()
        # VRF-002 (verified) untouched, others now accepted with rationale.
        assert queue.count("**Status:** accepted") == 2
        assert queue.count("**Status:** verified") == 1
        assert (
            "**Accepted:** 2026-05-19 — rationale: shipping for demo"
            in queue
        )


# =============================================================================
# enable_v1_4_operator_verification (migrate flow)
# =============================================================================


class TestEnableV1_4OperatorVerification:
    def test_one_shot_short_circuits(self, tmp_path: Path):
        product = tmp_path / "p"
        (product / ".prawduct").mkdir(parents=True)
        (product / ".prawduct" / "project-state.yaml").write_text(
            "operator_verification_required: false\n"
        )
        manifest = {"v1_4_operator_verification_enabled": True}
        actions, notes = enable_v1_4_operator_verification(
            product, manifest, force=False
        )
        assert actions == []
        assert notes == []
        # Flag still set; YAML untouched.
        text = (product / ".prawduct" / "project-state.yaml").read_text()
        assert "operator_verification_required: false" in text

    def test_flips_existing_false_key(self, tmp_path: Path):
        product = tmp_path / "p"
        (product / ".prawduct").mkdir(parents=True)
        (product / ".prawduct" / "project-state.yaml").write_text(
            "operator_verification_required: false\n"
        )
        manifest: dict = {}
        actions, notes = enable_v1_4_operator_verification(product, manifest)
        assert any("Flipped" in a for a in actions)
        assert manifest["v1_4_operator_verification_enabled"] is True
        text = (product / ".prawduct" / "project-state.yaml").read_text()
        assert "operator_verification_required: true" in text

    def test_appends_block_when_key_absent(self, tmp_path: Path):
        product = tmp_path / "p"
        (product / ".prawduct").mkdir(parents=True)
        (product / ".prawduct" / "project-state.yaml").write_text(
            "other_field: 1\n"
        )
        manifest: dict = {}
        actions, notes = enable_v1_4_operator_verification(product, manifest)
        assert any("Added operator_verification_required" in a for a in actions)
        text = (product / ".prawduct" / "project-state.yaml").read_text()
        assert "operator_verification_required: true" in text

    def test_places_queue_template_if_absent(self, tmp_path: Path):
        product = tmp_path / "p"
        (product / ".prawduct").mkdir(parents=True)
        (product / ".prawduct" / "project-state.yaml").write_text(
            "operator_verification_required: false\n"
        )
        manifest: dict = {}
        actions, _ = enable_v1_4_operator_verification(product, manifest)
        assert (product / ".prawduct" / "operator-verification.md").is_file()
        assert any("Placed" in a for a in actions)

    def test_existing_queue_not_overwritten(self, tmp_path: Path):
        product = tmp_path / "p"
        (product / ".prawduct").mkdir(parents=True)
        (product / ".prawduct" / "project-state.yaml").write_text(
            "operator_verification_required: false\n"
        )
        # User-authored content must survive migration.
        existing_queue = (
            "# Queue\n\n## VRF-001 — pre-existing\n**Status:** pending\n"
        )
        (product / ".prawduct" / "operator-verification.md").write_text(
            existing_queue
        )
        manifest: dict = {}
        enable_v1_4_operator_verification(product, manifest)
        queue = (
            product / ".prawduct" / "operator-verification.md"
        ).read_text()
        assert queue == existing_queue

    def test_already_on_no_actions(self, tmp_path: Path):
        product = tmp_path / "p"
        (product / ".prawduct").mkdir(parents=True)
        (product / ".prawduct" / "project-state.yaml").write_text(
            "operator_verification_required: true\n"
        )
        # Queue file already present so we don't trigger the place step.
        (product / ".prawduct" / "operator-verification.md").write_text(
            "# Queue\n"
        )
        manifest: dict = {}
        actions, notes = enable_v1_4_operator_verification(product, manifest)
        assert actions == []
        assert manifest["v1_4_operator_verification_enabled"] is True
        assert any("already true" in n for n in notes)

    def test_inline_comment_tolerated(self, tmp_path: Path):
        # Detector/mutator must agree on inline-comment forms (Chunk 10
        # asymmetry lesson reapplied).
        product = tmp_path / "p"
        (product / ".prawduct").mkdir(parents=True)
        (product / ".prawduct" / "project-state.yaml").write_text(
            "operator_verification_required: false  # opt-in\n"
        )
        manifest: dict = {}
        actions, _ = enable_v1_4_operator_verification(product, manifest)
        assert any("Flipped" in a for a in actions)
        text = (product / ".prawduct" / "project-state.yaml").read_text()
        assert "operator_verification_required: true" in text
        assert "# opt-in" in text  # inline comment preserved


# =============================================================================
# run_migrate_operator_verification (runner)
# =============================================================================


class TestRunMigrateOperatorVerification:
    def test_no_prawduct_dir_errors(self, tmp_path: Path):
        result = run_migrate_operator_verification(str(tmp_path / "nope"))
        assert "error" in result

    def test_missing_manifest_errors(self, tmp_path: Path):
        product = tmp_path / "p"
        (product / ".prawduct").mkdir(parents=True)
        (product / ".prawduct" / "project-state.yaml").write_text("")
        result = run_migrate_operator_verification(str(product))
        assert "error" in result
        assert "sync-manifest.json" in result["error"]

    def test_happy_path_persists_manifest(self, tmp_path: Path):
        product = tmp_path / "p"
        prawduct = product / ".prawduct"
        prawduct.mkdir(parents=True)
        (prawduct / "project-state.yaml").write_text(
            "operator_verification_required: false\n"
        )
        (prawduct / "sync-manifest.json").write_text("{}\n")

        result = run_migrate_operator_verification(str(product))
        assert "error" not in result
        assert result["enabled"] is True
        manifest = json.loads(
            (prawduct / "sync-manifest.json").read_text()
        )
        assert manifest["v1_4_operator_verification_enabled"] is True

    def test_result_shape_stable(self, tmp_path: Path):
        product = tmp_path / "p"
        prawduct = product / ".prawduct"
        prawduct.mkdir(parents=True)
        (prawduct / "project-state.yaml").write_text(
            "operator_verification_required: false\n"
        )
        (prawduct / "sync-manifest.json").write_text("{}\n")

        result = run_migrate_operator_verification(str(product))
        for key in (
            "product_dir",
            "enabled",
            "force",
            "actions",
            "notes",
        ):
            assert key in result


# =============================================================================
# product-hook check-operator-verification / accept-operator-verification
# (subprocess so we exercise the dispatch wiring)
# =============================================================================


class TestProductHookCommands:
    """Subprocess-level coverage of the product-hook dispatch wiring.

    Kept intentionally minimal — three subprocess tests verify the new
    commands are reachable and exit-code semantics are correct. Branch
    coverage of the underlying logic lives in the in-process
    Test* classes above.
    """

    def _hook(self, project_dir: Path, *args: str) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(TOOLS_DIR / "product-hook"), *args]
        return subprocess.run(
            cmd,
            cwd=project_dir,
            capture_output=True,
            text=True,
            env={"CLAUDE_PROJECT_DIR": str(project_dir), "PATH": "/usr/bin:/bin"},
        )

    def test_check_dispatch_returns_0_when_gate_off(self, tmp_path: Path):
        product = _make_product(tmp_path, required=False)
        cp = self._hook(product, "check-operator-verification")
        assert cp.returncode == 0

    def test_check_dispatch_returns_1_with_pending(self, tmp_path: Path):
        product = _make_product(
            tmp_path,
            required=True,
            queue_body="## VRF-001 — a\n**Status:** pending\n",
        )
        cp = self._hook(product, "check-operator-verification")
        assert cp.returncode == 1

    def test_accept_dispatch_requires_rationale_arg(self, tmp_path: Path):
        product = _make_product(
            tmp_path,
            required=True,
            queue_body="## VRF-001 — a\n**Status:** pending\n",
        )
        cp = self._hook(product, "accept-operator-verification")
        assert cp.returncode == 1
        assert "rationale" in cp.stderr.lower()


# =============================================================================
# prawduct-setup CLI (subprocess)
# =============================================================================


class TestPrawductSetupCLI:
    """Subprocess-level coverage of the prawduct-setup CLI dispatch wiring.

    Two subprocess tests verify the new ``--enable-operator-verification``
    migrate flag and the new ``verify`` subcommand are reachable. Branch
    coverage of the underlying logic lives in the in-process Test*
    classes above.
    """

    def _setup(self, *args: str) -> subprocess.CompletedProcess:
        cmd = [
            sys.executable,
            str(TOOLS_DIR / "prawduct-setup.py"),
            *args,
        ]
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_migrate_dispatch_enable_operator_verification(self, tmp_path: Path):
        product = tmp_path / "p"
        prawduct = product / ".prawduct"
        prawduct.mkdir(parents=True)
        (prawduct / "project-state.yaml").write_text(
            "operator_verification_required: false\n"
        )
        (prawduct / "sync-manifest.json").write_text("{}\n")

        cp = self._setup(
            "migrate",
            "--enable-operator-verification",
            str(product),
            "--json",
        )
        assert cp.returncode == 0, cp.stderr
        data = json.loads(cp.stdout)
        assert data["enabled"] is True
        assert "actions" in data
        assert "notes" in data

    def test_verify_dispatch_drains_entry(self, tmp_path: Path):
        product = tmp_path / "p"
        prawduct = product / ".prawduct"
        prawduct.mkdir(parents=True)
        (prawduct / "project-state.yaml").write_text(
            "operator_verification_required: true\n"
        )
        (prawduct / "operator-verification.md").write_text(
            "## VRF-001 — sample\n**Status:** pending\n"
        )

        cp = self._setup(
            "verify",
            str(product),
            "VRF-001",
            "--json",
        )
        assert cp.returncode == 0, cp.stderr
        data = json.loads(cp.stdout)
        assert data["status"] == "verified"
        assert data["previous_status"] == "pending"
