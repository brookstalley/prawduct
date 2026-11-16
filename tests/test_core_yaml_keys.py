"""The column-0 boolean YAML key scanner in ``lib/core.py``.

``project-state.yaml`` is read without a PyYAML dependency by a deliberately
small column-0 scan, ``core.read_bool_flag``, the one reader of a boolean opt-in
flag. (It once had an inline copy in ``bin/prawduct-hook`` pinned here by a
parity test; the copy had no callers and was deleted with #777.)

These tests were extracted (SYN-9C4T) from a scan shared by two opt-in flags:
``coverage_required``, which survives, and ``views_enabled``, which was retired
with the derived-view machinery. They live here rather than in that module's
test file because their subject outlived it — the retirement removed a caller,
not the scanner. The unreadable-file cases live in
``tests/test_gate_flags_fail_closed.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib import core  # noqa: E402


def _flag(path: Path, key: str) -> bool:
    return core.read_bool_flag(path, key)["value"]


class TestReadBoolFlagValue:
    """The shared column-0 boolean scan."""

    def test_true_value(self, tmp_path: Path):
        p = tmp_path / "s.yaml"
        p.write_text("classification:\n  domain: util\ncoverage_required: true\n")
        assert _flag(p, "coverage_required") is True

    def test_false_value(self, tmp_path: Path):
        p = tmp_path / "s.yaml"
        p.write_text("coverage_required: false\n")
        assert _flag(p, "coverage_required") is False

    def test_missing_key(self, tmp_path: Path):
        p = tmp_path / "s.yaml"
        p.write_text("operator_verification_required: true\n")
        assert _flag(p, "coverage_required") is False

    def test_missing_file(self, tmp_path: Path):
        assert _flag(tmp_path / "nope.yaml", "coverage_required") is False

    def test_indented_line_ignored(self, tmp_path: Path):
        """A nested ``key: true`` must not flip the top-level switch — only
        column-0 keys count."""
        p = tmp_path / "s.yaml"
        p.write_text("nested:\n  coverage_required: true\n")
        assert _flag(p, "coverage_required") is False

    def test_comment_only_line_ignored(self, tmp_path: Path):
        p = tmp_path / "s.yaml"
        p.write_text("# coverage_required: true\ncoverage_required: false\n")
        assert _flag(p, "coverage_required") is False

    def test_quoted_true_reads_false(self, tmp_path: Path):
        """Quotes are not stripped (unlike ``read_str_yaml_key``): a quoted
        ``"true"`` does not equal the bare ``true`` sentinel."""
        p = tmp_path / "s.yaml"
        p.write_text('coverage_required: "true"\n')
        assert _flag(p, "coverage_required") is False
