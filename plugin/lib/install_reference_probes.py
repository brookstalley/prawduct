"""Post-sync advisory probe for the committed install reference.

One probe: it nudges repair when a repo's ``.claude/settings.json`` install
reference has drifted from the contract prawduct writes
(``lib.migrate_plugin.INSTALL_REFERENCE`` — ``ref: "main"``, ``autoUpdate: true``).
A drifted reference means the repo commits a pin to a fixed release ref, or an
opt-out of auto-update, and so hands that state to every fresh clone of it. See
"Known limit" below for what it does *not* mean: on a machine that has already
resolved the plugin, the committed entry is inert.

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
onboard against an old release, or an external tool that manages
``.claude/settings.json`` (a session manager, a dotfile sync, a template repo).
Naming a writer is not required to act on the state, which is the point — the
field case in `#120` was misattributed at first, and the probe was correct
throughout regardless. A version-delta banner line would fire once at the
crossing and be lost if that session went elsewhere.

**Known limit, stated rather than implied.** This probe reads the repo's
committed ``.claude/settings.json``. What actually binds plugin resolution at
runtime is machine-level — ``~/.claude/plugins/known_marketplaces.json`` —
outside ``${CLAUDE_PROJECT_DIR}``, which the hook runtime does not leave
(design §2). The two are **decoupled**, which was measured rather than assumed
(`#120`): a repo whose committed reference still read ``ref: v2.1.5`` ran a
clean v3.2.2 session, because the configured machine resolved the plugin and
the repo entry never got a vote.

So the limit is a **false negative, not a coupling**: a stranded machine whose
repos all carry a correct reference produces no advisory here, because the
stranding is not in anything this probe can see. What a drifted committed
reference does cost is the *next* clone — it is what a fresh checkout or a new
machine seeds from, which is `/prawduct:doctor` Health Check #1's own stated
rationale ("contributors won't get governance on clone"). That is why the
advisory still routes to doctor, which is model-side and *can* read the
machine-level file: the two halves are complementary checks, not two ends of
one loop.

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

    The consequence clause claims only what was measured (see module docstring):
    a fresh clone is stranded. It deliberately does **not** say "this repo will
    not receive framework updates" — that is false on a machine which already
    resolved the plugin, and it is the machine most operators read this on, so
    the overstatement would be discovered as a wrong nudge rather than a true one.
    """
    parts = [f"{d['field']} is {_fmt(d['actual'])} (contract: {_fmt(d['expected'])})" for d in drifted]
    return (
        "the committed prawduct install reference has drifted from the contract "
        f"({'; '.join(parts)}) — a fresh clone of this repo would be stranded at that version"
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
                "the condition is silent wherever it does bite: a clone seeded from this "
                "reference does not fail, its gates all pass, and its session banner reports "
                "a version that simply never moves",
                "a drifted committed reference is inert on a machine already configured — the "
                "machine-level ~/.claude/plugins/known_marketplaces.json is what binds plugin "
                "resolution — but it is what a fresh clone or a new machine seeds from, so the "
                "drift travels to the next person even when it costs you nothing here",
            ),
            trigger_summary=_summary(drift["drifted"]),
            recommended_action="/prawduct:doctor",
            priority="info",
        )
    ]


def register() -> None:
    """Register the install-reference probe. Idempotent (register_probe overwrites)."""
    register_probe(FEATURE, "contract-drift", PROBE_VERSION, probe_install_reference_drift)
