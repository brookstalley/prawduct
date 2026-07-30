"""Post-sync advisory probe for the committed install reference.

One probe: it nudges repair when a repo's ``.claude/settings.json`` install
reference has drifted from the contract prawduct writes
(``lib.migrate_plugin.INSTALL_REFERENCE`` — ``ref: "main"``, ``autoUpdate: true``).
A drifted reference means the repo is pinned to a fixed release ref, or opted out
of auto-update, and will therefore never receive another framework version.

**Why this needs an ambient nudge and not only a health check.**
``/prawduct:doctor`` Health Check #1 already asserts this exact contract, and it
is the right check — but it is operator-invoked, per repo, and the condition it
detects is *silent*. A pinned repo does not fail; it runs an old framework
forever while the session banner reports a version that never moves. Nobody runs
a health check on a repo that appears to be working. The gap is the trigger, not
the assertion, which is why this probe reuses doctor's contract rather than
inventing a second one.

**Why it is cause-agnostic.** Drift is checked as *state*, never as an event, so
it fires the same whether the pin arrived from a hand-edit, a stale clone, an
onboard against an old release, or the Claude Code CLI writing a machine-level
marketplace pin down into the repo (`#120`). A version-delta banner line would
fire once at the crossing and be lost if that session went elsewhere.

**Known limit, stated rather than implied.** The file that actually binds plugin
resolution is machine-level — ``~/.claude/plugins/known_marketplaces.json`` —
and it is outside ``${CLAUDE_PROJECT_DIR}``, which the hook runtime does not
leave (design §2). So this probe sees one end of a two-ended condition: the CLI
can write a machine-level pin down into a repo, and a repo that commits it can
re-seed the machine on open. Repairing only the repo end loses to the other. The
advisory therefore names both ends in its evidence and routes to
``/prawduct:doctor``, which is model-side and *can* read the machine-level file.

**Self-resolving.** Trigger and resolution are the same observable state — the
repo's own committed ``.claude/settings.json`` — so a teammate's committed fix
resolves it for every clone on next sync (§3.5), the same shape as
``gitignore_probes`` and ``upstream_probes``. No redundant ``project-state.yaml``
fact to drift from the file it describes.

Registered at the runtime composition root (``lib/probe_families.py``), not at
import time, so the infrastructure stays feature-agnostic.
"""

from __future__ import annotations

from .advisory_store import AdvisoryCandidate, Codebase, ProjectState, register_probe
from .migrate_plugin import install_reference_drift

FEATURE = "install-reference"
PROBE_VERSION = 1


def _fmt(value: object) -> str:
    """Render a contract value for operator-facing text (``None`` reads as absent)."""
    return "absent" if value is None else repr(value)


def _summary(drifted: list[dict]) -> str:
    """Human-facing one-liner naming the live drift and its consequence.

    The specifics live here, not in the evidence: evidence is hashed into the
    advisory id, so keeping it qualitative holds the id stable while a partial
    fix changes which fields are drifted (D14).
    """
    parts = [f"{d['field']} is {_fmt(d['actual'])} (contract: {_fmt(d['expected'])})" for d in drifted]
    return (
        "the committed prawduct install reference has drifted from the contract "
        f"({'; '.join(parts)}) — this repo will not receive framework updates"
    )


def probe_install_reference_drift(state: ProjectState, codebase: Codebase):
    """Fire when the present install reference disagrees with the contract.

    Inert when the reference matches, and inert when there is **no** prawduct
    entry at all — an un-onboarded repo has nothing to have drifted, and that
    absence is doctor's Health Check #1 finding rather than a session-start nag.
    """
    drift = install_reference_drift(codebase.root)
    if not drift["present"] or not drift["drifted"]:
        return []
    return [
        AdvisoryCandidate(
            type="contract-drift",
            evidence=(
                ".claude/settings.json extraKnownMarketplaces.prawduct does not match the "
                "install-reference contract (lib/migrate_plugin.py INSTALL_REFERENCE)",
                "a pinned or auto-update-disabled reference is silent: the repo keeps running "
                "an old framework and the session banner reports a version that never moves",
                "the machine-level ~/.claude/plugins/known_marketplaces.json is what actually "
                "binds plugin resolution and may carry the same pin — repairing only this repo "
                "can be undone by it (brookstalley/prawduct#120)",
            ),
            trigger_summary=_summary(drift["drifted"]),
            recommended_action="/prawduct:doctor",
            priority="info",
        )
    ]


def register() -> None:
    """Register the install-reference probe. Idempotent (register_probe overwrites)."""
    register_probe(FEATURE, "contract-drift", PROBE_VERSION, probe_install_reference_drift)
