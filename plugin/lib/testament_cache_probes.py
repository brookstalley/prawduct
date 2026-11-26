"""Post-sync advisory probe: tests testament cannot cache, and why.

testament's result cache never reuses a result from a test process that did
something it cannot replay — read the live clock, ran a subprocess. A cause
that blocks every test in a process is easy to write and invisible from inside
the suite: one clock read in a run-level hook kept about 300k of 577k of this
repo's executions uncacheable for a week, and nothing said so. testament finds
the causes; this probe relays them, so the owner can fix each one or declare it
expected.

**Offline, and no process.** Probes run at every session start in every governed
repo. After each run testament writes one snapshot per project and suite,
``<home>/client/cacheability/<project>.<suite>.json`` (testament #287,
``cache_advice.write``), holding the coordinator's cacheability row as ``row``. The
project is the ``name`` in this repo's ``.testament.toml``, which testament requires
(its manifest loader refuses one without it), so with a manifest naming none the
probe could not look. This reads the manifest, the snapshot directory's files and nothing
else, apart from one local ``git log``. Where testament is not used the directory
or the manifest does not exist and the probe returns at once.

**A snapshot counts only when its ``tree`` is the tree of a commit on this branch.**
A snapshot is per machine, so the file may be any worktree's or clone's last run.
Its ``commit`` cannot say which: it is a synthetic commit in testament's own store
(``keys.synthetic_commit``), never one of this repo's. Its ``tree`` is the git
tree of the worktree content the run shipped, tracked and untracked files alike, so
it equals a commit's tree exactly when the run was of that commit with nothing
uncommitted. A snapshot whose tree is no tree of HEAD's last
:data:`_HISTORY_TREES` commits was a dirty-tree run (perhaps a sibling worktree's
work in progress), another branch's, or too old to trust; it is skipped and named,
and fires and resolves nothing. Remaining limits: a clean run at an older commit
of this branch is accepted and reports the causes as they were at that commit, not
as they are at HEAD; and in a repo whose git filters change file bytes (autocrlf or
eol, LFS, ident) a run's tree may never be a commit's, so every suite reads as could
not look and the advisory never fires, rather than giving wrong advice.

**One advisory per suite, its id following the set of causes.** Evidence is one
``suite kind site scope`` line per cause, sorted by its own text — never a count,
a line number or a rank by count, since the store hashes evidence in order — so a
dismissal holds until a cause is added or goes away. Every cause testament lists
is raised, in testament's order. testament ranks them greedily, so a cause's
``frees`` counts what fixing it frees only after the causes above it are fixed; a
cause freeing 0 there must still be fixed for those below it to free theirs. The
summary keeps that order and says each count is "after those above", and
``owner_action`` says to fix them in this order. A coordinator that sends no
``frees`` gives ``alone``, the tests a cause is the sole blocker of; that is not a
fix-order count, and ``owner_action`` says what it is instead.

**Only checked tokens reach the briefing.** The snapshot is foreign-written
content arriving at a governance surface that renders into the model's context.
Kinds and scopes must be plain words and sites ``path:function`` tokens (a
module-level site is ``path:<module>``); anything else is dropped. testament's
``hint`` and the project's ``why`` strings are never carried, and a stderr note
echoes a snapshot's version, tree or file name only when it passes the same kind
of check. A dropped cause is counted, not silent: testament's order is greedy, so a
gap makes the counts below it counts after a fix the owner was never shown. The
summary says how many are missing, and the sync could not look, so nothing resolves
on a list known to be incomplete.

**Each cause names its remedy.** ``owner_action`` gives, for each kind among the
raised causes, its pattern in ``docs/test-determinism.md`` and a one-line remedy
(:data:`REMEDIES`); a kind not in the map is sent to that page, never guessed at.

**A suite speaks through its newest usable file.** An envelope is unusable when it
is of an unknown version, holds no ``row``, is narrowed only, or is not of this
branch's history; one with no plain-word suite belongs to no suite and is always
unusable. Each file is checked before any is chosen, and of a suite's usable files
the newest ``generated_at``, read as a time, speaks for it, so a stale backup or a
later narrowed or off-branch run beside a good snapshot changes nothing. A suite
with no usable file is skipped with one note, about its newest file; the other
suites still report, as :class:`~lib.advisory_store.CouldNotLook`, so no open
advisory resolves on a sync that skipped one. Could not look (``None``) when no
envelope of this project is usable, or the manifest names no project: an open
advisory then stays open instead of resolving on data that is not about this
checkout. Remaining limit: a suite left stale (only ever narrowed, or last run on a
dirty tree or another branch) keeps the advisory at could not look until that suite
is run cleanly here; the note names the suite to run.

Registered at the composition root (``lib/probe_families.register_all``).
"""

from __future__ import annotations

import json
import os
import re
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from . import evidence
from .advisory_store import (
    AdvisoryCandidate,
    Codebase,
    CouldNotLook,
    ProjectState,
    register_probe,
)

FEATURE = "testament-cache"
PROBE_TYPE = "uncacheable-tests"
PROBE_VERSION = 1

#: The envelope version this reader knows (testament #287).
_ENVELOPE_V = 1

_WORD_RE = re.compile(r"^[a-z][a-z0-9_-]{0,39}$")
_SITE_RE = re.compile(r"^[A-Za-z0-9_./-]{1,200}:[A-Za-z_<][A-Za-z0-9_.<>]{0,120}$")
#: What a note may echo of a snapshot: its file's name, and its tree.
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9 _.+-]{1,120}$")
_TREE_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")

#: Causes named in the summary; the rest are counted.
_SUMMARY_CAUSES = 3

#: How far back a snapshot's tree may be: HEAD's last this-many commits. One git
#: call lists them; a clean run older than this reports causes too stale to act on,
#: so it is skipped like an off-branch one.
_HISTORY_TREES = 500

#: testament's cause kind -> (its pattern in prawduct's ``docs/test-determinism.md``,
#: the remedy). Kinds testament reports that this leaves out (``host``,
#: ``inputs_outside``) get :data:`_UNMAPPED_REMEDY`.
REMEDIES: "dict[str, tuple[str, str]]" = {
    "subprocess": (
        "P9, P10",
        "call the product's own entry point in-process, and start tool children through "
        "one helper that isolates them and dates them from the suite's clock",
    ),
    "clock": (
        "P3, P4, P11",
        "read the time through one owner the suite pins, never in a fake or at import",
    ),
    "entropy": (
        "P3, P4, P11",
        "draw IDs and random values through one owner the suite replaces; seeding frees nothing",
    ),
    "file": (
        "Declaring a test uncacheable on purpose",
        "read it from the tree or the test's temporary directory; if the file is the test's "
        "subject, declare the test uncacheable",
    ),
    "socket": (
        "Declaring a test uncacheable on purpose",
        "stub the network call, or declare the test uncacheable when the network is its subject",
    ),
}

_UNMAPPED_REMEDY = "no remedy is mapped for this kind; see prawduct's docs/test-determinism.md"

#: The manifest testament reads at the project root, and so the project's name.
_MANIFEST = ".testament.toml"


def snapshot_dir() -> Path:
    """Where testament writes its cacheability snapshots: testament's
    ``cache_advice.snapshot_dir``, ``<home>/client/cacheability`` with ``<home>``
    ``$TESTAMENT_HOME`` when set, else ``~/.local/share/testament``. testament names
    each file ``<project>.<suite>.json``; :func:`_snapshots` does not rely on that
    name, and reads which project a file is from its content."""
    home = os.environ.get("TESTAMENT_HOME")
    base = Path(home) if home else Path.home() / ".local" / "share" / "testament"
    return base / "client" / "cacheability"


def _project(root: Path) -> "str | None":
    """The project testament files this repo's snapshots under: ``name`` in its
    manifest. testament has no fallback name: its manifest loader refuses a manifest
    without one, so no snapshot of this repo can exist under any other. ``None`` when
    there is no manifest (testament is not used here), and ``""`` when one exists but
    names no project, after saying why."""
    try:
        data = tomllib.loads((root / _MANIFEST).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        _note(f"{_MANIFEST} could not be read ({type(exc).__name__})")
        return ""
    name = data.get("name")
    if not (isinstance(name, str) and name and "/" not in name and not name.startswith(".")):
        _note(f"{_MANIFEST} names no project, and testament refuses a manifest without a name")
        return ""
    return name


def _snapshots(root: Path) -> "list[tuple[Path, dict]] | None":
    """This project's envelopes, each with its file, unchecked; ``None`` when it
    could not look at all (the manifest names no project, or the directory would
    not list).

    The one home of "which files are this repo's". Every ``*.json`` in
    :func:`snapshot_dir` is opened and kept when its ``project`` is the manifest's
    name, whatever the file is called; any other file, one that will not parse
    included, is passed over and never costs this one anything. ``[]`` when testament
    has written nothing for this project. Which file speaks for a suite is
    :func:`probe_uncacheable_tests`'s question.
    """
    directory = snapshot_dir()
    if not directory.is_dir():
        return []
    project = _project(root)
    if project is None:
        return []
    if not project:
        return None
    try:
        paths = sorted(p for p in directory.iterdir() if p.suffix == ".json")
    except OSError as exc:
        _note(f"the snapshot directory {directory} could not be listed ({exc})")
        return None
    found = []
    for path in paths:
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(envelope, dict) and envelope.get("project") == project:
            found.append((path, envelope))
    return found


def _generated(envelope: dict) -> "tuple[int, datetime]":
    """A sort key for ``generated_at`` read as a time: an ISO 8601 string (``Z`` or
    an offset, any fraction; a naive one is UTC) or epoch seconds. One that is
    neither sorts before every time, so it never outranks a readable one."""
    value = envelope.get("generated_at")
    when = None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            when = datetime.fromtimestamp(value, timezone.utc)
        except (OverflowError, OSError, ValueError):
            when = None
    elif isinstance(value, str):
        try:
            text = value[:-1] + "+00:00" if value.endswith("Z") else value
            when = datetime.fromisoformat(text)
        except ValueError:
            when = None
        if when is not None and when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
    return (1, when) if when is not None else (0, datetime.min.replace(tzinfo=timezone.utc))


def _shown(path: Path) -> str:
    """A snapshot's file as a note may name it: its path when its name is plain."""
    return str(path) if _SAFE_NAME_RE.match(path.name) else f"a file in {path.parent}"


class _NoHistory(Exception):
    """git could not list this branch's history, so no tree can be checked."""


def _note(why: str, *, one: bool = False) -> None:
    """Say on stderr what went unchecked: the whole probe, or (``one``) one snapshot."""
    if one:
        print(
            f"NOTE: testament cacheability probe skipped a snapshot: {why} — its suite's "
            "causes go unreported this session, and no open uncacheable-tests advisory resolves",
            file=sys.stderr,
        )
        return
    print(
        f"NOTE: testament cacheability probe skipped: {why} — causes keeping tests "
        "uncacheable go unreported this session",
        file=sys.stderr,
    )


def _history_trees(root: Path) -> "frozenset[str] | None":
    """The trees of HEAD's last :data:`_HISTORY_TREES` commits, or ``None`` when git
    could not list them. A snapshot is this branch's when its ``tree`` is one."""
    rc, out, _err = evidence.run_git(
        root, "log", f"--max-count={_HISTORY_TREES}", "--format=%T", "HEAD"
    )
    if rc != 0:
        return None
    return frozenset(out.split())


def _causes(row: dict) -> "tuple[list[tuple[str, str, str, str, str]], int]":
    """``(kind, site, scope, count, measure)`` for each checked cause, in
    testament's order, and how many causes failed the check. ``count`` says
    testament's ``frees`` (``measure`` ``frees``), or ``alone`` from a coordinator
    that sends no ``frees`` (``alone``), or nothing when neither is a count (``""``)."""
    out = []
    dropped = 0
    listed = row.get("causes")
    for cause in listed if isinstance(listed, list) else []:
        if not (isinstance(cause, dict)
                and isinstance(kind := cause.get("kind"), str) and _WORD_RE.match(kind)
                and isinstance(scope := cause.get("scope"), str) and _WORD_RE.match(scope)
                and isinstance(site := cause.get("site"), str) and _SITE_RE.match(site)):
            dropped += 1
            continue
        frees, alone = cause.get("frees"), cause.get("alone")
        if _count(frees):
            out.append((kind, site, scope, f", frees {frees} after those above", "frees"))
        elif _count(alone):
            out.append((kind, site, scope, f", sole blocker of {alone} test(s)", "alone"))
        else:
            out.append((kind, site, scope, "", ""))
    return out, dropped


def _count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _problem(path: Path, envelope: dict, suite: "str | None", trees) -> "str | None":
    """Why ``envelope`` cannot speak for its suite, as a note says it, or ``None``.
    ``trees()`` gives this branch's trees, asked only of an envelope that reaches
    the tree check, so a directory of narrowed runs costs no git call."""
    version = envelope.get("v")
    if version != _ENVELOPE_V:
        if _count(version):
            return f"{_shown(path)}'s snapshot version {version} is not one this reader knows"
        return f"{_shown(path)}'s snapshot is of an unknown version"
    if not isinstance(envelope.get("row"), dict):
        return f"{_shown(path)} is not a cacheability snapshot"
    if suite is None:
        return f"{_shown(path)}'s suite name is not a plain word"
    if envelope.get("selection") != "full":
        # A narrowed run (`-k`, a path) is not the suite's state, and its absence
        # of causes proves nothing; testament writes one only where the suite has
        # no full run.
        return f"suite `{suite}` has only a narrowed run's snapshot; run the whole suite once"
    tree = envelope.get("tree")
    if isinstance(tree, str) and tree in trees():
        return None
    shown = repr(tree[:12]) if isinstance(tree, str) and _TREE_RE.match(tree) else "an unreadable tree"
    return (
        f"suite `{suite}`'s snapshot is of tree {shown}, which is no commit of this "
        "branch's recent history (a run with uncommitted work, perhaps another "
        "worktree's, or another branch's); run the suite here on a clean commit"
    )


def probe_uncacheable_tests(state: ProjectState, codebase: Codebase):
    """One advisory per suite whose newest usable snapshot names a cause whose fix
    frees tests. Skips (and names) each suite with no usable file; see the module
    docstring for what that returns."""
    found = _snapshots(codebase.root)
    if found is None:
        return None
    groups: dict[object, list[tuple[Path, dict]]] = {}
    for path, envelope in found:
        suite = envelope.get("suite")
        key = suite if isinstance(suite, str) and _WORD_RE.match(suite) else ("file", path)
        groups.setdefault(key, []).append((path, envelope))

    history: list = []

    def trees() -> "frozenset[str]":
        if not history:
            listed = _history_trees(codebase.root)
            if listed is None:
                raise _NoHistory
            history.append(listed)
        return history[0]

    skipped = unusable = 0
    candidates = []
    try:
        for key, files in groups.items():
            suite = key if isinstance(key, str) else None
            files.sort(key=lambda item: (_generated(item[1]), str(item[0])), reverse=True)
            problems = [_problem(path, envelope, suite, trees) for path, envelope in files]
            chosen = next((env for (_p, env), why in zip(files, problems) if why is None), None)
            if chosen is None:
                _note(problems[0], one=True)
                skipped += 1
                unusable += 1
                continue
            causes, dropped = _causes(chosen["row"])
            if dropped:
                print(
                    f"NOTE: testament cacheability probe: suite `{suite}`: {dropped} cause(s) "
                    "failed the token check and are not shown, so its fix order is incomplete "
                    "— no open uncacheable-tests advisory resolves",
                    file=sys.stderr,
                )
                skipped += 1
            if causes:
                candidates.append(_candidate(suite, causes, dropped))
    except _NoHistory:
        _note("git could not list this branch's history")
        return None
    if unusable and unusable == len(groups):
        return None
    return CouldNotLook(candidates) if skipped else candidates


def _order_sentence(causes: "list[tuple[str, str, str, str, str]]") -> str:
    """What the counts mean, derived from the counts shown: a fix order only when
    every one is testament's ``frees``."""
    measures = {cause[4] for cause in causes}
    if measures == {"frees"}:
        return ("Fix them in this order: each count is what that fix frees once the causes "
                "before it are fixed.")
    if "alone" in measures:
        return ("They are listed in testament's order. A \"sole blocker of N\" count is the "
                "tests that cause blocks by itself, not what fixing it frees after the causes "
                "above it.")
    return "They are listed in testament's order."


def _candidate(suite: str, causes: "list[tuple[str, str, str, str, str]]",
               dropped: int) -> AdvisoryCandidate:
    named = "; ".join(
        f"{kind} at {site} ({scope}-wide{count})"
        for kind, site, scope, count, _m in causes[:_SUMMARY_CAUSES]
    )
    more = len(causes) - _SUMMARY_CAUSES
    return AdvisoryCandidate(
        type=PROBE_TYPE,
        evidence=tuple(sorted(
            f"{suite} {kind} {site} {scope}" for kind, site, scope, _n, _m in causes
        )),
        trigger_summary=(
            f"testament cannot cache some of suite `{suite}`'s results, and fixing "
            f"{len(causes)} cause(s) would free tests, in testament's order: {named}"
            + (f"; and {more} more" if more > 0 else "")
            + (f"; {dropped} cause(s) testament listed could not be shown, so a count "
               "after one of them may be off" if dropped else "")
        ),
        owner_action=(
            "Decide, cause by cause, whether to fix it so those tests can be "
            "cached, or to declare it expected in testament's configuration, "
            f"which stops it being reported. {_order_sentence(causes)} {_remedies(causes)} "
            "Dismissing this advisory hides it until the set of causes changes."
        ),
        # Owner-only: the decision is per cause and the summary names
        # each one. `testament cacheability --offline` would show more,
        # but it is not an allowlisted executable.
        recommended_action="",
    )


def _remedies(causes: "list[tuple[str, str, str, str, str]]") -> str:
    """One line per kind among ``causes``, in the order the kinds first appear (the
    summary's): its pattern and remedy, or the pointer for a kind the map lacks."""
    lines = []
    for kind in dict.fromkeys(cause[0] for cause in causes):
        if kind in REMEDIES:
            pattern, remedy = REMEDIES[kind]
            lines.append(f"{kind} ({pattern} in prawduct's docs/test-determinism.md): {remedy}.")
        else:
            lines.append(f"{kind}: {_UNMAPPED_REMEDY}.")
    return "Remedies by kind: " + " ".join(lines)


def register() -> None:
    """Register the cacheability probe. Idempotent (register_probe overwrites)."""
    register_probe(FEATURE, PROBE_TYPE, PROBE_VERSION, probe_uncacheable_tests)
