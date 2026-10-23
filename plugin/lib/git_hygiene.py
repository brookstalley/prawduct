"""Git hygiene: which branches and worktrees can go, and the proof that says so.

One rule governs everything here: a ref or worktree is removed only when what it
holds is provably carried by something that stays. Age, inactivity and "looks
abandoned" are never proof. The proof for a branch is that its tip is reachable
from a LONG-LIVED branch (the remote's default branch, the resolved base,
``main``/``master``/``develop``/``trunk``, ``release/*``, and whatever the
product lists in its ``Long-lived branches`` preference row), or — where a
squash or rebase merge rewrote the commits — a merged pull request whose head was
exactly this commit. Being pushed is not proof: a pushed, unmerged branch has
nothing integrated anywhere. A remote deletion is proven only by a REMOTE
long-lived branch, because a local one may hold merges nobody has pushed.

This module classifies and, on approval, removes; it does not decide policy.
Three readers:

* ``prawduct-hook git-tidy`` — the dry run every removal starts from: each
  action, the commit it is about, its proof, and the exact git command, ending in
  a fingerprint of the set. ``--apply <fingerprint>`` removes exactly that set.
* The ``tidy-available`` advisory, which proposes that dry run at session start,
  offline.
* The stranded-branch scan shares ``gitstate.held_branches``, so "checked out"
  has one definition across both.

What is never a candidate, whatever its state: a long-lived branch; a branch
checked out in a worktree somebody could be working in; the main worktree and
the current one; a locked worktree (the harness locks an agent's worktree while
the agent runs); a worktree with tracked changes or untracked files; a detached
or long-lived-branch worktree, which is a checkout kept for its own sake (an
install a plugin runs from looks exactly like one); a remote branch an open pull
request uses as its head or base (deleting a base closes the request stacked on
it); and a branch on someone else's fork. A sibling worktree is proposed only
when it holds a finished feature branch and has shown no sign of life for a week.

**Removal re-proves, then compares and deletes.** Approval binds to a
fingerprint of the exact set, and ``--apply`` refuses when the set has changed.
Each removal then re-checks its own proof immediately before it runs, and the
delete itself is conditional on the ref still naming the proven commit:
``git update-ref -d <ref> <sha>`` locally, and a fresh ``ls-remote`` before a
remote delete. ``git branch -d`` is not used, because it asks whether the branch
is merged into HEAD or its upstream — not into the long-lived branch that is the
proof — and so refuses a branch merged into ``main`` while ``develop`` is checked
out. Nothing here passes ``-D`` or ``--force``.

**Network.** Only the online dry run and ``--apply`` touch it: ``git fetch
--prune`` first (a proof against stale refs is not a proof), one ``gh pr list``
of open pull requests, at most :data:`MAX_PR_PROOFS` merged-PR lookups, an
``ls-remote`` and the ``git push --delete`` per remote removal. All of it goes
to the product's own remote and carries none of its content. ``offline`` skips
every leg and marks what it would have decided as unchecked.

Reads run with ``GIT_OPTIONAL_LOCKS=0`` so observing a sibling never rewrites its
index. A read that fails is a named problem, and the dry run says "nothing to
tidy" only when every part of it was checked.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import evidence, gitstate, stranded_work

SCHEMA_VERSION = 1

#: Branch names that are long-lived wherever they exist.
LONG_LIVED_NAMES = frozenset({"main", "master", "develop", "trunk"})
#: Prefixes whose branches are long-lived. ``hotfix/*`` is deliberately absent:
#: a hotfix branch merges and is done, like a feature branch.
LONG_LIVED_PREFIXES = ("release/",)

#: ``project-preferences.md`` rows this module reads.
CLEANUP_LABEL = "Branch cleanup"
LONG_LIVED_LABEL = "Long-lived branches"
MERGE_STRATEGY_LABEL = "PR merge strategy"
CLEANUP_OFF = "off"

#: Merged-pull-request lookups per run, oldest branch first. Each is one network
#: call; the rest are reported as unchecked rather than silently dropped.
MAX_PR_PROOFS = 8
#: Open pull requests listed in one call. A full page means the list may be
#: incomplete, and then no remote deletion is proven by it.
OPEN_PR_LIMIT = 500
#: Seconds one ``gh`` call may take before it counts as unavailable.
GH_TIMEOUT = 15

# Action kinds, in the order they run: removing a worktree frees its branch, so
# worktrees go before branches, and local deletes go before remote ones.
REMOVE_WORKTREE = "remove-worktree"
PRUNE_WORKTREE = "prune-worktree"
DELETE_BRANCH = "delete-branch"
DELETE_REMOTE_BRANCH = "delete-remote-branch"
KIND_ORDER = (REMOVE_WORKTREE, PRUNE_WORKTREE, DELETE_BRANCH, DELETE_REMOTE_BRANCH)

#: ``proven_by`` prefix for a merged-pull-request proof, followed by its number.
PR_PROOF = "pull-request:"

#: Why a remote deletion cannot be proven without the network: an open pull
#: request may use the branch as its base, and deleting a base closes the PR
#: stacked on it.
OPEN_PR_UNCHECKED = "not checked offline: an open pull request may still use it"


@dataclass(frozen=True)
class Action:
    kind: str
    target: str  # branch name, "<remote>/<branch>", or worktree path
    sha: str  # the commit the proof is about; "" when there is none (a prune)
    proof: str  # why removing it loses nothing, in words
    command: tuple[str, ...]
    #: Set when the action cannot run until a network check confirms it; says why.
    unchecked: str | None = None
    #: The full ref whose reach is the proof, or ``pull-request:<n>``; "" for a prune.
    proven_by: str = ""


@dataclass
class Plan:
    remote: str = "origin"
    online: bool = False
    long_lived: list[str] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def fingerprint(self) -> str:
        return fingerprint(self.actions)

    @property
    def fully_checked(self) -> bool:
        return not self.problems and not any(a.unchecked for a in self.actions)


def fingerprint(actions: list[Action]) -> str:
    """12 hex chars naming exactly this set of removals, independent of order.
    What an approval binds to: a branch whose tip moves changes it."""
    lines = sorted(f"{a.kind}\0{a.target}\0{a.sha}" for a in actions)
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()[:12]


# --- reading git and gh -------------------------------------------------------


def _git(cwd: Path, *args: str) -> str | None:
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    rc, out, _err = evidence.run_git(cwd, *args, env=env)
    return out if rc == 0 else None


def _git_write(cwd: Path, *args: str) -> tuple[bool, str]:
    """``(ok, detail)``. The detail is git's own message, scrubbed: a remote URL
    can carry a token, and the detail reaches stdout and the ``--json`` payload."""
    from .backlog.transport import scrub_secrets  # noqa: PLC0415 — the one credential denylist

    rc, out, err = evidence.run_git(cwd, *args)
    return rc == 0, scrub_secrets((err or out).strip())


def _refs(project_dir: Path, *patterns: str, merged: str | None = None) -> dict[str, str] | None:
    """``{full refname: sha}`` for ``patterns``, optionally only those reachable
    from ``merged``. Symbolic refs (``refs/remotes/<r>/HEAD``) are skipped."""
    args = ["for-each-ref", "--format=%(refname)%09%(objectname)%09%(symref)"]
    if merged:
        args.append(f"--merged={merged}")
    out = _git(project_dir, *args, *patterns)
    if out is None:
        return None
    refs: dict[str, str] = {}
    for line in out.splitlines():
        name, _t, rest = line.partition("\t")
        sha, _t, symref = rest.partition("\t")
        if name and sha and not symref:
            refs[name] = sha
    return refs


def _upstream_gone_and_age(project_dir: Path) -> dict[str, tuple[bool, float]]:
    """``{refs/heads/x: (upstream gone, last commit time)}``; empty on failure."""
    out = _git(
        project_dir, "for-each-ref",
        "--format=%(refname)%09%(upstream:track)%09%(committerdate:unix)", "refs/heads/",
    )
    result: dict[str, tuple[bool, float]] = {}
    for line in (out or "").splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            try:
                result[parts[0]] = (parts[1] == "[gone]", float(parts[2] or 0))
            except ValueError:
                continue
    return result


def _short(refname: str, remote: str) -> str:
    """The branch name a ref carries: ``refs/heads/x`` and ``refs/remotes/<remote>/x`` → ``x``."""
    for prefix in ("refs/heads/", f"refs/remotes/{remote}/"):
        if refname.startswith(prefix):
            return refname[len(prefix):]
    return refname


def _shown(ref: str) -> str:
    """How a proof ref reads to a person: ``refs/remotes/origin/main`` → ``origin/main``."""
    return ref.removeprefix("refs/").removeprefix("heads/").removeprefix("remotes/")


def _gh_json(project_dir: Path, *args: str) -> list | None:
    """Parsed JSON from one ``gh`` call against the product's own repo, or None
    when gh is missing, unauthenticated, slow or answers with something else."""
    try:
        proc = subprocess.run(
            ["gh", *args], cwd=str(project_dir), capture_output=True, text=True, timeout=GH_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout or "null")
    except ValueError:
        return None
    return data if isinstance(data, list) else None


def _branches_in_use(project_dir: Path) -> tuple[set[str] | None, dict[str, int]]:
    """``(names, pr number per name)`` an open pull request uses, as its base or
    its head. None when that cannot be told.

    A head counts whatever repository it lives in. ``gh`` answers for the repo it
    resolves, which in a fork setup is often the upstream, and there this clone's
    own branch heads a request as a cross-repository head. Counting only
    same-repo heads would delete the branch under an open request. The cost of
    counting every head is that a stranger's fork branch of the same name keeps
    ours one more run."""
    prs = _gh_json(
        project_dir, "pr", "list", "--state", "open",
        "--json", "number,headRefName,baseRefName,isCrossRepository", "--limit", str(OPEN_PR_LIMIT),
    )
    if prs is None or len(prs) >= OPEN_PR_LIMIT:
        return None, {}
    names: set[str] = set()
    numbers: dict[str, int] = {}
    for pr in prs:
        if not isinstance(pr, dict):
            return None, {}
        for name in (pr.get("baseRefName"), pr.get("headRefName")):
            if isinstance(name, str) and name:
                names.add(name)
                numbers.setdefault(name, pr.get("number"))
    return names, numbers


def _merged_pr_for(project_dir: Path, branch: str, sha: str) -> int | None | bool:
    """The number of a merged pull request from this repo whose head was exactly
    ``sha``; False when there is none; None when gh could not be asked."""
    prs = _gh_json(
        project_dir, "pr", "list", "--state", "merged", "--head", branch,
        "--json", "number,headRefOid,isCrossRepository", "--limit", "20",
    )
    if prs is None:
        return None
    for pr in prs:
        if isinstance(pr, dict) and pr.get("headRefOid") == sha and pr.get("isCrossRepository") is False:
            return pr.get("number")
    return False


# --- policy -------------------------------------------------------------------


def cleanup_enabled(project_dir: Path) -> bool:
    """False only when ``Branch cleanup`` says ``off``. Absent, unreadable or
    unrecognised all read as the default, ``propose``."""
    from .core import read_preference_row  # noqa: PLC0415 — core is heavy; only policy needs it

    row = read_preference_row(project_dir, CLEANUP_LABEL)
    return row.value != CLEANUP_OFF


def rewrites_history(project_dir: Path) -> bool:
    """True when the product's ``PR merge strategy`` is squash or rebase, which
    leaves a merged branch's own commits on no long-lived branch."""
    from .core import read_preference_row  # noqa: PLC0415

    value = read_preference_row(project_dir, MERGE_STRATEGY_LABEL).value or ""
    return value.startswith(("squash", "rebase"))


def _preferred_long_lived(project_dir: Path) -> set[str]:
    from .core import read_preference_row  # noqa: PLC0415

    row = read_preference_row(project_dir, LONG_LIVED_LABEL, lower=False)
    if not row.value:
        return set()
    return {n.strip().strip("`") for n in row.value.replace(";", ",").split(",") if n.strip()}


def long_lived_names(project_dir: Path, remote: str) -> set[str]:
    """Names that are never deleted and against which integration is proven."""
    from . import coverage  # noqa: PLC0415 — the one base resolver

    names = set(LONG_LIVED_NAMES) | _preferred_long_lived(project_dir)
    for ref in (coverage._origin_head_ref(project_dir), coverage._resolve_base_branch(project_dir)[0]):
        if not ref or "~" in ref or ref == "HEAD":
            continue  # the resolver's HEAD~1 fallback names no branch
        for prefix in (f"{remote}/", "origin/"):
            if ref.startswith(prefix):
                ref = ref[len(prefix):]
                break
        names.add(ref)
    return names


def is_long_lived(name: str, names: set[str]) -> bool:
    return name in names or name.startswith(LONG_LIVED_PREFIXES)


# --- classification -----------------------------------------------------------


def _delete_branch_command(name: str, sha: str) -> tuple[str, ...]:
    return ("git", "update-ref", "-d", f"refs/heads/{name}", sha)


def plan(
    project_dir: Path,
    *,
    now: float | None = None,
    roots: list[Path] | None = None,
    offline: bool = True,
) -> Plan:
    """Every removal this clone's state proves safe. Never raises. Offline it
    never writes; online it refreshes remote-tracking refs first and asks the
    product's own remote which branches open pull requests still use."""
    now = time.time() if now is None else now
    result = Plan(remote=gitstate.push_remote(project_dir), online=not offline)
    remote = result.remote

    records = gitstate.worktree_records(project_dir)
    if records is None:
        result.problems.append("could not list worktrees, so nothing was checked")
        return result
    if not records:
        return result  # not a git repository: nothing to tidy and nothing went wrong

    fetched = True
    if not offline:
        fetched, detail = _git_write(project_dir, "fetch", "--prune", "--quiet", remote)
        if not fetched:
            result.problems.append(
                f"could not fetch from {remote} ({detail or 'no detail'}); remote branches were "
                "not checked against the remote's current state"
            )

    local = _refs(project_dir, "refs/heads/")
    remote_refs = _refs(project_dir, f"refs/remotes/{remote}/")
    if local is None or remote_refs is None:
        result.problems.append("could not list branches, so nothing was checked")
        return result

    names = long_lived_names(project_dir, remote)
    proof_refs = [r for r in (*remote_refs, *local) if is_long_lived(_short(r, remote), names)]
    result.long_lived = sorted({_short(r, remote) for r in proof_refs})
    # Which long-lived ref proves each ref integrated: the first that reaches it.
    # A remote deletion is proven only by a remote long-lived branch: a local one
    # may hold merges nobody has pushed, and deleting the remote copy on their
    # strength would leave those commits on this machine alone.
    proven_by: dict[str, str] = {}
    proven_remotely: dict[str, str] = {}
    for ref in proof_refs:
        reached = _refs(project_dir, "refs/heads/", f"refs/remotes/{remote}/", merged=ref)
        if reached is None:
            result.problems.append(f"could not compare branches with {_shown(ref)}")
            continue
        for name in reached:
            proven_by.setdefault(name, ref)
            if ref.startswith("refs/remotes/"):
                proven_remotely.setdefault(name, ref)

    report = stranded_work.scan(project_dir, now=now, roots=roots, branches=False)
    result.problems.extend(report.problems)
    rows = {r.path: r for r in report.worktrees}
    held = gitstate.held_branches(records)
    freed: set[str] = set()

    for index, record in enumerate(records):
        path = record.get("worktree")
        if not path:
            continue
        gone = gitstate.record_is_gone(record)
        if gone is True and "locked" not in record:
            result.actions.append(Action(
                PRUNE_WORKTREE, path, "", "its directory is gone; only git's record of it remains",
                ("git", "worktree", "prune"),
            ))
            continue
        action = _sibling_removal(record, index, rows, local, proven_by, names)
        if action:
            result.actions.append(action)
            freed.add(gitstate.record_branch(record) or "")

    unproven: list[tuple[str, str]] = []
    for ref, sha in sorted(local.items()):
        name = _short(ref, remote)
        if is_long_lived(name, names) or (name in held and name not in freed):
            continue
        if ref not in proven_by:
            unproven.append((name, sha))
            continue
        via = "; checked out only in a worktree removed first" if name in freed else ""
        result.actions.append(Action(
            DELETE_BRANCH, name, sha, f"reachable from {_shown(proven_by[ref])}{via}",
            _delete_branch_command(name, sha), proven_by=proven_by[ref],
        ))

    if not offline:
        _prove_by_merged_pr(project_dir, result, unproven)

    in_use: set[str] | None = None
    pr_numbers: dict[str, int] = {}
    if not offline:
        in_use, pr_numbers = _branches_in_use(project_dir)
    deleted_local = {a.target for a in result.actions if a.kind == DELETE_BRANCH}
    for ref, sha in sorted(remote_refs.items()):
        name = _short(ref, remote)
        if is_long_lived(name, names) or ref not in proven_remotely:
            continue
        if f"refs/heads/{name}" in local and name not in deleted_local:
            continue  # a local branch of that name is still in use
        if in_use is not None and name in in_use:
            result.notes.append(
                f"kept {remote}/{name}: open pull request #{pr_numbers.get(name)} uses it, and "
                "deleting it would close or orphan that request"
            )
            continue
        if offline:
            unchecked = OPEN_PR_UNCHECKED
        elif not fetched:
            unchecked = "not checked: the fetch failed, so the remote's current state is unknown"
        elif in_use is None:
            unchecked = "not checked: could not list open pull requests (is `gh` installed and signed in?)"
        else:
            unchecked = None
        result.actions.append(Action(
            DELETE_REMOTE_BRANCH, f"{remote}/{name}", sha, f"reachable from {_shown(proven_remotely[ref])}",
            ("git", "push", remote, "--delete", f"refs/heads/{name}"),
            unchecked=unchecked, proven_by=proven_remotely[ref],
        ))

    # An environment branch kept level with a long-lived one (`staging` at `main`)
    # reads as merged. Such a branch is always pushed, so a local branch with no
    # remote namesake — a scratch branch cut from main with nothing on it — is
    # not what this warns about.
    tips = {sha: _short(r, remote) for r, sha in (*remote_refs.items(), *local.items()) if r in proof_refs}
    pushed = {_short(r, remote) for r in remote_refs}
    for action in result.actions:
        if action.kind == DELETE_BRANCH and action.target not in pushed:
            continue
        if action.kind in (DELETE_BRANCH, DELETE_REMOTE_BRANCH) and action.sha in tips:
            result.notes.append(
                f"{action.target} points at the same commit as {tips[action.sha]}. If it is a "
                f"long-lived branch, list it in project-preferences `{LONG_LIVED_LABEL}` and it "
                "will never be proposed."
            )
    result.actions.sort(key=lambda a: (KIND_ORDER.index(a.kind), a.target))
    return result


def _prove_by_merged_pr(project_dir: Path, result: Plan, unproven: list[tuple[str, str]]) -> None:
    """Squash and rebase merges leave a merged branch's own commits on no
    long-lived branch, so its proof is a merged pull request whose head was this
    exact commit. Asked only for branches that look merged that way: the upstream
    is gone, or the product merges by squash or rebase. Bounded and reported."""
    track = _upstream_gone_and_age(project_dir)
    squashing = rewrites_history(project_dir)
    candidates = [
        (name, sha) for name, sha in unproven
        if squashing or track.get(f"refs/heads/{name}", (False, 0.0))[0]
    ]
    candidates.sort(key=lambda c: track.get(f"refs/heads/{c[0]}", (False, 0.0))[1])
    for name, sha in candidates[:MAX_PR_PROOFS]:
        number = _merged_pr_for(project_dir, name, sha)
        if number is None:
            result.problems.append(
                f"could not ask whether {name}'s pull request merged (is `gh` installed and signed in?)"
            )
            return
        if number is not False:
            result.actions.append(Action(
                DELETE_BRANCH, name, sha,
                f"its pull request #{number} merged with this exact commit as its head",
                _delete_branch_command(name, sha), proven_by=f"{PR_PROOF}{number}",
            ))
    if len(candidates) > MAX_PR_PROOFS:
        result.problems.append(
            f"{len(candidates) - MAX_PR_PROOFS} more branch(es) whose pull request may have merged "
            f"were not checked this run (at most {MAX_PR_PROOFS} per run, oldest first)"
        )


def _sibling_removal(record, index, rows, local, proven_by, names) -> Action | None:
    """A removal for a sibling worktree holding a finished feature branch, idle a
    week, or None. Every condition is a reason to keep it; each is checked."""
    path = record["worktree"]
    row = rows.get(str(stranded_work._resolve(path)))
    branch = gitstate.record_branch(record)
    if index == 0 or row is None or row.is_current or "locked" in record:
        return None
    if not branch or is_long_lived(branch, names):
        return None  # a detached or long-lived checkout is kept for its own sake
    if row.dirty != 0 or row.state != stranded_work.IDLE:
        return None  # unknown dirtiness or liveness is not clean or idle
    ref = f"refs/heads/{branch}"
    if ref not in proven_by or local.get(ref) != record.get("HEAD"):
        return None
    days = stranded_work.IDLE_AFTER_SECONDS // 86400
    return Action(
        REMOVE_WORKTREE, path, record["HEAD"],
        f"clean, no activity for {days}+ days, and {branch} is reachable from {_shown(proven_by[ref])}",
        ("git", "worktree", "remove", path), proven_by=proven_by[ref],
    )


# --- applying -----------------------------------------------------------------

REMOVED, KEPT, SKIPPED, FAILED = "removed", "kept", "skipped", "failed"


@dataclass(frozen=True)
class Outcome:
    kind: str
    target: str
    result: str  # removed | kept | skipped | failed
    detail: str = ""


def _still_reaches(project_dir: Path, sha: str, proven_by: str) -> bool:
    if proven_by.startswith(PR_PROOF):
        return True  # the merged request was asked moments ago; its head cannot change
    return _git(project_dir, "merge-base", "--is-ancestor", sha, proven_by) is not None


def _record_for(project_dir: Path, path: str) -> dict | None:
    for record in gitstate.worktree_records(project_dir) or []:
        if record.get("worktree") == path:
            return record
    return None


def _reprove(project_dir: Path, action: Action, remote: str) -> str | None:
    """Why ``action`` no longer holds, or None when it still does. Asked of the
    state as it is now, not as the dry run saw it."""
    if action.kind == PRUNE_WORKTREE:
        record = _record_for(project_dir, action.target)
        if record is None:
            return "already gone"
        if "locked" in record or gitstate.record_is_gone(record) is not True:
            return "its directory is back, or it was locked"
        return None
    if action.kind == REMOVE_WORKTREE:
        record = _record_for(project_dir, action.target)
        if record is None or "locked" in record:
            return "it was removed or locked since the dry run"
        if record.get("HEAD") != action.sha:
            return "it moved to another commit since the dry run"
        status = _git(Path(action.target), "status", "--porcelain")
        if status is None or status.strip():
            return "it has uncommitted or untracked files now"
    elif action.kind == DELETE_BRANCH:
        tip = _git(project_dir, "rev-parse", "--verify", "--quiet", f"refs/heads/{action.target}")
        if (tip or "").strip() != action.sha:
            return "it moved since the dry run"
        records = gitstate.worktree_records(project_dir)
        if records is None:
            return "could not check whether it is checked out"
        if action.target in gitstate.held_branches(records):
            return "it is checked out now"
    elif action.kind == DELETE_REMOTE_BRANCH:
        name = action.target.removeprefix(f"{remote}/")
        out = _git(project_dir, "ls-remote", remote, f"refs/heads/{name}")
        if out is None:
            return f"could not ask {remote} for its current tip"
        if not out.strip():
            return f"{remote} no longer has it"
        if out.split()[0] != action.sha:
            return f"it moved on {remote} since the dry run"
    if action.sha and action.proven_by and not _still_reaches(project_dir, action.sha, action.proven_by):
        return f"{_shown(action.proven_by)} no longer reaches it"
    return None


def apply(
    project_dir: Path,
    approved: str,
    *,
    now: float | None = None,
    roots: list[Path] | None = None,
    offline: bool = False,
) -> tuple[Plan, list[Outcome]]:
    """Remove exactly the set whose fingerprint is ``approved``. Returns the plan
    as recomputed and one outcome per action; no outcomes when the set changed."""
    current = plan(project_dir, now=now, roots=roots, offline=offline)
    if current.fingerprint != approved:
        return current, []
    outcomes: list[Outcome] = []
    pruned = False
    for action in current.actions:
        if action.unchecked:
            outcomes.append(Outcome(action.kind, action.target, SKIPPED, action.unchecked))
            continue
        reason = _reprove(project_dir, action, current.remote)
        if reason:
            outcomes.append(Outcome(action.kind, action.target, KEPT, reason))
            continue
        if action.kind == PRUNE_WORKTREE:
            if not pruned:
                ok, detail = _git_write(project_dir, "worktree", "prune")
                pruned = ok
            else:
                ok, detail = True, ""
        else:
            ok, detail = _git_write(project_dir, *action.command[1:])
        if ok and action.kind == DELETE_BRANCH:
            # update-ref leaves the branch's tracking config behind; a later
            # branch of the same name would inherit it. Absent config is fine.
            _git_write(project_dir, "config", "--remove-section", f"branch.{action.target}")
        outcomes.append(Outcome(action.kind, action.target, REMOVED if ok else FAILED, "" if ok else detail))
    return current, outcomes


# --- rendering ----------------------------------------------------------------

_HEADINGS = {
    REMOVE_WORKTREE: "Remove worktrees (another session's: clean, merged, idle)",
    PRUNE_WORKTREE: "Prune worktree entries whose directory is gone",
    DELETE_BRANCH: "Delete local branches (merged)",
    DELETE_REMOTE_BRANCH: "Delete remote branches (merged)",
}


def render(result: Plan) -> str:
    changed = "remote-tracking refs were refreshed; nothing else was changed" if result.online else "nothing was changed"
    lines = [f"GIT TIDY — dry run; {changed}."]
    if result.long_lived:
        lines.append(f"Long-lived (never deleted; proof is reaching one): {', '.join(result.long_lived)}")
    for kind in KIND_ORDER:
        group = [a for a in result.actions if a.kind == kind]
        if not group:
            continue
        lines.append(f"{_HEADINGS[kind]}:")
        for a in group:
            sha = f"  {a.sha[:10]}" if a.sha else ""
            lines.append(f"  {a.target}{sha}  — {a.proof}")
            lines.append(f"      {' '.join(a.command)}")
            if a.unchecked:
                lines.append(f"      {a.unchecked}")
    if not result.actions:
        lines.append(
            "Nothing to tidy." if result.fully_checked else "Nothing found, but not everything was checked:"
        )
    for note in result.notes:
        lines.append(f"note: {note}")
    for problem in result.problems:
        lines.append(f"WARNING: {problem}")
    if result.actions:
        remote = any(a.kind == DELETE_REMOTE_BRANCH for a in result.actions)
        lines.append(
            f"{len(result.actions)} removal(s), fingerprint {result.fingerprint}. "
            f"`prawduct-hook git-tidy --apply {result.fingerprint}` removes exactly these, "
            "re-checking each one's proof first."
            + (" A deleted remote branch is restored only by pushing it again." if remote else "")
        )
    return "\n".join(lines)


def render_applied(result: Plan, approved: str, outcomes: list[Outcome]) -> str:
    if result.fingerprint != approved:
        return (
            f"GIT TIDY — nothing was changed: the set is no longer the one approved "
            f"(fingerprint {approved} is now {result.fingerprint}). Here is the current dry run; "
            "approve it again to apply it.\n" + render(result)
        )
    lines = ["GIT TIDY — applied."]
    for o in outcomes:
        lines.append(f"  {o.result:<8} {o.target}" + (f" — {o.detail}" if o.detail else ""))
    for problem in result.problems:
        lines.append(f"WARNING: {problem}")
    return "\n".join(lines)


def to_json(result: Plan) -> str:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "fingerprint": result.fingerprint,
        "fully_checked": result.fully_checked,
        **asdict(result),
    }
    return json.dumps(payload)


def applied_json(result: Plan, approved: str, outcomes: list[Outcome]) -> str:
    return json.dumps({
        "schema_version": SCHEMA_VERSION,
        "approved": approved,
        "fingerprint": result.fingerprint,
        "applied": result.fingerprint == approved,
        "outcomes": [asdict(o) for o in outcomes],
        "problems": result.problems,
    })


USAGE = "usage: prawduct-hook git-tidy [--offline] [--json] [--apply <fingerprint>]"


def _parse(argv: list[str]) -> tuple[dict, str | None]:
    opts: dict = {"offline": False, "json": False, "apply": None}
    args = iter(argv)
    for arg in args:
        if arg == "--offline":
            opts["offline"] = True
        elif arg == "--json":
            opts["json"] = True
        elif arg == "--apply":
            value = next(args, None)
            if not value or value.startswith("-"):
                return opts, "--apply needs the fingerprint the dry run printed"
            opts["apply"] = value
        else:
            return opts, f"unknown argument {arg!r}"
    return opts, None


def git_tidy_cmd(project_dir: Path, argv: list[str]) -> int:
    """``prawduct-hook git-tidy``. Dry run: exit 0 when a plan was produced (an
    empty one included), 3 when git could not be read at all, which is never
    "nothing to tidy". ``--apply``: exit 0 when every approved removal happened,
    1 when the set changed or any removal was kept, skipped or failed. Exit 2 on
    bad usage."""
    opts, error = _parse(argv)
    if error:
        print(f"git-tidy: {error}; {USAGE}", file=sys.stderr)
        return 2
    if opts["apply"]:
        result, outcomes = apply(project_dir, opts["apply"], offline=opts["offline"])
        print(applied_json(result, opts["apply"], outcomes) if opts["json"]
              else render_applied(result, opts["apply"], outcomes))
        approved_set = result.fingerprint == opts["apply"]
        return 0 if approved_set and all(o.result == REMOVED for o in outcomes) else 1
    result = plan(project_dir, offline=opts["offline"])
    print(to_json(result) if opts["json"] else render(result))
    nothing_read = result.problems and not result.actions and not result.long_lived
    return 3 if nothing_read else 0
