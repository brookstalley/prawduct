"""Post-sync advisory probe for an unintegrated ad-hoc delegate worktree.

One probe, the *reaping* side of ad-hoc delegation
(``methodology/delegation.md`` § Work no plan anticipated): a delegate hands
back a branch plus an integration debt, and the agent that incurred that debt
is — by the very reason it delegated, a full context — not the one who will
pay it. A debt held only in a coordinator's context evaporates at the next
``/clear``, leaving an unmerged branch and a worktree nobody remembers
creating. This probe is what makes that state say its own name at session
start.

**The trigger is the dispatch record, not a registry.** The brief is written
into the delegate's worktree at ``.prawduct/.delegate-brief.md``, so an
abandoned delegate is detectable from the filesystem alone — no registry,
schema, lease or slot accounting. That is also what keeps the probe **inert by
absence**: the brief is gitignored, so it exists only in a worktree where a
dispatch actually happened. A clone that has never delegated sees nothing, and
so does a clone whose worktrees are ordinary feature checkouts — which is the
common case and the reason the brief, rather than the worktree, is the key.

**The worktree boundary is respected: this probe stats, it never reads.** The
brief belongs to the session that wrote it, and "other worktrees belong to
their own sessions" is a rule this framework states and must therefore obey.
Presence of the file is the whole signal; its contents are for the human or
agent who decides what to do about it.

**Self-resolving, both ways.** Trigger and resolution are the same observable
state, as in ``gitignore_probes`` / ``stale_base_probes``. Merge the branch and
its tip becomes an ancestor of HEAD (or of the integration base), so the probe
returns nothing and ``reconcile`` flips the advisory to ``resolved``; remove
the worktree and the brief is gone with it. The third path — abandoning it
deliberately — is a dismissal with a reason, which the advisory store keeps per
clone and indefinitely.

**One advisory per worktree, keyed on the branch.** Two abandoned delegates are
two decisions, so dismissing the first must not silence the second. The
evidence string names only the branch (or, detached, the commit), so the id is
stable for as long as that worktree lives and a second delegate elsewhere does
not churn it.

Registered at the composition root (``lib/probe_families.register_all``), not
at import time — the same pattern as the sibling probe modules.
"""

from __future__ import annotations

from pathlib import Path

from . import evidence
from .advisory_store import AdvisoryCandidate, Codebase, ProjectState, register_probe

FEATURE = "delegation"
PROBE_VERSION = 1

# The dispatch record's location inside a delegate's own worktree. Kept in step
# with `methodology/delegation.md` and with `core.GITIGNORE_ENTRIES`, which is
# what makes the file untracked and therefore a per-worktree signal rather than
# something every checkout inherits from HEAD.
BRIEF_REL = Path(".prawduct") / ".delegate-brief.md"


def _worktree_records(root: Path) -> list[dict]:
    """Parse ``git worktree list --porcelain`` into one dict per worktree.

    Keys are the porcelain's own line labels — ``worktree`` (path), ``HEAD``
    (sha), ``branch`` (full ref) — plus valueless markers (``bare``,
    ``detached``, ``locked``, ``prunable``) mapped to ``""``. Any git failure
    yields an empty list, so the probe stays silent rather than raising.
    """
    rc, out, _err = evidence.run_git(root, "worktree", "list", "--porcelain")
    if rc != 0 or not out:
        return []
    records: list[dict] = []
    current: dict = {}
    for line in out.splitlines():
        if not line.strip():
            if current:
                records.append(current)
                current = {}
            continue
        key, _sep, value = line.partition(" ")
        current[key] = value
    if current:
        records.append(current)
    return records


def _is_integrated(root: Path, sha: str, refs: list[str]) -> bool:
    """True when ``sha`` is already reachable from one of ``refs``.

    Both refs matter. HEAD covers the ordinary case — the coordinator merged the
    delegate into the branch it was working on. The integration base covers the
    case where that feature branch has itself shipped and the coordinator has
    since moved to unrelated work, where HEAD alone would report a long-merged
    delegate as outstanding.
    """
    for ref in refs:
        rc, _out, _err = evidence.run_git(root, "merge-base", "--is-ancestor", sha, ref)
        if rc == 0:
            return True
    return False


def _integration_refs(root: Path) -> list[str]:
    """HEAD plus the configured integration base, when one resolves."""
    from . import coverage  # noqa: PLC0415 — lazy: only a brief-holding worktree pays for it

    refs = ["HEAD"]
    base_ref, _reason = coverage._resolve_base_branch(root)
    if base_ref:
        refs.append(base_ref)
    return refs


def _display_path(root: Path, worktree: Path) -> str:
    """The worktree path relative to the clone when it sits inside it, else absolute.

    ``root`` must already be absolute: git reports worktree paths absolute, so a
    relative root would fail every comparison and print the long form for the
    common case — a harness worktree living inside the clone.
    """
    try:
        return str(worktree.relative_to(root))
    except ValueError:
        return str(worktree)


def probe_unintegrated_delegate_worktree(state: ProjectState, codebase: Codebase):
    """Fire once per worktree that holds a delegate brief on an unintegrated branch.

    Inert when the clone has no linked worktrees, when no worktree holds a
    brief (every repo that has never dispatched an ad-hoc delegate), and when
    every brief-holding worktree's tip is already reachable from HEAD or the
    integration base. That last condition is also what keeps a session running
    *inside* a delegate worktree from nagging about itself — its own tip is its
    own HEAD — so no special case is needed for the tree you are standing in.
    """
    root = codebase.root
    records = _worktree_records(root)
    if len(records) < 2:
        return []

    try:
        root_abs = root.resolve()
    except OSError:
        root_abs = root
    candidates: list[AdvisoryCandidate] = []
    # Resolved lazily, and only once, on the first brief found: the steady state
    # is "no brief anywhere", and the base resolution costs a git call plus a
    # project-state read that the steady state must not pay on the hot path.
    refs: list[str] | None = None

    for record in records:
        raw_path = record.get("worktree")
        # A bare worktree carries no HEAD line, which is also the only shape
        # that can reach here without one.
        sha = record.get("HEAD")
        if not raw_path or not sha:
            continue
        worktree = Path(raw_path)
        # A stat, never a read — see the module docstring's boundary note.
        if not (worktree / BRIEF_REL).is_file():
            continue
        if refs is None:
            refs = _integration_refs(root)
        if _is_integrated(root, sha, refs):
            continue

        branch_ref = record.get("branch") or ""
        label = branch_ref.rpartition("refs/heads/")[2] or branch_ref
        subject = f"branch {label}" if label else f"detached HEAD {sha[:12]}"
        shown = _display_path(root_abs, worktree)
        candidates.append(
            AdvisoryCandidate(
                type="unintegrated-delegate-worktree",
                evidence=(
                    f"delegate worktree on {subject} holds a brief and is not "
                    "reachable from HEAD or the integration base",
                ),
                trigger_summary=(
                    f"delegate {subject} is unintegrated — its worktree ({shown}) "
                    "holds a dispatch brief, so compute was spent and nothing else "
                    "remembers it; integrate it (you own the merge, live "
                    "verification and the Critic) or abandon it and record why"
                ),
                recommended_action=(
                    f"git log --oneline HEAD..{label}" if label else f"git log --oneline HEAD..{sha[:12]}"
                ),
                alternative_actions=(
                    f"git worktree remove {shown}",
                    "/prawduct:advisory dismiss <id> --reason=\"<why it was abandoned>\"",
                ),
                priority="warn",
            )
        )
    return candidates


def register() -> None:
    """Register the ad-hoc delegate probe. Idempotent (register_probe overwrites)."""
    register_probe(
        FEATURE,
        "unintegrated-delegate-worktree",
        PROBE_VERSION,
        probe_unintegrated_delegate_worktree,
    )
