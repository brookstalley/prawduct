"""The collector's Python-parity fixtures are regenerated from the client, not trusted.

The collector's suite checks its JS validator and number formatting against two
committed fixtures, both written by ``collector/test/fixtures/generate.py`` from
the plugin's real ``contribution.to_step`` and ``validate``. If the client changes
and nobody regenerates them, both suites stay green while the deployed collector
refuses what the client sends. So this rebuilds both from the client in the
tree and compares.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent.parent / "collector" / "test" / "fixtures"


def _generate():
    spec = importlib.util.spec_from_file_location("collector_fixture_generate", FIXTURES / "generate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_step_values_fixture_matches_the_client():
    committed = json.loads((FIXTURES / "python-step-values.json").read_text(encoding="utf-8"))
    assert committed["values"], "the fixture must hold values to compare"
    assert _generate().step_values() == committed["values"]


def test_the_verdicts_fixture_matches_the_client():
    generate = _generate()
    committed = json.loads((FIXTURES / "python-verdicts.json").read_text(encoding="utf-8"))
    assert committed["cases"], "the fixture must hold cases to compare"
    assert [generate.verdict(body) for body in generate.BODIES] == committed["cases"]
