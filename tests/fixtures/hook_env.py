"""Run ``prawduct-hook`` where its environment notices cannot fire.

Before dispatching any command the hook may print a NOTE about the checkout it
was run from: a ``linked agent worktree`` notice when the project resolves to a
``.claude/worktrees/agent-*`` tree, and a ``plugin-binary-skew`` notice when a
framework checkout runs a plugin root other than its own. Both are correct
behaviour, and both belong to that checkout, not to the command under test.

A test that asserts on the WHOLE of stderr (empty, or its first line) is
therefore only valid when it runs the hook somewhere neither notice applies.
Run from the ambient checkout, it passes in CI and fails in every agent worktree
that runs the suite. The hook has no switch that silences the notices, and
filtering their lines out of stderr would also hide a regression that prints
them where they do not belong. So this helper removes their cause instead: the
project resolves to a directory the test owns, and the plugin root is pinned.

Use it for any test that asserts on all of stderr, and on all of stdout of
``clear --session-start``: that one call prints the skew notice on stdout, the
channel SessionStart injects into the agent's context. A test that asserts only
that a given string is or is not in a stream doesn't need it.
"""

from __future__ import annotations

import os
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2] / "plugin"
HOOK = PLUGIN_ROOT / "bin" / "prawduct-hook"


def isolated_hook_run(
    project_dir: Path,
    *,
    plugin_root: Path | None = None,
    env: dict[str, str] | None = None,
) -> dict:
    """``subprocess.run`` keyword arguments (``cwd`` and ``env``) that resolve
    the hook's project to ``project_dir``.

    It sets both because the hook reads both: ``cwd``'s git work tree, then
    ``CLAUDE_PROJECT_DIR``, and it follows ``cwd`` over the variable when the
    two are worktrees of one repository. Setting both leaves neither the
    inherited variable nor the inherited ``cwd`` a way to win.

    ``plugin_root`` defaults to this checkout's ``plugin/``. A test that
    exercises the skew guard on purpose passes its own. ``env`` replaces the
    inherited environment as the base when given.
    """
    merged = dict(os.environ if env is None else env)
    merged["CLAUDE_PROJECT_DIR"] = str(project_dir)
    merged["CLAUDE_PLUGIN_ROOT"] = str(plugin_root or PLUGIN_ROOT)
    return {"cwd": str(project_dir), "env": merged}
