"""Persistent memo of each git tree's judgeable-content key.

The coverage verdict groups trees by a key over their judgeable content
(:func:`judgeable_key`, reached through ``gates._tree_key_fn``), and computing
one costs a ``git ls-tree -r`` of the whole tree. Every tree the evidence store
mentions is keyed on every verdict, and the store is append-only and shared by
every worktree of the clone. So a per-process memo still pays for the whole
store on every SessionStart and every Stop, and that cost grows with the store's
age rather than with the work in front of it. Measured on a consumer repo's
snapshot (231 trees): about 4 s of a 6.4 s Stop hook, the same on every plugin
version from 3.5.1-dev.2 to 3.7.0-dev.2. A consumer with 1,743 trees saw Stop
hooks of a minute or more. This memo makes each tree cost once per clone and
per code identity.

**A memo, not a view** (``data-model.md``: *derived views are disposable and
never authoritative*). Each entry is keyed by every input its value is a
function of: the tree SHA, which names immutable content, and
:func:`verdict_cache.code_identity`, which covers the code that classifies
paths and forms the key (the plugin version, a checkout's plugin tree and the
content of its uncommitted edits, and the bytes of the judgeability and keying
modules, this one included). Deleting the file loses nothing but time.

**It cannot grant a free edge the slow path would deny** under those inputs.
Only a computed key is stored; an unreadable tree (``None``) is never
memoised, so it is re-asked next time and keeps denying the edge until git can
read it. An unreadable, malformed or foreign-schema file, and any entry that is
not a well-formed key, reads as a miss. Trust is the same as the evidence
store's beside it: whoever can rewrite this file can rewrite the facts.
"""

from __future__ import annotations

import atexit
import hashlib
import re
import sys
from pathlib import Path

from . import coverage_algebra, evidence, gitstate, verdict_cache

MEMO_BASENAME = "tree-keys.json"

#: The file format's version. What the keys MEAN is covered by the code
#: identity, which includes this module's bytes, so a change to how a key is
#: formed needs no bump here.
MEMO_SCHEMA = 1

#: Entries kept, least recently used dropped first. Each is roughly 130 bytes,
#: so the file stays near 2.6 MB at the cap and parses in tens of
#: milliseconds, far below the cost it saves. The live population is the
#: store's distinct trees plus the working-tree captures a session makes, and
#: the cap is set well above the largest store measured (1,743 trees).
MAX_ENTRIES = 20_000

#: Computed-but-unsaved keys that trigger a save before the process ends. A
#: hook the harness kills never reaches its exit handler, and a cold store
#: large enough to be killed is exactly the one that must keep its progress.
FLUSH_EVERY = 100

_KEY = re.compile(r"^[0-9a-f]{64}$")

#: One memo per memo file per process, so every key function a gate builds
#: shares both the disk read and the unsaved entries.
_MEMOS: "dict[Path, TreeKeyMemo]" = {}


def judgeable_key(entries: "list[tuple[str, str, str]]") -> str:
    """A tree's key: a digest over its judgeable ``(mode, object, path)``
    entries, so two trees agree exactly when a diff between them holds no
    judgeable path. Lives here so its code is part of the identity every
    memoised key is filed under."""
    judgeable = sorted(
        f"{mode} {object_id} {path}"
        for mode, object_id, path in entries
        if coverage_algebra.is_judgeable_path(path)
    )
    return hashlib.sha256(
        "\n".join(judgeable).encode("utf-8", "surrogateescape")
    ).hexdigest()


def memo_path(project_dir: Path) -> "Path | None":
    """The memo beside the evidence store, or ``None`` outside a git repo."""
    store = evidence.store_path(project_dir)
    return None if store is None else store.parent / MEMO_BASENAME


def _identity() -> str:
    return verdict_cache.code_identity()[:16]


def _read(path: Path) -> dict:
    return {
        k: v for k, v in verdict_cache.read_memo_entries(path, MEMO_SCHEMA).items()
        if isinstance(k, str) and isinstance(v, str) and _KEY.match(v)
    }


class TreeKeyMemo:
    """One memo file's view within a process. Build with :func:`for_project`."""

    def __init__(self, path: "Path | None", identity: str):
        self._path = path
        self._identity = identity
        self._disk: "dict[str, str] | None" = None
        self._pending: dict[str, str] = {}
        self._touched: list[str] = []
        #: Set by a save that failed. From then on nothing retries: each retry
        #: would re-read and rewrite the whole file to fail again, on the cold
        #: run that can least afford it. The exit handler reports it once.
        self.save_failed = False

    def _entry(self, tree: str) -> str:
        return f"{self._identity}:{tree}"

    def get(self, tree: str) -> "str | None":
        """The memoised key for ``tree``, or ``None`` on a miss."""
        if self._path is None or not gitstate.is_object_id(tree):
            return None
        entry = self._entry(tree)
        if entry in self._pending:
            return self._pending[entry]
        if self._disk is None:
            self._disk = _read(self._path)
        key = self._disk.get(entry)
        if key is not None:
            self._touched.append(entry)
        return key

    def put(self, tree: str, key: str) -> None:
        """Remember a COMPUTED key. The caller never passes the ``None`` of an
        unreadable tree: that must be re-asked, not replayed."""
        if self._path is None or not gitstate.is_object_id(tree) or not _KEY.match(key or ""):
            return
        self._pending[self._entry(tree)] = key
        if len(self._pending) >= FLUSH_EVERY:
            self.flush()

    def flush(self) -> bool:
        """Save new keys, refreshing the recency of the ones read. ``True`` when
        something was written. Best-effort: a save that fails costs the next
        process a recomputation, never a verdict. Re-reads the file first so a
        sibling worktree's concurrent entries survive this write."""
        # Recency rides a write that is happening anyway: rewriting the whole
        # file only to reorder it would put that cost on every warm hook.
        if self._path is None or not self._pending or self.save_failed:
            return False
        merged = _read(self._path)
        for entry in self._touched:
            if entry in merged:
                merged[entry] = merged.pop(entry)
        merged.update(self._pending)
        if not verdict_cache.write_memo_entries(self._path, MEMO_SCHEMA, merged, MAX_ENTRIES):
            self.save_failed = True
            return False
        if self._disk is not None:
            self._disk.update(self._pending)
        self._pending.clear()
        self._touched.clear()
        return True


def for_project(project_dir: Path) -> TreeKeyMemo:
    """The process's memo for ``project_dir``'s clone. Inert (every lookup a
    miss, nothing saved) outside a git repo. Its unsaved keys are saved when
    the process exits, and every :data:`FLUSH_EVERY` new keys before that."""
    path = memo_path(project_dir)
    if path is None:
        return TreeKeyMemo(None, "")
    memo = _MEMOS.get(path)
    if memo is None:
        memo = _MEMOS[path] = TreeKeyMemo(path, _identity())
    return memo


def flush_all() -> None:
    """Save every memo this process holds (the exit handler), and say so when
    one could not be saved. Silence there would be indistinguishable from a
    memo that works: every later hook would quietly pay the per-tree cost this
    memo exists to remove, with nothing to point at."""
    for memo in list(_MEMOS.values()):
        memo.flush()
        if memo.save_failed and memo._pending:
            print(
                f"NOTE: the tree-key memo at {memo._path} could not be saved, so "
                f"{len(memo._pending)} tree key(s) computed here will be "
                "recomputed by the next hook. The verdict itself is unaffected.",
                file=sys.stderr,
            )


atexit.register(flush_all)
