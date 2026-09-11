"""Whether the prawduct plugin is actually LOADED for a given repo.

A repo can carry a byte-perfect install reference — ``.claude/settings.json``
with ``extraKnownMarketplaces.prawduct`` and
``enabledPlugins["prawduct@prawduct"] = true`` — a fully scaffolded
``.prawduct/``, and a ``CLAUDE.md`` promising that "the plugin's Stop hook runs
at session end and blocks", and still have **no governance whatsoever**: no
session banner, no ``/prawduct:*`` skills, no hooks. Project-scope *enablement*
is not *installation*. The harness additionally requires a record in
``~/.claude/plugins/installed_plugins.json`` whose ``projectPath`` is that repo.

**Why this cannot be a session probe, which is the whole design.** Every other
"is this repo healthy" check prawduct owns runs *inside* the repo's own session —
an advisory probe, or a ``/prawduct:doctor`` step. Neither can reach this failure,
because both are delivered BY the plugin: when the plugin does not load, the
probe does not run and the skill cannot be invoked. The agent reads the CLAUDE.md
stanza, believes it, and proceeds ungoverned. So the detector has to run from
*outside* the repo — from the onboarding session, which lives elsewhere and can
see the target. That is why this module takes an explicit ``project_dir`` rather
than inferring one, and why its caller is ``/prawduct:onboard`` rather than a
probe registry.

**Fail-soft, and never in the direction of a false accusation.**
``installed_plugins.json`` is a Claude Code *internal* file — not a documented
contract prawduct is entitled to rely on. Every read or shape problem therefore
yields ``unknown`` ("could not verify"), never ``inactive`` ("not installed").
The two are different answers and the distinction is load-bearing: telling an
operator their plugin is not installed, when in truth a file could not be parsed,
sends them to reinstall something that was never broken. Only a file that read
cleanly and demonstrably lacks a matching record returns ``inactive``.

**Structural parsing, not version-gating.** The file carries a top-level
``version`` (2 at time of writing). This module does not branch on it. It looks
for the shape it needs — ``plugins`` as a mapping, the plugin's entry as a list
of records — and reports ``unknown`` when that shape is absent. A harness release
that bumps the version while keeping the shape keeps working; one that changes
the shape says "could not verify" instead of guessing. Version-gating would have
inverted both cases. The observed ``version`` rides along in the result for
diagnostics, and nothing reads it to reach a verdict.

Return-value based per ``project-preferences.md``: this returns a status dict and
raises nothing. The CLI wrapper in ``bin/prawduct-hook`` maps it to an exit code.
"""

from __future__ import annotations

import json
import os
import shlex
from pathlib import Path

#: The plugin as the harness names it: ``<plugin>@<marketplace>``.
PLUGIN_ID = "prawduct@prawduct"

#: Where the harness records what is installed where. Overridable for tests and
#: for a non-default ``CLAUDE_CONFIG_DIR``.
DEFAULT_PLUGINS_FILE = Path("~/.claude/plugins/installed_plugins.json")

#: ``scope`` values that make a record apply to every project rather than one.
#: A user-scope install governs the target repo without naming it, so a record
#: carrying one satisfies the check with no path comparison.
_GLOBAL_SCOPES = frozenset({"user", "global"})

ACTIVE = "active"
INACTIVE = "inactive"
UNKNOWN = "unknown"


def default_plugins_file() -> Path:
    """The harness's installed-plugins manifest, honouring ``CLAUDE_CONFIG_DIR``.

    Resolved at call time rather than import time so a test or a caller that
    sets the environment variable is not defeated by import ordering.
    """
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    if config_dir:
        return Path(config_dir).expanduser() / "plugins" / "installed_plugins.json"
    return DEFAULT_PLUGINS_FILE.expanduser()


def _same_path(a: str, b: Path) -> bool:
    """Whether ``a`` names the same directory as ``b``.

    Compares resolved paths so a symlinked or trailing-slash spelling of the
    same repo still matches. A path that cannot be resolved (it no longer
    exists, or is not a valid path) is simply not a match — this is a
    comparison, not a validation, and the caller has already decided what an
    absent match means.
    """
    try:
        return Path(a).expanduser().resolve() == b
    except (OSError, ValueError, RuntimeError):
        return False


def plugin_activation_status(
    project_dir: str | Path,
    *,
    plugin_id: str = PLUGIN_ID,
    plugins_file: str | Path | None = None,
) -> dict:
    """Whether ``plugin_id`` is installed for ``project_dir``.

    Returns a dict carrying:

    ``status``
        ``"active"`` — a record covers this repo (path match, or a global-scope
        install). ``"inactive"`` — the manifest read cleanly and holds no such
        record; the repo is genuinely ungoverned. ``"unknown"`` — the question
        could not be answered. **Never** conflate the last two.
    ``reason``
        One sentence naming what was found, suitable for an operator.
    ``plugin_id``, ``project_path``, ``plugins_file``
        The inputs as resolved, so a report can name them.
    ``matched_scope``
        The ``scope`` of the record that matched, or ``None``.
    ``manifest_version``
        The manifest's top-level ``version``, for diagnostics only. Nothing
        branches on it (see the module docstring).
    ``other_paths``
        Project paths the plugin IS installed for, when this one is not. This is
        what makes an ``inactive`` report actionable rather than merely
        negative — the field case had entries for two unrelated repos, and
        seeing them is what identified the failure.
    """
    path = Path(plugins_file) if plugins_file is not None else default_plugins_file()
    try:
        target = Path(project_dir).expanduser().resolve()
    except (OSError, ValueError, RuntimeError) as exc:
        return _unknown(
            plugin_id, str(project_dir), path,
            f"the target path could not be resolved ({exc.__class__.__name__})",
        )

    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _unknown(
            plugin_id, str(target), path,
            "the harness's installed-plugins manifest does not exist at this "
            "path, so what is installed cannot be read",
        )
    except (OSError, UnicodeDecodeError) as exc:
        return _unknown(
            plugin_id, str(target), path,
            f"the installed-plugins manifest could not be read "
            f"({exc.__class__.__name__})",
        )

    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as exc:
        return _unknown(
            plugin_id, str(target), path,
            f"the installed-plugins manifest is not valid JSON (line {exc.lineno})",
        )

    if not isinstance(manifest, dict):
        return _unknown(
            plugin_id, str(target), path,
            "the installed-plugins manifest is not a JSON object",
        )

    version = manifest.get("version")
    plugins = manifest.get("plugins")
    if not isinstance(plugins, dict):
        return _unknown(
            plugin_id, str(target), path,
            "the installed-plugins manifest has no `plugins` object — its shape "
            "is not the one this check knows how to read",
            manifest_version=version,
        )

    records = plugins.get(plugin_id)
    if records is None:
        return {
            "status": INACTIVE,
            "reason": (
                f"`{plugin_id}` has no entry in the installed-plugins manifest — "
                "it is not installed for this or any project"
            ),
            "plugin_id": plugin_id,
            "project_path": str(target),
            "plugins_file": str(path),
            "matched_scope": None,
            "manifest_version": version,
            "other_paths": [],
        }

    if not isinstance(records, list):
        return _unknown(
            plugin_id, str(target), path,
            f"`{plugin_id}`'s manifest entry is not a list — its shape is not "
            "the one this check knows how to read",
            manifest_version=version,
        )

    other_paths: list[str] = []
    malformed = 0
    for record in records:
        if not isinstance(record, dict):
            malformed += 1
            continue
        scope = record.get("scope")
        if isinstance(scope, str) and scope in _GLOBAL_SCOPES:
            return {
                "status": ACTIVE,
                "reason": (
                    f"`{plugin_id}` is installed at `{scope}` scope, which covers "
                    "every project including this one"
                ),
                "plugin_id": plugin_id,
                "project_path": str(target),
                "plugins_file": str(path),
                "matched_scope": scope,
                "manifest_version": version,
                "other_paths": [],
            }
        project_path = record.get("projectPath")
        if not isinstance(project_path, str):
            malformed += 1
            continue
        if _same_path(project_path, target):
            return {
                "status": ACTIVE,
                "reason": (
                    f"`{plugin_id}` is installed for this project "
                    f"(scope `{scope}`)"
                ),
                "plugin_id": plugin_id,
                "project_path": str(target),
                "plugins_file": str(path),
                "matched_scope": scope if isinstance(scope, str) else None,
                "manifest_version": version,
                "other_paths": [],
            }
        other_paths.append(project_path)

    if malformed:
        # A record this check could not read might have been the matching one,
        # so "no match" is not a finding here — it is an unanswered question.
        return _unknown(
            plugin_id, str(target), path,
            f"{malformed} of {len(records)} manifest record(s) for "
            f"`{plugin_id}` could not be read, and none of the readable ones "
            "matched this project — the answer would be a guess",
            manifest_version=version,
        )

    return {
        "status": INACTIVE,
        "reason": (
            f"`{plugin_id}` has {len(other_paths)} manifest record(s), none "
            "naming this project path"
        ),
        "plugin_id": plugin_id,
        "project_path": str(target),
        "plugins_file": str(path),
        "matched_scope": None,
        "manifest_version": version,
        "other_paths": other_paths,
    }


def _unknown(
    plugin_id: str,
    project_path: str,
    plugins_file: Path,
    reason: str,
    *,
    manifest_version=None,
) -> dict:
    """An unanswerable question, shaped like every other answer.

    Kept as one constructor so every degradation path returns the same keys —
    a caller reading ``other_paths`` or ``matched_scope`` must not have to know
    which failure it is looking at.
    """
    return {
        "status": UNKNOWN,
        "reason": reason,
        "plugin_id": plugin_id,
        "project_path": project_path,
        "plugins_file": str(plugins_file),
        "matched_scope": None,
        "manifest_version": manifest_version,
        "other_paths": [],
    }


def remediation_command(project_dir: str | Path) -> str:
    """The exact command an operator runs to fix an ``inactive`` repo.

    Named here rather than written into the onboard skill's prose so the
    instruction and the check that produces it cannot drift apart.

    The path is shell-quoted because this line is produced to be **pasted**: an
    unquoted repo path containing a space yields a command that fails when the
    operator runs it, and the failure lands on someone already dealing with a
    broken install. `tmp_path` in a test never contains a space, so this needs
    its own fixture rather than trusting the incidental one.
    """
    return f"cd {shlex.quote(str(Path(project_dir)))} && claude plugin install {PLUGIN_ID}"


ONBOARD = "onboard"
DOCTOR = "doctor"


def report_lines(result: dict, *, context: str = ONBOARD) -> list[str]:
    """The operator-facing report for a status dict.

    One home for the wording, so the CLI and any skill relaying it say the same
    thing. An ``unknown`` result leads with what could NOT be established —
    advice fails soft, but a degraded advisory that does not name its
    consequence manufactures the false success it exists to prevent.

    **``context`` exists because the same status means different things to the
    two callers, and getting this wrong is the module's own failure mode aimed
    at itself.** From ``/prawduct:onboard`` — running outside the target — an
    ``inactive`` means the repo will load nothing at all, which is the disaster
    this module was written for. From ``/prawduct:doctor`` it cannot mean that:
    doctor IS a plugin skill, so the plugin demonstrably loaded, and the only
    thing an ``inactive`` can indicate there is that the manifest's record does
    not name *this* path — a worktree, a moved, renamed or symlinked checkout.
    Relaying the onboard consequence there would send an operator to reinstall a
    working install, which is the false accusation the rest of this module
    refuses to make. Two consequences, two messages, one home.
    """
    status = result.get("status")
    if status == ACTIVE:
        return [f"active: {result['reason']}."]

    if status == INACTIVE and context == DOCTOR:
        lines = [
            f"stale install record: {result['reason']}.",
            "",
            "The plugin plainly DID load — you are running one of its skills — so "
            "this is not an ungoverned repo. What it means is that the manifest "
            "holds no record for this exact path: a git worktree, or a checkout "
            "that was moved, renamed, or is reached through a symlink. Session "
            "state still resolves, but the record no longer describes reality.",
            "",
            f"Re-point it if you want the record accurate: "
            f"{remediation_command(result['project_path'])}",
        ]
        others = result.get("other_paths") or []
        if others:
            lines.extend(["", f"Recorded instead for: {', '.join(others)}"])
        return lines

    if status == INACTIVE:
        lines = [
            f"inactive: {result['reason']}.",
            "",
            "Enabling the plugin in `.claude/settings.json` does not install it "
            "— the harness needs a record naming this path, and there is none. "
            "This repo will start a session with NO governance: no session "
            "briefing, no `/prawduct:*` skills, and no Stop-hook gates — while "
            "its CLAUDE.md states that governance is enforced.",
            "",
            f"Fix: {remediation_command(result['project_path'])}",
        ]
        others = result.get("other_paths") or []
        if others:
            lines.extend([
                "",
                f"Installed instead for: {', '.join(others)}",
            ])
        return lines

    return [
        f"NOTE: could not verify whether `{result.get('plugin_id', PLUGIN_ID)}` "
        f"is installed for this project — {result.get('reason')}.",
        "",
        "This is NOT a clean bill: the check did not run, so the repo may be "
        "governed or may be silently ungoverned. Confirm by opening it in a "
        "Claude Code session and looking for the prawduct session briefing.",
    ]
