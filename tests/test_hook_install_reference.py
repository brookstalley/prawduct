"""Tests for the ``prawduct-hook print-install-reference`` subcommand.

The published form of how a repo references this plugin. Before it existed the
value was a private module constant with no readable form, so external
consumers AST-parsed ``migrate_plugin.INSTALL_REFERENCE`` — deliberately, since
the alternative (transcribing it) drifts silently, which is the exact failure
that put a wrong copy into 11 repos.

**Every assertion here compares against the constant, never a literal.** A
transcribed copy in the test would be a third copy of the contract and would go
stale the same way the ones in those repos did — the test would then certify
agreement with a value nobody maintains.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent / "plugin"
sys.path.insert(0, str(_ROOT))

from lib.migrate_plugin import INSTALL_REFERENCE  # noqa: E402

_hook_loader = importlib.machinery.SourceFileLoader(
    "prawduct_hook_install_reference", str(_ROOT / "bin" / "prawduct-hook")
)
_hook_spec = importlib.util.spec_from_loader("prawduct_hook_install_reference", _hook_loader)
_hook = importlib.util.module_from_spec(_hook_spec)
_hook_loader.exec_module(_hook)


class TestPrintInstallReference:
    def test_emits_json_that_round_trips_to_the_constant(self, capsys):
        rc = _hook.cmd_print_install_reference()
        out = capsys.readouterr().out
        assert rc == 0
        assert json.loads(out) == INSTALL_REFERENCE

    def test_stdout_is_pure_json_so_a_consumer_can_pipe_it(self, capsys):
        """The whole point is machine-readability from a repo that has the
        plugin installed but not vendored — a banner or warning on stdout would
        break every consumer parsing it."""
        _hook.cmd_print_install_reference()
        captured = capsys.readouterr()
        assert captured.out.endswith("\n")
        assert json.loads(captured.out)  # no leading/trailing non-JSON
        assert captured.err == ""

    def test_output_is_stable_across_calls(self, capsys):
        """Sorted keys: a consumer diffing two plugin versions' output should
        see only real contract changes, never dict-ordering noise."""
        _hook.cmd_print_install_reference()
        first = capsys.readouterr().out
        _hook.cmd_print_install_reference()
        assert capsys.readouterr().out == first

    def test_publishes_the_keys_a_settings_merge_needs(self):
        """Guards the *shape* the value must keep to be an install reference at
        all — derived from the constant, so it pins structure without
        transcribing any value. ``init_product`` and ``migrate_plugin`` both
        merge these top-level keys into a repo's ``.claude/settings.json``."""
        assert set(INSTALL_REFERENCE) == {"extraKnownMarketplaces", "enabledPlugins"}
        assert all(isinstance(v, dict) for v in INSTALL_REFERENCE.values())

    def test_exit_1_when_the_constant_cannot_be_imported(self, monkeypatch, capsys):
        """Degrades to an attributed error rather than printing something a
        consumer would merge — a half-written install reference is worse than
        none, because the caller cannot tell it is incomplete."""
        monkeypatch.setitem(sys.modules, "lib.migrate_plugin", None)
        rc = _hook.cmd_print_install_reference()
        captured = capsys.readouterr()
        assert rc == 1
        assert captured.out == ""
        assert "install reference" in captured.err
