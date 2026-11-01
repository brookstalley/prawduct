"""Post-sync advisory probe for a change record still on the single-file log.

Fires when ``.prawduct/change-log.md`` is committed and ``.prawduct/changes/``
does not exist: every branch still edits that one shared file, so merges
conflict there, and the repo has not moved onto change fragments.

**Why an advisory, not only a doctor check.** The migration
(``prawduct-hook migrate-change-log``) is owner-initiated by design — it can need
the owner's ``--default-type`` and it is one reviewable commit — and its procedure
lives in ``/prawduct:doctor`` check #22. But doctor runs only when someone runs
it, so a consuming repo that never did was never told the migration exists. The
session-start briefing is the one surface every onboarded repo re-reads, so the
nudge lives here and routes to doctor for the procedure.

**Self-resolving.** The migration always writes ``.prawduct/changes/.gitkeep``
(even with nothing pending), so the directory's existence is the done signal; the
next sync resolves the advisory, and ``gitattributes_probes`` then takes over the
union-attribute cleanup it gates on the same directory.

**Committed logs only.** A log git does not track cannot conflict at merge time,
which is the whole cost being advised against; when git cannot be asked the probe
returns ``None`` (could not look) rather than claiming either answer.

Registered at the composition root (``lib/probe_families.register_all``), not at
import time — the same pattern as the sibling probe modules.
"""

from __future__ import annotations

from . import gitstate
from .advisory_store import AdvisoryCandidate, Codebase, ProjectState, register_probe
from .change_fragments import FRAGMENT_DIR_REL
from .change_log import CHANGE_LOG_REL_PATH

FEATURE = "change-record"
PROBE_VERSION = 1


def probe_change_log_fragments_available(state: ProjectState, codebase: Codebase):
    """Fire when the committed change record is still the single-file log.

    Ordered so the steady state is cheapest: a migrated repo (or one with no log)
    ends on two stat calls; only a repo shaped like a legacy one pays the git
    subprocess that tells a committed log from an untracked one.
    """
    if not (codebase.root / CHANGE_LOG_REL_PATH).is_file():
        return []
    if (codebase.root / FRAGMENT_DIR_REL).is_dir():
        return []
    tracked = gitstate.git_path_is_tracked(codebase.root, CHANGE_LOG_REL_PATH)
    if tracked is None:
        return None  # could not look — not "nothing to report" (#917)
    if tracked is False:
        return []

    from .change_migrate import FRAGMENT_READERS_RELEASE, install_pin_too_old  # noqa: PLC0415 — lazy; only a firing repo asks

    # Count-independent: hashed into the advisory id, so it must not move as
    # entries are added or the install pin changes.
    evidence = (f"{CHANGE_LOG_REL_PATH} is committed and {FRAGMENT_DIR_REL}/ does not exist",)
    trigger_summary = (
        f"This repo still records changes in the single {CHANGE_LOG_REL_PATH}, so every "
        "branch edits the same file and merges conflict there; recording each change as "
        f"its own file under {FRAGMENT_DIR_REL}/ ends that"
    )
    # Moving onto fragments retires the reason for the union attribute, so the
    # migration is the work to weigh first.
    prerequisite_of = (
        (
            "gitattributes:change-log-union-merge",
            "moving onto change fragments, so no branch edits the shared log and the "
            "union-merge line is never needed",
        ),
    )
    pinned = install_pin_too_old(codebase.root)
    if pinned is not None:
        first = "v" + ".".join(map(str, FRAGMENT_READERS_RELEASE))
        return [
            AdvisoryCandidate(
                type="change-log-fragments-available",
                evidence=evidence,
                trigger_summary=trigger_summary,
                owner_action=(
                    f"First move this repo's prawduct install pin from {pinned} to {first} or "
                    "later — older releases cannot read change fragments, so the move refuses "
                    "until then. After that, say go to see a dry run; nothing is written until "
                    "you approve it."
                ),
                recommended_action="/prawduct:doctor",
                prerequisite_of=prerequisite_of,
                priority="info",
            )
        ]
    return [
        AdvisoryCandidate(
            type="change-log-fragments-available",
            evidence=evidence,
            trigger_summary=trigger_summary,
            owner_action=(
                "Say go to see a dry run first: it lists each not-yet-released entry that "
                "moves into its own file, and nothing is written until you approve it. "
                "Released history stays in the log, and the move is one commit you can revert."
            ),
            # Doctor check #22 is the one home for how the migration is run, its
            # refusals relayed and its --default-type chosen; doctor's routing
            # table sends this advisory straight to that check.
            recommended_action="/prawduct:doctor",
            prerequisite_of=prerequisite_of,
            priority="info",
        )
    ]


def register() -> None:
    """Register the change-record format probe. Idempotent (register_probe overwrites)."""
    register_probe(
        FEATURE,
        "change-log-fragments-available",
        PROBE_VERSION,
        probe_change_log_fragments_available,
    )
