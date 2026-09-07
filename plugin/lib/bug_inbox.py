"""Resolve the gitignored ``incoming-bugs/`` drop-box on a co-located checkout.

**Nothing calls this any more.** ``/prawduct:report-bug`` files upstream as a
GitHub issue through the backlog adapter's ``file-upstream`` op, which needs no
co-located checkout and no local pointer; this resolver is what routed a report
to a directory back when the report was a file. It retires together with the
drop-box itself, once the ``untriaged-upstream-reports`` advisory stops counting
files there — the reports already sitting in that directory still need triaging,
and retiring the drop-box before its replacement was live is the one ordering the
design forbids.

The resolution it performs is unchanged and is described below, because the
directory it finds still holds real reports.

Precedence (first usable hit wins):
  1. the ``PRAWDUCT_BUG_INBOX`` environment variable
  2. the first non-blank, non-``#`` line of the gitignored
     ``<project>/.prawduct/.bug-inbox`` pointer file
  3. ``None``

A path is returned only when it names an existing, writable directory. A stale,
missing, or unwritable config resolves to ``None`` — it never raises — so a
plugin-only user is never nagged and a misconfigured path never errors. The
inbox path is machine-specific and therefore deliberately lives in local signals
(env / gitignored file), never in committed project state that would travel to
other clones or CI.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

ENV_VAR = "PRAWDUCT_BUG_INBOX"
POINTER_NAME = ".bug-inbox"  # under <project>/.prawduct/


def _coerce(raw: str | None, base: Path) -> Path | None:
    """Expand, resolve, and validate a candidate; ``None`` if unusable.

    Relative paths resolve against ``base`` (the project root) for determinism.
    The candidate must name an existing, writable directory.
    """
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = base / path
    try:
        path = path.resolve()
    except OSError:
        return None
    if path.is_dir() and os.access(path, os.W_OK):
        return path
    return None


def _read_pointer(pointer: Path) -> str | None:
    """First non-blank, non-comment line of the pointer file, or ``None``."""
    try:
        text = pointer.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return None


def resolve_inbox(environ: Mapping[str, str], project_dir: Path) -> Path | None:
    """Resolve the upstream bug inbox, or ``None``.

    Precedence: ``PRAWDUCT_BUG_INBOX`` env → gitignored ``.prawduct/.bug-inbox``
    pointer → ``None``. A returned path always names an existing, writable
    directory; any failure mode resolves to ``None`` (never raises).
    """
    env_hit = _coerce(environ.get(ENV_VAR), project_dir)
    if env_hit is not None:
        return env_hit
    pointer = project_dir / ".prawduct" / POINTER_NAME
    return _coerce(_read_pointer(pointer), project_dir)
