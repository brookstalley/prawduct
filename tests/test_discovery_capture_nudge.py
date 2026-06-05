"""Tests for the discovery-capture nudge (`cmd_clear` session-start detection).

The gap this guards: a repo onboarded via `/prawduct:onboard` and then worked on
docs-first (or as an existing codebase) accrues rich product-definition work while
`project-state.yaml` stays template-default — and prawduct never nudges, because
the only "you haven't done discovery" signal (the project-preferences CRITICAL)
is gated on source code (`_has_product_code`), staying silent through a no-code
discovery/architecture phase. The nudge fires when discovery is uncaptured AND the
repo shows product-definition work (code OR docs/markdown); a freshly-onboarded
empty repo (no code, no docs) stays silent.

This is the first direct coverage for this `cmd_clear` detection family — the
pre-existing project-preferences CRITICAL it sits beside had none.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_loader = importlib.machinery.SourceFileLoader(
    "prawduct_hook_discovery", str(_ROOT / "bin" / "prawduct-hook")
)
_spec = importlib.util.spec_from_loader("prawduct_hook_discovery", _loader)
_hook = importlib.util.module_from_spec(_spec)
_loader.exec_module(_hook)

# Stable substrings the briefing emits — pinned so a reword that drops the routing
# target or the "reconcile" affordance is caught.
_NUDGE = "DISCOVERY NOT CAPTURED"
_ROUTE = "/prawduct:discovery"
_PREFS_CRITICAL = "MUST create .prawduct/artifacts/project-preferences.md"

_UNCAPTURED_STATE = (
    "classification:\n"
    "  domain: null\n"
    "product_definition:\n"
    "  vision: null\n"
    "distribution: plugin\n"
)
_CAPTURED_STATE = (
    "classification:\n"
    "  domain: productivity\n"
    "product_definition:\n"
    '  vision: "Turn ideas into software"\n'
    "distribution: plugin\n"
)


def _repo(tmp_path: Path, *, state: str, code: bool = False, docs: bool = False) -> Path:
    """Build a minimal product repo: .prawduct/project-state.yaml plus optional
    product-definition signals (source code and/or docs markdown)."""
    prawduct = tmp_path / ".prawduct"
    prawduct.mkdir()
    (prawduct / "project-state.yaml").write_text(state)
    if code:
        src = tmp_path / "src"
        src.mkdir()
        (src / "app.py").write_text("print('hi')\n")
    if docs:
        reqs = tmp_path / "docs" / "requirements"
        reqs.mkdir(parents=True)
        (reqs / "index.md").write_text("# Requirements\n")
    return tmp_path


# =============================================================================
# Pure helpers
# =============================================================================


class TestDiscoveryUncaptured:
    def test_both_sentinels_present_is_uncaptured(self, tmp_path):
        p = tmp_path / "state.yaml"
        p.write_text(_UNCAPTURED_STATE)
        assert _hook._discovery_uncaptured(p) is True

    def test_domain_filled_is_captured(self, tmp_path):
        p = tmp_path / "state.yaml"
        p.write_text(_UNCAPTURED_STATE.replace("  domain: null\n", "  domain: content\n"))
        assert _hook._discovery_uncaptured(p) is False

    def test_vision_filled_is_captured(self, tmp_path):
        p = tmp_path / "state.yaml"
        p.write_text(_UNCAPTURED_STATE.replace("  vision: null\n", '  vision: "X"\n'))
        assert _hook._discovery_uncaptured(p) is False

    def test_fully_captured_is_captured(self, tmp_path):
        p = tmp_path / "state.yaml"
        p.write_text(_CAPTURED_STATE)
        assert _hook._discovery_uncaptured(p) is False

    def test_missing_file_is_not_uncaptured(self, tmp_path):
        # Conservative: no file → no claim that discovery was skipped (the caller
        # also guards on state_path.is_file(), but the helper must not raise).
        assert _hook._discovery_uncaptured(tmp_path / "nope.yaml") is False


class TestHasProductCode:
    def test_python_source_counts(self, tmp_path):
        (tmp_path / "app.py").write_text("x = 1\n")
        assert _hook._has_product_code(tmp_path) is True

    def test_prawduct_state_does_not_count(self, tmp_path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(_UNCAPTURED_STATE)
        assert _hook._has_product_code(tmp_path) is False

    def test_framework_tooling_does_not_count(self, tmp_path):
        lib = tmp_path / "tools" / "lib"
        lib.mkdir(parents=True)
        (lib / "core.py").write_text("x = 1\n")
        assert _hook._has_product_code(tmp_path) is False

    def test_markdown_only_is_not_code(self, tmp_path):
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "vision.md").write_text("# Vision\n")
        assert _hook._has_product_code(tmp_path) is False


class TestHasProductDefinitionWork:
    def test_code_counts(self, tmp_path):
        (tmp_path / "app.py").write_text("x = 1\n")
        assert _hook._has_product_definition_work(tmp_path) is True

    def test_docs_markdown_counts(self, tmp_path):
        reqs = tmp_path / "docs" / "requirements"
        reqs.mkdir(parents=True)
        (reqs / "index.md").write_text("# Requirements\n")
        assert _hook._has_product_definition_work(tmp_path) is True

    def test_documentation_dir_markdown_counts(self, tmp_path):
        # `documentation/` is the other framework-recognized doc root (CLAUDE.md /
        # MIG-6B0R) — a docs-first product using it must trip the signal too.
        d = tmp_path / "documentation"
        d.mkdir()
        (d / "vision.md").write_text("# Vision\n")
        assert _hook._has_product_definition_work(tmp_path) is True

    def test_empty_repo_is_no_work(self, tmp_path):
        (tmp_path / ".prawduct").mkdir()
        assert _hook._has_product_definition_work(tmp_path) is False

    def test_docs_dir_without_markdown_is_no_work(self, tmp_path):
        # A docs/ with only a .gitkeep is a scaffold, not product-definition work.
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / ".gitkeep").write_text("")
        assert _hook._has_product_definition_work(tmp_path) is False


# =============================================================================
# Wiring — cmd_clear emits (or withholds) the nudge in the briefing
# =============================================================================


class TestTemplateContract:
    """The detector is a substring match against project-state.yaml sentinels.
    Pin the SHIPPED template (what `init-product` renders) so a reformat of the
    `domain:` / `vision:` lines fails loud HERE instead of silently disabling the
    docs-first discovery nudge — the exact silent-degradation class of BLD-7P3K.
    The other tests use a hand-written `_UNCAPTURED_STATE`; this one ties the
    contract to the real file so the two can't drift apart unnoticed.
    """

    def test_shipped_template_reads_as_uncaptured(self):
        template = _ROOT / "templates" / "project-state.yaml"
        assert template.is_file()
        assert _hook._discovery_uncaptured(template) is True, (
            "templates/project-state.yaml no longer trips _discovery_uncaptured — "
            "the domain:/vision: sentinel format changed. Update the detection in "
            "bin/prawduct-hook (_discovery_uncaptured) to match, or the docs-first "
            "discovery nudge silently stops firing on freshly-onboarded repos."
        )


class TestNudgeWiring:
    def test_docs_first_repo_fires_nudge_not_prefs_critical(self, tmp_path, capsys):
        # THE Scriob case: discovery uncaptured, docs present, no code. The
        # discovery nudge fires; the code-gated project-preferences CRITICAL does
        # NOT (this is exactly the phase the old detection was blind to).
        repo = _repo(tmp_path, state=_UNCAPTURED_STATE, docs=True, code=False)
        _hook.cmd_clear(repo)
        out = capsys.readouterr().out
        assert _NUDGE in out
        assert _ROUTE in out
        assert _PREFS_CRITICAL not in out

    def test_brownfield_code_fires_nudge(self, tmp_path, capsys):
        # Existing codebase onboarded without discovery: nudge fires (and the
        # prefs CRITICAL fires too — both are genuinely missing).
        repo = _repo(tmp_path, state=_UNCAPTURED_STATE, code=True, docs=False)
        _hook.cmd_clear(repo)
        out = capsys.readouterr().out
        assert _NUDGE in out
        assert _PREFS_CRITICAL in out  # refactor-safety: prefs CRITICAL still wired

    def test_fresh_onboarded_repo_is_silent(self, tmp_path, capsys):
        # Uncaptured but no product work yet — do not nag a just-scaffolded repo.
        repo = _repo(tmp_path, state=_UNCAPTURED_STATE, code=False, docs=False)
        _hook.cmd_clear(repo)
        out = capsys.readouterr().out
        assert _NUDGE not in out
        assert _PREFS_CRITICAL not in out

    def test_captured_discovery_is_silent(self, tmp_path, capsys):
        # Discovery captured — no nudge even with product work present.
        repo = _repo(tmp_path, state=_CAPTURED_STATE, docs=True, code=True)
        _hook.cmd_clear(repo)
        out = capsys.readouterr().out
        assert _NUDGE not in out
