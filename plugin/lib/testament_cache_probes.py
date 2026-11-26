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
(its manifest loader refuses one without it), so a manifest naming none is could
not look. This reads the manifest, the snapshot directory's files and nothing
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
and fires and resolves nothing. Remaining limit: a clean run at an older commit of
this branch is accepted and reports the causes as they were at that commit, not
as they are at HEAD.

**One advisory per suite, its id following the set of causes.** Evidence is one
``suite kind site scope`` line per cause, sorted by its own text — never a count,
a line number or a rank by count, since the store hashes evidence in order — so a
dismissal holds until a cause is added or goes away. A cause is raised when fixing
it frees tests: testament's ``frees`` (what fixing it, after the causes ranked
before it, leaves with no cause) is above 0, or, from a coordinator that sends no
``frees``, ``alone`` (the tests it is the sole blocker of) is. The summary ranks
by that same count, so it leads with the cause whose fix frees the most.

**Only checked tokens reach the briefing.** The snapshot is foreign-written
content arriving at a governance surface that renders into the model's context.
Kinds and scopes must be plain words and sites ``path:function`` tokens; anything
else is dropped. testament's ``hint`` and the project's ``why`` strings are never
carried.

**Each cause names its remedy.** ``owner_action`` gives, for each kind among the
raised causes, its pattern in ``docs/test-determinism.md`` and a one-line remedy
(:data:`REMEDIES`); a kind not in the map is sent to that page, never guessed at.

**One unusable snapshot is skipped, not the probe.** An envelope of this project
that is narrowed only, of an unknown version, unreadable or holding no ``row``, or
not of this branch's history, is skipped with a note; the other suites' current
snapshots still report, as :class:`~lib.advisory_store.CouldNotLook`, so no open
advisory resolves on a sync that skipped one. Could not look (``None``) when no
envelope of this project is usable, or the manifest names no project: an open
advisory then stays open instead of resolving on data that is not about this
checkout.

Registered at the composition root (``lib/probe_families.register_all``).
"""

from __future__ import annotations

import json
import os
import re
import sys
import tomllib
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
_SITE_RE = re.compile(r"^[A-Za-z0-9_./-]{1,200}:[A-Za-z_][A-Za-z0-9_.<>]{0,120}$")

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


def _snapshots(root: Path) -> "tuple[list[dict], int] | None":
    """This project's readable envelopes of a known version, and how many of its
    files were skipped (each named on stderr); ``None`` when it could not look at
    all (the manifest names no project, or the directory would not list).

    The one home of "which files are this repo's". Every ``*.json`` in
    :func:`snapshot_dir` is opened and kept when its ``project`` is the manifest's
    name, whatever the file is called; another project's file, whatever its shape,
    is passed over and never costs this one anything. A file that will not parse
    names no project, so it is counted as skipped only when its name is this
    project's (``<project>.``...), the one way it could be one of its snapshots.
    ``([], 0)`` when testament has written nothing for this project. Whether an
    envelope is about this branch is :func:`_history_trees`'s question.
    """
    directory = snapshot_dir()
    if not directory.is_dir():
        return [], 0
    project = _project(root)
    if project is None:
        return [], 0
    if not project:
        return None
    found: list[dict] = []
    skipped = 0
    try:
        paths = sorted(p for p in directory.iterdir() if p.suffix == ".json")
    except OSError as exc:
        _note(f"the snapshot directory {directory} could not be listed ({exc})")
        return None
    for path in paths:
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            if path.name.startswith(f"{project}."):
                _note(f"{path} could not be read ({type(exc).__name__})", one=True)
                skipped += 1
            continue
        if not (isinstance(envelope, dict) and envelope.get("project") == project):
            continue
        if envelope.get("v") != _ENVELOPE_V:
            _note(f"{path}'s snapshot version {envelope.get('v')!r} is not one this reader "
                  "knows", one=True)
            skipped += 1
        elif not isinstance(envelope.get("row"), dict):
            _note(f"{path} is not a cacheability snapshot", one=True)
            skipped += 1
        else:
            found.append(envelope)
    return found, skipped


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


def _suite(envelope: dict) -> str:
    suite = envelope.get("suite")
    return suite if isinstance(suite, str) and _WORD_RE.match(suite) else "default"


def _causes(row: dict) -> "list[tuple[str, str, str, int, str]]":
    """``(kind, site, scope, count, what)`` for each checked cause whose fix frees
    tests, most first. ``count`` is testament's ``frees``, or ``alone`` from a
    coordinator that sends no ``frees``; ``what`` says which, for the summary."""
    out = []
    for cause in row.get("causes") or []:
        if not isinstance(cause, dict):
            continue
        kind, site, scope = cause.get("kind"), cause.get("site"), cause.get("scope")
        if not (isinstance(kind, str) and _WORD_RE.match(kind)):
            continue
        if not (isinstance(scope, str) and _WORD_RE.match(scope)):
            continue
        if not (isinstance(site, str) and _SITE_RE.match(site)):
            continue
        frees, alone = cause.get("frees"), cause.get("alone")
        if _count(frees):
            count, what = frees, "fixing it frees"
        elif frees is None and _count(alone):
            count, what = alone, "sole blocker of"
        else:
            continue
        out.append((kind, site, scope, count, what))
    return sorted(out, key=lambda c: (-c[3], c[0], c[1], c[2]))


def _count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def probe_uncacheable_tests(state: ProjectState, codebase: Codebase):
    """One advisory per suite whose full, current snapshot names a cause whose fix
    frees tests. Skips (and names) each envelope it cannot use; see the module
    docstring for what that returns."""
    found = _snapshots(codebase.root)
    if found is None:
        return None
    envelopes, skipped = found
    usable: list[dict] = []
    for envelope in envelopes:
        if envelope.get("selection") != "full":
            # A narrowed run (`-k`, a path) is not the suite's state, and its
            # absence of causes proves nothing; testament writes one only where
            # the suite has no full run.
            _note(f"suite `{_suite(envelope)}` has only a narrowed run's snapshot; run the "
                  "whole suite once", one=True)
            skipped += 1
        else:
            usable.append(envelope)
    if usable:
        trees = _history_trees(codebase.root)
        if trees is None:
            _note("git could not list this branch's history")
            return None
        current = []
        for envelope in usable:
            tree = envelope.get("tree")
            if isinstance(tree, str) and tree in trees:
                current.append(envelope)
                continue
            _note(
                f"suite `{_suite(envelope)}`'s snapshot is of tree {str(tree)[:12]!r}, which "
                "is no commit of this branch's recent history (a run with uncommitted work, "
                "perhaps another worktree's, or another branch's); run the suite here on a "
                "clean commit", one=True,
            )
            skipped += 1
        usable = current
    if skipped and not usable:
        return None
    candidates = [c for c in map(_candidate, usable) if c is not None]
    return CouldNotLook(candidates) if skipped else candidates


def _candidate(envelope: dict) -> "AdvisoryCandidate | None":
    causes = _causes(envelope["row"])
    if not causes:
        return None
    suite = _suite(envelope)
    named = "; ".join(
        f"{kind} at {site} ({scope}-wide, {what} {count} test(s))"
        for kind, site, scope, count, what in causes[:_SUMMARY_CAUSES]
    )
    more = len(causes) - _SUMMARY_CAUSES
    return AdvisoryCandidate(
        type=PROBE_TYPE,
        evidence=tuple(sorted(
            f"{suite} {kind} {site} {scope}" for kind, site, scope, _n, _w in causes
        )),
        trigger_summary=(
            f"testament cannot cache some of suite `{suite}`'s results, and fixing "
            f"{len(causes)} cause(s) would free tests, the most first: {named}"
            + (f"; and {more} more" if more > 0 else "")
        ),
        owner_action=(
            "Decide, cause by cause, whether to fix it so those tests can be "
            "cached, or to declare it expected in testament's configuration, "
            "which stops it being reported. Fix first the cause that frees the "
            f"most tests; the summary leads with it. {_remedies(causes)} "
            "Dismissing this advisory hides it until the set of causes changes."
        ),
        # Owner-only: the decision is per cause and the summary names
        # each one. `testament cacheability --offline` would show more,
        # but it is not an allowlisted executable.
        recommended_action="",
    )


def _remedies(causes: "list[tuple[str, str, str, int, str]]") -> str:
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
