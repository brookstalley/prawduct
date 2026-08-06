"""Post-sync advisory probe for the upstream dependency intake policy.

One probe: the ambient migration nudge for a product that has recorded no terms
on which upstream code enters it. It is the retroactive, *don't-have-to-think-to-
run-a-skill* twin of the forward Critic gate (Goal 2's `**Dependency change:**`
check) and the on-demand ``/prawduct:doctor`` Health Check #15 — same signal,
three surfaces. The terms themselves are stated once, in
``docs/upstream-dependency-policy.md``; nothing here restates them.

**Force the decision, don't mandate the answer.** The nudge is ``info``-priority
and dismissable, and a product that incorporates no upstream code silences it
with one recorded fact. Resolution is the committed answer-store fact, so a
teammate's recorded decision clears the advisory for everyone on next sync.

**Why there is no ``Codebase`` scan — this is the design, not an omission.**
Every other migration nudge asks "does this product have the thing?" before
asking "has it decided about the thing?". This one asks only the second question,
because the first has no honest detector. The trigger is universal: the policy
governs any artifact whose release someone else controls, independent of how it
is delivered, so *every* product either incorporates upstream code or records in
one line that it does not. A scan would have to decide which files constitute an
intake surface — and any such list under-enumerates by construction, which is the
precise failure the policy exists to reject. It would also quietly re-scope the
nudge to the delivery mechanisms the list happened to know about, making an
unrecognised one read as "no upstream code here" rather than "unexamined".

So the probe reads one fact and nothing else. **Do not add a scan here.** The
enumeration this feature does need is agent-performed, where reading beats
matching: ``/prawduct:doctor`` Health Check #15(b) walks the repo's real intake
surfaces and reports conformant / drifted / **unclassified**, and unclassified is
a finding rather than a blank. That check is also the one that can see
``design_decisions.upstream_dependency_policy`` itself — ``ProjectState`` exposes
only top-level scalars, so the flat fact below is all a probe can read. Both
mismatches between the two are therefore #15's to report, not this probe's: a
fact set over a still-null block (decided in name only), and a filled block whose
flat mirror was never set — which keeps this nudge firing at an owner who has in
fact decided. Setting the flat fact is the documented resolution step on every
surface that asks for the decision; widening the probe to guess at nested state
is not the fix, because it can only see what the answer store exposes.

Registered at the composition root (``lib/probe_families.register_all``), not at
``advisory_store`` import time, so the infrastructure stays feature-agnostic —
the same pattern as ``lib/api_versioning_probes.py`` and ``lib/norm_probes.py``.
"""

from __future__ import annotations

from .advisory_store import AdvisoryCandidate, Codebase, ProjectState, register_probe

FEATURE = "upstream-dependency-policy"
PROBE_TYPE = "dependency-policy"
PROBE_VERSION = 1

# The answer-store fact (top-level scalar; templates/project-state.yaml documents
# it). Truthy = intake terms, an explicit deferral, or "none — no upstream code"
# was recorded → suppress. Top-level on purpose: load_project_state reads only
# column-0 scalars, so the probe cannot consult the nested decision block — this
# flat mirror is the readable resolution signal.
RESOLUTION_FACT = "upstream_dependency_policy_decided"


def probe_dependency_policy_undeclared(state: ProjectState, codebase: Codebase):
    """Fire when no upstream intake policy is recorded.

    ``codebase`` is accepted because the registry calls every probe with it, and
    deliberately unread — see the module docstring for why this probe has no
    detector and why adding one would be a regression rather than a fix.

    It performs **no I/O**: the single read is an in-memory lookup in the already-
    loaded answer store, so there is no read error here to fail open on, and no
    broad ``except`` to waive (``run_all_probes`` remains the backstop for every
    probe). Where the failure does live is upstream — a missing or unreadable
    ``project-state.yaml`` degrades to an empty answer store, and this probe then
    *fires* rather than going quiet. That is the right direction for a nudge: it
    can ask again, but it must never conclude "decided" from a state it could not
    read.

    Evidence is a single fixed citation: the trigger is universal, so there is
    nothing repo-specific to cite and the advisory id is the same everywhere,
    which is what lets a dismissal stay dismissed.
    """
    if state.get(RESOLUTION_FACT):
        return []
    return [
        AdvisoryCandidate(
            type=PROBE_TYPE,
            # This string is an IDENTITY KEY, not prose: `advisory_store.compute_id`
            # hashes the evidence list, so editing it mints a new id and every repo
            # that dismissed this advisory sees it return. Say anything that needs
            # to change in `trigger_summary`, which is rendered and id-free.
            evidence=(
                "no upstream dependency intake policy is recorded "
                "(design_decisions.upstream_dependency_policy)",
            ),
            trigger_summary=(
                "This product records no terms for how upstream code enters it — "
                "decide the terms on which someone else's release becomes yours "
                "(or record that none does) and the nudge goes quiet"
            ),
            recommended_action=(
                "/prawduct:methodology discovery (record the terms) — or "
                "/prawduct:doctor Health Check #15 (what this repo's intake "
                "surfaces do today)"
            ),
            priority="info",
        )
    ]


def register() -> None:
    """Register the dependency-policy probe. Idempotent (register_probe overwrites)."""
    register_probe(FEATURE, PROBE_TYPE, PROBE_VERSION, probe_dependency_policy_undeclared)
