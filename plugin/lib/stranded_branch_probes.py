"""Post-sync advisory probe for a stranded branch — the local-only arm of #843.

A branch is stranded when it is checked out in no live worktree and its tip is
reachable from no remote-tracking ref (``stranded_work.stranded_branches``).
That is the shape a finished, reviewed fix takes when its session ends before
the push: #898 and #818 sat that way for a day while the next session planned
to build #898 from scratch, and #640's fix sat that way for nine days until a
later PR re-applied it.

**An advisory, not a briefing line** (owner, 2026-09-19 on #843: "a visible,
dismissible signal, not a refusal"; reaffirmed 2026-09-28). Each branch is its
own decision, so each gets its own advisory, keyed on the branch name alone —
dismissing one never silences another, and the id is stable for as long as the
branch lives. Naming the branch is safe where naming a sibling worktree is not
(#410): a branch checked out nowhere is nobody's live work.

**Self-resolving.** Push the branch, merge it, or delete it, and the probe stops
producing it; ``reconcile`` then marks the advisory resolved. Abandoning it on
purpose is a dismissal with a reason, kept per clone.

**Known false positive, accepted:** in a repo that squash- or rebase-merges, a
merged branch that was never deleted locally still has commits no remote has,
so it fires once. The dismissal answers it, and deleting the branch — the
hygiene those strategies already require — resolves it.

#843's other arm — a pushed branch whose build plan is fully ticked but which
never got a PR — needs a network call and is not built here.

Registered at the composition root (``lib/probe_families.register_all``).
"""

from __future__ import annotations

import sys

from . import stranded_work
from .advisory_store import AdvisoryCandidate, Codebase, ProjectState, register_probe

FEATURE = "branch-landing"
PROBE_VERSION = 1


def probe_stranded_branch(state: ProjectState, codebase: Codebase):
    """One advisory per local branch checked out nowhere whose commits no remote
    has. Inert in a repo with no remote-tracking refs, where every branch would
    qualify and the signal would mean nothing."""
    rows, _has_remotes, problem = stranded_work.stranded_branches(codebase.root)
    if problem:
        print(
            f"NOTE: stranded-branch probe skipped: {problem} — a branch holding "
            "unpushed work would go unreported this session",
            file=sys.stderr,
        )
        return []
    candidates: list[AdvisoryCandidate] = []
    for row in rows:
        candidates.append(
            AdvisoryCandidate(
                type="stranded-branch",
                evidence=(
                    f"local branch {row.name} is checked out in no worktree and holds "
                    "commits no remote-tracking ref reaches",
                ),
                trigger_summary=(
                    f"branch {row.name} holds commits no remote has, and no worktree has it "
                    "checked out — work stranded like this gets rebuilt by the next session "
                    "that cannot see it; land it, push it, or delete it and record why"
                ),
                owner_action=(
                    "Decide whether the work on this branch is still wanted: ship it through "
                    "a pull request, push it so it is visible while it waits, or drop it and "
                    "say why so nobody builds it again."
                ),
                recommended_action=f"git log --oneline refs/heads/{row.name} --not --remotes",
                priority="warn",
            )
        )
    return candidates


def register() -> None:
    """Register the stranded-branch probe. Idempotent (register_probe overwrites)."""
    register_probe(FEATURE, "stranded-branch", PROBE_VERSION, probe_stranded_branch)
