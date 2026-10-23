"""Git hygiene: which branches and worktrees can go, and the proof that says so.

One rule governs everything here: a ref or worktree is removed only when what it
holds is provably carried by something that stays. Age, inactivity and "looks
abandoned" are never proof. The proof for a branch is that its tip is reachable
from a LONG-LIVED branch (the remote's default branch, the resolved base,
``main``/``master``/``develop``/``trunk``, ``release/*``, and whatever the
product lists in its ``Long-lived branches`` preference row). Being pushed is not
proof: a pushed, unmerged branch has nothing integrated anywhere.

This module classifies; it does not decide policy. Three readers:

* ``prawduct-hook git-tidy`` — the dry run every removal starts from: each
  action, the commit it is about, its proof, and the exact git command.
* The ``tidy-available`` advisory, which proposes that dry run at session start.
* The stranded-branch scan shares ``gitstate.held_branches``, so "checked out"
  has one definition across both.

What is never a candidate, whatever its state: a long-lived branch; a branch
checked out in a worktree somebody could be working in; the main worktree and
the current one; a locked worktree (the harness locks an agent's worktree while
the agent runs); a worktree with tracked changes or untracked files; and a
detached or long-lived-branch worktree. That last is a checkout kept for its
own sake, such as an install a plugin runs from, so being clean and merged says
nothing about whether it is finished. A sibling worktree is proposed only when it
holds a finished feature branch and has shown no sign of life for a week.

Reads run with ``GIT_OPTIONAL_LOCKS=0`` so observing a sibling never rewrites its
index. A read that fails is a named problem, and the dry run says "nothing to
tidy" only when every part of it was checked.
"""

from __future__ import annotations

import hashlib
import json
import os
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
CLEANUP_OFF = "off"

# Action kinds, in the order they run: removing a worktree frees its branch, so
# worktrees go before branches, and local deletes go before remote ones.
REMOVE_WORKTREE = "remove-worktree"
PRUNE_WORKTREE = "prune-worktree"
DELETE_BRANCH = "delete-branch"
DELETE_REMOTE_BRANCH = "delete-remote-branch"
KIND_ORDER = (REMOVE_WORKTREE, PRUNE_WORKTREE, DELETE_BRANCH, DELETE_REMOTE_BRANCH)

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


@dataclass
class Plan:
    remote: str = "origin"
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


# --- reading git --------------------------------------------------------------


def _git(cwd: Path, *args: str) -> str | None:
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    rc, out, _err = evidence.run_git(cwd, *args, env=env)
    return out if rc == 0 else None


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


def _short(refname: str, remote: str) -> str:
    """The branch name a ref carries: ``refs/heads/x`` and ``refs/remotes/<remote>/x`` → ``x``."""
    for prefix in ("refs/heads/", f"refs/remotes/{remote}/"):
        if refname.startswith(prefix):
            return refname[len(prefix):]
    return refname


# --- policy -------------------------------------------------------------------


def cleanup_enabled(project_dir: Path) -> bool:
    """False only when ``Branch cleanup`` says ``off``. Absent, unreadable or
    unrecognised all read as the default, ``propose``."""
    from .core import read_preference_row  # noqa: PLC0415 — core is heavy; only policy needs it

    row = read_preference_row(project_dir, CLEANUP_LABEL)
    return row.value != CLEANUP_OFF


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


def plan(
    project_dir: Path,
    *,
    now: float | None = None,
    roots: list[Path] | None = None,
    offline: bool = True,
) -> Plan:
    """Every removal this clone's state proves safe. Never raises, never writes.

    ``offline`` is the only mode so far: the open-pull-request check a remote
    deletion needs is reported as unchecked rather than guessed."""
    now = time.time() if now is None else now
    result = Plan(remote=gitstate.push_remote(project_dir))
    remote = result.remote

    records = gitstate.worktree_records(project_dir)
    if records is None:
        result.problems.append("could not list worktrees, so nothing was checked")
        return result
    if not records:
        return result  # not a git repository: nothing to tidy and nothing went wrong

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
            result.problems.append(f"could not compare branches with {_short(ref, remote)}")
            continue
        shown = ref.removeprefix("refs/").removeprefix("heads/").removeprefix("remotes/")
        for name in reached:
            proven_by.setdefault(name, shown)
            if ref.startswith("refs/remotes/"):
                proven_remotely.setdefault(name, shown)

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
        action = _sibling_removal(record, index, rows, local, proven_by, names, remote)
        if action:
            result.actions.append(action)
            freed.add(gitstate.record_branch(record) or "")

    for ref, sha in sorted(local.items()):
        name = _short(ref, remote)
        if is_long_lived(name, names) or (name in held and name not in freed) or ref not in proven_by:
            continue
        via = "; checked out only in a worktree removed first" if name in freed else ""
        result.actions.append(Action(
            DELETE_BRANCH, name, sha, f"reachable from {proven_by[ref]}{via}",
            ("git", "branch", "-d", "--", name),
        ))

    deleted_local = {a.target for a in result.actions if a.kind == DELETE_BRANCH}
    for ref, sha in sorted(remote_refs.items()):
        name = _short(ref, remote)
        if is_long_lived(name, names) or ref not in proven_remotely:
            continue
        if f"refs/heads/{name}" in local and name not in deleted_local:
            continue  # a local branch of that name is still in use
        result.actions.append(Action(
            DELETE_REMOTE_BRANCH, f"{remote}/{name}", sha, f"reachable from {proven_remotely[ref]}",
            ("git", "push", remote, "--delete", f"refs/heads/{name}"),
            unchecked=OPEN_PR_UNCHECKED if offline else None,
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


def _sibling_removal(record, index, rows, local, proven_by, names, remote) -> Action | None:
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
        f"clean, no activity for {days}+ days, and {branch} is reachable from {proven_by[ref]}",
        ("git", "worktree", "remove", path),
    )


# --- rendering ----------------------------------------------------------------

_HEADINGS = {
    REMOVE_WORKTREE: "Remove worktrees (another session's: clean, merged, idle)",
    PRUNE_WORKTREE: "Prune worktree entries whose directory is gone",
    DELETE_BRANCH: "Delete local branches (merged)",
    DELETE_REMOTE_BRANCH: "Delete remote branches (merged)",
}


def render(result: Plan) -> str:
    lines = ["GIT TIDY — dry run; nothing was changed."]
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
            f"{len(result.actions)} removal(s), fingerprint {result.fingerprint}."
            + (" A deleted remote branch is restored only by pushing it again." if remote else "")
        )
    return "\n".join(lines)


def to_json(result: Plan) -> str:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "fingerprint": result.fingerprint,
        "fully_checked": result.fully_checked,
        **asdict(result),
    }
    return json.dumps(payload)


USAGE = "usage: prawduct-hook git-tidy [--offline] [--json]"


def git_tidy_cmd(project_dir: Path, argv: list[str]) -> int:
    """``prawduct-hook git-tidy``. Exit 0 when a plan was produced (an empty one
    included); 2 on bad usage; 3 when git could not be read at all, which is never
    "nothing to tidy"."""
    known = {"--offline", "--json"}
    unknown = [a for a in argv if a not in known]
    if unknown:
        print(f"git-tidy: unknown argument(s) {unknown}; {USAGE}", file=sys.stderr)
        return 2
    result = plan(project_dir, offline=True)
    print(to_json(result) if "--json" in argv else render(result))
    nothing_read = result.problems and not result.actions and not result.long_lived
    return 3 if nothing_read else 0
