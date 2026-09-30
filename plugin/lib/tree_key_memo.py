"""Persistent memo of each git tree's judgeable-content key.

The coverage verdict groups trees by a key over their judgeable content
(``gates._tree_key_fn``), and computing one costs a ``git ls-tree -r`` of the
whole tree. Every tree the evidence store mentions is keyed on every verdict,
and the store is append-only and shared by every worktree of the clone. So a
per-process memo still pays for the whole store on every SessionStart and every
Stop, and that cost grows with the store's age rather than with the work in
front of it. Measured on a consumer repo's snapshot (231 trees): about 4 s of a
6.4 s Stop hook, the same on every plugin version from 3.5.1-dev.2 to
3.7.0-dev.2. A consumer with 1,743 trees saw Stop hooks of a minute or more.
This memo makes each tree cost once per clone.

**A memo, not a view** (``data-model.md``: *derived views are disposable and
never authoritative*). The same argument :mod:`verdict_cache` makes applies:
the entry's key covers every input the value is a function of. A tree SHA names
immutable content, and the rest is the code that classifies paths as judgeable,
which :func:`_identity` folds in through the plugin version and the checkout's
code identity. A hit therefore replays a computation whose inputs are provably
unchanged, and deleting the file loses nothing but time.

**It can never grant a free edge the slow path would deny.** Only a computed key
is stored; an unreadable tree (``None``) is never memoised, so it is re-asked
next time and keeps denying the edge until git can read it. An unreadable,
malformed or foreign-schema file, and any entry that is not a well-formed
key, reads as a miss. Trust is the same as the evidence store's beside it:
whoever can rewrite this file can rewrite the facts.
"""

from __future__ import annotations

import atexit
import hashlib
import json
import re
from pathlib import Path

from . import evidence, verdict_cache
from .core import atomic_write_text

MEMO_BASENAME = "tree-keys.json"

#: Bumped when the key's derivation changes shape in a way the code identity
#: would not see (an installed copy's identity is only its version string).
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

_OBJECT_ID = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_KEY = re.compile(r"^[0-9a-f]{64}$")

#: One memo per memo file per process, so every key function a gate builds
#: shares both the disk read and the unsaved entries.
_MEMOS: "dict[Path, TreeKeyMemo]" = {}


def memo_path(project_dir: Path) -> "Path | None":
    """The memo beside the evidence store, or ``None`` outside a git repo."""
    store = evidence.store_path(project_dir)
    return None if store is None else store.parent / MEMO_BASENAME


def _identity() -> str:
    """What names the code that computed a key: the memo schema, the plugin
    version and, on a git checkout, the plugin tree (``verdict_cache``'s code
    identity, which also fingerprints uncommitted edits)."""
    return hashlib.sha256(
        "\0".join((
            str(MEMO_SCHEMA),
            evidence._plugin_version() or "unversioned",
            verdict_cache._code_identity(),
        )).encode()
    ).hexdigest()[:16]


def _read(path: Path) -> dict:
    """The file's well-formed entries, or ``{}``. Never raises: a memo that
    cannot be read is a miss, and a miss is only ever slower."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    if not isinstance(data, dict) or data.get("schema") != MEMO_SCHEMA:
        return {}
    entries = data.get("entries")
    if not isinstance(entries, dict):
        return {}
    return {
        k: v for k, v in entries.items()
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
        self.hits = 0
        self.misses = 0

    def _entry(self, tree: str) -> str:
        return f"{self._identity}:{tree}"

    def get(self, tree: str) -> "str | None":
        """The memoised key for ``tree``, or ``None`` on a miss."""
        if self._path is None or not _OBJECT_ID.match(tree or ""):
            return None
        entry = self._entry(tree)
        if entry in self._pending:
            self.hits += 1
            return self._pending[entry]
        if self._disk is None:
            self._disk = _read(self._path)
        key = self._disk.get(entry)
        if key is None:
            self.misses += 1
            return None
        self.hits += 1
        self._touched.append(entry)
        return key

    def put(self, tree: str, key: str) -> None:
        """Remember a COMPUTED key. The caller never passes the ``None`` of an
        unreadable tree: that must be re-asked, not replayed."""
        if self._path is None or not _OBJECT_ID.match(tree or "") or not _KEY.match(key or ""):
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
        if self._path is None or not self._pending:
            return False
        merged = _read(self._path)
        for entry in self._touched:
            if entry in merged:
                merged[entry] = merged.pop(entry)
        merged.update(self._pending)
        if len(merged) > MAX_ENTRIES:
            merged = dict(list(merged.items())[-MAX_ENTRIES:])
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(
                self._path,
                json.dumps({"schema": MEMO_SCHEMA, "entries": merged}, separators=(",", ":")),
            )
        except OSError:
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
    """Save every memo this process holds (the exit handler)."""
    for memo in list(_MEMOS.values()):
        memo.flush()


atexit.register(flush_all)
