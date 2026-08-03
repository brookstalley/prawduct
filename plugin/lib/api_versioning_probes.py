"""Post-sync advisory probe for the api-design / versioning feature.

One probe: the ambient migration nudge for a product that exposes an API but has
not recorded a versioning decision. It is the retroactive, *don't-have-to-think-
to-run-a-skill* twin of the forward Critic gate (review-protocol.md Goal 2) and
the on-demand ``/prawduct:doctor`` check #9 — same signal, three surfaces.

**Force the decision, don't mandate the answer.** The nudge is ``info``-priority
and dismissable; a legitimately-unversioned internal API silences it with one
recorded fact (``api_versioning_decided`` — "none — internal-only" is a valid
recorded decision). Resolution is the committed answer-store fact, so a
teammate's recorded decision clears the advisory for everyone on next sync.

Detection is a polyglot ``Codebase`` scan (the motivating product, scriob, is a
JS/TS app — a Python-only scan would miss the very case this feature exists for):
Python web-framework imports, JS/Go/Java dependency-manifest framework tokens,
and language-agnostic API contract / IDL artifacts (openapi / swagger / proto /
graphql). Registered at the runtime composition root (``bin/prawduct-hook``
``cmd_clear``), not at ``advisory_store`` import time, so the infrastructure
stays feature-agnostic — the same pattern as ``lib/backlog_probes.py`` and
``lib/upstream_probes.py``.
"""

from __future__ import annotations

from .advisory_store import AdvisoryCandidate, Codebase, ProjectState, register_probe

FEATURE = "api-design"
PROBE_TYPE = "api-versioning"
PROBE_VERSION = 1

# The answer-store fact (top-level scalar; Chunk 01 documents it in
# templates/project-state.yaml). Truthy = a versioning + deprecation decision, an
# explicit dated deferral, or "none — internal-only" was recorded → suppress.
# Top-level on purpose: load_project_state reads only column-0 scalars, so the
# probe cannot consult nested classification.structural.* — this flat mirror is
# the readable resolution signal.
RESOLUTION_FACT = "api_versioning_decided"

# Python web/API frameworks — import-detected (Codebase.has_imports scans *.py).
# `rest_framework` is Django REST Framework's import name (the "django-rest"
# signal); bare `django` is intentionally absent — a server-rendered Django site
# is not necessarily an exposed API and would over-fire.
PY_API_IMPORTS = ("fastapi", "flask", "starlette", "sanic", "falcon", "rest_framework")

# Language-agnostic API contract / IDL artifacts — existence is the signal.
SPEC_GLOBS = (
    "openapi*.yaml", "openapi*.yml", "openapi*.json",
    "swagger*.yaml", "swagger*.yml", "swagger*.json",
    "*.proto", "*.graphql", "*.graphqls",
)

# Polyglot framework detection by dependency-manifest content. Each entry pairs
# manifest glob(s) with the dependency tokens that signal a server/API framework.
# JS tokens are quoted (the manifest is JSON) so `"koa"` can't match inside a
# longer package name like `koa-router`.
MANIFEST_SCANS = (
    # JS/TS — package.json dependency names.
    (("package.json",),
     ('"express"', '"fastify"', '"koa"', '"@hapi/hapi"', '"@nestjs/core"', '"restify"')),
    # Go — module paths in go.mod.
    (("go.mod",),
     ("gin-gonic/gin", "labstack/echo", "gofiber/fiber", "go-chi/chi")),
    # Java/Kotlin — Spring / JAX-RS coordinates in Maven/Gradle build files.
    (("pom.xml", "build.gradle", "build.gradle.kts"),
     ("spring-boot-starter-web", "spring-webmvc", "spring-webflux", "javax.ws.rs", "jakarta.ws.rs")),
)


def _exposes_api(codebase: Codebase) -> bool:
    """True if any detector trips: a Python framework import, an API spec/IDL
    file, or a polyglot dependency-manifest framework token. Each Codebase scan
    is best-effort and non-raising, so this never raises."""
    if codebase.has_imports(PY_API_IMPORTS):
        return True
    if codebase.has_source_matching(SPEC_GLOBS):
        return True
    for globs, needles in MANIFEST_SCANS:
        if codebase.has_source_matching(globs, needles):
            return True
    return False


def probe_api_versioning_undecided(state: ProjectState, codebase: Codebase):
    """Fire when the repo exposes an API but no versioning decision is recorded.

    Suppressed when (a) the ``api_versioning_decided`` answer-store fact is truthy
    (a decision, a dated deferral, or "none — internal-only" was recorded), or
    (b) no exposed API is detected. Both reads are non-raising, and ``run_all_probes``
    additionally guards each probe, so a faulty scan fails open (no nudge) rather
    than blocking the sync — no broad ``except`` is needed in the probe body.

    Evidence is qualitative and detector-independent (it is hashed into the
    advisory id, so the id stays put regardless of which signal tripped) — the
    nudge is one stable advisory, not a churn of per-framework ids (D14).
    """
    if state.get(RESOLUTION_FACT):
        return []
    if not _exposes_api(codebase):
        return []
    return [
        AdvisoryCandidate(
            type=PROBE_TYPE,
            evidence=(
                "the product exposes an API but no versioning/deprecation decision "
                "is recorded (design_decisions.api_versioning_approach)",
            ),
            trigger_summary=(
                "This product exposes an API but records no versioning decision — "
                "choose a versioning + deprecation scheme (or a dated deferral, or "
                "\"none — internal-only\") and record it to silence this nudge"
            ),
            owner_action=(
                "Decide how this product's interface is allowed to change: versioned, free "
                "to break with notice, or internal-only where the question does not really "
                "arise. Any of those is a fine answer — leaving it unrecorded is the only "
                "one that costs something later, when a caller breaks and nobody agreed it could."
            ),
            recommended_action="/prawduct:methodology discovery",
            priority="info",
        )
    ]


def register() -> None:
    """Register the api-versioning probe. Idempotent (register_probe overwrites)."""
    register_probe(FEATURE, PROBE_TYPE, PROBE_VERSION, probe_api_versioning_undecided)
