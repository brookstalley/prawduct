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

Records are read under every ``prawduct@<marketplace>`` key, because the
cache is scanned under every marketplace directory; a record from another
marketplace protects the directory it names.

**A profile is one cache, not one config root.** Profiles commonly share
``plugins/`` through a symlink, and counting each root would multiply one pile
by the number of roots pointing at it.

**Anything unreadable grades nothing.** A profile whose install record is
missing, unreadable, or holds one record this module cannot read has its
versions reported as ungraded, never as stale: an unreadable record might be
the one protecting a version, and a delete command for the version a profile
loads is the one wrong answer this report must never give. The manifest itself
is read through :func:`lib.plugin_activation.read_installed_plugins`, the one
reader of that file. A cache directory that cannot be listed is reported, not
dropped.
"""

from __future__ import annotations

import json
import os
import shlex
import sys
from pathlib import Path

from lib.plugin_activation import (
    MANIFEST_MISSING,
    MANIFEST_OK,
    MANIFEST_UNREADABLE,
    read_installed_plugins,
)
from lib.stranded_work import config_roots

PLUGIN = "prawduct"
SCHEMA_VERSION = 1

#: The profile's cache could not be listed, so nothing in it was graded.
CACHE_UNREADABLE = "cache unreadable"


def _resolved(path: Path) -> Path | None:
    try:
        return path.resolve()
    except (OSError, RuntimeError):
        return None


def _tail(path: Path) -> tuple[str, ...]:
    """``(marketplace, plugin, version)`` — the part of a cache path that names
    the same version on any host."""
    return tuple(path.parts[-3:])


def _install_paths(plugins_dir: Path) -> tuple[str, list[Path]]:
    """``(manifest status, every install path this plugin's records name)``.
    One record in a shape this cannot read makes the whole file unreadable."""
    read = read_installed_plugins(plugins_dir / "installed_plugins.json")
    if read["status"] != MANIFEST_OK:
        return read["status"], []
    paths: list[Path] = []
    for key, entries in read["plugins"].items():
        if not isinstance(key, str) or key.split("@", 1)[0] != PLUGIN:
            continue
        if not isinstance(entries, list):
            return MANIFEST_UNREADABLE, []
        for entry in entries:
            raw = entry.get("installPath") if isinstance(entry, dict) else None
            if not isinstance(raw, str) or not raw:
                return MANIFEST_UNREADABLE, []
            try:
                paths.append(Path(raw).expanduser())
            except RuntimeError:  # `~user` naming no user on this host
                return MANIFEST_UNREADABLE, []
    return MANIFEST_OK, paths


def _exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def _disk_bytes(path: Path) -> int:
    """Disk usage the way ``du`` counts it: allocated blocks, symlinks not
    followed, each hard-linked file once."""
    total = 0
    seen: set[tuple[int, int]] = set()
    # The directory's own entry counts too: `du` includes it, and on Linux it
    # holds blocks of its own.
    entries = [str(path)]
    for dirpath, dirnames, filenames in os.walk(path):
        entries.extend(os.path.join(dirpath, name) for name in dirnames + filenames)
    for entry in entries:
        try:
            st = os.lstat(entry)
        except OSError:
            continue
        key = (st.st_dev, st.st_ino)
        if key in seen:
            continue
        seen.add(key)
        blocks = getattr(st, "st_blocks", None)
        total += blocks * 512 if blocks is not None else st.st_size
    return total


def _version_dirs(plugins_dir: Path) -> list[Path] | None:
    """Every version directory of this plugin in the cache, or ``None`` when
    the cache exists and cannot be listed."""
    cache = plugins_dir / "cache"
    if not cache.is_dir():
        return []
    try:
        return sorted(
            version
            for marketplace in cache.iterdir()
            if (marketplace / PLUGIN).is_dir()
            for version in (marketplace / PLUGIN).iterdir()
            if version.is_dir()
        )
    except OSError:
        return None


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
        group["manifest"], group["paths"] = _install_paths(group["plugins_dir"])
    protected: set[Path] = set()
    if running_root is not None and (resolved := _resolved(running_root)) is not None:
        protected.add(resolved)
    for group in groups.values():
        group["by_name"] = set()
        for path in group["paths"]:
            if _exists(path) and (resolved := _resolved(path)) is not None:
                protected.add(resolved)
            else:
                group["by_name"].add(_tail(path))

    profiles = []
    for group in groups.values():
        versions = _version_dirs(group["plugins_dir"])
        if versions is None:
            profiles.append({
                "config_roots": [str(root) for root in group["roots"]],
                "cache": str(group["plugins_dir"] / "cache"),
                "manifest": CACHE_UNREADABLE,
                "in_use": [], "stale": [], "stale_bytes": 0, "ungraded": [],
            })
            continue
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
        if profile["manifest"] == CACHE_UNREADABLE:
            lines.append(f"  not graded: {profile['cache']} could not be listed")
        elif profile["manifest"] != MANIFEST_OK:
            what = "missing" if profile["manifest"] == MANIFEST_MISSING else "unreadable"
            lines.append(
                f"  not graded: its installed_plugins.json is {what}, so "
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
