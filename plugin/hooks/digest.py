#!/usr/bin/env python3
"""Prawduct plugin SessionStart guidance digest.

Chunk 6 of the v2.0.0 plugin-distribution build plan. Injects a compact,
*supplemental* governance digest into the model's context at session start via
the SessionStart ``additionalContext`` channel (design §4: the full methodology
lives in the plugin and is read on demand through the ``/prawduct:*`` reader
skills; this digest is the session-start reminder, not a replacement for the
authoritative rules in the repo's instruction files).

Output: the host's session-context shape, written by
``host.emit_session_context`` (``lib/host.py`` owns the structured hook
responses).
Multiple SessionStart hooks compose — the banner (plain stdout) and the
``prawduct-hook clear`` briefing (plain stdout) still render alongside it.
Context over ~10,000 characters is spilled to a file by Claude Code, so the
digest is deliberately kept well under that.

The same output carries ``reloadSkills`` — but only when the governed repo is
the checkout this plugin ships from (``ships_from_this_repo``). Skill bodies are
cached per session and ``/clear`` does not refresh them, so in THIS repo a
session that edits a skill and then exercises it tests the previous version
while believing it tests the new one. Product repos never edit the plugin, so
they pay nothing for the re-scan.

Governing invariant (design §2): the plugin ships immutable, read-only code.
This script reads ONLY the plugin-bundled digest under the plugin root
(``host.plugin_root``; the whole plugin tree is copied into the cache on
install, so a plugin-root file resolves there) and writes nothing. All mutable,
per-repo state lives in the governed repo's ``.prawduct/`` and is not touched
here.
"""
from __future__ import annotations

# The Python floor, checked before anything newer is imported: below it, re-run
# this entry point under an interpreter that qualifies, or fail loudly. This WHOLE
# file must parse on old interpreters: Python compiles a file before running any
# of it, so newer syntax anywhere fails before this check (tests/test_python_floor.py).
import os as _os
import sys as _sys

try:
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.realpath(__file__)), "..", "bin"))
    try:
        import _python_floor  # noqa: E402
    finally:
        del _sys.path[0]
except (NameError, ImportError):
    # Run without a `__file__` (exec'd source) or copied without its sibling
    # module: there is no floor check to run, so run as before rather than
    # tracing back ahead of every command's own error handling.
    _python_floor = None
if _python_floor is not None and __name__ == "__main__":
    _python_floor.ensure(__file__)

import importlib.util  # noqa: E402 -- after the Python floor check
import sys  # noqa: E402 -- after the Python floor check
from pathlib import Path  # noqa: E402 -- after the Python floor check

# Source of truth for the digest text — one canonical document, bundled at the
# plugin root. This is the distilled session-start dose; the
# /prawduct:methodology reader skills serve the full guides on demand.
#
# ONE digest, no per-repo variants: every governed repo receives this file, the
# framework repo included. When a repo's own always-loaded CLAUDE.md overlaps
# this digest, the fix is to trim that CLAUDE.md, never to ship a second variant
# here — a variant duplicates every rule it carries into a shipped artifact all
# sessions pay for, and each duplicated rule then needs a must-agree pin to stop
# the two copies drifting.
DIGEST_RELPATH = ("methodology", "session-digest.md")


def _host():
    """The host seam (``lib/host.py``), which owns every read of the host's
    environment and every structured hook response. Loaded by file path, because
    this script runs before ``lib`` is importable; it imports nothing from
    ``lib``."""
    module = sys.modules.get("prawduct_host")
    if module is None:
        path = Path(__file__).resolve().parent.parent / "lib" / "host.py"
        spec = importlib.util.spec_from_file_location("prawduct_host", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["prawduct_host"] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            # A half-built module must not be what the next caller gets.
            del sys.modules["prawduct_host"]
            raise
    return module


def plugin_root() -> Path:
    """Resolve the plugin root: ``host.plugin_root``, the host's plugin-root
    variable (set by Claude Code when the hook fires, and exported to hook
    subprocesses), else the plugin tree this script sits in, so it is runnable
    directly in tests.
    """
    return Path(_host().plugin_root())


def read_digest(root: Path) -> str:
    """Read the bundled session-start guidance digest."""
    return (root.joinpath(*DIGEST_RELPATH)).read_text(encoding="utf-8").strip()


def project_dir() -> Path:
    """The governed repo — the host's launch dir (``host.project_dir_hint``;
    Claude Code sets ``CLAUDE_PROJECT_DIR`` for every hook), falling back to cwd
    for direct invocation."""
    return Path(_host().project_dir_hint() or ".").resolve()


def in_prawduct_repo() -> bool:
    """True when the consuming repo is Prawduct-governed — i.e. has a ``.prawduct/``.

    The plugin is user-scoped, so this SessionStart hook fires in *every* repo the
    user opens. The digest is product-session governance guidance; it must stay
    silent in repos that never onboarded. This mirrors the gate the banner
    (``hooks/banner.py``) and the Stop hook (``prawduct-hook`` ``cmd_stop``) already
    apply — ``.prawduct/`` is the single is-this-a-Prawduct-repo marker.

    Read-only: only ``.is_dir()``.
    """
    return (project_dir() / ".prawduct").is_dir()


def ships_from_this_repo() -> bool:
    """True when the governed repo IS the checkout this plugin ships from.

    Claude Code caches skill bodies per session, and `/clear` does not refresh
    them. So a session that edits `skills/*/SKILL.md` and then exercises that
    skill runs the PRE-EDIT body while believing it tests the new one — a
    silent-wrong-answer failure, not a slow one, because the work looks
    validated. Only this repo has that problem: it is the framework, so editing
    a skill and exercising it is the ordinary shape of a session here.

    A product repo has nothing to gain and a directory re-scan to pay, so the
    refresh is gated on the answer to "did this plugin come out of the repo I
    am governing?" — asked structurally rather than by name, because a repo
    called `prawduct` that installed the plugin from the marketplace is a
    product session, and a fork under any other name is not.

    Read-only: two path resolutions and a parent walk, no filesystem writes and
    no stat beyond what `resolve()` does.
    """
    try:
        root = plugin_root().resolve()
        project = project_dir()
    except OSError:
        # A resolvable-path failure must never break session start, and the
        # conservative answer is the one that costs a product repo nothing.
        return False
    return root == project or project in root.parents


def main() -> int:
    # Emit the governance digest only in a Prawduct-governed repo; stay silent
    # (and write nothing) everywhere else. Without this the user-scoped plugin
    # injects governance context into every repo the user opens (see banner.py /
    # cmd_stop, which already gate on .prawduct/).
    try:
        unknown = _host().unknown_host_reason()
    except Exception as exc:  # prawduct:allow prawduct/broad-except -- a digest failure must never break session start
        print(f"NOTE: Prawduct could not load its host seam: {exc}", file=sys.stderr)
        return 0
    try:
        governed = in_prawduct_repo()
    except OSError as exc:
        # The project directory could not be resolved (a deleted cwd, say).
        print(f"NOTE: Prawduct could not locate the project directory: {exc}", file=sys.stderr)
        return 0
    if not governed:
        return 0
    if unknown:
        print(f"NOTE: Prawduct session digest did nothing: {unknown}", file=sys.stderr)
        return 0
    try:
        digest = read_digest(plugin_root())
    except Exception as exc:  # prawduct:allow prawduct/broad-except -- a digest failure must never break session start
        print(f"NOTE: Prawduct could not read the session digest: {exc}", file=sys.stderr)
        return 0
    if not digest:
        return 0
    # Ask for a skill re-scan only here, so an edited skill body is the one this
    # session's forks load (see `ships_from_this_repo`).
    _host().emit_session_context(digest, reload_skills=ships_from_this_repo())
    return 0


if __name__ == "__main__":
    sys.exit(main())
