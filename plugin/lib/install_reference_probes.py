"""Post-sync advisory probes for the committed install reference.

Two probes. ``tripwire-missing`` (:func:`probe_tripwire_missing`) nudges adding
the unloaded-plugin tripwire hook to an onboarded repo that lacks it; it is not
part of the contract below, because the contract is compared leaf by leaf and a
hook list is not a leaf. The rest of this docstring is ``contract-drift``, which
nudges repair when a repo's ``.claude/settings.json`` has drifted
from the install contract prawduct writes — **every field of**
``lib.migrate_plugin.INSTALL_REFERENCE``, which is the authority for what the
contract *is*; no list in this docstring is (a transcribed list is exactly how
the check went stale once already — see
:func:`lib.migrate_plugin.install_reference_drift`). Drift looks like a pin to a
fixed release ref, an opt-out of auto-update, a repointed marketplace repo, or
prawduct disabled outright — **examples, not the set** — in any combination, and
the repo hands that state to every fresh clone of it. See "Known limit" below for what it does *not* mean:
on a machine that has already resolved the plugin, the committed entry is inert.

**Why this needs an ambient nudge and not only a health check.**
``/prawduct:doctor`` Health Check #1 already asserts this exact contract, and it
is the right check — but it is operator-invoked, per repo, and the condition it
detects is *silent*. A drifted repo does not fail, and on a configured machine
nothing here breaks today at all; it is a clone seeded from the drift that runs
an old framework while its banner reports a version that never moves. Nobody
runs a health check on a repo that appears to be working — and this one does
appear to be working, which is the whole difficulty. The gap is the trigger, not
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
rationale (the next clone seeds from it and has nothing to resolve the
install against). That is why the
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
from . import unloaded_tripwire
from .migrate_plugin import INSTALL_REFERENCE, PLUGIN_ID, install_reference_drift

FEATURE = "install-reference"
PROBE_VERSION = 1

#: The one contract field whose drift is not a *version* problem — governance is
#: off rather than pinned, so it earns a different consequence clause. Derived
#: from the contract's own key so it tracks a rename.
_ENABLED_PLUGINS_FIELD = f"enabledPlugins.{PLUGIN_ID}"


def _fmt(value: object) -> str:
    """Render a contract value for operator-facing text (``None`` reads as absent)."""
    return "absent" if value is None else repr(value)


def _summary(drifted: list[dict]) -> str:
    """Human-facing one-liner naming the live drift and its consequence.

    The specifics live here, not in the evidence: evidence is hashed into the
    advisory id, so keeping it qualitative holds the id stable while a partial
    fix changes which fields are drifted (D14).

    The consequence clause claims only what was measured (see module docstring):
    the cost lands on a fresh clone. It deliberately does **not** say "this repo
    will not receive framework updates" — that is false on a machine which
    already resolved the plugin, and it is the machine most operators read this
    on, so the overstatement would be discovered as a wrong nudge rather than a
    true one.

    Two consequences, because the contract covers two different harms and one
    sentence cannot honestly cover both: a drifted *version* strands the clone at
    that version, while ``enabledPlugins: false`` leaves it with no governance at
    all. When both drift, stranding is the more specific statement and is used.
    """
    parts = [f"{d['field']} is {_fmt(d['actual'])} (contract: {_fmt(d['expected'])})" for d in drifted]
    version_drifted = any(d["field"] != _ENABLED_PLUGINS_FIELD for d in drifted)
    consequence = (
        "a fresh clone of this repo would be stranded at that reference"
        if version_drifted
        else "a fresh clone of this repo would run with prawduct governance switched off"
    )
    return (
        "the committed prawduct install reference has drifted from the contract "
        f"({'; '.join(parts)}) — {consequence}"
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
                # Names the FILE, not a subtree of it: `enabledPlugins` is a top-level
                # sibling of `extraKnownMarketplaces`, so naming the latter read as a
                # claim about a subtree that matches exactly on an enabledPlugins-only
                # drift. Generalized rather than branched — evidence is hashed into the
                # advisory id, so it must stay drift-set-independent (D14).
                ".claude/settings.json does not match the install-reference contract "
                "(lib/migrate_plugin.py INSTALL_REFERENCE); the drifted fields are named "
                "in the summary above",
                "the condition is silent wherever it does bite: a clone seeded from this "
                "reference does not fail, its gates all pass, and its session banner reports "
                "a version that simply never moves",
                "a drifted committed reference is inert on a machine already configured — the "
                "machine-level ~/.claude/plugins/known_marketplaces.json is what binds plugin "
                "resolution — but it is what a fresh clone or a new machine seeds from, so the "
                "drift travels to the next person even when it costs you nothing here",
            ),
            trigger_summary=_summary(drift["drifted"]),
            # The owner line has to answer "why should I care, if nothing here is
            # broken?" — because on THIS machine nothing is (the comment on priority
            # below spells out why). The cost is borne by the next person to clone,
            # which is a thing only the person deciding whether to commit a fix can
            # weigh, and it is invisible from where they are sitting.
            owner_action=(
                "Say go — this edits a committed file, so you will see a diff to review "
                "before anything is staged. It changes nothing about how this machine "
                "runs; what it fixes is what a fresh clone or a new teammate's machine "
                "would set itself up from."
            ),
            # Doctor Health Check #1 asserts this whole contract — every field this
            # probe can fire on, `autoUpdate` included. That was not true when this
            # probe was written (HC#1 checked `enabledPlugins` and `ref` only), which
            # made `/prawduct:doctor` report healthy on the `autoUpdate: false` repos
            # this fires on. Kept as one contract in two places rather than two
            # contracts: if a field is added here, add it there.
            recommended_action="/prawduct:doctor",
            # `info`, deliberately — which since 2026-08-03 means relayed as ONE
            # COMPACT LINE rather than not relayed at all (the relay now covers every
            # priority and scales verbosity instead; `observability-strategy.md` § How
            # the owner actually learns). The priority is still right, and for the
            # same reason: the condition costs the CURRENT machine nothing — which
            # holds for every contract field, though for two reasons worth keeping
            # distinct:
            #   - marketplace/source/autoUpdate drift: measured decoupling from the
            #     machine-level file (see module docstring, #120).
            #   - `enabledPlugins: false`: not measured, and does not need to be — this
            #     probe only runs at all because the plugin IS loaded in this session,
            #     so a committed `false` is self-evidently not binding here.
            # It is also self-resolving and re-fires every session until someone commits
            # the fix — exactly the profile the compact form exists for; a nudge that
            # takes a paragraph every session about a cost they will not pay today is
            # the one that teaches them to skip the channel. Raise to `warn` only if the
            # decoupling is ever falsified in the other direction.
            priority="info",
        )
    ]


#: Why the tripwire matters, shared by both shapes of the advisory.
_TRIPWIRE_WHY = (
    "every other prawduct check is delivered by the plugin, so in a session "
    "that loads no plugin (a new Claude Code profile, a machine that never ran "
    "the install) only a project hook can say governance is off"
)
_TRIPWIRE_COST = (
    " — a session whose profile has no prawduct install for this repo would run "
    "ungoverned with nothing saying so"
)


def probe_tripwire_missing(state: ProjectState, codebase: Codebase):
    """Fire when an onboarded repo's settings lack the current unloaded-plugin
    tripwire hook (``lib/unloaded_tripwire.py``).

    The hook is what speaks in a session that loaded no prawduct plugin, and that
    session is exactly the one where this probe cannot run — so the nudge has to
    land here, in a session that did load it, for the hook to be there next time.
    Gated on the marketplace entry like the drift probe: a repo that never
    onboarded has nothing to add it to. A ``hooks`` shape the writer refuses
    fires too, with evidence naming the shape, because that repo is just as
    silent and no writer will fix it unasked.
    """
    if not install_reference_drift(codebase.root)["present"]:
        return []
    found, reason = unloaded_tripwire.read_settings(codebase.root)
    if found == unloaded_tripwire.PRESENT:
        return []
    if found == unloaded_tripwire.MALFORMED:
        return [
            AdvisoryCandidate(
                type="tripwire-missing",
                evidence=(
                    ".claude/settings.json has a shape the tripwire writer will not "
                    f"edit: {reason}",
                    _TRIPWIRE_WHY,
                ),
                trigger_summary=(
                    "this repo's committed .claude/settings.json cannot take the "
                    f"unloaded-plugin tripwire hook: {reason}{_TRIPWIRE_COST}"
                ),
                owner_action=(
                    "Fix the `hooks` shape in .claude/settings.json by hand (it must be "
                    "an object whose SessionStart is a list); after that, say go and the "
                    "hook is added with everything else kept."
                ),
                recommended_action="/prawduct:doctor",
                priority="info",
            )
        ]
    what = (
        "has no unloaded-plugin tripwire hook"
        if found == unloaded_tripwire.ABSENT
        else "carries an older copy of the unloaded-plugin tripwire hook"
    )
    return [
        AdvisoryCandidate(
            type="tripwire-missing",
            evidence=(
                ".claude/settings.json lacks the current SessionStart hook that "
                "lib/unloaded_tripwire.py writes",
                _TRIPWIRE_WHY,
            ),
            trigger_summary=f"this repo's committed .claude/settings.json {what}{_TRIPWIRE_COST}",
            owner_action=(
                "Say go — this adds one SessionStart hook to a committed settings file "
                "and keeps everything else in it; you will see what it adds before "
                "anything is written."
            ),
            recommended_action="/prawduct:doctor",
            # `info`, the drift probe's priority and for its reason: this session is
            # governed, and the cost lands on a session elsewhere.
            priority="info",
        )
    ]


def register() -> None:
    """Register the install-reference probes. Idempotent (register_probe overwrites)."""
    register_probe(FEATURE, "contract-drift", PROBE_VERSION, probe_install_reference_drift)
    register_probe(FEATURE, "tripwire-missing", PROBE_VERSION, probe_tripwire_missing)
