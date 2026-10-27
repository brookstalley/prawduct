"""Post-sync advisory probe: tests testament cannot cache, and why.

testament's result cache never reuses a result from a test process that did
something it cannot replay — read the live clock, ran a subprocess. A cause
that blocks every test in a process is easy to write and invisible from inside
the suite: one clock read in a run-level hook kept about 300k of 577k of this
repo's executions uncacheable for a week, and nothing said so. testament finds
the causes; this probe relays them, so the owner can fix each one or declare it
expected.

**Offline, and no process.** Probes run at every session start in every governed
repo. After each run testament writes a per-worktree snapshot of its cacheability
rollup (testament #287) under its own state directory; this reads that file and
nothing else, apart from one local ``git merge-base --is-ancestor``. Where
testament is not used the directory does not exist and the probe returns at
once.

**One advisory per suite, its id following the set of causes.** Evidence is one
``suite kind site scope`` line per cause, sorted by its own text — never a count,
a line number or a rank by count, since the store hashes evidence in order — so a
dismissal holds until a cause is added or goes away. Only a cause that is the
sole blocker of some tests (``alone > 0``) is raised: fixing any other changes
nothing while its partner still blocks.

**Only checked tokens reach the briefing.** The snapshot is foreign-written
content arriving at a governance surface that renders into the model's context.
Kinds and scopes must be plain words and sites ``path:function`` tokens; anything
else is dropped. testament's ``hint`` and the project's ``why`` strings are never
carried.

**Could not look, rather than nothing to report,** when the snapshot is narrowed
only, of an unknown version, unreadable, or about a commit outside this branch's
history: an open advisory then stays open instead of resolving on data that is not
about this checkout.

Registered at the composition root (``lib/probe_families.register_all``).
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from . import evidence
from .advisory_store import AdvisoryCandidate, Codebase, ProjectState, register_probe

FEATURE = "testament-cache"
PROBE_TYPE = "uncacheable-tests"
PROBE_VERSION = 1

#: The envelope version this reader knows (testament #287).
_ENVELOPE_V = 1

_WORD_RE = re.compile(r"^[a-z][a-z0-9_-]{0,39}$")
_SITE_RE = re.compile(r"^[A-Za-z0-9_./-]{1,200}:[A-Za-z_][A-Za-z0-9_.<>]{0,120}$")

#: Causes named in the summary; the rest are counted.
_SUMMARY_CAUSES = 3


def snapshot_dir() -> Path:
    """Where testament writes its cacheability snapshots (testament #287):
    under its own state directory, ``$TESTAMENT_HOME`` when set. Filenames are
    not part of the contract; :func:`_snapshots` matches on content."""
    home = os.environ.get("TESTAMENT_HOME")
    base = Path(home) if home else Path.home() / ".local" / "share" / "testament"
    return base / "client" / "cacheability"


def _snapshots(root: Path) -> "list[dict] | None":
    """This worktree's snapshot envelopes, or ``None`` when one could not be read.

    The one home of "which files are this worktree's": an envelope whose
    ``root`` is this worktree's resolved root. ``[]`` when testament has written
    nothing here, which is the common case and costs one ``stat``.
    """
    directory = snapshot_dir()
    if not directory.is_dir():
        return []
    mine = str(root.resolve())
    found: list[dict] = []
    try:
        names = sorted(p for p in directory.iterdir() if p.suffix == ".json")
    except OSError as exc:
        _note(f"the snapshot directory {directory} could not be listed ({exc})")
        return None
    for path in names:
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            _note(f"{path} could not be read ({type(exc).__name__})")
            return None
        if isinstance(envelope, dict) and envelope.get("root") == mine:
            found.append(envelope)
    return found


def _note(why: str) -> None:
    print(
        f"NOTE: testament cacheability probe skipped: {why} — causes keeping tests "
        "uncacheable go unreported this session",
        file=sys.stderr,
    )


def _current(root: Path, envelope: dict) -> bool:
    commit = envelope.get("commit")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{7,64}", commit):
        return False
    rc, _out, _err = evidence.run_git(root, "merge-base", "--is-ancestor", commit, "HEAD")
    return rc == 0


def _causes(row: dict) -> "list[tuple[str, str, str, int]]":
    """``(kind, site, scope, alone)`` for each checked cause that alone blocks tests."""
    out = []
    for cause in row.get("causes") or []:
        if not isinstance(cause, dict):
            continue
        kind, site, scope, alone = (
            cause.get("kind"), cause.get("site"), cause.get("scope"), cause.get("alone"),
        )
        if not (isinstance(kind, str) and _WORD_RE.match(kind)):
            continue
        if not (isinstance(scope, str) and _WORD_RE.match(scope)):
            continue
        if not (isinstance(site, str) and _SITE_RE.match(site)):
            continue
        if not isinstance(alone, int) or isinstance(alone, bool) or alone <= 0:
            continue
        out.append((kind, site, scope, alone))
    return sorted(out, key=lambda c: -c[3])


def probe_uncacheable_tests(state: ProjectState, codebase: Codebase):
    """One advisory per suite whose full, current snapshot names a sole blocker."""
    envelopes = _snapshots(codebase.root)
    if envelopes is None:
        return None
    full = [e for e in envelopes if e.get("selection") == "full"]
    if not full:
        if not envelopes:
            return []
        # Only narrowed runs: a `-k` run is not the project's state, and its
        # absence of causes proves nothing.
        _note("only a narrowed run's snapshot exists here; run the whole suite once")
        return None
    candidates = []
    for envelope in full:
        if envelope.get("v") != _ENVELOPE_V:
            _note(f"snapshot version {envelope.get('v')!r} is not one this reader knows")
            return None
        if not _current(codebase.root, envelope):
            _note(
                f"the snapshot's commit {str(envelope.get('commit'))[:12]!r} is not in "
                "this branch's history; run the suite here once"
            )
            return None
        for row in envelope.get("rows") or []:
            if not isinstance(row, dict):
                continue
            causes = _causes(row)
            if not causes:
                continue
            suite = envelope.get("suite")
            suite = suite if isinstance(suite, str) and _WORD_RE.match(suite) else "default"
            named = "; ".join(
                f"{kind} at {site} ({scope}-wide, sole blocker of {alone} test(s))"
                for kind, site, scope, alone in causes[:_SUMMARY_CAUSES]
            )
            more = len(causes) - _SUMMARY_CAUSES
            candidates.append(
                AdvisoryCandidate(
                    type=PROBE_TYPE,
                    evidence=tuple(sorted(
                        f"{suite} {kind} {site} {scope}" for kind, site, scope, _a in causes
                    )),
                    trigger_summary=(
                        f"testament cannot cache some of suite `{suite}`'s results, and "
                        f"{len(causes)} cause(s) are each the only thing stopping it: {named}"
                        + (f"; and {more} more" if more > 0 else "")
                    ),
                    owner_action=(
                        "Decide, cause by cause, whether to fix it so those tests can be "
                        "cached, or to declare it expected in testament's configuration, "
                        "which stops it being reported. Dismissing this advisory hides it "
                        "until the set of causes changes."
                    ),
                    # Owner-only: the decision is per cause and the summary names
                    # each one. `testament cacheability --offline` would show more,
                    # but it ships with #287 and is not an allowlisted executable.
                    recommended_action="",
                )
            )
    return candidates


def register() -> None:
    """Register the cacheability probe. Idempotent (register_probe overwrites)."""
    register_probe(FEATURE, PROBE_TYPE, PROBE_VERSION, probe_uncacheable_tests)
