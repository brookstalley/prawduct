"""Tests for the discovery-capture nudge (layer 0 of the structural-coverage chain).

The gap this guards: a repo onboarded via `/prawduct:onboard` and then worked on
docs-first (or as an existing codebase) accrues rich product-definition work while
`project-state.yaml` stays template-default — and prawduct never nudges, because
the only "you haven't done discovery" signal (the project-preferences CRITICAL)
is gated on source code (`_has_product_code`), staying silent through a no-code
discovery/architecture phase. The nudge fires when discovery is uncaptured AND the
repo shows product-definition work (code OR docs/markdown); a freshly-onboarded
empty repo (no code, no docs) stays silent.

Delivery contract: the nudge is an advisory-store probe
(`lib.coverage_probes.probe_discovery_not_captured`), synced by `cmd_clear`'s
roster step and surfaced in the session briefing's ADVISORIES block — dismissible
per-clone, unlike the hard print it replaced. The wiring tests below assert both
surfaces: the store entry (the durable record) and the briefing text (what the
session actually sees).
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

# The read-only probes moved to lib/gitstate.py (STH-9V4K ch.2); cmd_clear stays
# in the hook (the integration surface exercised below via _hook.cmd_clear).
from lib import gitstate  # noqa: E402

# Stable substrings the briefing emits — pinned so a reword that drops the routing
# target or the "reconcile" affordance is caught.
_NUDGE = "DISCOVERY NOT CAPTURED"
_ROUTE = "/prawduct:methodology discovery"
_PREFS_CRITICAL = "MUST create .prawduct/artifacts/project-preferences.md"
# The sharpened layer-0 variant (discovery ran — domain/vision filled — but the
# structural characteristics were never recorded) uses this distinct phrasing.
_STRUCT_VARIANT = "does not record this product's"

# A recorded structural block (>=1 characteristic present) — what "fully captured"
# now requires. The layer-0 nudge is gated on the SHARED coverage predicate
# (structural_characteristics_recorded), so a state with domain+vision but no
# recorded characteristic is NOT "captured" for staging purposes.
_STRUCTURAL_BLOCK_RECORDED = (
    "  structural:\n"
    "    has_human_interface:\n"
    "      modality: terminal\n"
)
# A present-but-all-null structural block (the template default / never-recorded).
_STRUCTURAL_BLOCK_NULL = (
    "  structural:\n"
    "    has_human_interface: null\n"
    "    runs_unattended: null\n"
    "    exposes_programmatic_interface: null\n"
    "    has_multiple_party_types: null\n"
    "    handles_sensitive_data: null\n"
    "    multi_process_distributed: null\n"
)

_UNCAPTURED_STATE = (
    "classification:\n"
    "  domain: null\n"
    "product_definition:\n"
    "  vision: null\n"
    "distribution: plugin\n"
)
# Fully captured: domain, vision, AND >=1 structural characteristic recorded.
_CAPTURED_STATE = (
    "classification:\n"
    "  domain: productivity\n"
    f"{_STRUCTURAL_BLOCK_RECORDED}"
    "product_definition:\n"
    '  vision: "Turn ideas into software"\n'
    "distribution: plugin\n"
)
# The sharpening's target: discovery ran (domain + vision filled) but structural
# characteristics were never recorded (all null) — the gap the old domain/vision-only
# detection missed. prawduct's own state is a sibling of this (no structural block).
_STRUCTURAL_UNRECORDED_STATE = (
    "classification:\n"
    "  domain: productivity\n"
    f"{_STRUCTURAL_BLOCK_NULL}"
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
        assert gitstate._discovery_uncaptured(p) is True

    def test_domain_filled_is_captured(self, tmp_path):
        p = tmp_path / "state.yaml"
        p.write_text(_UNCAPTURED_STATE.replace("  domain: null\n", "  domain: content\n"))
        assert gitstate._discovery_uncaptured(p) is False

    def test_vision_filled_is_captured(self, tmp_path):
        p = tmp_path / "state.yaml"
        p.write_text(_UNCAPTURED_STATE.replace("  vision: null\n", '  vision: "X"\n'))
        assert gitstate._discovery_uncaptured(p) is False

    def test_fully_captured_is_captured(self, tmp_path):
        p = tmp_path / "state.yaml"
        p.write_text(_CAPTURED_STATE)
        assert gitstate._discovery_uncaptured(p) is False

    def test_missing_file_is_not_uncaptured(self, tmp_path):
        # Conservative: no file → no claim that discovery was skipped (the caller
        # also guards on state_path.is_file(), but the helper must not raise).
        assert gitstate._discovery_uncaptured(tmp_path / "nope.yaml") is False


class TestHasProductCode:
    def test_python_source_counts(self, tmp_path):
        (tmp_path / "app.py").write_text("x = 1\n")
        assert gitstate._has_product_code(tmp_path) is True

    def test_prawduct_state_does_not_count(self, tmp_path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(_UNCAPTURED_STATE)
        assert gitstate._has_product_code(tmp_path) is False

    def test_framework_tooling_does_not_count(self, tmp_path):
        lib = tmp_path / "tools" / "lib"
        lib.mkdir(parents=True)
        (lib / "core.py").write_text("x = 1\n")
        assert gitstate._has_product_code(tmp_path) is False

    def test_markdown_only_is_not_code(self, tmp_path):
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "vision.md").write_text("# Vision\n")
        assert gitstate._has_product_code(tmp_path) is False


class TestHasProductDefinitionWork:
    def test_code_counts(self, tmp_path):
        (tmp_path / "app.py").write_text("x = 1\n")
        assert gitstate._has_product_definition_work(tmp_path) is True

    def test_docs_markdown_counts(self, tmp_path):
        reqs = tmp_path / "docs" / "requirements"
        reqs.mkdir(parents=True)
        (reqs / "index.md").write_text("# Requirements\n")
        assert gitstate._has_product_definition_work(tmp_path) is True

    def test_documentation_dir_markdown_counts(self, tmp_path):
        # `documentation/` is the other framework-recognized doc root (CLAUDE.md /
        # MIG-6B0R) — a docs-first product using it must trip the signal too.
        d = tmp_path / "documentation"
        d.mkdir()
        (d / "vision.md").write_text("# Vision\n")
        assert gitstate._has_product_definition_work(tmp_path) is True

    def test_empty_repo_is_no_work(self, tmp_path):
        (tmp_path / ".prawduct").mkdir()
        assert gitstate._has_product_definition_work(tmp_path) is False

    def test_docs_dir_without_markdown_is_no_work(self, tmp_path):
        # A docs/ with only a .gitkeep is a scaffold, not product-definition work.
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / ".gitkeep").write_text("")
        assert gitstate._has_product_definition_work(tmp_path) is False


# =============================================================================
# Wiring — cmd_clear syncs (or withholds) the nudge advisory; briefing surfaces it
# =============================================================================


def _active_nudges(repo: Path) -> list[dict]:
    """The active discovery-not-captured advisories in the repo's store."""
    import json

    store_path = repo / ".prawduct" / ".advisories.json"
    if not store_path.is_file():
        return []
    store = json.loads(store_path.read_text(encoding="utf-8"))
    return [
        a
        for a in store.get("advisories", [])
        if a.get("type") == "discovery-not-captured" and a.get("state") == "active"
    ]


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
        assert gitstate._discovery_uncaptured(template) is True, (
            "templates/project-state.yaml no longer trips _discovery_uncaptured — "
            "the domain:/vision: sentinel format changed. Update the detection in "
            "lib/gitstate.py (_discovery_uncaptured) to match, or the docs-first "
            "discovery nudge silently stops firing on freshly-onboarded repos."
        )

    def test_shipped_template_reads_as_structural_unrecorded(self):
        # The layer-0 fire decision is the coverage predicate. The template ships
        # classification.structural with every characteristic null, so a fresh repo
        # must read as "structural not recorded" — else the sharpened nudge silently
        # stops firing on freshly-onboarded repos (the same failure class as above,
        # for the structural gate).
        from lib import coverage_probes

        template = _ROOT / "templates" / "project-state.yaml"
        assert coverage_probes.structural_characteristics_recorded(template) is False, (
            "templates/project-state.yaml now reads as recording a structural "
            "characteristic — the classification.structural default format changed. "
            "Update the scanner in lib/coverage_probes.py or the template, or the "
            "sharpened layer-0 discovery nudge (and layer-1 staging) stops firing on "
            "freshly-onboarded repos."
        )


class TestNudgeWiring:
    def test_docs_first_repo_fires_nudge_not_prefs_critical(self, tmp_path, capsys):
        # THE Scriob case: discovery uncaptured, docs present, no code. The
        # discovery nudge fires; the code-gated project-preferences CRITICAL does
        # NOT (this is exactly the phase the old detection was blind to).
        repo = _repo(tmp_path, state=_UNCAPTURED_STATE, docs=True, code=False)
        _hook.cmd_clear(repo)
        out = capsys.readouterr().out
        assert len(_active_nudges(repo)) == 1
        assert _NUDGE in out  # surfaced in the briefing's ADVISORIES block
        assert _ROUTE in out
        assert _PREFS_CRITICAL not in out

    def test_brownfield_code_fires_nudge(self, tmp_path, capsys):
        # Existing codebase onboarded without discovery: nudge fires (and the
        # prefs CRITICAL fires too — both are genuinely missing).
        repo = _repo(tmp_path, state=_UNCAPTURED_STATE, code=True, docs=False)
        _hook.cmd_clear(repo)
        out = capsys.readouterr().out
        assert len(_active_nudges(repo)) == 1
        assert _NUDGE in out
        assert _PREFS_CRITICAL in out  # refactor-safety: prefs CRITICAL still wired

    def test_fresh_onboarded_repo_is_silent(self, tmp_path, capsys):
        # Uncaptured but no product work yet — do not nag a just-scaffolded repo.
        repo = _repo(tmp_path, state=_UNCAPTURED_STATE, code=False, docs=False)
        _hook.cmd_clear(repo)
        out = capsys.readouterr().out
        assert _active_nudges(repo) == []
        assert _NUDGE not in out
        assert _PREFS_CRITICAL not in out

    def test_captured_discovery_is_silent(self, tmp_path, capsys):
        # Fully captured (domain + vision + a recorded structural characteristic) —
        # no nudge even with product work present.
        repo = _repo(tmp_path, state=_CAPTURED_STATE, docs=True, code=True)
        _hook.cmd_clear(repo)
        out = capsys.readouterr().out
        assert _active_nudges(repo) == []
        assert _NUDGE not in out

    def test_structural_unrecorded_fires_sharpened_nudge(self, tmp_path, capsys):
        # THE sharpening: domain + vision are filled (old detection would call this
        # "captured" and stay silent), but no structural characteristic is recorded.
        # Layer 0 now fires with the structural-specific variant — the gap that let
        # prawduct's own rich-but-characteristic-less state pass silently.
        repo = _repo(tmp_path, state=_STRUCTURAL_UNRECORDED_STATE, code=True, docs=False)
        _hook.cmd_clear(repo)
        out = capsys.readouterr().out
        nudges = _active_nudges(repo)
        assert len(nudges) == 1
        assert _STRUCT_VARIANT in nudges[0]["trigger_summary"]  # sharpened, not never-ran
        assert _NUDGE in out
        assert _ROUTE in out

    def test_recorded_structural_is_silent_even_without_vision(self, tmp_path, capsys):
        # The fire decision is the structural predicate alone: once a characteristic
        # is recorded, layer 0 clears (layer 1 takes over) — staging is one nudge at
        # a time, keyed off the shared predicate, not off domain/vision.
        state = (
            "classification:\n"
            "  domain: productivity\n"
            f"{_STRUCTURAL_BLOCK_RECORDED}"
            "distribution: plugin\n"
        )
        repo = _repo(tmp_path, state=state, code=True, docs=False)
        _hook.cmd_clear(repo)
        out = capsys.readouterr().out
        assert _active_nudges(repo) == []
        assert _NUDGE not in out

    def test_nudge_is_a_dismissible_warn_advisory(self, tmp_path, capsys):
        # The whole point of advisory delivery (vs the hard print it replaced): the
        # entry carries an id the owner can dismiss per-clone, at warn priority so
        # it sorts above the info siblings; the briefing renders the dismiss path.
        repo = _repo(tmp_path, state=_UNCAPTURED_STATE, docs=True, code=False)
        _hook.cmd_clear(repo)
        out = capsys.readouterr().out
        (nudge,) = _active_nudges(repo)
        assert nudge["priority"] == "warn"
        assert nudge.get("id")
        assert "/prawduct:advisory dismiss" in out
