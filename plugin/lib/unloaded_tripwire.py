"""The project-level SessionStart hook that says when prawduct is NOT loaded.

Everything prawduct ships that could notice an unloaded plugin — the banner, the
Stop gates, the skills, the advisory probes — is delivered BY the plugin, so in a
session that loaded no plugin none of it runs and nothing says so. A hook in the
product repo's own committed ``.claude/settings.json`` is the one thing that runs
either way: Claude Code merges project hooks with plugin hooks, and runs project
hooks whether or not any plugin loaded. A SessionStart hook's plain stdout is
added to the agent's context, so the hook's job is to print one line when the
install record lacks this repo, and nothing when it has it.

**Self-contained, because the case is that the plugin is absent.** The command
cannot call ``prawduct-hook`` or import ``lib/``; product repos commit no
framework files. So the check is inlined: POSIX ``sh`` around a short ``python3
-c`` verdict that mirrors :func:`lib.plugin_activation.plugin_activation_status`
— a ``user``/``global``-scope record, or one whose ``projectPath`` is this repo,
is active; a clean read with no such record is inactive; anything else is
unknown. The Python uses nothing newer than 3.0 (no f-strings), so the plugin's
own Python floor is not this hook's floor. If ``python3`` cannot be run at all
(absent, or the macOS shim that only offers to install the tools), the ``sh``
half still prints the could-not-verify line: a missing interpreter is visible.

**Never a false accusation.** Only ``inactive`` gets the loud line. A missing or
unparseable manifest, an unreadable record, or no interpreter gets a soft line
that says it could not verify and tells the agent how to tell for itself (the
banner). That is the stance ``plugin_activation`` takes, for the same reason:
``installed_plugins.json`` is a Claude Code internal.

**One owner.** :data:`TRIPWIRE_COMMAND` is the text; every writer
(``migrate_plugin.transform_settings``, so ``init-product`` and
``/prawduct:migrate``, and ``prawduct-hook install-tripwire`` for doctor) goes
through :func:`ensure_tripwire`, and every reader (``init_product``'s
already-present check, the install-reference probe) through
:func:`tripwire_state`. The hook is recognised by :data:`TRIPWIRE_TAG`, a no-op
``:`` line at the head of the command, so a later release can replace a stale
copy in place rather than add a second one.
"""

from __future__ import annotations

import json
from pathlib import Path

from .plugin_activation import PLUGIN_ID

#: The first line of the command. ``:`` is the shell's no-op, so the line costs
#: nothing at runtime and makes the hook findable by a writer. Bump the version
#: when the command changes; :func:`tripwire_state` reports an older copy stale.
TRIPWIRE_TAG = ": prawduct-unloaded-tripwire v1"

#: Same events the plugin's banner hook fires on, so "no banner appeared" and
#: "the tripwire would have spoken" cover the same session starts.
TRIPWIRE_MATCHER = "startup|resume|clear|compact|fork"

#: The verdict, read the way ``plugin_activation.plugin_activation_status``
#: reads the manifest. Prints one word: active | inactive | missing | unreadable.
#: Double quotes only — the ``sh`` wrapper single-quotes this text.
_VERDICT_PY = "\n".join([
    "import json,os,sys",
    "f=os.path.expanduser(sys.argv[1]);p=os.path.realpath(sys.argv[2])",
    "def out(v):",
    " print(v);sys.exit(0)",
    "try:",
    " m=json.load(open(f))",
    "except (IOError,OSError):",
    ' out("unreadable" if os.path.exists(f) else "missing")',
    "except ValueError:",
    ' out("unreadable")',
    'd=m.get("plugins") if isinstance(m,dict) else None',
    "if not isinstance(d,dict):",
    ' out("unreadable")',
    f'r=d.get("{PLUGIN_ID}")',
    "if r is None:",
    ' out("inactive")',
    "if not isinstance(r,list):",
    ' out("unreadable")',
    "b=0",
    "for x in r:",
    " if not isinstance(x,dict):",
    "  b=1;continue",
    ' if x.get("scope") in ("user","global"):',
    '  out("active")',
    ' q=x.get("projectPath")',
    " if not isinstance(q,str):",
    "  b=1;continue",
    " if os.path.realpath(os.path.expanduser(q))==p:",
    '  out("active")',
    'out("unreadable" if b else "inactive")',
])

#: What the agent reads when the manifest read cleanly and names no install for
#: this repo. It says what is missing, what to do first, what not to do, and the
#: fix — and names the one case it cannot tell apart (``--plugin-dir``).
INACTIVE_MESSAGE = (
    "PRAWDUCT GOVERNANCE IS NOT ACTIVE IN THIS SESSION. This repo is governed by "
    f"Prawduct, but {PLUGIN_ID} is not installed for it in this Claude Code profile "
    "($m): no session banner, no /prawduct:* skills, no Stop gates. Tell the user "
    "before any work, and do not imitate the gates by reading the plugin's files. "
    f"Fix: run claude plugin install {PLUGIN_ID} in this repo, then restart the "
    "session. (Loaded the plugin with --plugin-dir? Then ignore this line.)"
)

#: What the agent reads when the check could not answer. ``$v`` is the reason
#: word. It claims nothing about the install, only what to look for.
UNKNOWN_MESSAGE = (
    f"PRAWDUCT: could not verify that {PLUGIN_ID} is installed for this repo "
    "($v: $m). If no Prawduct session banner appeared at session start, "
    "governance is not loaded: tell the user before any work, and do not imitate "
    "its gates by reading the plugin's files."
)

TRIPWIRE_COMMAND = "\n".join([
    TRIPWIRE_TAG,
    'm="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/plugins/installed_plugins.json"',
    "v=$(python3 -c '" + _VERDICT_PY + "' \"$m\" \"${CLAUDE_PROJECT_DIR:-.}\" 2>/dev/null)"
    " || v=\"python3 could not be run\"",
    'case "$v" in',
    "active) ;;",
    f'inactive) echo "{INACTIVE_MESSAGE}" ;;',
    f'*) echo "{UNKNOWN_MESSAGE}" ;;',
    "esac",
    "exit 0",
])

#: The hook group written into ``hooks.SessionStart``.
TRIPWIRE_GROUP = {
    "matcher": TRIPWIRE_MATCHER,
    "hooks": [{"type": "command", "command": TRIPWIRE_COMMAND, "timeout": 10}],
}

PRESENT = "present"
ABSENT = "absent"
STALE = "stale"
#: ``hooks`` or ``hooks.SessionStart`` is not the shape Claude Code reads, so a
#: writer cannot add to it without guessing at the owner's intent.
MALFORMED = "malformed"


def _is_tripwire(hook: object) -> bool:
    return isinstance(hook, dict) and str(hook.get("command", "")).startswith(
        TRIPWIRE_TAG.rsplit(" ", 1)[0]
    )


def _session_start(data: dict):
    hooks = data.get("hooks")
    if hooks is None:
        return []
    if not isinstance(hooks, dict):
        return None
    groups = hooks.get("SessionStart", [])
    return groups if isinstance(groups, list) else None


def tripwire_state(data: object) -> str:
    """Whether parsed settings carry the current tripwire: one of ``PRESENT``,
    ``ABSENT``, ``STALE`` (an older or edited copy) or ``MALFORMED``."""
    if not isinstance(data, dict):
        return MALFORMED
    groups = _session_start(data)
    if groups is None:
        return MALFORMED
    found = [
        (group, hook)
        for group in groups
        if isinstance(group, dict) and isinstance(group.get("hooks"), list)
        for hook in group["hooks"]
        if _is_tripwire(hook)
    ]
    if not found:
        return ABSENT
    if len(found) == 1 and found[0][0] == TRIPWIRE_GROUP:
        return PRESENT
    return STALE


def ensure_tripwire(data: dict) -> bool:
    """Make parsed settings carry exactly one current tripwire; True iff changed.

    Removes every tripwire hook (an older version, or a duplicate) and appends
    the current group, leaving every other hook and group as it was. A
    ``MALFORMED`` hooks shape is left alone and reported unchanged — its owner
    decides what it meant.
    """
    state = tripwire_state(data)
    if state in (PRESENT, MALFORMED):
        return False
    hooks = data.setdefault("hooks", {})
    kept = []
    for group in hooks.get("SessionStart", []):
        if isinstance(group, dict) and isinstance(group.get("hooks"), list):
            inner = [h for h in group["hooks"] if not _is_tripwire(h)]
            if not inner:
                continue
            group = {**group, "hooks": inner}
        kept.append(group)
    kept.append(json.loads(json.dumps(TRIPWIRE_GROUP)))
    hooks["SessionStart"] = kept
    return True


def settings_path(project_dir: str | Path) -> Path:
    return Path(project_dir) / ".claude" / "settings.json"


def read_settings_state(project_dir: str | Path) -> str:
    """:func:`tripwire_state` of the repo's committed settings. A missing file is
    ``ABSENT``; an unreadable or non-JSON one is ``MALFORMED``."""
    path = settings_path(project_dir)
    if not path.is_file():
        return ABSENT
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return MALFORMED
    return tripwire_state(data)


def install(project_dir: str | Path, *, apply: bool) -> dict:
    """Report, and on ``apply`` write, the tripwire into ``.claude/settings.json``.

    Returns ``{"status", "applied", "path"}``: ``status`` is the state found
    before any write. Writes only on ``ABSENT``/``STALE``; never rewrites a
    malformed file. Every other key is preserved; line endings are not, since
    the settings writer prawduct already ships writes ``\\n`` JSON.
    """
    path = settings_path(project_dir)
    status = read_settings_state(project_dir)
    applied = False
    if apply and status in (ABSENT, STALE):
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        applied = ensure_tripwire(data)
        if applied:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {"status": status, "applied": applied, "path": str(path)}
