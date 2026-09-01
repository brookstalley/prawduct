"""The api-design / versioning legs: is a decision recorded, and is it kept.

Two legs, and the distinction between them is the point.

**Presence** — :func:`probe_api_versioning_undecided`, the post-sync advisory
nudge for a product that exposes an API but has not recorded a versioning
decision. It is the retroactive, *don't-have-to-think-to-run-a-skill* twin of the
forward Critic gate (review-protocol.md Goal 2) and the on-demand
``/prawduct:doctor`` check #9 — same signal, three surfaces.

**Conformance** — :func:`conformance_departures`, which reads the declared public
surface and the recorded retention policy and reports removals the policy defers.
Presence was the only thing anything checked, and a recorded decision is not
adherence to it: v3.3.2 deleted ``build-index`` and ``user-prompt-submit`` from
``bin/prawduct-hook`` against a live recorded norm saying removal defers to a
major, broke every pre-3.3.2 consumer at session start, and forced an expedited
v3.3.3. Every guardrail was green, because "a decision exists" was true
throughout. The precedent remedy — ``tests/test_retired_hook_subcommands.py``
with its hand-maintained ``EVER_REGISTERED_HOOK_COMMANDS`` — closed the instance
for one surface and generalises to no consumer; this is the general form.

**Declaration-driven, and deliberately so.** The leg reads what the artifact
DECLARES (an inventory of members with stability tiers, and a retention line),
never the source. A checker that inferred the public surface from code would have
to be right about every language's notion of "public" before it could be right
about a removal, and would grade a product's API by prawduct's opinion of it.
Declaring the surface is the product's job; holding it to its own declaration is
this leg's.

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

import re
from dataclasses import dataclass

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
            recommended_action="/prawduct:methodology discovery",
            priority="info",
        )
    ]


def register() -> None:
    """Register the api-versioning probe. Idempotent (register_probe overwrites)."""
    register_probe(FEATURE, PROBE_TYPE, PROBE_VERSION, probe_api_versioning_undecided)


# ---------------------------------------------------------------------------
# Conformance: is the recorded decision KEPT
# ---------------------------------------------------------------------------

#: Stability tiers an inventory entry may declare (`templates/api-contract.md`
#: § Surface Inventory & Stability Tiers). Only the first two are a promise:
#: `experimental` is the tier whose whole meaning is "this may break", so
#: removing one is the policy working, not a departure from it.
STABILITY_TIERS = ("experimental", "stable", "deprecated")
PROMISED_TIERS = frozenset({"stable", "deprecated"})

#: One inventory entry: ``- `name` — stable`` (an em dash, a hyphen or a colon
#: separates them; the name is in a code span so a prose mention of the same word
#: elsewhere in the section is not an entry).
_INVENTORY_ENTRY = re.compile(
    r"^\s*[-*]\s+`([^`]+)`\s*(?:—|-|:)\s*(" + "|".join(STABILITY_TIERS) + r")\b",
    re.MULTILINE | re.IGNORECASE,
)

#: The recorded retention policy: ``Retention: removal defers to a major``.
#: Free text after the label, because the policy is the product's to write — this
#: only has to find it and decide whether it binds.
_RETENTION_LINE = re.compile(r"^\s*(?:[-*]\s+)?\**Retention:?\**\s*(.+?)\s*$", re.MULTILINE)

#: What makes a retention policy BINDING on removal. A policy that defers removal
#: to a major is the case with a conformance question; "none" and an open-ended
#: "we may remove things" have nothing to conform to, and this leg stays silent
#: rather than inventing a promise the product did not make.
_DEFERS_REMOVAL = re.compile(r"\bmajor\b", re.IGNORECASE)

#: Where the declaration lives. Matched on the heading text so a product may
#: retitle around it, and scoped so an inventory-shaped bullet in another section
#: is not read as a declaration.
_INVENTORY_HEADING = re.compile(r"^#{1,6}\s+.*\bSurface Inventory\b.*$", re.MULTILINE)
_ANY_HEADING = re.compile(r"^#{1,6}\s+", re.MULTILINE)

#: The template's authoring guidance lives in HTML comments and SHOWS the two
#: declaration forms by example. Reading those examples as declarations makes an
#: untouched template report a binding policy over a surface nobody declared —
#: a finding invented out of instructions. Comments are stripped before parsing,
#: which is also what makes "delete the entry" visible rather than expressible as
#: "comment the entry out".
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)

#: An unfilled placeholder — `<your rule>`, `<member>`. A template that has not
#: been authored has recorded nothing, and angle brackets are how every artifact
#: template in this repo says so.
_PLACEHOLDER = re.compile(r"^<[^>]*>$")


def _authored(text: str) -> str:
    """``text`` with its authoring comments removed."""
    return _HTML_COMMENT.sub("", text)


@dataclass(frozen=True)
class SurfaceMember:
    """One declared member of the public surface."""

    name: str
    tier: str


@dataclass(frozen=True)
class ConformanceDeparture:
    """A removal the recorded retention policy said would not happen yet.

    ``kind`` separates the two shapes, because they are fixed differently:
    ``removed`` — the member is still declared but is gone from the surface the
    diff leaves behind, so either restore it (inert if that is what the policy
    allows) or take the removal through the policy; ``undeclared`` — the member
    left the inventory itself, which retires the promise by editing the artifact
    that carries it, and that is the tell Goal 3's Normative authority names.
    """

    member: str
    tier: str
    kind: str
    policy: str


def _section(text: str, heading: re.Pattern[str]) -> str:
    """The body under the first heading ``heading`` matches, to the next heading."""
    found = heading.search(text)
    if found is None:
        return ""
    rest = text[found.end():]
    nxt = _ANY_HEADING.search(rest)
    return rest[: nxt.start()] if nxt else rest


def declared_surface(contract_text: str) -> tuple[SurfaceMember, ...]:
    """The members the API contract declares, with their stability tiers.

    Empty when the artifact declares no inventory — which is not a departure and
    not this leg's finding to make. An undeclared surface is the *presence* leg's
    subject, and reporting it here would file the same gap twice under two
    severities.
    """
    body = _section(_authored(contract_text), _INVENTORY_HEADING)
    return tuple(
        SurfaceMember(name=m.group(1).strip(), tier=m.group(2).lower())
        for m in _INVENTORY_ENTRY.finditer(body)
        if not _PLACEHOLDER.match(m.group(1).strip())
    )


def retention_policy(contract_text: str) -> str | None:
    """The recorded retention policy line, or ``None`` when none is recorded.

    ``None`` and "recorded but non-binding" are different answers and only one of
    them is silence-with-nothing-owed: an absent policy is the presence leg's
    WARNING, while a recorded "none — internal-only" is a decision this leg
    honours by having no departure to report.
    """
    for match in _RETENTION_LINE.finditer(_authored(contract_text)):
        value = match.group(1).strip()
        if value and not _PLACEHOLDER.match(value):
            return value
    return None


def conformance_departures(
    contract_text: str,
    present: set[str] | frozenset[str],
    *,
    previous_contract_text: str | None = None,
) -> tuple[ConformanceDeparture, ...]:
    """Declared members the diff removed against a policy that defers removal.

    Parameters
    ----------
    contract_text:
        The API contract artifact as the diff leaves it.
    present:
        The member names the reviewed tree still exposes. The caller gathers
        these — for `bin/prawduct-hook` that is its dispatchable subcommands —
        because what counts as "still exposed" is surface-specific and a library
        that guessed would be wrong for every surface but the one it was written
        against.
    previous_contract_text:
        The artifact as it stood BEFORE the diff, when the review has it. Without
        it a member deleted from the inventory in the same commit that deleted
        the member is invisible: the promise and the thing it protected vanish
        together, which is precisely the edit Goal 3 calls amending a norm to
        match your own code.

    Returns ``()`` when no policy is recorded, or when the recorded one does not
    defer removal — there is then nothing to depart from, and manufacturing a
    finding out of a product's decision not to promise anything is the opposite
    of force-the-decision-don't-mandate-the-answer.
    """
    policy = retention_policy(contract_text)
    if not policy or not _DEFERS_REMOVAL.search(policy):
        return ()

    current = declared_surface(contract_text)
    departures = [
        ConformanceDeparture(member=m.name, tier=m.tier, kind="removed", policy=policy)
        for m in current
        if m.tier in PROMISED_TIERS and m.name not in present
    ]

    if previous_contract_text is not None:
        still_declared = {m.name for m in current}
        departures.extend(
            ConformanceDeparture(
                member=m.name, tier=m.tier, kind="undeclared", policy=policy
            )
            for m in declared_surface(previous_contract_text)
            if m.tier in PROMISED_TIERS
            and m.name not in still_declared
            and m.name not in present
        )

    return tuple(departures)
