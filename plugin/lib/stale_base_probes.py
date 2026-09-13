"""Post-sync advisory probe for a stale remote integration base — COV-7K4N.

One probe: it nudges before a coverage gate is ever hit when the local
integration branch (the configured ``base_branch:``, or the default
``origin/main`` resolution) carries an unpushed ``release-prep(vX)`` commit
ahead of its remote — a **"phantom release."** In that state
``check_cumulative_critic`` anchors its merge-base to the stale remote and can
report ``uncovered`` on already-reviewed work; the cheap, correct remedy is
``git push origin <b>`` (a required release step anyway), not the 4–10 min full
re-review the gate's generic remedy suggests. The reactive half of COV-7K4N — a
diagnostic hint on the gate's ``uncovered`` path — lives in
``gates.check_cumulative_critic``; this probe is the proactive half.

**Why release-prep-qualified, not merely "local ahead of remote."** A local
integration branch that is simply ahead of its remote is the *normal* state of
active development (you commit before you push) and would nag every session.
The costly, surprising foot-gun is specifically the unpromoted release-prep:
the release was cut locally but never pushed, so the remote pointer lags a
version behind and drags a whole already-shipped range into every feature's
required review span. Keying on the ``release-prep(...)`` subject targets that
root cause precisely and keeps the advisory quiet the rest of the time. The
broader stale-base case is still covered — reactively — by the gate hint.

**Self-resolving.** The trigger reads a directly-observable local-vs-remote git
fact (``coverage.diagnose_stale_remote_base``). Once ``git push origin <b>``
fast-forwards the remote, ``origin/<b>..<b>`` is empty, the probe returns ``[]``
on the next sync, and ``reconcile`` flips the advisory to ``resolved``. This
mirrors ``gitignore_probes`` / ``upstream_probes`` (trigger and resolution are
the same observable state), except the observable state here is a git ancestry
relation rather than a committed file.

**Evidence discipline.** The evidence string is count- and version-independent
(it names only the branches), so the advisory id stays stable across the whole
unpushed lifetime — a second release-prep stacked before the push does not churn
the id. The live count and the release-prep version live in ``trigger_summary``.

Registered at the composition root (``lib/probe_families.register_all``), not at
import time — the same pattern as the sibling probe modules. That module is the
one place the family roster lives; both roster call sites import it, so a probe
registered there cannot be reached by one call site and missed by the other.
"""

from __future__ import annotations

from . import coverage
from .advisory_store import AdvisoryCandidate, Codebase, ProjectState, register_probe

FEATURE = "stale-base"
PROBE_VERSION = 1


def probe_unpromoted_release_prep(state: ProjectState, codebase: Codebase):
    """Fire when the local integration branch has an unpushed release-prep.

    Inert whenever the remote is up to date with local, the local branch is
    ahead only by ordinary (non-release-prep) work, or the base is not a
    remote-tracking ref — the steady state for every repo not mid-phantom-release.
    """
    base_ref, _reason = coverage._resolve_base_branch(codebase.root)
    if not base_ref:
        return []
    diag = coverage.diagnose_stale_remote_base(codebase.root, base_ref)
    if diag is None or not diag["release_prep_subject"]:
        return []
    local = diag["local"]
    ahead = diag["commits_ahead"]
    plural = "" if ahead == 1 else "s"
    return [
        AdvisoryCandidate(
            type="unpromoted-release-prep",
            evidence=(
                f"local {local} carries an unpushed release-prep commit ahead of "
                f"{diag['remote']}",
            ),
            # States the condition, not the instruction: this line is relayed to the
            # owner, and "push before running coverage gates" told the one reader who
            # runs neither to do both — directly above an owner line that asks only
            # for a go-ahead.
            trigger_summary=(
                f"local {local} is {ahead} commit{plural} ahead of {diag['remote']} "
                f"with an unpushed {diag['release_prep_subject']!r}, so coverage gates "
                f"will read already-reviewed work as `uncovered`"
            ),
            # `ahead`, not "the commit": the probe already knows the count and renders a
            # plural for its summary, so a hardcoded singular would have the owner
            # approving N commits believing it was one — the precise failure the
            # cost-of-yes rule exists to prevent, in the one field they read.
            owner_action=(
                f"Say go and the {ahead} unpushed commit{plural} on {local} go{'' if plural else 'es'} "
                f"up to {diag['remote']}. It is work that was already reviewed here; pushing it "
                "just stops the coverage gates from re-flagging it as unreviewed."
            ),
            recommended_action=f"git push origin {local}",
            priority="warn",
        )
    ]


def register() -> None:
    """Register the stale-base probe. Idempotent (register_probe overwrites)."""
    register_probe(
        FEATURE, "unpromoted-release-prep", PROBE_VERSION, probe_unpromoted_release_prep
    )
