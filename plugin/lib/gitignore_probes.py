"""Post-sync advisory probe for the session-file ``.gitignore`` contract.

One probe: it nudges reconciliation when a repo's ``.gitignore`` has drifted from
the framework's session-file contract (``lib.core.GITIGNORE_ENTRIES`` /
``RETIRED_GITIGNORE_ENTRIES`` / ``MANAGED_FILES``). Drift is **cause-agnostic** —
it arises from a prawduct upgrade that extended the contract, a fresh clone, a
hand-edited ``.gitignore``, or a botched onboard — because the probe checks the
*drifted state itself*, not the upgrade event. That is deliberately stronger than
a version-delta banner line, which fires once at the crossing and is lost if the
first post-upgrade session is spent on other work.

**Why an advisory and not an auto-fix.** ``.gitignore`` is a COMMITTED file, and
the session hooks never edit tracked files (the no-noise guarantee — see the
defensive untracker in ``bin/prawduct-hook``). An auto-write would create an
unstaged diff the user did not ask for that could ride into an unrelated commit.
The advisory keeps the human in the loop at near-zero cost; the recommended
action ``prawduct-hook update-gitignore`` is the idempotent fixer, with
``/prawduct:doctor`` offered as the fuller-check alternative.

**Self-resolving, and why resolution reads ``.gitignore`` (not ``project-state.yaml``).**
§7.1 of the advisory spec defaults resolution to a ``project-state.yaml`` fact,
to decouple "the codebase still has SDK imports" (a permanent feature) from "the
project has been characterized" (the answer). That guard does not apply here: the
trigger is the *fixable* drift, which genuinely disappears when reconciled, and
the reconciled ``.gitignore`` is itself a COMMITTED, SHARED fact — so a teammate's
committed fix resolves the advisory for every clone on next sync, exactly the role
§3.5 assigns to the answer store. Reading resolution from ``.gitignore`` needs no
redundant ``project-state.yaml`` fact and cannot drift from the file it describes.
This mirrors ``upstream_probes.py`` (trigger and resolution are the same observable
state). The fire condition is EXACTLY ``update_gitignore``'s ``modified`` condition
— both read :func:`lib.core.gitignore_contract_drift` — so the nudge can never
outlive the fix.

Registered at the runtime composition root (``bin/prawduct-hook`` ``cmd_clear``),
not at import time, so the infrastructure stays feature-agnostic — the same
pattern as ``lib/backlog_probes.py`` and ``lib/upstream_probes.py``.
"""

from __future__ import annotations

from .advisory_store import AdvisoryCandidate, Codebase, ProjectState, register_probe
from .core import gitignore_contract_drift

FEATURE = "gitignore"
PROBE_VERSION = 1


def _summary(missing: list[str], incorrectly_ignored: list[str]) -> str:
    """Human-facing one-liner naming the live drift counts.

    The counts live here (not in the evidence) so the advisory id stays stable as
    the drift set shrinks under a partial fix — see :func:`probe_gitignore_contract_drift`.

    **States the condition, not the fix.** This line is relayed into conversation, so
    a "run prawduct-hook update-gitignore" tail — which it used to carry — put a
    framework binary in front of the one reader who never runs one, and did it in the
    sentence they read first. The fix now has its two proper homes: what the owner
    decides (`owner_action`) and what the runtime executes (`recommended_action`).
    """
    parts: list[str] = []
    if missing:
        noun = "entry" if len(missing) == 1 else "entries"
        parts.append(f"{len(missing)} session {noun} missing")
    if incorrectly_ignored:
        noun = "file" if len(incorrectly_ignored) == 1 else "files"
        parts.append(f"{len(incorrectly_ignored)} committed {noun} wrongly ignored")
    return (
        ".gitignore has drifted from the prawduct session-file contract "
        f"({'; '.join(parts)})"
    )


def probe_gitignore_contract_drift(state: ProjectState, codebase: Codebase):
    """Fire when ``.gitignore`` diverges from the session-file contract.

    Inert when it already satisfies the contract — the steady state for every
    correctly-onboarded repo (including this framework repo, which dogfoods the
    contract). Evidence is qualitative and count-independent (it is hashed into
    the advisory id, so the id stays put as the drift set changes under a partial
    fix — D14); the live counts live in the summary.
    """
    drift = gitignore_contract_drift(codebase.root)
    missing = drift["missing"]
    incorrectly_ignored = drift["incorrectly_ignored"]
    if not missing and not incorrectly_ignored:
        return []
    return [
        AdvisoryCandidate(
            type="contract-drift",
            evidence=(
                ".gitignore does not satisfy the prawduct session-file contract "
                "(lib/core.py GITIGNORE_ENTRIES / RETIRED_GITIGNORE_ENTRIES)",
            ),
            trigger_summary=_summary(missing, incorrectly_ignored),
            # The owner is not asked to run the fixer. `prawduct-hook` is a framework
            # binary the runtime invokes; put it in front of a person and it reads as
            # an instruction to open a terminal and type something they have never
            # heard of. What is genuinely theirs is the approval, because the file is
            # committed — which is also why this is an advisory and not an auto-fix.
            owner_action=(
                "Say go — this reconciles a committed file, adding the entries prawduct "
                "needs and clearing ones that wrongly hide tracked files, so you will see "
                "a diff to review before anything is staged."
            ),
            recommended_action="prawduct-hook update-gitignore",
            alternative_actions=("/prawduct:doctor",),
            priority="info",
        )
    ]


def register() -> None:
    """Register the gitignore-contract probe. Idempotent (register_probe overwrites)."""
    register_probe(FEATURE, "contract-drift", PROBE_VERSION, probe_gitignore_contract_drift)
