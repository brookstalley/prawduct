"""Post-sync advisory probes for structural-coverage — the forcing function that
keys off what a product *is* to require what it should therefore *have*.

The framework's other mechanisms are reactive: the Critic reviews diffs and the
sibling probes inspect existing files, so an artifact / structural characteristic /
norm that was *never created* is invisible to all of them. These probes make that
absence detectable — the coverage chain that a product with no strategy-class
artifacts is currently missing.

**Layer 1 — strategy-class artifact coverage (this module).** The seven
strategy-class artifacts (``docs/norms.md`` § Where Norms Live) split into two
arms:

- *Universal* (:data:`UNIVERSAL_ARTIFACTS`) — expected of every product scaled to
  risk: data model, security model, non-functional requirements, operational
  spec, observability strategy. These five are the **intersection** of
  ``methodology/planning.md``'s universal artifacts (nine — which also include
  product brief, project preferences, test specifications, dependency manifest,
  none of them strategy-class) with the seven strategy-class artifacts; naming
  planning.md's "Universal artifacts" section alone would over-claim, since only
  five of its nine are strategy-class.
- *Characteristic-triggered* (:data:`TRIGGERED_ARTIFACTS`) — required only when a
  recorded structural characteristic implies them: an API contract when the
  product records ``exposes_programmatic_interface``; an architecture spec when it
  records ``multi_process_distributed``. The two remaining strategy-class
  artifacts (architecture, api-contract) are exactly planning.md's
  structurally-triggered ones — so universal ∪ triggered = the full seven.

A triggered arm reads only the *recorded* characteristic in
``classification.structural`` (never a filesystem heuristic): if the
characteristic is unrecorded, requiring its artifact would be guessing, and that
gap — a product whose characteristics were never captured — is layer 0's nudge
(discovery not captured), not this probe's. So a triggered arm fails toward
silence on anything it cannot read as clearly present.

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

from pathlib import Path

from .advisory_store import AdvisoryCandidate, Codebase, ProjectState, register_probe

FEATURE = "structural-coverage"
PROBE_VERSION = 1

# Universal strategy-class artifacts — expected of every product, scaled to risk.
# The intersection of methodology/planning.md's universal artifacts with the seven
# strategy-class artifacts (docs/norms.md § Where Norms Live); see the module
# docstring for why the intersection, not planning.md's list, is the authority.
UNIVERSAL_ARTIFACTS: tuple[str, ...] = (
    "data-model.md",
    "security-model.md",
    "nonfunctional-requirements.md",
    "operational-spec.md",
    "observability-strategy.md",
)

# Characteristic-triggered strategy-class artifacts — each required only when its
# structural characteristic is *recorded present* in classification.structural
# (methodology/planning.md "Structurally-triggered artifacts"; the characteristic
# names are the discovery flags in templates/project-state.yaml). Read from the raw
# project-state.yaml, never inferred from surface markers in the tree
# (detection of structural characteristics must not rely on mechanistic markers).
TRIGGERED_ARTIFACTS: tuple[tuple[str, str], ...] = (
    ("api-contract.md", "exposes_programmatic_interface"),
    ("architecture.md", "multi_process_distributed"),
)

# The full strategy-class set = universal ∪ triggered (docs/norms.md § Where Norms
# Live). This module owns the coverage expectation table, so it is the single home
# for the filename list; lib/norm_probes.py imports this constant rather than
# transcribing it (transcription across surfaces flattens quantifiers).
STRATEGY_CLASS_ARTIFACTS: tuple[str, ...] = UNIVERSAL_ARTIFACTS + tuple(
    name for name, _ in TRIGGERED_ARTIFACTS
)

# Directory (relative to the product root) holding generated strategy-class artifacts.
_ARTIFACTS_REL = (".prawduct", "artifacts")

# Values that record a structural characteristic as ABSENT (not present): the
# template ``null`` sentinel plus explicit negatives. Any other recorded value — a
# nested attribute block (``consumers:`` / ``topology:`` …) or a truthy scalar —
# means the characteristic is present, so its triggered artifact is required.
_ABSENT_VALUES = frozenset({"null", "~", "none", "false", "no", "off"})


def _artifact_exists(codebase: Codebase, artifact_filename: str) -> bool:
    """True if the artifact file exists — content is irrelevant. A one-line
    ``(not relevant — <reason>)`` stub satisfies coverage exactly as a full spec
    does; the probe checks presence, the Critic judges whether the decision holds."""
    return (codebase.root.joinpath(*_ARTIFACTS_REL) / artifact_filename).is_file()


def _state_path(codebase: Codebase) -> Path:
    return codebase.root / ".prawduct" / "project-state.yaml"


def _opens_nested_block(lines: list[str], key_idx: int) -> bool:
    """True if the first non-blank, non-comment line after ``key_idx`` is indented
    deeper than four spaces — i.e. the characteristic key opens a nested attribute
    block (recording presence) rather than being a bare key with nothing under it."""
    for nxt in lines[key_idx + 1:]:
        if not nxt.strip() or nxt.lstrip().startswith("#"):
            continue
        return (len(nxt) - len(nxt.lstrip(" "))) > 4
    return False


def _structural_recorded(codebase: Codebase, characteristic: str) -> bool:
    """True when ``classification.structural.<characteristic>`` is recorded *present*
    in the raw ``project-state.yaml``.

    ``ProjectState`` is a column-0-only scan (no PyYAML — advisory_store.py), so a
    probe cannot read a nested ``classification.structural.*`` value through it;
    this walks the raw file the way ``gitstate._discovery_uncaptured`` does. Present
    = the key exists under ``structural`` and its value is a nested attribute block
    or a truthy scalar. Absent = the value is the template ``null`` sentinel or an
    explicit negative (:data:`_ABSENT_VALUES`), or the block / key / file is missing
    — all of which mean the characteristic is unrecorded (layer 0's nudge), so a
    triggered arm fails toward silence on anything it cannot read as clearly present.
    """
    try:
        lines = _state_path(codebase).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return False
    in_classification = False
    in_structural = False
    for idx, line in enumerate(lines):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0:
            in_classification = line.startswith("classification:")
            in_structural = False
            continue
        if not in_classification:
            continue
        if indent == 2:
            # A sibling key of classification (domain:, structural:, risk_profile: …)
            # — we are inside structural only while this one is `structural:`.
            in_structural = line.strip().startswith("structural:")
            continue
        if not in_structural or indent != 4:
            continue  # 6-space nested attribute lines, or keys outside structural
        key, _, rest = line.strip().partition(":")
        if key != characteristic:
            continue
        value = rest.split("#", 1)[0].strip().strip("\"'")
        if value:
            return value.lower() not in _ABSENT_VALUES
        # Empty inline value: a nested attribute block records presence; a bare
        # key with nothing under it does not (fail toward silence).
        return _opens_nested_block(lines, idx)
    return False


def _missing_universal(codebase: Codebase) -> list[str]:
    return [name for name in UNIVERSAL_ARTIFACTS if not _artifact_exists(codebase, name)]


def _missing_triggered(codebase: Codebase) -> list[tuple[str, str]]:
    """``(artifact, characteristic)`` pairs whose characteristic is recorded present
    but whose artifact file is absent."""
    return [
        (name, characteristic)
        for name, characteristic in TRIGGERED_ARTIFACTS
        if _structural_recorded(codebase, characteristic) and not _artifact_exists(codebase, name)
    ]


def probe_strategy_artifact_missing(state: ProjectState, codebase: Codebase):
    """Fire when an expected strategy-class artifact file does not exist.

    Universal artifacts are always expected; a characteristic-triggered artifact
    is expected only when its structural characteristic is recorded present. One
    stable advisory regardless of *which* artifacts are missing: the id-affecting
    ``evidence`` is a fixed string (so the advisory keeps its identity across
    sessions as the missing set shrinks — :func:`compute_id` hashes evidence),
    while the volatile per-artifact detail lives in ``trigger_summary`` (not
    id-affecting), mirroring ``norm-registry-unratified``. Each triggered artifact
    is annotated with the characteristic that requires it, so the reader sees why.
    """
    universal_missing = _missing_universal(codebase)
    triggered_missing = _missing_triggered(codebase)
    if not universal_missing and not triggered_missing:
        return []
    listed = ", ".join(
        universal_missing
        + [f"{name} (required — {characteristic} recorded)" for name, characteristic in triggered_missing]
    )
    return [
        AdvisoryCandidate(
            type="strategy-artifact-missing",
            evidence=(
                "one or more expected strategy-class artifacts do not exist",
            ),
            trigger_summary=(
                "Strategy-class artifact(s) expected but absent: "
                + listed
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
