"""Post-sync advisory probes for structural-coverage — the forcing function that
keys off what a product *is* to require what it should therefore *have*.

The framework's other mechanisms are reactive: the Critic reviews diffs and the
sibling probes inspect existing files, so an artifact / structural characteristic /
norm that was *never created* is invisible to all of them. These probes make that
absence detectable — the coverage chain that a product with no strategy-class
artifacts is currently missing.

This module owns the chain's two staged nudges: **layer 0**
(:func:`probe_discovery_not_captured` — structural characteristics never recorded)
and **layer 1** (:func:`probe_strategy_artifact_missing` — characteristics recorded
but expected artifacts absent), complements on the shared staging predicate.

**Layer 1 — strategy-class artifact coverage.** The seven
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

**The whole probe stages behind layer 0.** It stays silent until the product has
recorded at least one structural characteristic
(:func:`structural_characteristics_recorded`) — the shared boundary predicate layer
0 fires on the negation of. A product that has not captured *what it is* gets the
upstream nudge (record your characteristics), not the downstream one (author the
artifacts those characteristics imply); firing both at once would double-nag. Once
characteristics are recorded, layer 0 clears and layer 1 takes over — the universal
arms always, the triggered arms per characteristic. This is why the universal arms,
though expected of every product, are gated too: "every product" means every
product that has told the framework it *is* a product by recording its
characteristics.

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

# The six structural characteristics discovery captures (methodology/discovery.md;
# templates/project-state.yaml classification.structural). The two triggered arms
# above name only the two that imply a specific artifact; this is the full set, so
# the staging predicate below can ask "were the characteristics captured at all?"
# rather than only about the two artifact-bearing ones.
STRUCTURAL_CHARACTERISTICS: tuple[str, ...] = (
    "has_human_interface",
    "runs_unattended",
    "exposes_programmatic_interface",
    "has_multiple_party_types",
    "handles_sensitive_data",
    "multi_process_distributed",
)

# Directory (relative to the product root) holding generated strategy-class artifacts.
_ARTIFACTS_REL = (".prawduct", "artifacts")

# Values that record a structural characteristic as ABSENT (not present): the
# template ``null`` sentinel plus explicit negatives. Any other recorded value — a
# nested attribute block (``consumers:`` / ``topology:`` …) or a truthy scalar —
# means the characteristic is present, so its triggered artifact is required.
_ABSENT_VALUES = frozenset({"null", "~", "none", "false", "no", "off", "0"})


def _artifact_exists(codebase: Codebase, artifact_filename: str) -> bool:
    """True if the artifact file exists — content is irrelevant. A one-line
    ``(not relevant — <reason>)`` stub satisfies coverage exactly as a full spec
    does; the probe checks presence, the Critic judges whether the decision holds."""
    return (codebase.root.joinpath(*_ARTIFACTS_REL) / artifact_filename).is_file()


def _state_path(codebase: Codebase) -> Path:
    return codebase.root / ".prawduct" / "project-state.yaml"


def _opens_nested_block(lines: list[str], key_idx: int, key_indent: int) -> bool:
    """True if the first non-blank, non-comment line after ``key_idx`` is indented
    deeper than ``key_indent`` — i.e. the characteristic key opens a nested attribute
    block (recording presence) rather than being a bare key with nothing under it."""
    for nxt in lines[key_idx + 1:]:
        if not nxt.strip() or nxt.lstrip().startswith("#"):
            continue
        return (len(nxt) - len(nxt.lstrip(" "))) > key_indent
    return False


def _structural_recorded_at(state_path: Path, characteristic: str) -> bool:
    """True when ``classification.structural.<characteristic>`` is recorded *present*
    in the raw ``project-state.yaml`` at ``state_path``.

    ``ProjectState`` is a column-0-only scan (no PyYAML — advisory_store.py), so a
    probe cannot read a nested ``classification.structural.*`` value through it;
    this walks the raw file the way ``gitstate._discovery_uncaptured`` does. Present
    = the key exists under ``structural`` and its value is a nested attribute block
    or a truthy scalar. Absent = the value is the template ``null`` sentinel or an
    explicit negative (:data:`_ABSENT_VALUES`), or the block / key / file is missing
    — all of which mean the characteristic is unrecorded (layer 0's nudge), so a
    triggered arm fails toward silence on anything it cannot read as clearly present.

    Indentation is tracked *relative to the levels the file actually uses* (the
    template's 2/4-space steps are the common case, not a requirement): the first
    indent seen under ``classification:`` is its direct-child level, and the first
    indent seen under ``structural:`` is the characteristic-key level. A file
    reformatted to 3- or 4-space steps with a characteristic recorded must read as
    recorded — a false "unrecorded" here would pin the layer-0 discovery advisory
    on a repo whose owner already answered.
    """
    try:
        lines = state_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return False
    in_classification = False
    child_indent: int | None = None  # direct-child level of classification (domain:, structural:, …)
    in_structural = False
    key_indent: int | None = None  # characteristic-key level under structural:
    for idx, line in enumerate(lines):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0:
            in_classification = line.startswith("classification:")
            child_indent = None
            in_structural = False
            key_indent = None
            continue
        if not in_classification:
            continue
        if child_indent is None:
            child_indent = indent
        if indent <= child_indent:
            # A sibling key of classification (domain:, structural:, risk_profile: …)
            # — we are inside structural only while this one is `structural:`. A line
            # shallower than the established child level is malformed relative to the
            # block; fail toward silence by leaving structural.
            in_structural = indent == child_indent and line.strip().startswith("structural:")
            key_indent = None
            continue
        if not in_structural:
            continue
        if key_indent is None:
            key_indent = indent
        if indent != key_indent:
            continue  # nested attribute lines of a characteristic block
        key, _, rest = line.strip().partition(":")
        if key != characteristic:
            continue
        value = rest.split("#", 1)[0].strip().strip("\"'")
        if value:
            return value.lower() not in _ABSENT_VALUES
        # Empty inline value: a nested attribute block records presence; a bare
        # key with nothing under it does not (fail toward silence).
        return _opens_nested_block(lines, idx, key_indent)
    return False


def _structural_recorded(codebase: Codebase, characteristic: str) -> bool:
    """``Codebase`` wrapper over :func:`_structural_recorded_at` (reads the
    codebase's own ``project-state.yaml``). The triggered arms call through here."""
    return _structural_recorded_at(_state_path(codebase), characteristic)


def structural_characteristics_recorded(state_path: Path) -> bool:
    """True when the product has recorded *at least one* structural characteristic
    present in ``classification.structural``.

    This is the **shared staging boundary** between layer 0
    (:func:`probe_discovery_not_captured`) and layer 1 (the strategy-artifact
    probe). Layer 0 fires on its *negation*; layer 1 speaks only on its truth — so
    exactly one layer nudges a given product (one actionable nudge at a time;
    docs/norms.md § Enforcement). Both sides key off THIS predicate rather than each
    re-deciding "were characteristics captured?", so the boundary can't drift
    (transcription across surfaces flattens quantifiers).

    "Recorded" is defined as ≥1 characteristic present, not all six answered,
    because the template default is ``null`` for every characteristic and ``null``
    doubles as the "not applicable" answer — so "all six non-null" is unreachable for
    any real product (every product leaves some characteristic inapplicable). ≥1
    present is the tractable floor: an all-``null`` (or absent) block reads as
    unrecorded — the template-default / never-captured state layer 0 owns — while a
    block that records even one characteristic reads as captured, and layer 1 takes
    over. A stricter "answered" sentinel distinct from ``null`` is a discovery-schema
    change out of this probe's scope.
    """
    return any(
        _structural_recorded_at(state_path, characteristic)
        for characteristic in STRUCTURAL_CHARACTERISTICS
    )


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


def missing_expected_artifacts(codebase: Codebase) -> list[tuple[str, str | None]]:
    """The expected-but-absent strategy-class artifacts as ``(filename,
    characteristic)`` pairs — ``characteristic`` is ``None`` for a universal
    artifact and the triggering flag for a characteristic-triggered one.

    This is the coverage expectation table applied to one codebase, and it is the
    single answer to "what does this product owe?" shared by three surfaces: the
    layer-1 probe (which nudges), the ``coverage-status`` doctor check (which
    reports), and the ``coverage-scaffold`` helper (which drops stubs). Homing the
    computation here keeps the table from being transcribed across those surfaces
    (transcription flattens quantifiers). Universal artifacts are listed first, then
    the triggered ones, so every consumer renders the missing set in one order.

    Independent of the layer-0/1 staging gate: it reports the raw expected set
    (universal always; a triggered artifact only when its characteristic is recorded
    present), leaving *whether to nudge yet* to :func:`probe_strategy_artifact_missing`.
    So the scaffold helper can offer the universal stubs even before characteristics
    are recorded, while the probe still holds its nudge for layer 0.
    """
    return [(name, None) for name in _missing_universal(codebase)] + [
        (name, characteristic) for name, characteristic in _missing_triggered(codebase)
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

    **Staging gate.** The whole probe stays silent until the product records at
    least one structural characteristic (:func:`structural_characteristics_recorded`).
    Until then a product has not yet captured *what it is*, so requiring the
    artifacts *what it is* would imply is premature — that upstream gap is layer 0's
    nudge (discovery-not-captured), and firing both layers at once would double-nag a
    fresh product. Once characteristics are recorded, layer 0 clears and this probe
    takes over: the universal arms fire regardless of *which* characteristics, the
    triggered arms per their recorded characteristic.
    """
    if not structural_characteristics_recorded(_state_path(codebase)):
        return []
    missing = missing_expected_artifacts(codebase)
    if not missing:
        return []
    listed = ", ".join(
        name if characteristic is None else f"{name} (required — {characteristic} recorded)"
        for name, characteristic in missing
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


def probe_discovery_not_captured(state: ProjectState, codebase: Codebase):
    """Layer 0 of the structural-coverage chain — discovery not captured.

    Fires when the repo shows product-definition work (code OR docs markdown) but
    ``classification.structural`` records no characteristic present — the product
    has not told governance what it *is*, so rigor can't be calibrated, the
    coverage chain stays blind, and requiring the artifacts those characteristics
    would imply is premature (that's layer 1, staged behind this via the shared
    predicate :func:`structural_characteristics_recorded` — exactly one of the two
    speaks). Two variants share one advisory identity (fixed ``evidence``; the
    variant lives in ``trigger_summary``): discovery never ran (both template
    sentinels still null — ``gitstate._discovery_uncaptured``), or discovery ran
    but the structural characteristics were never recorded.

    Delivered through the advisory store rather than a hard session-start print so
    it is dismissible per-clone (``/prawduct:advisory dismiss``) — a repo whose
    owner considers discovery settled can decline the nudge without editing state,
    while the default remains a recurring, prominent (``warn``-priority) prompt.
    Gated on product-definition work so a freshly-scaffolded empty repo stays
    silent; fail-soft like every probe (a scan failure reads as "no work").
    """
    from . import gitstate  # deferred: keep module import light for non-probe callers

    state_path = _state_path(codebase)
    if not state_path.is_file():
        return []
    if not gitstate._has_product_definition_work(codebase.root):
        return []
    if structural_characteristics_recorded(state_path):
        return []
    if gitstate._discovery_uncaptured(state_path):
        summary = (
            "DISCOVERY NOT CAPTURED: .prawduct/project-state.yaml has no classification or "
            "product definition, but this repo has product work (code and/or docs/). Until "
            "discovery is captured, governance can't calibrate rigor and the build gates "
            "won't engage. Discovery RECONCILES existing requirements/architecture/code — "
            "it reads what exists and backfills project-state.yaml rather than starting over."
        )
    else:
        summary = (
            "DISCOVERY NOT CAPTURED: .prawduct/project-state.yaml does not record this product's "
            "structural characteristics (none present in classification.structural), but this "
            "repo has product work (code and/or docs/). Structural characteristics decide which "
            "strategy-class artifacts the product needs, so until they're captured governance "
            "can't calibrate rigor and the coverage chain stays blind. Discovery RECONCILES "
            "existing material — it backfills the characteristics rather than starting over."
        )
    return [
        AdvisoryCandidate(
            type="discovery-not-captured",
            evidence=(
                "product-definition work present but no structural characteristic recorded",
            ),
            trigger_summary=summary,
            recommended_action="/prawduct:methodology discovery",
            priority="warn",
        )
    ]


def register() -> None:
    """Register the structural-coverage probes. Idempotent (register_probe overwrites)."""
    register_probe(FEATURE, "strategy-artifact-missing", PROBE_VERSION, probe_strategy_artifact_missing)
    register_probe(FEATURE, "discovery-not-captured", PROBE_VERSION, probe_discovery_not_captured)
