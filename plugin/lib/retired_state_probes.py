"""Post-sync advisory probe for the retired ``build_state.test_tracking`` block.

One probe: it fires when a governed repo's ``project-state.yaml`` still carries
the hand-maintained test-count block that ``lifecycle_repair`` removes.

**Why a nudge and not just the repair.** The block is removable two ways —
``/prawduct:doctor`` → ``lifecycle-repair`` for an already-onboarded repo, and
the plugin cutover for one crossing over — and *both need someone to decide to
run them*. Nothing told them there was anything to run, and the routes differ per
repo: measured across the fleet the day the removal shipped, nine repos still
carried the block, four of which needed ``migrate`` rather than ``doctor``.
Expecting each owner to work that out unprompted is the gap this closes.

**The harm is behavioural, not spatial, and that is what shapes the message.**
The block's cost was never its bytes. It is that an agent meeting a stale count
in a product's *source of truth* is obliged by Living Documentation to correct
it — and every correction is a commit, every commit extends HEAD, and that is how
a record defect buys a review round. So the summary leads with **"retired; do not
maintain it"** rather than with a diagnosis: that instruction reaches the agent
at session start and stops the bleeding on the first session, whether or not the
repair is ever run. A nudge that only reported the condition would leave the
treadmill turning until someone acted.

**Recommends; never writes.** Unlike ``.gitattributes`` (which sits outside the
plugin's write set entirely), ``project-state.yaml`` *is* the plugin's own
``.prawduct/`` state, so the write-set norm would permit an automatic strip.
What forbids it is ``security-model.md`` § Direction: a destructive operation
takes one informed confirmation at the operation level, and a framework silently
deleting from a product's hand-authored state file is the trust breach that rule
exists for. So this names the block and the command, and the operator runs it.

**Detection is delegated, not restated.** What a retired key *is* — the name, the
enclosing parent, the span — lives in :func:`lib.lifecycle_repair.state_removals`
and nowhere else. This module is its third caller, after the doctor repair and
the cutover; a copy of the key name here would drift the moment either changed
(`architecture.md` § Direction: every fact has one home).

**Scoped to this block alone.** ``views_enabled`` and ``scope_rollups`` are the
other retired state keys and are deliberately **excluded**: nobody maintains
them, so they carry no behavioural cost, and doctor's Health Check #15 already
covers their cleanup. An ambient nudge about inert residue is exactly the control
``nonfunctional-requirements.md`` § Direction says to remove by default.

**Self-resolving.** The trigger and the resolution are one observable state — the
block is there or it is not — so running the repair makes the next sync return
``[]`` and the advisory flips to ``resolved`` with no dismissal needed. Same
shape as ``gitattributes_probes`` and ``gitignore_probes``.

**Named for the family, not for the key** — ``retired_state_probes`` rather than
``test_tracking_probes``. A module whose name starts with ``test_`` reads as a
test file to pytest's collector, and this repo's ``testpaths=["tests"]`` means
one living under ``plugin/lib/`` would be silently skipped by any run that did
collect it. A preferences test enforces the naming; it caught this module on its
first full run.

Registered at the composition root (``lib/probe_families.register_all``), not at
import time — the same pattern as the sibling probe modules.
"""

from __future__ import annotations

from . import lifecycle_repair
from .advisory_store import AdvisoryCandidate, Codebase, ProjectState, register_probe

FEATURE = "test-tracking"
PROBE_VERSION = 1

#: The advisory type. Named once so the probe, its registration and its tests
#: cannot drift into disagreeing about what fired.
PROBE_TYPE = "retired-test-tracking"

#: The key this probe is about, as `state_removals` reports it. Compared against
#: that function's output rather than re-deriving the name from YAML, so the
#: definition stays in one place.
RETIRED_KEY = f"{lifecycle_repair.TEST_TRACKING_PARENT}.{lifecycle_repair.TEST_TRACKING_KEY}"

#: The remedy, verbatim. One string so the recommendation and its test cannot
#: recommend two different commands.
REPAIR_COMMAND = "prawduct-hook lifecycle-repair --apply"


def probe_retired_test_tracking(state: ProjectState, codebase: Codebase):
    """Raise one advisory when the retired test-count block is still present.

    Quiet on every input it cannot read: an absent, unreadable or undecodable
    state file yields ``[]`` rather than a guess. This is the *advice fails
    soft* half of ``architecture.md`` § Direction — nagging a repo about a file
    that was never read would be a confident claim about something unexamined,
    and unlike a gate there is no caller here to fail closed on.

    ``state`` is unused: :class:`ProjectState` exposes top-level scalars, and
    this key is nested, so the file is read directly.
    """
    path = codebase.root / ".prawduct" / "project-state.yaml"
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    if not any(item["key"] == RETIRED_KEY for item in lifecycle_repair.state_removals(text)):
        return []

    return [
        AdvisoryCandidate(
            type=PROBE_TYPE,
            # Deliberately carries NO count, size or member list. The advisory
            # id hashes this, and these files are edited by their own sessions —
            # one shrank by ~52 KB mid-measurement while this feature was being
            # built. Evidence that moved with the contents would give the same
            # condition a new id on every such edit, silently un-dismissing an
            # advisory the owner had already decided about.
            evidence=(
                f".prawduct/project-state.yaml carries the retired `{RETIRED_KEY}` block",
            ),
            trigger_summary=(
                f"`{RETIRED_KEY}` is retired — **do not maintain it**. It is a "
                "hand-kept copy of a fact the test evidence store already holds "
                "per tree, nothing in the runtime reads it, and no template "
                "creates it; correcting the number costs a commit and a review "
                "round every time. Read `prawduct-hook test-status` for the real "
                "result, and remove the block"
            ),
            recommended_action=(
                f"{REPAIR_COMMAND} (previews first without `--apply`); "
                "`/prawduct:doctor` walks it with you"
            ),
            # Named because the route genuinely differs: a repo that has not yet
            # cut over to the plugin gets this removed by `/prawduct:migrate`,
            # and `lifecycle-repair` is not its path. Recommending only the
            # doctor route would send those repos to a command that changes
            # nothing on them, which reads as the feature being broken.
            alternative_actions=(
                "/prawduct:migrate — if this repo has not yet cut over to the plugin, "
                "the cutover removes it on the way through",
            ),
            priority="info",
        )
    ]


def register() -> None:
    """Register the retired-test-tracking probe. Idempotent (register_probe overwrites)."""
    register_probe(FEATURE, PROBE_TYPE, PROBE_VERSION, probe_retired_test_tracking)
