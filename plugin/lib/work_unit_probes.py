"""Post-sync advisory probe for the work-unit binding's legacy window (#1050, MG3).

A repo whose plans predate claims still binds through the ``active_build_plan``
pointer or the conventional ``artifacts/build-plan.md`` — ``work_unit.resolve``
serves such a plan with its ``case`` naming the route, and only while no live
plan in the repo declares a ``branch:``. That window is temporary: it closes the
moment any plan claims a branch, and a later release retires the window itself.
A repo still inside it when it closes would find its gates disarmed, so the
binding says so every session through this advisory, which names the one
command that ends the window for that plan.

**The advisory is the binding's own reason.** ``trigger_summary`` is
``Binding.reason`` verbatim — the resolver is the one place that knows which
route answered — and the briefing does not print that sentence a second time
for a legacy binding (``briefing.render_briefing``). The remedy is concrete:
``prawduct-hook plan bind <plan> --branch <branch>`` for the plan and branch the
binding named.

**Evidence is keyed on the plan and route, not the branch**, so one dismissal
covers the plan across the branches a legacy repo checks out, and binding it
anywhere resolves the advisory everywhere — the plan stops being served by the
window on every branch the moment it claims one.

Inert in a scratch worktree, on a detached HEAD and on any checkout the window
does not serve: those bindings are not legacy. Registered at the composition
root (``lib/probe_families.register_all``).
"""

from __future__ import annotations

import shlex

from . import gitstate, work_unit
from .advisory_store import AdvisoryCandidate, Codebase, ProjectState, register_probe

FEATURE = "work-unit"
PROBE_VERSION = 1

def probe_plan_unbound_legacy(state: ProjectState, codebase: Codebase):
    """One advisory when this checkout's plan governs through the legacy window."""
    root = codebase.root
    branch = gitstate.current_branch(root)
    binding = work_unit.resolve(root, branch=branch)
    if not binding.is_legacy or binding.plan_path is None or not branch:
        return []
    rel = work_unit.repo_rel(binding.plan_path, root, within=".prawduct/artifacts")
    route = "the active_build_plan pointer" if binding.case == "legacy-pointer" else (
        "the conventional build-plan path"
    )
    return [
        AdvisoryCandidate(
            type=work_unit.LEGACY_ADVISORY_KEY,
            evidence=(
                f"{rel} declares no `branch:` and governs through {route}, a route "
                "being retired",
            ),
            trigger_summary=binding.reason or "",
            owner_action=(
                "Approve recording which branch this plan governs. Until it does, its "
                "reviews and gates stop applying the moment any other plan in this repo "
                "names its branch."
            ),
            # Spelled out rather than built from `work_unit.BIND_COMMAND` so the
            # actionability lint can read it; a test pins the two together.
            recommended_action=(
                f"prawduct-hook plan bind {shlex.quote(rel)} --branch {shlex.quote(branch)}"
            ),
            priority="warn",
        )
    ]


def register() -> None:
    """Register the legacy-binding probe. Idempotent (register_probe overwrites)."""
    register_probe(FEATURE, work_unit.LEGACY_ADVISORY_KEY, PROBE_VERSION, probe_plan_unbound_legacy)
