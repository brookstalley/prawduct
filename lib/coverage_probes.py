"""Post-sync advisory probes for structural-coverage — the forcing function that
keys off what a product *is* to require what it should therefore *have*.

The framework's other mechanisms are reactive: the Critic reviews diffs and the
sibling probes inspect existing files, so an artifact / structural characteristic /
norm that was *never created* is invisible to all of them. These probes make that
absence detectable — the coverage chain that a product with no strategy-class
artifacts is currently missing.

**Layer 1 — strategy-class artifact coverage (this module).** Five artifacts are
*universal*, expected of every product scaled to risk (data model, security model,
non-functional requirements, operational spec, observability strategy); two are
*characteristic-triggered* (an API contract when the product exposes a programmatic
interface; an architecture spec when it is multi-process / distributed).

**Coverage is satisfied by the artifact existing — full stop.** Its content may be
a real spec OR a deliberate ``(not relevant to this project — <reason>)`` stub: for a
tiny product that genuinely does not need a formal security model, a one-line stub
recording that conscious decision, where a reader will find it, IS coverage. There is
no separate suppression / decline list — one mechanism (does the file exist?), and
the decision lives in the artifact rather than in an inert scalar. The probe owns
*existence* (a conscious decision was recorded); the Critic and risk calibration own
*decision quality* (a high-risk product stubbing out its security model, or a repo
that recorded ``exposes_programmatic_interface`` stubbing out its api-contract, is a
contradiction they catch — not this probe's concern).

The nudge recurs gently: ``info`` priority, re-raised each session until a file
exists, dismissable per-clone. Resolution is cheap (author the spec, or write the
stub), which is what keeps a recurring nudge un-annoying.

Registered at the runtime composition root (``bin/prawduct-hook`` ``cmd_clear``),
like every sibling probe family. Read-only and fail-soft: a probe never executes
anything and never blocks session start.
"""

from __future__ import annotations

from .advisory_store import AdvisoryCandidate, Codebase, ProjectState, register_probe

FEATURE = "structural-coverage"
PROBE_VERSION = 1

# Universal strategy-class artifacts — expected of every product, scaled to risk
# (methodology/planning.md "Universal artifacts"). This module wires the universal
# arm to lock the primitive (read the artifacts dir + emit one stable advisory). The
# remaining universal artifacts and the two characteristic-triggered arms (api-contract
# ← exposes_programmatic_interface; architecture ← multi_process_distributed, read from
# classification.structural in the raw project-state.yaml) extend UNIVERSAL_ARTIFACTS /
# add the triggered table with no primitive change.
UNIVERSAL_ARTIFACTS: tuple[str, ...] = ("data-model.md",)

# Directory (relative to the product root) holding generated strategy-class artifacts.
_ARTIFACTS_REL = (".prawduct", "artifacts")


def _artifact_exists(codebase: Codebase, artifact_filename: str) -> bool:
    """True if the artifact file exists — content is irrelevant. A one-line
    ``(not relevant — <reason>)`` stub satisfies coverage exactly as a full spec
    does; the probe checks presence, the Critic judges whether the decision holds."""
    return (codebase.root.joinpath(*_ARTIFACTS_REL) / artifact_filename).is_file()


def _missing_universal(codebase: Codebase) -> list[str]:
    return [name for name in UNIVERSAL_ARTIFACTS if not _artifact_exists(codebase, name)]


def probe_strategy_artifact_missing(state: ProjectState, codebase: Codebase):
    """Fire when an expected strategy-class artifact file does not exist.

    One stable advisory regardless of *which* artifacts are missing: the
    id-affecting ``evidence`` is a fixed string (so the advisory keeps its identity
    across sessions as the missing set shrinks — :func:`compute_id` hashes evidence),
    while the volatile per-artifact detail lives in ``trigger_summary`` (not
    id-affecting), mirroring ``norm-registry-unratified``.
    """
    missing = _missing_universal(codebase)
    if not missing:
        return []
    return [
        AdvisoryCandidate(
            type="strategy-artifact-missing",
            evidence=(
                "one or more expected strategy-class artifacts do not exist",
            ),
            trigger_summary=(
                "Strategy-class artifact(s) expected but absent: "
                + ", ".join(missing)
                + ". Author each via /prawduct:methodology planning, or add a brief "
                + ".prawduct/artifacts/<name> recording why it is not relevant to this "
                + "product — a one-line '(not relevant — <reason>)' stub is a valid decision."
            ),
            recommended_action="/prawduct:methodology planning",
            priority="info",
        )
    ]


def register() -> None:
    """Register the structural-coverage probes. Idempotent (register_probe overwrites)."""
    register_probe(FEATURE, "strategy-artifact-missing", PROBE_VERSION, probe_strategy_artifact_missing)
