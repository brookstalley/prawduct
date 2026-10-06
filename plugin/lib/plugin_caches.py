"""Stale plugin caches: prawduct version directories no install uses.

Claude Code keeps every plugin version it installs under each config root's
``plugins/cache/<marketplace>/<plugin>/<version>/`` and never removes one, and
``claude plugin prune`` does not either. Every config root keeps its own set, so
a machine with several profiles collects one pile per profile. Older prawduct
releases shipped the framework's own ``.prawduct/``, tests and documentation in
the plugin tree, so the pile is another product's requirements sitting readable
in every profile, not only disk.

This module answers one question, read-only: which version directories does no
install record use? It deletes nothing. The operator decides, because a session
already running in a profile keeps using the version it started with, and only
they know which sessions are open. ``prawduct-hook stale-plugin-caches`` prints
the answer with a delete command per directory; ``/prawduct:doctor`` relays it.

**A version is in use** when any install record on the machine names it:

* by its ``installPath``, compared resolved, so a record naming the cache
  through a symlinked profile still matches; or
* when the record's path does not exist on this host (a devcontainer record
  says ``/home/vscode/...``), by its ``<marketplace>/<plugin>/<version>`` tail,
  but only for the profile whose record it is; or
* because it is the plugin running this command.

**A profile is one cache, not one config root.** Profiles commonly share
``plugins/`` through a symlink, and counting each root would multiply one pile
by the number of roots pointing at it. A profile whose install record is
missing or unreadable has its versions reported as ungraded, never as stale:
with no record, every version would look unused.
"""

from __future__ import annotations

import json
import os
import shlex
import sys
from pathlib import Path

from lib.stranded_work import config_roots

PLUGIN = "prawduct"
SCHEMA_VERSION = 1

MANIFEST_OK = "ok"
MANIFEST_MISSING = "missing"
MANIFEST_UNREADABLE = "unreadable"


def _resolved(path: Path) -> Path | None:
    try:
        return path.resolve()
    except (OSError, RuntimeError):
        return None


def _tail(path: Path) -> tuple[str, ...]:
    """``(marketplace, plugin, version)`` — the part of a cache path that names
    the same version on any host."""
    return tuple(path.parts[-3:])


def _records(plugins_dir: Path) -> tuple[str, list[dict]]:
    """``(manifest status, this plugin's install records)``."""
    path = plugins_dir / "installed_plugins.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return MANIFEST_MISSING, []
    except (OSError, UnicodeDecodeError, ValueError):
        return MANIFEST_UNREADABLE, []
    plugins = data.get("plugins") if isinstance(data, dict) else None
    if not isinstance(plugins, dict):
        return MANIFEST_UNREADABLE, []
    records: list[dict] = []
    for key, entries in plugins.items():
        if key.split("@", 1)[0] != PLUGIN or not isinstance(entries, list):
            continue
        records.extend(entry for entry in entries if isinstance(entry, dict))
    return MANIFEST_OK, records


def _disk_bytes(path: Path) -> int:
    """Disk usage the way ``du`` counts it: allocated blocks, symlinks not
    followed, each hard-linked file once."""
    total = 0
    seen: set[tuple[int, int]] = set()
    for dirpath, dirnames, filenames in os.walk(path):
        for name in dirnames + filenames:
            try:
                st = os.lstat(os.path.join(dirpath, name))
            except OSError:
                continue
            key = (st.st_dev, st.st_ino)
            if key in seen:
                continue
            seen.add(key)
            blocks = getattr(st, "st_blocks", None)
            total += blocks * 512 if blocks is not None else st.st_size
    return total


def _version_dirs(plugins_dir: Path) -> list[Path]:
    try:
        return sorted(
            version
            for marketplace in (plugins_dir / "cache").iterdir()
            if (marketplace / PLUGIN).is_dir()
            for version in (marketplace / PLUGIN).iterdir()
            if version.is_dir()
        )
    except OSError:
        return []


def scan(
    env: dict | None = None, home: Path | None = None, running_root: Path | None = None
) -> dict:
    """The report: one entry per distinct cache, with what is stale in it."""
    groups: dict[Path, dict] = {}
    for root in config_roots(env, home, holding="plugins"):
        plugins_dir = _resolved(root / "plugins")
        if plugins_dir is None:
            continue
        group = groups.setdefault(plugins_dir, {"roots": [], "plugins_dir": plugins_dir})
        group["roots"].append(root)

    # Every record on the machine, resolved, protects a version in any profile.
    for group in groups.values():
        group["manifest"], group["records"] = _records(group["plugins_dir"])
    protected: set[Path] = set()
    if running_root is not None and (resolved := _resolved(running_root)) is not None:
        protected.add(resolved)
    for group in groups.values():
        group["by_name"] = set()
        for record in group["records"]:
            raw = record.get("installPath")
            if not isinstance(raw, str) or not raw:
                continue
            path = Path(raw).expanduser()
            if path.exists() and (resolved := _resolved(path)) is not None:
                protected.add(resolved)
            else:
                group["by_name"].add(_tail(path))

    profiles = []
    for group in groups.values():
        versions = _version_dirs(group["plugins_dir"])
        if not versions:
            continue
        in_use, stale, ungraded = [], [], []
        for version in versions:
            if _resolved(version) in protected or _tail(version) in group["by_name"]:
                in_use.append(version.name)
            elif group["manifest"] != MANIFEST_OK:
                ungraded.append(version.name)
            else:
                stale.append({"path": str(version), "bytes": _disk_bytes(version)})
        profiles.append({
            "config_roots": [str(root) for root in group["roots"]],
            "cache": str(group["plugins_dir"] / "cache"),
            "manifest": group["manifest"],
            "in_use": in_use,
            "stale": stale,
            "stale_bytes": sum(item["bytes"] for item in stale),
            "ungraded": ungraded,
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "profiles": profiles,
        "stale_count": sum(len(p["stale"]) for p in profiles),
        "stale_bytes": sum(p["stale_bytes"] for p in profiles),
    }


def _mb(count: int) -> str:
    return f"{count / (1024 * 1024):.1f} MB"


def render(report: dict) -> str:
    profiles = report["profiles"]
    if not profiles:
        return "stale-plugin-caches: no config root on this machine holds a prawduct plugin cache"
    lines = [
        f"stale-plugin-caches: {report['stale_count']} unused prawduct version "
        f"director{'y' if report['stale_count'] == 1 else 'ies'}, {_mb(report['stale_bytes'])}, "
        f"across {len(profiles)} cache(s)"
    ]
    for profile in profiles:
        lines.append("")
        lines.append(f"{' + '.join(profile['config_roots'])}")
        lines.append(f"  in use: {', '.join(profile['in_use']) or 'none'}")
        if profile["manifest"] != MANIFEST_OK:
            lines.append(
                f"  not graded: its installed_plugins.json is {profile['manifest']}, so "
                f"nothing here can be called unused ({', '.join(profile['ungraded'])})"
            )
        for item in profile["stale"]:
            lines.append(f"  {Path(item['path']).name}  {_mb(item['bytes'])}  "
                         f"rm -rf {shlex.quote(item['path'])}")
    if report["stale_count"]:
        lines.append("")
        lines.append(
            "Close every Claude Code session in a profile before deleting its directories: "
            "a running session keeps using the version it started with."
        )
    return "\n".join(lines)


def stale_plugin_caches_cmd(argv: list[str], running_root: Path | None = None) -> int:
    """``prawduct-hook stale-plugin-caches [--json]``. Read-only. Exit 0 with a
    report, ungraded profiles included (each is named in it); 2 on bad usage."""
    unknown = [a for a in argv if a != "--json"]
    if unknown:
        print(
            f"stale-plugin-caches: unknown argument(s) {unknown}; "
            "usage: prawduct-hook stale-plugin-caches [--json]",
            file=sys.stderr,
        )
        return 2
    report = scan(running_root=running_root)
    print(json.dumps(report, indent=1) if "--json" in argv else render(report))
    return 0
