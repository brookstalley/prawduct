"""Tests for the upstream bug-inbox resolver + the ``bug-inbox`` subcommand
(upstream-bug-reporting, Chunk 01).

The resolver's *inert* cases ARE the product guarantees: a plugin-only user
(neither signal configured) and a stale/unwritable config must both resolve to
``None`` so ``/prawduct:report-bug`` never errors or nags. They are first-class
tests here, not afterthoughts.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
from pathlib import Path

import pytest

from lib.bug_inbox import ENV_VAR, resolve_inbox

_ROOT = Path(__file__).resolve().parent.parent / "plugin"

# Load the extensionless plugin-runtime hook the same way test_build_plan_resolution
# does (SourceFileLoader — the script has a shebang, no .py extension). The module
# name is not "__main__", so its CLI dispatch does not run at import.
_hook_loader = importlib.machinery.SourceFileLoader(
    "prawduct_hook_bug_inbox", str(_ROOT / "bin" / "prawduct-hook")
)
_hook_spec = importlib.util.spec_from_loader("prawduct_hook_bug_inbox", _hook_loader)
_hook = importlib.util.module_from_spec(_hook_spec)
_hook_loader.exec_module(_hook)


@pytest.fixture
def project(tmp_path):
    """A product-repo skeleton: ``<root>/.prawduct/`` exists."""
    (tmp_path / ".prawduct").mkdir()
    return tmp_path


@pytest.fixture
def inbox(tmp_path):
    """A reachable inbox dir (a co-located prawduct checkout's incoming-bugs/)."""
    d = tmp_path / "prawduct-checkout" / "incoming-bugs"
    d.mkdir(parents=True)
    return d


def _pointer(project: Path) -> Path:
    return project / ".prawduct" / ".bug-inbox"


# --- resolve_inbox: precedence + validation matrix ---------------------------

def test_env_var_valid_returns_path(project, inbox):
    assert resolve_inbox({ENV_VAR: str(inbox)}, project) == inbox.resolve()


def test_env_var_stale_returns_none(project, tmp_path):
    assert resolve_inbox({ENV_VAR: str(tmp_path / "does-not-exist")}, project) is None


def test_env_var_pointing_at_a_file_returns_none(project, tmp_path):
    f = tmp_path / "a-file"
    f.write_text("x", encoding="utf-8")
    assert resolve_inbox({ENV_VAR: str(f)}, project) is None


def test_env_var_blank_returns_none(project):
    assert resolve_inbox({ENV_VAR: "   "}, project) is None


def test_pointer_file_valid_returns_path(project, inbox):
    _pointer(project).write_text(str(inbox) + "\n", encoding="utf-8")
    assert resolve_inbox({}, project) == inbox.resolve()


def test_pointer_file_skips_comments_and_blanks(project, inbox):
    _pointer(project).write_text(f"# my prawduct checkout\n\n{inbox}\n", encoding="utf-8")
    assert resolve_inbox({}, project) == inbox.resolve()


def test_pointer_file_stale_returns_none(project, tmp_path):
    _pointer(project).write_text(str(tmp_path / "nope") + "\n", encoding="utf-8")
    assert resolve_inbox({}, project) is None


def test_neither_signal_returns_none(project):
    # The plugin-only user — this is the inert guarantee.
    assert resolve_inbox({}, project) is None


def test_env_takes_precedence_over_pointer(project, tmp_path):
    env_dir = tmp_path / "env-inbox"
    env_dir.mkdir()
    ptr_dir = tmp_path / "ptr-inbox"
    ptr_dir.mkdir()
    _pointer(project).write_text(str(ptr_dir) + "\n", encoding="utf-8")
    assert resolve_inbox({ENV_VAR: str(env_dir)}, project) == env_dir.resolve()


def test_unwritable_dir_returns_none(project, tmp_path):
    d = tmp_path / "ro-inbox"
    d.mkdir()
    d.chmod(0o500)
    try:
        if os.access(d, os.W_OK):  # root bypasses perms — the assertion wouldn't hold
            pytest.skip("running as root — W_OK is bypassed")
        assert resolve_inbox({ENV_VAR: str(d)}, project) is None
    finally:
        d.chmod(0o700)


# --- bug-inbox subcommand: exit-code contract --------------------------------

def test_subcommand_exit_0_prints_resolved_path(project, inbox, monkeypatch, capsys):
    monkeypatch.setenv(ENV_VAR, str(inbox))
    rc = _hook.cmd_bug_inbox(project)
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert out == str(inbox.resolve())


def test_subcommand_exit_1_when_no_inbox(project, monkeypatch, capsys):
    monkeypatch.delenv(ENV_VAR, raising=False)
    rc = _hook.cmd_bug_inbox(project)
    out = capsys.readouterr().out.strip()
    assert rc == 1
    assert out == ""
