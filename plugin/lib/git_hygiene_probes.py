"""Post-sync advisory probe: merged branches and dead worktrees are ready to go.

One advisory for the whole set, not one per branch. A merged branch is not a
decision the way a stranded one is: its content is already carried by a
long-lived branch, so the only question is whether to tidy now, and that is
asked once. The agent shows the owner ``prawduct-hook git-tidy``'s dry run and
applies it on a yes.

**No network, ever.** Probes run at every session start, and this one reads only
the clone: refs, worktree records and file times. A remote deletion it lists is
marked unchecked, because the open-pull-request check it needs is the network's.

**Its id follows the set.** The evidence is one line per proposed removal (kind
and target, never the commit), so dismissing it holds until a removal is added
or one goes away, and a branch gaining a commit does not reopen it.

**Silent under ``Branch cleanup: off``.** The product owns that policy; an
absent, unreadable or unrecognised row means ``propose``.

Self-resolving: tidy, and the probe returns nothing, so ``reconcile`` marks the
advisory resolved.

Registered at the composition root (``lib/probe_families.register_all``).
"""

from __future__ import annotations

import sys

from . import git_hygiene
from .advisory_store import AdvisoryCandidate, Codebase, ProjectState, register_probe

FEATURE = "git-hygiene"
PROBE_TYPE = "tidy-available"
PROBE_VERSION = 1

#: (singular, plural) per removal kind.
_NOUNS = {
    git_hygiene.REMOVE_WORKTREE: ("finished worktree", "finished worktrees"),
    git_hygiene.PRUNE_WORKTREE: ("dead worktree entry", "dead worktree entries"),
    git_hygiene.DELETE_BRANCH: ("merged local branch", "merged local branches"),
    git_hygiene.DELETE_REMOTE_BRANCH: ("merged remote branch", "merged remote branches"),
}


def _summary(plan: git_hygiene.Plan) -> str:
    """Counts by kind in run order, such as `5 merged local branches, 1 dead worktree entry`."""
    parts = []
    for kind in git_hygiene.KIND_ORDER:
        n = sum(1 for a in plan.actions if a.kind == kind)
        if n:
            parts.append(f"{n} {_NOUNS[kind][0 if n == 1 else 1]}")
    return ", ".join(parts)


def probe_tidy_available(state: ProjectState, codebase: Codebase):
    """One advisory when the clone holds removals that lose nothing, or none."""
    if not git_hygiene.cleanup_enabled(codebase.root):
        return []
    plan = git_hygiene.plan(codebase.root, offline=True)
    if plan.problems and not plan.actions:
        print(
            f"NOTE: tidy probe skipped: {plan.problems[0]} — merged branches and dead "
            "worktrees would go unreported this session",
            file=sys.stderr,
        )
        return None  # could not look — not "nothing to report"
    if not plan.actions:
        return []
    return [
        AdvisoryCandidate(
            type=PROBE_TYPE,
            evidence=tuple(f"{a.kind} {a.target}" for a in plan.actions),
            trigger_summary=(
                f"{_summary(plan)} can be removed without losing anything: each is "
                "already carried by a long-lived branch, or is a record of a directory "
                "that no longer exists"
            ),
            owner_action=(
                "Say whether to tidy now. The dry run lists every removal with its proof; "
                "one yes covers the whole list, and a deleted remote branch is restored "
                "only by pushing it again."
            ),
            recommended_action="prawduct-hook git-tidy",
            priority="info",
        )
    ]


def register() -> None:
    """Register the tidy probe. Idempotent (register_probe overwrites)."""
    register_probe(FEATURE, PROBE_TYPE, PROBE_VERSION, probe_tidy_available)
