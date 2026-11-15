"""An opt-in gate flag that cannot be READ must refuse, not read as "off" (#777).

``coverage_required`` and ``operator_verification_required`` are opt-in: an absent
file or an absent key means the gate is off, and that stays true. What is NOT the
same thing is a ``project-state.yaml`` that EXISTS and cannot be read (permission
denied, a directory in its place, bytes that are not UTF-8). The readers used to
fold that into ``False``, so an operator who had turned a gate on lost it the
moment the file became unreadable, with exit 0 and no output.

The queue (``operator-verification.md``) had the sibling defect one frame lower:
``_load_queue`` had no ``try``, so an unreadable queue crossed the CLI as a Python
traceback, which ``api-contract.md`` § Error Model forbids.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

_PLUGIN = Path(__file__).resolve().parent.parent / "plugin"
if str(_PLUGIN) not in sys.path:
    sys.path.insert(0, str(_PLUGIN))

from lib import core  # noqa: E402
from lib import operator_verification as ov  # noqa: E402

HOOK_PATH = _PLUGIN / "bin" / "prawduct-hook"

_hook_loader = importlib.machinery.SourceFileLoader("prawduct_hook_flags_closed", str(HOOK_PATH))
_hook_spec = importlib.util.spec_from_loader("prawduct_hook_flags_closed", _hook_loader)
_hook = importlib.util.module_from_spec(_hook_spec)
_hook_loader.exec_module(_hook)

_RUNNING_AS_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0

_PENDING_QUEUE = "# Operator Verification Queue\n\n## VRF-001 — Chunk 1 — look\n\n**Status:** pending\n"


def _deny(path: Path) -> None:
    """Make ``path`` unreadable, skipping where chmod cannot (root reads anything)."""
    if _RUNNING_AS_ROOT:
        pytest.skip("root reads a chmod 000 file; the unreadable case cannot be built")
    path.chmod(0o000)


def _restore(path: Path) -> None:
    if path.exists():
        path.chmod(0o644)


@pytest.fixture
def unreadable_kinds(tmp_path: Path):
    """The three ways an existing state file can fail to be read, as paths."""
    denied = tmp_path / "denied.yaml"
    denied.write_text("coverage_required: true\noperator_verification_required: true\n")
    garbled = tmp_path / "garbled.yaml"
    garbled.write_bytes(b"coverage_required: true\n\xff\xfe\x80 not utf-8\n")
    directory = tmp_path / "dir.yaml"
    directory.mkdir()
    kinds = {"garbled": garbled, "directory": directory}
    if not _RUNNING_AS_ROOT:
        _deny(denied)
        kinds["denied"] = denied
    yield kinds
    _restore(denied)


# --- core.read_bool_flag: the one owner --------------------------------------


class TestReadBoolFlag:
    def test_unreadable_is_reported_not_folded_into_off(self, unreadable_kinds):
        for kind, path in unreadable_kinds.items():
            result = core.read_bool_flag(path, "coverage_required")
            assert result["status"] == core.FLAG_UNREADABLE, kind
            assert result["value"] is False, kind
            assert "coverage_required" in result["reason"], kind
            assert path.name in result["reason"], kind

    def test_absent_file_and_absent_key_still_read_as_off(self, tmp_path: Path):
        gone = core.read_bool_flag(tmp_path / "nope.yaml", "coverage_required")
        assert gone == {"status": core.FLAG_OK, "value": False, "reason": None}
        nokey = tmp_path / "s.yaml"
        nokey.write_text("other: true\n")
        assert core.read_bool_flag(nokey, "coverage_required")["status"] == core.FLAG_OK
        assert core.read_bool_flag(nokey, "coverage_required")["value"] is False

    def test_a_parent_that_is_a_file_is_absent_not_unreadable(self, tmp_path: Path):
        """``NotADirectoryError`` means there is no such file, which is "absent"."""
        parent = tmp_path / "f"
        parent.write_text("x")
        result = core.read_bool_flag(parent / "project-state.yaml", "coverage_required")
        assert result["status"] == core.FLAG_OK and result["value"] is False

    def test_positive_control_a_readable_true_is_true(self, tmp_path: Path):
        p = tmp_path / "s.yaml"
        p.write_text("coverage_required: true  # on\n")
        assert core.read_bool_flag(p, "coverage_required") == {
            "status": core.FLAG_OK,
            "value": True,
            "reason": None,
        }


class TestReadBoolYamlKeyRaisesWhenUnreadable:
    """``read_bool_yaml_key`` has a bool contract, so it cannot report; it raises."""

    def test_raises_a_specific_error(self, unreadable_kinds):
        for kind, path in unreadable_kinds.items():
            with pytest.raises(core.StateFileUnreadable) as exc:
                core.read_bool_yaml_key(path, "coverage_required")
            assert path.name in str(exc.value), kind

    def test_absent_still_false(self, tmp_path: Path):
        assert core.read_bool_yaml_key(tmp_path / "nope.yaml", "coverage_required") is False

    def test_the_error_is_not_an_oserror(self):
        """A caller's ``except OSError`` is exactly the swallow this class removes."""
        assert not issubclass(core.StateFileUnreadable, (OSError, ValueError))


# --- the hook's inline mirror ------------------------------------------------


class TestHookMirrorAgreesOnUnreadable:
    def test_mirror_raises_where_core_raises(self, unreadable_kinds):
        for kind, path in unreadable_kinds.items():
            with pytest.raises(Exception) as hook_exc:
                _hook._read_bool_yaml_key(path, "coverage_required")
            with pytest.raises(core.StateFileUnreadable):
                core.read_bool_yaml_key(path, "coverage_required")
            assert type(hook_exc.value).__name__ == core.StateFileUnreadable.__name__, kind

    def test_mirror_still_reads_absent_as_false(self, tmp_path: Path):
        assert _hook._read_bool_yaml_key(tmp_path / "nope.yaml", "coverage_required") is False


# --- operator verification: the flag read ------------------------------------


def _product(tmp_path: Path, state_text: str | bytes, queue: str | bytes | None = None) -> Path:
    prawduct = tmp_path / "product" / ".prawduct"
    prawduct.mkdir(parents=True)
    state = prawduct / "project-state.yaml"
    if isinstance(state_text, bytes):
        state.write_bytes(state_text)
    else:
        state.write_text(state_text)
    if queue is not None:
        q = prawduct / "operator-verification.md"
        if isinstance(queue, bytes):
            q.write_bytes(queue)
        else:
            q.write_text(queue)
    return prawduct.parent


def _run_hook(product: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(  # noqa: S603
        [sys.executable, str(HOOK_PATH), *args],
        capture_output=True,
        text=True,
        env={"CLAUDE_PROJECT_DIR": str(product), "PATH": "/usr/bin:/bin"},
    )


class TestOperatorVerificationStateFileUnreadable:
    def test_flag_reader_raises_on_unreadable(self, tmp_path: Path):
        product = _product(tmp_path, b"operator_verification_required: true\n\xff\xfe\n")
        state = product / ".prawduct" / "project-state.yaml"
        with pytest.raises(core.StateFileUnreadable):
            ov.is_operator_verification_required(state)

    def test_check_refuses_with_the_third_outcome_shape(self, tmp_path: Path):
        product = _product(tmp_path, b"operator_verification_required: true\n\xff\xfe\n", _PENDING_QUEUE)
        result = ov.run_check_operator_verification(product)
        assert result["queue_status"] == ov.QUEUE_STATE_UNREADABLE
        assert result["required"] is None  # unknown: the flag could not be read
        assert result["message"].startswith("blocking: ")
        assert "project-state.yaml" in result["message"]

    def test_every_branch_carries_the_same_keys(self, tmp_path: Path):
        ok = ov.run_check_operator_verification(
            _product(tmp_path / "a", "operator_verification_required: false\n")
        )
        bad = ov.run_check_operator_verification(
            _product(tmp_path / "b", b"operator_verification_required: true\n\xff\n")
        )
        assert set(ok) == set(bad)

    def test_cli_exits_3_and_says_why_on_a_garbled_state_file(self, tmp_path: Path):
        product = _product(tmp_path, b"operator_verification_required: true\n\xff\xfe\n")
        proc = _run_hook(product, "check-operator-verification")
        assert proc.returncode == 3, (proc.returncode, proc.stdout, proc.stderr)
        assert "project-state.yaml" in proc.stderr
        assert "Traceback" not in proc.stderr

    def test_cli_exits_3_on_a_permission_denied_state_file(self, tmp_path: Path):
        """The issue's repro: ``chmod 000`` with the flag on exited 0 silently."""
        product = _product(tmp_path, "operator_verification_required: true\n")
        state = product / ".prawduct" / "project-state.yaml"
        _deny(state)
        try:
            proc = _run_hook(product, "check-operator-verification")
        finally:
            _restore(state)
        assert proc.returncode == 3, (proc.returncode, proc.stdout, proc.stderr)
        assert "project-state.yaml" in proc.stderr

    def test_cli_still_exits_0_when_the_state_file_is_absent(self, tmp_path: Path):
        product = tmp_path / "product"
        (product / ".prawduct").mkdir(parents=True)
        proc = _run_hook(product, "check-operator-verification")
        assert proc.returncode == 0, proc.stderr

    def test_cli_still_exits_0_when_the_flag_is_off(self, tmp_path: Path):
        proc = _run_hook(
            _product(tmp_path, "operator_verification_required: false\n"),
            "check-operator-verification",
        )
        assert proc.returncode == 0, proc.stderr


# --- operator verification: the queue read -----------------------------------

_GARBLED_QUEUE = b"## VRF-001 \xff\xfe\x80 not utf-8\n"


class TestOperatorVerificationQueueUnreadable:
    def test_check_returns_the_unreadable_shape_not_a_traceback(self, tmp_path: Path):
        product = _product(tmp_path, "operator_verification_required: true\n", _GARBLED_QUEUE)
        result = ov.run_check_operator_verification(product)
        assert result["queue_status"] == ov.QUEUE_UNREADABLE
        assert result["message"].startswith("blocking: ")
        assert "operator-verification.md" in result["message"]

    def test_cli_check_exits_3_on_a_garbled_queue(self, tmp_path: Path):
        product = _product(tmp_path, "operator_verification_required: true\n", _GARBLED_QUEUE)
        proc = _run_hook(product, "check-operator-verification")
        assert proc.returncode == 3, (proc.returncode, proc.stderr)
        assert "Traceback" not in proc.stderr
        assert "operator-verification.md" in proc.stderr

    def test_cli_check_exits_3_on_a_permission_denied_queue(self, tmp_path: Path):
        product = _product(tmp_path, "operator_verification_required: true\n", _PENDING_QUEUE)
        queue = product / ".prawduct" / "operator-verification.md"
        _deny(queue)
        try:
            proc = _run_hook(product, "check-operator-verification")
        finally:
            _restore(queue)
        assert proc.returncode == 3, (proc.returncode, proc.stderr)
        assert "Traceback" not in proc.stderr

    def test_gate_off_notes_the_unreadable_queue_and_exits_0(self, tmp_path: Path):
        product = _product(tmp_path, "operator_verification_required: false\n", _GARBLED_QUEUE)
        result = ov.run_check_operator_verification(product)
        assert result["required"] is False
        assert result["note"] and "operator-verification.md" in result["note"]
        proc = _run_hook(product, "check-operator-verification")
        assert proc.returncode == 0, proc.stderr
        assert "Traceback" not in proc.stderr

    def test_verify_returns_the_error_shape(self, tmp_path: Path):
        product = _product(tmp_path, "operator_verification_required: true\n", _GARBLED_QUEUE)
        result = ov.run_verify_entry(product, "VRF-001")
        assert "error" in result
        assert "operator-verification.md" in result["error"]

    def test_accept_returns_the_error_shape_and_writes_nothing(self, tmp_path: Path):
        product = _product(tmp_path, "operator_verification_required: true\n", _GARBLED_QUEUE)
        queue = product / ".prawduct" / "operator-verification.md"
        before = queue.read_bytes()
        result = ov.run_accept_pending(product, "shipping anyway")
        assert "error" in result
        assert queue.read_bytes() == before

    def test_cli_verify_and_accept_refuse_without_a_traceback(self, tmp_path: Path):
        product = _product(tmp_path, "operator_verification_required: true\n", _GARBLED_QUEUE)
        for args in (
            ("verify-operator-verification", "VRF-001"),
            ("accept-operator-verification", "shipping anyway"),
        ):
            proc = _run_hook(product, *args)
            assert proc.returncode == 1, (args, proc.returncode, proc.stderr)
            assert proc.stderr.startswith("error: "), (args, proc.stderr)
            assert "Traceback" not in proc.stderr

    def test_a_readable_queue_is_unaffected(self, tmp_path: Path):
        product = _product(tmp_path, "operator_verification_required: true\n", _PENDING_QUEUE)
        result = ov.run_check_operator_verification(product)
        assert result["queue_status"] == ov.QUEUE_OK
        assert result["pending"] == 1
