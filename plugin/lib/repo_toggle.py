"""Per-repo plugin enable/disable toggle — the writer behind ``/prawduct:repo-disable``.

The Prawduct plugin installs at **user** scope, so its hooks and skills load in
every repo the user opens. v2.0.11 made the SessionStart hooks silent in repos
without a ``.prawduct/`` directory, but the ``/prawduct:*`` commands and the
one-line version banner still appear everywhere. To turn Prawduct OFF entirely in
a specific repo — commands included — a project-scope (or local-scope)
``enabledPlugins`` override is the native lever (it beats the user-scope enable).

This module writes that override the safe way:

  * It merges ``"enabledPlugins": {"prawduct@prawduct": false}`` into the chosen
    settings file, **preserving every other key** (permissions, env, hooks, other
    plugins/marketplaces, and prawduct's own install reference under
    ``extraKnownMarketplaces`` — left intact so re-enabling is a one-line edit).
  * Unlike ``migrate_plugin.transform_settings`` (which runs in a migration where a
    reset is acceptable), this **aborts** if the target file exists but is not
    valid JSON, or is not a JSON object — it must never clobber a user's settings.
  * It is idempotent: a file already pinning the plugin to ``false`` is a no-op.

There is deliberately no enable counterpart here: once the plugin is disabled in a
repo, its own skills do not load, so a ``/prawduct:repo-enable`` skill could never
run there. Re-enabling is a documented manual edit (set the value back to ``true``
or delete the key) — see ``skills/repo-disable/SKILL.md``.
"""
from __future__ import annotations

import json
from pathlib import Path

# The plugin identifier as it appears under ``enabledPlugins`` — ``<plugin>@<marketplace>``.
# Matches ``migrate_plugin.INSTALL_REFERENCE``'s ``enabledPlugins`` key.
PLUGIN_ID = "prawduct@prawduct"

# Settings file per scope. Project = committed (team-wide); local = auto-gitignored
# by Claude Code (just-me). Local wins over project wins over user in the settings
# hierarchy, so either reliably overrides the user-scope enable.
_SCOPE_FILES = {
    "project": ".claude/settings.json",
    "local": ".claude/settings.local.json",
}


def set_repo_disabled(
    project_dir: str | Path, *, local: bool = False, apply: bool = False
) -> dict:
    """Plan or apply disabling the Prawduct plugin for ``project_dir``.

    ``local=True`` targets ``.claude/settings.local.json`` (auto-gitignored, just
    this user); otherwise ``.claude/settings.json`` (committed, whole team).
    ``apply=False`` (default) computes the plan without writing.

    Returns a summary dict. On an unreadable/malformed target it returns
    ``{"error": ...}`` and writes nothing. Keys:

      * ``scope`` / ``target`` — chosen scope and its repo-relative file
      * ``file_existed`` — whether the settings file was already present
      * ``previous_value`` — prior ``enabledPlugins["prawduct@prawduct"]``
        (``True`` / ``False`` / ``None`` if unset)
      * ``already_disabled`` — prior value was already ``False`` (no-op)
      * ``change_needed`` — the write would change state (the dry-run signal)
      * ``applied`` — a write actually happened (only true when ``apply`` and
        ``change_needed``)
    """
    scope = "local" if local else "project"
    rel = _SCOPE_FILES[scope]
    path = Path(project_dir) / rel
    existed = path.is_file()

    if existed:
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            return {"scope": scope, "target": rel, "error": f"could not read {rel}: {exc}"}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            # Never clobber a user's settings: a malformed file is a fix-it-first
            # condition, not a reset-to-default one.
            return {
                "scope": scope,
                "target": rel,
                "error": f"{rel} is not valid JSON ({exc}); fix it manually, then retry",
            }
        if not isinstance(data, dict):
            return {
                "scope": scope,
                "target": rel,
                "error": f"{rel} is not a JSON object; refusing to overwrite",
            }
    else:
        data = {}

    enabled = data.get("enabledPlugins")
    previous = enabled.get(PLUGIN_ID) if isinstance(enabled, dict) else None
    already = previous is False

    result = {
        "scope": scope,
        "target": rel,
        "path": str(path),
        "file_existed": existed,
        "previous_value": previous,
        "already_disabled": already,
        "change_needed": not already,
        "applied": False,
    }

    if already or not apply:
        return result

    if not isinstance(enabled, dict):
        enabled = {}
    enabled[PLUGIN_ID] = False
    data["enabledPlugins"] = enabled

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    result["applied"] = True
    return result
