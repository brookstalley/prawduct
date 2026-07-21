"""Tests for the ``prawduct-hook version`` subcommand.

The bare-semver version source consumers stamp into upstream bug reports (the
``Found in: prawduct vX.Y.Z`` field — XP2 provenance / the MG5 report-bug path)
instead of *recalling* a version from the model. It reads
``.claude-plugin/plugin.json`` at call time and prints one bare line, so a skill
can format ``prawduct v<version>`` deterministically.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent / "plugin"

# Load the extensionless plugin-runtime hook via SourceFileLoader (the script has
# a shebang, no .py extension). The module name is not "__main__", so its CLI
# dispatch does not run at import.
_hook_loader = importlib.machinery.SourceFileLoader(
    "prawduct_hook_version", str(_ROOT / "bin" / "prawduct-hook")
)
_hook_spec = importlib.util.spec_from_loader("prawduct_hook_version", _hook_loader)
_hook = importlib.util.module_from_spec(_hook_spec)
_hook_loader.exec_module(_hook)


def _manifest_version() -> str:
    return json.loads((_ROOT / ".claude-plugin" / "plugin.json").read_text())["version"]


def test_prints_manifest_version_exit_0(capsys):
    rc = _hook.cmd_version()
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert out == _manifest_version()


def test_output_is_bare_semver_no_v_prefix(capsys):
    _hook.cmd_version()
    out = capsys.readouterr().out.strip()
    # Bare so a consumer formats `prawduct v<version>` itself — no leading "v", no
    # decoration, exactly one line.
    assert "\n" not in out
    assert not out.startswith("v")
    assert out[0].isdigit()


def test_exit_1_when_manifest_unreadable(monkeypatch, capsys):
    # A missing/corrupt manifest degrades to exit 1 with no output — the report-bug
    # skill then falls back rather than emitting a bogus version.
    monkeypatch.setattr(_hook, "_plugin_manifest_version", lambda: None)
    rc = _hook.cmd_version()
    out = capsys.readouterr().out.strip()
    assert rc == 1
    assert out == ""
