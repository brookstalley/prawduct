"""Stranded work: local branches no remote carries, and worktrees nobody is in.

Finished work gets stranded where no reader looks. A reviewed fix can sit on a
local-only branch while the next session plans to build it again, and a clone
collects worktrees with no sign of which still have an agent in them. This
module answers both questions from git and file timestamps, read-only, for two
renderers: the session briefing (counts only) and ``prawduct-hook worktrees``
(the full table).

The briefing names NO branch, path or worktree. A list of sibling worktrees
reads to an agent as a menu of work to pick up, and agents have followed it
into a directory where another live session was working (owner ruling on #410,
reaffirmed 2026-09-28). Counts plus a command keep the signal and leave nothing
to wander toward.

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
report the probe itself as activity; every status call here passes
``--no-optional-locks`` so that observing a sibling never rewrites its index.
A process whose cwd is the worktree misses desktop-app sessions, which run with
cwd ``/``.

Advice fails soft: every probe failure degrades to a missing signal or a named
problem in the report, never an exception into SessionStart.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import gitstate

#: Any signal this recent means an agent is plausibly working there now.
ACTIVE_WITHIN_SECONDS = 30 * 60
#: No signal for this long: nobody has touched the worktree in a week.
IDLE_AFTER_SECONDS = 7 * 24 * 3600

#: Per git call. The briefing runs at SessionStart, so a wedged repo must cost
#: a bounded wait and a named problem, not a hung session.
_GIT_TIMEOUT_SECONDS = 5
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
    unique_commits: int | None  # commits reachable from no remote; None = count failed


@dataclass
class Report:
    worktrees: list[WorktreeRow] = field(default_factory=list)
    branches: list[BranchRow] = field(default_factory=list)
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
    because ``$CLAUDE_CONFIG_DIR`` usually points at one of the others."""
    env = os.environ if env is None else env
    home = Path.home() if home is None else home
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
        except OSError:
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


def _git(cwd: Path, *args: str) -> str | None:
    """stdout of one git call, or None if git could not answer. Always passes
    ``--no-optional-locks`` so a read never refreshes another tree's index."""
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", *args],
            capture_output=True,
            text=True,
            cwd=str(cwd),
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout if result.returncode == 0 else None


def dirty_signal(worktree: Path) -> tuple[int | None, Signal | None]:
    """``(dirty file count, newest edit)``. The count is None when git could not
    be asked; the signal is None when nothing is dirty or nothing could be
    stat'd (a deleted file has no mtime)."""
    out = _git(worktree, "status", "--porcelain", "-z")
    if out is None:
        return None, None
    entries = [e for e in out.split("\0") if e]
    paths: list[str] = []
    skip_next = False
    for entry in entries:
        if skip_next:  # a rename's second field is its source path
            skip_next = False
            continue
        code, rel = entry[:2], entry[3:]
        if code[0] in "RC":
            skip_next = True
        paths.append(rel)
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


def _list_worktrees(project_dir: Path) -> list[dict] | None:
    out = _git(project_dir, "worktree", "list", "--porcelain")
    if out is None:
        return None
    rows: list[dict] = []
    current: dict = {}
    for line in out.splitlines() + [""]:
        if not line:
            if current:
                rows.append(current)
            current = {}
        elif line.startswith("worktree "):
            current["path"] = line[len("worktree "):]
        elif line.startswith("branch "):
            current["branch"] = line[len("branch "):].removeprefix("refs/heads/")
        elif line.startswith("prunable"):
            current["prunable"] = True
    return rows


def _resolve(path: str | Path) -> Path:
    try:
        return Path(path).resolve()
    except OSError:
        return Path(path)


def _scan_worktree(raw: dict, *, current: Path, roots: list[Path], now: float) -> WorktreeRow:
    path = _resolve(raw["path"])
    branch = raw.get("branch")
    row = WorktreeRow(
        path=str(path),
        branch=branch,
        is_current=path == current,
        ephemeral=gitstate.ephemeral_kind_of(path, branch),
    )
    try:
        present = path.is_dir()
    except OSError:  # a permission error is not a missing tree; say nothing about it
        row.state = UNKNOWN
        return row
    if raw.get("prunable") or not present:
        row.state = MISSING
        return row
    git_dir_out = _git(path, "rev-parse", "--absolute-git-dir")
    reflog = _mtime_signal(Path(git_dir_out.strip()) / "logs" / "HEAD", "reflog") if git_dir_out else None
    row.dirty, edit = dirty_signal(path)
    row.last_activity = newest([
        transcript_signal(path, roots),
        reflog,
        _mtime_signal(path / ".prawduct" / ".session-start", "session-start"),
        edit,
    ])
    row.state = classify(row.last_activity, now)
    return row


def _stranded_branches(project_dir: Path, checked_out: set[str], report: Report) -> None:
    remotes = _git(project_dir, "for-each-ref", "--format=%(refname)", "refs/remotes/")
    if remotes is None:
        report.problems.append("could not list remote-tracking refs")
        return
    if not remotes.strip():
        report.has_remotes = False
        return
    heads = _git(
        project_dir, "for-each-ref", "--format=%(refname:short)%09%(objectname)%09%(committerdate:unix)",
        "refs/heads/",
    )
    # One walk for every branch at once: a tip reachable from no remote IS a
    # commit no remote carries, and a tip any remote reaches means every commit
    # under it is carried too. So membership of the tip answers the question
    # without a rev-list per branch, which a repo with hundreds of branches
    # could not afford at SessionStart.
    unique = _git(project_dir, "rev-list", "--branches", "--not", "--remotes")
    if heads is None or unique is None:
        report.problems.append("could not compare local branches with the remotes")
        return
    uncarried = set(unique.split())
    for line in heads.splitlines():
        try:
            name, sha, stamp = line.split("\t")
            last = float(stamp)
        except ValueError:
            continue
        # No age gate. A branch checked out in no worktree has nobody on it
        # already, and the incident this exists for was 18 hours old: a
        # reviewed fix built one afternoon and planned again the next morning.
        if name in checked_out or sha not in uncarried:
            continue
        count = _git(project_dir, "rev-list", "--count", name, "--not", "--remotes")
        report.branches.append(
            BranchRow(name=name, last_commit=last, unique_commits=int(count) if count and count.strip().isdigit() else None)
        )


def scan(project_dir: Path, *, now: float | None = None, roots: list[Path] | None = None) -> Report:
    """The whole report. Never raises: a failed probe is a named problem."""
    now = time.time() if now is None else now
    roots = config_roots() if roots is None else roots
    report = Report()
    raws = _list_worktrees(project_dir)
    if raws is None:
        report.problems.append("could not list worktrees")
        return report
    toplevel = _git(project_dir, "rev-parse", "--show-toplevel")
    current = _resolve(toplevel.strip()) if toplevel else _resolve(project_dir)
    for raw in raws:
        if "path" in raw:
            report.worktrees.append(_scan_worktree(raw, current=current, roots=roots, now=now))
    checked_out = {w.branch for w in report.worktrees if w.branch}
    _stranded_branches(project_dir, checked_out, report)
    return report


# --- renderers ----------------------------------------------------------------


def briefing_line(report: Report) -> str | None:
    """One line of COUNTS for the session briefing, or None when there is
    nothing to say. Names no branch, path or worktree — see the module doc."""
    others = [w for w in report.worktrees if not w.is_current]
    idle = [w for w in others if w.state == IDLE]
    idle_dirty = sum(1 for w in idle if w.dirty)
    active = sum(1 for w in others if w.state == ACTIVE)
    parts: list[str] = []
    if report.branches:
        n = len(report.branches)
        parts.append(
            f"{n} local branch{'es' if n != 1 else ''} checked out nowhere, "
            "with commits no remote has"
        )
    if idle:
        n = len(idle)
        dirty_note = f" ({idle_dirty} with uncommitted changes)" if idle_dirty else ""
        parts.append(
            f"{n} worktree{'s' if n != 1 else ''} idle {IDLE_AFTER_SECONDS // 86400}+ days{dirty_note}"
        )
    if not parts and not active:
        return None
    if active:
        parts.append(
            f"{active} other worktree{'s' if active != 1 else ''} "
            f"{'has' if active == 1 else 'have'} an agent active in the last "
            f"{ACTIVE_WITHIN_SECONDS // 60} min — a separate session, leave it alone"
        )
    return (
        "Stranded work: " + " · ".join(parts) + ". `prawduct-hook worktrees` lists them — "
        "report to the user; never adopt, delete or modify another worktree's work."
    )


def _age(seconds: float) -> str:
    if seconds < 3600:
        return f"{int(seconds // 60)}m ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h ago"
    return f"{int(seconds // 86400)}d ago"


def render_table(report: Report, now: float) -> str:
    lines = ["WORKTREES (state · last agent activity · uncommitted files · branch · path)"]
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
    else:
        lines.append("BRANCHES: none stranded.")
    for problem in report.problems:
        lines.append(f"note: {problem}")
    lines.append(
        "Liveness is inferred from timestamps: a session paused for a weekend looks idle. "
        "Report what you see to the user; never adopt, delete or modify another worktree's work."
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
    report = scan(project_dir, now=now)
    print(to_json(report) if "--json" in argv else render_table(report, now))
    return 0
