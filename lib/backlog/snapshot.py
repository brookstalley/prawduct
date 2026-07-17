"""Snapshot — the ``briefing_counts`` degenerate cache (GV2/M3).

The **only** persisted count in the slice (Data Model §6): a tiny JSON file that
lets session start show backlog counts **without waiting on the network** and
**never silently stale** (G3) — every read carries a visible age. It is a
*degenerate cache*, subordinate to GitHub and never treated as truth; the live,
always-derived rollup is ``query.counts`` (Q5). The full SQLite cache (item
bodies, FTS, relationships) is a post-slice layer (W1) — this file is just the
counts floor the PRD admits (M3).

**Location.** ``<git-common-dir>/prawduct/backlog-counts.json`` — the same
clone-shared directory the evidence store uses (``lib/evidence.py``). Chosen for
the same reasons: one location every worktree of a clone already shares
(per-clone, D5), **never committed** (inside ``.git``, so no ``.gitignore``
contract to get wrong — the F5 content-borne-secret concern is about the working
-tree SQLite cache, W1, not this), and isolated between unrelated repos by
construction. An absent file *is* the empty snapshot (lazy init).

**Layering.** Pure filesystem — no transport, no model, no network. The *reader*
(session start / briefing) calls :func:`read` in-process for a zero-latency,
network-independent count (BLOCK-5); the *writer* is ``refresh-counts``
(``query.refresh_counts``), run inline or warmed by a detached subprocess
(:func:`spawn_refresh`, the D6 pattern — sync core, subprocess warm, no asyncio).
Errors are return values (never raises) per project-preferences.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# The persisted-format version (Data Model §7): a mismatch means "discard and
# re-derive" — the snapshot is a cache, so dropping an unreadable one is always
# safe (never a data-loss migration). Bumped only on an incompatible layout.
SCHEMA_VERSION = 1

STORE_SUBDIR = "prawduct"
STORE_BASENAME = "backlog-counts.json"


def snapshot_path(project_dir: Path) -> Path | None:
    """The clone-shared snapshot path, or ``None`` outside a git repo.

    Keyed off ``--git-common-dir`` so every worktree of a clone shares one file
    (mirrors ``evidence.store_path``). ``None`` when ``project_dir`` is not in a
    git work tree — the caller degrades (refresh returns fresh-but-unpersisted;
    read returns ``None``), never crashes.
    """
    from .. import gitstate  # noqa: PLC0415 — lazy: only the resolver needs git

    common = gitstate.git_common_dir(project_dir)
    if common is None:
        return None
    return common / STORE_SUBDIR / STORE_BASENAME


def _load(path: Path) -> dict:
    """Read the whole snapshot file, tolerant of absence/corruption.

    An absent file is the empty snapshot ``{}``; a corrupt or wrong-schema file
    is treated the same (a cache is disposable — never a hard error), with a
    stderr note so the drop is never silent."""
    try:
        raw = path.read_text()
    except FileNotFoundError:
        return {"schema": SCHEMA_VERSION, "scopes": {}}
    except OSError as exc:
        _diag(f"could not read snapshot {path.name}: {type(exc).__name__}")
        return {"schema": SCHEMA_VERSION, "scopes": {}}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        _diag(f"snapshot {path.name} is unparseable; treating as empty (cache is disposable)")
        return {"schema": SCHEMA_VERSION, "scopes": {}}
    if not isinstance(data, dict) or data.get("schema") != SCHEMA_VERSION:
        _diag(f"snapshot {path.name} schema mismatch; discarding (will re-derive)")
        return {"schema": SCHEMA_VERSION, "scopes": {}}
    scopes = data.get("scopes")
    if not isinstance(scopes, dict):
        return {"schema": SCHEMA_VERSION, "scopes": {}}
    return {"schema": SCHEMA_VERSION, "scopes": scopes}


def write(path: Path, scope: str, counts: dict, *, now: datetime | None = None) -> dict:
    """Persist ``counts`` for ``scope``, stamped ``fetched_at`` (visible age).

    **Atomic** (temp file + ``os.replace``) so a crash mid-write can never leave a
    corrupt snapshot — the old file survives intact (a torn write is impossible).
    Merges into the scope-keyed map, so refreshing one project never drops
    another's counts. Returns ``{"status": "written", "path", "fetched_at"}`` or
    ``{"status": "error", "reason": ...}`` — never raises.
    """
    now = now or datetime.now(timezone.utc)
    fetched_at = _iso(now)
    data = _load(path)
    data["scopes"][scope] = {"counts": counts, "fetched_at": fetched_at}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(data, handle)
            os.replace(tmp, path)  # atomic on POSIX — the old file is never torn
        finally:
            # If replace already consumed tmp this is a harmless no-op.
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass
    except OSError as exc:
        return {"status": "error", "reason": f"{type(exc).__name__}"}
    return {"status": "written", "path": str(path), "fetched_at": fetched_at}


def read(path: Path, scope: str, *, now: datetime | None = None) -> dict | None:
    """Read ``scope``'s persisted counts with a **visible age**, or ``None``.

    Touches **no network** — the never-block session-start read (BLOCK-5). Returns
    ``{"scope", "counts", "fetched_at", "age_seconds"}``; ``age_seconds`` is the
    G3 visible-age (``None`` only if ``fetched_at`` is unparseable, which a write
    never produces). ``None`` when the scope has no snapshot yet (the caller
    degrades to a live read or a clear ``unavailable`` — never a hang).
    """
    entry = _load(path)["scopes"].get(scope)
    if not isinstance(entry, dict) or "counts" not in entry:
        return None
    now = now or datetime.now(timezone.utc)
    fetched_at = entry.get("fetched_at")
    age = _age_seconds(fetched_at, now)
    return {
        "scope": scope,
        "counts": entry.get("counts"),
        "fetched_at": fetched_at,
        "age_seconds": age,
    }


def spawn_refresh(
    hook_cmd: list[str],
    project_dir: Path,
    scope: str,
    *,
    popen=None,
    env: dict | None = None,
) -> bool:
    """Warm the snapshot in a **detached** subprocess (D6 — no asyncio, no wait).

    Fire-and-forget: launches ``<hook_cmd> backlog refresh-counts --repo <scope>``
    in its own session, marked ``PRAWDUCT_UNATTENDED=1``, and returns
    **immediately** — session start never blocks on the refresh (that is the whole
    point of the degenerate-cache floor). This is the *policy* (what to warm, under
    which context); the detached-Popen *mechanism* lives in ``transport`` (the sole
    subprocess egress — the egress-discipline invariant), so no ``subprocess``
    import lands here. ``hook_cmd`` is the argv prefix that reaches
    ``prawduct-hook`` (resolved by the briefing wiring); ``popen`` is injectable
    for tests. Returns ``True`` if the spawn was issued, ``False`` otherwise (never
    raises — a failed warm just means the next read is a touch staler)."""
    from .transport import spawn_detached  # noqa: PLC0415 — lazy; transport owns egress

    child_env = dict(env if env is not None else os.environ)
    child_env["PRAWDUCT_UNATTENDED"] = "1"
    argv = [*hook_cmd, "backlog", "refresh-counts", "--repo", scope]
    return spawn_detached(argv, cwd=project_dir, env=child_env, popen=popen)


def _age_seconds(fetched_at: str | None, now: datetime) -> int | None:
    from .encode import parse_iso  # noqa: PLC0415 — reuse the tolerant ISO parser

    stamped = parse_iso(fetched_at)
    if stamped is None:
        return None
    return max(0, int((now - stamped).total_seconds()))


def _iso(now: datetime) -> str:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _diag(message: str) -> None:
    print(f"backlog: {message}", file=sys.stderr)
