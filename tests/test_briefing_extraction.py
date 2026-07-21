"""SessionStart briefing extraction — lib/briefing.py (STH-9V4K, Chunk 7).

The final decomposition chunk moved the staleness scan, the structured session
briefing, the subagent briefing, the cross-/clear handoff, and the
previous-session governance check out of ``bin/prawduct-hook`` into
``lib/briefing.py``. ``cmd_clear`` stays in the hook and reaches them via the
lazy ``_briefing()`` accessor.

Two contracts that the move opens and that the behavioral CLI tests
(``test_plugin_runtime``'s ``clear`` suite, which exercise the happy path
end-to-end through the new accessor) do NOT cover:

  1. **The public surface lives in lib/briefing and is exercised there** — the
     "test the code where it lives" discipline + the project preference that
     every public ``lib/`` function is referenced by a test. Before this chunk no
     test referenced these symbols at all; now they have a home.
  2. **Graceful degradation** — the briefing was deliberately lib-free on the hot
     path. Now it imports ``lib.briefing``; on an incomplete plugin install that
     import can fail. ``cmd_clear`` must NOT block session start: each of its five
     ``_briefing()`` call sites is broad-caught, so an import failure degrades to a
     skipped briefing while the session (markers, baseline) still proceeds. This
     pins the contract the plan's "decide + test the degradation" calls for.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path

from lib import briefing

_ROOT = Path(__file__).resolve().parent.parent / "plugin"


def _load_hook():
    """Load the extensionless hook as a module (its cmd_* live behind __main__)."""
    loader = importlib.machinery.SourceFileLoader(
        "prawduct_hook_briefing_extraction", str(_ROOT / "bin" / "prawduct-hook")
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class TestBriefingPublicApi:
    """The public briefing surface resolves and runs from lib/briefing — directly,
    not only through the hook (coverage preference + 'test where it lives')."""

    def test_public_functions_resolve(self):
        for name in (
            "staleness_scan",
            "assemble_session_briefing",
            "generate_subagent_briefing",
            "generate_session_handoff",
        ):
            assert callable(getattr(briefing, name)), f"lib.briefing.{name} missing"

    def test_assemble_briefing_renders_identity_and_work(self, tmp_path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "product_identity:\n  name: Widget\n"
            "work_in_progress:\n  description: build the thing\n  size: small\n"
        )
        staleness = briefing.staleness_scan(tmp_path)
        out = briefing.assemble_session_briefing(tmp_path, staleness)
        assert out.startswith("== SESSION BRIEFING ==")
        assert "Project: Widget" in out
        assert "build the thing (small)" in out

    def test_generate_subagent_briefing_writes_file(self, tmp_path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text("product_identity:\n  name: Widget\n")
        briefing.generate_subagent_briefing(tmp_path)
        sub = prawduct / ".subagent-briefing.md"
        assert sub.is_file()
        assert "# Subagent Briefing — Widget" in sub.read_text()

    def test_generate_session_handoff_writes_file(self, tmp_path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "work_in_progress:\n  description: in-flight work\n"
        )
        briefing.generate_session_handoff(tmp_path)
        handoff = prawduct / ".session-handoff.md"
        assert handoff.is_file()
        assert "in-flight work" in handoff.read_text()


class TestBriefingImportDegradation:
    """cmd_clear must survive a lib/briefing import failure (incomplete install):
    the session still starts (returns 0, writes its markers); only the briefing is
    skipped. Mirrors the ch.2-6 precedent — an import failure surfaces at the call
    site (broad-caught), never at the hook's top level."""

    def _onboarded_repo(self, tmp_path) -> Path:
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text("product_identity:\n  name: Widget\n")
        return prawduct

    def test_cmd_clear_writes_briefing_artifacts_normally(self, tmp_path):
        # Baseline: with a working _briefing(), cmd_clear renders the briefing and
        # writes both the session-start marker and the subagent briefing.
        prawduct = self._onboarded_repo(tmp_path)
        hook = _load_hook()
        rc = hook.cmd_clear(tmp_path)
        assert rc == 0
        assert (prawduct / ".session-start").is_file()
        assert (prawduct / ".subagent-briefing.md").is_file()

    def test_cmd_clear_survives_briefing_import_failure(self, tmp_path, monkeypatch):
        # Simulate an incomplete plugin install where lib.briefing cannot import.
        prawduct = self._onboarded_repo(tmp_path)
        hook = _load_hook()

        def _boom():
            raise ImportError("simulated incomplete install: lib.briefing unavailable")

        monkeypatch.setattr(hook, "_briefing", _boom)

        # Must not raise, and must still start the session (return 0 + marker written)...
        rc = hook.cmd_clear(tmp_path)
        assert rc == 0
        assert (prawduct / ".session-start").is_file()
        # ...while the briefing-dependent artifact is skipped (the degraded path was taken).
        assert not (prawduct / ".subagent-briefing.md").is_file()
