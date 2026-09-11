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


# --- conformance: is the recorded decision KEPT --------------------------------

_CONTRACT = """
# API Contract

## Deprecation & Compatibility

Retention: additive-first; removal defers to a major.

## Surface Inventory & Stability Tiers

- `clear` — stable
- `build-index` — deprecated
- `sketch` — experimental

## Conventions

- `not-a-member` — stable
"""


def test_declared_surface_reads_names_and_tiers():
    members = av.declared_surface(_CONTRACT)
    assert [(m.name, m.tier) for m in members] == [
        ("clear", "stable"),
        ("build-index", "deprecated"),
        ("sketch", "experimental"),
    ]


def test_the_inventory_is_scoped_to_its_own_section():
    """An inventory-shaped bullet under a different heading is not a declaration
    — otherwise every example in the artifact becomes a promise."""
    assert "not-a-member" not in {m.name for m in av.declared_surface(_CONTRACT)}


def test_retention_policy_is_free_text():
    assert av.retention_policy(_CONTRACT) == "additive-first; removal defers to a major."


def test_an_authoring_comment_declares_nothing():
    """The template SHOWS both forms by example inside HTML comments. Reading
    those as declarations makes an unauthored artifact report a binding policy
    over a surface nobody declared — a finding invented out of instructions."""
    commented = """
# API Contract

<!-- Retention: removal defers to a major.

## Surface Inventory & Stability Tiers

- `example` — stable
-->
"""
    assert av.retention_policy(commented) is None
    assert av.declared_surface(commented) == ()


def test_the_shipped_template_declares_nothing():
    """The real file, not a fixture of it: an untouched template must be inert."""
    template = (
        Path(__file__).resolve().parents[1]
        / "plugin" / "templates" / "api-contract.md"
    ).read_text()
    assert av.retention_policy(template) is None
    assert av.declared_surface(template) == ()
    assert av.conformance_departures(template, set()) == ()


def test_an_unfilled_placeholder_is_not_a_declaration():
    text = """
## Deprecation & Compatibility

Retention: <your rule, or "none">

## Surface Inventory & Stability Tiers

- `<member>` — stable
"""
    assert av.retention_policy(text) is None
    assert av.declared_surface(text) == ()


def test_a_removed_promised_member_is_a_departure():
    out = av.conformance_departures(_CONTRACT, {"clear", "sketch"})
    assert [(d.member, d.kind) for d in out] == [("build-index", "removed")]
    assert out[0].policy == "additive-first; removal defers to a major."


def test_experimental_may_break():
    """`experimental` is the tier whose entire meaning is "this may break", so
    removing one is the policy working rather than a departure from it."""
    assert av.conformance_departures(_CONTRACT, {"clear", "build-index"}) == ()


def test_nothing_removed_is_no_departure():
    assert av.conformance_departures(_CONTRACT, {"clear", "build-index", "sketch"}) == ()


def test_no_recorded_policy_reports_nothing():
    """The absence of a decision is the PRESENCE leg's WARNING. Reporting it here
    too would file one gap twice under two severities."""
    text = _CONTRACT.replace("Retention: additive-first; removal defers to a major.", "")
    assert av.retention_policy(text) is None
    assert av.conformance_departures(text, set()) == ()


def test_a_policy_that_promises_nothing_binds_nothing():
    """Force the decision, don't mandate the answer: "none" is a valid recorded
    policy, and manufacturing a finding out of it inverts the whole feature."""
    text = _CONTRACT.replace(
        "Retention: additive-first; removal defers to a major.", "Retention: none"
    )
    assert av.retention_policy(text) == "none"
    assert av.conformance_departures(text, set()) == ()


def test_dropping_the_entry_does_not_retire_the_promise():
    """Deleting the member and its inventory line in one change is amending the
    norm to match the code — the tell Goal 3's Normative authority names. Without
    the previous artifact the promise and the thing it protected vanish together."""
    after = _CONTRACT.replace("- `build-index` — deprecated\n", "")
    assert av.conformance_departures(after, {"clear", "sketch"}) == ()

    out = av.conformance_departures(
        after, {"clear", "sketch"}, previous_contract_text=_CONTRACT
    )
    assert [(d.member, d.kind) for d in out] == [("build-index", "undeclared")]


def test_un_declaring_a_member_that_is_still_there_is_not_a_departure():
    """Reclassifying a member out of the public inventory while it still exists
    is a promise being narrowed deliberately, not a consumer being broken. The
    departure this leg reports is a removal."""
    after = _CONTRACT.replace("- `build-index` — deprecated\n", "")
    out = av.conformance_departures(
        after, {"clear", "build-index", "sketch"}, previous_contract_text=_CONTRACT
    )
    assert out == ()
