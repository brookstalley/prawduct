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
— a ``user``/``global``-scope record, or one whose ``projectPath`` is this repo
or, in a linked git worktree, its main checkout, is active; a clean read with no
such record is inactive; anything else is unknown. The Python uses nothing newer
than 3.0 (no f-strings), so the plugin's own Python floor is not this hook's
floor. If ``python3`` is not on ``PATH``, or exits non-zero (the macOS shim that
only offers to install the tools, or a manifest shape the verdict did not
expect), the ``sh`` half still prints the could-not-verify line and says which:
a missing interpreter is visible.

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
``:`` line at the head of the command, so a later release removes a stale copy
and appends the current group rather than adding a second one. A settings shape
the writer cannot add to is reported, never skipped silently
(:func:`skipped_warning`).
"""

from __future__ import annotations

import json
from pathlib import Path

#: The install contract's own id (``INSTALL_REFERENCE``), so the hook names the
#: plugin the settings file beside it enables. ``migrate_plugin`` imports this
#: module lazily, inside ``transform_settings``, to keep the import one-way.
from .migrate_plugin import PLUGIN_ID

#: The first line of the command. ``:`` is the shell's no-op, so the line costs
#: nothing at runtime and makes the hook findable by a writer. It carries no
#: version: :func:`tripwire_state` calls any copy that is not exactly
#: :data:`TRIPWIRE_GROUP` stale, so a changed command needs no other edit.
TRIPWIRE_TAG = ": prawduct-unloaded-tripwire"

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
    "def rd(x):",
    " try:return open(x).read().strip()",
    ' except (IOError,OSError,ValueError):return ""',
    # A linked git worktree's `.git` is a FILE naming its gitdir, and that
    # gitdir's `commondir` leads to the main checkout's `.git`. A record naming
    # the main checkout covers the worktree — plugin_activation.checkout_paths,
    # the same rule. A submodule's gitdir has no `commondir`, so it never matches.
    "P=[p]",
    'g=rd(os.path.join(p,".git"))',
    'if g.startswith("gitdir:"):',
    ' x=os.path.join(p,g[7:].strip());c=rd(os.path.join(x,"commondir"))',
    ' c=os.path.realpath(os.path.join(x,c)) if c else ""',
    ' if os.path.basename(c)==".git":P.append(os.path.dirname(c))',
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
    " if os.path.realpath(os.path.expanduser(q)) in P:",
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
    "if command -v python3 >/dev/null 2>&1; then",
    "v=$(python3 -c '" + _VERDICT_PY + "' \"$m\" \"${CLAUDE_PROJECT_DIR:-.}\" 2>/dev/null)"
    " || v=\"python3 exited $?, so the check did not finish\"",
    'else v="python3 not found"; fi',
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
    return isinstance(hook, dict) and str(hook.get("command", "")).startswith(TRIPWIRE_TAG)


def malformed_shape(data: object) -> str | None:
    """What about parsed settings stops a writer adding the hook, in words an
    owner can find in the file — or ``None`` when the shape is writable.

    ``null`` at ``hooks`` or ``hooks.SessionStart`` reads as absent: it states
    no hooks, and the writer replaces it with the one group it adds.
    """
    if not isinstance(data, dict):
        return "the settings file is not a JSON object"
    hooks = data.get("hooks")
    if hooks is None:
        return None
    if not isinstance(hooks, dict):
        return f"`hooks` is a JSON {_json_type(hooks)}, not an object"
    groups = hooks.get("SessionStart")
    if groups is None or isinstance(groups, list):
        return None
    return f"`hooks.SessionStart` is a JSON {_json_type(groups)}, not a list"


def _json_type(value: object) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object"


def _session_start(data: dict) -> list:
    return (data.get("hooks") or {}).get("SessionStart") or []


def tripwire_state(data: object) -> str:
    """Whether parsed settings carry the current tripwire: one of ``PRESENT``,
    ``ABSENT``, ``STALE`` (an older or edited copy) or ``MALFORMED``
    (:func:`malformed_shape` names why)."""
    if malformed_shape(data) is not None:
        return MALFORMED
    found = [
        (group, hook)
        for group in _session_start(data)
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

    Removes every tripwire hook (an older copy, or a duplicate) and appends the
    current group, leaving every other hook and group as it was. A ``MALFORMED``
    hooks shape is left alone and reported unchanged — its owner decides what it
    meant, and every caller says the hook was not written
    (:func:`skipped_warning`).
    """
    state = tripwire_state(data)
    if state in (PRESENT, MALFORMED):
        return False
    if data.get("hooks") is None:
        data["hooks"] = {}
    hooks = data["hooks"]
    kept = []
    for group in hooks.get("SessionStart") or []:
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


def read_settings(project_dir: str | Path) -> tuple[str, str | None]:
    """``(state, reason)`` for the repo's committed settings: ``reason`` names
    the malformed shape, and is ``None`` unless the state is ``MALFORMED``. A
    missing file is ``ABSENT``; an unreadable or non-JSON one is ``MALFORMED``."""
    path = settings_path(project_dir)
    if not path.is_file():
        return ABSENT, None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        return MALFORMED, f"the settings file could not be read ({exc.__class__.__name__})"
    except json.JSONDecodeError as exc:
        return MALFORMED, f"the settings file is not valid JSON (line {exc.lineno})"
    return tripwire_state(data), malformed_shape(data)


def read_settings_state(project_dir: str | Path) -> str:
    """:func:`tripwire_state` of the repo's committed settings."""
    return read_settings(project_dir)[0]


def skipped_warning(project_dir: str | Path) -> str | None:
    """The sentence a settings writer reports when it could not add the hook, or
    ``None`` when the hook is there. One home for it, so ``init-product`` and
    ``/prawduct:migrate`` say the same thing.

    Only a JSON object whose ``hooks`` shape the writer refuses: a file that is
    not a JSON object at all is replaced whole by ``transform_settings``, so the
    hook is written there."""
    path = settings_path(project_dir)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    reason = malformed_shape(data)
    if reason is None:
        return None
    return (
        f"Unloaded-plugin tripwire not written to .claude/settings.json: {reason}. "
        "Fix the shape by hand, then run `prawduct-hook install-tripwire --apply`; "
        "until then a session that loads no prawduct plugin here says nothing."
    )


def install(project_dir: str | Path, *, apply: bool) -> dict:
    """Report, and on ``apply`` write, the tripwire into ``.claude/settings.json``.

    Returns ``{"status", "applied", "path", "reason"}``: ``status`` is the state
    found before any write, and ``reason`` names the malformed shape (``None``
    otherwise). Writes only on ``ABSENT``/``STALE``; never rewrites a malformed
    file. Every other key is preserved; line endings are not, since the settings
    writer prawduct already ships writes ``\\n`` JSON.
    """
    path = settings_path(project_dir)
    status, reason = read_settings(project_dir)
    applied = False
    if apply and status in (ABSENT, STALE):
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        applied = ensure_tripwire(data)
        if applied:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {"status": status, "applied": applied, "path": str(path), "reason": reason}
