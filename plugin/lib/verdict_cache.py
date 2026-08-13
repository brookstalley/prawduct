"""Memoization of the composed coverage verdict (tactical-efficiency Chunk 02).

``coverage_algebra.coverage_verdict`` is a pure function, and an expensive one:
its free-edge search keys every tree the store mentions, which is one
``git ls-tree`` per tree. Measured on this repo (2,715 facts, 701 distinct
trees) a cold verdict costs 17.4 s; with the per-invocation key cache already
warm it costs 0.01 s. The store is append-only and shared by every worktree of
the clone, so that cost grows monotonically and is paid again by every gate
call — nine invocations in one consumer session ran 29–120 s each, two of them
hitting the 2-minute Bash ceiling, and the agent resorted to `timeout 200`.

**This is a memo, not a second home for any fact** (``data-model.md``: *derived
views are disposable and never authoritative — no gate reads a view to reach a
verdict*). The distinction is the key: it covers EVERY input the verdict is a
function of — the two endpoint trees and a content hash of the whole evidence
store — so a hit replays a computation whose inputs are provably unchanged
rather than substituting for one. A miss, an unreadable cache, a corrupt entry,
or an unreadable store all recompute. There is no path on which the cache
decides something the store would not.

**Why a cached verdict can never be a false PASS.** Git objects are immutable
and content-addressed, so they are not in the key — and they do not need to be.
``coverage_verdict`` grants ``covered`` only through review edges (derived from
facts, which ARE in the key) and free edges (tree-key equality). A missing
object or a git failure makes ``key_fn`` return ``None``, which denies a free
edge; it can never manufacture one. So git-side degradation moves the verdict
only toward denial, and a verdict recorded under it can only be replayed as a
denial. The residual, stated: an ``uncovered`` computed while an object was
transiently unreadable is replayed until the store's next append changes the
fingerprint. That is a false negative — the safe direction, and the one this
subsystem's authority contract requires.

The cache lives beside the evidence store, in the per-clone gitignored area
(``two stores, two lifetimes``) — never in committed state.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import coverage_algebra, evidence
from .core import atomic_write_text

CACHE_BASENAME = "verdict-cache.json"

#: Bumped whenever the verdict SHAPE changes, so entries written by an older
#: reading of the same inputs cannot be replayed against a newer consumer. The
#: fingerprint covers the inputs; this covers the function.
CACHE_SCHEMA = 1

#: Entries kept, newest first. A gate call touches a handful of keys (the span,
#: plus each diagnosis's), and a branch's keys all die on the next store append,
#: so this only has to outlive one session's polling — not accumulate history.
MAX_ENTRIES = 64


def cache_path(project_dir: Path) -> "Path | None":
    """The cache file beside the evidence store, or ``None`` when the store has
    no home (outside a git repo). No fallback location, for the same reason
    :func:`evidence.store_path` has none."""
    store = evidence.store_path(project_dir)
    return None if store is None else store.parent / CACHE_BASENAME


def _key(base_tree: str, target_tree: str, fingerprint: str) -> str:
    return hashlib.sha256(
        "\0".join((str(CACHE_SCHEMA), base_tree, target_tree, fingerprint)).encode()
    ).hexdigest()


def _read(path: Path) -> dict:
    """The cache file's entries, or ``{}`` for anything unreadable, malformed,
    or written under a different schema. Never raises: a cache that cannot be
    read is a cache miss, and a cache miss is only ever slower."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    if not isinstance(data, dict) or data.get("schema") != CACHE_SCHEMA:
        return {}
    entries = data.get("entries")
    return entries if isinstance(entries, dict) else {}


class VerdictCache:
    """One gate invocation's view of the memo. Built once, consulted by every
    call site that needs a composed verdict — the span itself and each
    diagnosis — so they share both the disk cache and the in-process one.

    Construct with :meth:`for_project`; a cache whose fingerprint could not be
    computed is *inert* (every call recomputes), so callers need no special
    case for "no store" or "unreadable store".
    """

    def __init__(self, path: "Path | None", fingerprint: "str | None"):
        self._path = path
        self._fingerprint = fingerprint
        self._enabled = path is not None and fingerprint is not None
        self._disk: "dict | None" = None
        self._memory: dict[str, dict] = {}
        self._dirty = False
        self.hits = 0
        self.misses = 0

    @classmethod
    def for_read(cls, project_dir: Path, read: dict) -> "VerdictCache":
        """Build the memo from the ``read_facts`` result whose facts it will be
        asked about.

        The fingerprint comes from that read rather than from a second look at
        the store, and that is a correctness property, not a saved syscall: the
        store is shared by every worktree of the clone, so two reads are two
        moments, and a sibling's ``critic-consolidate`` landing between them
        yields a key that does not describe the facts it was computed for.
        Taking both from one read makes the pairing structural — there is no
        window to lose.
        """
        return cls(cache_path(project_dir), read.get("fingerprint"))

    @property
    def enabled(self) -> bool:
        return self._enabled

    def verdict(
        self,
        facts: list[dict],
        base_tree: str,
        target_tree: str,
        diff_fn,
        key_fn,
    ) -> dict:
        """:func:`coverage_algebra.coverage_verdict`, memoized.

        **``facts`` must be the parse of the store this cache was fingerprinted
        from.** It is deliberately not in the key — hashing a 2,700-element
        structure per lookup would cost what the memo saves — so the fingerprint
        stands in for it, and that substitution is only sound while the two
        describe the same bytes. :meth:`for_read` is what makes that hold:
        both come out of one ``read_facts``. A caller that filtered the list, or
        paired a cache with a different read, would be asking a different
        question under an unchanged key.

        Returns a fresh copy every time, so a caller that annotates the verdict
        (``check_cumulative_critic`` adds ``base``/``target``/``base_source``)
        cannot mutate what the next caller — or the next gate call — reads back.
        """
        if not self._enabled or not base_tree or not target_tree:
            return coverage_algebra.coverage_verdict(
                facts, base_tree, target_tree, diff_fn, key_fn
            )
        key = _key(base_tree, target_tree, self._fingerprint)
        if key in self._memory:
            self.hits += 1
            return json.loads(json.dumps(self._memory[key]))
        if self._disk is None:
            self._disk = _read(self._path)
        cached = self._disk.get(key)
        if isinstance(cached, dict) and isinstance(cached.get("status"), str):
            self.hits += 1
            self._memory[key] = cached
            return json.loads(json.dumps(cached))
        self.misses += 1
        verdict = coverage_algebra.coverage_verdict(
            facts, base_tree, target_tree, diff_fn, key_fn
        )
        self._memory[key] = verdict
        self._dirty = True
        return json.loads(json.dumps(verdict))

    def flush(self) -> bool:
        """Persist newly computed verdicts. ``True`` when something was written.

        Best-effort by contract: a cache that fails to save costs the next call
        a recomputation and nothing else, so an ``OSError`` here must not turn a
        correct verdict into a gate failure. Re-reads the file first, so a
        sibling worktree's concurrent entries survive this write — last-writer
        semantics lose entries, and a lost entry is only ever slower.
        """
        if not self._enabled or not self._dirty:
            return False
        merged = _read(self._path)
        merged.update(self._memory)
        # Newest-last insertion order is what `dict` preserves, so trimming from
        # the front drops the oldest.
        if len(merged) > MAX_ENTRIES:
            merged = dict(list(merged.items())[-MAX_ENTRIES:])
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(
                self._path,
                json.dumps({"schema": CACHE_SCHEMA, "entries": merged}),
            )
        except OSError:
            return False
        self._dirty = False
        return True
