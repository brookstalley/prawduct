"""Stranded work: local branches no remote carries, and worktrees nobody is in.

Finished work gets stranded where no reader looks. A reviewed fix can sit on a
local-only branch while the next session plans to build it again, and a clone
collects worktrees with no sign of which still have an agent in them. This
module answers both questions from git and file timestamps, read-only, for
three readers:

* ``prawduct-hook worktrees`` — the full table, on demand.
* The session briefing — sibling WORKTREES as counts only.
* The ``stranded-branch`` advisory (``stranded_branch_probes``) — one per
  stranded BRANCH, by name, dismissible, resolving itself once the branch is
  pushed or deleted.

The briefing names no worktree, path or branch. A list of sibling worktrees
reads to an agent as a menu of work to pick up, and agents have followed it
into a directory where another live session was working (owner ruling on #410,
reaffirmed 2026-09-28). A stranded branch is different: it is checked out
nowhere, so it is nobody's live work, and an advisory naming it points at
nothing another session holds.

**Liveness is the newest of several signals, and the report names which one
won.** No single signal is trustworthy on its own:

* Claude Code transcripts — the newest ``*.jsonl`` directly in
  ``<root>/projects/<encoded path>/``, over EVERY config root. Several accounts
  (and devcontainer twins) each keep their own root, so the same worktree can
  have transcripts of very different ages in different roots, and only the
  newest across all of them says anything about now. A subagent's transcript
  lives under its PARENT session's directory, so a harness agent worktree has
  none of its own; the other signals cover it.
* The worktree's HEAD reflog — commits, checkouts, resets.
* Its ``.prawduct/.session-start`` marker — a governed session opened there.
* Its newest modified or untracked file.

Two tempting signals are deliberately absent. The git index's mtime moves
whenever anyone runs ``git status`` there, observers included, so it would
report the probe itself as activity; every git call here runs with
``GIT_OPTIONAL_LOCKS=0`` so that observing a sibling never rewrites its index.
A process whose cwd is the worktree misses desktop-app sessions, which run with
cwd ``/``.

Advice fails soft, but not silent: a probe failure degrades to a missing signal
or a named problem in the report, never an exception into SessionStart, and a
reader told "nothing found" is told whether anything was checked.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import evidence, gitstate

#: Any signal this recent means an agent is plausibly working there now.
ACTIVE_WITHIN_SECONDS = 30 * 60
#: No signal for this long: nobody has touched the worktree in a week.
IDLE_AFTER_SECONDS = 7 * 24 * 3600

#: The whole worktree scan, not each call. The briefing runs at SessionStart
#: in every governed repo, and a clone can hold dozens of worktrees; past this,
#: the rest are reported unchecked rather than making the session wait. One
#: wedged call is bounded separately, by the framework-wide git budget
#: (``PRAWDUCT_GIT_TIMEOUT``, read by ``evidence.run_git``).
SCAN_BUDGET_SECONDS = 4.0
#: Dirty files stat'd per worktree when looking for the newest edit. A tree
#: with thousands of untracked files still answers "dirty", just from a sample.
_DIRTY_STAT_CAP = 500

SCHEMA_VERSION = 1

ACTIVE, RECENT, IDLE, UNKNOWN, MISSING = "active", "recent", "idle", "unknown", "missing"


@dataclass(frozen=True)
class Signal:
    source: str  # "transcript" | "reflog" | "session-start" | "file-edit"
    at: float  # epoch seconds


@dataclass
class WorktreeRow:
    path: str
    branch: str | None  # None = detached HEAD
    is_current: bool
    ephemeral: str | None  # gitstate.ephemeral_kind_of: "agent" | "workflow" | None
    state: str = UNKNOWN
    last_activity: Signal | None = None
    dirty: int | None = None  # None = could not ask git


@dataclass
class BranchRow:
    name: str
    last_commit: float
    #: Commits reachable from no remote. Counted only on request (the table);
    #: None when not requested or when the count failed.
    unique_commits: int | None = None


@dataclass
class Report:
    worktrees: list[WorktreeRow] = field(default_factory=list)
    branches: list[BranchRow] = field(default_factory=list)
    #: False when git could not list the worktrees at all — every count below
    #: is then "not checked", never "none found".
    worktrees_checked: bool = True
    #: False when the repo has no remote-tracking refs: then every branch is
    #: "on no remote" and flagging them would say nothing, so none are.
    has_remotes: bool = True
    problems: list[str] = field(default_factory=list)


# --- pure classification ------------------------------------------------------


def classify(last: Signal | None, now: float) -> str:
    """The liveness class for a worktree whose newest signal is ``last``.

    ``None`` is UNKNOWN, never IDLE: no signal is an absence of evidence, and
    calling it idle would invite someone to treat a live tree as abandoned."""
    if last is None:
        return UNKNOWN
    age = now - last.at
    if age <= ACTIVE_WITHIN_SECONDS:
        return ACTIVE
    if age >= IDLE_AFTER_SECONDS:
        return IDLE
    return RECENT


def newest(signals: list[Signal | None]) -> Signal | None:
    present = [s for s in signals if s is not None]
    return max(present, key=lambda s: s.at) if present else None


def encode_project_dir(path: str | Path) -> str:
    """Claude Code's transcript directory name for a working directory: every
    character that is not an ASCII letter or digit becomes ``-``. Observed on
    real roots: ``/`` and ``.`` both map (``.claude/worktrees`` appears as
    ``--claude-worktrees``), and a macOS ``/tmp`` path appears resolved, as
    ``-private-tmp``, which is why callers pass a resolved path."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


# --- signal probes (each returns None on any failure) -------------------------


def config_roots(env: dict | None = None, home: Path | None = None) -> list[Path]:
    """Every Claude config root that holds transcripts: ``$CLAUDE_CONFIG_DIR``,
    ``~/.claude`` and each ``~/.claude-*``. Deduplicated by resolved path,
    because ``$CLAUDE_CONFIG_DIR`` usually points at one of the others. A home
    that cannot be resolved yields no roots, not an exception."""
    env = os.environ if env is None else env
    try:
        home = Path.home() if home is None else home
    except (RuntimeError, KeyError, OSError):
        return []
    candidates: list[Path] = []
    if env.get("CLAUDE_CONFIG_DIR"):
        candidates.append(Path(env["CLAUDE_CONFIG_DIR"]).expanduser())
    candidates.append(home / ".claude")
    try:
        candidates.extend(sorted(home.glob(".claude-*")))
    except OSError:
        pass
    roots: list[Path] = []
    seen: set[str] = set()
    for root in candidates:
        try:
            if not (root / "projects").is_dir():
                continue
            key = str(root.resolve())
        except (OSError, RuntimeError):
            continue
        if key not in seen:
            seen.add(key)
            roots.append(root)
    return roots


def transcript_signal(worktree: Path, roots: list[Path]) -> Signal | None:
    """Newest top-level transcript for ``worktree`` across every root. Only
    modification times are read; transcript content never is."""
    name = encode_project_dir(worktree)
    best: float | None = None
    for root in roots:
        try:
            for entry in os.scandir(root / "projects" / name):
                if entry.name.endswith(".jsonl") and entry.is_file():
                    at = entry.stat().st_mtime
                    if best is None or at > best:
                        best = at
        except OSError:
            continue
    return Signal("transcript", best) if best is not None else None


def _mtime_signal(path: Path, source: str) -> Signal | None:
    try:
        return Signal(source, path.stat().st_mtime)
    except OSError:
        return None


def _git(cwd: Path, *args: str, strip: bool = True) -> str | None:
    """stdout of one git call through the shared runner, or None if git could
    not answer (including output that is not valid UTF-8, which the runner
    reports as a failed call). ``GIT_OPTIONAL_LOCKS=0`` so a read never
    refreshes another tree's index."""
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    rc, out, _err = evidence.run_git(cwd, *args, env=env, strip=strip)
    return out if rc == 0 else None


def dirty_signal(worktree: Path) -> tuple[int | None, Signal | None]:
    """``(dirty file count, newest edit)``. The count is None when git could not
    be asked; the signal is None when nothing is dirty or nothing could be
    stat'd (a deleted file has no mtime)."""
    out = _git(worktree, "status", "--porcelain", "-z", strip=False)
    if out is None:
        return None, None
    paths: list[str] = []
    entries = iter(e for e in out.split("\0") if e)
    for entry in entries:
        code, rel = entry[:2], entry[3:]
        paths.append(rel)
        if code[0] in "RC":  # a rename or copy carries its source as the next field
            next(entries, None)
    best: float | None = None
    for rel in paths[:_DIRTY_STAT_CAP]:
        try:
            at = (worktree / rel).lstat().st_mtime
        except OSError:
            continue
        if best is None or at > best:
            best = at
    return len(paths), (Signal("file-edit", best) if best is not None else None)


# --- the scan -----------------------------------------------------------------


def _resolve(path: str | Path) -> Path:
    try:
        return Path(path).resolve()
    except (OSError, RuntimeError):
        return Path(path)


def _scan_worktree(record: dict, *, current: Path, roots: list[Path], now: float) -> WorktreeRow:
    path = _resolve(record["worktree"])
    branch = gitstate.record_branch(record)
    row = WorktreeRow(
        path=str(path),
        branch=branch,
        is_current=path == current,
        ephemeral=gitstate.ephemeral_kind_of(path, branch),
    )
    gone = gitstate.record_is_gone(record)
    # None: unreadable, or locked with its storage absent — neither is a missing
    # tree, so say nothing about its liveness.
    if gone is None:
        return row
    if gone:
        row.state = MISSING
        return row
    git_dir = _git(path, "rev-parse", "--absolute-git-dir")
    reflog = _mtime_signal(Path(git_dir) / "logs" / "HEAD", "reflog") if git_dir else None
    row.dirty, edit = dirty_signal(path)
    row.last_activity = newest([
        transcript_signal(path, roots),
        reflog,
        _mtime_signal(path / ".prawduct" / ".session-start", "session-start"),
        edit,
    ])
    row.state = classify(row.last_activity, now)
    return row


def stranded_branches(
    project_dir: Path, *, records: list[dict] | None = None, count_commits: bool = False
) -> tuple[list[BranchRow], bool, str | None]:
    """``(branches, has_remotes, problem)`` — local branches checked out in no
    live worktree whose tip no remote-tracking ref reaches, at any age.

    No age floor: a branch checked out nowhere already has nobody on it, and
    the incident this exists for was 18 hours old — a reviewed fix built one
    afternoon and planned again the next morning.

    A worktree whose directory is gone does not hold its branch: git still lists it, but nobody can be working there, and
    counting it as "checked out" would hide exactly the work a deleted tree
    leaves behind.

    ``count_commits`` adds one ``rev-list --count`` per stranded branch — the
    table wants it, the advisory and the briefing do not."""
    if records is None:
        records = gitstate.worktree_records(project_dir)
        if records is None:
            return [], True, "could not list worktrees, so could not tell which branches are checked out"
    if not records:  # not a git repository: nothing to compare, and nothing went wrong
        return [], True, None
    held: set[str] = set()
    for record in records:
        branch = gitstate.record_branch(record)
        # Unreadable (None) is not gone: the branch stays held.
        if branch and gitstate.record_is_gone(record) is not True:
            held.add(branch)

    remotes = _git(project_dir, "for-each-ref", "--format=%(refname)", "refs/remotes/")
    if remotes is None:
        return [], True, "could not list remote-tracking refs"
    if not remotes.strip():
        return [], False, None
    heads = _git(
        project_dir, "for-each-ref",
        # `lstrip=2`, not `short`: git lengthens `short` to `heads/<name>` when a tag
        # shares the name, and the branch would then match no worktree's branch.
        "--format=%(refname:lstrip=2)%09%(objectname)%09%(committerdate:unix)", "refs/heads/",
    )
    # One walk for every branch at once: a tip reachable from no remote IS a
    # commit no remote carries, and a tip any remote reaches means every commit
    # under it is carried too. So membership of the tip answers the question
    # without a rev-list per branch.
    uncarried = _git(project_dir, "rev-list", "--branches", "--not", "--remotes")
    if heads is None or uncarried is None:
        return [], True, "could not compare local branches with the remotes"
    tips = set(uncarried.split())
    rows: list[BranchRow] = []
    for line in heads.splitlines():
        try:
            name, sha, stamp = line.split("\t")
            last = float(stamp)
        except ValueError:
            continue
        if name in held or sha not in tips:
            continue
        row = BranchRow(name=name, last_commit=last)
        if count_commits:
            # `refs/heads/` makes the argument a ref, never a path: a branch named
            # like a directory (`docs`, `tests`) is otherwise ambiguous to git.
            count = _git(project_dir, "rev-list", "--count", f"refs/heads/{name}", "--not", "--remotes")
            row.unique_commits = int(count) if count and count.isdigit() else None
        rows.append(row)
    return rows, True, None


def scan(
    project_dir: Path,
    *,
    now: float | None = None,
    roots: list[Path] | None = None,
    branches: bool = True,
    count_commits: bool = False,
    budget_seconds: float = SCAN_BUDGET_SECONDS,
) -> Report:
    """The report. Never raises: a failed probe is a named problem.

    ``branches=False`` skips the branch comparison — the briefing's case, since
    stranded branches reach the session through their advisory instead."""
    now = time.time() if now is None else now
    roots = config_roots() if roots is None else roots
    report = Report()
    records = gitstate.worktree_records(project_dir)
    if records is None:
        report.worktrees_checked = False
        report.problems.append("could not list worktrees")
        return report
    toplevel = _git(project_dir, "rev-parse", "--show-toplevel")
    current = _resolve(toplevel) if toplevel else _resolve(project_dir)
    deadline = time.monotonic() + budget_seconds
    skipped = 0
    for record in records:
        if "worktree" not in record:
            continue
        if time.monotonic() > deadline:
            path = _resolve(record["worktree"])
            report.worktrees.append(WorktreeRow(
                path=str(path),
                branch=gitstate.record_branch(record),
                is_current=path == current,
                ephemeral=None,
            ))
            skipped += 1
            continue
        report.worktrees.append(_scan_worktree(record, current=current, roots=roots, now=now))
    if skipped:
        report.problems.append(
            f"{skipped} worktree(s) not checked within the {budget_seconds:g}s scan budget"
        )
    if branches:
        rows, report.has_remotes, problem = stranded_branches(
            project_dir, records=records, count_commits=count_commits
        )
        report.branches = rows
        if problem:
            report.problems.append(problem)
    return report


# --- renderers ----------------------------------------------------------------


def briefing_line(report: Report) -> str | None:
    """One line of WORKTREE counts for the session briefing, or None when there
    is nothing to say. Names no worktree, path or branch — see the module doc.
    When the scan could not run, the line says so: silence would read as
    "nothing to report" when nothing was checked."""
    if not report.worktrees_checked:
        return (
            "Worktrees: could not check sibling worktrees this session — "
            "`prawduct-hook worktrees` says why."
        )
    others = [w for w in report.worktrees if not w.is_current]
    idle = [w for w in others if w.state == IDLE]
    idle_dirty = sum(1 for w in idle if w.dirty)
    active = sum(1 for w in others if w.state == ACTIVE)
    unchecked = [p for p in report.problems if "scan budget" in p]
    parts: list[str] = []
    if idle:
        n = len(idle)
        dirty_note = f" ({idle_dirty} with uncommitted changes)" if idle_dirty else ""
        parts.append(f"{n} idle {IDLE_AFTER_SECONDS // 86400}+ days{dirty_note}")
    if active:
        parts.append(
            f"{active} other{'s' if active != 1 else ''} with an agent active in the last "
            f"{ACTIVE_WITHIN_SECONDS // 60} min"
        )
    if unchecked:
        parts.append(unchecked[0])
    if not parts:
        return None
    return (
        "Worktrees: " + " · ".join(parts) + ". `prawduct-hook worktrees` lists them. Tell the "
        "user; act on another worktree only when the user or an advisory asks you to."
    )


def _age(seconds: float) -> str:
    if seconds < 3600:
        return f"{int(seconds // 60)}m ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h ago"
    return f"{int(seconds // 86400)}d ago"


def render_table(report: Report, now: float) -> str:
    lines = ["WORKTREES (state · last agent activity · uncommitted files · branch · path)"]
    if not report.worktrees_checked:
        lines.append("  could not list worktrees (git failed here)")
    for w in report.worktrees:
        where = "this session" if w.is_current else w.path
        seen = f"{_age(now - w.last_activity.at)} via {w.last_activity.source}" if w.last_activity else "no signal"
        dirty = "?" if w.dirty is None else str(w.dirty)
        branch = w.branch or "(detached)"
        tag = f" [{w.ephemeral} worktree]" if w.ephemeral else ""
        state = "missing (run `git worktree prune`)" if w.state == MISSING else w.state
        lines.append(f"  {state:<8} {seen:<24} {dirty:>4}  {branch}  {where}{tag}")
    if not report.has_remotes:
        lines.append("BRANCHES: this repo has no remote-tracking refs, so none are compared.")
    elif report.branches:
        lines.append("LOCAL BRANCHES CHECKED OUT NOWHERE, WITH COMMITS NO REMOTE HAS")
        for b in report.branches:
            count = "?" if b.unique_commits is None else str(b.unique_commits)
            lines.append(f"  {b.name}  {count} commit(s)  last {_age(now - b.last_commit)}")
    elif report.worktrees_checked:
        lines.append("BRANCHES: none stranded.")
    for problem in report.problems:
        lines.append(f"note: {problem}")
    lines.append(
        "Liveness is inferred from timestamps: a session paused for a weekend looks idle. "
        "Tell the user what you see; act on another worktree only when the user or an "
        "advisory asks you to."
    )
    return "\n".join(lines)


def to_json(report: Report) -> str:
    payload = {"schema_version": SCHEMA_VERSION, **asdict(report)}
    return json.dumps(payload)


def worktrees_cmd(project_dir: Path, argv: list[str]) -> int:
    """``prawduct-hook worktrees [--json]``. Exit 0 whenever a report was
    produced, partial included (its problems are named in it); 2 on bad usage."""
    unknown = [a for a in argv if a != "--json"]
    if unknown:
        print(f"worktrees: unknown argument(s) {unknown}; usage: prawduct-hook worktrees [--json]",
              file=sys.stderr)
        return 2
    now = time.time()
    report = scan(project_dir, now=now, count_commits=True)
    print(to_json(report) if "--json" in argv else render_table(report, now))
    return 0
