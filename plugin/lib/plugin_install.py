"""Machine-level plugin install state — is prawduct actually installed for a path?

A repo's committed ``.claude/settings.json`` declares **enablement**. Claude Code's
``~/.claude/plugins/installed_plugins.json`` records **installation**, keyed by
``(scope, projectPath)``. The two are separate facts, and a repo can carry a
perfect install reference while no entry exists for it — in which case the plugin
never loads there: no session banner, no ``/prawduct:*`` skills, no Stop-hook
gates, and a ``CLAUDE.md`` anchor that asserts enforcement is structural while
nothing enforces anything.

``lib/install_reference_probes`` grades the committed half and states this as its
"Known limit": what binds resolution at runtime is machine-level, outside
``${CLAUDE_PROJECT_DIR}``, which the hook runtime does not leave. This module is
the other half — the machine-level read, for the two callers that *can* do it:
``lib/init_product`` (a CLI command the onboard skill invokes with an explicit
target) and ``/prawduct:doctor`` Health Check #19 (model-side). Neither is a hook.

**Read-only, always.** Nothing here writes to the operator's config home. That
keeps the module inside the least-authority Direction that makes running prawduct
a safe trust decision (``architecture.md``): the plugin writes into a governed
repo, never into ``~/.claude``.

**Fail toward alarming.** ``installed`` is answered only for an exact resolved-path
match or a ``user``-scope entry. An ancestor-directory entry is deliberately NOT
accepted as covering, because whether Claude Code matches ``projectPath`` exactly
or by prefix could not be verified (the CLI ships as a packed binary, and every
machine available for testing carried a ``user``-scope entry that would mask the
difference). The two error directions are not symmetric: a false alarm costs one
idempotent ``claude plugin install`` invocation, while a false all-clear recreates
the silently-ungoverned repo this module exists to detect. If the prefix reading
turns out to be right, the cost is a redundant remedy, never a missed one.

**Advice fails soft.** Every answer is a ``{"status", "reason", ...}`` dict; nothing
raises and nothing here decides an exit code. Callers report it — the install
state of one path on one machine is not a verdict on whether a scaffold succeeded.
"""

from __future__ import annotations

import json
import os
import shlex
from pathlib import Path

# One derivation, one owner: ``migrate_plugin`` derives the ``name@marketplace``
# key from ``INSTALL_REFERENCE`` (the install contract), which is the same key
# Claude Code uses in ``installed_plugins.json``. Re-deriving it here would be a
# second copy that can drift; importing it cannot.
from .migrate_plugin import PLUGIN_KEY

__all__ = [
    "PLUGIN_KEY",
    "config_home",
    "install_status",
    "installed_plugins_path",
    "remedy_for",
]

#: Scopes that cover a path without naming it. ``user`` is machine-wide; ``project``
#: and ``local`` are path-keyed and must match exactly.
_WILDCARD_SCOPES = frozenset({"user"})


def config_home() -> Path | None:
    """Claude Code's config home — ``$CLAUDE_CONFIG_DIR`` or ``~/.claude``.

    ``None`` when the home directory cannot be resolved. ``Path.home()`` raises in
    that case rather than returning anything, and this function is called from
    inside a *scaffold*: letting the exception out would mean an unresolvable HOME
    takes down `init-product`, i.e. the advice killing the operation it advises on.
    Advice fails soft, so the caller gets "could not ask" instead.

    A deliberate twin of ``hooks/banner.py``'s ``managed_plugin_home``. The hooks
    are invoked as bare scripts with no ``lib/`` on ``sys.path``, so sharing this
    would mean a ``sys.path`` insert in the session-start hot path to save four
    lines. Two copies, named on both sides, is the cheaper trade.
    """
    cfg = os.environ.get("CLAUDE_CONFIG_DIR")
    if cfg:
        return Path(cfg)
    try:
        return Path.home() / ".claude"
    except (OSError, RuntimeError):
        return None


def installed_plugins_path() -> Path | None:
    """The registry file recording which plugins are installed, and for what."""
    home = config_home()
    return None if home is None else home / "plugins" / "installed_plugins.json"


def _resolve(path: str | Path) -> Path | None:
    """Best-effort absolute resolution; ``None`` when the path cannot be resolved."""
    try:
        return Path(path).expanduser().resolve()
    except (OSError, RuntimeError, ValueError):
        return None


def remedy_for(project_dir: str | Path) -> str:
    """The exact command that installs prawduct for ``project_dir``.

    The ``cd`` is not decoration: ``claude plugin install --scope project`` keys the
    entry on the *current* directory, and the caller that most needs this string
    (``/prawduct:onboard <target>``) is by construction running somewhere else.
    """
    # Quoted: the caller supplies this path and a space in it turns a pasted
    # remedy into `cd /Users/me/My` — which usually succeeds somewhere else and
    # installs project-scope into the wrong directory.
    return f"cd {shlex.quote(str(project_dir))} && claude plugin install {PLUGIN_KEY} --scope project"


def install_status(project_dir: str | Path) -> dict:
    """Is prawduct installed for ``project_dir`` on THIS machine, right now?

    Returns ``{"status", "reason", "scope", "registry", "remedy"}``:

    - ``status: "installed"`` — an exact-path or ``user``-scope entry exists.
      ``scope`` names which; ``remedy`` is ``None``.
    - ``status: "absent"`` — the registry is readable and has no entry covering
      this path. Governance will NOT load in the target's own session.
    - ``status: "unchecked"`` — the registry could not be read or parsed. This is
      "could not ask", never "fine": an unreadable registry and an empty one give
      the same silence, so they must not give the same answer.

    ``reason`` is a complete sentence in every branch, including the good one — a
    caller rendering only failures still has something honest to print.

    The scope of the answer is deliberately narrow: **this path, this machine, this
    moment.** A fresh clone by another developer legitimately has no entry until
    their own trust prompt, and that is not a defect in the repo. Callers must say
    so rather than letting ``absent`` read as "the repo is misconfigured".
    """
    registry = installed_plugins_path()
    target = _resolve(project_dir)

    if registry is None:
        return _unchecked(
            None,
            project_dir,
            "cannot locate the Claude Code config home ($CLAUDE_CONFIG_DIR unset "
            "and the home directory did not resolve)",
        )

    if target is None:
        # The one branch where an empty answer and a could-not-ask answer would
        # otherwise collide: with no resolved target every `projectPath` entry is
        # unreachable, so the scan falls through to `absent` and asserts a registry
        # fact when the truth is that the path never resolved.
        return _unchecked(registry, project_dir, f"could not resolve the path {project_dir}")

    try:
        raw = registry.read_text(encoding="utf-8")
    except FileNotFoundError:
        # A registry that has never been written is a real, readable answer:
        # nothing is installed, for anything. Not the same as unparseable.
        return {
            "status": "absent",
            "reason": (
                f"no plugin registry at {registry} — no Claude Code plugin is "
                "installed on this machine, so prawduct will not load"
            ),
            "scope": None,
            "registry": str(registry),
            "remedy": remedy_for(project_dir),
        }
    except OSError as exc:
        return _unchecked(registry, project_dir, f"could not read {registry}: {exc}")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return _unchecked(registry, project_dir, f"{registry} is not valid JSON: {exc}")

    if not isinstance(data, dict):
        return _unchecked(registry, project_dir, f"{registry} is not a JSON object")

    plugins = data.get("plugins")
    if not isinstance(plugins, dict):
        # A registry with no `plugins` mapping is structurally unexpected. Reading
        # it as "nothing installed" would be a guess about a shape we do not
        # control; say we could not tell.
        return _unchecked(
            registry, project_dir, f"{registry} has no readable 'plugins' mapping"
        )

    entries = plugins.get(PLUGIN_KEY)
    if not isinstance(entries, list):
        entries = []

    # Both kinds of match are scanned before either is reported, and the
    # path-scoped one wins. First-match-wins would make the answer depend on the
    # registry's list order, and the ONE fact doctor Health Check #19 exists to
    # report is "`user`-scope only" — this repo runs on a machine-wide install and
    # carries nothing of its own. That claim is only true if a path entry, when
    # one exists, is what gets reported.
    wildcard_scope: str | None = None
    path_scope: str | None = None

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        scope = entry.get("scope")
        if scope in _WILDCARD_SCOPES:
            if wildcard_scope is None:
                wildcard_scope = scope
            continue
        entry_path = entry.get("projectPath")
        if not isinstance(entry_path, str) or target is None:
            continue
        if path_scope is None and _resolve(entry_path) == target:
            path_scope = scope or "project"

    if path_scope is not None:
        return {
            "status": "installed",
            "reason": f"{PLUGIN_KEY} is installed at {path_scope} scope for {target}",
            "scope": path_scope,
            "registry": str(registry),
            "remedy": None,
        }

    if wildcard_scope is not None:
        return {
            "status": "installed",
            "reason": (
                f"{PLUGIN_KEY} is installed at {wildcard_scope} scope and has no "
                f"entry of its own for this path — it loads here because of a "
                f"machine-wide install, so a clone of this repo on another machine "
                f"gets nothing from it"
            ),
            "scope": wildcard_scope,
            "registry": str(registry),
            "remedy": None,
        }

    shown = target if target is not None else project_dir
    return {
        "status": "absent",
        "reason": (
            f"{PLUGIN_KEY} has no entry in {registry} covering {shown} — the "
            "committed install reference enables the plugin but does not install "
            "it, so this repo's own session gets no banner, no /prawduct:* skills "
            "and no Stop-hook gates"
        ),
        "scope": None,
        "registry": str(registry),
        "remedy": remedy_for(project_dir),
    }


def _unchecked(registry: Path | None, project_dir: str | Path, why: str) -> dict:
    """The could-not-ask answer, with its consequence named.

    Advice fails soft, but soft is not silent: a caller that prints only ``why``
    tells the operator a file was unreadable without telling them what it cost.
    """
    return {
        "status": "unchecked",
        "reason": (
            f"{why} — cannot confirm whether {PLUGIN_KEY} is installed for this "
            "path; if it is not, governance will be silently inactive there"
        ),
        "scope": None,
        "registry": str(registry) if registry is not None else None,
        "remedy": remedy_for(project_dir),
    }
