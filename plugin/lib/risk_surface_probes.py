"""Post-sync advisory probe: a product with code under review that has never said
where a missed defect would cost it most.

One probe. ``risk_surfaces:`` in ``project-state.yaml`` is the product's own answer
to one discovery question — *where would a missed defect cost you most?* — and it
decides review depth for the life of the product: a change touching a listed path
gets the deeper review at any size (``methodology/discovery.md`` § Surface Risk
Surfaces owns the question and the capture format; ``lib.risk`` owns the reading).
Silence is silent *by design*: a product that declares nothing is reviewed at the
depth its diff size suggests, whatever the diff touches, so nothing ever fails and
nothing ever prompts. This probe is the prompt — asked once, in the product's
terms, and dismissable like every advisory.

**Absent is the only firing state.** ``lib.risk.read_declared_surfaces`` grades the
key three ways and each routes differently here:

- ``absent`` — the question was never answered. Fire.
- ``declared`` — answered, including ``risk_surfaces: []``, which ``discovery.md``
  defines as the deliberate opt-out. Silent. (``lib.risk.has_product_risk_declaration``
  reads ``[]`` as *no declaration*, which is the right answer for a consumer asking
  whether any surface is named and the wrong one for this ask, whose whole contract
  is that the opt-out silences it — so this probe reads the status, not that
  predicate.)
- ``unparseable`` — a key is there in a shape the reader does not parse. The
  question WAS answered, so the "please answer it" ask is wrong; silent here, and
  reported instead by ``coverage-status``'s risk-surfaces row, which grades that
  state degraded with the shape fix. The Critic's roster derivation also escalates
  on it out loud (``lib.risk.paths_touch_risk_surface``).

**Gated on judgeable work.** A risk surface is a path pattern over the product's
code, so the ask is owed only once there is code for it to name:
``gitstate._has_product_code`` — the single definition behind the
project-preferences CRITICAL and the discovery-capture nudge, reused rather than
re-derived — plus a ``project-state.yaml`` to record the answer in (its absence is
core-state breakage, a different check's finding). A docs-only or freshly
scaffolded repo stays silent.

**Fires once.** Evidence is fixed text carrying no path or count, so the advisory
keeps one identity across every repo and every session (``advisory_store.compute_id``
hashes the evidence): a second sync refreshes the same entry rather than opening a
new one, and a dismissal is sticky under that id (``advisory_store.reconcile``).
Writing the key resolves it on the next sync.

Read-only and fail-soft, never fail-silent: the probe writes nothing (the plugin
writes nothing into a governed repo except its own state), an unreadable state
file grades ``absent`` in the shared reader and so FIRES rather than vanishing, and
a probe that raises is reported and skipped by the advisory runner, never swallowed.

Registered at the composition root (``lib/probe_families.py``), like every sibling
probe family.
"""

from __future__ import annotations

from pathlib import Path

from .advisory_store import AdvisoryCandidate, Codebase, ProjectState, register_probe
from .core import YAML_ABSENT, YAML_UNPARSEABLE
from .risk import read_declared_surfaces

FEATURE = "review-depth"
PROBE_VERSION = 1

#: The advisory type, and the key it asks for — one home each.
PROBE_TYPE = "risk-surfaces-undeclared"
RISK_SURFACES_KEY = "risk_surfaces"

#: Where the question is asked and answered, cited by heading so a reader lands on
#: the section rather than the guide.
DISCOVERY_SECTION = "Surface Risk Surfaces"

STATUS_DECLARED = "declared"
STATUS_UNDECLARED = "undeclared"
STATUS_UNPARSEABLE = "unparseable"
STATUS_NOT_OWED = "not-owed"


def _state_path(root: Path) -> Path:
    return Path(root) / ".prawduct" / "project-state.yaml"


def judgeable_work_present(root: Path) -> bool:
    """True when this repo has code a risk surface could name, and a state file
    to record the answer in. Composes the existing predicates; defines no new one."""
    from . import gitstate  # deferred: keep module import light for non-probe callers

    root = Path(root)
    return _state_path(root).is_file() and gitstate._has_product_code(root)


def risk_surfaces_status(root: Path) -> str:
    """The one classification both surfaces read — the ambient probe and the
    ``coverage-status`` doctor row — so the two cannot disagree about a repo.

    ``not-owed`` (no judgeable work yet), ``declared`` (a key in a supported
    shape, ``[]`` included), ``undeclared`` (judgeable work and no key), or
    ``unparseable`` (a key in a shape the reader refuses).
    """
    root = Path(root)
    if not judgeable_work_present(root):
        return STATUS_NOT_OWED
    status, _items = read_declared_surfaces(_state_path(root), RISK_SURFACES_KEY)
    if status == YAML_ABSENT:
        return STATUS_UNDECLARED
    if status == YAML_UNPARSEABLE:
        return STATUS_UNPARSEABLE
    return STATUS_DECLARED


def probe_risk_surfaces_undeclared(state: ProjectState, codebase: Codebase):
    """Fire once when the product has code under review and has never said where
    its risk concentrates. Silent on any declared key (``[]`` included), on an
    unparseable one (answered, wrongly shaped — the doctor row's finding), and on
    a repo with no judgeable work yet.
    """
    if risk_surfaces_status(codebase.root) != STATUS_UNDECLARED:
        return []
    return [
        AdvisoryCandidate(
            type=PROBE_TYPE,
            evidence=(
                f"this repo has source code and .prawduct/project-state.yaml carries no "
                f"`{RISK_SURFACES_KEY}:` key, so it has never said where a missed defect "
                "would cost it most",
                "review depth is decided by the size of each change alone until it does: "
                "a small change to the riskiest code gets the cheaper review because it "
                "is small",
            ),
            trigger_summary=(
                "WHERE WOULD A MISSED DEFECT COST YOU MOST? This repo has code under "
                "review but has never said where its risk concentrates — auth, payments, "
                "a migration that rewrites data, a contract others build against, the "
                "safety interlock — so every change is reviewed at the depth its size "
                "suggests, and a two-line change to your riskiest code gets the cheap "
                f"review because it is small. Name those paths under `{RISK_SURFACES_KEY}:` "
                "in .prawduct/project-state.yaml and a change touching them gets the "
                f"deeper review at any size. `{RISK_SURFACES_KEY}: []` is the opt-out — "
                "write it only if there is genuinely no such place; it turns the check "
                f"off, and this reminder with it. The discovery guide's \"{DISCOVERY_SECTION}\" "
                "section has the question and the capture format."
            ),
            owner_action=(
                "Answer one question: where would a missed defect cost you most? I will "
                "turn the answer into path patterns for you to confirm before anything "
                "is recorded — or say there is no such place, and I will record the "
                "opt-out instead."
            ),
            recommended_action="/prawduct:methodology discovery",
            priority="warn",
        )
    ]


def register() -> None:
    """Register the risk-surfaces probe. Idempotent (register_probe overwrites)."""
    register_probe(FEATURE, PROBE_TYPE, PROBE_VERSION, probe_risk_surfaces_undeclared)
