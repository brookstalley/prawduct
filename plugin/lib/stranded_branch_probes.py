"""Post-sync advisory probes for unlanded branches — both arms of #843.

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

**The pushed arm** (``finished-branch-unlanded``) is #843's own design: a
pushed branch that every build plan claiming it calls finished, that has not
merged into its base, and whose last commit is a day old
(``stranded_work.unlanded_branches``). ``fix/767-test-status-clause`` sat that
way for two days, plan saying "PR-ready", while the defect it fixed cost two
red CI runs. Probes run at every session start, where nothing touches the
network, so this one cannot ask whether a pull request was ever opened: it
names the branch and recommends ``prawduct-hook worktrees --prs``, which asks.
That is why it is ``info``, not ``warn``. **Known false positive, accepted:**
a finished branch whose pull request is open and waiting fires until it
merges; dismissing it with that reason answers it.

Registered at the composition root (``lib/probe_families.register_all``).
"""

from __future__ import annotations

import shlex
import sys
import time

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
        return None  # could not look — not "nothing to report" (#917)
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
                # Quoted: git allows `$(`, backticks and spaces in a branch name,
                # and this line is a command the runtime executes as given.
                recommended_action=f"git log --oneline {shlex.quote('refs/heads/' + row.name)} --not --remotes",
                priority="warn",
            )
        )
    return candidates


def probe_finished_branch_unlanded(state: ProjectState, codebase: Codebase):
    """One advisory per finished, pushed, unmerged branch idle a day or more.
    Offline: the pull-request question is ``worktrees --prs``'s to ask."""
    rows, problem = stranded_work.unlanded_branches(codebase.root)
    if problem:
        print(
            f"NOTE: finished-branch probe skipped: {problem} — a finished branch that "
            "never reached a pull request would go unreported this session",
            file=sys.stderr,
        )
        return None  # could not look — not "nothing to report" (#917)
    now = time.time()
    candidates: list[AdvisoryCandidate] = []
    for row in rows:
        plans = ", ".join(row.plans)
        candidates.append(
            AdvisoryCandidate(
                type="finished-branch-unlanded",
                # The branch alone: the id must survive new plans and the clock.
                evidence=(f"branch {row.name}",),
                trigger_summary=(
                    f"branch {row.name} is finished by every build plan claiming it ({plans}), "
                    f"pushed, and not merged into its base; its last commit was "
                    f"{stranded_work.age_text(now - row.last_commit)} — finished work that may never "
                    "have reached a pull request (not checked at session start)"
                ),
                owner_action=(
                    "Decide whether this finished work should land: ship it through a pull "
                    "request, or say why not. If a pull request is already open and waiting, "
                    "dismiss this with that reason."
                ),
                recommended_action="prawduct-hook worktrees --prs",
                priority="info",
            )
        )
    return candidates


def register() -> None:
    """Register both arms. Idempotent (register_probe overwrites)."""
    register_probe(FEATURE, "stranded-branch", PROBE_VERSION, probe_stranded_branch)
    register_probe(FEATURE, "finished-branch-unlanded", PROBE_VERSION, probe_finished_branch_unlanded)
