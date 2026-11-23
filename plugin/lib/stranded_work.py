"""Stranded work: unlanded branches, and worktrees nobody is in.

Finished work gets stranded where no reader looks. A reviewed fix can sit on a
local-only branch while the next session plans to build it again, a finished
and pushed branch can wait days for a pull request nobody opened, and a clone
collects worktrees with no sign of which still have an agent in them. This
module answers those questions from git, build plans and file timestamps,
read-only, for four readers:

* ``prawduct-hook worktrees`` — the full table, on demand. Its ``--prs`` flag
  is this module's one network leg (:func:`check_pull_requests`).
* The session briefing — sibling WORKTREES as counts only.
* The ``stranded-branch`` advisory (``stranded_branch_probes``) — one per
  stranded BRANCH, by name, dismissible, resolving itself once the branch is
  pushed or deleted.
* The ``finished-branch-unlanded`` advisory (same module) — one per finished,
  pushed, unmerged branch (:func:`unlanded_branches`), offline.

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

from . import evidence, gitstate, host

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

#: A finished branch is unlanded only once its tip commit is this old. Same-day
#: work is somebody's next step, not a stranding; the #843 cost example sat two
#: days. Hardcoded, not a preference row (#843 Decision 2).
UNLANDED_AFTER_SECONDS = 24 * 3600
#: ``gh`` lookups per ``worktrees --prs`` run, oldest branch first. Each is one
#: network call; the rest are reported unchecked, never silently dropped.
MAX_PR_CHECKS = 8

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
class UnlandedRow:
    """A finished branch that is pushed, unmerged and idle (:func:`unlanded_branches`)."""

    name: str
    last_commit: float
    #: The build plans claiming it, as ``plan_index.display_path`` writes them.
    plans: list[str]
    #: ``unchecked`` (offline, or past :data:`MAX_PR_CHECKS`), ``none`` (gh
    #: answered: no pull request from this repo, ever), ``found``, or
    #: ``failed`` (gh could not be asked — never read as ``none``).
    pr_check: str = "unchecked"
    #: ``{"number", "state"}`` of the newest pull request when ``found``.
    pull_request: dict | None = None


@dataclass
class Report:
    worktrees: list[WorktreeRow] = field(default_factory=list)
    branches: list[BranchRow] = field(default_factory=list)
    unlanded: list[UnlandedRow] = field(default_factory=list)
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


def config_roots(
    env: dict | None = None, home: Path | None = None, *, holding: str = "projects"
) -> list[Path]:
    """Every host config root holding a ``holding`` directory (transcripts
    live under ``projects``, plugin caches under ``plugins``), from the
    candidates ``host.config_roots`` names. Deduplicated by resolved path,
    because the configured override usually points at one of the others. A home
    that cannot be resolved yields no roots, not an exception."""
    try:
        home = Path.home() if home is None else home
    except (RuntimeError, KeyError, OSError):
        return []
    candidates = host.config_roots(env, home)
    roots: list[Path] = []
    seen: set[str] = set()
    for root in candidates:
        try:
            if not (root / holding).is_dir():
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
    not answer. ``GIT_OPTIONAL_LOCKS=0`` so a read never refreshes another
    tree's index."""
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

    "Checked out" is ``gitstate.held_branches``, which git hygiene shares.

    ``count_commits`` adds one ``rev-list --count`` per stranded branch — the
    table wants it, the advisory and the briefing do not."""
    if records is None:
        records = gitstate.worktree_records(project_dir)
        if records is None:
            return [], True, "could not list worktrees, so could not tell which branches are checked out"
    if not records:  # not a git repository: nothing to compare, and nothing went wrong
        return [], True, None
    held = gitstate.held_branches(records)

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


def unlanded_branches(
    project_dir: Path, *, records: list[dict] | None = None, now: float | None = None
) -> tuple[list[UnlandedRow], str | None]:
    """``(rows, problem)`` — #843's pushed arm, offline: local branches that
    every live build plan claiming them calls finished, whose tip a remote has,
    that have not merged into their base, and whose last commit is at least
    :data:`UNLANDED_AFTER_SECONDS` old. Oldest first.

    Each test is an existing answer, never a new one: the claim index
    (``plan_index.branch_claiming_plans`` — no claiming plan, no reading of
    "finished", so silence), ``plan_status.is_finished`` for every claimant (one
    open plan among several keeps the branch open), and
    ``plan_lifecycle.observe`` answering ``in-progress`` for each (merged,
    released, superseded or unknown is not "unlanded"). A branch checked out in
    ANOTHER worktree is that worktree's (#843 Decision 3); the one checked out
    here is not exempt, since the cost example was a branch its own session had
    moved on from. An unpushed tip is the local arm's (:func:`stranded_branches`),
    and a long-lived branch is never a pull request's head.

    Whether a pull request was ever opened is NOT asked here: this runs at
    session start, where nothing touches the network.
    :func:`check_pull_requests` asks, from ``worktrees --prs`` only.

    Costs nothing beyond reading plan frontmatter unless a plan claims a
    branch; git and the evidence store are read only for claimed branches."""
    from . import plan_index  # noqa: PLC0415 — lazy: most sessions stop at no claim

    artifacts = gitstate.get_prawduct_dir(project_dir) / "artifacts"
    claims: dict[str, list[Path]] = {}
    for plan_path, branch in plan_index.branch_claiming_plans(artifacts):
        claims.setdefault(branch, []).append(plan_path)
    if not claims:
        return [], None
    if records is None:
        records = gitstate.worktree_records(project_dir)
        if records is None:
            return [], "could not list worktrees, so could not tell which branches another worktree holds"
    if not records:  # not a git repository
        return [], None
    toplevel = _git(project_dir, "rev-parse", "--show-toplevel")
    current = _resolve(toplevel) if toplevel else _resolve(project_dir)
    held_elsewhere = gitstate.held_branches(
        [r for r in records if "worktree" in r and _resolve(r["worktree"]) != current]
    )
    heads = _git(
        project_dir, "for-each-ref",
        "--format=%(refname:lstrip=2)%09%(objectname)%09%(committerdate:unix)", "refs/heads/",
    )
    if heads is None:
        return [], "could not list local branches"
    now = time.time() if now is None else now
    candidates: list[tuple[str, str, float]] = []
    for line in heads.splitlines():
        try:
            name, sha, stamp = line.split("\t")
            last = float(stamp)
        except ValueError:
            continue
        if name in claims and name not in held_elsewhere and now - last >= UNLANDED_AFTER_SECONDS:
            candidates.append((name, sha, last))
    if not candidates:
        return [], None

    # Lazy: git_hygiene imports this module, and plan_lifecycle reaches it.
    from . import git_hygiene, plan_lifecycle, plan_status  # noqa: PLC0415

    long_lived = git_hygiene.long_lived_names(project_dir, gitstate.push_remote(project_dir))
    facts = None
    rows: list[UnlandedRow] = []
    for name, sha, last in candidates:
        if git_hygiene.is_long_lived(name, long_lived):
            continue
        carried = _git(project_dir, "for-each-ref", "--count=1", "--contains", sha,
                       "--format=%(refname)", "refs/remotes/")
        if carried is None:
            return [], "could not compare finished branches with the remotes"
        if not carried.strip():
            continue  # never pushed: the local arm's
        if facts is None:
            facts = evidence.read_facts(project_dir)
        plans = claims[name]
        if not all(plan_status.is_finished(p, facts, repo_dir=project_dir) for p in plans):
            continue
        if not all(
            plan_lifecycle.observe(p, repo_dir=project_dir, facts=facts).state == plan_lifecycle.IN_PROGRESS
            for p in plans
        ):
            continue
        rows.append(UnlandedRow(
            name=name, last_commit=last, plans=[plan_index.display_path(p, artifacts) for p in plans]
        ))
    rows.sort(key=lambda r: r.last_commit)
    return rows, None


def check_pull_requests(project_dir: Path, rows: list[UnlandedRow], *, limit: int = MAX_PR_CHECKS) -> str | None:
    """Ask ``gh`` whether each row's branch ever had a pull request, oldest
    first, at most ``limit`` calls; fills ``pr_check`` / ``pull_request`` in
    place. Returns a problem naming the rows left unchecked, else None.

    The network goes through ``git_hygiene.any_pr_for`` — the one ``gh``
    seam, declared in project-state's ``egress_boundary`` — and only from
    ``worktrees --prs``, a command someone chose to run."""
    from . import git_hygiene  # noqa: PLC0415 — git_hygiene imports this module

    for row in sorted(rows, key=lambda r: r.last_commit)[:limit]:
        answer = git_hygiene.any_pr_for(project_dir, row.name)
        if answer is None:
            row.pr_check = "failed"
        elif answer is False:
            row.pr_check = "none"
        else:
            row.pr_check, row.pull_request = "found", answer
    left = len(rows) - min(len(rows), limit)
    if left:
        return (f"{left} finished branch(es) not checked for a pull request: past the "
                f"{limit}-lookup cap for one run, newest left; run it again after landing some")
    return None


def scan(
    project_dir: Path,
    *,
    now: float | None = None,
    roots: list[Path] | None = None,
    branches: bool = True,
    count_commits: bool = False,
    check_prs: bool = False,
    budget_seconds: float = SCAN_BUDGET_SECONDS,
) -> Report:
    """The report. Never raises: a failed probe is a named problem.

    ``branches=False`` skips both branch comparisons — the briefing's case,
    since stranded and unlanded branches reach the session through their
    advisories instead. ``check_prs`` asks ``gh`` about the unlanded ones
    (:func:`check_pull_requests`); only ``worktrees --prs`` passes it."""
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
        report.unlanded, problem = unlanded_branches(project_dir, records=records, now=now)
        if problem:
            report.problems.append(problem)
        elif check_prs and report.unlanded:
            problem = check_pull_requests(project_dir, report.unlanded)
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


def age_text(seconds: float) -> str:
    if seconds < 3600:
        return f"{int(seconds // 60)}m ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h ago"
    return f"{int(seconds // 86400)}d ago"


def _pull_request_text(row: UnlandedRow) -> str:
    if row.pr_check == "found" and row.pull_request:
        return f"pull request #{row.pull_request['number']} ({row.pull_request['state'] or 'state unknown'})"
    if row.pr_check == "none":
        return "no pull request, ever"
    if row.pr_check == "failed":
        return "could not ask gh about a pull request"
    return "pull request not checked"


def render_table(report: Report, now: float) -> str:
    lines = ["WORKTREES (state · last agent activity · uncommitted files · branch · path)"]
    if not report.worktrees_checked:
        lines.append("  could not list worktrees (git failed here)")
    for w in report.worktrees:
        where = "this session" if w.is_current else w.path
        seen = f"{age_text(now - w.last_activity.at)} via {w.last_activity.source}" if w.last_activity else "no signal"
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
            lines.append(f"  {b.name}  {count} commit(s)  last {age_text(now - b.last_commit)}")
    elif report.worktrees_checked:
        lines.append("BRANCHES: none stranded.")
    if report.unlanded:
        lines.append("FINISHED BRANCHES NOT MERGED (pushed; every build plan claiming them finished)")
        for u in report.unlanded:
            lines.append(f"  {u.name}  last {age_text(now - u.last_commit)}  "
                         f"{_pull_request_text(u)}  plan: {', '.join(u.plans)}")
        if any(u.pr_check == "unchecked" for u in report.unlanded):
            lines.append("  `prawduct-hook worktrees --prs` asks GitHub whether each ever had a "
                         f"pull request (one call per branch, at most {MAX_PR_CHECKS}).")
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
    """``prawduct-hook worktrees [--json] [--prs]``. Exit 0 whenever a report
    was produced, partial included (its problems are named in it); 2 on bad
    usage. ``--prs`` is the one network leg: a ``gh pr list`` per finished,
    unmerged branch, capped at :data:`MAX_PR_CHECKS`."""
    unknown = [a for a in argv if a not in ("--json", "--prs")]
    if unknown:
        print(f"worktrees: unknown argument(s) {unknown}; usage: prawduct-hook worktrees [--json] [--prs]",
              file=sys.stderr)
        return 2
    now = time.time()
    report = scan(project_dir, now=now, count_commits=True, check_prs="--prs" in argv)
    print(to_json(report) if "--json" in argv else render_table(report, now))
    return 0
