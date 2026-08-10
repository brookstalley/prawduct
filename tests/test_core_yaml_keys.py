"""The column-0 YAML key scanners in ``lib/core.py``, and the hook's mirror.

``project-state.yaml`` is read without a PyYAML dependency by a deliberately
small column-0 scan. Two callers share it: ``lib.core.read_bool_yaml_key`` and
an inline mirror in ``bin/prawduct-hook`` kept import-light because it sits on
the session hot path. A mirror that drifts from its original is a silent
behaviour split, so the parity between them is pinned here rather than assumed.

These tests were extracted (SYN-9C4T) from a scan shared by two opt-in flags:
``coverage_required``, which survives, and ``views_enabled``, which was retired
with the derived-view machinery. They live here rather than in that module's
test file because their subject outlived it — the retirement removed a caller,
not the scanner.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib import core  # noqa: E402

HOOK_PATH = _REPO_ROOT / "bin" / "prawduct-hook"

# plugin-runtime inline mirror via SourceFileLoader (extensionless shebang script)
_hook_loader = importlib.machinery.SourceFileLoader("prawduct_hook_yaml_keys", str(HOOK_PATH))
_hook_spec = importlib.util.spec_from_loader("prawduct_hook_yaml_keys", _hook_loader)
_hook = importlib.util.module_from_spec(_hook_spec)
_hook_loader.exec_module(_hook)


class TestReadBoolYamlKey:
    """The shared column-0 boolean scan."""

    def test_true_value(self, tmp_path: Path):
        p = tmp_path / "s.yaml"
        p.write_text("classification:\n  domain: util\ncoverage_required: true\n")
        assert core.read_bool_yaml_key(p, "coverage_required") is True

    def test_false_value(self, tmp_path: Path):
        p = tmp_path / "s.yaml"
        p.write_text("coverage_required: false\n")
        assert core.read_bool_yaml_key(p, "coverage_required") is False

    def test_missing_key(self, tmp_path: Path):
        p = tmp_path / "s.yaml"
        p.write_text("operator_verification_required: true\n")
        assert core.read_bool_yaml_key(p, "coverage_required") is False

    def test_missing_file(self, tmp_path: Path):
        assert core.read_bool_yaml_key(tmp_path / "nope.yaml", "coverage_required") is False

    def test_indented_line_ignored(self, tmp_path: Path):
        """A nested ``key: true`` must not flip the top-level switch — only
        column-0 keys count."""
        p = tmp_path / "s.yaml"
        p.write_text("nested:\n  coverage_required: true\n")
        assert core.read_bool_yaml_key(p, "coverage_required") is False

    def test_comment_only_line_ignored(self, tmp_path: Path):
        p = tmp_path / "s.yaml"
        p.write_text("# coverage_required: true\ncoverage_required: false\n")
        assert core.read_bool_yaml_key(p, "coverage_required") is False

    def test_quoted_true_reads_false(self, tmp_path: Path):
        """Quotes are not stripped (unlike ``read_str_yaml_key``): a quoted
        ``"true"`` does not equal the bare ``true`` sentinel."""
        p = tmp_path / "s.yaml"
        p.write_text('coverage_required: "true"\n')
        assert core.read_bool_yaml_key(p, "coverage_required") is False


class TestBoolKeyCallSiteParity:
    """The inline ``_read_bool_yaml_key`` mirror in ``bin/prawduct-hook`` — kept
    import-light on the hot path — must agree with ``core.read_bool_yaml_key``.

    A second call site (``is_views_enabled``) was pinned here until the flag it
    read was retired. The mirror is the one that remains, and it is the one that
    matters: a copy that drifts is a behaviour split nothing else would catch.
    """

    def test_hook_mirror_parity_true(self, tmp_path: Path):
        p = tmp_path / "project-state.yaml"
        p.write_text("coverage_required: true\n")
        assert _hook._read_bool_yaml_key(p, "coverage_required") == core.read_bool_yaml_key(
            p, "coverage_required"
        )

    def test_hook_mirror_parity_missing_and_indented(self, tmp_path: Path):
        # missing file
        gone = tmp_path / "nope.yaml"
        assert _hook._read_bool_yaml_key(gone, "coverage_required") == core.read_bool_yaml_key(
            gone, "coverage_required"
        )
        # indented (must not flip)
        p = tmp_path / "project-state.yaml"
        p.write_text("nested:\n  coverage_required: true\n")
        assert _hook._read_bool_yaml_key(p, "coverage_required") == core.read_bool_yaml_key(
            p, "coverage_required"
        )

    def test_the_parity_assertions_are_not_vacuous(self, tmp_path: Path):
        """The positive control for the two tests above.

        They assert the two functions AGREE, and agreement is exactly what two
        broken scanners returning False for every input would also show. So this
        requires the pair to actually discriminate: True on a set key, False on a
        missing file, from both implementations independently.
        """
        setkey = tmp_path / "set.yaml"
        setkey.write_text("coverage_required: true\n")
        gone = tmp_path / "nope.yaml"

        assert core.read_bool_yaml_key(setkey, "coverage_required") is True
        assert _hook._read_bool_yaml_key(setkey, "coverage_required") is True
        assert core.read_bool_yaml_key(gone, "coverage_required") is False
        assert _hook._read_bool_yaml_key(gone, "coverage_required") is False
