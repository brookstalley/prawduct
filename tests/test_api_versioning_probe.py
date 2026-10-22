"""Tests for the api-design versioning-undecided advisory probe (Chunk 05).

The contract: fire when the repo exposes an API AND no versioning decision is
recorded; suppress when the ``api_versioning_decided`` answer-store fact is truthy
OR no API is detected. Detection is polyglot — Python imports, JS/Go/Java
dependency manifests, and language-agnostic spec/IDL files — because the
motivating product is a JS app a Python-only scan would miss. Registry isolation
mirrors ``test_upstream_probes.py`` (autouse ``clear_registry``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lib.advisory_store import (
    Codebase,
    ProjectState,
    clear_registry,
    make_codebase,
    run_all_probes,
)
from lib import api_versioning_probes as av


@pytest.fixture(autouse=True)
def _isolated_registry():
    clear_registry()
    yield
    clear_registry()


def _cb(tmp_path):
    return Codebase(root=tmp_path)


def _probe(tmp_path, state=None):
    return av.probe_api_versioning_undecided(ProjectState(state or {}), _cb(tmp_path))


# --- suppression --------------------------------------------------------------


def test_suppressed_when_no_api(tmp_path):
    # Empty repo — no detector trips → no nudge.
    (tmp_path / "README.md").write_text("# just docs\n")
    assert _probe(tmp_path) == []


def test_suppressed_when_fact_set(tmp_path):
    # API present, but a decision was recorded → suppressed for everyone.
    (tmp_path / "app.py").write_text("from fastapi import FastAPI\n")
    assert _probe(tmp_path, {"api_versioning_decided": True}) == []


def test_suppressed_when_fact_is_internal_only_truthy(tmp_path):
    # Any truthy fact suppresses — including a recorded "none — internal-only"
    # decision (the load-bearing thing is that a decision exists, D14).
    (tmp_path / "app.py").write_text("from flask import Flask\n")
    assert _probe(tmp_path, {"api_versioning_decided": "none — internal-only"}) == []


# --- firing + detector coverage -----------------------------------------------


def test_fires_on_python_framework_import(tmp_path):
    (tmp_path / "app.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n")
    out = _probe(tmp_path)
    assert len(out) == 1
    assert out[0].type == "api-versioning"
    assert out[0].priority == "info"
    assert out[0].recommended_action == "/prawduct:methodology discovery"


def test_fires_on_django_rest_framework_import(tmp_path):
    # `rest_framework` is the django-rest signal; bare `django` must NOT fire.
    (tmp_path / "views.py").write_text("from rest_framework import viewsets\n")
    assert len(_probe(tmp_path)) == 1


def test_bare_django_does_not_fire(tmp_path):
    # A server-rendered Django site is not necessarily an exposed API.
    (tmp_path / "urls.py").write_text("from django.urls import path\n")
    assert _probe(tmp_path) == []


def test_fires_on_js_manifest(tmp_path):
    # The motivating case: a JS app whose package.json depends on a server
    # framework — a Python-only scan would miss it.
    (tmp_path / "package.json").write_text(
        '{\n  "dependencies": {\n    "express": "^4.18.0"\n  }\n}\n'
    )
    assert len(_probe(tmp_path)) == 1


def test_fires_on_go_manifest(tmp_path):
    (tmp_path / "go.mod").write_text(
        "module example.com/api\n\nrequire github.com/gin-gonic/gin v1.9.1\n"
    )
    assert len(_probe(tmp_path)) == 1


def test_fires_on_java_spring_manifest(tmp_path):
    (tmp_path / "pom.xml").write_text(
        "<project><dependencies><dependency>"
        "<artifactId>spring-boot-starter-web</artifactId>"
        "</dependency></dependencies></project>\n"
    )
    assert len(_probe(tmp_path)) == 1


def test_fires_on_openapi_spec_file(tmp_path):
    (tmp_path / "openapi.yaml").write_text("openapi: 3.0.0\ninfo: {title: x}\n")
    assert len(_probe(tmp_path)) == 1


def test_fires_on_proto_file(tmp_path):
    (tmp_path / "svc.proto").write_text('syntax = "proto3";\n')
    assert len(_probe(tmp_path)) == 1


def test_does_not_fire_on_vendored_only_manifest(tmp_path):
    # A package.json buried in node_modules (a *dependency's* manifest naming
    # express) must NOT be read as the product exposing an API — the scan prunes
    # vendored trees.
    nm = tmp_path / "node_modules" / "some-dep"
    nm.mkdir(parents=True)
    (nm / "package.json").write_text('{"dependencies": {"express": "^4.0.0"}}\n')
    assert _probe(tmp_path) == []


# --- id stability + registration ----------------------------------------------


def test_evidence_is_detector_independent(tmp_path, tmp_path_factory):
    # Two repos that trip *different* detectors must yield identical evidence so
    # the advisory id is one stable nudge, not a per-framework churn (D14).
    py_repo = tmp_path
    (py_repo / "app.py").write_text("from fastapi import FastAPI\n")
    spec_repo = tmp_path_factory.mktemp("spec")
    (spec_repo / "openapi.json").write_text('{"openapi": "3.0.0"}\n')
    py = _probe(py_repo)
    spec = av.probe_api_versioning_undecided(ProjectState({}), _cb(spec_repo))
    assert py[0].evidence == spec[0].evidence


def test_register_runs_in_the_roster(tmp_path):
    (tmp_path / "app.py").write_text("from fastapi import FastAPI\n")
    av.register()
    av.register()  # idempotent — register_probe overwrites
    cands = run_all_probes(ProjectState({}), make_codebase(tmp_path))
    fired = [c for c in cands if c.type == "api-versioning"]
    assert len(fired) == 1
    assert fired[0].feature == "api-design"
    assert fired[0].probe_version == av.PROBE_VERSION


def _state(tmp_path, text):
    (tmp_path / ".prawduct").mkdir(exist_ok=True)
    (tmp_path / ".prawduct" / "project-state.yaml").write_text(text, encoding="utf-8")


@pytest.mark.parametrize(
    "text",
    [
        # The shape the guides and the template describe: a nested attribute block.
        "design_decisions:\n  api_versioning_approach:\n    scheme: uri-path\n    status: active\n",
        # Inline flow mapping, and other indent steps.
        "design_decisions:\n    api_versioning_approach: {scheme: header, status: active}\n",
        # "none — internal-only" is a decision like any other.
        'design_decisions:\n  other: x\n  api_versioning_approach: "none — internal-only"  # c\n',
    ],
)
def test_suppressed_when_the_nested_record_holds_a_decision(tmp_path, text):
    # A repo that recorded the decision where the guides say to (and where
    # doctor's check reads it) must not be told it recorded none.
    (tmp_path / "app.py").write_text("from fastapi import FastAPI\n")
    _state(tmp_path, text)
    assert _probe(tmp_path) == []


@pytest.mark.parametrize(
    "text",
    [
        "design_decisions:\n  api_versioning_approach: null\n",
        "design_decisions:\n  api_versioning_approach: ~  # undecided\n",
        "design_decisions:\n  api_versioning_approach:\n  other: x\n",
        "design_decisions:\n  other:\n    api_versioning_approach: uri-path\n",
        "api_versioning_approach: uri-path\ndesign_decisions:\n  other: x\n",
    ],
)
def test_fires_when_the_nested_record_holds_no_decision(tmp_path, text):
    # The template's null, a bare key, and the key at the wrong level or outside
    # design_decisions are all unrecorded.
    (tmp_path / "app.py").write_text("from fastapi import FastAPI\n")
    _state(tmp_path, text)
    assert len(_probe(tmp_path)) == 1


def test_summary_names_both_places_a_decision_may_live(tmp_path):
    (tmp_path / "app.py").write_text("from fastapi import FastAPI\n")
    summary = _probe(tmp_path)[0].trigger_summary
    assert "design_decisions.api_versioning_approach" in summary
    assert "`api_versioning_decided`" in summary
    assert "either" in summary


def test_evidence_wording_is_frozen_so_dismissals_survive(tmp_path):
    # The id hashes the evidence: a reworded evidence string re-raises every
    # dismissed api-versioning advisory. Change it only with a PROBE_VERSION bump.
    (tmp_path / "app.py").write_text("from fastapi import FastAPI\n")
    assert _probe(tmp_path)[0].evidence == (
        "the product exposes an API but no versioning/deprecation decision "
        "is recorded (design_decisions.api_versioning_approach)",
    )
